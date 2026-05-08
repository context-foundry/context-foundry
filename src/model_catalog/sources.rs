use super::ModelEntry;
use anyhow::{Context, Result};
use chrono::Utc;
use reqwest::Client;
use serde::Deserialize;
use std::time::Duration;

const HTTP_TIMEOUT_SECS: u64 = 15;
const USER_AGENT: &str = concat!("foundry/", env!("CARGO_PKG_VERSION"));
const ANTHROPIC_DEFAULT_URL: &str = "https://api.anthropic.com/v1/models";
const OPENAI_DEFAULT_URL: &str = "https://api.openai.com/v1/models";

pub fn build_client() -> Result<Client> {
    Client::builder()
        .user_agent(USER_AGENT)
        .timeout(Duration::from_secs(HTTP_TIMEOUT_SECS))
        .build()
        .context("build reqwest client")
}

pub async fn fetch_anthropic(
    client: &Client,
    override_url: Option<&String>,
) -> Result<Vec<ModelEntry>> {
    let api_key = match std::env::var("ANTHROPIC_API_KEY") {
        Ok(k) if !k.is_empty() => k,
        _ => return Ok(Vec::new()),
    };
    let url = override_url
        .cloned()
        .unwrap_or_else(|| ANTHROPIC_DEFAULT_URL.to_string());
    let resp = client
        .get(&url)
        .header("x-api-key", &api_key)
        .header("anthropic-version", "2023-06-01")
        .send()
        .await
        .with_context(|| format!("GET {}", url))?;
    if !resp.status().is_success() {
        return Err(anyhow::anyhow!(
            "anthropic GET {}: HTTP {}",
            url,
            resp.status()
        ));
    }

    #[derive(Deserialize)]
    struct AnthropicListResp {
        data: Vec<AnthropicModel>,
    }
    #[derive(Deserialize)]
    struct AnthropicModel {
        id: String,
        #[serde(default)]
        display_name: Option<String>,
    }

    let parsed: AnthropicListResp = resp
        .json()
        .await
        .with_context(|| format!("parse anthropic response from {}", url))?;
    let now = Utc::now();
    let entries = parsed
        .data
        .into_iter()
        .map(|m| {
            let (input_price, cached, output_price) = default_anthropic_pricing(&m.id);
            let display = m.display_name.clone().unwrap_or_else(|| m.id.clone());
            ModelEntry {
                provider: "claude".into(),
                model_id: m.id.clone(),
                display_name: display,
                context_window: 200000,
                input_price_per_mtok: input_price,
                cached_input_price_per_mtok: cached,
                output_price_per_mtok: output_price,
                deprecated_at: None,
                released_at: None,
                source_url: url.clone(),
                source_fetched_at: now,
                recommended: false,
                group: default_anthropic_group(&m.id).to_string(),
            }
        })
        .collect();
    Ok(entries)
}

fn default_anthropic_pricing(model_id: &str) -> (f64, Option<f64>, f64) {
    if model_id.starts_with("claude-opus") {
        (15.0, Some(1.5), 75.0)
    } else if model_id.starts_with("claude-sonnet") {
        (3.0, Some(0.3), 15.0)
    } else if model_id.starts_with("claude-haiku") {
        (1.0, Some(0.1), 5.0)
    } else {
        (0.0, None, 0.0)
    }
}

fn default_anthropic_group(model_id: &str) -> &'static str {
    let _ = model_id;
    "Claude"
}

pub async fn fetch_openai(
    client: &Client,
    override_url: Option<&String>,
) -> Result<Vec<ModelEntry>> {
    let api_key = match std::env::var("OPENAI_API_KEY") {
        Ok(k) if !k.is_empty() => k,
        _ => return Ok(Vec::new()),
    };
    let url = override_url
        .cloned()
        .unwrap_or_else(|| OPENAI_DEFAULT_URL.to_string());
    let resp = client
        .get(&url)
        .bearer_auth(&api_key)
        .send()
        .await
        .with_context(|| format!("GET {}", url))?;
    if !resp.status().is_success() {
        return Err(anyhow::anyhow!(
            "openai GET {}: HTTP {}",
            url,
            resp.status()
        ));
    }

    #[derive(Deserialize)]
    struct OAIListResp {
        data: Vec<OAIModel>,
    }
    #[derive(Deserialize)]
    struct OAIModel {
        id: String,
    }

    let parsed: OAIListResp = resp.json().await.context("parse openai response")?;
    let now = Utc::now();
    let entries = parsed
        .data
        .into_iter()
        .filter(|m| {
            m.id.starts_with("gpt-5")
                || m.id.starts_with("gpt-4")
                || m.id.starts_with("o1")
                || m.id.starts_with("o3")
        })
        .map(|m| {
            let (input_price, cached, output_price) = default_openai_pricing(&m.id);
            let display = m.id.clone();
            ModelEntry {
                provider: "codex".into(),
                model_id: m.id.clone(),
                display_name: display,
                context_window: 200000,
                input_price_per_mtok: input_price,
                cached_input_price_per_mtok: cached,
                output_price_per_mtok: output_price,
                deprecated_at: None,
                released_at: None,
                source_url: url.clone(),
                source_fetched_at: now,
                recommended: false,
                group: "Codex".into(),
            }
        })
        .collect();
    Ok(entries)
}

fn default_openai_pricing(model_id: &str) -> (f64, Option<f64>, f64) {
    if model_id.starts_with("gpt-5") {
        (5.0, None, 15.0)
    } else if model_id.starts_with("gpt-4o") {
        (2.5, None, 10.0)
    } else if model_id.starts_with("gpt-4") {
        (10.0, None, 30.0)
    } else if model_id.starts_with("o3") || model_id.starts_with("o1") {
        (15.0, None, 60.0)
    } else {
        (0.0, None, 0.0)
    }
}

pub async fn fetch_opencode() -> Result<Vec<ModelEntry>> {
    let out = tokio::task::spawn_blocking(|| {
        std::process::Command::new("opencode")
            .args(["models", "list"])
            .output()
    })
    .await
    .context("spawn opencode")?;
    let output = match out {
        Ok(o) => o,
        Err(_) => return Ok(Vec::new()),
    };
    if !output.status.success() {
        return Ok(Vec::new());
    }
    let text = String::from_utf8_lossy(&output.stdout);
    let now = Utc::now();
    let mut entries: Vec<ModelEntry> = Vec::new();
    for line in text.lines() {
        let trimmed = line.trim();
        if trimmed.is_empty() || trimmed.starts_with('#') || trimmed.starts_with("--") {
            continue;
        }
        let id = match trimmed.split_whitespace().next() {
            Some(s) => s.to_string(),
            None => continue,
        };
        let group = if id.starts_with("lmstudio/") {
            "OpenCode -- LM Studio"
        } else if id.starts_with("ollama/") {
            "OpenCode -- Ollama"
        } else {
            "OpenCode"
        };
        entries.push(ModelEntry {
            provider: "opencode".into(),
            model_id: id.clone(),
            display_name: id.clone(),
            context_window: 0,
            input_price_per_mtok: 0.0,
            cached_input_price_per_mtok: None,
            output_price_per_mtok: 0.0,
            deprecated_at: None,
            released_at: None,
            source_url: "opencode".into(),
            source_fetched_at: now,
            recommended: false,
            group: group.to_string(),
        });
    }
    Ok(entries)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serial_test::serial;

    #[test]
    fn test_default_anthropic_pricing_opus() {
        let (i, c, o) = default_anthropic_pricing("claude-opus-4-7");
        assert_eq!(i, 15.0);
        assert_eq!(c, Some(1.5));
        assert_eq!(o, 75.0);
    }

    #[test]
    fn test_default_anthropic_pricing_unknown() {
        let (i, c, o) = default_anthropic_pricing("unknown-model");
        assert_eq!(i, 0.0);
        assert_eq!(c, None);
        assert_eq!(o, 0.0);
    }

    #[test]
    fn test_default_openai_pricing_gpt5() {
        let (i, c, o) = default_openai_pricing("gpt-5.4");
        assert_eq!(i, 5.0);
        assert_eq!(c, None);
        assert_eq!(o, 15.0);
    }

    #[tokio::test]
    #[serial]
    async fn test_fetch_anthropic_empty_without_key() {
        std::env::remove_var("ANTHROPIC_API_KEY");
        let client = build_client().unwrap();
        let r = fetch_anthropic(&client, None).await.unwrap();
        assert!(r.is_empty());
    }

    #[tokio::test]
    #[serial]
    async fn test_fetch_openai_empty_without_key() {
        std::env::remove_var("OPENAI_API_KEY");
        let client = build_client().unwrap();
        let r = fetch_openai(&client, None).await.unwrap();
        assert!(r.is_empty());
    }
}
