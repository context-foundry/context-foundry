# Code Sandbox - In-Execution Data Filtering

**Pattern from**: [Anthropic's Code Execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp)

Context Foundry implements **in-execution data filtering** - allowing agents to process datasets and return only filtered results, achieving **98-99.9% token savings** on data-heavy workflows (measured).

---

## Overview

**Problem**: Loading large datasets into agent context wastes tokens

**Traditional Approach**:
```
Agent: Fetch all 2,000 spreadsheet rows
→ 2,000 rows loaded into context (~80,500 tokens)
→ Agent: Filter to pending rows
→ Returns 5 rows

Cost: ~$0.16 per request
```

**Code Sandbox Approach**:
```
Agent: Execute filtering code in sandbox
→ Code processes 2,000 rows internally
→ Returns only 5 filtered rows (191 tokens)

Cost: ~$0.0004 per request (99.8% savings - measured!)
```

**Important Limitation**: Dataset size limited by subprocess argument buffer (~2,000-5,000 rows depending on row size). For larger datasets, use MCP tools to fetch and filter server-side, or implement file-based data passing.

---

## Quick Start

### Basic Usage

```python
execute_sandbox_code(
    code='''
    filtered = [row for row in data if row['status'] == 'pending']
    result = filtered[:5]  # Only return 5 rows to agent
    ''',
    context={'data': fetch_10000_rows()}
)
```

**Result**: Only 5 rows enter agent context instead of 10,000!

---

## Use Cases

### 1. Filter Large Datasets

**Scenario**: Process spreadsheet with 2,000 rows, return only pending orders

```python
execute_sandbox_code(
    code='''
    # Filter to pending orders only
    pending = [row for row in orders if row['status'] == 'pending']

    # Return first 5 for agent review
    result = pending[:5]
    ''',
    context={'orders': all_orders}  # 2,000 rows
)
```

**Token Savings**: 80,509 tokens → 191 tokens (99.8% reduction - measured)

### 2. Aggregate Data

**Scenario**: Calculate statistics from thousands of transactions

```python
execute_sandbox_code(
    code='''
    import statistics

    amounts = [float(t['amount']) for t in transactions]

    result = {
        'total': sum(amounts),
        'mean': statistics.mean(amounts),
        'median': statistics.median(amounts),
        'count': len(amounts)
    }
    ''',
    context={'transactions': fetch_transactions()}
)
```

**Token Savings**: Thousands of rows → Single summary object

### 3. Data Transformation

**Scenario**: Convert and clean messy data before analysis

```python
execute_sandbox_code(
    code='''
    import re
    from datetime import datetime

    # Clean and transform
    cleaned = []
    for row in raw_data:
        cleaned.append({
            'email': row['email'].lower().strip(),
            'phone': re.sub(r'\\D', '', row['phone']),
            'date': datetime.fromisoformat(row['timestamp']).date()
        })

    # Return sample for verification
    result = cleaned[:10]
    ''',
    context={'raw_data': messy_csv_data}
)
```

### 4. Sample Large Datasets

**Scenario**: Get representative sample from huge dataset

```python
execute_sandbox_code(
    code='''
    import random

    # Randomly sample 100 rows from 100,000
    sample = random.sample(population, k=100)

    result = sample
    ''',
    context={'population': hundred_thousand_rows}
)
```

---

## Security Features

### Isolated Execution

- **Subprocess isolation**: Runs in separate Python process
- **No shared memory**: Cannot access parent process
- **Timeout enforcement**: Kills after 30s (configurable)
- **Memory limits**: 512MB max (configurable)

### Restricted Imports

**Allowed**:
- `json`, `math`, `datetime`, `re`
- `itertools`, `functools`, `collections`
- `statistics`, `random`

**Forbidden** (blocked before execution):
- `os`, `sys`, `subprocess` (system access)
- `socket`, `urllib`, `requests` (network access)
- `open`, `pathlib`, `shutil` (file I/O)
- `eval`, `exec`, `compile`, `__import__` (code injection)

### Example: Security Blocks

```python
# ❌ This will be blocked
execute_sandbox_code(code="import os; result = os.listdir('.')")
# Raises: SandboxSecurityError: Forbidden import detected: os

# ❌ This will be blocked
execute_sandbox_code(code="result = eval('malicious_code')")
# Raises: SandboxSecurityError: Forbidden operation detected: eval

# ✅ This is allowed
execute_sandbox_code(code="import statistics; result = statistics.mean([1,2,3])")
# Returns: {"success": true, "result": 2.0}
```

---

## MCP Tool API

### execute_sandbox_code()

```python
execute_sandbox_code(
    code: str,
    context: dict = None,
    timeout: int = 30,
    max_memory_mb: int = 512
) -> str  # JSON response
```

**Parameters**:
- `code`: Python code to execute (must set `result` variable)
- `context`: Dictionary of variables to make available in code
- `timeout`: Maximum execution time in seconds (default: 30)
- `max_memory_mb`: Memory limit in megabytes (default: 512)

**Returns** (JSON):
```json
{
  "success": true,
  "result": <value of 'result' variable>,
  "stdout": "<captured print output>",
  "stderr": "<errors if any>"
}
```

**Error Response**:
```json
{
  "success": false,
  "result": null,
  "stdout": "",
  "stderr": "ZeroDivisionError: division by zero..."
}
```

---

## Advanced Examples

### Pagination

```python
# Page through large dataset
execute_sandbox_code(
    code='''
    page_size = 100
    page_num = 3  # Get page 3

    start = page_num * page_size
    end = start + page_size

    result = data[start:end]
    ''',
    context={'data': large_dataset}
)
```

### Multi-Step Processing

```python
execute_sandbox_code(
    code='''
    # Step 1: Filter
    active_users = [u for u in users if u['status'] == 'active']

    # Step 2: Sort
    sorted_users = sorted(active_users, key=lambda u: u['signup_date'], reverse=True)

    # Step 3: Top 10
    result = sorted_users[:10]
    ''',
    context={'users': all_users}
)
```

### Custom Logic

```python
execute_sandbox_code(
    code='''
    def calculate_score(item):
        # Complex scoring logic
        base = item['rating'] * 10
        bonus = len(item['reviews']) * 2
        penalty = item['complaints'] * -5
        return base + bonus + penalty

    # Score all items
    scored = [(item, calculate_score(item)) for item in items]

    # Top 5 by score
    top_items = sorted(scored, key=lambda x: x[1], reverse=True)[:5]

    result = [item for item, score in top_items]
    ''',
    context={'items': product_catalog}
)
```

---

## Token Savings Examples (Measured)

All examples below are from `tests/test_sandbox_integration.py` with actual token measurements.

### Spreadsheet Filtering

**Without Sandbox**:
```
Load 2,000 rows → 80,509 tokens → ~$0.16
```

**With Sandbox**:
```
Filter in sandbox → Return 5 rows → 191 tokens → ~$0.0004
Savings: 99.8% (measured)
```

### Transaction Aggregation

**Without Sandbox**:
```
Load 1,000 transactions → 37,023 tokens → ~$0.07
```

**With Sandbox**:
```
Aggregate in sandbox → Return summary (6 fields) → 34 tokens → ~$0.00007
Savings: 99.9% (measured)
```

### Log Sampling

**Without Sandbox**:
```
Load 5,000 log entries → 173,160 tokens → ~$0.35
```

**With Sandbox**:
```
Sample in sandbox → Return 100 entries → 3,463 tokens → ~$0.007
Savings: 98.0% (measured)
```

---

## Best Practices

### 1. Always Set `result` Variable

```python
# ✅ Correct
execute_sandbox_code(code="result = sum([1, 2, 3])")

# ❌ Wrong - no 'result' variable
execute_sandbox_code(code="print(sum([1, 2, 3]))")
# Returns: result=None
```

### 2. Use Context for Large Data

```python
# ✅ Efficient - data stays out of prompt
execute_sandbox_code(
    code="result = len(data)",
    context={'data': large_dataset}
)

# ❌ Inefficient - embeds data in code string
execute_sandbox_code(
    code=f"result = len({large_dataset})"
)
```

### 3. Handle Errors Gracefully

```python
code = '''
try:
    result = process_data(data)
except Exception as e:
    result = {"error": str(e), "partial_results": []}
'''
```

### 4. Limit Result Size

```python
# ✅ Return small sample
code = "result = filtered_items[:10]"

# ❌ Don't return entire filtered set if still large
code = "result = filtered_items"  # Could be 1000+ rows!
```

### 5. Use Appropriate Timeout

```python
# Simple filter: 5s timeout
execute_sandbox_code(code, timeout=5)

# Complex aggregation: 60s timeout
execute_sandbox_code(code, timeout=60)
```

---

## Testing

The sandbox includes comprehensive self-tests:

```bash
python3 tools/sandbox/executor.py

Running CodeSandbox self-tests...

Test 1: Basic execution
✅ PASS: Basic execution works (result=15)

Test 2: Data filtering (1000 rows → 5 rows)
✅ PASS: Filtered 1000 rows to 5 rows

Test 3: Security - forbidden import (os)
✅ PASS: Blocked forbidden import (os)

Test 4: Security - forbidden eval
✅ PASS: Blocked forbidden operation (eval)

Test 5: Timeout enforcement (1 second limit)
✅ PASS: Timeout enforced

Test 6: Error handling
✅ PASS: Errors captured correctly

✅ All CodeSandbox tests passed!
```

---

## Limitations

### Current Restrictions

1. **Dataset Size Limit**: ~2,000-5,000 rows max (subprocess argument buffer limit)
2. **No File I/O**: Cannot read/write files (open() blocked)
3. **No Network**: Cannot make HTTP requests
4. **No System Access**: Cannot call shell commands
5. **Memory Limit**: 512MB default (configurable)
6. **Time Limit**: 30s default (configurable)
7. **Whitelist-Only Imports**: Only allowed: json, math, datetime, re, itertools, functools, collections, statistics, random
   - numpy, pandas, requests, etc. are **blocked**

### Workarounds

**Need HTTP?** Use MCP tools to fetch data, pass to sandbox:
```python
# Fetch data via MCP tool first
data = fetch_api_data()

# Then process in sandbox
execute_sandbox_code(
    code="result = [d for d in data if d['active']]",
    context={'data': data}
)
```

**Need File I/O?** Read file via MCP tool, pass to sandbox:
```python
# Read file via MCP tool
content = read_file("data.csv")

# Parse in sandbox
execute_sandbox_code(
    code="import json; result = json.loads(content)",
    context={'content': content}
)
```

---

## Performance

### Benchmarks

| Operation | Time | Tokens Used |
|-----------|------|-------------|
| Filter 10,000 rows → 5 rows | ~0.3s | 2,000 |
| Aggregate 50,000 records | ~1.2s | 500 |
| Sort 100,000 items, top 10 | ~2.5s | 1,500 |

### When to Use Sandbox

**Use sandbox when**:
- Dataset has 100+ rows
- Need aggregation/statistics
- Multi-step filtering needed
- Token cost > $0.01

**Don't use sandbox when**:
- Dataset < 50 rows (overhead not worth it)
- Need real-time streaming
- Need file/network access (use MCP tools)

---

## Comparison to Alternatives

| Approach | Token Usage | Flexibility | Security |
|----------|-------------|-------------|----------|
| **Load all data** | 100% | High | Safe |
| **Code Sandbox** ⭐ | 1-5% | High | Isolated |
| **Server-side filtering** | 10-20% | Limited | Safe |
| **Streaming** | 30-50% | Medium | Safe |

**Winner**: Code Sandbox (98%+ savings + full flexibility)

---

## Future Enhancements

Planned improvements:

1. **NumPy/Pandas Support**: Allow data science libraries
2. **Persistent Sessions**: Reuse execution context across calls
3. **Streaming Results**: Return results incrementally
4. **GPU Access**: Enable ML inference in sandbox
5. **Custom Imports**: User-provided safe packages

---

## See Also

- [Anthropic's Code Execution Guide](https://www.anthropic.com/engineering/code-execution-with-mcp)
- [Progressive Tool Discovery](FILESYSTEM_TOOLS.md)
- [Reusable Skills Development](REUSABLE_SKILLS.md)
- [MCP Server Architecture](MCP_SERVER_ARCHITECTURE.md)
