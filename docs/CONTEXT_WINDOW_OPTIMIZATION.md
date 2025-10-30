# Context Window Optimization Guide

**Complete guide to understanding and optimizing context window usage in Context Foundry builds**

## Table of Contents

- [Overview](#overview)
- [Key Concepts](#key-concepts)
- [Performance Zones](#performance-zones)
- [Budget Allocations](#budget-allocations)
- [Using the System](#using-the-system)
- [Interpreting Reports](#interpreting-reports)
- [Optimization Strategies](#optimization-strategies)
- [Troubleshooting](#troubleshooting)
- [API Reference](#api-reference)

## Overview

Context Foundry now includes comprehensive context window budget monitoring that tracks token usage across all build phases. This feature helps you:

- **Identify performance bottlenecks**: See which phases consume excessive context
- **Optimize builds**: Stay in the "smart zone" (0-40%) for optimal model performance
- **Prevent failures**: Avoid the "dumb zone" (40-100%) where model performance degrades
- **Track improvements**: Monitor context efficiency over time

### Research Background

Recent research shows that large language models perform optimally when operating at **0-40% of their context window** (the "smart zone"). Performance degrades significantly at 40-100% usage (the "dumb zone"), with reasoning quality, accuracy, and response quality all suffering.

Context Foundry's monitoring system is designed to keep your builds in the smart zone.

## Key Concepts

### Context Window

The **context window** is the maximum amount of text (measured in tokens) that a model can process at once. Different models have different context windows:

- **Claude Sonnet 4**: 200,000 tokens
- **GPT-4 Turbo**: 128,000 tokens
- **GPT-4**: 128,000 tokens

### Tokens

**Tokens** are the basic units of text that models process. Roughly:
- 1 token ≈ 4 characters in English
- 1 token ≈ ¾ of a word
- 100 tokens ≈ 75 words

Example: "Hello, world!" = ~3 tokens

### Budget Allocation

Each build phase has a **token budget** (percentage of the total context window):

| Phase | Budget | Tokens (200K window) | Purpose |
|-------|--------|---------------------|---------|
| Scout | 7% | 14,000 | Requirements gathering |
| Architect | 7% | 14,000 | System design |
| Builder | 20% | 40,000 | Code implementation |
| Test | 20% | 40,000 | Validation & testing |
| Documentation | 5% | 10,000 | Docs generation |
| Deploy | 3% | 6,000 | Deployment tasks |
| Feedback | 5% | 10,000 | Learnings extraction |

**Total allocated: ~67%**, leaving ~33% buffer for safety.

## Performance Zones

### Smart Zone (0-40%) ✅

**Optimal Performance**
- Excellent reasoning quality
- Accurate responses
- Fast processing
- Minimal errors

**Target**: Keep all phases in this zone

### Dumb Zone (40-80%) ⚠️

**Degraded Performance**
- Reduced reasoning quality
- More errors and hallucinations
- Slower processing
- Less accurate responses

**Action**: Optimize to return to smart zone

### Critical Zone (80-100%) 🚨

**Severe Degradation**
- Major quality issues
- Frequent failures
- Very slow processing
- High error rates

**Action**: Immediate optimization required

## Using the System

### Automatic Monitoring

Context monitoring is **automatic** - no configuration needed. Every build automatically tracks:

- Token usage per phase
- Zone detection (smart/dumb/critical)
- Budget compliance
- Warnings and recommendations

Results are saved to `.context-foundry/session-summary.json`.

### Viewing Reports

#### During Build

Monitor real-time usage (if using TUI):

```bash
cf-monitor
```

The dashboard shows live token usage gauges.

#### After Build

Generate a comprehensive report:

```python
from tools.context_budget import ContextBudgetReporter
import json

# Load session summary
with open('.context-foundry/session-summary.json') as f:
    summary = json.load(f)

# Generate report
reporter = ContextBudgetReporter()
print(reporter.generate_context_report(summary['context_metrics']))
```

#### Command Line Report

```bash
python3 -c "
import json
from tools.context_budget import ContextBudgetReporter

summary = json.load(open('.context-foundry/session-summary.json'))
reporter = ContextBudgetReporter()
print(reporter.generate_context_report(summary.get('context_metrics', {})))
"
```

## Interpreting Reports

### Sample Report

```
Context Window Budget Report
═══════════════════════════════════════════════════════════════════════════

Model: Claude Sonnet 4 (200,000 tokens)

Phase Analysis:
┌─────────────────┬──────────┬──────────┬────────┬────────────┐
│ Phase           │ Used     │ Budget   │ Usage  │ Zone       │
├─────────────────┼──────────┼──────────┼────────┼────────────┤
│ Scout           │ 12.0K    │ 14.0K    │  6.0%  │ ✅ Smart   │
│ Architect       │ 85.0K    │ 14.0K    │ 42.5%  │ ⚠️  Dumb   │
│ Builder         │ 45.0K    │ 40.0K    │ 22.5%  │ ✅ Smart   │
│ Test            │ 30.0K    │ 40.0K    │ 15.0%  │ ✅ Smart   │
└─────────────────┴──────────┴──────────┴────────┴────────────┘

Peak Usage: 85,000 tokens (42.5%) during Architect phase ⚠️
Average Usage: 20.9%
Smart Zone: 75.0% of phases

Recommendations:
  • Architect phase exceeded budget by 71K tokens
  • Consider breaking architecture into smaller chunks
  • Use sub-agents to isolate context per module
```

### Reading the Table

- **Phase**: Build phase name
- **Used**: Actual tokens consumed
- **Budget**: Allocated token budget
- **Usage**: Percentage of total context window
- **Zone**: Performance zone (✅ Smart, ⚠️ Dumb, 🚨 Critical)

### Key Metrics

- **Peak Usage**: Highest token usage across all phases
- **Average Usage**: Mean usage percentage
- **Smart Zone %**: Percentage of phases in optimal zone

### Warning Indicators

- ✅ **Green (Smart)**: Everything optimal
- ⚠️ **Yellow (Dumb)**: Phase needs optimization
- 🚨 **Red (Critical)**: Immediate action required

## Optimization Strategies

### Phase-Specific Strategies

#### Scout Phase (Target: 7% / 14K tokens)

**If exceeded**:
- Reduce task description verbosity
- Focus on essential requirements only
- Use bullet points instead of paragraphs
- Skip unnecessary background information

**Example optimization**:
```diff
- Task: "Create a comprehensive web application with user authentication,
-  real-time updates, responsive design, database integration, API endpoints,
-  admin dashboard, user profiles, notification system, and analytics..."

+ Task: "Create web app:
+ - User auth (login/register)
+ - Real-time updates (WebSocket)
+ - REST API
+ - Admin dashboard
+ - Analytics"
```

#### Architect Phase (Target: 7% / 14K tokens)

**If exceeded**:
- Break into modular sub-architectures
- Use sub-agents for complex components
- Reference external design docs instead of inlining
- Focus on high-level design first, details later

**Example optimization**:
```python
# Instead of one massive architecture phase:
# 1. High-level architecture (7K tokens)
# 2. Spawn sub-agents for modules:
#    - Database schema (sub-agent)
#    - API design (sub-agent)
#    - Frontend structure (sub-agent)
```

#### Builder Phase (Target: 20% / 40K tokens)

**If exceeded**:
- Use parallel builders (already implemented)
- Implement incrementally (files one at a time)
- Clear context between file creations
- Use code generation templates

#### Test Phase (Target: 20% / 40K tokens)

**If exceeded**:
- Run tests in batches
- Use test summaries instead of full output
- Filter test logs to errors only
- Parallel test execution

### General Optimization Techniques

#### 1. Context Chunking

Break large operations into smaller chunks:

```python
# Bad: Load entire codebase
context = read_all_files('src/')  # 100K tokens!

# Good: Load only what's needed
context = read_file('src/module.py')  # 5K tokens
```

#### 2. Summarization

Summarize instead of including full content:

```python
# Bad: Include full test output
output = run_tests()  # 50K tokens of logs

# Good: Summarize results
summary = f"Tests: {passed}/{total} passed in {duration}s"  # 50 tokens
```

#### 3. Sub-Agents

Use isolated agents for complex tasks:

```python
# Each sub-agent has its own clean context window
agent1 = spawn_agent(task="Design database schema")
agent2 = spawn_agent(task="Design API routes")
agent3 = spawn_agent(task="Design frontend")
```

#### 4. Prompt Caching

Reuse cached prompts when possible (supported by Claude):

```python
# Cache frequently used system prompts
# Cached tokens don't count toward context budget
```

## Troubleshooting

### Problem: Phase consistently exceeds budget

**Symptoms**: Warning messages about budget exceeded

**Solutions**:
1. Check if task complexity matches phase allocation
2. Break task into smaller sub-tasks
3. Use sub-agents for complex components
4. Reduce verbosity in task descriptions

### Problem: Multiple phases in dumb zone

**Symptoms**: Overall smart zone % < 70%

**Solutions**:
1. Review task scope - may be too complex
2. Implement incremental building
3. Use parallel execution
4. Clear context between phases

### Problem: Critical zone warnings

**Symptoms**: 🚨 Critical zone indicators

**Solutions**:
1. **Immediate**: Stop and redesign approach
2. Use multiple sub-agents instead of one agent
3. Break into smaller, focused tasks
4. Consider if task is too large for single build

### Problem: Token counting seems inaccurate

**Symptoms**: Reported usage doesn't match expectations

**Solutions**:
1. Check if tiktoken is installed: `pip install tiktoken`
2. Verify model name is correct in config
3. Check for hidden whitespace or formatting
4. Review `.context-foundry/session-summary.json` for details

## API Reference

### ContextBudgetMonitor

```python
from tools.context_budget import ContextBudgetMonitor

monitor = ContextBudgetMonitor(
    context_window_size=200000,
    model='claude-sonnet-4'
)

# Check phase usage
analysis = monitor.check_phase('scout', tokens_used=12000)

# Get phase budget
budget = monitor.get_budget_for_phase('architect')

# Check if in smart zone
is_optimal = monitor.is_in_smart_zone(50000)

# Export to session summary
metrics = monitor.export_to_session_summary()
```

### TokenCounter

```python
from tools.context_budget import TokenCounter

counter = TokenCounter(model='claude-sonnet-4')

# Estimate tokens in text
tokens = counter.estimate_tokens("Your text here")

# Count tokens in file
file_tokens = counter.count_file_tokens(Path('script.py'))

# Count tokens in messages
message_tokens = counter.count_message_tokens([
    {"role": "user", "content": "Hello"},
    {"role": "assistant", "content": "Hi!"}
])

# Get context window size
window_size = counter.get_context_window_size()
```

### ContextBudgetReporter

```python
from tools.context_budget import ContextBudgetReporter

reporter = ContextBudgetReporter()

# Generate text report
report = reporter.generate_context_report(context_metrics)

# Generate visualization
viz = reporter.visualize_context_usage(context_metrics)

# Get optimization suggestions
suggestions = reporter.get_optimization_suggestions(context_metrics)

# Export markdown report
markdown = reporter.export_markdown_report(
    context_metrics,
    output_path='context_report.md'
)
```

## Best Practices

### 1. Monitor Every Build

Always check the context report after builds to identify optimization opportunities.

### 2. Stay in Smart Zone

Aim for 80%+ of phases in smart zone (0-40% usage).

### 3. Optimize Early

Address dumb zone issues immediately - they compound over time.

### 4. Use Budgets as Guidelines

Budgets are targets, not hard limits. Brief exceedances are okay, but consistent violations need attention.

### 5. Document Optimizations

When you optimize a phase, document what worked in your project notes.

### 6. Track Trends

Compare context usage across builds to identify improvements or regressions.

## Examples

### Example 1: Basic Monitoring

```python
from tools.context_budget import ContextBudgetMonitor

# Initialize monitor
monitor = ContextBudgetMonitor()

# Track phases
scout_analysis = monitor.check_phase('scout', 15000)
print(f"Scout zone: {scout_analysis.zone.value}")

if scout_analysis.zone.value != 'smart':
    print(f"Warnings: {scout_analysis.warnings}")
    print(f"Recommendations: {scout_analysis.recommendations}")
```

### Example 2: Generate Report

```python
import json
from tools.context_budget import ContextBudgetReporter

# Load session summary
with open('.context-foundry/session-summary.json') as f:
    summary = json.load(f)

# Generate and print report
reporter = ContextBudgetReporter()
context_metrics = summary.get('context_metrics', {})
report = reporter.generate_context_report(context_metrics)
print(report)

# Get optimization suggestions
suggestions = reporter.get_optimization_suggestions(context_metrics)
for suggestion in suggestions:
    print(f"  → {suggestion}")
```

### Example 3: Custom Token Counting

```python
from tools.context_budget import TokenCounter
from pathlib import Path

counter = TokenCounter()

# Count tokens in project
total_tokens = counter.count_directory_tokens(
    Path('src/'),
    pattern='**/*.py'
)
print(f"Total project tokens: {total_tokens:,}")

# Check if fits in context
context_size = counter.get_context_window_size()
if total_tokens > context_size * 0.4:
    print("⚠️  Project too large for single context window")
```

## Conclusion

Context window optimization is crucial for maintaining high-quality autonomous builds. By monitoring usage, staying in the smart zone, and following optimization strategies, you can ensure your builds remain fast, accurate, and reliable.

For questions or issues, see the main Context Foundry documentation or open an issue on GitHub.

---

**Version**: 2.1.0
**Last Updated**: January 2025
**Related Docs**: [README.md](../README.md), [USER_GUIDE.md](../USER_GUIDE.md)
