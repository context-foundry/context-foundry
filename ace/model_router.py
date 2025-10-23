#!/usr/bin/env python3
"""
Intelligent Model Router - Routes tasks to appropriate models based on complexity.

Uses Sonnet 4.5 (fast, cost-effective) for most tasks.
Uses Opus 4 (expensive, most capable) only for complex tasks.

Expected impact: 40% cost savings while maintaining quality where it matters.
"""

import os
import re
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class ModelRoutingDecision:
    """Result of model routing decision."""
    model: str
    reason: str
    complexity_score: int
    used_opus: bool


class ModelRouter:
    """
    Routes tasks to appropriate models based on complexity analysis.

    Scoring Criteria (0-10 scale):
    - Phase type: Architect +3, Builder with high priority +2
    - Task priority >= 8: +2
    - Complex keywords in objective: +2 each
    - Workflow complexity = "Complex": +3

    Threshold: 7+ points = Use Opus 4
    """

    # Complexity keywords that indicate need for Opus
    COMPLEX_KEYWORDS = {
        'architecture', 'architect', 'design pattern', 'system design',
        'algorithm', 'optimization', 'optimize',
        'security', 'authentication', 'authorization', 'encryption',
        'database schema', 'data model', 'relational', 'normalization',
        'distributed', 'scalability', 'performance critical',
        'integration', 'api design', 'protocol',
        'refactor', 'migration', 'transformation'
    }

    def __init__(
        self,
        default_model: str = "claude-sonnet-4-5-20250929",
        complex_model: str = "claude-opus-4-20250514",
        complexity_threshold: int = 7,
        enabled: bool = True
    ):
        """
        Initialize model router.

        Args:
            default_model: Model for most tasks (Sonnet 4.5)
            complex_model: Model for complex tasks (Opus 4)
            complexity_threshold: Score threshold to trigger complex model (default: 7)
            enabled: Enable routing (if False, always use default)
        """
        self.default_model = default_model
        self.complex_model = complex_model
        self.complexity_threshold = complexity_threshold
        self.enabled = enabled

        # Load from environment if available
        self.default_model = os.getenv('MODEL_DEFAULT', self.default_model)
        self.complex_model = os.getenv('MODEL_COMPLEX', self.complex_model)
        self.complexity_threshold = int(os.getenv('COMPLEXITY_THRESHOLD', str(self.complexity_threshold)))
        self.enabled = os.getenv('MODEL_ROUTING_ENABLED', 'true').lower() == 'true'

        # Track routing decisions for stats
        self.decisions = []

    def get_model_for_task(
        self,
        phase: str,
        task: Optional[Any] = None,
        workflow_complexity: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> ModelRoutingDecision:
        """
        Determine which model to use for a task.

        Args:
            phase: Phase name ('scout', 'architect', 'builder', 'validator')
            task: SubagentTask object (optional, has priority, objective, type)
            workflow_complexity: Overall workflow complexity ('Simple', 'Medium', 'Complex')
            context: Additional context dict

        Returns:
            ModelRoutingDecision with model selection and reasoning
        """
        if not self.enabled:
            return ModelRoutingDecision(
                model=self.default_model,
                reason="Routing disabled",
                complexity_score=0,
                used_opus=False
            )

        # Calculate complexity score
        score, reasons = self._score_complexity(phase, task, workflow_complexity, context)

        # Make routing decision
        if score >= self.complexity_threshold:
            decision = ModelRoutingDecision(
                model=self.complex_model,
                reason=f"Complex task (score {score}/{self.complexity_threshold}): {', '.join(reasons)}",
                complexity_score=score,
                used_opus=True
            )
        else:
            decision = ModelRoutingDecision(
                model=self.default_model,
                reason=f"Standard task (score {score}/{self.complexity_threshold})",
                complexity_score=score,
                used_opus=False
            )

        # Track decision
        self.decisions.append(decision)

        return decision

    def _score_complexity(
        self,
        phase: str,
        task: Optional[Any],
        workflow_complexity: Optional[str],
        context: Optional[Dict[str, Any]]
    ) -> tuple[int, list[str]]:
        """
        Score task complexity on 0-10 scale.

        Returns:
            Tuple of (score, list of reasons)
        """
        score = 0
        reasons = []

        # Phase-based scoring
        if phase == 'architect':
            score += 3
            reasons.append("Architect phase (system design)")
        elif phase == 'builder' and task and hasattr(task, 'priority') and task.priority >= 8:
            score += 2
            reasons.append(f"High-priority builder task (priority {task.priority})")

        # Task priority scoring
        if task and hasattr(task, 'priority'):
            if task.priority >= 9:
                score += 2
                reasons.append(f"Critical priority ({task.priority})")
            elif task.priority >= 8:
                score += 1
                reasons.append(f"High priority ({task.priority})")

        # Objective keyword analysis
        if task and hasattr(task, 'objective'):
            objective_lower = task.objective.lower()
            matched_keywords = []

            for keyword in self.COMPLEX_KEYWORDS:
                if keyword in objective_lower:
                    matched_keywords.append(keyword)

            if matched_keywords:
                # Cap at +4 for keywords (max 2 keywords counted)
                keyword_score = min(len(matched_keywords) * 2, 4)
                score += keyword_score
                reasons.append(f"Complex keywords: {', '.join(matched_keywords[:2])}")

        # Workflow complexity assessment
        if workflow_complexity:
            if workflow_complexity.lower().startswith('complex'):
                score += 3
                reasons.append("Workflow marked as Complex")
            elif workflow_complexity.lower().startswith('medium'):
                score += 1
                reasons.append("Workflow marked as Medium")

        # Context-based scoring
        if context:
            # Check for dependency chains (complex coordination)
            if context.get('has_dependencies', False):
                score += 1
                reasons.append("Has task dependencies")

            # Check for large file operations
            if context.get('large_files', False):
                score += 1
                reasons.append("Large file operations")

        return score, reasons

    def get_routing_stats(self) -> Dict[str, Any]:
        """
        Get statistics on routing decisions.

        Returns:
            Dict with routing statistics
        """
        if not self.decisions:
            return {
                'total_decisions': 0,
                'default_model_count': 0,
                'complex_model_count': 0,
                'default_model_percentage': 0,
                'complex_model_percentage': 0,
                'average_complexity_score': 0
            }

        total = len(self.decisions)
        opus_count = sum(1 for d in self.decisions if d.used_opus)
        default_count = total - opus_count
        avg_score = sum(d.complexity_score for d in self.decisions) / total

        return {
            'total_decisions': total,
            'default_model_count': default_count,
            'complex_model_count': opus_count,
            'default_model_percentage': (default_count / total * 100) if total > 0 else 0,
            'complex_model_percentage': (opus_count / total * 100) if total > 0 else 0,
            'average_complexity_score': avg_score,
            'default_model': self.default_model,
            'complex_model': self.complex_model,
            'threshold': self.complexity_threshold
        }

    def format_routing_stats(self) -> str:
        """
        Format routing statistics for display.

        Returns:
            Formatted string with routing stats
        """
        stats = self.get_routing_stats()

        if stats['total_decisions'] == 0:
            return "No routing decisions made yet."

        lines = []
        lines.append("\n📊 Model Routing Statistics")
        lines.append("=" * 60)
        lines.append(f"Default Model ({self.default_model}):")
        lines.append(f"  {stats['default_model_count']} tasks ({stats['default_model_percentage']:.1f}%)")
        lines.append(f"\nComplex Model ({self.complex_model}):")
        lines.append(f"  {stats['complex_model_count']} tasks ({stats['complex_model_percentage']:.1f}%)")
        lines.append(f"\nAverage Complexity Score: {stats['average_complexity_score']:.1f}/{self.complexity_threshold}")
        lines.append(f"Threshold: {self.complexity_threshold} (tasks >= this use complex model)")

        return "\n".join(lines)

    def reset_stats(self):
        """Reset routing statistics."""
        self.decisions = []
