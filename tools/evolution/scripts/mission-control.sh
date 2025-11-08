#!/bin/bash
# Mission Control Launcher
# Starts the Textual TUI for Context Foundry Evolution

cd "$(dirname "$0")/../../.."

echo "🚀 Launching Context Foundry Mission Control..."
echo ""

# Check if textual is installed
if ! python3 -c "import textual" 2>/dev/null; then
    echo "❌ Textual not installed"
    echo ""
    echo "Install with:"
    echo "  pip3 install textual"
    echo ""
    exit 1
fi

# Launch mission control
python3 -m tools.evolution.mission_control
