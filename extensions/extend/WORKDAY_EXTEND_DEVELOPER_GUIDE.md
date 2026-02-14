# Workday Extend Developer Guide

Comprehensive reference for AI agents and developers building Workday Extend applications.

---

## Table of Contents

1. [Development Environment Setup](#1-development-environment-setup)
2. [Workday Extend App Development Workflow](#2-workday-extend-app-development-workflow)
3. [Testing Extend Applications](#3-testing-extend-applications)
4. [Troubleshooting Common Issues](#4-troubleshooting-common-issues)
5. [Deployment and Release Management](#5-deployment-and-release-management)
6. [Workday APIs](#6-workday-apis)
7. [Advanced Patterns](#7-advanced-patterns)
8. [Appendix: Error Codes and Reference Tables](#appendix-error-codes-and-reference-tables)

---

## 1. Development Environment Setup

### 1.1 Developer Portal Registration

**Portal URL:** `https://developer.workday.com`

Steps to get started:

1. **Create a Workday Community account** at `community.workday.com`. This is the single-sign-on identity used across all Workday developer resources.
2. **Navigate to the Developer Portal** at `developer.workday.com` and sign in with your Community credentials.
3. **Request a Developer Tenant** (also called a "sandbox"). Workday provides:
   - **Workday Extend Sandbox** -- a purpose-built tenant for Extend app development
   - **Implementation tenants** -- for customers/partners who have purchased Workday
4. **Accept the Developer License Agreement** -- this grants access to APIs, documentation, and the Extend platform.

**Important:** Developer tenant provisioning can take 1-5 business days. The tenant URL will look like:
```
https://wd5-impl-services1.workday.com/<tenant_name>/d/home.html
```

### 1.2 Tenant Types and Their Roles

| Tenant Type | Purpose | Data | Refresh Cycle |
|-------------|---------|------|---------------|
| **Sandbox (SBX)** | Development, experimentation | Sample data, safe to modify | On-demand or weekly |
| **Implementation (IMPL)** | Active configuration and extension work | Configuration data | Per customer schedule |
| **Preview (PREVIEW)** | Pre-production testing | Copy of production (anonymized) | Before each Workday release |
| **Production (PROD)** | Live system | Real employee/business data | N/A (live) |
| **GMS (Gold Master Sandbox)** | Testing upcoming Workday releases | Copy of production + next release features | Before each release |

**Development flow:** Sandbox --> Implementation/Preview --> Production

**Key considerations:**
- Never develop directly in production
- Sandbox tenants are reset periodically; always export your work
- Preview tenants receive the next Workday release ~4 weeks before production
- Use preview tenants to test that your Extend apps are compatible with upcoming releases

### 1.3 API Client Setup and Credentials

To call Workday APIs (REST or SOAP) or to enable external systems to call into Workday, you need to register an API Client.

**Registering an API Client (for OAuth 2.0):**

1. In Workday, search for the task: **"Register API Client for Integrations"**
2. Fill in:
   - **Client Name**: descriptive name (e.g., "My Extend App API Client")
   - **Non-Worker**: Check if this is a system-to-system integration
   - **Scope**: Select the functional areas the client can access:
     - `Tenant Non-Configurable` (read tenant info)
     - `System` (system-level operations)
     - Specific functional scopes like `Human Resources`, `Staffing`, `Benefits`, etc.
   - **Redirect URI**: For authorization code flow (e.g., `https://your-app.com/callback`)
3. Save -- Workday generates:
   - **Client ID**: A UUID-format identifier
   - **Client Secret**: Generated once, save immediately (cannot be retrieved later)

**Token endpoints:**
```
Authorization: https://<host>/authorize
Token:         https://<host>/ccx/oauth2/<tenant>/token
```

**Example token request (Client Credentials flow):**
```bash
curl -X POST \
  "https://wd5-impl-services1.workday.com/ccx/oauth2/my_tenant/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials" \
  -d "client_id=<CLIENT_ID>" \
  -d "client_secret=<CLIENT_SECRET>"
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJS...",
  "token_type": "Bearer",
  "expires_in": 3600
}
```

**Refresh token flow (Authorization Code grant):**
```bash
curl -X POST \
  "https://wd5-impl-services1.workday.com/ccx/oauth2/my_tenant/token" \
  -d "grant_type=refresh_token" \
  -d "refresh_token=<REFRESH_TOKEN>" \
  -d "client_id=<CLIENT_ID>" \
  -d "client_secret=<CLIENT_SECRET>"
```

### 1.4 Workday Studio (Eclipse-Based IDE)

**Workday Studio** is the primary IDE for building **Workday Integrations** (EIBs, Cloud Connect, custom integrations). Note: Studio is specifically for integrations, not for Extend apps (which use the browser-based App Builder).

**Installation:**

1. Download from the Workday Community portal under **Downloads > Workday Studio**
2. Requires Java 11+ (JDK, not JRE)
3. Based on Eclipse; comes pre-bundled with Workday-specific plugins
4. Install on Windows or macOS (Windows is the primary supported platform)

**Configuration:**

1. Launch Workday Studio
2. Go to **Window > Preferences > Workday > Connection**
3. Enter:
   - **Tenant URL**: `https://wd5-impl-services1.workday.com`
   - **Tenant ID**: your tenant name
   - **Username**: integration system user (ISU) credentials
   - **Password**: ISU password
4. Test connection

**Integration System User (ISU):**
- Created in Workday via the **"Create Integration System User"** task
- Assign appropriate security groups (e.g., `Integration Build`, `Integration Debug`)
- ISUs are non-worker accounts used for automated processes

**Studio project structure:**
```
MyIntegration/
  assembly.xml          -- Integration assembly descriptor
  mediation.xml         -- Mediation/transformation logic
  xslt/                 -- XSLT transformations
  schemas/              -- XSD schemas
  launch/               -- Launch configurations
  test/                 -- Test data files
```

### 1.5 BIRT Designer Setup

**BIRT (Business Intelligence and Reporting Tools) Designer** is used to create custom report layouts (Advanced reports with BIRT output).

**Installation:**

1. Download the Workday-specific BIRT Designer from the Community portal (NOT the open-source Eclipse BIRT)
2. The Workday version includes custom data sources and adapters for Workday report fields
3. Requires Java 8+

**Usage:**
1. Create a Custom Report in Workday (Advanced type)
2. Add report fields and filters
3. Export the report definition as a `.rptdesign` file
4. Open in BIRT Designer to customize layout
5. Upload the modified `.rptdesign` back to Workday

### 1.6 Local Development Tools and SDKs

**For Extend Apps (browser-based development):**
- No local SDK required -- Extend apps are built entirely within Workday's browser-based **App Builder** (formerly called "Workday Extend Builder")
- The App Builder is accessed directly in your Workday tenant

**For integrations that call Workday APIs externally:**
- **Postman Collection**: Workday publishes official Postman collections for their REST and SOAP APIs
- **WSDL files**: Available at `https://<host>/ccx/service/<tenant>/<service_name>?wsdl`
- **OpenAPI/Swagger specs**: Available for REST APIs at the developer portal
- **Python SDK**: `pip install workday` (community-maintained, not official)
- **Node.js**: No official SDK; use raw HTTP calls with `axios` or `node-fetch`

**Recommended local development setup for API work:**
```
project/
  .env                  -- Tenant URL, client credentials (NEVER commit)
  postman/
    Workday_REST_API.postman_collection.json
    Workday_Environment.postman_environment.json
  scripts/
    auth.py             -- Token acquisition helper
    test_api.py         -- API integration tests
```

---

## 2. Workday Extend App Development Workflow

### 2.1 What is Workday Extend?

Workday Extend is a platform-as-a-service (PaaS) that lets you build custom applications that run **natively inside Workday**. Key characteristics:

- Apps run within the Workday security model (no separate auth)
- Apps can read/write Workday data via built-in data sources
- Apps share the same UI framework as core Workday
- Apps are delivered through Workday's update cycle
- Apps are tenant-specific (deployed per tenant)

**Extend is NOT:**
- A way to build external/standalone apps (use REST APIs for that)
- A replacement for Workday Studio integrations
- Available to all customers by default (requires Extend license)

### 2.2 Starting a New Extend App Project

1. In your Workday tenant, search for **"Create App"** (or navigate to the Extend area)
2. Provide:
   - **App Name**: Human-readable name (e.g., "Employee Equipment Tracker")
   - **App ID**: System identifier, no spaces (e.g., `employeeEquipmentTracker`)
   - **Description**: Purpose of the app
   - **App Category**: Classification for discoverability
3. The App Builder workspace opens with:
   - **Business Objects** panel
   - **Pages** panel (UI designer)
   - **Orchestrations** panel
   - **Security** panel
   - **API** panel (web service endpoints)
   - **Settings** panel

### 2.3 App Manifest and Project Structure

Every Extend app has an implicit manifest that tracks:

```
App
├── Business Objects (Data Model)
│   ├── Custom Objects (your data)
│   ├── Fields (attributes on objects)
│   ├── Validations (field-level rules)
│   └── Relationships (references to Workday objects or other custom objects)
├── Pages (UI)
│   ├── Landing pages
│   ├── Detail/Edit pages
│   ├── Dashboard pages
│   └── Report pages
├── Orchestrations (Business Logic)
│   ├── Orchestration steps
│   ├── Conditions
│   └── Integrations (callouts)
├── Security
│   ├── Domain security policies
│   ├── Business process security
│   └── Custom security groups
├── Web Service Endpoints (APIs)
│   ├── GET endpoints
│   ├── POST endpoints
│   └── PUT endpoints
├── Tasks and Navigation
│   ├── Custom tasks
│   ├── Dashboard shortcuts
│   └── Menu items
└── Settings
    ├── App configuration
    ├── Tenant-specific settings
    └── Feature flags
```

**There is no file-based project structure.** Everything is configured within Workday's UI. This is fundamentally different from traditional software development -- there are no local files, no git repository for the app itself, no build scripts.

**What you CAN export:** Workday provides **migration** capabilities to move apps between tenants (see Deployment section).

### 2.4 Creating Business Objects (Custom Objects)

Business Objects are the data model layer of your Extend app. They are analogous to database tables.

**Creating a Business Object:**

1. In the App Builder, go to **Business Objects**
2. Click **Create Business Object**
3. Define:
   - **Name**: e.g., "Equipment Request"
   - **API Name**: auto-generated, e.g., `equipmentRequest`
   - **Plural Label**: e.g., "Equipment Requests"

**Adding Fields:**

| Field Type | Description | Example |
|------------|-------------|---------|
| **Text** | Single/multi-line string | Description, Notes |
| **Number** | Integer or decimal | Quantity, Amount |
| **Boolean** | True/false toggle | Is Approved, Is Active |
| **Date** | Calendar date | Request Date, Due Date |
| **DateTime** | Date + time | Created At, Modified At |
| **Single Instance Reference** | FK to one Workday object | Assigned Worker, Location |
| **Multi-Instance Reference** | FK to many Workday objects | Approvers, Tags |
| **Dropdown** | Enumerated values | Status, Priority, Category |
| **Currency** | Amount + currency code | Estimated Cost |
| **Rich Text** | Formatted text | Detailed Description |

**Reference fields (crucial concept):**

Extend apps can reference both **custom business objects** and **core Workday objects** (Worker, Organization, Location, Job Profile, etc.). This is how you connect your custom data to Workday's existing data model.

```
Example: Equipment Request Business Object

Fields:
  - requestId (Auto-number, Primary Key)
  - requestDate (Date, Required)
  - requestedBy (Single Instance Reference -> Worker, Required)
  - equipmentType (Dropdown: Laptop, Monitor, Desk, Chair, Other)
  - description (Text, Max 500 chars)
  - estimatedCost (Currency)
  - status (Dropdown: Draft, Submitted, Approved, Denied, Fulfilled)
  - approvedBy (Single Instance Reference -> Worker)
  - approvalDate (Date)
  - notes (Rich Text)
```

**Validation Rules:**

You can add field-level and object-level validation rules:
- Required field checks
- Value range checks (min/max for numbers)
- Pattern matching for text fields
- Cross-field validations (e.g., approvalDate must be >= requestDate)
- Custom validation via calculated fields / WEL expressions

### 2.5 Building UI Pages with the Page Designer

Workday Extend uses a **drag-and-drop Page Designer** to build UI pages. Pages are composed of **Workday Components** (a proprietary component library).

**Page Types:**

| Page Type | Purpose | Typical Use |
|-----------|---------|-------------|
| **View Page** | Read-only display | Detail views, dashboards |
| **Create Page** | Form for creating new records | "Create Equipment Request" |
| **Edit Page** | Form for modifying existing records | "Edit Equipment Request" |
| **Dashboard Page** | Overview with widgets | App landing page |
| **Report Page** | Data table with filtering | List of all requests |

**Page Designer Workflow:**

1. Create a new page from the Pages panel
2. Choose page type
3. Drag components from the component palette onto the canvas
4. Configure each component:
   - **Data binding**: Connect to business object fields
   - **Visibility conditions**: Show/hide based on data or user role
   - **Styling**: Limited theming options (follows Workday design system)
   - **Events**: OnClick, OnChange, OnLoad handlers

**Key components in the library:**

| Component | Description |
|-----------|-------------|
| **Text** | Static or dynamic text display |
| **RichText** | Formatted text block |
| **TextInput** | Single-line text entry |
| **TextArea** | Multi-line text entry |
| **NumberInput** | Numeric entry with validation |
| **DatePicker** | Calendar date selector |
| **Dropdown** | Single-select from options |
| **MultiSelectDropdown** | Multi-select from options |
| **Checkbox** | Boolean toggle |
| **RadioGroup** | Single-select radio buttons |
| **Button** | Action trigger (submit, navigate, custom) |
| **Grid/Table** | Tabular data display |
| **Card** | Grouped content container |
| **Section** | Layout container with header |
| **Tabs** | Tabbed content panels |
| **InstanceSearch** | Workday instance search (worker picker, org picker, etc.) |
| **FileUpload** | Document/file attachment |
| **Image** | Static or dynamic image |
| **Chart** | Data visualization (bar, pie, line) |
| **Badge** | Status indicator |
| **ProgressBar** | Progress indicator |
| **Separator** | Visual divider |

### 2.6 Creating Custom Tasks and Navigation

**Tasks** are how users discover and launch your Extend app within Workday.

**Creating a Custom Task:**

1. Search for **"Create Task"** in Workday
2. Configure:
   - **Task Name**: "Create Equipment Request"
   - **Task Type**: Select "Extend App Page"
   - **Target Page**: Link to your Extend app page
   - **Category**: For search/navigation grouping
   - **Security**: Which security groups can see/execute this task

**Adding to navigation:**

1. **Dashboard integration**: Add your task as a **Worklet** on user dashboards
2. **Menu integration**: Add to functional area menus
3. **Related Actions**: Add your task to the "Related Actions" menu on Workday objects (e.g., add "Request Equipment" to the Worker related actions)
4. **Search**: Tasks are automatically searchable in the Workday search bar

**Navigation configuration example:**
```
Task: "Create Equipment Request"
  - Available from: Global search
  - Dashboard worklet: "Equipment Requests" on Manager Dashboard
  - Related Action: On Worker profile -> Actions -> "Request Equipment"
  - Security: "Equipment Request - Creator" security group
```

### 2.7 Data Binding and Expressions

Data binding connects UI components to business object fields. The binding syntax uses a path notation.

**Simple binding:**
```
{businessObject.fieldName}
```

**Nested binding (through references):**
```
{equipmentRequest.requestedBy.worker.firstName}
```

**Collection binding (for grids/tables):**
```
Data Source: {equipmentRequests}
Column bindings:
  - {item.requestDate}
  - {item.requestedBy.worker.fullName}
  - {item.status}
  - {item.estimatedCost}
```

**Conditional visibility:**
```
Visible when: {equipmentRequest.status} == "Approved"
```

### 2.8 Workday Expression Language (WEL) / Calculated Fields

WEL (also known as Calculated Fields or Condition Rules) is Workday's expression language used for computed values, validations, and conditions.

**WEL is NOT a general-purpose programming language.** It is a declarative, formula-based language similar to spreadsheet formulas.

**Key WEL functions:**

**Text functions:**
```
CONCATENATE(field1, " ", field2)     -- Join strings
LEFT(field, n)                        -- Left n characters
RIGHT(field, n)                       -- Right n characters
UPPER(field)                          -- Uppercase
LOWER(field)                          -- Lowercase
CONTAINS(field, "search")            -- Boolean contains check
LENGTH(field)                         -- String length
TRIM(field)                          -- Remove whitespace
SUBSTITUTE(field, "old", "new")      -- Replace text
```

**Numeric functions:**
```
SUM(field1, field2, field3)          -- Sum values
AVERAGE(field1, field2)              -- Average
ROUND(field, decimals)               -- Round to N decimals
MAX(field1, field2)                  -- Maximum
MIN(field1, field2)                  -- Minimum
ABS(field)                           -- Absolute value
```

**Date functions:**
```
TODAY()                               -- Current date
NOW()                                 -- Current date/time
DATEDIFF(date1, date2, "days")       -- Difference in days/months/years
DATEADD(date, n, "days")             -- Add days/months/years
YEAR(dateField)                      -- Extract year
MONTH(dateField)                     -- Extract month
DAY(dateField)                       -- Extract day
```

**Logical functions:**
```
IF(condition, trueValue, falseValue)
AND(condition1, condition2)
OR(condition1, condition2)
NOT(condition)
ISBLANK(field)                        -- Check if null/empty
COALESCE(field1, field2, default)    -- First non-null value
```

**Instance/reference functions:**
```
INSTANCE(workerRef)                   -- Dereference a worker reference
COUNT(collection)                     -- Count items in a collection
FILTER(collection, condition)        -- Filter a collection
FIRST(collection)                    -- First item in collection
```

**Calculated field example -- Full name with title:**
```
IF(
  NOT(ISBLANK({worker.title})),
  CONCATENATE({worker.title}, " ", {worker.firstName}, " ", {worker.lastName}),
  CONCATENATE({worker.firstName}, " ", {worker.lastName})
)
```

**Calculated field example -- Days since request:**
```
DATEDIFF({equipmentRequest.requestDate}, TODAY(), "days")
```

**Calculated field example -- SLA status:**
```
IF(
  DATEDIFF({request.createdDate}, TODAY(), "days") > 5,
  IF(
    {request.status} == "Submitted",
    "Overdue",
    "Completed"
  ),
  "On Track"
)
```

**Important WEL limitations:**
- No loops or iteration (use collection functions instead)
- No variables or intermediate assignments
- No string interpolation (use CONCATENATE)
- No custom function definitions
- Limited error handling (no try/catch)
- Expressions must be deterministic (no random, no external calls)
- Maximum expression complexity limit (nesting depth ~10-15 levels)

### 2.9 Orchestrations (Business Logic)

Orchestrations are Workday Extend's mechanism for implementing multi-step business logic. They are visual workflow definitions.

**Orchestration components:**

| Component | Purpose |
|-----------|---------|
| **Start** | Entry point (triggered by UI action, schedule, or API call) |
| **Integration Step** | Call external systems or Workday APIs |
| **Condition** | If/else branching |
| **Parallel** | Execute multiple branches simultaneously |
| **Loop** | Iterate over a collection |
| **Sub-orchestration** | Call another orchestration |
| **Data Transform** | Map/transform data between steps |
| **Notification** | Send Workday notifications |
| **Create/Update/Delete** | CRUD operations on business objects |
| **End** | Termination point |

**Orchestration example -- Equipment Approval:**
```
Start (triggered by "Submit Equipment Request" button)
  |
  v
Set status to "Submitted"
  |
  v
Condition: estimatedCost > 500?
  |-- YES --> Send notification to department manager
  |            |
  |            v
  |           Wait for approval (creates Workday inbox task)
  |            |
  |            v
  |           Condition: Approved?
  |             |-- YES --> Set status "Approved", notify requestor
  |             |-- NO  --> Set status "Denied", notify requestor
  |
  |-- NO  --> Auto-approve, set status "Approved"
  |
  v
End
```

**Orchestration triggers:**
- **Manual**: User clicks a button on an Extend page
- **Scheduled**: Runs on a cron-like schedule
- **Event-driven**: Triggered by a Workday business event (e.g., worker hire, termination)
- **API-triggered**: Called via a web service endpoint

### 2.10 Creating Web Service Endpoints (Custom APIs)

Extend apps can expose custom REST API endpoints that external systems can call.

**Creating an endpoint:**

1. In the App Builder, go to **Web Service Endpoints**
2. Click **Create Endpoint**
3. Configure:
   - **Endpoint Path**: e.g., `/equipmentRequests`
   - **HTTP Method**: GET, POST, PUT, DELETE
   - **Request Schema**: Define expected input fields (for POST/PUT)
   - **Response Schema**: Define output structure
   - **Security**: Which API clients / security groups can call this
   - **Orchestration**: Link to an orchestration for processing logic

**Endpoint URL pattern:**
```
https://<host>/ccx/api/apps/<tenant>/<appId>/<endpointPath>
```

**Example endpoint definition:**
```
GET /equipmentRequests
  Query params: status (optional), requestedBy (optional)
  Response: Array of Equipment Request objects
  Security: "Equipment Request - API" security group

POST /equipmentRequests
  Request body:
    {
      "equipmentType": "Laptop",
      "description": "Need new laptop for remote work",
      "requestedBy": "<worker_wid>"
    }
  Response:
    {
      "requestId": "ER-00123",
      "status": "Draft"
    }
  Orchestration: "Create Equipment Request Flow"
```

### 2.11 Using Workday Built-in APIs from Extend Apps

Within an Extend app, you can call Workday's internal APIs to read/write core Workday data.

**Methods to access Workday data from Extend:**

1. **Reference fields**: Directly reference Workday objects (Worker, Organization, etc.) in your business objects
2. **InstanceSearch component**: Let users search for Workday objects in the UI
3. **Integration Steps in Orchestrations**: Call Workday Web Services (SOAP) or REST APIs as part of business logic
4. **Calculated Fields**: Access related Workday data through reference traversal

**Common Workday data sources accessed from Extend:**

| Data Source | Common Use | Access Method |
|-------------|------------|---------------|
| Worker | Employee info | Reference field, InstanceSearch |
| Organization | Dept/team info | Reference field |
| Job Profile | Job details | Reference field |
| Location | Office/site info | Reference field |
| Cost Center | Financial allocation | Reference field |
| Manager (of worker) | Approval routing | Calculated field traversal |
| Compensation | Salary data | Integration step (restricted) |

---

## 3. Testing Extend Applications

### 3.1 Testing Philosophy in Workday

Workday Extend does **not** support traditional unit testing. There is no test framework, no test runner, no mocking library. Testing is done primarily through **manual testing in sandbox/preview tenants** and **functional/integration testing**.

This is a fundamental difference from traditional software development.

### 3.2 Testing in Sandbox Tenants

**Sandbox testing workflow:**

1. **Build** your Extend app in the sandbox tenant
2. **Configure test users** with appropriate security groups
3. **Create test data** (business object instances)
4. **Walk through each user flow** manually:
   - Create a record
   - Edit a record
   - Submit for approval
   - Approve/deny
   - View reports/dashboards
5. **Test edge cases**:
   - Required field validation
   - Boundary values (max length, min/max numbers)
   - Invalid data
   - Permissions (test with users who should NOT have access)
6. **Test orchestrations**:
   - Verify each step executes
   - Check condition branching
   - Verify notifications are sent
   - Check error handling paths

**Test user setup:**
```
Create test users (via "Create Integration System User" or use existing test workers):
  - equiptest_admin    (Full access to Equipment Request app)
  - equiptest_manager  (Can approve requests)
  - equiptest_user     (Can create/view own requests)
  - equiptest_readonly (View only)
  - equiptest_noaccess (No permissions - negative testing)
```

### 3.3 Preview and Staging Environments

**Preview tenants** serve as staging environments in Workday:

- Receive the next Workday release ~4 weeks before production
- Contain anonymized copies of production data
- Ideal for regression testing before each Workday release
- NOT the same as your development sandbox

**Testing in preview:**
1. Migrate your Extend app to the preview tenant (see Deployment section)
2. Test all functionality against the upcoming Workday release
3. Pay attention to:
   - Deprecated APIs or fields that your app uses
   - UI component changes that might affect your pages
   - Security model changes
   - New calculated field functions that could simplify your logic

### 3.4 Testing Orchestrations

Orchestrations should be tested step-by-step:

1. **Trigger testing**: Verify each trigger mechanism works
   - Button click triggers
   - Scheduled triggers (set to run in minutes for testing)
   - API-triggered (use Postman/curl)
2. **Step-by-step verification**:
   - After each step, verify the data state in the business object
   - Check integration callout responses
   - Verify condition evaluation
3. **Error path testing**:
   - Force integration failures (use invalid URLs, bad credentials)
   - Force validation failures
   - Test timeout scenarios
4. **Notification testing**:
   - Verify notification recipients
   - Check notification content
   - Test notification actions (approve/deny links)

**Orchestration monitoring:**
- Search for **"View Orchestration Instances"** in Workday
- This shows all running and completed orchestration instances
- You can see step-by-step execution details, timings, and error messages
- Filter by status: Running, Completed, Failed, Cancelled

### 3.5 Test Data Management

**Creating test data:**
- Use the Extend app UI to create test records manually
- For bulk data, use Workday's **Enterprise Interface Builder (EIB)** to load data from CSV/XML
- For API testing, use Postman to create records via your custom endpoints

**Test data considerations:**
- Sandbox data may be refreshed/reset periodically
- Document your test data setup steps
- Consider creating a "seed data" orchestration that populates test records
- Be careful with references to production workers/orgs that may not exist in sandbox

**Cleaning up test data:**
- There is no "truncate table" for business objects
- Delete records individually through the UI or via orchestrations
- In extreme cases, request a tenant refresh

### 3.6 Regression Testing Strategies

Since there's no automated testing framework, regression testing requires discipline:

1. **Maintain a test case document** (spreadsheet or Workday document):
   - Test case ID
   - Description
   - Preconditions
   - Steps
   - Expected result
   - Actual result
   - Pass/Fail
2. **Execute before each deployment** to a higher environment
3. **Execute after each Workday release** (biannual major releases)
4. **Focus areas for regression**:
   - All CRUD operations on each business object
   - All orchestration paths
   - All API endpoints
   - Security/permissions
   - Cross-browser testing (Workday supports Chrome, Firefox, Edge, Safari)
   - Mobile responsiveness (Workday mobile app)

---

## 4. Troubleshooting Common Issues

### 4.1 Debugging Techniques in Workday

**Workday does not have a traditional debugger** (no breakpoints, no step-through, no console.log).

**Available debugging approaches:**

1. **Orchestration Instance Viewer**:
   - Task: **"View Orchestration Instances"**
   - Shows step-by-step execution with input/output data
   - Shows error messages for failed steps
   - Shows timing for performance analysis

2. **Integration Event Viewer**:
   - Task: **"View Integration Events"**
   - Shows integration execution logs
   - Download integration output files
   - View request/response payloads

3. **Audit Logs**:
   - Task: **"View Audit Logs"**
   - Shows all data modifications with before/after values
   - Useful for tracking unexpected data changes

4. **Workday System Log (Syslog)**:
   - Only accessible to Workday administrators
   - Shows low-level system events
   - Useful for API authentication issues

5. **Calculated Field Testing**:
   - Task: **"Test Calculated Field"**
   - Enter sample values and see the calculated result
   - Invaluable for debugging complex WEL expressions

6. **API testing via Postman**:
   - Test endpoints independently of the UI
   - Inspect full HTTP request/response
   - Useful for isolating API-level issues from UI-level issues

### 4.2 Common Deployment Failures and Fixes

| Issue | Symptom | Fix |
|-------|---------|-----|
| **Missing security configuration** | App deploys but users can't access it | Ensure security groups and policies are included in migration; assign users to security groups in target tenant |
| **Reference field target not found** | Migration fails with "object not found" | The referenced Workday object (e.g., a specific organization) must exist in the target tenant; use tenant-agnostic references |
| **Circular dependency** | Migration fails | Break the circular reference; deploy dependent objects in order |
| **Version mismatch** | App behaves differently after migration | Check Workday version differences between source and target tenants |
| **Calculated field references** | Field shows error or blank | Referenced fields must exist in target tenant; check for tenant-specific data references |
| **Integration credentials** | Integrations fail after migration | Credentials are NOT migrated; re-enter credentials in target tenant |
| **Orchestration scheduling** | Scheduled orchestrations don't run | Schedules are NOT migrated; recreate schedules in target tenant |

### 4.3 Integration Errors and Resolution

**Common integration error patterns:**

**Authentication failures:**
```
Error: "Invalid credentials" or "401 Unauthorized"
Cause: Expired token, wrong client ID/secret, insufficient scopes
Fix:
  1. Verify client ID and secret are correct
  2. Check that the API client scope includes the needed functional area
  3. Regenerate the client secret if compromised
  4. Verify the ISU (Integration System User) is active and not locked
  5. Check ISU security group membership
```

**Permission errors:**
```
Error: "403 Forbidden" or "Insufficient permissions"
Cause: The API client or ISU lacks access to the requested resource
Fix:
  1. Check which security groups the ISU belongs to
  2. Verify domain security policies grant access
  3. Ensure the security group has the needed data source access
  4. Check constrained vs unconstrained access
```

**Data validation errors:**
```
Error: "Validation error: field X is required" or "Invalid reference"
Cause: Missing required fields or invalid reference WIDs
Fix:
  1. Review the API request payload
  2. Ensure all required fields are populated
  3. Verify WID (Workday ID) references point to valid objects
  4. Check that the instance referenced is active (not deleted/archived)
```

**Timeout errors:**
```
Error: "504 Gateway Timeout" or integration step timeout
Cause: Long-running queries, large data sets, external system slow
Fix:
  1. Add pagination to large data requests
  2. Optimize calculated fields (reduce nesting/complexity)
  3. Increase timeout settings if configurable
  4. Break large operations into smaller batches
```

### 4.4 Performance Issues and Optimization

**Common performance bottlenecks:**

1. **Calculated field complexity**: Deeply nested or chained calculated fields compute on every access
   - Fix: Simplify expressions, store computed values when possible

2. **Large grid/table renders**: Loading thousands of records
   - Fix: Add pagination, server-side filtering, lazy loading

3. **N+1 query patterns in orchestrations**: Querying one record at a time in a loop
   - Fix: Use batch operations, bulk data access patterns

4. **Unindexed searches**: Searching large custom object collections without filtering
   - Fix: Add filters to narrow results before display

5. **Integration callout chains**: Sequential external API calls
   - Fix: Use parallel orchestration branches, cache results

**Performance best practices:**
- Limit grid data to < 500 records per page
- Use server-side filtering (not client-side)
- Avoid deeply nested reference traversals (>3 levels)
- Cache integration responses when data doesn't change frequently
- Use "effective date" filtering to limit historical data

### 4.5 Tenant Configuration Issues

| Issue | Symptom | Resolution |
|-------|---------|------------|
| **Feature not enabled** | Task not found in search | Contact Workday admin to enable the feature via "Maintain Feature Toggles" |
| **Security group mismatch** | User can do action in sandbox but not production | Compare security configurations between tenants |
| **Business process not configured** | Orchestration can't initiate approval | Configure the business process in the target tenant |
| **Domain security not activated** | API returns no data despite correct permissions | Activate pending security policy changes via "Activate Pending Security Policy Changes" |
| **Tenant time zone** | Dates/times appear wrong | Check tenant-level and user-level time zone settings |
| **Data purge** | Historical data missing | Check tenant data purge policies |

**CRITICAL: Security policy activation.** After making ANY security changes in Workday, you MUST run the task **"Activate Pending Security Policy Changes"**. Until this is done, security changes are in a "pending" state and are not enforced. This is one of the most common "it works for me but not for them" issues.

### 4.6 API Authentication Problems

**OAuth 2.0 token issues:**

```
Problem: Token expires during long-running operations
Solution: Implement token refresh logic:
  1. Store the refresh token securely
  2. Before each API call, check token expiry
  3. If expired (or about to expire in <5 min), refresh
  4. Use the new access token
  Token lifetime is typically 3600 seconds (1 hour)
```

```
Problem: "invalid_grant" error on token refresh
Solution:
  1. Refresh tokens are single-use; ensure you're using the latest one
  2. Refresh tokens expire after 14 days of inactivity
  3. If expired, re-authenticate from scratch
  4. Check that the API client configuration hasn't changed
```

```
Problem: CORS errors when calling from browser
Solution:
  Workday REST APIs require CORS origin configuration in the API client.
  If you control the API client, add your domain to "Authorized CORS Origins"
  in the API client configuration (see extend-js-example for reference).
  For external apps without API client access, proxy calls through a backend.
  Within Extend apps, use orchestration integration steps instead of browser calls.
```

### 4.7 Common Error Codes

| Error Code | Description | Common Cause | Resolution |
|------------|-------------|--------------|------------|
| **INVALID_INSTANCE** | Referenced instance doesn't exist | Wrong WID or deleted object | Verify the WID; check if object was deactivated |
| **REQUIRED_FIELD** | Missing required field value | Omitted field in API call or form | Add the missing field |
| **DUPLICATE_KEY** | Unique constraint violation | Creating record with existing unique value | Check for duplicates before creating |
| **UNAUTHORIZED** | Authentication failed | Bad credentials, expired token | Re-authenticate, check credentials |
| **FORBIDDEN** | Insufficient permissions | Missing security group membership | Add user to appropriate security group |
| **VALIDATION_ERROR** | Business rule violation | Data doesn't meet validation criteria | Check validation rules on the business object |
| **INTEGRATION_FAILURE** | External system call failed | Network issue, external system down | Check external system status, retry |
| **TIMEOUT** | Operation took too long | Complex query, large dataset | Optimize query, add pagination |
| **RATE_LIMIT** | Too many API calls | Exceeded API rate limit | Add delays, implement backoff |
| **ORCHESTRATION_ERROR** | Orchestration step failed | Logic error, bad data | Check orchestration instance viewer |

---

## 5. Deployment and Release Management

### 5.1 Packaging an Extend App

Extend apps are packaged for deployment using **Workday's migration framework**. There is no separate packaging tool.

**What gets migrated:**
- Business object definitions (schema, fields, validations)
- Page definitions (UI layout, bindings)
- Orchestration definitions (workflow logic)
- Security policies (domain security, business process security)
- Custom tasks and navigation
- Web service endpoint definitions
- Calculated field definitions

**What does NOT migrate (must be configured per-tenant):**
- Business object data (the actual records/rows)
- Integration credentials (passwords, API keys)
- Scheduled orchestration triggers
- Tenant-specific configuration values
- User/security group assignments (group definitions migrate, but membership does not)

### 5.2 Migration Sets

A **Migration Set** is a collection of Workday configuration objects packaged together for deployment.

**Creating a migration set:**

1. Search for **"Create Migration Set"** in Workday
2. Name the migration set (e.g., "Equipment Tracker v1.0")
3. **Add objects** to the migration set:
   - Add your Extend app
   - Add all associated business objects
   - Add all pages, orchestrations, tasks
   - Add security groups and policies
   - Add calculated fields
4. **Review dependencies**: Workday shows if you're missing dependent objects
5. **Generate the migration package**: This creates an exportable package

**Migration IDs:**

Every object in Workday has a unique identifier called a **WID (Workday ID)**. When migrating between tenants, Workday uses a **Migration ID** (separate from the WID) to match objects across tenants.

```
Migration ID format: <namespace>_<object_identifier>
Example: mycompany_equipmentRequest_v1
```

**Important migration ID rules:**
- Migration IDs must be unique within a tenant
- Once set, migration IDs should NOT change (they are the cross-tenant identity)
- Always assign meaningful migration IDs to custom objects
- Workday auto-generates migration IDs if you don't set them (not recommended)

### 5.3 Deploying to Different Tenants

**Deployment flow:**

```
Sandbox (SBX) --> Implementation (IMPL) --> Preview --> Production (PROD)
```

**Step-by-step deployment:**

1. **Export from source tenant:**
   - Navigate to your migration set
   - Click "Deploy" or "Export"
   - Download the migration package (XML-based)

2. **Import to target tenant:**
   - In the target tenant, search for **"Import Migration Package"**
   - Upload the package file
   - Workday validates the package:
     - Checks for missing dependencies
     - Checks for migration ID conflicts
     - Checks for version compatibility
   - Review warnings and resolve issues
   - Confirm import

3. **Post-import configuration in target tenant:**
   - Re-enter integration credentials
   - Configure scheduled triggers
   - Assign users to security groups
   - Run "Activate Pending Security Policy Changes"
   - Set tenant-specific configuration values
   - Create initial data / seed data if needed

4. **Verify deployment:**
   - Log in as test users
   - Walk through all functionality
   - Check orchestration execution
   - Test API endpoints
   - Verify security permissions

### 5.4 Version Management

Workday does NOT have built-in app versioning for Extend. Recommended practices:

1. **Name your migration sets with versions**: "Equipment Tracker v1.0", "v1.1", "v2.0"
2. **Maintain a changelog document** in Workday or externally:
   ```
   ## v1.1 (2024-03-15)
   - Added "Priority" field to Equipment Request
   - Added manager auto-approval for items under $100
   - Fixed: Notification not sent on denial

   ## v1.0 (2024-02-01)
   - Initial release
   - Equipment Request creation and approval workflow
   - Manager dashboard with pending requests
   ```
3. **Use migration ID suffixes for major versions** if making breaking changes:
   - v1: `mycompany_equipmentRequest`
   - v2: `mycompany_equipmentRequest_v2` (if schema changes are breaking)
4. **Document the migration dependency order** for multi-object deployments

### 5.5 Rollback Strategies

**Workday does not have a one-click rollback mechanism for Extend apps.**

**Rollback approaches:**

1. **Re-deploy previous version**: Keep migration packages for all versions; re-import the previous version
2. **Deactivate the app**: Remove tasks/navigation pointing to the app while you fix issues
3. **Feature flags**: Implement visibility conditions on pages to hide new features
4. **Data rollback**: For data changes, you may need to:
   - Restore from backup (request from Workday support for production)
   - Manually revert via orchestrations
   - Use audit logs to identify what changed

**Rollback best practices:**
- Always keep a copy of the previous migration package before deploying
- Test rollback procedures in sandbox before ever needing them in production
- Have a "kill switch" orchestration that can disable the app quickly
- Document the rollback procedure for each deployment

### 5.6 Continuous Integration Patterns

Since Extend apps live in the Workday browser, traditional CI/CD doesn't directly apply. However, for the surrounding infrastructure:

**What CAN be in CI/CD:**
- External integration code (if you have middleware calling Workday APIs)
- API test suites (Postman/Newman, custom scripts)
- Documentation generation
- Migration package storage and versioning

**Recommended CI/CD setup for Workday ecosystem:**
```
Git Repository
├── integrations/              -- External integration code
│   ├── middleware/             -- API middleware (Node.js, Python, etc.)
│   ├── tests/                 -- API integration tests
│   └── postman/               -- Postman collections
├── docs/                      -- App documentation, changelogs
├── migration-packages/        -- Stored migration packages (version-controlled)
│   ├── v1.0/
│   ├── v1.1/
│   └── v2.0/
├── config/                    -- Tenant-specific configurations
│   ├── sandbox.env
│   ├── impl.env
│   └── prod.env
└── scripts/
    ├── deploy.sh              -- Deployment helper scripts
    └── test.sh                -- Run API tests against a tenant
```

**API test automation example (using Postman/Newman):**
```bash
#!/bin/bash
# Run API tests against sandbox
newman run postman/Equipment_API_Tests.json \
  --environment postman/sandbox_env.json \
  --reporters cli,junit \
  --reporter-junit-export results/test-results.xml
```

**Deployment checklist automation:**
```bash
#!/bin/bash
# Pre-deployment checklist
echo "=== Pre-Deployment Checklist ==="
echo "[ ] Migration package exported from sandbox"
echo "[ ] All test cases passed in sandbox"
echo "[ ] Migration package uploaded to target tenant"
echo "[ ] Import validated (no errors)"
echo "[ ] Security policies activated"
echo "[ ] Integration credentials configured"
echo "[ ] Scheduled triggers configured"
echo "[ ] Smoke test passed"
echo "[ ] Stakeholders notified"
```

---

## 6. Workday APIs

### 6.1 REST API Overview

Workday's REST API (sometimes called WQL-based or RAAS-based) provides modern HTTP access to Workday data.

**Base URL pattern:**
```
https://<host>/ccx/api/v1/<tenant>/<resource>
```

**Common resources:**

| Resource Path | Description |
|---------------|-------------|
| `/workers` | Employee and contingent worker data |
| `/workers/{id}` | Specific worker details |
| `/organizations` | Organizational hierarchy |
| `/locations` | Location data |
| `/jobProfiles` | Job profile definitions |
| `/costCenters` | Cost center data |
| `/compensationPlans` | Compensation plan data |
| `/timeOff` | Time off balances and requests |
| `/payroll` | Payroll data (restricted) |

**Example REST API calls:**

**Get all workers:**
```bash
curl -X GET \
  "https://wd5-impl-services1.workday.com/ccx/api/v1/my_tenant/workers" \
  -H "Authorization: Bearer <access_token>" \
  -H "Accept: application/json"
```

**Response:**
```json
{
  "total": 1523,
  "data": [
    {
      "id": "3aa5550b7fe348b98d7b5741afc65534",
      "descriptor": "John Smith",
      "href": "/ccx/api/v1/my_tenant/workers/3aa5550b7fe348b98d7b5741afc65534",
      "primaryWorkEmail": "john.smith@company.com",
      "primaryWorkPhone": "+1-555-0100",
      "businessTitle": "Senior Software Engineer",
      "primarySupervisoryOrganization": {
        "id": "abc123",
        "descriptor": "Engineering - Platform"
      }
    }
  ]
}
```

**Get a specific worker:**
```bash
curl -X GET \
  "https://wd5-impl-services1.workday.com/ccx/api/v1/my_tenant/workers/3aa5550b7fe348b98d7b5741afc65534" \
  -H "Authorization: Bearer <access_token>"
```

**Search workers with filters:**
```bash
curl -X GET \
  "https://wd5-impl-services1.workday.com/ccx/api/v1/my_tenant/workers?search=john&limit=10&offset=0" \
  -H "Authorization: Bearer <access_token>"
```

### 6.2 WQL (Workday Query Language)

WQL is a SQL-like query language for the REST API.

**WQL endpoint:**
```
GET /ccx/api/wql/v1/<tenant>?query=<wql_query>
```

**WQL syntax:**
```sql
SELECT worker, fullName, businessTitle, primaryWorkEmail
FROM allActiveWorkers
WHERE primarySupervisoryOrganization = '<org_wid>'
ORDER BY fullName ASC
LIMIT 100 OFFSET 0
```

**URL-encoded example:**
```bash
curl -X GET \
  "https://wd5-impl-services1.workday.com/ccx/api/wql/v1/my_tenant?query=SELECT%20worker%2C%20fullName%20FROM%20allActiveWorkers%20WHERE%20primarySupervisoryOrganization%20%3D%20'abc123'%20LIMIT%2010" \
  -H "Authorization: Bearer <access_token>"
```

**WQL data sources (FROM clause):**
- `allActiveWorkers` -- All active employees and contingent workers
- `allWorkers` -- All workers including terminated
- `allOrganizations` -- Organization hierarchy
- `allJobProfiles` -- Job profile definitions
- `allLocations` -- Location data
- `allCostCenters` -- Cost center data

**WQL operators:**
```sql
=, !=, <, >, <=, >=
LIKE '%pattern%'
IN ('value1', 'value2')
IS NULL, IS NOT NULL
AND, OR, NOT
```

### 6.3 SOAP/WS API (Web Services)

Workday's SOAP-based Web Services are the older but more comprehensive API. Many operations are only available via SOAP.

**WSDL discovery:**
```
https://<host>/ccx/service/<tenant>/<service_name>?wsdl
```

**Common SOAP services:**

| Service | Description | Key Operations |
|---------|-------------|----------------|
| **Human_Resources** | Worker data management | Get_Workers, Put_Worker, Hire_Employee |
| **Staffing** | Position and staffing | Get_Positions, Put_Position |
| **Recruiting** | Job requisitions, candidates | Get_Job_Requisitions, Put_Candidate |
| **Compensation** | Compensation data | Get_Compensation_Plans |
| **Benefits_Administration** | Benefits enrollment | Get_Benefit_Plans |
| **Payroll** | Payroll processing | Get_Payroll_Results |
| **Time_Tracking** | Time entry and approval | Get_Time_Entry |
| **Absence_Management** | Time off requests | Get_Time_Off_Balance |
| **Financial_Management** | Financial data | Get_Journal_Entries |
| **Integrations** | Integration management | Get_Integration_Events |
| **Tenant_Data_Translation** | Reference data | Get_Tenant_Data_Translation |

**SOAP request structure:**
```xml
<env:Envelope xmlns:env="http://schemas.xmlsoap.org/soap/envelope/"
              xmlns:wd="urn:com.workday/bsvc">
  <env:Header>
    <wsse:Security>
      <wsse:UsernameToken>
        <wsse:Username>ISU_username@tenant</wsse:Username>
        <wsse:Password>ISU_password</wsse:Password>
      </wsse:UsernameToken>
    </wsse:Security>
  </env:Header>
  <env:Body>
    <wd:Get_Workers_Request wd:version="v42.0">
      <wd:Request_References>
        <wd:Worker_Reference>
          <wd:ID wd:type="Employee_ID">12345</wd:ID>
        </wd:Worker_Reference>
      </wd:Request_References>
      <wd:Response_Filter>
        <wd:Page>1</wd:Page>
        <wd:Count>100</wd:Count>
      </wd:Response_Filter>
      <wd:Response_Group>
        <wd:Include_Personal_Information>true</wd:Include_Personal_Information>
        <wd:Include_Employment_Information>true</wd:Include_Employment_Information>
        <wd:Include_Compensation>false</wd:Include_Compensation>
      </wd:Response_Group>
    </wd:Get_Workers_Request>
  </env:Body>
</env:Envelope>
```

**SOAP response structure:**
```xml
<env:Envelope>
  <env:Body>
    <wd:Get_Workers_Response>
      <wd:Response_Results>
        <wd:Total_Results>1</wd:Total_Results>
        <wd:Total_Pages>1</wd:Total_Pages>
        <wd:Page_Results>1</wd:Page_Results>
        <wd:Page>1</wd:Page>
      </wd:Response_Results>
      <wd:Response_Data>
        <wd:Worker>
          <wd:Worker_Reference>
            <wd:ID wd:type="WID">abc123def456</wd:ID>
            <wd:ID wd:type="Employee_ID">12345</wd:ID>
          </wd:Worker_Reference>
          <wd:Worker_Data>
            <wd:Worker_ID>12345</wd:Worker_ID>
            <wd:Personal_Data>
              <wd:Name_Data>
                <wd:Legal_Name_Data>
                  <wd:Name_Detail_Data>
                    <wd:First_Name>John</wd:First_Name>
                    <wd:Last_Name>Smith</wd:Last_Name>
                  </wd:Name_Detail_Data>
                </wd:Legal_Name_Data>
              </wd:Name_Data>
            </wd:Personal_Data>
          </wd:Worker_Data>
        </wd:Worker>
      </wd:Response_Data>
    </wd:Get_Workers_Response>
  </env:Body>
</env:Envelope>
```

### 6.4 Common API Operations

**GET operations** -- Retrieve data:
```
Get_Workers          -- Retrieve worker information
Get_Organizations    -- Retrieve org hierarchy
Get_Job_Profiles     -- Retrieve job profiles
Get_Locations        -- Retrieve location data
```

**PUT operations** -- Create or update data:
```
Put_Worker           -- Update worker data
Put_Position         -- Create/update position
Put_Organization     -- Create/update organization
```

**SUBMIT operations** -- Initiate business processes:
```
Hire_Employee        -- Initiate hire process
Terminate_Employee   -- Initiate termination
Change_Job           -- Initiate job change
```

**Important:** PUT operations in Workday are **idempotent**. If the object exists (matched by reference/ID), it updates. If it doesn't exist, it creates. There is no separate POST/PUT distinction in SOAP.

### 6.5 Pagination and Large Datasets

**REST API pagination:**
```bash
# First page
GET /workers?limit=100&offset=0

# Second page
GET /workers?limit=100&offset=100

# Response includes total count for calculating pages
{
  "total": 5230,
  "data": [...]
}
```

**SOAP API pagination:**
```xml
<wd:Response_Filter>
  <wd:Page>1</wd:Page>
  <wd:Count>100</wd:Count>
</wd:Response_Filter>
```

The response tells you total pages:
```xml
<wd:Response_Results>
  <wd:Total_Results>5230</wd:Total_Results>
  <wd:Total_Pages>53</wd:Total_Pages>
  <wd:Page>1</wd:Page>
</wd:Response_Results>
```

**Pagination best practices:**
- Default page size is typically 100; max is often 999
- Always implement pagination for any data retrieval
- Use `Response_Group` in SOAP to limit fields returned (reduces payload)
- For very large datasets (>10,000 records), consider using scheduled integrations instead of real-time API calls

### 6.6 API Versioning

Workday APIs are versioned by release number (e.g., v42.0, v43.0). Workday releases twice per year (March and September).

**Version format:** `v<major>.<minor>` (e.g., `v42.0`, `v42.1`)

**Specifying version in SOAP:**
```xml
<wd:Get_Workers_Request wd:version="v42.0">
```

**Specifying version in REST:**
```
/ccx/api/v1/<tenant>/workers     (uses latest)
```

**Version lifecycle:**
- Workday supports the **current version** and **two prior versions**
- Deprecated versions are announced at least one release in advance
- Always test with the newest version in preview before upgrading

**Version changes to watch for:**
- New required fields on PUT operations
- Deprecated fields (still returned but will be removed)
- New optional fields
- Changed validation rules
- New API operations

### 6.7 Rate Limits and Throttling

Workday enforces rate limits to protect platform stability.

**General limits:**
- **Per-tenant**: Approximately 10-50 concurrent API connections (varies by tenant size/license)
- **Per-user/ISU**: Limits on concurrent sessions
- **Per-endpoint**: Some endpoints have stricter limits (e.g., payroll data)
- **Daily volume**: Limits on total daily API calls (varies by contract)

**Rate limit response:**
```
HTTP 429 Too Many Requests
Retry-After: 60
```

**Handling rate limits:**
```python
import time
import requests

def call_workday_api(url, headers, max_retries=3):
    for attempt in range(max_retries):
        response = requests.get(url, headers=headers)
        if response.status_code == 429:
            retry_after = int(response.headers.get('Retry-After', 60))
            print(f"Rate limited. Retrying in {retry_after} seconds...")
            time.sleep(retry_after)
            continue
        return response
    raise Exception("Max retries exceeded due to rate limiting")
```

**Best practices to avoid rate limits:**
- Implement exponential backoff
- Cache API responses where appropriate
- Use bulk/batch operations instead of individual calls
- Schedule intensive operations during off-peak hours
- Use pagination with reasonable page sizes (100-200)
- Avoid polling; use Workday events/notifications when possible

### 6.8 Authentication Flows

**OAuth 2.0 -- Authorization Code Flow (for user-interactive apps):**
```
1. Redirect user to:
   GET /authorize?response_type=code&client_id=<ID>&redirect_uri=<URI>&scope=<SCOPES>

2. User logs in to Workday, approves access

3. Workday redirects to your URI with authorization code:
   GET <redirect_uri>?code=<AUTH_CODE>

4. Exchange code for tokens:
   POST /token
   grant_type=authorization_code&code=<AUTH_CODE>&client_id=<ID>&client_secret=<SECRET>&redirect_uri=<URI>

5. Response: access_token, refresh_token, expires_in
```

**OAuth 2.0 -- Client Credentials Flow (for server-to-server):**
```
POST /token
grant_type=client_credentials&client_id=<ID>&client_secret=<SECRET>

Response: access_token, expires_in (no refresh token)
```

**OAuth 2.0 -- JWT Bearer Flow (for ISU-based auth):**
```
1. Create a JWT signed with your private key
2. POST /token
   grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer
   &assertion=<signed_JWT>

This is the preferred method for production integrations.
```

**SOAP Authentication (WS-Security):**
```xml
<wsse:Security>
  <wsse:UsernameToken>
    <wsse:Username>ISU_username@tenant_name</wsse:Username>
    <wsse:Password>ISU_password</wsse:Password>
  </wsse:UsernameToken>
</wsse:Security>
```

**SAML 2.0 (for SSO-integrated apps):**
- Workday acts as the Service Provider (SP)
- Your Identity Provider (IdP) issues SAML assertions
- Used for browser-based SSO, not API calls

**x509 Certificate Authentication:**
- Upload a public certificate to the ISU configuration in Workday
- Sign requests with the corresponding private key
- Most secure for production integrations

---

## 7. Advanced Patterns

### 7.1 Multi-Tenant Extend Apps

When building an Extend app intended for multiple tenants:

**Design considerations:**
1. **Avoid hardcoded references**: Don't reference specific WIDs (they differ per tenant)
2. **Use reference IDs instead of WIDs**: Reference IDs are stable across tenants
3. **Make configuration tenant-specific**: Use a "Settings" business object for tenant-specific values
4. **Test in multiple tenants**: Different tenants may have different configurations, security models, and data

**Configuration pattern:**
```
Business Object: AppConfiguration (singleton pattern)
  - settingName (Text, Key)
  - settingValue (Text)
  - description (Text)

Example records:
  { settingName: "approvalThreshold", settingValue: "500", description: "Auto-approve below this amount" }
  { settingName: "notificationEmail", settingValue: "admin@company.com", description: "Admin notifications" }
  { settingName: "maxRequestsPerDay", settingValue: "10", description: "Rate limit per user" }
```

### 7.2 Event-Driven Architectures with Workday

Workday supports event-driven patterns through several mechanisms:

**Business Process Events:**
- Configure business process steps to trigger orchestrations
- Example: When a hire event completes, trigger your Extend app to create an equipment request

**Workday Integration Cloud (WIC) Events:**
- Subscribe to Workday events from external systems
- Events are delivered via webhooks or message queues
- Event types: Worker hired, terminated, promoted, compensated, etc.

**Scheduled orchestrations as pseudo-events:**
- Run an orchestration every N minutes to check for changes
- Compare with last-checked timestamp
- Process new/changed records

**Event pattern example:**
```
Event: Worker Hired
  |
  v
Business Process Step: "Post-Hire Integration"
  |
  v
Orchestration: "New Hire Equipment Setup"
  |
  v
Create Equipment Request (auto-populated)
  |
  v
Notify Manager for Approval
```

### 7.3 Custom Notifications

Workday Extend apps can send notifications through Workday's built-in notification system.

**Notification types:**
- **Inbox tasks**: Action-required items in the user's Workday inbox
- **Notifications**: Informational messages in the notification feed
- **Email notifications**: Triggered by Workday notification configuration

**Creating notifications from orchestrations:**
```
Orchestration Step: Send Notification
  Recipients: {request.approver}
  Type: Inbox Task
  Subject: "Equipment Request Requires Approval"
  Body: "Equipment request from {request.requestedBy.fullName} for {request.equipmentType}"
  Actions:
    - Approve (triggers approval orchestration)
    - Deny (triggers denial orchestration)
    - View Details (navigates to request detail page)
```

**Notification best practices:**
- Don't over-notify; consolidate where possible
- Use inbox tasks for action-required items only
- Use notifications for informational items
- Include enough context in the notification body
- Provide direct action links when possible

### 7.4 File Handling and Document Management

**Document handling in Extend:**

1. **FileUpload component**: Allows users to upload files through the UI
2. **Document business object**: Store file metadata (name, type, size, upload date)
3. **Workday Drive**: Workday's internal document storage
4. **External storage**: For large files, consider storing in external systems (S3, Azure Blob) with metadata in Workday

**File upload pattern:**
```
Business Object: Document
  - fileName (Text)
  - fileType (Text)
  - fileSize (Number)
  - uploadedBy (Reference -> Worker)
  - uploadDate (DateTime)
  - relatedRequest (Reference -> Equipment Request)
  - documentContent (File/Attachment type)
```

**File size limits:**
- Workday typically limits file uploads to 4MB per file through the standard UI
- For larger files, use integration-based approaches (EIB, REST API)
- Document storage counts against tenant storage allocation

### 7.5 Batch Processing Patterns

For operations on large datasets:

**Pattern 1: Scheduled batch orchestration**
```
Orchestration: "Nightly Equipment Review" (Scheduled: daily at 2 AM)
  |
  v
Query: Get all Equipment Requests where status = "Approved" AND fulfillmentDate is blank
  |
  v
Loop: For each request
  |-- Check if item is available in inventory (external API call)
  |-- If available: Update status to "Fulfilling", create fulfillment record
  |-- If not available: Check if order placed
  |     |-- If no order: Create purchase order (external API call)
  |     |-- If order exists: Check delivery date
  |
  v
Send daily summary notification to admin
```

**Pattern 2: EIB-based bulk operations**
```
For loading large amounts of data:
1. Prepare CSV/XML file with data
2. Upload via Enterprise Interface Builder (EIB)
3. EIB maps columns to business object fields
4. Workday processes in batch
5. Review results/errors in integration event log
```

**Pattern 3: Chunked API processing**
```python
def process_all_workers(tenant_url, token):
    offset = 0
    page_size = 100
    total_processed = 0

    while True:
        response = requests.get(
            f"{tenant_url}/ccx/api/v1/my_tenant/workers",
            params={"limit": page_size, "offset": offset},
            headers={"Authorization": f"Bearer {token}"}
        )
        data = response.json()
        workers = data.get("data", [])

        if not workers:
            break

        for worker in workers:
            process_worker(worker)  # Your processing logic
            total_processed += 1

        offset += page_size
        time.sleep(1)  # Respect rate limits

    return total_processed
```

### 7.6 Integration with External Systems

**Outbound integrations (Workday calling external systems):**

Use Integration Steps in orchestrations:

```
Orchestration Step: Call External System
  URL: https://api.external-system.com/equipment/order
  Method: POST
  Headers:
    Authorization: Bearer {config.externalApiKey}
    Content-Type: application/json
  Body:
    {
      "itemType": "{request.equipmentType}",
      "employeeName": "{request.requestedBy.fullName}",
      "deliveryLocation": "{request.requestedBy.location.name}",
      "budget": "{request.estimatedCost}"
    }
  Response Mapping:
    externalOrderId -> request.externalOrderId
    estimatedDelivery -> request.estimatedDeliveryDate
  Error Handling:
    On failure -> Set status "Integration Error", notify admin
```

**Inbound integrations (external systems calling Workday):**

Via custom API endpoints:
```
External System --> HTTPS POST --> Workday Extend API Endpoint --> Orchestration --> Business Object Update
```

**Middleware pattern (recommended for complex integrations):**
```
External System <--> Middleware (AWS Lambda, Azure Function, etc.) <--> Workday APIs

Benefits:
  - Decouple external systems from Workday API changes
  - Add caching, retries, circuit breakers
  - Transform data formats
  - Handle rate limiting gracefully
  - Log all API traffic
  - Add monitoring and alerting
```

**Common external integration points:**

| External System | Integration Pattern | Protocol |
|----------------|-------------------|----------|
| ServiceNow | REST API callouts | HTTPS/REST |
| Salesforce | Middleware + REST | HTTPS/REST |
| SAP | SOAP/RFC via middleware | SOAP |
| Active Directory | Workday Integration Cloud | LDAP/SCIM |
| Slack | Webhook from orchestration | HTTPS webhook |
| Email (SMTP) | Workday notification or integration | SMTP |
| AWS S3 | Integration for file exchange | REST/SDK |
| Custom apps | Extend API endpoints | HTTPS/REST |

### 7.7 Security Model Deep Dive

Understanding Workday security is critical for Extend apps:

**Security layers:**

1. **Authentication**: Who is the user? (SSO, credentials, API token)
2. **Domain Security**: What functional areas can they access?
3. **Business Process Security**: What actions can they perform?
4. **Instance Security**: Which specific records can they see?

**Custom security for Extend apps:**

```
Security Group: "Equipment Request - Admin"
  Domain Policies:
    - Equipment Request domain: View, Modify, Delete
    - Equipment Configuration domain: View, Modify
  Business Process Policies:
    - Can approve/deny equipment requests
    - Can manage equipment types

Security Group: "Equipment Request - Manager"
  Domain Policies:
    - Equipment Request domain: View, Modify (constrained to team)
  Business Process Policies:
    - Can approve requests for their team members
  Instance Security:
    - Only sees requests from workers in their supervisory org

Security Group: "Equipment Request - User"
  Domain Policies:
    - Equipment Request domain: View (own), Create
  Instance Security:
    - Can only see their own requests

Security Group: "Equipment Request - API"
  Domain Policies:
    - Equipment Request domain: View, Modify (for integration system user)
```

**Instance security (row-level security):**
- Controls WHICH records a user can see
- Based on organizational relationships (supervisory org, cost center, etc.)
- Example: A manager can only see equipment requests from workers in their organization

---

## Appendix: Error Codes and Reference Tables

### Workday API HTTP Status Codes

| Code | Meaning | Action |
|------|---------|--------|
| 200 | Success | Process response |
| 201 | Created | Resource created successfully |
| 400 | Bad Request | Check request format, required fields |
| 401 | Unauthorized | Re-authenticate, check credentials |
| 403 | Forbidden | Check security group membership |
| 404 | Not Found | Check resource URL, WID |
| 405 | Method Not Allowed | Check HTTP method against endpoint |
| 409 | Conflict | Resource already exists or version conflict |
| 413 | Payload Too Large | Reduce request size |
| 429 | Too Many Requests | Implement backoff, wait and retry |
| 500 | Internal Server Error | Retry; if persistent, contact Workday support |
| 502 | Bad Gateway | Retry; transient network issue |
| 503 | Service Unavailable | Retry; Workday maintenance window |
| 504 | Gateway Timeout | Reduce request complexity, add pagination |

### SOAP Fault Codes

| Fault Code | Meaning |
|------------|---------|
| `INVALID_ID_TYPE_ERROR` | The ID type specified doesn't match the object |
| `PROCESSING_ERROR` | General processing failure (check detail message) |
| `VALIDATION_ERROR` | Data validation failed |
| `INVALID_REFERENCE` | Referenced object not found |
| `AUTHORIZATION_ERROR` | ISU lacks permission |
| `VERSION_ERROR` | API version not supported |

### Workday Release Calendar (Approximate)

| Release | Preview Available | Production Deploy |
|---------|------------------|------------------|
| Spring (e.g., 2025R1) | ~January | March |
| Fall (e.g., 2025R2) | ~July | September |

### Key Workday Search Tasks

| Task Name | Purpose |
|-----------|---------|
| `Create App` | Start a new Extend app |
| `View App` | Open an existing Extend app |
| `Create Business Object` | Create a custom data object |
| `Create Task` | Create a navigation task |
| `Register API Client for Integrations` | Set up OAuth client |
| `Create Integration System User` | Create ISU |
| `View Integration Events` | Debug integrations |
| `View Orchestration Instances` | Debug orchestrations |
| `Activate Pending Security Policy Changes` | Apply security changes |
| `Create Migration Set` | Package for deployment |
| `Import Migration Package` | Deploy to tenant |
| `Maintain Feature Toggles` | Enable/disable features |
| `Test Calculated Field` | Debug WEL expressions |
| `View Audit Logs` | Track data changes |
| `Create Security Group` | Set up permissions |
| `Create Domain Security Policy` | Configure access policies |

### Useful Community Resources

| Resource | URL | Content |
|----------|-----|---------|
| Workday Community | `community.workday.com` | Forums, docs, downloads |
| Developer Portal | `developer.workday.com` | API docs, SDK, tutorials |
| Workday Pro Certification | Community > Learning | Extend certification path |
| REST API Reference | Developer Portal > API Reference | OpenAPI specs |
| SOAP API Reference | Developer Portal > Web Services | WSDL documentation |
| Extend Documentation | Community > Product Documentation > Extend | Official Extend docs |
| Brainstorm (Ideas) | Community > Brainstorm | Feature requests |

---

## Summary of Key Gotchas for AI Agents

1. **There is no local file-based development for Extend apps.** Everything is built in the browser-based App Builder within a Workday tenant.

2. **Security policy changes must be activated.** After ANY security change, run "Activate Pending Security Policy Changes" or changes won't take effect.

3. **Credentials do not migrate between tenants.** Always re-enter integration credentials after deploying to a new tenant.

4. **WIDs are tenant-specific.** Never hardcode WIDs; use Reference IDs or configuration objects instead.

5. **Workday APIs require CORS configuration.** Browser-based JavaScript requires the calling domain to be added to "Authorized CORS Origins" in the API client configuration. Without this, browser calls are blocked. Within Extend apps, use orchestration integration steps rather than direct browser calls. ([source: extend-js-example](https://github.com/Workday/extend-js-example))

6. **PUT is idempotent in SOAP.** PUT creates if the object doesn't exist, updates if it does. There is no separate create operation.

7. **There is no automated testing framework.** Testing is manual, tenant-based, and requires documented test cases.

8. **Extend requires a separate license.** Not all Workday customers have access to Extend.

9. **Workday releases break things.** Always test your Extend app in the preview tenant before each biannual release.

10. **Rate limits are real.** Implement exponential backoff and respect `Retry-After` headers.

11. **Refresh tokens are single-use.** Always store the latest refresh token; the previous one becomes invalid after use.

12. **Migration IDs are your cross-tenant identity.** Set them intentionally and never change them after initial deployment.
