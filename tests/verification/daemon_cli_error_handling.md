# Daemon CLI Error Handling Verification

**Date:** 2025-11-24
**Issue:** #178
**PR:** #179
**Commit:** 51499a0

## Problem

When the Context Foundry daemon runs autonomous builds and `claude` CLI is not in the daemon's PATH, it fails with cryptic errors:

```
[Errno 2] No such file or directory: 'claude'
```

The daemon would retry 3 times, all failing at the Scout phase with no helpful guidance.

## Fix Applied

Added `shutil.which()` checks in:
1. `tools/mcp_utils/phase_execution.py` - Phase execution system
2. `tools/mcp_utils/delegation.py` - Delegation system

## Verification Tests

### Test 1: Delegation System (delegation.py)

**Setup:**
```python
os.environ['PATH'] = '/usr/bin:/bin:/usr/sbin:/sbin'  # Remove claude from PATH
```

**Result:**
```
❌ Error: Claude CLI not found in PATH

The delegation system requires the Claude CLI to be installed and available in PATH.

Installation:
  - Download from: https://claude.com/download
  - Ensure it's in your PATH after installation

Current PATH: /usr/bin:/bin:/usr/sbin:/sbin

Troubleshooting:
  - Verify installation: run 'which claude' in terminal
  - Check PATH: echo $PATH
  - Restart terminal after installation
```

**Status:** ✅ PASS - Clear error with actionable guidance

---

### Test 2: Phase Execution System (phase_execution.py)

**Setup:**
```python
os.environ['PATH'] = '/usr/bin:/bin:/usr/sbin:/sbin'  # Remove claude from PATH

result = run_phase(
    phase_name="Scout",
    phase_prompt_path=Path("tools/prompts/phases/phase_scout.txt"),
    input_instruction="Test task",
    working_directory=Path("/tmp/cf-test-no-cli"),
    phase_timeout=60,
    provider="claude"
)
```

**Error Output:**
```
❌ claude CLI not found in PATH

The Scout phase requires the claude CLI to be installed and available in PATH.

Installation:
  - Claude CLI: https://claude.com/download
  - Gemini CLI: https://ai.google.dev/gemini-api/docs/cli

Current PATH: /usr/bin:/bin:/usr/sbin:/sbin

Environment: Running in daemon? Check daemon's PATH configuration.
```

**Result:**
```
Phase: Scout
Status: failed
Exit Code: 127
Error: claude CLI not found in PATH
Duration: 0s
```

**Status:** ✅ PASS - Clear error, proper exit code (127), helpful message

---

## Key Improvements

### Before Fix
- ❌ Cryptic error: `[Errno 2] No such file or directory: 'claude'`
- ❌ No indication of what's missing
- ❌ No installation guidance
- ❌ Users confused about why daemon fails
- ❌ Daemon retries 3 times with same useless error

### After Fix
- ✅ Clear error message
- ✅ Installation instructions with URLs
- ✅ Current PATH shown for debugging
- ✅ Proper exit code (127 = command not found)
- ✅ Troubleshooting steps included
- ✅ Environment-aware messaging (daemon vs direct)

---

## Evidence Files

- Test script: `/tmp/test_daemon_error.sh` (delegation test)
- Test script: `/tmp/test_phase_error.py` (phase execution test)
- Original failure logs: See failed job e692fbb7-a612-46c6-92f0-c027381de3ca

---

## Conclusion

Both systems now gracefully handle missing Claude CLI with helpful error messages instead of cryptic FileNotFoundError exceptions. The fix is verified and working as designed.

**Verified by:** Claude (AI Assistant)
**Test Date:** 2025-11-24 17:50 PST
**Environment:** macOS, Python 3.9, CF Daemon v0.x
