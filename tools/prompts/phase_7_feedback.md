PHASE 7: FEEDBACK ANALYSIS (Self-Learning & Continuous Improvement)


**Purpose:** Extract learnings from this build to improve future builds automatically.

**When to run:** Always run after Deploy (success) or after Test (failure)

0. Write phase status (REQUIRED FIRST STEP):
   Update .context-foundry/current-phase.json:
   {
     "current_phase": "Feedback",
     "phase_number": "7/8",
     "status": "analyzing",
     "progress_detail": "Analyzing build for learnings and pattern updates",
     "test_iteration": {final_iteration},
     "phases_completed": ["Scout", "Architect", "Builder", "Test", "Screenshot", "Documentation", "Deploy"],
     "started_at": "{current ISO timestamp}",
     "last_updated": "{current ISO timestamp}"
   }

1. Create Feedback Analyzer agent:
   Type: /agents
   Description: "Expert build analyst who reviews completed builds to extract patterns, identify improvements, and generate structured learnings for the self-improving system. I analyze what worked, what failed, what could be prevented, and create actionable feedback that makes future builds better."

2. Activate Analyzer and collect build data:

   **Read all artifacts:**
   - .context-foundry/scout-report.md
   - .context-foundry/architecture.md
   - .context-foundry/build-log.md
   - .context-foundry/test-iteration-count.txt
   - .context-foundry/test-results-iteration-*.md (all iterations)
   - .context-foundry/fixes-iteration-*.md (all fixes)
   - .context-foundry/test-final-report.md
   - .context-foundry/session-summary.json

   **Analyze the build:**
   - What was the project type? (browser-app, cli-tool, api, game, etc.)
   - How many test iterations were needed?
   - What issues occurred during the build?
   - Which phase caught issues vs which phase should have?
   - Were there any manual interventions needed?
   - What patterns emerged?
   - What worked well?

3. Categorize feedback by phase:

   **Scout improvements:**
   - Research gaps that caused problems
   - Technology choices that led to issues
   - Missing risk identification
   - Better questions to ask upfront

   **Architect improvements:**
   - Design flaws that caused test failures
   - Missing preventive measures
   - Configuration gaps
   - Dependency omissions

   **Builder improvements:**
   - Implementation patterns that failed
   - Code quality issues
   - Missing edge case handling
   - Better coding practices

   **Test improvements:**
   - Test coverage gaps (what tests missed)
   - Integration test needs
   - Browser/environment testing gaps
   - Better validation strategies

4. Extract patterns for future builds:

   **For each issue found:**
   - Identify if it's a recurring pattern or one-time
   - Determine project types it applies to
   - Document the solution that worked
   - Assign severity (LOW/MEDIUM/HIGH)

   **Example pattern extraction:**
   ```
   Issue: CORS error prevented ES6 modules from loading
   Root cause: Browser blocks file:// protocol module imports
   Project types affected: browser-app, es6-modules, web-game
   Should have been caught by: Scout (flagged risk), Architect (included dev server), Test (browser integration test)
   Solution: Include http-server dependency + npm dev script
   Severity: HIGH (breaks entire application)
   Prevention: Scout should flag this for all ES6 module projects
   ```

5. Create structured feedback file:

   Create: .context-foundry/feedback/build-feedback-{timestamp}.json

   Format:
   {
     "timestamp": "2025-10-18T22:30:00Z",
     "project_type": "browser-game",
     "tech_stack": ["javascript", "html5-canvas", "es6-modules"],
     "build_duration_minutes": 18.5,
     "test_iterations": 2,
     "success": true/false,

     "issues_found": [
       {
         "id": "cors-es6-modules",
         "category": "Testing",
         "issue": "CORS issue not caught by unit tests",
         "root_cause": "Jest with jsdom doesn't test actual browser environment",
         "detected_in_phase": "Manual user testing",
         "should_detect_in_phase": "Test",
         "solution": "Add Playwright browser integration tests for web apps",
         "applies_to_phases": ["Scout", "Architect", "Test"],
         "severity": "HIGH",
         "project_types": ["browser-app", "es6-modules", "web-game"],
         "prevention": "Scout should flag CORS risk, Architect should include dev server, Test should verify browser loading"
       }
     ],

     "successful_patterns": [
       {
         "category": "Architecture",
         "pattern": "Entity-component game architecture",
         "worked_well": true,
         "project_types": ["game", "simulation"],
         "notes": "Clean separation of concerns, testable modules"
       }
     ],

     "recommendations": [
       {
         "for_phase": "Test",
         "recommendation": "Add browser integration testing for all web apps",
         "priority": "HIGH",
         "rationale": "Unit tests don't catch CORS, module loading, or runtime browser issues"
       }
     ]
   }

6. Update GLOBAL pattern library (Cross-Project Learning):

   **CRITICAL:** Patterns must be saved to GLOBAL storage so ALL future builds benefit!

   **IMPORTANT:** The feedback file already contains all patterns in structured format.
   You do NOT need to create .context-foundry/patterns/ - just merge the feedback file directly!

   **Merge feedback patterns to GLOBAL storage** using MCP tool:

   Execute this command to merge patterns from the feedback file:
   ```
   merge_project_patterns(
     project_pattern_file="{absolute_path}/.context-foundry/feedback/build-feedback-{timestamp}.json",
     pattern_type="common-issues",
     increment_build_count=true
   )
   ```

   Replace {absolute_path} with the actual working directory path (e.g., /Users/name/homelab/1942-shooter)
   Replace {timestamp} with the actual feedback file timestamp (e.g., 2025-01-13)

   **What this does automatically:**
     * Adds new patterns to ~/.context-foundry/patterns/common-issues.json
     * Increments frequency for existing patterns
     * Updates last_seen dates
     * Merges project_types
     * Preserves highest severity
     * Keeps most comprehensive solutions
     * Increments total_builds counter

   **Example: Merging common-issues to global storage:**
   ```
   1. Create .context-foundry/patterns/common-issues.json with new pattern:
   {
     "patterns": [{
       "pattern_id": "cors-es6-modules",
       "first_seen": "2025-10-18",
       "last_seen": "2025-10-18",
       "frequency": 1,
       "project_types": ["browser-app", "es6-modules", "web-game"],
       "issue": "ES6 modules fail with CORS from file://",
       "solution": {
         "scout": "Flag CORS risk for ES6 modules",
         "architect": "Include http-server in package.json",
         "test": "Verify module loading works"
       },
       "severity": "HIGH",
       "auto_apply": true
     }],
     "version": "1.0",
     "total_builds": 1
   }

   2. Call MCP tool to merge:
   merge_project_patterns(
     project_pattern_file="{working_dir}/.context-foundry/patterns/common-issues.json",
     pattern_type="common-issues",
     increment_build_count=true
   )

   3. The pattern is now in ~/.context-foundry/patterns/common-issues.json
   4. ALL future builds (any project) will read this pattern and avoid CORS issues!
   ```

   **Result:** Next browser app build will automatically:
   - Scout phase: Read this pattern and flag CORS risk
   - Architect phase: Apply the solution (include http-server)
   - Test phase: Verify module loading works
   - Zero failures from this issue!

7. Generate improvement recommendations:

   Create: .context-foundry/feedback/recommendations.md

   Include:
   - List of specific changes for each phase
   - Priorities (HIGH/MEDIUM/LOW)
   - Expected impact
   - Implementation notes

   Example:
   ```markdown
   # Improvement Recommendations

   ## HIGH Priority

   ### Test Phase: Add Browser Integration Testing
   - **Issue:** Unit tests don't catch CORS, module loading issues
   - **Solution:** Add Playwright for browser testing
   - **Impact:** Prevent 100% of browser compatibility issues
   - **Implementation:** Update orchestrator_prompt.txt Test phase

   ## MEDIUM Priority

   ### Scout Phase: Enhanced Risk Detection
   - **Issue:** Didn't flag CORS risk for ES6 modules
   - **Solution:** Check project type and flag known risks
   - **Impact:** Earlier detection, preventive measures
   ```

8. Verify pattern merge succeeded:

   After calling merge_project_patterns(), verify the result:
   - Check the return value shows "status": "success"
   - Confirm "new_patterns" and "updated_patterns" counts
   - If merge failed, log the error but continue (non-blocking)

9. Save feedback metadata:

   Update: .context-foundry/session-summary.json

   Add feedback section with ACTUAL merge results:
   ```json
   {
     ...,
     "feedback": {
       "analyzed": true,
       "feedback_file": ".context-foundry/feedback/build-feedback-{timestamp}.json",
       "patterns_merged_to_global": true,
       "global_patterns_updated": ["~/.context-foundry/patterns/common-issues.json"],
       "new_patterns_added_globally": <actual_count_from_merge_result>,
       "existing_patterns_updated_globally": <actual_count_from_merge_result>,
       "pattern_merge_status": "success",
       "high_priority_recommendations": 2,
       "cross_project_learning_enabled": true
     }
   }
   ```

   If pattern merge failed, set:
   ```json
   "patterns_merged_to_global": false,
   "pattern_merge_status": "failed",
   "pattern_merge_error": "<error_message>"
   ```

10. Share patterns to community (AUTOMATIC):

   **Purpose:** Automatically contribute your learnings to the global Context Foundry community
   so everyone benefits from this build's patterns.

   **Call the pattern sharing MCP tool:**
   ```
   share_patterns_to_community(
     auto_confirm=true,
     skip_if_no_changes=true
   )
   ```

   **What this does:**
   - Checks if gh CLI is authenticated (if not, skips gracefully with warning)
   - Checks if there are new patterns since last share (avoids duplicate PRs)
   - Creates a branch: patterns/{your-github-username}/{timestamp}
   - Merges your local patterns into the repo's .context-foundry/patterns/
   - Creates a PR automatically
   - PR will be validated and auto-merged if all checks pass
   - Patterns included in next nightly release for everyone!

   **This is non-blocking:**
   - If gh not installed: Skips with message "Install gh CLI to enable pattern sharing"
   - If gh not authenticated: Skips with message "Run 'gh auth login' to enable pattern sharing"
   - If no new patterns: Skips with message "No new patterns since last share"
   - If sharing fails: Logs error but continues (build still succeeds)

   **Update session-summary.json with sharing result:**
   ```json
   "feedback": {
     ...,
     "patterns_shared_to_community": true/false,
     "pattern_share_status": "success"/"skipped"/"error",
     "pattern_share_pr_url": "https://github.com/.../pull/123",
     "pattern_share_timestamp": "2025-10-27T14:32:00Z"
   }
   ```

   **Benefits:**
   - Your patterns help prevent issues in OTHER people's builds
   - Community pattern library grows automatically
   - Everyone gets smarter together
   - Zero manual work required (runs after every build)

   **Privacy:**
   - Only generic patterns are shared (no code, no project names)
   - You authenticated gh once (one-time setup)
   - Patterns are reviewed automatically before merge (validation workflow)

11. **Generate Context Budget Report (MANDATORY):**

   Create comprehensive context budget analysis report showing how context window was utilized throughout the build.

   ```bash
   # Generate markdown report with full visualization
   python3 tools/check_context_budget.py --report > .context-foundry/context-budget-report.md

   # Verify report was created successfully
   if [ -f .context-foundry/context-budget-report.md ]; then
       echo "✅ Context budget report generated: .context-foundry/context-budget-report.md"

       # Update session-summary.json with report reference
       jq '.context_budget_report = ".context-foundry/context-budget-report.md"' \
          .context-foundry/session-summary.json > .context-foundry/session-summary.json.tmp && \
       mv .context-foundry/session-summary.json.tmp .context-foundry/session-summary.json

       echo "✅ Session summary updated with context budget report reference"
   else
       echo "⚠️  Warning: Failed to generate context budget report (non-fatal)"
   fi
   ```

   **Report contents:**
   - Build identification (session ID, task, mode, directory, timestamps, GitHub PR)
   - Phase-by-phase token usage table with budget allocations
   - ASCII bar chart visualization showing usage across phases
   - Peak usage analysis (which phase used most tokens)
   - Smart zone percentage (phases operating optimally)
   - Budget compliance (phases that exceeded allocation)
   - Optimization recommendations (if any warnings detected)

   **Purpose:**
   - Users can review how efficiently context was used
   - Identify phases that need optimization
   - Track context efficiency across builds
   - Document that build stayed in SMART zone (0-40% context)
   - Provide actionable recommendations for future builds

   **Report location:** `.context-foundry/context-budget-report.md` (preserved in git alongside other build artifacts)

   **Note:** Report generation is non-fatal - if it fails, build continues successfully.

12. Learning accumulation (GLOBAL - over time across ALL projects):

   As more builds complete (from ANY project):
   - GLOBAL pattern library grows with proven solutions from all builds
   - Frequency counts show common vs rare issues ACROSS ALL PROJECTS
   - High-frequency patterns get auto-applied by default in ALL FUTURE BUILDS
   - Low-frequency patterns (< 3 occurrences globally) get pruned annually
   - Success patterns get reinforced globally

   **Cross-project self-improvement:**
   - Pattern from browser app build #1 → Prevents issue in browser app build #50
   - Pattern from API build #3 → Prevents issue in API build #25
   - As pattern library grows, build success rate increases for ALL project types
   - New projects benefit from learnings of ALL past projects

   **Self-improvement metrics (tracked globally):**
   - Track test iterations trend (should decrease over time across all projects)
   - Track common issue prevention rate (across all project types)
   - Track build success rate (should increase globally)
   - Track average build duration (should stabilize/decrease globally)
   - Track pattern effectiveness (how often each pattern prevents issues)

13. Update phase status (REQUIRED LAST STEP):
    Update .context-foundry/current-phase.json:
    {
      "current_phase": "Feedback",
      "phase_number": "7/8",
      "status": "completed",
      "progress_detail": "Build analysis complete, patterns updated globally",
      "test_iteration": {final_iteration},
      "phases_completed": ["Scout", "Architect", "Builder", "Test", "Screenshot", "Documentation", "Deploy", "Feedback"],
      "last_updated": "{current ISO timestamp}"
    }
