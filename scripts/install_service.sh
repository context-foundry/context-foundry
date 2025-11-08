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
    
    PLIST_PATH="$HOME/Library/LaunchAgents/dev.contextfoundry.evolution.plist"
    
    cat > "$PLIST_PATH" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>dev.contextfoundry.evolution</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>$PROJECT_ROOT/tools/evolution/daemon.py</string>
        <string>start</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardErrorPath</key>
    <string>$HOME/.context-foundry/evolution/logs/daemon-error.log</string>
    <key>StandardOutPath</key>
    <string>$HOME/.context-foundry/evolution/logs/daemon-out.log</string>
</dict>
</plist>
PLIST
    
    # Load service
    launchctl load "$PLIST_PATH"
    
    echo "✅ Installed launchd service: $PLIST_PATH"
    echo "🔧 To uninstall: launchctl unload $PLIST_PATH"
    
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux - use systemd
    echo "🐧 Detected Linux - installing systemd service"
    
    SERVICE_PATH="$HOME/.config/systemd/user/context-foundry-evolution.service"
    mkdir -p "$(dirname "$SERVICE_PATH")"
    
    cat > "$SERVICE_PATH" << SERVICE
[Unit]
Description=Context Foundry Evolution Daemon
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 $PROJECT_ROOT/tools/evolution/daemon.py start --foreground
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
SERVICE
    
    # Reload systemd and enable service
    systemctl --user daemon-reload
    systemctl --user enable context-foundry-evolution.service
    systemctl --user start context-foundry-evolution.service
    
    echo "✅ Installed systemd service: $SERVICE_PATH"
    echo "🔧 To check status: systemctl --user status context-foundry-evolution"
    echo "🔧 To stop: systemctl --user stop context-foundry-evolution"
    
else
    echo "❌ Unsupported OS: $OSTYPE"
    echo "Manual installation required"
    exit 1
fi

echo "✅ Service installation complete!"
