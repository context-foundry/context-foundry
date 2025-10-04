#!/usr/bin/env python3
"""
Claude CLI Integration for Context Foundry
Uses the Claude CLI instead of API key for authentication.
Supports users already logged into Claude CLI.
"""

import os
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Tuple

# Import context management components
from ace.context_manager import ContextManager
from ace.compactors.smart_compactor import SmartCompactor


class ClaudeCLIClient:
    """
    Client for interacting with Claude via CLI instead of API key.
    Provides same interface as ClaudeClient for drop-in compatibility.
    """

    def __init__(self, log_dir: Optional[Path] = None, session_id: Optional[str] = None, use_context_manager: bool = True):
        """Initialize Claude CLI client.

        Args:
            log_dir: Directory for logs
            session_id: Session identifier for context management
            use_context_manager: Enable intelligent context management
        """
        # Check if claude CLI is available
        if not self._check_claude_cli():
            raise ValueError(
                "Claude CLI not found. Please install Claude CLI and login first:\n"
                "Visit: https://claude.ai/download"
            )

        self.max_tokens = 8000
        self.conversation_history: List[Dict] = []
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost_usd = 0.0

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

        # Conversation file for maintaining history
        self.conversation_file = self.log_dir / "cli_conversation.json"
        self._load_conversation()

    def _check_claude_cli(self) -> bool:
        """Check if Claude CLI is installed and accessible."""
        try:
            result = subprocess.run(
                ["claude", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def _load_conversation(self):
        """Load conversation history from file."""
        if self.conversation_file.exists():
            try:
                with open(self.conversation_file, 'r') as f:
                    data = json.load(f)
                    self.conversation_history = data.get('history', [])
                    self.total_input_tokens = data.get('total_input_tokens', 0)
                    self.total_output_tokens = data.get('total_output_tokens', 0)
                    self.total_cost_usd = data.get('total_cost_usd', 0.0)
            except Exception as e:
                print(f"⚠️  Could not load conversation history: {e}")

    def _save_conversation(self):
        """Save conversation history to file."""
        data = {
            'history': self.conversation_history,
            'total_input_tokens': self.total_input_tokens,
            'total_output_tokens': self.total_output_tokens,
            'total_cost_usd': self.total_cost_usd,
            'last_updated': datetime.now().isoformat()
        }
        with open(self.conversation_file, 'w') as f:
            json.dump(data, f, indent=2)

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

    def call_claude(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_retries: int = 3,
        reset_context: bool = False,
        content_type: str = "general",
    ) -> Tuple[str, Dict]:
        """
        Call Claude via CLI with automatic retries and context management.

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

        # Build full prompt with history
        full_prompt = self._build_prompt_with_history(prompt, system_prompt)

        # Retry logic
        for attempt in range(max_retries):
            try:
                # Call Claude CLI
                result = subprocess.run(
                    ["claude", "--print", "--output-format", "json"],
                    input=full_prompt,
                    capture_output=True,
                    text=True,
                    timeout=600  # 10 minute timeout for long-running phases like Architect
                )

                if result.returncode != 0:
                    raise RuntimeError(f"Claude CLI failed: {result.stderr}")

                # Parse JSON response
                response_data = json.loads(result.stdout)

                if response_data.get('is_error'):
                    raise RuntimeError(f"Claude CLI error: {response_data.get('result', 'Unknown error')}")

                # Extract response
                response_text = response_data['result']

                # Extract usage stats
                usage = response_data.get('usage', {})
                input_tokens = usage.get('input_tokens', 0)
                output_tokens = usage.get('output_tokens', 0)
                cost_usd = response_data.get('total_cost_usd', 0.0)

                # Track tokens
                self.total_input_tokens += input_tokens
                self.total_output_tokens += output_tokens
                self.total_cost_usd += cost_usd

                # Update conversation history
                self.conversation_history.append({"role": "user", "content": prompt})
                self.conversation_history.append({"role": "assistant", "content": response_text})

                # Save conversation
                self._save_conversation()

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
                    "model": response_data.get('modelUsage', {}).get('claude-sonnet-4-5-20250929', {}).get('modelName', 'claude-sonnet-4'),
                    "timestamp": datetime.now().isoformat(),
                    "cost_usd": cost_usd,
                    "total_cost_usd": self.total_cost_usd,
                }

                # Add context health if using context manager
                if self.use_context_manager:
                    # TODO: Add health status once ContextManager has public get_health_status() method
                    # metadata["context_health"] = "healthy"  # Placeholder
                    metadata["compaction_count"] = self.context_manager.compaction_count

                # Log the interaction
                self._log_interaction(prompt, response_text, metadata)

                return response_text, metadata

            except subprocess.TimeoutExpired:
                if attempt < max_retries - 1:
                    print(f"⚠️  Request timeout, retrying ({attempt + 1}/{max_retries})...")
                    continue
                raise RuntimeError("Claude CLI request timed out after multiple retries")

            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"⚠️  Error: {e}, retrying ({attempt + 1}/{max_retries})...")
                    continue
                raise

        raise RuntimeError("Failed after maximum retries")

    def calculate_context_percentage(self, input_tokens: int) -> float:
        """Calculate context usage percentage."""
        context_window = 200000  # Sonnet 4 context window
        return (input_tokens / context_window) * 100

    def reset_context(self):
        """Reset conversation history (fresh start)."""
        self.conversation_history = []
        self._save_conversation()
        print("🔄 Context reset - starting fresh conversation")

    def get_context_stats(self) -> Dict:
        """Get current context usage statistics."""
        stats = {
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "input_tokens": self.total_input_tokens,
            "output_tokens": self.total_output_tokens,
            "total_cost_usd": self.total_cost_usd,
            "conversation_turns": len(self.conversation_history) // 2,
        }

        if self.use_context_manager:
            context_window = 200000
            total_tokens = sum(item.token_estimate for item in self.context_manager.tracked_content)
            stats["context_percentage"] = (total_tokens / context_window) * 100
            # TODO: Add health status once ContextManager has public method
            # stats["context_health"] = "healthy"  # Placeholder
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
        }
        with open(self.session_log, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
