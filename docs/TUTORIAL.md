# From Zero to First PR in 30 Minutes

This tutorial will take you from nothing to a working pull request in 30 minutes using Context Foundry.

## Prerequisites

Before starting, make sure you have:
- Python 3.8 or higher installed
- Git installed
- A text editor
- 30 minutes of focused time

## Step 1: Installation (5 minutes)

### 1.1 Clone the Repository

```bash
# Clone Context Foundry
git clone https://github.com/yourusername/context-foundry.git
cd context-foundry
```

### 1.2 Install Dependencies

```bash
# Install in development mode (recommended)
pip install -e .

# Verify installation
foundry --version
# Should output: foundry, version 1.0.0
```

**Troubleshooting:**
- **Linux:** If `foundry` command not found, add `~/.local/bin` to your PATH
- **macOS:** If `foundry` command not found, add `~/Library/Python/3.9/bin` to your PATH (adjust Python version as needed)
- If you get permission errors, use `pip install -e . --user`
- SSL warnings about urllib3 are harmless and can be ignored

### 1.3 Get Your API Key

1. Go to [Anthropic Console](https://console.anthropic.com/)
2. Sign up or log in
3. Navigate to API Keys
4. Create a new API key
5. Copy it (it starts with `sk-ant-`)

### 1.4 Configure Environment

```bash
# Initialize configuration
foundry config --init

# Set your API key
export ANTHROPIC_API_KEY=sk-ant-api03-your-key-here

# Or add to .env file
echo "ANTHROPIC_API_KEY=sk-ant-api03-your-key-here" >> .env
```

### 1.5 Verify Setup

```bash
# Run health check
python3 tools/health_check.py

# You should see: ✅ All critical checks passed!
```

## Step 2: Your First Build (15 minutes)

Let's build a simple CLI todo application as our first project.

### Key Insight: Don't Overthink the Prompt

**You don't need to be a prompt engineer.** The initial command is just a starting point:

- ✅ **Good enough beats perfect** - Describe what you want in 1-2 sentences
- ✅ **The power is in refinement** - You'll review and edit the plan before any code is written
- ✅ **80/20 rule** - Your prompt gets you 80% there, checkpoint editing gets you to 100%

**Traditional approach:**
```
❌ Spend 30 minutes crafting the perfect prompt
❌ Hope the AI understands everything
❌ Get frustrated when it doesn't
```

**Context Foundry approach:**
```
✅ Spend 2 minutes on a "good enough" prompt
✅ Review the generated plan (5 minutes)
✅ Edit the SPEC/PLAN/TASKS files to make it perfect
✅ Approve and let it build exactly what you want
```

**Bottom line:** The critical checkpoint is at the Architect phase where you review and edit the plan, not the initial prompt.

### 2.1 Start the Build

```bash
foundry build todo-cli "Create a CLI todo app with add, list, and complete commands. Use local JSON file for storage."
```

**Note:** Your project will be created in the `examples/todo-cli/` directory (relative to your Context Foundry installation). This keeps generated projects organized and separate from the Context Foundry codebase.

**What happens next:**

1. **Scout Phase** (~2 minutes)
   - Context Foundry researches CLI best practices
   - Explores storage options (JSON vs SQLite)
   - Identifies relevant patterns

   You'll see output like:
   ```
   🔍 SCOUT Phase Starting...
   Researching: CLI frameworks
   Researching: JSON storage patterns
   Research complete: blueprints/specs/RESEARCH_[timestamp].md
   ```

2. **Review Point: Research**

   ```
   📋 Review research artifact? (y/n):
   ```

   Type `y` and review the research. Look for:
   - Architecture choices explained
   - Technology recommendations
   - Potential challenges identified

   Press Enter to continue.

3. **Architect Phase** (~3 minutes)
   - Creates technical specification
   - Generates implementation plan
   - Breaks down into tasks

   You'll see:
   ```
   📐 ARCHITECT Phase Starting...
   Creating specification...
   Generating plan...
   Breaking into tasks...
   ```

4. **Review Point: Plan** ⚠️ **IMPORTANT**

   ```
   📋 Review plan and tasks? (y/n):
   ```

   **This is your highest leverage point!** Type `y` and carefully review:

   - `blueprints/specs/SPEC_[timestamp].md` - What will be built
   - `blueprints/plans/PLAN_[timestamp].md` - How it will be built
   - `blueprints/tasks/TASKS_[timestamp].md` - Step-by-step tasks

   Look for:
   - ✅ All features you requested are included
   - ✅ Architecture makes sense
   - ✅ Tasks are in logical order
   - ❌ Anything unnecessary or over-engineered

   **Pro tip:** A bad plan = thousands of bad lines of code. Take your time here!

   **💡 You can customize the plan!** If you want to make changes:
   1. Edit any of the `.md` files directly in your text editor
   2. Modify specs, adjust the plan, add/remove/reorder tasks, etc.
   3. Save your changes
   4. Type `approve` in the console
   5. The Builder will use your edited files!

   This gives you full control to fine-tune the implementation before any code is written.

5. **Builder Phase** (~10 minutes)
   - Implements each task sequentially
   - Writes tests first, then implementation
   - Creates git commits after each task
   - Compacts context automatically

   You'll see:
   ```
   🔨 BUILDER Phase Starting...
   [1/8] Creating project structure...
   [2/8] Implementing add command...
   [3/8] Implementing list command...
   ...
   ```

### 2.2 While Building: Monitor Progress

In another terminal, watch live progress:

```bash
# Watch mode (updates every 5 seconds)
foundry status --watch
```

You'll see:
- Current phase
- Tasks completed
- Tasks remaining
- Context usage (should stay under 50%)

## Step 3: Review Results (5 minutes)

### 3.1 Check the Output

```bash
# Your new project is in the examples directory
cd examples/todo-cli

# List files
ls -la

# You should see:
# - todo.py (main application)
# - test_todo.py (tests)
# - README.md (documentation)
# - requirements.txt (dependencies)
```

### 3.2 Run the Application

```bash
# Install dependencies (if any)
pip install -r requirements.txt

# Run the app
python3 todo.py add "Learn Context Foundry"
python3 todo.py list

# You should see your todo item!
```

### 3.3 Run Tests

```bash
# Run the test suite
pytest test_todo.py

# All tests should pass ✅
```

### 3.4 Check Git History

```bash
# View commits
git log --oneline

# You should see commits for each task:
# abc1234 Implement complete command
# def5678 Implement list command
# ghi9012 Implement add command
# ...
```

## Step 4: Analyze Session (5 minutes)

### 4.1 Generate Analysis Report

```bash
# Analyze the session
foundry analyze --format markdown --save report.md

# Open the report
cat report.md
```

You'll see:
- Completion rate (should be ~100%)
- Token usage
- Estimated cost
- Context efficiency metrics

### 4.2 Check Pattern Library

```bash
# View extracted patterns
foundry patterns --stats

# You should see patterns extracted from your build
foundry patterns --list
```

These patterns will be automatically reused in future builds!

## What You Just Did

In 30 minutes, you:

1. ✅ Installed Context Foundry
2. ✅ Configured API access
3. ✅ Built a complete CLI application
4. ✅ Got working code with tests
5. ✅ Received git history with meaningful commits
6. ✅ Extracted reusable patterns

**And most importantly:** You didn't write a single line of code manually!

## Next Steps

### Try More Complex Builds

```bash
# Build a REST API
foundry build api-server "REST API with JWT authentication and PostgreSQL" --livestream

# Build a web app
foundry build webapp "Todo app with React frontend and Express backend"

# Overnight autonomous session
foundry build big-project "Full e-commerce platform" --overnight 8
```

### Enable Livestream Dashboard

```bash
# Start with livestream enabled
foundry build my-app "Your task" --livestream

# Open browser to http://localhost:8765
# Watch progress in real-time!
```

### Autonomous Mode (No Reviews)

```bash
# Skip all review checkpoints
foundry build my-app "Your task" --autonomous

# Good for:
# - Simple, well-defined tasks
# - Overnight runs
# - When you trust the patterns
```

## Common Issues and Solutions

### Issue: Command not found

**On Linux:**
```bash
# Solution: Add pip bin directory to PATH
export PATH="$HOME/.local/bin:$PATH"

# Add to ~/.bashrc or ~/.zshrc to make permanent
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
```

**On macOS:**
```bash
# Solution: Add Python user bin directory to PATH
export PATH="$HOME/Library/Python/3.9/bin:$PATH"

# Add to ~/.zshrc or ~/.bashrc to make permanent
echo 'export PATH="$HOME/Library/Python/3.9/bin:$PATH"' >> ~/.zshrc

# Reload your configuration
source ~/.zshrc
```

**Note:** Adjust the Python version (3.9) to match your installed version.

### Issue: API key not set

```bash
# Check if set
echo $ANTHROPIC_API_KEY

# Set temporarily
export ANTHROPIC_API_KEY=your_key_here

# Set permanently in .env
foundry config --init
# Then edit .env file
```

### Issue: Import errors

```bash
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall

# If that doesn't work, use a virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

### Issue: Build seems stuck

```bash
# Check status in another terminal
foundry status --watch

# Look for:
# - Context usage (if >80%, compaction might be running)
# - Current task (shows what it's working on)
# - Error messages
```

### Issue: Context usage too high

```bash
# Context manager should auto-compact at 40%
# If not working, check configuration:
foundry config --show

# Ensure context manager is enabled
foundry config --set USE_CONTEXT_MANAGER true
```

### Issue: Tests failing in build

This is actually **expected behavior**! Context Foundry uses TDD:

1. Writes failing tests first
2. Implements code to make tests pass
3. Commits when tests pass

If you see test failures during the build, that's normal. Check the final result.

### Issue: Generated code doesn't match request

**This is why we review!** At the Architect phase:

1. Carefully review `SPEC.md` and `PLAN.md`
2. If something is wrong, type `n` when asked to approve
3. Provide feedback on what needs to change
4. The system will revise the plan

**Pro tip:** 5 minutes reviewing the plan saves hours of bad implementation.

## Understanding the Three Phases

### 🔍 Scout (Research)
- **Purpose:** Understand the problem space
- **Output:** Research artifact (~5K tokens)
- **What to review:** Architecture choices, technology recommendations
- **Context target:** <30%

### 📐 Architect (Planning)
- **Purpose:** Create detailed technical plan
- **Output:** Spec, plan, and task breakdown
- **What to review:** ⚠️ **CRITICAL** - Review everything carefully!
- **Context target:** <40%
- **Why it matters:** Bad plan = thousands of bad LOC
- **Customization:** Edit the .md files directly before approving - your changes will be used

### 🔨 Builder (Implementation)
- **Purpose:** Execute the plan
- **Output:** Working code, tests, commits
- **What to review:** Final PR before merging
- **Context target:** <50%
- **Features:** TDD, auto-compaction, checkpointing

## Tips for Success

### 1. Be Specific in Task Descriptions

**❌ Bad:** "Build an app"
**✅ Good:** "Build a CLI todo app with add, list, complete, and delete commands using JSON file storage"

### 2. Always Review the Plan

The Architect phase is your highest leverage point:
- 5 minutes reviewing = hours saved
- Check for over-engineering
- Verify all features are included
- Ensure architecture makes sense

### 3. Use Patterns

After your first few builds:
```bash
# Check what patterns you've learned
foundry patterns --stats

# These automatically improve future builds!
```

### 4. Monitor Context Usage

```bash
# Watch mode is your friend
foundry status --watch

# Context should stay under 50%
# If it doesn't, context manager will auto-compact
```

### 5. Use Overnight Mode for Big Projects

```bash
# Complex projects? Let it run overnight
foundry build big-project "Full REST API with auth" --overnight 8

# Check progress in the morning
foundry status
foundry analyze
```

## Video Walkthrough

*Coming soon: Video tutorial showing this entire process in real-time*

## Get Help

- 📖 Documentation: [CLI_GUIDE.md](../CLI_GUIDE.md)
- 🐛 Issues: [GitHub Issues](https://github.com/yourusername/context-foundry/issues)
- 💬 Community: [GitHub Discussions](https://github.com/yourusername/context-foundry/discussions)
- 📧 Email: support@contextfoundry.dev

## Congratulations!

You've completed your first Context Foundry build. You now understand:

- The three-phase workflow (Scout → Architect → Builder)
- How to review at critical checkpoints
- How to monitor progress and context usage
- How the pattern library learns from your builds

**Now go build something amazing!** 🚀

---

*"Workflow over vibes. Specs before code. Context is everything."*
