//! `MockBuildBackend` — the M1 build backend.
//!
//! It performs no real work: `stream_events` replays a recorded JSONL event
//! stream verbatim (the same fixture `foundry run --output-format json-stream`
//! emits), and the image/preview steps return synthetic references. This lets
//! the worker pool, job store, and API be exercised end-to-end without Docker.

use anyhow::Result;
use async_trait::async_trait;

use crate::service::backend::{
    BuildBackend, BuildHandle, ImageRef, PreviewInfo, StorageGrant,
};
use crate::service::models::Job;

/// A build backend that replays a fixed recorded event stream.
pub struct MockBuildBackend {
    stream: String,
}

impl MockBuildBackend {
    /// Construct with the bundled recorded stream (terminates in a report).
    pub fn new() -> Self {
        Self {
            stream: include_str!("../../tests/fixtures/service-run-sample.jsonl").to_string(),
        }
    }

    /// Construct with a caller-supplied stream — used by tests to exercise
    /// crash paths (e.g. a stream with no terminal report).
    pub fn with_stream(stream: String) -> Self {
        Self { stream }
    }

    /// A minimal valid empty-gzip member (20 bytes) used as the mock artifact
    /// and diagnostics payload.
    pub fn fixture_artifact() -> Vec<u8> {
        vec![
            0x1f, 0x8b, 0x08, 0, 0, 0, 0, 0, 0, 0xff, 0x03, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        ]
    }
}

impl Default for MockBuildBackend {
    fn default() -> Self {
        Self::new()
    }
}

#[async_trait]
impl BuildBackend for MockBuildBackend {
    async fn start_build(
        &self,
        job: &Job,
        _grant: &StorageGrant,
        _proxy_token: &str,
    ) -> Result<BuildHandle> {
        Ok(BuildHandle {
            job_id: job.id.clone(),
        })
    }

    async fn stream_events(&self, _handle: &BuildHandle) -> Result<String> {
        Ok(self.stream.clone())
    }

    async fn build_image(&self, job: &Job) -> Result<ImageRef> {
        Ok(ImageRef {
            reference: format!("mock-image:{}", job.id),
        })
    }

    async fn deploy_preview(&self, job: &Job, _image: &ImageRef) -> Result<PreviewInfo> {
        Ok(PreviewInfo {
            url: format!("http://preview.local/{}", job.id),
        })
    }

    async fn collect_artifact(&self, _handle: &BuildHandle) -> Result<Vec<u8>> {
        Ok(Self::fixture_artifact())
    }

    async fn collect_diagnostics(&self, _handle: &BuildHandle) -> Result<Vec<u8>> {
        Ok(Self::fixture_artifact())
    }

    async fn teardown(&self, _job_id: &str) -> Result<()> {
        Ok(())
    }
}
