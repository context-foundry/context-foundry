# Best Practices - Flowise Agent Builder

**Guidelines for optimal results and high-quality Flowise workflows**

---

## Writing Effective Prompts

### ✅ Do's

1. **Include "Flowise" explicitly**
   ```
   ✅ "Build a Flowise customer service multi-agent flow"
   ❌ "Build a customer service system"
   ```

2. **List all integrations by name**
   ```
   ✅ "...integrating with Shopify, Stripe, Twilio, and SendGrid"
   ❌ "...with e-commerce and payment integration"
   ```

3. **Specify agent domains clearly**
   ```
   ✅ "...with agents for inventory, orders, shipping, and returns"
   ❌ "...with agents for e-commerce stuff"
   ```

4. **Mention knowledge sources if needed**
   ```
   ✅ "...with knowledge base for product documentation and troubleshooting guides"
   ❌ "...with some documentation"
   ```

5. **Use industry-standard terms**
   ```
   ✅ "CRM", "EHR", "MES", "SCM"
   ✅ "OAuth 2.0", "API Key", "Bearer Token"
   ```

6. **Be specific about complexity**
   ```
   ✅ "Build a comprehensive workflow with 8-10 specialized agents..."
   ❌ "Build a big system..."
   ```

7. **Mention compliance requirements**
   ```
   ✅ "...with HIPAA compliance for healthcare data"
   ✅ "...with PCI DSS compliance for payment processing"
   ```

8. **Specify agent count if you have a preference**
   ```
   ✅ "...with 5 agents: intake, processing, validation, approval, and general"
   ```

### ❌ Don'ts

1. **Don't be vague**
   ```
   ❌ "Build a business system"
   ❌ "Make an agent flow"
   ```

2. **Don't mix unrelated domains**
   ```
   ❌ "Build a flow for healthcare, e-commerce, and manufacturing"
   ✅ Split into 3 separate flows
   ```

3. **Don't omit "Flowise" keyword**
   ```
   ❌ "Create a multi-agent workflow"
   ✅ "Create a Flowise multi-agent workflow"
   ```

4. **Don't request features Flowise doesn't support**
   ```
   ❌ "...with real-time video processing"
   ❌ "...with blockchain integration"
   ```

5. **Don't specify exact JSON structure**
   ```
   ❌ "Create a node with ID agentAgentflow_23..."
   ✅ Let the builder follow authoritative patterns
   ```

6. **Don't go over 12 agents**
   ```
   ❌ "Build a flow with 20 specialized agents..."
   ✅ "Build a flow with 8-10 agents..." (optimal)
   ```

7. **Don't request multiple flow types in one**
   ```
   ❌ "Build a flow that's both multi-agent AND sequential..."
   ✅ Choose one primary pattern
   ```

8. **Don't forget authentication requirements**
   ```
   ❌ "...integrate with Salesforce"
   ✅ "...integrate with Salesforce (OAuth 2.0)"
   ```

---

## 🏆 Production Success Example

### Promotion Nomination Workflow - Best Practices in Action

**[View Full Documentation →](./SUCCESS_PROMOTION_NOMINATION.md)**

This real enterprise build (Nov 4, 2025) demonstrates all best practices working together:

**The Prompt** (following all Do's):
```
Build a Flowise promotion nomination multi-agent workflow with manager-driven nominations,
on-behalf-of support, two-stage approval process with human-in-the-loop gates, bulk
decision capability, and complete Workday HCM integration
```

**Why This Prompt Worked**:
1. ✅ Included "Flowise" explicitly
2. ✅ Listed specific features (manager-driven, OBO, approval gates, bulk decisions)
3. ✅ Specified integration by name (Workday HCM)
4. ✅ Clear complexity indication (multi-stage, HIL gates, bulk operations)
5. ✅ Industry-standard terminology (OBO, two-stage approval, HIL)
6. ✅ Focused on single domain (HR promotion nominations)

**Results**:
- **Build Time**: 25 minutes (first-try success)
- **Complexity**: 11 nodes (7 agents + 2 HIL gates)
- **Test Iterations**: 1 (100% pass rate)
- **Pattern Prevention**: 9/9 patterns prevented
- **Production Readiness**: 95% out of the box

**Key Success Factors**:

1. **Clear Feature Requirements**
   - Manager-driven: ✅ Form input with detailed fields
   - OBO support: ✅ Dedicated agent with routing
   - Two-stage approval: ✅ HIL gates at each stage
   - Bulk decisions: ✅ Specialized agent for bulk operations

2. **Specific Integration**
   - Named system: Workday HCM
   - Integration points defined: Employee lookup, business process routing
   - Result: Complete INTEGRATION_GUIDE.md with API endpoints

3. **Complex Workflow Elements**
   - HIL gates: First successful implementation with semantic outputs
   - Multi-path routing: Proceed/reject branches wired correctly
   - State management: Complete nomination lifecycle tracked

4. **Real-World Use Case**
   - Enterprise HR process (not theoretical)
   - Production-ready audit trail
   - Compliance considerations built-in

**What Made This Build Special**:
- First successful Human-in-the-Loop gates
- Most complex workflow built to date
- Complete enterprise integration guide
- Real production use case

**Lessons for Your Prompts**:
- Be specific about workflow stages ("two-stage approval")
- Name advanced features explicitly ("human-in-the-loop gates")
- Specify business operations ("bulk decision capability")
- Name actual systems ("Workday HCM" not "HR system")
- Focus on one clear domain (promotion nominations)

**Template for Similar Prompts**:
```
Build a Flowise [DOMAIN] workflow with [FEATURE_1], [FEATURE_2], [FEATURE_3],
[ADVANCED_PATTERN], and complete [SYSTEM_NAME] integration
```

Where:
- `[DOMAIN]` = Specific business process (not vague category)
- `[FEATURE_1-3]` = Core capabilities needed
- `[ADVANCED_PATTERN]` = HIL gates, ExecuteFlow, complex routing, etc.
- `[SYSTEM_NAME]` = Actual third-party system (Workday, Salesforce, SAP, etc.)

---

## Agent Count Guidelines

### Simple (3-5 agents)

**When to use**:
- Single-domain workflows (customer support, IT helpdesk)
- Clear, distinct responsibilities
- Limited integrations (1-2 APIs)
- Quick turnaround needed

**Examples**:
- Customer support: Technical, Billing, General
- IT helpdesk: Password, Software, Hardware
- HR onboarding: Benefits, Paperwork, Orientation

**Expected build time**: 10-15 minutes

**Characteristics**:
- ✅ Fast builds
- ✅ Easy to understand
- ✅ Simple testing
- ❌ Limited flexibility
- ❌ May need expansion later

### Moderate (5-8 agents)

**When to use**:
- Multi-domain workflows (e-commerce, real estate)
- Multiple integrations (3-5 APIs)
- Balanced complexity and capability
- **RECOMMENDED FOR MOST PROJECTS**

**Examples**:
- E-commerce: Inventory, Orders, Shipping, Returns, Customer Service, Analytics
- Real estate: Property Search, Leads, Documents, Showings, Financing
- Healthcare: Scheduling, Insurance, Medical History, Compliance, Forms

**Expected build time**: 15-25 minutes

**Characteristics**:
- ✅ Good balance of features and complexity
- ✅ Handles most use cases
- ✅ Room for growth
- ✅ Manageable testing
- ❌ Slightly longer build time

### Complex (8+ agents)

**When to use**:
- Enterprise-scale workflows (warehouse ops, manufacturing)
- Many integrations (5+ APIs)
- Comprehensive coverage needed
- Production systems with high requirements

**Examples**:
- Warehouse operations: Inventory, Orders, HR, Equipment, Reporting, Integration, Safety, General
- Manufacturing QC: Defect Detection, Process Optimization, Supplier Management, Compliance, Scheduling
- Supply chain: Procurement, Logistics, Vendor Management, Demand Forecasting, Analytics

**Expected build time**: 20-30 minutes

**Characteristics**:
- ✅ Comprehensive coverage
- ✅ Feature-complete
- ✅ Handles complex scenarios
- ❌ Longer build time
- ❌ More complex testing
- ❌ Higher maintenance

**⚠️ Warning**: Going beyond 12 agents has diminishing returns. Consider splitting into multiple flows.

---

## Tool Configuration Best Practices

### ✅ Standard Tools (Auto-Included with Correct Structure)

**All Flowise agents now include 2 standard tools automatically with CORRECT Flowise UI JSON structure:**

Generated workflows have **populated tool arrays** with exact structure:
```json
"agentTools": [
  {
    "agentSelectedTool": "currentDateTime",
    "agentSelectedToolRequiresHumanInput": "",
    "agentSelectedToolConfig": {
      "agentSelectedTool": "currentDateTime"
    }
  },
  {
    "agentSelectedTool": "searXNG",  // CRITICAL: capital X, capital NG
    "agentSelectedToolRequiresHumanInput": "",  // CRITICAL: empty string, not boolean
    "agentSelectedToolConfig": {
      "apiBase": "https://s.llam.ai",  // CRITICAL: apiBase, not baseUrl
      "toolName": "searxng-search",
      "toolDescription": "Federated web/meta search...",
      // ... all required fields
    }
  }
]
```

**Why this works now?**
- Fixed Pattern #6: ROOT CAUSE was wrong JSON structure, NOT missing tools
- We were using "baseUrl" instead of "apiBase"
- We were using "searxng-search" instead of "searXNG"
- We were using `false` (boolean) instead of `""` (empty string)
- Now using EXACT structure from Flowise UI exports

**No manual setup required** - tools work immediately upon import!

### Pattern #6 Learning: Incorrect Tool JSON Structure

**What we initially thought** (WRONG):
- Tools must be created in Flowise UI first
- Can't auto-include tools in generated workflows

**What we discovered** (CORRECT):
- Tools ARE built-in to Flowise (currentDateTime, searXNG)
- Problem was we used WRONG field names and data types
- Fixed by copying exact structure from Flowise UI export

**Key fields that were wrong**:
- Tool name: "searxng-search" → "searXNG"
- Field: "baseUrl" → "apiBase"
- Type: `false` → `""`

### Standard Tool Capabilities (Auto-Included)

#### 1. CurrentDateTime
- **Purpose**: Provides current date and time for temporal context
- **Why**: Helps agents evaluate if search results and information are current
- **Example Use**: "Is this news article from today or last year?"
- **Auto-Included**: ✅ Yes, in all generated workflows

#### 2. SearXNG Search
- **Base URL**: https://s.llam.ai
- **Purpose**: Federated meta-search across multiple search engines
- **Why**: Real-time information retrieval for dynamic queries
- **Example Use**: "What are the latest industry trends?"
- **Auto-Included**: ✅ Yes, in all generated workflows

**Combined Benefit**:
Agents can search for real-time information (SearXNG) and then evaluate its freshness
(CurrentDateTime) to provide contextually aware, temporally accurate responses.

**Import Process** (SIMPLE - tools work immediately):
1. Generate workflow with Context Foundry (tools auto-included with correct structure)
2. Import JSON to Flowise
3. Test workflow - tools work immediately, no setup needed!

**Documentation**: See `/extensions/flowise/tool-configs/STANDARD_TOOLS.md` for technical details and field structure.

---

### API Integration

**How to specify in prompts**:
```
✅ "...integrating with Shopify API for inventory and orders"
✅ "...using Stripe API for payment processing"
✅ "...connecting to Salesforce CRM via REST API"
```

**Auth pattern recommendations**:

| Integration Type | Recommended Auth | Example |
|-----------------|------------------|---------|
| E-commerce (Shopify, WooCommerce) | API Key | `X-Shopify-Access-Token` |
| CRM (Salesforce, HubSpot) | OAuth 2.0 | OAuth flow with refresh tokens |
| Payment (Stripe, Square) | API Key + Secret | `Authorization: Bearer sk_test_...` |
| Cloud (AWS, Google Cloud) | Bearer Token | IAM credentials, service accounts |
| Communication (Twilio, SendGrid) | API Key | Account SID + Auth Token |
| Legacy Systems | Basic Auth | Username + Password (over HTTPS) |

**Security best practices**:
1. ✅ Use environment variables for secrets: `STRIPE_API_KEY`
2. ✅ Never commit API keys to git: Include in .env.example, not .env
3. ✅ Use separate keys for dev/staging/production
4. ✅ Rotate keys periodically
5. ✅ Use minimum required permissions (principle of least privilege)

### Custom Tools

**When to create custom tools**:
- ✅ Integration with internal APIs
- ✅ Complex multi-step operations
- ✅ Reusable across multiple agents
- ❌ One-off simple operations (use built-in tools instead)

**Structure guidelines**:
```json
{
  "name": "Clear, descriptive name",
  "description": "What it does, when to use it",
  "auth": {
    "type": "apiKey | oauth2 | bearer | basic",
    "envVar": "ENV_VAR_NAME"
  },
  "operations": [
    {
      "name": "operationName",
      "method": "GET|POST|PUT|DELETE",
      "endpoint": "/api/v1/resource",
      "parameters": {
        "param1": "type (required|optional)",
        "param2": "type (required|optional)"
      }
    }
  ]
}
```

**Naming conventions**:
- ✅ `shopify-inventory-check`
- ✅ `salesforce-lead-create`
- ❌ `tool1`, `api`, `thing`

---

## Knowledge Source Recommendations

### Document Stores

**When to use**:
- ✅ Well-structured documents (PDFs, Word, Markdown)
- ✅ Internal documentation, procedures, policies
- ✅ Content that changes infrequently
- ✅ Documents with clear sections/chapters

**Content types**:
- Company policies and procedures
- Employee handbooks
- Product manuals
- Training materials
- Legal documents
- Standard Operating Procedures (SOPs)

**Organization best practices**:
1. ✅ **Categorize by domain**: HR docs, IT docs, Product docs
2. ✅ **One store per category**: Don't mix HR and IT in same store
3. ✅ **Keep descriptions specific**: "HR policies including time-off, benefits, and code of conduct"
4. ❌ **Don't create one giant store**: Split into focused collections

**Search configuration**:
```json
{
  "topK": 5,              // Return top 5 results (good default)
  "scoreThreshold": 0.7   // Minimum relevance score (0.7 = 70%)
}
```

### Vector Embeddings

**When to use**:
- ✅ Large, unstructured text corpora
- ✅ Content that requires semantic search
- ✅ Frequently updated content
- ✅ Multi-language content

**Content types**:
- Product documentation (technical)
- API references
- Knowledge base articles
- Customer support tickets (historical)
- Research papers
- Code documentation

**Embedding model selection**:

| Model | Best For | Dimensions | Cost |
|-------|----------|------------|------|
| text-embedding-3-small | General purpose, cost-effective | 1536 | $ |
| text-embedding-3-large | Higher quality, larger docs | 3072 | $$$ |
| text-embedding-ada-002 | Legacy, still good | 1536 | $$ |

**Configuration recommendations**:
```json
{
  "topK": 10,                    // More results for semantic search
  "includeMetadata": true,       // Include document source info
  "returnSourceDocuments": true  // Show where info came from
}
```

**Chunking best practices**:
- ✅ **Chunk size**: 1000-1500 characters (good default)
- ✅ **Overlap**: 200-300 characters (maintains context)
- ❌ **Too small** (<500): Loses context
- ❌ **Too large** (>2000): Dilutes relevance

---

## Temperature Settings

### By Agent Type

**Router/Intent Detection (0.1-0.3)**:
```
Purpose: Deterministic routing decisions
Use for: Condition nodes, classification agents
Example: 0.2 for intent router
```
- ✅ Consistent routing
- ✅ Predictable behavior
- ❌ No creativity needed

**Operational/Factual (0.4-0.6)**:
```
Purpose: Accurate information retrieval and processing
Use for: Data lookup, inventory checks, order processing
Example: 0.5 for inventory management agent
```
- ✅ Balanced accuracy and flexibility
- ✅ Handles edge cases
- ❌ Minimal hallucination risk

**Creative/Analytical (0.7-0.9)**:
```
Purpose: Content generation, recommendations
Use for: Marketing copy, product recommendations, analysis
Example: 0.8 for content generation agent
```
- ✅ Creative outputs
- ✅ Varied responses
- ❌ May need validation

### By Use Case

**Deterministic scenarios** (0.1-0.3):
- Payment processing
- Compliance checking
- Data validation
- Security operations

**Standard scenarios** (0.4-0.6):
- Customer support responses
- Information retrieval
- Order processing
- Inventory management

**Creative scenarios** (0.7-0.9):
- Marketing content generation
- Product descriptions
- Recommendations
- Brainstorming

**⚠️ Warning**: Never use temperature >0.9 for production systems (too unpredictable).

---

## Agent Persona Writing

### Effective Patterns

**HTML format** (Flowise standard):
```html
<p><em>You are an expert [ROLE] agent.</em> [CAPABILITIES AND BOUNDARIES]</p>
```

**Structure components**:
1. **Role definition**: "You are an expert X agent"
2. **Capabilities**: What you CAN do
3. **Boundaries**: What you CANNOT do (defer to others)
4. **Tone/style**: How to communicate
5. **Tool/knowledge references**: What resources you have

**Example - Inventory Management Agent**:
```html
<p><em>You are an expert Inventory Management agent.</em> You track stock levels across all warehouse locations, process inventory adjustments, and provide real-time inventory status. You have access to the Shopify Inventory API and can check stock, update quantities, and flag low-stock items. You maintain a professional, data-driven tone and always verify stock levels before making commitments. You do NOT handle order fulfillment or shipping logistics - defer those questions to the Orders and Shipping agents.</p>
```

**Key elements**:
- ✅ Clear role ("Inventory Management agent")
- ✅ Specific capabilities ("track stock", "process adjustments")
- ✅ Tool mention ("Shopify Inventory API")
- ✅ Explicit boundaries ("do NOT handle order fulfillment")
- ✅ Tone guidance ("professional, data-driven")

### Common Mistakes

❌ **Too broad**:
```html
<p>You are a helpful agent. You can help with anything related to the business.</p>
```
Problem: No boundaries, overlaps with other agents

❌ **Unclear boundaries**:
```html
<p>You handle customer inquiries and maybe some order stuff.</p>
```
Problem: "Maybe" is vague - other agents won't know when to defer

❌ **Missing context**:
```html
<p>You are a billing agent.</p>
```
Problem: No capabilities listed, no tool references, no tone guidance

❌ **No tool references**:
```html
<p>You manage payments and process refunds.</p>
```
Problem: Doesn't mention Stripe API access, agent may not know it can actually process refunds

✅ **Good persona** (all elements present):
```html
<p><em>You are an expert Billing Support agent.</em> You handle billing inquiries, payment issues, refund requests, and subscription changes. You have access to the Stripe Payment API and can view charges, process refunds up to $500, and update payment methods. You maintain a patient, empathetic tone when discussing billing issues. You escalate refund requests over $500 to management. You do NOT handle product support or technical issues - defer those to the Technical Support agent.</p>
```

---

## Routing Scenario Design

### Keyword Mapping

**Effective scenarios**:
```json
{
  "scenario": "User is asking about inventory, stock levels, availability, or product quantities"
}
```

**What makes this good**:
- ✅ Multiple related keywords
- ✅ Natural language variations
- ✅ Clear intent

**Poor scenarios**:
```json
{
  "scenario": "inventory"
}
```
Problem: Too vague, single keyword

**Best practices**:
1. ✅ List 3-5 related keywords per scenario
2. ✅ Include variations ("help desk" vs "helpdesk")
3. ✅ Use natural language ("asking about" not just "inventory")
4. ✅ Be specific about intent
5. ❌ Don't overlap scenarios

### Keyword Conflict Resolution

**Problem:** Keywords that could match multiple scenarios cause routing ambiguity.

#### Strategy 1: Specificity Hierarchy

Make scenarios more specific to avoid overlap:

**Before (Overlapping):**
```json
{
  "scenario": "Questions about time"  // Too vague
}
{
  "scenario": "Questions about payroll"  // Could include time-related questions
}
```

**After (Specific):**
```json
{
  "scenario": "Questions about time off, PTO, vacation, leave requests, or time-away balances"
}
{
  "scenario": "Questions about payroll timing, payment dates, pay periods, or paycheck schedules"
}
```

**Result:** "When do I get paid?" clearly routes to Payroll. "When can I take PTO?" routes to Time Off.

---

#### Strategy 2: Negative Keywords

Use exclusion clauses to disambiguate:

```json
{
  "scenario": "Payroll questions about salary, payment, deductions, or withholding (NOT about updating bank account - that's Employee Data)"
}
```

This explicitly tells the router what NOT to route to Payroll, reducing mis-classification.

---

#### Strategy 3: Conditional Routing in Instructions

When keywords overlap, use conditional logic in `conditionAgentInstructions`:

```json
{
  "conditionAgentInstructions": "...

KEYWORD CONFLICT RESOLUTION:

'Payroll' keyword appears in question:
  - If combined with 'bank account', 'routing number', 'direct deposit setup' → Employee Data Agent
  - If combined with 'missing payment', 'pay stub', 'deduction', 'W-2' → Payroll Agent
  - If only 'How do I find payroll?' (navigational) → Navigation Agent

'Time' keyword appears in question:
  - If combined with 'off', 'PTO', 'vacation', 'leave' → Time & Attendance Agent
  - If combined with 'payroll runs', 'payment date', 'when paid' → Payroll Agent
  - If combined with 'submit timesheet', 'clock in' → Time & Attendance Agent

..."
}
```

---

#### Strategy 4: Context-Based Disambiguation

Use surrounding words to determine intent:

**Example: "Address" keyword**

- "Update my address" → Employee Data Agent (data modification)
- "What's the office address?" → General Info/Facilities Agent
- "Email address change" → IT/Systems Agent

**Implementation:**

```json
{
  "conditionAgentInstructions": "...

'Address' disambiguation:
- Personal/home address updates → Employee Data
- Office/facility location → Facilities/General Help
- Email/system address → IT Support

..."
}
```

---

#### Strategy 5: Primary Intent Rule

When a question has multiple valid keywords, route based on PRIMARY intent:

**Question:** "I need to update my address for payroll and benefits"

**Analysis:**
- Keywords match: Employee Data (address update), Payroll, Benefits
- PRIMARY action: Updating address (a data modification)
- SECONDARY effects: Impacts payroll and benefits (but not separate actions)

**Route to:** Employee Data Agent

**Rule:** "When multiple domains detected, route to the agent handling the PRIMARY user action, not peripheral impacts."

---

#### Strategy 6: Priority Order

Define explicit priority when keywords truly conflict:

```json
{
  "conditionAgentInstructions": "...

PRIORITY ORDER FOR OVERLAPPING KEYWORDS:

If a question could match multiple scenarios, use this priority:
1. Security/Access issues (highest priority - always route here first)
2. Data modification actions (updates, changes, corrections)
3. Specialized domain agents (Payroll, Benefits, etc.)
4. Navigation assistance
5. General information (lowest priority - fallback)

Example: 'Update my payroll withholding'
- Matches: Employee Data (update action) AND Payroll (withholding)
- Priority: Data modification > Specialized domain
- Route to: Employee Data Agent

..."
}
```

---

### Conflict Resolution Examples

#### Example 1: "Payroll" + "Bank Account"

**Ambiguity:** Both Payroll and Employee Data agents could handle this.

**Solution:**
```json
{
  "scenario": "Employee Data Updates",
  "keywords": "update address, phone, emergency contact, bank account, routing number"
}

{
  "scenario": "Payroll Inquiries",
  "keywords": "paycheck, pay stub, salary, deductions (NOT bank account setup)"
}

// In instructions:
"Bank account or direct deposit SETUP → Employee Data
Bank account inquiry (verify deposit received) → Payroll"
```

---

#### Example 2: "Benefits" + "Enrollment"

**Ambiguity:** Could be navigation ("How do I enroll?") or benefits question ("What can I enroll in?").

**Solution:**
```json
{
  "conditionAgentInstructions": "...

'Enrollment' + 'Benefits':
- 'How do I...' or 'Where do I...' (navigational phrasing) → Navigation Agent
- 'What benefits...', 'Which plans...', 'Coverage details' (informational) → Benefits Agent
- 'Enroll me...', 'I want to enroll' (action during open enrollment) → Benefits Agent

..."
}
```

---

#### Example 3: "Time" (Multiple Meanings)

**Ambiguity:** Could mean time off, time tracking, or temporal timing.

**Solution:**
```json
{
  "scenario": "Time and Attendance - Questions about PTO, vacation, sick leave, time-off balances, or timesheet submission"
}

{
  "scenario": "Payroll - Questions about payment dates, pay periods, when payroll runs, or paycheck timing"
}

// Clear differentiation through specific keywords
// "Time off" vs "Time payroll runs" → Different agents
```

---

### Testing for Conflicts

**Validation Process:**

1. List all keywords across all scenarios
2. Identify overlaps (same word in multiple scenarios)
3. Create test questions using overlapping keywords
4. Verify routing matches PRIMARY intent
5. Add disambiguation rules if needed

**Example Test Matrix:**

| Test Question | Keyword Overlap | Expected Route | Actual Route | Status |
|--------------|----------------|----------------|--------------|--------|
| "Update bank account" | Payroll + Employee Data | Employee Data | ✅ Employee Data | Pass |
| "When is payroll?" | Payroll + Time | Payroll | ✅ Payroll | Pass |
| "How do I find benefits?" | Benefits + Navigation | Navigation | ❌ Benefits | Fail - Add rule |

When tests fail, add conditional routing rules or refine scenario keywords.

---

### Fallback Handling

**General agent pattern**:
Every multi-agent flow should have a **General** or **Help** agent as fallback.

```json
{
  "scenario": "User needs general help, clarification, or the question doesn't fit other categories"
}
```

**This agent**:
- ✅ Handles unclear requests
- ✅ Asks clarifying questions
- ✅ Routes to correct agent after clarification
- ✅ Handles greetings and general chat

**Example persona**:
```html
<p><em>You are a General Help agent.</em> You assist with questions that don't fit other specialized agents, provide clarification, and help users navigate to the right agent. You ask clarifying questions when intent is unclear and maintain a friendly, helpful tone. If you determine the user needs a specialized agent, guide them by saying "Let me connect you with our [X] specialist who can help with that."</p>
```

### Edge Label Conventions

**Purpose:** Edge labels in Flowise provide visual clarity about routing paths from ConditionAgent to specialized agents.

#### Recommendation: Use Descriptive Labels

**✅ Best Practice:**
```json
{
  "source": "conditionAgentAgentflow_0",
  "sourceHandle": "conditionAgentAgentflow_0-output-2",
  "target": "agentAgentflow_5",
  "data": {
    "edgeLabel": "Payroll"  // Descriptive, not "2"
  }
}
```

**❌ Avoid:**
```json
{
  "data": {
    "edgeLabel": "2"  // Numeric only - unclear what scenario this represents
  }
}
```

#### Benefits of Descriptive Labels

1. **✅ Easier to read workflow** in Flowise UI
2. **✅ Self-documenting** - edge label shows what scenario triggers it
3. **✅ Helpful for troubleshooting** routing issues
4. **✅ Better for stakeholder demos** - non-technical viewers can understand flow
5. **✅ Reduces need for external documentation**

#### Label Naming Pattern

Use the first 1-3 words of the scenario description as the edge label:

| Scenario | Edge Label | Notes |
|----------|-----------|-------|
| `"Payroll and Compensation"` | `"Payroll"` | Shortened to core keyword |
| `"Benefits Administration"` | `"Benefits"` | Single word sufficient |
| `"Time and Attendance"` | `"Time"` or `"Time & Attendance"` | Either works, prefer brevity |
| `"Employee Data Updates"` | `"Employee Data"` | Two words for clarity |
| `"General HR Support"` | `"General HR"` | Keep descriptive |

#### Multiple Edges to Same Agent

When multiple scenarios route to the same agent, descriptive labels are **essential**:

```json
// Scenario 2 → General Agent
{
  "data": {
    "edgeLabel": "Time"  // Clear which scenario triggered
  }
},
// Scenario 3 → General Agent (SAME agent)
{
  "data": {
    "edgeLabel": "Employee Data"  // Different label, same target
  }
},
// Scenario 4 → General Agent (SAME agent)
{
  "data": {
    "edgeLabel": "Onboarding"  // Another distinct label
  }
}
```

**Why important:** Without descriptive labels, you can't tell why the General Agent was selected. Labels provide routing traceability.

#### Edge Label Length Guidelines

- **Optimal:** 1-3 words (e.g., "Payroll", "Benefits", "Employee Data")
- **Maximum:** 15-20 characters (longer labels wrap in Flowise UI)
- **Avoid:** Full scenario text (too verbose)

**Examples:**

```
✅ "Payroll"              (8 chars)
✅ "Benefits"             (8 chars)
✅ "Time Off"             (8 chars)
✅ "Employee Data"        (13 chars)
✅ "General Help"         (12 chars)
❌ "Payroll and Compensation Issues" (37 chars - too long)
```

#### Technical Format

Edge labels are set in the `data.edgeLabel` field:

```json
{
  "source": "conditionAgentAgentflow_0",
  "sourceHandle": "conditionAgentAgentflow_0-output-[INDEX]",
  "target": "agentAgentflow_[N]",
  "targetHandle": "agentAgentflow_[N]",
  "data": {
    "sourceColor": "#ff8fab",  // Condition node color (pink)
    "targetColor": "#4DD0E1",  // Agent node color (teal)
    "edgeLabel": "[DESCRIPTIVE_LABEL]",  // Key field
    "isHumanInput": false
  },
  "type": "agentFlow",
  "id": "[SOURCE]-[SOURCE_HANDLE]-[TARGET]-[TARGET_HANDLE]"
}
```

#### Consistency Across Workflow

Maintain consistent naming style across all edges:

**✅ Consistent:**
```
"Payroll"
"Benefits"
"Time Off"
"Employee Data"
```
All use short, noun-based labels.

**❌ Inconsistent:**
```
"Payroll"
"Benefits Administration Team"
"Time"
"Employee Data Updates and Changes"
```
Mixed lengths and styles - harder to scan visually.

---

## ConditionAgent Instructions Design

### Overview

The `conditionAgentInstructions` field is the "brain" of your routing logic. Well-designed instructions lead to accurate routing; poor instructions cause frustration and mis-routing.

### Two Proven Patterns

#### Pattern A: Brief Keyword-Based (3-8 Scenarios)

**When to Use:**
- Simple routing with clear categories
- Limited keyword overlap
- Straightforward domain boundaries
- Small number of agents (3-8)

**Structure:**
```
[One sentence role definition]

[Action directive]

[Numbered or bulleted list of categories with keywords]

[Final instruction to select category]
```

**Example:**

```json
{
  "conditionAgentInstructions": "You are a ServiceNow ticket classifier for HCM issues.

Analyze the ticket and classify it into ONE category:

1. Payroll and Compensation - Issues with salary, pay, deductions, bonuses, withholding
2. Benefits Administration - Health insurance, retirement, benefits enrollment, FSA, HSA
3. Time and Attendance - PTO, sick leave, timesheets, schedules, hours worked
4. Employee Data - Personal info updates, contact changes, address updates
5. General HR Support - Other HR inquiries that don't fit above categories

Select the most appropriate category based on the primary intent."
}
```

**Characteristics:**
- ✅ Fast routing decisions (low latency)
- ✅ Easy to maintain and update
- ✅ Clear keyword-to-agent mapping
- ✅ Works well for non-overlapping domains
- ❌ Limited guidance for edge cases
- ❌ No complex conditional rules

**Use this pattern when:** Categories are distinct, keywords don't overlap significantly, and routing decisions are straightforward.

---

#### Pattern B: Comprehensive Structured (8+ Scenarios)

**When to Use:**
- Complex routing with overlapping domains
- Need for conditional routing rules
- Cross-functional workflows
- Guardrails required (PII, compliance)
- Large number of agents (8-20+)

**Structure (Plain Text or HTML):**

```
[Detailed Persona & Role]

[Routing Process/Steps]

[Keyword → Agent Mapping with Exceptions]

[Multi-Intent Handling Rules]

[Fallback/Escalation Logic]

[Context Awareness Rules]
```

**Example (Plain Text):**

```json
{
  "conditionAgentInstructions": "You are an intelligent Workday Support Router with expertise in HCM processes.

ROUTING PROCESS:
1. Analyze the user's question for primary intent
2. Identify keywords and their context
3. Apply conditional routing rules below
4. Select the most appropriate specialist

KEYWORD → AGENT MAPPING:

Navigation Basics:
- Keywords: 'how do I find', 'where is', 'navigate to', 'locate', 'can't find', 'page location'
- Route to: Agent.NavigationBasics
- Exception: If mentions 'permission denied' or 'access blocked' → Agent.SecurityAccess

Payroll:
- Keywords: 'paycheck', 'pay stub', 'salary', 'withholding', 'direct deposit', 'W-2', 'payment'
- Route to: Agent.Payroll
- Exception: If question is 'How do I find my paycheck?' (navigational intent) → Agent.NavigationBasics
- Exception: If about updating bank account (not payment inquiry) → Agent.EmployeeData

Benefits:
- Keywords: 'health insurance', 'dental', '401k', 'retirement', 'FSA', 'HSA', 'enrollment'
- Route to: Agent.Benefits
- Exception: General benefit questions during non-enrollment periods → Agent.GeneralHelp

Employee Data:
- Keywords: 'update address', 'phone number', 'emergency contact', 'personal info', 'name change', 'demographic'
- Route to: Agent.EmployeeData

MULTI-INTENT HANDLING:
- If question spans multiple domains (e.g., 'Update my address for payroll and benefits'):
  → Route to agent handling PRIMARY action (Employee Data for address update)
  → That agent can coordinate with other domains as needed

- If question has navigational + functional intent (e.g., 'How do I access payroll to check my pay?'):
  → Route to functional agent (Payroll) - they can provide navigation guidance

FALLBACK RULES:
- Unclear informational questions → Agent.GeneralHelp
- Unclear urgent/action requests → Route to most likely specialist
- Completely ambiguous → Agent.GeneralHelp with instruction to clarify

CONTEXT AWARENESS:
- Urgency indicators ('urgent', 'ASAP', 'blocked', 'critical') → Bias toward action-capable specialist
- Navigation phrases ('how do I', 'where can I') → Check Navigation keywords first
- Questions with no action verbs → Likely informational, consider General Help"
}
```

**Example (HTML-Formatted):**

```json
{
  "conditionAgentInstructions": "<h3>Agent Persona & Core Directive</h3>
<p>You are a <strong>Workday Support Router</strong> with deep expertise in HCM processes, system navigation, and HR operations. Your mission is to analyze user inquiries and route them to the most appropriate specialist agent.</p>

<h3>Primary Flow</h3>
<ol>
<li><strong>Greet & Inquire:</strong> Understand the user's core need</li>
<li><strong>Analyze Intent:</strong> Identify primary keywords and context</li>
<li><strong>Apply Rules:</strong> Use keyword mapping and conditional logic below</li>
<li><strong>Route:</strong> Connect user to the best specialist</li>
</ol>

<h3>Critical Guardrails</h3>
<ul>
<li>⛔ Never ask for sensitive PII (SSN, bank details) - route to secure agents</li>
<li>⛔ Do not attempt to answer specialized questions - route to experts</li>
<li>⛔ If in doubt, route to General Help for triage</li>
</ul>

<h3>Intent → Agent Mapping</h3>

<h4>Payroll Specialist</h4>
<ul>
<li><strong>Keywords/Intents:</strong> 'paycheck', 'pay stub', 'direct deposit', 'salary', 'W-2', 'withholding', 'YTD earnings', 'payment date', 'deductions'</li>
<li><strong>Handoff:</strong> Agent.Payroll</li>
<li><strong>Exception:</strong> If question is <em>only</em> about finding/navigating to payroll page → Agent.NavigationBasics</li>
<li><strong>Exception:</strong> If about bank account updates → Agent.EmployeeData</li>
</ul>

<h4>Benefits Administration</h4>
<ul>
<li><strong>Keywords/Intents:</strong> 'health insurance', 'dental', 'vision', '401k', 'retirement', 'FSA', 'HSA', 'enrollment', 'dependent', 'life insurance'</li>
<li><strong>Handoff:</strong> Agent.Benefits</li>
<li><strong>Exception:</strong> Simple benefit FAQ during non-enrollment → Agent.GeneralHelp</li>
</ul>

<h4>Navigation Basics</h4>
<ul>
<li><strong>Keywords/Intents:</strong> 'how do I find', 'where is', 'navigate to', 'page location', 'can't find', 'worklet', 'menu', 'search'</li>
<li><strong>Handoff:</strong> Agent.NavigationBasics</li>
<li><strong>Exception:</strong> If mentions access/permission issues → Agent.SecurityAccess</li>
</ul>

<h3>Cross-Topic Routing Rules</h3>
<p>When a question involves multiple domains:</p>
<ul>
<li><strong>'Update my address for payroll'</strong> → Agent.EmployeeData (primary action: data update)</li>
<li><strong>'Where do I enroll in benefits?'</strong> → Agent.NavigationBasics (primary: navigation) OR Agent.Benefits if enrollment period active</li>
<li><strong>'How do I check my paycheck and YTD?'</strong> → Agent.Payroll (primary: payroll information; agent can guide navigation)</li>
</ul>

<h3>Fallback & Escalation</h3>
<p>If intent is unclear:</p>
<ul>
<li>Informational/casual → Agent.GeneralHelp</li>
<li>Urgent/action-oriented → Route to most likely specialist (bias toward helping)</li>
<li>Completely ambiguous → Agent.GeneralHelp with clarification request</li>
</ul>"
}
```

**Characteristics:**
- ✅ Handles complex overlapping scenarios
- ✅ Clear guardrails for sensitive data
- ✅ Conditional routing rules
- ✅ Multi-intent handling logic
- ✅ Context-aware decisions
- ❌ Longer to write and maintain
- ❌ Higher token usage per routing decision

**Use this pattern when:** Domains overlap, keywords conflict, need for conditional rules, complex cross-functional workflows, or compliance/security guardrails required.

---

### Choosing Pattern A vs. Pattern B

| Criteria | Pattern A | Pattern B |
|----------|-----------|-----------|
| **Number of Scenarios** | 3-8 | 8-20+ |
| **Keyword Overlap** | Minimal | Significant |
| **Edge Cases** | Few | Many |
| **Conditional Rules** | Not needed | Required |
| **Guardrails (PII, Compliance)** | Not needed | Required |
| **Clarification Logic** | Simple fallback | Multi-turn possible |
| **Maintenance Effort** | Low | Medium-High |
| **Routing Accuracy** | Good (for simple cases) | Excellent (for complex cases) |
| **Token Usage** | Low | Medium-High |

---

### Common Mistakes to Avoid

#### ❌ Mistake 1: Vague Instructions

**Bad:**
```json
{
  "conditionAgentInstructions": "Route the question to the right agent."
}
```

**Problem:** No keyword mapping, no rules, no guidance.

**Fix:** Provide clear keyword mapping and routing rules (use Pattern A or B).

---

#### ❌ Mistake 2: No Exception Handling

**Bad:**
```json
{
  "conditionAgentInstructions": "Payroll keywords → Payroll Agent"
}
```

**Problem:** Doesn't handle edge cases like navigational questions about payroll.

**Fix:** Add exception rules: "If question is 'How do I find payroll?' → Navigation Agent"

---

#### ❌ Mistake 3: Overlapping Keywords with No Priority

**Bad:**
```json
"Scenario 1: Questions about time (→ Time Agent)
Scenario 2: Questions about payroll (→ Payroll Agent)"
```

**Problem:** "What time does payroll run?" matches both. No guidance on which takes priority.

**Fix:** Define priority rules or conditional logic: "If 'time' relates to schedules/PTO → Time Agent. If 'time' relates to payment timing → Payroll Agent."

---

#### ❌ Mistake 4: No Fallback

**Bad:** Only specific scenarios, no general/help agent.

**Problem:** Unclear questions or greetings have nowhere to route.

**Fix:** Always include a General Help/Fallback scenario as the last option.

---

#### ❌ Mistake 5: Too Many Instructions (Token Bloat)

**Bad:** 2000+ word instructions with every possible edge case documented.

**Problem:** High token cost, slower routing, model confusion.

**Fix:** Be concise. Use structured sections. Focus on common patterns, not exhaustive rules.

**Optimal Length:**
- Pattern A: 100-300 words
- Pattern B: 300-800 words

---

### Testing Your Instructions

**Validation Questions:**

1. ✅ Are keywords clearly mapped to scenarios?
2. ✅ Are exception/conditional rules documented?
3. ✅ Is there a fallback for unclear requests?
4. ✅ Are multi-intent cases handled?
5. ✅ Is the structure easy to read (sections, bullets)?
6. ✅ Is length appropriate (not too verbose)?

**Test Cases:**

Create test questions for each scenario and edge cases:

```json
{
  "test_cases": [
    {"input": "What's my pay stub?", "expected_route": "Payroll Agent"},
    {"input": "How do I find my pay stub?", "expected_route": "Navigation Agent (exception)"},
    {"input": "Update my address for payroll", "expected_route": "Employee Data (multi-intent)"},
    {"input": "Hello", "expected_route": "General Help (fallback)"},
    {"input": "I'm confused", "expected_route": "General Help (fallback)"}
  ]
}
```

Test each case in Flowise to verify correct routing.

---

## Production Deployment

### Pre-Deployment Checklist

**✅ Before deploying to production**:

1. **Test in Flowise**
   - [ ] Import flow.json successfully
   - [ ] All nodes render correctly
   - [ ] All connections visible
   - [ ] Model dropdowns populate

2. **Configure Credentials**
   - [ ] All API keys added to Flowise credentials
   - [ ] OAuth flows configured
   - [ ] Test credentials work

3. **Test Each Agent**
   - [ ] Test routing (each scenario triggers correct agent)
   - [ ] Test tools (APIs respond correctly)
   - [ ] Test knowledge sources (relevant results returned)
   - [ ] Test fallback (general agent handles unclear queries)

4. **Validate Outputs**
   - [ ] Agents return expected format
   - [ ] No hallucinations
   - [ ] Proper error handling
   - [ ] Appropriate tone/style

5. **Performance Testing**
   - [ ] Response times acceptable (<5 seconds for most queries)
   - [ ] Concurrent users handled
   - [ ] No timeout errors

6. **Security Review**
   - [ ] No API keys in flow.json (use credentials)
   - [ ] Sensitive operations require approval (human-in-loop)
   - [ ] No PII exposed in logs

### API Key Management

**✅ Best practices**:

1. **Separate environments**
   ```
   Development:  SHOPIFY_API_KEY_DEV
   Staging:      SHOPIFY_API_KEY_STAGING
   Production:   SHOPIFY_API_KEY_PROD
   ```

2. **Use Flowise credentials manager**
   - Store keys in Flowise, not in JSON
   - Never commit keys to git
   - Use .env.example as template

3. **Rotate keys**
   - Schedule: Every 90 days minimum
   - After: Team member departure
   - If: Suspected compromise

4. **Monitor usage**
   - Track API calls per key
   - Set up alerts for unusual activity
   - Review logs regularly

5. **Principle of least privilege**
   - Use read-only keys where possible
   - Limit permissions to only what's needed
   - Create service accounts for automation

### Credential Naming Convention in Flowise

**Standard Credential Names:**

Use these exact credential names when creating credentials in the Flowise UI. This allows generated workflows to work immediately after import without manual configuration.

| Model Platform | Standard Credential Name | Used In Field |
|---------------|-------------------------|---------------|
| OpenAI (ChatGPT, GPT-4) | `OpenAI API Key` | `"credential": "OpenAI API Key"` |
| Anthropic (Claude) | `Anthropic API Key` | `"credential": "Anthropic API Key"` |
| Google (Gemini) | `Google API Key` | `"credential": "Google API Key"` |

**Setup Process:**

1. **Create Credential in Flowise** (one time per platform):
   - Navigate to Flowise UI → Credentials
   - Click "Add Credential"
   - Select credential type (e.g., "OpenAI API")
   - **Name it exactly**: `OpenAI API Key` (case-sensitive)
   - Paste your actual API key
   - Save

2. **Reference in JSON**:
   ```json
   "agentModelConfig": {
     "credential": "OpenAI API Key",  // Must match credential name in Flowise
     "modelName": "gpt-4o-mini",
     "agentModel": "chatOpenAI"
   }
   ```

3. **Import Workflow**:
   - Import JSON into Flowise
   - All agents automatically use the credential
   - No manual configuration needed

**Benefits:**

- ✅ **One-time setup**: Create credential once, use in all workflows
- ✅ **Automatic connection**: Imported workflows work immediately
- ✅ **Easy rotation**: Update key in Flowise UI, all workflows get new key
- ✅ **No manual wiring**: No need to select credential for each agent after import
- ✅ **Consistent pattern**: All Context Foundry generated workflows follow this standard

**Important:**

- ⚠️ Credential name MUST match exactly (case-sensitive)
- ⚠️ Use empty string `""` only if credential doesn't exist in Flowise yet
- ⚠️ If name doesn't match, agents will show "No credential selected" error
- ⚠️ Different Flowise instances may have different credential names (adjust as needed)

**Example Error (credential name mismatch):**

```
❌ "credential": "openai_key"  // Wrong - not the standard name
❌ "credential": "OpenAI Key"  // Wrong - missing "API"
✅ "credential": "OpenAI API Key"  // Correct - exact match
```

---

## ExecuteFlow Best Practices

The ExecuteFlow node enables modular workflow composition by calling sub-flows. Follow these best practices to use it effectively.

### When to Use ExecuteFlow

✅ **USE when**:
- Breaking complex workflows into modular, reusable components
- Need to execute specialized sub-workflows conditionally
- Creating workflow templates that can be composed
- Isolating error-prone operations in separate flows
- Building hierarchical agent systems (organization → department → team)
- Reusing validation/processing logic across multiple flows

❌ **DON'T use when**:
- Simple agent-to-agent handoff (use direct connection instead)
- Sub-flow would only be used once (inline it instead)
- Performance is critical (ExecuteFlow adds overhead of separate flow execution)
- Logic is trivial and doesn't warrant separate flow
- Debugging is priority (nested flows harder to troubleshoot)

### Configuration Best Practices

#### Flow ID Management

**✅ Good**:
```json
{
  "executeFlowSelectedFlow": ""  // Empty string - user selects in Flowise UI
}
```

**✅ Also good** (if flow ID is known and static):
```json
{
  "executeFlowSelectedFlow": "clm9x8f3j0001..."  // Real Flowise flow ID
}
```

**❌ Bad**:
```json
{
  "executeFlowSelectedFlow": "{{FLOW_ID}}"  // Placeholder - will fail at runtime
}
```

**Why**: Flow IDs must be valid Flowise flow identifiers. Use empty string in generated JSON (user selects in UI), or use variables only when dynamically selecting flows at runtime.

---

#### Response Attribution Strategy

**User Message** (default):
- Sub-flow response appears as **user input** to next node
- Next agent will **respond TO** the sub-flow output
- **Use when**: Next node should treat sub-flow output as new user input

**Example**:
```json
{
  "executeFlowReturnResponseAs": "userMessage"
}
```
**Flow**: `Start → ExecuteFlow (Validation) → Agent (Process validated data)`
The agent receives validation result as if user sent it.

---

**Assistant Message**:
- Sub-flow response appears as **assistant response**
- Workflow considers sub-flow as completing the interaction
- **Use when**: Sub-flow produces the final answer, no further agent needed

**Example**:
```json
{
  "executeFlowReturnResponseAs": "assistantMessage"
}
```
**Flow**: `Condition → ExecuteFlow (Specialized Handler)`
The specialized handler's response is the final output.

---

#### Input JSON Structure

**✅ Good** - Properly formatted JSON:
```json
{
  "executeFlowInput": "{\"query\": \"{{question}}\", \"context\": \"{{context}}\"}"
}
```

**✅ Minimal valid** - Empty object:
```json
{
  "executeFlowInput": "{}"
}
```

**✅ Variable interpolation** - Pass through user input:
```json
{
  "executeFlowInput": "{{question}}"
}
```

**❌ Bad** - Not valid JSON:
```json
{
  "executeFlowInput": "plain text here"  // Not JSON
}
```

**❌ Bad** - Malformed JSON:
```json
{
  "executeFlowInput": "{query: value}"  // Missing quotes
}
```

---

### Common Patterns

#### Pattern 1: Validation → Processing Pipeline

**Use case**: Multi-stage data processing with reusable validation logic

**Structure**:
```
Start → ExecuteFlow (Validation) → ExecuteFlow (Processing) → Agent (Results)
```

**Example**:
```json
{
  "id": "executeFlowAgentflow_1",
  "data": {
    "label": "Validate Input",
    "name": "executeFlowAgentflow",
    "inputs": {
      "executeFlowSelectedFlow": "",  // User selects validation flow
      "executeFlowInput": "{{question}}",
      "executeFlowReturnResponseAs": "userMessage"
    }
  }
}
```

**When to use**:
- Input sanitization before processing
- Data validation with complex rules
- Format transformation pipelines
- Multi-step data enrichment

**Benefits**:
- Reusable validation across flows
- Isolates validation logic
- Easy to update validation rules
- Clear separation of concerns

---

#### Pattern 2: Conditional Sub-Flow Routing

**Use case**: Different workflows for different user intent categories

**Structure**:
```
Condition → ExecuteFlow (Technical) | ExecuteFlow (Billing) | ExecuteFlow (General)
```

**Example**:
```json
{
  "id": "executeFlowAgentflow_2",
  "data": {
    "label": "Route to Specialist Flow",
    "name": "executeFlowAgentflow",
    "inputs": {
      "executeFlowSelectedFlow": "",  // Different flow per scenario
      "executeFlowInput": "{\"data\": \"{{processedData}}\", \"category\": \"{{category}}\"}",
      "executeFlowReturnResponseAs": "assistantMessage"
    }
  }
}
```

**When to use**:
- Different workflows for different departments
- Specialized processing per category
- Compliance-driven routing (some requests need audit flows)
- A/B testing different flow versions

**Benefits**:
- Modular specialist flows
- Easy to add new categories
- Independent flow updates
- Clear routing logic

---

#### Pattern 3: Hierarchical/Nested Workflows

**Use case**: Multi-level organizational routing (company → department → team)

**Structure**:
```
Parent Flow → ExecuteFlow (Department) → [Sub-flow contains ExecuteFlow (Team)]
```

**Example**:
```json
{
  "id": "executeFlowAgentflow_3",
  "data": {
    "label": "Department Router",
    "name": "executeFlowAgentflow",
    "inputs": {
      "executeFlowSelectedFlow": "",  // Department-level sub-flow
      "executeFlowInput": "{{question}}",
      "executeFlowReturnResponseAs": "userMessage"
    }
  }
}
```

**When to use**:
- Organizational hierarchies (company → department → team)
- Multi-tier approval workflows
- Escalation patterns (Level 1 → Level 2 → Level 3 support)
- Recursive processing (directory traversal, nested data)

**⚠️ Warning**: Avoid deep nesting (>3 levels) - causes:
- Performance degradation (each level adds latency)
- Difficult debugging (hard to trace execution path)
- Increased error surface (more points of failure)
- Complex state management

**Best practice**: Flatten hierarchies where possible, use state to track levels instead of nesting.

---

### Security Considerations

**✅ DO**:
- Validate sub-flow IDs before execution (prevent unauthorized flow access)
- Sanitize input JSON to prevent injection attacks
- Use override config to enforce security policies (e.g., force temperature limits)
- Implement access control at flow level (not just parent flow)
- Log all sub-flow executions for audit trail

**❌ DON'T**:
- Expose sensitive data in `executeFlowInput` (use encrypted channels)
- Trust user-provided flow IDs (validate against allowlist)
- Pass credentials in input JSON (use Flowise credentials manager)
- Allow unlimited nesting (set depth limits)
- Skip validation assuming sub-flow will handle it

**Example - Secure configuration**:
```json
{
  "executeFlowInput": "{\"userId\": \"{{userId}}\", \"action\": \"{{action}}\"}",
  "executeFlowOverrideConfig": "{\"temperature\": 0.3}"  // Enforce deterministic responses
}
```

---

### Performance Optimization

**Minimize sub-flow calls**:
- Cache sub-flow results when appropriate
- Batch operations instead of multiple sequential calls
- Consider parallelization (use Condition node to route to multiple ExecuteFlow nodes simultaneously)

**Avoid anti-patterns**:
```
❌ Start → ExecuteFlow A → ExecuteFlow B → ExecuteFlow C → ExecuteFlow D
   (4 sequential sub-flows = 4x latency)

✅ Start → Condition → ExecuteFlow A | ExecuteFlow B | ExecuteFlow C
   (Parallel execution = 1x latency)
```

**Monitor execution time**:
- Sub-flow adds ~200-500ms overhead per call
- Deep nesting multiplies latency (3 levels = 600-1500ms overhead)
- Consider timeout configurations for long-running sub-flows

---

### Debugging Tips

**Enable detailed logging**:
- Log input JSON before ExecuteFlow call
- Log sub-flow response
- Track execution path in nested flows

**Validate independently**:
- Test sub-flow standalone before integrating
- Use hardcoded input to verify sub-flow behavior
- Check sub-flow error handling

**Common debugging scenarios**:

**Issue**: Sub-flow not executing
```
Check:
1. Is flow ID valid?
2. Is sub-flow published/active?
3. Is input JSON valid?
4. Are credentials configured in sub-flow?
```

**Issue**: Unexpected response attribution
```
Check:
1. Is executeFlowReturnResponseAs correct?
2. Does next node expect user or assistant message?
3. Is conversation history preserved correctly?
```

**Issue**: State not updating
```
Check:
1. Is executeFlowUpdateState configured?
2. Are state keys correct?
3. Is state accessible to next node?
```

---

### Example: Complete Pattern Library Use Case

**Scenario**: Customer support system with validation, routing, and escalation

```
1. Start Node (user question)
      ↓
2. ExecuteFlow (Input Validation)
   - Validates/sanitizes user input
   - returnResponseAs: userMessage
      ↓
3. Condition Node (Category Detection)
   - Technical → 4a
   - Billing → 4b
   - General → 4c
      ↓
4a. ExecuteFlow (Technical Support Flow)
    - Handles technical queries
    - returnResponseAs: assistantMessage

4b. ExecuteFlow (Billing Support Flow)
    - Handles billing queries
    - May contain nested ExecuteFlow for escalation
    - returnResponseAs: assistantMessage

4c. Agent (General Support)
    - Handles general queries
```

This demonstrates all 3 patterns:
- **Pattern A**: Validation → Processing
- **Pattern B**: Conditional routing
- **Pattern C**: Hierarchical (billing flow contains escalation sub-flow)

---

## Loop Node Best Practices

The Loop Node enables iterative workflows with retry logic, validation loops, and approval-with-revision patterns. Follow these best practices for reliable loop control.

### When to Use Loop Nodes

✅ **USE when**:
- Approvals that allow revision and resubmission (promotion nominations, document approvals)
- Data validation requiring user correction (form validation, data quality checks)
- Quality gates with retry logic (code quality, test execution, build validation)
- Iterative refinement workflows (design review cycles, content approval)
- Workflows where failure should trigger retry with improvement
- Need to prevent infinite resubmission loops with max iteration limits

❌ **DON'T use when**:
- Simple binary decisions (use Condition or HIL node instead)
- One-time operations (no iteration needed)
- Loops would be infinite without clear exit conditions
- State tracking overhead not justified by use case
- Nested loops (causes complexity explosion - redesign workflow instead)

---

### Configuration Best Practices

#### Max Iterations (loopMaxIterations)

**✅ Recommended Values**:

| Use Case | Max Iterations | Rationale |
|----------|----------------|-----------|
| Approval workflows | 3 | Reasonable revision attempts before escalation |
| Document validation | 5 | More attempts for complex validation rules |
| Quality gates | 3 | Balance between improvement cycles and efficiency |
| Simple toggles | 1 | Binary decision, no retry needed |

**❌ Bad**:
```json
{
  "loopMaxIterations": ""  // ❌ Missing - risk of infinite loop
}
```

**✅ Good**:
```json
{
  "loopMaxIterations": 3  // ✅ Reasonable limit
}
```

---

#### Temperature Settings

**Critical**: Loop decisions MUST be deterministic.

**✅ Good**:
```json
{
  "temperature": 0.1  // ✅ Deterministic routing
}
```

**❌ Bad**:
```json
{
  "temperature": 0.9  // ❌ Random routing decisions
}
```

**Why**: High temperature causes non-deterministic routing, making loop behavior unpredictable. Use 0.1-0.2 for consistent decisions.

---

#### State Management

**Required Pattern**: Agent BEFORE loop node must increment iteration count.

**✅ Good** - Proper state tracking:
```json
{
  "agentUpdateState": [
    {
      "key": "loop.iteration_count",
      "value": "{{ $flow.state.loop.iteration_count + 1 }}"
    },
    {
      "key": "loop_context",
      "value": "{\"iteration_count\": {{ $flow.state.loop.iteration_count }}, \"max_iterations\": 3, \"approval_state\": \"{{ approval_state }}\", \"validation_errors\": {{ validation_errors }}}"
    }
  ]
}
```

**❌ Bad** - No state tracking:
```json
{
  "conditionAgentInput": "{{ question }}"  // ❌ Missing iteration count
}
```

**Why**: Without iteration tracking, loop can't enforce max iterations and may run forever.

---

#### Exit Conditions (exitOnApprovalStates)

**Critical**: Define clear success states.

**✅ Good**:
```json
{
  "exitOnApprovalStates": ["APPROVED", "VALIDATED", "PASSED", "COMPLETED"]
}
```

**❌ Bad**:
```json
{
  "exitOnApprovalStates": ["OK", "good", "yes"]  // ❌ Vague, inconsistent
}
```

**Why**: Success states must be explicit, case-sensitive, and consistent across workflow.

---

### Wiring Patterns

#### Pattern A: Approval with Revision Loop

**Use Case**: Promotion nominations, document approvals

```
[Submission Agent] → [HIL Approval Gate]
                         ↓ proceed → [Final Stage]
                         ↓ reject  → [Loop Node]
                                        ↓
                                  0: Revise & Resubmit ↺
                                  1: Approved (exit)
                                  2: Max Iters (abandon)
                                  3: Escalate (executive review)
```

**Key Wiring**:
- HIL reject → Loop Node input
- Loop output 0 → Revision agent (loops back)
- Loop output 1 → Next stage (success exit)
- Loop output 2 → Failure handler (max iters reached)
- Loop output 3 → Human escalation (edge cases)

**Example**:
```json
{
  "source": "humanInputAgentflow_0",
  "sourceHandle": "humanInputAgentflow_0-output-reject",
  "target": "conditionAgentAgentflow_12",
  "data": {
    "edgeLabel": "Rejected",
    "isHumanInput": true
  }
}
```

---

#### Pattern B: Validation with Correction Loop

**Use Case**: Form validation, data quality checks

```
[User Input] → [Validator Agent] → [Loop Node]
                                        ↓
                      0: Back to Input Form ↺
                      1: Exit (Valid) → Processing Agent
                      2: Exit (Max Iters) → Error Display
                      3: Escalate → Manual Review
```

**State Requirements**:
```json
{
  "validation_errors": ["Missing field: employee_id", "Invalid date format"],
  "required_fields_missing": true,
  "quality_score": 65
}
```

---

#### Pattern C: Quality Gate with Retry

**Use Case**: Code quality, test execution, build validation

```
[Builder Agent] → [Quality Check Agent] → [Loop Node]
                                              ↓
                            0: Back to Builder Agent ↺
                            1: Exit (Passed) → Deploy
                            2: Exit (Max Iters) → Mark Failed
                            3: Escalate → Manual QA Review
```

**Decision Logic**:
- quality_score < 80 → Route 0 (continue)
- quality_score >= 80 → Route 1 (exit approved)
- iteration_count >= max_iterations → Route 2 (max iters)

---

### Integration with HIL Gates

Loop Nodes complement HIL gates by handling rejection paths.

**Combined Benefits**:
- ✅ Enables iterative refinement after rejection
- ✅ Prevents infinite resubmission loops (max iterations)
- ✅ Provides escalation path for edge cases
- ✅ Tracks attempt count for audit trail
- ✅ Automated retry logic without manual intervention

**Typical Flow**:
```
1. User submits → HIL approves → Proceed
2. User submits → HIL rejects → Loop Node
   ↓
3. Loop checks iteration (1 of 3)
   ↓
4. Route 0: User revises → Resubmit → HIL reviews again
   ↓
5. Loop checks iteration (2 of 3)
   ↓
6. If still rejected after 3 attempts → Route 2 (abandon)
   OR Route 3 (escalate to executive review)
```

---

### Common Pitfalls

#### ❌ Pitfall 1: No Max Iterations Limit

**Problem**: Risk of infinite loop
```json
{
  "loopMaxIterations": ""  // ❌ Missing
}
```

**Solution**: Always set reasonable limit
```json
{
  "loopMaxIterations": 3  // ✅ Safety limit
}
```

---

#### ❌ Pitfall 2: Non-Deterministic Routing

**Problem**: High temperature causes unpredictable decisions
```json
{
  "temperature": 0.9  // ❌ Random routing
}
```

**Solution**: Use low temperature for consistency
```json
{
  "temperature": 0.1  // ✅ Deterministic
}
```

---

#### ❌ Pitfall 3: Missing State Tracking

**Problem**: Iteration count not tracked, loop can't exit
```json
{
  "conditionAgentInput": "{{ question }}"  // ❌ No iteration count
}
```

**Solution**: Track iteration_count in flow state
```json
{
  "agentUpdateState": [
    {"key": "loop.iteration_count", "value": "{{ $flow.state.loop.iteration_count + 1 }}"}
  ],
  "conditionAgentInput": "{{ loop_context }}"  // ✅ Includes iteration_count
}
```

---

#### ❌ Pitfall 4: Unwired Escalation Path

**Problem**: No human escalation for edge cases
```json
// Only routes 0, 1, 2 wired, route 3 disconnected
```

**Solution**: Always wire all four routes
```json
// Route 0: Loop back ✅
// Route 1: Exit approved ✅
// Route 2: Exit max iters ✅
// Route 3: Escalate to human ✅ Always wire this!
```

**Why**: Edge cases (policy conflicts, ambiguous situations) need human judgment.

---

#### ❌ Pitfall 5: Nested Loops

**Problem**: Loop inside loop causes complexity explosion
```
[Loop A] → [Agent] → [Loop B] → [Agent] → [Loop C]
```

**Solution**: Redesign with single loop and multi-stage validation
```
[Multi-Stage Validator] → [Single Loop Node] → [0: Retry All Stages]
```

**Why**: Nested loops are hard to debug, track, and reason about. Use sequential stages instead.

---

### Validation Checklist

Before deploying Loop Node workflows, verify:

- [ ] **loopMaxIterations** set to reasonable limit (3-5)
- [ ] **exitOnApprovalStates** defined with explicit success states
- [ ] **Temperature** set to 0.1-0.2 for deterministic routing
- [ ] **Agent before loop** populates loop_context with required fields
- [ ] **Agent before loop** increments iteration_count in state
- [ ] **Output 0 (Continue)** wired back to revision/correction agent
- [ ] **Output 1 (Exit Approved)** wired to next stage
- [ ] **Output 2 (Exit Max Iters)** wired to failure handler
- [ ] **Output 3 (Escalate)** wired to human review node
- [ ] **State reset** mechanism for successful completion (set iteration_count to 0)
- [ ] **Audit logging** includes iteration count and routing decisions

---

### Real-World Example: Promotion Nomination Loop

**Scenario**: Manager submits promotion → Local leadership rejects → Manager revises → Resubmit (max 3 times)

**Flow**:
```
Manager Form → NominationIntake Agent → LocalLeadershipReview Agent → HIL Gate
                                                                            ↓ proceed → FinalApprover
                                                                            ↓ reject  → Loop Node
                                                                                           ↓
Loop Decision (iteration 1 of 3):
  - approval_state = "REJECTED" → Route 0
  ↓
Back to Manager → Revision Form → Update justification → Resubmit
  ↓
LocalLeadershipReview Agent → HIL Gate → Still rejected → Loop Node
  ↓
Loop Decision (iteration 2 of 3):
  - approval_state = "REJECTED", iteration_count < max_iterations → Route 0
  ↓
Back to Manager again → Final revision → Resubmit
  ↓
LocalLeadershipReview Agent → HIL Gate → Approved! → Route 1 (exit success)
```

**State Tracking**:
```json
{
  "loop": {
    "iteration_count": 2,
    "max_iterations": 3
  },
  "nomination": {
    "worker_id": "EMP12345",
    "manager_id": "MGR98765",
    "approval_state": "APPROVED",
    "revision_history": [
      "Initial submission - insufficient peer comparison",
      "Revision 1 - added peer comparison but missing metrics",
      "Revision 2 - complete with all required data - APPROVED"
    ]
  }
}
```

**Result**: Manager successfully revised nomination twice before approval, demonstrating iterative refinement with loop safety (3-attempt limit).

---

## Mermaid Diagram Generation

Context Foundry automatically generates beautiful Mermaid diagrams for Flowise workflows with authentic styling, emoji icons, and intelligent layout.

### Features

**✅ Authentic Flowise Styling**
- 12+ node types with correct shapes and colors from Flowise UI
- Emoji icons for quick visual identification
- Intelligent layout direction (TD vs LR based on complexity)

**✅ Flow Metadata Badges**
- Total nodes count
- Agent count
- Complexity level (Simple/Moderate/Complex)
- Memory and tools indicators

**✅ Interactive Documentation**
- Collapsible agent details table with emojis
- Visual node type legend with all 14 node types
- Flow metadata summary

### Node Type Reference

All 14 supported Flowise node types render with authentic colors:

| Type | Shape | Color | Icon |
|------|-------|-------|------|
| Start | Stadium | Green `#7EE787` | 🚀 |
| Agent | Rectangle | Teal `#4DD0E1` | 🤖 |
| ConditionAgent | Hexagon | Pink `#ff8fab` | 🎯 |
| Condition | Diamond | Orange `#FFB938` | 🔀 |
| LLM | Rounded | Blue `#64B5F6` | 💬 |
| Tool | Trapezoid | Brown `#d4a373` | 🔧 |
| ExecuteFlow | Rectangle | Olive `#a3b18a` | ▶️ |
| CustomFunction | Rectangle | Purple `#E4B7FF` | ⚙️ |
| HTTP | Rectangle | Red `#FF7F7F` | 🌐 |
| HumanInput | Hexagon | Indigo `#6E6EFD` | 👤 |
| DirectReply | Rectangle | Mint `#4DDBBB` | 💭 |
| Loop | Stadium | Coral `#FFA07A` | 🔄 |
| Iteration | Rectangle | Lavender `#9C89B8` | 🔁 |
| StickyNote | Rectangle | Yellow `#fee440` | 📝 |

### CLI Usage

**Basic usage** (all features enabled by default):
```bash
python3 mermaid_generator.py workflow.json DIAGRAM.md
```

**Output includes**:
- Mermaid diagram with emojis
- Flow metadata badges
- Interactive agent details table
- Node type legend

**Custom options**:
```bash
# Minimal output (no interactive features)
python3 mermaid_generator.py workflow.json DIAGRAM.md --no-interactive

# Badges only (no legend)
python3 mermaid_generator.py workflow.json DIAGRAM.md --badges

# Legend only (no badges)
python3 mermaid_generator.py workflow.json DIAGRAM.md --legend

# Detailed node descriptions
python3 mermaid_generator.py workflow.json DIAGRAM.md --include-details
```

### Layout Direction

The generator intelligently chooses graph direction for optimal readability:

**Top-Down (TD)** - Simple flows:
- ≤5 nodes
- Linear structure
- Easy to follow vertically

**Left-Right (LR)** - Complex flows:
- >10 nodes
- Multiple branches (≥2 branching points)
- Better horizontal space utilization

### Generated Output Example

```markdown
![Nodes](https://img.shields.io/badge/Nodes-8-blue) ![Agents](https://img.shields.io/badge/Agents-5-green) ![Complexity](https://img.shields.io/badge/Complexity-Moderate-yellow)

---

**Total Nodes**: 8 | **Agents**: 5 | **Complexity**: Moderate

\`\`\`mermaid
graph LR
    start([🚀 Start Node])
    router{{🎯 Intent Router}}
    agent1[🤖 Technical Agent]
    agent2[🤖 Billing Agent]
    ...
\`\`\`

<details>
<summary><b>🔍 View Agent Details (Click to Expand)</b></summary>

| Agent | Type | Description |
|-------|------|-------------|
| 🚀 Start Node | Start | Workflow entry point |
| 🎯 Intent Router | ConditionAgent | Routes to specialist |
| 🤖 Technical Agent | Agent | Handles tech support |
...

</details>

### 🎨 Node Type Legend
| Icon | Type | Description |
|------|------|-------------|
| 🚀 | Start | Entry point of the workflow |
| 🤖 | Agent | AI agent with reasoning |
...
```

### Embedding in README

The orchestrator automatically embeds diagrams prominently in README:

```markdown
# Project Name

Description...

## 📊 Workflow Architecture

**[View Full Workflow Diagram →](./WORKFLOW-DIAGRAM.md)**

[Badges display here]

[Mermaid diagram renders here]

[Interactive details expand here]

---

## Overview
...
```

### Tips for Beautiful Diagrams

**✅ DO**:
- Let the generator choose layout direction automatically
- Use descriptive node labels (they'll get emojis automatically)
- Include node descriptions (shown in interactive table)
- Keep workflows focused (8-12 nodes optimal for readability)

**❌ DON'T**:
- Override node colors in Flowise (generator uses authentic colors)
- Create overly complex flows (>15 nodes hard to visualize)
- Skip the interactive section (users love the details table)

---

**For troubleshooting these best practices**, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

**For real-world examples**, see [EXAMPLES.md](docs/EXAMPLES.md)
