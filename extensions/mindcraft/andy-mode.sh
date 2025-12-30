#!/bin/bash
# Andy Mode Switcher - Easy way to change Andy's orchestrator mode
# Usage: ./andy-mode.sh [builder|helper|defender|stop|status]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CF_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
LOG_FILE="/tmp/orch_log.txt"
SCREEN_NAME="andy-orchestrator"

show_help() {
    echo "Andy Mode Switcher"
    echo "=================="
    echo ""
    echo "Usage: $0 <mode>"
    echo ""
    echo "Modes:"
    echo "  builder   - Village building mode (assigns building projects, gives supplies)"
    echo "  helper    - Helper mode (follows players, assists with tasks)"
    echo "  defender  - Defender mode (combat, protection, mob hunting)"
    echo "  stop      - Stop the orchestrator"
    echo "  status    - Check if orchestrator is running"
    echo ""
    echo "Examples:"
    echo "  $0 builder    # Start Andy in builder mode"
    echo "  $0 helper     # Switch Andy to helper mode"
    echo "  $0 stop       # Stop the orchestrator"
}

stop_orchestrator() {
    if screen -list | grep -q "$SCREEN_NAME"; then
        echo "Stopping current orchestrator..."
        screen -S "$SCREEN_NAME" -X quit 2>/dev/null
        sleep 1
        echo "Orchestrator stopped."
    else
        echo "No orchestrator running."
    fi
}

start_orchestrator() {
    local mode=$1

    # Validate mode
    if [[ ! "$mode" =~ ^(builder|helper|defender)$ ]]; then
        echo "Error: Invalid mode '$mode'"
        echo "Valid modes: builder, helper, defender"
        exit 1
    fi

    # Stop existing orchestrator
    stop_orchestrator

    echo "Starting Andy in $mode mode..."

    # Clear log file
    > "$LOG_FILE"

    # Start in screen session
    cd "$CF_DIR"
    screen -dmS "$SCREEN_NAME" bash -c "python -m extensions.mindcraft.orchestrator --mode $mode 2>&1 | tee -a $LOG_FILE"

    sleep 2

    if screen -list | grep -q "$SCREEN_NAME"; then
        echo "Orchestrator started in $mode mode!"
        echo ""
        echo "Commands:"
        echo "  View logs:    tail -f $LOG_FILE"
        echo "  Attach:       screen -r $SCREEN_NAME"
        echo "  Stop:         $0 stop"
    else
        echo "Error: Failed to start orchestrator"
        echo "Check logs: cat $LOG_FILE"
        exit 1
    fi
}

check_status() {
    if screen -list | grep -q "$SCREEN_NAME"; then
        echo "Orchestrator is RUNNING"
        echo ""
        echo "Recent log:"
        tail -5 "$LOG_FILE" 2>/dev/null || echo "(no logs yet)"
    else
        echo "Orchestrator is STOPPED"
    fi
}

# Main
case "${1:-}" in
    builder|helper|defender)
        start_orchestrator "$1"
        ;;
    stop)
        stop_orchestrator
        ;;
    status)
        check_status
        ;;
    -h|--help|help)
        show_help
        ;;
    "")
        show_help
        ;;
    *)
        echo "Unknown command: $1"
        echo ""
        show_help
        exit 1
        ;;
esac
