#!/usr/bin/env python3
"""
Claude Code Client for Context Foundry
Sends prompts to Claude Desktop/Code via MCP instead of calling Anthropic API
This allows Context Foundry to work without API charges when used through MCP
"""

import os
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Tuple

# Import context management components
from ace.context_manager import ContextManager
from ace.compactors.smart_compactor import SmartCompactor


class ClaudeCodeClient:
    """
    Client for interacting with Claude via MCP (Model Context Protocol).
    Provides same interface as ClaudeClient but doesn't make API calls.
    Instead, returns prompts to be processed by Claude Desktop/Code.
    """

    def __init__(self, log_dir: Optional[Path] = None, session_id: Optional[str] = None, use_context_manager: bool = True):
        """Initialize Claude Code client.

        Args:
            log_dir: Directory for logs
            session_id: Session identifier for context management
            use_context_manager: Enable intelligent context management
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

        if self.use_context_manager:
            self.context_manager = ContextManager(self.session_id)
            self.smart_compactor = SmartCompactor()
        else:
            self.context_manager = None
            self.smart_compactor = None

        # MCP mode indicator
        self.mcp_mode = True
        print("🔧 Using MCP Mode - prompts will be processed by Claude Desktop")
        print("💰 No API charges - using your Claude subscription")

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

        # Build full prompt with conversation history
        full_prompt = self._build_prompt_with_history(prompt, system_prompt)

        # In MCP mode, we would use mcp.sampling here to send the prompt
        # to Claude Desktop. For now, this is a placeholder that demonstrates
        # the interface. The actual MCP server in tools/mcp_server.py handles
        # the sampling flow.

        # TODO: Implement actual MCP sampling integration
        # For now, raise an error indicating this client should only be used
        # through the MCP server, not directly
        raise NotImplementedError(
            "ClaudeCodeClient should be used through the MCP server (tools/mcp_server.py), "
            "not called directly. Run 'foundry serve' to start the MCP server."
        )

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
