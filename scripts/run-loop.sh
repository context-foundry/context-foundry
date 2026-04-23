#!/usr/bin/env bash
# run-loop.sh v0.8 — Ralph Wiggum loop for the RPID pipeline. https://ghuntley.com/ralph/
#
# Usage:
#   ./scripts/run-loop.sh              # run all unchecked tasks until queue is empty
#   ./scripts/run-loop.sh --max 8      # stop after 8 tasks (default: unlimited)
#   ./scripts/run-loop.sh --dry-run    # show plan without running
#   ./scripts/run-loop.sh --model opus # pin the model
#   ./scripts/run-loop.sh --tasks F    # custom tasks file
#
# Install (Mac/Linux):
#   sudo ln -s /path/to/run-loop.sh /usr/local/bin/foundry-loop
#
# Install (Windows — WSL):
#   ln -s /mnt/c/path/to/run-loop.sh ~/.local/bin/foundry-loop
#
# Install (Windows — Git Bash, add to ~/.bashrc):
#   alias foundry-loop='/c/path/to/run-loop.sh'
#
# Exit codes: 0=queue drained, 1=task failed twice, 2=max iter reached

set -euo pipefail

MAX_ITER=""; DRY_RUN=false; CLAUDE_MODEL=""; TASKS_FILE="TASKS.md"; _S='/-\|'

while [[ $# -gt 0 ]]; do
  case "$1" in
    --max) MAX_ITER="$2"; shift 2;; --dry-run) DRY_RUN=true; shift;;
    --model) CLAUDE_MODEL="$2"; shift 2;; --tasks) TASKS_FILE="$2"; shift 2;;
    -h|--help) sed -n '/^# /s/^# //p' "$0"; exit 0;;
    *) echo "unknown: $1" >&2; exit 2;;
  esac
done

command -v claude >/dev/null 2>&1 || { echo "claude not on PATH" >&2; exit 2; }
[[ -f "$TASKS_FILE" ]] || { echo "$TASKS_FILE not found (run from repo root?)" >&2; exit 2; }

LOG_DIR="$HOME/.foundry/logs/$(date +%Y%m%d-%H%M%S)-$(basename "$(pwd)")"

prompt_for() {
  local tid="$1"
  printf 'Work task %s in %s. Run full RPID pipeline per ~/.claude/CLAUDE.md:\n\n' "$tid" "$TASKS_FILE"
  printf '1. Research — read %s description, write .buildloop/research-report.md\n' "$tid"
  printf '2. Plan — write .buildloop/current-plan.md with explicit file ops\n'
  printf '3. Implement — execute plan, run verification, fix failures\n'
  printf '4. Write .buildloop/build-claims.md (Audit Payload Format)\n'
  printf '5. Doubt — spawn sub-agent to audit; fix HIGH+MEDIUM findings\n'
  printf '6. Commit: feat(%s): <summary> on pass, WIP(%s): <summary> on fail\n' "$tid" "$tid"
  printf '7. Mark %s as [x] with [RPID] or [RPID:fast] in %s\n\n' "$tid" "$TASKS_FILE"
  printf 'Work exactly this one task, then exit.\n'
}

next_task() { grep -oE '\- \[ \] [A-Z][0-9]+\.[0-9]+' "$TASKS_FILE" 2>/dev/null | head -1 | sed 's/- \[ \] //' || true; }
checked()   { grep -qE "^\- \[x\] $1" "$TASKS_FILE"; }
pending_cnt(){ grep -cE '\- \[ \] [A-Z][0-9]+\.[0-9]+' "$TASKS_FILE" 2>/dev/null || echo 0; }

echo "==> foundry loop starting"
echo "    tasks: $TASKS_FILE | max: ${MAX_ITER:-unlimited} | pending: $(pending_cnt)"
echo "    model: ${CLAUDE_MODEL:-default}"
echo ""

if [[ "$DRY_RUN" == true ]]; then
  echo "==> pending tasks:"
  grep -E '\- \[ \] [A-Z][0-9]+\.[0-9]+' "$TASKS_FILE" 2>/dev/null | sed 's/- \[ \] /    /' || echo "    (none)"
  FIRST=$(next_task)
  [[ -n "$FIRST" ]] && { echo ""; echo "    First prompt preview:"; prompt_for "$FIRST" | sed 's/^/    /'; }
  exit 0
fi

mkdir -p "$LOG_DIR"
echo "    log dir: $LOG_DIR"

FAIL_STREAK=0
EXIT_CODE=0
i=0

while true; do
  i=$((i+1))
  TASK=$(next_task)
  [[ -z "$TASK" ]] && { echo "==> no more tasks — done"; break; }

  ITER_LABEL="[$i${MAX_ITER:+/$MAX_ITER}]"
  echo "==> $ITER_LABEL RPID on $TASK (remaining: $(pending_cnt))"

  ARGS=(-p "$(prompt_for "$TASK")" --dangerously-skip-permissions)
  [[ -n "$CLAUDE_MODEL" ]] && ARGS=(--model "$CLAUDE_MODEL" "${ARGS[@]}")

  START=$(date +%s); LOG="$LOG_DIR/$TASK.log"
  set +e; claude "${ARGS[@]}" >"$LOG" 2>&1 & _PID=$!
  _i=0; while kill -0 $_PID 2>/dev/null; do printf "\r  ${_S:$((_i++%4)):1}  %s" "$TASK"; sleep 0.1; done
  wait $_PID; CL_EXIT=$?; set -e; printf "\r%-60s\r" " "
  DURATION=$(( $(date +%s) - START ))

  if checked "$TASK"; then
    echo "    PASS: $TASK (${DURATION}s)"
    FAIL_STREAK=0
  else
    FAIL_STREAK=$((FAIL_STREAK+1))
    echo "    FAIL/WIP: $TASK (${DURATION}s, exit=$CL_EXIT, streak=$FAIL_STREAK)"
    [[ $FAIL_STREAK -ge 2 ]] && { echo "==> 2 consecutive failures — aborting"; EXIT_CODE=1; break; }
  fi

  [[ -n "$MAX_ITER" && $i -ge $MAX_ITER ]] && { echo "==> max iterations ($MAX_ITER) reached"; EXIT_CODE=2; break; }
done

echo ""; echo "==> loop finished | logs: $LOG_DIR"
exit $EXIT_CODE
