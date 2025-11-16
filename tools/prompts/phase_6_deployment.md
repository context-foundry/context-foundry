PHASE 6: DEPLOYMENT (GitHub)


(Only reached if tests PASSED)

**Enhancement modes:** See §Enhancement Mode Reference. Push to feature branch, create PR (skip to step 3 below).

0. Write phase status (REQUIRED FIRST STEP):
   Update .context-foundry/current-phase.json:
   {
     "current_phase": "Deploy",
     "phase_number": "6/8",
     "status": "deploying",
     "progress_detail": "Initializing Git and deploying to GitHub",
     "test_iteration": {final_iteration},
     "phases_completed": ["Scout", "Architect", "Builder", "Test", "Screenshot", "Documentation"],
     "started_at": "{current ISO timestamp}",
     "last_updated": "{current ISO timestamp}"
   }

1. **Pre-Flight Checks** (CRITICAL - Check before attempting deployment):

   **IMPORTANT:** Create deployment log file FIRST:
   ```bash
   # Initialize deployment log
   DEPLOY_LOG=".context-foundry/deploy-log.md"
   echo "# Deployment Log" > "$DEPLOY_LOG"
   echo "" >> "$DEPLOY_LOG"
   echo "Started: $(date -u +"%Y-%m-%dT%H:%M:%SZ")" >> "$DEPLOY_LOG"
   echo "" >> "$DEPLOY_LOG"
   ```

   ```bash
   # Check 1: GitHub CLI available
   echo "## Pre-Flight Checks" >> "$DEPLOY_LOG"
   echo "" >> "$DEPLOY_LOG"

   if ! command -v gh &> /dev/null; then
     echo "⚠️  GitHub CLI not installed"
     echo "❌ GitHub CLI: Not installed" >> "$DEPLOY_LOG"
     DEPLOYMENT_AVAILABLE=false
     DEPLOYMENT_SKIP_REASON="GitHub CLI not installed"
   else
     echo "✅ GitHub CLI: Installed" >> "$DEPLOY_LOG"

     # Check 2: GitHub authentication status
     AUTH_OUTPUT=$(gh auth status 2>&1)
     if ! gh auth status &> /dev/null 2>&1; then
       echo "⚠️  Not authenticated to GitHub"
       echo "❌ GitHub Auth: Not authenticated" >> "$DEPLOY_LOG"
       echo '```' >> "$DEPLOY_LOG"
       echo "$AUTH_OUTPUT" >> "$DEPLOY_LOG"
       echo '```' >> "$DEPLOY_LOG"
       DEPLOYMENT_AVAILABLE=false
       DEPLOYMENT_SKIP_REASON="Not authenticated to GitHub"
     else
       echo "✅ GitHub Auth: Authenticated" >> "$DEPLOY_LOG"
       echo '```' >> "$DEPLOY_LOG"
       echo "$AUTH_OUTPUT" >> "$DEPLOY_LOG"
       echo '```' >> "$DEPLOY_LOG"

       # Check 3: Validate GitHub token scopes
       # The 'repo' scope includes public_repo access
       if echo "$AUTH_OUTPUT" | grep -q "'repo'"; then
         echo "✅ Token scopes: Valid (repo scope found)" >> "$DEPLOY_LOG"
         echo "✅ GitHub deployment ready"
         DEPLOYMENT_AVAILABLE=true
       elif echo "$AUTH_OUTPUT" | grep -q "'public_repo'"; then
         echo "✅ Token scopes: Valid (public_repo scope found)" >> "$DEPLOY_LOG"
         echo "✅ GitHub deployment ready"
         DEPLOYMENT_AVAILABLE=true
       else
         echo "⚠️  GitHub token missing required scopes"
         echo "❌ Token scopes: Missing 'repo' or 'public_repo'" >> "$DEPLOY_LOG"
         echo "Available scopes:" >> "$DEPLOY_LOG"
         echo '```' >> "$DEPLOY_LOG"
         echo "$AUTH_OUTPUT" | grep -i "scopes:" >> "$DEPLOY_LOG"
         echo '```' >> "$DEPLOY_LOG"
         DEPLOYMENT_AVAILABLE=false
         DEPLOYMENT_SKIP_REASON="GitHub token missing required scopes (needs 'repo' or 'public_repo')"
       fi
     fi
   fi

   echo "" >> "$DEPLOY_LOG"
   echo "Deployment Available: $DEPLOYMENT_AVAILABLE" >> "$DEPLOY_LOG"
   if [ "$DEPLOYMENT_AVAILABLE" = "false" ]; then
     echo "Reason: $DEPLOYMENT_SKIP_REASON" >> "$DEPLOY_LOG"
   fi
   echo "" >> "$DEPLOY_LOG"
   ```

2. **Graceful Degradation - Build Success Regardless of Deployment**:

   **IF DEPLOYMENT_AVAILABLE=true:**
   - Proceed with GitHub deployment (step 3)

   **IF DEPLOYMENT_AVAILABLE=false:**
   - **DEPLOYMENT IS OPTIONAL - BUILD HAS SUCCEEDED!**
   - Log warning, print manual deployment instructions
   - Exit with code 10 (build succeeded, deployment skipped)
   - DO NOT exit with error code 1 or -15

   ```bash
   echo "═══════════════════════════════════════════════════"
   echo "✅ BUILD SUCCEEDED!"
   echo "═══════════════════════════════════════════════════"
   echo ""
   echo "📦 Project Location: $(pwd)"
   echo "📂 Files Created: $(find . -type f -not -path '*/\.*' | wc -l) files"
   echo ""
   echo "⚠️  DEPLOYMENT SKIPPED"
   echo ""
   echo "Reason: $DEPLOYMENT_SKIP_REASON"
   echo ""

   # Log to deploy-log.md
   echo "## Deployment Skipped" >> "$DEPLOY_LOG"
   echo "" >> "$DEPLOY_LOG"
   echo "Reason: $DEPLOYMENT_SKIP_REASON" >> "$DEPLOY_LOG"
   echo "" >> "$DEPLOY_LOG"

   # Provide specific instructions based on reason
   if ! command -v gh &> /dev/null; then
     echo "To install:"
     echo "  macOS:   brew install gh"
     echo "  Linux:   sudo apt install gh"
   elif echo "$DEPLOYMENT_SKIP_REASON" | grep -q "scope"; then
     echo "To fix token scopes:"
     echo "  gh auth refresh -s repo"
     echo "  # OR: gh auth login --scopes repo"
   else
     echo "To authenticate:"
     echo "  gh auth login --scopes repo"
   fi
   echo ""
   echo "📝 To deploy manually:"
   echo "  1. gh auth login --scopes repo  # (if needed)"
   echo "  2. gh repo create [project-name] --public --source=. --push"
   echo ""
   echo "═══════════════════════════════════════════════════"

   # Update session summary with deployment skipped
   # **CRITICAL:** Use the ACTUAL skip reason from pre-flight checks
   # Save to .context-foundry/session-summary.json with the real reason
   python3 -c "
import json
from pathlib import Path

summary_file = Path('.context-foundry/session-summary.json')
if summary_file.exists():
    with open(summary_file, 'r') as f:
        summary = json.load(f)
else:
    summary = {}

summary['deployment'] = {
    'status': 'skipped',
    'reason': '''$DEPLOYMENT_SKIP_REASON''',
    'attempted_at': '$(date -u +"%Y-%m-%dT%H:%M:%SZ")'
}

with open(summary_file, 'w') as f:
    json.dump(summary, f, indent=2)
"

   echo "Completed: $(date -u +"%Y-%m-%dT%H:%M:%SZ")" >> "$DEPLOY_LOG"

   # Exit with code 10 (build success, deployment skipped)
   exit 10
   ```

3. **New Project Git Setup** (only if DEPLOYMENT_AVAILABLE=true AND not enhancement mode):

   **CRITICAL: Capture ALL command output to deploy-log.md**

   ```bash
   echo "## GitHub Repository Creation" >> "$DEPLOY_LOG"
   echo "" >> "$DEPLOY_LOG"

   # Ensure screenshots are staged
   git add docs/screenshots/ 2>&1 | tee -a "$DEPLOY_LOG"

   # Create GitHub repository and push
   echo "### Running: gh repo create" >> "$DEPLOY_LOG"
   echo '```bash' >> "$DEPLOY_LOG"
   echo "gh repo create $(basename $(pwd)) --public --source=. --push" >> "$DEPLOY_LOG"
   echo '```' >> "$DEPLOY_LOG"
   echo "" >> "$DEPLOY_LOG"
   echo "Output:" >> "$DEPLOY_LOG"
   echo '```' >> "$DEPLOY_LOG"

   # Capture both stdout and stderr
   GH_OUTPUT=$(gh repo create $(basename $(pwd)) --public --source=. --push 2>&1)
   GH_EXIT_CODE=$?

   echo "$GH_OUTPUT" >> "$DEPLOY_LOG"
   echo '```' >> "$DEPLOY_LOG"
   echo "" >> "$DEPLOY_LOG"
   echo "Exit code: $GH_EXIT_CODE" >> "$DEPLOY_LOG"
   echo "" >> "$DEPLOY_LOG"

   # Check if deployment failed
   if [ $GH_EXIT_CODE -ne 0 ]; then
     echo "❌ GitHub deployment failed" >> "$DEPLOY_LOG"
     echo "" >> "$DEPLOY_LOG"
     echo "═══════════════════════════════════════════════════"
     echo "✅ BUILD SUCCEEDED!"
     echo "═══════════════════════════════════════════════════"
     echo ""
     echo "❌ DEPLOYMENT FAILED"
     echo ""
     echo "Error output:"
     echo "$GH_OUTPUT"
     echo ""
     echo "📝 To deploy manually:"
     echo "  gh repo create $(basename $(pwd)) --public --source=. --push"
     echo ""
     echo "═══════════════════════════════════════════════════"

     # Update session summary with deployment failed and REAL error
     python3 -c "
import json
from pathlib import Path

summary_file = Path('.context-foundry/session-summary.json')
if summary_file.exists():
    with open(summary_file, 'r') as f:
        summary = json.load(f)
else:
    summary = {}

# Get commit SHA even if push failed
import subprocess
try:
    commit_sha = subprocess.check_output(['git', 'rev-parse', 'HEAD']).decode().strip()
    local_commit = True
except:
    commit_sha = None
    local_commit = False

summary['deployment'] = {
    'status': 'failed',
    'reason': '''$GH_OUTPUT''',
    'commit_sha': commit_sha,
    'local_commit_created': local_commit,
    'attempted_at': '$(date -u +"%Y-%m-%dT%H:%M:%SZ")'
}

with open(summary_file, 'w') as f:
    json.dump(summary, f, indent=2)
"

     echo "Completed: $(date -u +"%Y-%m-%dT%H:%M:%SZ")" >> "$DEPLOY_LOG"

     # Exit with code 11 (build success, deployment failed)
     exit 11
   fi

   echo "✅ GitHub repository created successfully" >> "$DEPLOY_LOG"
   echo "" >> "$DEPLOY_LOG"
   ```

   **Error Handling:**
   - All git/gh command output is captured to deploy-log.md
   - Real stderr/stdout saved to session-summary.json (not LLM guesses!)
   - Exit with code 11 if deployment fails (build success, deployment failed)
   - DO NOT exit with code 1 or -15 (those indicate build failure, not deployment failure)

4. **Enhancement Mode Git Setup** (only if DEPLOYMENT_AVAILABLE=true AND enhancement mode):
   - Verify on feature branch (or create: `git checkout -b enhancement/{name}`)
   - See §Git Workflow Reference for enhancement workflow
   - Commit changes, push branch, create PR
   - DO NOT merge automatically - human review required
   - Skip to step 5 after PR created

5. Capture deployment information:

   ```bash
   # Get deployment details
   COMMIT_SHA=$(git rev-parse HEAD)
   REPO_URL=$(git remote get-url origin)

   # Convert SSH URL to HTTPS for browser access
   if echo "$REPO_URL" | grep -q "^git@github.com:"; then
     GITHUB_URL="https://github.com/$(echo $REPO_URL | sed 's/git@github.com://; s/.git$//')"
   else
     GITHUB_URL=$(echo "$REPO_URL" | sed 's/.git$//')
   fi

   # Log to deploy-log.md
   echo "## Deployment Success" >> "$DEPLOY_LOG"
   echo "" >> "$DEPLOY_LOG"
   echo "- Repository URL: $GITHUB_URL" >> "$DEPLOY_LOG"
   echo "- Commit SHA: $COMMIT_SHA" >> "$DEPLOY_LOG"
   echo "- Deployed at: $(date -u +"%Y-%m-%dT%H:%M:%SZ")" >> "$DEPLOY_LOG"
   echo "" >> "$DEPLOY_LOG"

   # Update session-summary.json with successful deployment
   python3 -c "
import json
from pathlib import Path

summary_file = Path('.context-foundry/session-summary.json')
if summary_file.exists():
    with open(summary_file, 'r') as f:
        summary = json.load(f)
else:
    summary = {}

summary['deployment'] = {
    'status': 'success',
    'repository_url': '''$GITHUB_URL''',
    'commit_sha': '''$COMMIT_SHA''',
    'deployed_at': '$(date -u +"%Y-%m-%dT%H:%M:%SZ")'
}

with open(summary_file, 'w') as f:
    json.dump(summary, f, indent=2)
"

   echo "Completed: $(date -u +"%Y-%m-%dT%H:%M:%SZ")" >> "$DEPLOY_LOG"

   echo "═══════════════════════════════════════════════════"
   echo "✅ BUILD AND DEPLOYMENT SUCCEEDED!"
   echo "═══════════════════════════════════════════════════"
   echo ""
   echo "🚀 Deployed to: $GITHUB_URL"
   echo "📦 Commit: $COMMIT_SHA"
   echo ""
   echo "═══════════════════════════════════════════════════"
   ```

6. Update phase status (REQUIRED LAST STEP):
   Update .context-foundry/current-phase.json:
   {
     "current_phase": "Deploy",
     "phase_number": "6/8",
     "status": "completed",
     "progress_detail": "Successfully deployed to GitHub",
     "test_iteration": {final_iteration},
     "phases_completed": ["Scout", "Architect", "Builder", "Test", "Screenshot", "Documentation", "Deploy"],
     "last_updated": "{current ISO timestamp}"
   }
