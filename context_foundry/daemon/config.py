"""
Configuration management for Context Foundry Daemon

Loads config from:
1. Default values
2. Config file (~/.context-foundry/cfd/config.json)
3. Environment variables (CFD_*)
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Config:
    """CF Daemon configuration"""

    # Daemon settings
    poll_interval_seconds: int = 60
    max_concurrent_jobs: int = 3
    log_level: str = "INFO"
    enable_github_integration: bool = True
    enable_resource_monitoring: bool = True

    # Resource limits
    max_cpu_percent: float = 80.0
    max_memory_gb: float = 16.0
    active_hours: tuple = (6, 22)  # (start_hour, end_hour)

    # Job settings
    default_job_timeout_minutes: int = 90
    default_max_retries: int = 0

    # Paths
    data_dir: Path = field(
        default_factory=lambda: Path.home() / ".context-foundry" / "cfd"
    )
    log_dir: Path = field(
        default_factory=lambda: Path.home() / ".context-foundry" / "cfd" / "logs"
    )
    db_path: Path = field(
        default_factory=lambda: Path.home() / ".context-foundry" / "cfd" / "jobs.db"
    )
    pid_file: Path = field(
        default_factory=lambda: Path.home() / ".context-foundry" / "cfd" / "daemon.pid"
    )

    # GitHub (optional)
    github_token: Optional[str] = None
    github_repo: Optional[str] = None

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "Config":
        """
        Load configuration from file and environment

        Priority: env vars > config file > defaults
        """
        # Start with defaults
        config_data = {}

        # Load from config file if exists
        if config_path is None:
            config_path = Path.home() / ".context-foundry" / "cfd" / "config.json"

        if config_path.exists():
            with open(config_path) as f:
                config_data = json.load(f)

        # Override with environment variables
        env_overrides = {
            "CFD_POLL_INTERVAL": "poll_interval_seconds",
            "CFD_MAX_CONCURRENT": "max_concurrent_jobs",
            "CFD_LOG_LEVEL": "log_level",
            "CFD_MAX_CPU": "max_cpu_percent",
            "CFD_MAX_MEMORY_GB": "max_memory_gb",
            "GITHUB_TOKEN": "github_token",
        }

        for env_var, config_key in env_overrides.items():
            if env_var in os.environ:
                value = os.environ[env_var]
                # Type conversion
                if config_key.endswith(("_seconds", "_jobs", "_minutes", "_retries")):
                    value = int(value)
                elif config_key.endswith(("_percent", "_gb")):
                    value = float(value)
                config_data[config_key] = value

        # Convert path strings to Path objects
        for key in ["data_dir", "log_dir", "db_path", "pid_file"]:
            if key in config_data and isinstance(config_data[key], str):
                config_data[key] = Path(config_data[key])

        return cls(**config_data)

    def save(self, config_path: Optional[Path] = None):
        """Save configuration to file"""
        if config_path is None:
            config_path = Path.home() / ".context-foundry" / "cfd" / "config.json"

        config_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to dict, handling Path objects
        data = {}
        for key, value in self.__dict__.items():
            if isinstance(value, Path):
                data[key] = str(value)
            elif isinstance(value, tuple):
                data[key] = list(value)
            else:
                data[key] = value

        with open(config_path, "w") as f:
            json.dump(data, f, indent=2)

    def ensure_directories(self):
        """Ensure all required directories exist"""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
