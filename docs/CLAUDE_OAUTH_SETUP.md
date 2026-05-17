# Claude OAuth / Subscription Setup on this VPS

Audience: the engineer (human or agent) designing the Context Foundry backend
APIs that Knowmler will call to build apps.

Read this before adding any provider, API-key, or "Azure" setting to that
backend. The goal of this document is simple: **the new backend must not break
the way Claude is already billed on this machine.**

## TL;DR (the one rule)

Every Claude call on this VPS rides a **Claude subscription** through the
`claude` CLI's **OAuth login**. It does **not** use a pay-per-token
`ANTHROPIC_API_KEY`. Two separate tools depend on this, the same way:

- **Knowmler** (the app) calls `claude` for prototype generation and the
  idea-assist chat.
- **Context Foundry** (the build tool) spawns `claude` agents to build tasks.

If anything sets `ANTHROPIC_API_KEY` (or the other override variables listed
below) in an environment that a `claude` process inherits, **every** Claude
call on the box silently switches to metered API billing. Do not let the new
backend do that. Its API / Azure provider must be a separate, opt-in code path
whose credentials never reach the `claude` CLI's environment.

## How authentication works today

### The credential store

- The `claude` CLI is installed at `~/.local/bin/claude` (currently v2.1.x) and
  is logged in to a Claude subscription.
- The login is stored in **`~/.claude/.credentials.json`** (mode `600`, owned
  by `chuck`). Its shape is:

  ```
  { "claudeAiOauth": { "accessToken", "refreshToken", "expiresAt",
                        "scopes", "subscriptionType", "rateLimitTier" } }
  ```

  This is an **OAuth token pair**, not an API key. The CLI refreshes
  `accessToken` automatically using `refreshToken` and rewrites this file when
  the token nears expiry. That automatic rewrite is normal and must keep
  working; it is the only thing that should ever write to this file.

- `~/.claude/settings.json` holds CLI behavior settings only. It currently has
  **no `env` block and no `apiKeyHelper`**, so it injects no credentials. Keep
  it that way.
- `~/.claude.json` holds the logged-in `oauthAccount` and assorted Claude Code
  state. Not a secret store; do not edit it programmatically.
- `~/.claude/backups/` already exists and holds credential backups.

### How each tool reaches Claude (same pattern, two tools)

**Context Foundry** runs as the host user `chuck`. Its Rust orchestrator spawns
`claude` (Claude Code) processes directly. Because they run as `chuck`, they
read `~/.claude/` automatically and authenticate as the subscription. Nothing
special is configured; it just inherits the user's login.

**Knowmler** runs in Docker. Its backend container reaches the same
subscription by **bind-mounting the host's `~/.claude` into the container**:

- `knowmler/docker-compose.yml`: `~/.claude:/home/appuser/.claude`
- `knowmler/docker-compose.local.yml`: `~/.claude:/home/appuser/.claude`

The mount is read-write on purpose (the CLI writes debug logs and refreshes the
token). Inside the container, `backend/app/services/claude_provider.py` shells
out to the `claude` binary (`claude --print --permission-mode
bypassPermissions --strict-mcp-config --tools "" --model <model>
--max-turns 1`). That provider **never reads or sets an API key** -- it only
runs the CLI. `LLM_PROVIDER=claude` is set; the compose file even comments
"Claude CLI runs directly in container, no API key needed."

Knowmler's provider also supports an optional HTTP "bridge" mode via a
`CLAUDE_BRIDGE_URL` env var. That is **not configured here**, so Knowmler is in
direct mode. If a bridge is ever introduced it must itself ride the same
`~/.claude` OAuth login; it does not change the rule.

### Current state, verified

- No `ANTHROPIC_API_KEY` (or any `ANTHROPIC_*` / `CLAUDE_CODE_USE_*`) variable
  in the shell environment.
- No such variable in `knowmler/.env`, `knowmler/.env.staging`, or any
  `knowmler` compose file.
- No API key in `~/.claude/settings.json`.
- Context Foundry's Rust source contains no `ANTHROPIC_API_KEY` handling.

The setup is clean. The job of the new backend is to keep it clean.

## What would override the subscription (the danger list)

The `claude` CLI decides how to authenticate and bill from its **process
environment** and its settings. If any `claude` process inherits one of these,
it stops using the subscription:

| Variable / setting | Effect |
|---|---|
| `ANTHROPIC_API_KEY` | Switches Claude to **metered Anthropic API billing**, bypassing the subscription. |
| `ANTHROPIC_AUTH_TOKEN` | Uses a custom bearer token instead of the OAuth login. |
| `ANTHROPIC_BASE_URL` | Points Claude at a different endpoint (a proxy or an Azure-style gateway). |
| `CLAUDE_CODE_USE_BEDROCK=1` | Routes via AWS Bedrock. |
| `CLAUDE_CODE_USE_VERTEX=1` | Routes via Google Vertex. |
| `apiKeyHelper` in `~/.claude/settings.json` | Runs a script that supplies a key. |

These are dangerous specifically because environment variables are
**inherited**: a variable exported in a shell, set in a globally sourced
`.env`, or placed in a docker-compose `environment:` block flows into every
child process, including the `claude` subprocesses that Context Foundry and
Knowmler spawn. One stray export bills the whole machine to the API.

## Rules for the new Context Foundry backend

The new backend reportedly has settings for an API-based provider (for an
Azure-hosted model). That is allowed to exist, but it must be quarantined:

1. **Default provider is the subscription.** Any provider/config schema must
   default to the `claude` CLI path. An API/Azure provider is opt-in and
   explicit (for example `provider: "subscription"` vs `provider: "azure"`),
   never the default, never silently selected.

2. **Never export the override variables.** The backend must not set
   `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_BASE_URL`,
   `CLAUDE_CODE_USE_BEDROCK`, or `CLAUDE_CODE_USE_VERTEX` into:
   - its own process environment,
   - any `.env` file that is sourced process-wide,
   - a docker-compose `environment:` or `env_file:` for a service that spawns
     `claude`,
   - `~/.claude/settings.json`,
   - shell rc files (`~/.bashrc`, `~/.zshrc`, `~/.profile`).

3. **Scope the Azure key to the Azure client only.** If the backend calls an
   Azure-hosted model, it must pass that key directly to that provider's own
   SDK/HTTP client, as a function argument or that client's own scoped config.
   The key must never be named `ANTHROPIC_API_KEY` and never be exported. Treat
   the Azure path and the `claude` CLI path as fully separate clients that
   share no environment.

4. **Do not re-authenticate Claude.** The backend, its installer, and its
   upgrade scripts must never run `claude login`, `claude setup-token`,
   `claude logout`, or otherwise write to `~/.claude/.credentials.json`. The
   existing OAuth login is managed out of band by the VPS owner.

5. **Do not overwrite `~/.claude/settings.json` or `~/.claude.json`.** If the
   backend needs CLI settings, it should use a project-level `.claude/`
   directory inside the repo it is building, not the user's home config.

6. **Containers reach Claude only by bind-mounting `~/.claude`,** exactly as
   Knowmler does. They must not bake credentials into an image and must not set
   API-key env vars.

## Protecting the setup across Context Foundry upgrades

A Context Foundry upgrade is the most likely thing to break this, because
installers tend to write config and set environment variables. Precautions:

- **Back up the credential before any upgrade:**
  `cp ~/.claude/.credentials.json ~/.claude/backups/credentials.$(date +%F-%H%M).json`
- **Pin `~/.claude/` as out-of-scope for the installer.** It is owned by
  `chuck`, lives outside every repo, and no Context Foundry upgrade step should
  touch it. Review the upgrade's file list before running it; reject any step
  that writes under `~/.claude/` (other than the CLI's own token refresh).
- **Diff env and compose changes.** Before loading the new backend, diff every
  `.env`, `env_file`, compose `environment:` block, and rc file it ships, and
  confirm none of the danger-list variables appear.
- **Run the guard check below** before and after the upgrade. If "before"
  passes and "after" fails, the upgrade broke the setup; restore the backed-up
  credential and remove whatever variable was introduced.
- **Verify billing mode after the upgrade.** Run a trivial `claude` prompt and
  confirm in the Claude usage dashboard that it counted against the
  subscription, not API spend.

## Verification checklist

Run this any time, and always before and after a Context Foundry upgrade or a
new-backend deploy:

- [ ] `claude` resolves on `PATH` and `claude --version` works.
- [ ] `~/.claude/.credentials.json` exists and its top-level key is
      `claudeAiOauth` (an OAuth login, not an API key).
- [ ] No `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_BASE_URL`,
      `CLAUDE_CODE_USE_BEDROCK`, or `CLAUDE_CODE_USE_VERTEX` in the environment.
- [ ] `~/.claude/settings.json` has no `env` block and no `apiKeyHelper`.
- [ ] Knowmler compose still bind-mounts `~/.claude` and sets no API key.
- [ ] No danger-list variable in any `.env` / `env_file` the new backend ships.

## Guard script

Save as `scripts/check-claude-oauth.sh`, make it executable, and run it before
and after any Context Foundry upgrade or backend deploy. It exits non-zero if
the subscription setup looks compromised.

```bash
#!/usr/bin/env bash
# Verify the Claude subscription/OAuth setup is intact and not overridden.
set -u
fail=0
note() { printf '  %s\n' "$1"; }

echo "== Claude OAuth / subscription guard =="

# 1. claude CLI present
if command -v claude >/dev/null 2>&1; then
  note "OK   claude CLI: $(claude --version 2>/dev/null | head -1)"
else
  note "FAIL claude CLI not found on PATH"; fail=1
fi

# 2. OAuth credential present and is an OAuth login (not an API key)
cred="$HOME/.claude/.credentials.json"
if [ -f "$cred" ] && grep -q '"claudeAiOauth"' "$cred"; then
  note "OK   ~/.claude/.credentials.json is an OAuth login"
else
  note "FAIL ~/.claude/.credentials.json missing or not an OAuth login"; fail=1
fi

# 3. No override variables in the environment
for v in ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN ANTHROPIC_BASE_URL \
         CLAUDE_CODE_USE_BEDROCK CLAUDE_CODE_USE_VERTEX; do
  if [ -n "${!v:-}" ]; then
    note "FAIL $v is set in the environment (overrides the subscription)"; fail=1
  fi
done
[ "$fail" -eq 0 ] && note "OK   no Claude billing-override variables in the environment"

# 4. settings.json injects no credentials
settings="$HOME/.claude/settings.json"
if [ -f "$settings" ] && grep -Eq '"(apiKeyHelper|ANTHROPIC_API_KEY)"' "$settings"; then
  note "FAIL ~/.claude/settings.json injects a key or apiKeyHelper"; fail=1
else
  note "OK   ~/.claude/settings.json injects no credentials"
fi

echo
if [ "$fail" -eq 0 ]; then
  echo "PASS - Claude is riding the subscription via OAuth."
else
  echo "FAIL - the subscription setup may be overridden. Do not deploy until fixed."
fi
exit "$fail"
```
