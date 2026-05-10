use chrono::Utc;
use ratatui::{
    layout::Rect,
    style::{Modifier, Style},
    text::{Line, Span},
    widgets::{Block, Borders, Paragraph},
    Frame,
};

use crate::app::AppState;
use crate::utils::truncate_str;

pub(super) fn render_narrative(frame: &mut Frame, area: Rect, state: &AppState) {
    let inner_width = area.width.saturating_sub(4) as usize;
    let body_max = inner_width.saturating_sub(7);

    // Last:
    let last_body_full = match state.last_commit_brief.as_ref() {
        Some(brief) if !brief.subject.is_empty() => {
            format!("{} ({}, {})", brief.subject, brief.short_sha, brief.relative_age)
        }
        _ => "no prior commits".to_string(),
    };
    let last_body = truncate_str(&last_body_full, body_max).to_string();

    // Now:
    let now_body_full = if let Some(task) = state.current_task.as_ref() {
        if let Some((role, started)) = state.current_agent.as_ref() {
            let dur = Utc::now().signed_duration_since(*started);
            let secs = dur.num_seconds().max(0) as u64;
            let mins = secs / 60;
            let secs_rem = secs % 60;
            let dur_str = format!("{}m{:02}s", mins, secs_rem);
            let stage_label = state
                .current_agent_stage_id
                .as_deref()
                .unwrap_or(role.slug())
                .to_string();
            let evt = state.events_received;
            format!(
                "{} -- {} | stage {} ({}, {} evt)",
                task.id,
                task.short_desc(60),
                stage_label,
                dur_str,
                evt
            )
        } else {
            format!("{} -- {} | stage idle", task.id, task.short_desc(60))
        }
    } else {
        "no task in progress".to_string()
    };
    let now_body = truncate_str(&now_body_full, body_max).to_string();

    // Next:
    let next_body_full = match state.next_task_hint.as_ref() {
        Some(hint) if !hint.is_empty() => hint.clone(),
        _ => "queue empty".to_string(),
    };
    let next_body = truncate_str(&next_body_full, body_max).to_string();

    let muted = Style::default().fg(state.tui_theme.muted);
    let text = Style::default().fg(state.tui_theme.text);
    let text_bold = Style::default()
        .fg(state.tui_theme.text)
        .add_modifier(Modifier::BOLD);

    let line1 = Line::from(vec![
        Span::styled(" Last: ", muted),
        Span::styled(last_body, text),
    ]);
    let line2 = Line::from(vec![
        Span::styled(" Now:  ", muted),
        Span::styled(now_body, text_bold),
    ]);
    let line3 = Line::from(vec![
        Span::styled(" Next: ", muted),
        Span::styled(next_body, text),
    ]);

    let block = Block::default()
        .borders(Borders::ALL)
        .border_style(Style::default().fg(state.tui_theme.border))
        .title(Span::styled(
            " Narrative ",
            Style::default()
                .fg(state.tui_theme.info)
                .add_modifier(Modifier::BOLD),
        ));

    let paragraph = Paragraph::new(vec![line1, line2, line3]).block(block);
    frame.render_widget(paragraph, area);
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::agent::AgentRole;
    use crate::app::AppState;
    use crate::git::LastCommitBrief;
    use crate::task::Task;
    use chrono::Utc;
    use std::path::PathBuf;

    fn render_narrative_text(state: &AppState) -> String {
        use ratatui::backend::TestBackend;
        use ratatui::Terminal;
        let backend = TestBackend::new(80, 6);
        let mut terminal = Terminal::new(backend).expect("failed to create terminal");
        terminal
            .draw(|frame| render_narrative(frame, frame.area(), state))
            .expect("failed to draw");
        let buffer = terminal.backend().buffer();
        let area = *buffer.area();
        (0..area.height)
            .map(|y| {
                (0..area.width)
                    .map(|x| {
                        buffer
                            .cell((x, y))
                            .map(|c| c.symbol().to_string())
                            .unwrap_or_default()
                    })
                    .collect::<Vec<_>>()
                    .join("")
            })
            .collect::<Vec<_>>()
            .join("\n")
    }

    #[test]
    fn narrative_renders_all_three_lines_when_populated() {
        let mut state = AppState::new(PathBuf::from(".buildloop"));
        state.last_commit_brief = Some(LastCommitBrief {
            subject: "feat(T0.5): something".into(),
            relative_age: "8 minutes ago".into(),
            short_sha: "49e9ca6".into(),
        });
        state.current_task = Some(Task {
            id: "T1.1".into(),
            description: "archiving artifacts".into(),
            line_number: 0,
            completed: false,
            pipeline_progress: None,
        });
        state.current_agent = Some((AgentRole::PlanReview, Utc::now()));
        state.current_agent_stage_id = Some("plan-review".into());
        state.events_received = 56;
        state.next_task_hint = Some("bash safety eval check".into());

        let rendered = render_narrative_text(&state);
        for needle in [
            "Last:",
            "Now:",
            "Next:",
            "feat(T0.5)",
            "49e9ca6",
            "T1.1",
            "archiving",
            "plan-review",
            "bash safety",
        ] {
            assert!(
                rendered.contains(needle),
                "expected `{}` in rendered:\n{}",
                needle,
                rendered
            );
        }
    }

    #[test]
    fn narrative_renders_empty_state_with_placeholders() {
        let state = AppState::new(PathBuf::from(".buildloop"));
        let rendered = render_narrative_text(&state);
        for needle in ["no prior commits", "no task in progress", "queue empty"] {
            assert!(
                rendered.contains(needle),
                "expected `{}` in rendered:\n{}",
                needle,
                rendered
            );
        }
    }

    #[test]
    fn narrative_truncates_overlong_lines() {
        let mut state = AppState::new(PathBuf::from(".buildloop"));
        state.next_task_hint = Some("a".repeat(500));
        let rendered = render_narrative_text(&state);
        for (i, line) in rendered.lines().enumerate() {
            assert!(
                line.chars().count() <= 80,
                "row {} exceeded width 80: {} chars",
                i,
                line.chars().count()
            );
        }
    }
}
