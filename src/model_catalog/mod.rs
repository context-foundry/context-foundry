use anyhow::{Context, Result};
use chrono::{DateTime, Duration, Utc};
use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet};
use std::path::PathBuf;
use tokio::sync::mpsc;

pub mod sources;

pub const SCHEMA_VERSION: u32 = 1;
const BASELINE_JSON: &str = include_str!("baseline.json");
const REFRESH_AGE_THRESHOLD_HOURS: i64 = 24;
const REFRESH_HARD_CEILING_HOURS: i64 = 6;
const STALE_WARNING_DAYS: i64 = 14;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ModelEntry {
    pub provider: String,
    pub model_id: String,
    pub display_name: String,
    #[serde(default)]
    pub context_window: u32,
    #[serde(default)]
    pub input_price_per_mtok: f64,
    #[serde(default)]
    pub cached_input_price_per_mtok: Option<f64>,
    #[serde(default)]
    pub output_price_per_mtok: f64,
    #[serde(default)]
    pub deprecated_at: Option<DateTime<Utc>>,
    #[serde(default)]
    pub released_at: Option<DateTime<Utc>>,
    #[serde(default)]
    pub source_url: String,
    pub source_fetched_at: DateTime<Utc>,
    #[serde(default)]
    pub recommended: bool,
    #[serde(default)]
    pub group: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ModelCatalog {
    pub schema_version: u32,
    pub source_fetched_at: DateTime<Utc>,
    pub entries: Vec<ModelEntry>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum RefreshMode {
    Auto,
    Force,
    Skip,
}

pub fn baseline_catalog() -> ModelCatalog {
    serde_json::from_str::<ModelCatalog>(BASELINE_JSON)
        .expect("baseline.json must parse -- this is a build-time invariant")
}

pub fn catalog_path() -> Option<PathBuf> {
    Some(
        crate::utils::home_dir()?
            .join(".foundry")
            .join("model_catalog.json"),
    )
}

pub fn load_catalog() -> ModelCatalog {
    let path = match catalog_path() {
        Some(p) => p,
        None => return baseline_catalog(),
    };
    if !path.exists() {
        return baseline_catalog();
    }
    let content = match std::fs::read_to_string(&path) {
        Ok(c) => c,
        Err(_) => return baseline_catalog(),
    };
    let parsed: ModelCatalog = match serde_json::from_str(&content) {
        Ok(c) => c,
        Err(_) => {
            eprintln!(
                "warning: failed to parse {} -- using baseline",
                path.display()
            );
            return baseline_catalog();
        }
    };
    if parsed.schema_version != SCHEMA_VERSION {
        eprintln!(
            "warning: catalog at {} has schema_version {} (expected {}) -- using baseline",
            path.display(),
            parsed.schema_version,
            SCHEMA_VERSION
        );
        return baseline_catalog();
    }
    parsed
}

pub fn save_catalog(catalog: &ModelCatalog) -> Result<PathBuf> {
    let path = catalog_path().context("HOME not set -- cannot resolve catalog path")?;
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)
            .with_context(|| format!("create_dir_all {}", parent.display()))?;
    }
    let json = serde_json::to_string_pretty(catalog).context("serialize catalog")?;
    crate::utils::atomic_write_file(&path, json.as_bytes())
        .with_context(|| format!("atomic write {}", path.display()))?;
    Ok(path)
}

pub fn refresh_mode_from_env() -> RefreshMode {
    match std::env::var("FOUNDRY_MODEL_REFRESH").ok().as_deref() {
        Some("force") => RefreshMode::Force,
        Some("skip") => RefreshMode::Skip,
        _ => RefreshMode::Auto,
    }
}

pub fn refresh_policy_should_run(
    catalog: &ModelCatalog,
    mode: RefreshMode,
    now: DateTime<Utc>,
) -> bool {
    match mode {
        RefreshMode::Skip => false,
        RefreshMode::Force => {
            (now - catalog.source_fetched_at) >= Duration::hours(REFRESH_HARD_CEILING_HOURS)
        }
        RefreshMode::Auto => {
            (now - catalog.source_fetched_at) >= Duration::hours(REFRESH_AGE_THRESHOLD_HOURS)
        }
    }
}

pub fn staleness_label(now: DateTime<Utc>, fetched_at: DateTime<Utc>) -> (String, bool) {
    let delta = now - fetched_at;
    if delta.num_seconds() < 0 {
        return ("(updated just now)".to_string(), false);
    }
    if fetched_at.timestamp() == 0 {
        return ("(baseline)".to_string(), false);
    }
    if delta < Duration::hours(1) {
        return ("(updated <1h ago)".to_string(), false);
    }
    if delta < Duration::days(1) {
        return (format!("(updated {}h ago)", delta.num_hours()), false);
    }
    let days = delta.num_days();
    if days > STALE_WARNING_DAYS {
        return (format!("(stale: {}d)", days), true);
    }
    (format!("(updated {}d ago)", days), false)
}

pub fn diff_new_models<'a>(
    prev: &'a ModelCatalog,
    next: &'a ModelCatalog,
) -> Vec<&'a ModelEntry> {
    let prev_keys: HashSet<(String, String)> = prev
        .entries
        .iter()
        .map(|e| (e.provider.clone(), e.model_id.clone()))
        .collect();
    next.entries
        .iter()
        .filter(|e| !prev_keys.contains(&(e.provider.clone(), e.model_id.clone())))
        .collect()
}

pub fn diff_newly_deprecated<'a>(
    prev: &'a ModelCatalog,
    next: &'a ModelCatalog,
) -> Vec<&'a ModelEntry> {
    let prev_dep: HashMap<(String, String), bool> = prev
        .entries
        .iter()
        .map(|e| {
            (
                (e.provider.clone(), e.model_id.clone()),
                e.deprecated_at.is_some(),
            )
        })
        .collect();
    next.entries
        .iter()
        .filter(|e| {
            e.deprecated_at.is_some()
                && !prev_dep
                    .get(&(e.provider.clone(), e.model_id.clone()))
                    .copied()
                    .unwrap_or(false)
        })
        .collect()
}

pub fn merge_catalogs(
    prev: ModelCatalog,
    fetched: Vec<ModelEntry>,
    now: DateTime<Utc>,
) -> ModelCatalog {
    let mut by_key: HashMap<(String, String), ModelEntry> = prev
        .entries
        .into_iter()
        .map(|e| ((e.provider.clone(), e.model_id.clone()), e))
        .collect();
    for mut e in fetched {
        let key = (e.provider.clone(), e.model_id.clone());
        // Preserve the Foundry-internal `recommended` flag from the existing entry;
        // live API responses carry no recommendation signal and always deliver false.
        if !e.recommended {
            if let Some(prev_entry) = by_key.get(&key) {
                e.recommended = prev_entry.recommended;
            }
        }
        by_key.insert(key, e);
    }
    let mut entries: Vec<ModelEntry> = by_key.into_values().collect();
    entries.sort_by(|a, b| {
        a.provider
            .cmp(&b.provider)
            .then_with(|| a.model_id.cmp(&b.model_id))
    });
    ModelCatalog {
        schema_version: SCHEMA_VERSION,
        source_fetched_at: now,
        entries,
    }
}

pub async fn refresh_catalog_async(
    prev: ModelCatalog,
    url_overrides: HashMap<String, String>,
    log_tx: Option<mpsc::UnboundedSender<String>>,
) -> Result<ModelCatalog> {
    let client = sources::build_client()?;
    let (anth, oai, oc) = tokio::join!(
        sources::fetch_anthropic(&client, url_overrides.get("anthropic")),
        sources::fetch_openai(&client, url_overrides.get("openai")),
        sources::fetch_opencode(),
    );

    let mut fetched: Vec<ModelEntry> = Vec::new();
    let mut any_error = false;

    for (name, result) in [
        ("anthropic", anth),
        ("openai", oai),
        ("opencode", oc),
    ] {
        match result {
            Ok(v) => {
                fetched.extend(v);
            }
            Err(e) => {
                any_error = true;
                if let Some(tx) = log_tx.as_ref() {
                    let _ = tx.send(format!("[catalog] {} fetch failed: {}", name, e));
                }
            }
        }
    }

    if fetched.is_empty() {
        if any_error {
            return Err(anyhow::anyhow!("all providers failed"));
        }
        return Err(anyhow::anyhow!(
            "no fetched entries (no API keys configured?)"
        ));
    }

    let now = Utc::now();
    let prev_clone = prev.clone();
    let next = merge_catalogs(prev, fetched, now);
    let path = save_catalog(&next).context("save catalog")?;

    if let Some(tx) = log_tx.as_ref() {
        for entry in diff_new_models(&prev_clone, &next) {
            let _ = tx.send(format!(
                "[catalog] new model available: {} (input ${:.2} / output ${:.2} per Mtok)",
                entry.model_id, entry.input_price_per_mtok, entry.output_price_per_mtok
            ));
        }
        for entry in diff_newly_deprecated(&prev_clone, &next) {
            let _ = tx.send(format!(
                "[catalog] deprecated: {} (sunset {})",
                entry.model_id,
                entry
                    .deprecated_at
                    .map(|d| d.format("%Y-%m-%d").to_string())
                    .unwrap_or_else(|| "unknown".into())
            ));
        }
        let _ = tx.send(format!("[catalog] refreshed -> {}", path.display()));
    }

    Ok(next)
}

#[allow(dead_code)]
pub fn lookup<'a>(
    catalog: &'a ModelCatalog,
    provider: &str,
    model_id: &str,
) -> Option<&'a ModelEntry> {
    catalog
        .entries
        .iter()
        .find(|e| e.provider == provider && e.model_id == model_id)
}

#[cfg(test)]
mod tests {
    use super::*;
    use serial_test::serial;
    use tempfile::TempDir;

    fn set_home(td: &TempDir) {
        std::env::set_var("HOME", td.path());
    }

    #[test]
    fn test_baseline_parses() {
        let cat = baseline_catalog();
        assert_eq!(cat.schema_version, 1);
        assert!(cat.entries.len() >= 8, "baseline must have >=8 entries");
    }

    #[test]
    #[serial]
    fn test_load_falls_back_when_missing() {
        let td = TempDir::new().unwrap();
        set_home(&td);
        let cat = load_catalog();
        assert_eq!(cat.entries.len(), baseline_catalog().entries.len());
    }

    #[test]
    #[serial]
    fn test_load_falls_back_on_bad_json() {
        let td = TempDir::new().unwrap();
        set_home(&td);
        let dir = td.path().join(".foundry");
        std::fs::create_dir_all(&dir).unwrap();
        std::fs::write(dir.join("model_catalog.json"), "not json").unwrap();
        let cat = load_catalog();
        assert_eq!(cat.entries.len(), baseline_catalog().entries.len());
    }

    #[test]
    #[serial]
    fn test_save_and_reload_roundtrip() {
        let td = TempDir::new().unwrap();
        set_home(&td);
        let cat = baseline_catalog();
        save_catalog(&cat).unwrap();
        let loaded = load_catalog();
        assert_eq!(loaded.entries.len(), cat.entries.len());
    }

    #[test]
    fn test_refresh_policy_skip() {
        let cat = baseline_catalog();
        assert!(!refresh_policy_should_run(
            &cat,
            RefreshMode::Skip,
            Utc::now()
        ));
    }

    #[test]
    fn test_refresh_policy_auto_fresh() {
        let now = Utc::now();
        let mut cat = baseline_catalog();
        cat.source_fetched_at = now - Duration::hours(1);
        assert!(!refresh_policy_should_run(&cat, RefreshMode::Auto, now));
        cat.source_fetched_at = now - Duration::hours(25);
        assert!(refresh_policy_should_run(&cat, RefreshMode::Auto, now));
    }

    #[test]
    fn test_refresh_policy_force_under_ceiling() {
        let now = Utc::now();
        let mut cat = baseline_catalog();
        cat.source_fetched_at = now - Duration::hours(1);
        assert!(!refresh_policy_should_run(&cat, RefreshMode::Force, now));
        cat.source_fetched_at = now - Duration::hours(7);
        assert!(refresh_policy_should_run(&cat, RefreshMode::Force, now));
    }

    #[test]
    fn test_staleness_label_warning_above_14d() {
        let now = Utc::now();
        let fetched = now - Duration::days(15);
        let (label, warn) = staleness_label(now, fetched);
        assert!(warn);
        assert!(label.starts_with("(stale:"));
    }

    #[test]
    fn test_diff_new_models() {
        let prev = baseline_catalog();
        let mut next = prev.clone();
        next.entries.push(ModelEntry {
            provider: "claude".into(),
            model_id: "claude-opus-4-9-novel".into(),
            display_name: "Claude Opus 4.9".into(),
            context_window: 200000,
            input_price_per_mtok: 15.0,
            cached_input_price_per_mtok: Some(1.5),
            output_price_per_mtok: 75.0,
            deprecated_at: None,
            released_at: None,
            source_url: "test".into(),
            source_fetched_at: Utc::now(),
            recommended: false,
            group: "Claude".into(),
        });
        let diffs = diff_new_models(&prev, &next);
        assert_eq!(diffs.len(), 1);
        assert_eq!(diffs[0].model_id, "claude-opus-4-9-novel");
    }

    #[test]
    fn test_diff_newly_deprecated() {
        let mut prev = baseline_catalog();
        let mut next = prev.clone();
        // pretend opus was deprecated in next but not prev
        let dep_time = Utc::now();
        for e in next.entries.iter_mut() {
            if e.model_id == "claude-opus-4-7" {
                e.deprecated_at = Some(dep_time);
            }
        }
        let diffs = diff_newly_deprecated(&prev, &next);
        assert_eq!(diffs.len(), 1);
        assert_eq!(diffs[0].model_id, "claude-opus-4-7");

        // mark prev also deprecated -> no diff
        for e in prev.entries.iter_mut() {
            if e.model_id == "claude-opus-4-7" {
                e.deprecated_at = Some(dep_time);
            }
        }
        let diffs = diff_newly_deprecated(&prev, &next);
        assert!(diffs.is_empty());
    }

    #[test]
    fn test_merge_preserves_other_providers() {
        let prev = baseline_catalog();
        let prev_openai_count = prev
            .entries
            .iter()
            .filter(|e| e.provider == "codex")
            .count();
        // fetched contains only one anthropic update
        let fetched = vec![ModelEntry {
            provider: "claude".into(),
            model_id: "claude-opus-4-7".into(),
            display_name: "Claude Opus 4.7 updated".into(),
            context_window: 200000,
            input_price_per_mtok: 16.0,
            cached_input_price_per_mtok: Some(1.6),
            output_price_per_mtok: 80.0,
            deprecated_at: None,
            released_at: None,
            source_url: "test".into(),
            source_fetched_at: Utc::now(),
            recommended: true,
            group: "Claude".into(),
        }];
        let merged = merge_catalogs(prev, fetched, Utc::now());
        let merged_openai = merged
            .entries
            .iter()
            .filter(|e| e.provider == "codex")
            .count();
        assert_eq!(merged_openai, prev_openai_count);
        // updated entry should reflect new price
        let opus = merged
            .entries
            .iter()
            .find(|e| e.provider == "claude" && e.model_id == "claude-opus-4-7")
            .unwrap();
        assert_eq!(opus.input_price_per_mtok, 16.0);
    }

    #[test]
    fn test_merge_preserves_recommended_from_prev_when_fetched_is_false() {
        let prev = baseline_catalog();
        // baseline has claude-opus-4-7 recommended=true
        assert!(prev.entries.iter().any(|e| e.model_id == "claude-opus-4-7" && e.recommended));
        // fetched returns recommended=false (as live API would)
        let fetched = vec![ModelEntry {
            provider: "claude".into(),
            model_id: "claude-opus-4-7".into(),
            display_name: "Claude Opus 4.7".into(),
            context_window: 200000,
            input_price_per_mtok: 15.0,
            cached_input_price_per_mtok: Some(1.5),
            output_price_per_mtok: 75.0,
            deprecated_at: None,
            released_at: None,
            source_url: "https://api.anthropic.com/v1/models".into(),
            source_fetched_at: Utc::now(),
            recommended: false,
            group: "Claude".into(),
        }];
        let merged = merge_catalogs(prev, fetched, Utc::now());
        let opus = merged
            .entries
            .iter()
            .find(|e| e.provider == "claude" && e.model_id == "claude-opus-4-7")
            .unwrap();
        assert!(opus.recommended, "recommended flag must be preserved from prev when fetched=false");
    }
}
