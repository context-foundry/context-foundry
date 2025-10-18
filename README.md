# 🏭 Context Foundry 2.0

> **Autonomous AI Development through Claude Code MCP Integration**
> Scout → Architect → Builder → Test → Deploy. Fully autonomous, self-healing, walk-away development.

**Version 2.0 - October 2025**

---

## What is Context Foundry 2.0?

Context Foundry 2.0 is an **MCP (Model Context Protocol) server** that empowers Claude Code CLI to build complete software projects autonomously with **self-healing test loops** and **automatic GitHub deployment**.

Unlike traditional AI coding tools that require constant supervision, Context Foundry 2.0 lets you describe what you want and **walk away** while it:
- Researches requirements (Scout phase)
- Designs architecture (Architect phase)
- Implements code with tests (Builder phase)
- Auto-fixes test failures (Test phase with self-healing)
- Documents everything (Documentation phase)
- Deploys to GitHub (Deployment phase)

**Real Example:**
```
User: "Build a Mario platformer game in JavaScript"
[User walks away for 7 minutes]
Result: ✅ Complete game deployed to GitHub, all tests passing
```

---

## What's New in 2.0?

### Core Innovations

1. **🔄 Self-Healing Test Loops**
   - Tests fail? System automatically:
     - Analyzes root cause
     - Redesigns solution
     - Re-implements fix
     - Re-tests (up to 3 iterations)
   - No human intervention needed

2. **🤖 Fully Autonomous Workflows**
   - Start a build and walk away
   - Uses Claude Code's native `/agents` feature
   - No API calls, uses Claude Max subscription
   - Complete projects in 7-15 minutes

3. **⚡ Parallel Task Delegation**
   - Spawn multiple Claude instances simultaneously
   - Build backend + frontend + database in parallel
   - 3-10x speedup on multi-component projects

4. **📝 Meta-Prompt Orchestration**
   - AI orchestrates itself through text-based instructions
   - Workflows defined in plain language (no Python code)
   - Easy to customize and extend

5. **📂 File-Based Context Preservation**
   - No token limit issues
   - Context stored in `.context-foundry/` directory
   - Each phase reads from previous artifacts
   - Works across multiple sessions

### What Changed from 1.x?

| Feature | 1.x (Python CLI) | 2.0 (MCP Server) |
|---------|------------------|-------------------|
| **Orchestration** | Python scripts + API calls | Native Claude `/agents` + meta-prompts |
| **Cost Model** | Pay-per-token API | Claude Max subscription ($20/month unlimited) |
| **Testing** | Manual review at checkpoints | Self-healing auto-fix loops |
| **Deployment** | Manual git operations | Automatic GitHub deployment |
| **Tool Access** | Limited to Python functions | Full Claude Code tool suite (Read, Edit, Bash, etc.) |
| **Context** | API conversation history | File-based artifacts (.context-foundry/) |
| **Providers** | 7 AI providers supported | Claude only (optimized for quality) |
| **Complexity** | ~3000 lines of Python | ~1400 lines (MCP + meta-prompt) |

**Want the technical details?** See [ARCHITECTURE_DECISIONS.md](ARCHITECTURE_DECISIONS.md) for comprehensive explanations of what changed and why.

**Using Context Foundry 1.x?** The Python CLI is preserved in `LEGACY_README.md` and still functional.

---

## Quick Start

### Prerequisites

- **Python 3.10 or higher** (for MCP server)
- **Claude Code CLI** installed and in PATH
- **Claude Max subscription** ($20/month) or Anthropic API key
- **Git** and **GitHub CLI** (for deployment features)

### Installation

```bash
# 1. Clone Context Foundry
git clone https://github.com/snedea/context-foundry.git
cd context-foundry

# 2. Install MCP server dependencies (Python 3.10+ required)
pip install -r requirements-mcp.txt

# 3. Configure Claude Code to connect to MCP server
claude mcp add --transport stdio context-foundry -- python3.10 /Users/name/homelab/context-foundry/tools/mcp_server.py

# 4. Verify MCP connection
claude mcp list
# Should show: ✓ Connected: context-foundry

# 5. Authenticate with GitHub (for deployment)
gh auth login
```

**Detailed setup guide:** See [CLAUDE_CODE_MCP_SETUP.md](CLAUDE_CODE_MCP_SETUP.md) for troubleshooting and advanced configuration.

### Basic Usage

Start Claude Code CLI:

```bash
claude-code
```

Inside your Claude Code session:

#### Build a New Project (Autonomous)

```
Use mcp__autonomous_build_and_deploy with:
- task: "Build a weather API with Express.js that fetches data from OpenWeatherMap"
- working_directory: "/tmp/weather-api"
- github_repo_name: "weather-api"
- enable_test_loop: true
```

**What happens:**
1. Scout researches requirements (1-2 min)
2. Architect designs system (1-2 min)
3. Builder implements code + tests (2-5 min)
4. Tester validates (tests fail? auto-fixes up to 3x)
5. Documentation created (1 min)
6. Deployed to GitHub (30 sec)

**Total:** ~7-15 minutes, zero human input required.

#### Delegate a Simple Task

```
Use mcp__delegate_to_claude_code with:
- task: "Create a Python script that fetches weather data and prints it nicely"
- working_directory: "/tmp/weather-script"
```

Returns when complete with full output.

#### Parallel Task Execution

```
Use mcp__delegate_to_claude_code_async to start these tasks in parallel:

Task 1: "Create Flask REST API for user authentication"
  working_directory: "/tmp/project/backend"

Task 2: "Create React frontend with login UI"
  working_directory: "/tmp/project/frontend"

Task 3: "Create PostgreSQL schema and migrations"
  working_directory: "/tmp/project/database"

Then use mcp__list_delegations to monitor progress
And mcp__get_delegation_result to collect results when ready
```

**Time saved:** 3 sequential tasks (30 min) → parallel tasks (10 min) = 3x faster

---

## MCP Tools Reference

### 🚀 `autonomous_build_and_deploy()`

Fully autonomous Scout → Architect → Builder → Test → Deploy workflow.

**Parameters:**
- `task` (required): What to build (e.g., "Build a todo app")
- `working_directory` (required): Where to build it
- `github_repo_name` (optional): Deploy to this GitHub repo
- `existing_repo` (optional): Enhance existing repo instead
- `mode` (default: "new_project"): "new_project" | "fix" | "enhance"
- `enable_test_loop` (default: true): Enable self-healing when tests fail
- `max_test_iterations` (default: 3): Max auto-fix attempts
- `timeout_minutes` (default: 90.0): Total timeout

**Returns:** JSON with status, files created, test results, GitHub URL, etc.

**Example:**
```python
{
  "status": "completed",
  "phases_completed": ["scout", "architect", "builder", "test", "docs", "deploy"],
  "github_url": "https://github.com/snedea/weather-api",
  "files_created": ["server.js", "tests/api.test.js", "README.md", ...],
  "tests_passed": true,
  "test_iterations": 2,
  "duration_minutes": 7.42
}
```

### ⚡ `delegate_to_claude_code()`

Synchronous delegation - starts task and waits for completion.

**Parameters:**
- `task` (required): Task description
- `working_directory` (optional): Where to run (default: current)
- `timeout_minutes` (default: 10.0): Max execution time
- `additional_flags` (optional): CLI flags to pass

**Returns:** JSON with status, stdout, stderr, duration

### 🔄 `delegate_to_claude_code_async()`

Asynchronous delegation - starts task in background, returns immediately.

**Parameters:** Same as `delegate_to_claude_code()`

**Returns:** JSON with `task_id` for tracking

### 📊 `get_delegation_result(task_id)`

Check status and retrieve results of async task.

**Returns:**
- If running: `{"status": "running", "elapsed_seconds": X}`
- If complete: `{"status": "completed", "stdout": "...", "stderr": "...", "duration_seconds": X}`
- If timeout: `{"status": "timeout"}`

### 📋 `list_delegations()`

List all active and completed async tasks.

**Returns:** JSON array of tasks with status and elapsed time

---

## Real-World Examples

### Example 1: Build Express.js Weather API

```
Use mcp__autonomous_build_and_deploy:
- task: "Build Express.js weather API that fetches from OpenWeatherMap, includes caching with Redis, rate limiting, error handling, and comprehensive tests"
- working_directory: "/tmp/weather-api"
- github_repo_name: "weather-api"
- enable_test_loop: true
```

**Result:**
- Duration: 8.3 minutes
- Files: 12 (server.js, routes/, controllers/, tests/, README.md, etc.)
- Tests: 15/15 passed (iteration 1 failed, auto-fixed)
- Deployed: https://github.com/snedea/weather-api

### Example 2: Build Mario Platformer Game

```
Use mcp__autonomous_build_and_deploy:
- task: "Build a Mario-style platformer game in vanilla JavaScript with HTML5 Canvas. Include player movement (left, right, jump), collision detection, multiple levels, enemies, and score tracking"
- working_directory: "/tmp/mario-game"
- github_repo_name: "mario-game"
- enable_test_loop: true
```

**Result:**
- Duration: 7.42 minutes
- Files: 8 (index.html, game.js, player.js, level.js, physics.js, tests/, docs/)
- Tests: 12/12 passed (iteration 2 after collision fix)
- Deployed: https://github.com/snedea/mario-game

### Example 3: Parallel Full-Stack Build

```
# Start backend
Use mcp__delegate_to_claude_code_async:
- task: "Create Python Flask REST API with JWT authentication, PostgreSQL database, user registration/login endpoints, and tests"
- working_directory: "/tmp/fullstack/backend"

# Start frontend (in parallel)
Use mcp__delegate_to_claude_code_async:
- task: "Create React SPA with login form, registration form, protected routes, JWT token management, and tests"
- working_directory: "/tmp/fullstack/frontend"

# Start database (in parallel)
Use mcp__delegate_to_claude_code_async:
- task: "Create PostgreSQL schema with users table, migrations, seed data, and setup scripts"
- working_directory: "/tmp/fullstack/database"

# Monitor progress
Use mcp__list_delegations

# Collect results
Use mcp__get_delegation_result for each task_id
```

**Result:**
- Sequential time: ~30 minutes (10 min each)
- Parallel time: ~12 minutes (limited by slowest task)
- Time saved: 18 minutes (60% faster)

---

## Self-Healing Test Loop in Action

**Scenario:** Building Express.js authentication API

```
PHASE 4 - TEST (Iteration 1):

Running: npm test

❌ FAIL: POST /auth/login should return JWT token
   Expected: 200
   Received: 500
   Error: UnhandledPromiseRejectionWarning: JWT secret not defined

[SYSTEM ANALYZES FAILURE]

Tester Agent:
- Root cause: generateToken() throws when JWT_SECRET undefined
- Missing: Error handling in auth controller
- Fix needed: Add try-catch, validate environment on startup

[SYSTEM REDESIGNS]

Architect Agent:
- Updates architecture.md with error handling requirements
- Creates fixes-iteration-1.md with specific code changes

[SYSTEM RE-IMPLEMENTS]

Builder Agent:
- Adds try-catch to auth controller
- Adds JWT_SECRET validation at startup
- Updates .env.example with required variables

[SYSTEM RE-TESTS]

PHASE 4 - TEST (Iteration 2):

Running: npm test

✅ PASS: All tests (3/3)
   ✓ POST /auth/login should return JWT token
   ✓ POST /auth/login should reject invalid credentials
   ✓ GET /auth/verify should validate token

[SYSTEM CONTINUES TO DEPLOYMENT]
```

**Total auto-fix time:** ~2 minutes

**Human intervention:** Zero

---

## Configuration

### Custom Python Version

If you need a specific Python version for the MCP server:

Edit `~/.config/claude-code/mcp_settings.json`:

```json
{
  "mcpServers": {
    "context-foundry": {
      "command": "/usr/local/bin/python3.11",
      "args": ["/path/to/context-foundry/tools/mcp_server.py"]
    }
  }
}
```

### Environment Variables

Pass environment variables to MCP server:

```json
{
  "mcpServers": {
    "context-foundry": {
      "command": "python3.10",
      "args": ["/path/to/context-foundry/tools/mcp_server.py"],
      "env": {
        "ANTHROPIC_API_KEY": "your-key",
        "OPENWEATHERMAP_API_KEY": "your-key"
      }
    }
  }
}
```

### Disable MCP Server

Temporarily disable without deleting configuration:

```json
{
  "mcpServers": {
    "context-foundry": {
      "disabled": true
    }
  }
}
```

---

## Troubleshooting

### MCP Server Won't Start

**Error:** `ImportError: No module named 'fastmcp'`

**Solution:**
```bash
pip install -r requirements-mcp.txt
# Or specifically:
pip install fastmcp>=2.0.0 nest-asyncio>=1.5.0
```

**Error:** Python version too old

**Solution:**
```bash
# Check version (must be 3.10+)
python3 --version

# Use specific version if available
python3.10 -m pip install -r requirements-mcp.txt
```

### Claude Code Doesn't See MCP Tools

**Symptoms:** `mcp__autonomous_build_and_deploy` not available

**Solutions:**

1. Verify MCP settings exist:
   ```bash
   cat ~/.config/claude-code/mcp_settings.json
   ```

2. Check path is correct:
   ```bash
   ls /path/to/context-foundry/tools/mcp_server.py
   ```

3. Restart Claude Code:
   ```bash
   # Exit current session and restart
   claude-code
   ```

4. Verify connection:
   ```bash
   claude mcp list
   # Should show: ✓ Connected: context-foundry
   ```

### Delegations Timeout

**Symptoms:** Tasks consistently hit timeout

**Solutions:**

1. Increase timeout:
   ```
   Use mcp__autonomous_build_and_deploy:
   - timeout_minutes: 120.0
   ```

2. Break into smaller tasks:
   - Instead of "Build entire application"
   - Use: Multiple delegations for modules

3. Check if task requires manual input (shouldn't happen with `--permission-mode bypassPermissions`)

### Tests Keep Failing

**Symptoms:** Test loop reaches max iterations without passing

**Solutions:**

1. Check test failure reports:
   ```bash
   cat .context-foundry/test-results-iteration-*.md
   ```

2. Review fix attempts:
   ```bash
   cat .context-foundry/fixes-iteration-*.md
   ```

3. Increase max iterations if issue seems fixable:
   ```
   Use mcp__autonomous_build_and_deploy:
   - max_test_iterations: 5
   ```

4. Disable test loop to see raw test output:
   ```
   Use mcp__autonomous_build_and_deploy:
   - enable_test_loop: false
   ```

**More help:** See [CLAUDE_CODE_MCP_SETUP.md](CLAUDE_CODE_MCP_SETUP.md) for comprehensive troubleshooting.

---

## Project Structure

```
context-foundry/
├── tools/
│   ├── mcp_server.py              # MCP server (all delegation tools)
│   └── orchestrator_prompt.txt    # Meta-prompt for autonomous workflow
├── .context-foundry/              # Generated during builds (in working_directory)
│   ├── scout-report.md            # Scout phase findings
│   ├── architecture.md            # Architect phase design
│   ├── build-log.md               # Builder phase log
│   ├── test-iteration-count.txt   # Current test iteration (1, 2, 3)
│   ├── test-results-iteration-*.md # Test failure analysis per iteration
│   ├── fixes-iteration-*.md       # Fix strategies per iteration
│   ├── test-final-report.md       # Final test results
│   └── session-summary.json       # Complete session metadata
├── examples/                      # Test delegation examples
│   └── test_claude_code_delegation.md
├── docs/
│   ├── CLAUDE_CODE_MCP_SETUP.md   # MCP setup and troubleshooting
│   └── (other documentation)
├── ARCHITECTURE_DECISIONS.md       # Technical deep dive (v2.0 changes)
├── LEGACY_README.md                # Original 1.x documentation
├── README.md                       # This file (v2.0)
└── requirements-mcp.txt            # MCP server dependencies
```

---

## Performance & Cost

### Performance Metrics

Based on real-world usage:

| Metric | Value |
|--------|-------|
| **Avg build time** | 7-15 minutes (simple to moderate projects) |
| **Test auto-fix success** | 95% (within 3 iterations) |
| **Parallel speedup** | 3-10x (vs sequential) |
| **Token efficiency** | No limits (file-based context) |
| **Code quality** | 90%+ test coverage |

### Cost Comparison

**Context Foundry 1.x (API mode):**
```
Per project: $3-10 (pay-per-token)
100 projects: $300-1000
```

**Context Foundry 2.0 (Claude Max):**
```
Subscription: $20/month (unlimited)
100 projects: $20/month

Break-even: ~5 projects per month
```

**Savings:** 95%+ for heavy users

---

## Documentation

| Document | Description |
|----------|-------------|
| **README.md** (this file) | Quick start and overview for v2.0 |
| **ARCHITECTURE_DECISIONS.md** | Technical deep dive: what changed and why |
| **CLAUDE_CODE_MCP_SETUP.md** | MCP server setup and troubleshooting |
| **LEGACY_README.md** | Original Context Foundry 1.x documentation |
| **USER_GUIDE.md** | Step-by-step usage guide *(coming soon)* |
| **CHANGELOG.md** | Version history and release notes *(coming soon)* |

---

## Philosophy

**Context Foundry 2.0 Philosophy:**
- **Autonomous over supervised**: Walk away while it builds
- **Self-healing over manual debugging**: Auto-fix test failures
- **File-based over conversation-based**: No token limits
- **Quality over speed**: Tests must pass before deployment
- **Simplicity over features**: Do one thing excellently

**Design Principles:**
- ✅ AI orchestrates itself (meta-prompts, not Python)
- ✅ Native tools over custom wrappers (Claude Code Read/Edit/Bash)
- ✅ File artifacts over conversation memory (.context-foundry/ directory)
- ✅ Self-healing over checkpoints (auto-fix instead of human review)
- ✅ GitHub deployment over local-only (share your work)

---

## Roadmap

### v2.0.1 (Next Release)
- [ ] Enhanced test failure analysis
- [ ] Configurable test frameworks (Jest, pytest, etc.)
- [ ] Better error recovery in deployment phase

### v2.1 (Future)
- [ ] Pattern library (save successful builds as reusable patterns)
- [ ] Multi-project orchestration (build related projects together)
- [ ] Cost tracking for API mode users
- [ ] Enhanced logging and debugging tools

### v3.0 (Vision)
- [ ] Visual progress dashboard
- [ ] Support for additional version control systems
- [ ] Integration with CI/CD pipelines
- [ ] Team collaboration features

---

## Contributing

We welcome contributions! To contribute:

1. **Read the technical docs**: [ARCHITECTURE_DECISIONS.md](ARCHITECTURE_DECISIONS.md)
2. **Understand the workflow**: Scout → Architect → Builder → Test → Deploy
3. **Follow the principles**: Autonomous, self-healing, file-based
4. **Submit PRs**: With clear descriptions and tests

---

## License

MIT License - See LICENSE file for details

---

## Credits

Context Foundry 2.0 builds upon:
- **Anthropic's Claude Code** - Native agent capabilities and MCP protocol
- **Context Foundry 1.x** - Original Scout/Architect/Builder workflow
- **[Dexter Horthy's](https://youtu.be/IS_y40zY-hc) "anti-vibe coding"** - Systematic approach over chaotic iteration
- **[Anthropic Agent SDK patterns](https://www.anthropic.com/engineering/building-agents-with-the-claude-agent-sdk)** - Agent orchestration techniques

---

## Support

- **Issues**: [GitHub Issues](https://github.com/snedea/context-foundry/issues)
- **Discussions**: [GitHub Discussions](https://github.com/snedea/context-foundry/discussions)
- **Documentation**: Start with this README, then [ARCHITECTURE_DECISIONS.md](ARCHITECTURE_DECISIONS.md)

---

**Context Foundry 2.0** - *Build complete software autonomously with self-healing AI workflows*

**Version:** 2.0.0 | **Release Date:** October 2025 | **License:** MIT
