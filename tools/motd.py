#!/usr/bin/env python3
"""
Context Foundry - Message of the Day (MOTD) System

Generates intelligent, context-aware welcome messages that rotate daily.
Uses Claude (via delegation) to generate fresh, relevant messages.
"""

import json
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
import random

# MOTD cache location
MOTD_CACHE_PATH = Path.home() / ".context-foundry" / "motd.json"
MOTD_CACHE_MAX_AGE_HOURS = 4  # Refresh every 4 hours for variety


def get_context() -> dict:
    """Gather context for intelligent message generation."""
    now = datetime.now()

    # Time of day
    hour = now.hour
    if 5 <= hour < 12:
        time_of_day = "morning"
    elif 12 <= hour < 17:
        time_of_day = "afternoon"
    elif 17 <= hour < 21:
        time_of_day = "evening"
    else:
        time_of_day = "night"

    # Day of week
    day_of_week = now.strftime("%A")
    is_weekend = now.weekday() >= 5

    # Season (Northern Hemisphere)
    month = now.month
    if month in [3, 4, 5]:
        season = "spring"
    elif month in [6, 7, 8]:
        season = "summer"
    elif month in [9, 10, 11]:
        season = "fall"
    else:
        season = "winter"

    # Special dates/holidays
    special_occasion = None
    month_day = (now.month, now.day)

    holidays = {
        (1, 1): "New Year's Day",
        (2, 14): "Valentine's Day",
        (3, 14): "Pi Day",
        (3, 17): "St. Patrick's Day",
        (4, 1): "April Fools' Day",
        (5, 4): "Star Wars Day",
        (7, 4): "Independence Day",
        (10, 31): "Halloween",
        (11, 11): "Veterans Day",
        (12, 25): "Christmas",
        (12, 31): "New Year's Eve",
    }

    # Check exact match
    if month_day in holidays:
        special_occasion = holidays[month_day]

    # Check proximity to holidays (within 3 days)
    for (m, d), name in holidays.items():
        try:
            holiday_date = now.replace(month=m, day=d)
            days_until = (holiday_date - now).days
            if 0 < days_until <= 3:
                special_occasion = f"{name} coming up"
                break
        except ValueError:
            continue

    # Week of year for variety
    week_of_year = now.isocalendar()[1]

    return {
        "time_of_day": time_of_day,
        "day_of_week": day_of_week,
        "is_weekend": is_weekend,
        "season": season,
        "month": now.strftime("%B"),
        "special_occasion": special_occasion,
        "week_of_year": week_of_year,
        "year": now.year,
        "date": now.strftime("%Y-%m-%d"),
    }


def get_fallback_messages() -> list[str]:
    """Fallback messages when Claude generation isn't available."""
    context = get_context()

    # Base messages by time of day
    time_messages = {
        "morning": [
            "Good morning! Fresh context, fresh possibilities.",
            "Rise and build! Your code awaits.",
            "Morning builds hit different. Let's create something great.",
        ],
        "afternoon": [
            "Afternoon focus mode activated. What are we building?",
            "Peak productivity hours. Let's make them count.",
            "The afternoon stretch - perfect for shipping features.",
        ],
        "evening": [
            "Evening coding session? The best ideas come after hours.",
            "Burning the evening oil. Let's build something memorable.",
            "Evening mode: fewer interruptions, more flow state.",
        ],
        "night": [
            "Night owl mode engaged. The code is quieter at night.",
            "Late night builds have their own magic.",
            "While the world sleeps, we ship.",
        ],
    }

    # Season-specific additions
    season_messages = {
        "spring": [
            "Spring cleaning your codebase? Or planting new features?",
            "New season, new builds. What's sprouting today?",
        ],
        "summer": [
            "Summer builds: hot features, cool code.",
            "The days are long - perfect for ambitious projects.",
        ],
        "fall": [
            "Fall into a new project. The harvest of features awaits.",
            "Cozy coding weather. Time to build something warm.",
        ],
        "winter": [
            "Winter builds: staying warm with hot deploys.",
            "Cold outside, but the builds are running hot.",
        ],
    }

    # Weekend vibes
    weekend_messages = [
        "Weekend warrior mode! No meetings, pure building.",
        "Saturday/Sunday special: uninterrupted flow time.",
        "Weekend builds hit different. Let's ship something fun.",
    ]

    # Friday energy
    friday_messages = [
        "Friday deploy? Bold. I respect it.",
        "TGIF - Thank God It's Feature-complete.",
        "Friday: Ship it and forget it (until Monday).",
    ]

    # Monday motivation
    monday_messages = [
        "Monday fresh start. Clean slate, clean builds.",
        "New week, new features. Let's get it.",
        "Monday momentum: starting strong.",
    ]

    # Build the pool
    messages = time_messages.get(context["time_of_day"], [])
    messages.extend(season_messages.get(context["season"], []))

    if context["is_weekend"]:
        messages.extend(weekend_messages)
    elif context["day_of_week"] == "Friday":
        messages.extend(friday_messages)
    elif context["day_of_week"] == "Monday":
        messages.extend(monday_messages)

    # Special occasion override
    if context["special_occasion"]:
        occasion = context["special_occasion"]
        if "Halloween" in occasion:
            messages = ["Spooky season builds: May your tests pass and bugs be few."]
        elif "Christmas" in occasion:
            messages = ["Ho ho ho! Deploying presents to production."]
        elif "New Year" in occasion:
            messages = ["New year, new codebase, new possibilities!"]
        elif "Pi Day" in occasion:
            messages = ["Happy Pi Day! Time for some irrational productivity."]
        elif "Star Wars" in occasion:
            messages = ["May the Fourth be with your builds today."]

    return messages


def generate_motd_with_claude(context: dict) -> Optional[str]:
    """Generate a fresh MOTD using Claude via delegation."""
    prompt = f"""Generate a single, short (1-2 sentences max) welcome message for a developer starting their coding session with Context Foundry (an AI-powered autonomous build system).

Context:
- Time: {context['time_of_day']} on {context['day_of_week']}
- Season: {context['season']} ({context['month']})
- Special occasion: {context['special_occasion'] or 'None'}
- Weekend: {context['is_weekend']}

Guidelines:
- Be warm but not cheesy
- Mix professional with playful
- Reference the context naturally (don't force it)
- No emojis
- Focus on building/creating/shipping
- Make them feel ready to build something great
- Vary the style: sometimes inspirational, sometimes witty, sometimes matter-of-fact

Just output the message, nothing else. No quotes, no explanation."""

    try:
        # Use Claude Code CLI delegation
        result = subprocess.run(
            ["claude", "-p", prompt, "--output-format", "text"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0 and result.stdout.strip():
            message = result.stdout.strip()
            # Clean up any quotes Claude might add
            message = message.strip("\"'")
            # Sanity check - not too long
            if len(message) < 200:
                return message
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
        pass

    return None


def load_cached_motd() -> Optional[dict]:
    """Load MOTD from cache if fresh."""
    if not MOTD_CACHE_PATH.exists():
        return None

    try:
        with open(MOTD_CACHE_PATH) as f:
            cache = json.load(f)

        cached_time = datetime.fromisoformat(cache.get("generated_at", "2000-01-01"))
        age = datetime.now() - cached_time

        if age < timedelta(hours=MOTD_CACHE_MAX_AGE_HOURS):
            return cache
    except (json.JSONDecodeError, KeyError, ValueError):
        pass

    return None


def save_motd_cache(message: str, source: str):
    """Save MOTD to cache."""
    MOTD_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)

    cache = {
        "message": message,
        "source": source,
        "generated_at": datetime.now().isoformat(),
        "context": get_context(),
    }

    with open(MOTD_CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=2)


def get_motd(force_refresh: bool = False) -> str:
    """Get the Message of the Day.

    Args:
        force_refresh: If True, generate new message even if cache is fresh

    Returns:
        The MOTD string
    """
    # Check cache first (unless forcing refresh)
    if not force_refresh:
        cached = load_cached_motd()
        if cached:
            return cached["message"]

    # Get context
    context = get_context()

    # Try Claude generation first
    message = generate_motd_with_claude(context)
    if message:
        save_motd_cache(message, "claude")
        return message

    # Fall back to pre-defined messages
    fallbacks = get_fallback_messages()
    message = (
        random.choice(fallbacks)
        if fallbacks
        else "Welcome to Context Foundry. Let's build something great."
    )
    save_motd_cache(message, "fallback")

    return message


def refresh_motd() -> str:
    """Force refresh the MOTD (for daemon/scheduled use)."""
    return get_motd(force_refresh=True)


def format_motd_banner(message: str) -> str:
    """Format MOTD with Context Foundry branding."""
    # Get colored logo
    try:
        from context_foundry.daemon.art import get_lava_lamp_art
        import random

        logo = get_lava_lamp_art(random.randint(0, 359))
    except ImportError:
        logo = """
   ______            __            __
  / ____/___  ____  / /____  _  __/ /_
 / /   / __ \\/ __ \\/ __/ _ \\| |/_/ __/
/ /___/ /_/ / / / / /_/  __/>  </ /_
\\____/\\____/_/ /_/\\__/\\___/_/|_|\\__/
    ______                      __
   / ____/___  __  ______  ____/ /______  __
  / /_  / __ \\/ / / / __ \\/ __  / ___/ / / /
 / __/ / /_/ / /_/ / / / / /_/ / /  / /_/ /
/_/    \\____/\\__,_/_/ /_/\\__,_/_/   \\__, /
                                   /____/
"""

    return f"{logo}\n{message}\n"


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Context Foundry MOTD")
    parser.add_argument("--refresh", action="store_true", help="Force refresh MOTD")
    parser.add_argument("--raw", action="store_true", help="Output raw message only")
    parser.add_argument("--context", action="store_true", help="Show current context")

    args = parser.parse_args()

    if args.context:
        ctx = get_context()
        print(json.dumps(ctx, indent=2))
    elif args.raw:
        print(get_motd(force_refresh=args.refresh))
    else:
        message = get_motd(force_refresh=args.refresh)
        print(format_motd_banner(message))
