# Context Foundry Refactoring Plan

**Goal:** Simplify codebase, ensure Windows compatibility, reduce from ~115k to ~40k lines

**Audit Status:** Reviewed by DevOps Specialist - all findings addressed below

---

## Current Architecture

```
context-foundry/
├── tools/                      # Core MCP tools and utilities
│   ├── mcp_server.py          # MCP server entrypoint (1.6k lines)
│   ├── mcp_utils/             # Core business logic (16k lines)
│   └── dashboard/             # Web UI at :5174 → proxies to :8421
├── context_foundry/           # Python package
│   ├── daemon/                # Job management (18.5k lines)
│   └── storage/               # S3 pattern storage
├── apps/
│   └── context-foundry-desktop/  # Mac Tauri app (serves :8420)
└── [many optional/archived dirs]
```

## Port Architecture
- **:8420** - Dashboard served by Tauri app (or cfd daemon directly)
- **:8421** - HTTP API (daemon REST endpoints)
- **:5174** - Vite dev server (development only)

---

## Phase 0: Safety & CI Setup (AUDIT FINDING #1, #2)

### 0.1 Create backup tag
```bash
git tag -a v2.5.4-pre-refactor -m "Backup before cross-platform refactor"
git push origin v2.5.4-pre-refactor
```

### 0.2 Enable Windows CI
Update `.github/workflows/ci.yml` to add Windows matrix:

```yaml
test:
  name: Run Tests
  runs-on: ${{ matrix.os }}
  strategy:
    matrix:
      os: [ubuntu-latest, windows-latest]
      python-version: ['3.10', '3.11', '3.12']
    exclude:
      # Reduce matrix size - test 3.11 on Windows only initially
      - os: windows-latest
        python-version: '3.10'
      - os: windows-latest
        python-version: '3.12'
```

### 0.3 Establish Windows baseline
Run current test suite on Windows to identify existing failures before refactor.

### 0.4 Rollback strategy (AUDIT GAP #1)
If refactor breaks dependencies:
1. `git revert` the cleanup commit
2. Or restore from `v2.5.4-pre-refactor` tag
3. Keep `_archive_2025/` for 30 days before permanent deletion

---

## Phase 1: Safe Cleanup (AUDIT FINDING #2)

### 1.1 Move directories to archive (NOT rm -rf)
```bash
mkdir -p _archive_2025

# Move instead of delete
mv archive/ _archive_2025/archive_old/
mv logs/ _archive_2025/logs/
mv htmlcov/ _archive_2025/htmlcov/
mv builds/ _archive_2025/builds/
mv flowise-builds/ _archive_2025/flowise-builds/
mv projects/ _archive_2025/projects/
mv sandbox/ _archive_2025/sandbox/
mv working/ _archive_2025/working/
mv tmp/ _archive_2025/tmp/
mv checkpoints/ _archive_2025/checkpoints/
mv ace/ _archive_2025/ace/
mv foundry/ _archive_2025/foundry/
mv active-projects/ _archive_2025/active-projects/
```

### 1.2 Clean extension build artifacts
```bash
rm -rf extensions/*/node_modules/
rm -rf extensions/*/.next/
```

### 1.3 Extensions directory - KEEP
Keep `extensions/` - contains valuable assets:
- `workday/*.txt` - Training transcripts (38 files, few KB)
- `roblox/` - Roblox patterns and scripts
- `workday-transcripts/` - Additional transcripts

### 1.4 Verify MCP server still works
```bash
python -c "from tools.mcp_server import mcp; print('MCP server imports OK')"
```

### 1.5 Update .gitignore
```
_archive_2025/
```

---

## Phase 2: Windows Compatibility (AUDIT FINDING #1, #3)

### 2.1 Path Handling Audit
Files using subprocess that need Windows checks:
1. `tools/mcp_utils/delegation.py` - claude CLI invocation
2. `tools/mcp_utils/autonomous_build.py` - build subprocess
3. `tools/mcp_utils/phase_execution.py` - phase subprocess
4. `tools/cli.py` - CLI subprocess calls
5. `context_foundry/daemon/runner.py` - job execution

### 2.2 psutil Abstraction (AUDIT FINDING #3)
Files using psutil that need Windows-safe wrappers:
1. `tools/mcp_utils/delegation.py` - process management
2. `context_foundry/daemon/zombies.py` - zombie process cleanup
3. `context_foundry/daemon/runner.py` - job process control

Create `tools/mcp_utils/platform_utils.py`:
```python
import platform
import psutil

def kill_process_tree(pid: int, timeout: int = 5):
    """Cross-platform process tree termination."""
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)

        # On Windows, use terminate() first
        for child in children:
            child.terminate()
        parent.terminate()

        # Wait for graceful shutdown
        gone, alive = psutil.wait_procs(children + [parent], timeout=timeout)

        # Force kill remaining
        for p in alive:
            p.kill()
    except psutil.NoSuchProcess:
        pass

def get_shell_command():
    """Get appropriate shell for current platform."""
    if platform.system() == "Windows":
        return ["cmd", "/c"]
    return ["/bin/bash", "-c"]
```

### 2.3 Required Changes

1. **Detect OS and use appropriate shell:**
```python
import platform
def get_shell():
    if platform.system() == "Windows":
        return ["cmd", "/c"]
    return ["/bin/bash", "-c"]
```

2. **Check claude CLI availability:**
```python
import shutil
claude_path = shutil.which("claude")
if not claude_path:
    raise RuntimeError("Claude CLI not found in PATH")
```

3. **Use pathlib everywhere:**
```python
# Bad
path = f"{home}/.context-foundry/patterns"

# Good
path = Path.home() / ".context-foundry" / "patterns"
```

4. **Handle line endings:**
- Use `newline=""` in file operations
- Use `splitlines()` instead of `split("\n")`

### 2.4 Gate: CI must pass on Windows
Do NOT proceed to Phase 3 until Windows CI is green.

---

## Phase 3: Daemon Simplification (AUDIT FINDING #4)

**Decision: Option B - Slim Daemon** (balanced approach)

Rationale:
- Option A (keep as-is): Too complex, 18k lines
- Option C (simple runner): Too drastic, loses valuable features
- Option B (slim): Removes TUI, keeps HTTP API for web UI

### 3.1 Remove TUI Dashboard
Delete or archive `context_foundry/daemon/dashboard.py` (4.5k lines)
- Web UI at :8420 replaces TUI functionality
- Keep HTTP API for programmatic access

### 3.2 Simplify CLI
Reduce `context_foundry/daemon/cli.py` to essential commands:
- `cfd start` - Start daemon
- `cfd stop` - Stop daemon
- `cfd status` - Show status
- `cfd submit` - Submit job
- `cfd logs` - View logs
- `cfd list` - List jobs

Remove rarely-used commands to cut ~1.5k lines.

### 3.3 Keep HTTP API
`context_foundry/daemon/http_api.py` stays - web UI needs it.

### 3.4 Expected reduction
- Before: 18.5k lines
- After: ~10k lines

---

## Phase 4: Consolidate MCP Utils (AFTER Phase 3)

**Note:** This phase depends on Phase 3 daemon decision being complete.

### 4.1 Keep (Essential):
- `delegation.py` - Task delegation to Claude
- `autonomous_build.py` - Main build orchestration
- `pattern_management.py` - Pattern learning/storage
- `phase_execution.py` - Phase execution
- `project_detection.py` - Detect existing codebases

### 4.2 Merge or Remove:
- `approval_gates.py` → Merge into autonomous_build
- `contracts.py` → Merge into phase_execution
- `audit.py` → Remove (optional logging)
- `artifact_manifest.py` → Simplify
- `conversation_logger.py` → Remove (optional)
- `scope_guard.py` → Merge into autonomous_build

### 4.3 Delete optional tools
```bash
mv tools/baml_* _archive_2025/tools/
mv tools/baml_src/ _archive_2025/tools/
mv tools/baml_schemas/ _archive_2025/tools/
mv tools/baml_client/ _archive_2025/tools/
mv tools/livestream/ _archive_2025/tools/
mv tools/incremental/ _archive_2025/tools/
mv tools/back_pressure/ _archive_2025/tools/
mv tools/metrics/ _archive_2025/tools/
mv tools/log_monitor/ _archive_2025/tools/
mv tools/context_budget/ _archive_2025/tools/
mv tools/cache/ _archive_2025/tools/
mv tools/security/ _archive_2025/tools/
mv tools/screenshot_* _archive_2025/tools/
mv tools/generators/ _archive_2025/tools/
```

---

## Implementation Order (AUDIT GAP #3 - Documentation)

### Week 1: Phase 0 + Phase 1
- [ ] Create backup tag
- [ ] Update CI for Windows
- [ ] Run baseline Windows tests
- [ ] Move directories to `_archive_2025/`
- [ ] Verify MCP server works
- [ ] Update documentation (README, QUICKSTART)

### Week 2: Phase 2
- [ ] Create platform_utils.py
- [ ] Fix psutil usage
- [ ] Fix subprocess calls
- [ ] Run full test suite on Windows
- [ ] **Gate: Windows CI green**

### Week 3: Phase 3
- [ ] Remove TUI dashboard
- [ ] Simplify CLI
- [ ] Test web UI still works
- [ ] Update daemon documentation

### Week 4: Phase 4
- [ ] Merge mcp_utils modules
- [ ] Archive optional tools
- [ ] Final cross-platform testing
- [ ] Bump version to v3.0.0

---

## Expected Results

| Metric | Before | After Phase 1 | After All |
|--------|--------|---------------|-----------|
| Python lines | 115k | ~50k | ~35k |
| Disk size | ~2GB | ~200MB | ~150MB |
| Files | 500+ | ~100 | ~80 |
| Windows compat | Partial | Tested | Full |

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Breaking MCP tools | Test each tool before/after; backup tag |
| Breaking daemon | Keep daemon changes in Phase 3 separate |
| Missing dependencies | `_archive_2025/` allows recovery for 30 days |
| Windows edge cases | Windows CI gate before Phase 3 |
| Lost user data | Move to archive, not delete |

---

## Version Bump (AUDIT GAP #2)

After refactor complete:
```bash
# Update __version__.py
echo '__version__ = "3.0.0"' > context_foundry/__init__.py

# Tag release
git tag -a v3.0.0 -m "Cross-platform refactor: simplified, Windows-compatible"
git push origin v3.0.0
```

---

## Notes

- The web UI at :8420 is served by the Tauri desktop app on Mac
- On Windows/Linux, we'll need to either:
  - Create a similar Electron/Tauri app
  - Run the Vite dev server directly (development mode)
  - Build and serve static files from daemon HTTP server

- The daemon's HTTP API at :8421 is platform-agnostic
- The claude CLI must be installed and in PATH on all platforms
