use ratatui::{
    layout::Rect,
    style::{Color, Modifier, Style},
    text::{Line, Span},
    widgets::{Block, Borders, List, ListItem, Paragraph},
    Frame,
};

use super::{pane_border_style, pane_border_type};
use crate::agent::AgentRole;
use crate::app::{AppPhase, AppState, ExtensionDisplayInfo, StreamState, TuiPane};
use crate::utils::truncate_str;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum RunningStatusBarAction {
    Quit,
    Settings,
    ToggleView,
    Patterns,
    Stats,
    Findings,
    Inject,
    Approve,
    Deny,
    Continue,
}

fn qrpba_stage_seen(stages: &[AgentRole], role: &AgentRole) -> bool {
    match role {
        AgentRole::Research => {
            stages.contains(&AgentRole::Research) || stages.contains(&AgentRole::Scout)
        }
        AgentRole::Reviewer => {
            stages.contains(&AgentRole::Reviewer) || stages.contains(&AgentRole::Fixer)
        }
        _ => stages.contains(role),
    }
}

fn qrpba_stage_active(
    active_stage_id: Option<&str>,
    active_role: Option<&AgentRole>,
    role: &AgentRole,
) -> bool {
    if let Some(stage_id) = active_stage_id {
        return match role {
            AgentRole::Query => stage_id == "query",
            AgentRole::Research => stage_id == "research" || stage_id == "scout",
            AgentRole::Planner => stage_id == "plan",
            AgentRole::Builder => stage_id == "implement",
            AgentRole::Reviewer => stage_id == "doubt",
            _ => false,
        };
    }

    active_role == Some(role)
        || (*role == AgentRole::Research && active_role == Some(&AgentRole::Scout))
        || (*role == AgentRole::Reviewer && active_role == Some(&AgentRole::Fixer))
}

pub fn running_status_bar_hit_test(
    area: Rect,
    col: u16,
    state: &AppState,
) -> Option<RunningStatusBarAction> {
    if col < area.x || col >= area.x + area.width {
        return None;
    }

    if matches!(state.phase, AppPhase::Planning) {
        let mut x = area.x;
        let buttons: &[(&str, &str, RunningStatusBarAction)] = &[
            (" q ", " quit  ", RunningStatusBarAction::Quit),
            (
                " \u{2191}\u{2193} ",
                " scroll  ",
                RunningStatusBarAction::Quit,
            ), // non-actionable, skip
            (" p ", " patterns", RunningStatusBarAction::Patterns),
        ];
        for &(key, label, action) in buttons {
            let w = key.chars().count() as u16 + label.chars().count() as u16;
            if col >= x && col < x + w {
                if matches!(action, RunningStatusBarAction::Quit) && key == " q " {
                    return Some(RunningStatusBarAction::Quit);
                }
                if matches!(action, RunningStatusBarAction::Patterns) {
                    return Some(action);
                }
                return None;
            }
            x += w;
        }
        if state.last_orchestrator_outcome.is_some() {
            let w = "  f ".chars().count() as u16 + " findings".chars().count() as u16;
            if col >= x && col < x + w {
                return Some(RunningStatusBarAction::Findings);
            }
        }
        return None;
    }

    let mut x = area.x;
    let stop_label = if state.dual_arena_ready() {
        " Startup "
    } else {
        " Stop "
    };
    // Stop button: label + Esc key hint are one click target
    let stop_w = stop_label.chars().count() as u16 + " Esc ".chars().count() as u16;
    if col >= x && col < x + stop_w {
        return Some(RunningStatusBarAction::Quit);
    }
    x += stop_w;
    x += 2; // gap
    let base_buttons: Vec<(&str, &str, Option<RunningStatusBarAction>)> = vec![
        (" Ctrl+C ", " force quit  ", None),
        (" \u{2191}\u{2193} ", " scroll  ", None),
        (" i ", " inject  ", Some(RunningStatusBarAction::Inject)),
        (" PgUp/PgDn ", " queue  ", None),
        (" p ", " patterns  ", Some(RunningStatusBarAction::Patterns)),
        (" s ", " stats  ", Some(RunningStatusBarAction::Stats)),
        ("  ? ", " settings", Some(RunningStatusBarAction::Settings)),
    ];

    for (key, label, action) in &base_buttons {
        let w = key.chars().count() as u16 + label.chars().count() as u16;
        if col >= x && col < x + w {
            return *action;
        }
        x += w;
    }

    if state.awaiting_commit_approval {
        let approve_w = "  y ".chars().count() as u16 + " approve  ".chars().count() as u16;
        if col >= x && col < x + approve_w {
            return Some(RunningStatusBarAction::Approve);
        }
        x += approve_w;
        let deny_w = "  n ".chars().count() as u16 + " deny  ".chars().count() as u16;
        if col >= x && col < x + deny_w {
            return Some(RunningStatusBarAction::Deny);
        }
        x += deny_w;
    } else if state.awaiting_review {
        let w = "  Enter ".chars().count() as u16
            + if state.awaiting_pr.is_some() {
                " skip wait"
            } else {
                " continue"
            }
            .chars()
            .count() as u16;
        if col >= x && col < x + w {
            return Some(RunningStatusBarAction::Continue);
        }
        x += w;
    }

    if state.last_orchestrator_outcome.is_some() {
        let w = "  f ".chars().count() as u16 + " findings".chars().count() as u16;
        if col >= x && col < x + w {
            return Some(RunningStatusBarAction::Findings);
        }
        x += w;
    }

    // discovery_info is rendered before Tab
    if state.discovery_round > 0 {
        let info = format!(" | loop round {} ", state.discovery_round);
        x += info.chars().count() as u16;
    }

    // Tab toggle
    let tab_w = "  Tab ".chars().count() as u16
        + if state.show_running_explorer {
            " dashboard"
        } else {
            " explore"
        }
        .chars()
        .count() as u16;
    if col >= x && col < x + tab_w {
        return Some(RunningStatusBarAction::ToggleView);
    }

    None
}

pub enum RunningHeaderTab {
    Dashboard,
    Explore,
}

pub fn running_header_tab_hit_test(state: &AppState, column: u16) -> Option<RunningHeaderTab> {
    let project_len = if state.project_name.is_empty() {
        "  FOUNDRY ".len()
    } else {
        state.project_name.len() + 3
    };
    let status_len = if matches!(state.phase, AppPhase::Startup) {
        " STOPPED ".len()
    } else if matches!(state.phase, AppPhase::Planning) {
        " PLANNING ".len()
    } else if state.dual_arena_ready() {
        " DUAL COMPLETE ".len()
    } else if state.stop_after_task {
        " STOPPING ".len()
    } else if state.awaiting_commit_approval {
        " APPROVAL ".len()
    } else if state.awaiting_review {
        if state.awaiting_pr.is_some() {
            " POLLING PR ".len()
        } else {
            " PAUSED (Review) ".len()
        }
    } else {
        " RUNNING ".len()
    };
    let mode_len = match state.run_mode.as_str() {
        "sprint" => " Sprint ".len(),
        "review" => " Review ".len(),
        _ => " Auto ".len(),
    };
    // project + " " + status + "  " + mode + "  "
    let tabs_start = (project_len + 1 + status_len + 2 + mode_len + 2) as u16;
    let dashboard_end = tabs_start + " Dashboard ".len() as u16;
    let explore_start = dashboard_end + 1;
    let explore_end = explore_start + " Explore ".len() as u16;

    if column >= tabs_start && column < dashboard_end {
        Some(RunningHeaderTab::Dashboard)
    } else if column >= explore_start && column < explore_end {
        Some(RunningHeaderTab::Explore)
    } else {
        None
    }
}

pub(super) fn render_header(frame: &mut Frame, area: Rect, state: &AppState) {
    // Label for the "Current Task" table row -- all status lines align after this width.
    const TASK_LABEL: &str = "  Current Task  ";
    const NEXT_LABEL: &str = "  Next Task     ";
    let label_len = TASK_LABEL.len();
    let desc_width = area.width.saturating_sub(label_len as u16) as usize;
    let task_line = if let Some(ref task) = state.current_task {
        format!("{} — {}", task.id, task.short_desc(desc_width))
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
            format!(
                "  Design — {}: {}{}{}",
                iter_label, role, model_suffix, findings
            )
        } else {
            format!("  Planning — {}", planning.label)
        }
    } else if state.is_discovering {
        "  Loop — scanning for new work...".to_string()
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

        let activity = match state.stream_state {
            StreamState::WritingText => format!(
                "{} writing... ({} chunks)",
                spinner, state.stream_text_delta_count
            ),
            StreamState::Reading => {
                if state.status_summary.is_empty() {
                    format!("{} reading...", spinner)
                } else {
                    format!("{} {}", spinner, state.status_summary)
                }
            }
            StreamState::Idle => {
                if state.agent_output.is_empty() {
                    format!("{} thinking...", spinner)
                } else {
                    format!("{} {} events", spinner, state.events_received)
                }
            }
        };

        format!(
            "  ⎿ {} ({}) | {}m {}s | {}",
            role, model, mins, secs, activity
        )
    } else {
        String::new()
    };

    let agent_line = if let Some((total, done)) = state.parallel_builder_progress {
        format!("{} [parallel: {}/{}]", agent_line, done, total)
    } else {
        agent_line
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
                } else if matches!(state.phase, AppPhase::Planning) {
                    " PLANNING "
                } else if state.dual_arena_ready() {
                    " DUAL COMPLETE "
                } else if state.stop_after_task {
                    " STOPPING "
                } else if state.awaiting_commit_approval {
                    " APPROVAL "
                } else if state.awaiting_review {
                    if state.awaiting_pr.is_some() {
                        " POLLING PR "
                    } else {
                        " PAUSED (Review) "
                    }
                } else {
                    " RUNNING "
                },
                Style::default()
                    .fg(Color::Black)
                    .bg(if matches!(state.phase, AppPhase::Startup) {
                        Color::DarkGray
                    } else if matches!(state.phase, AppPhase::Planning) || state.dual_arena_ready()
                    {
                        Color::Magenta
                    } else if state.stop_after_task
                        || state.awaiting_review
                        || state.awaiting_commit_approval
                    {
                        Color::Yellow
                    } else {
                        Color::Green
                    })
                    .add_modifier(Modifier::BOLD),
            ),
            Span::raw("  "),
            Span::styled(
                match state.run_mode.as_str() {
                    "sprint" => " Sprint ",
                    "review" => " Review ",
                    _ => " Auto ",
                },
                Style::default()
                    .fg(Color::Black)
                    .bg(match state.run_mode.as_str() {
                        "sprint" => Color::Cyan,
                        "review" => Color::Yellow,
                        _ => Color::Green,
                    })
                    .add_modifier(Modifier::BOLD),
            ),
            Span::raw("  "),
            Span::styled(
                " Dashboard ",
                if !state.show_running_explorer {
                    Style::default()
                        .fg(state.tui_theme.text)
                        .bg(state.tui_theme.surface)
                        .add_modifier(Modifier::BOLD)
                } else {
                    Style::default().fg(state.tui_theme.muted)
                },
            ),
            Span::raw(" "),
            Span::styled(
                " Explore ",
                if state.show_running_explorer {
                    Style::default()
                        .fg(state.tui_theme.text)
                        .bg(state.tui_theme.surface)
                        .add_modifier(Modifier::BOLD)
                } else {
                    Style::default().fg(state.tui_theme.muted)
                },
            ),
        ]),
        if state.current_task.is_some() {
            Line::from(vec![
                Span::styled(TASK_LABEL, Style::default().fg(state.tui_theme.muted)),
                Span::styled(
                    task_line.clone(),
                    Style::default()
                        .fg(state.tui_theme.text)
                        .add_modifier(Modifier::BOLD),
                ),
            ])
        } else {
            Line::from(Span::styled(
                task_line.clone(),
                Style::default()
                    .fg(state.tui_theme.text)
                    .add_modifier(Modifier::BOLD),
            ))
        },
        {
            let mut agent_spans = vec![Span::styled(
                &agent_line,
                Style::default().fg(state.tui_theme.muted),
            )];
            if !state.status_summary.is_empty() && !agent_line.is_empty() {
                let prefix = " | ";
                let used = agent_line.len() + prefix.len();
                let avail = (area.width as usize).saturating_sub(used);
                if avail > 4 {
                    let summary = truncate_str(&state.status_summary, avail);
                    agent_spans.push(Span::styled(
                        format!("{}{}", prefix, summary),
                        Style::default().fg(state.tui_theme.muted),
                    ));
                }
            }
            Line::from(agent_spans)
        },
    ];

    if let Some(label) = state.active_builder_label() {
        header_text[0].spans.push(Span::raw("  "));
        header_text[0].spans.push(Span::styled(
            format!(" {label} "),
            Style::default()
                .fg(Color::Black)
                .bg(state.tui_theme.accent)
                .add_modifier(Modifier::BOLD),
        ));
    }

    // Sandbox indicator badge
    {
        let (sandbox_label, sandbox_color) = if state.sandbox_active {
            (" sandboxed ", Color::Green)
        } else if state.sandbox_enabled {
            (" sandbox degraded ", Color::Yellow)
        } else {
            (" sandbox disabled ", Color::Red)
        };
        header_text[0].spans.push(Span::raw("  "));
        header_text[0].spans.push(Span::styled(
            sandbox_label,
            Style::default()
                .fg(Color::Black)
                .bg(sandbox_color)
                .add_modifier(Modifier::BOLD),
        ));
    }

    if state.awaiting_commit_approval {
        if let Some(ref tid) = state.approval_task_id {
            let ptype = state.approval_proposed_type.as_deref().unwrap_or("feat");
            header_text.push(Line::from(vec![
                Span::styled(
                    format!("  Commit {} as {}? ", tid, ptype),
                    Style::default()
                        .fg(Color::Yellow)
                        .add_modifier(Modifier::BOLD),
                ),
                Span::styled("[y] approve  [n] deny", Style::default().fg(Color::White)),
            ]));
        }
    } else if state.awaiting_review {
        if let Some(pr_num) = state.awaiting_pr {
            let ago_text = match state.pr_poll_last_check {
                Some(last) => {
                    let elapsed = last.elapsed().as_secs();
                    if elapsed < 60 {
                        format!("last checked {}s ago", elapsed)
                    } else {
                        format!("last checked {}m ago", elapsed / 60)
                    }
                }
                None => "polling not started yet".to_string(),
            };
            header_text.push(Line::from(Span::styled(
                format!("  Waiting for PR #{} review... ({})", pr_num, ago_text),
                Style::default().fg(state.tui_theme.warning),
            )));
        } else {
            header_text.push(Line::from(Span::styled(
                "  Waiting for review -- press Enter to continue",
                Style::default().fg(state.tui_theme.warning),
            )));
        }
    }

    if let Some(next_task) = state.next_task_hint.as_ref() {
        let content_width = area.width.saturating_sub(label_len as u16) as usize;
        header_text.push(Line::from(vec![
            Span::styled(NEXT_LABEL, Style::default().fg(state.tui_theme.muted)),
            Span::styled(
                truncate_str(next_task, content_width).to_string(),
                Style::default()
                    .fg(state.tui_theme.info)
                    .add_modifier(Modifier::BOLD),
            ),
        ]));
    }

    // Log line removed from header -- the agent name + timer on line 3 already
    // conveys the same info. The status bar at the bottom shows the latest log.

    let header = Paragraph::new(header_text).block(
        Block::default()
            .borders(Borders::BOTTOM)
            .border_style(Style::default().fg(state.tui_theme.border)),
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

/// Returns true if the given assistant-output line reads like a phase
/// transition sentence ("Let me ...", "I'll now ...", a colon-terminated
/// header). Used to render those sentences with extra emphasis. Skips
/// lines that already carry a structured marker prefix (`[tool]`, etc.)
/// so we don't double-style streaming tool output.
pub(super) fn is_phase_transition(line: &str) -> bool {
    let trimmed = line.trim();
    if trimmed.is_empty() {
        return false;
    }
    if trimmed.starts_with('[') {
        return false;
    }
    let lower = trimmed.to_ascii_lowercase();
    let prefixes = [
        "let me ",
        "i'll now ",
        "i have enough ",
        "now i'll ",
        "i'll start ",
        "let's ",
    ];
    for p in prefixes.iter() {
        if lower.starts_with(p) {
            return true;
        }
    }
    if trimmed.ends_with(':')
        && trimmed.chars().count() <= 80
        && !trimmed.contains(['[', ']', '{', '}', '<', '>', '(', ')'])
    {
        return true;
    }
    false
}

pub(super) fn style_for_line(line: &str, theme: &super::theme::TuiTheme) -> Style {
    if line.starts_with("[stderr]") {
        Style::default().fg(theme.error)
    } else if line.starts_with("[tool]") {
        Style::default().fg(theme.info)
    } else if line.starts_with("[result]") {
        Style::default().fg(theme.muted)
    } else if line.starts_with("[info]") {
        Style::default().fg(theme.info)
    } else if line.starts_with("[rate limited]") {
        Style::default().fg(theme.warning)
    } else if line.starts_with("[injected]") {
        Style::default()
            .fg(theme.warning)
            .add_modifier(Modifier::BOLD)
    } else {
        Style::default().fg(theme.text)
    }
}

pub(super) fn render_agent_output(
    frame: &mut Frame,
    area: Rect,
    state: &AppState,
    focused: TuiPane,
) {
    let inner_width = area.width.saturating_sub(2) as usize;

    // Determine which output lines to render
    let (output_lines, scroll_offset) = if state.dual_build.active {
        // Show active tab's stream
        let tab = state.dual_build.tab;
        (state.dual_build.streams[tab].clone(), state.scroll_offset)
    } else {
        (state.agent_output.clone(), state.scroll_offset)
    };

    // Pre-wrap all lines, emphasizing phase-transition sentences with a
    // warning-colored bold style and surrounding blank lines.
    let mut wrapped: Vec<(String, Style)> = Vec::new();
    for line in output_lines.iter() {
        if is_phase_transition(line) {
            if wrapped.last().map(|(t, _)| !t.is_empty()).unwrap_or(false) {
                wrapped.push((String::new(), Style::default()));
            }
            let style = Style::default()
                .fg(state.tui_theme.warning)
                .add_modifier(Modifier::BOLD);
            for chunk in wrap_line(line, inner_width) {
                wrapped.push((chunk, style));
            }
            wrapped.push((String::new(), Style::default()));
        } else {
            let style = style_for_line(line, &state.tui_theme);
            for chunk in wrap_line(line, inner_width) {
                wrapped.push((chunk, style));
            }
        }
    }

    let max_lines = if state.dual_build.active {
        area.height.saturating_sub(3) as usize // 1 extra line for tab header
    } else {
        area.height.saturating_sub(2) as usize
    };
    let total_lines = wrapped.len();
    let start = total_lines.saturating_sub(max_lines + scroll_offset);
    let end = total_lines.saturating_sub(scroll_offset);

    let items: Vec<ListItem> = wrapped[start..end]
        .iter()
        .map(|(text, style)| ListItem::new(Span::styled(text.as_str(), *style)))
        .collect();

    // Build tab header for dual mode
    let mut title_spans = Vec::new();
    if state.dual_build.active {
        for i in 0..2 {
            let label = &state.dual_build.models[i];
            let count = state.dual_build.event_counts[i];
            let done = state.dual_build.finished[i];
            let stage = state.dual_build.stages[i]
                .as_ref()
                .map(|r| format!("{}", r))
                .unwrap_or_else(|| "...".to_string());
            let status = if done { "done".to_string() } else { stage };
            let tab_text = format!(" {}: {} [{}] ({}ev) ", i + 1, label, status, count);
            let style = if i == state.dual_build.tab {
                Style::default()
                    .fg(state.tui_theme.accent)
                    .add_modifier(Modifier::BOLD)
            } else {
                Style::default().fg(state.tui_theme.muted)
            };
            title_spans.push(Span::styled(tab_text, style));
        }
    }

    let title = if state.dual_build.active {
        Span::styled(
            " Dual Pipeline ",
            Style::default()
                .fg(state.tui_theme.accent)
                .add_modifier(Modifier::BOLD),
        )
    } else if let Some((ref role, _)) = state.current_agent {
        let color = match role {
            AgentRole::Scout => Color::LightBlue,
            AgentRole::Query => Color::LightCyan,
            AgentRole::Research => Color::LightBlue,
            AgentRole::Planner => Color::Magenta,
            AgentRole::Builder => Color::Green,
            AgentRole::Reviewer => Color::Cyan,
            AgentRole::Fixer => Color::Yellow,
            AgentRole::PlanReview => Color::Magenta,
            AgentRole::Discovery => Color::Blue,
            AgentRole::Coach => Color::LightYellow,
        };
        Span::styled(
            format!(" {} ", role),
            Style::default().fg(color).add_modifier(Modifier::BOLD),
        )
    } else {
        Span::styled(" Agent ", Style::default().fg(state.tui_theme.muted))
    };

    // If dual-build with tab header, prepend tab line as first ListItem
    let mut all_items = Vec::new();
    if state.dual_build.active && !title_spans.is_empty() {
        all_items.push(ListItem::new(Line::from(title_spans)));
    }
    all_items.extend(items);

    let list = List::new(all_items).block(
        Block::default()
            .borders(Borders::ALL)
            .border_style(pane_border_style(
                focused,
                TuiPane::AgentOutput,
                &state.tui_theme,
            ))
            .border_type(pane_border_type(focused, TuiPane::AgentOutput))
            .title(title),
    );

    frame.render_widget(list, area);
}

pub(super) fn render_task_queue(frame: &mut Frame, area: Rect, state: &AppState, focused: TuiPane) {
    if state.task_queue.is_empty() {
        let empty = Paragraph::new(Span::styled(
            " No tasks in queue yet.",
            Style::default().fg(state.tui_theme.muted),
        ))
        .block(
            Block::default()
                .borders(Borders::ALL)
                .border_style(pane_border_style(
                    focused,
                    TuiPane::TaskQueue,
                    &state.tui_theme,
                ))
                .border_type(pane_border_type(focused, TuiPane::TaskQueue))
                .title(Span::styled(
                    " Task Queue ",
                    Style::default()
                        .fg(state.tui_theme.text)
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

            // Pipeline indicator. is_current must take priority over
            // task_history: a task that previously failed (WIP, `!` written
            // to TASKS.md) leaves a history entry behind, and a retry would
            // otherwise keep displaying the prior attempt's `!` while the
            // new run is in progress.
            let pipeline_spans = if is_current {
                // Current: show progress through pipeline
                let all_stages = [
                    ("Q", AgentRole::Query),
                    ("R", AgentRole::Research),
                    ("P", AgentRole::Planner),
                    ("B", AgentRole::Builder),
                    ("A", AgentRole::Reviewer),
                ];
                let active = state.current_agent.as_ref().map(|(r, _)| r);
                let active_stage_id = state.current_agent_stage_id.as_deref();
                let mut spans = vec![Span::styled(" ", Style::default())];
                for (label, role) in &all_stages {
                    let seen = qrpba_stage_seen(&state.task_stages_seen, role);
                    let is_active = qrpba_stage_active(active_stage_id, active, role);
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
            } else if let Some(history) = state.task_history.get(&task.id) {
                // Completed: show Q>R>P>B>A with colors
                let all_stages = [
                    ("Q", AgentRole::Query),
                    ("R", AgentRole::Research),
                    ("P", AgentRole::Planner),
                    ("B", AgentRole::Builder),
                    ("A", AgentRole::Reviewer),
                ];
                let verify_color = if history.passed_review {
                    Color::Green
                } else {
                    Color::Red
                };
                let mut spans = vec![Span::styled(" ", Style::default())];
                for (label, role) in &all_stages {
                    let ran = qrpba_stage_seen(&history.stages_seen, role);
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
            .border_style(pane_border_style(
                focused,
                TuiPane::TaskQueue,
                &state.tui_theme,
            ))
            .border_type(pane_border_type(focused, TuiPane::TaskQueue))
            .title(Span::styled(
                title,
                Style::default()
                    .fg(state.tui_theme.text)
                    .add_modifier(Modifier::BOLD),
            )),
    );

    frame.render_widget(list, area);
}

pub(super) fn render_patterns(
    frame: &mut Frame,
    area: Rect,
    state: &AppState,
    _config: &crate::config::Config,
    focused: TuiPane,
) {
    use crate::app::PatternEventKind;

    let used_count = state
        .session_patterns
        .iter()
        .filter(|p| p.kind == PatternEventKind::Used)
        .count();
    let learned_count = state
        .session_patterns
        .iter()
        .filter(|p| p.kind == PatternEventKind::Learned)
        .count();
    let title = format!(
        " Patterns ({} injected, {} learned) ",
        used_count, learned_count
    );
    let max_lines = area.height.saturating_sub(2) as usize;

    if state.session_patterns.is_empty() {
        let empty = Paragraph::new(Span::styled(
            " Pattern activity will appear here.",
            Style::default().fg(state.tui_theme.muted),
        ))
        .block(
            Block::default()
                .borders(Borders::ALL)
                .border_style(pane_border_style(
                    focused,
                    TuiPane::PatternsLearned,
                    &state.tui_theme,
                ))
                .border_type(pane_border_type(focused, TuiPane::PatternsLearned))
                .title(Span::styled(
                    " Patterns ",
                    Style::default()
                        .fg(state.tui_theme.info)
                        .add_modifier(Modifier::BOLD),
                )),
        );
        frame.render_widget(empty, area);
        return;
    }

    let total_patterns = state.session_patterns.len();
    let scroll = state.patterns_scroll.min(total_patterns.saturating_sub(1));
    let items: Vec<ListItem> = state
        .session_patterns
        .iter()
        .rev()
        .skip(scroll)
        .take(max_lines)
        .enumerate()
        .map(|(i, event)| {
            let num = total_patterns.saturating_sub(scroll + i);
            let (label, color) = match event.kind {
                PatternEventKind::Used => ("used", Color::Green),
                PatternEventKind::Learned => ("new", Color::Yellow),
            };
            ListItem::new(Line::from(vec![
                Span::styled(format!(" #{} ", num), Style::default().fg(color)),
                Span::styled(format!("[{}] ", label), Style::default().fg(color)),
                Span::styled(
                    truncate_str(&event.title, area.width.saturating_sub(14) as usize),
                    Style::default().fg(state.tui_theme.text),
                ),
            ]))
        })
        .collect();

    let list = List::new(items).block(
        Block::default()
            .borders(Borders::ALL)
            .border_style(pane_border_style(
                focused,
                TuiPane::PatternsLearned,
                &state.tui_theme,
            ))
            .border_type(pane_border_type(focused, TuiPane::PatternsLearned))
            .title(Span::styled(
                title,
                Style::default()
                    .fg(state.tui_theme.info)
                    .add_modifier(Modifier::BOLD),
            )),
    );
    frame.render_widget(list, area);
}

pub(super) fn render_extensions_used(
    frame: &mut Frame,
    area: Rect,
    state: &AppState,
    focused: TuiPane,
) {
    let total = state.session_extensions_used.len();
    let total_inj: usize = state.extension_inject_count.values().sum();
    let total_ref: usize = state.extension_reference_count.values().sum();
    let title = format!(" Extensions ({} inj, {} ref) ", total_inj, total_ref);
    let max_lines = area.height.saturating_sub(2) as usize;

    if state.session_extensions_used.is_empty() {
        let empty = Paragraph::new(Span::styled(
            " Extension usage will appear here.",
            Style::default().fg(state.tui_theme.muted),
        ))
        .block(
            Block::default()
                .borders(Borders::ALL)
                .border_style(pane_border_style(
                    focused,
                    TuiPane::Extensions,
                    &state.tui_theme,
                ))
                .border_type(pane_border_type(focused, TuiPane::Extensions))
                .title(Span::styled(
                    " Extensions Used ",
                    Style::default()
                        .fg(state.tui_theme.accent)
                        .add_modifier(Modifier::BOLD),
                )),
        );
        frame.render_widget(empty, area);
        return;
    }

    let items: Vec<ListItem> = state
        .session_extensions_used
        .iter()
        .rev()
        .take(max_lines)
        .enumerate()
        .map(|(i, event)| {
            let num = total.saturating_sub(i);
            ListItem::new(Line::from(vec![
                Span::styled(
                    format!(" #{} ", num),
                    Style::default().fg(state.tui_theme.accent),
                ),
                Span::styled(
                    &event.name,
                    Style::default()
                        .fg(state.tui_theme.text)
                        .add_modifier(Modifier::BOLD),
                ),
                Span::styled(
                    format!(" ({})", event.task_id),
                    Style::default().fg(state.tui_theme.muted),
                ),
            ]))
        })
        .collect();

    let list = List::new(items).block(
        Block::default()
            .borders(Borders::ALL)
            .border_style(pane_border_style(
                focused,
                TuiPane::Extensions,
                &state.tui_theme,
            ))
            .border_type(pane_border_type(focused, TuiPane::Extensions))
            .title(Span::styled(
                title,
                Style::default()
                    .fg(state.tui_theme.accent)
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
        format!(" | loop round {} ", state.discovery_round)
    } else {
        String::new()
    };

    let mut spans = vec![
        Span::styled(
            if state.dual_arena_ready() {
                " Startup "
            } else {
                " Stop "
            },
            Style::default()
                .fg(Color::Black)
                .bg(state.tui_theme.error)
                .add_modifier(Modifier::BOLD),
        ),
        Span::styled(
            " Esc ",
            Style::default()
                .fg(Color::Black)
                .bg(state.tui_theme.muted)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw("  "),
        Span::styled(
            " Ctrl+C ",
            Style::default()
                .fg(Color::Black)
                .bg(state.tui_theme.muted)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw(" force quit  "),
        Span::styled(
            " ↑↓ ",
            Style::default()
                .fg(Color::Black)
                .bg(state.tui_theme.muted)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw(" scroll  "),
        Span::styled(
            " i ",
            Style::default()
                .fg(Color::Black)
                .bg(state.tui_theme.muted)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw(" inject  "),
        Span::styled(
            " PgUp/PgDn ",
            Style::default()
                .fg(Color::Black)
                .bg(state.tui_theme.muted)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw(" queue  "),
        Span::styled(
            " p ",
            Style::default()
                .fg(Color::Black)
                .bg(state.tui_theme.muted)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw(" patterns  "),
        Span::styled(
            " s ",
            Style::default()
                .fg(Color::Black)
                .bg(state.tui_theme.muted)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw(" stats  "),
        Span::styled(
            "  ? ",
            Style::default()
                .fg(Color::Black)
                .bg(state.tui_theme.muted)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw(" settings"),
    ];

    if state.awaiting_commit_approval {
        spans.push(Span::styled(
            "  y ",
            Style::default().fg(Color::Black).bg(Color::Yellow),
        ));
        spans.push(Span::styled(" approve  ", Style::default().fg(Color::Gray)));
        spans.push(Span::styled(
            "  n ",
            Style::default().fg(Color::Black).bg(Color::Yellow),
        ));
        spans.push(Span::styled(" deny  ", Style::default().fg(Color::Gray)));
    } else if state.awaiting_review {
        spans.push(Span::styled(
            "  Enter ",
            Style::default()
                .fg(Color::Black)
                .bg(Color::Yellow)
                .add_modifier(Modifier::BOLD),
        ));
        if state.awaiting_pr.is_some() {
            spans.push(Span::raw(" skip wait"));
        } else {
            spans.push(Span::raw(" continue"));
        }
    }

    if state.last_orchestrator_outcome.is_some() {
        spans.push(Span::styled(
            "  f ",
            Style::default()
                .fg(Color::Black)
                .bg(state.tui_theme.muted)
                .add_modifier(Modifier::BOLD),
        ));
        spans.push(Span::raw(" findings"));
    }

    spans.push(Span::styled(
        discovery_info,
        Style::default().fg(state.tui_theme.muted),
    ));

    // Tab toggle -- always visible on Dashboard
    spans.push(Span::styled(
        "  Tab ",
        Style::default()
            .fg(Color::Black)
            .bg(state.tui_theme.accent)
            .add_modifier(Modifier::BOLD),
    ));
    spans.push(Span::raw(if state.show_running_explorer {
        " dashboard"
    } else {
        " explore"
    }));

    // Extensions indicator (read-only during running)
    let ext_status = format_running_extensions_status(
        &state.available_extensions,
        &state.extension_inject_count,
        &state.extension_reference_count,
    );
    if !ext_status.is_empty() {
        spans.push(Span::styled(
            format!("  {} ", ext_status),
            Style::default().fg(state.tui_theme.accent),
        ));
    }

    if let Some(ref version) = state.update_available {
        spans.push(Span::styled(
            format!(" | v{} available — `foundry update`", version),
            Style::default()
                .fg(state.tui_theme.success)
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
            " Stop ",
            Style::default()
                .fg(Color::Black)
                .bg(state.tui_theme.error)
                .add_modifier(Modifier::BOLD),
        ),
        Span::styled(
            " Esc ",
            Style::default()
                .fg(Color::Black)
                .bg(state.tui_theme.muted)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw("  "),
        Span::styled(
            " ↑↓ ",
            Style::default()
                .fg(Color::Black)
                .bg(state.tui_theme.muted)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw(" scroll  "),
        Span::styled(
            " p ",
            Style::default()
                .fg(Color::Black)
                .bg(state.tui_theme.muted)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw(" patterns"),
    ];

    if state.last_orchestrator_outcome.is_some() {
        spans.push(Span::styled(
            "  f ",
            Style::default()
                .fg(Color::Black)
                .bg(state.tui_theme.muted)
                .add_modifier(Modifier::BOLD),
        ));
        spans.push(Span::raw(" findings"));
    }

    if let Some(ref version) = state.update_available {
        spans.push(Span::styled(
            format!(" | v{} available — `foundry update`", version),
            Style::default()
                .fg(state.tui_theme.success)
                .add_modifier(Modifier::BOLD),
        ));
    }

    frame.render_widget(Paragraph::new(Line::from(spans)), area);
}

pub(super) fn render_running_explorer_status_bar(frame: &mut Frame, area: Rect, state: &AppState) {
    let mut spans = vec![
        Span::styled(
            if state.dual_arena_ready() {
                " Startup "
            } else {
                " Stop "
            },
            Style::default()
                .fg(Color::Black)
                .bg(state.tui_theme.error)
                .add_modifier(Modifier::BOLD),
        ),
        Span::styled(
            " Esc ",
            Style::default()
                .fg(Color::Black)
                .bg(state.tui_theme.muted)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw("  "),
        Span::styled(
            " \u{2191}\u{2193} ",
            Style::default()
                .fg(Color::Black)
                .bg(state.tui_theme.muted)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw(" navigate  "),
        Span::styled(
            " Enter ",
            Style::default()
                .fg(Color::Black)
                .bg(state.tui_theme.muted)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw(" open  "),
        Span::styled(
            " Tab ",
            Style::default()
                .fg(Color::Black)
                .bg(state.tui_theme.accent)
                .add_modifier(Modifier::BOLD),
        ),
        Span::raw(" dashboard"),
    ];

    // Extensions indicator
    let ext_status = format_running_extensions_status(
        &state.available_extensions,
        &state.extension_inject_count,
        &state.extension_reference_count,
    );
    if !ext_status.is_empty() {
        spans.push(Span::styled(
            format!("  {} ", ext_status),
            Style::default().fg(state.tui_theme.accent),
        ));
    }

    if let Some(ref version) = state.update_available {
        spans.push(Span::styled(
            format!(" | v{} available -- `foundry update`", version),
            Style::default()
                .fg(state.tui_theme.success)
                .add_modifier(Modifier::BOLD),
        ));
    }

    frame.render_widget(Paragraph::new(Line::from(spans)), area);
}

fn format_running_extensions_status(
    extensions: &[ExtensionDisplayInfo],
    inject_count: &std::collections::HashMap<String, usize>,
    reference_count: &std::collections::HashMap<String, usize>,
) -> String {
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
    let parts: Vec<String> = active
        .iter()
        .map(|name| {
            let inj = inject_count.get(*name).copied().unwrap_or(0);
            let refs = reference_count.get(*name).copied().unwrap_or(0);
            if inj > 0 || refs > 0 {
                format!("{} ({} inj, {} ref)", name, inj, refs)
            } else {
                name.to_string()
            }
        })
        .collect();
    format!("Ext: {}", parts.join(", "))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn qrpba_stage_active_uses_stage_id_over_builder_role_for_custom_cards() {
        assert!(!qrpba_stage_active(
            Some("security"),
            Some(&AgentRole::Builder),
            &AgentRole::Builder,
        ));
        assert!(qrpba_stage_active(
            Some("implement"),
            Some(&AgentRole::Builder),
            &AgentRole::Builder,
        ));
    }

    #[test]
    fn is_phase_transition_matches_let_me_phrasings() {
        assert!(is_phase_transition("Let me write the implementation plan."));
        assert!(is_phase_transition("Let's verify this works."));
        assert!(is_phase_transition("I'll now write the test."));
        assert!(is_phase_transition("I have enough context to start."));
        assert!(is_phase_transition("Now I'll generate the plan:"));
    }

    #[test]
    fn is_phase_transition_rejects_regular_text_and_code() {
        assert!(!is_phase_transition("The function returns the correct value."));
        assert!(!is_phase_transition("[tool] Read /tmp/x"));
        assert!(!is_phase_transition("```rust"));
        assert!(!is_phase_transition("{ \"key\": 1 }"));
        assert!(!is_phase_transition("function foo() {"));
    }

    #[test]
    fn spinner_activity_uses_writing_label_when_streaming() {
        use chrono::Utc;
        use ratatui::backend::TestBackend;
        use ratatui::Terminal;
        use std::path::PathBuf;

        let mut state = AppState::new(PathBuf::from(".buildloop"));
        state.current_agent = Some((AgentRole::Builder, Utc::now()));
        state.current_agent_model = Some("Sonnet".to_string());
        state.stream_state = StreamState::WritingText;
        state.stream_text_delta_count = 5;

        let backend = TestBackend::new(220, 8);
        let mut terminal = Terminal::new(backend).expect("failed to create terminal");
        terminal
            .draw(|frame| render_header(frame, frame.area(), &state))
            .expect("failed to draw header");

        let buffer = terminal.backend().buffer();
        let area = *buffer.area();
        let rendered: String = (0..area.height)
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
            .join("\n");

        assert!(
            rendered.contains("writing... (5 chunks)"),
            "rendered: {}",
            rendered
        );
    }
}
