#!/usr/bin/env python3
"""
Cost Tracker
Real-time cost tracking for multi-provider AI usage across all phases
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field
from ace.pricing_database import PricingDatabase


@dataclass
class PhaseUsage:
    """Track usage for a single phase"""
    phase: str
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class CostTracker:
    """
    Track AI costs across all phases with multi-provider support.
    Uses pricing database for accurate per-provider pricing.
    """

    def __init__(self, db: Optional[PricingDatabase] = None):
        """
        Initialize cost tracker.

        Args:
            db: PricingDatabase instance (creates new if None)
        """
        self.db = db or PricingDatabase()
        self.phase_usage: Dict[str, PhaseUsage] = {}
        self.call_history: List[Dict] = []

    def track_usage(
        self,
        phase: str,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int
    ):
        """
        Track token usage and calculate cost.

        Args:
            phase: Phase name (scout, architect, builder)
            provider: Provider name (anthropic, openai, etc.)
            model: Model name
            input_tokens: Input tokens used
            output_tokens: Output tokens used
        """
        # Get pricing from database
        pricing = self.db.get_pricing(provider, model)

        if not pricing:
            # Try to get from provider fallback
            try:
                from ace.provider_registry import get_registry
                registry = get_registry()
                provider_obj = registry.get(provider)
                fallback_pricing = provider_obj._get_fallback_pricing()

                if fallback_pricing and model in fallback_pricing:
                    pricing = fallback_pricing[model]
            except Exception:
                pass

        # Calculate cost
        if pricing:
            input_cost = (input_tokens / 1_000_000) * pricing.input_cost_per_1m
            output_cost = (output_tokens / 1_000_000) * pricing.output_cost_per_1m
            cost = input_cost + output_cost
        else:
            # If no pricing available, set to 0 and warn
            cost = 0.0

        # Update or create phase usage
        if phase in self.phase_usage:
            # Accumulate
            usage = self.phase_usage[phase]
            usage.input_tokens += input_tokens
            usage.output_tokens += output_tokens
            usage.cost += cost
        else:
            # Create new
            self.phase_usage[phase] = PhaseUsage(
                phase=phase,
                provider=provider,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost=cost
            )

        # Record in call history
        self.call_history.append({
            'phase': phase,
            'provider': provider,
            'model': model,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'cost': cost
        })

    def get_phase_cost(self, phase: str) -> float:
        """Get total cost for a specific phase"""
        if phase in self.phase_usage:
            return self.phase_usage[phase].cost
        return 0.0

    def get_total_cost(self) -> float:
        """Get total cost across all phases"""
        return sum(usage.cost for usage in self.phase_usage.values())

    def get_total_tokens(self) -> int:
        """Get total tokens across all phases"""
        return sum(usage.total_tokens for usage in self.phase_usage.values())

    def get_summary(self) -> Dict:
        """
        Get complete cost summary.

        Returns:
            Dict with phase breakdown and totals
        """
        return {
            'phases': {
                phase: {
                    'provider': usage.provider,
                    'model': usage.model,
                    'input_tokens': usage.input_tokens,
                    'output_tokens': usage.output_tokens,
                    'total_tokens': usage.total_tokens,
                    'cost': usage.cost
                }
                for phase, usage in self.phase_usage.items()
            },
            'total_cost': self.get_total_cost(),
            'total_tokens': self.get_total_tokens(),
            'total_input_tokens': sum(u.input_tokens for u in self.phase_usage.values()),
            'total_output_tokens': sum(u.output_tokens for u in self.phase_usage.values()),
            'calls': len(self.call_history)
        }

    def format_summary(self, verbose: bool = True) -> str:
        """
        Format cost summary as human-readable string.

        Args:
            verbose: Include detailed breakdown

        Returns:
            Formatted string
        """
        summary = self.get_summary()
        lines = []

        if verbose:
            lines.append("💰 COST SUMMARY")
            lines.append("━" * 60)

            # Per-phase breakdown
            for phase_name in ['scout', 'architect', 'builder']:
                if phase_name in summary['phases']:
                    phase = summary['phases'][phase_name]
                    lines.append(f"\n{phase_name.title()} Phase:     ${phase['cost']:.2f}  ({phase['provider']}/{phase['model']})")
                    lines.append(f"  {phase['input_tokens']:,} input + {phase['output_tokens']:,} output tokens")

            lines.append("\n" + "━" * 60)
            lines.append(f"TOTAL COST:      ${summary['total_cost']:.2f}")
            lines.append(f"TOTAL TOKENS:    {summary['total_tokens']:,}")
            lines.append("━" * 60)
        else:
            # Compact format
            lines.append(f"💰 Total Cost: ${summary['total_cost']:.2f} ({summary['total_tokens']:,} tokens)")

        return "\n".join(lines)

    def export_json(self) -> Dict:
        """Export detailed tracking data as JSON"""
        return {
            'summary': self.get_summary(),
            'call_history': self.call_history,
            'phase_usage': {
                phase: {
                    'provider': usage.provider,
                    'model': usage.model,
                    'input_tokens': usage.input_tokens,
                    'output_tokens': usage.output_tokens,
                    'cost': usage.cost
                }
                for phase, usage in self.phase_usage.items()
            }
        }
