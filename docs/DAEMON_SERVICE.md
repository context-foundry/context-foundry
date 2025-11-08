# Evolution Daemon - Service Management Guide

The Context Foundry Evolution daemon can run as a managed system service for automatic startup and crash recovery.

## Quick Start

### Install as System Service

```bash
# Install and start the daemon service
bash scripts/install_service.sh
```

This will:
- Auto-detect your OS (macOS or Linux)
- Create appropriate service configuration (launchd or systemd)
- Start the daemon automatically
- Enable auto-start on boot/login

### Service Management

Use the convenient helper script for all service operations:

```bash
# Check service status
bash scripts/service.sh status

# Start the daemon
bash scripts/service.sh start

# Stop the daemon
bash scripts/service.sh stop

# Restart the daemon
bash scripts/service.sh restart

# View logs (auto-follows)
bash scripts/service.sh logs

# Launch monitoring dashboard
bash scripts/service.sh monitor

# Uninstall service
bash scripts/service.sh uninstall

# Show all commands
bash scripts/service.sh help
```

## macOS (launchd)

### Service Details

- **Service Label**: `dev.contextfoundry.evolution`
- **Plist Location**: `~/Library/LaunchAgents/dev.contextfoundry.evolution.plist`
- **Runs As**: Your user account
- **Auto-start**: On login (RunAtLoad)
- **Crash Recovery**: Automatic restart (60-second throttle)

### Direct launchctl Commands

```bash
# Check if service is loaded
launchctl list | grep contextfoundry

# Load service (start)
launchctl load ~/Library/LaunchAgents/dev.contextfoundry.evolution.plist

# Unload service (stop)
launchctl unload ~/Library/LaunchAgents/dev.contextfoundry.evolution.plist

# View service details
launchctl list dev.contextfoundry.evolution
```

### Configuration

The plist file includes:

- **WorkingDirectory**: Project root directory
- **EnvironmentVariables**: PATH, HOME
- **KeepAlive**: Restart on crash (not on clean exit)
- **ThrottleInterval**: 60 seconds between restart attempts
- **Resource Limits**: Max 1024 open files

### Logs

```bash
# Daemon application log (main log)
tail -f ~/.context-foundry/evolution/logs/daemon.log

# launchd stdout (console output)
tail -f ~/.context-foundry/evolution/logs/launchd-stdout.log

# launchd stderr (errors)
tail -f ~/.context-foundry/evolution/logs/launchd-stderr.log
```

Log rotation is automatic:
- **Max size per file**: 10MB
- **Backup files kept**: 5
- **Automatic cleanup**: Old logs deleted when limit reached

## Linux (systemd)

### Service Details

- **Service Name**: `context-foundry-evolution`
- **Service File**: `~/.config/systemd/user/context-foundry-evolution.service`
- **Runs As**: Your user account (user service)
- **Auto-start**: On login (default.target)
- **Crash Recovery**: Automatic restart (60-second delay)

### Direct systemctl Commands

```bash
# Check service status
systemctl --user status context-foundry-evolution

# Start service
systemctl --user start context-foundry-evolution

# Stop service
systemctl --user stop context-foundry-evolution

# Restart service
systemctl --user restart context-foundry-evolution

# Enable auto-start
systemctl --user enable context-foundry-evolution

# Disable auto-start
systemctl --user disable context-foundry-evolution

# Reload service configuration
systemctl --user daemon-reload
```

### Configuration

The service file includes:

- **Type**: simple (foreground process)
- **WorkingDirectory**: Project root
- **Environment**: PATH, HOME
- **Restart**: on-failure only
- **RestartSec**: 60 seconds between attempts
- **LimitNOFILE**: 1024 open files

### Logs

```bash
# View logs (journald)
journalctl --user -u context-foundry-evolution -f

# View last 100 lines
journalctl --user -u context-foundry-evolution -n 100

# View logs since boot
journalctl --user -u context-foundry-evolution -b

# Daemon application log
tail -f ~/.context-foundry/evolution/logs/daemon.log
```

## Monitoring

### Evolution Monitor Dashboard

Real-time visual dashboard showing:
- Current daemon status
- Claude instances running
- MCP delegation progress
- Recent file changes
- Git status
- Open PRs

```bash
# Launch monitor (auto-refreshes every 2 seconds)
bash scripts/service.sh monitor

# Or directly:
bash tools/evolution/scripts/watch-evolution.sh
```

### Checking Daemon Status Programmatically

```bash
# Get daemon PID (if running)
python3 -m tools.evolution.daemon status

# Check task queue
python3 -c "
from tools.evolution.task_queue import TaskQueueManager
tq = TaskQueueManager()
print(f'Pending tasks: {tq.count_pending()}')
print(f'Running tasks: {len(tq.list_tasks(status=\"running\"))}')
"
```

## Troubleshooting

### Service Won't Start

1. **Check logs for errors**:
   ```bash
   # macOS
   tail -100 ~/.context-foundry/evolution/logs/launchd-stderr.log

   # Linux
   journalctl --user -u context-foundry-evolution -n 100
   ```

2. **Validate Python environment**:
   ```bash
   # Check Python version
   python3 --version  # Should be 3.9+

   # Check required packages
   python3 -c "import psutil, requests, baml, fastmcp; print('OK')"
   ```

3. **Check project directory**:
   ```bash
   # Ensure you're in project root
   cd /path/to/context-foundry

   # Verify daemon.py exists
   ls -la tools/evolution/daemon.py
   ```

4. **Check permissions**:
   ```bash
   # Logs directory should be writable
   ls -ld ~/.context-foundry/evolution/logs

   # Database should be accessible
   ls -la ~/.context-foundry/evolution/task_queue.db
   ```

### Service Crashes Immediately

1. **Check for port conflicts**: Ensure no other daemon is running
   ```bash
   python3 -m tools.evolution.daemon status
   ```

2. **Check database integrity**:
   ```bash
   sqlite3 ~/.context-foundry/evolution/task_queue.db "PRAGMA integrity_check;"
   ```

3. **Review recent changes**: Check git status for uncommitted changes
   ```bash
   git status
   git diff
   ```

### High CPU/Memory Usage

1. **Check resource manager logs**:
   ```bash
   grep "Resource usage" ~/.context-foundry/evolution/logs/daemon.log
   ```

2. **Check running Claude processes**:
   ```bash
   ps aux | grep claude
   ```

3. **Review active tasks**:
   ```bash
   python3 -c "
   from tools.evolution.task_queue import TaskQueueManager
   tq = TaskQueueManager()
   for task in tq.list_tasks(status='running'):
       print(f'{task.id}: {task.type} - {task.params}')
   "
   ```

### Service Won't Stop

1. **Force unload** (macOS):
   ```bash
   launchctl remove dev.contextfoundry.evolution
   ```

2. **Force stop** (Linux):
   ```bash
   systemctl --user kill context-foundry-evolution
   ```

3. **Kill process directly** (last resort):
   ```bash
   pkill -f "tools.evolution.daemon"
   ```

### Logs Growing Too Large

Log rotation is automatic (10MB per file, 5 backups), but you can manually clean:

```bash
# Remove old rotated logs
rm ~/.context-foundry/evolution/logs/daemon.log.*

# Truncate current log (daemon must be stopped)
bash scripts/service.sh stop
: > ~/.context-foundry/evolution/logs/daemon.log
bash scripts/service.sh start
```

## Advanced Configuration

### Environment Variables

Add custom environment variables to the service configuration:

**macOS (edit plist)**:
```xml
<key>EnvironmentVariables</key>
<dict>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    <key>HOME</key>
    <string>/Users/yourname</string>
    <!-- Add custom variables -->
    <key>ANTHROPIC_API_KEY</key>
    <string>your-key-here</string>
    <key>GITHUB_TOKEN</key>
    <string>your-token-here</string>
</dict>
```

**Linux (edit service file)**:
```ini
[Service]
Environment="PATH=/usr/local/bin:/usr/bin:/bin"
Environment="HOME=/home/yourname"
# Add custom variables
Environment="ANTHROPIC_API_KEY=your-key-here"
Environment="GITHUB_TOKEN=your-token-here"
```

After editing, reload:
```bash
# macOS
launchctl unload ~/Library/LaunchAgents/dev.contextfoundry.evolution.plist
launchctl load ~/Library/LaunchAgents/dev.contextfoundry.evolution.plist

# Linux
systemctl --user daemon-reload
systemctl --user restart context-foundry-evolution
```

### Resource Limits

Adjust CPU/memory limits in the daemon configuration:

**Edit**: `~/.context-foundry/evolution/config.json`
```json
{
  "resources": {
    "max_cpu_percent": 80,
    "max_memory_gb": 16,
    "active_hours": [6, 22]
  }
}
```

Reload configuration without restart:
```bash
# Send SIGHUP signal to reload config
pkill -HUP -f "tools.evolution.daemon"
```

### Custom Polling Interval

Change how often the daemon checks for new tasks:

**Edit**: `~/.context-foundry/evolution/config.json`
```json
{
  "daemon": {
    "poll_interval_seconds": 60,
    "max_concurrent_tasks": 1
  }
}
```

### Running Multiple Daemons

**Not recommended** for normal use, but possible for testing:

```bash
# Stop managed service first
bash scripts/service.sh stop

# Run daemon in foreground with custom config
python3 -m tools.evolution.daemon start --foreground --config /path/to/custom/config.json
```

## Migration from Manual Start

If you were previously running the daemon manually:

1. **Stop manual daemon**:
   ```bash
   python3 -m tools.evolution.daemon stop
   ```

2. **Install service**:
   ```bash
   bash scripts/install_service.sh
   ```

3. **Verify service is running**:
   ```bash
   bash scripts/service.sh status
   ```

Your database and logs will be preserved in `~/.context-foundry/evolution/`.

## Uninstalling

To completely remove the daemon service:

```bash
# Uninstall service
bash scripts/service.sh uninstall

# Optional: Remove database and logs
rm -rf ~/.context-foundry/evolution/
```

## Next Steps

- **Monitor daemon activity**: `bash scripts/service.sh monitor`
- **Review logs regularly**: `bash scripts/service.sh logs`
- **Approve GitHub issues**: The daemon will implement approved issues automatically
- **Review PRs**: Human approval required before merging

For more information:
- [Evolution System Documentation](../README.md)
- [Task Queue Documentation](../tools/evolution/README.md)
- [MCP Integration Guide](./MCP_INTEGRATION.md)
