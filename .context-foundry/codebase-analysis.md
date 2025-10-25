# Codebase Analysis Report - Prompt Caching Implementation

## Project Overview
- **Type**: Python CLI/MCP Tool
- **Languages**: Python 3.10+
- **Architecture**: Multi-agent autonomous build orchestration system
- **Current Branch**: feature/metrics-cost-tracking-system (uncommitted changes present)

## Key Files for Prompt Caching Implementation

### Entry Points
- `tools/mcp_server.py` - MCP server, handles autonomous_build_and_deploy()
- `tools/orchestrator_prompt.txt` - 1,677 lines, ~9,000 tokens (target for caching)

### Cost/Metrics Infrastructure (Already Exists!)
- `tools/metrics/cost_calculator.py` - **Already supports cache pricing!**
  - Has cache_write_per_mtok and cache_read_per_mtok fields
  - calculate_cost() already handles cache tokens
  - get_cost_breakdown() already calculates cache_savings
- `tools/metrics/pricing_config.json` - **Already has cache rates!**
  - cache_write_per_mtok: 3.75 (Claude Sonnet)
  - cache_read_per_mtok: 0.30 (Claude Sonnet)
- `tools/metrics/metrics_db.py` - Database for metrics storage
- `tools/metrics/log_parser.py` - TokenUsage class

### Test Infrastructure
- `tests/test_cost_calculator.py` - Existing cost calculator tests
- `tests/test_metrics_db.py` - Database tests
- `tests/test_log_parser.py` - Log parsing tests

### Configuration
- `requirements.txt` - Python dependencies
- `.context-foundry/` - Build artifacts directory

## Existing Code to Leverage

### 1. Cost Calculator Already Cache-Aware!
The cost_calculator.py already has complete cache support:
- TokenUsage class has cache_read_tokens and cache_write_tokens
- calculate_cost() processes cache tokens with proper pricing
- get_cost_breakdown() calculates cache_savings
- pricing_config.json has cache rates for all Claude models

**Key Finding**: We don't need to add cache support to cost calculator - it's already there!

### 2. Prompt Structure (orchestrator_prompt.txt)
Current structure (1,677 lines):
- Lines 0-6: Git Workflow Reference (STATIC)
- Phase instructions (STATIC)
- Enhancement mode reference (STATIC)
- Phase tracking template (STATIC)
- Final output format (STATIC)
- Task configuration parsing (DYNAMIC - varies per build)

**Cache Strategy**:
- CACHEABLE: All phase instructions, templates, workflows (lines 0-1600+)
- DYNAMIC: Task description, working directory, mode flags (injected at runtime)

### 3. MCP Server Integration Point
`tools/mcp_server.py` line ~99+ contains autonomous_build_and_deploy():
- Currently constructs subprocess command with orchestrator prompt
- Needs modification to use cached prompt builder
- Already tracks metrics via collector

## Code to Modify

### Primary Changes
1. **tools/mcp_server.py**:
   - Import cached_prompt_builder
   - Modify autonomous_build_and_deploy() to use cache-aware prompts
   - Add cache tracking to metrics collection

2. **tools/orchestrator_prompt.txt**:
   - Add section markers for cache boundaries
   - Ensure static sections come first
   - Mark dynamic injection points

### New Files Needed
1. **tools/prompts/cache_analysis.py**:
   - Analyze orchestrator_prompt.txt structure
   - Identify static vs dynamic sections
   - Generate segmentation recommendations

2. **tools/prompts/cached_prompt_builder.py**:
   - Split prompt into cacheable/dynamic sections
   - Add Anthropic cache control markers
   - Build requests with proper structure

3. **tools/prompts/cache_config.json**:
   - Enable/disable caching
   - Configure cache settings
   - Model-specific configuration

4. **tests/test_cached_prompt_builder.py**:
   - Unit tests for prompt builder
   - Test cache marker insertion
   - Test prompt segmentation

5. **docs/PROMPT_CACHING.md**:
   - Implementation guide
   - Performance metrics
   - Troubleshooting

## Dependencies Analysis
Current requirements.txt includes:
- anthropic (for Claude API - supports prompt caching)
- fastmcp (for MCP server)
- sqlite3 (built-in, for metrics)

**No new dependencies needed!**

## Architecture Insights

### Cache Flow
1. First build: Send full prompt with cache markers → Cache created (cache_write_tokens)
2. Subsequent builds (within 5 min): Reuse cached prompt → Cache hit (cache_read_tokens)
3. After 5 min: Cache expired → Create new cache

### Integration with Existing Metrics
The existing metrics system is already cache-ready:
- TokenUsage captures cache tokens
- CostCalculator processes them correctly
- Database can store them
- Just need to populate cache token values!

## Risks & Considerations

### Low Risk
- Cost calculator already supports caching (no breaking changes)
- Metrics DB schema may already support cache fields (need to verify)
- Anthropic API supports caching (Claude 3.5+)

### Medium Risk
- Need to ensure prompt segmentation preserves functionality
- Cache invalidation if prompt template changes
- Backward compatibility with non-Anthropic models

### High Risk
- None identified - infrastructure already exists!

## Task Modification Strategy

**Key Insight**: The task specification overestimates the work needed!
- Cost calculator: Already done ✅
- Pricing config: Already done ✅
- Cache token handling: Already done ✅

**Actual Work Needed**:
1. Create prompt builder (new file)
2. Integrate with mcp_server.py (modify existing)
3. Add cache analysis tool (new file)
4. Update orchestrator prompt with markers (modify existing)
5. Add tests (new files)
6. Write documentation (new file)

**Estimated Scope**: ~60% of originally described work (infra exists)

## Next Steps for Scout Phase
1. Verify metrics_db schema supports cache fields
2. Review mcp_server.py autonomous_build_and_deploy() in detail
3. Analyze orchestrator_prompt.txt for optimal cache boundaries
4. Research Anthropic cache control API format
5. Design prompt builder architecture
6. Plan integration testing strategy
