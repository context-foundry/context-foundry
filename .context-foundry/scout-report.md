# Scout Report: Anthropic Prompt Caching Implementation

## Executive Summary

Implement Anthropic's prompt caching feature for Context Foundry's orchestrator to achieve **90% cost reduction** and **~$0.20 → $0.02 per build** savings. The infrastructure is **60% complete** - cost calculator, pricing config, and token tracking already support caching. Need to implement: prompt builder, mcp_server integration, tests, and docs.

**Key Discovery**: Cost calculator already has full cache support (cache_read/write tokens, pricing, savings calculation). This significantly simplifies implementation!

## Requirements Analysis

### Core Objective
Cache the static 9,000-token orchestrator prompt to reuse across builds within 5-minute TTL window, reducing input tokens by 90% on subsequent builds.

### Core Components Needed
1. **Prompt Builder** (tools/prompts/cached_prompt_builder.py) - Split orchestrator prompt into cacheable/dynamic sections
2. **Cache Analysis** (tools/prompts/cache_analysis.py) - Analyze prompt structure and generate segmentation plan
3. **MCP Integration** (tools/mcp_server.py) - Modify autonomous_build_and_deploy() to use cached prompts
4. **Cache Config** (tools/prompts/cache_config.json) - Enable/disable caching, configure TTL
5. **Tests** (tests/test_cached_prompt_builder.py) - Unit and integration tests
6. **Documentation** (docs/PROMPT_CACHING.md) - Complete implementation guide

## Technology Stack Decision
- **Language**: Python 3.10+ (existing codebase)
- **Caching**: Anthropic Prompt Caching API (Claude 3.5+)
- **Integration**: MCP server (tools/mcp_server.py)
- **No new dependencies needed** - anthropic package already installed

### Anthropic Cache API Spec (from docs.claude.com)
- **TTL**: 5 minutes (default) or 1 hour (extended, 2× cost)
- **Minimum tokens**: 1024 for Sonnet, 2048 for Haiku
- **Max breakpoints**: 4 per request
- **Pricing** (Claude Sonnet 4):
  - Input: $3.00/MTok
  - Cache writes (5min): $3.75/MTok (1.25×)
  - Cache reads: $0.30/MTok (0.1×) - **90% savings!**
- **Cache control marker**: `{"type": "ephemeral", "ttl": "5m"}`

## Critical Architecture Recommendations

### 1. Prompt Segmentation Strategy

**CACHEABLE SECTION** (~8,500 tokens):
- All phase instructions (Phases 0-7.5)
- Git workflow reference
- Enhancement mode reference
- Phase tracking templates
- Error handling guides
- Critical rules
- Test loop logic

**DYNAMIC SECTION** (~500 tokens):
- Task description (varies per build)
- Working directory path
- Mode flags (new_project/fix_bug/etc)
- Project configuration JSON
- Test iteration limits

**Cache Control Placement**:
```json
{
  "role": "user",
  "content": [
    {
      "type": "text",
      "text": "<STATIC ORCHESTRATOR PROMPT>",
      "cache_control": {"type": "ephemeral"}
    },
    {
      "type": "text",
      "text": "AUTONOMOUS BUILD TASK\\n\\nCONFIGURATION:\\n{...}"
    }
  ]
}
```

### 2. Integration with mcp_server.py

**Current Flow** (lines 1269-1293):
```python
with open(orchestrator_prompt_path) as f:
    system_prompt = f.read()

task_prompt = f"AUTONOMOUS BUILD TASK\\n\\nCONFIGURATION:\\n{json.dumps(...)}"

cmd = ["claude", "--system-prompt", system_prompt, task_prompt]
```

**New Cache-Aware Flow**:
```python
from tools.prompts.cached_prompt_builder import build_cached_prompt

# Build prompt with cache markers
prompt_data = build_cached_prompt(
    task_config=task_config,
    enable_caching=True  # from config
)

# Use structured prompt format
# Claude Code supports JSON prompt format via stdin
cmd = ["claude", "--print", "--prompt-format", "json"]
stdin_data = json.dumps(prompt_data)
```

### 3. Existing Infrastructure (Already Complete!)

✅ **Cost Calculator** (tools/metrics/cost_calculator.py):
- Already has cache_read_tokens and cache_write_tokens support
- get_cost_breakdown() calculates cache_savings
- No modifications needed!

✅ **Pricing Config** (tools/metrics/pricing_config.json):
- Already has cache_write_per_mtok: 3.75
- Already has cache_read_per_mtok: 0.30
- All Claude models configured!

✅ **Metrics DB** (tools/metrics/metrics_db.py):
- Schema already supports cache tokens
- TokenUsage class ready for cache data

## Main Challenges & Mitigations

### Challenge 1: Claude Code CLI Integration
**Issue**: Claude Code may not support structured JSON prompt format via stdin
**Solution**: Investigate three approaches:
1. Use --prompt-format json if supported (ideal)
2. Convert cache markers to equivalent --system-prompt usage
3. Fallback to current method with cache tracking in metrics only

### Challenge 2: Prompt Version Management
**Issue**: Any change to orchestrator_prompt.txt invalidates entire cache
**Solution**:
- Add version hash to prompt header
- Track prompt versions in cache_config.json
- Warn when prompt changes invalidate cache

### Challenge 3: Token Boundary Precision
**Issue**: Cache requires minimum 1024 tokens for Sonnet
**Solution**:
- Use anthropic package's count_tokens() for accurate counting
- Validate static section meets minimum before enabling caching
- Add buffer (ensure 1100+ tokens)

### Challenge 4: Known Risks from Pattern Analysis
**Medium-Priority Risks**:
1. **Prompt Structure Changes**: If orchestrator_prompt.txt modified, cache invalidates
   - Mitigation: Version prompt, include version hash in cache key

2. **Cache TTL Window**: 5-minute default may be too short for some workflows
   - Mitigation: Make configurable, support 1-hour extended cache option

## Testing Approach

### Unit Tests (tests/test_cached_prompt_builder.py)
- Test prompt segmentation logic
- Test cache marker insertion
- Test token counting accuracy
- Test config loading
- Test fallback behavior (non-Claude models)

### Integration Tests (tests/test_cache_integration.py)
- Mock subprocess calls to claude CLI
- Verify cache markers in generated commands
- Test metrics collection with cache tokens
- Test cost calculation with cached vs uncached

### End-to-End Test (manual)
```bash
# Build 1: Full prompt (cache miss)
foundry build test-app "Create hello world app"
# Verify: cache_write_tokens > 8000, cost ~$0.03

# Build 2: Cached prompt (cache hit) - within 5 min
foundry build test-app-2 "Create goodbye world app"
# Verify: cache_read_tokens > 8000, cost ~$0.003

# Build 3: After 5 min (cache expired)
sleep 310 && foundry build test-app-3 "Create test app"
# Verify: cache_write_tokens > 8000 again
```

## Success Criteria Validation

✅ Cost calculator already supports caching (done!)
✅ Pricing config already has cache rates (done!)
✅ Metrics DB already tracks cache tokens (verified in schema)
✅ Token counting infrastructure exists (TokenUsage class)
⏳ Need: Prompt builder, MCP integration, tests, docs
⏳ Target: 90% token reduction on cached builds
⏳ Target: $0.20 → $0.02 per build cost savings

## Timeline Estimate

- **Prompt Builder**: 2 hours (new file, straightforward logic)
- **MCP Integration**: 3 hours (modify existing, test CLI compatibility)
- **Cache Analysis Tool**: 1 hour (simple utility)
- **Tests**: 2 hours (unit + integration)
- **Documentation**: 2 hours (comprehensive guide)
- **Total**: ~10 hours (actual implementation ~60% smaller than task spec suggested)

## Applied Learnings from Pattern Library

No relevant patterns found in global library for prompt caching (new feature). After implementation, will contribute patterns for:
- cache-anthropic-prompt-caching-implementation
- cache-token-optimization-strategies
- cache-ttl-management

## Next Phase: Architect

Scout recommends Architect focus on:
1. Detailed prompt builder module design
2. MCP server integration strategy (CLI compatibility research)
3. Cache configuration schema
4. Test strategy refinement
5. Fallback mechanism design (graceful degradation)
6. Metrics tracking enhancement plan
