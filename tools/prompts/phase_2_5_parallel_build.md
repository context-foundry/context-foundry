PHASE 2.5: PARALLEL BUILD PLANNING (MANDATORY - ALWAYS USE)


⚡ **ALWAYS USE PARALLEL BUILDERS - NO EXCEPTIONS**

**Purpose:** Break down implementation into parallel tasks for concurrent execution (40-50% faster)

**MANDATORY for ALL projects:** Even small projects benefit from parallelization
- Small projects (2-5 files): Create 2 parallel tasks minimum
- Medium projects (6-15 files): Create 3-4 parallel tasks
- Large projects (16+ files): Create 4-8 parallel tasks

**NO SEQUENTIAL BUILDING ALLOWED** - This phase is REQUIRED, not optional

**Enhancement modes:** See §Enhancement Mode Reference for build planning guidance. Create feature branch first: `git checkout -b enhancement/descriptive-name`

🚨 **FLOWISE EXCEPTION - EXCLUSIVE BUILD MODE:**

**IF CONFIGURATION shows flowise_flow: True (FLOWISE-ONLY MODE):**

🚨 **FLOWISE-ONLY BUILD** 🚨

**DO NOT build:**
❌ React components or frontend UI files
❌ Backend server files (Express, FastAPI, etc.)
❌ Database schemas or migrations
❌ API endpoint files
❌ Traditional web app directory structure
❌ Multiple JSON files for workflow
❌ Separate config files that split the workflow

**ONLY build:**
✅ SINGLE workflow JSON file (e.g., `skills-inference-flow.json`)
✅ README.md (usage instructions)
✅ INTEGRATION_GUIDE.md (how to import into Flowise)

**SPECIAL BUILD RULES FOR FLOWISE:**
1. ❌ **DO NOT use parallel build tasks for JSON generation**
2. ❌ **DO NOT split nodes across multiple files**
3. ❌ **DO NOT create separate config files**
4. ✅ **Generate EXACTLY ONE workflow JSON file** (e.g., `workflow-name.json`)
5. ✅ **ALL nodes MUST be in single "nodes" array**
6. ✅ **ALL edges MUST be in single "edges" array**
7. ✅ **Self-contained structure** (no external references)

**Why this is critical:**
- Flowise imports require EXACTLY ONE JSON file per workflow
- Creating multiple JSON files = Pattern #3 violation (Separate Config Files Anti-Pattern)
- Parallel build tasks may attempt to split node generation → MUST be prevented
- Example of what NOT to do:
  ```
  ❌ flowise-workflow-nodes-0-1.json
  ❌ flowise-workflow-nodes-2-4.json
  ❌ flowise-workflow-nodes-5-7.json
  ```

**Correct Flowise build approach:**
```json
// .context-foundry/build-tasks.json for Flowise project
{
  "parallel_mode": false,  // ← CRITICAL: NO parallel mode for Flowise JSON
  "total_tasks": 1,
  "tasks": [
    {
      "id": "flowise-flow",
      "description": "Create complete Flowise workflow in single JSON file",
      "files": ["workflow-name.json"],
      "dependencies": [],
      "estimated_time": "15-20 minutes"
    }
  ]
}
```

**Additional Flowise project files** (these CAN be parallel):
- Documentation (README.md, INTEGRATION_GUIDE.md) - parallel OK
- Tool configs (tool-configs/*.json) - parallel OK
- Knowledge configs (knowledge-configs/*.json) - parallel OK

**Only the main workflow JSON must be generated as a single, non-parallel task.**

🚨🚨🚨 **MANDATORY BUILDER REQUIREMENT: Read Files BEFORE Generating Agents** 🚨🚨🚨

**BEFORE generating ANY agent node, Builder MUST execute these Read commands**:

1. **READ FAILURE_PATTERNS.md** (understand what NOT to do):
   ```
   Read /Users/name/homelab/context-foundry/extensions/flowise/FAILURE_PATTERNS.md
   ```
   **WHY**: Contains 6+ failure patterns with EXACT validation code to prevent crashes.
   Pattern #6 specifically addresses the tool structure issue you MUST avoid.

2. **READ the AGENT-NODE-TEMPLATE.json** (get the correct structure):
   ```
   Read /Users/name/homelab/context-foundry/extensions/flowise/prompts/AGENT-NODE-TEMPLATE.json
   ```
   **WHY**: This has the EXACT, tested, working structure for agent nodes.

3. **LOCATE lines 341-367** in the template (agentTools array structure)

4. **COPY the agentTools structure EXACTLY** into every agent node:
   - currentDateTime tool (lines 341-351)
   - searXNG tool (lines 352-367)

5. **VERIFY after generation** that both tools are present in EVERY agent

**Standard Agent Tools (REQUIRED for ALL agents)**:
Every Flowise agent MUST include these 2 tools in agentTools array with EXACT Flowise UI structure:

1. **currentDateTime** (temporal context)
   - NO configuration needed
   - Copy structure from template lines 341-351

2. **searXNG** (real-time web search)
   - ⚠️ CRITICAL: "searXNG" (capital X, capital NG) NOT "searxng-search"
   - ⚠️ CRITICAL: Field "apiBase" NOT "baseUrl"
   - ⚠️ CRITICAL: RequiresHumanInput: "" (empty string) NOT false (boolean)
   - ⚠️ CRITICAL: Include ALL fields: toolName, toolDescription, headers, format, categories, engines, etc.
   - Copy structure from template lines 352-367

**WHY Builder Must Read Template First**:
- ❌ Manual typing → Typos → Flowise crashes (Pattern #6)
- ❌ Guessing structure → Wrong fields → Import fails
- ✅ Copy from template → Exact structure → Works perfectly
- ✅ Template is tested and validated → Zero errors

**Validation Checklist (Builder MUST verify after generation)**:
```python
# Check that EVERY agent has both tools:
import json
flow = json.load(open('workflow.json'))
for node in flow['nodes']:
    if node['data']['name'] == 'agentAgentflow':
        tools = node['data']['inputs'].get('agentTools', [])
        tool_names = [t.get('toolName') for t in tools if isinstance(t, dict)]
        assert 'currentDateTime' in tool_names, f"Agent {node['id']} missing currentDateTime"
        assert 'searXNG' in tool_names, f"Agent {node['id']} missing searXNG"
print("✅ All agents have required standard tools")
```

These are NOT phantom references (Pattern #5) and NOT incorrect structure (Pattern #6).
They are real, working tools with correct Flowise UI JSON structure.

**PHASE TRACKING (START) - MANDATORY FIRST ACTION:**
Use BAML for type-safe phase tracking (see template above):
```bash
python3 tools/use_baml.py update-phase \
  "Builder" \
  "planning" \
  "Planning parallel build tasks" \
  --session-id "$(basename $(pwd))" \
  --iteration 0 \
  > .context-foundry/current-phase.json
```

0. **CHECK CONTEXT BUDGET (CRITICAL FOR BUILDER):**
   ```bash
   python3 tools/check_context_budget.py --phase builder --check-before
   ```

   Builder phase has 20% budget (40K tokens) - largest allocation.

   **If exit code 2 (CRITICAL):**
   - MUST use parallel builders with isolated contexts
   - Each builder gets fresh context window
   - Acts as automatic "garbage collection" for tokens

   This is WHY Phase 2.5 uses parallel builders - context management!

1. Analyze architecture for parallelization:
   - Count total files/modules to create
   - Identify dependencies between modules
   - Group independent tasks together

2. Create task breakdown:
   Create file: .context-foundry/build-tasks.json

   Format:
   ```json
   {
     "parallel_mode": true,
     "total_tasks": {count},
     "tasks": [
       {
         "id": "task-1",
         "description": "Create game engine core (game.js, engine.js)",
         "files": ["src/game.js", "src/engine.js"],
         "dependencies": [],
         "estimated_time": "5 minutes"
       },
       {
         "id": "task-2",
         "description": "Create player system (player.js, input.js)",
         "files": ["src/player.js", "src/input.js"],
         "dependencies": [],
         "estimated_time": "5 minutes"
       },
       {
         "id": "task-3",
         "description": "Create main entry point",
         "files": ["src/main.js"],
         "dependencies": ["task-1", "task-2"],
         "estimated_time": "2 minutes"
       }
     ]
   }
   ```

3. Determine parallelism level:
   - If tasks < 4: Use 2 parallel builders
   - If tasks 4-8: Use 4 parallel builders
   - If tasks > 8: Use 6 parallel builders

4. Execute parallel builders:

   **Create builder-logs directory:**
   ```bash
   mkdir -p .context-foundry/builder-logs
   ```

   **For each independent task (level 0 - no dependencies):**
   ```bash
   # Read Context Foundry installation path
   CF_PATH="$(cd "$(dirname "$(which claude)")/../.." && pwd)/context-foundry"
   BUILDER_PROMPT="$CF_PATH/tools/builder_task_prompt.txt"

   # Spawn builder for task-1 (background)
   claude --print --system-prompt "$(cat "$BUILDER_PROMPT")" \
     "TASK_ID: task-1 | DESCRIPTION: Create game engine core | FILES: src/game.js, src/engine.js" \
     > .context-foundry/builder-logs/task-1.log 2>&1 &
   PID_1=$!

   # Spawn builder for task-2 (background)
   claude --print --system-prompt "$(cat "$BUILDER_PROMPT")" \
     "TASK_ID: task-2 | DESCRIPTION: Create player system | FILES: src/player.js, src/input.js" \
     > .context-foundry/builder-logs/task-2.log 2>&1 &
   PID_2=$!

   # Wait for all level 0 tasks to complete
   wait $PID_1 $PID_2
   ```

   **Check for completion:**
   ```bash
   # Verify all .done files exist
   for task in task-1 task-2; do
     if [ ! -f ".context-foundry/builder-logs/$task.done" ]; then
       echo "ERROR: Task $task did not complete"
       exit 1
     fi
   done
   ```

   **Then spawn dependent tasks (level 1):**
   ```bash
   # task-3 depends on task-1 and task-2 (now complete)
   claude --print --system-prompt "$(cat "$BUILDER_PROMPT")" \
     "TASK_ID: task-3 | DESCRIPTION: Create main entry point | FILES: src/main.js"
   ```

5. Aggregate results:
   - Collect all task-*.log files
   - Check for any .error files
   - Verify all expected files were created
   - Update build-log.md with parallel execution summary

6. Update phase status:
   Update .context-foundry/current-phase.json:
   {
     "current_phase": "Builder",
     "phase_number": "3/7",
     "status": "completed",
     "progress_detail": "Parallel build complete ({N} tasks, {M} parallel workers)",
     "test_iteration": 0,
     "phases_completed": ["Scout", "Architect", "Builder"],
     "parallel_execution": true,
     "tasks_completed": {count},
     "last_updated": "{current ISO timestamp}"
   }

**After parallel build completes:**
- ✅ **If successful:** Proceed to Build Finalization steps below
- ❌ **If failed:** Debug and retry parallel build (do NOT fall back to sequential)
  - Check builder-logs/*.error files
  - Fix issues and re-run Phase 2.5
  - Sequential building is DEPRECATED and must not be used

**Build Finalization (Essential Project Files):**

After all code files are created, generate essential project files:

1. **Create README.md:**
   Auto-generate from architecture.md and build logs:
   ```bash
   # Use available context to create comprehensive README
   cat > README.md << 'EOF'
   # [Project Name from architecture.md]

   [Brief description from scout-report.md executive summary]

   ## Features

   [Extract from architecture.md implemented features section]

   ## Installation

   \`\`\`bash
   # Add installation steps based on project type
   # e.g., npm install, pip install -r requirements.txt, etc.
   \`\`\`

   ## Usage

   [Extract from architecture.md or add basic usage instructions]

   ## Testing

   [Add test command, e.g., npm test, pytest, etc.]

   ## Project Structure

   [Brief file structure if complex]

   ## Technologies

   [List from scout-report.md technology stack]

   🤖 Generated with Context Foundry
   EOF
   ```

2. **Create .gitignore:**
   Template based on project type:
   ```bash
   # Detect project type and create appropriate .gitignore
   if [ -f "package.json" ]; then
     # Node.js project
     cat > .gitignore << 'EOF'
   node_modules/
   .env
   .env.local
   dist/
   build/
   .DS_Store
   .context-foundry/
   test-results/
   playwright-report/
   coverage/
   EOF
   elif [ -f "requirements.txt" ] || [ -f "pyproject.toml" ]; then
     # Python project
     cat > .gitignore << 'EOF'
   __pycache__/
   *.py[cod]
   venv/
   .env
   .pytest_cache/
   .coverage
   htmlcov/
   .context-foundry/
   *.egg-info/
   dist/
   build/
   EOF
   else
     # Generic .gitignore
     cat > .gitignore << 'EOF'
   .env
   .DS_Store
   .context-foundry/
   EOF
   fi
   ```

3. **Initialize Git Repository:**
   ```bash
   # Initialize git (if not already initialized)
   if [ ! -d ".git" ]; then
     git init
     git add .
     git commit -m "Initial commit: [Project Name]

   ✅ All features implemented
   ✅ Tests ready
   🤖 Generated by Context Foundry"

     echo "✅ Git repository initialized and initial commit created"
   else
     echo "ℹ️  Git repository already exists, skipping initialization"
   fi
   ```
