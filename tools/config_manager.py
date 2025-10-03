#!/usr/bin/env python3
"""
Configuration Manager for Context Foundry
Manages settings, profiles, and environment configuration.
"""

import os
import json
from pathlib import Path
from typing import Dict, Optional, Any
from dataclasses import dataclass, asdict
import yaml


@dataclass
class FoundryConfig:
    """Context Foundry configuration."""
    # API Settings
    api_key: str = ""
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 8000

    # Context Management
    use_context_manager: bool = True
    context_threshold: float = 0.40  # Compact at 40%
    context_target: float = 0.25  # Target 25% after compaction

    # Pattern Library
    use_patterns: bool = True
    max_patterns: int = 3
    min_pattern_relevance: float = 0.6
    min_pattern_success_rate: float = 70.0

    # Workflow Settings
    autonomous_mode: bool = False
    enable_livestream: bool = False
    git_auto_commit: bool = True

    # Paths
    project_dir: str = "examples"
    blueprints_dir: str = "blueprints"
    checkpoints_dir: str = "checkpoints"
    logs_dir: str = "logs"

    # Notification Settings (optional)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_pass: str = ""
    notification_email: str = ""
    slack_webhook: str = ""


class ConfigManager:
    """
    Manages Context Foundry configuration with profiles and validation.

    Supports:
    - Multiple profiles (dev, prod, overnight)
    - Environment variable overrides
    - Validation and defaults
    - Config file management
    """

    DEFAULT_CONFIG_PATH = Path(".foundry/config.yaml")
    ENV_FILE_PATH = Path(".env")

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize configuration manager.

        Args:
            config_path: Path to config file (default: .foundry/config.yaml)
        """
        self.config_path = config_path or self.DEFAULT_CONFIG_PATH
        self.profiles: Dict[str, FoundryConfig] = {}
        self.current_profile: str = "default"

        self._load_config()

    def _load_config(self):
        """Load configuration from file and environment."""
        # Load from file if exists
        if self.config_path.exists():
            with open(self.config_path) as f:
                data = yaml.safe_load(f) or {}

            # Load profiles
            profiles_data = data.get("profiles", {})
            for profile_name, profile_data in profiles_data.items():
                self.profiles[profile_name] = FoundryConfig(**profile_data)

            # Set current profile
            self.current_profile = data.get("current_profile", "default")
        else:
            # Create default profile
            self.profiles["default"] = FoundryConfig()

        # Override with environment variables
        self._apply_env_overrides()

        # Ensure current profile exists
        if self.current_profile not in self.profiles:
            self.profiles[self.current_profile] = FoundryConfig()

    def _apply_env_overrides(self):
        """Apply environment variable overrides."""
        for profile in self.profiles.values():
            # API settings
            if os.getenv("ANTHROPIC_API_KEY"):
                profile.api_key = os.getenv("ANTHROPIC_API_KEY")
            if os.getenv("CLAUDE_MODEL"):
                profile.model = os.getenv("CLAUDE_MODEL")
            if os.getenv("MAX_TOKENS"):
                profile.max_tokens = int(os.getenv("MAX_TOKENS"))

            # Context settings
            if os.getenv("USE_CONTEXT_MANAGER"):
                profile.use_context_manager = os.getenv("USE_CONTEXT_MANAGER").lower() == "true"

            # Pattern settings
            if os.getenv("USE_PATTERNS"):
                profile.use_patterns = os.getenv("USE_PATTERNS").lower() == "true"

            # Notification settings
            if os.getenv("SMTP_HOST"):
                profile.smtp_host = os.getenv("SMTP_HOST")
            if os.getenv("SMTP_PORT"):
                profile.smtp_port = int(os.getenv("SMTP_PORT"))
            if os.getenv("SMTP_USER"):
                profile.smtp_user = os.getenv("SMTP_USER")
            if os.getenv("SMTP_PASS"):
                profile.smtp_pass = os.getenv("SMTP_PASS")
            if os.getenv("NOTIFICATION_EMAIL"):
                profile.notification_email = os.getenv("NOTIFICATION_EMAIL")
            if os.getenv("SLACK_WEBHOOK_URL"):
                profile.slack_webhook = os.getenv("SLACK_WEBHOOK_URL")

    def get(self, key: str, default: Any = None, profile: Optional[str] = None) -> Any:
        """Get configuration value.

        Args:
            key: Configuration key (dot-notation supported)
            default: Default value if not found
            profile: Profile name (uses current if not specified)

        Returns:
            Configuration value
        """
        profile_name = profile or self.current_profile
        config = self.profiles.get(profile_name, FoundryConfig())

        # Handle dot notation (e.g., "context.threshold")
        if "." in key:
            parts = key.split(".")
            value = config
            for part in parts:
                value = getattr(value, part, None)
                if value is None:
                    return default
            return value

        return getattr(config, key, default)

    def set(self, key: str, value: Any, profile: Optional[str] = None):
        """Set configuration value.

        Args:
            key: Configuration key
            value: Value to set
            profile: Profile name (uses current if not specified)
        """
        profile_name = profile or self.current_profile
        if profile_name not in self.profiles:
            self.profiles[profile_name] = FoundryConfig()

        setattr(self.profiles[profile_name], key, value)

    def get_config(self, profile: Optional[str] = None) -> FoundryConfig:
        """Get full configuration for profile.

        Args:
            profile: Profile name (uses current if not specified)

        Returns:
            FoundryConfig object
        """
        profile_name = profile or self.current_profile
        return self.profiles.get(profile_name, FoundryConfig())

    def save(self):
        """Save configuration to file."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "current_profile": self.current_profile,
            "profiles": {
                name: asdict(config)
                for name, config in self.profiles.items()
            }
        }

        with open(self.config_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    def create_profile(self, name: str, from_profile: Optional[str] = None) -> FoundryConfig:
        """Create a new profile.

        Args:
            name: New profile name
            from_profile: Copy settings from this profile (optional)

        Returns:
            New FoundryConfig
        """
        if from_profile and from_profile in self.profiles:
            # Copy from existing profile
            source = self.profiles[from_profile]
            self.profiles[name] = FoundryConfig(**asdict(source))
        else:
            # Create with defaults
            self.profiles[name] = FoundryConfig()

        return self.profiles[name]

    def delete_profile(self, name: str) -> bool:
        """Delete a profile.

        Args:
            name: Profile name to delete

        Returns:
            True if deleted, False if not found or is current
        """
        if name not in self.profiles:
            return False

        if name == self.current_profile:
            return False  # Can't delete current profile

        del self.profiles[name]
        return True

    def switch_profile(self, name: str) -> bool:
        """Switch to a different profile.

        Args:
            name: Profile name to switch to

        Returns:
            True if switched, False if profile not found
        """
        if name not in self.profiles:
            return False

        self.current_profile = name
        return True

    def list_profiles(self) -> Dict[str, Dict]:
        """List all profiles with summary info.

        Returns:
            Dictionary of profile summaries
        """
        summaries = {}
        for name, config in self.profiles.items():
            summaries[name] = {
                "model": config.model,
                "autonomous": config.autonomous_mode,
                "context_manager": config.use_context_manager,
                "patterns": config.use_patterns,
                "is_current": name == self.current_profile
            }
        return summaries

    def validate(self, profile: Optional[str] = None) -> Dict[str, list]:
        """Validate configuration.

        Args:
            profile: Profile to validate (uses current if not specified)

        Returns:
            Dictionary with 'errors' and 'warnings' lists
        """
        profile_name = profile or self.current_profile
        config = self.profiles.get(profile_name, FoundryConfig())

        errors = []
        warnings = []

        # Check API key
        if not config.api_key:
            errors.append("ANTHROPIC_API_KEY not set")

        # Validate thresholds
        if config.context_threshold < 0 or config.context_threshold > 1:
            errors.append(f"Invalid context_threshold: {config.context_threshold} (must be 0-1)")

        if config.context_target < 0 or config.context_target > 1:
            errors.append(f"Invalid context_target: {config.context_target} (must be 0-1)")

        if config.context_target >= config.context_threshold:
            warnings.append("context_target should be less than context_threshold")

        # Validate pattern settings
        if config.min_pattern_relevance < 0 or config.min_pattern_relevance > 1:
            errors.append(f"Invalid min_pattern_relevance: {config.min_pattern_relevance} (must be 0-1)")

        if config.min_pattern_success_rate < 0 or config.min_pattern_success_rate > 100:
            errors.append(f"Invalid min_pattern_success_rate: {config.min_pattern_success_rate} (must be 0-100)")

        # Check notification settings
        if config.notification_email and not config.smtp_host:
            warnings.append("notification_email set but smtp_host not configured")

        return {"errors": errors, "warnings": warnings}

    def init_env_file(self, force: bool = False) -> bool:
        """Initialize .env file from template.

        Args:
            force: Overwrite existing file

        Returns:
            True if created/updated
        """
        if self.ENV_FILE_PATH.exists() and not force:
            return False

        # Check for .env.example
        example_file = Path(".env.example")
        if example_file.exists():
            self.ENV_FILE_PATH.write_text(example_file.read_text())
        else:
            # Create minimal .env
            template = """# Context Foundry Environment Variables

# Required for API and Autonomous modes
ANTHROPIC_API_KEY=your_api_key_here

# Optional: Override default model
# CLAUDE_MODEL=claude-sonnet-4-20250514

# Optional: Maximum tokens per response
# MAX_TOKENS=8000

# Optional: Context management settings
# USE_CONTEXT_MANAGER=true

# Optional: Pattern library settings
# USE_PATTERNS=true

# Optional: Notification settings (for overnight sessions)
# SMTP_HOST=smtp.gmail.com
# SMTP_PORT=587
# SMTP_USER=your_email@gmail.com
# SMTP_PASS=your_app_password
# NOTIFICATION_EMAIL=you@example.com
# SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
"""
            self.ENV_FILE_PATH.write_text(template)

        return True

    def get_preset(self, preset_name: str) -> Optional[FoundryConfig]:
        """Get a preset configuration.

        Args:
            preset_name: Name of preset ('dev', 'prod', 'overnight')

        Returns:
            FoundryConfig with preset values, or None if preset not found
        """
        presets = {
            "dev": FoundryConfig(
                autonomous_mode=False,
                enable_livestream=True,
                use_context_manager=True,
                use_patterns=True,
                git_auto_commit=True,
            ),
            "prod": FoundryConfig(
                autonomous_mode=False,
                enable_livestream=False,
                use_context_manager=True,
                use_patterns=True,
                git_auto_commit=True,
            ),
            "overnight": FoundryConfig(
                autonomous_mode=True,
                enable_livestream=False,
                use_context_manager=True,
                use_patterns=True,
                git_auto_commit=True,
                context_threshold=0.35,  # More aggressive for overnight
            ),
        }

        return presets.get(preset_name)

    def apply_preset(self, preset_name: str, profile: Optional[str] = None) -> bool:
        """Apply a preset to a profile.

        Args:
            preset_name: Name of preset
            profile: Profile to apply to (uses current if not specified)

        Returns:
            True if applied, False if preset not found
        """
        preset = self.get_preset(preset_name)
        if not preset:
            return False

        profile_name = profile or self.current_profile
        self.profiles[profile_name] = preset
        return True


def test_config_manager():
    """Test configuration manager."""
    print("🧪 Testing Configuration Manager")
    print("=" * 60)

    # Create manager
    config_path = Path(".foundry/test_config.yaml")
    manager = ConfigManager(config_path)

    # Test getting values
    print("\n1. Testing get/set...")
    manager.set("model", "claude-sonnet-4-20250514")
    model = manager.get("model")
    print(f"   Model: {model}")

    # Test profiles
    print("\n2. Testing profiles...")
    manager.create_profile("overnight", from_profile="default")
    manager.switch_profile("overnight")
    manager.set("autonomous_mode", True)
    profiles = manager.list_profiles()
    print(f"   Profiles: {list(profiles.keys())}")

    # Test validation
    print("\n3. Testing validation...")
    validation = manager.validate()
    print(f"   Errors: {len(validation['errors'])}")
    print(f"   Warnings: {len(validation['warnings'])}")

    # Test presets
    print("\n4. Testing presets...")
    manager.apply_preset("dev", "default")
    config = manager.get_config("default")
    print(f"   Dev preset - livestream: {config.enable_livestream}")

    # Save
    print("\n5. Testing save...")
    manager.save()
    print(f"   Saved to: {config_path}")

    # Cleanup
    config_path.unlink()

    print("\n✅ Configuration Manager test complete!")


if __name__ == "__main__":
    test_config_manager()
