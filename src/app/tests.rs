use super::startup::{
    classify_plan_status, detect_startup_scenario, enter_home_surface, handle_startup_event,
    handle_startup_key, handle_startup_mouse_at, load_pending_task_at,
};
use super::state::{
    AppEvent, AppPhase, AppState, LoopEvent, PendingTransition, PlanStatus, PlanningOutcome,
    PlanningState, RowId, SettingsOverlayState, StartupScenario, StartupState,
};
use super::{
    apply_orchestrator_outcome, apply_pending_transition, apply_planning_outcome,
    handle_agent_done, handle_event, handle_settings_action, handle_settings_overlay_key,
    prepare_append_tasks_start, process_received_event, seed_spec_from_brief,
};
use crate::agent::{AgentOutputEvent, AgentRole};
use crate::config::Config;
use crate::orchestrator::{
    Finding, OrchestratorOutcome, PlanReviewOutcome, ProposerOutput, ReviewerOutput,
};
use crate::task::Task;
use crossterm::event::{self, KeyCode, KeyModifiers, MouseButton, MouseEvent, MouseEventKind};
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::sync::atomic::Ordering;
use std::time::{SystemTime, UNIX_EPOCH};
use tokio::sync::mpsc;

fn temp_project_dir(name: &str) -> PathBuf {
    let unique = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .expect("system time before unix epoch")
        .as_nanos();
    let dir = std::env::temp_dir().join(format!("{}-{}", name, unique));
    std::fs::create_dir_all(&dir).expect("failed to create temp dir");
    dir
}

fn write_file(path: &Path, content: &str) {
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).expect("failed to create parent dir");
    }
    std::fs::write(path, content).expect("failed to write test file");
}

fn overlay_focus_index(overlay: &SettingsOverlayState, field_id: &str) -> usize {
    for idx in 0..overlay.visible_row_count() {
        if matches!(overlay.row_at_index(idx), Some(RowId::Field(id)) if id == field_id) {
            return idx;
        }
    }
    panic!("missing overlay field: {field_id}");
}

#[test]
fn settings_overlay_bool_toggle_reloads_config_each_time() {
    let dir = temp_project_dir("foundry-settings-bool");
    write_file(
        &dir.join(".foundry.json"),
        r#"{"plan_review_enabled":false}"#,
    );
    std::fs::create_dir_all(dir.join(".buildloop")).expect("failed to create .buildloop");

    let mut state = AppState::new(dir.join(".buildloop"));
    state.show_settings_overlay = true;
    state.settings_overlay = Some(SettingsOverlayState::new());
    let focus = overlay_focus_index(
        state.settings_overlay.as_ref().expect("settings overlay"),
        "plan_review_enabled",
    );
    state.settings_overlay.as_mut().unwrap().focus = focus;

    handle_settings_action(&mut state);
    let config = Config::load(&dir);
    assert!(
        config.plan_review_enabled,
        "first toggle should enable the flag"
    );

    handle_settings_action(&mut state);
    let config = Config::load(&dir);
    assert!(
        !config.plan_review_enabled,
        "second toggle should observe the updated config and disable the flag"
    );

    let _ = std::fs::remove_dir_all(dir);
}

#[test]
fn settings_overlay_number_edit_persists_value() {
    let dir = temp_project_dir("foundry-settings-number");
    write_file(
        &dir.join(".foundry.json"),
        r#"{"embedding_timeout_ms":1000}"#,
    );
    std::fs::create_dir_all(dir.join(".buildloop")).expect("failed to create .buildloop");

    let mut state = AppState::new(dir.join(".buildloop"));
    state.show_settings_overlay = true;
    state.settings_overlay = Some(SettingsOverlayState::new());
    state
        .settings_overlay
        .as_mut()
        .unwrap()
        .expanded_sections
        .insert("local_models".into());
    let focus = overlay_focus_index(
        state.settings_overlay.as_ref().expect("settings overlay"),
        "embedding_timeout_ms",
    );
    state.settings_overlay.as_mut().unwrap().focus = focus;

    handle_settings_action(&mut state);
    assert!(
        state
            .settings_overlay
            .as_ref()
            .and_then(|ov| ov.editing.as_ref())
            .is_some(),
        "number field should enter inline edit mode"
    );

    handle_settings_overlay_key(
        &mut state,
        event::KeyEvent::new(KeyCode::Char('u'), KeyModifiers::CONTROL),
    );
    for ch in ['2', '5', '0', '0'] {
        handle_settings_overlay_key(
            &mut state,
            event::KeyEvent::new(KeyCode::Char(ch), KeyModifiers::NONE),
        );
    }
    handle_settings_overlay_key(
        &mut state,
        event::KeyEvent::new(KeyCode::Enter, KeyModifiers::NONE),
    );

    let config = Config::load(&dir);
    assert_eq!(config.embedding_timeout_ms, 2500);
    assert!(
        state
            .settings_overlay
            .as_ref()
            .and_then(|ov| ov.editing.as_ref())
            .is_none(),
        "successful save should exit inline edit mode"
    );

    let _ = std::fs::remove_dir_all(dir);
}

#[test]
fn detect_startup_scenario_for_fresh_directory() {
    let dir = temp_project_dir("foundry-fresh");
    assert_eq!(detect_startup_scenario(&dir), StartupScenario::EmptyProject);
    let _ = std::fs::remove_dir_all(dir);
}

#[test]
fn detect_startup_scenario_for_existing_code_without_plan() {
    let dir = temp_project_dir("foundry-needs-plan");
    write_file(
        &dir.join("Cargo.toml"),
        "[package]\nname = \"demo\"\nversion = \"0.1.0\"\n",
    );
    write_file(&dir.join("src/main.rs"), "fn main() {}\n");

    assert_eq!(detect_startup_scenario(&dir), StartupScenario::NeedsQueue);
    let _ = std::fs::remove_dir_all(dir);
}

#[test]
fn detect_startup_scenario_for_architecture_only_directory() {
    let dir = temp_project_dir("foundry-architecture-only");
    write_file(
        &dir.join("SPEC.md"),
        "# Architecture\n\n## Overview\nDescribe the system.\n",
    );

    assert_eq!(detect_startup_scenario(&dir), StartupScenario::NeedsQueue);
    let _ = std::fs::remove_dir_all(dir);
}

#[test]
fn detect_startup_scenario_ignores_virtualenv_only_directory() {
    let dir = temp_project_dir("foundry-virtualenv-only");
    write_file(
        &dir.join(".venv/lib/python3.12/site-packages/demo.py"),
        "def demo() -> None:\n    pass\n",
    );

    assert_eq!(detect_startup_scenario(&dir), StartupScenario::EmptyProject);
    let _ = std::fs::remove_dir_all(dir);
}

#[test]
fn detect_startup_scenario_for_plan_only_directory() {
    let dir = temp_project_dir("foundry-plan-only");
    write_file(
        &dir.join("TASKS.md"),
        "# Plan\n\n- [ ] T1.1: Add startup flow\n",
    );

    assert_eq!(detect_startup_scenario(&dir), StartupScenario::QueueReady);
    let _ = std::fs::remove_dir_all(dir);
}

#[test]
fn detect_startup_scenario_for_lowercase_tasks_file() {
    let dir = temp_project_dir("foundry-lowercase-tasks");
    write_file(
        &dir.join("tasks.md"),
        "# Plan\n\n- [ ] T1.1: Lowercase task\n",
    );

    assert_eq!(detect_startup_scenario(&dir), StartupScenario::QueueReady);
    let _ = std::fs::remove_dir_all(dir);
}

#[test]
fn legacy_contract_filenames_still_work() {
    let dir = temp_project_dir("foundry-legacy-contracts");
    write_file(
        &dir.join("ARCHITECTURE.md"),
        "# Architecture\n\n## Overview\nLegacy spec.\n",
    );
    write_file(
        &dir.join("IMPL_PLAN.md"),
        "# Plan\n\n- [ ] T1.1: Legacy task\n",
    );

    assert_eq!(detect_startup_scenario(&dir), StartupScenario::QueueReady);

    let startup = StartupState::new(
        &dir,
        StartupScenario::QueueReady,
        PlanStatus::Pending(1),
        None,
    );
    assert_eq!(startup.spec_file_name, "ARCHITECTURE.md");
    assert_eq!(startup.tasks_file_name, "IMPL_PLAN.md");

    let _ = std::fs::remove_dir_all(dir);
}

#[test]
fn detect_startup_scenario_for_pending_and_completed_plan() {
    let dir = temp_project_dir("foundry-plan-status");
    write_file(
        &dir.join("Cargo.toml"),
        "[package]\nname = \"demo\"\nversion = \"0.1.0\"\n",
    );
    write_file(&dir.join("src/main.rs"), "fn main() {}\n");
    write_file(
        &dir.join("TASKS.md"),
        "# Plan\n\n- [ ] T1.1: Add startup flow\n",
    );
    assert_eq!(detect_startup_scenario(&dir), StartupScenario::QueueReady);

    write_file(
        &dir.join("TASKS.md"),
        "# Plan\n\n- [x] T1.1: Add startup flow\n",
    );
    assert_eq!(
        detect_startup_scenario(&dir),
        StartupScenario::QueueComplete
    );
    let _ = std::fs::remove_dir_all(dir);
}

#[test]
fn classify_plan_status_distinguishes_common_states() {
    let dir = temp_project_dir("foundry-plan-classify");
    let plan_path = dir.join("TASKS.md");

    assert_eq!(classify_plan_status(&plan_path), PlanStatus::Missing);

    write_file(&plan_path, "# Plan\n\n");
    assert_eq!(classify_plan_status(&plan_path), PlanStatus::Empty);

    write_file(&plan_path, "# Plan\n\n- [ ] T1.1: Pending task\n");
    assert_eq!(classify_plan_status(&plan_path), PlanStatus::Pending(1));

    write_file(&plan_path, "# Plan\n\n- [x] T1.1: Done task\n");
    assert_eq!(classify_plan_status(&plan_path), PlanStatus::Complete);
    let _ = std::fs::remove_dir_all(dir);
}

#[test]
fn startup_empty_input_on_needs_queue_sets_planning_transition() {
    let dir = temp_project_dir("foundry-startup-scan");
    write_file(
        &dir.join("Cargo.toml"),
        "[package]\nname = \"demo\"\nversion = \"0.1.0\"\n",
    );
    let mut state = AppState::new(dir.join(".buildloop"));
    state.startup = Some(StartupState::new(
        &dir,
        StartupScenario::NeedsQueue,
        PlanStatus::Missing,
        None,
    ));

    // Press Enter with empty input on NeedsQueue -> opens selected file in explorer
    handle_startup_key(
        &mut state,
        event::KeyEvent::new(KeyCode::Enter, KeyModifiers::NONE),
        &Config::default(),
    );

    // Empty input Enter now triggers explorer action (open file / toggle dir)
    assert!(matches!(
        state.pending_transition,
        Some(PendingTransition::OpenExternalEditor { .. })
    ));
    let _ = std::fs::remove_dir_all(dir);
}

#[test]
fn enter_home_surface_keeps_fresh_directories_on_startup() {
    let dir = temp_project_dir("foundry-home-empty");
    let mut state = AppState::new(dir.join(".buildloop"));

    enter_home_surface(&dir, &mut state, None);

    assert_eq!(state.phase, AppPhase::Startup);
    assert!(state.startup.is_some());
    assert_eq!(
        state.startup.as_ref().map(|startup| startup.scenario),
        Some(StartupScenario::EmptyProject)
    );

    let _ = std::fs::remove_dir_all(dir);
}

#[test]
fn startup_empty_project_describe_work_seeds_spec_before_task_creation() {
    let dir = temp_project_dir("foundry-empty-describe");
    let mut state = AppState::new(dir.join(".buildloop"));
    state.startup = Some(StartupState::new(
        &dir,
        StartupScenario::EmptyProject,
        PlanStatus::Missing,
        None,
    ));

    // EditTasks at index 0 auto-enters intent mode for EmptyProject.
    assert!(state.startup.as_ref().unwrap().entering_intent);

    for c in "build a notes app".chars() {
        handle_startup_key(
            &mut state,
            event::KeyEvent::new(KeyCode::Char(c), KeyModifiers::NONE),
            &Config::default(),
        );
    }

    handle_startup_key(
        &mut state,
        event::KeyEvent::new(KeyCode::Enter, KeyModifiers::NONE),
        &Config::default(),
    );

    // EmptyProject with text now writes SPEC.md and returns to startup for review.
    // The user must press Enter again to start the loop.
    assert!(matches!(
        state.pending_transition,
        Some(PendingTransition::ShowStartup { .. })
    ));

    // Verify SPEC.md was seeded with the user's description
    let spec_path = dir.join("SPEC.md");
    let spec_content = std::fs::read_to_string(&spec_path).expect("SPEC.md should exist");
    assert!(spec_content.contains("build a notes app"));

    let _ = std::fs::remove_dir_all(dir);
}

#[test]
fn seed_spec_from_brief_writes_minimal_spec() {
    let dir = temp_project_dir("foundry-seed-spec");

    seed_spec_from_brief(&dir, "build a CLI todo app").expect("seed spec should succeed");

    let content = std::fs::read_to_string(dir.join("SPEC.md")).expect("missing SPEC.md");
    assert!(content.contains("# Specification:"));
    assert!(content.contains("## Project Brief"));
    assert!(content.contains("build a CLI todo app"));

    let _ = std::fs::remove_dir_all(dir);
}

#[test]
fn prepare_append_tasks_start_works_without_claude_cli() {
    // Task append is deterministic (no LLM) -- claude CLI not required.
    let dir = temp_project_dir("foundry-append-no-claude");
    let mut state = AppState::new(dir.join(".buildloop"));
    let request = super::state::AppendTasksRequest {
        description: "build a notes app".to_string(),
        label: "Describe project: build a notes app".to_string(),
        seed_spec_from_description: true,
    };

    let can_start = prepare_append_tasks_start(&dir, &mut state, &request, false);

    assert!(can_start);
    // SPEC.md seeded from description
    assert!(dir.join("SPEC.md").exists());

    let _ = std::fs::remove_dir_all(dir);
}

#[test]
fn startup_state_loads_plan_preview_and_next_pending_task() {
    let dir = temp_project_dir("foundry-startup-preview");
    write_file(
        &dir.join("Cargo.toml"),
        "[package]\nname = \"demo\"\nversion = \"0.1.0\"\n",
    );
    write_file(
        &dir.join("TASKS.md"),
        "# Plan\n\n- [x] T1.1: Done task\n- [ ] T1.2: Pending task\n",
    );

    let startup = StartupState::new(
        &dir,
        StartupScenario::QueueReady,
        PlanStatus::Pending(1),
        None,
    );
    assert!(!startup.plan_preview_lines.is_empty());
    assert!(startup
        .plan_preview_lines
        .iter()
        .any(|line| line.contains("T1.2")));
    assert_eq!(
        startup.next_pending_task.as_deref(),
        Some("T1.2 — Pending task")
    );

    let _ = std::fs::remove_dir_all(dir);
}

#[test]
fn load_pending_task_at_reads_later_pending_items() {
    let dir = temp_project_dir("foundry-next-pending");
    write_file(
        &dir.join("TASKS.md"),
        "# Plan\n\n- [x] T1.1: Done\n- [ ] T1.2: First\n- [ ] T1.3: Second\n",
    );

    assert_eq!(
        load_pending_task_at(&dir, 0).as_deref(),
        Some("T1.2 — First")
    );
    assert_eq!(
        load_pending_task_at(&dir, 1).as_deref(),
        Some("T1.3 — Second")
    );

    let _ = std::fs::remove_dir_all(dir);
}

#[test]
fn startup_arrow_keys_navigate_file_explorer() {
    let dir = temp_project_dir("foundry-startup-explorer-nav");
    write_file(
        &dir.join("Cargo.toml"),
        "[package]\nname = \"demo\"\nversion = \"0.1.0\"\n",
    );
    write_file(&dir.join("README.md"), "# README\n");
    write_file(&dir.join("TASKS.md"), "# Plan\n\n- [ ] T1.1: One\n");

    let mut state = AppState::new(dir.join(".buildloop"));
    state.startup = Some(StartupState::new(
        &dir,
        StartupScenario::QueueReady,
        PlanStatus::Pending(1),
        None,
    ));

    // Initially selected = TASKS.md (auto-selected as priority CF file)
    let tasks_idx = state
        .startup
        .as_ref()
        .and_then(|s| s.file_tree.iter().position(|e| e.name == "TASKS.md"))
        .unwrap_or(0);
    assert_eq!(
        state.startup.as_ref().map(|s| s.explorer_selected),
        Some(tasks_idx)
    );

    // Press Up to move to previous entry
    let before = state.startup.as_ref().unwrap().explorer_selected;
    handle_startup_key(
        &mut state,
        event::KeyEvent::new(KeyCode::Up, KeyModifiers::NONE),
        &Config::default(),
    );
    let after_up = state.startup.as_ref().unwrap().explorer_selected;
    assert!(
        after_up < before || before == 0,
        "Up should move selection earlier"
    );

    // Press Down to move back
    handle_startup_key(
        &mut state,
        event::KeyEvent::new(KeyCode::Down, KeyModifiers::NONE),
        &Config::default(),
    );
    let after_down = state.startup.as_ref().unwrap().explorer_selected;
    assert!(after_down >= after_up, "Down should move selection later");

    let _ = std::fs::remove_dir_all(dir);
}

#[test]
fn startup_mouse_click_selects_file_entry() {
    let dir = temp_project_dir("foundry-startup-mouse");
    write_file(
        &dir.join("Cargo.toml"),
        "[package]\nname = \"demo\"\nversion = \"0.1.0\"\n",
    );
    write_file(&dir.join("README.md"), "# README\n");

    let mut state = AppState::new(dir.join(".buildloop"));
    state.startup = Some(StartupState::new(
        &dir,
        StartupScenario::QueueReady,
        PlanStatus::Pending(1),
        None,
    ));

    // Click in file explorer area -- should select entry, not trigger transition
    handle_startup_mouse_at(
        &mut state,
        MouseEvent {
            kind: MouseEventKind::Down(MouseButton::Left),
            column: 2,
            row: 9,
            modifiers: KeyModifiers::NONE,
        },
        (140, 40),
    );

    assert!(state.pending_transition.is_none());

    let _ = std::fs::remove_dir_all(dir);
}

#[test]
fn startup_enter_empty_on_queue_ready_starts_build() {
    let dir = temp_project_dir("foundry-startup-enter");
    write_file(
        &dir.join("Cargo.toml"),
        "[package]\nname = \"demo\"\nversion = \"0.1.0\"\n",
    );
    write_file(
        &dir.join("TASKS.md"),
        "# Plan\n\n- [ ] T1.1: Pending task\n",
    );

    let mut state = AppState::new(dir.join(".buildloop"));
    state.startup = Some(StartupState::new(
        &dir,
        StartupScenario::QueueReady,
        PlanStatus::Pending(1),
        None,
    ));

    // Press Enter with empty input -- should start build (QueueReady preserves StartBuild)
    handle_startup_key(
        &mut state,
        event::KeyEvent::new(KeyCode::Enter, KeyModifiers::NONE),
        &Config::default(),
    );

    assert!(matches!(
        state.pending_transition,
        Some(PendingTransition::StartBuild)
    ));

    let _ = std::fs::remove_dir_all(dir);
}

#[test]
fn startup_intent_input_accepts_digits_and_q_without_triggering_shortcuts() {
    let dir = temp_project_dir("foundry-startup-intent-input");
    write_file(
        &dir.join("Cargo.toml"),
        "[package]\nname = \"demo\"\nversion = \"0.1.0\"\n",
    );

    let mut state = AppState::new(dir.join(".buildloop"));
    state.startup = Some(StartupState::new(
        &dir,
        StartupScenario::NeedsQueue,
        PlanStatus::Missing,
        None,
    ));

    // Input is always active now -- type directly
    handle_startup_key(
        &mut state,
        event::KeyEvent::new(KeyCode::Char('1'), KeyModifiers::NONE),
        &Config::default(),
    );
    handle_startup_key(
        &mut state,
        event::KeyEvent::new(KeyCode::Char('q'), KeyModifiers::NONE),
        &Config::default(),
    );

    assert_eq!(
        state
            .startup
            .as_ref()
            .map(|startup| startup.intent_input.as_str()),
        Some("1q")
    );
    assert!(!state.should_quit);
    assert!(state.pending_transition.is_none());

    let _ = std::fs::remove_dir_all(dir);
}

#[test]
fn startup_intent_input_accepts_paste_events() {
    let dir = temp_project_dir("foundry-startup-intent-paste");
    let mut state = AppState::new(dir.join(".buildloop"));
    state.startup = Some(StartupState::new(
        &dir,
        StartupScenario::NeedsQueue,
        PlanStatus::Missing,
        None,
    ));

    // Input is always active -- paste directly
    handle_startup_event(
        &mut state,
        AppEvent::Paste("fix login timeout".to_string()),
        &Config::default(),
    );

    assert_eq!(
        state
            .startup
            .as_ref()
            .map(|startup| startup.intent_input.as_str()),
        Some("fix login timeout")
    );

    let _ = std::fs::remove_dir_all(dir);
}

#[test]
fn startup_clicking_preview_does_not_change_explorer_selection() {
    let dir = temp_project_dir("foundry-startup-preview-jump");
    write_file(
        &dir.join("Cargo.toml"),
        "[package]\nname = \"demo\"\nversion = \"0.1.0\"\n",
    );
    write_file(&dir.join("TASKS.md"), "# Plan\n\n- [ ] T1.1: One\n");

    let mut state = AppState::new(dir.join(".buildloop"));
    state.startup = Some(StartupState::new(
        &dir,
        StartupScenario::QueueReady,
        PlanStatus::Pending(1),
        None,
    ));

    let initial_selected = state.startup.as_ref().map(|s| s.explorer_selected);

    // Click in the preview area (right column) -- should NOT change explorer selection
    handle_startup_mouse_at(
        &mut state,
        MouseEvent {
            kind: MouseEventKind::Down(MouseButton::Left),
            column: 80,
            row: 14,
            modifiers: KeyModifiers::NONE,
        },
        (140, 40),
    );

    assert_eq!(
        state.startup.as_ref().map(|s| s.explorer_selected),
        initial_selected
    );

    let _ = std::fs::remove_dir_all(dir);
}

#[test]
fn startup_scroll_events_are_debounced_immediately_after_click() {
    let dir = temp_project_dir("foundry-startup-scroll-debounce");
    write_file(
        &dir.join("Cargo.toml"),
        "[package]\nname = \"demo\"\nversion = \"0.1.0\"\n",
    );
    write_file(&dir.join("README.md"), "# README\n");
    let _ = std::fs::create_dir_all(dir.join("src"));
    write_file(&dir.join("src/main.rs"), "fn main() {}\n");

    let mut state = AppState::new(dir.join(".buildloop"));
    state.startup = Some(StartupState::new(
        &dir,
        StartupScenario::QueueReady,
        PlanStatus::Pending(1),
        None,
    ));

    let initial_selected = state.startup.as_ref().unwrap().explorer_selected;

    // Click sets debounce
    handle_startup_mouse_at(
        &mut state,
        MouseEvent {
            kind: MouseEventKind::Down(MouseButton::Left),
            column: 80,
            row: 13,
            modifiers: KeyModifiers::NONE,
        },
        (140, 40),
    );

    // Scroll immediately after click -- should be suppressed
    handle_startup_mouse_at(
        &mut state,
        MouseEvent {
            kind: MouseEventKind::ScrollDown,
            column: 2,
            row: 13,
            modifiers: KeyModifiers::NONE,
        },
        (140, 40),
    );

    assert_eq!(
        state.startup.as_ref().unwrap().explorer_selected,
        initial_selected
    );

    // Tick to expire debounce
    let (_event_tx, mut event_rx) = mpsc::unbounded_channel::<AppEvent>();
    process_received_event(
        &mut state,
        AppEvent::Tick,
        &mut event_rx,
        &Config::default(),
    );
    process_received_event(
        &mut state,
        AppEvent::Tick,
        &mut event_rx,
        &Config::default(),
    );

    // Scroll after debounce -- should work now
    handle_startup_mouse_at(
        &mut state,
        MouseEvent {
            kind: MouseEventKind::ScrollDown,
            column: 2,
            row: 13,
            modifiers: KeyModifiers::NONE,
        },
        (140, 40),
    );

    // Explorer selection should have changed (moved by 3)
    assert!(state.startup.as_ref().unwrap().explorer_selected > initial_selected);

    let _ = std::fs::remove_dir_all(dir);
}

#[test]
fn external_editor_transition_returns_file_path() {
    let dir = temp_project_dir("foundry-external-editor");
    write_file(&dir.join("TASKS.md"), "# Task Queue\n\n- [ ] T1.1: One\n");

    let mut state = AppState::new(dir.join(".buildloop"));
    state.pending_transition = Some(PendingTransition::OpenExternalEditor {
        file_path: dir.join("TASKS.md"),
    });

    let event_tx = mpsc::unbounded_channel::<AppEvent>().0;
    let shutdown = std::sync::Arc::new(std::sync::atomic::AtomicBool::new(false));
    let result =
        apply_pending_transition(&dir, &Config::default(), &event_tx, &mut state, &shutdown);

    assert_eq!(result, Some(dir.join("TASKS.md")));
    let _ = std::fs::remove_dir_all(dir);
}

#[test]
fn external_editor_transition_returns_spec_path() {
    let dir = temp_project_dir("foundry-external-editor-spec");

    let mut state = AppState::new(dir.join(".buildloop"));
    state.pending_transition = Some(PendingTransition::OpenExternalEditor {
        file_path: dir.join("SPEC.md"),
    });

    let event_tx = mpsc::unbounded_channel::<AppEvent>().0;
    let shutdown = std::sync::Arc::new(std::sync::atomic::AtomicBool::new(false));
    let result =
        apply_pending_transition(&dir, &Config::default(), &event_tx, &mut state, &shutdown);

    assert_eq!(result, Some(dir.join("SPEC.md")));
    let _ = std::fs::remove_dir_all(dir);
}

#[test]
fn planning_success_with_tasks_transitions_to_running() {
    let mut state = AppState::new(PathBuf::from(".buildloop"));
    apply_planning_outcome(
        &mut state,
        PlanningOutcome {
            success: true,
            total_tasks: 3,
            pending_tasks: 2,
            completed_tasks: 1,
            new_tasks: 2,
            error: None,
            return_to_startup: false,
        },
    );

    assert!(matches!(
        state.pending_transition,
        Some(PendingTransition::StartBuild)
    ));
}

#[test]
fn planning_success_with_no_tasks_returns_to_startup() {
    let mut state = AppState::new(PathBuf::from(".buildloop"));
    apply_planning_outcome(
        &mut state,
        PlanningOutcome {
            success: true,
            total_tasks: 0,
            pending_tasks: 0,
            completed_tasks: 0,
            new_tasks: 0,
            error: None,
            return_to_startup: false,
        },
    );

    assert!(matches!(
        state.pending_transition,
        Some(PendingTransition::ShowStartup { .. })
    ));
}

#[test]
fn planning_failure_returns_to_startup() {
    let mut state = AppState::new(PathBuf::from(".buildloop"));
    apply_planning_outcome(
        &mut state,
        PlanningOutcome {
            success: false,
            total_tasks: 0,
            pending_tasks: 0,
            completed_tasks: 0,
            new_tasks: 0,
            error: Some("planner failed".to_string()),
            return_to_startup: false,
        },
    );

    assert!(matches!(
        state.pending_transition,
        Some(PendingTransition::ShowStartup { .. })
    ));
}

#[test]
fn late_planning_finished_is_logged_in_running_phase() {
    let mut state = AppState::new(PathBuf::from(".buildloop"));
    handle_event(
        &mut state,
        AppEvent::PlanningFinished(PlanningOutcome {
            success: true,
            total_tasks: 4,
            pending_tasks: 1,
            completed_tasks: 3,
            new_tasks: 0,
            error: None,
            return_to_startup: false,
        }),
        &Config::default(),
    );

    assert!(state
        .log_messages
        .last()
        .map(|(_, msg)| msg.contains("Ignoring late planning result while running"))
        .unwrap_or(false));
}

#[test]
fn next_task_update_event_refreshes_running_queue_hint() {
    let mut state = AppState::new(PathBuf::from(".buildloop"));
    handle_event(
        &mut state,
        AppEvent::LoopEvent(LoopEvent::NextTaskUpdated(Some(
            "T2.4 — Wire auth callbacks".to_string(),
        ))),
        &Config::default(),
    );

    assert_eq!(
        state.next_task_hint.as_deref(),
        Some("T2.4 — Wire auth callbacks")
    );
}

#[test]
fn startup_typing_and_enter_queues_append_transition() {
    let dir = temp_project_dir("foundry-startup-describe-work");
    write_file(
        &dir.join("Cargo.toml"),
        "[package]\nname = \"demo\"\nversion = \"0.1.0\"\n",
    );
    write_file(
        &dir.join("TASKS.md"),
        "# Plan\n\n- [ ] T1.1: Pending task\n",
    );

    let mut state = AppState::new(dir.join(".buildloop"));
    state.startup = Some(StartupState::new(
        &dir,
        StartupScenario::QueueReady,
        PlanStatus::Pending(1),
        None,
    ));

    // Type a description directly (input is always active)
    for c in "fix the login timeout".chars() {
        handle_startup_key(
            &mut state,
            event::KeyEvent::new(KeyCode::Char(c), KeyModifiers::NONE),
            &Config::default(),
        );
    }

    // Press Enter
    handle_startup_key(
        &mut state,
        event::KeyEvent::new(KeyCode::Enter, KeyModifiers::NONE),
        &Config::default(),
    );

    assert!(matches!(
        state.pending_transition,
        Some(PendingTransition::AppendTasks(_))
    ));

    let _ = std::fs::remove_dir_all(dir);
}

#[test]
fn startup_empty_input_on_needs_queue_starts_build() {
    let dir = temp_project_dir("foundry-startup-scan-empty");
    write_file(
        &dir.join("Cargo.toml"),
        "[package]\nname = \"demo\"\nversion = \"0.1.0\"\n",
    );

    let mut state = AppState::new(dir.join(".buildloop"));
    state.startup = Some(StartupState::new(
        &dir,
        StartupScenario::NeedsQueue,
        PlanStatus::Missing,
        None,
    ));

    // Press Enter with empty input -> opens selected file in explorer
    handle_startup_key(
        &mut state,
        event::KeyEvent::new(KeyCode::Enter, KeyModifiers::NONE),
        &Config::default(),
    );

    // Empty input Enter now triggers explorer action (open file / toggle dir)
    assert!(matches!(
        state.pending_transition,
        Some(PendingTransition::OpenExternalEditor { .. })
    ));

    let _ = std::fs::remove_dir_all(dir);
}

#[test]
fn startup_text_input_on_needs_queue_starts_build() {
    let dir = temp_project_dir("foundry-startup-scan-focus");
    write_file(
        &dir.join("Cargo.toml"),
        "[package]\nname = \"demo\"\nversion = \"0.1.0\"\n",
    );

    let mut state = AppState::new(dir.join(".buildloop"));
    state.startup = Some(StartupState::new(
        &dir,
        StartupScenario::NeedsQueue,
        PlanStatus::Missing,
        None,
    ));

    // Type focus text
    for c in "auth bugs".chars() {
        handle_startup_key(
            &mut state,
            event::KeyEvent::new(KeyCode::Char(c), KeyModifiers::NONE),
            &Config::default(),
        );
    }

    handle_startup_key(
        &mut state,
        event::KeyEvent::new(KeyCode::Enter, KeyModifiers::NONE),
        &Config::default(),
    );

    // NeedsQueue with text treats input as a task description (AppendTasks),
    // not a SPEC.md overwrite. SPEC.md already exists in NeedsQueue scenario.
    match &state.pending_transition {
        Some(PendingTransition::AppendTasks(req)) => {
            assert!(
                req.description.contains("auth bugs"),
                "expected description to contain user input, got: {}",
                req.description
            );
        }
        other => panic!("expected AppendTasks transition, got: {:?}", other),
    }

    let _ = std::fs::remove_dir_all(dir);
}

#[test]
fn scan_outcome_with_pending_tasks_starts_build() {
    let mut state = AppState::new(PathBuf::from(".buildloop"));
    apply_planning_outcome(
        &mut state,
        PlanningOutcome {
            success: true,
            total_tasks: 5,
            pending_tasks: 3,
            completed_tasks: 2,
            new_tasks: 2,
            error: None,
            return_to_startup: false,
        },
    );

    assert!(matches!(
        state.pending_transition,
        Some(PendingTransition::StartBuild)
    ));
}

#[test]
fn describe_work_outcome_returns_to_startup_for_review() {
    let mut state = AppState::new(PathBuf::from(".buildloop"));
    apply_planning_outcome(
        &mut state,
        PlanningOutcome {
            success: true,
            total_tasks: 5,
            pending_tasks: 3,
            completed_tasks: 2,
            new_tasks: 2,
            error: None,
            return_to_startup: true,
        },
    );

    match &state.pending_transition {
        Some(PendingTransition::ShowStartup { message }) => {
            assert_eq!(
                message.as_deref(),
                Some("Added 2 task(s) — 3 pending. Review the queue, then Continue when ready.")
            );
        }
        other => panic!("expected ShowStartup transition, got {:?}", other),
    }
}

// ─── Running-mode tests ──────────────────────────────────────

#[test]
fn running_page_up_down_scrolls_task_queue() {
    let mut state = AppState::new(PathBuf::from(".buildloop"));
    state.phase = AppPhase::Running;
    // Populate task queue so scroll cap has room
    for i in 0..20 {
        state.task_queue.push(crate::task::Task {
            id: format!("T1.{}", i),
            description: format!("Task {}", i),
            line_number: i + 1,
            completed: false,
            pipeline_progress: None,
            override_flag: crate::complexity::TaskOverride::None,
        });
    }

    handle_event(
        &mut state,
        AppEvent::Key(event::KeyEvent::new(KeyCode::PageUp, KeyModifiers::NONE)),
        &Config::default(),
    );
    assert_eq!(state.task_queue_scroll, 3);

    handle_event(
        &mut state,
        AppEvent::Key(event::KeyEvent::new(KeyCode::PageDown, KeyModifiers::NONE)),
        &Config::default(),
    );
    assert_eq!(state.task_queue_scroll, 0);
}

#[test]
fn running_inject_input_accepts_paste_events() {
    let mut state = AppState::new(PathBuf::from(".buildloop"));
    state.phase = AppPhase::Running;
    state.inject_input = Some(String::new());

    handle_event(
        &mut state,
        AppEvent::Paste("fix flaky auth test".to_string()),
        &Config::default(),
    );

    assert_eq!(state.inject_input.as_deref(), Some("fix flaky auth test"));
}

#[test]
fn running_p_toggles_patterns_view_and_returns_to_previous() {
    let mut state = AppState::new(PathBuf::from(".buildloop"));
    state.phase = AppPhase::Running;

    // Start on main view
    assert!(!state.show_patterns);

    // p -> patterns
    handle_event(
        &mut state,
        AppEvent::Key(event::KeyEvent::new(KeyCode::Char('p'), KeyModifiers::NONE)),
        &Config::default(),
    );
    assert!(state.show_patterns);

    // p -> back to main view
    handle_event(
        &mut state,
        AppEvent::Key(event::KeyEvent::new(KeyCode::Char('p'), KeyModifiers::NONE)),
        &Config::default(),
    );
    assert!(!state.show_patterns);
}

#[test]
fn running_patterns_scroll_uses_natural_direction() {
    let mut state = AppState::new(PathBuf::from(".buildloop"));
    state.phase = AppPhase::Running;
    state.show_patterns = true;

    // Down scrolls deeper (increases offset)
    handle_event(
        &mut state,
        AppEvent::Key(event::KeyEvent::new(KeyCode::Down, KeyModifiers::NONE)),
        &Config::default(),
    );
    assert_eq!(state.patterns_scroll, 3);

    // Up scrolls back toward top (decreases offset)
    handle_event(
        &mut state,
        AppEvent::Key(event::KeyEvent::new(KeyCode::Up, KeyModifiers::NONE)),
        &Config::default(),
    );
    assert_eq!(state.patterns_scroll, 0);
}

#[test]
fn running_s_toggles_stats_overlay() {
    let mut state = AppState::new(PathBuf::from(".buildloop"));
    state.phase = AppPhase::Running;

    // Start with overlay manually enabled (compute won't work without observatory dir)
    assert!(!state.show_stats_overlay);
    state.show_stats_overlay = true;

    // s -> dismiss overlay
    handle_event(
        &mut state,
        AppEvent::Key(event::KeyEvent::new(KeyCode::Char('s'), KeyModifiers::NONE)),
        &Config::default(),
    );
    assert!(!state.show_stats_overlay);
    assert!(state.stats_overlay_report.is_none());
    assert_eq!(state.stats_overlay_scroll, 0);
}

#[test]
fn running_stats_overlay_scroll_uses_natural_direction() {
    let mut state = AppState::new(PathBuf::from(".buildloop"));
    state.phase = AppPhase::Running;
    state.show_stats_overlay = true;

    // Down scrolls deeper (increases offset)
    handle_event(
        &mut state,
        AppEvent::Key(event::KeyEvent::new(KeyCode::Down, KeyModifiers::NONE)),
        &Config::default(),
    );
    assert_eq!(state.stats_overlay_scroll, 3);

    // Up scrolls back toward top (decreases offset)
    handle_event(
        &mut state,
        AppEvent::Key(event::KeyEvent::new(KeyCode::Up, KeyModifiers::NONE)),
        &Config::default(),
    );
    assert_eq!(state.stats_overlay_scroll, 0);
}

#[test]
fn running_queue_updated_event_populates_task_queue() {
    let mut state = AppState::new(PathBuf::from(".buildloop"));
    let tasks = vec![
        Task {
            id: "T1.1".to_string(),
            description: "First task".to_string(),
            line_number: 3,
            completed: true,
            pipeline_progress: None,
            override_flag: crate::complexity::TaskOverride::None,
        },
        Task {
            id: "T1.2".to_string(),
            description: "Second task".to_string(),
            line_number: 4,
            completed: false,
            pipeline_progress: None,
            override_flag: crate::complexity::TaskOverride::None,
        },
    ];

    handle_event(
        &mut state,
        AppEvent::LoopEvent(LoopEvent::QueueUpdated(tasks)),
        &Config::default(),
    );

    assert_eq!(state.task_queue.len(), 2);
    assert!(state.task_queue[0].completed);
    assert!(!state.task_queue[1].completed);
}

#[test]
fn test_orchestrator_outcome_accepted_shows_startup() {
    let dir = temp_project_dir("foundry-orch-accepted");
    let mut state = AppState::new(dir.join(".buildloop"));
    state.phase = AppPhase::Planning;

    let outcome = OrchestratorOutcome {
        artifact: ProposerOutput {
            artifact_type: "plan".to_string(),
            artifact_text: "Build X".to_string(),
            rationale: "Because".to_string(),
            design_assertions: Vec::new(),
        },
        final_review: ReviewerOutput {
            status: "clean".to_string(),
            findings: Vec::new(),
            validated: Vec::new(),
        },
        iterations: 2,
        accepted: true,
    };

    apply_orchestrator_outcome(&mut state, outcome);

    match &state.pending_transition {
        Some(PendingTransition::ShowStartup { message: Some(m) }) => {
            assert!(
                m.contains("accepted"),
                "message should contain 'accepted': {}",
                m
            );
            assert!(
                m.contains("2 iteration(s)"),
                "message should contain '2 iteration(s)': {}",
                m
            );
        }
        other => panic!("expected ShowStartup transition, got {:?}", other),
    }
    let _ = std::fs::remove_dir_all(dir);
}

#[test]
fn test_orchestrator_outcome_unresolved_shows_startup() {
    let dir = temp_project_dir("foundry-orch-unresolved");
    let mut state = AppState::new(dir.join(".buildloop"));
    state.phase = AppPhase::Planning;

    let outcome = OrchestratorOutcome {
        artifact: ProposerOutput {
            artifact_type: "plan".to_string(),
            artifact_text: "Build X".to_string(),
            rationale: "Because".to_string(),
            design_assertions: Vec::new(),
        },
        final_review: ReviewerOutput {
            status: "findings".to_string(),
            findings: Vec::new(),
            validated: Vec::new(),
        },
        iterations: 3,
        accepted: false,
    };

    apply_orchestrator_outcome(&mut state, outcome);

    match &state.pending_transition {
        Some(PendingTransition::ShowStartup { message: Some(m) }) => {
            assert!(
                m.contains("unresolved findings"),
                "message should contain 'unresolved findings': {}",
                m
            );
            assert!(
                m.contains("3 iteration(s)"),
                "message should contain '3 iteration(s)': {}",
                m
            );
        }
        other => panic!("expected ShowStartup transition, got {:?}", other),
    }
    let _ = std::fs::remove_dir_all(dir);
}

// ─── Orchestrator TUI integration tests ──────────────────────

// test_design_with_review_intent_enter_creates_start_design_transition removed:
// DesignWithReview is no longer in the startup action lists (available via `foundry design` CLI)

// test_design_with_review_intent_enter_rejects_empty removed:
// DesignWithReview is no longer in the startup action lists (available via `foundry design` CLI)

#[test]
fn test_planning_header_orchestrator_mode_initial_state() {
    let mut state = AppState::new(PathBuf::from(".buildloop"));
    state.phase = AppPhase::Planning;
    state.planning = Some(PlanningState {
        label: "Design: build API".to_string(),
        user_intent: Some("build API".to_string()),
        orchestrator_mode: true,
        orchestrator_iteration: 0,
        orchestrator_max_iterations: 3,
        orchestrator_finding_count: 0,
        orchestrator_role_label: None,
        orchestrator_role_model: None,
    });
    let planning = state.planning.as_ref().unwrap();
    assert!(planning.orchestrator_mode);
    assert_eq!(planning.orchestrator_iteration, 0);
    assert_eq!(planning.orchestrator_max_iterations, 3);
    assert!(planning.orchestrator_role_label.is_none());
    assert_eq!(planning.orchestrator_finding_count, 0);
}

#[test]
fn test_planning_event_iteration_line_updates_iteration_count() {
    let mut state = AppState::new(PathBuf::from(".buildloop"));
    state.phase = AppPhase::Planning;
    state.planning = Some(PlanningState {
        label: "Design: test".to_string(),
        user_intent: None,
        orchestrator_mode: true,
        orchestrator_iteration: 0,
        orchestrator_max_iterations: 3,
        orchestrator_finding_count: 0,
        orchestrator_role_label: None,
        orchestrator_role_model: None,
    });
    let (_event_tx, mut event_rx) = mpsc::unbounded_channel::<AppEvent>();
    process_received_event(
        &mut state,
        AppEvent::AgentOutput(AgentOutputEvent::Text(
            "[orchestrator] Iteration 2/3: proposer (Claude opus)".to_string(),
        )),
        &mut event_rx,
        &Config::default(),
    );
    let planning = state.planning.as_ref().unwrap();
    assert_eq!(planning.orchestrator_iteration, 2);
    assert_eq!(
        planning.orchestrator_role_label.as_deref(),
        Some("Proposing")
    );
    assert_eq!(
        planning.orchestrator_role_model.as_deref(),
        Some("Claude opus")
    );
}

#[test]
fn test_planning_event_reviewing_line_updates_role() {
    let mut state = AppState::new(PathBuf::from(".buildloop"));
    state.phase = AppPhase::Planning;
    state.planning = Some(PlanningState {
        label: "Design: test".to_string(),
        user_intent: None,
        orchestrator_mode: true,
        orchestrator_iteration: 1,
        orchestrator_max_iterations: 3,
        orchestrator_finding_count: 0,
        orchestrator_role_label: None,
        orchestrator_role_model: None,
    });
    let (_event_tx, mut event_rx) = mpsc::unbounded_channel::<AppEvent>();
    process_received_event(
        &mut state,
        AppEvent::AgentOutput(AgentOutputEvent::Text(
            "[orchestrator] Reviewing with Codex codex-5.4...".to_string(),
        )),
        &mut event_rx,
        &Config::default(),
    );
    let planning = state.planning.as_ref().unwrap();
    assert_eq!(
        planning.orchestrator_role_label.as_deref(),
        Some("Reviewing")
    );
    assert_eq!(
        planning.orchestrator_role_model.as_deref(),
        Some("Codex codex-5.4")
    );
}

#[test]
fn test_planning_event_review_line_updates_finding_count() {
    let mut state = AppState::new(PathBuf::from(".buildloop"));
    state.phase = AppPhase::Planning;
    state.planning = Some(PlanningState {
        label: "Design: test".to_string(),
        user_intent: None,
        orchestrator_mode: true,
        orchestrator_iteration: 0,
        orchestrator_max_iterations: 0,
        orchestrator_finding_count: 0,
        orchestrator_role_label: None,
        orchestrator_role_model: None,
    });
    let (_event_tx, mut event_rx) = mpsc::unbounded_channel::<AppEvent>();
    process_received_event(
        &mut state,
        AppEvent::AgentOutput(AgentOutputEvent::Text(
            "[orchestrator] Review: findings (3 issues found)".to_string(),
        )),
        &mut event_rx,
        &Config::default(),
    );
    assert_eq!(
        state.planning.as_ref().unwrap().orchestrator_finding_count,
        3
    );
}

#[test]
fn test_planning_event_non_orchestrator_mode_ignores_orchestrator_lines() {
    let mut state = AppState::new(PathBuf::from(".buildloop"));
    state.phase = AppPhase::Planning;
    state.planning = Some(PlanningState {
        label: "Planning: scan".to_string(),
        user_intent: None,
        orchestrator_mode: false,
        orchestrator_iteration: 0,
        orchestrator_max_iterations: 0,
        orchestrator_finding_count: 0,
        orchestrator_role_label: None,
        orchestrator_role_model: None,
    });
    let (_event_tx, mut event_rx) = mpsc::unbounded_channel::<AppEvent>();
    process_received_event(
        &mut state,
        AppEvent::AgentOutput(AgentOutputEvent::Text(
            "[orchestrator] Iteration 2/3: proposer (Claude opus)".to_string(),
        )),
        &mut event_rx,
        &Config::default(),
    );
    let planning = state.planning.as_ref().unwrap();
    assert_eq!(planning.orchestrator_iteration, 0);
    assert!(planning.orchestrator_role_label.is_none());
}

#[test]
fn test_orchestrator_outcome_with_findings_enables_findings_panel() {
    let mut state = AppState::new(PathBuf::from(".buildloop"));
    state.phase = AppPhase::Planning;
    let outcome = OrchestratorOutcome {
        artifact: ProposerOutput {
            artifact_type: "plan".to_string(),
            artifact_text: "Build API".to_string(),
            rationale: "Because".to_string(),
            design_assertions: Vec::new(),
        },
        final_review: ReviewerOutput {
            status: "findings".to_string(),
            findings: vec![
                Finding {
                    severity: "high".to_string(),
                    description: "Missing error handling".to_string(),
                    location: "src/main.rs:42".to_string(),
                    suggestion: "Add Result return type".to_string(),
                },
                Finding {
                    severity: "medium".to_string(),
                    description: "No input validation".to_string(),
                    location: "src/api.rs:10".to_string(),
                    suggestion: "Add bounds check".to_string(),
                },
            ],
            validated: Vec::new(),
        },
        iterations: 2,
        accepted: false,
    };
    apply_orchestrator_outcome(&mut state, outcome);
    assert!(state.show_findings);
    assert_eq!(state.findings_scroll, 0);
    assert!(state.last_orchestrator_outcome.is_some());
    let saved = state.last_orchestrator_outcome.as_ref().unwrap();
    assert_eq!(saved.final_review.findings.len(), 2);
    assert_eq!(saved.final_review.findings[0].severity, "high");
    assert_eq!(saved.final_review.findings[1].severity, "medium");
    assert!(!saved.accepted);
}

#[test]
fn test_orchestrator_outcome_accepted_does_not_enable_findings_panel() {
    let mut state = AppState::new(PathBuf::from(".buildloop"));
    state.phase = AppPhase::Planning;
    let outcome = OrchestratorOutcome {
        artifact: ProposerOutput {
            artifact_type: "plan".to_string(),
            artifact_text: "Build API".to_string(),
            rationale: "Done".to_string(),
            design_assertions: Vec::new(),
        },
        final_review: ReviewerOutput {
            status: "pass".to_string(),
            findings: Vec::new(),
            validated: vec!["Claim A".to_string(), "Claim B".to_string()],
        },
        iterations: 1,
        accepted: true,
    };
    apply_orchestrator_outcome(&mut state, outcome);
    assert!(!state.show_findings);
    assert!(state.last_orchestrator_outcome.is_some());
    assert_eq!(
        state
            .last_orchestrator_outcome
            .as_ref()
            .unwrap()
            .final_review
            .validated
            .len(),
        2
    );
}

#[test]
fn test_agent_output_forwarding_produces_visible_events() {
    let mut state = AppState::new(PathBuf::from(".buildloop"));
    state.phase = AppPhase::Planning;
    state.planning = Some(PlanningState {
        label: "Design: test".to_string(),
        user_intent: None,
        orchestrator_mode: true,
        orchestrator_iteration: 1,
        orchestrator_max_iterations: 3,
        orchestrator_finding_count: 0,
        orchestrator_role_label: None,
        orchestrator_role_model: None,
    });
    let (_event_tx, mut event_rx) = mpsc::unbounded_channel::<AppEvent>();

    process_received_event(
        &mut state,
        AppEvent::AgentOutput(AgentOutputEvent::Text("Hello from proposer".to_string())),
        &mut event_rx,
        &Config::default(),
    );
    assert_eq!(state.agent_output.len(), 1);
    assert_eq!(state.agent_output[0], "Hello from proposer");
    assert_eq!(state.events_received, 1);

    process_received_event(
        &mut state,
        AppEvent::AgentOutput(AgentOutputEvent::ToolUse {
            tool: "Read".to_string(),
            input_preview: "src/main.rs".to_string(),
        }),
        &mut event_rx,
        &Config::default(),
    );
    assert_eq!(state.agent_output.len(), 2);
    assert!(state.agent_output[1].contains("[tool] Read"));
    assert_eq!(state.events_received, 2);

    process_received_event(
        &mut state,
        AppEvent::AgentOutput(AgentOutputEvent::ToolResult {
            output_preview: "fn main() {}".to_string(),
        }),
        &mut event_rx,
        &Config::default(),
    );
    assert_eq!(state.agent_output.len(), 3);
    assert!(state.agent_output[2].contains("[result]"));
    assert_eq!(state.events_received, 3);
}

#[test]
fn test_planning_log_line_suppressed_when_dominated_by_header() {
    let mut state = AppState::new(PathBuf::from(".buildloop"));
    state.phase = AppPhase::Planning;
    state.planning = Some(PlanningState {
        label: "Generate SPEC.md".to_string(),
        user_intent: Some("build an API".to_string()),
        orchestrator_mode: false,
        orchestrator_iteration: 0,
        orchestrator_max_iterations: 0,
        orchestrator_finding_count: 0,
        orchestrator_role_label: None,
        orchestrator_role_model: None,
    });
    state.log("Planning started — Generate SPEC.md".to_string());
    let (_ts, msg) = state.log_messages.last().unwrap();
    let dominated_by_header = state
        .planning
        .as_ref()
        .map(|p| msg.contains(&p.label))
        .unwrap_or(false)
        || state
            .current_task
            .as_ref()
            .map(|t| msg.contains(&t.id))
            .unwrap_or(false);
    assert!(
        dominated_by_header,
        "Log line containing planning label should be suppressed"
    );
}

#[test]
fn test_planning_log_line_shown_when_not_dominated() {
    let mut state = AppState::new(PathBuf::from(".buildloop"));
    state.phase = AppPhase::Planning;
    state.planning = Some(PlanningState {
        label: "Generate SPEC.md".to_string(),
        user_intent: Some("build an API".to_string()),
        orchestrator_mode: false,
        orchestrator_iteration: 0,
        orchestrator_max_iterations: 0,
        orchestrator_finding_count: 0,
        orchestrator_role_label: None,
        orchestrator_role_model: None,
    });
    state.log("Matched 3 patterns for task".to_string());
    let (_ts, msg) = state.log_messages.last().unwrap();
    let dominated_by_header = state
        .planning
        .as_ref()
        .map(|p| msg.contains(&p.label))
        .unwrap_or(false)
        || state
            .current_task
            .as_ref()
            .map(|t| msg.contains(&t.id))
            .unwrap_or(false);
    assert!(
        !dominated_by_header,
        "Unrelated log line should not be suppressed"
    );
}

#[test]
fn test_design_log_line_suppressed_when_dominated_by_header() {
    let mut state = AppState::new(PathBuf::from(".buildloop"));
    state.phase = AppPhase::Planning;
    state.planning = Some(PlanningState {
        label: "Design: build API".to_string(),
        user_intent: Some("build API".to_string()),
        orchestrator_mode: true,
        orchestrator_iteration: 0,
        orchestrator_max_iterations: 3,
        orchestrator_finding_count: 0,
        orchestrator_role_label: None,
        orchestrator_role_model: None,
    });
    state.log("Design started — Design: build API".to_string());
    let (_ts, msg) = state.log_messages.last().unwrap();
    let dominated_by_header = state
        .planning
        .as_ref()
        .map(|p| msg.contains(&p.label))
        .unwrap_or(false)
        || state
            .current_task
            .as_ref()
            .map(|t| msg.contains(&t.id))
            .unwrap_or(false);
    assert!(
        dominated_by_header,
        "Design log line containing planning label should be suppressed"
    );
}

#[test]
fn test_running_task_log_line_suppressed_when_dominated_by_task_id() {
    let mut state = AppState::new(PathBuf::from(".buildloop"));
    state.phase = AppPhase::Running;
    state.current_task = Some(crate::task::Task {
        id: "T6.1".to_string(),
        description: "Fix header duplication".to_string(),
        line_number: 47,
        completed: false,
        pipeline_progress: None,
        override_flag: crate::complexity::TaskOverride::None,
    });
    state.log("Task T6.1 started".to_string());
    let (_ts, msg) = state.log_messages.last().unwrap();
    let dominated_by_header = state
        .planning
        .as_ref()
        .map(|p| msg.contains(&p.label))
        .unwrap_or(false)
        || state
            .current_task
            .as_ref()
            .map(|t| msg.contains(&t.id))
            .unwrap_or(false);
    assert!(
        dominated_by_header,
        "Log line containing current task ID should be suppressed"
    );
}

#[test]
fn test_background_log_does_not_overwrite_agent_state() {
    let mut state = AppState::new(PathBuf::from("/tmp/test"));
    state.set_agent(AgentRole::Builder, "opus");
    state.agent_output.push("builder output line".to_string());
    state.task_stages_seen = vec![AgentRole::Planner, AgentRole::Builder];

    handle_event(
        &mut state,
        AppEvent::LoopEvent(LoopEvent::BackgroundLog(
            "Background pattern extraction started".to_string(),
        )),
        &Config::default(),
    );

    assert!(matches!(state.current_agent, Some((AgentRole::Builder, _))));
    assert_eq!(state.agent_output.len(), 1);
    assert_eq!(state.agent_output[0], "builder output line");
    assert_eq!(
        state.task_stages_seen,
        vec![AgentRole::Planner, AgentRole::Builder]
    );
    let (_ts, msg) = state.log_messages.last().unwrap();
    assert!(msg.contains("Background pattern extraction started"));
}

#[test]
fn test_background_log_tracks_pattern_count() {
    let mut state = AppState::new(PathBuf::from("/tmp/test"));
    assert_eq!(state.session_patterns_learned, 0);

    handle_event(
        &mut state,
        AppEvent::LoopEvent(LoopEvent::BackgroundLog(
            "Merged patterns: 3 new added to /path".to_string(),
        )),
        &Config::default(),
    );

    assert_eq!(state.session_patterns_learned, 3);
}

#[test]
fn test_agent_started_discovery_overwrites_agent_state() {
    let mut state = AppState::new(PathBuf::from("/tmp/test"));
    state.set_agent(AgentRole::Builder, "opus");
    state.agent_output.push("builder output line".to_string());
    state.task_stages_seen = vec![AgentRole::Planner, AgentRole::Builder];

    handle_event(
        &mut state,
        AppEvent::LoopEvent(LoopEvent::AgentStarted(
            AgentRole::Discovery,
            "opus".to_string(),
        )),
        &Config::default(),
    );

    assert!(matches!(
        state.current_agent,
        Some((AgentRole::Discovery, _))
    ));
    assert!(state.agent_output.is_empty());
    assert!(state.task_stages_seen.contains(&AgentRole::Discovery));
}

#[test]
fn test_dual_build_started_initializes_per_pipeline_stats() {
    let mut state = AppState::new(PathBuf::from(".buildloop"));

    handle_event(
        &mut state,
        AppEvent::LoopEvent(LoopEvent::DualBuildStarted {
            models: ["Claude".to_string(), "Codex".to_string()],
        }),
        &Config::default(),
    );

    assert!(state.dual_build.active);
    assert_eq!(state.dual_build.tab, 0);
    assert_eq!(
        state.dual_build.models,
        ["Claude".to_string(), "Codex".to_string()]
    );
    assert_eq!(state.dual_build.cost_usd, [0.0, 0.0]);
    assert_eq!(state.dual_build.input_tokens, [0, 0]);
    assert_eq!(state.dual_build.output_tokens, [0, 0]);
    assert_eq!(state.dual_build.context_pcts, [[None; 5]; 2]);
}

#[test]
fn test_dual_pipeline_usage_updates_pipeline_slot_and_session_totals() {
    let mut state = AppState::new(PathBuf::from(".buildloop"));

    handle_event(
        &mut state,
        AppEvent::LoopEvent(LoopEvent::DualBuildStarted {
            models: ["Claude".to_string(), "Codex".to_string()],
        }),
        &Config::default(),
    );

    handle_event(
        &mut state,
        AppEvent::DualPipelineEvent(
            1,
            Box::new(AppEvent::LoopEvent(LoopEvent::AgentStarted(
                AgentRole::Builder,
                "Codex".to_string(),
            ))),
        ),
        &Config::default(),
    );

    handle_event(
        &mut state,
        AppEvent::DualPipelineEvent(
            1,
            Box::new(AppEvent::AgentOutput(AgentOutputEvent::Usage {
                cost_usd: 1.25,
                input_tokens: 1_000,
                output_tokens: 250,
                context_window: 2_500,
                cache_creation_tokens: 0,
                cache_read_tokens: 0,
            })),
        ),
        &Config::default(),
    );

    assert!((state.session_cost_usd - 1.25).abs() < f64::EPSILON);
    assert_eq!(state.session_input_tokens, 1_000);
    assert_eq!(state.session_output_tokens, 250);
    assert_eq!(
        state.session_cost_millicents.load(Ordering::Relaxed),
        125_000
    );
    assert!((state.dual_build.cost_usd[0] - 0.0).abs() < f64::EPSILON);
    assert_eq!(state.dual_build.input_tokens[0], 0);
    assert_eq!(state.dual_build.output_tokens[0], 0);
    assert_eq!(state.dual_build.context_pcts[0], [None; 5]);
    assert!((state.dual_build.cost_usd[1] - 1.25).abs() < f64::EPSILON);
    assert_eq!(state.dual_build.input_tokens[1], 1_000);
    assert_eq!(state.dual_build.output_tokens[1], 250);
    assert_eq!(
        state.dual_build.context_pcts[1],
        [None, None, None, Some(50), None]
    );

    handle_event(
        &mut state,
        AppEvent::DualPipelineEvent(
            0,
            Box::new(AppEvent::LoopEvent(LoopEvent::AgentStarted(
                AgentRole::Scout,
                "Claude".to_string(),
            ))),
        ),
        &Config::default(),
    );

    handle_event(
        &mut state,
        AppEvent::DualPipelineEvent(
            0,
            Box::new(AppEvent::AgentOutput(AgentOutputEvent::Usage {
                cost_usd: 0.75,
                input_tokens: 400,
                output_tokens: 100,
                context_window: 1_000,
                cache_creation_tokens: 0,
                cache_read_tokens: 0,
            })),
        ),
        &Config::default(),
    );

    assert!((state.session_cost_usd - 2.0).abs() < f64::EPSILON);
    assert_eq!(state.session_input_tokens, 1_400);
    assert_eq!(state.session_output_tokens, 350);
    assert!((state.dual_build.cost_usd[0] - 0.75).abs() < f64::EPSILON);
    assert_eq!(state.dual_build.input_tokens[0], 400);
    assert_eq!(state.dual_build.output_tokens[0], 100);
    assert_eq!(
        state.dual_build.context_pcts[0],
        [None, Some(50), None, None, None]
    );
    assert!((state.dual_build.cost_usd[1] - 1.25).abs() < f64::EPSILON);
    assert_eq!(state.dual_build.input_tokens[1], 1_000);
    assert_eq!(state.dual_build.output_tokens[1], 250);
    assert_eq!(
        state.dual_build.context_pcts[1],
        [None, None, None, Some(50), None]
    );
}

#[test]
fn test_single_pipeline_query_and_research_update_qrpba_slots_0_and_1() {
    let mut state = AppState::new(PathBuf::from(".buildloop"));
    let config = Config::default();

    // AgentRole::Query -> slot 0 (Q).
    handle_event(
        &mut state,
        AppEvent::LoopEvent(LoopEvent::AgentStarted(
            AgentRole::Query,
            "claude:sonnet".to_string(),
        )),
        &config,
    );
    handle_event(
        &mut state,
        AppEvent::AgentOutput(AgentOutputEvent::Usage {
            cost_usd: 0.10,
            input_tokens: 200,
            output_tokens: 50,
            context_window: 1_000,
            cache_creation_tokens: 0,
            cache_read_tokens: 0,
        }),
        &config,
    );
    assert_eq!(
        state.spid_context_pcts,
        [Some(25), None, None, None, None],
        "Query usage must land in slot 0"
    );

    // AgentRole::Research -> slot 1 (R).
    handle_event(
        &mut state,
        AppEvent::LoopEvent(LoopEvent::AgentStarted(
            AgentRole::Research,
            "claude:opus".to_string(),
        )),
        &config,
    );
    handle_event(
        &mut state,
        AppEvent::AgentOutput(AgentOutputEvent::Usage {
            cost_usd: 0.20,
            input_tokens: 300,
            output_tokens: 100,
            context_window: 1_000,
            cache_creation_tokens: 0,
            cache_read_tokens: 0,
        }),
        &config,
    );
    assert_eq!(
        state.spid_context_pcts,
        [Some(25), Some(40), None, None, None],
        "Research usage must land in slot 1 without disturbing slot 0"
    );
}

#[test]
fn test_custom_pipeline_stage_usage_updates_stage_context_without_build_slot() {
    let mut state = AppState::new(PathBuf::from(".buildloop"));
    let config = Config::default();

    handle_event(
        &mut state,
        AppEvent::LoopEvent(LoopEvent::AgentStageStarted {
            role: AgentRole::Builder,
            stage_id: "security".to_string(),
            model: "claude:sonnet".to_string(),
        }),
        &config,
    );
    handle_event(
        &mut state,
        AppEvent::AgentOutput(AgentOutputEvent::Usage {
            cost_usd: 0.10,
            input_tokens: 400,
            output_tokens: 100,
            context_window: 1_000,
            cache_creation_tokens: 0,
            cache_read_tokens: 0,
        }),
        &config,
    );

    assert_eq!(
        state.spid_context_pcts,
        [None, None, None, None, None],
        "custom cards must not overwrite the canonical Build slot"
    );
    assert_eq!(state.stage_context_pcts.get("security"), Some(&50));
    assert!(
        !state.task_stages_seen.contains(&AgentRole::Builder),
        "custom cards should not make the QRPBA Build indicator look complete"
    );
}

#[test]
fn test_dual_custom_pipeline_stage_usage_updates_pipeline_stage_context() {
    let mut state = AppState::new(PathBuf::from(".buildloop"));
    let config = Config::default();

    handle_event(
        &mut state,
        AppEvent::LoopEvent(LoopEvent::DualBuildStarted {
            models: ["Claude".to_string(), "Codex".to_string()],
        }),
        &config,
    );
    handle_event(
        &mut state,
        AppEvent::DualPipelineEvent(
            1,
            Box::new(AppEvent::LoopEvent(LoopEvent::AgentStageStarted {
                role: AgentRole::Builder,
                stage_id: "security".to_string(),
                model: "Codex".to_string(),
            })),
        ),
        &config,
    );
    handle_event(
        &mut state,
        AppEvent::DualPipelineEvent(
            1,
            Box::new(AppEvent::AgentOutput(AgentOutputEvent::Usage {
                cost_usd: 0.25,
                input_tokens: 700,
                output_tokens: 100,
                context_window: 2_000,
                cache_creation_tokens: 0,
                cache_read_tokens: 0,
            })),
        ),
        &config,
    );

    assert_eq!(state.dual_build.context_pcts[1], [None; 5]);
    assert_eq!(
        state.dual_build.stage_context_pcts[1].get("security"),
        Some(&40)
    );
}

// ─── Plugin & Pattern Telemetry Tests ────────────────────────────

#[test]
fn test_plugin_reference_detection_finds_keywords() {
    let dir = temp_project_dir("ext-ref-detect");
    let mut state = AppState::new(dir.join(".buildloop"));
    state.plugin_keywords = HashMap::from([(
        "roblox".to_string(),
        vec![
            "cframe".to_string(),
            "workspace".to_string(),
            "baseplate".to_string(),
        ],
    )]);
    state.current_agent = Some((AgentRole::Builder, chrono::Utc::now()));
    state
        .agent_output
        .push("Using CFrame to position the part".to_string());
    handle_agent_done(&mut state, true);
    assert_eq!(state.plugin_reference_count.get("roblox"), Some(&1));
    assert!(state
        .log_messages
        .iter()
        .any(|(_, msg)| msg.contains("Plugin 'roblox' referenced")));
    let _ = std::fs::remove_dir_all(dir);
}

#[test]
fn test_plugin_reference_detection_no_match() {
    let dir = temp_project_dir("ext-ref-nomatch");
    let mut state = AppState::new(dir.join(".buildloop"));
    state.plugin_keywords = HashMap::from([(
        "roblox".to_string(),
        vec![
            "cframe".to_string(),
            "workspace".to_string(),
            "baseplate".to_string(),
        ],
    )]);
    state.current_agent = Some((AgentRole::Builder, chrono::Utc::now()));
    state
        .agent_output
        .push("Writing unit tests for the parser".to_string());
    handle_agent_done(&mut state, true);
    assert!(!state.plugin_reference_count.contains_key("roblox"));
    let _ = std::fs::remove_dir_all(dir);
}

#[test]
fn test_pattern_apply_detection_finds_keywords() {
    let dir = temp_project_dir("pat-apply-detect");
    let mut state = AppState::new(dir.join(".buildloop"));
    state.active_pattern_keywords = HashMap::from([(
        "SQLite case sensitivity".to_string(),
        vec![
            "func.lower".to_string(),
            "case-insensitive".to_string(),
            "sqlite".to_string(),
        ],
    )]);
    state.current_agent = Some((AgentRole::Builder, chrono::Utc::now()));
    state
        .agent_output
        .push("Using func.lower() for case-insensitive matching".to_string());
    handle_agent_done(&mut state, true);
    assert_eq!(state.pattern_apply_count, 1);
    assert!(state
        .log_messages
        .iter()
        .any(|(_, msg)| msg.contains("Pattern 'SQLite case sensitivity' applied")));
    let _ = std::fs::remove_dir_all(dir);
}

#[test]
fn test_pattern_apply_detection_no_match() {
    let dir = temp_project_dir("pat-apply-nomatch");
    let mut state = AppState::new(dir.join(".buildloop"));
    state.active_pattern_keywords = HashMap::from([(
        "SQLite case sensitivity".to_string(),
        vec!["func.lower".to_string(), "case-insensitive".to_string()],
    )]);
    state.current_agent = Some((AgentRole::Builder, chrono::Utc::now()));
    state
        .agent_output
        .push("Implementing the HTTP server".to_string());
    handle_agent_done(&mut state, true);
    assert_eq!(state.pattern_apply_count, 0);
    let _ = std::fs::remove_dir_all(dir);
}

#[test]
fn test_plugin_inject_count_incremented_on_event() {
    let dir = temp_project_dir("ext-inject-count");
    let mut state = AppState::new(dir.join(".buildloop"));
    let config = Config::default();
    handle_event(
        &mut state,
        AppEvent::LoopEvent(LoopEvent::PluginInjected {
            name: "roblox".to_string(),
            agent_role: "Builder".to_string(),
            task_id: "T1.1".to_string(),
        }),
        &config,
    );
    assert_eq!(state.plugin_inject_count.get("roblox"), Some(&1));
    assert_eq!(state.session_plugins_used.len(), 1);
    handle_event(
        &mut state,
        AppEvent::LoopEvent(LoopEvent::PluginInjected {
            name: "roblox".to_string(),
            agent_role: "Reviewer".to_string(),
            task_id: "T1.1".to_string(),
        }),
        &config,
    );
    assert_eq!(state.plugin_inject_count.get("roblox"), Some(&2));
    assert_eq!(state.session_plugins_used.len(), 2);
    let _ = std::fs::remove_dir_all(dir);
}

#[test]
fn test_patterns_used_event_increments_counters() {
    let dir = temp_project_dir("pat-used-count");
    let mut state = AppState::new(dir.join(".buildloop"));
    let config = Config::default();
    let titles = vec!["Pattern A".to_string(), "Pattern B".to_string()];
    let keywords_by_title = HashMap::from([
        ("Pattern A".to_string(), vec!["keyword1".to_string()]),
        ("Pattern B".to_string(), vec!["keyword2".to_string()]),
    ]);
    handle_event(
        &mut state,
        AppEvent::LoopEvent(LoopEvent::PatternsUsed {
            titles,
            keywords_by_title,
        }),
        &config,
    );
    assert_eq!(state.pattern_inject_count, 2);
    assert_eq!(state.session_patterns.len(), 2);
    assert_eq!(state.active_pattern_keywords.len(), 2);
    let _ = std::fs::remove_dir_all(dir);
}

#[test]
fn test_patterns_used_with_skill_ids_increments_inject_counter() {
    // T1.30: regression test for the skills branch wiring at src/app/build.rs:3574-3597.
    // Asserts the emit shape (titles populated with kebab-case skill_ids,
    // keywords_by_title keyed by skill_id) increments pattern_inject_count
    // and pushes per-id entries into session_patterns.
    let dir = temp_project_dir("skills-inject-count");
    let mut state = AppState::new(dir.join(".buildloop"));
    let config = Config::default();
    let titles = vec![
        "plan-file-token-overflow-planner".to_string(),
        "shared-gate-in-derived-contexts-planner".to_string(),
        "shared-gate-in-derived-contexts-reviewer".to_string(),
    ];
    let keywords_by_title = HashMap::from([
        (
            "plan-file-token-overflow-planner".to_string(),
            vec!["plan".to_string(), "tokens".to_string()],
        ),
        (
            "shared-gate-in-derived-contexts-planner".to_string(),
            vec!["arc".to_string(), "gate".to_string()],
        ),
    ]);
    handle_event(
        &mut state,
        AppEvent::LoopEvent(LoopEvent::PatternsUsed {
            titles: titles.clone(),
            keywords_by_title: keywords_by_title.clone(),
        }),
        &config,
    );
    assert_eq!(state.pattern_inject_count, 3);
    assert_eq!(state.session_patterns.len(), 3);
    assert!(state
        .session_patterns
        .iter()
        .any(|p| p.title == "plan-file-token-overflow-planner"));
    assert_eq!(state.active_pattern_keywords.len(), 2);
    let _ = std::fs::remove_dir_all(dir);
}

#[test]
fn test_build_completion_warns_unused_plugins() {
    let dir = temp_project_dir("ext-warn-unused");
    let mut state = AppState::new(dir.join(".buildloop"));
    state.plugin_inject_count = HashMap::from([("roblox".to_string(), 4)]);
    // Leave plugin_reference_count empty
    let config = Config::default();
    handle_event(
        &mut state,
        AppEvent::LoopEvent(LoopEvent::Finished),
        &config,
    );
    assert!(state.log_messages.iter().any(|(_, msg)| msg
        .contains("Warning: Plugin 'roblox' was injected 4 times but never referenced")));
    let _ = std::fs::remove_dir_all(dir);
}

#[test]
fn test_build_completion_no_warning_when_referenced() {
    let dir = temp_project_dir("ext-warn-none");
    let mut state = AppState::new(dir.join(".buildloop"));
    state.plugin_inject_count = HashMap::from([("roblox".to_string(), 4)]);
    state.plugin_reference_count = HashMap::from([("roblox".to_string(), 2)]);
    let config = Config::default();
    handle_event(
        &mut state,
        AppEvent::LoopEvent(LoopEvent::Finished),
        &config,
    );
    assert!(!state
        .log_messages
        .iter()
        .any(|(_, msg)| msg.contains("Warning: Plugin 'roblox'")));
    let _ = std::fs::remove_dir_all(dir);
}

#[test]
fn test_keyword_minimum_length_filter() {
    let dir = temp_project_dir("kw-min-len");
    let mut state = AppState::new(dir.join(".buildloop"));
    state.plugin_keywords = HashMap::from([(
        "recon".to_string(),
        vec!["ssh".to_string(), "idrac".to_string(), "racadm".to_string()],
    )]);
    state.current_agent = Some((AgentRole::Builder, chrono::Utc::now()));
    state
        .agent_output
        .push("Using ssh to connect and running racadm commands".to_string());
    handle_agent_done(&mut state, true);
    assert_eq!(state.plugin_reference_count.get("recon"), Some(&1));
    // The log should mention racadm (>= 4 chars) but NOT ssh (< 4 chars)
    let ref_log = state
        .log_messages
        .iter()
        .find(|(_, msg)| msg.contains("Plugin 'recon' referenced"));
    assert!(ref_log.is_some());
    let (_, log_msg) = ref_log.unwrap();
    assert!(log_msg.contains("racadm"));
    assert!(!log_msg.contains("ssh"));
    let _ = std::fs::remove_dir_all(dir);
}

#[test]
fn test_active_pattern_keywords_cleared_on_task_start() {
    let dir = temp_project_dir("pat-kw-clear");
    let mut state = AppState::new(dir.join(".buildloop"));
    state.active_pattern_keywords =
        HashMap::from([("Old Pattern".to_string(), vec!["stale_keyword".to_string()])]);
    let task = Task {
        id: "T2.1".to_string(),
        description: "New task".to_string(),
        line_number: 0,
        completed: false,
        pipeline_progress: None,
        override_flag: crate::complexity::TaskOverride::None,
    };
    let config = Config::default();
    handle_event(
        &mut state,
        AppEvent::LoopEvent(LoopEvent::TaskStarted(task)),
        &config,
    );
    assert!(state.active_pattern_keywords.is_empty());
    let _ = std::fs::remove_dir_all(dir);
}

#[test]
fn plan_review_outcome_accepted_replaces_text() {
    let outcome = PlanReviewOutcome {
        accepted: true,
        final_plan_text: "## File Operations\n...\n## Verification\n...".to_string(),
        iterations: 2,
        unresolved_findings: vec![],
    };
    assert!(outcome.accepted);
    assert!(outcome.final_plan_text.contains("## File Operations"));
    assert!(outcome.unresolved_findings.is_empty());
}

#[test]
fn plan_review_outcome_rejected_preserves_findings() {
    let outcome = PlanReviewOutcome {
        accepted: false,
        final_plan_text: "original".to_string(),
        iterations: 3,
        unresolved_findings: vec![Finding {
            severity: "high".to_string(),
            description: "Missing error handling".to_string(),
            location: "src/main.rs:42".to_string(),
            suggestion: "Add Result return type".to_string(),
        }],
    };
    assert!(!outcome.accepted);
    assert_eq!(outcome.unresolved_findings.len(), 1);
    assert_eq!(outcome.unresolved_findings[0].severity, "high");
}

#[test]
fn complex_task_triggers_plan_review_char() {
    use crate::complexity::{classify_task, TaskComplexity};
    assert_eq!(
        classify_task("refactor the authentication system to support OIDC"),
        TaskComplexity::Complex
    );
}

#[test]
fn test_parallel_builder_usage_events_update_session_cost() {
    // Parallel builder forwards Usage events via AppEvent::AgentOutput.
    // The handle_event handler should update session_cost_usd and
    // session_cost_millicents just like the single-builder path.
    let mut state = AppState::new(PathBuf::from(".buildloop"));

    // Simulate the app transitioning to Running phase so AgentOutput is handled
    // by the running-phase handler (handle_agent_output).
    state.phase = AppPhase::Running;

    // Simulate Usage events from two parallel builder slots
    handle_event(
        &mut state,
        AppEvent::AgentOutput(AgentOutputEvent::Usage {
            cost_usd: 0.50,
            input_tokens: 500,
            output_tokens: 100,
            context_window: 2_000,
            cache_creation_tokens: 0,
            cache_read_tokens: 0,
        }),
        &Config::default(),
    );

    handle_event(
        &mut state,
        AppEvent::AgentOutput(AgentOutputEvent::Usage {
            cost_usd: 0.75,
            input_tokens: 800,
            output_tokens: 200,
            context_window: 2_000,
            cache_creation_tokens: 0,
            cache_read_tokens: 0,
        }),
        &Config::default(),
    );

    // Verify session totals reflect both slots
    assert!((state.session_cost_usd - 1.25).abs() < f64::EPSILON);
    assert_eq!(state.session_input_tokens, 1_300);
    assert_eq!(state.session_output_tokens, 300);
    assert_eq!(
        state.session_cost_millicents.load(Ordering::Relaxed),
        125_000 // (0.50 + 0.75) * 100_000
    );
}

#[cfg(unix)]
#[test]
fn test_buildloop_dir_creation_fails_on_readonly_parent() {
    use std::os::unix::fs::PermissionsExt;

    let tmp = std::env::temp_dir().join("foundry-test-buildloop-readonly");
    let _ = std::fs::remove_dir_all(&tmp);
    std::fs::create_dir_all(&tmp).unwrap();
    std::fs::set_permissions(&tmp, std::fs::Permissions::from_mode(0o555)).unwrap();

    let buildloop_dir = tmp.join(".buildloop");
    let result = std::fs::create_dir_all(&buildloop_dir);
    assert!(
        result.is_err(),
        "create_dir_all should fail when parent is read-only"
    );

    std::fs::set_permissions(&tmp, std::fs::Permissions::from_mode(0o755)).unwrap();
    let _ = std::fs::remove_dir_all(&tmp);
}

#[test]
fn lmstudio_canonical_id_maps_namespaced_and_bare_ids() {
    let stdout = "\
lmstudio/openai/gpt-oss-20b
lmstudio/qwen/qwen3-coder-30b
lmstudio/qwen3.6-27b
lmstudio/mlx-community/qwen3.6-35b-a3b
";
    let map = super::build_lmstudio_canonical_map(stdout);
    assert_eq!(
        map.get("gpt-oss-20b").map(String::as_str),
        Some("lmstudio/openai/gpt-oss-20b")
    );
    assert_eq!(
        map.get("qwen3-coder-30b").map(String::as_str),
        Some("lmstudio/qwen/qwen3-coder-30b")
    );
    assert_eq!(
        map.get("qwen3.6-27b").map(String::as_str),
        Some("lmstudio/qwen3.6-27b")
    );
    assert_eq!(
        map.get("qwen3.6-35b-a3b").map(String::as_str),
        Some("lmstudio/mlx-community/qwen3.6-35b-a3b")
    );
    assert_eq!(map.len(), 4);
}

#[test]
fn lmstudio_canonical_id_handles_empty_and_whitespace() {
    let map = super::build_lmstudio_canonical_map("");
    assert!(map.is_empty());

    let map2 = super::build_lmstudio_canonical_map("\n   \n\t\n");
    assert!(map2.is_empty());
}

#[test]
fn lmstudio_canonical_id_skips_lines_without_lmstudio_prefix() {
    // If a line lacks the "lmstudio/" prefix, the parser still emits it
    // as a key based on the last path segment so the route is recoverable.
    let stdout = "openai/gpt-4\nlmstudio/qwen3.6-27b\n";
    let map = super::build_lmstudio_canonical_map(stdout);
    assert_eq!(map.get("gpt-4").map(String::as_str), Some("openai/gpt-4"));
    assert_eq!(
        map.get("qwen3.6-27b").map(String::as_str),
        Some("lmstudio/qwen3.6-27b")
    );
}

#[test]
fn handle_agent_output_text_delta_appends_to_last_line() {
    use super::state::StreamState;
    let mut state = AppState::new(PathBuf::from(".buildloop"));
    super::handle_agent_output(&mut state, AgentOutputEvent::TextDelta("Hello".into()));
    assert_eq!(state.agent_output, vec!["Hello".to_string()]);

    super::handle_agent_output(&mut state, AgentOutputEvent::TextDelta(", world".into()));
    assert_eq!(state.agent_output, vec!["Hello, world".to_string()]);

    assert_eq!(state.stream_state, StreamState::WritingText);
    assert_eq!(state.stream_text_delta_count, 2);
}

#[test]
fn handle_agent_output_text_delta_starts_new_burst_after_tool_use() {
    use super::state::StreamState;
    let mut state = AppState::new(PathBuf::from(".buildloop"));
    super::handle_agent_output(&mut state, AgentOutputEvent::TextDelta("first".into()));
    super::handle_agent_output(
        &mut state,
        AgentOutputEvent::ToolUse {
            tool: "Read".into(),
            input_preview: "/x.rs".into(),
        },
    );
    super::handle_agent_output(&mut state, AgentOutputEvent::TextDelta("second".into()));

    assert!(state.agent_output.contains(&"first".to_string()));
    assert_eq!(state.agent_output.last().unwrap(), "second");
    assert_eq!(state.stream_state, StreamState::WritingText);
}

#[test]
fn esc_opens_stop_run_modal_then_y_arms_stop() {
    use crate::app::RunningModalKind;
    let dir = temp_project_dir("foundry-running-modal-y");
    std::fs::create_dir_all(dir.join(".buildloop")).expect("failed to create .buildloop");
    let mut state = AppState::new(dir.join(".buildloop"));
    assert!(state.running_screen_modal.is_none());
    assert!(!state.stop_after_task);

    state.running_screen_modal = Some(RunningModalKind::StopRun);
    let key = event::KeyEvent::new(KeyCode::Char('y'), KeyModifiers::NONE);
    super::handle_running_modal_key(&mut state, key, RunningModalKind::StopRun);

    assert!(state.running_screen_modal.is_none());
    assert!(state.stop_after_task);
    let _ = std::fs::remove_dir_all(dir);
}

#[test]
fn esc_modal_n_dismisses_without_arming_stop() {
    use crate::app::RunningModalKind;
    let dir = temp_project_dir("foundry-running-modal-n");
    std::fs::create_dir_all(dir.join(".buildloop")).expect("failed to create .buildloop");
    let mut state = AppState::new(dir.join(".buildloop"));
    state.running_screen_modal = Some(RunningModalKind::StopRun);

    let key = event::KeyEvent::new(KeyCode::Char('n'), KeyModifiers::NONE);
    super::handle_running_modal_key(&mut state, key, RunningModalKind::StopRun);

    assert!(state.running_screen_modal.is_none());
    assert!(!state.stop_after_task);
    let _ = std::fs::remove_dir_all(dir);
}

#[test]
fn ctrl_c_modal_3_cancels() {
    use crate::app::RunningModalKind;
    let dir = temp_project_dir("foundry-running-modal-3");
    std::fs::create_dir_all(dir.join(".buildloop")).expect("failed to create .buildloop");
    let mut state = AppState::new(dir.join(".buildloop"));
    state.running_screen_modal = Some(RunningModalKind::CtrlC);

    let key = event::KeyEvent::new(KeyCode::Char('3'), KeyModifiers::NONE);
    super::handle_running_modal_key(&mut state, key, RunningModalKind::CtrlC);

    assert!(state.running_screen_modal.is_none());
    assert!(!state.stop_after_task);
    assert!(!state.should_quit);
    let _ = std::fs::remove_dir_all(dir);
}

#[test]
fn ctrl_c_modal_second_ctrl_c_force_quits() {
    use crate::app::RunningModalKind;
    let dir = temp_project_dir("foundry-running-modal-force-quit");
    std::fs::create_dir_all(dir.join(".buildloop")).expect("failed to create .buildloop");
    let mut state = AppState::new(dir.join(".buildloop"));
    state.running_screen_modal = Some(RunningModalKind::CtrlC);

    let key = event::KeyEvent::new(KeyCode::Char('c'), KeyModifiers::CONTROL);
    super::handle_running_modal_key(&mut state, key, RunningModalKind::CtrlC);

    assert!(state.should_quit);
    assert!(state.running_screen_modal.is_none());
    let _ = std::fs::remove_dir_all(dir);
}

#[test]
fn ctrl_c_modal_1_arms_stop_and_quits() {
    use crate::app::RunningModalKind;
    let dir = temp_project_dir("foundry-running-modal-1");
    std::fs::create_dir_all(dir.join(".buildloop")).expect("failed to create .buildloop");
    let mut state = AppState::new(dir.join(".buildloop"));
    state.running_screen_modal = Some(RunningModalKind::CtrlC);

    let key = event::KeyEvent::new(KeyCode::Char('1'), KeyModifiers::NONE);
    super::handle_running_modal_key(&mut state, key, RunningModalKind::CtrlC);

    assert!(state.stop_after_task);
    assert!(state.should_quit);
    assert!(state.running_screen_modal.is_none());
    let _ = std::fs::remove_dir_all(dir);
}

#[test]
fn pipeline_click_routes_connected_stages_to_summary_by_default() {
    use crate::tui;
    let cfg = Config {
        plan_review_enabled: true,
        ..Default::default()
    };
    let dir = PathBuf::from(".");
    let expected_ids = ["query", "research", "plan", "plan-review", "implement", "doubt"];
    for (i, expected) in expected_ids.iter().enumerate() {
        let target =
            super::pipeline_click_target(tui::PipelineClick::ConnectedStage(i), &dir, &cfg);
        match target {
            super::PipelineClickTarget::StageSummary {
                stage_id,
                fallback_file,
            } => {
                assert_eq!(stage_id.as_str(), *expected, "wrong stage id at index {}", i);
                assert!(
                    fallback_file.is_some(),
                    "fallback_file should be Some for stage {}",
                    expected
                );
            }
            other => panic!("expected StageSummary at index {}, got {:?}", i, other),
        }
    }
}

#[test]
fn pipeline_click_routes_ship_and_discover_to_summary() {
    use crate::tui;
    let cfg = Config::default();
    let dir = PathBuf::from(".");

    let ship_target = super::pipeline_click_target(tui::PipelineClick::Ship, &dir, &cfg);
    match ship_target {
        super::PipelineClickTarget::StageSummary {
            stage_id,
            fallback_file,
        } => {
            assert_eq!(stage_id, "ship");
            assert!(fallback_file.is_none(), "ship should have no fallback file");
        }
        other => panic!("expected ship to route to StageSummary, got {:?}", other),
    }

    let discover_target = super::pipeline_click_target(tui::PipelineClick::Discover, &dir, &cfg);
    match discover_target {
        super::PipelineClickTarget::StageSummary {
            stage_id,
            fallback_file,
        } => {
            assert_eq!(stage_id, "discover");
            assert!(fallback_file.is_some(), "discover should fall back to TASKS.md");
        }
        other => panic!("expected discover to route to StageSummary, got {:?}", other),
    }
}

#[test]
fn pipeline_click_respects_prefer_file_open_over_summary() {
    use crate::tui;
    let cfg = Config {
        prefer_file_open_over_summary: true,
        ..Default::default()
    };
    let dir = PathBuf::from(".");

    let stage_target =
        super::pipeline_click_target(tui::PipelineClick::ConnectedStage(0), &dir, &cfg);
    assert!(
        matches!(stage_target, super::PipelineClickTarget::OpenFile(_)),
        "expected OpenFile for connected stage with prefer_file_open_over_summary=true"
    );

    let ship_target = super::pipeline_click_target(tui::PipelineClick::Ship, &dir, &cfg);
    assert!(
        matches!(ship_target, super::PipelineClickTarget::None),
        "expected None for ship with prefer_file_open_over_summary=true"
    );

    let discover_target = super::pipeline_click_target(tui::PipelineClick::Discover, &dir, &cfg);
    assert!(
        matches!(discover_target, super::PipelineClickTarget::OpenFile(_)),
        "expected OpenFile for discover with prefer_file_open_over_summary=true"
    );
}

#[test]
fn handle_surface_click_opens_surface_summary_overlay_for_each_variant() {
    use crate::app::ClickableSurface;
    let dir = temp_project_dir("surface_click");
    let cfg = Config::default();
    let cases: Vec<ClickableSurface> = vec![
        ClickableSurface::TaskQueue,
        ClickableSurface::Narrative,
        ClickableSurface::SkillCitations,
        ClickableSurface::SkillRetrieval,
        ClickableSurface::Stats,
        ClickableSurface::AgentOutput,
        ClickableSurface::PipelineStage("plan".to_string()),
        ClickableSurface::ExplorerFile(PathBuf::from("/tmp/x.rs")),
    ];
    for surface in cases {
        let mut state = AppState::new(dir.join(".buildloop"));
        super::handle_surface_click(&mut state, &dir, &cfg, surface.clone());
        assert!(
            state.surface_summary_overlay.is_some(),
            "expected overlay for surface {:?}",
            surface.tag()
        );
        let ov = state.surface_summary_overlay.as_ref().unwrap();
        assert_eq!(ov.surface.tag(), surface.tag());
    }
}

/// T2.2: a SkillsRetrieved event for a stage populates `last_retrieval`
/// with up to 10 entries; subsequent SkillCitationsRecorded flips
/// `was_cited` for entries whose skill_id matches a citation.
#[test]
fn app_event_skills_retrieved_updates_last_retrieval_and_flips_was_cited() {
    use crate::eval::stage_id::StageId;
    let dir = temp_project_dir("skills_retrieved");
    let cfg = Config::default();
    let mut state = AppState::new(dir.join(".buildloop"));

    let top_picks: Vec<(String, f32)> = vec![
        ("skill-a".to_string(), 4.5),
        ("skill-b".to_string(), 3.2),
        ("skill-c".to_string(), 1.1),
    ];
    handle_event(
        &mut state,
        AppEvent::SkillsRetrieved {
            stage: StageId::Plan,
            top_picks: top_picks.clone(),
            total_pool: 20,
        },
        &cfg,
    );
    let plan_entries = state
        .last_retrieval
        .get(&StageId::Plan)
        .expect("plan entries present after SkillsRetrieved");
    assert_eq!(plan_entries.len(), 3);
    assert_eq!(plan_entries[0].skill_id, "skill-a");
    assert!((plan_entries[0].score - 4.5).abs() < 1e-4);
    assert!(!plan_entries[0].was_cited);

    // Bounded at 10 entries even if 12 picks come in.
    let many: Vec<(String, f32)> = (0..12)
        .map(|i| (format!("s{}", i), i as f32))
        .collect();
    handle_event(
        &mut state,
        AppEvent::SkillsRetrieved {
            stage: StageId::Build,
            top_picks: many,
            total_pool: 50,
        },
        &cfg,
    );
    let build_entries = state
        .last_retrieval
        .get(&StageId::Build)
        .expect("build entries present");
    assert_eq!(build_entries.len(), 10);

    // SkillCitationsRecorded flips was_cited on matching entries.
    handle_event(
        &mut state,
        AppEvent::LoopEvent(LoopEvent::SkillCitationsRecorded {
            skill_names: vec!["skill-b".to_string()],
        }),
        &cfg,
    );
    let plan_entries = state
        .last_retrieval
        .get(&StageId::Plan)
        .expect("plan entries still present after citations");
    let cited: Vec<&str> = plan_entries
        .iter()
        .filter(|e| e.was_cited)
        .map(|e| e.skill_id.as_str())
        .collect();
    assert_eq!(cited, vec!["skill-b"]);
}
