# Bug: Dashboard Missing Resume Button for Paused HITL Jobs

**Date Discovered:** 2025-11-29
**Date Fixed:** 2025-11-29
**Severity:** Medium
**Status:** FIXED
**Affected Component:** Dashboard UI (`tools/evolution/cf.html`), Backend (`context_foundry/daemon/dashboard.py`)

## Summary

When a job pauses after completing a phase in HITL (Human-in-the-Loop) mode, the dashboard does not display a "Resume" or "Approve" button. Users have no way to continue the build from the UI.

## Steps to Reproduce

1. Start a build with HITL pauses:
   ```bash
   ./tools/cfd submit --task "Build something" --pause-after Scout,Architect,Builder
   ```

2. Acknowledge the Scout prompt in the dashboard

3. Wait for Scout phase to complete

4. Observe: The job shows as "running" but is actually paused
   - No "Resume" button appears
   - No indication that user action is required
   - The only way to continue is via CLI

## Expected Behavior

When a job pauses after a phase:
- Dashboard should show a "Resume" or "Continue to [NextPhase]" button
- Job status should clearly indicate "Paused - Awaiting Approval"
- The approval panel should list the paused job

## Actual Behavior

- Dashboard shows job as "running"
- No Resume/Approve button visible
- `/pending-approvals` API returns empty `{"approvals": []}`
- User must use CLI workaround: `./tools/cfd resume --dir /path --from <Phase>`

## Root Cause

Two separate approval mechanisms exist that aren't connected:

1. **ApprovalManager** (`tools/mcp_utils/approval_gates.py`)
   - Used by `/pending-approvals` API
   - Dashboard polls this for approval buttons
   - Returns empty list for HITL pauses

2. **Pipeline State** (`pipeline-state.json`)
   - Set to `state: paused` when HITL phase completes
   - Contains `paused_at` timestamp
   - Dashboard doesn't check this for showing Resume button

## Technical Details

### Dashboard Code (`tools/evolution/cf.html`)

```javascript
// Line 3994-3999: Only checks ApprovalManager
async function fetchPendingApprovals() {
    const res = await fetch('/pending-approvals');
    const data = await res.json();
    state.pendingApprovals = data.approvals || [];  // Always empty for HITL pauses
}
```

### Backend Code (`context_foundry/daemon/dashboard.py`)

```python
# Line 566-578: Only queries ApprovalManager
def _serve_pending_approvals(self) -> None:
    from tools.mcp_utils.approval_gates import ApprovalManager
    manager = ApprovalManager()
    pending = manager.list_pending_requests()  # Doesn't include HITL paused jobs
```

### Pipeline State When Paused

```json
{
  "state": "paused",
  "current_phase": null,
  "paused_at": "2025-11-28T23:53:45.123456",
  "phases_completed": ["Scout"],
  "phases_remaining": ["Architect", "Builder", "Test", ...]
}
```

## Proposed Fix

### Option A: Extend `/pending-approvals` to include paused pipelines

In `dashboard.py`:
```python
def _serve_pending_approvals(self) -> None:
    # Existing ApprovalManager logic...
    approvals = [req.to_dict() for req in pending]

    # Also check for paused pipelines
    for job in self.server.context.store.list_jobs(status="running"):
        working_dir = job.params.get("working_directory")
        if working_dir:
            pipeline_state_file = Path(working_dir) / ".context-foundry" / "pipeline-state.json"
            if pipeline_state_file.exists():
                state = json.loads(pipeline_state_file.read_text())
                if state.get("state") == "paused":
                    approvals.append({
                        "request_id": f"resume-{job.id}",
                        "pipeline_id": job.id,
                        "working_directory": working_dir,
                        "phase": state.get("phases_remaining", ["Unknown"])[0],
                        "type": "phase_resume",
                        "status": "pending",
                        "paused_at": state.get("paused_at"),
                        "phases_completed": state.get("phases_completed", []),
                    })
```

### Option B: Add dedicated `/paused-jobs` endpoint

Create a new endpoint that specifically lists jobs with `pipeline-state.json` showing `state: paused`.

### Option C: Check pipeline state in job detail view

In the dashboard, when viewing a job, also check its `pipeline-state.json` and show a Resume button if `state === "paused"`.

## Solution Implemented (Option A)

Extended `/pending-approvals` endpoint to include paused pipelines:

### Backend Changes (`dashboard.py`)

1. Modified `_serve_pending_approvals()` to scan all jobs for paused pipelines
2. Added new `_resume_pipeline()` POST endpoint to handle resume requests
3. Returns approvals with `type: "phase_resume"` for paused HITL pipelines

### Frontend Changes (`cf.html`)

1. Added `resumePipeline(jobId, fromPhase)` function
2. Updated `renderApprovalBanner()` to display special Resume banner for `type: "phase_resume"`
3. Resume banner shows completed phases, pause time, and "Resume → [Phase]" button

## Related Files

- `tools/evolution/cf.html` - Dashboard frontend (updated)
- `context_foundry/daemon/dashboard.py` - Dashboard backend API (updated)
- `tools/mcp_utils/approval_gates.py` - ApprovalManager (not used for HITL)
- `tools/mcp_utils/phase_prompts.py` - HITL phase management

## Additional Notes

- The "Acknowledge" button for reviewing prompts DOES work correctly
- Resume button now appears for all paused HITL pipelines
- CLI `cfd resume` command still works as an alternative
