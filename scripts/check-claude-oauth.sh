#!/usr/bin/env bash
# Verify the Claude subscription/OAuth setup is intact and not overridden.
#
# SCOPE: this checks the HOST-LEVEL subscription -- the host shell and
# Knowmler's container, which use the ambient ~/.claude OAuth login. It does
# NOT verify `foundry serve`, the new build service: that authenticates
# through its own proxy (FOUNDRY_SERVICE_UPSTREAM_AUTH / _OAUTH_TOKEN) and its
# build containers set ANTHROPIC_* on purpose. A green result here does not
# mean foundry serve is on OAuth -- smoke-test a build for that.
#
# Run this before AND after any Context Foundry upgrade or backend deploy.
# Exits non-zero if the host-level subscription setup looks compromised.
# See docs/CLAUDE_OAUTH_SETUP.md for the why.
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
