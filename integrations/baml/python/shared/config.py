"""
Configuration management for BAML + Anthropic integration.

Loads environment variables and provides typed configuration access.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field, validator


class Config(BaseModel):
    """
    Configuration for BAML + Anthropic integration.

    Attributes:
        anthropic_api_key: Anthropic API key (optional - only needed for direct API calls, not MCP delegation)
        baml_log_level: BAML logging level
        run_integration_tests: Whether to run integration tests
        log_level: Application log level
    """

    anthropic_api_key: str | None = Field(default=None)
    baml_log_level: str = Field(default="INFO")
    run_integration_tests: bool = Field(default=False)
    log_level: str = Field(default="INFO")

    @validator("anthropic_api_key")
    @classmethod
    def validate_api_key(cls, v: str | None) -> str | None:
        """
        Validate API key if provided.

        For MCP-only mode (Context Foundry delegation), API key is not needed.
        Only validates if a key is provided to catch template placeholders.
        """
        if v is None or v == "":
            # MCP-only mode - no API key needed
            return None

        if v == "your_api_key_here" or len(v) < 10:
            raise ValueError(
                "Invalid API key format. Either leave empty for MCP-only mode, "
                "or provide a valid ANTHROPIC_API_KEY for direct API calls."
            )
        return v

    @validator("baml_log_level", "log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is valid."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return v_upper


def load_config(env_file: Path | None = None) -> Config:
    """
    Load configuration from environment variables.

    Args:
        env_file: Optional path to .env file. If not provided, searches for .env
                  in current directory and parent directories.

    Returns:
        Config object with validated configuration

    Raises:
        ValueError: If required configuration is missing or invalid
    """
    # Determine .env file location
    if env_file is None:
        # Search for .env in current directory and parent directories
        current_dir = Path(__file__).parent.parent
        env_file = current_dir / ".env"

        if not env_file.exists():
            # Try parent directory (integrations/baml/)
            env_file = current_dir.parent / ".env"

    # Load environment variables
    if env_file and env_file.exists():
        load_dotenv(env_file)

    # Extract configuration from environment
    config_dict = {
        "anthropic_api_key": os.getenv("ANTHROPIC_API_KEY", ""),
        "baml_log_level": os.getenv("BAML_LOG_LEVEL", "INFO"),
        "run_integration_tests": os.getenv("RUN_INTEGRATION_TESTS", "false").lower()
        == "true",
        "log_level": os.getenv("LOG_LEVEL", "INFO"),
    }

    # Validate and return
    return Config(**config_dict)


def get_config() -> Config:
    """
    Get configuration (convenience function).

    Returns:
        Config object with validated configuration
    """
    return load_config()
