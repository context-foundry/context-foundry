# Context Foundry Upgrade Guide

This guide provides step-by-step instructions for upgrading Context Foundry between versions.

---

## Quick Upgrade (2.2.0 → 2.3.0)

**TL;DR:** Pull latest code, update dependencies, start daemon. Everything else auto-migrates.

```bash
# 1. Update code
cd ~/homelab/context-foundry  # or your installation path
git pull origin main

# 2. Activate virtual environment
source venv/bin/activate

# 3. Update dependencies
pip install -r requirements-mcp.txt --upgrade

# 4. Start the CF Daemon (NEW requirement in v2.3.0)
./tools/cfd start

# 5. Verify daemon is running
./tools/cfd status

# 6. Test with Claude Code
claude
# In Claude: "Build a simple hello world app"
```

**That's it!** Pattern migration happens automatically on first use.

---

## Detailed Upgrade Instructions

### Version 2.2.0 → 2.3.0

**Release Date:** November 2025

**New Features:**
- 🎮 Glass Pane Dashboard - Mission Control TUI
- 🧠 Intelligent Parallel Detection - AI decides optimal parallelization
- 📚 Context Codex Database - SQLite-backed knowledge system
- ✨ CF Daemon - Background service for persistent job management

#### Prerequisites

- Python 3.10 or higher
- Existing Context Foundry 2.2.0 installation
- Claude Code CLI

#### Step-by-Step Upgrade

**1. Backup Your Patterns (Optional but Recommended)**

```bash
# Backup existing patterns to a safe location
cp -r ~/.context-foundry/patterns ~/.context-foundry/patterns-backup-$(date +%Y%m%d)
```

**2. Update the Code**

```bash
cd ~/homelab/context-foundry  # or wherever you installed CF

# Stash any local changes (if you have any)
git stash

# Pull latest version
git pull origin main

# Reapply local changes if needed
git stash pop
```

**3. Update Dependencies**

```bash
# Activate virtual environment (CRITICAL!)
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Verify you see (venv) in your prompt

# Update dependencies
pip install -r requirements-mcp.txt --upgrade

# Verify installation
python -c "from fastmcp import FastMCP; print('✅ Dependencies updated!')"
```

**4. Start the CF Daemon**

```bash
# Start the daemon (required for v2.3.0+)
./tools/cfd start

# Verify it's running
./tools/cfd status
```

Expected output:
```
CF Daemon is running (PID: 12345)
Jobs: 0 queued, 0 running, 0 completed
```

**5. Automatic Pattern Migration**

No action needed! When you first use Context Codex:

- JSON files in `~/.context-foundry/patterns/` automatically migrate to `~/.context-foundry/codex.db`
- **Original JSON files kept for backup** - nothing is deleted
- Migration happens transparently on first codex query or autonomous build
- You'll see a log message: "Migrating patterns from JSON to database..."

**6. Verify Everything Works**

```bash
# Restart Claude Code
claude

# Test with a simple build
# In Claude: "Build a simple calculator app"

# Or test daemon directly
cfd submit --type building --params '{"task": "Build a todo app", "working_directory": "/tmp/test-upgrade"}'

# Monitor with
cfd list
```

#### What Changes in 2.3.0

**New Capabilities:**
- ✅ Background job service (CF Daemon) for persistent builds
- ✅ Intelligent parallel detection (Scout analyzes and decides)
- ✅ Database-backed knowledge system (SQLite with full-text search)
- ✅ Glass Pane Dashboard (`cf mission-control` command)
- ✅ Working directory locking (prevents concurrent build conflicts)

**Backward Compatible:**
- ❌ **No MCP config changes** - `.mcp.json` works as-is
- ❌ **No workflow changes** - same MCP tools, enhanced reliability
- ❌ **No project changes** - all `.context-foundry/` artifacts compatible

**Breaking Changes:**
- ⚠️ **CF Daemon required** - Must run `./tools/cfd start` before autonomous builds
- ⚠️ **Pattern storage** - Migrates from JSON files to SQLite database (automatic)

#### Troubleshooting

**Issue: Daemon won't start**
```bash
# Check if already running
./tools/cfd status

# Stop and restart
./tools/cfd stop
./tools/cfd start

# Check logs
cat ~/.context-foundry/cfd/daemon.log
```

**Issue: Pattern migration failed**
```bash
# Check database
ls -lh ~/.context-foundry/codex.db

# View migration logs
cat ~/.context-foundry/codex-migration.log

# Restore from backup if needed
rm ~/.context-foundry/codex.db
# Patterns will re-migrate from JSON backup on next use
```

**Issue: MCP tools not working**
```bash
# Verify daemon is running
./tools/cfd status

# Restart Claude Code
# Exit current session and run: claude
```

---

### Version 2.1.x → 2.2.0

**Release Date:** October 2025

**New Features:**
- Agent Quality Enhancements (back pressure, context budgets, tool quality, semantic tags)

#### Upgrade Steps

```bash
# 1. Update code
cd ~/homelab/context-foundry
git pull origin main

# 2. Activate venv
source venv/bin/activate

# 3. Update dependencies
pip install -r requirements-mcp.txt --upgrade

# 4. Restart Claude Code
claude
```

**Breaking Changes:** None - fully backward compatible

---

### Version 2.0.x → 2.1.0

**Release Date:** October 2025

**New Features:**
- Enhancement modes (fix_bug, add_feature, upgrade_deps, refactor, add_tests)
- Phase 0: Codebase Analysis
- Intelligent project detection (15+ project types)

#### Upgrade Steps

```bash
# 1. Update code
cd ~/homelab/context-foundry
git pull origin main

# 2. Activate venv
source venv/bin/activate

# 3. Update dependencies
pip install -r requirements-mcp.txt --upgrade

# 4. Restart Claude Code
claude
```

**What's New:**
- Can now enhance existing codebases (not just new projects)
- Automatic detection of Python, Node.js, Rust, Go, Java, Ruby, PHP, .NET, etc.
- Feature branch + Pull Request workflow for enhancements

**Breaking Changes:** None - new project mode works exactly as before

---

### Version 1.x → 2.0

**Release Date:** October 2025

**Major Architectural Change:** Python CLI → MCP Server for Claude Code

This is a **major upgrade** with significant architectural changes. See [ARCHITECTURE_DECISIONS.md](docs/ARCHITECTURE_DECISIONS.md) for complete details.

#### Migration Overview

**What's Changing:**
- **Orchestration:** Python scripts → Meta-prompts (AI self-orchestration)
- **Installation:** `pip install` → MCP server setup
- **Usage:** `foundry` CLI → Claude Code MCP tools
- **Cost Model:** Pay-per-use API → Claude Max subscription

**Who Should Upgrade:**
- ✅ Heavy users (5+ projects/month) - 95% cost savings
- ✅ Those wanting autonomous builds - walk away builds
- ✅ Claude Code users - native integration

**Who Should Stay on 1.x:**
- ⚠️ Multi-provider users (OpenAI, Gemini, Groq, etc.)
- ⚠️ Occasional users (< 5 projects/month) - may be more expensive
- ⚠️ Those preferring checkpoints over full autonomy

#### Detailed Migration Steps

**1. Backup Your v1.x Installation**

```bash
# Clone v1.x to a safe location
cp -r ~/homelab/context-foundry ~/homelab/context-foundry-v1-backup

# Or checkout v1.x branch
cd ~/homelab/context-foundry
git checkout v1.x-legacy
```

**2. Fresh Installation of v2.0**

```bash
# Clone v2.0 to new directory
cd ~/homelab
git clone https://github.com/context-foundry/context-foundry.git context-foundry-v2
cd context-foundry-v2

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements-mcp.txt
```

**3. Configure MCP Server**

```bash
# Add to Claude Code
claude mcp add --transport stdio context-foundry -s project -- $(pwd)/venv/bin/python $(pwd)/tools/mcp_server.py

# Verify configuration
cat .mcp.json

# Start Claude Code
claude
```

**4. Workflow Changes**

| v1.x (Old) | v2.0 (New) |
|------------|------------|
| `foundry build my-app "task"` | In Claude Code: `Use mcp__autonomous_build_and_deploy with task: "task", working_directory: "/path/to/my-app"` |
| `foundry fix my-app "bug"` | In Claude Code: `Use mcp__autonomous_build_and_deploy with mode: "fix_bug", task: "bug"...` |
| `foundry status` | In Claude Code: `Use mcp__list_delegations` |

**5. Verify Migration**

```bash
# Test with simple build
claude
# In Claude: "Build a simple todo app"

# Check results
ls /tmp/todo-app/.context-foundry/
# Should see: scout-report.md, architecture.md, build-log.md, test-final-report.md
```

#### Data Migration

**Pattern Library:**
- v1.x pattern library is **not compatible** with v2.0
- v2.0 learns patterns automatically through Phase 7: Feedback
- Old patterns can be manually ported if needed

**Session Data:**
- v1.x session data in `.context-foundry/` format is **different** from v2.0
- Start fresh with v2.0 - no automatic migration

**Cost Comparison:**

| Usage Level | v1.x (API) | v2.0 (Subscription) | Recommendation |
|-------------|-----------|---------------------|----------------|
| 1-2 projects/month | $3-10 | $20/month | Stay on v1.x |
| 5 projects/month | $15-50 | $20/month | ✅ Upgrade to v2.0 |
| 10+ projects/month | $30-100+ | $20/month | ✅ Upgrade to v2.0 |
| Unlimited | $100-1000+ | $20/month | ✅ Upgrade to v2.0 |

---

## Version Compatibility Matrix

| From Version | To Version | Complexity | Breaking Changes | Data Migration |
|--------------|-----------|-----------|------------------|----------------|
| 2.2.0 | 2.3.0 | ⭐ Easy | Daemon required | ✅ Automatic |
| 2.1.x | 2.2.0 | ⭐ Easy | None | None |
| 2.0.x | 2.1.0 | ⭐ Easy | None | None |
| 1.x | 2.0 | ⭐⭐⭐⭐ Complex | Major | ❌ Manual |

---

## Rollback Procedures

### Rollback 2.3.0 → 2.2.0

```bash
cd ~/homelab/context-foundry

# Stop daemon
./tools/cfd stop

# Checkout v2.2.0
git fetch --tags
git checkout v2.2.0

# Reinstall dependencies
source venv/bin/activate
pip install -r requirements-mcp.txt

# Restart Claude Code
claude
```

**Pattern Data:**
- Codex database at `~/.context-foundry/codex.db` will be ignored
- Original JSON backups at `~/.context-foundry/patterns/*.json` still work in v2.2.0

### Rollback 2.0+ → 1.x

```bash
# Download v1.x
git clone https://github.com/context-foundry/context-foundry.git context-foundry-v1
cd context-foundry-v1
git checkout v1.x-legacy

# Install v1.x dependencies
pip install -r requirements.txt

# Use v1.x CLI
foundry --version
```

---

## Common Upgrade Issues

### Issue: Virtual Environment Not Activated

**Symptom:**
```
ERROR: externally-managed-environment
```

**Solution:**
```bash
# ALWAYS activate venv before pip install
source venv/bin/activate

# Verify - you should see (venv) in prompt
# (venv) user@computer:~/context-foundry$
```

### Issue: Daemon Already Running

**Symptom:**
```
Error: Daemon already running (PID: 12345)
```

**Solution:**
```bash
# Check status
./tools/cfd status

# Restart if needed
./tools/cfd stop
./tools/cfd start
```

### Issue: MCP Server Failed After Upgrade

**Symptom:**
```
Context-foundry MCP Server
Status: ✘ failed
```

**Solution:**
```bash
cd ~/homelab/context-foundry
source venv/bin/activate
pip install -r requirements-mcp.txt --upgrade

# Verify
python -c "from fastmcp import FastMCP; print('✅ Success!')"

# Restart Claude Code
```

### Issue: Pattern Migration Stuck

**Symptom:**
```
Migration has been running for 5+ minutes
```

**Solution:**
```bash
# Check process
ps aux | grep codex

# If stuck, kill and restart
pkill -f codex

# Patterns will auto-migrate on next use
```

---

## FAQ

### Do I need to upgrade?

**For 2.2.0 users → 2.3.0:**
- **Recommended:** Yes - daemon improves reliability, parallel detection speeds up builds
- **Required:** Only if you want Glass Pane dashboard or intelligent parallelization

**For 2.0-2.1 users → Latest:**
- **Recommended:** Yes - cumulative improvements in quality and features
- **Required:** No - older versions still work

**For 1.x users → 2.x:**
- **Recommended:** If you build 5+ projects/month (95% cost savings)
- **Required:** No - 1.x still maintained in `v1.x-legacy` branch

### Will I lose my pattern data?

**No** - all upgrade paths preserve data:
- **2.2.0 → 2.3.0:** Automatic migration + JSON backups kept
- **2.1.x → 2.2.0:** No data changes
- **2.0.x → 2.1.0:** No data changes
- **1.x → 2.0:** Different format, but v1.x patterns can be manually ported

### Can I run multiple versions?

**Yes!** Install in separate directories:
```bash
~/homelab/context-foundry-v1/  # v1.x installation
~/homelab/context-foundry-v2/  # v2.x installation
```

Each version has its own:
- Virtual environment
- MCP configuration
- Pattern storage

### How long does the upgrade take?

- **2.2.0 → 2.3.0:** 2-3 minutes
- **2.1.x → 2.2.0:** 1-2 minutes
- **2.0.x → 2.1.0:** 1-2 minutes
- **1.x → 2.0:** 10-15 minutes (fresh installation + learning curve)

### What if the upgrade fails?

1. **Don't panic** - your old version still works
2. **Check logs:** `cat ~/.context-foundry/cfd/daemon.log`
3. **Rollback** - use procedures in "Rollback Procedures" section
4. **Report issue:** https://github.com/context-foundry/context-foundry/issues

---

## Getting Help

- **Documentation:** [README.md](README.md), [USER_GUIDE.md](docs/USER_GUIDE.md)
- **Issues:** https://github.com/context-foundry/context-foundry/issues
- **Discussions:** https://github.com/context-foundry/context-foundry/discussions
- **Troubleshooting:** [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)

---

## Release Notes

For detailed release notes and changelogs:
- **[CHANGELOG.md](CHANGELOG.md)** - Complete version history
- **[GitHub Releases](https://github.com/context-foundry/context-foundry/releases)** - Download specific versions

---

**Last Updated:** November 2025 (v2.3.0)

**Maintained By:** Context Foundry Team
