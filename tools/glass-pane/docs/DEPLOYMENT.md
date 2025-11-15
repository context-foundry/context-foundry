# Glass Pane - Production Deployment Guide

This guide covers deploying Glass Pane to a VPS with NGINX and systemd.

## Prerequisites

- Ubuntu 22.04+ or similar Linux distribution
- Root or sudo access
- Domain name pointing to your server (e.g., glass.contextfoundry.dev)
- SSL certificate (Cloudflare or Let's Encrypt)
- Context Foundry installed on the server

## Server Requirements

### Minimum Specifications

- **CPU**: 2 cores
- **RAM**: 2GB
- **Storage**: 10GB
- **Network**: Stable connection

### Software Dependencies

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install required packages
sudo apt install -y \
    python3.10 \
    python3.10-venv \
    python3-pip \
    nginx \
    git \
    curl

# Install Node.js 18+
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs
```

## Automated Deployment

The easiest way to deploy is using the provided deployment script:

### 1. Clone Repository

```bash
cd /opt
sudo git clone https://github.com/your-org/glass-pane.git
cd glass-pane
```

### 2. Configure Environment

```bash
# Edit production environment file
sudo nano deployment/.env.production
```

Set the following:
```bash
DB_PATH=/home/youruser/.context-foundry/cfd/jobs.db
CORS_ORIGINS=https://glass.contextfoundry.dev
```

### 3. Run Deployment Script

```bash
sudo ./deployment/deploy.sh production
```

The script will:
1. Build the frontend
2. Deploy static files to /var/www/glass-pane
3. Setup backend in /opt/glass-pane
4. Create Python virtual environment
5. Install systemd service
6. Configure NGINX
7. Start all services

### 4. Verify Deployment

```bash
# Check service status
sudo systemctl status glass-pane

# Check logs
sudo journalctl -u glass-pane -n 50

# Test NGINX
sudo nginx -t

# Check if site is accessible
curl https://glass.contextfoundry.dev
```

## Manual Deployment

If you prefer manual deployment or need to customize:

### 1. Build Frontend

```bash
cd frontend
npm install
npm run build
```

### 2. Deploy Frontend

```bash
# Create directory
sudo mkdir -p /var/www/glass-pane

# Copy build files
sudo cp -r dist/* /var/www/glass-pane/

# Set permissions
sudo chown -R www-data:www-data /var/www/glass-pane
```

### 3. Setup Backend

```bash
# Create directory
sudo mkdir -p /opt/glass-pane

# Copy backend files
sudo cp -r backend/* /opt/glass-pane/

# Create virtual environment
cd /opt/glass-pane
sudo python3 -m venv venv

# Install dependencies
sudo venv/bin/pip install -r requirements.txt

# Copy environment file
sudo cp deployment/.env.production /opt/glass-pane/.env.production

# Edit configuration
sudo nano /opt/glass-pane/.env.production
```

### 4. Configure systemd Service

```bash
# Copy service file
sudo cp deployment/glass-pane.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable service
sudo systemctl enable glass-pane

# Start service
sudo systemctl start glass-pane

# Check status
sudo systemctl status glass-pane
```

### 5. Configure NGINX

```bash
# Copy NGINX config
sudo cp deployment/nginx.conf /etc/nginx/sites-available/glass-pane

# Enable site
sudo ln -s /etc/nginx/sites-available/glass-pane /etc/nginx/sites-enabled/

# Test configuration
sudo nginx -t

# Reload NGINX
sudo systemctl reload nginx
```

## SSL Certificate Setup

### Option 1: Cloudflare (Recommended)

If using Cloudflare for DNS:

1. Generate Origin Certificate in Cloudflare dashboard
2. Download certificate and private key
3. Place files:
   ```bash
   sudo mkdir -p /etc/ssl/certs /etc/ssl/private
   sudo cp cloudflare-cert.pem /etc/ssl/certs/glass.contextfoundry.dev.pem
   sudo cp cloudflare-key.pem /etc/ssl/private/glass.contextfoundry.dev.key
   sudo chmod 600 /etc/ssl/private/glass.contextfoundry.dev.key
   ```

### Option 2: Let's Encrypt

```bash
# Install certbot
sudo apt install -y certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d glass.contextfoundry.dev

# Auto-renewal is configured automatically
```

Update NGINX config to use Let's Encrypt certificates:
```nginx
ssl_certificate /etc/letsencrypt/live/glass.contextfoundry.dev/fullchain.pem;
ssl_certificate_key /etc/letsencrypt/live/glass.contextfoundry.dev/privkey.pem;
```

## Monitoring & Maintenance

### Check Service Health

```bash
# Service status
sudo systemctl status glass-pane

# Service logs (live)
sudo journalctl -u glass-pane -f

# Service logs (last 100 lines)
sudo journalctl -u glass-pane -n 100

# NGINX access logs
sudo tail -f /var/log/nginx/glass-pane-access.log

# NGINX error logs
sudo tail -f /var/log/nginx/glass-pane-error.log
```

### Restart Services

```bash
# Restart Glass Pane
sudo systemctl restart glass-pane

# Reload NGINX (no downtime)
sudo systemctl reload nginx

# Restart NGINX (brief downtime)
sudo systemctl restart nginx
```

### Update Deployment

```bash
# Pull latest changes
cd /opt/glass-pane
sudo git pull

# Rebuild frontend
cd frontend
npm install
npm run build

# Deploy frontend
sudo cp -r dist/* /var/www/glass-pane/

# Update backend dependencies
cd /opt/glass-pane
sudo venv/bin/pip install -r requirements.txt

# Restart service
sudo systemctl restart glass-pane
```

### Database Backup

```bash
# Backup Context Foundry database
sudo cp ~/.context-foundry/cfd/jobs.db ~/backups/jobs-$(date +%Y%m%d).db

# Automated daily backup (add to crontab)
0 2 * * * cp ~/.context-foundry/cfd/jobs.db ~/backups/jobs-$(date +\%Y\%m\%d).db
```

## Performance Tuning

### NGINX Worker Processes

Edit `/etc/nginx/nginx.conf`:
```nginx
worker_processes auto;
worker_connections 1024;
```

### Uvicorn Workers

Edit `/etc/systemd/system/glass-pane.service`:
```ini
ExecStart=/opt/glass-pane/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

Restart service:
```bash
sudo systemctl daemon-reload
sudo systemctl restart glass-pane
```

### Enable HTTP/2

Already enabled in provided NGINX config:
```nginx
listen 443 ssl http2;
```

## Security Hardening

### Firewall Configuration

```bash
# Install ufw
sudo apt install -y ufw

# Allow SSH
sudo ufw allow 22/tcp

# Allow HTTP/HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Enable firewall
sudo ufw enable
```

### Restrict Backend Access

The backend should only be accessible via NGINX proxy. Ensure port 8000 is not exposed:

```bash
# Check listening ports
sudo netstat -tlnp | grep 8000

# Should show: 127.0.0.1:8000 (localhost only)
```

### Regular Updates

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Update Python dependencies
cd /opt/glass-pane
sudo venv/bin/pip install --upgrade -r requirements.txt

# Update Node dependencies
cd frontend
npm update
```

## Troubleshooting

### Service won't start

```bash
# Check logs for errors
sudo journalctl -u glass-pane -n 50

# Common issues:
# - Database path incorrect in .env.production
# - Permissions on database file
# - Port 8000 already in use
```

### NGINX 502 Bad Gateway

```bash
# Check if backend is running
sudo systemctl status glass-pane

# Check backend logs
sudo journalctl -u glass-pane -n 50

# Test backend directly
curl http://localhost:8000/api/jobs
```

### SSE connections not working

```bash
# Check NGINX SSE configuration
sudo nginx -T | grep -A 10 "location /sse"

# Ensure proxy_buffering is off
# Ensure Connection header is set to ''
```

### High memory usage

```bash
# Check process memory
ps aux | grep uvicorn

# Reduce workers if needed
sudo nano /etc/systemd/system/glass-pane.service
# Set --workers 1 or 2

sudo systemctl daemon-reload
sudo systemctl restart glass-pane
```

## Rollback Procedure

If deployment fails:

```bash
# Stop new service
sudo systemctl stop glass-pane

# Restore previous build
cd /var/www/glass-pane
sudo rm -rf dist
sudo cp -r /var/backups/glass-pane-dist-previous/* .

# Restore backend
cd /opt/glass-pane
sudo git reset --hard HEAD~1
sudo venv/bin/pip install -r requirements.txt

# Restart service
sudo systemctl start glass-pane
```

## Production Checklist

- [ ] SSL certificate installed and valid
- [ ] Domain DNS pointing to server
- [ ] NGINX configured and tested
- [ ] systemd service enabled and running
- [ ] Firewall configured (ports 80, 443 open)
- [ ] Database path correct in .env.production
- [ ] CORS origins set correctly
- [ ] Logs accessible and rotating
- [ ] Monitoring setup (optional: Prometheus, Grafana)
- [ ] Backup strategy implemented
- [ ] Update procedure documented

## Monitoring (Optional)

### Setup Prometheus + Grafana

For advanced monitoring, you can add Prometheus metrics:

1. Install Prometheus exporter for FastAPI
2. Configure Prometheus to scrape metrics
3. Setup Grafana dashboards for visualization

See Context Foundry monitoring docs for details.

## Support

For deployment issues:
- Check logs: `sudo journalctl -u glass-pane -f`
- Review NGINX logs: `sudo tail -f /var/log/nginx/glass-pane-error.log`
- Test API: `curl http://localhost:8000/docs`
- Open GitHub issue with logs and error details
