//! `LocalDocker` — the M2 build backend.
//!
//! Runs each build in a disposable `foundry-builder` container (`docker/
//! foundry-builder/`). The job's storage directory is the per-job bind mount;
//! the container's entrypoint establishes the Build Container Contract, then
//! runs `foundry run --no-tui --output-format json-stream`. `LocalDocker`
//! captures container stdout into `jobs/<id>/logs/stream.jsonl` and stderr into
//! `jobs/<id>/logs/stderr.log`, and — after the container exits — packs the
//! source artifact and the diagnostics bundle straight off the bind mount.
//!
//! The pure helpers ([`service_profile_json`], [`pack_source`],
//! [`pack_diagnostics`], [`LocalDocker::docker_run_argv`]) carry the testable
//! weight; the `docker run` itself is gated behind an optional recorded-stream
//! test seam so the whole drive can be exercised without Docker.

use std::collections::HashSet;
use std::path::{Component, Path, PathBuf};
use std::process::Stdio;
use std::time::{Duration, Instant};

use anyhow::{Context, Result};
use async_trait::async_trait;
use flate2::write::GzEncoder;
use flate2::Compression;
use serde_json::json;
use walkdir::WalkDir;

use crate::service::backend::{BuildBackend, BuildHandle, ImageRef, PreviewInfo, StorageGrant};
use crate::service::caddy;
use crate::service::models::Job;

// ─── Build Container Contract ───────────────────────────────────────────────

/// Path components that are NEVER part of the source artifact: Context
/// Foundry's own build state plus dependency/build output directories.
const SOURCE_EXCLUDED: [&str; 4] = [".buildloop", "node_modules", "target", "dist"];

/// Render the service-owned `.foundry.json` for a build container.
///
/// This is the **exact** unattended-safe profile from the build-service spec:
/// `run_mode: "service"`, every provider pinned to Claude, no plugins, no
/// auto-push, no human gate, no local-model routing, sandbox disabled (the
/// outer build container is the isolation boundary). Tests assert every field.
pub fn render_service_profile() -> serde_json::Value {
    json!({
        "run_mode": "service",
        "planner_provider": "claude",
        "builder_provider": "claude",
        "reviewer_provider": "claude",
        "fixer_provider": "claude",
        "discovery_provider": "claude",
        "planner_model": "opus",
        "builder_model": "opus",
        "reviewer_model": "sonnet",
        "fixer_model": "sonnet",
        "discovery_model": "opus",
        "builder_models": [],
        "local_model": "",
        "stage_overrides": [],
        "plugins": [],
        "auto_push_remote": null,
        "require_human_approval": false,
        "planner_lookahead": false,
        "backpressure_only": false,
        "batch_doubt": false,
        "skip_doubt_for_simple": false,
        "doubt_confidence_threshold": 0,
        "parallel_builder": false,
        "arena_mode": "solo",
        "sandbox": false
    })
}

/// The service-owned `.foundry.json` rendered as pretty JSON text.
pub fn service_profile_json() -> String {
    serde_json::to_string_pretty(&render_service_profile())
        .expect("service profile is a static, serializable value")
}

/// Whether a path (relative to the build working tree) is excluded from the
/// `source.tar.gz` artifact. The `.git` directory is intentionally NOT
/// excluded — per-task commits are build provenance.
pub fn is_excluded_from_source(rel: &Path) -> bool {
    rel.components().any(|c| match c {
        Component::Normal(name) => SOURCE_EXCLUDED.iter().any(|e| name == *e),
        _ => false,
    })
}

// ─── Artifact packing ───────────────────────────────────────────────────────

/// Pack a build's working tree into a gzipped tar (`source.tar.gz`).
///
/// Includes the working tree **plus `.git` history**, and excludes
/// `.buildloop/`, `node_modules/`, `target/`, and `dist/` at any depth. Entries
/// are sorted for a deterministic layout.
pub fn pack_source(work_dir: &Path) -> Result<Vec<u8>> {
    if !work_dir.is_dir() {
        anyhow::bail!("source work dir does not exist: {}", work_dir.display());
    }
    let mut files: Vec<PathBuf> = Vec::new();
    let walker = WalkDir::new(work_dir)
        .sort_by_file_name()
        .into_iter()
        .filter_entry(|entry| match entry.path().strip_prefix(work_dir) {
            Ok(rel) => !is_excluded_from_source(rel),
            Err(_) => true,
        });
    for entry in walker {
        let entry = entry.context("walk build source tree")?;
        if entry.file_type().is_file() {
            files.push(entry.path().to_path_buf());
        }
    }
    files.sort();

    let mut builder = tar::Builder::new(GzEncoder::new(Vec::new(), Compression::default()));
    for path in &files {
        let rel = path
            .strip_prefix(work_dir)
            .expect("walked entry is under work_dir");
        builder
            .append_path_with_name(path, rel)
            .with_context(|| format!("add {} to source tar", rel.display()))?;
    }
    let encoder = builder.into_inner().context("finish source tar")?;
    encoder.finish().context("finish source gzip")
}

/// Pack a build's diagnostics into a gzipped tar.
///
/// Captures `.buildloop/*.md` (review reports, plans, build claims) plus the
/// entire `.buildloop/history/**` tree — the per-task snapshots that hold the
/// evidence behind any WIP/audit-failed task in a multi-task `ready` job.
/// Entries are rooted at `.buildloop/`. A missing or empty directory yields a
/// valid, empty archive.
pub fn pack_diagnostics(buildloop_dir: &Path) -> Result<Vec<u8>> {
    let mut files: Vec<(PathBuf, PathBuf)> = Vec::new();
    if buildloop_dir.is_dir() {
        // Top-level `.buildloop/*.md`.
        for entry in std::fs::read_dir(buildloop_dir).context("read .buildloop")? {
            let entry = entry.context("read .buildloop entry")?;
            let path = entry.path();
            let is_md = path.extension().map(|e| e == "md").unwrap_or(false);
            if path.is_file() && is_md {
                let name = Path::new(".buildloop").join(
                    path.file_name()
                        .expect("dir entry always has a file name"),
                );
                files.push((path, name));
            }
        }
        // The whole `.buildloop/history/**` tree.
        let history = buildloop_dir.join("history");
        if history.is_dir() {
            for entry in WalkDir::new(&history).sort_by_file_name() {
                let entry = entry.context("walk .buildloop/history")?;
                if entry.file_type().is_file() {
                    let rel = entry
                        .path()
                        .strip_prefix(buildloop_dir)
                        .expect("history entry is under .buildloop");
                    files.push((
                        entry.path().to_path_buf(),
                        Path::new(".buildloop").join(rel),
                    ));
                }
            }
        }
    }
    files.sort();

    let mut builder = tar::Builder::new(GzEncoder::new(Vec::new(), Compression::default()));
    for (abs, name) in &files {
        builder
            .append_path_with_name(abs, name)
            .with_context(|| format!("add {} to diagnostics tar", name.display()))?;
    }
    let encoder = builder.into_inner().context("finish diagnostics tar")?;
    encoder.finish().context("finish diagnostics gzip")
}

// ─── Container naming ───────────────────────────────────────────────────────

/// Sanitize a string into a Docker-name-safe component (`[a-zA-Z0-9_.-]`).
fn sanitize_component(s: &str) -> String {
    s.chars()
        .map(|c| {
            if c.is_ascii_alphanumeric() || matches!(c, '_' | '.' | '-') {
                c
            } else {
                '-'
            }
        })
        .collect()
}

/// The deterministic container name for a job's build container.
pub fn container_name(job_id: &str) -> String {
    format!("foundry-build-{}", sanitize_component(job_id))
}

/// The deterministic image tag for a job's preview app image.
///
/// Docker image repository names must be lowercase. Job IDs are `fj_` + a
/// ULID, and ULIDs are uppercase — so the component is lowercased here.
/// Container names (above) have no such rule and keep their original case.
pub fn preview_image_ref(job_id: &str) -> String {
    format!(
        "foundry-preview-{}:latest",
        sanitize_component(job_id).to_ascii_lowercase()
    )
}

/// The deterministic container name for a job's preview container.
pub fn preview_container_name(job_id: &str) -> String {
    format!("foundry-preview-{}", sanitize_component(job_id))
}

/// Recover the (sanitized) job label from a foundry container name.
/// Returns `Some(label)` for `foundry-build-*` / `foundry-preview-*`
/// container names, else `None`.
pub fn foundry_container_job_label(name: &str) -> Option<String> {
    name.strip_prefix("foundry-build-")
        .or_else(|| name.strip_prefix("foundry-preview-"))
        .filter(|s| !s.is_empty())
        .map(str::to_string)
}

// ─── Preview image build ────────────────────────────────────────────────────

/// The detected build stack, used to synthesize a fallback `Dockerfile` when a
/// build emitted none.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Stack {
    Node,
    Python,
    Static,
}

/// Classify a build tree by its marker files: `package.json` → Node,
/// `requirements.txt`/`pyproject.toml` → Python, otherwise a static server.
pub fn detect_stack(work_dir: &Path) -> Stack {
    if work_dir.join("package.json").is_file() {
        return Stack::Node;
    }
    if work_dir.join("requirements.txt").is_file() || work_dir.join("pyproject.toml").is_file() {
        return Stack::Python;
    }
    Stack::Static
}

/// The [`ImageRef::dockerfile_source`] label for a synthesized fallback build.
pub fn fallback_source_label(stack: Stack) -> &'static str {
    match stack {
        Stack::Node => "fallback_node",
        Stack::Python => "fallback_python",
        Stack::Static => "fallback_static",
    }
}

/// Synthesize a previewable `Dockerfile` for a build that emitted none (or an
/// invalid one). Every fallback binds `$PORT`/`8080` and `EXPOSE`s it.
pub fn fallback_dockerfile(stack: Stack) -> String {
    let lines: &[&str] = match stack {
        Stack::Node => &[
            "FROM node:22-slim",
            "WORKDIR /app",
            "COPY . .",
            "RUN if [ -f package-lock.json ]; then npm ci --omit=dev || npm install --omit=dev; else npm install --omit=dev; fi",
            "ENV PORT=8080",
            "EXPOSE 8080",
            "CMD [\"sh\", \"-c\", \"npm start\"]",
            "",
        ],
        Stack::Python => &[
            "FROM python:3.12-slim",
            "WORKDIR /app",
            "COPY . .",
            "RUN if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; fi",
            "ENV PORT=8080",
            "EXPOSE 8080",
            "CMD [\"sh\", \"-c\", \"if [ -f app.py ]; then exec python app.py; elif [ -f main.py ]; then exec python main.py; else exec python -m http.server ${PORT:-8080}; fi\"]",
            "",
        ],
        Stack::Static => &[
            "FROM python:3.12-slim",
            "WORKDIR /app",
            "COPY . .",
            "ENV PORT=8080",
            "EXPOSE 8080",
            "CMD [\"sh\", \"-c\", \"python -m http.server ${PORT:-8080}\"]",
            "",
        ],
    };
    lines.join("\n")
}

/// A cheap validity check for a project `Dockerfile`: a non-comment line that
/// starts with a `FROM ` instruction.
pub fn is_valid_dockerfile(content: &str) -> bool {
    content.lines().any(|line| {
        let bytes = line.trim_start().as_bytes();
        bytes.len() >= 5 && bytes[..5].eq_ignore_ascii_case(b"from ")
    })
}

/// The `docker build` argument vector (everything after the docker binary).
pub fn docker_build_argv(image_ref: &str, dockerfile_abs: &Path, context: &Path) -> Vec<String> {
    vec![
        "build".to_string(),
        "-t".to_string(),
        image_ref.to_string(),
        "-f".to_string(),
        dockerfile_abs.display().to_string(),
        context.display().to_string(),
    ]
}

// ─── Preview deployment ─────────────────────────────────────────────────────

/// Tunables for running and routing a preview container.
#[derive(Clone, Debug)]
pub struct PreviewConfig {
    pub network: String,
    pub base_domain: String,
    pub caddy_admin_url: String,
    pub caddy_server_name: String,
    pub container_port: u16,
    pub health_timeout_secs: u64,
    pub memory: String,
    pub cpus: String,
    pub pids_limit: u32,
}

impl Default for PreviewConfig {
    fn default() -> Self {
        PreviewConfig {
            network: "foundry-preview".to_string(),
            base_domain: "foundry.local".to_string(),
            caddy_admin_url: "http://localhost:2019".to_string(),
            caddy_server_name: "srv0".to_string(),
            container_port: 8080,
            health_timeout_secs: 60,
            memory: "512m".to_string(),
            cpus: "1".to_string(),
            pids_limit: 256,
        }
    }
}

/// CPU/memory/pids caps for a build container.
#[derive(Clone, Debug)]
pub struct BuildLimits {
    pub memory: String,
    pub cpus: String,
    pub pids_limit: u32,
}

impl Default for BuildLimits {
    fn default() -> Self {
        BuildLimits {
            memory: "4g".to_string(),
            cpus: "2".to_string(),
            pids_limit: 512,
        }
    }
}

/// Poll a preview upstream's `/healthz` then `/` until one returns HTTP 200, or
/// the timeout elapses. A connection error (the app still booting) is swallowed
/// and retried; only the deadline produces an error.
pub async fn health_check(upstream: &str, timeout_secs: u64) -> Result<()> {
    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(5))
        .build()
        .context("build health-check client")?;
    let deadline = Instant::now() + Duration::from_secs(timeout_secs);
    loop {
        for path in ["/healthz", "/"] {
            let url = format!("http://{upstream}{path}");
            if let Ok(resp) = client.get(&url).send().await {
                if resp.status() == reqwest::StatusCode::OK {
                    return Ok(());
                }
            }
        }
        if Instant::now() >= deadline {
            anyhow::bail!("preview at {upstream} did not return 200 within {timeout_secs}s");
        }
        tokio::time::sleep(Duration::from_secs(1)).await;
    }
}

// ─── LocalDocker backend ────────────────────────────────────────────────────

/// A [`BuildBackend`] that runs builds in local `foundry-builder` containers.
pub struct LocalDocker {
    image: String,
    storage_root: PathBuf,
    /// The URL a build container uses for `ANTHROPIC_BASE_URL` — the daemon's
    /// auth proxy, reachable from inside the container (e.g. via
    /// `host.docker.internal`).
    proxy_url: String,
    docker_bin: String,
    /// Test seam: when set, [`LocalDocker::start_build`] skips `docker run` and
    /// treats this string as the container's stdout (a recorded json-stream).
    recorded_stream: Option<String>,
    /// Tunables for running and routing preview containers.
    preview: PreviewConfig,
    /// CPU/memory/pids caps applied to the build container.
    build_limits: BuildLimits,
}

impl LocalDocker {
    /// Construct a backend that launches real `docker run` containers.
    pub fn new(
        image: String,
        storage_root: PathBuf,
        proxy_url: String,
        docker_bin: String,
    ) -> LocalDocker {
        LocalDocker {
            image,
            storage_root,
            proxy_url,
            docker_bin,
            recorded_stream: None,
            preview: PreviewConfig::default(),
            build_limits: BuildLimits::default(),
        }
    }

    /// Override the preview tunables. A builder method so `new` /
    /// `with_recorded_stream` keep their existing signatures.
    pub fn with_preview_config(mut self, preview: PreviewConfig) -> LocalDocker {
        self.preview = preview;
        self
    }

    /// Override the build-container CPU/memory/pids caps. A builder method,
    /// mirroring [`LocalDocker::with_preview_config`].
    pub fn with_build_limits(mut self, build_limits: BuildLimits) -> LocalDocker {
        self.build_limits = build_limits;
        self
    }

    /// Construct a backend that replays `stream` instead of running Docker —
    /// used to exercise the build drive in tests without a Docker daemon.
    pub fn with_recorded_stream(storage_root: PathBuf, stream: String) -> LocalDocker {
        LocalDocker {
            image: "foundry-builder:latest".to_string(),
            storage_root,
            proxy_url: "http://host.docker.internal:8788".to_string(),
            docker_bin: "docker".to_string(),
            recorded_stream: Some(stream),
            preview: PreviewConfig::default(),
            build_limits: BuildLimits::default(),
        }
    }

    /// `<storage_root>/jobs/<id>`.
    pub fn job_dir(&self, job_id: &str) -> PathBuf {
        self.storage_root.join("jobs").join(job_id)
    }

    /// The bind-mounted build working tree, `<job_dir>/work`.
    pub fn work_dir(&self, job_id: &str) -> PathBuf {
        self.job_dir(job_id).join("work")
    }

    /// The job's log directory, `<job_dir>/logs`.
    pub fn logs_dir(&self, job_id: &str) -> PathBuf {
        self.job_dir(job_id).join("logs")
    }

    /// Render the `docker run` argument vector (everything after the docker
    /// binary). Injects `ANTHROPIC_BASE_URL` → the auth proxy, the per-build
    /// scoped token as `ANTHROPIC_AUTH_TOKEN`, the per-job bind mount, and
    /// coarse CPU/memory/pids resource caps.
    ///
    /// The token is injected as `ANTHROPIC_AUTH_TOKEN` (not `ANTHROPIC_API_KEY`)
    /// so the `claude` CLI sends it in the `Authorization: Bearer` header — the
    /// header the auth proxy reads (`messages_handler` in `proxy.rs`). An
    /// `ANTHROPIC_API_KEY` would instead go out as `x-api-key` and the proxy
    /// would reject the request as unauthorized.
    pub fn docker_run_argv(&self, job_id: &str, work_dir: &Path, proxy_token: &str) -> Vec<String> {
        vec![
            "run".to_string(),
            "--rm".to_string(),
            "--name".to_string(),
            container_name(job_id),
            "-e".to_string(),
            format!("ANTHROPIC_BASE_URL={}", self.proxy_url),
            "-e".to_string(),
            format!("ANTHROPIC_AUTH_TOKEN={proxy_token}"),
            "--add-host".to_string(),
            "host.docker.internal:host-gateway".to_string(),
            "--memory".to_string(),
            self.build_limits.memory.clone(),
            "--cpus".to_string(),
            self.build_limits.cpus.clone(),
            "--pids-limit".to_string(),
            self.build_limits.pids_limit.to_string(),
            "-v".to_string(),
            format!("{}:/work", work_dir.display()),
            "-w".to_string(),
            "/work".to_string(),
            self.image.clone(),
        ]
    }

    /// The `docker rm -f` argument vector for a job's build container.
    pub fn rm_argv(&self, job_id: &str) -> Vec<String> {
        vec![
            "rm".to_string(),
            "-f".to_string(),
            container_name(job_id),
        ]
    }

    /// Run the build container to completion, streaming its stdout into
    /// `logs/stream.jsonl` and stderr into `logs/stderr.log`. Returns the
    /// container exit code.
    async fn run_container(&self, job_id: &str, argv: &[String]) -> Result<i32> {
        let logs = self.logs_dir(job_id);
        std::fs::create_dir_all(&logs)
            .with_context(|| format!("create logs dir {}", logs.display()))?;
        let stdout = std::fs::File::create(logs.join("stream.jsonl"))
            .context("create logs/stream.jsonl")?;
        let stderr = std::fs::File::create(logs.join("stderr.log"))
            .context("create logs/stderr.log")?;
        let status = tokio::process::Command::new(&self.docker_bin)
            .args(argv)
            .stdin(Stdio::null())
            .stdout(Stdio::from(stdout))
            .stderr(Stdio::from(stderr))
            .status()
            .await
            .with_context(|| format!("spawn `{}` for job {job_id}", self.docker_bin))?;
        Ok(status.code().unwrap_or(-1))
    }

    /// The `docker network create` argv for the isolated preview network.
    /// `--internal` keeps preview containers inbound-only (no egress).
    pub fn network_create_argv(&self) -> Vec<String> {
        vec![
            "network".to_string(),
            "create".to_string(),
            "--internal".to_string(),
            "--driver".to_string(),
            "bridge".to_string(),
            self.preview.network.clone(),
        ]
    }

    /// The `docker run -d` argv for a preview container: the isolated network,
    /// CPU/memory/pids caps, a bounded restart policy, and only a `PORT` env
    /// var. It MUST NOT carry any secret — no `ANTHROPIC_*` is ever injected.
    pub fn preview_run_argv(&self, job_id: &str, image_ref: &str) -> Vec<String> {
        vec![
            "run".to_string(),
            "-d".to_string(),
            "--name".to_string(),
            preview_container_name(job_id),
            "--network".to_string(),
            self.preview.network.clone(),
            "--restart".to_string(),
            "on-failure:3".to_string(),
            "--memory".to_string(),
            self.preview.memory.clone(),
            "--cpus".to_string(),
            self.preview.cpus.clone(),
            "--pids-limit".to_string(),
            self.preview.pids_limit.to_string(),
            "-e".to_string(),
            format!("PORT={}", self.preview.container_port),
            // No `-p` host-port publish: the preview is reached by container
            // name on the shared `foundry-preview` network. Publishing a port
            // does not work here anyway — the network is `--internal`, and the
            // service runs in its own container with its own loopback.
            image_ref.to_string(),
        ]
    }

    /// Run one `docker build`, teeing stdout/stderr to `logs/image-build.log`.
    async fn try_build(
        &self,
        job_id: &str,
        image_ref: &str,
        dockerfile_abs: &Path,
        context: &Path,
    ) -> Result<()> {
        let logs = self.logs_dir(job_id);
        std::fs::create_dir_all(&logs).ok();
        let log = std::fs::File::create(logs.join("image-build.log"))
            .context("create image-build.log")?;
        let log_err = log.try_clone().context("clone image-build log handle")?;
        let argv = docker_build_argv(image_ref, dockerfile_abs, context);
        let status = tokio::process::Command::new(&self.docker_bin)
            .args(&argv)
            .stdin(Stdio::null())
            .stdout(Stdio::from(log))
            .stderr(Stdio::from(log_err))
            .status()
            .await
            .with_context(|| format!("spawn docker build for job {job_id}"))?;
        if status.success() {
            Ok(())
        } else {
            anyhow::bail!("docker build exited with {:?}", status.code())
        }
    }
}

#[async_trait]
impl BuildBackend for LocalDocker {
    async fn start_build(
        &self,
        job: &Job,
        grant: &StorageGrant,
        proxy_token: &str,
    ) -> Result<BuildHandle> {
        if grant.kind != "local_mount" || grant.mount_path.is_none() {
            anyhow::bail!("LocalDocker requires a local_mount storage grant");
        }

        // Lay the build working tree out under the bind mount, with the
        // service-owned `.foundry.json` and the submitted inputs.
        let work = self.work_dir(&job.id);
        let logs = self.logs_dir(&job.id);
        std::fs::create_dir_all(&work)
            .with_context(|| format!("create work dir {}", work.display()))?;
        std::fs::create_dir_all(&logs)
            .with_context(|| format!("create logs dir {}", logs.display()))?;
        std::fs::write(work.join(".foundry.json"), service_profile_json())
            .context("write service .foundry.json")?;
        std::fs::write(work.join("SPEC.md"), &job.spec_md).context("write SPEC.md")?;
        std::fs::write(work.join("TASKS.md"), &job.tasks_md).context("write TASKS.md")?;

        if let Some(stream) = &self.recorded_stream {
            // Test seam: skip Docker, treat the recording as container stdout.
            std::fs::write(logs.join("stream.jsonl"), stream)
                .context("write recorded stream")?;
            std::fs::write(logs.join("stderr.log"), b"").context("write recorded stderr")?;
            return Ok(BuildHandle {
                job_id: job.id.clone(),
            });
        }

        let argv = self.docker_run_argv(&job.id, &work, proxy_token);
        let code = self.run_container(&job.id, &argv).await?;
        if code != 0 {
            anyhow::bail!(
                "foundry-builder container for job {} exited with status {code}",
                job.id
            );
        }
        Ok(BuildHandle {
            job_id: job.id.clone(),
        })
    }

    async fn stream_events(&self, handle: &BuildHandle) -> Result<String> {
        let path = self.logs_dir(&handle.job_id).join("stream.jsonl");
        match std::fs::read_to_string(&path) {
            Ok(s) => Ok(s),
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(String::new()),
            Err(e) => Err(anyhow::Error::new(e).context("read build event stream")),
        }
    }

    async fn build_image(&self, job: &Job) -> Result<ImageRef> {
        let work = self.work_dir(&job.id);
        let image = preview_image_ref(&job.id);

        // Test seam: a recorded build never produced a real working tree.
        if self.recorded_stream.is_some() {
            return Ok(ImageRef {
                reference: image,
                dockerfile_source: "project".to_string(),
            });
        }

        // Honor a valid project Dockerfile when the build emitted one.
        let root = work.join("Dockerfile");
        let project_valid = std::fs::read_to_string(&root)
            .ok()
            .map(|c| is_valid_dockerfile(&c))
            .unwrap_or(false);
        if project_valid
            && self
                .try_build(&job.id, &image, &root, &work)
                .await
                .is_ok()
        {
            return Ok(ImageRef {
                reference: image,
                dockerfile_source: "project".to_string(),
            });
        }

        // Otherwise synthesize a fallback by stack detection.
        let stack = detect_stack(&work);
        let fallback = work.join("Dockerfile.foundry-fallback");
        std::fs::write(&fallback, fallback_dockerfile(stack))
            .context("write fallback Dockerfile")?;
        if self
            .try_build(&job.id, &image, &fallback, &work)
            .await
            .is_ok()
        {
            return Ok(ImageRef {
                reference: image,
                dockerfile_source: fallback_source_label(stack).to_string(),
            });
        }

        anyhow::bail!(
            "preview image build failed for job {}: project Dockerfile {} and {:?} fallback both failed",
            job.id,
            if project_valid {
                "build failed"
            } else {
                "absent/invalid"
            },
            stack,
        )
    }

    async fn deploy_preview(&self, job: &Job, image: &ImageRef) -> Result<PreviewInfo> {
        let url = caddy::preview_url(
            &job.app_name,
            job.org_slug.as_deref(),
            &self.preview.base_domain,
        );

        // Test seam: a recorded build never produced a real image to run.
        if self.recorded_stream.is_some() {
            return Ok(PreviewInfo { url });
        }

        // Ensure the isolated preview network exists (ignore "already exists").
        let _ = tokio::process::Command::new(&self.docker_bin)
            .args(self.network_create_argv())
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status()
            .await;

        // Run the preview container.
        let run = tokio::process::Command::new(&self.docker_bin)
            .args(self.preview_run_argv(&job.id, &image.reference))
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status()
            .await
            .with_context(|| format!("spawn docker run for preview {}", job.id))?;
        if !run.success() {
            anyhow::bail!("preview container for job {} failed to start", job.id);
        }

        // The preview is reached by container name on the shared
        // `foundry-preview` network — the service and the reverse proxy both
        // join it. No host port is published (see `preview_run_argv`).
        let upstream = format!(
            "{}:{}",
            preview_container_name(&job.id),
            self.preview.container_port
        );

        // Health-check; on failure tear the container down so a failed deploy
        // leaves nothing running.
        if let Err(e) = health_check(&upstream, self.preview.health_timeout_secs).await {
            let _ = self.teardown(&job.id).await;
            return Err(e.context("preview health check"));
        }

        // Register the Caddy route — best-effort: a missing/misconfigured
        // Caddy logs a warning but must NOT fail the job.
        let hostname = caddy::preview_hostname(
            &job.app_name,
            job.org_slug.as_deref(),
            &self.preview.base_domain,
        );
        if let Err(e) = caddy::add_route(
            &self.preview.caddy_admin_url,
            &self.preview.caddy_server_name,
            &job.id,
            &hostname,
            &upstream,
        )
        .await
        {
            eprintln!(
                "foundry service: Caddy route for {} not registered: {e}",
                job.id
            );
        }

        Ok(PreviewInfo { url })
    }

    async fn collect_artifact(&self, handle: &BuildHandle) -> Result<Vec<u8>> {
        pack_source(&self.work_dir(&handle.job_id))
    }

    async fn collect_diagnostics(&self, handle: &BuildHandle) -> Result<Vec<u8>> {
        pack_diagnostics(&self.work_dir(&handle.job_id).join(".buildloop"))
    }

    async fn teardown(&self, job_id: &str) -> Result<()> {
        if self.recorded_stream.is_some() {
            // No container was ever launched in the test seam.
            return Ok(());
        }
        // Best-effort: remove the build container, the preview container, and
        // the Caddy route. A `--rm` build container is usually already gone.
        for name in [container_name(job_id), preview_container_name(job_id)] {
            let _ = tokio::process::Command::new(&self.docker_bin)
                .args(["rm", "-f", name.as_str()])
                .stdin(Stdio::null())
                .stdout(Stdio::null())
                .stderr(Stdio::null())
                .status()
                .await;
        }
        let _ = caddy::remove_route(&self.preview.caddy_admin_url, job_id).await;
        Ok(())
    }

    async fn sweep_orphans(&self, active_ids: &[String]) -> Result<Vec<String>> {
        if self.recorded_stream.is_some() {
            // No real Docker daemon in the test seam — nothing to sweep.
            return Ok(Vec::new());
        }
        let out = tokio::process::Command::new(&self.docker_bin)
            .args(["ps", "-a", "--format", "{{.Names}}"])
            .stdin(Stdio::null())
            .output()
            .await
            .context("docker ps for orphan sweep")?;
        if !out.status.success() {
            return Ok(Vec::new());
        }
        let active: HashSet<String> =
            active_ids.iter().map(|id| sanitize_component(id)).collect();
        let names = String::from_utf8_lossy(&out.stdout);
        let mut swept: Vec<String> = Vec::new();
        for name in names.lines().map(str::trim).filter(|n| !n.is_empty()) {
            let Some(label) = foundry_container_job_label(name) else {
                continue;
            };
            if active.contains(&label) {
                continue;
            }
            // Best-effort: kill the orphaned container and drop its Caddy route.
            let _ = tokio::process::Command::new(&self.docker_bin)
                .args(["rm", "-f", name])
                .stdin(Stdio::null())
                .stdout(Stdio::null())
                .stderr(Stdio::null())
                .status()
                .await;
            let _ = caddy::remove_route(&self.preview.caddy_admin_url, &label).await;
            if !swept.contains(&label) {
                swept.push(label);
            }
        }
        swept.sort();
        Ok(swept)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn service_profile_pins_the_exact_contract() {
        let p = render_service_profile();
        assert_eq!(p["run_mode"], "service");
        for provider in [
            "planner_provider",
            "builder_provider",
            "reviewer_provider",
            "fixer_provider",
            "discovery_provider",
        ] {
            assert_eq!(p[provider], "claude", "{provider} must be Claude-only");
        }
        assert_eq!(p["plugins"], json!([]));
        assert_eq!(p["stage_overrides"], json!([]));
        assert_eq!(p["builder_models"], json!([]));
        assert_eq!(p["local_model"], "");
        assert!(p["auto_push_remote"].is_null());
        assert_eq!(p["require_human_approval"], false);
        assert_eq!(p["planner_lookahead"], false);
        assert_eq!(p["backpressure_only"], false);
        assert_eq!(p["batch_doubt"], false);
        assert_eq!(p["skip_doubt_for_simple"], false);
        assert_eq!(p["doubt_confidence_threshold"], 0);
        assert_eq!(p["parallel_builder"], false);
        assert_eq!(p["arena_mode"], "solo");
        assert_eq!(p["sandbox"], false);
    }

    #[test]
    fn service_profile_json_is_parseable() {
        let text = service_profile_json();
        let parsed: serde_json::Value = serde_json::from_str(&text).expect("valid JSON");
        assert_eq!(parsed["run_mode"], "service");
    }

    #[test]
    fn source_exclusion_predicate() {
        assert!(is_excluded_from_source(Path::new(".buildloop/review-report.md")));
        assert!(is_excluded_from_source(Path::new("node_modules/pkg/index.js")));
        assert!(is_excluded_from_source(Path::new("target/debug/foundry")));
        assert!(is_excluded_from_source(Path::new("dist/bundle.js")));
        assert!(is_excluded_from_source(Path::new("ui/node_modules/x.js")));
        assert!(!is_excluded_from_source(Path::new("src/main.rs")));
        assert!(!is_excluded_from_source(Path::new(".git/HEAD")));
        assert!(!is_excluded_from_source(Path::new("SPEC.md")));
    }

    #[test]
    fn container_name_is_deterministic_and_safe() {
        assert_eq!(container_name("fj_01HMX"), "foundry-build-fj_01HMX");
        // Unsafe characters are replaced.
        assert_eq!(container_name("a/b c"), "foundry-build-a-b-c");
        let n = container_name("fj_01HMX");
        assert!(n
            .chars()
            .all(|c| c.is_ascii_alphanumeric() || matches!(c, '_' | '.' | '-')));
    }

    #[test]
    fn docker_run_argv_injects_proxy_mount_and_caps() {
        let backend = LocalDocker::new(
            "foundry-builder:latest".to_string(),
            PathBuf::from("/srv/storage"),
            "http://host.docker.internal:8788".to_string(),
            "docker".to_string(),
        );
        let argv = backend.docker_run_argv("fj_1", Path::new("/srv/storage/jobs/fj_1/work"), "fb_tok");
        assert_eq!(argv[0], "run");
        assert!(argv.contains(&"--rm".to_string()));
        assert!(argv.contains(&"ANTHROPIC_BASE_URL=http://host.docker.internal:8788".to_string()));
        assert!(argv.contains(&"ANTHROPIC_AUTH_TOKEN=fb_tok".to_string()));
        assert!(argv.contains(&"/srv/storage/jobs/fj_1/work:/work".to_string()));
        assert!(argv.contains(&"--pids-limit".to_string()));
        assert!(argv.contains(&"4g".to_string()), "default build memory cap");
        assert!(argv.contains(&"2".to_string()), "default build cpus cap");
        assert!(argv.contains(&"512".to_string()), "default build pids cap");
        assert!(argv.contains(&"foundry-build-fj_1".to_string()));
        assert_eq!(argv.last().unwrap(), "foundry-builder:latest");
        // The real Anthropic key must never appear in the container argv.
        assert!(!argv.iter().any(|a| a.contains("sk-ant")));
    }

    #[test]
    fn rm_argv_force_removes_the_named_container() {
        let backend = LocalDocker::new(
            "img".to_string(),
            PathBuf::from("/srv"),
            "http://proxy".to_string(),
            "docker".to_string(),
        );
        assert_eq!(
            backend.rm_argv("fj_1"),
            vec!["rm", "-f", "foundry-build-fj_1"]
        );
    }

    #[test]
    fn detect_stack_classifies_marker_files() {
        let base = std::env::temp_dir().join(format!("foundry-detect-{}", ulid::Ulid::new()));
        let node = base.join("node");
        let py_req = base.join("py-req");
        let py_proj = base.join("py-proj");
        let empty = base.join("empty");
        for dir in [&node, &py_req, &py_proj, &empty] {
            std::fs::create_dir_all(dir).unwrap();
        }
        std::fs::write(node.join("package.json"), "{}").unwrap();
        std::fs::write(py_req.join("requirements.txt"), "").unwrap();
        std::fs::write(py_proj.join("pyproject.toml"), "").unwrap();

        assert_eq!(detect_stack(&node), Stack::Node);
        assert_eq!(detect_stack(&py_req), Stack::Python);
        assert_eq!(detect_stack(&py_proj), Stack::Python);
        assert_eq!(detect_stack(&empty), Stack::Static);
    }

    #[test]
    fn is_valid_dockerfile_requires_a_from_line() {
        assert!(is_valid_dockerfile("FROM node:22\n"));
        assert!(is_valid_dockerfile("# comment\nfrom python:3.12"));
        assert!(!is_valid_dockerfile("# just a comment\nRUN echo hi"));
        assert!(!is_valid_dockerfile(""));
    }

    #[test]
    fn fallback_dockerfile_binds_port_and_exposes() {
        for stack in [Stack::Node, Stack::Python, Stack::Static] {
            let d = fallback_dockerfile(stack);
            assert!(d.contains("FROM "), "{stack:?} fallback has a FROM line");
            assert!(d.contains("EXPOSE 8080"), "{stack:?} fallback exposes 8080");
            assert!(d.contains("PORT"), "{stack:?} fallback sets PORT");
        }
    }

    #[test]
    fn preview_image_ref_and_name_are_safe() {
        // The image ref must be lowercased: job IDs are uppercase ULIDs but
        // Docker rejects an image repository name that is not lowercase.
        assert_eq!(
            preview_image_ref("fj_01HMX"),
            "foundry-preview-fj_01hmx:latest"
        );
        // Container names have no lowercase rule and keep their case.
        assert_eq!(
            preview_container_name("a/b c"),
            "foundry-preview-a-b-c"
        );
    }

    #[test]
    fn foundry_container_job_label_strips_prefixes() {
        assert_eq!(
            foundry_container_job_label("foundry-build-fj_1"),
            Some("fj_1".to_string())
        );
        assert_eq!(
            foundry_container_job_label("foundry-preview-fj_1"),
            Some("fj_1".to_string())
        );
        assert_eq!(foundry_container_job_label("postgres"), None);
        assert_eq!(foundry_container_job_label("foundry-build-"), None);
    }

    #[test]
    fn docker_build_argv_has_tag_file_and_context() {
        let argv = docker_build_argv(
            "img:latest",
            Path::new("/w/Dockerfile"),
            Path::new("/w"),
        );
        assert_eq!(argv[0], "build");
        assert!(argv.contains(&"-t".to_string()));
        assert!(argv.contains(&"-f".to_string()));
        assert!(argv.contains(&"img:latest".to_string()));
        assert_eq!(argv.last().unwrap(), "/w");
    }

    #[test]
    fn preview_run_argv_has_caps_isolation_and_no_secrets() {
        let backend = LocalDocker::new(
            "img".to_string(),
            PathBuf::from("/srv"),
            "http://proxy".to_string(),
            "docker".to_string(),
        );
        let argv = backend.preview_run_argv("fj_1", "img:latest");
        for expected in [
            "--network",
            "foundry-preview",
            "--restart",
            "on-failure:3",
            "--memory",
            "512m",
            "--cpus",
            "1",
            "--pids-limit",
            "256",
            "-e",
            "PORT=8080",
        ] {
            assert!(
                argv.contains(&expected.to_string()),
                "preview argv contains `{expected}`"
            );
        }
        assert!(!argv.iter().any(|a| a.contains("ANTHROPIC")));
        assert!(!argv.iter().any(|a| a.contains("sk-ant")));
        // No host-port publish — the preview is reached by container name.
        assert!(!argv.iter().any(|a| a == "-p"));
    }

    #[test]
    fn docker_run_argv_honors_custom_build_limits() {
        let backend = LocalDocker::new(
            "foundry-builder:latest".to_string(),
            PathBuf::from("/srv"),
            "http://proxy".to_string(),
            "docker".to_string(),
        )
        .with_build_limits(BuildLimits {
            memory: "8g".to_string(),
            cpus: "4".to_string(),
            pids_limit: 1024,
        });
        let argv = backend.docker_run_argv("fj_1", Path::new("/srv/jobs/fj_1/work"), "fb_tok");
        assert!(argv.contains(&"8g".to_string()), "custom build memory cap");
        assert!(argv.contains(&"4".to_string()), "custom build cpus cap");
        assert!(argv.contains(&"1024".to_string()), "custom build pids cap");
        assert!(
            !argv.contains(&"4g".to_string()),
            "default memory cap is overridden"
        );
    }

    #[test]
    fn with_preview_config_overrides_defaults() {
        let backend = LocalDocker::new(
            "img".to_string(),
            PathBuf::from("/srv"),
            "http://proxy".to_string(),
            "docker".to_string(),
        )
        .with_preview_config(PreviewConfig {
            network: "custom-net".to_string(),
            ..PreviewConfig::default()
        });
        assert!(backend
            .preview_run_argv("fj_1", "img:latest")
            .contains(&"custom-net".to_string()));
    }
}
