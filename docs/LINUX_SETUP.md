# Context Foundry - Linux Setup Guide

Complete setup guide for Context Foundry on Linux systems (Ubuntu, Debian, Fedora, Arch).

---

## Quick Setup (Ubuntu/Debian)

```bash
# 1. Install dependencies
sudo apt update
sudo apt install python3.10 python3.10-venv git

# 2. Install GitHub CLI
sudo apt install gh

# 3. Clone Context Foundry
cd ~/homelab  # or your preferred location
git clone https://github.com/context-foundry/context-foundry.git
cd context-foundry

# 4. Create virtual environment
python3 -m venv venv

# 5. ⚠️ CRITICAL: Activate venv BEFORE pip install!
source venv/bin/activate
# Your prompt should now show: (venv)

# 6. Install MCP dependencies
pip install -r requirements-mcp.txt

# 7. Verify installation
python -c "from fastmcp import FastMCP; print('✅ MCP ready!')"

# 8. Configure Claude Code MCP
claude mcp add --transport stdio context-foundry -s project -- $(pwd)/venv/bin/python $(pwd)/tools/mcp_server.py

# 9. Verify config
cat .mcp.json

# 10. Authenticate with GitHub (optional, for deployment)
gh auth login

# 11. Configure git
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"

# Done! Start Claude Code
claude
```

---

## Detailed Setup by Distribution

### Ubuntu / Debian

#### Prerequisites

**Ubuntu 22.04 LTS or newer** (recommended)

**Check Python version:**
```bash
python3 --version
# Needs to be 3.10 or higher
```

**If Python < 3.10:**
```bash
# Add deadsnakes PPA for newer Python
sudo apt update
sudo apt install software-properties-common
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.10 python3.10-venv
```

#### Install System Dependencies

```bash
sudo apt update
sudo apt install -y \
  python3.10 \
  python3.10-venv \
  python3-pip \
  git \
  curl \
  wget
```

#### Install GitHub CLI

**Official method (recommended):**
```bash
(type -p wget >/dev/null || (sudo apt update && sudo apt-get install wget -y)) \
&& sudo mkdir -p -m 755 /etc/apt/keyrings \
&& wget -qO- https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo tee /etc/apt/keyrings/githubcli-archive-keyring.gpg > /dev/null \
&& sudo chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg \
&& echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
&& sudo apt update \
&& sudo apt install gh -y
```

**Verify:**
```bash
gh --version
```

---

### Fedora / RHEL / CentOS

#### Install Dependencies

```bash
# Fedora
sudo dnf install -y python3.10 python3-pip git

# RHEL/CentOS with EPEL
sudo dnf install -y epel-release
sudo dnf install -y python3.10 python3-pip git
```

#### Install GitHub CLI

```bash
sudo dnf install -y gh
```

---

### Arch Linux

#### Install Dependencies

```bash
sudo pacman -S python python-pip git github-cli
```

---

## Context Foundry Installation

**All distributions follow the same steps:**

```bash
# 1. Navigate to your projects directory
cd ~/homelab  # or wherever you keep projects

# 2. Clone Context Foundry
git clone https://github.com/context-foundry/context-foundry.git
cd context-foundry

# 3. Create virtual environment with Python 3.10+
python3 -m venv venv
# or if you have multiple Python versions:
python3.10 -m venv venv

# 4. ⚠️ CRITICAL: Activate virtual environment
source venv/bin/activate

# 5. ✅ VERIFY: Check for (venv) in prompt
# Your prompt should look like:
# (venv) you@hostname:~/homelab/context-foundry$

# 6. Install MCP server dependencies
pip install -r requirements-mcp.txt

# 7. Verify installation
python -c "from fastmcp import FastMCP; print('✅ MCP dependencies installed!')"

# If you see ImportError here, venv wasn't activated in step 4!
```

---

## Claude Code MCP Configuration

### Option 1: Project-Scoped (Recommended for Teams)

```bash
# Must be in the context-foundry directory
cd ~/homelab/context-foundry

# Add MCP server with project scope
claude mcp add --transport stdio context-foundry -s project -- $(pwd)/venv/bin/python $(pwd)/tools/mcp_server.py

# This creates .mcp.json in the project directory
cat .mcp.json
```

**Pros:**
- Shareable with team via git
- Different settings per project
- Portable across machines

**Cons:**
- Only works when running `claude` from this directory

---

### Option 2: Global (Recommended for Individual Use)

```bash
# Works from any directory
claude mcp add --scope user --transport stdio context-foundry -- /home/yourusername/homelab/context-foundry/venv/bin/python /home/yourusername/homelab/context-foundry/tools/mcp_server.py

# Replace /home/yourusername/homelab/context-foundry with your actual path
```

**Pros:**
- Available from any directory
- Appears in `claude mcp list`
- No per-project configuration needed

**Cons:**
- Absolute paths (breaks if you move Context Foundry)

---

## GitHub Authentication

**Required for automatic GitHub deployment.**

```bash
# Start authentication flow
gh auth login

# Interactive prompts:
# 1. What account? → GitHub.com
# 2. Protocol? → HTTPS (recommended)
# 3. How? → Login with a web browser (easiest)
# 4. Copy the 8-digit code shown
# 5. Press Enter to open browser
# 6. Paste code in browser and authorize

# Verify authentication
gh auth status
# Should show: ✓ Logged in to github.com account yourusername
```

**Optional: Use SSH instead of HTTPS:**
```bash
# Generate SSH key if you don't have one
ssh-keygen -t ed25519 -C "your.email@example.com"

# Add to ssh-agent
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519

# Add public key to GitHub
gh auth login
# Choose: SSH protocol
# Choose: Upload SSH public key
```

---

## Git Configuration

**Required for commits to work properly:**

```bash
# Set your name
git config --global user.name "Your Name"

# Set your email
git config --global user.email "your.email@example.com"

# Verify
git config --list | grep user
```

---

## Verification

**Run this verification checklist:**

```bash
# 1. Python version
python3 --version
# ✅ Should be 3.10 or higher

# 2. Virtual environment
cd ~/homelab/context-foundry
source venv/bin/activate
echo $VIRTUAL_ENV
# ✅ Should show path ending in /venv

# 3. MCP dependencies
python -c "import fastmcp; print('✅ OK')"
# ✅ Should print OK

# 4. GitHub CLI
gh --version
# ✅ Should show version number

# 5. GitHub authentication
gh auth status
# ✅ Should show logged in status

# 6. Git configuration
git config user.name && git config user.email
# ✅ Should show your name and email

# 7. MCP configuration
cat .mcp.json
# ✅ Should show MCP server config

# 8. Claude Code
claude --version
# ✅ Should show Claude Code version
```

If all checks pass, you're ready to use Context Foundry!

---

## Common Linux-Specific Issues

### Issue: externally-managed-environment

**Error:**
```
error: externally-managed-environment

× This environment is externally managed
╰─> To install Python packages system-wide, try apt install
    python3-xyz, where xyz is the package you are trying to
    install.
```

**Cause:**
Debian/Ubuntu 23.04+ prevent pip installs to system Python.

**Solution:**
Always use virtual environments (which you should be doing anyway!):
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-mcp.txt
```

**DO NOT** use `--break-system-packages` flag - that's dangerous!

---

### Issue: Permission Denied When Installing

**Error:**
```
PermissionError: [Errno 13] Permission denied
```

**Cause:**
Trying to install without venv OR venv not activated.

**Solution:**
```bash
# Never use sudo pip!
# Instead, use virtual environment:
cd ~/homelab/context-foundry
source venv/bin/activate  # ← MUST activate first!
pip install -r requirements-mcp.txt
```

---

### Issue: Python 3.10 Not Found

**On Ubuntu 20.04 or older:**
```bash
# Add deadsnakes PPA
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt update
sudo apt install python3.10 python3.10-venv

# Use Python 3.10 explicitly
python3.10 -m venv venv
```

**On Debian:**
```bash
# Build from source or use pyenv
curl https://pyenv.run | bash

# Add to ~/.bashrc:
export PATH="$HOME/.pyenv/bin:$PATH"
eval "$(pyenv init -)"

# Install Python 3.10
pyenv install 3.10.13
pyenv global 3.10.13
```

---

### Issue: gh Command Not Found After Installation

**Cause:**
GitHub CLI package installed but not in PATH yet.

**Solution:**
```bash
# Reload shell
source ~/.bashrc
# or
exec bash

# Verify
which gh
gh --version
```

---

### Issue: Claude Code Not in PATH

**Symptoms:**
```
claude: command not found
```

**Solution:**
```bash
# Find where claude-code is installed
# Common locations:
ls ~/.local/bin/claude
ls /usr/local/bin/claude

# Add to PATH in ~/.bashrc
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# Verify
which claude
claude --version
```

---

## Performance Tips for Linux

### 1. Use SSD for Project Directory

```bash
# Bad (slow): /var/tmp, network drives
# Good (fast): ~/projects, ~/homelab on SSD
```

### 2. Increase inotify Limits (For Large Projects)

```bash
# Check current limits
cat /proc/sys/fs/inotify/max_user_watches

# Increase if needed
echo fs.inotify.max_user_watches=524288 | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

### 3. Use Parallel Builds

Context Foundry automatically uses parallel builds. For best performance:
- CPU: 4+ cores recommended
- RAM: 8GB+ recommended
- SSD: Strongly recommended

---

## Security Best Practices

### 1. API Keys and Secrets

**Never commit to git:**
```bash
# Always in .gitignore
echo ".env" >> .gitignore
echo "*.key" >> .gitignore
```

**Use environment variables:**
```bash
# In ~/.bashrc or ~/.zshrc
export ANTHROPIC_API_KEY="your-key-here"
export OPENWEATHERMAP_API_KEY="your-key-here"
```

### 2. GitHub SSH Keys

**Use SSH key with passphrase:**
```bash
ssh-keygen -t ed25519 -C "your.email@example.com"
# When prompted, enter a strong passphrase

# Add to ssh-agent
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_ed25519
```

### 3. File Permissions

**Protect private keys:**
```bash
chmod 600 ~/.ssh/id_ed25519
chmod 644 ~/.ssh/id_ed25519.pub
```

---

## Next Steps

After successful setup:

1. **Test the installation:**
   ```bash
   claude
   ```
   Then say:
   ```
   Build a simple hello world app to test Context Foundry.
   ```

2. **Read the user guide:** [USER_GUIDE.md](../USER_GUIDE.md)

3. **Try building something real:** [QUICKSTART.md](../QUICKSTART.md)

4. **Explore examples:** Check `.context-foundry/` in completed builds

---

## Getting Help

**If you encounter issues:**

1. Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
2. Run the verification checklist above
3. Check GitHub Issues: https://github.com/context-foundry/context-foundry/issues
4. Ask in Discussions: https://github.com/context-foundry/context-foundry/discussions

---

*Last updated: 2025-10-26*
*Tested on: Ubuntu 22.04 LTS, Fedora 39, Arch Linux*
