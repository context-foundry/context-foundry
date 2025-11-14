# BAML MCP Delegation Roadmap

**Status**: Proposed
**Priority**: Low (Cost savings minimal)
**Effort**: 1-2 days
**Created**: 2025-11-13
**Owner**: TBD

---

## Executive Summary

Context Foundry currently uses BAML (Basically a Made-up Language) for type-safe LLM validation via direct OpenAI API calls (GPT-4o-mini). This costs **~$0.006 per build** (~$0.64 per 100 builds).

An MCP delegation pattern exists in `integrations/baml/` that would enable **$0 API costs** by routing BAML validation through Claude Code subscription instances instead of direct API calls.

**Recommendation**: Implement when building out zero-dependency features, but **not urgent** given negligible current costs.

---

## Current State

### BAML Usage Pattern

**What BAML Does**:
- Type-safe phase tracking validation (Scout → Architect → Builder → Test)
- Structured JSON schema enforcement (5% → <1% error rate)
- Phase transition reliability

**What BAML Does NOT Do**:
- Main Scout/Architect/Builder work (runs via Claude Code CLI on subscription)
- Code generation (runs via Claude Code CLI)
- Test execution (runs via Claude Code CLI)

**Call Frequency**: 10-15 LLM calls per build
- `CreatePhaseInfo()`: Phase tracking (10-12 calls)
- `ValidatePhaseInfo()`: Validation (2-3 calls)
- Other functions: Rare/occasional

### Current Implementation

**File**: `tools/baml_integration.py`

```python
# Direct API approach:
BAML_CLIENT = BamlRuntime.from_files(
    root_path=str(schemas_dir),
    files=files_dict,
    env_vars=env_vars_for_baml  # Contains OPENAI_API_KEY
)

result = client.call_function_sync(
    function_name="CreatePhaseInfo",
    args={...},
    env_vars=get_baml_env_vars(),  # Makes direct OpenAI API call
)
```

**Provider**: GPT-4o-mini (intentionally cheap model)
- Model: `gpt-4o-mini`
- Temperature: 0.0 (deterministic)
- Input: $0.15 per 1M tokens
- Output: $0.60 per 1M tokens

**Dependencies**:
- `baml-py>=0.211.0` (required in requirements.txt)
- `OPENAI_API_KEY` environment variable (required)

**Historical Note**: Claude clients were removed in commit `749b7a1` (Oct 26, 2025) to avoid Anthropic API charges. See `tools/baml_schemas/clients.baml:37`:

```baml
// Claude clients removed - Context Foundry uses OpenAI GPT-4o-mini for BAML
// to avoid Anthropic API charges. All BAML functions use GPT4oMini client.
```

### Current Costs

**Per Build** (~17,000 tokens estimated):
- Input tokens: ~8,500 × $0.15/1M = $0.001275
- Output tokens: ~8,500 × $0.60/1M = $0.0051
- **Total: ~$0.0064 per build**

**Volume Estimates**:
- 100 builds/month: ~$0.64
- 1,000 builds/month: ~$6.40
- 10,000 builds/month: ~$64

**Note**: Documentation mentions $0.20/build, but actual costs are ~96% lower.

---

## Problem Statement

### Why Consider Alternatives?

1. **Zero-dependency vision**: Requires external OPENAI_API_KEY
2. **Philosophical alignment**: Main build uses Claude Code subscription (free), BAML uses paid API
3. **Scaling costs**: At 10K+ builds/month, costs become non-trivial (~$64/month)
4. **Security surface**: Additional API key to manage

### Non-Problems

- **Current costs are NOT a problem**: $0.64/100 builds is negligible
- **Quality is NOT a problem**: GPT-4o-mini performs perfectly for validation
- **Reliability is NOT a problem**: Current implementation works flawlessly

---

## Solution Options

### Option A: Keep GPT-4o-mini (Current State)

**Approach**: No changes

**Pros**:
- Already working perfectly
- Negligible costs (~$0.006/build)
- Zero implementation effort
- Battle-tested

**Cons**:
- Requires OPENAI_API_KEY dependency
- Non-zero API costs (however small)
- Not aligned with zero-dependency vision

**Cost**: ~$0.0064/build
**Effort**: 0 days
**Priority**: ✅ Current default

---

### Option B: Switch to Claude Direct API

**Approach**: Change BAML client from GPT-4o-mini to Claude 3.5 Sonnet

**Implementation**:
1. Uncomment Claude client in `tools/baml_schemas/clients.baml`
2. Update all function definitions to use `client Claude35Sonnet`
3. Set `ANTHROPIC_API_KEY` environment variable

**Pros**:
- Uses same provider as main build
- Marginally better reasoning (overkill for validation)

**Cons**:
- **20x cost increase** ($0.006 → $0.12 per build)
- Zero quality benefit for validation tasks
- Still requires API key dependency
- Waste of money

**Cost**: ~$0.12/build (20x increase)
**Effort**: 0.25 days (15 minutes)
**Priority**: ❌ **NOT RECOMMENDED**

---

### Option C: MCP Delegation Pattern (Proposed)

**Approach**: Route BAML validation through Claude Code subscription via MCP delegation

**Architecture**:

```
Traditional Approach (Current):
User → BAML → Direct API Call → OpenAI GPT-4o-mini → Pay per token 💸

MCP Delegation Approach (Proposed):
User → BAML Schema → MCP Delegation → Spawn Claude → Validate Schema → $0 🎉
```

**Implementation**:

Replace `tools/baml_integration.py` direct API calls with MCP delegation pattern from `integrations/baml/python/examples/mcp_delegation.py`:

```python
# New approach:
async def validate_phase_with_mcp(phase_data: dict, schema: str) -> dict:
    """Validate phase data using MCP-delegated Claude instance."""
    result = await mcp__context_foundry__delegate_to_claude_code(
        task=f"Validate this JSON against {schema} schema: {json.dumps(phase_data)}",
        working_directory=os.getcwd(),
        timeout_minutes=1.0
    )
    return parse_validated_result(result)
```

**Pros**:
- ✅ **Zero API costs** (runs on Claude Code subscription)
- ✅ No API key dependencies (OPENAI_API_KEY not needed)
- ✅ Same type-safety guarantees (schema still enforced)
- ✅ Better security (no API keys to manage)
- ✅ Aligned with zero-dependency vision
- ✅ Uses existing MCP infrastructure

**Cons**:
- Requires implementation effort (1-2 days)
- Adds latency vs direct API calls (~2-3s per spawn)
- More complex architecture
- Minimal cost savings given current usage ($0.64/100 builds)

**Cost**: $0/build
**Effort**: 1-2 days
**Priority**: 🎯 **RECOMMENDED** (when building zero-dependency features)

---

## Implementation Roadmap

### Phase 1: Research & Design (0.5 days)

**Goals**:
1. Review existing MCP delegation pattern in `integrations/baml/`
2. Design integration with current `tools/baml_integration.py`
3. Identify migration strategy (gradual vs all-at-once)

**Deliverables**:
- Architecture diagram
- Migration plan
- Risk assessment

**Dependencies**: None

---

### Phase 2: Prototype (0.5 days)

**Goals**:
1. Implement MCP delegation for `CreatePhaseInfo()` only
2. Add feature flag: `USE_BAML_MCP_DELEGATION` (default: false)
3. Test both paths (direct API vs MCP) side-by-side

**Deliverables**:
- Working prototype for single function
- Performance benchmarks (latency comparison)
- Test coverage

**Files Modified**:
- `tools/baml_integration.py` - Add MCP delegation path
- `tools/mcp_utils/phase_execution.py` - Add feature flag support
- `tests/test_baml_integration.py` - Test both modes

**Dependencies**: Phase 1 complete

---

### Phase 3: Full Implementation (0.5 days)

**Goals**:
1. Extend MCP delegation to all BAML functions
2. Add graceful fallback (MCP → Direct API if MCP unavailable)
3. Update documentation

**Deliverables**:
- All 8 BAML functions support MCP delegation
- Fallback mechanism tested
- Updated docs

**Files Modified**:
- `tools/baml_integration.py` - Complete MCP integration
- `docs/BAML_INTEGRATION.md` - Document MCP mode
- `README.md` - Update dependencies section

**Dependencies**: Phase 2 complete

---

### Phase 4: Migration & Cleanup (0.25 days)

**Goals**:
1. Enable MCP delegation by default
2. Remove `OPENAI_API_KEY` requirement (make optional)
3. Update setup/installation docs

**Deliverables**:
- Default mode switched to MCP
- Backwards compatibility maintained
- Installation guide updated

**Files Modified**:
- `.env.example` - Mark OPENAI_API_KEY as optional
- `docs/GETTING_STARTED.md` - Remove API key setup step
- `CHANGELOG.md` - Document zero-cost BAML feature

**Dependencies**: Phase 3 complete, production testing

---

## Technical Design

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Phase Execution (phase_execution.py)                        │
│                                                             │
│  run_phase() calls update_phase_with_baml()                │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ BAML Integration (baml_integration.py)                      │
│                                                             │
│  ┌────────────────────────────────────────────────┐        │
│  │ Feature Flag: USE_BAML_MCP_DELEGATION          │        │
│  └────────────┬───────────────────────────────────┘        │
│               │                                             │
│       ┌───────┴────────┐                                    │
│       │                │                                    │
│       ▼                ▼                                    │
│  ┌─────────┐    ┌──────────────┐                          │
│  │ MCP     │    │ Direct API   │                          │
│  │ Mode    │    │ Mode         │                          │
│  │ ($0)    │    │ ($0.006)     │                          │
│  └────┬────┘    └──────┬───────┘                          │
│       │                │                                    │
└───────┼────────────────┼────────────────────────────────────┘
        │                │
        ▼                ▼
┌──────────────┐  ┌──────────────┐
│ Spawn Claude │  │ OpenAI API   │
│ (Subscription│  │ (GPT-4o-mini)│
│  $0)         │  │ ($0.006)     │
└──────────────┘  └──────────────┘
```

### Code Changes

**File**: `tools/baml_integration.py`

```python
# Add at top:
import os
USE_BAML_MCP_DELEGATION = os.getenv("USE_BAML_MCP_DELEGATION", "false").lower() == "true"

async def update_phase_with_baml_mcp(
    phase: str,
    status: str,
    detail: str,
    session_id: str = "context-foundry",
    iteration: int = 0,
) -> Dict[str, Any]:
    """
    Update phase tracking using MCP delegation (zero-cost).

    Spawns fresh Claude instance to validate phase data against schema.
    """
    from tools.mcp_server import mcp__context_foundry__delegate_to_claude_code

    # Build validation task
    phase_data = {
        "session_id": session_id,
        "phase": phase,
        "status": status,
        "detail": detail,
        "iteration": iteration
    }

    task = f"""
Validate this phase tracking data against the PhaseInfo BAML schema:

{json.dumps(phase_data, indent=2)}

Return a complete PhaseInfo JSON object with:
- All required fields populated
- Valid enum values for phase and status
- ISO timestamps for started_at and last_updated
- Proper phase_number formatting

Schema validation is critical - ensure type safety.
"""

    # Delegate to Claude instance
    result = await mcp__context_foundry__delegate_to_claude_code(
        task=task,
        working_directory=os.getcwd(),
        timeout_minutes=1.0
    )

    # Parse result
    return parse_phase_info_from_delegation(result)

def update_phase_with_baml(
    phase: str,
    status: str,
    detail: str,
    session_id: str = "context-foundry",
    iteration: int = 0,
) -> Dict[str, Any]:
    """
    Update phase tracking (auto-selects MCP or direct API mode).
    """
    if USE_BAML_MCP_DELEGATION:
        # Try MCP delegation first
        try:
            return asyncio.run(update_phase_with_baml_mcp(
                phase, status, detail, session_id, iteration
            ))
        except Exception as e:
            print(f"⚠️ MCP delegation failed, falling back to direct API: {e}",
                  file=sys.stderr)
            # Fall through to direct API

    # Direct API mode (current implementation)
    return update_phase_with_baml_direct(
        phase, status, detail, session_id, iteration
    )
```

### Migration Strategy

**Gradual Rollout**:
1. **Week 1**: Deploy with feature flag disabled (default: direct API)
2. **Week 2**: Enable for 10% of builds, monitor performance
3. **Week 3**: Enable for 50% of builds, validate cost savings
4. **Week 4**: Enable for 100% of builds, make default

**Rollback Plan**:
- If MCP delegation fails: automatic fallback to direct API
- If performance unacceptable: disable feature flag
- If bugs detected: revert to previous version

---

## Success Metrics

### Performance Targets

| Metric | Current (Direct API) | Target (MCP) | Acceptable Range |
|--------|---------------------|--------------|------------------|
| Latency per call | ~200ms | ~2-3s | <5s |
| Cost per build | $0.0064 | $0.00 | $0.00 |
| Error rate | <1% | <1% | <2% |
| Build time overhead | 0s | +20-30s | <60s |

### Cost Savings

| Volume | Current Cost | MCP Cost | Monthly Savings |
|--------|-------------|----------|-----------------|
| 100 builds | $0.64 | $0.00 | $0.64 |
| 1,000 builds | $6.40 | $0.00 | $6.40 |
| 10,000 builds | $64.00 | $0.00 | $64.00 |

**Break-even Analysis**: Implementation effort pays off after ~10K builds (assuming $50/hr dev cost).

### Quality Metrics

- Schema validation accuracy: Maintain 99%+ accuracy
- Phase transition reliability: No regressions
- Type safety guarantees: Equivalent to direct API

---

## Open Questions

### Technical

1. **Latency impact**: Can we tolerate 2-3s overhead per phase transition?
   - Current: ~15 BAML calls × 0.2s = 3s per build
   - MCP: ~15 spawns × 2.5s = 37.5s per build
   - **Trade-off**: +35s build time for $0 cost

2. **Concurrency**: Should we batch BAML validations to reduce spawns?
   - Current: Sequential calls (15 separate API requests)
   - Optimized: Batch into 3-5 validation groups
   - Could reduce overhead to +10-15s

3. **Error handling**: What happens if Claude spawn fails?
   - Graceful fallback to direct API?
   - Retry logic?
   - Skip validation and continue?

### Product

1. **User preference**: Should this be user-configurable?
   - Environment variable: `USE_BAML_MCP_DELEGATION=true`
   - CLI flag: `--baml-mode=mcp|api`
   - Auto-detect based on API key availability?

2. **Documentation**: How to communicate the trade-off?
   - "Fast builds, small cost" vs "Slower builds, zero cost"
   - Default recommendation?

3. **Long-term vision**: Is BAML even needed with MCP delegation?
   - Could we replace BAML entirely with native Claude validation?
   - Would lose compile-time schema checking
   - Trade-off: Simplicity vs type safety

---

## Dependencies

### Required Features

- ✅ MCP delegation infrastructure (already exists)
- ✅ Claude Code subscription (already exists)
- ✅ BAML schemas (already defined)

### Blocked By

- None (can implement independently)

### Blocks

- Zero-dependency builds feature
- API key elimination roadmap
- Self-hosted deployment scenarios

---

## Alternatives Considered

### Alternative 1: Remove BAML Entirely

**Approach**: Replace BAML validation with manual JSON parsing

**Pros**:
- Zero external dependencies
- No API costs
- Simpler architecture

**Cons**:
- Loss of type safety (5% → 1% error rate becomes 5% again)
- No compile-time schema validation
- Higher build failure rates

**Decision**: ❌ Rejected - Type safety is worth the complexity

---

### Alternative 2: Use Cheaper API Provider

**Approach**: Switch to even cheaper model (e.g., GPT-3.5-turbo @ $0.0005/1K)

**Pros**:
- 10x cost reduction ($0.006 → $0.0006)
- Minimal code changes

**Cons**:
- Still non-zero cost
- Still requires API key
- Marginal quality risk

**Decision**: ❌ Rejected - Doesn't solve zero-dependency goal

---

### Alternative 3: Cache BAML Validation Results

**Approach**: Cache CreatePhaseInfo() results based on input hash

**Pros**:
- Reduces API calls by ~80% (many duplicate phase transitions)
- Simple to implement
- Cost reduction: $0.006 → $0.001

**Cons**:
- Still non-zero cost
- Cache invalidation complexity
- Doesn't solve dependency problem

**Decision**: 🤔 Worth considering as **complementary** optimization

---

## Related Work

### Existing Documentation

- `integrations/baml/README.md` - MCP delegation pattern documentation
- `integrations/baml/python/examples/mcp_delegation.py` - Reference implementation
- `docs/BAML_INTEGRATION.md` - Current BAML integration guide
- `tools/baml_schemas/` - Schema definitions

### Related Roadmap Items

- Zero-dependency builds
- Self-hosted deployment
- API key elimination
- Build performance optimization

---

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2025-10-26 | Remove Claude clients from BAML | Avoid Anthropic API charges (commit 749b7a1) |
| 2025-10-26 | Use GPT-4o-mini for BAML | 95% cheaper than Claude for validation tasks |
| 2025-11-13 | Document MCP delegation roadmap | Enable future zero-cost BAML when needed |

---

## Recommendation

### Short-Term (Now)

**Action**: ✅ **Keep current GPT-4o-mini implementation**

**Rationale**:
- Current costs negligible ($0.64/100 builds)
- Works perfectly
- No urgent need to change

**Next Steps**:
1. Update documentation to reflect actual ~$0.01 cost (not $0.20)
2. Monitor usage patterns
3. Re-evaluate at 1,000+ builds/month volume

---

### Medium-Term (Q1 2026)

**Action**: 🎯 **Implement MCP delegation as feature flag**

**Rationale**:
- Aligns with zero-dependency vision
- Enables self-hosted deployments
- Small implementation effort (1-2 days)
- Provides user choice

**Trigger Conditions**:
- When building zero-dependency features OR
- When monthly build volume exceeds 1,000 builds OR
- When users request API key elimination

**Next Steps**:
1. Schedule 1-2 day sprint
2. Follow phased implementation roadmap
3. Gradual rollout with monitoring

---

### Long-Term (2026+)

**Action**: 🔮 **Consider BAML architecture simplification**

**Questions**:
- Is BAML still needed with mature MCP delegation?
- Could we replace with native Claude validation?
- Are there simpler type-safety approaches?

**Research Needed**:
- Survey type-safety alternatives
- Measure actual error rates with/without BAML
- User feedback on build reliability

---

## Conclusion

BAML MCP delegation is a **low-priority, high-value** optimization that should be implemented when:
1. Building out zero-dependency features
2. Monthly build volumes justify the effort
3. Users request API key elimination

Current GPT-4o-mini implementation is working well and costs are negligible. No urgent action needed.

**Estimated ROI**: Low (saves ~$0.64/100 builds) unless building for scale (10K+ builds/month) or zero-dependency scenarios.

---

**Last Updated**: 2025-11-13
**Next Review**: Q1 2026 or when monthly builds exceed 1,000
