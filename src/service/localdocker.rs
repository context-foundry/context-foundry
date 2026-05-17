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

use std::path::{Component, Path, PathBuf};
use std::process::Stdio;

use anyhow::{Context, Result};
use async_trait::async_trait;
use flate2::write::GzEncoder;
use flate2::Compression;
use serde_json::json;
use walkdir::WalkDir;

use crate::service::backend::{BuildBackend, BuildHandle, ImageRef, PreviewInfo, StorageGrant};
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
        }
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
    /// scoped token as `ANTHROPIC_API_KEY`, the per-job bind mount, and coarse
    /// CPU/memory/pids resource caps.
    pub fn docker_run_argv(&self, job_id: &str, work_dir: &Path, proxy_token: &str) -> Vec<String> {
        vec![
            "run".to_string(),
            "--rm".to_string(),
            "--name".to_string(),
            container_name(job_id),
            "-e".to_string(),
            format!("ANTHROPIC_BASE_URL={}", self.proxy_url),
            "-e".to_string(),
            format!("ANTHROPIC_API_KEY={proxy_token}"),
            "--add-host".to_string(),
            "host.docker.internal:host-gateway".to_string(),
            "--memory".to_string(),
            "4g".to_string(),
            "--cpus".to_string(),
            "2".to_string(),
            "--pids-limit".to_string(),
            "512".to_string(),
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

    async fn build_image(&self, _job: &Job) -> Result<ImageRef> {
        anyhow::bail!("LocalDocker preview image build lands in M3 (T35.5)")
    }

    async fn deploy_preview(&self, _job: &Job, _image: &ImageRef) -> Result<PreviewInfo> {
        anyhow::bail!("LocalDocker preview deployment lands in M3 (T35.5)")
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
        // Best-effort: a `--rm` container is usually already gone.
        let _ = tokio::process::Command::new(&self.docker_bin)
            .args(self.rm_argv(job_id))
            .stdin(Stdio::null())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status()
            .await;
        Ok(())
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
        assert!(argv.contains(&"ANTHROPIC_API_KEY=fb_tok".to_string()));
        assert!(argv.contains(&"/srv/storage/jobs/fj_1/work:/work".to_string()));
        assert!(argv.contains(&"--pids-limit".to_string()));
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
}
