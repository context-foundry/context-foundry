#!/bin/bash

# Glass Pane Deployment Script
# Usage: ./deploy.sh [production|staging]

set -e

ENVIRONMENT=${1:-production}
DEPLOY_USER=${DEPLOY_USER:-www-data}
BACKEND_DIR=${BACKEND_DIR:-/opt/glass-pane}
FRONTEND_DIR=${FRONTEND_DIR:-/var/www/glass-pane}

echo "=================================="
echo "Glass Pane Deployment Script"
echo "Environment: $ENVIRONMENT"
echo "=================================="

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Please run as root or with sudo${NC}"
    exit 1
fi

# Step 1: Build Frontend
echo -e "\n${YELLOW}[1/8] Building frontend...${NC}"
cd frontend
npm install
npm run build
echo -e "${GREEN}Frontend built successfully${NC}"

# Step 2: Copy Frontend Files
echo -e "\n${YELLOW}[2/8] Deploying frontend files...${NC}"
mkdir -p $FRONTEND_DIR
rm -rf $FRONTEND_DIR/dist
cp -r dist $FRONTEND_DIR/
chown -R $DEPLOY_USER:$DEPLOY_USER $FRONTEND_DIR
echo -e "${GREEN}Frontend files deployed${NC}"

# Step 3: Setup Backend Directory
echo -e "\n${YELLOW}[3/8] Setting up backend...${NC}"
mkdir -p $BACKEND_DIR
cp -r ../backend/* $BACKEND_DIR/
cd $BACKEND_DIR

# Step 4: Create Python Virtual Environment
echo -e "\n${YELLOW}[4/8] Setting up Python environment...${NC}"
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
echo -e "${GREEN}Python environment ready${NC}"

# Step 5: Copy Environment File
echo -e "\n${YELLOW}[5/8] Configuring environment...${NC}"
if [ ! -f ".env.production" ]; then
    cp ../deployment/.env.production .env.production
    echo -e "${YELLOW}Created .env.production - please edit with your configuration${NC}"
fi

# Step 6: Setup systemd Service
echo -e "\n${YELLOW}[6/8] Installing systemd service...${NC}"
cp ../deployment/glass-pane.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable glass-pane
echo -e "${GREEN}Systemd service installed${NC}"

# Step 7: Setup NGINX
echo -e "\n${YELLOW}[7/8] Configuring NGINX...${NC}"
cp ../deployment/nginx.conf /etc/nginx/sites-available/glass-pane
if [ ! -f "/etc/nginx/sites-enabled/glass-pane" ]; then
    ln -s /etc/nginx/sites-available/glass-pane /etc/nginx/sites-enabled/
fi

# Test NGINX configuration
nginx -t
echo -e "${GREEN}NGINX configured${NC}"

# Step 8: Restart Services
echo -e "\n${YELLOW}[8/8] Restarting services...${NC}"
systemctl restart glass-pane
systemctl reload nginx

# Wait a moment for service to start
sleep 2

# Check service status
if systemctl is-active --quiet glass-pane; then
    echo -e "${GREEN}Glass Pane service is running${NC}"
else
    echo -e "${RED}Warning: Glass Pane service failed to start${NC}"
    echo "Check logs with: journalctl -u glass-pane -n 50"
fi

if systemctl is-active --quiet nginx; then
    echo -e "${GREEN}NGINX is running${NC}"
else
    echo -e "${RED}Warning: NGINX failed to start${NC}"
fi

echo -e "\n${GREEN}=================================="
echo "Deployment Complete!"
echo "==================================${NC}"
echo ""
echo "Service status: systemctl status glass-pane"
echo "Service logs:   journalctl -u glass-pane -f"
echo "NGINX logs:     tail -f /var/log/nginx/glass-pane-*.log"
echo ""
echo "Dashboard URL:  https://glass.contextfoundry.dev"
echo ""
