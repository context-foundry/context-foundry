# Context Foundry Evolution System

The Evolution System enables Context Foundry to autonomously improve itself by:
- 🔍 Scanning the codebase for issues (Scout)
- 🤖 AI-analyzing findings through 6 expert perspectives
- 📋 Creating GitHub issues following Context Foundry standards
- ✅ Polling for approved issues
- 🚀 Autonomously implementing approved improvements via MCP

## Quick Start

### Start the Evolution Daemon

```bash
# Start the daemon in the background
python3 -m tools.evolution.daemon start

# Or run in foreground to see output
python3 -m tools.evolution.daemon start --foreground
```

### Web Dashboard

The web dashboard runs via Docker on port 8421:

```bash
# Start the dashboard
docker-compose up -d

# Stop the dashboard
docker-compose down

# Rebuild after changes to cf.html
docker-compose build && docker-compose up -d
```

Access the dashboard at: http://localhost:8421/

### Monitor the System

```bash
# Run the real-time monitor dashboard
tools/evolution/scripts/watch-evolution.sh
```

The monitor shows:
- Executive status (what's happening right now)
- Claude instances (interactive vs daemon-spawned)
- Daemon status and recent logs
- MCP delegation status
- Network activity
- Recent file changes
- Git status
- Open pull requests

### Check Daemon Status

```bash
# Check if daemon is running
python3 -m tools.evolution.daemon status

# Stop the daemon
python3 -m tools.evolution.daemon stop

# Restart the daemon
python3 -m tools.evolution.daemon restart
```

## How It Works

### 1. Backlog Management (Scout + AI)

The system maintains a 5-issue backlog:

```bash
# Manually run backlog maintenance
python3 -m tools.evolution.autonomous maintain
```

**Process:**
1. Scout scans codebase (finds 300+ potential issues)
2. AI analyzes top 30 findings through 6 expert lenses:
   - 🔒 Security Analyst
   - ⚙️ DevOps Engineer
   - 📊 Functional Consultant
   - 💼 Business SME
   - 👨‍💻 Developer
   - 🏗️ Architect
3. AI filters to 5-10 high-priority issues (scored 0-10)
4. Issues created using Context Foundry template
5. Backlog maintained at 5 open issues

### 2. Issue Approval Workflow

Human approves issues by adding the `approved` label:

```bash
# View issues awaiting approval
gh issue list --label auto-generated

# Approve an issue
gh issue edit <number> --add-label approved
```

### 3. Autonomous Implementation

The daemon polls GitHub every cycle:

1. **Detects** approved issues
2. **Creates** task with priority 10 (higher than self-generated)
3. **Delegates** to Context Foundry MCP for implementation
4. **MCP spawns** Claude CLI to autonomously implement
5. **Creates** PR when done
6. **Links** PR to issue with "Fixes #<number>"

## System Components

### Daemon (`tools/evolution/daemon.py`)

Main orchestrator that:
- Polls GitHub for approved issues
- Manages task queue
- Delegates to MCP for implementation
- Monitors resource usage

**Service Management:**

```bash
# macOS (launchd)
launchctl load ~/Library/LaunchAgents/com.context-foundry.evolution.plist
launchctl unload ~/Library/LaunchAgents/com.context-foundry.evolution.plist

# Linux (systemd)
systemctl --user start context-foundry-evolution
systemctl --user stop context-foundry-evolution
systemctl --user status context-foundry-evolution
```

### Scout Agent (`tools/evolution/agents/scout_agent.py`)

AI-powered code scanner:
- Runs 15 different scanners (security, performance, tests, etc.)
- Uses Claude CLI to analyze findings
- Provides multi-perspective scoring

**Run manually:**

```bash
python3 -m tools.evolution.agents.scout_agent
```

### Backlog Generator (`tools/evolution/backlog_generator.py`)

Creates GitHub issues:
- Uses Context Foundry issue template
- Includes AI analysis and expert perspectives
- Validates labels before creation
- Maintains 5-issue backlog

### Task Queue (`tools/evolution/task_queue.py`)

SQLite-based task management:
- Prioritizes GitHub-approved tasks (priority 10)
- Falls back to self-generated tasks
- Tracks task status (pending/running/completed/failed)

**Database location:** `~/.context-foundry/evolution/task_queue.db`

## Configuration

### Issue Template

Located at: `tools/evolution/templates/github_issue_template.md`

Includes:
- Metadata (Type, Priority, Category, Effort, File)
- Problem description
- AI analysis with expert perspectives
- Implementation plan checklist

### GitHub Labels

Required labels (auto-created if missing):
- `approved` - Human-approved for implementation
- `auto-generated` - Created by Evolution system
- `security`, `bug`, `enhancement`, `performance`, `technical-debt`
- `p0`, `p1`, `p2`, `p3`, `p4`

### Active Hours & Resource Limits

The daemon includes safety features to prevent runaway builds:

**Active Hours** (default: 6 AM - 10 PM):
- Tasks are only started during configured active hours
- Prevents autonomous builds from consuming resources overnight
- Default window: `[6, 22]` (6:00 AM to 10:00 PM)

**Why?** Autonomous builds can take 30-60 minutes and consume significant resources. The active hours window ensures builds only run during business hours when you can monitor them.

**To extend active hours**, create `~/.context-foundry/evolution/config.json`:

```json
{
  "daemon": {
    "max_concurrent_tasks": 1
  },
  "resources": {
    "max_cpu_percent": 80,
    "max_memory_gb": 16,
    "active_hours": [0, 24]
  }
}
```

Then restart the daemon:
```bash
python3 -m tools.evolution.daemon stop
python3 -m tools.evolution.daemon start
```

**Resource limits:**
- `max_cpu_percent`: Daemon won't start tasks if CPU exceeds this (default: 80%)
- `max_memory_gb`: Daemon won't start tasks if memory exceeds this (default: 16GB)
- `active_hours`: Time window [start_hour, end_hour] in 24-hour format

## Monitoring & Debugging

### View Logs

```bash
# Daemon log
tail -f ~/.context-foundry/evolution/logs/daemon.log

# Task queue
sqlite3 ~/.context-foundry/evolution/task_queue.db "SELECT * FROM tasks ORDER BY created_at DESC LIMIT 10;"
```

### Check MCP Delegation Status

The monitor shows active MCP delegations, or check manually:

```bash
# List active delegations
python3 -c "
import sys
sys.path.insert(0, '/Users/name/homelab/context-foundry')
from tools.mcp_server import list_delegations
print(list_delegations())
"
```

### Check GitHub Issue Backlog

```bash
# Count open issues
gh issue list --state open --json number | jq '. | length'

# List auto-generated issues
gh issue list --label auto-generated

# List approved issues
gh issue list --label approved
```

## Workflow Examples

### Example 1: Let Evolution Find and Fix Issues

1. Start the daemon: `python3 -m tools.evolution.daemon start`
2. Wait for backlog generation (happens automatically)
3. Review auto-generated issues on GitHub
4. Approve an issue: `gh issue edit <number> --add-label approved`
5. Daemon picks it up and delegates to MCP
6. Claude implements autonomously
7. Review the PR created
8. Merge the PR

### Example 2: Manual Backlog Refresh

```bash
# Run Scout and create new issues
python3 -m tools.evolution.autonomous maintain

# Review the issues created
gh issue list --label auto-generated --limit 10

# Approve high-priority ones
gh issue edit 123 --add-label approved
gh issue edit 124 --add-label approved
```

### Example 3: Monitor Active Work

```bash
# Run the monitor
tools/evolution/scripts/watch-evolution.sh

# You'll see:
# - Current status (what's happening)
# - Claude instances working
# - MCP delegation progress
# - Recent file changes
# - Git status
```

## Troubleshooting

### Daemon won't start

```bash
# Check if already running
ps aux | grep "tools.evolution.daemon"

# Check logs
tail -50 ~/.context-foundry/evolution/logs/daemon.log

# Restart
python3 -m tools.evolution.daemon restart
```

### Issues not being created

```bash
# Test Scout manually
python3 -m tools.evolution.agents.scout_agent

# Test backlog generator
python3 -m tools.evolution.backlog_generator maintain

# Check GitHub CLI authentication
gh auth status
```

### MCP not delegating

```bash
# Check MCP server is accessible
python3 -c "
import sys
sys.path.insert(0, '/Users/name/homelab/context-foundry')
from tools.mcp_server import context_foundry_status
print(context_foundry_status())
"

# Check task queue
sqlite3 ~/.context-foundry/evolution/task_queue.db "SELECT status, COUNT(*) FROM tasks GROUP BY status;"
```

### Claude not spawning

Check the monitor's "CLAUDE INSTANCES" section. Daemon-spawned instances:
- Have state containing 'N' (nice/low priority)
- Run with no TTY (??)

If not appearing:
1. Check daemon logs
2. Verify MCP delegation status
3. Check Claude CLI is installed: `which claude`

### Status command shows permission errors

**Symptom:** Running `python3 -m tools.evolution.daemon status` prints:
```
/bin/ps: Operation not permitted
Daemon is running (PID: 73938)
  Note: Process running (macOS denied signal permission - this is normal)
```

**Cause:** This occurs in Homebrew-managed shells where:
1. Homebrew's `shellenv.sh` initialization script tries to run `/bin/ps` but lacks permission
2. macOS security restrictions prevent signaling processes, even your own

**Solution:** This is **expected behavior** in restricted shell environments. The command still works correctly - it reports the daemon status accurately. The permission errors are harmless warnings from shell initialization.

**Workarounds:**
```bash
# Suppress stderr to hide the noise
python3 -m tools.evolution.daemon status 2>/dev/null

# Or use the verbose flag to see explanatory notes
python3 -m tools.evolution.daemon status --verbose
```

The daemon itself runs fine; only the status check is noisy in these environments.

## Architecture

```
Evolution System
├── Daemon (orchestrator)
│   ├── Polls GitHub for approved issues
│   ├── Manages task queue
│   └── Delegates to MCP
├── Scout Agent (scanner)
│   ├── 15 different scanners
│   ├── AI analysis via Claude CLI
│   └── Multi-perspective scoring
├── Backlog Generator
│   ├── Formats issues
│   ├── Creates via gh CLI
│   └── Maintains 5-issue backlog
├── MCP Integration
│   ├── autonomous_build_and_deploy
│   ├── Spawns Claude CLI
│   └── Handles implementation
└── Task Queue (SQLite)
    ├── Priority-based
    ├── Status tracking
    └── GitHub issue linking
```

## Files & Directories

```
tools/evolution/
├── README.md                          # This file
├── daemon.py                          # Main orchestrator
├── task_queue.py                      # Task management
├── backlog_generator.py               # Issue creator
├── autonomous/                        # Backlog maintenance module
│   ├── __init__.py
│   └── __main__.py
├── agents/
│   └── scout_agent.py                 # AI-powered code scanner
├── templates/
│   └── github_issue_template.md      # Issue format
└── scripts/
    └── watch-evolution.sh             # Real-time monitor

~/.context-foundry/evolution/
├── task_queue.db                      # SQLite database
└── logs/
    └── daemon.log                     # Daemon output
```

## Next Steps

After starting the system:

1. **Monitor**: Run `tools/evolution/scripts/watch-evolution.sh`
2. **Check backlog**: `gh issue list --label auto-generated`
3. **Approve issues**: Add `approved` label to high-priority issues
4. **Watch it work**: Monitor shows Claude spawning and implementing
5. **Review PRs**: Check GitHub for autonomously-created PRs
6. **Merge**: Complete the improvement cycle

## Support

For issues or questions:
- Check logs: `~/.context-foundry/evolution/logs/daemon.log`
- Run monitor: `tools/evolution/scripts/watch-evolution.sh`
- GitHub issues: https://github.com/context-foundry/context-foundry/issues
