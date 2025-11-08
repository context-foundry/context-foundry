#!/bin/bash
# Context Foundry Evolution Daemon - Service Management Helper
# Provides convenient commands for managing the daemon service

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Detect OS and set service name
if [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
    SERVICE_LABEL="dev.contextfoundry.evolution"
    PLIST_PATH="$HOME/Library/LaunchAgents/${SERVICE_LABEL}.plist"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="linux"
    SERVICE_NAME="context-foundry-evolution"
else
    echo -e "${RED}❌ Unsupported OS: $OSTYPE${NC}"
    exit 1
fi

# Helper functions
is_service_installed() {
    if [[ "$OS" == "macos" ]]; then
        [ -f "$PLIST_PATH" ]
    else
        systemctl --user list-unit-files | grep -q "$SERVICE_NAME"
    fi
}

is_service_running() {
    if [[ "$OS" == "macos" ]]; then
        launchctl list | grep -q "$SERVICE_LABEL"
    else
        systemctl --user is-active --quiet "$SERVICE_NAME"
    fi
}

# Command implementations
cmd_status() {
    echo -e "${BLUE}📊 Service Status${NC}"
    echo ""

    if ! is_service_installed; then
        echo -e "${YELLOW}⚠️  Service not installed${NC}"
        echo "Run: $0 install"
        exit 1
    fi

    if [[ "$OS" == "macos" ]]; then
        if is_service_running; then
            echo -e "${GREEN}✅ Service is running${NC}"
            launchctl list | grep "$SERVICE_LABEL"
        else
            echo -e "${RED}❌ Service is not running${NC}"
        fi
        echo ""
        echo "Plist: $PLIST_PATH"
    else
        systemctl --user status "$SERVICE_NAME" --no-pager || true
    fi

    echo ""
    echo -e "${BLUE}📝 Recent Daemon Log (last 10 lines):${NC}"
    if [ -f "$HOME/.context-foundry/evolution/logs/daemon.log" ]; then
        tail -10 "$HOME/.context-foundry/evolution/logs/daemon.log"
    else
        echo "No daemon log found"
    fi
}

cmd_start() {
    echo -e "${BLUE}🚀 Starting service...${NC}"

    if ! is_service_installed; then
        echo -e "${RED}❌ Service not installed${NC}"
        echo "Run: $0 install"
        exit 1
    fi

    if is_service_running; then
        echo -e "${YELLOW}⚠️  Service is already running${NC}"
        exit 0
    fi

    if [[ "$OS" == "macos" ]]; then
        launchctl load "$PLIST_PATH"
    else
        systemctl --user start "$SERVICE_NAME"
    fi

    sleep 2

    if is_service_running; then
        echo -e "${GREEN}✅ Service started successfully${NC}"
    else
        echo -e "${RED}❌ Failed to start service${NC}"
        exit 1
    fi
}

cmd_stop() {
    echo -e "${BLUE}⏹️  Stopping service...${NC}"

    if ! is_service_installed; then
        echo -e "${YELLOW}⚠️  Service not installed${NC}"
        exit 0
    fi

    if ! is_service_running; then
        echo -e "${YELLOW}⚠️  Service is not running${NC}"
        exit 0
    fi

    if [[ "$OS" == "macos" ]]; then
        launchctl unload "$PLIST_PATH"
    else
        systemctl --user stop "$SERVICE_NAME"
    fi

    sleep 2

    if ! is_service_running; then
        echo -e "${GREEN}✅ Service stopped successfully${NC}"
    else
        echo -e "${RED}❌ Failed to stop service${NC}"
        exit 1
    fi
}

cmd_restart() {
    echo -e "${BLUE}🔄 Restarting service...${NC}"
    cmd_stop
    sleep 1
    cmd_start
}

cmd_logs() {
    LOG_TYPE="${1:-daemon}"

    case "$LOG_TYPE" in
        daemon)
            LOG_FILE="$HOME/.context-foundry/evolution/logs/daemon.log"
            ;;
        stdout)
            if [[ "$OS" == "macos" ]]; then
                LOG_FILE="$HOME/.context-foundry/evolution/logs/launchd-stdout.log"
            else
                echo "Use 'journalctl --user -u $SERVICE_NAME -f' for stdout on Linux"
                exit 0
            fi
            ;;
        stderr)
            if [[ "$OS" == "macos" ]]; then
                LOG_FILE="$HOME/.context-foundry/evolution/logs/launchd-stderr.log"
            else
                echo "Use 'journalctl --user -u $SERVICE_NAME -f' for stderr on Linux"
                exit 0
            fi
            ;;
        *)
            echo -e "${RED}❌ Unknown log type: $LOG_TYPE${NC}"
            echo "Valid types: daemon, stdout, stderr"
            exit 1
            ;;
    esac

    echo -e "${BLUE}📋 Tailing $LOG_TYPE log...${NC}"
    echo "File: $LOG_FILE"
    echo ""

    if [ -f "$LOG_FILE" ]; then
        tail -f "$LOG_FILE"
    else
        echo -e "${YELLOW}⚠️  Log file not found: $LOG_FILE${NC}"
        exit 1
    fi
}

cmd_install() {
    echo -e "${BLUE}📦 Installing service...${NC}"
    bash "$SCRIPT_DIR/install_service.sh"
}

cmd_uninstall() {
    echo -e "${BLUE}🗑️  Uninstalling service...${NC}"

    if ! is_service_installed; then
        echo -e "${YELLOW}⚠️  Service not installed${NC}"
        exit 0
    fi

    # Stop if running
    if is_service_running; then
        cmd_stop
    fi

    # Remove service file
    if [[ "$OS" == "macos" ]]; then
        rm -f "$PLIST_PATH"
        echo -e "${GREEN}✅ Removed: $PLIST_PATH${NC}"
    else
        SERVICE_PATH="$HOME/.config/systemd/user/${SERVICE_NAME}.service"
        systemctl --user disable "$SERVICE_NAME" 2>/dev/null || true
        rm -f "$SERVICE_PATH"
        systemctl --user daemon-reload
        echo -e "${GREEN}✅ Removed: $SERVICE_PATH${NC}"
    fi

    echo -e "${GREEN}✅ Service uninstalled${NC}"
}

cmd_monitor() {
    echo -e "${BLUE}📊 Launching Evolution Monitor...${NC}"
    bash "$PROJECT_ROOT/tools/evolution/scripts/watch-evolution.sh"
}

cmd_help() {
    cat << EOF
${BLUE}Context Foundry Evolution Daemon - Service Management${NC}

${YELLOW}Usage:${NC}
    $0 <command> [options]

${YELLOW}Commands:${NC}
    ${GREEN}status${NC}       Show service status and recent logs
    ${GREEN}start${NC}        Start the daemon service
    ${GREEN}stop${NC}         Stop the daemon service
    ${GREEN}restart${NC}      Restart the daemon service
    ${GREEN}logs${NC} [type]  Tail logs (types: daemon, stdout, stderr)
    ${GREEN}install${NC}      Install the daemon as a system service
    ${GREEN}uninstall${NC}    Remove the daemon service
    ${GREEN}monitor${NC}      Launch the Evolution Monitor dashboard
    ${GREEN}help${NC}         Show this help message

${YELLOW}Examples:${NC}
    $0 status                 # Check if daemon is running
    $0 start                  # Start the daemon
    $0 logs                   # Tail daemon.log
    $0 logs stderr            # Tail error log
    $0 monitor                # Launch dashboard

${YELLOW}Log Locations:${NC}
    Daemon:  ~/.context-foundry/evolution/logs/daemon.log
    Stdout:  ~/.context-foundry/evolution/logs/launchd-stdout.log (macOS)
    Stderr:  ~/.context-foundry/evolution/logs/launchd-stderr.log (macOS)

${YELLOW}Direct Commands (advanced):${NC}
EOF

    if [[ "$OS" == "macos" ]]; then
        cat << EOF
    launchctl list | grep contextfoundry
    launchctl load $PLIST_PATH
    launchctl unload $PLIST_PATH
EOF
    else
        cat << EOF
    systemctl --user status $SERVICE_NAME
    systemctl --user start $SERVICE_NAME
    systemctl --user stop $SERVICE_NAME
    journalctl --user -u $SERVICE_NAME -f
EOF
    fi
}

# Main command router
COMMAND="${1:-help}"

case "$COMMAND" in
    status)
        cmd_status
        ;;
    start)
        cmd_start
        ;;
    stop)
        cmd_stop
        ;;
    restart)
        cmd_restart
        ;;
    logs)
        shift
        cmd_logs "$@"
        ;;
    install)
        cmd_install
        ;;
    uninstall)
        cmd_uninstall
        ;;
    monitor)
        cmd_monitor
        ;;
    help|--help|-h)
        cmd_help
        ;;
    *)
        echo -e "${RED}❌ Unknown command: $COMMAND${NC}"
        echo ""
        cmd_help
        exit 1
        ;;
esac
