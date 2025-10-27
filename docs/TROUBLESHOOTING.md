# Context Foundry Troubleshooting Guide

Comprehensive troubleshooting for Context Foundry setup and builds.

---

## Table of Contents

1. [MCP Server Issues](#mcp-server-issues)
2. [GitHub Deployment Issues](#github-deployment-issues)
3. [Build Issues](#build-issues)
4. [Test Issues](#test-issues)
5. [Exit Code Reference](#exit-code-reference)
6. [Platform-Specific Issues](#platform-specific-issues)

---

## MCP Server Issues

### Issue: MCP Server Failed (Status: ✘ failed)

**Most common cause:** Dependencies not installed because virtual environment wasn't activated.

**Symptoms:**
```
Context-foundry MCP Server
Status: ✘ failed
Command: /home/you/homelab/context-foundry/venv/bin/python
Args: /home/you/homelab/context-foundry/tools/mcp_server.py
```

**Diagnosis:**
```bash
# Check if dependencies are installed
cd ~/homelab/context-foundry
source venv/bin/activate
python -c "import fastmcp" 2>&1

# If you see ImportError, dependencies are missing
```

**Solution:**
```bash
cd ~/homelab/context-foundry

# 1. Activate venv (CRITICAL STEP!)
source venv/bin/activate

# 2. Verify you see (venv) in your prompt
# Your prompt should look like: (venv) you@computer:~/homelab/context-foundry$

# 3. Install dependencies
pip install -r requirements-mcp.txt

# 4. Verify installation
python -c "from fastmcp import FastMCP; print('✅ Success!')"

# 5. Restart Claude Code
# Exit current session (Ctrl+C or 'exit')
claude
```

**Prevention:**
- Always activate venv BEFORE running pip install
- Look for `(venv)` prefix in your prompt
- Run verification command after installation

---

### Issue: ImportError: No module named 'fastmcp'

**Cause:** Virtual environment not activated when pip install was run.

**Solution:**
```bash
# Activate venv and reinstall
cd ~/homelab/context-foundry
source venv/bin/activate  # Must see (venv) prefix!
pip install -r requirements-mcp.txt
```

---

### Issue: Python Version Too Old

**Symptoms:**
```
SyntaxError: invalid syntax
```
or
```
Python 3.9 is not supported. Requires 3.10+
```

**Diagnosis:**
```bash
python3 --version
# Should be 3.10 or higher
```

**Solution (macOS):**
```bash
# Install Python 3.10+
brew install python@3.10

# Recreate venv with newer Python
cd ~/homelab/context-foundry
rm -rf venv
python3.10 -m venv venv
source venv/bin/activate
pip install -r requirements-mcp.txt
```

**Solution (Linux - Ubuntu/Debian):**
```bash
# Install Python 3.10+
sudo apt update
sudo apt install python3.10 python3.10-venv

# Recreate venv
cd ~/homelab/context-foundry
rm -rf venv
python3.10 -m venv venv
source venv/bin/activate
pip install -r requirements-mcp.txt
```

---

### Issue: MCP Server Not Connecting After Restart

**Symptoms:**
- MCP tools not available in Claude Code
- `/mcp` shows disconnected or failed status

**Solution:**
```bash
# 1. Verify MCP config exists
cat ~/.config/claude-code/mcp_settings.json
# or for project-scoped:
cat .mcp.json

# 2. Check paths are correct
# Ensure paths point to actual files

# 3. Restart Claude Code completely
# Exit session and restart: claude

# 4. Check MCP status
/mcp
# Should show connected status
```

---

## GitHub Deployment Issues

### Issue: Build Succeeded But Exit Code -15

**Symptoms:**
- Build process shows exit code -15 or SIGTERM
- Build files exist and work perfectly
- Process reports "failure" but everything seems fine

**What Really Happened:**
- ✅ Your build **DID** succeed! All files were created and tested.
- ❌ GitHub deployment failed (missing `gh` CLI or not authenticated)
- ⚠️ Process incorrectly reported this as a build failure

**Verify Build Succeeded:**
```bash
# Go to the project directory
cd /path/to/your/project

# Check if files exist
ls -la
# You should see: index.html, package.json, src/, etc.

# Try running it
npm install  # if applicable
npm run dev  # or npm start
```

**To Deploy to GitHub Manually:**
```bash
# 1. Install GitHub CLI (if needed)
# macOS:
brew install gh

# Linux:
sudo apt install gh

# 2. Authenticate
gh auth login

# 3. Initialize git (if not already done)
git init
git add .
git commit -m "Initial commit"

# 4. Create GitHub repo and push
gh repo create your-project-name --public --source=. --push
```

**Prevention:**
- Run `gh auth login` BEFORE building if you want GitHub deployment
- Or say: "Build locally only, skip GitHub deployment"

---

### Issue: GitHub CLI Not Found

**Symptoms:**
```
command not found: gh
```

**Solution (macOS):**
```bash
brew install gh
gh auth login
```

**Solution (Linux - Ubuntu/Debian):**
```bash
# Official installation
(type -p wget >/dev/null || (sudo apt update && sudo apt-get install wget -y)) \
&& sudo mkdir -p -m 755 /etc/apt/keyrings \
&& wget -qO- https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo tee /etc/apt/keyrings/githubcli-archive-keyring.gpg > /dev/null \
&& sudo chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg \
&& echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
&& sudo apt update \
&& sudo apt install gh -y

# Then authenticate
gh auth login
```

---

### Issue: Not Authenticated to GitHub

**Symptoms:**
```
gh: To get started with GitHub CLI, please run: gh auth login
```

**Solution:**
```bash
gh auth login

# Follow prompts:
# 1. Choose: GitHub.com
# 2. Choose: HTTPS
# 3. Choose: Login with a web browser
# 4. Copy the one-time code
# 5. Press Enter to open browser
# 6. Paste code and authorize
```

**Verification:**
```bash
gh auth status
# Should show: Logged in to github.com as yourusername
```

---

## Build Issues

### Issue: Build Timeout

**Symptoms:**
- Build process times out after 90 minutes
- Complex projects don't finish in time

**Solution:**
```
Build [complex project description]

Use a timeout of 120 minutes for this build.
```

**For Very Complex Projects:**
```
Build [complex project description]

Use a timeout of 180 minutes and enable incremental mode.
```

---

### Issue: Tests Keep Failing

**Symptoms:**
- Test loop reaches max iterations (3) without passing
- Same tests fail repeatedly

**Diagnosis:**
```bash
# Check test failure reports
cd /path/to/project
cat .context-foundry/test-results-iteration-*.md
```

**Solutions:**

**Option 1: Increase max iterations**
```
Build [project description]

Use max_test_iterations of 5.
```

**Option 2: Disable test loop to see raw output**
```
Build [project description]

Disable the test loop so I can see the raw test output.
```

**Option 3: Review fix attempts**
```bash
# Check what fixes were attempted
cat .context-foundry/fixes-iteration-*.md
```

---

### Issue: Missing README or .gitignore

**Symptoms:**
- Build completes but no README.md in project root
- No .gitignore file, unwanted files committed

**Cause:**
- Using older version of Context Foundry (before Build Finalization feature)

**Solution:**
```bash
# Update to latest version
cd ~/homelab/context-foundry
git pull origin main
source venv/bin/activate
pip install -r requirements-mcp.txt --upgrade

# Restart Claude Code
```

**Manual Fix (if needed):**
- README.md and .gitignore should be auto-generated now
- If using older builds, create manually based on project type

---

## Test Issues

### Issue: Test Results Show "PASS" But Features Don't Work

**Cause:**
- Unit tests may pass but integration/E2E tests missing
- Tests may not cover all user scenarios

**Solution:**
```bash
# Manual testing
cd /path/to/project

# For web apps:
npm run dev
# Then test in browser

# For APIs:
curl http://localhost:3000/endpoint

# For CLI tools:
./your-tool --help
```

**Report Issues:**
If manual testing reveals bugs, the autonomous build can fix them:
```
The [feature] doesn't work correctly. I tested it and found [specific issue].
Please fix this in the project at /path/to/project.
```

---

## Exit Code Reference

Context Foundry uses specific exit codes to indicate different outcomes:

| Exit Code | Meaning | What Happened |
|-----------|---------|---------------|
| **0** | Complete success | Build succeeded AND deployment succeeded |
| **10** | Build success, deployment skipped | All files created and tested successfully. GitHub deployment skipped (gh CLI not available or not authenticated). **This is a success!** |
| **11** | Build success, deployment failed | All files created and tested successfully. GitHub deployment attempted but failed (GitHub error). **This is a success!** |
| **1** | Build failed | Code errors, tests failed after max iterations, or critical build error |
| **-15 (SIGTERM)** | Process terminated | Old behavior (deprecated). Newer versions use exit codes 10/11 instead |

**How to Interpret:**
- **Exit codes 0, 10, 11**: Your build worked! Check project directory for files.
- **Exit code 1**: Build had problems. Check test reports and error logs.
- **Exit code -15**: Likely deployment issue on older version. Check if files exist in project directory.

---

## Platform-Specific Issues

### macOS Issues

**Issue: Permission Denied When Creating Venv**

**Solution:**
```bash
# Ensure Python is from Homebrew, not system Python
brew install python@3.10
python3.10 -m venv venv
```

---

### Linux Issues

**Issue: externally-managed-environment Error**

**Symptoms:**
```
error: externally-managed-environment
```

**Cause:**
Debian/Ubuntu systems prevent pip install to system Python for safety.

**Solution:**
```bash
# Always use virtual environment (best practice)
cd ~/homelab/context-foundry
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-mcp.txt
```

---

**Issue: Python 3.10 Not Available on Older Ubuntu**

**Solution:**
```bash
# Add deadsnakes PPA for newer Python versions
sudo apt update
sudo apt install software-properties-common
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.10 python3.10-venv

# Use Python 3.10 for venv
python3.10 -m venv venv
source venv/bin/activate
pip install -r requirements-mcp.txt
```

---

### Windows Issues

**Issue: Venv Activation Fails**

**Solution (PowerShell):**
```powershell
# Enable script execution
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Activate venv
venv\Scripts\Activate.ps1
```

**Solution (Command Prompt):**
```cmd
venv\Scripts\activate.bat
```

---

## Getting More Help

If you're still stuck after trying these solutions:

1. **Check the FAQ**: See [FAQ.md](../FAQ.md) for common questions
2. **Check logs**: `.context-foundry/` directory contains detailed build logs
3. **GitHub Issues**: [https://github.com/context-foundry/context-foundry/issues](https://github.com/context-foundry/context-foundry/issues)
4. **Discussions**: [https://github.com/context-foundry/context-foundry/discussions](https://github.com/context-foundry/context-foundry/discussions)

---

## Quick Diagnostic Checklist

Run through this checklist to quickly identify common issues:

```bash
# 1. Python version
python3 --version
# ✅ Should be 3.10+

# 2. Venv exists
ls -la venv/
# ✅ Should show venv directory

# 3. Venv activated
echo $VIRTUAL_ENV
# ✅ Should show path to venv

# 4. Dependencies installed
python -c "import fastmcp; print('OK')"
# ✅ Should print OK

# 5. GitHub CLI available
command -v gh
# ✅ Should show path to gh

# 6. GitHub authenticated
gh auth status
# ✅ Should show logged in status

# 7. Git configured
git config user.name && git config user.email
# ✅ Should show your name and email

# 8. MCP config exists
test -f ~/.config/claude-code/mcp_settings.json && echo "Global config found" || test -f .mcp.json && echo "Project config found"
# ✅ Should find at least one config
```

If all checks pass, Context Foundry should work correctly!

---

*Last updated: 2025-10-26*
