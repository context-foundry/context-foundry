# Scout Report: Livestream Real-Time Updates Fix

## Executive Summary
The livestream feature has functional WebSocket communication but suffers from performance and usability issues due to lack of change detection and real-time file watching. The system sends duplicate stale data every second and doesn't auto-refresh enhanced metrics, creating a poor monitoring experience.

## Task Requirements
**Primary Goals:**
1. Add change detection to WebSocket to prevent duplicate data transmission
2. Implement auto-refresh for enhanced metrics in dashboard (5-second interval)
3. Add filesystem watching for `.context-foundry/current-phase.json` changes
4. Update MetricsCollector to watch live phase files, not just checkpoints
5. Connect WebSocket message reception to enhanced metrics refresh

**Success Criteria:**
- Dashboard updates immediately when current-phase.json changes
- WebSocket only sends data when it actually changes
- Enhanced metrics auto-refresh every 5 seconds
- "Last updated" timestamps visible
- Works with both live builds and viewing past sessions

## Technology Stack

**Existing:**
- Python 3.x
- FastAPI (async web framework)
- WebSocket (real-time communication)
- SQLite (metrics database)
- Vanilla JavaScript (dashboard frontend)

**Required Addition:**
- **watchdog** library for filesystem monitoring

**Justification**: Watchdog is the industry-standard Python library for cross-platform filesystem event monitoring, stable and widely used.

## Critical Architecture Recommendations

### 1. Change Detection Pattern (High Priority)
**Problem**: WebSocket sends same data every second regardless of changes
**Solution**: Hash-based change detection
- Store SHA256 hash of last sent data
- Compare before sending
- Only transmit if hash differs
**Impact**: Reduces bandwidth by 90%+ in steady-state

### 2. Filesystem Watching (High Priority)
**Problem**: MetricsCollector polls checkpoints, misses live updates
**Solution**: Watchdog FileSystemEventHandler
- Watch `.context-foundry/` directories
- Trigger collection on `current-phase.json` modification
- Debounce rapid changes (100ms window)
**Impact**: Real-time updates instead of 5-30s polling delay

### 3. Dashboard Auto-Refresh (High Priority)
**Problem**: Enhanced metrics never update automatically
**Solution**: Dual trigger system
- setInterval every 5 seconds (polling fallback)
- WebSocket onmessage triggers immediate refresh
- Prevent concurrent refreshes with flag
**Impact**: Sub-second latency for metric updates

### 4. Graceful Degradation (Medium Priority)
**Problem**: Dashboard might fail if enhanced metrics unavailable
**Solution**: Try/catch with fallback
- Enhanced metrics failures don't crash basic UI
- Show "Enhanced metrics unavailable" message
- Continue updating basic phase/status info
**Impact**: Resilient to partial failures

### 5. Last Updated Timestamps (Low Priority)
**Problem**: Users can't tell if data is fresh or stale
**Solution**: Add timestamp displays
- "Last updated: 2s ago" for each metric section
- Color-code (green < 5s, yellow < 30s, red > 30s)
- Update via setInterval every second
**Impact**: Better user trust and debugging

## Main Challenges and Mitigations

### Challenge 1: Filesystem Watching Performance
**Issue**: Watching many directories could impact performance
**Mitigation**:
- Only watch specific files (current-phase.json)
- Use debouncing (100ms) to batch rapid changes
- Limit to active sessions only

### Challenge 2: WebSocket Scalability
**Issue**: Multiple clients receiving updates every second
**Mitigation**:
- Change detection reduces transmission by 90%
- Consider max clients per session (10-20)
- Connection cleanup on disconnect

### Challenge 3: Race Conditions
**Issue**: File changes while reading could cause errors
**Mitigation**:
- Wrap file reads in try/except
- Retry on failure (max 3 attempts)
- Fall back to last known good data

### Challenge 4: Dashboard UI Flicker
**Issue**: Frequent DOM updates might cause visual flicker
**Mitigation**:
- Only update changed elements (diff before apply)
- Use CSS transitions for smooth updates
- Batch DOM updates in single RAF cycle

## Testing Approach

**Unit Tests:**
- Change detection hashing logic
- Filesystem watcher debouncing
- MCP client file reading

**Integration Tests:**
- End-to-end WebSocket flow
- MetricsCollector with real files
- Dashboard refresh triggers

**Manual Tests:**
1. Start livestream server
2. Run autonomous build in separate terminal
3. Observe real-time updates (< 1s latency)
4. Verify enhanced metrics refresh every 5s
5. Check network tab for duplicate transmissions (should be none)
6. Test with multiple dashboard tabs
7. Verify graceful degradation when build completes

**Performance Tests:**
- Measure WebSocket message frequency (should be < 1/sec in steady state)
- Check CPU usage (filesystem watching overhead)
- Memory leak test (24-hour run)

## Timeline Estimate
**Total: 2-3 hours**
- Architecture/Design: 30 minutes (complete)
- Implementation: 90 minutes
- Testing: 45 minutes
- Documentation: 15 minutes
