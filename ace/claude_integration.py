#!/usr/bin/env python3
"""
Claude API Integration for Context Foundry
Handles all interactions with Anthropic's Claude API or CLI
"""

import os
import json
import time
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Union
import anthropic
from anthropic import Anthropic, APIError, RateLimitError

# Import context management components
from ace.context_manager import ContextManager
from ace.compactors.smart_compactor import SmartCompactor


def get_claude_client(
    log_dir: Optional[Path] = None,
    session_id: Optional[str] = None,
    use_context_manager: bool = True,
    prefer_mcp: bool = None
) -> Union['ClaudeClient', 'ClaudeCodeClient']:
    """
    Factory function to get appropriate Claude client (API or MCP).

    Args:
        log_dir: Directory for logs
        session_id: Session identifier
        use_context_manager: Enable context management
        prefer_mcp: If True, use MCP mode. If None, auto-detect from env

    Returns:
        ClaudeClient (API mode) or ClaudeCodeClient (MCP mode) instance
    """
    # Import here to avoid circular dependency
    from ace.claude_code_client import ClaudeCodeClient

    # Check if running in MCP mode
    if prefer_mcp is None:
        prefer_mcp = os.getenv('CONTEXT_FOUNDRY_MCP_MODE', '').lower() in ('true', '1', 'yes')

    # If MCP mode requested, use ClaudeCodeClient
    if prefer_mcp:
        print("🔧 Using MCP Mode (Claude Desktop integration)")
        print("💰 No API charges - using your Claude subscription")
        return ClaudeCodeClient(log_dir, session_id, use_context_manager)

    # Otherwise, use API mode
    api_key = os.getenv('ANTHROPIC_API_KEY', '').strip()
    if not api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY environment variable not set.\n"
            "Options:\n"
            "1. Set ANTHROPIC_API_KEY=your_key (API mode - charges apply)\n"
            "2. Use MCP mode through Claude Desktop (no charges - see docs)\n"
            "Get API key from: https://console.anthropic.com/"
        )

    print("🔧 Using Anthropic API for authentication")
    print("💰 API charges apply - see https://www.anthropic.com/pricing")
    return ClaudeClient(log_dir, session_id, use_context_manager)


class ClaudeClient:
    """
    Client for interacting with Claude API with context management.
    Tracks token usage, implements retries, and auto-compacts context.
    """

    def __init__(self, log_dir: Optional[Path] = None, session_id: Optional[str] = None, use_context_manager: bool = True):
        """Initialize Claude client.

        Args:
            log_dir: Directory for logs
            session_id: Session identifier for context management
            use_context_manager: Enable intelligent context management
        """
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY environment variable not set. "
                "Get your API key from https://console.anthropic.com/"
            )

        self.client = Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-20250514"  # Latest Sonnet
        self.max_tokens = 8000
        self.conversation_history: List[Dict] = []
        self.total_input_tokens = 0
        self.total_output_tokens = 0

        # Logging
        self.log_dir = log_dir or Path("logs") / datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.session_log = self.log_dir / "session.jsonl"

        # Context management
        self.use_context_manager = use_context_manager
        self.session_id = session_id or f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        if self.use_context_manager:
            self.context_manager = ContextManager(self.session_id)
            self.smart_compactor = SmartCompactor()
        else:
            self.context_manager = None
            self.smart_compactor = None

    def call_claude(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_retries: int = 3,
        reset_context: bool = False,
        content_type: str = "general",
    ) -> Tuple[str, Dict]:
        """
        Call Claude with automatic retries and context management.

        Args:
            prompt: User prompt to send to Claude
            system_prompt: Optional system prompt
            max_retries: Number of retry attempts
            reset_context: If True, start fresh conversation
            content_type: Type of content ('decision', 'pattern', 'error', 'code', 'general')

        Returns:
            Tuple of (response_text, metadata)
        """
        if reset_context:
            self.reset_context()

        # Check if we need to compact BEFORE the call
        if self.use_context_manager:
            should_compact, reason = self.context_manager.should_compact()
            if should_compact:
                print(f"🔄 Auto-compacting context: {reason}")
                compaction_result = self.context_manager.compact(self.smart_compactor)
                if compaction_result["compacted"]:
                    print(f"   ✅ Compacted: {compaction_result['reduction_pct']:.1f}% reduction")
                    print(f"   📊 {compaction_result['before_tokens']:,} → {compaction_result['after_tokens']:,} tokens")

                    # Rebuild conversation history from compacted content
                    self.conversation_history = [
                        {"role": item.role, "content": item.content}
                        for item in self.context_manager.tracked_content
                    ]

        # Build messages
        messages = self.conversation_history + [{"role": "user", "content": prompt}]

        # Retry logic with exponential backoff
        for attempt in range(max_retries):
            try:
                # Call Claude API
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    system=system_prompt or "",
                    messages=messages,
                )

                # Extract response
                response_text = response.content[0].text

                # Track tokens
                input_tokens = response.usage.input_tokens
                output_tokens = response.usage.output_tokens
                self.total_input_tokens += input_tokens
                self.total_output_tokens += output_tokens

                # Update conversation history
                self.conversation_history.append({"role": "user", "content": prompt})
                self.conversation_history.append(
                    {"role": "assistant", "content": response_text}
                )

                # Track with context manager
                if self.use_context_manager:
                    metrics = self.context_manager.track_interaction(
                        prompt, response_text, input_tokens, output_tokens, content_type
                    )
                    context_pct = metrics.context_percentage
                else:
                    context_pct = self.calculate_context_percentage(input_tokens)

                # Metadata
                metadata = {
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_input": self.total_input_tokens,
                    "total_output": self.total_output_tokens,
                    "context_percentage": context_pct,
                    "model": self.model,
                    "timestamp": datetime.now().isoformat(),
                }

                # Add context manager insights
                if self.use_context_manager:
                    insights = self.context_manager.get_insights()
                    metadata["context_health"] = insights["health"]
                    metadata["compaction_count"] = insights["compaction_stats"]["count"]

                # Log the interaction
                self._log_interaction(prompt, response_text, metadata)

                # Check if we need to compact (warning only, actual compaction happens at start)
                if context_pct > 50:
                    print(f"⚠️  Context at {context_pct:.1f}% - will compact before next call")

                return response_text, metadata

            except RateLimitError as e:
                wait_time = 2**attempt  # Exponential backoff
                print(f"⏳ Rate limit hit. Waiting {wait_time}s... (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)

            except APIError as e:
                print(f"❌ API Error: {e}")
                if attempt == max_retries - 1:
                    raise
                time.sleep(2**attempt)

        raise Exception(f"Failed after {max_retries} retries")

    def calculate_context_percentage(self, current_tokens: int) -> int:
        """
        Calculate context window usage percentage.
        Claude Sonnet 4 has 200K token context window.
        """
        context_window = 200000
        return int((current_tokens / context_window) * 100)

    def compact_context(self, keep_recent: int = 2) -> str:
        """
        Compact conversation history by summarizing older messages.

        Args:
            keep_recent: Number of recent message pairs to keep

        Returns:
            Summary of compacted context
        """
        if len(self.conversation_history) <= keep_recent * 2:
            return "No compaction needed - conversation is short"

        # Keep recent messages
        recent_messages = self.conversation_history[-(keep_recent * 2) :]

        # Summarize the rest
        old_messages = self.conversation_history[: -(keep_recent * 2)]

        # Create summarization prompt
        conversation_text = "\n\n".join(
            [f"{msg['role']}: {msg['content']}" for msg in old_messages]
        )

        summary_prompt = f"""Summarize this conversation history in 500 tokens or less, preserving key decisions and context:

{conversation_text}

Provide a concise summary that captures the essential information."""

        # Get summary (with fresh context to avoid recursion)
        old_history = self.conversation_history
        self.conversation_history = []

        summary, _ = self.call_claude(summary_prompt, reset_context=True)

        # Update history: summary + recent messages
        self.conversation_history = [
            {"role": "user", "content": "Previous conversation summary:"},
            {"role": "assistant", "content": summary},
        ] + recent_messages

        print(f"✅ Context compacted: {len(old_history)} → {len(self.conversation_history)} messages")

        return summary

    def reset_context(self):
        """Reset conversation history (fresh start)."""
        self.conversation_history = []
        print("🔄 Context reset - starting fresh conversation")

    def get_context_stats(self) -> Dict:
        """Get current context statistics."""
        stats = {
            "messages": len(self.conversation_history),
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "context_percentage": self.calculate_context_percentage(
                self.total_input_tokens
            ),
        }

        # Add context manager insights if available
        if self.use_context_manager and self.context_manager:
            insights = self.context_manager.get_insights()
            stats["context_health"] = insights["health"]
            stats["compaction_stats"] = insights["compaction_stats"]
            stats["content_breakdown"] = insights["content_breakdown"]

        return stats

    def _log_interaction(self, prompt: str, response: str, metadata: Dict):
        """Log interaction to JSONL file."""
        log_entry = {
            "timestamp": metadata["timestamp"],
            "prompt": prompt[:500] + "..." if len(prompt) > 500 else prompt,
            "response": response[:500] + "..." if len(response) > 500 else response,
            "metadata": metadata,
        }

        with open(self.session_log, "a") as f:
            f.write(json.dumps(log_entry) + "\n")

    def save_full_conversation(self, filepath: Path):
        """Save complete conversation history to file."""
        conversation_data = {
            "timestamp": datetime.now().isoformat(),
            "model": self.model,
            "statistics": self.get_context_stats(),
            "conversation": self.conversation_history,
        }

        with open(filepath, "w") as f:
            json.dump(conversation_data, f, indent=2)

        print(f"💾 Conversation saved to {filepath}")


def test_claude_client():
    """Test the Claude client with a simple interaction."""
    print("🧪 Testing Claude API Integration")
    print("=" * 60)

    try:
        client = ClaudeClient()

        # Test basic call
        print("\n1. Testing basic API call...")
        response, metadata = client.call_claude(
            "Say 'Hello from Context Foundry!' and nothing else."
        )
        print(f"Response: {response}")
        print(f"Tokens: {metadata['input_tokens']} in, {metadata['output_tokens']} out")
        print(f"Context: {metadata['context_percentage']}%")

        # Test context tracking
        print("\n2. Testing context tracking...")
        stats = client.get_context_stats()
        print(f"Total messages: {stats['messages']}")
        print(f"Total tokens: {stats['total_tokens']}")

        # Test context reset
        print("\n3. Testing context reset...")
        client.reset_context()
        stats = client.get_context_stats()
        print(f"Messages after reset: {stats['messages']}")

        print("\n✅ All tests passed!")
        print(f"📂 Logs saved to: {client.log_dir}")

        return True

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        return False


if __name__ == "__main__":
    test_claude_client()
