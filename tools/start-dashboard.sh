#!/bin/bash
# Start CF Daemon + Vite Dashboard with a single command
#
# Usage: ./tools/start-dashboard.sh
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "🚀 Starting Context Foundry Dashboard..."

# Start daemon if not already running
if ! "$PROJECT_ROOT/tools/cfd" status >/dev/null 2>&1; then
    echo "📦 Starting CF Daemon..."
    "$PROJECT_ROOT/tools/cfd" start
    sleep 1
else
    echo "✅ CF Daemon already running"
fi

# Show daemon status
"$PROJECT_ROOT/tools/cfd" status

# Start Vite dev server
echo ""
echo "🌐 Starting Vite Dashboard on http://localhost:5174"
echo "   (Press Ctrl+C to stop)"
echo ""

cd "$PROJECT_ROOT/tools/dashboard"
npm run dev
