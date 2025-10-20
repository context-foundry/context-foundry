#!/bin/bash
#
# Start Context Foundry Livestream Server
# Launches server and opens dashboard in browser
#

set -euo pipefail

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
PORT="${LIVESTREAM_PORT:-8080}"
HOST="${LIVESTREAM_HOST:-0.0.0.0}"
USE_NGROK="${USE_NGROK:-false}"

echo -e "${GREEN}🎥 Context Foundry Livestream${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo -e "${YELLOW}❌ python3 not found${NC}"
    exit 1
fi

# Check for required packages
echo -e "${BLUE}📦 Checking dependencies...${NC}"

if ! python3 -c "import fastapi" 2>/dev/null; then
    echo -e "${YELLOW}⚠️  FastAPI not installed${NC}"
    echo "Installing dependencies..."
    pip3 install fastapi uvicorn websockets requests
fi

# Initialize enhanced metrics database
echo -e "${BLUE}💾 Initializing metrics database...${NC}"
cd "$(dirname "$0")/livestream"
python3 -c "
import sys
try:
    from metrics_db import get_db
    db = get_db()
    print('✅ Database initialized at:', db.db_path)
except Exception as e:
    print('⚠️  Database initialization skipped:', e)
"
cd - > /dev/null

# Kill any existing server on this port
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Port $PORT in use, attempting to free it...${NC}"
    lsof -ti:$PORT | xargs kill -9 2>/dev/null || true
    sleep 1
fi

# Start server in background
echo -e "${BLUE}🚀 Starting server on port $PORT...${NC}"

cd "$(dirname "$0")/livestream"

python3 server.py > /tmp/livestream.log 2>&1 &
SERVER_PID=$!

# Wait for server to start
echo -e "${BLUE}⏳ Waiting for server to start...${NC}"
sleep 2

# Check if server started
if ! kill -0 $SERVER_PID 2>/dev/null; then
    echo -e "${YELLOW}❌ Server failed to start${NC}"
    echo "Check logs: tail -f /tmp/livestream.log"
    exit 1
fi

# Local URL
LOCAL_URL="http://localhost:$PORT"

echo -e "\n${GREEN}✅ Server started successfully!${NC}"
echo -e "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${BLUE}📡 Local URL:${NC}  $LOCAL_URL"
echo -e "${BLUE}🔄 Enhanced metrics polling: 3-5 seconds${NC}"
echo -e "${BLUE}💾 Metrics database: ~/.context-foundry/metrics.db${NC}"

# Start ngrok if requested
NGROK_URL=""
if [ "$USE_NGROK" = "true" ]; then
    if command -v ngrok &> /dev/null; then
        echo -e "${BLUE}🌐 Starting ngrok tunnel...${NC}"

        ngrok http $PORT > /dev/null &
        NGROK_PID=$!

        # Wait for ngrok to start
        sleep 3

        # Get ngrok URL
        NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | python3 -c "import sys, json; print(json.load(sys.stdin)['tunnels'][0]['public_url'])" 2>/dev/null || echo "")

        if [ -n "$NGROK_URL" ]; then
            echo -e "${BLUE}🌍 Public URL:${NC}  $NGROK_URL"

            # Generate QR code if possible
            if command -v qrencode &> /dev/null; then
                echo -e "\n${BLUE}📱 QR Code for mobile:${NC}"
                qrencode -t ANSI "$NGROK_URL"
            fi
        fi
    else
        echo -e "${YELLOW}⚠️  ngrok not installed (skipping)${NC}"
        echo "Install with: brew install ngrok"
    fi
fi

echo -e "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${BLUE}📊 API Docs:${NC}  http://localhost:$PORT/docs"
echo -e "${BLUE}📝 Logs:${NC}      tail -f /tmp/livestream.log"
echo -e "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Open browser
if command -v open &> /dev/null; then
    # macOS
    echo -e "${BLUE}🌐 Opening browser...${NC}"
    open "$LOCAL_URL"
elif command -v xdg-open &> /dev/null; then
    # Linux
    xdg-open "$LOCAL_URL"
elif command -v start &> /dev/null; then
    # Windows
    start "$LOCAL_URL"
fi

echo ""
echo -e "${GREEN}✨ Dashboard is running!${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
echo ""

# Cleanup function
cleanup() {
    echo -e "\n${YELLOW}🛑 Shutting down...${NC}"

    if [ -n "${SERVER_PID:-}" ]; then
        kill $SERVER_PID 2>/dev/null || true
    fi

    if [ -n "${NGROK_PID:-}" ]; then
        kill $NGROK_PID 2>/dev/null || true
    fi

    echo -e "${GREEN}✅ Stopped${NC}"
    exit 0
}

trap cleanup SIGINT SIGTERM

# Keep script running
wait $SERVER_PID
