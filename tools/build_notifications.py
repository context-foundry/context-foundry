#!/usr/bin/env python3
"""
Build Notification System
Send Discord notifications when builds complete.
"""

import os
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.discord_notify import DiscordNotifier  # noqa: E402


class BuildNotificationManager:
    """Manage Discord notifications for build events."""

    def __init__(self, webhook_url: Optional[str] = None):
        """
        Initialize build notification manager.

        Args:
            webhook_url: Discord webhook URL (or uses DISCORD_WEBHOOK env var)
        """
        self.webhook_url = webhook_url or os.getenv("DISCORD_WEBHOOK")
        self.enabled = bool(self.webhook_url)

        if self.enabled:
            self.notifier = DiscordNotifier(webhook_url=self.webhook_url)

    def notify_build_started(
        self,
        project: str,
        task: str,
        job_id: Optional[str] = None,
    ) -> bool:
        """
        Notify when a build starts.

        Args:
            project: Project name
            task: Task description
            job_id: Optional job ID

        Returns:
            True if notification sent successfully
        """
        if not self.enabled:
            return False

        embed = {
            "title": "🔨 Build Started",
            "description": f"**Project:** {project}\n**Task:** {task}",
            "color": 0x3498DB,  # Blue
            "timestamp": self._get_timestamp(),
        }

        if job_id:
            embed["footer"] = {"text": f"Job ID: {job_id}"}

        return self.notifier.send_message(content=None, embeds=[embed])

    def notify_build_complete(
        self,
        project: str,
        status: str,
        duration_seconds: float,
        job_id: Optional[str] = None,
        tests_passed: Optional[int] = None,
        tests_total: Optional[int] = None,
        phases_completed: Optional[list] = None,
        error_message: Optional[str] = None,
    ) -> bool:
        """
        Notify when a build completes.

        Args:
            project: Project name
            status: "success" or "failed"
            duration_seconds: Build duration in seconds
            job_id: Optional job ID
            tests_passed: Number of tests passed
            tests_total: Total number of tests
            phases_completed: List of completed phases
            error_message: Error message if build failed

        Returns:
            True if notification sent successfully
        """
        if not self.enabled:
            return False

        # Determine status emoji and color
        if status == "success":
            emoji = "✅"
            color = 0x2ECC71  # Green
            title = "Build Complete - Success"
        else:
            emoji = "❌"
            color = 0xE74C3C  # Red
            title = "Build Complete - Failed"

        # Format duration
        duration_str = self._format_duration(duration_seconds)

        # Build fields
        fields = [
            {"name": "Status", "value": f"{emoji} {status.upper()}", "inline": True},
            {"name": "Duration", "value": duration_str, "inline": True},
        ]

        # Add test results if available
        if tests_passed is not None and tests_total is not None:
            test_emoji = "✅" if tests_passed == tests_total else "⚠️"
            fields.append(
                {
                    "name": "Tests",
                    "value": f"{test_emoji} {tests_passed}/{tests_total} passed",
                    "inline": True,
                }
            )

        # Add phases if available
        if phases_completed:
            phases_str = " → ".join(phases_completed)
            fields.append({"name": "Phases", "value": phases_str, "inline": False})

        # Add error message if failed
        description = f"**Project:** {project}"
        if error_message and status == "failed":
            # Truncate error message if too long
            error_preview = error_message[:500]
            if len(error_message) > 500:
                error_preview += "..."
            description += f"\n\n**Error:**\n```\n{error_preview}\n```"

        embed = {
            "title": title,
            "description": description,
            "color": color,
            "fields": fields,
            "timestamp": self._get_timestamp(),
        }

        if job_id:
            embed["footer"] = {"text": f"Job ID: {job_id}"}

        return self.notifier.send_message(content=None, embeds=[embed])

    def notify_phase_complete(
        self,
        project: str,
        phase: str,
        status: str,
        job_id: Optional[str] = None,
    ) -> bool:
        """
        Notify when a build phase completes.

        Args:
            project: Project name
            phase: Phase name (Scout, Architect, Builder, Test)
            status: "completed" or "failed"
            job_id: Optional job ID

        Returns:
            True if notification sent successfully
        """
        if not self.enabled:
            return False

        # Phase emojis
        phase_emojis = {
            "Scout": "🔍",
            "Architect": "📐",
            "Builder": "🔨",
            "Test": "🧪",
            "Feedback": "📊",
        }

        emoji = phase_emojis.get(phase, "⚙️")
        status_emoji = "✅" if status == "completed" else "❌"

        embed = {
            "title": f"{emoji} Phase Complete: {phase}",
            "description": f"**Project:** {project}\n**Status:** {status_emoji} {status.upper()}",
            "color": 0x9B59B6,  # Purple
            "timestamp": self._get_timestamp(),
        }

        if job_id:
            embed["footer"] = {"text": f"Job ID: {job_id}"}

        return self.notifier.send_message(content=None, embeds=[embed])

    def notify_test_iteration(
        self,
        project: str,
        iteration: int,
        max_iterations: int,
        tests_passed: int,
        tests_total: int,
        job_id: Optional[str] = None,
    ) -> bool:
        """
        Notify about test iteration progress.

        Args:
            project: Project name
            iteration: Current iteration number
            max_iterations: Maximum iterations
            tests_passed: Number of tests passed
            tests_total: Total number of tests
            job_id: Optional job ID

        Returns:
            True if notification sent successfully
        """
        if not self.enabled:
            return False

        progress = f"{iteration}/{max_iterations}"
        test_status = f"{tests_passed}/{tests_total}"

        embed = {
            "title": "🔄 Test Iteration",
            "description": f"**Project:** {project}",
            "color": 0xF39C12,  # Orange
            "fields": [
                {"name": "Iteration", "value": progress, "inline": True},
                {"name": "Tests Passed", "value": test_status, "inline": True},
            ],
            "timestamp": self._get_timestamp(),
        }

        if job_id:
            embed["footer"] = {"text": f"Job ID: {job_id}"}

        return self.notifier.send_message(content=None, embeds=[embed])

    @staticmethod
    def _format_duration(seconds: float) -> str:
        """Format duration in human-readable format."""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            remaining_seconds = int(seconds % 60)
            return f"{minutes}m {remaining_seconds}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"

    @staticmethod
    def _get_timestamp() -> str:
        """Get current timestamp in ISO format."""
        from datetime import timezone

        return datetime.now(timezone.utc).isoformat()


# Singleton instance for easy access
_notification_manager = None


def get_notification_manager() -> BuildNotificationManager:
    """Get global notification manager instance."""
    global _notification_manager
    if _notification_manager is None:
        _notification_manager = BuildNotificationManager()
    return _notification_manager


def notify_build_started(project: str, task: str, job_id: Optional[str] = None):
    """Convenience function to notify build started."""
    manager = get_notification_manager()
    return manager.notify_build_started(project, task, job_id)


def notify_build_complete(
    project: str,
    status: str,
    duration_seconds: float,
    job_id: Optional[str] = None,
    tests_passed: Optional[int] = None,
    tests_total: Optional[int] = None,
    phases_completed: Optional[list] = None,
    error_message: Optional[str] = None,
):
    """Convenience function to notify build complete."""
    manager = get_notification_manager()
    return manager.notify_build_complete(
        project=project,
        status=status,
        duration_seconds=duration_seconds,
        job_id=job_id,
        tests_passed=tests_passed,
        tests_total=tests_total,
        phases_completed=phases_completed,
        error_message=error_message,
    )


def notify_phase_complete(
    project: str, phase: str, status: str, job_id: Optional[str] = None
):
    """Convenience function to notify phase complete."""
    manager = get_notification_manager()
    return manager.notify_phase_complete(project, phase, status, job_id)


if __name__ == "__main__":
    # Test the notification system
    import argparse

    parser = argparse.ArgumentParser(description="Test build notifications")
    parser.add_argument("--test", choices=["start", "success", "failed", "phase"])
    parser.add_argument("--project", default="test-project")

    args = parser.parse_args()

    manager = BuildNotificationManager()

    if args.test == "start":
        manager.notify_build_started(
            project=args.project,
            task="Test build notification",
            job_id="test-123",
        )
    elif args.test == "success":
        manager.notify_build_complete(
            project=args.project,
            status="success",
            duration_seconds=754,  # 12m 34s
            job_id="test-123",
            tests_passed=142,
            tests_total=142,
            phases_completed=["Scout", "Architect", "Builder", "Test"],
        )
    elif args.test == "failed":
        manager.notify_build_complete(
            project=args.project,
            status="failed",
            duration_seconds=345,
            job_id="test-123",
            error_message="TypeError: Cannot read property 'foo' of undefined",
        )
    elif args.test == "phase":
        manager.notify_phase_complete(
            project=args.project,
            phase="Scout",
            status="completed",
            job_id="test-123",
        )

    print("Test notification sent!")
