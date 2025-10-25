# Anthropic Prompt Caching Architecture

## System Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                    Autonomous Build Workflow                          │
│                                                                        │
│  autonomous_build_and_deploy() [mcp_server.py:1046]                  │
│         │                                                              │
│         ├──> Load orchestrator_prompt.txt (~9,000 tokens)            │
│         │                                                              │
│         ├──> Build task configuration (task, mode, working_dir)      │
│         │                                                              │
│         v                                                              │
│  ┌───────────────────────────────────────────────────────────┐       │
│  │         Cached Prompt Builder (NEW MODULE)                 │       │
│  │  ┌─────────────────────────────────────────────────────┐  │       │
│  │  │  1. Read orchestrator_prompt.txt                    │  │       │
│  │  │  2. Split into STATIC (~8,500) + DYNAMIC (~500)     │  │       │
│  │  │  3. Add cache_control marker to STATIC section      │  │       │
│  │  │  4. Build structured prompt with cache markers      │  │       │
│  │  └─────────────────────────────────────────────────────┘  │       │
│  └───────────────────────────────┬───────────────────────────┘       │
│                                  │                                    │
│                                  v                                    │
│         Execute: claude --print --system-prompt <cached_prompt>      │
│                                  │                                    │
└──────────────────────────────────┼────────────────────────────────────┘
                                   │
         ┌─────────────────────────┴───────────────────────┐
         │                                                  │
         v                                                  v
  ┌─────────────────┐                            ┌─────────────────┐
  │  First Request   │                            │ Subsequent Reqs │
  │  (Cache Miss)    │                            │  (Cache Hit)    │
  ├─────────────────┤                            ├─────────────────┤
  │ • Send 9K tokens │                            │ • Send 500 toks │
  │ • Create cache   │                            │ • Read cache    │
  │ • Cost: $0.034   │                            │ • Cost: $0.003  │
  │ • cache_write    │                            │ • cache_read    │
  └─────────────────┘                            └─────────────────┘
         │                                                  │
         └─────────────────────┬────────────────────────────┘
                               │
                               v
                    ┌────────────────────────┐
                    │  Metrics Collection    │
                    │  (Already Exists!)     │
                    ├────────────────────────┤
                    │ • TokenUsage class     │
                    │ • cache_read_tokens    │
                    │ • cache_write_tokens   │
                    │ • CostCalculator       │
                    │ • cache_savings calc   │
                    └────────────────────────┘
```

## Module Specifications

### 1. Cached Prompt Builder (`tools/prompts/cached_prompt_builder.py`)

**Purpose**: Build prompts with Anthropic cache control markers

**Main Function**:
```python
def build_cached_prompt(
    task_config: dict,
    orchestrator_prompt_path: str = "tools/orchestrator_prompt.txt",
    enable_caching: bool = True,
    cache_ttl: str = "5m"
) -> str:
    """
    Build orchestrator prompt with cache markers.
    
    Args:
        task_config: Task configuration dict (task, mode, working_dir, etc.)
        orchestrator_prompt_path: Path to orchestrator prompt template
        enable_caching: Enable/disable caching (default: True)
        cache_ttl: Cache TTL - "5m" or "1h" (default: "5m")
    
    Returns:
        System prompt string with cache markers embedded
        
    Strategy:
        1. Read orchestrator_prompt.txt
        2. Split at cache boundary marker (line ~1650)
        3. Build static section with cache marker
        4. Append dynamic task configuration
        5. Return combined prompt
    """
```

**Prompt Structure**:
```
=== STATIC SECTION (Cacheable) ===
YOU ARE AN AUTONOMOUS ORCHESTRATOR AGENT
Version: v1.2.1 (No Livestream)
...
[All phase instructions]
[Git workflow reference]
[Enhancement mode reference]
[Phase tracking templates]
[Final output format]
[Critical rules]
[Error handling]
...
<<CACHE_BOUNDARY>>

=== DYNAMIC SECTION (Not Cached) ===
AUTONOMOUS BUILD TASK

CONFIGURATION:
{
  "task": "...",
  "working_directory": "...",
  "mode": "...",
  ...
}

Execute the full Scout → Architect → Builder → Test → Deploy workflow.
Self-healing test loop is ENABLED. Fix and retry up to 3 times if tests fail.

Return JSON summary when complete.
BEGIN AUTONOMOUS EXECUTION NOW.
```

**Cache Marker Injection**:
The cache marker is injected as a special comment at the cache boundary:

```
... end of static content ...

<!-- ANTHROPIC_CACHE_CONTROL: {"type": "ephemeral", "ttl": "5m"} -->

AUTONOMOUS BUILD TASK
...
```

Claude Code will pass this to the Anthropic API which processes cache control markers.

**Token Counting**:
```python
def count_prompt_tokens(text: str, model: str = "claude-sonnet-4") -> int:
    """
    Count tokens in prompt using anthropic package.
    
    Validates cache boundary meets minimum (1024 tokens for Sonnet).
    """
    from anthropic import Anthropic
    client = Anthropic()
    count = client.count_tokens(text)
    return count
```

**Fallback Behavior**:
- If cache disabled: Return prompt without markers
- If non-Claude model: Return prompt without markers
- If static section < 1024 tokens: Warn and disable caching
- If Claude Code doesn't support markers: Degrade gracefully

### 2. Cache Configuration (`tools/prompts/cache_config.json`)

**Schema**:
```json
{
  "version": "1.0.0",
  "caching": {
    "enabled": true,
    "ttl": "5m",
    "min_tokens": 1024,
    "cache_boundary_line": 1650,
    "models_supported": [
      "claude-sonnet-4",
      "claude-sonnet-3-5",
      "claude-opus-4",
      "claude-haiku-3-5"
    ]
  },
  "prompt_version": {
    "hash": "abc123def456",
    "last_updated": "2025-01-13T00:00:00Z",
    "comment": "Version hash for cache invalidation"
  },
  "metrics": {
    "track_cache_hits": true,
    "track_token_savings": true,
    "track_cost_savings": true
  }
}
```

**Configuration Loading**:
```python
class CacheConfig:
    def __init__(self, config_path: str = "tools/prompts/cache_config.json"):
        self.config = self._load_config(config_path)
    
    def is_caching_enabled(self) -> bool:
        return self.config["caching"]["enabled"]
    
    def get_cache_ttl(self) -> str:
        return self.config["caching"]["ttl"]
    
    def is_model_supported(self, model: str) -> bool:
        supported = self.config["caching"]["models_supported"]
        return any(m in model for m in supported)
```

### 3. Cache Analysis Tool (`tools/prompts/cache_analysis.py`)

**Purpose**: Analyze orchestrator prompt and recommend cache boundaries

**Main Function**:
```python
def analyze_prompt_structure(
    prompt_path: str = "tools/orchestrator_prompt.txt"
) -> dict:
    """
    Analyze orchestrator prompt for optimal cache segmentation.
    
    Returns:
        {
            "total_lines": 1677,
            "total_tokens": 9100,
            "recommended_boundary": 1650,
            "static_section": {
                "lines": 1650,
                "tokens": 8500,
                "cacheable": true
            },
            "dynamic_section": {
                "lines": 27,
                "tokens": 600,
                "cacheable": false
            },
            "recommendations": [
                "Static section meets minimum token requirement (8500 > 1024)",
                "Cache boundary at line 1650 (after 'BEGIN EXECUTION NOW')",
                "Expected savings: 90% on cached requests"
            ]
        }
    """
```

**Analysis Strategy**:
1. Read orchestrator_prompt.txt
2. Count tokens per section
3. Identify natural boundaries (phase endings, section markers)
4. Validate static section meets minimum tokens
5. Calculate expected savings
6. Generate recommendations

**CLI Interface**:
```bash
python tools/prompts/cache_analysis.py

Output:
📊 Orchestrator Prompt Cache Analysis
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total lines: 1677
Total tokens: ~9,100

Static section (cacheable):
  Lines: 1-1650
  Tokens: ~8,500
  ✓ Meets minimum (1024)

Dynamic section:
  Lines: 1651-1677  
  Tokens: ~600

Recommended boundary: Line 1650
Expected savings: 90% on cache hits
Cost: $0.034 → $0.003 per build
```

### 4. MCP Server Integration (`tools/mcp_server.py`)

**Modification Points**:

**Current Code** (lines 1269-1293):
```python
# Load orchestrator system prompt
orchestrator_prompt_path = Path(__file__).parent / "orchestrator_prompt.txt"
if not orchestrator_prompt_path.exists():
    return json.dumps({"status": "error", ...})

with open(orchestrator_prompt_path) as f:
    system_prompt = f.read()

# Build task prompt
task_prompt = f"""AUTONOMOUS BUILD TASK

CONFIGURATION:
{json.dumps(task_config, indent=2)}

Execute the full Scout → Architect → Builder → Test → Deploy workflow.
...
"""

# Build command
cmd = [
    "claude", "--print",
    "--permission-mode", "bypassPermissions",
    "--strict-mcp-config",
    "--settings", '{"thinkingMode": "off"}',
    "--system-prompt", system_prompt,
    task_prompt
]
```

**New Code** (with caching):
```python
from tools.prompts.cached_prompt_builder import build_cached_prompt
from tools.prompts.cache_config import CacheConfig

# Load cache configuration
cache_config = CacheConfig()
enable_caching = cache_config.is_caching_enabled()

# Build cached prompt
orchestrator_prompt_path = Path(__file__).parent / "orchestrator_prompt.txt"
system_prompt = build_cached_prompt(
    task_config=task_config,
    orchestrator_prompt_path=str(orchestrator_prompt_path),
    enable_caching=enable_caching,
    cache_ttl=cache_config.get_cache_ttl()
)

# Task prompt is now embedded in system_prompt
# Build command (same as before)
cmd = [
    "claude", "--print",
    "--permission-mode", "bypassPermissions",
    "--strict-mcp-config",
    "--settings", '{"thinkingMode": "off"}',
    "--system-prompt", system_prompt,
    ""  # Empty user message (everything in system prompt)
]
```

**Key Changes**:
1. Import cached_prompt_builder
2. Load cache configuration
3. Call build_cached_prompt() instead of direct file read
4. Task configuration embedded in system prompt (not separate arg)
5. Cache markers handled internally by builder

**Backward Compatibility**:
- If caching disabled: Works exactly as before
- If cache_config.json missing: Falls back to non-cached
- No breaking changes to autonomous_build_and_deploy() signature

### 5. Orchestrator Prompt Modifications (`tools/orchestrator_prompt.txt`)

**Add Cache Boundary Marker** (line ~1650):

```
═══════════════════════════════════════════════════════════
END OF STATIC ORCHESTRATOR INSTRUCTIONS
═══════════════════════════════════════════════════════════

<<CACHE_BOUNDARY_MARKER>>

The following content varies per build and should NOT be cached:
- Task description
- Working directory
- Mode flags
- Configuration JSON
```

**No other changes needed** - existing prompt structure is already optimal for caching!

## Integration with Existing Systems

### Metrics System (Already Complete!)

**No changes needed** - existing infrastructure already supports caching:

✅ **TokenUsage class** (`tools/metrics/log_parser.py`):
```python
@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0      # ← Already exists!
    cache_write_tokens: int = 0     # ← Already exists!
    model: Optional[str] = None
    request_id: Optional[str] = None
```

✅ **CostCalculator** (`tools/metrics/cost_calculator.py`):
```python
def calculate_cost(self, usage: TokenUsage, model: Optional[str] = None) -> float:
    pricing = self.get_model_pricing(model)
    
    input_cost = (usage.input_tokens / 1_000_000) * pricing['input_per_mtok']
    output_cost = (usage.output_tokens / 1_000_000) * pricing['output_per_mtok']
    cache_write_cost = (usage.cache_write_tokens / 1_000_000) * pricing['cache_write_per_mtok']  # ← Already works!
    cache_read_cost = (usage.cache_read_tokens / 1_000_000) * pricing['cache_read_per_mtok']    # ← Already works!
    
    return input_cost + output_cost + cache_write_cost + cache_read_cost
```

✅ **Pricing Config** (`tools/metrics/pricing_config.json`):
```json
{
  "claude-sonnet-4-20250514": {
    "input_per_mtok": 3.00,
    "output_per_mtok": 15.00,
    "cache_write_per_mtok": 3.75,    // ← Already configured!
    "cache_read_per_mtok": 0.30      // ← Already configured!
  }
}
```

**Result**: Once we populate cache_read_tokens and cache_write_tokens, everything else works automatically!

## Testing Strategy

### Unit Tests (`tests/test_cached_prompt_builder.py`)

```python
def test_build_cached_prompt_with_caching_enabled():
    """Test prompt builder with caching enabled"""
    config = {"task": "Build app", "mode": "new_project"}
    prompt = build_cached_prompt(config, enable_caching=True)
    
    assert "ANTHROPIC_CACHE_CONTROL" in prompt
    assert "AUTONOMOUS BUILD TASK" in prompt
    assert '"task": "Build app"' in prompt

def test_build_cached_prompt_with_caching_disabled():
    """Test prompt builder with caching disabled"""
    config = {"task": "Build app"}
    prompt = build_cached_prompt(config, enable_caching=False)
    
    assert "ANTHROPIC_CACHE_CONTROL" not in prompt

def test_token_counting():
    """Test token counting meets minimum"""
    with open("tools/orchestrator_prompt.txt") as f:
        static_section = f.read()[:50000]  # First ~1650 lines
    
    tokens = count_prompt_tokens(static_section)
    assert tokens >= 1024, f"Static section only {tokens} tokens (need 1024+)"

def test_cache_boundary_marker():
    """Test cache boundary is correctly placed"""
    with open("tools/orchestrator_prompt.txt") as f:
        content = f.read()
    
    assert "<<CACHE_BOUNDARY_MARKER>>" in content
```

### Integration Tests (`tests/test_cache_integration.py`)

```python
@mock.patch("subprocess.Popen")
def test_autonomous_build_uses_cached_prompt(mock_popen):
    """Test autonomous_build_and_deploy uses cached prompt builder"""
    # Mock process
    mock_process = MagicMock()
    mock_process.poll.return_value = None
    mock_popen.return_value = mock_process
    
    # Call autonomous build
    result = autonomous_build_and_deploy(
        task="Test build",
        working_directory="/tmp/test"
    )
    
    # Verify subprocess called with cache markers
    call_args = mock_popen.call_args
    cmd = call_args[0][0]
    system_prompt_idx = cmd.index("--system-prompt") + 1
    system_prompt = cmd[system_prompt_idx]
    
    assert "ANTHROPIC_CACHE_CONTROL" in system_prompt

def test_cost_calculation_with_cache():
    """Test cost calculator handles cached tokens correctly"""
    usage = TokenUsage(
        input_tokens=100,
        output_tokens=200,
        cache_read_tokens=8500,  # Cached static prompt
        cache_write_tokens=0
    )
    
    calc = CostCalculator()
    cost = calc.calculate_cost(usage, "claude-sonnet-4")
    
    # Verify cost includes cache discount
    expected_cost = (
        (100 / 1_000_000) * 3.00 +      # Input
        (200 / 1_000_000) * 15.00 +     # Output
        (8500 / 1_000_000) * 0.30       # Cache read (90% discount!)
    )
    assert abs(cost - expected_cost) < 0.0001
```

### End-to-End Test (Manual)

```bash
# Test 1: First build (cache miss)
echo "🧪 Test 1: First build (cache creation)"
time foundry build test-cache-1 "Create hello.py that prints hello"

# Expected:
# - cache_write_tokens: ~8500
# - cache_read_tokens: 0
# - Cost: ~$0.034

# Test 2: Second build within 5 min (cache hit)
echo "🧪 Test 2: Second build (cache hit)"
time foundry build test-cache-2 "Create goodbye.py that prints goodbye"

# Expected:
# - cache_write_tokens: 0
# - cache_read_tokens: ~8500
# - Cost: ~$0.003 (90% savings!)

# Test 3: Wait for cache expiration
echo "🧪 Test 3: After cache expiration (5+ min)"
sleep 310  # Wait 5min 10sec
time foundry build test-cache-3 "Create test.py that prints test"

# Expected:
# - cache_write_tokens: ~8500 (cache recreated)
# - cache_read_tokens: 0
# - Cost: ~$0.034

# Verify metrics
sqlite3 ~/.context-foundry/metrics.db << SQL
SELECT 
    session_id,
    cache_write_tokens,
    cache_read_tokens,
    total_cost
FROM builds
WHERE session_id LIKE 'test-cache-%'
ORDER BY created_at;
SQL
```

## Implementation Steps

### Step 1: Create Cached Prompt Builder
- File: `tools/prompts/cached_prompt_builder.py`
- Implement: `build_cached_prompt()`, `count_prompt_tokens()`
- Add: Cache marker injection logic
- Validate: Token counting meets minimum

### Step 2: Create Cache Configuration
- File: `tools/prompts/cache_config.json`
- Define: Schema with enabled, ttl, models
- Create: `CacheConfig` class for loading

### Step 3: Create Cache Analysis Tool
- File: `tools/prompts/cache_analysis.py`
- Implement: `analyze_prompt_structure()`
- Add: CLI interface for analysis
- Generate: Segmentation recommendations

### Step 4: Modify Orchestrator Prompt
- File: `tools/orchestrator_prompt.txt`
- Add: Cache boundary marker at line ~1650
- Document: Static vs dynamic sections
- Validate: No functional changes

### Step 5: Integrate with MCP Server
- File: `tools/mcp_server.py`
- Import: `cached_prompt_builder`, `CacheConfig`
- Modify: `autonomous_build_and_deploy()` lines 1269-1293
- Test: Backward compatibility

### Step 6: Write Tests
- File: `tests/test_cached_prompt_builder.py`
- Tests: 10+ unit tests for prompt builder
- File: `tests/test_cache_integration.py`
- Tests: 5+ integration tests with mocking

### Step 7: Create Documentation
- File: `docs/PROMPT_CACHING.md`
- Sections: Overview, Architecture, Usage, Troubleshooting
- Include: Cost savings examples, metrics

## Success Criteria

✅ **Prompt builder creates valid cached prompts**
- Cache markers correctly placed
- Static section >= 1024 tokens
- Dynamic content injected properly

✅ **MCP server integration works**
- autonomous_build_and_deploy() uses cached prompts
- Backward compatible (no breaking changes)
- Falls back gracefully if caching unavailable

✅ **Token savings achieved**
- First build: cache_write_tokens populated
- Subsequent builds: cache_read_tokens populated
- 80-90% token reduction on cached requests

✅ **Cost savings validated**
- CostCalculator computes correct costs
- Cache discounts applied (0.1× for reads)
- Session summaries show cache_savings

✅ **Tests pass**
- 90%+ code coverage
- Unit tests validate logic
- Integration tests verify behavior
- E2E test shows real savings

✅ **Documentation complete**
- PROMPT_CACHING.md comprehensive
- Architecture diagrams included
- Troubleshooting guide provided

## Cost Savings Projection

**Scenario: 50 builds per month**

**Without Caching**:
- 50 builds × 9,000 tokens × $3.00/1M = $1.35/month

**With Caching** (5-minute TTL, sequential builds):
- Build 1: 9,000 tokens × $3.75/1M = $0.034 (cache creation)
- Builds 2-50: 49 × (500 + 8,500 cache) tokens = $0.147
  - 500 regular × $3.00/1M = $0.0015 per build
  - 8,500 cached × $0.30/1M = $0.0026 per build
  - Total per build: $0.0041
  - 49 builds: $0.20

**Total with caching: $0.234/month**
**Savings: $1.12/month (83% reduction)**

**Annual savings: $13.44/year**

For heavy users (200 builds/month): **$54/year savings**

## Risk Mitigation

### Risk 1: Claude Code CLI Compatibility
- **If unsupported**: Fall back to current method
- **Monitoring**: Check logs for cache token presence
- **Testing**: Verify with real claude CLI

### Risk 2: Prompt Version Changes
- **Prevention**: Track prompt hash in config
- **Warning**: Alert when hash changes
- **Recovery**: Automatic cache recreation

### Risk 3: Cache TTL Too Short
- **Solution**: Make TTL configurable (5m or 1h)
- **Monitoring**: Track cache hit rate
- **Adjustment**: Recommend 1h for heavy users

### Risk 4: Token Counting Inaccuracy
- **Prevention**: Use anthropic.count_tokens()
- **Validation**: Add buffer (1100+ tokens)
- **Testing**: Verify counts in E2E tests

## Next Phase: Builder

Implementation ready. Proceed to build phase with:
1. Parallel task execution (if applicable)
2. Create all new files
3. Modify existing files
4. Run tests continuously
5. Fix any issues immediately
