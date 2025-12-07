# Glass Pane Dashboard - Setup Guide

Real-time monitoring dashboard for Context Foundry builds.

## Quick Start

### Easy Way (Recommended)

```bash
cd {CF_ROOT}/tools/glass-pane
./start-glass-pane.sh
```

This script will:
- Start both backend (port 3001) and frontend (port 5173)
- Monitor processes and auto-restart if they crash
- Display logs and status

Then open: **http://localhost:5173**

Press `Ctrl+C` to stop both services.

### Manual Start

**Backend:**
```bash
cd backend
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 3001 --reload
```

**Frontend:**
```bash
cd frontend
npm run dev
```

## Troubleshooting

### "No jobs found" Issue

If you see "no jobs found" frequently:

1. **Use the startup script** - It monitors and restarts services automatically:
   ```bash
   ./start-glass-pane.sh
   ```

2. **Check backend health**: http://localhost:3001/health

3. **Check logs**:
   ```bash
   tail -f /tmp/glass-pane-backend.log
   tail -f /tmp/glass-pane-frontend.log
   ```

### Connection Issues

The dashboard now has automatic retry with exponential backoff. If you still see connection errors:

1. Check that both services are running:
   ```bash
   ps aux | grep -E "uvicorn.*3001|vite.*glass-pane"
   ```

2. Restart using the startup script

3. Clear browser cache and reload

### Port Conflicts

If port 3001 or 5173 are already in use:

```bash
# Kill existing processes
pkill -f "uvicorn.*3001"
pkill -f "vite.*glass-pane"

# Restart
./start-glass-pane.sh
```

## Architecture

- **Backend**: FastAPI (Python) on port 3001
  - REST API for job data
  - SSE (Server-Sent Events) for real-time updates
  - SQLite database at `~/.context-foundry/cfd/jobs.db`

- **Frontend**: React + TypeScript + Vite on port 5173
  - Vite dev server with proxy to backend
  - Real-time updates via SSE
  - Auto-retry on network errors

## Features

- **Real-time monitoring** of CF daemon builds
- **Phase pipeline** visualization
- **Live logs** streaming
- **File browser** for build artifacts
- **Markdown viewer** for reports (scout, architect, test, deploy logs)
- **Deployment status** with error details
- **Auto-reconnection** if backend restarts

## Recent Improvements

- ✅ Auto-retry with exponential backoff for network errors
- ✅ Process monitoring and auto-restart
- ✅ Better error handling and logging
- ✅ Health monitor to detect backend issues
- ✅ Deployment status and error display
- ✅ Build artifacts browser (deploy-log.md, main-builder.done, etc.)
