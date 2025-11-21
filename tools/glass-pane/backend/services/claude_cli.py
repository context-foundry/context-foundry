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

from services.mcp_executor import MCPExecutor

logger = logging.getLogger(__name__)

# Path to Forge system prompt
FORGE_SYSTEM_PROMPT_PATH = (
    Path(__file__).parent.parent / "prompts" / "forge_system_prompt.md"
)


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
        self.system_prompt = self._load_system_prompt()
        self.mcp_executor = MCPExecutor()

    def _load_system_prompt(self) -> str:
        """
        Load Forge system prompt from file.

        Returns:
            System prompt content, or empty string if file not found
        """
        try:
            if FORGE_SYSTEM_PROMPT_PATH.exists():
                return FORGE_SYSTEM_PROMPT_PATH.read_text()
            else:
                logger.warning(f"System prompt not found at {FORGE_SYSTEM_PROMPT_PATH}")
                return ""
        except Exception as e:
            logger.error(f"Error loading system prompt: {e}")
            return ""

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

        # Path to MCP config for Context Foundry
        mcp_config_path = Path(__file__).parent.parent / "mcp_config.json"

        cmd = [
            str(self.claude_path),
            "--print",
            "--output-format",
            "stream-json",
            "--model",
            config.model,
            "--verbose",
        ]

        # Add MCP config to load Context Foundry tools
        if mcp_config_path.exists():
            cmd.extend(["--mcp-config", str(mcp_config_path)])
            logger.info(f"Loading MCP config from: {mcp_config_path}")
        else:
            logger.warning(f"MCP config not found at: {mcp_config_path}")

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
            messages: List of conversation messages (including system message if present)

        Returns:
            Formatted prompt string
        """
        # Build prompt with system message first (if provided)
        prompt_parts = []

        # Separate system message from user/assistant messages
        system_msg = None
        conversation_msgs = []

        for msg in messages:
            if msg.role == "system":
                system_msg = msg.content
            else:
                conversation_msgs.append(msg)

        # Add system prompt if we have one
        if system_msg:
            prompt_parts.append(f"<system>\n{system_msg}\n</system>")

        # Add conversation history
        for msg in conversation_msgs:
            if msg.role == "user":
                prompt_parts.append(f"{msg.content}")
            elif msg.role == "assistant":
                # Include previous assistant responses for context
                prompt_parts.append(f"Assistant: {msg.content}")

        return "\n\n".join(prompt_parts)

    async def chat_stream(
        self,
        messages: List[ClaudeMessage],
        config: ClaudeConfig,
        cwd: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Send messages to Claude CLI and stream responses.

        Args:
            messages: Conversation history
            config: CLI configuration
            cwd: Optional working directory for CLI execution

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
        if cwd:
            logger.info(f"Working directory: {cwd}")

        try:
            # Start subprocess with optional working directory
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,  # Pass working directory to subprocess
            )

            logger.info(f"📝 Writing prompt to Claude CLI stdin ({len(prompt)} bytes)")
            logger.debug(f"📝 Prompt content: {prompt[:200]}...")

            # Write prompt to stdin
            if process.stdin:
                process.stdin.write(prompt.encode("utf-8"))
                await process.stdin.drain()
                # Close stdin to signal end of user input - Claude CLI needs this!
                process.stdin.close()
                logger.info(
                    "✅ Stdin written and closed, waiting for Claude response..."
                )

            # Track accumulated response and tool use
            full_response = []

            logger.info("📖 Reading Claude CLI output...")

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

                        # Log every event for debugging
                        logger.debug(f"CLI event type: {event_type}")
                        # Log full event (truncated to avoid massive logs)
                        event_json = json.dumps(event)
                        if len(event_json) > 500:
                            logger.debug(
                                f"CLI event data: {event_json[:500]}... (truncated)"
                            )
                        else:
                            logger.debug(f"CLI event data: {event_json}")

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

                        elif event_type == "tool_use":
                            # Tool invocation request from Claude
                            tool_name = event.get("name", "unknown")
                            tool_input = event.get("input", {})
                            tool_id = event.get("id", "unknown")
                            logger.info(
                                f"🔧 Claude requested tool: {tool_name} (id: {tool_id})"
                            )
                            logger.debug(
                                f"🔧 Tool input: {json.dumps(tool_input, indent=2)[:500]}"
                            )

                            # Execute the tool via MCP executor
                            try:
                                tool_result = self.mcp_executor.execute(
                                    tool_name, tool_input
                                )
                                logger.info(
                                    f"✅ Tool {tool_name} executed successfully"
                                )

                                # Send tool_result back to Claude
                                tool_result_event = {
                                    "type": "tool_result",
                                    "tool_use_id": tool_id,
                                    "content": tool_result.get("content", []),
                                    "is_error": tool_result.get("is_error", False),
                                }

                                # Write to stdin to continue conversation
                                if process.stdin:
                                    result_json = json.dumps(tool_result_event) + "\n"
                                    process.stdin.write(result_json.encode("utf-8"))
                                    await process.stdin.drain()
                                    logger.debug(
                                        f"📤 Sent tool_result to Claude: {tool_id}"
                                    )

                            except Exception as e:
                                logger.error(
                                    f"❌ Tool execution failed: {e}", exc_info=True
                                )
                                # Send error result to Claude
                                error_result = {
                                    "type": "tool_result",
                                    "tool_use_id": tool_id,
                                    "content": [
                                        {
                                            "type": "text",
                                            "text": f"Tool execution error: {str(e)}",
                                        }
                                    ],
                                    "is_error": True,
                                }
                                if process.stdin:
                                    error_json = json.dumps(error_result) + "\n"
                                    process.stdin.write(error_json.encode("utf-8"))
                                    await process.stdin.drain()

                        elif event_type == "tool_result":
                            # Tool execution result echoed back by Claude
                            tool_id = event.get("tool_use_id", "unknown")
                            logger.debug(f"Received tool_result echo for: {tool_id}")

                        elif event_type == "system":
                            # {"type":"system","subtype":"init",...} - ignore for now
                            pass

                        elif event_type == "error":
                            error_msg = event.get("error", {}).get(
                                "message", "Unknown error"
                            )
                            yield {"type": "error", "message": error_msg}

                        else:
                            # Unknown event type
                            logger.warning(f"❓ Unknown event type: {event_type}")

                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse JSON line: {line_str[:100]}")
                        continue

                    except Exception as e:
                        logger.error(f"Error processing stream event: {e}")
                        continue

            # Close stdin now that conversation is complete
            if process.stdin and not process.stdin.is_closing():
                process.stdin.close()
                logger.debug("Closed stdin after conversation complete")

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
            else:
                # Also log stderr even on success to see MCP server errors
                if process.stderr:
                    stderr_bytes = await process.stderr.read()
                    stderr = stderr_bytes.decode("utf-8")
                    if stderr.strip():
                        logger.warning(f"Claude CLI stderr output:\n{stderr[:1000]}")

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
