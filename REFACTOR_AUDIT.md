# Audit Report: REFACTOR_PLAN.md

**Date:** December 19, 2025
**Auditor:** DevOps Specialist

## Executive Summary
The proposed refactor plan correctly identifies the need for code reduction and cross-platform compatibility. However, the plan lacks critical safety mechanisms for the destructive "Phase 1" and underestimates the infrastructure required to verify "Phase 2" (Windows Compatibility).

## Critical Findings

### 1. Missing Windows CI Infrastructure (High Risk)
The plan relies on "Week 2: Windows Testing" but the current `ci.yml` **only runs on `ubuntu-latest`**.
- **Risk:** "Tested" status in the results table will be manually verified and brittle. Regressions will happen immediately after the refactor if CI doesn't enforce Windows compatibility.
- **Recommendation:** Update `.github/workflows/ci.yml` to use a matrix strategy:
  ```yaml
  runs-on: ${{ matrix.os }}
  strategy:
    matrix:
      os: [ubuntu-latest, windows-latest]
  ```

### 2. Destructive Clean-up Protocol (Medium Risk)
"Phase 1: Remove Noise" suggests using `rm -rf` on working directories (`projects/`, `sandbox/`, `working/`) and tools.
- **Risk:** Data loss if users have local uncommitted changes or valuable state in these directories.
- **Recommendation:** Implement a "trash" or "archive" move instead of immediate deletion. Move to `.trash/` and allow user to delete manually later.

### 3. Dependency Verification (Medium Risk)
The plan identifies `subprocess` calls but misses `psutil` usage verification.
- **Context:** `requirements.txt` includes `psutil`. Process management (killing trees, checking status) behaves differently on Windows.
- **Recommendation:** Add `psutil` wrappers to the "Path Handling Audit" section in Phase 2.

### 4. Daemon "Decision Paralysis" (Low Risk)
Phase 3 leaves the Daemon architecture open ("Option A, B, C").
- **Risk:** Refactoring `mcp_utils` (Phase 4) depends heavily on how the daemon invokes them. If we choose "Option C" (Simple Job Runner), much of the code integration in Phase 4 might be redundant or different.
- **Recommendation:** Decide on Phase 3 approach **before** Phase 4.

## Gaps in Plan

1.  **Rollback Strategy:** No mention of how to revert if the "Remove Noise" breaks obscure dependencies (e.g., if `tools/metrics` is imported by a script not in the main path).
2.  **Versioning:** The plan does not mention bumping `__version__.py` or creating a git tag before starting.
3.  **Documentation:** "Week 4: Polish" is too late for documentation updates if we are changing architecture in Phase 2/3.

## Refined Plan Suggestion

**Phase 0: Safety & CI (New)**
1.  Tag current state `v1.backup`.
2.  Enable `windows-latest` in GitHub Actions.
3.  Run current test suite on Windows to establish baseline failures.

**Phase 1: Safe Cleanup**
1.  Move directories to `_archive_2025/` instead of `rm -rf`.
2.  Verify `mcp_server` startup.

**Phase 2: Windows Port**
1.  Fix paths using `pathlib` (as planned).
2.  Abstract `psutil` and `subprocess`.
3.  **Gate:** CI must pass on Windows.

**Phase 3: Daemon Decision & Execution**
1.  Select Option B (Slim Daemon) as the balanced approach.
2.  Execute split.

**Phase 4: Consolidation**
1.  Merge modules.
