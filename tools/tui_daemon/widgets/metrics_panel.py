"""
Metrics Panel Widget - System statistics display

Shows aggregated metrics: Total jobs, Active jobs, Success rate, Average duration
"""

from textual.widgets import Static

from ..daemon_client import SystemMetrics


class MetricsPanel(Static):
    """
    Panel displaying system-wide metrics.

    Shows:
    - Total jobs
    - Active jobs
    - Success rate
    - Average duration
    """

    def __init__(self, **kwargs):
        """Initialize the metrics panel"""
        super().__init__(**kwargs)
        self._metrics: SystemMetrics = SystemMetrics(
            total_jobs=0, active_jobs=0, success_rate=0.0, avg_duration_seconds=0.0
        )

    def update_metrics(self, metrics: SystemMetrics) -> None:
        """
        Update displayed metrics.

        Args:
            metrics: SystemMetrics object with new data
        """
        self._metrics = metrics
        self._refresh_display()

    def _refresh_display(self) -> None:
        """Refresh the displayed metrics"""
        avg_mins = int(self._metrics.avg_duration_seconds / 60)

        self.update(
            f"Total: {self._metrics.total_jobs} | "
            f"Active: {self._metrics.active_jobs} | "
            f"Success: {self._metrics.success_rate:.1f}% | "
            f"Avg: {avg_mins}m"
        )
