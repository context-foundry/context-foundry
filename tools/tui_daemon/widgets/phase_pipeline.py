"""
Phase Pipeline Widget - Visual progress bar for build phases

Displays: Scout → Architect → Builder → Test
With status icons and progress percentage.
"""

from typing import Dict, List
from textual.widgets import Static
from textual.containers import Vertical

from ..daemon_client import PhaseEvent


class PhasePipeline(Vertical):
    """
    Visual representation of build phase pipeline.

    Shows phases: Scout → Architect → Builder → Test
    With status icons: ✓ (completed), 🔄 (in progress), ⏳ (pending), ✗ (failed)
    """

    PHASES = ["scout", "architect", "builder", "test"]

    STATUS_ICONS = {
        "completed": "✓",
        "started": "🔄",
        "failed": "✗",
        "pending": "⏳",
    }

    def __init__(self, **kwargs):
        """Initialize the phase pipeline"""
        super().__init__(**kwargs)
        self._phase_status: Dict[str, str] = {phase: "pending" for phase in self.PHASES}
        self._progress_percent = 0.0

    def update_phases(self, phase_events: List[PhaseEvent]) -> None:
        """
        Update pipeline with phase events.

        Args:
            phase_events: List of PhaseEvent objects
        """
        # Reset status
        self._phase_status = {phase: "pending" for phase in self.PHASES}

        # Process events
        for event in phase_events:
            phase = event.phase.lower()
            if phase in self._phase_status:
                self._phase_status[phase] = event.status

        # Calculate overall progress
        self._calculate_progress(phase_events)

        # Refresh display
        self._refresh_display()

    def _calculate_progress(self, phase_events: List[PhaseEvent]) -> None:
        """Calculate overall progress percentage"""
        # Count completed phases
        completed = sum(
            1 for status in self._phase_status.values() if status == "completed"
        )

        # Check for in-progress phase
        in_progress = any(status == "started" for status in self._phase_status.values())

        # Base progress on completed phases
        self._progress_percent = (completed / len(self.PHASES)) * 100

        # Add partial progress for in-progress phase
        if in_progress and phase_events:
            # Get latest progress_percent from events
            latest_progress = max(
                (e.progress_percent for e in phase_events if e.status == "started"),
                default=0.0,
            )
            # Add partial credit for current phase
            phase_weight = 100 / len(self.PHASES)
            self._progress_percent += (latest_progress / 100) * phase_weight

    def compose(self):
        """Initial composition of child widgets."""
        yield Static("", id="phase-display")
        yield Static("", id="progress-bar")

    def on_mount(self) -> None:
        """Initial render when widget mounts."""
        self._refresh_display()

    def _refresh_display(self) -> None:
        """Refresh the visual display"""
        # Build phase status line
        phase_line = " → ".join(
            [
                f"{phase.capitalize()} {self.STATUS_ICONS[self._phase_status[phase]]}"
                for phase in self.PHASES
            ]
        )

        # Build progress bar (text representation)
        bar_width = 40
        filled = int((self._progress_percent / 100) * bar_width)
        empty = bar_width - filled
        progress_bar = f"[{'█' * filled}{'░' * empty}] {self._progress_percent:.0f}%"

        # Update existing widgets instead of mounting new ones
        phase_widget = self.query_one("#phase-display", Static)
        phase_widget.update(phase_line)

        progress_widget = self.query_one("#progress-bar", Static)
        progress_widget.update(progress_bar)
