# Pipeline Safety Controls

This document describes the safety and control mechanisms implemented for the Context Foundry autonomous agent pipeline, as specified in [Issue #181](https://github.com/context-foundry/context-foundry/issues/181).

## Overview

Context Foundry's pipeline now includes comprehensive safety controls that allow operators to:
- Pause and resume builds at any phase
- Require human approval for high-risk operations
- Emergency stop all agent activity
- Audit all phase transitions

All features are **backward compatible** - existing `cfd build` commands work unchanged.

## Implementation Status

| Milestone | Status | Description |
|-----------|--------|-------------|
| M1: Pause/Resume | ✅ Complete | State persistence and resumable builds |
| M2: Selective Phase Execution | ✅ Complete | Phase registry and configuration |
| M3: Safety Mechanisms | ✅ Complete | Preflight, scope guard, audit logging |
| M4: Checkpoints & Rollback | ❌ Not Started | Automatic snapshots and recovery |
| M5: Human Approval Gates | ✅ Complete | Configurable approval for any phase |
| M6: Emergency Stop | ✅ Complete | Global kill switch |

---

## M1: Pause/Resume Foundation

### Files
- `tools/mcp_utils/pipeline_state.py` - Core state management

### Usage

```bash
# Pause after specific phases
cfd build "Create API" --pause-after Scout,Architect

# Resume a paused build
cfd resume <job-id>

# Check resumable builds
cfd list --resumable
```

### Pipeline States
- `INITIALIZING` - Build starting
- `RUNNING` - Phase in progress
- `PAUSED` - Waiting to resume
- `WAITING_APPROVAL` - Blocked on human approval
- `COMPLETED` - All phases done
- `FAILED` - Build failed
- `CANCELLED` - User cancelled
- `EMERGENCY_STOPPED` - Halted by emergency stop

---

## M3: Safety Mechanisms

### Preflight Validation

Before each phase, preflight checks verify:
- Working directory exists and is writable
- Required files are present
- No scope violations detected

```python
# In autonomous_build.py
run_phase_preflight("Builder")  # Validates before Builder phase
```

### Scope Guard

Prevents agents from modifying files outside the project directory:

```python
from tools.mcp_utils.scope_guard import is_path_in_scope

if not is_path_in_scope(file_path, working_directory):
    raise ScopeViolationError(f"Path {file_path} is outside project scope")
```

### Audit Logging

All phase transitions are logged for compliance and debugging:

```python
from tools.mcp_utils.audit import audit_phase_started, audit_phase_completed

audit_phase_started("Builder", working_directory)
# ... phase execution ...
audit_phase_completed("Builder", working_directory)
```

Audit logs are stored in `~/.context-foundry/audit/`.

---

## M5: Human Approval Gates

### Files
- `tools/mcp_utils/approval_gates.py` - Core approval management
- `tests/test_approval_gates.py` - 25 test cases

### Configuration

By default, only the `Deploy` phase requires approval. Configure additional phases:

```python
task_config = {
    "task": "Build my app",
    "working_directory": "/path/to/project",
    "require_approval_phases": ["Builder", "Deploy"],  # Require approval for both
}
```

Or skip all approvals:

```python
task_config = {
    "skip_approval": True,  # No approvals required
}
```

### CLI Commands

```bash
# List pending approvals
cfd pending-approvals

# List all approvals (including resolved)
cfd pending-approvals --all

# Approve a request
cfd approve <request-id>
cfd approve abc12345

# Deny a request
cfd approve <request-id> --deny
cfd approve abc12345 --deny --reason "Not ready for production"
```

### Sample Output

```
Pending Approval Requests (1 shown):
======================================================================

⏳ [DEPLOY] PENDING
   ID: abc12345
   Project: my-api (/Users/dev/projects/my-api)
   Task: Build REST API with JWT authentication...
   ⚠️  Risk: Will push code to GitHub and create public repository
   Progress: Phases completed: Scout, Architect, Builder, Test
   Requested: 2025-01-15T10:30:00
   Expires: 23h 45m remaining
   → Approve: cfd approve abc12345
   → Deny:    cfd approve abc12345 --deny

======================================================================

📋 1 request(s) awaiting approval
```

### Approval Request Lifecycle

1. **Created** - When phase requiring approval is reached
2. **Pending** - Waiting for human response
3. **Approved** - Human approved, phase proceeds
4. **Denied** - Human denied, phase skipped (build continues)
5. **Expired** - No response within expiry window (default 24h), re-requested on resume

### Expiry Enforcement

Approval requests expire after 24 hours by default. When resuming a build with an expired approval:
- The expired request is detected
- A new approval request is created automatically
- Message: "⏰ Previous approval request expired, requesting new approval..."

---

## M6: Emergency Stop

### Files
- `tools/mcp_utils/emergency_stop.py` - Kill switch implementation

### Usage

```bash
# Activate emergency stop (halts ALL running agents)
cfd emergency-stop
cfd emergency-stop --reason "Detected runaway process"

# Check status
cfd emergency-status

# Resume operations
cfd emergency-resume
```

### How It Works

1. Creates `~/.context-foundry/EMERGENCY_STOP` file
2. All agents check for this file before each phase
3. If file exists, agents halt immediately with `EMERGENCY_STOPPED` state
4. Removing the file allows agents to resume

### Integration

Emergency stop is checked:
- Before every phase starts
- At the start of each test iteration
- Before any phase-level operation

```python
from tools.mcp_utils.emergency_stop import is_emergency_stop_active

if is_emergency_stop_active():
    return {"status": "emergency_stopped", "message": "..."}
```

---

## Remaining Work

### M4: Checkpoints & Rollback (Not Implemented)

This milestone would add:
- Automatic filesystem snapshots before each phase
- Rollback capability to restore previous state
- Checkpoint management CLI (`cfd checkpoint list`, `cfd rollback <checkpoint>`)

### Known Gaps

1. **Scope Guard Wiring**: The scope guard module exists but is not yet wired into all file operations in the pipeline.

2. **Mid-Phase Blocking**: Approval gates and emergency stop check at phase boundaries, not during phase execution. A long-running phase will complete before the stop takes effect.

---

## Testing

Run the approval gates test suite:

```bash
pytest tests/test_approval_gates.py -v
```

All 25 tests cover:
- ApprovalRequest creation and lifecycle
- ApprovalManager CRUD operations
- ApprovalGateConfig configuration
- Helper functions (approve_phase, deny_phase, etc.)
- Pipeline state integration

---

## Related Documentation

- [CF Daemon Architecture](CF_DAEMON_ARCHITECTURE.md)
- [Build Modes](BUILD_MODES.md)
- [Phase Spawning Implementation](PHASE_SPAWNING_IMPLEMENTATION_SUMMARY.md)
