PHASE 1: SCOUT (Research & Context Gathering + Learning Application)

**⚡ SMART CACHE CHECK - INCREMENTAL BUILDS:**

**IF incremental mode is enabled (check CONFIGURATION.incremental):**

1. **Check for cached Scout report:**
   ```python
   python3 -c "
   import sys
   sys.path.insert(0, '/Users/name/homelab/context-foundry')
   from tools.cache.scout_cache import get_cached_scout_report

   cached = get_cached_scout_report(
       task='TASK_DESCRIPTION',
       mode='MODE',
       working_directory='WORKING_DIR'
   )

   if cached:
       print('CACHE_HIT')
       # Save cached report to expected location
       with open('.context-foundry/scout-report.md', 'w') as f:
           f.write(cached)
   else:
       print('CACHE_MISS')
   "
   ```

2. **If CACHE_HIT:**
   - ✅ Scout phase complete (reused cached report)
   - Skip to Phase 2 (Architect)
   - Log: "⚡ Incremental build: Reusing Scout report from cache"
   - Update phase tracking: "Scout" → "completed" (cache hit)

3. **If CACHE_MISS:**
   - Continue with normal Scout phase below
   - After completing Scout, save to cache (see step 5 below)

**PHASE TRACKING (START) - MANDATORY FIRST ACTION:**
Update phase: "Scout" (1/7, "researching", "Analyzing task requirements")
(See PHASE TRACKING TEMPLATE)

0. **CHECK CONTEXT BUDGET (PROACTIVE WARNING):**
   ```bash
   python3 tools/check_context_budget.py --phase scout --check-before
   ```

   This checks if Scout phase will stay in SMART ZONE (0-40% context):
   - Exit code 0: ✅ Safe to proceed
   - Exit code 1: ⚠️ Warning - approaching dumb zone
   - Exit code 2: 🚨 Critical - consider sub-agent

   **If exit code 2 (CRITICAL):**
   - Strong recommendation to use sub-agent for Scout
   - Reduces context to isolated window
   - Prevents performance degradation

   **Otherwise:** Proceed with normal Scout workflow

1. Check for Past Learnings (Self-Learning System - GLOBAL PATTERNS):

   **Read GLOBAL pattern files** using MCP tools:
   - Use `read_global_patterns("scout-learnings")` to get learnings from ALL past projects
   - Use `read_global_patterns("common-issues")` to get issues from ALL past builds

   The global patterns are stored at ~/.context-foundry/patterns/ and shared across all projects.

   If patterns exist:
   - Identify project type from task description
   - Check for relevant past issues matching this project type
   - Note warnings and recommendations from previous builds across ALL projects
   - Flag high-risk patterns to watch for (learned from any past project)

   Example: If building browser app with ES6 modules, patterns might warn:
   "⚠️ CORS Risk: ES6 modules fail from file:// - Include dev server in architecture"
   (This learning comes from ANY past browser app build, not just this project)

**FLOWISE EXTENSION CHECK** (if Flowise flow detected in codebase):

   If CONFIGURATION shows flowise_flow: True:

   🚨 **FLOWISE-ONLY MODE ACTIVATED** 🚨

   **Flowise Flow Detected!**
   - Flow Type: {flowise_flow_type}
   - Complexity: {flowise_complexity}
   - This is a Flowise workflow project, NOT a traditional web application

   **DO NOT research:**
   ❌ Web frameworks (React, Vue, Angular, etc.)
   ❌ Frontend architectures or UI patterns
   ❌ Backend API frameworks (Express, FastAPI, etc.)
   ❌ Database schemas or ORMs
   ❌ Traditional full-stack application patterns

   **ONLY research:**
   ✅ Flowise node architectures and patterns
   ✅ Agent specialization and persona design
   ✅ Tool integration patterns (currentDateTime, searXNG, custom)
   ✅ Memory management strategies (contextual, long-term)
   ✅ Prompt engineering best practices
   ✅ Condition routing and workflow orchestration

   **MANDATORY Reading (Scout MUST execute these Read commands)**:

   1. **Read AGENT_PATTERN_REFERENCE.md** (the authority on Flowise structure):
      ```
      Read /Users/name/homelab/context-foundry/extensions/flowise/AGENT_PATTERN_REFERENCE.md
      ```

   2. **Read FAILURE_PATTERNS.md** (learn from past mistakes):
      ```
      Read /Users/name/homelab/context-foundry/extensions/flowise/FAILURE_PATTERNS.md
      ```
      This contains detailed root causes, fixes, and prevention checklists for 6+ known failure patterns.
      Don't just read the summary - read the FULL file to understand WHY each pattern fails.

   3. **Read STANDARD_TOOLS.md** (understand required tools):
      ```
      Read /Users/name/homelab/context-foundry/extensions/flowise/tool-configs/STANDARD_TOOLS.md
      ```

   4. **Read BEST_PRACTICES.md** (if exists):
      ```
      Read /Users/name/homelab/context-foundry/extensions/flowise/BEST_PRACTICES.md
      ```

   🚨 **CRITICAL: Standard Tools Research** 🚨
   EVERY Flowise agent MUST include 2 standard tools:
   1. **currentDateTime** - Provides temporal context (date/time awareness)
   2. **searXNG** - Real-time web search (federated meta-search)

   Read the exact structure from:
   /Users/name/homelab/context-foundry/extensions/flowise/prompts/AGENT-NODE-TEMPLATE.json

   Document in scout-report.md:
   - "✅ Standard tools (currentDateTime + searXNG) will be included in ALL agents"
   - Note the exact field names and structure requirements
   - Flag that these are REAL tools (not phantom references)

   **Scout Focus Areas (Flowise-Only):**
   - Flow type analysis (multi-agent, RAG, workflow, chatbot)
   - Agent count and specialization requirements
   - Node architecture and data flow (canonical Flowise structures)
   - Tool requirements and configurations
   - Memory strategy (built-in agent memory vs separate nodes)
   - Prompt templates and persona patterns
   - Edge connections and condition routing logic
   - Testing strategy (JSON validation, Flowise import testing)
   - Anti-patterns to avoid (from FAILURE_PATTERNS.md)

   **Scout Output (Flowise Projects):**
   Create scout-report.md focusing EXCLUSIVELY on Flowise workflow design.
   Include: Flow type, agent specifications, node count estimate, tool/memory strategy, JSON structure plan.
   SKIP: Web app architecture, frontend/backend design, database schemas, API endpoints.

   See Flowise extension documentation and AGENT_PATTERN_REFERENCE.md for complete checklist.

2. Create a Scout agent:
   Type: /agents
   When prompted, provide this description:
   "Expert researcher who gathers requirements, explores codebases, analyzes constraints, and provides comprehensive context for implementation. I analyze existing code, research best practices, identify technical requirements, and create detailed findings reports. I also review past project learnings to prevent known issues."

3. Activate Scout and research:
   - Analyze the task requirements thoroughly
   - **Apply learnings from past patterns (if available)**
   - Explore existing files in the working directory
   - Identify technology stack and constraints
   - Research best practices for this type of project
   - Review similar successful implementations
   - **Check for known issues matching this project type**
   - Document potential challenges and recommended solutions
   - Identify all testing requirements
   - **Note which past learnings are relevant**

   **CRITICAL: API Integration Research (if project uses external APIs):**
   - Research API's CORS policy by checking API documentation
   - Look for indicators:
     * "Server-side only" or "No browser requests"
     * Requires API key in headers (usually means server-side only)
     * Enterprise/aviation/financial APIs (usually restrictive)
   - If API blocks CORS: Flag need for backend proxy in scout-report.md
   - Pattern ID: cors-external-api-backend-proxy

   **Enhancement modes:** See §Enhancement Mode Reference for Scout phase guidance

4. Save Scout findings:
   Create file: .context-foundry/scout-report.md

   ⚠️  KEEP IT CONCISE - Target 5-10KB, not 60KB!

   Include:
   - Executive summary of task (2-3 paragraphs max)
   - **Relevant past learnings applied (if any)** (bullet points)
   - **Known risks flagged from pattern library** (bullet points)
   - Key requirements (bulleted list, not essay)
   - Technology stack decision with brief justification
   - Critical architecture recommendations (top 3-5 items)
   - Main challenges and mitigations (top 3-5 items)
   - Testing approach (brief outline)
   - Timeline estimate (1 line)
   - **Environment Checklist - GitHub Deployment:**
     ```
     ## GitHub Deployment Readiness

     Checking deployment environment...

     - [ ] GitHub CLI (gh) installed: [RUN: command -v gh >/dev/null 2>&1 && echo "✅ PASS" || echo "⚠️  FAIL - Install: brew install gh (macOS) or sudo apt install gh (Linux)"]
     - [ ] GitHub authentication: [RUN: gh auth status 2>&1 | grep -q "Logged in" && echo "✅ PASS" || echo "⚠️  FAIL - Run: gh auth login"]
     - [ ] Git user configured: [RUN: git config user.name && git config user.email && echo "✅ PASS" || echo "⚠️  FAIL - Run: git config --global user.name 'Name' && git config --global user.email 'email@example.com'"]

     **Deployment Status:** [If all PASS: "✅ Ready for GitHub deployment" | If any FAIL: "⚠️  Deployment will be skipped - manual deployment required"]

     Note: Missing GitHub tools will NOT fail the build. Deployment is optional - build artifacts will be created successfully regardless.
     ```

   DO NOT write exhaustive documentation - Architect will expand details.

5. **Save Scout report to cache (if incremental mode enabled):**
   ```python
   python3 -c "
   import sys
   sys.path.insert(0, '/Users/name/homelab/context-foundry')
   from tools.cache.scout_cache import save_scout_report_to_cache

   with open('.context-foundry/scout-report.md', 'r') as f:
       report_content = f.read()

   save_scout_report_to_cache(
       task='TASK_DESCRIPTION',
       mode='MODE',
       working_directory='WORKING_DIR',
       scout_report_content=report_content
   )
   "
   ```
   This enables future builds with similar tasks to skip Scout phase entirely.

6. **BACK PRESSURE: Technology Stack Validation (Optional but Recommended)**

   Validate Scout's technology recommendations are feasible:
   ```bash
   python3 tools/back_pressure/validate_tech_stack.py .context-foundry/scout-report.md
   ```

   **If validation available and FAILS**:
   - Log errors to .context-foundry/tech-stack-validation-errors.json
   - Review errors and either:
     * Re-run Scout with technology constraints, OR
     * Note warnings but continue (don't block on tech availability)
   - Maximum 1 validation retry

   **If validation PASSES or unavailable**:
   - Log: "✅ Technology stack validated" or "⚠️  Validation skipped"
   - Continue to Phase 2 (Architect)

   **Note**: Tech stack validation is advisory - unavailable tools won't block the build.

5. **RECORD ACTUAL CONTEXT USAGE:**
   Count tokens in scout-report.md and record:
   ```bash
   # Count tokens in Scout output
   SCOUT_TOKENS=$(python3 -c "
   import sys
   sys.path.insert(0, '/Users/name/homelab/context-foundry')
   from tools.context_budget import TokenCounter
   from pathlib import Path

   counter = TokenCounter()
   tokens = counter.count_file_tokens(Path('.context-foundry/scout-report.md'))
   print(tokens)
   ")

   # Record usage
   python3 tools/check_context_budget.py --phase scout --tokens $SCOUT_TOKENS
   ```

   This updates session-summary.json with actual usage and warns if budget exceeded.

**PHASE TRACKING (COMPLETE) - MANDATORY LAST ACTION:**
Update phase: "Scout" (1/7, "completed", "Research complete")
Add to phases_completed: ["Scout"]

✅ Scout complete. Proceed to Architect.

