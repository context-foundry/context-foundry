"""Phase progress widget"""

from textual.widgets import Static, ProgressBar
from textual.reactive import reactive
from textual.containers import Vertical
from textual.app import ComposeResult


class PhaseProgressWidget(Vertical):
    """Display current phase progress"""

    current_phase: reactive[str] = reactive("", init=False)
    progress: reactive[float] = reactive(0.0, init=False)
    progress_detail: reactive[str] = reactive("", init=False)

    def compose(self) -> ComposeResult:
        """Compose the widget"""
        yield Static("Phase: Unknown", id="phase-label")
        yield Static("", id="phase-detail")
        yield ProgressBar(total=100, show_eta=False, id="phase-bar")

    def watch_current_phase(self, phase: str):
        """Update phase label"""
        try:
            label = self.query_one("#phase-label", Static)
            label.update(f"Phase: {phase}")
        except Exception:
            pass

    def watch_progress_detail(self, detail: str):
        """Update progress detail"""
        try:
            detail_widget = self.query_one("#phase-detail", Static)
            detail_widget.update(detail)
        except Exception:
            pass

    def watch_progress(self, progress: float):
        """Update progress bar"""
        try:
            bar = self.query_one("#phase-bar", ProgressBar)
            # Ensure progress is between 0 and 100
            progress = max(0.0, min(100.0, progress))
            bar.update(progress=progress)
        except Exception:
            pass
