# Context Budget Monitoring

Comprehensive context window budget tracking and monitoring for Context Foundry builds.

## Overview

This module provides real-time tracking of token usage across all build phases, identifying when agents are operating in the "smart zone" (0-40% context) vs "dumb zone" (40-100% context), with actionable warnings for optimization.

## Features

- **Accurate Token Counting**: Uses tiktoken library for precise token estimation
- **Budget Allocation**: Phase-specific budgets (Scout: 7%, Architect: 7%, Builder: 20%, etc.)
- **Zone Detection**: Real-time identification of smart (0-40%), dumb (40-80%), and critical (80-100%) zones
- **Warning System**: Actionable alerts when budgets exceeded or entering dumb zone
- **Human-Readable Reports**: ASCII tables and charts for easy understanding
- **Session Integration**: Seamlessly integrates with session-summary.json

## Quick Start

```python
from tools.context_budget import ContextBudgetMonitor, TokenCounter

# Initialize monitor
monitor = ContextBudgetMonitor(context_window_size=200000, model='claude-sonnet-4')

# Count tokens in text
counter = TokenCounter()
tokens = counter.estimate_tokens("Your text here")

# Check phase usage
analysis = monitor.check_phase('scout', tokens_used=12000)
print(f"Zone: {analysis.zone.value}")
print(f"Warnings: {analysis.warnings}")

# Export to session summary
metrics = monitor.export_to_session_summary()
```

## Modules

### monitor.py
Core monitoring logic with budget tracking and zone detection.

**Key Classes:**
- `ContextBudgetMonitor`: Main monitoring class
- `PhaseAnalysis`: Analysis results for a phase
- `ContextZone`: Enum for smart/dumb/critical zones

### token_counter.py
Token counting utilities with tiktoken integration.

**Key Functions:**
- `estimate_tokens(text)`: Estimate tokens in text
- `count_file_tokens(path)`: Count tokens in file
- `count_message_tokens(messages)`: Count tokens in message array

### report.py
Reporting and visualization utilities.

**Key Classes:**
- `ContextBudgetReporter`: Generate reports and visualizations

## Usage Examples

### Basic Monitoring

```python
from tools.context_budget import ContextBudgetMonitor

monitor = ContextBudgetMonitor()

# Check Scout phase
analysis = monitor.check_phase('scout', 15000)
if analysis.zone.value == 'dumb':
    print(f"Warning: {analysis.warnings}")
    print(f"Recommendations: {analysis.recommendations}")
```

### Generate Report

```python
from tools.context_budget import ContextBudgetReporter

reporter = ContextBudgetReporter()

# Assuming you have context_metrics from session-summary.json
report = reporter.generate_context_report(context_metrics)
print(report)
```

### Token Counting

```python
from tools.context_budget import TokenCounter
from pathlib import Path

counter = TokenCounter(model='claude-sonnet-4')

# Count tokens in file
tokens = counter.count_file_tokens(Path('script.py'))

# Count tokens in directory
total = counter.count_directory_tokens(Path('src/'), pattern='**/*.py')
```

## Budget Allocations

Default budget allocations (percentage of context window):

| Phase | Budget | Tokens (200K window) |
|-------|--------|---------------------|
| Scout | 7% | 14,000 |
| Architect | 7% | 14,000 |
| Builder | 20% | 40,000 |
| Test | 20% | 40,000 |
| Documentation | 5% | 10,000 |
| Deploy | 3% | 6,000 |
| Feedback | 5% | 10,000 |
| System Prompts | 15% | 30,000 |

## Performance Zones

- **Smart Zone (0-40%)**: Optimal model performance
- **Dumb Zone (40-80%)**: Degraded reasoning and performance
- **Critical Zone (80-100%)**: Severe performance degradation

## Integration with Session Summary

The module automatically exports metrics to `session-summary.json`:

```json
{
  "context_metrics": {
    "max_context_window": 200000,
    "model": "claude-sonnet-4",
    "by_phase": {
      "phase_scout": {
        "tokens_used": 12000,
        "percentage": 6.0,
        "zone": "smart",
        "budget_allocated": 14000,
        "warnings": []
      }
    },
    "overall": {
      "peak_usage_tokens": 85000,
      "peak_usage_percentage": 42.5,
      "smart_zone_percentage": 75.0
    }
  }
}
```

## Dependencies

- **tiktoken** >= 0.5.0 (for accurate token counting)

Install with:
```bash
pip install tiktoken
```

If tiktoken is not available, the module falls back to a char_count/4 heuristic (~75% accurate).

## Testing

Run tests with:
```bash
pytest tests/test_context_budget.py -v
```

## Documentation

For detailed usage guide, see: `docs/CONTEXT_WINDOW_OPTIMIZATION.md`

## License

Same as Context Foundry main project.
