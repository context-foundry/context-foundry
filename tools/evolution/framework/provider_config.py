"""
Provider Configuration for Phase-based Model/Provider Selection.

Allows configuring which LLM provider and model to use for each phase.

Configuration Priority (highest to lowest):
1. Environment variable: CF_PHASE_<PHASE>=<provider>:<model>
2. Config file: ~/.context-foundry/provider_config.json
3. Defaults: local provider, no specific model

Examples:
    # Environment variable
    export CF_PHASE_BUILDER=bedrock:qwen.qwen3-coder-480b-v1:0
    export CF_PHASE_SCOUT=bedrock:anthropic.claude-opus-4-5-20251101-v1:0
    export CF_PHASE_TEST=local

    # Config file (~/.context-foundry/provider_config.json)
    {
      "default_provider": "local",
      "default_bedrock_model": "anthropic.claude-opus-4-5-20251101-v1:0",
      "phases": {
        "Scout": { "provider": "bedrock", "model": "anthropic.claude-opus-4-5-20251101-v1:0" },
        "Builder": { "provider": "bedrock", "model": "qwen.qwen3-coder-480b-v1:0" }
      }
    }
"""

import os
import json
import logging
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

logger = logging.getLogger(__name__)

CONFIG_DIR = Path.home() / ".context-foundry"
CONFIG_PATH = CONFIG_DIR / "provider_config.json"

# Cache for loaded config
_config_cache: Optional[Dict[str, Any]] = None


def _load_config() -> Dict[str, Any]:
    """Load config from file, with caching."""
    global _config_cache

    if _config_cache is not None:
        return _config_cache

    if CONFIG_PATH.exists():
        try:
            _config_cache = json.loads(CONFIG_PATH.read_text())
            logger.debug(f"Loaded provider config from {CONFIG_PATH}")
            return _config_cache
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid provider config JSON: {e}")
            _config_cache = {}
            return _config_cache

    _config_cache = {}
    return _config_cache


def reload_config() -> None:
    """Force reload of config file (useful for testing)."""
    global _config_cache
    _config_cache = None
    _load_config()


def get_provider_for_phase(phase: str) -> Tuple[str, Optional[str], Optional[Dict[str, str]]]:
    """
    Get the provider and model for a given phase.

    Args:
        phase: Phase name (e.g., "Scout", "Builder", "Test")

    Returns:
        Tuple of (provider, model, extra_config) where:
        - provider: "local", "bedrock", or "bedrock-agent"
        - model: Model ID string or None
        - extra_config: Dict with 'agent_id', 'alias_id' for bedrock-agent

    Priority:
        1. Environment variable CF_PHASE_<PHASE>=provider:model
        2. Config file phase-specific setting
        3. Config file defaults
        4. Hardcoded defaults (local, None)
    """
    # Normalize phase name for env var lookup
    phase_upper = phase.upper().replace(" ", "_").replace("-", "_")
    env_key = f"CF_PHASE_{phase_upper}"

    # 1. Check environment variable (highest priority)
    env_val = os.environ.get(env_key)
    if env_val:
        parts = env_val.split(":", 1)
        provider = parts[0].strip().lower()
        rest = parts[1].strip() if len(parts) > 1 else None
        
        if provider == "bedrock-agent" and rest:
             # Parse AGENT_ID/ALIAS_ID
             if "/" in rest:
                 agent_id, alias_id = rest.split("/", 1)
                 logger.debug(f"Phase '{phase}' using env override: provider=bedrock-agent, agent={agent_id}, alias={alias_id}")
                 return ("bedrock-agent", None, {"agent_id": agent_id, "alias_id": alias_id})
        
        model = rest
        logger.debug(f"Phase '{phase}' using env override: provider={provider}, model={model}")
        return (provider, model, {})

    # 2. Load config file
    config = _load_config()

    # 3. Check phase-specific config
    phase_config = config.get("phases", {}).get(phase, {})

    if phase_config:
        provider = phase_config.get("provider", config.get("default_provider", "local"))
        model = phase_config.get("model")
        
        extra_config = {}
        if provider == "bedrock-agent":
            extra_config["agent_id"] = phase_config.get("agent_id")
            extra_config["alias_id"] = phase_config.get("alias_id")

        # If no model specified but using bedrock, use default bedrock model
        if model is None and provider == "bedrock":
            model = config.get("default_bedrock_model")

        logger.debug(f"Phase '{phase}' using config: provider={provider}, model={model}")
        return (provider, model, extra_config)

    # 4. Use defaults from config or hardcoded
    default_provider = config.get("default_provider", "local")
    default_model = config.get("default_bedrock_model") if default_provider == "bedrock" else None

    logger.debug(f"Phase '{phase}' using defaults: provider={default_provider}, model={default_model}")
    return (default_provider, default_model, {})


def get_all_phase_configs() -> Dict[str, Tuple[str, Optional[str], Optional[Dict[str, str]]]]:
    """
    Get provider/model config for all known phases.
    Useful for displaying current configuration.
    """
    phases = ["Scout", "Architect", "Builder", "Test", "Screenshot", "Documentation", "Deploy", "Feedback"]
    return {phase: get_provider_for_phase(phase) for phase in phases}


def create_default_config() -> None:
    """Create a default config file if it doesn't exist."""
    if CONFIG_PATH.exists():
        return

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    default_config = {
        "default_provider": "local",
        "default_bedrock_model": "anthropic.claude-opus-4-5-20251101-v1:0",
        "phases": {
            "Scout": {
                "provider": "bedrock",
                "model": "anthropic.claude-opus-4-5-20251101-v1:0",
                "_comment": "Deep codebase analysis needs best reasoning"
            },
            "Architect": {
                "provider": "bedrock",
                "model": "anthropic.claude-opus-4-5-20251101-v1:0",
                "_comment": "System design needs advanced reasoning"
            },
            "Builder": {
                "provider": "bedrock",
                "model": "anthropic.claude-sonnet-4-20250514-v1:0",
                "_comment": "Code generation - can swap to qwen3-coder for specialized tasks"
            },
            "Test": {
                "provider": "local",
                "_comment": "Simple task - use subscription"
            },
            "Screenshot": {
                "provider": "local",
                "_comment": "Simple task - use subscription"
            },
            "Documentation": {
                "provider": "local",
                "_comment": "Simple task - use subscription"
            },
            "Deploy": {
                "provider": "local",
                "_comment": "Simple task - use subscription"
            },
            "Feedback": {
                "provider": "local",
                "_comment": "Simple task - use subscription"
            }
        }
    }

    CONFIG_PATH.write_text(json.dumps(default_config, indent=2))
    logger.info(f"Created default provider config at {CONFIG_PATH}")


def print_current_config() -> None:
    """Print current configuration to stdout (for CLI usage)."""
    print(f"\nProvider Configuration")
    print(f"{'='*50}")
    print(f"Config file: {CONFIG_PATH}")
    print(f"Config exists: {CONFIG_PATH.exists()}")
    print()

    configs = get_all_phase_configs()

    print(f"{'Phase':<15} {'Provider':<10} {'Model':<50}")
    print(f"{'-'*15} {'-'*10} {'-'*50}")

    for phase, (provider, model, extra) in configs.items():
        model_display = model or "(default)"
        if provider == "bedrock-agent":
            agent_id = extra.get("agent_id", "N/A")
            alias_id = extra.get("alias_id", "N/A")
            model_display = f"Agent: {agent_id} (Alias: {alias_id})"
            
        # Check if overridden by env
        env_key = f"CF_PHASE_{phase.upper()}"
        env_marker = " [ENV]" if os.environ.get(env_key) else ""
        print(f"{phase:<15} {provider:<10} {model_display:<50}{env_marker}")

    print()


if __name__ == "__main__":
    # CLI: show current config
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "init":
        create_default_config()
        print(f"Created config at {CONFIG_PATH}")
    else:
        print_current_config()
