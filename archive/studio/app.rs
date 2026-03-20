use anyhow::Result;
use crossterm::event::Event;
use futures::{future::join_all, StreamExt};
use std::{path::Path, time::Duration};
use tokio::{sync::mpsc, task::JoinHandle};

use crate::{agent::ModelProvider, config::Config, git, tui};

use super::{
    model::{StudioEvent, SHUTDOWN_GRACE_MILLIS},
    providers::log_provider_probe,
    state::StudioState,
    ui::{
        input::{cancel_running_sessions, handle_event, handle_pending_action},
        render::render,
    },
};

pub(in crate::studio) fn spawn_terminal_event_reader(
    event_tx: mpsc::UnboundedSender<StudioEvent>,
) -> JoinHandle<()> {
    tokio::spawn(async move {
        let mut reader = crossterm::event::EventStream::new();
        loop {
            if let Some(Ok(event)) = reader.next().await {
                let studio_event = match event {
                    Event::Key(key) if key.kind == crossterm::event::KeyEventKind::Press => {
                        Some(StudioEvent::Key(key))
                    }
                    Event::Key(_) => None,
                    Event::Mouse(mouse) => Some(StudioEvent::Mouse(mouse)),
                    Event::Paste(text) => Some(StudioEvent::Paste(text)),
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
    for warning in std::mem::take(&mut state.theme_warnings) {
        state.log(warning);
    }
    state.log(format!("theme: {}", state.theme.name));
    state.log(format!("studio ready for {}", project_dir.display()));
    state.log(format!(
        "selected execution contract: {}",
        state
            .selected_execution_contract()
            .map(|c| c.name.as_str())
            .unwrap_or("<none>")
    ));
    for msg in git::check_git_readiness(project_dir) {
        state.log(msg);
    }
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

pub(in crate::studio) async fn shutdown_active_sessions(state: &mut StudioState) {
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

#[cfg(test)]
mod shutdown_tests {
    use std::sync::{
        atomic::{AtomicBool, Ordering},
        Arc,
    };

    use super::super::{
        model::SessionStatus,
        state::SessionControl,
        test_helpers::{test_session, test_state},
    };
    use super::shutdown_active_sessions;

    #[tokio::test]
    async fn shutdown_active_sessions_cancels_and_drains_handles() {
        let mut state = test_state();
        let cancel_flag = Arc::new(AtomicBool::new(false));
        let task_flag = cancel_flag.clone();
        let task = tokio::spawn(async move {
            while !task_flag.load(Ordering::Relaxed) {
                tokio::task::yield_now().await;
            }
        });

        let mut session = test_session(SessionStatus::Running);
        session.id = "session-1".into();
        state.sessions.push(session);
        state.session_controls.insert(
            "session-1".into(),
            SessionControl {
                cancel_flag: cancel_flag.clone(),
                task,
            },
        );

        shutdown_active_sessions(&mut state).await;

        assert!(cancel_flag.load(Ordering::Relaxed));
        assert!(state.session_controls.is_empty());
    }

    #[tokio::test]
    async fn shutdown_active_sessions_aborts_hung_tasks_after_grace_period() {
        let mut state = test_state();
        let cancel_flag = Arc::new(AtomicBool::new(false));
        let task = tokio::spawn(std::future::pending::<()>());

        let mut session = test_session(SessionStatus::Running);
        session.id = "session-1".into();
        state.sessions.push(session);
        state.session_controls.insert(
            "session-1".into(),
            SessionControl {
                cancel_flag: cancel_flag.clone(),
                task,
            },
        );

        shutdown_active_sessions(&mut state).await;

        assert!(cancel_flag.load(Ordering::Relaxed));
        assert!(state.session_controls.is_empty());
    }
}
