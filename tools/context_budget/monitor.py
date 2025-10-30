#!/usr/bin/env python3
"""
Context Budget Monitor

Core monitoring logic for context window budget tracking and zone detection.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from enum import Enum


class ContextZone(Enum):
    """Context usage zones based on performance research"""
    SMART = "smart"          # 0-40% - optimal performance
    DUMB = "dumb"            # 40-80% - degraded performance
    CRITICAL = "critical"    # 80-100% - severe degradation


@dataclass
class PhaseAnalysis:
    """Analysis results for a build phase"""
    phase_name: str
    tokens_used: int
    percentage: float
    zone: ContextZone
    budget_allocated: int
    budget_remaining: int
    budget_exceeded_by: int = 0
    warnings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'phase_name': self.phase_name,
            'tokens_used': self.tokens_used,
            'percentage': round(self.percentage, 2),
            'zone': self.zone.value,
            'budget_allocated': self.budget_allocated,
            'budget_remaining': self.budget_remaining,
            'budget_exceeded_by': self.budget_exceeded_by,
            'warnings': self.warnings,
            'recommendations': self.recommendations,
        }


class ContextBudgetMonitor:
    """
    Monitors context window usage and enforces budgets.

    Budget allocation (percentage of context window):
    - Scout: 7% (requirements gathering)
    - Architect: 7% (system design)
    - Builder: 20% (code implementation)
    - Test: 20% (validation)
    - Documentation: 5% (docs generation)
    - Deploy: 3% (deployment tasks)
    - Feedback: 5% (learnings extraction)
    - System prompts: 15% (base orchestrator prompt)
    """

    # Budget allocations (percentage of context window)
    BUDGETS = {
        'scout': 7,
        'architect': 7,
        'builder': 20,
        'test': 20,
        'documentation': 5,
        'deploy': 3,
        'feedback': 5,
        'system_prompts': 15,
        'codebase_analysis': 10,
        'screenshot': 3,
        'github': 5,
    }

    # Zone thresholds (percentage)
    SMART_ZONE_MAX = 40
    CRITICAL_ZONE_MIN = 80

    def __init__(self, context_window_size: int = 200000, model: str = 'claude-sonnet-4'):
        """
        Initialize context budget monitor.

        Args:
            context_window_size: Maximum context window in tokens
            model: Model name (for reference)
        """
        self.context_window_size = context_window_size
        self.model = model
        self._phase_history: Dict[str, List[PhaseAnalysis]] = {}

    def check_phase(self, phase_name: str, tokens_used: int) -> PhaseAnalysis:
        """
        Analyze phase token usage against budget.

        Args:
            phase_name: Name of the phase (e.g., 'scout', 'architect')
            tokens_used: Actual tokens consumed in phase

        Returns:
            PhaseAnalysis with full analysis results
        """
        # Normalize phase name
        phase_key = phase_name.lower().replace(' ', '_').replace('-', '_')

        # Get budget for phase
        budget_allocated = self.get_budget_for_phase(phase_key)

        # Calculate percentage of total context
        percentage = (tokens_used / self.context_window_size) * 100 if self.context_window_size > 0 else 0

        # Determine zone
        zone = self.get_zone(tokens_used)

        # Calculate budget remaining/exceeded
        budget_remaining = max(0, budget_allocated - tokens_used)
        budget_exceeded_by = max(0, tokens_used - budget_allocated)

        # Generate warnings
        warnings = self._generate_warnings(phase_key, tokens_used, budget_allocated, zone, percentage)

        # Generate recommendations
        recommendations = self._generate_recommendations(phase_key, zone, budget_exceeded_by, percentage)

        # Create analysis
        analysis = PhaseAnalysis(
            phase_name=phase_name,
            tokens_used=tokens_used,
            percentage=percentage,
            zone=zone,
            budget_allocated=budget_allocated,
            budget_remaining=budget_remaining,
            budget_exceeded_by=budget_exceeded_by,
            warnings=warnings,
            recommendations=recommendations,
        )

        # Store in history
        if phase_key not in self._phase_history:
            self._phase_history[phase_key] = []
        self._phase_history[phase_key].append(analysis)

        return analysis

    def get_budget_for_phase(self, phase_name: str) -> int:
        """
        Get allocated token budget for phase.

        Args:
            phase_name: Name of the phase

        Returns:
            Token budget for phase
        """
        phase_key = phase_name.lower().replace(' ', '_').replace('-', '_')
        budget_percentage = self.BUDGETS.get(phase_key, 5)  # Default 5% if unknown
        return int(self.context_window_size * (budget_percentage / 100))

    def is_in_smart_zone(self, tokens_used: int) -> bool:
        """
        Check if usage is in smart zone (0-40%).

        Args:
            tokens_used: Token count

        Returns:
            True if in smart zone
        """
        percentage = (tokens_used / self.context_window_size) * 100
        return percentage <= self.SMART_ZONE_MAX

    def get_zone(self, tokens_used: int) -> ContextZone:
        """
        Determine which performance zone the usage falls into.

        Args:
            tokens_used: Token count

        Returns:
            ContextZone (SMART, DUMB, or CRITICAL)
        """
        percentage = (tokens_used / self.context_window_size) * 100

        if percentage <= self.SMART_ZONE_MAX:
            return ContextZone.SMART
        elif percentage < self.CRITICAL_ZONE_MIN:
            return ContextZone.DUMB
        else:
            return ContextZone.CRITICAL

    def _generate_warnings(self, phase_name: str, tokens_used: int,
                          budget_allocated: int, zone: ContextZone,
                          percentage: float) -> List[str]:
        """Generate warnings for phase analysis"""
        warnings = []

        # Budget exceeded warning
        if tokens_used > budget_allocated:
            exceeded_by = tokens_used - budget_allocated
            warnings.append(
                f"{phase_name.title()} phase exceeded budget by {exceeded_by:,} tokens "
                f"({exceeded_by / 1000:.1f}K)"
            )

        # Zone warnings
        if zone == ContextZone.CRITICAL:
            warnings.append(
                f"CRITICAL: Operating at {percentage:.1f}% context (>80%) - severe performance degradation"
            )
        elif zone == ContextZone.DUMB:
            warnings.append(
                f"Operating in dumb zone ({percentage:.1f}% context) - degraded model performance"
            )

        return warnings

    def _generate_recommendations(self, phase_name: str, zone: ContextZone,
                                 budget_exceeded_by: int, percentage: float) -> List[str]:
        """Generate actionable recommendations"""
        recommendations = []

        # Budget optimization
        if budget_exceeded_by > 0:
            recommendations.append(
                f"Consider breaking {phase_name} into smaller sub-phases or reducing scope"
            )

        # Zone-specific recommendations
        if zone == ContextZone.CRITICAL:
            recommendations.append(
                "Use sub-agents with isolated context to avoid critical zone"
            )
            recommendations.append(
                "Consider caching frequently used context (prompt caching)"
            )
        elif zone == ContextZone.DUMB:
            recommendations.append(
                "Reduce context by chunking large documents or using summarization"
            )

        # Phase-specific recommendations
        if phase_name == 'architect' and budget_exceeded_by > 10000:
            recommendations.append(
                "Architect phase too large - use modular architecture design"
            )
        elif phase_name == 'builder' and budget_exceeded_by > 20000:
            recommendations.append(
                "Builder phase too large - implement in parallel with sub-agents"
            )

        return recommendations

    def get_phase_history(self, phase_name: str) -> List[PhaseAnalysis]:
        """
        Get historical analysis for a phase.

        Args:
            phase_name: Name of the phase

        Returns:
            List of PhaseAnalysis objects
        """
        phase_key = phase_name.lower().replace(' ', '_').replace('-', '_')
        return self._phase_history.get(phase_key, [])

    def get_overall_stats(self) -> Dict:
        """
        Get overall statistics across all phases.

        Returns:
            Dictionary with overall stats
        """
        if not self._phase_history:
            return {
                'peak_usage_tokens': 0,
                'peak_usage_percentage': 0.0,
                'peak_phase': None,
                'avg_usage_percentage': 0.0,
                'smart_zone_percentage': 100.0,
                'total_phases': 0,
            }

        all_analyses = [
            analysis
            for analyses in self._phase_history.values()
            for analysis in analyses
        ]

        # Find peak usage
        peak_analysis = max(all_analyses, key=lambda a: a.tokens_used)

        # Calculate averages
        avg_percentage = sum(a.percentage for a in all_analyses) / len(all_analyses)

        # Calculate smart zone percentage
        smart_count = sum(1 for a in all_analyses if a.zone == ContextZone.SMART)
        smart_percentage = (smart_count / len(all_analyses)) * 100

        return {
            'peak_usage_tokens': peak_analysis.tokens_used,
            'peak_usage_percentage': peak_analysis.percentage,
            'peak_phase': peak_analysis.phase_name,
            'avg_usage_percentage': avg_percentage,
            'smart_zone_percentage': smart_percentage,
            'total_phases': len(all_analyses),
        }

    def export_to_session_summary(self) -> Dict:
        """
        Export metrics in session-summary.json format.

        Returns:
            Dictionary ready for session-summary.json
        """
        by_phase = {}
        for phase_key, analyses in self._phase_history.items():
            # Use most recent analysis for each phase
            if analyses:
                latest = analyses[-1]
                by_phase[f"phase_{phase_key}"] = latest.to_dict()

        overall = self.get_overall_stats()

        # Generate overall recommendations
        recommendations = []
        for phase_key, analyses in self._phase_history.items():
            if analyses:
                latest = analyses[-1]
                if latest.zone != ContextZone.SMART:
                    recommendations.append(
                        f"{latest.phase_name} consistently in {latest.zone.value} zone - optimize context usage"
                    )

        overall['recommendations'] = recommendations

        return {
            'max_context_window': self.context_window_size,
            'model': self.model,
            'by_phase': by_phase,
            'overall': overall,
        }
