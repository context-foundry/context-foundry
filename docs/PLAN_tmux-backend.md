# Plan: Tmux Agent Backend

Date: 2026-03-20
Version: v1
Status: planning

## Context

Context Foundry spawns each SPID stage as a separate `claude` CLI process via `portable_pty` (agent.rs:558-801). This works but has limitations:

1. **Sessions die with the TUI** -- if Foundry crashes or is killed, all in-flight agents die immediately. Checkpoint recovery restarts from scratch.
2. **No live inspection** -- the user can only see agent output through the TUI's filtered view. No way to attach to a running agent's terminal.
3. **No session persistence** -- a crashed builder loses all in-flight context. The Doubt stage must re-run the full build.

Tmux solves all three: sessions persist independently, the user can `tmux attach` to watch/interact, and crash recovery can reconnect to still-running agents.

## Current State

### Agent spawning (agent.rs)

`run_agent()` at line 558 is the primary entry point. Two paths:

- **Codex path** (lines 558-627): calls `run_provider_session()` with retry loop and rate-limit fallback to Claude
- **Claude path** (lines 633-794): creates PTY via `portable_pty::native_pty_system().openpty()`, spawns `claude -p "..." --output-format stream-json`, monitors via `child.try_wait()` polling every 500ms

Output flows through:
- `read_pty_output()` (lines 813-893) runs in `tokio::spawn_blocking`, parses JSON lines, sends `AgentOutputEvent` variants over `mpsc::UnboundedSender`
- Log file written to `{log_dir}/{role}-{timestamp}.jsonl`

Key types:
- `AgentRole` enum: Scout, Planner, Builder, Reviewer, Fixer, Discovery
- `AgentResult` struct: success, exit_code, exit_kind (Completed/Failed/Cancelled/TimedOut/TransportStall), failure_message
- `AgentOutputEvent` enum: Text, ToolUse, ToolResult, Stderr, Result, Usage

### Config (config.rs)

Per-role provider/model settings already exist (e.g., `builder_provider`, `builder_model`). Config loads from `~/.foundry/config.json` (global) merged with `.foundry.json` (project-local).

### Build loop (build.rs)

All `run_agent()` calls follow the same pattern (e.g., line 2725):
```rust
let result = agent::run_agent(
    &AgentRole::Builder,
    Config::parse_provider(&ctx.config.builder_provider),
    &ctx.config.builder_model,
    &prompt,
    &ctx.project_dir,
    agent_tx,
    &ctx.log_dir,
    None,  // allowed_tools
    ctx.config.agent_timeout_secs,
    Some(ctx.shutdown.clone()),
).await;
```

## Implementation Plan

### Architecture decision: Backend dispatch inside run_agent()

Add an `AgentBackend` enum and dispatch internally. The `run_agent()` signature stays the same -- backend selection is config-driven, not caller-driven. This means zero changes to build.rs, review.rs, or any call site.

```rust
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum AgentBackend {
    #[default]
    Pty,
    Tmux,
}
```

Inside `run_agent()`, read `config.agent_backend` and dispatch:
```rust
let backend = AgentBackend::from_config(&config);
match backend {
    AgentBackend::Pty => run_agent_pty(role, provider, model, prompt, ...).await,
    AgentBackend::Tmux => run_agent_tmux(role, provider, model, prompt, ...).await,
}
```

### T1.1: Core tmux backend

**New file: `src/tmux.rs`** -- TmuxSession struct and all tmux subprocess wrappers.

```rust
pub struct TmuxSession {
    pub name: String,          // "foundry-builder-20260320-143000"
    pub project_dir: PathBuf,
    pub created_at: Instant,
}

impl TmuxSession {
    pub fn create(prefix: &str, role: &AgentRole, project_dir: &Path) -> Result<Self>;
    pub fn send_keys(&self, command: &str) -> Result<()>;
    pub fn capture_pane(&self, lines: i32) -> Result<String>;
    pub fn is_alive(&self) -> bool;
    pub fn kill(&self) -> Result<()>;
}
```

All methods shell out to tmux via `std::process::Command`:
- `create()`: `tmux new-session -d -s {name} -x 4096 -y 24 -c {project_dir}`
- `send_keys()`: `tmux send-keys -t {name} "{command}" Enter`
- `capture_pane()`: `tmux capture-pane -t {name} -p -S -{lines}`
- `is_alive()`: `tmux has-session -t {name}` (exit code 0 = alive)
- `kill()`: `tmux kill-session -t {name}`

Session naming: `{prefix}-{role_slug}-{timestamp}` where prefix defaults to "foundry".

**New function: `run_agent_tmux()`** in agent.rs (or tmux.rs):

1. Create TmuxSession
2. Build the same claude CLI command string as the PTY path
3. `session.send_keys(&cli_command)`
4. Enter polling loop (same 500ms interval as PTY):
   - `session.capture_pane(1000)` to get current output
   - Diff against previous capture to find new lines
   - Parse new lines with existing `parse_claude_json()`
   - Send `AgentOutputEvent` variants over the channel
   - Write new lines to log file
   - Check idle timeout (no new lines for `timeout_secs`)
   - Check hard deadline (`timeout_secs * 4`)
   - Check shutdown flag
5. On completion/timeout/shutdown:
   - If `keep_sessions` is false: `session.kill()`
   - If true: leave session alive, log the session name
6. Return `AgentResult`

**Diff tracking for capture_pane:**

Tmux `capture-pane` returns the full visible buffer. To detect new output:
- Track `last_line_count: usize` and `last_content_hash: u64`
- On each poll: capture, split by newlines, compare count and hash
- New lines = lines[last_line_count..]
- Edge case: scrollback overflow (buffer wraps). Use `-S -` for full history or accept some loss.

Better approach: use `tmux pipe-pane -t {name} "cat >> {log_file}"` at session creation. This streams all output to a file. The polling loop then reads the file (tail -f style) instead of capture-pane. This is more reliable and avoids diff tracking entirely.

**Config additions to `config.rs`:**

```rust
/// Agent execution backend: "pty" (default) or "tmux"
#[serde(default = "default_agent_backend")]
pub agent_backend: String,

/// Tmux session name prefix (default: "foundry")
#[serde(default = "default_tmux_prefix")]
pub tmux_session_prefix: String,

/// Keep tmux sessions alive after agent completion (default: false)
#[serde(default)]
pub tmux_keep_sessions: bool,
```

**Tests:**

Unit tests (mocked subprocess):
- TmuxSession::create builds correct tmux command
- send_keys escapes special characters
- capture_pane parses output correctly
- kill sends correct command
- Session naming follows prefix-role-timestamp pattern

Integration tests (real tmux, `#[ignore]` by default):
- Create session, send echo, capture output, verify, kill
- Timeout triggers kill
- Shutdown flag triggers kill
- Output events match expected AgentOutputEvent variants

### T1.2: Wire into pipeline and add TUI session list

**Changes to agent.rs:**

Extract current PTY code into `run_agent_pty()` (pure rename/move, no logic changes). Add dispatch in `run_agent()` based on config.

**No changes to build.rs, review.rs, or any call site.** The dispatch is internal to `run_agent()`.

**TUI addition:**

Add a 'tmux' info line to the dashboard view (Phase T3.4 already built this) showing:
- Active tmux sessions: count and names
- "Attach: tmux attach -t {name}" hint for the current agent

**Config validation at startup:**

In `src/app/startup.rs` or `src/config.rs`:
- If `agent_backend == "tmux"`, check that `tmux` binary exists (`which tmux`)
- If not found, show warning and fall back to PTY
- Log the active backend at session start

**Integration test:**

End-to-end: config `agent_backend: "tmux"`, run a Scout stage against a trivial project, verify:
- Tmux session was created
- Output events arrived on the channel
- Scout report was written
- Session was cleaned up (or left alive if keep_sessions)

## Dependencies

No new crate dependencies. All tmux interaction is via `std::process::Command`. The `shell-escape` crate could help with argument quoting but isn't strictly necessary if we control the command construction.

## Risks & Open Questions

1. **Output buffering in tmux**: Claude CLI's `--output-format stream-json` should still line-buffer since tmux allocates a PTY for the child process. Need to verify this -- if tmux doesn't allocate a PTY, Node.js will block-buffer and we'll get delayed output. (Likely fine: tmux always creates a PTY for the session.)

2. **Pipe-pane reliability**: `tmux pipe-pane` is the most reliable output capture method but has a race condition at session startup -- if we pipe before sending the command, we might miss the first few bytes. Solution: pipe first, then send-keys.

3. **Session cleanup on crash**: If Foundry crashes, tmux sessions persist (that's the point). But on next startup, stale sessions from a previous run should be detected and optionally cleaned up. Could check for `foundry-*` sessions at startup.

4. **Windows support**: tmux doesn't exist on Windows. The PTY backend remains the default and the only option on Windows. Config validation should handle this.

5. **Codex path**: The Codex provider path in `run_agent()` (lines 558-627) has its own retry logic before falling through to `run_provider_session()`. The tmux backend should handle Codex the same way -- the CLI command is different (`codex` vs `claude`) but the session lifecycle is identical.

## Constraints

- `run_agent()` public signature must not change (backward compat for all call sites)
- All existing tests must pass unchanged
- PTY backend remains the default -- tmux is opt-in via config
- Session names must not collide across concurrent Foundry instances (timestamp component handles this)
