#!/usr/bin/env python3
"""
Discord Notification Utility
Send messages to Discord channels via webhooks.
"""

import os
import sys
import requests
from typing import Optional, Dict, Any
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console  # noqa: E402

console = Console()


class DiscordNotifier:
    """Send notifications to Discord via webhooks."""

    def __init__(self, webhook_url: Optional[str] = None):
        """
        Initialize Discord notifier.

        Args:
            webhook_url: Discord webhook URL (or uses DISCORD_WEBHOOK env var)
        """
        self.webhook_url = webhook_url or os.getenv("DISCORD_WEBHOOK")

        if not self.webhook_url:
            raise ValueError(
                "Discord webhook URL not provided. "
                "Set DISCORD_WEBHOOK in .env or pass webhook_url parameter."
            )

    def send_message(
        self,
        content: str,
        username: Optional[str] = None,
        avatar_url: Optional[str] = None,
        embeds: Optional[list] = None,
    ) -> bool:
        """
        Send a message to Discord.

        Args:
            content: Message text (up to 2000 characters)
            username: Override webhook username (optional)
            avatar_url: Override webhook avatar (optional)
            embeds: List of embed objects for rich formatting (optional)

        Returns:
            True if message sent successfully, False otherwise
        """
        payload: Dict[str, Any] = {}

        if content:
            payload["content"] = content[:2000]  # Discord limit
        if username:
            payload["username"] = username
        if avatar_url:
            payload["avatar_url"] = avatar_url
        if embeds:
            payload["embeds"] = embeds

        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            console.print(f"[red]Failed to send Discord message:[/red] {e}")
            return False

    def send_release(
        self,
        version: str,
        title: str,
        description: str,
        url: Optional[str] = None,
        color: int = 0x00FF00,  # Green
    ) -> bool:
        """
        Send a release notification with rich formatting.

        Args:
            version: Release version (e.g., "v1.2.3")
            title: Release title
            description: Release description/notes
            url: URL to release (optional)
            color: Embed color (default: green)

        Returns:
            True if sent successfully
        """
        embed = {
            "title": f"🚀 {title}",
            "description": description,
            "color": color,
            "fields": [
                {"name": "Version", "value": version, "inline": True},
            ],
            "timestamp": self._get_timestamp(),
        }

        if url:
            embed["url"] = url

        return self.send_message(content=None, embeds=[embed])

    def send_build_complete(
        self,
        project: str,
        status: str,
        duration: str,
        tests_passed: Optional[int] = None,
        tests_total: Optional[int] = None,
    ) -> bool:
        """
        Send a build completion notification.

        Args:
            project: Project name
            status: "success" or "failed"
            duration: Build duration (e.g., "12m 34s")
            tests_passed: Number of tests passed (optional)
            tests_total: Total number of tests (optional)

        Returns:
            True if sent successfully
        """
        color = 0x00FF00 if status == "success" else 0xFF0000  # Green or red
        emoji = "✅" if status == "success" else "❌"

        fields = [
            {"name": "Status", "value": f"{emoji} {status.upper()}", "inline": True},
            {"name": "Duration", "value": duration, "inline": True},
        ]

        if tests_passed is not None and tests_total is not None:
            fields.append(
                {
                    "name": "Tests",
                    "value": f"{tests_passed}/{tests_total} passed",
                    "inline": True,
                }
            )

        embed = {
            "title": f"Build Complete: {project}",
            "color": color,
            "fields": fields,
            "timestamp": self._get_timestamp(),
        }

        return self.send_message(content=None, embeds=[embed])

    def send_simple(self, message: str) -> bool:
        """
        Send a simple text message.

        Args:
            message: Message to send

        Returns:
            True if sent successfully
        """
        return self.send_message(content=message)

    @staticmethod
    def _get_timestamp() -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime, timezone

        return datetime.now(timezone.utc).isoformat()


def main():
    """CLI for sending Discord messages."""
    import argparse

    parser = argparse.ArgumentParser(description="Send Discord notifications")
    parser.add_argument("message", help="Message to send")
    parser.add_argument(
        "--webhook", help="Discord webhook URL (or use DISCORD_WEBHOOK env)"
    )
    parser.add_argument("--username", help="Override webhook username")
    parser.add_argument("--release", help="Release version (enables release format)")
    parser.add_argument("--title", help="Release title (with --release)")
    parser.add_argument("--url", help="Release URL (with --release)")

    args = parser.parse_args()

    try:
        notifier = DiscordNotifier(webhook_url=args.webhook)

        if args.release:
            success = notifier.send_release(
                version=args.release,
                title=args.title or f"Release {args.release}",
                description=args.message,
                url=args.url,
            )
        else:
            success = notifier.send_simple(args.message)

        if success:
            console.print("[green]✓[/green] Message sent to Discord!")
            sys.exit(0)
        else:
            console.print("[red]✗[/red] Failed to send message")
            sys.exit(1)

    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
