#!/usr/bin/env python3
"""
Context Manager for Context Foundry
Intelligent context window tracking and management with automatic compaction.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict


@dataclass
class ContextMetrics:
    """Context usage metrics."""
    total_tokens: int
    context_percentage: float
    message_count: int
    compaction_count: int
    last_compaction_tokens: int
    timestamp: str


@dataclass
class ContentItem:
    """Tracked content item with priority."""
    content: str
    role: str
    importance_score: float
    token_estimate: int
    timestamp: str
    content_type: str  # 'decision', 'pattern', 'error', 'code', 'general'


class ContextManager:
    """
    Manages context window with intelligent compaction and prioritization.

    Features:
    - Real-time token tracking against 200K window
    - Automatic compaction at 40-50% threshold
    - Content prioritization by importance
    - Checkpoint/restore functionality
    - Quality metrics and insights
    """

    CONTEXT_WINDOW = 200000  # Claude Sonnet 4 context window
    COMPACTION_THRESHOLD = 0.40  # Compact at 40%
    COMPACTION_TARGET = 0.25  # Target 25% after compaction
    CRITICAL_THRESHOLD = 0.70  # Emergency compaction at 70%

    def __init__(self, session_id: str, checkpoint_dir: Optional[Path] = None):
        """Initialize context manager.

        Args:
            session_id: Unique session identifier
            checkpoint_dir: Directory for checkpoints (default: checkpoints/context)
        """
        self.session_id = session_id
        self.checkpoint_dir = checkpoint_dir or Path(f"checkpoints/context/{session_id}")
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

        # Tracking
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.message_count = 0
        self.compaction_count = 0
        self.last_compaction_tokens = 0

        # Content tracking for prioritization
        self.tracked_content: List[ContentItem] = []

        # Metrics history
        self.metrics_history: List[ContextMetrics] = []

        # Load previous state if exists
        self._load_checkpoint()

    def track_interaction(
        self,
        prompt: str,
        response: str,
        input_tokens: int,
        output_tokens: int,
        content_type: str = "general"
    ) -> ContextMetrics:
        """Track an interaction and update metrics.

        Args:
            prompt: User prompt
            response: Claude response
            input_tokens: Input token count
            output_tokens: Output token count
            content_type: Type of content ('decision', 'pattern', 'error', 'code', 'general')

        Returns:
            Current context metrics
        """
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.message_count += 1

        # Track content with importance scoring
        importance = self._calculate_importance(content_type, prompt, response)

        self.tracked_content.extend([
            ContentItem(
                content=prompt,
                role="user",
                importance_score=importance,
                token_estimate=input_tokens,
                timestamp=datetime.now().isoformat(),
                content_type=content_type
            ),
            ContentItem(
                content=response,
                role="assistant",
                importance_score=importance,
                token_estimate=output_tokens,
                timestamp=datetime.now().isoformat(),
                content_type=content_type
            )
        ])

        # Calculate metrics
        metrics = self.get_usage()
        self.metrics_history.append(metrics)

        # Auto-checkpoint periodically
        if self.message_count % 5 == 0:
            self.checkpoint()

        return metrics

    def get_usage(self) -> ContextMetrics:
        """Get current context usage metrics.

        Returns:
            Current context metrics
        """
        percentage = (self.total_input_tokens / self.CONTEXT_WINDOW) * 100

        return ContextMetrics(
            total_tokens=self.total_input_tokens,
            context_percentage=percentage,
            message_count=self.message_count,
            compaction_count=self.compaction_count,
            last_compaction_tokens=self.last_compaction_tokens,
            timestamp=datetime.now().isoformat()
        )

    def should_compact(self) -> Tuple[bool, str]:
        """Check if compaction is needed.

        Returns:
            Tuple of (should_compact, reason)
        """
        usage_pct = self.get_usage().context_percentage / 100

        if usage_pct >= self.CRITICAL_THRESHOLD:
            return True, f"CRITICAL: {usage_pct*100:.1f}% usage (threshold: {self.CRITICAL_THRESHOLD*100}%)"

        if usage_pct >= self.COMPACTION_THRESHOLD:
            return True, f"Standard compaction: {usage_pct*100:.1f}% usage (threshold: {self.COMPACTION_THRESHOLD*100}%)"

        return False, f"No compaction needed: {usage_pct*100:.1f}% usage"

    def compact(self, compactor=None) -> Dict:
        """Trigger context compaction.

        Args:
            compactor: Optional SmartCompactor instance. If None, uses basic compaction.

        Returns:
            Compaction results
        """
        should_compact, reason = self.should_compact()

        if not should_compact:
            return {
                "compacted": False,
                "reason": reason,
                "before_tokens": self.total_input_tokens,
                "after_tokens": self.total_input_tokens,
                "reduction_pct": 0
            }

        before_tokens = self.total_input_tokens
        before_count = len(self.tracked_content)

        if compactor:
            # Use intelligent compactor
            result = compactor.compact_context(self.tracked_content, self.get_usage())
            self.tracked_content = result["retained_content"]
            summary = result["summary"]
            after_tokens = result["estimated_tokens"]
        else:
            # Basic prioritization-based compaction
            self.tracked_content = self._basic_compaction()
            after_tokens = sum(item.token_estimate for item in self.tracked_content)
            summary = "Basic priority-based compaction"

        # Update metrics
        self.total_input_tokens = after_tokens
        self.compaction_count += 1
        self.last_compaction_tokens = before_tokens - after_tokens

        reduction_pct = ((before_tokens - after_tokens) / before_tokens * 100) if before_tokens > 0 else 0

        # Save compaction summary
        self._save_compaction_summary(before_tokens, after_tokens, summary)

        # Checkpoint after compaction
        self.checkpoint()

        return {
            "compacted": True,
            "reason": reason,
            "before_tokens": before_tokens,
            "after_tokens": after_tokens,
            "reduction_pct": reduction_pct,
            "before_items": before_count,
            "after_items": len(self.tracked_content),
            "summary": summary
        }

    def prioritize(self) -> List[ContentItem]:
        """Prioritize content by importance.

        Returns:
            Sorted list of content items by importance (descending)
        """
        return sorted(self.tracked_content, key=lambda x: x.importance_score, reverse=True)

    def checkpoint(self) -> Path:
        """Save current state to checkpoint.

        Returns:
            Path to checkpoint file
        """
        checkpoint_file = self.checkpoint_dir / f"checkpoint_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        state = {
            "session_id": self.session_id,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "message_count": self.message_count,
            "compaction_count": self.compaction_count,
            "last_compaction_tokens": self.last_compaction_tokens,
            "tracked_content": [asdict(item) for item in self.tracked_content],
            "metrics_history": [asdict(m) for m in self.metrics_history],
            "timestamp": datetime.now().isoformat()
        }

        with open(checkpoint_file, "w") as f:
            json.dump(state, f, indent=2)

        # Also save as latest
        latest_file = self.checkpoint_dir / "latest.json"
        with open(latest_file, "w") as f:
            json.dump(state, f, indent=2)

        return checkpoint_file

    def restore(self, checkpoint_path: Optional[Path] = None) -> bool:
        """Restore from checkpoint.

        Args:
            checkpoint_path: Path to checkpoint file. If None, uses latest.

        Returns:
            True if restored successfully
        """
        if checkpoint_path is None:
            checkpoint_path = self.checkpoint_dir / "latest.json"

        if not checkpoint_path.exists():
            return False

        with open(checkpoint_path) as f:
            state = json.load(f)

        self.session_id = state["session_id"]
        self.total_input_tokens = state["total_input_tokens"]
        self.total_output_tokens = state["total_output_tokens"]
        self.message_count = state["message_count"]
        self.compaction_count = state["compaction_count"]
        self.last_compaction_tokens = state["last_compaction_tokens"]

        self.tracked_content = [
            ContentItem(**item) for item in state["tracked_content"]
        ]

        self.metrics_history = [
            ContextMetrics(**m) for m in state["metrics_history"]
        ]

        return True

    def get_insights(self) -> Dict:
        """Get context management insights.

        Returns:
            Dictionary of insights and statistics
        """
        usage = self.get_usage()

        # Content type breakdown
        type_counts = {}
        type_tokens = {}
        for item in self.tracked_content:
            type_counts[item.content_type] = type_counts.get(item.content_type, 0) + 1
            type_tokens[item.content_type] = type_tokens.get(item.content_type, 0) + item.token_estimate

        # Average importance by type
        type_importance = {}
        for content_type in type_counts.keys():
            items = [i for i in self.tracked_content if i.content_type == content_type]
            type_importance[content_type] = sum(i.importance_score for i in items) / len(items) if items else 0

        # Compaction efficiency
        total_tokens_saved = self.compaction_count * self.last_compaction_tokens if self.compaction_count > 0 else 0

        return {
            "current_usage": {
                "tokens": usage.total_tokens,
                "percentage": usage.context_percentage,
                "messages": usage.message_count
            },
            "compaction_stats": {
                "count": self.compaction_count,
                "last_saved_tokens": self.last_compaction_tokens,
                "total_saved_estimate": total_tokens_saved
            },
            "content_breakdown": {
                "by_count": type_counts,
                "by_tokens": type_tokens,
                "by_importance": type_importance
            },
            "health": self._get_health_status()
        }

    def _calculate_importance(self, content_type: str, prompt: str, response: str) -> float:
        """Calculate importance score for content.

        Args:
            content_type: Type of content
            prompt: User prompt
            response: Claude response

        Returns:
            Importance score (0.0-1.0)
        """
        # Base scores by type
        type_scores = {
            "decision": 0.9,
            "pattern": 0.8,
            "error": 0.85,
            "code": 0.7,
            "general": 0.5
        }

        base_score = type_scores.get(content_type, 0.5)

        # Boost for keywords
        important_keywords = [
            "architecture", "design", "decision", "critical", "important",
            "error", "bug", "fix", "pattern", "strategy", "approach"
        ]

        text = (prompt + " " + response).lower()
        keyword_boost = sum(0.05 for keyword in important_keywords if keyword in text)

        # Length penalty (very long items are harder to keep)
        length_penalty = min(0.1, len(text) / 10000 * 0.1)

        final_score = min(1.0, base_score + keyword_boost - length_penalty)
        return final_score

    def _basic_compaction(self) -> List[ContentItem]:
        """Basic compaction using priority scoring.

        Returns:
            Retained content items
        """
        # Sort by importance
        sorted_items = self.prioritize()

        # Calculate target token count
        target_tokens = int(self.CONTEXT_WINDOW * self.COMPACTION_TARGET)

        # Keep items until we hit target
        retained = []
        current_tokens = 0

        for item in sorted_items:
            if current_tokens + item.token_estimate <= target_tokens:
                retained.append(item)
                current_tokens += item.token_estimate
            else:
                # Check if this is critical content we must keep
                if item.importance_score >= 0.85:
                    retained.append(item)
                    current_tokens += item.token_estimate

        return retained

    def _get_health_status(self) -> str:
        """Get context health status.

        Returns:
            Health status string
        """
        usage_pct = self.get_usage().context_percentage / 100

        if usage_pct < self.COMPACTION_THRESHOLD:
            return "healthy"
        elif usage_pct < self.CRITICAL_THRESHOLD:
            return "elevated"
        else:
            return "critical"

    def _save_compaction_summary(self, before: int, after: int, summary: str):
        """Save compaction summary to file.

        Args:
            before: Tokens before compaction
            after: Tokens after compaction
            summary: Compaction summary text
        """
        summary_file = self.checkpoint_dir / f"compaction_{self.compaction_count}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"

        content = f"""# Compaction Summary #{self.compaction_count}

**Timestamp**: {datetime.now().isoformat()}
**Session**: {self.session_id}

## Metrics
- **Before**: {before:,} tokens ({before/self.CONTEXT_WINDOW*100:.1f}%)
- **After**: {after:,} tokens ({after/self.CONTEXT_WINDOW*100:.1f}%)
- **Reduction**: {before-after:,} tokens ({(before-after)/before*100:.1f}%)

## Summary
{summary}

## Content Retained
- Total items: {len(self.tracked_content)}
- By type: {self._get_type_breakdown()}
"""

        summary_file.write_text(content)

    def _get_type_breakdown(self) -> str:
        """Get content type breakdown as string."""
        type_counts = {}
        for item in self.tracked_content:
            type_counts[item.content_type] = type_counts.get(item.content_type, 0) + 1

        return ", ".join(f"{t}: {c}" for t, c in sorted(type_counts.items()))

    def _load_checkpoint(self):
        """Load previous checkpoint if exists."""
        latest = self.checkpoint_dir / "latest.json"
        if latest.exists():
            self.restore(latest)


def test_context_manager():
    """Test context manager functionality."""
    print("🧪 Testing Context Manager")
    print("=" * 60)

    # Create manager
    manager = ContextManager("test_session")

    # Simulate interactions
    print("\n1. Tracking interactions...")
    for i in range(5):
        manager.track_interaction(
            prompt=f"Test prompt {i}" * 100,
            response=f"Test response {i}" * 100,
            input_tokens=1000 + i * 100,
            output_tokens=500 + i * 50,
            content_type="code" if i % 2 == 0 else "decision"
        )

    # Check usage
    print("\n2. Current usage...")
    metrics = manager.get_usage()
    print(f"   Tokens: {metrics.total_tokens:,}")
    print(f"   Percentage: {metrics.context_percentage:.2f}%")
    print(f"   Messages: {metrics.message_count}")

    # Check if compaction needed
    print("\n3. Compaction check...")
    should_compact, reason = manager.should_compact()
    print(f"   Should compact: {should_compact}")
    print(f"   Reason: {reason}")

    # Prioritize content
    print("\n4. Content prioritization...")
    prioritized = manager.prioritize()
    print(f"   Items: {len(prioritized)}")
    print(f"   Top importance: {prioritized[0].importance_score:.2f}")
    print(f"   Top type: {prioritized[0].content_type}")

    # Checkpoint
    print("\n5. Creating checkpoint...")
    checkpoint_path = manager.checkpoint()
    print(f"   Saved to: {checkpoint_path}")

    # Insights
    print("\n6. Context insights...")
    insights = manager.get_insights()
    print(f"   Health: {insights['health']}")
    print(f"   Content types: {list(insights['content_breakdown']['by_count'].keys())}")

    print("\n✅ Context Manager test complete!")


if __name__ == "__main__":
    test_context_manager()
