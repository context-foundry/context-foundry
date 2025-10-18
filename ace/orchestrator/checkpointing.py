#!/usr/bin/env python3
"""
Checkpointing system for long-running agent workflows.

Based on Anthropic's approach:
- Regular checkpoints during execution
- Resume from checkpoint on failure
- Combine with retry logic
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional


class CheckpointManager:
    """
    Manages checkpoints for long-running workflows.

    Allows resuming from failures without starting over.
    """

    def __init__(self, session_dir: Path):
        """Initialize checkpoint manager.

        Args:
            session_dir: Directory for this session
        """
        self.session_dir = Path(session_dir)
        self.checkpoint_dir = self.session_dir / 'checkpoints'
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def save_checkpoint(self, phase: str, state: Dict[str, Any]):
        """Save checkpoint after completing a phase.

        Args:
            phase: Phase name (e.g., 'planning', 'scout', 'architect', 'builder', 'validation')
            state: State to save
        """

        timestamp = datetime.now().isoformat()
        checkpoint_file = self.checkpoint_dir / f"{phase}_{timestamp.replace(':', '-')}.json"

        checkpoint_data = {
            'phase': phase,
            'timestamp': timestamp,
            'state': state
        }

        with open(checkpoint_file, 'w') as f:
            json.dump(checkpoint_data, f, indent=2)

        print(f"💾 Checkpoint saved: {phase}")

    def load_latest_checkpoint(self) -> Optional[Dict[str, Any]]:
        """Load the most recent checkpoint.

        Returns:
            Checkpoint data or None if no checkpoints exist
        """

        checkpoints = sorted(self.checkpoint_dir.glob("*.json"))

        if not checkpoints:
            return None

        latest = checkpoints[-1]

        with open(latest) as f:
            checkpoint_data = json.load(f)

        print(f"📂 Loaded checkpoint: {checkpoint_data['phase']} from {checkpoint_data['timestamp']}")

        return checkpoint_data

    def load_checkpoint_by_phase(self, phase: str) -> Optional[Dict[str, Any]]:
        """Load the most recent checkpoint for a specific phase.

        Args:
            phase: Phase name to load

        Returns:
            Checkpoint data or None if not found
        """

        checkpoints = sorted(self.checkpoint_dir.glob(f"{phase}_*.json"))

        if not checkpoints:
            return None

        latest = checkpoints[-1]

        with open(latest) as f:
            checkpoint_data = json.load(f)

        print(f"📂 Loaded {phase} checkpoint from {checkpoint_data['timestamp']}")

        return checkpoint_data

    def resume_from_checkpoint(self, checkpoint_data: Dict) -> str:
        """Determine which phase to resume from.

        Args:
            checkpoint_data: Checkpoint data

        Returns:
            Next phase to execute
        """

        phase = checkpoint_data['phase']

        # Map completed phases to next phase
        next_phase = {
            'planning': 'scout',
            'scout': 'architect',
            'architect': 'builder',
            'builder': 'validation',
            'validation': 'complete'
        }

        return next_phase.get(phase, 'planning')

    def list_checkpoints(self) -> list[Dict[str, Any]]:
        """List all checkpoints for this session.

        Returns:
            List of checkpoint metadata
        """

        checkpoints = []

        for checkpoint_file in sorted(self.checkpoint_dir.glob("*.json")):
            with open(checkpoint_file) as f:
                data = json.load(f)
                checkpoints.append({
                    'phase': data['phase'],
                    'timestamp': data['timestamp'],
                    'file': checkpoint_file.name
                })

        return checkpoints

    def clear_checkpoints(self):
        """Clear all checkpoints for this session."""

        for checkpoint_file in self.checkpoint_dir.glob("*.json"):
            checkpoint_file.unlink()

        print(f"🗑️  Cleared all checkpoints")
