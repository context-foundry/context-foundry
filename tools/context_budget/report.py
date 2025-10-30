#!/usr/bin/env python3
"""
Context Budget Reporter

Generates human-readable reports and visualizations of context window usage.
"""

from typing import Dict, Any, List, Optional
from .monitor import ContextZone


class ContextBudgetReporter:
    """Generate human-readable context budget reports"""

    def __init__(self):
        """Initialize reporter"""
        pass

    def generate_context_report(self, context_metrics: Dict) -> str:
        """
        Generate comprehensive context report.

        Args:
            context_metrics: Context metrics from session-summary.json

        Returns:
            Formatted report string
        """
        if not context_metrics:
            return "No context metrics available."

        max_window = context_metrics.get('max_context_window', 200000)
        model = context_metrics.get('model', 'unknown')
        by_phase = context_metrics.get('by_phase', {})
        overall = context_metrics.get('overall', {})

        # Build report
        lines = [
            "Context Window Budget Report",
            "═" * 75,
            "",
            f"Model: {model} ({max_window:,} tokens)",
            "",
            "Phase Analysis:",
        ]

        # Generate phase table
        if by_phase:
            lines.append(self.generate_phase_table(by_phase))
        else:
            lines.append("  No phase data available")

        lines.append("")

        # Overall stats
        if overall:
            peak_tokens = overall.get('peak_usage_tokens', 0)
            peak_pct = overall.get('peak_usage_percentage', 0)
            peak_phase = overall.get('peak_phase', 'unknown')
            avg_pct = overall.get('avg_usage_percentage', 0)
            smart_pct = overall.get('smart_zone_percentage', 0)

            zone_indicator = "⚠️" if peak_pct > 40 else "✅"
            lines.extend([
                f"Peak Usage: {peak_tokens:,} tokens ({peak_pct:.1f}%) during {peak_phase} phase {zone_indicator}",
                f"Average Usage: {avg_pct:.1f}%",
                f"Smart Zone: {smart_pct:.1f}% of phases",
                "",
            ])

        # Recommendations
        recommendations = overall.get('recommendations', [])
        if recommendations:
            lines.append("Recommendations:")
            for rec in recommendations:
                lines.append(f"  • {rec}")
        else:
            lines.append("Recommendations: All phases within optimal budget ✅")

        return "\n".join(lines)

    def generate_phase_table(self, by_phase: Dict) -> str:
        """
        Generate ASCII table of phase usage.

        Args:
            by_phase: Phase metrics dictionary

        Returns:
            Formatted table string
        """
        # Table header
        lines = [
            "┌─────────────────┬──────────┬──────────┬────────┬────────────┐",
            "│ Phase           │ Used     │ Budget   │ Usage  │ Zone       │",
            "├─────────────────┼──────────┼──────────┼────────┼────────────┤",
        ]

        # Sort phases by name
        sorted_phases = sorted(by_phase.items())

        for phase_key, metrics in sorted_phases:
            # Extract phase name (remove 'phase_' prefix)
            phase_name = metrics.get('phase_name', phase_key.replace('phase_', ''))

            tokens_used = metrics.get('tokens_used', 0)
            budget = metrics.get('budget_allocated', 0)
            percentage = metrics.get('percentage', 0)
            zone = metrics.get('zone', 'unknown')

            # Format values
            used_str = self._format_tokens(tokens_used)
            budget_str = self._format_tokens(budget)
            pct_str = f"{percentage:5.1f}%"
            zone_str = self.format_zone_indicator(zone)

            # Truncate phase name if too long
            phase_display = phase_name[:15].ljust(15)

            line = f"│ {phase_display} │ {used_str:8} │ {budget_str:8} │ {pct_str:6} │ {zone_str:10} │"
            lines.append(line)

        # Table footer
        lines.append("└─────────────────┴──────────┴──────────┴────────┴────────────┘")

        return "\n".join(lines)

    def visualize_context_usage(self, context_metrics: Dict) -> str:
        """
        Generate ASCII bar chart visualization.

        Args:
            context_metrics: Context metrics

        Returns:
            Formatted visualization
        """
        by_phase = context_metrics.get('by_phase', {})
        if not by_phase:
            return "No data to visualize"

        lines = ["Context Usage by Phase:", ""]

        max_percentage = 100
        bar_width = 50

        sorted_phases = sorted(by_phase.items())

        for phase_key, metrics in sorted_phases:
            phase_name = metrics.get('phase_name', phase_key.replace('phase_', ''))
            percentage = metrics.get('percentage', 0)
            zone = metrics.get('zone', 'unknown')

            # Create bar
            filled = int(bar_width * min(percentage, max_percentage) / max_percentage)
            bar = "█" * filled + "░" * (bar_width - filled)

            # Color indicator
            zone_emoji = self._get_zone_emoji(zone)

            # Format line
            line = f"{phase_name:15} {zone_emoji} [{bar}] {percentage:5.1f}%"
            lines.append(line)

        return "\n".join(lines)

    def get_optimization_suggestions(self, context_metrics: Dict) -> List[str]:
        """
        Generate optimization recommendations.

        Args:
            context_metrics: Context metrics

        Returns:
            List of actionable suggestions
        """
        suggestions = []

        by_phase = context_metrics.get('by_phase', {})
        overall = context_metrics.get('overall', {})

        # Check for phases in dumb/critical zones
        for phase_key, metrics in by_phase.items():
            zone = metrics.get('zone', 'smart')
            phase_name = metrics.get('phase_name', phase_key)
            tokens_used = metrics.get('tokens_used', 0)
            budget = metrics.get('budget_allocated', 0)

            if zone == 'critical':
                suggestions.append(
                    f"🚨 {phase_name} in CRITICAL zone - immediately reduce context or use sub-agents"
                )
            elif zone == 'dumb':
                exceeded = tokens_used - budget
                if exceeded > 0:
                    suggestions.append(
                        f"⚠️  {phase_name} exceeded budget by {exceeded:,} tokens - consider chunking"
                    )

        # Check overall stats
        avg_usage = overall.get('avg_usage_percentage', 0)
        smart_pct = overall.get('smart_zone_percentage', 0)

        if avg_usage > 30:
            suggestions.append(
                f"Average usage ({avg_usage:.1f}%) approaching dumb zone - review phase budgets"
            )

        if smart_pct < 70:
            suggestions.append(
                f"Only {smart_pct:.0f}% of phases in smart zone - optimize context management"
            )

        # General recommendations
        if not suggestions:
            suggestions.append("✅ All phases operating efficiently within budget")

        return suggestions

    def format_zone_indicator(self, zone: str) -> str:
        """
        Format zone with emoji indicator.

        Args:
            zone: Zone name ('smart', 'dumb', 'critical')

        Returns:
            Formatted zone string
        """
        indicators = {
            'smart': '✅ Smart',
            'dumb': '⚠️  Dumb',
            'critical': '🚨 Critical',
        }
        return indicators.get(zone, '❓ Unknown')

    def _get_zone_emoji(self, zone: str) -> str:
        """Get emoji for zone"""
        emojis = {
            'smart': '✅',
            'dumb': '⚠️',
            'critical': '🚨',
        }
        return emojis.get(zone, '❓')

    def _format_tokens(self, tokens: int) -> str:
        """Format token count (e.g., 12000 -> '12.0K')"""
        if tokens >= 1000:
            return f"{tokens / 1000:.1f}K"
        return f"{tokens}"

    def generate_summary_json(self, context_metrics: Dict) -> Dict[str, Any]:
        """
        Generate summary in JSON format.

        Args:
            context_metrics: Context metrics

        Returns:
            Summary dictionary
        """
        overall = context_metrics.get('overall', {})

        return {
            'status': 'optimal' if overall.get('smart_zone_percentage', 0) > 70 else 'needs_optimization',
            'peak_usage_percentage': overall.get('peak_usage_percentage', 0),
            'smart_zone_percentage': overall.get('smart_zone_percentage', 0),
            'total_phases_analyzed': overall.get('total_phases', 0),
            'recommendations': self.get_optimization_suggestions(context_metrics),
        }

    def export_markdown_report(self, context_metrics: Dict, output_path: Optional[str] = None) -> str:
        """
        Generate markdown-formatted report.

        Args:
            context_metrics: Context metrics
            output_path: Optional path to save report

        Returns:
            Markdown report string
        """
        report = f"""# Context Window Budget Analysis

## Summary

{self.generate_context_report(context_metrics)}

## Visualization

```
{self.visualize_context_usage(context_metrics)}
```

## Optimization Suggestions

"""
        for suggestion in self.get_optimization_suggestions(context_metrics):
            report += f"- {suggestion}\n"

        if output_path:
            with open(output_path, 'w') as f:
                f.write(report)

        return report
