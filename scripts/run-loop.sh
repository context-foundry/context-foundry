#!/usr/bin/env bash
#
# run-loop.sh — drive Context Foundry's RPID pipeline over a task queue.
#
# Finds the next unchecked task in TASKS.md whose ID matches a prefix, invokes
# `claude -p` in headless mode with an RPID-triggering prompt, captures per-task
# logs, detects pass/fail by re-reading TASKS.md after each run, and loops
# until either the queue is empty or a task fails twice in a row.
#
# Usage:
#   ./scripts/run-loop.sh                         # defaults to T_FI_A prefix
#   ./scripts/run-loop.sh T_FI_F                  # different task prefix
#   ./scripts/run-loop.sh T_FI_A --max 8          # lower retry budget
#   ./scripts/run-loop.sh T_FI_A --dry-run        # show plan without running
#   ./scripts/run-loop.sh T_FI_A --model opus     # pin the model
#
# Assumes:
#   - pwd is the repo root (script resolves TASKS.md as ./TASKS.md)
#   - claude CLI is on PATH
#   - RPID pipeline defined in ~/.claude/CLAUDE.md
#
# Stops when:
#   - no more unchecked tasks match the prefix  → exit 0
#   - same task fails twice in a row            → exit 1 (abort, investigate)
#   - max iterations hit                        → exit 2 (safety cap)
#   - Ctrl+C                                    → current claude -p exits, script halts

set -euo pipefail

# --- defaults ---

PREFIX="T_FI_A"
MAX_ITER=12
DRY_RUN=false
CLAUDE_MODEL=""
TASKS_FILE="TASKS.md"

# --- parse args ---

while [[ $# -gt 0 ]]; do
  case "$1" in
    --max) MAX_ITER="$2"; shift 2 ;;
    --dry-run) DRY_RUN=true; shift ;;
    --model) CLAUDE_MODEL="$2"; shift 2 ;;
    --tasks) TASKS_FILE="$2"; shift 2 ;;
    --help|-h)
      grep '^#' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    -*)
      echo "unknown flag: $1" >&2
      exit 2
      ;;
    *)
      PREFIX="$1"
      shift
      ;;
  esac
done

# --- prereqs ---

command -v claude >/dev/null 2>&1 || { echo "claude CLI not found on PATH" >&2; exit 2; }
[[ -f "$TASKS_FILE" ]] || { echo "TASKS.md not found at $TASKS_FILE (run from repo root?)" >&2; exit 2; }

REPO_NAME="$(basename "$(pwd)")"
LOG_DIR="$HOME/.foundry/logs/$(date +%Y%m%d-%H%M%S)-${REPO_NAME}-${PREFIX}"
mkdir -p "$LOG_DIR"

# --- prompt template ---
# Single-task RPID invocation. The prompt names the task ID explicitly so
# Claude doesn't have to guess which one is next — the shell loop already
# picked it.

make_prompt() {
  local task_id="$1"
  cat <<EOF
Work task ${task_id} in ${TASKS_FILE}. Run the full RPID pipeline per ~/.claude/CLAUDE.md:

1. Research — read ${task_id}'s description, read relevant source files, write .buildloop/scout-report.md
2. Plan — write .buildloop/current-plan.md with explicit file operations and verification steps
3. Implement — execute the plan, run verification commands, fix failures
4. Write .buildloop/build-claims.md using the Audit Payload Format
5. Doubt — spawn a sub-agent to audit the build-claims; fix HIGH + MEDIUM findings
6. Commit: feat(${task_id}): <summary> on Doubt pass, WIP(${task_id}): <summary> on Doubt fail
7. Mark ${task_id} as [x] with the RPID indicator ([RPID] or [RPID:fast]) in ${TASKS_FILE}

Work exactly this one task, then exit. Do not start the next task even if time remains.
Respect the human gates (G1-G6) declared in ${TASKS_FILE}; mark anything blocked on them as KNOWN_GAPS in the build-claims, do not try to bypass.
EOF
}

# --- helpers ---

find_next_task() {
  # Grab the first unchecked task line matching the prefix, extract the ID.
  grep -oE "^- \[ \] ${PREFIX}[0-9]+\.[0-9]+" "$TASKS_FILE" | head -1 | sed -E 's/^- \[ \] //'
}

task_is_checked() {
  local task_id="$1"
  grep -qE "^- \[x\] ${task_id}" "$TASKS_FILE"
}

count_remaining() {
  grep -cE "^- \[ \] ${PREFIX}[0-9]+\.[0-9]+" "$TASKS_FILE" || true
}

# --- main loop ---

echo "==> foundry loop starting"
echo "    prefix:      ${PREFIX}"
echo "    tasks file:  ${TASKS_FILE}"
echo "    max iter:    ${MAX_ITER}"
echo "    log dir:     ${LOG_DIR}"
echo "    model:       ${CLAUDE_MODEL:-default}"
echo "    dry run:     ${DRY_RUN}"
echo "    pending:     $(count_remaining)"
echo ""

# --- dry-run: enumerate all pending tasks and exit without invoking claude ---

if [[ "$DRY_RUN" == "true" ]]; then
  echo "==> dry-run plan (tasks that WOULD be run, in order):"
  PENDING="$(grep -oE "^- \[ \] ${PREFIX}[0-9]+\.[0-9]+" "$TASKS_FILE" | sed -E 's/^- \[ \] //')"
  if [[ -z "$PENDING" ]]; then
    echo "    (no pending tasks matching ${PREFIX})"
  else
    idx=0
    while IFS= read -r task; do
      idx=$((idx+1))
      printf "    %2d. %s\n" "$idx" "$task"
    done <<< "$PENDING"
    FIRST="$(echo "$PENDING" | head -1)"
    echo ""
    echo "    first task prompt preview:"
    echo "    ---"
    make_prompt "$FIRST" | sed 's/^/    /'
    echo "    ---"
  fi
  echo ""
  echo "==> dry-run complete (no claude invocations, no logs written)"
  rmdir "$LOG_DIR" 2>/dev/null || true
  exit 0
fi

# --- real run ---

PREV_TASK=""
EXIT_CODE=0
i=0

for ((i=1; i<=MAX_ITER; i++)); do
  NEXT="$(find_next_task)"

  if [[ -z "$NEXT" ]]; then
    echo "==> no more pending ${PREFIX} tasks — done"
    break
  fi

  echo "==> [$i/${MAX_ITER}] RPID on ${NEXT}  (remaining: $(count_remaining))"

  # Build claude command.
  # --dangerously-skip-permissions is required for headless RPID: without it,
  # every Write/Edit/Bash permission prompt auto-denies because there is no
  # interactive approver, and the task exits with "blocked writing files".
  CLAUDE_ARGS=(-p "$(make_prompt "$NEXT")" --dangerously-skip-permissions)
  if [[ -n "$CLAUDE_MODEL" ]]; then
    CLAUDE_ARGS=(--model "$CLAUDE_MODEL" "${CLAUDE_ARGS[@]}")
  fi

  START_TS=$(date +%s)
  LOG_FILE="${LOG_DIR}/${NEXT}.log"

  if claude "${CLAUDE_ARGS[@]}" 2>&1 | tee "$LOG_FILE"; then
    CLAUDE_EXIT=0
  else
    CLAUDE_EXIT=$?
  fi

  DURATION=$(( $(date +%s) - START_TS ))

  if task_is_checked "$NEXT"; then
    echo "    PASS: ${NEXT}  (${DURATION}s, log: ${LOG_FILE})"
    PREV_TASK=""  # reset retry tracking on any success
  else
    echo "    FAIL/WIP: ${NEXT}  (${DURATION}s, claude exit ${CLAUDE_EXIT}, log: ${LOG_FILE})"
    if [[ "$PREV_TASK" == "$NEXT" ]]; then
      echo "==> same task failed twice in a row — aborting"
      echo "    investigate: ${LOG_FILE}"
      EXIT_CODE=1
      break
    fi
    PREV_TASK="$NEXT"
  fi
done

if [[ $i -gt $MAX_ITER && -n "$(find_next_task)" ]]; then
  echo "==> max iterations (${MAX_ITER}) reached without draining queue"
  echo "    remaining: $(count_remaining)"
  EXIT_CODE=2
fi

echo ""
echo "==> loop finished"
echo "    logs: ${LOG_DIR}"
exit $EXIT_CODE
