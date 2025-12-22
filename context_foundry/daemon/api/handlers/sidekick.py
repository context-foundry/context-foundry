"""
Sidekick chat API handler.

Handles the sidekick chat interface that uses Claude CLI for responses.
"""

import json
import logging
import os
import platform
import shutil
import subprocess
from typing import Optional

from .base import HandlerMixin

logger = logging.getLogger(__name__)


class SidekickHandlersMixin(HandlerMixin):
    """Mixin providing sidekick chat handler methods."""

    # Reference to rfile for reading request body
    rfile: any

    def handle_sidekick_chat(self) -> None:
        """Handle chat messages for the sidekick interface using Claude CLI."""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body_raw = self.rfile.read(content_length)
            data = json.loads(body_raw.decode("utf-8"))
            message = data.get("message", "").strip()

            logger.info(f"Sidekick received message: {message[:50]}...")

            if not message:
                self.send_json_error(400, "Empty message")
                return

            # Try to use Claude CLI for response
            response_text = self._get_claude_response(message)

            if not response_text:
                response_text = (
                    "I'm having trouble connecting right now. Please try again."
                )

            self.send_json_response({"response": response_text})

        except Exception as exc:
            logger.error("Error in sidekick chat: %s", exc, exc_info=True)
            self.send_json_error(500, str(exc))

    def _get_claude_response(self, message: str) -> Optional[str]:
        """Get a response from Claude CLI."""
        claude_path = self._find_claude_cli()
        if not claude_path:
            logger.warning("Claude CLI not found")
            return None

        try:
            simple_prompt = (
                f"You are a helpful assistant. Respond briefly to: {message}"
            )
            logger.info("Sidekick: Running Claude subprocess...")

            env = self._get_subprocess_env()

            result = subprocess.run(
                [
                    claude_path,
                    "-p",
                    "--print",
                    "--dangerously-skip-permissions",
                    "--model",
                    "haiku",
                ],
                input=simple_prompt,
                capture_output=True,
                text=True,
                timeout=90,
                env=env,
            )

            logger.info(f"Sidekick: Claude returned code {result.returncode}")

            if result.returncode == 0 and result.stdout:
                response_text = result.stdout.strip()
                logger.info(f"Sidekick: Got response of {len(response_text)} chars")
                return response_text
            else:
                logger.warning(
                    f"Sidekick: Claude failed - stderr: {result.stderr[:200] if result.stderr else 'none'}"
                )
                return None

        except subprocess.TimeoutExpired:
            logger.warning("Sidekick: Claude timed out after 90s")
            return None
        except Exception as e:
            logger.warning(f"Sidekick: Claude error - {e}")
            return None

    def _find_claude_cli(self) -> Optional[str]:
        """Find the Claude CLI executable."""
        claude_path = shutil.which("claude")
        if not claude_path and os.path.exists("/opt/homebrew/bin/claude"):
            claude_path = "/opt/homebrew/bin/claude"
        return claude_path

    def _get_subprocess_env(self) -> dict:
        """Get environment variables for subprocess with proper PATH."""
        env = os.environ.copy()

        if platform.system() == "Windows":
            programfiles = os.environ.get("ProgramFiles", r"C:\Program Files")
            appdata = os.environ.get("APPDATA", "")
            extra_paths = (
                f"{programfiles}\\nodejs;{appdata}\\npm"
                if appdata
                else f"{programfiles}\\nodejs"
            )
            env["PATH"] = f"{extra_paths};{env.get('PATH', '')}"
        else:
            # macOS/Linux: add homebrew and common locations
            env["PATH"] = (
                f"/opt/homebrew/bin:/usr/local/bin:{env.get('PATH', '/usr/bin:/bin')}"
            )

        return env
