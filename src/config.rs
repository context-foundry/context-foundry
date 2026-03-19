use serde::Deserialize;
use std::{collections::BTreeMap, path::Path};

use crate::agent::ModelProvider;

fn default_true() -> bool {
    true
}

#[derive(Debug, Clone, Deserialize, Default)]
#[serde(default)]
pub struct StudioThemeConfig {
    pub base: Option<String>,
    pub background: Option<String>,
    pub surface: Option<String>,
    pub text: Option<String>,
    pub text_dim: Option<String>,
    pub text_muted: Option<String>,
    pub border: Option<String>,
    pub info: Option<String>,
    pub success: Option<String>,
    pub warning: Option<String>,
    pub error: Option<String>,
    pub claude: Option<String>,
    pub codex: Option<String>,
    pub scan: Option<String>,
    pub prompt: Option<String>,
    pub contracts: Option<String>,
    pub brief: Option<String>,
    pub sessions: Option<String>,
    pub output: Option<String>,
    pub activity: Option<String>,
    pub badge_fg: Option<String>,
    pub badge_bg: Option<String>,
    pub status_fg: Option<String>,
    pub status_bg: Option<String>,
    pub tool: Option<String>,
    pub tool_result: Option<String>,
}

#[derive(Debug, Clone, Deserialize)]
#[serde(default)]
pub struct Config {
    pub scout_model: String,
    pub planner_model: String,
    pub builder_model: String,
    /// Dual-model execution: e.g. ["claude:opus", "codex:"].
    /// When len >= 2, overrides builder_model/builder_provider.
    /// Format: "provider:model" where provider is "claude" or "codex".
    pub builder_models: Vec<String>,
    /// Dual-build selection: "first", "second", "both", or empty (off).
    /// Ctrl+D cycles through model[0]-only, model[1]-only, both pipelines.
    pub dual_selection: String,
    pub reviewer_model: String,
    pub fixer_model: String,
    pub discovery_model: String,

    /// Provider per build-loop role: "claude" (default) or "codex".
    pub scout_provider: String,
    pub planner_provider: String,
    pub builder_provider: String,
    pub reviewer_provider: String,
    pub fixer_provider: String,
    pub discovery_provider: String,

    pub studio_claude_model: String,
    pub studio_codex_model: String,
    pub studio_theme: String,
    pub studio_custom_themes: BTreeMap<String, StudioThemeConfig>,

    pub pause_between_tasks_secs: u64,
    pub pause_between_agents_secs: u64,
    pub pause_between_cycles_secs: u64,

    pub agent_timeout_secs: u64,

    pub patterns_dir: String,

    /// Skip reviewer/fixer when builder's verification commands pass.
    /// Relies on deterministic backpressure (tests, lints, type checks) instead of LLM review.
    pub backpressure_only: bool,

    /// Model overrides for Simple-complexity tasks.
    /// When a task is classified as Simple, these override the default role models.
    pub simple_planner_model: String,
    pub simple_builder_model: String,
    /// Empty string means use backpressure_only (skip LLM review).
    pub simple_reviewer_model: String,

    /// Max number of patterns injected into agent prompts (protects context "smart zone").
    pub max_pattern_injection: usize,

    /// Minimum patterns injected even for simple tasks (floor for scaled injection).
    pub min_pattern_injection: usize,

    /// Max iterations for `foundry plan` mode (0 = unlimited).
    pub planning_iterations: u64,

    /// Use adaptive inter-agent pauses: skip the full sleep when the last
    /// agent was not rate-limited, using a minimal 500ms pause instead.
    pub adaptive_pauses: bool,

    /// Optional git remote name to auto-push after successful commits.
    /// Defaults to None so Foundry commits locally only.
    pub auto_push_remote: Option<String>,

    /// Enable semantic pattern matching via local Ollama embeddings.
    pub semantic_match_enabled: bool,

    /// Ollama embedding model name.
    pub embedding_model: String,

    /// Ollama API base URL for embeddings (default: http://127.0.0.1:11434).
    pub ollama_url: String,

    /// Timeout for Ollama embedding requests (in milliseconds, rounded to whole seconds for curl).
    pub embedding_timeout_ms: u64,

    /// Orchestrator: proposer model provider.
    pub orchestrator_proposer_provider: String,
    /// Orchestrator: proposer model name.
    pub orchestrator_proposer_model: String,
    /// Orchestrator: reviewer model provider.
    pub orchestrator_reviewer_provider: String,
    /// Orchestrator: reviewer model name.
    pub orchestrator_reviewer_model: String,
    /// Orchestrator: max proposal/review iterations.
    pub orchestrator_max_iterations: usize,
    /// Orchestrator: acceptance policy ("no-high", "no-high-medium", "no-findings").
    pub orchestrator_accept_policy: String,

    /// Review mode: "diff-only" passes git diff to reviewer, "file-list" uses changed file list.
    pub review_mode: String,

    /// Skip the planner stage for Simple-complexity tasks and pass the task
    /// description directly to the builder.
    pub skip_planner_for_simple: bool,

    /// Skip the scout stage for Simple-complexity tasks. The task description
    /// is sufficient context for the builder without a codebase investigation.
    pub skip_scout_for_simple: bool,

    /// Minutes to wait before running discovery after the last H-prefixed
    /// (human-injected) task completes. Doubles (up to 30 min) when discovery
    /// finds 0 new tasks.
    pub discovery_cooldown_minutes: u64,

    /// Spawn the planner for task N+1 while the builder is running task N.
    /// The pre-computed plan is reused when the loop advances to that task.
    pub planner_lookahead: bool,

    /// Model for pattern extraction (lightweight JSON output, doesn't need Opus).
    pub pattern_extraction_model: String,

    /// Run mode: "auto" (default) runs forever with discovery.
    /// "sprint" runs all tasks then stops. "review" runs one task at a time with PR per task.
    #[serde(alias = "mode")]
    pub run_mode: String,

    /// Pipeline mode: "full" (all 4 SPID stages), "fast" (skip scout if report
    /// exists, defer doubt to end of session), "backpressure" (skip LLM review).
    pub pipeline_mode: String,

    /// When true, skip doubt for all tasks except the last pending one in the
    /// session. The final doubt audits all accumulated changes.
    pub batch_doubt: bool,

    /// Selected extension names (e.g., ["roblox", "extend"]).
    pub extensions: Vec<String>,

    /// When true, auto-create a GitHub issue when a task commits as WIP
    /// (validation failed). The issue body includes review findings from
    /// .buildloop/review-report.md.
    pub create_issue_on_wip: bool,

    /// Preview pane word-wrap preference (persisted to .foundry.json).
    #[serde(default = "default_true")]
    pub preview_wrap: bool,

    /// Poll interval (seconds) for checking PR review status in Review mode.
    pub pr_poll_interval_secs: u64,

    /// TUI color theme: "dark" (default), "catppuccin", or "solarized".
    pub theme: String,

    /// Override truecolor detection: true forces RGB, false forces ANSI-256.
    /// When None (default), auto-detection is used.
    pub truecolor: Option<bool>,

    /// Optional build/compile command to run after builder completes.
    /// If set, output is checked before proceeding to doubt stage.
    pub build_command: Option<String>,

    /// Maximum session cost in USD. When reached, the loop pauses.
    /// 0.0 (default) means no limit.
    pub cost_limit: f64,

    /// Multi-pass review threshold: when changed file count exceeds this,
    /// split review into per-file passes plus an integration pass.
    /// 0 disables multi-pass (always single-pass review).
    pub review_multipass_threshold: usize,

    /// Confidence threshold for reviewer findings. Findings with confidence
    /// below this value are logged as warnings but not auto-fixed.
    /// Range 0.0-1.0, default 0.5.
    pub confidence_threshold: f64,
}

impl Default for Config {
    fn default() -> Self {
        Self {
            scout_model: "sonnet".into(),
            planner_model: "opus".into(),
            builder_model: "opus".into(),
            builder_models: Vec::new(),
            dual_selection: String::new(),
            reviewer_model: "sonnet".into(),
            fixer_model: "sonnet".into(),
            discovery_model: "opus".into(),

            scout_provider: "claude".into(),
            planner_provider: "claude".into(),
            builder_provider: "claude".into(),
            reviewer_provider: "claude".into(),
            fixer_provider: "claude".into(),
            discovery_provider: "claude".into(),

            studio_claude_model: "opus".into(),
            studio_codex_model: String::new(),
            studio_theme: "foundry".into(),
            studio_custom_themes: BTreeMap::new(),

            pause_between_tasks_secs: 10,
            pause_between_agents_secs: 3,
            pause_between_cycles_secs: 30,

            agent_timeout_secs: 600, // 10 minutes

            patterns_dir: "~/.foundry/patterns".into(),

            backpressure_only: true,
            simple_planner_model: "sonnet".into(),
            simple_builder_model: "sonnet".into(),
            simple_reviewer_model: String::new(),
            max_pattern_injection: 10,
            min_pattern_injection: 2,
            planning_iterations: 0,
            adaptive_pauses: true,
            auto_push_remote: None,
            semantic_match_enabled: true,
            embedding_model: "nomic-embed-text".into(),
            ollama_url: "http://127.0.0.1:11435".into(),
            embedding_timeout_ms: 2000,
            orchestrator_proposer_provider: "claude".into(),
            orchestrator_proposer_model: "opus".into(),
            orchestrator_reviewer_provider: "claude".into(),
            orchestrator_reviewer_model: "opus".into(),
            orchestrator_max_iterations: 3,
            orchestrator_accept_policy: "no-high-medium".into(),
            review_mode: "diff-only".into(),
            skip_planner_for_simple: true,
            skip_scout_for_simple: true,
            discovery_cooldown_minutes: 5,
            planner_lookahead: true,
            pattern_extraction_model: "sonnet".into(),
            run_mode: "auto".into(),
            pipeline_mode: "full".into(),
            batch_doubt: true,
            extensions: Vec::new(),
            create_issue_on_wip: false,
            preview_wrap: true,
            pr_poll_interval_secs: 30,
            theme: "dark".into(),
            truecolor: None,
            build_command: None,
            cost_limit: 0.0,
            review_multipass_threshold: 8,
            confidence_threshold: 0.5,
        }
    }
}

impl Config {
    /// Read a JSON config file and return its content as a serde_json::Value.
    /// Returns None if the file doesn't exist or can't be read/parsed.
    fn read_json_file(path: &Path) -> Option<serde_json::Value> {
        if !path.exists() {
            return None;
        }
        let content = match std::fs::read_to_string(path) {
            Ok(c) => c,
            Err(e) => {
                eprintln!(
                    "warning: failed to read {}: {e} -- skipping",
                    path.display(),
                );
                return None;
            }
        };
        match serde_json::from_str::<serde_json::Value>(&content) {
            Ok(v) => Some(v),
            Err(e) => {
                eprintln!(
                    "warning: failed to parse {}: {e} -- skipping",
                    path.display(),
                );
                None
            }
        }
    }

    /// Merge two JSON objects. Project values override global values.
    /// Non-object values are not merged (project wins entirely).
    fn merge_json(global: serde_json::Value, project: serde_json::Value) -> serde_json::Value {
        match (global, project) {
            (serde_json::Value::Object(mut g), serde_json::Value::Object(p)) => {
                for (k, v) in p {
                    g.insert(k, v);
                }
                serde_json::Value::Object(g)
            }
            (_, project) => project,
        }
    }

    /// Resolve the global config path: ~/.foundry/config.json
    fn global_config_path() -> Option<std::path::PathBuf> {
        if cfg!(target_os = "windows") {
            std::env::var("LOCALAPPDATA")
                .or_else(|_| std::env::var("USERPROFILE").map(|p| format!("{}\\.foundry", p)))
                .ok()
                .map(|p| {
                    std::path::PathBuf::from(p)
                        .join(".foundry")
                        .join("config.json")
                })
        } else {
            std::env::var("HOME").ok().map(|h| {
                std::path::PathBuf::from(h)
                    .join(".foundry")
                    .join("config.json")
            })
        }
    }

    pub fn load(project_dir: &Path) -> Self {
        let global_path = Self::global_config_path();
        let project_path = project_dir.join(".foundry.json");

        let global_val = global_path.as_deref().and_then(Self::read_json_file);
        let project_val = Self::read_json_file(&project_path);

        let merged = match (global_val, project_val) {
            (Some(g), Some(p)) => Self::merge_json(g, p),
            (Some(g), None) => g,
            (None, Some(p)) => p,
            (None, None) => return Self::default(),
        };

        match serde_json::from_value::<Self>(merged) {
            Ok(mut config) => {
                // Normalize legacy mode values
                if config.run_mode == "loop" {
                    config.run_mode = "auto".into();
                } else if config.run_mode == "hil" {
                    config.run_mode = "review".into();
                }
                config
            }
            Err(e) => {
                eprintln!("warning: failed to deserialize merged config: {e} -- using defaults");
                Self::default()
            }
        }
    }

    /// Parse a provider string ("claude" or "codex") into a ModelProvider.
    /// Falls back to Claude for unrecognized values.
    pub fn parse_provider(value: &str) -> ModelProvider {
        match value.trim().to_lowercase().as_str() {
            "codex" => ModelProvider::Codex,
            _ => ModelProvider::Claude,
        }
    }

    /// Split a "provider:model" spec into (provider, model) tuple.
    /// If no `:` is found, the entire string is treated as the provider.
    pub fn parse_model_spec(spec: &str) -> (String, String) {
        match spec.find(':') {
            Some(pos) => {
                let provider = spec[..pos].trim().to_string();
                let model = spec[pos + 1..].trim().to_string();
                (provider, model)
            }
            None => (spec.trim().to_string(), String::new()),
        }
    }

    pub fn display_provider_model(provider: &str, model: &str) -> String {
        let provider = Self::parse_provider(provider);
        let model = model.trim();
        if model.is_empty() {
            provider.to_string()
        } else {
            // Capitalize first letter: "sonnet" -> "Sonnet", "opus" -> "Opus"
            let capitalized = {
                let mut chars = model.chars();
                match chars.next() {
                    Some(c) => format!("{}{}", c.to_uppercase(), chars.as_str()),
                    None => String::new(),
                }
            };
            format!("{provider} {capitalized}")
        }
    }

    pub fn display_model_spec(spec: &str) -> String {
        let (provider, model) = Self::parse_model_spec(spec);
        Self::display_provider_model(&provider, &model)
    }

    /// Persist the preview wrap preference to .foundry.json without
    /// overwriting other config fields.
    pub fn save_preview_wrap(project_dir: &Path, wrap: bool) {
        let config_path = project_dir.join(".foundry.json");
        let content = std::fs::read_to_string(&config_path).unwrap_or_else(|_| "{}".to_string());
        let mut value: serde_json::Value =
            serde_json::from_str(&content).unwrap_or(serde_json::json!({}));
        value["preview_wrap"] = serde_json::json!(wrap);
        let json = serde_json::to_string_pretty(&value).unwrap_or_default();
        let _ = crate::utils::atomic_write_file(&config_path, json.as_bytes());
    }

    pub fn save_extensions(project_dir: &Path, extensions: &[String]) {
        let config_path = project_dir.join(".foundry.json");
        let content = std::fs::read_to_string(&config_path).unwrap_or_else(|_| "{}".to_string());
        let mut value: serde_json::Value =
            serde_json::from_str(&content).unwrap_or(serde_json::json!({}));
        value["extensions"] = serde_json::json!(extensions);
        let json = serde_json::to_string_pretty(&value).unwrap_or_default();
        let _ = crate::utils::atomic_write_file(&config_path, json.as_bytes());
    }

    /// Persist the run_mode to .foundry.json without overwriting other config fields.
    /// Also removes the legacy "mode" key if present, to prevent it from shadowing.
    pub fn save_run_mode(project_dir: &Path, run_mode: &str) {
        let config_path = project_dir.join(".foundry.json");
        let content = std::fs::read_to_string(&config_path).unwrap_or_else(|_| "{}".to_string());
        let mut value: serde_json::Value =
            serde_json::from_str(&content).unwrap_or(serde_json::json!({}));
        value["run_mode"] = serde_json::json!(run_mode);
        // Remove legacy "mode" key to prevent it from shadowing "run_mode"
        // when JSON is reordered or parsed by a different library.
        if let Some(obj) = value.as_object_mut() {
            obj.remove("mode");
        }
        let json = serde_json::to_string_pretty(&value).unwrap_or_default();
        let _ = crate::utils::atomic_write_file(&config_path, json.as_bytes());
    }

    pub fn save_dual_selection(project_dir: &Path, selection: &str) {
        let config_path = project_dir.join(".foundry.json");
        let content = std::fs::read_to_string(&config_path).unwrap_or_else(|_| "{}".to_string());
        let mut value: serde_json::Value =
            serde_json::from_str(&content).unwrap_or(serde_json::json!({}));
        value["dual_selection"] = serde_json::json!(selection);
        let json = serde_json::to_string_pretty(&value).unwrap_or_default();
        let _ = crate::utils::atomic_write_file(&config_path, json.as_bytes());
    }

    fn model_provider_hint(model: &str) -> Option<ModelProvider> {
        let lower = model.trim().to_ascii_lowercase();
        if lower.is_empty() {
            return None;
        }

        if lower.starts_with("claude") || matches!(lower.as_str(), "opus" | "sonnet" | "haiku") {
            return Some(ModelProvider::Claude);
        }

        if lower.starts_with("codex")
            || lower.starts_with("gpt-")
            || matches!(lower.as_str(), "o1" | "o3" | "o4")
            || lower.starts_with("o1-")
            || lower.starts_with("o3-")
            || lower.starts_with("o4-")
        {
            return Some(ModelProvider::Codex);
        }

        None
    }

    fn normalize_model_for_provider(provider: ModelProvider, model: &str) -> String {
        match Self::model_provider_hint(model) {
            Some(owner) if owner != provider => String::new(),
            _ => model.trim().to_string(),
        }
    }

    /// Create a Config clone with all build-loop role providers overridden for
    /// a specific pipeline spec (e.g. "claude:opus" or "codex:").
    ///
    /// The builder stage uses the spec's explicit model. Other stages keep
    /// their configured model only when it is compatible with the selected
    /// provider; otherwise they fall back to the provider default model.
    pub fn for_pipeline(&self, spec: &str) -> Config {
        let (provider, model) = Self::parse_model_spec(spec);
        let provider_kind = Self::parse_provider(&provider);
        let mut config = self.clone();
        config.scout_provider = provider.clone();
        config.planner_provider = provider.clone();
        config.builder_provider = provider.clone();
        config.reviewer_provider = provider.clone();
        config.fixer_provider = provider.clone();
        config.discovery_provider = provider.clone();
        config.scout_model = Self::normalize_model_for_provider(provider_kind, &self.scout_model);
        config.planner_model =
            Self::normalize_model_for_provider(provider_kind, &self.planner_model);
        config.builder_model = model;
        config.reviewer_model =
            Self::normalize_model_for_provider(provider_kind, &self.reviewer_model);
        config.fixer_model = Self::normalize_model_for_provider(provider_kind, &self.fixer_model);
        config.discovery_model =
            Self::normalize_model_for_provider(provider_kind, &self.discovery_model);
        // Disable dual in the forked config so process_task runs single-pipeline
        config.builder_models.clear();
        config.dual_selection.clear();
        config
    }

    /// Return the effective pipeline configs for the active dual selection.
    /// Single-selection modes return one config; dual mode returns two.
    pub fn selected_pipeline_configs(&self, selection: &str) -> Vec<Config> {
        match selection {
            "first" if !self.builder_models.is_empty() => {
                vec![self.for_pipeline(&self.builder_models[0])]
            }
            "second" if self.builder_models.len() >= 2 => {
                vec![self.for_pipeline(&self.builder_models[1])]
            }
            "both" if self.builder_models.len() >= 2 => vec![
                self.for_pipeline(&self.builder_models[0]),
                self.for_pipeline(&self.builder_models[1]),
            ],
            _ => vec![self.clone()],
        }
    }

    /// Return (role_name, provider, model) tuples for all build-loop roles.
    pub fn role_configs(&self) -> Vec<(&str, &str, &str)> {
        vec![
            ("Scout", &self.scout_provider, &self.scout_model),
            ("Plan", &self.planner_provider, &self.planner_model),
            ("Implement", &self.builder_provider, &self.builder_model),
            ("Reviewer", &self.reviewer_provider, &self.reviewer_model),
            ("Fixer", &self.fixer_provider, &self.fixer_model),
            ("Discovery", &self.discovery_provider, &self.discovery_model),
            ("Patterns", "claude", &self.pattern_extraction_model),
            ("Add Tasks", "claude", "sonnet"),
        ]
    }
}

#[cfg(test)]
mod tests {
    use super::Config;
    use crate::agent::ModelProvider;
    use std::fs;

    #[test]
    fn default_config_disables_auto_push() {
        assert_eq!(Config::default().auto_push_remote, None);
    }

    #[test]
    fn config_deserializes_auto_push_remote() {
        let config: Config = serde_json::from_str(r#"{"auto_push_remote":"snedea"}"#)
            .expect("config should deserialize");
        assert_eq!(config.auto_push_remote.as_deref(), Some("snedea"));
    }

    #[test]
    fn parse_provider_supports_codex_and_defaults_to_claude() {
        assert_eq!(Config::parse_provider("codex"), ModelProvider::Codex);
        assert_eq!(Config::parse_provider("CoDeX"), ModelProvider::Codex);
        assert_eq!(Config::parse_provider("claude"), ModelProvider::Claude);
        assert_eq!(Config::parse_provider("unknown"), ModelProvider::Claude);
    }

    #[test]
    fn display_provider_model_formats_empty_and_named_models() {
        assert_eq!(
            Config::display_provider_model("claude", "opus"),
            "Claude Opus"
        );
        assert_eq!(Config::display_provider_model("codex", ""), "Codex");
        assert_eq!(Config::display_model_spec("codex:gpt-5.4"), "Codex Gpt-5.4");
    }

    #[test]
    fn for_pipeline_overrides_all_providers_and_clears_incompatible_models() {
        let config = Config::default();
        let pipeline = config.for_pipeline("codex:");

        assert_eq!(pipeline.scout_provider, "codex");
        assert_eq!(pipeline.planner_provider, "codex");
        assert_eq!(pipeline.builder_provider, "codex");
        assert_eq!(pipeline.reviewer_provider, "codex");
        assert_eq!(pipeline.fixer_provider, "codex");
        assert_eq!(pipeline.discovery_provider, "codex");

        assert_eq!(pipeline.scout_model, "");
        assert_eq!(pipeline.planner_model, "");
        assert_eq!(pipeline.builder_model, "");
        assert_eq!(pipeline.reviewer_model, "");
        assert_eq!(pipeline.fixer_model, "");
        assert_eq!(pipeline.discovery_model, "");
    }

    #[test]
    fn for_pipeline_keeps_compatible_role_models_and_uses_builder_spec_model() {
        let mut config = Config::default();
        config.scout_model = "sonnet".into();
        config.planner_model = "opus".into();
        config.builder_model = "sonnet".into();
        config.reviewer_model = "haiku".into();
        config.fixer_model = "sonnet".into();
        config.discovery_model = "opus".into();

        let pipeline = config.for_pipeline("claude:opus");

        assert_eq!(pipeline.scout_model, "sonnet");
        assert_eq!(pipeline.planner_model, "opus");
        assert_eq!(pipeline.builder_model, "opus");
        assert_eq!(pipeline.reviewer_model, "haiku");
        assert_eq!(pipeline.fixer_model, "sonnet");
        assert_eq!(pipeline.discovery_model, "opus");
    }

    #[test]
    fn selected_pipeline_configs_expand_both_selection() {
        let mut config = Config::default();
        config.builder_models = vec!["claude:opus".into(), "codex:".into()];

        let selected = config.selected_pipeline_configs("both");

        assert_eq!(selected.len(), 2);
        assert_eq!(selected[0].builder_provider, "claude");
        assert_eq!(selected[0].builder_model, "opus");
        assert_eq!(selected[1].builder_provider, "codex");
        assert_eq!(selected[1].builder_model, "");
        assert_eq!(selected[1].planner_model, "");
    }

    #[test]
    fn config_deserializes_role_specific_providers() {
        let config: Config = serde_json::from_str(
            r#"{
                "planner_provider":"claude",
                "builder_provider":"codex",
                "reviewer_provider":"claude",
                "fixer_provider":"codex",
                "discovery_provider":"claude"
            }"#,
        )
        .expect("config should deserialize");

        assert_eq!(config.planner_provider, "claude");
        assert_eq!(config.builder_provider, "codex");
        assert_eq!(config.reviewer_provider, "claude");
        assert_eq!(config.fixer_provider, "codex");
        assert_eq!(config.discovery_provider, "claude");
    }

    #[test]
    fn load_warns_on_invalid_json() {
        let dir = tempfile::tempdir().unwrap();
        fs::write(dir.path().join(".foundry.json"), "{ not valid json").unwrap();
        let config = Config::load(dir.path());
        assert_eq!(
            config.agent_timeout_secs,
            Config::default().agent_timeout_secs
        );
        assert_eq!(config.planner_model, Config::default().planner_model);
    }

    #[test]
    fn config_deserializes_pipeline_mode_and_batch_doubt() {
        let config: Config = serde_json::from_str(r#"{"pipeline_mode":"fast","batch_doubt":true}"#)
            .expect("config should deserialize");
        assert_eq!(config.pipeline_mode, "fast");
        assert!(config.batch_doubt);
    }

    #[test]
    fn default_config_uses_auto_run_mode() {
        assert_eq!(Config::default().run_mode, "auto");
    }

    #[test]
    fn config_normalizes_legacy_mode_values() {
        let dir = tempfile::tempdir().unwrap();
        // Old "loop" -> "auto"
        fs::write(dir.path().join(".foundry.json"), r#"{"mode":"loop"}"#).unwrap();
        let config = Config::load(dir.path());
        assert_eq!(config.run_mode, "auto");

        // Old "hil" -> "review"
        fs::write(dir.path().join(".foundry.json"), r#"{"mode":"hil"}"#).unwrap();
        let config = Config::load(dir.path());
        assert_eq!(config.run_mode, "review");

        // New "run_mode" key passes through
        fs::write(dir.path().join(".foundry.json"), r#"{"run_mode":"sprint"}"#).unwrap();
        let config = Config::load(dir.path());
        assert_eq!(config.run_mode, "sprint");
    }

    #[test]
    fn default_config_disables_create_issue_on_wip() {
        assert!(!Config::default().create_issue_on_wip);
    }

    #[test]
    fn config_deserializes_create_issue_on_wip() {
        let config: Config = serde_json::from_str(r#"{"create_issue_on_wip":true}"#)
            .expect("config should deserialize");
        assert!(config.create_issue_on_wip);
    }

    #[cfg(unix)]
    #[test]
    fn load_warns_on_unreadable_file() {
        use std::os::unix::fs::PermissionsExt;
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join(".foundry.json");
        fs::write(&path, "{}").unwrap();
        fs::set_permissions(&path, fs::Permissions::from_mode(0o000)).unwrap();
        let config = Config::load(dir.path());
        assert_eq!(
            config.agent_timeout_secs,
            Config::default().agent_timeout_secs
        );
        // Restore permissions so tempdir cleanup succeeds
        fs::set_permissions(&path, fs::Permissions::from_mode(0o644)).unwrap();
    }
}
