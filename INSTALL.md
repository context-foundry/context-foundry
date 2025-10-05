# Context Foundry Installation Guide

> **Complete installation guide with troubleshooting based on real-world deployment experience**

## Table of Contents
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Detailed Installation](#detailed-installation)
- [Two Modes Explained](#two-modes-explained)
- [Common Issues & Solutions](#common-issues--solutions)
- [Lessons Learned](#lessons-learned)

---

## Prerequisites

### Python Version Requirements

Context Foundry has a **two-tier Python requirement structure**:

| Mode | Python Version | Why? |
|------|---------------|------|
| **API Mode** | Python 3.9+ | Base dependencies work with 3.9 |
| **MCP Mode** | Python 3.10+ | FastMCP package requires 3.10+ |

**Check your Python version:**
```bash
python --version
python3 --version
python3.10 --version  # If you have 3.10 installed
```

### Other Requirements

- **Git** (for cloning the repository)
- **pip** (Python package manager)
- **For MCP Mode**: Claude Desktop with Pro/Max subscription
- **For API Mode**: Anthropic API key

---

## Quick Start

### Option 1: API Mode (Works with Python 3.9+)

```bash
# Clone repository
git clone https://github.com/snedea/context-foundry.git
cd context-foundry

# Install dependencies
pip install -r requirements.txt

# Install Context Foundry
pip install -e .

# Add to PATH (macOS/Linux)
export PATH="$HOME/Library/Python/3.9/bin:$PATH"
echo 'export PATH="$HOME/Library/Python/3.9/bin:$PATH"' >> ~/.zshrc

# Set API key
export ANTHROPIC_API_KEY=your_key_here

# Test installation
foundry --version

# Build your first project
foundry build my-app "Create a todo CLI app"
```

### Option 2: MCP Mode (Requires Python 3.10+)

```bash
# Clone repository
git clone https://github.com/snedea/context-foundry.git
cd context-foundry

# Install with Python 3.10
python3.10 -m pip install -r requirements.txt
python3.10 -m pip install -r requirements-mcp.txt
python3.10 -m pip install -e .

# Add to PATH (prioritize Python 3.10)
export PATH="/opt/homebrew/bin:$PATH"
echo 'export PATH="/opt/homebrew/bin:$PATH"' >> ~/.zshrc

# Configure Claude Desktop
foundry serve --config-help

# Follow the instructions to set up Claude Desktop
```

---

## Detailed Installation

### Step 1: Install Python 3.10+ (For MCP Mode)

If you want MCP mode and don't have Python 3.10+:

**macOS (Homebrew):**
```bash
brew install python@3.10
python3.10 --version  # Verify installation
```

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install python3.10 python3.10-venv python3.10-pip
```

**Windows:**
Download from [python.org](https://www.python.org/downloads/) and install Python 3.10 or higher.

### Step 2: Clone Repository

```bash
git clone https://github.com/snedea/context-foundry.git
cd context-foundry
```

### Step 3: Install Dependencies

**For API Mode (Python 3.9+):**
```bash
pip install -r requirements.txt
```

**For MCP Mode (Python 3.10+):**
```bash
python3.10 -m pip install -r requirements.txt
python3.10 -m pip install -r requirements-mcp.txt
```

**What's the difference?**
- `requirements.txt` - Core dependencies (works with Python 3.9+)
- `requirements-mcp.txt` - Adds FastMCP for MCP server mode (requires Python 3.10+)

### Step 4: Install Context Foundry

**For Python 3.9 (API mode only):**
```bash
pip install -e .
```

**For Python 3.10+ (both modes):**
```bash
python3.10 -m pip install -e .
```

**What does `-e` mean?**
"Editable install" - changes you make to the code are immediately available without reinstalling.

### Step 5: Fix PATH Issues

This is crucial - the `foundry` command needs to be in your PATH.

**Find where foundry was installed:**
```bash
# For Python 3.9
ls $HOME/Library/Python/3.9/bin/foundry

# For Python 3.10
ls /opt/homebrew/bin/foundry
```

**Add to PATH:**

**If using Python 3.9:**
```bash
export PATH="$HOME/Library/Python/3.9/bin:$PATH"
echo 'export PATH="$HOME/Library/Python/3.9/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

**If using Python 3.10 (MCP mode):**
```bash
export PATH="/opt/homebrew/bin:$PATH"
echo 'export PATH="/opt/homebrew/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

**Verify it works:**
```bash
foundry --version
# Should show: foundry, version 1.0.0
```

### Step 6A: Configure API Mode

```bash
export ANTHROPIC_API_KEY=your_key_here
echo 'export ANTHROPIC_API_KEY=your_key_here' >> ~/.zshrc

# Test
foundry build test-app "Create a hello world app"
```

### Step 6B: Configure MCP Mode

```bash
# Get configuration instructions
foundry serve --config-help

# Create config file
mkdir -p ~/Library/Application\ Support/Claude
cat > ~/Library/Application\ Support/Claude/claude_desktop_config.json << 'EOF'
{
  "mcpServers": {
    "context-foundry": {
      "command": "python3.10",
      "args": ["-m", "tools.mcp_server"],
      "cwd": "/Users/YOUR_USERNAME/path/to/context-foundry"
    }
  }
}
EOF

# Important: Replace the "cwd" path with your actual path!

# Restart Claude Desktop
# Test by asking: "What MCP tools are available?"
```

---

## Two Modes Explained

### API Mode

**How it works:**
- You run `foundry build` from command line
- Context Foundry calls Anthropic API directly
- You get charged per token used

**Pros:**
- ✅ Works with Python 3.9
- ✅ No Claude Desktop needed
- ✅ Good for CI/CD and automation
- ✅ Simple setup

**Cons:**
- ❌ Costs money (API charges)
- ❌ Need to manage API keys

**Use cases:**
- Automated build pipelines
- Server environments
- Batch processing
- Don't have Claude Pro/Max subscription

### MCP Mode

**How it works:**
- Context Foundry runs as MCP server
- Claude Desktop connects to it
- You talk to Claude Desktop
- Claude processes prompts using your subscription
- No additional per-token API charges (beyond subscription cost)

**Current Status:**
- ✅ MCP mode works as terminal-based MCP server (uses API key)
- ⚠️ Claude Desktop integration not available (would use subscription - blocked by sampling support)
- ✅ Use `foundry serve` to run MCP server
- ℹ️ See docs/MCP_SETUP.md for details

**Pros (when available):**
- ✅ Uses Claude Pro/Max subscription ($20/month) instead of per-token charges
- ✅ Integrated with Claude Desktop
- ✅ Interactive and conversational
- ✅ Can review and iterate easily

**Cons:**
- ❌ Requires Python 3.10+
- ❌ Requires Claude Pro/Max subscription
- ❌ Only works when Claude Desktop is running
- ❌ More complex setup

**Use cases:**
- Interactive development
- Iterative refinement
- Learning and experimentation
- Cost-conscious development

---

## Common Issues & Solutions

### Issue 1: `command not found: foundry`

**Problem:** The `foundry` command isn't in your PATH.

**Solution:**
```bash
# Find where it was installed
python -m site --user-base
ls $HOME/Library/Python/3.9/bin/ | grep foundry

# Add to PATH
export PATH="$HOME/Library/Python/3.9/bin:$PATH"
echo 'export PATH="$HOME/Library/Python/3.9/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

### Issue 2: `ModuleNotFoundError: No module named 'tools'`

**Problem:** Missing `__init__.py` files in package directories.

**Solution:**
```bash
# Create missing __init__.py files
touch tools/__init__.py
touch ace/__init__.py
touch workflows/__init__.py
touch foundry/__init__.py

# Reinstall
python3.10 -m pip install -e .
```

This happened because the original setup.py used `find_packages()` but the directories weren't proper Python packages without `__init__.py` files.

### Issue 3: `ERROR: Could not find a version that satisfies the requirement fastmcp`

**Problem:** FastMCP requires Python 3.10+, but you're using Python 3.9.

**Solutions:**

**Option A - Upgrade Python:**
```bash
brew install python@3.10
python3.10 -m pip install -r requirements-mcp.txt
```

**Option B - Use API mode instead:**
```bash
# Just install base requirements
pip install -r requirements.txt

# Use API mode
export ANTHROPIC_API_KEY=your_key
foundry build my-app "task description"
```

### Issue 4: Python Version Mismatch

**Problem:** `foundry` uses Python 3.9 but you want MCP mode (needs 3.10).

**Why this happens:**
- You installed with both Python 3.9 and 3.10
- PATH has Python 3.9's bin directory first
- The `foundry` script uses the first Python it was installed with

**Solution:**
```bash
# Uninstall from all Python versions
pip uninstall context-foundry
python3.10 -m pip uninstall context-foundry

# Install only with Python 3.10
python3.10 -m pip install -e .

# Fix PATH order (put Python 3.10 first)
export PATH="/opt/homebrew/bin:$PATH"

# Verify
which foundry
# Should show: /opt/homebrew/bin/foundry

head -1 /opt/homebrew/bin/foundry
# Should show: #!/opt/homebrew/opt/python@3.10/bin/python3.10
```

### Issue 5: urllib3 SSL Warning

**Problem:**
```
NotOpenSSLWarning: urllib3 v2 only supports OpenSSL 1.1.1+
```

**Solution:** This is harmless - it's just a warning. The software still works correctly. If it bothers you:

```bash
pip install 'urllib3<2.0'
```

### Issue 6: Claude Desktop Doesn't Show MCP Server

**Checklist:**
1. ✅ Python 3.10+ installed?
2. ✅ FastMCP installed? (`python3.10 -c "from fastmcp import FastMCP"`)
3. ✅ Config file exists? (`cat ~/Library/Application\ Support/Claude/claude_desktop_config.json`)
4. ✅ Config file has correct path? (Use absolute path, not ~)
5. ✅ Config file valid JSON? (Check at jsonlint.com)
6. ✅ Claude Desktop restarted? (Quit completely, not just close window)

**Debug:**
```bash
# Test if MCP server can start
python3.10 -m tools.mcp_server

# Should show startup messages, not errors
```

---

## Lessons Learned

### 1. Python Version Management is Critical

**The Challenge:**
We initially tried to use a single Python version for both modes, but FastMCP requires Python 3.10+ while many users have Python 3.9. This created a conflict.

**The Solution:**
Two-tier architecture:
- Base installation works with Python 3.9
- MCP mode is optional and requires Python 3.10+
- Clear error messages guide users

**Key Insight:**
Don't force users to upgrade if they don't need the feature. Make advanced features opt-in.

### 2. Package Structure Matters

**The Challenge:**
Directories like `tools/`, `ace/`, `workflows/` weren't recognized as Python packages, causing `ModuleNotFoundError`.

**The Solution:**
Added `__init__.py` files to all package directories.

**Key Insight:**
`setup.py`'s `find_packages()` requires `__init__.py` files. Don't assume directories are packages without them.

### 3. PATH Management is Non-Trivial

**The Challenge:**
Users had multiple Python versions (3.9, 3.10, 3.11) each with their own bin directories. The `foundry` command would use whichever was first in PATH.

**The Solution:**
- Document exactly where the command gets installed
- Provide explicit PATH setup instructions
- Explain how to prioritize Python 3.10 for MCP mode

**Key Insight:**
Never assume users have a clean Python environment. Be explicit about PATH configuration.

### 4. Editable Installs Can Be Tricky

**The Challenge:**
`pip install -e .` sometimes didn't work correctly, especially when switching between Python versions.

**The Solution:**
- Always uninstall before reinstalling
- Use `python3.10 -m pip` to be explicit about which Python
- Run `pip install -e .` from the project root directory

**Key Insight:**
Editable installs are powerful but require proper package structure. Test installation in a fresh environment.

### 5. Dependencies Should Be Gradual

**The Challenge:**
Initially had MCP dependencies in `requirements.txt`, which failed for Python 3.9 users.

**The Solution:**
- `requirements.txt` - Core dependencies only
- `requirements-mcp.txt` - Optional MCP dependencies
- Clear documentation about when to use each

**Key Insight:**
Not all users need all features. Make dependencies match the features users actually want.

### 6. Error Messages Should Be Helpful

**The Challenge:**
Users got cryptic errors like "No module named fastmcp" without understanding why.

**The Solution:**
Added friendly error messages explaining:
- What the problem is
- Why it's happening
- How to fix it (with exact commands)
- Alternative approaches

**Example:**
```python
try:
    from fastmcp import FastMCP
except ImportError:
    print("❌ Error: FastMCP not installed")
    print("MCP mode requires Python 3.10+ and fastmcp package")
    print("Option 1: Upgrade Python and run: pip install -r requirements-mcp.txt")
    print("Option 2: Use API mode instead: foundry build <project> <task>")
    sys.exit(1)
```

**Key Insight:**
Good error messages save hours of debugging. Invest in user-facing error handling.

### 7. Documentation Should Match Reality

**The Challenge:**
Documentation said "just run this command" but didn't account for real-world issues like PATH problems, Python version conflicts, or missing dependencies.

**The Solution:**
- Document common issues based on actual experience
- Include troubleshooting for each step
- Explain the "why" not just the "what"
- Test installation steps on fresh machines

**Key Insight:**
The best documentation comes from real deployment experience. Write docs after you've debugged the issues, not before.

### 8. Two Modes Require Two Strategies

**The Challenge:**
API mode and MCP mode have completely different execution models. API mode is synchronous CLI, MCP mode is async server.

**The Solution:**
- Shared core (`AutonomousOrchestrator`)
- Different clients (`ClaudeClient` vs `ClaudeCodeClient`)
- Factory pattern to choose the right one
- Clear documentation about when to use each

**Key Insight:**
Build abstractions that allow different execution modes without duplicating business logic.

---

## Verification Checklist

After installation, verify everything works:

### API Mode Verification

```bash
# 1. Command is available
foundry --version
# ✅ Should show: foundry, version 1.0.0

# 2. Python version (3.9+ OK)
python --version
# ✅ Should show: Python 3.9.x or higher

# 3. Dependencies installed
python -c "import anthropic, click, rich"
# ✅ Should complete without errors

# 4. API key set
echo $ANTHROPIC_API_KEY
# ✅ Should show your API key

# 5. Build works
foundry build test "Create a hello world script"
# ✅ Should start Scout → Architect → Builder workflow
```

### MCP Mode Verification

```bash
# 1. Python 3.10+ available
python3.10 --version
# ✅ Should show: Python 3.10.x or higher

# 2. FastMCP installed
python3.10 -c "from fastmcp import FastMCP; print('✅ OK')"
# ✅ Should print: ✅ OK

# 3. Foundry uses Python 3.10
head -1 $(which foundry)
# ✅ Should show: #!/opt/homebrew/opt/python@3.10/bin/python3.10

# 4. Config help works
foundry serve --config-help
# ✅ Should show configuration instructions

# 5. Config file exists
cat ~/Library/Application\ Support/Claude/claude_desktop_config.json
# ✅ Should show valid JSON config

# 6. In Claude Desktop: Ask "What MCP tools are available?"
# ✅ Should list: context_foundry_build, context_foundry_status, context_foundry_enhance
```

---

## Next Steps

- **New Users**: Start with the [Tutorial](docs/TUTORIAL.md)
- **MCP Users**: See [MCP Setup Guide](docs/MCP_SETUP.md)
- **Contributing**: See [CONTRIBUTING.md](CONTRIBUTING.md)
- **Issues**: Report at [GitHub Issues](https://github.com/snedea/context-foundry/issues)

---

## Support

Having trouble? Check these resources:

1. **Common Issues** section above
2. **MCP Setup Guide**: [docs/MCP_SETUP.md](docs/MCP_SETUP.md)
3. **Tutorial**: [docs/TUTORIAL.md](docs/TUTORIAL.md)
4. **GitHub Issues**: https://github.com/snedea/context-foundry/issues

---

**Installation complete! Ready to build with Context Foundry.** 🎉
