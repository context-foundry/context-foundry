# Active Context Budget Monitoring

**Implementation Date:** 2025-01-13
**Based on Research:** Jeff Huntley (Ralph Wiggum), Vibov (Agentic RAG)

## Overview

Context Foundry now features **active, proactive context window budget monitoring** integrated directly into the orchestrator workflow. This system moves from passive token awareness to active budget enforcement with real-time warnings.

## What Changed

### Before (Passive)
- ✅ Token counts in tool outputs
- ✅ Smart truncation to prevent overflow
- ✅ Relative paths for token savings
- ❌ No real-time percentage tracking
- ❌ No quality zone warnings
- ❌ No proactive pre-checks

### After (Active)
- ✅ Real-time context percentage tracking
- ✅ **Proactive warnings BEFORE phases start**
- ✅ Quality zone detection (SMART/DUMB/CRITICAL)
- ✅ Per-phase budget allocation enforcement
- ✅ Automatic session-summary.json updates
- ✅ CLI tool for agent integration
- ✅ Exit codes for decision-making

## Research-Backed Design

### Performance Zones (Jeff Huntley)

Based on empirical research with Ralph Wiggum technique:

```
SMART ZONE (0-40%)     ✅ Optimal model performance
DUMB ZONE (40-80%)     ⚠️  Degraded reasoning & quality
CRITICAL ZONE (80%+)   🚨 Severe performance issues
```

**Key Quote:**
> "You get better results if you use less context because the attention is spread over less noise. Even with 10M token windows, less is better."

### Tool Implementation > Prompts (Vibov)

**70% of agent quality comes from HOW tools are implemented:**

1. **Truncation with recovery instructions**
   - ❌ Bad: "Output truncated"
   - ✅ Good: "Output truncated at line 5000. Use: read file.py --offset 5000"

2. **Relative paths** (20-30% token savings)
   - ❌ Bad: `/Users/name/homelab/context-foundry/tools/script.py`
   - ✅ Good: `tools/script.py`

3. **Explicit limits and timeouts**
   - Every tool MUST have these

4. **Semantic tags for clarity**
   - `dir src/`, `file main.py`, `match:def`, `match:call`

### Sub-Agents as Garbage Collection (Jeff)

**Quote:**
> "Spawn a green thread... I don't want 200K tokens appended to the main loop"

**Use sub-agents to:**
- Isolate large operations (test execution, file analysis)
- Return only summary to main context
- Prevent context pollution
- Act like garbage collection for tokens

This is **why Phase 2.5 uses parallel builders** - context management!

## Budget Allocations

| Phase | Budget | Tokens (200K) | Why |
|-------|--------|---------------|-----|
| Scout | 7% | 14K | Requirements gathering |
| Architect | 7% | 14K | System design |
| **Builder** | **20%** | **40K** | Code generation (largest) |
| **Test** | **20%** | **40K** | Validation + outputs |
| Documentation | 5% | 10K | Docs generation |
| Deploy | 3% | 6K | Deployment |
| Feedback | 5% | 10K | Learnings extraction |
| System Prompts | 15% | 30K | Base orchestrator |

**Total Allocated:** 82%
**Reserve Buffer:** 18% (36K tokens)

## CLI Tool Usage

### For Agents (in orchestrator_prompt.txt)

**Check BEFORE phase:**
```bash
python3 tools/check_context_budget.py --phase scout --check-before
```

Returns:
- Exit 0: ✅ SMART zone (safe to proceed)
- Exit 1: ⚠️  DUMB zone (warning, consider optimization)
- Exit 2: 🚨 CRITICAL zone (MUST use sub-agent)

**Record AFTER phase:**
```bash
SCOUT_TOKENS=$(python3 -c "
from tools.context_budget import TokenCounter
from pathlib import Path
counter = TokenCounter()
print(counter.count_file_tokens(Path('.context-foundry/scout-report.md')))
")

python3 tools/check_context_budget.py --phase scout --tokens $SCOUT_TOKENS
```

**Generate report:**
```bash
python3 tools/check_context_budget.py --report
```

## Integration Points

### 1. Orchestrator Prompt

Added context budget section at top explaining:
- Performance zones
- Budget allocations
- When to use sub-agents
- Tool implementation best practices

### 2. Phase Tracking

**Every major phase now:**
1. Checks budget BEFORE starting
2. Records actual usage AFTER completing
3. Updates session-summary.json automatically

### 3. Build Report Generation (NEW)

**Phase 8 (Feedback) automatically generates context budget report:**

At the end of every build, after pattern sharing completes:
```bash
python3 tools/check_context_budget.py --report > .context-foundry/context-budget-report.md
```

**Report location:** `.context-foundry/context-budget-report.md`

**Users can review:**
- Token usage per phase
- Which phases stayed in SMART zone
- Budget compliance
- Optimization recommendations

**Preserved in git** alongside other build artifacts (scout-report.md, test-final-report.md, etc.)

### 4. Session Summary

New sections in `.context-foundry/session-summary.json`:
```json
{
  "context_budget_report": ".context-foundry/context-budget-report.md",
  "context_metrics": {
    "max_context_window": 200000,
    "model": "claude-sonnet-4",
    "by_phase": {
      "phase_scout": {
        "tokens_used": 12000,
        "percentage": 6.0,
        "zone": "smart",
        "budget_allocated": 14000,
        "budget_remaining": 2000,
        "warnings": [],
        "recommendations": []
      }
    },
    "overall": {
      "peak_usage_tokens": 45000,
      "peak_usage_percentage": 22.5,
      "peak_phase": "builder",
      "avg_usage_percentage": 15.8,
      "smart_zone_percentage": 100.0,
      "total_phases": 4
    }
  }
}
```

## Example Output

### Pre-Check (Proactive Warning)
```
╔════════════════════════════════════════════════════════════════════════════╗
║                     CONTEXT BUDGET - BUILD INFORMATION                     ║
╚════════════════════════════════════════════════════════════════════════════╝

  Session ID:   context-foundry
  Task:         Build comprehensive metrics and cost tracking system
  Mode:         add_feature
  Directory:    ~/homelab/context-foundry
  Started:      2025-01-13 10:00:00 UTC
  Status:       In_Progress - Phase 1/7 (Scout)
                Analyzing task requirements
  GitHub:       PR #7
                https://github.com/snedea/context-foundry/pull/7

╔══════════════════════════════════════════════════════╗
║  Context Budget Pre-Check: SCOUT                  ║
╚══════════════════════════════════════════════════════╝

Estimated tokens: 14,000
Budget allocated: 14,000
Context usage:    7.0% of 200K window
Performance zone: SMART

✅ SAFE: Operating in smart zone for optimal performance
```

### Post-Check (Recording Actual)
```
╔════════════════════════════════════════════════════════════════════════════╗
║                     CONTEXT BUDGET - BUILD INFORMATION                     ║
╚════════════════════════════════════════════════════════════════════════════╝

  Session ID:   context-foundry
  Task:         Build comprehensive metrics and cost tracking system
  Mode:         add_feature
  Directory:    ~/homelab/context-foundry
  Started:      2025-01-13 10:00:00 UTC
  Status:       In_Progress - Phase 3/7 (Builder)
                Building implementation files
  GitHub:       PR #7
                https://github.com/snedea/context-foundry/pull/7

╔══════════════════════════════════════════════════════╗
║  Context Budget Report: BUILDER                   ║
╚══════════════════════════════════════════════════════╝

Actual tokens used: 45,000
Budget allocated:   40,000
Context usage:      22.5%
Performance zone:   SMART
Budget exceeded by: 5,000 tokens

⚠️  WARNINGS:
  • Builder phase exceeded budget by 5,000 tokens (5.0K)

💡 RECOMMENDATIONS:
  • Consider breaking builder into smaller sub-phases or reducing scope
```

### Full Report
```
╔════════════════════════════════════════════════════════════════════════════╗
║                     CONTEXT BUDGET - BUILD INFORMATION                     ║
╚════════════════════════════════════════════════════════════════════════════╝

  Session ID:   context-foundry
  Task:         Build comprehensive metrics and cost tracking system
  Mode:         add_feature
  Directory:    ~/homelab/context-foundry
  Started:      2025-01-13 10:00:00 UTC
  Status:       Completed (55.0 minutes)
  GitHub:       PR #7
                https://github.com/snedea/context-foundry/pull/7

Context Window Budget Report
═══════════════════════════════════════════════════════════════════════════

Model: claude-sonnet-4 (200,000 tokens)

Phase Analysis:
┌─────────────────┬──────────┬──────────┬────────┬────────────┐
│ Phase           │ Used     │ Budget   │ Usage  │ Zone       │
├─────────────────┼──────────┼──────────┼────────┼────────────┤
│ scout           │ 12.0K    │ 14.0K    │   6.0% │ ✅ Smart    │
│ architect       │ 13.5K    │ 14.0K    │   6.8% │ ✅ Smart    │
│ builder         │ 45.0K    │ 40.0K    │  22.5% │ ✅ Smart    │
│ test            │ 38.0K    │ 40.0K    │  19.0% │ ✅ Smart    │
└─────────────────┴──────────┴──────────┴────────┴────────────┘

Peak Usage: 45,000 tokens (22.5%) during builder phase ✅
Average Usage: 13.6%
Smart Zone: 100.0% of phases

Recommendations: All phases within optimal budget ✅
```

## Design Decisions

### Why Exit Codes?

Agents can make decisions based on exit codes:
```bash
python3 tools/check_context_budget.py --phase builder --check-before
if [ $? -eq 2 ]; then
    echo "CRITICAL: Using sub-agent for Builder"
    # Spawn isolated builder
else
    echo "SAFE: Proceeding with normal Builder"
    # Continue normally
fi
```

### Why Proactive Checks?

Jeff's key insight: **Check BEFORE, not AFTER**
- Prevents entering dumb zone in first place
- Allows strategic use of sub-agents
- Better than reactive "oops, we're at 90%"

### Why Track Per-Phase?

Different phases have different characteristics:
- Scout: Research-heavy (documents, web searches)
- Architect: Design-heavy (reasoning, planning)
- Builder: Code-heavy (large files, multiple modules)
- Test: Output-heavy (test results, logs, screenshots)

Per-phase tracking allows phase-specific optimization.

## Adoption from Transcripts

### From Ralph Wiggum Episode (Jeff Huntley)

1. ✅ **Back Pressure System** - Test/compile friction to stop bad code
2. ✅ **Context Budget Allocation** - 7% specs, 7% state, 20% builder, etc.
3. ✅ **Sub-Agents as Garbage Collection** - Isolated contexts for large ops
4. ✅ **Smart vs Dumb Zone** - 0-40% optimal, 40%+ degraded
5. ✅ **Proactive Monitoring** - Check before operations, not after

### From Agentic RAG Episode (Vibov & Dexter)

1. ✅ **Tool Implementation > Prompts** - 70% quality from tool design
2. ✅ **Truncation with Recovery** - Explicit instructions on how to continue
3. ✅ **Relative Paths** - 20-30% token savings
4. ✅ **Explicit Limits & Timeouts** - Every tool has these
5. ✅ **Semantic Tags** - Clear output formatting for agents

## Impact

**Before:** Context management was reactive - truncate when too large
**After:** Context management is proactive - prevent overflow before it happens

**Before:** No visibility into zone status during build
**After:** Real-time monitoring with warnings at phase transitions

**Before:** No guidance on when to use sub-agents
**After:** Explicit recommendations based on context usage

## Future Enhancements

1. **Auto Sub-Agent Spawning** - Automatically use sub-agent when pre-check returns CRITICAL
2. **Dynamic Budget Adjustment** - Learn optimal budgets per project type
3. **Context Compression** - Automatically summarize when approaching limits
4. **Visual Dashboard** - Real-time TUI showing context usage per phase
5. **Pattern Learning** - Track which phases consistently exceed budget

## Testing

```bash
# Test CLI tool
python3 tools/check_context_budget.py --help
python3 tools/check_context_budget.py --phase scout --check-before
python3 tools/check_context_budget.py --phase builder --tokens 45000
python3 tools/check_context_budget.py --report

# Test in real build
cd /tmp/test-project
python3 /Users/name/homelab/context-foundry/tools/check_context_budget.py --phase scout --check-before
```

## References

- **Ralph Wiggum Technique**: Jeff Huntley, "AI That Works" podcast
- **Agentic RAG**: Vibov & Dexter, Episode #28
- **Context Budget Module**: `tools/context_budget/`
- **CLI Tool**: `tools/check_context_budget.py`
- **Orchestrator Integration**: Lines 267-332, 386-401, 521-540 in orchestrator_prompt.txt

## Summary

Context Foundry now implements **active context budget monitoring** based on research from industry leaders. This moves from reactive token management to proactive budget enforcement, resulting in:

- ✅ Better model performance (staying in SMART zone)
- ✅ Predictable context usage
- ✅ Strategic use of sub-agents
- ✅ Visibility into budget health
- ✅ Research-backed best practices

**Key Insight from Transcripts:**
> "Context engineering isn't about clever prompts—it's about smart tool design, explicit back pressure, and strategic context budget allocation."
