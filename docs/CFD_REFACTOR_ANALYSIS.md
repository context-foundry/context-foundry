# Context Foundry Daemon (cfd) - Refactoring Analysis

**Date**: 2025-11-13
**Status**: Planning Phase
**Goal**: Transform `tools/evolution/daemon.py` into a first-class Context Foundry Daemon

---

## 1. Current State Analysis

### Existing Daemon: `tools/evolution/daemon.py`

**Lines of Code**: 1,923 lines (monolithic)
**Purpose**: Orchestrate "Evolution System" - self-improvement loop for Context Foundry

**Core Responsibilities**:
1. ✅ **Task Queue Management** - SQLite-based persistent queue
2. ✅ **Process Monitoring** - Watchdog for stuck/timeout processes
3. ✅ **GitHub Integration** - Poll issues, create PRs, close issues
4. ✅ **PR-Based Workflow** - Wait for PRs to merge before next task
5. ✅ **Resource Management** - CPU, memory, disk monitoring
6. ✅ **Delegation Monitoring** - Track MCP delegations
7. ✅ **Backlog Generation** - Scout-based issue creation
8. ✅ **Sandbox Management** - Clean up orphaned sandboxes

**Architecture**:
```
tools/evolution/
├── daemon.py              (1922 lines - monolithic orchestrator)
├── task_queue.py          (664 lines - SQLite queue)
├── resource_manager.py    (Resource monitoring)
├── process_watchdog.py    (Process monitoring)
├── backlog_generator.py   (GitHub issue creation)
├── sandboxes.py           (Sandbox lifecycle)
├── mission_control.py     (2035 lines - command center)
├── modes/                 (Execution modes)
│   ├── self_improvement.py
│   ├── chaos_creative.py
│   ├── research_discovery.py
│   └── delegation.py
└── agents/
    └── scout_agent.py
```

**Dependencies**:
- SQLite (task queue persistence)
- GitHub API (issue/PR integration)
- psutil (resource monitoring)
- requests (HTTP client)
- subprocess (process spawning)

**Current Issues**:
- ❌ **Evolution-specific** - Tightly coupled to "self-improvement" workflow
- ❌ **Monolithic** - daemon.py is 1922 lines, hard to maintain
- ❌ **Poor modularity** - Mixed concerns (PR detection, resource monitoring, task execution)
- ❌ **Not first-class** - Located in `tools/evolution/` (feels like a side project)
- ❌ **Limited scope** - Only handles evolution tasks, not general CF jobs
- ❌ **No HTTP API** - Only CLI/internal Python API

---

## 2. Design: Context Foundry Daemon (cfd)

### Vision

Transform the daemon from an "evolution engine" into the **main orchestration service** for Context Foundry:

```
Context Foundry Daemon (cfd)
├── Accepts job requests (CLI, HTTP, MCP, CI/CD)
├── Manages job lifecycle (queued → running → succeeded/failed)
├── Launches CF orchestrator runs (Scout → Architect → Build → Test)
├── Captures phase transitions, logs, events
├── Streams job status in real-time
├── Supports multiple job types:
│   ├── New project builds
│   ├── Enhancement tasks (evolution-style)
│   ├── Testing/validation runs
│   ├── Pattern applications
│   └── Custom workflows
└── Exposes clean APIs:
    ├── Python API (programmatic)
    ├── CLI (cfd start/submit/status)
    └── HTTP API (future - /v1/jobs)
```

### Module Structure

```
context_foundry/
└── daemon/
    ├── __init__.py           # Public API exports
    ├── server.py             # Main daemon server (replaces daemon.py)
    ├── config.py             # Configuration management
    ├── models.py             # Domain models (Job, JobStatus, PhaseEvent, LogEntry)
    ├── store.py              # Persistence layer (SQLite)
    ├── jobs.py               # Job manager / queue / worker loop
    ├── runner.py             # CF orchestrator integration
    ├── monitors/             # Monitoring subsystems
    │   ├── __init__.py
    │   ├── resource.py       # CPU/memory monitoring (from resource_manager.py)
    │   ├── process.py        # Process watchdog (from process_watchdog.py)
    │   └── github.py         # GitHub integration (from daemon.py PR methods)
    └── cli.py                # CLI entrypoints (cfd command)

tools/
└── cfd                       # Executable CLI entry point
```

---

## 3. Domain Models (models.py)

### Core Entities

```python
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List

class JobStatus(str, Enum):
    """Job lifecycle states"""
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"

class JobType(str, Enum):
    """Types of jobs CF Daemon can run"""
    NEW_PROJECT = "new_project"            # Build new project from scratch
    ENHANCEMENT = "enhancement"            # Evolution-style improvement
    TESTING = "testing"                    # Run tests only
    PATTERN_APPLICATION = "pattern_application"  # Apply learned patterns
    VALIDATION = "validation"              # Validate existing code
    DELEGATION = "delegation"              # Monitor external delegation

@dataclass
class Job:
    """A CF Daemon job"""
    id: str                                # UUID
    type: JobType
    status: JobStatus
    priority: int                          # 1-10
    params: Dict[str, Any]                # Job-specific parameters
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3

@dataclass
class PhaseEvent:
    """Phase transition event"""
    job_id: str
    phase: str                            # Scout, Architect, Builder, Test, etc.
    status: str                           # started, completed, failed
    timestamp: datetime
    details: Optional[Dict[str, Any]] = None

@dataclass
class LogEntry:
    """Structured log entry"""
    job_id: str
    timestamp: datetime
    level: str                            # INFO, WARNING, ERROR
    message: str
    metadata: Optional[Dict[str, Any]] = None
```

---

## 4. Job Manager (jobs.py)

### Responsibilities

```python
class JobManager:
    """Central job management"""

    def __init__(self, store: Store, config: Config):
        self.store = store
        self.config = config
        self.active_jobs: Dict[str, Job] = {}

    def submit_job(self, job_type: JobType, params: Dict) -> str:
        """Submit new job, returns job_id"""
        pass

    def get_job(self, job_id: str) -> Optional[Job]:
        """Get job by ID"""
        pass

    def list_jobs(self, status: Optional[JobStatus] = None) -> List[Job]:
        """List jobs, optionally filtered by status"""
        pass

    def cancel_job(self, job_id: str) -> bool:
        """Cancel running job"""
        pass

    def worker_loop(self):
        """Main worker loop - picks queued jobs and executes them"""
        pass
```

---

## 5. Runner Integration (runner.py)

### Orchestrator Hook

```python
class Runner:
    """Executes CF orchestrator runs"""

    def __init__(self, job_manager: JobManager):
        self.job_manager = job_manager

    def run_job(self, job: Job) -> Dict[str, Any]:
        """
        Execute job by calling appropriate CF orchestrator

        Integrates with:
        - tools/mcp_utils/autonomous_build.py (for new_project)
        - tools/mcp_utils/phase_execution.py (for individual phases)
        - Evolution modes (for enhancement tasks)
        """
        pass

    def emit_phase_event(self, job_id: str, phase: str, status: str):
        """Emit phase transition event"""
        pass

    def emit_log(self, job_id: str, level: str, message: str):
        """Emit log entry"""
        pass
```

---

## 6. CLI Interface (cli.py)

### Commands

```bash
# Start daemon
cfd start [--foreground] [--config CONFIG]

# Stop daemon
cfd stop

# Check status
cfd status [--verbose]

# Submit job
cfd submit --type new_project --task "Build weather app" --dir /path/to/project
cfd submit --type enhancement --github-issue 123
cfd submit --type testing --project todo-cli-v3

# Query jobs
cfd list [--status queued|running|succeeded|failed]
cfd show JOB_ID

# Logs
cfd logs JOB_ID [--follow] [--lines 100]

# Cancel job
cfd cancel JOB_ID
```

---

## 7. Migration Strategy

### Phase 1: Create New Module (No Breaking Changes)
1. Create `context_foundry/daemon/` with clean architecture
2. Implement core models, store, job manager
3. Keep `tools/evolution/daemon.py` working as-is
4. New daemon runs independently

### Phase 2: Parallel Operation
1. Both daemons can run simultaneously
2. Evolution daemon optionally delegates to new cfd
3. Gradual migration of evolution tasks to cfd

### Phase 3: Deprecation
1. Evolution daemon becomes thin wrapper around cfd
2. All new features go into cfd
3. Evolution daemon marked deprecated

### Phase 4: Removal (Optional)
1. Remove `tools/evolution/daemon.py`
2. Evolution system fully integrated into cfd

---

## 8. Implementation Plan

### Step 1: Core Infrastructure ✅ IN PROGRESS
- [ ] Create `context_foundry/daemon/` module
- [ ] Implement `models.py` (Job, JobStatus, PhaseEvent, LogEntry)
- [ ] Implement `store.py` (SQLite persistence)
- [ ] Implement `config.py` (Configuration management)

### Step 2: Job Management
- [ ] Implement `jobs.py` (JobManager with worker loop)
- [ ] Port task queue logic from `task_queue.py`
- [ ] Add job submission, cancellation, listing

### Step 3: Orchestrator Integration
- [ ] Implement `runner.py`
- [ ] Integrate with `tools/mcp_utils/autonomous_build.py`
- [ ] Hook phase tracking (Scout → Architect → Builder → Test)
- [ ] Capture logs and phase events

### Step 4: Monitoring Subsystems
- [ ] Port `resource_manager.py` → `monitors/resource.py`
- [ ] Port `process_watchdog.py` → `monitors/process.py`
- [ ] Extract GitHub logic → `monitors/github.py`

### Step 5: Server & CLI
- [ ] Implement `server.py` (main daemon loop)
- [ ] Implement `cli.py` (argparse-based CLI)
- [ ] Create `tools/cfd` executable

### Step 6: Testing
- [ ] Unit tests for models, store, jobs
- [ ] Integration test: submit job → execute → complete
- [ ] Mock orchestrator for isolated testing

### Step 7: Documentation
- [ ] Write `docs/context-foundry-daemon.md`
- [ ] API reference
- [ ] Migration guide from evolution daemon

---

## 9. Success Criteria

### Functional Requirements
- ✅ Accept job submissions via CLI
- ✅ Persist jobs in SQLite
- ✅ Execute jobs via CF orchestrator
- ✅ Track phase transitions (Scout → Architect → Builder → Test)
- ✅ Capture and query logs per job
- ✅ Support graceful shutdown
- ✅ Recover from crashes (orphaned jobs, stuck processes)

### Non-Functional Requirements
- ✅ Clean separation of concerns (models, store, jobs, runner)
- ✅ Type hints everywhere
- ✅ Comprehensive test coverage (>80%)
- ✅ Documentation (architecture, API, migration)
- ✅ Backward compatibility (evolution system still works)

### Future-Friendly
- 🔮 HTTP API ready (POST /v1/jobs, GET /v1/jobs/:id)
- 🔮 WebSocket streaming (real-time logs)
- 🔮 MCP server integration
- 🔮 Multi-tenant support
- 🔮 Distributed workers

---

## 10. Open Questions

1. **Database Schema**: Reuse evolution's SQLite or start fresh?
   - **Decision**: Start fresh, migrate old tasks if needed

2. **Evolution Compatibility**: Keep evolution daemon or deprecate immediately?
   - **Decision**: Keep working in parallel, gradual migration

3. **Process Model**: Single process or multi-worker?
   - **Decision**: Start single-process, design for multi-worker future

4. **HTTP API**: Implement now or defer?
   - **Decision**: Defer - CLI + Python API first, HTTP later

5. **GitHub Integration**: Keep tight coupling or make optional?
   - **Decision**: Make optional - cfd is generic, GitHub is a monitor plugin

---

## 11. Timeline Estimate

- **Step 1-3** (Core + Job Management + Runner): 4-6 hours
- **Step 4** (Monitoring): 2-3 hours
- **Step 5** (Server + CLI): 2-3 hours
- **Step 6** (Testing): 3-4 hours
- **Step 7** (Documentation): 1-2 hours

**Total**: 12-18 hours of focused development

---

## 12. Next Actions

1. ✅ Create this analysis document
2. ⏭️ Create `context_foundry/daemon/` module structure
3. ⏭️ Implement core models (Job, JobStatus, PhaseEvent)
4. ⏭️ Implement SQLite store
5. ⏭️ Implement job manager with worker loop
6. ⏭️ Integrate CF orchestrator runner
7. ⏭️ Build CLI interface
8. ⏭️ Write tests
9. ⏭️ Document architecture

---

**Status**: Ready to proceed with implementation ✅
