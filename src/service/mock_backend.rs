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
    fail_image: bool,
    start_delay_ms: u64,
}

impl MockBuildBackend {
    /// Construct with the bundled recorded stream (terminates in a report).
    pub fn new() -> Self {
        Self {
            stream: include_str!("../../tests/fixtures/service-run-sample.jsonl").to_string(),
            fail_image: false,
            start_delay_ms: 0,
        }
    }

    /// Construct with a caller-supplied stream — used by tests to exercise
    /// crash paths (e.g. a stream with no terminal report).
    pub fn with_stream(stream: String) -> Self {
        Self {
            stream,
            fail_image: false,
            start_delay_ms: 0,
        }
    }

    /// Construct a backend whose build stream succeeds but whose `build_image`
    /// fails — exercises the `preview_deploy_failed` path while keeping the
    /// source artifact downloadable.
    pub fn with_failing_image() -> Self {
        Self {
            stream: include_str!("../../tests/fixtures/service-run-sample.jsonl").to_string(),
            fail_image: true,
            start_delay_ms: 0,
        }
    }

    /// Construct a backend whose `start_build` sleeps `delay_ms` before
    /// returning — used to exercise the wall-clock build timeout.
    pub fn with_slow_start(delay_ms: u64) -> Self {
        Self {
            stream: include_str!("../../tests/fixtures/service-run-sample.jsonl").to_string(),
            fail_image: false,
            start_delay_ms: delay_ms,
        }
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
        if self.start_delay_ms > 0 {
            tokio::time::sleep(std::time::Duration::from_millis(self.start_delay_ms)).await;
        }
        Ok(BuildHandle {
            job_id: job.id.clone(),
        })
    }

    async fn stream_events(&self, _handle: &BuildHandle) -> Result<String> {
        Ok(self.stream.clone())
    }

    async fn build_image(&self, job: &Job) -> Result<ImageRef> {
        if self.fail_image {
            anyhow::bail!("mock image build failed");
        }
        Ok(ImageRef {
            reference: format!("mock-image:{}", job.id),
            dockerfile_source: "project".to_string(),
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
