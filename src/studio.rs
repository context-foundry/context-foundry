use anyhow::{Context, Result};
use chrono::{DateTime, Utc};
use crossterm::event::{
    self, Event, KeyCode, KeyModifiers, MouseButton, MouseEvent, MouseEventKind,
};
use futures::{future::join_all, StreamExt};
use ratatui::{
    layout::{Constraint, Direction, Layout, Rect},
    style::{Color, Modifier, Style},
    text::{Line, Span},
    widgets::{Block, BorderType, Borders, Clear, List, ListItem, Paragraph, Wrap},
};
use serde::{Deserialize, Serialize};
use std::{
    collections::{BTreeSet, HashMap},
    fs,
    io::Read,
    path::{Component, Path, PathBuf},
    process::{Command, Stdio},
    sync::{
        atomic::{AtomicBool, Ordering},
        Arc,
    },
    time::{Duration, Instant, SystemTime},
};
use tokio::sync::mpsc;
use tokio::task::JoinHandle;

use crate::{
    agent::{self, AgentOutputEvent, ModelProvider, ProviderRunOptions},
    config::Config,
    tui,
    utils::truncate_str,
};

const STUDIO_ROOT_DIR: &str = ".foundry/studio";
const STUDIO_CONTRACTS_DIR: &str = "contracts";
const STUDIO_SELECTED_CONTRACT_FILE: &str = ".selected";
const STUDIO_SELECTED_EDITOR_FILE: &str = ".editor";
const DEFAULT_PROMPT: &str = "";
const LIVE_PROBE_TTL_SECS: i64 = 900;
const LIVE_PROBE_TIMEOUT_SECS: u64 = 20;
const FOLLOW_UP_CONTEXT_MAX_LINES: usize = 120;
const FOLLOW_UP_CONTEXT_MAX_CHARS: usize = 12_000;
const SHUTDOWN_GRACE_MILLIS: u64 = 1500;
const DEFAULT_LEFT_COLUMN_PERCENT: u16 = 44;
const DEFAULT_LEFT_SCAN_HEIGHT: u16 = 6;
const DEFAULT_LEFT_PROMPT_HEIGHT: u16 = 8;
const DEFAULT_LEFT_CONTRACTS_HEIGHT: u16 = 8;
const DEFAULT_RIGHT_SESSIONS_HEIGHT: u16 = 8;
const DEFAULT_RIGHT_ACTIVITY_HEIGHT: u16 = 10;
const MIN_LEFT_COLUMN_WIDTH: u16 = 28;
const MIN_RIGHT_COLUMN_WIDTH: u16 = 36;
const MIN_LEFT_SECTION_HEIGHT: u16 = 5;
const MIN_LEFT_BRIEF_HEIGHT: u16 = 8;
const MIN_RIGHT_SECTION_HEIGHT: u16 = 5;
const MIN_OUTPUT_HEIGHT: u16 = 8;
const COLUMN_SPLIT_WIDTH: u16 = 1;
const ROW_SPLIT_HEIGHT: u16 = 1;
const LEFT_SPLIT_COUNT: u16 = 3;
const RIGHT_SPLIT_COUNT: u16 = 2;
const COLUMN_RESIZE_HIT_MARGIN: u16 = 2;
const MAX_INLINE_FILE_BYTES: usize = 64 * 1024;
const MAX_TREE_DEPTH: usize = 3;
const MAX_TREE_FILES: usize = 50;
const MAX_TOTAL_ATTACHMENT_CHARS: usize = 100_000;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum FocusedPane {
    Scan,
    Prompt,
    Contracts,
    ExecutionBrief,
    Sessions,
    Output,
    Activity,
}

impl FocusedPane {
    fn label(self) -> &'static str {
        match self {
            FocusedPane::Scan => "project scan",
            FocusedPane::Prompt => "prompt",
            FocusedPane::Contracts => "contracts",
            FocusedPane::ExecutionBrief => "execution brief",
            FocusedPane::Sessions => "sessions",
            FocusedPane::Output => "output",
            FocusedPane::Activity => "activity",
        }
    }

    fn next(self) -> Self {
        match self {
            FocusedPane::Scan => FocusedPane::Prompt,
            FocusedPane::Prompt => FocusedPane::Contracts,
            FocusedPane::Contracts => FocusedPane::ExecutionBrief,
            FocusedPane::ExecutionBrief => FocusedPane::Sessions,
            FocusedPane::Sessions => FocusedPane::Output,
            FocusedPane::Output => FocusedPane::Activity,
            FocusedPane::Activity => FocusedPane::Scan,
        }
    }

    fn previous(self) -> Self {
        match self {
            FocusedPane::Scan => FocusedPane::Activity,
            FocusedPane::Prompt => FocusedPane::Scan,
            FocusedPane::Contracts => FocusedPane::Prompt,
            FocusedPane::ExecutionBrief => FocusedPane::Contracts,
            FocusedPane::Sessions => FocusedPane::ExecutionBrief,
            FocusedPane::Output => FocusedPane::Sessions,
            FocusedPane::Activity => FocusedPane::Output,
        }
    }
}

struct StudioLayout {
    header: Rect,
    body: Rect,
    left_body: Rect,
    right_body: Rect,
    column_split: Rect,
    left_scan_prompt_split: Rect,
    left_prompt_contracts_split: Rect,
    left_contracts_brief_split: Rect,
    right_sessions_output_split: Rect,
    right_output_activity_split: Rect,
    scan: Rect,
    prompt: Rect,
    contracts: Rect,
    execution_brief: Rect,
    sessions: Rect,
    output: Rect,
    activity: Rect,
    status: Rect,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
struct StudioLayoutConfig {
    left_column_percent: u16,
    left_scan_height: u16,
    left_prompt_height: u16,
    left_contracts_height: u16,
    right_sessions_height: u16,
    right_activity_height: u16,
}

impl Default for StudioLayoutConfig {
    fn default() -> Self {
        Self {
            left_column_percent: DEFAULT_LEFT_COLUMN_PERCENT,
            left_scan_height: DEFAULT_LEFT_SCAN_HEIGHT,
            left_prompt_height: DEFAULT_LEFT_PROMPT_HEIGHT,
            left_contracts_height: DEFAULT_LEFT_CONTRACTS_HEIGHT,
            right_sessions_height: DEFAULT_RIGHT_SESSIONS_HEIGHT,
            right_activity_height: DEFAULT_RIGHT_ACTIVITY_HEIGHT,
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum ResizeHandle {
    ColumnSplit,
    LeftScanPrompt,
    LeftPromptContracts,
    LeftContractsBrief,
    RightSessionsOutput,
    RightOutputActivity,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
struct ResizeDragState {
    handle: ResizeHandle,
    start_column: u16,
    start_row: u16,
    initial_layout: StudioLayoutConfig,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum ProviderMode {
    Claude,
    Codex,
    Both,
}

impl ProviderMode {
    fn next(self) -> Self {
        match self {
            ProviderMode::Claude => ProviderMode::Codex,
            ProviderMode::Codex => ProviderMode::Both,
            ProviderMode::Both => ProviderMode::Claude,
        }
    }

    fn providers(self) -> &'static [ModelProvider] {
        const CLAUDE_ONLY: &[ModelProvider] = &[ModelProvider::Claude];
        const CODEX_ONLY: &[ModelProvider] = &[ModelProvider::Codex];
        const BOTH: &[ModelProvider] = &[ModelProvider::Claude, ModelProvider::Codex];
        match self {
            ProviderMode::Claude => CLAUDE_ONLY,
            ProviderMode::Codex => CODEX_ONLY,
            ProviderMode::Both => BOTH,
        }
    }
}

impl std::fmt::Display for ProviderMode {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ProviderMode::Claude => write!(f, "claude"),
            ProviderMode::Codex => write!(f, "codex"),
            ProviderMode::Both => write!(f, "both"),
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum WorkspaceMode {
    Isolated,
    Shared,
}

impl WorkspaceMode {
    fn next(self) -> Self {
        match self {
            WorkspaceMode::Isolated => WorkspaceMode::Shared,
            WorkspaceMode::Shared => WorkspaceMode::Isolated,
        }
    }
}

impl std::fmt::Display for WorkspaceMode {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            WorkspaceMode::Isolated => write!(f, "isolated"),
            WorkspaceMode::Shared => write!(f, "shared"),
        }
    }
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum SessionStatus {
    Running,
    Succeeded,
    Failed,
}

impl SessionStatus {
    fn label(self) -> &'static str {
        match self {
            SessionStatus::Running => "running",
            SessionStatus::Succeeded => "done",
            SessionStatus::Failed => "failed",
        }
    }

    fn color(self) -> Color {
        match self {
            SessionStatus::Running => Color::Yellow,
            SessionStatus::Succeeded => Color::Green,
            SessionStatus::Failed => Color::Red,
        }
    }
}

#[derive(Clone, Debug)]
struct ProjectScan {
    generated_at: DateTime<Utc>,
    top_level: Vec<String>,
    stack_signals: Vec<String>,
    data_candidates: Vec<String>,
    output_targets: Vec<String>,
}

impl ProjectScan {
    fn summary_lines(&self) -> Vec<String> {
        let mut lines = Vec::new();
        lines.push(format!(
            "scan: {}",
            self.generated_at.format("%Y-%m-%d %H:%M:%S UTC")
        ));
        lines.push(format!(
            "stack: {}",
            join_or_none(&self.stack_signals, ", ")
        ));
        lines.push(format!("top: {}", join_or_none(&self.top_level, ", ")));
        lines.push(format!(
            "data: {}",
            join_or_none(&self.data_candidates, ", ")
        ));
        lines.push(format!(
            "outputs: {}",
            join_or_none(&self.output_targets, ", ")
        ));
        lines
    }
}

#[derive(Clone, Debug)]
struct SessionState {
    id: String,
    provider: ModelProvider,
    model: String,
    workspace_dir: PathBuf,
    artifact_dir: PathBuf,
    status: SessionStatus,
    started_at: DateTime<Utc>,
    output: Vec<String>,
    artifacts: Vec<PathBuf>,
    error: Option<String>,
    event_count: usize,
    last_event_at: Option<DateTime<Utc>>,
    prompt_path: Option<PathBuf>,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
struct AttachmentSpec {
    path: String,
    mode: AttachmentMode,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    label: Option<String>,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
enum AttachmentMode {
    InlineFile,
    DirectoryTree,
}

#[derive(Clone, Debug)]
struct ResolvedAttachment {
    spec: AttachmentSpec,
    label: String,
    content: String,
    truncated: bool,
    error: Option<String>,
}

#[derive(Clone, Debug)]
struct PreviewPromptCache {
    rendered_prompt: String,
}

#[derive(Clone, Debug)]
struct ExecutionContract {
    file_name: String,
    path: PathBuf,
    name: String,
    body: String,
    attachments: Vec<AttachmentSpec>,
}

#[derive(Clone)]
struct SessionLaunch {
    id: String,
    provider: ModelProvider,
    model: String,
    workspace_mode: WorkspaceMode,
    project_dir: PathBuf,
    workspace_dir: PathBuf,
    artifact_dir: PathBuf,
    prompt: String,
    execution_contract: ExecutionContract,
    scan: ProjectScan,
    prior_context: Option<String>,
    prepare_workspace: bool,
}

enum PendingStudioAction {
    EditExecutionContract {
        path: PathBuf,
        action_label: &'static str,
    },
    PickExecutionContractAttachment {
        contract_path: PathBuf,
    },
}

struct EditorGuideState {
    action: PendingStudioAction,
}

struct DeleteConfirmationState {
    contract_name: String,
}

#[derive(Clone, Debug, Default)]
struct AttachmentManagerState {
    selected_attachment: usize,
    marked_attachments: BTreeSet<usize>,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum EditorChoice {
    System,
    Vi,
    Nano,
    CodeWait,
}

impl EditorChoice {
    fn next(self) -> Self {
        match self {
            Self::System => Self::Nano,
            Self::Nano => Self::Vi,
            Self::Vi => Self::CodeWait,
            Self::CodeWait => Self::System,
        }
    }

    fn persist_value(self) -> &'static str {
        match self {
            Self::System => "system",
            Self::Vi => "vi",
            Self::Nano => "nano",
            Self::CodeWait => "code-wait",
        }
    }

    fn from_persisted(value: &str) -> Option<Self> {
        match value {
            "system" => Some(Self::System),
            "vi" => Some(Self::Vi),
            "nano" => Some(Self::Nano),
            "code-wait" => Some(Self::CodeWait),
            _ => None,
        }
    }
}

struct StudioState {
    project_dir: PathBuf,
    prompt: String,
    is_editing_prompt: bool,
    focused_pane: FocusedPane,
    provider_mode: ProviderMode,
    workspace_mode: WorkspaceMode,
    scan: ProjectScan,
    execution_contracts: Vec<ExecutionContract>,
    selected_execution_contract: usize,
    sessions: Vec<SessionState>,
    selected_session: usize,
    output_scroll: usize,
    preview_scroll: usize,
    preview_cache: Option<PreviewPromptCache>,
    logs: Vec<(DateTime<Utc>, String)>,
    tick_count: usize,
    should_quit: bool,
    shutdown_initiated: bool,
    layout_config: StudioLayoutConfig,
    active_resize: Option<ResizeDragState>,
    claude_model: String,
    codex_model: String,
    claude_readiness: ProviderReadiness,
    codex_readiness: ProviderReadiness,
    editor_choice: EditorChoice,
    session_controls: HashMap<String, SessionControl>,
    pending_action: Option<PendingStudioAction>,
    editor_guide: Option<EditorGuideState>,
    delete_confirmation: Option<DeleteConfirmationState>,
    attachment_manager: Option<AttachmentManagerState>,
}

struct SessionControl {
    cancel_flag: Arc<AtomicBool>,
    task: tokio::task::JoinHandle<()>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
enum ProviderState {
    Ready,
    Missing,
    Blocked,
}

#[derive(Clone, Debug)]
struct ProviderReadiness {
    state: ProviderState,
    detail: String,
}

#[derive(Debug)]
struct AuthCheck {
    authenticated: bool,
    detail: String,
}

#[derive(Debug)]
struct CapturedCommand {
    success: bool,
    stdout: String,
    stderr: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
struct ProbeCache {
    entries: Vec<CachedProbeEntry>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct CachedProbeEntry {
    provider: String,
    model: String,
    auth_detail: String,
    checked_at: DateTime<Utc>,
}

#[derive(Debug, Deserialize)]
struct ClaudeAuthStatus {
    #[serde(rename = "loggedIn")]
    logged_in: bool,
    #[serde(rename = "authMethod")]
    auth_method: Option<String>,
    #[serde(rename = "apiProvider")]
    api_provider: Option<String>,
}

impl ProviderReadiness {
    fn ready(detail: impl Into<String>) -> Self {
        Self {
            state: ProviderState::Ready,
            detail: detail.into(),
        }
    }

    fn missing(detail: impl Into<String>) -> Self {
        Self {
            state: ProviderState::Missing,
            detail: detail.into(),
        }
    }

    fn blocked(detail: impl Into<String>) -> Self {
        Self {
            state: ProviderState::Blocked,
            detail: detail.into(),
        }
    }

    fn is_available(&self) -> bool {
        self.state == ProviderState::Ready
    }

    fn short_label(&self) -> &'static str {
        match self.state {
            ProviderState::Ready => "ready",
            ProviderState::Missing => "missing",
            ProviderState::Blocked => "blocked",
        }
    }
}

impl StudioState {
    fn new(project_dir: &Path, config: &Config) -> Result<Self> {
        let scan = scan_project(project_dir)?;
        let claude_model = config.studio_claude_model.clone();
        let codex_model = config.studio_codex_model.clone();
        let claude_readiness = probe_claude_readiness(project_dir, &claude_model);
        let codex_readiness = probe_codex_readiness(project_dir, &codex_model);
        let provider_mode = default_provider_mode(&claude_readiness, &codex_readiness);
        let (execution_contracts, selected_execution_contract) =
            load_execution_contracts(project_dir)?;
        let editor_choice = load_editor_choice(project_dir);
        Ok(Self {
            project_dir: project_dir.to_path_buf(),
            prompt: DEFAULT_PROMPT.to_string(),
            is_editing_prompt: false,
            focused_pane: FocusedPane::Prompt,
            provider_mode,
            workspace_mode: WorkspaceMode::Isolated,
            scan,
            execution_contracts,
            selected_execution_contract,
            sessions: Vec::new(),
            selected_session: 0,
            output_scroll: 0,
            preview_scroll: 0,
            preview_cache: None,
            logs: Vec::new(),
            tick_count: 0,
            should_quit: false,
            shutdown_initiated: false,
            layout_config: StudioLayoutConfig::default(),
            active_resize: None,
            claude_model,
            codex_model,
            claude_readiness,
            codex_readiness,
            editor_choice,
            session_controls: HashMap::new(),
            pending_action: None,
            editor_guide: None,
            delete_confirmation: None,
            attachment_manager: None,
        })
    }

    fn log(&mut self, message: impl Into<String>) {
        self.logs.push((Utc::now(), message.into()));
    }

    fn invalidate_preview_cache(&mut self) {
        self.preview_cache = None;
    }

    fn has_running_sessions(&self) -> bool {
        self.sessions
            .iter()
            .any(|session| session.status == SessionStatus::Running)
    }

    fn preview_prompt(&mut self) -> String {
        if let Some(cache) = &self.preview_cache {
            return cache.rendered_prompt.clone();
        }

        let provider_label = match self.provider_mode {
            ProviderMode::Both => "Claude + Codex".to_string(),
            ProviderMode::Claude => "Claude".to_string(),
            ProviderMode::Codex => "Codex".to_string(),
        };
        let execution_contract = self.selected_execution_contract().clone();
        let workspace_dir = match self.workspace_mode {
            WorkspaceMode::Shared => self.project_dir.display().to_string(),
            WorkspaceMode::Isolated => "<isolated-workspace-per-provider>".to_string(),
        };
        let artifact_dir = match self.workspace_mode {
            WorkspaceMode::Shared => self
                .project_dir
                .join(STUDIO_ROOT_DIR)
                .join("artifacts/<run>/<provider>")
                .display()
                .to_string(),
            WorkspaceMode::Isolated => {
                "<workspace>/.foundry/studio/artifacts/<run>/<provider>".to_string()
            }
        };
        let attachments =
            resolve_all_attachments(&execution_contract.attachments, &self.project_dir);
        let prompt = compose_smoothed_prompt(
            &provider_label,
            &self.prompt,
            &execution_contract,
            &attachments,
            &self.scan,
            &workspace_dir,
            &artifact_dir,
            None,
        );
        self.preview_cache = Some(PreviewPromptCache {
            rendered_prompt: prompt.clone(),
        });
        prompt
    }

    fn selected_session(&self) -> Option<&SessionState> {
        self.sessions.get(self.selected_session)
    }

    fn selected_execution_contract(&self) -> &ExecutionContract {
        &self.execution_contracts[self.selected_execution_contract]
    }

    fn set_selected_execution_contract_index(&mut self, index: usize) {
        self.selected_execution_contract = index;
        self.preview_scroll = 0;
        self.invalidate_preview_cache();
        self.sync_attachment_manager_selection();
    }

    fn refresh_execution_contracts(&mut self) -> Result<()> {
        let selected_file = self
            .execution_contracts
            .get(self.selected_execution_contract)
            .map(|contract| contract.file_name.clone());
        let (contracts, selected_index) =
            load_execution_contracts_with_selection(&self.project_dir, selected_file.as_deref())?;
        self.execution_contracts = contracts;
        self.set_selected_execution_contract_index(selected_index);
        Ok(())
    }

    fn sync_attachment_manager_selection(&mut self) {
        let attachment_len = self
            .execution_contracts
            .get(self.selected_execution_contract)
            .map(|contract| contract.attachments.len())
            .unwrap_or(0);
        if let Some(manager) = self.attachment_manager.as_mut() {
            manager.marked_attachments = manager
                .marked_attachments
                .iter()
                .copied()
                .filter(|idx| *idx < attachment_len)
                .collect();
            if attachment_len == 0 {
                manager.selected_attachment = 0;
            } else {
                manager.selected_attachment = manager
                    .selected_attachment
                    .min(attachment_len.saturating_sub(1));
            }
        }
    }

    fn model_for(&self, provider: ModelProvider) -> &str {
        match provider {
            ModelProvider::Claude => &self.claude_model,
            ModelProvider::Codex => &self.codex_model,
        }
    }

    fn provider_readiness(&self, provider: ModelProvider) -> &ProviderReadiness {
        match provider {
            ModelProvider::Claude => &self.claude_readiness,
            ModelProvider::Codex => &self.codex_readiness,
        }
    }
}

enum StudioEvent {
    Key(event::KeyEvent),
    Mouse(MouseEvent),
    Quit,
    Tick,
    SessionOutput {
        session_id: String,
        event: AgentOutputEvent,
    },
    SessionFinished {
        session_id: String,
        success: bool,
        artifacts: Vec<PathBuf>,
        error: Option<String>,
    },
}

fn spawn_terminal_event_reader(event_tx: mpsc::UnboundedSender<StudioEvent>) -> JoinHandle<()> {
    tokio::spawn(async move {
        let mut reader = crossterm::event::EventStream::new();
        loop {
            if let Some(Ok(event)) = reader.next().await {
                let studio_event = match event {
                    Event::Key(key) => Some(StudioEvent::Key(key)),
                    Event::Mouse(mouse) => Some(StudioEvent::Mouse(mouse)),
                    _ => None,
                };
                if let Some(studio_event) = studio_event {
                    if event_tx.send(studio_event).is_err() {
                        break;
                    }
                }
            }
        }
    })
}

pub async fn run_tui(project_dir: &Path) -> Result<()> {
    let config = Config::load(project_dir);
    let mut state = StudioState::new(project_dir, &config)?;
    state.log(format!("studio ready for {}", project_dir.display()));
    state.log(format!(
        "selected execution contract: {}",
        state.selected_execution_contract().name
    ));
    log_provider_probe(&mut state, ModelProvider::Claude);
    log_provider_probe(&mut state, ModelProvider::Codex);

    let mut terminal = tui::setup_terminal()?;
    let (event_tx, mut event_rx) = mpsc::unbounded_channel::<StudioEvent>();

    let tick_tx = event_tx.clone();
    tokio::spawn(async move {
        let mut interval = tokio::time::interval(Duration::from_millis(100));
        loop {
            interval.tick().await;
            if tick_tx.send(StudioEvent::Tick).is_err() {
                break;
            }
        }
    });

    let mut terminal_event_reader = spawn_terminal_event_reader(event_tx.clone());

    let quit_tx = event_tx.clone();
    tokio::spawn(async move {
        if tokio::signal::ctrl_c().await.is_ok() {
            let _ = quit_tx.send(StudioEvent::Quit);
        }
    });

    loop {
        terminal.draw(|frame| render(frame, &mut state))?;

        match event_rx.recv().await {
            Some(StudioEvent::Tick) => {
                state.tick_count = state.tick_count.wrapping_add(1);
                while let Ok(evt) = event_rx.try_recv() {
                    handle_event(&mut state, evt, &event_tx);
                    if state.should_quit {
                        break;
                    }
                }
            }
            Some(event) => handle_event(&mut state, event, &event_tx),
            None => break,
        }

        if let Some(action) = state.pending_action.take() {
            handle_pending_action(
                &mut terminal,
                &mut state,
                action,
                &event_tx,
                &mut terminal_event_reader,
            )?;
        }

        if state.should_quit {
            break;
        }
    }

    shutdown_active_sessions(&mut state).await;
    terminal_event_reader.abort();
    tui::restore_terminal(&mut terminal)?;
    println!("Foundry Studio closed.");
    Ok(())
}

fn handle_event(
    state: &mut StudioState,
    event: StudioEvent,
    tx: &mpsc::UnboundedSender<StudioEvent>,
) {
    match event {
        StudioEvent::Tick => {
            state.tick_count = state.tick_count.wrapping_add(1);
        }
        StudioEvent::Key(key) => {
            if state.delete_confirmation.is_some() {
                handle_delete_confirmation_key(state, key);
            } else if state.editor_guide.is_some() {
                handle_editor_guide_key(state, key);
            } else if state.attachment_manager.is_some() {
                handle_attachment_manager_key(state, key);
            } else if is_quit_key(key) {
                request_quit(state);
            } else if state.is_editing_prompt {
                handle_prompt_edit_key(state, key);
            } else {
                handle_global_key(state, key, tx);
            }
        }
        StudioEvent::Mouse(mouse) => {
            if state.editor_guide.is_none()
                && state.delete_confirmation.is_none()
                && state.attachment_manager.is_none()
            {
                handle_mouse_event(state, mouse)
            }
        }
        StudioEvent::Quit => {
            request_quit(state);
        }
        StudioEvent::SessionOutput { session_id, event } => {
            if let Some(session) = state.sessions.iter_mut().find(|s| s.id == session_id) {
                session.event_count += 1;
                session.last_event_at = Some(Utc::now());
                match event {
                    AgentOutputEvent::Text(text) => session.output.push(text),
                    AgentOutputEvent::ToolUse {
                        tool,
                        input_preview,
                    } => {
                        if input_preview.is_empty() {
                            session.output.push(format!("[tool] {}", tool));
                        } else {
                            session
                                .output
                                .push(format!("[tool] {} — {}", tool, input_preview));
                        }
                    }
                    AgentOutputEvent::ToolResult { output_preview } => {
                        if !output_preview.is_empty() {
                            session.output.push(format!("[result] {}", output_preview));
                        }
                    }
                    AgentOutputEvent::Stderr(line) => {
                        session.output.push(format!("[stderr] {}", line));
                    }
                    AgentOutputEvent::Result(text) => {
                        session.output.push(String::new());
                        for line in text.lines().take(24) {
                            session.output.push(line.to_string());
                        }
                    }
                }
            }
        }
        StudioEvent::SessionFinished {
            session_id,
            success,
            artifacts,
            error,
        } => {
            let mut completion_log: Option<(String, usize)> = None;
            state.session_controls.remove(&session_id);
            if let Some(session) = state.sessions.iter_mut().find(|s| s.id == session_id) {
                session.status = if success {
                    SessionStatus::Succeeded
                } else {
                    SessionStatus::Failed
                };
                session.artifacts = artifacts;
                session.error = error;
                completion_log = Some((
                    format!(
                        "{} session {} ({})",
                        session.provider,
                        session.status.label(),
                        display_model_name(&session.model)
                    ),
                    session.artifacts.len(),
                ));
            }
            if let Some((message, artifact_count)) = completion_log {
                state.log(message);
                if artifact_count > 0 {
                    state.log(format!("{} artifact(s) captured", artifact_count));
                }
            }
        }
    }
}

fn handle_editor_guide_key(state: &mut StudioState, key: event::KeyEvent) {
    match key.code {
        KeyCode::Enter => {
            if let Some(guide) = state.editor_guide.take() {
                state.pending_action = Some(guide.action);
            }
        }
        KeyCode::Char('v') => {
            cycle_editor_choice(state);
        }
        KeyCode::Esc | KeyCode::Char('q') => {
            state.editor_guide = None;
            state.log("editor launch canceled");
        }
        _ => {}
    }
}

fn handle_delete_confirmation_key(state: &mut StudioState, key: event::KeyEvent) {
    match key.code {
        KeyCode::Char(c) if c.eq_ignore_ascii_case(&'y') => {
            state.delete_confirmation = None;
            if let Err(err) = delete_selected_execution_contract(state) {
                state.log(format!("contract delete failed: {}", err));
            }
        }
        KeyCode::Char(c) if c.eq_ignore_ascii_case(&'n') => {
            state.delete_confirmation = None;
            state.log("contract delete canceled");
        }
        KeyCode::Esc => {
            state.delete_confirmation = None;
            state.log("contract delete canceled");
        }
        _ => {}
    }
}

fn handle_attachment_manager_key(state: &mut StudioState, key: event::KeyEvent) {
    match key.code {
        KeyCode::Esc | KeyCode::Enter | KeyCode::Char('q') => {
            state.attachment_manager = None;
        }
        KeyCode::Char('a') => {
            if let Err(err) = queue_selected_execution_contract_attachment_action(state) {
                state.log(format!("contract attachment edit failed: {}", err));
            }
        }
        KeyCode::Char('d') => {
            if let Err(err) = remove_selected_execution_contract_attachments(state) {
                state.log(format!("attachment delete failed: {}", err));
            }
        }
        KeyCode::Char(' ') => toggle_selected_attachment_mark(state),
        KeyCode::Up => cycle_attachment_manager_selection(state, false),
        KeyCode::Down => cycle_attachment_manager_selection(state, true),
        _ => {}
    }
}

fn request_quit(state: &mut StudioState) {
    if state.shutdown_initiated {
        state.should_quit = true;
        return;
    }

    state.shutdown_initiated = true;
    if state.has_running_sessions() {
        state.log(format!(
            "shutting down {} active session(s)",
            state.session_controls.len()
        ));
        cancel_running_sessions(state);
    }
    state.should_quit = true;
}

fn cancel_running_sessions(state: &mut StudioState) {
    for control in state.session_controls.values() {
        control.cancel_flag.store(true, Ordering::Relaxed);
    }
}

async fn shutdown_active_sessions(state: &mut StudioState) {
    if state.session_controls.is_empty() {
        return;
    }

    cancel_running_sessions(state);
    let controls = std::mem::take(&mut state.session_controls);
    let shutdowns = controls
        .into_iter()
        .map(|(session_id, mut control)| async move {
            let finished = tokio::time::timeout(
                Duration::from_millis(SHUTDOWN_GRACE_MILLIS),
                &mut control.task,
            )
            .await;
            if finished.is_err() {
                control.task.abort();
                eprintln!(
                    "Foundry Studio: forced shutdown for session {} after {}ms",
                    session_id, SHUTDOWN_GRACE_MILLIS
                );
            }
        });
    join_all(shutdowns).await;
}

fn is_quit_key(key: event::KeyEvent) -> bool {
    key.code == KeyCode::Char('q')
        || (key.code == KeyCode::Char('c') && key.modifiers.contains(KeyModifiers::CONTROL))
}

fn set_focused_pane(state: &mut StudioState, pane: FocusedPane) {
    if state.focused_pane != pane && state.is_editing_prompt && pane != FocusedPane::Prompt {
        state.is_editing_prompt = false;
        state.log("prompt edit mode off");
    }
    state.focused_pane = pane;
}

fn handle_prompt_edit_key(state: &mut StudioState, key: event::KeyEvent) {
    match key.code {
        KeyCode::Esc => {
            state.is_editing_prompt = false;
            state.log("prompt edit mode off");
        }
        KeyCode::Backspace => {
            state.prompt.pop();
            state.invalidate_preview_cache();
        }
        KeyCode::Enter => {
            state.prompt.push('\n');
            state.invalidate_preview_cache();
        }
        KeyCode::Tab => {
            state.prompt.push_str("    ");
            state.invalidate_preview_cache();
        }
        KeyCode::Char('u') if key.modifiers.contains(KeyModifiers::CONTROL) => {
            state.prompt.clear();
            state.invalidate_preview_cache();
        }
        KeyCode::Char(c) if key.modifiers.is_empty() || key.modifiers == KeyModifiers::SHIFT => {
            state.prompt.push(c);
            state.invalidate_preview_cache();
        }
        _ => {}
    }
}

fn handle_global_key(
    state: &mut StudioState,
    key: event::KeyEvent,
    tx: &mpsc::UnboundedSender<StudioEvent>,
) {
    match key.code {
        KeyCode::Enter => {
            if state.focused_pane == FocusedPane::Contracts {
                edit_selected_execution_contract(state);
            }
        }
        KeyCode::Char('e') => {
            set_focused_pane(state, FocusedPane::Prompt);
            state.is_editing_prompt = true;
            state.log("prompt edit mode on");
        }
        KeyCode::Char('c') => {
            cycle_execution_contract(state, true);
        }
        KeyCode::Char('a') => {
            if let Err(err) = create_execution_contract(state) {
                state.log(format!("contract creation failed: {}", err));
            }
        }
        KeyCode::Char('x') => {
            edit_selected_execution_contract(state);
        }
        KeyCode::Char('d') => {
            request_delete_selected_execution_contract(state);
        }
        KeyCode::Char('t') => {
            if state.focused_pane == FocusedPane::Contracts {
                open_attachment_manager(state);
            }
        }
        KeyCode::Char('v') => {
            cycle_editor_choice(state);
        }
        KeyCode::Tab => {
            let next_pane = state.focused_pane.next();
            set_focused_pane(state, next_pane);
        }
        KeyCode::BackTab => {
            let previous_pane = state.focused_pane.previous();
            set_focused_pane(state, previous_pane);
        }
        KeyCode::Char('p') => {
            state.provider_mode = state.provider_mode.next();
            state.invalidate_preview_cache();
            state.log(format!("provider mode: {}", state.provider_mode));
        }
        KeyCode::Char('w') => {
            state.workspace_mode = state.workspace_mode.next();
            state.invalidate_preview_cache();
            state.log(format!("workspace mode: {}", state.workspace_mode));
        }
        KeyCode::Char('r') => match scan_project(&state.project_dir) {
            Ok(scan) => {
                state.scan = scan;
                match state.refresh_execution_contracts() {
                    Ok(()) => {
                        state.invalidate_preview_cache();
                        state.log("project scan refreshed");
                    }
                    Err(err) => state.log(format!(
                        "project scan refreshed, but contract reload failed: {}",
                        err
                    )),
                }
            }
            Err(err) => state.log(format!("scan refresh failed: {}", err)),
        },
        KeyCode::Char('s') => {
            start_sessions(state, tx.clone(), false);
        }
        KeyCode::Char('f') => {
            start_sessions(state, tx.clone(), true);
        }
        KeyCode::Char('j') => {
            if !state.sessions.is_empty() {
                state.selected_session = (state.selected_session + 1) % state.sessions.len();
                state.output_scroll = 0;
            }
        }
        KeyCode::Char('k') => {
            if !state.sessions.is_empty() {
                state.selected_session = state
                    .selected_session
                    .checked_sub(1)
                    .unwrap_or_else(|| state.sessions.len().saturating_sub(1));
                state.output_scroll = 0;
            }
        }
        KeyCode::Up => match state.focused_pane {
            FocusedPane::Contracts => cycle_execution_contract(state, false),
            FocusedPane::Output => {
                state.output_scroll = state.output_scroll.saturating_add(3);
            }
            _ => {}
        },
        KeyCode::Down => match state.focused_pane {
            FocusedPane::Contracts => cycle_execution_contract(state, true),
            FocusedPane::Output => {
                state.output_scroll = state.output_scroll.saturating_sub(3);
            }
            _ => {}
        },
        _ => {}
    }
}

fn handle_mouse_event(state: &mut StudioState, mouse: MouseEvent) {
    let Some(layout) = current_studio_layout(state) else {
        return;
    };

    match mouse.kind {
        MouseEventKind::Down(MouseButton::Left) => {
            if let Some(handle) = resize_handle_at(&layout, mouse.column, mouse.row) {
                state.active_resize = Some(ResizeDragState {
                    handle,
                    start_column: mouse.column,
                    start_row: mouse.row,
                    initial_layout: state.layout_config,
                });
                return;
            }
            if let Some(pane) = pane_at_position(&layout, mouse.column, mouse.row) {
                activate_pane_from_click(state, pane, layout.sessions, layout.contracts, mouse.row);
            }
        }
        MouseEventKind::Drag(MouseButton::Left) => {
            if let Some(drag) = state.active_resize {
                apply_resize_drag(state, &layout, drag, mouse.column, mouse.row);
            }
        }
        MouseEventKind::Up(MouseButton::Left) => {
            state.active_resize = None;
        }
        MouseEventKind::ScrollUp => {
            if let Some(pane) = pane_at_position(&layout, mouse.column, mouse.row) {
                scroll_pane_by_mouse(state, pane, &layout, true);
            }
        }
        MouseEventKind::ScrollDown => {
            if let Some(pane) = pane_at_position(&layout, mouse.column, mouse.row) {
                scroll_pane_by_mouse(state, pane, &layout, false);
            }
        }
        _ => {}
    }
}

fn activate_pane_from_click(
    state: &mut StudioState,
    pane: FocusedPane,
    sessions_area: Rect,
    contracts_area: Rect,
    row: u16,
) {
    if pane == FocusedPane::Sessions {
        select_session_from_click(state, sessions_area, row);
    }
    if pane == FocusedPane::Contracts {
        select_execution_contract_from_click(state, contracts_area, row);
    }
    set_focused_pane(state, pane);
    if pane == FocusedPane::Prompt && !state.is_editing_prompt {
        state.is_editing_prompt = true;
        state.log("prompt edit mode on");
    }
}

fn scroll_pane_by_mouse(
    state: &mut StudioState,
    pane: FocusedPane,
    layout: &StudioLayout,
    scroll_up: bool,
) {
    match pane {
        FocusedPane::ExecutionBrief => {
            set_focused_pane(state, FocusedPane::ExecutionBrief);
            let delta = if scroll_up { -3 } else { 3 };
            scroll_preview(state, layout.execution_brief, delta);
        }
        FocusedPane::Output => {
            set_focused_pane(state, FocusedPane::Output);
            if scroll_up {
                state.output_scroll = state.output_scroll.saturating_add(3);
            } else {
                state.output_scroll = state.output_scroll.saturating_sub(3);
            }
        }
        _ => {}
    }
}

fn scroll_preview(state: &mut StudioState, area: Rect, delta: i32) {
    let preview = state.preview_prompt();
    let wrapped = wrap_text_lines(&preview, area.width.saturating_sub(2) as usize);
    let max_lines = area.height.saturating_sub(2) as usize;
    let max_scroll = wrapped.len().saturating_sub(max_lines);
    let next = (state.preview_scroll as i32 + delta).clamp(0, max_scroll as i32);
    state.preview_scroll = next as usize;
}

fn start_sessions(
    state: &mut StudioState,
    tx: mpsc::UnboundedSender<StudioEvent>,
    follow_up: bool,
) {
    if state.has_running_sessions() {
        state.log("wait for the current run to finish before starting another");
        return;
    }

    if state.prompt.trim().is_empty() {
        state.log("enter a prompt before starting a run");
        return;
    }

    let follow_up_seed = if follow_up {
        if let Some(session) = state.selected_session() {
            let provider = session.provider;
            let workspace_dir = session.workspace_dir.clone();
            let prior_context = follow_up_context(session);
            if let Some(issue) = follow_up_workspace_issue(&workspace_dir) {
                state.log(issue);
                return;
            }
            state.log(format!(
                "follow-up continues {} in {}",
                provider,
                workspace_dir.display()
            ));
            Some((provider, workspace_dir, prior_context))
        } else {
            state.log("select a session before sending a follow-up");
            return;
        }
    } else {
        None
    };

    let requested: Vec<ModelProvider> = if let Some((provider, _, _)) = &follow_up_seed {
        vec![*provider]
    } else {
        state.provider_mode.providers().to_vec()
    };
    let blocked: Vec<String> = requested
        .iter()
        .filter_map(|provider| {
            let readiness = state.provider_readiness(*provider);
            if readiness.is_available() {
                None
            } else {
                Some(format!("{}: {}", provider, readiness.detail))
            }
        })
        .collect();

    if !blocked.is_empty() {
        state.log(format!("run blocked: {}", blocked.join(" | ")));
        return;
    }

    if !follow_up && state.workspace_mode == WorkspaceMode::Shared && requested.len() > 1 {
        state.log("shared mode with both providers can cause overlapping edits");
    }

    let run_id = Utc::now().format("%Y%m%d-%H%M%S").to_string();
    let project_dir = state.project_dir.clone();
    let scan = state.scan.clone();
    let prompt = state.prompt.clone();
    let execution_contract = state.selected_execution_contract().clone();

    for provider in requested {
        let prior_context = follow_up_seed
            .as_ref()
            .map(|(_, _, context)| context.clone());
        let model = state.model_for(provider).to_string();
        let workspace_dir = if let Some((_, workspace_dir, _)) = &follow_up_seed {
            workspace_dir.clone()
        } else {
            match state.workspace_mode {
                WorkspaceMode::Shared => project_dir.clone(),
                WorkspaceMode::Isolated => project_dir
                    .join(STUDIO_ROOT_DIR)
                    .join("workspaces")
                    .join(provider.slug()),
            }
        };
        let artifact_dir = workspace_dir
            .join(STUDIO_ROOT_DIR)
            .join("artifacts")
            .join(&run_id)
            .join(provider.slug());
        let session_id = format!("{}-{}", run_id, provider.slug());

        state.sessions.push(SessionState {
            id: session_id.clone(),
            provider,
            model: model.clone(),
            workspace_dir: workspace_dir.clone(),
            artifact_dir: artifact_dir.clone(),
            status: SessionStatus::Running,
            started_at: Utc::now(),
            output: vec![format!(
                "{} session {} in {}",
                provider,
                if follow_up { "continuing" } else { "starting" },
                workspace_dir.display()
            )],
            artifacts: Vec::new(),
            error: None,
            event_count: 0,
            last_event_at: None,
            prompt_path: Some(artifact_dir.join("execution-brief.md")),
        });
        state.selected_session = state.sessions.len().saturating_sub(1);
        state.output_scroll = 0;
        state.log(format!(
            "{} {} with model {}",
            if follow_up { "continuing" } else { "starting" },
            provider,
            display_model_name(&model)
        ));

        let control_session_id = session_id.clone();
        let launch = SessionLaunch {
            id: session_id,
            provider,
            model,
            workspace_mode: state.workspace_mode,
            project_dir: project_dir.clone(),
            workspace_dir,
            artifact_dir,
            prompt: prompt.clone(),
            execution_contract: execution_contract.clone(),
            scan: scan.clone(),
            prior_context,
            prepare_workspace: !follow_up,
        };
        let cancel_flag = Arc::new(AtomicBool::new(false));
        let task = tokio::spawn(run_session(launch, tx.clone(), cancel_flag.clone()));
        state
            .session_controls
            .insert(control_session_id, SessionControl { cancel_flag, task });
    }
}

async fn run_session(
    launch: SessionLaunch,
    tx: mpsc::UnboundedSender<StudioEvent>,
    cancel_flag: Arc<AtomicBool>,
) {
    if let Err(err) = prepare_workspace(&launch) {
        let _ = tx.send(StudioEvent::SessionFinished {
            session_id: launch.id,
            success: false,
            artifacts: Vec::new(),
            error: Some(format!("workspace preparation failed: {}", err)),
        });
        return;
    }

    if let Err(err) = fs::create_dir_all(&launch.artifact_dir) {
        let _ = tx.send(StudioEvent::SessionFinished {
            session_id: launch.id,
            success: false,
            artifacts: Vec::new(),
            error: Some(format!("artifact directory setup failed: {}", err)),
        });
        return;
    }

    let attachments =
        resolve_all_attachments(&launch.execution_contract.attachments, &launch.project_dir);
    let smoothed_prompt = compose_smoothed_prompt(
        &launch.provider.to_string(),
        &launch.prompt,
        &launch.execution_contract,
        &attachments,
        &launch.scan,
        &launch.workspace_dir.display().to_string(),
        &launch.artifact_dir.display().to_string(),
        launch.prior_context.as_deref(),
    );
    let prompt_path = launch.artifact_dir.join("execution-brief.md");
    let _ = fs::write(&prompt_path, &smoothed_prompt);
    let _ = tx.send(StudioEvent::SessionOutput {
        session_id: launch.id.clone(),
        event: AgentOutputEvent::Text(format!(
            "[studio] execution brief saved to {}",
            prompt_path.display()
        )),
    });
    let log_dir = launch.project_dir.join(STUDIO_ROOT_DIR).join("logs");
    let _ = fs::create_dir_all(&log_dir);
    let started_at = SystemTime::now();

    let (agent_tx, mut agent_rx) = mpsc::unbounded_channel();
    let forward_tx = tx.clone();
    let session_id = launch.id.clone();
    tokio::spawn(async move {
        while let Some(event) = agent_rx.recv().await {
            let _ = forward_tx.send(StudioEvent::SessionOutput {
                session_id: session_id.clone(),
                event,
            });
        }
    });

    let result = agent::run_provider_session(ProviderRunOptions {
        provider: launch.provider,
        model: &launch.model,
        prompt: &smoothed_prompt,
        project_dir: &launch.workspace_dir,
        output_tx: agent_tx,
        log_dir: &log_dir,
        timeout_secs: 900,
        skip_git_repo_check: launch.workspace_mode == WorkspaceMode::Isolated,
        cancel_flag: Some(cancel_flag),
    })
    .await;

    let artifacts = discover_artifacts(&launch.workspace_dir, &launch.artifact_dir, started_at);
    let (success, error) = match result {
        Ok(outcome) => (outcome.success, None),
        Err(err) => (false, Some(err.to_string())),
    };

    let _ = tx.send(StudioEvent::SessionFinished {
        session_id: launch.id,
        success,
        artifacts,
        error,
    });
}

fn prepare_workspace(launch: &SessionLaunch) -> Result<()> {
    if !launch.prepare_workspace {
        fs::create_dir_all(&launch.workspace_dir)?;
        return Ok(());
    }

    if launch.workspace_mode == WorkspaceMode::Shared {
        return Ok(());
    }

    if launch.workspace_dir.exists() {
        fs::remove_dir_all(&launch.workspace_dir).with_context(|| {
            format!(
                "failed to remove existing workspace {}",
                launch.workspace_dir.display()
            )
        })?;
    }

    if let Some(parent) = launch.workspace_dir.parent() {
        fs::create_dir_all(parent)?;
    }

    copy_workspace_snapshot(&launch.project_dir, &launch.workspace_dir)
}

fn render(frame: &mut ratatui::Frame, state: &mut StudioState) {
    let layout = studio_layout(frame.area(), state.layout_config);

    render_header(frame, layout.header, state);
    render_scan(frame, layout.scan, state);
    render_prompt(frame, layout.prompt, state);
    render_contracts(frame, layout.contracts, state);
    render_preview(frame, layout.execution_brief, state);
    render_sessions(frame, layout.sessions, state);
    render_output(frame, layout.output, state);
    render_activity(frame, layout.activity, state);
    render_status(frame, layout.status, state);
    render_resize_handles(frame, &layout, state);
    render_editor_guide(frame, state);
    render_delete_confirmation(frame, state);
    render_attachment_manager(frame, state);
}

fn studio_layout(area: Rect, config: StudioLayoutConfig) -> StudioLayout {
    let root = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(4),
            Constraint::Min(20),
            Constraint::Length(1),
        ])
        .split(area);

    let body_area = root[1];
    let left_width = clamped_left_column_width(body_area.width, config.left_column_percent);
    let column_split_width = if body_area.width >= 3 {
        COLUMN_SPLIT_WIDTH
    } else {
        0
    };
    let right_width = body_area
        .width
        .saturating_sub(left_width)
        .saturating_sub(column_split_width)
        .max(1);

    let body = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([
            Constraint::Length(left_width),
            Constraint::Length(column_split_width),
            Constraint::Min(right_width),
        ])
        .split(body_area);

    let left_height = left_content_height(body[0]).max(1);
    let mut left_scan_height = config.left_scan_height.max(MIN_LEFT_SECTION_HEIGHT);
    let mut left_prompt_height = config.left_prompt_height.max(MIN_LEFT_SECTION_HEIGHT);
    let mut left_contracts_height = config.left_contracts_height.max(MIN_LEFT_SECTION_HEIGHT);
    let left_brief_min = MIN_LEFT_BRIEF_HEIGHT.min(left_height.saturating_sub(3));
    let left_scan_max = left_height
        .saturating_sub(left_prompt_height)
        .saturating_sub(left_contracts_height)
        .saturating_sub(left_brief_min)
        .max(MIN_LEFT_SECTION_HEIGHT);
    left_scan_height = left_scan_height.min(left_scan_max);
    let left_prompt_max = left_height
        .saturating_sub(left_scan_height)
        .saturating_sub(left_contracts_height)
        .saturating_sub(left_brief_min)
        .max(MIN_LEFT_SECTION_HEIGHT);
    left_prompt_height = left_prompt_height.min(left_prompt_max);
    let left_contracts_max = left_height
        .saturating_sub(left_scan_height)
        .saturating_sub(left_prompt_height)
        .saturating_sub(left_brief_min)
        .max(MIN_LEFT_SECTION_HEIGHT);
    left_contracts_height = left_contracts_height.min(left_contracts_max);

    let left = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(left_scan_height),
            Constraint::Length(ROW_SPLIT_HEIGHT),
            Constraint::Length(left_prompt_height),
            Constraint::Length(ROW_SPLIT_HEIGHT),
            Constraint::Length(left_contracts_height),
            Constraint::Length(ROW_SPLIT_HEIGHT),
            Constraint::Min(left_brief_min.max(1)),
        ])
        .split(body[0]);

    let right_height = right_content_height(body[2]).max(1);
    let mut right_sessions_height = config.right_sessions_height.max(MIN_RIGHT_SECTION_HEIGHT);
    let mut right_activity_height = config.right_activity_height.max(MIN_RIGHT_SECTION_HEIGHT);
    let output_min = MIN_OUTPUT_HEIGHT.min(right_height.saturating_sub(2));
    let right_sessions_max = right_height
        .saturating_sub(right_activity_height)
        .saturating_sub(output_min)
        .max(MIN_RIGHT_SECTION_HEIGHT);
    right_sessions_height = right_sessions_height.min(right_sessions_max);
    let right_activity_max = right_height
        .saturating_sub(right_sessions_height)
        .saturating_sub(output_min)
        .max(MIN_RIGHT_SECTION_HEIGHT);
    right_activity_height = right_activity_height.min(right_activity_max);

    let right = Layout::default()
        .direction(Direction::Vertical)
        .constraints([
            Constraint::Length(right_sessions_height),
            Constraint::Length(ROW_SPLIT_HEIGHT),
            Constraint::Min(output_min.max(1)),
            Constraint::Length(ROW_SPLIT_HEIGHT),
            Constraint::Length(right_activity_height),
        ])
        .split(body[2]);

    StudioLayout {
        header: root[0],
        body: body_area,
        left_body: body[0],
        right_body: body[2],
        column_split: body[1],
        left_scan_prompt_split: left[1],
        left_prompt_contracts_split: left[3],
        left_contracts_brief_split: left[5],
        right_sessions_output_split: right[1],
        right_output_activity_split: right[3],
        scan: left[0],
        prompt: left[2],
        contracts: left[4],
        execution_brief: left[6],
        sessions: right[0],
        output: right[2],
        activity: right[4],
        status: root[2],
    }
}

fn render_resize_handles(frame: &mut ratatui::Frame, layout: &StudioLayout, state: &StudioState) {
    render_resize_handle(
        frame,
        layout.column_split,
        state,
        ResizeHandle::ColumnSplit,
        '│',
    );
    render_resize_handle(
        frame,
        layout.left_scan_prompt_split,
        state,
        ResizeHandle::LeftScanPrompt,
        '─',
    );
    render_resize_handle(
        frame,
        layout.left_prompt_contracts_split,
        state,
        ResizeHandle::LeftPromptContracts,
        '─',
    );
    render_resize_handle(
        frame,
        layout.left_contracts_brief_split,
        state,
        ResizeHandle::LeftContractsBrief,
        '─',
    );
    render_resize_handle(
        frame,
        layout.right_sessions_output_split,
        state,
        ResizeHandle::RightSessionsOutput,
        '─',
    );
    render_resize_handle(
        frame,
        layout.right_output_activity_split,
        state,
        ResizeHandle::RightOutputActivity,
        '─',
    );
}

fn render_resize_handle(
    frame: &mut ratatui::Frame,
    area: Rect,
    state: &StudioState,
    handle: ResizeHandle,
    fill: char,
) {
    if area.width == 0 || area.height == 0 {
        return;
    }

    let is_active = state
        .active_resize
        .map(|drag| drag.handle == handle)
        .unwrap_or(false);
    let style = if is_active {
        Style::default()
            .fg(Color::Cyan)
            .add_modifier(Modifier::BOLD)
    } else {
        Style::default().fg(Color::DarkGray)
    };
    let row = std::iter::repeat_n(fill, area.width as usize).collect::<String>();
    let lines = (0..area.height)
        .map(|_| Line::from(Span::styled(row.clone(), style)))
        .collect::<Vec<_>>();

    frame.render_widget(Paragraph::new(lines), area);
}

fn render_header(frame: &mut ratatui::Frame, area: ratatui::layout::Rect, state: &StudioState) {
    let mut lines = Vec::new();
    lines.push(Line::from(vec![
        Span::styled(
            " STUDIO ",
            Style::default()
                .fg(Color::Black)
                .bg(Color::LightCyan)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw("  "),
        Span::styled(
            truncate_display_path(&state.project_dir, 72),
            Style::default()
                .fg(Color::White)
                .add_modifier(Modifier::BOLD),
        ),
    ]));
    lines.push(Line::from(vec![
        Span::styled(
            format!("providers={} ", state.provider_mode),
            Style::default().fg(Color::Yellow),
        ),
        Span::styled(
            format!("workspace={} ", state.workspace_mode),
            Style::default().fg(Color::Cyan),
        ),
        Span::styled(
            format!("contract={} ", state.selected_execution_contract().name),
            Style::default().fg(Color::LightMagenta),
        ),
        Span::styled(
            format!("editor={} ", editor_choice_summary(state.editor_choice)),
            Style::default().fg(Color::LightCyan),
        ),
        Span::styled(
            format!(
                "claude={} ({}) ",
                display_model_name(&state.claude_model),
                header_readiness_label(&state.claude_readiness)
            ),
            Style::default().fg(provider_color(ModelProvider::Claude)),
        ),
        Span::styled(
            format!(
                "codex={} ({})",
                display_model_name(&state.codex_model),
                header_readiness_label(&state.codex_readiness)
            ),
            Style::default().fg(provider_color(ModelProvider::Codex)),
        ),
    ]));
    lines.push(Line::from(Span::styled(
        "keys: e edit  c cycle contract  v cycle editor  a add  d delete  s start  f follow-up  tab/shift-tab focus  click pane  drag split bars resize  p provider  w workspace  r rescan  j/k session  ↑/↓ contracts|output  enter edit contract  q/ctrl-c quit",
        Style::default().fg(Color::DarkGray),
    )));

    let header = Paragraph::new(lines).block(
        Block::default()
            .borders(Borders::BOTTOM)
            .border_style(Style::default().fg(Color::DarkGray)),
    );
    frame.render_widget(header, area);
}

fn render_scan(frame: &mut ratatui::Frame, area: ratatui::layout::Rect, state: &StudioState) {
    let items: Vec<ListItem> = state
        .scan
        .summary_lines()
        .into_iter()
        .map(|line| ListItem::new(Span::styled(line, Style::default().fg(Color::White))))
        .collect();

    let list = List::new(items).block(
        Block::default()
            .title(Span::styled(
                " Project Scan ",
                pane_title_style(state, FocusedPane::Scan, Color::LightYellow),
            ))
            .borders(Borders::ALL)
            .border_style(pane_border_style(
                state,
                FocusedPane::Scan,
                Color::LightYellow,
            ))
            .border_type(pane_border_type(state, FocusedPane::Scan)),
    );
    frame.render_widget(list, area);
}

fn render_prompt(frame: &mut ratatui::Frame, area: ratatui::layout::Rect, state: &StudioState) {
    let prompt_text = if state.is_editing_prompt {
        format!("{}█", state.prompt)
    } else {
        state.prompt.clone()
    };

    let title = if state.is_editing_prompt {
        " Prompt (editing) "
    } else {
        " Prompt "
    };

    let paragraph = Paragraph::new(prompt_text)
        .wrap(Wrap { trim: false })
        .block(
            Block::default()
                .title(Span::styled(
                    title,
                    pane_title_style(state, FocusedPane::Prompt, Color::LightGreen),
                ))
                .borders(Borders::ALL)
                .border_style(if state.is_editing_prompt {
                    Style::default()
                        .fg(Color::Green)
                        .add_modifier(Modifier::BOLD)
                } else {
                    pane_border_style(state, FocusedPane::Prompt, Color::LightGreen)
                })
                .border_type(if state.is_editing_prompt {
                    BorderType::Thick
                } else {
                    pane_border_type(state, FocusedPane::Prompt)
                }),
        );
    frame.render_widget(paragraph, area);
}

fn render_contracts(frame: &mut ratatui::Frame, area: ratatui::layout::Rect, state: &StudioState) {
    let selected = state.selected_execution_contract();
    let mut lines = vec![Line::from(Span::styled(
        format!("selected: {}", execution_contract_list_label(selected)),
        Style::default()
            .fg(Color::White)
            .add_modifier(Modifier::BOLD),
    ))];

    for (idx, contract) in state.execution_contracts.iter().enumerate() {
        let prefix = if idx == state.selected_execution_contract {
            ">"
        } else {
            " "
        };
        let contract_label = execution_contract_list_label(contract);
        lines.push(Line::from(Span::styled(
            format!(
                "{} {}",
                prefix,
                truncate_str(&contract_label, area.width.saturating_sub(6) as usize)
            ),
            if idx == state.selected_execution_contract {
                Style::default()
                    .fg(Color::White)
                    .add_modifier(Modifier::BOLD)
            } else {
                Style::default().fg(Color::Gray)
            },
        )));
    }

    lines.push(Line::from(Span::styled(
        "vars: {{workspace_dir}} {{artifact_dir}} {{provider_label}}",
        Style::default().fg(Color::DarkGray),
    )));
    lines.push(Line::from(Span::styled(
        format!(
            "editor: {} (press v to change)",
            editor_choice_summary(state.editor_choice)
        ),
        Style::default().fg(Color::LightCyan),
    )));
    lines.push(Line::from(Span::styled(
        "actions: enter edit contract  t manage attachments",
        Style::default().fg(Color::DarkGray),
    )));

    let paragraph = Paragraph::new(lines).wrap(Wrap { trim: false }).block(
        Block::default()
            .title(Span::styled(
                " Execution Contracts ",
                pane_title_style(state, FocusedPane::Contracts, Color::LightMagenta),
            ))
            .borders(Borders::ALL)
            .border_style(pane_border_style(
                state,
                FocusedPane::Contracts,
                Color::LightMagenta,
            ))
            .border_type(pane_border_type(state, FocusedPane::Contracts)),
    );
    frame.render_widget(paragraph, area);
}

fn render_preview(
    frame: &mut ratatui::Frame,
    area: ratatui::layout::Rect,
    state: &mut StudioState,
) {
    let preview = state.preview_prompt();
    let wrapped = wrap_text_lines(&preview, area.width.saturating_sub(2) as usize);
    let max_lines = area.height.saturating_sub(2) as usize;
    let max_scroll = wrapped.len().saturating_sub(max_lines);
    let start = state.preview_scroll.min(max_scroll);
    let end = (start + max_lines).min(wrapped.len());
    let items: Vec<ListItem> = wrapped[start..end]
        .iter()
        .cloned()
        .map(|line| ListItem::new(Span::styled(line, Style::default().fg(Color::Gray))))
        .collect();

    let list = List::new(items).block(
        Block::default()
            .title(Span::styled(
                " Execution Brief ",
                pane_title_style(state, FocusedPane::ExecutionBrief, Color::LightMagenta),
            ))
            .borders(Borders::ALL)
            .border_style(pane_border_style(
                state,
                FocusedPane::ExecutionBrief,
                Color::LightMagenta,
            ))
            .border_type(pane_border_type(state, FocusedPane::ExecutionBrief)),
    );
    frame.render_widget(list, area);
}

fn render_sessions(frame: &mut ratatui::Frame, area: ratatui::layout::Rect, state: &StudioState) {
    let items: Vec<ListItem> = if state.sessions.is_empty() {
        vec![ListItem::new(Span::styled(
            "No sessions yet. Press `s` to launch.",
            Style::default().fg(Color::DarkGray),
        ))]
    } else {
        state
            .sessions
            .iter()
            .enumerate()
            .map(|(idx, session)| {
                let prefix = if idx == state.selected_session {
                    ">"
                } else {
                    " "
                };
                let running_marker = if session.status == SessionStatus::Running {
                    studio_spinner(state.tick_count)
                } else {
                    ' '
                };
                let elapsed = Utc::now()
                    .signed_duration_since(session.started_at)
                    .num_seconds()
                    .max(0);
                let line = format!(
                    "{}{} {} {} {}ev {}s",
                    prefix,
                    running_marker,
                    session.provider,
                    session.status.label(),
                    session.event_count,
                    elapsed
                );
                ListItem::new(Span::styled(
                    line,
                    Style::default()
                        .fg(if idx == state.selected_session {
                            Color::White
                        } else {
                            session.status.color()
                        })
                        .add_modifier(if idx == state.selected_session {
                            Modifier::BOLD
                        } else {
                            Modifier::empty()
                        }),
                ))
            })
            .collect()
    };

    let list = List::new(items).block(
        Block::default()
            .title(Span::styled(
                " Sessions ",
                pane_title_style(state, FocusedPane::Sessions, Color::LightBlue),
            ))
            .borders(Borders::ALL)
            .border_style(pane_border_style(
                state,
                FocusedPane::Sessions,
                Color::LightBlue,
            ))
            .border_type(pane_border_type(state, FocusedPane::Sessions)),
    );
    frame.render_widget(list, area);
}

fn render_output(frame: &mut ratatui::Frame, area: ratatui::layout::Rect, state: &StudioState) {
    let width = area.width.saturating_sub(2) as usize;
    let mut lines = Vec::new();
    if let Some(session) = state.selected_session() {
        if session.output.is_empty() {
            lines.push(ListItem::new(Span::styled(
                "Waiting for output...",
                Style::default().fg(Color::DarkGray),
            )));
        } else {
            let wrapped: Vec<(String, Style)> = session
                .output
                .iter()
                .flat_map(|line| {
                    let style = output_style(line);
                    wrap_text_lines(line, width)
                        .into_iter()
                        .map(move |chunk| (chunk, style))
                })
                .collect();
            let max_lines = area.height.saturating_sub(2) as usize;
            let total = wrapped.len();
            let start = total.saturating_sub(max_lines + state.output_scroll);
            let end = total.saturating_sub(state.output_scroll);
            for (text, style) in wrapped[start..end].iter() {
                lines.push(ListItem::new(Span::styled(text.clone(), *style)));
            }
        }
    } else {
        lines.push(ListItem::new(Span::styled(
            "Select or start a session to see output.",
            Style::default().fg(Color::DarkGray),
        )));
    }

    let title = if let Some(session) = state.selected_session() {
        format!(" Output [{}] ", session.provider)
    } else {
        " Output ".to_string()
    };

    let list = List::new(lines).block(
        Block::default()
            .title(Span::styled(
                title,
                pane_title_style(state, FocusedPane::Output, Color::LightCyan),
            ))
            .borders(Borders::ALL)
            .border_style(pane_border_style(
                state,
                FocusedPane::Output,
                Color::LightCyan,
            ))
            .border_type(pane_border_type(state, FocusedPane::Output)),
    );
    frame.render_widget(list, area);
}

fn render_activity(frame: &mut ratatui::Frame, area: ratatui::layout::Rect, state: &StudioState) {
    let mut lines: Vec<ListItem> = Vec::new();

    lines.push(ListItem::new(Span::styled(
        format!("Claude: {}", readiness_summary(&state.claude_readiness)),
        Style::default().fg(provider_color(ModelProvider::Claude)),
    )));
    lines.push(ListItem::new(Span::styled(
        format!("Codex: {}", readiness_summary(&state.codex_readiness)),
        Style::default().fg(provider_color(ModelProvider::Codex)),
    )));

    if let Some(session) = state.selected_session() {
        lines.push(ListItem::new(Span::styled(
            format!("contract: {}", state.selected_execution_contract().name),
            Style::default().fg(Color::DarkGray),
        )));
        lines.push(ListItem::new(Span::styled(
            format!(
                "workspace: {}",
                truncate_display_path(&session.workspace_dir, 72)
            ),
            Style::default().fg(Color::DarkGray),
        )));
        if let Some(prompt_path) = &session.prompt_path {
            lines.push(ListItem::new(Span::styled(
                format!("brief: {}", truncate_display_path(prompt_path, 72)),
                Style::default().fg(Color::DarkGray),
            )));
        }
        lines.push(ListItem::new(Span::styled(
            format!(
                "artifacts: {}",
                truncate_display_path(&session.artifact_dir, 72)
            ),
            Style::default().fg(Color::DarkGray),
        )));
        lines.push(ListItem::new(Span::styled(
            format!("started: {}", session.started_at.format("%H:%M:%S UTC")),
            Style::default().fg(Color::DarkGray),
        )));
        lines.push(ListItem::new(Span::styled(
            format!(
                "activity: {} events{}",
                session.event_count,
                session
                    .last_event_at
                    .map(|ts| format!("; last {}", ts.format("%H:%M:%S")))
                    .unwrap_or_default()
            ),
            Style::default().fg(Color::DarkGray),
        )));

        if let Some(error) = &session.error {
            lines.push(ListItem::new(Span::styled(
                format!("error: {}", truncate_str(error, 80)),
                Style::default().fg(Color::Red),
            )));
        }

        for artifact in session.artifacts.iter().take(4) {
            lines.push(ListItem::new(Span::styled(
                format!("open: {}", truncate_display_path(artifact, 72)),
                Style::default().fg(Color::Green),
            )));
        }
    }

    for (ts, message) in state.logs.iter().rev().take(4).rev() {
        lines.push(ListItem::new(Line::from(vec![
            Span::styled(
                format!("{} ", ts.format("%H:%M:%S")),
                Style::default().fg(Color::DarkGray),
            ),
            Span::styled(message.clone(), Style::default().fg(Color::Gray)),
        ])));
    }

    let list = List::new(lines).block(
        Block::default()
            .title(Span::styled(
                " Artifacts + Log ",
                pane_title_style(state, FocusedPane::Activity, Color::LightGreen),
            ))
            .borders(Borders::ALL)
            .border_style(pane_border_style(
                state,
                FocusedPane::Activity,
                Color::LightGreen,
            ))
            .border_type(pane_border_type(state, FocusedPane::Activity)),
    );
    frame.render_widget(list, area);
}

fn render_status(frame: &mut ratatui::Frame, area: ratatui::layout::Rect, state: &StudioState) {
    let status = if state.is_editing_prompt {
        "editing prompt"
    } else if state.has_running_sessions() {
        "sessions running"
    } else {
        "ready"
    };
    let text = format!(
        " {} | focus={} | prompt={} chars | sessions={} ",
        status,
        state.focused_pane.label(),
        state.prompt.len(),
        state.sessions.len()
    );
    let paragraph = Paragraph::new(text).style(Style::default().fg(Color::Black).bg(Color::White));
    frame.render_widget(paragraph, area);
}

fn render_editor_guide(frame: &mut ratatui::Frame, state: &StudioState) {
    let Some(guide) = &state.editor_guide else {
        return;
    };

    let editor_command = resolve_editor_command(state.editor_choice);
    let editor_name = editor_command_name(&editor_command);
    let action_label = pending_action_label(&guide.action);
    let area = centered_rect(68, 14, frame.area());
    let mut lines = vec![
        Line::from(Span::styled(
            format!("Editor: {}", editor_choice_summary(state.editor_choice)),
            Style::default()
                .fg(Color::White)
                .add_modifier(Modifier::BOLD),
        )),
        Line::from(Span::styled(
            format!("Target: {}", action_label),
            Style::default().fg(Color::LightCyan),
        )),
        Line::from(Span::styled(
            "Studio will temporarily leave the TUI while the editor is open.",
            Style::default().fg(Color::Gray),
        )),
        Line::from(""),
    ];

    for tip in editor_help_lines(&editor_name) {
        lines.push(Line::from(Span::styled(
            tip,
            Style::default().fg(Color::White),
        )));
    }

    lines.push(Line::from(""));
    lines.push(Line::from(Span::styled(
        "V cycle editor  Enter open editor  Esc cancel",
        Style::default().fg(Color::LightGreen),
    )));

    frame.render_widget(Clear, area);
    let paragraph = Paragraph::new(lines).wrap(Wrap { trim: false }).block(
        Block::default()
            .title(Span::styled(
                " Open Editor ",
                Style::default()
                    .fg(Color::LightCyan)
                    .add_modifier(Modifier::BOLD),
            ))
            .borders(Borders::ALL)
            .border_type(BorderType::Thick)
            .border_style(Style::default().fg(Color::LightCyan)),
    );
    frame.render_widget(paragraph, area);
}

fn render_delete_confirmation(frame: &mut ratatui::Frame, state: &StudioState) {
    let Some(confirm) = &state.delete_confirmation else {
        return;
    };

    let area = centered_rect(60, 8, frame.area());
    let lines = vec![
        Line::from(Span::styled(
            format!("Delete contract: {}", confirm.contract_name),
            Style::default()
                .fg(Color::White)
                .add_modifier(Modifier::BOLD),
        )),
        Line::from(""),
        Line::from(Span::styled(
            "Are you sure? Y/N",
            Style::default()
                .fg(Color::LightRed)
                .add_modifier(Modifier::BOLD),
        )),
        Line::from(""),
        Line::from(Span::styled(
            "Y delete permanently (moved to .trash)  N cancel",
            Style::default().fg(Color::Gray),
        )),
    ];

    frame.render_widget(Clear, area);
    let paragraph = Paragraph::new(lines).wrap(Wrap { trim: false }).block(
        Block::default()
            .title(Span::styled(
                " Confirm Delete ",
                Style::default()
                    .fg(Color::LightRed)
                    .add_modifier(Modifier::BOLD),
            ))
            .borders(Borders::ALL)
            .border_type(BorderType::Thick)
            .border_style(Style::default().fg(Color::LightRed)),
    );
    frame.render_widget(paragraph, area);
}

fn render_attachment_manager(frame: &mut ratatui::Frame, state: &StudioState) {
    let Some(manager) = &state.attachment_manager else {
        return;
    };

    let contract = state.selected_execution_contract();
    let area = centered_rect(76, 18, frame.area());
    let mut lines = vec![
        Line::from(Span::styled(
            format!("Contract: {}", contract.name),
            Style::default()
                .fg(Color::White)
                .add_modifier(Modifier::BOLD),
        )),
        Line::from(Span::styled(
            format!("{} attachment(s)", contract.attachments.len()),
            Style::default().fg(Color::LightCyan),
        )),
        Line::from(""),
    ];

    if contract.attachments.is_empty() {
        lines.push(Line::from(Span::styled(
            "No attachments yet. Press `a` to add file(s) or folder(s).",
            Style::default().fg(Color::Gray),
        )));
    } else {
        for (idx, attachment) in contract.attachments.iter().enumerate() {
            let prefix = if idx == manager.selected_attachment {
                ">"
            } else {
                " "
            };
            let marked = if manager.marked_attachments.contains(&idx) {
                "[x]"
            } else {
                "[ ]"
            };
            let style = if idx == manager.selected_attachment {
                Style::default()
                    .fg(Color::White)
                    .add_modifier(Modifier::BOLD)
            } else {
                Style::default().fg(Color::Gray)
            };
            let mode_style = Style::default().fg(Color::LightMagenta);
            let path_width = area.width.saturating_sub(20) as usize;
            lines.push(Line::from(vec![
                Span::styled(format!("{} {} ", prefix, marked), style),
                Span::styled(truncate_str(&attachment.path, path_width), style),
                Span::styled(
                    format!(" ({})", attachment_mode_summary(attachment.mode)),
                    mode_style,
                ),
            ]));
        }

        let selected = &contract.attachments[manager
            .selected_attachment
            .min(contract.attachments.len().saturating_sub(1))];
        lines.push(Line::from(""));
        lines.push(Line::from(Span::styled(
            format!("selected: {}", selected.path),
            Style::default().fg(Color::LightCyan),
        )));
        lines.push(Line::from(Span::styled(
            format!("type: {}", attachment_mode_summary(selected.mode)),
            Style::default().fg(Color::Gray),
        )));
        if let Some(label) = &selected.label {
            lines.push(Line::from(Span::styled(
                format!("label: {}", label),
                Style::default().fg(Color::Gray),
            )));
        }
    }

    lines.push(Line::from(""));
    lines.push(Line::from(Span::styled(
        "a add  d delete marked, else selected  space mark  ↑/↓ move  enter/esc close",
        Style::default().fg(Color::DarkGray),
    )));

    frame.render_widget(Clear, area);
    let paragraph = Paragraph::new(lines).wrap(Wrap { trim: false }).block(
        Block::default()
            .title(Span::styled(
                " Manage Attachments ",
                Style::default()
                    .fg(Color::LightMagenta)
                    .add_modifier(Modifier::BOLD),
            ))
            .borders(Borders::ALL)
            .border_type(BorderType::Thick)
            .border_style(Style::default().fg(Color::LightMagenta)),
    );
    frame.render_widget(paragraph, area);
}

fn scan_project(project_dir: &Path) -> Result<ProjectScan> {
    let mut top_level = Vec::new();
    for entry in fs::read_dir(project_dir)? {
        let entry = entry?;
        let name = entry.file_name().to_string_lossy().to_string();
        if should_skip_snapshot_path(Path::new(&name)) {
            continue;
        }
        top_level.push(name);
    }
    top_level.sort();
    top_level.truncate(12);

    let mut stack_signals = Vec::new();
    let stack_checks = [
        ("Cargo.toml", "Rust"),
        ("package.json", "Node/TS"),
        ("pyproject.toml", "Python"),
        ("requirements.txt", "Python"),
        ("docker-compose.yml", "Docker Compose"),
        ("Dockerfile", "Docker"),
    ];
    for (file, label) in stack_checks {
        if project_dir.join(file).exists() {
            stack_signals.push(label.to_string());
        }
    }

    if stack_signals.is_empty() {
        stack_signals.push("unknown".to_string());
    }

    let data_candidates = collect_matching_paths(
        project_dir,
        3,
        10,
        &[
            "json", "jsonl", "csv", "tsv", "sqlite", "db", "parquet", "md", "yaml", "yml",
        ],
    )?;
    let output_targets = collect_output_targets(project_dir)?;

    Ok(ProjectScan {
        generated_at: Utc::now(),
        top_level,
        stack_signals,
        data_candidates,
        output_targets,
    })
}

fn collect_matching_paths(
    root: &Path,
    max_depth: usize,
    limit: usize,
    extensions: &[&str],
) -> Result<Vec<String>> {
    let mut results = Vec::new();
    collect_matching_paths_inner(root, root, 0, max_depth, limit, extensions, &mut results)?;
    Ok(results)
}

fn collect_matching_paths_inner(
    root: &Path,
    current: &Path,
    depth: usize,
    max_depth: usize,
    limit: usize,
    extensions: &[&str],
    results: &mut Vec<String>,
) -> Result<()> {
    if depth > max_depth || results.len() >= limit {
        return Ok(());
    }

    let mut entries: Vec<_> = fs::read_dir(current)?
        .filter_map(|entry| entry.ok())
        .collect();
    entries.sort_by_key(|entry| entry.file_name());

    for entry in entries {
        if results.len() >= limit {
            break;
        }
        let path = entry.path();
        let rel = path
            .strip_prefix(root)
            .unwrap_or(&path)
            .to_string_lossy()
            .to_string();
        if should_skip_snapshot_path(Path::new(&rel)) {
            continue;
        }

        let file_type = entry.file_type()?;
        if file_type.is_dir() {
            collect_matching_paths_inner(
                root,
                &path,
                depth + 1,
                max_depth,
                limit,
                extensions,
                results,
            )?;
            continue;
        }

        if let Some(ext) = path.extension().and_then(|ext| ext.to_str()) {
            if extensions
                .iter()
                .any(|wanted| ext.eq_ignore_ascii_case(wanted))
            {
                results.push(rel);
            }
        }
    }

    Ok(())
}

fn collect_output_targets(root: &Path) -> Result<Vec<String>> {
    let candidates = ["public", "dist", "apps", "tools", "reports", "dashboard"];
    let mut found = Vec::new();
    for name in candidates {
        if root.join(name).exists() {
            found.push(name.to_string());
        }
    }

    if found.is_empty() {
        found = collect_matching_paths(root, 2, 8, &["html", "htm", "tsx", "jsx"])?;
    }

    Ok(found)
}

#[allow(clippy::too_many_arguments)]
fn compose_smoothed_prompt(
    provider_label: &str,
    raw_prompt: &str,
    execution_contract: &ExecutionContract,
    attachments: &[ResolvedAttachment],
    scan: &ProjectScan,
    workspace_dir: &str,
    artifact_dir: &str,
    prior_context: Option<&str>,
) -> String {
    let prior_context_block = prior_context
        .filter(|text| !text.trim().is_empty())
        .map(|text| {
            format!(
                "\n\nPrevious session context:\n--- BEGIN PRIOR OUTPUT ---\n{}\n--- END PRIOR OUTPUT ---",
                text
            )
        })
        .unwrap_or_default();
    let rendered_contract = render_execution_contract_body(
        &execution_contract.body,
        provider_label,
        workspace_dir,
        artifact_dir,
    );
    let attachments_block = format_attachments_block(attachments);
    format!(
        r#"You are running inside Foundry Studio through the {provider_label} CLI.

User objective:
{raw_prompt}

Execution contract: {contract_name}
--- BEGIN EXECUTION CONTRACT ---
{rendered_contract}
--- END EXECUTION CONTRACT ---{attachments_block}

Project scan:
- stack signals: {stack}
- top-level entries: {top}
- likely data/report inputs: {data}
- likely output areas: {outputs}
- Keep changes scoped to the request and leave unrelated files untouched.{prior_context_block}"#,
        contract_name = execution_contract.name,
        stack = join_or_none(&scan.stack_signals, ", "),
        top = join_or_none(&scan.top_level, ", "),
        data = join_or_none(&scan.data_candidates, ", "),
        outputs = join_or_none(&scan.output_targets, ", "),
    )
}

fn render_execution_contract_body(
    body: &str,
    provider_label: &str,
    workspace_dir: &str,
    artifact_dir: &str,
) -> String {
    body.replace("{{provider_label}}", provider_label)
        .replace("{{workspace_dir}}", workspace_dir)
        .replace("{{artifact_dir}}", artifact_dir)
}

fn attachment_requested_display_path(spec: &AttachmentSpec) -> String {
    let trimmed = spec.path.trim().replace('\\', "/");
    trimmed
        .trim_end_matches('/')
        .trim_end_matches('\\')
        .to_string()
}

fn attachment_path_has_parent_reference(path: &Path) -> bool {
    path.components()
        .any(|component| matches!(component, Component::ParentDir))
}

fn normalize_relative_display_path(path: &Path) -> String {
    let mut parts = Vec::new();
    for component in path.components() {
        match component {
            Component::CurDir => {}
            Component::Normal(value) => parts.push(value.to_string_lossy().to_string()),
            Component::ParentDir => {
                if !parts.is_empty() {
                    parts.pop();
                } else {
                    parts.push("..".to_string());
                }
            }
            Component::RootDir | Component::Prefix(_) => {}
        }
    }

    if parts.is_empty() {
        ".".to_string()
    } else {
        parts.join("/")
    }
}

fn attachment_display_label(spec: &AttachmentSpec, display_path: &str) -> String {
    let custom_label = spec
        .label
        .as_deref()
        .map(str::trim)
        .filter(|label| !label.is_empty());
    match custom_label {
        Some(label) if label != display_path => format!("{} [{}]", label, display_path),
        Some(label) => label.to_string(),
        None => display_path.to_string(),
    }
}

fn attachment_mode_label(mode: &AttachmentMode) -> &'static str {
    match mode {
        AttachmentMode::InlineFile => "inline file",
        AttachmentMode::DirectoryTree => "directory tree",
    }
}

fn attachment_error(
    spec: &AttachmentSpec,
    display_path: &str,
    message: String,
) -> ResolvedAttachment {
    ResolvedAttachment {
        spec: spec.clone(),
        label: attachment_display_label(spec, display_path),
        content: format!("[ATTACHMENT ERROR: {}]", message),
        truncated: false,
        error: Some(message),
    }
}

fn truncate_with_notice(text: &str, max_chars: usize, notice: &str) -> String {
    if text.chars().count() <= max_chars {
        return text.to_string();
    }
    if max_chars == 0 {
        return String::new();
    }

    let notice_chars = notice.chars().count();
    if max_chars <= notice_chars {
        return notice.chars().take(max_chars).collect();
    }

    let prefix_chars = max_chars - notice_chars;
    let cutoff = text
        .char_indices()
        .nth(prefix_chars)
        .map(|(idx, _)| idx)
        .unwrap_or(text.len());
    format!("{}{}", &text[..cutoff], notice)
}

fn human_readable_bytes(size: u64) -> String {
    if size >= 1024 * 1024 {
        format!("{:.1} MB", size as f64 / (1024.0 * 1024.0))
    } else if size >= 1024 {
        format!("{:.1} KB", size as f64 / 1024.0)
    } else {
        format!("{} B", size)
    }
}

fn directory_has_children(path: &Path) -> bool {
    fs::read_dir(path)
        .ok()
        .and_then(|mut entries| entries.next())
        .is_some()
}

fn collect_directory_tree_lines(
    current_abs: &Path,
    current_rel: &Path,
    depth: usize,
    lines: &mut Vec<String>,
    entry_count: &mut usize,
    truncated: &mut bool,
) -> Result<()> {
    let mut entries: Vec<_> = fs::read_dir(current_abs)?
        .filter_map(|entry| entry.ok())
        .collect();
    entries.sort_by_key(|entry| entry.file_name());

    for entry in entries {
        if *entry_count >= MAX_TREE_FILES {
            lines.push(format!(
                "{}[truncated: max {} entries reached]",
                "  ".repeat(depth + 1),
                MAX_TREE_FILES
            ));
            *truncated = true;
            break;
        }

        let name = entry.file_name().to_string_lossy().to_string();
        let child_rel = current_rel.join(&name);
        let indent = "  ".repeat(depth + 1);
        *entry_count += 1;

        if should_skip_snapshot_path(&child_rel) {
            lines.push(format!("{}{} [snapshot-excluded]", indent, name));
            continue;
        }

        let file_type = match entry.file_type() {
            Ok(file_type) => file_type,
            Err(err) => {
                lines.push(format!("{}{} [error: {}]", indent, name, err));
                continue;
            }
        };

        if file_type.is_symlink() {
            lines.push(format!("{}{} [symlink omitted]", indent, name));
            continue;
        }

        if file_type.is_file() {
            let size = entry
                .metadata()
                .map(|metadata| metadata.len())
                .unwrap_or_default();
            lines.push(format!(
                "{}{} ({})",
                indent,
                name,
                human_readable_bytes(size)
            ));
            continue;
        }

        if file_type.is_dir() {
            lines.push(format!("{}{}/", indent, name));
            if depth + 1 >= MAX_TREE_DEPTH {
                if directory_has_children(&entry.path()) {
                    lines.push(format!(
                        "{}  [truncated: max depth {} reached]",
                        indent, MAX_TREE_DEPTH
                    ));
                    *truncated = true;
                }
                continue;
            }
            collect_directory_tree_lines(
                &entry.path(),
                &child_rel,
                depth + 1,
                lines,
                entry_count,
                truncated,
            )?;
            continue;
        }

        lines.push(format!("{}{}", indent, name));
    }

    Ok(())
}

fn render_directory_tree(root_abs: &Path, root_rel: &Path) -> Result<(String, bool)> {
    let mut lines = vec![format!("{}/", normalize_relative_display_path(root_rel))];
    let mut entry_count = 0usize;
    let mut truncated = false;

    if should_skip_snapshot_path(root_rel) {
        lines.push("[warning] path is excluded from isolated workspace snapshots".to_string());
    }

    collect_directory_tree_lines(
        root_abs,
        root_rel,
        0,
        &mut lines,
        &mut entry_count,
        &mut truncated,
    )?;

    Ok((lines.join("\n"), truncated))
}

fn resolve_attachment_with_root(
    spec: &AttachmentSpec,
    project_dir: &Path,
    canonical_project: &Path,
) -> ResolvedAttachment {
    let requested_path = attachment_requested_display_path(spec);
    if requested_path.is_empty() {
        return attachment_error(
            spec,
            "<empty attachment path>",
            "attachment path is empty".to_string(),
        );
    }

    let requested = Path::new(spec.path.trim());
    if requested.is_absolute() {
        return attachment_error(
            spec,
            &requested_path,
            format!(
                "absolute attachment paths are not supported: {}",
                requested_path
            ),
        );
    }
    if attachment_path_has_parent_reference(requested) {
        return attachment_error(
            spec,
            &requested_path,
            format!(
                "attachment path cannot contain '..' components: {}",
                requested_path
            ),
        );
    }

    let joined = project_dir.join(requested);
    let canonical_target = match fs::canonicalize(&joined) {
        Ok(path) => path,
        Err(err) if err.kind() == std::io::ErrorKind::NotFound => {
            return attachment_error(
                spec,
                &requested_path,
                format!("attachment path does not exist: {}", requested_path),
            );
        }
        Err(err) => {
            return attachment_error(
                spec,
                &requested_path,
                format!("failed to resolve attachment {}: {}", requested_path, err),
            );
        }
    };

    let relative = match canonical_target.strip_prefix(canonical_project) {
        Ok(path) => path.to_path_buf(),
        Err(_) => {
            return attachment_error(
                spec,
                &requested_path,
                format!(
                    "attachment path escapes the project root: {}",
                    requested_path
                ),
            );
        }
    };
    let display_path = normalize_relative_display_path(&relative);

    match spec.mode {
        AttachmentMode::InlineFile => {
            if !canonical_target.is_file() {
                return attachment_error(
                    spec,
                    &display_path,
                    format!("attachment is not a file: {}", display_path),
                );
            }

            let bytes = match fs::read(&canonical_target) {
                Ok(bytes) => bytes,
                Err(err) => {
                    return attachment_error(
                        spec,
                        &display_path,
                        format!("failed to read attachment {}: {}", display_path, err),
                    );
                }
            };

            let truncated = bytes.len() > MAX_INLINE_FILE_BYTES;
            let content = if truncated {
                format!(
                    "{}\n[truncated: file exceeds {} bytes]",
                    String::from_utf8_lossy(&bytes[..MAX_INLINE_FILE_BYTES]),
                    MAX_INLINE_FILE_BYTES
                )
            } else {
                String::from_utf8_lossy(&bytes).to_string()
            };

            ResolvedAttachment {
                spec: spec.clone(),
                label: attachment_display_label(spec, &display_path),
                content,
                truncated,
                error: None,
            }
        }
        AttachmentMode::DirectoryTree => {
            if !canonical_target.is_dir() {
                return attachment_error(
                    spec,
                    &display_path,
                    format!("attachment is not a directory: {}", display_path),
                );
            }

            match render_directory_tree(&canonical_target, &relative) {
                Ok((content, truncated)) => ResolvedAttachment {
                    spec: spec.clone(),
                    label: attachment_display_label(spec, &display_path),
                    content,
                    truncated,
                    error: None,
                },
                Err(err) => attachment_error(
                    spec,
                    &display_path,
                    format!("failed to list attachment {}: {}", display_path, err),
                ),
            }
        }
    }
}

#[allow(dead_code)]
fn resolve_attachment(spec: &AttachmentSpec, project_dir: &Path) -> ResolvedAttachment {
    let requested_path = attachment_requested_display_path(spec);
    let canonical_project = match fs::canonicalize(project_dir) {
        Ok(path) => path,
        Err(err) => {
            return attachment_error(
                spec,
                requested_path.as_str(),
                format!(
                    "failed to resolve project root {}: {}",
                    project_dir.display(),
                    err
                ),
            );
        }
    };

    resolve_attachment_with_root(spec, project_dir, &canonical_project)
}

fn resolve_all_attachments(
    specs: &[AttachmentSpec],
    project_dir: &Path,
) -> Vec<ResolvedAttachment> {
    if specs.is_empty() {
        return Vec::new();
    }

    let canonical_project = match fs::canonicalize(project_dir) {
        Ok(path) => path,
        Err(err) => {
            return specs
                .iter()
                .map(|spec| {
                    attachment_error(
                        spec,
                        attachment_requested_display_path(spec).as_str(),
                        format!(
                            "failed to resolve project root {}: {}",
                            project_dir.display(),
                            err
                        ),
                    )
                })
                .collect();
        }
    };

    let mut remaining_chars = MAX_TOTAL_ATTACHMENT_CHARS;
    let mut resolved = Vec::with_capacity(specs.len());

    for spec in specs {
        let mut attachment = resolve_attachment_with_root(spec, project_dir, &canonical_project);
        let content_chars = attachment.content.chars().count();
        if content_chars > remaining_chars {
            attachment.content = truncate_with_notice(
                &attachment.content,
                remaining_chars,
                "\n[truncated: total attachment size budget reached]",
            );
            attachment.truncated = true;
        }
        remaining_chars = remaining_chars.saturating_sub(attachment.content.chars().count());
        resolved.push(attachment);
    }

    resolved
}

fn format_attachments_block(resolved: &[ResolvedAttachment]) -> String {
    if resolved.is_empty() {
        return String::new();
    }

    let mut blocks = Vec::with_capacity(resolved.len() + 1);
    blocks.push("Attached context:".to_string());

    for attachment in resolved {
        let line_count = if attachment.content.is_empty() {
            0
        } else {
            attachment.content.lines().count()
        };
        let mut meta = vec![
            attachment_mode_label(&attachment.spec.mode).to_string(),
            format!(
                "{} {}",
                line_count,
                if line_count == 1 { "line" } else { "lines" }
            ),
        ];
        if attachment.error.is_some() {
            meta.push("error".to_string());
        } else if attachment.truncated {
            meta.push("truncated".to_string());
        }
        blocks.push(format!(
            "--- BEGIN ATTACHMENT: {} ({}) ---\n{}\n--- END ATTACHMENT: {} ---",
            attachment.label,
            meta.join(", "),
            attachment.content,
            attachment.label
        ));
    }

    format!("\n\n{}", blocks.join("\n\n"))
}

fn resolve_system_editor_command() -> String {
    std::env::var("VISUAL")
        .ok()
        .filter(|value| !value.trim().is_empty())
        .or_else(|| {
            std::env::var("EDITOR")
                .ok()
                .filter(|value| !value.trim().is_empty())
        })
        .unwrap_or_else(|| "vi".to_string())
}

fn resolve_editor_command(choice: EditorChoice) -> String {
    match choice {
        EditorChoice::System => resolve_system_editor_command(),
        EditorChoice::Vi => "vi".to_string(),
        EditorChoice::Nano => "nano".to_string(),
        EditorChoice::CodeWait => "code --wait".to_string(),
    }
}

fn editor_choice_summary(choice: EditorChoice) -> String {
    match choice {
        EditorChoice::System => format!("system -> {}", resolve_editor_command(choice)),
        _ => resolve_editor_command(choice),
    }
}

fn editor_command_name(editor_command: &str) -> String {
    let first = editor_command
        .split_whitespace()
        .next()
        .unwrap_or(editor_command);
    Path::new(first)
        .file_name()
        .and_then(|value| value.to_str())
        .unwrap_or(first)
        .to_string()
}

fn editor_help_lines(editor_name: &str) -> Vec<&'static str> {
    match editor_name {
        "vi" | "vim" | "nvim" => vec![
            "Press `i` to enter insert mode.",
            "Press `Esc`, then type `:wq` and press Enter to save and exit.",
            "Press `Esc`, then type `:q!` and press Enter to discard changes.",
        ],
        "nano" => vec![
            "Edit directly in the buffer.",
            "Press `Ctrl+O`, then Enter to save.",
            "Press `Ctrl+X` to exit.",
        ],
        "emacs" => vec![
            "Edit directly in the buffer.",
            "Press `Ctrl+X Ctrl+S` to save.",
            "Press `Ctrl+X Ctrl+C` to exit.",
        ],
        "code" | "code-insiders" => vec![
            "Edit the file in VS Code.",
            "Save in the editor, then close the editor window/tab when done.",
            "If VS Code was launched with `--wait`, Studio will resume after close.",
        ],
        _ => vec![
            "Edit the file in your configured editor.",
            "Save and close the editor to return to Studio.",
            "If you want different behavior, set `$VISUAL` or `$EDITOR`.",
        ],
    }
}

fn centered_rect(width: u16, height: u16, area: Rect) -> Rect {
    let popup_width = width.min(area.width.saturating_sub(2)).max(1);
    let popup_height = height.min(area.height.saturating_sub(2)).max(1);
    Rect::new(
        area.x + area.width.saturating_sub(popup_width) / 2,
        area.y + area.height.saturating_sub(popup_height) / 2,
        popup_width,
        popup_height,
    )
}

fn execution_contracts_dir(project_dir: &Path) -> PathBuf {
    project_dir.join(STUDIO_ROOT_DIR).join(STUDIO_CONTRACTS_DIR)
}

fn attachment_sidecar_path(contract_path: &Path) -> PathBuf {
    contract_path.with_extension("attachments.json")
}

fn execution_contract_list_label(contract: &ExecutionContract) -> String {
    if contract.attachments.is_empty() {
        contract.name.clone()
    } else {
        format!(
            "{} [{} attached]",
            contract.name,
            contract.attachments.len()
        )
    }
}

fn attachment_mode_summary(mode: AttachmentMode) -> &'static str {
    match mode {
        AttachmentMode::InlineFile => "file",
        AttachmentMode::DirectoryTree => "folder",
    }
}

fn execution_contract_selection_path(project_dir: &Path) -> PathBuf {
    execution_contracts_dir(project_dir).join(STUDIO_SELECTED_CONTRACT_FILE)
}

fn editor_selection_path(project_dir: &Path) -> PathBuf {
    project_dir
        .join(STUDIO_ROOT_DIR)
        .join(STUDIO_SELECTED_EDITOR_FILE)
}

fn load_editor_choice(project_dir: &Path) -> EditorChoice {
    fs::read_to_string(editor_selection_path(project_dir))
        .ok()
        .map(|value| value.trim().to_string())
        .as_deref()
        .and_then(EditorChoice::from_persisted)
        .unwrap_or(EditorChoice::System)
}

fn persist_editor_choice(project_dir: &Path, choice: EditorChoice) -> Result<()> {
    let path = editor_selection_path(project_dir);
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }
    fs::write(path, choice.persist_value())?;
    Ok(())
}

fn default_execution_contract_content() -> &'static str {
    r#"# Standard Build Contract

- Inspect the repository before editing anything.
- Work only inside this workspace: {{workspace_dir}}
- Prefer the existing stack, conventions, and architecture over rewrites.
- Favor polished, production-quality results over placeholder output.
- If the request implies analysis, reporting, dashboarding, or visualization, generate a self-contained HTML artifact.
- Write primary generated artifacts to: {{artifact_dir}}
- If you create an HTML report, use inline CSS/JS so the file can be opened directly in a browser.
- End with a concise summary of assumptions, files changed, and the exact artifact path(s) to open.

## Delivery Guidance

- When possible, make the result feel intentional and finished, not generic.
- If data sources are ambiguous, inspect the repository and state what you found.
- If the user asks for a dashboard or report, compute the answer from repository data and create the artifact instead of only describing it.
- Treat this contract as instructions layered on top of the user's objective, not a replacement for it."#
}

fn new_execution_contract_content(name: &str) -> String {
    default_execution_contract_content().replacen(
        "# Standard Build Contract",
        &format!("# {}", name),
        1,
    )
}

fn ensure_execution_contracts_exist(project_dir: &Path) -> Result<()> {
    let dir = execution_contracts_dir(project_dir);
    fs::create_dir_all(&dir)?;

    let has_visible_contract = fs::read_dir(&dir)?
        .filter_map(|entry| entry.ok())
        .any(|entry| {
            let path = entry.path();
            path.is_file()
                && path.extension().and_then(|ext| ext.to_str()) == Some("md")
                && !entry.file_name().to_string_lossy().starts_with('.')
        });

    if !has_visible_contract {
        fs::write(
            dir.join("standard.md"),
            default_execution_contract_content(),
        )?;
    }

    Ok(())
}

fn load_attachment_specs(contract_path: &Path) -> Vec<AttachmentSpec> {
    let sidecar_path = attachment_sidecar_path(contract_path);
    let content = match fs::read_to_string(&sidecar_path) {
        Ok(content) => content,
        Err(err) if err.kind() == std::io::ErrorKind::NotFound => return Vec::new(),
        Err(err) => {
            eprintln!(
                "Foundry Studio: failed to read attachment sidecar {}: {}",
                sidecar_path.display(),
                err
            );
            return Vec::new();
        }
    };

    match serde_json::from_str::<Vec<AttachmentSpec>>(&content) {
        Ok(specs) => specs,
        Err(err) => {
            eprintln!(
                "Foundry Studio: failed to parse attachment sidecar {}: {}",
                sidecar_path.display(),
                err
            );
            Vec::new()
        }
    }
}

fn persist_attachment_specs(contract_path: &Path, specs: &[AttachmentSpec]) -> Result<()> {
    let sidecar_path = attachment_sidecar_path(contract_path);
    if let Some(parent) = sidecar_path.parent() {
        fs::create_dir_all(parent)?;
    }
    let serialized = serde_json::to_string_pretty(specs)?;
    fs::write(sidecar_path, format!("{}\n", serialized))?;
    Ok(())
}

fn load_execution_contracts(project_dir: &Path) -> Result<(Vec<ExecutionContract>, usize)> {
    load_execution_contracts_with_selection(project_dir, None)
}

fn load_execution_contracts_with_selection(
    project_dir: &Path,
    preferred_file_name: Option<&str>,
) -> Result<(Vec<ExecutionContract>, usize)> {
    ensure_execution_contracts_exist(project_dir)?;
    let dir = execution_contracts_dir(project_dir);
    let selected_path = execution_contract_selection_path(project_dir);
    let selected_file = preferred_file_name
        .map(str::to_string)
        .or_else(|| {
            fs::read_to_string(&selected_path)
                .ok()
                .map(|value| value.trim().to_string())
        })
        .filter(|value| !value.is_empty());

    let mut contracts = Vec::new();
    let mut entries: Vec<_> = fs::read_dir(&dir)?.filter_map(|entry| entry.ok()).collect();
    entries.sort_by_key(|entry| entry.file_name());

    for entry in entries {
        let file_name = entry.file_name().to_string_lossy().to_string();
        if file_name.starts_with('.') {
            continue;
        }
        let path = entry.path();
        if !path.is_file() || path.extension().and_then(|ext| ext.to_str()) != Some("md") {
            continue;
        }
        let body = fs::read_to_string(&path)
            .with_context(|| format!("failed to read execution contract {}", path.display()))?;
        let attachments = load_attachment_specs(&path);
        contracts.push(ExecutionContract {
            name: execution_contract_name(&file_name, &body),
            file_name,
            path,
            body,
            attachments,
        });
    }

    if contracts.is_empty() {
        anyhow::bail!("no execution contracts available");
    }

    let selected_index = selected_file
        .as_deref()
        .and_then(|wanted| {
            contracts
                .iter()
                .position(|contract| contract.file_name == wanted)
        })
        .unwrap_or(0);
    persist_selected_execution_contract(project_dir, &contracts[selected_index].file_name)?;
    Ok((contracts, selected_index))
}

fn execution_contract_name(file_name: &str, body: &str) -> String {
    body.lines()
        .find_map(|line| {
            let trimmed = line.trim();
            trimmed
                .strip_prefix("# ")
                .map(str::trim)
                .filter(|name| !name.is_empty())
                .map(ToOwned::to_owned)
        })
        .unwrap_or_else(|| file_name.trim_end_matches(".md").replace('-', " "))
}

fn persist_selected_execution_contract(project_dir: &Path, file_name: &str) -> Result<()> {
    let path = execution_contract_selection_path(project_dir);
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }
    fs::write(path, file_name)?;
    Ok(())
}

fn cycle_execution_contract(state: &mut StudioState, forward: bool) {
    if state.execution_contracts.is_empty() {
        return;
    }

    let len = state.execution_contracts.len();
    let selected_index = if forward {
        (state.selected_execution_contract + 1) % len
    } else {
        state
            .selected_execution_contract
            .checked_sub(1)
            .unwrap_or_else(|| len.saturating_sub(1))
    };
    state.set_selected_execution_contract_index(selected_index);
    if let Err(err) = persist_selected_execution_contract(
        &state.project_dir,
        &state.selected_execution_contract().file_name,
    ) {
        state.log(format!("failed to persist selected contract: {}", err));
    } else {
        state.log(format!(
            "execution contract: {}",
            state.selected_execution_contract().name
        ));
    }
}

fn open_attachment_manager(state: &mut StudioState) {
    state.attachment_manager = Some(AttachmentManagerState::default());
    state.sync_attachment_manager_selection();
    state.focused_pane = FocusedPane::Contracts;
}

fn cycle_attachment_manager_selection(state: &mut StudioState, forward: bool) {
    let attachment_len = state.selected_execution_contract().attachments.len();
    if attachment_len == 0 {
        return;
    }

    if let Some(manager) = state.attachment_manager.as_mut() {
        manager.selected_attachment = if forward {
            (manager.selected_attachment + 1) % attachment_len
        } else {
            manager
                .selected_attachment
                .checked_sub(1)
                .unwrap_or_else(|| attachment_len.saturating_sub(1))
        };
    }
}

fn toggle_selected_attachment_mark(state: &mut StudioState) {
    let attachment_len = state.selected_execution_contract().attachments.len();
    if attachment_len == 0 {
        return;
    }

    if let Some(manager) = state.attachment_manager.as_mut() {
        let selected = manager
            .selected_attachment
            .min(attachment_len.saturating_sub(1));
        if !manager.marked_attachments.insert(selected) {
            manager.marked_attachments.remove(&selected);
        }
    }
}

fn cycle_editor_choice(state: &mut StudioState) {
    state.editor_choice = state.editor_choice.next();
    if let Err(err) = persist_editor_choice(&state.project_dir, state.editor_choice) {
        state.log(format!("failed to persist editor choice: {}", err));
    } else {
        state.log(format!(
            "editor: {}",
            editor_choice_summary(state.editor_choice)
        ));
    }
}

fn request_delete_selected_execution_contract(state: &mut StudioState) {
    if state.execution_contracts.len() <= 1 {
        state.log("contract delete failed: cannot delete the last execution contract");
        return;
    }

    state.delete_confirmation = Some(DeleteConfirmationState {
        contract_name: state.selected_execution_contract().name.clone(),
    });
}

fn create_execution_contract(state: &mut StudioState) -> Result<()> {
    let dir = execution_contracts_dir(&state.project_dir);
    fs::create_dir_all(&dir)?;
    let contract_name = format!("Custom Contract {}", Utc::now().format("%H:%M:%S"));
    let file_name = format!("contract-{}.md", Utc::now().format("%Y%m%d-%H%M%S"));
    let path = dir.join(&file_name);
    fs::write(&path, new_execution_contract_content(&contract_name))?;
    fs::write(attachment_sidecar_path(&path), "[]\n")?;
    let (contracts, selected_index) =
        load_execution_contracts_with_selection(&state.project_dir, Some(&file_name))?;
    state.execution_contracts = contracts;
    state.set_selected_execution_contract_index(selected_index);
    state.focused_pane = FocusedPane::Contracts;
    queue_editor_action(
        state,
        PendingStudioAction::EditExecutionContract {
            path,
            action_label: "new contract",
        },
    );
    state.log("created new execution contract");
    Ok(())
}

fn edit_selected_execution_contract(state: &mut StudioState) {
    let selected = state.selected_execution_contract().clone();
    queue_editor_action(
        state,
        PendingStudioAction::EditExecutionContract {
            path: selected.path,
            action_label: "contract",
        },
    );
    state.focused_pane = FocusedPane::Contracts;
}

#[cfg(not(target_os = "macos"))]
fn edit_selected_execution_contract_attachments(state: &mut StudioState) -> Result<()> {
    let selected = state.selected_execution_contract().clone();
    let sidecar_path = attachment_sidecar_path(&selected.path);
    if !sidecar_path.exists() {
        fs::write(&sidecar_path, "[]\n")?;
    }
    queue_editor_action(
        state,
        PendingStudioAction::EditExecutionContract {
            path: sidecar_path,
            action_label: "contract attachments",
        },
    );
    state.focused_pane = FocusedPane::Contracts;
    Ok(())
}

fn queue_selected_execution_contract_attachment_action(state: &mut StudioState) -> Result<()> {
    #[cfg(target_os = "macos")]
    {
        let selected = state.selected_execution_contract().clone();
        state.pending_action = Some(PendingStudioAction::PickExecutionContractAttachment {
            contract_path: selected.path,
        });
        state.focused_pane = FocusedPane::Contracts;
        Ok(())
    }

    #[cfg(not(target_os = "macos"))]
    {
        edit_selected_execution_contract_attachments(state)
    }
}

fn queue_editor_action(state: &mut StudioState, action: PendingStudioAction) {
    state.editor_guide = Some(EditorGuideState { action });
}

fn remove_selected_execution_contract_attachments(state: &mut StudioState) -> Result<()> {
    let attachment_len = state.selected_execution_contract().attachments.len();
    if attachment_len == 0 {
        state.log("contract has no attachments");
        return Ok(());
    }

    let indices = {
        let manager = state
            .attachment_manager
            .as_ref()
            .context("attachment manager is not open")?;
        if manager.marked_attachments.is_empty() {
            BTreeSet::from([manager
                .selected_attachment
                .min(attachment_len.saturating_sub(1))])
        } else {
            manager
                .marked_attachments
                .iter()
                .copied()
                .filter(|idx| *idx < attachment_len)
                .collect()
        }
    };

    let contract_path = state.selected_execution_contract().path.clone();
    let existing = load_attachment_specs(&contract_path);
    let removed_paths: Vec<String> = existing
        .iter()
        .enumerate()
        .filter(|(idx, _)| indices.contains(idx))
        .map(|(_, spec)| spec.path.clone())
        .collect();
    let retained: Vec<AttachmentSpec> = existing
        .into_iter()
        .enumerate()
        .filter(|(idx, _)| !indices.contains(idx))
        .map(|(_, spec)| spec)
        .collect();

    persist_attachment_specs(&contract_path, &retained)?;
    state.refresh_execution_contracts()?;
    if let Some(manager) = state.attachment_manager.as_mut() {
        manager.marked_attachments.clear();
        if retained.is_empty() {
            manager.selected_attachment = 0;
        } else {
            manager.selected_attachment = manager
                .selected_attachment
                .min(retained.len().saturating_sub(1));
        }
    }
    state.log(format!(
        "removed {} attachment(s){}",
        removed_paths.len(),
        if removed_paths.is_empty() {
            String::new()
        } else {
            format!(": {}", removed_paths.join(", "))
        }
    ));
    Ok(())
}

fn pending_action_label(action: &PendingStudioAction) -> &'static str {
    match action {
        PendingStudioAction::EditExecutionContract { action_label, .. } => action_label,
        PendingStudioAction::PickExecutionContractAttachment { .. } => "contract attachment",
    }
}

fn infer_attachment_spec_from_selected_path(
    selected_path: &Path,
    project_dir: &Path,
) -> Result<AttachmentSpec> {
    let canonical_project = fs::canonicalize(project_dir).with_context(|| {
        format!(
            "failed to resolve project root for attachment picker: {}",
            project_dir.display()
        )
    })?;
    let canonical_selected = fs::canonicalize(selected_path).with_context(|| {
        format!(
            "failed to resolve selected attachment path: {}",
            selected_path.display()
        )
    })?;
    let relative = canonical_selected
        .strip_prefix(&canonical_project)
        .map_err(|_| {
            anyhow::anyhow!(
                "selected attachment must be inside the project root: {}",
                project_dir.display()
            )
        })?
        .to_path_buf();
    let mode = if canonical_selected.is_dir() {
        AttachmentMode::DirectoryTree
    } else if canonical_selected.is_file() {
        AttachmentMode::InlineFile
    } else {
        anyhow::bail!(
            "selected attachment is neither a file nor a directory: {}",
            selected_path.display()
        );
    };

    Ok(AttachmentSpec {
        path: normalize_relative_display_path(&relative),
        mode,
        label: None,
    })
}

fn append_attachment_specs_for_paths(
    contract_path: &Path,
    project_dir: &Path,
    selected_paths: &[PathBuf],
) -> Result<Vec<AttachmentSpec>> {
    let mut specs = load_attachment_specs(contract_path);
    let mut changed = false;

    for selected_path in selected_paths {
        let spec = infer_attachment_spec_from_selected_path(selected_path, project_dir)?;
        if specs
            .iter()
            .any(|existing| existing.path == spec.path && existing.mode == spec.mode)
        {
            continue;
        }
        specs.push(spec);
        changed = true;
    }

    if changed || !attachment_sidecar_path(contract_path).exists() {
        persist_attachment_specs(contract_path, &specs)?;
    }

    Ok(specs)
}

#[cfg(target_os = "macos")]
fn pick_attachment_paths(project_dir: &Path) -> Result<Vec<PathBuf>> {
    let script = r#"
ObjC.import("AppKit");
ObjC.import("Foundation");
var app = $.NSApplication.sharedApplication;
app.setActivationPolicy($.NSApplicationActivationPolicyRegular);
var panel = $.NSOpenPanel.openPanel;
panel.setCanChooseFiles(true);
panel.setCanChooseDirectories(true);
panel.setAllowsMultipleSelection(true);
panel.setCanCreateDirectories(false);
panel.setResolvesAliases(true);
panel.setPrompt($("Attach"));
panel.setMessage($("Choose file(s) or folder(s) to attach"));
var projectDir = $.NSProcessInfo.processInfo.environment.objectForKey("FOUNDRY_PROJECT_DIR");
if (projectDir) {
    panel.setDirectoryURL($.NSURL.fileURLWithPath($(ObjC.unwrap(projectDir))));
}
$.NSRunningApplication.currentApplication.activateWithOptions($.NSApplicationActivateIgnoringOtherApps);
app.activateIgnoringOtherApps(true);
panel.orderFrontRegardless;
var response = panel.runModal;
if (response !== $.NSModalResponseOK) { ""; }
else {
    var urls = panel.URLs;
    var out = [];
    for (var i = 0; i < urls.count; i++) {
        out.push(ObjC.unwrap(urls.objectAtIndex(i).path));
    }
    out.join("\n");
}
"#;

    let output = Command::new("osascript")
        .args(["-l", "JavaScript", "-e", script])
        .env("FOUNDRY_PROJECT_DIR", project_dir)
        .output()
        .context("failed to open macOS attachment picker")?;

    if !output.status.success() {
        anyhow::bail!(
            "attachment picker failed: {}",
            String::from_utf8_lossy(&output.stderr).trim()
        );
    }

    Ok(String::from_utf8_lossy(&output.stdout)
        .lines()
        .map(str::trim)
        .filter(|line| !line.is_empty())
        .map(PathBuf::from)
        .collect())
}

#[cfg(not(target_os = "macos"))]
fn pick_attachment_paths(_project_dir: &Path) -> Result<Vec<PathBuf>> {
    anyhow::bail!("native attachment picker is only available on macOS");
}

fn delete_selected_execution_contract(state: &mut StudioState) -> Result<()> {
    if state.execution_contracts.len() <= 1 {
        anyhow::bail!("cannot delete the last execution contract");
    }

    let selected_index = state.selected_execution_contract;
    let selected = state.selected_execution_contract().clone();
    let trash_dir = execution_contracts_dir(&state.project_dir).join(".trash");
    fs::create_dir_all(&trash_dir)?;
    let trash_name = format!(
        "{}-{}",
        Utc::now().format("%Y%m%d-%H%M%S"),
        selected.file_name
    );
    fs::rename(&selected.path, trash_dir.join(trash_name))?;
    let sidecar_path = attachment_sidecar_path(&selected.path);
    if sidecar_path.exists() {
        let sidecar_name = sidecar_path
            .file_name()
            .and_then(|name| name.to_str())
            .unwrap_or("contract.attachments.json");
        let trashed_sidecar_name =
            format!("{}-{}", Utc::now().format("%Y%m%d-%H%M%S"), sidecar_name);
        fs::rename(&sidecar_path, trash_dir.join(trashed_sidecar_name))?;
    }

    let preferred_file_name = state
        .execution_contracts
        .iter()
        .enumerate()
        .find_map(|(idx, contract)| {
            (idx != selected_index
                && (idx == selected_index.saturating_add(1)
                    || idx == selected_index.saturating_sub(1)))
            .then(|| contract.file_name.clone())
        })
        .or_else(|| {
            state
                .execution_contracts
                .iter()
                .enumerate()
                .find_map(|(idx, contract)| {
                    (idx != selected_index).then(|| contract.file_name.clone())
                })
        });
    let (contracts, selected_index) = load_execution_contracts_with_selection(
        &state.project_dir,
        preferred_file_name.as_deref(),
    )?;
    let deleted_name = selected.name;
    state.execution_contracts = contracts;
    state.set_selected_execution_contract_index(selected_index);
    persist_selected_execution_contract(
        &state.project_dir,
        &state.selected_execution_contract().file_name,
    )?;
    state.log(format!("deleted execution contract: {}", deleted_name));
    Ok(())
}

fn handle_pending_action(
    terminal: &mut tui::Tui,
    state: &mut StudioState,
    action: PendingStudioAction,
    event_tx: &mpsc::UnboundedSender<StudioEvent>,
    terminal_event_reader: &mut JoinHandle<()>,
) -> Result<()> {
    match action {
        PendingStudioAction::EditExecutionContract { path, action_label } => {
            terminal_event_reader.abort();
            tui::restore_terminal(terminal)?;
            let editor_result =
                open_file_in_editor(&path, &resolve_editor_command(state.editor_choice));
            *terminal = tui::setup_terminal()?;
            *terminal_event_reader = spawn_terminal_event_reader(event_tx.clone());
            match editor_result {
                Ok(()) => {
                    state.refresh_execution_contracts()?;
                    state.log(format!("updated {}", action_label));
                }
                Err(err) => {
                    state.log(format!("failed to edit {}: {}", action_label, err));
                }
            }
        }
        PendingStudioAction::PickExecutionContractAttachment { contract_path } => {
            terminal_event_reader.abort();
            tui::restore_terminal(terminal)?;
            let picker_result = pick_attachment_paths(&state.project_dir);
            *terminal = tui::setup_terminal()?;
            *terminal_event_reader = spawn_terminal_event_reader(event_tx.clone());
            match picker_result {
                Ok(paths) if paths.is_empty() => {
                    state.log("attachment picker canceled");
                }
                Ok(paths) => match append_attachment_specs_for_paths(
                    &contract_path,
                    &state.project_dir,
                    &paths,
                ) {
                    Ok(specs) => {
                        state.refresh_execution_contracts()?;
                        let selected_paths = paths
                            .iter()
                            .filter_map(|path| {
                                infer_attachment_spec_from_selected_path(path, &state.project_dir)
                                    .ok()
                                    .map(|spec| spec.path)
                            })
                            .collect::<Vec<_>>();
                        state.log(format!(
                            "attached {} item(s) to contract{}",
                            selected_paths.len(),
                            if selected_paths.is_empty() {
                                "".to_string()
                            } else {
                                format!(": {}", selected_paths.join(", "))
                            }
                        ));
                        if specs.is_empty() {
                            state.log("contract has no attachments");
                        }
                    }
                    Err(err) => {
                        state.log(format!("failed to add attachment: {}", err));
                    }
                },
                Err(err) => {
                    state.log(format!("attachment picker failed: {}", err));
                }
            }
        }
    }
    Ok(())
}

fn open_file_in_editor(path: &Path, editor: &str) -> Result<()> {
    let status = Command::new("sh")
        .arg("-c")
        .arg("$FOUNDRY_EDITOR \"$FOUNDRY_TARGET_FILE\"")
        .env("FOUNDRY_EDITOR", editor)
        .env("FOUNDRY_TARGET_FILE", path)
        .status()
        .context("failed to launch editor")?;
    if !status.success() {
        anyhow::bail!("editor exited with status {}", status);
    }
    Ok(())
}

fn copy_workspace_snapshot(src_root: &Path, dst_root: &Path) -> Result<()> {
    fs::create_dir_all(dst_root)?;
    copy_workspace_snapshot_inner(src_root, dst_root, Path::new(""))
}

fn copy_workspace_snapshot_inner(src_root: &Path, dst_root: &Path, rel: &Path) -> Result<()> {
    let current_src = if rel.as_os_str().is_empty() {
        src_root.to_path_buf()
    } else {
        src_root.join(rel)
    };

    let mut entries: Vec<_> = fs::read_dir(&current_src)?
        .filter_map(|entry| entry.ok())
        .collect();
    entries.sort_by_key(|entry| entry.file_name());

    for entry in entries {
        let name = entry.file_name();
        let next_rel = if rel.as_os_str().is_empty() {
            PathBuf::from(&name)
        } else {
            rel.join(&name)
        };

        if should_skip_snapshot_path(&next_rel) {
            continue;
        }

        let src_path = src_root.join(&next_rel);
        let dst_path = dst_root.join(&next_rel);
        let file_type = entry.file_type()?;

        if file_type.is_dir() {
            fs::create_dir_all(&dst_path)?;
            copy_workspace_snapshot_inner(src_root, dst_root, &next_rel)?;
        } else if file_type.is_file() {
            if let Some(parent) = dst_path.parent() {
                fs::create_dir_all(parent)?;
            }
            fs::copy(&src_path, &dst_path).with_context(|| {
                format!(
                    "failed to copy {} to {}",
                    src_path.display(),
                    dst_path.display()
                )
            })?;
        }
    }

    Ok(())
}

fn should_skip_snapshot_path(rel: &Path) -> bool {
    let components: Vec<String> = rel
        .components()
        .map(|component| component.as_os_str().to_string_lossy().to_string())
        .collect();

    if components.is_empty() {
        return false;
    }

    let first = components[0].as_str();
    if matches!(
        first,
        ".git"
            | "target"
            | "node_modules"
            | ".venv"
            | "venv"
            | "__pycache__"
            | ".pytest_cache"
            | ".ruff_cache"
            | ".build-venv"
    ) {
        return true;
    }

    components.len() >= 2 && components[0] == ".foundry" && components[1] == "studio"
}

fn discover_artifacts(
    workspace_dir: &Path,
    artifact_dir: &Path,
    started_at: SystemTime,
) -> Vec<PathBuf> {
    let mut paths = BTreeSet::new();
    collect_recent_artifacts(artifact_dir, artifact_dir, started_at, &mut paths, 12);
    if paths.is_empty() {
        collect_recent_artifacts(workspace_dir, workspace_dir, started_at, &mut paths, 12);
    }
    paths.into_iter().collect()
}

fn collect_recent_artifacts(
    root: &Path,
    current: &Path,
    started_at: SystemTime,
    paths: &mut BTreeSet<PathBuf>,
    limit: usize,
) {
    if paths.len() >= limit {
        return;
    }

    let Ok(entries) = fs::read_dir(current) else {
        return;
    };

    let mut entries: Vec<_> = entries.filter_map(|entry| entry.ok()).collect();
    entries.sort_by_key(|entry| entry.file_name());

    for entry in entries {
        if paths.len() >= limit {
            return;
        }
        let path = entry.path();
        let rel = path.strip_prefix(root).unwrap_or(&path);
        if should_skip_snapshot_path(rel) {
            continue;
        }

        let Ok(file_type) = entry.file_type() else {
            continue;
        };

        if file_type.is_dir() {
            collect_recent_artifacts(root, &path, started_at, paths, limit);
            continue;
        }

        let Some(ext) = path.extension().and_then(|ext| ext.to_str()) else {
            continue;
        };
        if !matches!(ext, "html" | "htm" | "md" | "json") {
            continue;
        }

        let Ok(metadata) = entry.metadata() else {
            continue;
        };
        let modified = metadata.modified().unwrap_or(SystemTime::UNIX_EPOCH);
        if modified < started_at {
            continue;
        }
        paths.insert(path);
    }
}

fn output_style(line: &str) -> Style {
    if line.starts_with("[stderr]") {
        Style::default().fg(Color::Red)
    } else if line.starts_with("[tool]") {
        Style::default().fg(Color::Yellow)
    } else if line.starts_with("[result]") {
        Style::default().fg(Color::DarkGray)
    } else {
        Style::default().fg(Color::White)
    }
}

fn current_studio_layout(state: &StudioState) -> Option<StudioLayout> {
    let Ok((width, height)) = crossterm::terminal::size() else {
        return None;
    };
    Some(studio_layout(
        Rect::new(0, 0, width, height),
        state.layout_config,
    ))
}

fn clamped_left_column_width(body_width: u16, percent: u16) -> u16 {
    let content_width = body_width.saturating_sub(COLUMN_SPLIT_WIDTH);
    if content_width > MIN_LEFT_COLUMN_WIDTH + MIN_RIGHT_COLUMN_WIDTH {
        ((content_width as u32 * percent as u32) / 100).clamp(
            MIN_LEFT_COLUMN_WIDTH as u32,
            content_width.saturating_sub(MIN_RIGHT_COLUMN_WIDTH) as u32,
        ) as u16
    } else {
        (content_width / 2).max(1)
    }
}

fn left_content_height(area: Rect) -> u16 {
    area.height
        .saturating_sub(ROW_SPLIT_HEIGHT.saturating_mul(LEFT_SPLIT_COUNT))
}

fn right_content_height(area: Rect) -> u16 {
    area.height
        .saturating_sub(ROW_SPLIT_HEIGHT.saturating_mul(RIGHT_SPLIT_COUNT))
}

fn resize_handle_at(layout: &StudioLayout, column: u16, row: u16) -> Option<ResizeHandle> {
    if rect_contains(layout.left_scan_prompt_split, column, row) {
        return Some(ResizeHandle::LeftScanPrompt);
    }
    if rect_contains(layout.left_prompt_contracts_split, column, row) {
        return Some(ResizeHandle::LeftPromptContracts);
    }
    if rect_contains(layout.left_contracts_brief_split, column, row) {
        return Some(ResizeHandle::LeftContractsBrief);
    }
    if rect_contains(layout.right_sessions_output_split, column, row) {
        return Some(ResizeHandle::RightSessionsOutput);
    }
    if rect_contains(layout.right_output_activity_split, column, row) {
        return Some(ResizeHandle::RightOutputActivity);
    }

    let min_column = layout
        .column_split
        .x
        .saturating_sub(COLUMN_RESIZE_HIT_MARGIN);
    let max_column = layout
        .column_split
        .x
        .saturating_add(layout.column_split.width.saturating_sub(1))
        .saturating_add(COLUMN_RESIZE_HIT_MARGIN);
    if row >= layout.column_split.y
        && row
            < layout
                .column_split
                .y
                .saturating_add(layout.column_split.height)
        && column >= min_column
        && column <= max_column
    {
        return Some(ResizeHandle::ColumnSplit);
    }

    None
}

fn apply_resize_drag(
    state: &mut StudioState,
    layout: &StudioLayout,
    drag: ResizeDragState,
    column: u16,
    row: u16,
) {
    let delta_columns = column as i32 - drag.start_column as i32;
    let delta_rows = row as i32 - drag.start_row as i32;
    let mut config = drag.initial_layout;

    match drag.handle {
        ResizeHandle::ColumnSplit => {
            let initial_left_width = clamped_left_column_width(
                layout.body.width,
                drag.initial_layout.left_column_percent,
            ) as i32;
            let min_left = 1.max(MIN_LEFT_COLUMN_WIDTH.min(layout.body.width / 2)) as i32;
            let min_right = 1.max(MIN_RIGHT_COLUMN_WIDTH.min(layout.body.width / 2)) as i32;
            let content_width = layout.body.width.saturating_sub(COLUMN_SPLIT_WIDTH);
            let max_left = content_width.saturating_sub(min_right as u16).max(1) as i32;
            let new_left_width = (initial_left_width + delta_columns).clamp(min_left, max_left);
            config.left_column_percent =
                ((new_left_width * 100) / content_width.max(1) as i32).clamp(1, 99) as u16;
        }
        ResizeHandle::LeftScanPrompt => {
            let max_height = (left_content_height(layout.left_body) as i32
                - drag.initial_layout.left_prompt_height as i32
                - drag.initial_layout.left_contracts_height as i32
                - MIN_LEFT_BRIEF_HEIGHT as i32)
                .max(MIN_LEFT_SECTION_HEIGHT as i32);
            config.left_scan_height = (drag.initial_layout.left_scan_height as i32 + delta_rows)
                .clamp(MIN_LEFT_SECTION_HEIGHT as i32, max_height)
                as u16;
        }
        ResizeHandle::LeftPromptContracts => {
            let max_height = (left_content_height(layout.left_body) as i32
                - drag.initial_layout.left_scan_height as i32
                - drag.initial_layout.left_contracts_height as i32
                - MIN_LEFT_BRIEF_HEIGHT as i32)
                .max(MIN_LEFT_SECTION_HEIGHT as i32);
            config.left_prompt_height = (drag.initial_layout.left_prompt_height as i32 + delta_rows)
                .clamp(MIN_LEFT_SECTION_HEIGHT as i32, max_height)
                as u16;
        }
        ResizeHandle::LeftContractsBrief => {
            let max_height = (left_content_height(layout.left_body) as i32
                - drag.initial_layout.left_scan_height as i32
                - drag.initial_layout.left_prompt_height as i32
                - MIN_LEFT_BRIEF_HEIGHT as i32)
                .max(MIN_LEFT_SECTION_HEIGHT as i32);
            config.left_contracts_height =
                (drag.initial_layout.left_contracts_height as i32 + delta_rows)
                    .clamp(MIN_LEFT_SECTION_HEIGHT as i32, max_height) as u16;
        }
        ResizeHandle::RightSessionsOutput => {
            let max_height = (right_content_height(layout.right_body) as i32
                - drag.initial_layout.right_activity_height as i32
                - MIN_OUTPUT_HEIGHT as i32)
                .max(MIN_RIGHT_SECTION_HEIGHT as i32);
            config.right_sessions_height =
                (drag.initial_layout.right_sessions_height as i32 + delta_rows)
                    .clamp(MIN_RIGHT_SECTION_HEIGHT as i32, max_height) as u16;
        }
        ResizeHandle::RightOutputActivity => {
            let max_height = (right_content_height(layout.right_body) as i32
                - drag.initial_layout.right_sessions_height as i32
                - MIN_OUTPUT_HEIGHT as i32)
                .max(MIN_RIGHT_SECTION_HEIGHT as i32);
            config.right_activity_height =
                (drag.initial_layout.right_activity_height as i32 - delta_rows)
                    .clamp(MIN_RIGHT_SECTION_HEIGHT as i32, max_height) as u16;
        }
    }

    state.layout_config = config;
}

fn pane_at_position(layout: &StudioLayout, column: u16, row: u16) -> Option<FocusedPane> {
    [
        (FocusedPane::Scan, layout.scan),
        (FocusedPane::Prompt, layout.prompt),
        (FocusedPane::Contracts, layout.contracts),
        (FocusedPane::ExecutionBrief, layout.execution_brief),
        (FocusedPane::Sessions, layout.sessions),
        (FocusedPane::Output, layout.output),
        (FocusedPane::Activity, layout.activity),
    ]
    .into_iter()
    .find_map(|(pane, area)| rect_contains(area, column, row).then_some(pane))
}

fn rect_contains(area: Rect, column: u16, row: u16) -> bool {
    let max_x = area.x.saturating_add(area.width);
    let max_y = area.y.saturating_add(area.height);
    column >= area.x && column < max_x && row >= area.y && row < max_y
}

fn select_session_from_click(state: &mut StudioState, area: Rect, row: u16) {
    if state.sessions.is_empty()
        || row <= area.y
        || row >= area.y.saturating_add(area.height).saturating_sub(1)
    {
        return;
    }

    let index = row.saturating_sub(area.y.saturating_add(1)) as usize;
    if index < state.sessions.len() {
        state.selected_session = index;
        state.output_scroll = 0;
    }
}

fn select_execution_contract_from_click(state: &mut StudioState, area: Rect, row: u16) {
    if state.execution_contracts.is_empty()
        || row <= area.y + 1
        || row >= area.y.saturating_add(area.height).saturating_sub(1)
    {
        return;
    }

    let index = row.saturating_sub(area.y.saturating_add(2)) as usize;
    if index < state.execution_contracts.len() {
        state.set_selected_execution_contract_index(index);
        if let Err(err) = persist_selected_execution_contract(
            &state.project_dir,
            &state.selected_execution_contract().file_name,
        ) {
            state.log(format!("failed to persist selected contract: {}", err));
        }
    }
}

fn pane_border_style(state: &StudioState, pane: FocusedPane, accent: Color) -> Style {
    if state.focused_pane == pane {
        Style::default().fg(accent).add_modifier(Modifier::BOLD)
    } else {
        Style::default().fg(Color::DarkGray)
    }
}

fn pane_title_style(state: &StudioState, pane: FocusedPane, accent: Color) -> Style {
    if state.focused_pane == pane {
        Style::default().fg(accent).add_modifier(Modifier::BOLD)
    } else {
        Style::default().fg(accent)
    }
}

fn pane_border_type(state: &StudioState, pane: FocusedPane) -> BorderType {
    if state.focused_pane == pane {
        BorderType::Thick
    } else {
        BorderType::Plain
    }
}

fn provider_color(provider: ModelProvider) -> Color {
    match provider {
        ModelProvider::Claude => Color::LightMagenta,
        ModelProvider::Codex => Color::LightBlue,
    }
}

fn studio_spinner(tick_count: usize) -> char {
    const SPINNER: &[char] = &['|', '/', '-', '\\'];
    SPINNER[tick_count % SPINNER.len()]
}

fn wrap_text_lines(text: &str, width: usize) -> Vec<String> {
    if width == 0 {
        return vec![String::new()];
    }

    let mut lines = Vec::new();
    for line in text.lines() {
        if line.is_empty() {
            lines.push(String::new());
            continue;
        }

        let mut remaining = line;
        while !remaining.is_empty() {
            if remaining.len() <= width {
                lines.push(remaining.to_string());
                break;
            }
            let safe_width = truncate_str(remaining, width).len();
            if safe_width == 0 {
                let first_char_len = remaining
                    .chars()
                    .next()
                    .map(|ch| ch.len_utf8())
                    .unwrap_or(1);
                lines.push(remaining[..first_char_len].to_string());
                remaining = &remaining[first_char_len..];
                continue;
            }
            let split_at = remaining[..safe_width]
                .rfind(' ')
                .map(|idx| idx + 1)
                .unwrap_or(safe_width);
            lines.push(remaining[..split_at].to_string());
            remaining = &remaining[split_at..];
        }
    }

    if lines.is_empty() {
        lines.push(String::new());
    }

    lines
}

fn truncate_display_path(path: &Path, max_len: usize) -> String {
    let display = path.display().to_string();
    if display.len() <= max_len {
        display
    } else {
        let suffix_len = max_len.saturating_sub(3);
        let mut start = display.len().saturating_sub(suffix_len);
        while start < display.len() && !display.is_char_boundary(start) {
            start += 1;
        }
        format!("...{}", &display[start..])
    }
}

fn join_or_none(items: &[String], separator: &str) -> String {
    if items.is_empty() {
        "none".to_string()
    } else {
        items.join(separator)
    }
}

fn follow_up_context(session: &SessionState) -> String {
    let mut tail = Vec::new();
    let mut total_chars = 0usize;

    for line in session
        .output
        .iter()
        .rev()
        .filter(|line| !line.trim().is_empty())
        .take(FOLLOW_UP_CONTEXT_MAX_LINES)
    {
        let capped_line = truncate_str(line, FOLLOW_UP_CONTEXT_MAX_CHARS);
        let additional_chars = capped_line.len() + usize::from(!tail.is_empty());
        if total_chars + additional_chars > FOLLOW_UP_CONTEXT_MAX_CHARS {
            if tail.is_empty() {
                tail.push(capped_line.to_string());
            }
            break;
        }
        tail.push(capped_line.to_string());
        total_chars += additional_chars;
    }

    tail.reverse();
    tail.join("\n")
}

fn follow_up_workspace_issue(workspace_dir: &Path) -> Option<String> {
    if !workspace_dir.exists() {
        Some(format!(
            "follow-up blocked: selected workspace no longer exists: {}",
            workspace_dir.display()
        ))
    } else if !workspace_dir.is_dir() {
        Some(format!(
            "follow-up blocked: selected workspace is not a directory: {}",
            workspace_dir.display()
        ))
    } else {
        None
    }
}

fn default_provider_mode(
    claude_readiness: &ProviderReadiness,
    codex_readiness: &ProviderReadiness,
) -> ProviderMode {
    match (
        claude_readiness.is_available(),
        codex_readiness.is_available(),
    ) {
        (true, true) => ProviderMode::Both,
        (true, false) => ProviderMode::Claude,
        (false, true) => ProviderMode::Codex,
        (false, false) => ProviderMode::Claude,
    }
}

fn probe_claude_readiness(project_dir: &Path, model: &str) -> ProviderReadiness {
    if !command_exists("claude") {
        return ProviderReadiness::missing("claude CLI not found in PATH");
    }

    let output = Command::new("claude").arg("--help").output();
    let output = match output {
        Ok(output) => output,
        Err(err) => {
            return ProviderReadiness::blocked(format!("failed to run `claude --help`: {}", err));
        }
    };

    if !output.status.success() {
        return ProviderReadiness::blocked(format!(
            "`claude --help` exited with status {}",
            output.status
        ));
    }

    let mut help_text = String::new();
    help_text.push_str(&String::from_utf8_lossy(&output.stdout));
    if !output.stderr.is_empty() {
        if !help_text.is_empty() {
            help_text.push('\n');
        }
        help_text.push_str(&String::from_utf8_lossy(&output.stderr));
    }

    let contract = assess_claude_help(&help_text);
    if !contract.is_available() {
        return contract;
    }

    let auth = match check_claude_auth() {
        Ok(auth) => auth,
        Err(err) => {
            return ProviderReadiness::blocked(format!("Claude auth status check failed: {}", err));
        }
    };

    if !auth.authenticated {
        return ProviderReadiness::blocked(auth.detail);
    }

    if let Some(detail) =
        load_cached_live_probe(project_dir, ModelProvider::Claude, model, &auth.detail)
    {
        return ProviderReadiness::ready(detail);
    }

    match run_claude_live_probe(model) {
        Ok(()) => {
            save_cached_live_probe(project_dir, ModelProvider::Claude, model, &auth.detail);
            ProviderReadiness::ready(format!("authenticated; live smoke OK via {}", auth.detail))
        }
        Err(err) => ProviderReadiness::blocked(format!(
            "authenticated but live Claude smoke failed: {}",
            err
        )),
    }
}

fn probe_codex_readiness(project_dir: &Path, model: &str) -> ProviderReadiness {
    if !command_exists("codex") {
        return ProviderReadiness::missing("codex CLI not found in PATH");
    }

    let output = Command::new("codex").args(["exec", "--help"]).output();
    let output = match output {
        Ok(output) => output,
        Err(err) => {
            return ProviderReadiness::blocked(format!(
                "failed to run `codex exec --help`: {}",
                err
            ));
        }
    };

    if !output.status.success() {
        return ProviderReadiness::blocked(format!(
            "`codex exec --help` exited with status {}",
            output.status
        ));
    }

    let mut help_text = String::new();
    help_text.push_str(&String::from_utf8_lossy(&output.stdout));
    if !output.stderr.is_empty() {
        if !help_text.is_empty() {
            help_text.push('\n');
        }
        help_text.push_str(&String::from_utf8_lossy(&output.stderr));
    }

    let contract = assess_codex_exec_help(&help_text);
    if !contract.is_available() {
        return contract;
    }

    let auth = match check_codex_auth() {
        Ok(auth) => auth,
        Err(err) => {
            return ProviderReadiness::blocked(format!("Codex login status check failed: {}", err));
        }
    };

    if !auth.authenticated {
        return ProviderReadiness::blocked(auth.detail);
    }

    if let Some(detail) =
        load_cached_live_probe(project_dir, ModelProvider::Codex, model, &auth.detail)
    {
        return ProviderReadiness::ready(detail);
    }

    match run_codex_live_probe(model) {
        Ok(()) => {
            save_cached_live_probe(project_dir, ModelProvider::Codex, model, &auth.detail);
            ProviderReadiness::ready(format!("authenticated; live smoke OK via {}", auth.detail))
        }
        Err(err) => ProviderReadiness::blocked(format!(
            "authenticated but live Codex smoke failed: {}",
            err
        )),
    }
}

fn assess_claude_help(help_text: &str) -> ProviderReadiness {
    let required_tokens = [
        ("usage", "Usage: claude"),
        ("--print", "--print"),
        ("--output-format", "--output-format"),
        ("stream-json", "stream-json"),
        ("--verbose", "--verbose"),
        (
            "--dangerously-skip-permissions",
            "--dangerously-skip-permissions",
        ),
    ];

    let missing: Vec<&str> = required_tokens
        .iter()
        .filter_map(|(label, token)| (!help_text.contains(token)).then_some(*label))
        .collect();

    if missing.is_empty() {
        ProviderReadiness::ready(
            "--print, --output-format=stream-json, --verbose, and --dangerously-skip-permissions supported",
        )
    } else {
        ProviderReadiness::blocked(format!(
            "missing required Claude features: {}",
            missing.join(", ")
        ))
    }
}

fn assess_codex_exec_help(help_text: &str) -> ProviderReadiness {
    let required_tokens = [
        ("exec usage", "Usage: codex exec"),
        ("--json", "--json"),
        ("--full-auto", "--full-auto"),
        ("--output-last-message", "--output-last-message"),
        ("--skip-git-repo-check", "--skip-git-repo-check"),
    ];

    let missing: Vec<&str> = required_tokens
        .iter()
        .filter_map(|(label, token)| (!help_text.contains(token)).then_some(*label))
        .collect();

    if missing.is_empty() {
        ProviderReadiness::ready(
            "exec, --json, --full-auto, --output-last-message, and --skip-git-repo-check supported",
        )
    } else {
        ProviderReadiness::blocked(format!(
            "missing required Codex exec features: {}",
            missing.join(", ")
        ))
    }
}

fn check_claude_auth() -> Result<AuthCheck> {
    let output = Command::new("claude")
        .args(["auth", "status", "--json"])
        .output()
        .context("failed to run `claude auth status --json`")?;

    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    let status: ClaudeAuthStatus =
        serde_json::from_str(&stdout).context("failed to parse Claude auth status JSON")?;

    if status.logged_in {
        let auth_method = status.auth_method.as_deref().unwrap_or("unknown");
        let api_provider = status.api_provider.as_deref().unwrap_or("unknown");
        Ok(AuthCheck {
            authenticated: true,
            detail: format!("{} / {}", auth_method, api_provider),
        })
    } else {
        Ok(AuthCheck {
            authenticated: false,
            detail: "not logged in".to_string(),
        })
    }
}

fn check_codex_auth() -> Result<AuthCheck> {
    let output = Command::new("codex")
        .args(["login", "status"])
        .output()
        .context("failed to run `codex login status`")?;

    let stdout = String::from_utf8_lossy(&output.stdout).trim().to_string();
    let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();
    let text = if !stdout.is_empty() { stdout } else { stderr };

    let normalized = text.to_lowercase();
    if normalized.contains("logged in") {
        Ok(AuthCheck {
            authenticated: true,
            detail: text,
        })
    } else if normalized.contains("not logged in") || normalized.contains("logged out") {
        Ok(AuthCheck {
            authenticated: false,
            detail: if text.is_empty() {
                "not logged in".to_string()
            } else {
                text
            },
        })
    } else if output.status.success() {
        Ok(AuthCheck {
            authenticated: false,
            detail: if text.is_empty() {
                "login status did not confirm authentication".to_string()
            } else {
                text
            },
        })
    } else {
        anyhow::bail!(
            "`codex login status` exited with status {}: {}",
            output.status,
            text
        );
    }
}

fn run_claude_live_probe(model: &str) -> Result<()> {
    let probe_dir = make_probe_dir("claude")?;
    let mut cmd = Command::new("claude");
    cmd.current_dir(&probe_dir);
    cmd.arg("-p");
    cmd.arg("Reply with exactly OK and no other text.");
    if !model.trim().is_empty() {
        cmd.arg("--model");
        cmd.arg(model);
    }
    cmd.args([
        "--output-format",
        "stream-json",
        "--verbose",
        "--dangerously-skip-permissions",
        "--no-session-persistence",
        "--tools",
        "",
    ]);

    let result = run_command_with_timeout(cmd, Duration::from_secs(LIVE_PROBE_TIMEOUT_SECS));
    let _ = fs::remove_dir_all(&probe_dir);
    let output = result?;

    if !output.success {
        anyhow::bail!(summarize_command_failure("claude live smoke", &output));
    }

    if !claude_probe_output_contains_ok(&output.stdout) {
        anyhow::bail!("unexpected Claude smoke output");
    }

    Ok(())
}

fn run_codex_live_probe(model: &str) -> Result<()> {
    let probe_dir = make_probe_dir("codex")?;
    let last_message_path = probe_dir.join("last-message.txt");
    let mut cmd = Command::new("codex");
    cmd.current_dir(&probe_dir);
    cmd.arg("exec");
    cmd.arg("--json");
    cmd.arg("--full-auto");
    cmd.arg("--skip-git-repo-check");
    cmd.arg("--ephemeral");
    cmd.arg("--output-last-message");
    cmd.arg(last_message_path.to_string_lossy().to_string());
    if !model.trim().is_empty() {
        cmd.arg("--model");
        cmd.arg(model);
    }
    cmd.arg("Reply with exactly OK and do not run commands, inspect files, or use tools.");

    let result = run_command_with_timeout(cmd, Duration::from_secs(LIVE_PROBE_TIMEOUT_SECS));
    let output = result?;
    let last_message = fs::read_to_string(&last_message_path).unwrap_or_default();
    let _ = fs::remove_dir_all(&probe_dir);

    if !output.success {
        anyhow::bail!(summarize_command_failure("codex live smoke", &output));
    }

    if !last_message.to_uppercase().contains("OK") {
        anyhow::bail!("unexpected Codex smoke output");
    }

    Ok(())
}

fn run_command_with_timeout(mut cmd: Command, timeout: Duration) -> Result<CapturedCommand> {
    cmd.stdout(Stdio::piped());
    cmd.stderr(Stdio::piped());
    let mut child = cmd.spawn().context("failed to spawn probe command")?;
    let deadline = Instant::now() + timeout;

    loop {
        if Instant::now() >= deadline {
            let _ = child.kill();
            let _ = child.wait();
            anyhow::bail!("timed out after {}s", timeout.as_secs());
        }

        match child
            .try_wait()
            .context("failed while waiting for probe command")?
        {
            Some(status) => {
                let mut stdout = String::new();
                let mut stderr = String::new();
                if let Some(mut handle) = child.stdout.take() {
                    let _ = handle.read_to_string(&mut stdout);
                }
                if let Some(mut handle) = child.stderr.take() {
                    let _ = handle.read_to_string(&mut stderr);
                }
                return Ok(CapturedCommand {
                    success: status.success(),
                    stdout,
                    stderr,
                });
            }
            None => std::thread::sleep(Duration::from_millis(100)),
        }
    }
}

fn make_probe_dir(provider_slug: &str) -> Result<PathBuf> {
    let path = std::env::temp_dir().join(format!(
        "foundry-studio-live-probe-{}-{}",
        provider_slug,
        Utc::now().timestamp_nanos_opt().unwrap_or(0)
    ));
    fs::create_dir_all(&path)?;
    Ok(path)
}

fn claude_probe_output_contains_ok(stdout: &str) -> bool {
    for line in stdout.lines() {
        if !line.contains('{') {
            continue;
        }
        let Ok(value) = serde_json::from_str::<serde_json::Value>(line) else {
            continue;
        };
        if let Some(result) = value.get("result").and_then(|value| value.as_str()) {
            if result.to_uppercase().contains("OK") {
                return true;
            }
        }
        if let Some(content) = value
            .get("message")
            .and_then(|message| message.get("content"))
            .and_then(|content| content.as_array())
        {
            for block in content {
                if let Some(text) = block.get("text").and_then(|value| value.as_str()) {
                    if text.to_uppercase().contains("OK") {
                        return true;
                    }
                }
            }
        }
    }

    false
}

fn summarize_command_failure(context: &str, output: &CapturedCommand) -> String {
    let stderr = truncate_str(output.stderr.trim(), 120);
    let stdout = truncate_str(output.stdout.trim(), 120);
    format!(
        "{} failed; stderr=`{}` stdout=`{}`",
        context,
        if stderr.is_empty() { "<empty>" } else { stderr },
        if stdout.is_empty() { "<empty>" } else { stdout }
    )
}

fn probe_cache_path(project_dir: &Path) -> PathBuf {
    project_dir.join(STUDIO_ROOT_DIR).join("probe-cache.json")
}

fn load_cached_live_probe(
    project_dir: &Path,
    provider: ModelProvider,
    model: &str,
    auth_detail: &str,
) -> Option<String> {
    let path = probe_cache_path(project_dir);
    let content = fs::read_to_string(path).ok()?;
    let cache: ProbeCache = serde_json::from_str(&content).ok()?;
    let now = Utc::now();

    cache.entries.iter().find_map(|entry| {
        let fresh =
            now.signed_duration_since(entry.checked_at).num_seconds() <= LIVE_PROBE_TTL_SECS;
        if entry.provider == provider.slug()
            && entry.model == model
            && entry.auth_detail == auth_detail
            && fresh
        {
            let age = now
                .signed_duration_since(entry.checked_at)
                .num_seconds()
                .max(0);
            Some(format!(
                "authenticated; cached live smoke OK ({}s old)",
                age
            ))
        } else {
            None
        }
    })
}

fn save_cached_live_probe(
    project_dir: &Path,
    provider: ModelProvider,
    model: &str,
    auth_detail: &str,
) {
    let path = probe_cache_path(project_dir);
    let mut cache = load_probe_cache(&path).unwrap_or_default();
    cache.entries.retain(|entry| {
        !(entry.provider == provider.slug()
            && entry.model == model
            && entry.auth_detail == auth_detail)
    });
    cache.entries.push(CachedProbeEntry {
        provider: provider.slug().to_string(),
        model: model.to_string(),
        auth_detail: auth_detail.to_string(),
        checked_at: Utc::now(),
    });

    if let Some(parent) = path.parent() {
        let _ = fs::create_dir_all(parent);
    }
    if let Ok(content) = serde_json::to_string_pretty(&cache) {
        let _ = fs::write(path, content);
    }
}

fn load_probe_cache(path: &Path) -> Option<ProbeCache> {
    let content = fs::read_to_string(path).ok()?;
    serde_json::from_str(&content).ok()
}

fn readiness_summary(readiness: &ProviderReadiness) -> String {
    let summary = format!("{} - {}", readiness.short_label(), readiness.detail);
    if summary.len() > 78 {
        format!("{}...", truncate_str(&summary, 75))
    } else {
        summary
    }
}

fn header_readiness_label(readiness: &ProviderReadiness) -> String {
    if readiness.is_available() {
        return "ready".to_string();
    }

    let detail = readiness.detail.trim();
    let concise = detail
        .strip_prefix("missing required Claude features: ")
        .or_else(|| detail.strip_prefix("missing required Codex features: "))
        .or_else(|| detail.strip_prefix("authenticated but live Claude smoke failed: "))
        .or_else(|| detail.strip_prefix("authenticated but live Codex smoke failed: "))
        .or_else(|| detail.strip_prefix("Claude auth status check failed: "))
        .or_else(|| detail.strip_prefix("Codex login status check failed: "))
        .unwrap_or(detail);

    let label = if detail.contains("CLI not found in PATH") {
        "CLI missing".to_string()
    } else {
        concise.to_string()
    };

    if label.len() > 32 {
        format!("{}...", truncate_str(&label, 29))
    } else {
        label
    }
}

fn log_provider_probe(state: &mut StudioState, provider: ModelProvider) {
    let message = {
        let readiness = state.provider_readiness(provider);
        format!("{} {}", provider, readiness_summary(readiness))
    };
    state.log(message);
}

fn display_model_name(model: &str) -> &str {
    if model.trim().is_empty() {
        "<cli-default>"
    } else {
        model
    }
}

fn command_exists(command: &str) -> bool {
    std::process::Command::new("which")
        .arg(command)
        .output()
        .map(|output| output.status.success())
        .unwrap_or(false)
}

#[cfg(test)]
mod tests {
    use super::*;
    #[cfg(unix)]
    use std::os::unix::fs::symlink;
    use std::time::{SystemTime, UNIX_EPOCH};

    fn test_scan() -> ProjectScan {
        ProjectScan {
            generated_at: Utc::now(),
            top_level: vec!["src".into()],
            stack_signals: vec!["Rust".into()],
            data_candidates: vec!["metrics.json".into()],
            output_targets: vec!["public".into()],
        }
    }

    fn test_contract() -> ExecutionContract {
        ExecutionContract {
            file_name: "standard.md".into(),
            path: PathBuf::from("/tmp/project/.foundry/studio/contracts/standard.md"),
            name: "Standard Build Contract".into(),
            body: default_execution_contract_content().into(),
            attachments: Vec::new(),
        }
    }

    fn temp_test_dir(prefix: &str) -> PathBuf {
        let unique = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("system time before unix epoch")
            .as_nanos();
        std::env::temp_dir().join(format!("{}-{}", prefix, unique))
    }

    fn test_state() -> StudioState {
        StudioState {
            project_dir: PathBuf::from("/tmp/project"),
            prompt: DEFAULT_PROMPT.to_string(),
            is_editing_prompt: false,
            focused_pane: FocusedPane::Scan,
            provider_mode: ProviderMode::Claude,
            workspace_mode: WorkspaceMode::Isolated,
            scan: test_scan(),
            execution_contracts: vec![test_contract()],
            selected_execution_contract: 0,
            sessions: Vec::new(),
            selected_session: 0,
            output_scroll: 0,
            preview_scroll: 0,
            preview_cache: None,
            logs: Vec::new(),
            tick_count: 0,
            should_quit: false,
            shutdown_initiated: false,
            layout_config: StudioLayoutConfig::default(),
            active_resize: None,
            claude_model: "opus".into(),
            codex_model: String::new(),
            claude_readiness: ProviderReadiness::ready("ready"),
            codex_readiness: ProviderReadiness::missing("missing"),
            editor_choice: EditorChoice::System,
            session_controls: HashMap::new(),
            pending_action: None,
            editor_guide: None,
            delete_confirmation: None,
            attachment_manager: None,
        }
    }

    fn test_session(status: SessionStatus) -> SessionState {
        SessionState {
            id: "session".into(),
            provider: ModelProvider::Claude,
            model: "opus".into(),
            workspace_dir: PathBuf::from("/tmp/workspace"),
            artifact_dir: PathBuf::from("/tmp/workspace/.foundry/studio/artifacts/run/claude"),
            status,
            started_at: Utc::now(),
            output: Vec::new(),
            artifacts: Vec::new(),
            error: None,
            event_count: 0,
            last_event_at: None,
            prompt_path: None,
        }
    }

    #[test]
    fn smoothed_prompt_includes_artifact_contract() {
        let mut scan = test_scan();
        scan.top_level.push("Cargo.toml".into());

        let prompt = compose_smoothed_prompt(
            "Claude",
            "Build me a usage dashboard.",
            &test_contract(),
            &[],
            &scan,
            "/tmp/workspace",
            "/tmp/workspace/.foundry/studio/artifacts/run/claude",
            None,
        );

        assert!(prompt.contains("Build me a usage dashboard."));
        assert!(prompt.contains("BEGIN EXECUTION CONTRACT"));
        assert!(prompt.contains("/tmp/workspace/.foundry/studio/artifacts/run/claude"));
    }

    #[test]
    fn attachment_sidecar_path_rewrites_md_extension() {
        let contract_path = Path::new("/tmp/project/.foundry/studio/contracts/standard.md");
        assert_eq!(
            attachment_sidecar_path(contract_path),
            PathBuf::from("/tmp/project/.foundry/studio/contracts/standard.attachments.json")
        );
    }

    #[test]
    fn execution_contract_list_label_includes_attachment_count() {
        let mut contract = test_contract();
        assert_eq!(
            execution_contract_list_label(&contract),
            "Standard Build Contract"
        );

        contract.attachments = vec![
            AttachmentSpec {
                path: "docs/one.md".into(),
                mode: AttachmentMode::InlineFile,
                label: None,
            },
            AttachmentSpec {
                path: "docs/two.md".into(),
                mode: AttachmentMode::InlineFile,
                label: None,
            },
        ];
        assert_eq!(
            execution_contract_list_label(&contract),
            "Standard Build Contract [2 attached]"
        );
    }

    #[test]
    fn append_attachment_specs_for_paths_writes_relative_paths_and_modes() -> Result<()> {
        let project_dir = temp_test_dir("foundry-append-attachments");
        let contracts_dir = project_dir.join(STUDIO_ROOT_DIR).join(STUDIO_CONTRACTS_DIR);
        fs::create_dir_all(project_dir.join("docs"))?;
        fs::create_dir_all(&contracts_dir)?;
        fs::write(
            project_dir.join("Cargo.toml"),
            "[package]\nname = \"demo\"\n",
        )?;
        fs::write(project_dir.join("docs/readme.md"), "# Docs\n")?;
        let contract_path = contracts_dir.join("standard.md");
        fs::write(&contract_path, "# Standard Build Contract\n")?;

        let specs = append_attachment_specs_for_paths(
            &contract_path,
            &project_dir,
            &[project_dir.join("Cargo.toml"), project_dir.join("docs")],
        )?;
        let loaded_specs = load_attachment_specs(&contract_path);

        fs::remove_dir_all(&project_dir)?;
        assert_eq!(specs, loaded_specs);
        assert_eq!(specs.len(), 2);
        assert_eq!(specs[0].path, "Cargo.toml");
        assert_eq!(specs[0].mode, AttachmentMode::InlineFile);
        assert_eq!(specs[1].path, "docs");
        assert_eq!(specs[1].mode, AttachmentMode::DirectoryTree);
        Ok(())
    }

    #[test]
    fn load_attachment_specs_missing_file_returns_empty() -> Result<()> {
        let project_dir = temp_test_dir("foundry-attachment-missing");
        let contracts_dir = project_dir.join(STUDIO_ROOT_DIR).join(STUDIO_CONTRACTS_DIR);
        fs::create_dir_all(&contracts_dir)?;
        let contract_path = contracts_dir.join("standard.md");
        fs::write(&contract_path, "# Standard Build Contract\n")?;

        let specs = load_attachment_specs(&contract_path);

        fs::remove_dir_all(&project_dir)?;
        assert!(specs.is_empty());
        Ok(())
    }

    #[test]
    fn load_attachment_specs_malformed_json_returns_empty() -> Result<()> {
        let project_dir = temp_test_dir("foundry-attachment-malformed");
        let contracts_dir = project_dir.join(STUDIO_ROOT_DIR).join(STUDIO_CONTRACTS_DIR);
        fs::create_dir_all(&contracts_dir)?;
        let contract_path = contracts_dir.join("standard.md");
        fs::write(&contract_path, "# Standard Build Contract\n")?;
        fs::write(attachment_sidecar_path(&contract_path), "{not json")?;

        let specs = load_attachment_specs(&contract_path);

        fs::remove_dir_all(&project_dir)?;
        assert!(specs.is_empty());
        Ok(())
    }

    #[test]
    fn resolve_attachment_inline_file_reads_content() -> Result<()> {
        let project_dir = temp_test_dir("foundry-attachment-inline");
        fs::create_dir_all(project_dir.join("docs"))?;
        fs::write(project_dir.join("docs/api.md"), "# API\nline two\n")?;

        let resolved = resolve_attachment(
            &AttachmentSpec {
                path: "docs/api.md".into(),
                mode: AttachmentMode::InlineFile,
                label: None,
            },
            &project_dir,
        );

        fs::remove_dir_all(&project_dir)?;
        assert_eq!(resolved.label, "docs/api.md");
        assert!(resolved.content.contains("# API"));
        assert!(resolved.error.is_none());
        assert!(!resolved.truncated);
        Ok(())
    }

    #[test]
    fn resolve_attachment_rejects_absolute_path() -> Result<()> {
        let project_dir = temp_test_dir("foundry-attachment-absolute");
        fs::create_dir_all(&project_dir)?;

        let resolved = resolve_attachment(
            &AttachmentSpec {
                path: "/tmp/outside.md".into(),
                mode: AttachmentMode::InlineFile,
                label: None,
            },
            &project_dir,
        );

        fs::remove_dir_all(&project_dir)?;
        assert!(resolved.error.is_some());
        assert!(resolved
            .content
            .contains("absolute attachment paths are not supported"));
        Ok(())
    }

    #[test]
    fn resolve_attachment_rejects_escape_path() -> Result<()> {
        let temp_root = temp_test_dir("foundry-attachment-escape");
        let project_dir = temp_root.join("project");
        fs::create_dir_all(&project_dir)?;
        fs::write(temp_root.join("outside.md"), "secret\n")?;

        let resolved = resolve_attachment(
            &AttachmentSpec {
                path: "../outside.md".into(),
                mode: AttachmentMode::InlineFile,
                label: None,
            },
            &project_dir,
        );

        fs::remove_dir_all(&temp_root)?;
        assert!(resolved.error.is_some());
        assert!(resolved.content.contains("cannot contain '..' components"));
        Ok(())
    }

    #[cfg(unix)]
    #[test]
    fn resolve_attachment_rejects_symlink_escape() -> Result<()> {
        let temp_root = temp_test_dir("foundry-attachment-symlink");
        let project_dir = temp_root.join("project");
        fs::create_dir_all(&project_dir)?;
        let outside_path = temp_root.join("outside.md");
        fs::write(&outside_path, "secret\n")?;
        symlink(&outside_path, project_dir.join("leak.md"))?;

        let resolved = resolve_attachment(
            &AttachmentSpec {
                path: "leak.md".into(),
                mode: AttachmentMode::InlineFile,
                label: None,
            },
            &project_dir,
        );

        fs::remove_dir_all(&temp_root)?;
        assert!(resolved.error.is_some());
        assert!(resolved.content.contains("escapes the project root"));
        Ok(())
    }

    #[test]
    fn resolve_attachment_directory_tree_marks_snapshot_excluded_paths() -> Result<()> {
        let project_dir = temp_test_dir("foundry-attachment-tree");
        fs::create_dir_all(project_dir.join(".foundry/studio/logs"))?;
        fs::create_dir_all(project_dir.join("src"))?;
        fs::write(project_dir.join("src/main.rs"), "fn main() {}\n")?;
        fs::write(project_dir.join(".foundry/studio/logs/run.log"), "log\n")?;

        let resolved = resolve_attachment(
            &AttachmentSpec {
                path: ".".into(),
                mode: AttachmentMode::DirectoryTree,
                label: None,
            },
            &project_dir,
        );

        fs::remove_dir_all(&project_dir)?;
        assert!(resolved.error.is_none());
        assert!(resolved.content.contains("studio [snapshot-excluded]"));
        assert!(resolved.content.contains("src/"));
        Ok(())
    }

    #[test]
    fn resolve_attachment_inline_file_truncates_large_files() -> Result<()> {
        let project_dir = temp_test_dir("foundry-attachment-large-inline");
        fs::create_dir_all(project_dir.join("docs"))?;
        fs::write(
            project_dir.join("docs/big.txt"),
            "a".repeat(MAX_INLINE_FILE_BYTES + 1024),
        )?;

        let resolved = resolve_attachment(
            &AttachmentSpec {
                path: "docs/big.txt".into(),
                mode: AttachmentMode::InlineFile,
                label: None,
            },
            &project_dir,
        );

        fs::remove_dir_all(&project_dir)?;
        assert!(resolved.error.is_none());
        assert!(resolved.truncated);
        assert!(resolved.content.contains("file exceeds"));
        Ok(())
    }

    #[test]
    fn resolve_all_attachments_truncates_when_total_budget_is_exceeded() -> Result<()> {
        let project_dir = temp_test_dir("foundry-attachment-budget");
        fs::create_dir_all(project_dir.join("docs"))?;
        fs::write(project_dir.join("docs/one.txt"), "a".repeat(60_000))?;
        fs::write(project_dir.join("docs/two.txt"), "b".repeat(60_000))?;

        let resolved = resolve_all_attachments(
            &[
                AttachmentSpec {
                    path: "docs/one.txt".into(),
                    mode: AttachmentMode::InlineFile,
                    label: None,
                },
                AttachmentSpec {
                    path: "docs/two.txt".into(),
                    mode: AttachmentMode::InlineFile,
                    label: None,
                },
            ],
            &project_dir,
        );

        fs::remove_dir_all(&project_dir)?;
        assert_eq!(resolved.len(), 2);
        assert!(!resolved[0].truncated);
        assert!(resolved[1].truncated);
        assert!(resolved[1]
            .content
            .contains("total attachment size budget reached"));
        Ok(())
    }

    #[test]
    fn format_attachments_block_is_empty_for_no_attachments() {
        assert!(format_attachments_block(&[]).is_empty());
    }

    #[test]
    fn compose_smoothed_prompt_places_attachments_between_contract_and_scan() {
        let attachment = ResolvedAttachment {
            spec: AttachmentSpec {
                path: "docs/api.md".into(),
                mode: AttachmentMode::InlineFile,
                label: None,
            },
            label: "docs/api.md".into(),
            content: "# API".into(),
            truncated: false,
            error: None,
        };

        let prompt = compose_smoothed_prompt(
            "Claude",
            "Build me a usage dashboard.",
            &test_contract(),
            &[attachment],
            &test_scan(),
            "/tmp/workspace",
            "/tmp/workspace/.foundry/studio/artifacts/run/claude",
            None,
        );

        let contract_end = prompt
            .find("--- END EXECUTION CONTRACT ---")
            .expect("missing contract end marker");
        let attachment_start = prompt
            .find("--- BEGIN ATTACHMENT: docs/api.md")
            .expect("missing attachment block");
        let scan_start = prompt.find("Project scan:").expect("missing project scan");

        assert!(contract_end < attachment_start);
        assert!(attachment_start < scan_start);
    }

    #[test]
    fn preview_prompt_uses_cache_until_invalidated() -> Result<()> {
        let project_dir = temp_test_dir("foundry-preview-cache");
        fs::create_dir_all(project_dir.join("docs"))?;
        let attachment_path = project_dir.join("docs/api.md");
        fs::write(&attachment_path, "first version\n")?;

        let mut state = test_state();
        state.project_dir = project_dir.clone();
        state.execution_contracts = vec![ExecutionContract {
            file_name: "standard.md".into(),
            path: project_dir.join(".foundry/studio/contracts/standard.md"),
            name: "Standard Build Contract".into(),
            body: default_execution_contract_content().into(),
            attachments: vec![AttachmentSpec {
                path: "docs/api.md".into(),
                mode: AttachmentMode::InlineFile,
                label: None,
            }],
        }];

        let first = state.preview_prompt();
        fs::write(&attachment_path, "second version\n")?;
        let cached = state.preview_prompt();
        state.invalidate_preview_cache();
        let refreshed = state.preview_prompt();

        fs::remove_dir_all(&project_dir)?;
        assert!(first.contains("first version"));
        assert!(cached.contains("first version"));
        assert!(!cached.contains("second version"));
        assert!(refreshed.contains("second version"));
        Ok(())
    }

    #[test]
    fn snapshot_skip_rules_cover_foundry_studio() {
        assert!(should_skip_snapshot_path(Path::new(".git")));
        assert!(should_skip_snapshot_path(Path::new("target")));
        assert!(should_skip_snapshot_path(Path::new(".foundry/studio")));
        assert!(should_skip_snapshot_path(Path::new(".foundry/studio/logs")));
        assert!(!should_skip_snapshot_path(Path::new("src")));
    }

    #[test]
    fn project_scan_detects_stack_signals() -> Result<()> {
        let unique = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("system time before unix epoch")
            .as_nanos();
        let temp_dir = std::env::temp_dir().join(format!("foundry-studio-scan-{}", unique));
        fs::create_dir_all(temp_dir.join("src"))?;
        fs::write(temp_dir.join("Cargo.toml"), "[package]\nname = \"demo\"\n")?;
        fs::write(temp_dir.join("metrics.json"), "{}")?;
        fs::create_dir_all(temp_dir.join("public"))?;

        let scan = scan_project(&temp_dir)?;
        assert!(scan.stack_signals.iter().any(|item| item == "Rust"));
        assert!(scan
            .data_candidates
            .iter()
            .any(|item| item == "metrics.json"));
        assert!(scan.output_targets.iter().any(|item| item == "public"));

        fs::remove_dir_all(&temp_dir)?;
        Ok(())
    }

    #[test]
    fn codex_probe_accepts_required_exec_features() {
        let help = r#"
Run Codex non-interactively

Usage: codex exec [OPTIONS] [PROMPT] [COMMAND]

Options:
      --skip-git-repo-check
      --full-auto
      --json
  -o, --output-last-message <FILE>
"#;

        let readiness = assess_codex_exec_help(help);
        assert_eq!(readiness.state, ProviderState::Ready);
    }

    #[test]
    fn codex_probe_blocks_when_required_flag_is_missing() {
        let help = r#"
Run Codex non-interactively

Usage: codex exec [OPTIONS] [PROMPT] [COMMAND]

Options:
      --full-auto
      --json
"#;

        let readiness = assess_codex_exec_help(help);
        assert_eq!(readiness.state, ProviderState::Blocked);
        assert!(readiness.detail.contains("--output-last-message"));
        assert!(readiness.detail.contains("--skip-git-repo-check"));
    }

    #[test]
    fn claude_probe_accepts_required_help_features() {
        let help = r#"
Usage: claude [options] [command] [prompt]

Options:
  -p, --print
  --output-format <format> text json stream-json
  --verbose
  --dangerously-skip-permissions
"#;

        let readiness = assess_claude_help(help);
        assert_eq!(readiness.state, ProviderState::Ready);
    }

    #[test]
    fn claude_probe_blocks_when_stream_json_support_is_missing() {
        let help = r#"
Usage: claude [options] [command] [prompt]

Options:
  -p, --print
  --output-format <format> text json
"#;

        let readiness = assess_claude_help(help);
        assert_eq!(readiness.state, ProviderState::Blocked);
        assert!(readiness.detail.contains("stream-json"));
        assert!(readiness.detail.contains("--verbose"));
        assert!(readiness.detail.contains("--dangerously-skip-permissions"));
    }

    #[test]
    fn default_provider_mode_prefers_claude_when_nothing_is_ready() {
        let claude = ProviderReadiness::missing("claude missing");
        let codex = ProviderReadiness::missing("codex missing");

        assert_eq!(default_provider_mode(&claude, &codex), ProviderMode::Claude);
    }

    #[test]
    fn header_readiness_label_shows_real_auth_reason() {
        let readiness = ProviderReadiness::blocked("not logged in");
        assert_eq!(header_readiness_label(&readiness), "not logged in");
    }

    #[test]
    fn header_readiness_label_strips_verbose_feature_prefix() {
        let readiness = ProviderReadiness::blocked(
            "missing required Claude features: stream-json, --verbose, --dangerously-skip-permissions",
        );
        assert!(header_readiness_label(&readiness).contains("stream-json"));
    }

    #[test]
    fn header_readiness_label_keeps_ready_short() {
        let readiness = ProviderReadiness::ready("authenticated; live smoke OK");
        assert_eq!(header_readiness_label(&readiness), "ready");
    }

    #[test]
    fn claude_live_probe_parser_accepts_result_event() {
        let output = r#"{"type":"result","result":"OK"}"#;
        assert!(claude_probe_output_contains_ok(output));
    }

    #[test]
    fn live_probe_cache_round_trip() -> Result<()> {
        let unique = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("system time before unix epoch")
            .as_nanos();
        let project_dir = std::env::temp_dir().join(format!("foundry-probe-cache-{}", unique));
        fs::create_dir_all(project_dir.join(STUDIO_ROOT_DIR))?;

        save_cached_live_probe(
            &project_dir,
            ModelProvider::Claude,
            "opus",
            "api-key / firstParty",
        );

        let cached = load_cached_live_probe(
            &project_dir,
            ModelProvider::Claude,
            "opus",
            "api-key / firstParty",
        );
        fs::remove_dir_all(&project_dir)?;

        assert!(cached.is_some());
        assert!(cached.unwrap_or_default().contains("cached live smoke OK"));
        Ok(())
    }

    #[test]
    fn focused_pane_cycles_forward_and_backward() {
        assert_eq!(FocusedPane::Scan.next(), FocusedPane::Prompt);
        assert_eq!(FocusedPane::Prompt.next(), FocusedPane::Contracts);
        assert_eq!(FocusedPane::Contracts.previous(), FocusedPane::Prompt);
        assert_eq!(FocusedPane::Activity.next(), FocusedPane::Scan);
        assert_eq!(FocusedPane::Scan.previous(), FocusedPane::Activity);
    }

    #[test]
    fn pane_hit_testing_maps_points_to_expected_panes() {
        let layout = studio_layout(Rect::new(0, 0, 120, 40), StudioLayoutConfig::default());

        assert_eq!(
            pane_at_position(&layout, layout.scan.x + 1, layout.scan.y + 1),
            Some(FocusedPane::Scan)
        );
        assert_eq!(
            pane_at_position(&layout, layout.contracts.x + 1, layout.contracts.y + 1),
            Some(FocusedPane::Contracts)
        );
        assert_eq!(
            pane_at_position(
                &layout,
                layout.execution_brief.x + 1,
                layout.execution_brief.y + 1
            ),
            Some(FocusedPane::ExecutionBrief)
        );
        assert_eq!(
            pane_at_position(&layout, layout.output.x + 1, layout.output.y + 1),
            Some(FocusedPane::Output)
        );
        assert_eq!(pane_at_position(&layout, 0, 0), None);
    }

    #[test]
    fn quit_key_supports_q_and_ctrl_c() {
        let plain_q = event::KeyEvent::new(KeyCode::Char('q'), KeyModifiers::NONE);
        let ctrl_c = event::KeyEvent::new(KeyCode::Char('c'), KeyModifiers::CONTROL);
        let plain_c = event::KeyEvent::new(KeyCode::Char('c'), KeyModifiers::NONE);

        assert!(is_quit_key(plain_q));
        assert!(is_quit_key(ctrl_c));
        assert!(!is_quit_key(plain_c));
    }

    #[test]
    fn clicking_prompt_enters_prompt_edit_mode() {
        let mut state = test_state();

        activate_pane_from_click(
            &mut state,
            FocusedPane::Prompt,
            Rect::default(),
            Rect::default(),
            0,
        );

        assert_eq!(state.focused_pane, FocusedPane::Prompt);
        assert!(state.is_editing_prompt);
    }

    #[test]
    fn queue_editor_action_opens_guide_instead_of_immediate_launch() {
        let mut state = test_state();

        queue_editor_action(
            &mut state,
            PendingStudioAction::EditExecutionContract {
                path: PathBuf::from("/tmp/contract.md"),
                action_label: "contract",
            },
        );

        assert!(state.editor_guide.is_some());
        assert!(state.pending_action.is_none());
    }

    #[test]
    fn editor_guide_can_cycle_editor_choice() {
        let mut state = test_state();

        queue_editor_action(
            &mut state,
            PendingStudioAction::EditExecutionContract {
                path: PathBuf::from("/tmp/contract.md"),
                action_label: "contract",
            },
        );

        handle_editor_guide_key(
            &mut state,
            event::KeyEvent::new(KeyCode::Char('v'), KeyModifiers::NONE),
        );

        assert_eq!(state.editor_choice, EditorChoice::Nano);
        assert!(state.editor_guide.is_some());
    }

    #[test]
    fn request_delete_opens_confirmation() {
        let mut state = test_state();
        state.execution_contracts.push(ExecutionContract {
            file_name: "reporting.md".into(),
            path: PathBuf::from("/tmp/project/.foundry/studio/contracts/reporting.md"),
            name: "Reporting Contract".into(),
            body: "# Reporting Contract".into(),
            attachments: Vec::new(),
        });
        state.selected_execution_contract = 1;

        request_delete_selected_execution_contract(&mut state);

        assert!(state.delete_confirmation.is_some());
    }

    #[test]
    fn resize_handle_hit_testing_identifies_all_splitters() {
        let layout = studio_layout(Rect::new(0, 0, 120, 40), StudioLayoutConfig::default());

        assert_eq!(
            resize_handle_at(&layout, layout.column_split.x, layout.column_split.y + 1),
            Some(ResizeHandle::ColumnSplit)
        );
        assert_eq!(
            resize_handle_at(
                &layout,
                layout.left_scan_prompt_split.x + 1,
                layout.left_scan_prompt_split.y,
            ),
            Some(ResizeHandle::LeftScanPrompt)
        );
        assert_eq!(
            resize_handle_at(
                &layout,
                layout.left_prompt_contracts_split.x + 1,
                layout.left_prompt_contracts_split.y,
            ),
            Some(ResizeHandle::LeftPromptContracts)
        );
        assert_eq!(
            resize_handle_at(
                &layout,
                layout.left_contracts_brief_split.x + 1,
                layout.left_contracts_brief_split.y,
            ),
            Some(ResizeHandle::LeftContractsBrief)
        );
        assert_eq!(
            resize_handle_at(
                &layout,
                layout.right_sessions_output_split.x + 1,
                layout.right_sessions_output_split.y,
            ),
            Some(ResizeHandle::RightSessionsOutput)
        );
        assert_eq!(
            resize_handle_at(
                &layout,
                layout.right_output_activity_split.x + 1,
                layout.right_output_activity_split.y,
            ),
            Some(ResizeHandle::RightOutputActivity)
        );
        assert_eq!(
            resize_handle_at(&layout, layout.scan.x + 2, layout.scan.y + 2),
            None
        );
    }

    #[test]
    fn column_split_hit_testing_respects_grab_zone_boundaries() {
        let layout = studio_layout(Rect::new(0, 0, 120, 40), StudioLayoutConfig::default());

        assert_eq!(
            resize_handle_at(
                &layout,
                layout
                    .column_split
                    .x
                    .saturating_sub(COLUMN_RESIZE_HIT_MARGIN),
                layout.column_split.y + 1,
            ),
            Some(ResizeHandle::ColumnSplit)
        );
        assert_eq!(
            resize_handle_at(
                &layout,
                layout
                    .column_split
                    .x
                    .saturating_add(COLUMN_RESIZE_HIT_MARGIN),
                layout.column_split.y + 1,
            ),
            Some(ResizeHandle::ColumnSplit)
        );
        assert_eq!(
            resize_handle_at(
                &layout,
                layout
                    .column_split
                    .x
                    .saturating_sub(COLUMN_RESIZE_HIT_MARGIN.saturating_add(1)),
                layout.column_split.y + 1,
            ),
            None
        );
        assert_eq!(
            resize_handle_at(
                &layout,
                layout
                    .column_split
                    .x
                    .saturating_add(COLUMN_RESIZE_HIT_MARGIN.saturating_add(1)),
                layout.column_split.y + 1,
            ),
            None
        );
    }

    #[test]
    fn dragging_column_split_updates_layout_width() {
        let mut state = test_state();
        let layout = studio_layout(Rect::new(0, 0, 120, 40), state.layout_config);
        let drag = ResizeDragState {
            handle: ResizeHandle::ColumnSplit,
            start_column: layout.column_split.x,
            start_row: layout.column_split.y,
            initial_layout: state.layout_config,
        };

        apply_resize_drag(
            &mut state,
            &layout,
            drag,
            layout.column_split.x.saturating_add(8),
            layout.column_split.y,
        );

        assert!(state.layout_config.left_column_percent > DEFAULT_LEFT_COLUMN_PERCENT);
    }

    #[test]
    fn scrolling_preview_updates_preview_scroll() {
        let mut state = test_state();
        state.prompt = (0..40)
            .map(|idx| format!("line {}", idx))
            .collect::<Vec<_>>()
            .join("\n");
        let area = Rect::new(0, 0, 30, 8);

        scroll_preview(&mut state, area, 3);
        assert!(state.preview_scroll > 0);

        scroll_preview(&mut state, area, -3);
        assert_eq!(state.preview_scroll, 0);
    }

    #[test]
    fn cycling_execution_contract_resets_preview_scroll() {
        let mut state = test_state();
        state.execution_contracts.push(ExecutionContract {
            file_name: "reporting.md".into(),
            path: PathBuf::from("/tmp/project/.foundry/studio/contracts/reporting.md"),
            name: "Reporting Contract".into(),
            body: "# Reporting Contract".into(),
            attachments: Vec::new(),
        });
        state.preview_scroll = 9;

        cycle_execution_contract(&mut state, true);

        assert_eq!(state.selected_execution_contract, 1);
        assert_eq!(state.preview_scroll, 0);
    }

    #[test]
    fn dragging_scan_prompt_split_updates_scan_height() {
        let mut state = test_state();
        let layout = studio_layout(Rect::new(0, 0, 120, 40), state.layout_config);
        let drag = ResizeDragState {
            handle: ResizeHandle::LeftScanPrompt,
            start_column: layout.left_scan_prompt_split.x + 1,
            start_row: layout.left_scan_prompt_split.y,
            initial_layout: state.layout_config,
        };

        apply_resize_drag(
            &mut state,
            &layout,
            drag,
            layout.left_scan_prompt_split.x + 1,
            layout.left_scan_prompt_split.y.saturating_add(2),
        );

        assert!(state.layout_config.left_scan_height > DEFAULT_LEFT_SCAN_HEIGHT);
    }

    #[test]
    fn dragging_prompt_contracts_split_updates_prompt_height() {
        let mut state = test_state();
        let layout = studio_layout(Rect::new(0, 0, 120, 40), state.layout_config);
        let drag = ResizeDragState {
            handle: ResizeHandle::LeftPromptContracts,
            start_column: layout.left_prompt_contracts_split.x + 1,
            start_row: layout.left_prompt_contracts_split.y,
            initial_layout: state.layout_config,
        };

        apply_resize_drag(
            &mut state,
            &layout,
            drag,
            layout.left_prompt_contracts_split.x + 1,
            layout.left_prompt_contracts_split.y.saturating_add(2),
        );

        assert!(state.layout_config.left_prompt_height > DEFAULT_LEFT_PROMPT_HEIGHT);
    }

    #[test]
    fn dragging_contracts_brief_split_updates_contracts_height() {
        let mut state = test_state();
        let layout = studio_layout(Rect::new(0, 0, 120, 40), state.layout_config);
        let drag = ResizeDragState {
            handle: ResizeHandle::LeftContractsBrief,
            start_column: layout.left_contracts_brief_split.x + 1,
            start_row: layout.left_contracts_brief_split.y,
            initial_layout: state.layout_config,
        };

        apply_resize_drag(
            &mut state,
            &layout,
            drag,
            layout.left_contracts_brief_split.x + 1,
            layout.left_contracts_brief_split.y.saturating_add(2),
        );

        assert!(state.layout_config.left_contracts_height > DEFAULT_LEFT_CONTRACTS_HEIGHT);
    }

    #[test]
    fn dragging_sessions_output_split_updates_sessions_height() {
        let mut state = test_state();
        let layout = studio_layout(Rect::new(0, 0, 120, 40), state.layout_config);
        let drag = ResizeDragState {
            handle: ResizeHandle::RightSessionsOutput,
            start_column: layout.right_sessions_output_split.x + 1,
            start_row: layout.right_sessions_output_split.y,
            initial_layout: state.layout_config,
        };

        apply_resize_drag(
            &mut state,
            &layout,
            drag,
            layout.right_sessions_output_split.x + 1,
            layout.right_sessions_output_split.y.saturating_add(2),
        );

        assert!(state.layout_config.right_sessions_height > DEFAULT_RIGHT_SESSIONS_HEIGHT);
    }

    #[test]
    fn dragging_output_activity_split_down_shrinks_activity_height() {
        let mut state = test_state();
        let layout = studio_layout(Rect::new(0, 0, 120, 40), state.layout_config);
        let drag = ResizeDragState {
            handle: ResizeHandle::RightOutputActivity,
            start_column: layout.right_output_activity_split.x + 1,
            start_row: layout.right_output_activity_split.y,
            initial_layout: state.layout_config,
        };

        apply_resize_drag(
            &mut state,
            &layout,
            drag,
            layout.right_output_activity_split.x + 1,
            layout.right_output_activity_split.y.saturating_add(2),
        );

        assert!(state.layout_config.right_activity_height < DEFAULT_RIGHT_ACTIVITY_HEIGHT);
    }

    #[test]
    fn dragging_output_activity_split_up_grows_activity_height() {
        let mut state = test_state();
        let layout = studio_layout(Rect::new(0, 0, 120, 40), state.layout_config);
        let drag = ResizeDragState {
            handle: ResizeHandle::RightOutputActivity,
            start_column: layout.right_output_activity_split.x + 1,
            start_row: layout.right_output_activity_split.y,
            initial_layout: state.layout_config,
        };

        apply_resize_drag(
            &mut state,
            &layout,
            drag,
            layout.right_output_activity_split.x + 1,
            layout.right_output_activity_split.y.saturating_sub(2),
        );

        assert!(state.layout_config.right_activity_height > DEFAULT_RIGHT_ACTIVITY_HEIGHT);
    }

    #[test]
    fn arrow_keys_move_contract_selection_when_contracts_pane_is_focused() {
        let mut state = test_state();
        state.focused_pane = FocusedPane::Contracts;
        state.execution_contracts.push(ExecutionContract {
            file_name: "reporting.md".into(),
            path: PathBuf::from("/tmp/project/.foundry/studio/contracts/reporting.md"),
            name: "Reporting Contract".into(),
            body: "# Reporting Contract".into(),
            attachments: Vec::new(),
        });

        let (tx, _rx) = mpsc::unbounded_channel();
        handle_global_key(
            &mut state,
            event::KeyEvent::new(KeyCode::Down, KeyModifiers::NONE),
            &tx,
        );
        assert_eq!(state.selected_execution_contract, 1);

        handle_global_key(
            &mut state,
            event::KeyEvent::new(KeyCode::Up, KeyModifiers::NONE),
            &tx,
        );
        assert_eq!(state.selected_execution_contract, 0);
    }

    #[test]
    fn enter_edits_selected_contract_when_contracts_pane_is_focused() {
        let mut state = test_state();
        state.focused_pane = FocusedPane::Contracts;

        let (tx, _rx) = mpsc::unbounded_channel();
        handle_global_key(
            &mut state,
            event::KeyEvent::new(KeyCode::Enter, KeyModifiers::NONE),
            &tx,
        );

        assert!(state.editor_guide.is_some());
        assert_eq!(state.focused_pane, FocusedPane::Contracts);
    }

    #[test]
    fn t_opens_attachment_manager_when_contracts_pane_is_focused() -> Result<()> {
        let project_dir = temp_test_dir("foundry-edit-attachments-keybind");
        fs::create_dir_all(project_dir.join(STUDIO_ROOT_DIR))?;

        let mut state = test_state();
        state.project_dir = project_dir.clone();
        let (contracts, selected_index) = load_execution_contracts(&project_dir)?;
        state.execution_contracts = contracts;
        state.selected_execution_contract = selected_index;
        state.focused_pane = FocusedPane::Contracts;

        let (tx, _rx) = mpsc::unbounded_channel();
        handle_global_key(
            &mut state,
            event::KeyEvent::new(KeyCode::Char('t'), KeyModifiers::NONE),
            &tx,
        );

        assert!(state.attachment_manager.is_some());
        assert!(state.pending_action.is_none());
        assert!(state.editor_guide.is_none());
        assert_eq!(state.focused_pane, FocusedPane::Contracts);

        fs::remove_dir_all(&project_dir)?;
        Ok(())
    }

    #[cfg(target_os = "macos")]
    #[test]
    fn attachment_manager_a_queues_picker_on_macos() -> Result<()> {
        let project_dir = temp_test_dir("foundry-attachment-manager-add");
        fs::create_dir_all(project_dir.join(STUDIO_ROOT_DIR))?;

        let mut state = test_state();
        state.project_dir = project_dir.clone();
        let (contracts, selected_index) = load_execution_contracts(&project_dir)?;
        state.execution_contracts = contracts;
        state.selected_execution_contract = selected_index;
        state.focused_pane = FocusedPane::Contracts;
        open_attachment_manager(&mut state);

        let selected_contract_path = state.selected_execution_contract().path.clone();
        handle_attachment_manager_key(
            &mut state,
            event::KeyEvent::new(KeyCode::Char('a'), KeyModifiers::NONE),
        );

        match state
            .pending_action
            .as_ref()
            .expect("pending picker action")
        {
            PendingStudioAction::PickExecutionContractAttachment { contract_path } => {
                assert_eq!(contract_path, &selected_contract_path);
            }
            PendingStudioAction::EditExecutionContract { .. } => {
                panic!("expected native picker action");
            }
        }
        assert!(state.attachment_manager.is_some());

        fs::remove_dir_all(&project_dir)?;
        Ok(())
    }

    #[cfg(not(target_os = "macos"))]
    #[test]
    fn attachment_manager_a_opens_editor_on_non_macos() -> Result<()> {
        let project_dir = temp_test_dir("foundry-attachment-manager-add");
        fs::create_dir_all(project_dir.join(STUDIO_ROOT_DIR))?;

        let mut state = test_state();
        state.project_dir = project_dir.clone();
        let (contracts, selected_index) = load_execution_contracts(&project_dir)?;
        state.execution_contracts = contracts;
        state.selected_execution_contract = selected_index;
        state.focused_pane = FocusedPane::Contracts;
        open_attachment_manager(&mut state);

        let sidecar_path = attachment_sidecar_path(&state.selected_execution_contract().path);
        handle_attachment_manager_key(
            &mut state,
            event::KeyEvent::new(KeyCode::Char('a'), KeyModifiers::NONE),
        );

        let guide = state
            .editor_guide
            .as_ref()
            .expect("editor guide should be open");
        match &guide.action {
            PendingStudioAction::EditExecutionContract { path, action_label } => {
                assert_eq!(path, &sidecar_path);
                assert_eq!(*action_label, "contract attachments");
            }
            PendingStudioAction::PickExecutionContractAttachment { .. } => {
                panic!("expected editor fallback action");
            }
        }
        assert!(state.attachment_manager.is_some());

        fs::remove_dir_all(&project_dir)?;
        Ok(())
    }

    #[test]
    fn attachment_manager_d_removes_only_marked_attachments() -> Result<()> {
        let project_dir = temp_test_dir("foundry-attachment-manager-delete");
        let contracts_dir = project_dir.join(STUDIO_ROOT_DIR).join(STUDIO_CONTRACTS_DIR);
        fs::create_dir_all(&contracts_dir)?;
        let contract_path = contracts_dir.join("standard.md");
        fs::write(&contract_path, "# Standard Build Contract\n")?;
        persist_attachment_specs(
            &contract_path,
            &[
                AttachmentSpec {
                    path: "Cargo.toml".into(),
                    mode: AttachmentMode::InlineFile,
                    label: None,
                },
                AttachmentSpec {
                    path: "src".into(),
                    mode: AttachmentMode::DirectoryTree,
                    label: None,
                },
            ],
        )?;

        let mut state = test_state();
        state.project_dir = project_dir.clone();
        let (contracts, selected_index) = load_execution_contracts(&project_dir)?;
        state.execution_contracts = contracts;
        state.selected_execution_contract = selected_index;
        open_attachment_manager(&mut state);
        handle_attachment_manager_key(
            &mut state,
            event::KeyEvent::new(KeyCode::Char(' '), KeyModifiers::NONE),
        );
        handle_attachment_manager_key(
            &mut state,
            event::KeyEvent::new(KeyCode::Down, KeyModifiers::NONE),
        );
        handle_attachment_manager_key(
            &mut state,
            event::KeyEvent::new(KeyCode::Char('d'), KeyModifiers::NONE),
        );

        let remaining = load_attachment_specs(&contract_path);
        fs::remove_dir_all(&project_dir)?;
        assert_eq!(remaining.len(), 1);
        assert_eq!(remaining[0].path, "src");
        assert!(state.attachment_manager.is_some());
        assert!(state
            .logs
            .last()
            .is_some_and(|(_, line)| { line.contains("removed 1 attachment(s): Cargo.toml") }));
        Ok(())
    }

    #[test]
    fn attachment_manager_d_removes_selected_and_clamps_selection_when_unmarked() -> Result<()> {
        let project_dir = temp_test_dir("foundry-attachment-manager-delete-selected");
        let contracts_dir = project_dir.join(STUDIO_ROOT_DIR).join(STUDIO_CONTRACTS_DIR);
        fs::create_dir_all(&contracts_dir)?;
        let contract_path = contracts_dir.join("standard.md");
        fs::write(&contract_path, "# Standard Build Contract\n")?;
        persist_attachment_specs(
            &contract_path,
            &[
                AttachmentSpec {
                    path: "Cargo.toml".into(),
                    mode: AttachmentMode::InlineFile,
                    label: None,
                },
                AttachmentSpec {
                    path: "src".into(),
                    mode: AttachmentMode::DirectoryTree,
                    label: None,
                },
            ],
        )?;

        let mut state = test_state();
        state.project_dir = project_dir.clone();
        let (contracts, selected_index) = load_execution_contracts(&project_dir)?;
        state.execution_contracts = contracts;
        state.selected_execution_contract = selected_index;
        open_attachment_manager(&mut state);
        handle_attachment_manager_key(
            &mut state,
            event::KeyEvent::new(KeyCode::Down, KeyModifiers::NONE),
        );
        handle_attachment_manager_key(
            &mut state,
            event::KeyEvent::new(KeyCode::Char('d'), KeyModifiers::NONE),
        );

        let remaining = load_attachment_specs(&contract_path);
        let selected_attachment = state
            .attachment_manager
            .as_ref()
            .map(|manager| manager.selected_attachment)
            .unwrap_or(usize::MAX);
        fs::remove_dir_all(&project_dir)?;
        assert_eq!(remaining.len(), 1);
        assert_eq!(remaining[0].path, "Cargo.toml");
        assert_eq!(selected_attachment, 0);
        Ok(())
    }

    #[test]
    fn delete_confirmation_can_cancel() {
        let mut state = test_state();
        state.delete_confirmation = Some(DeleteConfirmationState {
            contract_name: "Standard Build Contract".into(),
        });

        handle_delete_confirmation_key(
            &mut state,
            event::KeyEvent::new(KeyCode::Char('n'), KeyModifiers::NONE),
        );

        assert!(state.delete_confirmation.is_none());
    }

    #[test]
    fn execution_contract_body_renders_placeholders() {
        let rendered = render_execution_contract_body(
            "use {{provider_label}} in {{workspace_dir}} and write to {{artifact_dir}}",
            "Claude",
            "/tmp/workspace",
            "/tmp/artifacts",
        );

        assert!(rendered.contains("Claude"));
        assert!(rendered.contains("/tmp/workspace"));
        assert!(rendered.contains("/tmp/artifacts"));
    }

    #[test]
    fn load_execution_contracts_bootstraps_default_contract() -> Result<()> {
        let unique = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("system time before unix epoch")
            .as_nanos();
        let project_dir = std::env::temp_dir().join(format!("foundry-studio-contracts-{}", unique));
        fs::create_dir_all(&project_dir)?;

        let (contracts, selected) = load_execution_contracts(&project_dir)?;
        fs::remove_dir_all(&project_dir)?;

        assert_eq!(selected, 0);
        assert_eq!(contracts.len(), 1);
        assert_eq!(contracts[0].file_name, "standard.md");
        Ok(())
    }

    #[test]
    fn create_execution_contract_creates_empty_attachment_sidecar() -> Result<()> {
        let project_dir = temp_test_dir("foundry-create-contract-sidecar");
        fs::create_dir_all(project_dir.join(STUDIO_ROOT_DIR))?;

        let mut state = test_state();
        state.project_dir = project_dir.clone();
        let (contracts, selected_index) = load_execution_contracts(&project_dir)?;
        state.execution_contracts = contracts;
        state.selected_execution_contract = selected_index;

        create_execution_contract(&mut state)?;

        let sidecar_path = attachment_sidecar_path(&state.selected_execution_contract().path);
        let sidecar = fs::read_to_string(&sidecar_path)?;

        fs::remove_dir_all(&project_dir)?;
        assert_eq!(sidecar, "[]\n");
        Ok(())
    }

    #[test]
    fn editor_choice_persists_round_trip() -> Result<()> {
        let unique = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("system time before unix epoch")
            .as_nanos();
        let project_dir = std::env::temp_dir().join(format!("foundry-studio-editor-{}", unique));
        fs::create_dir_all(project_dir.join(STUDIO_ROOT_DIR))?;

        persist_editor_choice(&project_dir, EditorChoice::Nano)?;
        let loaded = load_editor_choice(&project_dir);
        fs::remove_dir_all(&project_dir)?;

        assert_eq!(loaded, EditorChoice::Nano);
        Ok(())
    }

    #[test]
    fn delete_confirmation_yes_deletes_selected_contract() -> Result<()> {
        let unique = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("system time before unix epoch")
            .as_nanos();
        let project_dir =
            std::env::temp_dir().join(format!("foundry-studio-delete-confirm-{}", unique));
        let contracts_dir = project_dir.join(STUDIO_ROOT_DIR).join(STUDIO_CONTRACTS_DIR);
        fs::create_dir_all(&contracts_dir)?;
        fs::write(
            contracts_dir.join("standard.md"),
            "# Standard Build Contract\n",
        )?;
        fs::write(contracts_dir.join("reporting.md"), "# Reporting Contract\n")?;
        fs::write(
            contracts_dir.join("reporting.attachments.json"),
            r#"[{"path":"docs/report.md","mode":"inline_file"}]"#,
        )?;

        let (contracts, selected_index) =
            load_execution_contracts_with_selection(&project_dir, Some("reporting.md"))?;
        let mut state = test_state();
        state.project_dir = project_dir.clone();
        state.execution_contracts = contracts;
        state.selected_execution_contract = selected_index;
        state.delete_confirmation = Some(DeleteConfirmationState {
            contract_name: "Reporting Contract".into(),
        });

        handle_delete_confirmation_key(
            &mut state,
            event::KeyEvent::new(KeyCode::Char('y'), KeyModifiers::NONE),
        );

        assert!(state.delete_confirmation.is_none());
        assert_eq!(state.execution_contracts.len(), 1);
        assert_eq!(state.execution_contracts[0].file_name, "standard.md");
        assert!(contracts_dir.join(".trash").exists());
        assert!(!contracts_dir.join("reporting.attachments.json").exists());
        let trashed_entries = fs::read_dir(contracts_dir.join(".trash"))?
            .filter_map(|entry| entry.ok())
            .map(|entry| entry.file_name().to_string_lossy().to_string())
            .collect::<Vec<_>>();
        assert!(trashed_entries
            .iter()
            .any(|name| name.ends_with("reporting.attachments.json")));

        fs::remove_dir_all(&project_dir)?;
        Ok(())
    }

    #[test]
    fn clicking_contract_row_selects_it() {
        let mut state = test_state();
        state.execution_contracts.push(ExecutionContract {
            file_name: "reporting.md".into(),
            path: PathBuf::from("/tmp/project/.foundry/studio/contracts/reporting.md"),
            name: "Reporting Contract".into(),
            body: "# Reporting Contract".into(),
            attachments: Vec::new(),
        });
        let area = Rect::new(0, 0, 40, 8);

        select_execution_contract_from_click(&mut state, area, area.y + 3);

        assert_eq!(state.selected_execution_contract, 1);
    }

    #[test]
    fn quit_event_sets_should_quit() {
        let mut state = test_state();
        let (tx, _rx) = mpsc::unbounded_channel();

        handle_event(&mut state, StudioEvent::Quit, &tx);

        assert!(state.should_quit);
    }

    #[test]
    fn follow_up_context_is_capped_by_character_budget() {
        let mut session = test_session(SessionStatus::Succeeded);
        session.output = vec![
            "older line".into(),
            "x".repeat(FOLLOW_UP_CONTEXT_MAX_CHARS),
            "latest line".into(),
        ];

        let context = follow_up_context(&session);
        assert!(context.len() <= FOLLOW_UP_CONTEXT_MAX_CHARS);
        assert!(context.contains("latest line"));
    }

    #[test]
    fn follow_up_workspace_issue_detects_missing_path() {
        let missing = std::env::temp_dir().join(format!(
            "foundry-missing-workspace-{}",
            Utc::now().timestamp_nanos_opt().unwrap_or_default()
        ));
        let issue = follow_up_workspace_issue(&missing);
        assert!(issue.is_some());
        assert!(issue.unwrap_or_default().contains("no longer exists"));
    }

    #[tokio::test]
    async fn request_quit_cancels_running_sessions_and_drains_handles() {
        let mut state = test_state();
        let cancel_flag = Arc::new(AtomicBool::new(false));
        let task_flag = cancel_flag.clone();
        let task = tokio::spawn(async move {
            while !task_flag.load(Ordering::Relaxed) {
                tokio::task::yield_now().await;
            }
        });
        state.session_controls.insert(
            "session".into(),
            SessionControl {
                cancel_flag: cancel_flag.clone(),
                task,
            },
        );
        state.sessions.push(test_session(SessionStatus::Running));

        request_quit(&mut state);

        assert!(state.should_quit);
        assert!(state.shutdown_initiated);
        assert!(cancel_flag.load(Ordering::Relaxed));

        shutdown_active_sessions(&mut state).await;
        assert!(state.session_controls.is_empty());
    }
}
