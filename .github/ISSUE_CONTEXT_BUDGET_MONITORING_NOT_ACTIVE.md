# Context Budget Monitoring Not Active During Builds

## Issue Summary

The **Context Budget Monitoring** feature with real-time token tracking and smart/dumb zone detection (0-40% = optimal, 40-100% = degraded) is **not being executed** during autonomous builds, despite being fully implemented and documented.

## Status

- ✅ **Feature Implemented:** Yes (2025-01-13)
- ✅ **Tool Exists:** `tools/check_context_budget.py` works correctly
- ✅ **Documentation Complete:** `docs/ACTIVE_CONTEXT_BUDGET_MONITORING.md`
- ✅ **Orchestrator References:** Present in `tools/orchestrator_prompt.txt` (lines 273-274, 297-298, 453-461, 704-706, 1141-1143, 1565-1572, 2764-2800)
- ❌ **Actually Running:** No - not being called during builds
- ❌ **Metrics Collected:** No `context_metrics` in `session-summary.json`
- ❌ **Report Generated:** No `.context-foundry/context-budget-report.md` file

## Expected Behavior

According to `docs/ACTIVE_CONTEXT_BUDGET_MONITORING.md`, the system should:

### 1. **Real-Time Zone Tracking**
```
SMART ZONE (0-40%)     ✅ Optimal model performance
DUMB ZONE (40-80%)     ⚠️  Degraded reasoning & quality
CRITICAL ZONE (80%+)   🚨 Severe performance issues
```

### 2. **Proactive Warnings BEFORE Phases**
```bash
# Before Scout phase
python3 tools/check_context_budget.py --phase scout --check-before
# Returns:
# - Exit 0: ✅ SMART zone (safe to proceed)
# - Exit 1: ⚠️  DUMB zone (warning, consider optimization)
# - Exit 2: 🚨 CRITICAL zone (MUST use sub-agent)
```

### 3. **Recording AFTER Phases**
```bash
# After Scout phase
python3 tools/check_context_budget.py --phase scout --tokens $SCOUT_TOKENS
```

### 4. **Final Report Generation**
At end of Phase 8 (Feedback):
```bash
python3 tools/check_context_budget.py --report > .context-foundry/context-budget-report.md
```

### 5. **session-summary.json Integration**
Should include:
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

## Actual Behavior

### Verification (2025-11-02)

1. **Tool Works Correctly:**
   ```bash
   $ python3 tools/check_context_budget.py --help
   # ✅ Outputs help correctly
   ```

2. **No Metrics in session-summary.json:**
   ```bash
   $ cat .context-foundry/session-summary.json
   # ❌ No "context_metrics" or "context_budget_report" fields
   ```

3. **No Report File:**
   ```bash
   $ ls .context-foundry/context-budget-report.md
   # ❌ No such file or directory
   ```

4. **Attempting Manual Report:**
   ```bash
   $ python3 tools/check_context_budget.py --report
   # ❌ "No context metrics available yet. Run phases with --tokens flag to collect data."
   ```

## Root Cause

The orchestrator prompt (`tools/orchestrator_prompt.txt`) **references** the context budget monitoring commands but they are **NOT being executed** during autonomous builds via `/agents` command.

**Likely reasons:**
1. The bash commands may not be executing (agents skip them?)
2. The instructions might be in comments that agents ignore
3. The proactive checks might be optional and agents choose not to run them
4. Integration with the `/agents` workflow may be incomplete

## Impact

**Missing critical functionality:**
- ❌ No real-time visibility into context window usage
- ❌ No warnings when approaching dumb zone (40-80%)
- ❌ No alerts when entering critical zone (80%+)
- ❌ No proactive guidance on when to use sub-agents
- ❌ No post-build analysis of context budget efficiency
- ❌ No tracking of which phases exceed budget allocations

**Result:** Builds may unknowingly operate in the **dumb zone**, degrading model performance without any warnings or visibility.

## Verification Steps

To reproduce:

1. Check any recent build's session-summary.json:
   ```bash
   cat .context-foundry/session-summary.json | grep -i "context_metrics"
   # Should return nothing (bug)
   ```

2. Look for context budget report:
   ```bash
   ls .context-foundry/context-budget-report.md
   # Should not exist (bug)
   ```

3. Try to generate report manually:
   ```bash
   python3 tools/check_context_budget.py --report
   # Returns: "No context metrics available yet" (bug - no data collected)
   ```

## Proposed Fix

### Option 1: Enforce in Orchestrator
Modify `tools/orchestrator_prompt.txt` to make context budget checks **mandatory** rather than optional guidance. Ensure bash commands are actually executed.

### Option 2: Integrate into Phase Tracker
Add context budget tracking directly into the phase tracking system (`current-phase.json` updates) so it runs automatically without requiring bash execution.

### Option 3: Add to MCP Server
Integrate context budget tracking into the MCP server so it runs server-side during delegation, independent of orchestrator prompt compliance.

### Option 4: Validation Check
Add a validation step that fails builds if context budget monitoring didn't run, forcing compliance.

## Priority

**High** - This is a research-backed performance optimization feature (Jeff Huntley, Vibov) that was explicitly implemented but is not functioning. The 0-40% smart zone vs 40-100% dumb zone distinction directly impacts build quality.

## Related Documentation

- `docs/ACTIVE_CONTEXT_BUDGET_MONITORING.md` - Complete feature documentation
- `tools/context_budget/README.md` - Module documentation
- `tools/check_context_budget.py` - CLI tool (works correctly)
- `tools/orchestrator_prompt.txt` - Orchestrator integration (not executing)

## Research References

- **Jeff Huntley (Ralph Wiggum technique):** "You get better results if you use less context because the attention is spread over less noise"
- **Vibov (Agentic RAG):** "70% of agent quality comes from HOW tools are implemented"

## Acceptance Criteria

Fix is complete when:

- [ ] Context budget checks run automatically BEFORE each phase
- [ ] Actual token usage is recorded AFTER each phase
- [ ] `session-summary.json` includes `context_metrics` section
- [ ] `.context-foundry/context-budget-report.md` is generated at build end
- [ ] Warnings appear when entering dumb zone (40-80%)
- [ ] Critical alerts appear when entering critical zone (80%+)
- [ ] Overall stats show smart_zone_percentage and peak_usage_percentage

## Discovered By

User observation: "haven't seen it anymore" - Context budget monitoring with smart/dumb zone detection was working at some point but is no longer active.

## Date Reported

2025-11-02
