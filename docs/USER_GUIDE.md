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
7. [**Real-Time Monitoring Dashboard (NEW)**](#real-time-monitoring-dashboard)
8. [Troubleshooting](#troubleshooting)
9. [Best Practices](#best-practices)
10. [Advanced Usage](#advanced-usage)

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
# Use $(pwd) for automatic absolute paths, add to project scope
cd /path/to/context-foundry
claude mcp add --transport stdio context-foundry -s project -- $(pwd)/venv/bin/python $(pwd)/tools/mcp_server.py

# The -s project flag creates .mcp.json in the project directory (shareable with team)
```

#### Step 4: Verify Connection

```bash
# Verify the config was created
cat .mcp.json
# Should show the server configuration with your paths

# Note: Project-scoped servers don't appear in `claude mcp list` (that shows global config)
# They're automatically detected when you run `claude` in this directory
```

If you see "✗ Disconnected" or errors, see [Troubleshooting MCP Connection](#troubleshooting-mcp-connection).

#### Step 5: Test the Setup

```bash
# Start Claude Code
claude

# You should see MCP tools available
# Try typing: "What MCP tools are available?"
# Claude should list: mcp__autonomous_build_and_deploy, mcp__delegate_to_claude_code, etc.
```

✅ **Success!** You're ready to use Context Foundry 2.0.

---

## How Claude Code Recognizes Build Requests

**The easiest way to use Context Foundry:** Just ask naturally in plain English!

### 🎯 Intent Detection

Claude Code automatically uses Context Foundry's autonomous build system when you:

✅ **Use action words:** "build", "create", "make", "develop", "implement"
✅ **Describe an application or project:** "weather app", "REST API", "todo list"
✅ **Include features or requirements:** List what you want it to do

### ✅ Examples That Trigger Autonomous Build

These natural requests will automatically use `mcp__autonomous_build_and_deploy`:

```
Build a weather app
```

```
Create a REST API with user authentication
```

```
Make a game like Snake
```

```
Develop a todo list app with React
```

```
Build a calculator with basic and scientific functions
```

```
Create a blog platform with Markdown support
```

### ❌ Examples That Won't Trigger (Just Explains)

These are questions that ask for information, not requests to build:

```
How do I build a weather app?
→ This explains the process, doesn't build
```

```
What's the best way to create an API?
→ This discusses approaches, doesn't build
```

```
Can you help me understand how to make a game?
→ This teaches concepts, doesn't build
```

```
Explain the steps to develop a todo app
→ This provides guidance, doesn't build
```

### 💡 The Difference

| Intent | Example | What Happens |
|--------|---------|--------------|
| **Build Request** | "Build a weather app" | ✅ Automatic autonomous build |
| **Question** | "How do I build a weather app?" | ℹ️ Explains the process |
| **Discussion** | "What's the best way to build apps?" | ℹ️ Discusses approaches |
| **Learning** | "Teach me to build a weather app" | ℹ️ Educational response |

### 🚀 No Need to Mention MCP Tools!

You don't need to say:
- ❌ "Use mcp__autonomous_build_and_deploy..."
- ❌ "Call the autonomous build tool..."
- ❌ "Execute the MCP command for..."

Just say what you want:
- ✅ "Build a weather app"
- ✅ "Create a todo list"
- ✅ "Make a calculator"

**Claude Code handles the MCP calls automatically!**

### 📝 Being Specific Gets Better Results

**Vague (works, but basic):**
```
Build an app
```

**Specific (much better results):**
```
Build a weather app with:
- Current weather display
- 5-day forecast
- City search with autocomplete
- Temperature unit toggle (C/F)
- Responsive design for mobile
- Clean, modern UI
```

**Very specific (best results):**
```
Build a weather application using the OpenWeatherMap API with:
- Current weather and 5-day forecast
- Air Quality Index (AQI) display
- City search with autocomplete
- Geolocation to detect user's location
- Temperature unit toggle
- Responsive design
- Express.js backend with caching
- Comprehensive tests with Jest
- Error handling for API failures
```

### 🎓 Learning the Pattern

**Pattern:** `[Action] [What] [Optional: with features/tech]`

Examples:
- **Build** a **todo app** with **React and localStorage**
- **Create** a **REST API** with **Express and PostgreSQL**
- **Make** a **Snake game** with **HTML5 Canvas**
- **Develop** a **blog platform** with **Markdown support and authentication**

### 💬 What If You're Unsure?

Just ask naturally! Worst case:
- If it's a build request → Autonomous build starts
- If it's a question → You get an explanation (then you can say "Actually, build it!")

**Example conversation:**
```
You: "How do I build a weather app?"
Claude: "Here's how to build a weather app..."
You: "Actually, build it for me"
Claude: [Starts autonomous build]
```

### 🔧 Advanced: Customize the Build

You can still specify advanced options if needed:

```
Build a weather app, but use a 30-minute timeout and build it in /Users/me/projects/weather
```

```
Create a REST API and skip the test loop for faster prototyping
```

```
Make a todo app and deploy to my existing repo at github.com/me/todos
```

Claude Code will extract these requirements and use the right parameters.

---

## Basic Usage

### Your First Build

Let's build a simple "Hello World" project to verify everything works.

```bash
# Start Claude Code
claude
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

Phase 4.5 - Screenshot Capture (30-60 sec):
- Installs Playwright automatically
- Starts application dev server
- Captures hero screenshot for README
- Captures step-by-step workflow screenshots
- Saves to docs/screenshots/
- Creates manifest.json listing all screenshots

Phase 5 - Documentation (1 min):
- Creates comprehensive README with hero screenshot
- Documents usage with visual step-by-step guides
- Includes screenshots in docs/USAGE.md

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

## Background Builds

**Important:** By default, all autonomous builds run in the **background** (non-blocking), so you can continue working while projects build.

### Why Background Builds?

**Before (blocking builds):**
```
You: Build a weather app
Claude: [Building... your session is frozen for 10 minutes]
You: [Can't do anything else, must wait]
```

**After (background builds):**
```
You: Build a weather app
Claude: 🚀 Build started! Task ID: abc-123
        You can continue working.
You: [Immediately continue with other work]
     [Check back in 10-15 minutes]
```

### How It Works

When you request a build, the system:

1. **Spawns a background process** - Fresh Claude Code instance starts
2. **Returns immediately** - You get a task_id right away
3. **Runs autonomously** - Complete workflow happens in background
4. **No blocking** - Your Claude Code session stays responsive

### Starting a Background Build

**Natural language (easiest):**
```
Build a todo app with React
```

Claude automatically uses the async version!

**Explicit MCP call:**
```
Use mcp__autonomous_build_and_deploy_async:
- task: "Build a calculator app"
- working_directory: "/tmp/calculator"
- github_repo_name: "calculator-app"
```

**You'll get:**
```json
{
  "task_id": "abc-123-def-456",
  "status": "started",
  "project": "calculator-app",
  "message": "Build started! Expected duration: 7-15 minutes. You can continue working."
}
```

### Checking Build Status

**Ask naturally:**
```
What's the status of my build?
How's the calculator app going?
Is task abc-123-def-456 done?
```

**Use MCP tool:**
```
Use mcp__get_delegation_result with task_id "abc-123-def-456"
```

**If still running:**
```json
{
  "status": "running",
  "elapsed_seconds": 312.5,
  "message": "Build in progress (5.2 minutes elapsed)"
}
```

**If complete:**
```json
{
  "status": "completed",
  "duration_seconds": 487.3,
  "stdout": "[Full build output]",
  "stderr": "",
  "return_code": 0
}
```

### Listing All Active Builds

**Natural language:**
```
What builds are running?
Show me all my active tasks
List all delegations
```

**MCP tool:**
```
Use mcp__list_delegations
```

**Response:**
```json
{
  "tasks": [
    {
      "task_id": "abc-123",
      "status": "running",
      "elapsed_seconds": 245.7
    },
    {
      "task_id": "def-456",
      "status": "completed",
      "elapsed_seconds": 512.3
    },
    {
      "task_id": "ghi-789",
      "status": "running",
      "elapsed_seconds": 87.1
    }
  ]
}
```

### Real-World Example

**Scenario:** Build a full-stack app while working on documentation

```
[9:00 AM]
You: Build a full-stack todo app with React frontend, Express backend, and PostgreSQL

Claude: 🚀 Build started!
        Task ID: fullstack-001
        Expected: 15-20 minutes
        You can continue working!

[9:01 AM]
You: [Switch to working on your documentation]
     [Write blog post about the project]
     [Answer emails]

[9:15 AM]
You: What's the status of fullstack-001?

Claude: ✅ Build completed!
        GitHub: https://github.com/you/todo-app
        Files: 32 created
        Tests: 45/45 passing
        Duration: 14.2 minutes

[9:16 AM]
You: Great! Now deploy it to Vercel
```

**Time saved:** Instead of staring at the screen for 15 minutes, you worked on other tasks!

### Multiple Simultaneous Builds

You can start multiple builds at once:

```
Build a weather app in /tmp/weather
Build a calculator in /tmp/calc
Build a Snake game in /tmp/snake
```

All three run in parallel! Check status with:

```
List all my builds
```

### When to Use Synchronous (Blocking) Builds

Most of the time, use async (default). Only use synchronous if:

- You're debugging the workflow
- You want to see live output as it happens
- You have a very short build (< 2 min)

**Request synchronous explicitly:**
```
Use the synchronous version of autonomous_build_and_deploy to build [...]
I want to wait for this build to complete
```

### Best Practices

**✅ Do:**
- Start your build and continue working
- Check back in 10-15 minutes
- Use natural language to check status
- Run multiple builds in parallel for different projects

**❌ Don't:**
- Sit and wait for async builds (defeats the purpose!)
- Restart Claude Code while builds are running (you'll lose tracking)
- Use synchronous builds unless you have a reason

### Troubleshooting Background Builds

**Q: I lost my task_id, how do I find it?**
```
Show me all my active builds
List all delegations
```

**Q: Build seems stuck, how do I check?**
```
Use mcp__get_delegation_result with task_id "[your-id]"
```

If elapsed_seconds keeps increasing, it's still running.

**Q: Can I cancel a background build?**

Builds will timeout after `timeout_minutes` (default: 90). No manual cancellation needed.

**Q: What happens if I restart Claude Code?**

Background builds continue! But you lose the ability to track them in the current session. They'll complete and be available in the working_directory.

---

## Understanding the Workflow

### The 8-Phase Autonomous Workflow

Context Foundry runs through 8 phases to build complete, tested, documented, and visually documented projects automatically.

### Visual Walkthrough: Real Build Example

**Here's how Context Foundry built Evolution Quest autonomously:**

**Phase 1-2: Scout & Architect**

![Starting Research and Design](docs/screenshots/EvolutionQuestBeingBuilt.png)
*Context Foundry analyzes requirements and creates architecture plan - guided by meta-prompt workflow*

**Phase 3-4: Builder & Test**

![Implementation and Testing](docs/screenshots/BuildStatusUpdate1.png)
*Code implementation with integrated testing. Self-healing test loop validates quality.*

**Phase 4.5-5: Screenshot & Documentation**

![Capturing Screenshots](docs/screenshots/BuildStatusUpdate2.png)
*Automated screenshot capture and documentation generation - no manual steps required*

**Phase 6-7: Deployment & Feedback**

![Build Complete](docs/screenshots/BuildStatusComplete.png)
*GitHub deployment and feedback analysis for continuous self-improvement*

**The Result**

![Working Application](docs/screenshots/App_Ready_to_Play.png)
*Complete, tested, documented application deployed to GitHub - ready to use*

**Key Point:** This entire process happened **autonomously** after the initial request. No checkpoints, no manual intervention - true "walk away" development.

---

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

#### Phase 4.5: Screenshot Capture (Visual Documentation) 📸 NEW!

**What happens:**
- AI detects project type (web app, game, CLI, API, etc.)
- AI installs Playwright automatically
- AI copies screenshot capture templates to project
- AI starts dev server (for web apps/games)
- AI captures screenshots automatically:
  - **Hero screenshot**: Main application view (docs/screenshots/hero.png)
  - **Feature screenshots**: Key functionality views
  - **Workflow screenshots**: Step-by-step user journey
- AI creates manifest.json listing all screenshots
- AI stops dev server gracefully
- **If screenshot capture fails**: Logs warning, continues build (graceful degradation)

**Project Type Detection:**
- **Web Apps** (React, Vue, etc.): Full browser screenshots via Playwright
- **Games** (Canvas, WebGL): Gameplay screenshots
- **CLI Tools**: Terminal output screenshots
- **APIs**: Documentation/Postman screenshots
- **Other**: Project structure visualization or README preview

**Example Screenshot Manifest:**
```json
{
  "generated": "2025-10-19T14:30:00Z",
  "projectType": "web-app",
  "screenshots": [
    {
      "filename": "hero.png",
      "type": "hero",
      "description": "Main application view"
    },
    {
      "filename": "feature-01-navigation.png",
      "type": "feature"
    },
    {
      "filename": "step-01-initial-state.png",
      "type": "step"
    }
  ],
  "total": 6
}
```

**Why this phase is important:**
- Visual documentation significantly improves README appeal
- Step-by-step screenshots make tutorials much clearer
- Screenshots stored in GitHub make projects more discoverable
- Users can see what they're building before cloning

#### Phase 5: Documentation

**What happens:**
- AI creates comprehensive README.md **with hero screenshot**
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

🤖 Built autonomously by Context Foundry
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

🤖 Built autonomously by Context Foundry
Co-Authored-By: Claude <noreply@anthropic.com>
```

---

## Build Artifacts & Documentation

### Where to Find Everything

**Every Context Foundry build creates a `.context-foundry/` directory in your project:**

```
your-project/
├── src/                           ← Your actual code
├── tests/                         ← Test files
├── README.md                      ← Project documentation
└── .context-foundry/              ← Build artifacts (plans, logs, patterns)
    ├── scout-report.md            ← Phase 1: Research findings
    ├── architecture.md            ← Phase 2: Complete technical design
    ├── build-log.md               ← Phase 3: Implementation log
    ├── test-iteration-count.txt   ← Current test iteration number
    ├── test-results-iteration-1.md  ← Test run #1 results
    ├── test-results-iteration-2.md  ← Test run #2 (if self-healing triggered)
    ├── fixes-iteration-1.md       ← Fix strategy for iteration 1
    ├── test-final-report.md       ← Final test summary
    ├── session-summary.json       ← Complete build metadata
    ├── feedback/
    │   └── build-feedback-{timestamp}.json  ← Learnings from this build
    └── patterns/
        ├── common-issues.json     ← Patterns discovered
        ├── test-patterns.json
        ├── architecture-patterns.json
        └── scout-learnings.json
```

### Key Files Explained

#### `scout-report.md` (40-60KB)

**What it contains:**
- Task analysis and requirements breakdown
- Technology stack recommendations
- Architecture patterns to apply
- Potential challenges identified
- Prior art research
- Patterns applied from pattern library

**When to read:**
- Understand why certain technologies were chosen
- See what patterns were applied
- Review risk assessment

**Example:**
```bash
cat your-project/.context-foundry/scout-report.md
```

#### `architecture.md` (30-90KB)

**What it contains:**
- Complete system architecture
- Detailed file structure
- Module specifications and responsibilities
- Data models and schemas
- API design (if applicable)
- Component hierarchy
- State management design
- Testing strategy
- Implementation roadmap

**When to read:**
- **Before making changes** - understand the design
- **When onboarding** - learn how the system works
- **For documentation** - reference for future work

**Example:**
```bash
# View VimQuest's architecture plan
cat /Users/name/homelab/vimquest/.context-foundry/architecture.md

# View Satoshi Chore Tracker's architecture
cat /Users/name/homelab/satoshi-chore-tracker/.context-foundry/architecture.md
```

**Pro tip:** This file is comprehensive! It's like having a senior architect document your entire system.

#### `build-log.md`

**What it contains:**
- Chronological implementation log
- Files created in order
- Key decisions during building
- Challenges encountered and solutions

**When to read:**
- Understand the build sequence
- Debug issues by seeing what was built when
- Learn the Builder's approach

#### `test-results-iteration-X.md`

**What it contains:**
- Complete test output for each iteration
- Failed tests (if any)
- Error messages and stack traces
- Root cause analysis

**When to read:**
- Understand what tests failed and why
- See how self-healing diagnosed issues
- Debug persistent test failures

#### `fixes-iteration-X.md`

**What it contains:**
- Architect's analysis of test failures
- Specific code changes planned
- Rationale for each fix

**When to read:**
- Understand how self-healing fixed issues
- Learn problem-solving approach
- See the redesign → re-implement process

#### `session-summary.json`

**What it contains:**
```json
{
  "status": "completed",
  "phases_completed": ["scout", "architect", "builder", "test", "docs", "deploy", "feedback"],
  "github_url": "https://github.com/snedea/your-project",
  "files_created": ["server.js", "tests/api.test.js", ...],
  "tests_passed": true,
  "test_iterations": 2,
  "duration_minutes": 7.42,
  "patterns_applied": ["vite-educational-spa", "hash-routing-offline-first"]
}
```

**When to read:**
- Quick build overview
- Check test pass rate
- See total duration
- Get GitHub URL

### Pattern Library Locations

**Global Pattern Library** (shared across ALL builds):
```
/Users/name/homelab/context-foundry/.context-foundry/patterns/
├── common-issues.json
├── test-patterns.json
├── architecture-patterns.json
└── scout-learnings.json
```

**Per-Project Patterns** (this build's discoveries):
```
your-project/.context-foundry/patterns/
└── [Same structure]
```

**How they work together:**
1. Scout/Architect/Test phases READ global patterns
2. Patterns auto-apply if conditions match
3. New patterns discovered during build go to project directory
4. Phase 7: Feedback promotes valuable patterns to global library
5. Next build benefits from expanded pattern library

**View global patterns:**
```bash
# See all known issues and solutions
cat /Users/name/homelab/context-foundry/.context-foundry/patterns/common-issues.json

# See testing strategies learned
cat /Users/name/homelab/context-foundry/.context-foundry/patterns/test-patterns.json
```

### Reviewing Plans Before/After Build

**Option 1: Review After Build (Recommended)**

```bash
# Build completes autonomously
# Then review the plan:
cat your-project/.context-foundry/architecture.md

# If you want changes, just ask:
claude
You: "I reviewed the architecture. Can we change the database from SQLite to PostgreSQL?"
```

**Option 2: Checkpoint Mode (Review During Build)**

```python
# Use autonomous=False to pause at key phases
autonomous_build_and_deploy(
    task="Build a weather app",
    autonomous=False  # ← Enables review checkpoints
)
```

**What happens:**
1. Scout completes → Pauses → Shows scout-report.md → Waits for "Continue"
2. Architect completes → Pauses → Shows architecture.md → Waits for approval
3. Test completes → Pauses → Shows results → Waits for "Deploy"

**Example session:**
```
[Scout completes]
Assistant: Scout phase complete! Review the findings:
           cat .context-foundry/scout-report.md

           Type "Continue" to proceed to Architect phase.

You: cat .context-foundry/scout-report.md
[Review findings]

You: Continue

[Architect completes]
Assistant: Architect phase complete! Review the architecture plan:
           cat .context-foundry/architecture.md

           Type "Continue" to proceed to Builder phase, or request changes.

You: cat .context-foundry/architecture.md
[Review 90KB plan]

You: Looks good! Continue
```

### Understanding the Delegation Model

**Why your context usage stays low:**

```
┌──────────────────────────────────────┐
│ Your Claude Code Window (Main)       │
│                                       │
│ You: "Build a weather app"           │
│                                       │
│ Context Used: ~1,000 tokens (0.5%)   │
│                                       │
│ Claude: [Delegates to MCP]           │
│         ↓                             │
└─────────┼────────────────────────────┘
          │
          ↓ Spawns
┌──────────────────────────────────────┐
│ Fresh Claude Instance (Delegated)    │
│                                       │
│ Receives: orchestrator_prompt.txt    │
│                                       │
│ Context Used: ~80,000 tokens (40%)   │
│                                       │
│ ├─ Phase 1: Scout (~10K tokens)      │
│ ├─ Phase 2: Architect (~15K tokens)  │
│ ├─ Phase 3: Builder (~30K tokens)    │
│ ├─ Phase 4: Test (~8K tokens)        │
│ ├─ Phase 5: Docs (~3K tokens)        │
│ ├─ Phase 6: Deploy (~2K tokens)      │
│ └─ Phase 7: Feedback (~5K tokens)    │
│                                       │
│ Returns: "Build complete! ✅"         │
│          [Summary JSON]               │
└──────────────────────────────────────┘
          │
          ↓ Returns
┌──────────────────────────────────────┐
│ Your Claude Code Window (Main)       │
│                                       │
│ Claude: "Build complete! ✅"          │
│         GitHub: github.com/you/app   │
│         Tests: 25/25 passing         │
│                                       │
│ Context Used: ~1,500 tokens (0.75%)  │
└──────────────────────────────────────┘
```

**Key insights:**
- ✅ Main window stays clean (< 1% context usage)
- ✅ Delegated instance does all the work (can use 100% if needed)
- ✅ Agents live in delegated instance (ephemeral)
- ✅ Only artifacts persist (.context-foundry/ files)
- ✅ Multiple builds can run in parallel (separate instances)

### Agent Lifecycle

**What happens to the agents?**

```
Build Starts
    ↓
Delegated Claude instance spawned
    ↓
Orchestrator reads orchestrator_prompt.txt
    ↓
Phase 1: Scout agent created via /agents
    ├─ Researches requirements
    ├─ Writes scout-report.md
    └─ [Agent conversation DISCARDED]
    ↓
Phase 2: Architect agent created via /agents
    ├─ Reads scout-report.md (file persists)
    ├─ Designs system
    ├─ Writes architecture.md
    └─ [Agent conversation DISCARDED]
    ↓
Phase 3-7: Builder, Test, Docs, Deploy, Feedback agents
    └─ [Same pattern: use artifacts, create artifacts, discard]
    ↓
Build Completes
    ↓
Delegated Claude instance terminates
    ↓
ALL agent conversations GONE
```

**What persists:**
- ✅ All files in `.context-foundry/`
- ✅ Your actual project code
- ✅ Git commits
- ✅ GitHub repository
- ✅ Pattern library updates

**What disappears:**
- ❌ Agent conversation histories
- ❌ Delegated Claude instance
- ❌ Temporary state

**Next build:** Fresh agents read the pattern library and start clean!

### For More Details

**Comprehensive FAQ:** See [FAQ.md](FAQ.md) for:
- Complete delegation model explanation
- Where all prompts are located (orchestrator_prompt.txt, etc.)
- How Context Foundry DOESN'T change Claude's system prompt
- Why context stays low (separate instances)
- What happens to agents (ephemeral)
- Control options (autonomous vs checkpoints)

**Technical Deep Dive:** See [docs/DELEGATION_MODEL.md](docs/DELEGATION_MODEL.md) for architecture diagrams and implementation details.

---

## Real-Time Monitoring Dashboard

**NEW: Enhanced status dashboard with comprehensive metrics tracking**

Monitor your Context Foundry builds in real-time with a beautiful dark-themed web dashboard that polls MCP status and displays detailed metrics including token usage, agent performance, decision quality, and test analytics.

### Features

✅ **Real-Time Updates** - 3-5 second polling interval for near real-time status
✅ **Token Usage Tracking** - Visual gauge showing usage out of 200K budget
✅ **Agent Performance** - Track Scout, Architect, Builder, and Tester metrics
✅ **Decision Analytics** - Quality ratings, difficulty, lessons learned tracking
✅ **Test Loop Insights** - Iteration counts, success rates, failure patterns
✅ **Pattern Effectiveness** - See which patterns prevented issues
✅ **Persistent Storage** - SQLite database for historical analysis
✅ **Beautiful Dark Mode** - Easy on the eyes for overnight monitoring

### Quick Start

#### 1. Start the Dashboard

```bash
cd ~/context-foundry
./tools/start_livestream.sh
```

The script will:
- Check dependencies (FastAPI, uvicorn, etc.)
- Initialize the metrics database (~/.context-foundry/metrics.db)
- Start the server on http://localhost:8080
- Open the dashboard in your browser

#### 2. Run a Task

In another terminal, start a Context Foundry task:

```bash
# Example: Async build
foundry build my-app "Build a todo app with REST API" --async

# The dashboard will automatically detect and display the task
```

#### 3. Monitor in Real-Time

The dashboard will show:
- **Current Phase**: Scout → Architect → Builder → Test → Deploy
- **Progress**: Tasks completed vs remaining
- **Token Usage**: Visual gauge with color-coded warning levels
- **Live Logs**: Streaming output from the build
- **Detailed Metrics**: Agent performance, decisions, test iterations

### Dashboard Panels

#### Main Status Panel
- **Session Selector**: Switch between active tasks
- **Phase Indicator**: Current phase with gradient color coding
- **Elapsed Time**: How long the task has been running
- **Iteration Count**: Number of context resets / healing loops

#### Context Usage
- Progress bar showing token usage out of 200K budget
- Color-coded: Green (safe), Yellow (warning >50%), Red (critical >75%)
- Real-time updates as task progresses

#### Task Progress
- List of completed tasks (✓)
- Currently executing task (⏳)
- Pending tasks (○)
- Progress percentage bar

#### Token Usage Panel 🔢
- **Used / Budget**: e.g., "45,234 / 200,000"
- **Visual Gauge**: Gradient progress bar (green→yellow→red)
- **Warning Thresholds**:
  - **Safe**: < 50% (green)
  - **Warning**: 50-75% (yellow)
  - **Critical**: > 75% (red - pulses)
- Updates every 3-5 seconds

#### Test Loop Analytics 🧪
- **Total Iterations**: Number of test/fix cycles
- **Success Rate**: Percentage of tests passing
- **Iteration History**: Last 3 iterations with pass/fail counts
- **Visual Indicators**: Green ✓ for passing, Red ✗ for failing

#### Agent Performance 🤖
- **Per-Agent Cards**: Scout, Architect, Builder, Tester
- **Metrics**:
  - Execution time
  - Success/failure status
  - Issues found vs fixed
  - Files created/modified
- **Hover Effects**: Cards highlight on mouseover

#### Decision Quality 🧠
- **Total Decisions**: Count of autonomous decisions made
- **Average Quality**: Rating 1-5 (Low, Medium, High)
- **Lessons Applied**: Number of times past patterns were used
- **Recent Decisions**: Last 3 decisions with quality badges
- **Color Coding**:
  - High quality: Green
  - Medium quality: Yellow
  - Low quality: Red
- **Lessons Indicator**: Purple 📚 icon when lessons were applied

### Configuration

#### Environment Variables

```bash
# Server configuration
export LIVESTREAM_PORT=8080
export LIVESTREAM_HOST=0.0.0.0

# Polling interval (seconds)
export POLL_INTERVAL_SECONDS=4  # 3-5 recommended

# Database location
export CF_METRICS_DB="$HOME/.context-foundry/metrics.db"

# Enable enhanced metrics
export ENABLE_METRICS=true
```

#### Polling Interval

The default 3-5 second polling interval balances:
- **Freshness**: Near real-time updates
- **Overhead**: Minimal API traffic
- **Responsiveness**: Smooth UI updates

To adjust:
```bash
# Aggressive (1-2 seconds) - for active monitoring
export POLL_INTERVAL_SECONDS=2

# Balanced (3-5 seconds) - recommended
export POLL_INTERVAL_SECONDS=4

# Conservative (10 seconds) - for long-running tasks
export POLL_INTERVAL_SECONDS=10
```

### API Endpoints

The dashboard provides a REST API for programmatic access:

```bash
# List all active MCP tasks
curl http://localhost:8080/api/mcp/tasks

# Get task status
curl http://localhost:8080/api/mcp/task/{task_id}

# Get comprehensive metrics
curl http://localhost:8080/api/metrics/{task_id}

# Get historical data
curl http://localhost:8080/api/metrics/historical

# Get decision analytics
curl http://localhost:8080/api/analytics/decisions

# Get agent performance analytics
curl http://localhost:8080/api/analytics/agents

# Get token usage status
curl http://localhost:8080/api/token/status/{task_id}

# Health check
curl http://localhost:8080/api/health
```

### Metrics Database

All metrics are persisted to SQLite for historical analysis:

```bash
# Database location
~/.context-foundry/metrics.db

# Tables:
# - tasks: Main task tracking
# - metrics: Time-series metrics per task
# - decisions: Autonomous decision tracking
# - agent_performance: Per-agent metrics
# - test_iterations: Test loop analytics
# - pattern_effectiveness: Pattern usage tracking
```

#### Querying Metrics

```bash
# Access the database
sqlite3 ~/.context-foundry/metrics.db

# Example queries:
sqlite> SELECT COUNT(*) FROM tasks;
sqlite> SELECT project_name, status, duration_seconds FROM tasks ORDER BY start_time DESC LIMIT 10;
sqlite> SELECT agent_type, AVG(duration_seconds), COUNT(*) FROM agent_performance GROUP BY agent_type;
sqlite> SELECT AVG(quality_rating), COUNT(*) FROM decisions WHERE used_lessons_learned = 1;
```

### Self-Improvement Integration

The dashboard tracks metrics that help Context Foundry improve itself:

1. **Decision Quality Tracking**
   - Rates every autonomous decision (1-5)
   - Tracks difficulty level
   - Flags regrettable decisions to learn from
   - Measures effectiveness of lessons learned

2. **Pattern Effectiveness**
   - Tracks which patterns were applied
   - Measures if they prevented issues
   - Correlates pattern usage with success rates
   - Builds data for pattern refinement

3. **Agent Performance Analysis**
   - Measures time spent per agent type
   - Tracks success rates by phase
   - Identifies bottlenecks and inefficiencies
   - Optimizes workflow over time

4. **Test Loop Analytics**
   - Monitors test iteration trends
   - Identifies common failure patterns
   - Measures fix effectiveness
   - Reduces iterations over time through learning

### Dark Mode Design

The dashboard uses a carefully crafted dark theme:

- **Background**: Deep black (#0a0a0a) for OLED-friendly viewing
- **Panels**: Dark gray (#111827) with subtle borders
- **Text**: High contrast (#e0e0e0) for readability
- **Accents**: Vibrant gradients for phase indicators
- **Hover Effects**: Smooth transitions and subtle glows
- **Color Coding**:
  - Green: Success, safe levels
  - Yellow: Warnings, caution
  - Red: Critical, failures
  - Blue: Info, in-progress
  - Purple: Lessons learned, special features

Perfect for overnight monitoring sessions!

### Remote Access

#### With ngrok (Recommended)

```bash
# Start dashboard with public URL
USE_NGROK=true ./tools/start_livestream.sh

# You'll get:
# - Local URL: http://localhost:8080
# - Public URL: https://xxxx.ngrok.io
# - QR Code: Scan with phone to access remotely
```

#### Local Network

```bash
# Find your local IP
ifconfig | grep "inet "

# Access from other devices on same network
# http://YOUR_IP:8080
```

### Troubleshooting Dashboard

#### Server Won't Start

```bash
# Check if port is in use
lsof -i :8080

# Kill existing server
lsof -ti:8080 | xargs kill -9

# Check logs
tail -f /tmp/livestream.log
```

#### Dashboard Not Updating

1. **Check WebSocket Connection**: Look for green "Connected" indicator
2. **Verify Task is Running**: Ensure Context Foundry task is active
3. **Check Browser Console**: Press F12, look for errors
4. **Refresh Page**: Force reload with Cmd+Shift+R (Mac) or Ctrl+Shift+R
5. **Check Enhanced Metrics**: If disabled, some panels may not populate

#### Enhanced Metrics Not Available

If you see "⚠️ Enhanced metrics not available":

```bash
# Install missing dependencies
cd ~/context-foundry/tools/livestream
pip3 install -r requirements.txt

# Restart server
./tools/start_livestream.sh
```

#### Database Errors

```bash
# Reinitialize database
python3 -c "
from tools.livestream.metrics_db import get_db
db = get_db()
print('Database initialized at:', db.db_path)
"

# Check database integrity
sqlite3 ~/.context-foundry/metrics.db "PRAGMA integrity_check;"
```

### Performance

- **Latency**: < 100ms from task update to dashboard
- **Resource Usage**: ~50MB RAM for server
- **Concurrent Sessions**: Tested with 10+ simultaneous tasks
- **WebSocket Limit**: 100 concurrent connections
- **Database Size**: ~1-5MB per 100 tasks

### Best Practices

1. **Start Dashboard Before Tasks**: Launch dashboard first, then start builds
2. **Monitor Token Usage**: Watch for yellow/red warnings
3. **Review Decision Quality**: Identify patterns in high vs low quality decisions
4. **Analyze Test Failures**: Use test loop panel to spot recurring issues
5. **Export Data**: Periodically export session data for analysis
6. **Clean Up Old Tasks**: Archive completed tasks to keep dashboard responsive

### Future Enhancements

Planned features:
- [ ] Historical session comparison
- [ ] Performance trend graphs
- [ ] Desktop notifications on completion
- [ ] Mobile app
- [ ] Video recording of sessions
- [ ] Multi-user authentication
- [ ] Session sharing via URL
- [ ] Pattern library visualization
- [ ] Cost estimation improvements
- [ ] Integration with GitHub Issues

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
cd /path/to/context-foundry
claude mcp remove context-foundry -s project
claude mcp add --transport stdio context-foundry -s project -- $(pwd)/venv/bin/python $(pwd)/tools/mcp_server.py
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
claude
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
1. Verify MCP configuration: `cat .mcp.json` (project-scoped) or `claude mcp list` (global)
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
   - [ARCHITECTURE_DECISIONS.md](ARCHITECTURE_DECISIONS.md) for deep dives and 1.x vs 2.0 comparison

### Learning More

- **README.md** - Quick reference and overview
- **ARCHITECTURE_DECISIONS.md** - Technical deep dives and what's new in 2.0
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
claude
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

**Check MCP configuration:**
```bash
# For project-scoped config
cat .mcp.json

# For global config
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
