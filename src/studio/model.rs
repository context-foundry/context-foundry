use chrono::{DateTime, Utc};
use crossterm::event::{self, MouseEvent};
use ratatui::style::{Color, Style};
use serde::{Deserialize, Serialize};
use std::path::PathBuf;

use crate::agent::{AgentOutputEvent, ModelProvider};

use super::{attachments::AttachmentSpec, scan::ProjectScan};

pub(super) const STUDIO_ROOT_DIR: &str = ".foundry/studio";
pub(super) const STUDIO_CONTRACTS_DIR: &str = "contracts";
pub(super) const STUDIO_SELECTED_CONTRACT_FILE: &str = ".selected";
pub(super) const STUDIO_SELECTED_EDITOR_FILE: &str = ".editor";
pub(super) const STUDIO_PROMPT_HISTORY_FILE: &str = "prompt-history.json";
pub(super) const DEFAULT_PROMPT: &str = "";
pub(super) const MAX_PROMPT_HISTORY_ENTRIES: usize = 200;
pub(super) const LIVE_PROBE_TTL_SECS: i64 = 900;
pub(super) const LIVE_PROBE_TIMEOUT_SECS: u64 = 20;
pub(super) const FOLLOW_UP_CONTEXT_MAX_LINES: usize = 120;
pub(super) const FOLLOW_UP_CONTEXT_MAX_CHARS: usize = 12_000;
pub(super) const SHUTDOWN_GRACE_MILLIS: u64 = 1500;
pub(super) const MAX_PROMPT_BYTES: usize = 256 * 1024;
pub(super) const MAX_PROMPT_RENDER_BYTES: usize = 16 * 1024;
pub(super) const MAX_PREVIEW_RENDER_BYTES: usize = 32 * 1024;
pub(super) const DEFAULT_LEFT_COLUMN_PERCENT: u16 = 44;
pub(super) const DEFAULT_LEFT_SCAN_HEIGHT: u16 = 6;
pub(super) const DEFAULT_LEFT_PROMPT_HEIGHT: u16 = 8;
pub(super) const DEFAULT_LEFT_CONTRACTS_HEIGHT: u16 = 8;
pub(super) const DEFAULT_RIGHT_SESSIONS_HEIGHT: u16 = 8;
pub(super) const DEFAULT_RIGHT_ACTIVITY_HEIGHT: u16 = 10;
pub(super) const MIN_LEFT_COLUMN_WIDTH: u16 = 28;
pub(super) const MIN_RIGHT_COLUMN_WIDTH: u16 = 36;
pub(super) const MIN_LEFT_SECTION_HEIGHT: u16 = 5;
pub(super) const MIN_LEFT_BRIEF_HEIGHT: u16 = 8;
pub(super) const MIN_RIGHT_SECTION_HEIGHT: u16 = 5;
pub(super) const MIN_OUTPUT_HEIGHT: u16 = 8;
pub(super) const COLUMN_SPLIT_WIDTH: u16 = 1;
pub(super) const ROW_SPLIT_HEIGHT: u16 = 1;
pub(super) const COLUMN_RESIZE_HIT_MARGIN: u16 = 2;
pub(super) const MAX_INLINE_FILE_BYTES: usize = 64 * 1024;
pub(super) const MAX_TREE_DEPTH: usize = 3;
pub(super) const MAX_TREE_FILES: usize = 50;
pub(super) const MAX_TOTAL_ATTACHMENT_CHARS: usize = 100_000;

#[derive(Clone, Debug)]
pub(super) struct StudioTheme {
    pub(super) id: String,
    pub(super) name: String,
    pub(super) background: Color,
    pub(super) surface: Color,
    pub(super) text: Color,
    pub(super) text_dim: Color,
    pub(super) text_muted: Color,
    pub(super) border: Color,
    pub(super) info: Color,
    pub(super) success: Color,
    pub(super) warning: Color,
    pub(super) error: Color,
    pub(super) claude: Color,
    pub(super) codex: Color,
    pub(super) scan: Color,
    pub(super) prompt: Color,
    pub(super) contracts: Color,
    pub(super) brief: Color,
    pub(super) sessions: Color,
    pub(super) output: Color,
    pub(super) activity: Color,
    pub(super) badge_fg: Color,
    pub(super) badge_bg: Color,
    pub(super) status_fg: Color,
    pub(super) status_bg: Color,
    pub(super) tool: Color,
    pub(super) tool_result: Color,
}

pub(super) fn panel_style(theme: &StudioTheme) -> Style {
    Style::default().bg(theme.surface).fg(theme.text)
}

pub(super) fn root_style(theme: &StudioTheme) -> Style {
    Style::default().bg(theme.background).fg(theme.text)
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(super) enum FocusedPane {
    Scan,
    Prompt,
    Contracts,
    ExecutionBrief,
    Sessions,
    Output,
    Activity,
}

impl FocusedPane {
    pub(super) fn label(self) -> &'static str {
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

    pub(super) fn next(self) -> Self {
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

    pub(super) fn previous(self) -> Self {
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

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(super) enum ProviderMode {
    Claude,
    Codex,
    Both,
}

impl ProviderMode {
    pub(super) fn next(self) -> Self {
        match self {
            ProviderMode::Claude => ProviderMode::Codex,
            ProviderMode::Codex => ProviderMode::Both,
            ProviderMode::Both => ProviderMode::Claude,
        }
    }

    pub(super) fn providers(self) -> &'static [ModelProvider] {
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
pub(super) enum WorkspaceMode {
    Isolated,
    Shared,
}

impl WorkspaceMode {
    pub(super) fn next(self) -> Self {
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
pub(super) enum SessionStatus {
    Running,
    Stopped,
    Succeeded,
    Failed,
}

impl SessionStatus {
    pub(super) fn label(self) -> &'static str {
        match self {
            SessionStatus::Running => "running",
            SessionStatus::Stopped => "stopped",
            SessionStatus::Succeeded => "done",
            SessionStatus::Failed => "failed",
        }
    }
}

#[derive(Clone, Debug)]
pub(super) struct SessionState {
    pub(super) id: String,
    pub(super) provider: ModelProvider,
    pub(super) model: String,
    pub(super) workspace_dir: PathBuf,
    pub(super) artifact_dir: PathBuf,
    pub(super) status: SessionStatus,
    pub(super) started_at: DateTime<Utc>,
    pub(super) finished_at: Option<DateTime<Utc>>,
    pub(super) output: Vec<String>,
    pub(super) artifacts: Vec<PathBuf>,
    pub(super) error: Option<String>,
    pub(super) event_count: usize,
    pub(super) last_event_at: Option<DateTime<Utc>>,
    pub(super) prompt_path: Option<PathBuf>,
    pub(super) stop_requested: bool,
}

#[derive(Clone, Debug)]
pub(super) struct PreviewPromptCache {
    #[cfg(test)]
    pub(super) rendered_prompt: String,
    pub(super) display_preview: String,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
pub(super) struct PromptHistoryEntry {
    pub(super) created_at: DateTime<Utc>,
    pub(super) prompt: String,
    pub(super) provider_mode: String,
    pub(super) workspace_mode: String,
    pub(super) contract_name: String,
    pub(super) follow_up: bool,
}

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub(super) struct PromptAppendOutcome {
    pub(super) appended_bytes: usize,
    pub(super) truncated_bytes: usize,
}

#[derive(Clone, Debug)]
pub(super) struct ExecutionContract {
    pub(super) file_name: String,
    pub(super) path: PathBuf,
    pub(super) name: String,
    pub(super) body: String,
    pub(super) attachments: Vec<AttachmentSpec>,
}

#[derive(Clone)]
pub(super) struct SessionLaunch {
    pub(super) id: String,
    pub(super) provider: ModelProvider,
    pub(super) model: String,
    pub(super) workspace_mode: WorkspaceMode,
    pub(super) project_dir: PathBuf,
    pub(super) workspace_dir: PathBuf,
    pub(super) artifact_dir: PathBuf,
    pub(super) prompt: String,
    pub(super) execution_contract: ExecutionContract,
    pub(super) scan: ProjectScan,
    pub(super) prior_context: Option<String>,
    pub(super) prepare_workspace: bool,
}

pub(super) enum PendingStudioAction {
    EditExecutionContract {
        path: PathBuf,
        action_label: &'static str,
    },
    #[cfg_attr(not(target_os = "macos"), allow(dead_code))]
    PickExecutionContractAttachment {
        contract_path: PathBuf,
    },
}

pub(super) struct EditorGuideState {
    pub(super) action: PendingStudioAction,
}

pub(super) struct DeleteConfirmationState {
    pub(super) contract_name: String,
}

pub(super) struct SessionStopConfirmationState {
    pub(super) session_id: String,
    pub(super) provider: ModelProvider,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(super) enum EditorChoice {
    System,
    Vi,
    Nano,
    CodeWait,
}

impl EditorChoice {
    pub(super) fn next(self) -> Self {
        match self {
            Self::System => Self::Nano,
            Self::Nano => Self::Vi,
            Self::Vi => Self::CodeWait,
            Self::CodeWait => Self::System,
        }
    }

    pub(super) fn persist_value(self) -> &'static str {
        match self {
            Self::System => "system",
            Self::Vi => "vi",
            Self::Nano => "nano",
            Self::CodeWait => "code-wait",
        }
    }

    pub(super) fn from_persisted(value: &str) -> Option<Self> {
        match value {
            "system" => Some(Self::System),
            "vi" => Some(Self::Vi),
            "nano" => Some(Self::Nano),
            "code-wait" => Some(Self::CodeWait),
            _ => None,
        }
    }
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub(super) enum ProviderState {
    Ready,
    Missing,
    Blocked,
}

#[derive(Clone, Debug)]
pub(super) struct ProviderReadiness {
    pub(super) state: ProviderState,
    pub(super) detail: String,
}

#[derive(Debug)]
pub(super) struct AuthCheck {
    pub(super) authenticated: bool,
    pub(super) detail: String,
}

#[derive(Debug)]
pub(super) struct CapturedCommand {
    pub(super) success: bool,
    pub(super) stdout: String,
    pub(super) stderr: String,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub(super) struct ProbeCache {
    pub(super) entries: Vec<CachedProbeEntry>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub(super) struct CachedProbeEntry {
    pub(super) provider: String,
    pub(super) model: String,
    pub(super) auth_detail: String,
    pub(super) checked_at: DateTime<Utc>,
}

#[derive(Debug, Deserialize)]
pub(super) struct ClaudeAuthStatus {
    #[serde(rename = "loggedIn")]
    pub(super) logged_in: bool,
    #[serde(rename = "authMethod")]
    pub(super) auth_method: Option<String>,
    #[serde(rename = "apiProvider")]
    pub(super) api_provider: Option<String>,
}

impl ProviderReadiness {
    pub(super) fn ready(detail: impl Into<String>) -> Self {
        Self {
            state: ProviderState::Ready,
            detail: detail.into(),
        }
    }

    pub(super) fn missing(detail: impl Into<String>) -> Self {
        Self {
            state: ProviderState::Missing,
            detail: detail.into(),
        }
    }

    pub(super) fn blocked(detail: impl Into<String>) -> Self {
        Self {
            state: ProviderState::Blocked,
            detail: detail.into(),
        }
    }

    pub(super) fn is_available(&self) -> bool {
        self.state == ProviderState::Ready
    }

    pub(super) fn short_label(&self) -> &'static str {
        match self.state {
            ProviderState::Ready => "ready",
            ProviderState::Missing => "missing",
            ProviderState::Blocked => "blocked",
        }
    }
}

pub(super) enum StudioEvent {
    Key(event::KeyEvent),
    Mouse(MouseEvent),
    Paste(String),
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

#[cfg(test)]
mod tests {
    use crate::agent::ModelProvider;

    use super::{
        EditorChoice, FocusedPane, ProviderMode, ProviderReadiness, ProviderState, WorkspaceMode,
    };

    #[test]
    fn focused_pane_cycles_forward_and_backward() {
        assert_eq!(FocusedPane::Scan.next(), FocusedPane::Prompt);
        assert_eq!(FocusedPane::Prompt.next(), FocusedPane::Contracts);
        assert_eq!(FocusedPane::Contracts.previous(), FocusedPane::Prompt);
        assert_eq!(FocusedPane::Activity.next(), FocusedPane::Scan);
        assert_eq!(FocusedPane::Scan.previous(), FocusedPane::Activity);
    }

    #[test]
    fn provider_mode_wraps_and_returns_expected_provider_sets() {
        assert_eq!(ProviderMode::Claude.next(), ProviderMode::Codex);
        assert_eq!(ProviderMode::Codex.next(), ProviderMode::Both);
        assert_eq!(ProviderMode::Both.next(), ProviderMode::Claude);

        assert_eq!(ProviderMode::Claude.providers(), &[ModelProvider::Claude]);
        assert_eq!(ProviderMode::Codex.providers(), &[ModelProvider::Codex]);
        assert_eq!(
            ProviderMode::Both.providers(),
            &[ModelProvider::Claude, ModelProvider::Codex]
        );
    }

    #[test]
    fn workspace_mode_wraps_between_isolated_and_shared() {
        assert_eq!(WorkspaceMode::Isolated.next(), WorkspaceMode::Shared);
        assert_eq!(WorkspaceMode::Shared.next(), WorkspaceMode::Isolated);
    }

    #[test]
    fn editor_choice_persist_round_trip_and_cycle() {
        assert_eq!(EditorChoice::System.next(), EditorChoice::Nano);
        assert_eq!(EditorChoice::Nano.next(), EditorChoice::Vi);
        assert_eq!(EditorChoice::Vi.next(), EditorChoice::CodeWait);
        assert_eq!(EditorChoice::CodeWait.next(), EditorChoice::System);

        for choice in [
            EditorChoice::System,
            EditorChoice::Vi,
            EditorChoice::Nano,
            EditorChoice::CodeWait,
        ] {
            assert_eq!(
                EditorChoice::from_persisted(choice.persist_value()),
                Some(choice)
            );
        }

        assert_eq!(EditorChoice::from_persisted("unknown"), None);
    }

    #[test]
    fn provider_readiness_helpers_encode_state_and_availability() {
        let ready = ProviderReadiness::ready("ok");
        assert_eq!(ready.state, ProviderState::Ready);
        assert!(ready.is_available());
        assert_eq!(ready.short_label(), "ready");

        let missing = ProviderReadiness::missing("install it");
        assert_eq!(missing.state, ProviderState::Missing);
        assert!(!missing.is_available());
        assert_eq!(missing.short_label(), "missing");

        let blocked = ProviderReadiness::blocked("auth failed");
        assert_eq!(blocked.state, ProviderState::Blocked);
        assert!(!blocked.is_available());
        assert_eq!(blocked.short_label(), "blocked");
    }
}
