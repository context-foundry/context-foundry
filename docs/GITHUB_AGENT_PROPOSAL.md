# GitHub Agent Proposal

## Executive Summary

Add a dedicated **GitHub Agent** to Context Foundry's autonomous workflow to handle comprehensive GitHub integration beyond basic repo creation.

## Current State

**Phase 6 (Deploy):**
- Creates GitHub repo
- Pushes to main (new projects)
- Creates PR (enhancement mode)
- Basic git operations

**Missing:** 90% of GitHub's project management, CI/CD, and collaboration features.

## Proposed Solution

### New Phase: 7.5 - GitHub Integration

**Agent Description:**
> "Expert GitHub automation specialist who sets up comprehensive project infrastructure including issues, milestones, CI/CD workflows, documentation publishing, release management, and deployment pipelines. I configure GitHub to maximize collaboration, automation, and project visibility."

### Responsibilities by Project Type

#### All Projects
1. **Issue Management**
   ```bash
   # Create tracking issue from Scout report
   ISSUE_NUM=$(gh issue create \
     --title "Build: ${TASK_DESCRIPTION}" \
     --body "$(cat .context-foundry/scout-report.md)" \
     --label "context-foundry,autonomous-build" \
     --json number -q .number)

   echo $ISSUE_NUM > .context-foundry/github-issue.txt
   ```

2. **Labels & Templates**
   ```bash
   # Set up standard labels
   gh label create "context-foundry" --color "7057ff" --description "Built by Context Foundry"
   gh label create "autonomous" --color "0e8a16" --description "Autonomous build"

   # Create issue templates
   cat > .github/ISSUE_TEMPLATE/bug_report.md << 'EOF'
   ---
   name: Bug Report
   about: Report a bug in this project
   ---
   ...
   EOF
   ```

3. **Branch Protection** (if not existing repo)
   ```bash
   # Protect main branch
   gh api repos/{owner}/{repo}/branches/main/protection \
     --method PUT \
     --field required_status_checks='{"strict":true,"contexts":["test"]}' \
     --field enforce_admins=true \
     --field required_pull_request_reviews='{"required_approving_review_count":1}'
   ```

#### Web Apps & Games

4. **GitHub Pages Setup**
   ```bash
   # Enable GitHub Pages
   gh api repos/{owner}/{repo}/pages \
     --method POST \
     --field source='{"branch":"main","path":"/docs"}' \
     --field build_type="jekyll"

   # Add deployment workflow
   cat > .github/workflows/deploy.yml << 'EOF'
   name: Deploy to GitHub Pages
   on:
     push:
       branches: [main]
   jobs:
     deploy:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4
         - name: Build
           run: npm run build
         - name: Deploy
           uses: peaceiris/actions-gh-pages@v3
           with:
             github_token: ${{ secrets.GITHUB_TOKEN }}
             publish_dir: ./dist
   EOF
   ```

#### All Projects with Tests

5. **GitHub Actions CI/CD**
   ```bash
   # Create test workflow
   cat > .github/workflows/test.yml << 'EOF'
   name: Test Suite
   on: [push, pull_request]
   jobs:
     test:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4
         - uses: actions/setup-node@v4  # or python, etc.
         - run: npm install
         - run: npm test
         - run: npm run lint
   EOF

   git add .github/workflows/test.yml
   git commit -m "ci: add GitHub Actions test workflow"
   ```

#### Successful Builds

6. **Release Creation**
   ```bash
   # Get version from package.json or detect
   VERSION=$(jq -r .version package.json)

   # Create git tag
   git tag -a "v${VERSION}" -m "Release v${VERSION} - Built by Context Foundry"
   git push origin "v${VERSION}"

   # Generate changelog from commits
   CHANGELOG=$(git log --oneline --pretty=format:"- %s" $(git describe --tags --abbrev=0 HEAD^)..HEAD)

   # Create GitHub release
   gh release create "v${VERSION}" \
     --title "v${VERSION}" \
     --notes "## What's New

   ${CHANGELOG}

   ## Test Results
   - All tests passing (${TEST_ITERATION} iteration(s))
   - Coverage: ${COVERAGE}%

   ## Documentation
   - 📖 [README](README.md)
   - 🏗️ [Architecture](docs/ARCHITECTURE.md)
   - 🧪 [Testing Guide](docs/TESTING.md)

   🤖 Built autonomously by Context Foundry" \
     --latest
   ```

#### Enhancement Mode

7. **Draft PR Workflow**
   ```bash
   # Create draft PR immediately (track progress)
   gh pr create \
     --draft \
     --title "[WIP] ${MODE}: ${DESCRIPTION}" \
     --body "## 🚧 Work in Progress

   Closes #${ISSUE_NUM}

   ### Build Progress
   - ✅ Scout: Requirements gathered
   - ✅ Architect: Design complete
   - 🔄 Builder: Implementation in progress
   - ⏳ Tester: Pending

   **Auto-updating:** This PR will be updated as build progresses.
   " \
     --label "context-foundry,work-in-progress"

   # Update PR as phases complete
   gh pr edit \
     --body "$(cat .context-foundry/pr-progress.md)" \
     --remove-label "work-in-progress" \
     --add-label "ready-for-review"

   # Mark ready when tests pass
   gh pr ready
   ```

### Agent Workflow

**When to Run:** After Phase 7 (Feedback Analysis), before final completion

**Orchestrator Integration:**

```markdown
═══════════════════════════════════════════════════════════
PHASE 7.5: GITHUB INTEGRATION (Comprehensive Setup)
═══════════════════════════════════════════════════════════

**Purpose:** Configure GitHub for optimal collaboration, automation, and deployment

0. Write phase status:
   Update .context-foundry/current-phase.json:
   {
     "current_phase": "GitHub Integration",
     "phase_number": "7.5/8",
     "status": "configuring",
     "progress_detail": "Setting up GitHub project infrastructure"
   }

1. Create GitHub Agent:
   Type: /agents
   Description: "Expert GitHub automation specialist who sets up comprehensive project infrastructure including issues, milestones, CI/CD workflows, documentation publishing, release management, and deployment pipelines. I configure GitHub to maximize collaboration, automation, and project visibility."

2. Activate GitHub Agent and configure:

   **Read context:**
   - .context-foundry/scout-report.md (project type)
   - .context-foundry/architecture.md (tech stack)
   - .context-foundry/test-final-report.md (test results)
   - .context-foundry/session-summary.json (build metadata)

   **Determine project type:**
   - Web app → Enable GitHub Pages, add deployment workflow
   - CLI tool → Add release workflow, binary publishing
   - API → Add Docker workflow, container registry
   - Library → Add package publishing (npm, PyPI)

   **Create tracking issue:**
   - Use Scout report as issue body
   - Add labels based on mode
   - Save issue number for linking

   **Set up CI/CD:**
   - Generate appropriate GitHub Actions workflow
   - Configure test automation
   - Add linting/formatting checks
   - Set up branch protection rules

   **Configure deployment:**
   - GitHub Pages for web apps
   - Docker registry for containers
   - Package registry for libraries
   - Release automation

   **Create release (if successful build):**
   - Tag version
   - Generate changelog
   - Create GitHub release
   - Attach artifacts if applicable

   **Enhancement mode:**
   - Update PR with final status
   - Link to issue
   - Add test results
   - Mark as ready for review

3. Update session summary:
   Add to .context-foundry/session-summary.json:
   {
     "github": {
       "issue_number": 123,
       "issue_url": "https://github.com/...",
       "pr_number": 456,
       "pr_url": "https://github.com/...",
       "release_version": "1.0.0",
       "release_url": "https://github.com/...",
       "pages_url": "https://username.github.io/repo",
       "actions_configured": true,
       "branch_protection": true
     }
   }

4. Update phase status:
   {
     "current_phase": "GitHub Integration",
     "phase_number": "7.5/8",
     "status": "completed",
     "progress_detail": "GitHub project fully configured"
   }
```

## Benefits

### For Users
- **Better tracking:** Issues → PRs → Releases all linked
- **Automatic CI/CD:** Tests run on every push
- **Professional setup:** Looks like a mature project from day 1
- **Easy collaboration:** Templates and guidelines in place
- **Deployment ready:** GitHub Pages, containers, packages configured

### For Context Foundry
- **Showcase quality:** Autonomous builds look professional
- **Full automation:** True end-to-end workflow
- **Better debugging:** GitHub Actions logs for build failures
- **Metrics:** Track build success via GitHub API
- **Community:** Easier to share and fork successful builds

## Implementation Priority

### Phase 1 (High Priority)
- ✅ Issue creation and linking
- ✅ GitHub Actions test workflow
- ✅ Release creation with changelog
- ✅ Draft PR workflow for enhancements

### Phase 2 (Medium Priority)
- ⏳ GitHub Pages deployment
- ⏳ Branch protection rules
- ⏳ Issue/PR templates
- ⏳ Labels and milestones

### Phase 3 (Nice to Have)
- ⏳ Dependabot setup
- ⏳ CodeQL security scanning
- ⏳ Wiki generation
- ⏳ Package publishing (npm, PyPI, Docker)

## Alternative: Helper Functions vs Agent

### Option A: Dedicated GitHub Agent (Recommended)
**Pros:**
- Sophisticated decision-making (which workflows to create?)
- Can read Scout/Architect context to customize setup
- Handles complex workflows (e.g., monorepo setups)
- Future-proof for advanced GitHub features

**Cons:**
- Adds another agent to orchestrate
- More complex to maintain

### Option B: GitHub Helper Functions
**Pros:**
- Simpler - just bash functions in Deploy phase
- Less overhead
- Easier to debug

**Cons:**
- Limited intelligence (can't adapt to project type)
- Hard to maintain as GitHub evolves
- Would need lots of if/else logic

## Recommendation

**Use a dedicated GitHub Agent** because:

1. **Context-aware decisions:** Agent can read Scout report to determine:
   - Is this a web app? → Set up GitHub Pages
   - Has Docker? → Set up GHCR publishing
   - Has package.json? → Set up npm publishing

2. **Sophisticated workflows:** Agent can:
   - Analyze test structure to create appropriate CI
   - Read architecture to determine deployment needs
   - Generate custom workflows based on tech stack

3. **Future extensibility:** Easy to add:
   - GitLab support
   - Bitbucket support
   - Custom deployment targets

4. **Consistent with existing architecture:** Scout/Architect/Builder/Tester are already agents

## Success Metrics

After implementing GitHub Agent, successful builds should have:
- ✅ Tracking issue created and closed
- ✅ GitHub Actions workflow running tests
- ✅ Branch protection on main
- ✅ GitHub release with changelog
- ✅ GitHub Pages live (if web app)
- ✅ Professional README with badges
- ✅ Issue/PR templates in place

## Example Output

```json
{
  "status": "completed",
  "phases_completed": ["scout", "architect", "builder", "test", "screenshot", "docs", "deploy", "feedback", "github"],
  "github": {
    "issue": {
      "number": 1,
      "url": "https://github.com/snedea/weather-app/issues/1",
      "status": "closed"
    },
    "release": {
      "version": "1.0.0",
      "url": "https://github.com/snedea/weather-app/releases/tag/v1.0.0",
      "changelog": "- Initial implementation\n- Complete test suite\n- Documentation"
    },
    "pages": {
      "url": "https://snedea.github.io/weather-app",
      "status": "live"
    },
    "actions": {
      "workflows": ["test.yml", "deploy.yml"],
      "status": "configured"
    },
    "protection": {
      "branch": "main",
      "rules": ["required_reviews", "status_checks"]
    }
  }
}
```

## Next Steps

1. Create `tools/github_agent_prompt.txt` with detailed instructions
2. Add Phase 7.5 to `orchestrator_prompt.txt`
3. Update session summary schema to include GitHub metadata
4. Add GitHub integration tests
5. Document in main README

## Questions to Resolve

1. Should GitHub Agent run for **all** builds or only successful ones?
   - Recommendation: All builds (create issue at start, update throughout)

2. Should branch protection be mandatory or optional?
   - Recommendation: Optional based on repo settings (don't break existing workflows)

3. Should we support other platforms (GitLab, Bitbucket)?
   - Recommendation: Start with GitHub, design for extensibility

4. Should releases be created for every build or only tagged versions?
   - Recommendation: Only when version changes detected (semantic versioning)

---

**Status:** Proposal - Ready for Review
**Author:** Claude Code
**Date:** 2025-10-24
