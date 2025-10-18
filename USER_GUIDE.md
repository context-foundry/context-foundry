# Context Foundry 2.0 - User Guide

**Your step-by-step guide to autonomous AI development**

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Basic Usage](#basic-usage)
3. [Autonomous Builds](#autonomous-builds)
4. [Task Delegation](#task-delegation)
5. [Parallel Execution](#parallel-execution)
6. [Understanding the Workflow](#understanding-the-workflow)
7. [Troubleshooting](#troubleshooting)
8. [Best Practices](#best-practices)
9. [Advanced Usage](#advanced-usage)

---

## Getting Started

### Prerequisites Check

Before starting, verify you have:

```bash
# 1. Python 3.10 or higher
python3 --version
# Should show: Python 3.10.x or higher

# 2. Claude Code CLI
which claude
# Should show: /opt/homebrew/bin/claude (or similar)

claude --version
# Should show version info

# 3. Git and GitHub CLI
git --version
gh --version

# 4. GitHub authentication
gh auth status
# Should show: Logged in as [your-username]
```

If any of these fail, see [Prerequisites Setup](#prerequisites-setup) below.

### Installation

#### Step 1: Clone Context Foundry

```bash
# Navigate to where you want Context Foundry
cd ~/homelab  # or your preferred directory

# Clone the repository
git clone https://github.com/snedea/context-foundry.git
cd context-foundry
```

#### Step 2: Install MCP Server Dependencies

```bash
# Install required Python packages
pip install -r requirements-mcp.txt

# Verify installation
python3.10 -c "from fastmcp import FastMCP; print('✅ FastMCP installed')"
```

If you get errors, see [Troubleshooting Installation](#troubleshooting-installation).

#### Step 3: Configure MCP Connection

```bash
# Add MCP server to Claude Code configuration
# Replace /full/path/to with your actual path
claude mcp add --transport stdio context-foundry -- \
  python3.10 /full/path/to/context-foundry/tools/mcp_server.py

# Example:
claude mcp add --transport stdio context-foundry -- \
  python3.10 /Users/yourname/homelab/context-foundry/tools/mcp_server.py
```

#### Step 4: Verify Connection

```bash
# List MCP servers
claude mcp list

# Should show:
# ✓ Connected: context-foundry
```

If you see "✗ Disconnected" or errors, see [Troubleshooting MCP Connection](#troubleshooting-mcp-connection).

#### Step 5: Test the Setup

```bash
# Start Claude Code
claude-code

# You should see MCP tools available
# Try typing: "What MCP tools are available?"
# Claude should list: mcp__autonomous_build_and_deploy, mcp__delegate_to_claude_code, etc.
```

✅ **Success!** You're ready to use Context Foundry 2.0.

---

## Basic Usage

### Your First Build

Let's build a simple "Hello World" project to verify everything works.

```bash
# Start Claude Code
claude-code
```

Inside your Claude Code session, say:

```
Please use mcp__autonomous_build_and_deploy to build a simple "Hello World" web page:

- task: "Create a simple Hello World HTML page with CSS styling and a button that shows an alert"
- working_directory: "/tmp/hello-world"
- github_repo_name: "hello-world-test"
- enable_test_loop: false
```

**What happens:**

1. Scout phase: AI researches how to build a simple HTML page
2. Architect phase: AI designs the structure (HTML, CSS, button)
3. Builder phase: AI creates the files
4. Test phase: Skipped (enable_test_loop: false)
5. Documentation phase: AI creates README
6. Deploy phase: AI pushes to GitHub

**Expected output:**

```json
{
  "status": "completed",
  "phases_completed": ["scout", "architect", "builder", "docs", "deploy"],
  "github_url": "https://github.com/yourusername/hello-world-test",
  "files_created": ["index.html", "style.css", "README.md"],
  "tests_passed": null,
  "duration_minutes": 2.3
}
```

**Verify the result:**

```bash
# Check files were created
ls -la /tmp/hello-world

# Open in browser
open /tmp/hello-world/index.html

# Check GitHub
gh repo view yourusername/hello-world-test --web
```

✅ If you see your project deployed to GitHub, everything works!

---

## Autonomous Builds

### Building a Todo CLI App

Let's build a more realistic project with tests enabled.

```
Use mcp__autonomous_build_and_deploy:

- task: "Build a command-line todo app in Python with the following features:
  - Add new todos
  - List all todos
  - Mark todos as complete
  - Delete todos
  - Store todos in JSON file
  - Use Rich library for colorful output
  - Include comprehensive tests with pytest"

- working_directory: "/tmp/todo-cli"
- github_repo_name: "todo-cli-app"
- enable_test_loop: true
- max_test_iterations: 3
```

**What's different:**
- `enable_test_loop: true` - AI will auto-fix if tests fail
- `max_test_iterations: 3` - Up to 3 auto-fix attempts

**Duration:** ~5-10 minutes

**What to expect:**

```
Phase 1 - Scout (1-2 min):
- Researches Python CLI best practices
- Identifies Rich library for formatting
- Plans JSON storage approach

Phase 2 - Architect (1-2 min):
- Designs command structure (add, list, complete, delete)
- Plans file structure
- Defines test strategy

Phase 3 - Builder (2-4 min):
- Creates todo.py (main logic)
- Creates cli.py (command interface)
- Creates tests/test_todo.py
- Creates requirements.txt

Phase 4 - Test (1-2 min):
[If tests fail - auto-healing kicks in]
Iteration 1: Run tests → Fail
  Tester: Analyzes failures
  Architect: Redesigns fix
  Builder: Implements fix
Iteration 2: Run tests → Pass

Phase 5 - Documentation (1 min):
- Creates comprehensive README
- Documents usage and installation

Phase 6 - Deploy (30 sec):
- Pushes to GitHub
```

**Final structure:**

```
/tmp/todo-cli/
├── todo.py
├── cli.py
├── tests/
│   └── test_todo.py
├── requirements.txt
├── README.md
└── .context-foundry/
    ├── scout-report.md
    ├── architecture.md
    ├── build-log.md
    ├── test-iteration-count.txt
    ├── test-results-iteration-*.md
    └── test-final-report.md
```

**Try it out:**

```bash
cd /tmp/todo-cli
pip install -r requirements.txt
python cli.py add "Buy groceries"
python cli.py list
python cli.py complete 1
```

---

## Task Delegation

### Simple Synchronous Delegation

For quick, standalone tasks that don't need the full workflow:

```
Use mcp__delegate_to_claude_code:

- task: "Create a Python script that fetches the current weather for San Francisco using the OpenWeatherMap API and prints it nicely formatted"
- working_directory: "/tmp/weather-script"
- timeout_minutes: 5
```

**When to use:**
- Quick scripts or single files
- No need for full Scout → Architect → Builder workflow
- Want synchronous execution (wait for result)

**Returns immediately when complete with:**
- stdout (script output)
- stderr (error messages)
- duration
- exit code

### Checking Working Directory

Before delegating, optionally create and verify the directory:

```bash
mkdir -p /tmp/my-project
ls -la /tmp/my-project
```

Then delegate:

```
Use mcp__delegate_to_claude_code:
- task: "Create a simple Flask API with a /hello endpoint"
- working_directory: "/tmp/my-project"
```

---

## Parallel Execution

### Building a Full-Stack App in Parallel

Instead of building components sequentially (slow), build them in parallel (fast).

#### Step 1: Start All Tasks in Parallel

```
I need to build a full-stack app with backend, frontend, and database.
Please start these three tasks in parallel using mcp__delegate_to_claude_code_async:

Task 1 - Backend:
- task: "Create a Python Flask REST API with user authentication (JWT), PostgreSQL database connection, endpoints for register/login/profile, and comprehensive tests"
- working_directory: "/tmp/fullstack-app/backend"
- timeout_minutes: 15

Task 2 - Frontend:
- task: "Create a React SPA with login page, registration page, user profile page, JWT token management, protected routes, and tests with React Testing Library"
- working_directory: "/tmp/fullstack-app/frontend"
- timeout_minutes: 15

Task 3 - Database:
- task: "Create PostgreSQL schema with users table, authentication tokens table, migration scripts, seed data, and setup documentation"
- working_directory: "/tmp/fullstack-app/database"
- timeout_minutes: 10
```

Claude will spawn all three tasks and return task IDs:

```json
{
  "task_1_id": "abc123-backend",
  "task_2_id": "def456-frontend",
  "task_3_id": "ghi789-database"
}
```

#### Step 2: Monitor Progress

```
Use mcp__list_delegations to check progress
```

Returns:

```json
{
  "tasks": [
    {
      "task_id": "abc123-backend",
      "status": "running",
      "elapsed_seconds": 125.3
    },
    {
      "task_id": "def456-frontend",
      "status": "running",
      "elapsed_seconds": 124.8
    },
    {
      "task_id": "ghi789-database",
      "status": "completed",
      "elapsed_seconds": 87.2
    }
  ]
}
```

#### Step 3: Collect Results

```
Use mcp__get_delegation_result with task_id "ghi789-database"
```

Returns:

```json
{
  "status": "completed",
  "duration_seconds": 87.2,
  "stdout": "Database schema created successfully...",
  "stderr": "",
  "return_code": 0
}
```

Repeat for other tasks when they complete.

#### Performance Comparison

**Sequential approach:**
```
Backend: 12 min
Frontend: 14 min
Database: 6 min
Total: 32 minutes
```

**Parallel approach:**
```
All three start simultaneously
Longest task (Frontend): 14 min
Total: 14 minutes (56% time savings)
```

---

## Understanding the Workflow

### The 6-Phase Autonomous Workflow

#### Phase 1: Scout (Research & Context Gathering)

**What happens:**
- AI creates a Scout agent using `/agents`
- Scout explores your requirements
- Scout researches best practices
- Scout identifies technology choices
- Scout saves findings to `.context-foundry/scout-report.md`

**Example Scout Report:**

```markdown
# Scout Report

## Task Analysis
Build a weather API with Express.js and OpenWeatherMap integration

## Technology Stack
- Runtime: Node.js 18+
- Framework: Express.js
- External API: OpenWeatherMap
- Caching: Redis (for rate limiting)
- Testing: Jest + Supertest

## Requirements
- GET /weather/:city endpoint
- Error handling for invalid cities
- Rate limiting (100 req/hour per IP)
- Caching (5 min TTL)

## Challenges
- API key management
- Rate limit enforcement
- Error responses
```

#### Phase 2: Architect (Design & Planning)

**What happens:**
- AI reads scout-report.md
- AI creates Architect agent using `/agents`
- Architect designs system architecture
- Architect creates implementation plan
- Architect saves to `.context-foundry/architecture.md`

**Example Architecture:**

```markdown
# Architecture

## File Structure
```
weather-api/
├── server.js
├── routes/
│   └── weather.js
├── controllers/
│   └── weatherController.js
├── middleware/
│   └── rateLimiter.js
├── tests/
│   └── weather.test.js
└── .env.example
```

## Implementation Plan
1. Set up Express server
2. Create weather controller with OpenWeatherMap client
3. Implement rate limiting middleware with Redis
4. Create routes
5. Add error handling
6. Write comprehensive tests
7. Create documentation
```

#### Phase 3: Builder (Implementation)

**What happens:**
- AI reads architecture.md
- AI creates Builder agent using `/agents`
- Builder implements all files per architecture
- Builder writes tests
- Builder saves log to `.context-foundry/build-log.md`

**What Builder creates:**
- All source code files
- Test files
- Configuration files (.env.example, package.json, etc.)
- Build log documenting all changes

#### Phase 4: Test (Validation & Quality Assurance)

**What happens:**
- AI creates Tester agent using `/agents`
- Tester runs all tests
- **If tests pass:**
  - Creates test-final-report.md
  - Continues to Phase 5
- **If tests fail (and enable_test_loop=true):**
  - Self-healing loop activates (see below)

**Self-Healing Loop (when tests fail):**

```
Test Iteration 1:
1. Tester runs: npm test
2. Tests fail: Authentication error
3. Tester analyzes: "JWT secret undefined"
4. Tester creates: test-results-iteration-1.md

5. Architect reads failure report
6. Architect redesigns: "Add JWT_SECRET validation"
7. Architect creates: fixes-iteration-1.md

8. Builder reads fix plan
9. Builder implements: try-catch blocks, env validation
10. Builder updates: build-log.md

11. Increment test-iteration-count.txt (1 → 2)
12. Tester runs: npm test again

Test Iteration 2:
1. All tests pass!
2. Tester creates: test-final-report.md
3. Continue to Phase 5
```

**Max iterations:** If tests still fail after `max_test_iterations` (default: 3), system reports failure and stops.

#### Phase 5: Documentation

**What happens:**
- AI creates comprehensive README.md
- AI creates docs/ directory with:
  - INSTALLATION.md
  - USAGE.md
  - ARCHITECTURE.md
  - TESTING.md
  - API.md (if applicable)

**Example README:**

```markdown
# Weather API

Get current weather data for any city.

## Features
- RESTful API with Express.js
- OpenWeatherMap integration
- Redis caching (5 min TTL)
- Rate limiting (100 req/hour)
- Comprehensive error handling
- 95% test coverage

## Installation
```bash
npm install
cp .env.example .env
# Add your OPENWEATHERMAP_API_KEY to .env
npm start
```

## Usage
```bash
curl http://localhost:3000/weather/sanfrancisco
```

## Testing
```bash
npm test
```

🤖 Built autonomously by Claude Code Context Foundry
```

#### Phase 6: Deployment (GitHub)

**What happens:**
- AI initializes git (if new project)
- AI adds all files: `git add .`
- AI creates detailed commit message
- AI creates GitHub repo: `gh repo create`
- AI pushes to GitHub: `git push`

**Commit Message Format:**

```
Initial implementation via Context Foundry autonomous agent

Project: Weather API with Express.js
Status: Tests PASSED (after 2 iteration(s))

Architecture:
- Scout phase: Requirements analysis and tech stack selection
- Architect phase: System design and implementation plan
- Builder phase: Code implementation with tests
- Test phase: Validation and quality assurance

Test Results:
- All tests passing
- Test iterations: 2
- Quality: Production ready

Documentation:
- Complete README
- Installation guide
- Usage guide
- Architecture documentation
- Test documentation

🤖 Generated autonomously by Claude Code Context Foundry
Co-Authored-By: Claude <noreply@anthropic.com>
```

---

## Troubleshooting

### Prerequisites Setup

#### Installing Python 3.10+

**macOS (Homebrew):**
```bash
brew install python@3.10
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install python3.10 python3.10-pip
```

**Verify:**
```bash
python3.10 --version
```

#### Installing Claude Code CLI

Follow Anthropic's official installation guide for your platform.

**Verify:**
```bash
which claude
claude --version
```

#### Installing GitHub CLI

**macOS:**
```bash
brew install gh
```

**Linux:**
```bash
# Debian/Ubuntu
sudo apt install gh

# Other distributions - see: https://github.com/cli/cli
```

**Authenticate:**
```bash
gh auth login
# Follow prompts to authenticate
```

### Troubleshooting Installation

#### Error: "No module named 'fastmcp'"

```bash
# Install again with specific Python version
python3.10 -m pip install -r requirements-mcp.txt

# Verify
python3.10 -c "from fastmcp import FastMCP; print('✅ Success')"
```

#### Error: "Python version too old"

Your system Python is < 3.10. Install Python 3.10+ (see above).

#### Error: "Permission denied"

Try with `--user` flag:
```bash
pip install --user -r requirements-mcp.txt
```

### Troubleshooting MCP Connection

#### Error: "MCP server not found"

Check the path in your `mcp add` command:

```bash
# Verify the file exists
ls /full/path/to/context-foundry/tools/mcp_server.py

# Re-add with correct path
claude mcp remove context-foundry
claude mcp add --transport stdio context-foundry -- \
  python3.10 /correct/path/to/context-foundry/tools/mcp_server.py
```

#### Error: "MCP server disconnected"

Check MCP configuration:

```bash
cat ~/.config/claude-code/mcp_settings.json
```

Should show:

```json
{
  "mcpServers": {
    "context-foundry": {
      "command": "python3.10",
      "args": ["/full/path/to/context-foundry/tools/mcp_server.py"],
      "disabled": false
    }
  }
}
```

Restart Claude Code:
```bash
# Exit current session
# Start fresh
claude-code
```

#### MCP Tools Not Showing Up

```bash
# In Claude Code session, ask:
"What MCP tools are available?"

# Should list:
# - mcp__autonomous_build_and_deploy
# - mcp__delegate_to_claude_code
# - mcp__delegate_to_claude_code_async
# - mcp__get_delegation_result
# - mcp__list_delegations
```

If not showing:
1. Verify MCP connection: `claude mcp list`
2. Check for errors in configuration
3. Restart Claude Code

### Troubleshooting Builds

#### Build Hangs or Takes Too Long

Increase timeout:

```
Use mcp__autonomous_build_and_deploy:
- timeout_minutes: 120  # Increase from default 90
```

Check if build is actually running:

```bash
# In another terminal
ps aux | grep claude
# Should show claude processes
```

#### Tests Keep Failing (Max Iterations Reached)

Check test failure reports:

```bash
cd /your/working/directory
cat .context-foundry/test-results-iteration-*.md
```

Review fix attempts:

```bash
cat .context-foundry/fixes-iteration-*.md
```

Options:

1. **Increase max iterations:**
   ```
   - max_test_iterations: 5
   ```

2. **Disable test loop temporarily:**
   ```
   - enable_test_loop: false
   ```

3. **Fix manually and re-run**

#### GitHub Deployment Fails

Check GitHub authentication:

```bash
gh auth status
# Should show: Logged in

# If not:
gh auth login
```

Check GitHub CLI works:

```bash
gh repo list
# Should show your repos
```

#### Files Created in Wrong Directory

Verify working_directory is absolute path:

```
❌ Wrong: working_directory: "~/my-project"
❌ Wrong: working_directory: "./my-project"
✅ Correct: working_directory: "/Users/yourname/my-project"
✅ Correct: working_directory: "/tmp/my-project"
```

Create directory first if it doesn't exist:

```bash
mkdir -p /tmp/my-project
```

---

## Best Practices

### Naming Projects

**Good project names:**
- Lowercase with hyphens
- Descriptive
- GitHub-friendly

```
✅ weather-api
✅ todo-cli-app
✅ user-auth-service
❌ My Cool Project
❌ test123
❌ untitled
```

### Working Directories

**Recommended:**
```bash
# For temporary/test projects
/tmp/project-name

# For real projects
/Users/yourname/projects/project-name
~/projects/project-name  # Will be expanded to absolute path
```

**Create directory first:**
```bash
mkdir -p /path/to/project
```

### Timeout Settings

**Guidelines:**

| Project Type | Recommended Timeout |
|--------------|---------------------|
| Single file script | 2-5 minutes |
| Simple CLI app | 5-10 minutes |
| REST API | 10-20 minutes |
| Full-stack app | 30-60 minutes |
| Complex system | 60-120 minutes |

**Example:**
```
- timeout_minutes: 15  # REST API
```

### Test Loop Settings

**Enable test loop when:**
- ✅ Building production code
- ✅ Code has complex logic
- ✅ You want high quality output

**Disable test loop when:**
- ✅ Rapid prototyping
- ✅ Throwaway code
- ✅ Debugging workflow issues

**Max iterations:**
- **3** (default) - Good balance
- **5** - For complex projects
- **1** - See raw failures without auto-fix

### Task Descriptions

**Good task descriptions:**

```
✅ Specific:
"Build a REST API with Express.js that has endpoints for user CRUD operations,
JWT authentication, PostgreSQL database, and comprehensive tests"

✅ Lists requirements:
"Create a CLI todo app with:
- Add, list, complete, delete commands
- JSON file storage
- Colorful output with Rich library
- Pytest tests"

❌ Too vague:
"Build an app"

❌ Too constraining:
"Use exactly this code structure: [paste 500 lines]"
```

**Sweet spot:** Specific requirements, but let AI decide implementation details.

---

## Advanced Usage

### Customizing the Workflow

Edit `tools/orchestrator_prompt.txt` to customize the workflow:

```bash
# Edit the meta-prompt
nano /path/to/context-foundry/tools/orchestrator_prompt.txt
```

**Example customizations:**

1. **Add a security audit phase:**
   ```
   PHASE 5: SECURITY AUDIT
   1. Create Security Agent via /agents
   2. Run security scans
   3. Check for vulnerabilities
   4. Create security-report.md
   ```

2. **Change test framework:**
   ```
   PHASE 3: BUILDER
   - For Python: Use pytest (not unittest)
   - For JavaScript: Use Jest (not Mocha)
   - For Go: Use standard testing package
   ```

3. **Add deployment to cloud:**
   ```
   PHASE 6: DEPLOYMENT
   - Deploy to Vercel for frontend
   - Deploy to Railway for backend
   - Deploy to Supabase for database
   ```

### Environment Variables

Pass env vars to MCP server:

Edit `~/.config/claude-code/mcp_settings.json`:

```json
{
  "mcpServers": {
    "context-foundry": {
      "command": "python3.10",
      "args": ["/path/to/mcp_server.py"],
      "env": {
        "ANTHROPIC_API_KEY": "your-key",
        "OPENWEATHERMAP_API_KEY": "your-key",
        "DATABASE_URL": "postgresql://..."
      }
    }
  }
}
```

### Using with Different GitHub Accounts

```bash
# Switch GitHub accounts
gh auth switch

# Or log out and log in with different account
gh auth logout
gh auth login
```

### Inspecting Build Artifacts

After a build, explore the `.context-foundry/` directory:

```bash
cd /your/project/.context-foundry

# Scout findings
cat scout-report.md

# Architecture design
cat architecture.md

# Build log
cat build-log.md

# Test iterations (if any failures)
cat test-iteration-count.txt
cat test-results-iteration-*.md
cat fixes-iteration-*.md

# Final test report
cat test-final-report.md
```

These files help you understand what the AI did and debug issues.

### Resuming Failed Builds

If a build fails, you can:

1. **Review the artifacts:**
   ```bash
   cd /your/project/.context-foundry
   cat test-results-iteration-*.md
   ```

2. **Fix manually and re-run:**
   ```bash
   # Fix the code manually
   # Then re-run autonomous build
   ```

3. **Increase iterations:**
   ```
   Use mcp__autonomous_build_and_deploy:
   - max_test_iterations: 5  # Try more times
   ```

---

## Next Steps

### After Your First Successful Build

1. **Try more complex projects:**
   - Full-stack applications
   - Microservices
   - Game development

2. **Experiment with parallel execution:**
   - Build multiple components simultaneously
   - Measure time savings

3. **Customize the workflow:**
   - Edit `orchestrator_prompt.txt`
   - Add custom phases
   - Adjust test strategies

4. **Read the technical docs:**
   - [ARCHITECTURE_DECISIONS.md](ARCHITECTURE_DECISIONS.md) for deep dives
   - [CONTEXT_FOUNDRY_2.0.md](CONTEXT_FOUNDRY_2.0.md) for 1.x vs 2.0 comparison

### Learning More

- **README.md** - Quick reference and overview
- **ARCHITECTURE_DECISIONS.md** - Technical deep dives
- **CONTEXT_FOUNDRY_2.0.md** - What's new in 2.0
- **CLAUDE_CODE_MCP_SETUP.md** - MCP setup and troubleshooting
- **examples/** - Test scenarios and examples

### Getting Help

- **GitHub Issues:** Report bugs and request features
- **GitHub Discussions:** Ask questions and share projects
- **Documentation:** Start here, then technical docs

---

## Summary Cheat Sheet

### Quick Reference

**Start Claude Code:**
```bash
claude-code
```

**Build a project (autonomous):**
```
Use mcp__autonomous_build_and_deploy:
- task: "Description of what to build"
- working_directory: "/full/path/to/project"
- github_repo_name: "repo-name"
- enable_test_loop: true
```

**Delegate a simple task:**
```
Use mcp__delegate_to_claude_code:
- task: "Create a script that does X"
- working_directory: "/tmp/my-script"
```

**Parallel tasks:**
```
Use mcp__delegate_to_claude_code_async for each task
Use mcp__list_delegations to monitor
Use mcp__get_delegation_result to collect results
```

**Check MCP status:**
```bash
claude mcp list
```

**View artifacts:**
```bash
ls -la /your/project/.context-foundry/
```

---

**Happy Building!** 🎉

Context Foundry 2.0 - Autonomous AI Development

For more help: [README.md](README.md) | [ARCHITECTURE_DECISIONS.md](ARCHITECTURE_DECISIONS.md)
