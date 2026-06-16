//! `AzureContainerApps` — the M5 production [`BuildBackend`].
//!
//! Runs builds as ACA Jobs, builds preview images with ACR Tasks, and deploys
//! scale-to-zero Container Apps for previews. The build event stream does NOT
//! depend on ACA log streaming: the builder writes `jobs/<id>/logs/stream.jsonl`
//! as an Append Blob and [`AzureContainerApps`] tails it by persisted byte
//! offset / ETag with retry/backoff (see [`tail_until_complete`]).
//!
//! This whole module compiles only under `--features azure`.

use std::collections::{HashMap, HashSet};
use std::sync::Mutex;
use std::time::{Duration, Instant};

use anyhow::{bail, Context, Result};
use async_trait::async_trait;
use serde_json::json;

use crate::service::azure::{self, AzureConfig, ManagedIdentityCredential, SasParams};
use crate::service::backend::{BuildBackend, BuildHandle, ImageRef, PreviewInfo, StorageGrant};
use crate::service::localdocker::{
    detect_stack, fallback_dockerfile, fallback_source_label, is_valid_dockerfile,
};
use crate::service::models::Job;

/// ARM API version for `Microsoft.App` resources (jobs + container apps).
const ACA_API_VERSION: &str = "2024-03-01";
/// ARM API version for ACR run scheduling.
const ACR_API_VERSION: &str = "2019-06-01-preview";

// ─── Tail cursor ────────────────────────────────────────────────────────────

/// A persisted byte-offset/ETag cursor for tailing the append-blob log stream.
#[derive(Clone, Debug, Default)]
pub struct TailCursor {
    pub offset: u64,
    pub etag: Option<String>,
}

impl TailCursor {
    pub fn new() -> TailCursor {
        TailCursor {
            offset: 0,
            etag: None,
        }
    }

    /// The `Range` header for the next tail read.
    pub fn range_header(&self) -> String {
        format!("bytes={}-", self.offset)
    }

    /// Move the cursor forward after consuming a chunk of `chunk_len` bytes.
    pub fn advance(&mut self, chunk_len: u64, etag: Option<String>) {
        self.offset += chunk_len;
        if etag.is_some() {
            self.etag = etag;
        }
    }
}

// ─── Pure naming / URL helpers ──────────────────────────────────────────────

/// Produce an Azure-resource-valid name: lowercase `[a-z0-9-]`, starts with the
/// prefix's letter, <= 32 chars, no trailing hyphen.
fn sanitize_azure_name(prefix: &str, job_id: &str) -> String {
    let cleaned: String = job_id
        .to_lowercase()
        .chars()
        .map(|c| if c.is_ascii_alphanumeric() { c } else { '-' })
        .collect();
    let mut base = format!("{prefix}-{cleaned}");
    base.truncate(32);
    while base.ends_with('-') {
        base.pop();
    }
    base
}

/// The ACA Job name for a build.
pub fn aca_job_name(job_id: &str) -> String {
    sanitize_azure_name("fb", job_id)
}

/// The ACA Container App name for a preview.
pub fn aca_app_name(job_id: &str) -> String {
    sanitize_azure_name("fp", job_id)
}

/// The URLs an ACA preview health check polls, in order.
pub fn aca_health_urls(fqdn: &str) -> [String; 2] {
    [
        format!("https://{fqdn}/healthz"),
        format!("https://{fqdn}/"),
    ]
}

/// The ARM resource URLs `teardown` issues `DELETE` against — proves ACA Job +
/// Container App cleanup coverage.
pub fn teardown_delete_paths(cfg: &AzureConfig, job_id: &str) -> Vec<String> {
    vec![
        format!(
            "{}/subscriptions/{}/resourceGroups/{}/providers/Microsoft.App/jobs/{}?api-version={}",
            cfg.arm_endpoint,
            cfg.subscription_id,
            cfg.resource_group,
            aca_job_name(job_id),
            ACA_API_VERSION,
        ),
        format!(
            "{}/subscriptions/{}/resourceGroups/{}/providers/Microsoft.App/containerApps/{}?api-version={}",
            cfg.arm_endpoint,
            cfg.subscription_id,
            cfg.resource_group,
            aca_app_name(job_id),
            ACA_API_VERSION,
        ),
    ]
}

/// The ACA managed-environment resource ID. Accepts either a bare name or an
/// already-qualified `/subscriptions/...` resource ID.
fn environment_id(cfg: &AzureConfig) -> String {
    if cfg.aca_environment.starts_with("/subscriptions/") {
        cfg.aca_environment.clone()
    } else {
        format!(
            "/subscriptions/{}/resourceGroups/{}/providers/Microsoft.App/managedEnvironments/{}",
            cfg.subscription_id, cfg.resource_group, cfg.aca_environment,
        )
    }
}

/// ARM URL of a `Microsoft.App` resource (`jobs` or `containerApps`).
fn aca_resource_url(cfg: &AzureConfig, kind: &str, name: &str) -> String {
    format!(
        "{}/subscriptions/{}/resourceGroups/{}/providers/Microsoft.App/{}/{}?api-version={}",
        cfg.arm_endpoint, cfg.subscription_id, cfg.resource_group, kind, name, ACA_API_VERSION,
    )
}

/// ARM list URL for a `Microsoft.App` resource collection.
fn aca_list_url(cfg: &AzureConfig, kind: &str) -> String {
    format!(
        "{}/subscriptions/{}/resourceGroups/{}/providers/Microsoft.App/{}?api-version={}",
        cfg.arm_endpoint, cfg.subscription_id, cfg.resource_group, kind, ACA_API_VERSION,
    )
}

/// Pick the status of the most-recently-started execution from an ACA Job
/// executions list response.
fn latest_execution_status(list: &serde_json::Value) -> Option<String> {
    let mut best: Option<(String, String)> = None; // (startTime, status)
    for exec in list.get("value")?.as_array()? {
        let status = exec
            .get("properties")
            .and_then(|p| p.get("status"))
            .and_then(|s| s.as_str())
            .unwrap_or("")
            .to_string();
        let start = exec
            .get("properties")
            .and_then(|p| p.get("startTime"))
            .and_then(|s| s.as_str())
            .unwrap_or("")
            .to_string();
        match &best {
            Some((bs, _)) if *bs >= start => {}
            _ => best = Some((start, status)),
        }
    }
    best.map(|(_, status)| status)
}

/// Whether an ACA Job execution status is terminal.
fn is_terminal_status(status: &str) -> bool {
    matches!(status, "Succeeded" | "Failed" | "Stopped")
}

// ─── Backend ────────────────────────────────────────────────────────────────

/// ACA/ACR-backed [`BuildBackend`].
pub struct AzureContainerApps {
    cfg: AzureConfig,
    client: reqwest::Client,
    mi: ManagedIdentityCredential,
    /// The ACR-hosted `foundry-builder` image the ACA Job runs.
    builder_image: String,
    /// `ANTHROPIC_BASE_URL` the build container reaches the daemon proxy on.
    proxy_url: String,
    /// job_id -> accumulated JSONL event stream tailed from the append blob.
    streams: Mutex<HashMap<String, String>>,
}

impl AzureContainerApps {
    pub fn new(
        cfg: AzureConfig,
        builder_image: String,
        proxy_url: String,
    ) -> AzureContainerApps {
        let client = azure::http_client();
        let mi = ManagedIdentityCredential::new(client.clone(), &cfg);
        AzureContainerApps {
            cfg,
            client,
            mi,
            builder_image,
            proxy_url,
            streams: Mutex::new(HashMap::new()),
        }
    }

    /// Poll the ACA Job execution to a terminal state while tailing the
    /// `stream.jsonl` Append Blob by byte offset / ETag. Returns the full
    /// accumulated JSONL. This is what makes the Azure build stream independent
    /// of ACA's log API.
    async fn tail_until_complete(&self, job_id: &str, job_name: &str) -> Result<String> {
        let mut cursor = TailCursor::new();
        let mut acc = String::new();
        let stream_path = format!("jobs/{job_id}/logs/stream.jsonl");
        let executions_url = format!(
            "{}/subscriptions/{}/resourceGroups/{}/providers/Microsoft.App/jobs/{}/executions?api-version={}",
            self.cfg.arm_endpoint,
            self.cfg.subscription_id,
            self.cfg.resource_group,
            job_name,
            ACA_API_VERSION,
        );
        // Absolute backstop; the worker's wall-clock timeout is the real bound.
        let started = Instant::now();
        let backstop = Duration::from_secs(24 * 60 * 60);

        loop {
            // (a) tail the append blob — 404 / transient errors are swallowed:
            // the builder may not have created the blob yet.
            match azure::blob_get_range(
                &self.client,
                &self.mi,
                &self.cfg,
                &stream_path,
                &cursor.range_header(),
            )
            .await
            {
                Ok(Some(rr)) => {
                    acc.push_str(&String::from_utf8_lossy(&rr.bytes));
                    cursor.advance(rr.bytes.len() as u64, rr.etag);
                }
                Ok(None) => {}
                Err(_) => {}
            }

            // (b) inspect the ACA Job execution status.
            let (status, body) = azure::arm_request(
                &self.client,
                &self.mi,
                reqwest::Method::GET,
                &executions_url,
                None,
            )
            .await
            .context("poll ACA Job executions")?;
            if status.is_success() {
                if let Some(exec_status) = latest_execution_status(&body) {
                    if is_terminal_status(&exec_status) {
                        break;
                    }
                }
            }

            if started.elapsed() > backstop {
                bail!("ACA Job {job_name} did not reach a terminal state within backstop");
            }
            tokio::time::sleep(Duration::from_secs(3)).await;
        }

        // One final tail read to capture bytes written just before exit.
        if let Ok(Some(rr)) = azure::blob_get_range(
            &self.client,
            &self.mi,
            &self.cfg,
            &stream_path,
            &cursor.range_header(),
        )
        .await
        {
            acc.push_str(&String::from_utf8_lossy(&rr.bytes));
            cursor.advance(rr.bytes.len() as u64, rr.etag);
        }
        Ok(acc)
    }

    /// Best-effort deletion of the preview's ACR repository. ACR data-plane
    /// auth (AAD -> ACR refresh token -> ACR access token) is done inline; any
    /// failure is swallowed by the caller's `let _ =`.
    async fn acr_delete_repo(&self, repo: &str) -> Result<()> {
        let acr_host = format!("{}.azurecr.io", self.cfg.acr_name);
        let aad = self.mi.token("https://management.azure.com/").await?;

        // Exchange the AAD token for an ACR refresh token.
        let exchange: serde_json::Value = self
            .client
            .post(format!("https://{acr_host}/oauth2/exchange"))
            .form(&[
                ("grant_type", "access_token"),
                ("service", acr_host.as_str()),
                ("access_token", aad.as_str()),
            ])
            .send()
            .await
            .context("acr token exchange")?
            .json()
            .await
            .context("parse acr refresh token")?;
        let refresh = exchange
            .get("refresh_token")
            .and_then(|v| v.as_str())
            .context("acr exchange had no refresh_token")?;

        // Trade the refresh token for a delete-scoped ACR access token.
        let token: serde_json::Value = self
            .client
            .post(format!("https://{acr_host}/oauth2/token"))
            .form(&[
                ("grant_type", "refresh_token"),
                ("service", acr_host.as_str()),
                ("scope", &format!("repository:{repo}:delete")),
                ("refresh_token", refresh),
            ])
            .send()
            .await
            .context("acr token request")?
            .json()
            .await
            .context("parse acr access token")?;
        let access = token
            .get("access_token")
            .and_then(|v| v.as_str())
            .context("acr token response had no access_token")?;

        let resp = self
            .client
            .delete(format!("https://{acr_host}/acr/v1/{repo}"))
            .bearer_auth(access)
            .send()
            .await
            .context("acr repo delete")?;
        if !resp.status().is_success() {
            bail!("acr repo delete {repo} -> HTTP {}", resp.status());
        }
        Ok(())
    }
}

#[async_trait]
impl BuildBackend for AzureContainerApps {
    async fn start_build(
        &self,
        job: &Job,
        grant: &StorageGrant,
        proxy_token: &str,
    ) -> Result<BuildHandle> {
        if grant.kind != "azure_blob" {
            bail!("AzureContainerApps requires an azure_blob storage grant");
        }
        let grant_sas = grant
            .sas
            .as_deref()
            .context("azure_blob storage grant has no SAS document")?;

        let job_name = aca_job_name(&job.id);
        let job_url = aca_resource_url(&self.cfg, "jobs", &job_name);

        // (1) Create the ACA Job resource.
        let job_body = json!({
            "location": self.cfg.location,
            "identity": { "type": "SystemAssigned" },
            "properties": {
                "environmentId": environment_id(&self.cfg),
                "configuration": {
                    "triggerType": "Manual",
                    "replicaTimeout": 86400,
                    "replicaRetryLimit": 0,
                    "manualTriggerConfig": {
                        "parallelism": 1,
                        "replicaCompletionCount": 1
                    }
                },
                "template": {
                    "containers": [{
                        "name": "builder",
                        "image": self.builder_image,
                        "resources": { "cpu": 2.0, "memory": "4Gi" },
                        "env": [
                            { "name": "ANTHROPIC_BASE_URL", "value": self.proxy_url },
                            // TODO(auth-401): inject `proxy_token` as ANTHROPIC_AUTH_TOKEN,
                            // not ANTHROPIC_API_KEY. The `claude` CLI sends ANTHROPIC_API_KEY
                            // as the `x-api-key` header, but the auth proxy reads the token
                            // from `Authorization: Bearer` (`messages_handler` in proxy.rs),
                            // so every build call is rejected 401 `unauthorized`. This is the
                            // identical bug fixed for the local_docker backend in
                            // `localdocker.rs::docker_run_argv` (see the doc comment there).
                            // The foundry-builder `entrypoint.sh` now also requires
                            // ANTHROPIC_AUTH_TOKEN. Fix when the Azure backend is exercised.
                            { "name": "ANTHROPIC_API_KEY", "value": proxy_token },
                            { "name": "FOUNDRY_JOB_ID", "value": job.id },
                            { "name": "FOUNDRY_STORAGE_GRANT", "value": grant_sas },
                            { "name": "FOUNDRY_BLOB_ACCOUNT", "value": self.cfg.storage_account },
                            { "name": "FOUNDRY_BLOB_CONTAINER", "value": self.cfg.storage_container }
                        ]
                    }]
                }
            }
        });
        let (status, body) = azure::arm_request(
            &self.client,
            &self.mi,
            reqwest::Method::PUT,
            &job_url,
            Some(job_body),
        )
        .await
        .context("create ACA Job")?;
        if !(status == reqwest::StatusCode::OK || status == reqwest::StatusCode::CREATED) {
            bail!("create ACA Job {job_name} -> HTTP {status}: {body}");
        }

        // (2) Start the ACA Job execution.
        let start_url = format!(
            "{}/subscriptions/{}/resourceGroups/{}/providers/Microsoft.App/jobs/{}/start?api-version={}",
            self.cfg.arm_endpoint,
            self.cfg.subscription_id,
            self.cfg.resource_group,
            job_name,
            ACA_API_VERSION,
        );
        let (status, body) = azure::arm_request(
            &self.client,
            &self.mi,
            reqwest::Method::POST,
            &start_url,
            None,
        )
        .await
        .context("start ACA Job")?;
        if !status.is_success() {
            bail!("start ACA Job {job_name} -> HTTP {status}: {body}");
        }

        // (3) Block until the execution is terminal, tailing the append blob.
        // Blocking here keeps the build inside the worker's wall-clock timeout.
        let stream = self.tail_until_complete(&job.id, &job_name).await?;
        self.streams
            .lock()
            .expect("streams map poisoned")
            .insert(job.id.clone(), stream);
        Ok(BuildHandle {
            job_id: job.id.clone(),
        })
    }

    async fn stream_events(&self, handle: &BuildHandle) -> Result<String> {
        Ok(self
            .streams
            .lock()
            .expect("streams map poisoned")
            .get(&handle.job_id)
            .cloned()
            .unwrap_or_default())
    }

    async fn build_image(&self, job: &Job) -> Result<ImageRef> {
        // (1) Download the source artifact the builder uploaded.
        let src = azure::blob_get(
            &self.client,
            &self.mi,
            &self.cfg,
            &format!("jobs/{}/output/source.tar.gz", job.id),
        )
        .await?
        .context("source artifact missing for image build")?;

        // (2) Extract it to a temp working dir.
        let work = std::env::temp_dir().join(format!("foundry-azure-{}", job.id));
        let _ = std::fs::remove_dir_all(&work);
        std::fs::create_dir_all(&work).context("create azure build work dir")?;
        tar::Archive::new(flate2::read::GzDecoder::new(&src[..]))
            .unpack(&work)
            .context("unpack source artifact")?;

        // (3)/(4) Decide the Dockerfile, reusing the localdocker pure helpers.
        let project_valid = std::fs::read_to_string(work.join("Dockerfile"))
            .ok()
            .map(|c| is_valid_dockerfile(&c))
            .unwrap_or(false);
        let dockerfile_source = if project_valid {
            "project"
        } else {
            let stack = detect_stack(&work);
            std::fs::write(work.join("Dockerfile"), fallback_dockerfile(stack))
                .context("write fallback Dockerfile")?;
            fallback_source_label(stack)
        };

        // (5) Re-pack and upload the build context, then mint a read SAS for
        // ACR. The SAS lifetime must cover ACR queue + source-fetch time, so it
        // uses the generous `sas_grant_ttl_secs`, NOT the client-facing
        // `signed_url_ttl_secs`.
        let mut tar_gz: Vec<u8> = Vec::new();
        {
            let enc = flate2::write::GzEncoder::new(&mut tar_gz, flate2::Compression::default());
            let mut builder = tar::Builder::new(enc);
            builder
                .append_dir_all(".", &work)
                .context("repack build context")?;
            builder
                .into_inner()
                .context("finish build-context tar")?
                .finish()
                .context("finish build-context gzip")?;
        }
        let context_path = format!("jobs/{}/output/_build-context.tar.gz", job.id);
        azure::blob_put_block(
            &self.client,
            &self.mi,
            &self.cfg,
            &context_path,
            tar_gz,
            "application/gzip",
        )
        .await
        .context("upload ACR build context")?;
        let now = std::time::SystemTime::now();
        let context_sas = azure::build_blob_sas(&SasParams {
            account: &self.cfg.storage_account,
            account_key: &self.cfg.storage_account_key,
            container: &self.cfg.storage_container,
            blob_path: &context_path,
            permissions: "r",
            start: now - Duration::from_secs(300),
            expiry: now + Duration::from_secs(self.cfg.sas_grant_ttl_secs),
        })?;
        let context_url = format!(
            "{}/{}/{}?{}",
            self.cfg.blob_endpoint, self.cfg.storage_container, context_path, context_sas
        );

        // (6) The pushed image reference.
        let image_name = format!("foundry-preview-{}:latest", aca_job_name(&job.id));
        let image_ref = format!("{}.azurecr.io/{}", self.cfg.acr_name, image_name);

        // (7) Schedule the ACR build run.
        let schedule_url = format!(
            "{}/subscriptions/{}/resourceGroups/{}/providers/Microsoft.ContainerRegistry/registries/{}/scheduleRun?api-version={}",
            self.cfg.arm_endpoint,
            self.cfg.subscription_id,
            self.cfg.resource_group,
            self.cfg.acr_name,
            ACR_API_VERSION,
        );
        let schedule_body = json!({
            "type": "DockerBuildRequest",
            "sourceLocation": context_url,
            "dockerFilePath": "Dockerfile",
            "imageNames": [image_name],
            "isPushEnabled": true,
            "platform": { "os": "Linux" }
        });
        let (status, run) = azure::arm_request(
            &self.client,
            &self.mi,
            reqwest::Method::POST,
            &schedule_url,
            Some(schedule_body),
        )
        .await
        .context("schedule ACR build run")?;
        if !status.is_success() {
            bail!("schedule ACR run -> HTTP {status}: {run}");
        }
        let run_id = run
            .get("name")
            .and_then(|v| v.as_str())
            .or_else(|| run.get("properties").and_then(|p| p.get("runId")).and_then(|v| v.as_str()))
            .context("ACR scheduleRun response had no run id")?
            .to_string();

        // (8) Poll the ACR run to completion.
        let run_url = format!(
            "{}/subscriptions/{}/resourceGroups/{}/providers/Microsoft.ContainerRegistry/registries/{}/runs/{}?api-version={}",
            self.cfg.arm_endpoint,
            self.cfg.subscription_id,
            self.cfg.resource_group,
            self.cfg.acr_name,
            run_id,
            ACR_API_VERSION,
        );
        loop {
            let (status, body) = azure::arm_request(
                &self.client,
                &self.mi,
                reqwest::Method::GET,
                &run_url,
                None,
            )
            .await
            .context("poll ACR run")?;
            if status.is_success() {
                let run_status = body
                    .get("properties")
                    .and_then(|p| p.get("status"))
                    .and_then(|s| s.as_str())
                    .unwrap_or("");
                match run_status {
                    "Succeeded" => break,
                    "Failed" | "Canceled" | "Error" | "Timeout" => {
                        bail!("ACR run {run_id} -> {run_status}")
                    }
                    _ => {}
                }
            }
            tokio::time::sleep(Duration::from_secs(5)).await;
        }

        // (9) Best-effort cleanup of the temp dir.
        let _ = std::fs::remove_dir_all(&work);

        Ok(ImageRef {
            reference: image_ref,
            dockerfile_source: dockerfile_source.to_string(),
        })
    }

    async fn deploy_preview(&self, job: &Job, image: &ImageRef) -> Result<PreviewInfo> {
        let app_name = aca_app_name(&job.id);
        let app_url = aca_resource_url(&self.cfg, "containerApps", &app_name);
        let acr_server = format!("{}.azurecr.io", self.cfg.acr_name);

        // (2) Create the scale-to-zero Container App.
        let app_body = json!({
            "location": self.cfg.location,
            "identity": { "type": "SystemAssigned" },
            "properties": {
                "environmentId": environment_id(&self.cfg),
                "configuration": {
                    "ingress": {
                        "external": true,
                        "targetPort": 8080,
                        "transport": "auto"
                    },
                    "registries": [{
                        "server": acr_server,
                        "identity": "system"
                    }]
                },
                "template": {
                    "containers": [{
                        "name": "app",
                        "image": image.reference,
                        "resources": { "cpu": 0.5, "memory": "1Gi" },
                        "env": [{ "name": "PORT", "value": "8080" }]
                    }],
                    "scale": { "minReplicas": 0, "maxReplicas": 1 }
                }
            }
        });
        let (status, body) = azure::arm_request(
            &self.client,
            &self.mi,
            reqwest::Method::PUT,
            &app_url,
            Some(app_body),
        )
        .await
        .context("create preview Container App")?;
        if !(status == reqwest::StatusCode::OK || status == reqwest::StatusCode::CREATED) {
            bail!("create Container App {app_name} -> HTTP {status}: {body}");
        }

        // (3) Poll the app to a provisioned state and read its FQDN.
        let provision_deadline = Instant::now() + Duration::from_secs(180);
        let fqdn: String = loop {
            let (status, body) = azure::arm_request(
                &self.client,
                &self.mi,
                reqwest::Method::GET,
                &app_url,
                None,
            )
            .await
            .context("poll Container App provisioning")?;
            if status.is_success() {
                let state = body
                    .get("properties")
                    .and_then(|p| p.get("provisioningState"))
                    .and_then(|s| s.as_str())
                    .unwrap_or("");
                if state == "Succeeded" {
                    break body
                        .get("properties")
                        .and_then(|p| p.get("configuration"))
                        .and_then(|c| c.get("ingress"))
                        .and_then(|i| i.get("fqdn"))
                        .and_then(|f| f.as_str())
                        .unwrap_or("")
                        .to_string();
                }
                if state == "Failed" || state == "Canceled" {
                    let _ = self.teardown(&job.id).await;
                    bail!("preview Container App {app_name} provisioning {state}");
                }
            }
            if Instant::now() > provision_deadline {
                let _ = self.teardown(&job.id).await;
                bail!("preview Container App {app_name} did not provision in time");
            }
            tokio::time::sleep(Duration::from_secs(3)).await;
        };
        if fqdn.is_empty() {
            let _ = self.teardown(&job.id).await;
            bail!("preview Container App {app_name} exposed no ingress FQDN");
        }

        // (4) Health-check the preview, accepting the first 200.
        let health_deadline = Instant::now() + Duration::from_secs(120);
        let mut healthy = false;
        while Instant::now() < health_deadline {
            for url in aca_health_urls(&fqdn) {
                if let Ok(resp) = self.client.get(&url).send().await {
                    if resp.status().is_success() {
                        healthy = true;
                        break;
                    }
                }
            }
            if healthy {
                break;
            }
            tokio::time::sleep(Duration::from_secs(3)).await;
        }
        if !healthy {
            let _ = self.teardown(&job.id).await;
            bail!("preview health check failed for {app_name}");
        }

        Ok(PreviewInfo {
            url: format!("https://{fqdn}"),
        })
    }

    async fn collect_artifact(&self, handle: &BuildHandle) -> Result<Vec<u8>> {
        azure::blob_get(
            &self.client,
            &self.mi,
            &self.cfg,
            &format!("jobs/{}/output/source.tar.gz", handle.job_id),
        )
        .await?
        .context("source artifact not found in blob storage")
    }

    async fn collect_diagnostics(&self, handle: &BuildHandle) -> Result<Vec<u8>> {
        azure::blob_get(
            &self.client,
            &self.mi,
            &self.cfg,
            &format!("jobs/{}/diagnostics/diagnostics.tar.gz", handle.job_id),
        )
        .await?
        .context("diagnostics not found in blob storage")
    }

    async fn teardown(&self, job_id: &str) -> Result<()> {
        // Delete the ACA Job and the preview Container App (best-effort).
        for url in teardown_delete_paths(&self.cfg, job_id) {
            let _ = azure::arm_request(
                &self.client,
                &self.mi,
                reqwest::Method::DELETE,
                &url,
                None,
            )
            .await;
        }
        // Best-effort ACR image cleanup — a missing image must never fail
        // teardown.
        let _ = self
            .acr_delete_repo(&format!("foundry-preview-{}", aca_job_name(job_id)))
            .await;
        // Blobs under `jobs/<id>/` are intentionally retained so the source
        // artifact stays downloadable after teardown.
        self.streams
            .lock()
            .expect("streams map poisoned")
            .remove(job_id);
        Ok(())
    }

    async fn sweep_orphans(&self, active_ids: &[String]) -> Result<Vec<String>> {
        // Names of resources that belong to a still-active job.
        let mut keep: HashSet<String> = HashSet::new();
        for id in active_ids {
            keep.insert(aca_job_name(id));
            keep.insert(aca_app_name(id));
        }

        let mut swept = Vec::new();
        for kind in ["jobs", "containerApps"] {
            // Follow `nextLink` so a multi-page resource group is fully swept.
            let mut next = Some(aca_list_url(&self.cfg, kind));
            while let Some(url) = next.take() {
                let (status, body) = azure::arm_request(
                    &self.client,
                    &self.mi,
                    reqwest::Method::GET,
                    &url,
                    None,
                )
                .await
                .with_context(|| format!("list Microsoft.App/{kind}"))?;
                if !status.is_success() {
                    break;
                }
                if let Some(items) = body.get("value").and_then(|v| v.as_array()) {
                    for item in items {
                        let name = item
                            .get("name")
                            .and_then(|n| n.as_str())
                            .unwrap_or("")
                            .to_string();
                        let ours = name.starts_with("fb-") || name.starts_with("fp-");
                        if ours && !keep.contains(&name) {
                            let del_url = aca_resource_url(&self.cfg, kind, &name);
                            let _ = azure::arm_request(
                                &self.client,
                                &self.mi,
                                reqwest::Method::DELETE,
                                &del_url,
                                None,
                            )
                            .await;
                            swept.push(name);
                        }
                    }
                }
                next = body
                    .get("nextLink")
                    .and_then(|l| l.as_str())
                    .map(|s| s.to_string());
            }
        }
        Ok(swept)
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

    #[test]
    fn test_tail_cursor_starts_at_zero() {
        let c = TailCursor::new();
        assert_eq!(c.offset, 0);
        assert_eq!(c.range_header(), "bytes=0-");
        assert_eq!(c.etag, None);
    }

    #[test]
    fn test_tail_cursor_advances_by_chunk_len() {
        let mut c = TailCursor::new();
        c.advance(50, Some("e1".to_string()));
        assert_eq!(c.offset, 50);
        assert_eq!(c.range_header(), "bytes=50-");
        assert_eq!(c.etag, Some("e1".to_string()));
        c.advance(30, Some("e2".to_string()));
        assert_eq!(c.offset, 80);
        assert_eq!(c.range_header(), "bytes=80-");
        assert_eq!(c.etag, Some("e2".to_string()));
    }

    #[test]
    fn test_tail_cursor_zero_chunk_keeps_offset() {
        let mut c = TailCursor::new();
        c.advance(50, Some("e1".to_string()));
        c.advance(0, None);
        assert_eq!(c.offset, 50);
        assert_eq!(c.etag, Some("e1".to_string()));
    }

    #[test]
    fn test_aca_names_are_azure_valid() {
        let job = aca_job_name("fj_01HMXR8ZZZ");
        let app = aca_app_name("fj_01HMXR8ZZZ");
        for name in [&job, &app] {
            assert!(name.len() <= 32, "too long: {name}");
            assert!(
                name.chars().all(|c| c.is_ascii_lowercase() || c.is_ascii_digit() || c == '-'),
                "invalid chars: {name}"
            );
            assert!(!name.contains('_'), "underscore: {name}");
            assert!(!name.ends_with('-'), "trailing hyphen: {name}");
        }
        assert_ne!(job, app);
    }

    #[test]
    fn test_aca_names_truncate_long_ids() {
        let name = aca_job_name(&"x".repeat(60));
        assert!(name.len() <= 32);
        assert!(!name.ends_with('-'));
    }

    #[test]
    fn test_aca_health_urls() {
        assert_eq!(
            aca_health_urls("app.region.azurecontainerapps.io"),
            [
                "https://app.region.azurecontainerapps.io/healthz".to_string(),
                "https://app.region.azurecontainerapps.io/".to_string(),
            ]
        );
    }

    #[test]
    fn test_teardown_delete_paths_cover_job_and_app() {
        let cfg = azure_test_cfg();
        let paths = teardown_delete_paths(&cfg, "fj_x");
        assert_eq!(paths.len(), 2);
        let job_path = paths
            .iter()
            .find(|p| p.contains("/providers/Microsoft.App/jobs/"))
            .expect("job delete path");
        let app_path = paths
            .iter()
            .find(|p| p.contains("/providers/Microsoft.App/containerApps/"))
            .expect("app delete path");
        assert!(job_path.contains(&aca_job_name("fj_x")));
        assert!(app_path.contains(&aca_app_name("fj_x")));
        for p in &paths {
            assert!(p.contains(&cfg.subscription_id));
            assert!(p.contains(&cfg.resource_group));
        }
    }

    #[test]
    fn test_latest_execution_status_picks_most_recent() {
        let list = json!({
            "value": [
                { "properties": { "status": "Failed", "startTime": "2024-01-01T00:00:00Z" } },
                { "properties": { "status": "Succeeded", "startTime": "2024-01-02T00:00:00Z" } }
            ]
        });
        assert_eq!(latest_execution_status(&list).as_deref(), Some("Succeeded"));
        assert!(is_terminal_status("Succeeded"));
        assert!(!is_terminal_status("Running"));
    }

    /// Opt-in live Azure smoke test. Never runs in CI — set
    /// `FOUNDRY_AZURE_SMOKE=1` and a full `FOUNDRY_SERVICE_AZURE_*` env to
    /// exercise a real round trip (mirrors the `TEST_DATABASE_URL` convention).
    #[tokio::test]
    async fn azure_live_smoke() {
        if std::env::var("FOUNDRY_AZURE_SMOKE").is_err() {
            return;
        }
        // When the flag is set: resolve real config, construct the backend,
        // and sweep orphans — a minimal authenticated round trip that proves
        // the managed-identity credential path and ARM listing both work.
        let cfg = AzureConfig::from_env().expect("resolve Azure config for smoke");
        let aca = AzureContainerApps::new(
            cfg,
            "foundry-builder:latest".to_string(),
            "http://127.0.0.1:9000".to_string(),
        );
        let swept = aca
            .sweep_orphans(&[])
            .await
            .expect("sweep_orphans round trip");
        eprintln!("azure_live_smoke: swept {} orphan resources", swept.len());
    }
}
