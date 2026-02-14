# Workday Extend: Core Architecture and Metadata Structures

## Comprehensive Developer Reference

---

## 1. What is Workday Extend

### Overview

Workday Extend is Workday's platform-as-a-service (PaaS) offering that allows customers and partners to build custom applications that run natively within the Workday environment. Unlike integrations that sit outside Workday and communicate via APIs, Extend apps are first-class citizens of the Workday platform -- they share the same security model, the same UI framework (the Workday Canvas design system), the same data layer, and the same deployment infrastructure.

### How Extend Fits in the Workday Ecosystem

The Workday platform has several layers:

```
+---------------------------------------------------------------+
|                    Workday Tenant (Customer)                   |
+---------------------------------------------------------------+
|  Core Workday Apps    |  Extend Apps    |  Integrations (EIBs) |
|  (HCM, Finance, etc) |  (Custom apps)  |  (Studio, Cloud     |
|                       |                 |   Connect, etc.)     |
+---------------------------------------------------------------+
|              Workday Application Platform                      |
|  - Business Objects   - Business Processes                     |
|  - Security Domains   - Reporting Engine                       |
|  - Task Framework     - Notification Framework                 |
+---------------------------------------------------------------+
|              Workday Data Layer (Object Store)                 |
+---------------------------------------------------------------+
```

Key points:
- Extend apps run **inside** the Workday tenant, not alongside it
- They use Workday's own security model (security domains, security groups)
- They participate in Workday's business process framework
- They can reference and extend core Workday business objects
- They appear in the Workday UI alongside native functionality (in the global navigation, search, dashboards)

### Extend Apps vs. Traditional Workday Functionality

| Aspect | Core Workday | Workday Extend |
|--------|-------------|----------------|
| Built by | Workday (delivered in updates) | Customers, partners, ISVs |
| Update cycle | Workday's biannual release | Independent of Workday releases |
| Data model | Core business objects | Custom business objects (can reference core) |
| Security | Built-in security policies | Custom security domains (inherits security model) |
| UI | Standard Workday pages | Custom pages using Canvas design system components |
| Business processes | Pre-built workflows | Custom business processes |
| Deployment | Automatic with tenant updates | Deployed via App Manager |
| Technology | Proprietary Workday stack | Metadata-driven (AMD, PMD, SMD) |

### What You Can Build with Extend

- **Custom business applications** - e.g., a visitor management system, an asset tracking app, an IT service desk
- **Process extensions** - extend existing Workday business processes with additional steps
- **Dashboards and reporting apps** - custom analytics views combining core and custom data
- **Integration orchestration apps** - apps that coordinate data flow between Workday and external systems
- **Mobile-first apps** - apps optimized for Workday's mobile experience

### Architecture Principles

Workday Extend is entirely **metadata-driven**. There is no traditional "code" in the sense of compiled executables. Instead, apps are defined through three types of metadata:

1. **AMD (Application Metadata Definition)** -- The application manifest
2. **PMD (Presentation Metadata Definition)** -- The UI layer
3. **SMD (Service Metadata Definition)** -- The backend/service layer

These three metadata types together form the complete definition of an Extend app.

---

## 2. Application Metadata Definition (AMD)

### Purpose

The AMD is the application manifest -- it defines what the application is, what it contains, and how it relates to the Workday platform. Think of it as the `package.json` or `AndroidManifest.xml` equivalent for an Extend app.

### Structure

The AMD is structured as XML metadata. Here is a representative example:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<amd:Application
    xmlns:amd="urn:com.workday/amd"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    id="myCompany_visitorManagement"
    version="1.0.0"
    label="Visitor Management"
    description="Track and manage office visitors">

    <!-- Application Identity -->
    <amd:ApplicationInfo>
        <amd:Id>com.mycompany.visitormanagement</amd:Id>
        <amd:Version>1.0.0</amd:Version>
        <amd:Label>Visitor Management</amd:Label>
        <amd:Description>A complete visitor management solution</amd:Description>
        <amd:Category>Custom</amd:Category>
        <amd:Vendor>My Company</amd:Vendor>
        <amd:MinPlatformVersion>2024.1</amd:MinPlatformVersion>
    </amd:ApplicationInfo>

    <!-- Dependencies on Core Workday Objects -->
    <amd:Dependencies>
        <amd:Dependency type="businessObject" ref="wd:Worker"/>
        <amd:Dependency type="businessObject" ref="wd:Location"/>
        <amd:Dependency type="securityDomain" ref="wd:Security_Domain_HR"/>
    </amd:Dependencies>

    <!-- References to PMD and SMD -->
    <amd:Presentations>
        <amd:Presentation ref="visitorManagement_pmd.xml"/>
    </amd:Presentations>

    <amd:Services>
        <amd:Service ref="visitorManagement_smd.xml"/>
    </amd:Services>

    <!-- Security Configuration -->
    <amd:Security>
        <amd:SecurityDomain id="visitorMgmt_domain">
            <amd:Label>Visitor Management</amd:Label>
            <amd:SecurityPolicy>
                <amd:Permission type="get"/>
                <amd:Permission type="put"/>
                <amd:Permission type="delete"/>
            </amd:SecurityPolicy>
        </amd:SecurityDomain>
    </amd:Security>

    <!-- Navigation / Menu Items -->
    <amd:Navigation>
        <amd:TaskItem id="manageVisitors">
            <amd:Label>Manage Visitors</amd:Label>
            <amd:Icon>people</amd:Icon>
            <amd:Target ref="pmd:visitorListPage"/>
        </amd:TaskItem>
    </amd:Navigation>

</amd:Application>
```

### Key AMD Elements

#### Application Identity

- **id**: A unique identifier for the app, typically namespaced (e.g., `com.mycompany.appname`)
- **version**: Semantic versioning (major.minor.patch). Workday uses this for upgrade management
- **label**: Human-readable name displayed in the Workday UI
- **description**: Shown in the App Manager and marketplace
- **category**: Classification for organizational purposes
- **vendor**: The organization that built the app
- **MinPlatformVersion**: The minimum Workday platform version required to run this app

#### Dependencies

Dependencies declare what core Workday objects, security domains, or other Extend apps this application requires. This allows the platform to:
- Validate that all dependencies are available before installation
- Manage upgrade compatibility
- Provide referential integrity

Types of dependencies:
- **businessObject**: Core Workday objects the app references (Worker, Location, Organization, etc.)
- **securityDomain**: Security domains the app needs access to
- **report**: Core reports the app uses as data sources
- **application**: Other Extend apps this app depends on

#### PMD and SMD References

The AMD connects the three metadata layers:
- `<amd:Presentations>` points to one or more PMD files (UI definitions)
- `<amd:Services>` points to one or more SMD files (service definitions)

This separation allows independent development of UI and backend layers while the AMD ties them together.

#### Security Configuration

Security in Extend apps follows Workday's standard security model:
- **Security Domains** define logical areas of the app
- **Security Policies** define what operations (get, put, delete, etc.) are available
- These are then assigned to **Security Groups** (either existing Workday groups or custom ones)

#### Navigation

The AMD defines how the app appears in the Workday navigation:
- **TaskItems**: Appear in the Workday task search and can be pinned to dashboards
- **Menu entries**: Can appear in the global navigation menu
- **Related Actions**: Can be added to existing Workday pages as related actions

### Versioning Model

Workday Extend uses a versioning scheme that tracks:
- **App version**: The developer's semantic version
- **Platform version**: The Workday release the app was built against
- **Deployment version**: An auto-incremented deployment counter

When the Workday platform is updated (biannual releases), apps may need to be tested against the new platform version. The `MinPlatformVersion` in the AMD helps manage this compatibility.

---

## 3. Presentation Metadata Definition (PMD)

### Purpose

The PMD defines the entire user interface layer of an Extend app. It specifies pages, layouts, components, data bindings, navigation flows, and user interactions. The PMD is interpreted by the Workday rendering engine to produce the actual UI.

### Design System: Canvas

Workday Extend apps use the **Workday Canvas Design System** for their UI. This ensures visual consistency with the rest of the Workday platform. Canvas provides:
- Pre-built components (buttons, forms, tables, cards, etc.)
- Layout primitives (grid, stack, container)
- Typography and color tokens
- Responsive behavior for mobile and desktop

### PMD Structure

```xml
<?xml version="1.0" encoding="UTF-8"?>
<pmd:Presentation
    xmlns:pmd="urn:com.workday/pmd"
    id="visitorManagement_presentation">

    <!-- Page Definitions -->
    <pmd:Page id="visitorListPage" type="list">
        <pmd:Title>All Visitors</pmd:Title>
        <pmd:Layout type="fullWidth">

            <!-- Search/Filter Bar -->
            <pmd:Component type="searchBar" id="visitorSearch">
                <pmd:DataBinding source="smd:VisitorBusinessObject"
                                 field="visitorName"/>
                <pmd:Placeholder>Search visitors...</pmd:Placeholder>
            </pmd:Component>

            <!-- Data Grid/Table -->
            <pmd:Component type="grid" id="visitorGrid">
                <pmd:DataSource ref="smd:getAllVisitors"/>
                <pmd:Columns>
                    <pmd:Column field="visitorName" label="Visitor Name"
                                sortable="true"/>
                    <pmd:Column field="visitDate" label="Visit Date"
                                type="date" sortable="true"/>
                    <pmd:Column field="hostWorker" label="Host"
                                type="reference" ref="wd:Worker"/>
                    <pmd:Column field="status" label="Status"
                                type="enum"/>
                    <pmd:Column field="actions" type="actions">
                        <pmd:Action type="view"
                                    target="visitorDetailPage"/>
                        <pmd:Action type="edit"
                                    target="visitorEditPage"/>
                    </pmd:Column>
                </pmd:Columns>
                <pmd:Pagination pageSize="20"/>
            </pmd:Component>

            <!-- Floating Action Button -->
            <pmd:Component type="button" id="addVisitorBtn">
                <pmd:Label>Register Visitor</pmd:Label>
                <pmd:Icon>add</pmd:Icon>
                <pmd:Action type="navigate" target="visitorCreatePage"/>
            </pmd:Component>

        </pmd:Layout>
    </pmd:Page>

    <!-- Detail Page -->
    <pmd:Page id="visitorDetailPage" type="detail">
        <pmd:Title expression="{{visitor.visitorName}}"/>
        <pmd:DataSource ref="smd:getVisitor" param="visitorId"/>

        <pmd:Layout type="twoColumn">
            <pmd:Section position="main">
                <pmd:Component type="fieldGroup">
                    <pmd:Field ref="visitorName" label="Name"/>
                    <pmd:Field ref="company" label="Company"/>
                    <pmd:Field ref="email" label="Email"/>
                    <pmd:Field ref="phone" label="Phone"/>
                </pmd:Component>

                <pmd:Component type="fieldGroup" label="Visit Details">
                    <pmd:Field ref="visitDate" label="Date" type="date"/>
                    <pmd:Field ref="visitPurpose" label="Purpose"/>
                    <pmd:Field ref="hostWorker" label="Host"
                               type="workerReference"/>
                    <pmd:Field ref="location" label="Location"
                               type="locationReference"/>
                </pmd:Component>
            </pmd:Section>

            <pmd:Section position="sidebar">
                <pmd:Component type="statusIndicator" ref="status"/>
                <pmd:Component type="relatedActions">
                    <pmd:Action label="Check In" ref="smd:checkInVisitor"
                                condition="status == 'Expected'"/>
                    <pmd:Action label="Check Out" ref="smd:checkOutVisitor"
                                condition="status == 'CheckedIn'"/>
                    <pmd:Action label="Cancel Visit"
                                ref="smd:cancelVisit"
                                condition="status != 'Completed'"/>
                </pmd:Component>
            </pmd:Section>
        </pmd:Layout>
    </pmd:Page>

    <!-- Create/Edit Page -->
    <pmd:Page id="visitorCreatePage" type="create">
        <pmd:Title>Register New Visitor</pmd:Title>
        <pmd:DataSource ref="smd:VisitorBusinessObject" mode="create"/>

        <pmd:Layout type="form">
            <pmd:Step label="Visitor Information">
                <pmd:Field ref="visitorName" label="Full Name"
                           required="true"/>
                <pmd:Field ref="company" label="Company"/>
                <pmd:Field ref="email" label="Email"
                           validation="email"/>
                <pmd:Field ref="phone" label="Phone Number"/>
            </pmd:Step>
            <pmd:Step label="Visit Details">
                <pmd:Field ref="visitDate" label="Visit Date"
                           type="date" required="true"/>
                <pmd:Field ref="visitPurpose" label="Purpose of Visit"
                           type="textarea"/>
                <pmd:Field ref="hostWorker" label="Host (Employee)"
                           type="workerPrompt" required="true"/>
                <pmd:Field ref="location" label="Location"
                           type="locationPrompt"/>
            </pmd:Step>
            <pmd:SubmitAction ref="smd:createVisitor"
                              successTarget="visitorDetailPage"
                              successMessage="Visitor registered successfully"/>
        </pmd:Layout>
    </pmd:Page>

    <!-- Dashboard Worklet -->
    <pmd:Dashboard id="visitorDashboard">
        <pmd:Title>Visitor Overview</pmd:Title>
        <pmd:Worklet id="todaysVisitors" size="half">
            <pmd:Title>Today's Visitors</pmd:Title>
            <pmd:DataSource ref="smd:getTodaysVisitors"/>
            <pmd:Component type="metric">
                <pmd:Value expression="{{count}}"/>
                <pmd:Label>Expected Today</pmd:Label>
            </pmd:Component>
        </pmd:Worklet>
        <pmd:Worklet id="visitorChart" size="half">
            <pmd:Title>Visitors This Week</pmd:Title>
            <pmd:DataSource ref="smd:getWeeklyVisitorStats"/>
            <pmd:Component type="barChart">
                <pmd:XAxis field="day"/>
                <pmd:YAxis field="count"/>
            </pmd:Component>
        </pmd:Worklet>
    </pmd:Dashboard>

</pmd:Presentation>
```

### Key PMD Concepts

#### Page Types

- **List Page**: Displays a collection of business objects in a grid/table format. Typically the entry point for managing a set of records.
- **Detail Page (View Page)**: Shows the details of a single business object instance. Read-only with action buttons.
- **Create Page**: A form for creating a new instance of a business object. Often uses a multi-step wizard layout.
- **Edit Page**: A form for modifying an existing business object instance.
- **Task Page**: A page associated with a step in a business process.
- **Report Page**: Displays report output, charts, and analytics.

#### Layout Types

- **fullWidth**: Single column taking full available width
- **twoColumn**: Main content area with sidebar (common for detail pages)
- **form**: Multi-step wizard form layout
- **dashboard**: Grid layout for worklets and widgets
- **responsive**: Automatically adjusts between mobile and desktop

#### Components

Components map to Canvas design system elements:

| Component Type | Description | Common Properties |
|---------------|-------------|-------------------|
| `grid` | Data table/grid | columns, pagination, sorting, filtering |
| `fieldGroup` | Group of labeled fields | fields, label, collapsible |
| `field` | Individual data field | ref, type, label, required, validation |
| `button` | Action button | label, icon, action, variant |
| `searchBar` | Search/filter input | dataBinding, placeholder |
| `metric` | KPI/metric display | value, label, trend |
| `chart` | Various chart types (bar, line, pie, donut) | dataSource, axes |
| `statusIndicator` | Visual status badge | ref, colorMapping |
| `card` | Content card | title, body, actions |
| `tabs` | Tabbed content area | tabs with content |
| `relatedActions` | Action menu/buttons | actions with conditions |
| `workerPhoto` | Employee photo | workerRef |
| `richText` | Rich text display/editor | content, editable |

#### Data Binding

Data binding connects UI components to backend data defined in the SMD:

- **DataSource reference**: `ref="smd:getAllVisitors"` -- points to a data source or service endpoint in the SMD
- **Field reference**: `ref="visitorName"` -- binds a field to a property on the current data context
- **Expression binding**: `expression="{{visitor.visitorName}}"` -- dynamic expressions that evaluate at render time
- **Conditional rendering**: `condition="status == 'Expected'"` -- show/hide components based on data values

#### Navigation and Routing

Navigation between pages is defined through:
- **target**: References a page id within the PMD
- **params**: Parameters passed to the target page (e.g., object ID)
- **type**: Navigation type (navigate, modal, drawer, back)

```xml
<pmd:Action type="navigate" target="visitorDetailPage">
    <pmd:Param name="visitorId" value="{{id}}"/>
</pmd:Action>
```

#### Responsive Behavior

PMD supports responsive design through:
- **Breakpoints**: Components can specify different configurations for mobile, tablet, desktop
- **Visibility conditions**: `visible-on="desktop"` or `visible-on="mobile"`
- **Layout adaptation**: Columns collapse into single-column layouts on smaller screens

---

## 4. Service Metadata Definition (SMD)

### Purpose

The SMD defines the backend layer of an Extend app. It specifies business objects (data model), business processes (workflows), web service endpoints, data sources, validation rules, calculated fields, and integration points. The SMD is the "brains" of the application.

### SMD Structure

```xml
<?xml version="1.0" encoding="UTF-8"?>
<smd:Service
    xmlns:smd="urn:com.workday/smd"
    id="visitorManagement_service">

    <!-- ============================= -->
    <!-- BUSINESS OBJECTS (Data Model)  -->
    <!-- ============================= -->

    <smd:BusinessObject id="Visitor" label="Visitor">
        <smd:Description>Represents an external visitor</smd:Description>

        <!-- Simple Fields -->
        <smd:Field id="visitorName" type="text" required="true">
            <smd:Label>Visitor Name</smd:Label>
            <smd:MaxLength>100</smd:MaxLength>
        </smd:Field>

        <smd:Field id="company" type="text">
            <smd:Label>Company</smd:Label>
        </smd:Field>

        <smd:Field id="email" type="text">
            <smd:Label>Email Address</smd:Label>
            <smd:Validation type="email"/>
        </smd:Field>

        <smd:Field id="phone" type="text">
            <smd:Label>Phone Number</smd:Label>
        </smd:Field>

        <smd:Field id="visitDate" type="date" required="true">
            <smd:Label>Visit Date</smd:Label>
        </smd:Field>

        <smd:Field id="visitPurpose" type="text">
            <smd:Label>Purpose of Visit</smd:Label>
            <smd:MaxLength>500</smd:MaxLength>
        </smd:Field>

        <smd:Field id="checkInTime" type="dateTime">
            <smd:Label>Check-In Time</smd:Label>
        </smd:Field>

        <smd:Field id="checkOutTime" type="dateTime">
            <smd:Label>Check-Out Time</smd:Label>
        </smd:Field>

        <!-- Enum Field -->
        <smd:Field id="status" type="enum" required="true">
            <smd:Label>Status</smd:Label>
            <smd:DefaultValue>Expected</smd:DefaultValue>
            <smd:EnumValues>
                <smd:Value id="Expected" label="Expected"/>
                <smd:Value id="CheckedIn" label="Checked In"/>
                <smd:Value id="CheckedOut" label="Checked Out"/>
                <smd:Value id="Cancelled" label="Cancelled"/>
                <smd:Value id="NoShow" label="No Show"/>
            </smd:EnumValues>
        </smd:Field>

        <!-- Reference to Core Workday Object -->
        <smd:Field id="hostWorker" type="reference"
                   referenceType="wd:Worker" required="true">
            <smd:Label>Host Employee</smd:Label>
        </smd:Field>

        <!-- Reference to Core Workday Object -->
        <smd:Field id="location" type="reference"
                   referenceType="wd:Location">
            <smd:Label>Office Location</smd:Label>
        </smd:Field>

        <!-- Calculated Field -->
        <smd:Field id="visitDuration" type="decimal" calculated="true">
            <smd:Label>Visit Duration (hours)</smd:Label>
            <smd:Calculation>
                <smd:Expression>
                    HOURS_BETWEEN(checkInTime, checkOutTime)
                </smd:Expression>
            </smd:Calculation>
        </smd:Field>

        <!-- Boolean Field -->
        <smd:Field id="ndaSigned" type="boolean">
            <smd:Label>NDA Signed</smd:Label>
            <smd:DefaultValue>false</smd:DefaultValue>
        </smd:Field>

        <!-- System Fields (auto-generated) -->
        <smd:SystemFields>
            <smd:Field id="createdBy" type="reference"
                       referenceType="wd:Worker" readonly="true"/>
            <smd:Field id="createdDate" type="dateTime" readonly="true"/>
            <smd:Field id="lastModifiedBy" type="reference"
                       referenceType="wd:Worker" readonly="true"/>
            <smd:Field id="lastModifiedDate" type="dateTime"
                       readonly="true"/>
        </smd:SystemFields>

        <!-- Indexes for query performance -->
        <smd:Indexes>
            <smd:Index fields="visitDate" />
            <smd:Index fields="hostWorker" />
            <smd:Index fields="status, visitDate" />
        </smd:Indexes>

    </smd:BusinessObject>

    <!-- ============================= -->
    <!-- BUSINESS PROCESSES (Workflows) -->
    <!-- ============================= -->

    <smd:BusinessProcess id="registerVisitor"
                         label="Register Visitor">
        <smd:Description>
            Process for registering a new visitor
        </smd:Description>
        <smd:TriggerType>manual</smd:TriggerType>
        <smd:InputObject ref="Visitor"/>

        <!-- Step 1: Initiation -->
        <smd:Step id="initiate" type="initiation">
            <smd:Label>Register Visitor</smd:Label>
            <smd:AllowedSecurityGroups>
                <smd:SecurityGroup ref="visitorMgmt_users"/>
            </smd:AllowedSecurityGroups>
        </smd:Step>

        <!-- Step 2: Approval (optional) -->
        <smd:Step id="managerApproval" type="approval" optional="true">
            <smd:Label>Manager Approval</smd:Label>
            <smd:ApproverRule>
                <smd:Expression>
                    hostWorker.manager
                </smd:Expression>
            </smd:ApproverRule>
            <smd:Condition>
                <smd:Expression>
                    visitor.ndaSigned == false
                </smd:Expression>
            </smd:Condition>
        </smd:Step>

        <!-- Step 3: Notification -->
        <smd:Step id="notifyHost" type="notification">
            <smd:Label>Notify Host</smd:Label>
            <smd:Recipients>
                <smd:Expression>hostWorker</smd:Expression>
            </smd:Recipients>
            <smd:NotificationTemplate ref="visitorRegisteredNotif"/>
        </smd:Step>

        <!-- Step 4: Complete -->
        <smd:Step id="complete" type="completion">
            <smd:PostAction>
                <smd:SetField ref="status" value="Expected"/>
            </smd:PostAction>
        </smd:Step>

    </smd:BusinessProcess>

    <!-- ============================= -->
    <!-- DATA SOURCES (Queries)         -->
    <!-- ============================= -->

    <smd:DataSource id="getAllVisitors" type="query">
        <smd:Description>Get all visitors with filtering</smd:Description>
        <smd:Source ref="Visitor"/>
        <smd:Fields>
            <smd:Field ref="visitorName"/>
            <smd:Field ref="visitDate"/>
            <smd:Field ref="hostWorker"/>
            <smd:Field ref="status"/>
            <smd:Field ref="location"/>
        </smd:Fields>
        <smd:Filters>
            <smd:Filter field="visitDate" operator="between"
                        parameterized="true"/>
            <smd:Filter field="status" operator="equals"
                        parameterized="true"/>
        </smd:Filters>
        <smd:DefaultSort field="visitDate" direction="descending"/>
        <smd:Pagination maxPageSize="50"/>
    </smd:DataSource>

    <smd:DataSource id="getTodaysVisitors" type="query">
        <smd:Source ref="Visitor"/>
        <smd:Fields>
            <smd:Field ref="visitorName"/>
            <smd:Field ref="hostWorker"/>
            <smd:Field ref="status"/>
        </smd:Fields>
        <smd:Filters>
            <smd:Filter field="visitDate" operator="equals"
                        value="TODAY()"/>
        </smd:Filters>
    </smd:DataSource>

    <smd:DataSource id="getWeeklyVisitorStats" type="aggregate">
        <smd:Source ref="Visitor"/>
        <smd:GroupBy field="visitDate" granularity="day"/>
        <smd:Aggregate function="count" alias="count"/>
        <smd:Filters>
            <smd:Filter field="visitDate" operator="greaterThanOrEqual"
                        value="START_OF_WEEK()"/>
        </smd:Filters>
    </smd:DataSource>

    <smd:DataSource id="getVisitor" type="single">
        <smd:Source ref="Visitor"/>
        <smd:Parameter name="visitorId" type="id" required="true"/>
    </smd:DataSource>

    <!-- ============================= -->
    <!-- SERVICE ENDPOINTS (Actions)    -->
    <!-- ============================= -->

    <smd:Endpoint id="createVisitor" type="create">
        <smd:Description>Create a new visitor record</smd:Description>
        <smd:BusinessObject ref="Visitor"/>
        <smd:Validation>
            <smd:Rule field="visitDate"
                      expression="visitDate >= TODAY()"
                      message="Visit date must be today or in the future"/>
            <smd:Rule field="email"
                      expression="MATCHES(email, EMAIL_PATTERN)"
                      message="Invalid email format"/>
        </smd:Validation>
        <smd:PostAction ref="registerVisitor"/>
    </smd:Endpoint>

    <smd:Endpoint id="checkInVisitor" type="update">
        <smd:Description>Check in a visitor</smd:Description>
        <smd:BusinessObject ref="Visitor"/>
        <smd:PreCondition>
            <smd:Expression>status == 'Expected'</smd:Expression>
            <smd:ErrorMessage>
                Only expected visitors can be checked in
            </smd:ErrorMessage>
        </smd:PreCondition>
        <smd:Actions>
            <smd:SetField ref="status" value="CheckedIn"/>
            <smd:SetField ref="checkInTime" value="NOW()"/>
        </smd:Actions>
    </smd:Endpoint>

    <smd:Endpoint id="checkOutVisitor" type="update">
        <smd:Description>Check out a visitor</smd:Description>
        <smd:BusinessObject ref="Visitor"/>
        <smd:PreCondition>
            <smd:Expression>status == 'CheckedIn'</smd:Expression>
        </smd:PreCondition>
        <smd:Actions>
            <smd:SetField ref="status" value="CheckedOut"/>
            <smd:SetField ref="checkOutTime" value="NOW()"/>
        </smd:Actions>
    </smd:Endpoint>

    <smd:Endpoint id="cancelVisit" type="update">
        <smd:Description>Cancel a scheduled visit</smd:Description>
        <smd:BusinessObject ref="Visitor"/>
        <smd:PreCondition>
            <smd:Expression>
                status == 'Expected'
            </smd:Expression>
        </smd:PreCondition>
        <smd:Actions>
            <smd:SetField ref="status" value="Cancelled"/>
        </smd:Actions>
    </smd:Endpoint>

    <!-- ============================= -->
    <!-- WEB SERVICE (External API)     -->
    <!-- ============================= -->

    <smd:WebService id="visitorAPI" type="REST">
        <smd:BasePath>/api/custom/visitors</smd:BasePath>

        <smd:Operation method="GET" path="/">
            <smd:DataSource ref="getAllVisitors"/>
        </smd:Operation>

        <smd:Operation method="GET" path="/{visitorId}">
            <smd:DataSource ref="getVisitor"/>
        </smd:Operation>

        <smd:Operation method="POST" path="/">
            <smd:Endpoint ref="createVisitor"/>
        </smd:Operation>

        <smd:Operation method="PUT" path="/{visitorId}/checkin">
            <smd:Endpoint ref="checkInVisitor"/>
        </smd:Operation>
    </smd:WebService>

    <!-- ============================= -->
    <!-- NOTIFICATIONS                  -->
    <!-- ============================= -->

    <smd:NotificationTemplate id="visitorRegisteredNotif">
        <smd:Subject>
            Visitor {{visitor.visitorName}} registered for
            {{visitor.visitDate}}
        </smd:Subject>
        <smd:Body>
            A visitor has been registered:
            - Name: {{visitor.visitorName}}
            - Company: {{visitor.company}}
            - Date: {{visitor.visitDate}}
            - Purpose: {{visitor.visitPurpose}}
        </smd:Body>
    </smd:NotificationTemplate>

</smd:Service>
```

### Key SMD Concepts

#### Business Objects

Business objects are the core data model of an Extend app. They are analogous to database tables but operate within Workday's object store.

**Field Types:**
| Type | Description | Example |
|------|-------------|---------|
| `text` | String/text data | Names, descriptions |
| `numeric` | Integer numbers | Counts, quantities |
| `decimal` | Decimal numbers | Amounts, percentages |
| `boolean` | True/false | Flags, toggles |
| `date` | Date only | Visit date, due date |
| `dateTime` | Date and time | Timestamps |
| `enum` | Enumerated values | Status, category |
| `reference` | Reference to another business object | Worker, Location |
| `currency` | Money with currency code | Amount, cost |
| `richText` | Formatted text | Descriptions, notes |
| `attachment` | File attachment | Documents, images |
| `multi-instance` | Collection/array of sub-objects | Line items, addresses |

**Reference Fields:**
Reference fields create relationships between business objects. They can reference:
- Core Workday objects (`wd:Worker`, `wd:Location`, `wd:Organization`, `wd:CostCenter`, etc.)
- Other custom business objects defined in the same app
- Business objects from other Extend apps (if a dependency is declared)

**Calculated Fields:**
Fields whose values are derived from expressions rather than stored directly:
```xml
<smd:Field id="totalCost" type="currency" calculated="true">
    <smd:Calculation>
        <smd:Expression>quantity * unitPrice</smd:Expression>
    </smd:Calculation>
</smd:Field>
```

Built-in functions available in expressions:
- `NOW()`, `TODAY()` -- current date/time
- `HOURS_BETWEEN(start, end)` -- time calculations
- `DAYS_BETWEEN(start, end)` -- date arithmetic
- `IF(condition, trueValue, falseValue)` -- conditional logic
- `CONCATENATE(str1, str2, ...)` -- string concatenation
- `SUM()`, `COUNT()`, `AVG()`, `MIN()`, `MAX()` -- aggregations
- `CURRENT_USER()` -- the logged-in worker
- `MATCHES(value, pattern)` -- regex matching

#### Business Processes

Business processes define workflows -- sequences of steps that data flows through. Extend business processes work the same as core Workday business processes:

**Step Types:**
- **initiation**: The starting step where a user triggers the process
- **approval**: Requires one or more approvers to approve/deny
- **review**: Like approval but informational (no approve/deny action)
- **to-do**: An action item assigned to a person
- **notification**: Sends a notification to specified recipients
- **integration**: Calls an external system
- **sub-process**: Invokes another business process
- **completion**: Final step that commits the data

**Approver Rules:**
Approver rules dynamically determine who should approve a step:
```xml
<smd:ApproverRule>
    <smd:Expression>initiator.manager</smd:Expression>
</smd:ApproverRule>
```

Common patterns:
- `initiator.manager` -- the initiator's manager
- `securityGroup("HR_Partner")` -- all members of a security group
- `lookup("costCenterOwner", visitor.location.costCenter)` -- lookup-based routing

**Conditional Steps:**
Steps can be conditional, only executing when a condition is met:
```xml
<smd:Condition>
    <smd:Expression>amount > 1000</smd:Expression>
</smd:Condition>
```

#### Data Sources

Data sources define how data is queried from the object store. They are referenced by PMD components and web service operations.

**Query Types:**
- **query**: Returns multiple results with optional filtering, sorting, pagination
- **single**: Returns a single record by ID
- **aggregate**: Returns grouped/aggregated data (for charts, metrics)
- **report**: Wraps a Workday report as a data source

**Filter Operators:**
- `equals`, `notEquals`
- `contains`, `startsWith`, `endsWith`
- `greaterThan`, `greaterThanOrEqual`, `lessThan`, `lessThanOrEqual`
- `between`
- `in` (list of values)
- `isNull`, `isNotNull`

#### Web Service Endpoints

Extend apps can expose REST APIs that external systems can call:
- These are secured by Workday's standard API authentication (OAuth 2.0)
- They use the same security domains defined in the AMD
- They can perform CRUD operations on custom business objects
- They can trigger business processes

#### Validation Rules

Validation rules enforce data integrity at the service layer:
```xml
<smd:Validation>
    <smd:Rule field="startDate"
              expression="startDate <= endDate"
              message="Start date must be before end date"/>
    <smd:Rule field="quantity"
              expression="quantity > 0"
              message="Quantity must be positive"/>
</smd:Validation>
```

---

## 5. The Extend App Lifecycle

### Phase 1: Planning and Setup

1. **Identify the use case** -- What business problem does the app solve? Could it be addressed with configuration of existing Workday features instead?

2. **Register as a developer** at developer.workday.com:
   - Create a developer account
   - Register your organization
   - Request a developer tenant (sandbox) or connect to an existing tenant

3. **Set up API credentials**:
   - Create an API client in the Workday tenant
   - Configure OAuth 2.0 credentials
   - Set up the integration system user

4. **Review platform capabilities**:
   - Available business object types
   - UI component library
   - Business process framework
   - API limits and constraints

### Phase 2: Development

#### In-Tenant Development (Visual Builder)

Workday provides an in-tenant development experience through the **Extend App Builder**:

1. Navigate to the "Create App" task in Workday
2. Use the visual designer to:
   - Define business objects and their fields
   - Create pages with drag-and-drop components
   - Configure business processes with the workflow designer
   - Set up security domains and policies
3. Preview the app in the development tenant
4. The visual builder generates AMD, PMD, and SMD metadata behind the scenes

#### Development Portal / IDE-Based Development

For more advanced scenarios, developers can:

1. Export the app metadata as files (XML/JSON)
2. Edit the metadata directly in an IDE
3. Use the Workday Extend SDK/CLI tools to:
   - Validate metadata syntax
   - Deploy to the development tenant
   - Run tests
4. Import the modified metadata back

#### Key Development Activities

- **Define the data model**: Create business objects with fields, relationships, indexes
- **Build the UI**: Define pages, layouts, components, data bindings
- **Configure business processes**: Set up approval chains, notifications, conditions
- **Set up security**: Define security domains, assign to security groups
- **Create web services**: Expose APIs for external integration (if needed)
- **Test in sandbox**: Verify all functionality in the developer tenant

### Phase 3: Testing

- **Functional testing**: Test all CRUD operations, business processes, validations
- **Security testing**: Verify access controls by testing with different security roles
- **Performance testing**: Test with realistic data volumes
- **Integration testing**: If the app integrates with external systems, test those flows
- **User acceptance testing (UAT)**: Have business users validate the app in a sandbox tenant
- **Cross-device testing**: Verify the app works on desktop and mobile (Workday app)

### Phase 4: Packaging

An Extend app is packaged into a deployment artifact that includes:
- AMD, PMD, SMD metadata files
- App configuration
- Version information
- Dependencies

The package format is a structured archive that the Workday platform knows how to process.

### Phase 5: Deployment

Deployment is done through the **App Manager** in the target Workday tenant:

1. **Upload the app package** to the App Manager
2. **Configure tenant-specific settings** (e.g., default values, integration endpoints)
3. **Assign security groups** to the app's security domains
4. **Activate the app** -- makes it available to users
5. The app appears in the Workday navigation, search, and dashboard configuration

### Phase 6: Updates and Maintenance

- **Version management**: New versions are uploaded through the App Manager
- **Migration**: Data model changes require migration definitions (add field, rename field, etc.)
- **Compatibility**: Apps must be tested against new Workday platform versions (biannual releases)
- **Monitoring**: Use Workday's monitoring tools to track app usage, errors, performance
- **Deprecation**: Old versions can be deprecated and eventually decommissioned

### The Update Lifecycle

```
Developer               App Manager (Tenant)
   |                         |
   |  1. Build v1.1          |
   |  2. Package             |
   |  3. Upload      ------> |
   |                         |  4. Review changes
   |                         |  5. Test in sandbox
   |                         |  6. Approve
   |                         |  7. Activate
   |                         |  8. Data migration runs
   |                         |  9. Users see updated app
```

---

## 6. Developer Portal (developer.workday.com)

### Overview

The Workday Developer Portal is the central hub for Extend app development. It provides:

- Documentation and API references
- Developer tenant provisioning
- API credentials management
- App registration and publishing
- Community forums and support

### Registration and Setup

1. **Create an account** at developer.workday.com
   - Individual developer accounts are free
   - Partner and ISV accounts require approval from Workday

2. **Organization registration**:
   - Register your organization (company/partner)
   - Assign roles (admin, developer, viewer)

3. **Request a developer tenant**:
   - Workday provides sandbox tenants for development
   - These are isolated Workday environments with sample data
   - They receive platform updates on the same schedule as production tenants

### Connecting to a Workday Tenant

To connect your development environment to a Workday tenant:

1. **In the Workday tenant** (requires admin/ISU access):
   - Navigate to "Register API Client for Integrations"
   - Create a new API client
   - Note the Client ID and Client Secret
   - Configure OAuth 2.0 scopes (read/write for relevant domains)
   - Create or designate an Integration System User (ISU)
   - Assign appropriate security groups to the ISU

2. **In the Developer Portal**:
   - Add the tenant connection with:
     - Tenant URL (e.g., `https://wd5-impl-services1.workday.com/ccx/`)
     - Client ID
     - Client Secret
     - Token endpoint
     - ISU username
   - Test the connection

### API Authentication Flow

Workday uses OAuth 2.0 for API authentication:

```
Developer App         Workday Token Endpoint        Workday API
     |                        |                         |
     | 1. POST /token         |                         |
     |    grant_type=          |                         |
     |    client_credentials   |                         |
     |    client_id=xxx        |                         |
     |    client_secret=yyy    |                         |
     | ----------------------> |                         |
     |                        |                         |
     | 2. Access Token         |                         |
     | <---------------------- |                         |
     |                                                   |
     | 3. API Call with Bearer token                      |
     | ------------------------------------------------> |
     |                                                   |
     | 4. Response                                       |
     | <------------------------------------------------ |
```

Key OAuth details:
- **Grant type**: `client_credentials` for server-to-server
- **Token endpoint**: `https://{tenant-host}/ccx/oauth2/{tenant}/token`
- **API endpoint**: `https://{tenant-host}/ccx/api/{version}/{tenant}/`
- **Scopes**: Determined by the security groups assigned to the ISU

### Tenant Types

| Tenant Type | Purpose | Data | Updates |
|-------------|---------|------|---------|
| Developer Sandbox | Development/testing | Sample data | Platform updates |
| Implementation (Impl) | Pre-production testing | Copy of production data | Platform updates |
| Production | Live system | Real data | Managed updates |
| Preview | Early access to upcoming release | N/A | Next release |

### The Relationship Between Portal and In-Tenant

The Developer Portal and the in-tenant development experience are complementary:

- **Portal**: Registration, credentials, documentation, app listing/publishing, cross-tenant management
- **In-Tenant**: Actual app building (visual builder), testing, configuration, deployment
- **Bridge**: The portal credentials allow CLI/IDE tools to connect to the tenant for programmatic development and deployment

---

## 7. App Manager in Tenant

### Overview

The App Manager is the administrative interface within a Workday tenant for managing Extend apps. It is accessible to Workday administrators and handles the full lifecycle of apps within a given tenant.

### Accessing App Manager

- Search for "App Manager" in the Workday search bar
- Or navigate through: Menu > Administration > App Manager
- Requires the "Application Administrator" security role or equivalent

### Installing an Extend App

1. **Upload**: Navigate to App Manager > "Install App"
2. **Review**: Review the app's metadata, security domains, dependencies
3. **Dependencies check**: Workday verifies all dependencies are met (referenced business objects, security domains, etc.)
4. **Security configuration**: Assign the app's security domains to security groups
   - This determines which users can access which parts of the app
5. **Configuration**: Set any tenant-specific configuration values
6. **Activate**: Make the app available to users

### Managing Installed Apps

The App Manager shows:
- **App list**: All installed Extend apps with status, version, vendor
- **App details**: AMD information, dependencies, security configuration
- **Version history**: Previous versions of the app
- **Usage metrics**: How many users are using the app, frequency
- **Error logs**: Runtime errors and issues

### Configuration and Tenant-Level Settings

Extend apps can define configurable parameters that admins set per-tenant:
```xml
<amd:Configuration>
    <amd:Parameter id="defaultLocation" type="reference"
                   referenceType="wd:Location">
        <amd:Label>Default Office Location</amd:Label>
        <amd:Description>
            The default location for new visitor registrations
        </amd:Description>
    </amd:Parameter>
    <amd:Parameter id="requireNDA" type="boolean">
        <amd:Label>Require NDA for All Visitors</amd:Label>
        <amd:DefaultValue>false</amd:DefaultValue>
    </amd:Parameter>
    <amd:Parameter id="notificationEmail" type="text">
        <amd:Label>Notification Email Address</amd:Label>
    </amd:Parameter>
</amd:Configuration>
```

These are set in the App Manager and accessed by the app at runtime.

### Monitoring and Troubleshooting

**Error Categories:**
- **Deployment errors**: Metadata validation failures, dependency issues
- **Runtime errors**: Business process failures, data validation errors, expression evaluation errors
- **Security errors**: Access denied due to misconfigured security groups
- **Integration errors**: Web service call failures, timeouts

**Diagnostic Tools:**
- **Business Process Monitor**: View in-progress and completed business process instances
- **Integration Event Logs**: Track API calls and integration events
- **Error Inbox**: Centralized view of all app errors
- **Audit Trail**: Who did what, when (Workday's standard audit capabilities)

### Security Domains and Permissions

Security in Workday Extend follows the standard Workday security model:

```
Security Domain (defined in AMD)
    |
    +-- Security Policy (get, put, delete, etc.)
            |
            +-- Assigned to Security Group(s)
                    |
                    +-- Contains Workers/Users
```

**Key security concepts:**
- **Security Domain**: A logical grouping of securable items (like a module or feature area)
- **Security Policy**: Defines what operations are allowed in a domain
- **Security Group**: A collection of users who share the same access
- **Constrained Security Group**: Access limited to specific instances (e.g., only visitors at the user's location)

**Example security setup for the visitor management app:**

| Security Domain | Security Group | Permissions |
|----------------|----------------|-------------|
| Visitor Management - View | All Workers | Get |
| Visitor Management - Manage | Front Desk Staff | Get, Put, Delete |
| Visitor Management - Admin | HR Administrators | Get, Put, Delete, Modify Security |
| Visitor Management - Reports | Manager | Get (reports only) |

### Integration with Core Workday Features

Extend apps can integrate with several core Workday capabilities:

- **Workday Search**: Custom business objects appear in global search
- **Dashboards**: Custom worklets can be added to Workday dashboards
- **Notifications**: Use Workday's notification framework
- **Reports**: Custom business objects can be used as report data sources
- **Related Actions**: Add custom actions to existing Workday pages
- **Inbox**: Business process tasks appear in users' Workday inbox
- **Mobile**: Apps work in the Workday mobile app (if PMD is responsive)

---

## 8. Key Technical Details and Patterns

### Common Architectural Patterns

#### Master-Detail Pattern
A list page showing all records with navigation to a detail page for each record. This is the most common pattern for data management apps.

```
AMD: Defines app, security domains, navigation task
PMD: List page (grid) + Detail page (field groups) + Create/Edit page (form)
SMD: Business object + Query data source + Single data source + CRUD endpoints
```

#### Approval Workflow Pattern
A create form that triggers a business process requiring approval before the record is finalized.

```
AMD: Defines app + security for initiator vs. approver
PMD: Create page (form with submit) + Approval task page
SMD: Business object + Business process (initiation -> approval -> completion)
```

#### Dashboard/Analytics Pattern
A read-only app that aggregates and visualizes data.

```
AMD: Defines app + read-only security
PMD: Dashboard with worklets (metrics, charts)
SMD: Aggregate data sources + Report-type data sources
```

#### Integration Hub Pattern
An app that orchestrates data exchange between Workday and external systems.

```
AMD: Defines app + integration security domains
PMD: Configuration page + Status/monitoring page
SMD: Web service endpoints + Integration business process steps
```

### Best Practices

1. **Security-first design**: Plan security domains and groups before building
2. **Reference core objects**: Use Workday's existing objects (Worker, Location, Organization) rather than duplicating data
3. **Keep business objects focused**: One business object per entity, avoid "god objects"
4. **Use business processes for important actions**: Any action that needs auditability, approval, or notifications should go through a business process
5. **Design for mobile**: Test the PMD on mobile screen sizes
6. **Plan for data migration**: Design business objects with future field additions in mind
7. **Use calculated fields wisely**: Calculated fields recompute on every read; for expensive calculations, consider storing the result
8. **Leverage existing security groups**: Reuse Workday's built-in security groups where possible
9. **Document your metadata**: Use description elements in AMD, PMD, and SMD for maintainability
10. **Version carefully**: Breaking changes to business objects require migration definitions

### Limitations and Constraints

- **No custom code execution**: Extend apps are entirely metadata-driven; there is no ability to run arbitrary code (JavaScript, Python, etc.)
- **Limited expression language**: The expression/formula language is not a full programming language
- **Object store, not relational DB**: You cannot write SQL queries; data access is through the data source framework
- **Tenant isolation**: An Extend app in one tenant cannot access data in another tenant
- **API rate limits**: Web service endpoints are subject to Workday's API rate limiting
- **Size limits**: Business objects have limits on the number of fields, depth of references
- **No direct file system access**: Apps cannot read/write files on a server; file handling is through Workday's attachment framework
- **Update compatibility**: Business object schema changes must be backward-compatible or include migration
- **UI framework constraints**: The UI is limited to what the Canvas component library provides; no custom HTML/CSS/JavaScript

### Workday Extend vs. Workday Orchestrations vs. Workday Integration Cloud

| Feature | Extend | Orchestrations | Integration Cloud |
|---------|--------|---------------|-------------------|
| Purpose | Custom apps with UI | Workflow automation | Data integration |
| UI | Full UI (pages, dashboards) | No UI (background processes) | No UI (data pipelines) |
| Data model | Custom business objects | Uses existing objects | Transforms data |
| Business processes | Yes, custom | Yes, orchestration steps | No |
| API exposure | Yes (REST) | Yes (triggers) | Yes (endpoints) |
| Complexity | High (full apps) | Medium (workflows) | Medium (integrations) |
| Coding | Metadata (AMD/PMD/SMD) | Low-code (visual designer) | Low-code (templates) |

---

## 9. Core Workday Objects Commonly Referenced by Extend Apps

These are the core Workday business objects that Extend apps most frequently reference:

| Object | Namespace | Description | Common Use |
|--------|-----------|-------------|------------|
| Worker | `wd:Worker` | An employee or contingent worker | Assignee, owner, approver |
| Organization | `wd:Organization` | Organizational unit | Scoping, filtering |
| Supervisory Organization | `wd:Supervisory_Organization` | Manager-report hierarchy | Approval chains |
| Location | `wd:Location` | Physical location | Office, site assignment |
| Cost Center | `wd:Cost_Center` | Financial allocation unit | Budget tracking |
| Company | `wd:Company` | Legal entity | Multi-company scenarios |
| Job Profile | `wd:Job_Profile` | Job role definition | Role-based access |
| Position | `wd:Position` | Filled/vacant position | Staffing apps |
| Academic Unit | `wd:Academic_Unit` | (Higher Ed) Department | Education apps |
| Customer | `wd:Customer` | External customer | CRM-like apps |
| Supplier | `wd:Supplier` | External vendor | Procurement apps |

These can be used as `referenceType` values in business object field definitions to create relationships between custom and core data.

---

## 10. Summary: How AMD, PMD, and SMD Work Together

```
                    AMD (Application Manifest)
                    /                         \
                   /                           \
                  v                             v
    PMD (Presentation Layer)          SMD (Service Layer)
    - Pages                           - Business Objects
    - Layouts                         - Business Processes
    - Components                      - Data Sources
    - Data Bindings ----------------> - Endpoints
    - Navigation                      - Web Services
    - Dashboards                      - Validations
                                      - Notifications
```

1. **AMD** is the root -- it identifies the app, declares dependencies on core Workday objects, defines security domains, sets up navigation/menu items, and points to PMD and SMD files.

2. **SMD** defines the data and logic layer -- business objects (schema), business processes (workflows), data sources (queries), endpoints (CRUD actions), web services (external APIs), and notification templates.

3. **PMD** defines the presentation layer -- pages (list, detail, create, edit), layouts, UI components, and data bindings that reference SMD data sources and endpoints.

The flow at runtime:
1. User navigates to an Extend app (via search, dashboard, or menu) -- AMD navigation definition tells Workday which PMD page to render
2. PMD page is rendered -- layout, components, fields are drawn using Canvas design system
3. Components request data via data source bindings -- these are SMD data source definitions that query the object store
4. User takes an action (submit form, click button) -- triggers an SMD endpoint
5. Endpoint validates data, executes actions, and optionally kicks off a business process
6. Business process steps execute (approvals, notifications, etc.)
7. Data is committed to the object store
8. UI updates to reflect the new state

---

## Appendix: Glossary

| Term | Definition |
|------|-----------|
| **AMD** | Application Metadata Definition -- the app manifest |
| **PMD** | Presentation Metadata Definition -- the UI layer |
| **SMD** | Service Metadata Definition -- the backend/service layer |
| **Business Object** | A data entity in the Workday object store (like a database table) |
| **Business Process** | A workflow with steps (approval, notification, etc.) |
| **Security Domain** | A logical area of the app with access control policies |
| **Security Group** | A collection of users with shared access rights |
| **Canvas** | Workday's design system used for all UI components |
| **ISU** | Integration System User -- a service account for API access |
| **Tenant** | A customer's Workday instance/environment |
| **App Manager** | The in-tenant admin interface for managing Extend apps |
| **Worklet** | A small dashboard widget showing a metric, chart, or summary |
| **Related Action** | A context menu action that can be added to existing Workday pages |
| **Data Source** | An SMD definition that queries data from the object store |
| **Endpoint** | An SMD definition that performs an action (create, update, delete) |
| **Orchestration** | A separate Workday feature for workflow automation (not the same as Extend) |
