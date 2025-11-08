#!/bin/bash
# Stop Context Foundry Evolution Daemon

set -e

echo "🛑 Stopping Context Foundry Evolution Daemon..."

# Check if daemon is running
if [ ! -f "$HOME/.context-foundry/evolution/daemon.pid" ]; then
    echo "❌ Daemon is not running"
    exit 1
fi

PID=$(cat "$HOME/.context-foundry/evolution/daemon.pid")

if ! ps -p $PID > /dev/null 2>&1; then
    echo "❌ Daemon is not running (stale PID file)"
    rm "$HOME/.context-foundry/evolution/daemon.pid"
    exit 1
fi

# Send SIGTERM
kill -TERM $PID

echo "✅ Sent stop signal to daemon (PID: $PID)"
echo "⏳ Waiting for graceful shutdown..."

# Wait up to 30 seconds
for i in {1..30}; do
    if ! ps -p $PID > /dev/null 2>&1; then
        echo "✅ Daemon stopped successfully"
        exit 0
    fi
    sleep 1
done

echo "⚠️  Daemon did not stop gracefully, sending SIGKILL"
kill -KILL $PID
echo "✅ Daemon killed"
