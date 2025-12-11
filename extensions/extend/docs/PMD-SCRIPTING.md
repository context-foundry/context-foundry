# PMD Scripting Reference

PMD Scripting is Workday Extend's **server-side scripting language** for dynamic page behavior. Think of it as JavaScript for Workday - similar syntax but NOT JavaScript.

## Quick Comparison

| Aspect | PMD (Layout) | PMD Scripting (Logic) |
|--------|--------------|----------------------|
| Analogy | HTML | JavaScript |
| Purpose | Define widgets, structure | Business logic, events, data manipulation |
| Syntax | JSON | Java-based expression language |

---

## Syntax Fundamentals

### Script Notation

All PMD scripts use `<% %>` notation:

```javascript
// Inline expression
"value": "<% endpoint.data.name %>"

// Multi-line script
"onChange": "<%
  var result = calculate();
  self.value = result;
%>"

// Script block (page-level functions)
"script": "<%
  var myFunction = function(param) {
    return param * 2;
  };
%>"
```

### Variables

**Scope keywords:**

| Keyword | Scope | Reassignable | Best Practice |
|---------|-------|--------------|---------------|
| `const` | Block `{}` | No | Prefer this |
| `let` | Block `{}` | Yes | Second choice |
| `var` | Function | Yes | Last resort |

```javascript
const immutable = 'cannot change';
let blockScoped = 'can reassign within block';
var functionScoped = 'accessible anywhere in function';
```

**Naming rules:**
- Start with: `a-z`, `A-Z`, `_`, `$`
- Then use: `0-9`, `a-z`, `A-Z`, `_`, `$`
- Case-sensitive: `myVar` != `MyVar`

**Reserved keywords (cannot use):**
```
and, break, catch, const, continue, do, div, else, eq, false,
finally, for, function, ge, gt, if, instanceof, lt, le, let,
mod, ne, new, not, null, or, return, throw, true, try, typeof,
var, while
```

### Property Access

```javascript
// Dot notation
map.propertyName

// Bracket notation (use for reserved words, hyphens, dynamic keys)
event['for'].id        // 'for' is reserved
data['my-field']       // hyphen would be parsed as subtraction
map[variableKey]       // dynamic key lookup
```

### Operators

**Arithmetic:**
```javascript
+   // Addition
-   // Subtraction
*   // Multiplication
/   // Division
%   // Modulus
++  // Increment (a++ or ++a)
--  // Decrement (a-- or --a)
```

**Comparison:**
```javascript
==  // Equal
!=  // Not equal
<   // Less than
<=  // Less than or equal
>   // Greater than
>=  // Greater than or equal
```

**Logical (NOT and/or/not!):**
```javascript
&&  // AND
||  // OR
!   // NOT
```

**Special operators:**
```javascript
// Ternary
condition ? valueIfTrue : valueIfFalse

// Elvis (falsy fallback)
value ?: 'default'   // Returns default if value is false/null/empty

// Null-coalescing (null-only fallback)
value ?? 'default'   // Returns default ONLY if value is null

// Safe chaining (no error if null)
object?.property?.method()

// Range (inclusive)
1 to 10    // [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

// Range (exclusive)
0 until 10 // [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
```

**Side-effect operators:**
```javascript
a += 2   // a = a + 2
a -= 2   // a = a - 2
a *= 2   // a = a * 2
a /= 2   // a = a / 2
a %= 2   // a = a % 2
```

### Collections (CRITICAL - Different from JavaScript!)

| Type | Syntax | Empty | Access |
|------|--------|-------|--------|
| List | `["a", "b"]` | `[]` | `list[0]` |
| Map | `{"key": "value"}` | `{:}` | `map["key"]` or `map.key` |
| Set | `{"a", "b"}` | `{}` | iteration only |

```javascript
// List - ordered, indexed
const list = ["item1", "item2"];
list[0]  // "item1"

// Map - key:value pairs (COLON separator!)
const map = {"name": "Logan", "age": 30};
map["name"]  // "Logan"
map.name     // "Logan"

// GOTCHA: Unquoted keys reference variables!
const a = "dynamicKey";
const map1 = {a: "value"};     // Key = value of 'a' = "dynamicKey"
const map2 = {"a": "value"};   // Key = literal "a"

// Empty collections
const emptyList = [];
const emptyMap = {:};   // NOT {} - that's an empty SET!
const emptySet = {};
```

### Control Flow

```javascript
// if/else
if (condition) {
  // code
} else if (other) {
  // code
} else {
  // code
}

// for loop (traditional)
for (let i = 0; i < 10; i++) {
  list.add(i);
}

// for-each (PMD style with colon)
for (let item : items) {
  process(item);
}

// for with range
for (let i : 1 to 10) {
  list.add(i);
}

// while
while (condition) {
  // code
}

// do-while
do {
  // code
} while (condition);

// break and continue
for (let item : items) {
  if (item == null) continue;
  if (item == target) break;
}
```

### Functions

```javascript
// Define function
var calculateTotal = function(items) {
  var total = 0;
  for (let item : items) {
    total += item.price;
  }
  return total;
};

// Call function
var result = calculateTotal(myItems);

// Closures (arrow syntax)
items.filter(item => { item.active })
items.map(item => { item.name })
items.find(item => { item.id == searchId })
```

**Closure limitation:** Cannot reassign external variables inside closure:
```javascript
// WRONG - won't work
let count = 0;
items.forEach(item => { count++; });

// CORRECT - mutate existing object
const results = [];
items.forEach(item => { results.add(item); });

// CORRECT - use for loop instead
let count = 0;
for (let item : items) { count++; }
```

### String Interpolation

Use backticks with `{{variable}}`:
```javascript
var name = 'Logan';
var greeting = `Hello, {{name}}!`;  // "Hello, Logan!"

// Multiline
var message = `
  Dear {{name}},
  Welcome to the system.
`;
```

### Comments

```javascript
// Single line comment

/* Multi-line
   comment */
```

---

## Built-in Functions

### `empty(value)`
Returns true if: null, "", [], size=0, isEmpty()=true
```javascript
if (empty self.value) { ... }
empty myList  // true if list is empty
```

### `size(value)`
Returns length/size (0 for null):
```javascript
size("Hello")  // 5
size([1,2,3])  // 3
size(null)     // 0
```

---

## Widget Methods Reference

### Common Methods (Most Widgets)

| Method | Shortcut | Description |
|--------|----------|-------------|
| `getValue()` | `.value` | Get widget value |
| `setValue(val)` | `.value = val` | Set widget value |
| `isVisible()` | `.visible` | Check visibility |
| `setVisible(bool)` | `.visible = bool` | Show/hide (widget must be in fieldSet!) |
| `isEnabled()` | `.enabled` | Check enabled state |
| `setEnabled(bool)` | `.enabled = bool` | Enable/disable |
| `isRequired()` | `.required` | Check required |
| `setRequired(bool)` | `.required = bool` | Set required |
| `getLabel()` | `.label` | Get label |
| `setLabel(str)` | `.label = str` | Set label |
| `setError(msg)` | - | Show validation error (blocks submit) |
| `clearError()` | - | Clear error |
| `setWarning(msg)` | - | Show warning (doesn't block submit) |
| `clearWarning()` | - | Clear warning |
| `isUpdated()` | - | User manually changed value |
| `isUpdatedByScript()` | - | Script changed value |

### Container Methods (section, fieldSet, dynamicSection)

```javascript
container.childId              // Direct child access
container['childId']           // Bracket notation
container.get('childId')       // Method call
container.getChildren()        // List of all children
container.getChildrenMap()     // Map keyed by id
container.anyUpdated()         // Any child changed?

// fieldSet specific
fieldSet.getTitle() / .title
fieldSet.setTitle(str)

// dynamicSection specific
dynamicSection.setData(newData)  // Refresh data binding
```

### Grid Methods

```javascript
// Grid container
grid.getRows() / .rows           // All rows
grid.getSelectedRows()           // Selected rows only
grid.setRows(listData)           // Replace all data
grid.addRow(index)               // Insert at index
grid.removeRow(index)            // Remove at index
grid.getSubtotal('columnId')     // Column subtotal
grid.setDoNotAdd(bool)           // Prevent adding
grid.setDoNotRemove(bool)        // Prevent removing

// Grid row
row.columnId.value               // Direct cell access (preferred)
row.get('columnId').value        // Method access
row.childrenMap.columnId.value   // Map access
row.isSelected()                 // Is row selected?
row.anyUpdated()                 // Any cell changed?
```

### Instance List Methods (dropdown, radioGroup, checkBoxList, instanceList)

```javascript
list.getValue()                  // List of selected IDs: ["123", "456"]
list.setValue(['id1', 'id2'])    // Set selected by IDs
list.getSelectedEntries()        // [{id, descriptor}, ...]
list.setValues(dataSource)       // Set ALL possible values
list.promptSelections[0]         // Multilevel list selections
```

### Endpoint Methods

```javascript
// Deferred endpoint invocation
var result = endpoint.invoke();              // No params
var result = endpoint.invoke({'id': '123'}); // With params
result.data.fieldName                        // Access response
```

### Specialized Methods

**Currency:**
```javascript
currency.getCurrencyCode()
currency.setCurrencyCode('USD')
```

**Date:**
```javascript
dateWidget.setValue(null)  // Use null, NOT empty string!
```

**Image:**
```javascript
image.getImageUri() / setImageUri(str)
image.setEndPointUrl(str)
```

**Edit Button:**
```javascript
// Only accessible during page submission!
editButton.getValue()
editButton.setValue(bool)
```

---

## PMD Functions by Namespace

### `date:` - Date/Time

```javascript
// Current date/time
date:now()
date:now(timeZone)
date:getTodaysDate(timeZone)
date:getTodaysDateFormatted(timeZone, 'yyyy-MM-dd')
date:getDateTimeZone(timeZone)

// Parsing
date:parse(dateString)
date:parse(dateString, format)
date:parseDateString(dateString)

// Formatting
myDate.format('yyyy-MM-dd')
myDate.formatWithTimeZone(format, timeZone)

// Arithmetic (chainable)
myDate.plusDays(5).plusMonths(1)
myDate.minusYears(1).minusWeeks(2)

// Components
myDate.withYear(2025).withMonth(6).withDayOfMonth(15)
myDate.year()
myDate.month()
```

### `list:` - List Operations

```javascript
// Creation
list:toList('a', 'b', 'c')
list:emptyList()

// Access
myList.first()
myList.last()
myList.get(index)
myList.size()
myList.isEmpty()

// Search
myList.contains(element)
myList.indexOf(element)
myList.find(item => { item.id == searchId })

// Transform (functional)
myList.map(item => { item.name })
myList.filter(item => { item.active })
myList.reduce(closure)
myList.forEach(item => { process(item) })

// Shortcuts (very useful!)
list:mapAttribute(items, 'name')         // Extract attribute from all
list:filter(list, 'status', 'active')    // Filter by key/value
list:filterMultiple(list, 'id', idList)  // Filter by list of values
list:exclude(list, 'type', 'deleted')    // Exclude by key/value

// Modification
myList.add(element)
myList.addAll(otherList)
myList.remove(element)
myList.clear()

// Utility
myList.distinct()
myList.reverse()
myList.sort()
myList.sort(list, 'name', true)  // Sort by key, ascending
myList.join(', ')
list:join(list1, list2)          // Merge lists
list:flatten(nestedList)

// Conversion
list:toMap(items, 'id')          // List to Map keyed by 'id'
myList.toJson()
```

### `map:` - Map Operations

```javascript
myMap.get(key)
myMap.keys()
myMap.values()
myMap.containsKey(key)
myMap.put(key, value)
myMap.remove(key)
myMap.filter(closure)
myMap.forEach(closure)
```

### `string:` - String Operations

```javascript
// Case
myStr.upperCase()
myStr.lowerCase()
myStr.capitalize()

// Trim/Pad
myStr.trim()
myStr.leftPad(10, '0')
myStr.rightPad(10)

// Search
myStr.contains(search)
myStr.startsWith(prefix)
myStr.endsWith(suffix)
myStr.indexOf(search)

// Extract
myStr.substring(start, end)
myStr.substringBefore('-')
myStr.substringAfter('-')

// Modify
myStr.replace(search, replacement)
myStr.remove(substring)

// Check
myStr.isBlank()
myStr.isNumber()
myStr.length()

// Default
myStr.defaultIfBlank('fallback')
myStr.defaultIfEmpty('fallback')

// Split/Join
myStr.split(',')
string:join(str1, str2, str3)

// Encoding
myStr.urlEncode()
myStr.urlDecode()

// Convert
myStr.toInt()
myStr.toDecimal()

// Utility
string:uuid()
```

### `json:` - JSON Operations

```javascript
json:parse(jsonString)           // String to Object
json:stringify(object)           // Object to String
json:query(source, jsonPath)     // JSONPath query
```

### `number:` - Math

```javascript
number:max(1, 5, 3)              // 5
number:min(1, 5, 3)              // 1
number:pow(2, 3)                 // 8
number:sqrt(16)                  // 4
number:convertStringToInt('42')
number:toBigDecimal(expr, scale, roundingMode)
```

### `regex:` - Regular Expressions

```javascript
regex:match(text, pattern)
regex:find(text, pattern)
regex:replace(text, pattern, replacement)
regex:split(text, pattern)
```

### `object:` - Object Utilities

```javascript
object:defaultIfNull(obj, 'default')
object:firstNonNull(obj1, obj2, obj3)
```

### `validate:` - Validation

```javascript
validate:match(regex, string)
```

### `bool:` - Boolean Logic

```javascript
bool:all(expr1, expr2, ...)  // All must be true
bool:any(expr1, expr2, ...)  // Any true
```

### `converter:` - Type Conversion

```javascript
converter:booleanAsInt(true)     // 1
converter:booleanAsString(true)  // "true"
```

---

## Event Handling

### Event Matrix by Widget

| Widget | onChange | onClick | onRowAdd/Remove/Select | onPanelAdd/Remove | onSearch |
|--------|:--------:|:-------:|:----------------------:|:-----------------:|:--------:|
| text, number, date, etc. | Y | | | | |
| pageActionButton | Y | Y | | | |
| grid row | Y | Y | Y | | |
| panelList panel | Y | Y | | Y | |
| instanceList | Y | Y | | | Y |

### Page Lifecycle

**1. Page Load:**
```
Invoke inbound endpoints (concurrent)
    -> onSend (per endpoint)
    -> onLoad
    -> Widgets render
```

**2. User Interaction:**
```
User changes widget
    -> onChange/onClick fires
    -> Script can access ALL widgets
    -> (Optional) invoke deferred endpoint -> onSend
```

**3. Page Submit:**
```
User clicks OK
    -> onSubmit
    -> Outbound endpoints submit
    -> onSend/onMultiPartSend
```

### Widget Access Rules

| Event | Can Access Widgets? |
|-------|---------------------|
| `onLoad` (page load) | NO - fires before widget render |
| `onSend` (page load) | NO - fires before widget render |
| `onChange`, `onClick` | YES - all widgets |
| `onRowSelect`, `onRowAdd` | YES - use `row.childrenMap.columnId` |
| `onSubmit` | YES - but changes won't display |
| `onSend` (user action) | YES - when invoked from event handler |

### The `self` Variable

Always use `self` inside event handlers to reference the triggering widget:

```json
{
  "type": "text",
  "id": "firstName",
  "onChange": "<%
    // self.value is cleaner than firstName.value
    fullName.value = self.value + ' ' + lastName.value;
  %>"
}
```

---

## Common Patterns

### 1. Dependent Widget Update

```json
{
  "script": "<%
    var updateDependents = function(sourceValue) {
      if (sourceValue == 'optionA') {
        dependentField.value = 'Value for A';
        dependentField.visible = true;
      } else {
        dependentField.visible = false;
      }
    };
  %>",
  "presentation": {
    "body": {
      "children": [
        {
          "type": "dropdown",
          "id": "selector",
          "onChange": "<% updateDependents(self.value[0]); %>"
        },
        {
          "type": "text",
          "id": "dependentField",
          "visible": false
        }
      ]
    }
  }
}
```

### 2. Grid Selection with Summary

```json
{
  "script": "<%
    var calculateSummary = function(grid) {
      var total = 0;
      var names = [];
      for (var row : grid.selectedRows) {
        total += row.childrenMap.amount.value;
        names.add(row.childrenMap.name.value);
      }
      summaryTotal.value = total;
      summaryNames.value = names.join(', ');
    };
  %>",
  "presentation": {
    "body": {
      "children": [
        {
          "type": "grid",
          "id": "itemsGrid",
          "selectionEnabled": true,
          "onRowSelect": "<% calculateSummary(self); %>"
        }
      ]
    }
  }
}
```

### 3. Field Validation

```json
{
  "type": "text",
  "id": "email",
  "onChange": "<%
    self.clearError();
    if (!empty self.value && !self.value.contains('@')) {
      self.setError('Please enter a valid email address');
    }
  %>"
}
```

### 4. Deferred Endpoint with Validation

```json
{
  "type": "text",
  "id": "lookupField",
  "onChange": "<%
    if (!empty self.value) {
      var result = lookupEndpoint.invoke({'query': self.value});
      if (empty result.data) {
        self.setError('No results found');
      } else {
        resultField.value = result.data[0].name;
        self.clearError();
      }
    }
  %>"
}
```

### 5. Flow Variable Creation

```json
{
  "type": "outboundVariable",
  "name": "selectedData",
  "variableScope": "flow",
  "onSend": "<%
    {
      'selectedId': myDropdown.value[0],
      'selectedItems': myGrid.selectedRows.map(row => {
        row.childrenMap.id.value
      })
    }
  %>"
}
```

### 6. Console Debugging

```javascript
console.debug('Debug: ', variable);
console.info('Info: ', data);
console.warn('Warning: ', message);
console.error('Error: ', error);

// View in: Analytics -> Logs -> Filter: wd_category is console
```

---

## Limits

| Limit | Maximum |
|-------|---------|
| Call frames (recursion) | 25 |
| CPU time per script | 5 seconds |
| Nested script modules | 2 levels |
| PMD file size | 100 KB |

---

## Quick Reference Card

```javascript
// Variables
const x = 1;        // Block scope, immutable
let y = 2;          // Block scope, mutable
var z = 3;          // Function scope

// Collections (DIFFERENT from JS!)
[]                  // Empty list
{:}                 // Empty map (NOT {})
{}                  // Empty set

// Null handling
value ?? 'default'  // Null-coalescing
obj?.prop           // Safe chaining
empty value         // Check null/empty
value ?: 'default'  // Falsy fallback

// Loops
for (let i : list) { }      // For-each
for (let i : 1 to 10) { }   // Range inclusive
for (let i : 0 until 10) { } // Range exclusive

// Logical (NOT and/or/not!)
cond1 && cond2
cond1 || cond2
!condition

// Common widget methods
widget.value = x;
widget.visible = true;
widget.setError('msg');
widget.clearError();
endpoint.invoke({'param': val});

// Common functions
empty(value)
list:mapAttribute(list, 'key')
list:filter(list, 'key', 'value')
myDate.format('yyyy-MM-dd')
myStr.defaultIfBlank('fallback')
```
