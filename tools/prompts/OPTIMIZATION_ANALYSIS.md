# Orchestrator Prompt Optimization Analysis

**Current Version:** v1.0.0 (1996 lines, 8344 words, ~11-15k tokens)

## Redundancy Analysis

### 1. Repeated Phase Tracking Boilerplate (HIGH IMPACT)
**Occurrences:** 17 instances of phase tracking JSON updates
**Current Token Cost:** ~2,500-3,000 tokens
**Potential Savings:** ~1,500-2,000 tokens (40-60% reduction)

**Pattern Found:**
```
Update .context-foundry/current-phase.json:
{
  "session_id": "{project_directory_name}",
  "current_phase": "...",
  "phase_number": "X/7",
  "status": "...",
  ...
}
```

**Optimization Strategy:**
- Define phase tracking format ONCE at top
- Reference it with: "Update phase tracking (see §2.1)"
- Include only phase-specific fields inline

**Example Reduction:**
```
BEFORE (60 lines across all phases):
Execute: cat > .context-foundry/current-phase.json << 'EOF'
{
  "session_id": "{project_directory_name}",
  "current_phase": "Scout",
  "phase_number": "1/7",
  "status": "researching",
  ...
}
EOF

AFTER (5 lines per phase):
Update phase: Scout (1/7, researching, "Analyzing task requirements")
```

### 2. Enhancement Mode Guidance Blocks (MEDIUM IMPACT)
**Occurrences:** 4 separate "🔧 ENHANCEMENT MODE GUIDANCE" blocks
**Current Token Cost:** ~800-1,000 tokens
**Potential Savings:** ~400-600 tokens (50% reduction)

**Optimization Strategy:**
- Consolidate all enhancement mode logic into ONE section at the top
- Reference it per-phase: "For enhancement modes, see §1.2"
- Keep only phase-specific enhancement notes inline

### 3. Pattern Application Examples (MEDIUM IMPACT)
**Current Token Cost:** ~1,000-1,500 tokens
**Potential Savings:** ~500-800 tokens

**Examples like:**
```
Example: If building browser app with ES6 modules, patterns might warn:
"⚠️ CORS Risk: ES6 modules fail from file:// - Include dev server in architecture"
```

**Optimization:**
- Move verbose examples to external reference doc
- Keep only pattern IDs and brief descriptions
- "See pattern: cors-es6-modules (common-issues.json)"

### 4. Verbose Instructions (MEDIUM IMPACT)
**Patterns:**
- "CRITICAL:", "IMPORTANT:", "⚠️" overused (14 CRITICAL labels)
- Step-by-step curl commands repeated
- Long explanatory paragraphs

**Optimization:**
- Use formatting instead of ALL CAPS emphasis
- Define common operations (like curl broadcast) ONCE
- Consolidate explanations into bulleted lists

### 5. Deprecated Section (LOW IMPACT but MISLEADING)
**Issue:** PHASE 3: BUILDER marked as "DEPRECATED - USE PHASE 2.5 INSTEAD"
**Lines:** ~120 lines
**Token Cost:** ~400-500 tokens

**Optimization:**
- DELETE entirely (it's deprecated!)
- Or reduce to 3-line notice: "Phase 3 deprecated. Use Phase 2.5 parallel build."

## Proposed Optimization Roadmap

### Phase 1: Low-Risk Quick Wins - ✅ COMPLETED (v1.1.0)
1. ✅ Remove ASCII logo (DONE in v1.0.0 - saved ~200 tokens)
2. ✅ Delete deprecated Phase 3 content (saved ~500 tokens)
3. ✅ Consolidate phase tracking format (saved ~400 tokens)
4. ✅ Reduce "CRITICAL" overuse (saved ~100 tokens)

**ACTUAL RESULTS:**
- Lines reduced: 1996 → 1819 (-177 lines, -8.9%)
- Words reduced: 8344 → 7601 (-743 words, -8.9%)
- Tokens saved: ~966 tokens (-8.9%)
- Version: v1.1.0 (Quick Wins)
- Date: 2025-10-24

**Risk:** Very low - removing clearly redundant content
**Effort:** 2 hours actual
**Status:** COMPLETED and archived

### Phase 2: Moderate Restructuring (~1,500 token savings)
1. Consolidate enhancement mode blocks (save ~600 tokens)
2. Move verbose examples to reference appendix (save ~600 tokens)
3. Compress instruction paragraphs to bullets (save ~300 tokens)

**Risk:** Low-medium - requires careful rewrite
**Effort:** 4-6 hours
**Expected Version:** v1.2.0

### Phase 3: Advanced Optimization (~1,000 token savings)
1. Create reusable macro system (e.g., `{{PHASE_UPDATE Scout 1/7}}`)
2. Extract common operations to definitions section
3. Consider splitting into multiple specialized prompts

**Risk:** Medium - requires testing
**Effort:** 8-10 hours
**Expected Version:** v2.0.0

## Total Potential Savings
- **Conservative:** 2,500-3,000 tokens (20-25% reduction)
- **Aggressive:** 4,000-5,000 tokens (35-40% reduction)
- **Target:** Reduce from ~12,000 to ~8,000 tokens

## Performance Tracking Plan

Track these metrics PER VERSION in `session-summary.json`:

```json
{
  "prompt_metadata": {
    "orchestrator_version": "v1.1.0",
    "orchestrator_tokens": 9800,
    "github_agent_version": "v1.0.0"
  },
  "performance_metrics": {
    "build_success": true,
    "test_iterations": 1,
    "total_duration_minutes": 42.5,
    "phases_completed": 8,
    "issues_encountered": []
  }
}
```

Then analyze:
- Success rate per version
- Average test iterations per version
- Average duration per version
- Token savings vs. quality trade-off

## Recommended Next Steps

1. **Immediate:** Implement Phase 1 optimizations (v1.1.0)
   - Safe, high-impact, quick wins
   - Create archive backup before changes
   - A/B test with 5-10 builds

2. **Short-term:** Add version tracking to MCP server
   - Update `session-summary.json` to include prompt version
   - Track metrics in pattern library

3. **Medium-term:** Implement Phase 2 optimizations (v1.2.0)
   - Based on v1.1.0 performance data
   - Continue A/B testing

4. **Long-term:** Consider modular prompt architecture
   - Split into: core instructions + phase modules + reference appendix
   - Load dynamically based on mode (new_project vs enhancement)

## Rollback Safety

All versions archived at: `tools/prompts/archive/`

To rollback:
```bash
cp tools/prompts/archive/orchestrator_prompt_v1.0.0_baseline.txt tools/orchestrator_prompt.txt
```

Git tags for each version:
```bash
git tag -a prompt-v1.1.0 -m "Orchestrator prompt v1.1.0 - Quick wins"
```
