# Codebase Analysis Report

## Project Overview
- Type: Python web application (FastAPI backend + HTML/JS frontend)
- Languages: Python, HTML, JavaScript
- Architecture: Real-time monitoring dashboard with WebSocket updates

## Key Files

### Backend
- **server.py**: Main FastAPI server with WebSocket support
  - Live session monitoring via /api/phase-update endpoint
  - Multi-agent monitoring endpoints
  - Enhanced MCP metrics integration
  - WebSocket real-time updates with change detection
  
- **metrics_db.py**: SQLite database for comprehensive metrics
  - Tasks, metrics, decisions, agent performance tracking
  - Multi-agent instance tracking table
  - Pattern effectiveness tracking

### Frontend
- **dashboard.html**: Current dashboard UI
  - Terminal CSS aesthetic (must preserve)
  - Basic phase display with colored cards
  - Multi-agent panel (hidden by default)
  - Task progress tracking
  - Live logs viewer
  - Enhanced metrics panels (token usage, test loop, agent performance, decision tracking)

## Current Functionality

### Session Tracking
- Discovers sessions from both live phase-update API and checkpoint files
- Real-time WebSocket updates for active sessions
- Change detection to minimize unnecessary updates

### Phase Tracking
- Phases: Scout, Architect, Builder (displayed as colored cards)
- Phase status updates via /api/phase-update endpoint
- Current implementation shows ONE active phase card at top

### Multi-Agent Support
- Agent instance tracking in database
- Agent progress monitoring with token usage per agent
- WebSocket broadcasts for agent updates
- Hidden panel (only shows if agents exist)

## Current Dashboard Layout

1. **Header**: Project title
2. **Session Selector**: Dropdown to choose active session
3. **Multi-Agent Panel**: (hidden) Shows active agents if any
4. **Main Grid**: Two columns
   - Left: Phase card, Context usage, Task progress, Live logs
   - Right: Session info, Statistics, Connection status, Actions
5. **Detailed Metrics**: Token usage, Test loop, Agent performance, Decision quality

## Issues with Current Design

1. **Lacks detailed phase breakdown**
   - Only shows current phase, not completed/upcoming phases
   - No phase-by-phase progress view
   - Missing "what's happening now" narrative

2. **No session tabs**
   - Can't filter by active/completed/failed sessions
   - Session selector is simple dropdown, not categorized

3. **Limited progress visibility**
   - No overall progress percentage
   - No estimated time remaining
   - No detailed phase descriptions

4. **Missing critical features from requirements**
   - No phase completion checklist
   - No upcoming phases preview
   - No detailed "what's happening now" section
   - No metrics at top showing overall status

## Code to Modify

**Files to change**:
1. `tools/livestream/dashboard.html` - Complete UI redesign
2. `tools/livestream/server.py` - Add new API endpoints for phase breakdown
3. `tools/livestream/metrics_db.py` - Schema looks sufficient, may need minor updates

**Approach**:
- Scrap existing dashboard layout completely
- Build new phase-tracking focused UI
- Add new API endpoints to serve phase breakdown data
- Parse current-phase.json for detailed phase info
- Implement session tabs (Active/Completed/Failed/All)
- Add overall progress metrics at top
- Create phase-by-phase breakdown sections

## Risks

1. **Breaking existing functionality**
   - Must preserve WebSocket updates
   - Must preserve Terminal CSS aesthetic
   - Must preserve export functionality
   - Must maintain backwards compatibility with existing APIs

2. **Data availability**
   - current-phase.json may not exist for all sessions
   - Need graceful degradation if phase data unavailable

3. **Real-time updates**
   - New UI must update smoothly when phases change
   - Tab switching must maintain WebSocket connection
   - Progress calculations must be accurate

## Dependencies
- FastAPI, uvicorn (backend)
- Terminal CSS (frontend styling)
- Chart.js (for potential visualizations)
- WebSocket for real-time updates
