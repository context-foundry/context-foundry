# Scout Report: Context Foundry Evolution System (CFES)

## Executive Summary

The Context Foundry Evolution System (CFES) will transform Context Foundry from a task-based autonomous build tool into a continuously-evolving, self-improving system that runs perpetually. This represents a fundamental architectural enhancement adding daemon services, persistent task queuing, multi-agent coordination, and three distinct evolution modes.

**Project Type**: Enhancement to existing Python MCP server
**Scope**: Large multi-component system (~2500 lines of new code, 10 new MCP tools)
**Mode**: add_docs (actually add_feature - comprehensive new capability)

## Key Requirements Analysis

### 1. Evolution Daemon (Core Service)
**Purpose**: Continuously-running background service orchestrating evolution tasks

**Requirements**:
- Hybrid trigger system: 60-second polling + event-driven responses
- Resource-aware: respect CPU/memory limits, honor active hours
- Signal handling: SIGTERM (graceful shutdown), SIGHUP (reload config)
- Process control: systemd (Linux) / launchd (macOS) integration
- Health monitoring: HTTP endpoint for liveness checks
- Logging: rotating file handler (10MB max, 5 backups)

**Technical Approach**:
- Python `daemon` library OR custom daemonization with `fork()` + `setsid()`
- PID file at `~/.context-foundry/evolution/daemon.pid`
- Config reload without restart
- Graceful task completion on shutdown (no orphans)

### 2. Task Queue System (Persistent Storage)
**Purpose**: SQLite-based task queue with history and registries

**Schema Design**:
```sql
-- Main task queue
CREATE TABLE tasks (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,  -- 'self_improvement' | 'chaos_creative' | 'research' | 'apply_pattern' | 'validate'
    status TEXT NOT NULL,  -- 'pending' | 'running' | 'completed' | 'failed'
    priority INTEGER NOT NULL DEFAULT 5,  -- 1-10
    params_json TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    result_json TEXT,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3
);

-- Task history (completed/failed tasks)
CREATE TABLE task_history (
    -- Same schema as tasks
    -- Moved here after 30 days
);

-- Global project registry
CREATE TABLE project_registry (
    path TEXT PRIMARY KEY,
    project_type TEXT NOT NULL,
    metadata_json TEXT,
    last_updated TEXT NOT NULL,
    patterns_applied TEXT  -- JSON array
);

-- Agent network registry
CREATE TABLE agent_network (
    agent_id TEXT PRIMARY KEY,
    agent_name TEXT NOT NULL,
    agent_url TEXT,  -- NULL for local
    capabilities_json TEXT,  -- JSON array
    connection_weight REAL DEFAULT 1.0,
    last_seen TEXT NOT NULL
);
```

**Critical Features**:
- ACID transactions (SQLite WAL mode)
- Proper indexing: `(status, priority, created_at)`
- Task locking: `SELECT ... FOR UPDATE` equivalent
- Retry logic: exponential backoff (1s, 2s, 4s)
- Auto-archive: Move to history after 30 days

### 3. Evolution Modes (Plugin Architecture)

#### Base Interface
```python
class BaseEvolutionMode(ABC):
    @abstractmethod
    def generate_tasks(self) -> List[Task]:
        """Analyze environment and generate improvement tasks"""
    
    @abstractmethod
    def execute_task(self, task: Task) -> TaskResult:
        """Execute task using CF delegation"""
    
    @abstractmethod
    def validate_result(self, result: TaskResult) -> bool:
        """Validate task completion"""
```

#### Mode A: Self-Improvement
**Purpose**: Analyze CF codebase and generate improvement tasks

**Task Generation**:
- Run `coverage.py` to find untested code
- Run `ruff check` for linting issues
- Analyze pattern library for optimization opportunities
- Check for TODO/FIXME comments
- Monitor build times for performance bottlenecks

**Execution**:
- Create feature branch: `self-improvement/task-{id}`
- Delegate to existing CF build system
- Run tests to validate changes
- Create PR for human review (NEVER auto-merge)

**Safety**:
- CRITICAL: Changes to CF itself require human approval
- Create PR workflow, not direct commits
- Include rollback instructions
- Test on isolated branch first

#### Mode B: Chaos/Creative
**Purpose**: Generate random projects to explore possibilities

**Project Types** (weighted selection):
- Web apps (30%): React/Vue/Vanilla JS
- CLI tools (20%): Python/Go/Rust
- Games (15%): 2D canvas, terminal games
- Frameworks/Libraries (15%): Utilities, helpers
- Art projects (10%): Generative art, visualizations
- Experiments (10%): Novel ideas, research

**Learning Loop**:
1. Generate project idea (weighted random + LLM creativity)
2. Delegate to CF build system
3. Track: build time, test pass rate, patterns used
4. Update pattern library with learnings
5. Adjust weights based on success rate

**Pattern Contribution**:
- Successful patterns → Add to global library
- Failed patterns → Document anti-patterns
- Novel solutions → Share with community

#### Mode C: Research/Discovery
**Purpose**: Research assistant for long-running investigations

**Capabilities**:
- WebSearch integration for paper discovery
- API integrations: arXiv, PubMed, Semantic Scholar
- Multi-step research workflows
- Citation tracking and cross-referencing
- Hypothesis generation using LLM
- Experiment design suggestions

**Output Format**:
- Structured markdown reports
- Citation management (BibTeX)
- Hypothesis tracking
- Follow-up question generation

### 4. Communication Layer

#### Web Dashboard (FastAPI + WebSocket)
**Port**: 8765
**Framework**: FastAPI (modern, async, fast)
**Frontend**: Jinja2 templates + Tailwind CSS + HTMX

**Pages**:
- `/` - Dashboard overview (active tasks, queue, health)
- `/tasks` - Task list with filters
- `/projects` - Project registry
- `/agents` - Agent network graph
- `/patterns` - Pattern library viewer
- `/health` - System health metrics

**Real-time Updates**: WebSocket for live task status

#### REST API (OpenAPI)
**Port**: 8766
**Documentation**: Auto-generated at `/docs`

**Endpoints**:
```
POST   /tasks              Create new task
GET    /tasks              List tasks (with filters)
GET    /tasks/{id}         Get task status
DELETE /tasks/{id}         Cancel task
POST   /tasks/{id}/retry   Retry failed task
GET    /projects           List projects
POST   /projects           Register project
GET    /agents             List agents
POST   /agents/message     Send inter-agent message
GET    /health             System health
```

#### WebSocket Stream
**Port**: 8767
**Messages**:
- Task status changes (pending → running → completed)
- Build logs (streaming)
- Pattern updates (new patterns added)
- Agent connections/disconnections

### 5. Agent Protocol (Multi-Agent Network)

**Message Format**:
```json
{
  "from": "agent-name",
  "to": "target-agent",
  "type": "task_delegation" | "learning_share" | "health_check",
  "payload": {...},
  "timestamp": "2025-11-07T18:30:00Z"
}
```

**Discovery Mechanism**:
- Local: File-based (`~/.context-foundry/evolution/shared_tasks/`)
- Network: HTTP beacon (optional, disabled by default)
- Multicast UDP for LAN discovery (optional)

**Connection Weights**:
- Track success rate per agent connection
- Prefer agents with high success rates
- Decay weights over time (prevent stale connections)

**Trust Model**:
- v1: Whitelist mode (only known agents)
- Future: Reputation system, signed messages

### 6. New MCP Tools (Extension to mcp_server.py)

**Tools to Add**:
1. `create_evolution_task()` - Add task to queue
2. `get_evolution_tasks()` - List tasks with filters
3. `start_evolution_daemon()` - Start daemon service
4. `stop_evolution_daemon()` - Stop daemon gracefully
5. `get_daemon_status()` - Health and stats
6. `register_project()` - Add to project registry
7. `apply_pattern_to_project()` - Apply specific pattern
8. `validate_project_health()` - Run tests and validate
9. `register_agent()` - Add agent to network
10. `send_agent_message()` - Inter-agent messaging

**Integration**: Extend existing mcp_server.py without breaking changes

## Technology Stack Decisions

### Core Technologies
- **Python 3.11+**: Required for FastAPI, async/await patterns
- **SQLite**: Persistent storage (lightweight, no external DB)
- **FastAPI**: Web framework (modern, async, OpenAPI)
- **FastMCP**: Existing CF framework (extend it)

### Additional Dependencies
```
# Add to requirements.txt:
fastapi>=0.104.0
uvicorn>=0.24.0
websockets>=12.0
jinja2>=3.1.2
python-daemon>=3.0.0  # OR custom daemonization
psutil>=5.9.0  # Resource monitoring
```

### Frontend
- **Jinja2**: Server-side templates
- **Tailwind CSS**: Styling (CDN for v1)
- **HTMX**: Dynamic updates (optional, vanilla JS acceptable)
- **Chart.js**: Visualizations (task queue, agent network)

## Critical Architecture Recommendations

### 1. SQLite Concurrency Strategy
**Challenge**: Multiple processes accessing same DB

**Solution**:
- Enable WAL mode: `PRAGMA journal_mode=WAL`
- Connection pooling with timeout
- Retry logic for locked database
- Transaction isolation: `BEGIN IMMEDIATE`

### 2. Resource Management
**Challenge**: Daemon consuming all CPU/memory

**Solution**:
```python
import psutil

def check_resources():
    cpu = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory().percent
    
    if cpu > config.max_cpu_percent:
        return False  # Don't start new task
    if memory > config.max_memory_percent:
        return False
    return True
```

**Active Hours**: Only run during configured hours (default: 6am-10pm)

### 3. Graceful Daemon Shutdown
**Challenge**: Don't kill running builds

**Solution**:
```python
import signal

def handle_sigterm(signum, frame):
    logger.info("Received SIGTERM, graceful shutdown...")
    daemon.stop_accepting_new_tasks = True
    daemon.wait_for_active_tasks()  # Block until complete
    daemon.cleanup()
    sys.exit(0)

signal.signal(signal.SIGTERM, handle_sigterm)
```

### 4. Self-Improvement Safety
**Challenge**: CF modifying itself could break system

**Solution**:
- ALWAYS create feature branch
- NEVER auto-merge to main
- Create PR for human review
- Include rollback instructions
- Test on isolated branch first
- Validate tests pass before PR

### 5. Dashboard Security
**Challenge**: Exposed web interface

**Solution** (v1 - local only):
- Bind to 127.0.0.1 (localhost only)
- No external exposure
- CORS: Whitelist only
- Future: API key authentication

## Testing Strategy

### Unit Tests (80%+ coverage target)
**test_daemon.py**:
- Start/stop lifecycle
- Signal handling
- Task polling logic
- Resource limit enforcement

**test_task_queue.py**:
- CRUD operations
- Task locking
- Retry logic with backoff
- Archive mechanism

**test_modes.py**:
- Task generation for each mode
- Execution delegation
- Result validation

**test_communication.py**:
- API endpoint responses
- WebSocket messaging
- Dashboard rendering

**test_agent_protocol.py**:
- Message passing
- Agent discovery
- Connection weights

### Integration Tests
**End-to-End Flow**:
1. Create task via REST API
2. Daemon picks up task
3. Mode executes task
4. Result validated
5. Task archived
6. WebSocket streams updates

**Multi-Mode Test**:
- Run all three modes simultaneously
- Verify no conflicts
- Check resource limits respected

### Test Environment
- In-memory SQLite for tests (`:memory:`)
- Mock external dependencies (WebSearch, APIs)
- Pytest fixtures for daemon lifecycle

## Main Challenges and Mitigations

### Challenge 1: Daemon Stability
**Mitigation**:
- Comprehensive error handling
- Automatic restart via systemd/launchd
- Health check endpoint (port 8768)
- Watchdog timer (detect hangs)

### Challenge 2: SQLite Locking
**Mitigation**:
- WAL mode (better concurrency)
- Retry logic with exponential backoff
- Connection timeout: 30 seconds
- Regular VACUUM to prevent bloat

### Challenge 3: Breaking Existing CF
**Mitigation**:
- Non-breaking extension (add tools at end)
- Comprehensive tests for existing functionality
- Feature flag for evolution system
- Rollback plan (git revert)

### Challenge 4: Resource Exhaustion
**Mitigation**:
- Active resource monitoring (psutil)
- Configurable limits (CPU, memory)
- Max concurrent tasks: 3
- Active hours enforcement

### Challenge 5: Self-Improvement Risks
**Mitigation**:
- PR-only workflow (no auto-merge)
- Isolated feature branches
- Test validation required
- Human approval mandatory

## Timeline Estimate

**Phase 1 (Scout)**: 5 minutes ✅
**Phase 2 (Architect)**: 15 minutes
**Phase 2.5 (Build Planning)**: 5 minutes
**Phase 3 (Builder)**: 60-90 minutes (parallel execution)
  - Task 1 (Daemon + Queue): 20 minutes
  - Task 2 (Evolution Modes): 20 minutes
  - Task 3 (Communication Layer): 25 minutes
  - Task 4 (Agent Protocol): 15 minutes
  - Task 5 (MCP Tools): 10 minutes
  - Task 6 (Scripts): 10 minutes
**Phase 4 (Test)**: 30-45 minutes (comprehensive testing)
**Phase 5 (Documentation)**: 20 minutes
**Phase 6 (Deploy)**: 10 minutes (feature branch + PR)

**Total Estimated Time**: 2.5 - 3.5 hours

## Success Criteria Mapping

1. ✅ **Daemon starts successfully** - Standard Python daemon pattern with systemd/launchd
2. ✅ **Queue persists across restarts** - SQLite with proper shutdown handling
3. ✅ **All modes generate tasks** - Plugin architecture with base class
4. ✅ **Self-improvement creates PR** - Git workflow with feature branches
5. ✅ **Chaos mode builds project** - Delegation to existing CF build system
6. ✅ **Dashboard displays updates** - FastAPI + WebSocket real-time streaming
7. ✅ **REST API accepts tasks** - FastAPI with OpenAPI documentation
8. ✅ **WebSocket streams logs** - FastAPI WebSocket support
9. ✅ **Tests pass (80%+)** - Pytest with coverage.py
10. ✅ **Documentation complete** - EVOLUTION_SYSTEM.md with examples

## Integration with Existing CF

### Pattern Library
- Read from: `~/.context-foundry/patterns/`
- Write to: Same location
- Use existing MCP tools: `read_global_patterns()`, `merge_project_patterns()`

### Delegation
- Use existing infrastructure in mcp_server.py
- Leverage task tracking and phase monitoring
- Reuse context budget management

### Project Registry
- Auto-register on successful builds
- Track metadata: type, tech stack, patterns used
- Enable pattern application to existing projects

## Risks and Known Issues

### High Risk
1. **Self-improvement breaking CF** → Mitigated by PR workflow
2. **Daemon hanging/crashing** → Mitigated by watchdog + auto-restart

### Medium Risk
1. **SQLite corruption** → Mitigated by WAL mode + regular backups
2. **Resource exhaustion** → Mitigated by active monitoring

### Low Risk
1. **Dashboard XSS** → Local-only binding (v1)
2. **Agent protocol abuse** → Whitelist mode (v1)

## Recommendations for Next Phases

### Architect Phase
- Design detailed module interfaces
- Specify API contracts (OpenAPI schema)
- Define SQLite schema with migrations
- Create sequence diagrams for key flows

### Builder Phase
- Use parallel build tasks (6 tasks recommended)
- Start with core (daemon + queue) as foundation
- Communication layer can be built independently
- MCP tools extend existing file (careful merge)

### Test Phase
- Start with unit tests (fast feedback)
- Integration tests after all components built
- End-to-end test for full workflow
- Performance test (1000+ tasks in queue)

## Conclusion

The Context Foundry Evolution System is an ambitious but achievable enhancement. All technical requirements can be met using existing Python ecosystem tools (FastAPI, SQLite, daemon). The main risks are around daemon stability and self-modification safety, both mitigated through established patterns (systemd management, PR workflow).

The system will enable CF to:
- **Self-improve** through automated analysis and PR generation
- **Explore** through random creative projects
- **Research** through long-running investigation workflows
- **Coordinate** with other agent instances
- **Learn** continuously from every build

This transforms CF from a one-shot build tool into a perpetually-evolving autonomous system.

**Scout Phase Complete** ✅
