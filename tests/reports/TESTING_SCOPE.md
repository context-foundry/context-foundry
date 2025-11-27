# Test Coverage and Scope

This document clearly defines what IS and IS NOT tested by the automated test suites.

## Test Results Evidence

See `test_results_evidence.txt` for captured pytest output showing all 27 tests passing.

## Architecture Parsing Tests (17 tests)

**File:** `tests/test_architecture_parsing.py`

### What IS Tested ✅

1. **Unit Tests (9 tests - TestClaudeCliParsing)**
   - Claude CLI not installed → FileNotFoundError
   - Claude CLI success → JSON parsing
   - JSON wrapped in markdown code blocks → extraction
   - Claude CLI non-zero exit → RuntimeError
   - Claude CLI timeout → TimeoutExpired
   - Claude CLI empty output → RuntimeError
   - Claude CLI invalid JSON → JSONDecodeError
   - Correct flags used (--print, --dangerously-skip-permissions)
   - Temp file cleanup on failure

2. **Integration Tests (3 tests - TestArchitectureParsingIntegration)**
   - FileNotFoundError triggers BAML fallback
   - TimeoutExpired triggers BAML fallback
   - json.JSONDecodeError triggers BAML fallback

3. **End-to-End Tests (5 tests - TestProductionArchitectureParsingEndToEnd)**
   - **Calls actual production function:** `parse_and_save_architecture_json()`
   - Claude CLI success → architecture.json saved to disk
   - BAML fallback executes → architecture.json saved to disk
   - BAML timeout → returns None, no file saved
   - Dual failure (CLI + BAML) → returns None, no file saved
   - Missing architecture.md → returns None, no file saved

### What IS NOT Tested ❌

- Real Claude CLI subprocess execution (mocked)
- Real BAML LLM calls (mocked)
- Network/API failures during BAML execution
- File system permission errors
- Concurrent access to architecture.json

---

## Random ID Tests (10 tests)

**File:** `tests/test_runner_random_id.py`

### What IS Tested ✅

1. **Simulated Logic Tests (8 tests)**
   - Random ID appending logic (TestRandomIDAppending: 3 tests)
   - Mode auto-switching logic (TestModeAutoSwitching: 2 tests)
   - Collision detection logic (TestCollisionDetection: 2 tests)
   - Job params update logic (TestJobParamsUpdate: 1 test)

2. **Pre-Run Integration Tests (2 tests - TestRunnerPreRunLogic)**
   - **Calls actual:** `Runner.run(job)`
   - **Verifies:**
     - Random ID appended to working_directory
     - Mode auto-switched from new_project → enhancement
     - **store.save_job() called with updated params**
     - Updated params persisted to database
     - Runner.run() returns success result

### What IS NOT Tested ❌

**IMPORTANT:** These tests mock `_run_autonomous_build`, so they verify ONLY the pre-run parameter mutations. The following are NOT tested:

- ❌ Subprocess spawning and polling loop
- ❌ Discord notification hooks
- ❌ Active task tracking in runner.active_tasks
- ❌ Log emission via _emit_log()
- ❌ Phase event emission via store.save_phase_event()
- ❌ Pattern merge via _merge_patterns()
- ❌ Job status updates via store.update_job_status()
- ❌ Error handling in polling loop
- ❌ Timeout enforcement
- ❌ Process cleanup

**Why this limitation?**

To test the full execution path would require either:
1. Running actual autonomous builds (too slow for unit tests)
2. Complex subprocess mocking (brittle and hard to maintain)
3. Refactoring Runner to make these paths testable (future work)

**What we do test:**

The critical bug we found and fixed: **Random ID and mode changes are persisted to the database via store.save_job()**.

---

## Summary

**Total: 27 tests**
- 17 architecture parsing tests (9 unit + 3 integration + 5 end-to-end)
- 10 random ID tests (8 simulated + 2 pre-run integration)

**Test Evidence:**
- `test_results_evidence.txt` - Captured pytest output showing 27 passed

**Key Achievements:**
- ✅ Production architecture parsing code tested end-to-end with file I/O
- ✅ Critical Runner bug found: store.save_job() calls were missing
- ✅ Pre-run logic verified: random ID and mode switch persisted correctly

**Known Gaps:**
- Runner polling loop, notifications, logs, phase events, and pattern merge not tested
- Full subprocess execution path not tested

**Future Work:**
- Add functional tests that run actual builds (slow but comprehensive)
- Refactor Runner to make polling loop testable without subprocess
- Add tests for notification hooks, log emission, pattern merge
