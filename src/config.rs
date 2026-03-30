use serde::Deserialize;
use std::path::Path;

use crate::agent::ModelProvider;
use crate::budget::BudgetTargets;

fn default_true() -> bool {
    true
}

fn default_archive_keep() -> usize {
    3
}

fn default_budget_overrun_threshold() -> u8 {
    10
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

    /// Enable P+ subphase: run the planner's output through the proposer/reviewer
    /// orchestrator loop for Complex-classified tasks before passing to Builder.
    #[serde(default)]
    pub plan_review_enabled: bool,

    /// Review mode: "diff-only" passes git diff to reviewer, "file-list" uses changed file list.
    pub review_mode: String,

    /// Skip the planner stage for Simple-complexity tasks and pass the task
    /// description directly to the builder.
    pub skip_planner_for_simple: bool,

    /// Skip the scout stage for Simple-complexity tasks. The task description
    /// is sufficient context for the builder without a codebase investigation.
    pub skip_scout_for_simple: bool,

    /// Skip the doubt/verify stage for Simple-complexity tasks when the
    /// builder's own verification commands passed (exit code 0).
    pub skip_doubt_for_simple: bool,

    /// Consecutive doubt passes required before learned doubt confidence
    /// can skip the doubt stage for matching task shapes (Simple/Medium only).
    /// 0 disables learned doubt confidence entirely.
    pub doubt_confidence_threshold: usize,

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

    /// Auto-archive completed phases in TASKS.md to TASKS-ARCHIVE.md.
    #[serde(default = "default_true")]
    pub auto_archive_tasks: bool,

    /// Number of completed tasks to keep at the start of each archived phase.
    #[serde(default = "default_archive_keep")]
    pub archive_keep_first: usize,

    /// Number of completed tasks to keep at the end of each archived phase.
    #[serde(default = "default_archive_keep")]
    pub archive_keep_last: usize,

    /// Multi-pass review threshold: when changed file count exceeds this,
    /// split review into per-file passes plus an integration pass.
    /// 0 disables multi-pass (always single-pass review).
    pub review_multipass_threshold: usize,

    /// Confidence threshold for reviewer findings. Findings with confidence
    /// below this value are logged as warnings but not auto-fixed.
    /// Range 0.0-1.0, default 0.5.
    pub confidence_threshold: f64,

    /// Enable parallel builder: split multi-file plans into concurrent
    /// sub-agents, each in its own git worktree. Experimental.
    pub parallel_builder: bool,

    /// Minimum independent file operations in the plan before parallel
    /// builder activates. Below this threshold the sequential builder runs.
    pub parallel_builder_min_files: usize,

    /// Agent execution backend: "pty" (default) or "tmux".
    pub agent_backend: String,

    /// Tmux session name prefix (default: "foundry").
    pub tmux_session_prefix: String,

    /// Keep tmux sessions alive after agent completion (default: false).
    pub tmux_keep_sessions: bool,

    /// Enable per-phase file isolation for QRPID pipeline boundaries.
    /// When true, restricted artifacts are physically moved out of the workspace
    /// before spawning isolated agents (e.g., Doubt cannot read current-plan.md).
    #[serde(default)]
    pub phase_isolation: bool,

    /// Per-phase context budget targets (percentage of context window).
    /// Defaults match QRPID spec: scout=15%, planner=40%, builder=60%, reviewer=50%.
    #[serde(default)]
    pub budget_targets: BudgetTargets,

    /// Overrun tolerance in percentage points. Overruns within this margin
    /// are logged but do not trigger recovery actions. Default: 10.
    #[serde(default = "default_budget_overrun_threshold")]
    pub budget_overrun_threshold: u8,

    /// Enable budget overrun detection and recovery actions.
    /// When false, budget is tracked in telemetry but no recovery actions execute.
    #[serde(default)]
    pub budget_recovery_enabled: bool,

    /// Enable Docker sandbox isolation for agent subprocesses (default: true).
    /// Always on by default. Only implementers should override via .foundry.json.
    #[serde(default = "default_true")]
    pub sandbox: bool,

    /// Docker image used for sandbox containers.
    pub sandbox_image: String,

    /// Additional bind mounts passed to docker run (e.g. ["~/.cache:/cache:ro"]).
    pub sandbox_extra_mounts: Vec<String>,

    /// Host credential directories to mount into sandbox containers.
    /// Paths are relative to $HOME (e.g. ".claude" mounts ~/.claude).
    /// Default: [".claude"] for Claude Code OAuth.
    /// For Copilot: [".claude", ".copilot"] or [".copilot", ".config/gh"].
    pub sandbox_auth_dirs: Vec<String>,

    /// Extra environment variables injected into sandbox containers.
    /// Format: ["KEY=VALUE", ...]. Useful for ANTHROPIC_BASE_URL (copilot-api proxy).
    pub sandbox_env: Vec<String>,

    /// Single model override. When non-empty, all pipeline role models
    /// (scout, planner, builder, reviewer, fixer, discovery) use this value.
    /// Useful for OAuth subscriptions that lock you to one model.
    pub model: String,

    /// Run semgrep static analysis before the doubt/review stage.
    /// Findings are injected into the reviewer prompt as reference data.
    /// Gracefully skipped when semgrep is not installed.
    #[serde(default)]
    pub semgrep_enabled: bool,

    /// Semgrep rulesets to run (e.g. ["p/default", "p/security-audit"]).
    /// Empty uses auto-detection based on project languages.
    pub semgrep_rulesets: Vec<String>,

    /// Require human approval in the TUI before committing a validated task as feat.
    /// When true, the TUI prompts "Commit T1.1 as feat? [y/n]" after doubt passes.
    /// On deny, the task commits as WIP and the loop pauses instead of retrying.
    /// In headless mode, this flag is ignored with a warning (auto-approves).
    #[serde(default)]
    pub require_human_approval: bool,

    /// Enforce role-based tool allowlists at the CLI level.
    /// When true, uses --allowedTools instead of --dangerously-skip-permissions
    /// for Claude backend agents. This is tool-surface reduction, not a hard
    /// filesystem security boundary -- any role with Bash access is still trusted code.
    /// Codex provider does not support this; a warning is logged when enabled with Codex.
    #[serde(default)]
    pub enforce_phase_rbac: bool,

    /// Model for PR review via `foundry review-pr`. Defaults to reviewer_model.
    /// Allows using a higher-quality model (e.g., opus) for PR reviews while
    /// keeping the build-loop reviewer on a cheaper model (e.g., sonnet).
    pub pr_review_model: String,

    /// Provider for PR review via `foundry review-pr`. Defaults to reviewer_provider.
    pub pr_review_provider: String,

    /// Multi-pass threshold for PR review. When changed file count exceeds this,
    /// split into per-file passes plus integration pass (like build-loop reviewer).
    /// 0 (default) means use review_multipass_threshold.
    pub pr_review_multipass_threshold: usize,
}

impl Default for Config {
    fn default() -> Self {
        Self {
            scout_model: "sonnet".into(),
            planner_model: "opus".into(),
            builder_model: "opus".into(),
            builder_models: Vec::new(),
            dual_selection: "first".into(),
            reviewer_model: "sonnet".into(),
            fixer_model: "sonnet".into(),
            discovery_model: "opus".into(),

            scout_provider: "claude".into(),
            planner_provider: "claude".into(),
            builder_provider: "claude".into(),
            reviewer_provider: "claude".into(),
            fixer_provider: "claude".into(),
            discovery_provider: "claude".into(),

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
            ollama_url: "http://127.0.0.1:11434".into(),
            embedding_timeout_ms: 2000,
            orchestrator_proposer_provider: "claude".into(),
            orchestrator_proposer_model: "opus".into(),
            orchestrator_reviewer_provider: "claude".into(),
            orchestrator_reviewer_model: "opus".into(),
            orchestrator_max_iterations: 3,
            orchestrator_accept_policy: "no-high-medium".into(),
            plan_review_enabled: false,
            review_mode: "diff-only".into(),
            skip_planner_for_simple: true,
            skip_scout_for_simple: true,
            skip_doubt_for_simple: true,
            doubt_confidence_threshold: 5,
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
            auto_archive_tasks: true,
            archive_keep_first: 3,
            archive_keep_last: 3,
            review_multipass_threshold: 8,
            confidence_threshold: 0.5,
            parallel_builder: false,
            parallel_builder_min_files: 3,
            agent_backend: "pty".into(),
            tmux_session_prefix: "foundry".into(),
            tmux_keep_sessions: false,
            phase_isolation: false,
            budget_targets: BudgetTargets::default(),
            budget_overrun_threshold: 10,
            budget_recovery_enabled: false,
            sandbox: true,
            sandbox_image: "foundry-sandbox:latest".into(),
            sandbox_extra_mounts: Vec::new(),
            sandbox_auth_dirs: vec![".claude".into()],
            sandbox_env: Vec::new(),
            model: String::new(),
            semgrep_enabled: false,
            semgrep_rulesets: Vec::new(),
            require_human_approval: false,
            enforce_phase_rbac: false,
            pr_review_model: String::new(),
            pr_review_provider: String::new(),
            pr_review_multipass_threshold: 0,
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

    fn normalize(&mut self) {
        // Normalize legacy mode values
        if self.run_mode == "loop" {
            self.run_mode = "auto".into();
        } else if self.run_mode == "hil" {
            self.run_mode = "review".into();
        }
        // Single model override: collapse all role models
        if !self.model.is_empty() {
            let m = self.model.clone();
            self.scout_model = m.clone();
            self.planner_model = m.clone();
            self.builder_model = m.clone();
            self.reviewer_model = m.clone();
            self.fixer_model = m.clone();
            self.discovery_model = m.clone();
            self.simple_planner_model = m.clone();
            self.simple_builder_model = m.clone();
            self.simple_reviewer_model = m.clone();
            self.pattern_extraction_model = m;
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
                config.normalize();
                config
            }
            Err(e) => {
                eprintln!("warning: failed to deserialize merged config: {e} -- using defaults");
                Self::default()
            }
        }
    }

    /// Load config from global `~/.foundry/config.json` only, ignoring any
    /// project-level `.foundry.json`. Used by CI workflows to prevent untrusted
    /// PR branches from influencing review config.
    pub fn load_global_only() -> Self {
        let global_path = Self::global_config_path();
        let global_val = global_path.as_deref().and_then(Self::read_json_file);

        match global_val {
            Some(val) => match serde_json::from_value::<Self>(val) {
                Ok(mut config) => {
                    config.normalize();
                    config
                }
                Err(e) => {
                    eprintln!("warning: failed to deserialize global config: {e} -- using defaults");
                    Self::default()
                }
            },
            None => Self::default(),
        }
    }

    /// Build a SandboxConfig from this Config's sandbox fields.
    pub fn sandbox_config(&self) -> crate::sandbox::SandboxConfig {
        crate::sandbox::SandboxConfig::detect(
            self.sandbox,
            &self.sandbox_image,
            self.sandbox_extra_mounts.clone(),
            self.sandbox_auth_dirs.clone(),
            self.sandbox_env.clone(),
        )
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
        match provider {
            ModelProvider::Claude => "Claude".to_string(),
            ModelProvider::Codex => {
                let model = model.trim();
                if model.is_empty() {
                    provider.to_string()
                } else {
                    // Capitalize first letter: "gpt-5.4" -> "Gpt-5.4"
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
            "Claude"
        );
        assert_eq!(
            Config::display_provider_model("claude", "sonnet"),
            "Claude"
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
    fn default_config_enables_skip_doubt_for_simple() {
        assert!(Config::default().skip_doubt_for_simple);
    }

    #[test]
    fn config_deserializes_skip_doubt_for_simple() {
        let config: Config =
            serde_json::from_str(r#"{"skip_doubt_for_simple":false}"#)
                .expect("config should deserialize");
        assert!(!config.skip_doubt_for_simple);
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

    #[test]
    fn default_config_enables_sandbox() {
        let config = Config::default();
        assert!(config.sandbox);
        assert_eq!(config.sandbox_image, "foundry-sandbox:latest");
        assert!(config.sandbox_extra_mounts.is_empty());
        assert_eq!(config.sandbox_auth_dirs, vec![".claude"]);
        assert!(config.sandbox_env.is_empty());
        assert!(config.model.is_empty());
    }

    #[test]
    fn config_deserializes_sandbox_fields() {
        let config: Config = serde_json::from_str(
            r#"{"sandbox":false,"sandbox_image":"custom:v1","sandbox_extra_mounts":["/data:/data:ro"]}"#,
        ).expect("config should deserialize");
        assert!(!config.sandbox);
        assert_eq!(config.sandbox_image, "custom:v1");
        assert_eq!(config.sandbox_extra_mounts, vec!["/data:/data:ro"]);
    }

    #[test]
    fn config_deserializes_sandbox_defaults_when_absent() {
        let config: Config = serde_json::from_str(r#"{"builder_model":"opus"}"#)
            .expect("config should deserialize");
        assert!(config.sandbox);
        assert_eq!(config.sandbox_image, "foundry-sandbox:latest");
        assert!(config.sandbox_extra_mounts.is_empty());
    }

    #[test]
    fn model_override_collapses_all_role_models() {
        let dir = tempfile::tempdir().unwrap();
        fs::write(
            dir.path().join(".foundry.json"),
            r#"{"model":"opus"}"#,
        ).unwrap();
        let config = Config::load(dir.path());
        assert_eq!(config.model, "opus");
        assert_eq!(config.scout_model, "opus");
        assert_eq!(config.planner_model, "opus");
        assert_eq!(config.builder_model, "opus");
        assert_eq!(config.reviewer_model, "opus");
        assert_eq!(config.fixer_model, "opus");
        assert_eq!(config.discovery_model, "opus");
        assert_eq!(config.simple_planner_model, "opus");
        assert_eq!(config.simple_builder_model, "opus");
        assert_eq!(config.pattern_extraction_model, "opus");
    }

    #[test]
    fn empty_model_override_preserves_role_models() {
        let dir = tempfile::tempdir().unwrap();
        fs::write(
            dir.path().join(".foundry.json"),
            r#"{"scout_model":"haiku","builder_model":"opus"}"#,
        ).unwrap();
        let config = Config::load(dir.path());
        assert!(config.model.is_empty());
        assert_eq!(config.scout_model, "haiku");
        assert_eq!(config.builder_model, "opus");
    }

    #[test]
    fn config_deserializes_sandbox_auth_dirs_and_env() {
        let config: Config = serde_json::from_str(
            r#"{"sandbox_auth_dirs":[".claude",".copilot"],"sandbox_env":["ANTHROPIC_BASE_URL=http://localhost:8080"]}"#,
        ).expect("config should deserialize");
        assert_eq!(config.sandbox_auth_dirs, vec![".claude", ".copilot"]);
        assert_eq!(config.sandbox_env, vec!["ANTHROPIC_BASE_URL=http://localhost:8080"]);
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

    #[test]
    fn default_config_disables_require_human_approval() {
        assert!(!Config::default().require_human_approval);
    }

    #[test]
    fn config_deserializes_require_human_approval() {
        let config: Config = serde_json::from_str(r#"{"require_human_approval":true}"#)
            .expect("config should deserialize");
        assert!(config.require_human_approval);
    }

    #[test]
    fn pr_review_config_defaults_to_empty() {
        let config = Config::default();
        assert_eq!(config.pr_review_model, "");
        assert_eq!(config.pr_review_provider, "");
    }

    #[test]
    fn pr_review_config_deserializes_overrides() {
        let config: Config = serde_json::from_str(
            r#"{"pr_review_model":"opus","pr_review_provider":"claude"}"#,
        )
        .expect("config should deserialize");
        assert_eq!(config.pr_review_model, "opus");
        assert_eq!(config.pr_review_provider, "claude");
    }
}
