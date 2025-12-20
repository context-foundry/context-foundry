# Context Foundry Refactoring Plan

**Goal:** Simplify codebase, ensure Windows compatibility, reduce from ~115k to ~40k lines

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

## Phase 1: Remove Noise (Immediate, Low Risk)

### Delete directories
```bash
rm -rf archive/           # 788MB - old archived code
rm -rf examples/          # 324MB - example projects
rm -rf logs/              # 5.3MB - old logs
rm -rf htmlcov/           # 8.6MB - coverage reports
rm -rf builds/            # Working directory
rm -rf flowise-builds/    # Working directory
rm -rf projects/          # Working directory
rm -rf sandbox/           # Working directory
rm -rf working/           # Working directory
rm -rf tmp/               # Working directory
rm -rf checkpoints/       # Session checkpoints
rm -rf ace/               # Unknown/unused
rm -rf foundry/           # Old patterns dir
rm -rf active-projects/   # Working directory
```

### Add to .gitignore
```
# Already there: extensions/flowise/
examples/
archive/
logs/
builds/
projects/
sandbox/
working/
tmp/
*.db
*.log
```

### Delete optional tools (move to separate packages later)
```bash
rm -rf tools/baml_*           # BAML integration (optional)
rm -rf tools/baml_src/        # BAML schemas
rm -rf tools/baml_schemas/    # BAML schemas
rm -rf tools/baml_client/     # BAML client
rm -rf tools/livestream/      # Multi-agent streaming
rm -rf tools/incremental/     # Incremental builds
rm -rf tools/back_pressure/   # Validation checks
rm -rf tools/metrics/         # Telemetry collection
rm -rf tools/log_monitor/     # Log monitoring
rm -rf tools/context_budget/  # Context budget
rm -rf tools/cache/           # Scout/test caching
rm -rf tools/security/        # Sandbox enforcement
rm -rf tools/screenshot_*     # Screenshot helpers
rm -rf tools/generators/      # Code generators
```

---

## Phase 2: Windows Compatibility

### Path Handling Audit
Files using subprocess that need Windows checks:
1. `tools/mcp_utils/delegation.py` - claude CLI invocation
2. `tools/mcp_utils/autonomous_build.py` - build subprocess
3. `tools/mcp_utils/phase_execution.py` - phase subprocess
4. `tools/cli.py` - CLI subprocess calls
5. `context_foundry/daemon/runner.py` - job execution

### Required Changes

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

---

## Phase 3: Simplify Daemon (Optional, Higher Risk)

Current daemon is feature-rich but complex:
- `dashboard.py` (4.5k lines) - TUI dashboard (not needed if using web UI)
- `cli.py` (3.2k lines) - Full CLI with many subcommands
- `http_api.py` (1.9k lines) - REST API
- `store.py` (1.5k lines) - SQLite job storage

### Option A: Keep as-is
- Pros: Full featured, battle tested
- Cons: Complex, 18k lines

### Option B: Slim daemon
- Remove TUI dashboard (use web UI only)
- Simplify CLI to essential commands
- Keep HTTP API for web UI
- Estimated: ~8k lines

### Option C: Replace with simple job runner
- File-based job queue (JSON files)
- Minimal HTTP API for status
- No TUI, web UI only
- Estimated: ~2k lines

---

## Phase 4: Consolidate MCP Utils

Current mcp_utils has many interconnected modules. Consider:

### Keep (Essential):
- `delegation.py` - Task delegation to Claude
- `autonomous_build.py` - Main build orchestration
- `pattern_management.py` - Pattern learning/storage
- `phase_execution.py` - Phase execution
- `project_detection.py` - Detect existing codebases

### Merge or Remove:
- `approval_gates.py` → Merge into autonomous_build
- `contracts.py` → Merge into phase_execution
- `audit.py` → Remove (optional logging)
- `artifact_manifest.py` → Simplify
- `conversation_logger.py` → Remove (optional)
- `filesystem_tools.py` → Keep but simplify
- `scope_guard.py` → Merge into autonomous_build

---

## Implementation Order

1. **Week 1: Cleanup**
   - Remove archived/example directories
   - Remove optional tools
   - Update imports
   - Test MCP server still works

2. **Week 2: Windows Testing**
   - Set up Windows VM/machine
   - Run full test suite
   - Fix path issues as found
   - Test claude CLI integration

3. **Week 3: Daemon Simplification (if chosen)**
   - Decide on daemon approach
   - Implement changes
   - Test web UI still works

4. **Week 4: Polish**
   - Update documentation
   - Clean up unused imports
   - Final cross-platform testing

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

1. **Breaking MCP tools** - Test each tool individually before/after
2. **Breaking daemon** - Keep daemon changes optional
3. **Missing dependencies** - Audit all imports before removal
4. **Windows edge cases** - Extensive testing on Windows

---

## Notes

- The web UI at :8420 is served by the Tauri desktop app on Mac
- On Windows/Linux, we'll need to either:
  - Create a similar Electron/Tauri app
  - Run the Vite dev server directly (development mode)
  - Build and serve static files from daemon HTTP server

- The daemon's HTTP API at :8421 is platform-agnostic
- The claude CLI must be installed and in PATH on all platforms
