"""Configuration management for TUI"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import os


@dataclass
class TUIConfig:
    """TUI configuration"""
    # Update intervals
    update_interval_seconds: float = 1.5
    file_watch_debounce_ms: int = 500

    # Data sources
    context_foundry_dir: Path = Path.home() / ".context-foundry"
    metrics_db_path: Optional[Path] = None
    mcp_server_url: str = "http://localhost:3000"

    # UI settings
    theme: str = "dark"
    show_debug_panel: bool = False
    max_log_lines: int = 1000

    # Keyboard shortcuts
    key_quit: str = "q"
    key_help: str = "?"
    key_refresh: str = "r"
    key_dashboard: str = "d"
    key_metrics: str = "m"

    @classmethod
    def from_env(cls) -> 'TUIConfig':
        """Load config from environment variables"""
        config = cls()

        # Override from environment
        if interval := os.getenv('TUI_UPDATE_INTERVAL'):
            config.update_interval_seconds = float(interval)

        if cf_dir := os.getenv('CONTEXT_FOUNDRY_DIR'):
            config.context_foundry_dir = Path(cf_dir)

        if db_path := os.getenv('METRICS_DB_PATH'):
            config.metrics_db_path = Path(db_path)

        if mcp_url := os.getenv('MCP_SERVER_URL'):
            config.mcp_server_url = mcp_url

        if theme := os.getenv('TUI_THEME'):
            config.theme = theme

        if debug := os.getenv('TUI_DEBUG'):
            config.show_debug_panel = debug.lower() in ('1', 'true', 'yes')

        return config

    def get_watch_paths(self) -> list[Path]:
        """Get paths to watch for changes"""
        paths = []

        # Global context foundry dir
        if self.context_foundry_dir.exists():
            paths.append(self.context_foundry_dir)

        # Current project dir
        project_cf = Path.cwd() / ".context-foundry"
        if project_cf.exists():
            paths.append(project_cf)

        return paths
