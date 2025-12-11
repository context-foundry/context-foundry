# Workday Extend Quality Rules

**CRITICAL**: Claude Code agents (Architect, Builder, Test) MUST follow these rules when building Workday Extend applications. These rules are derived from ArcaneAuditor's 42 validation rules.

## Rule Severity Levels

- **ACTION** - Must fix. These rules catch issues that cause bugs, security holes, or performance problems.
- **ADVICE** - Should fix. These rules improve code quality, maintainability, and consistency.

---

## Quick Reference: Critical Rules (ACTION)

| Rule | What To Do |
|------|------------|
| **EndpointFailOnStatusCodes** | Always add `failOnStatusCodes: [{code: 400}, {code: 403}]` to endpoints |
| **PMDSecurityDomain** | Always add `securityDomains` array to PMD pages |
| **WidgetIdRequired** | Always add `id` property to widgets |
| **HardcodedWorkdayAPI** | Never hardcode `*.workday.com` URLs - use `apiGatewayEndpoint` |
| **NoIsCollectionOnEndpoints** | Never use `isCollection: true` on inbound endpoints |
| **OnlyMaximumEffort** | Never use `bestEffort: true` on endpoints |
| **NoPMDSessionVariables** | Never use `variableScope: "session"` on outbound endpoints |
| **ScriptConsoleLog** | Remove all `console.log`/`console.debug` statements |
| **GridPagingWithSortable** | Never combine `autoPaging` with `sortableAndFilterable` columns |

---

## Endpoint Rules

### EndpointFailOnStatusCodesRule (ACTION)

**Always add error handling to endpoints.**

```json
// WRONG - Missing error handling
{
  "name": "getWorker",
  "url": "/workers/me"
}

// CORRECT - Has failOnStatusCodes
{
  "name": "getWorker",
  "url": "/workers/me",
  "failOnStatusCodes": [
    {"code": 400},
    {"code": 403}
  ]
}
```

### EndpointNameLowerCamelCaseRule (ADVICE)

**Endpoint names must use lowerCamelCase.**

```json
// WRONG
"name": "get_user_data"    // snake_case
"name": "GetUserProfile"   // PascalCase

// CORRECT
"name": "getUserData"
"name": "getUserProfile"
```

### EndpointBaseUrlTypeRule (ADVICE)

**Use baseUrlType instead of hardcoded URLs for Workday APIs.**

```json
// WRONG - Hardcoded URL
{
  "name": "getWorker",
  "url": "<% apiGatewayEndpoint + '/common/v1/workers/me' %>"
}

// CORRECT - Use baseUrlType
{
  "name": "getWorker",
  "url": "/workers/me",
  "baseUrlType": "workday-common"
}
```

### HardcodedWorkdayAPIRule (ACTION)

**Never hardcode *.workday.com URLs.**

```json
// WRONG
"url": "https://api.workday.com/common/v1/workers"

// CORRECT
"url": "<% apiGatewayEndpoint + '/common/v1/workers' %>"
// Or better, use baseUrlType (see above)
```

### NoIsCollectionOnEndpointsRule (ACTION)

**Never use isCollection: true on inbound endpoints** - causes severe performance degradation.

```json
// WRONG - Can crash tenant performance
{
  "name": "getWorkers",
  "isCollection": true
}

// CORRECT - Use WQL or RaaS instead for large datasets
{
  "name": "getWorkers"
  // Use WQL query endpoint for better performance
}
```

### OnlyMaximumEffortRule (ACTION)

**Never use bestEffort: true** - silently swallows API failures.

```json
// WRONG - Masks API failures
{
  "name": "saveData",
  "bestEffort": true
}

// CORRECT - Let failures bubble up
{
  "name": "saveData"
  // No bestEffort property
}
```

### NoPMDSessionVariablesRule (ACTION)

**Never use variableScope: "session"** - causes memory leaks.

```json
// WRONG - Memory persists entire session
{
  "type": "outboundVariable",
  "variableScope": "session"
}

// CORRECT - Use flow scope
{
  "type": "outboundVariable",
  "variableScope": "flow"
}
```

---

## Widget Rules

### WidgetIdRequiredRule (ACTION)

**Every widget must have an `id` property** (except: footer, item, group, title, pod, cardContainer, card, column).

```json
// WRONG - Missing id
{
  "type": "richText",
  "label": "Welcome"
}

// CORRECT - Has id
{
  "type": "richText",
  "id": "welcomeMessage",
  "label": "Welcome"
}
```

### WidgetIdLowerCamelCaseRule (ADVICE)

**Widget IDs must use lowerCamelCase.**

```json
// WRONG
"id": "WelcomeMessage"   // PascalCase
"id": "welcome_message"  // snake_case

// CORRECT
"id": "welcomeMessage"
```

### FooterPodRequiredRule (ADVICE)

**Footers should use pod structure for reusability.**

```json
// WRONG - Inline footer content
{
  "footer": {
    "type": "footer",
    "children": [{"type": "richText", "id": "footerText"}]
  }
}

// CORRECT - Use pod for reusability
{
  "footer": {
    "type": "footer",
    "children": [{"type": "pod", "podId": "footer"}]
  }
}
```

### GridPagingWithSortableFilterableRule (ACTION)

**Never combine paging with sortableAndFilterable** - causes severe performance issues.

```json
// WRONG - Loads entire dataset client-side
{
  "type": "grid",
  "autoPaging": true,
  "columns": [{
    "columnId": "name",
    "sortableAndFilterable": true  // BAD with paging!
  }]
}

// CORRECT - Choose one or the other
{
  "type": "grid",
  "columns": [{
    "columnId": "name",
    "sortableAndFilterable": true
  }]
  // No autoPaging
}
```

---

## Security Rules

### PMDSecurityDomainRule (ACTION)

**Every PMD page must have securityDomains** (except microConclusion pages and error pages).

```json
// WRONG - Missing security
{
  "id": "myPage",
  "presentation": {...}
}

// CORRECT - Has security domains
{
  "id": "myPage",
  "securityDomains": ["ViewAdminPages"],
  "presentation": {...}
}
```

### HardcodedApplicationIdRule (ADVICE)

**Never hardcode applicationId - use site.applicationId.**

```javascript
// WRONG
const appId = "acmeCorp_speedy";

// CORRECT
const appId = site.applicationId;
```

### HardcodedWidRule (ADVICE)

**Never hardcode WIDs - use app attributes.**

```javascript
// WRONG - WID will break in other environments
const query = "WHERE country = 'd9e41a8c446c11de98360015c5e6daf6'";

// CORRECT - Use app attribute
const usaLocation = appAttr.usaLocation;
const query = `WHERE country = ${usaLocation}`;
```

---

## Script Quality Rules

### ScriptVarUsageRule (ADVICE)

**Use `let` or `const` instead of `var`.**

```javascript
// WRONG
var myVariable = "value";

// CORRECT
const myVariable = "value";  // Immutable
let mutableVar = "value";    // Mutable
```

### ScriptConsoleLogRule (ACTION)

**Remove all console statements before production.**

```javascript
// WRONG - Debug code in production
console.log("Processing data:", data);
console.debug("User:", user);

// CORRECT - Remove console statements
// (or use conditional logging with app attributes)
```

### ScriptVariableNamingRule (ADVICE)

**Variables must use lowerCamelCase.**

```javascript
// WRONG
const user_name = "John";     // snake_case
const UserAge = 25;           // PascalCase

// CORRECT
const userName = "John";
const userAge = 25;
```

### ScriptFunctionParameterNamingRule (ADVICE)

**Function parameters must use lowerCamelCase.**

```javascript
// WRONG
const validateUser = function(user_id, user_name) {...};

// CORRECT
const validateUser = function(userId, userName) {...};
```

### ScriptDescriptiveParameterRule (ADVICE)

**Use descriptive names in array methods, not single letters.**

```javascript
// WRONG - Confusing single letters
const activeUsers = users.filter(x => x.active);
const userNames = users.map(u => u.name);

// CORRECT - Descriptive names
const activeUsers = users.filter(user => user.active);
const userNames = users.map(user => user.name);
```

### ScriptArrayMethodUsageRule (ADVICE)

**Use array methods (map, filter, forEach) instead of for loops.**

```javascript
// WRONG - Manual loop
const results = [];
for (let i = 0; i < items.length; i++) {
    if (items[i].active) {
        results.add(items[i].name);
    }
}

// CORRECT - Array methods
const results = items
    .filter(item => item.active)
    .map(item => item.name);
```

### ScriptNestedArraySearchRule (ADVICE)

**Avoid nested array searches - use list:toMap for O(1) lookups.**

```javascript
// WRONG - O(n^2) performance, can cause out-of-memory
const result = workers.map(worker =>
    orgData.find(org => org.id == worker.orgId)
);

// CORRECT - O(n) with map lookup
const orgById = list:toMap(orgData, 'id');
const result = workers.map(worker => orgById[worker.orgId]);
```

### ScriptMagicNumberRule (ADVICE)

**Use named constants instead of magic numbers.**

```javascript
// WRONG - Magic numbers hide meaning
if (price > 1000) {
    return price * 0.15;
}

// CORRECT - Named constants
const premiumThreshold = 1000;
const premiumDiscount = 0.15;
if (price > premiumThreshold) {
    return price * premiumDiscount;
}
```

### ScriptStringConcatRule (ADVICE)

**Use PMD template literals instead of string concatenation.**

```javascript
// WRONG - String concatenation
const message = "Hello " + userName + ", welcome!";

// CORRECT - Template literal
const message = `Hello {{userName}}, welcome!`;
```

### ScriptVerboseBooleanCheckRule (ADVICE)

**Use concise boolean expressions.**

```javascript
// WRONG - Verbose
if (user.active == true) {...}
if (user.active != false) {...}

// CORRECT - Concise
if (user.active) {...}
if (!user.active) {...}
```

---

## Complexity Rules

### ScriptComplexityRule (ADVICE)

**Keep cyclomatic complexity under 10.** Break complex functions into smaller ones.

```javascript
// WRONG - Complexity > 10 (too many if/else/loops)
const processOrder = function(order) {
    if (order.type == 'premium') {
        if (order.amount > 1000) {
            if (order.customer.vip) {
                // ... more nesting
            }
        }
    }
    // Many more branches...
};

// CORRECT - Break into focused functions
const processOrder = function(order) {
    if (order.type == 'premium') {
        processPremiumOrder(order);
    } else {
        processStandardOrder(order);
    }
};
```

### ScriptNestingLevelRule (ADVICE)

**Keep nesting under 4 levels.** Use early returns.

```javascript
// WRONG - 5+ levels of nesting
if (data) {
    if (data.isValid) {
        if (data.hasContent) {
            if (data.content.size() > 0) {
                if (data.content[0].isActive) {
                    return data.content[0];
                }
            }
        }
    }
}

// CORRECT - Early returns
if (empty data || !data.isValid || !data.hasContent) {
    return null;
}
return data.content[0].isActive ? data.content[0] : null;
```

### ScriptLongFunctionRule (ADVICE)

**Keep functions under 50 lines.** Break into smaller functions.

### ScriptLongBlockRule (ADVICE)

**Keep embedded script blocks (onLoad, onChange, etc.) under 30 lines.**

### ScriptFunctionParameterCountRule (ADVICE)

**Keep function parameters under 4.** Use objects for many parameters.

```javascript
// WRONG - 6 parameters
function createUser(name, email, phone, address, age, department) {...}

// CORRECT - Grouped into logical objects
function createUser(personalInfo, contactInfo, workInfo) {...}
```

---

## Dead Code Rules

### ScriptUnusedVariableRule (ADVICE)

**Remove unused variables.**

```javascript
// WRONG - unusedVar is dead code
const unusedVar = "never used";
const result = calculateResult();
return result;

// CORRECT - Only used variables
const result = calculateResult();
return result;
```

### ScriptUnusedFunctionRule (ADVICE)

**Remove functions that are declared but never called.**

### ScriptUnusedFunctionParametersRule (ADVICE)

**Remove parameters that are declared but never used.**

### ScriptDeadCodeRule (ADVICE)

**In standalone .script files, ensure all top-level declarations are exported or used internally.**

### ScriptUnusedIncludesRule (ADVICE)

**Remove script includes that are never called.**

```json
// WRONG - helper.script is never used
{
  "include": ["util.script", "helper.script"],
  "onLoad": "<% util.doSomething(); %>"
}

// CORRECT - Only include what's used
{
  "include": ["util.script"],
  "onLoad": "<% util.doSomething(); %>"
}
```

---

## Structure Rules

### PMDSectionOrderingRule (ADVICE)

**Follow consistent section ordering in PMD files:**

1. `id`
2. `securityDomains`
3. `include`
4. `script`
5. `endPoints`
6. `onSubmit`
7. `outboundData`
8. `onLoad`
9. `presentation`

### FileNameLowerCamelCaseRule (ADVICE)

**File names must use lowerCamelCase.**

```
// WRONG
MyPage.pmd              // PascalCase
worker_detail.pmd       // snake_case
FOOTER.pod              // UPPERCASE

// CORRECT
myPage.pmd
workerDetail.pmd
footer.pod
```

### StringBooleanRule (ADVICE)

**Use actual booleans, not strings.**

```json
// WRONG - Strings
"visible": "true"
"enabled": "false"

// CORRECT - Booleans
"visible": true
"enabled": false
```

**Exception**: Some Extend properties (like `enabled` in widgets) actually require strings. Check the specific widget documentation.

### MultipleStringInterpolatorsRule (ADVICE)

**Use single template literal instead of multiple interpolators.**

```json
// WRONG - Multiple interpolators
"value": "My name is <% name %> and I am <% age %>"

// CORRECT - Single interpolator with template
"value": "<% `My name is {{name}} and I am {{age}}` %>"
```

### EmbeddedImagesRule (ADVICE)

**Don't embed base64 images - use external URLs.**

```json
// WRONG - Bloats file size
"url": "data:image/png;base64,iVBORw0KGgo..."

// CORRECT - External image
"url": "https://example.com/images/logo.png"
```

### ScriptOnSendSelfDataRule (ADVICE)

**In onSend, use local variables instead of self.data as temporary storage.**

```javascript
// WRONG - Using self.data as temporary storage
self.data = {:};
self.data.foo = 'bar';
return self.data;

// CORRECT - Use local variable
let postData = {:};
postData.foo = 'bar';
return postData;
```

### ScriptFunctionReturnConsistencyRule (ADVICE)

**Ensure all code paths return a value consistently.**

```javascript
// WRONG - Inconsistent returns
const processUser = function(user) {
    if (user.active) {
        return user.name;
    }
    // Missing return!
};

// CORRECT - All paths return
const processUser = function(user) {
    if (user.active) {
        return user.name;
    }
    return null;
};
```

### ScriptEmptyFunctionRule (ADVICE)

**Don't leave empty function bodies - implement or remove them.**

---

## Summary Checklist for Agents

When building Workday Extend apps, agents MUST:

### Before Creating Endpoints:
- [ ] Use lowerCamelCase for endpoint names
- [ ] Add `failOnStatusCodes` for error handling
- [ ] Use `baseUrlType` instead of hardcoded URLs
- [ ] Never use `isCollection: true`
- [ ] Never use `bestEffort: true`

### Before Creating Widgets:
- [ ] Add `id` to every widget (except footer, item, group, title, pod, cardContainer, card)
- [ ] Use lowerCamelCase for widget IDs
- [ ] Use pod for footers

### Before Creating Pages:
- [ ] Add `securityDomains` array
- [ ] Follow section ordering (id, securityDomains, include, script, endPoints, onSubmit, outboundData, onLoad, presentation)
- [ ] Use lowerCamelCase for file names

### When Writing Scripts:
- [ ] Use `let`/`const` not `var`
- [ ] Remove all `console.log` statements
- [ ] Use lowerCamelCase for variables and parameters
- [ ] Use descriptive names in array methods
- [ ] Use array methods instead of for loops
- [ ] Use `list:toMap` for lookups instead of nested searches
- [ ] Use named constants instead of magic numbers
- [ ] Keep functions under 50 lines
- [ ] Keep embedded scripts under 30 lines
- [ ] Keep nesting under 4 levels
- [ ] Keep complexity under 10
- [ ] Ensure all code paths return consistently
- [ ] Remove unused variables, functions, and parameters

### Security:
- [ ] Never hardcode WIDs - use app attributes
- [ ] Never hardcode applicationId - use `site.applicationId`
- [ ] Never hardcode `*.workday.com` URLs - use `apiGatewayEndpoint`
