"""
Mindcraft Persistence Layer

Handles saving and loading of agent state and history.
Changes are persisted to ~/.context-foundry/mindcraft/state/
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from .models import AgentState


class MindcraftPersistence:
    """
    Persistence manager for Mindcraft extension.
    Saves agent states and event history to disk.
    """

    def __init__(self, base_dir: Optional[Path] = None):
        """
        Initialize persistence manager.

        Args:
            base_dir: Optional override for base directory.
                      Defaults to ~/.context-foundry/mindcraft
        """
        if base_dir:
            self.base_dir = base_dir
        else:
            self.base_dir = Path.home() / ".context-foundry" / "mindcraft"

        self.state_dir = self.base_dir / "state"
        self.logs_dir = self.base_dir / "logs"

        # Ensure directories exist
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        self.history_file = self.logs_dir / "orchestration.jsonl"

    def save_agent_state(self, state: AgentState) -> None:
        """
        Save the current state of an agent to disk.

        Args:
            state: The AgentState object to save
        """
        file_path = self.state_dir / f"{state.name}_state.json"
        try:
            with open(file_path, "w") as f:
                json.dump(state.to_dict(), f, indent=2)
        except Exception as e:
            print(f"Error saving agent state for {state.name}: {e}")

    def load_agent_state(self, name: str) -> Optional[AgentState]:
        """
        Load the last known state of an agent.

        Args:
            name: Agent name

        Returns:
            AgentState if found, None otherwise
        """
        file_path = self.state_dir / f"{name}_state.json"
        if not file_path.exists():
            return None

        try:
            with open(file_path, "r") as f:
                data = json.load(f)
            return AgentState.from_dict(data)
        except Exception as e:
            print(f"Error loading agent state for {name}: {e}")
            return None

    def get_all_saved_states(self) -> Dict[str, AgentState]:
        """
        Load all saved agent states found in the state directory.

        Returns:
            Dictionary mapping agent names to AgentState objects
        """
        states = {}
        for file_path in self.state_dir.glob("*_state.json"):
            try:
                # expecting filename like "andy_state.json"
                name = file_path.name.replace("_state.json", "")
                state = self.load_agent_state(name)
                if state:
                    states[name] = state
            except Exception:
                pass
        return states

    def save_history(self, event_type: str, details: Dict[str, Any]) -> None:
        """
        Append an event to the history log (JSONL format).

        Args:
            event_type: Type of event (e.g., "death", "goal_complete")
            details: Dictionary containing event details
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            "details": details,
        }

        try:
            with open(self.history_file, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            print(f"Error saving history: {e}")

    def get_recent_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get the most recent history entries.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of history entries
        """
        entries = []
        if not self.history_file.exists():
            return entries

        try:
            # Simple implementation for small logs.
            # For massive logs, reading from end would be better.
            with open(self.history_file, "r") as f:
                lines = f.readlines()

            for line in lines[-limit:]:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        except Exception as e:
            print(f"Error reading history: {e}")

        return entries
