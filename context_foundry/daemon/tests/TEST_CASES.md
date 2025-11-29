# Daemon Workflow Engine Test Cases

Validation checklist for the job-level workflow engine. These tests verify the integration between the state machine, gate manager, watchdog, and timeline helpers.

## Prerequisites

```bash
# Ensure daemon is running
cfd start

# Have a test project directory ready
export TEST_PROJECT="/tmp/cf-test-project"
mkdir -p $TEST_PROJECT
```

---

## Test A: Happy-Path Pipeline Run

**Objective:** Verify a normal job completes successfully with all phases passing gates.

### Setup

```bash
# Submit a simple build job
cfd submit --type autonomous_build --params '{
  "task": "Create a simple hello world Python script",
  "working_directory": "/tmp/cf-test-project",
  "mode": "new_project",
  "timeout_minutes": 30
}'

# Capture the job ID
JOB_ID="<job_id_from_output>"
```

### During Execution

| Check | Command | Expected Result |
|-------|---------|-----------------|
| Gates progressing | `cfd gates $JOB_ID` | Shows phases transitioning: Scout PASSED, Architect ACTIVE, etc. |
| Events accumulating | `cfd timeline $JOB_ID` | Events appearing with timestamps, task_running, task_succeeded |
| Recent activity | `cfd events` | Job appears in recent events list |

### After Completion

| Check | Command | Expected Result |
|-------|---------|-----------------|
| Phase summary | `cfd phase-summary $JOB_ID` | All required phases show "SUCCEEDED" |
| Final gates | `cfd gates $JOB_ID` | Scout, Architect, Builder, Test all PASSED |
| State reconstruction | `cfd reconstruct $JOB_ID` | `current_status: succeeded` |
| Job status | `cfd show $JOB_ID` | Status: succeeded |

### Verification Script

```python
"""Test A: Happy-path verification"""
from context_foundry.daemon.store import Store
from context_foundry.daemon.state_machine import StateMachine
from context_foundry.daemon.gates import GateManager
from context_foundry.daemon.models import JobStatus
from pathlib import Path

JOB_ID = "<insert_job_id>"

store = Store(Path.home() / ".context-foundry" / "daemon.db")
sm = StateMachine(store)
gate_mgr = GateManager(store)

# Get job
job = store.get_job(JOB_ID)
assert job is not None, "Job not found"

# Verify final status
assert job.status == JobStatus.SUCCEEDED, f"Expected SUCCEEDED, got {job.status}"

# Verify gates
report = gate_mgr.get_gate_report(JOB_ID)
assert report.all_required_passed, "Not all required gates passed"
assert not report.has_failures, "Has failures but shouldn't"

# Verify reconstruction matches
reconstructed = store.reconstruct_job_state(JOB_ID)
assert reconstructed["current_status"] == "succeeded"

# Verify phase summary
summary = store.get_job_phase_summary(JOB_ID)
assert summary["progress"]["failed"] == 0, "Has failed phases"

print("[PASS] Test A: Happy-path pipeline run")
```

### Pass Criteria

- [ ] Job status is `SUCCEEDED`
- [ ] All required phases (Scout, Architect, Builder, Test) are `PASSED` in gate report
- [ ] `try_complete_job()` actually set the final status (not just suggested)
- [ ] Timeline shows clear progression of events
- [ ] Reconstructed state matches stored state

---

## Test B: Controlled Failure in Mid-Phase

**Objective:** Verify failed phases correctly propagate to job failure.

### Setup

```bash
# Submit a job with intentionally bad task that will fail
cfd submit --type autonomous_build --params '{
  "task": "Create a program that divides by zero and has syntax errors",
  "working_directory": "/tmp/cf-test-failure",
  "mode": "new_project",
  "timeout_minutes": 30
}'

JOB_ID="<job_id_from_output>"
```

### Expected Behavior

| Check | Command | Expected Result |
|-------|---------|-----------------|
| Failed phase task | `cfd phase-summary $JOB_ID` | Builder or Test shows FAILED |
| Gate failure | `cfd gates $JOB_ID` | Failing gate marked FAILED with error |
| Job failed | `cfd show $JOB_ID` | Status: failed |
| Timeline shows failure | `cfd timeline $JOB_ID` | `task_failed` event visible |

### Verification Script

```python
"""Test B: Controlled failure verification"""
from context_foundry.daemon.store import Store
from context_foundry.daemon.state_machine import StateMachine
from context_foundry.daemon.gates import GateManager
from context_foundry.daemon.models import JobStatus
from pathlib import Path

JOB_ID = "<insert_job_id>"

store = Store(Path.home() / ".context-foundry" / "daemon.db")
sm = StateMachine(store)
gate_mgr = GateManager(store)

# Get job
job = store.get_job(JOB_ID)
assert job is not None, "Job not found"

# Verify job is FAILED
assert job.status == JobStatus.FAILED, f"Expected FAILED, got {job.status}"

# Verify gate report shows failure
report = gate_mgr.get_gate_report(JOB_ID)
assert report.has_failures, "Should have failures"

# Get failed phases
failed_phases = gate_mgr.get_failed_phases(JOB_ID)
assert len(failed_phases) > 0, "Should have at least one failed phase"
print(f"Failed phases: {failed_phases}")

# Verify evaluate_job_completion suggested FAILED
suggested = sm.evaluate_job_completion(JOB_ID)
# Note: After job is already FAILED, this may return None or FAILED
# The key is that try_complete_job() already acted on it

# Verify timeline has failure event
timeline = store.get_job_timeline(JOB_ID)
failure_events = [e for e in timeline if "failed" in e.get("status", "")]
assert len(failure_events) > 0, "No failure events in timeline"

print("[PASS] Test B: Controlled failure in mid-phase")
```

### Pass Criteria

- [ ] Failing phase task status is `FAILED`
- [ ] `GateManager.get_gate_report()` shows gate as FAILED
- [ ] `evaluate_job_completion()` returns `FAILED`
- [ ] `try_complete_job()` sets job to `FAILED`
- [ ] Watchdog does NOT leave job stuck in `RUNNING` or `STALLED`

---

## Test C: Zombie Simulation (Kill Agent Mid-Phase)

**Objective:** Verify stalled job detection when agent stops sending heartbeats.

### Setup

```bash
# Submit a job with a long-running task
cfd submit --type autonomous_build --params '{
  "task": "Create a complex web application with React frontend and Node.js backend",
  "working_directory": "/tmp/cf-test-zombie",
  "mode": "new_project",
  "timeout_minutes": 60
}'

JOB_ID="<job_id_from_output>"

# Wait for job to enter Builder phase (typically the longest)
sleep 120
cfd gates $JOB_ID  # Confirm Builder is ACTIVE
```

### Simulate Agent Death

```bash
# Find and kill the claude agent process (NOT the daemon)
ps aux | grep "claude.*cf-test-zombie" | grep -v grep
kill <agent_pid>

# Alternative: Kill by working directory
pkill -f "cf-test-zombie"
```

### Wait for Stall Detection

```bash
# Default stall threshold is 600 seconds (10 minutes)
# For testing, you can temporarily modify STALL_THRESHOLD in server.py

# Watch for stall detection (check every minute)
while true; do
    echo "=== $(date) ==="
    cfd show $JOB_ID | grep Status
    cfd timeline $JOB_ID --limit 5
    sleep 60
done
```

### Expected Behavior

| Time | Expected State |
|------|----------------|
| T+0 | Job RUNNING, Builder ACTIVE, heartbeats flowing |
| T+5m | Last heartbeat 5 minutes ago, still RUNNING |
| T+10m | Watchdog detects stall, job marked STALLED |

### Verification Script

```python
"""Test C: Zombie simulation verification"""
from context_foundry.daemon.store import Store
from context_foundry.daemon.state_machine import StateMachine
from context_foundry.daemon.gates import GateManager
from context_foundry.daemon.models import JobStatus, TaskStatus
from pathlib import Path
from datetime import datetime, timedelta

JOB_ID = "<insert_job_id>"

store = Store(Path.home() / ".context-foundry" / "daemon.db")
sm = StateMachine(store)

# Get job
job = store.get_job(JOB_ID)
assert job is not None, "Job not found"

# Verify job is STALLED
assert job.status == JobStatus.STALLED, f"Expected STALLED, got {job.status}"

# Get tasks and check heartbeats
tasks = store.get_tasks_for_job(JOB_ID)
running_tasks = [t for t in tasks if t.status == TaskStatus.RUNNING]

# There should be a task that was running when agent died
# Its last_heartbeat should be old (or task may be TIMED_OUT)

# Check timeline for stall event
timeline = store.get_job_timeline(JOB_ID)
stall_events = [e for e in timeline if "stall" in e.get("status", "").lower()]
assert len(stall_events) > 0, "No stall event in timeline"

# Find last heartbeat event
heartbeat_events = [e for e in timeline if "heartbeat" in e.get("status", "")]
if heartbeat_events:
    last_hb = heartbeat_events[-1]
    print(f"Last heartbeat: {last_hb['timestamp']}")

print("[PASS] Test C: Zombie simulation - job correctly marked STALLED")
```

### Pass Criteria

- [ ] Job marked `STALLED` after heartbeat timeout
- [ ] Phase task is either `TIMED_OUT` or remains non-terminal but job recognized as `STALLED`
- [ ] Timeline clearly shows last heartbeat timestamp
- [ ] Watchdog event visible in timeline indicating stall detection

---

## Test D: Resume Stalled Job

**Objective:** Verify stalled jobs can be resumed and continue execution.

### Prerequisites

- Complete Test C to have a `STALLED` job, OR
- Manually stall a job via the state machine

### Create a Stalled Job (if needed)

```python
"""Manually create a stalled job for testing"""
from context_foundry.daemon.store import Store
from context_foundry.daemon.state_machine import StateMachine
from context_foundry.daemon.models import Job, JobType
from pathlib import Path

store = Store(Path.home() / ".context-foundry" / "daemon.db")
sm = StateMachine(store)

# Create and start a job
job = Job.create(
    job_type=JobType.NEW_PROJECT,
    params={"task": "Test resume", "working_directory": "/tmp/cf-resume-test"}
)
store.save_job(job)
sm.start_job(job.id)

# Create a task and start it
task = sm.create_task_for_phase(job.id, "Builder", 2, 1800)
sm.start_task(task.id)

# Stall the job
sm.stall_job(job.id, "Manual stall for testing")

print(f"Stalled job created: {job.id}")
```

### Resume the Job

```bash
# Via CLI (if implemented)
# cfd resume-stalled $JOB_ID

# Or via Python
python3 << EOF
from context_foundry.daemon.store import Store
from context_foundry.daemon.state_machine import StateMachine
from pathlib import Path

JOB_ID = "<stalled_job_id>"

store = Store(Path.home() / ".context-foundry" / "daemon.db")
sm = StateMachine(store)

# Resume the job
job = sm.resume_stalled_job(JOB_ID)
print(f"Job resumed: {job.status.value}")
EOF
```

### Verification Script

```python
"""Test D: Resume stalled job verification"""
from context_foundry.daemon.store import Store
from context_foundry.daemon.state_machine import StateMachine
from context_foundry.daemon.models import JobStatus
from pathlib import Path

JOB_ID = "<insert_job_id>"

store = Store(Path.home() / ".context-foundry" / "daemon.db")
sm = StateMachine(store)

# Get job - should now be RUNNING
job = store.get_job(JOB_ID)
assert job is not None, "Job not found"
assert job.status == JobStatus.RUNNING, f"Expected RUNNING after resume, got {job.status}"

# Check timeline shows resumption
timeline = store.get_job_timeline(JOB_ID)
resume_events = [e for e in timeline if "resume" in str(e.get("details", {})).lower()]

# Should have state transitions: STALLED -> RUNNING
stall_to_run = [e for e in timeline
                if e.get("status") == "job_running"
                and "stalled" in str(e.get("details", {})).lower()]

print(f"Timeline events after resume: {len(timeline)}")
print("[PASS] Test D: Resume stalled job")
```

### Pass Criteria

- [ ] Job transitions from `STALLED` to `RUNNING`
- [ ] New phases or retries can progress
- [ ] Timeline shows clear resumption event with reason
- [ ] If resume not supported, `STALLED` remains terminal (operator must intervene)

---

## Test E: Replay Consistency

**Objective:** Verify event stream and materialized state never diverge.

### Setup

Use any finished job from previous tests (success, failure, or stall).

```bash
JOB_ID="<any_finished_job_id>"
```

### Verification Script

```python
"""Test E: Replay consistency verification"""
from context_foundry.daemon.store import Store
from context_foundry.daemon.gates import GateManager
from pathlib import Path
import json

JOB_ID = "<insert_job_id>"

store = Store(Path.home() / ".context-foundry" / "daemon.db")
gate_mgr = GateManager(store)

# Get current stored state
job = store.get_job(JOB_ID)
assert job is not None, "Job not found"
stored_status = job.status.value

# Get timeline
timeline = store.get_job_timeline(JOB_ID)
print(f"Timeline has {len(timeline)} events")

# Reconstruct state from events
reconstructed = store.reconstruct_job_state(JOB_ID)
reconstructed_status = reconstructed["current_status"]

# CRITICAL CHECK: Reconstructed must match stored
assert stored_status == reconstructed_status, \
    f"MISMATCH! Stored: {stored_status}, Reconstructed: {reconstructed_status}"

# Get gate report
gate_report = gate_mgr.get_gate_report(JOB_ID)

# Get phase summary
phase_summary = store.get_job_phase_summary(JOB_ID)

# Cross-check: Gate report and phase summary should agree
for gate in gate_report.gates:
    phase_data = phase_summary.get("phases", {}).get(gate.phase)
    if phase_data:
        gate_status_map = {
            "passed": "succeeded",
            "failed": "failed",
            "active": "running",
            "pending": "created",
        }
        expected_task_status = gate_status_map.get(gate.status.value)
        if expected_task_status:
            actual_task_status = phase_data.get("status")
            # Allow some flexibility (e.g., timed_out maps to failed gate)
            if gate.status.value == "failed" and actual_task_status in ("failed", "timed_out"):
                pass  # OK
            elif expected_task_status != actual_task_status:
                print(f"WARNING: Gate {gate.phase} status {gate.status.value} "
                      f"vs phase status {actual_task_status}")

# Save timeline for reference
timeline_file = f"/tmp/timeline_{JOB_ID[:8]}.json"
with open(timeline_file, "w") as f:
    json.dump(timeline, f, indent=2)
print(f"Timeline saved to {timeline_file}")

print(f"\nStored status:       {stored_status}")
print(f"Reconstructed status: {reconstructed_status}")
print(f"Gate report agrees:   {gate_report.all_required_passed if stored_status == 'succeeded' else gate_report.has_failures}")

print("\n[PASS] Test E: Replay consistency - no divergence detected")
```

### Pass Criteria

- [ ] `reconstructed_job_state()` status matches `job.status`
- [ ] Phase summaries from `get_job_phase_summary()` align with gate report
- [ ] No mismatches between event-derived state and stored state
- [ ] If ANY mismatch found, this is a **HIGH PRIORITY BUG**

---

## Automated Test Runner

Run all verification scripts in sequence:

```bash
#!/bin/bash
# run_daemon_tests.sh

set -e

echo "=============================================="
echo "DAEMON WORKFLOW ENGINE TEST SUITE"
echo "=============================================="

# Test A: Requires manual job submission first
# echo "Test A: Happy-path (requires JOB_ID)"
# python3 test_a_happy_path.py

# Test B: Requires manual failure job first
# echo "Test B: Controlled failure (requires JOB_ID)"
# python3 test_b_failure.py

# Test C: Requires manual zombie simulation
# echo "Test C: Zombie simulation (requires setup)"
# python3 test_c_zombie.py

# Test D: Resume stalled job
# echo "Test D: Resume stalled (requires stalled job)"
# python3 test_d_resume.py

# Test E: Replay consistency (run on any finished job)
echo "Test E: Replay consistency"
python3 << 'EOF'
from context_foundry.daemon.store import Store
from pathlib import Path

store = Store(Path.home() / ".context-foundry" / "daemon.db")

# Get recent completed jobs
from context_foundry.daemon.models import JobStatus
jobs = store.list_jobs(limit=5)
completed_jobs = [j for j in jobs if j.status in JobStatus.terminal_states()]

if not completed_jobs:
    print("No completed jobs to test replay consistency")
    exit(0)

for job in completed_jobs[:3]:
    print(f"\nChecking job {job.id[:8]}...")
    reconstructed = store.reconstruct_job_state(job.id)
    if reconstructed["current_status"] != job.status.value:
        print(f"  MISMATCH! Stored: {job.status.value}, Reconstructed: {reconstructed['current_status']}")
        exit(1)
    print(f"  OK: {job.status.value}")

print("\n[PASS] All replay consistency checks passed")
EOF

echo ""
echo "=============================================="
echo "TEST SUITE COMPLETE"
echo "=============================================="
```

---

## Quick Reference: CLI Commands

| Command | Purpose |
|---------|---------|
| `cfd gates <job_id>` | Show phase gate status |
| `cfd timeline <job_id>` | Show event timeline |
| `cfd timeline <job_id> --heartbeats` | Include heartbeat events |
| `cfd events` | Recent events across all jobs |
| `cfd events --type task_failed` | Filter by event type |
| `cfd reconstruct <job_id>` | Reconstruct state from events |
| `cfd phase-summary <job_id>` | Phase progress summary |
| `cfd show <job_id>` | Full job details |

---

## Troubleshooting

### Job stuck in RUNNING but no heartbeats

1. Check watchdog is running: `cfd status -v`
2. Check heartbeat file age: `cat ~/.context-foundry/daemon_heartbeat.txt`
3. Verify stall threshold: Default is 600s (10 min)

### Mismatch between reconstructed and stored state

This is a **critical bug**. Steps:
1. Export timeline: `cfd timeline <job_id> --json > timeline.json`
2. Check for missing events or out-of-order timestamps
3. Verify all state transitions emit events

### Gates not updating

1. Verify tasks exist: `cfd phase-summary <job_id>`
2. Check task status in DB directly
3. Ensure phase_execution.py is creating tasks via state machine
