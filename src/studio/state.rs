use anyhow::Result;
use chrono::{DateTime, Utc};
use ratatui::style::Color;
use std::{
    collections::HashMap,
    path::{Path, PathBuf},
    sync::{atomic::AtomicBool, Arc},
};
use tokio::task::JoinHandle;

use crate::{
    agent::ModelProvider,
    config::{Config, StudioThemeConfig as StudioThemeOverrides},
    utils::truncate_str,
};

use super::{
    attachments::{resolve_all_attachments, AttachmentManagerState},
    contracts::{load_execution_contracts, load_execution_contracts_with_selection},
    model::{
        DeleteConfirmationState, EditorChoice, EditorGuideState, ExecutionContract, FocusedPane,
        PendingStudioAction, PreviewPromptCache, PromptAppendOutcome, ProviderMode,
        ProviderReadiness, SessionState, SessionStatus, SessionStopConfirmationState, StudioTheme,
        WorkspaceMode, DEFAULT_PROMPT, MAX_PROMPT_BYTES, STUDIO_ROOT_DIR,
    },
    prompt::compose_smoothed_prompt,
    providers::{default_provider_mode, probe_claude_readiness, probe_codex_readiness},
    scan::{scan_project, ProjectScan},
    ui::{
        input::load_editor_choice,
        layout::{ResizeDragState, StudioLayoutConfig},
        render::preview_text_for_display,
    },
};

pub(super) struct ThemeCatalog {
    pub(super) selected_id: String,
    pub(super) order: Vec<String>,
    pub(super) themes: HashMap<String, StudioTheme>,
    pub(super) warnings: Vec<String>,
}

fn rgb(r: u8, g: u8, b: u8) -> Color {
    Color::Rgb(r, g, b)
}

fn normalize_theme_name(name: &str) -> String {
    name.trim()
        .to_ascii_lowercase()
        .chars()
        .map(|ch| match ch {
            'a'..='z' | '0'..='9' => ch,
            _ => '-',
        })
        .collect::<String>()
        .split('-')
        .filter(|part| !part.is_empty())
        .collect::<Vec<_>>()
        .join("-")
}

fn builtin_themes() -> Vec<StudioTheme> {
    vec![
        StudioTheme {
            id: "foundry".into(),
            name: "Foundry".into(),
            background: rgb(0x08, 0x0c, 0x10),
            surface: rgb(0x11, 0x16, 0x1b),
            text: rgb(0xf8, 0xfa, 0xfc),
            text_dim: rgb(0xc0, 0xca, 0xd8),
            text_muted: rgb(0x63, 0x72, 0x84),
            border: rgb(0x37, 0x47, 0x57),
            info: rgb(0x67, 0xe8, 0xf9),
            success: rgb(0x34, 0xd3, 0x99),
            warning: rgb(0xfb, 0xbf, 0x24),
            error: rgb(0xf8, 0x71, 0x71),
            claude: rgb(0xf4, 0x72, 0xb6),
            codex: rgb(0x60, 0xa5, 0xfa),
            scan: rgb(0xfa, 0xcc, 0x15),
            prompt: rgb(0x4a, 0xde, 0x80),
            contracts: rgb(0xf4, 0x72, 0xb6),
            brief: rgb(0xe8, 0x79, 0xf9),
            sessions: rgb(0x60, 0xa5, 0xfa),
            output: rgb(0x67, 0xe8, 0xf9),
            activity: rgb(0x86, 0xef, 0xac),
            badge_fg: rgb(0x08, 0x0c, 0x10),
            badge_bg: rgb(0x67, 0xe8, 0xf9),
            status_fg: rgb(0x08, 0x0c, 0x10),
            status_bg: rgb(0xf8, 0xfa, 0xfc),
            tool: rgb(0x67, 0xe8, 0xf9),
            tool_result: rgb(0x94, 0xa3, 0xb8),
        },
        StudioTheme {
            id: "cyberpunk".into(),
            name: "Cyberpunk".into(),
            background: rgb(0x07, 0x02, 0x14),
            surface: rgb(0x13, 0x0a, 0x22),
            text: rgb(0xff, 0xfb, 0xf5),
            text_dim: rgb(0xe2, 0xd5, 0xff),
            text_muted: rgb(0x8e, 0x78, 0xad),
            border: rgb(0x53, 0x2d, 0x79),
            info: rgb(0x22, 0xd3, 0xee),
            success: rgb(0x5e, 0xff, 0x8c),
            warning: rgb(0xff, 0xc8, 0x57),
            error: rgb(0xff, 0x6b, 0xc1),
            claude: rgb(0xff, 0x61, 0xd8),
            codex: rgb(0x43, 0xf4, 0xff),
            scan: rgb(0xff, 0xf2, 0x75),
            prompt: rgb(0x5e, 0xff, 0x8c),
            contracts: rgb(0xff, 0x61, 0xd8),
            brief: rgb(0xc4, 0x6c, 0xff),
            sessions: rgb(0x43, 0xf4, 0xff),
            output: rgb(0x22, 0xd3, 0xee),
            activity: rgb(0xff, 0xa6, 0x5b),
            badge_fg: rgb(0x07, 0x02, 0x14),
            badge_bg: rgb(0x43, 0xf4, 0xff),
            status_fg: rgb(0xff, 0xfb, 0xf5),
            status_bg: rgb(0x35, 0x10, 0x57),
            tool: rgb(0x43, 0xf4, 0xff),
            tool_result: rgb(0xce, 0xb6, 0xff),
        },
        StudioTheme {
            id: "phosphor".into(),
            name: "Phosphor".into(),
            background: rgb(0x03, 0x08, 0x03),
            surface: rgb(0x08, 0x12, 0x08),
            text: rgb(0xc7, 0xff, 0xb1),
            text_dim: rgb(0xa7, 0xe9, 0x94),
            text_muted: rgb(0x4f, 0x76, 0x49),
            border: rgb(0x2a, 0x46, 0x29),
            info: rgb(0x7c, 0xff, 0xc4),
            success: rgb(0xc7, 0xff, 0xb1),
            warning: rgb(0xf4, 0xdc, 0x79),
            error: rgb(0xff, 0x86, 0x86),
            claude: rgb(0xb0, 0xff, 0x8d),
            codex: rgb(0x7c, 0xff, 0xc4),
            scan: rgb(0xe8, 0xff, 0x9c),
            prompt: rgb(0xc7, 0xff, 0xb1),
            contracts: rgb(0x9d, 0xff, 0xc7),
            brief: rgb(0x8f, 0xe9, 0x74),
            sessions: rgb(0x7c, 0xff, 0xc4),
            output: rgb(0x9d, 0xff, 0xc7),
            activity: rgb(0xb0, 0xff, 0x8d),
            badge_fg: rgb(0x03, 0x08, 0x03),
            badge_bg: rgb(0xc7, 0xff, 0xb1),
            status_fg: rgb(0x03, 0x08, 0x03),
            status_bg: rgb(0xc7, 0xff, 0xb1),
            tool: rgb(0x7c, 0xff, 0xc4),
            tool_result: rgb(0x75, 0x9b, 0x69),
        },
        StudioTheme {
            id: "ocean".into(),
            name: "Ocean".into(),
            background: rgb(0x05, 0x10, 0x1a),
            surface: rgb(0x0b, 0x1e, 0x2d),
            text: rgb(0xec, 0xfe, 0xff),
            text_dim: rgb(0xc9, 0xee, 0xf2),
            text_muted: rgb(0x66, 0x89, 0x9f),
            border: rgb(0x2a, 0x4e, 0x66),
            info: rgb(0x7d, 0xff, 0xf0),
            success: rgb(0x6e, 0xe7, 0xb7),
            warning: rgb(0xfd, 0xba, 0x74),
            error: rgb(0xfb, 0x71, 0x71),
            claude: rgb(0x93, 0xc5, 0xfd),
            codex: rgb(0x22, 0xd3, 0xee),
            scan: rgb(0xf0, 0xab, 0xfc),
            prompt: rgb(0x6e, 0xe7, 0xb7),
            contracts: rgb(0xc4, 0xb5, 0xfd),
            brief: rgb(0x93, 0xc5, 0xfd),
            sessions: rgb(0x38, 0xbd, 0xf8),
            output: rgb(0x7d, 0xff, 0xf0),
            activity: rgb(0x6e, 0xe7, 0xb7),
            badge_fg: rgb(0x05, 0x10, 0x1a),
            badge_bg: rgb(0x7d, 0xff, 0xf0),
            status_fg: rgb(0xec, 0xfe, 0xff),
            status_bg: rgb(0x0f, 0x2c, 0x40),
            tool: rgb(0x22, 0xd3, 0xee),
            tool_result: rgb(0x9c, 0xb6, 0xc5),
        },
        StudioTheme {
            id: "synthwave".into(),
            name: "Synthwave".into(),
            background: rgb(0x0e, 0x06, 0x1c),
            surface: rgb(0x18, 0x0e, 0x2f),
            text: rgb(0xf8, 0xf7, 0xff),
            text_dim: rgb(0xd7, 0xcf, 0xff),
            text_muted: rgb(0x7e, 0x74, 0xa6),
            border: rgb(0x44, 0x33, 0x74),
            info: rgb(0x5e, 0xe7, 0xff),
            success: rgb(0x86, 0xef, 0xac),
            warning: rgb(0xfb, 0xce, 0x72),
            error: rgb(0xfb, 0x71, 0x71),
            claude: rgb(0xf9, 0x72, 0xff),
            codex: rgb(0x60, 0xa5, 0xfa),
            scan: rgb(0xf9, 0xa8, 0xd4),
            prompt: rgb(0x86, 0xef, 0xac),
            contracts: rgb(0xf9, 0x72, 0xff),
            brief: rgb(0xc0, 0x84, 0xfc),
            sessions: rgb(0x60, 0xa5, 0xfa),
            output: rgb(0x5e, 0xe7, 0xff),
            activity: rgb(0xfd, 0xba, 0x74),
            badge_fg: rgb(0x0e, 0x06, 0x1c),
            badge_bg: rgb(0x5e, 0xe7, 0xff),
            status_fg: rgb(0xf8, 0xf7, 0xff),
            status_bg: rgb(0x2f, 0x1b, 0x56),
            tool: rgb(0x5e, 0xe7, 0xff),
            tool_result: rgb(0xb4, 0xa8, 0xd8),
        },
        StudioTheme {
            id: "amber".into(),
            name: "Amber".into(),
            background: rgb(0x10, 0x0b, 0x04),
            surface: rgb(0x1c, 0x14, 0x09),
            text: rgb(0xff, 0xf7, 0xdb),
            text_dim: rgb(0xe7, 0xd7, 0xa7),
            text_muted: rgb(0x8c, 0x79, 0x48),
            border: rgb(0x56, 0x46, 0x21),
            info: rgb(0xff, 0xd5, 0x7a),
            success: rgb(0xf5, 0xd0, 0x5c),
            warning: rgb(0xfb, 0xbf, 0x24),
            error: rgb(0xf9, 0x71, 0x71),
            claude: rgb(0xff, 0xb6, 0x4d),
            codex: rgb(0xff, 0xd9, 0x73),
            scan: rgb(0xff, 0xe4, 0x99),
            prompt: rgb(0xf5, 0xd0, 0x5c),
            contracts: rgb(0xff, 0xb6, 0x4d),
            brief: rgb(0xfd, 0xba, 0x74),
            sessions: rgb(0xff, 0xd9, 0x73),
            output: rgb(0xff, 0xd5, 0x7a),
            activity: rgb(0xf5, 0xd0, 0x5c),
            badge_fg: rgb(0x10, 0x0b, 0x04),
            badge_bg: rgb(0xff, 0xd5, 0x7a),
            status_fg: rgb(0x10, 0x0b, 0x04),
            status_bg: rgb(0xff, 0xe4, 0x99),
            tool: rgb(0xff, 0xd5, 0x7a),
            tool_result: rgb(0xba, 0xa3, 0x6d),
        },
        StudioTheme {
            id: "graphite".into(),
            name: "Graphite".into(),
            background: rgb(0x11, 0x14, 0x1a),
            surface: rgb(0x18, 0x1c, 0x23),
            text: rgb(0xf3, 0xf4, 0xf6),
            text_dim: rgb(0xd1, 0xd5, 0xdb),
            text_muted: rgb(0x6b, 0x72, 0x80),
            border: rgb(0x3b, 0x42, 0x4f),
            info: rgb(0x93, 0xc5, 0xfd),
            success: rgb(0x86, 0xef, 0xac),
            warning: rgb(0xfd, 0xba, 0x74),
            error: rgb(0xf8, 0x71, 0x71),
            claude: rgb(0xc4, 0xb5, 0xfd),
            codex: rgb(0x93, 0xc5, 0xfd),
            scan: rgb(0xfc, 0xf0, 0x89),
            prompt: rgb(0x86, 0xef, 0xac),
            contracts: rgb(0xc4, 0xb5, 0xfd),
            brief: rgb(0xd8, 0xb4, 0xfe),
            sessions: rgb(0x93, 0xc5, 0xfd),
            output: rgb(0x7d, 0xff, 0xf0),
            activity: rgb(0x86, 0xef, 0xac),
            badge_fg: rgb(0x11, 0x14, 0x1a),
            badge_bg: rgb(0xe5, 0xe7, 0xeb),
            status_fg: rgb(0xf3, 0xf4, 0xf6),
            status_bg: rgb(0x2b, 0x31, 0x3c),
            tool: rgb(0x93, 0xc5, 0xfd),
            tool_result: rgb(0x9c, 0xa3, 0xaf),
        },
        StudioTheme {
            id: "paper".into(),
            name: "Paper".into(),
            background: rgb(0xf4, 0xef, 0xe6),
            surface: rgb(0xff, 0xfb, 0xf1),
            text: rgb(0x1f, 0x29, 0x37),
            text_dim: rgb(0x47, 0x55, 0x69),
            text_muted: rgb(0x64, 0x74, 0x8b),
            border: rgb(0xc7, 0xd2, 0xfe),
            info: rgb(0x0f, 0x76, 0x6e),
            success: rgb(0x15, 0x80, 0x3d),
            warning: rgb(0xb4, 0x53, 0x09),
            error: rgb(0xb9, 0x1c, 0x1c),
            claude: rgb(0xbe, 0x18, 0x5d),
            codex: rgb(0x1d, 0x4e, 0xd8),
            scan: rgb(0xa1, 0x62, 0x07),
            prompt: rgb(0x15, 0x80, 0x3d),
            contracts: rgb(0x93, 0x33, 0xea),
            brief: rgb(0x7c, 0x3a, 0xed),
            sessions: rgb(0x25, 0x63, 0xeb),
            output: rgb(0x0f, 0x76, 0x6e),
            activity: rgb(0x05, 0x96, 0x69),
            badge_fg: rgb(0xff, 0xfb, 0xf1),
            badge_bg: rgb(0x0f, 0x76, 0x6e),
            status_fg: rgb(0xff, 0xfb, 0xf1),
            status_bg: rgb(0x1f, 0x29, 0x37),
            tool: rgb(0x08, 0x91, 0xb2),
            tool_result: rgb(0x64, 0x74, 0x8b),
        },
    ]
}

fn parse_hex_color(value: &str) -> Option<Color> {
    let hex = value.trim().strip_prefix('#')?;
    match hex.len() {
        3 => {
            let expand = |idx: usize| u8::from_str_radix(&hex[idx..=idx], 16).ok().map(|n| n * 17);
            Some(rgb(expand(0)?, expand(1)?, expand(2)?))
        }
        6 => Some(rgb(
            u8::from_str_radix(&hex[0..2], 16).ok()?,
            u8::from_str_radix(&hex[2..4], 16).ok()?,
            u8::from_str_radix(&hex[4..6], 16).ok()?,
        )),
        _ => None,
    }
}

fn parse_color_spec(value: &str) -> Option<Color> {
    if value.trim().starts_with('#') {
        return parse_hex_color(value);
    }

    match normalize_theme_name(value).as_str() {
        "black" => Some(Color::Black),
        "white" => Some(Color::White),
        "gray" => Some(Color::Gray),
        "dark-gray" => Some(Color::DarkGray),
        "red" => Some(Color::Red),
        "light-red" => Some(Color::LightRed),
        "green" => Some(Color::Green),
        "light-green" => Some(Color::LightGreen),
        "yellow" => Some(Color::Yellow),
        "light-yellow" => Some(Color::LightYellow),
        "blue" => Some(Color::Blue),
        "light-blue" => Some(Color::LightBlue),
        "magenta" => Some(Color::Magenta),
        "light-magenta" => Some(Color::LightMagenta),
        "cyan" => Some(Color::Cyan),
        "light-cyan" => Some(Color::LightCyan),
        _ => None,
    }
}

fn apply_theme_overrides(
    mut theme: StudioTheme,
    theme_name: &str,
    overrides: &StudioThemeOverrides,
    warnings: &mut Vec<String>,
) -> StudioTheme {
    macro_rules! apply_override {
        ($field:ident, $label:literal) => {
            if let Some(value) = overrides.$field.as_deref() {
                match parse_color_spec(value) {
                    Some(color) => theme.$field = color,
                    None => warnings.push(format!(
                        "theme `{}` ignored invalid {} color `{}`",
                        theme_name, $label, value
                    )),
                }
            }
        };
    }

    apply_override!(background, "background");
    apply_override!(surface, "surface");
    apply_override!(text, "text");
    apply_override!(text_dim, "text_dim");
    apply_override!(text_muted, "text_muted");
    apply_override!(border, "border");
    apply_override!(info, "info");
    apply_override!(success, "success");
    apply_override!(warning, "warning");
    apply_override!(error, "error");
    apply_override!(claude, "claude");
    apply_override!(codex, "codex");
    apply_override!(scan, "scan");
    apply_override!(prompt, "prompt");
    apply_override!(contracts, "contracts");
    apply_override!(brief, "brief");
    apply_override!(sessions, "sessions");
    apply_override!(output, "output");
    apply_override!(activity, "activity");
    apply_override!(badge_fg, "badge_fg");
    apply_override!(badge_bg, "badge_bg");
    apply_override!(status_fg, "status_fg");
    apply_override!(status_bg, "status_bg");
    apply_override!(tool, "tool");
    apply_override!(tool_result, "tool_result");

    theme.id = normalize_theme_name(theme_name);
    theme.name = theme_name.trim().to_string();
    theme
}

pub(super) fn build_theme_catalog(config: &Config) -> ThemeCatalog {
    let mut themes = HashMap::new();
    let mut order = Vec::new();
    let mut warnings = Vec::new();

    for theme in builtin_themes() {
        order.push(theme.id.clone());
        themes.insert(theme.id.clone(), theme);
    }

    for (name, overrides) in &config.studio_custom_themes {
        let trimmed = name.trim();
        if trimmed.is_empty() {
            warnings.push("ignored custom theme with an empty name".to_string());
            continue;
        }

        let id = normalize_theme_name(trimmed);
        let base_id = overrides
            .base
            .as_deref()
            .map(normalize_theme_name)
            .filter(|value| !value.is_empty())
            .unwrap_or_else(|| "foundry".to_string());
        let base_theme = themes
            .get(&base_id)
            .cloned()
            .or_else(|| themes.get("foundry").cloned());
        let Some(base_theme) = base_theme else {
            continue;
        };
        if !themes.contains_key(&base_id) {
            warnings.push(format!(
                "theme `{}` requested unknown base `{}`; using Foundry",
                trimmed,
                overrides.base.as_deref().unwrap_or("foundry")
            ));
        }

        let theme = apply_theme_overrides(base_theme, trimmed, overrides, &mut warnings);
        if !order.iter().any(|existing| existing == &id) {
            order.push(id.clone());
        }
        themes.insert(id, theme);
    }

    let requested_id = normalize_theme_name(&config.studio_theme);
    let selected_id = if requested_id.is_empty() || !themes.contains_key(&requested_id) {
        if !requested_id.is_empty() {
            warnings.push(format!(
                "theme `{}` not found; using Foundry",
                config.studio_theme
            ));
        }
        "foundry".to_string()
    } else {
        requested_id
    };

    ThemeCatalog {
        selected_id,
        order,
        themes,
        warnings,
    }
}

pub(super) struct StudioState {
    pub(super) project_dir: PathBuf,
    pub(super) prompt: String,
    pub(super) is_editing_prompt: bool,
    pub(super) focused_pane: FocusedPane,
    pub(super) provider_mode: ProviderMode,
    pub(super) workspace_mode: WorkspaceMode,
    pub(super) scan: ProjectScan,
    pub(super) execution_contracts: Vec<ExecutionContract>,
    pub(super) selected_execution_contract: usize,
    pub(super) sessions: Vec<SessionState>,
    pub(super) selected_session: usize,
    pub(super) output_scroll: usize,
    pub(super) preview_scroll: usize,
    pub(super) preview_cache: Option<PreviewPromptCache>,
    pub(super) logs: Vec<(DateTime<Utc>, String)>,
    pub(super) tick_count: usize,
    pub(super) should_quit: bool,
    pub(super) shutdown_initiated: bool,
    pub(super) layout_config: StudioLayoutConfig,
    pub(super) active_resize: Option<ResizeDragState>,
    pub(super) claude_model: String,
    pub(super) codex_model: String,
    pub(super) claude_readiness: ProviderReadiness,
    pub(super) codex_readiness: ProviderReadiness,
    pub(super) editor_choice: EditorChoice,
    pub(super) session_controls: HashMap<String, SessionControl>,
    pub(super) pending_action: Option<PendingStudioAction>,
    pub(super) editor_guide: Option<EditorGuideState>,
    pub(super) delete_confirmation: Option<DeleteConfirmationState>,
    pub(super) session_stop_confirmation: Option<SessionStopConfirmationState>,
    pub(super) attachment_manager: Option<AttachmentManagerState>,
    pub(super) theme: StudioTheme,
    pub(super) themes: HashMap<String, StudioTheme>,
    pub(super) theme_order: Vec<String>,
    pub(super) theme_warnings: Vec<String>,
}

pub(super) struct SessionControl {
    pub(super) cancel_flag: Arc<AtomicBool>,
    pub(super) task: JoinHandle<()>,
}

impl StudioState {
    pub(super) fn new(project_dir: &Path, config: &Config) -> Result<Self> {
        let scan = scan_project(project_dir)?;
        let claude_model = config.studio_claude_model.clone();
        let codex_model = config.studio_codex_model.clone();
        let claude_readiness = probe_claude_readiness(project_dir, &claude_model);
        let codex_readiness = probe_codex_readiness(project_dir, &codex_model);
        let provider_mode = default_provider_mode(&claude_readiness, &codex_readiness);
        let (execution_contracts, selected_execution_contract) =
            load_execution_contracts(project_dir)?;
        let editor_choice = load_editor_choice(project_dir);
        let theme_catalog = build_theme_catalog(config);
        let theme = theme_catalog
            .themes
            .get(&theme_catalog.selected_id)
            .cloned()
            .or_else(|| theme_catalog.themes.get("foundry").cloned())
            .unwrap_or_else(|| builtin_themes().into_iter().next().expect("built-in theme"));
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
            session_stop_confirmation: None,
            attachment_manager: None,
            theme,
            themes: theme_catalog.themes,
            theme_order: theme_catalog.order,
            theme_warnings: theme_catalog.warnings,
        })
    }

    pub(super) fn log(&mut self, message: impl Into<String>) {
        self.logs.push((Utc::now(), message.into()));
    }

    pub(super) fn invalidate_preview_cache(&mut self) {
        self.preview_cache = None;
    }

    fn ensure_preview_cache(&mut self) -> &PreviewPromptCache {
        if self.preview_cache.is_none() {
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
            let display_preview = preview_text_for_display(&prompt);
            self.preview_cache = Some(PreviewPromptCache {
                #[cfg(test)]
                rendered_prompt: prompt,
                display_preview,
            });
        }

        self.preview_cache
            .as_ref()
            .expect("preview cache should exist")
    }

    pub(super) fn has_running_sessions(&self) -> bool {
        self.sessions
            .iter()
            .any(|session| session.status == SessionStatus::Running)
    }

    #[cfg(test)]
    pub(super) fn preview_prompt(&mut self) -> &str {
        self.ensure_preview_cache().rendered_prompt.as_str()
    }

    pub(super) fn preview_display(&mut self) -> &str {
        self.ensure_preview_cache().display_preview.as_str()
    }

    pub(super) fn selected_session(&self) -> Option<&SessionState> {
        self.sessions.get(self.selected_session)
    }

    pub(super) fn selected_execution_contract(&self) -> &ExecutionContract {
        &self.execution_contracts[self.selected_execution_contract]
    }

    pub(super) fn set_selected_execution_contract_index(&mut self, index: usize) {
        self.selected_execution_contract = index;
        self.preview_scroll = 0;
        self.invalidate_preview_cache();
        self.sync_attachment_manager_selection();
    }

    pub(super) fn refresh_execution_contracts(&mut self) -> Result<()> {
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

    pub(super) fn sync_attachment_manager_selection(&mut self) {
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

    pub(super) fn model_for(&self, provider: ModelProvider) -> &str {
        match provider {
            ModelProvider::Claude => &self.claude_model,
            ModelProvider::Codex => &self.codex_model,
        }
    }

    pub(super) fn provider_readiness(&self, provider: ModelProvider) -> &ProviderReadiness {
        match provider {
            ModelProvider::Claude => &self.claude_readiness,
            ModelProvider::Codex => &self.codex_readiness,
        }
    }
}

pub(in crate::studio) fn cycle_theme(state: &mut StudioState, reverse: bool) {
    if state.theme_order.is_empty() {
        return;
    }

    let current_idx = state
        .theme_order
        .iter()
        .position(|theme_id| theme_id == &state.theme.id)
        .unwrap_or(0);
    let next_idx = if reverse {
        current_idx
            .checked_sub(1)
            .unwrap_or_else(|| state.theme_order.len().saturating_sub(1))
    } else {
        (current_idx + 1) % state.theme_order.len()
    };

    if let Some(theme) = state.themes.get(&state.theme_order[next_idx]).cloned() {
        state.theme = theme;
        state.log(format!("theme: {}", state.theme.name));
    }
}

pub(in crate::studio) fn append_prompt_text(
    state: &mut StudioState,
    text: &str,
) -> PromptAppendOutcome {
    if text.is_empty() {
        return PromptAppendOutcome::default();
    }

    let available_bytes = MAX_PROMPT_BYTES.saturating_sub(state.prompt.len());
    if available_bytes == 0 {
        return PromptAppendOutcome {
            appended_bytes: 0,
            truncated_bytes: text.len(),
        };
    }

    let appended = truncate_str(text, available_bytes);
    if appended.is_empty() {
        return PromptAppendOutcome {
            appended_bytes: 0,
            truncated_bytes: text.len(),
        };
    }

    state.prompt.push_str(appended);
    state.invalidate_preview_cache();
    PromptAppendOutcome {
        appended_bytes: appended.len(),
        truncated_bytes: text.len().saturating_sub(appended.len()),
    }
}

pub(in crate::studio) fn format_byte_count(bytes: usize) -> String {
    if bytes >= 1024 {
        format!("{} KB", bytes.div_ceil(1024))
    } else {
        format!("{} B", bytes)
    }
}

#[cfg(test)]
mod tests {
    use anyhow::Result;
    use ratatui::style::Color;
    use std::{fs, path::PathBuf};

    use super::super::{
        attachments::{AttachmentMode, AttachmentSpec},
        contracts::{cycle_execution_contract, default_execution_contract_content},
        model::ExecutionContract,
        test_helpers::{temp_test_dir, test_state},
    };
    use super::{build_theme_catalog, builtin_themes, cycle_theme};
    use crate::config::{Config, StudioThemeConfig as StudioThemeOverrides};

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

        let first = state.preview_prompt().to_string();
        fs::write(&attachment_path, "second version\n")?;
        let cached = state.preview_prompt().to_string();
        state.invalidate_preview_cache();
        let refreshed = state.preview_prompt().to_string();

        fs::remove_dir_all(&project_dir)?;
        assert!(first.contains("first version"));
        assert!(cached.contains("first version"));
        assert!(!cached.contains("second version"));
        assert!(refreshed.contains("second version"));
        Ok(())
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
    fn theme_catalog_loads_custom_theme_overrides() {
        let mut config = Config {
            studio_theme: "paper".into(),
            ..Config::default()
        };
        config.studio_custom_themes.insert(
            "CRT Mint".into(),
            StudioThemeOverrides {
                base: Some("phosphor".into()),
                output: Some("#112233".into()),
                ..StudioThemeOverrides::default()
            },
        );

        let catalog = build_theme_catalog(&config);
        let phosphor = builtin_themes()
            .into_iter()
            .find(|theme| theme.id == "phosphor")
            .expect("phosphor theme");
        let custom = catalog.themes.get("crt-mint").expect("custom theme");

        assert_eq!(catalog.selected_id, "paper");
        assert_eq!(custom.name, "CRT Mint");
        assert_eq!(custom.output, Color::Rgb(0x11, 0x22, 0x33));
        assert_eq!(custom.background, phosphor.background);
    }

    #[test]
    fn cycle_theme_wraps_forward_and_backward() {
        let mut state = test_state();
        let original = state.theme.id.clone();

        cycle_theme(&mut state, false);
        assert_ne!(state.theme.id, original);

        cycle_theme(&mut state, true);
        assert_eq!(state.theme.id, original);

        let last_theme = state
            .theme_order
            .last()
            .cloned()
            .expect("theme order should not be empty");
        cycle_theme(&mut state, true);
        assert_eq!(state.theme.id, last_theme);
    }
}
