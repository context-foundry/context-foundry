#!/usr/bin/env python3
"""
FastAPI Server for MCP Log Monitor
Real-time log streaming with WebSocket support
"""

import argparse
from pathlib import Path
from typing import Set, Dict
from collections import deque
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import Config
from .parsers import LogParser, LogEntry
from .log_watcher import LogFileWatcher


# Create FastAPI app
app = FastAPI(title="MCP Log Monitor", version="1.0.0")

# CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
config: Config = None
log_parser: LogParser = None
log_watcher: LogFileWatcher = None
broadcaster: "LogBroadcaster" = None


class LogBroadcaster:
    """
    Manage WebSocket connections and broadcast log updates.

    Uses pub/sub pattern with channels for different log sources.
    """

    def __init__(self, max_buffer_size: int = 100):
        self.clients: Dict[str, Set[WebSocket]] = {}
        self.message_buffers: Dict[str, deque] = {}
        self.max_buffer_size = max_buffer_size

    async def connect(self, websocket: WebSocket, channel: str = "all"):
        """Register new client connection"""
        await websocket.accept()

        if channel not in self.clients:
            self.clients[channel] = set()
            self.message_buffers[channel] = deque(maxlen=self.max_buffer_size)

        self.clients[channel].add(websocket)

        # Send buffered messages to new client
        await self._send_buffered(websocket, channel)

        print(
            f"Client connected to channel: {channel} (total: {len(self.clients[channel])})"
        )

    async def disconnect(self, websocket: WebSocket, channel: str = "all"):
        """Remove client connection"""
        if channel in self.clients:
            self.clients[channel].discard(websocket)

            if not self.clients[channel]:
                del self.clients[channel]
                del self.message_buffers[channel]

        print(f"Client disconnected from channel: {channel}")

    async def broadcast(self, entry: LogEntry, channel: str = "all"):
        """
        Broadcast log entry to all clients in channel.

        Args:
            entry: LogEntry to broadcast
            channel: Channel name (default: "all")
        """
        message = entry.to_dict()

        # Buffer message
        if channel not in self.message_buffers:
            self.message_buffers[channel] = deque(maxlen=self.max_buffer_size)
        self.message_buffers[channel].append(message)

        # Broadcast to "all" channel
        await self._send_to_clients("all", message)

        # Broadcast to server-specific channel
        if entry.server != "all":
            await self._send_to_clients(entry.server, message)

    async def _send_to_clients(self, channel: str, message: dict):
        """Send message to all clients in channel"""
        if channel not in self.clients:
            return

        # Collect disconnected clients
        disconnected = []

        for client in self.clients[channel]:
            try:
                await client.send_json(message)
            except Exception:
                disconnected.append(client)

        # Remove disconnected clients
        for client in disconnected:
            self.clients[channel].discard(client)

    async def _send_buffered(self, websocket: WebSocket, channel: str):
        """Send buffered messages to newly connected client"""
        if channel in self.message_buffers:
            for message in self.message_buffers[channel]:
                try:
                    await websocket.send_json(message)
                except Exception:
                    break


# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    global config, log_parser, log_watcher, broadcaster

    # Load configuration
    config_file = Path(__file__).parent.parent / "config.yaml"
    config = Config.load(config_file if config_file.exists() else None)

    # Initialize parser
    log_parser = LogParser()

    # Initialize broadcaster
    broadcaster = LogBroadcaster(max_buffer_size=config.performance.max_buffer_size)

    # Initialize watcher
    log_watcher = LogFileWatcher(
        parser=log_parser,
        broadcast_callback=broadcaster.broadcast,
        debounce_ms=config.performance.debounce_ms,
    )

    # Start watching log sources
    enabled_sources = config.get_enabled_sources()
    if enabled_sources:
        log_watcher.start_watching(enabled_sources)
        print(f"Watching {len(enabled_sources)} log sources")
    else:
        print("Warning: No log sources configured")


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    global log_watcher

    if log_watcher:
        log_watcher.stop_watching()

    print("Log monitor stopped")


# Health check
@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


# List available servers
@app.get("/api/servers")
async def list_servers():
    """List available MCP servers"""
    servers = []

    for source in config.get_enabled_sources():
        servers.append(
            {"name": source.name, "enabled": source.enabled, "paths": source.paths}
        )

    return {"servers": servers}


# WebSocket endpoint
@app.websocket("/ws/logs/{channel}")
async def websocket_logs(websocket: WebSocket, channel: str):
    """
    WebSocket endpoint for real-time log streaming.

    Args:
        channel: Channel name ("all" or specific server name)
    """
    await broadcaster.connect(websocket, channel)

    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        await broadcaster.disconnect(websocket, channel)


# Serve frontend (production mode)
@app.get("/")
async def serve_frontend():
    """Serve frontend in production mode"""
    frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
    index_file = frontend_dist / "index.html"

    if index_file.exists():
        return FileResponse(index_file)
    else:
        return HTMLResponse("""
        <html>
            <head><title>MCP Log Monitor</title></head>
            <body>
                <h1>MCP Log Monitor</h1>
                <p>Frontend not built. Run in development mode:</p>
                <pre>cd frontend && npm run dev</pre>
                <p>Or build for production:</p>
                <pre>cd frontend && npm run build</pre>
            </body>
        </html>
        """)


# Mount static files (production mode)
frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")


if __name__ == "__main__":
    import uvicorn

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=5000, help="Port to bind to")
    parser.add_argument("--production", action="store_true", help="Production mode")
    args = parser.parse_args()

    print(f"Starting MCP Log Monitor on {args.host}:{args.port}")

    if args.production:
        print("Running in PRODUCTION mode")
    else:
        print("Running in DEVELOPMENT mode")
        print("Frontend should be started separately: cd frontend && npm run dev")

    uvicorn.run(
        "server:app", host=args.host, port=args.port, reload=not args.production
    )
