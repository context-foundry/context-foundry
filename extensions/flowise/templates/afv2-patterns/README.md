# AgentFlow v2 Pattern Library

**Version:** 2.1
**Last Updated:** 2025-11-05
**Status:** Production Ready

---

## 📋 Overview

This directory contains 9 production-ready **AgentFlow v2 (AFv2)** pattern templates for Flowise. Each template demonstrates a fundamental orchestration pattern for multi-agent workflows.

All templates are:
- ✅ **Validator-passing** (exit code 0)
- ✅ **FLOWISE-STRUCTURE-AUTHORITY compliant**
- ✅ **Pattern #1-14 compliant** (including Pattern #14: Node Type Mismatch)
- ✅ **Self-contained** (agents have inline model/memory config)
- ✅ **Fully documented** (sticky notes with ALL CAPS prefixes)
- ✅ **State-tracked** (agentStateUpdates throughout)
- ✅ **Terminal nodes** (Direct Reply nodes properly end workflows)

---

## 🎯 Pattern Catalog

| # | Pattern | Complexity | Use Case | Key Features |
|---|---------|------------|----------|--------------|
| 1 | **Chaining** | Low | Fixed pipeline | Sequential artifact handoffs, HIL gate |
| 2 | **Parallel** | Medium | Multi-source research | Concurrent execution, aggregation |
| 3 | **Routing** | Medium | Intent classification | Confidence-based routing, FAIL path |
| 4 | **Iteration** | High | Quality refinement | Loop-back edge, scoring, convergence |
| 5 | **Looping** | High | Validation retry | Test-driven, 3-path gate (PASS/FIX/FAIL) |
| 6 | **Hierarchy** | Very High | Task delegation | Role-based, step iterator, supervisor |
| 7 | **Batch Processing** | Medium | Array processing | Iteration Node, for-each loops, aggregation |
| 8 | **Conditional Retry** | High | Score-based validation | Condition Node, deterministic threshold, retry loop |
| 9 | **API Integration** | Medium | External API calls | HTTP Request Node, status routing, error handling |

---

## 🧩 Node Types Available

All patterns use these **8 core node types** from Flowise AgentFlow v2:

| Node Type | Purpose | Color | Used In Patterns |
|-----------|---------|-------|------------------|
| **Start** | Entry point (chat/form input) | Green `#7EE787` | All patterns |
| **Agent** | Autonomous reasoning with tools | Teal `#4DD0E1` | All patterns |
| **Condition Agent** | AI-driven intent routing | Pink `#ff8fab` | Routing, Iteration, Looping, Hierarchy |
| **Human Input (HIL)** | Pause for approval/feedback | Yellow `#FFD700` | Chaining |
| **Direct Reply** | Terminal message to user | Turquoise `#4DDBBB` | All patterns ⭐ NEW |
| **Sticky Note** | Documentation annotations | Yellow `#fee440` | All patterns |
| **Condition** (deterministic) | If/else logic branching | Orange `#FFB938` | *Available, not yet used* |
| **Iteration** | For-each array loops | Purple `#9C89B8` | *Available, not yet used* |

### Additional Templates Available

These node templates are ready to use in custom flows:

- **CONDITION-NODE-TEMPLATE.json** - Deterministic if/else (equals, contains, greaterThan, isEmpty, etc.)
- **ITERATION-NODE-TEMPLATE.json** - For-each loops over arrays
- **LOOP-NODE-TEMPLATE.json** - While-loop style iteration
- **EXECUTEFLOW-NODE-TEMPLATE.json** - Sub-flow composition

See `/extensions/flowise/prompts/` for complete template files.

---

## 📂 Template Files

```
/templates/afv2-patterns/
├── 01-chaining.json          # Sequential 3-agent chain with HIL gate
├── 02-parallel.json          # 3-branch parallel + aggregation
├── 03-routing.json           # 4-path intent router (Billing/Tech/General/FAIL)
├── 04-iteration.json         # Quality loop with scoring (max 3 iterations)
├── 05-looping.json           # Validation retry loop (max 3 retries)
├── 06-hierarchy.json         # Supervisor → Worker → Reviewer orchestration
├── 07-batch-processing.json  # Iteration Node for-each array processing
├── 08-conditional-retry.json # Score-based retry with Condition Node threshold
├── 09-api-integration.json   # HTTP Request + status code routing
└── README.md                 # This file
```

---

## 🚀 Quick Start

### Import into Flowise:
1. Open Flowise UI
2. Go to **Agentflows** → **Add New**
3. Click **Load Agentflow**
4. Select template JSON (e.g., `01-chaining.json`)
5. Customize agents for your use case
6. Test with Chat input

### Validation:
```bash
cd /Users/name/homelab/context-foundry/extensions/flowise
python3 validate_workflow.py templates/afv2-patterns/01-chaining.json
```

---

## 📖 Pattern Details

### 1️⃣ Chaining Pattern (`01-chaining.json`)

**Description:** Linear 3-step sequential processing pipeline.

**Flow:** Start → Chain1 → HIL Gate → Chain2 → Chain3 → Report → **Direct Reply**

**Key Components:**
- **Nodes:** 10 total (1 Start, 4 Agents, 1 HIL, 1 Direct Reply, 3 Sticky Notes)
- **Edges:** 6 connections
- **HIL Gate:** Approval before Chain2 (write-capable tools)
- **Terminal Node:** Direct Reply sends final message and ends workflow
- **State Updates:** `artifacts.artifact_1/2/final_draft`, `chain.step`

**Use Cases:**
- Document processing pipelines (OCR → Extract → Transform → Format)
- Data transformation workflows (Raw → Clean → Enrich → Publish)
- Sequential approval workflows

**Sticky Notes:**
- PURPOSE: 3-stage sequential processing
- CHAIN LOGIC: Strict sequential execution with HIL
- OUTPUT FORMAT: Final artifact + execution metrics

**Customization:**
- Add/remove chain steps
- Adjust HIL gate threshold
- Change artifact schema

---

### 2️⃣ Parallel Pattern (`02-parallel.json`)

**Description:** Multi-source information gathering with conflict resolution.

**Flow:** Start → [Web Search || KB || Analyzer] → Aggregator → Report

**Key Components:**
- **Parallel Branches:** Web Search, Knowledge Base, Analyzer (3 concurrent)
- **Aggregator:** Deduplication, conflict resolution
- **Built-in Tools:** Web Search uses `web_search_20250305`

**Use Cases:**
- Research synthesis (multiple sources)
- Competitive analysis (web + internal data)
- Risk assessment (parallel checks)

**Sticky Notes:**
- PURPOSE: Multi-source parallel gathering
- PARALLEL EXECUTION: All 3 branches run concurrently
- AGGREGATION: Conflict resolution and deduplication
- OUTPUT FORMAT: Citations organized by source

**Customization:**
- Add/remove branches
- Change aggregation algorithm
- Add partial failure handling

---

### 3️⃣ Routing Pattern (`03-routing.json`)

**Description:** Intent-based routing to domain-specific agents.

**Flow:** Start → Router → [Billing | Technical | General | FAIL] → Synthesize

**Key Components:**
- **Router:** Condition agent with 0.6 confidence threshold
- **Domains:** Billing, Technical, General, FAIL (4 paths)
- **Metadata Tracking:** Confidence scores, alternate routes

**Use Cases:**
- Customer support routing
- Ticketing systems
- Multi-domain chatbots

**Sticky Notes:**
- PURPOSE: Intent-based domain routing
- ROUTING LOGIC: 0.6 threshold, FAIL for invalid input
- OUTPUT FORMAT: Response + routing metadata

**Customization:**
- Add/remove domains
- Adjust confidence threshold
- Change classification keywords

---

### 4️⃣ Iteration Pattern (`04-iteration.json`)

**Description:** Iterative quality improvement loop toward target score.

**Flow:** Start → Planner → Gate → Research → [loop back to Gate] → Report

**Key Components:**
- **Loop-back Edge:** Research → Gate (animated, critical)
- **Scoring:** 0.0-1.0 scale, target 0.85
- **Max Iterations:** 3 (configurable)
- **Convergence:** Early exit if score ≥ target

**Use Cases:**
- Content refinement (iterate until quality threshold)
- Code optimization (improve until performance target)
- Data quality improvement

**Sticky Notes:**
- PURPOSE: Quality-driven iteration loop
- ITERATION LOGIC: Score < target AND iter < max → CONTINUE
- SCORING: Rubric-based evaluation (0.0-1.0)
- OUTPUT FORMAT: Final artifact + iteration history

**Customization:**
- Change target score (default 0.85)
- Adjust max iterations (default 3)
- Modify scoring rubric

---

### 5️⃣ Looping Pattern (`05-looping.json`)

**Description:** Validation-driven retry loop with automated testing.

**Flow:** Start → Generate → Validate → Gate → [PASS → Return | FIX → Fix Plan → loop back | FAIL → Return]

**Key Components:**
- **Loop-back Edge:** Fix Plan → Generate (animated, critical)
- **3-Path Gate:** PASS, FIX, FAIL (not just binary)
- **FAIL Path:** Prevents returning broken code after max retries
- **Max Retries:** 3 (configurable)

**Use Cases:**
- Test-driven development (generate → test → fix loop)
- Policy compliance checking
- Automated code review with fixes

**Sticky Notes:**
- PURPOSE: Validation retry with automated fixes
- VALIDATION LOGIC: Tests pass → PASS, fail + retries → FIX, fail + no retries → FAIL
- RETRY LOGIC: Increment counter, generate fixes
- OUTPUT FORMAT: Status (PASS/FAIL) + retry history

**Customization:**
- Change max retries (default 3)
- Customize validator (tests, linting, policy)
- Add retry strategy (exponential backoff)

---

### 6️⃣ Hierarchy Pattern (`06-hierarchy.json`)

**Description:** Supervisor-orchestrated task delegation to specialist roles.

**Flow:** Start → Supervisor → Checker → [Worker → Reviewer → loop back to Checker] → Final

**Key Components:**
- **Loop-back Edge:** Reviewer → Checker (animated, critical)
- **Step Iterator:** `hierarchy.current_step` incremented by Reviewer
- **Roles:** Software Engineer (Worker), Code Reviewer (Reviewer)
- **Role ACLs:** Different tools per role

**Use Cases:**
- Software development workflows (planning → coding → review)
- Content creation (research → write → edit)
- Project management (delegate → execute → validate)

**Sticky Notes:**
- PURPOSE: Hierarchical task orchestration
- DELEGATION: Supervisor creates task graph, assigns roles
- REVIEW GATES: Reviewer validates, increments step
- OUTPUT FORMAT: Composed output + per-role metrics

**Customization:**
- Add/remove roles
- Change role ACLs (tools)
- Modify review criteria

---

### 7️⃣ Batch Processing Pattern (`07-batch-processing.json`)

**Description:** For-each iteration over arrays with aggregation.

**Flow:** Start → Planner → Iteration Node → [Processor Agent (N times)] → Aggregator → Direct Reply

**Key Components:**
- **Nodes:** 9 total (1 Start, 3 Agents, 1 Iteration Node, 1 Direct Reply, 3 Sticky Notes)
- **Edges:** 5 connections
- **Iteration Node:** For-each loop over input array
- **Processor Agent:** Executes once per item in array
- **Aggregator Agent:** Combines results from all iterations

**Use Cases:**
- Sentiment analysis on multiple reviews
- Batch document processing (OCR, extraction, classification)
- Multi-item quality checks (validate N files)
- Parallel data transformation pipelines

**Sticky Notes:**
- PURPOSE: Batch array processing with aggregation
- ITERATION LOGIC: For-each over array, process each item
- AGGREGATION: Combine results from all iterations
- OUTPUT FORMAT: Array of results + summary statistics

**Customization:**
- Change array source (user input, API response, database query)
- Modify processor logic (analysis, transformation, validation)
- Adjust aggregation strategy (sum, average, deduplicate)

---

### 8️⃣ Conditional Retry Pattern (`08-conditional-retry.json`)

**Description:** Score-based validation with deterministic threshold check and retry loop.

**Flow:** Start → Generator → Validator → Condition Node (score check) → [PASS → Success Agent → Direct Reply | RETRY → Retry Controller → loop back to Generator | FAIL → Fail Agent → Direct Reply]

**Key Components:**
- **Nodes:** 11 total (1 Start, 4 Agents, 1 Condition Node, 1 Condition Agent, 2 Direct Reply, 3 Sticky Notes)
- **Edges:** 9 connections
- **Condition Node:** Deterministic score threshold check (no LLM cost)
- **Condition Agent (Retry Controller):** LLM-based retry decision (Haiku model for cost optimization)
- **Loop-back Edge:** Retry Controller → Generator (animated, critical)
- **Max Retries:** 3 (configurable)
- **Dual Terminal Paths:** Success and Fail Direct Reply nodes

**Use Cases:**
- Content quality validation with iterative improvement
- Code generation with automated testing
- Data validation with auto-correction
- Compliance checking with remediation

**Sticky Notes:**
- PURPOSE: Score-based validation with retry logic
- CONDITION LOGIC: Score ≥ threshold → PASS, < threshold → RETRY/FAIL
- RETRY STRATEGY: Max 3 retries, LLM decides retry approach
- OUTPUT FORMAT: Final output + validation history + retry count

**Customization:**
- Change score threshold (default 0.85)
- Adjust max retries (default 3)
- Modify scoring rubric (different quality criteria)
- Use different models for retry controller (Haiku for cost, Sonnet for quality)

---

### 9️⃣ API Integration Pattern (`09-api-integration.json`)

**Description:** External HTTP API integration with status code routing and error handling.

**Flow:** Start → Parameter Extractor → HTTP Request Node → Condition Node (status check) → [SUCCESS (200) → Format Agent → Direct Reply | ERROR (5xx) → Retry Agent → loop back to HTTP | FATAL (4xx) → Error Handler → Direct Reply]

**Key Components:**
- **Nodes:** 10 total (1 Start, 4 Agents, 1 HTTP Request Node, 1 Condition Node, 2 Direct Reply, 2 Sticky Notes)
- **Edges:** 9 connections
- **HTTP Request Node:** Makes external API calls
- **Condition Node:** Routes based on HTTP status code (200/4xx/5xx)
- **Loop-back Edge:** Retry Agent → HTTP Request (animated, critical)
- **Max Retries:** 3 with exponential backoff
- **Triple Exit Paths:** Success, Error (retryable), Fatal (non-retryable)

**Use Cases:**
- Third-party API integration (payment, weather, geocoding)
- Webhook processing with retry logic
- Data enrichment from external sources
- Service composition (orchestrating multiple APIs)

**Sticky Notes:**
- PURPOSE: External API integration with error handling
- HTTP ROUTING: 200 → SUCCESS, 5xx → RETRY, 4xx → FATAL
- RETRY LOGIC: Exponential backoff, max 3 retries
- OUTPUT FORMAT: API response + status metadata + retry history

**Customization:**
- Change API endpoint and headers
- Adjust status code routing logic (add 3xx redirects)
- Modify retry strategy (exponential backoff parameters)
- Add authentication (API keys, OAuth tokens)

---

## 🔧 Configuration Standards

All templates use:

| Setting | Value | Notes |
|---------|-------|-------|
| **Model** | `claude-sonnet-4-5-20250929` | Latest Claude Sonnet |
| **Credential** | `"Anthropic API Key"` | Flowise credential label |
| **Temperature** | 0.1-0.4 | Routers: 0.1, Agents: 0.2-0.4 |
| **Tools** | `currentDateTime`, `calculator`, `searXNG` | Valid Flowise tools |
| **Tool Structure** | Nested `agentSelectedToolConfig` | Required per Pattern #6 |
| **agentMessages** | `""` (empty string) | Per FLOWISE-STRUCTURE-AUTHORITY |
| **Memory** | `agentEnableMemory: true` | All agents have memory |
| **START Node** | Chat input | Easier to test than Form |

---

## 📐 State Schema Conventions

All templates use dot notation for state keys:

| Pattern | State Keys |
|---------|----------|
| **Chaining** | `artifacts.artifact_1/2/final_draft`, `chain.step` |
| **Parallel** | `branches.web/kb/analysis.results`, `aggregate.summary` |
| **Routing** | `domain.response/name`, `route.chosen/confidence` |
| **Iteration** | `iteration.current/max/score/target`, `iteration.artifact` |
| **Looping** | `candidate.output`, `loop.retry_count`, `validation.pass/reasons` |
| **Hierarchy** | `plan.steps[]`, `hierarchy.current_step`, `worker_outputs` |
| **Batch Processing** | `batch.items[]`, `batch.current_index`, `batch.results[]` |
| **Conditional Retry** | `retry.count`, `validation.score`, `retry.history[]` |
| **API Integration** | `api.request`, `api.response`, `api.status_code`, `api.retry_count` |

---

## ✅ Validation Checklist

Before deploying templates:

- [ ] Run `validate_workflow.py` (exit code 0)
- [ ] All `agentMessages` are empty strings `""`
- [ ] All tools have `agentSelectedToolConfig` nested object
- [ ] HIL gates have 5 inputParams (if present)
- [ ] Condition nodes have matching scenarios/edges
- [ ] Loop-back edges are marked `animated: true`
- [ ] Sticky notes use ALL CAPS prefixes
- [ ] Output anchors follow format: `{nodeId}-output-{nodeName}`

---

## 🎨 Customization Guide

### Adding Agents:
1. Copy existing agent node
2. Update `id`, `label`, `position`
3. Set `agentMessages: ""`
4. Configure tools with `agentSelectedToolConfig`
5. Add `agentStateUpdates` for tracking

### Modifying Loop Logic:
1. Identify loop-back edge (e.g., `research → gate`)
2. Ensure counter increment in `agentStateUpdates`
3. Update condition gate logic
4. Mark edge as `"animated": true`

### Changing Models:
Replace all instances of:
```json
"modelName": "claude-sonnet-4-5-20250929"
```
With your desired model (e.g., `"gpt-4o"`)

### Adding Sticky Notes:
```json
{
  "id": "stickyNote_custom",
  "type": "stickyNote",
  "position": { "x": 100, "y": 50 },
  "data": {
    "inputs": {
      "note": "ALL CAPS PREFIX:\nYour note content here."
    },
    "color": "#fee440"
  }
}
```

---

## 🐛 Troubleshooting

### Template won't import:
- Check JSON validity (`python3 -m json.tool template.json`)
- Run validator: `python3 validate_workflow.py template.json`

### Missing icons or sync problems (Pattern #14):
- ✅ **Check node types** - Must use EXACT types from NODE_TYPE_REGISTRY.md
- ❌ **Common mistake:** Using "ConditionNode" instead of "ConditionAgent" or "Condition"
- ❌ **Common mistake:** Using "StartFlow" instead of "Start"
- ❌ **Common mistake:** Using "directReply" (lowercase) instead of "DirectReply"
- 🔧 **Fix:** Copy node structure from template files, don't manually type
- 🔍 **Detect:** Run `python3 validate_workflow.py` - Pattern #14 check will catch all mismatches

### Blank screen when clicking HIL node:
- HIL node must have exactly 5 inputParams (Pattern #11)
- Include: `humanInputModel` and `humanInputModelPrompt` (even if hidden)

### Agent not executing:
- Check `agentMessages` is empty string `""` (not array)
- Verify tools have `agentSelectedToolConfig` nested object

### Loop not iterating:
- Ensure loop-back edge exists (e.g., `research → gate`)
- Check counter increment in `agentStateUpdates`
- Verify condition gate has proper logic

---

## 📚 References

- **FLOWISE-STRUCTURE-AUTHORITY.md** - Canonical JSON structure guide
- **AGENT_PATTERN_REFERENCE.md** - Complete AFv2 schema documentation
- **FAILURE_PATTERNS.md** - 14 documented failure patterns + prevention (including Pattern #14: Node Type Mismatch)
- **NODE_TYPE_REGISTRY.md** - Authoritative node type reference (Pattern #14 prevention)
- **HIL-NODE-TEMPLATE.json** - Human-in-the-Loop node reference

---

## 🤝 Contributing

To add new patterns:

1. Follow existing template structure
2. Include 4+ sticky notes with ALL CAPS prefixes
3. Use proper tool structure (`agentSelectedToolConfig`)
4. Set `agentMessages: ""`
5. Run `validate_workflow.py` (must pass)
6. Document in this README

---

## 📝 License

Part of Context Foundry Flowise Extension
© 2025 Context Foundry

---

## 🔗 Quick Links

- [Flowise Documentation](https://docs.flowiseai.com/)
- [Claude API Documentation](https://docs.anthropic.com/)
- [Context Foundry](https://github.com/context-foundry)

---

**Version History:**
- **2.1** (2025-11-05): Added 3 new patterns (Batch Processing, Conditional Retry, API Integration) - total 9 patterns
- **2.0** (2025-11-05): Initial release with 6 production-ready patterns
