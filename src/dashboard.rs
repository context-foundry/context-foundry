use std::path::{Path, PathBuf};

use anyhow::{Context, Result};
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tokio::net::TcpListener;

use serde_json::json;

use crate::stats;

const DASHBOARD_HTML: &str = include_str!("dashboard.html");

pub async fn run_dashboard(port: u16, project_dir: &Path) -> Result<()> {
    println!("Dashboard running at http://127.0.0.1:{port}");
    println!("Press Ctrl+C to stop.");

    let listener = TcpListener::bind(format!("127.0.0.1:{}", port))
        .await
        .context("failed to bind dashboard port")?;

    let project_dir = project_dir.to_path_buf();

    loop {
        match listener.accept().await {
            Ok((stream, _addr)) => {
                let dir = project_dir.clone();
                tokio::spawn(async move {
                    handle_connection(stream, dir).await;
                });
            }
            Err(e) => {
                eprintln!("dashboard: accept error: {e}");
            }
        }
    }
}

async fn handle_connection(mut stream: tokio::net::TcpStream, project_dir: PathBuf) {
    let mut buf = [0u8; 4096];
    let n = match stream.read(&mut buf).await {
        Ok(0) | Err(_) => return,
        Ok(n) => n,
    };

    let request = String::from_utf8_lossy(&buf[..n]);
    let mut parts = request.split_whitespace();
    let method = parts.next().unwrap_or("");
    let path = parts.next().unwrap_or("");

    let (status, content_type, body) = if method == "GET" && path == "/" {
        (
            "200 OK",
            "text/html; charset=utf-8",
            DASHBOARD_HTML.to_string(),
        )
    } else if method == "GET" && (path == "/api/stats" || path.starts_with("/api/stats?")) {
        let path_owned = path.to_string();
        let dir_clone = project_dir.clone();
        match tokio::task::spawn_blocking(move || handle_api_stats(&path_owned, &dir_clone)).await {
            Ok(Ok(json)) => ("200 OK", "application/json", json),
            Ok(Err(e)) => {
                let msg = serde_json::to_string(&json!({"error": e.to_string()}))
                    .unwrap_or_else(|_| r#"{"error":"internal error"}"#.to_string());
                ("500 Internal Server Error", "application/json", msg)
            }
            Err(e) => {
                let msg = serde_json::to_string(&json!({"error": format!("task panicked: {}", e)}))
                    .unwrap_or_else(|_| r#"{"error":"internal error"}"#.to_string());
                ("500 Internal Server Error", "application/json", msg)
            }
        }
    } else {
        ("404 Not Found", "text/plain", "Not Found".to_string())
    };

    let body_bytes = body.as_bytes();
    let response = format!(
        "HTTP/1.1 {status}\r\nContent-Type: {content_type}\r\nContent-Length: {}\r\nConnection: close\r\nAccess-Control-Allow-Origin: *\r\n\r\n",
        body_bytes.len()
    );

    if stream.write_all(response.as_bytes()).await.is_err() {
        return;
    }
    if stream.write_all(body_bytes).await.is_err() {
        return;
    }
    let _ = stream.flush().await;
}

fn handle_api_stats(path: &str, project_dir: &Path) -> Result<String> {
    let days = path
        .split_once('?')
        .and_then(|(_, query)| {
            query
                .split('&')
                .find_map(|param| param.strip_prefix("days="))
        })
        .and_then(|v| v.parse::<u32>().ok())
        .unwrap_or(7);

    let use_global = path
        .split_once('?')
        .and_then(|(_, query)| {
            query
                .split('&')
                .find_map(|param| param.strip_prefix("project="))
        })
        .map(|v| v == "global")
        .unwrap_or(false);

    let obs_dir = stats::observatory_dir()?;
    let canonical = dunce::canonicalize(project_dir).unwrap_or_else(|_| project_dir.to_path_buf());
    let (project_filter, project_str) = if use_global {
        (None, None)
    } else {
        (
            Some(canonical.as_path()),
            Some(canonical.display().to_string()),
        )
    };
    let (events, skipped) = stats::load_events(&obs_dir, days, project_filter)?;
    let report = stats::compute_stats(&events, skipped, days, project_str.as_deref(), true);
    serde_json::to_string(&report).context("failed to serialize stats")
}
