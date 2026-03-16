use super::startup::{
    classify_plan_status, detect_startup_scenario, enter_home_surface,
    handle_startup_event, handle_startup_key, handle_startup_mouse_at, load_pending_task_at,
};
use super::state::{
    AppEvent, AppPhase, AppState, LoopEvent, PendingTransition, PlanStatus, PlanningOutcome,
    PlanningState, StartupScenario, StartupState,
};
use super::{
    apply_orchestrator_outcome, apply_pending_transition, apply_planning_outcome, handle_event,
    prepare_append_tasks_start, process_received_event, seed_spec_from_brief,
};
use crate::config::Config;
use crate::agent::{AgentOutputEvent, AgentRole};
use crate::orchestrator::{Finding, OrchestratorOutcome, ProposerOutput, ReviewerOutput};
use crossterm::event::{self, KeyCode, KeyModifiers, MouseButton, MouseEvent, MouseEventKind};
use std::path::{Path, PathBuf};
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
        );
    }

    handle_startup_key(
        &mut state,
        event::KeyEvent::new(KeyCode::Enter, KeyModifiers::NONE),
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
fn prepare_append_tasks_start_does_not_seed_spec_when_claude_is_missing() {
    let dir = temp_project_dir("foundry-append-no-claude");
    let mut state = AppState::new(dir.join(".buildloop"));
    let request = super::state::AppendTasksRequest {
        description: "build a notes app".to_string(),
        label: "Describe project: build a notes app".to_string(),
        seed_spec_from_description: true,
    };

    let can_start = prepare_append_tasks_start(&dir, &mut state, &request, false);

    assert!(!can_start);
    assert!(!dir.join("SPEC.md").exists());

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
    write_file(
        &dir.join("TASKS.md"),
        "# Plan\n\n- [ ] T1.1: One\n",
    );

    let mut state = AppState::new(dir.join(".buildloop"));
    state.startup = Some(StartupState::new(
        &dir,
        StartupScenario::QueueReady,
        PlanStatus::Pending(1),
        None,
    ));

    // Initially selected = 0
    assert_eq!(
        state.startup.as_ref().map(|s| s.explorer_selected),
        Some(0)
    );

    // Press Down to move to next entry
    handle_startup_key(
        &mut state,
        event::KeyEvent::new(KeyCode::Down, KeyModifiers::NONE),
    );

    assert_eq!(
        state.startup.as_ref().map(|s| s.explorer_selected),
        Some(1)
    );

    // Press Up to move back
    handle_startup_key(
        &mut state,
        event::KeyEvent::new(KeyCode::Up, KeyModifiers::NONE),
    );

    assert_eq!(
        state.startup.as_ref().map(|s| s.explorer_selected),
        Some(0)
    );

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
    );
    handle_startup_key(
        &mut state,
        event::KeyEvent::new(KeyCode::Char('q'), KeyModifiers::NONE),
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
    handle_startup_event(&mut state, AppEvent::Paste("fix login timeout".to_string()));

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
    write_file(
        &dir.join("TASKS.md"),
        "# Plan\n\n- [ ] T1.1: One\n",
    );

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
    process_received_event(&mut state, AppEvent::Tick, &mut event_rx, &Config::default());
    process_received_event(&mut state, AppEvent::Tick, &mut event_rx, &Config::default());

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
    assert!(
        state.startup.as_ref().unwrap().explorer_selected > initial_selected
    );

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
        );
    }

    // Press Enter
    handle_startup_key(
        &mut state,
        event::KeyEvent::new(KeyCode::Enter, KeyModifiers::NONE),
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
        );
    }

    handle_startup_key(
        &mut state,
        event::KeyEvent::new(KeyCode::Enter, KeyModifiers::NONE),
    );

    // NeedsQueue with text writes SPEC.md and returns to startup for review
    assert!(matches!(
        state.pending_transition,
        Some(PendingTransition::ShowStartup { .. })
    ));

    // NeedsQueue with text should write SPEC.md
    let spec_path = dir.join("SPEC.md");
    let spec_content = std::fs::read_to_string(&spec_path).expect("SPEC.md should exist");
    assert!(spec_content.contains("auth bugs"));

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
fn running_queue_updated_event_populates_task_queue() {
    use crate::task::Task;

    let mut state = AppState::new(PathBuf::from(".buildloop"));
    let tasks = vec![
        Task {
            id: "T1.1".to_string(),
            description: "First task".to_string(),
            line_number: 3,
            completed: true,
            pipeline_progress: None,
        },
        Task {
            id: "T1.2".to_string(),
            description: "Second task".to_string(),
            line_number: 4,
            completed: false,
            pipeline_progress: None,
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
            claims: Vec::new(),
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
            assert!(m.contains("accepted"), "message should contain 'accepted': {}", m);
            assert!(m.contains("2 iteration(s)"), "message should contain '2 iteration(s)': {}", m);
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
            claims: Vec::new(),
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
    assert_eq!(planning.orchestrator_role_label.as_deref(), Some("Proposing"));
    assert_eq!(planning.orchestrator_role_model.as_deref(), Some("Claude opus"));
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
    assert_eq!(planning.orchestrator_role_label.as_deref(), Some("Reviewing"));
    assert_eq!(planning.orchestrator_role_model.as_deref(), Some("Codex codex-5.4"));
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
    assert_eq!(state.planning.as_ref().unwrap().orchestrator_finding_count, 3);
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
            claims: Vec::new(),
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
            claims: Vec::new(),
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
