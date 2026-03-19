use anyhow::Result;
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::io::{self, BufRead, Write};
use std::path::Path;

use crate::config::Config;
use crate::extensions;
use crate::patterns;

// ─── JSON-RPC 2.0 Types ────────────────────────────────────

/// JSON-RPC 2.0 request (incoming from client)
#[derive(Debug, Deserialize)]
struct JsonRpcRequest {
    #[allow(dead_code)]
    jsonrpc: String,
    #[serde(default)]
    id: Option<Value>,
    method: String,
    #[serde(default)]
    params: Option<Value>,
}

/// JSON-RPC 2.0 response (outgoing to client)
#[derive(Debug, Serialize)]
struct JsonRpcResponse {
    jsonrpc: String,
    id: Value,
    #[serde(skip_serializing_if = "Option::is_none")]
    result: Option<Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    error: Option<JsonRpcError>,
}

/// JSON-RPC 2.0 error object
#[derive(Debug, Serialize)]
struct JsonRpcError {
    code: i64,
    message: String,
}

// ─── MCP Resource Types ─────────────────────────────────────

/// MCP Resource descriptor (returned by resources/list)
#[derive(Debug, Serialize)]
struct Resource {
    uri: String,
    name: String,
    description: String,
    #[serde(rename = "mimeType")]
    mime_type: String,
}

/// MCP ResourceContents (returned by resources/read)
#[derive(Debug, Serialize)]
struct ResourceContents {
    uri: String,
    #[serde(rename = "mimeType")]
    mime_type: String,
    text: String,
}

/// A single entry in the pattern catalog resource
#[derive(Debug, Serialize)]
struct PatternCatalogEntry {
    pattern_id: String,
    title: String,
    severity: Option<String>,
    keywords: Vec<String>,
    frequency: usize,
}

/// A single entry in the extension index resource
#[derive(Debug, Serialize)]
struct ExtensionIndexEntry {
    name: String,
    description: String,
    source: String,
    pattern_count: usize,
}

// ─── Response Constructors ──────────────────────────────────

fn make_success_response(id: Value, result: Value) -> JsonRpcResponse {
    JsonRpcResponse {
        jsonrpc: "2.0".to_string(),
        id,
        result: Some(result),
        error: None,
    }
}

fn make_error_response(id: Value, code: i64, message: &str) -> JsonRpcResponse {
    JsonRpcResponse {
        jsonrpc: "2.0".to_string(),
        id,
        result: None,
        error: Some(JsonRpcError {
            code,
            message: message.to_string(),
        }),
    }
}

// ─── Request Handlers ───────────────────────────────────────

fn handle_initialize(request: &JsonRpcRequest) -> JsonRpcResponse {
    let result = serde_json::json!({
        "protocolVersion": "2024-11-05",
        "capabilities": {
            "resources": {}
        },
        "serverInfo": {
            "name": "context-foundry",
            "version": "0.6.0"
        }
    });
    make_success_response(request.id.clone().unwrap_or(Value::Null), result)
}

fn handle_resources_list(request: &JsonRpcRequest) -> JsonRpcResponse {
    let resources = vec![
        Resource {
            uri: "foundry://patterns/catalog".to_string(),
            name: "Pattern Catalog".to_string(),
            description: "Browseable catalog of all learned patterns with title, severity, keywords, and frequency".to_string(),
            mime_type: "application/json".to_string(),
        },
        Resource {
            uri: "foundry://extensions/index".to_string(),
            name: "Extension Index".to_string(),
            description: "Available extensions with name, domain description, and pattern count".to_string(),
            mime_type: "application/json".to_string(),
        },
    ];

    let result = serde_json::json!({
        "resources": serde_json::to_value(&resources).unwrap_or(Value::Array(vec![]))
    });
    make_success_response(request.id.clone().unwrap_or(Value::Null), result)
}

fn handle_resources_read(
    request: &JsonRpcRequest,
    project_dir: &Path,
    config: &Config,
) -> JsonRpcResponse {
    let id = request.id.clone().unwrap_or(Value::Null);

    let uri = match request
        .params
        .as_ref()
        .and_then(|p| p.get("uri"))
        .and_then(|u| u.as_str())
    {
        Some(u) => u.to_string(),
        None => return make_error_response(id, -32602, "missing uri parameter"),
    };

    let content = match uri.as_str() {
        "foundry://patterns/catalog" => build_pattern_catalog(config),
        "foundry://extensions/index" => build_extension_index(project_dir),
        _ => return make_error_response(id, -32602, &format!("unknown resource URI: {uri}")),
    };

    match content {
        Ok(text) => {
            let contents = ResourceContents {
                uri,
                mime_type: "application/json".to_string(),
                text,
            };
            let result = serde_json::json!({
                "contents": [serde_json::to_value(&contents).unwrap_or(Value::Null)]
            });
            make_success_response(id, result)
        }
        Err(e) => make_error_response(id, -32603, &format!("internal error: {e}")),
    }
}

// ─── Resource Builders ──────────────────────────────────────

fn build_pattern_catalog(config: &Config) -> Result<String> {
    let patterns_dir = patterns::resolve_patterns_dir(&config.patterns_dir);
    let all_patterns = patterns::load_patterns(&patterns_dir);

    let mut entries: Vec<PatternCatalogEntry> = all_patterns
        .into_iter()
        .map(|p| PatternCatalogEntry {
            pattern_id: p.pattern_id,
            title: p.title,
            severity: p.severity,
            keywords: p.keywords,
            frequency: p.frequency,
        })
        .collect();

    // Sort by frequency descending, then title ascending as tiebreaker
    entries.sort_by(|a, b| {
        b.frequency
            .cmp(&a.frequency)
            .then_with(|| a.title.cmp(&b.title))
    });

    Ok(serde_json::to_string_pretty(&entries)?)
}

fn build_extension_index(project_dir: &Path) -> Result<String> {
    let all_extensions = extensions::discover_extensions(project_dir);

    let mut entries: Vec<ExtensionIndexEntry> = all_extensions
        .into_iter()
        .map(|ext| {
            let description = extensions::extract_description(&ext.claude_md_path);
            let pattern_count = extensions::count_extension_patterns(&ext.patterns_dir);
            let source = match ext.source {
                extensions::ExtensionSource::Global => "global".to_string(),
                extensions::ExtensionSource::ProjectLocal => "project-local".to_string(),
            };
            ExtensionIndexEntry {
                name: ext.name,
                description,
                source,
                pattern_count,
            }
        })
        .collect();

    entries.sort_by(|a, b| a.name.cmp(&b.name));

    Ok(serde_json::to_string_pretty(&entries)?)
}

// ─── Main Server Loop ───────────────────────────────────────

/// Run the MCP server over stdin/stdout (JSON-RPC 2.0, one message per line).
pub fn run_mcp_server(project_dir: &Path) -> Result<()> {
    let config = Config::load(project_dir);
    let stdin = io::stdin();
    let mut reader = stdin.lock();
    let stdout = io::stdout();
    let mut writer = stdout.lock();

    let mut line = String::new();
    loop {
        line.clear();
        let bytes_read = reader.read_line(&mut line)?;
        if bytes_read == 0 {
            break; // EOF
        }

        let trimmed = line.trim();
        if trimmed.is_empty() {
            continue;
        }

        let request: JsonRpcRequest = match serde_json::from_str(trimmed) {
            Ok(r) => r,
            Err(_) => {
                let resp = make_error_response(Value::Null, -32700, "Parse error");
                let json = serde_json::to_string(&resp)?;
                writeln!(writer, "{json}")?;
                writer.flush()?;
                continue;
            }
        };

        // Notifications have no id -- no response expected
        if request.id.is_none() {
            continue;
        }

        let response = match request.method.as_str() {
            "initialize" => handle_initialize(&request),
            "resources/list" => handle_resources_list(&request),
            "resources/read" => handle_resources_read(&request, project_dir, &config),
            _ => make_error_response(
                request.id.clone().unwrap_or(Value::Null),
                -32601,
                &format!("Method not found: {}", request.method),
            ),
        };

        let json = serde_json::to_string(&response)?;
        writeln!(writer, "{json}")?;
        writer.flush()?;
    }

    Ok(())
}

// ─── Tests ──────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn mock_request(id: Option<Value>, method: &str, params: Option<Value>) -> JsonRpcRequest {
        JsonRpcRequest {
            jsonrpc: "2.0".to_string(),
            id,
            method: method.to_string(),
            params,
        }
    }

    #[test]
    fn test_handle_initialize() {
        let req = mock_request(Some(Value::from(1)), "initialize", None);
        let resp = handle_initialize(&req);

        assert!(resp.error.is_none());
        let result = resp.result.unwrap();
        assert_eq!(result["protocolVersion"], "2024-11-05");
        assert!(result["capabilities"]["resources"].is_object());
        assert_eq!(result["serverInfo"]["name"], "context-foundry");
        assert_eq!(result["serverInfo"]["version"], "0.6.0");
    }

    #[test]
    fn test_handle_resources_list() {
        let req = mock_request(Some(Value::from(2)), "resources/list", None);
        let resp = handle_resources_list(&req);

        assert!(resp.error.is_none());
        let result = resp.result.unwrap();
        let resources = result["resources"].as_array().unwrap();
        assert_eq!(resources.len(), 2);
        assert_eq!(resources[0]["uri"], "foundry://patterns/catalog");
        assert_eq!(resources[1]["uri"], "foundry://extensions/index");
        assert_eq!(resources[0]["mimeType"], "application/json");
        assert_eq!(resources[1]["mimeType"], "application/json");
    }

    #[test]
    fn test_build_pattern_catalog() {
        let dir = tempfile::tempdir().unwrap();
        let pattern_json = r#"[{
            "pattern_id": "test-1",
            "title": "Test Pattern",
            "severity": "HIGH",
            "keywords": ["rust", "test"],
            "frequency": 5,
            "issue": "Some issue description",
            "solution": {"planner": "plan advice", "reviewer": "review advice"}
        }]"#;
        std::fs::write(dir.path().join("test.json"), pattern_json).unwrap();

        let config = Config {
            patterns_dir: dir.path().to_string_lossy().to_string(),
            ..Config::default()
        };

        let catalog = build_pattern_catalog(&config).unwrap();
        let entries: Vec<Value> = serde_json::from_str(&catalog).unwrap();
        assert_eq!(entries.len(), 1);
        assert_eq!(entries[0]["pattern_id"], "test-1");
        assert_eq!(entries[0]["title"], "Test Pattern");
        assert_eq!(entries[0]["severity"], "HIGH");
        assert_eq!(entries[0]["frequency"], 5);
        let keywords = entries[0]["keywords"].as_array().unwrap();
        assert_eq!(keywords.len(), 2);
        // Must NOT contain solution text
        assert!(entries[0].get("solution").is_none());
        assert!(entries[0].get("issue").is_none());
    }

    #[test]
    fn test_build_pattern_catalog_sorted_by_frequency() {
        let dir = tempfile::tempdir().unwrap();
        let pattern_json = r#"[
            {"pattern_id": "low", "title": "Low Freq", "frequency": 1, "keywords": []},
            {"pattern_id": "high", "title": "High Freq", "frequency": 10, "keywords": []},
            {"pattern_id": "mid", "title": "Mid Freq", "frequency": 5, "keywords": []}
        ]"#;
        std::fs::write(dir.path().join("test.json"), pattern_json).unwrap();

        let config = Config {
            patterns_dir: dir.path().to_string_lossy().to_string(),
            ..Config::default()
        };

        let catalog = build_pattern_catalog(&config).unwrap();
        let entries: Vec<Value> = serde_json::from_str(&catalog).unwrap();
        assert_eq!(entries[0]["pattern_id"], "high");
        assert_eq!(entries[1]["pattern_id"], "mid");
        assert_eq!(entries[2]["pattern_id"], "low");
    }

    #[test]
    fn test_build_extension_index() {
        let dir = tempfile::tempdir().unwrap();
        let ext_dir = dir.path().join("extensions").join("testext");
        std::fs::create_dir_all(&ext_dir).unwrap();
        std::fs::write(
            ext_dir.join("CLAUDE.md"),
            "# Test Extension\n\nA test extension for unit testing.\n",
        )
        .unwrap();

        let index = build_extension_index(dir.path()).unwrap();
        let entries: Vec<Value> = serde_json::from_str(&index).unwrap();
        assert_eq!(entries.len(), 1);
        assert_eq!(entries[0]["name"], "testext");
        assert_eq!(entries[0]["source"], "project-local");
        assert!(entries[0]["description"]
            .as_str()
            .unwrap()
            .contains("test extension"));
    }

    #[test]
    fn test_handle_resources_read_unknown_uri() {
        let dir = tempfile::tempdir().unwrap();
        let config = Config::default();
        let params = serde_json::json!({"uri": "foundry://unknown/thing"});
        let req = mock_request(Some(Value::from(3)), "resources/read", Some(params));
        let resp = handle_resources_read(&req, dir.path(), &config);

        assert!(resp.result.is_none());
        let err = resp.error.unwrap();
        assert_eq!(err.code, -32602);
        assert!(err.message.contains("unknown resource URI"));
    }

    #[test]
    fn test_handle_resources_read_missing_uri() {
        let dir = tempfile::tempdir().unwrap();
        let config = Config::default();
        let req = mock_request(
            Some(Value::from(4)),
            "resources/read",
            Some(serde_json::json!({})),
        );
        let resp = handle_resources_read(&req, dir.path(), &config);

        assert!(resp.result.is_none());
        let err = resp.error.unwrap();
        assert_eq!(err.code, -32602);
        assert!(err.message.contains("missing uri parameter"));
    }

    #[test]
    fn test_make_error_response() {
        let resp = make_error_response(Value::from(99), -32601, "Method not found");
        assert!(resp.result.is_none());
        let err = resp.error.unwrap();
        assert_eq!(err.code, -32601);
        assert_eq!(err.message, "Method not found");
        assert_eq!(resp.id, Value::from(99));
    }

    #[test]
    fn test_make_success_response() {
        let resp = make_success_response(Value::from(1), serde_json::json!({"ok": true}));
        assert!(resp.error.is_none());
        let result = resp.result.unwrap();
        assert_eq!(result["ok"], true);
        assert_eq!(resp.id, Value::from(1));
    }
}
