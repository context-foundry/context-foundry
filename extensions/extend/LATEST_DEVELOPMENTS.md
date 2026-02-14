# Workday Extend: Latest Developments (2024-2026)

Compiled from web research of developer.workday.com, Workday DevCon, community sources, and GitHub.

---

## Licensing Tiers

Workday Extend offers two tiers:
- **Essentials**: Core app-building capabilities
- **Professional**: Adds AI Gateway, Developer Copilot, Generative AI features, native AWS AI Services, and access to the upcoming Flowise Agent Builder

---

## Workday Build Platform (2025-2026)

At Workday Rising 2025, Workday launched **Workday Build** -- a unified developer platform that consolidates Workday Extend with new AI-powered tools:

- **Workday Extend** (app building -- the core)
- **Flowise Agent Builder**: Low-code AI agent design, targeted H1 2026 for Extend Professional customers (status: on track, not yet confirmed GA)
- **Developer Copilot**: AI coding companion, targeted GA end 2025 (initial release 2024 R2; enhanced capabilities announced June 2025; no delays reported but GA not explicitly confirmed)
- **Agent Gateway**: MCP- and A2A-compliant APIs for third-party AI agent integration, early adopter access reached end 2025; GA date TBD
- **Developer CLI**: Command-line tool for DevOps workflows, targeted GA end 2025 (no delays reported but GA not explicitly confirmed)
- **AI Widgets**: Embeddable AI-powered UI components, targeted GA end 2025 (no delays reported but GA not explicitly confirmed)
- **AI Services**: Expanded native APIs for Document Intelligence and natural language queries
- **Workday Data Cloud**: Zero-copy data sharing via Apache Iceberg, early adopter access targeted H1 2026, GA later 2026

### Agent Partner Network
15+ launch partners including Accenture, Adobe, AWS, Deloitte, Google Cloud, IBM, Microsoft -- their agents integrate through the gateway to connect with Workday's Agent System of Record (ASOR).

### Microsoft Partnership
- Microsoft Entra Agent ID integration for verified agent identities
- Centralized governance and real-time ROI tracking
- Seamless task workflows between Microsoft 365 Copilot and Workday agents

---

## DevCon 2024 Key Announcements

### Visual UI Mode in App Builder (Beta)
- Toggle between **Visual Mode** (drag-and-drop) and **Code Mode** (JSON editing)
- Build business processes, business objects, security domains with clicks
- Real-time preview in App Preview
- Available to all Workday Extend customers

### Copilot for Workday Extend (2024 R2)
- Generate code, data queries, and mock test data with natural language prompts
- Chat interface for accessing references and code snippets
- Suggested APIs with how-to guidance
- Automatic orchestration generation with documentation

### Built on Workday
- Partners can build, manage, and market apps on the Workday platform
- Workday Marketplace distribution (no manual code deployment to individual tenants)
- Eight early adopters launched, broader availability H2 2024

### ISU Configuration Streamlining (2024 R2)
- Integration System User setup up to **10x faster**
- Direct credential creation in Extend (no cross-tenant navigation)

### Bidirectional Business Object Relationships
- Extend Model Objects connect to Workday-delivered business objects
- Direct data reporting from Workday Data Sources
- Replaces limited custom object functionality

### Quick Deploy to IMPL
- Deployment to implementation tenants bypasses standard promotion windows
- For urgent updates

### Dark Mode (2024 R2)
- App Builder and Orchestration Builder support dark mode

---

## API Ecosystem (Current)

### API Types Available

| API Type | Format | Best For |
|----------|--------|----------|
| **REST API** | JSON | Modern web integrations, CRUD operations |
| **SOAP API (WWS)** | XML | Complex transactional work, payroll, financial operations |
| **RaaS** | JSON/XML | Exposing Workday reports as API endpoints |
| **Graph API** | JSON | Extend apps accessing Workday data relationships |
| **WQL** | SQL-like | Ad-hoc data queries with SQL-like syntax |

### REST API Details
- **Endpoint pattern**: `https://{hostname}.workday.com/ccx/api/v1/{tenant_name}`
- **Authentication**: OAuth 2.0 (Client ID + Client Secret -> Access/Refresh tokens)
- **Rate limiting**: Tenant-dependent; commonly reported as ~10 calls/sec but varies by tenant size, API type, and Workday configuration. Always implement exponential backoff and respect `Retry-After` headers.
- **No inbound webhook endpoint**: The REST API does not expose a native webhook subscription endpoint. For event-driven outbound notifications, use orchestration steps with REST API calls (see orchestrations-integrations-guide.md). For inbound event detection, use polling or third-party middleware.

### Graph API
- Used by Extend apps for data relationships
- Required scopes: Core Compensation, Talent Core, Workday Extend, Staffing
- Requires "Workday Graph API Applications" policy with Modify permissions

---

## Canvas Kit (UI Component Library)

Canvas Kit is Workday's **open-source** React component library implementing the Canvas Design System:

### Installation
```bash
yarn add @workday/canvas-kit-react @workday/canvas-tokens-web
```

### Technical Requirements
- **Framework**: React (>=16.8)
- **TypeScript**: >=5.0 (optional)
- **Styling**: Emotion ^11.7.0
- **Design Tokens**: CSS variables via `@workday/canvas-tokens-web`
- **License**: Apache 2.0
- **Browser Support**: Edge, Firefox, Chrome, Safari, Opera (last 2 versions)

### Token System (3 CSS files required)
```css
@import '@workday/canvas-tokens-web/css/base/_variables.css';
@import '@workday/canvas-tokens-web/css/brand/_variables.css';
@import '@workday/canvas-tokens-web/css/system/_variables.css';
```

### GitHub
- Repository: https://github.com/Workday/canvas-kit
- 131 contributors, 3,521 commits
- Monorepo managed via Lerna

---

## Official GitHub Examples

### Extend JS Example Repository
**Repository**: https://github.com/Workday/extend-js-example

- **Spot Bonus App**: One-time payments with feedback via Graph API
- **Worker Badge Generator**: Badge image generation using HTML5 Canvas and Application Business Objects

### Real-World App Examples (from Community)
- Certification Management (compliance tracking)
- Pulse Survey App (anonymous employee feedback)
- Employee Union Management (HR partner interface)
- Custom Learning Modules (AI-driven course recommendations)
- Journal Line Reclassification (financial reclassification)
- Promotion Nomination (manager-driven workflows)
- AI Translation Generator (award-winning Hackathon project)

---

## Workday Orchestrate vs. Studio

| Aspect | Orchestrate | Studio |
|--------|-------------|--------|
| Interface | Browser-based, drag-and-drop | Eclipse-based IDE |
| Best for | Lightweight, real-time, event-driven API integrations | Bulk operations, payroll, millions of records |
| Languages | JSON/XML expressions | XML assembly, XSLT 2.0, MVEL, Java (custom beans) |
| Deployment | In-tenant | Deployed to Workday cloud |
| Time savings | 30-50% reduction vs Studio | Baseline |

**Key insight**: Orchestrate is NOT a replacement for Studio -- they are complementary.

---

## Feature Release Timeline

| Feature | Available |
|---------|-----------|
| Visual UI Mode in App Builder (Beta) | 2024 |
| Built on Workday (Partner Apps) | H2 2024 |
| Dark Mode for App Builder/Orchestration Builder | 2024 R2 |
| Copilot for Workday Extend | 2024 R2 |
| Bidirectional BO Relationships | 2024 |
| Quick Deploy to IMPL | Late 2024 |
| AI Widgets | Targeted GA end 2025 (unconfirmed as of Feb 2026) |
| AI Services (expanded APIs) | Targeted GA end 2025 (unconfirmed as of Feb 2026) |
| Developer Copilot (enhanced) | Targeted GA end 2025; initial release 2024 R2 (unconfirmed as of Feb 2026) |
| Developer CLI | Targeted GA end 2025 (unconfirmed as of Feb 2026) |
| Agent Gateway (MCP + A2A) | Early adopter reached end 2025; GA date TBD |
| Flowise Agent Builder | Targeted H1 2026, Extend Professional (on track, not yet confirmed) |
| Workday Data Cloud | Early adopter targeted H1 2026, GA later 2026 |
| Workday Build platform | 2025-2026 rollout (ongoing) |

---

## Workday Illuminate Agents (Pre-built)

Pre-built AI agents for HR, Financials, and Industry workflows:
- 65% faster contract execution
- 90% reduction in staffing changes processing
- 900 hours saved annually on audit evidence
- 4x faster payroll compliance

---

## Key Observations for AI Agent Development

1. **Browser-based development**: Extend apps are NOT built with local file-based tools. The App Builder runs entirely in the browser. AI agents cannot generate files locally and deploy them.

2. **JSON-centric**: Everything in Extend is JSON -- pages, metadata, orchestrations. Well-suited for AI generation, but must be authored within the App Builder or IntelliJ plugin.

3. **New CLI opportunity**: The Developer CLI (targeted GA end 2025, status unconfirmed) may enable AI agents to interact with Workday Extend programmatically, opening the door for automated app creation, testing, and deployment.

4. **MCP-compliant Agent Gateway**: Workday's adoption of the Model Context Protocol means AI agents can potentially integrate directly with Workday's Agent System of Record.

5. **Developer Copilot as precedent**: Workday already has an AI coding companion -- showing they expect AI-assisted development as a first-class workflow.

---

## Request Framework (Relevant to Extend)

Workday's Request Framework enables configuration of requests with routing and approvals:
- Questionnaire configuration for data collection
- Rule-based business process routing
- Dashboard integration via "Request" worklet
- Custom integrations based on request data
- Use cases: special leave, tuition reimbursement, security changes, job description modifications

---

## Workday Release Cadence

Workday releases updates **twice per year**:
- **R1**: Typically March
- **R2**: Typically September

**Critical for Extend developers**: Test apps against preview tenants before each release to catch breaking changes.

---

## Key URLs and Resources

| Resource | URL |
|----------|-----|
| Developer Portal | https://developer.workday.com |
| Canvas Kit GitHub | https://github.com/Workday/canvas-kit |
| Extend JS Examples | https://github.com/Workday/extend-js-example |
| Canvas Kit Storybook | https://workday.github.io/canvas-kit/ |
| WQL Documentation | https://doc.workday.com (admin guide > reporting > WQL) |
| Workday Engineering Blog | https://medium.com/workday-engineering |
| Workday GitHub Page | https://workday.github.io/ |
| API Tracker | https://apitracker.io/a/workday |

---

## Source Citations

| Claim Area | Primary Source |
|------------|---------------|
| Workday Build platform | [Workday blog: Workday Build announcement (Sep 2025)](https://blog.workday.com/en-us/2025/workday-introduces-workday-build-unified-platform-developers-build-manage-workday-agents-apps.html) |
| Agent Gateway, Developer Copilot, CLI | [PRNewswire: Workday AI Developer Toolset (Jun 2025)](https://www.prnewswire.com/news-releases/workday-unveils-ai-developer-toolset-empowering-developers-to-customize-and-connect-ai-apps-and-agents-on-the-workday-platform-302471900.html) |
| Flowise acquisition | [PRNewswire: Workday Acquires Flowise (Aug 2025)](https://www.prnewswire.com/news-releases/workday-acquires-flowise-bringing-powerful-ai-agent-builder-capabilities-to-the-workday-platform-302530557.html) |
| Data Cloud, Flex Credits | [Futurum: Workday Rising 2025](https://futurumgroup.com/insights/workday-rising-2025-ai-agents-data-cloud-and-flex-credits-unveiled/) |
| Agent Gateway details | [Diginomica: Workday DevCon agent gateway](https://diginomica.com/workday-devcon-new-agent-gateway-adds-third-party-ai-agents-workdays-agentic-landscape) |
| Extend product page | [Workday: Application Development](https://www.workday.com/en-us/products/platform-product-extensions/application-development.html) |
| CORS configuration | [GitHub: extend-js-example](https://github.com/Workday/extend-js-example) |
| Canvas Kit | [GitHub: Workday/canvas-kit](https://github.com/Workday/canvas-kit) |
| Studio languages | [GitHub: vassar-college-es/workday-studio-integrations](https://github.com/vassar-college-es/workday-studio-integrations), [PhenomCloud: Workday Studio](https://resources.phenomecloud.com/workday-studio) |

*Last updated: 2026-02-13. Roadmap items with "unconfirmed" status should be re-verified against developer.workday.com before relying on them.*
