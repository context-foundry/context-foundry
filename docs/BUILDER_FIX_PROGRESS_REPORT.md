# Builder Fix Progress Report

**Date**: 2025-11-18
**Status**: IN PROGRESS - Root cause identified but fix not yet working

---

## Problem Summary

The Builder phase in autonomous builds was failing to create any files. Builds would stall for 10-14 minutes during Builder phase without producing output (no `build-tasks.json`, no source files).

## Root Cause Identified

**THE BUG**: The `--print` flag in `phase_execution.py:615` tells Claude CLI to only print output, not execute tools!

```python
# Original buggy code (line 612-624)
cmd = [
    "claude",
    "--print",  # <-- THIS WAS THE PROBLEM!
    "--permission-mode",
    "bypassPermissions",
    "--strict-mcp-config",
    ...
]
```

The `--print` flag makes Claude describe what it would do without actually doing it. No Write/Edit tool calls were executed, so no files were ever created.

## Fix Applied

Edited `/Users/name/homelab/context-foundry/tools/mcp_utils/phase_execution.py`:

```python
# Fixed code
cmd = [
    "claude",
    "--permission-mode",
    "bypassPermissions",
    "--strict-mcp-config",  # Prevents loading user MCP servers
    # Note: DO NOT add --print here - it prevents tool execution!
    "--settings",
    '{"thinkingMode": "off"}',
    "--system-prompt",
    phase_prompt,
    input_instruction,
]
```

## Test Results After Fix

### Test 1: Without --strict-mcp-config (removed both --print and --strict-mcp-config)
- **Result**: Scout ran for 167+ seconds without creating scout-report.md
- **Suspected Issue**: Without strict MCP config, Claude loads all user MCP servers which causes massive slowdown

### Test 2: With --strict-mcp-config restored (current state)
- **Result**: Scout fails quickly (~25s) with "Scout failed to create scout-report.md"
- **Retry behavior**: Job retries but fails 3 times
- **Phase events show**: Scout goes "in_progress" -> "failed" repeatedly

---

## Suspected Issues

### 1. --strict-mcp-config May Cause Startup Failures
The `--strict-mcp-config` flag may be failing because:
- No valid MCP config exists for the working directory
- The flag requires a valid `claude_desktop_config.json` or similar

### 2. Phase Timeout Too Short
Scout fails after ~25 seconds. The phase may have a very short timeout configured.

### 3. Claude CLI Exit Code Handling
The phase execution may not be handling Claude's exit codes correctly, treating any output as failure.

### 4. Need to Check stdout/stderr
The daemon isn't capturing or logging Claude's actual output - we need to see what Claude is reporting.

---

## Next Steps for Investigation

1. **Check phase timeouts in autonomous_build.py**
   - Look for SCOUT_TIMEOUT or similar
   - May be too short at 25s

2. **Remove --strict-mcp-config again, add MCP isolation differently**
   - Perhaps use `--mcp-config /dev/null` or empty config
   - Or use environment variable to disable MCP

3. **Add stdout/stderr logging to phase_execution.py**
   - Print `result.stdout` and `result.stderr` after subprocess completes
   - This will show what Claude is actually outputting/erroring

4. **Test claude CLI directly in terminal**
   ```bash
   cd /Users/name/homelab/test-builder-fix-v2
   claude --permission-mode bypassPermissions \
          --strict-mcp-config \
          --system-prompt "$(cat phase_scout.txt)" \
          "Create scout-report.md for: simple Python calculator"
   ```
   This bypasses the daemon entirely to see raw behavior.

5. **Check if bypassPermissions works with strict-mcp-config**
   - These flags may conflict

---

## Files Modified

- `/Users/name/homelab/context-foundry/tools/mcp_utils/phase_execution.py` (lines 612-624)
  - Removed `--print` flag
  - Restored `--strict-mcp-config`
  - Added explanatory comment

---

## Session Artifacts

- Test job 1: `460a0221-1217-4b9b-97a7-6dd33336c9e6` (cancelled - ran 193s without progress)
- Test job 2: `3687361a-6f47-47a5-b650-71972f2f6e3c` (failed - Scout not creating files)
- Test directories:
  - `/Users/name/homelab/test-builder-fix/`
  - `/Users/name/homelab/test-builder-fix-v2/`

---

## Key Insight

**The original bug (--print flag) was definitely wrong** - this was preventing all file creation across ALL phases, not just Builder.

However, fixing that exposed another issue with how Claude CLI is being invoked. The next session should focus on getting the CLI invocation right - either by:
1. Testing different flag combinations directly in terminal
2. Adding proper stdout/stderr logging to see what's failing
3. Checking if there are other required flags or configurations

---

## Commit to Make

Once working, commit should reference:
- Bug: `--print` flag prevents tool execution
- Fix: Remove flag, add warning comment
