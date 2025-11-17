# Root Cause Analysis: Vehicle Parking App Build Failure

**Date**: 2025-11-17
**Issue**: Scout agent built database/app architecture instead of Flowise flow JSON
**Impact**: CRITICAL - Wrong deliverable type, wasted build time

---

## Problem Summary

**Expected Deliverable**: `vehicle-parking-flow.json` (single Flowise workflow JSON file)
**Actual Deliverable**: Full-stack app with database schemas, custom tools, and directories

**Comparison**:

| Aspect | ✅ Correct (conflict-of-interest-flow) | ❌ Wrong (vehicle-parking-app) |
|--------|----------------------------------------|--------------------------------|
| **Main file** | `conflict-of-interest-flow.json` (70KB) | Database schema + custom tools |
| **Structure** | Single JSON with nodes/edges | Multiple directories (database/, custom-tools/, flowise-tool-configs/) |
| **Scout report line 40** | "Platform: Flowise AI (AgentFlow v2)" | "Database/Persistence: External PostgreSQL or MySQL" |
| **Scout report line 78** | "Multi-Agent Orchestration: 10-12 specialized agents" | "Multi-Agent Orchestration: 10-12 specialized agents" ← SAME! |
| **Scout report line 94-106** | NO DATABASE SECTION | FULL DATABASE SCHEMA with 9 tables |
| **Architecture** | Flowise workflow JSON structure | Full-stack app architecture |

---

## Root Cause

### 1. Scout Misinterpreted Task Complexity

**Task description included**:
- "Database schema for vehicles, permits, zones, bookings, waitlists, violations"
- "Workday API integration"
- "File uploads for insurance/license"
- "Email notifications"
- "QR code generation"

**Scout's incorrect interpretation**:
- Saw "database schema" → assumed external PostgreSQL needed
- Saw "API integration" → assumed backend server needed
- Saw "file uploads" → assumed file storage system needed
- **FAILED to recognize**: All of this can be handled via Flowise **custom tools** (HTTP tools calling external services)

**What Scout SHOULD have done**:
- Recognize this as a **Flowise Multi-Agent Workflow**
- Design custom HTTP tools to call external database API
- Design custom HTTP tools for Workday/email/file storage
- Keep ALL logic in Flowise agents
- Deliverable: SINGLE workflow JSON file

### 2. Orchestrator Prompt Weakness

**Current orchestrator prompt (line 573-618) says**:

```
**DO NOT research:**
❌ Database schemas or ORMs
❌ Traditional full-stack application patterns

**ONLY research:**
✅ Flowise node architectures and patterns
✅ Agent specialization and persona design
✅ Tool integration patterns (currentDateTime, searXNG, custom)
```

**BUT** - this guidance is **not strong enough** when the task description EXPLICITLY mentions:
- "Database schema"
- "API endpoints for Workday integration"
- "File upload handling"
- "Email notifications"

The Scout agent sees these requirements and thinks: "I need to build a real database!"

### 3. Missing Distinction: External Services vs Internal Implementation

**Flowise Philosophy**:
- Flowise workflows **orchestrate** external services via HTTP tools
- Flowise workflows **do NOT implement** databases, APIs, file storage
- Those are **external dependencies** called via custom tools

**Example from conflict-of-interest-flow**:
- NO database schema in scout report
- NO mention of PostgreSQL/MySQL
- Simply describes: "8 agent nodes" + "Risk scoring framework" + "Compliance rules"
- External data persistence handled via custom tools (not documented in scout report)

**Example from vehicle-parking-app (WRONG)**:
- Lines 94-106: Full database schema with 9 tables
- Line 107: "File Storage: AWS S3, Azure Blob Storage"
- Line 109: "Email Service: SendGrid, AWS SES"
- **ALL OF THIS SHOULD BE EXTERNAL** - not designed by Scout!

---

## Why Version 2.2.0 Worked

Checking the v2.2.0 orchestrator prompt (commit c70bc45), the Flowise section had **identical** guidance:

```
**DO NOT research:**
❌ Database schemas or ORMs

**ONLY research:**
✅ Tool integration patterns (currentDateTime, searXNG, custom)
```

**Hypothesis**: The conflict-of-interest-flow task description did NOT mention "database schema" explicitly, so Scout naturally focused on Flowise patterns.

**Verification**:
- conflict-of-interest-flow task: Focused on "conflict assessment", "risk scoring", "compliance report"
- vehicle-parking-app task: EXPLICITLY mentioned "database schema", "API endpoints", "file uploads"

**Conclusion**: The orchestrator prompt worked when task descriptions were "Flowise-native" (workflow-focused), but FAILED when task descriptions were "full-stack-like" (infrastructure-focused).

---

## The Fix

### Option 1: Strengthen Orchestrator Prompt (RECOMMENDED)

Add **explicit anti-pattern** detection in Scout phase:

```markdown
🚨 **FLOWISE ANTI-PATTERN DETECTION** 🚨

**IF task description mentions ANY of these keywords:**
- "database schema"
- "PostgreSQL", "MySQL", "MongoDB"
- "API endpoints"
- "backend server"
- "frontend UI"
- "file storage system"
- "authentication system"

**STOP AND REINTERPRET:**

❌ DO NOT design these as internal components
✅ These are EXTERNAL SERVICES called via Flowise custom HTTP tools

**Flowise projects ONLY design**:
1. Agent workflow structure (nodes + edges)
2. Agent personas and prompts
3. Custom HTTP tool configurations (pointing to external services)
4. State management within workflow
5. Routing logic and conditions

**Flowise projects NEVER design**:
1. Database schemas (external service responsibility)
2. API server implementations (external service responsibility)
3. File storage systems (external service responsibility)
4. Email servers (external service responsibility)

**Deliverable**: SINGLE workflow JSON file + README + INTEGRATION_GUIDE

**Example**:
- Task says: "Design database schema for vehicles table"
- ❌ Wrong: Create SQL schema in scout report
- ✅ Correct: Note "Custom HTTP tool needed for vehicle CRUD operations (calls external DB API)"
```

### Option 2: Add Flowise Task Detection in Configuration

Update `tools/mcp_utils/project_detection.py` to detect Flowise keywords in task description:

```python
def detect_flowise_mode(task_description: str) -> tuple[bool, str]:
    """
    Detect if task is a Flowise workflow project.

    Returns:
        (is_flowise, reason)
    """
    flowise_keywords = [
        "flowise flow",
        "flowise workflow",
        "flowise chatflow",
        "flowise agentflow",
        "multi-agent workflow",
        "conversational AI flow"
    ]

    # Check for explicit Flowise mentions
    for keyword in flowise_keywords:
        if keyword.lower() in task_description.lower():
            return (True, f"Task mentions '{keyword}'")

    # Check for database/API mentions WITHOUT Flowise context
    infrastructure_keywords = ["database schema", "API endpoints", "backend server"]
    has_infrastructure = any(k in task_description for k in infrastructure_keywords)
    has_flowise_context = any(k in task_description for k in flowise_keywords)

    if has_infrastructure and not has_flowise_context:
        # Warn: This looks like full-stack but might be Flowise
        return (False, "Task has infrastructure keywords but no Flowise context - may need clarification")

    return (False, "No Flowise indicators found")
```

### Option 3: Add Pre-Scout Clarification Step

Before Scout phase, analyze task and ask user:

```
🤔 **Task Clarification Needed**

Your task mentions:
- Database schema design
- API endpoint implementation
- File upload handling

**Question**: Are you building:
A) A Flowise workflow that CALLS external services for these features?
B) A full-stack application that IMPLEMENTS these features?

If A: I'll create a Flowise workflow JSON with custom HTTP tools.
If B: I'll create a complete application with database, API, and frontend.
```

---

## Recommended Solution

**Implement Option 1** (strengthen orchestrator prompt) because:

1. **No user interruption** - fully autonomous
2. **Clear anti-pattern detection** - prevents future failures
3. **Educational** - teaches Scout to distinguish external vs internal
4. **Backward compatible** - works with existing task descriptions

**Implementation**:

Add new section to orchestrator prompt after line 618:

```markdown
🚨 **FLOWISE ANTI-PATTERN DETECTION** 🚨

IF task description contains infrastructure keywords (database, API, backend, storage, authentication):

**CRITICAL DECISION POINT:**
- These are EXTERNAL SERVICES for Flowise workflows
- NOT components to design/build internally
- Design custom HTTP tools to call these services
- Focus on agent orchestration, NOT service implementation

**Deliverable Check:**
- ✅ Expected: workflow-name.json (single file)
- ❌ Wrong: database/, backend/, api/, src/ directories
```

---

## Testing the Fix

**Test Case 1**: Rebuild vehicle-parking-flow with fixed prompt
- **Expected**: Single `vehicle-parking-flow.json` file
- **Expected**: Scout report mentions "Custom HTTP tools for database, Workday API, email, file storage"
- **Expected**: NO database schema in scout report

**Test Case 2**: Run conflict-of-interest-flow with current prompt (regression test)
- **Expected**: Same behavior as before (already works correctly)

**Test Case 3**: Create new complex Flowise task with infrastructure keywords
- **Task**: "Build a Flowise workflow for employee onboarding with database for user profiles, API integration with HRIS, email notifications, and document storage"
- **Expected**: Scout recognizes all as external services, creates workflow JSON only

---

## Lessons Learned

1. **Explicit is better than implicit**: When task mentions infrastructure, Scout needs explicit "these are external" guidance
2. **Anti-pattern detection needed**: Add checks for common misinterpretations
3. **Deliverable validation**: Scout should state expected deliverable (e.g., "single workflow JSON")
4. **Task description matters**: Flowise-focused descriptions work better than full-stack descriptions

---

## Next Steps

1. ✅ Document root cause (this file)
2. ⏳ Update orchestrator prompt with anti-pattern detection
3. ⏳ Test fix with vehicle-parking-flow rebuild
4. ⏳ Update Flowise extension documentation
5. ⏳ Add this pattern to FAILURE_PATTERNS.md
