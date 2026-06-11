#!/usr/bin/env bash
# run-loop.sh v0.9 — Ralph Wiggum loop for the RPID pipeline. https://ghuntley.com/ralph/
#
# Usage:
#   ./scripts/run-loop.sh                                  # claude (default)
#   ./scripts/run-loop.sh --full-auto                      # bootstrap + discover forever
#   ./scripts/run-loop.sh --provider lmstudio --model ID   # local via LM Studio
#   ./scripts/run-loop.sh --provider gemini                # Google Gemini CLI
#   ./scripts/run-loop.sh --provider codex                 # OpenAI Codex CLI
#   ./scripts/run-loop.sh --provider copilot               # GitHub Copilot (gh)
#   ./scripts/run-loop.sh --provider custom --agent-bin X  # bring your own binary
#   ./scripts/run-loop.sh --base-url URL --api-key KEY     # override endpoint/key
#   ./scripts/run-loop.sh --max 8                          # stop after 8 tasks
#   ./scripts/run-loop.sh --dry-run                        # show plan, don't run
#   ./scripts/run-loop.sh --tasks F                        # custom tasks file
#
# Full Auto mode (--full-auto):
#   - If no TASKS.md exists, bootstraps by exploring the repo and creating it
#   - When the queue drains, runs discovery to find new work and keeps going
#   - Runs until Ctrl+C, a failure streak, or --max is reached
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

_logo(){ cat <<'EOF'
███████╗ ██████╗ ██╗   ██╗███╗   ██╗██████╗ ██████╗ ██╗   ██╗
██╔════╝██╔═══██╗██║   ██║████╗  ██║██╔══██╗██╔══██╗╚██╗ ██╔╝
█████╗  ██║   ██║██║   ██║██╔██╗ ██║██║  ██║██████╔╝ ╚████╔╝
██╔══╝  ██║   ██║██║   ██║██║╚██╗██║██║  ██║██╔══██╗  ╚██╔╝
██║     ╚██████╔╝╚██████╔╝██║ ╚████║██████╔╝██║  ██║   ██║
╚═╝      ╚═════╝  ╚═════╝ ╚═╝  ╚═══╝╚═════╝ ╚═╝  ╚═╝   ╚═╝

██╗      ██████╗  ██████╗ ██████╗
██║     ██╔═══██╗██╔═══██╗██╔══██╗
██║     ██║   ██║██║   ██║██████╔╝
██║     ██║   ██║██║   ██║██╔═══╝
███████╗╚██████╔╝╚██████╔╝██║
╚══════╝ ╚═════╝  ╚═════╝ ╚═╝

------------------------------------------------------------
               v0.9 · RPID Pipeline Runner
------------------------------------------------------------
EOF
}

MAX_ITER=""; DRY_RUN=false; CLAUDE_MODEL=""; TASKS_FILE="TASKS.md"
PROVIDER="claude"; BASE_URL=""; API_KEY=""; AGENT_BIN=""; FULL_AUTO=false
_SPIN_CHARS=(⠋ ⠙ ⠹ ⠸ ⠼ ⠴ ⠦ ⠧ ⠇ ⠏)

while [[ $# -gt 0 ]]; do
  case "$1" in
    --max)       MAX_ITER="$2";     shift 2;; --dry-run)   DRY_RUN=true;   shift;;
    --model)     CLAUDE_MODEL="$2"; shift 2;; --tasks)     TASKS_FILE="$2"; shift 2;;
    --provider)  PROVIDER="$2";     shift 2;; --base-url)  BASE_URL="$2";   shift 2;;
    --api-key)   API_KEY="$2";      shift 2;; --agent-bin) AGENT_BIN="$2";  shift 2;;
    --full-auto) FULL_AUTO=true;    shift;;
    -h|--help) _logo; sed -n '/^# /s/^# //p' "$0"; exit 0;;
    *) echo "unknown: $1" >&2; exit 2;;
  esac
done

_agent_bin() {
  case "$PROVIDER" in
    claude|lmstudio|custom) echo "${AGENT_BIN:-claude}";;
    gemini)  echo "${AGENT_BIN:-gemini}";;
    codex)   echo "${AGENT_BIN:-codex}";;
    copilot)
      if [[ -n "$AGENT_BIN" ]]; then echo "$AGENT_BIN"
      elif command -v foundry >/dev/null 2>&1; then echo "foundry"
      else
        # Auto-discover: prefer a foundry binary co-located with this script
        local _sd; _sd="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        echo "${_sd}/../target/release/foundry"
      fi;;
    *) echo "unknown provider: $PROVIDER (claude|lmstudio|gemini|codex|copilot|custom)" >&2; exit 2;;
  esac
}
_BIN=$(_agent_bin)
command -v "$_BIN" >/dev/null 2>&1 || { echo "$_BIN not on PATH" >&2; exit 2; }

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

next_task()  { grep -oE '\- \[ \] [A-Z][0-9]+\.[0-9]+' "$TASKS_FILE" 2>/dev/null | head -1 | sed 's/- \[ \] //' || true; }
checked()    { grep -qE "^\- \[x\] $1" "$TASKS_FILE"; }
pending_cnt(){ grep -cE '\- \[ \] [A-Z][0-9]+\.[0-9]+' "$TASKS_FILE" 2>/dev/null || true; }
_task_desc() {
  grep -E "^\- \[ \] ${1}[: ]" "$TASKS_FILE" 2>/dev/null | head -1 \
    | sed "s/^- \[ \] ${1}[: ]*//" | sed 's/ \[RPID[^]]*\]$//' \
    | cut -c1-48 | sed 's/[[:space:]]*[-—]*$//' || true
}
_next_after_current() {
  grep -oE '\- \[ \] [A-Z][0-9]+\.[0-9]+' "$TASKS_FILE" 2>/dev/null \
    | sed 's/- \[ \] //' | sed -n '2p' || true
}

# _spin_while LABEL DESC PID START [NEXT_TASK]
_spin_while() {
  local label="$1" desc="$2" pid="$3" start="$4" next="${5:-}"
  local i=0 lines=0 elapsed spin
  while kill -0 "$pid" 2>/dev/null; do
    spin="${_SPIN_CHARS[$(( i % ${#_SPIN_CHARS[@]} ))]}"
    i=$(( i + 1 ))
    elapsed=$(( $(date +%s) - start ))
    [[ $lines -gt 0 ]] && printf "\033[%dA" $lines
    printf "\r\033[2K  \033[1;33m%s\033[0m  \033[1;36m%s\033[0m" "$spin" "$label"
    [[ -n "$desc" ]] && printf "  \033[2m%s\033[0m" "$desc"
    printf "\n\r\033[2K     "
    [[ -n "$next" ]] && printf "\033[2mnext \033[0m\033[36m%s\033[0m  " "$next"
    printf "\033[2m%s  %ds  ^C to cancel\033[0m" "${CLAUDE_MODEL:-$PROVIDER}" "$elapsed"
    lines=1
    sleep 0.1
  done
  [[ $lines -gt 0 ]] && printf "\033[%dA\r\033[J" $lines || printf "\r\033[2K"
}

run_agent() {
  local prompt="$1" bin args
  case "$PROVIDER" in
    claude)
      bin="${AGENT_BIN:-claude}"
      [[ -n "$BASE_URL" ]] && export ANTHROPIC_BASE_URL="$BASE_URL"
      [[ -n "$API_KEY" ]]  && export ANTHROPIC_API_KEY="$API_KEY"
      args=(-p "$prompt" --dangerously-skip-permissions)
      [[ -n "$CLAUDE_MODEL" ]] && args=(--model "$CLAUDE_MODEL" "${args[@]}")
      ;;
    lmstudio)
      bin="${AGENT_BIN:-claude}"
      export ANTHROPIC_BASE_URL="${BASE_URL:-http://localhost:1234}"
      export ANTHROPIC_API_KEY="${API_KEY:-lm-studio}"
      args=(-p "$prompt" --dangerously-skip-permissions)
      [[ -n "$CLAUDE_MODEL" ]] && args=(--model "$CLAUDE_MODEL" "${args[@]}")
      ;;
    gemini)
      bin="${AGENT_BIN:-gemini}"
      [[ -n "$BASE_URL" ]] && export GOOGLE_API_ENDPOINT="$BASE_URL"
      [[ -n "$API_KEY" ]]  && export GEMINI_API_KEY="$API_KEY"
      args=(-p "$prompt" --yolo)
      [[ -n "$CLAUDE_MODEL" ]] && args=(--model "$CLAUDE_MODEL" "${args[@]}")
      ;;
    codex)
      bin="${AGENT_BIN:-codex}"
      [[ -n "$BASE_URL" ]] && export OPENAI_BASE_URL="$BASE_URL"
      [[ -n "$API_KEY" ]]  && export OPENAI_API_KEY="$API_KEY"
      args=(-p "$prompt" --full-auto)
      [[ -n "$CLAUDE_MODEL" ]] && args=(--model "$CLAUDE_MODEL" "${args[@]}")
      ;;
    copilot)
      # Copilot is native to the foundry binary — unreachable; delegation happens
      # before the main loop via _run_copilot_delegate().
      echo "internal error: run_agent called for copilot provider" >&2; exit 2;;

    custom)
      bin="${AGENT_BIN:?--agent-bin required for provider=custom}"
      [[ -n "$BASE_URL" ]] && export ANTHROPIC_BASE_URL="$BASE_URL"
      [[ -n "$API_KEY" ]]  && export ANTHROPIC_API_KEY="$API_KEY"
      args=(-p "$prompt")
      [[ -n "$CLAUDE_MODEL" ]] && args=(--model "$CLAUDE_MODEL" "${args[@]}")
      ;;
  esac
  "$bin" "${args[@]}"
}

_research_bootstrap() {
  local start; start=$(date +%s)
  local prompt="You are running the Research (R) stage of the RPID pipeline for this repository.

Repository: $(pwd)

Steps:
1. Read CLAUDE.md, README.md, SPEC.md if they exist.
2. Detect the tech stack from project files (package.json, Cargo.toml, go.mod, etc.).
3. Explore the source code to understand what this project does and its current state.
4. Create ${TASKS_FILE} with a research notes section followed by tasks:

## Research Notes
**Tech Stack:** ...
**Key Files:** ...
**Architecture:** ...
**Risks:** ...

## Tasks

- [ ] T1.1: Description of first task
- [ ] T1.2: Description of second task

Task rules:
- Number tasks T1.1, T1.2, T1.3...
- Each task should be a substantial unit of work that runs through a full RPID pipeline
- Be specific: 'add error handling to X in Y.rs:42' not 'improve error handling'
- Write ${TASKS_FILE} then exit. Do not write a separate research-report.md."

  set +e
  run_agent "$prompt" >"$LOG_DIR/research-bootstrap.log" 2>&1 & local bpid=$!
  _spin_while "Research" "exploring repo, generating ${TASKS_FILE}..." "$bpid" "$start"
  wait $bpid; set -e
}

_research_discover() {
  local round="$1" start; start=$(date +%s)
  local prompt="You are running the Research (R) stage of RPID — Discovery Round ${round}.
All current tasks in ${TASKS_FILE} are complete. Find new work.

Repository: $(pwd)

Steps:
1. Review completed tasks in ${TASKS_FILE} to understand what has already been done.
2. Read the current state of the codebase — it has changed since the last research pass.
3. Identify new bugs, missing tests, documentation gaps, performance issues, or unbuilt features.
4. Append to ${TASKS_FILE}:

## Discovery Round ${round}
**New Findings:** one-line summary of what changed or what you found

- [ ] D${round}.1: Description
- [ ] D${round}.2: Description

Task rules:
- Number tasks D${round}.1, D${round}.2...
- Do NOT re-add tasks already marked done
- If you genuinely find nothing new, write '## Discovery Round ${round} — No New Tasks' and exit
- Be specific about what needs to change and where
- Append to ${TASKS_FILE} then exit. Do not write a separate research-report.md."

  set +e
  run_agent "$prompt" >"$LOG_DIR/research-r${round}.log" 2>&1 & local dpid=$!
  _spin_while "Research" "discovery round ${round} — scanning for new work..." "$dpid" "$start"
  wait $dpid; set -e
}

# _run_copilot_delegate — delegates the entire loop to `foundry run --no-tui`
# with the ghcopilot provider patched into .foundry.json.  Called instead of
# the main while-loop when --provider copilot is active.
_run_copilot_delegate() {
  local bin="${_BIN}" json=".foundry.json"
  local original="" model="${CLAUDE_MODEL:-ghcopilot:claude-sonnet-4.6}"

  [[ -f "$json" ]] && original=$(cat "$json")

  # Restore .foundry.json on exit / Ctrl-C
  _cop_restore() {
    if [[ -n "$original" ]]; then printf '%s\n' "$original" > "$json"
    else rm -f "$json"; fi
  }
  trap '_cop_restore' EXIT INT TERM

  # Merge ghcopilot provider onto existing config; keep other settings intact.
  # If run_mode is "auto" (loops forever) demote it to "sprint" (drain then stop).
  if command -v jq >/dev/null 2>&1; then
    { [[ -n "$original" ]] && echo "$original" || echo '{}'; } \
    | jq --arg p "ghcopilot" --arg m "$model" \
         '. + {builder_provider: $p, builder_model: $m}
          | if (.run_mode // "auto") == "auto" then .run_mode = "sprint" else . end' \
    > "$json"
  else
    # No jq: write a minimal config (loses other .foundry.json settings)
    printf '{"builder_provider":"ghcopilot","builder_model":"%s","run_mode":"sprint"}\n' \
      "$model" > "$json"
    [[ -n "$original" ]] && \
      echo "    Warning: jq not found — other .foundry.json settings not preserved" >&2
  fi

  [[ -n "$API_KEY" ]] && export GH_TOKEN="$API_KEY"
  [[ -n "$MAX_ITER" ]] && echo "    Note: --max is not supported with --provider copilot" >&2
  [[ "$TASKS_FILE" != "TASKS.md" ]] && \
    echo "    Note: --tasks is not supported with --provider copilot; foundry uses TASKS.md" >&2

  echo "==> Copilot — foundry run --no-tui (ghcopilot / $(basename "$json") patched)"
  echo ""

  "$bin" run --no-tui; local rc=$?

  _cop_restore
  trap - EXIT INT TERM
  return $rc
}

# ── Startup ──────────────────────────────────────────────────────────────────

_logo
echo "==> Foundry Loop Starting"
echo ""
printf "    %-12s %s\n" "Tasks"     "$TASKS_FILE"
printf "    %-12s %s\n" "Max"       "${MAX_ITER:-Unlimited}"
printf "    %-12s %s\n" "Provider"  "$PROVIDER"
printf "    %-12s %s\n" "Model"     "${CLAUDE_MODEL:-Default}"
printf "    %-12s %s\n" "Full Auto" "$FULL_AUTO"
[[ -n "$BASE_URL" ]] && printf "    %-12s %s\n" "Base URL" "$BASE_URL"
echo ""

if [[ "$DRY_RUN" == true ]]; then
  if [[ -f "$TASKS_FILE" ]]; then
    echo "==> Pending Tasks:"
    grep -E '\- \[ \] [A-Z][0-9]+\.[0-9]+' "$TASKS_FILE" 2>/dev/null \
      | sed 's/- \[ \] /    /' || echo "    (none)"
    FIRST=$(next_task)
    [[ -n "$FIRST" ]] && { echo ""; echo "    First Prompt Preview:"; prompt_for "$FIRST" | sed 's/^/    /'; }
  else
    echo "    No ${TASKS_FILE} — run with --full-auto to bootstrap automatically"
  fi
  exit 0
fi

mkdir -p "$LOG_DIR"
printf "    %-12s %s\n" "Log Dir" "$LOG_DIR"
echo ""

# Bootstrap if no task file
if [[ ! -f "$TASKS_FILE" ]]; then
  if [[ "$FULL_AUTO" == false ]]; then
    printf "    %s not found — use --full-auto to bootstrap automatically\n" "$TASKS_FILE" >&2
    exit 2
  fi
  echo "==> No ${TASKS_FILE} Found — Running Research (R)"
  _research_bootstrap
  if [[ ! -f "$TASKS_FILE" ]]; then
    echo "==> Bootstrap Did Not Create ${TASKS_FILE} — Check $LOG_DIR/bootstrap.log" >&2
    exit 2
  fi
  echo "==> Bootstrap Complete — $(pending_cnt) Task(s) Ready"
  echo ""
else
  printf "    %-12s %s\n" "Pending" "$(pending_cnt)"
  echo ""
fi

# ── Main Loop ─────────────────────────────────────────────────────────────────

# Copilot uses foundry's native ghcopilot integration — delegate the full loop.
[[ "$PROVIDER" == "copilot" ]] && { _run_copilot_delegate; exit $?; }

FAIL_STREAK=0
EXIT_CODE=0
i=0
DISCOVERY_ROUND=0

while true; do
  TASK=$(next_task)

  if [[ -z "$TASK" ]]; then
    if [[ "$FULL_AUTO" == false ]]; then
      echo "==> No More Tasks — Done"
      break
    fi
    DISCOVERY_ROUND=$(( DISCOVERY_ROUND + 1 ))
    echo ""
    echo "==> Queue Empty — Research Round ${DISCOVERY_ROUND} (R)"
    _research_discover "$DISCOVERY_ROUND"
    TASK=$(next_task)
    if [[ -z "$TASK" ]]; then
      echo "==> Discovery Found No New Tasks — Done"
      break
    fi
    echo "==> Found $(pending_cnt) New Task(s)"
    echo ""
    continue
  fi

  i=$(( i + 1 ))
  ITER_LABEL="[$i${MAX_ITER:+/$MAX_ITER}]"
  echo "==> $ITER_LABEL RPID On $TASK (Remaining: $(pending_cnt))"

  START=$(date +%s); LOG="$LOG_DIR/$TASK.log"
  set +e
  run_agent "$(prompt_for "$TASK")" >"$LOG" 2>&1 & _PID=$!
  _spin_while "$TASK" "$(_task_desc "$TASK")" "$_PID" "$START" "$(_next_after_current)"
  wait $_PID; CL_EXIT=$?; set -e
  DURATION=$(( $(date +%s) - START ))

  if checked "$TASK"; then
    echo "    PASS: $TASK (${DURATION}s)"
    FAIL_STREAK=0
  else
    FAIL_STREAK=$(( FAIL_STREAK + 1 ))
    echo "    FAIL/WIP: $TASK (${DURATION}s, exit=$CL_EXIT, streak=$FAIL_STREAK)"
    [[ $FAIL_STREAK -ge 2 ]] && { echo "==> 2 Consecutive Failures — Aborting"; EXIT_CODE=1; break; }
  fi

  [[ -n "$MAX_ITER" && $i -ge $MAX_ITER ]] && { echo "==> Max Iterations ($MAX_ITER) Reached"; EXIT_CODE=2; break; }
done

echo ""
echo "==> Loop Finished"
printf "    %-12s %s\n" "Logs" "$LOG_DIR"
exit $EXIT_CODE
