#!/bin/bash
# Install Context Foundry Evolution Daemon as System Service

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "📦 Installing Context Foundry Evolution Daemon as system service..."

# Detect OS
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS - use launchd
    echo "🍎 Detected macOS - installing launchd service"

    # Detect Python location (prefer Homebrew python3)
    if [ -f "/opt/homebrew/bin/python3" ]; then
        PYTHON_PATH="/opt/homebrew/bin/python3"
    elif [ -f "/usr/local/bin/python3" ]; then
        PYTHON_PATH="/usr/local/bin/python3"
    else
        PYTHON_PATH="/usr/bin/python3"
    fi

    echo "🐍 Using Python: $PYTHON_PATH ($(${PYTHON_PATH} --version))"
    echo "📂 Project root: $PROJECT_ROOT"

    PLIST_PATH="$HOME/Library/LaunchAgents/dev.contextfoundry.evolution.plist"

    # Ensure logs directory exists
    mkdir -p "$HOME/.context-foundry/evolution/logs"

    # Unload existing service if running
    if launchctl list | grep -q "dev.contextfoundry.evolution"; then
        echo "⏹️  Stopping existing service..."
        launchctl unload "$PLIST_PATH" 2>/dev/null || true
        sleep 2
    fi

    cat > "$PLIST_PATH" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>dev.contextfoundry.evolution</string>

    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON_PATH</string>
        <string>$PROJECT_ROOT/tools/evolution/daemon.py</string>
        <string>start</string>
        <string>--foreground</string>
    </array>

    <key>WorkingDirectory</key>
    <string>$PROJECT_ROOT</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
        <key>HOME</key>
        <string>$HOME</string>
    </dict>

    <key>StandardOutPath</key>
    <string>$HOME/.context-foundry/evolution/logs/launchd-stdout.log</string>

    <key>StandardErrorPath</key>
    <string>$HOME/.context-foundry/evolution/logs/launchd-stderr.log</string>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
        <key>Crashed</key>
        <true/>
    </dict>

    <key>ThrottleInterval</key>
    <integer>60</integer>

    <key>HardResourceLimits</key>
    <dict>
        <key>NumberOfFiles</key>
        <integer>1024</integer>
    </dict>
</dict>
</plist>
PLIST

    echo "✅ Created plist: $PLIST_PATH"

    # Validate plist syntax
    if plutil -lint "$PLIST_PATH" >/dev/null 2>&1; then
        echo "✅ Plist syntax valid"
    else
        echo "❌ Invalid plist syntax!"
        plutil -lint "$PLIST_PATH"
        exit 1
    fi

    # Load service
    echo "🚀 Loading service..."
    launchctl load "$PLIST_PATH"

    # Wait a moment for service to start
    sleep 3

    # Check if service is running
    if launchctl list | grep -q "dev.contextfoundry.evolution"; then
        echo "✅ Service is running!"
        launchctl list | grep dev.contextfoundry.evolution
    else
        echo "❌ Service failed to start. Check logs:"
        echo "   tail -f $HOME/.context-foundry/evolution/logs/launchd-stderr.log"
        exit 1
    fi

    echo ""
    echo "📋 Service Management Commands:"
    echo "   Status:  launchctl list | grep contextfoundry"
    echo "   Stop:    launchctl unload $PLIST_PATH"
    echo "   Start:   launchctl load $PLIST_PATH"
    echo "   Restart: launchctl unload $PLIST_PATH && launchctl load $PLIST_PATH"
    echo ""
    echo "📋 Log Locations:"
    echo "   Daemon:  tail -f ~/.context-foundry/evolution/logs/daemon.log"
    echo "   Stdout:  tail -f ~/.context-foundry/evolution/logs/launchd-stdout.log"
    echo "   Stderr:  tail -f ~/.context-foundry/evolution/logs/launchd-stderr.log"
    echo ""
    echo "📊 Monitor: bash tools/evolution/scripts/watch-evolution.sh"
    
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux - use systemd
    echo "🐧 Detected Linux - installing systemd service"

    # Detect Python location
    PYTHON_PATH=$(which python3 || echo "/usr/bin/python3")
    echo "🐍 Using Python: $PYTHON_PATH ($(${PYTHON_PATH} --version))"
    echo "📂 Project root: $PROJECT_ROOT"

    SERVICE_PATH="$HOME/.config/systemd/user/context-foundry-evolution.service"
    mkdir -p "$(dirname "$SERVICE_PATH")"

    # Ensure logs directory exists
    mkdir -p "$HOME/.context-foundry/evolution/logs"

    cat > "$SERVICE_PATH" << SERVICE
[Unit]
Description=Context Foundry Evolution Daemon
After=network.target
Documentation=https://github.com/context-foundry/context-foundry

[Service]
Type=simple
ExecStart=$PYTHON_PATH $PROJECT_ROOT/tools/evolution/daemon.py start --foreground
WorkingDirectory=$PROJECT_ROOT
Environment="PATH=/usr/local/bin:/usr/bin:/bin"
Environment="HOME=$HOME"

# Restart policy
Restart=on-failure
RestartSec=60

# Resource limits
LimitNOFILE=1024

# Logging (journald)
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
SERVICE

    echo "✅ Created service file: $SERVICE_PATH"

    # Reload systemd and enable service
    systemctl --user daemon-reload
    systemctl --user enable context-foundry-evolution.service
    systemctl --user start context-foundry-evolution.service

    # Wait a moment for service to start
    sleep 2

    # Check status
    if systemctl --user is-active --quiet context-foundry-evolution.service; then
        echo "✅ Service is running!"
        systemctl --user status context-foundry-evolution.service --no-pager
    else
        echo "❌ Service failed to start. Check logs:"
        echo "   journalctl --user -u context-foundry-evolution.service -n 50"
        exit 1
    fi

    echo ""
    echo "📋 Service Management Commands:"
    echo "   Status:  systemctl --user status context-foundry-evolution"
    echo "   Stop:    systemctl --user stop context-foundry-evolution"
    echo "   Start:   systemctl --user start context-foundry-evolution"
    echo "   Restart: systemctl --user restart context-foundry-evolution"
    echo "   Logs:    journalctl --user -u context-foundry-evolution -f"
    echo ""
    echo "📋 Log Locations:"
    echo "   Daemon:  tail -f ~/.context-foundry/evolution/logs/daemon.log"
    echo "   System:  journalctl --user -u context-foundry-evolution -f"
    echo ""
    echo "📊 Monitor: bash tools/evolution/scripts/watch-evolution.sh"
    
else
    echo "❌ Unsupported OS: $OSTYPE"
    echo "Manual installation required"
    exit 1
fi

echo "✅ Service installation complete!"
