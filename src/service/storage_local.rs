//! `LocalFilesystem` — the M1 storage backend.
//!
//! Lays each job out under `<root>/jobs/<job_id>/` with `input/`, `output/`,
//! `logs/`, and `diagnostics/` subdirectories. Artifacts are streamed back
//! directly (no signed URLs); the `StorageGrant` is a plain local mount.

use std::path::{Path, PathBuf};

use anyhow::{Context, Result};
use async_trait::async_trait;

use crate::service::backend::{
    filter_log_lines, ArtifactKind, ArtifactResponse, StorageBackend, StorageGrant,
};

/// Filesystem-backed [`StorageBackend`].
pub struct LocalFilesystem {
    root: PathBuf,
}

impl LocalFilesystem {
    pub fn new(root: PathBuf) -> Self {
        Self { root }
    }

    fn job_dir(&self, job_id: &str) -> PathBuf {
        self.root.join("jobs").join(job_id)
    }
}

fn write_file(path: &Path, bytes: &[u8]) -> Result<()> {
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)
            .with_context(|| format!("create dir {}", parent.display()))?;
    }
    std::fs::write(path, bytes).with_context(|| format!("write {}", path.display()))
}

#[async_trait]
impl StorageBackend for LocalFilesystem {
    async fn put_input(&self, job_id: &str, spec_md: &str, tasks_md: &str) -> Result<()> {
        let input = self.job_dir(job_id).join("input");
        write_file(&input.join("SPEC.md"), spec_md.as_bytes())?;
        write_file(&input.join("TASKS.md"), tasks_md.as_bytes())?;
        Ok(())
    }

    async fn issue_grant(&self, job_id: &str) -> Result<StorageGrant> {
        let dir = self.job_dir(job_id);
        for sub in ["input", "output", "logs", "diagnostics"] {
            std::fs::create_dir_all(dir.join(sub))
                .with_context(|| format!("create {sub} dir for job {job_id}"))?;
        }
        Ok(StorageGrant {
            kind: "local_mount".to_string(),
            mount_path: Some(dir),
            sas: None,
        })
    }

    async fn revoke_grant(&self, _grant: &StorageGrant) -> Result<()> {
        // Nothing to revoke for a local mount.
        Ok(())
    }

    async fn put_logs(&self, job_id: &str, jsonl: &str) -> Result<()> {
        write_file(
            &self.job_dir(job_id).join("logs").join("stream.jsonl"),
            jsonl.as_bytes(),
        )
    }

    async fn read_logs(
        &self,
        job_id: &str,
        stage: Option<&str>,
        tail: Option<usize>,
    ) -> Result<String> {
        let path = self.job_dir(job_id).join("logs").join("stream.jsonl");
        let content = match std::fs::read_to_string(&path) {
            Ok(c) => c,
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => return Ok(String::new()),
            Err(e) => {
                return Err(anyhow::Error::new(e).context("read job logs"));
            }
        };
        Ok(filter_log_lines(&content, stage, tail))
    }

    async fn put_artifact(&self, job_id: &str, bytes: &[u8]) -> Result<String> {
        write_file(
            &self.job_dir(job_id).join("output").join("source.tar.gz"),
            bytes,
        )?;
        Ok(format!("/v1/jobs/{job_id}/artifact"))
    }

    async fn put_diagnostics(&self, job_id: &str, bytes: &[u8]) -> Result<()> {
        write_file(
            &self
                .job_dir(job_id)
                .join("diagnostics")
                .join("diagnostics.tar.gz"),
            bytes,
        )
    }

    async fn fetch(&self, job_id: &str, kind: ArtifactKind) -> Result<ArtifactResponse> {
        let (rel, filename) = match kind {
            ArtifactKind::Artifact => (
                Path::new("output").join("source.tar.gz"),
                "source.tar.gz",
            ),
            ArtifactKind::Diagnostics => (
                Path::new("diagnostics").join("diagnostics.tar.gz"),
                "diagnostics.tar.gz",
            ),
        };
        let path = self.job_dir(job_id).join(rel);
        let bytes = match std::fs::read(&path) {
            Ok(b) => b,
            Err(e) if e.kind() == std::io::ErrorKind::NotFound => {
                anyhow::bail!("artifact not found for job {job_id}")
            }
            Err(e) => return Err(anyhow::Error::new(e).context("read artifact")),
        };
        Ok(ArtifactResponse::Stream {
            filename: filename.to_string(),
            content_type: "application/gzip".to_string(),
            bytes,
        })
    }
}
