#!/bin/bash
# Evolution System Monitor - "Simplicity is the ultimate sophistication"
# Shows all Claude instances and their activity in one clean view

# Python command
PYTHON_CMD=${PYTHON_CMD:-python3}

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
RED='\033[0;31m'
GRAY='\033[0;90m'
BOLD='\033[1m'
NC='\033[0m' # No Color

clear
echo -e "${BOLD}${CYAN}════════════════ CONTEXT FOUNDRY EVOLUTION MONITOR ════════════════${NC}"
echo ""

# EXECUTIVE STATUS - The story of what's happening right now
echo -e "${BOLD}${CYAN}STATUS:${NC}"
cd /Users/name/homelab/context-foundry 2>/dev/null

# Check for recently merged PRs (last 5 minutes)
RECENT_MERGED=$(gh pr list --state merged --limit 1 --json number,title,mergedAt 2>/dev/null | jq -r '.[0] | select(.mergedAt != null) | .number' 2>/dev/null)

# Check for recently created issues (last 5 minutes)
RECENT_ISSUES=$(gh issue list --state open --limit 10 --json number,title,createdAt 2>/dev/null | jq -r '.[] | select((now - (.createdAt | fromdateiso8601)) < 300) | "\(.number)|\(.title)"' 2>/dev/null)

# Check current state
DAEMON_PID=$(pgrep -f "tools.evolution.daemon" 2>/dev/null | head -1)
OPEN_PRS=$(gh pr list --state open --json number 2>/dev/null | jq '. | length' 2>/dev/null)
APPROVED=$(gh issue list --label approved --state open --json number 2>/dev/null | jq '. | length' 2>/dev/null)
ISSUE_COUNT=$(gh issue list --state open --json number 2>/dev/null | jq '. | length' 2>/dev/null)
CLAUDE_WORKING=$(ps aux | grep " claude " | grep -v "grep\|Claude.app" | awk '{print $2}' | while read pid; do
    STATE=$(ps -p $pid -o state= 2>/dev/null | tr -d ' ')
    if [[ "$STATE" =~ N ]]; then
        echo $pid
    fi
done | head -1)

# Build status narrative
if [ -n "$RECENT_MERGED" ]; then
    echo -e "  ${GREEN}✓${NC} Just merged PR #$RECENT_MERGED"
fi

if [ -n "$CLAUDE_WORKING" ]; then
    # Get what Claude is working on
    TASK_DESC=$(sqlite3 ~/.context-foundry/evolution/task_queue.db "SELECT params_json FROM tasks WHERE status = 'running' ORDER BY created_at DESC LIMIT 1;" 2>/dev/null | jq -r '.description // .action' 2>/dev/null)
    GITHUB_ISSUE=$(sqlite3 ~/.context-foundry/evolution/task_queue.db "SELECT params_json FROM tasks WHERE status = 'running' ORDER BY created_at DESC LIMIT 1;" 2>/dev/null | jq -r '.github_issue // empty' 2>/dev/null)

    if [ -n "$GITHUB_ISSUE" ]; then
        echo -e "  ${YELLOW}→${NC} Implementing approved issue #$GITHUB_ISSUE: ${TASK_DESC:0:60}"
    else
        echo -e "  ${YELLOW}→${NC} Working on: ${TASK_DESC:0:70}"
    fi
elif [ "$OPEN_PRS" -gt 0 ]; then
    echo -e "  ${CYAN}⏸${NC}  Waiting for PR review/merge"
elif [ "$APPROVED" -gt 0 ]; then
    echo -e "  ${GREEN}→${NC} Approved issue found, queuing for implementation..."
else
    # Check backlog health
    if [ "$ISSUE_COUNT" -lt 18 ]; then
        NEEDED=$((20 - ISSUE_COUNT))
        if [ -n "$RECENT_ISSUES" ]; then
            echo -e "  ${YELLOW}→${NC} Scout creating issues to maintain 20-issue backlog (currently $ISSUE_COUNT)"
            # Show recently created issues
            RECENT_COUNT=$(echo "$RECENT_ISSUES" | wc -l | tr -d ' ')
            echo -e "  ${GREEN}✓${NC} Created $RECENT_COUNT issue(s) in last 5 minutes:"
            echo "$RECENT_ISSUES" | head -3 | while IFS='|' read num title; do
                echo -e "    ${GRAY}#$num:${NC} ${title:0:60}"
            done
            if [ "$RECENT_COUNT" -gt 3 ]; then
                echo -e "    ${GRAY}... and $((RECENT_COUNT - 3)) more${NC}"
            fi
        else
            echo -e "  ${YELLOW}→${NC} Scout creating $NEEDED issues to maintain 20-issue backlog (currently $ISSUE_COUNT)"
        fi
    else
        echo -e "  ${GRAY}○${NC} Idle: Backlog healthy ($ISSUE_COUNT/20), awaiting issue approval"
    fi
fi

# TL;DR summary
if [ -z "$DAEMON_PID" ]; then
    echo -e "  ${RED}TL;DR:${NC} Daemon offline"
else
    echo -e "  ${GRAY}TL;DR: Backlog $ISSUE_COUNT/20 | Approved: $APPROVED | Open PRs: $OPEN_PRS | Working: $([ -n "$CLAUDE_WORKING" ] && echo "Yes" || echo "No")${NC}"
fi
echo -e "${GRAY}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# 1. CLAUDE INSTANCES
echo -e "${CYAN}CLAUDE INSTANCES${NC}"
echo -e "${GRAY}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
CLAUDE_PIDS=$(ps aux | grep " claude " | grep -v "grep\|Claude.app" | awk '{print $2}')
if [ -z "$CLAUDE_PIDS" ]; then
    echo -e "  ${GRAY}No Claude instances running${NC}"
else
    echo -e "  ${GRAY}PID    CPU%   MEM(MB)  TIME     STATE    TYPE${NC}"
    echo -e "  ${GRAY}────────────────────────────────────────────────────────────────${NC}"
    for pid in $CLAUDE_PIDS; do
        # Check if it's the interactive session (has terminal) or daemon-spawned
        TTY=$(ps -p $pid -o tty= 2>/dev/null | tr -d ' ')
        STATE=$(ps -p $pid -o state= 2>/dev/null | tr -d ' ')

        # Daemon processes have no TTY (??) and state contains N (nice/low priority)
        if [[ "$TTY" == "??" ]] || [[ "$STATE" =~ N ]]; then
            TYPE_TEXT="daemon"
            TYPE_COLOR="${BLUE}"
        else
            TYPE_TEXT="interactive"
            TYPE_COLOR="${GRAY}"
        fi

        ps -p $pid -o pid=,pcpu=,rss=,etime=,state= 2>/dev/null | \
        awk -v type_text="$TYPE_TEXT" -v type_color="$TYPE_COLOR" -v green="$GREEN" -v yellow="$YELLOW" -v red="$RED" -v nc="$NC" '{
            cpu_color = ($2 > 50) ? red : ($2 > 20) ? yellow : green
            printf "  %-6s " cpu_color "%-6s" nc " %-8.0f %-8s %-8s " type_color "%s" nc "\n", $1, $2"%", $3/1024, $4, $5, type_text
        }'
    done
fi
echo ""

# 2. DAEMON STATUS
echo -e "${CYAN}DAEMON STATUS${NC}"
echo -e "${GRAY}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
DAEMON_PID=$(pgrep -f "tools.evolution.daemon" 2>/dev/null | head -1)
if [ -z "$DAEMON_PID" ]; then
    echo -e "  ${RED}Daemon not running${NC}"
else
    echo -e "  ${GREEN}Running${NC} ${GRAY}(PID: $DAEMON_PID)${NC}"
    tail -3 ~/.context-foundry/evolution/logs/daemon.log 2>/dev/null | while read line; do
        echo -e "  ${GRAY}│${NC} $line"
    done
fi
echo ""

# 3. ACTIVE AUTONOMOUS BUILDS
echo -e "${CYAN}ACTIVE AUTONOMOUS BUILDS${NC}"
echo -e "${GRAY}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Query running tasks with full details including phase information
ACTIVE_BUILDS=$($PYTHON_CMD << 'PYTHON'
import sys
sys.path.insert(0, '/Users/name/homelab/context-foundry')
try:
    from tools.evolution.task_queue import TaskQueueManager, TaskStatus
    import json
    import os
    from datetime import datetime
    from pathlib import Path

    tq = TaskQueueManager()
    running = tq.list_tasks(status=TaskStatus.RUNNING.value)

    for task in running:
        params = json.loads(task.params_json) if task.params_json else {}
        result = task.result if task.result else {}

        # Extract key information
        task_id = task.id[:8]
        description = params.get('description', params.get('action', 'Unknown task'))
        sandbox = params.get('sandbox_dir', result.get('sandbox_dir', 'N/A'))
        branch = params.get('branch', result.get('branch', 'N/A'))
        issue = params.get('github_issue', result.get('github_issue', 'N/A'))
        mcp_task_id = result.get('mcp_task_id', '')[:8] if result.get('mcp_task_id') else 'N/A'

        # Format spawn time
        created_time = task.created_at.strftime('%H:%M') if hasattr(task, 'created_at') else 'N/A'

        # Read phase information from current-phase.json
        phase_data = "N/A|N/A|N/A|N/A|N/A"
        if sandbox != 'N/A':
            phase_file = Path(sandbox) / '.context-foundry' / 'current-phase.json'
            if phase_file.exists():
                try:
                    # Check staleness (file modified within last 10 minutes)
                    file_age = datetime.now().timestamp() - phase_file.stat().st_mtime
                    if file_age < 600:  # 10 minutes
                        with open(phase_file, 'r') as f:
                            phase_info = json.load(f)
                            current_phase = phase_info.get('current_phase', 'N/A')
                            phase_number = phase_info.get('phase_number', 'N/A')
                            status = phase_info.get('status', 'N/A')
                            progress_detail = phase_info.get('progress_detail', 'N/A')
                            phases_completed = ','.join(phase_info.get('phases_completed', []))
                            test_iteration = str(phase_info.get('test_iteration', 0))

                            phase_data = f"{current_phase}|{phase_number}|{status}|{progress_detail}|{phases_completed}|{test_iteration}"
                except Exception:
                    pass

        print(f"{task_id}|{description}|{sandbox}|{branch}|{issue}|{mcp_task_id}|{created_time}|{phase_data}")
except Exception as e:
    pass
PYTHON
)

if [ -z "$ACTIVE_BUILDS" ]; then
    echo -e "  ${GRAY}No active autonomous builds${NC}"
else
    echo "$ACTIVE_BUILDS" | while IFS='|' read task_id description sandbox branch issue mcp_id spawn_time current_phase phase_number phase_status progress_detail phases_completed test_iteration; do
        # Find associated Claude process
        CLAUDE_PID=""
        for pid in $(ps aux | grep " claude " | grep -v "grep\|Claude.app" | awk '{print $2}'); do
            STATE=$(ps -p $pid -o state= 2>/dev/null | tr -d ' ')
            if [[ "$STATE" =~ N ]]; then
                CLAUDE_PID=$pid
                break
            fi
        done

        echo -e "  ${GREEN}🎉 Autonomous Build Active${NC}"
        if [ -n "$CLAUDE_PID" ]; then
            echo -e "    ${GRAY}Claude Process:${NC} PID ${YELLOW}$CLAUDE_PID${NC} ${GRAY}(spawned at $spawn_time)${NC}"
            echo -e "    ${GRAY}Status:${NC} ${GREEN}Running ✅${NC}"
        fi
        echo -e "    ${GRAY}Task ID:${NC} $task_id ${GRAY}(MCP: $mcp_id)${NC}"
        echo -e "    ${GRAY}Task:${NC} $description"
        if [ "$issue" != "N/A" ]; then
            echo -e "    ${GRAY}Will fix:${NC} ${YELLOW}Issue #$issue${NC}"
        fi
        if [ "$branch" != "N/A" ]; then
            echo -e "    ${GRAY}Branch:${NC} $branch"
        fi
        if [ "$sandbox" != "N/A" ]; then
            # Shorten sandbox path for display
            SANDBOX_SHORT=$(echo "$sandbox" | sed 's|/tmp/cf-sandboxes/||')
            echo -e "    ${GRAY}Sandbox:${NC} $SANDBOX_SHORT"
        fi

        # Display orchestration progress if phase data available
        if [ "$current_phase" != "N/A" ] && [ "$phase_number" != "N/A" ]; then
            echo ""
            echo -e "    ${CYAN}Orchestration Progress [$phase_number]:${NC}"

            # Define all phases in order
            ALL_PHASES=("Scout" "Architect" "Builder" "Test" "Screenshot" "Documentation" "Feedback")
            PHASE_DESCRIPTIONS=("Research & analysis" "Design & planning" "Code implementation" "Validation & testing" "Visual validation" "README & docs" "Pattern learning")

            # Split completed phases
            IFS=',' read -ra COMPLETED <<< "$phases_completed"

            # Display each phase
            for i in "${!ALL_PHASES[@]}"; do
                PHASE_NAME="${ALL_PHASES[$i]}"
                PHASE_DESC="${PHASE_DESCRIPTIONS[$i]}"

                # Check if this phase is completed
                IS_COMPLETED=false
                for comp in "${COMPLETED[@]}"; do
                    if [ "$comp" = "$PHASE_NAME" ]; then
                        IS_COMPLETED=true
                        break
                    fi
                done

                # Determine status symbol and color
                if [ "$IS_COMPLETED" = true ]; then
                    echo -e "      ${GREEN}✓${NC} ${PHASE_NAME} - ${GRAY}$PHASE_DESC${NC}"
                elif [ "$PHASE_NAME" = "$current_phase" ]; then
                    # Current phase
                    if [ "$test_iteration" != "0" ] && [ "$PHASE_NAME" = "Test" ]; then
                        echo -e "      ${YELLOW}🔄${NC} ${PHASE_NAME} - ${YELLOW}$PHASE_DESC (iteration $test_iteration/3)${NC}"
                    else
                        echo -e "      ${YELLOW}🔄${NC} ${PHASE_NAME} - ${YELLOW}$PHASE_DESC${NC}"
                    fi
                else
                    # Pending phase
                    echo -e "      ${GRAY}⏳${NC} ${PHASE_NAME} - ${GRAY}$PHASE_DESC${NC}"
                fi
            done
        fi
    done
fi
echo ""

# 4. OPEN PULL REQUESTS
echo -e "${CYAN}OPEN PULL REQUESTS${NC}"
echo -e "${GRAY}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
cd /Users/name/homelab/context-foundry 2>/dev/null
PRS=$(gh pr list --state open --json number,title --limit 3 2>/dev/null)
PR_COUNT=$(echo "$PRS" | jq '. | length' 2>/dev/null)
if [ "$PR_COUNT" = "0" ] || [ -z "$PR_COUNT" ]; then
    echo -e "  ${GRAY}No open PRs${NC}"
else
    echo "$PRS" | jq -r '.[] | "\(.number)|\(.title)"' 2>/dev/null | while IFS='|' read num title; do
        echo -e "  ${YELLOW}PR #$num:${NC} $title"
    done
fi
echo ""

# 5. GIT STATUS
echo -e "${CYAN}GIT STATUS${NC} ${GRAY}[M=Modified, A=Added, D=Deleted, ??=Untracked]${NC}"
echo -e "${GRAY}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
cd /Users/name/homelab/context-foundry 2>/dev/null
GIT_STATUS=$(git status --short 2>/dev/null)
if [ -z "$GIT_STATUS" ]; then
    echo -e "  ${GREEN}Working tree clean${NC}"
else
    echo "$GIT_STATUS" | head -10 | while read line; do
        if [[ $line =~ ^M ]]; then
            echo -e "  ${YELLOW}$line${NC}"
        elif [[ $line =~ ^\?\? ]]; then
            echo -e "  ${GRAY}$line${NC}"
        elif [[ $line =~ ^D ]]; then
            echo -e "  ${RED}$line${NC}"
        else
            echo -e "  ${GREEN}$line${NC}"
        fi
    done
    COUNT=$(echo "$GIT_STATUS" | wc -l | tr -d ' ')
    if [ "$COUNT" -gt 10 ]; then
        echo -e "  ${GRAY}... and $((COUNT - 10)) more files${NC}"
    fi
fi
echo ""

# 6. RECENT FILE CHANGES
echo -e "${CYAN}RECENT FILE CHANGES${NC} ${GRAY}(last 60 seconds)${NC}"
echo -e "${GRAY}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
RECENT=$(find . -type f -mmin -1 -not -path "*/.git/*" -not -path "*/.pytest_cache/*" -not -path "*/node_modules/*" 2>/dev/null)
if [ -z "$RECENT" ]; then
    echo -e "  ${GRAY}No recent changes${NC}"
else
    echo "$RECENT" | head -5 | while read file; do
        echo -e "  ${YELLOW}✏${NC}  $file"
    done
    COUNT=$(echo "$RECENT" | wc -l | tr -d ' ')
    if [ "$COUNT" -gt 5 ]; then
        echo -e "  ${GRAY}... and $((COUNT - 5)) more files${NC}"
    fi
fi
echo ""

# 7. MCP DELEGATION STATUS
echo -e "${CYAN}MCP DELEGATION STATUS${NC}"
echo -e "${GRAY}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Query running tasks with MCP task IDs
MCP_TASKS=$($PYTHON_CMD << 'PYTHON'
import sys
sys.path.insert(0, '/Users/name/homelab/context-foundry')
try:
    from tools.evolution.task_queue import TaskQueueManager, TaskStatus
    from tools.mcp_server import get_delegation_result
    import json

    tq = TaskQueueManager()
    running = tq.list_tasks(status=TaskStatus.RUNNING.value)

    for task in running:
        if not task.result or 'mcp_task_id' not in task.result:
            continue

        mcp_id = task.result['mcp_task_id']
        try:
            status_json = get_delegation_result(mcp_id, include_full_output=False)
            status = json.loads(status_json)
            print(f"{task.id[:8]}|{mcp_id[:8]}|{status.get('status')}|{status.get('current_phase', 'N/A')}|{status.get('progress', 'N/A')}")
        except:
            print(f"{task.id[:8]}|{mcp_id[:8]}|checking|...|...")
except Exception as e:
    pass
PYTHON
)

# Fallback: Extract MCP task IDs from daemon logs (last 10 lines)
if [ -z "$MCP_TASKS" ]; then
    MCP_FROM_LOGS=$(tail -10 ~/.context-foundry/evolution/logs/daemon.log 2>/dev/null | grep "MCP Task ID:" | tail -1 | sed -E 's/.*MCP Task ID: ([a-f0-9-]+).*/\1/')
    TASK_FROM_LOGS=$(tail -10 ~/.context-foundry/evolution/logs/daemon.log 2>/dev/null | grep "Task [a-f0-9-]* delegated" | tail -1 | sed -E 's/.*Task ([a-f0-9-]+).*/\1/')

    if [ -n "$MCP_FROM_LOGS" ] && [ -n "$TASK_FROM_LOGS" ]; then
        MCP_TASKS="${TASK_FROM_LOGS:0:8}|${MCP_FROM_LOGS:0:8}|running|delegated|active"
    fi
fi

if [ -z "$MCP_TASKS" ]; then
    echo -e "  ${GRAY}No active MCP delegations${NC}"
else
    echo -e "  ${GRAY}TASK     MCP-ID   STATUS      PHASE                PROGRESS${NC}"
    echo -e "  ${GRAY}────────────────────────────────────────────────────────────────${NC}"
    echo "$MCP_TASKS" | while IFS='|' read task_id mcp_id status phase progress; do
        # Color code status
        if [[ "$status" == "completed" ]]; then
            STATUS_COLOR="${GREEN}"
        elif [[ "$status" == "running" ]]; then
            STATUS_COLOR="${YELLOW}"
        else
            STATUS_COLOR="${GRAY}"
        fi
        printf "  %-8s %-8s ${STATUS_COLOR}%-11s${NC} %-20s %s\n" "$task_id" "$mcp_id" "$status" "$phase" "$progress"
    done
fi
echo ""

# 8. NETWORK ACTIVITY
echo -e "${CYAN}NETWORK ACTIVITY${NC}"
echo -e "${GRAY}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Find all daemon-spawned Claude processes (legacy - will be removed once MCP is stable)
DAEMON_CLAUDES=$(ps aux | grep " claude " | grep -v "grep\|Claude.app" | awk '{print $2}' | while read pid; do
    STATE=$(ps -p $pid -o state= 2>/dev/null | tr -d ' ')
    if [[ "$STATE" =~ N ]]; then
        echo $pid
    fi
done)

if [ -z "$DAEMON_CLAUDES" ]; then
    echo -e "  ${GRAY}No daemon-spawned Claude instances${NC}"
else
    for pid in $DAEMON_CLAUDES; do
        # Check network connections
        CONN=$(lsof -p $pid -a -i 2>/dev/null | grep ESTABLISHED | wc -l | tr -d ' ')

        if [ "$CONN" -gt 0 ]; then
            echo -e "  ${GREEN}Claude (PID $pid) connected to Anthropic API${NC} ${GRAY}($CONN connections)${NC}"
        else
            echo -e "  ${GRAY}Claude (PID $pid) idle (no active connections)${NC}"
        fi
    done
fi
echo ""

echo -e "${GRAY}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GRAY}Last updated: $(date '+%Y-%m-%d %H:%M:%S')${NC}"
