# Sandbox Architecture for Evolution System
**"Simplicity is the ultimate sophistication" - Leonardo da Vinci**

**Date:** 2025-11-09
**Problem:** Evolution System modifies production code, breaking Context Foundry
**Solution:** Isolated sandbox environment with one-way flow

---

## 🎯 THE PROBLEM

```
Current Flow (DANGEROUS):
┌─────────────────────────────────────────┐
│  Context Foundry Production Repo       │
│  /Users/name/homelab/context-foundry   │
│                                         │
│  ┌──────────────────────────────────┐  │
│  │  Evolution System (daemon)       │  │
│  │  - Finds GitHub issues          │  │
│  │  - Creates fixes                │  │
│  │  - Modifies files IN PLACE ❌   │  │
│  │  - Creates PRs with changes      │  │
│  └──────────────────────────────────┘  │
│                                         │
│  Result: Production code gets broken!  │
└─────────────────────────────────────────┘
```

**Root Cause (Found in `tools/evolution/modes/self_improvement.py:524`):**
```python
result_json = _autonomous_build_and_deploy_impl(
    working_directory=str(cf_root),  # ❌ WORKS IN PRODUCTION!
    existing_repo=str(cf_root),      # ❌ MODIFIES PRODUCTION!
    mode="existing_repo",
)
```

---

## ✅ THE SOLUTION: ONE-WAY FLOW

```
New Flow (SAFE):
┌─────────────────────────────────────────────────────────────────┐
│  PRODUCTION (Protected, Read-Only)                              │
│  /Users/name/homelab/context-foundry                            │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Evolution Daemon (Observer Only)                        │  │
│  │  1. Monitors GitHub issues ✅                            │  │
│  │  2. Creates sandbox ✅                                   │  │
│  │  3. NO direct file modifications ✅                      │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                           │
                           │ Clone
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  SANDBOX (Isolated, Disposable)                                 │
│  /tmp/cf-sandboxes/sandbox_{task_id}_{timestamp}/               │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Evolution System (Full Control)                         │  │
│  │  1. Works in sandbox directory ✅                        │  │
│  │  2. Makes changes freely ✅                              │  │
│  │  3. Runs tests ✅                                        │  │
│  │  4. Creates PR from sandbox ✅                           │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  If task fails: DELETE sandbox, no harm done ✅                 │
└─────────────────────────────────────────────────────────────────┘
                           │
                           │ PR Created
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│  GITHUB (Human Review)                                          │
│  Pull Request with changes from sandbox                         │
│                                                                  │
│  Human reviews, approves, merges → Safe! ✅                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🏗️ ARCHITECTURE PRINCIPLES

### 1. **Immutable Production**
Production Context Foundry code is NEVER modified directly by Evolution System.
- **Read:** ✅ Can read production code for analysis
- **Write:** ❌ Cannot write to production
- **Execute:** ✅ Can run in production (daemon only)

### 2. **Ephemeral Sandboxes**
Every task gets a fresh, isolated sandbox.
- **Created:** On task start
- **Used:** For all file modifications
- **Destroyed:** On task completion (success or failure)
- **Lifetime:** Hours, not days

### 3. **One-Way Flow**
Changes only flow in one direction: Sandbox → PR → Review → Production
```
Sandbox → GitHub PR → Human Review → Production
(Never: Production → Sandbox)
```

### 4. **Fail-Safe Default**
If anything goes wrong, production remains untouched.
- Sandbox crashes? → Delete sandbox, production safe ✅
- Tests fail? → Delete sandbox, production safe ✅
- PR rejected? → Delete sandbox, production safe ✅

### 5. **Human in the Loop**
Every change requires human approval via PR review.
- No direct commits to main ✅
- All PRs reviewed before merge ✅
- Evolution System can't bypass review ✅

---

## 📐 TECHNICAL DESIGN

### Component 1: Sandbox Manager (EXISTS ✅)
**Location:** `tools/evolution/sandboxes.py`
**Status:** IMPLEMENTED but NOT INTEGRATED

**What it does:**
```python
manager = SandboxManager()
sandbox_path = manager.create_sandbox(
    repo_url="https://github.com/context-foundry/context-foundry.git",
    task_id="7b52735b"
)
# Returns: /tmp/cf-sandboxes/sandbox_7b52735b_20251109_160000/
```

**Features:**
- ✅ Creates isolated clone in `/tmp`
- ✅ Tracks active sandboxes
- ✅ Auto-cleanup (old sandboxes after 24h)
- ✅ Disk usage monitoring

**Missing:** Integration with self-improvement mode!

---

### Component 2: Self-Improvement Mode (NEEDS FIX ❌)
**Location:** `tools/evolution/modes/self_improvement.py`
**Status:** WORKS IN PRODUCTION (DANGEROUS!)

**Current Code (in `_delegate_to_context_foundry` method):**
```python
# ❌ PROBLEM: Uses production directory
result_json = _autonomous_build_and_deploy_impl(
    working_directory=str(cf_root),  # Production!
    existing_repo=str(cf_root),      # Production!
    mode="existing_repo",
)
```

**Fixed Code (Simple 3-line change):**
```python
# ✅ SOLUTION: Create and use sandbox
from ..sandboxes import SandboxManager

manager = SandboxManager()
sandbox_path = manager.create_sandbox(
    repo_url="https://github.com/context-foundry/context-foundry.git",
    task_id=task.id
)

result_json = _autonomous_build_and_deploy_impl(
    working_directory=str(sandbox_path),  # Sandbox!
    existing_repo=str(sandbox_path),      # Sandbox!
    mode="existing_repo",
)

# Cleanup sandbox after PR created (or on failure)
manager.cleanup_sandbox(task.id)
```

**That's it! 3 lines added, 0 lines changed.**

---

### Component 3: Safety Guards (NEW 🆕)
**Location:** `tools/evolution/safety.py` (to be created)
**Purpose:** Prevent accidental production modifications

**Guard #1: Production Write Lock**
```python
def is_production_directory(path: Path) -> bool:
    """Check if path is the production Context Foundry directory"""
    cf_production = Path.home() / "homelab" / "context-foundry"
    return path.resolve() == cf_production.resolve()

def prevent_production_write(path: Path):
    """Raise error if attempting to write to production"""
    if is_production_directory(path):
        raise PermissionError(
            "❌ SAFETY: Cannot modify production Context Foundry directory!\n"
            "   Use sandbox environment instead.\n"
            f"   Production: {path}\n"
            "   Create sandbox with: SandboxManager().create_sandbox()"
        )
```

**Guard #2: Sandbox Verification**
```python
def verify_sandbox_environment(path: Path) -> bool:
    """Verify we're working in a sandbox, not production"""
    # Sandbox must be in /tmp/cf-sandboxes/
    expected_parent = Path("/tmp/cf-sandboxes")

    try:
        path.relative_to(expected_parent)
        return True  # Safe: inside sandbox
    except ValueError:
        return False  # Unsafe: outside sandbox
```

**Guard #3: Environment Variable**
```python
import os

def set_sandbox_mode():
    """Mark current process as working in sandbox"""
    os.environ["CF_SANDBOX_MODE"] = "1"
    os.environ["CF_SANDBOX_PATH"] = str(sandbox_path)

def is_sandbox_mode() -> bool:
    """Check if running in sandbox mode"""
    return os.getenv("CF_SANDBOX_MODE") == "1"
```

---

## 🔄 COMPLETE WORKFLOW

### Step-by-Step Execution

#### **1. Issue Discovery (Daemon)**
```python
# daemon.py
issues = fetch_github_issues(label="approved")
if issues:
    issue = issues[0]
    task_id = create_task("implement_github_issue", {
        "github_issue": issue.number,
        "description": issue.title,
        "details": issue.body
    })
```

#### **2. Sandbox Creation (Self-Improvement Mode)**
```python
# self_improvement.py
def execute_task(self, task) -> TaskResult:
    # Create isolated sandbox
    manager = SandboxManager()
    sandbox_path = manager.create_sandbox(
        repo_url="https://github.com/context-foundry/context-foundry.git",
        task_id=task.id
    )

    # Set environment for safety
    os.environ["CF_SANDBOX_MODE"] = "1"
    os.environ["CF_SANDBOX_PATH"] = str(sandbox_path)

    try:
        # Work happens in sandbox
        result = self._delegate_to_context_foundry_in_sandbox(
            prompt,
            branch_name,
            sandbox_path
        )

        return result
    finally:
        # Always cleanup
        manager.cleanup_sandbox(task.id)
```

#### **3. Work in Sandbox (MCP Server)**
```python
# mcp_server.py - autonomous_build_and_deploy()
result = _autonomous_build_and_deploy_impl(
    task=prompt,
    working_directory=str(sandbox_path),  # SANDBOX!
    github_repo_name="context-foundry/context-foundry",
    existing_repo=str(sandbox_path),       # SANDBOX!
    mode="existing_repo",
    enable_test_loop=True
)

# All Scout, Architect, Builder, Test, Deploy work happens in sandbox
# Files modified: sandbox files ✅
# Files tested: sandbox files ✅
# PR created from: sandbox files ✅
```

#### **4. PR Creation (Git from Sandbox)**
```bash
# From sandbox directory
cd /tmp/cf-sandboxes/sandbox_7b52735b_20251109_160000/

git checkout -b self-improvement/issue-123
git add .
git commit -m "Fix: Implement feature from issue #123"
git push origin self-improvement/issue-123

gh pr create \
  --title "Fix: Implement feature from issue #123" \
  --body "Fixes #123\n\nAutonomous implementation by Evolution System" \
  --base main
```

#### **5. Sandbox Cleanup (Automatic)**
```python
# After PR created (or on error)
manager.cleanup_sandbox(task.id)

# Result: /tmp/cf-sandboxes/sandbox_7b52735b_20251109_160000/ deleted
# Production: /Users/name/homelab/context-foundry/ untouched ✅
```

#### **6. Human Review (GitHub)**
```
Human reviews PR → Approves → Merges to main
(Or rejects → PR closed → No changes to production)
```

#### **7. Loop Continues (Daemon)**
```python
# daemon.py detects PR merged
if pr_merged:
    # Wait complete, queue next task
    next_issue = fetch_next_approved_issue()
    create_task(...)
```

---

## 🛡️ SAFETY MECHANISMS

### Level 1: Path Validation
```python
# Before ANY file write operation
if is_production_directory(target_dir):
    raise PermissionError("Cannot modify production!")
```

### Level 2: Environment Check
```python
# In all Evolution System code
if not is_sandbox_mode():
    raise RuntimeError("Must run in sandbox mode!")
```

### Level 3: Sandbox Verification
```python
# Verify working directory is in /tmp/cf-sandboxes/
if not verify_sandbox_environment(working_dir):
    raise RuntimeError(f"Invalid sandbox: {working_dir}")
```

### Level 4: Git Remote Protection
```python
# Prevent accidental push from production
git_dir = working_dir / ".git"
if git_dir.exists():
    # Check if this is production
    if is_production_directory(working_dir):
        # Ensure we're not on main branch
        if current_branch == "main":
            raise RuntimeError("Cannot work on main in production!")
```

### Level 5: Daemon Pause on Write Attempt
```python
# In daemon main loop
try:
    execute_task(task)
except PermissionError as e:
    if "production" in str(e).lower():
        # CRITICAL: Attempted production write!
        logger.critical("⛔ SAFETY: Attempted production modification!")
        logger.critical("   Pausing daemon for manual intervention")
        pause_daemon()
        send_alert_to_admin()
```

---

## 📊 COMPARISON: BEFORE vs AFTER

### BEFORE (Dangerous)
| Aspect | Status | Risk |
|--------|--------|------|
| **Work Location** | Production (`/Users/name/homelab/context-foundry`) | 🔴 HIGH |
| **File Modifications** | Direct to production files | 🔴 CRITICAL |
| **Test Failures** | Break production code | 🔴 CRITICAL |
| **Bad Changes** | Corrupt production immediately | 🔴 CRITICAL |
| **Rollback** | Manual git revert required | 🔴 HIGH |
| **Parallel Tasks** | Can't run (would conflict) | 🟡 MEDIUM |

### AFTER (Safe)
| Aspect | Status | Risk |
|--------|--------|------|
| **Work Location** | Sandbox (`/tmp/cf-sandboxes/...`) | 🟢 NONE |
| **File Modifications** | Isolated in sandbox | 🟢 NONE |
| **Test Failures** | Delete sandbox, production safe | 🟢 NONE |
| **Bad Changes** | Delete sandbox, production safe | 🟢 NONE |
| **Rollback** | Just delete sandbox | 🟢 NONE |
| **Parallel Tasks** | Can run multiple sandboxes | 🟢 BONUS |

---

## 🚀 IMPLEMENTATION PLAN

### Phase 1: Immediate Fix (15 minutes)
**Goal:** Stop production modifications NOW

```python
# File: tools/evolution/modes/self_improvement.py

# Add at top:
from ..sandboxes import SandboxManager

# Modify _delegate_to_context_foundry() method (around line 486):

def _delegate_to_context_foundry(self, prompt: str, branch_name: str) -> Dict:
    """Delegate task to Context Foundry in SANDBOX"""

    # Create sandbox
    manager = SandboxManager()
    sandbox_path = manager.create_sandbox(
        repo_url="https://github.com/context-foundry/context-foundry.git",
        task_id=self.task.id if hasattr(self, 'task') else "unknown"
    )

    try:
        # Work in sandbox
        result_json = _autonomous_build_and_deploy_impl(
            task=prompt,
            working_directory=str(sandbox_path),  # ✅ SANDBOX
            github_repo_name="context-foundry/context-foundry",
            existing_repo=str(sandbox_path),       # ✅ SANDBOX
            mode="existing_repo",
            enable_test_loop=True,
            max_test_iterations=3,
            timeout_minutes=90.0,
            use_parallel=True,
        )

        result = json.loads(result_json)
        return result

    finally:
        # Cleanup sandbox (success or failure)
        manager.cleanup_sandbox(
            self.task.id if hasattr(self, 'task') else "unknown"
        )
```

**Test:**
```bash
# Trigger self-improvement task
# Verify it creates sandbox in /tmp/cf-sandboxes/
# Verify production directory is untouched
```

---

### Phase 2: Add Safety Guards (30 minutes)
**Goal:** Prevent accidental production writes

Create `tools/evolution/safety.py`:
```python
"""Safety mechanisms for Evolution System"""
from pathlib import Path
import os

def is_production_directory(path: Path) -> bool:
    """Check if path is production Context Foundry"""
    cf_production = Path.home() / "homelab" / "context-foundry"
    try:
        return path.resolve() == cf_production.resolve()
    except:
        return False

def verify_sandbox_environment(path: Path) -> bool:
    """Verify working in sandbox, not production"""
    sandbox_base = Path("/tmp/cf-sandboxes")
    try:
        path.relative_to(sandbox_base)
        return True
    except ValueError:
        return False

def enforce_sandbox_mode(working_dir: Path):
    """Raise error if not in sandbox"""
    if is_production_directory(working_dir):
        raise PermissionError(
            "❌ SAFETY: Cannot modify production!\n"
            f"   Production: {working_dir}\n"
            "   Use SandboxManager to create sandbox"
        )

    if not verify_sandbox_environment(working_dir):
        raise RuntimeError(
            f"❌ SAFETY: Invalid sandbox location!\n"
            f"   Location: {working_dir}\n"
            "   Expected: /tmp/cf-sandboxes/"
        )
```

Add to `self_improvement.py`:
```python
from ..safety import enforce_sandbox_mode

# Before any file operations:
enforce_sandbox_mode(sandbox_path)
```

---

### Phase 3: Monitoring & Alerts (1 hour)
**Goal:** Track sandbox usage and detect issues

Add to `SandboxManager`:
```python
def log_sandbox_activity(self, task_id: str, event: str, data: dict = None):
    """Log all sandbox operations for audit trail"""
    log_file = Path.home() / ".context-foundry" / "evolution" / "sandbox-audit.log"

    entry = {
        "timestamp": datetime.now().isoformat(),
        "task_id": task_id,
        "event": event,  # created, used, cleaned, failed
        "data": data or {}
    }

    with open(log_file, "a") as f:
        f.write(json.dumps(entry) + "\n")
```

Monitor for issues:
```bash
# Check if any sandboxes leaked (not cleaned up)
find /tmp/cf-sandboxes -type d -mtime +1

# Check audit log for failures
grep "failed" ~/.context-foundry/evolution/sandbox-audit.log
```

---

### Phase 4: Testing & Validation (2 hours)
**Goal:** Ensure sandbox system works perfectly

**Test Cases:**
1. ✅ Create sandbox → Verify isolated
2. ✅ Make changes in sandbox → Verify production untouched
3. ✅ Create PR from sandbox → Verify correct
4. ✅ Cleanup sandbox → Verify deleted
5. ✅ Attempt production write → Verify blocked
6. ✅ Run parallel sandboxes → Verify no conflicts
7. ✅ Sandbox failure → Verify production safe

**Validation Script:**
```bash
#!/bin/bash
# test-sandbox-safety.sh

echo "🧪 Testing sandbox safety mechanisms..."

# Test 1: Sandbox creation
python3 -c "
from tools.evolution.sandboxes import SandboxManager
manager = SandboxManager()
path = manager.create_sandbox(
    'https://github.com/context-foundry/context-foundry.git',
    'test-123'
)
print(f'✅ Sandbox created: {path}')
assert '/tmp/cf-sandboxes/' in str(path)
"

# Test 2: Production protection
python3 -c "
from tools.evolution.safety import enforce_sandbox_mode
from pathlib import Path

try:
    enforce_sandbox_mode(Path.home() / 'homelab' / 'context-foundry')
    print('❌ FAIL: Production write not blocked!')
    exit(1)
except PermissionError:
    print('✅ Production protection working')
"

echo "✅ All safety tests passed!"
```

---

## 📈 MONITORING DASHBOARD

### Key Metrics to Track

1. **Sandbox Count**
   - Active sandboxes
   - Peak concurrent sandboxes
   - Average lifetime

2. **Disk Usage**
   - Total sandbox disk usage
   - Largest sandbox
   - Cleanup effectiveness

3. **Safety Events**
   - Production write attempts (should be 0!)
   - Invalid sandbox paths
   - Failed sandbox creations

4. **Performance**
   - Sandbox creation time
   - Cleanup time
   - Task success rate

### Dashboard View (Mission Control)
```
╔══════════════════════════════════════════════════════════╗
║  SANDBOX STATUS                                          ║
╠══════════════════════════════════════════════════════════╣
║  Active Sandboxes:        3                              ║
║  Total Disk Usage:        450 MB                         ║
║  Oldest Sandbox:          2 hours                        ║
║                                                           ║
║  ✅ Production Protected: 0 write attempts               ║
║  ✅ All sandboxes valid                                  ║
║                                                           ║
║  Current Tasks:                                          ║
║   sandbox_7b52735b: Implementing issue #123              ║
║   sandbox_3a91bc44: Fixing TODO in cache.py              ║
║   sandbox_9f21ee77: Adding tests for metrics             ║
╚══════════════════════════════════════════════════════════╝
```

---

## 🎯 SUCCESS CRITERIA

### Must Have (Phase 1)
- [ ] Production directory NEVER modified by Evolution System
- [ ] All autonomous work happens in sandboxes
- [ ] Sandboxes automatically cleaned up
- [ ] PRs created from sandboxes, not production

### Should Have (Phase 2)
- [ ] Safety guards prevent production writes
- [ ] Clear error messages when safety violated
- [ ] Audit log of all sandbox operations
- [ ] Dashboard shows sandbox status

### Nice to Have (Phase 3)
- [ ] Parallel sandbox support (multiple tasks)
- [ ] Sandbox reuse (if task similar)
- [ ] Performance metrics
- [ ] Automated cleanup of leaked sandboxes

---

## 📝 CONFIGURATION

### File: `~/.context-foundry/evolution/sandbox-config.json`
```json
{
  "sandbox_base_dir": "/tmp/cf-sandboxes",
  "max_sandboxes": 10,
  "max_age_hours": 24,
  "max_disk_mb": 5000,
  "auto_cleanup": true,
  "safety_checks": true,
  "allow_production_mode": false,
  "alert_on_production_attempt": true
}
```

---

## ⚠️ ROLLBACK PLAN

If sandbox system causes issues:

### Quick Disable (1 minute)
```python
# File: tools/evolution/modes/self_improvement.py
# Add at top of execute_task():

USE_SANDBOX = False  # Emergency disable

if not USE_SANDBOX:
    # Old behavior (works in production)
    cf_root = Path(__file__).parent.parent.parent.parent
    working_dir = str(cf_root)
else:
    # New sandbox behavior
    manager = SandboxManager()
    sandbox_path = manager.create_sandbox(...)
    working_dir = str(sandbox_path)
```

### Full Rollback
```bash
git revert <commit-hash-of-sandbox-integration>
git push origin main
```

---

## 🔗 RELATED DOCUMENTS

- [tools/evolution/sandboxes.py](tools/evolution/sandboxes.py) - Sandbox manager (exists)
- [tools/evolution/modes/self_improvement.py](tools/evolution/modes/self_improvement.py) - Needs update
- [FULL_DIAGNOSTIC_REPORT.md](FULL_DIAGNOSTIC_REPORT.md) - System analysis

---

## 📚 APPENDIX: DA VINCI'S PRINCIPLES APPLIED

### 1. Simplicity
- One concept: Isolated sandboxes
- One change: Use sandbox_path instead of cf_root
- One safety rule: Never modify production

### 2. Clarity
- Clear separation: Production (read-only) vs Sandbox (read-write)
- Clear flow: Clone → Work → PR → Review → Merge
- Clear error messages: "Cannot modify production!"

### 3. Elegance
- Existing code reused (SandboxManager already written)
- Minimal changes (3 lines of code)
- Natural fit (git clone is already a sandbox concept)

### 4. Robustness
- Fail-safe: If sandbox fails, production untouched
- Multiple safety layers: Path check, env check, verification
- Auto-cleanup: No manual intervention needed

### 5. Beauty
- System protects itself
- Mirrors natural processes (cells have membranes)
- Self-healing without self-harm

---

**"A designer knows he has achieved perfection not when there is nothing left to add, but when there is nothing left to take away."**
— Antoine de Saint-Exupéry

**Implementation: 3 lines of code. Protection: Infinite.**

---

**Next Step:** [Implement Phase 1](#phase-1-immediate-fix-15-minutes) to protect production immediately.
