# Evolution System - Quick Commands

## View Logs (The commands you asked for!)

```bash
# Daemon output (what the daemon is doing RIGHT NOW)
tail -f /tmp/daemon_with_auth.log

# Evolution logs (detailed task execution)
tail -f ~/.context-foundry/evolution/logs/daemon.log

# Context Foundry build logs (what CF agents are doing)
tail -f ~/.context-foundry/evolution/delegation-logs/claude-*.log
```

## Check if Running

```bash
# Is it running?
ps aux | grep "tools.evolution.daemon" | grep -v grep

# Or check status
python3 -m tools.evolution.daemon status
```

## Start the System

```bash
# Simple start (foreground, logs to terminal)
cd /Users/name/homelab/context-foundry
python3 -m tools.evolution.daemon start --foreground

# Start in background with logging
nohup python3 -m tools.evolution.daemon start --foreground > /tmp/daemon_output.log 2>&1 &
```

## Stop the System

```bash
# Graceful stop
pkill -TERM -f "tools.evolution.daemon"

# Force stop
pkill -9 -f "tools.evolution.daemon"
```

## Monitor

```bash
# View task queue
sqlite3 ~/.context-foundry/evolution/task_queue.db "SELECT * FROM tasks;"

# Check for PRs
gh pr list

# Watch logs in real-time
tail -f /tmp/daemon_with_auth.log
```

## Common Tasks

```bash
# Add a TODO for the system to work on
echo "# TODO: Add rate limiting to API" >> tools/api.py

# Clear bad tasks from queue
sqlite3 ~/.context-foundry/evolution/task_queue.db "DELETE FROM tasks WHERE status = 'pending';"

# Restart everything
pkill -f "tools.evolution.daemon" && sleep 2 && python3 -m tools.evolution.daemon start --foreground &
```

---
**Full documentation:** `docs/EVOLUTION_SYSTEM_GUIDE.md`
