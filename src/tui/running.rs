use ratatui::{
    layout::Rect,
    style::{Color, Modifier, Style},
    text::{Line, Span},
    widgets::{Block, Borders, List, ListItem, Paragraph},
    Frame,
};

use crate::agent::AgentRole;
use crate::app::{AppPhase, AppState, ExtensionDisplayInfo, TuiPane};
use super::{pane_border_style, pane_border_type};
use crate::utils::truncate_str;

pub(super) fn render_header(frame: &mut Frame, area: Rect, state: &AppState) {
    let completed = state.completed_count;
    let total = state.total_count;
    let pct = if total > 0 {
        (completed as f64 / total as f64) * 100.0
    } else {
        0.0
    };

    let desc_width = area.width.saturating_sub(10) as usize;
    let task_line = if let Some(ref task) = state.current_task {
        format!("  {} — {}", task.id, task.short_desc(desc_width))
    } else if let Some(ref planning) = state.planning {
        if planning.orchestrator_mode {
            let iter_label = if planning.orchestrator_iteration > 0 {
                format!(
                    "Iteration {}/{}",
                    planning.orchestrator_iteration, planning.orchestrator_max_iterations
                )
            } else {
                "Starting...".to_string()
            };
            let role = planning
                .orchestrator_role_label
                .as_deref()
                .unwrap_or("Preparing");
            let model_suffix = if let Some(ref model) = planning.orchestrator_role_model {
                format!(" with {}", model)
            } else {
                String::new()
            };
            let findings = if planning.orchestrator_finding_count > 0 {
                format!(" | {} finding(s)", planning.orchestrator_finding_count)
            } else {
                String::new()
            };
            format!("  Design — {}: {}{}{}", iter_label, role, model_suffix, findings)
        } else {
            format!("  Planning — {}", planning.label)
        }
    } else if state.is_discovering {
        "  Discovery — scanning for new work...".to_string()
    } else {
        "  Waiting...".to_string()
    };

    let agent_line = if let Some((ref role, ref started)) = state.current_agent {
        let elapsed = chrono::Utc::now().signed_duration_since(*started);
        let mins = elapsed.num_minutes();
        let secs = elapsed.num_seconds() % 60;
        let model = state.current_agent_model.as_deref().unwrap_or("?");

        // Spinner animation while waiting for output
        let spinner_chars = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏'];
        let spinner = spinner_chars[state.tick_count % spinner_chars.len()];

        let activity = if state.agent_output.is_empty() {
            format!("{} thinking...", spinner)
        } else {
            format!("{} {} events", spinner, state.events_received)
        };

        format!(
            "  ⎿ {} ({}) | {}m {}s | {}",
            role, model, mins, secs, activity
        )
    } else {
        String::new()
    };

    let brand = if state.project_name.is_empty() {
        "  FOUNDRY ".to_string()
    } else {
        format!("  {} ", state.project_name)
    };

    let mut header_text = vec![
        Line::from(vec![
            Span::styled(
                &brand,
                Style::default()
                    .fg(Color::Black)
                    .bg(Color::Cyan)
                    .add_modifier(Modifier::BOLD),
            ),
            Span::raw(" "),
            Span::styled(
                if matches!(state.phase, AppPhase::Startup) {
                    " STOPPED "
                } else if state.stop_after_task {
                    " STOPPING "
                } else if state.run_mode == "hil" {
                    " RUNNING (Review) "
                } else {
                    " RUNNING "
                },
                Style::default()
                    .fg(Color::Black)
                    .bg(if matches!(state.phase, AppPhase::Startup) {
                        Color::DarkGray
                    } else if state.stop_after_task {
                        Color::Yellow
                    } else {
                        Color::Green
                    })
                    .add_modifier(Modifier::BOLD),
            ),
            Span::raw("  "),
            Span::styled(
                format!("[{}/{}] {:.0}%", completed, total, pct),
                Style::default()
                    .fg(Color::Yellow)
                    .add_modifier(Modifier::BOLD),
            ),
        ]),
        Line::from(Span::styled(
            task_line,
            Style::default()
                .fg(Color::White)
                .add_modifier(Modifier::BOLD),
        )),
        Line::from(Span::styled(
            agent_line,
            Style::default().fg(Color::DarkGray),
        )),
    ];

    if let Some(next_task) = state.next_task_hint.as_ref() {
        header_text.push(Line::from(Span::styled(
            format!(
                "  Next: {}",
                truncate_str(next_task, area.width.saturating_sub(10) as usize)
            ),
            Style::default().fg(Color::Cyan),
        )));
    }

    // Log line removed from header -- the agent name + timer on line 3 already
    // conveys the same info. The status bar at the bottom shows the latest log.

    let header = Paragraph::new(header_text).block(
        Block::default()
            .borders(Borders::BOTTOM)
            .border_style(Style::default().fg(Color::DarkGray)),
    );
    frame.render_widget(header, area);
}

pub(super) fn wrap_line(line: &str, width: usize) -> Vec<String> {
    if width == 0 || line.len() <= width {
        return vec![line.to_string()];
    }
    let mut result = Vec::new();
    let mut remaining = line;
    while !remaining.is_empty() {
        if remaining.len() <= width {
            result.push(remaining.to_string());
            break;
        }
        // Find a safe char boundary at or before `width`
        let safe_width = truncate_str(remaining, width).len();
        // Guarantee forward progress: if we can't fit even one char,
        // push the first character and advance past it.
        if safe_width == 0 {
            let first_char_len = remaining.chars().next().map(|c| c.len_utf8()).unwrap_or(1);
            result.push(remaining[..first_char_len].to_string());
            remaining = &remaining[first_char_len..];
            continue;
        }
        // Try to break at a space within the safe range
        let split_at = remaining[..safe_width]
            .rfind(' ')
            .map(|p| p + 1)
            .unwrap_or(safe_width);
        result.push(remaining[..split_at].to_string());
        remaining = &remaining[split_at..];
    }
    result
}

pub(super) fn style_for_line(line: &str) -> Style {
    if line.starts_with("[stderr]") {
        Style::default().fg(Color::Red)
    } else if line.starts_with("[tool]") {
        Style::default().fg(Color::Cyan)
    } else if line.starts_with("[result]") {
        Style::default().fg(Color::DarkGray)
    } else if line.starts_with("[rate limited]") {
        Style::default().fg(Color::Yellow)
    } else if line.starts_with("[studio]") {
        Style::default().fg(Color::Cyan)
    } else if line.starts_with("[injected]") {
        Style::default()
            .fg(Color::Yellow)
            .add_modifier(Modifier::BOLD)
    } else {
        Style::default().fg(Color::White)
    }
}

pub(super) fn render_agent_output(frame: &mut Frame, area: Rect, state: &AppState, focused: TuiPane) {
    let inner_width = area.width.saturating_sub(2) as usize;

    // Pre-wrap all lines, preserving style
    let wrapped: Vec<(String, Style)> = state
        .agent_output
        .iter()
        .flat_map(|line| {
            let style = style_for_line(line);
            wrap_line(line, inner_width)
                .into_iter()
                .map(move |chunk| (chunk, style))
        })
        .collect();

    let max_lines = area.height.saturating_sub(2) as usize;
    let total_lines = wrapped.len();
    let start = total_lines.saturating_sub(max_lines + state.scroll_offset);
    let end = total_lines.saturating_sub(state.scroll_offset);

    let items: Vec<ListItem> = wrapped[start..end]
        .iter()
        .map(|(text, style)| ListItem::new(Span::styled(text.as_str(), *style)))
        .collect();

    let title = if let Some((ref role, _)) = state.current_agent {
        let color = match role {
            AgentRole::Scout => Color::LightBlue,
            AgentRole::Planner => Color::Magenta,
            AgentRole::Builder => Color::Green,
            AgentRole::Reviewer => Color::Cyan,
            AgentRole::Fixer => Color::Yellow,
            AgentRole::Discovery => Color::Blue,
        };
        Span::styled(
            format!(" {} ", role),
            Style::default().fg(color).add_modifier(Modifier::BOLD),
        )
    } else {
        Span::styled(" Agent ", Style::default().fg(Color::DarkGray))
    };

    let list = List::new(items).block(
        Block::default()
            .borders(Borders::ALL)
            .border_style(pane_border_style(focused, TuiPane::AgentOutput))
            .border_type(pane_border_type(focused, TuiPane::AgentOutput))
            .title(title),
    );

    frame.render_widget(list, area);
}

pub(super) fn render_task_queue(frame: &mut Frame, area: Rect, state: &AppState, focused: TuiPane) {
    if state.task_queue.is_empty() {
        let empty = Paragraph::new(Span::styled(
            " No tasks in queue yet.",
            Style::default().fg(Color::DarkGray),
        ))
        .block(
            Block::default()
                .borders(Borders::ALL)
                .border_style(pane_border_style(focused, TuiPane::TaskQueue))
                .border_type(pane_border_type(focused, TuiPane::TaskQueue))
                .title(Span::styled(
                    " Task Queue ",
                    Style::default()
                        .fg(Color::White)
                        .add_modifier(Modifier::BOLD),
                )),
        );
        frame.render_widget(empty, area);
        return;
    }

    let max_lines = area.height.saturating_sub(2) as usize;
    let total = state.task_queue.len();
    let scroll = state.task_queue_scroll.min(total.saturating_sub(max_lines));
    let end = total.saturating_sub(scroll);
    let start = end.saturating_sub(max_lines);
    let inner_width = area.width.saturating_sub(4) as usize;

    let current_id = state.current_task.as_ref().map(|t| t.id.as_str());

    let items: Vec<ListItem> = state.task_queue[start..end]
        .iter()
        .map(|task| {
            let is_current = current_id == Some(task.id.as_str());

            // Color by task prefix: H=human(yellow), D=discovered(blue), T=planned(white)
            let prefix_color = if task.id.starts_with('H') {
                Color::Yellow
            } else if task.id.starts_with('D') {
                Color::Blue
            } else {
                Color::White
            };

            let was_wip = state
                .task_history
                .get(&task.id)
                .map(|h| !h.passed_review)
                .unwrap_or(false);

            let (icon, style) = if task.completed && was_wip {
                // WIP commit -- review failed
                ("\u{2717}", Style::default().fg(Color::Yellow))
            } else if task.completed {
                ("\u{25cf}", Style::default().fg(Color::Green))
            } else if is_current {
                (
                    "\u{25b6}",
                    Style::default()
                        .fg(prefix_color)
                        .add_modifier(Modifier::BOLD),
                )
            } else {
                ("\u{25cb}", Style::default().fg(Color::Gray))
            };

            // ID gets prefix color even when pending
            let id_style = if task.completed {
                style
            } else {
                Style::default().fg(prefix_color)
            };

            // Pipeline indicator for completed and current tasks
            let pipeline_spans = if let Some(history) = state.task_history.get(&task.id) {
                // Completed: show S>P>I>V with colors
                let all_stages = [
                    ("S", AgentRole::Scout),
                    ("P", AgentRole::Planner),
                    ("I", AgentRole::Builder),
                    ("D", AgentRole::Reviewer),
                ];
                let verify_color = if history.passed_review {
                    Color::Green
                } else {
                    Color::Red
                };
                let mut spans = vec![Span::styled(" ", Style::default())];
                for (label, role) in &all_stages {
                    let ran = history.stages_seen.contains(role);
                    let color = if !ran {
                        Color::DarkGray
                    } else if *role == AgentRole::Reviewer {
                        verify_color
                    } else {
                        Color::Green
                    };
                    let text = if ran {
                        label.to_string()
                    } else {
                        "-".to_string()
                    };
                    spans.push(Span::styled(text, Style::default().fg(color)));
                }
                if !history.passed_review {
                    spans.push(Span::styled("!", Style::default().fg(Color::Red)));
                }
                spans
            } else if is_current {
                // Current: show progress through pipeline
                let all_stages = [
                    ("S", AgentRole::Scout),
                    ("P", AgentRole::Planner),
                    ("I", AgentRole::Builder),
                    ("D", AgentRole::Reviewer),
                ];
                let active = state.current_agent.as_ref().map(|(r, _)| r);
                let mut spans = vec![Span::styled(" ", Style::default())];
                for (label, role) in &all_stages {
                    let seen = state.task_stages_seen.contains(role);
                    let is_active = active == Some(role);
                    let (text, color) = if is_active {
                        (label.to_string(), Color::Yellow)
                    } else if seen {
                        (label.to_string(), Color::Green)
                    } else {
                        (".".to_string(), Color::DarkGray)
                    };
                    let style = if is_active {
                        Style::default().fg(color).add_modifier(Modifier::BOLD)
                    } else {
                        Style::default().fg(color)
                    };
                    spans.push(Span::styled(text, style));
                }
                spans
            } else if task.completed {
                // Completed in a prior session -- no live pipeline data
                vec![Span::styled(
                    if was_wip { " \u{2717}" } else { " \u{2714}" },
                    Style::default().fg(if was_wip { Color::Yellow } else { Color::Green }),
                )]
            } else {
                // Pending: show anticipated pipeline in gray
                vec![Span::styled(" ....", Style::default().fg(Color::DarkGray))]
            };

            let pipeline_width: usize = pipeline_spans.iter().map(|s| s.width()).sum();
            let desc =
                task.short_desc(inner_width.saturating_sub(task.id.len() + 5 + pipeline_width));
            let mut spans = vec![
                Span::styled(format!(" {} ", icon), style),
                Span::styled(format!("{}: ", task.id), id_style),
                Span::styled(desc, style),
            ];
            spans.extend(pipeline_spans);
            ListItem::new(Line::from(spans))
        })
        .collect();

    let pending = total - state.completed_count;
    let title = format!(
        " Task Queue [{}/{} done | {} left] ",
        state.completed_count, total, pending
    );

    let list = List::new(items).block(
        Block::default()
            .borders(Borders::ALL)
            .border_style(pane_border_style(focused, TuiPane::TaskQueue))
            .border_type(pane_border_type(focused, TuiPane::TaskQueue))
            .title(Span::styled(
                title,
                Style::default()
                    .fg(Color::White)
                    .add_modifier(Modifier::BOLD),
            )),
    );

    frame.render_widget(list, area);
}

pub(super) fn render_patterns_learned(
    frame: &mut Frame,
    area: Rect,
    state: &AppState,
    _config: &crate::config::Config,
    focused: TuiPane,
) {
    let title = format!(" Patterns Learned ({}) ", state.session_patterns.len());
    let max_lines = area.height.saturating_sub(2) as usize;

    if state.session_patterns.is_empty() {
        let empty = Paragraph::new(Span::styled(
            " Patterns will appear here as tasks complete.",
            Style::default().fg(Color::DarkGray),
        ))
        .block(
            Block::default()
                .borders(Borders::ALL)
                .border_style(pane_border_style(focused, TuiPane::PatternsLearned))
                .border_type(pane_border_type(focused, TuiPane::PatternsLearned))
                .title(Span::styled(
                    title,
                    Style::default()
                        .fg(Color::Cyan)
                        .add_modifier(Modifier::BOLD),
                )),
        );
        frame.render_widget(empty, area);
        return;
    }

    // Show most recent patterns first, respecting scroll offset
    let total_patterns = state.session_patterns.len();
    let scroll = state
        .patterns_scroll
        .min(total_patterns.saturating_sub(1));
    let items: Vec<ListItem> = state
        .session_patterns
        .iter()
        .rev()
        .skip(scroll)
        .take(max_lines)
        .enumerate()
        .map(|(i, title)| {
            let num = total_patterns.saturating_sub(scroll + i);
            ListItem::new(Line::from(vec![
                Span::styled(
                    format!(" #{} ", num),
                    Style::default().fg(Color::Cyan),
                ),
                Span::styled(
                    truncate_str(title, area.width.saturating_sub(8) as usize),
                    Style::default().fg(Color::White),
                ),
            ]))
        })
        .collect();

    let list = List::new(items).block(
        Block::default()
            .borders(Borders::ALL)
            .border_style(pane_border_style(focused, TuiPane::PatternsLearned))
            .border_type(pane_border_type(focused, TuiPane::PatternsLearned))
            .title(Span::styled(
                format!(" Patterns Learned ({}) ", state.session_patterns.len()),
                Style::default()
                    .fg(Color::Cyan)
                    .add_modifier(Modifier::BOLD),
            )),
    );
    frame.render_widget(list, area);
}

pub(super) fn render_status_bar(frame: &mut Frame, area: Rect, state: &AppState) {
    if matches!(state.phase, AppPhase::Planning) {
        render_planning_status_bar(frame, area, state);
        return;
    }

    let discovery_info = if state.discovery_round > 0 {
        format!(" | discovery round {} ", state.discovery_round)
    } else {
        String::new()
    };

    let mut spans = vec![
        Span::styled(
            " q ",
            Style::default()
                .fg(Color::Black)
                .bg(Color::DarkGray)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw(" stop  "),
        Span::styled(
            " Ctrl+C ",
            Style::default()
                .fg(Color::Black)
                .bg(Color::DarkGray)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw(" force quit  "),
        Span::styled(
            " ↑↓ ",
            Style::default()
                .fg(Color::Black)
                .bg(Color::DarkGray)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw(" scroll  "),
        Span::styled(
            " i ",
            Style::default()
                .fg(Color::Black)
                .bg(Color::DarkGray)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw(" inject  "),
        Span::styled(
            " PgUp/PgDn ",
            Style::default()
                .fg(Color::Black)
                .bg(Color::DarkGray)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw(" queue  "),
        Span::styled(
            " p ",
            Style::default()
                .fg(Color::Black)
                .bg(Color::DarkGray)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw(" patterns"),
    ];

    if state.last_orchestrator_outcome.is_some() {
        spans.push(Span::styled(
            "  f ",
            Style::default()
                .fg(Color::Black)
                .bg(Color::DarkGray)
                .add_modifier(Modifier::BOLD),
        ));
        spans.push(Span::raw(" findings"));
    }

    spans.push(Span::styled(discovery_info, Style::default().fg(Color::DarkGray)));

    // Tab toggle -- always visible on Dashboard
    spans.push(Span::styled(
        "  Tab ",
        Style::default()
            .fg(Color::Black)
            .bg(Color::Rgb(227, 115, 75))
            .add_modifier(Modifier::BOLD),
    ));
    spans.push(Span::raw(" explorer"));

    // Extensions indicator (read-only during running)
    let ext_status = format_running_extensions_status(&state.available_extensions);
    if !ext_status.is_empty() {
        spans.push(Span::styled(
            format!("  {} ", ext_status),
            Style::default().fg(Color::Rgb(227, 115, 75)),
        ));
    }

    if let Some(ref version) = state.update_available {
        spans.push(Span::styled(
            format!(" | v{} available — `foundry update`", version),
            Style::default()
                .fg(Color::Green)
                .add_modifier(Modifier::BOLD),
        ));
    }

    let status = Line::from(spans);
    let bar = Paragraph::new(status);
    frame.render_widget(bar, area);
}

pub(super) fn render_planning_status_bar(frame: &mut Frame, area: Rect, state: &AppState) {
    let mut spans = vec![
        Span::styled(
            " q ",
            Style::default()
                .fg(Color::Black)
                .bg(Color::DarkGray)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw(" quit  "),
        Span::styled(
            " ↑↓ ",
            Style::default()
                .fg(Color::Black)
                .bg(Color::DarkGray)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw(" scroll  "),
        Span::styled(
            " p ",
            Style::default()
                .fg(Color::Black)
                .bg(Color::DarkGray)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw(" patterns"),
    ];

    if state.last_orchestrator_outcome.is_some() {
        spans.push(Span::styled(
            "  f ",
            Style::default()
                .fg(Color::Black)
                .bg(Color::DarkGray)
                .add_modifier(Modifier::BOLD),
        ));
        spans.push(Span::raw(" findings"));
    }

    if let Some((_ts, msg)) = state.log_messages.last() {
        spans.push(Span::styled(
            format!("  {}", truncate_str(msg, 60)),
            Style::default().fg(Color::DarkGray),
        ));
    }

    if let Some(ref version) = state.update_available {
        spans.push(Span::styled(
            format!(" | v{} available — `foundry update`", version),
            Style::default()
                .fg(Color::Green)
                .add_modifier(Modifier::BOLD),
        ));
    }

    frame.render_widget(Paragraph::new(Line::from(spans)), area);
}

pub(super) fn render_running_explorer_status_bar(frame: &mut Frame, area: Rect, state: &AppState) {
    let mut spans = vec![
        Span::styled(
            " \u{2191}\u{2193} ",
            Style::default()
                .fg(Color::Black)
                .bg(Color::DarkGray)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw(" navigate  "),
        Span::styled(
            " Enter ",
            Style::default()
                .fg(Color::Black)
                .bg(Color::DarkGray)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw(" open  "),
        Span::styled(
            " Tab ",
            Style::default()
                .fg(Color::Black)
                .bg(Color::Rgb(227, 115, 75))
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw(" dashboard  "),
        Span::styled(
            " q ",
            Style::default()
                .fg(Color::Black)
                .bg(Color::DarkGray)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw(" stop"),
    ];

    // Extensions indicator
    let ext_status = format_running_extensions_status(&state.available_extensions);
    if !ext_status.is_empty() {
        spans.push(Span::styled(
            format!("  {} ", ext_status),
            Style::default().fg(Color::Rgb(227, 115, 75)),
        ));
    }

    if let Some(ref version) = state.update_available {
        spans.push(Span::styled(
            format!(" | v{} available -- `foundry update`", version),
            Style::default()
                .fg(Color::Green)
                .add_modifier(Modifier::BOLD),
        ));
    }

    frame.render_widget(Paragraph::new(Line::from(spans)), area);
}

fn format_running_extensions_status(extensions: &[ExtensionDisplayInfo]) -> String {
    if extensions.is_empty() {
        return String::new();
    }
    let active: Vec<&str> = extensions
        .iter()
        .filter(|e| e.selected)
        .map(|e| e.name.as_str())
        .collect();
    if active.is_empty() {
        return "Ext: none".to_string();
    }
    format!("Ext: {} ({} active)", active.join(", "), active.len())
}
