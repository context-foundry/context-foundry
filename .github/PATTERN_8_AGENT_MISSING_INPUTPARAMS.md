# Pattern #8: Agent Nodes Missing inputParams - CRITICAL

**Date Discovered:** 2025-11-02
**Severity:** CRITICAL (Production Blocker)
**Status:** Added to pattern library

---

## User Report

> "When I double click on an agent in the ecommerce-support-flow.json, nothing happens. Agent.OrderTracking, Agent.Returns, Agent.Payment, etc. - nothing happens when I double click on them. I'm afraid the code is broken somewhere."

---

## The Problem

**All 8 agent nodes are missing the `inputParams` array**, which defines the UI schema for Flowise.

### What Happens:
- ✅ Workflow imports successfully (no errors)
- ✅ All nodes appear on canvas
- ✅ All connections render correctly
- ❌ **Double-clicking ANY agent does NOTHING**
- ❌ Cannot edit agent settings
- ❌ Workflow completely unusable

---

## Root Cause

**Missing UI Schema (inputParams array)**

The agent nodes were generated with:
```json
{
  "data": {
    "inputs": {
      "agentModel": "chatOpenAI",
      "agentMessages": [...],
      ...
    }
  }
}
```

But they need BOTH schema AND data:
```json
{
  "data": {
    "inputParams": [  // ← MISSING!
      {
        "label": "Model",
        "name": "agentModel",
        "type": "asyncOptions",
        ...
      },
      // ... 14 more parameter definitions
    ],
    "inputs": {
      "agentModel": "chatOpenAI",
      ...
    }
  }
}
```

### Understanding the Structure

- **`inputParams`** = SCHEMA (what fields exist, how to render them)
- **`inputs`** = DATA (values for those fields)

**Without inputParams**, Flowise UI has no schema to render the edit form.

---

## Impact

**Severity: CRITICAL**

- Workflow imports without errors (misleading - looks successful)
- All nodes visible but completely uneditable
- Must manually add ~300 lines of inputParams per agent
- 8 agents × 300 lines = **2,400+ lines of manual JSON editing**
- **Production blocker** - cannot customize or debug workflow

**Comparison to Other Patterns:**
- Pattern #7 (incomplete scenarios) - CAN open node, just fields are blank
- **Pattern #8 (missing inputParams) - CAN'T EVEN OPEN the node** ← WORSE

---

## Detection

### In Flowise UI (fastest):
1. Import workflow
2. Double-click any agent node
3. If nothing happens → inputParams missing

### In JSON:
```bash
# Quick check
grep -c '"inputParams"' workflow.json
# Should be >= agent count
# If 0 → CRITICAL BUG

# Detailed check
cat workflow.json | jq '.nodes[] | select(.data.type == "Agent") | .data | has("inputParams")'
# Should return: true for each agent
# If returns: false → PATTERN VIOLATED
```

---

## Files Updated

### 1. Global Pattern Library

**File:** `/Users/name/.context-foundry/patterns/common-issues.json`

```json
{
  "id": "agent-missing-inputparams",
  "issue": "Agent nodes missing inputParams array - nodes cannot be edited in Flowise UI (double-click does nothing)",
  "frequency": 1,
  "severity": "critical",
  "solution": "MUST copy the complete inputParams array from AGENT-NODE-TEMPLATE.json to every agent node...",
  "symptom": "User reports: 'When I double click on Agent.OrderTracking, Agent.Returns, etc., nothing happens. The code is broken somewhere.'",
  "root_cause": "Builder phase copied inputs (DATA) but omitted inputParams (SCHEMA)...",
  "detection": "Double-click agent node in Flowise UI - if nothing happens (no edit dialog), inputParams is missing...",
  "last_seen": "2025-11-02"
}
```

**Total patterns:** 10 (was 9)

### 2. Flowise Extension Documentation

**File:** `extensions/flowise/FAILURE_PATTERNS.md`

**Added:** Pattern #8 - Agent Nodes Missing inputParams

**Sections:**
- Symptom (with exact user quote)
- Root Cause (missing UI schema)
- What is inputParams? (detailed explanation)
- Comparison: Template vs Generated
- Impact (production blocker details)
- Detection (UI and JSON methods)
- Fix Required (15 required inputParams)
- Prevention (checklists)
- Template Reference
- Relationship to Other Patterns
- Quick Fix for Existing Workflows

---

## Prevention Guidelines

**Before generating agent nodes:**
- [ ] Reference AGENT-NODE-TEMPLATE.json for complete structure
- [ ] Copy the ENTIRE inputParams array (15 objects, ~200 lines)
- [ ] Do NOT just copy inputs - MUST include inputParams
- [ ] Verify inputParams array exists in template (line 17+)

**During Builder phase:**
- [ ] For EVERY agent node, include both inputParams AND inputs
- [ ] inputParams = SCHEMA (what fields exist)
- [ ] inputs = DATA (values for those fields)
- [ ] **Both are required** - inputParams is NOT optional

**Post-generation validation:**
```bash
agent_count=$(cat workflow.json | jq '[.nodes[] | select(.data.type == "Agent")] | length')
inputparams_count=$(grep -c '"inputParams"' workflow.json)

if [ "$inputparams_count" -lt "$agent_count" ]; then
  echo "❌ CRITICAL: Some agent nodes missing inputParams"
  echo "Expected: $agent_count, Found: $inputparams_count"
fi
```

---

## Template Reference

**Source:** `extensions/flowise/prompts/AGENT-NODE-TEMPLATE.json`
**Lines:** 17-210 (inputParams array definition)
**Size:** ~200 lines for 15 inputParam objects

**Required inputParams (15 total):**
1. agentModel
2. agentMessages
3. agentTools
4. agentToolsBuiltInOpenAI
5. agentToolsBuiltInAnthropic
6. agentToolsBuiltInGemini
7. agentKnowledgeDocumentStores
8. agentKnowledgeVSEmbeddings
9. agentEnableMemory
10. agentMemoryType
11. agentMemoryWindowSize
12. agentMemoryMaxTokenLimit
13. agentReturnResponseAs
14. agentUpdateState
15. Model configuration

---

## Quick Fix for Broken Workflows

If you have a workflow with missing inputParams:

1. Open `AGENT-NODE-TEMPLATE.json`
2. Copy lines 17-210 (complete inputParams array)
3. For each agent node in your workflow JSON:
   - Add `"inputParams": [...]` before `"inputs": {...}`
   - Paste the copied array
   - Update `id` fields to match your node ID
4. Save and re-import to Flowise

**Note:** This is tedious manual work. Better to fix Context Foundry to generate it correctly.

---

## Lessons Learned

1. **Schema is as important as data** - inputParams is NOT optional
2. **Template compliance is critical** - Must copy ALL parts of template, not just data
3. **Silent failures are dangerous** - Workflow imports successfully but is broken
4. **UI testing is essential** - Must actually double-click nodes to verify editability
5. **Pattern detection works** - User caught this immediately in testing

---

## Next Steps

Context Foundry will now:
1. **Include inputParams in all agent nodes** (not just inputs)
2. **Copy complete template structure** (schema + data)
3. **Validate inputParams existence** before completing build
4. **Prevent this critical bug** in all future Flowise workflows

---

## Related Patterns

- Pattern #4: condition-agent-no-scenarios (no scenarios array)
- Pattern #7: condition-agent-incomplete-scenarios (scenarios incomplete)
- **Pattern #8: agent-missing-inputparams** (no UI schema) ← **THIS ONE**

**Common theme:** Missing or incomplete array structures that define UI schemas

---

## Verification

To verify this pattern is fixed in future builds:

```bash
# Check pattern exists in global library
cat ~/.context-foundry/patterns/common-issues.json | jq '.patterns[] | select(.id == "agent-missing-inputparams")'

# Check documented in Flowise extension
grep -A 20 "Agent Nodes Missing inputParams" extensions/flowise/FAILURE_PATTERNS.md

# Validate generated workflow has inputParams
cat workflow.json | jq '[.nodes[] | select(.data.type == "Agent") | .data | has("inputParams")] | all'
# Should return: true
```

---

**Status:** ✅ Complete - Pattern documented and will prevent future occurrences

**Impact:** This was a CRITICAL production-blocking bug. Workflow appeared to work but was completely unusable. Now documented and future builds will include inputParams.
