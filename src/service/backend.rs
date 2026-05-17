//! Pluggable build- and storage-backend traits.
//!
//! M1 ships a [`super::mock_backend::MockBuildBackend`] and a
//! [`super::storage_local::LocalFilesystem`]. M2 (T35.4) adds real Docker
//! builds and cloud object storage behind these same traits.

use std::path::PathBuf;

use anyhow::Result;
use async_trait::async_trait;

use crate::service::models::Job;

/// A handle to where a job's inputs/outputs/logs live, plus the credential a
/// (future, real) build container uses to reach them.
///
/// M1 `LocalFilesystem` uses `kind = "local_mount"` with a `mount_path` and no
/// `sas`. Cloud backends set `kind = "azure_blob"` etc. with a short-TTL `sas`.
#[derive(Clone, Debug)]
pub struct StorageGrant {
    pub kind: String,
    pub mount_path: Option<PathBuf>,
    pub sas: Option<String>,
}

/// An opaque handle to an in-progress build.
#[derive(Clone, Debug)]
pub struct BuildHandle {
    pub job_id: String,
}

/// A reference to a built container image.
#[derive(Clone, Debug)]
pub struct ImageRef {
    pub reference: String,
    /// Which Dockerfile produced the image: `"project"` (the build's own
    /// root `Dockerfile`) or `"fallback_node"` / `"fallback_python"` /
    /// `"fallback_static"` (a synthesized fallback).
    pub dockerfile_source: String,
}

/// The result of a successful preview deployment.
#[derive(Clone, Debug)]
pub struct PreviewInfo {
    pub url: String,
}

/// How the API should serve an artifact: either stream the bytes directly
/// (local backend) or redirect to a short-TTL signed URL (cloud backend).
#[derive(Clone, Debug)]
pub enum ArtifactResponse {
    Stream {
        filename: String,
        content_type: String,
        bytes: Vec<u8>,
    },
    Redirect {
        url: String,
    },
}

/// Which artifact a `fetch` call is for.
#[derive(Clone, Copy, Debug)]
pub enum ArtifactKind {
    Artifact,
    Diagnostics,
}

/// Backing store for a job's inputs, logs, artifacts, and diagnostics.
#[async_trait]
pub trait StorageBackend: Send + Sync {
    /// Persist the submitted `SPEC.md` / `TASKS.md` for a job.
    async fn put_input(&self, job_id: &str, spec_md: &str, tasks_md: &str) -> Result<()>;
    /// Issue a storage grant the build will mount/sign against.
    async fn issue_grant(&self, job_id: &str) -> Result<StorageGrant>;
    /// Revoke a previously issued grant (no-op for local mounts).
    async fn revoke_grant(&self, grant: &StorageGrant) -> Result<()>;
    /// Persist the recorded build event stream (JSONL).
    async fn put_logs(&self, job_id: &str, jsonl: &str) -> Result<()>;
    /// Read back the build logs, optionally filtered to one stage / tailed.
    async fn read_logs(
        &self,
        job_id: &str,
        stage: Option<&str>,
        tail: Option<usize>,
    ) -> Result<String>;
    /// Store the source artifact; returns the URL clients fetch it from.
    async fn put_artifact(&self, job_id: &str, bytes: &[u8]) -> Result<String>;
    /// Store the diagnostics bundle.
    async fn put_diagnostics(&self, job_id: &str, bytes: &[u8]) -> Result<()>;
    /// Fetch an artifact for serving over the API.
    async fn fetch(&self, job_id: &str, kind: ArtifactKind) -> Result<ArtifactResponse>;
}

/// Drives a job through the build/deploy lifecycle.
#[async_trait]
pub trait BuildBackend: Send + Sync {
    /// Start a build, handing it the storage grant and a scoped proxy token.
    async fn start_build(
        &self,
        job: &Job,
        grant: &StorageGrant,
        proxy_token: &str,
    ) -> Result<BuildHandle>;
    /// Return the recorded event stream (JSONL) for a build.
    async fn stream_events(&self, handle: &BuildHandle) -> Result<String>;
    /// Build the app's container image.
    async fn build_image(&self, job: &Job) -> Result<ImageRef>;
    /// Deploy a preview of the built image.
    async fn deploy_preview(&self, job: &Job, image: &ImageRef) -> Result<PreviewInfo>;
    /// Collect the built source as a `.tar.gz`: the working tree plus `.git`
    /// history, excluding `.buildloop/` and dependency/build directories.
    async fn collect_artifact(&self, handle: &BuildHandle) -> Result<Vec<u8>>;
    /// Collect the build diagnostics bundle as a `.tar.gz`: `.buildloop/*.md`
    /// plus the `.buildloop/history/**` per-task snapshots.
    async fn collect_diagnostics(&self, handle: &BuildHandle) -> Result<Vec<u8>>;
    /// Tear down any resources associated with a job.
    async fn teardown(&self, job_id: &str) -> Result<()>;
}
