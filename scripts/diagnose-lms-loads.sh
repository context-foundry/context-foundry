#!/usr/bin/env bash
# Diagnose what is auto-loading models in LM Studio.
#
# Usage: bash scripts/diagnose-lms-loads.sh
#
# Looks for the most common culprits when LM Studio shows mystery models in
# its Loaded Models panel:
#   - LaunchAgents / LaunchDaemons that invoke `lms load`
#   - Cron jobs touching `lms`
#   - Shell startup scripts that run `lms` at login
#   - Any process currently holding a connection to LM Studio's port 1234
#   - LM Studio's own JIT auto-load setting (which loads any model named in an
#     incoming chat-completions request, with default 4K context)
set -u

LMSTUDIO_URL="http://localhost:1234/v1/models"

section() { printf '\n=== %s ===\n' "$*"; }

section "1. Running processes invoking lms or lmstudio"
ps aux | grep -iE "lms |lmstudio_watchdog|lms-cli" | grep -v grep || echo "(none)"

section "2. User LaunchAgents touching lms"
ls -la "$HOME/Library/LaunchAgents/" 2>/dev/null \
  | grep -iE "lms|lmstudio|wikillm" || echo "(none)"

section "3. System LaunchAgents / LaunchDaemons"
{
  ls -la /Library/LaunchAgents/ 2>/dev/null
  ls -la /Library/LaunchDaemons/ 2>/dev/null
} | grep -iE "lms|lmstudio" || echo "(none)"

section "4. crontab"
crontab -l 2>/dev/null | grep -iE "lms|lmstudio" || echo "(no matches in user crontab)"

section "5. Shell startup files"
grep -lE "lms |lms load|lmstudio" \
  "$HOME/.zshrc" "$HOME/.zprofile" "$HOME/.zshenv" \
  "$HOME/.bashrc" "$HOME/.bash_profile" 2>/dev/null \
  || echo "(no matches)"

section "6. Open connections to port 1234"
lsof -nP -i :1234 2>/dev/null | head -20 || echo "(none — LM Studio not listening?)"

section "7. LM Studio reachable?"
if curl -sf "$LMSTUDIO_URL" > /dev/null; then
  echo "PASS — LM Studio at $LMSTUDIO_URL"
  echo
  echo "Models LM Studio currently exposes:"
  curl -sf "$LMSTUDIO_URL" | jq -r '.data[].id' | sed 's/^/  - /'
else
  echo "FAIL — LM Studio is not responding at $LMSTUDIO_URL"
fi

section "Summary"
cat <<'EOF'
If you see a watchdog process or LaunchAgent in sections 1-2, that's almost
certainly what is auto-loading models. To stop it temporarily:

  launchctl unload ~/Library/LaunchAgents/<name>.plist
  pkill -f <watchdog-script-name>

LM Studio also has its own "Just-In-Time Model Loading" feature in the GUI
which loads any model named in a chat-completions API request -- with the
*default* context length (4K), not whatever you set when you manually loaded
it. If foundry / opencode sends a model id that doesn't exactly match an
already-loaded instance, LM Studio will JIT-load a duplicate. Disable JIT
loading in the GUI to avoid surprises. After disabling, foundry must send
requests for already-loaded model ids or those requests will fail fast.
EOF
