"""Build table widget"""

from typing import List
from textual.widgets import DataTable
from textual.reactive import reactive

from ..data.models import BuildSummary


class BuildTable(DataTable):
    """Table displaying build list"""

    builds: reactive[List[BuildSummary]] = reactive(list, init=False)

    def on_mount(self):
        """Setup table columns"""
        self.cursor_type = "row"
        self.zebra_stripes = True
        self.add_columns(
            "Status",
            "Session ID",
            "Phase",
            "Started",
            "Duration",
            "Iter"
        )

    def watch_builds(self, builds: List[BuildSummary]):
        """Update table when builds change"""
        self.clear()

        if not builds:
            # Show empty state
            self.add_row("—", "No builds found", "—", "—", "—", "—")
            return

        for build in builds:
            # Format status with icon
            status_display = f"{build.get_status_icon()} {build.status}"

            # Truncate session ID
            session_display = build.session_id[:25] + "..." if len(build.session_id) > 25 else build.session_id

            # Format time
            time_display = build.started_at.strftime("%H:%M:%S")

            self.add_row(
                status_display,
                session_display,
                build.current_phase,
                time_display,
                build.get_duration_display(),
                str(build.test_iterations)
            )
