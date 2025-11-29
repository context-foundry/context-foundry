"""
Conversation Logger for Context Foundry Daemon

Captures and logs structured conversation events from Claude Code agents
using the stream-json output format. This provides full transparency into
what agents are saying and doing.

Usage:
    logger = ConversationLogger(task_id, working_dir)
    async for event in logger.stream_from_process(process):
        # Handle parsed events (tool_use, assistant, etc.)
        print(event)
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Dict, Any, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Types of events emitted by Claude Code stream-json"""

    INIT = "init"
    ASSISTANT = "assistant"
    USER = "user"
    TOOL_USE = "tool_use"
    TOOL_RESULT = "tool_result"
    RESULT = "result"
    ERROR = "error"
    SYSTEM = "system"
    USAGE = "usage"


@dataclass
class ConversationEvent:
    """Represents a single event in the agent's conversation"""

    timestamp: str
    event_type: str
    task_id: str

    # Content varies by event type
    text: Optional[str] = None  # For assistant messages
    tool_name: Optional[str] = None  # For tool_use
    tool_input: Optional[Dict] = None  # For tool_use
    tool_id: Optional[str] = None  # For tool_use/tool_result
    is_error: bool = False
    exit_code: Optional[int] = None  # For result events

    # Token usage
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None

    # Raw event for debugging
    raw: Optional[Dict] = field(default=None, repr=False)

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        d = asdict(self)
        d.pop("raw", None)  # Don't include raw in serialized output
        return {k: v for k, v in d.items() if v is not None}

    def to_log_line(self) -> str:
        """Format as a human-readable log line"""
        ts = self.timestamp.split("T")[1][:12]  # HH:MM:SS.mmm

        if self.event_type == EventType.ASSISTANT:
            text_preview = (self.text or "")[:100]
            if len(self.text or "") > 100:
                text_preview += "..."
            return f"[{ts}] 💬 AGENT: {text_preview}"

        elif self.event_type == EventType.TOOL_USE:
            input_preview = json.dumps(self.tool_input or {})[:80]
            return f"[{ts}] 🔧 TOOL: {self.tool_name}({input_preview})"

        elif self.event_type == EventType.TOOL_RESULT:
            return f"[{ts}] ✅ RESULT: {self.tool_name or self.tool_id}"

        elif self.event_type == EventType.ERROR:
            return f"[{ts}] ❌ ERROR: {self.text}"

        elif self.event_type == EventType.RESULT:
            status = (
                "✅ SUCCESS"
                if self.exit_code == 0
                else f"❌ FAILED (exit {self.exit_code})"
            )
            return f"[{ts}] {status}"

        elif self.event_type == EventType.USAGE:
            return (
                f"[{ts}] 📊 USAGE: +{self.input_tokens} in / +{self.output_tokens} out"
            )

        else:
            return f"[{ts}] {self.event_type.upper()}: {self.text or '(no content)'}"


class ConversationLogger:
    """
    Captures conversation events from Claude Code agents.

    Parses stream-json output and writes events to:
    - A JSONL file for structured access
    - A human-readable log file for quick viewing
    """

    def __init__(
        self,
        task_id: str,
        working_dir: str,
        log_dir: Optional[Path] = None,
    ):
        self.task_id = task_id
        self.working_dir = Path(working_dir)

        # Create logs directory
        if log_dir:
            self.log_dir = Path(log_dir)
        else:
            self.log_dir = self.working_dir / ".context-foundry" / "conversations"
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Log files
        self.jsonl_file = self.log_dir / f"conversation-{task_id}.jsonl"
        self.readable_file = self.log_dir / f"conversation-{task_id}.log"

        # Event buffer for streaming
        self.events: List[ConversationEvent] = []
        self.current_tool_calls: Dict[str, str] = {}  # id -> tool_name

    def parse_event(self, line: str) -> List[ConversationEvent]:
        """Parse a JSON line from stream-json output into one or more events"""
        events = []
        try:
            data = json.loads(line.strip())
            event_type = data.get("type", "unknown")

            # Common fields
            timestamp = datetime.now().isoformat()
            task_id = self.task_id

            # Check for usage in any event and emit separate usage event
            usage = data.get("usage")
            if usage:
                events.append(
                    ConversationEvent(
                        timestamp=timestamp,
                        event_type=EventType.USAGE,
                        task_id=task_id,
                        input_tokens=usage.get("input_tokens"),
                        output_tokens=usage.get("output_tokens"),
                        raw=data,
                    )
                )

            if event_type == "assistant":
                # Extract content blocks
                message = data.get("message", {})
                content = message.get("content", [])

                # Group text blocks to avoid spamming multiple text events
                text_buffer = []

                for block in content:
                    block_type = block.get("type")

                    if block_type == "text":
                        text_buffer.append(block.get("text", ""))

                    elif block_type == "tool_use":
                        # Flush text buffer first
                        if text_buffer:
                            events.append(
                                ConversationEvent(
                                    timestamp=timestamp,
                                    event_type=EventType.ASSISTANT,
                                    task_id=task_id,
                                    text="\n".join(text_buffer),
                                    raw=data,  # Attach raw to first event of the group
                                )
                            )
                            text_buffer = []

                        # Create tool use event
                        tool_id = block.get("id")
                        tool_name = block.get("name")
                        tool_input = block.get("input", {})

                        if tool_id:
                            self.current_tool_calls[tool_id] = tool_name

                        events.append(
                            ConversationEvent(
                                timestamp=timestamp,
                                event_type=EventType.TOOL_USE,
                                task_id=task_id,
                                tool_name=tool_name,
                                tool_input=tool_input,
                                tool_id=tool_id,
                                raw=data,
                            )
                        )

                # Flush remaining text
                if text_buffer:
                    events.append(
                        ConversationEvent(
                            timestamp=timestamp,
                            event_type=EventType.ASSISTANT,
                            task_id=task_id,
                            text="\n".join(text_buffer),
                            raw=data,
                        )
                    )

            elif event_type == "user":
                # Check for tool results
                message = data.get("message", {})
                content = message.get("content", [])

                for block in content:
                    if block.get("type") == "tool_result":
                        tool_id = block.get("tool_use_id")
                        tool_name = self.current_tool_calls.get(tool_id)
                        is_error = block.get("is_error", False)

                        # Extract text content
                        result_content = block.get("content", [])
                        texts = []
                        if isinstance(result_content, list):
                            for c in result_content:
                                if isinstance(c, dict) and c.get("type") == "text":
                                    texts.append(c.get("text", ""))
                                elif isinstance(c, str):
                                    texts.append(c)
                        elif isinstance(result_content, str):
                            texts.append(result_content)

                        events.append(
                            ConversationEvent(
                                timestamp=timestamp,
                                event_type=EventType.TOOL_RESULT,
                                task_id=task_id,
                                tool_id=tool_id,
                                tool_name=tool_name,
                                is_error=is_error,
                                text="\n".join(texts)[:2000],  # Truncate long results
                                raw=data,
                            )
                        )

            elif event_type == "tool_use":
                # Legacy/Top-level tool use
                tool_id = data.get("id")
                tool_name = data.get("name")
                if tool_id:
                    self.current_tool_calls[tool_id] = tool_name

                events.append(
                    ConversationEvent(
                        timestamp=timestamp,
                        event_type=EventType.TOOL_USE,
                        task_id=task_id,
                        tool_name=tool_name,
                        tool_input=data.get("input", {}),
                        tool_id=tool_id,
                        raw=data,
                    )
                )

            elif event_type == "tool_result":
                # Legacy/Top-level tool result
                tool_id = data.get("tool_use_id")
                tool_name = self.current_tool_calls.get(tool_id)

                content = data.get("content", [])
                texts = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        texts.append(block.get("text", ""))
                    elif isinstance(block, str):
                        texts.append(block)

                events.append(
                    ConversationEvent(
                        timestamp=timestamp,
                        event_type=EventType.TOOL_RESULT,
                        task_id=task_id,
                        tool_id=tool_id,
                        tool_name=tool_name,
                        is_error=data.get("is_error", False),
                        text="\n".join(texts)[:2000],
                        raw=data,
                    )
                )

            elif event_type == "result":
                subtype = data.get("subtype", "")
                events.append(
                    ConversationEvent(
                        timestamp=timestamp,
                        event_type=EventType.RESULT,
                        task_id=task_id,
                        text=data.get("result", subtype),
                        exit_code=0 if subtype == "success" else 1,
                        is_error=data.get("is_error", False),
                        raw=data,
                    )
                )

            elif event_type == "error":
                error_info = data.get("error", {})
                events.append(
                    ConversationEvent(
                        timestamp=timestamp,
                        event_type=EventType.ERROR,
                        task_id=task_id,
                        text=error_info.get("message", str(data)),
                        is_error=True,
                        raw=data,
                    )
                )

            elif event_type == "system":
                subtype = data.get("subtype", "")
                events.append(
                    ConversationEvent(
                        timestamp=timestamp,
                        event_type=EventType.SYSTEM,
                        task_id=task_id,
                        text=f"[{subtype}]",
                        raw=data,
                    )
                )

            return events

        except json.JSONDecodeError:
            return []
        except Exception as e:
            logger.warning(f"Failed to parse event: {e}")
            return []

    def log_event(self, event: ConversationEvent):
        """Write event to log files"""
        self.events.append(event)

        # Write to JSONL (machine-readable)
        with open(self.jsonl_file, "a") as f:
            f.write(json.dumps(event.to_dict()) + "\n")

        # Write to readable log
        with open(self.readable_file, "a") as f:
            f.write(event.to_log_line() + "\n")

    async def stream_from_process(
        self,
        process: asyncio.subprocess.Process,
    ) -> AsyncGenerator[ConversationEvent, None]:
        """
        Read stream-json output from a process and yield parsed events.
        """
        if process.stdout is None:
            return

        async for line in process.stdout:
            try:
                line_str = line.decode("utf-8").strip()
                if not line_str:
                    continue

                events = self.parse_event(line_str)
                for event in events:
                    self.log_event(event)
                    yield event

            except Exception as e:
                logger.debug(f"Error processing line: {e}")
                continue

    def stream_from_sync_process(
        self,
        process,  # subprocess.Popen
    ):
        """
        Read stream-json output from a synchronous subprocess.
        """
        if process.stdout is None:
            return

        for line in process.stdout:
            try:
                line_str = (
                    line.strip()
                    if isinstance(line, str)
                    else line.decode("utf-8").strip()
                )
                if not line_str:
                    continue

                events = self.parse_event(line_str)
                for event in events:
                    self.log_event(event)
                    yield event

            except Exception as e:
                logger.debug(f"Error processing line: {e}")
                continue

    def get_events(
        self,
        event_type: Optional[str] = None,
        last_n: Optional[int] = None,
    ) -> List[ConversationEvent]:
        """
        Get logged events with optional filtering.

        Args:
            event_type: Filter by event type (e.g., "tool_use", "assistant")
            last_n: Return only the last N events
        """
        events = self.events

        if event_type:
            events = [e for e in events if e.event_type == event_type]

        if last_n:
            events = events[-last_n:]

        return events

    def get_tool_calls(self) -> List[ConversationEvent]:
        """Get all tool use events"""
        return self.get_events(event_type="tool_use")

    def get_conversation_text(self) -> str:
        """Get human-readable conversation transcript"""
        return "\n".join(e.to_log_line() for e in self.events)

    @classmethod
    def load_from_file(cls, jsonl_path: Path) -> "ConversationLogger":
        """Load a conversation logger from an existing JSONL file"""
        task_id = jsonl_path.stem.replace("conversation-", "")
        logger_instance = cls(task_id, jsonl_path.parent.parent.parent)

        if jsonl_path.exists():
            with open(jsonl_path) as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        event = ConversationEvent(**data)
                        logger_instance.events.append(event)
                    except Exception:
                        continue

        return logger_instance


def get_conversation_logs_dir(working_dir: str) -> Path:
    """Get the conversation logs directory for a project"""
    return Path(working_dir) / ".context-foundry" / "conversations"


def list_conversations(working_dir: str) -> List[Dict[str, Any]]:
    """List all conversations for a project"""
    logs_dir = get_conversation_logs_dir(working_dir)
    if not logs_dir.exists():
        return []

    conversations = []
    for jsonl_file in logs_dir.glob("conversation-*.jsonl"):
        task_id = jsonl_file.stem.replace("conversation-", "")
        stat = jsonl_file.stat()

        # Count events
        event_count = 0
        with open(jsonl_file) as f:
            for _ in f:
                event_count += 1

        conversations.append(
            {
                "task_id": task_id,
                "jsonl_file": str(jsonl_file),
                "readable_file": str(jsonl_file.with_suffix(".log")),
                "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "event_count": event_count,
            }
        )

    return sorted(conversations, key=lambda x: x["modified"], reverse=True)


def tail_conversation(
    working_dir: str,
    task_id: str,
    lines: int = 50,
    follow: bool = False,
) -> str:
    """
    Tail a conversation log file.

    Args:
        working_dir: Project working directory
        task_id: Task ID to tail
        lines: Number of lines to show
        follow: If True, keep watching for new lines

    Returns:
        Last N lines of the readable log
    """
    logs_dir = get_conversation_logs_dir(working_dir)
    log_file = logs_dir / f"conversation-{task_id}.log"

    if not log_file.exists():
        return f"No conversation log found for task {task_id}"

    with open(log_file) as f:
        all_lines = f.readlines()

    return "".join(all_lines[-lines:])
