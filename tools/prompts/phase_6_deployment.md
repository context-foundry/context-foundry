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
   ```bash
   # Check 1: GitHub CLI available
   if ! command -v gh &> /dev/null; then
     echo "⚠️  GitHub CLI not installed"
     DEPLOYMENT_AVAILABLE=false
   else
     # Check 2: GitHub authentication
     if ! gh auth status &> /dev/null 2>&1; then
       echo "⚠️  Not authenticated to GitHub"
       DEPLOYMENT_AVAILABLE=false
     else
       echo "✅ GitHub deployment ready"
       DEPLOYMENT_AVAILABLE=true
     fi
   fi
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
   if ! command -v gh &> /dev/null; then
     echo "Reason: GitHub CLI not installed"
     echo ""
     echo "To install:"
     echo "  macOS:   brew install gh"
     echo "  Linux:   sudo apt install gh"
   else
     echo "Reason: Not authenticated to GitHub"
     echo ""
     echo "To authenticate:"
     echo "  gh auth login"
   fi
   echo ""
   echo "📝 To deploy manually:"
   echo "  1. gh auth login  # (if not authenticated)"
   echo "  2. gh repo create [project-name] --public --source=. --push"
   echo ""
   echo "═══════════════════════════════════════════════════"

   # Update session summary with deployment skipped
   # Save to .context-foundry/session-summary.json
   # Mark phases_completed including all except Deploy

   # Exit with code 10 (build success, deployment skipped)
   exit 10
   ```

3. **New Project Git Setup** (only if DEPLOYMENT_AVAILABLE=true AND not enhancement mode):
   - Ensure screenshots staged: `git add docs/screenshots/`
   - See §Git Workflow Reference for full new project workflow
   - Initialize (if not already done in Build Finalization), commit, create repo, push to main

   **Error Handling:**
   - IF git/gh commands fail: Log error, print manual instructions, exit with code 11 (build success, deployment failed)
   - DO NOT exit with code 1 or -15 (those indicate build failure, not deployment failure)

4. **Enhancement Mode Git Setup** (only if DEPLOYMENT_AVAILABLE=true AND enhancement mode):
   - Verify on feature branch (or create: `git checkout -b enhancement/{name}`)
   - See §Git Workflow Reference for enhancement workflow
   - Commit changes, push branch, create PR
   - DO NOT merge automatically - human review required
   - Skip to step 5 after PR created

5. Capture deployment information:
   - Get final commit SHA: git rev-parse HEAD
   - Get repository URL
   - Save to .context-foundry/session-summary.json

5. Update phase status (REQUIRED LAST STEP):
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
