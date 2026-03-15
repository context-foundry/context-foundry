use serde::Deserialize;
use std::{collections::BTreeMap, path::Path};

use crate::agent::ModelProvider;

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
    pub planner_model: String,
    pub builder_model: String,
    pub reviewer_model: String,
    pub fixer_model: String,
    pub discovery_model: String,

    /// Provider per build-loop role: "claude" (default) or "codex".
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

    /// Minutes to wait before running discovery after the last H-prefixed
    /// (human-injected) task completes. Doubles (up to 30 min) when discovery
    /// finds 0 new tasks.
    pub discovery_cooldown_minutes: u64,

    /// Spawn the planner for task N+1 while the builder is running task N.
    /// The pre-computed plan is reused when the loop advances to that task.
    pub planner_lookahead: bool,

    /// Model for pattern extraction (lightweight JSON output, doesn't need Opus).
    pub pattern_extraction_model: String,
}

impl Default for Config {
    fn default() -> Self {
        Self {
            planner_model: "opus".into(),
            builder_model: "opus".into(),
            reviewer_model: "sonnet".into(),
            fixer_model: "sonnet".into(),
            discovery_model: "opus".into(),

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

            backpressure_only: false,
            simple_planner_model: "sonnet".into(),
            simple_builder_model: "sonnet".into(),
            simple_reviewer_model: String::new(),
            max_pattern_injection: 10,
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
            discovery_cooldown_minutes: 5,
            planner_lookahead: true,
            pattern_extraction_model: "sonnet".into(),
        }
    }
}

impl Config {
    pub fn load(project_dir: &Path) -> Self {
        let config_path = project_dir.join(".foundry.json");
        if config_path.exists() {
            let content = match std::fs::read_to_string(&config_path) {
                Ok(c) => c,
                Err(e) => {
                    eprintln!(
                        "warning: failed to read {}: {e} -- using default config",
                        config_path.display(),
                    );
                    return Self::default();
                }
            };
            match serde_json::from_str(&content) {
                Ok(config) => config,
                Err(e) => {
                    eprintln!(
                        "warning: failed to parse {}: {e} -- using default config",
                        config_path.display(),
                    );
                    Self::default()
                }
            }
        } else {
            Self::default()
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

    pub fn display_provider_model(provider: &str, model: &str) -> String {
        let provider = Self::parse_provider(provider);
        let model = model.trim();
        if model.is_empty() {
            provider.to_string()
        } else {
            format!("{provider} {model}")
        }
    }

    /// Return (role_name, provider, model) tuples for all build-loop roles.
    pub fn role_configs(&self) -> Vec<(&str, &str, &str)> {
        vec![
            ("Planner", &self.planner_provider, &self.planner_model),
            ("Builder", &self.builder_provider, &self.builder_model),
            ("Reviewer", &self.reviewer_provider, &self.reviewer_model),
            ("Discovery", &self.discovery_provider, &self.discovery_model),
            ("Patterns", "claude", &self.pattern_extraction_model),
            ("Add Tasks", "claude", "haiku"),
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
            "Claude opus"
        );
        assert_eq!(Config::display_provider_model("codex", ""), "Codex");
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
        assert_eq!(config.agent_timeout_secs, Config::default().agent_timeout_secs);
        assert_eq!(config.planner_model, Config::default().planner_model);
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
        assert_eq!(config.agent_timeout_secs, Config::default().agent_timeout_secs);
        // Restore permissions so tempdir cleanup succeeds
        fs::set_permissions(&path, fs::Permissions::from_mode(0o644)).unwrap();
    }
}
