# Testing Context Foundry - Quick Start Guide

## Prerequisites

1. Ensure Context Foundry MCP server is configured in Claude Code
2. Python 3.10+ installed
3. Git configured

## Option 1: Test MCP Tools (Recommended First)

### Step 1: Restart Claude Code
Close and restart Claude Code to load the updated MCP server with Context Codex tools.

### Step 2: Test MCP Tools Directly

Once Claude Code restarts, you can test the 5 new Context Codex MCP tools:

```python
# Search the knowledge base
mcp__context-foundry__codex_search("docker volume")

# Get detailed entry info (with new slug IDs and project stats)
mcp__context-foundry__codex_get_entry("iss-docker-volume-123")

# Add an issue to the knowledge base
mcp__context-foundry__codex_add_issue(
    title="Docker volume config issue",
    description="Volumes persist old config",
    severity="MEDIUM",
    tags=["docker", "volumes"],
    project_types=["python", "nodejs"]
)

# Add a pattern/best practice
mcp__context-foundry__codex_add_pattern(
    title="Use environment files for config",
    description="Store configuration in .env files instead of hardcoding",
    category="architecture",
    tags=["best-practice", "configuration"]
)

# View statistics
mcp__context-foundry__codex_stats()
```

### What to Verify:
- ✅ IDs are human-readable slugs (e.g., `iss-docker-volume-123`)
- ✅ Project stats include detailed info (occurrence_count, first_seen, last_seen)
- ✅ Full-text search returns relevant results
- ✅ JSON responses are well-formatted

## Option 2: Build a Test App with Daemon

### Step 1: Start the Evolution Daemon

```bash
cd /Users/name/homelab/context-foundry

# Start daemon in background
./tools/cfd start

# Check daemon status
./tools/cfd status
```

### Step 2: Create a Test Project

Pick a simple project to build. Examples:

**Simple Flask App:**
```bash
mkdir -p /Users/name/homelab/test-flask-app
cd /Users/name/homelab/test-flask-app
```

**Simple Next.js App:**
```bash
mkdir -p /Users/name/homelab/test-nextjs-app
cd /Users/name/homelab/test-nextjs-app
```

### Step 3: Use MCP Tool to Build Autonomously

In Claude Code, use the autonomous build MCP tool:

```python
mcp__context-foundry__autonomous_build_and_deploy(
    task="Build a simple Flask API with /health endpoint and basic error handling",
    working_directory="/Users/name/homelab/test-flask-app",
    mode="new_project",
    timeout_minutes=30
)
```

Or for async (runs in background):

```python
# Start build in background
result = mcp__context-foundry__delegate_to_claude_code_async(
    task="Build a simple Flask API with /health endpoint",
    working_directory="/Users/name/homelab/test-flask-app",
    timeout_minutes=30
)

# Get task ID from result
task_id = "abc-123-def-456"  # Extract from result

# Check status
mcp__context-foundry__get_delegation_result(task_id)

# Stream live output
mcp__context-foundry__stream_delegation_output(task_id, lines=50)
```

### Step 4: Monitor Build Progress

```bash
# In separate terminal, watch daemon logs
./tools/cfd logs --follow

# Or check specific delegation
./tools/cfd logs <task-id>
```

### Step 5: Verify Knowledge Capture

After build completes, check if knowledge was captured:

```python
# Search for patterns learned during build
mcp__context-foundry__codex_search("flask")

# Check project history
# (would need to add this query - get all entries for a specific project_path)

# View overall stats
mcp__context-foundry__codex_stats()
```

## Option 3: CLI Testing (Direct)

### Start Daemon via CLI

```bash
cd /Users/name/homelab/context-foundry

# Start daemon
./tools/cfd start

# Check status
./tools/cfd status

# View logs
./tools/cfd logs --follow
```

### Create Build Task Directly

```bash
# Create evolution task
./tools/cfd create-task \
  --type apply_pattern \
  --target-project /Users/name/homelab/test-app \
  --pattern-id pat-env-config-001

# List tasks
./tools/cfd list-tasks --status pending

# Watch progress
./tools/cfd status
```

## Troubleshooting

### Daemon won't start
```bash
# Check if already running
ps aux | grep cfd

# Kill existing
pkill -f cfd

# Check logs
cat /Users/name/.context-foundry/logs/daemon.log
```

### MCP tools not available
1. Restart Claude Code
2. Verify MCP server config: `~/.config/claude/claude_desktop_config.json`
3. Check server path points to: `/Users/name/homelab/context-foundry/tools/mcp_server.py`

### Build fails
```bash
# Check delegation status
./tools/cfd list-delegations

# View detailed output
./tools/cfd logs <task-id>

# Cancel stuck task
./tools/cfd cancel <task-id>
```

## What Success Looks Like

### MCP Tool Testing:
- ✅ All 5 codex tools respond without errors
- ✅ IDs are human-readable slugs
- ✅ Project stats show detailed occurrence data
- ✅ Search returns relevant results

### Autonomous Build Testing:
- ✅ Daemon starts and shows "running" status
- ✅ Build task creates project files
- ✅ Tests pass automatically
- ✅ Knowledge entries saved to Codex
- ✅ Patterns merged to global storage

## Next Steps

1. **Test MCP Tools First** - Verify Codex integration works
2. **Run Simple Build** - Test autonomous build on trivial project
3. **Check Knowledge Capture** - Verify learnings saved correctly
4. **Test Pattern Application** - Build second project, see if patterns auto-apply

## Reference

- Context Codex DB: `~/.context-foundry/codex.db`
- Global Patterns: `~/.context-foundry/patterns/`
- Daemon Logs: `~/.context-foundry/logs/daemon.log`
- Build Outputs: `.context-foundry/build-output-<task-id>.txt`
