use crate::sync_flag::SyncFlag;
use std::collections::{HashMap, VecDeque};
use std::sync::{Arc, Mutex};
use std::time::SystemTime;

use chrono::{DateTime, Utc};
use crossterm::event::{self, MouseEvent};
use std::path::PathBuf;

use crate::agent::{AgentErrorKind, AgentOutputEvent, AgentRole};
use crate::git;
use crate::orchestrator::OrchestratorOutcome;
use crate::stats::StatsReport;
use crate::task::{self, Task};
use crate::tui::theme::TuiTheme;

const LOG_MESSAGES_CAP: usize = 500;
const TASK_HISTORY_CAP: usize = 200;

// ─── App State ───────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AppPhase {
    Startup,
    Planning,
    Running,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TuiPane {
    Explorer,
    Preview,
    AgentOutput,
    TaskQueue,
    PatternsLearned,
    Extensions,
}

#[derive(Debug, Clone)]
pub struct ExtensionDisplayInfo {
    pub name: String,
    pub selected: bool,
    pub description: String,
    pub pattern_count: usize,
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

#[derive(Debug, Clone)]
pub struct ExtensionEvent {
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
    pub context_pcts: [[Option<u8>; 4]; 2], // Per-pipeline SPID context %: [pipeline][Scout, Plan, Implement, Doubt]
    pub finished: [bool; 2],
    pub stages: [Option<AgentRole>; 2], // Current SPID stage per pipeline
    pub stage_models: [String; 2],      // Model label for current stage
}

pub struct AppState {
    pub buildloop_dir: PathBuf,
    pub phase: AppPhase,
    pub startup: Option<StartupState>,
    pub planning: Option<PlanningState>,
    pub current_task: Option<Task>,
    pub next_task_hint: Option<String>,
    pub current_agent: Option<(AgentRole, DateTime<Utc>)>,
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
    pub observatory_session_id: Option<String>,
    pub stop_after_task: bool,
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
    pub run_mode: String,    // "auto", "sprint", or "review"
    pub dual_selection: DualSelection, // Ctrl+D cycle: Off, First, Second, Both
    pub builder_model_specs: Vec<String>, // raw config values (e.g., ["claude:opus", "codex:"])
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
    pub settings_overlay_cursor: usize,
    pub local_models: Vec<String>,       // discovered models (LM Studio + Ollama merged)
    pub lmstudio_models: Vec<String>,    // discovered LM Studio model IDs (raw /v1/models ids)
    pub lmstudio_id_to_opencode_path: HashMap<String, String>, // suffix-after-last-slash -> canonical opencode path (e.g. "qwen3-coder-30b" -> "lmstudio/qwen/qwen3-coder-30b")
    pub ollama_models: Vec<String>,      // discovered Ollama model names (raw /api/tags names)
    pub local_model_cursor: usize,       // index into local_models for current selection
    pub selected_local_model: String,    // persisted selection, from config or cycling
    pub builder_cursor: usize,           // index into unified builder list (specs + local)
    pub stats_overlay_report: Option<StatsReport>,
    pub stats_overlay_scroll: usize,
    pub findings_scroll: usize,
    pub last_orchestrator_outcome: Option<OrchestratorOutcome>,
    pub patterns_scroll: usize,
    pub patterns_cache: Option<Vec<crate::patterns::Pattern>>,
    pub patterns_dir_cache: Option<std::path::PathBuf>,
    pub last_pattern_match_mode: Option<String>, // "semantic", "keyword-only", "cooldown"
    pub session_patterns: Vec<PatternEvent>,     // pattern activity (learned + used) this session
    pub session_extensions_used: Vec<ExtensionEvent>, // extension injections this session
    pub session_feat_commits: usize,
    pub session_wip_commits: usize,
    pub git_initialized: bool,
    pub git_branch: String,
    pub git_remote: Option<String>,
    pub git_dirty_count: usize,
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
    pub spid_context_pcts: [Option<u8>; 4], // Per-stage context %: [Scout, Plan, Implement, Doubt]
    pub task_start: Option<DateTime<Utc>>,
    pub task_stages_seen: Vec<AgentRole>,
    pub(super) startup_scroll_debounce_ticks: u8,
    pub focused_pane: TuiPane,
    pub running_explorer: Option<StartupState>,
    pub show_running_explorer: bool,
    pub available_extensions: Vec<ExtensionDisplayInfo>,
    pub extensions_cursor: usize,
    // ─── Extension & Pattern Telemetry Counters ───
    pub extension_inject_count: HashMap<String, usize>,
    pub extension_reference_count: HashMap<String, usize>,
    pub pattern_inject_count: usize,
    pub pattern_apply_count: usize,
    pub extension_keywords: HashMap<String, Vec<String>>,
    pub active_pattern_keywords: HashMap<String, Vec<String>>,
    pub tui_theme: TuiTheme,
    pub ship_active: bool,
    pub status_summary: String,
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
    /// Percentage of the middle row given to the agent output pane (default 60, range 20-80).
    pub agent_pane_split: u16,
    /// True while the user is dragging the agent/task-queue vertical separator.
    pub dragging_split: bool,
    /// Timestamp of the last scroll event, used to compute velocity multiplier.
    pub last_scroll_at: Option<std::time::Instant>,
}

impl AppState {
    pub(crate) fn new(buildloop_dir: PathBuf) -> Self {
        Self {
            buildloop_dir,
            phase: AppPhase::Startup,
            startup: None,
            planning: None,
            current_task: None,
            next_task_hint: None,
            current_agent: None,
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
            observatory_session_id: None,
            stop_after_task: false,
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
            local_models: Vec::new(),
            lmstudio_models: Vec::new(),
            lmstudio_id_to_opencode_path: HashMap::new(),
            ollama_models: Vec::new(),
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
            session_patterns: Vec::new(),
            session_extensions_used: Vec::new(),
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
            spid_context_pcts: [None; 4],
            task_start: None,
            task_stages_seen: Vec::new(),
            startup_scroll_debounce_ticks: 0,
            focused_pane: TuiPane::Explorer,
            running_explorer: None,
            show_running_explorer: false,
            available_extensions: Vec::new(),
            extensions_cursor: 0,
            extension_inject_count: HashMap::new(),
            extension_reference_count: HashMap::new(),
            pattern_inject_count: 0,
            pattern_apply_count: 0,
            extension_keywords: HashMap::new(),
            active_pattern_keywords: HashMap::new(),
            tui_theme: TuiTheme::default(),
            ship_active: false,
            status_summary: String::new(),
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
            agent_pane_split: 60,
            dragging_split: false,
            last_scroll_at: None,
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
        self.current_agent_model = None;
        self.agent_output.clear();
        self.scroll_offset = 0;
    }

    pub(super) fn reset_dual_build(&mut self) {
        self.dual_build = DualBuildState::default();
    }

    pub(super) fn set_agent(&mut self, role: AgentRole, model: &str) {
        self.agent_output.clear();
        self.scroll_offset = 0;
        self.events_received = 0;
        self.agent_context_pct = None;
        self.status_summary = String::new();
        self.current_agent = Some((role, Utc::now()));
        self.current_agent_model = Some(model.to_string());
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

    pub fn selected_extension_names(&self) -> Vec<String> {
        self.available_extensions
            .iter()
            .filter(|e| e.selected)
            .map(|e| e.name.clone())
            .collect()
    }

    /// Returns the human-readable badge label for the currently selected builder.
    /// Local models are shown with a "~" prefix to distinguish them from active pipeline specs
    /// (local model routing is not yet wired to the agent pipeline).
    pub fn active_builder_label(&self) -> Option<String> {
        use crate::config::Config;
        let mut list: Vec<String> = self
            .builder_model_specs
            .iter()
            .map(|s| Config::readable_spec(s))
            .collect();
        let spec_count = list.len();
        if spec_count >= 2 {
            let combined = list
                .iter()
                .take(spec_count)
                .cloned()
                .collect::<Vec<_>>()
                .join("/");
            list.push(combined);
        }
        let local_start = list.len();
        for m in &self.local_models {
            if !list.contains(m) {
                list.push(m.clone());
            }
        }
        let cursor = self.builder_cursor.min(list.len().saturating_sub(1));
        list.into_iter().enumerate().nth(cursor).map(|(i, label)| {
            if i >= local_start {
                format!("~{label}")
            } else {
                label
            }
        })
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
    },
}

pub(super) enum LoopEvent {
    TaskStarted(Task),
    AgentStarted(AgentRole, String),
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
    ExtensionInjected {
        name: String,
        agent_role: String,
        task_id: String,
    },
    PatternsUsed {
        titles: Vec<String>,
        keywords_by_title: HashMap<String, Vec<String>>,
    },
    ExtensionKeywordsLoaded {
        keywords: HashMap<String, Vec<String>>,
    },
    Log(String),
    BackgroundLog(String),
    CountsUpdated(usize, usize),
    QueueUpdated(Vec<Task>),
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
    fn test_selected_extension_names_filters_by_selected_flag() {
        let mut state = AppState::new(PathBuf::from("/tmp/foundry-test-p261-1"));
        state.available_extensions = vec![
            ExtensionDisplayInfo {
                name: "rust".to_string(),
                selected: true,
                description: String::new(),
                pattern_count: 0,
            },
            ExtensionDisplayInfo {
                name: "python".to_string(),
                selected: false,
                description: String::new(),
                pattern_count: 0,
            },
            ExtensionDisplayInfo {
                name: "roblox".to_string(),
                selected: true,
                description: String::new(),
                pattern_count: 0,
            },
            ExtensionDisplayInfo {
                name: "extend".to_string(),
                selected: false,
                description: String::new(),
                pattern_count: 0,
            },
        ];
        let names = state.selected_extension_names();
        assert_eq!(names, vec!["rust".to_string(), "roblox".to_string()]);
    }

    #[test]
    fn test_selected_extension_names_returns_empty_when_none_selected() {
        let mut state = AppState::new(PathBuf::from("/tmp/foundry-test-p261-2"));
        state.available_extensions = vec![ExtensionDisplayInfo {
            name: "rust".to_string(),
            selected: false,
            description: String::new(),
            pattern_count: 0,
        }];
        assert!(state.selected_extension_names().is_empty());
    }

    #[test]
    fn test_selected_extension_names_returns_empty_when_no_extensions() {
        let state = AppState::new(PathBuf::from("/tmp/foundry-test-p261-3"));
        assert!(state.selected_extension_names().is_empty());
    }

    #[test]
    fn test_selected_extension_names_preserves_order() {
        let mut state = AppState::new(PathBuf::from("/tmp/foundry-test-p261-4"));
        state.available_extensions = vec![
            ExtensionDisplayInfo {
                name: "alpha".to_string(),
                selected: true,
                description: String::new(),
                pattern_count: 0,
            },
            ExtensionDisplayInfo {
                name: "beta".to_string(),
                selected: false,
                description: String::new(),
                pattern_count: 0,
            },
            ExtensionDisplayInfo {
                name: "gamma".to_string(),
                selected: true,
                description: String::new(),
                pattern_count: 0,
            },
        ];
        assert_eq!(
            state.selected_extension_names(),
            vec!["alpha".to_string(), "gamma".to_string()]
        );
    }
}
