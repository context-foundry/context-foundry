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
/// Checks COLORTERM, WT_SESSION, TERM_PROGRAM, KONSOLE_VERSION, and TERM.
/// Result is cached on first call via `std::sync::OnceLock`.
fn supports_truecolor() -> bool {
    static TRUECOLOR: std::sync::OnceLock<bool> = std::sync::OnceLock::new();
    *TRUECOLOR.get_or_init(detect_truecolor)
}

/// Override truecolor detection from config. Call once at startup if
/// the user has set `truecolor` in `.foundry.json`.
pub fn set_truecolor_override(value: bool) {
    TRUECOLOR_OVERRIDE.store(
        if value { 1 } else { 2 },
        std::sync::atomic::Ordering::Relaxed,
    );
}

static TRUECOLOR_OVERRIDE: std::sync::atomic::AtomicU8 = std::sync::atomic::AtomicU8::new(0);

fn detect_truecolor() -> bool {
    // Check config override first (0 = unset, 1 = true, 2 = false)
    match TRUECOLOR_OVERRIDE.load(std::sync::atomic::Ordering::Relaxed) {
        1 => return true,
        2 => return false,
        _ => {}
    }

    // COLORTERM is the standard signal
    if let Ok(ct) = std::env::var("COLORTERM") {
        let ct_lower = ct.to_ascii_lowercase();
        if ct_lower == "truecolor" || ct_lower == "24bit" {
            return true;
        }
    }

    // Windows Terminal always supports truecolor
    if std::env::var("WT_SESSION").is_ok() {
        return true;
    }

    // Known truecolor-capable terminal programs
    if let Ok(tp) = std::env::var("TERM_PROGRAM") {
        let tp_lower = tp.to_ascii_lowercase();
        if matches!(
            tp_lower.as_str(),
            "iterm.app" | "hyper" | "wezterm" | "alacritty" | "vscode"
        ) {
            return true;
        }
    }

    // KDE Konsole supports truecolor
    if std::env::var("KONSOLE_VERSION").is_ok() {
        return true;
    }

    // ConEmu / Cmder on Windows
    if std::env::var("ConEmuPID").is_ok() {
        return true;
    }

    // tmux often strips COLORTERM but passes through Tc capability.
    // If TERM contains "256color" inside tmux, it very likely supports truecolor.
    if std::env::var("TMUX").is_ok() {
        if let Ok(term) = std::env::var("TERM") {
            if term.contains("256color") {
                return true;
            }
        }
    }

    false
}

/// Downgrade an RGB color to the nearest ANSI-256 index.
/// ANSI-256 cube levels: 0, 95, 135, 175, 215, 255.
/// Breakpoints are midpoints: 48, 115, 155, 195, 235.
fn rgb_to_ansi256(r: u8, g: u8, b: u8) -> Color {
    fn channel_to_cube(v: u8) -> u8 {
        if v < 48 {
            0
        } else if v < 115 {
            1
        } else {
            ((v as u16 - 35) / 40).min(5) as u8
        }
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
        (
            "roundup",
            TuiTheme {
                accent: Color::Rgb(212, 130, 26),  // Western amber
                border: Color::Rgb(74, 50, 32),    // Leather brown
                text: Color::Rgb(232, 220, 200),   // Parchment
                muted: Color::Rgb(168, 148, 120),  // Dusty trail
                success: Color::Rgb(90, 158, 69),  // Prairie green
                warning: Color::Rgb(232, 184, 75), // Gold nugget
                error: Color::Rgb(192, 57, 43),    // Saloon red
                info: Color::Rgb(212, 130, 26),    // Amber
                surface: Color::Rgb(42, 26, 14),   // Dark saddle
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
    let adapted: Vec<_> = themes
        .iter()
        .map(|(n, t)| (*n, adapt_theme(t.clone())))
        .collect();
    let current_idx = adapted.iter().position(|(_, t)| t == current).unwrap_or(0);
    let next_idx = (current_idx + 1) % themes.len();
    (adapt_theme(themes[next_idx].1.clone()), themes[next_idx].0)
}

/// Return the name of the currently active theme.
pub fn current_name(current: &TuiTheme) -> &'static str {
    let themes = builtin_themes();
    let adapted: Vec<_> = themes
        .iter()
        .map(|(n, t)| (*n, adapt_theme(t.clone())))
        .collect();
    adapted
        .iter()
        .find(|(_, t)| t == current)
        .map(|(n, _)| *n)
        .unwrap_or("dark")
}

impl Default for TuiTheme {
    fn default() -> Self {
        from_name("dark")
    }
}
