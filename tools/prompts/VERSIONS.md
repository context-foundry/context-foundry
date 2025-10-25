# Prompt Versioning System

This directory tracks all versions of Context Foundry prompts for performance analysis and rollback.

## Version History

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
