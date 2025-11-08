#!/bin/bash
# Evolution System Monitor - "Simplicity is the ultimate sophistication"
# Shows all Claude instances and their activity in one clean view

clear
echo "╔════════════════════════════════════════════════════════════════════════════╗"
echo "║                    CONTEXT FOUNDRY EVOLUTION MONITOR                       ║"
echo "╚════════════════════════════════════════════════════════════════════════════╝"
echo ""

# 1. CLAUDE INSTANCES
echo "🤖 CLAUDE INSTANCES"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
CLAUDE_PIDS=$(ps aux | grep " claude " | grep -v "grep\|Claude.app" | awk '{print $2}')
if [ -z "$CLAUDE_PIDS" ]; then
    echo "  No Claude instances running"
else
    echo "  PID    CPU%   MEM(MB)  TIME     STATE    TYPE"
    echo "  ────────────────────────────────────────────────────────────────"
    for pid in $CLAUDE_PIDS; do
        # Check if it's the interactive session (has terminal) or daemon-spawned
        TTY=$(ps -p $pid -o tty= 2>/dev/null)
        if [ "$TTY" = "??" ] || [ "$TTY" = "?" ]; then
            TYPE="daemon"
        else
            TYPE="interactive"
        fi

        ps -p $pid -o pid=,pcpu=,rss=,etime=,state= 2>/dev/null | \
        awk -v type=$TYPE '{printf "  %-6s %-6s %-8.0f %-8s %-8s %s\n", $1, $2"%", $3/1024, $4, $5, type}'
    done
fi
echo ""

# 2. DAEMON STATUS
echo "⚙️  DAEMON STATUS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
DAEMON_PID=$(pgrep -f "tools.evolution.daemon" 2>/dev/null | head -1)
if [ -z "$DAEMON_PID" ]; then
    echo "  ❌ Daemon not running"
else
    echo "  ✅ Running (PID: $DAEMON_PID)"
    tail -3 ~/.context-foundry/evolution/logs/daemon.log 2>/dev/null | sed 's/^/  │ /'
fi
echo ""

# 3. ACTIVE NETWORK CONNECTIONS (for daemon-spawned Claude)
echo "🌐 NETWORK ACTIVITY"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
DAEMON_CLAUDE=$(ps aux | grep " claude " | grep -v "grep\|Claude.app" | awk '{print $2}' | while read pid; do
    TTY=$(ps -p $pid -o tty= 2>/dev/null)
    if [ "$TTY" = "??" ] || [ "$TTY" = "?" ]; then
        echo $pid
    fi
done | head -1)

if [ -n "$DAEMON_CLAUDE" ]; then
    CONN=$(lsof -p $DAEMON_CLAUDE -a -i 2>/dev/null | grep ESTABLISHED | tail -1)
    if [ -n "$CONN" ]; then
        echo "  ✅ Claude (PID $DAEMON_CLAUDE) connected to Anthropic API"
    else
        echo "  ⏸️  Claude (PID $DAEMON_CLAUDE) idle (no active connections)"
    fi
else
    echo "  No daemon-spawned Claude instances"
fi
echo ""

# 4. RECENT FILE CHANGES
echo "📝 RECENT FILE CHANGES (last 60 seconds)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
RECENT=$(find . -type f -mmin -1 -not -path "*/.git/*" -not -path "*/.pytest_cache/*" -not -path "*/node_modules/*" 2>/dev/null)
if [ -z "$RECENT" ]; then
    echo "  No recent changes"
else
    echo "$RECENT" | head -5 | sed 's/^/  ✏️  /'
    COUNT=$(echo "$RECENT" | wc -l | tr -d ' ')
    if [ "$COUNT" -gt 5 ]; then
        echo "  ... and $((COUNT - 5)) more files"
    fi
fi
echo ""

# 5. GIT STATUS
echo "📦 GIT STATUS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
cd /Users/name/homelab/context-foundry 2>/dev/null
GIT_STATUS=$(git status --short 2>/dev/null)
if [ -z "$GIT_STATUS" ]; then
    echo "  ✅ Working tree clean"
else
    echo "$GIT_STATUS" | head -10 | sed 's/^/  /'
    COUNT=$(echo "$GIT_STATUS" | wc -l | tr -d ' ')
    if [ "$COUNT" -gt 10 ]; then
        echo "  ... and $((COUNT - 10)) more files"
    fi
fi
echo ""

# 6. OPEN PRS
echo "🔀 OPEN PULL REQUESTS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
cd /Users/name/homelab/context-foundry 2>/dev/null
PRS=$(gh pr list --state open --json number,title --limit 3 2>/dev/null)
if [ "$PRS" = "[]" ] || [ -z "$PRS" ]; then
    echo "  No open PRs"
else
    echo "$PRS" | jq -r '.[] | "  PR #\(.number): \(.title)"' 2>/dev/null || echo "  $PRS"
fi
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Last updated: $(date '+%Y-%m-%d %H:%M:%S')"
