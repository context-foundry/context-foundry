use std::collections::HashMap;
use std::sync::{Arc, Mutex};

use chrono::{DateTime, Utc};
use crossterm::event::{self, MouseEvent};
use std::path::PathBuf;

use crate::agent::{AgentOutputEvent, AgentRole};
use crate::git;
use crate::orchestrator::OrchestratorOutcome;
use crate::task::{self, Task};

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
pub enum StartupAction {
    Continue,
    DescribeWork,
    DesignWithReview,
    ScanProject,
    ViewTasks,
    EditSpec,
}

#[derive(Debug, Clone)]
pub struct StartupState {
    pub scenario: StartupScenario,
    pub plan_status: PlanStatus,
    pub has_spec: bool,
    pub selected_action: usize,
    pub actions: Vec<StartupAction>,
    pub entering_intent: bool,
    pub intent_input: String,
    pub status_message: Option<String>,
    pub git_context: Option<git::GitContext>,
    pub tasks_file_name: String,
    pub plan_preview_lines: Vec<String>,
    pub plan_scroll_offset: usize,
    pub next_pending_task: Option<String>,
    pub spec_file_name: String,
    pub spec_preview_lines: Vec<String>,
    pub spec_scroll_offset: usize,
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
    pub show_patterns: bool,
    pub show_findings: bool,
    pub findings_scroll: usize,
    pub last_orchestrator_outcome: Option<OrchestratorOutcome>,
    pub patterns_scroll: usize,
    pub last_pattern_match_mode: Option<String>, // "semantic", "keyword-only", "cooldown"
    pub session_feat_commits: usize,
    pub session_wip_commits: usize,
    pub session_patterns_learned: usize,
    pub session_review_high: usize,
    pub session_review_medium: usize,
    pub session_review_low: usize,
    pub session_start: DateTime<Utc>,
    pub task_start: Option<DateTime<Utc>>,
    pub task_stages_seen: Vec<AgentRole>,
    pub(super) startup_scroll_debounce_ticks: u8,
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
            show_patterns: false,
            show_findings: false,
            findings_scroll: 0,
            last_orchestrator_outcome: None,
            patterns_scroll: 0,
            last_pattern_match_mode: None,
            session_feat_commits: 0,
            session_wip_commits: 0,
            session_patterns_learned: 0,
            session_review_high: 0,
            session_review_medium: 0,
            session_review_low: 0,
            session_start: Utc::now(),
            task_start: None,
            task_stages_seen: Vec::new(),
            startup_scroll_debounce_ticks: 0,
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
    Log(String),
    BackgroundLog(String),
    CountsUpdated(usize, usize),
    QueueUpdated(Vec<Task>),
    TaskReviewResult {
        task_id: String,
        fix_passes: usize,
        passed: bool,
    },
    Finished,
}
