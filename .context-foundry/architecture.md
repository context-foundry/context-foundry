# Architecture: Livestream Real-Time Updates Fix

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Autonomous Build Process                  │
│                                                              │
│  Orchestrator → writes .context-foundry/current-phase.json  │
│         ↓                                                    │
│         ↓ (curl POST /api/phase-update)                     │
└─────────┼──────────────────────────────────────────────────┘
          ↓
┌─────────┴──────────────────────────────────────────────────┐
│               Livestream Server (server.py)                 │
│                                                              │
│  ┌─────────────────┐      ┌──────────────────┐            │
│  │ SessionMonitor  │      │ WebSocket Handler│            │
│  │                 │      │                  │            │
│  │ - sessions{}    │◄─────┤ - connections{}  │            │
│  │ - last_update{} │      │ - change_hashes{}│ ← NEW      │
│  └────────┬────────┘      └────────┬─────────┘            │
│           │                         │                       │
│           │ /api/phase-update       │                       │
│           ↓                         ↓                       │
│  ┌─────────────────────────────────────────┐              │
│  │    Broadcast to WebSocket clients       │              │
│  │    (only if data changed - NEW)         │              │
│  └─────────────────┬───────────────────────┘              │
└────────────────────┼────────────────────────────────────────┘
                     ↓
┌────────────────────┴────────────────────────────────────────┐
│          Dashboard (dashboard.html)                          │
│                                                              │
│  WebSocket.onmessage → triggers:                            │
│    1. updateStatus() (existing)                             │
│    2. updateEnhancedMetrics() (NEW)                         │
│                                                              │
│  setInterval (5s) → updateEnhancedMetrics() (NEW)          │
│                                                              │
│  Displays: last updated timestamps (NEW)                    │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│        MetricsCollector (metrics_collector.py)               │
│                                                              │
│  Watchdog FileSystemEventHandler (NEW)                      │
│    → Watches: .context-foundry/current-phase.json          │
│    → on_modified() → collect_metrics()                      │
│    → Debounced (100ms)                                      │
│                                                              │
│  Fallback: Poll checkpoints/ralph/* (existing)              │
└─────────────────────────────────────────────────────────────┘
```

## File Structure

```
tools/livestream/
├── server.py             (MODIFY - add change detection)
├── dashboard.html        (MODIFY - add auto-refresh)
├── metrics_collector.py  (MODIFY - add file watching)
├── mcp_client.py        (MODIFY - prioritize live data)
├── config.py            (READ - get settings)
├── metrics_db.py        (READ - database access)
└── broadcaster.py       (KEEP - no changes)

requirements.txt          (MODIFY - add watchdog)
```

## Module Specifications

### Module 1: Change Detection in WebSocket (server.py)

**Location**: Lines 286-320

**Changes**:
1. Add global hash storage: `last_sent_hashes: Dict[str, str] = {}`
2. Add hash function:
```python
import hashlib

def hash_data(data: Dict) -> str:
    """Create SHA256 hash of data for change detection."""
    data_str = json.dumps(data, sort_keys=True)
    return hashlib.sha256(data_str.encode()).hexdigest()
```

3. Modify WebSocket loop:
```python
@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()

    if session_id not in connections:
        connections[session_id] = set()
    connections[session_id].add(websocket)

    # Track last hash for this connection
    last_hash = None

    try:
        # Send initial status
        status = monitor.get_session_status(session_id)
        current_hash = hash_data(status)
        await websocket.send_json({"type": "status", "data": status})
        last_hash = current_hash

        # Keep connection alive and send updates ONLY if changed
        while True:
            await asyncio.sleep(1)

            status = monitor.get_session_status(session_id)
            current_hash = hash_data(status)

            # CHANGE DETECTION: Only send if data changed
            if current_hash != last_hash:
                await websocket.send_json({"type": "status", "data": status})
                last_hash = current_hash

            # Check if session is complete
            if status.get("is_complete"):
                await websocket.send_json({
                    "type": "complete",
                    "message": "Session completed!"
                })
                break
    except WebSocketDisconnect:
        connections[session_id].remove(websocket)
        if not connections[session_id]:
            del connections[session_id]
```

**Testing**: Send same data twice, verify only one transmission

---

### Module 2: Dashboard Auto-Refresh (dashboard.html)

**Location**: Lines 491-793

**Changes**:

1. Add refresh state management (after line 353):
```javascript
let enhancedMetricsRefreshing = false;
let lastEnhancedMetricsUpdate = null;
```

2. Modify `updateEnhancedMetrics()` to prevent concurrent calls:
```javascript
async function updateEnhancedMetrics(sessionId) {
    // Prevent concurrent refreshes
    if (enhancedMetricsRefreshing) {
        return;
    }

    enhancedMetricsRefreshing = true;

    try {
        const response = await fetch(`/api/metrics/${sessionId}`);
        const data = await response.json();

        if (data.error) {
            console.warn('Enhanced metrics not available:', data.error);
            return;
        }

        // Update last refresh timestamp
        lastEnhancedMetricsUpdate = Date.now();

        // Update all metric panels
        if (data.metrics?.token_usage) {
            updateTokenUsage(data.metrics.token_usage);
        }
        if (data.test_iterations) {
            updateTestIterations(data.test_iterations);
        }
        if (data.agent_performance) {
            updateAgentPerformance(data.agent_performance);
        }
        if (data.decisions) {
            updateDecisions(data.decisions);
        }

        // Update "last updated" display
        updateMetricsTimestamp();

    } catch (error) {
        console.warn('Error fetching enhanced metrics:', error);
    } finally {
        enhancedMetricsRefreshing = false;
    }
}
```

3. Add timestamp display function:
```javascript
function updateMetricsTimestamp() {
    if (!lastEnhancedMetricsUpdate) return;

    const elapsed = Math.floor((Date.now() - lastEnhancedMetricsUpdate) / 1000);
    const timeText = elapsed < 60 ? `${elapsed}s ago` : `${Math.floor(elapsed / 60)}m ago`;

    // Add to each metric panel header
    document.querySelectorAll('.metric-timestamp').forEach(el => {
        el.textContent = `Updated: ${timeText}`;

        // Color code based on freshness
        el.className = 'metric-timestamp text-xs ';
        if (elapsed < 5) el.className += 'text-green-400';
        else if (elapsed < 30) el.className += 'text-yellow-400';
        else el.className += 'text-red-400';
    });
}
```

4. Add HTML timestamp elements (modify metric panel headers):
```html
<h3 class="text-lg font-bold text-gray-200 mb-4">
    🔢 Token Usage
    <span class="metric-timestamp text-xs text-gray-500 float-right">Not updated</span>
</h3>
```

5. Modify WebSocket handler to trigger refresh (line 674):
```javascript
ws.onmessage = (event) => {
    const data = JSON.parse(event.data);

    if (data.type === 'status') {
        updateStatus(data.data);
        // TRIGGER enhanced metrics refresh on WebSocket update
        updateEnhancedMetrics(currentSession);
    } else if (data.type === 'complete') {
        alert('🎉 Session complete!');
    } else if (data.type === 'log') {
        const logsDiv = document.getElementById('logs');
        const line = document.createElement('div');
        line.className = 'log-line text-gray-300';
        line.textContent = data.data;
        logsDiv.appendChild(line);
        logsDiv.scrollTop = logsDiv.scrollHeight;
    }
};
```

6. Add auto-refresh interval (after line 793):
```javascript
// Auto-refresh enhanced metrics every 5 seconds
setInterval(() => {
    if (currentSession) {
        updateEnhancedMetrics(currentSession);
    }
}, 5000);

// Update timestamp display every second
setInterval(updateMetricsTimestamp, 1000);
```

**Testing**: Verify metrics refresh on WebSocket message and every 5s

---

### Module 3: Filesystem Watching (metrics_collector.py)

**Location**: Top of file + new class

**Changes**:

1. Add imports:
```python
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent
import threading
```

2. Add FileSystemEventHandler class (after imports):
```python
class PhaseFileWatcher(FileSystemEventHandler):
    """
    Watches .context-foundry/current-phase.json files for changes.
    Triggers metrics collection when phase data updates.
    """

    def __init__(self, collector: 'MetricsCollector'):
        super().__init__()
        self.collector = collector
        self.debounce_timers = {}  # Debounce rapid changes
        self.debounce_delay = 0.1  # 100ms

    def on_modified(self, event):
        """Handle file modification events."""
        if event.is_directory:
            return

        # Only watch current-phase.json files
        if not event.src_path.endswith('current-phase.json'):
            return

        # Debounce rapid changes
        file_path = event.src_path

        # Cancel existing timer for this file
        if file_path in self.debounce_timers:
            self.debounce_timers[file_path].cancel()

        # Create new timer
        timer = threading.Timer(
            self.debounce_delay,
            self._handle_phase_update,
            args=[file_path]
        )
        timer.start()
        self.debounce_timers[file_path] = timer

    def _handle_phase_update(self, file_path: str):
        """Handle debounced phase file update."""
        print(f"📂 Detected phase file change: {file_path}")

        try:
            # Read phase data
            with open(file_path, 'r') as f:
                phase_data = json.load(f)

            # Extract session info
            session_id = phase_data.get('session_id', 'unknown')

            # Trigger metrics collection for this session
            # This will be called from the collector's context
            asyncio.create_task(
                self.collector.collect_live_phase_update(session_id, phase_data)
            )
        except Exception as e:
            print(f"⚠️  Error handling phase update: {e}")
```

3. Modify MetricsCollector class:
```python
class MetricsCollector:
    def __init__(self, ...):
        # ... existing init ...
        self.observer = None  # Watchdog observer
        self.watcher = None   # FileSystemEventHandler
        self.watched_dirs = set()  # Directories being watched

    async def start(self):
        """Start the collector service with filesystem watching."""
        self.running = True
        print(f"🔄 Metrics Collector started (poll interval: {self.poll_interval}s)")

        # Start filesystem watcher
        self.start_file_watcher()

        # ... existing polling loop ...

    def start_file_watcher(self):
        """Start watching for .context-foundry/current-phase.json changes."""
        self.watcher = PhaseFileWatcher(self)
        self.observer = Observer()

        # Watch common build directories
        watch_paths = [
            Path.home() / "homelab",  # Common build location
            Path.cwd(),                # Current directory
            Path("checkpoints/ralph")  # Checkpoint directory
        ]

        for watch_path in watch_paths:
            if watch_path.exists():
                self.observer.schedule(
                    self.watcher,
                    str(watch_path),
                    recursive=True
                )
                self.watched_dirs.add(str(watch_path))
                print(f"👁️  Watching: {watch_path}")

        self.observer.start()
        print("✅ Filesystem watcher started")

    def stop(self):
        """Stop the collector service."""
        self.running = False

        if self.observer:
            self.observer.stop()
            self.observer.join()

        print("🛑 Metrics Collector stopped")

    async def collect_live_phase_update(self, session_id: str, phase_data: Dict):
        """
        Collect metrics from live phase update (triggered by file watcher).

        Args:
            session_id: Session ID from phase data
            phase_data: Parsed current-phase.json content
        """
        print(f"📊 Collecting metrics for live session: {session_id}")

        # Create simplified task object from phase data
        task = {
            'task_id': session_id,
            'status': phase_data.get('status', 'running'),
            'current_phase': phase_data.get('current_phase', 'Unknown'),
            'phases_completed': phase_data.get('phases_completed', []),
            'test_iteration': phase_data.get('test_iteration', 0),
            'start_time': phase_data.get('started_at'),
            # Try to infer working directory from session_id
            'working_directory': str(Path.cwd() / session_id) if session_id else None
        }

        # Initialize task if new
        if session_id not in self.tracked_tasks:
            await self.initialize_task(task)
            self.tracked_tasks.add(session_id)

        # Update task status
        await self.update_task_status(task)

        # Collect metrics
        await self.collect_task_metrics(task)
```

**Testing**: Touch current-phase.json, verify metrics collected

---

### Module 4: MCP Client Live Data Priority (mcp_client.py)

**Location**: Lines 34-54, 119-142

**Changes**:

1. Modify `_read_phase_file()` to check modification time:
```python
def _read_phase_file(self, working_directory: str) -> Optional[Dict]:
    """
    Read .context-foundry/current-phase.json with freshness check.
    """
    try:
        phase_file = Path(working_directory) / ".context-foundry" / "current-phase.json"
        if not phase_file.exists():
            return None

        # Check file modification time
        mtime = phase_file.stat().st_mtime
        age_seconds = time.time() - mtime

        with open(phase_file, 'r') as f:
            data = json.load(f)

        # Add freshness metadata
        data['_file_age_seconds'] = age_seconds
        data['_is_fresh'] = age_seconds < 10  # Fresh if < 10s old

        return data
    except Exception as e:
        print(f"Error reading phase file: {e}")
        return None
```

2. Modify `get_task_status()` to prioritize live data:
```python
def get_task_status(self, task_id: str, use_cache: bool = True) -> Dict[str, Any]:
    """Get status prioritizing live current-phase.json over checkpoints."""

    # Check cache
    cache_key = f"task_{task_id}"
    if use_cache and cache_key in self.cache:
        cached_data, cached_time = self.cache[cache_key]
        if time.time() - cached_time < self.cache_ttl:
            return cached_data

    # PRIORITY 1: Try reading from live working directory
    # Common patterns: /Users/name/homelab/<project>
    live_paths = [
        Path.home() / "homelab" / task_id,
        Path.cwd() / task_id,
        Path.cwd()  # Current directory itself
    ]

    for live_path in live_paths:
        if live_path.exists():
            phase_data = self._read_phase_file(str(live_path))
            if phase_data and phase_data.get('_is_fresh'):
                # Found fresh live data
                result = {
                    "task_id": task_id,
                    "status": phase_data.get('status', 'running'),
                    "current_phase": phase_data.get('current_phase', 'Unknown'),
                    "phase_number": phase_data.get('phase_number', '?/7'),
                    "phases_completed": phase_data.get('phases_completed', []),
                    "test_iteration": phase_data.get('test_iteration', 0),
                    "started_at": phase_data.get('started_at'),
                    "progress_detail": phase_data.get('progress_detail', ''),
                    "source": "live",
                    "data_age_seconds": phase_data.get('_file_age_seconds', 0)
                }
                self.cache[cache_key] = (result, time.time())
                return result

    # PRIORITY 2: Fall back to checkpoint data
    result = self._read_from_checkpoint(task_id)
    self.cache[cache_key] = (result, time.time())
    return result
```

**Testing**: Create current-phase.json, verify it's read before checkpoints

---

## Implementation Steps (Ordered)

1. **Add watchdog dependency**
   - Modify requirements.txt: `watchdog>=3.0.0`
   - Run: `pip install watchdog`

2. **Implement change detection in server.py**
   - Add hash_data() function
   - Modify WebSocket loop with change detection
   - Test: Send duplicate data, verify single transmission

3. **Implement filesystem watching in metrics_collector.py**
   - Add PhaseFileWatcher class
   - Modify MetricsCollector.start() to initialize watcher
   - Add collect_live_phase_update() method
   - Test: Touch phase file, verify metrics collected

4. **Improve MCP client live data priority**
   - Modify _read_phase_file() with freshness check
   - Modify get_task_status() to prioritize live data
   - Test: Create live phase file, verify it's used

5. **Implement dashboard auto-refresh**
   - Add refresh state management variables
   - Modify updateEnhancedMetrics() with concurrency protection
   - Add updateMetricsTimestamp() function
   - Modify WebSocket onmessage to trigger refresh
   - Add setInterval for periodic refresh
   - Add timestamp HTML elements
   - Test: Verify 5s refresh and WebSocket triggers

6. **Integration testing**
   - Start livestream server
   - Run autonomous build
   - Verify real-time updates
   - Check enhanced metrics refresh
   - Validate no duplicate WebSocket messages

## Testing Requirements

### Unit Tests
- `test_hash_data()` - Verify consistent hashing
- `test_change_detection()` - Verify only changed data sent
- `test_file_watcher_debounce()` - Verify 100ms debouncing
- `test_live_data_priority()` - Verify live data chosen over checkpoint

### Integration Tests
- `test_websocket_real_time_update()` - E2E WebSocket flow
- `test_metrics_collector_file_watch()` - Real file watching
- `test_dashboard_auto_refresh()` - Frontend refresh triggers

### Manual Tests
1. Start server: `python tools/livestream/server.py`
2. Start build: `context-foundry build <task>`
3. Open dashboard: http://localhost:8080
4. Verify updates appear < 1s after phase change
5. Check enhanced metrics refresh every 5s
6. Verify "last updated" timestamps
7. Test with multiple browser tabs

## Success Criteria

✅ Dashboard updates within 1 second of current-phase.json change
✅ WebSocket only sends when data actually changes (95%+ reduction)
✅ Enhanced metrics auto-refresh every 5 seconds
✅ "Last updated" timestamps visible and accurate
✅ No duplicate data in network inspector
✅ Works with live builds AND viewing past sessions
✅ Graceful degradation if enhanced metrics unavailable
✅ No memory leaks during 1-hour test run
