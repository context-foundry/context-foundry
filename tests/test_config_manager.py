#!/usr/bin/env python3
"""
Comprehensive tests for ConfigManager
Tests all critical paths including initialization, profiles, validation, and persistence.
"""

import pytest
import tempfile
from pathlib import Path
from tools.config_manager import ConfigManager, FoundryConfig


@pytest.fixture
def temp_config_file():
    """Create a temporary config file for testing."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        config_path = Path(f.name)
    yield config_path
    # Cleanup
    if config_path.exists():
        config_path.unlink()


@pytest.fixture
def config_manager(temp_config_file):
    """Create a ConfigManager instance for testing."""
    return ConfigManager(temp_config_file)


class TestFoundryConfigDefaults:
    """Test FoundryConfig dataclass defaults."""

    def test_default_values(self):
        """Test default configuration values are set correctly."""
        config = FoundryConfig()
        assert config.model == "claude-sonnet-4-20250514"
        assert config.max_tokens == 8000
        assert config.use_context_manager is True
        assert config.context_threshold == 0.40
        assert config.context_target == 0.25
        assert config.use_patterns is True
        assert config.max_patterns == 3
        assert config.autonomous_mode is False
        assert config.git_auto_commit is True

    def test_custom_values(self):
        """Test creating config with custom values."""
        config = FoundryConfig(
            model="claude-opus-4", max_tokens=16000, autonomous_mode=True
        )
        assert config.model == "claude-opus-4"
        assert config.max_tokens == 16000
        assert config.autonomous_mode is True


class TestConfigManagerInitialization:
    """Test ConfigManager initialization."""

    def test_init_creates_default_profile(self, temp_config_file):
        """Test that initialization creates a default profile."""
        manager = ConfigManager(temp_config_file)
        assert "default" in manager.profiles
        assert manager.current_profile == "default"
        assert isinstance(manager.profiles["default"], FoundryConfig)

    def test_init_with_nonexistent_file(self, temp_config_file):
        """Test initialization when config file doesn't exist."""
        manager = ConfigManager(temp_config_file)
        assert manager.config_path == temp_config_file
        assert len(manager.profiles) == 1
        assert "default" in manager.profiles

    def test_init_loads_existing_config(self, temp_config_file):
        """Test loading existing configuration file."""
        # Create a config file first
        manager1 = ConfigManager(temp_config_file)
        manager1.create_profile("test_profile")
        manager1.set("model", "claude-opus-4", profile="test_profile")
        manager1.save()

        # Load it with a new manager
        manager2 = ConfigManager(temp_config_file)
        assert "test_profile" in manager2.profiles
        assert manager2.get("model", profile="test_profile") == "claude-opus-4"


class TestConfigManagerGetSet:
    """Test getting and setting configuration values."""

    def test_get_simple_value(self, config_manager):
        """Test getting a simple configuration value."""
        value = config_manager.get("model")
        assert value == "claude-sonnet-4-20250514"

    def test_get_with_default(self, config_manager):
        """Test getting value with default fallback."""
        value = config_manager.get("nonexistent_key", default="fallback")
        assert value == "fallback"

    def test_set_value(self, config_manager):
        """Test setting a configuration value."""
        config_manager.set("model", "claude-opus-4")
        assert config_manager.get("model") == "claude-opus-4"

    def test_get_from_specific_profile(self, config_manager):
        """Test getting value from a specific profile."""
        config_manager.create_profile("custom")
        config_manager.set("model", "custom-model", profile="custom")
        assert config_manager.get("model", profile="custom") == "custom-model"
        assert (
            config_manager.get("model") != "custom-model"
        )  # Default profile unchanged


class TestConfigManagerProfiles:
    """Test profile management."""

    def test_create_profile(self, config_manager):
        """Test creating a new profile."""
        config = config_manager.create_profile("test")
        assert "test" in config_manager.profiles
        assert isinstance(config, FoundryConfig)

    def test_create_profile_from_existing(self, config_manager):
        """Test creating profile copied from existing profile."""
        config_manager.set("model", "custom-model")
        config_manager.create_profile("copy", from_profile="default")
        assert config_manager.get("model", profile="copy") == "custom-model"

    def test_delete_profile(self, config_manager):
        """Test deleting a profile."""
        config_manager.create_profile("to_delete")
        assert config_manager.delete_profile("to_delete") is True
        assert "to_delete" not in config_manager.profiles

    def test_cannot_delete_current_profile(self, config_manager):
        """Test that current profile cannot be deleted."""
        assert config_manager.delete_profile("default") is False
        assert "default" in config_manager.profiles

    def test_delete_nonexistent_profile(self, config_manager):
        """Test deleting a profile that doesn't exist."""
        assert config_manager.delete_profile("nonexistent") is False

    def test_switch_profile(self, config_manager):
        """Test switching between profiles."""
        config_manager.create_profile("other")
        assert config_manager.switch_profile("other") is True
        assert config_manager.current_profile == "other"

    def test_switch_to_nonexistent_profile(self, config_manager):
        """Test switching to a profile that doesn't exist."""
        assert config_manager.switch_profile("nonexistent") is False
        assert config_manager.current_profile == "default"

    def test_list_profiles(self, config_manager):
        """Test listing all profiles."""
        config_manager.create_profile("profile1")
        config_manager.create_profile("profile2")

        profiles = config_manager.list_profiles()
        assert len(profiles) >= 3  # default + 2 created
        assert "default" in profiles
        assert "profile1" in profiles
        assert "profile2" in profiles
        assert profiles["default"]["is_current"] is True


class TestConfigManagerValidation:
    """Test configuration validation."""

    def test_validation_missing_api_key(self, config_manager):
        """Test validation detects missing API key."""
        validation = config_manager.validate()
        assert "ANTHROPIC_API_KEY not set" in validation["errors"]

    def test_validation_with_api_key(self, config_manager):
        """Test validation passes with API key."""
        config_manager.set("api_key", "sk-test-key")
        validation = config_manager.validate()
        assert "ANTHROPIC_API_KEY not set" not in validation["errors"]

    def test_validation_invalid_threshold(self, config_manager):
        """Test validation detects invalid threshold values."""
        config_manager.set("context_threshold", 1.5)
        validation = config_manager.validate()
        assert any("context_threshold" in err for err in validation["errors"])

    def test_validation_threshold_relationship(self, config_manager):
        """Test validation warns about threshold relationship."""
        config_manager.set("context_threshold", 0.3)
        config_manager.set("context_target", 0.4)
        validation = config_manager.validate()
        assert any(
            "context_target should be less" in warn for warn in validation["warnings"]
        )

    def test_validation_invalid_pattern_relevance(self, config_manager):
        """Test validation detects invalid pattern relevance."""
        config_manager.set("min_pattern_relevance", 1.5)
        validation = config_manager.validate()
        assert any("min_pattern_relevance" in err for err in validation["errors"])

    def test_validation_notification_incomplete(self, config_manager):
        """Test validation warns about incomplete notification config."""
        config_manager.set("notification_email", "test@example.com")
        config_manager.set("smtp_host", "")
        validation = config_manager.validate()
        assert any(
            "smtp_host not configured" in warn for warn in validation["warnings"]
        )


class TestConfigManagerPersistence:
    """Test saving and loading configuration."""

    def test_save_and_load(self, temp_config_file):
        """Test saving configuration and loading it back."""
        # Create and configure manager
        manager1 = ConfigManager(temp_config_file)
        manager1.create_profile("saved_profile")
        manager1.set("model", "test-model", profile="saved_profile")
        manager1.switch_profile("saved_profile")
        manager1.save()

        # Load with new manager
        manager2 = ConfigManager(temp_config_file)
        assert "saved_profile" in manager2.profiles
        assert manager2.current_profile == "saved_profile"
        assert manager2.get("model") == "test-model"

    def test_save_creates_directory(self, temp_config_file):
        """Test that save creates parent directories if needed."""
        nested_path = temp_config_file.parent / "nested" / "config.yaml"
        manager = ConfigManager(nested_path)
        manager.save()
        assert nested_path.exists()
        # Cleanup
        nested_path.unlink()
        nested_path.parent.rmdir()

    def test_save_preserves_all_profiles(self, config_manager):
        """Test that saving preserves all profiles."""
        config_manager.create_profile("profile1")
        config_manager.create_profile("profile2")
        config_manager.set("model", "model1", profile="profile1")
        config_manager.set("model", "model2", profile="profile2")
        config_manager.save()

        # Reload
        manager2 = ConfigManager(config_manager.config_path)
        assert "profile1" in manager2.profiles
        assert "profile2" in manager2.profiles
        assert manager2.get("model", profile="profile1") == "model1"
        assert manager2.get("model", profile="profile2") == "model2"


class TestConfigManagerPresets:
    """Test configuration presets."""

    def test_get_dev_preset(self, config_manager):
        """Test getting dev preset."""
        preset = config_manager.get_preset("dev")
        assert preset is not None
        assert preset.enable_livestream is True
        assert preset.autonomous_mode is False

    def test_get_prod_preset(self, config_manager):
        """Test getting prod preset."""
        preset = config_manager.get_preset("prod")
        assert preset is not None
        assert preset.enable_livestream is False
        assert preset.autonomous_mode is False

    def test_get_overnight_preset(self, config_manager):
        """Test getting overnight preset."""
        preset = config_manager.get_preset("overnight")
        assert preset is not None
        assert preset.autonomous_mode is True
        assert preset.context_threshold == 0.35

    def test_get_nonexistent_preset(self, config_manager):
        """Test getting a preset that doesn't exist."""
        preset = config_manager.get_preset("nonexistent")
        assert preset is None

    def test_apply_preset(self, config_manager):
        """Test applying a preset to a profile."""
        assert config_manager.apply_preset("dev") is True
        config = config_manager.get_config()
        assert config.enable_livestream is True

    def test_apply_nonexistent_preset(self, config_manager):
        """Test applying a preset that doesn't exist."""
        assert config_manager.apply_preset("nonexistent") is False


class TestConfigManagerEnvironmentOverrides:
    """Test environment variable overrides."""

    def test_env_api_key_override(self, monkeypatch):
        """Test API key override from environment."""
        # Environment variables are only applied if profiles exist
        # So we need to create a config file with profiles first
        monkeypatch.setenv("ANTHROPIC_API_KEY", "env-key")
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            import yaml

            config_data = {
                "current_profile": "default",
                "profiles": {
                    "default": {"api_key": "", "model": "claude-sonnet-4-20250514"}
                },
            }
            yaml.dump(config_data, f)
            temp_path = Path(f.name)
        try:
            manager = ConfigManager(temp_path)
            assert manager.get("api_key") == "env-key"
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_env_model_override(self, monkeypatch):
        """Test model override from environment."""
        monkeypatch.setenv("CLAUDE_MODEL", "env-model")
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            import yaml

            config_data = {
                "current_profile": "default",
                "profiles": {"default": {"model": "default-model"}},
            }
            yaml.dump(config_data, f)
            temp_path = Path(f.name)
        try:
            manager = ConfigManager(temp_path)
            assert manager.get("model") == "env-model"
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_env_max_tokens_override(self, monkeypatch):
        """Test max_tokens override from environment."""
        monkeypatch.setenv("MAX_TOKENS", "16000")
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            import yaml

            config_data = {
                "current_profile": "default",
                "profiles": {"default": {"max_tokens": 8000}},
            }
            yaml.dump(config_data, f)
            temp_path = Path(f.name)
        try:
            manager = ConfigManager(temp_path)
            assert manager.get("max_tokens") == 16000
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def test_env_boolean_override(self, monkeypatch):
        """Test boolean settings override from environment."""
        monkeypatch.setenv("USE_CONTEXT_MANAGER", "false")
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            import yaml

            config_data = {
                "current_profile": "default",
                "profiles": {"default": {"use_context_manager": True}},
            }
            yaml.dump(config_data, f)
            temp_path = Path(f.name)
        try:
            manager = ConfigManager(temp_path)
            assert manager.get("use_context_manager") is False
        finally:
            if temp_path.exists():
                temp_path.unlink()


class TestConfigManagerEdgeCases:
    """Test edge cases and error handling."""

    def test_get_config_nonexistent_profile(self, config_manager):
        """Test getting config for nonexistent profile returns default."""
        config = config_manager.get_config("nonexistent")
        assert isinstance(config, FoundryConfig)

    def test_set_on_new_profile_creates_it(self, config_manager):
        """Test setting value on nonexistent profile creates it."""
        config_manager.set("model", "test", profile="new_profile")
        assert "new_profile" in config_manager.profiles

    def test_empty_config_file_loads(self, temp_config_file):
        """Test loading empty config file."""
        temp_config_file.write_text("")
        manager = ConfigManager(temp_config_file)
        assert "default" in manager.profiles


class TestConfigManagerIntegration:
    """Integration tests for complex scenarios."""

    def test_complete_workflow(self, temp_config_file):
        """Test a complete configuration workflow."""
        # Create manager
        manager = ConfigManager(temp_config_file)

        # Create profiles
        manager.create_profile("dev")
        manager.create_profile("prod")

        # Configure dev profile
        manager.switch_profile("dev")
        manager.apply_preset("dev")
        manager.set("api_key", "dev-key")

        # Configure prod profile
        manager.switch_profile("prod")
        manager.apply_preset("prod")
        manager.set("api_key", "prod-key")

        # Save configuration
        manager.save()

        # Reload and verify
        manager2 = ConfigManager(temp_config_file)
        assert manager2.get("api_key", profile="dev") == "dev-key"
        assert manager2.get("api_key", profile="prod") == "prod-key"
        assert manager2.get("enable_livestream", profile="dev") is True
        assert manager2.get("enable_livestream", profile="prod") is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
