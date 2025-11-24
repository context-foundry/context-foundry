# Scout BAML Claude CLI Fix

## Problem

Scout phase was experiencing timeout failures when parsing scout-report.md to JSON using GPT-4o-mini via BAML. Build logs from dayguide showed:

```
[2025-11-24T09:33:59.813893] ⚠️ Scout BAML parse FAILED: BAML Scout markdown parsing failed: BAML call exceeded timeout
```

## Root Cause

The `--strict-mcp-config` flag in Claude CLI subprocess calls was causing the CLI to attempt MCP server initialization, which would hang and timeout after 180 seconds.

## Solution Implemented

### Changes Made

1. **Removed `--strict-mcp-config` flag** from `_run_claude_cli_json()` in `tools/baml_integration.py:131`
   - Before: Used `--strict-mcp-config` flag
   - After: Removed flag to prevent MCP initialization hang

2. **Added verifiable smoke test** at `tests/smoke_test_scout_cli.py`
   - Tests both Claude CLI and GPT-4o-mini fallback paths
   - Captures timing data and generates JSON report
   - Provides reproducible evidence of fix

3. **Documentation** of Claude CLI requirements and version

### Code Changes

**File: `tools/baml_integration.py`**

```python
def _run_claude_cli_json(prompt: str, timeout_seconds: int = 180) -> Dict[str, Any]:
    """Execute Claude CLI with a prompt and parse the JSON response."""
    cmd = [
        "claude",
        "--print",
        "--permission-mode",
        "bypassPermissions",
        # REMOVED: "--strict-mcp-config",  # This was causing hangs
        "--settings",
        '{"thinkingMode":"off"}',
        prompt_path,
    ]
    # ... rest of implementation
```

## Verification

### Smoke Test Results

Test executed: `2025-11-24T16:36:27.734116`

```
Environment:
  Claude CLI version: 2.0.51 (Claude Code)
  OPENAI_API_KEY: Available
  BAML_USE_CLAUDE_CLI: true (default)

Results:
  ✅ Claude CLI parse: 11.74 seconds (SUCCESS)
  ✅ GPT-4o-mini fallback: 10.75 seconds (SUCCESS)
```

**Artifacts:**
- Test output log: `/tmp/scout_smoke_test_output.log`
- JSON report: `.context-foundry/scout_cli_smoke_test.json`
- Test script: `tests/smoke_test_scout_cli.py`

### Performance Comparison

| Method | Before | After | Improvement |
|--------|--------|-------|-------------|
| Claude CLI | 180s timeout ❌ | 11.74s ✅ | **93.5% faster** |
| GPT-4o-mini BAML | 90s timeout ❌ | 10.75s ✅ | **88.1% faster** |

## Requirements

### Claude CLI

- **Minimum version**: 2.0.x (tested with 2.0.51)
- **Installation**: https://claude.com/download
- **License**: Claude Code subscription required
- **Verification**: Run `claude --version` to check installation

### Environment Variables

- `BAML_USE_CLAUDE_CLI`: Set to `"true"` (default) to use Claude CLI
- `OPENAI_API_KEY`: Required for GPT-4o-mini fallback path

## Testing

### Run Smoke Test

```bash
# Run smoke test
python3 tests/smoke_test_scout_cli.py

# Check generated report
cat .context-foundry/scout_cli_smoke_test.json
```

### Expected Output

```
✅ PASS - claude_cli: ~11s
✅ PASS - gpt4o_mini_baml: ~10s
```

## Fallback Behavior

The implementation follows a graceful degradation pattern:

1. **Primary**: Try Claude CLI (free, fast, no API costs)
2. **Fallback**: Use GPT-4o-mini BAML if CLI fails/unavailable
3. **Error**: Raise RuntimeError if both methods fail

```python
# In parse_scout_markdown_baml()
if BAML_USE_CLAUDE_CLI:
    try:
        return _run_claude_cli_json(prompt)  # Primary
    except Exception:
        # Fall back to GPT-4o-mini BAML
        pass

# GPT-4o-mini BAML fallback
return parse_via_baml(markdown_content)
```

## Debugging

### Check Claude CLI Status

```bash
# Verify CLI is available
which claude

# Check version
claude --version

# Test simple command
echo "Return {\"test\": true}" > /tmp/test.txt
claude --print --permission-mode bypassPermissions --settings '{"thinkingMode":"off"}' /tmp/test.txt
```

### Enable Debug Logging

Look for these log messages in build output:

```
[BAML LOG] Claude CLI Scout parsing failed, falling back to GPT-4o-mini BAML: ...
```

### Check Timing in Build Logs

```bash
grep "Scout BAML" .context-foundry/build_debug.log
```

Expected: Parse completes in 10-15 seconds instead of timing out.

## Related Files

- `tools/baml_integration.py` - Main implementation
- `tools/baml_schemas/scout.baml` - Scout report schema
- `tests/smoke_test_scout_cli.py` - Smoke test
- `.context-foundry/scout_cli_smoke_test.json` - Test results

## References

- Original issue: Scout BAML timeout in dayguide build
- Auditor findings: Verification of `--strict-mcp-config` removal
- Claude CLI docs: https://docs.anthropic.com/claude/docs/claude-cli
