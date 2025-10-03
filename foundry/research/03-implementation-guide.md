# Context Foundry Implementation Guide

> **Practical, hands-on guide for implementing and deploying the Anti-Vibe Coding Assembly Line**

**Version:** 1.0
**Last Updated:** October 2, 2025
**Audience:** Developers, DevOps engineers, team leads

---

## Table of Contents

1. [Prerequisites & System Requirements](#prerequisites--system-requirements)
2. [Installation & Setup](#installation--setup)
3. [Quick Start: Your First Build](#quick-start-your-first-build)
4. [Agent Configuration](#agent-configuration)
5. [Workflow Orchestration](#workflow-orchestration)
6. [Integration Patterns](#integration-patterns)
7. [Practical Examples](#practical-examples)
8. [Testing & Validation](#testing--validation)
9. [Advanced Configuration](#advanced-configuration)
10. [Production Deployment](#production-deployment)
11. [Troubleshooting](#troubleshooting)
12. [Best Practices](#best-practices)

---

## Prerequisites & System Requirements

### Minimum Requirements

**System:**
- CPU: 2+ cores
- RAM: 4GB minimum, 8GB recommended
- Disk: 10GB free space
- OS: macOS, Linux, or Windows (WSL recommended for Windows)

**Software:**
- Python 3.8 or higher
- pip (Python package installer)
- Git 2.0+
- Internet connection (for Claude API)

**Account:**
- Anthropic API account with API key
- Get one at: https://console.anthropic.com/

### Recommended Setup

**System:**
- CPU: 4+ cores (for parallel operations)
- RAM: 16GB (for large codebases)
- SSD storage

**Software:**
- Python 3.11+ (latest stable)
- Git 2.30+ (for advanced features)
- Text editor (VS Code, Vim, etc.)
- Terminal multiplexer (tmux/screen for long sessions)

---

## Installation & Setup

### Step 1: Clone Repository

```bash
# Clone from GitHub
git clone https://github.com/snedea/context-foundry.git
cd context-foundry

# Verify files
ls -la
# Should see: ace/, workflows/, foundry/, tools/, etc.
```

### Step 2: Create Virtual Environment (Recommended)

```bash
# Create virtual environment
python3 -m venv foundry-env

# Activate it
source foundry-env/bin/activate  # macOS/Linux
# or
foundry-env\Scripts\activate      # Windows

# Your prompt should now show (foundry-env)
```

### Step 3: Install Dependencies

```bash
# Install in development mode
pip install -e .

# This installs:
# - anthropic (Claude API)
# - click (CLI framework)
# - rich (terminal formatting)
# - sentence-transformers (pattern embeddings)
# - numpy, pyyaml, python-dotenv
# - and more...

# Verify installation
foundry --version
# Output: foundry, version 1.0.0
```

### Step 4: Configure API Key

#### Option A: Environment Variable (Temporary)

```bash
# Set for current session
export ANTHROPIC_API_KEY=sk-ant-api03-your-key-here

# Verify it's set
echo $ANTHROPIC_API_KEY
```

#### Option B: .env File (Persistent)

```bash
# Initialize .env file
foundry config --init

# Edit .env
nano .env
# or
vim .env
# or
code .env

# Add your key:
ANTHROPIC_API_KEY=sk-ant-api03-your-key-here
```

#### Option C: Using CLI

```bash
# Set via config command
foundry config --set ANTHROPIC_API_KEY sk-ant-api03-your-key-here
```

### Step 5: Validate Installation

```bash
# Run health check
python tools/health_check.py

# Expected output:
# ✅ Python version: 3.11.x
# ✅ API key configured
# ✅ Dependencies installed
# ✅ Directory structure valid
# ✅ Git available
# ✅ All critical checks passed!
```

---

## Quick Start: Your First Build

### 30-Minute Tutorial

Let's build a CLI todo application to learn the workflow.

#### 1. Start the Build

```bash
foundry build todo-cli "Create a CLI todo app with add, list, and complete commands. Use local JSON file for storage."
```

#### 2. Scout Phase (2-3 minutes)

You'll see:

```
🏭 Autonomous Context Foundry
📋 Project: todo-cli
📝 Task: Create a CLI todo app...
🤖 Mode: Interactive
📚 Patterns: Enabled
💾 Session: todo-cli_20251002_120000

🔍 PHASE 1: SCOUT
------------------------------------------------------------
Researching architecture options...
Exploring CLI frameworks...
Analyzing storage patterns...

✅ Research complete
📄 Artifact: blueprints/specs/RESEARCH_20251002_120000.md
📊 Context usage: 28%
```

**Review Checkpoint:**

```
📋 Review research artifact? (y/n):
```

Type `y` to review the research. Look for:
- Technology recommendations (argparse, Click, etc.)
- Architecture decisions (JSON structure)
- Identified patterns

Press Enter to continue.

#### 3. Architect Phase (3-5 minutes)

You'll see:

```
📐 PHASE 2: ARCHITECT
------------------------------------------------------------
Creating specifications...
Generating technical plan...
Breaking into tasks...

✅ Architect phase complete
📄 Artifacts:
   - SPEC_20251002_120000.md
   - PLAN_20251002_120000.md
   - TASKS_20251002_120000.md
📊 Context usage: 35%
```

**Review Checkpoint (CRITICAL):**

```
📋 Review plan and tasks? (y/n):
```

Type `y` and **carefully review**:

**SPEC.md** - What will be built:
```markdown
# Specification: CLI Todo App

## Requirements
1. Add todos with description
2. List all todos
3. Mark todos as complete
4. Persist to JSON file

## Success Criteria
- All commands work correctly
- Data persists across sessions
- Tests pass
```

**TASKS.md** - Step-by-step plan:
```markdown
## Task 1: Project Setup
- Create directory structure
- Add configuration

## Task 2: JSON Storage Module
- Implement load/save functions
- Handle file not found

## Task 3: Add Command
- CLI argument parsing
- Add to storage
- Tests

## Task 4: List Command
...
```

⚠️ **This is your highest leverage point!** Take time to review.

Press Enter to approve and continue.

#### 4. Builder Phase (10-15 minutes)

You'll see:

```
🔨 PHASE 3: BUILDER
------------------------------------------------------------
📝 Task 1/6: Project Setup
   🧪 Writing tests...
   💻 Implementing...
   ✅ Tests pass
   📊 Context: 32%

📝 Task 2/6: JSON Storage Module
   🧪 Writing tests...
   💻 Implementing...
   ✅ Tests pass
   📊 Context: 38%

📝 Task 3/6: Add Command
   🧪 Writing tests...
   💻 Implementing...
   ✅ Tests pass
   📊 Context: 42%
   🗜️  Compacting context... (42% → 28%)

...

✅ BUILDER PHASE COMPLETE
```

#### 5. Check Results

```bash
# Your new project is created
cd projects/todo-cli

# List files
ls -la
# You'll see:
# - todo.py (main application)
# - test_todo.py (comprehensive tests)
# - README.md (documentation)
# - todos.json (data file)

# Run the application
python todo.py add "Learn Context Foundry"
python todo.py list

# Output:
# [ ] Learn Context Foundry

# Mark as complete
python todo.py complete 1

# Run tests
pytest test_todo.py
# All tests pass ✅
```

#### 6. Review Git History

```bash
git log --oneline

# Output:
# a1b2c3d Complete Task 6: Add documentation (Context: 35%)
# b4e5f6g Complete Task 5: Delete command (Context: 42%)
# c7h8i9j Complete Task 4: Complete command (Context: 38%)
# ...
```

#### 7. Analyze Session

```bash
# Generate analysis report
foundry analyze --format markdown --save report.md

# View report
cat report.md
```

**Report shows:**
- Completion rate: 100%
- Total tokens: ~45,000
- Estimated cost: $1.20
- Context efficiency: 38% average
- Patterns extracted: 8
- Time: 18 minutes

**Congratulations!** You've completed your first build. 🎉

---

## Agent Configuration

Context Foundry uses three specialized agents in its workflow.

### Scout Agent

**Purpose:** Research and architecture exploration

**Configuration** (`ace/scouts/config.yaml`):

```yaml
scout:
  model: claude-sonnet-4-20250514
  max_tokens: 8000
  temperature: 0.7

  # Context limits
  context_window: 200000
  target_usage: 0.30  # 30%

  # Subagent settings
  enable_subagents: true
  subagent_window: 200000
  summary_max_tokens: 2000

  # Output settings
  output_format: markdown
  max_artifact_size: 5000

  # Search strategies
  exploration_strategy: execution_paths
  pattern_matching: enabled
```

**Customization:**

```python
# Custom Scout configuration
from ace.scouts import ScoutAgent

scout = ScoutAgent(
    temperature=0.8,  # More creative exploration
    context_target=0.25,  # Even tighter context
    enable_subagents=True
)

# Run custom scout
result = scout.research(
    project_name="my-app",
    task_description="Build user auth",
    focus_areas=["security", "oauth", "jwt"]
)
```

### Architect Agent

**Purpose:** Planning and specification

**Configuration** (`ace/architects/config.yaml`):

```yaml
architect:
  model: claude-sonnet-4-20250514
  max_tokens: 8000
  temperature: 0.6

  # Context limits
  context_window: 200000
  target_usage: 0.40  # 40%

  # Planning settings
  task_decomposition: atomic
  min_task_size: 30  # minutes
  max_task_size: 120  # minutes

  # Output settings
  generate_spec: true
  generate_plan: true
  generate_tasks: true

  # Quality gates
  require_success_criteria: true
  require_test_strategy: true
```

**Customization:**

```python
# Custom Architect configuration
from ace.architects import ArchitectAgent

architect = ArchitectAgent(
    task_size_preference="small",  # Prefer smaller tasks
    detail_level="comprehensive",  # More detailed specs
    alternatives=3  # Consider 3 alternatives per decision
)

# Run custom architect
result = architect.plan(
    research_artifact=scout_result,
    constraints=["Python 3.11+", "No external services"],
    preferences={"testing": "pytest", "style": "black"}
)
```

### Builder Agent

**Purpose:** Implementation with TDD

**Configuration** (`ace/builders/config.yaml`):

```yaml
builder:
  model: claude-sonnet-4-20250514
  max_tokens: 8000
  temperature: 0.5

  # Context limits
  context_window: 200000
  target_usage: 0.50  # 50%
  compaction_threshold: 0.50

  # TDD settings
  test_first: true
  test_framework: auto_detect
  min_coverage: 80

  # Execution settings
  sequential: true
  checkpoint_after_task: true
  git_auto_commit: true

  # Error handling
  retry_on_failure: true
  max_retries: 3
```

**Customization:**

```python
# Custom Builder configuration
from ace.builders import BuilderAgent

builder = BuilderAgent(
    test_first=True,
    compaction_strategy="aggressive",  # Compact more frequently
    git_commits=True,
    checkpoint_interval=1  # Checkpoint after every task
)

# Run custom builder
result = builder.execute_tasks(
    tasks=architect_tasks,
    spec=specification,
    style_guide="google",  # Use Google Python style guide
    type_hints=True  # Enforce type hints
)
```

---

## Workflow Orchestration

### The Three-Phase Pipeline

The orchestrator manages the Scout → Architect → Builder workflow.

### Basic Orchestration

```python
from workflows.autonomous_orchestrator import AutonomousOrchestrator

# Initialize orchestrator
orchestrator = AutonomousOrchestrator(
    project_name="my-app",
    task_description="Build REST API with auth",
    autonomous_mode=False,  # Enable human checkpoints
    enable_livestream=True,
    use_patterns=True,
    use_context_manager=True
)

# Run workflow
result = orchestrator.run()

# Result includes:
# - success: bool
# - artifacts: dict (research, spec, plan, tasks)
# - code_output: str (path to generated code)
# - metrics: dict (tokens, cost, context usage)
```

### Advanced Orchestration

#### Custom Phase Hooks

```python
class CustomOrchestrator(AutonomousOrchestrator):
    """Custom orchestrator with hooks"""

    def before_scout(self):
        """Called before Scout phase"""
        print("🎯 Starting research...")
        # Custom setup
        self.load_domain_knowledge()

    def after_scout(self, research):
        """Called after Scout phase"""
        # Validate research
        if not self.validate_research(research):
            raise ValueError("Research incomplete")

        # Store research metadata
        self.store_metadata("research", research)

    def before_architect(self, research):
        """Called before Architect phase"""
        # Inject additional context
        return self.enhance_research(research)

    def after_architect(self, spec, plan, tasks):
        """Called after Architect phase"""
        # Custom validation
        self.validate_plan(plan)
        self.estimate_cost(tasks)

    def before_builder(self, tasks):
        """Called before Builder phase"""
        # Setup build environment
        self.setup_environment()

    def after_builder(self, code_path):
        """Called after Builder phase"""
        # Post-build actions
        self.run_linters(code_path)
        self.generate_docs(code_path)

# Use custom orchestrator
orchestrator = CustomOrchestrator(
    project_name="my-app",
    task_description="Build feature"
)
result = orchestrator.run()
```

#### State Management

```python
# Save orchestrator state
state = orchestrator.save_state()

# State includes:
{
    "session_id": "my-app_20251002_120000",
    "current_phase": "builder",
    "completed_phases": ["scout", "architect"],
    "artifacts": {
        "research": "path/to/research.md",
        "spec": "path/to/spec.md",
        "plan": "path/to/plan.md",
        "tasks": "path/to/tasks.md"
    },
    "metrics": {
        "scout_tokens": 5234,
        "architect_tokens": 8765,
        "builder_tokens": 23456
    }
}

# Resume from saved state
orchestrator = AutonomousOrchestrator.from_state(state)
result = orchestrator.resume()
```

#### Parallel Orchestration

```python
import asyncio
from workflows.autonomous_orchestrator import AutonomousOrchestrator

async def build_multiple_features():
    """Build multiple features in parallel"""

    features = [
        ("auth-service", "User authentication"),
        ("api-gateway", "API gateway with routing"),
        ("notification-service", "Email/SMS notifications")
    ]

    # Create orchestrators
    orchestrators = [
        AutonomousOrchestrator(
            project_name=name,
            task_description=desc,
            autonomous_mode=True
        )
        for name, desc in features
    ]

    # Run in parallel
    results = await asyncio.gather(*[
        o.run_async() for o in orchestrators
    ])

    return results

# Execute
results = asyncio.run(build_multiple_features())
```

---

## Integration Patterns

### Standalone CLI (Current Implementation)

**Usage:**

```bash
# Direct CLI usage
foundry build my-app "Task description"
```

**Integration in scripts:**

```bash
#!/bin/bash
# build.sh - Automated build script

# Configuration
PROJECT=$1
TASK=$2

# Run build
foundry build "$PROJECT" "$TASK" \
  --autonomous \
  --use-patterns \
  --context-manager

# Validate
cd "projects/$PROJECT"
pytest
mypy .

# Deploy if tests pass
if [ $? -eq 0 ]; then
    ./deploy.sh
fi
```

### Python API Integration

```python
# main.py - Use Context Foundry as a library
from workflows.autonomous_orchestrator import AutonomousOrchestrator
from foundry.patterns import PatternLibrary
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)

def build_feature(feature_name, description):
    """Build a feature using Context Foundry"""

    # Initialize
    orchestrator = AutonomousOrchestrator(
        project_name=feature_name,
        task_description=description,
        autonomous_mode=True,
        use_patterns=True
    )

    # Execute
    result = orchestrator.run()

    # Handle result
    if result.success:
        print(f"✅ {feature_name} built successfully")
        print(f"📊 Cost: ${result.cost:.2f}")
        print(f"📁 Output: {result.output_path}")
    else:
        print(f"❌ {feature_name} failed")
        print(f"Error: {result.error}")

    return result

# Use it
if __name__ == "__main__":
    result = build_feature(
        "user-auth",
        "Build JWT authentication with refresh tokens"
    )
```

### CI/CD Integration

#### GitHub Actions

```yaml
# .github/workflows/context-foundry.yml
name: Context Foundry Build

on:
  workflow_dispatch:
    inputs:
      project_name:
        description: 'Project name'
        required: true
      task_description:
        description: 'What to build'
        required: true

jobs:
  build:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v3

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install Context Foundry
        run: |
          pip install -e .

      - name: Run Build
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          foundry build \
            "${{ github.event.inputs.project_name }}" \
            "${{ github.event.inputs.task_description }}" \
            --autonomous \
            --use-patterns

      - name: Run Tests
        run: |
          cd "projects/${{ github.event.inputs.project_name }}"
          pytest

      - name: Create PR
        uses: peter-evans/create-pull-request@v5
        with:
          title: "Add ${{ github.event.inputs.project_name }}"
          body: |
            ## Automated Build by Context Foundry

            **Project:** ${{ github.event.inputs.project_name }}
            **Task:** ${{ github.event.inputs.task_description }}

            🤖 Generated with Context Foundry
          branch: "cf-${{ github.event.inputs.project_name }}"
```

#### GitLab CI

```yaml
# .gitlab-ci.yml
stages:
  - build
  - test
  - deploy

context_foundry_build:
  stage: build
  image: python:3.11
  variables:
    PROJECT_NAME: "my-feature"
    TASK_DESC: "Build user dashboard"
  script:
    - pip install -e .
    - foundry build "$PROJECT_NAME" "$TASK_DESC" --autonomous
  artifacts:
    paths:
      - projects/$PROJECT_NAME/
```

### Integration with Other AI Coding Tools

#### Aider Integration

```python
# Use Context Foundry for planning, Aider for refinement
from workflows.autonomous_orchestrator import AutonomousOrchestrator
import subprocess

# 1. Generate initial code with Context Foundry
orchestrator = AutonomousOrchestrator(
    project_name="my-app",
    task_description="Build REST API",
    autonomous_mode=True
)
result = orchestrator.run()

# 2. Refine with Aider
subprocess.run([
    "aider",
    "--yes",
    f"--model=gpt-4",
    f"--message='Review and optimize the code in {result.output_path}'",
    result.output_path
])
```

#### Claude Code Integration

Context Foundry is designed to complement Claude Code (the IDE you're using now):

1. **Use Context Foundry for**: Initial project scaffolding, feature implementation
2. **Use Claude Code for**: Code review, refinement, debugging

```bash
# Generate with Context Foundry
foundry build my-app "REST API with auth"

# Open in VS Code with Claude Code
code projects/my-app

# Use Claude Code to:
# - Review generated code
# - Add edge case handling
# - Optimize performance
# - Fix any issues
```

---

## Practical Examples

### Example 1: CLI Tool

**Task:** Build a CLI tool for managing environment variables

```bash
foundry build envctl "CLI tool for managing .env files with add, list, remove, and export commands. Support multiple environment files (dev, staging, prod)."
```

**Generated Structure:**
```
envctl/
├── envctl.py           # Main CLI
├── env_manager.py      # Core logic
├── test_envctl.py      # Tests
├── README.md           # Documentation
└── requirements.txt    # Dependencies (click, python-dotenv)
```

**Usage:**
```bash
python envctl.py add DATABASE_URL postgres://localhost/mydb --env dev
python envctl.py list --env dev
python envctl.py export --env dev --output .env.dev
```

### Example 2: REST API

**Task:** Build a FastAPI REST API

```bash
foundry build task-api "REST API for task management with FastAPI. Features: CRUD operations, JWT authentication, PostgreSQL storage, OpenAPI docs. Include rate limiting and error handling." --livestream
```

**Generated Structure:**
```
task-api/
├── app/
│   ├── main.py         # FastAPI app
│   ├── models.py       # Pydantic models
│   ├── database.py     # Database connection
│   ├── auth.py         # JWT authentication
│   ├── routers/
│   │   ├── tasks.py    # Task endpoints
│   │   └── users.py    # User endpoints
│   └── middleware.py   # Rate limiting
├── tests/
│   ├── test_tasks.py
│   └── test_auth.py
├── alembic/            # Database migrations
├── requirements.txt
└── README.md
```

**Running:**
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
# API at http://localhost:8000
# Docs at http://localhost:8000/docs
```

### Example 3: Data Pipeline

**Task:** Build an ETL pipeline

```bash
foundry build etl-pipeline "ETL pipeline that fetches data from CSV files, validates using Pydantic, transforms with pandas, and loads to PostgreSQL. Include error handling, logging, and retry logic." --overnight 4
```

**Generated Structure:**
```
etl-pipeline/
├── pipeline/
│   ├── extract.py      # CSV reading
│   ├── transform.py    # Data transformation
│   ├── load.py         # Database loading
│   ├── validators.py   # Pydantic validators
│   └── config.py       # Configuration
├── tests/
│   ├── test_extract.py
│   ├── test_transform.py
│   └── test_load.py
├── data/
│   └── sample.csv
├── requirements.txt
└── main.py            # Pipeline runner
```

### Example 4: Web Scraper

**Task:** Build a web scraper

```bash
foundry build web-scraper "Web scraper for product data using BeautifulSoup and Selenium. Features: async scraping, rate limiting, proxy support, data validation, export to JSON/CSV. Include retry logic and user-agent rotation."
```

**Generated Structure:**
```
web-scraper/
├── scraper/
│   ├── base.py         # Base scraper class
│   ├── async_scraper.py # Async implementation
│   ├── parser.py       # HTML parsing
│   ├── rate_limiter.py # Rate limiting
│   └── proxy_manager.py # Proxy rotation
├── tests/
├── config.yaml
└── main.py
```

### Example 5: Machine Learning Pipeline

**Task:** Build an ML training pipeline

```bash
foundry build ml-pipeline "Machine learning pipeline for binary classification. Features: data preprocessing with pandas, feature engineering, model training with scikit-learn, hyperparameter tuning with GridSearch, model evaluation, model versioning. Include experiment tracking with MLflow."
```

**Generated Structure:**
```
ml-pipeline/
├── pipeline/
│   ├── preprocessing.py  # Data cleaning
│   ├── features.py       # Feature engineering
│   ├── training.py       # Model training
│   ├── evaluation.py     # Metrics & evaluation
│   └── serving.py        # Model serving API
├── tests/
├── models/              # Saved models
├── experiments/         # MLflow experiments
└── main.py
```

---

## Testing & Validation

### Unit Testing

Context Foundry generates comprehensive tests automatically.

**Verify Tests:**

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test file
pytest tests/test_auth.py

# Run with verbose output
pytest -v
```

**Test Structure:**

```python
# Generated test example
import pytest
from myapp import add_task

def test_add_task_success():
    """Test adding a task successfully"""
    task_id = add_task("Test task")
    assert task_id is not None
    assert task_id > 0

def test_add_task_empty_description():
    """Test adding task with empty description fails"""
    with pytest.raises(ValueError, match="Description cannot be empty"):
        add_task("")

def test_add_task_duplicate():
    """Test adding duplicate task"""
    add_task("Duplicate")
    with pytest.raises(ValueError, match="Task already exists"):
        add_task("Duplicate")
```

### Integration Testing

```python
# Test the full workflow
import subprocess

def test_context_foundry_workflow():
    """Test complete Scout → Architect → Builder workflow"""

    # Run build
    result = subprocess.run([
        "foundry", "build",
        "test-app",
        "Simple calculator CLI",
        "--autonomous"
    ], capture_output=True, text=True)

    # Verify success
    assert result.returncode == 0
    assert "✅ CONTEXT FOUNDRY WORKFLOW COMPLETE!" in result.stdout

    # Verify artifacts created
    assert os.path.exists("blueprints/specs/RESEARCH_*.md")
    assert os.path.exists("blueprints/specs/SPEC_*.md")
    assert os.path.exists("blueprints/plans/PLAN_*.md")
    assert os.path.exists("blueprints/tasks/TASKS_*.md")

    # Verify code generated
    assert os.path.exists("projects/test-app/")

    # Run generated tests
    test_result = subprocess.run(
        ["pytest", "projects/test-app/"],
        capture_output=True
    )
    assert test_result.returncode == 0
```

### Validation Checklist

After each build, validate:

**✅ Artifacts Generated:**
- [ ] RESEARCH.md exists
- [ ] SPEC.md exists
- [ ] PLAN.md exists
- [ ] TASKS.md exists

**✅ Code Quality:**
- [ ] All files created
- [ ] No syntax errors
- [ ] Tests exist
- [ ] Tests pass
- [ ] Type hints present (if configured)
- [ ] Docstrings present

**✅ Functionality:**
- [ ] Application runs without errors
- [ ] All features work as specified
- [ ] Edge cases handled

**✅ Context Management:**
- [ ] Context stayed under 50%
- [ ] Compaction occurred when needed
- [ ] No context limit errors

**✅ Git History:**
- [ ] Commits for each task
- [ ] Commit messages descriptive
- [ ] No merge conflicts

---

## Advanced Configuration

### Custom Profiles

Create custom configuration profiles for different scenarios.

**Edit `.foundry/config.yaml`:**

```yaml
# Default profile
current_profile: development

profiles:
  development:
    model: claude-sonnet-4-20250514
    autonomous_mode: false
    enable_livestream: true
    use_context_manager: true
    use_patterns: true
    context_threshold: 0.40
    git_auto_commit: true

  production:
    model: claude-sonnet-4-20250514
    autonomous_mode: false
    enable_livestream: false
    use_context_manager: true
    use_patterns: true
    context_threshold: 0.35  # More aggressive
    git_auto_commit: true
    require_tests: true
    min_test_coverage: 90

  overnight:
    model: claude-sonnet-4-20250514
    autonomous_mode: true
    enable_livestream: false
    use_context_manager: true
    use_patterns: true
    context_threshold: 0.35
    retry_on_failure: true
    max_retries: 5
    checkpoint_frequency: 1  # Every task

  experimental:
    model: claude-opus-4-20250514  # More powerful model
    autonomous_mode: false
    temperature: 0.8  # More creative
    use_patterns: false  # Don't use patterns
    enable_debug: true
    verbose_logging: true
```

**Use profiles:**

```bash
# Use production profile
foundry build my-app "Task" --profile production

# Or set default
foundry config --set current_profile production
foundry build my-app "Task"
```

### Environment-Specific Configuration

```yaml
# .foundry/environments/staging.yaml
environment: staging

overrides:
  project_dir: /var/www/staging
  git_branch: staging
  deployment_target: staging.example.com

notifications:
  slack_webhook: https://hooks.slack.com/staging
  email: staging-alerts@example.com

limits:
  max_cost_per_session: 10.00
  max_duration_minutes: 60
```

**Use:**

```bash
foundry build my-app "Task" --env staging
```

### Custom Hooks

Add custom behavior at key points in the workflow.

**Create `.foundry/hooks/post-build.sh`:**

```bash
#!/bin/bash
# Run after successful build

PROJECT=$1
SESSION=$2

echo "🎣 Running post-build hook for $PROJECT"

# Run linters
cd "projects/$PROJECT"
black .
isort .
mypy .

# Run security scan
bandit -r .

# Generate documentation
sphinx-build docs docs/_build

# Notify team
curl -X POST $SLACK_WEBHOOK \
  -H 'Content-Type: application/json' \
  -d "{\"text\":\"✅ $PROJECT built successfully\"}"

# Deploy to staging
./deploy-staging.sh
```

**Register hook:**

```yaml
# .foundry/config.yaml
hooks:
  post_build: .foundry/hooks/post-build.sh
  pre_architect: .foundry/hooks/validate-task.py
  post_test: .foundry/hooks/coverage-report.sh
```

### Pattern Library Tuning

```yaml
# foundry/patterns/config.yaml
extraction:
  min_complexity: 3     # Cyclomatic complexity threshold
  min_lines: 5          # Minimum lines for pattern
  max_similarity: 0.9   # Deduplication threshold
  languages: [python, javascript, typescript, go]
  frameworks: [fastapi, flask, django, react, vue, express]

search:
  default_limit: 5
  min_relevance: 0.6    # Minimum similarity score
  embedding_model: "all-MiniLM-L6-v2"

injection:
  enabled: true
  max_patterns: 3       # Patterns per prompt
  min_success_rate: 70  # Only inject proven patterns
  min_usage_count: 2    # Pattern must be used twice
  prioritize_recent: true  # Prefer recent patterns
```

---

## Production Deployment

### Server Setup

**Recommended Specs:**
- 4 CPU cores
- 16GB RAM
- 100GB SSD
- Ubuntu 22.04 LTS

**Installation:**

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python 3.11
sudo apt install python3.11 python3.11-venv python3-pip

# Install Git
sudo apt install git

# Clone Context Foundry
cd /opt
sudo git clone https://github.com/snedea/context-foundry.git
cd context-foundry

# Create service user
sudo useradd -r -s /bin/false foundry

# Setup virtual environment
sudo python3.11 -m venv /opt/foundry-env
sudo /opt/foundry-env/bin/pip install -e .

# Set permissions
sudo chown -R foundry:foundry /opt/context-foundry
```

### Systemd Service

**Create `/etc/systemd/system/context-foundry.service`:**

```ini
[Unit]
Description=Context Foundry Build Service
After=network.target

[Service]
Type=simple
User=foundry
Group=foundry
WorkingDirectory=/opt/context-foundry
Environment="PATH=/opt/foundry-env/bin"
Environment="ANTHROPIC_API_KEY=sk-ant-api03-your-key"
ExecStart=/opt/foundry-env/bin/python -m tools.queue_processor
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Enable service:**

```bash
sudo systemctl daemon-reload
sudo systemctl enable context-foundry
sudo systemctl start context-foundry
sudo systemctl status context-foundry
```

### Queue-Based Processing

For team environments, implement a build queue.

**`tools/queue_processor.py`:**

```python
# Queue processor for production
import time
from pathlib import Path
from workflows.autonomous_orchestrator import AutonomousOrchestrator

QUEUE_DIR = Path("queue/requests")
RESULTS_DIR = Path("queue/results")

def process_queue():
    """Process build requests from queue"""
    while True:
        # Check for new requests
        for request_file in QUEUE_DIR.glob("*.json"):
            try:
                # Load request
                request = json.loads(request_file.read_text())

                # Execute build
                orchestrator = AutonomousOrchestrator(
                    project_name=request['project'],
                    task_description=request['task'],
                    autonomous_mode=True
                )
                result = orchestrator.run()

                # Save result
                result_file = RESULTS_DIR / f"{request['id']}.json"
                result_file.write_text(json.dumps({
                    'success': result.success,
                    'output_path': result.output_path,
                    'cost': result.cost,
                    'metrics': result.metrics
                }))

                # Remove request
                request_file.unlink()

            except Exception as e:
                logger.error(f"Error processing {request_file}: {e}")

        time.sleep(5)

if __name__ == "__main__":
    process_queue()
```

### Monitoring

**Setup Prometheus metrics:**

```python
# tools/metrics.py
from prometheus_client import Counter, Histogram, Gauge

builds_total = Counter('cf_builds_total', 'Total builds')
builds_success = Counter('cf_builds_success', 'Successful builds')
build_duration = Histogram('cf_build_duration_seconds', 'Build duration')
context_usage = Gauge('cf_context_usage_percent', 'Context usage')
api_cost = Counter('cf_api_cost_dollars', 'API cost in dollars')
```

**Grafana Dashboard:**

Monitor:
- Builds per hour
- Success rate
- Average build time
- Context usage trends
- API costs
- Pattern library growth

---

## Troubleshooting

### Common Issues

#### 1. API Key Not Working

**Symptoms:**
```
Error: anthropic.AuthenticationError: Invalid API key
```

**Solutions:**

```bash
# Verify key is set
echo $ANTHROPIC_API_KEY

# Check key format (should start with sk-ant-)
# Get new key from console.anthropic.com

# Set in .env
foundry config --set ANTHROPIC_API_KEY sk-ant-api03-your-key

# Or export
export ANTHROPIC_API_KEY=sk-ant-api03-your-key
```

#### 2. Context Usage Too High

**Symptoms:**
```
⚠️ Warning: Context usage at 75%
```

**Solutions:**

```bash
# Enable context manager (should be default)
foundry config --set USE_CONTEXT_MANAGER true

# Lower compaction threshold
foundry config --set CONTEXT_THRESHOLD 0.35

# Check compaction is working
foundry status --watch
# Look for "🗜️ Compacting context..." messages
```

#### 3. Pattern Library Not Working

**Symptoms:**
```
No patterns found for task
```

**Solutions:**

```bash
# Check database exists
ls -la foundry/patterns/patterns.db

# Rebuild database
rm foundry/patterns/patterns.db

# Extract from successful sessions
python foundry/patterns/pattern_extractor.py \
  --session checkpoints/ralph/*

# Verify patterns
foundry patterns --stats
```

#### 4. Build Hangs/Freezes

**Symptoms:**
Build stops responding, no progress

**Solutions:**

```bash
# Check status in another terminal
foundry status --watch

# Check if API calls are succeeding
tail -f logs/*.log

# Kill and restart
pkill -f "foundry build"

# Resume from checkpoint
foundry resume SESSION_ID
```

#### 5. Generated Code Has Errors

**Symptoms:**
Code doesn't run, syntax errors, imports fail

**Solutions:**

This usually means the plan was flawed. **Prevention is key:**

1. **At Architect phase**, carefully review:
   - Technology choices make sense
   - Dependencies are correct
   - Architecture is sound

2. **If errors occur**, don't restart from scratch:
   ```bash
   # Extract what was learned
   foundry analyze SESSION_ID

   # Use insights in new build
   foundry build my-app "Same task but with fixes" --use-patterns
   ```

#### 6. Overnight Session Stopped

**Symptoms:**
Ralph Wiggum session terminated early

**Check logs:**

```bash
# View overnight log
tail -n 100 logs/overnight_*.log

# Look for:
# - API errors
# - Context limit exceeded
# - Task completion flag
```

**Resume:**

```bash
# Check checkpoint
cat checkpoints/ralph/SESSION_ID/state.json

# Resume from last good state
python ace/ralph_wiggum.py --resume SESSION_ID
```

### Debug Mode

Enable verbose debugging:

```bash
# Set debug environment variable
export CF_DEBUG=true

# Or in config
foundry config --set DEBUG true

# Run with debug output
foundry build my-app "Task" 2>&1 | tee debug.log
```

### Getting Help

1. **Check documentation**
   - README.md
   - CLI_GUIDE.md
   - This implementation guide

2. **Run health check**
   ```bash
   python tools/health_check.py
   ```

3. **Check GitHub Issues**
   - Search existing issues
   - File new issue with debug log

4. **Community Support**
   - GitHub Discussions
   - Discord (if available)

---

## Best Practices

### 1. Start Small, Scale Up

**❌ Don't:**
```bash
# First time using Context Foundry
foundry build mega-app "Complete e-commerce platform with microservices" --overnight 12
```

**✅ Do:**
```bash
# Start simple
foundry build calculator "Simple CLI calculator"

# Then medium
foundry build todo-api "REST API for todos"

# Then complex
foundry build ecommerce "E-commerce platform" --overnight 8
```

### 2. Always Review Plans

**The Architect phase is your highest leverage point.**

Spend 5-10 minutes reviewing:
- ✅ SPEC.md - Are all requirements captured?
- ✅ PLAN.md - Is the architecture sound?
- ✅ TASKS.md - Are tasks in logical order?

**A bad plan = thousands of bad lines of code.**

### 3. Build Pattern Library Gradually

```bash
# After successful builds, analyze
foundry analyze

# Check patterns extracted
foundry patterns --list

# Rate patterns
foundry patterns --rate PATTERN_ID 5

# Patterns improve future builds automatically
```

### 4. Use Overnight Mode Wisely

**Good candidates for overnight:**
- Well-defined features
- Repetitive tasks (CRUD APIs)
- Data pipelines
- Similar to past builds (patterns exist)

**Not good for overnight:**
- Exploratory work
- Novel architectures
- When requirements are unclear

### 5. Monitor Context Health

```bash
# Watch mode during builds
foundry status --watch

# Look for:
# - Context staying under 50%
# - Regular compaction occurring
# - No context warnings

# If context creeps up, investigate:
# - Are tasks too large?
# - Is compaction working?
# - Is context manager enabled?
```

### 6. Organize Projects

```
projects/
├── prod/           # Production projects
├── experiments/    # Experimental builds
├── examples/       # Example builds
└── archive/        # Completed projects
```

### 7. Commit Often

```yaml
# .foundry/config.yaml
git:
  auto_commit: true
  commit_after_task: true
  commit_template: "Complete Task {id}: {description} (Context: {context}%)"
```

### 8. Cost Management

```yaml
# Set cost limits
limits:
  max_cost_per_session: 20.00
  max_cost_per_task: 2.00
  alert_threshold: 10.00
```

```bash
# Analyze costs regularly
foundry analyze --cost-breakdown

# Use patterns to reduce costs (fewer retries)
foundry build my-app "Task" --use-patterns
```

### 9. Team Workflows

**For teams:**

1. **Shared pattern library** - One database, better patterns
2. **Code review** - Review generated PRs like any code
3. **Style guides** - Configure consistent style
4. **CI/CD integration** - Automated testing
5. **Documentation** - Generate docs automatically

### 10. Continuous Improvement

```bash
# After each sprint, analyze all sessions
for session in checkpoints/ralph/*; do
  foundry analyze $session --format markdown >> sprint-report.md
done

# Look for:
# - Which tasks work well autonomously
# - Which need human review
# - Pattern effectiveness
# - Cost trends
```

---

## Summary

This implementation guide covered:

✅ **Installation** - Step-by-step setup
✅ **Quick Start** - Your first build in 30 minutes
✅ **Agent Configuration** - Customizing Scout, Architect, Builder
✅ **Workflow Orchestration** - Advanced orchestration patterns
✅ **Integration** - CLI, Python API, CI/CD, other tools
✅ **Examples** - Real-world use cases
✅ **Testing** - Validation and quality assurance
✅ **Advanced Config** - Profiles, hooks, tuning
✅ **Production** - Deployment and monitoring
✅ **Troubleshooting** - Common issues and solutions
✅ **Best Practices** - Patterns for success

## Next Steps

1. **Install** Context Foundry (5 minutes)
2. **Run** your first build (30 minutes)
3. **Analyze** the results
4. **Extract** patterns
5. **Build** something bigger

## Philosophy

> **"Workflow over vibes. Specs before code. Context is everything."**

Context Foundry isn't about having AI write code for you. It's about **systematic engineering** of:

- Context (quality > quantity)
- Specifications (permanent artifacts)
- Workflows (structured phases)

The result: **Consistent, reviewable, production-ready code at scale.**

---

**Ready to build?**

```bash
foundry build your-app "Your amazing idea"
```

🚀 **Happy Building!**
