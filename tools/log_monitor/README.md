# MCP Log Monitor

Real-time web dashboard for monitoring Model Context Protocol (MCP) server logs with beautiful, interactive visualization.

## Features

✅ **Real-time Log Streaming** - WebSocket-based live updates
✅ **Multi-Server Tabs** - Monitor multiple MCP servers simultaneously
✅ **Advanced Filtering** - Filter by log level, server, search term
✅ **Structured JSON Parsing** - Pretty-print JSON-RPC messages
✅ **Token Usage Metrics** - Track token consumption and costs
✅ **Search with Highlighting** - Find specific log entries instantly
✅ **Dark Mode UI** - Beautiful, modern interface optimized for readability
✅ **Auto-Scroll** - Stay at the latest logs automatically
✅ **Export Capabilities** - Download logs for offline analysis

## Quick Start

### Prerequisites

- **Python 3.10+** (for backend)
- **Node.js 16+** (for frontend)
- **Context Foundry** (or other MCP server generating logs)

### Installation

```bash
# Navigate to log monitor directory
cd tools/log_monitor

# Run the start script (handles all dependencies)
./start.sh
```

That's it! The script will:
1. Create Python virtual environment if needed
2. Install backend dependencies
3. Install frontend dependencies
4. Start both servers
5. Open your browser automatically

### URLs

- **Frontend Dashboard**: http://localhost:5173 (development)
- **Backend API**: http://localhost:5000
- **WebSocket**: ws://localhost:5000/ws/logs/all

## Architecture

```
┌─────────────────────────────────────────┐
│  React Frontend (Port 5173)             │
│  - LogStream component                  │
│  - FilterPanel component                │
│  - ServerTabs component                 │
└────────────┬────────────────────────────┘
             │ WebSocket + REST API
┌────────────▼────────────────────────────┐
│  FastAPI Backend (Port 5000)            │
│  - WebSocket broadcaster                │
│  - Log file watcher (watchdog)          │
│  - Log parsers (MCP, Context Foundry)   │
└────────────┬────────────────────────────┘
             │ File System Monitoring
┌────────────▼────────────────────────────┐
│  Log Files                              │
│  - ~/Library/Logs/Claude/mcp*.log       │
│  - ~/.context-foundry/delegations/      │
│  - ~/.context-foundry/*/build-output-*  │
└─────────────────────────────────────────┘
```

## Usage

### Starting the Dashboard

**Development mode** (hot reload):
```bash
./start.sh
```

**Production mode** (optimized build):
```bash
LOG_MONITOR_MODE=production ./start.sh
```

### Monitoring Logs

1. **Select Server Tab**: Click "All Servers", "Context Foundry", or "Claude Desktop"
2. **Apply Filters**: Use checkboxes to filter by log level (INFO/WARNING/ERROR)
3. **Search**: Type in search box to highlight matching text
4. **View Details**: Click "View JSON data" on any log entry to see structured data
5. **Clear Logs**: Click "Clear Logs" button to reset the view

### Configuration

Edit `config.yaml` to customize:

```yaml
server:
  host: "0.0.0.0"
  port: 5000

log_sources:
  - name: "my-custom-server"
    paths:
      - "~/path/to/logs/*.log"
    enabled: true

performance:
  max_buffer_size: 100
  debounce_ms: 100
```

## Log Format Support

### MCP JSON-RPC Messages

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "autonomous_build_and_deploy",
    "arguments": {...}
  }
}
```

### Token Usage

```json
{
  "usage": {
    "input_tokens": 1523,
    "output_tokens": 847
  }
}
```

### Context Foundry Phase Updates

```json
{
  "current_phase": "Builder",
  "status": "building",
  "progress_detail": "Implementing server.py",
  "test_iteration": 1
}
```

## API Endpoints

### REST API

- `GET /api/health` - Health check
- `GET /api/servers` - List available MCP servers

### WebSocket

- `WS /ws/logs/all` - All servers combined
- `WS /ws/logs/context-foundry` - Context Foundry only
- `WS /ws/logs/claude-desktop` - Claude Desktop only

## Troubleshooting

### Backend Won't Start

**Error**: `ModuleNotFoundError: No module named 'fastapi'`

**Solution**:
```bash
source ../../venv/bin/activate
pip install -r requirements.txt
```

### Frontend Won't Start

**Error**: `sh: npm: command not found`

**Solution**: Install Node.js from https://nodejs.org

### No Logs Appearing

**Check**:
1. Are MCP servers running and generating logs?
2. Are log file paths correct in `config.yaml`?
3. Check console for permission errors
4. Try: `ls ~/Library/Logs/Claude/mcp*.log`

### WebSocket Disconnects

**Check**:
1. Backend server is running on port 5000
2. No firewall blocking WebSocket connections
3. Browser console for error messages

### Port Already in Use

**Change ports**:
```bash
LOG_MONITOR_PORT=5001 ./start.sh
```

Or edit `config.yaml`:
```yaml
server:
  port: 5001
```

## Development

### Backend Development

```bash
# Activate venv
source ../../venv/bin/activate

# Run backend directly
cd backend
python3 server.py

# Run with auto-reload
uvicorn server:app --reload --port 5000
```

### Frontend Development

```bash
cd frontend

# Install dependencies
npm install

# Start dev server with HMR
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

### Adding New Log Sources

1. Edit `config.yaml`:
```yaml
log_sources:
  - name: "my-new-server"
    paths:
      - "~/path/to/logs/*.log"
    enabled: true
```

2. Restart backend server

3. New server will appear in tabs automatically

## Performance

- **Latency**: <100ms from log write to display
- **Throughput**: Handles 1000+ log entries without lag
- **Memory**: ~50MB backend + ~30MB frontend
- **Virtual Scrolling**: Only renders visible log entries

## Tech Stack

**Backend**:
- FastAPI (Web framework)
- uvicorn (ASGI server)
- watchdog (File system monitoring)
- PyYAML (Configuration)

**Frontend**:
- React 18 (UI framework)
- Vite (Build tool)
- Tailwind CSS (Styling)
- WebSocket API (Real-time communication)

## License

MIT License - Part of Context Foundry project

## Credits

Built for Context Foundry autonomous development system.

---

**Need help?** Open an issue on GitHub or check the Context Foundry documentation.
