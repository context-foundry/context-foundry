PHASE 4: TEST (Validation & Quality Assurance + Pattern-Based Testing)

**⚡ SMART CACHE CHECK - INCREMENTAL BUILDS:**

**IF incremental mode is enabled (check CONFIGURATION.incremental):**

1. **Check for cached test results:**
   ```python
   python3 -c "
   import sys
   sys.path.insert(0, '/Users/name/homelab/context-foundry')
   from tools.cache.test_cache import get_cached_test_results

   cached = get_cached_test_results(
       working_directory='WORKING_DIR'
   )

   if cached:
       print('CACHE_HIT')
       # Save cached results to expected location
       import json
       with open('.context-foundry/test-final-report.md', 'w') as f:
           f.write(f'''# Test Results (Cached)

**Status**: {cached.get(\"success\", False) and \"✅ PASSED\" or \"❌ FAILED\"}
**Tests Passed**: {cached.get(\"passed\", 0)}/{cached.get(\"total\", 0)}
**Duration**: {cached.get(\"duration\", 0):.2f}s
**Source**: Cached (no code changes detected)

All source files unchanged since last test run.
Reusing cached test results.
''')
   else:
       print('CACHE_MISS')
   "
   ```

2. **If CACHE_HIT and tests PASSED:**
   - ✅ Test phase complete (reused cached results)
   - Skip to Phase 4.5 (Screenshot) or Phase 5 (Documentation)
   - Log: "⚡ Incremental build: No code changes, reusing test results"
   - Update phase tracking: "Test" → "completed" (cache hit)

3. **If CACHE_MISS or tests FAILED:**
   - Continue with normal Test phase below
   - After completing tests, save to cache (see end of phase)

⚡ **PERFORMANCE OPTIMIZATION**: Check for parallel test opportunity first
   If project has 2+ test types (unit/e2e/lint), use parallel execution
   60-70% faster than sequential testing!

0. Write phase status (REQUIRED FIRST STEP):
   Update .context-foundry/current-phase.json:
   Read current .context-foundry/test-iteration-count.txt (default to 1 if doesn't exist)
   {
     "current_phase": "Test",
     "phase_number": "4/7",
     "status": "testing",
     "progress_detail": "Running test suite and validating implementation",
     "test_iteration": {current_iteration},
     "phases_completed": ["Scout", "Architect", "Builder"],
     "started_at": "{current ISO timestamp}",
     "last_updated": "{current ISO timestamp}"
   }

0.25 **CHECK CONTEXT BUDGET:**
   ```bash
   python3 tools/check_context_budget.py --phase test --check-before
   ```

   Test phase has 20% budget - test outputs can be large!

   **If approaching DUMB ZONE:**
   - Use parallel test execution (already planned below)
   - Each test type in isolated context
   - Aggregate results without full output in main context

0.5 **MANDATORY: PARALLEL TEST EXECUTION** (Always use parallel tests for maximum speed)

   **Check for multiple test types first:**
   - Look for: package.json scripts (test:unit, test:e2e, test:lint, test, etc.)
   - If 2+ independent test types exist: MUST use parallel execution (60-70% faster)
   - If only one test type: Skip to sequential testing below

   **Execute tests in parallel (REQUIRED if 2+ test types):**
   ```bash
   # Create test-logs directory
   mkdir -p .context-foundry/test-logs

   # Read Context Foundry installation path
   CF_PATH="$(cd "$(dirname "$(which claude)")/../.." && pwd)/context-foundry"
   TEST_PROMPT="$CF_PATH/tools/test_task_prompt.txt"

   # Spawn unit tests (background)
   claude --print --system-prompt "$(cat "$TEST_PROMPT")" \
     "TEST_TYPE: unit" \
     > .context-foundry/test-logs/unit.log 2>&1 &
   PID_UNIT=$!

   # Spawn E2E tests (background)
   claude --print --system-prompt "$(cat "$TEST_PROMPT")" \
     "TEST_TYPE: e2e" \
     > .context-foundry/test-logs/e2e.log 2>&1 &
   PID_E2E=$!

   # Spawn lint tests (background)
   claude --print --system-prompt "$(cat "$TEST_PROMPT")" \
     "TEST_TYPE: lint" \
     > .context-foundry/test-logs/lint.log 2>&1 &
   PID_LINT=$!

   # Wait for all tests to complete
   wait $PID_UNIT $PID_E2E $PID_LINT

   # Verify all .done files exist
   for test_type in unit e2e lint; do
     if [ ! -f ".context-foundry/test-logs/$test_type.done" ]; then
       echo "ERROR: $test_type tests did not complete"
       exit 1
     fi
   done
   ```

   **Aggregate test results:**
   - Read all .context-foundry/test-logs/*.log files
   - Parse JSON results from each test type
   - Combine into unified test report
   - Check if ANY tests failed

   **If parallel tests passed:** Skip to Screenshot phase

   **If parallel tests failed:** Continue with sequential Tester agent analysis below

1. Review Testing Patterns (Self-Learning System - GLOBAL PATTERNS):

   **Read GLOBAL pattern files** using MCP tools:
   - Use `read_global_patterns("common-issues")` to get test patterns from ALL past projects

   If patterns indicate additional testing needed (learned from ANY past build):
   - Check for browser compatibility issues (if web app) - learned from past web app failures
   - Check for CORS/module loading (if ES6 modules) - learned from past browser app failures
   - Check for integration issues flagged by patterns - learned from all project types
   - Run environment-specific tests based on project type - learned from past similar projects

   Example: If browser app with ES6 modules (using learnings from past browser app builds):
   - Verify module loading works (learned this is critical from past CORS failures)
   - Check for CORS errors (high-frequency pattern from browser app builds)
   - Test dev server starts properly (prevention from past deployment failures)
   - Validate game/app runs in actual browser (integration test from past testing gaps)

2. Create Tester agent:
   Type: /agents
   Description: "Expert QA engineer who validates implementations thoroughly. I run all tests, check for errors and edge cases, validate against requirements, analyze failures deeply, and provide detailed reports with specific recommendations for fixes. I also run pattern-based integration tests to catch known issues that unit tests miss."

3. Activate Tester and validate:

   🚨 **FLOWISE PROJECTS: Mandatory Standard Tools Validation** 🚨

   **IF this is a Flowise project** (check CONFIGURATION for flowise_flow: True):

   **BEFORE running any other tests, Tester MUST validate standard tools:**

   ```bash
   # Create validation script
   cat > /tmp/validate_flowise_tools.py << 'VALIDATION_SCRIPT'
#!/usr/bin/env python3
import json
import sys
from pathlib import Path

# Find all .json files in current directory
json_files = list(Path('.').glob('*.json'))
flowise_files = []

for file in json_files:
    try:
        with open(file) as f:
            data = json.load(f)
            if 'nodes' in data and 'edges' in data:
                flowise_files.append(file)
    except:
        continue

if not flowise_files:
    print("⚠️  No Flowise JSON files found")
    sys.exit(0)

print(f"🔍 Validating {len(flowise_files)} Flowise workflow(s)...")

all_passed = True
for workflow_file in flowise_files:
    print(f"\n📄 Checking: {workflow_file}")

    with open(workflow_file) as f:
        flow = json.load(f)

    agents = [n for n in flow['nodes'] if n.get('data', {}).get('name') == 'agentAgentflow']

    if not agents:
        print("  ℹ️  No agent nodes found (may be non-agent flow)")
        continue

    print(f"  Found {len(agents)} agent(s)")

    for agent in agents:
        agent_id = agent['id']
        agent_label = agent.get('data', {}).get('label', 'Unknown')
        tools = agent.get('data', {}).get('inputs', {}).get('agentTools', [])

        # Handle both array of objects and empty string
        if isinstance(tools, str):
            tools = []

        tool_names = [t.get('toolName') for t in tools if isinstance(t, dict)]

        # Check for required tools
        has_datetime = 'currentDateTime' in tool_names
        has_searxng = 'searXNG' in tool_names

        if not has_datetime:
            print(f"  ❌ FAIL: Agent '{agent_label}' ({agent_id}) missing currentDateTime tool")
            all_passed = False

        if not has_searxng:
            print(f"  ❌ FAIL: Agent '{agent_label}' ({agent_id}) missing searXNG tool")
            all_passed = False

        if has_datetime and has_searxng:
            print(f"  ✅ PASS: Agent '{agent_label}' has both required tools")

            # Validate searXNG structure
            searxng_tool = next((t for t in tools if t.get('toolName') == 'searXNG'), None)
            if searxng_tool:
                if 'apiBase' not in searxng_tool:
                    print(f"  ⚠️  WARNING: searXNG missing 'apiBase' field (should be 'apiBase' not 'baseUrl')")
                    all_passed = False

if all_passed:
    print("\n✅ ALL AGENTS HAVE REQUIRED STANDARD TOOLS")
    sys.exit(0)
else:
    print("\n❌ VALIDATION FAILED: Some agents missing required tools")
    print("\n🔧 FIX REQUIRED:")
    print("1. Read template: /Users/name/homelab/context-foundry/extensions/flowise/prompts/AGENT-NODE-TEMPLATE.json")
    print("2. Copy agentTools structure from lines 341-367")
    print("3. Add to EVERY agent node's inputs.agentTools array")
    print("4. Re-run this validation")
    sys.exit(1)
VALIDATION_SCRIPT

   python3 /tmp/validate_flowise_tools.py

   VALIDATION_EXIT_CODE=$?
   ```

   **IF validation FAILS (exit code 1)**:
   - ❌ **STOP all other testing immediately**
   - ❌ Mark test phase as FAILED
   - Return to Builder phase with specific instructions:
     ```
     Builder must:
     1. Read AGENT-NODE-TEMPLATE.json (lines 341-367)
     2. Add currentDateTime and searXNG tools to EVERY agent
     3. Use EXACT structure from template (no modifications)
     4. Re-run validation before proceeding
     ```
   - Do NOT proceed to other tests until tools are fixed

   **IF validation PASSES (exit code 0)**:
   - ✅ Log: "Standard tools validation passed"
   - ✅ Proceed to comprehensive pattern-based validation

   🚨 **FLOWISE PROJECTS: Comprehensive Pattern-Based Validation** 🚨

   **Run comprehensive validator (validates ALL 10 patterns)**:

   ```bash
   python3 /Users/name/homelab/context-foundry/extensions/flowise/validate_workflow.py *.json

   VALIDATION_EXIT_CODE=$?
   ```

   **IF validation FAILS (exit code 1)**:
   - ❌ **CRITICAL FAILURES DETECTED** - Build BLOCKED
   - Review validation output for specific issues
   - Common failures:
     * Pattern #10: HIL gate with humanInputOutputAnchors inputParam (blank screen in Flowise)
     * Pattern #6: Incorrect tool structure (missing agentSelectedToolConfig)
     * Pattern #4: Disconnected nodes (scenario count ≠ edge count)
     * STRUCTURE: Invalid outputAnchor IDs (extra suffixes like -StartFlow, -Agent|AgentExecutor)
     * STRUCTURE: agentMessages as array (should be empty string)
   - Return to Builder phase with specific fix instructions
   - Do NOT proceed until validation passes

   **IF validation has WARNINGS (exit code 2)**:
   - ⚠️  Manual review recommended
   - Log warnings for user review
   - Proceed with remaining tests (warnings don't block)

   **IF validation PASSES (exit code 0)**:
   - ✅ Log: "Comprehensive pattern validation passed (10 patterns checked)"
   - ✅ Continue with remaining test suite

   **Patterns Validated**:
   - Pattern #1: Meta-description detection
   - Pattern #4: Disconnected agent nodes
   - Pattern #5: Phantom tool references
   - Pattern #6: Incorrect tool JSON structure
   - Pattern #8: Missing inputParams arrays
   - Pattern #10: HIL gate invalid inputParams (NEW!)
   - STRUCTURE: OutputAnchor ID format
   - STRUCTURE: agentMessages type

   **End of Flowise-specific validation**

   - Run ALL tests as specified in architecture
   - **Run pattern-based integration tests (if applicable)**
   - For automated tests: Execute test suite and capture results
   - For manual tests: Simulate user interactions and validate
   - Check for:
     * Functionality correctness
     * Error handling
     * Edge cases
     * Performance issues
     * Code quality
     * **Known issues from pattern library**
     * **Browser compatibility (if web app)**
     * **Module loading (if ES6 modules)**
   - Validate against original requirements from Scout phase
   - Document ALL test results in detail

   **E2E Testing for SPAs (MANDATORY for web apps):**
   SPAs MUST have at least ONE E2E test that:
   - Starts actual dev server (NOT mocked)
   - Opens real browser (Playwright/Cypress, NOT jsdom)
   - Navigates to app URL
   - Waits for content to load
   - Checks for console errors
   - Tests key user interaction (click, input, navigation)

   **Why this is critical:**
   - Unit tests DON'T catch: CORS errors, infinite loops, broken clicks
   - Integration tests DON'T catch: Real browser issues, API integration
   - E2E tests catch 80% of production bugs
   - ONE simple E2E test would have caught ALL 4 flight tracker issues

   **Example E2E test (Playwright):**
   ```javascript
   test('app loads and displays data', async ({ page }) => {
     await page.goto('http://localhost:5173')
     await page.waitForSelector('.primary-content')

     // Check for console errors
     const errors = []
     page.on('console', msg => {
       if (msg.type() === 'error') errors.push(msg.text())
     })

     expect(errors).toHaveLength(0)

     // Verify content loaded
     const content = await page.locator('.primary-content').count()
     expect(content).toBeGreaterThan(0)

     // Test interaction
     await page.click('.some-button')
     await page.waitForSelector('.expected-result')
   })
   ```

   Pattern ID: e2e-testing-spa-real-browser

   **Passing tests ≠ Working app. Always test in target environment (real browser for SPAs).**

3. Analyze results:

   **IF ALL TESTS PASS:**
   - Document success
   - Create file: .context-foundry/test-final-report.md
   - Mark status as "PASSED"
   - **Save test results to cache (if incremental mode enabled):**

     **Check if incremental mode is enabled:**
     ```bash
     # Read incremental setting from task config
     INCREMENTAL=$(python3 -c "import json; config=json.load(open('.context-foundry/task-config.json')); print(config.get('incremental', False))")

     if [ "$INCREMENTAL" = "True" ]; then
         echo "⚡ Incremental mode enabled - saving test cache..."

         # Save test results to cache
         python3 <<'PYTHON_SCRIPT'
import sys
import re
from pathlib import Path

sys.path.insert(0, '/Users/name/homelab/context-foundry')
from tools.cache.test_cache import save_test_results_to_cache

# Parse test results from test output (saved in variables or test-final-report.md)
# Default values if parsing fails
test_results = {
    'success': True,
    'passed': 0,
    'total': 0,
    'duration': 0.0,
    'test_command': 'npm test'  # or pytest, etc.
}

# Try to extract from test-final-report.md if it exists
report_file = Path('.context-foundry/test-final-report.md')
if report_file.exists():
    report_content = report_file.read_text()

    # Extract test count (look for patterns like "25/25 passing" or "25 passed, 0 failed")
    patterns = [
        r'(\d+)/(\d+)\s+(?:passing|passed)',  # Jest/Mocha: "25/25 passing"
        r'(\d+)\s+passed.*?(\d+)\s+total',     # pytest: "25 passed, 25 total"
        r'All\s+(\d+)\s+tests?\s+passed',       # Generic: "All 25 tests passed"
    ]

    for pattern in patterns:
        match = re.search(pattern, report_content, re.IGNORECASE)
        if match:
            if len(match.groups()) == 2:
                test_results['passed'] = int(match.group(1))
                test_results['total'] = int(match.group(2))
            elif len(match.groups()) == 1:
                count = int(match.group(1))
                test_results['passed'] = count
                test_results['total'] = count
            break

    # Extract duration if present
    duration_match = re.search(r'Duration[:\s]+(\d+\.?\d*)\s*(?:seconds|s)', report_content, re.IGNORECASE)
    if duration_match:
        test_results['duration'] = float(duration_match.group(1))

# Save to cache
try:
    save_test_results_to_cache('.', test_results)
    print(f"✅ Test cache saved: {test_results['passed']}/{test_results['total']} tests")
except Exception as e:
    print(f"⚠️  Failed to save test cache: {e}")
    # Don't fail the build if cache save fails
PYTHON_SCRIPT
     else
         echo "⚠️  Incremental mode disabled - skipping test cache"
     fi
     ```
   - Update phase status:
     Update .context-foundry/current-phase.json:
     {
       "current_phase": "Test",
       "phase_number": "4/7",
       "status": "completed",
       "progress_detail": "All tests passed successfully",
       "test_iteration": {final_iteration},
       "phases_completed": ["Scout", "Architect", "Builder", "Test"],
       "last_updated": "{current ISO timestamp}"
     }
   - Proceed to PHASE 5 (Documentation)

   **IF ANY TESTS FAIL:**
   - Check test iteration count:
     * Read .context-foundry/test-iteration-count.txt
     * If file doesn't exist: Create it with content "1"
     * If count >= max_test_iterations: STOP and report final failure
     * If count < max_test_iterations: Increment count and continue self-healing

4. Self-Healing Loop (if tests failed and iterations remaining):

   a. Save detailed test failure analysis:
      Read current iteration from .context-foundry/test-iteration-count.txt
      Create file: .context-foundry/test-results-iteration-{N}.md
      Include:
      - Which tests failed (be specific)
      - Exact error messages
      - Stack traces if available
      - Root cause analysis (what went wrong?)
      - Impact assessment
      - Recommended fixes

   a2. Update phase status to show self-healing:
       Update .context-foundry/current-phase.json:
       {
         "current_phase": "Test",
         "phase_number": "4/7",
         "status": "self-healing",
         "progress_detail": "Tests failed, initiating fix cycle (iteration {N})",
         "test_iteration": {N},
         "phases_completed": ["Scout", "Architect", "Builder"],
         "last_updated": "{current ISO timestamp}"
       }

   a3. **FLOWISE PROJECTS ONLY**: Update FAILURE_PATTERNS.md with new learnings:

       **IF this is a Flowise project** (check CONFIGURATION for flowise_flow: True):

       Analyze the test failures and validation errors for common Flowise-specific patterns:

       ```bash
       # Check if this is a Flowise failure pattern worth documenting
       # Look for patterns like:
       # - Wrong node types (type: "customNode" instead of "agentFlow")
       # - Disconnected agents (nodes not connected to router)
       # - Missing required fields (credentials, tools, messages)
       # - Structural issues (wrong file format, missing nodes)

       # Read current failure patterns
       PATTERNS_FILE="/Users/name/homelab/context-foundry/extensions/flowise/FAILURE_PATTERNS.md"

       # If pattern is NEW and significant:
       # - Add new pattern section to FAILURE_PATTERNS.md
       # - Include: Symptom, Root Cause, Impact, Fix, Prevention
       # - Update Table of Contents
       # - Increment version number
       # - Add to Version History table

       # Example new pattern documentation:
       cat >> "$PATTERNS_FILE" << 'EOF'

## Pattern #{N}: {Pattern Name}

### Symptom
{What the user/builder sees - specific error messages, visual issues}

### Root Cause
{Why this happened - technical explanation}
{What Builder did wrong or misunderstood}

### Impact
- **Severity**: CRITICAL/HIGH/MEDIUM/LOW
- **Frequency**: {How often this occurs}
- **User Experience**: {Impact on end users}

### Fix
{Step-by-step fix for this specific issue}

### Prevention
**During {Phase} Phase**:
- [ ] {Specific check/action to prevent}
- [ ] {Another preventive measure}

**Validation Rules** (Builder MUST check):
```python
{Python validation code example}
```

---
EOF

       # Update Table of Contents
       # Update Version History
       # Commit to extension repository
       ```

       **Pattern Documentation Guidelines**:
       - Only document REPEATABLE patterns (not one-off errors)
       - Focus on Flowise-specific issues (not general coding errors)
       - Include concrete validation code when possible
       - Link to successful examples for reference
       - Keep patterns actionable and specific

       **Common Flowise Patterns to Watch For**:
       1. Node type mismatches
       2. Connection/edge issues (disconnected nodes)
       3. Field format errors (arrays vs strings vs objects)
       4. Missing required configurations
       5. Structural integrity violations

       After documenting:
       - Save to: /Users/name/homelab/context-foundry/extensions/flowise/FAILURE_PATTERNS.md
       - This will be loaded in NEXT build's Architect phase
       - Creates continuous learning loop

   b. Return to PHASE 2 (Architect) for redesign:
      - Architect agent analyzes test failure report
      - Architect identifies design flaws or gaps
      - Architect creates fix strategy
      - Architect updates .context-foundry/architecture.md with:
        * What needs to be changed
        * Why it failed
        * How the fix will work
      - Create file: .context-foundry/fixes-iteration-{N}.md documenting the fix plan

   c. Return to PHASE 3 (Builder) for re-implementation:
      - Builder reads:
        * Updated architecture
        * Test failure analysis
        * Fix plan
      - Builder implements fixes precisely
      - Builder ensures tests are updated if needed
      - Builder updates .context-foundry/build-log.md with fix details

   d. Return to PHASE 4 (Test) for re-validation:
      - Increment .context-foundry/test-iteration-count.txt
      - Run ALL tests again
      - If tests pass: Proceed to Documentation
      - If tests fail: Repeat loop (up to max_test_iterations)

5. Maximum iterations reached:
   If tests still fail after max_test_iterations:
   - Create file: .context-foundry/test-final-report.md
   - Document all attempts made
   - Mark status as "FAILED_MAX_ITERATIONS"
   - Do NOT proceed to deployment
   - Return failure report

