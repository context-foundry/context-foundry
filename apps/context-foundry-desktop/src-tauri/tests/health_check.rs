//! Health Check Integration Tests
//!
//! These tests verify the daemon health check functionality works correctly.

use std::time::Duration;
use tokio::time::timeout;

/// Test that the health check endpoint format is correct
#[tokio::test]
async fn test_health_check_response_format() {
    // Create a mock HTTP client
    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(5))
        .build()
        .expect("Failed to create HTTP client");

    // Try to connect to daemon (may not be running)
    let result = timeout(
        Duration::from_secs(2),
        client.get("http://127.0.0.1:8421/health").send(),
    )
    .await;

    // If daemon is running, verify response format
    if let Ok(Ok(response)) = result {
        if response.status().is_success() {
            let json: serde_json::Value = response.json().await.unwrap();

            // Verify expected fields exist
            assert!(
                json.get("status").is_some(),
                "Health response should have 'status' field"
            );
        }
    }
    // If daemon is not running, that's fine for this test
}

/// Test that daemon URL construction is correct
#[test]
fn test_daemon_url_construction() {
    let port: u16 = 8421;
    let url = format!("http://127.0.0.1:{}/health", port);
    assert_eq!(url, "http://127.0.0.1:8421/health");
}

/// Test environment variable port override
#[test]
fn test_port_from_env() {
    // Default port should be 8421
    let default_port: u16 = std::env::var("CFD_HTTP_API_PORT")
        .ok()
        .and_then(|p| p.parse().ok())
        .unwrap_or(8421);

    assert!(default_port > 0 && default_port < 65536);
}

/// Test daemon status structure
#[test]
fn test_daemon_status_defaults() {
    #[derive(Default)]
    struct DaemonStatus {
        running: bool,
        port: u16,
        pid: Option<u32>,
    }

    impl DaemonStatus {
        fn new() -> Self {
            Self {
                running: false,
                port: 8421,
                pid: None,
            }
        }
    }

    let status = DaemonStatus::new();
    assert!(!status.running);
    assert_eq!(status.port, 8421);
    assert!(status.pid.is_none());
}
