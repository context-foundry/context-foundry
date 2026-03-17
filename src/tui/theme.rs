use ratatui::style::Color;

#[derive(Debug, Clone, PartialEq)]
pub struct TuiTheme {
    pub accent: Color,
    pub border: Color,
    pub text: Color,
    pub muted: Color,
    pub success: Color,
    pub warning: Color,
    pub error: Color,
    pub info: Color,
    pub surface: Color,
}

fn normalize_theme_name(name: &str) -> String {
    name.trim()
        .to_ascii_lowercase()
        .chars()
        .map(|c| if c.is_alphanumeric() { c } else { '-' })
        .collect()
}

pub fn builtin_themes() -> Vec<(&'static str, TuiTheme)> {
    vec![
        (
            "dark",
            TuiTheme {
                accent: Color::Rgb(227, 115, 75),
                border: Color::DarkGray,
                text: Color::White,
                muted: Color::DarkGray,
                success: Color::Green,
                warning: Color::Yellow,
                error: Color::Red,
                info: Color::Cyan,
                surface: Color::Rgb(60, 60, 80),
            },
        ),
        (
            "catppuccin",
            TuiTheme {
                accent: Color::Rgb(203, 166, 247),
                border: Color::Rgb(88, 91, 112),
                text: Color::Rgb(205, 214, 244),
                muted: Color::Rgb(108, 112, 134),
                success: Color::Rgb(166, 227, 161),
                warning: Color::Rgb(249, 226, 175),
                error: Color::Rgb(243, 139, 168),
                info: Color::Rgb(137, 220, 235),
                surface: Color::Rgb(49, 50, 68),
            },
        ),
        (
            "solarized",
            TuiTheme {
                accent: Color::Rgb(38, 139, 210),
                border: Color::Rgb(88, 110, 117),
                text: Color::Rgb(131, 148, 150),
                muted: Color::Rgb(88, 110, 117),
                success: Color::Rgb(133, 153, 0),
                warning: Color::Rgb(181, 137, 0),
                error: Color::Rgb(220, 50, 47),
                info: Color::Rgb(42, 161, 152),
                surface: Color::Rgb(0, 43, 54),
            },
        ),
    ]
}

pub fn from_name(name: &str) -> TuiTheme {
    let normalized = normalize_theme_name(name);
    let themes = builtin_themes();
    themes
        .iter()
        .find(|(n, _)| normalize_theme_name(n) == normalized)
        .map(|(_, t)| t.clone())
        .unwrap_or_else(|| themes[0].1.clone())
}

/// Cycle to the next built-in theme. Returns (new theme, theme name).
pub fn cycle_next(current: &TuiTheme) -> (TuiTheme, &'static str) {
    let themes = builtin_themes();
    let current_idx = themes
        .iter()
        .position(|(_, t)| t == current)
        .unwrap_or(0);
    let next_idx = (current_idx + 1) % themes.len();
    (themes[next_idx].1.clone(), themes[next_idx].0)
}

impl Default for TuiTheme {
    fn default() -> Self {
        from_name("dark")
    }
}
