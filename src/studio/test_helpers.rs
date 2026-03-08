use super::{
    contracts::default_execution_contract_content,
    model::{
        EditorChoice, ExecutionContract, FocusedPane, ProviderMode, ProviderReadiness,
        SessionState, SessionStatus, WorkspaceMode, DEFAULT_PROMPT,
    },
    scan::ProjectScan,
    state::{build_theme_catalog, StudioState},
    ui::layout::StudioLayoutConfig,
};
use crate::{agent::ModelProvider, config::Config};
use chrono::Utc;
use std::path::PathBuf;
use std::{
    collections::HashMap,
    time::{SystemTime, UNIX_EPOCH},
};

pub(super) fn test_scan() -> ProjectScan {
    ProjectScan {
        generated_at: Utc::now(),
        top_level: vec!["src".into()],
        stack_signals: vec!["Rust".into()],
        data_candidates: vec!["metrics.json".into()],
        output_targets: vec!["public".into()],
    }
}

pub(super) fn test_contract() -> ExecutionContract {
    ExecutionContract {
        file_name: "standard.md".into(),
        path: PathBuf::from("/tmp/project/.foundry/studio/contracts/standard.md"),
        name: "Standard Build Contract".into(),
        body: default_execution_contract_content().into(),
        attachments: Vec::new(),
    }
}

pub(super) fn temp_test_dir(prefix: &str) -> PathBuf {
    let unique = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("system time before unix epoch")
        .as_nanos();
    std::env::temp_dir().join(format!("{}-{}", prefix, unique))
}

pub(super) fn test_state() -> StudioState {
    let theme_catalog = build_theme_catalog(&Config::default());
    let theme = theme_catalog
        .themes
        .get(&theme_catalog.selected_id)
        .cloned()
        .or_else(|| theme_catalog.themes.get("foundry").cloned())
        .expect("foundry theme");
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
        session_stop_confirmation: None,
        attachment_manager: None,
        theme,
        themes: theme_catalog.themes,
        theme_order: theme_catalog.order,
        theme_warnings: Vec::new(),
    }
}

pub(super) fn test_session(status: SessionStatus) -> SessionState {
    SessionState {
        id: "session".into(),
        provider: ModelProvider::Claude,
        model: "opus".into(),
        workspace_dir: PathBuf::from("/tmp/workspace"),
        artifact_dir: PathBuf::from("/tmp/workspace/.foundry/studio/artifacts/run/claude"),
        status,
        started_at: Utc::now(),
        finished_at: None,
        output: Vec::new(),
        artifacts: Vec::new(),
        error: None,
        event_count: 0,
        last_event_at: None,
        prompt_path: None,
        stop_requested: false,
    }
}
