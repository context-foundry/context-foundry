# Architecture Design: Context Foundry Evolution System (CFES)

## System Architecture Overview

The CFES extends Context Foundry with a daemon-based autonomous evolution layer, creating a continuously-running system that improves itself and generates new projects.

```
┌──────────────────────────────────────────────────────────────┐
│                    External Interfaces                        │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────────┐     │
│  │ Web Dashboard│  │  REST API   │  │ WebSocket Stream │     │
│  │  (Port 8765) │  │ (Port 8766) │  │   (Port 8767)    │     │
│  └──────┬───────┘  └──────┬──────┘  └────────┬─────────┘     │
└─────────┼──────────────────┼──────────────────┼───────────────┘
          │                  │                  │
┌─────────┼──────────────────┼──────────────────┼───────────────┐
│         │    Evolution Daemon (Main Loop)     │               │
│         └──────────┬───────┘  ┌───────────────┘               │
│                    │          │                                │
│         ┌──────────▼──────────▼──────────┐                    │
│         │     Task Queue Manager          │                    │
│         │   (SQLite: task_queue.db)       │                    │
│         └──────────┬──────────────────────┘                    │
│                    │                                            │
│         ┌──────────▼──────────────────────┐                    │
│         │   Evolution Modes (Plugins)     │                    │
│         │  ┌────────────────────────┐     │                    │
│         │  │ Self-Improvement Mode  │────┐│                    │
│         │  └────────────────────────┘    ││                    │
│         │  ┌────────────────────────┐    ││                    │
│         │  │ Chaos/Creative Mode    │────┼┤                    │
│         │  └────────────────────────┘    ││                    │
│         │  ┌────────────────────────┐    ││                    │
│         │  │ Research/Discovery Mode│────┘│                    │
│         │  └────────────────────────┘     │                    │
│         └──────────┬──────────────────────┘                    │
│                    │                                            │
│         ┌──────────▼──────────────────────┐                    │
│         │  Existing CF Build System       │                    │
│         │  (via MCP delegation)           │                    │
│         └─────────────────────────────────┘                    │
│                                                                 │
│  ┌──────────────────────────────────────────────────────┐     │
│  │       Agent Protocol (Multi-Agent Network)           │     │
│  │  - Message passing                                   │     │
│  │  - Agent discovery                                   │     │
│  │  - Connection weights                                │     │
│  └──────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────┘
```

## Module Breakdown

### 1. Evolution Daemon (`tools/evolution/daemon.py`)

**Purpose**: Main service orchestrator running continuously

**Class Structure**:
```python
class EvolutionDaemon:
    def __init__(self, config_path: str = None):
        self.config = load_config(config_path)
        self.task_queue = TaskQueueManager()
        self.resource_manager = ResourceManager()
        self.modes = {
            'self_improvement': SelfImprovementMode(),
            'chaos_creative': ChaosCreativeMode(),
            'research_discovery': ResearchDiscoveryMode()
        }
        self.running = False
        self.active_tasks = {}
        
    def start(self):
        """Start daemon (daemonize or run in foreground)"""
        
    def main_loop(self):
        """Main polling loop (runs every 60s)"""
        
    def handle_signals(self):
        """Setup SIGTERM, SIGHUP handlers"""
        
    def process_task(self, task: Task):
        """Execute single task with appropriate mode"""
        
    def check_resources(self) -> bool:
        """Verify CPU/memory within limits"""
        
    def graceful_shutdown(self):
        """Wait for active tasks, cleanup"""
```

**Key Methods**:
- `daemonize()` - Fork process, create PID file, detach from terminal
- `reload_config()` - SIGHUP handler, reload without restart
- `poll_queue()` - Check for pending tasks every 60s
- `execute_task_async()` - Run task in background, track progress
- `cleanup_completed()` - Archive finished tasks

**Configuration**: `~/.context-foundry/evolution/config.json`

**Logging**: Rotating file at `~/.context-foundry/evolution/logs/daemon.log`

---

### 2. Task Queue Manager (`tools/evolution/task_queue.py`)

**Purpose**: SQLite-based persistent task storage with ACID guarantees

**Database Schema**:
```sql
-- Main task table
CREATE TABLE tasks (
    id TEXT PRIMARY KEY,  -- UUID
    type TEXT NOT NULL CHECK(type IN ('self_improvement', 'chaos_creative', 'research', 'apply_pattern', 'validate')),
    status TEXT NOT NULL CHECK(status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    priority INTEGER NOT NULL DEFAULT 5 CHECK(priority BETWEEN 1 AND 10),
    params_json TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    result_json TEXT,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3
);

CREATE INDEX idx_tasks_status_priority ON tasks(status, priority DESC, created_at);
CREATE INDEX idx_tasks_type ON tasks(type);

-- Task history (archived tasks)
CREATE TABLE task_history (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    status TEXT NOT NULL,
    priority INTEGER NOT NULL,
    params_json TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    result_json TEXT,
    error_message TEXT,
    archived_at TEXT NOT NULL
);

CREATE INDEX idx_history_created ON task_history(created_at DESC);

-- Project registry
CREATE TABLE project_registry (
    path TEXT PRIMARY KEY,
    project_type TEXT NOT NULL,
    metadata_json TEXT,
    last_updated TEXT NOT NULL,
    patterns_applied TEXT  -- JSON array
);

CREATE INDEX idx_projects_type ON project_registry(project_type);

-- Agent network
CREATE TABLE agent_network (
    agent_id TEXT PRIMARY KEY,
    agent_name TEXT NOT NULL,
    agent_url TEXT,
    capabilities_json TEXT,
    connection_weight REAL DEFAULT 1.0 CHECK(connection_weight BETWEEN 0 AND 10),
    last_seen TEXT NOT NULL
);

CREATE INDEX idx_agents_last_seen ON agent_network(last_seen DESC);
```

**Class Structure**:
```python
class TaskQueueManager:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or default_path()
        self.conn = None
        self._init_db()
        
    def _init_db(self):
        """Initialize database with schema"""
        
    def create_task(self, task_type: str, params: Dict, priority: int = 5) -> str:
        """Add new task, return task_id"""
        
    def get_next_task(self) -> Optional[Task]:
        """Get highest priority pending task with locking"""
        
    def update_task_status(self, task_id: str, status: str, result: Dict = None):
        """Update task status atomically"""
        
    def retry_task(self, task_id: str):
        """Increment retry count, reset to pending"""
        
    def archive_old_tasks(self, days: int = 30):
        """Move completed/failed tasks to history"""
        
    def register_project(self, path: str, project_type: str, metadata: Dict):
        """Add project to registry"""
        
    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """Retrieve agent info"""
```

**Concurrency Strategy**:
```python
# WAL mode for better concurrency
PRAGMA journal_mode=WAL;

# Task locking pattern
BEGIN IMMEDIATE;
SELECT * FROM tasks WHERE status='pending' ORDER BY priority DESC, created_at LIMIT 1;
UPDATE tasks SET status='running', started_at=? WHERE id=?;
COMMIT;
```

**Retry Logic**:
```python
def should_retry(task: Task) -> bool:
    if task.retry_count >= task.max_retries:
        return False
    return True

def calculate_backoff(retry_count: int) -> int:
    """Exponential backoff: 1s, 2s, 4s"""
    return 2 ** retry_count
```

---

### 3. Resource Manager (`tools/evolution/resource_manager.py`)

**Purpose**: Monitor system resources, enforce limits

**Class Structure**:
```python
class ResourceManager:
    def __init__(self, config: Dict):
        self.max_cpu_percent = config.get('max_cpu_percent', 80)
        self.max_memory_gb = config.get('max_memory_gb', 16)
        self.active_hours = config.get('active_hours', [6, 22])
        
    def check_cpu(self) -> bool:
        """Check if CPU usage is within limits"""
        cpu = psutil.cpu_percent(interval=1)
        return cpu < self.max_cpu_percent
        
    def check_memory(self) -> bool:
        """Check if memory usage is within limits"""
        memory = psutil.virtual_memory()
        memory_gb = memory.used / (1024**3)
        return memory_gb < self.max_memory_gb
        
    def is_active_hour(self) -> bool:
        """Check if current time is within active hours"""
        current_hour = datetime.now().hour
        start, end = self.active_hours
        return start <= current_hour < end
        
    def can_accept_task(self) -> bool:
        """Check all resource constraints"""
        return (
            self.check_cpu() and
            self.check_memory() and
            self.is_active_hour()
        )
```

---

### 4. Evolution Modes (Plugin System)

#### Base Mode (`tools/evolution/modes/base_mode.py`)

**Abstract Interface**:
```python
from abc import ABC, abstractmethod
from typing import List, Dict, Any

class Task:
    def __init__(self, task_id: str, task_type: str, params: Dict):
        self.task_id = task_id
        self.task_type = task_type
        self.params = params

class TaskResult:
    def __init__(self, success: bool, output: Any, error: str = None):
        self.success = success
        self.output = output
        self.error = error

class BaseEvolutionMode(ABC):
    def __init__(self, config: Dict = None):
        self.config = config or {}
        
    @abstractmethod
    def generate_tasks(self) -> List[Task]:
        """Analyze environment and generate improvement tasks"""
        pass
    
    @abstractmethod
    def execute_task(self, task: Task) -> TaskResult:
        """Execute a single task using CF delegation"""
        pass
    
    @abstractmethod
    def validate_result(self, result: TaskResult) -> bool:
        """Validate task completion"""
        pass
```

#### Self-Improvement Mode (`tools/evolution/modes/self_improvement.py`)

**Implementation**:
```python
class SelfImprovementMode(BaseEvolutionMode):
    def generate_tasks(self) -> List[Task]:
        """Analyze CF codebase for improvements"""
        tasks = []
        
        # Check test coverage
        coverage_report = self._run_coverage()
        if coverage_report.missing_coverage:
            tasks.append(Task(
                task_id=uuid4(),
                task_type='self_improvement',
                params={
                    'action': 'add_tests',
                    'files': coverage_report.missing_files
                }
            ))
        
        # Check for linting issues
        lint_issues = self._run_linter()
        if lint_issues:
            tasks.append(Task(
                task_id=uuid4(),
                task_type='self_improvement',
                params={
                    'action': 'fix_lint',
                    'issues': lint_issues
                }
            ))
        
        # Check for TODOs
        todos = self._find_todos()
        for todo in todos:
            tasks.append(Task(
                task_id=uuid4(),
                task_type='self_improvement',
                params={
                    'action': 'implement_todo',
                    'file': todo.file,
                    'line': todo.line,
                    'description': todo.text
                }
            ))
        
        return tasks
    
    def execute_task(self, task: Task) -> TaskResult:
        """Execute via CF delegation with PR workflow"""
        # Create feature branch
        branch_name = f"self-improvement/task-{task.task_id}"
        subprocess.run(['git', 'checkout', '-b', branch_name])
        
        # Delegate to CF build system
        result = delegate_to_cf(task.params)
        
        # Create PR (NEVER auto-merge)
        if result.success:
            pr_url = create_pr(
                branch=branch_name,
                title=f"Self-improvement: {task.params['action']}",
                body=f"Automated PR from Evolution System\n\n{result.summary}"
            )
            return TaskResult(success=True, output={'pr_url': pr_url})
        else:
            return TaskResult(success=False, error=result.error)
    
    def _run_coverage(self):
        """Run coverage.py and parse report"""
        subprocess.run(['coverage', 'run', '-m', 'pytest'])
        report = subprocess.run(['coverage', 'report', '--show-missing'], capture_output=True)
        return parse_coverage_report(report.stdout)
    
    def _run_linter(self):
        """Run ruff and parse issues"""
        result = subprocess.run(['ruff', 'check', '.'], capture_output=True)
        return parse_lint_output(result.stdout)
    
    def _find_todos(self):
        """Grep for TODO/FIXME comments"""
        result = subprocess.run(['grep', '-rn', 'TODO\\|FIXME', 'tools/'], capture_output=True)
        return parse_todo_output(result.stdout)
```

#### Chaos/Creative Mode (`tools/evolution/modes/chaos_creative.py`)

**Implementation**:
```python
class ChaosCreativeMode(BaseEvolutionMode):
    PROJECT_TYPES = {
        'web_app': 0.30,
        'cli_tool': 0.20,
        'game': 0.15,
        'framework': 0.15,
        'art': 0.10,
        'experiment': 0.10
    }
    
    def generate_tasks(self) -> List[Task]:
        """Generate random project ideas"""
        project_type = self._weighted_random(self.PROJECT_TYPES)
        project_idea = self._generate_idea(project_type)
        
        return [Task(
            task_id=uuid4(),
            task_type='chaos_creative',
            params={
                'project_type': project_type,
                'idea': project_idea,
                'tech_stack': self._select_tech_stack(project_type)
            }
        )]
    
    def execute_task(self, task: Task) -> TaskResult:
        """Delegate to CF build system"""
        start_time = time.time()
        
        result = delegate_to_cf({
            'task': task.params['idea'],
            'mode': 'new_project'
        })
        
        duration = time.time() - start_time
        
        # Track metrics
        self._record_metrics({
            'project_type': task.params['project_type'],
            'success': result.success,
            'duration': duration,
            'tests_passed': result.tests_passed,
            'patterns_used': result.patterns
        })
        
        # Update pattern library
        if result.success:
            self._contribute_patterns(result.patterns)
        
        return TaskResult(
            success=result.success,
            output={
                'project_path': result.project_path,
                'github_url': result.github_url,
                'duration': duration
            }
        )
    
    def _weighted_random(self, weights: Dict[str, float]) -> str:
        """Select item based on weights"""
        import random
        items = list(weights.keys())
        probs = list(weights.values())
        return random.choices(items, weights=probs)[0]
    
    def _generate_idea(self, project_type: str) -> str:
        """Use LLM to generate creative project idea"""
        # Call to LLM for idea generation
        prompt = f"Generate a creative {project_type} project idea"
        return call_llm(prompt)
    
    def _select_tech_stack(self, project_type: str) -> List[str]:
        """Select appropriate tech stack"""
        stacks = {
            'web_app': ['react', 'typescript', 'tailwind'],
            'cli_tool': ['python', 'click', 'rich'],
            'game': ['javascript', 'html5-canvas', 'physics-engine'],
            # ...
        }
        return stacks.get(project_type, [])
```

#### Research/Discovery Mode (`tools/evolution/modes/research_discovery.py`)

**Implementation**:
```python
class ResearchDiscoveryMode(BaseEvolutionMode):
    def generate_tasks(self) -> List[Task]:
        """Generate tasks from research prompts"""
        # Read research queue (from config or file)
        research_prompts = self._read_research_queue()
        
        tasks = []
        for prompt in research_prompts:
            tasks.append(Task(
                task_id=uuid4(),
                task_type='research',
                params={
                    'prompt': prompt,
                    'sources': ['arxiv', 'pubmed', 'web'],
                    'depth': 'thorough'
                }
            ))
        
        return tasks
    
    def execute_task(self, task: Task) -> TaskResult:
        """Conduct multi-step research"""
        prompt = task.params['prompt']
        sources = task.params['sources']
        
        # Phase 1: Paper discovery
        papers = []
        if 'arxiv' in sources:
            papers.extend(self._search_arxiv(prompt))
        if 'pubmed' in sources:
            papers.extend(self._search_pubmed(prompt))
        if 'web' in sources:
            papers.extend(self._search_web(prompt))
        
        # Phase 2: Analyze papers
        summaries = [self._summarize_paper(p) for p in papers]
        
        # Phase 3: Synthesize findings
        synthesis = self._synthesize_findings(summaries)
        
        # Phase 4: Generate hypotheses
        hypotheses = self._generate_hypotheses(synthesis)
        
        # Create research report
        report = self._create_report(
            prompt=prompt,
            papers=papers,
            synthesis=synthesis,
            hypotheses=hypotheses
        )
        
        # Save report
        report_path = self._save_report(report)
        
        return TaskResult(
            success=True,
            output={
                'report_path': report_path,
                'papers_analyzed': len(papers),
                'hypotheses_generated': len(hypotheses)
            }
        )
    
    def _search_arxiv(self, query: str):
        """Search arXiv API"""
        import arxiv
        search = arxiv.Search(query=query, max_results=10)
        return list(search.results())
    
    def _create_report(self, **kwargs) -> str:
        """Generate markdown research report"""
        report = f"""# Research Report: {kwargs['prompt']}

## Summary
{kwargs['synthesis']}

## Papers Analyzed
"""
        for paper in kwargs['papers']:
            report += f"- [{paper.title}]({paper.url}) - {paper.authors}\n"
        
        report += "\n## Hypotheses\n"
        for i, hyp in enumerate(kwargs['hypotheses'], 1):
            report += f"{i}. {hyp}\n"
        
        return report
```

---

### 5. Communication Layer

#### REST API (`tools/evolution/communication/rest_api.py`)

**FastAPI Application**:
```python
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List

app = FastAPI(
    title="Context Foundry Evolution API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

class TaskCreate(BaseModel):
    task_type: str
    priority: int = 5
    params: Optional[Dict] = None

class TaskResponse(BaseModel):
    id: str
    type: str
    status: str
    priority: int
    created_at: str
    started_at: Optional[str]
    completed_at: Optional[str]

@app.post("/tasks", response_model=TaskResponse)
async def create_task(task: TaskCreate):
    """Create new evolution task"""
    task_id = task_queue.create_task(
        task_type=task.task_type,
        params=task.params,
        priority=task.priority
    )
    return task_queue.get_task(task_id)

@app.get("/tasks", response_model=List[TaskResponse])
async def list_tasks(
    status: Optional[str] = None,
    type: Optional[str] = None,
    limit: int = Query(50, le=500)
):
    """List tasks with optional filters"""
    return task_queue.list_tasks(
        status=status,
        task_type=type,
        limit=limit
    )

@app.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str):
    """Get task details"""
    task = task_queue.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@app.delete("/tasks/{task_id}")
async def cancel_task(task_id: str):
    """Cancel pending task"""
    success = task_queue.cancel_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found or already running")
    return {"status": "cancelled"}

@app.get("/health")
async def health_check():
    """System health"""
    return {
        "status": "healthy",
        "daemon_running": daemon.is_running(),
        "queue_size": task_queue.count_pending(),
        "active_tasks": len(daemon.active_tasks)
    }
```

**Server Launch**:
```python
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="127.0.0.1",  # Local only
        port=8766,
        log_level="info"
    )
```

#### Web Dashboard (`tools/evolution/communication/web_dashboard.py`)

**FastAPI + Jinja2**:
```python
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

app = FastAPI()
templates = Jinja2Templates(directory="tools/evolution/templates")

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Main dashboard page"""
    active_tasks = task_queue.list_tasks(status='running')
    pending_tasks = task_queue.list_tasks(status='pending', limit=10)
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "active_tasks": active_tasks,
        "pending_tasks": pending_tasks,
        "queue_size": len(pending_tasks),
        "daemon_status": "running" if daemon.is_running() else "stopped"
    })

@app.get("/tasks", response_class=HTMLResponse)
async def tasks_page(request: Request):
    """Tasks list page"""
    tasks = task_queue.list_tasks(limit=100)
    return templates.TemplateResponse("tasks.html", {
        "request": request,
        "tasks": tasks
    })

@app.get("/projects", response_class=HTMLResponse)
async def projects_page(request: Request):
    """Projects registry page"""
    projects = task_queue.list_projects()
    return templates.TemplateResponse("projects.html", {
        "request": request,
        "projects": projects
    })
```

**WebSocket for Live Updates**:
```python
from fastapi import WebSocket

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time updates"""
    await websocket.accept()
    
    # Subscribe to task updates
    subscription = task_queue.subscribe()
    
    try:
        while True:
            # Wait for task status change
            event = await subscription.next()
            
            # Send to client
            await websocket.send_json({
                "type": "task_update",
                "task_id": event.task_id,
                "status": event.status,
                "timestamp": event.timestamp.isoformat()
            })
    except WebSocketDisconnect:
        subscription.unsubscribe()
```

#### WebSocket Stream (`tools/evolution/communication/websocket_stream.py`)

**Dedicated WebSocket Server** (Port 8767):
```python
import asyncio
import websockets

async def stream_handler(websocket, path):
    """Handle streaming connections"""
    subscription = task_queue.subscribe()
    
    try:
        async for event in subscription:
            message = {
                "type": event.type,
                "data": event.data,
                "timestamp": event.timestamp.isoformat()
            }
            await websocket.send(json.dumps(message))
    except websockets.ConnectionClosed:
        pass
    finally:
        subscription.unsubscribe()

async def main():
    async with websockets.serve(stream_handler, "127.0.0.1", 8767):
        await asyncio.Future()  # Run forever

if __name__ == "__main__":
    asyncio.run(main())
```

---

### 6. Agent Protocol (`tools/evolution/agent_protocol.py`)

**Multi-Agent Network**:
```python
class AgentProtocol:
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.agent_id = uuid4()
        self.network = AgentNetwork()
        
    def register_agent(self, agent_name: str, agent_url: str = None, capabilities: List[str] = None):
        """Register agent in network"""
        self.network.add_agent(Agent(
            id=uuid4(),
            name=agent_name,
            url=agent_url,
            capabilities=capabilities or [],
            weight=1.0
        ))
    
    def send_message(self, target: str, message_type: str, payload: Dict):
        """Send message to another agent"""
        message = {
            "from": self.agent_name,
            "to": target,
            "type": message_type,
            "payload": payload,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        agent = self.network.get_agent(target)
        if agent.url:
            # Remote agent - HTTP POST
            requests.post(f"{agent.url}/messages", json=message)
        else:
            # Local agent - file-based
            self._write_local_message(target, message)
    
    def discover_agents(self):
        """Discover other agents on network"""
        # File-based discovery (scan shared directory)
        shared_dir = Path("~/.context-foundry/evolution/shared_tasks")
        for file in shared_dir.glob("agent_*.json"):
            agent_info = json.loads(file.read_text())
            self.register_agent(**agent_info)
```

---

### 7. MCP Tools Extension (`tools/mcp_server.py`)

**Add at end of file (after existing tools)**:
```python
# ═══════════════════════════════════════════════════════════
# EVOLUTION SYSTEM TOOLS (CFES)
# ═══════════════════════════════════════════════════════════

from tools.evolution.task_queue import TaskQueueManager
from tools.evolution.daemon import EvolutionDaemon

# Initialize evolution components (lazy loading)
_task_queue = None
_daemon = None

def get_task_queue():
    global _task_queue
    if _task_queue is None:
        _task_queue = TaskQueueManager()
    return _task_queue

def get_daemon():
    global _daemon
    if _daemon is None:
        _daemon = EvolutionDaemon()
    return _daemon

@mcp.tool()
def create_evolution_task(
    task_type: str,
    target_project: Optional[str] = None,
    pattern_id: Optional[str] = None,
    priority: int = 5,
    params: Optional[Dict] = None
) -> str:
    """
    Create a new evolution task and add to queue.
    
    Args:
        task_type: Type of task ('self_improvement', 'chaos_creative', 'research', 'apply_pattern', 'validate')
        target_project: Optional project path for apply_pattern/validate tasks
        pattern_id: Optional pattern ID for apply_pattern tasks
        priority: Task priority 1-10 (default 5)
        params: Optional additional parameters as JSON dict
    
    Returns:
        JSON string with task ID and status
    """
    try:
        queue = get_task_queue()
        
        task_params = params or {}
        if target_project:
            task_params['target_project'] = target_project
        if pattern_id:
            task_params['pattern_id'] = pattern_id
        
        task_id = queue.create_task(
            task_type=task_type,
            params=task_params,
            priority=priority
        )
        
        return json.dumps({
            "success": True,
            "task_id": task_id,
            "status": "pending",
            "message": f"Task {task_id} created successfully"
        })
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e)
        })

@mcp.tool()
def get_evolution_tasks(
    status: str = "pending",
    limit: int = 50
) -> str:
    """
    List evolution tasks with optional filters.
    
    Args:
        status: Filter by status ('pending', 'running', 'completed', 'failed', 'all')
        limit: Maximum number of tasks to return (default 50)
    
    Returns:
        JSON string with list of tasks
    """
    try:
        queue = get_task_queue()
        
        tasks = queue.list_tasks(
            status=None if status == 'all' else status,
            limit=limit
        )
        
        return json.dumps({
            "success": True,
            "count": len(tasks),
            "tasks": [task.to_dict() for task in tasks]
        })
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e)
        })

@mcp.tool()
def start_evolution_daemon(config_path: Optional[str] = None) -> str:
    """
    Start the evolution daemon.
    
    Args:
        config_path: Optional path to config file (default: ~/.context-foundry/evolution/config.json)
    
    Returns:
        JSON string with daemon status
    """
    try:
        daemon = get_daemon()
        
        if daemon.is_running():
            return json.dumps({
                "success": False,
                "message": "Daemon is already running",
                "pid": daemon.get_pid()
            })
        
        daemon.start(config_path=config_path)
        
        return json.dumps({
            "success": True,
            "message": "Daemon started successfully",
            "pid": daemon.get_pid()
        })
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e)
        })

@mcp.tool()
def stop_evolution_daemon(graceful: bool = True) -> str:
    """
    Stop the evolution daemon.
    
    Args:
        graceful: If True, wait for active tasks to complete (default True)
    
    Returns:
        JSON string with stop status
    """
    try:
        daemon = get_daemon()
        
        if not daemon.is_running():
            return json.dumps({
                "success": False,
                "message": "Daemon is not running"
            })
        
        daemon.stop(graceful=graceful)
        
        return json.dumps({
            "success": True,
            "message": "Daemon stopped successfully"
        })
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e)
        })

@mcp.tool()
def get_daemon_status() -> str:
    """
    Get daemon health and statistics.
    
    Returns:
        JSON string with daemon status, queue size, active tasks, resource usage
    """
    try:
        daemon = get_daemon()
        queue = get_task_queue()
        
        status = {
            "running": daemon.is_running(),
            "pid": daemon.get_pid() if daemon.is_running() else None,
            "uptime_seconds": daemon.get_uptime() if daemon.is_running() else 0,
            "queue_size": queue.count_pending(),
            "active_tasks": len(daemon.active_tasks) if daemon.is_running() else 0,
            "completed_tasks": queue.count_completed(),
            "failed_tasks": queue.count_failed(),
            "resource_usage": {
                "cpu_percent": psutil.cpu_percent(interval=1),
                "memory_mb": psutil.virtual_memory().used / (1024**2)
            }
        }
        
        return json.dumps({
            "success": True,
            "status": status
        })
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e)
        })

@mcp.tool()
def register_project(
    project_path: str,
    project_type: str,
    metadata: Optional[Dict] = None
) -> str:
    """
    Register a project in the global registry.
    
    Args:
        project_path: Absolute path to project directory
        project_type: Type of project (e.g., 'web-app', 'cli-tool', 'game')
        metadata: Optional metadata dict
    
    Returns:
        JSON string with registration status
    """
    try:
        queue = get_task_queue()
        
        queue.register_project(
            path=project_path,
            project_type=project_type,
            metadata=metadata or {}
        )
        
        return json.dumps({
            "success": True,
            "message": f"Project registered: {project_path}"
        })
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e)
        })

@mcp.tool()
def apply_pattern_to_project(
    project_path: str,
    pattern_id: str
) -> str:
    """
    Apply a specific pattern to an existing project.
    
    Args:
        project_path: Path to project
        pattern_id: Pattern ID from global library
    
    Returns:
        JSON string with application result
    """
    try:
        # Create task to apply pattern
        queue = get_task_queue()
        
        task_id = queue.create_task(
            task_type='apply_pattern',
            params={
                'project_path': project_path,
                'pattern_id': pattern_id
            },
            priority=7
        )
        
        return json.dumps({
            "success": True,
            "task_id": task_id,
            "message": f"Pattern application task created: {task_id}"
        })
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e)
        })

@mcp.tool()
def validate_project_health(project_path: str) -> str:
    """
    Run tests and validate project health.
    
    Args:
        project_path: Path to project to validate
    
    Returns:
        JSON string with validation results
    """
    try:
        # Create validation task
        queue = get_task_queue()
        
        task_id = queue.create_task(
            task_type='validate',
            params={'project_path': project_path},
            priority=8
        )
        
        return json.dumps({
            "success": True,
            "task_id": task_id,
            "message": f"Validation task created: {task_id}"
        })
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e)
        })

@mcp.tool()
def register_agent(
    agent_name: str,
    agent_url: Optional[str] = None,
    capabilities: Optional[List[str]] = None
) -> str:
    """
    Register an agent in the network.
    
    Args:
        agent_name: Name of the agent
        agent_url: Optional URL for remote agent (None for local)
        capabilities: Optional list of agent capabilities
    
    Returns:
        JSON string with registration status
    """
    try:
        queue = get_task_queue()
        
        agent_id = queue.register_agent(
            name=agent_name,
            url=agent_url,
            capabilities=capabilities or []
        )
        
        return json.dumps({
            "success": True,
            "agent_id": agent_id,
            "message": f"Agent registered: {agent_name}"
        })
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e)
        })

@mcp.tool()
def send_agent_message(
    target_agent: str,
    message_type: str,
    payload: Dict
) -> str:
    """
    Send message to another agent.
    
    Args:
        target_agent: Target agent name or ID
        message_type: Type of message ('task_delegation', 'learning_share', 'health_check')
        payload: Message payload as dict
    
    Returns:
        JSON string with send status
    """
    try:
        protocol = AgentProtocol(agent_name="cfes")
        
        protocol.send_message(
            target=target_agent,
            message_type=message_type,
            payload=payload
        )
        
        return json.dumps({
            "success": True,
            "message": f"Message sent to {target_agent}"
        })
    except Exception as e:
        return json.dumps({
            "success": False,
            "error": str(e)
        })
```

---

## File Structure

```
context-foundry/
├── tools/
│   ├── mcp_server.py           # MODIFY: Add 10 new tools at end
│   └── evolution/              # NEW DIRECTORY
│       ├── __init__.py
│       ├── daemon.py           # Main daemon (300 lines)
│       ├── task_queue.py       # SQLite queue (250 lines)
│       ├── resource_manager.py # Resource monitoring (100 lines)
│       ├── agent_protocol.py   # Agent network (200 lines)
│       ├── modes/
│       │   ├── __init__.py
│       │   ├── base_mode.py    # Abstract base (80 lines)
│       │   ├── self_improvement.py (300 lines)
│       │   ├── chaos_creative.py   (250 lines)
│       │   └── research_discovery.py (300 lines)
│       ├── communication/
│       │   ├── __init__.py
│       │   ├── local_exchange.py  (100 lines)
│       │   ├── web_dashboard.py   (250 lines)
│       │   ├── rest_api.py        (200 lines)
│       │   └── websocket_stream.py (150 lines)
│       └── templates/          # Jinja2 templates
│           ├── dashboard.html
│           ├── tasks.html
│           └── projects.html
├── scripts/
│   ├── start_evolution.sh      # Launch daemon
│   ├── stop_evolution.sh       # Stop daemon
│   └── install_service.sh      # systemd/launchd install
├── tests/evolution/
│   ├── __init__.py
│   ├── test_daemon.py
│   ├── test_task_queue.py
│   ├── test_modes.py
│   ├── test_communication.py
│   └── test_agent_protocol.py
└── docs/
    └── EVOLUTION_SYSTEM.md     # User guide

Runtime directory (created on first run):
~/.context-foundry/evolution/
├── config.json                 # Configuration
├── task_queue.db               # SQLite database
├── daemon.pid                  # PID file
├── logs/
│   └── daemon.log              # Rotating log
└── shared_tasks/               # Local agent exchange
    └── agent_*.json
```

**Total New Code**: ~2500 lines

---

## Implementation Steps (Parallel Build Tasks)

### Task 1: Core Daemon + Task Queue (20 minutes)
**Files**:
- `tools/evolution/__init__.py`
- `tools/evolution/daemon.py`
- `tools/evolution/task_queue.py`
- `tools/evolution/resource_manager.py`

**Dependencies**: None (foundation layer)

---

### Task 2: Evolution Modes (20 minutes)
**Files**:
- `tools/evolution/modes/__init__.py`
- `tools/evolution/modes/base_mode.py`
- `tools/evolution/modes/self_improvement.py`
- `tools/evolution/modes/chaos_creative.py`
- `tools/evolution/modes/research_discovery.py`

**Dependencies**: Task 1 (needs task queue)

---

### Task 3: Communication Layer (25 minutes)
**Files**:
- `tools/evolution/communication/__init__.py`
- `tools/evolution/communication/rest_api.py`
- `tools/evolution/communication/web_dashboard.py`
- `tools/evolution/communication/websocket_stream.py`
- `tools/evolution/communication/local_exchange.py`
- `tools/evolution/templates/` (HTML files)

**Dependencies**: Task 1 (needs task queue)

---

### Task 4: Agent Protocol (15 minutes)
**Files**:
- `tools/evolution/agent_protocol.py`

**Dependencies**: Task 1 (needs task queue)

---

### Task 5: MCP Tools Extension (10 minutes)
**Files**:
- `tools/mcp_server.py` (MODIFY: add tools at end)

**Dependencies**: Tasks 1, 2, 4 (imports from evolution/)

---

### Task 6: Scripts and Configuration (10 minutes)
**Files**:
- `scripts/start_evolution.sh`
- `scripts/stop_evolution.sh`
- `scripts/install_service.sh`
- `~/.context-foundry/evolution/config.json` (template)

**Dependencies**: Task 1 (needs daemon)

---

## Testing Plan

### Unit Tests
- **test_daemon.py**: Start/stop, signal handling, main loop
- **test_task_queue.py**: CRUD, locking, retry, archive
- **test_modes.py**: Task generation, execution, validation
- **test_communication.py**: API endpoints, WebSocket
- **test_agent_protocol.py**: Message passing, discovery

### Integration Tests
- **End-to-end flow**: REST API → Daemon → Mode → Result
- **Multi-mode**: All three modes running simultaneously
- **Resource limits**: Verify CPU/memory enforcement
- **Performance**: 1000+ tasks in queue

### Coverage Target: 80%+

---

## Success Criteria

1. ✅ Daemon starts and enters polling loop
2. ✅ Queue persists across restarts (SQLite)
3. ✅ All modes generate valid tasks
4. ✅ Self-improvement creates PR (not auto-merge)
5. ✅ Chaos mode delegates to CF build system
6. ✅ Dashboard shows live updates (WebSocket)
7. ✅ REST API accepts and schedules tasks
8. ✅ WebSocket streams build logs
9. ✅ Tests pass with 80%+ coverage
10. ✅ Documentation is comprehensive

---

## Deployment Strategy

### Feature Branch
- Branch name: `feature/evolution-system`
- Base: `main`
- Create PR for human review
- DO NOT auto-merge (this modifies CF itself)

### PR Checklist
- [ ] All tests passing
- [ ] Coverage >= 80%
- [ ] Documentation complete
- [ ] No breaking changes to existing MCP tools
- [ ] Scripts tested on macOS and Linux
- [ ] Configuration template included

---

## Configuration Template

**File**: `~/.context-foundry/evolution/config.json`
```json
{
  "daemon": {
    "enabled": true,
    "poll_interval_seconds": 60,
    "max_concurrent_tasks": 3,
    "log_level": "INFO"
  },
  "modes": {
    "self_improvement": {
      "enabled": true,
      "priority": 8,
      "schedule": "0 0 * * *",
      "max_daily_tasks": 5
    },
    "chaos_creative": {
      "enabled": true,
      "priority": 5,
      "schedule": "0 */6 * * *",
      "project_types": ["web-app", "cli-tool", "game", "framework"]
    },
    "research_discovery": {
      "enabled": false,
      "priority": 9,
      "schedule": "on_demand"
    }
  },
  "resources": {
    "max_cpu_percent": 80,
    "max_memory_gb": 16,
    "active_hours": [6, 22]
  },
  "communication": {
    "web_dashboard_port": 8765,
    "rest_api_port": 8766,
    "websocket_port": 8767,
    "expose_external": false,
    "cors_origins": ["http://localhost:3000"]
  },
  "agent_network": {
    "enable_discovery": true,
    "allow_external_agents": false,
    "trust_mode": "whitelist",
    "heartbeat_interval_seconds": 30
  }
}
```

---

## Architecture Complete ✅

This architecture provides:
- **Modularity**: Each component is independent
- **Extensibility**: Easy to add new modes or tools
- **Safety**: Resource limits, PR workflow, graceful shutdown
- **Observability**: Dashboard, API, WebSocket, logs
- **Persistence**: SQLite with ACID guarantees
- **Multi-agent**: Network protocol for coordination

Ready for parallel build execution.
