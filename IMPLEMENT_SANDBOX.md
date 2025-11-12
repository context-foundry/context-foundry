# Sandbox Implementation Guide
**Priority:** 🔴 CRITICAL - Prevents production code corruption
**Time Required:** 15 minutes
**Difficulty:** Easy (3 lines of code)

---

## ⚡ QUICK START (Copy-Paste)

### Step 1: Test Safety Module (2 minutes)

```bash
# Verify safety module works
python3 tools/evolution/safety.py

# Expected output:
# ✅ PASS: Production protection working
# ✅ PASS: Invalid sandbox detected
# ✅ PASS: Valid sandbox accepted
# ✅ All safety tests passed!
```

---

### Step 2: Update Self-Improvement Mode (5 minutes)

**File:** `tools/evolution/modes/self_improvement.py`

**Find the `_delegate_to_context_foundry` method:**
```python
def _delegate_to_context_foundry(self, prompt: str, branch_name: str) -> Dict:
    """Delegate task to Context Foundry MCP server directly"""
    try:
        available, reason = self._mcp_status()
        if not available:
            return {"success": False, "error": f"MCP unavailable: {reason}"}

        import json
        from tools.mcp_server import _autonomous_build_and_deploy_impl

        cf_root = Path(__file__).parent.parent.parent.parent  # ❌ PRODUCTION

        print("🤖 Calling Context Foundry MCP autonomous_build_and_deploy()...")

        result_json = _autonomous_build_and_deploy_impl(
            task=prompt,
            working_directory=str(cf_root),  # ❌ MODIFIES PRODUCTION!
            existing_repo=str(cf_root),      # ❌ MODIFIES PRODUCTION!
            mode="existing_repo",
            ...
        )
```

**Replace with:**
```python
def _delegate_to_context_foundry(self, prompt: str, branch_name: str) -> Dict:
    """Delegate task to Context Foundry in ISOLATED SANDBOX"""
    try:
        available, reason = self._mcp_status()
        if not available:
            return {"success": False, "error": f"MCP unavailable: {reason}"}

        import json
        from tools.mcp_server import _autonomous_build_and_deploy_impl
        from ..sandboxes import SandboxManager  # ✅ NEW
        from ..safety import enforce_sandbox_mode, set_sandbox_mode  # ✅ NEW

        # Get task ID (use from context or generate)
        task_id = getattr(self, 'current_task_id', 'unknown')

        # Create isolated sandbox ✅
        print("🏗️  Creating isolated sandbox...")
        manager = SandboxManager()
        sandbox_path = manager.create_sandbox(
            repo_url="https://github.com/context-foundry/context-foundry.git",
            task_id=task_id
        )

        # Verify sandbox safety ✅
        enforce_sandbox_mode(sandbox_path, "autonomous build")
        set_sandbox_mode(sandbox_path)

        print(f"✅ Sandbox created: {sandbox_path}")
        print("🤖 Calling Context Foundry MCP autonomous_build_and_deploy()...")

        try:
            result_json = _autonomous_build_and_deploy_impl(
                task=prompt,
                working_directory=str(sandbox_path),  # ✅ SANDBOX!
                existing_repo=str(sandbox_path),      # ✅ SANDBOX!
                mode="existing_repo",
                github_repo_name="context-foundry/context-foundry",
                enable_test_loop=True,
                max_test_iterations=3,
                timeout_minutes=90.0,
                use_parallel=True,
            )

            result = json.loads(result_json)
            return result

        finally:
            # Always cleanup sandbox ✅
            print(f"🧹 Cleaning up sandbox: {sandbox_path}")
            manager.cleanup_sandbox(task_id)
```

---

### Step 3: Pass Task ID to Method (3 minutes)

**File:** `tools/evolution/modes/self_improvement.py`

**Find the `execute_task` method:**
```python
def execute_task(self, task) -> TaskResult:
    """Execute improvement task via CF delegation"""
    try:
        params = task.params
        action = params.get("action", "")

        # Build prompt...

        # Delegate to Context Foundry via Claude CLI...
        result = self._delegate_to_context_foundry(prompt, branch_name)
```

**Add ONE line to set task ID:**
```python
def execute_task(self, task) -> TaskResult:
    """Execute improvement task via CF delegation"""
    try:
        self.current_task_id = task.id  # ✅ ADD THIS LINE

        params = task.params
        action = params.get("action", "")

        # Build prompt...

        # Delegate to Context Foundry via Claude CLI...
        result = self._delegate_to_context_foundry(prompt, branch_name)
```

---

### Step 4: Test the Implementation (5 minutes)

```bash
# 1. Restart the daemon
launchctl stop dev.contextfoundry.evolution
launchctl start dev.contextfoundry.evolution

# 2. Watch the logs
tail -f ~/.context-foundry/evolution/logs/daemon.log

# 3. Trigger a task (create approved GitHub issue or wait for automatic)

# 4. Verify sandbox is used:
#    - Look for "Creating isolated sandbox..." in logs
#    - Check /tmp/cf-sandboxes/ for sandbox directory
#    - Verify production directory is untouched
#    - PR created from sandbox

# 5. Check sandbox cleanup
ls -la /tmp/cf-sandboxes/
# Should be empty or contain only active tasks
```

---

## ✅ VERIFICATION CHECKLIST

After implementation, verify:

- [ ] Safety module tests pass (`python3 tools/evolution/safety.py`)
- [ ] Self-improvement mode imports sandbox modules
- [ ] `_delegate_to_context_foundry` creates sandbox
- [ ] Working directory is sandbox, not production
- [ ] Sandbox is cleaned up after task
- [ ] Production directory is never modified
- [ ] PRs are created from sandbox
- [ ] Daemon logs show sandbox creation/cleanup

---

## 🎯 EXPECTED BEHAVIOR

### Before (Dangerous):
```
Evolution System starts task
  ↓
Works in /Users/name/homelab/context-foundry  ❌
  ↓
Modifies production files directly  ❌
  ↓
Creates PR with changes
  ↓
If changes are bad → Production broken!  🔴
```

### After (Safe):
```
Evolution System starts task
  ↓
Creates sandbox in /tmp/cf-sandboxes/sandbox_xxx/  ✅
  ↓
Works in sandbox (production untouched)  ✅
  ↓
Creates PR from sandbox  ✅
  ↓
Cleans up sandbox  ✅
  ↓
If changes are bad → Just delete sandbox, production safe!  🟢
```

---

## 🚨 ROLLBACK (If Needed)

If sandbox causes issues, quick disable:

```python
# Add at top of _delegate_to_context_foundry() method:

USE_SANDBOX = False  # Set to False to disable

if USE_SANDBOX:
    # New sandbox code
    manager = SandboxManager()
    sandbox_path = manager.create_sandbox(...)
    working_dir = str(sandbox_path)
else:
    # Old behavior (works in production)
    cf_root = Path(__file__).parent.parent.parent.parent
    working_dir = str(cf_root)
```

Then restart daemon.

---

## 📊 MONITORING

### Check Sandbox Activity
```bash
# List active sandboxes
ls -lh /tmp/cf-sandboxes/

# Check sandbox disk usage
du -sh /tmp/cf-sandboxes/*

# Monitor daemon logs for sandbox operations
tail -f ~/.context-foundry/evolution/logs/daemon.log | grep -i sandbox
```

### Audit Safety
```bash
# Check for any production write attempts (should be 0!)
grep "SAFETY VIOLATION" ~/.context-foundry/evolution/logs/daemon.log

# If any violations found:
# 1. STOP the daemon immediately
# 2. Review the logs
# 3. Fix the issue before restarting
```

---

## 🎓 UNDERSTANDING THE FIX

### What Changed?
**3 lines of code added, 2 lines changed:**

1. `from ..sandboxes import SandboxManager` - Import sandbox manager
2. `manager = SandboxManager()` - Create manager
3. `sandbox_path = manager.create_sandbox(...)` - Create sandbox
4. `working_directory=str(sandbox_path)` - Changed from `cf_root`
5. `manager.cleanup_sandbox(task_id)` - Cleanup after

### Why It Works?
- **Isolation:** Each task gets a fresh clone in `/tmp`
- **Safety:** Production directory is never touched
- **Cleanup:** Temporary sandboxes are deleted automatically
- **Simplicity:** Uses standard git clone (nothing fancy)

### Cost?
- **Disk:** ~200-300 MB per sandbox (temporary)
- **Time:** ~30 seconds to clone (one-time per task)
- **CPU:** Minimal (just git clone)

### Benefit?
- **Production:** 100% safe from corruption
- **Confidence:** Can let Evolution run unattended
- **Debugging:** Easy to inspect sandbox if task fails
- **Parallel:** Can run multiple tasks in separate sandboxes

---

## 🔗 RELATED FILES

- `tools/evolution/sandboxes.py` - Sandbox manager (already exists)
- `tools/evolution/safety.py` - Safety checks (just created)
- `tools/evolution/modes/self_improvement.py` - Mode to update
- `SANDBOX_ARCHITECTURE.md` - Full architecture document

---

**Ready to implement?** Follow Steps 1-4 above!

**Questions?** Check `SANDBOX_ARCHITECTURE.md` for details.

**Issues?** Use rollback procedure above.
