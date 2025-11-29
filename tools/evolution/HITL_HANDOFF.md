# HITL (Human-in-the-Loop) Implementation Handoff

**Date**: 2025-11-29 (Updated)
**Status**: Auto-Handoff Implemented

---

## Auto-Handoff Model (NEW - 2025-11-29)

### What Changed: No Post-Phase Pauses

HITL mode now uses an **auto-handoff** model where:

1. **Human approval still required BEFORE each phase** (prompt review/editing via `wait_for_acknowledgment`)
2. **No post-phase pauses** - pipeline continues automatically to next phase (no `cfd resume` needed)
3. The pipeline flows continuously, pausing only for prompt approval

### Flow:
```
Scout prompts created → Human approves → Scout runs → scout_report.json created
    ↓ NO PAUSE (auto-handoff)
Architect prompts created → Human approves → Architect runs → architecture.json created
    ↓ NO PAUSE (auto-handoff)
Builder prompts created → Human approves → Builder runs → build-tasks.json created
    ↓ NO PAUSE (auto-handoff)
(... continues through Test, Deploy, etc.)
```

**Important Clarification**: "Auto-handoff" means no `cfd resume` between phases, NOT automatic execution.
Each phase still blocks for human prompt approval before starting. The human approval gate is
`wait_for_acknowledgment()` in `phase_prompts.py`, not the removed `pause_after_phases`.

### JSON-First Input Preference

Each phase now prefers `.json` over `.md` inputs:
- **Architect**: Looks for `scout_report.json` first, falls back to `scout-report.md`
- **Builder**: Looks for `architecture.json` first, falls back to `architecture.md`

This ensures structured data is used when available, with markdown as fallback.

### Phase Outputs (Contract Completion Signals)

| Phase | Output File(s) | Signal to Next Phase |
|-------|---------------|----------------------|
| Scout | `scout_report.json`, `scout-report.md` | Architect can begin |
| Architect | `architecture.json`, `architecture.md` | Builder can begin |
| Builder | `build-tasks.json` | Test can begin |
| Test | Test results | Deploy can begin |
| Deploy | Deployment artifacts | Feedback can begin |

---

## What Was Accomplished

### 1. API URL Fix for cf.html (COMPLETED)
The dashboard UI (cf.html) was calling phase endpoints on the wrong port. Fixed by:

- Added `dashboardApiBase: 'http://localhost:8420'` to CONFIG section (line ~1942)
- Updated ALL phase-related fetch calls to use `${CONFIG.dashboardApiBase}`:
  - `/phase-prompts` (GET and POST)
  - `/phase-acknowledge`
  - `/phase-inject`

**File**: `/Users/name/homelab/context-foundry/tools/evolution/cf.html`

### 2. State Machine Fix (COMPLETED - from earlier session)
Fixed `_inject_phase_prompt` in dashboard.py to use proper state constants:
- Uses `STATE_READY`, `STATE_PROCESSING`, `STATE_COMPLETE`, `STATE_FAILED`
- No longer uses old string literals ("pending", "approved")

**File**: `/Users/name/homelab/context-foundry/context_foundry/daemon/dashboard.py`

### 3. task_config Propagation (COMPLETED - from earlier session)
Added `task_config=task_config` to Screenshot, Documentation, and Deploy phases in autonomous_build.py so HITL applies to all phases.

**File**: `/Users/name/homelab/context-foundry/tools/mcp_utils/autonomous_build.py`

### 4. Test Build Submitted
A test calculator build is running with HITL mode:
- **Job ID**: `85c5616c-3fb6-4b56-86b9-87c8a9b0c48a`
- **Working Dir**: `/private/tmp/calc-hitl-test-x7j`
- **Current Phase**: Scout (state: `ready`, waiting for acknowledgment)

---

## What's Remaining

### 1. Dashboard Serving Issue (BLOCKER)
The cf.html dashboard isn't accessible:
- Port 8421 (TUI proxy) shows "Connecting..." - not running or not forwarding
- Port 8420 (daemon dashboard) returns 404 for `/cf.html` - doesn't serve static files

**Fix needed**: Either:
- Start the TUI which serves as proxy on 8421
- Or add static file serving to the daemon dashboard on 8420
- Or serve cf.html from a separate static server

### 2. Agent Activity Display (FEATURE REQUEST)
User requested showing real-time agent activity during "Agent executing..." state:
- What the agent is thinking/saying
- Tool calls being made
- Tool results

**Infrastructure exists but not integrated**:
- `/Users/name/homelab/context-foundry/tools/mcp_utils/conversation_logger.py` - Parses stream-json output
- `/Users/name/homelab/context-foundry/tools/glass-pane/backend/api/agent_events.py` - SSE streaming API

**Integration needed**:
- Add activity panel to cf.html
- Connect to conversation logs or SSE stream
- Display events in real-time during phase execution

### 3. Job Status Sync Issue (BUG)
CLI shows jobs as "queued" even when daemon logs show they're "running". Status not being updated in the store properly.

---

## Architecture Notes

### Port Architecture
- **8420**: Daemon dashboard (HITL API endpoints like `/phase-acknowledge`, `/phase-prompts`, `/phase-inject`)
- **8421**: TUI proxy (serves cf.html, forwards some requests to 8420)

### HITL Flow (Updated - Auto-Handoff Model)
1. Job submitted with `execution_mode: "hitl"` (or `"human_in_the_loop"`)
2. **Before** each phase, prompt is written to `.context-foundry/phase-prompts/{phase}-prompt.json` with state `draft`
3. Phase execution blocks waiting for acknowledgment (via `wait_for_acknowledgment()`)
4. User reviews/edits prompts in dashboard, clicks "Acknowledge & Start"
5. Dashboard calls `/phase-acknowledge` which sets state to `acknowledged_edited` or `acknowledged_unedited`
6. Phase execution transitions to `processing` and runs the agent
7. Agent completes, produces output files (.json preferred)
8. **AUTO-HANDOFF**: Next phase's prompts are immediately generated (no pause)
9. Repeat from step 3 for next phase

**Key Change**: No more pausing AFTER phases - phases auto-trigger as soon as outputs are produced.
Human checkpoint is BEFORE each phase (prompt approval), not after.

### Key Files
- `tools/evolution/cf.html` - Dashboard UI
- `context_foundry/daemon/dashboard.py` - HITL API endpoints
- `tools/mcp_utils/phase_prompts.py` - State constants and prompt management
- `tools/mcp_utils/phase_execution.py` - Phase runner with HITL blocking
- `tools/mcp_utils/autonomous_build.py` - Orchestrator calling phases

---

## Quick Test Commands

```bash
# Check daemon status
python3 -m context_foundry.daemon.cli status

# List jobs
python3 -m context_foundry.daemon.cli list

# Check specific job
python3 -m context_foundry.daemon.cli show 85c5616c-3fb6-4b56-86b9-87c8a9b0c48a

# Check daemon logs
tail -50 ~/.context-foundry/cfd/logs/cfd.log

# Check phase prompt state
cat /private/tmp/calc-hitl-test-x7j/.context-foundry/phase-prompts/scout-prompt.json | jq '.state'

# Manual acknowledge via curl (if dashboard not working)
curl -X POST "http://localhost:8420/phase-acknowledge" \
  -H "Content-Type: application/json" \
  -d '{"job_id": "85c5616c-3fb6-4b56-86b9-87c8a9b0c48a", "phase": "Scout", "acknowledged_by": "manual"}'
```
