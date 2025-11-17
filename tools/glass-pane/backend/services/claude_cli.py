"""
Claude CLI Proxy Service

Manages spawning Claude CLI processes, parsing stream-json output,
and handling subprocess lifecycle for the Forge chat interface.
"""

import asyncio
import json
import logging
import shutil
from pathlib import Path
from typing import AsyncGenerator, Optional, Dict, List, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ClaudeMessage:
    """Represents a message in the conversation."""

    role: str  # 'user' | 'assistant' | 'system'
    content: str


@dataclass
class ClaudeConfig:
    """Configuration for Claude CLI execution."""

    model: str = "sonnet"  # sonnet | opus | haiku
    plan_mode: bool = False
    bypass_permissions: bool = False
    timeout: int = 60  # seconds


class ClaudeCLIError(Exception):
    """Raised when Claude CLI encounters an error."""

    pass


class ClaudeCLIService:
    """
    Service for proxying requests to Claude Code CLI.

    Spawns subprocess, parses stream-json output, and yields
    streaming responses for real-time UI updates.
    """

    def __init__(self):
        """Initialize Claude CLI service."""
        self.claude_path = self._find_claude_binary()
        if not self.claude_path:
            logger.warning("Claude CLI not found in PATH")

    def _find_claude_binary(self) -> Optional[Path]:
        """
        Find Claude CLI binary in common installation paths.

        Returns:
            Path to claude binary, or None if not found
        """
        # Try shutil.which first (checks PATH)
        cli_path = shutil.which("claude")
        if cli_path:
            return Path(cli_path)

        # Try common installation paths
        common_paths = [
            Path("/opt/homebrew/bin/claude"),
            Path("/usr/local/bin/claude"),
            Path.home() / ".local" / "bin" / "claude",
        ]

        for path in common_paths:
            if path.exists() and path.is_file():
                return path

        return None

    def _build_command(
        self, messages: List[ClaudeMessage], config: ClaudeConfig
    ) -> List[str]:
        """
        Build Claude CLI command with arguments.

        Args:
            messages: Conversation history
            config: CLI configuration

        Returns:
            Command as list of strings
        """
        if not self.claude_path:
            raise ClaudeCLIError("Claude CLI not found - please install Claude Code")

        cmd = [
            str(self.claude_path),
            "--print",
            "--output-format",
            "stream-json",
            "--model",
            config.model,
            "--verbose",
        ]

        # Add optional flags
        if config.bypass_permissions:
            cmd.append("--dangerously-skip-permissions")

        if config.plan_mode:
            cmd.append("--plan-mode")

        return cmd

    def _format_prompt(self, messages: List[ClaudeMessage]) -> str:
        """
        Format message history into Claude CLI prompt format.

        Args:
            messages: List of conversation messages

        Returns:
            Formatted prompt string
        """
        # Simple format: just join all user/assistant messages
        # Claude CLI will handle the conversation context
        prompt_parts = []

        for msg in messages:
            if msg.role == "user":
                prompt_parts.append(f"{msg.content}")
            elif msg.role == "assistant":
                # Include previous assistant responses for context
                prompt_parts.append(f"Assistant: {msg.content}")

        return "\n\n".join(prompt_parts)

    async def chat_stream(
        self, messages: List[ClaudeMessage], config: ClaudeConfig
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Send messages to Claude CLI and stream responses.

        Args:
            messages: Conversation history
            config: CLI configuration

        Yields:
            Dict containing streaming events:
            - {"type": "delta", "text": "..."}
            - {"type": "complete", "text": "..."}
            - {"type": "error", "message": "..."}
        """
        if not self.claude_path:
            yield {"type": "error", "message": "Claude CLI not installed"}
            return

        cmd = self._build_command(messages, config)
        prompt = self._format_prompt(messages)

        logger.info(f"Starting Claude CLI: {' '.join(cmd[:5])}...")

        try:
            # Start subprocess
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Write prompt to stdin
            if process.stdin:
                process.stdin.write(prompt.encode("utf-8"))
                await process.stdin.drain()
                process.stdin.close()

            # Track accumulated response
            full_response = []

            # Read stdout line by line
            if process.stdout:
                async for line in process.stdout:
                    try:
                        line_str = line.decode("utf-8").strip()
                        if not line_str:
                            continue

                        # Parse JSON event
                        event = json.loads(line_str)
                        event_type = event.get("type", "")

                        # Handle Claude Code CLI JSON format
                        if event_type == "assistant":
                            # {"type":"assistant","message":{"content":[{"type":"text","text":"..."}],...}}
                            message = event.get("message", {})
                            content = message.get("content", [])

                            # Extract text from content blocks
                            for block in content:
                                if block.get("type") == "text":
                                    text = block.get("text", "")
                                    if text:
                                        full_response.append(text)
                                        # Yield delta for streaming
                                        yield {"type": "delta", "text": text}

                        elif event_type == "result":
                            # {"type":"result","subtype":"success",...}
                            # Message complete
                            complete_text = "".join(full_response)
                            if complete_text:
                                yield {"type": "complete", "text": complete_text}

                            # Check for errors in result
                            if event.get("is_error") or event.get("subtype") == "error":
                                error_msg = event.get("result", "Unknown error")
                                yield {"type": "error", "message": error_msg}

                        elif event_type == "system":
                            # {"type":"system","subtype":"init",...} - ignore for now
                            pass

                        elif event_type == "error":
                            error_msg = event.get("error", {}).get(
                                "message", "Unknown error"
                            )
                            yield {"type": "error", "message": error_msg}

                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse JSON line: {line_str[:100]}")
                        continue

                    except Exception as e:
                        logger.error(f"Error processing stream event: {e}")
                        continue

            # Wait for process to complete with timeout
            try:
                await asyncio.wait_for(process.wait(), timeout=config.timeout)
            except asyncio.TimeoutError:
                logger.warning(
                    f"Claude CLI timeout after {config.timeout}s, terminating..."
                )
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=5)
                except asyncio.TimeoutError:
                    process.kill()
                yield {
                    "type": "error",
                    "message": f"Request timed out after {config.timeout}s",
                }

            # Check exit code
            if process.returncode and process.returncode != 0:
                stderr = ""
                if process.stderr:
                    stderr_bytes = await process.stderr.read()
                    stderr = stderr_bytes.decode("utf-8")

                logger.error(
                    f"Claude CLI exited with code {process.returncode}: {stderr}"
                )
                yield {
                    "type": "error",
                    "message": f"Claude CLI error (exit code {process.returncode})",
                }

        except Exception as e:
            logger.error(f"Claude CLI execution error: {e}", exc_info=True)
            yield {"type": "error", "message": str(e)}

    async def check_availability(self) -> Dict[str, Any]:
        """
        Check if Claude CLI is available and working.

        Returns:
            Status dict with availability and version info
        """
        if not self.claude_path:
            return {"available": False, "error": "Claude CLI not found in PATH"}

        try:
            # Try to get version
            result = await asyncio.create_subprocess_exec(
                str(self.claude_path),
                "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(result.communicate(), timeout=5)

            version = stdout.decode("utf-8").strip() or stderr.decode("utf-8").strip()

            return {
                "available": True,
                "path": str(self.claude_path),
                "version": version,
            }

        except Exception as e:
            return {"available": False, "error": str(e)}
