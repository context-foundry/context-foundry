#!/usr/bin/env python3
"""
Claude Code Client for Context Foundry
Sends prompts to Claude Desktop/Code via MCP instead of calling Anthropic API
This allows Context Foundry to work without API charges when used through MCP
"""

import os
import json
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Any

# Import context management components
from ace.context_manager import ContextManager
from ace.compactors.smart_compactor import SmartCompactor

# Try to import nest_asyncio for nested event loop support
try:
    import nest_asyncio
    nest_asyncio.apply()
    NEST_ASYNCIO_AVAILABLE = True
except ImportError:
    NEST_ASYNCIO_AVAILABLE = False


class ClaudeCodeClient:
    """
    Client for interacting with Claude via MCP (Model Context Protocol).
    Provides same interface as ClaudeClient but doesn't make API calls.
    Instead, returns prompts to be processed by Claude Desktop/Code.
    """

    def __init__(self, log_dir: Optional[Path] = None, session_id: Optional[str] = None, use_context_manager: bool = True, ctx: Optional[Any] = None):
        """Initialize Claude Code client.

        Args:
            log_dir: Directory for logs
            session_id: Session identifier for context management
            use_context_manager: Enable intelligent context management
            ctx: FastMCP Context object for MCP sampling (required for MCP mode)
        """
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

        # Disable context manager in MCP mode for now
        # SmartCompactor requires API key which we don't have in MCP mode
        # TODO: Implement MCP-compatible compactor that uses ctx.sample() instead
        if self.use_context_manager:
            print("⚠️  Context management disabled in MCP mode (SmartCompactor requires API key)")
            self.context_manager = None
            self.smart_compactor = None
            self.use_context_manager = False  # Force disable
        else:
            self.context_manager = None
            self.smart_compactor = None

        # MCP Context for sampling
        self.ctx = ctx
        if ctx is None:
            raise ValueError(
                "ClaudeCodeClient requires a FastMCP Context object (ctx parameter). "
                "This client should only be instantiated from within an MCP tool function."
            )

        # MCP mode indicator
        self.mcp_mode = True
        print("🔧 Using MCP Mode - prompts will be processed by Claude Desktop")
        print("💰 Uses your Claude subscription (no per-token API charges)")

    def call_claude(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_retries: int = 3,
        reset_context: bool = False,
        content_type: str = "general",
    ) -> Tuple[str, Dict]:
        """
        Send prompt to Claude Desktop via MCP sampling.

        In MCP mode, this method:
        1. Constructs the full prompt with context
        2. Returns it to the MCP server
        3. MCP server asks Claude Desktop to process it
        4. Response comes back through MCP

        Note: This is a simplified implementation. In practice, the MCP
        server handles the prompt/response flow using mcp.sampling.

        Args:
            prompt: User prompt to send to Claude
            system_prompt: Optional system prompt
            max_retries: Number of retry attempts (not used in MCP mode)
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

        # Use MCP sampling to get response from Claude Desktop
        try:
            # Call async sampling - handle event loop properly
            response_text = self._call_sampling_sync(prompt, system_prompt)
        except Exception as e:
            raise RuntimeError(f"MCP sampling failed: {e}") from e

        # Estimate tokens (approximation: ~4 chars per token)
        input_tokens = len(prompt) // 4 + len(system_prompt or "") // 4
        output_tokens = len(response_text) // 4
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens

        # Update conversation history
        self.conversation_history.append({"role": "user", "content": prompt})
        self.conversation_history.append({"role": "assistant", "content": response_text})

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
            "model": "claude-via-mcp",
            "timestamp": datetime.now().isoformat(),
            "mcp_mode": True,
        }

        # Add context manager insights
        if self.use_context_manager:
            insights = self.context_manager.get_insights()
            metadata["context_health"] = insights["health"]
            metadata["compaction_count"] = insights["compaction_stats"]["count"]

        # Log the interaction
        self._log_interaction(prompt, response_text, metadata)

        # Check if we need to compact
        if context_pct > 50:
            print(f"⚠️  Context at {context_pct:.1f}% - will compact before next call")

        return response_text, metadata

    def _call_sampling_sync(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        Call MCP sampling, handling async/sync boundary.

        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt

        Returns:
            Response text from Claude Desktop
        """
        # Build messages - handle conversation history properly
        messages = []

        # Add conversation history as context
        for msg in self.conversation_history:
            role = msg['role']
            content = msg['content']
            if role == 'user':
                messages.append(f"[Previous] User: {content[:500]}")  # Truncate for context
            elif role == 'assistant':
                messages.append(f"[Previous] Assistant: {content[:500]}")

        # Add current prompt
        messages.append(prompt)

        # Combine into single prompt string
        full_prompt = "\n\n".join(messages)

        # Call async sampling in sync context
        try:
            # Try to get the event loop
            try:
                loop = asyncio.get_running_loop()
                # Loop is running - we're in an async context
                if NEST_ASYNCIO_AVAILABLE:
                    # nest_asyncio allows nested event loops
                    result = asyncio.run(self._do_sampling(full_prompt, system_prompt))
                    return result
                else:
                    # Without nest_asyncio, we can't easily handle this
                    # Try using run_until_complete anyway (will fail but with clear error)
                    raise RuntimeError(
                        "Calling sync method from async context requires nest_asyncio. "
                        "Install with: pip install nest-asyncio"
                    )
            except RuntimeError:
                # No running loop - we can create one
                result = asyncio.run(self._do_sampling(full_prompt, system_prompt))
                return result
        except Exception as e:
            raise RuntimeError(f"Failed to execute MCP sampling: {e}") from e

    async def _do_sampling(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        Perform the actual MCP sampling call.

        Args:
            prompt: The complete prompt to send
            system_prompt: Optional system prompt

        Returns:
            Response text
        """
        # Call FastMCP sampling
        response = await self.ctx.sample(
            messages=prompt,
            system_prompt=system_prompt,
            temperature=0.7,
            max_tokens=self.max_tokens
        )

        # Extract text from response
        # Response should be TextContent or ImageContent with a .text attribute
        if hasattr(response, 'text'):
            return response.text
        elif isinstance(response, str):
            return response
        else:
            raise ValueError(f"Unexpected response type from MCP sampling: {type(response)}")

    def _build_prompt_with_history(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Build prompt including conversation history."""
        parts = []

        if system_prompt:
            parts.append(f"<system>\n{system_prompt}\n</system>\n")

        # Add conversation history
        for msg in self.conversation_history:
            role = msg['role']
            content = msg['content']
            if role == 'user':
                parts.append(f"<previous_user>\n{content}\n</previous_user>\n")
            elif role == 'assistant':
                parts.append(f"<previous_assistant>\n{content}\n</previous_assistant>\n")

        # Add current prompt
        parts.append(prompt)

        return '\n'.join(parts)

    def calculate_context_percentage(self, input_tokens: int) -> float:
        """Calculate context usage percentage."""
        context_window = 200000  # Sonnet 4 context window
        return (input_tokens / context_window) * 100

    def reset_context(self):
        """Reset conversation history (fresh start)."""
        self.conversation_history = []
        print("🔄 Context reset - starting fresh conversation")

    def get_context_stats(self) -> Dict:
        """Get current context usage statistics."""
        stats = {
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "input_tokens": self.total_input_tokens,
            "output_tokens": self.total_output_tokens,
            "conversation_turns": len(self.conversation_history) // 2,
            "mcp_mode": True,
        }

        if self.use_context_manager:
            context_window = 200000
            total_tokens = sum(item.token_estimate for item in self.context_manager.tracked_content)
            stats["context_percentage"] = (total_tokens / context_window) * 100
            stats["compaction_stats"] = {
                "count": self.context_manager.compaction_count,
                "available": self.use_context_manager,
            }
        else:
            stats["context_percentage"] = self.calculate_context_percentage(self.total_input_tokens)

        return stats

    def save_full_conversation(self, filepath: Path):
        """Save complete conversation history to file."""
        data = {
            "session_id": self.session_id,
            "conversation": self.conversation_history,
            "stats": self.get_context_stats(),
            "timestamp": datetime.now().isoformat(),
            "mcp_mode": True,
        }
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

    def _log_interaction(self, prompt: str, response: str, metadata: Dict):
        """Log interaction to session log."""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "prompt": prompt[:200] + "..." if len(prompt) > 200 else prompt,
            "response_length": len(response),
            "metadata": metadata,
            "mcp_mode": True,
        }
        with open(self.session_log, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
