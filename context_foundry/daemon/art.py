"""
ASCII Art for Context Foundry Daemon
"""

import time
import math
import random


def get_status_art() -> str:
    """
    Get compact ASCII art for status command
    """
    return r"""
   ______            __            __
  / ____/___  ____  / /____  _  __/ /_
 / /   / __ \/ __ \/ __/ _ \| |/_/ __/
/ /___/ /_/ / / / / /_/  __/>  </ /_
\____/\____/_/ /_/\__/\___/_/|_|\__/
    ______                      __
   / ____/___  __  ______  ____/ /______  __
  / /_  / __ \/ / / / __ \/ __  / ___/ / / /
 / __/ / /_/ / /_/ / / / / /_/ / /  / /_/ /
/_/    \____/\__,_/_/ /_/\__,_/_/   \__, /
                                   /____/
    """


def get_lava_lamp_art(frame: int = 0) -> str:
    """
    Get colorful animated ASCII art with lava lamp effect.

    Args:
        frame: Animation frame number (0-359 for smooth loop)

    Returns:
        Colored ASCII art string
    """
    logo = [
        "   ______            __            __",
        "  / ____/___  ____  / /____  _  __/ /_",
        " / /   / __ \\/ __ \\/ __/ _ \\| |/_/ __/",
        "/ /___/ /_/ / / / / /_/  __/>  </ /_",
        "\\____/\\____/_/ /_/\\__/\\___/_/|_|\\__/",
        "    ______                      __",
        "   / ____/___  __  ______  ____/ /______  __",
        "  / /_  / __ \\/ / / / __ \\/ __  / ___/ / / /",
        " / __/ / /_/ / /_/ / / / / /_/ / /  / /_/ /",
        "/_/    \\____/\\__,_/_/ /_/\\__,_/_/   \\__, /",
        "                                   /____/",
    ]

    # Create lava lamp color palette (warm colors)
    def get_color(offset: float) -> str:
        """Get ANSI color code based on offset (0-1)"""
        # Cycle through warm colors: red -> orange -> yellow -> pink -> red
        hue = (offset * 360) % 360

        if hue < 60:  # Red to Orange
            return "\033[38;5;196m"  # Bright red
        elif hue < 120:  # Orange to Yellow
            return "\033[38;5;208m"  # Orange
        elif hue < 180:  # Yellow to Pink
            return "\033[38;5;226m"  # Yellow
        elif hue < 240:  # Pink to Magenta
            return "\033[38;5;201m"  # Magenta
        elif hue < 300:  # Magenta to Purple
            return "\033[38;5;165m"  # Purple
        else:  # Purple to Red
            return "\033[38;5;196m"  # Back to red

    # Reset color
    reset = "\033[0m"

    # Apply lava lamp effect
    colored_lines = []
    for i, line in enumerate(logo):
        # Create wave effect - each line has different phase
        phase = (frame + i * 30) % 360
        offset = (math.sin(math.radians(phase)) + 1) / 2  # 0-1

        # Add some randomness for "bubbling" effect
        bubble = random.random() * 0.1
        offset = (offset + bubble) % 1.0

        color = get_color(offset)
        colored_lines.append(f"{color}{line}{reset}")

    return "\n".join(colored_lines)


def animate_lava_lamp(duration: float = 5.0, fps: int = 10):
    """
    Display animated lava lamp logo for specified duration.

    Args:
        duration: How long to animate (seconds)
        fps: Frames per second
    """
    import sys

    frames = int(duration * fps)
    frame_delay = 1.0 / fps

    try:
        # Hide cursor
        sys.stdout.write("\033[?25l")
        sys.stdout.flush()

        for frame in range(frames):
            # Clear screen and move to top
            sys.stdout.write("\033[2J\033[H")

            # Draw frame
            art = get_lava_lamp_art(frame * (360 // frames))
            sys.stdout.write(art)
            sys.stdout.flush()

            time.sleep(frame_delay)

    finally:
        # Show cursor
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()
