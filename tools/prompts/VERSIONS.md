# Prompt Versioning System

This directory tracks all versions of Context Foundry prompts for performance analysis and rollback.

## Version History

### v1.2.1 - No Livestream (2025-10-24)
**Files:**
- `archive/orchestrator_prompt_v1.2.1_no-livestream.txt` (1,648 lines, ~8,911 tokens)

**Metrics:**
- Lines: 1,648 (-10 from v1.2.0, -0.6%)
- Words: 6,855 (-52 from v1.2.0, -0.8%)
- Estimated tokens: 8,911 (-68 from v1.2.0, -0.8%)
- **Total from baseline:** -1,936 tokens (-17.8%)

**Changes:**
1. ✅ Removed livestream integration entirely (~68 tokens)
   - Removed LIVESTREAM INTEGRATION section (4 lines)
   - Removed curl broadcast command from PHASE TRACKING TEMPLATE (5 lines)
   - Removed broadcast reference in Scout phase (1 word)

**Rationale:**
- Livestream broadcasting is optional/not always used
- Instructions were sent on every build regardless of server status
- Removing saves tokens and reduces noise

**Performance:**
- TBD - will track and compare against v1.2.0

**Status:** Active - ready for testing

---

### v1.2.0 - Consolidated (2025-10-24)
**Files:**
- `archive/orchestrator_prompt_v1.2.0_consolidated.txt` (1,658 lines, ~8,979 tokens)

**Metrics:**
- Lines: 1,658 (-161 from v1.1.0, -9.7%)
- Words: 6,907 (-694 from v1.1.0, -9.1%)
- Estimated tokens: 8,979 (-902 from v1.1.0, -9.1%)
- **Total from baseline:** -1,868 tokens (-17.2%)

**Changes:**
1. ✅ Consolidated 4 enhancement mode blocks (~600 tokens)
   - Created single Enhancement Mode Reference section
   - Replaced verbose per-phase guidance with references
2. ✅ Simplified livestream broadcasting (~150 tokens)
   - Reduced from 18 lines to 3 lines
   - Curl command in template, just reference it
3. ✅ Consolidated git workflow (~200 tokens)
   - Created Git Workflow Reference section
   - Replaced verbose commit/PR templates with compact versions
4. ✅ Removed redundant phase references (~150 tokens)
   - "Phase 1 (Scout)" → "Scout"
   - "Proceed to Phase 2" → "Proceed to Architect"
5. ✅ Removed decorative separators (~100 tokens)
   - Removed closing separators after section titles
   - Kept opening separators for visual structure

**Performance:**
- TBD - will track and compare against v1.1.0

**Status:** Active - ready for testing

---

### v1.1.0 - Quick Wins (2025-10-24)
**Files:**
- `archive/orchestrator_prompt_v1.1.0_quick-wins.txt` (1819 lines, ~10-11k tokens)

**Metrics:**
- Lines: 1819 (-177 from v1.0.0, -8.9%)
- Words: 7601 (-743 from v1.0.0, -8.9%)
- Estimated tokens: 10,000-11,000 (~1,000-1,500 tokens saved)

**Changes:**
1. ✅ Deleted deprecated Phase 3 section (~500 tokens saved)
   - Reduced from 104 lines to 6 lines
   - Phase 3 is deprecated in favor of Phase 2.5 parallel building
2. ✅ Consolidated phase tracking format (~400 tokens saved)
   - Created single template reference at top
   - Simplified phase start/end tracking blocks
   - Reduced repetition across 8 phases
3. ✅ Reduced CRITICAL label overuse (~100 tokens saved)
   - Removed redundant emphasis markers
   - Kept CRITICAL only for truly critical items
4. ✅ Updated version header to v1.1.0

**Performance:**
- TBD - will track and compare against v1.0.0 baseline

**Status:** Active - ready for A/B testing

---

### v1.0.0 - Baseline (2025-10-24)
**Files:**
- `archive/orchestrator_prompt_v1.0.0_baseline.txt` (1996 lines, ~11-15k tokens)
- `archive/github_agent_prompt_v1.0.0_baseline.txt`

**Metrics:**
- Lines: 1996
- Words: 8344
- Estimated tokens: 11,000-15,000
- Status: Baseline version before optimization

**Performance:**
- TBD - will track build success rate, test iterations, duration

**Notes:**
- Removed ASCII logo (saved ~200 tokens)
- Contains comprehensive instructions for all 8 phases
- Has significant redundancy and verbosity

## Version Tracking Schema

Each build's `session-summary.json` should include:
```json
{
  "prompt_version": "v1.0.0",
  "prompt_token_count": 12500,
  "prompt_file": "orchestrator_prompt_v1.0.0_baseline.txt"
}
```

## Performance Metrics to Track

Per version:
- Average build success rate
- Average test iterations needed
- Average build duration
- Token usage per build
- Common failure patterns

## Optimization Strategy

1. **Create backup** ✅
2. **Analyze for redundancy**
3. **Create optimized v1.1.0**
4. **A/B test both versions**
5. **Compare metrics**
6. **Keep better performer**

## Rollback Procedure

To rollback to a previous version:
```bash
cp tools/prompts/archive/orchestrator_prompt_v1.0.0_baseline.txt tools/orchestrator_prompt.txt
```
