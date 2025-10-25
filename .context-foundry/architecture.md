# Architecture Specification: Multi-Agent Monitoring Dashboard

## System Architecture Overview

### High-Level Design
```
┌─────────────────────────────────────────────────────────────┐
│                    Browser (Frontend)                        │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ dashboard.html (Enhanced)                            │   │
│  │ - Multi-Agent Panel (new)                           │   │
│  │ - Multi-Instance Cards (new)                        │   │
│  │ - Geek Stats Section (new)                          │   │
│  │ - Phase Timeline (new)                              │   │
│  │ - Per-Agent Progress Bars (new)                     │   │
│  │ - Per-Agent Token Gauges (new)                      │   │
│  └──────────────────────────────────────────────────────┘   │
│           ↕ WebSocket (agent events) + REST API              │
└─────────────────────────────────────────────────────────────┘
                              ↕
┌─────────────────────────────────────────────────────────────┐
│              FastAPI Server (server.py)                      │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ New Endpoints:                                       │   │
│  │ - GET /api/agents/{session_id}                      │   │
│  │ - GET /api/agent/{agent_id}                         │   │
│  │ - GET /api/instances                                │   │
│  │ - POST /api/agent-update                            │   │
│  │ Enhanced:                                            │   │
│  │ - POST /api/phase-update (now tracks agents)        │   │
│  │ - WebSocket /ws/{session_id} (agent events)         │   │
│  └──────────────────────────────────────────────────────┘   │
│           ↕ Database queries + Metrics collection            │
└─────────────────────────────────────────────────────────────┘
                              ↕
┌─────────────────────────────────────────────────────────────┐
│         MetricsDatabase (metrics_db.py - Enhanced)           │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ New Table: agent_instances                          │   │
│  │ - id, session_id, agent_id, agent_type              │   │
│  │ - status, phase, progress_percent                   │   │
│  │ - tokens_used, tokens_limit, token_percentage       │   │
│  │ - start_time, end_time, parent_agent_id             │   │
│  │ - error_message                                      │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              ↕
┌─────────────────────────────────────────────────────────────┐
│     MetricsCollector (metrics_collector.py - Enhanced)       │
│  - Watches .context-foundry/current-phase.json              │
│  - Parses orchestrator logs for agent spawning              │
│  - Tracks per-agent token usage                             │
│  - Emits agent WebSocket events                             │
└─────────────────────────────────────────────────────────────┘
```

## Database Schema Changes

### New Table: agent_instances
```sql
CREATE TABLE IF NOT EXISTS agent_instances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    agent_id TEXT UNIQUE NOT NULL,
    agent_type TEXT NOT NULL,  -- 'Scout', 'Architect', 'Builder', 'Tester', etc.
    agent_name TEXT,  -- 'Builder-1', 'Builder-2' for parallel builders
    status TEXT NOT NULL,  -- 'spawning', 'active', 'idle', 'completed', 'failed'
    phase TEXT,  -- Current phase the agent is working on
    progress_percent REAL DEFAULT 0.0,
    tokens_used INTEGER DEFAULT 0,
    tokens_limit INTEGER DEFAULT 200000,
    token_percentage REAL DEFAULT 0.0,
    start_time TEXT,
    end_time TEXT,
    duration_seconds INTEGER,
    parent_agent_id TEXT,  -- For nested agents
    error_message TEXT,
    metadata TEXT,  -- JSON for additional data
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES tasks(task_id)
)
```

### Index for Performance
```sql
CREATE INDEX IF NOT EXISTS idx_agent_instances_session 
ON agent_instances(session_id);

CREATE INDEX IF NOT EXISTS idx_agent_instances_status 
ON agent_instances(status);
```

## API Endpoints

### 1. GET /api/agents/{session_id}
**Purpose**: List all agents for a session
**Response**:
```json
{
  "session_id": "context-foundry",
  "agents": [
    {
      "agent_id": "scout-001",
      "agent_type": "Scout",
      "agent_name": "Scout",
      "status": "completed",
      "phase": "Research",
      "progress_percent": 100.0,
      "tokens_used": 15234,
      "token_percentage": 7.6,
      "start_time": "2025-01-13T10:05:00Z",
      "end_time": "2025-01-13T10:10:00Z",
      "duration_seconds": 300
    },
    {
      "agent_id": "architect-001",
      "agent_type": "Architect",
      "agent_name": "Architect",
      "status": "active",
      "phase": "Design",
      "progress_percent": 45.0,
      "tokens_used": 8932,
      "token_percentage": 4.5,
      "start_time": "2025-01-13T10:10:00Z",
      "end_time": null,
      "duration_seconds": null
    }
  ],
  "total_agents": 2,
  "active_agents": 1
}
```

### 2. GET /api/agent/{agent_id}
**Purpose**: Get detailed status for specific agent
**Response**:
```json
{
  "agent_id": "builder-001",
  "agent_type": "Builder",
  "agent_name": "Builder-1",
  "status": "active",
  "phase": "Implementation",
  "progress_percent": 67.0,
  "tokens_used": 45678,
  "tokens_limit": 200000,
  "token_percentage": 22.8,
  "start_time": "2025-01-13T10:15:00Z",
  "elapsed_seconds": 450,
  "estimated_remaining_seconds": 220,
  "files_modified": ["dashboard.html", "server.py"],
  "current_task": "Implementing multi-agent UI components"
}
```

### 3. GET /api/instances
**Purpose**: List all running Context Foundry instances
**Response**:
```json
{
  "instances": [
    {
      "session_id": "context-foundry",
      "project_name": "context-foundry",
      "status": "building",
      "agents_active": 2,
      "agents_total": 4,
      "progress_percent": 65.0,
      "start_time": "2025-01-13T10:00:00Z",
      "elapsed_seconds": 900
    },
    {
      "session_id": "flight-tracker",
      "project_name": "flight-tracker",
      "status": "testing",
      "agents_active": 1,
      "agents_total": 3,
      "progress_percent": 85.0,
      "start_time": "2025-01-13T09:30:00Z",
      "elapsed_seconds": 2700
    }
  ],
  "total_instances": 2
}
```

### 4. POST /api/agent-update
**Purpose**: Receive agent status updates from orchestrator/builders
**Request Body**:
```json
{
  "session_id": "context-foundry",
  "agent_id": "builder-001",
  "agent_type": "Builder",
  "status": "active",
  "progress_percent": 70.0,
  "tokens_used": 50000,
  "current_task": "Writing tests"
}
```
**Response**:
```json
{
  "status": "updated",
  "agent_id": "builder-001",
  "broadcasted_to": 3
}
```

## WebSocket Events

### Event: agent_spawned
```json
{
  "type": "agent_spawned",
  "session_id": "context-foundry",
  "data": {
    "agent_id": "builder-002",
    "agent_type": "Builder",
    "agent_name": "Builder-2",
    "phase": "Parallel Build",
    "timestamp": "2025-01-13T10:20:00Z"
  }
}
```

### Event: agent_progress
```json
{
  "type": "agent_progress",
  "session_id": "context-foundry",
  "data": {
    "agent_id": "builder-001",
    "progress_percent": 75.0,
    "tokens_used": 55000,
    "token_percentage": 27.5,
    "current_task": "Implementing geek stats section"
  }
}
```

### Event: agent_completed
```json
{
  "type": "agent_completed",
  "session_id": "context-foundry",
  "data": {
    "agent_id": "architect-001",
    "success": true,
    "duration_seconds": 420,
    "files_created": 2,
    "files_modified": 5
  }
}
```

### Event: agent_failed
```json
{
  "type": "agent_failed",
  "session_id": "context-foundry",
  "data": {
    "agent_id": "tester-001",
    "error_message": "Tests failed: 3 failures in test_multi_agent.py",
    "retry_count": 1,
    "will_retry": true
  }
}
```

## Frontend UI Components

### 1. Multi-Agent Panel (New Component)
**Location**: After "Session Selector", before "Main Grid"
**HTML Structure**:
```html
<div id="multiAgentPanel" class="bg-gray-900 p-6 rounded-lg mb-6">
    <h2 class="text-2xl font-bold mb-4">🤖 Active Agents</h2>
    <div id="agentsList" class="space-y-3">
        <!-- Agent cards dynamically inserted here -->
    </div>
</div>
```

**Agent Card Template**:
```html
<div class="agent-card bg-gradient-to-r from-gray-800 to-gray-900 p-4 rounded-lg border border-gray-700">
    <div class="flex justify-between items-center mb-2">
        <div class="flex items-center space-x-2">
            <span class="status-badge {status-class}">●</span>
            <span class="font-bold text-lg">{agent_name}</span>
            <span class="text-xs text-gray-500">{agent_type}</span>
        </div>
        <span class="text-xs text-gray-400">{elapsed_time}</span>
    </div>
    
    <!-- Horizontal Gradient Progress Bar -->
    <div class="progress-container mb-2">
        <div class="h-6 bg-gray-700 rounded-full overflow-hidden relative">
            <div class="progress-bar-fill h-full bg-gradient-to-r from-green-400 via-blue-500 to-blue-600 transition-all duration-500"
                 style="width: {progress_percent}%"></div>
            <div class="absolute inset-0 flex items-center justify-center text-xs font-bold text-white">
                {progress_percent}%
            </div>
        </div>
    </div>
    
    <!-- Per-Agent Token Gauge -->
    <div class="token-gauge-mini mb-2">
        <div class="flex justify-between text-xs mb-1">
            <span class="text-gray-400">Tokens</span>
            <span class="font-mono">{tokens_used} / {tokens_limit}</span>
        </div>
        <div class="h-2 bg-gray-700 rounded-full overflow-hidden">
            <div class="h-full {token-color-class} transition-all duration-300"
                 style="width: {token_percentage}%"></div>
        </div>
    </div>
    
    <!-- Current Task -->
    <div class="text-xs text-gray-400 truncate">
        {current_task}
    </div>
</div>
```

### 2. Multi-Instance Cards (New Component)
**Location**: Top of page, replaces session selector
**HTML Structure**:
```html
<div id="multiInstancePanel" class="mb-6 space-y-3">
    <h2 class="text-2xl font-bold">📦 Active Instances</h2>
    <!-- Instance cards dynamically inserted -->
</div>
```

**Instance Card Template**:
```html
<div class="instance-card bg-gray-900 rounded-lg border border-gray-700 overflow-hidden">
    <div class="instance-header p-4 cursor-pointer hover:bg-gray-800 transition"
         onclick="toggleInstance('{session_id}')">
        <div class="flex justify-between items-center">
            <div>
                <h3 class="font-bold text-lg">{project_name}</h3>
                <p class="text-xs text-gray-400">{session_id}</p>
            </div>
            <div class="text-right">
                <div class="text-sm font-bold {status-color}">{status}</div>
                <div class="text-xs text-gray-500">{agents_active}/{agents_total} agents</div>
            </div>
        </div>
        <div class="mt-2 h-2 bg-gray-700 rounded-full overflow-hidden">
            <div class="h-full bg-blue-500" style="width: {progress_percent}%"></div>
        </div>
    </div>
    <div id="instance-{session_id}-content" class="instance-content hidden p-4 bg-gray-950">
        <!-- Multi-agent panel for this instance -->
    </div>
</div>
```

### 3. Phase Timeline (New Component)
**Location**: In main grid, left column
**HTML Structure**:
```html
<div class="bg-gray-900 p-6 rounded-lg">
    <h3 class="text-lg font-bold mb-4">📊 Phase Progress</h3>
    <div id="phaseTimeline" class="space-y-3">
        <!-- Phase items dynamically inserted -->
    </div>
</div>
```

**Phase Item Template**:
```html
<div class="phase-item flex items-center space-x-3">
    <div class="phase-icon {status-class}">
        {icon} <!-- ⏳ for active, ✓ for complete, ○ for pending -->
    </div>
    <div class="flex-1">
        <div class="flex justify-between text-sm">
            <span class="font-bold">{phase_name}</span>
            <span class="text-gray-400">{duration}</span>
        </div>
        <div class="h-1 bg-gray-700 rounded-full mt-1">
            <div class="h-full {phase-color}" style="width: {percent}%"></div>
        </div>
    </div>
</div>
```

### 4. Geek Stats Section (New Component)
**Location**: Bottom of page, after detailed metrics
**HTML Structure**:
```html
<div class="mt-6">
    <h2 class="text-2xl font-bold mb-4">🤓 Geek Stats</h2>
    <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
        <!-- Stat cards -->
    </div>
</div>
```

**Stat Cards**:
```html
<div class="bg-gray-900 p-6 rounded-lg border border-gray-800">
    <h3 class="text-sm text-gray-400 mb-2">{stat_name}</h3>
    <div class="text-3xl font-bold {color-class}">{value}</div>
    <div class="text-xs text-gray-500 mt-1">{description}</div>
</div>
```

**Stats to Display**:
- Total Agents Spawned
- Parallel vs Sequential (ratio)
- Token Efficiency (tokens per file)
- Avg API Latency
- Iteration Speed (iterations/hour)
- Memory Usage (if available)

## CSS Styling

### Gradient Progress Bars
```css
.progress-bar-in-progress {
    background: linear-gradient(to right, #10b981 0%, #3b82f6 50%, #2563eb 100%);
    animation: shimmer 2s infinite;
}

.progress-bar-idle {
    background: #4b5563;
}

.progress-bar-completed {
    background: #10b981;
}

@keyframes shimmer {
    0%, 100% { background-position: 0% 50%; }
    50% { background-position: 100% 50%; }
}
```

### Token Color Classes
```css
.token-safe { background: #10b981; } /* green <50% */
.token-warning { background: #eab308; } /* yellow 50-75% */
.token-critical { background: #ef4444; } /* red >75% */
```

### Status Badges
```css
.status-active { color: #10b981; }
.status-idle { color: #6b7280; }
.status-completed { color: #3b82f6; }
.status-failed { color: #ef4444; }
```

## Implementation Steps (Ordered)

### Step 1: Database Enhancement (metrics_db.py)
1. Add `agent_instances` table creation in `_init_schema()`
2. Add methods:
   - `create_agent_instance(session_id, agent_data)`
   - `update_agent_instance(agent_id, updates)`
   - `get_agent_instance(agent_id)`
   - `get_session_agents(session_id)`
   - `get_all_instances()`

### Step 2: Backend API (server.py)
1. Add endpoint `GET /api/agents/{session_id}`
2. Add endpoint `GET /api/agent/{agent_id}`
3. Add endpoint `GET /api/instances`
4. Add endpoint `POST /api/agent-update`
5. Enhance WebSocket handler to broadcast agent events
6. Add agent event helpers (broadcast_agent_spawned, etc.)

### Step 3: Metrics Collector (metrics_collector.py)
1. Add agent detection logic in `collect_live_phase_update()`
2. Parse orchestrator output for agent spawning
3. Track per-agent token usage
4. Emit agent WebSocket events
5. Update agent instances in database

### Step 4: Frontend UI (dashboard.html)
1. Add Multi-Agent Panel HTML structure
2. Add Multi-Instance Cards HTML structure
3. Add Phase Timeline component
4. Add Geek Stats section
5. Implement JavaScript functions:
   - `renderAgentCard(agent)`
   - `renderInstanceCard(instance)`
   - `updateAgentProgress(agent_id, progress)`
   - `updateAgentTokens(agent_id, tokens)`
   - `renderPhaseTimeline(phases)`
   - `renderGeekStats(stats)`
6. Add WebSocket event handlers for agent events
7. Add CSS animations and transitions

### Step 5: Testing
1. Unit tests for database methods
2. Unit tests for API endpoints
3. Integration tests for WebSocket events
4. E2E tests with Playwright:
   - Test multi-agent rendering
   - Test progress bar animations
   - Test token gauge colors
   - Test instance card expansion
   - Validate no broken graphs
5. Error handling tests

## Testing Requirements

### Unit Tests (pytest)
```python
# tests/test_agent_instances.py
def test_create_agent_instance()
def test_update_agent_progress()
def test_get_session_agents()
def test_agent_token_tracking()

# tests/test_api_agents.py
def test_get_agents_endpoint()
def test_get_agent_detail_endpoint()
def test_get_instances_endpoint()
def test_agent_update_endpoint()
```

### Integration Tests
```python
# tests/test_websocket_agents.py
async def test_agent_spawned_event()
async def test_agent_progress_event()
async def test_agent_completed_event()
```

### E2E Tests (Playwright)
```javascript
// tests/e2e/test_dashboard.spec.js
test('multi-agent panel renders correctly', async ({ page }) => {
    await page.goto('http://localhost:8080');
    await page.waitForSelector('#multiAgentPanel');
    const agents = await page.locator('.agent-card').count();
    expect(agents).toBeGreaterThan(0);
});

test('progress bars animate smoothly', async ({ page }) => {
    // Verify CSS transitions work
});

test('no broken graphs or console errors', async ({ page }) => {
    const errors = [];
    page.on('console', msg => {
        if (msg.type() === 'error') errors.push(msg.text());
    });
    await page.goto('http://localhost:8080');
    await page.waitForTimeout(2000);
    expect(errors).toHaveLength(0);
});
```

## Success Criteria

1. ✅ Agent instances table created and populated
2. ✅ API endpoints return correct agent data
3. ✅ WebSocket events broadcast agent updates
4. ✅ Multi-agent panel displays all active agents
5. ✅ Horizontal gradient progress bars animate
6. ✅ Per-agent token gauges show color-coded warnings
7. ✅ Multi-instance cards expand/collapse
8. ✅ Phase timeline shows progress
9. ✅ Geek stats display comprehensive metrics
10. ✅ All tests pass (unit, integration, E2E)
11. ✅ No console errors or broken graphs
12. ✅ Backwards compatible with existing sessions
13. ✅ Performance: <10 WebSocket updates per second per agent
14. ✅ UI responsive and smooth on all viewports

## Error Handling Strategy

1. **Data Validation**: Check all incoming data for null/undefined before rendering
2. **Fallback Values**: Use defaults when data missing ("No data", 0%, gray status)
3. **Loading States**: Show spinners while fetching data
4. **Error Boundaries**: Catch rendering errors and show friendly messages
5. **Graceful Degradation**: If multi-agent features fail, fall back to single-agent view
6. **Logging**: Log warnings for parsing failures but continue operation

## Preventive Measures

1. **No Broken Graphs**: Validate all chart data before passing to Chart.js
2. **No Flickering**: Throttle WebSocket updates, use CSS transitions
3. **Performance**: Batch DOM updates, use requestAnimationFrame
4. **Memory Leaks**: Clean up event listeners on component unmount
5. **Backwards Compatibility**: Feature detection, keep old APIs working

This architecture ensures robust, production-ready multi-agent monitoring!
