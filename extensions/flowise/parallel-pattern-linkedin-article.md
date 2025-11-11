# Running Parallel Workflows: The Concurrent Execution Pattern in Flowise

---

Picture a Formula 1 pit stop. The car screams in at 200 mph. In 2.3 seconds, four tire specialists, two jack operators, and a front wing adjuster execute twenty-seven simultaneous actions.

Sequential? The pit stop would take 15 seconds. Parallel? Championship-winning speed.

That's the difference between running tasks one-at-a-time versus running them simultaneously.

## Why Parallel Matters When Chaining Doesn't

Last week, we explored the Chaining pattern—sequential workflows where order matters. Paint the car *after* you build it.

But what about when tasks are **independent**?

- Checking three different compliance databases
- Gathering data from multiple APIs simultaneously
- Running parallel validations before a decision

Running independent tasks sequentially isn't just inefficient—it's architecturally wrong. If Task A doesn't need Task B's output, why make it wait?

The Parallel pattern is about **recognizing independence** and benefiting from it.

---

## The Anatomy of Parallel Execution

The Parallel pattern follows a **Fan-Out/Fan-In** architecture:

**Fan-Out**: One starting point branches to multiple concurrent nodes
**Parallel Execution**: All branches run simultaneously (theoretically)
**Fan-In**: Results converge at an aggregator node for synthesis

Think of it like a research team:
- **Sequential (Chaining)**: One researcher finishes, hands notes to the next → slow
- **Parallel**: Three researchers investigate simultaneously → 3x faster

### Parallel vs. Chaining: Side-by-Side

| Aspect | **Chaining (Sequential)** | **Parallel (Concurrent)** |
|--------|---------------------------|---------------------------|
| **Execution Order** | Strict: A → B → C | Simultaneous: [A, B, C] → Aggregator |
| **Total Time** | Sum of all steps (longest path) | Time of slowest branch only |
| **Dependencies** | Each step waits for previous | All branches start together |
| **Data Flow** | Linear handoffs (artifact_1 → artifact_2) | Independent branches, merged at end |
| **Use Case** | Approval workflows, document pipelines | Multi-source research, parallel checks |
| **State Updates** | `chain.step`, sequential artifacts | `branches.{name}.completed`, per-branch results |

**Example:**
- **Chaining**: Background Check (3 min) → I-9 (2 min) → Benefits (4 min) = **9 minutes total**
- **Parallel**: [Background Check || I-9 || Benefits] = **4 minutes total** (slowest branch)

When independence exists, Parallel is the only logical choice.

---

## Flow State: How Context Flows Across Parallel Branches

In AgentFlow V2, parallel branches don't share a growing chat history. Instead, each branch updates its own **namespace** in `$flow.state`, then the Aggregator synthesizes everything.

### State Structure for Parallel Workflows

```javascript
{
  "$flow": {
    "state": {
      // Each branch gets its own namespace
      "branches": {
        "backgroundCheck": {
          "results": "",
          "completed": false,
          "status": ""
        },
        "i9Verification": {
          "results": "",
          "completed": false,
          "documents": []
        },
        "benefitsEligibility": {
          "results": "",
          "plans": [],
          "completed": false
        }
      },

      // Aggregator writes final synthesis here
      "aggregate": {
        "summary": "",
        "readyToHire": false,
        "blockers": []
      }
    }
  }
}
```

### Three Principles of Parallel State Management

1. **Branch Isolation**: Each branch writes to `branches.{name}.*` only
2. **Completion Signaling**: Every branch sets `branches.{name}.completed = true` when done
3. **Aggregation**: Final node reads all `branches.*` and synthesizes into `aggregate.*`

This architecture keeps branches independent while enabling intelligent convergence.

---

## Real Workday Scenarios: When Parallel Wins

Let's walk through four Workday use cases where the Parallel pattern transforms process efficiency.

---

### Scenario 1: New Hire Onboarding (HCM)

**The Challenge:**
A new Software Engineer starts Monday. Before granting system access, you need:
- Background check clearance
- I-9 employment verification
- Benefits eligibility confirmation
- IT provisioning approval

**The Old Way (Sequential):**
Background check (5 min) → I-9 (3 min) → Benefits (7 min) → IT (4 min) = **19 minutes**

**The Parallel Way:**

```
                    Start (new hire data)
                          │
        ┌─────────────────┼─────────────────┬─────────────┐
        ▼                 ▼                 ▼             ▼
  Background Check    I-9 Verify      Benefits      IT Provisioning
  (5 min)             (3 min)         (7 min)       (4 min)
        │                 │                 │             │
        └─────────────────┼─────────────────┴─────────────┘
                          ▼
                   Onboarding Decision
                  (approve/flag/block)
                          ▼
                 Update Workday + Notify
```

**Total Time:** **7 minutes** (slowest branch: Benefits)
**Time Saved:** 63% faster
**Business Impact:** New hire gets access same day, not next day

### State Flow Example

**After Parallel Branches Complete:**

```javascript
{
  "branches": {
    "backgroundCheck": {
      "status": "CLEAR",
      "vendor": "Sterling",
      "completed": true,
      "timestamp": "2025-11-14T09:15:23Z"
    },
    "i9": {
      "status": "VERIFIED",
      "documents": ["passport", "ssn_card"],
      "completed": true,
      "expirationDate": "2030-05-20"
    },
    "benefits": {
      "eligible": true,
      "plans": ["Medical PPO", "Dental", "401k"],
      "effectiveDate": "2025-11-14",
      "completed": true
    },
    "itProvisioning": {
      "status": "APPROVED",
      "systems": ["Workday", "Slack", "GitHub", "AWS"],
      "completed": true
    }
  }
}
```

**After Aggregation:**

```javascript
{
  "branches": {...},  // preserved for audit trail
  "aggregate": {
    "decision": "APPROVED",
    "readyToHire": true,
    "blockers": [],  // empty = good to go
    "systemAccessGranted": true,
    "notificationsSent": ["hiring_manager", "it_team", "candidate"]
  }
}
```

**The Aggregator's Role:**
Checks all `branches.*.completed` flags, validates no `status: "FAIL"` exists, then grants access. If any branch fails (e.g., background check flagged), it routes to HR for manual review.

---

### Scenario 2: Expense Report Validation (Financials)

**The Challenge:**
CFO wants expense reports validated for:
- Policy compliance (per diem limits, approved categories)
- Receipt matching (OCR + amount verification)
- Budget availability (department budget check)
- Duplicate detection (same expense claimed twice)

**Sequential Problem:**
By the time you check for duplicates (step 4), you've already spent time on a potentially invalid claim.

**Parallel Solution:**

```
                Start (expense report submission)
                          │
        ┌─────────────────┼─────────────────┬─────────────┐
        ▼                 ▼                 ▼             ▼
  Policy Check      Receipt Match      Budget Check   Duplicate Scan
  (2s - rules)      (4s - OCR)         (3s - ERP)     (2s - DB query)
        │                 │                 │             │
        └─────────────────┼─────────────────┴─────────────┘
                          ▼
                    Smart Routing
              (auto-approve / flag / reject)
                          ▼
                 Workday Financials Update
```

**Total Time:** **4 seconds** (slowest: Receipt Match OCR)
vs. **11 seconds sequential**

**Real Example:**

**Expense:** Dinner in San Francisco – $187.50

**Parallel Branch Results:**

```javascript
{
  "branches": {
    "policyCheck": {
      "compliant": false,
      "violations": ["Exceeds SF dinner per diem of $75"],
      "completed": true
    },
    "receiptMatch": {
      "ocrAmount": "$187.50",
      "claimedAmount": "$187.50",
      "matched": true,
      "vendor": "Boulevard Restaurant",
      "completed": true
    },
    "budgetCheck": {
      "available": true,
      "department": "Engineering",
      "remaining": "$12,340",
      "completed": true
    },
    "duplicateScan": {
      "isDuplicate": false,
      "similarClaims": [],
      "completed": true
    }
  }
}
```

**Aggregator Decision:**

```javascript
{
  "aggregate": {
    "decision": "FLAG_FOR_REVIEW",
    "reason": "Policy violation: exceeds per diem by $112.50",
    "autoApprove": false,
    "severity": "MEDIUM",
    "recommendedAction": "Request manager override or split across 2 days"
  }
}
```

**Why Parallel Matters:**
Discovered the policy violation in 4 seconds instead of 11. If this were auto-reject logic, employee gets feedback immediately—not after wasting time on OCR and duplicate scans.

---

### Scenario 3: Project Feasibility Analysis (PSA)

**The Challenge:**
Sales team wants to bid on a $2M project. Before committing, you need parallel analysis:
- Resource availability (do we have the people?)
- Skills match (do they have the right expertise?)
- Margin calculation (is it profitable at proposed rate?)
- Risk assessment (complexity, dependencies, past performance)

**Parallel Workflow:**

```
              Start (project opportunity: $2M, 6 months)
                          │
        ┌─────────────────┼─────────────────┬─────────────┐
        ▼                 ▼                 ▼             ▼
  Resource Check    Skills Analysis    Margin Calc    Risk Assessment
  (Workday HCM)     (Talent DB)        (Finance)      (Historical)
        │                 │                 │             │
        └─────────────────┼─────────────────┴─────────────┘
                          ▼
                   Feasibility Report
                  (GO / NO-GO / CONDITIONAL)
                          ▼
                  Sales Team Notification
```

**State After Parallel Execution:**

```javascript
{
  "branches": {
    "resourceAvailability": {
      "available": true,
      "consultants": [
        {"name": "Sarah Chen", "role": "Tech Lead", "availability": "80%"},
        {"name": "Marcus Rodriguez", "role": "Senior Dev", "availability": "100%"},
        {"name": "Priya Sharma", "role": "BA", "availability": "60%"}
      ],
      "gaps": ["Need 1 additional senior dev"],
      "completed": true
    },
    "skillsMatch": {
      "requiredSkills": ["Python", "AWS", "Workday Integrations"],
      "teamCoverage": 85,  // 85% match
      "missingSkills": ["Workday Prism Analytics"],
      "trainingNeeded": true,
      "completed": true
    },
    "marginCalculation": {
      "proposedRate": "$180/hr",
      "estimatedCost": "$1.4M",
      "revenue": "$2M",
      "margin": 30,  // 30% margin
      "profitable": true,
      "completed": true
    },
    "riskAssessment": {
      "complexity": "HIGH",
      "dependencies": ["Client Workday upgrade", "3rd party API"],
      "historicalSuccess": 0.78,  // 78% similar projects succeeded
      "riskScore": 6.5,  // out of 10
      "completed": true
    }
  }
}
```

**Aggregator Synthesis:**

```javascript
{
  "aggregate": {
    "decision": "CONDITIONAL_GO",
    "confidence": 75,
    "summary": "Project is feasible with conditions: hire 1 senior dev, budget 40hrs for Prism training, add $50K risk contingency.",
    "recommendations": [
      "Start recruiting for senior dev now",
      "Negotiate milestone-based payments",
      "Schedule Prism Analytics training for team"
    ],
    "estimatedStartDate": "2025-12-01"  // after hiring
  }
}
```

**Business Impact:**
Sales gets a **comprehensive feasibility report in 8 seconds** instead of 3 days of manual coordination across HR, Finance, and PMO.

---

### Scenario 4: Candidate Evaluation (Recruiting)

**The Challenge:**
A candidate applies for Senior Engineering Manager. You need simultaneous evaluation of:
- Resume screening (experience, keywords, role fit)
- Skills assessment (technical test results)
- Culture fit analysis (values alignment, leadership style)
- Reference checks (past performance verification)

**Why Parallel?**
Reference checks can take hours (phone calls). While waiting, run resume + skills + culture analysis simultaneously. Total time = longest individual task, not sum of all tasks.

**Workflow:**

```
           Start (candidate application + assessment data)
                          │
        ┌─────────────────┼─────────────────┬─────────────┐
        ▼                 ▼                 ▼             ▼
  Resume Screen     Skills Analysis   Culture Fit    Reference Check
  (LLM - 3s)        (Test results)    (Survey + LLM) (Async - 2hrs)
        │                 │                 │             │
        └─────────────────┼─────────────────┴─────────────┘
                          ▼
                 Candidate Scorecard
                  (hire / maybe / pass)
                          ▼
            Hiring Manager Notification + Next Steps
```

**Key Insight:**
Reference checks are slow (human-in-the-loop). But the other three branches can complete in seconds. The Aggregator waits for all branches via `completed` flags, then synthesizes.

**Parallel Results:**

```javascript
{
  "branches": {
    "resumeScreen": {
      "score": 8.5,  // out of 10
      "experience": "12 years, 5 in management",
      "keywordMatch": 92,  // 92% match to job description
      "redFlags": [],
      "completed": true
    },
    "skillsAssessment": {
      "technicalScore": 85,  // out of 100
      "strengths": ["System design", "Team leadership"],
      "weaknesses": ["Kubernetes deep-dive"],
      "passThreshold": 70,
      "passed": true,
      "completed": true
    },
    "cultureFit": {
      "values": ["Collaboration: HIGH", "Innovation: MEDIUM", "Ownership: HIGH"],
      "leadershipStyle": "Servant leader, consensus-driven",
      "alignment": 88,  // 88% match to company culture
      "completed": true
    },
    "referenceCheck": {
      "contacts": [
        {"name": "Former Manager", "rating": 9, "comment": "Top 5% performer"},
        {"name": "Peer", "rating": 8, "comment": "Great collaborator"}
      ],
      "averageRating": 8.5,
      "concerns": "None",
      "completed": true,
      "duration": "7200s"  // 2 hours
    }
  }
}
```

**Aggregator Decision:**

```javascript
{
  "aggregate": {
    "decision": "STRONG_HIRE",
    "overallScore": 8.6,
    "summary": "Excellent fit across all dimensions. Resume + skills + culture + references all score 8.5+. Recommend immediate offer.",
    "nextSteps": [
      "Schedule exec interview",
      "Prepare offer package",
      "Target start date: 2025-12-15"
    ]
  }
}
```

**Time Comparison:**
- **Sequential:** 2hrs 6min (all tasks in series)
- **Parallel:** 2hrs 0min (dominated by reference checks, but resume/skills/culture ran simultaneously)
- **Time Saved:** Not dramatic in total time (references are bottleneck), but **recruiter productivity increased 3x** (no manual coordination)

---

## Visual Architecture: The Fan-Out/Fan-In Dance

Here's how the Expense Report workflow looks in Flowise:

```
┌─────────────────────────────────────────────────────────┐
│                    Start Node                           │
│  (Input: expense report JSON)                           │
└────────────┬────────────────────────────────────────────┘
             │
    ┌────────┼────────┬─────────────┐
    ▼        ▼        ▼             ▼
┌────────┐ ┌───────┐ ┌──────────┐ ┌─────────┐
│ Policy │ │Receipt│ │  Budget  │ │Duplicate│
│ Check  │ │ Match │ │  Check   │ │  Scan   │
└───┬────┘ └───┬───┘ └────┬─────┘ └────┬────┘
    │          │           │            │
    └──────────┼───────────┴────────────┘
               ▼
        ┌─────────────┐
        │ Aggregator  │
        │ (synthesis) │
        └──────┬──────┘
               ▼
        ┌─────────────┐
        │Smart Routing│
        └──────┬──────┘
               ▼
        ┌─────────────┐
        │   Reply     │
        └─────────────┘
```

**Data Flow:**

1. **Start Node** fans out to 4 branches simultaneously
2. Each branch writes to `branches.{name}.*` in Flow State
3. **Aggregator** reads all `branches.*` once all `completed = true`
4. **Smart Routing** decides auto-approve / flag / reject based on aggregated data
5. **Reply** sends notification + updates Workday

---

## Technical Deep-Dive: Building a Parallel Workflow

### Node Configuration Example

**Background Check Agent (Branch 1):**

```javascript
{
  "id": "agent_background_check",
  "type": "agent",
  "data": {
    "model": "claude-sonnet-4-5-20250929",
    "temperature": 0.2,
    "systemPrompt": "You are a background check validator. Verify candidate info against Sterling API. Return CLEAR/FLAG/FAIL.",
    "tools": ["sterling_api", "workday_hcm"],
    "agentEnableMemory": true,
    "agentStateUpdates": [
      {"key": "branches.backgroundCheck.status", "value": "{{ status }}"},
      {"key": "branches.backgroundCheck.vendor", "value": "Sterling"},
      {"key": "branches.backgroundCheck.completed", "value": "true"}
    ]
  }
}
```

**I-9 Verification Agent (Branch 2):**

```javascript
{
  "id": "agent_i9",
  "type": "agent",
  "data": {
    "model": "claude-sonnet-4-5-20250929",
    "temperature": 0.2,
    "systemPrompt": "Verify I-9 documents. Check expiration dates, validate document types.",
    "tools": ["document_verification_api"],
    "agentStateUpdates": [
      {"key": "branches.i9.status", "value": "{{ status }}"},
      {"key": "branches.i9.documents", "value": "{{ documents }}"},
      {"key": "branches.i9.expirationDate", "value": "{{ expiration }}"},
      {"key": "branches.i9.completed", "value": "true"}
    ]
  }
}
```

**Benefits Eligibility Agent (Branch 3):**

```javascript
{
  "id": "agent_benefits",
  "type": "agent",
  "data": {
    "model": "claude-sonnet-4-5-20250929",
    "temperature": 0.2,
    "systemPrompt": "Check benefits eligibility. Verify hire date, employment type, location.",
    "tools": ["workday_benefits_api"],
    "agentStateUpdates": [
      {"key": "branches.benefits.eligible", "value": "{{ eligible }}"},
      {"key": "branches.benefits.plans", "value": "{{ available_plans }}"},
      {"key": "branches.benefits.effectiveDate", "value": "{{ effective_date }}"},
      {"key": "branches.benefits.completed", "value": "true"}
    ]
  }
}
```

**Aggregator Agent (Fan-In Node):**

```javascript
{
  "id": "agent_aggregator",
  "type": "agent",
  "data": {
    "model": "claude-sonnet-4-5-20250929",
    "temperature": 0.3,
    "systemPrompt": `You are the onboarding decision aggregator.

INPUT: Read from $flow.state.branches.*
- branches.backgroundCheck.* (status, vendor, completed)
- branches.i9.* (status, documents, expiration, completed)
- branches.benefits.* (eligible, plans, effectiveDate, completed)
- branches.itProvisioning.* (status, systems, completed)

LOGIC:
1. Verify all branches.*.completed = true
2. Check for any FAIL/FLAG statuses
3. If all CLEAR → decision = APPROVED, readyToHire = true
4. If any FLAG/FAIL → decision = REVIEW_REQUIRED, readyToHire = false

OUTPUT: Write to $flow.state.aggregate.*`,
    "agentStateUpdates": [
      {"key": "aggregate.decision", "value": "{{ decision }}"},
      {"key": "aggregate.readyToHire", "value": "{{ ready }}"},
      {"key": "aggregate.blockers", "value": "{{ blockers }}"}
    ]
  }
}
```

### Edge Configuration (Fan-Out/Fan-In)

```javascript
// Fan-Out: Start → All Branches
{"source": "start_node", "target": "agent_background_check"},
{"source": "start_node", "target": "agent_i9"},
{"source": "start_node", "target": "agent_benefits"},
{"source": "start_node", "target": "agent_it_provisioning"},

// Fan-In: All Branches → Aggregator
{"source": "agent_background_check", "target": "agent_aggregator"},
{"source": "agent_i9", "target": "agent_aggregator"},
{"source": "agent_benefits", "target": "agent_aggregator"},
{"source": "agent_it_provisioning", "target": "agent_aggregator"}
```

---

## The Aggregation Challenge: Merging Intelligence

The **Aggregator** is the most critical node in a Parallel workflow. It must:

1. **Wait for Completion**: Check all `branches.*.completed` flags
2. **Deduplicate**: Remove redundant information across branches
3. **Resolve Conflicts**: Handle contradictions (e.g., one source says approved, another says rejected)
4. **Prioritize**: Rank by source reliability (verified data > scraped data)
5. **Synthesize**: Create unified summary

### Aggregation Strategies

**Strategy 1: Unanimous Consent**
```javascript
// All branches must agree
if (branches.*.status === "APPROVED") {
  aggregate.decision = "APPROVED"
} else {
  aggregate.decision = "REJECTED"
}
```

**Strategy 2: Weighted Voting**
```javascript
// Weight by reliability
const score =
  (branches.backgroundCheck.status === "CLEAR" ? 3 : 0) +  // highest weight
  (branches.i9.status === "VERIFIED" ? 2 : 0) +
  (branches.benefits.eligible ? 1 : 0)

if (score >= 5) aggregate.decision = "APPROVED"
```

**Strategy 3: Conflict Resolution**
```javascript
// Policy check failed but others passed → flag for review
if (branches.policyCheck.compliant === false) {
  aggregate.decision = "FLAG_FOR_REVIEW"
  aggregate.reason = branches.policyCheck.violations
} else if (allOthersPassed) {
  aggregate.decision = "AUTO_APPROVE"
}
```

---

## The Reality Check: AgentFlow V2 Limitation

**Full Transparency:** There's a known issue in AgentFlow V2.

### Expected Behavior:
Multiple LLM nodes arranged in parallel should execute **concurrently**. Total time ≈ slowest branch.

### Actual Behavior:
Nodes execute **sequentially** (one at a time). Total time = sum of all branches.

**GitHub Issues:**
- [#4673: Parallel Execution Not Working](https://github.com/FlowiseAI/Flowise/issues/4673)
- [#4710: State Contamination Bug](https://github.com/FlowiseAI/Flowise/issues/4710)

### Technical Root Cause:

Current implementation processes nodes one at a time:
```javascript
while (queue.length) {
    const node = queue.shift()  // ONE node at a time
    await executeNode(node)      // Blocks until complete
}
// Missing: await Promise.all([...parallelNodes])
```

Additionally, parallel branches incorrectly inherit chat history from previously executed nodes, causing "data contamination."

### Workaround: Use AgentFlow V1

**AgentFlow V1 (Sequential Agents)** supports true parallel execution via LangGraph:
- Built on LangGraph with proper concurrent branching
- "Sequential Agents can trigger multiple actions in parallel within a single run"
- No state contamination issues

**Recommendation:**
For workflows requiring true parallelism, use **AgentFlow V1** until V2 implementation is fixed.

### Why Learn the Pattern Anyway?

1. **Architectural Thinking**: Understanding Fan-Out/Fan-In is valuable regardless of execution engine
2. **Future-Ready**: V2 will support parallel execution eventually
3. **V1 Works Now**: The pattern is production-ready in V1
4. **Transferable**: This pattern exists in LangGraph, Apache Airflow, AWS Step Functions—it's universal

---

## When to Use Parallel vs. Other Patterns

### The 30-Second Litmus Test

```
Can tasks run simultaneously without dependencies?
  ├─ YES → Are results independent?
  │         ├─ YES → PARALLEL ✓
  │         └─ NO → One task needs output from another?
  │                  └─ YES → CHAINING
  │
  └─ NO → Need branching based on conditions?
            ├─ YES → ROUTING
            └─ NO → Need iterative refinement?
                     └─ YES → ITERATION
```

### Decision Matrix

| Pattern | When to Use | Don't Use If |
|---------|-------------|--------------|
| **Parallel** | Multi-source research, concurrent validations, independent checks | Tasks have dependencies, simple linear logic |
| **Chaining** | Approval workflows, document pipelines, artifact handoffs | Tasks can run simultaneously |
| **Routing** | Intent classification, domain routing, conditional branching | All branches always execute |
| **Iteration** | Quality loops, test-driven refinement, progressive enhancement | Fixed steps, no feedback loop |

### Perfect for Parallel:
- ✅ Multi-source data gathering (web + DB + API)
- ✅ Concurrent validations (compliance + budget + duplicates)
- ✅ Parallel risk checks (credit + fraud + KYC)
- ✅ Multi-language translation (EN → [ES, FR, DE, JA])

### Consider Alternatives:
- ❌ Approval workflows → **Chaining** (can't approve before review)
- ❌ Conditional routing → **Routing** (only run relevant branch)
- ❌ Progressive refinement → **Iteration** (improve until threshold met)

---

## The Over-Parallelization Trap

**Not everything benefits from parallel execution.**

### Anti-Pattern: "Parallel for Parallel's Sake"

**Bad Example:**
```
Start → [Step1] → [Step2] → [Step3] → Aggregator
```

This is just **Chaining with extra steps**. If tasks are truly sequential, keep it simple.

### When Parallel Backfires:

1. **Fake Independence**: Tasks secretly depend on each other
   - *Example:* "Calculate tax" needs "Calculate subtotal" → just chain it

2. **Aggregation Complexity > Time Savings**
   - *Example:* 3 branches save 2 seconds, but aggregation logic takes 5 minutes to build → not worth it

3. **Increased Failure Surface**
   - *Example:* 5 parallel branches = 5 potential failure points → harder to debug

4. **Cost Explosion**
   - *Example:* 10 parallel LLM calls = 10x API cost → only worth it if speed matters

### Rule of Thumb:

**Use Parallel when:**
- Time savings > 30%
- Tasks are genuinely independent
- Aggregation logic is straightforward
- Debugging complexity is acceptable

**Use Chaining when:**
- Dependencies exist
- Total time difference < 2 seconds
- Simplicity > marginal speed gain

---

## Best Practices for Parallel Workflows

### 1. Branch Independence
**Do:** Ensure branches can execute without each other's outputs
```javascript
// Good: Each branch has its own data source
Branch A: Query Workday HCM
Branch B: Query External API
Branch C: Run calculation on Start node input
```

**Don't:** Create hidden dependencies
```javascript
// Bad: Branch B needs Branch A's output
Branch A: Fetch user_id
Branch B: Use user_id to query database  // ❌ Depends on A
```

### 2. Completion Signaling
**Always** set `branches.{name}.completed = true` in state updates:
```javascript
"agentStateUpdates": [
  {"key": "branches.policyCheck.results", "value": "{{ results }}"},
  {"key": "branches.policyCheck.completed", "value": "true"}  // ✓
]
```

Aggregator should check completion before proceeding:
```javascript
if (!branches.policyCheck.completed ||
    !branches.receiptMatch.completed ||
    !branches.budgetCheck.completed) {
  return "Waiting for all branches..."
}
```

### 3. Error Handling Strategies

**Strategy A: Fail-Fast (Strict)**
```javascript
if (branches.backgroundCheck.status === "FAIL") {
  aggregate.decision = "REJECTED"
  aggregate.reason = "Background check failed"
  // Stop processing, no need to check other branches
}
```

**Strategy B: Graceful Degradation (Tolerant)**
```javascript
// Proceed with partial results
aggregate.summary = combineAvailableResults(branches)
aggregate.warnings = branches.filter(b => b.status === "FAIL")
aggregate.confidence = calculateConfidence(branches)  // Lower if some failed
```

**Strategy C: Retry with Fallback**
```javascript
if (!branches.externalAPI.completed) {
  // Retry once
  await retryBranch("externalAPI")

  if (stillFailed) {
    // Fallback to cached data
    branches.externalAPI.results = getCachedData()
    branches.externalAPI.completed = true
    branches.externalAPI.usedFallback = true
  }
}
```

### 4. State Namespacing
**Use clear, consistent naming:**
```javascript
// Good structure
branches.{branchName}.{property}
aggregate.{synthesizedProperty}

// Example
branches.backgroundCheck.status
branches.i9.documents
aggregate.decision
aggregate.readyToHire
```

**Avoid:**
```javascript
// Bad: Flat structure, no namespacing
backgroundCheckStatus  // ❌ Hard to track which branch
i9Docs                 // ❌ Inconsistent naming
finalDecision          // ❌ Ambiguous
```

### 5. Aggregation Anti-Patterns

**❌ Don't: The "Concatenation Dump"**
```javascript
// Just mashing results together
aggregate.summary = branches.web + branches.kb + branches.analysis
```

**✓ Do: Intelligent Synthesis**
```javascript
aggregate.summary = deduplicateAndSynthesize({
  sources: [branches.web, branches.kb, branches.analysis],
  prioritization: ["kb", "analysis", "web"],  // Trust internal sources more
  conflictResolution: "mostRecent"
})
```

---

## Your Action Items: Progressive Complexity

Don't try to build the perfect parallel workflow on day one. Iterate and improve.

### Week 1: Simple 2-Branch Parallel (15 minutes)

**Goal:** Build your first fan-out/fan-in workflow

**Example:** Expense Report – Policy Check + Budget Check

1. Define `$flow.state.branches.policyCheck.*` and `branches.budgetCheck.*`
2. Create 2 agent nodes, both read from Start
3. Each writes `completed = true` when done
4. Aggregator combines results → approve/reject

**Measure:**
- Do both branches update state correctly?
- Does aggregator wait for both `completed` flags?

### Week 2: Add 3rd Branch + Robust Completion Checks (30 minutes)

**Goal:** Scale to 3 branches, handle missing completions

**Example:** Add Receipt Match to expense workflow

1. Add `branches.receiptMatch.*` namespace
2. Update Aggregator prompt to check **all 3** completion flags
3. Add timeout handling (what if one branch hangs?)

**Measure:**
- Test with intentionally failed branch—does aggregator handle gracefully?
- Time difference vs. sequential execution

### Week 3: Advanced Aggregation + Conflict Resolution (1 hour)

**Goal:** Handle contradictions across branches

**Example:** Multi-source research (web says "yes", KB says "no")

1. Implement prioritization logic (internal sources > external)
2. Add conflict detection: flag contradictions in `aggregate.conflicts`
3. Use recency/consensus for resolution

**Measure:**
- Test with intentionally conflicting data
- Verify aggregator surfaces conflicts, doesn't hide them

### Week 4: Error Handling + Partial Failures (1 hour)

**Goal:** Production-ready resilience

**Example:** One branch fails (external API timeout)

1. Add retry logic (1 retry with exponential backoff)
2. Implement fallback (use cached data if API fails)
3. Add `aggregate.warnings` for partial results
4. Set `aggregate.confidence` score (100% if all branches succeed, lower if fallbacks used)

**Measure:**
- Intentionally break one branch—does workflow still complete?
- Is confidence score accurate?
- Are warnings surfaced to user?

---

## The Bottom Line

The Parallel pattern is about **recognizing independence** and exploiting it for speed.

When tasks don't depend on each other, running them sequentially isn't just slow—it's architecturally wrong.

In Flowise, parallel execution means:
- **Fan-Out/Fan-In** architecture (one start → many branches → one aggregator)
- **Branch-specific state** (`branches.{name}.*` namespaces)
- **Intelligent aggregation** (deduplication + conflict resolution + synthesis)

Yes, AgentFlow V2 has a known limitation (sequential execution bug). Use V1 for production parallel workflows until the fix lands. But learn the pattern anyway—it's universal across LangGraph, Step Functions, Airflow, and every modern orchestration engine.

When every branch in your parallel workflow is independent, and your aggregator is smart enough to synthesize contradictions, you haven't just built a faster workflow.

You've built **concurrent intelligence**.

That's the difference between waiting in line and working in parallel.

---

## Next Week: Smart Routing

Last week: **Chaining** (sequential, order matters)
This week: **Parallel** (concurrent, independence matters)
Next week: **Routing** (conditional, intent matters)

We'll explore:
- The Routing Litmus Test (when to branch conditionally)
- Intent classification patterns (support vs. sales vs. billing)
- Fallback strategies (default route when intent unclear)
- Human-in-the-loop gates (pause for approval before continuing)

**Preview:**

```
            Start (customer message)
              │
              ▼
        Intent Classifier
              │
     ┌────────┼────────┬────────┐
     ▼        ▼        ▼        ▼
  Billing  Support  Sales   Escalation
   Route    Route   Route     Route
     │        │        │        │
     └────────┴────────┴────────┘
              ▼
      Specialized Response
```

Only **one** route executes. Parallel runs **all** branches. Routing runs **one** branch.

Know the difference. Use the right pattern.

---

## Your Turn

**What Workday process could benefit from parallel execution?**

Drop a comment with your use case:
- HCM (recruiting, onboarding, performance reviews)
- Financials (expense reports, invoice processing, budgeting)
- PSA (project staffing, margin analysis, resource planning)
- Other (procurement, time tracking, benefits)

I'll suggest the optimal branch configuration and aggregation strategy. Let's build something amazing together!

---

**Built with:** [https://flowiseai.com](https://flowiseai.com)
**AgentFlow V2 Docs:** [https://docs.flowiseai.com/using-flowise/agentflowv2](https://docs.flowiseai.com/using-flowise/agentflowv2)
**Templates:** [https://github.com/FlowiseAI/Flowise/tree/main/templates](https://github.com/FlowiseAI/Flowise/tree/main/templates)

#Workday #WorkdayExtend #AI #AgentWorkflows #Automation #LLMOps #Flowise #AgentFlowV2 #MachineLearning #ParallelProcessing #ConcurrentExecution
