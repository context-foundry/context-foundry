# PMD Functions Reference

> Official Workday PMD function documentation for Extend apps.
> Source: Workday Documentation > Extend Apps > Extend App Components Reference > Pages > PMD Functions

## Quick Reference

| Namespace | Key Functions | Use Case |
|-----------|---------------|----------|
| `bool:` | `all`, `any` | Boolean logic |
| `bpfTaskHelper:` | `fetchTaskType` | Business process tasks |
| `converter:` | `booleanAsInt`, `booleanAsString` | Type conversion |
| `date:` | `add`, `between`, `after`, `format`, `now`, `parse*`, `year`, `month`, `extractValue` | Date manipulation |
| `list:` | `toList`, `toMap`, `filter`, `find`, `map`, `mapAttribute`, `flatten` | Collections |
| `json:` | `parse`, `stringify`, `asJSON`, `query`, `create` | JSON handling |
| `map:` | `get`, `put`, `keys`, `values`, `filter`, `forEach` | Map operations |
| `object:` | `defaultIfNull`, `firstNonNull` | Null handling |
| `string:` | `contains`, `replace`, `format*`, `trim`, `substringBefore` | Text manipulation |
| `regex:` | `find`, `match`, `replace` | Pattern matching |
| `number:` | `max`, `min`, `convertStringToInt` | Math operations |
| `console:` | `debug`, `error`, `info`, `warn` | Logging/debugging |

---

## Calling Conventions

Many functions support **two syntaxes**:

```javascript
// Instance method (on object)
myDate.add('DAY', 5)
myList.filter(x => {x.active})

// Namespace function
date:add(myDate, 'DAY', 5)
list:filter(myList, x => {x.active})
```

---

## bool Functions

### `bool:all(expression1, expressionN)`

Returns `true` if ALL subexpressions return true.

```javascript
bool:all(true, false)   // false
bool:all(true, true)    // true
bool:all(x > 0, y > 0)  // true if both positive
```

**Returns:** boolean

### `bool:any(expression1, expressionN)`

Returns `true` if ANY subexpression returns true.

```javascript
bool:any(true, false)   // true
bool:any(false, false)  // false
```

**Returns:** boolean

---

## bpfTaskHelper Functions

### `bpfTaskHelper:fetchTaskType(businessProcessTask)`

Returns the task type for a business process task name.

```javascript
bpfTaskHelper:fetchTaskType('Complete Questionnaire')  // 'questionnaire'
```

**Returns:** String

---

## converter Functions

### `converter:booleanAsInt(expression)`

Converts boolean to integer (1 or 0).

```javascript
converter:booleanAsInt(true)   // 1
converter:booleanAsInt(false)  // 0
```

**Returns:** int

### `converter:booleanAsString(expression)`

Converts boolean to string ('1' or '0').

```javascript
converter:booleanAsString(true)   // '1'
converter:booleanAsString(false)  // '0'
```

**Returns:** String

---

## date Functions

### `date:add(date, precision, duration)` / `thisDate.add(precision, duration)`

Adds duration to a date. Returns original date if duration is null.

```javascript
// Instance method
aDateWidget.value.add('HOUR', 1)

// Namespace function
date:add(dateId.value, 'HOUR', 1)

// Chain with format
aDateWidget.value.add('HOUR', 1).format('MM/dd/yyyy hh:mm:ss')

// Parse then add
date:add(date:parseDateString('2016-10-31'), 'DAY', 10)  // 2016-11-10
```

**Precision values (case-sensitive):**
- `YEAR`, `MONTH`, `DAY`
- `HOUR`, `MINUTE`, `SECOND`, `MILLISECOND`

**Returns:** Date

### `date:between(date1, date2, precision)` / `thisDate1.between(date2, precision)`

Returns the number of precision units between two dates.

```javascript
// Days between March 1 and March 30
dateWidget1.value.between(dateWidget2.value, 'DAY')  // 29

// Namespace syntax
date:between(date1, date2, 'DAY')
```

**Returns:** int

### `date:after(date1, date2)` / `thisDate1.after(date2)`

Returns true if first date is after second date.

```javascript
// Is March 1 after March 30?
dateWidget1.value.after(dateWidget2.value)  // false

// Namespace syntax
date:after(dateObjectWithYear2016, dateObjectWithYear2000)  // true
```

**Returns:** Boolean

### `date:now()`

Returns current date/time as Date object (system timezone).

```javascript
date:now()  // Current Date object

// Compare with another date
myDate.after(date:now())  // Is myDate in the future?

// Format current time
date:now().format('yyyy-MM-dd HH:mm:ss')

// Calculate deadline (7 days from now)
date:now().add('DAY', 7).format('yyyy-MM-dd')
```

**Returns:** Date

### `date:parse(dateString)`

Parse ISO date string (yyyy-MM-dd) to Date object.

```javascript
date:parse('2021-07-04')  // Date object

// Chain operations
date:parse('2021-07-04').add('MONTH', 1).format('yyyy-MM-dd')
// '2021-08-04'
```

> **Note:** Equivalent to `date:parseDateString(dateString)`. For custom formats, use `date:parse(dateString, dateFormat)`.

**Returns:** Date

### `date:format(date, dateFormat)` / `thisDate.format(dateFormat)`

Format a Date object to string.

```javascript
// Instance method
dateWidget.value.format('MM/dd/yyyy HH:mm:ss')  // '03/01/2022 15:30:00'
dateWidget.value.format('yyyy-MM-dd')           // '2022-03-01'

// Day name/number
dateWidget.value.format('E')   // 'Fri'
dateWidget.value.format('u')   // '5' (Friday = 5)

// Chained after operations
myDate.add('DAY', 7).format('yyyy-MM-dd')
```

**Common format patterns:**

| Pattern | Output | Example |
|---------|--------|---------|
| `yyyy-MM-dd` | ISO date | `2022-03-01` |
| `MM/dd/yyyy` | US format | `03/01/2022` |
| `dd/MM/yyyy` | EU format | `01/03/2022` |
| `HH:mm:ss` | 24-hour time | `15:30:00` |
| `hh:mm:ss a` | 12-hour time | `03:30:00 PM` |
| `E` | Day name | `Fri` |
| `MMMM` | Month name | `March` |

**Returns:** String

### `date:getDateTimeZone(timeZone)`

Convert timezone string to DateTimeZone object.

```javascript
date:getDateTimeZone('America/Los_Angeles')  // UTC-8
date:getDateTimeZone('Europe/London')        // UTC+0
date:getDateTimeZone(null)                   // UTC

// Most common: use with userTimeZone system variable
date:getDateTimeZone(userTimeZone)
```

**Returns:** DateTimeZone

### `date:getTodaysDate(timeZone)`

Get today's date/time as string in user's default format.

```javascript
date:getTodaysDate(date:getDateTimeZone(userTimeZone))
// '02/01/2022 5:52:12 PM' (format varies by user locale)

// System timezone
date:getTodaysDate(null)
```

**Returns:** String

### `date:getTodaysDateFormatted(timeZone, dateTimeFormat)`

Get today's date/time as string in custom format.

```javascript
date:getTodaysDateFormatted(date:getDateTimeZone(userTimeZone), 'yyyy-MM-dd')
// '2022-02-01'

date:getTodaysDateFormatted(date:getDateTimeZone('Asia/Shanghai'), 'dd/MM/yyyy hh:mm:ss')
// '31/10/2016 20:05:38'
```

**Returns:** String

**Common date pattern:**
```javascript
// Get user's current date in ISO format
date:getTodaysDateFormatted(date:getDateTimeZone(userTimeZone), 'yyyy-MM-dd')
```

### `date:year(date)`

Extracts the year from a date.

```javascript
date:year(myDate)  // 2024
```

**Returns:** int

### `date:month(date)`

Extracts the month from a date (1-12).

```javascript
date:month(myDate)  // 3 (March)
```

**Returns:** int

### `date:extractValue(precision, date)`

Extracts a specific component from a date.

```javascript
date:extractValue('DAY', myDate)    // 15
date:extractValue('MONTH', myDate)  // 3
date:extractValue('YEAR', myDate)   // 2024
```

**Precision values:** `YEAR`, `MONTH`, `DAY`, `HOUR`, `MINUTE`, `SECOND`

**Returns:** int

### `date:parseDateString(dateString)`

Parse ISO date string to Date object. Alias of `date:parse()`.

```javascript
date:parseDateString('2024-03-15')  // Date object

// Chain with operations
date:parseDateString(holiday.date).format('MM/dd/yyyy')
```

**Returns:** Date

---

## console Functions (Logging)

Console methods for debugging PMD scripts. Logs appear in **Analytics > Logs** section of the Workday Developer Site. Filter with `wd_category is console`.

### `console.debug(message, ...args)`

Log debug-level message.

```javascript
console.debug('Debug value: ', myVariable);
```

### `console.error(message, ...args)`

Log error-level message.

```javascript
console.error('Invalid value: ', self.value);
```

### `console.info(message, ...args)`

Log info-level message.

```javascript
console.info('Processing complete: ', result);
```

### `console.warn(message, ...args)`

Log warning-level message.

```javascript
console.warn('Deprecated: ', oldMethod);
```

**Viewing Logs:**
1. Go to Workday Developer Site
2. Navigate to **Analytics > Logs**
3. Add filter: `wd_category is console`

---

## list Functions

### `list:toList(value1, valueN)`

Creates a list from values. **Automatically excludes nulls.**

```javascript
list:toList('1', '2', null)  // ['1', '2']

// Common: build dynamic list
list:toList(value1, conditionalValue, value3)
```

**Returns:** List

### `list:toListIncludeNull(value1, valueN)`

Creates a list from values. **Keeps null values.**

```javascript
list:toListIncludeNull('1', '2', null)  // ['1', '2', null]
```

Use when null positions are meaningful.

**Returns:** List

### `list:toMap(list, key)`

Converts a list to a map, keyed by specified attribute. **Critical for O(1) lookups.**

```javascript
// Input
[
  {"id":"1", "name":"Anne"},
  {"id":"2", "name":"Joe"}
]

// Convert to map keyed by 'id'
list:toMap(theList, 'id')

// Result - entire object is the value
{
  "1": {"id":"1", "name":"Anne"},
  "2": {"id":"2", "name":"Joe"}
}

// Fast lookups!
myMap.get('1').name  // 'Anne'
```

**Returns:** Map

### `list:filter` - 6 Variants

#### `thisList.filter(closure)` / `list:filter(list, closure)`

Filter with custom closure function.

```javascript
[1, 2, 3, 4, 5].filter(x => {x % 2 != 0})  // [1, 3, 5]
```

#### `thisList.filter(closure(item, index))`

Filter with access to index.

```javascript
["a", "b", "c"].filter((item, index) => index % 2 == 0)  // ["a", "c"]
```

#### `list:filter(list, key, value)`

Simple key/value match. **Most common!**

```javascript
list:filter(employees, 'department', 'Engineering')
list:filter(theList, 'key', 'value0')  // [{"key": "value0"}]
```

#### `list:filterMultiple(list, key, comparisonList)`

Match any value in comparison list.

```javascript
list:filterMultiple(items, 'status', ['pending', 'review'])
```

#### `list:filterEmptyAttribute(list, key)`

Find items WITHOUT a specific attribute.

```javascript
list:filterEmptyAttribute(theList, 'email')  // Items missing 'email'
```

#### `list:filterRegex(list, regexValue)`

Filter string list by regex.

```javascript
list:filterRegex(['my','123','regex','list'], '[a-z]+')  // ['my', 'regex', 'list']
```

**Returns:** List

> **Performance Tip:** Use `find()` instead of `filter()` when you only need the first match!

> **Closure Limitation:** Cannot reassign variables declared outside the closure.

### `list:find(closure)` / `thisList.find(closure)`

Returns the **first** element matching the closure. More efficient than `filter()` for single matches.

```javascript
// First even number
[1, 4, 8].find(x => {x % 2 == 0})  // 4

// Find in complex data
data.groups.find(group => {group.descriptor == 'Compensation Administrator'})

// Common null-safe pattern
!empty list.find(x => {x.id == targetId}) ?? ''
```

**Returns:** Object (can be null - always null-check!)

### `list:mapAttribute(list, key)`

Extracts a single attribute from each object in a list. **Simpler than map() for single properties.**

```javascript
// Input
[{"key": "value0"}, {"key": "value1"}]

// Extract 'key' values
list:mapAttribute(theList, 'key')  // ['value0', 'value1']

// Common uses
list:mapAttribute(selectedWorkers, 'id')  // ['id1', 'id2', 'id3']
list:mapAttribute(errors, 'error')        // ['Error 1', 'Error 2']
```

**Comparison:**
| Function | Use Case |
|----------|----------|
| `list:mapAttribute(list, 'name')` | Extract one attribute (simple) |
| `list.map(x => {x.name})` | Same, but closure syntax |
| `list.map(x => {{id: x.id, label: x.name}})` | Transform to new shape |

**Returns:** List

### `list:join(list1, list2)`

Combines two lists. **Not string concatenation!**

```javascript
list:join(list:toList('a', 'b'), list:toList('c', 'd'))
// ['a', 'b', 'c', 'd']

// Combine endpoint results
list:join(countries1.items, countries2.items)
```

> **Important:** Different from `myList.join(', ')` which converts list to string!

| Syntax | Purpose | Returns |
|--------|---------|---------|
| `list:join(list1, list2)` | Combine lists | List |
| `myList.join(', ')` | List → String | String |

**Returns:** List

### `list:isEmpty()` / `thisList.isEmpty()`

Returns true if the list is empty.

```javascript
// Instance method
myList.isEmpty()  // true/false

// Namespace function
list:isEmpty(myList)

// Common patterns
<% items.isEmpty() ? 'No results' : items.size() + ' found' %>
```

> **Prefer `empty` operator for null-safety:**
> ```javascript
> <% empty myList %>        // true if null OR empty (safe)
> <% myList.isEmpty() %>    // ERROR if myList is null
> ```

**Returns:** boolean

### `list:flatten(list)` / `thisList.flatten()`

Flattens nested arrays into a single-level array.

```javascript
// Flatten nested structure
var nestedList = [[1, 2], [3, 4], [5]];
list:flatten(nestedList)  // [1, 2, 3, 4, 5]

// Common pattern: flatten nested API response
var list = report.entries.map(x => {
  x.nestedItems.map(y => {
    y.add('parentId', x.id);
    return y;
  });
});
list = list:flatten(list);
```

**Returns:** List

### `thisList.distinct()`

Returns a new list with duplicate values removed.

```javascript
workers.data.map(worker => { worker.businessTitle }).distinct()
// Unique business titles only

[1, 2, 2, 3, 3, 3].distinct()  // [1, 2, 3]
```

**Returns:** List

### `thisList.sort(closure)`

Sorts list by the value returned from closure.

```javascript
// Sort by businessTitle
workers.data.sort(worker => { worker.businessTitle })

// Sort by date
expenses.data.sort(item => { item.date })
```

**Returns:** List

### `thisList.add(value)` / `thisMap.add(key, value)`

Adds a value to a list, or adds a key-value pair to a map/object.

```javascript
// Add to list
var items = [];
items.add({'name': 'John'});
items.add({'name': 'Jane'});

// Add to object/map (dynamic property)
var obj = {:};
obj.add('Location_Name', x.Location_Name);
obj.add('Employee_ID', x.employeeId);
```

**Returns:** List or Map (mutates original)

### `thisList.contains(value)`

Check if list contains a specific value.

```javascript
var holidays = [date1, date2, date3];
holidays.contains(checkDate)  // true/false

['pending', 'active'].contains(status)  // true/false
```

**Returns:** boolean

### `list:createMapList(list, key)`

Transforms simple values into objects with the same key.

```javascript
// Input: simple array
['my', 'list']

// Transform
list:createMapList(theList, 'key')

// Output: list of objects
[{'key': 'my'}, {'key': 'list'}]

// Prepare values for dropdown
list:createMapList(['USA', 'UK', 'CA'], 'id')
// [{'id': 'USA'}, {'id': 'UK'}, {'id': 'CA'}]
```

**Returns:** List

### `list:createMapListWithKeys(list, keyList)`

Transforms values into objects with different keys (1:1 mapping).

```javascript
// Input
values: ['my', 'list']
keys: ['key1', 'key2']

// Transform
list:createMapListWithKeys(theList, theKeyList)

// Output
[{'key1': 'my'}, {'key2': 'list'}]
```

⚠️ **Lists must be same size** - returns empty map if different lengths!

**Returns:** List

---

## json Functions

### `json:parse(jsonString)`

Converts a JSON string to the corresponding data object.

```javascript
json:parse('[1, 2]')  // [1, 2] (actual array)

json:parse('{"name": "John"}')  // {name: "John"} (actual object)

// Common: parse API response body
json:parse(response.body)
```

**Returns:** Object

### `json:stringify(object)` / `json:asJSON(object)`

Converts an object to a JSON string.

```javascript
json:stringify([{'a':1}, {'b':2}])
// "[{'a':1},{'b':2}]"

json:asJSON(myList.toString())
// Converts list to JSON string

// Debugging
console.log(json:stringify(myData))
```

> **Tip:** For Map/List/Set, use `.toJson()` instance method instead:
> ```javascript
> myVariable.toJson()  // More concise!
> ```

**Returns:** String

### `json:create(attribute1, attributeN)` + `json:attribute(key, value)`

Builds JSON objects programmatically using attribute pairs.

```javascript
json:create(
  json:attribute('key0', 'value0'),
  json:attribute('key1', 'value1')
)
// {"key0": "value0", "key1": "value1"}
```

⚠️ **Workday recommends using `{}` syntax instead:**
```javascript
// Preferred in PMD Scripting
{'key0': 'value0', 'key1': 'value1'}

// Instead of
json:create(json:attribute('key0', 'value0'), ...)
```

**Use `json:create` when:** Building objects dynamically with conditional attributes.

**Returns:** Object

### `json:query(source, jsonPath)`

Evaluates JSONPath expression against JSON data. **Extremely powerful!**

```javascript
// Sample data
{
  "data": [
    {"name": "HR", "inactive": false, "Organization_Reference_ID": "SUP_HR"},
    {"name": "Finance", "inactive": true},
    {"name": "IT", "inactive": false, "Organization_Reference_ID": "SUP_IT"}
  ]
}
```

| JSONPath | Result |
|----------|--------|
| `$.data[*].name` | `["HR", "Finance", "IT"]` |
| `$.data[0].name` | `["HR"]` |
| `$.data[:2].name` | `["HR", "Finance"]` (first 2) |
| `$.data[3,4].name` | Specific indices |
| `$.data[?(@.inactive==true)].name` | `["Finance"]` (filter) |
| `$.data[?(@.Organization_Reference_ID)].name` | `["HR", "IT"]` (has field) |

**Key JSONPath Syntax:**
- `[*]` - all items
- `[0]` - first item
- `[:2]` - slice (first 2)
- `[3,4]` - specific indices
- `[?(@.field==value)]` - filter by condition
- `[?(@.field)]` - filter by field existence

**Returns:** List (always a list, even for single values!)

---

## map Functions

### Empty Map Literal: `{:}`

Creates an empty map/object. **Important:** Use `{:}` not `{}` for empty maps in PMD.

```javascript
var params = {:};  // Empty map

// Add properties dynamically
params.expenseStatus = 'pending';
params.fromDate = date:format(startDate, 'yyyy-MM-dd');

// Or use .add()
params.add('key', 'value');
```

### `map:get(key)` / `thisMap.get(key)`

Get value by key. Returns null if key doesn't exist.

```javascript
{'foo': 1, 'bar': 2}.get('foo')  // 1

// Bracket syntax shortcut (for string keys)
{'foo': 1, 'bar': 2}['foo']  // 1

// With null handling
myMap.get('id') ?? 'default'
object:defaultIfNull(myMap.get('name'), 'Unknown')
```

**Returns:** Object (or null)

### `map:put(key, value)` / `thisMap.put(key, value)`

Add or update a key-value pair.

```javascript
{'foo': 1, 'bar': 2}.put('key', 'value')
// {'bar':2, 'foo':1, 'key': 'value'}

// Update existing key
myMap.put('foo', 99)
```

**Returns:** Map

### `map:keys()` / `thisMap.keys()`

Get all keys as a Set.

```javascript
{'foo': 1, 'bar': 2}.keys()
// {'bar', 'foo'}  (Set, not List!)

// Iterate over keys
myMap.keys().forEach(k => { ... })
```

**Returns:** Set (order depends on implementation)

### `map:values()` / `thisMap.values()`

Get all values as a List.

```javascript
{'foo': 1, 'bar': 2, 'baz': 3}.values()
// [2, 1, 3]  (List, order may vary)

// Filter/reduce values
myMap.values().filter(v => {v > 0})
myMap.values().reduce((a, b) => {a + b})
```

**Returns:** List

### `map:containsKey(key)` / `thisMap.containsKey(key)`

Check if key exists. ⚠️ Takes linear time.

```javascript
{'bar':2, 'foo':1}.containsKey('bar')  // true
{'bar':2, 'foo':1}.containsKey('baz')  // false

// Safe access pattern
<% myMap.containsKey('id') ? myMap.get('id') : 'default' %>
```

**Returns:** boolean

### `map:mapValue(closure)` / `thisMap.mapValue(closure)`

Transform all values, keeping keys the same.

```javascript
{'a':1, 'b':2}.mapValue(v => {v * 5})
// {'a':5, 'b':10}

// Add 10% to all prices
prices.mapValue(p => {p * 1.1})
```

**Returns:** Map

### `thisMap.forEach((key, value) => {...})`

Iterate over all key-value pairs in a map.

```javascript
// Build query string from map
var params = {:};
params.status = 'pending';
params.type = 'expense';

var pairs = [];
params.forEach((key, value) => {
  pairs.add(key + '=' + value);
});
var queryString = pairs.join('&');
// "status=pending&type=expense"
```

**Returns:** void (iteration only)

---

## object Functions

### `object:defaultIfNull(object, default)`

Returns object unless null, then returns default. **Critical for null handling.**

```javascript
object:defaultIfNull(countrySelected.value[0], 'USA')
object:defaultIfNull(response.message, '')
object:defaultIfNull(items, [])
```

**Returns:** Object

### `object:firstNonNull(object1, objectN)`

Returns first non-null value from the list.

```javascript
// Try queryParams first, fall back to flowVariables
object:firstNonNull(queryParams.workerId, flowVariables.workerId)

// Multiple fallbacks
object:firstNonNull(cache.value, api.result, 'default')
```

**Returns:** Object (null if all inputs are null)

---

## regex Functions

### `regex:find(text, regex)`

Returns all substrings matching the regex.

```javascript
regex:find('ABC123DEF', '[a-zA-Z]+')  // ['ABC', 'DEF']
```

**Returns:** List

---

## string Functions

### `string:formatMessage(messageWithParameters, orderedParameters)`

Replaces placeholders with values. **Great for dynamic messages.**

```javascript
// Basic usage - {0} placeholder
string:formatMessage('My {0} string', 'formatted')
// 'My formatted string'

// Multiple parameters
string:formatMessage('Hello {0}, you have {1} messages', 'John', '5')
// 'Hello John, you have 5 messages'

// Common uses
string:formatMessage('Selected {0} of {1} items', selectedCount, totalCount)
string:formatMessage('Field {0} is required', fieldLabel)
```

**Placeholder syntax:** `{0}`, `{1}`, `{2}` ... (zero-based index)

**Returns:** String

### `string:contains(string, searchString)` / `thisString.contains(searchString)`

Case-sensitive substring check.

```javascript
// Instance method
'The quick brown fox'.contains('Ox')   // false (case-sensitive!)
'The quick brown fox'.contains('ox')   // true

// Namespace function
string:contains('Hello World', 'World')  // true

// Common use
<% description.contains('urgent') ? 'HIGH' : 'NORMAL' %>
```

⚠️ **Case-sensitive!** Use `containsIgnoreCase` for case-insensitive.

**Returns:** boolean

### `string:replace` - 4 Variants

#### `thisString.replace(searchString, replacement)`

Replaces **ALL** occurrences (case-sensitive).

```javascript
'The quick brown fox'.replace('quick', 'small')
// 'The small brown fox'

'hello world'.replace('o', '0')
// 'hell0 w0rld'  (all occurrences!)
```

#### `thisString.replaceIgnoreCase(searchString, replacement)`

Replaces **ALL** occurrences (case-insensitive).

```javascript
'The quick Quick brown fox'.replaceIgnoreCase('Quick', 'Small')
// 'The Small Small brown fox'
```

#### `thisString.replaceOnce(searchString, replacement)`

Replaces **FIRST** occurrence only (case-sensitive).

```javascript
'The quick quick brown fox'.replaceOnce('quick', 'Small')
// 'The Small quick brown fox'
```

#### `thisString.replaceOnceIgnoreCase(searchString, replacement)`

Replaces **FIRST** occurrence only (case-insensitive).

```javascript
'The quick Quick brown fox'.replaceOnceIgnoreCase('Quick', 'Small')
// 'The Small Quick brown fox'
```

**Summary:**

| Function | Replaces | Case |
|----------|----------|------|
| `replace` | ALL | Sensitive |
| `replaceIgnoreCase` | ALL | Insensitive |
| `replaceOnce` | FIRST | Sensitive |
| `replaceOnceIgnoreCase` | FIRST | Insensitive |

**Returns:** String

### `thisString.substringBefore(delimiter)`

Returns the substring before the first occurrence of a delimiter.

```javascript
'Sun Jan 01 2024'.substringBefore(' ')  // 'Sun'
'hello@example.com'.substringBefore('@')  // 'hello'
'path/to/file.txt'.substringBefore('/')  // 'path'
```

**Returns:** String

### `thisString.join(delimiter)` (on List)

Converts a list to a delimited string.

```javascript
// List to comma-separated string
workers.data.map(worker => { worker.descriptor }).join(', ')
// "John Doe, Jane Smith, Bob Wilson"

['a', 'b', 'c'].join('-')  // "a-b-c"
```

> **Note:** Different from `list:join(list1, list2)` which combines two lists!

**Returns:** String

---

## set Functions

### `set:isEmpty()` / `thisSet.isEmpty()`

Returns true if the set is empty.

```javascript
mySet.isEmpty()      // true/false
set:isEmpty(mySet)   // namespace syntax
```

**Returns:** Boolean

### `set:containsAll(set, elements)` / `thisSet.containsAll(elements)`

Returns true if set contains ALL specified elements.

```javascript
{1, 2, 3}.containsAll({2, 4})  // false (missing 4)
{1, 2, 3}.containsAll({1, 2})  // true
```

**Returns:** Boolean

---

## PMD-Specific Syntax

### Range-Based For Loop

```javascript
// PMD syntax for iterating over a range
for (var i : 1 to 50) {
  items.add({'id': i, 'descriptor': i});
}

// Equivalent to: for (var i = 1; i <= 50; i++)
```

### Empty Operator

Check if a value is null or empty. **Safer than `.isEmpty()`**.

```javascript
// As condition
if (empty myList) { ... }
if (!(empty startDate.value)) { ... }

// As function
if (!empty(self.value)) { ... }

// In expressions
<% empty queryParams.id %>  // true if null or empty
```

### Page Variables (`pageVariables`)

Store page-level state that persists during the page session.

```javascript
// In onLoad
pageVariables.holidays = holidayService.invoke(reqMap).data;
pageVariables.initialized = true;

// In widgets
"values": "<% pageVariables.holidays %>"

// In scripts
if (pageVariables.initialized) { ... }
```

### Flow Variables (`flowVariables`)

Pass data between pages in a multi-step flow.

```javascript
// Reading (in receiving page)
"value": "<% flowVariables.workerId %>"
"render": "<% flowVariables.withGiftcard %>"

// Writing (via outboundData in sending page)
"outboundEndPoints": [{
  "type": "outboundVariable",
  "name": "variable1",
  "variableScope": "flow",
  "onSend": "<%
    self.data.selectedEmployees = getSelectedEmployees();
    self.data;
  %>"
}]
```

---

## Widget Methods

Methods available on widget references in scripts.

### Value Methods

```javascript
widget.value           // Get current value
widget.value = 'new'   // Set value
widget.getValue()      // Get value (method form)
```

### Grid Methods

```javascript
grid.setRows(dataList)           // Set grid data
grid.rows = dataList             // Alternative assignment
grid.selectedRows                // Array of selected rows
grid.selectedRows.isEmpty()      // Check if any selected
grid.selectedRows[0]             // First selected row
grid.selectedRows[0].childrenMap.columnId.value  // Column value
```

### Validation Methods

```javascript
widget.setError('Error message')    // Show error (blocks submit)
widget.clearError()                 // Clear error
widget.setWarning('Warning text')   // Show warning (yellow)
widget.clearWarning()               // Clear warning
```

### Visibility Methods

```javascript
section.visible = true    // Show section
section.visible = false   // Hide section
widget.setVisible(true)   // Method form
```

### Endpoint Methods

```javascript
// Invoke deferred endpoint with parameters
var result = myEndpoint.invoke({'id': workerId});

// Access response data
result.data
result.descriptor
```

---

## Function Inventory

### Documented (from official Workday docs + PMD Scripting app)

| Namespace | Functions Documented | Status |
|-----------|---------------------|--------|
| `bool:` | `all`, `any` | ✅ Complete |
| `bpfTaskHelper:` | `fetchTaskType` | ✅ Complete |
| `console:` | `debug`, `error`, `info`, `warn` | ✅ Complete |
| `converter:` | `booleanAsInt`, `booleanAsString` | ✅ Complete |
| `date:` | `add`, `between`, `after`, `now`, `parse`, `parseDateString`, `format`, `year`, `month`, `extractValue`, `getDateTimeZone`, `getTodaysDate`, `getTodaysDateFormatted` | ✅ Complete |
| `list:` | `toList`, `toListIncludeNull`, `toMap`, `filter` (6), `find`, `mapAttribute`, `join`, `isEmpty`, `flatten`, `createMapList`, `createMapListWithKeys` + `.distinct()`, `.sort()`, `.add()`, `.contains()` | ✅ Complete |
| `json:` | `parse`, `stringify`, `asJSON`, `create`, `attribute`, `query` | ✅ Complete |
| `map:` | `get`, `put`, `keys`, `values`, `containsKey`, `mapValue`, `forEach`, empty literal `{:}` | ✅ Complete |
| `object:` | `defaultIfNull`, `firstNonNull` | ✅ Complete |
| `regex:` | `find` | 🔶 Partial |
| `set:` | `isEmpty`, `containsAll` | 🔶 Partial |
| `string:` | `formatMessage`, `contains`, `replace` (4 variants), `substringBefore`, `join` | ✅ Core Complete |
| **Widget** | `setRows`, `setError`, `clearError`, `setWarning`, `clearWarning`, `visible`, `selectedRows`, `childrenMap`, `invoke` | ✅ Complete |
| **Syntax** | `for...to` loop, `empty` operator, `pageVariables`, `flowVariables` | ✅ Complete |

### Pending Documentation (available on request)

<details>
<summary>Click to expand full function list</summary>

**date:** `checkTodaysDate`, `createMonth`, `createYear`, `extractValue`, `format`, `formatDateWithTimeZones`, `formatWithTimeZone`, `get`, `getDateTimeZone`, `getTodaysDate`, `getTodaysDateFormatted`, `minusDays/Hours/Minutes/Months/Nanos/Seconds/Weeks/Years`, `month`, `now`, `parse` (3 variants), `parseDateString`, `parseFormattedDateString`, `plusDays/Hours/Minutes/Months/Nanos/Seconds/Weeks/Years`, `timeAfter`, `toString`, `withDayOfMonth/Year`, `withHour/Minute/Month/Nano/Second/Year`, `year`

**list:** `add`, `addAll`, `clear`, `contains`, `containsAll`, `createMapList`, `createMapListWithKeys`, `distinct`, `emptyList`, `exclude`, `excludeEmptyAttribute`, `excludeMultiple`, `excludeRegex`, `first`, `firstNonEmpty`, `flatten`, `forEach`, `get`, `indexOf`, `isEmpty`, `isList`, `join`, `last`, `lastIndexOf`, `map`, `mapAttribute`, `mapBeanAttribute`, `nonNull`, `reduce`, `remove`, `removeAll`, `retainAll`, `reverse`, `set`, `size`, `sort`, `subList`, `toJson`, `toString`

**json:** `asJSON`, `attribute`, `create`, `parse`, `stringify`, `query` (with resultsAsList)

**map:** `add`, `addAll`, `clear`, `containsKey`, `containsValue`, `filter`, `forEach`, `get`, `getKeys`, `getObject`, `getValues`, `getValuesFromKeys`, `isEmpty`, `keys`, `map`, `mapKey`, `mapValue`, `put`, `remove`, `size`, `toJson`, `toString`, `values`

**string:** `abbreviate`, `capitalize`, `concat`, `contains`, `containsIgnoreCase`, `defaultIfBlank`, `defaultIfEmpty`, `endsWith`, `endsWithIgnoreCase`, `formatListToString`, `formatMessage`, `fuzzyMatchIndex`, `fuzzyMatchString`, `fuzzyScore`, `indexOf`, `isAllLowerCase/UpperCase`, `isBlank`, `isNumber`, `isNumeric`, `isString`, `join`, `lastIndexOf`, `leftPad`, `length`, `lowerCase`, `pathEncode`, `remove`, `removeEnd/Start`, `replace`, `replaceIgnoreCase`, `replaceOnce`, `replaceSubstring`, `reverse`, `rightPad`, `size`, `split`, `splitByRegex`, `startsWith`, `startsWithIgnoreCase`, `stripPrefix/Suffix`, `substring`, `substringAfter/Before`, `toDecimal`, `toInt`, `toString`, `trim`, `trimToEmpty`, `truncate`, `uncapitalize`, `upperCase`, `urlDecode/Encode`, `uuid`

**number:** `convertNumberToInt`, `convertStringToInt`, `max`, `min`, `pow`, `sqrt`, `toBigDecimal`

**set:** `add`, `addAll`, `clear`, `contains`, `containsAll`, `filter`, `find`, `forEach`, `isEmpty`, `join`, `map`, `reduce`, `remove`, `size`, `toJson`, `toString`

**regex:** `match`, `replace`, `replaceOnce`, `split`

**validate:** `match`

**file:** `byteCountToDisplaySize`

**fileType:** `getFileType`

**graph:** `createId` (3 variants), `createIds` (2 variants)

**grid:** `getSubtotal`

</details>

---

## Related Documentation

- [PMD-SCRIPTING.md](./PMD-SCRIPTING.md) - Scripting syntax, events, lifecycle
- [GRAMMAR.md](./GRAMMAR.md) - Expression language basics
- [WIDGETS.md](./WIDGETS.md) - Widget types and properties

---

*Last updated: 2025-12-11*
*Sources: Workday Documentation Portal, PMD Scripting Example App*
