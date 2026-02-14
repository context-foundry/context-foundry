# Workday Extend: Orchestrations, Integrations, and Business Processes

## Comprehensive Developer Guide for AI Agents

---

# Part 1: Orchestrations

## 1.1 What Are Orchestrations?

Orchestrations are Workday's workflow automation engine -- a low-code/no-code framework for defining multi-step automated processes. They allow developers and administrators to chain together a sequence of operations (API calls, data transformations, approvals, notifications, conditions, and integrations) into a single executable workflow.

Orchestrations are one of the most important features in Workday Extend because they serve as the "glue" connecting Extend applications to Workday's core platform, external systems, and business processes.

**Key characteristics:**
- Orchestrations execute server-side within the Workday platform
- They are defined declaratively through the Orchestration Editor (a visual designer in Workday)
- They support both synchronous and asynchronous execution
- They can be triggered by events, schedules, or manual actions
- They have access to Workday's security model and run in a tenant's security context
- They can call Workday APIs (WQL, REST, SOAP), external APIs, and other orchestrations

## 1.2 Orchestration Architecture

An orchestration consists of:

1. **Trigger** -- What initiates the orchestration
2. **Context** -- Data available throughout the orchestration (input parameters, variables)
3. **Steps** -- The individual operations to perform
4. **Flow control** -- Conditions, parallel execution, loops
5. **Error handling** -- What happens when steps fail
6. **Output** -- Data returned when the orchestration completes

### Execution Model

Orchestrations run asynchronously by default. When triggered, they create an **orchestration instance** that tracks the execution state. Each instance has:
- A unique instance ID
- Status (Running, Completed, Failed, Cancelled)
- Start and end timestamps
- Input parameters and output values
- Step-level execution details and logs

## 1.3 Orchestration Types and Patterns

### Sequential Orchestrations
The most common pattern. Steps execute one after another in order. Each step can use the output of previous steps.

```
Trigger -> Step 1 (Get Worker Data) -> Step 2 (Transform) -> Step 3 (Send to External System) -> End
```

### Parallel Orchestrations
Multiple steps execute concurrently. The orchestration waits for all parallel branches to complete before continuing. Useful for independent operations that do not depend on each other.

```
Trigger -> Parallel Start
            |-> Branch A: Call System 1
            |-> Branch B: Call System 2
            |-> Branch C: Send Notification
          Parallel End -> Step 4 (Aggregate Results) -> End
```

### Conditional Orchestrations
Steps execute based on conditions evaluated at runtime. Conditions can reference orchestration variables, step outputs, or Workday data.

```
Trigger -> Step 1 (Get Data) -> Condition (Is Manager?)
            |-> True: Step 2a (Manager Approval Flow)
            |-> False: Step 2b (Auto-Approve)
          -> Step 3 (Complete) -> End
```

### Sub-Orchestration Pattern
Orchestrations can call other orchestrations as steps. This enables:
- Reusable orchestration components
- Separation of concerns
- Modular design
- Easier testing of individual parts

### Loop/Iteration Pattern
Orchestrations can iterate over collections. For example, processing each worker in a list:

```
Trigger -> Step 1 (Get Worker List) -> For Each Worker:
            |-> Step 2 (Process Worker)
            |-> Step 3 (Update Record)
          End Loop -> Step 4 (Summary) -> End
```

## 1.4 Triggers

### Event-Based Triggers
Orchestrations can be triggered by Workday business events:
- **Business Process Events**: When a business process step completes (e.g., Hire, Termination, Job Change)
- **Data Change Events**: When specific data changes in Workday (e.g., a worker's address is updated)
- **Custom Object Events**: When records in custom Workday objects are created, updated, or deleted
- **Extend App Events**: When an Extend application raises a custom event

Configuration example (conceptual):
```
Trigger Type: Business Process Event
Event: Hire Employee - Complete
Condition: Worker Type = "Regular"
```

### Scheduled Triggers
Orchestrations can run on a schedule:
- **Recurring**: Daily, weekly, monthly, custom cron-like schedules
- **One-time**: Execute at a specific date/time
- Schedules are configured in the orchestration definition
- Time zone aware

### Manual Triggers
- Triggered by a user action in an Extend app (button click, form submission)
- Triggered via API call (REST endpoint for the orchestration)
- Triggered from a task or report action

### API Triggers
Orchestrations expose REST endpoints that external systems can call:
- Endpoint pattern: `https://<tenant>.workday.com/api/orchestrations/v1/<orchestration-id>/run`
- Accepts JSON payload matching the orchestration's input parameters
- Returns orchestration instance ID for status tracking
- Authenticated via OAuth 2.0 or Workday API credentials

## 1.5 Steps and Step Types

### Integration Step
Calls an external or internal API:
- **REST API Call**: HTTP GET, POST, PUT, PATCH, DELETE to any URL
- **SOAP API Call**: Call Workday's SOAP web services (WWS)
- **Workday REST API**: Call Workday's internal REST APIs
- Supports request/response mapping
- Can include headers, query parameters, request body
- Response can be mapped to orchestration variables

Configuration:
```
Step Type: Integration
Name: "Get Worker Details"
Method: GET
URL: https://<tenant>.workday.com/api/wql/v1/data?query=SELECT worker, fullName FROM allWorkers WHERE worker = {workerId}
Headers:
  Authorization: Bearer {accessToken}
  Content-Type: application/json
Output Mapping:
  workerName -> response.data[0].fullName
```

### Workday Web Services (WWS) Step
Calls Workday's SOAP-based web services directly:
- Access to all Workday SOAP operations (Human_Resources, Staffing, Compensation, etc.)
- Handles SOAP envelope construction
- Supports all WWS operations like Get_Workers, Put_Worker, etc.

### WQL Step (Workday Query Language)
Executes a WQL query against Workday data:
- Returns structured data from Workday's data model
- Supports filtering, joining, aggregation
- Results are available as orchestration variables

```
Step Type: WQL Query
Query: SELECT worker, fullName, email
       FROM allActiveWorkers
       WHERE supervisoryOrganization = {orgId}
Output: workerList
```

### Approval Step
Routes a task to a user or group for approval:
- Configurable approvers (specific user, role, supervisory org, custom logic)
- Timeout and escalation rules
- Approval/rejection paths
- Comments and attachments
- Integrates with Workday's inbox

### Notification Step
Sends notifications through Workday's notification system:
- In-app notifications (Workday inbox)
- Email notifications
- Push notifications (mobile)
- Configurable templates with variable substitution
- Rich text support

### Condition Step
Evaluates a boolean expression to control flow:
- Supports comparison operators (==, !=, >, <, >=, <=)
- Logical operators (AND, OR, NOT)
- Null checks
- String matching
- Collection membership checks
- References orchestration variables and step outputs

```
Condition: workerType == "Regular" AND department IN ("Engineering", "Product")
True Branch: [steps...]
False Branch: [steps...]
```

### Data Transformation Step
Transforms data between steps:
- Field mapping
- Type conversion
- String manipulation
- Date formatting
- JSON path extraction
- Collection operations (filter, map, reduce)

### Sub-Orchestration Step
Invokes another orchestration:
- Pass input parameters
- Receive output values
- Can be synchronous (wait for completion) or asynchronous (fire and forget)

### Custom Step (via Extend)
Extend apps can define custom orchestration step types:
- Implemented in the Extend app's server-side code
- Registered as available step types
- Can have custom configuration UI
- Have access to Extend app's data and logic

### Wait/Delay Step
Pauses orchestration execution:
- Wait for a specific duration
- Wait until a specific date/time
- Wait for an external event or callback

### Loop Step
Iterates over a collection:
- For-each semantics
- Access to current item and index
- Can contain any other step types
- Supports break and continue logic

## 1.6 Context and Variable Passing

### Orchestration Context
Every orchestration has a context that contains:
- **Input Parameters**: Defined in the orchestration signature, passed when triggered
- **Variables**: Declared within the orchestration, can be set by steps
- **System Variables**: Automatically available (current user, current date/time, tenant info)
- **Step Outputs**: Results from completed steps, referenced by step name

### Variable Types
- **String**: Text values
- **Integer/Decimal**: Numeric values
- **Boolean**: True/false
- **Date/DateTime**: Date and time values
- **Object**: Structured data (JSON-like)
- **Collection/List**: Arrays of values or objects
- **Workday Object Reference**: Reference to a Workday business object (Worker, Organization, etc.)

### Variable Scoping
- **Orchestration-level**: Available to all steps
- **Step-level**: Available only within a specific step
- **Loop-level**: Available within a loop iteration (current item)
- **Branch-level**: Available within a conditional branch

### Passing Data Between Steps
Steps reference outputs from previous steps using expressions:

```
Step 1 Output: workerData = { name: "John", email: "john@company.com" }
Step 2 Input:  recipientEmail = {steps.Step1.workerData.email}
```

Expression syntax:
- `{steps.<stepName>.<outputField>}` -- Reference step output
- `{context.<paramName>}` -- Reference orchestration input parameter
- `{variables.<varName>}` -- Reference orchestration variable
- `{system.currentDateTime}` -- Reference system variable
- `{loop.currentItem}` -- Reference current loop item
- `{loop.index}` -- Reference current loop index

## 1.7 Error Handling and Retry Logic

### Step-Level Error Handling
Each step can have error handling configuration:

- **On Error Actions**:
  - `Fail`: Stop the orchestration and mark as failed (default)
  - `Continue`: Log the error and continue to the next step
  - `Retry`: Retry the step with configurable parameters
  - `Branch`: Execute an error-handling branch

### Retry Configuration
```
Retry Policy:
  Max Retries: 3
  Initial Delay: 5 seconds
  Backoff Multiplier: 2 (exponential backoff: 5s, 10s, 20s)
  Max Delay: 60 seconds
  Retryable Errors: [HTTP 429, HTTP 500, HTTP 502, HTTP 503, Timeout]
```

### Error Handling Patterns

**Try-Catch Pattern:**
```
Try:
  Step 1: Call External API
Catch (on error):
  Step 2: Log Error Details
  Step 3: Send Alert Notification
  Step 4: Set Fallback Values
Continue:
  Step 5: Process Results (uses fallback if error occurred)
```

**Circuit Breaker Pattern:**
Not natively built in, but can be implemented by:
- Tracking failure counts in a custom object
- Checking the failure count before making calls
- Skipping calls if the circuit is "open"
- Resetting after a cooldown period

### Timeout Configuration
- Each step can have a timeout (default varies by step type)
- The overall orchestration can have a maximum execution time
- Timeouts trigger the configured error handling action

### Monitoring and Alerting
- Failed orchestrations appear in the Workday monitoring dashboard
- Administrators can configure alerts for orchestration failures
- Each orchestration instance has detailed execution logs
- Step-level timing and status information is recorded

## 1.8 Testing and Debugging Orchestrations

### Testing Approaches

**1. Manual Testing:**
- Use the "Test" button in the Orchestration Editor
- Provide test input parameters
- Watch execution in real-time
- Inspect step-by-step results
- View variable values at each point

**2. Sandbox/Preview Testing:**
- Deploy orchestration to a Workday Sandbox or Preview tenant
- Trigger with test data
- Verify end-to-end flow
- Check external system interactions (use mock endpoints in sandbox)

**3. Unit Testing Individual Steps:**
- Test WQL queries independently
- Test API calls with tools like Postman
- Verify condition logic with different inputs
- Test data transformations with sample data

### Debugging Tools

**Orchestration Monitor:**
- Available in Workday under Integration > Orchestration Monitor
- Shows all orchestration instances
- Filter by status (Running, Completed, Failed)
- Drill into individual instances for step-by-step details

**Execution Details:**
For each orchestration instance:
- Overall status and timing
- Step-by-step execution sequence
- Input/output values for each step
- Error messages and stack traces
- HTTP request/response details for integration steps
- Variable values at each checkpoint

**Logging:**
- Orchestrations support log statements
- Log levels: Debug, Info, Warning, Error
- Logs are visible in the orchestration instance details
- Can be used to trace data flow through complex orchestrations

### Common Debugging Scenarios

1. **Step fails with HTTP error**: Check the full request/response in step details. Common issues: wrong URL, missing auth, incorrect payload format.

2. **Variable is null unexpectedly**: Trace the variable through each step. Check if a previous step failed silently. Check field mapping expressions.

3. **Condition evaluates incorrectly**: Log the condition inputs before the condition step. Check data types (string "true" vs boolean true).

4. **Timeout**: Check external system response times. Consider adding retry with longer timeout. Break long operations into smaller steps.

5. **Loop processing**: Check collection size. Watch for n+1 query patterns. Consider batching.

## 1.9 Common Orchestration Patterns and Best Practices

### Pattern: Worker Onboarding Automation
```
Trigger: Hire Business Process Complete
Steps:
  1. Get new worker details (WQL)
  2. Create accounts in external systems (parallel):
     a. Create AD account (REST)
     b. Create email account (REST)
     c. Assign default learning courses (WWS)
  3. Wait for all parallel steps
  4. Send welcome notification to worker
  5. Send IT setup notification to IT team
  6. Log completion in custom object
```

### Pattern: Data Sync to External System
```
Trigger: Scheduled (Daily at 2 AM)
Steps:
  1. Query changed workers since last sync (WQL with date filter)
  2. For each changed worker:
     a. Transform to external system format
     b. Call external API (PUT/POST)
     c. Log sync result
  3. Update last sync timestamp
  4. Send summary notification
Error Handling:
  - Retry individual API calls 3x with exponential backoff
  - On persistent failure, log and continue to next worker
  - Send error summary at end
```

### Pattern: Approval Workflow
```
Trigger: Custom event from Extend app
Steps:
  1. Get request details from custom object
  2. Determine approver based on amount:
     Condition: amount > 10000
       True: Route to VP for approval
       False: Route to Manager for approval
  3. Wait for approval response
  4. Condition: Approved?
     True:
       a. Update request status to "Approved"
       b. Execute fulfillment steps
       c. Notify requester
     False:
       a. Update request status to "Rejected"
       b. Notify requester with reason
```

### Best Practices

1. **Keep orchestrations focused**: One orchestration should do one thing well. Use sub-orchestrations for reusable components.

2. **Use meaningful names**: Step names should describe what they do, not how. "Get Active Workers in Department" not "Step 1".

3. **Handle errors at every external call**: Never assume an API call will succeed. Always have error handling on integration steps.

4. **Use parallel execution wisely**: Only parallelize independent operations. Be aware of rate limits on external systems.

5. **Log strategically**: Add log steps at key decision points. Log input parameters and key variable values. Do not log sensitive data.

6. **Design for idempotency**: Orchestrations may be retried. Ensure that re-running a step does not create duplicate data. Use upsert patterns.

7. **Mind the timeout**: Long-running orchestrations can time out. Break them into smaller orchestrations if needed.

8. **Version control**: Use descriptive names and version numbers. Document changes between versions.

9. **Test with edge cases**: Empty collections, null values, large datasets, network failures.

10. **Security**: Follow principle of least privilege for API credentials. Use Workday's credential management. Do not hardcode secrets.

## 1.10 Orchestrations and Extend Apps

### How Extend Apps Use Orchestrations

Extend apps interact with orchestrations in several ways:

1. **Triggering Orchestrations**: An Extend app's UI can trigger an orchestration when a user takes an action (button click, form submission). The app passes input parameters from the UI context.

2. **Receiving Orchestration Results**: The Extend app can poll for orchestration completion or register for callbacks. Results are displayed in the app UI.

3. **Custom Orchestration Steps**: An Extend app can define custom step types that appear in the Orchestration Editor. This extends the platform's orchestration capabilities.

4. **Event-Driven Integration**: Extend apps can publish events that trigger orchestrations, and orchestrations can raise events consumed by Extend apps.

### Extend App Orchestration API

From an Extend app's server-side code:

```javascript
// Triggering an orchestration (conceptual)
const result = await workday.orchestrations.run({
  orchestrationId: "orch_abc123",
  inputs: {
    workerId: context.currentWorkerId,
    requestType: formData.requestType,
    amount: formData.amount
  }
});

// Checking orchestration status
const status = await workday.orchestrations.getStatus(result.instanceId);

// Getting orchestration output
if (status.state === "Completed") {
  const output = status.outputs;
  // Use output in the app
}
```

## 1.11 The Orchestration Editor UI

The Orchestration Editor is a visual design tool within the Workday platform:

### Key Features
- **Drag-and-drop step placement**: Add steps from a palette
- **Visual flow diagram**: See the orchestration as a flowchart
- **Step configuration panels**: Configure each step's properties
- **Variable inspector**: View and manage orchestration variables
- **Expression editor**: Build expressions for data mapping with autocomplete
- **Test runner**: Execute the orchestration with test inputs
- **Version history**: Track changes over time
- **Validation**: Real-time validation of the orchestration definition
- **Import/Export**: Share orchestrations between tenants

### Navigation
- Access via: Search "Orchestrations" in Workday > Create/Edit Orchestration
- The editor has a canvas area for the flow, a properties panel on the right, and a palette/toolbar at the top
- Steps are connected by arrows showing the execution flow
- Conditions show branch points with labeled paths

---

# Part 2: Integrations in Workday

## 2.1 Integration Architecture Overview

Workday provides multiple integration mechanisms, each suited to different use cases:

| Mechanism | Best For | Complexity | Flexibility |
|-----------|----------|------------|-------------|
| Enterprise Interface Builder (EIB) | Simple file-based imports/exports | Low | Low |
| Core Connectors | Standard system integrations | Low-Medium | Medium |
| Workday Studio | Complex custom integrations | High | High |
| Cloud Connect | Pre-built partner integrations | Low | Low |
| Orchestrations | Workflow-driven integrations | Medium | High |
| RaaS + API | Programmatic data access | Medium | High |

## 2.2 Enterprise Interface Builder (EIB)

EIB is Workday's simplest integration tool for file-based data exchange.

### What EIB Does
- Imports data from flat files (CSV, delimited text) into Workday
- Exports data from Workday reports to files
- Supports scheduled and on-demand execution
- No coding required -- entirely configured through the Workday UI

### EIB Inbound (Import)

**Process:**
1. Create or select a Workday Web Service operation (e.g., Put_Worker, Submit_Expense_Report)
2. Define field mapping from file columns to web service fields
3. Configure file source (SFTP, local upload, cloud storage)
4. Set up scheduling (if recurring)
5. Configure error handling and notifications

**Configuration Example (Conceptual):**
```
Name: Import Employee Updates
Type: Inbound
Web Service: Human_Resources > Put_Worker (v40.0)
File Format: CSV
Delimiter: Comma
Header Row: Yes
Field Mapping:
  Column A (Employee_ID) -> Worker_Reference > ID (Employee_ID type)
  Column B (Phone_Number) -> Phone_Data > Phone_Number
  Column C (Phone_Type) -> Phone_Data > Usage_Data > Type_Reference
File Source: SFTP
  Host: sftp.company.com
  Path: /outbound/worker_updates/
  Username: workday_integration
  Authentication: SSH Key
Schedule: Daily at 6:00 AM EST
```

### EIB Outbound (Export)

**Process:**
1. Create a custom report or use an existing report as the data source
2. Configure output format (CSV, XML, JSON)
3. Define delivery method (SFTP, email, cloud storage)
4. Set up scheduling

**Configuration Example:**
```
Name: Export Active Workers
Type: Outbound
Data Source: Custom Report "CR - Active Workers with Details"
Output Format: CSV
Delivery:
  Method: SFTP
  Host: sftp.company.com
  Path: /inbound/worker_extract/
  Filename: active_workers_{date}.csv
Schedule: Weekly, Monday at 1:00 AM EST
Notification:
  On Success: integration-team@company.com
  On Failure: integration-alerts@company.com
```

### EIB Limitations
- Cannot perform complex transformations
- Limited error handling (all-or-nothing for many operations)
- No conditional logic
- No ability to call external APIs
- Not suitable for real-time integrations
- Limited to file-based data exchange

## 2.3 Core Connectors

Core Connectors are pre-built, configurable integrations that Workday provides for common integration patterns.

### Available Core Connectors (Common Examples)
- **Worker Connector**: Export worker data to downstream systems
- **Benefits Connector**: Exchange benefits enrollment data
- **Payroll Connector**: Interface with payroll systems
- **Absence Connector**: Export time off and leave data
- **Recruiting Connector**: Share job requisition and candidate data
- **Learning Connector**: Exchange training completion data
- **Financial Connector**: Export financial transactions

### How Core Connectors Work
1. Select the appropriate connector for your use case
2. Configure connection parameters (SFTP, API endpoint, etc.)
3. Map data fields (many have sensible defaults)
4. Configure filters (which records to include)
5. Set up scheduling
6. Define transformation rules (optional XSLT for format changes)

### Core Connector Features
- Pre-defined data extracts optimized for specific business domains
- Configurable field selection and filtering
- Support for custom fields via calculated fields
- Built-in data formatting options
- Document transformation support (XSLT)
- Scheduled execution
- Error reporting and notifications
- Delta/incremental processing (changed records only)

### Configuration Example (Worker Core Connector):
```
Name: Worker Data to HRIS
Connector: Worker
Data Selection:
  Worker Types: Employee, Contingent Worker
  Statuses: Active, On Leave
  Fields: Employee ID, Name, Email, Department, Job Title, Manager, Hire Date
  Custom Fields: Badge Number (CF), Building (CF)
Filtering:
  Companies: Acme Corp, Acme International
  Effective Date: Last Run Date (delta mode)
Output:
  Format: CSV (with XSLT for custom formatting)
  Delivery: SFTP to hr-systems.company.com:/inbound/
Schedule: Daily at 3:00 AM
```

## 2.4 Workday Studio

### What is Workday Studio?

Workday Studio is an Eclipse-based IDE for building complex custom integrations. It provides:
- A full development environment with visual and code-based development
- Support for complex data transformations, routing, and mediation
- Connectors for REST, SOAP, file systems, databases, and messaging
- Testing and debugging capabilities
- Version control integration
- Deployment to Workday tenants

**Note:** Workday Studio is being gradually superseded by Orchestrations and newer Extend capabilities for many use cases, but remains important for complex enterprise integrations.

### Studio Project Structure

A Studio project consists of:

```
my-integration/
  |-- assembly/
  |    |-- main.assembly            # Main integration assembly (entry point)
  |    |-- sub-assembly.assembly    # Reusable sub-assemblies
  |-- mediation/
  |    |-- transform.xsl            # XSLT transformations
  |    |-- routing.mediation        # Mediation routing rules
  |-- schemas/
  |    |-- input-schema.xsd         # Input data schemas
  |    |-- output-schema.xsd        # Output data schemas
  |-- connectors/
  |    |-- rest-config.xml          # REST connector configurations
  |    |-- sftp-config.xml          # SFTP connector configurations
  |-- resources/
  |    |-- templates/               # Message templates
  |    |-- reference-data/          # Lookup tables, mapping files
  |-- test/
  |    |-- test-data/               # Test input files
  |    |-- test-configs/            # Test configurations
  |-- integration.properties        # Integration properties/settings
  |-- project.xml                   # Studio project descriptor
```

### Assembly Steps

Assemblies are the backbone of Studio integrations. An assembly defines the integration flow using a sequence of steps:

**Common Assembly Steps:**

1. **Start Step**: Entry point of the assembly
2. **End Step**: Exit point
3. **Call Integration Step**: Calls Workday Web Services (SOAP)
4. **Call REST Step**: Makes REST API calls
5. **Call Assembly Step**: Calls a sub-assembly (reuse)
6. **Mediation Step**: Applies XSLT or routing logic
7. **Condition Step**: Branching logic
8. **Loop Step**: Iteration over collections
9. **Variable Step**: Set/get integration variables
10. **Write File Step**: Write data to a file
11. **Read File Step**: Read data from a file
12. **FTP Step**: Transfer files via FTP/SFTP
13. **Email Step**: Send emails
14. **Error Handler Step**: Handle errors in the flow
15. **Log Step**: Write to integration logs

### Assembly Example (Conceptual XML):
```xml
<assembly name="MainAssembly">
  <start name="Begin"/>

  <callIntegration name="GetWorkers">
    <service>Human_Resources</service>
    <operation>Get_Workers</operation>
    <version>v40.0</version>
    <request>
      <requestCriteria>
        <transactionLogCriteria>
          <updatedFrom>{lastRunDate}</updatedFrom>
          <updatedThrough>{currentDate}</updatedThrough>
        </transactionLogCriteria>
      </requestCriteria>
    </request>
    <output variable="workerData"/>
  </callIntegration>

  <mediation name="TransformToCSV">
    <xslt>transform/workers-to-csv.xsl</xslt>
    <input>{workerData}</input>
    <output variable="csvOutput"/>
  </mediation>

  <writeFile name="WriteOutput">
    <content>{csvOutput}</content>
    <filename>workers_{date}.csv</filename>
    <encoding>UTF-8</encoding>
  </writeFile>

  <ftp name="UploadFile">
    <host>sftp.external-system.com</host>
    <path>/inbound/</path>
    <file>workers_{date}.csv</file>
    <protocol>SFTP</protocol>
    <credentials ref="sftp_creds"/>
  </ftp>

  <end name="Complete"/>

  <errorHandler>
    <email>
      <to>integration-alerts@company.com</to>
      <subject>Worker Export Failed</subject>
      <body>{errorMessage}</body>
    </email>
  </errorHandler>
</assembly>
```

### Mediation and Routing

**Mediation** is Studio's mechanism for data transformation:
- Uses XSLT for transforming XML data between formats
- Supports XSLT 1.0 and 2.0
- Can chain multiple transformations
- Supports custom XSLT functions

**Routing** controls message flow:
- Content-based routing (route based on data values)
- Recipient list (send to multiple destinations)
- Message filter (include/exclude based on criteria)
- Splitter (break a collection into individual messages)
- Aggregator (combine multiple messages into one)

### Connectors

Studio provides pre-built connectors:

**REST Connector:**
- HTTP methods: GET, POST, PUT, PATCH, DELETE
- Authentication: Basic, OAuth 2.0, API Key, Certificate
- Request/response mapping
- Timeout and retry configuration
- SSL/TLS support

**SOAP Connector:**
- WSDL-based service invocation
- All Workday Web Services (WWS)
- Custom SOAP endpoints
- WS-Security support

**File Connector:**
- Local file system access
- CSV, XML, JSON, flat file formats
- File watching (trigger on new file)

**FTP/SFTP Connector:**
- File upload and download
- Directory listing
- SSH key and password authentication

**Database Connector (limited):**
- JDBC connections to external databases
- SQL query execution
- Result set mapping

**JMS/Messaging Connector:**
- Message queue integration
- Publish/subscribe patterns

### Testing in Studio

1. **Local Testing**: Run integrations locally in the Studio IDE with test data
2. **Mock Services**: Create mock endpoints for external services
3. **Test Data**: Use sample files in the test/ directory
4. **Debugging**: Set breakpoints, inspect variables, step through assemblies
5. **Integration Test**: Deploy to Sandbox tenant and run end-to-end

### Deploying Studio Integrations

1. **Build**: Compile the Studio project into a deployment package
2. **Upload**: Upload to Workday via the "Deploy Integration" task
3. **Configure**: Set runtime parameters (credentials, endpoints, schedules)
4. **Test**: Run in the target tenant with test data
5. **Activate**: Enable for production use
6. **Monitor**: Use Workday's integration monitoring tools

### Studio and Extend Relationship

- Studio integrations can be called from Orchestrations as integration steps
- Extend apps can trigger Studio integrations via API
- Studio integrations can call Extend app APIs
- Both share the same Workday security model
- New development is generally recommended to use Orchestrations over Studio for simpler integrations

## 2.5 Cloud Connect Integrations

Cloud Connect provides pre-built, certified integrations with third-party systems:

### Common Cloud Connect Partners
- **Payroll**: ADP, Ceridian
- **Benefits**: Various benefits providers
- **Financial**: Banking, payment systems
- **Tax**: Tax filing services
- **Background Check**: Various providers
- **Learning**: LinkedIn Learning, Coursera, etc.

### How Cloud Connect Works
1. Select the Cloud Connect integration from the Workday marketplace
2. Configure connection parameters (provided by the partner)
3. Map any customer-specific fields
4. Test with sample data
5. Activate

### Advantages
- Pre-built, tested, and certified by Workday
- Minimal configuration required
- Supported by both Workday and the partner
- Regular updates for API changes

## 2.6 Document Transformation

Document Transformation is a key capability used across integration types:

### XSLT Transformations
Most Workday integrations use XSLT to transform data between formats:

```xml
<!-- Example: Transform Workday worker XML to external system format -->
<xsl:stylesheet version="2.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
                xmlns:wd="urn:com.workday/bsvc">

  <xsl:output method="text" encoding="UTF-8"/>

  <xsl:template match="/">
    <xsl:text>EmployeeID,Name,Email,Department&#10;</xsl:text>
    <xsl:for-each select="//wd:Worker">
      <xsl:value-of select="wd:Worker_Data/wd:Employee_ID"/>
      <xsl:text>,</xsl:text>
      <xsl:value-of select="wd:Worker_Data/wd:Personal_Data/wd:Name_Data/wd:Legal_Name/wd:Name_Detail_Data/@wd:Formatted_Name"/>
      <xsl:text>,</xsl:text>
      <xsl:value-of select="wd:Worker_Data/wd:Personal_Data/wd:Contact_Data/wd:Email_Address_Data[wd:Usage_Data/wd:Type_Data/wd:Type_Reference/wd:ID[@wd:type='Communication_Usage_Type_ID']='WORK']/wd:Email_Address"/>
      <xsl:text>,</xsl:text>
      <xsl:value-of select="wd:Worker_Data/wd:Organization_Data/wd:Worker_Organization_Data[wd:Organization_Data/wd:Organization_Type_Reference/wd:ID='Organization_Type_ID=Cost_Center']/wd:Organization_Data/wd:Organization_Name"/>
      <xsl:text>&#10;</xsl:text>
    </xsl:for-each>
  </xsl:template>
</xsl:stylesheet>
```

### Document Transformation Features
- XSLT 1.0 and 2.0 support
- Custom XSLT functions
- Template-based transformations
- Support for XML, CSV, JSON, fixed-width output formats
- Lookup tables for reference data mapping
- Chained transformations (multiple passes)

## 2.7 Integration System Configuration

Every integration in Workday is configured through an Integration System:

### Integration System Components

1. **Integration System Definition**: The blueprint -- defines what the integration does
2. **Integration System Instance**: A specific configuration of the definition (you can have multiple instances of the same definition with different settings)
3. **Integration Attributes**: Configuration parameters (endpoints, credentials, file paths)
4. **Integration Sequences**: Ordering of integration steps
5. **Integration Maps**: Field-level mapping configurations
6. **Integration Field Overrides**: Custom field mappings that override defaults

### Configuration Hierarchy
```
Integration System
  |-- Attributes (global settings)
  |-- Sequences (execution order)
  |-- Maps (field mappings)
  |     |-- Field Overrides
  |     |-- Calculated Fields
  |     |-- Lookup Tables
  |-- Notifications (success/failure alerts)
  |-- Scheduling (when to run)
  |-- Security (who can run/configure)
  |-- Connections (endpoint details)
       |-- Transport Protocol (SFTP, HTTP, etc.)
       |-- Authentication
       |-- Encryption
```

### Integration Events
Every integration execution creates an Integration Event:

```
Integration Event:
  Status: Completed/Failed/In Progress
  Started: 2024-01-15 03:00:00 EST
  Completed: 2024-01-15 03:05:23 EST
  Records Processed: 1,247
  Records Succeeded: 1,245
  Records Failed: 2
  Files Generated: active_workers_20240115.csv
  Error Details:
    - Row 523: Invalid email format for worker W12345
    - Row 891: Missing required field "Department" for worker W67890
```

### Integration Scheduling
- **Recurring Schedules**: Daily, weekly, monthly, custom frequency
- **Time-based**: Specific time of day (with timezone)
- **Event-based**: Trigger on business process completion
- **Manual**: On-demand execution by authorized users
- **Chaining**: One integration triggers another upon completion

## 2.8 REST and SOAP API Integrations

### Workday REST API

Workday provides RESTful APIs for many common operations:

**Base URL pattern:**
```
https://<tenant>.workday.com/api/<resource>/<version>/<endpoint>
```

**Common REST API categories:**
- `/api/wql/v1/` -- Workday Query Language
- `/api/staffing/v1/` -- Worker and organization data
- `/api/person/v1/` -- Person data
- `/api/absenceManagement/v1/` -- Time off
- `/api/compensation/v1/` -- Compensation data
- `/api/common/v1/` -- Common resources (currencies, countries)
- `/api/orchestrations/v1/` -- Orchestration management

**Authentication:**
- OAuth 2.0 (Authorization Code, Client Credentials)
- Bearer tokens
- API Client registration in Workday

**Example REST API calls:**
```
# Get worker by ID
GET /api/staffing/v1/workers/{workerId}
Authorization: Bearer {token}
Accept: application/json

# Search workers
GET /api/staffing/v1/workers?search=John+Smith&limit=20
Authorization: Bearer {token}
Accept: application/json

# Execute WQL query
POST /api/wql/v1/data
Authorization: Bearer {token}
Content-Type: application/json

{
  "query": "SELECT worker, fullName, email FROM allActiveWorkers WHERE supervisoryOrganization = 'ORG-12345'"
}

# Trigger orchestration
POST /api/orchestrations/v1/{orchestrationId}/run
Authorization: Bearer {token}
Content-Type: application/json

{
  "inputs": {
    "workerId": "W12345",
    "requestType": "equipment"
  }
}
```

### Workday SOAP Web Services (WWS)

Workday's original API, still widely used:

**WSDL URL pattern:**
```
https://<tenant>.workday.com/ccx/service/<tenant>/<service>/<version>
```

**Common SOAP Services:**
- `Human_Resources` -- Worker, organization, job data
- `Staffing` -- Hiring, transfers, terminations
- `Compensation` -- Pay, bonus, stock
- `Benefits_Administration` -- Benefits enrollment
- `Payroll` -- Payroll data
- `Financial_Management` -- Accounting, journals
- `Revenue_Management` -- Billing, invoicing
- `Resource_Management` -- Projects, time tracking
- `Recruiting` -- Job requisitions, candidates
- `Learning` -- Courses, enrollments
- `Talent` -- Performance, goals, succession
- `Integrations` -- Integration management

**Example SOAP request:**
```xml
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:bsvc="urn:com.workday/bsvc">
  <soapenv:Header>
    <wsse:Security xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">
      <wsse:UsernameToken>
        <wsse:Username>ISU_User@tenant</wsse:Username>
        <wsse:Password>password</wsse:Password>
      </wsse:UsernameToken>
    </wsse:Security>
  </soapenv:Header>
  <soapenv:Body>
    <bsvc:Get_Workers_Request bsvc:version="v40.0">
      <bsvc:Request_References>
        <bsvc:Worker_Reference>
          <bsvc:ID bsvc:type="Employee_ID">12345</bsvc:ID>
        </bsvc:Worker_Reference>
      </bsvc:Request_References>
      <bsvc:Response_Group>
        <bsvc:Include_Personal_Information>true</bsvc:Include_Personal_Information>
        <bsvc:Include_Employment_Information>true</bsvc:Include_Employment_Information>
        <bsvc:Include_Organizations>true</bsvc:Include_Organizations>
      </bsvc:Response_Group>
    </bsvc:Get_Workers_Request>
  </soapenv:Body>
</soapenv:Envelope>
```

### API Versioning
- Workday APIs are versioned (e.g., v40.0, v41.0)
- New versions are released with each Workday update (twice yearly)
- Older versions are supported for a deprecation period
- Always specify a version to avoid breaking changes

## 2.9 RaaS (Report as a Service)

RaaS allows Workday custom reports to be consumed as REST endpoints -- a powerful mechanism for integration data sourcing.

### How RaaS Works

1. **Create a Custom Report** in Workday with the desired data
2. **Enable as a Web Service**: Check "Enable As Web Service" on the report definition
3. **Access via REST**: The report is now available as a REST endpoint
4. **Consume**: Integration tools, Orchestrations, or external systems can call the endpoint

### RaaS URL Pattern
```
https://<tenant>.workday.com/ccx/service/customreport2/<tenant>/<report_owner>/<report_name>?format=json
```

**Supported output formats:**
- `json` -- JSON format
- `csv` -- Comma-separated values
- `simplexml` -- Simple XML
- `gdata` -- Google Data format (Atom)

### RaaS with Parameters
Reports can have prompt parameters that become query parameters:

```
# Report with worker filter
GET /ccx/service/customreport2/tenant/ISU_Report_Owner/Active_Workers?Worker_Type!WID=d588c41a446c11de98360015c5e6daf6&format=json

# Report with date range
GET /ccx/service/customreport2/tenant/ISU_Report_Owner/Hires_Report?Effective_Date=2024-01-01-08:00&End_Date=2024-12-31-08:00&format=json
```

### RaaS Best Practices
- Create purpose-built reports for integrations (not end-user reports)
- Use calculated fields for data transformation in the report
- Apply security groups to control access
- Use report parameters for filtering (do not fetch all data and filter client-side)
- Consider performance: large reports may time out. Use pagination or date-based incremental queries.
- RaaS is excellent as a data source for EIB, Orchestrations, and external API consumers

### RaaS and Orchestrations
Orchestrations can call RaaS endpoints as integration steps:
```
Step Type: REST API Call
URL: /ccx/service/customreport2/{tenant}/ISU_Owner/MyReport?format=json&Worker={workerId}
Method: GET
Output: reportData
```

### RaaS and Extend
Extend apps can use RaaS as a data source:
- Call the RaaS endpoint from the app's server-side code
- Use the report data to populate UI components
- Combine RaaS data with custom object data

---

# Part 3: Business Process Framework

## 3.1 What Are Business Processes?

Business Processes (BPs) are Workday's mechanism for modeling and automating HR, Finance, and operational workflows. They are the core of how work gets done in Workday.

### Key Characteristics
- Every significant action in Workday goes through a Business Process (Hire, Terminate, Change Job, Request Time Off, Create Expense Report, etc.)
- BPs define who can initiate actions, who must approve them, and what happens at each stage
- BPs are configurable -- customers can add, remove, or modify steps
- BPs enforce security, compliance, and audit requirements
- BPs generate events that other systems can react to

## 3.2 Business Process Structure

A Business Process consists of:

### Initiation
- **Initiator**: The user or system that starts the process
- **Security**: Who is allowed to initiate (security roles/groups)
- **Context**: The business object being acted upon (Worker, Position, Cost Center, etc.)

### Steps
BPs are composed of ordered steps. Each step defines:

1. **Step Type**: What kind of action occurs
2. **Assignee/Actor**: Who performs the step (person, role, rule-based)
3. **Condition**: When the step applies (can be skipped based on rules)
4. **Due Date**: When the step should be completed
5. **Routing**: How the step is assigned (single person, group, parallel)

### Step Types

**Approval Step:**
- Routes to a person or group for approval/rejection
- Configurable approval chain (sequential, parallel)
- Escalation rules for overdue approvals
- Delegation support

**Review Step:**
- Routes for review (informational, no approval required)
- Reviewer can add comments but cannot approve/reject
- Send-back capability

**To-Do Step:**
- Creates a task for someone to complete
- May include instructions or a checklist
- Completion triggers the next step

**Notification Step:**
- Sends a notification (email, in-app, push)
- Does not require action from the recipient
- Configurable templates

**Integration Step:**
- Triggers an integration (EIB, Studio, Orchestration)
- Can pass business process data to the integration
- The integration can report success/failure back

**Sub-Business-Process Step:**
- Invokes another Business Process
- Allows modular BP design
- The parent BP waits for the sub-BP to complete

**Custom Step (via Extend):**
- A step whose behavior is defined by an Extend app
- The app controls what happens when the step is reached
- The app can display a custom UI for the step

### Conditions

Conditions control whether a step is executed:

```
Condition Examples:
- Worker Type = "Employee" (skip for contingent workers)
- Amount > $10,000 (require additional approval for large amounts)
- Country = "United States" (US-specific compliance step)
- Job Family IN ("Engineering", "Product") (department-specific steps)
- Is Rehire = True (additional steps for returning workers)
```

Conditions use **Condition Rules**, which are reusable boolean expressions defined in Workday.

### Step Routing

**Sequential**: Steps execute one after another
**Parallel**: Multiple steps execute simultaneously (all must complete)
**Conditional**: Steps execute based on conditions
**Dynamic**: Routing determined at runtime by rules (e.g., route to the worker's manager's manager)

## 3.3 Business Process Security

### Security Groups
- **Business Process Security**: Controls who can initiate, view, and participate in BPs
- **Step-level Security**: Each step can have its own security restrictions
- **Role-based**: Typically assigned to security roles (HR Partner, Manager, IT Admin)
- **Constrained**: Can be constrained to specific organizations, locations, or worker types

### Common Security Roles in BPs
- **HR Partner**: Manages HR-related business processes
- **Manager**: Approves direct report actions
- **Compensation Partner**: Approves compensation changes
- **Benefits Administrator**: Manages benefits enrollments
- **IT Administrator**: Handles system provisioning steps
- **Finance Partner**: Approves financial transactions

## 3.4 Business Process Events

Every Business Process generates events at various stages:

### Event Types
- **Initiation Event**: When the BP is started
- **Step Completion Event**: When a step is completed
- **Approval Event**: When a step is approved or rejected
- **Completion Event**: When the entire BP completes successfully
- **Cancellation Event**: When the BP is cancelled
- **Denial Event**: When the BP is denied (rejected)
- **Rescind Event**: When a completed BP is rescinded

### Event-Driven Architecture
These events can trigger:
- **Orchestrations**: Run automated workflows
- **Integrations**: Send data to external systems
- **Notifications**: Alert stakeholders
- **Other Business Processes**: Chain BPs together

### Example Event Flow
```
Hire Employee Business Process:
  1. [Event: Initiation] -> Trigger: Sync to ATS Integration
  2. Step: Manager Approval
  3. [Event: Manager Approved] -> Trigger: Notify HR Partner
  4. Step: HR Partner Review
  5. Step: Compensation Review
  6. [Event: Compensation Approved] -> Trigger: Calculate Benefits Eligibility
  7. Step: IT Provisioning (Integration Step)
     -> Triggers: Account Creation Orchestration
  8. [Event: Completion] -> Triggers:
     - Send Welcome Email Orchestration
     - Sync to Payroll Integration
     - Update External HRIS Integration
     - Create Onboarding Tasks
```

## 3.5 Integration with Orchestrations

Business Processes and Orchestrations work together in several ways:

### BP Triggering Orchestrations
- A BP step completion event triggers an orchestration
- The orchestration receives the BP context (worker, transaction data)
- The orchestration performs automated work (API calls, data sync, etc.)
- Configuration: In the BP definition, add an integration step that references the orchestration

### Orchestrations Triggering BPs
- An orchestration can initiate a BP via Workday Web Services
- Example: An external event triggers an orchestration that starts a "Job Change" BP
- The orchestration provides the required BP data as input

### Custom BP Steps via Orchestrations
- An orchestration can serve as the implementation behind a custom BP step
- When the BP reaches that step, the orchestration executes
- The orchestration's result determines whether the step succeeds or fails

## 3.6 Custom Business Process Steps via Extend

Extend apps can create custom BP step types:

### How It Works
1. **Define the Step Type**: In the Extend app configuration, define a custom step type with:
   - Name and description
   - Input parameters (what data the step receives from the BP)
   - Output parameters (what data the step returns to the BP)
   - UI configuration (if the step requires user interaction)

2. **Implement the Step Logic**: In the Extend app's server-side code:
   - Handle the step execution event
   - Perform custom logic (calculations, API calls, data validation)
   - Return results to the BP

3. **Register the Step**: Make the custom step available in the BP configuration UI

4. **Configure in BP**: Add the custom step to the appropriate BP definition

### Example: Custom Compliance Check Step
```
Step Type: Compliance Verification
Inputs:
  - Worker Reference
  - Transaction Type (Hire, Transfer, Promotion)
  - Effective Date
Logic:
  1. Query compliance database for worker's country regulations
  2. Validate transaction against country-specific rules
  3. Check for required certifications/licenses
  4. Return compliance status
Outputs:
  - Compliant (boolean)
  - Issues (list of compliance findings)
  - Required Actions (list of remediation steps)
BP Integration:
  - If Compliant = false, route to Compliance Review step
  - If Compliant = true, continue to next step
```

## 3.7 Business Process Versioning and Migration

### Versioning
- BPs have versions -- changes create new versions
- Active version is the one currently in use
- Previous versions are retained for audit
- In-flight processes continue on their version even if a new version is activated

### Migration Considerations
- Test BP changes in Sandbox/Preview first
- Consider in-flight processes when making changes
- Use Workday's BP compare tool to diff versions
- Document changes for audit and compliance

---

# Part 4: Webhooks and External Connectivity

## 4.1 Outbound Webhooks (Workday to External Systems)

### Overview
Workday can send webhook notifications to external systems when events occur.

### Configuration
Outbound webhooks are typically configured as integration steps in orchestrations:

```
Step Type: REST API Call (Outbound Webhook)
Event: Worker Hire Complete
URL: https://external-system.company.com/api/webhooks/workday-events
Method: POST
Headers:
  Content-Type: application/json
  X-Webhook-Secret: {webhookSecret}
  X-Workday-Tenant: {tenantId}
Body:
{
  "event": "worker.hire.complete",
  "timestamp": "{system.currentDateTime}",
  "data": {
    "workerId": "{steps.GetWorkerData.employeeId}",
    "workerName": "{steps.GetWorkerData.fullName}",
    "email": "{steps.GetWorkerData.email}",
    "department": "{steps.GetWorkerData.department}",
    "hireDate": "{steps.GetWorkerData.hireDate}",
    "jobTitle": "{steps.GetWorkerData.jobTitle}",
    "manager": "{steps.GetWorkerData.managerName}"
  }
}
```

### Webhook Patterns

**Simple Event Notification:**
- Fire-and-forget: Send the event, do not wait for response
- Best for logging, analytics, non-critical notifications

**Request-Response:**
- Send event, wait for response
- Use response data in subsequent orchestration steps
- Implement timeout and retry logic

**Callback Pattern:**
- Send initial request with a callback URL
- External system processes asynchronously
- External system calls the callback URL when complete
- Orchestration has a "Wait for Callback" step

### Webhook Security
- **HMAC Signature**: Sign the payload with a shared secret. Include signature in header.
- **Mutual TLS**: Both sides present certificates
- **API Keys**: Include API key in header
- **OAuth 2.0**: Use bearer token authentication
- **IP Whitelisting**: Restrict to known Workday IP ranges

### Webhook Reliability
- Implement retry logic (3 retries with exponential backoff)
- Log all webhook attempts (success and failure)
- Implement dead letter queue for failed deliveries
- Monitor webhook delivery rates
- Handle duplicate deliveries (idempotent receivers)

## 4.2 Inbound Event Handling (External Systems to Workday)

### REST API Endpoints
External systems can push events to Workday via REST APIs:

```
# Create a worker event
POST /api/staffing/v1/workers
Authorization: Bearer {token}
Content-Type: application/json

{
  "personalData": {
    "nameData": {
      "legalName": {
        "firstName": "Jane",
        "lastName": "Smith"
      }
    }
  }
}
```

### Orchestration Endpoints
External systems can trigger orchestrations directly:

```
POST /api/orchestrations/v1/{orchestrationId}/run
Authorization: Bearer {token}
Content-Type: application/json

{
  "inputs": {
    "externalEventType": "account_created",
    "externalSystemId": "salesforce",
    "externalRecordId": "SF-12345",
    "data": {
      "accountName": "Acme Corp",
      "industry": "Technology",
      "region": "North America"
    }
  }
}
```

### Extend App API Endpoints
Extend apps can expose custom REST endpoints:

```javascript
// Extend app endpoint definition (conceptual)
app.post('/api/v1/external-events', async (req, res) => {
  const { eventType, payload } = req.body;

  // Validate the incoming event
  if (!validateEvent(eventType, payload)) {
    return res.status(400).json({ error: 'Invalid event format' });
  }

  // Process the event
  switch (eventType) {
    case 'customer_update':
      await handleCustomerUpdate(payload);
      break;
    case 'order_placed':
      await handleOrderPlaced(payload);
      break;
    default:
      return res.status(400).json({ error: 'Unknown event type' });
  }

  // Trigger an orchestration if needed
  await workday.orchestrations.run({
    orchestrationId: 'orch_process_external_event',
    inputs: { eventType, payload }
  });

  res.status(200).json({ status: 'accepted' });
});
```

### File-Based Inbound Integration
For batch/file-based inbound processing:
- External system uploads file to SFTP
- Workday EIB or Studio integration polls for new files
- Files are processed and data loaded into Workday
- Processing results are logged

## 4.3 Authentication Patterns

### OAuth 2.0 (Recommended)

**Client Credentials Flow** (system-to-system):
```
1. Register API Client in Workday:
   - Client ID: auto-generated
   - Client Secret: auto-generated
   - Scopes: Define allowed operations
   - Redirect URIs: Not needed for client credentials

2. Obtain Token:
   POST /oauth2/{tenant}/token
   Content-Type: application/x-www-form-urlencoded

   grant_type=client_credentials
   &client_id={clientId}
   &client_secret={clientSecret}
   &scope=staffing:read compensation:read

3. Use Token:
   GET /api/staffing/v1/workers
   Authorization: Bearer {accessToken}
```

**Authorization Code Flow** (user-context):
```
1. Redirect user to Workday authorization:
   GET /oauth2/{tenant}/authorize?
     response_type=code
     &client_id={clientId}
     &redirect_uri={redirectUri}
     &scope=staffing:read

2. User authenticates and authorizes

3. Exchange code for token:
   POST /oauth2/{tenant}/token
   grant_type=authorization_code
   &code={authorizationCode}
   &redirect_uri={redirectUri}
   &client_id={clientId}
   &client_secret={clientSecret}

4. Use access token for API calls
5. Refresh token when expired:
   POST /oauth2/{tenant}/token
   grant_type=refresh_token
   &refresh_token={refreshToken}
   &client_id={clientId}
   &client_secret={clientSecret}
```

### Integration System User (ISU) Authentication
For SOAP web services and some integration patterns:
- Create an Integration System User (ISU) in Workday
- Assign appropriate security groups
- Use username/password in WS-Security header
- Rotate credentials regularly

### API Key Authentication
For simpler integrations:
- Generate API key in Workday
- Include in request header: `X-API-Key: {key}`
- Less common than OAuth 2.0

### Certificate-Based Authentication
For high-security integrations:
- x.509 certificates
- Mutual TLS (mTLS)
- Certificate management in Workday

### Authentication Best Practices
1. **Use OAuth 2.0** whenever possible (most secure, standard)
2. **Rotate secrets** on a regular schedule
3. **Use scopes** to limit API client permissions
4. **Store credentials** in Workday's credential vault, not in integration code
5. **Log authentication events** for audit
6. **Use ISU accounts** (not personal accounts) for integrations
7. **Separate credentials** per environment (sandbox vs production)
8. **Enable MFA** for administrative access to integration configurations

## 4.4 Rate Limiting and Best Practices

### Workday API Rate Limits
- Workday enforces rate limits on API calls
- Limits vary by endpoint and tenant configuration
- Typical limits:
  - REST API: Varies, generally allows sustained throughput with burst capacity
  - SOAP WWS: Similar limits
  - RaaS: Report execution frequency limits
  - WQL: Query rate limits

### Rate Limit Headers
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 950
X-RateLimit-Reset: 1705312800
Retry-After: 30
```

### Handling Rate Limits
```
Rate Limit Strategy:
1. Check rate limit headers on every response
2. If X-RateLimit-Remaining < threshold:
   - Slow down request rate
   - Implement backoff
3. If HTTP 429 received:
   - Wait for Retry-After seconds
   - Retry the request
   - Implement exponential backoff for repeated 429s
4. Log rate limit events for monitoring
```

### Best Practices for External Connectivity

1. **Batch operations** when possible. Do not make individual API calls for each record when batch APIs are available.

2. **Use delta/incremental processing**. Only process changed records, not full data sets.

3. **Implement circuit breakers**. If an external system is consistently failing, stop calling it and alert an administrator.

4. **Use connection pooling**. Reuse HTTP connections instead of creating new ones for each request.

5. **Compress payloads**. Use gzip compression for large data transfers.

6. **Validate data before sending**. Catch errors early to avoid unnecessary API calls.

7. **Implement idempotency**. Ensure that retrying a failed operation does not create duplicates.

8. **Monitor and alert**. Track integration health metrics (latency, error rates, throughput).

9. **Use async patterns** for long-running operations. Do not block on synchronous calls that may take minutes.

10. **Document all integrations**. Maintain a catalog of all integrations with their endpoints, schedules, data flows, and owners.

---

# Part 5: Putting It All Together -- Integration Architecture Patterns

## 5.1 Real-Time Event-Driven Pattern

```
Workday BP Event (Hire)
  -> Orchestration (triggered by event)
    -> Step 1: Get worker details (WQL)
    -> Step 2: Transform data
    -> Step 3: POST to external system (REST webhook)
    -> Step 4: Log result in custom object
    -> Step 5: Send notification
```

**When to use:** Immediate data sync, real-time notifications, time-sensitive operations.

## 5.2 Batch/Scheduled Pattern

```
Schedule (Daily 2 AM)
  -> Orchestration
    -> Step 1: Execute RaaS report for changed workers
    -> Step 2: Loop through results
      -> Step 2a: Transform each record
      -> Step 2b: Upsert to external system
      -> Step 2c: Log result
    -> Step 3: Generate summary report
    -> Step 4: Send completion notification
```

**When to use:** Non-time-sensitive data sync, large data volumes, system reconciliation.

## 5.3 Request-Response Pattern

```
External System
  -> POST to Orchestration endpoint
    -> Step 1: Validate request
    -> Step 2: Look up Workday data
    -> Step 3: Apply business logic
    -> Step 4: Return response
  <- Response with data/status
```

**When to use:** External system needs Workday data on-demand, validation services, lookup services.

## 5.4 Hybrid Pattern (Extend + Orchestration + Integration)

```
User action in Extend App
  -> Extend app server-side logic
    -> Validate and prepare data
    -> Trigger Orchestration
      -> Step 1: Create record in Workday (WWS)
      -> Step 2: Initiate Business Process
      -> Step 3: Call external API for enrichment
      -> Step 4: Update Extend app custom object
    -> Return status to Extend app UI
  -> Update UI with result
```

**When to use:** Complex workflows that span Workday core, Extend apps, and external systems.

## 5.5 Middleware/Integration Platform Pattern

```
Workday -> Orchestration (outbound webhook) -> Integration Platform (MuleSoft, Boomi, etc.)
  -> Transform and Route
    -> System A (Salesforce)
    -> System B (ServiceNow)
    -> System C (Custom App)

Integration Platform -> Workday API (inbound)
  <- Data from external systems
    -> Orchestration (process inbound data)
      -> Update Workday records
```

**When to use:** Enterprise integration scenarios with multiple target systems, complex routing, protocol translation.

---

# Part 6: Key Terminology Quick Reference

| Term | Definition |
|------|-----------|
| **Orchestration** | Workday's workflow automation engine for multi-step processes |
| **Business Process (BP)** | Workday's framework for modeling HR/Finance/operational workflows |
| **EIB** | Enterprise Interface Builder -- simple file-based integration tool |
| **Core Connector** | Pre-built, configurable integration for common patterns |
| **Studio** | Eclipse-based IDE for complex custom integrations |
| **Cloud Connect** | Pre-built partner integrations (ADP, Ceridian, etc.) |
| **RaaS** | Report as a Service -- custom reports accessible via REST |
| **WQL** | Workday Query Language -- SQL-like language for querying Workday data |
| **WWS** | Workday Web Services -- SOAP-based API |
| **ISU** | Integration System User -- service account for integrations |
| **Integration Event** | Record of an integration execution (logs, status, metrics) |
| **Integration System** | Configuration container for an integration (attributes, maps, schedules) |
| **BP Step** | A single action within a Business Process (approval, review, integration, etc.) |
| **Condition Rule** | Reusable boolean expression used to control BP/Orchestration flow |
| **Document Transformation** | XSLT-based data format conversion |
| **Calculated Field** | Derived/computed field in reports and integrations |

---

# Part 7: Common Pitfalls and Troubleshooting

## 7.1 Orchestration Issues

1. **Orchestration timeout**: Long-running orchestrations may hit the maximum execution time. Break into smaller orchestrations or use async patterns.

2. **Variable type mismatch**: Ensure variable types match between steps. A string "123" is not the same as an integer 123.

3. **Null reference errors**: Always check for null before accessing nested properties. Use condition steps to guard against missing data.

4. **Infinite loops**: Ensure loop termination conditions are correct. Add safety limits (max iterations).

5. **Rate limiting in loops**: When calling external APIs in a loop, implement throttling. Add delay steps between iterations.

6. **Credential expiration**: OAuth tokens expire. Ensure token refresh logic is in place. For long-running orchestrations, refresh tokens mid-execution if needed.

## 7.2 Integration Issues

1. **SOAP namespace issues**: Workday SOAP namespaces change between versions. Always use the correct namespace for your version.

2. **Date/time formatting**: Workday uses ISO 8601 with timezone offsets. External systems may expect different formats. Always transform dates explicitly.

3. **Character encoding**: Use UTF-8 consistently. Watch for encoding issues in CSV files, especially with names containing accented characters.

4. **Large payload handling**: Workday APIs may paginate large result sets. Always handle pagination (check for `next` links in REST, `Response_Results` in SOAP).

5. **Sandbox vs Production**: Always test in sandbox first. Ensure environment-specific configurations (URLs, credentials) are parameterized, not hardcoded.

## 7.3 Business Process Issues

1. **In-flight process conflicts**: Changing a BP definition does not affect in-flight processes. Plan migrations carefully.

2. **Security group gaps**: Ensure all BP step actors have the appropriate security group assignments. Missing assignments cause steps to be unroutable.

3. **Condition rule performance**: Complex conditions on high-volume BPs can impact performance. Keep conditions simple and efficient.

4. **Integration step failures**: BP integration steps that fail can block the entire BP. Implement error handling and timeout in the integration.

---

*This guide is part of the Context Foundry Workday Extend extension. It provides comprehensive reference material for AI agents building Extend applications that interact with Workday's orchestration, integration, and business process frameworks.*
