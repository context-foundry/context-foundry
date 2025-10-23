"""Phase Pipeline Widget - Visual workflow display"""

from rich.console import RenderableType
from rich.panel import Panel
from rich.text import Text
from textual.reactive import reactive
from textual.widget import Widget


class PhasesPipelineWidget(Widget):
    """Visual pipeline showing all build phases with progress bars"""

    # Reactive properties
    session_id: reactive[str] = reactive("No build")
    overall_progress: reactive[int] = reactive(0)
    time_elapsed: reactive[str] = reactive("0m 0s")

    # Phase data (phase_name, progress_percent, status, details)
    phases: reactive[list] = reactive([
        ("Scout", 0, "pending", ""),
        ("Architect", 0, "pending", ""),
        ("Builder", 0, "pending", ""),
        ("Tester", 0, "pending", ""),
        ("Fix Loop", 0, "standby", ""),
        ("Reviewer", 0, "pending", ""),
        ("Integrator", 0, "pending", ""),
        ("Deployer", 0, "pending", "")
    ])

    def render(self) -> RenderableType:
        """Render the visual pipeline"""
        lines = []

        # Header
        lines.append("╔═══════════════════════════════════════════════════════════════════════╗")
        header_text = f"🚀 {self.session_id} • {self.overall_progress}% • {self.time_elapsed} elapsed"
        padding = 71 - len(header_text)
        lines.append(f"║  {header_text}{' ' * padding}║")
        lines.append("╚═══════════════════════════════════════════════════════════════════════╝")
        lines.append("")

        # Phase bars
        for idx, (phase_name, progress, status, details) in enumerate(self.phases):
            phase_num = idx + 1 if idx < 4 else (idx + 0.5 if idx == 4 else idx)

            # Format phase number
            if idx == 4:
                phase_label = f"Phase 4.5:"
            else:
                actual_num = idx + 1 if idx < 4 else idx
                phase_label = f"Phase {actual_num}:"

            # Status icons
            status_icons = {
                "completed": "✅",
                "running": "🔄",
                "pending": "⏳",
                "standby": "⏸️"
            }
            status_icon = status_icons.get(status, "⏳")

            # Special markers
            marker = ""
            if phase_name == "Builder":
                marker = "⚡"
            elif phase_name == "Fix Loop":
                marker = "🔧"

            # Create progress bar (28 chars wide)
            bar_width = 28
            filled = int((progress / 100) * bar_width)
            empty = bar_width - filled

            if progress == 100:
                # Completed - solid fill
                bar = "█" * bar_width
            elif progress > 0:
                # In progress - mix filled and empty
                bar = "█" * filled + "░" * empty
            else:
                # Pending/standby - all empty
                bar = "░" * bar_width

            # Format details
            detail_text = f" {details}" if details else ""
            if status == "running":
                detail_text = f" {details or 'In progress...'}"

            # Build line
            phase_line = f"{phase_label:12} {phase_name:12}{marker:2} {bar} {progress:3}% {status_icon}{detail_text}"
            lines.append(phase_line)

        # Overall progress
        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

        # Overall bar (60 chars wide)
        overall_filled = int((self.overall_progress / 100) * 60)
        overall_empty = 60 - overall_filled
        overall_bar = "█" * overall_filled + "▓" * min(5, overall_empty) + "░" * max(0, overall_empty - 5)

        lines.append(f"Overall: {overall_bar} {self.overall_progress}%")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

        return "\n".join(lines)

    def update_from_build(self, build_status, duration_minutes=None):
        """Update pipeline from build status data"""
        if not build_status:
            self.session_id = "No active builds"
            self.overall_progress = 0
            self.time_elapsed = "0m 0s"
            # Reset all phases to pending
            self.phases = [
                ("Scout", 0, "pending", ""),
                ("Architect", 0, "pending", ""),
                ("Builder", 0, "pending", ""),
                ("Tester", 0, "pending", ""),
                ("Fix Loop", 0, "standby", ""),
                ("Reviewer", 0, "pending", ""),
                ("Integrator", 0, "pending", ""),
                ("Deployer", 0, "pending", "")
            ]
            return

        # Update header
        self.session_id = build_status.session_id or "build"

        # Format time elapsed
        if duration_minutes:
            minutes = int(duration_minutes)
            seconds = int((duration_minutes - minutes) * 60)
            self.time_elapsed = f"{minutes}m {seconds}s"
        else:
            self.time_elapsed = "0m 0s"

        # Parse current phase
        current_phase_name = build_status.current_phase.split()[0] if build_status.current_phase else "Scout"
        phase_status = build_status.status

        # Map phases
        phase_map = {
            "Scout": 0,
            "Architect": 1,
            "Builder": 2,
            "Test": 3,
            "Tester": 3,
            "Fix": 4,
            "Review": 5,
            "Reviewer": 5,
            "Integrate": 6,
            "Integrator": 6,
            "Deploy": 7,
            "Deployer": 7,
            "Complete": 8
        }

        current_phase_idx = phase_map.get(current_phase_name, 0)

        # Build phases list
        new_phases = []

        for idx, (name, _, _, _) in enumerate(self.phases):
            if idx < current_phase_idx:
                # Completed phases
                progress = 100
                status = "completed"
                details = ""

                # Add worker count for Builder
                if name == "Builder" and "4 workers" not in details:
                    details = "(4 workers)"

            elif idx == current_phase_idx:
                # Current phase
                if phase_status == "completed":
                    progress = 100
                    status = "completed"
                    details = ""
                else:
                    # Estimate progress based on phase
                    if name == "Scout":
                        progress = 50
                    elif name == "Architect":
                        progress = 50
                    elif name == "Builder":
                        progress = 65
                    elif name == "Tester":
                        progress = 65
                    else:
                        progress = 50

                    status = "running"
                    details = build_status.progress_detail or "In progress..."

            else:
                # Pending phases
                progress = 0
                if name == "Fix Loop":
                    status = "standby"
                    details = "If tests fail"
                else:
                    status = "pending"
                    details = ""

            new_phases.append((name, progress, status, details))

        self.phases = new_phases

        # Calculate overall progress
        completed_phases = sum(1 for _, prog, _, _ in new_phases if prog == 100)
        # Don't count Fix Loop in total
        total_phases = 7
        self.overall_progress = int((completed_phases / total_phases) * 100)
