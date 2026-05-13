use std::path::{Path, PathBuf};
use std::time::{Duration, Instant};

use anyhow::{anyhow, Context as _, Result};
use tokio::process::Command;
use tokio::time::timeout;

use crate::app::ClickableSurface;
use crate::config::Config;
use crate::llm::summary_cache::{
    compute_key, global as cache_global, insert as cache_insert, invalidate as cache_invalidate,
    lookup as cache_lookup, CacheKeyInput, StageState,
};
use crate::prompts::surface_summary_prompt;
use crate::utils::truncate_str;

// T1.36: `surface_tag` and `surface_label` are populated at every construction
// site and read in tests (surface_label) / by the summary_cache key (surface_tag
// through a separate path). Kept as part of the public outcome contract so
// downstream consumers can pivot on them without having to recompute.
#[derive(Debug, Clone)]
#[allow(dead_code)]
pub struct SummaryOutcome {
    pub surface_tag: String,
    pub stage: String,
    pub surface_label: String,
    pub state: StageState,
    pub summary: String,
    pub cache_hit: bool,
    pub model: String,
    pub provider: String,
    pub latency_ms: u128,
    pub error: Option<String>,
}

pub fn read_artifact_excerpt(path: &Path, max_bytes: usize) -> Option<String> {
    let bytes = std::fs::read(path).ok()?;
    if bytes.len() <= max_bytes {
        Some(String::from_utf8_lossy(&bytes).into_owned())
    } else {
        let tail = &bytes[bytes.len() - max_bytes..];
        Some(format!(
            "...truncated to {} bytes...\n{}",
            max_bytes,
            String::from_utf8_lossy(tail)
        ))
    }
}

pub async fn summarize_surface(
    surface: ClickableSurface,
    state: StageState,
    artifacts: Vec<PathBuf>,
    log_tail: Option<String>,
    config: &Config,
    force_refresh: bool,
) -> SummaryOutcome {
    let started = Instant::now();
    let tag = surface.tag();
    let label = surface.label();
    // For pipeline surfaces, the canonical id is the stage id; for everything
    // else the tag itself is stable enough to act as the cache "stage" string.
    let stage_str = match &surface {
        ClickableSurface::PipelineStage(sid) => sid.clone(),
        _ => tag.to_string(),
    };

    let key_input = CacheKeyInput {
        surface_tag: tag,
        stage: &stage_str,
        state: &state,
        artifacts: &artifacts,
    };
    let key = compute_key(&key_input);
    let cache = cache_global();

    if !force_refresh {
        if let Some(cached) = cache_lookup(cache, &key) {
            return SummaryOutcome {
                surface_tag: tag.to_string(),
                stage: stage_str.clone(),
                surface_label: label,
                state,
                summary: cached,
                cache_hit: true,
                model: String::new(),
                provider: String::new(),
                latency_ms: started.elapsed().as_millis(),
                error: None,
            };
        }
    } else {
        cache_invalidate(cache, &key);
    }

    let (provider, model) = config.active_routing_for_stage("summary");

    let mut excerpts: Vec<(String, String)> = Vec::new();
    for path in &artifacts {
        if let Some(body) = read_artifact_excerpt(path, 4096) {
            excerpts.push((path.display().to_string(), body));
        }
    }

    let prompt = surface_summary_prompt(
        &surface,
        &state,
        &excerpts,
        log_tail.as_deref().unwrap_or(""),
    );

    let result = invoke_haiku(&provider, &model, &prompt, config.summary_timeout_secs).await;

    match result {
        Ok(text) => {
            let trimmed = truncate_str(text.trim(), 4096).to_string();
            cache_insert(cache, key, trimmed.clone());
            SummaryOutcome {
                surface_tag: tag.to_string(),
                stage: stage_str,
                surface_label: label,
                state,
                summary: trimmed,
                cache_hit: false,
                model,
                provider,
                latency_ms: started.elapsed().as_millis(),
                error: None,
            }
        }
        Err(e) => {
            let fallback = format!(
                "summary unavailable -- check the log directly at .buildloop/logs/{}.jsonl ({})",
                stage_str, e
            );
            SummaryOutcome {
                surface_tag: tag.to_string(),
                stage: stage_str,
                surface_label: label,
                state,
                summary: fallback,
                cache_hit: false,
                model,
                provider,
                latency_ms: started.elapsed().as_millis(),
                error: Some(e.to_string()),
            }
        }
    }
}

async fn invoke_haiku(
    provider: &str,
    model: &str,
    prompt: &str,
    timeout_secs: u64,
) -> Result<String> {
    let timeout_dur = Duration::from_secs(timeout_secs);
    match provider {
        "claude" => {
            let mut cmd = Command::new("claude");
            cmd.arg("-p").arg(prompt);
            if !model.trim().is_empty() && model != "claude" {
                cmd.arg("--model").arg(model);
            }
            cmd.arg("--dangerously-skip-permissions");
            cmd.arg("--output-format").arg("text");
            cmd.stdin(std::process::Stdio::null())
                .stdout(std::process::Stdio::piped())
                .stderr(std::process::Stdio::piped())
                .env("CLAUDECODE", "");
            cmd.kill_on_drop(true);

            let fut = cmd.output();
            let output = timeout(timeout_dur, fut)
                .await
                .with_context(|| format!("summary timed out after {}s", timeout_secs))??;
            if !output.status.success() {
                return Err(anyhow!(
                    "claude exit {}: {}",
                    output.status,
                    String::from_utf8_lossy(&output.stderr).trim()
                ));
            }
            Ok(String::from_utf8_lossy(&output.stdout).into_owned())
        }
        _ => Err(anyhow!(
            "provider {} not supported for stage summaries",
            provider
        )),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn summarize_stage_returns_fallback_when_provider_missing() {
        let cfg = Config {
            summary_provider: "nonexistent".into(),
            summary_model: "x".into(),
            ..Default::default()
        };

        let outcome = summarize_surface(
            ClickableSurface::PipelineStage("plan-review".to_string()),
            StageState::Running,
            vec![],
            None,
            &cfg,
            false,
        )
        .await;

        assert!(outcome.error.is_some(), "error must be set on bad provider");
        assert!(
            outcome.summary.starts_with("summary unavailable"),
            "fallback string must begin with 'summary unavailable', got: {}",
            outcome.summary
        );
        assert!(!outcome.cache_hit, "cache_hit must be false on miss");
        assert_eq!(outcome.surface_label, "plan-review");
    }
}
