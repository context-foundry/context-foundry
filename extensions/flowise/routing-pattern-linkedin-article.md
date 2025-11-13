# Smart Routing: The Conditional Branching Pattern in Flowise

---

Picture an emergency room triage nurse. A patient arrives. In 30 seconds, the nurse assesses severity:

- Chest pain? → Code Red, immediate cardiac care
- Broken finger? → Urgent care, 15-minute wait
- Flu symptoms? → General examination room

The nurse doesn't send every patient through every department. That would be chaos.

One assessment. One path. The right specialist at the right time.

That's the Routing pattern.

## Why Routing Matters When Parallel Wastes Resources

Last week, we explored the Parallel pattern—running independent tasks simultaneously to maximize speed.

But what about when you **shouldn't** run all branches?

- Classifying customer intent (support vs. sales vs. billing)
- Routing by severity level (low/medium/high/critical)
- Domain-specific specialization (HR vs. Finance vs. IT)
- Compliance gating (approved → proceed, rejected → escalate)

Running **all branches** when you only need **one** isn't just wasteful—it's architecturally wrong. If only the Sales scenario applies, why invoke Support and Billing agents?

The Routing pattern is about **intelligent decision-making** followed by **selective execution**.

---

## The Anatomy of Routing

The Routing pattern follows a **Classify-Route-Execute** architecture:

**Classification**: Analyze input to determine the appropriate path
**Route Selection**: Choose ONE branch based on classification result
**Execution**: Execute only the selected branch, ignore others

Think of it like a corporate switchboard:
- **Parallel (wrong)**: Connect caller to Sales, Support, AND Billing simultaneously → chaos
- **Routing (correct)**: Ask "How can I help you?" → connect to ONE department → efficient

### Routing vs. Parallel: Side-by-Side

| Aspect | **Parallel (Concurrent)** | **Routing (Conditional)** |
|--------|---------------------------|---------------------------|
| **Branches Executed** | ALL branches run | ONE branch runs |
| **Decision Point** | None (always fan-out) | Classification node decides path |
| **Use Case** | Independent validations, multi-source research | Intent classification, conditional logic |
| **Total Time** | Slowest branch only | Classification time + selected branch |
| **Resource Usage** | High (all LLM calls) | Low (1 classifier + 1 branch) |
| **State Updates** | `branches.{name}.*` for all | `routing.selectedPath`, then `{path}.*` |

**Example:**
- **Parallel**: Run [Support Agent, Sales Agent, Billing Agent] = **3 LLM calls** (expensive)
- **Routing**: Classify intent → run **only** Sales Agent = **2 LLM calls** (efficient)

When branches are mutually exclusive, Routing is the only logical choice.

---

## Flow State: How Context Flows Through Routing

In AgentFlow V2, routing involves a **two-phase state update**:

1. **Classification Phase**: Determine the path and store in `$flow.state.routing.*`
2. **Execution Phase**: Selected branch writes to its own namespace

### State Structure for Routed Workflows

```javascript
{
  "$flow": {
    "state": {
      // Classification result
      "routing": {
        "intent": "sales_inquiry",
        "confidence": 0.92,
        "classifier": "condition_agent",
        "timestamp": "2025-11-14T10:23:15Z"
      },

      // Only the selected branch populates
      "sales": {
        "opportunity": {
          "product": "Workday HCM",
          "estimatedValue": "$500K",
          "timeline": "Q1 2026"
        },
        "nextSteps": ["Schedule demo", "Send pricing"],
        "assignedTo": "sales_team@company.com"
      },

      // Other branches remain empty (not executed)
      "support": {},
      "billing": {}
    }
  }
}
```

### Three Principles of Routing State Management

1. **Classification First**: Always store `routing.intent` or `routing.selectedPath` before execution
2. **Single-Branch Execution**: Only the selected path writes state
3. **Empty Alternatives**: Non-selected branches remain unexecuted (no wasted resources)

This architecture ensures efficient resource usage while maintaining clear decision trails.

---

## The Two Faces of Routing: Rules vs. Intelligence

Flowise AgentFlow V2 offers **two routing mechanisms**:

### Approach 1: Condition Node (Rule-Based Routing)

**When to Use**: Deterministic logic based on explicit values

**How It Works**:
- Define conditions using operators: `equal`, `notEqual`, `contains`, `larger`, `isEmpty`
- Compare values (strings, numbers, booleans)
- Output: `true` or `false` (binary branching)

**Configuration Example**:

```javascript
{
  "node": "condition_check_expense_amount",
  "type": "condition",
  "conditions": [
    {
      "variable": "$flow.state.expense.amount",
      "operator": "larger",
      "value": 1000,
      "dataType": "Number"
    }
  ]
  // Output paths: [true_branch, false_branch]
}
```

**Use Cases**:
- Amount thresholds (>$1000 → manager approval, else auto-approve)
- Status checks (status === "pending" → process, else skip)
- Eligibility gates (role === "admin" → grant access, else deny)

**Strengths**: Fast, predictable, no LLM cost
**Limitations**: Only 2 outputs (true/false), requires explicit rules

---

### Approach 2: Condition Agent Node (AI-Driven Routing)

**When to Use**: Complex intent classification requiring nuanced understanding

**How It Works**:
- Define natural language **Instructions** (what decision to make)
- Specify **Scenarios** (possible outcomes, each gets its own output path)
- LLM analyzes input and selects the best-matching scenario
- Output: Routes to the chosen scenario's branch

**Configuration Example**:

```javascript
{
  "node": "intent_classifier",
  "type": "conditionAgent",
  "model": "claude-sonnet-4-5-20250929",
  "instructions": "Analyze the customer message and classify their intent. Choose the scenario that best matches their primary need.",
  "scenarios": [
    {
      "name": "sales_inquiry",
      "description": "Customer is interested in purchasing, pricing, or product demos"
    },
    {
      "name": "support_request",
      "description": "Customer needs help with existing product, troubleshooting, or technical issues"
    },
    {
      "name": "billing_question",
      "description": "Customer has questions about invoices, payments, or subscription management"
    },
    {
      "name": "general_inquiry",
      "description": "General questions, feedback, or unclear intent"
    }
  ]
  // Output paths: 4 (one per scenario)
}
```

**Use Cases**:
- Customer support routing (intent classification)
- Document type classification (invoice vs. purchase order vs. contract)
- Severity assessment (low/medium/high/critical)
- Sentiment-based routing (positive → thank you, negative → escalation)

**Strengths**: Handles complexity, multiple outputs (N scenarios), adapts to nuance
**Limitations**: LLM cost, slight latency, non-deterministic

---

### Choosing Between Rules and Intelligence

| Factor | **Condition Node** | **Condition Agent Node** |
|--------|-------------------|-------------------------|
| **Decision Complexity** | Simple comparisons | Nuanced understanding |
| **Number of Paths** | 2 (true/false) | N (one per scenario) |
| **Cost** | Free (logic-based) | Paid (LLM inference) |
| **Speed** | Instant (<1ms) | Fast but slower (~500ms) |
| **Determinism** | 100% predictable | ~95% consistent |
| **Examples** | Amount > threshold, status checks | Intent classification, sentiment analysis |

**Rule of Thumb**:
- Use **Condition Node** for binary decisions based on measurable values
- Use **Condition Agent Node** for multi-way classification requiring contextual understanding

---

## Real Workday Scenarios: When Routing Wins

Let's walk through four Workday use cases where the Routing pattern transforms process intelligence.

---

### Scenario 1: Employee Support Request Routing (HCM)

**The Challenge:**
Employees submit support requests via Workday chatbot. Requests range from password resets to benefits questions to payroll issues. Each requires a different team.

**Old Way (Manual Triage):**
All tickets go to general queue → HR admin reads → manually routes → 15-minute delay

**The Routing Way:**

```
              Start (employee message)
                     │
                     ▼
            ┌──────────────────┐
            │ Intent Classifier │
            │ (Condition Agent) │
            └─────────┬──────────┘
                      │
       ┌──────────────┼──────────────┬──────────────┐
       ▼              ▼              ▼              ▼
  IT Support    Benefits Team   Payroll Team   General HR
  (password)    (enrollment)    (discrepancy)  (catch-all)
       │              │              │              │
       └──────────────┴──────────────┴──────────────┘
                      ▼
            Auto-Route to Specialist
```

**Total Time:** **2 seconds** (classification + routing)
**Time Saved:** 87% faster (15 min → 2 sec)
**Business Impact:** Instant specialist assignment, happier employees

### Classification Example

**Employee Message:**
"Hi, I'm trying to enroll in the HSA plan but the deadline page won't load. I keep getting an error when I click 'Confirm Enrollment'."

**Condition Agent Analysis:**

```javascript
{
  "routing": {
    "intent": "benefits_team",
    "confidence": 0.94,
    "reasoning": "Message mentions HSA enrollment and technical issue with benefits portal",
    "keywords": ["enroll", "HSA plan", "deadline", "error"]
  }
}
```

**State After Routing to Benefits Team:**

```javascript
{
  "routing": {...},  // preserved for audit trail
  "benefits": {
    "ticketId": "BEN-2025-1147",
    "issue": "HSA enrollment portal error",
    "priority": "HIGH",  // deadline-sensitive
    "assignedTo": "benefits_specialist@company.com",
    "suggestedActions": [
      "Check for active system maintenance",
      "Verify employee eligibility window",
      "Manually process enrollment if portal down"
    ],
    "sla": "4 hours"  // benefits deadline urgency
  }
}
```

**Why Routing Matters:**
Instead of running IT, Payroll, AND Benefits agents (parallel = wasteful), the Condition Agent classified intent and routed to **only** the Benefits specialist. One LLM call for classification, one agent execution.

---

### Scenario 2: Expense Approval Workflow (Financials)

**The Challenge:**
Expense reports need different approval paths based on amount:
- <$100: Auto-approve
- $100-$1,000: Manager approval
- $1,000-$5,000: Director approval
- >$5,000: CFO approval + audit trail

**The Old Way (Single Approval Queue):**
All expenses go to manager, who manually escalates high-value items → bottleneck

**The Routing Way:**

```
           Start (expense report: $1,250)
                     │
                     ▼
            ┌──────────────────┐
            │  Condition Node   │
            │ (Check Amount)    │
            └─────────┬──────────┘
                      │
       ┌──────────────┼──────────────┬──────────────┐
       ▼              ▼              ▼              ▼
  Auto-Approve   Manager Route   Director Route  CFO Route
  (<$100)        ($100-$1K)      ($1K-$5K)       (>$5K)
       │              │              │              │
       └──────────────┴──────────────┴──────────────┘
                      ▼
           Update Workday + Notify Employee
```

**Condition Node Configuration:**

```javascript
{
  "node": "amount_router",
  "type": "condition",
  "logic": "nested",  // multiple thresholds
  "conditions": [
    {
      "if": "$flow.state.expense.amount < 100",
      "route": "auto_approve"
    },
    {
      "if": "$flow.state.expense.amount >= 100 && $flow.state.expense.amount < 1000",
      "route": "manager_approval"
    },
    {
      "if": "$flow.state.expense.amount >= 1000 && $flow.state.expense.amount < 5000",
      "route": "director_approval"
    },
    {
      "if": "$flow.state.expense.amount >= 5000",
      "route": "cfo_approval"
    }
  ]
}
```

**Real Example:**

**Expense:** Client dinner in NYC – $1,250

**Routing Decision:**

```javascript
{
  "routing": {
    "amount": 1250,
    "selectedPath": "director_approval",
    "rule": "amount >= 1000 && amount < 5000",
    "approver": "Jane Smith (Director, Engineering)"
  }
}
```

**State After Director Route:**

```javascript
{
  "routing": {...},
  "director_approval": {
    "approver": "jane.smith@company.com",
    "expense": {
      "employee": "John Doe",
      "category": "Client Entertainment",
      "amount": 1250,
      "receipt": "uploaded",
      "businessPurpose": "Q4 partnership discussions with Acme Corp"
    },
    "notificationSent": true,
    "approvalDeadline": "2025-11-16T17:00:00Z",  // 48-hour SLA
    "escalationRules": {
      "noResponse": "Auto-escalate to CFO after 48hrs",
      "rejection": "Return to employee with feedback"
    }
  }
}
```

**Why Routing Matters:**
Manager doesn't see $1,250 expense (above their authority), Director gets it immediately. No manual escalation, no bottleneck. **100% of expenses routed to correct approver automatically.**

---

### Scenario 3: Candidate Pipeline Routing (Recruiting)

**The Challenge:**
Candidates apply for various roles. Each role type needs a different screening process:
- Engineering: Technical assessment + system design
- Sales: Role-play + negotiation exercise
- Operations: Process mapping + case study
- Leadership: Executive interview + board presentation

**The Routing Way:**

```
         Start (candidate application + resume)
                     │
                     ▼
            ┌──────────────────┐
            │ Role Classifier   │
            │ (Condition Agent) │
            └─────────┬──────────┘
                      │
       ┌──────────────┼──────────────┬──────────────┐
       ▼              ▼              ▼              ▼
  Engineering   Sales Pipeline  Operations     Leadership
  Screening     Screening       Screening      Screening
       │              │              │              │
       └──────────────┴──────────────┴──────────────┘
                      ▼
           Schedule Appropriate Assessment
```

**Classification Example:**

**Candidate:** Applied for "Senior Engineering Manager"

**Condition Agent Analysis:**

```javascript
{
  "routing": {
    "roleType": "engineering",
    "level": "senior_management",
    "confidence": 0.89,
    "reasoning": "Job title contains 'Engineering Manager', resume shows 8 years technical experience + 3 years leadership"
  }
}
```

**State After Engineering Route:**

```javascript
{
  "routing": {...},
  "engineering": {
    "candidateId": "CAND-2025-3482",
    "screeningPipeline": [
      {
        "stage": "Technical Phone Screen",
        "duration": "45 min",
        "focus": ["System design", "Leadership scenarios"],
        "interviewer": "Assigned based on calendar"
      },
      {
        "stage": "Coding Assessment",
        "platform": "HackerRank",
        "difficulty": "Senior-level",
        "timeLimit": "90 min"
      },
      {
        "stage": "Onsite Loop",
        "interviews": [
          {"type": "System Design", "duration": "60 min"},
          {"type": "Team Management", "duration": "45 min"},
          {"type": "Cultural Fit", "duration": "30 min"}
        ]
      }
    ],
    "estimatedTimeToHire": "3-4 weeks",
    "nextAction": "Send technical assessment invite"
  }
}
```

**Why Routing Matters:**
Sales candidates don't get coding tests. Engineers don't get role-play exercises. Each role gets a **tailored screening pipeline**, improving candidate experience and hiring accuracy.

---

### Scenario 4: Incident Severity Routing (IT Operations)

**The Challenge:**
IT incidents need triage based on severity:
- **Critical**: Production down, revenue impact → Page on-call engineer immediately
- **High**: Major feature broken, customer-facing → Assign to senior engineer, 2-hour SLA
- **Medium**: Minor bug, workaround exists → Regular queue, 24-hour SLA
- **Low**: Enhancement request, non-blocking → Backlog, next sprint

**The Routing Way:**

```
         Start (incident report)
                │
                ▼
       ┌────────────────┐
       │ Severity Agent │
       │ (AI Analysis)  │
       └────────┬────────┘
                │
    ┌───────────┼───────────┬─────────────┐
    ▼           ▼           ▼             ▼
 Critical    High        Medium         Low
 (Page)      (Assign)    (Queue)        (Backlog)
    │           │           │             │
    └───────────┴───────────┴─────────────┘
                │
        Update Ticket + Notify
```

**Severity Classification Example:**

**Incident Report:**
"Workday login page returning 503 errors. All employees unable to access HCM. Started 10 minutes ago."

**Condition Agent Analysis:**

```javascript
{
  "routing": {
    "severity": "critical",
    "confidence": 0.97,
    "reasoning": "Production system down, affects all users, no workaround, active outage",
    "impactScore": 10,  // max impact
    "urgencyScore": 10  // max urgency
  }
}
```

**State After Critical Route:**

```javascript
{
  "routing": {...},
  "critical": {
    "incidentId": "INC-2025-8821",
    "severity": "P0 - Critical Outage",
    "actions": [
      {
        "type": "page_oncall",
        "target": "oncall_engineer@company.com",
        "method": ["PagerDuty", "SMS", "Phone Call"],
        "status": "SENT",
        "timestamp": "2025-11-14T14:23:47Z"
      },
      {
        "type": "war_room",
        "channel": "#incident-war-room-8821",
        "participants": ["SRE team", "Engineering leads", "CTO"],
        "status": "ACTIVE"
      },
      {
        "type": "status_page",
        "message": "Workday HCM login experiencing issues. Team investigating.",
        "visibility": "PUBLIC",
        "updated": true
      }
    ],
    "sla": "15 minutes to acknowledge, 1 hour to resolve",
    "escalationTimer": "900s"  // auto-escalate if no ack in 15 min
  }
}
```

**Why Routing Matters:**
Minor bugs don't trigger pages. Critical outages don't sit in queues. **Severity-based routing ensures the right response** at the right speed.

---

## Visual Architecture: The Classification-Route Pattern

Here's how the Customer Support Routing workflow looks in Flowise:

```
┌─────────────────────────────────────────────────────────┐
│                    Start Node                           │
│  (Input: customer message)                              │
└────────────┬────────────────────────────────────────────┘
             │
             ▼
    ┌─────────────────┐
    │ Intent Classifier│
    │(Condition Agent) │
    └────────┬─────────┘
             │
    ┌────────┼────────┬─────────┐
    ▼        ▼        ▼         ▼
┌────────┐ ┌───────┐ ┌──────┐ ┌────────┐
│Sales   │ │Support│ │Billing│ │General │
│Agent   │ │Agent  │ │Agent  │ │Agent   │
└───┬────┘ └───┬───┘ └──┬───┘ └───┬────┘
    │          │         │         │
    │    (ONLY ONE EXECUTES)       │
    │          │         │         │
    └──────────┼─────────┴─────────┘
               ▼
        ┌─────────────┐
        │   Reply     │
        └─────────────┘
```

**Key Difference from Parallel:**

**Parallel:**
```
Start → [Agent A, Agent B, Agent C] → Aggregator
(ALL agents run, results merged)
```

**Routing:**
```
Start → Classifier → [Agent A OR Agent B OR Agent C] → Reply
(ONE agent runs, no aggregation needed)
```

---

## Technical Deep-Dive: Building a Routing Workflow

### Condition Agent Configuration (Intent Classification)

```javascript
{
  "id": "intent_classifier",
  "type": "conditionAgent",
  "data": {
    "model": "claude-sonnet-4-5-20250929",
    "temperature": 0.2,  // Lower temp for consistent classification
    "instructions": `Analyze the customer message and determine their primary intent.

Consider these factors:
- Keywords and phrases
- Urgency indicators
- Specific questions or requests
- Emotional tone

Choose the scenario that best matches their need.`,
    "scenarios": [
      {
        "name": "sales_inquiry",
        "description": "Customer interested in purchasing, pricing, demos, or product information. Keywords: 'buy', 'price', 'demo', 'features', 'upgrade'."
      },
      {
        "name": "support_request",
        "description": "Customer needs help with existing product, technical issues, troubleshooting, or 'how-to' questions. Keywords: 'error', 'not working', 'help', 'broken', 'issue'."
      },
      {
        "name": "billing_question",
        "description": "Customer has questions about invoices, payments, subscriptions, refunds, or account charges. Keywords: 'invoice', 'charge', 'refund', 'payment', 'subscription'."
      },
      {
        "name": "general_inquiry",
        "description": "General questions, feedback, unclear intent, or doesn't fit other categories."
      }
    ],
    "agentStateUpdates": [
      {"key": "routing.intent", "value": "{{ selectedScenario }}"},
      {"key": "routing.confidence", "value": "{{ confidence }}"},
      {"key": "routing.timestamp", "value": "{{ timestamp }}"}
    ]
  }
}
```

### Sales Agent (One Possible Route)

```javascript
{
  "id": "sales_agent",
  "type": "agent",
  "data": {
    "model": "claude-sonnet-4-5-20250929",
    "temperature": 0.7,  // Higher temp for conversational sales
    "systemPrompt": `You are a sales specialist for Workday products.

Your goal:
- Understand customer needs and budget
- Recommend appropriate Workday solutions (HCM, Financials, PSA)
- Provide pricing estimates
- Schedule demos with sales team

Always be helpful, consultative, and focused on value.`,
    "tools": ["workday_product_catalog", "demo_scheduler", "crm_integration"],
    "agentStateUpdates": [
      {"key": "sales.opportunity.product", "value": "{{ recommended_product }}"},
      {"key": "sales.opportunity.estimatedValue", "value": "{{ estimated_value }}"},
      {"key": "sales.nextSteps", "value": "{{ next_steps }}"}
    ]
  }
}
```

### Edge Configuration (Routing Paths)

```javascript
// Start to Classifier
{"source": "start_node", "target": "intent_classifier"}

// Classifier to Route-Specific Agents (conditional edges)
{"source": "intent_classifier", "sourceHandle": "sales_inquiry", "target": "sales_agent"}
{"source": "intent_classifier", "sourceHandle": "support_request", "target": "support_agent"}
{"source": "intent_classifier", "sourceHandle": "billing_question", "target": "billing_agent"}
{"source": "intent_classifier", "sourceHandle": "general_inquiry", "target": "general_agent"}

// Each agent to Reply (only executed agent proceeds)
{"source": "sales_agent", "target": "reply_node"}
{"source": "support_agent", "target": "reply_node"}
{"source": "billing_agent", "target": "reply_node"}
{"source": "general_agent", "target": "reply_node"}
```

**Note:** The `sourceHandle` parameter specifies which scenario output path to follow. Only the matched path executes.

---

## Hybrid Pattern: Routing + Parallel

Sometimes you need **both** patterns in a single workflow.

### Example: Multi-Stage Incident Response

```
         Start (incident report)
                │
                ▼
       ┌────────────────┐
       │ Severity Router│  ← ROUTING
       └────────┬────────┘
                │
         (If Critical)
                │
                ▼
       ┌────────────────────────┐
       │     FAN-OUT             │  ← PARALLEL
       ├────────┬────────┬───────┤
       ▼        ▼        ▼       ▼
    Page     War Room  Status   Customer
    Oncall   Setup     Page     Notice
       │        │        │       │
       └────────┴────────┴───────┘
                │
                ▼
       ┌────────────────┐
       │   Aggregator    │
       └────────────────┘
```

**Flow:**
1. **Route by severity** (Critical vs. High vs. Medium)
2. If Critical → **Parallel execution** of multiple urgent actions
3. Aggregate results and update incident ticket

**When to Use Hybrid:**
- First, classify/route based on type/severity
- Then, within the selected route, run parallel sub-tasks if needed

**State Structure:**

```javascript
{
  "routing": {
    "severity": "critical"  // Router decision
  },
  "critical": {
    // Parallel branches within critical route
    "branches": {
      "paging": {"status": "sent", "completed": true},
      "warRoom": {"channel": "created", "completed": true},
      "statusPage": {"updated": true, "completed": true},
      "customerNotice": {"sent": true, "completed": true}
    },
    "aggregate": {
      "allActionsComplete": true,
      "responseTime": "47 seconds"
    }
  }
}
```

---

## When to Use Routing vs. Other Patterns

### The 30-Second Litmus Test

```
Do branches need to run based on conditions?
  ├─ YES → Are conditions simple (true/false)?
  │         ├─ YES → Condition Node (Rule-Based) ✓
  │         └─ NO → Need multi-way classification?
  │                  └─ YES → Condition Agent (AI-Driven) ✓
  │
  └─ NO → Should ALL branches always run?
            ├─ YES → PARALLEL
            └─ NO → Need sequential execution?
                     └─ YES → CHAINING
```

### Decision Matrix

| Pattern | When to Use | Don't Use If |
|---------|-------------|--------------|
| **Routing (Rules)** | Binary decisions, threshold checks, status gates | Need nuanced classification |
| **Routing (AI)** | Intent classification, multi-way routing, complexity | Simple true/false logic |
| **Parallel** | Independent tasks, all needed, concurrent execution | Mutually exclusive branches |
| **Chaining** | Sequential dependencies, order matters, artifact handoffs | No dependencies exist |

### Perfect for Routing:
- ✅ Customer support intent classification (sales/support/billing)
- ✅ Severity-based escalation (low/medium/high/critical)
- ✅ Approval workflows (amount-based routing)
- ✅ Document type routing (invoice/PO/contract → specific handler)

### Consider Alternatives:
- ❌ Multi-source research → **Parallel** (need all sources)
- ❌ Approval chain (employee → manager → director) → **Chaining** (sequential approvals)
- ❌ Quality improvement loop → **Iteration** (refine until acceptable)

---

## Best Practices for Routing Workflows

### 1. Classification Quality is Everything

**Rule-Based (Condition Node):**
```javascript
// Good: Clear, unambiguous thresholds
if (expense.amount >= 1000) {
  route = "director_approval"
}

// Bad: Overlapping conditions
if (expense.amount > 500) {
  route = "manager"  // What if amount is 1500? Both trigger!
}
if (expense.amount > 1000) {
  route = "director"
}
```

**AI-Based (Condition Agent):**
```javascript
// Good: Clear scenario descriptions with keywords
{
  "name": "urgent_support",
  "description": "Customer has urgent issue preventing work. Keywords: 'urgent', 'critical', 'blocker', 'down', 'immediately'. Tone: frustrated or stressed."
}

// Bad: Vague, overlapping scenarios
{
  "name": "support",
  "description": "Customer needs help"  // Too generic!
}
```

### 2. Always Have a Fallback Route

**Condition Node:** Explicit else/default branch
```javascript
{
  "conditions": [
    {"if": "amount < 100", "route": "auto_approve"},
    {"if": "amount >= 100 && amount < 1000", "route": "manager"},
    {"if": "amount >= 1000", "route": "director"}
  ],
  "defaultRoute": "manual_review"  // Catches unexpected cases
}
```

**Condition Agent:** Add "general" or "unclear" scenario
```javascript
{
  "scenarios": [
    {"name": "sales", ...},
    {"name": "support", ...},
    {"name": "billing", ...},
    {"name": "unclear_intent", "description": "Intent is ambiguous or doesn't fit other categories. Route to general team for manual classification."}
  ]
}
```

### 3. Log Classification Decisions

Store routing decisions for debugging and improvement:

```javascript
"agentStateUpdates": [
  {"key": "routing.intent", "value": "{{ selectedScenario }}"},
  {"key": "routing.confidence", "value": "{{ confidence }}"},
  {"key": "routing.reasoning", "value": "{{ reasoning }}"},  // Why this path?
  {"key": "routing.timestamp", "value": "{{ timestamp }}"},
  {"key": "routing.inputPreview", "value": "{{ first_100_chars }}"}  // For audit
]
```

**Why This Matters:**
If classification is wrong, you need logs to:
- Identify patterns (certain keywords consistently misclassified)
- Improve scenario descriptions
- Add edge case handling

### 4. Set Confidence Thresholds

For Condition Agent routing, handle low-confidence classifications:

```javascript
if (routing.confidence < 0.7) {
  // Low confidence → route to human review instead
  route = "manual_classification_queue"
  escalationReason = "AI confidence below threshold"
}
```

### 5. Test Edge Cases

**Rule-Based Edge Cases:**
- Boundary values (amount = exactly $1000)
- Null/undefined inputs
- Unexpected data types (string "500" vs. number 500)

**AI-Based Edge Cases:**
- Ambiguous messages ("I need help with pricing" → sales or support?)
- Multi-intent messages ("I want a demo but my current system is broken")
- Non-English text (if multilingual routing)
- Sarcasm or unclear tone

### 6. Routing Anti-Patterns

**❌ Don't: The "Route Everything" Trap**
```javascript
// Bad: Routing to parallel sub-branches (just use parallel directly!)
Start → Router → [ParallelBranch1, ParallelBranch2, ParallelBranch3]
```

**✓ Do: Route to single execution paths**
```javascript
// Good: Each route is a distinct execution path
Start → Router → [SalesAgent OR SupportAgent OR BillingAgent]
```

**❌ Don't: Nested Routers Without Purpose**
```javascript
// Bad: Router → Router → Router (hard to debug)
Start → SeverityRouter → DepartmentRouter → SkillRouter → Agent
```

**✓ Do: Single classification or hybrid**
```javascript
// Good: One classification step, then execute
Start → IntentRouter → SpecializedAgent

// Or: One router, then parallel actions within route
Start → SeverityRouter → (if critical) → [Page, WarRoom, StatusUpdate]
```

---

## Your Action Items: Progressive Complexity

Start simple, iterate, improve. Don't build the perfect classifier on day one.

### Week 1: Simple Rule-Based Router (20 minutes)

**Goal:** Build your first binary routing workflow

**Example:** Expense Auto-Approval

1. Create Condition Node checking `expense.amount < 100`
2. True path → Auto-Approve Agent
3. False path → Manager Approval Agent
4. Test with amounts: $50 (auto), $150 (manager)

**Measure:**
- Does each path execute correctly?
- Are state updates isolated to executed branch?

### Week 2: Multi-Way AI Router (45 minutes)

**Goal:** Build intent classification with 3-4 scenarios

**Example:** Customer Support Router (Sales/Support/Billing/General)

1. Create Condition Agent Node with 4 scenarios
2. Write clear scenario descriptions with keywords
3. Connect each scenario to specialized agent
4. Add fallback scenario ("unclear_intent")

**Test Cases:**
- "I want to buy Workday HCM" → Sales
- "My payroll report is showing errors" → Support
- "When will I receive my refund?" → Billing
- "Hello, I have a question" → General (ambiguous)

**Measure:**
- Classification accuracy (manual validation on 10 test messages)
- Confidence scores (are low-confidence cases routed to fallback?)

### Week 3: Routing + State Management (1 hour)

**Goal:** Build routing with comprehensive state updates

**Example:** IT Incident Severity Router

1. Create 4-way severity classification (Critical/High/Medium/Low)
2. Each route has different SLA and notification logic
3. Store `routing.severity`, `routing.impactScore`, `routing.urgencyScore`
4. Selected route stores detailed action plan in `{severity}.*` namespace

**Measure:**
- Can you trace why an incident was classified as "High" vs. "Critical"?
- Are SLAs correctly assigned based on severity?
- Can you generate reports from routing logs?

### Week 4: Hybrid Routing + Parallel (1.5 hours)

**Goal:** Combine routing with parallel execution

**Example:** Multi-Stage Incident Response

1. First stage: Route by severity (Condition Agent)
2. If Critical → Parallel: [Page Oncall, War Room Setup, Status Page, Customer Notice]
3. If High → Single: Assign to Senior Engineer
4. If Medium → Single: Add to Queue

**Measure:**
- Does routing correctly trigger parallel for Critical only?
- Are parallel branches within Critical route independent?
- Is total time optimal (routing + parallel, not sequential)?

---

## The Bottom Line

The Routing pattern is about **intelligent decision-making** followed by **efficient execution**.

When branches are mutually exclusive, running all of them isn't just wasteful—it's architecturally wrong. If only the Sales scenario applies, why invoke Support and Billing agents?

In Flowise, routing means:
- **Classification-Route-Execute** architecture (one decision → one path)
- **Two routing mechanisms**: Condition Node (rule-based) or Condition Agent (AI-driven)
- **Efficient resource usage** (pay for 1 branch, not N branches)

**Choose Rules** for deterministic, binary decisions (amount > threshold, status checks)
**Choose AI** for nuanced, multi-way classification (intent, sentiment, complexity)

When your routing classifier is accurate and your fallback scenarios are robust, you haven't just built a smarter workflow.

You've built **adaptive intelligence**.

That's the difference between treating every problem the same way and treating each problem the right way.

---

## Next Week: Iterative Refinement

Last week: **Parallel** (concurrent, independence matters)
This week: **Routing** (conditional, intent matters)
Next week: **Iteration** (refinement, quality matters)

We'll explore:
- The Iteration Litmus Test (when to refine vs. accept first result)
- Quality feedback loops (test-driven refinement)
- Progressive enhancement patterns (improve until threshold met)
- Human-in-the-loop validation gates

**Preview:**

```
            Start (draft document)
              │
              ▼
        ┌─────────────┐
        │  Generate   │
        │   Draft     │
        └──────┬──────┘
               ▼
        ┌─────────────┐
        │   Evaluate  │
        │   Quality   │
        └──────┬──────┘
               │
        Quality >= 8? ──NO─→ (feedback loop)
               │              ↑
              YES             │
               │              │
               └──────────────┘
               ▼
            Finalized Document
```

Only **iterate** if quality is below threshold. Routing runs **one** branch. Parallel runs **all** branches.

Know the difference. Use the right pattern.

---

## Your Turn

**What Workday process needs intelligent routing?**

Drop a comment with your use case:
- HCM (support routing, candidate screening, performance review escalation)
- Financials (expense approval, invoice routing, budget allocation)
- IT Operations (incident severity, request classification, change approval)
- Customer Service (intent classification, escalation routing)

I'll suggest the optimal routing mechanism (rule-based vs. AI-driven) and state management strategy. Let's build something amazing together!

---

**Built with:** [https://flowiseai.com](https://flowiseai.com)
**AgentFlow V2 Docs:** [https://docs.flowiseai.com/using-flowise/agentflowv2](https://docs.flowiseai.com/using-flowise/agentflowv2)
**Templates:** [https://github.com/FlowiseAI/Flowise/tree/main/templates](https://github.com/FlowiseAI/Flowise/tree/main/templates)

#Workday #WorkdayExtend #AI #AgentWorkflows #Automation #LLMOps #Flowise #AgentFlowV2 #MachineLearning #ConditionalBranching #IntentClassification #SmartRouting
