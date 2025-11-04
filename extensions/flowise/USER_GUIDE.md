# User Guide - Flowise Agent Builder

**Complete reference for building Flowise multi-agent workflows with Context Foundry**

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Basic Usage - Simple Prompts (3-5 Agents)](#basic-usage---simple-prompts-3-5-agents)
3. [Intermediate Usage - Moderate Prompts (5-8 Agents)](#intermediate-usage---moderate-prompts-5-8-agents)
4. [Advanced Usage - Complex Prompts (8+ Agents)](#advanced-usage---complex-prompts-8-agents)
5. [Understanding Generated Flows](#understanding-generated-flows)
6. [Customizing Agent Personas](#customizing-agent-personas)
7. [Adding Custom Tools](#adding-custom-tools)
8. [Working with Knowledge Sources](#working-with-knowledge-sources)
9. [Validation and Testing](#validation-and-testing)
10. [Importing to Flowise](#importing-to-flowise)
11. [Troubleshooting](#troubleshooting)
12. [Best Practices](#best-practices)
13. [Advanced Topics](#advanced-topics)

---

## Getting Started

### Prerequisites

Before using the Flowise Agent Builder, ensure you have:

1. **Context Foundry installed** and working
2. **Claude Code CLI** accessible in your PATH
3. **Python 3.10+** for validation scripts
4. **GitHub CLI authenticated** (for deployment)
5. **Flowise instance** (for testing generated flows)

**Quick verification**:
```bash
cf --version        # Context Foundry
claude --help       # Claude Code CLI
python3 --version   # Python
gh auth status      # GitHub authentication
```

### Installation Verification

```bash
# Navigate to Context Foundry
cd ~/homelab/context-foundry  # or your install path

# Verify Flowise extension exists
ls -lh extensions/flowise/AGENT_PATTERN_REFERENCE.md
# Expected: 26KB file

# Count templates
ls extensions/flowise/templates/ | wc -l
# Expected: 13+ files
```

✅ **Ready**: If all checks pass, you're ready to build Flowise flows!

---

## Basic Usage - Simple Prompts (3-5 Agents)

**Build Time**: 10-15 minutes
**Agent Count**: 3-5 specialized agents
**Complexity**: Simple
**Best For**: Single-domain workflows with clear routing

### Example 1: Customer Support

**Prompt**:
```
Build a Flowise customer service multi-agent flow with routing for technical support,
billing questions, and general inquiries
```

**What You Get**:
- **Agents**: 4-5 (Router, Technical Support, Billing, General Help, possibly Escalation)
- **Routing Scenarios**: 3-4 scenarios
- **Tools**: Email notification tool
- **Knowledge**: Support knowledge base configuration
- **Duration**: ~12 minutes

**Generated Files**:
```
customer-service-flow.json          # Main Flowise import file
README.md                           # Architecture overview
INTEGRATION_GUIDE.md                # Setup instructions
DEPLOYMENT.md                       # Flowise deployment guide
TESTING.md                          # Test scenarios
tool-configs/email-notification.json
knowledge-configs/support-kb.json
```

### Example 2: IT Helpdesk

**Prompt**:
```
Create a Flowise IT helpdesk flow with agents for password resets, software issues,
hardware problems, and network troubleshooting
```

**What You Get**:
- **Agents**: 5-6 (Router, Password Reset, Software Support, Hardware Support, Network, General)
- **Routing Scenarios**: 4-5 scenarios
- **Tools**: ServiceNow or Jira integration
- **Knowledge**: IT documentation, troubleshooting guides
- **Duration**: ~14 minutes

### Example 3: HR Onboarding

**Prompt**:
```
Build a Flowise HR onboarding assistant with agents for benefits enrollment,
paperwork processing, and orientation scheduling
```

**What You Get**:
- **Agents**: 4 (Router, Benefits, Paperwork, Orientation)
- **Routing Scenarios**: 3 scenarios
- **Tools**: Workday or BambooHR integration
- **Knowledge**: HR policy documents, benefits guides
- **Duration**: ~11 minutes

### Tips for Simple Prompts

✅ **Do**:
- Mention "Flowise" explicitly
- List 3-5 agent domains
- Specify key integrations if any
- Keep it focused on one department/domain

❌ **Don't**:
- Try to cover too many domains (use moderate/complex instead)
- Be vague ("build a business system")
- Skip mentioning "Flowise"

---

## Intermediate Usage - Moderate Prompts (5-8 Agents)

**Build Time**: 15-25 minutes
**Agent Count**: 5-8 specialized agents
**Complexity**: Moderate
**Best For**: Multi-domain workflows with multiple integrations

### Example 4: E-commerce Operations

**Prompt**:
```
Build a Flowise e-commerce order processing flow with inventory management,
shipping coordination, customer notifications, and returns handling,
integrating with Shopify and Shippo APIs
```

**What You Get**:
- **Agents**: 6-7 (Router, Inventory, Shipping, Customer Service, Returns, Analytics, General)
- **Routing Scenarios**: 5-6 scenarios
- **Tools**: Shopify API, Shippo API, Email service
- **Knowledge**: Product catalog, shipping policies, return procedures
- **Duration**: ~19 minutes

**Generated Tool Configs**:
```json
// tool-configs/shopify-api.json
{
  "name": "Shopify Inventory API",
  "description": "Check inventory levels and update stock",
  "auth": "API Key",
  "endpoints": [
    {
      "method": "GET",
      "path": "/admin/api/2024-01/products/{id}/inventory.json"
    }
  ]
}
```

### Example 5: Real Estate Assistant

**Prompt**:
```
Create a Flowise real estate property search multi-agent system with
Zillow API, Salesforce CRM, DocuSign, and Google Maps integration
```

**What You Get**:
- **Agents**: 6 (Router, Property Search, Lead Management, Document Processing, Showing Coordinator, General)
- **Routing Scenarios**: 5 scenarios
- **Tools**: Zillow API, Salesforce CRM, DocuSign, Google Maps API
- **Knowledge**: Real estate procedures, local market data
- **Duration**: ~22 minutes

### Example 6: Healthcare Patient Intake

**Prompt**:
```
Build a Flowise patient intake workflow with scheduling, insurance verification,
medical history collection, and HIPAA compliance agents
```

**What You Get**:
- **Agents**: 6-7 (Router, Scheduling, Insurance, Medical History, Compliance, Forms, General)
- **Routing Scenarios**: 5-6 scenarios
- **Tools**: EHR system integration (FHIR API)
- **Knowledge**: HIPAA compliance documents, intake procedures
- **Duration**: ~24 minutes

**HIPAA Compliance Note**: Generated flow includes compliance agent with strict data handling guidelines in persona.

### Tips for Moderate Prompts

✅ **Do**:
- Specify all major integrations (APIs, CRMs, etc.)
- List 5-8 distinct agent responsibilities
- Mention compliance requirements if applicable
- Include knowledge source types

❌ **Don't**:
- List more than 8 domains (consider splitting into multiple flows)
- Mix unrelated business areas
- Forget to mention API names explicitly

---

## Advanced Usage - Complex Prompts (8+ Agents)

**Build Time**: 20-30 minutes
**Agent Count**: 8+ specialized agents
**Complexity**: Complex
**Best For**: Enterprise-scale workflows with many integrations

### 🏆 Example 7: Promotion Nomination Workflow (Production Build - Nov 4, 2025)

**[View Complete Success Documentation →](./SUCCESS_PROMOTION_NOMINATION.md)**

This is a **real production build** that demonstrates the full capabilities of the Flowise extension, including the first successful Human-in-the-Loop (HIL) approval gate implementation.

**Prompt**:
```
Build a Flowise promotion nomination multi-agent workflow with manager-driven nominations,
on-behalf-of support, two-stage approval process with human-in-the-loop gates, bulk
decision capability, and complete Workday HCM integration
```

**Actual Build Results** (25 minutes, 1 iteration, 100% pass):
- **Nodes**: 11 total (1 start + 1 router + 7 agents + 2 HIL gates)
- **Edges**: 12 connections with multi-path routing
- **Agents**: 7 specialized (NominationIntake, OBOHandler, LocalLeadershipReview, FinalApprover, BulkDecision, ReportingAnalytics, GeneralHelp)
- **HIL Gates**: 2 approval checkpoints (Local Leadership → Executive)
- **JSON Lines**: 3,734 lines (127.8KB)
- **GitHub**: [promotion-nomination-flowise-agent](https://github.com/snedea/promotion-nomination-flowise-agent)

**Core Features Implemented**:
1. ✅ **Manager-Driven Nominations** - Form-based input with employee selection and justification
2. ✅ **On-Behalf-Of (OBO)** - Designated roles submit for managers
3. ✅ **Two-Stage Approval** - Local Leadership → Executive with HIL gates
4. ✅ **Bulk Decisions** - Filter by org and bulk approve/deny
5. ✅ **Complete Audit Trail** - Full state tracking and reporting

**Agent Topology**:
```
                 Start (Form Input)
                         |
                    Router (Intent Detection)
                         |
      ┌──────────────────┼──────────────────┐
      |                  |                  |
  NominationIntake   OBOHandler    LocalLeadershipReview
                                            |
                                    HIL: Local Approval
                                      ├─ proceed ─→ FinalApprover
                                      └─ reject ──→ GeneralHelp
                                                         |
                                                 HIL: Final Decision
                                                   ├─ proceed ─→ Complete
                                                   └─ reject ──→ Feedback
      |                  |
  BulkDecision   ReportingAnalytics
```

**HIL Gates (First Successful Implementation!)**:
- **Local Leadership Approval Gate**:
  - Fixed description with state variables
  - Outputs: `proceed` → FinalApprover | `reject` → GeneralHelp
  - Shows: nomination details, justification, peer comparison

- **Final Decision Gate**:
  - Fixed description with full history
  - Outputs: `proceed` → Completion | `reject` → Feedback loop
  - Shows: complete approval chain, impact analysis

**State Management**:
```json
{
  "nomination": {
    "worker_id": "string",
    "manager_id": "string",
    "obo_submitter_id": "string",
    "current_role": "string",
    "proposed_role": "string",
    "status": "submitted|local_approved|final_approved|denied",
    "local_approver_id": "string",
    "final_approver_id": "string",
    "decision_notes": "string"
  }
}
```

**Integration Points**:
- Workday HCM API (employee data lookup)
- Workday Business Process (approval routing)
- Email notifications (status updates)
- Document stores (promotion criteria)

**Why This Build Is Special**:
- ✅ First successful HIL gate implementation with semantic outputs
- ✅ Most complex workflow built (11 nodes, 12 edges)
- ✅ All 9 failure patterns prevented on first try
- ✅ Production-ready with complete Workday integration guide
- ✅ Real-world enterprise use case fully implemented

**Pattern Prevention**: 21/21 tests passed
- 7/7 structural tests
- 5/5 diagram validation
- 9/9 pattern prevention

**Production Readiness**: 95% ready out of the box
- Only requires API credentials and custom tool configuration
- Complete INTEGRATION_GUIDE.md with Workday setup
- Full state management and audit trail implemented

**Repository**: https://github.com/snedea/promotion-nomination-flowise-agent

---

### Example 8: Manufacturing Quality Control

**Prompt**:
```
Build a Flowise manufacturing quality control workflow with defect detection,
process optimization, supplier management, compliance tracking, and production scheduling,
integrating with SAP, MES systems, and IoT sensor data
```

**What You Get**:
- **Agents**: 8-10 (Router, Defect Detection, Process Optimization, Supplier Management, Compliance, Scheduling, Analytics, Reporting, Maintenance, General)
- **Routing Scenarios**: 7-8 scenarios
- **Tools**: SAP integration, MES system API, IoT data feed
- **Knowledge**: Quality standards (ISO 9001), manufacturing procedures
- **Duration**: ~28 minutes

### Example 8: Warehouse Operations (Proven)

**Prompt**:
```
Build a comprehensive Flowise multi-agent workflow for large-scale warehouse operations with
Workday, Dynamics 365, SharePoint, and SmartSheets integration
```

**Actual Build Results** (21 minutes, 1 iteration, 100% pass):
- **Agents**: 9 (Router, Inventory, Orders, HR/Labor, Equipment, Reporting, Integration, Safety, General)
- **Routing Scenarios**: 8 scenarios
- **Tools**: Workday API, Dynamics 365, SharePoint, SmartSheets, Email
- **Knowledge**: 4 sources (Warehouse procedures, Safety protocols, Equipment manuals, HR policies)
- **JSON Lines**: 1,164
- **Total Files**: 20

**Agent Topology**:
```
                   Router (Intent Detection)
                           |
       ┌───────────────────┼───────────────────┐
       |                   |                   |
   Inventory          HR/Labor            Orders
   Management         Management         Fulfillment
       |                   |                   |
   Equipment          Reporting           Integration
   Maintenance        Analytics           Coordinator
       |                   |                   |
    Safety            General Ops
   Compliance
```

### Tips for Complex Prompts

✅ **Do**:
- Be very specific about all integrations
- Organize agents by domain/department
- Mention all compliance requirements
- Specify knowledge sources needed
- Allow 20-30 minutes for build

❌ **Don't**:
- Go over 12 agents (diminishing returns)
- Mix incompatible domains
- Expect instant results (complex builds take time)

---

## Understanding Generated Flows

### Anatomy of Output Files

Every successful build produces:

```
project-name/
├── flow.json                    # Main Flowise import file
├── README.md                    # Architecture overview
├── INTEGRATION_GUIDE.md         # API setup instructions
├── DEPLOYMENT.md                # Flowise deployment guide
├── TESTING.md                   # Test scenarios
├── .env.example                 # Environment variables template
├── tool-configs/
│   ├── api-tool-1.json
│   ├── api-tool-2.json
│   └── ...
├── knowledge-configs/
│   ├── document-store-1.json
│   ├── vector-embedding-1.json
│   └── ...
└── docs/
    ├── AGENT_DESCRIPTIONS.md
    ├── ROUTING_SCENARIOS.md
    └── API_INTEGRATION_DETAILS.md
```

### JSON Structure

The main `flow.json` contains:

```json
{
  "nodes": [
    {
      "id": "startAgentflow_0",
      "data": {
        "name": "startAgentflow",
        "label": "Start",
        // ... start node config
      }
    },
    {
      "id": "conditionAgentAgentflow_1",
      "data": {
        "name": "conditionAgentAgentflow",
        "label": "Detect User Intention",
        "inputs": {
          "conditionAgentScenarios": [
            {"scenario": "User asking about inventory"},
            {"scenario": "User asking about orders"},
            // ... more scenarios
          ]
        }
      }
    },
    {
      "id": "agentAgentflow_2",
      "data": {
        "name": "agentAgentflow",
        "label": "Agent.Inventory",
        "inputs": {
          "agentModel": "chatOpenAI",
          "agentModelConfig": {
            "modelName": "gpt-4o-mini",
            "temperature": 0.5
          },
          "agentMessages": [
            {
              "role": "system",
              "content": "<p><em>You are an expert Inventory Management agent.</em> ...</p>"
            }
          ]
        }
      }
    }
    // ... more agents
  ],
  "edges": [
    {
      "source": "startAgentflow_0",
      "target": "conditionAgentAgentflow_1"
    },
    {
      "source": "conditionAgentAgentflow_1",
      "sourceHandle": "...-output-0",
      "target": "agentAgentflow_2"
    }
    // ... more edges
  ]
}
```

### Tool Configuration Structure

```json
// tool-configs/shopify-inventory.json
{
  "name": "Shopify Inventory Check",
  "description": "Check current inventory levels in Shopify",
  "type": "api",
  "auth": {
    "type": "apiKey",
    "header": "X-Shopify-Access-Token",
    "envVar": "SHOPIFY_API_KEY"
  },
  "endpoint": {
    "baseUrl": "https://{shop-name}.myshopify.com",
    "method": "GET",
    "path": "/admin/api/2024-01/products/{id}/inventory.json"
  },
  "schema": {
    "input": {
      "productId": "string (required)"
    },
    "output": {
      "quantity": "number",
      "location": "string",
      "sku": "string"
    }
  }
}
```

### Knowledge Configuration Structure

```json
// knowledge-configs/product-catalog.json
{
  "type": "documentStore",
  "name": "Product Catalog",
  "description": "Complete product information, pricing, specifications",
  "documents": [
    "docs/products/catalog.pdf",
    "docs/products/specifications.md",
    "docs/products/pricing.xlsx"
  ],
  "embeddingModel": "text-embedding-3-small",
  "chunkSize": 1000,
  "overlap": 200
}
```

---

## Customizing Agent Personas

### Understanding Agent Personas

Each agent has a system message that defines its personality, capabilities, and boundaries:

```html
<p><em>You are an expert Inventory Management agent.</em> You track stock levels,
process inventory adjustments, and provide real-time inventory status. You have access
to the Shopify inventory API and can check stock across all warehouse locations.
You do NOT handle order fulfillment or shipping - defer those to other agents.</p>
```

### How to Modify Personas

1. **Open the generated `flow.json`**
2. **Find the agent** you want to modify (search for `"label": "Agent.YourDomain"`)
3. **Locate `agentMessages`** array in the `inputs` object
4. **Edit the `content`** field

**Example**:
```json
{
  "agentMessages": [
    {
      "role": "system",
      "content": "<p><em>You are an expert Customer Service agent.</em> You handle customer inquiries with empathy and professionalism. You can access order history, process refunds up to $500, and escalate complex issues to management. You maintain a friendly, helpful tone and always ask clarifying questions before taking action.</p>"
    }
  ]
}
```

### Best Practices for Personas

✅ **Include**:
- Clear role definition ("You are an expert X agent")
- Specific capabilities (what the agent CAN do)
- Explicit boundaries (what the agent CANNOT do, defer to others)
- Tone/style guidance
- Access to tools/knowledge mentioned

❌ **Avoid**:
- Vague responsibilities
- Overlapping with other agents
- No boundaries (leads to scope creep)
- Missing tool/knowledge references

---

## Adding Custom Tools

### Tool Types

Flowise agents support two types of tools:

1. **Built-in Tools** - Platform-specific capabilities (web search, code interpreter)
2. **Custom Tools** - User-defined API integrations, database queries, etc.

### Creating Custom Tool Configurations

**Step 1**: Create a tool configuration file

```json
// tool-configs/stripe-payment.json
{
  "name": "Stripe Payment Processor",
  "description": "Process payments and refunds via Stripe API",
  "type": "api",
  "auth": {
    "type": "bearer",
    "envVar": "STRIPE_API_KEY"
  },
  "operations": [
    {
      "name": "createPayment",
      "method": "POST",
      "endpoint": "/v1/payment_intents",
      "parameters": {
        "amount": "number (required)",
        "currency": "string (required, default: usd)",
        "customer": "string (optional)"
      }
    },
    {
      "name": "refund",
      "method": "POST",
      "endpoint": "/v1/refunds",
      "parameters": {
        "payment_intent": "string (required)",
        "amount": "number (optional, defaults to full refund)"
      }
    }
  ]
}
```

**Step 2**: Reference in agent configuration

In `flow.json`, add to agent's `agentTools`:

```json
{
  "agentTools": [
    {
      "agentSelectedTool": "stripe-payment-processor",
      "agentSelectedToolRequiresHumanInput": true  // For sensitive operations
    }
  ]
}
```

### Auth Pattern Recommendations

| Integration Type | Auth Method | Example |
|-----------------|-------------|---------|
| REST APIs | API Key | `X-API-Key: {key}` |
| Enterprise SaaS | OAuth 2.0 | Salesforce, HubSpot |
| Cloud Services | Bearer Token | AWS, Google Cloud |
| Legacy Systems | Basic Auth | `Authorization: Basic {base64}` |

---

## Working with Knowledge Sources

### Document Stores

**When to use**: Pre-indexed document collections (PDFs, Word docs, etc.)

**Setup**:
```json
{
  "type": "documentStore",
  "name": "Company Policies",
  "description": "HR policies, procedures, and employee handbook",
  "storeId": "company-policies-store",  // Created in Flowise UI
  "searchConfig": {
    "topK": 5,
    "scoreThreshold": 0.7
  }
}
```

**In agent inputs**:
```json
{
  "agentKnowledgeDocumentStores": [
    {
      "documentStore": "company-policies-store",
      "docStoreDescription": "Use this to answer questions about company policies, benefits, time off, and HR procedures. Contains the complete employee handbook and all policy documents.",
      "returnSourceDocuments": true
    }
  ]
}
```

### Vector Embeddings

**When to use**: Semantic search across large text corpora

**Setup**:
```json
{
  "type": "vectorEmbedding",
  "name": "Product Documentation",
  "description": "Technical documentation for all products",
  "vectorStore": "pinecone-products",  // Created in Flowise UI
  "embeddingModel": "text-embedding-3-small",
  "configuration": {
    "namespace": "product-docs",
    "topK": 10,
    "includeMetadata": true
  }
}
```

**In agent inputs**:
```json
{
  "agentKnowledgeVSEmbeddings": [
    {
      "vectorStore": "pinecone-products",
      "embeddingModel": "text-embedding-3-small",
      "knowledgeName": "Product Technical Docs",
      "knowledgeDescription": "Comprehensive technical documentation, API references, troubleshooting guides, and best practices for all products. Use this when users ask about product features, APIs, or technical issues.",
      "returnSourceDocuments": true
    }
  ]
}
```

### Best Practices

**Document Stores**:
- ✅ Use for well-structured documents (PDFs, Word, Markdown)
- ✅ Index separately by category (HR, Legal, Technical, etc.)
- ✅ Keep descriptions specific (helps agent know when to use)

**Vector Embeddings**:
- ✅ Use for large, unstructured text corpora
- ✅ Choose embedding model based on content type
- ✅ Set appropriate `topK` (5-10 for most use cases)

---

## Validation and Testing

### What Gets Validated Automatically

Every build includes validation checks:

```bash
# 1. JSON Structure
✓ Valid JSON (jq parsing)
✓ Required fields present (nodes, edges)
✓ Proper node IDs

# 2. Self-Contained Architecture
✓ No separate chatOpenAI nodes
✓ No separate windowMemory nodes
✓ agentModelConfig in each agent
✓ Built-in memory configuration

# 3. Input Parameters
✓ asyncOptions present (model selection)
✓ inputParams complete
✓ No truncated placeholders

# 4. Edge Connections
✓ Valid source/target IDs
✓ Proper handle naming
✓ Edge type = "agentFlow"
```

### Manual Verification

After build completes:

```bash
# Navigate to project
cd /path/to/generated-project

# Check agent count
grep -c '"name": "agentAgentflow"' flow.json
# Expected: Your agent count

# Verify no anti-patterns
grep -c '"name": "chatOpenAI"' flow.json || echo "0"
# Expected: 0

grep -c '"name": "windowMemory"' flow.json || echo "0"
# Expected: 0

# Validate JSON
jq . flow.json > /dev/null && echo "✅ Valid JSON"
```

---

## Importing to Flowise

### Step-by-Step Import

1. **Open Flowise UI**
   ```
   http://localhost:3000  # or your Flowise instance URL
   ```

2. **Navigate to Agent Flows**
   - Click "Agent Flows" in the left sidebar

3. **Click "Import"**
   - Look for Import button in top-right corner

4. **Select Your JSON File**
   - Choose the generated `flow.json` file
   - Click "Open"

5. **Verify Import**
   - Flow should render immediately
   - Check all nodes are visible
   - Verify connections between nodes

6. **Configure Environment Variables**
   - Click on each agent that uses tools
   - Add API keys to credential fields
   - Save changes

7. **Test the Flow**
   - Click "Test" button
   - Enter a sample query
   - Verify routing works

### Common Import Issues

❌ **Issue**: "Invalid JSON format"
✅ **Solution**: Validate with `jq . flow.json`

❌ **Issue**: "Unknown node type"
✅ **Solution**: Ensure Flowise version supports agentAgentflow nodes

❌ **Issue**: "Missing credentials"
✅ **Solution**: Add API keys in Flowise UI after import

---

## Troubleshooting

For common issues, see [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

**Quick fixes**:

| Issue | Solution |
|-------|----------|
| Build doesn't detect as Flowise | Include "Flowise" in prompt |
| Too few/many agents | Be specific about agent count |
| Missing integrations | List all APIs explicitly |
| No knowledge sources | Mention knowledge requirements |

---

## Best Practices

For comprehensive guidelines, see [BEST_PRACTICES.md](BEST_PRACTICES.md).

**Key tips**:

✅ **Prompt Writing**:
- Mention "Flowise" explicitly
- List all integrations by name
- Specify agent domains clearly

✅ **Agent Design**:
- Keep agents focused (single responsibility)
- Define clear boundaries
- Include explicit capability statements

✅ **Tool Configuration**:
- Use environment variables for secrets
- Document API requirements
- Test tools before deployment

---

## Advanced Topics

### Multi-Level Routing

For complex workflows, agents can chain together:

```
Router → Agent A → Agent B → Agent C
```

**Use cases**:
- Escalation workflows (L1 → L2 → L3 support)
- Refinement workflows (draft → review → polish)
- Multi-step processes (collect → validate → process)

### State Management

Agents can share state across the workflow:

```json
{
  "agentUpdateState": [
    {
      "key": "customer_id",
      "value": "{{response}}"
    }
  ]
}
```

**Use when**: Information from one agent needed by another

### Agent Chaining

Connect agent outputs directly:

```json
{
  "source": "agentAgentflow_1",
  "sourceHandle": "agentAgentflow_1-output-agentAgentflow-Agent|AgentExecutor",
  "target": "agentAgentflow_2"
}
```

**Use when**: Sequential processing required

---

**For complete examples**, see [EXAMPLES.md](docs/EXAMPLES.md)

**For technical details**, see [ARCHITECTURE.md](ARCHITECTURE.md)
