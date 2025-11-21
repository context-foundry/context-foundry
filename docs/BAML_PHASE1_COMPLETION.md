# Phase 1 Completion: Remove Redundant current-phase.json Instructions

## Discovery Summary

**Good News:** BAML phase tracking is **already implemented and working!**

The orchestrator (`phase_execution.py`) already uses BAML to create `current-phase.json` before each phase starts.

However, phase prompts still contain redundant instructions telling agents to manually create this file.

## Current Implementation

### Python Orchestrator (Already Working ✅)
```python
# tools/mcp_utils/phase_execution.py:311-322
phase_info = update_phase_with_baml(
    phase=phase_name,
    status=phase_status,
    detail=f"Starting {phase_name} phase",
    session_id=session_id,
    iteration=iteration,
)

# Save to current-phase.json
phase_file = working_directory / ".context-foundry" / "current-phase.json"
phase_file.parent.mkdir(parents=True, exist_ok=True)
phase_file.write_text(json.dumps(phase_info, indent=2))
```

### BAML Integration (Already Working ✅)
- File: `tools/baml_integration.py`
- Function: `update_phase_with_baml()` (lines 244-396)
- Schema: `tools/baml_schemas/phase_tracking.baml`
- Status: **Active and functional**

### Phase Prompts (REDUNDANT - Needs Cleanup ❌)

All phase prompts currently contain instructions like:

```markdown
0. Write phase status (REQUIRED FIRST STEP):
   Update .context-foundry/current-phase.json:
   {
     "current_phase": "Deploy",
     "phase_number": 6,
     "status": "in_progress",
     ...
   }
```

**This is redundant** because the Python orchestrator already creates this file via BAML before the agent even starts!

## What Needs to be Done

### Task 1: Remove Redundant Instructions from Phase Prompts

Remove the "REQUIRED FIRST STEP" and "REQUIRED LAST STEP" current-phase.json update instructions from:

1. `tools/prompts/phase_4_test.md` (lines 53-60, 452-460, 485-495)
2. `tools/prompts/phase_6_deployment.md` (lines 9-20, 335-345)
3. `tools/prompts/phase_7_feedback.md` (lines 9-20, 519-530)
4. `tools/prompts/phase_7_5_github.md` (lines 11-22, 102-112)
5. `tools/prompts/phase_4_5_screenshot.md` (lines 9-20, 120-130)
6. `tools/prompts/phase_5_documentation.md` (lines 7-18, 98-110)
7. `tools/prompts/phase_2_5_parallel_build.md` (lines 511-520)

### Task 2: Add Note About Automatic Phase Tracking (Optional)

Replace removed instructions with a brief note:

```markdown
**Note:** Phase tracking is handled automatically by the orchestrator using BAML.
The `current-phase.json` file is created and updated for you.
```

## Token Savings Estimate

### Before (Current State)
Each phase prompt contains ~150 tokens of JSON structure instructions × 2 (start + end) = 300 tokens/phase

**Total across 7 phases:** 300 × 7 = **2,100 tokens/build**

### After (Completed Phase 1)
Instructions removed, brief note added: ~20 tokens/phase

**Total across 7 phases:** 20 × 7 = 140 tokens/build

**Net Savings:** ~1,960 tokens per build

## Files to Modify

### Phase Prompts (7 files)
- `tools/prompts/phase_4_test.md`
- `tools/prompts/phase_6_deployment.md`
- `tools/prompts/phase_7_feedback.md`
- `tools/prompts/phase_7_5_github.md`
- `tools/prompts/phase_4_5_screenshot.md`
- `tools/prompts/phase_5_documentation.md`
- `tools/prompts/phase_2_5_parallel_build.md`

**Note:** Phase 1 (Scout) and Phase 2 (Architect) prompts may also need checking.

### No Python Changes Needed
The Python code is already correct and doesn't need modification.

## Testing Plan

After removing redundant instructions:

1. Run a test build: `./tools/cfd build "Create a simple hello world app"`
2. Verify `current-phase.json` is still created
3. Verify Glass Pane displays phases correctly
4. Check for warnings like "BAML phase tracking failed"
5. Confirm token usage decreased by ~2,000 tokens

## Risk Assessment

**Risk Level:** VERY LOW

- Python orchestrator already handles phase tracking
- Agents don't actually need to create this file
- Removing redundant instructions can only help (fewer tokens, less confusion)
- If anything fails, orchestrator creates the file anyway

## Next Steps

1. ✅ Create migration plan (DONE)
2. ⏳ Remove redundant instructions from all 7 phase prompts
3. ⏳ Test with a sample build
4. ⏳ Measure token savings
5. ⏳ Update BAML_MIGRATION_PLAN.md status to "COMPLETE"

---

**Status:** Ready to execute
**Estimated Time:** 30 minutes
**Estimated Savings:** ~2,000 tokens per build
