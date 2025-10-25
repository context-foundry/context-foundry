# Codebase Analysis Report

## Project Overview
- **Type**: Python web application (FastAPI + WebSocket)
- **Languages**: Python, HTML, JavaScript
- **Architecture**: Real-time monitoring dashboard with WebSocket updates

## Key Files
- **Entry point**: `tools/livestream/server.py` (FastAPI app with WebSocket)
- **Frontend**: `tools/livestream/dashboard.html` (Single-page dashboard)
- **Metrics Collection**: `tools/livestream/metrics_collector.py` (Background polling service)
- **MCP Client**: `tools/livestream/mcp_client.py` (Reads task status from filesystem)
- **Config**: `tools/livestream/config.py` (Settings and constants)

## Current Issues Identified

### Issue 1: WebSocket Sends Duplicate Stale Data
**Location**: `server.py` lines 301-308
**Problem**: WebSocket loop polls every 1 second and sends status regardless of changes
```python
while True:
    await asyncio.sleep(1)
    status = monitor.get_session_status(session_id)
    await websocket.send_json({"type": "status", "data": status})
```
**Root Cause**: No change detection - always sends same data every second

### Issue 2: Dashboard Doesn't Auto-Refresh Enhanced Metrics
**Location**: `dashboard.html` lines 491-523
**Problem**: `updateEnhancedMetrics()` function defined but never called automatically
**Current Behavior**: Enhanced metrics only load on manual refresh
**Expected**: Auto-refresh every 5 seconds

### Issue 3: No Filesystem Watching for current-phase.json
**Location**: `metrics_collector.py` entire file
**Problem**: Collector only polls checkpoints, not live `.context-foundry/current-phase.json` files
**Root Cause**: Designed for checkpoint-based sessions, not real-time file watching

### Issue 4: MetricsCollector Watches Wrong Files
**Location**: `metrics_collector.py` lines 97-123
**Problem**: Only reads from `checkpoints/ralph/*` directory
**Missing**: Direct watching of `.context-foundry/current-phase.json` in active builds

### Issue 5: Dashboard Receives WebSocket But Doesn't Refresh Metrics
**Location**: `dashboard.html` lines 674-690
**Problem**: WebSocket `onmessage` handler only updates basic status
**Missing**: Trigger for `updateEnhancedMetrics()` when WebSocket message arrives

## Architecture Analysis

### Current Flow (Broken):
1. Orchestrator writes `.context-foundry/current-phase.json`
2. Orchestrator calls `/api/phase-update` (works)
3. Server broadcasts to WebSocket clients (works)
4. Dashboard receives WebSocket message (works)
5. Dashboard updates basic UI (works)
6. **BROKEN**: Enhanced metrics never refresh
7. **BROKEN**: MetricsCollector never sees current-phase.json

### Desired Flow (Fixed):
1. Orchestrator writes `.context-foundry/current-phase.json`
2. **NEW**: MetricsCollector detects file change via watchdog
3. **NEW**: MetricsCollector reads updated phase data
4. **NEW**: MetricsCollector stores metrics in database
5. Orchestrator calls `/api/phase-update` (existing)
6. Server broadcasts to WebSocket clients (existing)
7. Dashboard receives WebSocket message (existing)
8. **NEW**: Dashboard triggers `updateEnhancedMetrics()` on WebSocket message
9. **NEW**: Enhanced metrics auto-refresh every 5s

## Code to Modify

### Files to Change:
1. **server.py** - Add change detection to WebSocket loop
2. **dashboard.html** - Add auto-refresh for enhanced metrics
3. **metrics_collector.py** - Add filesystem watching for current-phase.json
4. **mcp_client.py** - Improve real-time data fetching from current-phase.json

### Approach:

#### Fix 1: Change Detection in WebSocket (server.py)
- Store last sent data hash
- Compare before sending
- Only send if changed

#### Fix 2: Dashboard Auto-Refresh (dashboard.html)
- Call `updateEnhancedMetrics()` when WebSocket receives update
- Add setInterval for periodic refresh (5s)
- Add "last updated" timestamps

#### Fix 3: Filesystem Watching (metrics_collector.py)
- Add `watchdog` library for file monitoring
- Watch for `.context-foundry/current-phase.json` changes
- Trigger metric collection on file change

#### Fix 4: Real-time Data Fetching (mcp_client.py)
- Prioritize reading from current-phase.json
- Fall back to checkpoints only if live data unavailable
- Add file modification time checking

## Dependencies
- **Add**: `watchdog` library for filesystem monitoring

## Risks
- WebSocket performance if many clients connected
- Filesystem watching might miss rapid updates
- Dashboard refresh could cause UI flicker

## Testing Plan
1. Start livestream server
2. Run autonomous build in another terminal
3. Watch .context-foundry/current-phase.json updates
4. Verify dashboard updates in real-time
5. Check enhanced metrics refresh every 5s
6. Verify no duplicate/stale data sent
