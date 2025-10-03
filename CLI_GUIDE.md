# Context Foundry CLI Guide

Complete guide to using the `foundry` command-line interface.

## Installation

```bash
# Install in development mode (recommended)
pip install -e .

# Or install normally
pip install .
```

This makes the `foundry` command available globally.

## Quick Start

```bash
# Initialize configuration
foundry config --init

# Set your API key in .env
export ANTHROPIC_API_KEY=your_key_here

# Build your first project
foundry build my-app "Build a CLI todo app in Python"
```

## Commands

### `foundry build` - Build a Project

Start a new Context Foundry build with the Scout → Architect → Builder workflow.

**Usage:**
```bash
foundry build PROJECT TASK [OPTIONS]
```

**Arguments:**
- `PROJECT` - Project name (used for directory and session ID)
- `TASK` - Task description (what to build)

**Options:**
- `--autonomous` - Skip human review checkpoints (full auto-pilot)
- `--livestream` - Enable real-time dashboard at http://localhost:8765
- `--overnight HOURS` - Schedule overnight run (e.g., `--overnight 8`)
- `--use-patterns` / `--no-patterns` - Enable/disable pattern injection (default: enabled)
- `--context-manager` / `--no-context-manager` - Enable/disable smart context management (default: enabled)
- `--project-dir PATH` - Custom project directory

**Examples:**

```bash
# Interactive build with human reviews
foundry build my-app "Build user authentication with JWT"

# Autonomous build (no reviews)
foundry build api-server "REST API with PostgreSQL" --autonomous

# Overnight session (8 hours)
foundry build ml-pipeline "Data pipeline with validation" --overnight 8

# With livestream dashboard
foundry build web-app "Todo app with React" --livestream

# Custom project directory
foundry build webapp "E-commerce site" --project-dir ~/projects/shop
```

**Workflow Phases:**

1. **Scout** (Research)
   - Explores architecture options
   - Researches best practices
   - Produces research artifact (~5K tokens)
   - Target: <30% context usage

2. **Architect** (Planning)
   - Creates specifications
   - Generates technical plan
   - Breaks into atomic tasks
   - **Human review checkpoint** (unless `--autonomous`)
   - Target: <40% context usage

3. **Builder** (Implementation)
   - Executes tasks sequentially
   - Test-driven development
   - Automatic context compaction
   - Git commits after each task
   - Target: <50% context usage

---

### `foundry status` - Check Progress

Monitor current or past session progress.

**Usage:**
```bash
foundry status [OPTIONS]
```

**Options:**
- `--session ID` - Check specific session
- `--all` - Show all sessions (last 10)
- `--watch` - Watch mode (auto-refresh every 5s)

**Examples:**

```bash
# Show latest session
foundry status

# Show specific session
foundry status --session my-app_20251002_210000

# Show all sessions
foundry status --all

# Watch mode (live updates)
foundry status --watch
```

**Output:**
- Session ID and project name
- Current phase (scout/architect/builder)
- Progress percentage
- Completed tasks
- Remaining tasks
- Context usage statistics

---

### `foundry patterns` - Manage Pattern Library

Manage the reusable pattern library that learns from successful builds.

**Usage:**
```bash
foundry patterns [OPTIONS]
```

**Options:**
- `--list` - List top patterns
- `--search QUERY` - Search patterns by description/code
- `--add FILE` - Add pattern from file
- `--rate ID RATING` - Rate pattern (1-5 stars)
- `--top N` - Show top N patterns (default: 10)
- `--stats` - Show library statistics

**Examples:**

```bash
# Show top patterns
foundry patterns --list

# Search for patterns
foundry patterns --search "authentication JWT"

# Show statistics
foundry patterns --stats

# Add pattern from file
foundry patterns --add ./auth_pattern.py

# Rate a pattern
foundry patterns --rate 42 5
```

**Pattern Library Features:**
- Semantic search using embeddings
- Success rate tracking
- Usage statistics
- Automatic injection into builds

---

### `foundry analyze` - Analyze Sessions

Post-session analysis for metrics and continuous improvement.

**Usage:**
```bash
foundry analyze [SESSION] [OPTIONS]
```

**Arguments:**
- `SESSION` - Session ID (optional, uses latest if not specified)

**Options:**
- `--format FORMAT` - Output format: text, json, markdown (default: text)
- `--save FILE` - Save report to file

**Examples:**

```bash
# Analyze latest session
foundry analyze

# Analyze specific session
foundry analyze my-app_20251002_210000

# Save as markdown report
foundry analyze --format markdown --save report.md

# JSON output
foundry analyze --format json
```

**Analysis Includes:**
- Completion rate
- Task breakdown
- Token usage statistics
- Estimated cost
- Context efficiency
- Pattern usage
- Time metrics

---

### `foundry config` - Manage Configuration

Configure Context Foundry settings and profiles.

**Usage:**
```bash
foundry config [OPTIONS]
```

**Options:**
- `--init` - Initialize .env configuration file
- `--show` - Show current configuration
- `--set KEY VALUE` - Set configuration value

**Examples:**

```bash
# Initialize .env file
foundry config --init

# Show current config
foundry config --show

# Set a value
foundry config --set CLAUDE_MODEL claude-sonnet-4-20250514
```

**Configuration Files:**
- `.env` - Environment variables (API keys, etc.)
- `.foundry/config.yaml` - Advanced configuration and profiles

**Key Settings:**
- `ANTHROPIC_API_KEY` - Your Claude API key (required)
- `CLAUDE_MODEL` - Model to use (default: claude-sonnet-4-20250514)
- `MAX_TOKENS` - Max tokens per response (default: 8000)
- `USE_CONTEXT_MANAGER` - Enable context management (default: true)
- `USE_PATTERNS` - Enable pattern injection (default: true)

---

## Configuration Profiles

Context Foundry supports multiple configuration profiles for different use cases.

### Available Presets

**Dev Profile** (Interactive development)
```yaml
autonomous_mode: false
enable_livestream: true
use_context_manager: true
use_patterns: true
git_auto_commit: true
```

**Prod Profile** (Production builds)
```yaml
autonomous_mode: false
enable_livestream: false
use_context_manager: true
use_patterns: true
git_auto_commit: true
```

**Overnight Profile** (Autonomous overnight runs)
```yaml
autonomous_mode: true
enable_livestream: false
use_context_manager: true
use_patterns: true
git_auto_commit: true
context_threshold: 0.35  # More aggressive
```

### Creating Profiles

Edit `.foundry/config.yaml`:

```yaml
current_profile: dev

profiles:
  dev:
    model: claude-sonnet-4-20250514
    autonomous_mode: false
    enable_livestream: true
    use_context_manager: true
    use_patterns: true

  overnight:
    model: claude-sonnet-4-20250514
    autonomous_mode: true
    use_context_manager: true
    context_threshold: 0.35
```

---

## Advanced Features

### Context Management

Automatic context management keeps token usage under 50%:

```bash
# Enable context manager (default)
foundry build my-app "Task" --context-manager

# Disable if you want manual control
foundry build my-app "Task" --no-context-manager
```

**How it works:**
- Tracks context usage in real-time
- Auto-compacts at 40% threshold
- Uses Claude to intelligently summarize
- Preserves critical information:
  - Architecture decisions
  - Patterns identified
  - Current task context
  - Errors to avoid
- Reduces context by 60-70%

### Pattern Library

Learn from successful builds:

```bash
# Enable patterns (default)
foundry build my-app "Task" --use-patterns

# Patterns are:
# - Automatically extracted from successful code
# - Semantically searched for relevance
# - Injected into prompts when appropriate
# - Rated based on success
```

### Overnight Sessions

Long-running autonomous sessions:

```bash
# Schedule 8-hour overnight run
foundry build big-project "Complex task" --overnight 8

# Uses Ralph Wiggum strategy:
# - Same prompt, fresh context each iteration
# - Progress persists via checkpoints
# - Automatic recovery from errors
# - Completion detection
```

### Livestream Dashboard

Real-time build visualization:

```bash
foundry build my-app "Task" --livestream

# Opens dashboard at http://localhost:8765
# Shows:
# - Live progress updates
# - Context usage graphs
# - Task completion
# - Error notifications
```

---

## Troubleshooting

### API Key Issues

```bash
# Check if API key is set
echo $ANTHROPIC_API_KEY

# Set API key
export ANTHROPIC_API_KEY=your_key_here

# Or add to .env
foundry config --init
# Then edit .env file
```

### Session Not Found

```bash
# List all sessions
foundry status --all

# Check session directory
ls -la checkpoints/ralph/
```

### Pattern Library Issues

```bash
# Check pattern database
ls -la foundry/patterns/patterns.db

# View pattern stats
foundry patterns --stats

# Rebuild patterns (if corrupted)
rm foundry/patterns/patterns.db
# Patterns will be re-extracted on next use
```

### Context Usage Too High

```bash
# Context manager should auto-compact at 40%
# If not, check settings:
foundry config --show

# Ensure USE_CONTEXT_MANAGER=true
foundry config --set USE_CONTEXT_MANAGER true
```

---

## Best Practices

### 1. Start with Research Phase

Always review the Scout phase output before proceeding:

```bash
# Interactive mode (recommended for first runs)
foundry build my-app "Task description"

# Review RESEARCH.md before approving
```

### 2. Critical Review at Architect Phase

The Architect phase is your highest leverage point:

```bash
# Review SPEC.md, PLAN.md, and TASKS.md
# Bad plan = thousands of bad lines of code
# Take time to review and approve
```

### 3. Use Patterns for Common Tasks

Build up your pattern library:

```bash
# After successful builds, patterns are auto-extracted
# Rate patterns to improve recommendations
foundry patterns --rate 42 5
```

### 4. Monitor Context Usage

Keep an eye on context health:

```bash
# Watch mode shows real-time context usage
foundry status --watch
```

### 5. Overnight Sessions for Complex Tasks

Use overnight mode for large projects:

```bash
# 8 hours is usually sufficient
foundry build large-project "Complex system" --overnight 8

# Check progress in the morning
foundry status --session large-project_*
foundry analyze --format markdown --save report.md
```

---

## Environment Variables Reference

| Variable | Description | Default |
|----------|-------------|---------|
| `ANTHROPIC_API_KEY` | Claude API key | (required) |
| `CLAUDE_MODEL` | Model to use | `claude-sonnet-4-20250514` |
| `MAX_TOKENS` | Max response tokens | `8000` |
| `USE_CONTEXT_MANAGER` | Enable context management | `true` |
| `USE_PATTERNS` | Enable pattern library | `true` |
| `SMTP_HOST` | SMTP server for notifications | (optional) |
| `SMTP_PORT` | SMTP port | `587` |
| `SMTP_USER` | SMTP username | (optional) |
| `SMTP_PASS` | SMTP password | (optional) |
| `NOTIFICATION_EMAIL` | Email for notifications | (optional) |
| `SLACK_WEBHOOK_URL` | Slack webhook for notifications | (optional) |

---

## Getting Help

```bash
# General help
foundry --help

# Command-specific help
foundry build --help
foundry status --help
foundry patterns --help
foundry analyze --help
foundry config --help
```

---

## Examples Gallery

### Example 1: Simple CLI App

```bash
foundry build todo-cli "Build a CLI todo app with local JSON storage"
```

### Example 2: REST API

```bash
foundry build api-server "REST API with JWT auth, PostgreSQL, and OpenAPI docs" --livestream
```

### Example 3: Web Application

```bash
foundry build webapp "E-commerce site with React frontend and Express backend" --overnight 8
```

### Example 4: Data Pipeline

```bash
foundry build pipeline "ETL pipeline with data validation and error handling" --autonomous
```

### Example 5: Testing a Pattern

```bash
# First, build something and extract patterns
foundry build auth-service "User authentication service"

# Then search for the pattern
foundry patterns --search "authentication"

# Use it in a new project (patterns auto-injected)
foundry build new-app "App with user login" --use-patterns
```

---

## Quick Reference Card

```bash
# Install
pip install -e .

# Setup
foundry config --init
export ANTHROPIC_API_KEY=your_key

# Build
foundry build PROJECT "TASK"                    # Interactive
foundry build PROJECT "TASK" --autonomous       # Auto-pilot
foundry build PROJECT "TASK" --overnight 8      # Overnight

# Monitor
foundry status                                  # Latest session
foundry status --watch                          # Live updates
foundry status --all                            # All sessions

# Patterns
foundry patterns --list                         # Show patterns
foundry patterns --search "QUERY"               # Search
foundry patterns --stats                        # Statistics

# Analyze
foundry analyze                                 # Latest session
foundry analyze SESSION                         # Specific session
foundry analyze --format markdown --save FILE   # Save report

# Config
foundry config --show                           # View config
foundry config --set KEY VALUE                  # Set value
```

---

*For more information, see the main [README.md](README.md) or visit the documentation.*
