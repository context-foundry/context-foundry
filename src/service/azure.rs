//! Shared Azure plumbing for the M5 production backends.
//!
//! Env-driven [`AzureConfig`], a managed-identity (IMDS) token source, retry/
//! backoff, Azure Blob REST helpers, and the service-SAS signing algorithm.
//! Used by both [`super::azure_blob`] and [`super::azure_aca`]. Everything is
//! implemented against the Azure REST APIs with the already-present `reqwest`
//! dependency — no `azure_*` SDK crate is pulled in.
//!
//! This whole module compiles only under `--features azure`.

use std::collections::HashMap;
use std::future::Future;
use std::sync::Mutex;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use anyhow::{anyhow, bail, Context, Result};
use base64::Engine;
use chrono::{DateTime, Utc};
use hmac::{Hmac, Mac};
use sha2::Sha256;

/// The Azure storage REST/SAS service version this module signs against.
/// 2020-12-06 and later put `signedEncryptionScope` in the service-SAS
/// string-to-sign, so the 16-field layout below is correct for this version.
const SAS_VERSION: &str = "2022-11-02";

// ─── Config ─────────────────────────────────────────────────────────────────

/// All Azure deployment config, resolved from `FOUNDRY_SERVICE_AZURE_*` env
/// vars. Kept separate from `ServiceConfig` so the local/VPS struct literal is
/// untouched (mirrors how T35.7d added `UpstreamAuthConfig`).
#[derive(Clone, Debug)]
pub struct AzureConfig {
    pub subscription_id: String,
    pub resource_group: String,
    pub location: String,
    pub storage_account: String,
    pub storage_container: String,
    pub storage_account_key: String,
    pub acr_name: String,
    pub aca_environment: String,
    /// Empty = system-assigned managed identity.
    pub managed_identity_client_id: String,
    pub arm_endpoint: String,
    pub blob_endpoint: String,
    pub imds_endpoint: String,
    pub signed_url_ttl_secs: u64,
    pub sas_grant_ttl_secs: u64,
}

/// Read an env var, falling back to a default (mirrors `config.rs` `env_or`).
fn azure_env_or(key: &str, default: &str) -> String {
    std::env::var(key)
        .ok()
        .filter(|s| !s.is_empty())
        .unwrap_or_else(|| default.to_string())
}

/// Read a mandatory env var, failing fast when absent or empty.
fn azure_env_required(key: &str) -> Result<String> {
    match std::env::var(key) {
        Ok(v) if !v.is_empty() => Ok(v),
        _ => bail!("{key} is required for the Azure backend but is unset"),
    }
}

impl AzureConfig {
    /// Resolve every Azure setting from the environment.
    pub fn from_env() -> Result<AzureConfig> {
        let subscription_id = azure_env_required("FOUNDRY_SERVICE_AZURE_SUBSCRIPTION_ID")?;
        let resource_group = azure_env_required("FOUNDRY_SERVICE_AZURE_RESOURCE_GROUP")?;
        let location = azure_env_required("FOUNDRY_SERVICE_AZURE_LOCATION")?;
        let storage_account = azure_env_required("FOUNDRY_SERVICE_AZURE_STORAGE_ACCOUNT")?;
        let storage_account_key = azure_env_required("FOUNDRY_SERVICE_AZURE_STORAGE_KEY")?;
        let acr_name = azure_env_required("FOUNDRY_SERVICE_AZURE_ACR_NAME")?;
        let aca_environment = azure_env_required("FOUNDRY_SERVICE_AZURE_ACA_ENVIRONMENT")?;
        let storage_container =
            azure_env_or("FOUNDRY_SERVICE_AZURE_STORAGE_CONTAINER", "foundry-jobs");
        let managed_identity_client_id = azure_env_or("FOUNDRY_SERVICE_AZURE_MI_CLIENT_ID", "");
        let arm_endpoint =
            azure_env_or("FOUNDRY_SERVICE_AZURE_ARM_URL", "https://management.azure.com");
        let blob_endpoint = azure_env_or(
            "FOUNDRY_SERVICE_AZURE_BLOB_URL",
            &format!("https://{storage_account}.blob.core.windows.net"),
        );
        let imds_endpoint = azure_env_or(
            "FOUNDRY_SERVICE_AZURE_IMDS_URL",
            "http://169.254.169.254/metadata/identity/oauth2/token",
        );
        let signed_url_ttl_secs = azure_env_or("FOUNDRY_SERVICE_AZURE_SIGNED_URL_TTL_SECS", "900")
            .parse()
            .context("parse FOUNDRY_SERVICE_AZURE_SIGNED_URL_TTL_SECS")?;
        let sas_grant_ttl_secs = azure_env_or("FOUNDRY_SERVICE_AZURE_SAS_GRANT_TTL_SECS", "3600")
            .parse()
            .context("parse FOUNDRY_SERVICE_AZURE_SAS_GRANT_TTL_SECS")?;
        Ok(AzureConfig {
            subscription_id,
            resource_group,
            location,
            storage_account,
            storage_container,
            storage_account_key,
            acr_name,
            aca_environment,
            managed_identity_client_id,
            arm_endpoint,
            blob_endpoint,
            imds_endpoint,
            signed_url_ttl_secs,
            sas_grant_ttl_secs,
        })
    }
}

/// A shared `reqwest` client for all Azure REST calls.
pub fn http_client() -> reqwest::Client {
    reqwest::Client::builder()
        .timeout(Duration::from_secs(30))
        .build()
        .unwrap_or_else(|_| reqwest::Client::new())
}

// ─── Small pure helpers ─────────────────────────────────────────────────────

/// Render a `SystemTime` in Azure's SAS timestamp format (no fractional secs).
pub fn iso8601(t: SystemTime) -> String {
    DateTime::<Utc>::from(t)
        .format("%Y-%m-%dT%H:%M:%SZ")
        .to_string()
}

/// Percent-encode a string for safe inclusion in a URL query value.
pub fn percent_encode(s: &str) -> String {
    let mut out = String::with_capacity(s.len());
    for &b in s.as_bytes() {
        let unreserved = b.is_ascii_alphanumeric() || matches!(b, b'-' | b'_' | b'.' | b'~');
        if unreserved {
            out.push(b as char);
        } else {
            out.push_str(&format!("%{b:02X}"));
        }
    }
    out
}

/// Build the IMDS token-request URL — the pure, testable seam of managed
/// identity. A non-empty `client_id` selects a user-assigned identity.
pub fn imds_token_url(endpoint: &str, resource: &str, client_id: &str) -> String {
    let mut url = format!(
        "{endpoint}?api-version=2018-02-01&resource={}",
        percent_encode(resource)
    );
    if !client_id.is_empty() {
        url.push_str(&format!("&client_id={}", percent_encode(client_id)));
    }
    url
}

/// Parse the total blob size out of a `Content-Range: bytes 0-49/120` header.
pub fn parse_total_size(content_range: &str) -> Option<u64> {
    content_range
        .rsplit('/')
        .next()
        .and_then(|tail| tail.trim().parse::<u64>().ok())
}

// ─── Retry / backoff ────────────────────────────────────────────────────────

/// Retry a transient async op with exponential backoff (200ms, 400ms, ...).
pub async fn with_retry<T, F, Fut>(label: &str, max_attempts: u32, op: F) -> Result<T>
where
    F: Fn(u32) -> Fut,
    Fut: Future<Output = Result<T>>,
{
    let mut attempt = 1;
    loop {
        match op(attempt).await {
            Ok(v) => return Ok(v),
            Err(e) => {
                if attempt >= max_attempts {
                    return Err(e.context(format!(
                        "{label} failed after {max_attempts} attempts"
                    )));
                }
                let backoff = Duration::from_millis(200 * 2u64.pow(attempt - 1));
                tokio::time::sleep(backoff).await;
                attempt += 1;
            }
        }
    }
}

// ─── Managed identity ───────────────────────────────────────────────────────

/// An IMDS-backed AAD token source. Caches one token per AAD resource and
/// refuses to hand back a token within 120s of expiry.
pub struct ManagedIdentityCredential {
    client: reqwest::Client,
    imds_endpoint: String,
    mi_client_id: String,
    cache: Mutex<HashMap<String, (String, SystemTime)>>,
}

impl ManagedIdentityCredential {
    pub fn new(client: reqwest::Client, cfg: &AzureConfig) -> Self {
        ManagedIdentityCredential {
            client,
            imds_endpoint: cfg.imds_endpoint.clone(),
            mi_client_id: cfg.managed_identity_client_id.clone(),
            cache: Mutex::new(HashMap::new()),
        }
    }

    /// Return a valid AAD bearer token for `resource`, fetching from IMDS and
    /// caching it. The `Metadata: true` header is what proves to IMDS that the
    /// caller is on the instance (the managed-identity credential path).
    pub async fn token(&self, resource: &str) -> Result<String> {
        {
            let cache = self.cache.lock().expect("token cache poisoned");
            if let Some((tok, expiry)) = cache.get(resource) {
                let fresh = expiry
                    .duration_since(SystemTime::now())
                    .map(|d| d > Duration::from_secs(120))
                    .unwrap_or(false);
                if fresh {
                    return Ok(tok.clone());
                }
            }
        }

        let url = imds_token_url(&self.imds_endpoint, resource, &self.mi_client_id);
        let body: serde_json::Value = with_retry("imds token", 4, |_| async {
            let resp = self
                .client
                .get(&url)
                .header("Metadata", "true")
                .send()
                .await
                .context("send IMDS token request")?;
            let status = resp.status();
            if !status.is_success() {
                bail!("IMDS token request -> HTTP {status}");
            }
            resp.json::<serde_json::Value>()
                .await
                .context("parse IMDS token JSON")
        })
        .await
        .context("acquire managed identity token")?;

        let token = body
            .get("access_token")
            .and_then(|v| v.as_str())
            .filter(|s| !s.is_empty())
            .ok_or_else(|| anyhow!("IMDS token response had no access_token"))?
            .to_string();
        let expiry = body
            .get("expires_on")
            .and_then(|v| v.as_str())
            .and_then(|s| s.parse::<u64>().ok())
            .map(|secs| UNIX_EPOCH + Duration::from_secs(secs))
            .unwrap_or_else(|| SystemTime::now() + Duration::from_secs(600));

        self.cache
            .lock()
            .expect("token cache poisoned")
            .insert(resource.to_string(), (token.clone(), expiry));
        Ok(token)
    }
}

// ─── Service-SAS signing ────────────────────────────────────────────────────

/// Inputs for a single-blob service SAS.
pub struct SasParams<'a> {
    pub account: &'a str,
    pub account_key: &'a str,
    pub container: &'a str,
    pub blob_path: &'a str,
    pub permissions: &'a str,
    pub start: SystemTime,
    pub expiry: SystemTime,
}

/// Produce a service-SAS query string for one blob (no leading `?`).
///
/// The 16-field string-to-sign matches storage service version 2020-12-06+
/// (`signedEncryptionScope` is field 11). HTTPS-only (`spr=https`).
pub fn build_blob_sas(p: &SasParams) -> Result<String> {
    let sv = SAS_VERSION;
    let sr = "b"; // blob resource
    let st = iso8601(p.start);
    let se = iso8601(p.expiry);
    let canonical = format!("/blob/{}/{}/{}", p.account, p.container, p.blob_path);

    // Joined with '\n' in this exact order — see Azure "Create a service SAS".
    let string_to_sign = [
        p.permissions, // signedPermissions
        &st,           // signedStart
        &se,           // signedExpiry
        &canonical,    // canonicalizedResource
        "",            // signedIdentifier
        "",            // signedIP
        "https",       // signedProtocol
        sv,            // signedVersion
        sr,            // signedResource
        "",            // signedSnapshotTime
        "",            // signedEncryptionScope
        "",            // rscc (Cache-Control)
        "",            // rscd (Content-Disposition)
        "",            // rsce (Content-Encoding)
        "",            // rscl (Content-Language)
        "",            // rsct (Content-Type)
    ]
    .join("\n");

    let key = base64::engine::general_purpose::STANDARD
        .decode(p.account_key)
        .context("decode storage account key")?;
    let mut mac = Hmac::<Sha256>::new_from_slice(&key)
        .map_err(|e| anyhow!("invalid storage account key length: {e}"))?;
    mac.update(string_to_sign.as_bytes());
    let sig = base64::engine::general_purpose::STANDARD.encode(mac.finalize().into_bytes());

    Ok(format!(
        "sv={sv}&sr={sr}&sp={}&st={}&se={}&spr=https&sig={}",
        percent_encode(p.permissions),
        percent_encode(&st),
        percent_encode(&se),
        percent_encode(&sig),
    ))
}

// ─── Blob REST ──────────────────────────────────────────────────────────────

/// The absolute URL of a blob within the configured container.
fn blob_url(cfg: &AzureConfig, blob_path: &str) -> String {
    format!(
        "{}/{}/{}",
        cfg.blob_endpoint, cfg.storage_container, blob_path
    )
}

/// A range read of a blob, used to tail the append-blob log stream.
#[derive(Clone, Debug)]
pub struct RangeRead {
    pub bytes: Vec<u8>,
    /// Total blob size parsed from the `Content-Range` header, when present.
    pub total: Option<u64>,
    pub etag: Option<String>,
}

/// Upload (overwrite) a block blob.
pub async fn blob_put_block(
    client: &reqwest::Client,
    mi: &ManagedIdentityCredential,
    cfg: &AzureConfig,
    blob_path: &str,
    bytes: Vec<u8>,
    content_type: &str,
) -> Result<()> {
    let token = mi.token("https://storage.azure.com/").await?;
    let url = blob_url(cfg, blob_path);
    with_retry("blob put", 3, |_| async {
        let resp = client
            .put(&url)
            .bearer_auth(&token)
            .header("x-ms-version", SAS_VERSION)
            .header("x-ms-blob-type", "BlockBlob")
            .header("Content-Type", content_type)
            .body(bytes.clone())
            .send()
            .await
            .context("send blob put")?;
        let status = resp.status();
        if !status.is_success() {
            bail!("blob put {blob_path} -> HTTP {status}");
        }
        Ok(())
    })
    .await
}

/// Download a whole blob; `Ok(None)` on 404.
pub async fn blob_get(
    client: &reqwest::Client,
    mi: &ManagedIdentityCredential,
    cfg: &AzureConfig,
    blob_path: &str,
) -> Result<Option<Vec<u8>>> {
    let token = mi.token("https://storage.azure.com/").await?;
    let url = blob_url(cfg, blob_path);
    with_retry("blob get", 3, |_| async {
        let resp = client
            .get(&url)
            .bearer_auth(&token)
            .header("x-ms-version", SAS_VERSION)
            .send()
            .await
            .context("send blob get")?;
        let status = resp.status();
        if status == reqwest::StatusCode::NOT_FOUND {
            return Ok(None);
        }
        if !status.is_success() {
            bail!("blob get {blob_path} -> HTTP {status}");
        }
        Ok(Some(resp.bytes().await.context("read blob body")?.to_vec()))
    })
    .await
}

/// Range-read a blob for the append-blob tail. `Ok(None)` when the blob does
/// not exist yet (404).
pub async fn blob_get_range(
    client: &reqwest::Client,
    mi: &ManagedIdentityCredential,
    cfg: &AzureConfig,
    blob_path: &str,
    range_header: &str,
) -> Result<Option<RangeRead>> {
    let token = mi.token("https://storage.azure.com/").await?;
    let url = blob_url(cfg, blob_path);
    with_retry("blob range get", 3, |_| async {
        let resp = client
            .get(&url)
            .bearer_auth(&token)
            .header("x-ms-version", SAS_VERSION)
            .header("Range", range_header)
            .send()
            .await
            .context("send blob range get")?;
        let status = resp.status();
        if status == reqwest::StatusCode::NOT_FOUND {
            return Ok(None);
        }
        let etag = resp
            .headers()
            .get("etag")
            .and_then(|v| v.to_str().ok())
            .map(|s| s.to_string());
        // 416: the cursor is already at end-of-blob — no new bytes.
        if status == reqwest::StatusCode::RANGE_NOT_SATISFIABLE {
            return Ok(Some(RangeRead {
                bytes: Vec::new(),
                total: None,
                etag,
            }));
        }
        if status == reqwest::StatusCode::OK || status == reqwest::StatusCode::PARTIAL_CONTENT {
            let total = resp
                .headers()
                .get("content-range")
                .and_then(|v| v.to_str().ok())
                .and_then(parse_total_size);
            let bytes = resp.bytes().await.context("read blob range body")?.to_vec();
            return Ok(Some(RangeRead { bytes, total, etag }));
        }
        bail!("blob range get {blob_path} -> HTTP {status}");
    })
    .await
}

/// Check whether a blob exists (a `HEAD` request). 404 -> `Ok(false)`.
pub async fn blob_head(
    client: &reqwest::Client,
    mi: &ManagedIdentityCredential,
    cfg: &AzureConfig,
    blob_path: &str,
) -> Result<bool> {
    let token = mi.token("https://storage.azure.com/").await?;
    let url = blob_url(cfg, blob_path);
    with_retry("blob head", 3, |_| async {
        let resp = client
            .head(&url)
            .bearer_auth(&token)
            .header("x-ms-version", SAS_VERSION)
            .send()
            .await
            .context("send blob head")?;
        Ok(resp.status().is_success())
    })
    .await
}

/// A single authenticated ARM (Azure Resource Manager) REST call. The caller
/// decides whether the returned status is acceptable.
pub async fn arm_request(
    client: &reqwest::Client,
    mi: &ManagedIdentityCredential,
    method: reqwest::Method,
    url: &str,
    body: Option<serde_json::Value>,
) -> Result<(reqwest::StatusCode, serde_json::Value)> {
    let token = mi.token("https://management.azure.com/").await?;
    let (status, text) = with_retry("arm request", 3, |_| async {
        let mut req = client.request(method.clone(), url).bearer_auth(&token);
        if let Some(b) = &body {
            req = req.json(b);
        }
        let resp = req.send().await.context("send ARM request")?;
        let status = resp.status();
        let text = resp.text().await.context("read ARM response body")?;
        Ok((status, text))
    })
    .await?;
    let json = if text.trim().is_empty() {
        serde_json::Value::Null
    } else {
        serde_json::from_str(&text).unwrap_or(serde_json::Value::Null)
    };
    Ok((status, json))
}

// ─── Tests ──────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicU32, Ordering};

    fn azure_test_cfg() -> AzureConfig {
        AzureConfig {
            subscription_id: "sub-1".to_string(),
            resource_group: "rg-1".to_string(),
            location: "eastus".to_string(),
            storage_account: "acct".to_string(),
            storage_container: "foundry-jobs".to_string(),
            // base64 of "testkey"
            storage_account_key: "dGVzdGtleQ==".to_string(),
            acr_name: "acr1".to_string(),
            aca_environment: "env-1".to_string(),
            managed_identity_client_id: String::new(),
            arm_endpoint: "https://management.azure.com".to_string(),
            blob_endpoint: "https://acct.blob.core.windows.net".to_string(),
            imds_endpoint: "http://imds".to_string(),
            signed_url_ttl_secs: 900,
            sas_grant_ttl_secs: 3600,
        }
    }

    #[test]
    fn test_percent_encode_encodes_reserved() {
        assert_eq!(percent_encode("a+b/c=d"), "a%2Bb%2Fc%3Dd");
        assert_eq!(percent_encode("plain-text_1.0~"), "plain-text_1.0~");
    }

    #[test]
    fn test_imds_token_url_system_assigned() {
        let url = imds_token_url("http://imds", "https://management.azure.com/", "");
        assert!(url.contains("api-version=2018-02-01"));
        assert!(url.contains("resource=https%3A%2F%2Fmanagement.azure.com%2F"));
        assert!(!url.contains("client_id"));
    }

    #[test]
    fn test_imds_token_url_user_assigned() {
        let url = imds_token_url("http://imds", "https://management.azure.com/", "abc-123");
        assert!(url.contains("client_id=abc-123"));
    }

    #[test]
    fn test_build_blob_sas_structure() {
        let cfg = azure_test_cfg();
        let start = UNIX_EPOCH + Duration::from_secs(1000);
        let expiry = UNIX_EPOCH + Duration::from_secs(4600);
        let sas = build_blob_sas(&SasParams {
            account: &cfg.storage_account,
            account_key: &cfg.storage_account_key,
            container: &cfg.storage_container,
            blob_path: "jobs/fj_x/input/SPEC.md",
            permissions: "r",
            start,
            expiry,
        })
        .expect("sas builds");
        assert!(sas.contains("sv=2022-11-02"), "sas: {sas}");
        assert!(sas.contains("sr=b"), "sas: {sas}");
        assert!(sas.contains("sp=r"), "sas: {sas}");
        assert!(sas.contains("spr=https"), "sas: {sas}");
        assert!(sas.contains(&format!("st={}", percent_encode(&iso8601(start)))));
        assert!(sas.contains(&format!("se={}", percent_encode(&iso8601(expiry)))));
        // a non-empty signature is present
        let sig = sas.split("sig=").nth(1).unwrap_or("");
        assert!(!sig.is_empty(), "sas: {sas}");
    }

    #[test]
    fn test_build_blob_sas_is_deterministic() {
        let cfg = azure_test_cfg();
        let mk = || {
            build_blob_sas(&SasParams {
                account: &cfg.storage_account,
                account_key: &cfg.storage_account_key,
                container: &cfg.storage_container,
                blob_path: "jobs/fj_x/logs/stream.jsonl",
                permissions: "acw",
                start: UNIX_EPOCH + Duration::from_secs(1000),
                expiry: UNIX_EPOCH + Duration::from_secs(4600),
            })
            .expect("sas builds")
        };
        assert_eq!(mk(), mk());
    }

    #[test]
    fn test_parse_total_size() {
        assert_eq!(parse_total_size("bytes 0-49/120"), Some(120));
        assert_eq!(parse_total_size("bytes */120"), Some(120));
        assert_eq!(parse_total_size("garbage"), None);
    }

    #[tokio::test]
    async fn test_with_retry_succeeds_after_transient_failures() {
        let counter = AtomicU32::new(0);
        let result = with_retry("t", 4, |_| async {
            let n = counter.fetch_add(1, Ordering::SeqCst) + 1;
            if n < 3 {
                bail!("transient {n}")
            } else {
                Ok(7)
            }
        })
        .await;
        assert_eq!(result.expect("eventually succeeds"), 7);

        let always_err = with_retry::<i32, _, _>("t", 2, |_| async { bail!("always") }).await;
        assert!(always_err.is_err());
    }
}
