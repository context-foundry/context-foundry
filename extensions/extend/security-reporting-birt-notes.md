# Workday Extend: Security, Reporting, and BIRT -- Comprehensive Developer Notes

These notes are written for AI agents building Workday Extend applications. They cover the Workday security model, reporting infrastructure, BIRT report templates, Prism Analytics, and audit/compliance considerations as they relate to Extend development.

---

## 1. Workday Security Model for Extend

### 1.1 Core Security Concepts

Workday uses a **configurable security framework** that controls access to every piece of data, every task, every report, and every integration. Security is NOT role-based in the traditional RBAC sense -- it is a multi-layered model built on **security domains**, **security policies**, **security groups**, and **functional areas**.

Key principle: **Security is evaluated at runtime.** When a user or integration attempts to access data or perform an action, Workday checks all applicable security policies to determine whether access is permitted. There is no "superuser" or "root" in Workday -- even tenant administrators have explicitly granted permissions.

### 1.2 Security Domains

A **security domain** is a logical grouping of related securable items (tasks, reports, data elements). Think of it as a namespace for security.

Examples of security domains:
- `Worker Data: Personal Information` -- controls access to names, addresses, dates of birth
- `Worker Data: Compensation` -- controls access to salary, pay grade, comp history
- `Worker Data: Employment Data` -- controls access to hire dates, termination dates, positions
- `Staffing: Position Management` -- controls access to position-related tasks
- `Benefits Administration` -- controls access to benefit enrollment tasks and data
- `Integration: Build` -- controls ability to create and manage integrations
- `Custom Report Creation` -- controls ability to create custom reports

Security domains contain **securable items** which are the actual resources:
- **Reports** -- specific report definitions
- **Tasks** -- business process steps, configuration tasks
- **Data** -- specific business object fields and related data

### 1.3 Security Policies

There are two types of security policies:

#### Domain Security Policies (DSPs)

Domain Security Policies control **which security groups** can access the items in a security domain and **what type of access** they have.

Access types for DSPs:
- **Get** -- Read/view access to data
- **Put** -- Write/modify access to data
- **View** -- Ability to see reports
- **Modify** -- Ability to run tasks

Example DSP configuration:
```
Security Domain: Worker Data: Personal Information
  Security Group: HR Partner          -> Get, Put
  Security Group: Manager             -> Get (only)
  Security Group: Employee as Self    -> Get (own data only)
  Security Group: Benefits Partner    -> Get (only)
```

#### Business Process Security Policies (BPSPs)

BPSPs control who can **initiate** or **participate in** specific business process steps (approvals, reviews, to-dos). These are configured on the business process definition itself rather than through domain security.

### 1.4 Functional Areas

A **functional area** is a high-level organizational grouping of security domains. Functional areas map to Workday product modules.

Examples:
- **HCM Core** -- Worker data, staffing, job management
- **Benefits** -- Enrollment, benefit plans, life events
- **Payroll** -- Pay calculations, payroll runs, tax configuration
- **Recruiting** -- Requisitions, candidates, job postings
- **Learning** -- Courses, enrollments, completions
- **Financial Management** -- Ledger, journals, accounting
- **Extend** -- Custom applications, custom objects, APIs

For Extend apps, the relevant functional areas include:
- **Extend** -- The core functional area for custom app permissions
- Any functional area whose data the Extend app needs to read/write

When you deploy an Extend app, you must declare which functional areas and security domains it requires. The tenant administrator then grants appropriate access through security policies.

### 1.5 Security Groups

Security groups are the mechanism by which users are granted permissions. There are several types:

#### Role-Based Security Groups (most common)
Assigned to users based on their **role assignment** in the organization. The role is assigned on an organizational unit (supervisory org, company, cost center, etc.).

Examples:
- **HR Partner** -- Assigned to specific supervisory orgs
- **Benefits Partner** -- Assigned to specific companies
- **Compensation Partner** -- Assigned to specific supervisory orgs
- **Manager** -- Automatically assigned based on supervisory hierarchy
- **Employee as Self** -- Automatically assigned to every active employee

Important: Role-based security groups are **constrained** -- the user only has permissions for workers/data within the organizational scope where the role is assigned. An HR Partner for "US Operations" org cannot see data in "UK Operations" org.

#### User-Based Security Groups
Explicitly assigned to specific users. NOT constrained to any organizational scope -- the user gets access across the entire tenant.

Examples:
- **Integration Build** -- Grants ability to build integrations
- **Report Administrator** -- Grants ability to create custom reports
- **Setup: Tenant Setup - Extend** -- Grants ability to manage Extend apps

#### Unconstrained Security Groups
Grant access to data/tasks **across all organizations** without organizational scoping. Use sparingly.

Example: `All Workers` -- a group that automatically includes every active worker. If a DSP grants `Get` to `All Workers` for a domain, then every worker can see that data for every other worker.

#### Constrained Security Groups
Grant access that is **limited to a specific organizational scope**. Most role-based groups are constrained.

The constraint is typically:
- **Supervisory Organization** and subordinate orgs
- **Company**
- **Cost Center**
- **Region**
- **Custom Organization**

#### Intersection Security Groups
Combine two or more security groups using AND logic. A user must be a member of ALL constituent groups to be in the intersection group. Useful for creating narrow, specific access grants.

Example: `Manager AND US Workers` -- only managers whose workers are in US organizations.

#### Aggregation Security Groups
Combine two or more security groups using OR logic. A user who is a member of ANY constituent group is in the aggregation group. Used to simplify policy assignments.

Example: `HR Partner OR Compensation Partner` -- anyone who is either role.

### 1.6 How Extend Apps Declare Security Requirements

When building a Workday Extend app, security is declared at multiple levels:

#### App-Level Security Configuration

In the Extend app's `app.json` (or the Extend App definition in the tenant), you declare:

1. **Required Security Domains** -- Which domains your app needs access to
2. **Access Types** -- Get, Put, View, Modify for each domain
3. **Custom Security Domains** -- If your app creates new custom objects, it auto-creates a security domain for them
4. **API Permissions** -- Which Workday APIs the app will call

Example conceptual app security declaration:
```json
{
  "security": {
    "requiredDomains": [
      {
        "domain": "Worker Data: Personal Information",
        "access": ["Get"]
      },
      {
        "domain": "Worker Data: Employment Data",
        "access": ["Get"]
      },
      {
        "domain": "Custom Object: My App Data",
        "access": ["Get", "Put"]
      }
    ],
    "apiPermissions": [
      "Workday REST API: Workers",
      "Workday REST API: Organizations"
    ]
  }
}
```

#### Runtime Security Enforcement

At runtime, when the Extend app's code calls a Workday API or accesses data:
1. Workday evaluates the security context of the **current user** (not the app itself)
2. The user must have the required security group memberships
3. Constrained access is enforced -- the user only sees data within their org scope
4. If the app uses a service account (ISU), that account's security groups apply

#### Custom Objects Security

When an Extend app defines **custom business objects** (custom data stored in Workday), Workday automatically creates:
- A security domain for the custom object (e.g., `Custom Object: Equipment Tracking`)
- The app developer configures which security groups get Get/Put access to this domain
- This integrates with the standard DSP framework

### 1.7 Authentication and Authorization for Extend APIs

#### OAuth 2.0

Workday uses **OAuth 2.0** as the primary authentication mechanism for API access. The supported grant types are:

1. **Authorization Code Grant** -- For user-facing Extend apps that act on behalf of a signed-in user. This is the standard flow for Extend UI apps.

2. **Client Credentials Grant** -- For server-to-server integrations and background processes. Uses an Integration System User (ISU) identity.

3. **JWT Bearer Token Grant** -- For service-to-service authentication using signed JWTs.

#### API Client Configuration

To set up OAuth for an Extend app:

1. **Register an API Client** in the Workday tenant:
   - Navigate to `Register API Client` task
   - Provide client name and description
   - Select **Client Grant Type**: Authorization Code, Client Credentials, or JWT Bearer
   - Configure **Redirect URIs** (for Authorization Code flow)
   - Select **Scope (Functional Areas)**: Choose which functional areas the client can access
   - Workday generates a **Client ID** and **Client Secret**

2. **Configure Token Endpoint**:
   - Token URL: `https://<tenant>.workday.com/ccx/oauth2/<tenant>/token`
   - Authorization URL: `https://<tenant>.workday.com/authorize`

3. **Map to Integration System User** (for Client Credentials):
   - Create an ISU
   - Assign security groups to the ISU
   - Map the API Client to the ISU in `Manage API Client` or `Register API Client for Integrations`

Example OAuth 2.0 token request (Client Credentials):
```http
POST /ccx/oauth2/{tenant}/token HTTP/1.1
Host: {host}.workday.com
Content-Type: application/x-www-form-urlencoded

grant_type=client_credentials
&client_id={client_id}
&client_secret={client_secret}
```

Example OAuth 2.0 token request (Authorization Code):
```http
POST /ccx/oauth2/{tenant}/token HTTP/1.1
Host: {host}.workday.com
Content-Type: application/x-www-form-urlencoded

grant_type=authorization_code
&code={authorization_code}
&redirect_uri={redirect_uri}
&client_id={client_id}
&client_secret={client_secret}
```

#### Scopes and Functional Areas

OAuth scopes in Workday map to **functional areas**. When registering an API client, you select which functional areas the client can access. This creates an outer boundary -- the client can never access data outside these functional areas, even if the underlying ISU or user has broader security.

Common scopes for Extend apps:
- `Tenant Non-Configurable` -- Basic tenant information
- `Human Resources` -- HCM data access
- `Staffing` -- Position and staffing data
- `Benefits` -- Benefits data
- `Payroll` -- Payroll data
- `System` -- System configuration and metadata

### 1.8 Integration System Users (ISUs)

An **Integration System User (ISU)** is a non-human user account used for integrations and background processes. ISUs are critical for Extend apps that need to perform operations outside the context of a logged-in user.

#### Creating an ISU

1. Navigate to `Create Integration System User` task
2. Provide:
   - **User Name**: e.g., `ISU_ExtendApp_EquipmentTracker`
   - **Password**: Strong password (stored in Workday)
   - **Session Timeout**: Typically 0 (no timeout for integrations)
   - **Do Not Allow UI Sessions**: Check this for security -- prevents the ISU from logging into the Workday UI

3. Assign security groups to the ISU:
   - Navigate to `Security Group Membership: Assign` or manage from the ISU's profile
   - Add the ISU to relevant **Integration Security Groups** or **User-Based Security Groups**
   - Common groups: `Integration Build`, specific functional integration groups

4. Optionally constrain the ISU:
   - Add the ISU to constrained security groups with specific organizational scope
   - This limits what data the ISU can access

#### ISU Best Practices

- **One ISU per integration/app** -- Do not share ISUs across multiple Extend apps
- **Least privilege** -- Only grant the minimum security groups needed
- **Naming convention** -- Use clear naming: `ISU_<AppName>_<Purpose>`
- **Password rotation** -- Implement regular password rotation schedules
- **Audit trail** -- ISU actions are logged in Workday audit logs
- **Disable unused ISUs** -- Deactivate ISUs for decommissioned apps
- **Do Not Allow UI Sessions** -- Always enable this for ISUs

#### ISU Security Group Assignment Pattern

A typical ISU security setup for an Extend app:

```
ISU: ISU_ExtendApp_EquipmentTracker
  Security Groups:
    - Integration System Security Group: "ISG Equipment Tracker" (custom, user-based)
        -> Grants Get access to Worker Data: Personal Information
        -> Grants Get access to Worker Data: Employment Data
        -> Grants Get/Put access to Custom Object: Equipment Tracking
    - Integration System Security Group: "Workday REST API" (system)
        -> Grants access to REST API endpoints
```

### 1.9 Tenant-Level Security Configuration for Extend Apps

#### Deploying an Extend App's Security

When an Extend app is deployed to a tenant:

1. **Review Security Requirements**: The tenant administrator reviews the app's declared security needs
2. **Create/Update DSPs**: Configure domain security policies to grant the app's security groups access to required domains
3. **Create Security Groups**: If the app needs custom security groups, create them
4. **Activate Security Policy Changes**: All DSP changes require activation via the `Activate Pending Security Policy Changes` task -- changes are NOT live until activated
5. **Test in Sandbox**: Always test security changes in a sandbox/preview tenant first

#### Security Policy Activation

This is a critical concept. Security policy changes in Workday are **staged** and must be explicitly activated:

1. Make changes to DSPs or BPSPs
2. Review changes via `View Security Policy Changes` report
3. Run `Activate Pending Security Policy Changes`
4. Changes take effect immediately upon activation
5. If something goes wrong, use `Rollback Security Policy Changes` to revert

#### Authentication Policies

Workday also supports **authentication policies** that control HOW users authenticate:
- Password-based authentication
- SAML 2.0 SSO
- Multi-Factor Authentication (MFA)
- Certificate-based authentication
- OpenID Connect

For Extend apps, the authentication policy of the tenant applies. If the tenant uses SAML SSO, the Extend app's user-facing authentication will go through the same SSO flow via the OAuth 2.0 Authorization Code grant.

### 1.10 Best Practices for Least-Privilege Security Design

1. **Start with zero access and add incrementally** -- Begin with no security groups and add only what is required as you discover needs during development.

2. **Use constrained security groups when possible** -- If the app only needs to access data for a specific org or company, use constrained groups rather than unconstrained ones.

3. **Create dedicated security groups for the app** -- Do not reuse existing security groups. Create custom user-based or role-based groups specifically for the Extend app.

4. **Separate read and write access** -- Use separate security groups for Get vs. Put access. Some users may need to view data but not modify it.

5. **Use intersection security groups for narrow access** -- Combine groups to create precise access patterns.

6. **Document security requirements** -- Maintain a security matrix documenting which security groups access which domains and why.

7. **Regular security audits** -- Use the `View Domain Security Policies for Functional Area` and `View Security Group Membership` reports to audit access.

8. **Test with realistic users** -- Test the app with users who have realistic (limited) security, not just administrators with broad access.

9. **Handle security errors gracefully** -- When an Extend app encounters a security denial (403), display a meaningful message rather than a generic error.

10. **Minimize ISU scope** -- Give ISUs only the access they need. Use the `View Integration System Users` report to audit ISU permissions.

---

## 2. Workday Reporting

### 2.1 Overview

Workday has a built-in reporting engine called **Report Writer** that allows administrators to create custom reports. Reports are first-class objects in Workday -- they are stored as configuration, they respect security, and they can be exposed as web services.

Reports in Workday are divided into three categories:
- **Standard Reports** -- Pre-delivered by Workday with each release. Cannot be edited but can be copied.
- **Custom Reports** -- Created or copied by administrators using Report Writer. Fully configurable.
- **Espresso Reports** -- Code-based reports that act more like tasks. Cannot be copied or edited.

### 2.2 Report Types

#### Simple Reports
- Basic tabular output
- Limited design options
- Display primary data from a single data source
- Good for quick, straightforward data retrieval

#### Advanced Reports
- Most commonly used report type
- Traditional table with rows and columns
- Support complex filtering, sorting, grouping, and outlining
- Can combine data from related business objects via sub-filters and related data sources
- Support calculated fields
- Can include charts
- Support drill-to-report links

#### Matrix Reports
- Cross-tabular / pivot table format
- Group and summarize data across multiple dimensions
- Support aggregation functions: count, sum, average, min, max
- Allow drill-down into summarized values to see detail
- Support row and column grouping
- Can display percentages of row total, column total, or overall total
- Useful for comparative analysis

#### Composite Reports
- Combine multiple sub-reports into a single output
- Can include headers, footers, hierarchies, outlining, and styling
- Each sub-report can be a different type (advanced, matrix, etc.)
- Provide comprehensive multi-perspective views
- Good for executive dashboards and comprehensive analyses

#### Other Report Types
- **Transposed Reports** -- Swap rows for columns, useful for side-by-side comparisons
- **Search Reports** -- Optimized for searching high-volume data with facet filters
- **Nbox Reports** -- Visualize groupings across two-dimensional axes (e.g., performance vs. potential)
- **Trending Reports** -- Like matrix reports but grouped by time periods to show trends over time

### 2.3 Data Sources and Business Objects

Every Workday report starts with a **data source** (also called a **primary business object**). The data source determines what type of data the report accesses.

Examples of data sources:
- `All Workers` -- Access worker data
- `All Positions` -- Access position data
- `All Organizations` -- Access organization data
- `Expense Report Lines for Company` -- Access expense data
- `All Benefits Elections` -- Access benefits enrollment data
- `All Job Requisitions` -- Access recruiting data
- `All Learning Enrollments` -- Access learning data
- `All Custom Objects: <name>` -- Access custom object data (Extend apps!)

From the primary data source, you navigate to **related business objects** to pull in additional fields. This is done through the object model -- Workday's data is a graph of interconnected business objects.

Example navigation path:
```
All Workers
  -> Worker (primary)
    -> Personal Data
      -> Legal Name
        -> First Name
        -> Last Name
      -> Date of Birth
      -> Contact Information
        -> Email Address
    -> Employment Data
      -> Position
        -> Job Profile
        -> Supervisory Organization
      -> Hire Date
      -> Worker Type
    -> Compensation
      -> Total Base Pay
      -> Compensation Grade
```

For Extend apps, custom business objects appear as data sources, so you can create reports that query your Extend app's data alongside standard Workday data.

### 2.4 Calculated Fields

Calculated fields are custom field definitions that perform transformations, calculations, or logic on data. They are powerful building blocks used across reporting, business processes, and Extend apps.

Types of calculated fields:
- **Arithmetic** -- Math operations: add, subtract, multiply, divide
- **Concatenation** -- Combine text fields
- **Conditional (If/Then/Else)** -- Branching logic
- **Date calculations** -- Date differences, date arithmetic, fiscal period extraction
- **Lookup** -- Cross-reference data from other business objects
- **Custom List** -- Map values to categories
- **Aggregation** -- Sum, count, average across related records
- **Regular Expression** -- Pattern matching on text fields

Example calculated fields for an Extend app:
```
Field: Tenure in Years
  Type: Arithmetic
  Formula: (Current Date - Hire Date) / 365.25

Field: Full Name
  Type: Concatenation
  Formula: First Name + " " + Last Name

Field: Risk Category
  Type: Conditional
  Formula: IF Tenure < 1 THEN "New Hire"
           ELSE IF Tenure < 3 THEN "Developing"
           ELSE IF Tenure < 10 THEN "Established"
           ELSE "Veteran"
```

Calculated fields are reusable across reports and can be shared via the `Maintain Calculated Fields` task. They are also versioned and auditable.

### 2.5 Report Filters

#### Prompt-Based Filters (Runtime)

Prompts ask the user to specify filter criteria when running the report. They can be:
- **Required** (marked with red asterisk) -- The report will not run without a value
- **Optional** -- Can be left blank; the report returns all data if omitted

Prompt types:
- Single-select -- Choose one value from a list
- Multi-select -- Choose one or more values
- Date -- Pick a date or date range
- Text -- Free-text entry
- Boolean -- Yes/No toggle

Prompts can have **default values** that pre-populate, and can use **date variables** for dynamic defaults:
- `Current Date`
- `First Day of Current Month`
- `Last Day of Previous Quarter`
- `Beginning of Current Fiscal Year`

For scheduled reports, prompts support the `Determine Value at Runtime` option, which uses dynamic date variables that resolve when the report actually runs.

#### Fixed Filters (Design-Time)

Fixed filters are built into the report definition and cannot be changed by the end user:
- Filter on specific values (e.g., only active workers)
- Filter on calculated fields
- Filter on related object attributes
- Comparison operators: equals, not equals, greater than, less than, in, not in, contains, is empty, is not empty

Example fixed filter:
```
Filter: Worker Status
  Field: Active Status
  Operator: Equals
  Value: "Active"

Filter: Worker Type
  Field: Worker Type
  Operator: Not Equal To
  Value: "Contingent Worker"
```

### 2.6 RaaS (Report as a Service)

**Report as a Service (RaaS)** is one of Workday's most important features for Extend developers. It allows any custom report to be exposed as a **REST or SOAP web service endpoint**.

#### Enabling RaaS

1. In the report definition, check **Enable As Web Service**
2. Optionally check **Optimized for Performance** (recommended for large reports called via API)
3. The report becomes available at a REST URL

#### REST Endpoint Format

```
GET https://{host}/ccx/service/customreport2/{tenant}/{report_owner}/{report_name}
    ?format={json|csv|simplexml|gdata}
    &{prompt_parameter}={value}
```

Example:
```
GET https://wd5-impl-services1.workday.com/ccx/service/customreport2/mycompany/jsmith/Active_Workers
    ?format=json
    &Worker_Type!WID=d588c41a446c11de98360015c5e6daf6
```

#### Authentication for RaaS

RaaS endpoints support:
- **Basic Authentication** -- Using ISU credentials (username@tenant / password)
- **OAuth 2.0 Bearer Token** -- Using an access token obtained via OAuth flow

#### Response Formats

- **JSON** -- Most common for Extend app consumption
- **CSV** -- For file-based integrations
- **Simple XML** -- Lightweight XML
- **gData** -- Google Data protocol format

Example JSON response:
```json
{
  "Report_Entry": [
    {
      "Worker": "Logan McNeil",
      "Employee_ID": "21001",
      "Hire_Date": "2015-01-01",
      "Job_Profile": "Manager",
      "Location": "San Francisco"
    },
    {
      "Worker": "Teresa Serrano",
      "Employee_ID": "21002",
      "Hire_Date": "2018-06-15",
      "Job_Profile": "Controller",
      "Location": "New York"
    }
  ]
}
```

#### RaaS Best Practices for Extend

1. **Create dedicated reports for API consumption** -- Do not reuse UI reports for RaaS. Create slim, efficient reports with only the fields the API consumer needs.

2. **Use filters to limit data** -- Always include filters. An unfiltered report returning all workers in a large enterprise will be slow and may time out.

3. **Paginate large result sets** -- Use the `count` and `offset` query parameters:
   ```
   ?format=json&count=100&offset=0
   ?format=json&count=100&offset=100
   ```

4. **Use WIDs for filter parameters** -- When passing prompt values via URL, use Workday IDs (WIDs) rather than display names for reliability.

5. **Cache results when appropriate** -- If the data does not change frequently, cache the RaaS response in the Extend app.

6. **Monitor performance** -- Use the Process Monitor to track RaaS execution times. Reports that take too long will time out for API consumers.

### 2.7 Report Scheduling and Distribution

Reports can be scheduled to run automatically:

#### Schedule Configuration
- **Frequency**: Run now, once in future, daily, weekly, monthly, custom recurrence
- **Timing**: Specific times and days
- **Catchup Behavior**: If the tenant is down during a scheduled run, choose to skip missed runs or run once when available
- **Recurrence Range**: Start date, end date, or indefinite

#### Output Options
- **Format**: Excel, CSV, PDF
- **Retention**: How long to keep generated output files
- **Empty Report Handling**: Option to skip output generation if the report returns no results

#### Distribution (Sharing)
- Share output with specific users (they see the data as the report owner sees it, bypassing their own security)
- Email notification when report is ready
- Output available in **My Reports** (profile menu)
- Output available in **Process Monitor**

#### Accessing Scheduled Output
- **My Reports**: Profile icon > My Reports (also accessible on mobile)
- **Process Monitor**: Background processes that have run; select the process request to download from the Output Files tab
- **Schedule Future Processes Report**: View and manage all scheduled reports; take actions like edit, suspend, delete, transfer ownership

### 2.8 How Reports Integrate with Extend Apps

Reports are deeply integrated into the Extend ecosystem:

1. **Data Source for Extend UI Components**: Extend apps can embed Workday reports directly in their UI using report worklets and dashboard components.

2. **RaaS as Data API**: Extend app backend code can call RaaS endpoints to retrieve Workday data, avoiding the need to use lower-level SOAP/REST APIs for read operations.

3. **Custom Object Reporting**: When an Extend app defines custom objects, those objects automatically become available as report data sources. Administrators can create standard Workday reports over Extend app data.

4. **Report-Driven Alerts**: Custom reports can trigger alert conditions that generate notifications. Extend apps can leverage this for monitoring/notification use cases.

5. **Export to Worksheets**: Report data can be exported to Workday Worksheets for ad hoc analysis, and worksheets can use live data connections to reports to stay in sync.

6. **Discovery Boards**: Report data sources power Discovery Board visualizations, enabling drag-and-drop analytics over Extend app data.

### 2.9 Using Reports as Data Sources for Integrations and Orchestrations

#### Enterprise Interface Builder (EIB)

EIBs can use custom reports as their data source:
1. Create a custom report with the desired output columns
2. Create an EIB integration
3. Select the report as the EIB's data source
4. Map report columns to the output file format
5. Schedule the EIB to run automatically

This is the most common pattern for extracting data from Workday, including Extend app custom object data.

#### Orchestrations

Workday Orchestrations can invoke reports as steps in an automated workflow:
- Call a RaaS endpoint to retrieve data
- Process the data in subsequent orchestration steps
- Use the data to drive conditional logic, API calls, or notifications

#### Integration with External Systems

RaaS endpoints can be called by any external system that supports REST/SOAP:
- Middleware platforms (MuleSoft, Dell Boomi, Workato)
- Custom applications
- Data warehouses and ETL tools
- Other SaaS platforms

---

## 3. BIRT Reports

### 3.1 What is BIRT in Workday?

**BIRT (Business Intelligence and Reporting Tools)** is an Eclipse-based open-source reporting framework that Workday supports for creating **pixel-perfect formatted documents**. In the Workday context, BIRT is used to create **report templates** that control the visual layout and formatting of report output.

BIRT is NOT a replacement for Workday Report Writer. Instead, BIRT provides a **presentation layer** on top of Workday data. The data comes from a Workday custom report (created in Report Writer), and the BIRT template controls how that data is rendered as a formatted document.

### 3.2 When to Use BIRT vs. Standard Reports

| Aspect | Standard Workday Reports | BIRT Reports |
|--------|-------------------------|--------------|
| **Use case** | Data analysis, dashboards, exports | Formatted documents, letters, official output |
| **Output** | Tables, charts, pivot tables | Pixel-perfect PDF, printable documents |
| **Layout control** | Limited (column-based) | Full control (headers, footers, logos, tables, text blocks) |
| **Design tool** | Report Writer (in Workday) | BIRT Designer (Eclipse plugin, desktop) |
| **Examples** | Worker list, expense summary, compensation analysis | Offer letters, benefit statements, tax forms, certificates |
| **Security** | Standard Workday security | Standard Workday security (data layer) |
| **Performance** | Generally fast | Can be slower for complex layouts |

### 3.3 BIRT Architecture in Workday

The architecture has three components:

1. **Data Source** -- A Workday custom report (created in Report Writer) that provides the data
2. **BIRT Template** -- An `.rptdesign` file that defines the visual layout
3. **Output** -- Generated PDF (or other format) when the report is run

Flow:
```
User runs report
    -> Workday executes the custom report (data source)
    -> Workday passes data to the BIRT rendering engine
    -> BIRT applies the template layout
    -> PDF or other formatted output is generated
    -> User downloads/views the output
```

### 3.4 BIRT Designer (Eclipse Plugin)

BIRT templates are created using **BIRT Designer**, which is an Eclipse-based desktop application:

#### Installation
1. Download Eclipse IDE (the version compatible with your Workday release)
2. Install the BIRT Report Designer plugin from Eclipse Marketplace
3. Workday also provides a **Workday BIRT Designer** package that includes pre-configured Eclipse with the correct BIRT version and Workday-specific extensions

#### BIRT Designer Workspace

The designer provides:
- **Layout Editor** -- Drag-and-drop visual design surface
- **Data Explorer** -- Browse available data fields from the Workday data source
- **Property Editor** -- Configure properties of selected elements
- **Palette** -- UI elements: labels, text, images, tables, lists, charts, grids
- **Script Editor** -- JavaScript for dynamic content and conditional logic
- **Preview** -- Preview the report with sample data

### 3.5 Creating a BIRT Template

#### Step 1: Create the Data Source Report

First, create a Workday custom report (Advanced Report) that will provide data to BIRT:

1. Navigate to `Create Custom Report` task
2. Select report type (typically Advanced)
3. Choose the data source (business object)
4. Add all fields that the BIRT template will need
5. Configure filters and prompts
6. Save the report

Important: The BIRT template can only use fields that exist in the data source report. Plan ahead and include all necessary fields.

#### Step 2: Download the Data Source XML

1. Run the data source report to generate output
2. Export the output as XML
3. This XML becomes the sample data for BIRT template development

#### Step 3: Design the BIRT Template

In BIRT Designer:

1. **Create a new report** -- File > New > Report
2. **Define the data source** -- Point to the sample XML file
3. **Define data sets** -- Map the XML elements to data sets that BIRT can use
4. **Design the layout**:
   - Add a **Grid** for the overall page structure
   - Add **Labels** for static text (headers, titles)
   - Add **Data** elements for dynamic values from the data source
   - Add **Images** for logos or graphics
   - Add **Tables** for repeating data (one row per data record)
   - Add **Lists** for grouped data
   - Use **Text** elements for rich text (HTML formatted content)

5. **Configure page layout**:
   - Page size (Letter, A4, custom)
   - Margins
   - Orientation (portrait, landscape)
   - Header and footer regions

6. **Add expressions**:
   - BIRT uses JavaScript expressions for dynamic content
   - Example: `row["Worker_Name"]` to display a worker's name
   - Conditional display: `if (row["Status"] == "Active") { ... }`
   - Formatting: `new java.text.SimpleDateFormat("MM/dd/yyyy").format(row["Hire_Date"])`

7. **Add parameters** (optional):
   - Parameters in BIRT can map to report prompts
   - Used for dynamic titles, date ranges, etc.

#### Step 4: Upload the Template to Workday

1. Navigate to the custom report definition in Workday
2. Go to the **Advanced** tab or **BIRT Template** section
3. Upload the `.rptdesign` file
4. Associate the template with the report
5. Test by running the report

### 3.6 Data Sources in BIRT

BIRT templates in Workday connect to data through:

#### XML Data Source
The most common approach. The Workday custom report generates XML output, which BIRT consumes:

```xml
<wd:Report_Data>
  <wd:Report_Entry>
    <wd:Worker>Logan McNeil</wd:Worker>
    <wd:Employee_ID>21001</wd:Employee_ID>
    <wd:Department>Human Resources</wd:Department>
    <wd:Hire_Date>2015-01-01</wd:Hire_Date>
  </wd:Report_Entry>
  <wd:Report_Entry>
    <wd:Worker>Teresa Serrano</wd:Worker>
    <wd:Employee_ID>21002</wd:Employee_ID>
    <wd:Department>Finance</wd:Department>
    <wd:Hire_Date>2018-06-15</wd:Hire_Date>
  </wd:Report_Entry>
</wd:Report_Data>
```

#### Data Set Configuration in BIRT

In the BIRT template, configure:
1. **Data Source**: Type = XML, pointing to the report XML schema
2. **Data Set**: XPath expressions to navigate the XML:
   - Table mapping: `//wd:Report_Entry`
   - Column mapping: `wd:Worker`, `wd:Employee_ID`, etc.
3. **Column bindings**: Map data set columns to report elements

### 3.7 Report Layouts and Formatting

BIRT provides full control over document formatting:

#### Page Layout
```
+------------------------------------------+
|              [Page Header]                |
|  Company Logo    |    Report Title        |
|                  |    Date: 01/15/2025    |
+------------------------------------------+
|                                           |
|  [Body Content]                           |
|                                           |
|  Dear [Worker Name],                      |
|                                           |
|  We are pleased to confirm your           |
|  employment with [Company Name] in the    |
|  position of [Job Title].                 |
|                                           |
|  Start Date: [Hire Date]                  |
|  Department: [Department]                 |
|  Manager: [Manager Name]                  |
|                                           |
|  +------+----------+-----------+          |
|  | Item | Detail   | Amount    |          |
|  +------+----------+-----------+          |
|  | Base | Annual   | $85,000   |          |
|  | Bonus| Target % | 10%       |          |
|  +------+----------+-----------+          |
|                                           |
+------------------------------------------+
|              [Page Footer]                |
|  Page [X] of [Y]  |  Confidential         |
+------------------------------------------+
```

#### Formatting Capabilities
- **Fonts**: Any system font, size, weight, color, style
- **Borders**: Table borders, cell borders, custom line styles
- **Colors**: Background colors, foreground colors, alternating row colors
- **Alignment**: Horizontal and vertical alignment in cells
- **Spacing**: Padding, margins for individual elements
- **Page breaks**: Control where page breaks occur (before/after groups, tables)
- **Conditional formatting**: Change styles based on data values (e.g., red text for negative amounts)
- **Barcodes**: Some BIRT extensions support barcode generation
- **Images**: Static images (logos) and dynamic images (from Workday data)

### 3.8 Parameters and Prompts

BIRT parameters map to Workday report prompts:

1. **Report prompts** defined in the Workday custom report become available in the BIRT template
2. Parameters can be used for:
   - Dynamic titles: "Benefits Statement for [Year]"
   - Conditional sections: Show/hide sections based on parameter values
   - Date formatting: Display the reporting period in headers
3. In BIRT expressions, access parameters via: `params["parameter_name"].value`

### 3.9 Deploying BIRT Templates

#### Deployment Steps
1. Design and test the template locally in BIRT Designer using sample XML data
2. Upload the `.rptdesign` file to the Workday custom report definition
3. Run the report in the Workday sandbox/preview tenant
4. Verify output formatting, data binding, and page layout
5. Iterate: Download, modify, re-upload as needed
6. Deploy to production by migrating the report definition (which includes the template)

#### Version Management
- Keep template files in source control (Git)
- Name templates with version numbers: `offer_letter_v2.3.rptdesign`
- Document which Workday report version the template is designed for
- Test after Workday updates (biannual releases may affect data structures)

### 3.10 Common BIRT Use Cases

1. **Offer Letters** -- Merge worker data, compensation details, and company information into a formatted letter template

2. **Benefits Enrollment Confirmations** -- Show elected benefits, coverage levels, costs, and effective dates in a printable format

3. **Compensation Statements** -- Annual total compensation statements showing base salary, bonus, equity, benefits value

4. **Tax Forms** -- Formatted tax documents (W-2 summaries, etc.) -- note: actual tax forms like W-2 are typically system-generated

5. **Certificates** -- Training completion certificates with worker name, course name, completion date, and signatures

6. **Employee Letters** -- Promotion letters, transfer confirmations, employment verification letters

7. **Payslips** -- Formatted pay statements (in jurisdictions where Workday payroll is used)

8. **Compliance Documents** -- Formatted regulatory filings, audit reports, compliance certifications

9. **Custom Invoices** -- For organizations using Workday Financial Management, formatted invoices and purchase orders

### 3.11 BIRT Tips for Extend Developers

1. **Custom object data in BIRT**: If your Extend app has custom objects, you can create a custom report over those objects and attach a BIRT template. This lets you generate formatted documents from Extend app data.

2. **Performance**: BIRT rendering can be slow for reports with many pages. Keep BIRT reports focused -- one document per worker/entity rather than mass-generating thousands of documents in a single run.

3. **Testing**: Use the BIRT preview with a representative XML data sample. Edge cases to test:
   - Missing/null data fields
   - Very long text values (overflow handling)
   - Multiple pages (page break behavior)
   - Special characters and international text (UTF-8)

4. **Workday version compatibility**: BIRT templates may need updates after Workday releases if data source field names or structures change.

---

## 4. Workday Prism Analytics

### 4.1 Overview

**Prism Analytics** is Workday's data hub and analytics platform that allows organizations to bring in external data, combine it with Workday data, and perform advanced analytics. It extends Workday's analytics capabilities beyond the transactional data stored natively in Workday.

### 4.2 Core Components

#### Data Sources
Prism Analytics can ingest data from:
- **Workday Data Sources** -- Direct access to Workday transactional data (workers, financials, etc.)
- **External Files** -- CSV, TSV uploads (manual or automated)
- **External APIs** -- Via integrations (EIBs, Orchestrations) that push data into Prism
- **Prism Analytics API** -- REST API for programmatic data loading

#### Datasets
A **dataset** is a structured table of data in Prism:
- **Workday Data Sources** -- Pre-built datasets from Workday's transactional data
- **Custom Datasets** -- Created by uploading external data or combining sources
- Datasets have schemas (column definitions with types)
- Datasets can be refreshed on a schedule
- Datasets support versioning (full replace or append)

#### Data Categories
Prism organizes data into categories:
- **HCM** -- Worker, position, organization data
- **Financial** -- Ledger, journal, accounting data
- **Payroll** -- Pay data, deductions, taxes
- **Custom** -- Data from external sources or Extend apps

### 4.3 Discovery Boards (Prism-Powered)

**Discovery Boards** are the primary visualization tool in Prism Analytics:

- Built directly in Workday (no external tools needed)
- Access via Workday Drive
- Support multiple visualization types:
  - Bar charts, line charts, donut charts, area charts
  - Tables and pivot tables
  - KPIs (single-value highlights)
  - Heat maps, scatter plots
  - Combo charts (multiple chart types on one viz)

Key features:
- **Sheets** -- Tabs within a discovery board (up to 10 visualizations per sheet)
- **Controls** -- Interactive filters that end users can adjust
- **Drill-by** -- Explore data by additional dimensions
- **Show Details** -- View underlying data for any aggregated value
- **Related Actions** -- Create a custom report from a viz, download as PNG/CSV

#### Creating a Discovery Board

1. Navigate to Drive > Add New > Discovery Board
2. Name the discovery board
3. Select a data source (Workday data source or Prism dataset)
4. Use the builder panel to construct visualizations:
   - Drag fields to X-axis, Y-axis, Color, Size drop zones
   - Choose visualization type (chart, table, KPI)
   - Configure aggregations (sum, count, average, min, max)
5. Apply filters (sheet-level or viz-level)
6. Create controls for interactive filtering
7. Configure formatting (colors, labels, data labels)
8. Share with other users (view, edit permissions)

### 4.4 How Prism Connects to Extend Data

Extend apps can leverage Prism Analytics in several ways:

1. **Custom Object Data as Prism Data Source**: When an Extend app creates custom objects, the data stored in those objects can be exposed to Prism via custom reports. Create a custom report over the Extend app's custom objects, then use that report as a data source for a Prism dataset.

2. **Prism Analytics API**: Extend app orchestrations can use the Prism Analytics REST API to:
   - Create datasets programmatically
   - Upload data from external sources into Prism
   - Trigger dataset refreshes

3. **Combining Extend Data with Workday Data**: In Prism, you can create discovery boards that join Extend custom object data (via custom reports) with standard Workday data sources. This enables analytics that span both native and custom data.

4. **Embedding Analytics**: Discovery Board worklets can be embedded in Extend app dashboards, providing analytics visualizations directly within the Extend app UI.

### 4.5 API Access to Prism Data

#### Prism Analytics REST API

The Prism Analytics API allows programmatic interaction:

**Base URL**: `https://{host}/api/prismAnalytics/v1/{tenant}`

**Key endpoints**:

```
# List datasets
GET /datasets

# Get dataset details
GET /datasets/{datasetId}

# Create a new dataset
POST /datasets
Body: { "name": "My Dataset", "fields": [...] }

# Upload data to dataset (create a new version)
POST /datasets/{datasetId}/data
Content-Type: text/csv
Body: <CSV data>

# Create a data change task (for large uploads)
POST /dataChangeTasks
Body: {
  "datasetId": "...",
  "operation": "fullReplace"  // or "append"
}

# Upload file to data change task
PUT /dataChangeTasks/{taskId}/file
Body: <file content>

# Execute data change task
POST /dataChangeTasks/{taskId}/execute
```

**Authentication**: OAuth 2.0 Bearer Token (same as other Workday REST APIs)

**Typical workflow for loading data**:
1. Create or identify the target dataset
2. Create a data change task specifying the dataset and operation (full replace or append)
3. Upload the data file (CSV/gzip) to the data change task
4. Execute the data change task
5. Monitor the task status until completion

### 4.6 Prism Analytics Best Practices for Extend

1. **Use Prism for historical/trend analysis** -- Prism datasets can store historical snapshots that Workday transactional data does not retain.

2. **Schedule dataset refreshes** -- Keep Prism data in sync with transactional data by scheduling regular refreshes.

3. **Combine data sources** -- Prism's power is in combining external data with Workday data. Use this for benchmarking, market data comparisons, etc.

4. **Performance** -- Large datasets (millions of rows) may be slow to query. Use aggregation and filtering in the dataset/report level rather than the discovery board level.

5. **Security** -- Prism datasets inherit Workday's security framework. Ensure appropriate security policies are in place for custom datasets.

---

## 5. Audit and Compliance

### 5.1 Audit Logging for Extend Apps

Workday provides comprehensive audit logging that covers Extend app activities:

#### System Audit Logs

Workday automatically logs:
- **User sign-in/sign-out events** -- Including ISU sessions
- **Task execution** -- Every task (business process step) executed by a user or ISU
- **Data access** -- Report execution, API calls, data retrievals
- **Configuration changes** -- Changes to security policies, business processes, report definitions
- **Integration execution** -- Integration runs, including those triggered by Extend apps

#### User Activity Logging

The `User Activity` report tracks:
- Which users accessed which reports/tasks
- When access occurred (timestamps)
- What data was viewed or modified
- IP addresses and session information

#### Integration Audit

For Extend apps using integrations:
- Every integration run is logged in the Process Monitor
- Success/failure status
- Number of records processed
- Error details
- Execution duration
- Who initiated the run (user or schedule)

#### Custom Object Audit

When Extend apps modify custom object data:
- Workday logs create, update, delete operations
- The audit trail shows who made each change and when
- Previous values are retained for changed fields (history tracking)

#### API Audit

REST and SOAP API calls are logged:
- Endpoint called
- Authentication method and identity
- Request timestamp
- Response status code
- Rate limiting events

### 5.2 Relevant Audit Reports

Key reports for auditing Extend apps:

- **User Activity** -- Search for specific user/ISU activity
- **Integration Events** -- View integration run history and status
- **Task Server Events** -- View background task execution
- **Security Policy Changes Audit** -- Track changes to security policies
- **Custom Report Audit** -- Track report creation, modification, and execution
- **Login Activity** -- Track authentication events
- **View API Activity** -- API call logs

### 5.3 Compliance Requirements

#### Data Residency

- Workday stores data in the region selected during tenant provisioning
- Extend apps that store data in custom objects inherit Workday's data residency
- If an Extend app integrates with external systems, data residency for those external systems must be separately managed

#### Regulatory Compliance

Workday's platform (and by extension, Extend apps) is designed to support:
- **SOC 1 Type II** -- Financial reporting controls
- **SOC 2 Type II** -- Security, availability, processing integrity, confidentiality, privacy
- **ISO 27001** -- Information security management
- **ISO 27017** -- Cloud security
- **ISO 27018** -- Protection of personally identifiable information (PII) in the cloud
- **GDPR** -- General Data Protection Regulation (EU)
- **CCPA** -- California Consumer Privacy Act
- **HIPAA** -- Health Insurance Portability and Accountability Act (where applicable)

#### Extend App Compliance Responsibilities

When building Extend apps, developers must:
1. **Follow security best practices** -- Use least privilege, encrypt sensitive data, validate inputs
2. **Respect data classifications** -- Do not expose sensitive data (PII, PHI, financial) inappropriately
3. **Enable audit trails** -- Ensure all data modifications are traceable
4. **Handle data retention** -- Define and enforce retention policies for custom object data
5. **Support data subject requests** -- Enable data access and deletion for GDPR/CCPA compliance
6. **Document data flows** -- Maintain data flow diagrams showing where data moves

### 5.4 GDPR Considerations for Extend Apps

#### Key Requirements

1. **Right to Access (Article 15)**: Users can request all data held about them. Extend apps must be able to produce a complete export of a user's data from custom objects.

2. **Right to Erasure (Article 17)**: Users can request deletion of their data. Extend apps must support deleting or anonymizing user data from custom objects.

3. **Data Minimization (Article 5)**: Only collect and store data that is necessary for the app's purpose. Do not store excessive personal data in custom objects.

4. **Purpose Limitation (Article 5)**: Data collected for one purpose should not be repurposed. Document the purpose of each data field in custom objects.

5. **Consent Management**: If the Extend app collects data that requires consent, implement consent tracking.

6. **Data Processing Agreements**: If the Extend app integrates with third-party services, ensure DPAs are in place.

#### Workday GDPR Tools

Workday provides built-in tools that Extend apps can leverage:
- **Person Data Purge** -- Workday's mechanism for purging personal data; Extend custom object data should participate in this process
- **Data Privacy Masking** -- Workday can mask sensitive fields; configure masking for custom object fields
- **Consent Management Framework** -- Track consent for data processing activities

### 5.5 Data Retention and Archival

#### Retention Policies

For Extend apps:
1. **Define retention periods** for custom object data (e.g., 7 years for financial records, 3 years for HR records)
2. **Implement automated cleanup** using scheduled orchestrations that delete expired records
3. **Archive data** before deletion if required for compliance

#### Workday Data Retention Capabilities

- **Transaction Log Purge** -- Workday can purge old transaction logs
- **Custom Object Data**: Retention must be managed by the Extend app. Workday does not automatically purge custom object data.
- **Report Output Retention**: Scheduled report outputs have configurable retention periods

### 5.6 Change Tracking

#### Configuration Change Tracking

Workday tracks all configuration changes:
- Security policy changes
- Business process definition changes
- Report definition changes
- Integration configuration changes
- Custom object schema changes

Use the `View Setup Changes by Functional Area` report to review changes.

#### Data Change Tracking

For custom objects in Extend apps:
- Workday maintains a **business process history** for objects that go through business processes
- For direct API modifications, the **audit log** tracks who changed what and when
- Consider adding `last_modified_by` and `last_modified_date` fields to custom objects for application-level tracking

#### Migration and Deployment Tracking

When deploying Extend app updates:
- Use **migration sets** to move configuration between tenants (sandbox to production)
- Migration is audited -- who migrated what and when
- Test thoroughly in sandbox before production migration
- Maintain a deployment log/changelog for the Extend app

### 5.7 Security Audit Best Practices for Extend

1. **Regular security reviews**: Run the `Domain Security Policies for Functional Area` report quarterly to verify that security grants have not drifted from the intended design.

2. **ISU audit**: Run the `Integration System Users` report to verify that all ISUs are still needed and have appropriate access.

3. **API client audit**: Review registered API clients and their scope assignments. Remove unused clients.

4. **Access certification**: Implement periodic access reviews where security administrators verify that users still need their assigned security groups.

5. **Penetration testing**: If the Extend app has external-facing components, conduct regular security testing.

6. **Incident response**: Define a process for responding to security incidents involving the Extend app, including data breach notification procedures.

---

## 6. Cross-Cutting Concerns: How Security, Reporting, and Extend Intersect

### 6.1 Security Controls Report Data Visibility

All Workday reports (standard, custom, BIRT, RaaS) respect the security context of the user running them:
- A manager running a headcount report only sees workers in their org
- An HR Partner sees workers in their assigned organizations
- An ISU sees data according to its security group assignments

This means:
- An Extend app that displays report data to a user automatically inherits the user's data scope
- RaaS calls authenticated as an ISU return data according to the ISU's security, not the end user's security
- BIRT templates render the same template but with different data depending on who runs the report

### 6.2 Reporting on Extend App Security

You can create reports to audit your Extend app's security:
- Report on security group membership to see who has access
- Report on domain security policies to see what access is granted
- Report on user activity to see who is using the Extend app
- Report on API activity to see what API calls the app is making

### 6.3 End-to-End Pattern: Extend App with Reporting

A typical Extend app deployment includes:

1. **Custom Objects** -- Extend app data stored in Workday
2. **Security Groups** -- Custom groups granting access to the app and its data
3. **DSPs** -- Policies granting the security groups access to required domains
4. **ISU** -- Service account for background operations
5. **API Client** -- OAuth configuration for the app
6. **Custom Reports** -- Reports over custom object data (for analytics, RaaS, BIRT)
7. **BIRT Templates** -- Formatted document output from the app's data
8. **Discovery Boards** -- Ad hoc analytics over the app's data
9. **Scheduled Reports** -- Automated data delivery to stakeholders
10. **Orchestrations** -- Automated workflows triggered by data changes

---

## 7. Quick Reference: Key Tasks and Reports

### Tasks

| Task | Purpose |
|------|---------|
| `Create Security Group` | Create new security groups |
| `Edit Domain Security Policies` | Modify DSP access grants |
| `Activate Pending Security Policy Changes` | Make DSP changes live |
| `Rollback Security Policy Changes` | Revert security changes |
| `Create Integration System User` | Create ISU accounts |
| `Register API Client` | Set up OAuth clients |
| `Create Custom Report` | Create new reports |
| `Maintain Calculated Fields` | Create/edit calculated fields |
| `Schedule a Report` | Set up automated report runs |
| `Edit Custom Report` | Modify report definitions |

### Reports (for auditing/admin)

| Report | Purpose |
|--------|---------|
| `View Domain Security Policies for Functional Area` | Audit DSP configurations |
| `View Security Group Membership` | See who is in which security group |
| `User Activity` | Track user/ISU actions |
| `Integration Events` | View integration run history |
| `Active and Pending Security Policy Changes` | Review staged security changes |
| `Custom Reports` | List all custom reports in the tenant |
| `Schedule Future Processes` | Manage scheduled reports |
| `View API Activity` | Audit API calls |
| `Integration System Users` | List all ISUs |
| `Registered API Clients` | List all OAuth clients |

### Search Prefixes (for finding reports)

| Prefix | Meaning |
|--------|---------|
| `rd:` | Report Definition -- search for reports by name |
| `rdt:` | Report Definition Tag -- search by report tag |
| `bp:` | Business Process -- search for business processes |
| `sg:` | Security Group -- search for security groups |
| `dsp:` | Domain Security Policy -- search for DSPs |

---

## 8. Common Patterns and Anti-Patterns

### Patterns (Do This)

1. **Dedicated ISU per Extend app** with minimum required security groups
2. **Custom security groups** for each Extend app (do not reuse existing ones)
3. **RaaS for data retrieval** when building Extend app backends (simpler than raw SOAP/REST)
4. **BIRT for formatted output** when the app needs to generate documents
5. **Prism for cross-cutting analytics** when combining Extend data with Workday data
6. **Custom reports over custom objects** for end-user self-service analytics
7. **Security testing with constrained users** (not tenant admins)
8. **Audit logging review** as part of Extend app deployment checklist

### Anti-Patterns (Avoid This)

1. **Sharing ISUs across apps** -- Creates security audit nightmares and blast radius issues
2. **Using unconstrained security groups** when constrained groups would work -- Violates least privilege
3. **Hardcoding Workday data IDs** in BIRT templates or reports -- IDs differ between tenants; use references
4. **Skipping sandbox testing** for security policy changes -- Can lock out users in production
5. **Not paginating RaaS calls** -- Large responses will time out
6. **Forgetting to activate security policy changes** -- Changes are staged, not live, until activated
7. **Using BIRT for tabular data analysis** -- Use standard reports or Discovery Boards instead; BIRT is for formatted documents
8. **Granting Put access when only Get is needed** -- Common security over-grant
9. **Not documenting security requirements** -- Makes future audits and troubleshooting difficult
10. **Ignoring GDPR/data retention for custom objects** -- Workday does not auto-purge custom object data
