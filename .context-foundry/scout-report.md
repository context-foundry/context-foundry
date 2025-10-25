# Scout Report: Multi-Agent Monitoring Dashboard Enhancement

## Executive Summary
Enhance Context Foundry's livestream dashboard to support advanced multi-agent monitoring, per-agent token tracking, multi-instance support, and comprehensive geek stats. The current dashboard provides basic single-session monitoring; the goal is production-ready, robust visualization of parallel autonomous builds with complete visibility into agent-level operations.

## Key Requirements Analysis

### 1. Multi-Agent Monitoring Panel
**Current State**: Dashboard shows single session with basic phase tracking
**Target**: Display all running agents (Scout, Architect, Builder 1-N, Tester) with individual status, progress, and metrics
**Complexity**: MEDIUM - Requires agent instance tracking, real-time updates per agent
**Implementation Path**: Add agent_instances table, WebSocket agent events, UI components per agent

### 2. Horizontal Gradient Progress Bars
**Current State**: Basic progress bars exist (context, tasks)
**Target**: Beautiful horizontal bars per agent with smooth gradients (green→blue in-progress, gray idle, green complete)
**Complexity**: LOW - Primarily CSS/JavaScript frontend work
**Implementation Path**: CSS gradient definitions, JavaScript animation handlers, per-agent progress calculation

### 3. Per-Agent Token Tracking
**Current State**: Global token tracking only
**Target**: Each agent shows current token count, budget percentage, visual warnings (green <50%, yellow 50-75%, red >75%)
**Complexity**: MEDIUM - Requires parsing agent output for token usage, storing per-agent metrics
**Implementation Path**: Enhance metrics collector to parse agent logs, store agent-level token data, display gauges per agent

### 4. Multi-Instance Support
**Current State**: Session selector shows one instance at a time
**Target**: Simultaneous monitoring of multiple Context Foundry builds in expandable cards
**Complexity**: HIGH - Complex state management, needs instance discovery, concurrent WebSocket connections
**Implementation Path**: Instance registry, multi-WebSocket management, accordion/card UI for instances

### 5. Enhanced Time Tracking
**Current State**: Session-level elapsed time
**Target**: Per-agent elapsed time, estimated remaining, percentage complete, phase-level time tracking
**Complexity**: MEDIUM - Requires timestamp tracking per agent/phase, estimation algorithms
**Implementation Path**: Agent start/end timestamps, phase duration calculation, progress estimation based on phase

### 6. Phase Tracking Dashboard
**Current State**: Single phase indicator
**Target**: Visual progress bar per phase (Scout→Architect→Builder→Test→Deploy), time per phase, success/failure indicators
**Complexity**: MEDIUM - Needs phase history, duration tracking, status per phase
**Implementation Path**: Phase timeline component, phase duration storage, visual indicators (✓/✗ per phase)

### 7. Real-Time Updates
**Current State**: WebSocket working for sessions
**Target**: Smooth WebSocket updates for all new metrics without flickering
**Complexity**: LOW - Enhance existing WebSocket handlers
**Implementation Path**: Add agent-level WebSocket events, throttle updates (max 10/sec), validate data before rendering

### 8. Geek Stats Section
**Target**: Total agents spawned, parallel vs sequential breakdown, token efficiency, API calls per agent, iteration speed
**Complexity**: MEDIUM - Requires comprehensive metrics collection
**Implementation Path**: Analytics queries on metrics_db, display panel with stats, chart visualizations

### 9. Modern UI/UX
**Target**: Dark mode optimized, smooth animations, responsive, no broken graphs, error handling, loading states
**Complexity**: LOW-MEDIUM - Frontend polish work
**Implementation Path**: CSS transitions, loading spinners, error boundaries, data validation

### 10. Backend Enhancements
**Target**: Track per-agent metrics, WebSocket messages for agents, API endpoints for multi-instance query, parse orchestrator output
**Complexity**: HIGH - Core infrastructure work
**Implementation Path**: New database schema, API endpoints, output parsing logic, WebSocket event system

## Technology Stack Decision

**Backend**: Python FastAPI (existing) - ✅ Keep, add new endpoints
**Frontend**: Vanilla JS + Tailwind CSS + Chart.js (existing) - ✅ Keep, no new dependencies
**Database**: SQLite (existing) - ✅ Keep, add agent_instances table
**WebSocket**: FastAPI WebSockets (existing) - ✅ Keep, enhance with agent events
**Testing**: Playwright (add new) - ⚠️ Need for E2E browser tests

**Rationale**: Minimize new dependencies, build on existing infrastructure, maintain backwards compatibility

## Critical Architecture Recommendations

### 1. Agent Instance Tracking Schema
```sql
CREATE TABLE agent_instances (
    id INTEGER PRIMARY KEY,
    session_id TEXT,
    agent_id TEXT UNIQUE,
    agent_type TEXT,
    status TEXT,
    phase TEXT,
    progress_percent REAL,
    tokens_used INTEGER,
    tokens_limit INTEGER,
    start_time TEXT,
    end_time TEXT,
    parent_agent_id TEXT,
    FOREIGN KEY (session_id) REFERENCES tasks(task_id)
)
```

### 2. WebSocket Event System
- `agent_spawned`: New agent started (sends agent_id, agent_type, phase)
- `agent_progress`: Progress update (sends agent_id, progress_percent, tokens_used)
- `agent_completed`: Agent finished (sends agent_id, success, duration)
- `agent_failed`: Agent error (sends agent_id, error_message)

### 3. Output Parsing Strategy
Parse orchestrator logs to detect:
- Agent spawning: `Starting [Agent Type] agent...`
- Progress updates: Token usage from Claude output
- Completion: `Agent [Type] completed in X seconds`

### 4. UI Component Structure
```
Dashboard
├── Instance Selector (dropdown or cards)
├── Multi-Agent Panel (per instance)
│   ├── Agent Card (Scout)
│   │   ├── Status badge
│   │   ├── Horizontal gradient progress bar
│   │   ├── Token gauge
│   │   └── Elapsed time
│   ├── Agent Card (Architect)
│   ├── Agent Card (Builder 1)
│   └── Agent Card (Builder 2)
├── Phase Timeline (all phases)
├── Geek Stats Panel
└── Live Logs
```

### 5. Data Validation & Error Handling
- Validate all WebSocket data before rendering
- Check for null/undefined before updating DOM
- Gracefully handle missing agent data
- Loading states while fetching
- Fallback to "No data" when appropriate

## Main Challenges & Mitigations

### Challenge 1: Parsing Orchestrator Output
**Risk**: Output format may vary, parsing could fail
**Mitigation**: Robust regex patterns, fallback mechanisms, log warnings but continue

### Challenge 2: Performance with Many Agents
**Risk**: Dozens of WebSocket updates per second could lag browser
**Mitigation**: Throttle updates (max 10/sec per agent), batch updates, use requestAnimationFrame for smooth animations

### Challenge 3: State Management Complexity
**Risk**: Multiple instances × multiple agents = complex state synchronization
**Mitigation**: Single source of truth (server-side), stateless frontend updates, clear data flow

### Challenge 4: Backwards Compatibility
**Risk**: Breaking existing single-agent monitoring
**Mitigation**: Feature detection, graceful degradation, keep existing APIs intact

### Challenge 5: Testing Coverage
**Risk**: Broken graphs, missing error handling
**Mitigation**: Comprehensive test suite:
- Unit tests for API endpoints
- Integration tests for WebSocket events
- E2E tests with Playwright to catch UI bugs
- Validation tests for data rendering

## Testing Approach

### Unit Tests (pytest)
- `test_agent_instances_api` - Test CRUD operations for agents
- `test_multi_instance_discovery` - Test instance listing
- `test_agent_metrics_collection` - Test metrics gathering

### Integration Tests
- `test_websocket_agent_events` - Test WebSocket message flow
- `test_agent_progress_updates` - Test real-time progress updates

### E2E Tests (Playwright)
- `test_multi_agent_display` - Verify all agents render correctly
- `test_gradient_progress_bars` - Verify animations work
- `test_no_broken_graphs` - Verify all charts render without errors
- `test_multi_instance_cards` - Verify instance cards expand/collapse
- `test_error_handling` - Verify graceful degradation when data missing

### Validation Tests
- Check all DOM elements exist before updating
- Validate data types before rendering
- Ensure no console errors during operation

## Timeline Estimate
- Scout: 15 minutes ✅
- Architect: 30 minutes
- Builder: 90 minutes (complex changes)
- Test: 30 minutes (comprehensive testing)
- Deploy: 10 minutes
**Total: ~2.5-3 hours**

## Success Criteria
1. ✅ Multi-agent panel displays all running agents with individual progress bars
2. ✅ Horizontal gradient progress bars animate smoothly
3. ✅ Per-agent token tracking with color-coded warnings
4. ✅ Multi-instance support with expandable cards
5. ✅ Phase tracking dashboard with timeline visualization
6. ✅ Geek stats section with comprehensive metrics
7. ✅ Real-time WebSocket updates without flickering
8. ✅ No broken graphs or console errors
9. ✅ Comprehensive test coverage (>80%)
10. ✅ Backwards compatible with existing sessions
