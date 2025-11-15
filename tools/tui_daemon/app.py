"""
CF Daemon TUI - Main Application

Entry point for the Textual TUI application.
"""

import sys
from textual.app import App

from .manager import TUIManager
from .screens.dashboard import DashboardScreen


class CFDaemonTUI(App):
    """
    Context Foundry Daemon Terminal User Interface.

    A modern TUI for managing CF Daemon builds with:
    - Conversational build launcher
    - Real-time job monitoring
    - Phase pipeline visualization
    - Live log streaming
    """

    CSS_PATH = "styles/dark.tcss"
    TITLE = "CF Daemon TUI"
    SUB_TITLE = "Context Foundry Build Manager"

    def __init__(self, db_path: str = None, **kwargs):
        """
        Initialize the TUI application.

        Args:
            db_path: Path to jobs.db (optional)
        """
        super().__init__(**kwargs)
        self.manager = TUIManager(db_path)

    def on_mount(self) -> None:
        """Handle app mount"""
        # Connect to daemon
        if not self.manager.initialize():
            self.exit(message="❌ Failed to connect to CF Daemon. Is it running?")
            return

        # Push dashboard screen
        self.push_screen(DashboardScreen(self.manager))


def main():
    """Entry point for the TUI application"""
    # Parse arguments (simple arg parsing)
    db_path = None
    if len(sys.argv) > 1:
        db_path = sys.argv[1]

    # Run the app
    app = CFDaemonTUI(db_path=db_path)
    app.run()


if __name__ == "__main__":
    main()
