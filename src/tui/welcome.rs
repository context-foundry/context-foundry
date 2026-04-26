use ratatui::{
    style::{Color, Modifier, Style},
    text::{Line, Span},
    widgets::{Block, Borders, Clear, Paragraph},
    Frame,
};

use crate::app::AppState;
use super::theme::TuiTheme;

const LOGO: &[&str] = &[
    r" ____     _____   __  __  ______  ____    __   __   ______",
    r"/\  _`\  /\  __`\/\ \/\ \/\__  _\/\  _`\ /\ \ /\ \ /\__  _\",
    r"\ \ \/\_\\ \ \/\ \ \ `\\ \/_/\ \/\ \ \L\_\ `\`\/'/'\/_/\ \/",
    r" \ \ \/_/_\ \ \ \ \ \ , ` \ \ \ \ \ \  _\L`\/ > <     \ \ \",
    r"  \ \ \L\ \\ \ \_\ \ \ \`\ \ \ \ \ \ \ \L\ \ \/'/\`\   \ \ \",
    r"   \ \____/ \ \_____\ \_\ \_\ \ \_\ \ \____/ /\_\\ \_\  \ \_\",
    r"    \/___/   \/_____/\/_/\/_/  \/_/  \/___/  \/_/ \/_/   \/_/",
    r"",
    r" ____    _____   __  __  __  __  ____    ____    __    __",
    r"/\  _`\ /\  __`\/\ \/\ \/\ \/\ \/\  _`\ /\  _`\ /\ \  /\ \",
    r"\ \ \L\_\ \ \/\ \ \ \ \ \ \ `\\ \ \ \/\ \ \ \L\ \ `\`\\/'/",
    r" \ \  _\/\ \ \ \ \ \ \ \ \ \ , ` \ \ \ \ \ \ ,  /`\ `\ /'",
    r"  \ \ \/  \ \ \_\ \ \ \_\ \ \ \`\ \ \ \_\ \ \ \\ \ `\ \ \",
    r"   \ \_\   \ \_____\ \_____\ \_\ \_\ \____/\ \_\ \_\ \ \_\",
    r"    \/_/    \/_____/\/_____/\/_/\/_/\/___/  \/_/\/ /  \/_/",
];

const FALLBACK_MESSAGES: &[&str] = &[
    "Patterns remembered,\nbugs grow quiet at last --\nthe loop learns for you.",
    "Scout, plan, build, doubt --\nfour agents walk into code.\nOnly tests survive.",
    "In the foundry's glow,\ncontext shapes the molten thought --\npatterns cool as code.",
    "Agents come and go,\nbut the patterns they leave behind\nteach the ones that follow.",
    "A bug hides in plain sight.\nThe doubt agent squints, leans in --\n\"Line 42. Got you.\"",
    "What runs but never tires,\nlearns but never forgets,\nand builds but never ships?\n... A foundry with no git remote.",
    "Today's code is tomorrow's context.\nToday's context is yesterday's lesson.\nShip it.",
    "The planner whispers: \"Five files.\"\nThe builder replies: \"Twelve.\"\nThe reviewer sighs.",
    "Trust the loop.\nDoubt the output.\nShip the pattern.",
    "First it scouts. Then it plans.\nThen it builds. Then it doubts.\nThen it does it all again, slightly better.",
    "Some forge steel.\nSome forge code.\nWe forge context.",
    "Riddle: I run in circles\nbut always move forward.\nI break things to fix them.\nWhat am I?\n... A build loop.",
    "The best pattern is the one\nyou never have to learn twice.",
    "Dawn breaks on the loop --\nthe scout finds what changed last night,\nthe planner adapts.",
    "Three agents argue.\nThe reviewer breaks the tie.\nThe commit is clean.",
    "Haiku for the impatient:\nIt compiles. Ship it.\nThe tests will catch the rest. Right?\n... Right?",
    "What the builder starts,\nthe doubter must finish --\nthat is the contract.",
    "Context is not data.\nContext is the story data tells\nwhen you ask the right question.",
    "The foundry glows warm tonight.\nPatterns crystallize like iron.\nTomorrow: fewer bugs.",
    "A wise agent once said:\n\"I don't fix bugs.\nI prevent the conditions\nthat let them exist.\"",
    "Plan twice. Build once.\nOr build twice. Plan... eventually.\nBoth work here.",
    "Loops within loops --\nthe discovery agent finds\nwork the builder missed.",
    "Every WIP commit\nis a promise to return.\nEvery feat commit: kept.",
    "The scout reads the map.\nThe planner draws the route.\nThe builder drives.\nThe reviewer checks the mirrors.",
    "In the space between\nresearch and implementation,\nlives the plan nobody reads.",
    "Why did the agent cross the codebase?\nTo get to the other side... of the diff.",
    "Old code, new context --\nthe foundry melts both together.\nStronger alloy forms.",
    "The pattern library grows.\nEach entry: a scar healed,\na lesson forged in fire.",
    "Commit early. Commit often.\nBut first -- let the doubt agent\nhave its say.",
    "Roses are red,\ncompiler errors are long,\nthe foundry caught it\nbefore it went wrong.",
];

pub fn random_fallback_message() -> &'static str {
    pick_random(FALLBACK_MESSAGES)
}

fn pick_random(pool: &[&'static str]) -> &'static str {
    use std::collections::hash_map::DefaultHasher;
    use std::hash::{Hash, Hasher};
    use std::time::SystemTime;

    let mut hasher = DefaultHasher::new();
    SystemTime::now()
        .duration_since(SystemTime::UNIX_EPOCH)
        .unwrap_or_default()
        .as_nanos()
        .hash(&mut hasher);
    let idx = (hasher.finish() as usize) % pool.len();
    pool[idx]
}

pub fn render_welcome(frame: &mut Frame, state: &AppState) {
    let theme = &state.tui_theme;
    let area = frame.area();

    frame.render_widget(Clear, area);

    let mut lines: Vec<Line> = Vec::new();

    // Blank line
    lines.push(Line::from(""));

    // ASCII logo
    for row in LOGO {
        lines.push(Line::from(Span::styled(
            *row,
            Style::default().fg(theme.accent).add_modifier(Modifier::BOLD),
        )));
    }

    lines.push(Line::from(""));

    // Version + date
    let version = env!("CARGO_PKG_VERSION");
    let date = chrono::Local::now().format("%A, %B %-d, %Y").to_string();
    lines.push(Line::from(vec![
        Span::styled("   v", Style::default().fg(theme.muted)),
        Span::styled(version, Style::default().fg(theme.text)),
        Span::styled("  --  ", Style::default().fg(theme.muted)),
        Span::styled(&date, Style::default().fg(theme.text)),
    ]));

    lines.push(Line::from(""));

    // Provider status
    let provider_line = build_provider_line(state, theme);
    lines.push(provider_line);

    lines.push(Line::from(""));
    lines.push(Line::from(Span::styled(
        "   ───────────────────────────────────────",
        Style::default().fg(theme.border),
    )));
    lines.push(Line::from(""));

    // Message (LLM-generated or fallback)
    let message = if state.welcome_message.is_empty() {
        random_fallback_message().to_string()
    } else {
        state.welcome_message.clone()
    };
    for msg_line in message.lines() {
        lines.push(Line::from(Span::styled(
            format!("   {}", msg_line),
            Style::default().fg(theme.info),
        )));
    }

    lines.push(Line::from(""));
    lines.push(Line::from(""));

    // URL
    lines.push(Line::from(Span::styled(
        "   contextfoundry.dev",
        Style::default().fg(theme.muted),
    )));

    lines.push(Line::from(""));

    // Dismiss hint
    lines.push(Line::from(Span::styled(
        "   Press Enter to get started...",
        Style::default().fg(theme.muted),
    )));

    let block = Block::default()
        .borders(Borders::NONE)
        .style(Style::default().bg(Color::Reset));

    let paragraph = Paragraph::new(lines).block(block);
    frame.render_widget(paragraph, area);
}

fn build_provider_line<'a>(state: &AppState, theme: &'a TuiTheme) -> Line<'a> {
    let label = state.active_builder_label();
    let ollama_ok = state
        .last_pattern_match_mode
        .as_deref()
        == Some("semantic");

    match label {
        Some(ref provider) => {
            let mut spans = vec![
                Span::styled("   Provider  ", Style::default().fg(theme.muted)),
                Span::styled(
                    provider.clone(),
                    Style::default().fg(theme.success).add_modifier(Modifier::BOLD),
                ),
            ];
            if ollama_ok {
                spans.push(Span::styled(
                    "  |  Ollama connected",
                    Style::default().fg(theme.success),
                ));
            }
            Line::from(spans)
        }
        None => Line::from(vec![
            Span::styled("   Provider  ", Style::default().fg(theme.muted)),
            Span::styled(
                "not configured",
                Style::default().fg(theme.warning).add_modifier(Modifier::BOLD),
            ),
            Span::styled(
                "  -- press ? to open settings",
                Style::default().fg(theme.muted),
            ),
        ]),
    }
}
