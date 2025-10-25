# Scout Report: Context Foundry Dashboard Redesign

## Executive Summary

**Mission**: Complete redesign of the Context Foundry livestream dashboard to provide detailed, phase-by-phase build status monitoring similar to Claude Code's UI.

**Scope**: This is a fix_bugs/enhancement mode task on an existing Python/FastAPI + HTML/JS project. The current dashboard provides basic real-time monitoring but lacks the detailed phase breakdown and user-friendly session management required for effective autonomous build monitoring.

**Complexity**: Medium-High - Requires comprehensive UI restructuring, new API endpoints, and careful preservation of existing real-time features.

## Key Requirements Analysis

### 1. Complete UI Redesign (Primary Focus)
- **Remove**: Current basic panels (phase card, simple task list)
- **Add**: Comprehensive phase-tracking dashboard with:
  * Overall progress percentage calculation
  * Elapsed time display (human-readable format)
  * Current phase with emoji and detailed status
  * Phase-by-phase breakdown (completed ✅ / current 🔨 / upcoming ⏱️)
  * Estimated time remaining
  * "What's happening now" narrative section

### 2. Session Management with Tabs
- **Tab System**: Active / Completed / Failed / All Sessions
- **Session Cards**: Clickable items showing:
  * Session ID and project name
  * Start time and status indicator
  * Progress bar/percentage
  * Quick status badge

### 3. Phase Tracking System
Must track and display these phases:
- Phase 0: Codebase Analysis
- Phase 1: Scout
- Phase 2: Architect
- Phase 3: Builder (noted as "The Big One!")
- Phase 4: Tester
- Phase 5: Test Loop (if needed)
- Phase 6: Documentation (optional)
- Phase 7: Deployer

### 4. Backend Enhancements
**New API Endpoints Needed**:
- GET `/api/phases/{session_id}` - Detailed phase breakdown
- GET `/api/sessions/active` - Active sessions only
- GET `/api/sessions/completed` - Completed sessions only
- GET `/api/sessions/failed` - Failed sessions only

**Enhanced Response Data**:
- Phase-by-phase breakdown with timestamps
- Progress percentage calculation (phases completed / total phases * 100)
- Estimated remaining time based on elapsed time and phase progress

## Technology Stack

### Frontend
- **HTML/CSS/JS**: Pure vanilla (no frameworks required)
- **Terminal CSS**: MUST preserve retro terminal aesthetic
- **Chart.js**: Already available (optional for visualizations)
- **WebSocket**: Real-time updates (preserve existing implementation)

### Backend
- **FastAPI**: Existing server.py
- **SQLite**: Existing metrics_db.py (schema sufficient, may need query updates)
- **Python 3**: Standard library + asyncio for WebSocket

## Critical Architecture Recommendations

### 1. Preserve Existing Features
**MUST NOT BREAK**:
- WebSocket real-time updates
- Terminal CSS aesthetic
- Export functionality
- Backwards compatibility with `/api/phase-update` endpoint
- Multi-agent monitoring (if present)
- Enhanced metrics panels

### 2. Data Flow Architecture
```
Autonomous Build → current-phase.json → POST /api/phase-update
                                              ↓
                                    SessionMonitor.sessions
                                              ↓
                                    WebSocket broadcast
                                              ↓
                                    Dashboard UI Update
```

### 3. Phase Data Structure
Parse `current-phase.json` to extract:
```json
{
  "session_id": "project-name",
  "current_phase": "Builder",
  "phase_number": "3/7",
  "status": "implementing",
  "progress_detail": "Writing code across multiple files",
  "test_iteration": 0,
  "phases_completed": ["Scout", "Architect"],
  "started_at": "ISO timestamp",
  "last_updated": "ISO timestamp"
}
```

### 4. Progress Calculation
```python
total_phases = 7
phases_completed_count = len(phases_completed)
overall_progress = (phases_completed_count / total_phases) * 100

# For current phase in-progress, add partial credit:
if current_phase_number:
    phase_num = int(current_phase_number.split('/')[0])
    overall_progress = ((phase_num - 1 + 0.5) / total_phases) * 100
```

### 5. Time Estimation
```python
elapsed_seconds = (now - started_at).total_seconds()
phases_done = len(phases_completed)
if phases_done > 0:
    avg_time_per_phase = elapsed_seconds / phases_done
    remaining_phases = total_phases - phases_done
    estimated_remaining = avg_time_per_phase * remaining_phases
```

## Main Challenges & Mitigations

### Challenge 1: Backwards Compatibility
**Risk**: Breaking existing autonomous builds that depend on current API structure
**Mitigation**:
- Keep all existing endpoints functional
- Add new endpoints, don't modify existing ones
- Ensure /api/phase-update still works exactly as before

### Challenge 2: Data Availability
**Risk**: current-phase.json may not exist for older/checkpoint-based sessions
**Mitigation**:
- Implement graceful degradation
- Fall back to basic checkpoint data if phase data unavailable
- Show "Unknown phase" or "Legacy session" for old data

### Challenge 3: Real-Time UI Updates
**Risk**: New complex UI may not update smoothly with WebSocket
**Mitigation**:
- Use efficient DOM updates (update only changed elements)
- Maintain existing change detection hash system
- Auto-refresh every 2-3 seconds as backup

### Challenge 4: Session Filtering Performance
**Risk**: Filtering hundreds of sessions by status could be slow
**Mitigation**:
- Implement server-side filtering (new endpoints)
- Cache session lists in memory
- Use indexes in SQLite queries

## Testing Requirements

### Functional Tests
1. ✅ Phase tracking displays correctly for all 7 phases
2. ✅ Tab switching works (Active/Completed/Failed/All)
3. ✅ Session filtering returns correct results
4. ✅ WebSocket updates trigger UI refresh
5. ✅ Progress percentage calculates accurately
6. ✅ Time estimates display correctly
7. ✅ Export functionality still works
8. ✅ Terminal CSS aesthetic preserved

### Edge Cases
1. Session with missing current-phase.json
2. Session with partial phase data
3. Very long-running session (hours)
4. Session that failed mid-build
5. Multiple concurrent active sessions
6. Switching between sessions rapidly

## Timeline Estimate

- **Scout** (Research): ~10 minutes ✅
- **Architect** (Design): ~15 minutes
- **Builder** (Implementation): ~45 minutes (The Big One!)
  * Backend API endpoints: ~15 min
  * Frontend UI restructure: ~25 min
  * Integration & polish: ~5 min
- **Test** (Validation): ~20 minutes
- **Documentation**: ~5 minutes
- **Deploy**: ~5 minutes

**Total**: ~100 minutes (1 hour 40 minutes)

## Success Criteria

1. ✅ Dashboard shows overall progress percentage prominently
2. ✅ Current phase displays with emoji, name, and detailed status
3. ✅ Completed phases shown with checkmarks and descriptions
4. ✅ Upcoming phases listed with pending icons
5. ✅ Session tabs work (Active/Completed/Failed/All)
6. ✅ Real-time updates via WebSocket still functional
7. ✅ Terminal CSS aesthetic fully preserved
8. ✅ No broken functionality (export, logs, metrics)
9. ✅ Graceful degradation for missing data
10. ✅ Responsive design (works on different screen sizes)

## Next Steps

Hand off to Architect for:
1. Detailed component structure design
2. API endpoint specifications
3. Data model definitions
4. UI layout mockups (text/ASCII format)
5. Implementation task breakdown
