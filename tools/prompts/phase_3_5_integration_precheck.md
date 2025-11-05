PHASE 3.5: INTEGRATION PRE-CHECK (NEW - Fast Validation Before Test)
═══════════════════════════════════════════════════════════

**Purpose**: Catch syntax errors, import issues, and missing files BEFORE expensive test execution.
**Expected**: 5-15 seconds vs 30-120 seconds for full test suite.
**Catch Rate**: 30-40% of issues that would fail in Phase 4.

**When to run**: After Phase 2.5 (Parallel Builders complete), BEFORE Phase 4 (Test)

**BACK PRESSURE: Integration Validation**

1. Execute fast pre-checks:
   ```bash
   python3 tools/back_pressure/integration_pre_check.py .
   ```

2. Analyze results:

   **If ANY check FAILS**:
   - Save errors to .context-foundry/integration-errors.json
   - Analyze error type:
     * **Syntax errors**: Return to Phase 2.5 (Builder) with specific file/line errors
     * **Import errors**: Return to Phase 2 (Architect) - may be circular dependencies
     * **Missing files**: Return to Phase 2.5 (Builder) - files not created

   - Maximum 2 retries at Phase 3.5 level
   - If still failing after retries: Proceed to Phase 4 (full diagnostics in test phase)

   **If ALL checks PASS**:
   - Log: "✅ Integration pre-check passed ({duration}s)"
   - Log: "Estimated time saved vs failing in tests: {time_saved}s"
   - Proceed to Phase 4 (Test)

   **If validation unavailable or times out**:
   - Log: "⚠️  Integration pre-check skipped"
   - Proceed to Phase 4 (Test)

**Note**: Integration pre-check is optional but highly recommended. Skipping won't block the build.

✅ **Integration pre-check complete. Proceed to Phase 4 (Test).**


**After Build Finalization:**
- ✅ All files created (code + README + .gitignore)
- ✅ Git repository initialized with initial commit

**🎨 FLOWISE PROJECTS: Generate Workflow Diagram (MANDATORY - BLOCKING)**

**IF CONFIGURATION shows flowise_flow: True:**

**⚠️ CRITICAL SEQUENCE - FOLLOW IN EXACT ORDER:**

**THIS IS A BLOCKING REQUIREMENT - ENFORCED WITH EXIT CODES**

The build MUST NOT proceed to Phase 4 (Test) until ALL validation passes.
Validation failures will cause `exit 1` and terminate the build process.
This prevents deployment of Flowise workflows without visual documentation.

**STEP 1: Generate Mermaid Diagram File FIRST**

Run this command BEFORE creating or finalizing README.md:

```bash
# Execute mermaid generator
python3 /Users/name/homelab/context-foundry/extensions/flowise/mermaid_generator.py \
  <workflow-name>.json \
  WORKFLOW-DIAGRAM.md \
  --interactive \
  --badges \
  --legend

# MANDATORY: Check if command succeeded
if [ $? -ne 0 ]; then
    echo "❌ FATAL ERROR: mermaid_generator.py failed to execute"
    echo "Build is BLOCKED - cannot proceed without workflow diagram"
    exit 1
fi

# MANDATORY: Verify file was created
if [ ! -f WORKFLOW-DIAGRAM.md ]; then
    echo "❌ FATAL ERROR: WORKFLOW-DIAGRAM.md was not created"
    echo "Build is BLOCKED - file must exist before continuing"
    exit 1
fi

echo "✅ WORKFLOW-DIAGRAM.md created successfully"
```

This creates:
- `WORKFLOW-DIAGRAM.md`: Standalone diagram file with all enhancements
- Mermaid syntax with proper Flowise color scheme and emoji icons
- Flow metadata badges (node count, agents, complexity)
- Interactive <details> section with agent descriptions table
- Complete node type legend (all 14 node types)

---

**STEP 2: Read Diagram Content**

```bash
# Extract the full diagram content for embedding
DIAGRAM_CONTENT=$(cat WORKFLOW-DIAGRAM.md)
```

---

**STEP 3: Embed Diagram in README (BEFORE FINALIZING README)**

Insert the COMPLETE diagram content RIGHT AFTER the hero/title section, BEFORE "## Overview":

**Exact Structure:**
```markdown
# {Project Name}

{One-line description}

## 📊 Workflow Architecture

**[View Full Workflow Diagram →](./WORKFLOW-DIAGRAM.md)**

{PASTE ENTIRE CONTENT FROM WORKFLOW-DIAGRAM.md HERE - badges, mermaid block, interactive details, legend, everything}

---

## Overview
{Rest of README continues...}
```

**Key Points:**
- Include ALL content from WORKFLOW-DIAGRAM.md (not just the mermaid block)
- Include badges, interactive <details> section, and legend
- Place AFTER title/description, BEFORE "## Overview"
- Add horizontal rule `---` separator after diagram section

---

**STEP 4: Validation (BLOCKING - MUST PASS)**

**YOU MUST EXECUTE THESE EXACT COMMANDS - BUILD WILL FAIL IF ANY CHECK FAILS:**

```bash
echo "Running MANDATORY Mermaid diagram validation checks..."
echo ""

# Check 1: WORKFLOW-DIAGRAM.md exists
echo "Check 1/5: Verifying WORKFLOW-DIAGRAM.md exists..."
if [ ! -f WORKFLOW-DIAGRAM.md ]; then
    echo "❌ BLOCKING FAILURE: Missing WORKFLOW-DIAGRAM.md"
    echo "Build STOPPED - cannot proceed to Phase 4 (Test)"
    exit 1
fi
echo "✅ Pass"

# Check 2: README contains ```mermaid block
echo "Check 2/5: Verifying README contains mermaid diagram..."
if ! grep -q '```mermaid' README.md; then
    echo "❌ BLOCKING FAILURE: Diagram not embedded in README"
    echo "Build STOPPED - README must contain mermaid code block"
    exit 1
fi
echo "✅ Pass"

# Check 3: README contains interactive details section
echo "Check 3/5: Verifying README contains interactive details..."
if ! grep -q '<details>' README.md; then
    echo "❌ BLOCKING FAILURE: Missing interactive <details> section in README"
    echo "Build STOPPED - README must include collapsible agent details"
    exit 1
fi
echo "✅ Pass"

# Check 4: README contains badges
echo "Check 4/5: Verifying README contains diagram badges..."
if ! grep -q 'img.shields.io/badge' README.md; then
    echo "❌ BLOCKING FAILURE: Missing diagram badges in README"
    echo "Build STOPPED - README must include workflow metadata badges"
    exit 1
fi
echo "✅ Pass"

# Check 5: README contains "Workflow Architecture" section
echo "Check 5/5: Verifying README contains Workflow Architecture section..."
if ! grep -q '## 📊 Workflow Architecture' README.md; then
    echo "❌ BLOCKING FAILURE: Missing Workflow Architecture section in README"
    echo "Build STOPPED - README must have dedicated diagram section"
    exit 1
fi
echo "✅ Pass"

echo ""
echo "✅ ✅ ✅ All 5 Mermaid diagram validations PASSED"
echo "Build may proceed to Phase 4 (Test)"
```

**IMPORTANT**: If ANY validation fails:
- The build MUST STOP immediately
- DO NOT proceed to Phase 4 (Test)
- DO NOT deploy to GitHub
- The exit 1 command will terminate the build process

---

**Why This Is Critical:**
- ✅ GitHub natively renders Mermaid diagrams
- ✅ Users see workflow structure immediately without opening Flowise
- ✅ Interactive expandable section shows agent details
- ✅ Prominent placement at top ensures visibility
- ✅ Separate .md file allows deep-linking to diagram

**THIS IS A BLOCKING REQUIREMENT** - Flowise projects without embedded diagrams are considered INCOMPLETE and MUST NOT be deployed.

**End of Flowise diagram generation**

- ✅ Ready to proceed to Phase 4 (Test)

