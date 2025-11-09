# Mission Control - Context Foundry TUI

**Beautiful Terminal UI for managing autonomous builds and delegations**

Mission Control is the primary interface for Context Foundry, providing a Claude-style chat interface alongside real-time build monitoring and file exploration.

![Mission Control Screenshot](assets/screenshots/mission-control-overview.png)
*Screenshot: Mission Control main interface showing all three tabs*

---

## Features

### 🎯 Three-Tab Interface

Mission Control provides a unified interface with three main views:

#### 1. **Conversation Tab**
- Claude-style chat interface for natural language interaction
- Ask questions, start builds, get status updates
- Full markdown rendering for rich responses
- Scrollable conversation history

![Conversation Tab](assets/screenshots/conversation-tab.png)
*Screenshot: Conversation tab with Claude-style chat*

#### 2. **Builds Tab**
- Real-time monitoring of all user-initiated delegations
- Live status updates with daemon integration
- Sortable columns: Status, Project, Started, Duration, Phase, Progress, Daemon
- Color-coded status indicators:
  - **Green** - Running/Monitoring
  - **Blue** - Complete/Checked
  - **Yellow** - Queued
  - **Red** - Failed
  - **Orange** - Timeout

![Builds Tab](assets/screenshots/builds-tab.png)
*Screenshot: Builds tab showing active delegations with daemon monitoring status*

**Columns:**
- **Status** - Current build state (Running, Complete, Failed, etc.)
- **Project** - Project name from GitHub repo or working directory
- **Started** - Build start time (HH:MM:SS format)
- **Duration** - Elapsed time (seconds, minutes, or hours)
- **Phase** - Current build phase (Scout, Architect, Builder, Test, Deploy)
- **Progress** - Detailed progress information
- **Daemon** - Evolution daemon monitoring status:
  - `Monitoring` (green bold) - Actively monitored with ProcessWatchdog
  - `Queued` (yellow) - Monitoring task pending in daemon queue
  - `Checked` (blue) - Monitoring task completed
  - `-` (dim) - Not monitored by daemon

#### 3. **Directory Tab**
- Multi-build file explorer
- Separate tabs for each active build's working directory
- Real-time file tree updates
- Navigate and inspect build outputs

![Directory Tab](assets/screenshots/directory-tab.png)
*Screenshot: Directory tab showing file trees for multiple builds*

---

## Delegation Management System

Mission Control integrates deeply with the **Evolution daemon** for robust delegation management:

### Architecture

```
User → Mission Control TUI
         ↓
    Delegation Metadata (~/.context-foundry/delegations/)
         ↓
    Evolution Daemon (monitors every 60s)
         ↓
    DelegationMode → ProcessWatchdog
         ↓
    Task Queue (SQLite) → delegation_build tasks
         ↓
    REST API (/delegations) ← External tools
```

### Components

1. **Delegation Files** (`~/.context-foundry/delegations/task-{id}.json`)
   - Stores delegation metadata (task_id, project, status, PID, timestamps)
   - Written by MCP server when delegation starts
   - Updated on completion/failure

2. **Evolution Daemon** (`tools/evolution/daemon.py`)
   - Polls delegation files every 60 seconds
   - Creates monitoring tasks in SQLite queue
   - Registers PIDs with ProcessWatchdog for timeout detection
   - Recovers orphaned delegations on startup

3. **DelegationMode** (`tools/evolution/modes/delegation.py`)
   - Monitors running delegations
   - Registers/unregisters PIDs with ProcessWatchdog
   - Detects completion and updates status

4. **ProcessWatchdog** (`tools/evolution/process_watchdog.py`)
   - Monitors delegation processes for timeouts (60min max)
   - Detects stuck processes (no log activity for 10min)
   - Kills runaway processes
   - Tracks token usage estimates

5. **REST API** (`tools/evolution/command_server.py`)
   ```
   GET  /delegations           - List all delegations
   GET  /delegations/{id}      - Get specific delegation
   POST /delegations/{id}/cancel - Cancel running delegation
   ```

---

## How It Works

### Starting a Build

1. User types in Conversation tab: "Build a weather app"
2. Mission Control sends request to MCP server
3. MCP server creates delegation file and spawns Claude process
4. Builds tab immediately shows new entry with "Running" status
5. Evolution daemon detects new delegation within 60s
6. Daemon creates monitoring task in SQLite queue
7. DelegationMode registers PID with ProcessWatchdog
8. Mission Control queries daemon DB and shows "Monitoring" status

### Build Monitoring

**Every 1.5 seconds:**
- Mission Control reads delegation metadata files
- Queries daemon SQLite database for monitoring status
- Updates Builds tab with latest info

**Every 60 seconds:**
- Daemon polls delegation files
- Re-creates monitoring tasks for completed checks
- ProcessWatchdog checks for timeouts/stuck processes

### Build Completion

1. Claude process completes and updates delegation metadata
2. MCP server writes final status (completed/failed/timeout)
3. DelegationMode detects completion
4. Unregisters PID from ProcessWatchdog
5. Marks monitoring task as completed
6. Mission Control shows final status in Builds tab

### Build Recovery

On daemon startup:
- Scans `~/.context-foundry/delegations/` for running delegations
- Checks if PIDs are still alive using psutil
- Re-creates monitoring tasks for orphaned builds
- Marks dead processes as "failed" with error message

---

## Screenshots

### Where to Add Screenshots

Place screenshots in `docs/assets/screenshots/`:

```
docs/assets/screenshots/
├── mission-control-overview.png    # Full TUI showing all three tabs
├── conversation-tab.png            # Conversation tab with chat history
├── builds-tab.png                  # Builds tab with delegation list
├── directory-tab.png               # Directory tab with file trees
├── daemon-monitoring.png           # Close-up of "Daemon" column showing statuses
└── build-recovery.png              # Example of recovered delegation
```

### Screenshot Guidelines

**Recommended tool:** Use a terminal screenshot tool like:
- `screencapture` (macOS built-in)
- `gnome-screenshot` (Linux)
- iTerm2's built-in screenshot feature (Cmd+Shift+S)

**Recommended terminal setup:**
- **Font:** Monospace, 14pt
- **Window size:** 120x40 columns minimum
- **Theme:** Dark theme for contrast
- **Content:** Show real examples with active builds

**Example screenshots to capture:**

1. **mission-control-overview.png**
   - Show all three tabs visible (switch between them)
   - At least 2-3 active builds in Builds tab
   - Some conversation history in Conversation tab

2. **builds-tab.png**
   - Focus on Builds tab
   - Show variety of statuses (Running, Complete, Failed)
   - Show different daemon monitoring states (Monitoring, Queued, Checked, -)
   - At least 5 rows for good visual

3. **conversation-tab.png**
   - Show natural language interaction
   - Example: "Build a weather app" → Claude response
   - Show markdown rendering (bold, code blocks)

4. **directory-tab.png**
   - Show 2-3 build tabs
   - Expanded file trees
   - Different project structures

---

## Usage Examples

### Starting Mission Control

```bash
# Using the 'cf' command (if installed via pip install -e .)
cf

# Or run directly
python3 -m tools.cli
```

### Keyboard Navigation

**Global:**
- `Ctrl+C` or `q` - Quit
- `1`, `2`, `3` - Switch to Conversation, Builds, Directory tab
- `Tab` - Cycle focus between UI elements

**Conversation Tab:**
- Type message and press `Enter` to send
- `Up/Down` - Scroll conversation history

**Builds Tab:**
- `Up/Down` - Navigate delegation list
- `Enter` - View detailed logs (future feature)
- Click column headers to sort

**Directory Tab:**
- `Up/Down` - Navigate file tree
- `Enter` - Expand/collapse directories

---

## Integration with Claude Code

Mission Control works seamlessly with Claude Code CLI:

```bash
# In Claude Code session
claude> Use the autonomous_build_and_deploy MCP tool to build a weather app

# In separate terminal
cf  # Watch build progress in real-time
```

The delegation appears immediately in Mission Control's Builds tab!

---

## Configuration

Mission Control settings are in `~/.context-foundry/config/`:

```json
{
  "refresh_interval": 1.5,
  "daemon_poll_interval": 60,
  "max_concurrent_tasks": 3,
  "max_duration_minutes": 60,
  "max_tokens_per_task": 100000
}
```

---

## Troubleshooting

### Builds Tab Shows "unknown" Start Times

**Cause:** Delegation metadata missing `start_time` or `started` field

**Fix:** Ensure MCP server writes timestamps:
```python
metadata["start_time"] = datetime.now().isoformat()
```

### Daemon Column Shows "-" for All Builds

**Cause:** Evolution daemon not running or database connection issue

**Fix:**
```bash
# Check daemon status
python3 -m tools.evolution.daemon status

# Start daemon if not running
python3 -m tools.evolution.daemon start

# Check database exists
ls -la ~/.context-foundry/evolution/task_queue.db
```

### ProcessWatchdog Not Killing Stuck Processes

**Cause:** PIDs not registered with watchdog

**Fix:** Check DelegationMode integration in `tools/evolution/modes/delegation.py:126-138`

---

## Technical Details

### Database Schema

**Task Queue** (`~/.context-foundry/evolution/task_queue.db`):

```sql
CREATE TABLE tasks (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL CHECK(type IN (
        'self_improvement',
        'chaos_creative',
        'research',
        'apply_pattern',
        'validate',
        'delegation_build',
        'delegation_deploy',
        'delegation_test'
    )),
    status TEXT NOT NULL CHECK(status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    priority INTEGER NOT NULL DEFAULT 5,
    params_json TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    result_json TEXT,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3
);
```

### Delegation Metadata Format

```json
{
  "task_id": "abc-123-def-456",
  "project": "weather-app",
  "github_repo_name": "weather-app",
  "working_directory": "/Users/name/homelab/weather-app",
  "start_time": "2025-11-08T18:51:40.419195",
  "status": "running",
  "pid": 12345,
  "current_phase": "Builder",
  "phase_status": "in_progress",
  "progress_detail": "Creating API integration..."
}
```

### Monitoring Query

Mission Control queries daemon status with:

```python
def get_daemon_monitoring_status(task_id: str) -> Optional[dict]:
    db_path = Path.home() / ".context-foundry" / "evolution" / "task_queue.db"
    conn = sqlite3.connect(str(db_path))

    cursor = conn.execute("""
        SELECT status, json_extract(result_json, '$.pid') as pid
        FROM tasks
        WHERE type = 'delegation_build'
          AND json_extract(params_json, '$.mcp_task_id') = ?
        ORDER BY created_at DESC
        LIMIT 1
    """, (task_id,))

    row = cursor.fetchone()
    # Returns: {"monitored": True, "task_status": "running", "pid": 12345}
```

---

## See Also

- [Evolution Daemon Architecture](MULTI_AGENT_ARCHITECTURE.md)
- [MCP Server Documentation](MCP_SERVER_ARCHITECTURE.md)
- [Delegation Model](DELEGATION_MODEL.md)
- [TUI Implementation Plan](TUI_IMPLEMENTATION_PLAN.md) - Original monitoring TUI design

---

## Future Enhancements

- [ ] Click build in Builds tab to view detailed logs
- [ ] Cancel build button
- [ ] Restart failed build
- [ ] Export build history to JSON
- [ ] Notifications on build completion
- [ ] Terminal bell on failure
- [ ] Configurable refresh intervals
- [ ] Filter builds by status/project
- [ ] Search functionality

---

**Mission Control** - Your command center for autonomous AI builds 🚀
