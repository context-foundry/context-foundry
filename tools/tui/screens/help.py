"""Help screen with keyboard shortcuts"""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.containers import VerticalScroll
from textual.widgets import Header, Footer, Markdown
from textual.binding import Binding


HELP_TEXT = """
# Context Foundry TUI Monitor - Help

## Keyboard Shortcuts

### Global
- `q` / `Esc` - Quit application
- `?` - Show this help screen
- `r` - Refresh data manually

### Navigation
- `d` - Go to Dashboard
- `m` - Show Metrics screen
- `h` - Show Help screen
- `n` - New Project (launch autonomous build)

### Dashboard
- `↑/↓` - Navigate build list (when implemented)
- `Enter` - View build details (when implemented)

## Data Sources

The TUI monitors the following data sources:

1. **Current Phase JSON**: `.context-foundry/current-phase.json`
   - Real-time build status updates
   - Phase progress tracking
   - Test iteration counts

2. **Metrics Database**: `metrics.db` (if available)
   - Build metrics and statistics
   - Historical data

3. **MCP Server**: Model Context Protocol server (if running)
   - Agent metrics
   - Token usage

## Refresh Rate

- Data refreshes automatically every **1.5 seconds**
- File changes are detected immediately via file watcher
- Manual refresh available with `r` key

## Features

- Real-time build monitoring
- Phase progress visualization
- Token usage tracking
- Build history table
- **Launch new projects** directly from TUI (press `n`)
- Responsive terminal UI

## About

Context Foundry TUI Monitor v1.0.0

Built with [Textual](https://textual.textualize.io/) - Modern TUI framework for Python

🤖 Part of the Context Foundry autonomous build system
"""


class HelpScreen(Screen):
    """Help and keyboard shortcuts"""

    BINDINGS = [
        Binding("escape", "pop_screen", "Back"),
        Binding("q", "quit", "Quit"),
    ]

    def compose(self) -> ComposeResult:
        """Compose the help screen"""
        yield Header()
        with VerticalScroll():
            yield Markdown(HELP_TEXT)
        yield Footer()

    def action_quit(self):
        """Quit application"""
        self.app.exit()

    def action_pop_screen(self):
        """Go back to previous screen"""
        self.app.pop_screen()
