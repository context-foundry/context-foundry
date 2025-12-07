# Context Foundry Desktop - Development Summary

## Overview

Context Foundry Desktop (CFD) is a Tauri 2.0 native desktop application that provides a visual dashboard for the Context Foundry Daemon. It wraps the existing web dashboard and adds native OS integration.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Tauri App                            │
│  ┌─────────────────────┐  ┌─────────────────────────┐  │
│  │   Rust Backend      │  │   React Frontend        │  │
│  │   (src-tauri/)      │  │   (tools/dashboard/)    │  │
│  │                     │  │                         │  │
│  │  - DaemonManager    │  │  - Vite + React 18      │  │
│  │  - API client       │  │  - Zustand state        │  │
│  │  - System tray      │  │  - Tailwind CSS         │  │
│  │  - IPC commands     │  │  - SSE for real-time    │  │
│  └─────────────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────┐
│              CF Daemon (Python)                         │
│  Port 8420: Dashboard static files                      │
│  Port 8421: HTTP JSON API                               │
└─────────────────────────────────────────────────────────┘
```

## Key Files

### Tauri Backend (`apps/context-foundry-desktop/src-tauri/`)

| File | Purpose |
|------|---------|
| `src/lib.rs` | App entry, state management, startup daemon check |
| `src/daemon.rs` | DaemonManager - start/stop/restart daemon process |
| `src/api.rs` | DaemonApi - HTTP client for daemon endpoints |
| `src/tray.rs` | System tray icon and menu |
| `src/commands.rs` | Tauri IPC commands exposed to frontend |
| `tauri.conf.json` | Tauri configuration, CSP, build settings |
| `Cargo.toml` | Rust dependencies |

### React Frontend (`tools/dashboard/`)

| File | Purpose |
|------|---------|
| `src/api/client.ts` | API client with CORS handling, job_id→id transform |
| `src/api/sse.ts` | Server-Sent Events manager for real-time updates |
| `src/stores/jobs.ts` | Zustand store for job state |
| `src/components/Sidebar/` | Job list, filters, job cards |
| `src/components/JobDetail/` | Job details, phase timeline, actions |
| `src/types/index.ts` | TypeScript type definitions |

### Daemon HTTP API (`context_foundry/daemon/http_api.py`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check with uptime |
| `/jobs` | GET | List jobs with filters |
| `/jobs/{id}` | GET | Job details |
| `/jobs/{id}/tree` | GET | Phase/task tree view |
| `/jobs/{id}/timeline` | GET | Event timeline |
| `/jobs/{id}/gates` | GET | Gate status |
| `/metrics` | GET | Metrics snapshot |
| `/config` | GET | Provider configuration |
| `/agents` | GET/POST | Agent configuration |

## Critical Fixes Applied

### 1. API Path Mismatch
**Problem:** Frontend called `/api/jobs`, daemon served `/jobs`
**Solution:** Added `/api/` prefix stripping in `http_api.py`:
```python
# In do_GET and do_POST:
if path.startswith("/api/"):
    path = path[4:]  # Remove "/api" prefix
```

### 2. CORS Preflight
**Problem:** OPTIONS requests returned 501
**Solution:** Added `do_OPTIONS` handler with proper headers:
```python
def do_OPTIONS(self) -> None:
    self.send_response(200)
    self.send_header("Access-Control-Allow-Origin", "*")
    self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
    self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-CF-Auth")
    self.send_header("Access-Control-Max-Age", "86400")
    self.send_header("Content-Length", "0")
    self.end_headers()
```

### 3. Job ID Field Mismatch
**Problem:** API returns `job_id`, frontend expects `id`
**Solution:** Transform in `client.ts`:
```typescript
function transformJob(apiJob: Record<string, unknown>): Job {
  return {
    ...apiJob,
    id: (apiJob.job_id || apiJob.id) as string,
  } as Job;
}
```

### 4. Tauri 2.x Shell Plugin Config
**Problem:** Invalid `scope` field in shell plugin config
**Solution:** Removed `scope`, kept only `"open": true` in `tauri.conf.json`

### 5. Missing Emitter Trait
**Problem:** `emit()` method not found on AppHandle
**Solution:** Added `use tauri::Emitter;` to `lib.rs` and `tray.rs`

## Running in Development

```bash
# Terminal 1: Start dashboard dev server
cd /Users/name/homelab/context-foundry/tools/dashboard
npm run dev  # Runs on port 5174

# Terminal 2: Start Tauri dev mode
cd /Users/name/homelab/context-foundry/apps/context-foundry-desktop
npm run tauri:dev

# Ensure daemon is running
./tools/cfd status
./tools/cfd start  # If not running
```

## Building for Release

```bash
cd /Users/name/homelab/context-foundry/apps/context-foundry-desktop
npm run tauri:build
# Output: src-tauri/target/release/bundle/
```

**Known Issue:** Release build may crash due to missing icons. Add icons to `src-tauri/icons/` before building.

## Port Configuration

| Port | Service | Purpose |
|------|---------|---------|
| 5174 | Vite dev server | Frontend hot reload (dev only) |
| 8420 | CF Daemon | Dashboard static files |
| 8421 | CF Daemon | HTTP JSON API |

## Tauri IPC Commands

Commands defined in `commands.rs`, invokable from frontend:

```typescript
// From React:
import { invoke } from '@tauri-apps/api/core';

await invoke('check_daemon_status');
await invoke('start_daemon');
await invoke('stop_daemon');
await invoke('get_jobs');
await invoke('get_job', { jobId: 'uuid' });
```

## Frontend API Detection

The frontend detects Tauri environment and adjusts API base URL:

```typescript
const isTauri = typeof window !== 'undefined' && '__TAURI__' in window;
const API_BASE = isTauri ? 'http://127.0.0.1:8421' : '';
```

- **In Tauri:** Direct HTTP to daemon API (port 8421)
- **In Browser:** Relative paths (proxied by Vite or daemon)

## State Management

Zustand stores in `tools/dashboard/src/stores/`:

- `jobs.ts` - Job list, selection, filters, SSE connection
- `settings.ts` - UI preferences
- `approvals.ts` - Pending approval management
- `sidekick.ts` - Sidekick chat state

## Real-time Updates

SSE connection to daemon for live updates:
- Job status changes
- Phase transitions
- Metrics updates
- Heartbeats

Managed by `src/api/sse.ts` with auto-reconnect.

## Future Development Notes

### Adding New Endpoints
1. Add handler in `http_api.py` `do_GET` or `do_POST`
2. Add client function in `tools/dashboard/src/api/client.ts`
3. Transform `job_id` → `id` if returning job data

### Adding Tauri Commands
1. Define command in `src-tauri/src/commands.rs`
2. Register in `lib.rs` `invoke_handler`
3. Call from frontend via `invoke()`

### System Tray Actions
Defined in `src-tauri/src/tray.rs` - add menu items and handlers there.

### CSP (Content Security Policy)
Configured in `tauri.conf.json` under `app.security.csp`. Must allow:
- `connect-src` for API calls to 127.0.0.1:8421
- `img-src` for images
- `style-src 'unsafe-inline'` for Tailwind

## Dependencies

### Rust (Cargo.toml)
- tauri 2.x with tray-icon feature
- tauri-plugin-shell 2.x
- reqwest (HTTP client)
- tokio (async runtime)
- serde/serde_json (serialization)

### Frontend (package.json in tools/dashboard)
- React 18
- Vite
- Zustand
- Tailwind CSS
- @tauri-apps/api

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Load failed" | Check daemon running, CORS headers, API paths |
| CORS errors | Verify `do_OPTIONS` handler, check CSP |
| `job.id` undefined | Ensure `transformJob()` applied to API responses |
| Tray not showing | Need valid icon in `src-tauri/icons/` |
| Release crash | Check icons exist, run in dev mode first |
| Port conflict | Check nothing else on 8420/8421/5174 |
