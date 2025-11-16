#!/usr/bin/env python3
"""
Discord Notification Examples
Demonstrates various ways to send Discord messages.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.discord_notify import DiscordNotifier


def example_simple_message():
    """Send a simple text message."""
    notifier = DiscordNotifier()
    notifier.send_simple("🤖 Context Foundry: Build started!")


def example_release_notification():
    """Send a release announcement."""
    notifier = DiscordNotifier()
    notifier.send_release(
        version="v1.2.3",
        title="New Feature Release",
        description=(
            "**What's New:**\n"
            "• Added Discord webhook support\n"
            "• Improved build performance\n"
            "• Fixed critical bugs\n\n"
            "See the [release notes](https://github.com/your-repo/releases/v1.2.3) for details."
        ),
        url="https://github.com/your-repo/releases/v1.2.3",
        color=0x5865F2,  # Discord blurple
    )


def example_build_notification():
    """Send build completion notification."""
    notifier = DiscordNotifier()
    notifier.send_build_complete(
        project="context-foundry",
        status="success",
        duration="12m 34s",
        tests_passed=142,
        tests_total=142,
    )


def example_custom_embed():
    """Send a custom rich message with embeds."""
    notifier = DiscordNotifier()

    embed = {
        "title": "🎯 Weekly Deployment Summary",
        "description": "Automated deployment completed successfully",
        "color": 0x00FF00,  # Green
        "fields": [
            {"name": "Environment", "value": "Production", "inline": True},
            {"name": "Services", "value": "5 updated", "inline": True},
            {"name": "Status", "value": "✅ All systems operational", "inline": False},
        ],
        "footer": {"text": "Context Foundry"},
        "timestamp": notifier._get_timestamp(),
    }

    notifier.send_message(content=None, embeds=[embed])


def example_with_username_override():
    """Send message with custom username and avatar."""
    notifier = DiscordNotifier()
    notifier.send_message(
        content="🚀 Deployment complete!",
        username="Context Foundry Bot",
        avatar_url="https://example.com/bot-avatar.png",
    )


def example_error_notification():
    """Send an error/warning notification."""
    notifier = DiscordNotifier()

    embed = {
        "title": "⚠️ Build Warning",
        "description": "Build completed with warnings",
        "color": 0xFFA500,  # Orange
        "fields": [
            {"name": "Project", "value": "my-app", "inline": True},
            {"name": "Warnings", "value": "3", "inline": True},
            {
                "name": "Details",
                "value": (
                    "• Deprecated API usage\n"
                    "• Missing documentation\n"
                    "• Type hints needed"
                ),
                "inline": False,
            },
        ],
        "timestamp": notifier._get_timestamp(),
    }

    notifier.send_message(content=None, embeds=[embed])


if __name__ == "__main__":
    print("Discord Notification Examples")
    print("=" * 50)
    print("\nAvailable examples:")
    print("1. Simple message")
    print("2. Release notification")
    print("3. Build notification")
    print("4. Custom embed")
    print("5. Username override")
    print("6. Error notification")
    print("\nSet DISCORD_WEBHOOK in .env to test these examples.")
    print("\nUsage:")
    print("  from tools.discord_notify import DiscordNotifier")
    print("  notifier = DiscordNotifier()")
    print('  notifier.send_simple("Your message here")')
