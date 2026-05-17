//! `AzureBlob` — the M5 production [`StorageBackend`].
//!
//! Stores each job's inputs/logs/diagnostics/artifacts in Azure Blob storage
//! under a `jobs/<id>/` prefix, hands the build container a path-scoped, short-
//! TTL service-SAS grant, and serves `GET /artifact` / `GET /diagnostics` as
//! signed-URL redirects (minted fresh per request so they never go stale).
//!
//! This whole module compiles only under `--features azure`.

use std::time::{Duration, SystemTime};

use anyhow::{bail, Context, Result};
use async_trait::async_trait;
use serde_json::json;

use crate::service::azure::{self, AzureConfig, ManagedIdentityCredential, SasParams};
use crate::service::backend::{
    filter_log_lines, ArtifactKind, ArtifactResponse, StorageBackend, StorageGrant,
};

/// Azure-Blob-backed [`StorageBackend`].
pub struct AzureBlob {
    cfg: AzureConfig,
    client: reqwest::Client,
    mi: ManagedIdentityCredential,
}

/// The five well-known blobs that make up one job's state.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum JobBlob {
    SpecMd,
    TasksMd,
    StreamLog,
    Diagnostics,
    SourceArtifact,
}

/// The canonical relative blob path for one of a job's known blobs.
fn job_blob_path(job_id: &str, which: JobBlob) -> String {
    match which {
        JobBlob::SpecMd => format!("jobs/{job_id}/input/SPEC.md"),
        JobBlob::TasksMd => format!("jobs/{job_id}/input/TASKS.md"),
        JobBlob::StreamLog => format!("jobs/{job_id}/logs/stream.jsonl"),
        JobBlob::Diagnostics => format!("jobs/{job_id}/diagnostics/diagnostics.tar.gz"),
        JobBlob::SourceArtifact => format!("jobs/{job_id}/output/source.tar.gz"),
    }
}

/// The SAS permission string for each known blob — the testable seam for
/// "grant permissions". No entry contains `l` (list) or `d` (delete), and the
/// characters are in Azure's canonical order (`racwdxltmeop`): Add before
/// Create before Write.
fn job_blob_permissions(which: JobBlob) -> &'static str {
    match which {
        JobBlob::SpecMd | JobBlob::TasksMd => "r",
        // create + add + write: the append-blob lifecycle for stream.jsonl.
        JobBlob::StreamLog => "acw",
        JobBlob::Diagnostics | JobBlob::SourceArtifact => "cw",
    }
}

/// Build the path-scoped SAS grant JSON document handed to the build
/// container. Each of the five job blobs gets its own narrowly-scoped SAS URL.
pub fn build_job_grant(cfg: &AzureConfig, job_id: &str, now: SystemTime) -> Result<String> {
    let start = now - Duration::from_secs(300); // clock-skew tolerance
    let expiry = now + Duration::from_secs(cfg.sas_grant_ttl_secs);

    let url_for = |which: JobBlob| -> Result<String> {
        let blob_path = job_blob_path(job_id, which);
        let sas = azure::build_blob_sas(&SasParams {
            account: &cfg.storage_account,
            account_key: &cfg.storage_account_key,
            container: &cfg.storage_container,
            blob_path: &blob_path,
            permissions: job_blob_permissions(which),
            start,
            expiry,
        })?;
        Ok(format!(
            "{}/{}/{}?{}",
            cfg.blob_endpoint, cfg.storage_container, blob_path, sas
        ))
    };

    let doc = json!({
        "spec_md": url_for(JobBlob::SpecMd)?,
        "tasks_md": url_for(JobBlob::TasksMd)?,
        "stream_log": url_for(JobBlob::StreamLog)?,
        "diagnostics": url_for(JobBlob::Diagnostics)?,
        "source_artifact": url_for(JobBlob::SourceArtifact)?,
    });
    serde_json::to_string(&doc).context("serialize storage grant")
}

/// Build a short-TTL, read-only signed URL for `GET /artifact` /
/// `GET /diagnostics`.
pub fn artifact_signed_url(
    cfg: &AzureConfig,
    job_id: &str,
    kind: ArtifactKind,
    now: SystemTime,
) -> Result<String> {
    let which = match kind {
        ArtifactKind::Artifact => JobBlob::SourceArtifact,
        ArtifactKind::Diagnostics => JobBlob::Diagnostics,
    };
    let blob_path = job_blob_path(job_id, which);
    let start = now - Duration::from_secs(300);
    let expiry = now + Duration::from_secs(cfg.signed_url_ttl_secs);
    let sas = azure::build_blob_sas(&SasParams {
        account: &cfg.storage_account,
        account_key: &cfg.storage_account_key,
        container: &cfg.storage_container,
        blob_path: &blob_path,
        permissions: "r",
        start,
        expiry,
    })?;
    Ok(format!(
        "{}/{}/{}?{}",
        cfg.blob_endpoint, cfg.storage_container, blob_path, sas
    ))
}

impl AzureBlob {
    pub fn new(cfg: AzureConfig) -> AzureBlob {
        let client = azure::http_client();
        let mi = ManagedIdentityCredential::new(client.clone(), &cfg);
        AzureBlob { cfg, client, mi }
    }
}

#[async_trait]
impl StorageBackend for AzureBlob {
    async fn put_input(&self, job_id: &str, spec_md: &str, tasks_md: &str) -> Result<()> {
        azure::blob_put_block(
            &self.client,
            &self.mi,
            &self.cfg,
            &job_blob_path(job_id, JobBlob::SpecMd),
            spec_md.as_bytes().to_vec(),
            "text/markdown",
        )
        .await?;
        azure::blob_put_block(
            &self.client,
            &self.mi,
            &self.cfg,
            &job_blob_path(job_id, JobBlob::TasksMd),
            tasks_md.as_bytes().to_vec(),
            "text/markdown",
        )
        .await?;
        Ok(())
    }

    async fn issue_grant(&self, job_id: &str) -> Result<StorageGrant> {
        let sas = build_job_grant(&self.cfg, job_id, SystemTime::now())?;
        Ok(StorageGrant {
            kind: "azure_blob".to_string(),
            mount_path: None,
            sas: Some(sas),
        })
    }

    async fn revoke_grant(&self, _grant: &StorageGrant) -> Result<()> {
        // An account-key service SAS cannot be individually revoked; the short
        // `sas_grant_ttl_secs` TTL is the bound. Nothing to do here.
        Ok(())
    }

    async fn put_logs(&self, job_id: &str, jsonl: &str) -> Result<()> {
        azure::blob_put_block(
            &self.client,
            &self.mi,
            &self.cfg,
            &job_blob_path(job_id, JobBlob::StreamLog),
            jsonl.as_bytes().to_vec(),
            "application/x-ndjson",
        )
        .await
    }

    async fn read_logs(
        &self,
        job_id: &str,
        stage: Option<&str>,
        tail: Option<usize>,
    ) -> Result<String> {
        let bytes = match azure::blob_get(
            &self.client,
            &self.mi,
            &self.cfg,
            &job_blob_path(job_id, JobBlob::StreamLog),
        )
        .await?
        {
            Some(b) => b,
            None => return Ok(String::new()),
        };
        let content = String::from_utf8_lossy(&bytes).into_owned();
        Ok(filter_log_lines(&content, stage, tail))
    }

    async fn put_artifact(&self, job_id: &str, bytes: &[u8]) -> Result<String> {
        azure::blob_put_block(
            &self.client,
            &self.mi,
            &self.cfg,
            &job_blob_path(job_id, JobBlob::SourceArtifact),
            bytes.to_vec(),
            "application/gzip",
        )
        .await?;
        // The API route, not a signed URL — `fetch` mints the signed URL fresh
        // per request so it never goes stale in the `jobs` table.
        Ok(format!("/v1/jobs/{job_id}/artifact"))
    }

    async fn put_diagnostics(&self, job_id: &str, bytes: &[u8]) -> Result<()> {
        azure::blob_put_block(
            &self.client,
            &self.mi,
            &self.cfg,
            &job_blob_path(job_id, JobBlob::Diagnostics),
            bytes.to_vec(),
            "application/gzip",
        )
        .await
    }

    async fn fetch(&self, job_id: &str, kind: ArtifactKind) -> Result<ArtifactResponse> {
        let which = match kind {
            ArtifactKind::Artifact => JobBlob::SourceArtifact,
            ArtifactKind::Diagnostics => JobBlob::Diagnostics,
        };
        if !azure::blob_head(
            &self.client,
            &self.mi,
            &self.cfg,
            &job_blob_path(job_id, which),
        )
        .await?
        {
            bail!("artifact not found for job {job_id}");
        }
        let url = artifact_signed_url(&self.cfg, job_id, kind, SystemTime::now())?;
        Ok(ArtifactResponse::Redirect { url })
    }

    async fn revoke_job(&self, _job_id: &str) -> Result<()> {
        // Blobs under `jobs/<id>/` are intentionally retained on cancel/expire
        // so the source artifact stays downloadable after teardown; the SAS
        // grant self-expires via its short TTL.
        Ok(())
    }
}

// ─── Tests ──────────────────────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn azure_test_cfg() -> AzureConfig {
        AzureConfig {
            subscription_id: "sub-1".to_string(),
            resource_group: "rg-1".to_string(),
            location: "eastus".to_string(),
            storage_account: "acct".to_string(),
            storage_container: "foundry-jobs".to_string(),
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

    const ALL_BLOBS: [JobBlob; 5] = [
        JobBlob::SpecMd,
        JobBlob::TasksMd,
        JobBlob::StreamLog,
        JobBlob::Diagnostics,
        JobBlob::SourceArtifact,
    ];

    /// Pull the value of a query param like `sp` out of a SAS URL.
    fn query_param<'a>(url: &'a str, key: &str) -> Option<&'a str> {
        let query = url.split('?').nth(1)?;
        query
            .split('&')
            .find_map(|kv| kv.strip_prefix(&format!("{key}=")))
    }

    #[test]
    fn test_job_blob_paths_are_under_job_prefix() {
        for which in ALL_BLOBS {
            let path = job_blob_path("fj_x", which);
            assert!(
                path.starts_with("jobs/fj_x/"),
                "{which:?} path not under job prefix: {path}"
            );
        }
    }

    #[test]
    fn test_grant_permissions_have_no_list_or_delete() {
        for which in ALL_BLOBS {
            let perms = job_blob_permissions(which);
            assert!(!perms.contains('l'), "{which:?} grants list");
            assert!(!perms.contains('d'), "{which:?} grants delete");
        }
        assert_eq!(job_blob_permissions(JobBlob::SpecMd), "r");
        assert_eq!(job_blob_permissions(JobBlob::TasksMd), "r");
        let stream = job_blob_permissions(JobBlob::StreamLog);
        assert!(stream.contains('a') && stream.contains('c') && stream.contains('w'));
        // Add must precede Create must precede Write (canonical SAS order).
        assert_eq!(stream, "acw");
        for which in [JobBlob::Diagnostics, JobBlob::SourceArtifact] {
            let perms = job_blob_permissions(which);
            assert!(perms.contains('c') && perms.contains('w'));
        }
    }

    #[test]
    fn test_build_job_grant_scopes_each_sas() {
        let cfg = azure_test_cfg();
        let now = SystemTime::now();
        let grant = build_job_grant(&cfg, "fj_x", now).expect("grant builds");
        let doc: serde_json::Value = serde_json::from_str(&grant).expect("grant is JSON");
        let keys = [
            ("spec_md", JobBlob::SpecMd),
            ("tasks_md", JobBlob::TasksMd),
            ("stream_log", JobBlob::StreamLog),
            ("diagnostics", JobBlob::Diagnostics),
            ("source_artifact", JobBlob::SourceArtifact),
        ];
        for (key, which) in keys {
            let url = doc.get(key).and_then(|v| v.as_str()).expect(key);
            assert!(
                url.contains("/foundry-jobs/jobs/fj_x/"),
                "{key} not scoped to job: {url}"
            );
            let sp = query_param(url, "sp").expect("sp param");
            assert_eq!(sp, job_blob_permissions(which), "{key} sp mismatch");
            assert!(!sp.contains('l') && !sp.contains('d'), "{key} sp too broad");
        }
    }

    #[test]
    fn test_artifact_signed_url_expiry_is_short_ttl() {
        let cfg = azure_test_cfg();
        let now = SystemTime::now();
        let url = artifact_signed_url(&cfg, "fj_x", ArtifactKind::Artifact, now)
            .expect("signed url builds");
        let expected_se = azure::percent_encode(&azure::iso8601(
            now + Duration::from_secs(cfg.signed_url_ttl_secs),
        ));
        assert_eq!(query_param(&url, "se"), Some(expected_se.as_str()));
        assert_eq!(query_param(&url, "sp"), Some("r"));
        let path = url.split('?').next().unwrap_or("");
        assert!(path.ends_with("output/source.tar.gz"), "path: {path}");
    }

    #[test]
    fn test_artifact_signed_url_diagnostics_targets_diagnostics_blob() {
        let cfg = azure_test_cfg();
        let url =
            artifact_signed_url(&cfg, "fj_x", ArtifactKind::Diagnostics, SystemTime::now())
                .expect("signed url builds");
        let path = url.split('?').next().unwrap_or("");
        assert!(
            path.ends_with("diagnostics/diagnostics.tar.gz"),
            "path: {path}"
        );
    }
}
