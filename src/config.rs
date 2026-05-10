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

fn default_catalog_refresh_secs() -> u64 {
    86400
}

fn default_history_retention_tasks() -> usize {
    50
}

fn default_agent_pane_split() -> u16 {
    50
}

#[derive(Debug, Clone, Deserialize, PartialEq, Eq)]
#[serde(default)]
pub struct PipelineStageConfig {
    pub id: String,
    pub label: String,
    #[serde(default = "default_true")]
    pub enabled: bool,
    #[serde(default)]
    pub prompt_override: Option<String>,
}

impl Default for PipelineStageConfig {
    fn default() -> Self {
        Self {
            id: String::new(),
            label: String::new(),
            enabled: true,
            prompt_override: None,
        }
    }
}

fn default_pipeline_stages() -> Vec<PipelineStageConfig> {
    vec![
        PipelineStageConfig {
            id: "query".into(),
            label: "QUERY".into(),
            enabled: true,
            prompt_override: None,
        },
        PipelineStageConfig {
            id: "research".into(),
            label: "RESEARCH".into(),
            enabled: true,
            prompt_override: None,
        },
        PipelineStageConfig {
            id: "plan".into(),
            label: "PLAN".into(),
            enabled: true,
            prompt_override: None,
        },
        PipelineStageConfig {
            id: "implement".into(),
            label: "BUILD".into(),
            enabled: true,
            prompt_override: None,
        },
        PipelineStageConfig {
            id: "doubt".into(),
            label: "AUDIT".into(),
            enabled: true,
            prompt_override: None,
        },
    ]
}

#[derive(Debug, Clone, Deserialize)]
#[serde(default)]
pub struct Config {
    pub scout_model: String,
    pub query_model: String,
    pub research_model: String,
    pub planner_model: String,
    pub builder_model: String,
    /// Dual-model execution: e.g. ["claude:opus", "codex:"].
    /// When len >= 2, overrides builder_model/builder_provider.
    /// Format: "provider:model" where provider is "claude" or "codex".
    pub builder_models: Vec<String>,
    /// Dual-build selection: "first", "second", "both", or empty (off).
    /// Ctrl+D cycles through model[0]-only, model[1]-only, both pipelines.
    pub dual_selection: String,
    /// Snapshot of `builder_models` taken when a local model was selected via
    /// `save_builder_routing`. Restored by `clear_builder_routing` so picking
    /// a local model and then switching back to a configured spec does not
    /// lose the user's prior dual-pipeline configuration. Read/written through
    /// raw JSON manipulation in `save_builder_routing`/`clear_builder_routing`.
    #[serde(default)]
    #[allow(dead_code)]
    pub prev_builder_models: Vec<String>,
    /// Snapshot of `dual_selection` taken when a local model was selected via
    /// `save_builder_routing`. Restored by `clear_builder_routing`. Read/written
    /// through raw JSON manipulation in `save_builder_routing`/`clear_builder_routing`.
    #[serde(default)]
    #[allow(dead_code)]
    pub prev_dual_selection: String,
    /// Snapshot of `arena_mode` taken when a local model was selected via
    /// `save_builder_routing`. Restored by `clear_builder_routing` so picking
    /// a local model from a dual-arena config and switching back returns the
    /// user to dual mode instead of stranding them in solo.
    #[serde(default)]
    #[allow(dead_code)]
    pub prev_arena_mode: String,
    pub reviewer_model: String,
    pub fixer_model: String,
    pub discovery_model: String,

    /// Provider per build-loop role: "claude" (default) or "codex".
    pub scout_provider: String,
    pub query_provider: String,
    pub research_provider: String,
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

    /// Directory for build history JSONL log (cross-session recall).
    pub history_dir: String,

    /// Days of inactivity before a pattern's auto_apply is disabled.
    /// 0 disables time-based decay entirely.
    pub pattern_decay_days: i64,

    /// Max number of history search results injected into scout prompts.
    pub history_search_results: usize,

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

    /// Selected local model (LM Studio or Ollama). Empty = none selected.
    /// Written by Settings overlay Left/Right on Builder Arena row.
    #[serde(default)]
    pub local_model: String,

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
    /// Provider for pattern extraction. Defaults to "claude".
    pub pattern_extraction_provider: String,

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

    /// Percentage of the running-screen middle row given to the agent output
    /// pane (default 50, valid range 20-80). Persisted to ~/.foundry/config.json
    /// when the user drags the vertical separator on the running screen.
    #[serde(default = "default_agent_pane_split")]
    pub agent_pane_split: u16,

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

    /// Maximum number of per-task subdirectories retained under
    /// `.buildloop/history/`. On each task cleanup, prior-run artifacts are
    /// archived to `.buildloop/history/<task_id>/<UTC-timestamp>/`; once the
    /// number of `<task_id>` subdirectories exceeds this cap, the oldest are
    /// pruned (best-effort). 0 disables pruning. Default: 50.
    #[serde(default = "default_history_retention_tasks")]
    pub history_retention_tasks: usize,

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
    #[serde(default = "default_true")]
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
    #[serde(default = "default_true")]
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

    /// Max concurrent per-file review agents in multipass PR review.
    /// 1 = sequential (original behavior). Default: 4.
    pub pr_review_concurrency: usize,

    /// Port for the `foundry dashboard` web server (default: 9400).
    /// Serves only on localhost (127.0.0.1).
    pub dashboard_port: u16,

    /// Doubt stage execution engine: "claude" (default) or "codex".
    /// "claude" runs the reviewer as a Claude sub-agent (current behavior).
    /// "codex" launches Codex as a separate process: `codex exec` audits and
    /// fixes HIGH/MEDIUM issues, then `codex review --uncommitted` does an
    /// independent diff review. Both write findings to .buildloop/review-report.md.
    /// Override with FOUNDRY_DOUBT_ENGINE env var.
    pub doubt_engine: String,

    /// RPID pipeline stage list rendered in the TUI pipeline map. Stage order
    /// here is display-only: the build-loop dispatch sequence remains hardcoded.
    /// Missing from JSON -> 5-stage RPID default (query, research, plan, implement, doubt).
    /// Accepts either "pipeline_stages" or the shorter "stages" key.
    #[serde(alias = "stages")]
    pub pipeline_stages: Vec<PipelineStageConfig>,

    /// Optional shell command run after each successful task commit.
    /// Receives FOUNDRY_TASK_ID, FOUNDRY_TASK_STATUS (feat|WIP),
    /// FOUNDRY_TASK_DESC (first 100 chars), FOUNDRY_COMMIT_SHA via env.
    /// Runs fire-and-forget; non-zero exit logs a warning but does not block.
    /// None (default) means no hook is invoked.
    #[serde(default)]
    pub on_task_complete: Option<String>,

    /// Per-stage routing overrides. When a stage id is in this list, that stage
    /// keeps its own *_provider / *_model fields even when for_pipeline() would
    /// override them with the global builder selection. Allows mixing providers
    /// across the pipeline (e.g. Claude for Plan, Codex for Build, Claude for Audit).
    #[serde(default)]
    pub stage_overrides: Vec<String>,

    /// Background catalog refresh cadence in seconds. 0 disables refresh entirely
    /// (the on-disk catalog or baseline is used as-is). Default 86400 (24h).
    #[serde(default = "default_catalog_refresh_secs")]
    pub model_catalog_refresh_secs: u64,

    /// Map of provider -> URL override for model catalog sources. Keys: "anthropic",
    /// "openai". When set, the catalog refresher hits this URL instead of the
    /// provider default. Useful for internal mirrors. Empty by default.
    #[serde(default)]
    pub model_catalog_url_overrides: std::collections::HashMap<String, String>,

    /// Arena mode: "solo" (one pipeline) or "dual" (two parallel pipelines).
    #[serde(default)]
    pub arena_mode: String,

    // Pipeline B per-stage routing (used only in dual mode).
    #[serde(default)]
    pub b_scout_provider: String,
    #[serde(default)]
    pub b_scout_model: String,
    #[serde(default)]
    pub b_query_provider: String,
    #[serde(default)]
    pub b_query_model: String,
    #[serde(default)]
    pub b_research_provider: String,
    #[serde(default)]
    pub b_research_model: String,
    #[serde(default)]
    pub b_planner_provider: String,
    #[serde(default)]
    pub b_planner_model: String,
    #[serde(default)]
    pub b_builder_provider: String,
    #[serde(default)]
    pub b_builder_model: String,
    #[serde(default)]
    pub b_reviewer_provider: String,
    #[serde(default)]
    pub b_reviewer_model: String,
    #[serde(default)]
    pub b_fixer_provider: String,
    #[serde(default)]
    pub b_fixer_model: String,
    #[serde(default)]
    pub b_discovery_provider: String,
    #[serde(default)]
    pub b_discovery_model: String,
    #[serde(default)]
    pub b_pr_review_provider: String,
    #[serde(default)]
    pub b_pr_review_model: String,
    #[serde(default)]
    pub b_pattern_extraction_provider: String,
    #[serde(default)]
    pub b_pattern_extraction_model: String,
}

impl Default for Config {
    fn default() -> Self {
        Self {
            scout_model: "sonnet".into(),
            query_model: "sonnet".into(),
            research_model: "sonnet".into(),
            planner_model: "opus".into(),
            builder_model: "opus".into(),
            builder_models: Vec::new(),
            dual_selection: "first".into(),
            prev_builder_models: Vec::new(),
            prev_dual_selection: String::new(),
            prev_arena_mode: String::new(),
            reviewer_model: "sonnet".into(),
            fixer_model: "sonnet".into(),
            discovery_model: "opus".into(),

            scout_provider: "claude".into(),
            query_provider: "claude".into(),
            research_provider: "claude".into(),
            planner_provider: "claude".into(),
            builder_provider: "claude".into(),
            reviewer_provider: "claude".into(),
            fixer_provider: "claude".into(),
            discovery_provider: "claude".into(),

            pause_between_tasks_secs: 10,
            pause_between_agents_secs: 3,
            pause_between_cycles_secs: 30,

            agent_timeout_secs: 600, // 10 minutes idle; hard timeout = 4x = 40 minutes. Opus on a fresh complex prompt routinely thinks for >3 min before emitting tool calls; the prior 180s default produced timeouts and infinite WIP retries on planning-heavy tasks.

            patterns_dir: "~/.foundry/patterns".into(),
            history_dir: "~/.foundry/history".into(),
            pattern_decay_days: 90,
            history_search_results: 5,

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
            local_model: String::new(),
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
            pattern_extraction_provider: "claude".into(),
            run_mode: "auto".into(),
            pipeline_mode: "full".into(),
            batch_doubt: true,
            extensions: Vec::new(),
            create_issue_on_wip: false,
            preview_wrap: false,
            agent_pane_split: 50,
            pr_poll_interval_secs: 30,
            theme: "dark".into(),
            truecolor: None,
            build_command: None,
            cost_limit: 0.0,
            auto_archive_tasks: true,
            archive_keep_first: 3,
            archive_keep_last: 3,
            history_retention_tasks: 50,
            review_multipass_threshold: 8,
            confidence_threshold: 0.5,
            parallel_builder: false,
            parallel_builder_min_files: 3,
            agent_backend: "pty".into(),
            tmux_session_prefix: "foundry".into(),
            tmux_keep_sessions: false,
            phase_isolation: true,
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
            enforce_phase_rbac: true,
            pr_review_model: String::new(),
            pr_review_provider: String::new(),
            pr_review_multipass_threshold: 0,
            pr_review_concurrency: 4,
            dashboard_port: 9400,
            doubt_engine: "claude".into(),
            pipeline_stages: default_pipeline_stages(),
            on_task_complete: None,
            stage_overrides: Vec::new(),
            model_catalog_refresh_secs: 86400,
            model_catalog_url_overrides: std::collections::HashMap::new(),
            arena_mode: "solo".into(),
            b_scout_provider: String::new(),
            b_scout_model: String::new(),
            b_query_provider: String::new(),
            b_query_model: String::new(),
            b_research_provider: String::new(),
            b_research_model: String::new(),
            b_planner_provider: String::new(),
            b_planner_model: String::new(),
            b_builder_provider: String::new(),
            b_builder_model: String::new(),
            b_reviewer_provider: String::new(),
            b_reviewer_model: String::new(),
            b_fixer_provider: String::new(),
            b_fixer_model: String::new(),
            b_discovery_provider: String::new(),
            b_discovery_model: String::new(),
            b_pr_review_provider: String::new(),
            b_pr_review_model: String::new(),
            b_pattern_extraction_provider: String::new(),
            b_pattern_extraction_model: String::new(),
        }
    }
}

impl Config {
    fn stage_ids_match(lhs: &str, rhs: &str) -> bool {
        lhs == rhs
            || matches!(
                (lhs, rhs),
                ("build", "implement")
                    | ("implement", "build")
                    | ("audit", "doubt")
                    | ("doubt", "audit")
                    | ("discovery", "discover")
                    | ("discover", "discovery")
                    | ("pattern_extraction", "patterns")
                    | ("patterns", "pattern_extraction")
            )
    }

    fn stage_is_overridden(&self, stage_id: &str) -> bool {
        self.stage_overrides
            .iter()
            .any(|candidate| Self::stage_ids_match(candidate, stage_id))
    }

    fn normalize_doubt_engine_value(value: &str) -> Option<&'static str> {
        match value.trim().to_ascii_lowercase().as_str() {
            "claude" => Some("claude"),
            "codex" => Some("codex"),
            _ => None,
        }
    }

    /// Return the configured label for a pipeline stage by id.
    /// Falls back to `id.to_ascii_uppercase()` if the stage is not present.
    pub fn pipeline_stage_label(&self, id: &str) -> String {
        self.pipeline_stages
            .iter()
            .find(|s| s.id == id)
            .map(|s| s.label.clone())
            .unwrap_or_else(|| id.to_ascii_uppercase())
    }

    /// Return whether a pipeline stage is present and enabled.
    /// A stage missing from `pipeline_stages` is treated as disabled.
    pub fn pipeline_stage_enabled(&self, id: &str) -> bool {
        self.pipeline_stages
            .iter()
            .find(|s| s.id == id)
            .map(|s| s.enabled)
            .unwrap_or(false)
    }

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
            self.query_model = m.clone();
            self.research_model = m.clone();
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
        // Clamp concurrency to at least 1 (JSON config can bypass env var >= 1 check)
        self.pr_review_concurrency = self.pr_review_concurrency.max(1);
        match Self::normalize_doubt_engine_value(&self.doubt_engine) {
            Some(engine) => self.doubt_engine = engine.to_string(),
            None => {
                eprintln!(
                    "warning: doubt_engine={:?} is not supported -- defaulting to \"claude\"",
                    self.doubt_engine
                );
                self.doubt_engine = "claude".into();
            }
        }
    }

    fn apply_env_overrides(&mut self) {
        if let Ok(val) = std::env::var("FOUNDRY_PR_REVIEW_MODEL") {
            if !val.is_empty() {
                self.pr_review_model = val;
            }
        }
        if let Ok(val) = std::env::var("FOUNDRY_PR_REVIEW_PROVIDER") {
            if !val.is_empty() {
                self.pr_review_provider = val;
            }
        }
        if let Ok(val) = std::env::var("FOUNDRY_AGENT_TIMEOUT_SECS") {
            if !val.is_empty() {
                match val.parse::<u64>() {
                    Ok(n) => self.agent_timeout_secs = n,
                    Err(_) => {
                        eprintln!("warning: FOUNDRY_AGENT_TIMEOUT_SECS={val:?} is not a valid u64 -- ignoring");
                    }
                }
            }
        }
        if let Ok(val) = std::env::var("FOUNDRY_PR_REVIEW_MULTIPASS_THRESHOLD") {
            if !val.is_empty() {
                match val.parse::<usize>() {
                    Ok(n) => self.pr_review_multipass_threshold = n,
                    Err(_) => {
                        eprintln!("warning: FOUNDRY_PR_REVIEW_MULTIPASS_THRESHOLD={val:?} is not a valid usize -- ignoring");
                    }
                }
            }
        }
        if let Ok(val) = std::env::var("FOUNDRY_PR_REVIEW_CONCURRENCY") {
            if !val.is_empty() {
                match val.parse::<usize>() {
                    Ok(n) if n >= 1 => self.pr_review_concurrency = n,
                    Ok(_) => {
                        eprintln!(
                            "warning: FOUNDRY_PR_REVIEW_CONCURRENCY must be >= 1 -- ignoring"
                        );
                    }
                    Err(_) => {
                        eprintln!("warning: FOUNDRY_PR_REVIEW_CONCURRENCY={val:?} is not a valid usize -- ignoring");
                    }
                }
            }
        }
        // FOUNDRY_DOUBT_ENGINE mirrors the DOUBT_ENGINE var from CLAUDE.md run-loop usage.
        // Both names are accepted so shell exports work in both contexts.
        for var in &["FOUNDRY_DOUBT_ENGINE", "DOUBT_ENGINE"] {
            if let Ok(val) = std::env::var(var) {
                if !val.is_empty() {
                    match Self::normalize_doubt_engine_value(&val) {
                        Some(engine) => {
                            self.doubt_engine = engine.to_string();
                            break;
                        }
                        None => {
                            eprintln!("warning: {}={:?} is not supported -- ignoring", var, val);
                        }
                    }
                }
            }
        }
    }

    pub fn load(project_dir: &Path) -> Self {
        let global_path = Self::global_config_path();
        let project_path = project_dir.join(".foundry.json");

        let global_val = global_path.as_deref().and_then(Self::read_json_file);
        let project_val = Self::read_json_file(&project_path);

        let merged = match (global_val, project_val) {
            (Some(g), Some(p)) => Some(Self::merge_json(g, p)),
            (Some(g), None) => Some(g),
            (None, Some(p)) => Some(p),
            (None, None) => None,
        };

        let mut config = match merged {
            Some(val) => serde_json::from_value::<Self>(val).unwrap_or_else(|e| {
                eprintln!("warning: failed to deserialize config: {e} -- using defaults");
                Self::default()
            }),
            None => Self::default(),
        };
        config.normalize();
        config.apply_env_overrides();
        config
    }

    /// Load config from global `~/.foundry/config.json` only, ignoring any
    /// project-level `.foundry.json`. Used by CI workflows to prevent untrusted
    /// PR branches from influencing review config.
    pub fn load_global_only() -> Self {
        let global_path = Self::global_config_path();
        let global_val = global_path.as_deref().and_then(Self::read_json_file);

        let mut config = match global_val {
            Some(val) => serde_json::from_value::<Self>(val).unwrap_or_else(|e| {
                eprintln!("warning: failed to deserialize global config: {e} -- using defaults");
                Self::default()
            }),
            None => Self::default(),
        };
        config.normalize();
        config.apply_env_overrides();
        config
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

    /// Parse a provider string ("claude", "codex", "opencode", or "ghcopilot") into a
    /// ModelProvider. Falls back to Claude for unrecognized values.
    pub fn parse_provider(value: &str) -> ModelProvider {
        match value.trim().to_lowercase().as_str() {
            "codex" => ModelProvider::Codex,
            "opencode" => ModelProvider::OpenCode,
            "ghcopilot" | "gh-copilot" | "github-copilot" | "copilot" => ModelProvider::GhCopilot,
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
            ModelProvider::Claude => {
                let model = model.trim();
                if model.is_empty() {
                    "Claude".to_string()
                } else {
                    let tier = match model {
                        "opus" | "claude-opus-4-7" => "Opus",
                        "sonnet" | "claude-sonnet-4-6" => "Sonnet",
                        "haiku" | "claude-haiku-4-5" => "Haiku",
                        other => other,
                    };
                    format!("Claude {tier}")
                }
            }
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
            ModelProvider::OpenCode => {
                let model = model.trim();
                if model.is_empty() {
                    provider.to_string()
                } else {
                    // Model is "provider/name" (e.g. "lmstudio/qwen3.6-35b-a3b").
                    // Show just the tail after the last slash for brevity.
                    let tail = model.rsplit('/').next().unwrap_or(model);
                    format!("{provider} {tail}")
                }
            }
            ModelProvider::GhCopilot => {
                let model = model.trim();
                if model.is_empty() {
                    provider.to_string()
                } else {
                    format!("{provider} {model}")
                }
            }
        }
    }

    /// Expand a short model tier ("opus", "sonnet", "haiku") to its full model ID.
    /// Returns the input unchanged if it's already a full ID or unrecognized.
    pub fn expand_model_tier(model: &str) -> &'static str {
        match model {
            "opus" => "claude-opus-4-7",
            "sonnet" => "claude-sonnet-4-6",
            "haiku" => "claude-haiku-4-5",
            _ => "",
        }
    }

    /// Human-readable label for a spec string, expanding tier names to full IDs.
    /// "claude:opus"           -> "claude-opus-4-7"  (provider prefix dropped, tier expanded)
    /// "codex:"                -> "codex"
    /// "claude:claude-opus-4-7" -> "claude-opus-4-7" (already full, provider prefix dropped)
    pub fn readable_spec(spec: &str) -> String {
        let (provider, model) = Self::parse_model_spec(spec);
        if model.is_empty() {
            // e.g. "codex:" -> "codex"
            return provider;
        }
        let expanded = Self::expand_model_tier(&model);
        let effective_model = if expanded.is_empty() {
            model.as_str()
        } else {
            expanded
        };
        // Drop the provider prefix when it's redundant (model ID already starts with provider name)
        if effective_model.starts_with(&provider) || provider == "claude" {
            effective_model.to_string()
        } else {
            format!("{provider}:{effective_model}")
        }
    }

    /// Persist the preview wrap preference to .foundry.json without
    /// overwriting other config fields.
    pub fn save_preview_wrap(project_dir: &Path, wrap: bool) {
        let config_path = project_dir.join(".foundry.json");
        let content = std::fs::read_to_string(&config_path).unwrap_or_else(|_| "{}".to_string());
        let mut value: serde_json::Value = serde_json::from_str(&content).unwrap_or_else(|e| {
            eprintln!(
                "warning: {} contains invalid JSON ({e}) -- existing settings will be lost",
                config_path.display(),
            );
            serde_json::json!({})
        });
        value["preview_wrap"] = serde_json::json!(wrap);
        let json = serde_json::to_string_pretty(&value).unwrap_or_default();
        if let Err(e) = crate::utils::atomic_write_file(&config_path, json.as_bytes()) {
            eprintln!(
                "warning: failed to save preview_wrap to {} -- change will not persist across restarts: {e}",
                config_path.display(),
            );
        }
    }

    pub fn save_extensions(project_dir: &Path, extensions: &[String]) {
        let config_path = project_dir.join(".foundry.json");
        let content = std::fs::read_to_string(&config_path).unwrap_or_else(|_| "{}".to_string());
        let mut value: serde_json::Value = serde_json::from_str(&content).unwrap_or_else(|e| {
            eprintln!(
                "warning: {} contains invalid JSON ({e}) -- existing settings will be lost",
                config_path.display(),
            );
            serde_json::json!({})
        });
        value["extensions"] = serde_json::json!(extensions);
        let json = serde_json::to_string_pretty(&value).unwrap_or_default();
        if let Err(e) = crate::utils::atomic_write_file(&config_path, json.as_bytes()) {
            eprintln!(
                "warning: failed to save extensions to {} -- change will not persist across restarts: {e}",
                config_path.display(),
            );
        }
    }

    /// Persist the run_mode to .foundry.json without overwriting other config fields.
    /// Also removes the legacy "mode" key if present, to prevent it from shadowing.
    pub fn save_run_mode(project_dir: &Path, run_mode: &str) {
        let config_path = project_dir.join(".foundry.json");
        let content = std::fs::read_to_string(&config_path).unwrap_or_else(|_| "{}".to_string());
        let mut value: serde_json::Value = serde_json::from_str(&content).unwrap_or_else(|e| {
            eprintln!(
                "warning: {} contains invalid JSON ({e}) -- existing settings will be lost",
                config_path.display(),
            );
            serde_json::json!({})
        });
        value["run_mode"] = serde_json::json!(run_mode);
        // Remove legacy "mode" key to prevent it from shadowing "run_mode"
        // when JSON is reordered or parsed by a different library.
        if let Some(obj) = value.as_object_mut() {
            obj.remove("mode");
        }
        let json = serde_json::to_string_pretty(&value).unwrap_or_default();
        if let Err(e) = crate::utils::atomic_write_file(&config_path, json.as_bytes()) {
            eprintln!(
                "warning: failed to save run_mode to {} -- change will not persist across restarts: {e}",
                config_path.display(),
            );
        }
    }

    pub fn save_dual_selection(project_dir: &Path, selection: &str) {
        let config_path = project_dir.join(".foundry.json");
        let content = std::fs::read_to_string(&config_path).unwrap_or_else(|_| "{}".to_string());
        let mut value: serde_json::Value = serde_json::from_str(&content).unwrap_or_else(|e| {
            eprintln!(
                "warning: {} contains invalid JSON ({e}) -- existing settings will be lost",
                config_path.display(),
            );
            serde_json::json!({})
        });
        value["dual_selection"] = serde_json::json!(selection);
        let json = serde_json::to_string_pretty(&value).unwrap_or_default();
        if let Err(e) = crate::utils::atomic_write_file(&config_path, json.as_bytes()) {
            eprintln!(
                "warning: failed to save dual_selection to {} -- change will not persist across restarts: {e}",
                config_path.display(),
            );
        }
    }

    /// Persist the theme to .foundry.json without overwriting other config fields.
    pub fn save_theme(project_dir: &Path, theme_name: &str) {
        let config_path = project_dir.join(".foundry.json");
        let content = std::fs::read_to_string(&config_path).unwrap_or_else(|_| "{}".to_string());
        let mut value: serde_json::Value = serde_json::from_str(&content).unwrap_or_else(|e| {
            eprintln!(
                "warning: {} contains invalid JSON ({e}) -- existing settings will be lost",
                config_path.display(),
            );
            serde_json::json!({})
        });
        value["theme"] = serde_json::json!(theme_name);
        let json = serde_json::to_string_pretty(&value).unwrap_or_default();
        if let Err(e) = crate::utils::atomic_write_file(&config_path, json.as_bytes()) {
            eprintln!(
                "warning: failed to save theme to {} -- change will not persist across restarts: {e}",
                config_path.display(),
            );
        }
    }

    /// Persist the selected local model to .foundry.json without overwriting other fields.
    pub fn save_local_model(project_dir: &Path, model: &str) {
        let config_path = project_dir.join(".foundry.json");
        let content = std::fs::read_to_string(&config_path).unwrap_or_else(|_| "{}".to_string());
        let mut value: serde_json::Value = serde_json::from_str(&content).unwrap_or_else(|e| {
            eprintln!(
                "warning: {} contains invalid JSON ({e}) -- existing settings will be lost",
                config_path.display(),
            );
            serde_json::json!({})
        });
        value["local_model"] = serde_json::json!(model);
        let json = serde_json::to_string_pretty(&value).unwrap_or_default();
        if let Err(e) = crate::utils::atomic_write_file(&config_path, json.as_bytes()) {
            eprintln!(
                "warning: failed to save local_model to {} -- change will not persist across restarts: {e}",
                config_path.display(),
            );
        }
    }

    /// Persist `builder_provider` and `builder_model` to .foundry.json without
    /// overwriting any other config fields. Also writes `builder_models` and
    /// `dual_selection` so `selected_pipeline_configs("first")` routes the
    /// pipeline through `for_pipeline("opencode:<model>")` and overrides every
    /// stage provider. The pre-local `builder_models`/`dual_selection` is
    /// snapshotted into `prev_builder_models`/`prev_dual_selection` so
    /// `clear_builder_routing` can restore it.
    pub fn save_builder_routing(project_dir: &Path, provider: &str, model: &str) {
        let config_path = project_dir.join(".foundry.json");
        let content = std::fs::read_to_string(&config_path).unwrap_or_else(|_| "{}".to_string());
        let mut value: serde_json::Value = serde_json::from_str(&content).unwrap_or_else(|e| {
            eprintln!(
                "warning: {} contains invalid JSON ({e}) -- existing settings will be lost",
                config_path.display(),
            );
            serde_json::json!({})
        });
        let new_spec = format!("{}:{}", provider, model);
        let current_models: Vec<String> = value
            .get("builder_models")
            .and_then(|v| v.as_array())
            .map(|arr| {
                arr.iter()
                    .filter_map(|e| e.as_str().map(String::from))
                    .collect()
            })
            .unwrap_or_default();
        let current_selection: String = value
            .get("dual_selection")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();
        let current_arena: String = value
            .get("arena_mode")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();
        let prev_models: Vec<String> = value
            .get("prev_builder_models")
            .and_then(|v| v.as_array())
            .map(|arr| {
                arr.iter()
                    .filter_map(|e| e.as_str().map(String::from))
                    .collect()
            })
            .unwrap_or_default();
        let current_is_local = current_models.len() == 1
            && current_models
                .first()
                .map(|s| s.starts_with("opencode:"))
                .unwrap_or(false);
        let prev_already_recorded = !prev_models.is_empty();
        if !current_is_local && !prev_already_recorded {
            value["prev_builder_models"] = serde_json::json!(current_models);
            value["prev_dual_selection"] = serde_json::json!(current_selection);
            value["prev_arena_mode"] = serde_json::json!(current_arena);
        }
        value["builder_models"] = serde_json::json!(vec![new_spec.clone()]);
        value["dual_selection"] = serde_json::json!("first");
        value["arena_mode"] = serde_json::json!("solo");
        value["builder_provider"] = serde_json::json!(provider);
        value["builder_model"] = serde_json::json!(model);
        let json = serde_json::to_string_pretty(&value).unwrap_or_default();
        if let Err(e) = crate::utils::atomic_write_file(&config_path, json.as_bytes()) {
            eprintln!(
                "warning: failed to save builder_routing to {} -- change will not persist across restarts: {e}",
                config_path.display(),
            );
        }
    }

    /// Undo a `save_builder_routing` call: restore the snapshotted
    /// `builder_models`/`dual_selection` and reset `builder_provider`/
    /// `builder_model` to defaults so the user returns cleanly to their
    /// pre-local dual config.
    pub fn clear_builder_routing(project_dir: &Path) {
        let config_path = project_dir.join(".foundry.json");
        let content = std::fs::read_to_string(&config_path).unwrap_or_else(|_| "{}".to_string());
        let mut value: serde_json::Value = serde_json::from_str(&content).unwrap_or_else(|e| {
            eprintln!(
                "warning: {} contains invalid JSON ({e}) -- existing settings will be lost",
                config_path.display(),
            );
            serde_json::json!({})
        });
        let prev_models: Vec<String> = value
            .get("prev_builder_models")
            .and_then(|v| v.as_array())
            .map(|arr| {
                arr.iter()
                    .filter_map(|e| e.as_str().map(String::from))
                    .collect()
            })
            .unwrap_or_default();
        let prev_selection: String = value
            .get("prev_dual_selection")
            .and_then(|v| v.as_str())
            .unwrap_or("")
            .to_string();
        let prev_arena: Option<String> = value
            .get("prev_arena_mode")
            .and_then(|v| v.as_str())
            .map(String::from);

        // D2.9: only restore from snapshot when one actually exists. Without
        // this guard, calling clear_builder_routing on a tree that's already
        // a dual config (no local-override snapshot present) would set
        // builder_models = [] and strand the user with no way back to dual
        // routing except hand-editing .foundry.json. Callers in
        // apply_builder_selection invoke this on every non-local selection,
        // not just when undoing a local override, so the no-snapshot path
        // must be a true no-op.
        if prev_models.is_empty() {
            return;
        }

        value["builder_models"] = serde_json::json!(prev_models);
        if prev_selection.is_empty() {
            value["dual_selection"] = serde_json::json!("first");
        } else {
            value["dual_selection"] = serde_json::json!(prev_selection);
        }
        if let Some(arena) = prev_arena {
            value["arena_mode"] = serde_json::json!(arena);
        }
        if let Some(obj) = value.as_object_mut() {
            obj.remove("prev_builder_models");
            obj.remove("prev_dual_selection");
            obj.remove("prev_arena_mode");
        }
        value["builder_provider"] = serde_json::json!("claude");
        value["builder_model"] = serde_json::json!("opus");
        let json = serde_json::to_string_pretty(&value).unwrap_or_default();
        if let Err(e) = crate::utils::atomic_write_file(&config_path, json.as_bytes()) {
            eprintln!(
                "warning: failed to save builder_routing to {} -- change will not persist across restarts: {e}",
                config_path.display(),
            );
        }
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

        if lower.starts_with("lmstudio/")
            || lower.starts_with("ollama/")
            || lower.starts_with("opencode/")
        {
            return Some(ModelProvider::OpenCode);
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
        // Only override stages NOT in stage_overrides
        if !self.stage_is_overridden("scout") {
            config.scout_provider = provider.clone();
        }
        if !self.stage_is_overridden("query") {
            config.query_provider = provider.clone();
        }
        if !self.stage_is_overridden("research") {
            config.research_provider = provider.clone();
        }
        if !self.stage_is_overridden("plan") {
            config.planner_provider = provider.clone();
        }
        if !self.stage_is_overridden("build") {
            config.builder_provider = provider.clone();
        }
        if !self.stage_is_overridden("audit") {
            config.reviewer_provider = provider.clone();
        }
        if !self.stage_is_overridden("fixer") {
            config.fixer_provider = provider.clone();
        }
        if !self.stage_is_overridden("discovery") {
            config.discovery_provider = provider.clone();
        }
        if provider_kind == ModelProvider::OpenCode {
            if !self.stage_is_overridden("scout") {
                config.scout_model = model.clone();
            }
            if !self.stage_is_overridden("query") {
                config.query_model = model.clone();
            }
            if !self.stage_is_overridden("research") {
                config.research_model = model.clone();
            }
            if !self.stage_is_overridden("plan") {
                config.planner_model = model.clone();
            }
            if !self.stage_is_overridden("build") {
                config.builder_model = model.clone();
            }
            if !self.stage_is_overridden("audit") {
                config.reviewer_model = model.clone();
            }
            if !self.stage_is_overridden("fixer") {
                config.fixer_model = model.clone();
            }
            if !self.stage_is_overridden("discovery") {
                config.discovery_model = model.clone();
            }
        } else {
            if !self.stage_is_overridden("scout") {
                config.scout_model =
                    Self::normalize_model_for_provider(provider_kind, &self.scout_model);
            }
            if !self.stage_is_overridden("query") {
                config.query_model =
                    Self::normalize_model_for_provider(provider_kind, &self.query_model);
            }
            if !self.stage_is_overridden("research") {
                config.research_model =
                    Self::normalize_model_for_provider(provider_kind, &self.research_model);
            }
            if !self.stage_is_overridden("plan") {
                config.planner_model =
                    Self::normalize_model_for_provider(provider_kind, &self.planner_model);
            }
            if !self.stage_is_overridden("build") {
                config.builder_model = model;
            }
            if !self.stage_is_overridden("audit") {
                config.reviewer_model =
                    Self::normalize_model_for_provider(provider_kind, &self.reviewer_model);
            }
            if !self.stage_is_overridden("fixer") {
                config.fixer_model =
                    Self::normalize_model_for_provider(provider_kind, &self.fixer_model);
            }
            if !self.stage_is_overridden("discovery") {
                config.discovery_model =
                    Self::normalize_model_for_provider(provider_kind, &self.discovery_model);
            }
        }
        // Disable dual in the forked config so process_task runs single-pipeline
        config.builder_models.clear();
        config.dual_selection.clear();
        config
    }

    /// Return the effective pipeline configs for the active dual selection.
    /// Single-selection modes return one config; dual mode returns two.
    pub fn selected_pipeline_configs(&self, selection: &str) -> Vec<Config> {
        // New arena_mode-based routing: "dual" uses per-stage B fields
        if self.arena_mode == "dual" {
            let mut a = self.clone();
            a.arena_mode = "solo".into();
            a.builder_models.clear();
            a.dual_selection.clear();
            return vec![a, self.pipeline_b_config()];
        }
        // Legacy builder_models-based routing
        match selection {
            "first" if !self.builder_models.is_empty() => {
                vec![self.for_pipeline(&self.builder_models[0])]
            }
            "second" if self.builder_models.len() >= 2 => {
                vec![self.for_pipeline(&self.builder_models[1])]
            }
            "third" if self.builder_models.len() >= 3 => {
                vec![self.for_pipeline(&self.builder_models[2])]
            }
            _ => vec![self.clone()],
        }
    }

    /// Return (role_name, provider, model) tuples for all build-loop roles.
    pub fn role_configs(&self) -> Vec<(&str, &str, &str)> {
        vec![
            ("Scout", &self.scout_provider, &self.scout_model),
            ("Query", &self.query_provider, &self.query_model),
            ("Research", &self.research_provider, &self.research_model),
            ("Plan", &self.planner_provider, &self.planner_model),
            ("Implement", &self.builder_provider, &self.builder_model),
            ("Reviewer", &self.reviewer_provider, &self.reviewer_model),
            ("Fixer", &self.fixer_provider, &self.fixer_model),
            ("Discovery", &self.discovery_provider, &self.discovery_model),
            (
                "Patterns",
                &self.pattern_extraction_provider,
                &self.pattern_extraction_model,
            ),
            ("Add Tasks", "claude", "sonnet"),
        ]
    }

    /// Resolve the effective (provider, model) for a pipeline stage.
    ///
    /// Resolution order:
    /// 1. If stage_id is in stage_overrides, use the stage's own fields.
    /// 2. Otherwise use the stage's own fields (which may have been overridden
    ///    by for_pipeline() if a global builder routing is active).
    ///
    /// This is the single source of truth. TUI display and agent dispatch
    /// should both call this rather than reading *_provider / *_model directly.
    pub fn active_routing_for_stage(&self, stage_id: &str) -> (String, String) {
        match stage_id {
            "scout" => (self.scout_provider.clone(), self.scout_model.clone()),
            "query" => (self.query_provider.clone(), self.query_model.clone()),
            "research" => (self.research_provider.clone(), self.research_model.clone()),
            "plan" => (self.planner_provider.clone(), self.planner_model.clone()),
            "build" | "implement" => (self.builder_provider.clone(), self.builder_model.clone()),
            "audit" | "doubt" => (self.reviewer_provider.clone(), self.reviewer_model.clone()),
            "discovery" | "discover" => (
                self.discovery_provider.clone(),
                self.discovery_model.clone(),
            ),
            "pr_review" => {
                let p = if self.pr_review_provider.is_empty() {
                    self.reviewer_provider.clone()
                } else {
                    self.pr_review_provider.clone()
                };
                let m = if self.pr_review_model.is_empty() {
                    self.reviewer_model.clone()
                } else {
                    self.pr_review_model.clone()
                };
                (p, m)
            }
            "pattern_extraction" | "patterns" => (
                self.pattern_extraction_provider.clone(),
                self.pattern_extraction_model.clone(),
            ),
            "fixer" => (self.fixer_provider.clone(), self.fixer_model.clone()),
            _ => (self.builder_provider.clone(), self.builder_model.clone()),
        }
    }

    /// Write a per-stage routing override to .foundry.json and ensure the stage
    /// is added to `stage_overrides`.
    pub fn set_stage_routing(project_dir: &Path, stage_id: &str, provider: &str, model: &str) {
        let config_path = project_dir.join(".foundry.json");
        let content = std::fs::read_to_string(&config_path).unwrap_or_else(|_| "{}".to_string());
        let mut value: serde_json::Value =
            serde_json::from_str(&content).unwrap_or_else(|_| serde_json::json!({}));

        let (prov_key, model_key) = Self::stage_field_keys(stage_id);
        value[prov_key] = serde_json::json!(provider);
        value[model_key] = serde_json::json!(model);

        // Ensure stage_id is in stage_overrides
        let overrides = value
            .get_mut("stage_overrides")
            .and_then(|v| v.as_array_mut());
        if let Some(arr) = overrides {
            let sid = serde_json::Value::String(stage_id.to_string());
            if !arr.iter().any(|value| {
                value
                    .as_str()
                    .is_some_and(|candidate| Self::stage_ids_match(candidate, stage_id))
            }) {
                arr.push(sid);
            }
        } else {
            value["stage_overrides"] = serde_json::json!([stage_id]);
        }

        let json = serde_json::to_string_pretty(&value).unwrap_or_default();
        if let Err(e) = crate::utils::atomic_write_file(&config_path, json.as_bytes()) {
            eprintln!(
                "warning: failed to save stage routing to {} -- {e}",
                config_path.display(),
            );
        }
    }

    /// Remove a per-stage routing override from .foundry.json. The stage's
    /// *_provider / *_model fields are left as-is so re-toggling works.
    pub fn clear_stage_routing(project_dir: &Path, stage_id: &str) {
        let config_path = project_dir.join(".foundry.json");
        let content = std::fs::read_to_string(&config_path).unwrap_or_else(|_| "{}".to_string());
        let mut value: serde_json::Value =
            serde_json::from_str(&content).unwrap_or_else(|_| serde_json::json!({}));

        if let Some(arr) = value
            .get_mut("stage_overrides")
            .and_then(|v| v.as_array_mut())
        {
            arr.retain(|value| {
                !value
                    .as_str()
                    .is_some_and(|candidate| Self::stage_ids_match(candidate, stage_id))
            });
        }

        let json = serde_json::to_string_pretty(&value).unwrap_or_default();
        if let Err(e) = crate::utils::atomic_write_file(&config_path, json.as_bytes()) {
            eprintln!(
                "warning: failed to clear stage routing in {} -- {e}",
                config_path.display(),
            );
        }
    }

    /// Read the current value of a config field as a display string.
    pub fn field_value(&self, field_id: &str) -> String {
        match field_id {
            "run_mode" => self.run_mode.clone(),
            "pipeline_mode" => self.pipeline_mode.clone(),
            "plan_review_enabled" => self.plan_review_enabled.to_string(),
            "review_mode" => self.review_mode.clone(),
            "skip_planner_for_simple" => self.skip_planner_for_simple.to_string(),
            "skip_scout_for_simple" => self.skip_scout_for_simple.to_string(),
            "skip_doubt_for_simple" => self.skip_doubt_for_simple.to_string(),
            "batch_doubt" => self.batch_doubt.to_string(),
            "planner_lookahead" => self.planner_lookahead.to_string(),
            "planning_iterations" => self.planning_iterations.to_string(),
            "doubt_engine" => self.doubt_engine.clone(),
            "confidence_threshold" => format!("{:.1}", self.confidence_threshold),
            "parallel_builder" => self.parallel_builder.to_string(),
            "parallel_builder_min_files" => self.parallel_builder_min_files.to_string(),
            "agent_timeout_secs" => self.agent_timeout_secs.to_string(),
            "pause_between_tasks_secs" => self.pause_between_tasks_secs.to_string(),
            "pause_between_agents_secs" => self.pause_between_agents_secs.to_string(),
            "pause_between_cycles_secs" => self.pause_between_cycles_secs.to_string(),
            "adaptive_pauses" => self.adaptive_pauses.to_string(),
            "cost_limit" => format!("{:.2}", self.cost_limit),
            "budget_overrun_threshold" => self.budget_overrun_threshold.to_string(),
            "budget_recovery_enabled" => self.budget_recovery_enabled.to_string(),
            "discovery_cooldown_minutes" => self.discovery_cooldown_minutes.to_string(),
            "local_model" => self.local_model.clone(),
            "ollama_url" => self.ollama_url.clone(),
            "embedding_model" => self.embedding_model.clone(),
            "embedding_timeout_ms" => self.embedding_timeout_ms.to_string(),
            "semantic_match_enabled" => self.semantic_match_enabled.to_string(),
            "sandbox" => self.sandbox.to_string(),
            "sandbox_image" => self.sandbox_image.clone(),
            "phase_isolation" => self.phase_isolation.to_string(),
            "semgrep_enabled" => self.semgrep_enabled.to_string(),
            "require_human_approval" => self.require_human_approval.to_string(),
            "enforce_phase_rbac" => self.enforce_phase_rbac.to_string(),
            "auto_archive_tasks" => self.auto_archive_tasks.to_string(),
            "archive_keep_first" => self.archive_keep_first.to_string(),
            "archive_keep_last" => self.archive_keep_last.to_string(),
            "max_pattern_injection" => self.max_pattern_injection.to_string(),
            "min_pattern_injection" => self.min_pattern_injection.to_string(),
            "history_search_results" => self.history_search_results.to_string(),
            "auto_push_remote" => self.auto_push_remote.clone().unwrap_or_default(),
            "create_issue_on_wip" => self.create_issue_on_wip.to_string(),
            "pr_review_concurrency" => self.pr_review_concurrency.to_string(),
            "pr_poll_interval_secs" => self.pr_poll_interval_secs.to_string(),
            "dashboard_port" => self.dashboard_port.to_string(),
            "theme" => self.theme.clone(),
            "preview_wrap" => self.preview_wrap.to_string(),
            "extensions" => self.extensions.join(", "),
            "on_task_complete" => self.on_task_complete.clone().unwrap_or_default(),
            "build_command" => self.build_command.clone().unwrap_or_default(),
            "patterns_dir" => self.patterns_dir.clone(),
            "history_dir" => self.history_dir.clone(),
            "tmux_session_prefix" => self.tmux_session_prefix.clone(),
            "tmux_keep_sessions" => self.tmux_keep_sessions.to_string(),
            "agent_backend" => self.agent_backend.clone(),
            "backpressure_only" => self.backpressure_only.to_string(),
            "arena_mode" => self.arena_mode.clone(),
            _ => {
                if let Some(stage_id) = Self::stage_id_from_field(field_id) {
                    let (p, m) = if Self::is_pipeline_b_field(field_id) {
                        self.active_routing_for_stage_b(stage_id)
                    } else {
                        self.active_routing_for_stage(stage_id)
                    };
                    if p.is_empty() && m.is_empty() {
                        "(default)".into()
                    } else {
                        Self::display_provider_model(&p, &m)
                    }
                } else {
                    String::new()
                }
            }
        }
    }

    /// Write a single config field to .foundry.json. Returns Err on parse failure.
    pub fn save_field(project_dir: &Path, field_id: &str, new_value: &str) -> Result<(), String> {
        let config_path = project_dir.join(".foundry.json");
        let content = std::fs::read_to_string(&config_path).unwrap_or_else(|_| "{}".to_string());
        let mut value: serde_json::Value =
            serde_json::from_str(&content).unwrap_or_else(|_| serde_json::json!({}));

        match field_id {
            // Bools
            "plan_review_enabled"
            | "skip_planner_for_simple"
            | "skip_scout_for_simple"
            | "skip_doubt_for_simple"
            | "batch_doubt"
            | "planner_lookahead"
            | "parallel_builder"
            | "adaptive_pauses"
            | "budget_recovery_enabled"
            | "semantic_match_enabled"
            | "sandbox"
            | "phase_isolation"
            | "semgrep_enabled"
            | "require_human_approval"
            | "enforce_phase_rbac"
            | "auto_archive_tasks"
            | "create_issue_on_wip"
            | "preview_wrap"
            | "tmux_keep_sessions"
            | "backpressure_only" => {
                let b = new_value
                    .parse::<bool>()
                    .map_err(|_| format!("not a bool: {}", new_value))?;
                value[field_id] = serde_json::json!(b);
            }
            // u64 numbers
            "agent_timeout_secs"
            | "pause_between_tasks_secs"
            | "pause_between_agents_secs"
            | "pause_between_cycles_secs"
            | "discovery_cooldown_minutes" => {
                let n = new_value
                    .parse::<u64>()
                    .map_err(|_| format!("not a number: {}", new_value))?;
                value[field_id] = serde_json::json!(n);
            }
            // usize numbers
            "planning_iterations"
            | "parallel_builder_min_files"
            | "archive_keep_first"
            | "archive_keep_last"
            | "max_pattern_injection"
            | "min_pattern_injection"
            | "history_search_results"
            | "pr_review_concurrency"
            | "embedding_timeout_ms"
            | "budget_overrun_threshold"
            | "pr_poll_interval_secs" => {
                let n = new_value
                    .parse::<usize>()
                    .map_err(|_| format!("not a number: {}", new_value))?;
                value[field_id] = serde_json::json!(n);
            }
            // u16 numbers
            "dashboard_port" => {
                let n = new_value
                    .parse::<u16>()
                    .map_err(|_| format!("not a port: {}", new_value))?;
                value[field_id] = serde_json::json!(n);
            }
            // f64 numbers
            "cost_limit" | "confidence_threshold" => {
                let n = new_value
                    .parse::<f64>()
                    .map_err(|_| format!("not a number: {}", new_value))?;
                value[field_id] = serde_json::json!(n);
            }
            // Strings
            "run_mode"
            | "pipeline_mode"
            | "review_mode"
            | "doubt_engine"
            | "theme"
            | "agent_backend"
            | "ollama_url"
            | "embedding_model"
            | "sandbox_image"
            | "patterns_dir"
            | "history_dir"
            | "tmux_session_prefix" => {
                value[field_id] = serde_json::json!(new_value);
            }
            // Optional strings
            "auto_push_remote" | "on_task_complete" | "build_command" => {
                if new_value.is_empty() {
                    value[field_id] = serde_json::Value::Null;
                } else {
                    value[field_id] = serde_json::json!(new_value);
                }
            }
            _ => return Err(format!("unknown field: {}", field_id)),
        }

        let json = serde_json::to_string_pretty(&value).unwrap_or_default();
        crate::utils::atomic_write_file(&config_path, json.as_bytes())
            .map_err(|e| format!("write error: {}", e))
    }

    /// Get the list of valid enum values for cycling.
    pub fn enum_values(field_id: &str) -> &'static [&'static str] {
        match field_id {
            "run_mode" => &["auto", "sprint", "review", "coach"],
            "pipeline_mode" => &["full", "fast", "backpressure"],
            "review_mode" => &["diff-only", "full-file"],
            "doubt_engine" => &["claude", "codex"],
            "agent_backend" => &["pty", "tmux"],
            _ => &[],
        }
    }

    fn stage_field_keys(stage_id: &str) -> (&'static str, &'static str) {
        match stage_id {
            "scout" => ("scout_provider", "scout_model"),
            "query" => ("query_provider", "query_model"),
            "research" => ("research_provider", "research_model"),
            "plan" => ("planner_provider", "planner_model"),
            "build" | "implement" => ("builder_provider", "builder_model"),
            "audit" | "doubt" => ("reviewer_provider", "reviewer_model"),
            "discovery" | "discover" => ("discovery_provider", "discovery_model"),
            "pr_review" => ("pr_review_provider", "pr_review_model"),
            "pattern_extraction" | "patterns" => {
                ("pattern_extraction_provider", "pattern_extraction_model")
            }
            "fixer" => ("fixer_provider", "fixer_model"),
            _ => ("builder_provider", "builder_model"),
        }
    }

    pub fn stage_id_from_field(field_id: &str) -> Option<&str> {
        match field_id {
            "stage_query" | "stage_query_b" => Some("query"),
            "stage_research" | "stage_research_b" => Some("research"),
            "stage_plan" | "stage_plan_b" => Some("plan"),
            "stage_build" | "stage_build_b" => Some("build"),
            "stage_audit" | "stage_audit_b" => Some("audit"),
            "stage_discovery" | "stage_discovery_b" => Some("discovery"),
            "stage_pr_review" | "stage_pr_review_b" => Some("pr_review"),
            "stage_patterns" | "stage_patterns_b" => Some("pattern_extraction"),
            "stage_fixer" | "stage_fixer_b" => Some("fixer"),
            _ => None,
        }
    }

    pub fn is_pipeline_b_field(field_id: &str) -> bool {
        field_id.ends_with("_b")
            && matches!(
                field_id,
                "stage_query_b"
                    | "stage_research_b"
                    | "stage_plan_b"
                    | "stage_build_b"
                    | "stage_audit_b"
                    | "stage_discovery_b"
                    | "stage_pr_review_b"
                    | "stage_patterns_b"
                    | "stage_fixer_b"
            )
    }

    fn stage_field_keys_b(stage_id: &str) -> (&'static str, &'static str) {
        match stage_id {
            "scout" => ("b_scout_provider", "b_scout_model"),
            "query" => ("b_query_provider", "b_query_model"),
            "research" => ("b_research_provider", "b_research_model"),
            "plan" => ("b_planner_provider", "b_planner_model"),
            "build" | "implement" => ("b_builder_provider", "b_builder_model"),
            "audit" | "doubt" => ("b_reviewer_provider", "b_reviewer_model"),
            "discovery" | "discover" => ("b_discovery_provider", "b_discovery_model"),
            "pr_review" => ("b_pr_review_provider", "b_pr_review_model"),
            "pattern_extraction" | "patterns" => {
                ("b_pattern_extraction_provider", "b_pattern_extraction_model")
            }
            "fixer" => ("b_fixer_provider", "b_fixer_model"),
            _ => ("b_builder_provider", "b_builder_model"),
        }
    }

    pub fn active_routing_for_stage_b(&self, stage_id: &str) -> (String, String) {
        let (prov, model) = match stage_id {
            "scout" => (&self.b_scout_provider, &self.b_scout_model),
            "query" => (&self.b_query_provider, &self.b_query_model),
            "research" => (&self.b_research_provider, &self.b_research_model),
            "plan" => (&self.b_planner_provider, &self.b_planner_model),
            "build" | "implement" => (&self.b_builder_provider, &self.b_builder_model),
            "audit" | "doubt" => (&self.b_reviewer_provider, &self.b_reviewer_model),
            "discovery" | "discover" => (&self.b_discovery_provider, &self.b_discovery_model),
            "pr_review" => (&self.b_pr_review_provider, &self.b_pr_review_model),
            "pattern_extraction" | "patterns" => (
                &self.b_pattern_extraction_provider,
                &self.b_pattern_extraction_model,
            ),
            "fixer" => (&self.b_fixer_provider, &self.b_fixer_model),
            _ => (&self.b_builder_provider, &self.b_builder_model),
        };
        // Provider-gated: model-only without provider is not a valid B override
        // (runtime ignores it). Return empty so UI shows "(default)" / inherits A.
        if prov.is_empty() {
            (String::new(), String::new())
        } else {
            (prov.clone(), model.clone())
        }
    }

    pub fn set_stage_routing_b(project_dir: &Path, stage_id: &str, provider: &str, model: &str) {
        let config_path = project_dir.join(".foundry.json");
        let content = std::fs::read_to_string(&config_path).unwrap_or_else(|_| "{}".to_string());
        let mut value: serde_json::Value =
            serde_json::from_str(&content).unwrap_or_else(|_| serde_json::json!({}));

        let (prov_key, model_key) = Self::stage_field_keys_b(stage_id);
        value[prov_key] = serde_json::json!(provider);
        value[model_key] = serde_json::json!(model);

        let json = serde_json::to_string_pretty(&value).unwrap_or_default();
        if let Err(e) = crate::utils::atomic_write_file(&config_path, json.as_bytes()) {
            eprintln!(
                "warning: failed to save pipeline B routing to {} -- {e}",
                config_path.display(),
            );
        }
    }

    pub fn clear_stage_routing_b(project_dir: &Path, stage_id: &str) {
        let config_path = project_dir.join(".foundry.json");
        let content = std::fs::read_to_string(&config_path).unwrap_or_else(|_| "{}".to_string());
        let mut value: serde_json::Value =
            serde_json::from_str(&content).unwrap_or_else(|_| serde_json::json!({}));

        let (prov_key, model_key) = Self::stage_field_keys_b(stage_id);
        if let Some(obj) = value.as_object_mut() {
            obj.remove(prov_key);
            obj.remove(model_key);
        }

        let json = serde_json::to_string_pretty(&value).unwrap_or_default();
        if let Err(e) = crate::utils::atomic_write_file(&config_path, json.as_bytes()) {
            eprintln!(
                "warning: failed to clear pipeline B routing in {} -- {e}",
                config_path.display(),
            );
        }
    }

    pub fn save_arena_mode(project_dir: &Path, mode: &str) {
        let config_path = project_dir.join(".foundry.json");
        let content = std::fs::read_to_string(&config_path).unwrap_or_else(|_| "{}".to_string());
        let mut value: serde_json::Value =
            serde_json::from_str(&content).unwrap_or_else(|_| serde_json::json!({}));
        value["arena_mode"] = serde_json::json!(mode);
        let json = serde_json::to_string_pretty(&value).unwrap_or_default();
        if let Err(e) = crate::utils::atomic_write_file(&config_path, json.as_bytes()) {
            eprintln!(
                "warning: failed to save arena_mode to {} -- {e}",
                config_path.display(),
            );
        }
    }

    /// Persist the agent/task-queue pane split percentage to the global
    /// `~/.foundry/config.json`. Pane split is a per-user preference, not a
    /// per-project one, so saves go to the global file by default. Best-effort:
    /// on missing HOME or write error, the in-memory value is kept and a warning
    /// is logged.
    pub fn save_agent_pane_split_global(pct: u16) {
        let Some(config_path) = Self::global_config_path() else {
            eprintln!(
                "warning: cannot save agent_pane_split -- HOME or USERPROFILE not set"
            );
            return;
        };
        if let Some(parent) = config_path.parent() {
            if let Err(e) = std::fs::create_dir_all(parent) {
                eprintln!(
                    "warning: failed to create {} -- agent_pane_split will not persist: {e}",
                    parent.display(),
                );
                return;
            }
        }
        let content = std::fs::read_to_string(&config_path).unwrap_or_else(|_| "{}".to_string());
        let mut value: serde_json::Value = serde_json::from_str(&content).unwrap_or_else(|e| {
            eprintln!(
                "warning: {} contains invalid JSON ({e}) -- existing settings will be lost",
                config_path.display(),
            );
            serde_json::json!({})
        });
        value["agent_pane_split"] = serde_json::json!(pct);
        let json = serde_json::to_string_pretty(&value).unwrap_or_default();
        if let Err(e) = crate::utils::atomic_write_file(&config_path, json.as_bytes()) {
            eprintln!(
                "warning: failed to save agent_pane_split to {} -- change will not persist across restarts: {e}",
                config_path.display(),
            );
        }
    }

    pub fn pipeline_b_config(&self) -> Config {
        let mut config = self.clone();
        // Only override stages that actually run per-pipeline in dual mode.
        // Excluded: scout (outer loop bootstrap), discovery (outer loop),
        // fixer (no runtime invocations), pr_review, pattern_extraction.
        if !self.b_query_provider.is_empty() {
            config.query_provider = self.b_query_provider.clone();
            config.query_model = self.b_query_model.clone();
        }
        if !self.b_research_provider.is_empty() {
            config.research_provider = self.b_research_provider.clone();
            config.research_model = self.b_research_model.clone();
        }
        if !self.b_planner_provider.is_empty() {
            config.planner_provider = self.b_planner_provider.clone();
            config.planner_model = self.b_planner_model.clone();
        }
        if !self.b_builder_provider.is_empty() {
            config.builder_provider = self.b_builder_provider.clone();
            config.builder_model = self.b_builder_model.clone();
        }
        if !self.b_reviewer_provider.is_empty() {
            config.reviewer_provider = self.b_reviewer_provider.clone();
            config.reviewer_model = self.b_reviewer_model.clone();
        }
        config.builder_models.clear();
        config.dual_selection.clear();
        config.arena_mode = "solo".into();
        config
    }

    pub fn list_available_models(
        claude_available: bool,
        codex_available: bool,
        copilot_available: bool,
        lmstudio: &[String],
        ollama: &[String],
    ) -> Vec<crate::app::ModelEntry> {
        use crate::app::ModelEntry;

        let catalog = crate::model_catalog::load_catalog();
        let mut entries: Vec<ModelEntry> = Vec::new();

        for e in &catalog.entries {
            let visible = match e.provider.as_str() {
                "claude" => claude_available,
                "codex" => codex_available,
                "ghcopilot" => copilot_available,
                "opencode" => false,
                _ => false,
            };
            if !visible {
                continue;
            }
            let label = if e.deprecated_at.is_some() {
                format!(
                    "{} (deprecated, sunset {})",
                    e.display_name,
                    e.deprecated_at
                        .map(|d| d.format("%Y-%m-%d").to_string())
                        .unwrap_or_else(|| "unknown".into())
                )
            } else {
                e.display_name.clone()
            };
            entries.push(ModelEntry {
                provider: e.provider.clone(),
                model: e.model_id.clone(),
                label,
                recommended: e.recommended,
                group: if e.group.is_empty() {
                    default_group_for_provider(&e.provider).to_string()
                } else {
                    e.group.clone()
                },
            });
        }

        for m in lmstudio {
            entries.push(ModelEntry {
                provider: "opencode".into(),
                model: format!("lmstudio/{}", m),
                label: m.clone(),
                recommended: false,
                group: "OpenCode -- LM Studio".into(),
            });
        }

        for m in ollama {
            entries.push(ModelEntry {
                provider: "opencode".into(),
                model: format!("ollama/{}", m),
                label: m.clone(),
                recommended: false,
                group: "OpenCode -- Ollama".into(),
            });
        }

        entries.push(ModelEntry {
            provider: String::new(),
            model: String::new(),
            label: "Use stage default".into(),
            recommended: false,
            group: "Reset".into(),
        });

        entries
    }
}

fn default_group_for_provider(provider: &str) -> &'static str {
    match provider {
        "claude" => "Claude",
        "codex" => "Codex",
        "ghcopilot" => "GitHub Copilot",
        "opencode" => "OpenCode",
        _ => "Other",
    }
}

#[cfg(test)]
#[allow(clippy::field_reassign_with_default)]
mod tests {
    use super::Config;
    use crate::agent::ModelProvider;
    use serial_test::serial;
    use std::fs;

    #[test]
    fn default_config_disables_auto_push() {
        assert_eq!(Config::default().auto_push_remote, None);
    }

    #[test]
    fn run_mode_enum_values_include_coach() {
        let values = Config::enum_values("run_mode");
        assert!(values.contains(&"auto"));
        assert!(values.contains(&"sprint"));
        assert!(values.contains(&"review"));
        assert!(values.contains(&"coach"));
    }

    #[test]
    fn save_builder_routing_writes_provider_and_model_keys() {
        let dir = tempfile::tempdir().unwrap();
        Config::save_builder_routing(dir.path(), "opencode", "lmstudio/qwen3.6-35b-a3b");
        let content = fs::read_to_string(dir.path().join(".foundry.json")).unwrap();
        let value: serde_json::Value = serde_json::from_str(&content).unwrap();
        assert_eq!(value["builder_provider"], "opencode");
        assert_eq!(value["builder_model"], "lmstudio/qwen3.6-35b-a3b");
    }

    #[test]
    fn save_builder_routing_preserves_existing_fields() {
        let dir = tempfile::tempdir().unwrap();
        fs::write(
            dir.path().join(".foundry.json"),
            r#"{"theme":"light","run_mode":"sprint"}"#,
        )
        .unwrap();
        Config::save_builder_routing(dir.path(), "opencode", "ollama/llama3.2");
        let content = fs::read_to_string(dir.path().join(".foundry.json")).unwrap();
        let value: serde_json::Value = serde_json::from_str(&content).unwrap();
        assert_eq!(value["theme"], "light");
        assert_eq!(value["run_mode"], "sprint");
        assert_eq!(value["builder_provider"], "opencode");
        assert_eq!(value["builder_model"], "ollama/llama3.2");
    }

    #[test]
    fn save_builder_routing_sets_builder_models_and_dual_selection_to_first() {
        let dir = tempfile::tempdir().unwrap();
        Config::save_builder_routing(dir.path(), "opencode", "lmstudio/qwen3.6-35b-a3b");
        let content = std::fs::read_to_string(dir.path().join(".foundry.json")).unwrap();
        let value: serde_json::Value = serde_json::from_str(&content).unwrap();
        assert_eq!(value["builder_provider"], "opencode");
        assert_eq!(value["builder_model"], "lmstudio/qwen3.6-35b-a3b");
        assert_eq!(value["dual_selection"], "first");
        let arr = value["builder_models"]
            .as_array()
            .expect("builder_models should be an array");
        assert_eq!(arr.len(), 1);
        assert_eq!(arr[0], "opencode:lmstudio/qwen3.6-35b-a3b");
    }

    #[test]
    fn save_builder_routing_snapshots_prev_builder_models_when_switching_to_local() {
        let dir = tempfile::tempdir().unwrap();
        std::fs::write(
            dir.path().join(".foundry.json"),
            r#"{"builder_models":["claude:opus","codex:"],"dual_selection":"both"}"#,
        )
        .unwrap();
        Config::save_builder_routing(dir.path(), "opencode", "lmstudio/qwen3.6-35b-a3b");
        let content = std::fs::read_to_string(dir.path().join(".foundry.json")).unwrap();
        let value: serde_json::Value = serde_json::from_str(&content).unwrap();
        let prev = value["prev_builder_models"]
            .as_array()
            .expect("prev_builder_models should be an array");
        assert_eq!(prev.len(), 2);
        assert_eq!(prev[0], "claude:opus");
        assert_eq!(prev[1], "codex:");
        assert_eq!(value["prev_dual_selection"], "both");
        let new_models = value["builder_models"]
            .as_array()
            .expect("builder_models should be an array");
        assert_eq!(new_models.len(), 1);
        assert_eq!(new_models[0], "opencode:lmstudio/qwen3.6-35b-a3b");
        assert_eq!(value["dual_selection"], "first");
    }

    #[test]
    fn save_builder_routing_does_not_overwrite_existing_snapshot_when_switching_between_local_models(
    ) {
        let dir = tempfile::tempdir().unwrap();
        Config::save_builder_routing(dir.path(), "opencode", "lmstudio/foo");
        // Pre-populate a snapshot as if the user already had specs before going local.
        let content = std::fs::read_to_string(dir.path().join(".foundry.json")).unwrap();
        let mut value: serde_json::Value = serde_json::from_str(&content).unwrap();
        value["prev_builder_models"] = serde_json::json!(["claude:opus", "codex:"]);
        value["prev_dual_selection"] = serde_json::json!("both");
        std::fs::write(
            dir.path().join(".foundry.json"),
            serde_json::to_string_pretty(&value).unwrap(),
        )
        .unwrap();
        Config::save_builder_routing(dir.path(), "opencode", "ollama/llama3.2");
        let content = std::fs::read_to_string(dir.path().join(".foundry.json")).unwrap();
        let value: serde_json::Value = serde_json::from_str(&content).unwrap();
        let prev = value["prev_builder_models"]
            .as_array()
            .expect("prev_builder_models should remain");
        assert_eq!(prev.len(), 2);
        assert_eq!(prev[0], "claude:opus");
        assert_eq!(prev[1], "codex:");
        assert_eq!(value["prev_dual_selection"], "both");
        let new_models = value["builder_models"]
            .as_array()
            .expect("builder_models should be an array");
        assert_eq!(new_models[0], "opencode:ollama/llama3.2");
    }

    #[test]
    fn clear_builder_routing_restores_prev_builder_models_and_dual_selection() {
        let dir = tempfile::tempdir().unwrap();
        std::fs::write(
            dir.path().join(".foundry.json"),
            r#"{
                "builder_models":["opencode:lmstudio/qwen3.6-35b-a3b"],
                "dual_selection":"first",
                "builder_provider":"opencode",
                "builder_model":"lmstudio/qwen3.6-35b-a3b",
                "prev_builder_models":["claude:opus","codex:"],
                "prev_dual_selection":"both"
            }"#,
        )
        .unwrap();
        Config::clear_builder_routing(dir.path());
        let content = std::fs::read_to_string(dir.path().join(".foundry.json")).unwrap();
        let value: serde_json::Value = serde_json::from_str(&content).unwrap();
        let restored = value["builder_models"]
            .as_array()
            .expect("builder_models should be an array");
        assert_eq!(restored.len(), 2);
        assert_eq!(restored[0], "claude:opus");
        assert_eq!(restored[1], "codex:");
        assert_eq!(value["dual_selection"], "both");
        assert_eq!(value["builder_provider"], "claude");
        assert_eq!(value["builder_model"], "opus");
        assert!(value.get("prev_builder_models").is_none());
        assert!(value.get("prev_dual_selection").is_none());
    }

    /// Round-trip: when a user is in dual arena and selects a local model,
    /// arena_mode must be forced to "solo" (so two pipelines don't spawn with
    /// the same local model) and snapshotted into prev_arena_mode. Restoring
    /// must put arena_mode back to "dual".
    #[test]
    fn local_model_routing_snapshots_and_restores_arena_mode() {
        let dir = tempfile::tempdir().unwrap();
        std::fs::write(
            dir.path().join(".foundry.json"),
            r#"{
                "builder_models":["claude:opus","codex:"],
                "dual_selection":"both",
                "arena_mode":"dual"
            }"#,
        )
        .unwrap();
        Config::save_builder_routing(dir.path(), "opencode", "lmstudio/qwen3.6-35b-a3b");

        let content = std::fs::read_to_string(dir.path().join(".foundry.json")).unwrap();
        let value: serde_json::Value = serde_json::from_str(&content).unwrap();
        assert_eq!(value["arena_mode"], "solo", "local-model selection must drop to solo");
        assert_eq!(value["prev_arena_mode"], "dual", "prior arena_mode must be snapshotted");

        Config::clear_builder_routing(dir.path());
        let content = std::fs::read_to_string(dir.path().join(".foundry.json")).unwrap();
        let value: serde_json::Value = serde_json::from_str(&content).unwrap();
        assert_eq!(value["arena_mode"], "dual", "arena_mode must be restored on clear");
        assert!(value.get("prev_arena_mode").is_none(), "snapshot must be removed");
    }

    #[test]
    fn clear_builder_routing_with_no_snapshot_is_a_noop() {
        // D2.9: clear_builder_routing must be a no-op when no
        // prev_builder_models snapshot exists. Previously this path nuked
        // builder_models to [] which stranded users in a dual config where
        // every dual-spec selection silently emptied the builder list and
        // left the TUI cycle showing only LM Studio models.
        let dir = tempfile::tempdir().unwrap();
        let initial = r#"{
            "builder_models":["claude:opus","codex:"],
            "dual_selection":"both",
            "builder_provider":"claude",
            "builder_model":"opus"
        }"#;
        std::fs::write(dir.path().join(".foundry.json"), initial).unwrap();
        Config::clear_builder_routing(dir.path());
        let content = std::fs::read_to_string(dir.path().join(".foundry.json")).unwrap();
        let value: serde_json::Value = serde_json::from_str(&content).unwrap();
        let arr = value["builder_models"]
            .as_array()
            .expect("builder_models should be an array");
        assert_eq!(
            arr.len(),
            2,
            "no-snapshot clear_builder_routing must preserve dual builder_models"
        );
        assert_eq!(arr[0], "claude:opus");
        assert_eq!(arr[1], "codex:");
        assert_eq!(value["dual_selection"], "both");
        assert_eq!(value["builder_provider"], "claude");
        assert_eq!(value["builder_model"], "opus");
    }

    #[test]
    fn clear_builder_routing_with_no_snapshot_leaves_local_override_alone() {
        // Defensive: if a caller invokes clear_builder_routing on a tree
        // that is in local-override mode but has no snapshot recorded,
        // we'd rather preserve the user's current state than nuke their
        // builder_models to []. The fix is a no-op rather than a destructive
        // reset.
        let dir = tempfile::tempdir().unwrap();
        let initial = r#"{
            "builder_models":["opencode:lmstudio/qwen3.6-35b-a3b"],
            "dual_selection":"first",
            "builder_provider":"opencode",
            "builder_model":"lmstudio/qwen3.6-35b-a3b"
        }"#;
        std::fs::write(dir.path().join(".foundry.json"), initial).unwrap();
        Config::clear_builder_routing(dir.path());
        let content = std::fs::read_to_string(dir.path().join(".foundry.json")).unwrap();
        let value: serde_json::Value = serde_json::from_str(&content).unwrap();
        let arr = value["builder_models"]
            .as_array()
            .expect("builder_models should be an array");
        assert_eq!(arr.len(), 1);
        assert_eq!(arr[0], "opencode:lmstudio/qwen3.6-35b-a3b");
        assert_eq!(value["builder_provider"], "opencode");
        assert_eq!(value["builder_model"], "lmstudio/qwen3.6-35b-a3b");
    }

    #[test]
    fn for_pipeline_with_opencode_routes_all_eight_stages_to_opencode_and_propagates_model() {
        let mut config = Config::default();
        config.scout_model = "sonnet".into();
        config.query_model = "haiku".into();
        config.research_model = "sonnet".into();
        config.planner_model = "opus".into();
        config.builder_model = "opus".into();
        config.reviewer_model = "sonnet".into();
        config.fixer_model = "sonnet".into();
        config.discovery_model = "opus".into();

        let pipeline = config.for_pipeline("opencode:lmstudio/qwen3.6-35b-a3b");

        assert_eq!(pipeline.scout_provider, "opencode");
        assert_eq!(pipeline.query_provider, "opencode");
        assert_eq!(pipeline.research_provider, "opencode");
        assert_eq!(pipeline.planner_provider, "opencode");
        assert_eq!(pipeline.builder_provider, "opencode");
        assert_eq!(pipeline.reviewer_provider, "opencode");
        assert_eq!(pipeline.fixer_provider, "opencode");
        assert_eq!(pipeline.discovery_provider, "opencode");

        assert_eq!(pipeline.scout_model, "lmstudio/qwen3.6-35b-a3b");
        assert_eq!(pipeline.query_model, "lmstudio/qwen3.6-35b-a3b");
        assert_eq!(pipeline.research_model, "lmstudio/qwen3.6-35b-a3b");
        assert_eq!(pipeline.planner_model, "lmstudio/qwen3.6-35b-a3b");
        assert_eq!(pipeline.builder_model, "lmstudio/qwen3.6-35b-a3b");
        assert_eq!(pipeline.reviewer_model, "lmstudio/qwen3.6-35b-a3b");
        assert_eq!(pipeline.fixer_model, "lmstudio/qwen3.6-35b-a3b");
        assert_eq!(pipeline.discovery_model, "lmstudio/qwen3.6-35b-a3b");

        // Selected_pipeline_configs sanity: when the in-memory config has the
        // saved local-mode builder_models, "first" must produce the OpenCode pipeline.
        let mut local_cfg = Config::default();
        local_cfg.builder_models = vec!["opencode:lmstudio/qwen3.6-35b-a3b".into()];
        local_cfg.dual_selection = "first".into();
        let selected = local_cfg.selected_pipeline_configs(&local_cfg.dual_selection);
        assert_eq!(selected.len(), 1);
        assert_eq!(selected[0].scout_provider, "opencode");
        assert_eq!(selected[0].planner_provider, "opencode");
        assert_eq!(selected[0].discovery_provider, "opencode");
        assert_eq!(selected[0].scout_model, "lmstudio/qwen3.6-35b-a3b");
        assert_eq!(selected[0].discovery_model, "lmstudio/qwen3.6-35b-a3b");
    }

    #[test]
    fn config_deserializes_auto_push_remote() {
        let config: Config = serde_json::from_str(r#"{"auto_push_remote":"snedea"}"#)
            .expect("config should deserialize");
        assert_eq!(config.auto_push_remote.as_deref(), Some("snedea"));
    }

    #[test]
    fn parse_provider_supports_all_providers_and_defaults_to_claude() {
        assert_eq!(Config::parse_provider("codex"), ModelProvider::Codex);
        assert_eq!(Config::parse_provider("CoDeX"), ModelProvider::Codex);
        assert_eq!(Config::parse_provider("claude"), ModelProvider::Claude);
        assert_eq!(Config::parse_provider("unknown"), ModelProvider::Claude);
        assert_eq!(
            Config::parse_provider("ghcopilot"),
            ModelProvider::GhCopilot
        );
        assert_eq!(
            Config::parse_provider("gh-copilot"),
            ModelProvider::GhCopilot
        );
        assert_eq!(Config::parse_provider("copilot"), ModelProvider::GhCopilot);
    }

    #[test]
    fn display_provider_model_formats_empty_and_named_models() {
        assert_eq!(Config::display_provider_model("claude", ""), "Claude");
        assert_eq!(Config::display_provider_model("claude", "opus"), "Claude Opus");
        assert_eq!(Config::display_provider_model("claude", "sonnet"), "Claude Sonnet");
        assert_eq!(Config::display_provider_model("claude", "haiku"), "Claude Haiku");
        assert_eq!(
            Config::display_provider_model("claude", "claude-opus-4-7"),
            "Claude Opus"
        );
        assert_eq!(
            Config::display_provider_model("claude", "claude-sonnet-4-6"),
            "Claude Sonnet"
        );
        assert_eq!(Config::display_provider_model("codex", ""), "Codex");
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
        assert_eq!(pipeline.query_provider, "codex");
        assert_eq!(pipeline.research_provider, "codex");

        assert_eq!(pipeline.scout_model, "");
        assert_eq!(pipeline.planner_model, "");
        assert_eq!(pipeline.builder_model, "");
        assert_eq!(pipeline.reviewer_model, "");
        assert_eq!(pipeline.fixer_model, "");
        assert_eq!(pipeline.discovery_model, "");
        assert_eq!(pipeline.query_model, "");
        assert_eq!(pipeline.research_model, "");
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
        config.query_model = "haiku".into();
        config.research_model = "sonnet".into();

        let pipeline = config.for_pipeline("claude:opus");

        assert_eq!(pipeline.scout_model, "sonnet");
        assert_eq!(pipeline.planner_model, "opus");
        assert_eq!(pipeline.builder_model, "opus");
        assert_eq!(pipeline.reviewer_model, "haiku");
        assert_eq!(pipeline.fixer_model, "sonnet");
        assert_eq!(pipeline.discovery_model, "opus");
        assert_eq!(pipeline.query_model, "haiku");
        assert_eq!(pipeline.research_model, "sonnet");
    }

    #[test]
    fn selected_pipeline_configs_expand_dual_arena() {
        let mut config = Config::default();
        config.arena_mode = "dual".into();
        config.b_builder_provider = "codex".into();
        config.b_builder_model = String::new();

        let selected = config.selected_pipeline_configs("both");

        assert_eq!(selected.len(), 2);
        assert_eq!(selected[0].builder_provider, "claude");
        assert_eq!(selected[0].arena_mode, "solo");
        assert_eq!(selected[1].builder_provider, "codex");
        assert_eq!(selected[1].arena_mode, "solo");
    }

    #[test]
    fn selected_pipeline_configs_solo_ignores_legacy_both() {
        let mut config = Config::default();
        // arena_mode defaults to "" via serde, not "solo" -- but either way, not "dual"
        config.builder_models = vec!["claude:opus".into(), "codex:".into()];

        let selected = config.selected_pipeline_configs("both");

        assert_eq!(selected.len(), 1, "solo mode should not fork into dual pipelines");
    }

    /// Regression: a real on-disk config without `arena_mode` deserializes the
    /// field to "" via #[serde(default)], not "solo". Any guard written as
    /// `arena_mode != "solo"` would incorrectly trigger dual mode here. The
    /// positive `== "dual"` guard at config.rs:1402 is what keeps this safe.
    #[test]
    fn selected_pipeline_configs_solo_when_arena_mode_missing_from_json() {
        let config: Config = serde_json::from_str(
            r#"{"builder_models":["claude:opus","codex:"],"dual_selection":"both"}"#,
        )
        .unwrap();
        assert_eq!(config.arena_mode, "", "serde default for arena_mode is empty string");

        let selected = config.selected_pipeline_configs("both");
        assert_eq!(
            selected.len(),
            1,
            "missing arena_mode must be treated as solo, not dual"
        );
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
    #[serial]
    fn load_warns_on_invalid_json() {
        // Isolate HOME so Config::load() cannot pick up a global config
        // written by another serial test's temp dir
        let dir = tempfile::tempdir().unwrap();
        std::env::set_var("HOME", dir.path());
        // Clear all FOUNDRY_* env overrides
        std::env::remove_var("FOUNDRY_PR_REVIEW_MODEL");
        std::env::remove_var("FOUNDRY_PR_REVIEW_PROVIDER");
        std::env::remove_var("FOUNDRY_AGENT_TIMEOUT_SECS");
        std::env::remove_var("FOUNDRY_PR_REVIEW_MULTIPASS_THRESHOLD");
        std::env::remove_var("FOUNDRY_PR_REVIEW_CONCURRENCY");

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
        let config: Config = serde_json::from_str(r#"{"skip_doubt_for_simple":false}"#)
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
        let config: Config =
            serde_json::from_str(r#"{"builder_model":"opus"}"#).expect("config should deserialize");
        assert!(config.sandbox);
        assert_eq!(config.sandbox_image, "foundry-sandbox:latest");
        assert!(config.sandbox_extra_mounts.is_empty());
    }

    #[test]
    fn model_override_collapses_all_role_models() {
        let dir = tempfile::tempdir().unwrap();
        fs::write(dir.path().join(".foundry.json"), r#"{"model":"opus"}"#).unwrap();
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
        )
        .unwrap();
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
        assert_eq!(
            config.sandbox_env,
            vec!["ANTHROPIC_BASE_URL=http://localhost:8080"]
        );
    }

    #[cfg(unix)]
    #[test]
    #[serial]
    fn load_warns_on_unreadable_file() {
        use std::os::unix::fs::PermissionsExt;
        // Isolate HOME so Config::load() cannot pick up a global config
        // written by another serial test's temp dir
        let dir = tempfile::tempdir().unwrap();
        std::env::set_var("HOME", dir.path());
        // Clear all FOUNDRY_* env overrides
        std::env::remove_var("FOUNDRY_PR_REVIEW_MODEL");
        std::env::remove_var("FOUNDRY_PR_REVIEW_PROVIDER");
        std::env::remove_var("FOUNDRY_AGENT_TIMEOUT_SECS");
        std::env::remove_var("FOUNDRY_PR_REVIEW_MULTIPASS_THRESHOLD");
        std::env::remove_var("FOUNDRY_PR_REVIEW_CONCURRENCY");

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
    fn default_config_enables_enforce_phase_rbac() {
        assert!(Config::default().enforce_phase_rbac);
    }

    #[test]
    fn default_config_enables_phase_isolation() {
        assert!(Config::default().phase_isolation);
    }

    #[test]
    fn config_deserializes_phase_isolation_default_true() {
        let config: Config = serde_json::from_str(r#"{"builder_model":"opus"}"#).unwrap();
        assert!(config.phase_isolation);
    }

    #[test]
    fn config_deserializes_phase_isolation_explicit_false() {
        let config: Config = serde_json::from_str(r#"{"phase_isolation":false}"#).unwrap();
        assert!(!config.phase_isolation);
    }

    #[test]
    fn config_deserializes_enforce_phase_rbac_default_true() {
        let config: Config = serde_json::from_str(r#"{"builder_model":"opus"}"#).unwrap();
        assert!(config.enforce_phase_rbac);
    }

    #[test]
    fn config_deserializes_enforce_phase_rbac_explicit_false() {
        let config: Config = serde_json::from_str(r#"{"enforce_phase_rbac":false}"#).unwrap();
        assert!(!config.enforce_phase_rbac);
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
        let config: Config =
            serde_json::from_str(r#"{"pr_review_model":"opus","pr_review_provider":"claude"}"#)
                .expect("config should deserialize");
        assert_eq!(config.pr_review_model, "opus");
        assert_eq!(config.pr_review_provider, "claude");
    }

    #[test]
    #[serial]
    fn load_global_only_returns_defaults_when_no_global_config() {
        // Point HOME to a temp dir with no .foundry/config.json
        let dir = tempfile::tempdir().unwrap();
        std::env::set_var("HOME", dir.path());
        // Clear any env overrides that might interfere
        std::env::remove_var("FOUNDRY_PR_REVIEW_MODEL");
        std::env::remove_var("FOUNDRY_PR_REVIEW_PROVIDER");
        std::env::remove_var("FOUNDRY_AGENT_TIMEOUT_SECS");
        std::env::remove_var("FOUNDRY_PR_REVIEW_MULTIPASS_THRESHOLD");
        std::env::remove_var("FOUNDRY_PR_REVIEW_CONCURRENCY");

        let config = Config::load_global_only();
        let defaults = Config::default();
        assert_eq!(config.agent_timeout_secs, defaults.agent_timeout_secs);
        assert_eq!(config.pr_review_model, defaults.pr_review_model);
        assert_eq!(config.pr_review_provider, defaults.pr_review_provider);
        assert_eq!(config.reviewer_model, defaults.reviewer_model);
        assert_eq!(config.run_mode, defaults.run_mode);
    }

    #[test]
    #[serial]
    fn load_global_only_deserializes_global_config() {
        let dir = tempfile::tempdir().unwrap();
        let foundry_dir = dir.path().join(".foundry");
        fs::create_dir_all(&foundry_dir).unwrap();
        fs::write(
            foundry_dir.join("config.json"),
            r#"{"agent_timeout_secs":120,"pr_review_model":"opus","reviewer_model":"haiku"}"#,
        )
        .unwrap();
        std::env::set_var("HOME", dir.path());
        // Clear env overrides
        std::env::remove_var("FOUNDRY_PR_REVIEW_MODEL");
        std::env::remove_var("FOUNDRY_AGENT_TIMEOUT_SECS");
        std::env::remove_var("FOUNDRY_PR_REVIEW_CONCURRENCY");

        let config = Config::load_global_only();
        assert_eq!(config.agent_timeout_secs, 120);
        assert_eq!(config.pr_review_model, "opus");
        assert_eq!(config.reviewer_model, "haiku");
    }

    #[test]
    #[serial]
    fn load_global_only_applies_normalize() {
        let dir = tempfile::tempdir().unwrap();
        let foundry_dir = dir.path().join(".foundry");
        fs::create_dir_all(&foundry_dir).unwrap();
        // Legacy "mode":"loop" should be normalized to "auto"
        // "model" override should collapse all role models
        fs::write(
            foundry_dir.join("config.json"),
            r#"{"mode":"loop","model":"haiku"}"#,
        )
        .unwrap();
        std::env::set_var("HOME", dir.path());
        // Clear env overrides
        std::env::remove_var("FOUNDRY_PR_REVIEW_MODEL");
        std::env::remove_var("FOUNDRY_AGENT_TIMEOUT_SECS");
        std::env::remove_var("FOUNDRY_PR_REVIEW_CONCURRENCY");

        let config = Config::load_global_only();
        assert_eq!(config.run_mode, "auto");
        assert_eq!(config.scout_model, "haiku");
        assert_eq!(config.planner_model, "haiku");
        assert_eq!(config.builder_model, "haiku");
        assert_eq!(config.reviewer_model, "haiku");
    }

    #[test]
    #[serial]
    fn load_global_only_applies_env_overrides() {
        let dir = tempfile::tempdir().unwrap();
        std::env::set_var("HOME", dir.path());
        // No global config file -- starts from defaults
        std::env::set_var("FOUNDRY_PR_REVIEW_MODEL", "opus");
        std::env::set_var("FOUNDRY_PR_REVIEW_PROVIDER", "claude");
        std::env::set_var("FOUNDRY_AGENT_TIMEOUT_SECS", "300");
        std::env::set_var("FOUNDRY_PR_REVIEW_MULTIPASS_THRESHOLD", "12");

        let config = Config::load_global_only();
        assert_eq!(config.pr_review_model, "opus");
        assert_eq!(config.pr_review_provider, "claude");
        assert_eq!(config.agent_timeout_secs, 300);
        assert_eq!(config.pr_review_multipass_threshold, 12);

        // Clean up
        std::env::remove_var("FOUNDRY_PR_REVIEW_MODEL");
        std::env::remove_var("FOUNDRY_PR_REVIEW_PROVIDER");
        std::env::remove_var("FOUNDRY_AGENT_TIMEOUT_SECS");
        std::env::remove_var("FOUNDRY_PR_REVIEW_MULTIPASS_THRESHOLD");
    }

    #[test]
    #[serial]
    fn agent_pane_split_default_is_50() {
        let config = Config::default();
        assert_eq!(config.agent_pane_split, 50);
    }

    #[test]
    #[serial]
    fn agent_pane_split_deserializes_from_global_config() {
        let dir = tempfile::tempdir().unwrap();
        let foundry_dir = dir.path().join(".foundry");
        fs::create_dir_all(&foundry_dir).unwrap();
        fs::write(
            foundry_dir.join("config.json"),
            r#"{"agent_pane_split":70}"#,
        )
        .unwrap();
        std::env::set_var("HOME", dir.path());
        std::env::remove_var("FOUNDRY_PR_REVIEW_MODEL");
        std::env::remove_var("FOUNDRY_AGENT_TIMEOUT_SECS");
        std::env::remove_var("FOUNDRY_PR_REVIEW_CONCURRENCY");

        let config = Config::load_global_only();
        assert_eq!(config.agent_pane_split, 70);
    }

    #[test]
    #[serial]
    fn agent_pane_split_falls_back_to_default_when_missing() {
        let dir = tempfile::tempdir().unwrap();
        let foundry_dir = dir.path().join(".foundry");
        fs::create_dir_all(&foundry_dir).unwrap();
        // Config file present but without agent_pane_split -- serde default fires.
        fs::write(foundry_dir.join("config.json"), r#"{"theme":"dark"}"#).unwrap();
        std::env::set_var("HOME", dir.path());
        std::env::remove_var("FOUNDRY_PR_REVIEW_MODEL");
        std::env::remove_var("FOUNDRY_AGENT_TIMEOUT_SECS");
        std::env::remove_var("FOUNDRY_PR_REVIEW_CONCURRENCY");

        let config = Config::load_global_only();
        assert_eq!(config.agent_pane_split, 50);
    }

    #[test]
    #[serial]
    fn save_agent_pane_split_round_trips_through_global_config() {
        let dir = tempfile::tempdir().unwrap();
        std::env::set_var("HOME", dir.path());
        std::env::remove_var("FOUNDRY_PR_REVIEW_MODEL");
        std::env::remove_var("FOUNDRY_AGENT_TIMEOUT_SECS");
        std::env::remove_var("FOUNDRY_PR_REVIEW_CONCURRENCY");

        Config::save_agent_pane_split_global(72);
        let config = Config::load_global_only();
        assert_eq!(config.agent_pane_split, 72);

        // A second save replaces only the one field -- preserve other fields.
        let foundry_dir = dir.path().join(".foundry");
        let config_path = foundry_dir.join("config.json");
        let before = std::fs::read_to_string(&config_path).unwrap();
        let mut value: serde_json::Value = serde_json::from_str(&before).unwrap();
        value["theme"] = serde_json::json!("solarized");
        std::fs::write(&config_path, serde_json::to_string_pretty(&value).unwrap()).unwrap();

        Config::save_agent_pane_split_global(33);
        let config2 = Config::load_global_only();
        assert_eq!(config2.agent_pane_split, 33);
        assert_eq!(config2.theme, "solarized");
    }

    #[test]
    #[serial]
    fn env_overrides_take_precedence_over_config_file() {
        let dir = tempfile::tempdir().unwrap();
        let foundry_dir = dir.path().join(".foundry");
        fs::create_dir_all(&foundry_dir).unwrap();
        fs::write(
            foundry_dir.join("config.json"),
            r#"{"pr_review_model":"sonnet","agent_timeout_secs":600}"#,
        )
        .unwrap();
        std::env::set_var("HOME", dir.path());
        std::env::set_var("FOUNDRY_PR_REVIEW_MODEL", "opus");
        std::env::set_var("FOUNDRY_AGENT_TIMEOUT_SECS", "120");

        let config = Config::load_global_only();
        // Env vars win over config file
        assert_eq!(config.pr_review_model, "opus");
        assert_eq!(config.agent_timeout_secs, 120);

        // Clean up
        std::env::remove_var("FOUNDRY_PR_REVIEW_MODEL");
        std::env::remove_var("FOUNDRY_AGENT_TIMEOUT_SECS");
    }

    #[test]
    #[serial]
    fn env_overrides_apply_to_load() {
        let dir = tempfile::tempdir().unwrap();
        fs::write(
            dir.path().join(".foundry.json"),
            r#"{"pr_review_model":"sonnet"}"#,
        )
        .unwrap();
        std::env::set_var("FOUNDRY_PR_REVIEW_MODEL", "opus");
        std::env::set_var("FOUNDRY_AGENT_TIMEOUT_SECS", "180");

        let config = Config::load(dir.path());
        assert_eq!(config.pr_review_model, "opus");
        assert_eq!(config.agent_timeout_secs, 180);

        // Clean up
        std::env::remove_var("FOUNDRY_PR_REVIEW_MODEL");
        std::env::remove_var("FOUNDRY_AGENT_TIMEOUT_SECS");
    }

    #[test]
    #[serial]
    fn env_override_invalid_timeout_is_ignored() {
        let dir = tempfile::tempdir().unwrap();
        std::env::set_var("HOME", dir.path());
        std::env::set_var("FOUNDRY_AGENT_TIMEOUT_SECS", "not_a_number");
        std::env::remove_var("FOUNDRY_PR_REVIEW_MODEL");
        std::env::remove_var("FOUNDRY_PR_REVIEW_PROVIDER");
        std::env::remove_var("FOUNDRY_PR_REVIEW_MULTIPASS_THRESHOLD");
        std::env::remove_var("FOUNDRY_PR_REVIEW_CONCURRENCY");

        let config = Config::load_global_only();
        // Should keep the default value
        assert_eq!(
            config.agent_timeout_secs,
            Config::default().agent_timeout_secs
        );

        std::env::remove_var("FOUNDRY_AGENT_TIMEOUT_SECS");
    }

    #[test]
    #[serial]
    fn env_override_empty_string_is_ignored() {
        let dir = tempfile::tempdir().unwrap();
        std::env::set_var("HOME", dir.path());
        std::env::set_var("FOUNDRY_PR_REVIEW_MODEL", "");
        std::env::remove_var("FOUNDRY_PR_REVIEW_PROVIDER");
        std::env::remove_var("FOUNDRY_AGENT_TIMEOUT_SECS");
        std::env::remove_var("FOUNDRY_PR_REVIEW_MULTIPASS_THRESHOLD");
        std::env::remove_var("FOUNDRY_PR_REVIEW_CONCURRENCY");

        let config = Config::load_global_only();
        // Empty env var should NOT override the default (empty string is treated as unset)
        assert_eq!(config.pr_review_model, Config::default().pr_review_model);

        std::env::remove_var("FOUNDRY_PR_REVIEW_MODEL");
    }

    #[test]
    #[serial]
    fn doubt_engine_env_override_accepts_both_vars_with_priority() {
        let dir = tempfile::tempdir().unwrap();
        std::env::set_var("HOME", dir.path());
        std::env::set_var("FOUNDRY_DOUBT_ENGINE", "codex");
        std::env::set_var("DOUBT_ENGINE", "claude");

        let config = Config::load_global_only();
        assert_eq!(config.doubt_engine, "codex");

        std::env::remove_var("FOUNDRY_DOUBT_ENGINE");
        std::env::remove_var("DOUBT_ENGINE");
    }

    #[test]
    #[serial]
    fn doubt_engine_env_override_falls_back_to_second_var_when_first_is_invalid() {
        let dir = tempfile::tempdir().unwrap();
        std::env::set_var("HOME", dir.path());
        std::env::set_var("FOUNDRY_DOUBT_ENGINE", "invalid");
        std::env::set_var("DOUBT_ENGINE", "codex");

        let config = Config::load_global_only();
        assert_eq!(config.doubt_engine, "codex");

        std::env::remove_var("FOUNDRY_DOUBT_ENGINE");
        std::env::remove_var("DOUBT_ENGINE");
    }

    #[test]
    fn doubt_engine_json_value_is_normalized_and_validated() {
        let mut config: Config = serde_json::from_str(r#"{"doubt_engine":" CODEX "}"#).unwrap();
        config.normalize();
        assert_eq!(config.doubt_engine, "codex");

        let mut invalid: Config = serde_json::from_str(r#"{"doubt_engine":"wat"}"#).unwrap();
        invalid.normalize();
        assert_eq!(invalid.doubt_engine, "claude");
    }

    #[test]
    fn test_pr_review_concurrency_default() {
        let config = Config::default();
        assert_eq!(config.pr_review_concurrency, 4);
    }

    #[test]
    fn test_pr_review_concurrency_from_json() {
        let json = r#"{"pr_review_concurrency": 8}"#;
        let config: Config = serde_json::from_str(json).unwrap();
        assert_eq!(config.pr_review_concurrency, 8);
    }

    #[test]
    fn test_pr_review_concurrency_sequential() {
        let json = r#"{"pr_review_concurrency": 1}"#;
        let config: Config = serde_json::from_str(json).unwrap();
        assert_eq!(config.pr_review_concurrency, 1);
    }

    #[test]
    fn test_pr_review_concurrency_zero_normalized_to_one() {
        let json = r#"{"pr_review_concurrency": 0}"#;
        let mut config: Config = serde_json::from_str(json).unwrap();
        config.normalize();
        assert_eq!(config.pr_review_concurrency, 1);
    }

    #[test]
    fn test_fallback_path_normalize_then_env_overrides() {
        // Simulate what load() and load_global_only() fallback paths do:
        // Self::default() -> normalize() -> apply_env_overrides()
        // This verifies that normalize() runs correctly on default configs
        // and catches regressions if normalize() is accidentally removed from a path.
        let mut config: Config =
            serde_json::from_str(r#"{"pr_review_concurrency": 0, "run_mode": "loop"}"#).unwrap();
        config.normalize();
        config.apply_env_overrides();
        assert_eq!(
            config.pr_review_concurrency, 1,
            "normalize must clamp pr_review_concurrency to >= 1"
        );
        assert_eq!(
            config.run_mode, "auto",
            "normalize must convert legacy 'loop' mode to 'auto'"
        );
    }

    #[test]
    #[serial]
    fn load_invalid_json_warns_and_normalizes() {
        // Config::load() with invalid JSON should:
        // 1. Log a warning to stderr (not easily captured, verified by code inspection)
        // 2. Return defaults
        // 3. Run normalize() on the defaults (single exit path guarantee)
        let dir = tempfile::tempdir().unwrap();
        std::env::set_var("HOME", dir.path());
        std::env::remove_var("FOUNDRY_PR_REVIEW_MODEL");
        std::env::remove_var("FOUNDRY_PR_REVIEW_PROVIDER");
        std::env::remove_var("FOUNDRY_AGENT_TIMEOUT_SECS");
        std::env::remove_var("FOUNDRY_PR_REVIEW_MULTIPASS_THRESHOLD");
        std::env::remove_var("FOUNDRY_PR_REVIEW_CONCURRENCY");

        fs::write(
            dir.path().join(".foundry.json"),
            "this is not json at all {{{",
        )
        .unwrap();
        let config = Config::load(dir.path());

        // Verify defaults are used (invalid JSON was not silently applied)
        assert_eq!(
            config.agent_timeout_secs,
            Config::default().agent_timeout_secs
        );
        assert_eq!(config.planner_model, Config::default().planner_model);

        // Verify normalize() invariants hold on the returned config
        assert!(
            config.pr_review_concurrency >= 1,
            "normalize must clamp pr_review_concurrency to >= 1"
        );
        assert_ne!(
            config.run_mode, "loop",
            "normalize must convert legacy 'loop' mode"
        );
        assert_ne!(
            config.run_mode, "hil",
            "normalize must convert legacy 'hil' mode"
        );
    }

    #[test]
    fn default_config_has_five_rpid_pipeline_stages() {
        let stages = Config::default().pipeline_stages;
        assert_eq!(stages.len(), 5);
        assert_eq!(stages[0].id, "query");
        assert_eq!(stages[0].label, "QUERY");
        assert!(stages[0].enabled);
        assert_eq!(stages[1].id, "research");
        assert_eq!(stages[1].label, "RESEARCH");
        assert_eq!(stages[2].id, "plan");
        assert_eq!(stages[2].label, "PLAN");
        assert_eq!(stages[3].id, "implement");
        assert_eq!(stages[3].label, "BUILD");
        assert_eq!(stages[4].id, "doubt");
        assert_eq!(stages[4].label, "AUDIT");
    }

    #[test]
    fn config_deserializes_missing_pipeline_stages_uses_rpid_defaults() {
        let config: Config = serde_json::from_str(r#"{"builder_model":"opus"}"#).unwrap();
        assert_eq!(config.pipeline_stages.len(), 5);
        assert_eq!(config.pipeline_stages[0].id, "query");
        assert_eq!(config.pipeline_stages[4].id, "doubt");
    }

    #[test]
    fn config_deserializes_explicit_pipeline_stages_overrides_default() {
        let json = r#"{
            "pipeline_stages": [
                {"id":"plan","label":"PLAN","enabled":true},
                {"id":"implement","label":"BUILD","enabled":false}
            ]
        }"#;
        let config: Config = serde_json::from_str(json).unwrap();
        assert_eq!(config.pipeline_stages.len(), 2);
        assert_eq!(config.pipeline_stages[0].id, "plan");
        assert_eq!(config.pipeline_stages[1].label, "BUILD");
        assert!(!config.pipeline_stages[1].enabled);
    }

    #[test]
    fn config_deserializes_stages_alias() {
        let json = r#"{"stages":[{"id":"doubt","label":"AUDIT"}]}"#;
        let config: Config = serde_json::from_str(json).unwrap();
        assert_eq!(config.pipeline_stages.len(), 1);
        assert_eq!(config.pipeline_stages[0].id, "doubt");
        assert_eq!(config.pipeline_stages[0].label, "AUDIT");
        assert!(config.pipeline_stages[0].enabled);
    }

    #[test]
    fn pipeline_stage_config_enabled_defaults_to_true() {
        let stage: crate::config::PipelineStageConfig =
            serde_json::from_str(r#"{"id":"plan","label":"PLAN"}"#).unwrap();
        assert!(stage.enabled);
    }

    #[test]
    fn pipeline_stage_config_explicit_enabled_false() {
        let stage: crate::config::PipelineStageConfig =
            serde_json::from_str(r#"{"id":"plan","label":"PLAN","enabled":false}"#).unwrap();
        assert!(!stage.enabled);
    }

    #[test]
    fn pipeline_stage_label_returns_configured_label() {
        let config: Config =
            serde_json::from_str(r#"{"pipeline_stages":[{"id":"implement","label":"BUILD"}]}"#)
                .unwrap();
        assert_eq!(config.pipeline_stage_label("implement"), "BUILD");
    }

    #[test]
    fn pipeline_stage_label_falls_back_to_uppercase_id() {
        let config: Config =
            serde_json::from_str(r#"{"pipeline_stages":[{"id":"plan","label":"PLAN"}]}"#).unwrap();
        assert_eq!(config.pipeline_stage_label("doubt"), "DOUBT");
    }

    #[test]
    fn pipeline_stage_enabled_returns_configured_value() {
        let config: Config = serde_json::from_str(
            r#"{"pipeline_stages":[{"id":"query","label":"QUERY","enabled":false},{"id":"plan","label":"PLAN","enabled":true}]}"#,
        )
        .unwrap();
        assert!(!config.pipeline_stage_enabled("query"));
        assert!(config.pipeline_stage_enabled("plan"));
    }

    #[test]
    fn pipeline_stage_enabled_missing_stage_is_disabled() {
        let config: Config =
            serde_json::from_str(r#"{"pipeline_stages":[{"id":"plan","label":"PLAN"}]}"#).unwrap();
        assert!(!config.pipeline_stage_enabled("doubt"));
    }

    #[test]
    fn default_config_all_stages_enabled() {
        let c = Config::default();
        assert!(c.pipeline_stage_enabled("query"));
        assert!(c.pipeline_stage_enabled("research"));
        assert!(c.pipeline_stage_enabled("plan"));
        assert!(c.pipeline_stage_enabled("implement"));
        assert!(c.pipeline_stage_enabled("doubt"));
    }

    #[test]
    fn pipeline_stage_config_prompt_override_defaults_to_none() {
        let stage: crate::config::PipelineStageConfig =
            serde_json::from_str(r#"{"id":"plan","label":"PLAN"}"#).unwrap();
        assert_eq!(stage.prompt_override, None);
    }

    #[test]
    fn pipeline_stage_config_explicit_prompt_override() {
        let stage: crate::config::PipelineStageConfig = serde_json::from_str(
            r#"{"id":"security","label":"SECURITY","prompt_override":"Audit for OWASP Top 10."}"#,
        )
        .unwrap();
        assert_eq!(
            stage.prompt_override.as_deref(),
            Some("Audit for OWASP Top 10.")
        );
    }

    #[test]
    fn pipeline_stage_config_empty_prompt_override_preserved() {
        let stage: crate::config::PipelineStageConfig =
            serde_json::from_str(r#"{"id":"plan","label":"PLAN","prompt_override":""}"#).unwrap();
        assert_eq!(stage.prompt_override.as_deref(), Some(""));
    }

    #[test]
    fn default_config_pipeline_stages_have_no_prompt_override() {
        let stages = Config::default().pipeline_stages;
        for stage in &stages {
            assert!(
                stage.prompt_override.is_none(),
                "stage {} should have no prompt_override by default",
                stage.id
            );
        }
    }

    #[test]
    fn config_deserializes_pipeline_stages_with_custom_card_and_override() {
        let json = r#"{
            "pipeline_stages": [
                {"id":"query","label":"QUERY"},
                {"id":"research","label":"RESEARCH"},
                {"id":"plan","label":"PLAN"},
                {"id":"implement","label":"IMPLEMENT"},
                {"id":"security","label":"SECURITY","prompt_override":"Audit for OWASP Top 10."},
                {"id":"doubt","label":"DOUBT"}
            ]
        }"#;
        let config: Config = serde_json::from_str(json).unwrap();
        assert_eq!(config.pipeline_stages.len(), 6);
        assert_eq!(config.pipeline_stages[4].id, "security");
        assert_eq!(
            config.pipeline_stages[4].prompt_override.as_deref(),
            Some("Audit for OWASP Top 10.")
        );
    }

    #[test]
    fn config_deserializes_reordered_pipeline_stages_preserves_order() {
        let json = r#"{
            "pipeline_stages": [
                {"id":"implement","label":"IMPLEMENT"},
                {"id":"doubt","label":"DOUBT"},
                {"id":"plan","label":"PLAN"}
            ]
        }"#;
        let config: Config = serde_json::from_str(json).unwrap();
        assert_eq!(config.pipeline_stages.len(), 3);
        assert_eq!(config.pipeline_stages[0].id, "implement");
        assert_eq!(config.pipeline_stages[1].id, "doubt");
        assert_eq!(config.pipeline_stages[2].id, "plan");
    }

    #[test]
    fn default_config_has_no_task_completion_hook() {
        assert_eq!(Config::default().on_task_complete, None);
    }

    #[test]
    fn config_deserializes_missing_on_task_complete_as_none() {
        let config: Config = serde_json::from_str("{}").expect("config should deserialize");
        assert_eq!(config.on_task_complete, None);
    }

    #[test]
    fn config_deserializes_explicit_on_task_complete_string() {
        let config: Config = serde_json::from_str(
            r#"{"on_task_complete":"afplay /System/Library/Sounds/Glass.aiff"}"#,
        )
        .expect("config should deserialize");
        assert_eq!(
            config.on_task_complete.as_deref(),
            Some("afplay /System/Library/Sounds/Glass.aiff"),
        );
    }

    #[test]
    fn active_routing_for_stage_returns_field_values() {
        let config: Config =
            serde_json::from_str(r#"{"planner_provider":"claude","planner_model":"opus-4-7"}"#)
                .unwrap();
        let (p, m) = config.active_routing_for_stage("plan");
        assert_eq!(p, "claude");
        assert_eq!(m, "opus-4-7");
    }

    #[test]
    fn active_routing_for_stage_all_stages_default() {
        let config = Config::default();
        let (p, _) = config.active_routing_for_stage("scout");
        assert_eq!(p, "claude");
        let (p, _) = config.active_routing_for_stage("build");
        assert_eq!(p, "claude");
        let (p, _) = config.active_routing_for_stage("audit");
        assert_eq!(p, "claude");
        let (p, _) = config.active_routing_for_stage("discover");
        assert_eq!(p, "claude");
        let (p, m) = config.active_routing_for_stage("pattern_extraction");
        assert_eq!(p, "claude");
        assert_eq!(m, "sonnet");
    }

    #[test]
    fn for_pipeline_respects_stage_overrides() {
        let mut config = Config::default();
        config.planner_provider = "claude".into();
        config.planner_model = "opus-4-7".into();
        config.stage_overrides = vec!["plan".into()];
        let pipelined = config.for_pipeline("codex:");
        assert_eq!(pipelined.planner_provider, "claude", "plan is pinned");
        assert_eq!(pipelined.planner_model, "opus-4-7", "plan model preserved");
        assert_eq!(pipelined.builder_provider, "codex", "build follows global");
        assert_eq!(pipelined.reviewer_provider, "codex", "audit follows global");
        assert_eq!(pipelined.scout_provider, "codex", "scout follows global");
    }

    #[test]
    fn for_pipeline_with_no_overrides_overrides_all_stages() {
        let config = Config::default();
        let pipelined = config.for_pipeline("codex:");
        assert_eq!(pipelined.planner_provider, "codex");
        assert_eq!(pipelined.builder_provider, "codex");
        assert_eq!(pipelined.reviewer_provider, "codex");
        assert_eq!(pipelined.scout_provider, "codex");
        assert_eq!(pipelined.discovery_provider, "codex");
    }

    #[test]
    fn for_pipeline_multiple_overrides() {
        let mut config = Config::default();
        config.planner_provider = "claude".into();
        config.planner_model = "opus-4-7".into();
        config.reviewer_provider = "claude".into();
        config.reviewer_model = "opus-4-7".into();
        config.builder_provider = "codex".into();
        config.builder_model = "gpt-5.4".into();
        config.stage_overrides = vec!["plan".into(), "build".into(), "audit".into()];
        let pipelined = config.for_pipeline("opencode:lmstudio/qwen");
        assert_eq!(pipelined.planner_provider, "claude", "plan pinned");
        assert_eq!(pipelined.planner_model, "opus-4-7", "plan model pinned");
        assert_eq!(pipelined.builder_provider, "codex", "build pinned");
        assert_eq!(pipelined.builder_model, "gpt-5.4", "build model pinned");
        assert_eq!(pipelined.reviewer_provider, "claude", "audit pinned");
        assert_eq!(pipelined.reviewer_model, "opus-4-7", "audit model pinned");
        assert_eq!(pipelined.scout_provider, "opencode", "scout follows global");
        assert_eq!(pipelined.query_provider, "opencode", "query follows global");
    }

    #[test]
    #[serial]
    fn set_stage_routing_writes_and_clears_round_trip() {
        let dir = tempfile::tempdir().unwrap();
        std::fs::write(dir.path().join(".foundry.json"), "{}").unwrap();

        Config::set_stage_routing(dir.path(), "plan", "claude", "opus-4-7");
        let content = std::fs::read_to_string(dir.path().join(".foundry.json")).unwrap();
        let value: serde_json::Value = serde_json::from_str(&content).unwrap();
        assert_eq!(value["planner_provider"], "claude");
        assert_eq!(value["planner_model"], "opus-4-7");
        let overrides = value["stage_overrides"].as_array().unwrap();
        assert!(overrides.contains(&serde_json::json!("plan")));

        Config::clear_stage_routing(dir.path(), "plan");
        let content = std::fs::read_to_string(dir.path().join(".foundry.json")).unwrap();
        let value: serde_json::Value = serde_json::from_str(&content).unwrap();
        let overrides = value["stage_overrides"].as_array().unwrap();
        assert!(!overrides.contains(&serde_json::json!("plan")));
        assert_eq!(
            value["planner_provider"], "claude",
            "field preserved after clear"
        );
    }

    #[test]
    fn stage_overrides_deserialization_defaults_to_empty() {
        let config: Config = serde_json::from_str("{}").unwrap();
        assert!(config.stage_overrides.is_empty());
    }

    #[test]
    fn stage_overrides_deserialization_with_values() {
        let config: Config =
            serde_json::from_str(r#"{"stage_overrides":["plan","build","audit"]}"#).unwrap();
        assert_eq!(config.stage_overrides, vec!["plan", "build", "audit"]);
    }

    #[test]
    fn list_available_models_includes_detected_providers() {
        let entries = Config::list_available_models(true, true, true, &[], &[]);
        let providers: Vec<&str> = entries.iter().map(|e| e.provider.as_str()).collect();
        assert!(providers.contains(&"claude"), "missing claude");
        assert!(providers.contains(&"codex"), "missing codex");
        assert!(providers.contains(&"ghcopilot"), "missing ghcopilot");
        assert!(providers.contains(&""), "missing reset sentinel");
    }

    #[test]
    fn list_available_models_excludes_unavailable_providers() {
        let entries = Config::list_available_models(false, false, false, &[], &[]);
        let providers: Vec<&str> = entries.iter().map(|e| e.provider.as_str()).collect();
        assert!(!providers.contains(&"claude"), "claude should be absent");
        assert!(!providers.contains(&"codex"), "codex should be absent");
        assert!(!providers.contains(&"ghcopilot"), "copilot should be absent");
        assert!(providers.contains(&""), "reset sentinel always present");
    }

    #[test]
    fn list_available_models_includes_lmstudio() {
        let entries =
            Config::list_available_models(false, false, false, &["qwen3-coder-30b".into()], &[]);
        let lm = entries.iter().find(|e| e.label == "qwen3-coder-30b");
        assert!(lm.is_some(), "LM Studio model not in entries");
        assert_eq!(lm.unwrap().model, "lmstudio/qwen3-coder-30b");
    }

    #[test]
    fn list_available_models_includes_ollama() {
        let entries =
            Config::list_available_models(false, false, false, &[], &["llama3.2".into()]);
        let ol = entries.iter().find(|e| e.label == "llama3.2");
        assert!(ol.is_some(), "Ollama model not in entries");
        assert_eq!(ol.unwrap().model, "ollama/llama3.2");
    }

    #[test]
    fn stage_id_from_field_maps_correctly() {
        assert_eq!(Config::stage_id_from_field("stage_plan"), Some("plan"));
        assert_eq!(Config::stage_id_from_field("stage_build"), Some("build"));
        assert_eq!(Config::stage_id_from_field("stage_audit"), Some("audit"));
        assert_eq!(
            Config::stage_id_from_field("stage_patterns"),
            Some("pattern_extraction")
        );
        assert_eq!(Config::stage_id_from_field("run_mode"), None);
    }

    #[test]
    fn field_value_for_stage_returns_display() {
        let config: Config =
            serde_json::from_str(r#"{"planner_provider":"claude","planner_model":"opus-4-7"}"#)
                .unwrap();
        let val = config.field_value("stage_plan");
        assert!(
            val.contains("Claude") || val.contains("claude") || val.contains("opus"),
            "stage_plan field_value should contain provider/model info, got: {val}"
        );
    }

    #[test]
    fn pipeline_b_config_inherits_a_when_b_empty() {
        let mut config = Config::default();
        config.scout_provider = "claude".into();
        config.scout_model = "opus-4-7".into();
        config.builder_provider = "codex".into();
        config.builder_model = "gpt-5.4".into();
        // B fields left empty -- should inherit from A
        let b = config.pipeline_b_config();
        assert_eq!(b.scout_provider, "claude", "B should inherit scout from A");
        assert_eq!(b.scout_model, "opus-4-7");
        assert_eq!(b.builder_provider, "codex", "B should inherit builder from A");
        assert_eq!(b.builder_model, "gpt-5.4");
    }

    #[test]
    fn pipeline_b_config_overrides_when_b_set() {
        let mut config = Config::default();
        config.query_provider = "claude".into();
        config.query_model = "opus".into();
        config.b_query_provider = "codex".into();
        config.b_query_model = "gpt-5.4".into();
        let b = config.pipeline_b_config();
        assert_eq!(b.query_provider, "codex", "B should use its own provider");
        assert_eq!(b.query_model, "gpt-5.4", "B should use its own model");
    }

    #[test]
    fn pipeline_b_config_clears_arena_mode() {
        let mut config = Config::default();
        config.arena_mode = "dual".into();
        let b = config.pipeline_b_config();
        assert_eq!(b.arena_mode, "solo", "B config should not re-trigger dual");
    }

    #[test]
    fn selected_pipeline_configs_dual_returns_two() {
        let mut config = Config::default();
        config.arena_mode = "dual".into();
        config.query_provider = "claude".into();
        config.b_query_provider = "codex".into();
        let configs = config.selected_pipeline_configs("");
        assert_eq!(configs.len(), 2);
        assert_eq!(configs[0].query_provider, "claude");
        assert_eq!(configs[1].query_provider, "codex");
    }

    #[test]
    fn selected_pipeline_configs_dual_both_are_solo() {
        let mut config = Config::default();
        config.arena_mode = "dual".into();
        config.builder_models = vec!["claude:opus".into(), "codex:".into()];
        config.dual_selection = "both".into();
        let configs = config.selected_pipeline_configs("both");
        assert_eq!(configs.len(), 2);
        assert_eq!(configs[0].arena_mode, "solo", "Pipeline A must be solo to prevent recursion");
        assert_eq!(configs[1].arena_mode, "solo", "Pipeline B must be solo to prevent recursion");
        assert!(configs[0].builder_models.is_empty(), "Pipeline A must clear legacy dual fields");
        assert!(configs[1].builder_models.is_empty(), "Pipeline B must clear legacy dual fields");
        assert!(configs[0].dual_selection.is_empty(), "Pipeline A must clear dual_selection");
        assert!(configs[1].dual_selection.is_empty(), "Pipeline B must clear dual_selection");
    }

    #[test]
    fn selected_pipeline_configs_dual_no_infinite_recursion() {
        let mut config = Config::default();
        config.arena_mode = "dual".into();
        config.query_provider = "claude".into();
        config.b_query_provider = "codex".into();
        let configs = config.selected_pipeline_configs("");
        // Both A and B configs should themselves return 1 config (not trigger another dual split)
        let a_sub = configs[0].selected_pipeline_configs("");
        let b_sub = configs[1].selected_pipeline_configs("");
        assert_eq!(a_sub.len(), 1, "Pipeline A config must not trigger dual again");
        assert_eq!(b_sub.len(), 1, "Pipeline B config must not trigger dual again");
    }

    #[test]
    fn selected_pipeline_configs_solo_returns_one() {
        let config = Config::default();
        let configs = config.selected_pipeline_configs("");
        assert_eq!(configs.len(), 1);
    }

    #[test]
    fn pipeline_b_partial_config_ignored_without_provider() {
        let mut config = Config::default();
        config.query_provider = "claude".into();
        config.query_model = "opus".into();
        // Only model set, no provider -- should be ignored
        config.b_query_model = "gpt-5.4".into();
        let b = config.pipeline_b_config();
        assert_eq!(b.query_provider, "claude", "should inherit A provider");
        assert_eq!(b.query_model, "opus", "should inherit A model");
    }

    #[test]
    fn pipeline_b_provider_only_clears_model() {
        let mut config = Config::default();
        config.query_provider = "claude".into();
        config.query_model = "opus".into();
        // Provider set, model empty -- valid: use provider default model
        config.b_query_provider = "codex".into();
        let b = config.pipeline_b_config();
        assert_eq!(b.query_provider, "codex");
        assert!(b.query_model.is_empty(), "empty B model means use provider default");
    }

    #[test]
    fn arena_mode_round_trip() {
        let dir = tempfile::tempdir().unwrap();
        Config::save_arena_mode(dir.path(), "dual");
        let config = Config::load(dir.path());
        assert_eq!(config.arena_mode, "dual");
        Config::save_arena_mode(dir.path(), "solo");
        let config = Config::load(dir.path());
        assert_eq!(config.arena_mode, "solo");
    }

    #[test]
    fn active_routing_for_stage_b_provider_gated() {
        let mut config = Config::default();
        // Model-only without provider: should return empty (UI shows "(default)")
        config.b_scout_model = "opus-4-7".into();
        let (p, m) = config.active_routing_for_stage_b("scout");
        assert!(p.is_empty(), "model-only B should return empty provider");
        assert!(m.is_empty(), "model-only B should return empty model");

        // Provider set: should return both
        config.b_scout_provider = "codex".into();
        let (p, m) = config.active_routing_for_stage_b("scout");
        assert_eq!(p, "codex");
        assert_eq!(m, "opus-4-7");
    }

    #[test]
    fn pipeline_b_config_skips_pr_review_and_patterns() {
        let mut config = Config::default();
        config.b_pr_review_provider = "codex".into();
        config.b_pr_review_model = "gpt-5.4".into();
        config.b_pattern_extraction_provider = "codex".into();
        config.b_pattern_extraction_model = "gpt-5.4".into();
        config.pr_review_provider = "claude".into();
        config.pattern_extraction_provider = "claude".into();
        let b = config.pipeline_b_config();
        assert_eq!(
            b.pr_review_provider, "claude",
            "PR review should inherit A (not used per-pipeline)"
        );
        assert_eq!(
            b.pattern_extraction_provider, "claude",
            "patterns should inherit A (hardcoded Claude)"
        );
    }

    #[test]
    fn selected_pipeline_configs_dual_skips_legacy_builder_models() {
        let mut config = Config::default();
        config.arena_mode = "dual".into();
        config.builder_models = vec!["claude:opus".into(), "codex:".into()];
        config.dual_selection = "both".into();
        let configs = config.selected_pipeline_configs("both");
        // Should still return exactly 2 (arena mode path, not legacy)
        assert_eq!(configs.len(), 2);
        // Both should have empty builder_models
        assert!(configs[0].builder_models.is_empty());
        assert!(configs[1].builder_models.is_empty());
    }
}
