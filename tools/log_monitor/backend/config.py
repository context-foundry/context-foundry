"""
Configuration management for MCP Log Monitor
"""

import os
import yaml
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ServerConfig:
    """Server configuration"""

    host: str = "0.0.0.0"
    port: int = 5000


@dataclass
class LogSourceConfig:
    """Log source configuration"""

    name: str
    paths: List[str]
    enabled: bool = True


@dataclass
class PerformanceConfig:
    """Performance tuning configuration"""

    max_buffer_size: int = 100
    broadcast_batch_size: int = 50
    file_read_chunk_size: int = 4096
    debounce_ms: int = 100


@dataclass
class RetentionConfig:
    """Log retention configuration"""

    max_log_entries: int = 10000
    history_days: int = 7


@dataclass
class Config:
    """Global configuration"""

    server: ServerConfig = field(default_factory=ServerConfig)
    log_sources: List[LogSourceConfig] = field(default_factory=list)
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)
    retention: RetentionConfig = field(default_factory=RetentionConfig)

    @classmethod
    def load(cls, config_file: Optional[Path] = None) -> "Config":
        """
        Load configuration from YAML file and environment variables.

        Environment variables take precedence over config file.

        Args:
            config_file: Path to config.yaml (optional)

        Returns:
            Config instance
        """
        # Start with defaults
        config_data = {}

        # Load from YAML if provided
        if config_file and config_file.exists():
            with open(config_file, "r") as f:
                config_data = yaml.safe_load(f) or {}

        # Override with environment variables
        server_config = ServerConfig(
            host=os.getenv(
                "LOG_MONITOR_HOST", config_data.get("server", {}).get("host", "0.0.0.0")
            ),
            port=int(
                os.getenv(
                    "LOG_MONITOR_PORT", config_data.get("server", {}).get("port", 5000)
                )
            ),
        )

        # Load log sources
        log_sources = []
        for source in config_data.get("log_sources", []):
            log_sources.append(
                LogSourceConfig(
                    name=source["name"],
                    paths=source["paths"],
                    enabled=source.get("enabled", True),
                )
            )

        # Add default sources if none configured
        if not log_sources:
            log_sources = cls._get_default_log_sources()

        # Load performance config
        perf_data = config_data.get("performance", {})
        performance = PerformanceConfig(
            max_buffer_size=perf_data.get("max_buffer_size", 100),
            broadcast_batch_size=perf_data.get("broadcast_batch_size", 50),
            file_read_chunk_size=perf_data.get("file_read_chunk_size", 4096),
            debounce_ms=perf_data.get("debounce_ms", 100),
        )

        # Load retention config
        ret_data = config_data.get("retention", {})
        retention = RetentionConfig(
            max_log_entries=ret_data.get("max_log_entries", 10000),
            history_days=ret_data.get("history_days", 7),
        )

        return cls(
            server=server_config,
            log_sources=log_sources,
            performance=performance,
            retention=retention,
        )

    @staticmethod
    def _get_default_log_sources() -> List[LogSourceConfig]:
        """Get default log sources"""
        home = Path.home()

        return [
            LogSourceConfig(
                name="context-foundry",
                paths=[
                    str(home / ".context-foundry" / "*" / "build-output-*.txt"),
                    str(home / ".context-foundry" / "delegations" / "*.json"),
                ],
                enabled=True,
            ),
            LogSourceConfig(
                name="claude-desktop",
                paths=[str(home / "Library" / "Logs" / "Claude" / "mcp*.log")],
                enabled=True,
            ),
        ]

    def get_enabled_sources(self) -> List[LogSourceConfig]:
        """Get list of enabled log sources"""
        return [source for source in self.log_sources if source.enabled]
