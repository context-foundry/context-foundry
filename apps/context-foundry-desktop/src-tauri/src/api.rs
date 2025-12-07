//! Daemon API Client Module
//!
//! Provides HTTP client wrapper for communicating with the Context Foundry daemon API.
//! All methods return JSON values that are passed through to the frontend.

use std::time::Duration;
use log::debug;
use thiserror::Error;

/// Default port for the CF Daemon HTTP API
const DEFAULT_API_PORT: u16 = 8421;

/// API client errors
#[derive(Error, Debug)]
pub enum ApiError {
    #[error("HTTP request failed: {0}")]
    HttpError(#[from] reqwest::Error),

    #[error("API returned error status {status}: {message}")]
    ApiError { status: u16, message: String },

    #[error("Failed to parse response: {0}")]
    ParseError(String),
}

/// HTTP client for the daemon API
pub struct DaemonApi {
    client: reqwest::Client,
    base_url: String,
}

impl DaemonApi {
    /// Create a new API client
    pub fn new() -> Self {
        let port = std::env::var("CFD_HTTP_API_PORT")
            .ok()
            .and_then(|p| p.parse().ok())
            .unwrap_or(DEFAULT_API_PORT);

        let client = reqwest::Client::builder()
            .timeout(Duration::from_secs(10))
            .build()
            .expect("Failed to create HTTP client");

        Self {
            client,
            base_url: format!("http://127.0.0.1:{}", port),
        }
    }

    /// Perform GET request and return JSON response
    async fn get(&self, path: &str) -> Result<serde_json::Value, ApiError> {
        let url = format!("{}{}", self.base_url, path);
        debug!("GET {}", url);

        let response = self.client.get(&url).send().await?;
        let status = response.status();

        if !status.is_success() {
            let message = response.text().await.unwrap_or_else(|_| "Unknown error".to_string());
            return Err(ApiError::ApiError {
                status: status.as_u16(),
                message,
            });
        }

        let json: serde_json::Value = response.json().await?;
        Ok(json)
    }

    /// Get health status
    pub async fn health(&self) -> Result<serde_json::Value, ApiError> {
        self.get("/health").await
    }

    /// Get list of jobs with optional filters
    pub async fn get_jobs(
        &self,
        status: Option<String>,
        limit: Option<u32>,
        offset: Option<u32>,
    ) -> Result<serde_json::Value, ApiError> {
        let mut params = Vec::new();

        if let Some(s) = status {
            params.push(format!("status={}", s));
        }
        if let Some(l) = limit {
            params.push(format!("limit={}", l));
        }
        if let Some(o) = offset {
            params.push(format!("offset={}", o));
        }

        let query = if params.is_empty() {
            String::new()
        } else {
            format!("?{}", params.join("&"))
        };

        self.get(&format!("/jobs{}", query)).await
    }

    /// Get a specific job by ID
    pub async fn get_job(&self, job_id: &str) -> Result<serde_json::Value, ApiError> {
        self.get(&format!("/jobs/{}", job_id)).await
    }

    /// Get job tree (phases and tasks hierarchy)
    pub async fn get_job_tree(&self, job_id: &str) -> Result<serde_json::Value, ApiError> {
        self.get(&format!("/jobs/{}/tree", job_id)).await
    }

    /// Get job timeline (chronological events)
    pub async fn get_job_timeline(&self, job_id: &str) -> Result<serde_json::Value, ApiError> {
        self.get(&format!("/jobs/{}/timeline", job_id)).await
    }

    /// Get job phase gates
    pub async fn get_job_gates(&self, job_id: &str) -> Result<serde_json::Value, ApiError> {
        self.get(&format!("/jobs/{}/gates", job_id)).await
    }

    /// Get metrics
    pub async fn get_metrics(&self) -> Result<serde_json::Value, ApiError> {
        self.get("/metrics").await
    }

    /// Get recent events
    pub async fn get_recent_events(&self, event_type: Option<String>) -> Result<serde_json::Value, ApiError> {
        let query = event_type
            .map(|t| format!("?type={}", t))
            .unwrap_or_default();

        self.get(&format!("/events/recent{}", query)).await
    }

    /// Get daemon configuration
    pub async fn get_config(&self) -> Result<serde_json::Value, ApiError> {
        self.get("/config").await
    }

    /// Get agent configuration
    pub async fn get_agents(&self) -> Result<serde_json::Value, ApiError> {
        self.get("/agents").await
    }
}

impl Default for DaemonApi {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_api_client_creation() {
        let api = DaemonApi::new();
        assert!(api.base_url.contains("127.0.0.1"));
    }
}
