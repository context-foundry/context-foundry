# Architecture Specification: Context Foundry Dashboard Redesign

## System Overview

Complete redesign of the livestream dashboard to provide detailed, phase-by-phase build monitoring with session management tabs and comprehensive progress tracking.

## File Structure

```
tools/livestream/
├── server.py          (MODIFY - Add new API endpoints)
├── dashboard.html     (COMPLETE REDESIGN - New UI)
└── metrics_db.py      (NO CHANGES - Schema sufficient)
```

## Component Architecture

### 1. Backend API Endpoints (server.py)

#### NEW ENDPOINTS:

**GET `/api/phases/{session_id}`**
```python
Response: {
  "session_id": "context-foundry",
  "total_phases": 7,
  "phases_completed_count": 3,
  "current_phase_number": 4,
  "overall_progress_percent": 50.0,
  "phases": [
    {
      "number": 0,
      "name": "Codebase Analysis",
      "emoji": "🔍",
      "status": "completed",
      "description": "Analyzed project structure and dependencies",
      "completed_at": "2025-01-13T10:05:00Z"
    },
    {
      "number": 1,
      "name": "Scout",
      "emoji": "🔍",
      "status": "completed",
      "description": "Researched requirements and patterns",
      "completed_at": "2025-01-13T10:15:00Z"
    },
    {
      "number": 2,
      "name": "Architect",
      "emoji": "🏗️",
      "status": "completed",
      "description": "Designed system architecture",
      "completed_at": "2025-01-13T10:30:00Z"
    },
    {
      "number": 3,
      "name": "Builder",
      "emoji": "🔨",
      "status": "in_progress",
      "description": "Writing code across multiple files",
      "detail": "Creating new API endpoints, implementing business logic",
      "note": "This is typically the longest phase!",
      "progress_percent": 60
    },
    {
      "number": 4,
      "name": "Tester",
      "emoji": "🧪",
      "status": "pending",
      "description": "Running tests and validating implementation"
    },
    {
      "number": 5,
      "name": "Test Loop",
      "emoji": "🔄",
      "status": "pending",
      "description": "Auto-fix if tests fail (conditional)"
    },
    {
      "number": 6,
      "name": "Documentation",
      "emoji": "📝",
      "status": "pending",
      "description": "Creating comprehensive docs (optional)"
    },
    {
      "number": 7,
      "name": "Deployer",
      "emoji": "🚀",
      "status": "pending",
      "description": "Git commit and PR creation"
    }
  ]
}
```

**GET `/api/sessions/active`**
```python
Response: {
  "sessions": [
    {
      "id": "context-foundry",
      "project": "context-foundry",
      "status": "running",
      "current_phase": "Builder",
      "phase_number": "3/7",
      "progress_percent": 42.8,
      "start_time": "2025-01-13T10:00:00Z",
      "elapsed_seconds": 1800,
      "estimated_remaining_seconds": 2400
    }
  ],
  "count": 1
}
```

**GET `/api/sessions/completed`**
```python
Response: {
  "sessions": [...],  # Same structure, status="completed"
  "count": 15
}
```

**GET `/api/sessions/failed`**
```python
Response: {
  "sessions": [...],  # Same structure, status="failed"
  "count": 2
}
```

#### ENHANCED EXISTING ENDPOINTS:

**GET `/api/status/{session_id}`** - Add phase breakdown to response
```python
# Add to existing response:
"phase_breakdown": {
  "completed": ["Scout", "Architect"],
  "current": "Builder",
  "remaining": ["Tester", "Test Loop", "Documentation", "Deployer"]
},
"overall_progress_percent": 35.7,
"estimated_remaining_seconds": 3900
```

### 2. Frontend UI Structure (dashboard.html)

#### LAYOUT HIERARCHY:

```
┌─────────────────────────────────────────────────────────────┐
│ Header: 🏭 Context Foundry Build Monitor                   │
├─────────────────────────────────────────────────────────────┤
│ Top Metrics Bar:                                            │
│   📊 ACTIVE: 2 | ✅ COMPLETED: 15 | ⏱️ AVG TIME: 12m 30s   │
├─────────────────────────────────────────────────────────────┤
│ Session Tabs:                                               │
│   [🟢 Active] [✅ Completed] [❌ Failed] [📊 All]          │
├─────────────────────────────────────────────────────────────┤
│ Session Selector (filtered by tab):                         │
│   Dropdown showing sessions matching current tab filter     │
├─────────────────────────────────────────────────────────────┤
│ Build Status Card:                                          │
│   🚀 Build Status Update                                    │
│   Task ID: abc-123                                          │
│   Project: my-awesome-app                                   │
│   Status: ✅ Running                                        │
│   Overall Progress: 45.2% (8.5 minutes elapsed)            │
│   Est. Remaining: ~10-15 minutes                            │
├─────────────────────────────────────────────────────────────┤
│ ✅ COMPLETED PHASES:                                        │
│   1. Phase 0 - Codebase Analysis ✅                         │
│      • Analyzed project structure                           │
│      • Identified dependencies                              │
│   2. Phase 1 - Scout ✅                                     │
│      • Researched implementation patterns                   │
├─────────────────────────────────────────────────────────────┤
│ 🔨 CURRENT PHASE:                                           │
│   Phase 3 - Builder (In Progress - The Big One!)           │
│   Status: Writing code across multiple files                │
│   Tasks in progress:                                        │
│     • Creating new API endpoints                            │
│     • Implementing business logic                           │
│   Progress: 60% of phase complete                           │
├─────────────────────────────────────────────────────────────┤
│ 📋 UPCOMING PHASES:                                         │
│   ⏱️ Phase 4 - Tester                                       │
│   ⏱️ Phase 5 - Test Loop (if needed)                        │
│   ⏱️ Phase 6 - Documentation                                │
│   ⏱️ Phase 7 - Deployer                                     │
├─────────────────────────────────────────────────────────────┤
│ 💬 WHAT'S HAPPENING NOW:                                    │
│   The Builder agents are actively implementing...           │
│   Next: Once building completes, the Tester will run...     │
├─────────────────────────────────────────────────────────────┤
│ 📊 LIVE LOGS:                                               │
│   [scrollable log viewer]                                   │
└─────────────────────────────────────────────────────────────┘
```

#### COMPONENT BREAKDOWN:

1. **TopMetricsBar Component**
   - Displays aggregate statistics
   - Always visible
   - Updates when sessions change

2. **SessionTabs Component**
   - Four tabs: Active, Completed, Failed, All
   - State managed in JavaScript
   - Filters session list on click

3. **SessionSelector Component**
   - Dropdown filtered by active tab
   - Triggers WebSocket reconnection on change
   - Shows session count in tab

4. **BuildStatusCard Component**
   - Overall progress, elapsed time, remaining time
   - Project name, task ID, status badge
   - Prominent display at top

5. **CompletedPhases Component**
   - Expandable/collapsible section
   - Each phase with description bullets
   - Green checkmarks

6. **CurrentPhase Component**
   - Highlighted/emphasized styling
   - Detailed description
   - Progress bar within phase
   - Special note for Builder ("The Big One!")

7. **UpcomingPhases Component**
   - Simple list with pending icons
   - Phase names only

8. **WhatsHappeningNow Component**
   - Narrative description
   - Current activities
   - Next step preview

9. **LiveLogs Component**
   - Preserve existing logs viewer
   - Scrollable, auto-scroll to bottom

### 3. Data Models

#### SessionFilter State (Frontend)
```javascript
const sessionFilters = {
  active: session => session.status === 'running',
  completed: session => session.status === 'completed',
  failed: session => session.status === 'failed',
  all: session => true
};

let currentFilter = 'active';  // Default to active sessions
```

#### Phase Definition (Frontend)
```javascript
const PHASE_DEFINITIONS = [
  { number: 0, name: "Codebase Analysis", emoji: "🔍" },
  { number: 1, name: "Scout", emoji: "🔍" },
  { number: 2, name: "Architect", emoji: "🏗️" },
  { number: 3, name: "Builder", emoji: "🔨", note: "This is typically the longest phase!" },
  { number: 4, name: "Tester", emoji: "🧪" },
  { number: 5, name: "Test Loop", emoji: "🔄" },
  { number: 6, name: "Documentation", emoji: "📝" },
  { number: 7, name: "Deployer", emoji: "🚀" }
];
```

## Implementation Steps

### Step 1: Backend Enhancements (server.py)

1.1. Add helper function to calculate phase breakdown
```python
def get_phase_breakdown(session_data: Dict) -> Dict:
    """Calculate detailed phase breakdown from session data."""
    # Parse current_phase.json data
    # Return structured phase breakdown
```

1.2. Implement new endpoint `/api/phases/{session_id}`
```python
@app.get("/api/phases/{session_id}")
async def get_session_phases(session_id: str):
    # Get session data
    # Calculate phase breakdown
    # Return formatted response
```

1.3. Implement session filter endpoints
```python
@app.get("/api/sessions/active")
async def get_active_sessions():
    sessions = monitor.discover_sessions()
    active = [s for s in sessions if s['status'] == 'running']
    return JSONResponse({"sessions": active, "count": len(active)})

# Similar for completed and failed
```

1.4. Enhance existing `/api/status/{session_id}` response
```python
# Add phase_breakdown, overall_progress_percent, estimated_remaining_seconds
```

### Step 2: Frontend Complete Redesign (dashboard.html)

2.1. **HTML Structure Redesign**
- Remove old main-grid layout
- Create new single-column layout with sections
- Add tab navigation HTML
- Add phase sections (completed/current/upcoming)
- Add "what's happening now" section
- Preserve logs section at bottom

2.2. **CSS Updates** (Preserve Terminal.css aesthetic!)
- Add tab styling (.tab, .tab-active)
- Add phase section styling (.phase-section)
- Add completed phase styling (.phase-completed)
- Add current phase styling (.phase-current, highlighted)
- Add upcoming phase styling (.phase-upcoming, grayed)
- Add progress bar styling for phase-level progress

2.3. **JavaScript Refactoring**
- Create `updatePhaseBreakdown(phaseData)` function
- Create `updateSessionTabs(sessions)` function
- Create `filterSessions(filter)` function
- Create `renderCompletedPhases(phases)` function
- Create `renderCurrentPhase(phase)` function
- Create `renderUpcomingPhases(phases)` function
- Create `renderWhatsHappeningNow(status)` function
- Update WebSocket handler to call new render functions

2.4. **State Management**
```javascript
let allSessions = [];
let currentFilter = 'active';
let selectedSession = null;

function switchTab(filter) {
  currentFilter = filter;
  updateSessionSelector();
  updateTabStyling();
}

function updateSessionSelector() {
  const filtered = allSessions.filter(sessionFilters[currentFilter]);
  populateSelector(filtered);
}
```

### Step 3: Integration & Polish

3.1. Ensure WebSocket updates trigger phase breakdown refresh
3.2. Implement auto-refresh fallback (every 3 seconds)
3.3. Add loading states for async operations
3.4. Handle missing data gracefully (legacy sessions)
3.5. Test responsive design (mobile, tablet, desktop)

## Testing Plan

### Unit Tests
1. Backend endpoint responses match expected structure
2. Phase breakdown calculation accuracy
3. Session filtering logic correctness
4. Progress percentage calculations
5. Time estimation algorithm

### Integration Tests
1. WebSocket updates trigger UI refresh
2. Tab switching updates session list
3. Session selection triggers data load
4. Phase transitions update UI correctly
5. Real-time progress updates work

### End-to-End Tests
1. Load dashboard with active session → See detailed phase breakdown
2. Switch between tabs → Session list filters correctly
3. Select different session → Data updates
4. Monitor live build → Phases update in real-time
5. Export functionality → Still works
6. Legacy session (no phase data) → Graceful degradation

### Edge Cases
1. Session with no current-phase.json → Shows "Unknown phase"
2. Session mid-test-iteration → Shows test iteration count
3. Failed session → Displays in Failed tab with error info
4. Very long session (>1 hour) → Time displays correctly
5. Rapid tab switching → No race conditions

## Success Criteria

✅ All existing functionality preserved (WebSocket, export, logs, metrics)
✅ Terminal CSS aesthetic maintained throughout
✅ New phase breakdown displays for all sessions with phase data
✅ Session tabs work and filter correctly
✅ Overall progress percentage calculates accurately
✅ Time estimates are reasonable and update
✅ "What's happening now" provides useful narrative
✅ UI updates smoothly with WebSocket messages
✅ No console errors or broken layouts
✅ Responsive design works on all screen sizes

## Rollback Plan

If issues arise:
1. Git revert to previous dashboard.html
2. Remove new API endpoints (old endpoints still work)
3. All data preserved (no database changes)
4. Zero downtime (server restart not required)

## Next Steps

Hand off to Builder for implementation with this exact specification.
