use std::collections::HashMap;
use std::sync::atomic::AtomicBool;
use std::sync::{Arc, Mutex};
use std::time::SystemTime;

use chrono::{DateTime, Utc};
use crossterm::event::{self, MouseEvent};
use std::path::PathBuf;

use crate::agent::{AgentOutputEvent, AgentRole};
use crate::git;
use crate::orchestrator::OrchestratorOutcome;
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
    pub stop_after_task: bool,
    pub events_received: usize,
    pub tick_count: usize,
    pub update_available: Option<String>,
    pub inject_input: Option<String>,
    pub show_run_view: bool, // Tab toggle: startup shows run view (pipeline+queue+config)
    pub run_mode: String,    // "auto", "sprint", or "review"
    pub awaiting_review: bool,
    pub(super) review_gate: Option<Arc<AtomicBool>>,
    pub awaiting_pr: Option<u64>,
    pub pr_poll_last_check: Option<std::time::Instant>,
    pub show_patterns: bool,
    pub show_findings: bool,
    pub findings_scroll: usize,
    pub last_orchestrator_outcome: Option<OrchestratorOutcome>,
    pub patterns_scroll: usize,
    pub patterns_cache: Option<Vec<crate::patterns::Pattern>>,
    pub patterns_dir_cache: Option<std::path::PathBuf>,
    pub last_pattern_match_mode: Option<String>, // "semantic", "keyword-only", "cooldown"
    pub session_patterns: Vec<PatternEvent>, // pattern activity (learned + used) this session
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
    pub agent_context_pct: Option<u8>, // Context window % used by current/last agent
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
    pub(super) pending_transition: Option<PendingTransition>,
    pub(super) tasks_file_lock: Arc<Mutex<()>>,
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
            stop_after_task: false,
            events_received: 0,
            tick_count: 0,
            update_available: None,
            inject_input: None,
            show_run_view: false,
            run_mode: "auto".into(),
            awaiting_review: false,
            review_gate: None,
            awaiting_pr: None,
            pr_poll_last_check: None,
            show_patterns: false,
            show_findings: false,
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
            agent_context_pct: None,
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
            pending_transition: None,
            tasks_file_lock: Arc::new(Mutex::new(())),
        }
    }

    pub(super) fn log(&mut self, msg: impl Into<String>) {
        self.log_messages.push((Utc::now(), msg.into()));
        if self.log_messages.len() > LOG_MESSAGES_CAP {
            let excess = self.log_messages.len() - LOG_MESSAGES_CAP;
            self.log_messages.drain(..excess);
        }
    }

    pub(super) fn clear_agent(&mut self) {
        self.current_agent = None;
        self.current_agent_model = None;
        self.agent_output.clear();
        self.scroll_offset = 0;
    }

    pub(super) fn set_agent(&mut self, role: AgentRole, model: &str) {
        self.agent_output.clear();
        self.scroll_offset = 0;
        self.events_received = 0;
        self.agent_context_pct = None;
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
    PlanningFinished(PlanningOutcome),
    OrchestratorFinished(crate::orchestrator::OrchestratorOutcome),
    LoopEvent(LoopEvent),
    Key(event::KeyEvent),
    Mouse(MouseEvent),
    Paste(String),
    Tick,
    UpdateAvailable(String),
    OllamaStatus(bool), // true = connected, false = unreachable
}

pub(super) enum LoopEvent {
    TaskStarted(Task),
    AgentStarted(AgentRole, String),
    TaskCompleted(String, bool),
    NextTaskUpdated(Option<String>),
    DiscoveryStarted(usize),
    DiscoveryCompleted(usize),
    ExtensionInjected { name: String, agent_role: String, task_id: String },
    PatternsUsed { titles: Vec<String>, keywords_by_title: HashMap<String, Vec<String>> },
    ExtensionKeywordsLoaded { keywords: HashMap<String, Vec<String>> },
    Log(String),
    BackgroundLog(String),
    CountsUpdated(usize, usize),
    QueueUpdated(Vec<Task>),
    TaskReviewResult {
        task_id: String,
        fix_passes: usize,
        passed: bool,
    },
    WaitingForReview(Option<u64>),
    PrApproved(u64),
    PrClosed(u64),
    PrPollChecked,
    Finished,
}
