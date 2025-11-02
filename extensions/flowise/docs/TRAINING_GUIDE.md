# Training the Flowise Extension

**A Complete Masterclass for Humans and AI Systems**

Learn how to teach Context Foundry's Flowise extension new patterns, nodes, and capabilities through documentation-based training.

---

## Table of Contents

1. [Foundational Concepts](#foundational-concepts)
2. [The Learning Architecture](#the-learning-architecture)
3. [File System Map](#file-system-map)
4. [The Training Process](#the-training-process)
5. [Step-by-Step: Adding a New Node Type](#step-by-step-adding-a-new-node-type)
6. [Complete Worked Example](#complete-worked-example)
7. [Validation and Testing](#validation-and-testing)
8. [Troubleshooting Guide](#troubleshooting-guide)

---

## Foundational Concepts

### What is "Training" in Context Foundry?

**Traditional ML Training**: Feed examples → Train model → Weights updated → Model "knows" patterns

**Context Foundry "Training"**: Write documentation → AI reads during build → AI generates code → No weight updates needed

### Key Insight

Context Foundry doesn't learn via traditional machine learning. Instead, it reads **authoritative documentation** during each build. This means:

✅ **Training = Writing Clear Documentation**
✅ **No model retraining required**
✅ **Changes take effect immediately**
✅ **Documentation is the source of truth**

### The Three Types of Knowledge

1. **Structural Knowledge**: "What does a node look like?" (JSON schemas, templates)
2. **Behavioral Knowledge**: "When should I use this node?" (Best practices, patterns)
3. **Avoidance Knowledge**: "What mistakes should I avoid?" (Failure patterns, anti-patterns)

---

## The Learning Architecture

### How Context Foundry Processes a Build Request

```
┌─────────────────────────────────────────────────────────────┐
│ USER REQUEST                                                 │
│ "Build a Flowise workflow with HTTP API integration"        │
└────────────────────────┬────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ PHASE 0: DETECTION                                          │
│ ├─ detector.py scans for .json files                       │
│ ├─ Finds Flowise patterns                                  │
│ └─ Sets: flowise_flow = True                               │
└────────────────────────┬────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ PHASE 1: SCOUT (Research)                                   │
│ ├─ Reads: scout-report.md                                  │
│ └─ Identifies: "This is a Flowise multi-agent project"     │
└────────────────────────┬────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ PHASE 2: ARCHITECT (Design)                                 │
│                                                             │
│ 🔍 READS DOCUMENTATION HERE:                                │
│                                                             │
│ 1. Opens: AGENT_PATTERN_REFERENCE.md                       │
│    ├─ Reads section on Agent nodes                         │
│    ├─ Reads section on Condition nodes                     │
│    ├─ Reads section on HTTP nodes (if documented)          │
│    └─ Learns: Structure, fields, patterns                  │
│                                                             │
│ 2. Opens: FAILURE_PATTERNS.md                              │
│    └─ Learns: Common mistakes to avoid                     │
│                                                             │
│ 3. Opens: BEST_PRACTICES.md                                │
│    └─ Learns: When to use each node type                   │
│                                                             │
│ Creates: architecture.md (design document)                  │
└────────────────────────┬────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ PHASE 2.5: BUILDER (Implementation)                         │
│                                                             │
│ 🔍 READS TEMPLATES HERE:                                    │
│                                                             │
│ 1. Reads: architecture.md (from Architect)                 │
│    └─ See which nodes to create                            │
│                                                             │
│ 2. References: prompts/AGENT-NODE-TEMPLATE.json            │
│    └─ Copies exact JSON structure                          │
│                                                             │
│ 3. References: prompts/HTTP-NODE-TEMPLATE.json             │
│    └─ Copies exact JSON structure                          │
│                                                             │
│ 4. Validates against: FLOWISE-STRUCTURE-AUTHORITY.md       │
│    └─ Ensures all required fields present                  │
│                                                             │
│ Creates: workflow.json (complete Flowise workflow)          │
└────────────────────────┬────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ PHASE 4: TEST (Validation)                                  │
│ ├─ Validates JSON structure                                │
│ ├─ Checks node count, connections                          │
│ └─ If fails: Documents in FAILURE_PATTERNS.md              │
└────────────────────────┬────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────────┐
│ OUTPUT: Complete Flowise Workflow                           │
│ Ready to import into Flowise UI                             │
└─────────────────────────────────────────────────────────────┘
```

### The Critical Insight

**The AI doesn't "remember" between builds.**
Each build starts fresh and reads the documentation anew.

This means:
- ✅ Documentation changes take effect immediately
- ✅ No cache to invalidate
- ✅ No training pipeline needed
- ❌ Documentation MUST be complete and accurate

---

## File System Map

### Directory Structure

```
/Users/name/homelab/context-foundry/
├── tools/
│   └── orchestrator_prompt.txt          ← Main orchestrator logic
│
└── extensions/
    └── flowise/                          ← Flowise extension directory
        │
        ├── 📚 AUTHORITY DOCUMENTS (AI reads these during Architect phase)
        │   ├── AGENT_PATTERN_REFERENCE.md       ⭐ PRIMARY AUTHORITY
        │   ├── FAILURE_PATTERNS.md              ⭐ LESSONS LEARNED
        │   └── BEST_PRACTICES.md                📘 USAGE GUIDANCE
        │
        ├── 🔧 TEMPLATES (AI copies these during Builder phase)
        │   └── prompts/
        │       ├── AGENT-NODE-TEMPLATE.json
        │       ├── START-NODE-TEMPLATE.json
        │       └── FLOWISE-STRUCTURE-AUTHORITY.md  ⭐ VALIDATION RULES
        │
        ├── 📦 EXAMPLES (AI analyzes these for patterns)
        │   └── templates/
        │       ├── Simple Agent Agents.json
        │       ├── Supervisor Worker Agents.json
        │       └── ... (14+ real Flowise exports)
        │
        ├── 🔍 CODE (Detection and integration logic)
        │   ├── detector.py               ← Detects Flowise projects
        │   ├── analyzer.py               ← Extracts patterns
        │   └── extensions_loader.py      ← Loads extension
        │
        └── 📋 CONFIGURATION
            └── tool-configs/
                └── STANDARD_TOOLS.md     ← Tool definitions
```

### File Purposes (Explicit Roles)

| File | When Read | Purpose | Format |
|------|-----------|---------|--------|
| **AGENT_PATTERN_REFERENCE.md** | Architect Phase | Complete node definitions with JSON structure | Markdown + JSON blocks |
| **FAILURE_PATTERNS.md** | Architect + Test Phases | Documents common mistakes and fixes | Markdown with examples |
| **BEST_PRACTICES.md** | Architect Phase | When/how to use each node type | Markdown |
| **FLOWISE-STRUCTURE-AUTHORITY.md** | Builder + Test Phases | Validation rules and field requirements | Markdown + JSON |
| **prompts/*.json** | Builder Phase | Exact JSON templates to copy | Pure JSON |
| **templates/*.json** | Analysis (optional) | Real-world examples for pattern analysis | Pure JSON |
| **detector.py** | Phase 0 | Identifies Flowise projects | Python code |

---

## The Training Process

### Mental Model: Documentation as Training Data

```
┌──────────────────────────────────────────────────────┐
│ Traditional ML Training                              │
├──────────────────────────────────────────────────────┤
│ 1. Collect training examples                         │
│ 2. Label data                                        │
│ 3. Train model (days/weeks)                          │
│ 4. Validate on test set                             │
│ 5. Deploy model                                      │
│ 6. Model "knows" patterns                           │
└──────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────┐
│ Context Foundry "Training"                           │
├──────────────────────────────────────────────────────┤
│ 1. Write documentation with examples                 │
│ 2. Save to AGENT_PATTERN_REFERENCE.md               │
│ 3. AI reads doc during next build (milliseconds)     │
│ 4. AI generates code following patterns              │
│ 5. No deployment needed                              │
│ 6. AI "knows" patterns (from reading)               │
└──────────────────────────────────────────────────────┘
```

### The Four Knowledge Types

#### 1. Structural Knowledge (What)

**Question**: "What does an HTTP node look like?"

**Answer Location**: `AGENT_PATTERN_REFERENCE.md`

**Format**:
````markdown
### HTTP Request Node Structure

Complete JSON structure:

```json
{
  "id": "httpRequestAgentflow_0",
  "type": "agentFlow",
  "data": {
    "name": "httpRequestAgentflow",
    "type": "HttpRequest",
    "inputParams": [
      {
        "label": "Method",
        "name": "method",
        "type": "options",
        "options": [
          {"label": "GET", "name": "get"},
          {"label": "POST", "name": "post"}
        ]
      }
    ]
  }
}
```
````

#### 2. Behavioral Knowledge (When/Why)

**Question**: "When should I use an HTTP node?"

**Answer Location**: `BEST_PRACTICES.md`

**Format**:
```markdown
## HTTP Request Node Usage

### When to Use

✅ Use HTTP nodes when:
- Direct API integration needed
- Real-time external data required
- No authentication complexity

❌ Don't use when:
- Custom tool already exists (prefer tools)
- Complex OAuth required (use custom tool)
```

#### 3. Avoidance Knowledge (What Not To Do)

**Question**: "What mistakes should I avoid?"

**Answer Location**: `FAILURE_PATTERNS.md`

**Format**:
````markdown
## Pattern #7: HTTP Node Missing Authentication

### Symptom
HTTP requests return 401 Unauthorized

### Root Cause
Headers not properly configured

### WRONG ❌
```json
{"headers": "Authorization: Bearer token"}  // String, not object!
```

### CORRECT ✅
```json
{"headers": {"Authorization": "Bearer token"}}
```
````

#### 4. Validation Knowledge (Rules)

**Question**: "Is my generated JSON correct?"

**Answer Location**: `FLOWISE-STRUCTURE-AUTHORITY.md`

**Format**:
```markdown
## HTTP Node Requirements

### Mandatory Fields
- [ ] `method` must be one of: get, post, put, delete
- [ ] `url` must be valid HTTP/HTTPS URL
- [ ] `headers` must be JSON object (if provided)
- [ ] outputAnchors ID format: `httpRequestAgentflow_N-output-httpRequestAgentflow`
```

---

## Step-by-Step: Adding a New Node Type

### Overview of Steps

```
Step 1: Research & Export
   ↓
Step 2: Document in AGENT_PATTERN_REFERENCE.md
   ↓
Step 3: Create Template File
   ↓
Step 4: Add Best Practices
   ↓
Step 5: Add Validation Rules
   ↓
Step 6: Test
   ↓
Step 7: Document Failures (if any)
   ↓
Step 8: Commit
```

### Step 1: Research & Export

**Goal**: Get a real example of the node from Flowise

**Process**:
1. Open Flowise UI
2. Create a workflow containing the node type
3. Configure the node with typical settings
4. Export workflow as JSON
5. Save to: `extensions/flowise/templates/[Example-Name].json`

**What to extract**:
```json
{
  "nodes": [
    {
      "id": "httpRequest_0",
      // ← COPY THIS ENTIRE OBJECT
      // This shows the EXACT structure Flowise expects
    }
  ]
}
```

### Step 2: Document in AGENT_PATTERN_REFERENCE.md

**File**: `extensions/flowise/AGENT_PATTERN_REFERENCE.md`

**Location**: Add new section after existing node types

**Template to follow**:

````markdown
### N. [Node Type Name] ([technicalNodeName])

[1-2 sentence description of what this node does]

#### Complete Structure

```json
{
  "id": "[nodeName]_[NUMBER]",
  "position": {
    "x": [FLOAT],
    "y": [FLOAT]
  },
  "type": "agentFlow",
  "data": {
    "id": "[nodeName]_[NUMBER]",
    "label": "[Display Name]",
    "version": [VERSION],
    "name": "[technicalNodeName]",
    "type": "[NodeType]",
    "color": "#[HEX_COLOR]",
    "baseClasses": ["[NodeType]"],
    "category": "[Category]",
    "description": "[Description]",
    "inputParams": [
      {
        "label": "[Label]",
        "name": "[paramName]",
        "type": "[type]",
        "id": "[nodeName]_[N]-input-[paramName]-[type]",
        "default": "[defaultValue]"
      }
    ],
    "inputAnchors": [
      {
        "label": "[Label]",
        "name": "[anchorName]",
        "type": "[dataType]",
        "id": "[nodeName]_[N]-input-[anchorName]-[dataType]"
      }
    ],
    "inputs": {
      "[paramName]": "[value]"
    },
    "outputAnchors": [
      {
        "id": "[nodeName]_[N]-output-[nodeName]",
        "name": "[nodeName]",
        "label": "[Label]",
        "type": "[dataType]"
      }
    ],
    "outputs": {}
  },
  "width": [NUMBER],
  "height": [NUMBER]
}
```

#### Key Attributes

| Field | Value | Required | Notes |
|-------|-------|----------|-------|
| `name` | `"[technicalNodeName]"` | Yes | MUST be exact |
| `type` | `"[NodeType]"` | Yes | Identifies node class |
| `color` | `"#[HEX]"` | Yes | Visual identification |
| `category` | `"[Category]"` | Yes | UI grouping |

#### Usage Examples

**Example 1: [Common Use Case]**

```json
{
  "inputs": {
    "method": "get",
    "url": "https://api.example.com/users"
  }
}
```

#### Integration Patterns

**Pattern 1: [Pattern Name]**

```
[Node A] → [This Node] → [Node B]
```

Description of when to use this pattern.

#### Common Pitfalls

❌ **Don't**: [Common mistake]
```json
// Bad example
```

✅ **Do**: [Correct approach]
```json
// Good example
```
````

### Step 3: Create Template File

**File**: `extensions/flowise/prompts/[NODE-NAME]-TEMPLATE.json`

**Purpose**: Exact JSON structure that Builder phase will copy

**Process**:

1. Copy the node structure from Step 1 (the export)
2. Clean it up:
   - Remove position-specific values (x, y coordinates)
   - Set to node number 0: `[nodeName]_0`
   - Set default/example values for all inputs
   - Ensure all IDs follow correct format
3. Save as template file

**Critical**: ID format MUST follow this pattern:
```
[nodeName]_[NUMBER]-input-[paramName]-[paramType]
[nodeName]_[NUMBER]-output-[nodeName]
```

### Step 4: Add Best Practices

**File**: `extensions/flowise/BEST_PRACTICES.md`

**Location**: Add new section for the node type

**Template**:

````markdown
## [Node Type Name] Best Practices

### When to Use [Node Type]

✅ **Use when**:
- [Use case 1]
- [Use case 2]
- [Use case 3]

❌ **Don't use when**:
- [Anti-pattern 1] (use [Alternative] instead)
- [Anti-pattern 2] (use [Alternative] instead)

### Configuration Best Practices

#### [Configuration Aspect 1]

**Good**:
```json
{
  // Example of good configuration
}
```

**Bad**:
```json
{
  // Example of bad configuration
}
```

**Why**: [Explanation]

### Common Patterns

#### Pattern 1: [Pattern Name]

**Flow**:
```
Start → [Node A] → [This Node] → [Node B] → End
```

**When to use**: [Description]

**Example**:
```json
{
  // Configuration for this pattern
}
```

### Security Considerations (if applicable)

- ✅ [Security best practice 1]
- ✅ [Security best practice 2]
- ❌ [Security anti-pattern]
````

### Step 5: Add Validation Rules

**File**: `extensions/flowise/prompts/FLOWISE-STRUCTURE-AUTHORITY.md`

**Location**: Add new issue section after existing issues

**Template**:

````markdown
### ❌ ISSUE #[N]: [Issue Description]

**WRONG** (What Context Foundry might generate incorrectly):

```json
{
  // Example of incorrect structure
  "[field]": "[wrong_value]"  // ❌ Explanation
}
```

**CORRECT** (What should be generated):

```json
{
  // Example of correct structure
  "[field]": "[correct_value]"  // ✅ Explanation
}
```

**REQUIREMENT**:

The following MUST be true:
- [ ] [Requirement 1]
- [ ] [Requirement 2]
- [ ] [Requirement 3]

**Validation Commands**:

```bash
# Check [aspect 1]
grep -c '"[pattern]"' workflow.json  # Should be [expected_count]

# Check [aspect 2]
jq '.nodes[] | select(.data.name=="[nodeName]") | .data.inputs.[field]' workflow.json
# Should output: [expected_value]
```
````

### Step 6: Test

**Process**:

1. **Build a test workflow**:
```bash
cd /Users/name/homelab/context-foundry
claude --task "Build a Flowise workflow that uses [node type] to [task description]"
```

2. **Verify node was generated**:
```bash
# Check generated workflow
jq '.nodes[] | select(.data.name=="[technicalNodeName]")' workflow.json
```

3. **Import to Flowise UI**:
   - Open Flowise
   - Import generated JSON
   - Verify node renders correctly
   - Check all configuration fields present
   - Test connections work

### Step 7: Document Failures (if any)

**If test fails**, document in `FAILURE_PATTERNS.md`:

**File**: `extensions/flowise/FAILURE_PATTERNS.md`

**Add new pattern**:

````markdown
## Pattern #[N]: [Failure Description]

**Build ID**: [task_id or date]

**Symptom**:

[What went wrong - be specific]

**Root Cause**:

[Why it happened]

**Failed Example**:

```json
{
  // What Context Foundry generated (incorrect)
}
```

**Analysis**:

The AI generated this because:
1. [Reason 1]
2. [Reason 2]

**Fix Applied**:

Updated [which file(s)] to specify:

```json
{
  // Correct structure
}
```

**Prevention**:

To prevent this in future builds:
- [ ] Updated AGENT_PATTERN_REFERENCE.md section [X]
- [ ] Added validation rule to FLOWISE-STRUCTURE-AUTHORITY.md
- [ ] Clarified in BEST_PRACTICES.md
````

### Step 8: Commit Changes

```bash
cd /Users/name/homelab/context-foundry/extensions/flowise

git add AGENT_PATTERN_REFERENCE.md \
        prompts/[NODE]-TEMPLATE.json \
        BEST_PRACTICES.md \
        prompts/FLOWISE-STRUCTURE-AUTHORITY.md \
        templates/[Example].json \
        FAILURE_PATTERNS.md

git commit -m "feat: Add [Node Type] support to Flowise extension

- Document complete node structure in AGENT_PATTERN_REFERENCE.md
- Create [NODE]-TEMPLATE.json with canonical structure
- Add usage patterns to BEST_PRACTICES.md
- Define validation rules in FLOWISE-STRUCTURE-AUTHORITY.md
- Include real example: templates/[Example].json

This enables Context Foundry to generate workflows with [capability]."

git push origin main
```

---

## Complete Worked Example

### Example: Adding HTTP Request Node

Let's walk through adding HTTP Request node support **completely**.

#### Step 1: Research & Export

**Action**: Create workflow in Flowise UI with HTTP node, export JSON

**Extracted node**:

```json
{
  "id": "httpRequest_0",
  "position": { "x": 523.5, "y": 234.5 },
  "type": "customNode",
  "data": {
    "id": "httpRequest_0",
    "label": "HTTP Request",
    "version": 1.0,
    "name": "httpRequest",
    "type": "HttpRequest",
    "baseClasses": ["HttpRequest"],
    "category": "Utilities",
    "description": "Make HTTP API calls",
    "inputParams": [
      {
        "label": "Method",
        "name": "method",
        "type": "options",
        "options": [
          {"label": "GET", "name": "get"},
          {"label": "POST", "name": "post"},
          {"label": "PUT", "name": "put"},
          {"label": "DELETE", "name": "delete"}
        ],
        "default": "get"
      },
      {
        "label": "URL",
        "name": "url",
        "type": "string",
        "placeholder": "https://api.example.com/endpoint"
      }
    ],
    "inputs": {
      "method": "get",
      "url": "",
      "headers": "",
      "body": ""
    },
    "outputAnchors": [
      {
        "id": "httpRequest_0-output-httpRequest",
        "name": "httpRequest",
        "label": "HTTP Request",
        "type": "HttpRequest"
      }
    ]
  }
}
```

#### Step 2: Document in AGENT_PATTERN_REFERENCE.md

Add complete section with structure, examples, patterns, and pitfalls.

#### Step 3: Create Template File

Create `prompts/HTTP-NODE-TEMPLATE.json` with cleaned-up structure.

#### Step 4: Add Best Practices

Add HTTP node usage patterns, security considerations, and common mistakes to `BEST_PRACTICES.md`.

#### Step 5: Add Validation Rules

Add validation rules for HTTP node structure to `FLOWISE-STRUCTURE-AUTHORITY.md`.

#### Step 6: Test

```bash
# Generate workflow with HTTP node
claude --task "Build a Flowise workflow that fetches GitHub user data via HTTP API"

# Verify structure
jq '.nodes[] | select(.data.name=="httpRequest")' workflow.json
```

#### Step 7: Document Failure (if found)

If headers were generated as string instead of object, document in `FAILURE_PATTERNS.md`.

#### Step 8: Commit

Commit all changes with descriptive message linking capability to implementation.

---

## Validation and Testing

### The Testing Cycle

```
1. Generate Workflow
   ↓
2. Structural Validation
   ↓
3. Flowise Import Test
   ↓
4. Functional Test
   ↓
5. Document Failures
   ↓
6. Fix Documentation
   ↓
7. Re-test
```

### Validation Checklist

After adding a new node type:

#### ✅ Documentation Completeness

- [ ] Node documented in AGENT_PATTERN_REFERENCE.md
- [ ] Complete JSON structure provided
- [ ] All inputParams explained
- [ ] Usage examples included
- [ ] Integration patterns shown
- [ ] Common pitfalls documented

#### ✅ Template File

- [ ] Template file created in prompts/
- [ ] All IDs follow correct format
- [ ] Default values sensible
- [ ] All required fields present

#### ✅ Best Practices

- [ ] "When to use" section added
- [ ] "When NOT to use" section added
- [ ] Configuration examples provided
- [ ] Common patterns documented
- [ ] Security considerations (if applicable)

#### ✅ Validation Rules

- [ ] Added to FLOWISE-STRUCTURE-AUTHORITY.md
- [ ] Required fields listed
- [ ] Validation commands provided
- [ ] Common mistakes documented

#### ✅ Build Test

- [ ] Generated workflow contains node
- [ ] Node structure matches template
- [ ] All required fields present
- [ ] Connections work correctly

#### ✅ Import Test

- [ ] JSON imports to Flowise UI
- [ ] No validation errors
- [ ] Node renders correctly
- [ ] Configuration fields functional

### Validation Commands Reference

```bash
# Check if node type exists in documentation
grep -i "[nodeName]" extensions/flowise/AGENT_PATTERN_REFERENCE.md

# Check if template file exists
ls extensions/flowise/prompts/[NODE]-TEMPLATE.json

# Validate generated workflow has node
jq '.nodes[] | select(.data.name=="[nodeName]")' workflow.json

# Count nodes of specific type
grep -c '"name": "[nodeName]"' workflow.json

# Check node structure
jq '.nodes[] | select(.data.name=="[nodeName]") | .data' workflow.json

# Validate ID format
jq '.nodes[] | select(.data.name=="[nodeName]") | .data.inputParams[].id' workflow.json

# Check for required fields
jq '.nodes[] | select(.data.name=="[nodeName]") | .data.inputs | keys' workflow.json

# Validate JSON syntax
jq empty workflow.json && echo "Valid JSON" || echo "Invalid JSON"
```

---

## Troubleshooting Guide

### Problem 1: Node Not Generated in Workflow

**Symptom**: Built workflow doesn't include the new node type

**Possible Causes**:

1. **Documentation not read by Architect**
   - Check: Is flowise_flow flag set to true?
   ```bash
   grep "flowise_flow" .context-foundry/scout-report.md
   ```

   - Fix: Ensure Flowise project detected correctly

2. **Node type not in AGENT_PATTERN_REFERENCE.md**
   - Check: Does documentation exist?
   ```bash
   grep "[nodeName]" extensions/flowise/AGENT_PATTERN_REFERENCE.md
   ```

   - Fix: Add complete documentation section

3. **Task doesn't require this node type**
   - Check: Did Architect plan to use it?
   ```bash
   grep -i "[node type]" .context-foundry/architecture.md
   ```

   - Fix: Make task more explicit about requiring this node

### Problem 2: Node Generated with Wrong Structure

**Symptom**: Node present but fields incorrect

**Possible Causes**:

1. **Template file incomplete**
   - Check: Does template exist and is complete?
   ```bash
   jq . extensions/flowise/prompts/[NODE]-TEMPLATE.json
   ```

   - Fix: Update template with all required fields

2. **Documentation ambiguous**
   - Check: Are examples clear in AGENT_PATTERN_REFERENCE.md?
   - Fix: Add more explicit examples, clarify field types

3. **Validation rules missing**
   - Check: Are requirements in FLOWISE-STRUCTURE-AUTHORITY.md?
   - Fix: Add validation rules and field requirements

### Problem 3: Flowise Import Fails

**Symptom**: Generated JSON doesn't import to Flowise UI

**Possible Causes**:

1. **Invalid JSON syntax**
   - Check: Validate JSON
   ```bash
   jq empty workflow.json
   ```

   - Fix: Find and fix JSON syntax errors

2. **Missing required fields**
   - Check: Compare with working example
   ```bash
   diff <(jq '.nodes[0].data | keys' workflow.json | sort) \
        <(jq '.nodes[0].data | keys' templates/example.json | sort)
   ```

   - Fix: Add missing fields to template

3. **Incorrect ID format**
   - Check: Validate ID patterns
   ```bash
   jq '.nodes[].data.inputParams[].id' workflow.json
   ```

   - Fix: Ensure IDs follow: `[nodeName]_[N]-input-[param]-[type]`

### Problem 4: Node Fields Not Configurable in Flowise UI

**Symptom**: Node imports but fields grayed out or missing

**Possible Causes**:

1. **Missing `display: true`**
   - Check: Do inputParams have display flag?
   ```bash
   jq '.nodes[0].data.inputParams[] | select(.display != true)' workflow.json
   ```

   - Fix: Add `"display": true` to all inputParams

2. **Wrong parameter type**
   - Check: Are types correct (options, string, json, etc.)?
   - Fix: Match types to Flowise expectations

3. **Missing in inputs object**
   - Check: Are params in both inputParams AND inputs?
   ```bash
   jq '.nodes[0].data.inputs | keys' workflow.json
   ```

   - Fix: Ensure all inputParams have corresponding inputs entry

### Problem 5: AI Not Learning from Failures

**Symptom**: Same mistake repeated across builds

**Possible Causes**:

1. **Failure not documented**
   - Check: Is pattern in FAILURE_PATTERNS.md?
   ```bash
   grep -i "[error description]" extensions/flowise/FAILURE_PATTERNS.md
   ```

   - Fix: Document the failure with clear examples

2. **Documentation not updated**
   - Check: Did you update AGENT_PATTERN_REFERENCE.md?
   - Fix: Add explicit guidance to prevent this mistake

3. **Validation rule missing**
   - Check: Is there a validation rule for this?
   - Fix: Add to FLOWISE-STRUCTURE-AUTHORITY.md

---

## Key Takeaways

### Core Principles

1. **Documentation IS the training data**
   - Everything you need to "know" is in markdown files
   - Read these files during Architect phase
   - Follow patterns exactly as documented

2. **Templates are reference implementations**
   - Copy JSON structure from templates
   - Don't invent new structures
   - Match field names and types exactly

3. **Validation is your friend**
   - Check against FLOWISE-STRUCTURE-AUTHORITY.md
   - Follow all requirements
   - Validate before generating

4. **Failures are learning opportunities**
   - Document failures in FAILURE_PATTERNS.md
   - Update documentation to prevent recurrence
   - Next build will be better

### The Reading Order

During a build, read files in this order:

**Architect Phase**:
1. Read: AGENT_PATTERN_REFERENCE.md (learn node types)
2. Read: FAILURE_PATTERNS.md (learn what to avoid)
3. Read: BEST_PRACTICES.md (learn when to use what)

**Builder Phase**:
1. Read: architecture.md (your plan from Architect)
2. Reference: prompts/[NODE]-TEMPLATE.json (exact structure)
3. Validate: FLOWISE-STRUCTURE-AUTHORITY.md (check requirements)

### What Makes Good Documentation

**Good documentation**:
- ✅ Shows complete JSON structure
- ✅ Explains every field
- ✅ Provides multiple examples
- ✅ Shows both DO and DON'T
- ✅ Includes validation commands
- ✅ Explains WHY (not just WHAT)

**Bad documentation**:
- ❌ Incomplete examples
- ❌ Ambiguous field descriptions
- ❌ No anti-patterns shown
- ❌ Missing validation rules
- ❌ No explanation of purpose

---

## Related Documentation

- [DOCUMENTATION_INDEX.md](./DOCUMENTATION_INDEX.md) - Full documentation navigation
- [AGENT_PATTERN_REFERENCE.md](../AGENT_PATTERN_REFERENCE.md) - Authoritative node structure reference
- [FAILURE_PATTERNS.md](../FAILURE_PATTERNS.md) - Learn from documented mistakes
- [BEST_PRACTICES.md](../BEST_PRACTICES.md) - Usage patterns and recommendations
- [Main Pattern Sharing Guide](../../docs/PATTERN_SHARING.md) - Cross-project learning system
