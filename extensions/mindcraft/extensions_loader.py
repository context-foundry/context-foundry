"""
Mindcraft Extension Loader

Provides safe loading interface for the Mindcraft extension.
Follows Context Foundry extension contract pattern.
"""

import sys
from pathlib import Path
from typing import Optional, Dict, Any, List

# Add parent to path for imports
EXTENSION_DIR = Path(__file__).parent
sys.path.insert(0, str(EXTENSION_DIR.parent.parent))

from .detector import detect_mindcraft_config, is_mindcraft_available  # noqa: E402


class MindcraftExtensionLoader:
    """
    Safe loader for the Mindcraft extension.

    Provides lazy loading, error handling, and extension lifecycle management.
    """

    def __init__(self):
        self._client = None
        self._monitor = None
        self._planner = None
        self._config = None
        self._loaded = False

    @property
    def config(self) -> Optional[Dict[str, Any]]:
        """Get extension configuration, loading if needed."""
        if self._config is None:
            self._config = detect_mindcraft_config()
        return self._config

    @property
    def is_available(self) -> bool:
        """Check if extension is available and properly configured."""
        return is_mindcraft_available()

    def load(self) -> bool:
        """
        Load the extension and initialize components.

        Returns:
            True if loaded successfully, False otherwise
        """
        if self._loaded:
            return True

        if not self.is_available:
            return False

        try:
            # Lazy import to avoid loading if not needed
            from .client import MindcraftClient

            self._client = MindcraftClient(
                server_url=self.config.get("server_url"),
                dry_run=self.config.get("dry_run", False),
            )
            self._loaded = True
            return True

        except ImportError as e:
            print(f"Warning: Could not load Mindcraft extension: {e}")
            return False
        except Exception as e:
            print(f"Error loading Mindcraft extension: {e}")
            return False

    def unload(self) -> None:
        """Unload the extension and cleanup resources."""
        if self._client:
            try:
                self._client.disconnect()
            except Exception:
                pass
            self._client = None

        self._monitor = None
        self._planner = None
        self._loaded = False

    @property
    def client(self):
        """Get the Mindcraft client, loading if needed."""
        if not self._loaded:
            self.load()
        return self._client

    def get_extension_info(self) -> Dict[str, Any]:
        """
        Get information about this extension.

        Returns:
            Dict with extension metadata
        """
        return {
            "name": "mindcraft",
            "version": "0.1.0",
            "description": "Orchestrate Mindcraft AI agents in Minecraft",
            "domain": "minecraft",
            "available": self.is_available,
            "loaded": self._loaded,
            "config": self.config,
        }

    def get_available_tools(self) -> List[str]:
        """
        Get list of tools provided by this extension.

        Returns:
            List of tool names
        """
        return [
            "mindcraft_orchestrate",
            "mindcraft_goal",
            "mindcraft_agent",
            "mindcraft_config",
            "mindcraft_status",
        ]


# Singleton instance for global access
_loader_instance: Optional[MindcraftExtensionLoader] = None


def get_loader() -> MindcraftExtensionLoader:
    """Get the singleton extension loader instance."""
    global _loader_instance
    if _loader_instance is None:
        _loader_instance = MindcraftExtensionLoader()
    return _loader_instance


def load_extension() -> bool:
    """Convenience function to load the extension."""
    return get_loader().load()


def unload_extension() -> None:
    """Convenience function to unload the extension."""
    get_loader().unload()


if __name__ == "__main__":
    # Self-test
    print("Mindcraft Extension Loader")
    print("=" * 40)

    loader = get_loader()
    print(f"Available: {loader.is_available}")

    info = loader.get_extension_info()
    for key, value in info.items():
        print(f"  {key}: {value}")

    if loader.is_available:
        print("\nLoading extension...")
        success = loader.load()
        print(f"Loaded: {success}")

        print("\nAvailable tools:")
        for tool in loader.get_available_tools():
            print(f"  - {tool}")
