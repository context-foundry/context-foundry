#!/usr/bin/env python3
"""
Comprehensive unit tests for ContextManager.

Tests cover:
- Context tracking and metrics
- Token threshold detection
- Compaction logic and fallbacks
- Priority-based content retention
- Checkpoint/restore functionality
- Edge cases and error handling
"""

import json
import pytest
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from ace.context_manager import (
    ContextManager,
    ContextMetrics,
    ContentItem
)


# ============================================================================
# INITIALIZATION TESTS
# ============================================================================

@pytest.mark.unit
@pytest.mark.tier1
class TestContextManagerInit:
    """Test ContextManager initialization."""

    def test_init_creates_checkpoint_dir(self, tmp_path):
        """Test that initialization creates checkpoint directory."""
        # Arrange
        session_id = "test_session_001"
        checkpoint_dir = tmp_path / "checkpoints"

        # Act
        manager = ContextManager(session_id, checkpoint_dir)

        # Assert
        assert manager.session_id == session_id
        assert manager.checkpoint_dir == checkpoint_dir
        assert checkpoint_dir.exists()
        assert manager.total_input_tokens == 0
        assert manager.total_output_tokens == 0
        assert manager.message_count == 0
        assert manager.compaction_count == 0
        assert len(manager.tracked_content) == 0

    def test_init_default_checkpoint_path(self):
        """Test default checkpoint directory path."""
        # Arrange & Act
        manager = ContextManager("session_123")

        # Assert
        assert "session_123" in str(manager.checkpoint_dir)
        assert manager.checkpoint_dir.exists()

    def test_init_loads_existing_checkpoint(self, tmp_path):
        """Test that initialization loads existing checkpoint if available."""
        # Arrange
        session_id = "restore_test"
        checkpoint_dir = tmp_path / "checkpoints"
        checkpoint_dir.mkdir(parents=True)

        # Create existing checkpoint
        checkpoint_data = {
            "session_id": session_id,
            "total_input_tokens": 5000,
            "total_output_tokens": 2000,
            "message_count": 10,
            "compaction_count": 1,
            "last_compaction_tokens": 1000,
            "tracked_content": [],
            "metrics_history": [],
            "timestamp": datetime.now().isoformat()
        }

        latest_file = checkpoint_dir / "latest.json"
        with open(latest_file, "w") as f:
            json.dump(checkpoint_data, f)

        # Act
        manager = ContextManager(session_id, checkpoint_dir)

        # Assert
        assert manager.total_input_tokens == 5000
        assert manager.total_output_tokens == 2000
        assert manager.message_count == 10
        assert manager.compaction_count == 1


# ============================================================================
# TRACKING TESTS
# ============================================================================

@pytest.mark.unit
@pytest.mark.tier1
class TestTrackInteraction:
    """Test interaction tracking functionality."""

    def test_track_basic_interaction(self, tmp_path):
        """Test tracking a basic interaction."""
        # Arrange
        manager = ContextManager("track_test", tmp_path / "checkpoints")
        prompt = "Write a function to add two numbers"
        response = "Here's the function: def add(a, b): return a + b"

        # Act
        metrics = manager.track_interaction(
            prompt=prompt,
            response=response,
            input_tokens=100,
            output_tokens=50,
            content_type="code"
        )

        # Assert
        assert manager.total_input_tokens == 100
        assert manager.total_output_tokens == 50
        assert manager.message_count == 1
        assert len(manager.tracked_content) == 2  # prompt + response
        assert metrics.total_tokens == 100
        assert metrics.message_count == 1

    def test_track_multiple_interactions(self, tmp_path):
        """Test tracking multiple interactions accumulates correctly."""
        # Arrange
        manager = ContextManager("multi_track", tmp_path / "checkpoints")

        # Act
        manager.track_interaction("Prompt 1", "Response 1", 100, 50, "general")
        manager.track_interaction("Prompt 2", "Response 2", 200, 75, "code")
        metrics = manager.track_interaction("Prompt 3", "Response 3", 150, 60, "decision")

        # Assert
        assert manager.total_input_tokens == 450  # 100 + 200 + 150
        assert manager.total_output_tokens == 185  # 50 + 75 + 60
        assert manager.message_count == 3
        assert len(manager.tracked_content) == 6  # 3 prompts + 3 responses
        assert metrics.message_count == 3

    def test_track_content_importance_varies_by_type(self, tmp_path):
        """Test that different content types get different importance scores."""
        # Arrange
        manager = ContextManager("importance_test", tmp_path / "checkpoints")

        # Act
        manager.track_interaction("General query", "General answer", 100, 50, "general")
        manager.track_interaction("Critical decision", "Important choice", 100, 50, "decision")
        manager.track_interaction("Error occurred", "Fix applied", 100, 50, "error")

        # Assert
        items = manager.tracked_content
        general_items = [i for i in items if i.content_type == "general"]
        decision_items = [i for i in items if i.content_type == "decision"]
        error_items = [i for i in items if i.content_type == "error"]

        # Decision and error should have higher importance than general
        assert decision_items[0].importance_score > general_items[0].importance_score
        assert error_items[0].importance_score > general_items[0].importance_score

    def test_track_creates_content_items_with_metadata(self, tmp_path):
        """Test that tracked content includes all required metadata."""
        # Arrange
        manager = ContextManager("metadata_test", tmp_path / "checkpoints")

        # Act
        manager.track_interaction(
            prompt="Test prompt",
            response="Test response",
            input_tokens=100,
            output_tokens=50,
            content_type="pattern"
        )

        # Assert
        prompt_item = manager.tracked_content[0]
        response_item = manager.tracked_content[1]

        # Prompt item checks
        assert prompt_item.role == "user"
        assert prompt_item.content == "Test prompt"
        assert prompt_item.token_estimate == 100
        assert prompt_item.content_type == "pattern"
        assert prompt_item.importance_score > 0
        assert prompt_item.timestamp is not None

        # Response item checks
        assert response_item.role == "assistant"
        assert response_item.content == "Test response"
        assert response_item.token_estimate == 50


# ============================================================================
# USAGE METRICS TESTS
# ============================================================================

@pytest.mark.unit
@pytest.mark.tier1
class TestGetUsage:
    """Test context usage calculation."""

    def test_get_usage_empty_context(self, tmp_path):
        """Test usage metrics for empty context."""
        # Arrange
        manager = ContextManager("empty_usage", tmp_path / "checkpoints")

        # Act
        metrics = manager.get_usage()

        # Assert
        assert metrics.total_tokens == 0
        assert metrics.context_percentage == 0.0
        assert metrics.message_count == 0
        assert metrics.compaction_count == 0

    def test_get_usage_percentage_calculation(self, tmp_path):
        """Test that percentage is calculated correctly."""
        # Arrange
        manager = ContextManager("pct_test", tmp_path / "checkpoints")
        manager.total_input_tokens = 40000  # 20% of 200K

        # Act
        metrics = manager.get_usage()

        # Assert
        assert metrics.total_tokens == 40000
        assert metrics.context_percentage == 20.0

    def test_get_usage_at_threshold(self, tmp_path):
        """Test usage at compaction threshold."""
        # Arrange
        manager = ContextManager("threshold_test", tmp_path / "checkpoints")
        # 40% threshold = 80,000 tokens
        manager.total_input_tokens = 80000

        # Act
        metrics = manager.get_usage()

        # Assert
        assert metrics.context_percentage == 40.0


# ============================================================================
# COMPACTION DETECTION TESTS
# ============================================================================

@pytest.mark.unit
@pytest.mark.tier1
class TestShouldCompact:
    """Test compaction threshold detection."""

    def test_should_compact_below_threshold(self, tmp_path):
        """Test that compaction is not needed below threshold."""
        # Arrange
        manager = ContextManager("no_compact", tmp_path / "checkpoints")
        manager.total_input_tokens = 30000  # 15% (below 40% threshold)

        # Act
        should_compact, reason = manager.should_compact()

        # Assert
        assert should_compact is False
        assert "No compaction needed" in reason

    def test_should_compact_at_standard_threshold(self, tmp_path):
        """Test that compaction triggers at 40% threshold."""
        # Arrange
        manager = ContextManager("standard_compact", tmp_path / "checkpoints")
        manager.total_input_tokens = 80000  # 40%

        # Act
        should_compact, reason = manager.should_compact()

        # Assert
        assert should_compact is True
        assert "Standard compaction" in reason

    def test_should_compact_at_critical_threshold(self, tmp_path):
        """Test critical compaction at 70% threshold."""
        # Arrange
        manager = ContextManager("critical_compact", tmp_path / "checkpoints")
        manager.total_input_tokens = 140000  # 70%

        # Act
        should_compact, reason = manager.should_compact()

        # Assert
        assert should_compact is True
        assert "CRITICAL" in reason

    def test_should_compact_exact_threshold(self, tmp_path):
        """Test behavior at exact threshold values."""
        # Arrange
        manager = ContextManager("exact_threshold", tmp_path / "checkpoints")

        # Test at 39.9% - should not compact
        manager.total_input_tokens = 79800
        should_compact, _ = manager.should_compact()
        assert should_compact is False

        # Test at 40.0% - should compact
        manager.total_input_tokens = 80000
        should_compact, _ = manager.should_compact()
        assert should_compact is True


# ============================================================================
# EMERGENCY STOP TESTS
# ============================================================================

@pytest.mark.unit
@pytest.mark.tier1
class TestEmergencyStop:
    """Test emergency stop conditions."""

    def test_emergency_stop_below_threshold(self, tmp_path):
        """Test no emergency stop below 80% threshold."""
        # Arrange
        manager = ContextManager("no_emergency", tmp_path / "checkpoints")
        manager.total_input_tokens = 100000  # 50%

        # Act
        should_stop, reason = manager.should_emergency_stop()

        # Assert
        assert should_stop is False
        assert reason == ""

    def test_emergency_stop_at_hard_limit(self, tmp_path):
        """Test emergency stop at 80% hard limit."""
        # Arrange
        manager = ContextManager("hard_limit", tmp_path / "checkpoints")
        manager.total_input_tokens = 160000  # 80%

        # Act
        should_stop, reason = manager.should_emergency_stop()

        # Assert
        assert should_stop is True
        assert "EMERGENCY" in reason
        assert "80" in reason

    def test_emergency_stop_failing_compactions(self, tmp_path):
        """Test emergency stop when compactions consistently fail."""
        # Arrange
        manager = ContextManager("failing_compact", tmp_path / "checkpoints")
        manager.compaction_count = 3

        # Simulate failed compactions in metrics history
        # Pattern: before, after, before, after (where after >= 95% of before)
        manager.metrics_history = [
            ContextMetrics(100000, 50.0, 1, 0, 0, "2024-01-01T12:00:00"),
            ContextMetrics(98000, 49.0, 2, 1, 2000, "2024-01-01T12:01:00"),  # Only 2% reduction
            ContextMetrics(120000, 60.0, 3, 1, 0, "2024-01-01T12:02:00"),
            ContextMetrics(119000, 59.5, 4, 2, 1000, "2024-01-01T12:03:00"),  # Only 0.8% reduction
        ]

        # Act
        should_stop, reason = manager.should_emergency_stop()

        # Assert
        assert should_stop is True
        assert "algorithm breakdown" in reason


# ============================================================================
# BASIC COMPACTION TESTS
# ============================================================================

@pytest.mark.unit
@pytest.mark.tier1
class TestBasicCompaction:
    """Test basic priority-based compaction."""

    def test_basic_compaction_retains_high_priority(self, tmp_path):
        """Test that basic compaction retains high-priority items."""
        # Arrange
        manager = ContextManager("priority_compact", tmp_path / "checkpoints")

        # Add high and low priority items
        manager.tracked_content = [
            ContentItem("Low priority", "user", 0.3, 1000, "2024-01-01T12:00:00", "general"),
            ContentItem("High priority", "user", 0.9, 1000, "2024-01-01T12:01:00", "decision"),
            ContentItem("Medium priority", "user", 0.6, 1000, "2024-01-01T12:02:00", "code"),
        ]

        # Act
        retained = manager._basic_compaction()

        # Assert
        # Should retain high priority items
        high_priority_retained = any(item.importance_score == 0.9 for item in retained)
        assert high_priority_retained

    def test_basic_compaction_targets_25_percent(self, tmp_path):
        """Test that basic compaction targets 25% of context window."""
        # Arrange
        manager = ContextManager("target_test", tmp_path / "checkpoints")

        # Add items totaling 100K tokens
        for i in range(100):
            manager.tracked_content.append(
                ContentItem(f"Item {i}", "user", 0.5, 1000, f"2024-01-01T12:{i:02d}:00", "general")
            )

        # Act
        retained = manager._basic_compaction()
        total_retained_tokens = sum(item.token_estimate for item in retained)

        # Assert
        # Target is 25% of 200K = 50K tokens
        target = int(manager.CONTEXT_WINDOW * manager.COMPACTION_TARGET)
        # Should be close to target (allowing for critical items)
        assert total_retained_tokens <= target * 1.5  # Allow some overflow for critical items

    def test_basic_compaction_keeps_critical_content(self, tmp_path):
        """Test that critical content (importance >= 0.85) is always kept."""
        # Arrange
        manager = ContextManager("critical_test", tmp_path / "checkpoints")

        # Add one critical item and many non-critical items
        manager.tracked_content = [
            ContentItem(f"Non-critical {i}", "user", 0.5, 1000, f"2024-01-01T12:{i:02d}:00", "general")
            for i in range(60)
        ]
        # Add critical item
        manager.tracked_content.append(
            ContentItem("Critical item", "user", 0.9, 10000, "2024-01-01T13:00:00", "error")
        )

        # Act
        retained = manager._basic_compaction()

        # Assert
        critical_retained = any("Critical item" in item.content for item in retained)
        assert critical_retained


# ============================================================================
# FULL COMPACTION TESTS
# ============================================================================

@pytest.mark.unit
@pytest.mark.tier1
class TestCompact:
    """Test full compaction logic with fallbacks."""

    def test_compact_without_compactor(self, tmp_path):
        """Test compaction using basic compactor when no smart compactor provided."""
        # Arrange
        manager = ContextManager("basic_only", tmp_path / "checkpoints")
        manager.total_input_tokens = 80000  # At 40% threshold

        # Add content
        for i in range(50):
            manager.tracked_content.append(
                ContentItem(f"Item {i}", "user", 0.5, 2000, f"2024-01-01T12:{i:02d}:00", "general")
            )

        before_tokens = manager.total_input_tokens
        before_count = len(manager.tracked_content)

        # Act
        result = manager.compact(compactor=None)

        # Assert
        assert result["compacted"] is True
        assert result["after_tokens"] < result["before_tokens"]
        assert len(manager.tracked_content) < before_count
        assert manager.compaction_count == 1

    def test_compact_with_smart_compactor(self, tmp_path):
        """Test compaction with smart compactor."""
        # Arrange
        manager = ContextManager("smart_compact", tmp_path / "checkpoints")
        manager.total_input_tokens = 80000

        # Add content
        for i in range(10):
            manager.tracked_content.append(
                ContentItem(f"Item {i}", "user", 0.5, 8000, f"2024-01-01T12:{i:02d}:00", "code")
            )

        # Mock smart compactor
        mock_compactor = Mock()
        mock_compactor.compact_context.return_value = {
            "compacted": True,
            "retained_content": manager.tracked_content[:5],  # Keep half
            "estimated_tokens": 40000,
            "summary": "Smart compaction successful"
        }

        # Act
        result = manager.compact(compactor=mock_compactor)

        # Assert
        assert result["compacted"] is True
        assert result["after_tokens"] == 40000
        assert len(manager.tracked_content) == 5
        assert manager.compaction_count == 1
        assert "Smart" in result["summary"]

    def test_compact_smart_fails_fallback_to_basic(self, tmp_path):
        """Test fallback to basic compaction when smart compactor fails."""
        # Arrange
        manager = ContextManager("fallback_test", tmp_path / "checkpoints")
        manager.total_input_tokens = 80000

        for i in range(10):
            manager.tracked_content.append(
                ContentItem(f"Item {i}", "user", 0.5, 8000, f"2024-01-01T12:{i:02d}:00", "code")
            )

        # Mock smart compactor that indicates it skipped
        mock_compactor = Mock()
        mock_compactor.compact_context.return_value = {
            "compacted": False,
            "reason": "Not enough items to compact"
        }

        # Act
        result = manager.compact(compactor=mock_compactor)

        # Assert
        assert result["compacted"] is True  # Basic compaction should succeed
        assert "Basic compaction" in result["summary"]
        assert "skipped" in result["summary"]

    def test_compact_below_threshold_skips(self, tmp_path):
        """Test that compaction is skipped when below threshold."""
        # Arrange
        manager = ContextManager("skip_test", tmp_path / "checkpoints")
        manager.total_input_tokens = 30000  # 15%, below 40% threshold

        # Act
        result = manager.compact()

        # Assert
        assert result["compacted"] is False
        assert "No compaction needed" in result["reason"]
        assert result["reduction_pct"] == 0

    def test_compact_exception_handling(self, tmp_path):
        """Test exception handling during compaction."""
        # Arrange
        manager = ContextManager("error_test", tmp_path / "checkpoints")
        manager.total_input_tokens = 80000

        # Mock compactor that raises exception
        mock_compactor = Mock()
        mock_compactor.compact_context.side_effect = Exception("Smart compactor failed")

        # Add some content for basic compaction fallback
        for i in range(10):
            manager.tracked_content.append(
                ContentItem(f"Item {i}", "user", 0.5, 8000, f"2024-01-01T12:{i:02d}:00", "code")
            )

        # Act
        result = manager.compact(compactor=mock_compactor)

        # Assert
        # Should fall back to basic compaction
        assert result["compacted"] is True
        assert "error recovery" in result["summary"].lower()


# ============================================================================
# IMPORTANCE CALCULATION TESTS
# ============================================================================

@pytest.mark.unit
@pytest.mark.tier1
class TestCalculateImportance:
    """Test importance scoring algorithm."""

    def test_importance_by_content_type(self, tmp_path):
        """Test base importance scores for different content types."""
        # Arrange
        manager = ContextManager("importance_types", tmp_path / "checkpoints")

        # Act
        decision_score = manager._calculate_importance("decision", "prompt", "response")
        general_score = manager._calculate_importance("general", "prompt", "response")
        error_score = manager._calculate_importance("error", "prompt", "response")
        code_score = manager._calculate_importance("code", "prompt", "response")

        # Assert
        assert decision_score > general_score
        assert error_score > general_score
        assert code_score > general_score

    def test_importance_keyword_boost(self, tmp_path):
        """Test that important keywords boost importance score."""
        # Arrange
        manager = ContextManager("keyword_boost", tmp_path / "checkpoints")

        # Act
        with_keywords = manager._calculate_importance(
            "general",
            "This is a critical architecture decision",
            "Important design pattern"
        )
        without_keywords = manager._calculate_importance(
            "general",
            "Simple message",
            "Simple response"
        )

        # Assert
        assert with_keywords > without_keywords

    def test_importance_length_penalty(self, tmp_path):
        """Test that very long content gets a small penalty."""
        # Arrange
        manager = ContextManager("length_penalty", tmp_path / "checkpoints")

        # Act
        short_score = manager._calculate_importance("general", "Short", "Brief")
        long_score = manager._calculate_importance(
            "general",
            "x" * 10000,  # Very long prompt
            "y" * 10000   # Very long response
        )

        # Assert
        assert short_score >= long_score

    def test_importance_max_is_one(self, tmp_path):
        """Test that importance score never exceeds 1.0."""
        # Arrange
        manager = ContextManager("max_importance", tmp_path / "checkpoints")

        # Act - try to get maximum score
        score = manager._calculate_importance(
            "decision",  # High base score
            "critical important architecture decision error bug fix pattern strategy approach",
            "critical important architecture decision error bug fix pattern strategy approach"
        )

        # Assert
        assert score <= 1.0


# ============================================================================
# CHECKPOINT/RESTORE TESTS
# ============================================================================

@pytest.mark.unit
@pytest.mark.tier1
class TestCheckpointRestore:
    """Test checkpoint and restore functionality."""

    def test_checkpoint_saves_state(self, tmp_path):
        """Test that checkpoint saves complete state."""
        # Arrange
        manager = ContextManager("checkpoint_save", tmp_path / "checkpoints")
        manager.track_interaction("Test", "Response", 100, 50, "code")

        # Act
        checkpoint_path = manager.checkpoint()

        # Assert
        assert checkpoint_path.exists()
        assert (tmp_path / "checkpoints" / "latest.json").exists()

        # Verify checkpoint content
        with open(checkpoint_path) as f:
            data = json.load(f)

        assert data["session_id"] == "checkpoint_save"
        assert data["total_input_tokens"] == 100
        assert data["message_count"] == 1
        assert len(data["tracked_content"]) == 2

    def test_restore_from_checkpoint(self, tmp_path):
        """Test restoring from checkpoint."""
        # Arrange
        checkpoint_dir = tmp_path / "checkpoints"
        checkpoint_dir.mkdir(parents=True)

        # Create checkpoint
        checkpoint_data = {
            "session_id": "restore_me",
            "total_input_tokens": 5000,
            "total_output_tokens": 2500,
            "message_count": 10,
            "compaction_count": 2,
            "last_compaction_tokens": 1000,
            "tracked_content": [
                {
                    "content": "Test content",
                    "role": "user",
                    "importance_score": 0.8,
                    "token_estimate": 100,
                    "timestamp": "2024-01-01T12:00:00",
                    "content_type": "code"
                }
            ],
            "metrics_history": [],
            "timestamp": "2024-01-01T12:00:00"
        }

        checkpoint_path = checkpoint_dir / "test_checkpoint.json"
        with open(checkpoint_path, "w") as f:
            json.dump(checkpoint_data, f)

        # Act
        manager = ContextManager("new_session", checkpoint_dir)
        success = manager.restore(checkpoint_path)

        # Assert
        assert success is True
        assert manager.session_id == "restore_me"
        assert manager.total_input_tokens == 5000
        assert manager.total_output_tokens == 2500
        assert manager.message_count == 10
        assert manager.compaction_count == 2
        assert len(manager.tracked_content) == 1

    def test_restore_nonexistent_checkpoint(self, tmp_path):
        """Test restore returns False for nonexistent checkpoint."""
        # Arrange
        manager = ContextManager("no_checkpoint", tmp_path / "checkpoints")

        # Act
        success = manager.restore(tmp_path / "nonexistent.json")

        # Assert
        assert success is False

    def test_auto_checkpoint_every_5_messages(self, tmp_path):
        """Test that auto-checkpoint occurs every 5 messages."""
        # Arrange
        manager = ContextManager("auto_checkpoint", tmp_path / "checkpoints")

        # Act
        for i in range(6):
            manager.track_interaction(f"Prompt {i}", f"Response {i}", 100, 50, "general")

        # Assert
        # After 5 messages, a checkpoint should exist
        latest = tmp_path / "checkpoints" / "latest.json"
        assert latest.exists()


# ============================================================================
# INSIGHTS TESTS
# ============================================================================

@pytest.mark.unit
@pytest.mark.tier1
class TestGetInsights:
    """Test context insights generation."""

    def test_insights_structure(self, tmp_path):
        """Test that insights have correct structure."""
        # Arrange
        manager = ContextManager("insights_test", tmp_path / "checkpoints")
        manager.track_interaction("Test", "Response", 100, 50, "code")

        # Act
        insights = manager.get_insights()

        # Assert
        assert "current_usage" in insights
        assert "compaction_stats" in insights
        assert "content_breakdown" in insights
        assert "health" in insights

    def test_insights_content_breakdown(self, tmp_path):
        """Test content breakdown by type."""
        # Arrange
        manager = ContextManager("breakdown_test", tmp_path / "checkpoints")
        manager.track_interaction("Code query", "Code response", 100, 50, "code")
        manager.track_interaction("Decision query", "Decision response", 100, 50, "decision")
        manager.track_interaction("Error query", "Error response", 100, 50, "error")

        # Act
        insights = manager.get_insights()

        # Assert
        breakdown = insights["content_breakdown"]
        assert "code" in breakdown["by_count"]
        assert "decision" in breakdown["by_count"]
        assert "error" in breakdown["by_count"]

    def test_insights_health_status(self, tmp_path):
        """Test health status calculation."""
        # Arrange
        manager = ContextManager("health_test", tmp_path / "checkpoints")

        # Test healthy status (< 40%)
        manager.total_input_tokens = 60000  # 30%
        insights = manager.get_insights()
        assert insights["health"] == "healthy"

        # Test elevated status (40-70%)
        manager.total_input_tokens = 100000  # 50%
        insights = manager.get_insights()
        assert insights["health"] == "elevated"

        # Test critical status (>= 70%)
        manager.total_input_tokens = 140000  # 70%
        insights = manager.get_insights()
        assert insights["health"] == "critical"


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

@pytest.mark.integration
@pytest.mark.tier1
class TestContextManagerIntegration:
    """Integration tests for complete workflows."""

    def test_full_workflow_track_compact_checkpoint(self, tmp_path):
        """Test complete workflow: track, compact, checkpoint."""
        # Arrange
        manager = ContextManager("workflow_test", tmp_path / "checkpoints")

        # Act - Track many interactions to trigger compaction
        for i in range(50):
            manager.track_interaction(
                f"Prompt {i}",
                f"Response {i}",
                2000,  # 2K tokens each
                1000,
                "code" if i % 2 == 0 else "general"
            )

        # Should have 100K tokens now (50 * 2K), at 50% usage
        usage = manager.get_usage()

        # Trigger compaction
        result = manager.compact()

        # Checkpoint
        checkpoint_path = manager.checkpoint()

        # Assert
        assert usage.context_percentage >= 40.0  # Above compaction threshold
        assert result["compacted"] is True
        assert result["after_tokens"] < result["before_tokens"]
        assert checkpoint_path.exists()

    def test_checkpoint_restore_preserves_state(self, tmp_path):
        """Test that checkpoint and restore preserves complete state."""
        # Arrange
        checkpoint_dir = tmp_path / "checkpoints"
        manager1 = ContextManager("state_test", checkpoint_dir)

        # Track interactions
        for i in range(10):
            manager1.track_interaction(f"Q{i}", f"A{i}", 500, 250, "code")

        # Checkpoint
        manager1.checkpoint()

        original_tokens = manager1.total_input_tokens
        original_count = len(manager1.tracked_content)

        # Act - Create new manager and restore
        manager2 = ContextManager("new_session", checkpoint_dir)
        # Should auto-load from latest

        # Assert
        assert manager2.session_id == "state_test"
        assert manager2.total_input_tokens == original_tokens
        assert len(manager2.tracked_content) == original_count


# ============================================================================
# EDGE CASES AND ERROR HANDLING
# ============================================================================

@pytest.mark.unit
@pytest.mark.tier1
class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_tracked_content_compaction(self, tmp_path):
        """Test compaction with no tracked content."""
        # Arrange
        manager = ContextManager("empty_test", tmp_path / "checkpoints")
        manager.total_input_tokens = 80000  # Above threshold
        # But no tracked content

        # Act
        result = manager.compact()

        # Assert
        # Should handle gracefully
        assert isinstance(result, dict)

    def test_zero_tokens_usage(self, tmp_path):
        """Test usage calculation with zero tokens."""
        # Arrange
        manager = ContextManager("zero_tokens", tmp_path / "checkpoints")

        # Act
        metrics = manager.get_usage()

        # Assert
        assert metrics.total_tokens == 0
        assert metrics.context_percentage == 0.0

    def test_invalid_content_type(self, tmp_path):
        """Test handling of invalid content type."""
        # Arrange
        manager = ContextManager("invalid_type", tmp_path / "checkpoints")

        # Act
        manager.track_interaction(
            "Test",
            "Response",
            100,
            50,
            "unknown_type"  # Invalid type
        )

        # Assert
        # Should default to general importance
        items = manager.tracked_content
        assert len(items) == 2
        assert items[0].content_type == "unknown_type"

    def test_corrupted_checkpoint_handling(self, tmp_path):
        """Test handling of corrupted checkpoint file."""
        # Arrange
        checkpoint_dir = tmp_path / "checkpoints"
        checkpoint_dir.mkdir(parents=True)

        # Create corrupted checkpoint
        corrupted_file = checkpoint_dir / "latest.json"
        corrupted_file.write_text("{ invalid json")

        # Act & Assert
        # Should handle gracefully and not crash
        try:
            manager = ContextManager("corrupted_test", checkpoint_dir)
            # Manager should initialize with defaults if checkpoint is corrupted
            assert manager.total_input_tokens == 0
        except json.JSONDecodeError:
            # Also acceptable - restore fails gracefully
            pass
