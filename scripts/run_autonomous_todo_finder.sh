#!/usr/bin/env bash
#
# Kickstart Evolution System - Find and Implement First TODO
# Uses Claude CLI directly to spawn autonomous build
#

set -euo pipefail

echo "🚀 KICKSTARTING EVOLUTION SYSTEM - AUTONOMOUS TODO IMPLEMENTATION"
echo "=================================================================="
echo ""

# Task description
TASK=$(cat <<'EOF'
Kickstart Evolution System Perpetual Loop with Claude CLI delegation!

Find the first TODO in Context Foundry and implement it:
1. Scan codebase for TODOs/FIXMEs
2. Implement the highest priority improvement
3. Add tests if needed
4. Create a PR

This will test the full autonomous workflow.
EOF
)

# Working directory
WORKING_DIR="/Users/name/homelab/context-foundry"

echo "📋 Task: Find and implement first TODO in Context Foundry"
echo "🎯 Working Directory: $WORKING_DIR"
echo "🔧 Mode: fix_bugs (enhancing existing project)"
echo ""
echo "🔄 Starting autonomous build in background..."
echo ""

# Create log file
LOG_DIR="$HOME/.context-foundry/evolution/logs"
mkdir -p "$LOG_DIR"
LOGFILE="$LOG_DIR/autonomous-todo-$(date +%Y%m%d-%H%M%S).log"

# Build the system prompt (simplified version of orchestrator prompt)
SYSTEM_PROMPT=$(cat <<'PROMPT'
You are the Context Foundry Autonomous Build Orchestrator.

Your mission: Execute a complete autonomous build workflow to enhance an existing project.

WORKFLOW PHASES:
1. SCOUT: Scan codebase for TODOs/FIXMEs and analyze priority
2. ARCHITECT: Plan the implementation approach
3. BUILDER: Implement the solution
4. TESTER: Run tests and validate (self-healing loop enabled, max 2 iterations)
5. DEPLOY: Create PR with changes

MODE: fix_bugs (enhancing existing codebase)
WORKING_DIRECTORY: /Users/name/homelab/context-foundry
GITHUB_REPO: context-foundry
TEST_LOOP: enabled (max 2 iterations)

Execute each phase sequentially. If tests fail, go back to ARCHITECT/BUILDER to fix.
When complete, create a PR with your improvements.

BEGIN AUTONOMOUS EXECUTION NOW.
PROMPT
)

# Run Claude CLI in background
nohup claude --print \
  --permission-mode bypassPermissions \
  --strict-mcp-config \
  --settings '{"thinkingMode": "off"}' \
  --system-prompt "$SYSTEM_PROMPT" \
  "$TASK" \
  > "$LOGFILE" 2>&1 &

PID=$!

echo "✅ Autonomous build spawned!"
echo "   PID: $PID"
echo "   Log: $LOGFILE"
echo ""
echo "🔄 What happens next:"
echo "  1. Scout agent scans codebase for TODOs/FIXMEs"
echo "  2. Architect agent plans the implementation"
echo "  3. Builder agent implements the solution"
echo "  4. Tester agent runs tests (with self-healing loop)"
echo "  5. Deploy agent creates PR automatically"
echo ""
echo "📊 Monitor progress:"
echo "   tail -f $LOGFILE"
echo ""
echo "🎯 This tests the full autonomous Evolution System workflow!"
echo ""
echo "⏸️  To stop the build:"
echo "   kill $PID"
