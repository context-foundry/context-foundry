# Context Foundry Evolution System Guide

**Autonomous self-improvement system that uses Context Foundry to improve itself**

## Quick Reference Commands

### View Logs
```bash
# View daemon logs (main system output)
tail -f /tmp/daemon_with_auth.log

# View evolution logs (task execution details)
tail -f ~/.context-foundry/evolution/logs/daemon.log

# View Claude execution logs (Context Foundry build output)
ls -lt ~/.context-foundry/evolution/delegation-logs/
tail -f ~/.context-foundry/evolution/delegation-logs/claude-*.log
```

### Check Status
```bash
# Check if daemon is running
ps aux | grep "tools.evolution.daemon" | grep -v grep

# View task queue
sqlite3 ~/.context-foundry/evolution/task_queue.db "SELECT id, type, status, created_at FROM tasks ORDER BY created_at DESC LIMIT 10;"

# Check for open PRs
gh pr list --repo context-foundry
```

### Start the Daemon
```bash
# Start in foreground (recommended for testing)
python3 -m tools.evolution.daemon start --foreground

# Start in background with logging
nohup python3 -m tools.evolution.daemon start --foreground > /tmp/daemon_output.log 2>&1 &

# Or use the convenience command:
cd /Users/name/homelab/context-foundry
python3 -m tools.evolution.daemon start
```

### Stop the Daemon
```bash
# Graceful stop (waits for current task to finish)
pkill -TERM -f "tools.evolution.daemon"

# Force stop (immediate)
pkill -9 -f "tools.evolution.daemon"

# Or use the daemon command:
python3 -m tools.evolution.daemon stop
```

## How It Works

### The Perpetual Loop

```
1. Daemon polls every 60 seconds
2. Checks GitHub for open self-improvement PRs
3. If PRs exist → PAUSE (wait for human review)
4. If no PRs → Check task queue
5. If task in queue → Execute via Context Foundry
6. Context Foundry creates PR → Back to step 1
```

### Execution Flow

```
Daemon → Spawns Claude CLI → Calls MCP autonomous_build_and_deploy →
Scout Agent → Architect Agent → Builder Agent → Test Agent → Deploy Agent →
PR Created → Human Reviews → Merge → Loop Continues ♾️
```

## Configuration

### Location
```bash
~/.context-foundry/evolution/config.json
```

### Default Settings
```json
{
  "daemon": {
    "enabled": true,
    "poll_interval_seconds": 60,
    "max_concurrent_tasks": 1,
    "log_level": "INFO"
  },
  "modes": {
    "self_improvement": {"enabled": true, "priority": 8},
    "chaos_creative": {"enabled": true, "priority": 5},
    "research_discovery": {"enabled": false, "priority": 9}
  },
  "resources": {
    "max_cpu_percent": 80,
    "max_memory_gb": 16,
    "active_hours": [6, 22]
  }
}
```

## Task Management

### Add a Task Manually
```bash
# Add a TODO to any file (daemon will pick it up)
echo "# TODO: Add input validation to user registration" >> tools/example.py

# The daemon will automatically:
# 1. Find the TODO on next poll
# 2. Create a task in the queue
# 3. Execute it via Context Foundry
# 4. Create a PR
```

### View Task Queue
```bash
# All tasks
sqlite3 ~/.context-foundry/evolution/task_queue.db "SELECT * FROM tasks;"

# Pending tasks only
sqlite3 ~/.context-foundry/evolution/task_queue.db "SELECT id, type, params_json FROM tasks WHERE status = 'pending';"

# Failed tasks
sqlite3 ~/.context-foundry/evolution/task_queue.db "SELECT id, type, error FROM tasks WHERE status = 'failed';"
```

### Clear Tasks
```bash
# Clear all pending tasks
sqlite3 ~/.context-foundry/evolution/task_queue.db "DELETE FROM tasks WHERE status = 'pending';"

# Clear all tasks
sqlite3 ~/.context-foundry/evolution/task_queue.db "DELETE FROM tasks;"
```

## GitHub Authentication

The daemon uses `gh` CLI for authentication (avoiding rate limits).

### Check Authentication
```bash
gh auth status
```

### Login (if needed)
```bash
gh auth login
```

## Monitoring

### Web Dashboard
```bash
# Start dashboard
python3 tools/evolution/communication/web_dashboard_server.py &

# Access locally
open http://localhost:8765

# Access remotely via Tailscale
open http://100.106.244.86:8765
```

### Real-time Monitoring
```bash
# Watch daemon logs
tail -f /tmp/daemon_with_auth.log

# Watch task queue changes
watch -n 5 'sqlite3 ~/.context-foundry/evolution/task_queue.db "SELECT COUNT(*) as pending FROM tasks WHERE status = \"pending\";"'

# Watch for new PRs
watch -n 30 'gh pr list --repo context-foundry'
```

## Troubleshooting

### Daemon won't start
```bash
# Check if already running
ps aux | grep "tools.evolution.daemon"

# Remove stale PID file
rm -f ~/.context-foundry/evolution/daemon.pid

# Check logs for errors
tail -50 /tmp/daemon_with_auth.log
```

### GitHub rate limit errors
```bash
# Verify gh authentication
gh auth status

# Check rate limit status
gh api rate_limit
```

### Tasks not executing
```bash
# Check task queue
sqlite3 ~/.context-foundry/evolution/task_queue.db "SELECT * FROM tasks WHERE status = 'pending';"

# Check daemon logs
tail -50 ~/.context-foundry/evolution/logs/daemon.log

# Verify no open PRs blocking execution
gh pr list --repo context-foundry
```

### TODO not detected
```bash
# TODOs must follow this format:
# TODO: Description here (with colon!)

# Test TODO detection
python3 -c "
import sys
sys.path.insert(0, '/Users/name/homelab/context-foundry')
from tools.evolution.modes.self_improvement import SelfImprovementMode
mode = SelfImprovementMode()
todos = mode._find_todos()
print(f'Found {len(todos)} TODOs')
for t in todos[:5]:
    print(f'  - {t[\"text\"][:80]}')
"
```

## Safety Features

### Human-in-the-Loop
- **Every PR requires human review** before merging
- Daemon pauses when Evolution System PRs are open
- Only 1 PR at a time (prevents flooding)
- **PR Filtering**: Only pauses for PRs with these branch patterns:
  - `self-improvement/*` (primary pattern)
  - `enhancement/*` (legacy pattern)
  - `fix/*` (automated fixes)
  - Other human-created PRs are ignored

### Resource Management
- CPU usage limited to 80%
- Memory usage limited to 16GB
- Active hours: 6am - 10pm (configurable)

### Rate Limiting
- GitHub API: 5000 requests/hour (with auth)
- Poll interval: 60 seconds
- Max concurrent tasks: 1

## Advanced Usage

### Run Specific Mode
```python
from tools.evolution.modes.self_improvement import SelfImprovementMode

mode = SelfImprovementMode()
tasks = mode.generate_tasks()
print(f"Generated {len(tasks)} tasks")
```

### Custom Task Creation
```python
from tools.evolution.task_queue import TaskQueueManager, TaskType

queue = TaskQueueManager()
task_id = queue.create_task(
    task_type=TaskType.SELF_IMPROVEMENT.value,
    params={
        'action': 'implement_todo',
        'description': 'Add email validation',
        'priority': 8
    },
    priority=8
)
print(f"Created task: {task_id}")
```

### View Delegation Logs
```bash
# List all Claude execution logs
ls -lth ~/.context-foundry/evolution/delegation-logs/

# View most recent execution
tail -100 ~/.context-foundry/evolution/delegation-logs/claude-$(ls -t ~/.context-foundry/evolution/delegation-logs/ | grep claude | head -1)

# View prompts sent to Claude
ls -lth ~/.context-foundry/evolution/delegation-logs/prompt-*.txt
cat ~/.context-foundry/evolution/delegation-logs/prompt-$(ls -t ~/.context-foundry/evolution/delegation-logs/ | grep prompt | head -1)
```

## Files and Directories

```
~/.context-foundry/evolution/
├── config.json                    # Daemon configuration
├── daemon.pid                     # Process ID file
├── task_queue.db                  # SQLite task database
├── logs/
│   └── daemon.log                 # Daemon execution logs
└── delegation-logs/
    ├── claude-{id}.log            # Context Foundry execution logs
    └── prompt-{id}.txt            # Prompts sent to Claude

/tmp/
└── daemon_with_auth.log           # Current daemon output
```

## What Gets Improved?

The system looks for:
1. **TODO comments** (with colon: `# TODO: ...`)
2. **FIXME comments** (with colon: `# FIXME: ...`)
3. **Self-generated tasks** when no TODOs exist:
   - Priority 9: Test coverage
   - Priority 8: Type safety
   - Priority 7: Error handling
   - Priority 6: Documentation
   - Priority 5: Code quality

## Example Workflow

```bash
# 1. Start the daemon
python3 -m tools.evolution.daemon start --foreground &

# 2. Add a TODO to improve
echo "# TODO: Add rate limiting to API endpoints" >> src/api.py

# 3. Monitor logs
tail -f /tmp/daemon_with_auth.log

# 4. Wait for PR (daemon polls every 60s)
# You'll see: "✅ PERPETUAL LOOP: Queued task {id}"

# 5. Wait for Context Foundry to create PR
# You'll see: "⏸️ PAUSED: Waiting for PR(s) [X] to be merged"

# 6. Review PR on GitHub
gh pr view X

# 7. Merge when satisfied
gh pr merge X

# 8. Daemon automatically continues
# You'll see: "✅ PRs merged! Queuing next improvement task..."

# Loop repeats forever ♾️
```

## Support

- **Logs**: Check `/tmp/daemon_with_auth.log` first
- **Queue**: Use `sqlite3 ~/.context-foundry/evolution/task_queue.db`
- **PRs**: Use `gh pr list --repo context-foundry`
- **Restart**: `pkill -f tools.evolution.daemon && python3 -m tools.evolution.daemon start`
