PHASE 7.5: GITHUB INTEGRATION (Comprehensive Project Infrastructure)


**Purpose:** Configure comprehensive GitHub infrastructure for collaboration, automation, and deployment.

**When to run:** After Feedback Analysis, before final completion (for successful builds).

**Skip if:** Build failed before Deploy phase completed.

**Note:** Phase tracking is handled automatically by the orchestrator using BAML.

0.

1. Create GitHub Agent:
   Type: /agents
   Description: "Expert GitHub automation specialist who sets up comprehensive project infrastructure including issues, milestones, CI/CD workflows, documentation publishing, release management, and deployment pipelines. I configure GitHub to maximize collaboration, automation, and project visibility."

2. Activate GitHub Agent and configure:

   **The agent will read from tools/github_agent_prompt.txt automatically.**

   **Read Context Foundry installation path and agent prompt:**
   ```bash
   CF_PATH="$(cd "$(dirname "$(which claude)")/../.." && pwd)/context-foundry"
   GITHUB_PROMPT="$CF_PATH/tools/github_agent_prompt.txt"

   # Verify prompt exists
   if [ ! -f "$GITHUB_PROMPT" ]; then
     echo "ERROR: GitHub agent prompt not found at $GITHUB_PROMPT"
     exit 1
   fi
   ```

   **Launch GitHub Agent:**
   ```bash
   # Get repository info
   REPO_NAME=$(basename $(git rev-parse --show-toplevel 2>/dev/null) || echo "unknown")
   OWNER="snedea"
   MODE=$(jq -r '.mode // "new_project"' .context-foundry/session-summary.json 2>/dev/null || echo "new_project")

   # Execute GitHub agent with system prompt
   claude --print --system-prompt "$(cat "$GITHUB_PROMPT")" \
     "Configure GitHub for repository: $OWNER/$REPO_NAME

     Mode: $MODE
     Working Directory: $(pwd)

     Execute all phases from the GitHub Agent prompt:
     1. Project type detection
     2. Issue creation and tracking
     3. Labels and templates setup
     4. CI/CD workflows (GitHub Actions)
     5. Release creation
     6. GitHub Pages setup (if applicable)
     7. Branch protection (if applicable)
     8. Update issue and final status

     Read all context files from .context-foundry/ directory.
     Make intelligent decisions based on project type.
     Handle errors gracefully.
     Update session summary with GitHub metadata.

     Work autonomously and report results."
   ```

   **The GitHub Agent will:**
   - Detect project type (web app, CLI, API, library, etc.)
   - Create tracking issue from Scout report
   - Set up labels and issue templates
   - Create GitHub Actions workflows (test, deploy, docker)
   - Create GitHub release with changelog
   - Enable GitHub Pages (for web apps)
   - Set up branch protection (for new projects)
   - Update tracking issue and close it
   - Update session summary with GitHub metadata

3. Verify GitHub setup:
   ```bash
   # Check if GitHub metadata was added to session summary
   if jq -e '.github' .context-foundry/session-summary.json > /dev/null 2>&1; then
     echo "✅ GitHub integration complete"

     # Display summary
     echo ""
     echo "GitHub Setup Summary:"
     jq -r '.github | to_entries | map("  - \(.key): \(.value)") | .[]' .context-foundry/session-summary.json
   else
     echo "⚠️  GitHub integration completed with warnings"
   fi
   ```



**✅ GitHub Integration complete. Proceed to FINAL OUTPUT.**
