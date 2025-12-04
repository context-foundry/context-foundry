# Future Enhancements

## Modernize Web Dashboard

**Priority:** Low
**Status:** Proposed
**Current:** `tools/evolution/cf.html` (7,353-line vanilla JS monolith)

### Problem

The current web dashboard at `http://localhost:8420/` is a single HTML file with inline CSS and JavaScript. While functional, this approach has limitations:

- No hot module replacement during development
- No component reusability
- No TypeScript type safety
- Difficult to maintain at 7K+ lines
- No build-time optimizations

### Proposed Solution

Migrate to a modern Vite-based frontend:

```
tools/dashboard/
├── src/
│   ├── components/
│   │   ├── JobList.tsx
│   │   ├── JobDetail.tsx
│   │   ├── PhasePipeline.tsx
│   │   ├── ActivityPanel.tsx
│   │   └── SidekickChat.tsx
│   ├── hooks/
│   │   ├── useSSE.ts
│   │   └── useJobs.ts
│   ├── App.tsx
│   └── main.tsx
├── package.json
├── vite.config.ts
└── tsconfig.json
```

### Benefits

- **Developer Experience:** Hot reload, TypeScript, component isolation
- **Maintainability:** Smaller, focused files instead of one 7K-line file
- **Type Safety:** Catch errors at build time
- **Performance:** Tree shaking, code splitting, minification
- **Testing:** Component-level unit tests

### Migration Path

1. Keep existing `cf.html` as fallback
2. Build new Vite app that consumes same API endpoints
3. Serve built assets from daemon or run separately in dev
4. Deprecate `cf.html` once feature parity achieved

### Backend Changes Required

None - the existing HTTP API and SSE endpoints remain unchanged:
- `GET /jobs` - List jobs
- `GET /jobs/{id}` - Job details
- `GET /jobs/{id}/tree` - Phase tree
- `GET /sse` - Real-time updates
- `GET /agent-activity` - Activity stream

### References

- Current dashboard: `tools/evolution/cf.html`
- HTTP API: `context_foundry/daemon/http_api.py`
- SSE endpoints: `context_foundry/daemon/server.py`

---

## Consolidate Evolution Daemon into CF Daemon

**Priority:** Medium
**Status:** Proposed
**Blocked by:** None

### Problem

Context Foundry has **two separate daemon systems** with overlapping responsibilities:

| | **CF Daemon** | **Evolution Daemon** |
|---|--------------|---------------------|
| **Location** | `context_foundry/daemon/` | `tools/evolution/daemon.py` |
| **CLI** | `cfd` | None (MCP tools only) |
| **Class** | `CFDaemon` | `EvolutionDaemon` |
| **Port** | 8420 | None |
| **Purpose** | Build orchestration | Self-improvement, chaos/creative, research |
| **Task System** | Jobs + Tasks + Gates | TaskQueueManager + TaskTypes |
| **Dashboard** | `cf.html` web UI | None |

This creates confusion:
- Two task queue implementations
- Two sets of execution modes
- MCP tools reference both (`start_evolution_daemon` vs `autonomous_build_and_deploy`)
- Unclear which daemon to use for what

### Proposed Solution

Consolidate into a single `CFDaemon` with pluggable execution modes:

```
context_foundry/daemon/
├── server.py          # CFDaemon (already exists)
├── modes/
│   ├── __init__.py
│   ├── build.py       # Scout→Architect→Builder→Test→Feedback (current)
│   ├── self_improve.py # Migrate from evolution daemon
│   ├── chaos.py       # Migrate from evolution daemon
│   └── research.py    # Migrate from evolution daemon
├── store.py           # SQLite persistence (already exists)
└── ...
```

### Migration Steps

1. **Audit Evolution Daemon features**
   - `SelfImprovementMode` - auto-fix patterns, refactoring
   - `ChaosCreativeMode` - experimental feature generation
   - `ResearchDiscoveryMode` - codebase analysis
   - `DelegationMode` - task distribution
   - `BacklogGenerator` - automatic task creation
   - `ProcessWatchdog` - timeout/token limits

2. **Move reusable components to CF Daemon**
   - `ResourceManager` → integrate with existing metrics
   - `ProcessWatchdog` → enhance existing runner timeout handling
   - `BacklogGenerator` → new feature for CF Daemon

3. **Deprecate Evolution Daemon MCP tools**
   - Remove `start_evolution_daemon` / `stop_evolution_daemon`
   - Add mode selection to `autonomous_build_and_deploy`

4. **Update documentation**
   - Single daemon, multiple modes
   - Clear CLI: `cfd start --mode build|evolve|research`

### Files to Migrate

From `tools/evolution/`:
```
daemon.py              → Deprecate (functionality absorbed)
task_queue.py          → Keep CF Daemon's store.py
resource_manager.py    → Merge into daemon/metrics.py
process_watchdog.py    → Merge into daemon/runner.py
backlog_generator.py   → New feature in daemon/
modes/                 → Move to daemon/modes/
```

### Files to Delete After Migration

```
tools/evolution/daemon.py
tools/evolution/task_queue.py
tools/evolution/resource_manager.py
tools/evolution/process_watchdog.py
tools/evolution_mcp_tools.py (partially)
```

### Benefits

- **Single source of truth** for daemon operations
- **One CLI** (`cfd`) for all daemon management
- **Unified task queue** with SQLite persistence
- **Shared web dashboard** for all modes
- **Clearer MCP interface** - fewer confusing tool names

### References

- CF Daemon: `context_foundry/daemon/`
- Evolution Daemon: `tools/evolution/daemon.py`
- MCP tools: `tools/mcp_server.py`, `tools/evolution_mcp_tools.py`
- Implementation status: `context_foundry/daemon/IMPLEMENTATION_STATUS.md`
