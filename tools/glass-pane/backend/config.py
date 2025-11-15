"""
Configuration management for Glass Pane backend.
Uses pydantic-settings for environment variable management.
"""

from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database Configuration
    db_path: str = "~/.context-foundry/cfd/jobs.db"

    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = False

    # CORS Configuration
    cors_origins: List[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "https://glass.contextfoundry.dev",
    ]

    # File Watcher Configuration
    watch_path: str = ".context-foundry"
    debounce_seconds: float = 0.5

    # SSE Configuration
    heartbeat_interval: int = 30  # seconds
    log_batch_size: int = 50
    log_batch_interval: float = 0.5  # seconds

    # Logging
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    @property
    def expanded_db_path(self) -> Path:
        """Expand ~ in db_path to absolute path."""
        return Path(self.db_path).expanduser().resolve()

    @property
    def expanded_watch_path(self) -> Path:
        """Expand watch_path to absolute path."""
        path = Path(self.watch_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        return path.resolve()


# Global settings instance
settings = Settings()
