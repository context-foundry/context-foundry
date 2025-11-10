#!/bin/bash
# Evolution System Monitor - Horizontal Dashboard Layout
# Optimized for vertical screens with efficient horizontal space usage

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
NC='\033[0m'

# Function to calculate visible string length (excluding ANSI codes)
visible_length() {
    local str="$1"
    # Remove ANSI escape sequences
    local stripped=$(echo -e "$str" | sed 's/\x1b\[[0-9;]*m//g')
    echo "${#stripped}"
}

# Function to pad string to width (accounting for ANSI codes)
pad_string() {
    local str="$1"
    local width="$2"
    local vis_len=$(visible_length "$str")
    local padding=$((width - vis_len))

    if [ $padding -gt 0 ]; then
        printf "%b%*s" "$str" $padding ""
    else
        printf "%b" "$str"
    fi
}

# Detect terminal width
TERM_WIDTH=$(tput cols 2>/dev/null || echo 120)

clear
echo -e "${BOLD}${CYAN}════════════════ CONTEXT FOUNDRY EVOLUTION MONITOR ════════════════${NC}"

cd /Users/name/homelab/context-foundry 2>/dev/null

# Gather all data first
RECENT_MERGED=$(gh pr list --state merged --limit 1 --json number,title,mergedAt 2>/dev/null | jq -r '.[0] | select(.mergedAt != null) | .number' 2>/dev/null)
RECENT_ISSUES=$(gh issue list --state open --limit 10 --json number,title,createdAt 2>/dev/null | jq -r '.[] | select((now - (.createdAt | fromdateiso8601)) < 300) | "\(.number)|\(.title)"' 2>/dev/null)
DAEMON_PID=$(pgrep -f "tools.evolution.daemon" 2>/dev/null | head -1)
OPEN_PRS=$(gh pr list --state open --json number 2>/dev/null | jq '. | length' 2>/dev/null)
APPROVED=$(gh issue list --label approved --state open --json number 2>/dev/null | jq '. | length' 2>/dev/null)
ISSUE_COUNT=$(gh issue list --state open --json number 2>/dev/null | jq '. | length' 2>/dev/null)
CLAUDE_WORKING=$(ps aux | grep " claude " | grep -v "grep\|Claude.app" | awk '{print $2}' | while read pid; do
    STATE=$(ps -p $pid -o state= 2>/dev/null | tr -d ' ')
    if [[ "$STATE" =~ N ]]; then echo $pid; fi
done | head -1)

# Also check for active MCP delegations in logs
if [ -z "$CLAUDE_WORKING" ]; then
    MCP_CHECK=$(tail -100 ~/.context-foundry/evolution/logs/daemon.log 2>/dev/null | grep "MCP Task ID:" | tail -1)
    [ -n "$MCP_CHECK" ] && CLAUDE_WORKING="mcp_active"
fi

# Build compact status line
STATUS_LINE=""
[ -n "$RECENT_MERGED" ] && STATUS_LINE+="${GREEN}✓Merged#$RECENT_MERGED${NC} │ "
if [ -n "$CLAUDE_WORKING" ]; then
    TASK_DESC=$(sqlite3 ~/.context-foundry/evolution/task_queue.db "SELECT params_json FROM tasks WHERE status = 'running' ORDER BY created_at DESC LIMIT 1;" 2>/dev/null | jq -r '.description // .action' 2>/dev/null)
    GITHUB_ISSUE=$(sqlite3 ~/.context-foundry/evolution/task_queue.db "SELECT params_json FROM tasks WHERE status = 'running' ORDER BY created_at DESC LIMIT 1;" 2>/dev/null | jq -r '.github_issue // empty' 2>/dev/null)
    [ -n "$GITHUB_ISSUE" ] && STATUS_LINE+="${YELLOW}→Issue#$GITHUB_ISSUE${NC} │ " || STATUS_LINE+="${YELLOW}→Working${NC} │ "
elif [ "$OPEN_PRS" -gt 0 ]; then
    STATUS_LINE+="${CYAN}⏸Waiting for PR${NC} │ "
elif [ "$APPROVED" -gt 0 ]; then
    STATUS_LINE+="${GREEN}→Implementing${NC} │ "
elif [ "$ISSUE_COUNT" -lt 5 ]; then
    STATUS_LINE+="${YELLOW}→Scout creating issues${NC} │ "
else
    STATUS_LINE+="${GRAY}○Idle${NC} │ "
fi

STATUS_LINE+="${GRAY}Backlog:$ISSUE_COUNT/5 │ Approved:$APPROVED │ PRs:$OPEN_PRS │ Active Build:"
[ -n "$CLAUDE_WORKING" ] && STATUS_LINE+="Yes${NC}" || STATUS_LINE+="No${NC}"

echo -e "STATUS: $STATUS_LINE"
echo ""

# CLAUDE INSTANCES + DAEMON (side by side)
COL1_WIDTH=$(( TERM_WIDTH * 60 / 100 ))
COL2_WIDTH=$(( TERM_WIDTH - COL1_WIDTH - 4 ))

echo -e "${GRAY}┌$(printf '─%.0s' $(seq 1 $COL1_WIDTH))┬$(printf '─%.0s' $(seq 1 $COL2_WIDTH))┐${NC}"
printf "${CYAN}│ %-$((COL1_WIDTH-2))s ${NC}${GRAY}│${NC}${CYAN} %-$((COL2_WIDTH-2))s ${NC}${GRAY}│${NC}\n" "CLAUDE INSTANCES" "DAEMON"
echo -e "${GRAY}├$(printf '─%.0s' $(seq 1 $COL1_WIDTH))┼$(printf '─%.0s' $(seq 1 $COL2_WIDTH))┤${NC}"

# Collect Claude instances
CLAUDE_PIDS=$(ps aux | grep " claude " | grep -v "grep\|Claude.app" | awk '{print $2}')
CLAUDE_LINES=()
if [ -z "$CLAUDE_PIDS" ]; then
    CLAUDE_LINES+=("${GRAY}No instances running${NC}")
else
    for pid in $CLAUDE_PIDS; do
        TTY=$(ps -p $pid -o tty= 2>/dev/null | tr -d ' ')
        STATE=$(ps -p $pid -o state= 2>/dev/null | tr -d ' ')
        if [[ "$TTY" == "??" ]] || [[ "$STATE" =~ N ]]; then
            TYPE="${BLUE}daemon${NC}"
        else
            TYPE="${GRAY}interactive${NC}"
        fi
        INFO=$(ps -p $pid -o pid=,pcpu=,rss=,etime= 2>/dev/null | awk '{printf "%s %.1f%% %dMB %s", $1, $2, $3/1024, $4}')
        CLAUDE_LINES+=("$INFO $(echo -e $TYPE)")
    done
fi

# Collect daemon status
DAEMON_LINES=()
if [ -z "$DAEMON_PID" ]; then
    DAEMON_LINES+=("${RED}Not running${NC}")
else
    DAEMON_LINES+=("${GREEN}Running${NC} ${GRAY}(PID: $DAEMON_PID)${NC}")
    DAEMON_LOG=$(tail -1 ~/.context-foundry/evolution/logs/daemon.log 2>/dev/null | cut -c1-$((COL2_WIDTH-2)))
    [ -n "$DAEMON_LOG" ] && DAEMON_LINES+=("${GRAY}${DAEMON_LOG}${NC}")
fi

# Print side by side
MAX_LINES=$(( ${#CLAUDE_LINES[@]} > ${#DAEMON_LINES[@]} ? ${#CLAUDE_LINES[@]} : ${#DAEMON_LINES[@]} ))
for ((i=0; i<MAX_LINES; i++)); do
    LEFT="${CLAUDE_LINES[$i]:-}"
    RIGHT="${DAEMON_LINES[$i]:-}"
    printf "${GRAY}│${NC} "
    pad_string "$LEFT" $((COL1_WIDTH-2))
    printf " ${GRAY}│${NC} "
    pad_string "$RIGHT" $((COL2_WIDTH-2))
    printf " ${GRAY}│${NC}\n"
done

echo -e "${GRAY}└$(printf '─%.0s' $(seq 1 $COL1_WIDTH))┴$(printf '─%.0s' $(seq 1 $COL2_WIDTH))┘${NC}"
echo ""

# ACTIVE AUTONOMOUS BUILDS (compact)
echo -e "${CYAN}ACTIVE BUILDS${NC}"
ACTIVE_BUILDS=$($PYTHON_CMD << 'PYTHON'
import sys
sys.path.insert(0, '/Users/name/homelab/context-foundry')
try:
    from tools.evolution.task_queue import TaskQueueManager, TaskStatus
    import json
    from datetime import datetime
    from pathlib import Path

    tq = TaskQueueManager()
    running = tq.list_tasks(status=TaskStatus.RUNNING.value)

    for task in running:
        params = json.loads(task.params_json) if task.params_json else {}
        result = task.result if task.result else {}

        task_id = task.id[:8]
        description = params.get('description', params.get('action', ''))[:60]
        sandbox = params.get('sandbox_dir', result.get('sandbox_dir', ''))
        branch = params.get('branch', result.get('branch', ''))
        issue = params.get('github_issue', result.get('github_issue', ''))
        mcp_task_id = result.get('mcp_task_id', '')[:8] if result.get('mcp_task_id') else ''
        created_time = task.created_at.strftime('%H:%M') if hasattr(task, 'created_at') else ''

        # Read phase info
        phase_data = ""
        if sandbox:
            phase_file = Path(sandbox) / '.context-foundry' / 'current-phase.json'
            if phase_file.exists():
                try:
                    file_age = datetime.now().timestamp() - phase_file.stat().st_mtime
                    if file_age < 600:
                        with open(phase_file, 'r') as f:
                            phase_info = json.load(f)
                            current_phase = phase_info.get('current_phase', '')
                            phase_number = phase_info.get('phase_number', '')
                            phases_completed = phase_info.get('phases_completed', [])
                            test_iter = phase_info.get('test_iteration', 0)

                            # Build inline phase string
                            phases = ["Scout", "Architect", "Builder", "Test", "Screenshot", "Documentation", "Feedback"]
                            phase_str = ""
                            for p in phases:
                                if p in phases_completed:
                                    phase_str += f"✓{p} "
                                elif p == current_phase:
                                    if p == "Test" and test_iter > 0:
                                        phase_str += f"🔄{p}({test_iter}/3) "
                                    else:
                                        phase_str += f"🔄{p} "
                                else:
                                    phase_str += f"⏳{p} "
                            phase_data = f"{phase_number}|{phase_str.strip()}"
                except Exception:
                    pass

        print(f"{task_id}|{description}|{branch}|{issue}|{mcp_task_id}|{created_time}|{phase_data}")
except Exception as e:
    pass
PYTHON
)

if [ -z "$ACTIVE_BUILDS" ]; then
    # Fallback: Check daemon logs for recently delegated tasks
    MCP_FROM_LOGS=$(tail -100 ~/.context-foundry/evolution/logs/daemon.log 2>/dev/null | grep "MCP Task ID:" | tail -1 | sed -E 's/.*MCP Task ID: ([a-f0-9-]+).*/\1/')
    TASK_FROM_LOGS=$(tail -100 ~/.context-foundry/evolution/logs/daemon.log 2>/dev/null | grep "delegated to Context Foundry MCP" | tail -1 | sed -E 's/.*Task ([a-f0-9-]+) delegated.*/\1/')
    ISSUE_FROM_LOGS=$(tail -100 ~/.context-foundry/evolution/logs/daemon.log 2>/dev/null | grep "Task:" | tail -1 | sed -E 's/.*#([0-9]+).*/\1/')
    SANDBOX_FROM_LOGS=$(tail -100 ~/.context-foundry/evolution/logs/daemon.log 2>/dev/null | grep "Path: /tmp/cf-sandboxes" | tail -1 | sed -E 's/.*Path: (.*)/\1/')

    if [ -n "$MCP_FROM_LOGS" ] && [ -n "$TASK_FROM_LOGS" ]; then
        CLAUDE_PID=$(ps aux | grep " claude " | grep -v "grep\|Claude.app" | awk '{print $2}' | while read pid; do
            STATE=$(ps -p $pid -o state= 2>/dev/null | tr -d ' ')
            if [[ "$STATE" =~ N ]]; then echo $pid; break; fi
        done)

        # Check if delegation is still running by looking at recent logs
        RECENT_ACTIVITY=$(tail -20 ~/.context-foundry/evolution/logs/daemon.log 2>/dev/null | grep -c "Started monitoring delegation")
        if [ "$RECENT_ACTIVITY" -gt 0 ]; then
            MCP_STATUS="running|active"
        else
            MCP_STATUS="running|delegated"
        fi

        BUILD_STATUS=$(echo "$MCP_STATUS" | cut -d'|' -f1)
        BUILD_PHASE=$(echo "$MCP_STATUS" | cut -d'|' -f2)

        echo -e "  ${GREEN}🎉Build${NC} │ PID:${YELLOW}${CLAUDE_PID:-N/A}${NC} │ Task:${TASK_FROM_LOGS:0:8} (MCP:${MCP_FROM_LOGS:0:8})"
        [ -n "$ISSUE_FROM_LOGS" ] && echo -e "  ${GRAY}Issue:${NC} ${YELLOW}#$ISSUE_FROM_LOGS${NC}"
        echo -e "  ${GRAY}Status:${NC} ${YELLOW}$BUILD_STATUS${NC} │ ${GRAY}Phase:${NC} $BUILD_PHASE"
        [ -n "$SANDBOX_FROM_LOGS" ] && echo -e "  ${GRAY}Sandbox:${NC} ${CYAN}$SANDBOX_FROM_LOGS${NC}"
    else
        echo -e "  ${GRAY}No active builds${NC}"
    fi
else
    echo "$ACTIVE_BUILDS" | while IFS='|' read task_id description branch issue mcp_id spawn_time phase_number phase_str; do
        CLAUDE_PID=$(ps aux | grep " claude " | grep -v "grep\|Claude.app" | awk '{print $2}' | while read pid; do
            STATE=$(ps -p $pid -o state= 2>/dev/null | tr -d ' ')
            if [[ "$STATE" =~ N ]]; then echo $pid; break; fi
        done)

        BUILD_LINE="${GREEN}🎉Build${NC} │ PID:${YELLOW}${CLAUDE_PID:-N/A}${NC}($spawn_time) │ Task:$task_id"
        [ -n "$mcp_id" ] && BUILD_LINE+=" (MCP:$mcp_id)"
        [ -n "$issue" ] && BUILD_LINE+=" │ ${YELLOW}Issue#$issue${NC}"
        echo -e "  $BUILD_LINE"
        echo -e "  ${GRAY}Task:${NC} $description"
        [ -n "$branch" ] && echo -e "  ${GRAY}Branch:${NC} $branch"
        if [ -n "$phase_str" ]; then
            echo -e "  ${CYAN}Progress [$phase_number]:${NC} $phase_str"
        fi
        echo ""
    done
fi

# OPEN PRS + GIT STATUS (side by side)
PRS_WIDTH=$(( TERM_WIDTH * 35 / 100 ))
GIT_WIDTH=$(( TERM_WIDTH - PRS_WIDTH - 4 ))

echo -e "${GRAY}┌$(printf '─%.0s' $(seq 1 $PRS_WIDTH))┬$(printf '─%.0s' $(seq 1 $GIT_WIDTH))┐${NC}"
printf "${CYAN}│ %-$((PRS_WIDTH-2))s ${NC}${GRAY}│${NC}${CYAN} %-$((GIT_WIDTH-2))s ${NC}${GRAY}│${NC}\n" "OPEN PRS" "GIT STATUS [M=Mod D=Del ??=Untracked]"
echo -e "${GRAY}├$(printf '─%.0s' $(seq 1 $PRS_WIDTH))┼$(printf '─%.0s' $(seq 1 $GIT_WIDTH))┤${NC}"

# Collect PRs
PRS=$(gh pr list --state open --json number,title --limit 5 2>/dev/null)
PR_LINES=()
PR_COUNT=$(echo "$PRS" | jq '. | length' 2>/dev/null)
if [ "$PR_COUNT" = "0" ] || [ -z "$PR_COUNT" ]; then
    PR_LINES+=("${GRAY}No open PRs${NC}")
else
    while IFS='|' read num title; do
        PR_LINES+=("#$num: ${title:0:$((PRS_WIDTH-8))}")
    done < <(echo "$PRS" | jq -r '.[] | "\(.number)|\(.title)"' 2>/dev/null)
fi

# Collect Git status
GIT_STATUS=$(git status --short 2>/dev/null)
GIT_LINES=()
if [ -z "$GIT_STATUS" ]; then
    GIT_LINES+=("${GREEN}Working tree clean${NC}")
else
    while read line; do
        if [[ $line =~ ^M ]]; then
            GIT_LINES+=("${YELLOW}${line:0:$((GIT_WIDTH-4))}${NC}")
        elif [[ $line =~ ^\?\? ]]; then
            GIT_LINES+=("${GRAY}${line:0:$((GIT_WIDTH-4))}${NC}")
        elif [[ $line =~ ^D ]]; then
            GIT_LINES+=("${RED}${line:0:$((GIT_WIDTH-4))}${NC}")
        else
            GIT_LINES+=("${GREEN}${line:0:$((GIT_WIDTH-4))}${NC}")
        fi
    done < <(echo "$GIT_STATUS" | head -5)
    COUNT=$(echo "$GIT_STATUS" | wc -l | tr -d ' ')
    [ "$COUNT" -gt 5 ] && GIT_LINES+=("${GRAY}...+$((COUNT-5)) more${NC}")
fi

# Print side by side
MAX_LINES=$(( ${#PR_LINES[@]} > ${#GIT_LINES[@]} ? ${#PR_LINES[@]} : ${#GIT_LINES[@]} ))
for ((i=0; i<MAX_LINES; i++)); do
    LEFT="${PR_LINES[$i]:-}"
    RIGHT="${GIT_LINES[$i]:-}"
    printf "${GRAY}│${NC} "
    pad_string "$LEFT" $((PRS_WIDTH-2))
    printf " ${GRAY}│${NC} "
    pad_string "$RIGHT" $((GIT_WIDTH-2))
    printf " ${GRAY}│${NC}\n"
done

echo -e "${GRAY}└$(printf '─%.0s' $(seq 1 $PRS_WIDTH))┴$(printf '─%.0s' $(seq 1 $GIT_WIDTH))┘${NC}"
echo ""

# RECENT CHANGES + MCP DELEGATIONS + NETWORK (3 columns)
COL1_W=$(( TERM_WIDTH * 30 / 100 ))
COL2_W=$(( TERM_WIDTH * 45 / 100 ))
COL3_W=$(( TERM_WIDTH - COL1_W - COL2_W - 6 ))

echo -e "${GRAY}┌$(printf '─%.0s' $(seq 1 $COL1_W))┬$(printf '─%.0s' $(seq 1 $COL2_W))┬$(printf '─%.0s' $(seq 1 $COL3_W))┐${NC}"
printf "${CYAN}│ %-$((COL1_W-2))s ${NC}${GRAY}│${NC}${CYAN} %-$((COL2_W-2))s ${NC}${GRAY}│${NC}${CYAN} %-$((COL3_W-2))s ${NC}${GRAY}│${NC}\n" "FILE CHANGES (60s)" "MCP DELEGATIONS" "NETWORK"
echo -e "${GRAY}├$(printf '─%.0s' $(seq 1 $COL1_W))┼$(printf '─%.0s' $(seq 1 $COL2_W))┼$(printf '─%.0s' $(seq 1 $COL3_W))┤${NC}"

# Collect recent file changes
RECENT=$(find . -type f -mmin -1 -not -path "*/.git/*" -not -path "*/.pytest_cache/*" -not -path "*/node_modules/*" 2>/dev/null)
RECENT_LINES=()
if [ -z "$RECENT" ]; then
    RECENT_LINES+=("${GRAY}No changes${NC}")
else
    while read file; do
        RECENT_LINES+=("${YELLOW}${file:0:$((COL1_W-4))}${NC}")
    done < <(echo "$RECENT" | head -3)
    COUNT=$(echo "$RECENT" | wc -l | tr -d ' ')
    [ "$COUNT" -gt 3 ] && RECENT_LINES+=("${GRAY}+$((COUNT-3)) more${NC}")
fi

# Collect MCP delegations
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
            print(f"{task.id[:8]}|{mcp_id[:8]}|{status.get('status')}|{status.get('current_phase', 'N/A')}")
        except:
            print(f"{task.id[:8]}|{mcp_id[:8]}|running|active")
except Exception:
    pass
PYTHON
)

if [ -z "$MCP_TASKS" ]; then
    MCP_FROM_LOGS=$(tail -100 ~/.context-foundry/evolution/logs/daemon.log 2>/dev/null | grep "MCP Task ID:" | tail -1 | sed -E 's/.*MCP Task ID: ([a-f0-9-]+).*/\1/')
    TASK_FROM_LOGS=$(tail -100 ~/.context-foundry/evolution/logs/daemon.log 2>/dev/null | grep "delegated to Context Foundry MCP" | tail -1 | sed -E 's/.*Task ([a-f0-9-]+) delegated.*/\1/')

    if [ -n "$MCP_FROM_LOGS" ] && [ -n "$TASK_FROM_LOGS" ]; then
        # Check recent activity to determine status
        RECENT_ACTIVITY=$(tail -20 ~/.context-foundry/evolution/logs/daemon.log 2>/dev/null | grep -c "Started monitoring delegation")
        if [ "$RECENT_ACTIVITY" -gt 0 ]; then
            MCP_TASKS="${TASK_FROM_LOGS:0:8}|${MCP_FROM_LOGS:0:8}|running|active"
        else
            MCP_TASKS="${TASK_FROM_LOGS:0:8}|${MCP_FROM_LOGS:0:8}|running|delegated"
        fi
    fi
fi

MCP_LINES=()
if [ -z "$MCP_TASKS" ]; then
    MCP_LINES+=("${GRAY}No active delegations${NC}")
else
    while IFS='|' read task_id mcp_id status phase; do
        [[ "$status" == "completed" ]] && COLOR="${GREEN}" || COLOR="${YELLOW}"
        MCP_LINES+=("$task_id|$mcp_id $(echo -e ${COLOR}$status${NC}) $phase")
    done < <(echo "$MCP_TASKS")
fi

# Collect network status
DAEMON_CLAUDES=$(ps aux | grep " claude " | grep -v "grep\|Claude.app" | awk '{print $2}' | while read pid; do
    STATE=$(ps -p $pid -o state= 2>/dev/null | tr -d ' ')
    [[ "$STATE" =~ N ]] && echo $pid
done)

NET_LINES=()
if [ -z "$DAEMON_CLAUDES" ]; then
    NET_LINES+=("${GRAY}No daemon PIDs${NC}")
else
    for pid in $DAEMON_CLAUDES; do
        CONN=$(lsof -p $pid -a -i 2>/dev/null | grep ESTABLISHED | wc -l | tr -d ' ')
        if [ "$CONN" -gt 0 ]; then
            NET_LINES+=("${GREEN}PID $pid: ${CONN}conn${NC}")
        else
            NET_LINES+=("${GRAY}PID $pid: idle${NC}")
        fi
    done
fi

# Print 3 columns
MAX_LINES=$(( ${#RECENT_LINES[@]} > ${#MCP_LINES[@]} ? ${#RECENT_LINES[@]} : ${#MCP_LINES[@]} ))
MAX_LINES=$(( $MAX_LINES > ${#NET_LINES[@]} ? $MAX_LINES : ${#NET_LINES[@]} ))
for ((i=0; i<MAX_LINES; i++)); do
    COL1="${RECENT_LINES[$i]:-}"
    COL2="${MCP_LINES[$i]:-}"
    COL3="${NET_LINES[$i]:-}"
    printf "${GRAY}│${NC} "
    pad_string "$COL1" $((COL1_W-2))
    printf " ${GRAY}│${NC} "
    pad_string "$COL2" $((COL2_W-2))
    printf " ${GRAY}│${NC} "
    pad_string "$COL3" $((COL3_W-2))
    printf " ${GRAY}│${NC}\n"
done

echo -e "${GRAY}└$(printf '─%.0s' $(seq 1 $COL1_W))┴$(printf '─%.0s' $(seq 1 $COL2_W))┴$(printf '─%.0s' $(seq 1 $COL3_W))┘${NC}"
echo ""
echo -e "${GRAY}Last updated: $(date '+%Y-%m-%d %H:%M:%S')${NC}"
