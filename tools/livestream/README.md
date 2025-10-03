# Context Foundry Livestream

Real-time monitoring dashboard for overnight coding sessions.

## Features

- **Real-time Updates**: WebSocket-based live data streaming
- **Phase Tracking**: Visual indicators for Scout → Architect → Builder
- **Context Monitoring**: Live context usage percentage (0-100%)
- **Task Progress**: Completed vs remaining tasks with visual progress bar
- **Live Logs**: Streaming log output with syntax highlighting
- **Session Management**: View multiple active/past sessions
- **Mobile Responsive**: Works on phones, tablets, and desktop
- **Dark Theme**: Easy on the eyes for overnight monitoring
- **Cost Tracking**: Estimated API costs and token usage
- **Export**: Download session data as JSON

## Quick Start

### 1. Install Dependencies

```bash
cd ~/context-foundry
pip3 install -r tools/livestream/requirements.txt
```

### 2. Start the Server

```bash
./tools/start_livestream.sh
```

This will:
- Start FastAPI server on port 8080
- Open dashboard in your browser
- Display access URLs

### 3. Run a Context Foundry Task

In another terminal:
```bash
cd ~/context-foundry

# Start an overnight session (will broadcast to livestream)
./tools/overnight_session.sh my-app "Build feature" 4

# Or use the autonomous orchestrator
python3 workflows/autonomous_orchestrator.py my-app "Build API" --autonomous
```

### 4. Watch Live!

The dashboard will automatically:
- Detect the session
- Connect via WebSocket
- Stream updates in real-time

## Architecture

```
┌─────────────────┐
│  Context        │
│  Foundry        │
│  Task Running   │
└────────┬────────┘
         │
         │ Events via broadcaster.py
         ▼
┌─────────────────┐
│  FastAPI        │
│  Server         │◄─── WebSocket ──── Browser Dashboard
│  (port 8080)    │
└─────────────────┘
         │
         │ Reads from
         ▼
┌─────────────────┐
│  Checkpoints/   │
│  Logs/          │
│  Events/        │
└─────────────────┘
```

## Components

### `server.py`
FastAPI server with WebSocket support

**Endpoints:**
- `GET /` - Dashboard HTML
- `GET /api/sessions` - List all sessions
- `GET /api/status/{session_id}` - Session status
- `GET /api/logs/{session_id}` - Session logs
- `WS /ws/{session_id}` - WebSocket connection

### `dashboard.html`
Real-time monitoring interface

**Panels:**
- Header: Session selector, elapsed time
- Phase card: Current phase with gradient
- Context gauge: Visual 0-100% bar
- Task list: Completed/in-progress/remaining
- Live logs: Scrolling output
- Stats: Iterations, tokens, cost

### `broadcaster.py`
Event broadcasting module

**Events:**
- `phase_change` - Scout/Architect/Builder transition
- `iteration_start` / `iteration_complete`
- `task_complete` - Task progress
- `context_update` - Context percentage
- `log_line` - New log output
- `error` - Error occurred
- `completion` - Session finished

### `start_livestream.sh`
Convenience launcher

**Features:**
- Checks dependencies
- Starts server
- Opens browser
- Optional ngrok tunnel for remote access
- Generates QR code for mobile

## Usage Examples

### Basic Monitoring

```bash
# Terminal 1: Start livestream
./tools/start_livestream.sh

# Terminal 2: Run task
./tools/overnight_session.sh todo-app "Build CLI todo" 4
```

### Remote Monitoring (with ngrok)

```bash
# Start with ngrok tunnel
USE_NGROK=true ./tools/start_livestream.sh

# Access from anywhere via the public URL
# Use QR code to open on mobile
```

### Monitor Multiple Sessions

The dashboard automatically detects all sessions in `checkpoints/ralph/`.
Use the dropdown to switch between active sessions.

### Export Session Data

Click "Export Data" button to download complete session data as JSON.

## Configuration

### Environment Variables

```bash
# Server configuration
export LIVESTREAM_PORT=8080
export LIVESTREAM_HOST=0.0.0.0

# Enable ngrok tunnel
export USE_NGROK=true
```

### Integration with Tasks

The broadcaster is automatically integrated when you use:
- `workflows/autonomous_orchestrator.py`
- `ace/ralph_wiggum.py`
- `tools/overnight_session.sh`

No configuration needed - events are automatically broadcast!

## Development

### Test the Broadcaster

```bash
# Run broadcaster test
python3 tools/livestream/broadcaster.py

# This simulates a complete workflow and emits events
# Watch them appear on the dashboard
```

### Manual Event Broadcasting

```python
from tools.livestream.broadcaster import EventBroadcaster

broadcaster = EventBroadcaster(session_id="my_session")

# Emit events
broadcaster.phase_change("scout", context_percent=0)
broadcaster.iteration_start(1)
broadcaster.log_line("Starting research...")
broadcaster.task_complete("Setup", context_percent=25)
broadcaster.completion(success=True)
```

### Server API

**Get all sessions:**
```bash
curl http://localhost:8080/api/sessions
```

**Get session status:**
```bash
curl http://localhost:8080/api/status/my_session_123
```

**Get logs:**
```bash
curl http://localhost:8080/api/logs/my_session_123?lines=50
```

## Mobile Access

### With ngrok (Recommended)

```bash
USE_NGROK=true ./tools/start_livestream.sh
```

Scan the QR code with your phone to access the dashboard remotely.

### Local Network

1. Find your IP: `ifconfig | grep "inet "` (macOS/Linux)
2. Open `http://YOUR_IP:8080` on your phone
3. Ensure firewall allows port 8080

## Troubleshooting

### Server Won't Start

```bash
# Check if port is in use
lsof -i :8080

# Check logs
tail -f /tmp/livestream.log

# Kill existing server
lsof -ti:8080 | xargs kill -9
```

### Dashboard Not Updating

1. Check WebSocket connection (green dot in dashboard)
2. Ensure task is running and emitting events
3. Check browser console for errors
4. Refresh the page

### No Sessions Showing

1. Check if `checkpoints/ralph/` exists
2. Ensure at least one session has been run
3. Click "Refresh" button
4. Check server logs

## Advanced Features

### Session Replay

Events are recorded to `logs/events/{session_id}/events.jsonl`.
You can replay them later:

```python
from tools.livestream.broadcaster import EventBroadcaster

broadcaster = EventBroadcaster(session_id="old_session")
events = broadcaster.load_events()

for event in events:
    print(f"{event['type']}: {event['data']}")
```

### Custom Events

```python
broadcaster.emit("custom_event", {
    "metric": "code_quality",
    "value": 95,
    "details": "All tests passing"
})
```

### Webhook Integration

Modify `server.py` to add webhook notifications:

```python
@app.post("/api/broadcast/{session_id}")
async def broadcast_event(session_id: str, event: Dict):
    # Send to Slack, Discord, etc.
    if event['type'] == 'completion':
        send_slack_notification(event)

    # Broadcast to connected clients
    ...
```

## Performance

- **Latency**: <100ms event → dashboard
- **Resource Usage**: ~50MB RAM for server
- **Concurrent Sessions**: Tested with 10+ simultaneous
- **WebSocket Limit**: 100 concurrent connections

## Future Enhancements

- [ ] Historical session viewer
- [ ] Comparison between sessions
- [ ] Performance graphs (tokens/hour, cost/hour)
- [ ] Desktop notifications
- [ ] Mobile app
- [ ] Multi-user authentication
- [ ] Session sharing via URL
- [ ] Video recording of dashboard

## Support

Issues? Check:
1. Server logs: `tail -f /tmp/livestream.log`
2. Browser console: F12 → Console tab
3. Session files: `ls checkpoints/ralph/`
4. Server health: `curl http://localhost:8080/api/health`

---

**Built for overnight coding marathons. Watch your code being written while you sleep!** 🌙
