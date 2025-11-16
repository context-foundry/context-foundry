#!/bin/bash

# Start Glass Pane Dashboard (backend + frontend)
# This script ensures both services are running and stays persistent

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting Glass Pane Dashboard...${NC}"
echo ""

# Kill any existing instances
echo -e "${YELLOW}Cleaning up existing processes...${NC}"
pkill -f "uvicorn main:app.*3001" 2>/dev/null || true
pkill -f "vite.*glass-pane" 2>/dev/null || true
sleep 2

# Start backend
echo -e "${GREEN}Starting backend on port 3001...${NC}"
cd "$BACKEND_DIR"

if [ ! -d "venv" ]; then
    echo -e "${RED}Virtual environment not found. Creating...${NC}"
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

# Start backend in background
nohup uvicorn main:app --host 0.0.0.0 --port 3001 --reload > /tmp/glass-pane-backend.log 2>&1 &
BACKEND_PID=$!

# Wait for backend to start
echo "Waiting for backend to start..."
for i in {1..10}; do
    if curl -s http://localhost:3001/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Backend started (PID: $BACKEND_PID)${NC}"
        break
    fi
    if [ $i -eq 10 ]; then
        echo -e "${RED}✗ Backend failed to start${NC}"
        exit 1
    fi
    sleep 1
done

# Start frontend
echo -e "${GREEN}Starting frontend on port 5173...${NC}"
cd "$FRONTEND_DIR"

if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}Installing frontend dependencies...${NC}"
    npm install
fi

# Start frontend in background
nohup npm run dev > /tmp/glass-pane-frontend.log 2>&1 &
FRONTEND_PID=$!

# Wait for frontend to start
echo "Waiting for frontend to start..."
for i in {1..15}; do
    if curl -s http://localhost:5173 > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Frontend started (PID: $FRONTEND_PID)${NC}"
        break
    fi
    if [ $i -eq 15 ]; then
        echo -e "${RED}✗ Frontend failed to start${NC}"
        exit 1
    fi
    sleep 1
done

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
echo -e "${GREEN}Glass Pane Dashboard is running!${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════${NC}"
echo ""
echo -e "  Frontend: ${GREEN}http://localhost:5173${NC}"
echo -e "  Backend:  ${GREEN}http://localhost:3001${NC}"
echo ""
echo -e "  Backend PID:  $BACKEND_PID"
echo -e "  Frontend PID: $FRONTEND_PID"
echo ""
echo -e "  Backend logs:  tail -f /tmp/glass-pane-backend.log"
echo -e "  Frontend logs: tail -f /tmp/glass-pane-frontend.log"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
echo ""

# Keep script running and monitor processes
trap 'echo -e "\n${YELLOW}Stopping Glass Pane...${NC}"; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0' INT TERM

# Monitor processes
while true; do
    if ! kill -0 $BACKEND_PID 2>/dev/null; then
        echo -e "${RED}Backend process died! Restarting...${NC}"
        cd "$BACKEND_DIR"
        source venv/bin/activate
        nohup uvicorn main:app --host 0.0.0.0 --port 3001 --reload > /tmp/glass-pane-backend.log 2>&1 &
        BACKEND_PID=$!
    fi

    if ! kill -0 $FRONTEND_PID 2>/dev/null; then
        echo -e "${RED}Frontend process died! Restarting...${NC}"
        cd "$FRONTEND_DIR"
        nohup npm run dev > /tmp/glass-pane-frontend.log 2>&1 &
        FRONTEND_PID=$!
    fi

    sleep 5
done
