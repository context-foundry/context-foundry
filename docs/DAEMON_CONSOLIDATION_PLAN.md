# Daemon Consolidation Plan

## Status: ✅ COMPLETE (2024-12-06)
## Branch: feature/vite-dashboard

---

## Executive Summary

The Evolution Daemon (`tools/evolution/`) is **85% dead code**. The audit shows:
- Most modes are imported but never executed
- Process Watchdog is instantiated but methods never called
- Mission Control TUI has no working backend
- CF Daemon already provides better equivalents for most features

**Recommendation:** Delete the dead code, keep only Scout Agent and Backlog Generator.

---

## Audit Findings

### Files by Status

| Status | Files | Lines | Action |
|--------|-------|-------|--------|
| **DEAD CODE** | mission_control.py, cloud_runner.py, communication/*, modes/* | ~8K+ | DELETE |
| **NEVER CALLED** | process_watchdog.py, resource_manager.py | ~420 | DELETE |
| **KEEP** | scout_agent.py, backlog_generator.py, safety.py | ~2.9K | PRESERVE |
| **REVIEW** | task_queue.py, daemon.py | ~2.6K | EVALUATE |

### What CF Daemon Already Has

| Evolution Feature | CF Daemon Equivalent |
|------------------|---------------------|
| Mission Control TUI | `context_foundry/daemon/dashboard.py` (165K) |
| Process Watchdog | `context_foundry/daemon/runner.py` (timeout handling) |
| Cloud Runner | `context_foundry/daemon/runner.py` (job execution) |
| Communication | `context_foundry/daemon/http_api.py` (REST API) |
| Task Queue | `context_foundry/daemon/store.py` (SQLite jobs) |

### What's Unique to Evolution (KEEP)

1. **Scout Agent** (`agents/scout_agent.py` - 2,326 lines)
   - Codebase analysis with 15+ scanners
   - Project type detection (Flowise, Roblox, Python, Node)
   - Priority scoring system
   - **Use case:** Autonomous issue detection

2. **Backlog Generator** (`backlog_generator.py` - 302 lines)
   - Creates GitHub issues from Scout findings
   - Context-foundry issue template
   - Maintains 5-issue backlog
   - **Use case:** Autonomous backlog management

3. **Safety Module** (`safety.py` - 240 lines)
   - Sandbox enforcement for autonomous builds
   - **Use case:** Security for auto-execution

---

## Deletion Plan

### Phase 1: Delete Obvious Dead Code

```bash
# Files with zero imports / never called
rm tools/evolution/mission_control.py      # 2,068 lines - TUI never used
rm tools/evolution/cloud_runner.py         # 160 lines - dead
rm tools/evolution/process_watchdog.py     # 323 lines - instantiated, never called
rm tools/evolution/resource_manager.py     # 96 lines - never called
rm tools/evolution/verify_cloud_setup.py   # 90 lines - CLI only
rm tools/evolution/cli_agents.py           # 85 lines - unused
rm tools/evolution/agent_protocol.py       # 112 lines - unused

# Communication module (replaced by CF Daemon HTTP API)
rm -rf tools/evolution/communication/

# Modes (imported but never executed)
rm -rf tools/evolution/modes/

# Framework (mostly unused, keep only what scout needs)
rm tools/evolution/framework/provider_config.py
rm tools/evolution/framework/agent_registry.py
```

**Total cleanup:** ~6,000+ lines

### Phase 2: Remove Evolution MCP Tools

From `tools/mcp_server.py`, remove these tool registrations:
- `start_evolution_daemon`
- `stop_evolution_daemon`
- `get_daemon_status` (evolution version)
- `create_evolution_task`
- `get_evolution_tasks`
- `register_project`
- `apply_pattern_to_project`
- `validate_project_health`
- `register_agent`
- `send_agent_message`

Delete `tools/evolution_mcp_tools.py` entirely.

### Phase 3: Evaluate Remaining Files

**Keep as standalone utilities:**
- `scout_agent.py` - Move to `context_foundry/agents/scout.py`
- `backlog_generator.py` - Move to `context_foundry/github/backlog.py`
- `safety.py` - Move to `context_foundry/safety.py`

**Delete after extraction:**
- `daemon.py` - Core loop logic, but CF Daemon handles this better
- `task_queue.py` - SQLite queue, but CF Daemon's store.py is equivalent

### Phase 4: Clean Up Imports

After deletion, fix any broken imports in:
- `tools/mcp_server.py`
- `context_foundry/daemon/runner.py`
- Any files that imported evolution modules

---

## MCP Tool Consolidation

### Before (Two Systems)

```
CF Daemon Tools:
- autonomous_build_and_deploy
- delegate_to_claude_code
- get_delegation_result
- ...

Evolution Tools:
- start_evolution_daemon
- stop_evolution_daemon
- create_evolution_task
- get_evolution_tasks
- ...
```

### After (Single System)

```
CF Daemon Tools:
- autonomous_build_and_deploy (already exists)
- delegate_to_claude_code (already exists)
- get_delegation_result (already exists)
- scan_codebase (new - wraps Scout Agent)
- generate_backlog (new - wraps Backlog Generator)
```

---

## Timeline

| Phase | Description | Effort |
|-------|-------------|--------|
| 1 | Delete dead code files | 30 min |
| 2 | Remove MCP tools | 30 min |
| 3 | Move Scout/Backlog to new locations | 1 hour |
| 4 | Fix imports and test | 30 min |

**Total:** ~2.5 hours

---

## Files to Delete (Summary)

```
tools/evolution/
├── mission_control.py          # DELETE - 2,068 lines
├── cloud_runner.py             # DELETE - 160 lines
├── process_watchdog.py         # DELETE - 323 lines
├── resource_manager.py         # DELETE - 96 lines
├── verify_cloud_setup.py       # DELETE - 90 lines
├── cli_agents.py               # DELETE - 85 lines
├── agent_protocol.py           # DELETE - 112 lines
├── command_server.py           # DELETE - 538 lines
├── mcp_wrapper.py              # DELETE - 337 lines (if unused)
├── run_pipeline.py             # DELETE - 118 lines
├── mcp_support.py              # DELETE - 53 lines
├── cf.py                       # DELETE - 41 lines
├── daemon.py                   # DELETE - 1,922 lines (after extraction)
├── task_queue.py               # DELETE - 665 lines (after extraction)
├── communication/              # DELETE - entire directory
├── modes/                      # DELETE - entire directory
├── framework/                  # DELETE - most files
├── autonomous/                 # DELETE - entire directory
└── cf.html                     # DELETE - 291K (dead)

tools/evolution_mcp_tools.py    # DELETE - 280 lines
```

**Files to KEEP and relocate:**
```
tools/evolution/
├── agents/scout_agent.py       # MOVE → context_foundry/agents/scout.py
├── backlog_generator.py        # MOVE → context_foundry/github/backlog.py
├── safety.py                   # MOVE → context_foundry/safety.py
└── sandboxes.py                # KEEP if used by safety.py
```

---

## Verification Checklist

After cleanup:
- [ ] `cfd start` still works
- [ ] `autonomous_build_and_deploy` MCP tool works
- [ ] No import errors when starting MCP server
- [ ] Dashboard at :8420 loads correctly
- [ ] No references to deleted files in remaining code
