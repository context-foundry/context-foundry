# Pattern Library Update - ConditionAgent Incomplete Scenarios

**Date:** 2025-11-02
**Pattern ID:** `condition-agent-incomplete-scenarios`
**Severity:** CRITICAL
**Status:** Added to global pattern library + Flowise documentation

---

## Issue Discovered

**User Report:**
> "The node 'Detect User Intention' is not populated - all scenarios 0-7 show blank Model, Instructions, and Input fields in Flowise UI"

**Source:** E-commerce Customer Support Workflow build
**File:** `/Users/name/homelab/ecommerce-support-workflow/ecommerce-support-flow.json`

---

## Root Cause

The generated ConditionAgent had **incomplete scenario objects**:

### WRONG (Generated):
```json
"conditionAgentScenarios": [
  {"scenario": "Order status, tracking, delivery questions"},
  {"scenario": "Returns, refunds, RMA, exchanges"},
  ...
]
```

### CORRECT (Required):
```json
"conditionAgentScenarios": [
  {
    "scenario": "Order status, tracking, delivery questions",
    "model": "chatOpenAI",
    "instructions": "Route to Order Tracking when user asks about: order status, tracking number, delivery estimates...",
    "input": "{{question}}"
  },
  {
    "scenario": "Returns, refunds, RMA, exchanges",
    "model": "chatOpenAI",
    "instructions": "Route to Returns when user asks about: return policy, refund status, RMA processing...",
    "input": "{{question}}"
  }
]
```

## Impact

- ❌ All 8 scenarios show blank in Flowise UI (Model, Instructions, Input)
- ❌ Router cannot function without scenario configuration
- ❌ Requires manual configuration of 8+ scenarios by user
- ❌ Production blocker - workflow unusable until fixed
- ❌ User confusion: main ConditionAgent fields work, but scenarios don't

---

## Pattern Added To

### 1. Global Pattern Library

**File:** `/Users/name/.context-foundry/patterns/common-issues.json`

```json
{
  "id": "condition-agent-incomplete-scenarios",
  "issue": "ConditionAgent scenarios array contains only scenario descriptions, missing model, instructions, and input fields for each scenario",
  "frequency": 1,
  "severity": "critical",
  "solution": "Each scenario must be a complete object with: {\"scenario\": \"description\", \"model\": \"chatOpenAI\", \"instructions\": \"routing logic\", \"input\": \"{{question}}\"}. The model field MUST match the parent conditionAgentModel. All 8 scenario objects showed blank fields in Flowise UI because model/instructions/input were missing.",
  "incorrect_structure": "{\"scenario\": \"Order tracking\"}",
  "correct_structure": "{\"scenario\": \"Order tracking\", \"model\": \"chatOpenAI\", \"instructions\": \"Route when keywords: order status, tracking, WISMO\", \"input\": \"{{question}}\"}",
  "project_types": [
    "flowise-agents",
    "routing-workflows",
    "multi-agent-systems"
  ],
  "detection": "Open ConditionAgent node in Flowise UI - if scenario 0-7 show blank Model/Instructions/Input fields, this pattern was violated",
  "impact": "Router cannot function - all scenarios appear blank in UI, requiring manual configuration of 8+ scenarios",
  "last_seen": "2025-11-02"
}
```

### 2. Flowise Extension Documentation

**File:** `extensions/flowise/FAILURE_PATTERNS.md`

**Added:** Pattern #7 - ConditionAgent Incomplete Scenarios

**Sections:**
- Symptom (with user report quote)
- Root Cause (incorrect array structure)
- Impact (UI blank fields, manual work required)
- Fix Required (complete scenario object template)
- Prevention (checklists for before/during/after build)
- Template (copy-paste ready examples)
- Detection in Code Review (automated + manual checks)
- Related Patterns (links to Pattern #4)

---

## Prevention Guidelines

**Before generating ConditionAgent:**
- [ ] Check AGENT_PATTERN_REFERENCE.md Section 2.2 for complete scenario structure
- [ ] Each scenario is a FULL object with 4 fields: scenario, model, instructions, input
- [ ] Model field matches parent conditionAgentModel exactly
- [ ] Instructions include keywords, exceptions, and routing rules
- [ ] Input field is `"{{question}}"` or appropriate variable

**During Builder phase:**
- [ ] Generate complete scenario objects, not just descriptions
- [ ] Copy model from parent conditionAgentModel to each scenario
- [ ] Write detailed routing instructions for each scenario
- [ ] Include exception handling in instructions

**Test in Flowise UI:**
- [ ] Open ConditionAgent node after import
- [ ] Verify each scenario (0, 1, 2...) shows populated Model/Instructions/Input
- [ ] If ANY scenario shows blank fields → PATTERN VIOLATED

---

## Files Updated

1. ✅ `/Users/name/.context-foundry/patterns/common-issues.json`
   - Added pattern #9 (total now: 9 patterns)
   - Updated total_builds: 2
   - Updated timestamp: 2025-11-02

2. ✅ `extensions/flowise/FAILURE_PATTERNS.md`
   - Added Pattern #7 with comprehensive documentation
   - Updated table of contents
   - Added templates and examples
   - Added prevention checklists

---

## Next Steps for Future Builds

Context Foundry will now:

1. **Learn from this pattern** when generating ConditionAgent nodes
2. **Check scenario completeness** during JSON generation
3. **Include model/instructions/input** for EVERY scenario object
4. **Avoid this critical bug** in all future Flowise multi-agent builds

---

## Verification

To verify pattern is applied in future builds:

```bash
# Check if pattern exists in global library
cat ~/.context-foundry/patterns/common-issues.json | jq '.patterns[] | select(.id == "condition-agent-incomplete-scenarios")'

# Check if documented in Flowise extension
grep -A 10 "ConditionAgent Incomplete Scenarios" extensions/flowise/FAILURE_PATTERNS.md
```

---

## Related Issues

- **Pattern #4:** condition-agent-no-scenarios (no scenarios at all)
- **Pattern #7:** condition-agent-incomplete-scenarios (scenarios exist but incomplete) ← **THIS ONE**

---

**Status:** ✅ Complete - Pattern successfully added to library and will prevent future occurrences
