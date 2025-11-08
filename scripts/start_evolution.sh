#!/bin/bash
# Start Context Foundry Evolution Daemon

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "🚀 Starting Context Foundry Evolution Daemon..."

# Check if daemon is already running
if [ -f "$HOME/.context-foundry/evolution/daemon.pid" ]; then
    PID=$(cat "$HOME/.context-foundry/evolution/daemon.pid")
    if ps -p $PID > /dev/null 2>&1; then
        echo "❌ Daemon is already running (PID: $PID)"
        exit 1
    fi
fi

# Start daemon
cd "$PROJECT_ROOT"
python3 tools/evolution/daemon.py start --foreground &

echo "✅ Daemon started"
echo "📊 Dashboard: http://localhost:8765"
echo "📡 REST API: http://localhost:8766"
echo "🔌 WebSocket: ws://localhost:8767"
