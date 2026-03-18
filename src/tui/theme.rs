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

/// Detect whether the terminal supports truecolor (24-bit RGB).
/// Checks COLORTERM env var and WT_SESSION (Windows Terminal).
fn supports_truecolor() -> bool {
    if let Ok(ct) = std::env::var("COLORTERM") {
        if ct == "truecolor" || ct == "24bit" {
            return true;
        }
    }
    // Windows Terminal always supports truecolor
    if std::env::var("WT_SESSION").is_ok() {
        return true;
    }
    false
}

/// Downgrade an RGB color to the nearest ANSI-256 index.
/// ANSI-256 cube levels: 0, 95, 135, 175, 215, 255.
/// Breakpoints are midpoints: 48, 115, 155, 195, 235.
fn rgb_to_ansi256(r: u8, g: u8, b: u8) -> Color {
    fn channel_to_cube(v: u8) -> u8 {
        if v < 48 { 0 }
        else if v < 115 { 1 }
        else { ((v as u16 - 35) / 40).min(5) as u8 }
    }
    let idx = 16 + 36 * channel_to_cube(r) + 6 * channel_to_cube(g) + channel_to_cube(b);
    Color::Indexed(idx)
}

/// If the terminal doesn't support truecolor, downgrade RGB colors to ANSI-256.
fn adapt_color(color: Color) -> Color {
    match color {
        Color::Rgb(r, g, b) if !supports_truecolor() => rgb_to_ansi256(r, g, b),
        other => other,
    }
}

fn adapt_theme(theme: TuiTheme) -> TuiTheme {
    TuiTheme {
        accent: adapt_color(theme.accent),
        border: adapt_color(theme.border),
        text: adapt_color(theme.text),
        muted: adapt_color(theme.muted),
        success: adapt_color(theme.success),
        warning: adapt_color(theme.warning),
        error: adapt_color(theme.error),
        info: adapt_color(theme.info),
        surface: adapt_color(theme.surface),
    }
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
    let theme = themes
        .iter()
        .find(|(n, _)| normalize_theme_name(n) == normalized)
        .map(|(_, t)| t.clone())
        .unwrap_or_else(|| themes[0].1.clone());
    adapt_theme(theme)
}

/// Cycle to the next built-in theme. Returns (new theme, theme name).
pub fn cycle_next(current: &TuiTheme) -> (TuiTheme, &'static str) {
    let themes = builtin_themes();
    // Compare against adapted themes so cycling works regardless of color mode
    let adapted: Vec<_> = themes.iter().map(|(n, t)| (*n, adapt_theme(t.clone()))).collect();
    let current_idx = adapted
        .iter()
        .position(|(_, t)| t == current)
        .unwrap_or(0);
    let next_idx = (current_idx + 1) % themes.len();
    (adapt_theme(themes[next_idx].1.clone()), themes[next_idx].0)
}

impl Default for TuiTheme {
    fn default() -> Self {
        from_name("dark")
    }
}
