# Flowise Specialization - Test Prompts

**Purpose**: Test the Flowise agent flow specialization feature with these proven prompts
**Branch**: `enhancement/flowise-agent-builder`
**Last Updated**: 2025-10-31

---

## ✅ Verified Working Example

This prompt has been tested and produces a perfect, production-ready Flowise flow:

### Warehouse Operations (Complex)

**Prompt**:
```
Build a comprehensive Flowise multi-agent workflow for large-scale warehouse operations with
Workday, Dynamics 365, SharePoint, and SmartSheets integration
```

**Expected Result**:
- ✅ 9 agents (Inventory, Orders, HR, Equipment, Reporting, Integration, Safety, General)
- ✅ Intent router with 8 scenarios
- ✅ 5 external API integrations
- ✅ 4 knowledge sources
- ✅ Duration: ~20-25 minutes
- ✅ Test iterations: 1 (passes first try)

---

## 🎯 Test Prompts by Complexity

### Simple (3-5 Agents, 10-15 minutes)

#### 1. Customer Support
```
Build a Flowise customer service multi-agent flow with routing for technical support,
billing questions, and general inquiries
```

**Expected**:
- 4-5 agents (Router, Technical, Billing, General, possibly Escalation)
- 3-4 routing scenarios
- Email notification tool
- Knowledge base integration
- 10-15 minute build

#### 2. IT Helpdesk
```
Create a Flowise IT helpdesk flow with agents for password resets, software issues,
hardware problems, and network troubleshooting
```

**Expected**:
- 5-6 agents
- 4-5 routing scenarios
- ServiceNow or Jira integration
- IT knowledge base
- 12-15 minute build

#### 3. HR Onboarding
```
Build a Flowise HR onboarding assistant with agents for benefits enrollment,
paperwork processing, and orientation scheduling
```

**Expected**:
- 4 agents (Router, Benefits, Paperwork, Orientation)
- 3 routing scenarios
- Workday or BambooHR integration
- HR policy documents
- 10-12 minute build

---

### Moderate (5-8 Agents, 15-25 minutes)

#### 4. E-commerce Operations
```
Build a Flowise e-commerce order processing flow with inventory management,
shipping coordination, customer notifications, and returns handling,
integrating with Shopify and Shippo APIs
```

**Expected**:
- 6-7 agents
- 5-6 routing scenarios
- 2-3 external API integrations
- Product catalog knowledge
- 18-22 minute build

#### 5. Real Estate Assistant
```
Create a Flowise real estate property search multi-agent system with
Zillow API, Salesforce CRM, DocuSign, and Google Maps integration
```

**Expected**:
- 6 agents (Router, Search, Leads, Documents, Showings, General)
- 5 routing scenarios
- 4 API integrations
- Real estate procedures knowledge
- 20-25 minute build

#### 6. Healthcare Patient Intake
```
Build a Flowise patient intake workflow with scheduling, insurance verification,
medical history collection, and HIPAA compliance agents
```

**Expected**:
- 6-7 agents
- 5-6 routing scenarios
- EHR system integration (FHIR API)
- HIPAA compliance documents
- 22-25 minute build

#### 7. Financial Advisory
```
Create a Flowise financial advisory multi-agent flow with portfolio analysis,
risk assessment, tax planning, and retirement planning specialists
```

**Expected**:
- 5-6 agents
- 4-5 routing scenarios
- Financial data APIs (Alpha Vantage, IEX Cloud)
- Investment knowledge base
- 18-22 minute build

#### 8. Educational Course Advisor
```
Build a Flowise educational course recommendation system with academic advising,
career counseling, course search, and enrollment assistance
```

**Expected**:
- 5 agents
- 4 routing scenarios
- Student information system integration
- Course catalog knowledge
- 15-20 minute build

---

### Complex (8+ Agents, 20-30 minutes)

#### 9. Manufacturing Quality Control
```
Build a Flowise manufacturing quality control workflow with defect detection,
process optimization, supplier management, compliance tracking, and production scheduling,
integrating with SAP, MES systems, and IoT sensor data
```

**Expected**:
- 8-10 agents
- 7-8 routing scenarios
- 3-4 enterprise system integrations
- Quality standards knowledge
- 25-30 minute build

#### 10. Travel Booking Platform
```
Create a Flowise travel booking multi-agent system with flight search,
hotel booking, car rental, activities planning, and travel insurance,
integrating with Amadeus API, Booking.com, and Stripe payment processing
```

**Expected**:
- 7-9 agents
- 6-7 routing scenarios
- 4-5 API integrations
- Travel policies knowledge
- 22-28 minute build

#### 11. Legal Document Assistant
```
Build a Flowise legal document processing system with contract review,
compliance checking, case research, document drafting, and client communication
```

**Expected**:
- 6-8 agents
- 5-7 routing scenarios
- Legal database integration
- Legal precedent knowledge base
- 20-25 minute build

#### 12. Supply Chain Management
```
Create a Flowise supply chain coordination flow with procurement, logistics tracking,
vendor management, demand forecasting, and inventory optimization,
integrating with Oracle SCM, FedEx tracking, and Workday procurement
```

**Expected**:
- 8-10 agents
- 7-8 routing scenarios
- 3-4 enterprise integrations
- Supply chain best practices
- 25-30 minute build

---

## 🎨 Specialized Domain Examples

### Marketing Automation
```
Build a Flowise marketing campaign multi-agent workflow with content creation,
social media scheduling, email campaigns, analytics reporting, and lead scoring,
integrating with HubSpot, Mailchimp, and Google Analytics
```

**Expected**: 6-7 agents, 5-6 scenarios, 3 integrations, 20-25 minutes

### Restaurant Management
```
Create a Flowise restaurant operations flow with reservation management,
order processing, inventory tracking, staff scheduling, and customer feedback
```

**Expected**: 5-6 agents, 4-5 scenarios, POS integration, 15-20 minutes

### Property Management
```
Build a Flowise property management multi-agent system with tenant inquiries,
maintenance requests, rent collection, lease management, and property inspections
```

**Expected**: 6 agents, 5 scenarios, property management software integration, 18-22 minutes

### Insurance Claims Processing
```
Create a Flowise insurance claims workflow with claim intake, fraud detection,
damage assessment, approval routing, and payment processing
```

**Expected**: 6-7 agents, 5-6 scenarios, claims management system, 20-25 minutes

### Event Planning
```
Build a Flowise event planning multi-agent flow with venue booking,
vendor coordination, attendee registration, logistics management, and post-event follow-up
```

**Expected**: 5-6 agents, 4-5 scenarios, event management tools, 18-22 minutes

---

## 🧪 Stress Test Prompts

### Maximum Agents
```
Build a Flowise enterprise operations command center with agents for every major department:
Sales, Marketing, HR, Finance, IT, Legal, Operations, Customer Support, Product, Engineering,
and Executive Reporting
```

**Expected**: 12-15 agents, 10-12 scenarios, 30-40 minutes

### Maximum Integrations
```
Create a Flowise unified business platform integrating Salesforce, HubSpot, Slack,
Microsoft Teams, Jira, Confluence, GitHub, AWS, Google Workspace, Zoom, DocuSign,
QuickBooks, and Stripe
```

**Expected**: 8-10 agents, 13 API integrations, 35-45 minutes

### Maximum Complexity
```
Build a Flowise autonomous hospital operations system with patient care coordination,
emergency triage, surgical scheduling, pharmacy management, lab results processing,
insurance billing, medical records, compliance tracking, and staff management,
integrating with Epic EHR, HL7 FHIR, PACS imaging, and pharmacy systems
```

**Expected**: 10-12 agents, 9-10 scenarios, 4-5 integrations, 40-50 minutes

---

## 🎯 Testing Strategy

### Basic Validation (Test 1-3 Simple Prompts)
**Purpose**: Verify core functionality works
**Time**: 30-45 minutes total
**Success Criteria**: All 3 build successfully, pass tests, import into Flowise

### Moderate Validation (Test 4-8)
**Purpose**: Verify complex routing and integrations work
**Time**: 2-3 hours total
**Success Criteria**: At least 4/5 build successfully

### Full Validation (Test All)
**Purpose**: Comprehensive feature testing
**Time**: 6-8 hours total
**Success Criteria**: 90%+ success rate

---

## 📊 Expected Output for Each Prompt

Every successful build should produce:

### Files Created
- ✅ `[name]-flow.json` - Main Flowise import file
- ✅ `README.md` - Architecture overview
- ✅ `INTEGRATION_GUIDE.md` - API setup instructions
- ✅ `DEPLOYMENT.md` - Flowise deployment guide
- ✅ `TESTING.md` - Test scenarios
- ✅ `.env.example` - Environment variables
- ✅ `tool-configs/*.json` - Tool definitions
- ✅ `knowledge-configs/*.json` - Knowledge source configs
- ✅ `docs/*.md` - Additional documentation

### JSON Structure
- ✅ 1 start node (startAgentflow)
- ✅ 1 condition router (conditionAgentAgentflow)
- ✅ N specialized agents (agentAgentflow)
- ✅ N+1 edges (start→router, router→each agent)
- ✅ Valid JSON (jq parsing succeeds)

### Validation Checks Pass
- ✅ 0 separate model nodes
- ✅ 0 separate memory nodes
- ✅ N agentAgentflow nodes
- ✅ asyncOptions present
- ✅ agentModelConfig in each agent

---

## 🐛 Common Issues and Solutions

### Issue: Build doesn't recognize as Flowise flow
**Solution**: Include "Flowise" explicitly in prompt
```
❌ "Build a customer service system"
✅ "Build a Flowise customer service multi-agent flow"
```

### Issue: Too many/too few agents
**Solution**: Be specific about agent count
```
Better: "Build a Flowise sales flow with 4 agents: lead qualification,
product recommendation, quote generation, and follow-up"
```

### Issue: Missing integrations
**Solution**: List all desired integrations explicitly
```
Better: "...integrating with Salesforce CRM, HubSpot Marketing,
Stripe payments, and Twilio SMS"
```

### Issue: No knowledge sources
**Solution**: Mention knowledge requirements
```
Better: "...with knowledge base for product documentation
and troubleshooting guides"
```

---

## 💡 Prompt Writing Tips

### ✅ DO:
- Mention "Flowise" explicitly
- List desired integrations
- Specify agent domains
- Mention knowledge sources if needed
- Use industry-standard terms (CRM, EHR, POS, etc.)

### ❌ DON'T:
- Be too vague ("build a business system")
- Mix multiple unrelated domains
- Specify exact JSON structure (let it follow patterns)
- Request features Flowise doesn't support

---

## 🎓 Learning Resources

After building with these prompts:

1. **Study the generated JSON**
   - Compare to AGENT_PATTERN_REFERENCE.md
   - Notice the agent persona patterns
   - Observe routing scenario structure

2. **Read the generated docs**
   - INTEGRATION_GUIDE.md shows API patterns
   - TESTING.md shows test scenario structure
   - README.md shows architecture diagrams

3. **Import into Flowise**
   - See the visual flow diagram
   - Test the routing logic
   - Understand the tool configurations

---

## 📈 Success Metrics

Your testing is successful if:

✅ **90%+ of builds complete** without errors
✅ **100% of JSONs validate** (jq parsing succeeds)
✅ **100% of JSONs import** cleanly into Flowise
✅ **Build times** match estimates (±5 minutes)
✅ **Agent counts** match expectations
✅ **All validation checks pass** (see FLOWISE_SPECIALIZATION_FEATURE.md)

---

## 🎉 Quick Start

**To test this feature right now:**

1. Open Claude Code
2. Copy one of the simple prompts above (1-3)
3. Paste and send
4. Wait 10-15 minutes
5. Check the generated JSON imports into Flowise

**That's it!** You now have a production-ready Flowise flow built from a single sentence.

---

**Happy Testing! 🚀**

*If you discover any issues or have suggestions for new test prompts, document them here.*
