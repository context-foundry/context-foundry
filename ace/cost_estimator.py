#!/usr/bin/env python3
"""
Cost Estimator
Estimates project costs based on task and model configuration
"""

from typing import Dict, Optional
from dataclasses import dataclass
from ace.pricing_database import PricingDatabase
from ace.provider_registry import get_registry


@dataclass
class PhaseEstimate:
    """Estimate for a single phase"""
    provider: str
    model: str
    estimated_input_tokens: int
    estimated_output_tokens: int
    cost_min: float
    cost_max: float
    input_cost_per_1m: float
    output_cost_per_1m: float


@dataclass
class CostEstimate:
    """Complete cost estimate for a project"""
    scout: PhaseEstimate
    architect: PhaseEstimate
    builder: PhaseEstimate
    total_min: float
    total_max: float
    currency: str = "USD"


class CostEstimator:
    """Estimates costs for Context Foundry projects"""

    def __init__(self, db: Optional[PricingDatabase] = None):
        """
        Initialize cost estimator.

        Args:
            db: PricingDatabase instance
        """
        self.db = db or PricingDatabase()

        # Phase multipliers based on historical data
        # These represent how much output compared to input
        self.phase_multipliers = {
            'scout': {
                'input_base': 2000,      # Base input tokens
                'output_multiplier': 2.0  # Output is 2x input
            },
            'architect': {
                'input_base': 3000,
                'output_multiplier': 2.5
            },
            'builder': {
                'input_base': 5000,
                'output_multiplier': 4.0  # Builder generates more code
            }
        }

    def estimate(
        self,
        task_description: str,
        scout_provider: str,
        scout_model: str,
        architect_provider: str,
        architect_model: str,
        builder_provider: str,
        builder_model: str
    ) -> CostEstimate:
        """
        Estimate total project cost.

        Args:
            task_description: Project description
            scout_provider: Provider for Scout phase
            scout_model: Model for Scout phase
            architect_provider: Provider for Architect phase
            architect_model: Model for Architect phase
            builder_provider: Provider for Builder phase
            builder_model: Model for Builder phase

        Returns:
            CostEstimate with breakdown by phase
        """
        # Estimate complexity from task description
        complexity_factor = self._estimate_complexity(task_description)

        # Estimate each phase
        scout_estimate = self._estimate_phase(
            'scout',
            scout_provider,
            scout_model,
            complexity_factor
        )

        architect_estimate = self._estimate_phase(
            'architect',
            architect_provider,
            architect_model,
            complexity_factor
        )

        builder_estimate = self._estimate_phase(
            'builder',
            builder_provider,
            builder_model,
            complexity_factor * 3  # Builder uses most tokens
        )

        # Calculate totals
        total_min = scout_estimate.cost_min + architect_estimate.cost_min + builder_estimate.cost_min
        total_max = scout_estimate.cost_max + architect_estimate.cost_max + builder_estimate.cost_max

        return CostEstimate(
            scout=scout_estimate,
            architect=architect_estimate,
            builder=builder_estimate,
            total_min=total_min,
            total_max=total_max
        )

    def _estimate_phase(
        self,
        phase: str,
        provider: str,
        model: str,
        complexity_factor: float
    ) -> PhaseEstimate:
        """
        Estimate cost for a single phase.

        Args:
            phase: Phase name ('scout', 'architect', 'builder')
            provider: Provider name
            model: Model name
            complexity_factor: Complexity multiplier (1.0 = average)

        Returns:
            PhaseEstimate
        """
        # Get pricing from database
        pricing = self.db.get_pricing(provider, model)

        # If not in database, try to get from provider fallback
        if not pricing:
            try:
                registry = get_registry()
                provider_obj = registry.get(provider)
                fallback_pricing = provider_obj._get_fallback_pricing()

                if fallback_pricing and model in fallback_pricing:
                    pricing = fallback_pricing[model]
                else:
                    raise ValueError(f"No pricing found for {provider}/{model}")
            except Exception:
                raise ValueError(f"No pricing found for {provider}/{model}")

        # Get phase multipliers
        phase_config = self.phase_multipliers[phase]

        # Estimate tokens
        base_input = phase_config['input_base']
        output_mult = phase_config['output_multiplier']

        # Apply complexity factor
        estimated_input = int(base_input * complexity_factor)
        estimated_output = int(estimated_input * output_mult)

        # Calculate costs (min and max range)
        # Min = base estimate * 0.7 (optimistic)
        # Max = base estimate * 1.5 (pessimistic)

        input_cost_min = (estimated_input * 0.7 / 1_000_000) * pricing.input_cost_per_1m
        input_cost_max = (estimated_input * 1.5 / 1_000_000) * pricing.input_cost_per_1m

        output_cost_min = (estimated_output * 0.7 / 1_000_000) * pricing.output_cost_per_1m
        output_cost_max = (estimated_output * 1.5 / 1_000_000) * pricing.output_cost_per_1m

        cost_min = input_cost_min + output_cost_min
        cost_max = input_cost_max + output_cost_max

        return PhaseEstimate(
            provider=provider,
            model=model,
            estimated_input_tokens=estimated_input,
            estimated_output_tokens=estimated_output,
            cost_min=cost_min,
            cost_max=cost_max,
            input_cost_per_1m=pricing.input_cost_per_1m,
            output_cost_per_1m=pricing.output_cost_per_1m
        )

    def _estimate_complexity(self, task_description: str) -> float:
        """
        Estimate task complexity from description.

        Returns:
            Complexity factor (0.5 = simple, 1.0 = average, 2.0 = complex)
        """
        # Simple heuristic based on description length and keywords
        complexity = 1.0

        # Length factor
        words = len(task_description.split())
        if words < 10:
            complexity *= 0.7  # Simple task
        elif words > 30:
            complexity *= 1.3  # More complex

        # Keyword detection
        complex_keywords = [
            'authentication', 'auth', 'database', 'db', 'api',
            'backend', 'frontend', 'full-stack', 'integration',
            'microservice', 'deploy', 'docker', 'kubernetes'
        ]

        simple_keywords = [
            'simple', 'basic', 'quick', 'small', 'minimal'
        ]

        desc_lower = task_description.lower()

        # Count complex keywords
        complex_count = sum(1 for kw in complex_keywords if kw in desc_lower)
        if complex_count >= 3:
            complexity *= 1.5

        # Count simple keywords
        simple_count = sum(1 for kw in simple_keywords if kw in desc_lower)
        if simple_count >= 2:
            complexity *= 0.6

        # Clamp to reasonable range
        return max(0.5, min(2.5, complexity))

    def format_estimate(self, estimate: CostEstimate) -> str:
        """
        Format cost estimate as human-readable string.

        Args:
            estimate: CostEstimate object

        Returns:
            Formatted string
        """
        lines = []
        lines.append("Cost Estimate")
        lines.append("=" * 60)
        lines.append("")

        # Scout
        lines.append(f"Scout Phase")
        lines.append(f"  Provider: {estimate.scout.provider}")
        lines.append(f"  Model: {estimate.scout.model}")
        lines.append(f"  Est. tokens: {estimate.scout.estimated_input_tokens:,} input, {estimate.scout.estimated_output_tokens:,} output")
        lines.append(f"  Cost: ${estimate.scout.cost_min:.2f} - ${estimate.scout.cost_max:.2f}")
        lines.append("")

        # Architect
        lines.append(f"Architect Phase")
        lines.append(f"  Provider: {estimate.architect.provider}")
        lines.append(f"  Model: {estimate.architect.model}")
        lines.append(f"  Est. tokens: {estimate.architect.estimated_input_tokens:,} input, {estimate.architect.estimated_output_tokens:,} output")
        lines.append(f"  Cost: ${estimate.architect.cost_min:.2f} - ${estimate.architect.cost_max:.2f}")
        lines.append("")

        # Builder
        lines.append(f"Builder Phase")
        lines.append(f"  Provider: {estimate.builder.provider}")
        lines.append(f"  Model: {estimate.builder.model}")
        lines.append(f"  Est. tokens: {estimate.builder.estimated_input_tokens:,} input, {estimate.builder.estimated_output_tokens:,} output")
        lines.append(f"  Cost: ${estimate.builder.cost_min:.2f} - ${estimate.builder.cost_max:.2f}")
        lines.append("")

        # Total
        lines.append("=" * 60)
        lines.append(f"Total Estimated Cost: ${estimate.total_min:.2f} - ${estimate.total_max:.2f}")
        lines.append("")

        return "\n".join(lines)
