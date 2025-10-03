#!/usr/bin/env python3
"""
Smart Compactor for Context Foundry
Uses Claude to intelligently summarize completed work while preserving critical information.
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from anthropic import Anthropic
import os


@dataclass
class CompactionResult:
    """Result of context compaction."""
    summary: str
    retained_content: List
    estimated_tokens: int
    reduction_percentage: float
    critical_items_preserved: List[str]


class SmartCompactor:
    """
    Intelligent context compactor using Claude for summarization.

    Preserves:
    - Architecture decisions made
    - Patterns identified and applied
    - Current task context
    - Critical errors to avoid
    - Implementation approaches

    Reduces context by 60-70% while maintaining quality.
    """

    def __init__(self, output_dir: Optional[Path] = None):
        """Initialize smart compactor.

        Args:
            output_dir: Directory for PROGRESS_SUMMARY.md files
        """
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")

        self.client = Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-20250514"
        self.output_dir = output_dir or Path("checkpoints/summaries")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def compact_context(
        self,
        tracked_content: List,
        current_metrics: dict
    ) -> Dict:
        """Compact context using Claude for intelligent summarization.

        Args:
            tracked_content: List of ContentItem objects to compact
            current_metrics: Current context metrics

        Returns:
            Dictionary with compaction results
        """
        # Separate content by importance and type
        critical_items = [item for item in tracked_content if item.importance_score >= 0.85]
        compactable_items = [item for item in tracked_content if item.importance_score < 0.85]

        # Build conversation history for summarization
        conversation_text = self._build_conversation_text(compactable_items)

        # Create summarization prompt
        summary_prompt = self._build_summary_prompt(
            conversation_text,
            current_metrics,
            len(critical_items),
            len(compactable_items)
        )

        # Call Claude for summarization
        print("🤖 Calling Claude for intelligent context compaction...")
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4000,  # Generous limit for summary
            messages=[{"role": "user", "content": summary_prompt}]
        )

        summary = response.content[0].text
        summary_tokens = response.usage.output_tokens

        # Save summary to file
        summary_file = self._save_summary(summary, current_metrics)

        # Create compact representation
        from ace.context_manager import ContentItem

        compact_item = ContentItem(
            content=summary,
            role="assistant",
            importance_score=0.95,  # High importance
            token_estimate=summary_tokens,
            timestamp=datetime.now().isoformat(),
            content_type="summary"
        )

        # Retain critical items + summary
        retained_content = critical_items + [compact_item]

        # Calculate reduction
        before_tokens = sum(item.token_estimate for item in tracked_content)
        after_tokens = sum(item.token_estimate for item in retained_content)
        reduction_pct = ((before_tokens - after_tokens) / before_tokens * 100) if before_tokens > 0 else 0

        # Extract critical items preserved
        critical_descriptions = [
            f"{item.content_type}: {item.content[:100]}..."
            for item in critical_items[:5]  # Top 5
        ]

        print(f"✅ Compaction complete:")
        print(f"   Before: {before_tokens:,} tokens")
        print(f"   After: {after_tokens:,} tokens")
        print(f"   Reduction: {reduction_pct:.1f}%")
        print(f"   Summary saved: {summary_file}")

        return {
            "summary": summary,
            "retained_content": retained_content,
            "estimated_tokens": after_tokens,
            "reduction_pct": reduction_pct,
            "critical_items": critical_descriptions,
            "summary_file": str(summary_file)
        }

    def _build_conversation_text(self, items: List) -> str:
        """Build conversation text from content items.

        Args:
            items: List of ContentItem objects

        Returns:
            Formatted conversation text
        """
        lines = []

        for item in items:
            prefix = "USER" if item.role == "user" else "ASSISTANT"
            lines.append(f"{prefix} [{item.content_type}]:")
            lines.append(item.content)
            lines.append("")

        return "\n".join(lines)

    def _build_summary_prompt(
        self,
        conversation: str,
        metrics: dict,
        critical_count: int,
        compactable_count: int
    ) -> str:
        """Build prompt for Claude summarization.

        Args:
            conversation: Conversation text to summarize
            metrics: Current context metrics
            critical_count: Number of critical items kept
            compactable_count: Number of items to compact

        Returns:
            Summarization prompt
        """
        return f"""You are compacting context for an AI coding session to stay within token limits.

CURRENT STATE:
- Context usage: {metrics.context_percentage:.1f}% of 200K token window
- Total tokens: {metrics.total_tokens:,}
- Messages: {metrics.message_count}
- Critical items preserved: {critical_count}
- Items to compact: {compactable_count}

YOUR TASK:
Create a comprehensive but concise summary of the conversation below. This summary will replace the full conversation history, so it must preserve ALL critical information.

MUST PRESERVE:
1. **Architecture Decisions**: Any design choices, technology selections, or structural decisions
2. **Patterns Identified**: Code patterns, best practices, or approaches discovered/applied
3. **Current Task Context**: What we're working on NOW and immediate next steps
4. **Critical Errors/Pitfalls**: Any bugs found, errors to avoid, or lessons learned
5. **Implementation Approaches**: Key strategies or methods being used
6. **Progress Made**: What's been completed and what remains

CONVERSATION TO SUMMARIZE:
{conversation}

OUTPUT FORMAT:
Provide a structured summary with these sections:

## Architecture & Design Decisions
[Key architectural choices and rationale]

## Patterns & Best Practices
[Patterns identified, applied, or discovered]

## Current Context
[What we're working on right now, current phase, immediate goals]

## Progress Summary
[What's been completed, what remains, key milestones]

## Critical Issues & Learnings
[Errors encountered, solutions found, things to avoid]

## Implementation Details
[Key technical approaches, algorithms, data structures]

Be thorough but concise. Target 1500-2500 tokens. This summary is critical - missing information could derail the project."""

    def _save_summary(self, summary: str, metrics: dict) -> Path:
        """Save progress summary to file.

        Args:
            summary: Summary text
            metrics: Context metrics

        Returns:
            Path to summary file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        summary_file = self.output_dir / f"PROGRESS_SUMMARY_{timestamp}.md"

        content = f"""# Progress Summary
**Generated**: {datetime.now().isoformat()}
**Context Usage**: {metrics.context_percentage:.1f}% ({metrics.total_tokens:,} tokens)
**Messages**: {metrics.message_count}
**Compaction**: #{metrics.compaction_count + 1}

---

{summary}

---

*This summary was generated by SmartCompactor to reduce context usage while preserving critical information.*
"""

        summary_file.write_text(content)
        return summary_file

    def create_initial_summary(
        self,
        project_name: str,
        task_description: str,
        architecture_notes: str = ""
    ) -> str:
        """Create an initial summary for a new session.

        Args:
            project_name: Project name
            task_description: Task description
            architecture_notes: Optional architecture notes

        Returns:
            Initial summary text
        """
        summary = f"""## Project Context
**Project**: {project_name}
**Task**: {task_description}

## Architecture & Design Decisions
{architecture_notes if architecture_notes else 'Initial architecture to be determined.'}

## Current Context
Starting new implementation session. Research and planning phase.

## Progress Summary
- Session initialized
- Ready for Scout phase (research and architecture)

## Critical Issues & Learnings
None yet - fresh start.

## Implementation Details
To be determined during Scout and Architect phases.
"""

        return summary


def test_smart_compactor():
    """Test smart compactor functionality."""
    print("🧪 Testing Smart Compactor")
    print("=" * 60)

    # Check API key
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("⚠️  ANTHROPIC_API_KEY not set - skipping live test")
        print("✅ Smart Compactor loaded successfully (not tested)")
        return

    from ace.context_manager import ContentItem, ContextMetrics

    # Create compactor
    compactor = SmartCompactor()

    # Create sample content
    content_items = [
        ContentItem(
            content="Let's build a REST API with authentication",
            role="user",
            importance_score=0.9,
            token_estimate=100,
            timestamp=datetime.now().isoformat(),
            content_type="decision"
        ),
        ContentItem(
            content="I recommend using FastAPI with JWT tokens for authentication. Here's why...",
            role="assistant",
            importance_score=0.9,
            token_estimate=150,
            timestamp=datetime.now().isoformat(),
            content_type="decision"
        ),
        ContentItem(
            content="Implement the user model with password hashing",
            role="user",
            importance_score=0.7,
            token_estimate=80,
            timestamp=datetime.now().isoformat(),
            content_type="code"
        ),
        ContentItem(
            content="Here's the user model implementation:\nclass User:\n    def __init__(self, username, password):\n        self.username = username\n        self.password_hash = hash(password)",
            role="assistant",
            importance_score=0.7,
            token_estimate=200,
            timestamp=datetime.now().isoformat(),
            content_type="code"
        ),
    ]

    # Create metrics
    metrics = ContextMetrics(
        total_tokens=530,
        context_percentage=0.265,
        message_count=4,
        compaction_count=0,
        last_compaction_tokens=0,
        timestamp=datetime.now().isoformat()
    )

    # Test compaction
    print("\n1. Testing context compaction...")
    result = compactor.compact_context(content_items, metrics)

    print(f"\n2. Compaction results:")
    print(f"   Reduction: {result['reduction_pct']:.1f}%")
    print(f"   Estimated tokens: {result['estimated_tokens']}")
    print(f"   Retained items: {len(result['retained_content'])}")

    print(f"\n3. Summary preview:")
    print("-" * 60)
    print(result['summary'][:500] + "...")
    print("-" * 60)

    print(f"\n4. Summary saved to: {result['summary_file']}")

    print("\n✅ Smart Compactor test complete!")


if __name__ == "__main__":
    test_smart_compactor()
