#!/usr/bin/env python3
"""
Cost Calculator Module
Calculate costs from token usage with model-specific pricing
"""

import json
import threading
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from .log_parser import TokenUsage


class CostCalculator:
    """Calculate costs from token usage with model-specific pricing"""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize cost calculator.

        Args:
            config_path: Path to pricing_config.json (default: tools/metrics/pricing_config.json)
        """
        if config_path is None:
            # Default to config in same directory
            config_path = Path(__file__).parent / 'pricing_config.json'

        self.config_path = Path(config_path)
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load pricing configuration from JSON file"""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            # Return default configuration
            return {
                'models': {
                    'default': {
                        'input_per_mtok': 3.00,
                        'output_per_mtok': 15.00,
                        'cache_write_per_mtok': 3.75,
                        'cache_read_per_mtok': 0.30
                    }
                },
                'budget': {
                    'daily_limit_usd': 50.0,
                    'monthly_limit_usd': 500.0,
                    'alert_threshold_pct': 80,
                    'warning_threshold_pct': 90
                }
            }

    def get_model_pricing(self, model: str) -> Dict[str, float]:
        """
        Get pricing for specific model.

        Args:
            model: Model identifier

        Returns:
            Dict with pricing rates per million tokens
        """
        models = self.config.get('models', {})

        # Try exact match first
        if model in models:
            return models[model]

        # Try partial match (e.g., "claude-sonnet-4" matches "claude-sonnet-4-20250514")
        for model_key, pricing in models.items():
            if model in model_key or model_key in model:
                return pricing

        # Fallback to default
        return models.get('default', {
            'input_per_mtok': 3.00,
            'output_per_mtok': 15.00,
            'cache_write_per_mtok': 3.75,
            'cache_read_per_mtok': 0.30
        })

    def calculate_cost(self, usage: TokenUsage, model: Optional[str] = None) -> float:
        """
        Calculate cost for token usage.

        Args:
            usage: TokenUsage object with token counts
            model: Model name (uses usage.model if not provided)

        Returns:
            Total cost in USD
        """
        if model is None:
            model = usage.model or 'default'

        pricing = self.get_model_pricing(model)

        # Calculate costs per component (rates are per million tokens)
        input_cost = (usage.input_tokens / 1_000_000) * pricing.get('input_per_mtok', 0)
        output_cost = (usage.output_tokens / 1_000_000) * pricing.get('output_per_mtok', 0)
        cache_write_cost = (usage.cache_write_tokens / 1_000_000) * pricing.get('cache_write_per_mtok', 0)
        cache_read_cost = (usage.cache_read_tokens / 1_000_000) * pricing.get('cache_read_per_mtok', 0)

        total_cost = input_cost + output_cost + cache_write_cost + cache_read_cost

        return round(total_cost, 6)  # Round to 6 decimal places ($0.000001)

    def calculate_batch_cost(self, usages: list[TokenUsage], model: Optional[str] = None) -> Dict[str, Any]:
        """
        Calculate total cost for multiple API calls.

        Args:
            usages: List of TokenUsage objects
            model: Model name (if all calls use same model)

        Returns:
            Dict with breakdown and total
        """
        total_cost = 0.0
        total_input = 0
        total_output = 0
        total_cache_read = 0
        total_cache_write = 0

        for usage in usages:
            call_model = model or usage.model or 'default'
            cost = self.calculate_cost(usage, call_model)

            total_cost += cost
            total_input += usage.input_tokens
            total_output += usage.output_tokens
            total_cache_read += usage.cache_read_tokens
            total_cache_write += usage.cache_write_tokens

        return {
            'total_cost': round(total_cost, 6),
            'total_input_tokens': total_input,
            'total_output_tokens': total_output,
            'total_cache_read_tokens': total_cache_read,
            'total_cache_write_tokens': total_cache_write,
            'total_tokens': total_input + total_output,
            'call_count': len(usages)
        }

    def estimate_remaining_budget(self, current_cost: float, period: str = "monthly") -> Dict[str, Any]:
        """
        Calculate remaining budget for period.

        Args:
            current_cost: Current spending in period
            period: "daily" or "monthly"

        Returns:
            Dict with budget info
        """
        budget_config = self.config.get('budget', {})

        if period == "daily":
            limit = budget_config.get('daily_limit_usd', 50.0)
        else:
            limit = budget_config.get('monthly_limit_usd', 500.0)

        remaining = limit - current_cost
        percent_used = (current_cost / limit * 100) if limit > 0 else 0

        alert_threshold = budget_config.get('alert_threshold_pct', 80)
        warning_threshold = budget_config.get('warning_threshold_pct', 90)

        status = 'ok'
        if percent_used >= warning_threshold:
            status = 'critical'
        elif percent_used >= alert_threshold:
            status = 'warning'

        return {
            'limit': limit,
            'current': current_cost,
            'remaining': remaining,
            'percent_used': round(percent_used, 2),
            'status': status,
            'period': period
        }

    def check_budget_alert(self, current_cost: float, period: str = "monthly") -> Optional[str]:
        """
        Check if budget alert should be raised.

        Args:
            current_cost: Current spending
            period: "daily" or "monthly"

        Returns:
            Alert message or None
        """
        budget_info = self.estimate_remaining_budget(current_cost, period)

        if budget_info['status'] == 'critical':
            return f"⚠️ CRITICAL: {period.capitalize()} budget {budget_info['percent_used']:.1f}% used (${current_cost:.2f} / ${budget_info['limit']:.2f})"
        elif budget_info['status'] == 'warning':
            return f"⚠️ WARNING: {period.capitalize()} budget {budget_info['percent_used']:.1f}% used (${current_cost:.2f} / ${budget_info['limit']:.2f})"

        return None

    def get_budget_status(self, db) -> Dict[str, Any]:
        """
        Get current budget status from database.

        Args:
            db: MetricsDatabase instance

        Returns:
            Dict with daily and monthly budget status
        """
        now = datetime.now()

        # Daily budget
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = now
        daily_summary = db.get_cost_summary(
            today_start.isoformat(),
            today_end.isoformat()
        )
        daily_cost = daily_summary.get('total_cost', 0.0)
        daily_budget = self.estimate_remaining_budget(daily_cost, 'daily')

        # Monthly budget
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        monthly_summary = db.get_cost_summary(
            month_start.isoformat(),
            now.isoformat()
        )
        monthly_cost = monthly_summary.get('total_cost', 0.0)
        monthly_budget = self.estimate_remaining_budget(monthly_cost, 'monthly')

        return {
            'daily': daily_budget,
            'monthly': monthly_budget,
            'alerts': [
                alert for alert in [
                    self.check_budget_alert(daily_cost, 'daily'),
                    self.check_budget_alert(monthly_cost, 'monthly')
                ] if alert is not None
            ]
        }

    def estimate_cost_for_tokens(self, input_tokens: int, output_tokens: int,
                                 model: str = 'default') -> float:
        """
        Estimate cost for given token counts.

        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            model: Model name

        Returns:
            Estimated cost in USD
        """
        usage = TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=0,
            cache_write_tokens=0
        )

        return self.calculate_cost(usage, model)

    def get_cost_breakdown(self, usage: TokenUsage, model: Optional[str] = None) -> Dict[str, Any]:
        """
        Get detailed cost breakdown.

        Args:
            usage: TokenUsage object
            model: Model name

        Returns:
            Dict with itemized costs
        """
        if model is None:
            model = usage.model or 'default'

        pricing = self.get_model_pricing(model)

        input_cost = (usage.input_tokens / 1_000_000) * pricing.get('input_per_mtok', 0)
        output_cost = (usage.output_tokens / 1_000_000) * pricing.get('output_per_mtok', 0)
        cache_write_cost = (usage.cache_write_tokens / 1_000_000) * pricing.get('cache_write_per_mtok', 0)
        cache_read_cost = (usage.cache_read_tokens / 1_000_000) * pricing.get('cache_read_per_mtok', 0)

        return {
            'model': model,
            'input_tokens': usage.input_tokens,
            'input_cost': round(input_cost, 6),
            'output_tokens': usage.output_tokens,
            'output_cost': round(output_cost, 6),
            'cache_write_tokens': usage.cache_write_tokens,
            'cache_write_cost': round(cache_write_cost, 6),
            'cache_read_tokens': usage.cache_read_tokens,
            'cache_read_cost': round(cache_read_cost, 6),
            'total_cost': round(input_cost + output_cost + cache_write_cost + cache_read_cost, 6),
            'cache_savings': round(
                (usage.cache_read_tokens / 1_000_000) * (pricing.get('input_per_mtok', 0) - pricing.get('cache_read_per_mtok', 0)),
                6
            ) if usage.cache_read_tokens > 0 else 0.0
        }


# Singleton instance
_calculator_instance = None
_calculator_lock = threading.Lock()


def get_cost_calculator(config_path: Optional[str] = None) -> CostCalculator:
    """Get singleton cost calculator instance"""
    global _calculator_instance

    if _calculator_instance is None:
        with _calculator_lock:
            if _calculator_instance is None:
                _calculator_instance = CostCalculator(config_path)

    return _calculator_instance
