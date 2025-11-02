# Best Practices - Flowise Agent Builder

**Guidelines for optimal results and production-ready Flowise flows**

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
- ✅ Production-ready
- ✅ Handles complex scenarios
- ❌ Longer build time
- ❌ More complex testing
- ❌ Higher maintenance

**⚠️ Warning**: Going beyond 12 agents has diminishing returns. Consider splitting into multiple flows.

---

## Tool Configuration Best Practices

### Standard Tools (Required for ALL Agents)

All Flowise agents built with Context Foundry include 2 standard tools by default:

#### 1. CurrentDateTime
- **Purpose**: Provides current date and time for temporal context
- **Why**: Helps agents evaluate if search results and information are current
- **Example Use**: "Is this news article from today or last year?"
- **Auto-Included**: Yes (in AGENT-NODE-TEMPLATE.json)

#### 2. SearXNG Search
- **Base URL**: https://s.llam.ai
- **Purpose**: Federated meta-search across multiple search engines
- **Why**: Real-time information retrieval for dynamic queries
- **Example Use**: "What are the latest industry trends?"
- **Auto-Included**: Yes (in AGENT-NODE-TEMPLATE.json)

**Combined Benefit**:
Agents can search for real-time information (SearXNG) and then evaluate its freshness
(CurrentDateTime) to provide contextually aware, temporally accurate responses.

**Setup Required**:
After importing workflow to Flowise:
1. Create `currentDateTime` custom tool (see tool-configs/STANDARD_TOOLS.md)
2. Create `searxng-search` custom tool (see tool-configs/STANDARD_TOOLS.md)
3. Both tools are already referenced in agent configurations

**Documentation**: See `/extensions/flowise/tool-configs/STANDARD_TOOLS.md` for complete setup guide.

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

**For troubleshooting these best practices**, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

**For real-world examples**, see [EXAMPLES.md](docs/EXAMPLES.md)
