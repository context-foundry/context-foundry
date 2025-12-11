# Workday Extend Extension

**CRITICAL**: Read this file when working with Workday Extend / PMD applications.

## What is Workday Extend?

Workday Extend is a low-code platform for building custom applications within Workday. Apps are built using:

- **PMD (Page Metadata Definition)**: JSON files defining UI pages with widgets
- **AMD (App Metadata)**: JSON file defining app structure, flows, and tasks
- **Expression Language**: `<% %>` syntax for dynamic values and logic

## Quick Reference

### Expression Syntax: `<% ... %>`

```javascript
// Literals
<% 'Hello' %>                    // String
<% 123 %>                        // Number
<% true %>                       // Boolean
<% {:} %>                        // Empty object
<% { 'key': value } %>           // Object
<% [1, 2, 3] %>                  // Array

// Variables
<% self.value %>                 // Current widget
<% pageVariables.myState %>      // Page state
<% queryParams.id %>             // URL parameter
<% flowVariables.workerId %>     // Flow variable (multi-page flows)
<% tenant %>                     // Current tenant
<% userTimeZone %>               // User's timezone

// Operators
<% empty value %>                // Check null/empty
<% value ?: 'default' %>         // Elvis (falsy default)
<% value ?? 'default' %>         // Null coalescing
<% cond ? a : b %>               // Ternary

// Control flow
<% if (cond) { ... } else { ... } %>
<% var x = 10; %>                // Variable declaration

// Array methods
<% items.filter(x => { x.active }) %>
<% items.map(x => { x.name }) %>
<% items.find(x => { x.name == 'Target' }) %>
<% items.size() %>
<% items.join(', ') %>

// Date functions
<% date:getTodaysDateFormatted(date:getDateTimeZone(userTimeZone), 'yyyy-MM-dd') %>
<% date:parseDateString(dateStr).minusYears(1).format('yyyy-MM-dd') %>
<% date:parseDateString(dateStr).plusDays(30).format('yyyy-MM-dd') %>

// List functions
<% list:toList('value1', 'value2') %>           // Create list
<% list:toMap(items, 'id') %>                   // Convert to map by key
<% list:mapAttribute(errors, 'error') %>        // Extract attribute from list
```

### Widget Methods

```javascript
widget.getValue()        // Get value
widget.value             // Get/set value
widget.setVisible(bool)  // Show/hide
widget.setError('msg')   // Set error
widget.clearError()      // Clear error
endpoint.invoke()        // Call deferred endpoint
section.data = result    // Bind data to dynamicSection
```

## PMD Page Structure

**Required**: `id` and `presentation`. Everything else is optional.

```json
{
  "id": "pageName",
  "securityDomains": ["domain1"],
  "include": ["sharedScript.script"],
  "script": "<% var myVar = 10; %>",
  "endPoints": [],
  "onLoad": "<% pageVariables.init = true; %>",
  "onSubmit": "<% return true; %>",
  "outboundData": { "outboundEndPoints": [...] },
  "presentation": {
    "pageType": "EDIT",
    "micro": false,
    "standardEditButtonsHidden": true,
    "title": { "type": "title", "label": "Page Title" },
    "body": { "type": "section", "children": [...] },
    "footer": { "type": "footer", "children": [...] }
  }
}
```

See [PMD-STRUCTURE.md](docs/PMD-STRUCTURE.md) for complete property reference.

## Event Handlers

All event handlers start with "on":

| Handler | When | Use For |
|---------|------|---------|
| `onChange` | Widget value changes | Validation, warnings, update other widgets |
| `onClick` | Button clicked | API calls, state changes |
| `onLoad` | Page loads (after endpoints, before widgets) | Initialize state, manipulate data |
| `onSubmit` | OK/Submit button clicked | Final validation, calculations |
| `onRowSelect` | Grid row selected | Load details, update related widgets |
| `onSend` | Outbound data being sent | Transform data for next page |

```javascript
// onChange example - show warning
onChange: "<%
  self.clearWarning();
  if (self.value == 'risky') {
    self.setWarning('This option has limitations');
  }
%>"

// onLoad example - fetch data and store in pageVariables
onLoad: "<%
  var currYear = date:getTodaysDateFormatted(date:getDateTimeZone('America/Los_Angeles'), 'yyyy-01-01');
  var today = date:getTodaysDateFormatted(date:getDateTimeZone('America/Los_Angeles'), 'yyyy-MM-dd');
  var reqMap = {'start': currYear, 'end': today, 'worker': currentWorker.id};
  pageVariables.holidays = holidayService.invoke(reqMap).data;
%>"

// onSubmit example - validation
onSubmit: "<%
  if (passcode.value == 'Workday') {
    passcode.clearError();
  } else {
    passcode.value = '';
    passcode.setError('Wrong passcode');
  }
%>"

// onRowSelect example - load details
onRowSelect: "<% gridEvents.selectRow(); %>"
```

**Warnings (yellow)** - Don't block submission by default
**Errors (red)** - Block submission

## Common Widgets

| Type | Purpose |
|------|---------|
| `section` | Container with children |
| `fieldSet` | Container with title border |
| `cardContainer` | Card layout (MASONRY, etc.) |
| `card` | Card with cardId and parameters |
| `text` | Text input |
| `textArea` | Multi-line input |
| `readOnlyText` | Display-only text with valueOutBinding |
| `richText` | HTML-formatted text |
| `checkBox` | Checkbox |
| `dropdown` | Dropdown select (instanceList or values) |
| `date` | Date picker with datePrecision, dateFormat |
| `button` | Navigation button |
| `pageActionButton` | Client-side action with `onClick` |
| `editButtonBar` | Submit/Cancel buttons for forms |
| `grid` | Data table |
| `instanceList` | Worker/object reference list |
| `dynamicSection` | Data-bound container |

## Endpoint Patterns

### Basic Endpoint
```json
{
  "name": "getData",
  "baseUrlType": "workday-staffing",
  "url": "/workers?limit=30",
  "authType": "sso",
  "deferred": true,
  "onSend": "<% self.data = {...}; return self.data; %>"
}
```

### WQL Query Endpoint
```json
{
  "name": "employeeSearch",
  "baseUrlType": "workday-wql",
  "url": "/data",
  "authType": "sso",
  "wqlQuery": {
    "queryId": "employeeSearch",
    "parameters": { "manager": "<% me.id %>" }
  }
}
```

### Dynamic URL with Fallback
```json
{
  "name": "selectedWorker",
  "baseUrlType": "workday-common",
  "url": "<%`/{{queryParams.workerId ?? flowVariables.workerId}}` %>",
  "authType": "sso"
}
```

### Outbound POST Endpoint
```json
{
  "name": "submitFeedback",
  "baseUrlType": "workday-performance-enablement",
  "url": "<% `/workers/{{workerId}}/anytimeFeedbackEvents` %>",
  "httpMethod": "POST",
  "exclude": "<% pageVariables.skipSubmit %>",
  "values": [
    { "outboundPath": "comment", "value": "<% comment.value %>" },
    { "outboundPath": "badge.id", "value": "<% badgeId %>" }
  ]
}
```

**Invoke deferred endpoint in onClick:**
```javascript
<%
pageVariables.result = getData.invoke();
mySection.data = pageVariables.result;
%>
```

## Key Patterns

### Navigation with Parameters
```json
"taskReference": {
  "taskId": "targetPage",
  "parameterBindings": { "id": "<% row.id %>" }
}
```

### Conditional Rendering
```json
"render": "<% queryParams.showSection ?: false %>"
"visible": "<% !empty myData %>"
```

### Grid with Row Actions
```json
{
  "type": "grid",
  "rows": "<% endpoint.items %>",
  "rowVariableName": "item",
  "columns": [{
    "type": "column",
    "cellTemplate": {
      "type": "button",
      "taskReference": {
        "parameterBindings": { "id": "<% item.id %>" }
      }
    }
  }]
}
```

### Grid with Selection and Events
```json
{
  "type": "grid",
  "id": "reqGrid",
  "rows": "<% requisitions.data %>",
  "rowVariableName": "row",
  "selectionEnabled": true,
  "maxRowSelection": 1,
  "onRowSelect": "<% gridEvents.selectRow(); %>",
  "columns": [
    {
      "type": "column",
      "columnId": "quantityColumn",
      "cellTemplate": {
        "type": "number",
        "fractionDigits": 2,
        "onChange": "<% gridEvents.changeCost(); %>"
      }
    }
  ]
}
```

### Instance List with Search (Typeahead)
```json
{
  "type": "instanceList",
  "id": "workerSearch",
  "label": "Worker",
  "values": "<% workers.data %>",
  "multiSelect": false,
  "searchEndPoint": "<% endpoints.workerSearch %>",
  "searchResultValues": "<% workerSearch.data %>",
  "onChange": "<% scripts.populate(self.value); %>"
}
```

### Input Validation
```javascript
onChange: "<%
  self.clearError();
  if (!empty(self.value) && !validate:match('^\\d+$', self.value)) {
    self.setError('Must be numeric');
  }
%>"
```

### Flow Variables (Multi-Page Flows)
```json
// Reading flow variables
"render": "<% flowVariables.withGiftcard %>"
"value": "<% flowVariables.workerId %>"

// Writing flow variables (outboundData)
"outboundEndPoints": [{
  "type": "outboundVariable",
  "variableScope": "flow",
  "values": [{ "outboundPath": "workerId", "value": "<% selectedEmployee.value[0] %>" }]
}]
```

### Card Container with Cards
```json
{
  "type": "cardContainer",
  "layout": "MASONRY",
  "cards": [{
    "type": "card",
    "cardId": "FeedbackOption",
    "parameters": "<% { 'category': 'Innovation', 'icon': 'wd-accent-lightbulb' } %>"
  }]
}
```

### Dropdown with Static Values
```json
{
  "type": "dropdown",
  "id": "amount",
  "label": "Amount",
  "selectedValues": "<% list:toList('$25') %>",
  "instanceList": [
    { "id": "25", "descriptor": "$25" },
    { "id": "50", "descriptor": "$50" }
  ]
}
```

### Dropdown with Dynamic Values
```json
{
  "type": "dropdown",
  "id": "employeeList",
  "values": "<% (employees.data ?? []).map(emp => {{'id': emp.id, 'descriptor': emp.descriptor}}) %>"
}
```

### Date Widget with Formatting
```json
{
  "type": "date",
  "id": "eventDate",
  "datePrecision": "DAY",
  "dateFormat": "yyyy-MM-dd",
  "value": "<% record.feedbackDate ?? '' %>"
}
```

### Edit Button Bar (Form Submit)
```json
{
  "type": "editButtonBar",
  "editButtons": [{
    "type": "editButton",
    "buttonType": "PRIMARY",
    "label": "Submit"
  }]
}
```

### Micro Page (Popup/Confirmation)
```json
{
  "presentation": {
    "headerSize": "HIDDEN",
    "micro": "true",
    "standardEditButtonsHidden": "<% true %>"
  }
}
```

### Reusable Pod Definition
```json
{
  "podId": "doneButton",
  "seed": {
    "template": {
      "type": "editButtonBar",
      "editButtons": [{
        "type": "editButton",
        "label": "Done",
        "buttonType": "PRIMARY",
        "ignoreRequiredFields": "true"
      }]
    }
  }
}
```

### Using Pods in Pages
```json
{ "type": "pod", "podId": "doneButton" }
```

### AMD Flow Definition (Multi-step Pages)
```json
{
  "flowDefinitions": [{
    "id": "wizardFlow",
    "flowSteps": [
      {
        "id": "step1",
        "taskId": "inputPage",
        "transitions": [{ "order": "a", "value": "step2", "condition": "true" }]
      },
      {
        "id": "step2",
        "taskId": "summaryPage"
      }
    ]
  }]
}
```

### AMD Data Providers
```json
{
  "dataProviders": [
    { "key": "workday-common", "value": "<% apiGatewayEndpoint + '/common/v1' %>" },
    { "key": "workday-holiday", "value": "<% apiGatewayEndpoint + '/holiday/v1' %>" }
  ]
}
```

### Console Logging (Development Only)
```javascript
// For DEVELOPMENT/DEBUGGING only - remove before production!
console.debug('Debug: ', myValue);
console.info('Info: ', result);
console.warn('Warning: ', issue);
console.error('Error: ', error);
// View in: Analytics > Logs (filter: wd_category is console)
```

> **Important:** Console statements must be removed before production deployment.
> The `ScriptConsoleLog` quality rule will flag any remaining console calls.

## Detailed Documentation

- **[APP-BUILDER.md](docs/APP-BUILDER.md)** - IDE layout, components panel, deployment workflow
- **[GRAMMAR.md](docs/GRAMMAR.md)** - Expression syntax, comments, null handling
- **[PMD-FUNCTIONS.md](docs/PMD-FUNCTIONS.md)** - Official PMD function reference (bool, date, list, json, map, object, string)
- **[PMD-STRUCTURE.md](docs/PMD-STRUCTURE.md)** - Page properties (onLoad, onSubmit, outboundData, security)
- **[WIDGETS.md](docs/WIDGETS.md)** - All widget types and properties
- **[ENDPOINTS.md](docs/ENDPOINTS.md)** - API binding patterns
- **[AMD-STRUCTURE.md](docs/AMD-STRUCTURE.md)** - App Metadata (navigation, flows, data providers)
- **[SMD-STRUCTURE.md](docs/SMD-STRUCTURE.md)** - Site Metadata (auth, languages, CDN)
- **[PATTERNS.md](docs/PATTERNS.md)** - Event handlers, flow variables, translations, reusable pods
- **[QUALITY-RULES.md](docs/QUALITY-RULES.md)** - 42 code quality rules (from ArcaneAuditor)

## Quality Rules (CRITICAL for Agents)

**All Claude Code agents (Architect, Builder, Test) MUST follow the [Quality Rules](docs/QUALITY-RULES.md)** when building Extend apps. These 42 rules ensure production-quality code.

### Quick Reference: ACTION Rules (Must Fix)

| Rule | Requirement |
|------|-------------|
| `EndpointFailOnStatusCodes` | Add `failOnStatusCodes: [{code: 400}, {code: 403}]` to all endpoints |
| `PMDSecurityDomain` | Add `securityDomains` array to every PMD page |
| `WidgetIdRequired` | Add `id` property to every widget |
| `HardcodedWorkdayAPI` | Never hardcode `*.workday.com` - use `apiGatewayEndpoint` |
| `NoIsCollection` | Never use `isCollection: true` on inbound endpoints |
| `OnlyMaximumEffort` | Never use `bestEffort: true` on endpoints |
| `ScriptConsoleLog` | Remove all `console.log` statements |
| `GridPaging` | Never combine `autoPaging` with `sortableAndFilterable` |

### Quick Reference: ADVICE Rules (Should Fix)

| Category | Rules |
|----------|-------|
| **Naming** | lowerCamelCase for: endpoints, widgets, variables, parameters, files |
| **Scripts** | Use `let/const` not `var`, array methods not loops, descriptive names |
| **Complexity** | Functions <50 lines, embedded scripts <30 lines, nesting <4 levels |
| **Security** | No hardcoded WIDs or applicationIds - use app attributes |

### For Test Agent

Use `tests/extend-quality-checklist.json` to validate built apps against all 42 rules.

## Examples

See `examples/` folder for complete PMD files:
- `buttons.json` - All button types
- `editWizard.json` - Multi-step wizard
- `sentimentAnalysisPage.json` - API integration, charts
- `gridsEdit.json` - Grids with tabs, pagination
- `grids.json` - Basic grid with row actions
- `flowSurveyPage.json` - Flow page 1: onLoad, onSubmit, outboundData
- `flowResultsPage.json` - Flow page 2: receive flow variables

## Common Mistakes to Avoid

1. **String vs Boolean properties**: `"enabled": "false"` (string) vs `"visible": true` (boolean)
2. **parameterBindings overwrites parameters**: Use one or the other
3. **Deferred endpoints require `.invoke()`**: Auto-call only if `deferred: false`
4. **Expression delimiter**: Always wrap in `<% %>`, including inside JSON strings
5. **Empty object syntax**: Use `{:}` not `{}`

## Extension-Scoped Patterns

This extension includes learned patterns in `patterns/extend-common-issues.json`. These patterns are:

- **Scoped to Extend only** - Never merged into global Context Foundry patterns
- **Auto-injected** - Automatically added to phase prompts when building Extend apps
- **Severity-filtered** - Only HIGH severity patterns injected to keep prompts focused

### Pattern Categories

| Severity | Count | Examples |
|----------|-------|----------|
| HIGH | 20+ | Missing failOnStatusCodes, security domains, widget IDs |
| MEDIUM | 5+ | Empty object syntax, var instead of let/const |
| LOW | 5+ | Single-letter params, magic numbers |

### How Patterns Work

1. When Context Foundry detects an Extend project (via files or prompt keywords)
2. `session-summary.json` is created with `configuration.extension = "extend"`
3. Phase execution loads `extensions/extend/patterns/extend-common-issues.json`
4. High-severity patterns are formatted and injected into phase prompts
5. Agents receive patterns alongside CLAUDE.md documentation

### Adding New Patterns

Edit `patterns/extend-common-issues.json`:

```json
{
  "id": "extend-your-pattern-id",
  "error_pattern": "regex to match",
  "description": "What's wrong",
  "solution": "How to fix it",
  "severity": "high|medium|low",
  "example_bad": "{ bad code }",
  "example_good": "{ good code }"
}
```

Patterns stay in this extension and are never pushed to global storage.
