# CLAUDE.md - AI Assistant Guide to Context Foundry

**Last Updated:** 2025-11-24
**Version:** 2.4.0
**Purpose:** Comprehensive guide for AI assistants working with the Context Foundry codebase

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Codebase Structure](#codebase-structure)
3. [Development Setup](#development-setup)
4. [Key Technologies & Dependencies](#key-technologies--dependencies)
5. [Architecture Patterns](#architecture-patterns)
6. [Development Workflows](#development-workflows)
7. [Testing & Quality Assurance](#testing--quality-assurance)
8. [Coding Conventions](#coding-conventions)
9. [Common Tasks & How-Tos](#common-tasks--how-tos)
10. [Important Files & Their Purposes](#important-files--their-purposes)
11. [Gotchas & Things to Know](#gotchas--things-to-know)

---

## Project Overview

### What is Context Foundry?

Context Foundry is an **MCP (Model Context Protocol) server** that enables autonomous software development through recursive Claude spawning. It uses a Meta-MCP architecture where Claude orchestrates fresh Claude instances to build complete projects autonomously.

**Core Philosophy:** "The AI That Builds Itself" - Users describe what they want and walk away while the system researches, designs, builds, tests, documents, and deploys their application.

### Key Statistics

- **Language:** Python 3.10+ (374 Python files)
- **Package Name:** `context-foundry`
- **Current Version:** 2.4.0 (November 2025)
- **License:** MIT
- **Entry Points:**
  - `cf` - Mission Control TUI
  - `cfd` - CF Daemon CLI
  - `python tools/mcp_server.py` - MCP Server

### Core Features

1. **BAML Type-Safe Outputs** - Structured JSON outputs for reliable, first-try success
2. **Mission Control TUI** - Terminal interface for real-time build monitoring and chat
3. **Context Codex** - Database-backed self-learning system that remembers patterns
4. **Intelligent Parallel Build** - AI automatically decides when to spawn parallel agents
5. **Self-Healing Test Loop** - Automatically fixes test failures without intervention
6. **Meta-MCP Architecture** - Recursively spawns fresh Claude instances with full context windows

---

## Codebase Structure

### Directory Layout

```
/home/user/context-foundry/
├── context_foundry/          # Core Python package (daemon & storage)
│   ├── daemon/              # CF Daemon - background job orchestration
│   │   ├── server.py        # Main daemon server (FastAPI/ASGI)
│   │   ├── runner.py        # Job execution engine (1,100+ lines)
│   │   ├── jobs.py          # Job management & worker pool
│   │   ├── store.py         # SQLite persistence layer
│   │   └── models.py        # Domain models (Job, JobStatus, PhaseEvent)
│   └── storage/             # S3 pattern sync
│
├── tools/                    # Main application code (205 Python files)
│   ├── mcp_server.py        # 🎯 MAIN MCP SERVER ENTRY POINT (1,639 lines)
│   ├── cli.py               # 🎯 CLI ENTRY POINT (cf command)
│   ├── baml_integration.py  # BAML type-safe LLM integration (34KB)
│   │
│   ├── mcp_utils/           # Modularized MCP server utilities
│   │   ├── autonomous_build.py    # Main build orchestration (87KB)
│   │   ├── delegation.py          # Claude Code delegation (50KB)
│   │   ├── phase_execution.py     # Phase execution logic (52KB)
│   │   ├── pattern_management.py  # Pattern sync & merge (38KB)
│   │   └── project_detection.py   # Project/codebase detection (19KB)
│   │
│   ├── evolution/           # Mission Control TUI & Evolution System
│   │   ├── mission_control.py  # Main TUI application (73KB)
│   │   ├── daemon.py           # Evolution daemon (78KB)
│   │   └── task_queue.py       # Task management (21KB)
│   │
│   ├── baml_schemas/        # BAML type definitions (source)
│   │   ├── main.baml            # Generator config
│   │   ├── phase_tracking.baml  # PhaseInfo types
│   │   ├── scout.baml           # Scout phase types
│   │   ├── architect.baml       # Architect phase types
│   │   └── builder.baml         # Builder phase types
│   │
│   └── baml_client/         # Generated BAML Python client
│       └── baml_client/
│           ├── async_client.py  # Async BAML client
│           ├── sync_client.py   # Sync BAML client
│           └── types.py         # Type definitions
│
├── extensions/               # Domain-specific extensions
│   ├── flowise/             # Flowise integration
│   ├── roblox/              # Roblox game development
│   └── workday/             # Workday integration
│
├── integrations/             # Third-party integrations
│   └── baml/                # BAML integration examples
│
├── tests/                    # Comprehensive test suite (74 test files)
│   ├── test_baml_*.py       # BAML integration tests
│   ├── test_daemon_*.py     # Daemon tests
│   └── test_mcp_server_*.py # MCP server tests
│
├── docs/                     # Documentation (299 markdown files)
│   ├── ARCHITECTURE.md      # System architecture
│   ├── FEATURES.md          # Feature documentation
│   ├── BAML_INTEGRATION.md  # BAML guide
│   └── CONTRIBUTING.md      # Contribution guidelines
│
├── scripts/                  # Automation & bootstrap scripts
├── config/                   # Configuration templates
├── templates/                # Project templates
├── schemas/                  # JSON schemas
└── archive/                  # Legacy code & documentation
```

### Key Modules Deep Dive

#### 1. MCP Server (`tools/mcp_server.py`)

**The heart of Context Foundry** - 1,639 lines exposing 40+ MCP tools to Claude.

**Primary Functions:**
- `delegate_to_claude_code()` - Spawn fresh Claude instance
- `autonomous_build_and_deploy()` - Main build orchestration
- `read_global_patterns()` / `save_global_patterns()` - Pattern management
- `create_evolution_task()` - Create autonomous task
- `save_skill()` / `search_skills()` - Skills management

**Architecture:** Uses `fastmcp` library for MCP protocol implementation.

#### 2. CF Daemon (`context_foundry/daemon/`)

**Background service** for persistent job management.

**Components:**
- **Server** (`server.py`): FastAPI-based daemon with PID management
- **Runner** (`runner.py`): Job execution engine, delegates to Claude Code CLI
- **JobManager** (`jobs.py`): Thread pool executor for concurrent jobs
- **Store** (`store.py`): SQLite persistence (jobs, logs, phase events)
- **Models** (`models.py`): Domain models (Job, JobStatus, JobType)

**Features:**
- Unix double-fork daemonization
- Signal handling (SIGTERM, SIGINT, SIGHUP)
- Working directory locking
- Graceful shutdown
- Job persistence across restarts

#### 3. BAML Integration (`tools/baml_integration.py`)

**Type-safe LLM outputs** replacing fragile JSON parsing.

**Key Features:**
- Structured outputs using BAML schemas
- Compile-time validation
- 5% → <1% error rate improvement
- Client caching for performance

**BAML Schemas Location:** `tools/baml_schemas/`
- `phase_tracking.baml` - PhaseInfo, PhaseType, PhaseStatus enums
- `scout.baml` - Scout phase outputs
- `architect.baml` - Architect phase outputs
- `builder.baml` - Builder phase outputs
- `build_planning.baml` - Build planning structures

#### 4. Evolution System (`tools/evolution/`)

**Mission Control TUI** - Interactive terminal interface for build monitoring.

**Key Modules:**
- `mission_control.py` - Main TUI app (Textual framework)
- `daemon.py` - Evolution daemon (autonomous task execution)
- `task_queue.py` - Task scheduling & priority
- `command_server.py` - Inter-process communication

---

## Development Setup

### Prerequisites

- **Python 3.10+** (required for structural pattern matching and advanced type hints)
- **Git** (for version control)
- **GitHub CLI** (`gh`) - for deployment features
- **Virtual environment** (recommended, required on Debian/Ubuntu)

### Installation Steps

```bash
# 1. Clone the repository
cd ~/homelab  # or your preferred location
git clone https://github.com/context-foundry/context-foundry.git
cd context-foundry

# 2. Create virtual environment
python3 -m venv venv

# 3. ⚠️ CRITICAL: Activate the virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 4. Install MCP server dependencies
pip install -r requirements-mcp.txt

# 5. Verify installation
python -c "from fastmcp import FastMCP; print('✅ MCP dependencies installed!')"

# 6. (Optional) Install BAML dependencies
pip install -r requirements-baml.txt

# 7. (Optional) Install AWS dependencies for pattern sync
pip install -r requirements-aws.txt
```

### Configuration

#### 1. Environment Variables (`.env`)

Create a `.env` file from `.env.example`:

```bash
cp .env.example .env
```

**Key Variables:**
```bash
# AI Provider Configuration
SCOUT_PROVIDER=anthropic
SCOUT_MODEL=claude-sonnet-4-5-20250929

ARCHITECT_PROVIDER=anthropic
ARCHITECT_MODEL=claude-sonnet-4-5-20250929

BUILDER_PROVIDER=anthropic
BUILDER_MODEL=claude-sonnet-4-5-20250929

# API Keys
ANTHROPIC_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here  # Optional
GITHUB_TOKEN=your_token_here  # For deployment

# Incremental Builds (Phase 2)
INCREMENTAL_PHASE2_ENABLED=true
GLOBAL_SCOUT_CACHE_ENABLED=true
CHANGE_DETECTION_ENABLED=true
```

#### 2. MCP Server Configuration (`.mcp.json`)

For Claude Code integration:

```bash
# Add MCP server to Claude Code (project scope)
claude mcp add --transport stdio context-foundry -s project -- \
  $(pwd)/venv/bin/python $(pwd)/tools/mcp_server.py
```

This creates `.mcp.json` in the project directory.

#### 3. Starting the Daemon

```bash
# Start the CF Daemon
./tools/cfd start

# Verify it's running
./tools/cfd status

# Expected output:
# CF Daemon is running (PID: 12345)
# Jobs: 0 queued, 0 running, 0 completed
```

### Verifying Setup

```bash
# 1. Check Python version
python --version  # Should be 3.10+

# 2. Verify dependencies
python -c "import fastmcp, baml_py, textual; print('✅ All dependencies installed!')"

# 3. Test MCP server (run in separate terminal)
python tools/mcp_server.py

# 4. Check daemon status
./tools/cfd status

# 5. Launch Mission Control TUI
cf
```

---

## Key Technologies & Dependencies

### Core Dependencies

**From `requirements.txt` & `setup.py`:**

```python
# MCP Server Framework
fastmcp>=2.0.0              # Model Context Protocol implementation
nest-asyncio>=1.5.0         # Nested event loop support

# BAML - Type-safe LLM outputs
baml-py>=0.211.0            # BAML Python runtime

# TUI Framework
textual>=0.50.0             # Modern terminal UI framework

# Token Management
tiktoken>=0.5.0             # OpenAI token counter

# System Utilities
psutil>=5.9.0               # Process and system monitoring
watchdog>=3.0.0             # File system monitoring

# Optional: AWS Integration
boto3>=1.26.0               # S3 pattern sync (requirements-aws.txt)
```

### Python Version Requirements

**Python 3.10+** required for:
- Structural pattern matching (`match` statements)
- Advanced type hints (`TypeAlias`, `ParamSpec`)
- Better error messages
- Performance improvements

**Version Enforcement:** Both `setup.py` and `tools/cli.py` enforce Python 3.10+ with helpful error messages.

### External Services & APIs

**AI Providers** (configurable per phase):
- Anthropic Claude (default): Sonnet 4.5, Opus 4
- OpenAI GPT: GPT-4o, GPT-4o-mini
- Google Gemini
- GitHub Models (free GPT-4o)
- Groq, Mistral, Fireworks, Z.ai

**Storage:**
- SQLite 3.8.0+ (daemon job store, Context Codex)
- AWS S3 (community pattern sync - optional)

**Integrations:**
- GitHub CLI (`gh`) for PR creation & deployment
- Discord webhooks (optional notifications)
- Slack webhooks (optional notifications)

### Development Tools

**Code Quality:**
- `ruff` - Fast Python linter & formatter
- `pre-commit` - Git hooks for linting
- `pytest` - Testing framework

**CI/CD** (`.github/workflows/`):
- `ci.yml` - Continuous integration
- `nightly-release.yml` - Automated releases
- `daily-pattern-sync.yml` - S3 pattern sync
- `validate-patterns.yml` - Pattern validation

---

## Architecture Patterns

### 1. Meta-MCP Pattern

**Recursive Claude spawning:**

```
Claude Session (Parent)
  └─> MCP Server (tools/mcp_server.py)
       └─> delegate_to_claude_code()
            └─> Fresh Claude Instance (Child)
                 └─> Autonomous build execution
                      └─> Results returned to parent
```

**Key Insight:** Fresh Claude instances have clean context windows, enabling unlimited-length sessions while maintaining <40% context utilization.

### 2. Phase-Based Build System

**Scout → Architect → Builder → Test → Deploy**

```python
# Each phase is type-safe (BAML)
# Phase tracking in SQLite
# Real-time progress monitoring (TUI)
# Self-healing test loops

Phase 1: Scout (1-2 min)
  - Research best practices
  - Analyze complexity for parallel detection
  - Output: ScoutReport (BAML type-safe)

Phase 2: Architect (1-2 min)
  - Design system architecture
  - Create implementation plan
  - Output: ArchitectureBlueprint (BAML type-safe)

Phase 3: Builder (2-5 min)
  - Write all code + tests
  - Parallel building if recommended
  - Output: BuilderResult (BAML type-safe)

Phase 4: Test (1-2 min)
  - Run all tests
  - Auto-fix failures (self-healing)
  - Output: TestResults

Phase 5: Screenshot (30 sec)
  - Capture visual documentation
  - Output: Screenshots

Phase 6: Document (1 min)
  - Create README with screenshots
  - Output: Documentation

Phase 7: Deploy (30 sec)
  - Push to GitHub
  - Output: Deployment URL

Phase 8: Feedback (10 sec)
  - Learn patterns → Context Codex database
  - Output: Learned patterns
```

### 3. Stateless Conversation Architecture

**Problem:** Traditional AI coding sessions fill context windows after 50-100 messages.

**Solution:** Multiple short, focused conversations with state persisted to files.

```python
# Traditional (bloats context)
conversation_history = [
    {"role": "user", "content": "Build a todo app"},
    {"role": "assistant", "content": "Here's the implementation... [2,000 tokens]"},
    {"role": "user", "content": "Add authentication"},
    {"role": "assistant", "content": "Adding auth... [3,000 tokens]"},
    # ... [After 20 interactions: 80,000 tokens, 80% context filled]
]

# Context Foundry (resets context)
Scout Conversation (fresh):
  User: "Research this codebase"
  AI: "Here's the architecture... [5,000 tokens]"
  [SAVE to RESEARCH.md]
  🔄 RESET → conversation_history = []

Architect Conversation (fresh):
  User: "Read RESEARCH.md and create plan"
  AI: "Here's the plan... [8,000 tokens]"
  [SAVE to PLAN.md]
  🔄 RESET → conversation_history = []
```

**Benefits:**
- Each conversation uses only 10-40% of context window
- Can run for hours/days without hitting limits
- No token waste re-sending old messages
- Fresh perspective for each phase/task

### 4. Pattern Learning System

**Community-driven improvement:**

```python
1. Build completes successfully
2. Patterns extracted automatically
3. Merged with global patterns
4. Synced to S3 (optional)
5. Shared across community
6. Future builds use learned patterns
```

**Pattern Storage:**
- Local: `~/.context-foundry/patterns/`
- S3: `bedrock-builder-kb-898587418237/community-patterns/`

**Pattern Categories:**
- `common-issues` - Known issues and solutions
- `scout-learnings` - Research findings
- `build-metrics` - Performance data

### 5. Incremental Build System (Phase 2)

**70-90% speedup on rebuilds:**

```python
# Features:
- Global Scout cache (7-day TTL)
- Change detection (git diff + SHA256)
- Incremental Builder (file preservation)
- Test impact analysis (selective test execution)
- Incremental documentation

# Configuration (.env):
INCREMENTAL_PHASE2_ENABLED=true
GLOBAL_SCOUT_CACHE_ENABLED=true
GLOBAL_SCOUT_CACHE_TTL_HOURS=168
CHANGE_DETECTION_ENABLED=true
INCREMENTAL_BUILDER_ENABLED=true
TEST_IMPACT_ANALYSIS_ENABLED=true
```

### 6. BAML Type-Safety Pattern

**Problem:** JSON parsing errors, missing fields, type mismatches.

**Solution:** BAML compile-time validation.

```python
# Before BAML (fragile)
response = claude.messages.create(...)
data = json.loads(response.content)  # Might fail!
phase_type = data.get("phase_type", "unknown")  # No guarantees

# After BAML (type-safe)
from baml_client import b

phase_info = b.TrackPhase(
    instructions="Create authentication system",
    context="Scout phase complete"
)
# ✅ Guaranteed to have all required fields
# ✅ Types validated at compile-time
# ✅ 5% → <1% error rate
```

---

## Development Workflows

### Workflow 1: Adding a New MCP Tool

**Steps:**

1. **Define the tool in `tools/mcp_server.py`:**

```python
@mcp.tool()
async def my_new_tool(
    param1: str,
    param2: int = 5
) -> str:
    """
    Brief description of what the tool does.

    Args:
        param1: Description of parameter 1
        param2: Description of parameter 2 (default: 5)

    Returns:
        Description of return value
    """
    # Implementation
    result = do_something(param1, param2)
    return result
```

2. **Add implementation logic (if complex, extract to `tools/mcp_utils/`):**

```python
# tools/mcp_utils/my_feature.py
def do_something(param1: str, param2: int) -> str:
    """Implementation of the feature."""
    # Complex logic here
    return result
```

3. **Add tests:**

```python
# tests/test_my_feature.py
import pytest
from tools.mcp_utils.my_feature import do_something

def test_do_something():
    result = do_something("test", 5)
    assert result == expected_value
```

4. **Update documentation:**

```markdown
# docs/MCP_TOOLS.md
## my_new_tool

Description of the tool...

**Parameters:**
- `param1` (str): Description
- `param2` (int, optional): Description (default: 5)

**Example:**
...
```

5. **Test locally:**

```bash
# Run tests
pytest tests/test_my_feature.py

# Start MCP server
python tools/mcp_server.py

# Test in Claude Code
claude
# Then use the tool
```

### Workflow 2: Adding a New BAML Schema

**Steps:**

1. **Define the schema in `tools/baml_schemas/`:**

```baml
// tools/baml_schemas/my_feature.baml

class MyFeatureRequest {
  name string @description("Feature name")
  priority int @description("Priority 1-10")
  tags string[] @description("Feature tags")
}

class MyFeatureResponse {
  success bool
  message string
  data MyFeatureData?
}

class MyFeatureData {
  id string
  created_at string
}

function ExtractMyFeature(input: string) -> MyFeatureRequest {
  client claude-sonnet-4-5
  prompt #"
    Extract feature request details from: {{ input }}

    Return structured data.
  "#
}
```

2. **Regenerate BAML client:**

```bash
cd tools
baml-cli generate
```

This updates `tools/baml_client/baml_client/` with new types.

3. **Use in Python code:**

```python
from tools.baml_integration import get_baml_client
from tools.baml_client.baml_client import b

baml = get_baml_client()

# Use the function
feature_request = baml.ExtractMyFeature("Build a todo app with authentication")

print(feature_request.name)  # Type-safe!
print(feature_request.priority)  # Type-safe!
```

4. **Add tests:**

```python
# tests/test_baml_my_feature.py
from tools.baml_integration import get_baml_client
from tools.baml_client.baml_client import b

def test_extract_my_feature():
    baml = get_baml_client()
    result = baml.ExtractMyFeature("Build a todo app")

    assert isinstance(result.name, str)
    assert 1 <= result.priority <= 10
```

### Workflow 3: Modifying Build Phases

**Steps:**

1. **Understand the phase system:**

Phase execution is in `tools/mcp_utils/phase_execution.py`.

Each phase has:
- Entry function (e.g., `execute_scout_phase()`)
- BAML schema for outputs (e.g., `tools/baml_schemas/scout.baml`)
- Result validation
- Phase tracking

2. **Modify the phase logic:**

```python
# tools/mcp_utils/phase_execution.py

async def execute_scout_phase(
    task: str,
    working_directory: str,
    ...
) -> Dict[str, Any]:
    """Execute Scout phase with research and analysis."""

    # Your modifications here
    # ...

    # BAML type-safe output
    scout_report = baml.GenerateScoutReport(...)

    return {
        "status": "success",
        "report": scout_report,
        ...
    }
```

3. **Update BAML schema if needed:**

```baml
// tools/baml_schemas/scout.baml

class ScoutReport {
  // Add new fields
  my_new_field string @description("New feature")

  // Existing fields...
}
```

4. **Test the phase:**

```bash
# Run phase-specific tests
pytest tests/test_phase_execution.py -k scout

# Run full integration test
pytest tests/test_autonomous_build.py
```

### Workflow 4: Contributing to the Project

**Steps:**

1. **Fork and clone:**

```bash
git clone https://github.com/YOUR_USERNAME/context-foundry.git
cd context-foundry
git checkout -b feature/my-new-feature
```

2. **Make changes:**

- Follow coding conventions (see [Coding Conventions](#coding-conventions))
- Add tests for all new functionality
- Update documentation

3. **Run pre-commit hooks:**

```bash
# Install pre-commit hooks
pip install pre-commit
pre-commit install

# Run manually
pre-commit run --all-files
```

4. **Run tests:**

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=context_foundry --cov=tools --cov-report=html
```

5. **Commit and push:**

```bash
git add .
git commit -m "feat: Add my new feature"
git push origin feature/my-new-feature
```

6. **Create pull request:**

- Go to GitHub
- Create PR from your branch to `main`
- Fill out PR template with:
  - Description of changes
  - Testing performed
  - Breaking changes (if any)

---

## Testing & Quality Assurance

### Test Structure

**Test Organization:** `tests/` directory with 74 test files

```
tests/
├── test_baml_*.py           # BAML integration tests
├── test_daemon_*.py         # Daemon tests
├── test_mcp_server_*.py     # MCP server tests
├── test_evolution_*.py      # Evolution system tests
├── test_cache_*.py          # Caching system tests
└── test_incremental_*.py    # Incremental builds
```

### Test Configuration (`pytest.ini`)

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*

# Test markers
markers =
    unit: Unit tests
    integration: Integration tests
    tier1: Critical (MUST PASS)
    tier2: Important
    tier3: Nice-to-have
    slow: Long-running tests
    requires_api: External API tests
    requires_db: Database tests
```

### Running Tests

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_baml_integration.py

# Run by marker
pytest -m tier1  # Critical tests only
pytest -m unit   # Unit tests only
pytest -m "not slow"  # Skip slow tests

# Run with coverage
pytest --cov=context_foundry --cov=tools --cov-report=html

# Run with verbose output
pytest -v

# Run specific test function
pytest tests/test_baml_integration.py::test_baml_client_creation -v
```

### Pre-commit Hooks

**Configuration:** `.pre-commit-config.yaml`

**Hooks:**
1. Ruff linter (`ruff check --fix`)
2. Ruff formatter (`ruff format`)
3. Debug statement checker (breakpoint, pdb)
4. Large file checker (>500KB, excludes images)
5. Trailing whitespace
6. End-of-file fixer
7. YAML/JSON validation
8. Merge conflict detection
9. Private key detection

**Installation:**

```bash
pip install pre-commit
pre-commit install
```

**Manual run:**

```bash
pre-commit run --all-files
```

### Code Quality Standards

**Ruff Configuration:** `pyproject.toml`

```toml
[tool.ruff]
exclude = ["extensions/flowise/integration/*.py"]

[tool.ruff.lint]
ignore-init-module-imports = true
```

**Standards:**
- PEP 8 compliance
- Type hints for all functions
- Docstrings for all public APIs
- No debug statements (breakpoint, pdb) in commits
- No trailing whitespace
- Files end with newline

### Writing Good Tests

**Example:**

```python
import pytest
from tools.mcp_utils.my_feature import my_function

@pytest.mark.unit
@pytest.mark.tier1
def test_my_function_success():
    """Test my_function with valid input."""
    result = my_function("valid_input")
    assert result == "expected_output"

@pytest.mark.unit
@pytest.mark.tier2
def test_my_function_error():
    """Test my_function with invalid input."""
    with pytest.raises(ValueError, match="Invalid input"):
        my_function("invalid_input")

@pytest.mark.integration
@pytest.mark.requires_api
def test_my_function_with_api():
    """Test my_function with external API."""
    # This test requires API credentials
    result = my_function_with_api()
    assert result.status == "success"
```

**Best Practices:**
- One assertion per test (when possible)
- Clear test names describing what is tested
- Use fixtures for common setup
- Mock external dependencies
- Test both success and failure cases

---

## Coding Conventions

### Python Style Guide

**General:**
- Follow PEP 8
- Use type hints for all functions
- Maximum line length: 88 characters (Ruff default)
- Use double quotes for strings

**Example:**

```python
from typing import Dict, List, Optional

def process_data(
    input_data: str,
    config: Dict[str, any],
    options: Optional[List[str]] = None
) -> Dict[str, any]:
    """
    Process input data according to configuration.

    Args:
        input_data: Raw input string to process
        config: Configuration dictionary with processing options
        options: Optional list of additional options

    Returns:
        Dictionary containing processed results with keys:
        - "status": Processing status ("success" or "error")
        - "data": Processed data
        - "metadata": Processing metadata

    Raises:
        ValueError: If input_data is empty or invalid

    Example:
        >>> config = {"mode": "fast"}
        >>> result = process_data("sample", config)
        >>> result["status"]
        'success'
    """
    if not input_data:
        raise ValueError("input_data cannot be empty")

    # Implementation
    result = {
        "status": "success",
        "data": processed_data,
        "metadata": metadata
    }

    return result
```

### Naming Conventions

**Files:**
- Python modules: `lowercase_with_underscores.py`
- BAML schemas: `lowercase_with_underscores.baml`
- Test files: `test_feature_name.py`

**Variables:**
- Variables: `lowercase_with_underscores`
- Constants: `UPPERCASE_WITH_UNDERSCORES`
- Classes: `PascalCase`
- Functions: `lowercase_with_underscores`

**Examples:**

```python
# Constants
MAX_RETRIES = 3
DEFAULT_TIMEOUT = 60

# Classes
class ClaudeClient:
    pass

class PhaseExecutor:
    pass

# Functions
def execute_scout_phase():
    pass

def get_baml_client():
    pass

# Variables
user_input = "example"
phase_result = execute_phase()
```

### Docstrings

**Use Google-style docstrings:**

```python
def my_function(arg1: str, arg2: int) -> bool:
    """
    One-line summary.

    Longer description if needed, explaining the purpose,
    behavior, and any important details.

    Args:
        arg1: Description of arg1
        arg2: Description of arg2

    Returns:
        Description of return value

    Raises:
        ValueError: When arg1 is invalid
        RuntimeError: When operation fails

    Example:
        >>> my_function("test", 5)
        True
    """
    pass
```

### Type Hints

**Always use type hints:**

```python
from typing import Dict, List, Optional, Union, Tuple

# Simple types
def get_name() -> str:
    return "Context Foundry"

def get_count() -> int:
    return 42

# Optional types
def find_user(user_id: str) -> Optional[Dict[str, any]]:
    # Returns dict or None
    pass

# Union types
def process(value: Union[str, int]) -> str:
    # Accepts str or int
    pass

# Complex types
def get_results() -> List[Dict[str, any]]:
    # Returns list of dicts
    pass

# Tuples
def get_stats() -> Tuple[int, int, float]:
    # Returns (count, total, average)
    pass
```

### Error Handling

**Use specific exceptions:**

```python
# Good
if not input_data:
    raise ValueError("input_data cannot be empty")

if not os.path.exists(file_path):
    raise FileNotFoundError(f"File not found: {file_path}")

# Bad
if not input_data:
    raise Exception("Error")  # Too generic
```

**Catch specific exceptions:**

```python
# Good
try:
    data = json.loads(json_string)
except json.JSONDecodeError as e:
    logger.error(f"Failed to parse JSON: {e}")
    raise

# Bad
try:
    data = json.loads(json_string)
except Exception:  # Too broad
    pass
```

### Logging

**Use structured logging:**

```python
import logging

logger = logging.getLogger(__name__)

# Info level for normal operations
logger.info(f"Starting Scout phase for task: {task_name}")

# Debug level for detailed info
logger.debug(f"Scout phase config: {config}")

# Warning for recoverable issues
logger.warning(f"Retrying failed operation (attempt {retry_count}/{max_retries})")

# Error for failures
logger.error(f"Scout phase failed: {error_message}")

# Critical for system-level issues
logger.critical(f"Daemon crashed: {error}")
```

### File Organization

**Module structure:**

```python
"""
Module docstring explaining purpose.
"""

# Standard library imports
import os
import sys
from typing import Dict, List

# Third-party imports
import fastmcp
from textual.app import App

# Local imports
from tools.baml_integration import get_baml_client
from tools.mcp_utils.phase_execution import execute_scout_phase

# Constants
MAX_RETRIES = 3
DEFAULT_TIMEOUT = 60

# Type aliases
ConfigDict = Dict[str, any]

# Classes
class MyClass:
    pass

# Functions
def my_function():
    pass

# Main execution
if __name__ == "__main__":
    main()
```

---

## Common Tasks & How-Tos

### Task 1: Adding a New Phase to the Build System

**Goal:** Add a new phase (e.g., "Optimize" phase after Builder).

**Steps:**

1. **Define BAML schema:**

```baml
// tools/baml_schemas/optimizer.baml

class OptimizeRequest {
  code_directory string @description("Directory with code to optimize")
  optimization_level string @description("Level: basic, moderate, aggressive")
}

class OptimizeResult {
  success bool
  optimizations_applied string[] @description("List of optimizations")
  performance_gain_percent float @description("Estimated performance gain")
  issues string[] @description("Issues found")
}

function OptimizeCode(request: OptimizeRequest) -> OptimizeResult {
  client claude-sonnet-4-5
  prompt #"
    Optimize the code in: {{ request.code_directory }}
    Optimization level: {{ request.optimization_level }}

    Apply best practices and return results.
  "#
}
```

2. **Regenerate BAML client:**

```bash
cd tools
baml-cli generate
```

3. **Add phase execution function:**

```python
# tools/mcp_utils/phase_execution.py

async def execute_optimize_phase(
    working_directory: str,
    optimization_level: str = "moderate"
) -> Dict[str, any]:
    """
    Execute Optimize phase to improve code performance.

    Args:
        working_directory: Directory with code to optimize
        optimization_level: Level of optimization (basic, moderate, aggressive)

    Returns:
        Dict with optimization results
    """
    from tools.baml_integration import get_baml_client
    from tools.baml_client.baml_client import b

    logger.info(f"Starting Optimize phase: {working_directory}")

    baml = get_baml_client()

    request = b.OptimizeRequest(
        code_directory=working_directory,
        optimization_level=optimization_level
    )

    result = baml.OptimizeCode(request)

    return {
        "status": "success",
        "result": result,
        "optimizations_applied": result.optimizations_applied,
        "performance_gain": result.performance_gain_percent
    }
```

4. **Integrate into build pipeline:**

```python
# tools/mcp_utils/autonomous_build.py

async def autonomous_build_and_deploy(...):
    # ... existing phases ...

    # Scout phase
    scout_result = await execute_scout_phase(...)

    # Architect phase
    architect_result = await execute_architect_phase(...)

    # Builder phase
    builder_result = await execute_builder_phase(...)

    # NEW: Optimize phase
    optimize_result = await execute_optimize_phase(
        working_directory=working_directory,
        optimization_level="moderate"
    )

    # Test phase
    test_result = await execute_test_phase(...)

    # ... rest of pipeline ...
```

5. **Add tests:**

```python
# tests/test_optimize_phase.py

import pytest
from tools.mcp_utils.phase_execution import execute_optimize_phase

@pytest.mark.integration
@pytest.mark.tier2
async def test_execute_optimize_phase():
    """Test Optimize phase execution."""
    result = await execute_optimize_phase(
        working_directory="/tmp/test-project",
        optimization_level="moderate"
    )

    assert result["status"] == "success"
    assert isinstance(result["optimizations_applied"], list)
    assert result["performance_gain"] >= 0
```

### Task 2: Adding Pattern Categories

**Goal:** Add a new pattern category for tracking deployment issues.

**Steps:**

1. **Define pattern schema:**

```python
# schemas/pattern_schema.json

{
  "deployment_patterns": {
    "type": "object",
    "properties": {
      "issue": {"type": "string"},
      "solution": {"type": "string"},
      "platform": {"type": "string"},
      "frequency": {"type": "integer"}
    }
  }
}
```

2. **Update pattern management:**

```python
# tools/mcp_utils/pattern_management.py

PATTERN_CATEGORIES = [
    "common-issues",
    "scout-learnings",
    "build-metrics",
    "deployment-patterns"  # NEW
]

def save_deployment_pattern(
    issue: str,
    solution: str,
    platform: str
) -> None:
    """
    Save a deployment pattern to the pattern library.

    Args:
        issue: Description of the deployment issue
        solution: How it was resolved
        platform: Deployment platform (vercel, aws, github-pages)
    """
    patterns = read_global_patterns()

    if "deployment-patterns" not in patterns:
        patterns["deployment-patterns"] = []

    pattern = {
        "issue": issue,
        "solution": solution,
        "platform": platform,
        "timestamp": datetime.now().isoformat(),
        "frequency": 1
    }

    patterns["deployment-patterns"].append(pattern)
    save_global_patterns(patterns)
```

3. **Add pattern extraction:**

```python
# tools/mcp_utils/autonomous_build.py

async def extract_deployment_patterns(
    deployment_result: Dict[str, any]
) -> None:
    """Extract deployment patterns from build results."""
    if deployment_result.get("issues"):
        for issue in deployment_result["issues"]:
            save_deployment_pattern(
                issue=issue["description"],
                solution=issue["resolution"],
                platform=deployment_result.get("platform", "unknown")
            )
```

### Task 3: Debugging Build Failures

**Goal:** Debug why a build is failing.

**Steps:**

1. **Check daemon logs:**

```bash
# Get job ID from recent builds
cfd list

# View logs for specific job
cfd logs <job-id>

# Follow logs in real-time
cfd logs <job-id> --follow
```

2. **Check phase-specific outputs:**

```bash
# Navigate to working directory
cd /tmp/your-project

# Check phase outputs
cat .context-foundry/scout-report.json
cat .context-foundry/architect-blueprint.json
cat .context-foundry/builder-result.json
```

3. **Check test results:**

```bash
# Test results are in iterations
cat .context-foundry/test-results-iteration-1.md
cat .context-foundry/test-results-iteration-2.md
```

4. **Enable debug logging:**

```python
# In your code
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

logger.debug(f"Debug info: {variable}")
```

5. **Run phases manually:**

```python
# Test a specific phase in isolation
from tools.mcp_utils.phase_execution import execute_scout_phase

result = await execute_scout_phase(
    task="Build a todo app",
    working_directory="/tmp/test",
    ...
)

print(result)
```

### Task 4: Syncing Patterns to S3

**Goal:** Share your learned patterns with the community.

**Steps:**

1. **Configure AWS credentials:**

```bash
# Set environment variables
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_DEFAULT_REGION=us-east-1
```

2. **Install AWS dependencies:**

```bash
pip install -r requirements-aws.txt
```

3. **Sync patterns:**

```bash
# Using script
./scripts/share-my-patterns.sh

# Or via MCP tool (in Claude Code)
# "Sync my patterns to S3"
```

4. **Pull community patterns:**

```bash
# This happens automatically, but you can force it
# In Claude Code: "Pull latest patterns from S3"
```

### Task 5: Creating Custom Extensions

**Goal:** Create an extension for domain-specific functionality.

**Steps:**

1. **Create extension directory:**

```bash
mkdir -p extensions/my_domain
cd extensions/my_domain
```

2. **Create structure:**

```bash
extensions/my_domain/
├── __init__.py
├── integration/
│   ├── __init__.py
│   └── api_client.py
├── patterns/
│   └── my_domain_patterns.json
├── examples/
│   └── example_project/
└── README.md
```

3. **Implement integration:**

```python
# extensions/my_domain/integration/api_client.py

class MyDomainClient:
    """Client for My Domain API integration."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    def create_resource(self, config: Dict[str, any]) -> Dict[str, any]:
        """Create a resource in My Domain."""
        # Implementation
        pass
```

4. **Add MCP tools:**

```python
# tools/mcp_server.py

from extensions.my_domain.integration.api_client import MyDomainClient

@mcp.tool()
async def my_domain_create_resource(
    config: Dict[str, any]
) -> Dict[str, any]:
    """Create a resource in My Domain."""
    client = MyDomainClient(api_key=os.getenv("MY_DOMAIN_API_KEY"))
    result = client.create_resource(config)
    return result
```

5. **Document the extension:**

```markdown
# extensions/my_domain/README.md

# My Domain Extension

Integration with My Domain for Context Foundry.

## Features

- Create resources
- Deploy to My Domain
- Monitor deployments

## Setup

1. Get API key from My Domain
2. Set environment variable: `MY_DOMAIN_API_KEY=your_key`
3. Use in builds: "Deploy to My Domain"

## Examples

See `examples/example_project/` for a complete example.
```

---

## Important Files & Their Purposes

### Core Files

| File | Purpose | Modify When |
|------|---------|-------------|
| `tools/mcp_server.py` | Main MCP server, exposes tools to Claude | Adding new MCP tools |
| `tools/cli.py` | CLI entry point for `cf` command | Changing CLI behavior |
| `context_foundry/daemon/server.py` | CF Daemon server | Modifying daemon behavior |
| `context_foundry/daemon/runner.py` | Job execution engine | Changing how jobs are executed |
| `tools/baml_integration.py` | BAML client management | Updating BAML integration |
| `tools/mcp_utils/autonomous_build.py` | Build orchestration | Modifying build pipeline |
| `tools/mcp_utils/phase_execution.py` | Phase execution logic | Adding/modifying phases |

### Configuration Files

| File | Purpose | Modify When |
|------|---------|-------------|
| `.env.example` | Environment variable template | Adding new config options |
| `.mcp.json` | MCP server configuration | Changing MCP setup |
| `pyproject.toml` | Python project config | Changing Ruff settings |
| `pytest.ini` | Pytest configuration | Changing test settings |
| `.pre-commit-config.yaml` | Pre-commit hooks | Adding new quality checks |
| `setup.py` | Package installation | Changing dependencies |
| `requirements*.txt` | Python dependencies | Adding/updating packages |

### BAML Files

| File | Purpose | Modify When |
|------|---------|-------------|
| `tools/baml_schemas/main.baml` | BAML generator config | Changing BAML setup |
| `tools/baml_schemas/phase_tracking.baml` | Phase tracking types | Modifying phase system |
| `tools/baml_schemas/scout.baml` | Scout phase types | Changing Scout outputs |
| `tools/baml_schemas/architect.baml` | Architect phase types | Changing Architect outputs |
| `tools/baml_schemas/builder.baml` | Builder phase types | Changing Builder outputs |

### Documentation Files

| File | Purpose | Read When |
|------|---------|-----------|
| `README.md` | Project overview | Understanding project |
| `QUICKSTART.md` | Quick start guide | Getting started |
| `docs/ARCHITECTURE.md` | System architecture | Understanding design |
| `docs/FEATURES.md` | Feature documentation | Learning features |
| `docs/BAML_INTEGRATION.md` | BAML guide | Working with BAML |
| `docs/CONTRIBUTING.md` | Contribution guide | Contributing |
| `CHANGELOG.md` | Version history | Understanding changes |

### System Files

| File | Purpose | Purpose |
|------|---------|---------|
| `.github/workflows/*.yml` | CI/CD pipelines | Automated testing & releases |
| `schemas/pattern_schema.json` | Pattern validation schema | Pattern format definition |
| `__version__.py` | Version information | Version tracking |
| `VERSION` | Version number | Simple version lookup |

---

## Gotchas & Things to Know

### 1. Virtual Environment Required

**Issue:** MCP server fails with "module not found" errors.

**Cause:** Dependencies not installed because venv wasn't activated.

**Solution:**
```bash
cd context-foundry
source venv/bin/activate  # MUST see (venv) in prompt
pip install -r requirements-mcp.txt
```

**Prevention:** Always activate venv before pip install.

### 2. Python 3.10+ Required

**Issue:** Syntax errors or import errors.

**Cause:** Code uses Python 3.10+ features (pattern matching, advanced type hints).

**Solution:**
```bash
# Check version
python --version

# Upgrade if needed
brew install python@3.11  # macOS
sudo apt install python3.11  # Linux

# Use in venv
python3.11 -m venv venv
```

### 3. BAML Client Generation

**Issue:** Import errors for BAML types.

**Cause:** BAML client not regenerated after schema changes.

**Solution:**
```bash
cd tools
baml-cli generate
```

**When to regenerate:**
- After modifying any `.baml` file
- After pulling changes that modify `.baml` files
- When seeing BAML import errors

### 4. Daemon PID File Conflicts

**Issue:** Daemon won't start, says "already running" but it's not.

**Cause:** Stale PID file from crashed daemon.

**Solution:**
```bash
# Remove stale PID file
rm ~/.context-foundry/daemon/cfd.pid

# Start daemon
./tools/cfd start
```

### 5. Working Directory Locking

**Issue:** Build fails with "working directory locked" error.

**Cause:** Previous build in same directory didn't clean up.

**Solution:**
```bash
# Check for lock file
ls /tmp/your-project/.context-foundry/workdir.lock

# Remove lock (only if no build is running!)
rm /tmp/your-project/.context-foundry/workdir.lock
```

**Prevention:** Wait for builds to complete or cancel properly.

### 6. GitHub Deployment Failures

**Issue:** Build succeeds but deployment fails with exit code -15.

**Cause:** GitHub CLI not installed or not authenticated.

**Solution:**
```bash
# Install gh CLI
brew install gh  # macOS
sudo apt install gh  # Linux

# Authenticate
gh auth login

# Test
gh auth status
```

### 7. API Key vs Subscription Costs

**Important:** 99%+ of Context Foundry runs on Claude Code subscription ($20/month unlimited).

**BAML type validation:** ~$0.20/build (separate API key required)

**Confusion:** Users think entire build uses API keys.

**Clarification:**
- Scout, Architect, Builder, Test, Deploy = Claude Code subscription (FREE)
- BAML validation = API key (~$0.20/build)

### 8. Pattern Sync S3 Permissions

**Issue:** Pattern sync fails with permission errors.

**Cause:** AWS credentials not configured or insufficient permissions.

**Solution:**
```bash
# Configure AWS credentials
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret
export AWS_DEFAULT_REGION=us-east-1

# Or use AWS CLI
aws configure
```

**Alternative:** Skip S3 sync (patterns still work locally).

### 9. Test Timeout in CI

**Issue:** Tests timeout in CI but pass locally.

**Cause:** CI environment is slower or network issues.

**Solution:**
```python
# In test file, increase timeout
@pytest.mark.timeout(300)  # 5 minutes
def test_my_long_running_test():
    pass
```

### 10. Context Window Messages

**Expected:** You'll see "🔄 Context reset - starting fresh conversation" messages.

**Not an Error:** This is the stateless conversation architecture working as designed.

**Benefit:** Prevents context window bloat, enables unlimited-length sessions.

### 11. Pre-commit Hook Failures

**Issue:** Commit fails with "Large files found" or "Debug statements detected".

**Cause:** Pre-commit hooks are working correctly, blocking bad commits.

**Solution:**
```bash
# Remove large file or add to .gitignore
echo "large_file.bin" >> .gitignore

# Remove debug statements
# Change: import pdb; pdb.set_trace()
# To: # import pdb; pdb.set_trace()

# Or skip hooks (not recommended)
git commit --no-verify
```

### 12. Incremental Build Cache Issues

**Issue:** Scout cache not being used, always runs fresh.

**Cause:** Cache invalidation or configuration.

**Check:**
```bash
# Verify incremental build is enabled
grep INCREMENTAL_PHASE2_ENABLED .env
# Should be: INCREMENTAL_PHASE2_ENABLED=true

# Check cache directory
ls ~/.context-foundry/cache/scout/

# Clear cache if stale
rm -rf ~/.context-foundry/cache/scout/*
```

### 13. Module Import Errors

**Issue:** `ModuleNotFoundError: No module named 'tools'`

**Cause:** Running scripts from wrong directory or PYTHONPATH not set.

**Solution:**
```bash
# Always run from project root
cd /home/user/context-foundry

# Run scripts
python tools/mcp_server.py

# Or set PYTHONPATH
export PYTHONPATH=/home/user/context-foundry:$PYTHONPATH
```

### 14. Textual TUI Rendering Issues

**Issue:** Mission Control TUI looks broken or has rendering glitches.

**Cause:** Terminal emulator incompatibility.

**Solution:**
```bash
# Try different terminal
# - iTerm2 (macOS)
# - Windows Terminal (Windows)
# - GNOME Terminal (Linux)

# Or use environment variable
TERM=xterm-256color cf
```

### 15. Git Branch Naming

**Important:** When working with automated git operations, branch names starting with `claude/` are used for automated deployments.

**Convention:**
- Feature branches: `feature/my-feature`
- Bug fixes: `fix/bug-description`
- Claude automated: `claude/session-id`

**Don't manually create branches starting with `claude/`** unless you're testing automation.

---

## Quick Reference

### Essential Commands

```bash
# Development
source venv/bin/activate          # Activate virtual environment
pip install -r requirements-mcp.txt  # Install dependencies
python tools/mcp_server.py        # Start MCP server
pytest                            # Run tests
pre-commit run --all-files        # Run code quality checks

# Daemon
./tools/cfd start                 # Start daemon
./tools/cfd status                # Check status
./tools/cfd list                  # List jobs
./tools/cfd logs <job-id>         # View logs

# Mission Control
cf                                # Launch TUI

# BAML
cd tools && baml-cli generate     # Regenerate BAML client

# Git
git checkout -b feature/my-feature  # Create feature branch
git commit -m "feat: description"   # Commit with conventional commits
gh pr create                       # Create pull request
```

### Key Environment Variables

```bash
# AI Providers
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GITHUB_TOKEN=ghp_...

# Phase Configuration
SCOUT_MODEL=claude-sonnet-4-5-20250929
ARCHITECT_MODEL=claude-sonnet-4-5-20250929
BUILDER_MODEL=claude-sonnet-4-5-20250929

# Features
INCREMENTAL_PHASE2_ENABLED=true
GLOBAL_SCOUT_CACHE_ENABLED=true
USE_MULTI_AGENT=true
```

### File Locations

```bash
# Configuration
~/.context-foundry/               # User config directory
~/.context-foundry/patterns/      # Pattern library
~/.context-foundry/cache/         # Build cache
~/.context-foundry/daemon/        # Daemon files

# Project
.context-foundry/                 # Project-specific data
.mcp.json                         # MCP server config
.env                              # Environment variables
```

### Common Patterns

**MCP Tool:**
```python
@mcp.tool()
async def my_tool(param: str) -> str:
    """Tool description."""
    return result
```

**BAML Schema:**
```baml
class MyType {
  field string @description("Field description")
}

function MyFunction(input: string) -> MyType {
  client claude-sonnet-4-5
  prompt #"{{ input }}"#
}
```

**Test:**
```python
@pytest.mark.unit
@pytest.mark.tier1
def test_my_feature():
    """Test description."""
    assert my_function() == expected
```

---

## Additional Resources

### Documentation

- **README.md** - Project overview and features
- **QUICKSTART.md** - 5-minute quick start guide
- **docs/ARCHITECTURE.md** - System architecture deep dive
- **docs/FEATURES.md** - Complete feature documentation
- **docs/BAML_INTEGRATION.md** - BAML usage guide
- **docs/TROUBLESHOOTING.md** - Common issues and solutions
- **docs/CONTRIBUTING.md** - Contribution guidelines

### External Resources

- **MCP Documentation:** https://modelcontextprotocol.io
- **BAML Documentation:** https://docs.boundaryml.com
- **Textual Documentation:** https://textual.textualize.io
- **FastMCP GitHub:** https://github.com/jlowin/fastmcp
- **Claude API Docs:** https://docs.anthropic.com

### Community

- **GitHub Issues:** https://github.com/context-foundry/context-foundry/issues
- **Discussions:** https://github.com/context-foundry/context-foundry/discussions
- **Pattern Library:** S3 bucket `bedrock-builder-kb-898587418237/community-patterns/`

---

## Changelog

### 2025-11-24 - Initial CLAUDE.md Creation

- Created comprehensive AI assistant guide
- Documented codebase structure and architecture
- Added development workflows and conventions
- Included common tasks and troubleshooting
- Added quick reference section

---

**End of CLAUDE.md**

This document is maintained by the Context Foundry team and community contributors. For updates or corrections, please submit a pull request or open an issue.
