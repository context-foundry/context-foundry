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

**For troubleshooting these best practices**, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

**For real-world examples**, see [EXAMPLES.md](docs/EXAMPLES.md)
