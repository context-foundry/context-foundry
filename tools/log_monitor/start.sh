#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🚀 Starting MCP Log Monitor"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 not found"
    echo "Please install Python 3.10 or higher"
    exit 1
fi

# Check Node.js
if ! command -v node &> /dev/null; then
    echo "❌ Error: Node.js not found"
    echo "Please install Node.js 16 or higher"
    exit 1
fi

# Check if venv exists
if [ ! -d "../../venv" ]; then
    echo "📦 Creating virtual environment..."
    cd ../..
    python3 -m venv venv
    cd tools/log_monitor
fi

# Activate venv
source ../../venv/bin/activate

# Install backend dependencies
echo "📦 Installing backend dependencies..."
pip install -q -r requirements.txt

# Install frontend dependencies
if [ ! -d "frontend/node_modules" ]; then
    echo "📦 Installing frontend dependencies..."
    cd frontend
    npm install
    cd ..
fi

# Check mode
MODE="${LOG_MONITOR_MODE:-development}"

if [ "$MODE" = "production" ]; then
    echo "🏗️  Building frontend for production..."
    cd frontend
    npm run build
    cd ..

    echo ""
    echo "🚀 Starting server in PRODUCTION mode..."
    python3 backend/server.py --production
else
    echo "🚀 Starting backend server..."
    python3 backend/server.py &
    BACKEND_PID=$!

    echo "🚀 Starting frontend dev server..."
    cd frontend
    npm run dev &
    FRONTEND_PID=$!
    cd ..

    # Wait for servers to start
    sleep 3

    echo ""
    echo "✅ MCP Log Monitor is running!"
    echo ""
    echo "📊 Backend:  http://localhost:5000"
    echo "🎨 Frontend: http://localhost:5173"
    echo ""
    echo "Press Ctrl+C to stop both servers"
    echo ""

    # Open browser
    if command -v open &> /dev/null; then
        open http://localhost:5173
    elif command -v xdg-open &> /dev/null; then
        xdg-open http://localhost:5173
    fi

    # Trap Ctrl+C
    trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT

    # Wait
    wait
fi
