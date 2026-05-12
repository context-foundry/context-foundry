use crate::sync_flag::SyncFlag;
use std::collections::{HashMap, VecDeque};
use std::sync::{Arc, Mutex};
use std::time::SystemTime;

use chrono::{DateTime, Utc};
use crossterm::event::{self, MouseEvent};
use std::path::PathBuf;

use crate::agent::{AgentErrorKind, AgentOutputEvent, AgentRole};
use crate::complexity::{TaskComplexity, TaskOverride};
use crate::eval::report::EvalReportSnapshot;
use crate::git;
use crate::orchestrator::OrchestratorOutcome;
use crate::patterns::Pattern;
use crate::stats::StatsReport;
use crate::task::{self, Task};
use crate::tui::theme::TuiTheme;

const LOG_MESSAGES_CAP: usize = 500;
const TASK_HISTORY_CAP: usize = 200;

/// 100ms tick * 20 = 2000ms cadence for the TASKS.md live-reload poll.
pub(super) const TASKS_RELOAD_TICK_STRIDE: usize = 20;

// ─── App State ───────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AppPhase {
    Startup,
    Planning,
    Running,
}

/// Coarse-grained classification of the current agent's activity for the
/// spinner label. Updated by handle_agent_output as ToolUse / TextDelta /
/// Text events flow in. Reset to Idle on AgentDone and on set_agent.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum StreamState {
    #[default]
    Idle,
    Reading,
    WritingText,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TuiPane {
    Explorer,
    Preview,
    AgentOutput,
    TaskQueue,
    PatternsLearned,
    Plugins,
    Narrative,
    Stats,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum ClickableSurface {
    PipelineStage(String),
    TaskQueue,
    Narrative,
    SkillCitations,
    Stats,
    AgentOutput,
    ExplorerFile(std::path::PathBuf),
}

impl ClickableSurface {
    pub fn tag(&self) -> &'static str {
        match self {
            ClickableSurface::PipelineStage(_) => "pipeline_stage",
            ClickableSurface::TaskQueue => "task_queue",
            ClickableSurface::Narrative => "narrative",
            ClickableSurface::SkillCitations => "skill_citations",
            ClickableSurface::Stats => "stats",
            ClickableSurface::AgentOutput => "agent_output",
            ClickableSurface::ExplorerFile(_) => "explorer_file",
        }
    }
    pub fn label(&self) -> String {
        match self {
            ClickableSurface::PipelineStage(s) => s.clone(),
            ClickableSurface::TaskQueue => "Task Queue".to_string(),
            ClickableSurface::Narrative => "Narrative".to_string(),
            ClickableSurface::SkillCitations => "Skill Citations".to_string(),
            ClickableSurface::Stats => "Stats".to_string(),
            ClickableSurface::AgentOutput => "Agent Output".to_string(),
            ClickableSurface::ExplorerFile(p) => p
                .file_name()
                .and_then(|n| n.to_str())
                .unwrap_or("file")
                .to_string(),
        }
    }
}

#[derive(Debug, Clone)]
pub struct PluginDisplayInfo {
    pub name: String,
    pub selected: bool,
    pub description: String,
    pub pattern_count: usize,
}

/// Display info for an externally-discovered skill surfaced under the
/// "External Skills" section of the startup screen (T1.27). Each entry maps
/// 1:1 to a `crate::skill_discovery::DiscoveredSkill` and tracks the
/// per-project opt-in flag persisted to `.foundry.json`.
#[derive(Debug, Clone)]
pub struct ExternalSkillDisplayInfo {
    pub source: crate::skill_discovery::SkillSource,
    pub path: std::path::PathBuf,
    pub derived_name: String,
    pub selected: bool,
    /// True when another higher-precedence source contributes a skill with
    /// the same `derived_name`; the UI displays this as "shadowed by ..." so
    /// the user can see which file wins.
    pub shadowed_by: Option<String>,
}

#[derive(Debug, Clone)]
pub struct PatternEvent {
    pub title: String,
    pub kind: PatternEventKind,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PatternEventKind {
    Learned,
    Used,
}

#[derive(Debug, Clone, Default)]
pub struct SkillCitationSummary {
    pub session_skills_cited: usize,
    pub session_citations: usize,
    pub top_skills: Vec<crate::skills_telemetry::TelemetryRecord>,
    pub last_cited: Option<(String, String)>,
    pub all_skills: Vec<crate::skills_telemetry::TelemetryRecord>,
    pub db_available: bool,
    pub db_path: std::path::PathBuf,
}

#[derive(Debug, Clone)]
pub struct PluginEvent {
    pub name: String,
    #[allow(dead_code)]
    pub agent_role: String,
    pub task_id: String,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PlanStatus {
    Missing,
    Invalid,
    Empty,
    Pending(usize),
    Complete,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum StartupScenario {
    EmptyProject,
    NeedsQueue,
    QueueReady,
    QueueComplete,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[allow(dead_code)]
pub enum StartupAction {
    Continue,
    EditTasks,
    DescribeWork,
    DesignWithReview,
    ScanProject,
    ViewTasks,
    EditSpec,
}

#[derive(Debug, Clone)]
pub struct FileEntry {
    pub path: PathBuf,
    pub name: String,
    pub depth: usize,
    pub is_dir: bool,
    pub is_cf_highlight: bool,
    pub is_hidden: bool,
    pub expanded: bool,
    pub file_size: u64,
    pub modified: Option<SystemTime>,
}

#[derive(Debug, Clone)]
pub struct StartupState {
    pub scenario: StartupScenario,
    pub plan_status: PlanStatus,
    pub has_spec: bool,
    #[allow(dead_code)]
    pub selected_action: usize,
    #[allow(dead_code)]
    pub actions: Vec<StartupAction>,
    pub entering_intent: bool,
    pub intent_input: String,
    pub status_message: Option<String>,
    pub git_context: Option<git::GitContext>,
    #[allow(dead_code)]
    pub tasks_file_name: String,
    #[allow(dead_code)]
    pub plan_preview_lines: Vec<String>,
    #[allow(dead_code)]
    pub plan_scroll_offset: usize,
    pub next_pending_task: Option<String>,
    #[allow(dead_code)]
    pub spec_file_name: String,
    #[allow(dead_code)]
    pub spec_preview_lines: Vec<String>,
    #[allow(dead_code)]
    pub spec_scroll_offset: usize,
    pub file_tree: Vec<FileEntry>,
    pub explorer_selected: usize,
    pub explorer_scroll: usize,
    pub file_preview_content: Vec<String>,
    pub file_preview_scroll: usize,
    pub placeholder_tick: usize,
    pub preview_wrap: bool,
}

impl StartupState {
    pub fn visible_indices(&self) -> Vec<usize> {
        let mut result = Vec::new();
        let mut skip_below: Option<usize> = None;
        for (idx, entry) in self.file_tree.iter().enumerate() {
            if let Some(d) = skip_below {
                if entry.depth > d {
                    continue;
                }
                skip_below = None;
            }
            result.push(idx);
            if entry.is_dir && !entry.expanded {
                skip_below = Some(entry.depth);
            }
        }
        result
    }
}

#[derive(Debug, Clone)]
pub struct PlanningState {
    pub label: String,
    #[allow(dead_code)]
    pub user_intent: Option<String>,
    pub orchestrator_mode: bool,
    pub orchestrator_iteration: usize,
    pub orchestrator_max_iterations: usize,
    pub orchestrator_finding_count: usize,
    pub orchestrator_role_label: Option<String>,
    pub orchestrator_role_model: Option<String>,
}

#[derive(Debug, Clone)]
pub(super) struct AppendTasksRequest {
    pub(super) description: String,
    pub(super) label: String,
    pub(super) seed_spec_from_description: bool,
}

#[derive(Debug, Clone)]
pub(super) struct PlanningOutcome {
    pub(super) success: bool,
    pub(super) total_tasks: usize,
    pub(super) pending_tasks: usize,
    pub(super) completed_tasks: usize,
    pub(super) new_tasks: usize,
    pub(super) error: Option<String>,
    pub(super) return_to_startup: bool,
}

#[derive(Debug, Clone)]
#[allow(dead_code)]
pub(super) enum PendingTransition {
    StartBuild,
    StartPlanning {
        user_intent: Option<String>,
        label: String,
    },
    StartDesign {
        user_intent: String,
    },
    AppendTasks(AppendTasksRequest),
    OpenExternalEditor {
        file_path: std::path::PathBuf,
    },
    ShowStartup {
        message: Option<String>,
    },
}

// ─── Dual Pipeline State ──────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DualSelection {
    Off,
    First,
    Second,
    Third,
    Both,
}

impl DualSelection {
    pub fn from_str(s: &str) -> Self {
        match s {
            "first" => Self::First,
            "second" => Self::Second,
            "third" => Self::Third,
            "both" => Self::Both,
            _ => Self::Off,
        }
    }

    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Off => "",
            Self::First => "first",
            Self::Second => "second",
            Self::Third => "third",
            Self::Both => "both",
        }
    }

    /// Raw next-state cycle. Callers that know how many builder_models are
    /// configured should prefer `next_for(specs_len)` to skip invalid slots.
    pub fn next(self) -> Self {
        match self {
            Self::Off => Self::First,
            Self::First => Self::Second,
            Self::Second => Self::Third,
            Self::Third => Self::Both,
            Self::Both => Self::First,
        }
    }

    /// Cycle to the next valid selection given how many builder_model specs
    /// are configured. Skips `Third` when len < 3 and `Both` when len < 2.
    ///
    /// Note: once the cycle leaves Off it never returns (same as the underlying
    /// `next()` cycle). With 3 specs the reachable cycle is
    /// `First → Second → Third → Both → First → ...`. `Off` is only ever the
    /// initial state; clearing back to Off requires editing config.
    pub fn next_for(self, specs_len: usize) -> Self {
        let mut candidate = self.next();
        // Bounded loop: at most 5 variants to walk, so cap at 5 iterations.
        for _ in 0..5 {
            let ok = match candidate {
                Self::Off | Self::First => true,
                Self::Second => specs_len >= 2,
                Self::Third => specs_len >= 3,
                Self::Both => specs_len >= 2,
            };
            if ok {
                return candidate;
            }
            candidate = candidate.next();
        }
        Self::Off
    }

    #[cfg(test)]
    pub fn display_label(specs: &[String]) -> String {
        use crate::config::Config;
        match specs.len() {
            0 => "Off".to_string(),
            1 => {
                let (prov, _model) = Config::parse_model_spec(&specs[0]);
                let name = match prov.as_str() {
                    "claude" => "Claude",
                    "codex" => "Codex",
                    "opencode" => "OpenCode",
                    "ghcopilot" | "gh-copilot" | "copilot" => "GhCopilot",
                    other => return format!("{} Solo", other),
                };
                format!("{} Solo", name)
            }
            _ => {
                let names: Vec<&str> = specs
                    .iter()
                    .map(|s| {
                        let (prov, _) = Config::parse_model_spec(s);
                        match prov.as_str() {
                            "claude" => "Claude",
                            "codex" => "Codex",
                            "opencode" => "OpenCode",
                            "ghcopilot" | "gh-copilot" | "copilot" => "GhCopilot",
                            _ => "Other",
                        }
                    })
                    .collect();
                format!("Dual: {}", names.join("+"))
            }
        }
    }
}

// ─── Settings Overlay State ──────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum FieldKind {
    Bool,
    Enum,
    Number,
    Readonly,
    Editor,
    StagePicker,
}

#[derive(Debug, Clone)]
pub struct ModelEntry {
    pub provider: String,
    pub model: String,
    pub label: String,
    pub recommended: bool,
    pub group: String,
}

#[derive(Debug, Clone)]
pub struct ModelPicker {
    pub stage: String,
    pub pipeline_b: bool,
    pub focus: usize,
    pub entries: Vec<ModelEntry>,
    pub groups: Vec<String>,
    pub groups_open: std::collections::BTreeSet<String>,
    pub filter: String,
    pub filtering: bool,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Action {
    RerunEvalOnLastRun,
    ViewInjectedPatterns,
    ViewAllPatterns,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SectionKind {
    Standard,
    PipelineHealth,
    Patterns,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum PatternsFilter {
    InjectedThisSession,
    All,
}

#[derive(Debug, Clone)]
pub struct PatternsSectionSnapshot {
    /// All patterns parsed from `~/.foundry/patterns/`.
    pub all: Vec<Pattern>,
    /// Pattern ids that were injected this session (subset of all by id).
    pub injected_ids: std::collections::BTreeSet<String>,
    /// Currently selected filter: "session" or "all".
    pub filter: PatternsFilter,
}

#[derive(Debug, Clone)]
pub struct FieldDef {
    pub id: &'static str,
    pub label: &'static str,
    pub hint: &'static str,
    pub kind: FieldKind,
}

#[derive(Debug, Clone)]
#[allow(dead_code)]
pub enum OverlayRow {
    Field(FieldDef),
    ReportLine(String),
    ActionButton(Action),
}

#[derive(Debug, Clone)]
pub struct SectionDef {
    pub id: &'static str,
    pub name: &'static str,
    pub default_expanded: bool,
    pub fields: Vec<FieldDef>,
    pub kind: SectionKind,
}

pub fn settings_sections(dual_mode: bool) -> Vec<SectionDef> {
    // (field_id_a, field_id_b, label_solo, label_a_dual, label_b, has_b_row)
    // has_b_row=false for stages where B routing is not meaningful at runtime:
    //   - Discovery: runs in outer loop, not per-pipeline
    //   - PR Review: not part of the build loop
    //   - Patterns: hardcodes Claude provider, B provider ignored
    //   - Fixer: AgentRole::Fixer has no runtime invocations
    let stage_defs: &[(&str, &str, &str, &str, &str, bool)] = &[
        ("stage_query", "stage_query_b", "  Query", "  Query (A)", "  Query (B)", true),
        ("stage_research", "stage_research_b", "  Research", "  Research (A)", "  Research (B)", true),
        ("stage_plan", "stage_plan_b", "  Plan", "  Plan (A)", "  Plan (B)", true),
        ("stage_build", "stage_build_b", "  Build", "  Build (A)", "  Build (B)", true),
        ("stage_audit", "stage_audit_b", "  Audit", "  Audit (A)", "  Audit (B)", true),
        ("stage_discovery", "stage_discovery_b", "  Discovery", "  Discovery (A)", "  Discovery (B)", false),
        ("stage_pr_review", "stage_pr_review_b", "  PR Review", "  PR Review (A)", "  PR Review (B)", false),
        ("stage_patterns", "stage_patterns_b", "  Patterns", "  Patterns (A)", "  Patterns (B)", false),
        ("stage_fixer", "stage_fixer_b", "  Fixer", "  Fixer (A)", "  Fixer (B)", false),
    ];
    let mut routing_fields = vec![FieldDef {
        id: "arena",
        label: "Arena",
        hint: "Enter to toggle: Solo / Dual",
        kind: FieldKind::Enum,
    }];
    for &(id_a, id_b, label_solo, label_a_dual, label_b, has_b) in stage_defs {
        let show_b = dual_mode && has_b;
        let label_a = if show_b { label_a_dual } else { label_solo };
        routing_fields.push(FieldDef {
            id: id_a,
            label: label_a,
            hint: "Enter to pick model",
            kind: FieldKind::StagePicker,
        });
        if show_b {
            routing_fields.push(FieldDef {
                id: id_b,
                label: label_b,
                hint: "Enter to pick model",
                kind: FieldKind::StagePicker,
            });
        }
    }
    vec![
        SectionDef {
            id: "routing",
            name: "Routing",
            default_expanded: true,
            fields: routing_fields,
            kind: SectionKind::Standard,
        },
        SectionDef {
            id: "pipeline_health",
            name: "Pipeline Health",
            default_expanded: false,
            fields: vec![],
            kind: SectionKind::PipelineHealth,
        },
        SectionDef {
            id: "patterns_detail",
            name: "Patterns",
            default_expanded: false,
            fields: vec![],
            kind: SectionKind::Patterns,
        },
        SectionDef {
            id: "pipeline",
            name: "Pipeline behavior",
            default_expanded: true,
            fields: vec![
                FieldDef {
                    id: "run_mode",
                    label: "Run Mode",
                    hint: "auto / sprint / review / coach",
                    kind: FieldKind::Enum,
                },
                FieldDef {
                    id: "pipeline_mode",
                    label: "Pipeline Mode",
                    hint: "full / fast / backpressure",
                    kind: FieldKind::Enum,
                },
                FieldDef {
                    id: "plan_review_enabled",
                    label: "Plan Review",
                    hint: "Review plan before build",
                    kind: FieldKind::Bool,
                },
                FieldDef {
                    id: "review_mode",
                    label: "Review Mode",
                    hint: "diff-only / full-file",
                    kind: FieldKind::Enum,
                },
                FieldDef {
                    id: "skip_planner_for_simple",
                    label: "Skip Planner (simple)",
                    hint: "Simple tasks skip plan stage",
                    kind: FieldKind::Bool,
                },
                FieldDef {
                    id: "skip_scout_for_simple",
                    label: "Skip Scout (simple)",
                    hint: "Simple tasks skip scout stage",
                    kind: FieldKind::Bool,
                },
                FieldDef {
                    id: "skip_doubt_for_simple",
                    label: "Skip Doubt (simple)",
                    hint: "Simple tasks skip audit stage",
                    kind: FieldKind::Bool,
                },
                FieldDef {
                    id: "batch_doubt",
                    label: "Batch Doubt",
                    hint: "Defer audit to end of session",
                    kind: FieldKind::Bool,
                },
                FieldDef {
                    id: "planner_lookahead",
                    label: "Planner Lookahead",
                    hint: "Pre-plan next task while building",
                    kind: FieldKind::Bool,
                },
                FieldDef {
                    id: "planning_iterations",
                    label: "Planning Iterations",
                    hint: "0 = single pass",
                    kind: FieldKind::Number,
                },
                FieldDef {
                    id: "doubt_engine",
                    label: "Doubt Engine",
                    hint: "claude / codex",
                    kind: FieldKind::Enum,
                },
                FieldDef {
                    id: "confidence_threshold",
                    label: "Confidence Threshold",
                    hint: "0.0-1.0, findings below are logged only",
                    kind: FieldKind::Number,
                },
                FieldDef {
                    id: "parallel_builder",
                    label: "Parallel Builder",
                    hint: "Fork builder across files",
                    kind: FieldKind::Bool,
                },
                FieldDef {
                    id: "parallel_builder_min_files",
                    label: "Parallel Min Files",
                    hint: "Min files to trigger parallel build",
                    kind: FieldKind::Number,
                },
                FieldDef {
                    id: "observatory_jsonl_retention_days",
                    label: "Observatory Retention (days)",
                    hint: "0 disables; orphan .db files always archived",
                    kind: FieldKind::Number,
                },
            ],
            kind: SectionKind::Standard,
        },
        SectionDef {
            id: "budgets",
            name: "Budgets & timeouts",
            default_expanded: true,
            fields: vec![
                FieldDef {
                    id: "agent_timeout_secs",
                    label: "Agent Timeout (secs)",
                    hint: "Idle timeout per agent",
                    kind: FieldKind::Number,
                },
                FieldDef {
                    id: "pause_between_tasks_secs",
                    label: "Pause Between Tasks",
                    hint: "Seconds between tasks",
                    kind: FieldKind::Number,
                },
                FieldDef {
                    id: "pause_between_agents_secs",
                    label: "Pause Between Agents",
                    hint: "Seconds between agent spawns",
                    kind: FieldKind::Number,
                },
                FieldDef {
                    id: "pause_between_cycles_secs",
                    label: "Pause Between Cycles",
                    hint: "Seconds between discovery cycles",
                    kind: FieldKind::Number,
                },
                FieldDef {
                    id: "adaptive_pauses",
                    label: "Adaptive Pauses",
                    hint: "Auto-adjust pause timing",
                    kind: FieldKind::Bool,
                },
                FieldDef {
                    id: "cost_limit",
                    label: "Cost Limit (USD)",
                    hint: "0.0 = unlimited",
                    kind: FieldKind::Number,
                },
                FieldDef {
                    id: "budget_overrun_threshold",
                    label: "Overrun Threshold",
                    hint: "% over budget before warning",
                    kind: FieldKind::Number,
                },
                FieldDef {
                    id: "budget_recovery_enabled",
                    label: "Budget Recovery",
                    hint: "Auto-recover from overrun",
                    kind: FieldKind::Bool,
                },
                FieldDef {
                    id: "discovery_cooldown_minutes",
                    label: "Discovery Cooldown",
                    hint: "Minutes between discovery rounds",
                    kind: FieldKind::Number,
                },
            ],
            kind: SectionKind::Standard,
        },
        SectionDef {
            id: "local_models",
            name: "Local models",
            default_expanded: false,
            fields: vec![
                FieldDef {
                    id: "local_model",
                    label: "Local Model",
                    hint: "Active local model selection",
                    kind: FieldKind::Readonly,
                },
                FieldDef {
                    id: "ollama_url",
                    label: "Ollama URL",
                    hint: "Ollama API endpoint",
                    kind: FieldKind::Editor,
                },
                FieldDef {
                    id: "embedding_model",
                    label: "Embedding Model",
                    hint: "Model for semantic matching",
                    kind: FieldKind::Editor,
                },
                FieldDef {
                    id: "embedding_timeout_ms",
                    label: "Embedding Timeout (ms)",
                    hint: "Timeout for embedding calls",
                    kind: FieldKind::Number,
                },
                FieldDef {
                    id: "semantic_match_enabled",
                    label: "Semantic Match",
                    hint: "Use embeddings for pattern matching",
                    kind: FieldKind::Bool,
                },
            ],
            kind: SectionKind::Standard,
        },
        SectionDef {
            id: "sandbox",
            name: "Sandbox & security",
            default_expanded: false,
            fields: vec![
                FieldDef {
                    id: "sandbox",
                    label: "Sandbox",
                    hint: "Docker isolation for agents",
                    kind: FieldKind::Bool,
                },
                FieldDef {
                    id: "sandbox_image",
                    label: "Sandbox Image",
                    hint: "Docker image for sandbox",
                    kind: FieldKind::Editor,
                },
                FieldDef {
                    id: "phase_isolation",
                    label: "Phase Isolation",
                    hint: "Isolate build phases",
                    kind: FieldKind::Bool,
                },
                FieldDef {
                    id: "semgrep_enabled",
                    label: "Semgrep",
                    hint: "Static analysis on agent output",
                    kind: FieldKind::Bool,
                },
                FieldDef {
                    id: "require_human_approval",
                    label: "Human Approval",
                    hint: "Require approval before commit",
                    kind: FieldKind::Bool,
                },
                FieldDef {
                    id: "enforce_phase_rbac",
                    label: "Phase RBAC",
                    hint: "Enforce role-based access per phase",
                    kind: FieldKind::Bool,
                },
            ],
            kind: SectionKind::Standard,
        },
        SectionDef {
            id: "discovery",
            name: "Discovery & patterns",
            default_expanded: false,
            fields: vec![
                FieldDef {
                    id: "auto_archive_tasks",
                    label: "Auto Archive",
                    hint: "Archive completed tasks",
                    kind: FieldKind::Bool,
                },
                FieldDef {
                    id: "archive_keep_first",
                    label: "Archive Keep First",
                    hint: "Keep N first tasks visible",
                    kind: FieldKind::Number,
                },
                FieldDef {
                    id: "archive_keep_last",
                    label: "Archive Keep Last",
                    hint: "Keep N last tasks visible",
                    kind: FieldKind::Number,
                },
                FieldDef {
                    id: "max_pattern_injection",
                    label: "Max Patterns",
                    hint: "Max patterns injected per task",
                    kind: FieldKind::Number,
                },
                FieldDef {
                    id: "min_pattern_injection",
                    label: "Min Patterns",
                    hint: "Min patterns injected per task",
                    kind: FieldKind::Number,
                },
                FieldDef {
                    id: "history_search_results",
                    label: "History Results",
                    hint: "Max history entries in scout prompt",
                    kind: FieldKind::Number,
                },
            ],
            kind: SectionKind::Standard,
        },
        SectionDef {
            id: "git",
            name: "Git & PR",
            default_expanded: false,
            fields: vec![
                FieldDef {
                    id: "auto_push_remote",
                    label: "Auto Push Remote",
                    hint: "Git remote for auto-push (empty=off)",
                    kind: FieldKind::Editor,
                },
                FieldDef {
                    id: "create_issue_on_wip",
                    label: "Issue on WIP",
                    hint: "Create GitHub issue on WIP commits",
                    kind: FieldKind::Bool,
                },
                FieldDef {
                    id: "pr_review_concurrency",
                    label: "PR Review Concurrency",
                    hint: "Parallel file reviews in PR review",
                    kind: FieldKind::Number,
                },
                FieldDef {
                    id: "pr_poll_interval_secs",
                    label: "PR Poll Interval",
                    hint: "Seconds between PR status checks",
                    kind: FieldKind::Number,
                },
                FieldDef {
                    id: "dashboard_port",
                    label: "Dashboard Port",
                    hint: "Port for web dashboard",
                    kind: FieldKind::Number,
                },
            ],
            kind: SectionKind::Standard,
        },
        SectionDef {
            id: "display",
            name: "Display & theme",
            default_expanded: false,
            fields: vec![
                FieldDef {
                    id: "theme",
                    label: "Theme",
                    hint: "TUI color theme",
                    kind: FieldKind::Enum,
                },
                FieldDef {
                    id: "preview_wrap",
                    label: "Preview Wrap",
                    hint: "Wrap long lines in file preview",
                    kind: FieldKind::Bool,
                },
            ],
            kind: SectionKind::Standard,
        },
        SectionDef {
            id: "plugins",
            name: "Plugins & hooks",
            default_expanded: false,
            fields: vec![
                FieldDef {
                    id: "plugins",
                    label: "Plugins",
                    hint: "Active plugin list",
                    kind: FieldKind::Editor,
                },
                FieldDef {
                    id: "on_task_complete",
                    label: "On Task Complete",
                    hint: "Shell hook after each task commit",
                    kind: FieldKind::Editor,
                },
                FieldDef {
                    id: "build_command",
                    label: "Build Command",
                    hint: "Custom build/verify command",
                    kind: FieldKind::Editor,
                },
            ],
            kind: SectionKind::Standard,
        },
        SectionDef {
            id: "advanced",
            name: "Advanced",
            default_expanded: false,
            fields: vec![
                FieldDef {
                    id: "patterns_dir",
                    label: "Patterns Dir",
                    hint: "Pattern storage directory",
                    kind: FieldKind::Editor,
                },
                FieldDef {
                    id: "history_dir",
                    label: "History Dir",
                    hint: "Build history directory",
                    kind: FieldKind::Editor,
                },
                FieldDef {
                    id: "tmux_session_prefix",
                    label: "Tmux Prefix",
                    hint: "Prefix for tmux session names",
                    kind: FieldKind::Editor,
                },
                FieldDef {
                    id: "tmux_keep_sessions",
                    label: "Tmux Keep Sessions",
                    hint: "Keep tmux sessions after task",
                    kind: FieldKind::Bool,
                },
                FieldDef {
                    id: "agent_backend",
                    label: "Agent Backend",
                    hint: "pty / tmux",
                    kind: FieldKind::Enum,
                },
                FieldDef {
                    id: "backpressure_only",
                    label: "Doubt in the Loop?",
                    hint: "ON: runs Doubt (fresh-context audit). OFF: skips Doubt, builder tests only.",
                    kind: FieldKind::Bool,
                },
            ],
            kind: SectionKind::Standard,
        },
    ]
}

#[derive(Debug, Clone)]
#[allow(dead_code)]
pub enum RowId {
    SectionHeader(String),
    Field(String),
    ReportLine(String, usize),
    ActionButton(String, Action),
}

#[derive(Debug, Clone)]
#[allow(dead_code)]
pub struct InlineEdit {
    pub field_id: String,
    pub buffer: String,
    pub error: Option<String>,
}

#[derive(Debug, Clone)]
#[allow(dead_code)]
pub struct SettingsOverlayState {
    pub focus: usize,
    pub expanded_sections: std::collections::BTreeSet<String>,
    pub editing: Option<InlineEdit>,
    pub scroll_offset: usize,
    pub last_render: Vec<(ratatui::layout::Rect, RowId)>,
    pub picker: Option<ModelPicker>,
    pub dirty: bool,
    pub confirm_close: bool,
    pub original_json: Option<String>,
    pub dual_mode: bool,
    pub eval_report_cache: Option<EvalReportSnapshot>,
    pub eval_pipeline_health_first_view: bool,
    pub patterns_section_cache: Option<PatternsSectionSnapshot>,
    pub patterns_section_first_view: bool,
}

impl SettingsOverlayState {
    #[cfg(test)]
    pub fn new() -> Self {
        Self::with_dual_mode(false)
    }

    pub fn with_dual_mode(dual_mode: bool) -> Self {
        let expanded = settings_sections(dual_mode)
            .iter()
            .filter(|s| s.default_expanded)
            .map(|s| s.id.to_string())
            .collect();
        Self {
            focus: 0,
            expanded_sections: expanded,
            editing: None,
            scroll_offset: 0,
            last_render: Vec::new(),
            picker: None,
            dirty: false,
            confirm_close: false,
            original_json: None,
            dual_mode,
            eval_report_cache: None,
            eval_pipeline_health_first_view: true,
            patterns_section_cache: None,
            patterns_section_first_view: true,
        }
    }

    pub fn visible_row_count(&self) -> usize {
        let sections = settings_sections(self.dual_mode);
        let mut count = 0;
        for section in &sections {
            count += 1; // header
            if self.expanded_sections.contains(section.id) {
                match section.kind {
                    SectionKind::PipelineHealth => count += self.pipeline_health_row_count(),
                    SectionKind::Patterns => count += self.patterns_row_count(),
                    SectionKind::Standard => count += section.fields.len(),
                }
            }
        }
        count
    }

    pub fn pipeline_health_rows(&self) -> Vec<OverlayRow> {
        let mut rows: Vec<OverlayRow> = Vec::new();
        if self.eval_report_cache.is_none() {
            rows.push(OverlayRow::ReportLine(
                "No eval report yet -- run a task to generate one.".to_string(),
            ));
            rows.push(OverlayRow::ActionButton(Action::RerunEvalOnLastRun));
            return rows;
        }
        let report = self.eval_report_cache.as_ref().unwrap();
        let aggregate_text = if report.aggregate_badge.is_empty() {
            "EVAL (no data)"
        } else {
            report.aggregate_badge.as_str()
        };
        rows.push(OverlayRow::ReportLine(format!("Aggregate: {}", aggregate_text)));
        if let Some(cp) = report.completion_path.as_deref() {
            rows.push(OverlayRow::ReportLine(format!("Completion: {}", cp)));
        }
        let qrpba_order = ["query", "research", "plan", "implement", "doubt"];
        for slug in qrpba_order.iter() {
            if let Some(stage) = report.stages.get(*slug) {
                let letter = match *slug {
                    "query" => "Q",
                    "research" => "R",
                    "plan" => "P",
                    "implement" => "B",
                    "doubt" => "A",
                    _ => "?",
                };
                rows.push(OverlayRow::ReportLine(format!(
                    "{} {}",
                    letter, stage.badge
                )));
                for inv in &stage.invocations {
                    let status = inv.status.as_deref().unwrap_or("?");
                    let suffix = if let Some(r) = inv.skip_reason.as_deref() {
                        format!(" -- {}", r)
                    } else {
                        String::new()
                    };
                    rows.push(OverlayRow::ReportLine(format!(
                        "    {} [{}]{}",
                        inv.role, status, suffix
                    )));
                    let pass = inv.checks.iter().filter(|c| c.status == "pass").count();
                    let fail = inv.checks.iter().filter(|c| c.status == "fail").count();
                    let skip = inv.checks.iter().filter(|c| c.status == "skip").count();
                    rows.push(OverlayRow::ReportLine(format!(
                        "      {} pass / {} fail / {} skip",
                        pass, fail, skip
                    )));
                    for c in inv.checks.iter().filter(|c| c.status == "fail") {
                        let ev = if c.evidence.chars().count() > 80 {
                            format!(
                                "{}...",
                                c.evidence.chars().take(77).collect::<String>()
                            )
                        } else {
                            c.evidence.clone()
                        };
                        rows.push(OverlayRow::ReportLine(format!(
                            "      FAIL {}: {}",
                            c.name, ev
                        )));
                    }
                }
            }
        }
        for note in &report.notes {
            rows.push(OverlayRow::ReportLine(format!("Note: {}", note)));
        }
        rows.push(OverlayRow::ActionButton(Action::RerunEvalOnLastRun));
        rows
    }

    pub fn pipeline_health_row_count(&self) -> usize {
        self.pipeline_health_rows().len()
    }

    pub fn patterns_rows(&self) -> Vec<OverlayRow> {
        let mut rows: Vec<OverlayRow> = Vec::new();
        let cache = match self.patterns_section_cache.as_ref() {
            Some(c) => c,
            None => {
                rows.push(OverlayRow::ReportLine("No patterns loaded.".to_string()));
                rows.push(OverlayRow::ActionButton(Action::ViewAllPatterns));
                return rows;
            }
        };

        let working: Vec<&Pattern> = match cache.filter {
            PatternsFilter::InjectedThisSession => cache
                .all
                .iter()
                .filter(|p| cache.injected_ids.contains(&p.pattern_id))
                .collect(),
            PatternsFilter::All => cache.all.iter().collect(),
        };

        let filter_label = match cache.filter {
            PatternsFilter::InjectedThisSession => "session",
            PatternsFilter::All => "all",
        };
        rows.push(OverlayRow::ReportLine(format!(
            "Patterns ({}): id | title | sev | freq | used | last | success%",
            filter_label
        )));

        for p in working.iter().take(100) {
            let title_trunc = if p.title.chars().count() > 40 {
                let mut s: String = p.title.chars().take(37).collect();
                s.push_str("...");
                s
            } else {
                p.title.clone()
            };
            let sev = p.severity.as_deref().unwrap_or("-");
            let last = p.last_used_at.as_deref().unwrap_or("-");
            let success_pct = (p.success_rate() * 100.0).round() as i64;
            rows.push(OverlayRow::ReportLine(format!(
                "{} | {} | {} | freq {} | used {} | {} | {}%",
                p.pattern_id, title_trunc, sev, p.frequency, p.used_count, last, success_pct
            )));
        }

        rows.push(OverlayRow::ActionButton(Action::ViewInjectedPatterns));
        rows.push(OverlayRow::ActionButton(Action::ViewAllPatterns));
        rows
    }

    pub fn patterns_row_count(&self) -> usize {
        self.patterns_rows().len()
    }

    pub fn toggle_section(&mut self, section_id: &str) {
        if self.expanded_sections.contains(section_id) {
            self.expanded_sections.remove(section_id);
        } else {
            self.expanded_sections.insert(section_id.to_string());
        }
    }

    pub fn clamp_focus(&mut self) {
        let max = self.visible_row_count().saturating_sub(1);
        self.focus = self.focus.min(max);
    }

    pub fn ensure_focus_visible(&mut self, visible_rows: usize) {
        if visible_rows == 0 {
            self.scroll_offset = 0;
            return;
        }
        self.clamp_focus();
        if self.focus < self.scroll_offset {
            self.scroll_offset = self.focus;
        } else if self.focus >= self.scroll_offset + visible_rows {
            self.scroll_offset = self.focus.saturating_sub(visible_rows - 1);
        }
    }

    pub fn row_at_index(&self, index: usize) -> Option<RowId> {
        let sections = settings_sections(self.dual_mode);
        let mut idx = 0;
        for section in &sections {
            if idx == index {
                return Some(RowId::SectionHeader(section.id.to_string()));
            }
            idx += 1;
            if self.expanded_sections.contains(section.id) {
                match section.kind {
                    SectionKind::PipelineHealth => {
                        let rows = self.pipeline_health_rows();
                        for (j, row) in rows.iter().enumerate() {
                            if idx == index {
                                return match row {
                                    OverlayRow::ReportLine(_) => {
                                        Some(RowId::ReportLine(section.id.to_string(), j))
                                    }
                                    OverlayRow::ActionButton(action) => {
                                        Some(RowId::ActionButton(section.id.to_string(), *action))
                                    }
                                    OverlayRow::Field(_) => None,
                                };
                            }
                            idx += 1;
                        }
                    }
                    SectionKind::Patterns => {
                        let rows = self.patterns_rows();
                        for (j, row) in rows.iter().enumerate() {
                            if idx == index {
                                return match row {
                                    OverlayRow::ReportLine(_) => {
                                        Some(RowId::ReportLine(section.id.to_string(), j))
                                    }
                                    OverlayRow::ActionButton(action) => {
                                        Some(RowId::ActionButton(section.id.to_string(), *action))
                                    }
                                    OverlayRow::Field(_) => None,
                                };
                            }
                            idx += 1;
                        }
                    }
                    SectionKind::Standard => {
                        for field in &section.fields {
                            if idx == index {
                                return Some(RowId::Field(field.id.to_string()));
                            }
                            idx += 1;
                        }
                    }
                }
            }
        }
        None
    }

    pub fn row_at_focus(&self) -> Option<RowId> {
        self.row_at_index(self.focus)
    }
}

impl ModelPicker {
    #[cfg(test)]
    pub fn new(stage: &str, entries: Vec<ModelEntry>) -> Self {
        Self::with_pipeline(stage, false, entries)
    }

    pub fn with_pipeline(stage: &str, pipeline_b: bool, entries: Vec<ModelEntry>) -> Self {
        let mut groups = Vec::new();
        let mut groups_open = std::collections::BTreeSet::new();
        for e in &entries {
            if !groups.contains(&e.group) {
                groups.push(e.group.clone());
                groups_open.insert(e.group.clone());
            }
        }
        Self {
            stage: stage.to_string(),
            pipeline_b,
            focus: 0,
            entries,
            groups,
            groups_open,
            filter: String::new(),
            filtering: false,
        }
    }

    pub fn visible_items(&self) -> Vec<PickerItem> {
        let mut items = Vec::new();
        for group in &self.groups {
            let group_entries: Vec<&ModelEntry> = self
                .entries
                .iter()
                .filter(|e| &e.group == group)
                .filter(|e| {
                    if self.filter.is_empty() {
                        return true;
                    }
                    let needle = self.filter.to_lowercase();
                    e.label.to_lowercase().contains(&needle)
                        || e.provider.to_lowercase().contains(&needle)
                        || e.model.to_lowercase().contains(&needle)
                })
                .collect();
            if group_entries.is_empty() && !self.filter.is_empty() {
                continue;
            }
            let is_open = self.groups_open.contains(group);
            items.push(PickerItem::GroupHeader(group.clone(), is_open));
            if is_open {
                for entry in group_entries {
                    items.push(PickerItem::Entry(entry.clone()));
                }
            }
        }
        items
    }

    pub fn visible_count(&self) -> usize {
        self.visible_items().len()
    }

    pub fn clamp_focus(&mut self) {
        self.focus = self.focus.min(self.visible_count().saturating_sub(1));
    }
}

#[derive(Debug, Clone)]
pub enum PickerItem {
    GroupHeader(String, bool),
    Entry(ModelEntry),
}

#[derive(Debug, Clone, Default)]
pub struct DualBuildState {
    pub active: bool,
    pub streams: [Vec<String>; 2],
    pub event_counts: [usize; 2],
    pub models: [String; 2],
    pub tab: usize,
    pub cost_usd: [f64; 2],
    pub input_tokens: [u64; 2],
    pub output_tokens: [u64; 2],
    pub context_pcts: [[Option<u8>; 5]; 2], // Per-pipeline QRPBA context %: [pipeline][Query, Research, Plan, Build, Audit]
    pub stage_context_pcts: [HashMap<String, u8>; 2], // Per-pipeline custom-card context % keyed by pipeline stage id
    pub finished: [bool; 2],
    pub stages: [Option<AgentRole>; 2], // Current QRPBA stage per pipeline
    pub stage_ids: [Option<String>; 2], // Current configured pipeline stage id per pipeline
    pub stage_models: [String; 2],      // Model label for current stage
    /// Whether the most recent event for this pipeline index was a TextDelta.
    /// Used by the dual-stream handler to decide whether to append to the
    /// last entry in `streams[idx]` or push a new entry.
    pub last_event_was_delta: [bool; 2],
}

#[derive(Debug, Clone)]
pub struct SurfaceSummaryOverlay {
    pub surface: ClickableSurface,
    pub stage: String,
    pub stage_label: String,
    pub state: crate::llm::summary_cache::StageState,
    pub summary: Option<String>,
    pub in_flight: bool,
    pub last_error: Option<String>,
    pub last_cache_hit: bool,
    pub last_model: String,
    pub last_provider: String,
    /// Body scroll offset in display rows. Up/Down/PgUp/PgDn keys and the
    /// mouse wheel mutate this; the renderer applies it via Paragraph::scroll.
    pub scroll_offset: u16,
    /// Wall-clock instant the summarizer was kicked off. Used by the renderer
    /// to drive the spinner frame and the elapsed-seconds counter while
    /// `in_flight && summary.is_none()`.
    pub started_at: std::time::Instant,
}

#[derive(Debug, Clone)]
pub struct ExplorerContextMenu {
    pub anchor_col: u16,
    pub anchor_row: u16,
    pub file_path: std::path::PathBuf,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum RunningModalKind {
    /// Esc tap on running screen -- "Stop this run?" Y/N modal.
    StopRun,
    /// Ctrl+C tap on running screen -- 3-option modal:
    /// [1] stop and exit foundry, [2] stop and return to startup, [3] cancel.
    CtrlC,
}

#[derive(Debug, Clone, Copy)]
pub struct CurrentClassification {
    pub tier: TaskComplexity,
    pub override_flag: TaskOverride,
    pub p_plus_cycles_budget: usize,
}

pub struct AppState {
    pub buildloop_dir: PathBuf,
    pub eval_report_cache: Option<EvalReportSnapshot>,
    /// Mtime of `<buildloop_dir>/eval-report.json` at the moment
    /// `eval_report_cache` was populated. Used by the stats renderer to
    /// distinguish a fresh eval (`mtime >= task_start`) from a stale one
    /// (`mtime < task_start`) without touching disk on every render. `None`
    /// means the report does not exist yet or the mtime probe failed; the
    /// predicate treats that case as stale (conservative).
    pub eval_report_mtime: Option<SystemTime>,
    pub phase: AppPhase,
    pub startup: Option<StartupState>,
    pub planning: Option<PlanningState>,
    pub current_task: Option<Task>,
    pub current_classification: Option<CurrentClassification>,
    pub next_task_hint: Option<String>,
    pub current_agent: Option<(AgentRole, DateTime<Utc>)>,
    pub current_agent_stage_id: Option<String>,
    pub current_agent_model: Option<String>,
    pub agent_output: Vec<String>,
    pub scroll_offset: usize,
    pub log_messages: Vec<(DateTime<Utc>, String)>,
    pub project_name: String,
    pub completed_count: usize,
    pub total_count: usize,
    pub task_queue: Vec<Task>,
    pub task_queue_scroll: usize,
    pub task_history: HashMap<String, TaskPipelineHistory>,
    pub task_history_order: Vec<String>,
    pub discovery_round: usize,
    pub is_discovering: bool,
    pub should_quit: bool,
    pub confirm_quit: bool,
    pub show_no_tasks_warning: bool,
    pub show_welcome: bool,
    pub welcome_message: String,
    pub observatory_session_id: Option<String>,
    pub stop_after_task: bool,
    /// When `Some`, a modal dialog is open over the running screen and consumes all keys.
    /// `None` means no modal is shown. Transient UI state -- not persisted across restarts.
    pub running_screen_modal: Option<RunningModalKind>,
    /// Set when handle_agent_output observes a typed AgentErrorKind. The TUI
    /// renders this as a one-line toast and uses it to gate the R-key retry.
    /// Cleared on dismiss/retry. None == no toast displayed.
    pub typed_error_toast: Option<String>,
    /// True when the last typed error was ContextOverflow -- enables the
    /// "press R to retry" key handler. False for ProviderUnreachable /
    /// ModelNotLoaded (no retry; user must restart foundry).
    pub typed_error_can_retry: bool,
    /// The most recent AgentErrorKind observed in any pipeline. Used by the
    /// retry handler and by the headless command path to populate the
    /// SessionReport.typed_error field. None == no typed error this session.
    pub last_typed_error: Option<AgentErrorKind>,
    pub events_received: usize,
    pub tick_count: usize,
    pub update_available: Option<String>,
    pub inject_input: Option<String>,
    pub show_run_view: bool, // Tab toggle: startup shows run view (pipeline+queue+config)
    pub run_mode: String,    // "auto", "sprint", "review", or "coach"
    pub dual_selection: DualSelection, // Ctrl+D cycle: Off, First, Second, Both
    pub builder_model_specs: Vec<String>, // raw config values (e.g., ["claude:opus", "codex:"])
    pub arena_mode: String,              // "solo" or "dual"
    pub build_stage_label: String,       // formatted label from build stage routing
    pub awaiting_review: bool,
    pub(super) review_gates: HashMap<String, Arc<SyncFlag>>,
    pub(super) review_session_id: Option<String>,
    pub(super) pending_reviews: VecDeque<(String, Option<u64>)>,
    pub awaiting_pr: Option<u64>,
    pub pr_poll_last_check: Option<std::time::Instant>,
    pub show_patterns: bool,
    pub show_findings: bool,
    pub show_stats_overlay: bool,
    pub show_settings_overlay: bool,
    pub settings_overlay_cursor: usize, // legacy -- kept for compatibility, driven by settings_overlay.focus
    pub settings_overlay: Option<SettingsOverlayState>,
    pub local_models: Vec<String>, // discovered models (LM Studio + Ollama merged)
    pub lmstudio_models: Vec<String>, // discovered LM Studio model IDs (raw /v1/models ids)
    pub lmstudio_id_to_opencode_path: HashMap<String, String>, // suffix-after-last-slash -> canonical opencode path (e.g. "qwen3-coder-30b" -> "lmstudio/qwen/qwen3-coder-30b")
    pub ollama_models: Vec<String>, // discovered Ollama model names (raw /api/tags names)
    pub claude_cli_available: bool,  // `claude --version` succeeded
    pub codex_cli_available: bool,   // `codex --version` succeeded
    pub copilot_available: bool,     // `gh auth token` succeeded
    pub local_model_cursor: usize,  // index into local_models for current selection
    pub selected_local_model: String, // persisted selection, from config or cycling
    pub builder_cursor: usize,      // index into unified builder list (specs + local)
    pub stats_overlay_report: Option<StatsReport>,
    pub stats_overlay_scroll: usize,
    pub findings_scroll: usize,
    pub last_orchestrator_outcome: Option<OrchestratorOutcome>,
    pub patterns_scroll: usize,
    pub patterns_cache: Option<Vec<crate::patterns::Pattern>>,
    pub patterns_dir_cache: Option<std::path::PathBuf>,
    pub last_pattern_match_mode: Option<String>, // "semantic", "keyword-only", "cooldown"
    pub session_patterns: Vec<PatternEvent>,     // pattern activity (learned + used) this session
    pub skill_citation_summary: Option<SkillCitationSummary>,
    pub(super) skill_citation_summary_loaded_at: Option<std::time::Instant>,
    pub session_skill_citations_set: std::collections::HashSet<String>,
    pub session_skill_citation_count: usize,
    pub session_plugins_used: Vec<PluginEvent>, // plugin injections this session
    pub session_feat_commits: usize,
    pub session_wip_commits: usize,
    pub git_initialized: bool,
    pub git_branch: String,
    pub git_remote: Option<String>,
    pub git_dirty_count: usize,
    pub show_git_init_offer: bool,
    pub gh_cli_available: bool,
    pub session_patterns_learned: usize,
    pub session_review_high: usize,
    pub session_review_medium: usize,
    #[allow(dead_code)]
    pub session_review_low: usize,
    pub session_start: DateTime<Utc>,
    pub session_cost_usd: f64,
    pub session_input_tokens: u64,
    pub session_output_tokens: u64,
    pub agent_context_pct: Option<u8>, // Context window % used by current/last agent
    pub dual_build: DualBuildState,
    pub spid_context_pcts: [Option<u8>; 5], // Per-stage context %: [Query, Research, Plan, Build, Audit]
    pub stage_context_pcts: HashMap<String, u8>, // Custom-card context % keyed by pipeline stage id
    pub task_start: Option<DateTime<Utc>>,
    pub task_stages_seen: Vec<AgentRole>,
    pub(super) startup_scroll_debounce_ticks: u8,
    pub focused_pane: TuiPane,
    pub running_explorer: Option<StartupState>,
    pub show_running_explorer: bool,
    pub surface_summary_overlay: Option<SurfaceSummaryOverlay>,
    pub explorer_context_menu: Option<ExplorerContextMenu>,
    pub mouse_over_separator: bool,
    /// Full uppercase label of the pipeline tile the mouse is currently
    /// hovering over (e.g. Some("QUERY"), Some("SHIP")). None when the
    /// cursor isn't over a tile. Status bar reads this to surface the long
    /// name since rendered tiles use 1-2 char abbreviations.
    pub hovered_pipeline_label: Option<String>,
    pub available_plugins: Vec<PluginDisplayInfo>,
    pub plugins_cursor: usize,
    /// Externally-discovered skills surfaced under the "External Skills"
    /// section of the startup screen (T1.27). Empty until the project's
    /// startup-state initializer scans for AGENTS.md / .cursorrules /
    /// `.claude/skills/`.
    pub available_external_skills: Vec<ExternalSkillDisplayInfo>,
    // ─── Plugin & Pattern Telemetry Counters ───
    pub plugin_inject_count: HashMap<String, usize>,
    pub plugin_reference_count: HashMap<String, usize>,
    pub pattern_inject_count: usize,
    pub pattern_apply_count: usize,
    pub plugin_keywords: HashMap<String, Vec<String>>,
    pub active_pattern_keywords: HashMap<String, Vec<String>>,
    pub tui_theme: TuiTheme,
    pub ship_active: bool,
    pub status_summary: String,
    pub stream_state: StreamState,
    /// Number of TextDelta chunks accumulated for the current writing burst.
    /// Reset to 0 on every set_agent and every state transition out of WritingText.
    pub stream_text_delta_count: usize,
    pub parallel_builder_progress: Option<(usize, usize)>, // (total, done) when parallel builder active
    pub(super) pending_transition: Option<PendingTransition>,
    pub(super) tasks_file_lock: Arc<Mutex<()>>,
    /// Shared cost counter (millicents) — written by TUI event handler, read by build loop.
    pub(super) session_cost_millicents: Arc<std::sync::atomic::AtomicU64>,
    /// Active tmux session names for the current run (displayed in dashboard).
    pub tmux_session_names: Vec<String>,
    /// Whether Docker sandbox isolation is active for agent subprocesses.
    pub sandbox_active: bool,
    /// Whether sandbox is enabled in config (may not be active if Docker/image missing).
    pub sandbox_enabled: bool,
    /// Human-readable sandbox status label for TUI display.
    pub sandbox_status_label: String,
    pub stats_loading: bool,
    /// True when the TUI is showing a commit approval prompt.
    pub awaiting_commit_approval: bool,
    /// The task ID being approved (for display in the prompt).
    pub approval_task_id: Option<String>,
    /// The proposed commit type (for display, e.g. "feat").
    pub approval_proposed_type: Option<String>,
    pub(super) commit_approval_gates: HashMap<String, Arc<SyncFlag>>,
    pub(super) commit_approval_results: HashMap<String, Arc<SyncFlag>>,
    pub(super) approval_session_id: Option<String>,
    /// Queue of (session_id, task_id, proposed_commit_type) for approvals that
    /// arrived while another approval was already being shown to the user.
    pub(super) pending_approvals: VecDeque<(String, String, String)>,
    pub(super) event_tx: Option<tokio::sync::mpsc::UnboundedSender<AppEvent>>,
    /// Percentage of the middle row given to the agent output pane (default 30, range 20-80).
    pub agent_pane_split: u16,
    /// True while the user is dragging the agent/task-queue vertical separator.
    pub dragging_split: bool,
    /// Timestamp of the last scroll event, used to compute velocity multiplier.
    pub last_scroll_at: Option<std::time::Instant>,
    pub last_commit_brief: Option<crate::git::LastCommitBrief>,
    /// Absolute path to TASKS.md for the current project. Set in `refresh_plan_counts`
    /// during startup; consumed by the live-reload watcher in the Tick handlers.
    pub(super) tasks_file_path: Option<PathBuf>,
    /// Last mtime observed for `tasks_file_path`. The watcher polls every Nth tick
    /// and triggers reconcile only when the on-disk mtime exceeds this value.
    /// Refreshed on every successful reload AND on `LoopEvent::TasksFileMtime` so
    /// the build loop's own writes are not double-counted as foreign edits.
    pub(super) tasks_file_mtime: Option<SystemTime>,
    /// Reserved for tick-aligned double-stat protection. Stays optional --
    /// only adding now to avoid a future struct-shape migration.
    #[allow(dead_code)]
    pub(super) tasks_file_last_stat_tick: usize,
}

impl AppState {
    pub(crate) fn new(buildloop_dir: PathBuf) -> Self {
        // Re-hydrate the eval report from disk on startup. Without this,
        // closing and reopening Foundry hides the EVAL badge until the
        // next task completes -- even though .buildloop/eval-report.json
        // is sitting right there from the prior run. The settings overlay
        // populates the cache when opened (see open_settings_overlay in
        // app.rs), but the status meter renders directly from this field
        // and won't see anything until something forces a refresh.
        let initial_eval_mtime = std::fs::metadata(
            buildloop_dir.join(crate::eval::report::EVAL_REPORT_FILENAME),
        )
        .ok()
        .and_then(|m| m.modified().ok());
        let initial_eval_cache =
            crate::eval::report::read_report(&buildloop_dir);
        Self {
            buildloop_dir,
            eval_report_cache: initial_eval_cache,
            eval_report_mtime: initial_eval_mtime,
            phase: AppPhase::Startup,
            startup: None,
            planning: None,
            current_task: None,
            current_classification: None,
            next_task_hint: None,
            current_agent: None,
            current_agent_stage_id: None,
            current_agent_model: None,
            agent_output: Vec::new(),
            scroll_offset: 0,
            log_messages: Vec::new(),
            project_name: String::new(),
            completed_count: 0,
            total_count: 0,
            task_queue: Vec::new(),
            task_queue_scroll: 0,
            task_history: HashMap::new(),
            task_history_order: Vec::new(),
            discovery_round: 0,
            is_discovering: false,
            should_quit: false,
            confirm_quit: false,
            show_no_tasks_warning: false,
            show_welcome: true,
            welcome_message: crate::tui::random_fallback_message().to_string(),
            observatory_session_id: None,
            stop_after_task: false,
            running_screen_modal: None,
            typed_error_toast: None,
            typed_error_can_retry: false,
            last_typed_error: None,
            events_received: 0,
            tick_count: 0,
            update_available: None,
            inject_input: None,
            show_run_view: false,
            run_mode: "auto".into(),
            dual_selection: DualSelection::Off,
            builder_model_specs: Vec::new(),
            arena_mode: "solo".into(),
            build_stage_label: String::new(),
            awaiting_review: false,
            review_gates: HashMap::new(),
            review_session_id: None,
            pending_reviews: VecDeque::new(),
            awaiting_pr: None,
            pr_poll_last_check: None,
            show_patterns: false,
            show_findings: false,
            show_stats_overlay: false,
            show_settings_overlay: false,
            settings_overlay_cursor: 0,
            settings_overlay: None,
            local_models: Vec::new(),
            lmstudio_models: Vec::new(),
            lmstudio_id_to_opencode_path: HashMap::new(),
            ollama_models: Vec::new(),
            claude_cli_available: false,
            codex_cli_available: false,
            copilot_available: false,
            local_model_cursor: 0,
            selected_local_model: String::new(),
            builder_cursor: 0,
            stats_overlay_report: None,
            stats_overlay_scroll: 0,
            findings_scroll: 0,
            last_orchestrator_outcome: None,
            patterns_scroll: 0,
            patterns_cache: None,
            patterns_dir_cache: None,
            last_pattern_match_mode: None,
            session_feat_commits: 0,
            session_wip_commits: 0,
            git_initialized: false,
            git_branch: String::new(),
            git_remote: None,
            git_dirty_count: 0,
            show_git_init_offer: false,
            gh_cli_available: false,
            session_patterns: Vec::new(),
            skill_citation_summary: None,
            skill_citation_summary_loaded_at: None,
            session_skill_citations_set: std::collections::HashSet::new(),
            session_skill_citation_count: 0,
            session_plugins_used: Vec::new(),
            session_patterns_learned: 0,
            session_review_high: 0,
            session_review_medium: 0,
            session_review_low: 0,
            session_start: Utc::now(),
            session_cost_usd: 0.0,
            session_input_tokens: 0,
            session_output_tokens: 0,
            agent_context_pct: None,
            dual_build: DualBuildState::default(),
            spid_context_pcts: [None; 5],
            stage_context_pcts: HashMap::new(),
            task_start: None,
            task_stages_seen: Vec::new(),
            startup_scroll_debounce_ticks: 0,
            focused_pane: TuiPane::Explorer,
            running_explorer: None,
            show_running_explorer: false,
            surface_summary_overlay: None,
            explorer_context_menu: None,
            mouse_over_separator: false,
            hovered_pipeline_label: None,
            available_plugins: Vec::new(),
            plugins_cursor: 0,
            available_external_skills: Vec::new(),
            plugin_inject_count: HashMap::new(),
            plugin_reference_count: HashMap::new(),
            pattern_inject_count: 0,
            pattern_apply_count: 0,
            plugin_keywords: HashMap::new(),
            active_pattern_keywords: HashMap::new(),
            tui_theme: TuiTheme::default(),
            ship_active: false,
            status_summary: String::new(),
            stream_state: StreamState::Idle,
            stream_text_delta_count: 0,
            parallel_builder_progress: None,
            pending_transition: None,
            tasks_file_lock: Arc::new(Mutex::new(())),
            session_cost_millicents: Arc::new(std::sync::atomic::AtomicU64::new(0)),
            tmux_session_names: Vec::new(),
            sandbox_active: false,
            sandbox_enabled: true,
            sandbox_status_label: String::new(),
            awaiting_commit_approval: false,
            approval_task_id: None,
            approval_proposed_type: None,
            commit_approval_gates: HashMap::new(),
            commit_approval_results: HashMap::new(),
            approval_session_id: None,
            pending_approvals: VecDeque::new(),
            event_tx: None,
            stats_loading: false,
            agent_pane_split: 30,
            dragging_split: false,
            last_scroll_at: None,
            last_commit_brief: None,
            tasks_file_path: None,
            tasks_file_mtime: None,
            tasks_file_last_stat_tick: 0,
        }
    }

    pub(super) fn log(&mut self, msg: impl Into<String>) {
        self.log_messages.push((Utc::now(), msg.into()));
        if self.log_messages.len() > LOG_MESSAGES_CAP {
            let excess = self.log_messages.len() - LOG_MESSAGES_CAP;
            self.log_messages.drain(..excess);
        }
    }

    pub(super) fn write_stop_file(&mut self) {
        if let Err(e) = std::fs::create_dir_all(&self.buildloop_dir) {
            self.log(format!("Warning: failed to create .buildloop dir: {}", e));
            return;
        }
        if let Err(e) = std::fs::write(self.buildloop_dir.join("stop"), "") {
            self.log(format!("Warning: failed to write stop file: {}", e));
        }
    }

    pub(super) fn remove_stop_file(&mut self) {
        if let Err(e) = std::fs::remove_file(self.buildloop_dir.join("stop")) {
            if e.kind() != std::io::ErrorKind::NotFound {
                self.log(format!("Warning: failed to remove stop file: {}", e));
            }
        }
    }

    pub(super) fn clear_agent(&mut self) {
        self.current_agent = None;
        self.current_agent_stage_id = None;
        self.current_agent_model = None;
        self.agent_output.clear();
        self.scroll_offset = 0;
        self.stream_state = StreamState::Idle;
        self.stream_text_delta_count = 0;
    }

    pub(super) fn reset_dual_build(&mut self) {
        self.dual_build = DualBuildState::default();
    }

    pub(super) fn set_agent(&mut self, role: AgentRole, model: &str) {
        let stage_id = role.slug().to_string();
        self.set_agent_for_stage(role, model, stage_id);
    }

    pub(super) fn set_agent_for_stage(&mut self, role: AgentRole, model: &str, stage_id: String) {
        self.agent_output.clear();
        self.scroll_offset = 0;
        self.events_received = 0;
        self.agent_context_pct = None;
        self.status_summary = String::new();
        self.stream_state = StreamState::Idle;
        self.stream_text_delta_count = 0;
        self.current_agent_stage_id = Some(stage_id);
        self.current_agent = Some((role, Utc::now()));
        self.current_agent_model = Some(model.to_string());
    }

    /// Poll TASKS.md and reconcile any external edits into the in-memory queue.
    /// Returns `true` iff a reconcile actually ran. Skips silently when the
    /// path is unset, mtime is unchanged, or the file cannot be parsed.
    pub(super) fn handle_tasks_file_change(&mut self) -> bool {
        let path = match self.tasks_file_path.as_ref() {
            Some(p) => p.clone(),
            None => return false,
        };
        let _lock = self
            .tasks_file_lock
            .lock()
            .unwrap_or_else(|e| e.into_inner());
        let current_mtime = std::fs::metadata(&path).and_then(|m| m.modified()).ok();
        if current_mtime == self.tasks_file_mtime {
            return false;
        }
        let fresh = match task::parse_tasks(&path) {
            Ok(t) => t,
            Err(e) => {
                let msg = format!("Live-reload: failed to parse {}: {}", path.display(), e);
                drop(_lock);
                self.log(msg);
                return false;
            }
        };
        let current_id = self.current_task.as_ref().map(|t| t.id.clone());
        let report =
            task::reconcile_with_loaded(&mut self.task_queue, fresh, current_id.as_deref());
        self.total_count = self.task_queue.len();
        self.completed_count = task::count_completed(&self.task_queue);
        let max_scroll = self.task_queue.len().saturating_sub(1);
        if self.task_queue_scroll > max_scroll {
            self.task_queue_scroll = max_scroll;
        }
        self.tasks_file_mtime = current_mtime;
        drop(_lock);
        if !report.added.is_empty() {
            self.log(format!(
                "Live-reload: appended {} task(s): {}",
                report.added.len(),
                report.added.join(", ")
            ));
        }
        if !report.removed.is_empty() {
            self.log(format!(
                "Live-reload: removed {} pending task(s): {}",
                report.removed.len(),
                report.removed.join(", ")
            ));
        }
        if !report.updated_descriptions.is_empty() {
            self.log(format!(
                "Live-reload: updated description on {} task(s): {}",
                report.updated_descriptions.len(),
                report.updated_descriptions.join(", ")
            ));
        }
        if report.locked_running_skipped {
            self.log(
                "Live-reload: external edit to currently-running task description ignored (running task is locked)"
                    .to_string(),
            );
        }
        if report.running_task_missing_on_disk {
            self.log(
                "Live-reload: external edit removed the currently-running task; run continues, will re-mark on next pipeline write"
                    .to_string(),
            );
        }
        true
    }

    pub(super) fn update_counts(&mut self, tasks: &[Task]) {
        self.total_count = tasks.len();
        self.completed_count = task::count_completed(tasks);
    }

    pub(super) fn cap_task_history(&mut self) {
        if self.task_history_order.len() <= TASK_HISTORY_CAP {
            return;
        }
        let excess = self.task_history_order.len() - TASK_HISTORY_CAP;
        for key in self.task_history_order.drain(..excess) {
            self.task_history.remove(&key);
        }
    }

    pub(crate) fn dual_arena_ready(&self) -> bool {
        self.dual_selection == DualSelection::Both
            && self.dual_build.active
            && self.dual_build.finished.iter().all(|done| *done)
            && self.current_task.is_some()
            && self.current_agent.is_none()
    }

    pub fn selected_plugin_names(&self) -> Vec<String> {
        self.available_plugins
            .iter()
            .filter(|e| e.selected)
            .map(|e| e.name.clone())
            .collect()
    }

    /// Returns the human-readable badge label for the currently selected builder.
    /// Local models route through opencode (P32.4); no prefix distinguishes them
    /// from native Claude/Codex specs anymore.
    ///
    /// `build_stage_label` is normally populated on startup from
    /// `Config::active_routing_for_stage("build")`. The fallback to
    /// `builder_model_specs[0]` covers the unlikely case where startup hasn't
    /// run yet (e.g., a freshly constructed AppState in tests) so the
    /// clickable ModelLabel hit target in the startup header doesn't collapse
    /// to zero width.
    pub fn active_builder_label(&self) -> Option<String> {
        if !self.build_stage_label.is_empty() {
            return Some(self.build_stage_label.clone());
        }
        if let Some(spec) = self.builder_model_specs.first() {
            let trimmed = spec.trim();
            if !trimmed.is_empty() {
                return Some(trimmed.to_string());
            }
        }
        None
    }
}

// ─── Task Pipeline History ────────────────────────────────────

#[derive(Debug, Clone, Default)]
pub struct TaskPipelineHistory {
    pub fix_passes: usize,
    pub passed_review: bool,
    pub stages_seen: Vec<AgentRole>,
}

// ─── Events ──────────────────────────────────────────────────

pub(super) enum AppEvent {
    AgentOutput(AgentOutputEvent),
    AgentDone(bool),
    /// Wraps any event with a pipeline index for full-pipeline dual execution.
    DualPipelineEvent(usize, Box<AppEvent>),
    PlanningFinished(PlanningOutcome),
    OrchestratorFinished(crate::orchestrator::OrchestratorOutcome),
    LoopEvent(LoopEvent),
    Key(event::KeyEvent),
    Mouse(MouseEvent),
    Paste(String),
    Tick,
    UpdateAvailable(String),
    OllamaStatus(bool), // true = connected, false = unreachable
    WelcomeMessage(String),
    NarrativeRefresh(Option<crate::git::LastCommitBrief>),
    /// Background model-catalog refresh completed; payload contains
    /// activity-log lines (one per new model, deprecation, or error) that
    /// should be appended to the activity log.
    CatalogRefreshed(Vec<String>),
    /// Discovered local models, split by source so the selection handler can prefix
    /// `lmstudio/` vs `ollama/` correctly when persisting builder routing.
    /// `lmstudio_opencode_map` maps the LM Studio short-id (suffix after the last `/`)
    /// to the canonical opencode model path emitted by `opencode models lmstudio`.
    /// `opencode_warning` is `Some(msg)` when `opencode models lmstudio` failed or
    /// returned an empty list while LM Studio itself reported models.
    LocalModels {
        lmstudio: Vec<String>,
        ollama: Vec<String>,
        lmstudio_opencode_map: HashMap<String, String>,
        opencode_warning: Option<String>,
        claude_available: bool,
        codex_available: bool,
        copilot_available: bool,
    },
    SurfaceSummaryReady {
        surface: ClickableSurface,
        outcome: crate::llm::summary::SummaryOutcome,
    },
}

pub(super) enum LoopEvent {
    TaskStarted(Task),
    TaskClassified {
        task_id: String,
        tier: TaskComplexity,
        override_flag: TaskOverride,
        p_plus_cycles_budget: usize,
    },
    AgentStarted(AgentRole, String),
    AgentStageStarted {
        role: AgentRole,
        stage_id: String,
        model: String,
    },
    DualBuildStarted {
        models: [String; 2],
    },
    DualBuildStreamDone(usize, bool),
    TaskCompleted(String, bool),
    TaskReport {
        task_id: String,
        status: String,
        commit_sha: Option<String>,
        findings_high: usize,
        findings_medium: usize,
        findings_low: usize,
        duration_secs: f64,
    },
    NextTaskUpdated(Option<String>),
    DiscoveryStarted(usize),
    DiscoveryCompleted(usize),
    PluginInjected {
        name: String,
        agent_role: String,
        task_id: String,
    },
    PatternsUsed {
        titles: Vec<String>,
        keywords_by_title: HashMap<String, Vec<String>>,
    },
    SkillCitationsRecorded {
        skill_names: Vec<String>,
    },
    PluginKeywordsLoaded {
        keywords: HashMap<String, Vec<String>>,
    },
    Log(String),
    BackgroundLog(String),
    CountsUpdated(usize, usize),
    QueueUpdated(Vec<Task>),
    /// Sent by the build loop after it writes TASKS.md (mark_done /
    /// update_task_progress) so the TUI can update `state.tasks_file_mtime`
    /// without the watcher reloading on the loop's own write.
    TasksFileMtime(Option<SystemTime>),
    TaskReviewResult {
        task_id: String,
        fix_passes: usize,
        passed: bool,
    },
    WaitingForReview {
        pr_num: Option<u64>,
        session_id: String,
        gate: Arc<SyncFlag>,
    },
    PrApproved {
        pr_num: u64,
        session_id: String,
    },
    PrClosed {
        pr_num: u64,
        session_id: String,
    },
    PrPollChecked,
    ShipStarted,
    ShipDone,
    ParallelBuilderProgress {
        total: usize,
        done: usize,
    },
    BudgetOverrun {
        phase: String,
        target_pct: u8,
        actual_pct: u8,
        recovery: String,
    },
    AwaitCommitApproval {
        task_id: String,
        proposed_commit_type: String,
        session_id: String,
        gate: Arc<SyncFlag>,
        result: Arc<SyncFlag>,
    },
    CommitApprovalResponse {
        approved: bool,
    },
    #[allow(dead_code)]
    TmuxSessionStarted(String),
    StatsReady(Box<StatsReport>),
    StatsLoadFailed,
    SessionIdAssigned(String),
    Finished,
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::path::PathBuf;

    #[test]
    fn test_selected_plugin_names_filters_by_selected_flag() {
        let mut state = AppState::new(PathBuf::from("/tmp/foundry-test-p261-1"));
        state.available_plugins = vec![
            PluginDisplayInfo {
                name: "rust".to_string(),
                selected: true,
                description: String::new(),
                pattern_count: 0,
            },
            PluginDisplayInfo {
                name: "python".to_string(),
                selected: false,
                description: String::new(),
                pattern_count: 0,
            },
            PluginDisplayInfo {
                name: "roblox".to_string(),
                selected: true,
                description: String::new(),
                pattern_count: 0,
            },
            PluginDisplayInfo {
                name: "extend".to_string(),
                selected: false,
                description: String::new(),
                pattern_count: 0,
            },
        ];
        let names = state.selected_plugin_names();
        assert_eq!(names, vec!["rust".to_string(), "roblox".to_string()]);
    }

    #[test]
    fn test_selected_plugin_names_returns_empty_when_none_selected() {
        let mut state = AppState::new(PathBuf::from("/tmp/foundry-test-p261-2"));
        state.available_plugins = vec![PluginDisplayInfo {
            name: "rust".to_string(),
            selected: false,
            description: String::new(),
            pattern_count: 0,
        }];
        assert!(state.selected_plugin_names().is_empty());
    }

    #[test]
    fn test_selected_plugin_names_returns_empty_when_no_plugins() {
        let state = AppState::new(PathBuf::from("/tmp/foundry-test-p261-3"));
        assert!(state.selected_plugin_names().is_empty());
    }

    #[test]
    fn test_selected_plugin_names_preserves_order() {
        let mut state = AppState::new(PathBuf::from("/tmp/foundry-test-p261-4"));
        state.available_plugins = vec![
            PluginDisplayInfo {
                name: "alpha".to_string(),
                selected: true,
                description: String::new(),
                pattern_count: 0,
            },
            PluginDisplayInfo {
                name: "beta".to_string(),
                selected: false,
                description: String::new(),
                pattern_count: 0,
            },
            PluginDisplayInfo {
                name: "gamma".to_string(),
                selected: true,
                description: String::new(),
                pattern_count: 0,
            },
        ];
        assert_eq!(
            state.selected_plugin_names(),
            vec!["alpha".to_string(), "gamma".to_string()]
        );
    }

    #[test]
    fn test_dual_selection_display_label_off() {
        assert_eq!(DualSelection::display_label(&[]), "Off");
    }

    #[test]
    fn test_dual_selection_display_label_claude_solo() {
        assert_eq!(
            DualSelection::display_label(&["claude:opus".to_string()]),
            "Claude Solo"
        );
    }

    #[test]
    fn test_dual_selection_display_label_codex_solo() {
        assert_eq!(
            DualSelection::display_label(&["codex:".to_string()]),
            "Codex Solo"
        );
    }

    #[test]
    fn test_dual_selection_display_label_dual() {
        assert_eq!(
            DualSelection::display_label(&["claude:opus".to_string(), "codex:".to_string()]),
            "Dual: Claude+Codex"
        );
    }

    #[test]
    fn test_settings_overlay_state_visible_rows() {
        let ov = SettingsOverlayState::new();
        let total = ov.visible_row_count();
        assert!(total > 10, "should have sections + expanded fields");
    }

    #[test]
    fn test_settings_overlay_toggle_section() {
        let mut ov = SettingsOverlayState::new();
        let before = ov.visible_row_count();
        ov.toggle_section("routing");
        let after = ov.visible_row_count();
        assert!(after < before, "collapsing a section reduces row count");
        ov.toggle_section("routing");
        assert_eq!(
            ov.visible_row_count(),
            before,
            "re-expanding restores count"
        );
    }

    #[test]
    fn test_settings_overlay_ensure_focus_visible_scrolls() {
        let mut ov = SettingsOverlayState::new();
        ov.focus = 18;
        ov.ensure_focus_visible(8);
        assert_eq!(ov.scroll_offset, 11);
        ov.focus = 2;
        ov.ensure_focus_visible(8);
        assert_eq!(ov.scroll_offset, 2);
    }

    #[test]
    fn test_model_picker_visible_items_with_groups() {
        let entries = vec![
            ModelEntry {
                provider: "claude".into(),
                model: "opus-4-7".into(),
                label: "claude-opus-4-7".into(),
                recommended: true,
                group: "Claude".into(),
            },
            ModelEntry {
                provider: "codex".into(),
                model: "gpt-5.4".into(),
                label: "gpt-5.4".into(),
                recommended: false,
                group: "Codex".into(),
            },
        ];
        let picker = ModelPicker::new("plan", entries);
        let items = picker.visible_items();
        assert_eq!(items.len(), 4); // 2 headers + 2 entries
    }

    #[test]
    fn test_model_picker_filter() {
        let entries = vec![
            ModelEntry {
                provider: "claude".into(),
                model: "opus-4-7".into(),
                label: "claude-opus-4-7".into(),
                recommended: true,
                group: "Claude".into(),
            },
            ModelEntry {
                provider: "codex".into(),
                model: "gpt-5.4".into(),
                label: "gpt-5.4".into(),
                recommended: false,
                group: "Codex".into(),
            },
        ];
        let mut picker = ModelPicker::new("plan", entries);
        picker.filter = "opus".to_string();
        let items = picker.visible_items();
        // Claude header + opus entry; Codex group filtered out entirely
        assert_eq!(items.len(), 2);
    }

    #[test]
    fn test_model_picker_collapse_group() {
        let entries = vec![
            ModelEntry {
                provider: "claude".into(),
                model: "opus-4-7".into(),
                label: "claude-opus-4-7".into(),
                recommended: true,
                group: "Claude".into(),
            },
            ModelEntry {
                provider: "claude".into(),
                model: "sonnet-4-6".into(),
                label: "claude-sonnet-4-6".into(),
                recommended: false,
                group: "Claude".into(),
            },
        ];
        let mut picker = ModelPicker::new("plan", entries);
        assert_eq!(picker.visible_items().len(), 3); // 1 header + 2 entries
        picker.groups_open.remove("Claude");
        assert_eq!(picker.visible_items().len(), 1); // 1 header only
    }

    #[test]
    fn test_two_level_esc_closes_picker_first() {
        let mut ov = SettingsOverlayState::new();
        let entries = vec![ModelEntry {
            provider: "claude".into(),
            model: "opus".into(),
            label: "opus".into(),
            recommended: false,
            group: "Claude".into(),
        }];
        ov.picker = Some(ModelPicker::new("plan", entries));
        assert!(ov.picker.is_some());
        // First Esc: close picker
        ov.picker = None;
        assert!(ov.picker.is_none());
    }

    #[test]
    fn test_routing_section_has_stage_rows() {
        let sections = settings_sections(false);
        let routing = sections.iter().find(|s| s.id == "routing").unwrap();
        let stage_fields: Vec<&str> = routing
            .fields
            .iter()
            .filter(|f| f.kind == FieldKind::StagePicker)
            .map(|f| f.id)
            .collect();
        assert!(stage_fields.contains(&"stage_plan"), "missing stage_plan");
        assert!(stage_fields.contains(&"stage_build"), "missing stage_build");
        assert!(stage_fields.contains(&"stage_audit"), "missing stage_audit");
        assert_eq!(stage_fields.len(), 9, "expected 9 stage picker rows");
    }

    #[test]
    fn test_routing_section_dual_mode_has_ab_rows() {
        let sections = settings_sections(true);
        let routing = sections.iter().find(|s| s.id == "routing").unwrap();
        let stage_fields: Vec<&str> = routing
            .fields
            .iter()
            .filter(|f| f.kind == FieldKind::StagePicker)
            .map(|f| f.id)
            .collect();
        assert!(stage_fields.contains(&"stage_plan"), "missing stage_plan");
        assert!(
            stage_fields.contains(&"stage_plan_b"),
            "missing stage_plan_b"
        );
        assert!(stage_fields.contains(&"stage_build"), "missing stage_build");
        assert!(
            stage_fields.contains(&"stage_build_b"),
            "missing stage_build_b"
        );
        // 9 A rows + 5 B rows (Discovery, PR Review, Patterns, Fixer excluded from B)
        assert_eq!(stage_fields.len(), 14, "expected 14 stage picker rows (9 A + 5 B)");
    }

    #[test]
    fn test_routing_section_dual_mode_labels() {
        let sections = settings_sections(true);
        let routing = sections.iter().find(|s| s.id == "routing").unwrap();
        let labels: Vec<&str> = routing.fields.iter().map(|f| f.label).collect();
        assert!(labels.contains(&"  Plan (A)"), "missing Plan (A) label");
        assert!(labels.contains(&"  Plan (B)"), "missing Plan (B) label");
        assert!(!labels.contains(&"  Plan"), "solo label should not appear in dual mode");
    }

    #[test]
    fn test_routing_section_solo_mode_no_b_rows() {
        let sections = settings_sections(false);
        let routing = sections.iter().find(|s| s.id == "routing").unwrap();
        let b_fields: Vec<&str> = routing
            .fields
            .iter()
            .filter(|f| f.id.ends_with("_b"))
            .map(|f| f.id)
            .collect();
        assert!(b_fields.is_empty(), "solo mode should have no _b fields");
    }

    #[test]
    fn test_routing_section_has_arena_field() {
        for dual in [false, true] {
            let sections = settings_sections(dual);
            let routing = sections.iter().find(|s| s.id == "routing").unwrap();
            let arena = routing.fields.iter().find(|f| f.id == "arena");
            assert!(arena.is_some(), "arena field missing in dual={}", dual);
            assert_eq!(arena.unwrap().kind, FieldKind::Enum);
        }
    }

    #[test]
    fn test_dual_mode_excludes_patterns_and_pr_review_b() {
        let sections = settings_sections(true);
        let routing = sections.iter().find(|s| s.id == "routing").unwrap();
        let b_ids: Vec<&str> = routing
            .fields
            .iter()
            .filter(|f| f.id.ends_with("_b"))
            .map(|f| f.id)
            .collect();
        assert!(
            !b_ids.contains(&"stage_patterns_b"),
            "patterns B should not appear (hardcoded Claude)"
        );
        assert!(
            !b_ids.contains(&"stage_pr_review_b"),
            "PR review B should not appear (not in build loop)"
        );
        assert!(
            b_ids.contains(&"stage_build_b"),
            "build B should still appear"
        );
    }

    #[test]
    fn test_dual_mode_keeps_patterns_and_pr_review_a_rows() {
        let sections = settings_sections(true);
        let routing = sections.iter().find(|s| s.id == "routing").unwrap();
        let a_ids: Vec<&str> = routing
            .fields
            .iter()
            .filter(|f| !f.id.ends_with("_b") && f.kind == FieldKind::StagePicker)
            .map(|f| f.id)
            .collect();
        assert!(a_ids.contains(&"stage_patterns"), "patterns A should still appear");
        assert!(a_ids.contains(&"stage_pr_review"), "PR review A should still appear");
    }

    #[test]
    fn pipeline_health_section_present_and_collapsed_by_default() {
        let sections = settings_sections(false);
        let ph = sections.iter().find(|s| s.id == "pipeline_health");
        assert!(ph.is_some(), "pipeline_health section missing");
        let ph = ph.unwrap();
        assert_eq!(ph.kind, SectionKind::PipelineHealth);
        assert!(!ph.default_expanded);
        assert!(ph.fields.is_empty());
    }

    #[test]
    fn pipeline_health_rows_returns_button_when_cache_empty() {
        let ov = SettingsOverlayState::new();
        assert!(ov.eval_report_cache.is_none());
        let rows = ov.pipeline_health_rows();
        assert!(rows
            .iter()
            .any(|r| matches!(r, OverlayRow::ActionButton(Action::RerunEvalOnLastRun))));
    }
}
