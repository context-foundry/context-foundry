# Filesystem-Based Tool Discovery

## Overview

Context Foundry implements **filesystem-based tool discovery** to enable progressive loading of MCP tools. Instead of loading all tool definitions into context at once, agents discover and load tools on-demand, dramatically reducing token usage.

This follows the pattern described in [Anthropic's Code Execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp).

## Benefits

### Token Efficiency
- **98.7% reduction** in tool loading overhead (compared to loading all schemas)
- Tools loaded progressively as needed
- Only relevant tools consume context tokens

### Progressive Discovery
- Agents search for tools using natural language queries
- Three detail levels: minimal, standard, full
- Category-based filtering for targeted discovery

### Extensibility
- Community can create and share custom tools
- Tools stored in `~/.context-foundry/tools/`
- No core codebase modifications needed

### Isolation
- Tools execute in isolated subprocesses
- Timeout protection (default: 300s)
- Parameter validation before execution

## Architecture

### Directory Structure

```
~/.context-foundry/tools/
├── delegation/
│   ├── sync_execute.py           # delegate_to_claude_code
│   ├── async_execute.py          # async delegation
│   └── get_result.py             # check task status
├── codex/
│   ├── search.py                 # search knowledge base
│   ├── add_issue.py              # add issue to codex
│   └── stats.py                  # get codex statistics
├── patterns/
│   ├── read_patterns.py          # read global patterns
│   ├── merge_patterns.py         # merge project patterns
│   └── share_patterns.py         # share to community
└── core/
    ├── status.py                 # system status
    └── autonomous_build.py       # full build workflow
```

### Tool File Format

Each tool is a standalone Python script following this template:

```python
#!/usr/bin/env python3
"""
Tool: tool_name
Category: category_name
Description: Brief description of what the tool does

Parameters:
  param1: str (required) - Description of param1
  param2: int (optional, default=10) - Description of param2
  param3: bool (optional, default=False) - Description of param3

Returns:
  str - Description of return value (usually JSON)

Examples:
  - tool_name({"param1": "value"})
  - tool_name({"param1": "value", "param2": 20})
"""

import sys
import json
from pathlib import Path

# Add Context Foundry to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# Import implementation function
from tools.mcp_utils.some_module import implementation_function


def main():
    """Parse args from stdin and execute tool"""
    try:
        params = json.loads(sys.stdin.read())

        # Validate required parameters
        required = ['param1']
        for req in required:
            if req not in params:
                raise ValueError(f"Missing required parameter: {req}")

        # Call implementation
        result = implementation_function(
            param1=params['param1'],
            param2=params.get('param2', 10),
            param3=params.get('param3', False),
        )

        # Return result (usually JSON)
        print(result)

    except Exception as e:
        error_result = json.dumps({
            "error": str(e),
            "status": "failed",
            "message": "Tool execution failed"
        })
        print(error_result)
        sys.exit(1)


if __name__ == "__main__":
    main()
```

## Creating New Tools

### Step 1: Choose Category

Organize your tool into an appropriate category:

- **delegation**: Task delegation and subprocess management
- **codex**: Knowledge base operations
- **patterns**: Pattern management and learning
- **core**: Core system operations
- **custom**: Your own category

### Step 2: Write Tool File

Create `~/.context-foundry/tools/<category>/<tool_name>.py`:

```python
#!/usr/bin/env python3
"""
Tool: my_custom_tool
Category: custom
Description: Does something useful

Parameters:
  input: str (required) - The input data
  mode: str (optional, default=standard) - Processing mode

Returns:
  str - JSON with results

Examples:
  - my_custom_tool({"input": "test data"})
  - my_custom_tool({"input": "data", "mode": "advanced"})
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


def main():
    try:
        params = json.loads(sys.stdin.read())

        # Your tool logic here
        result = {
            "input": params['input'],
            "mode": params.get('mode', 'standard'),
            "output": "processed data"
        }

        print(json.dumps(result, indent=2))

    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
```

### Step 3: Make Executable

```bash
chmod +x ~/.context-foundry/tools/custom/my_custom_tool.py
```

### Step 4: Test Tool

```bash
# Test manually
echo '{"input": "test"}' | ~/.context-foundry/tools/custom/my_custom_tool.py

# Or test via discovery
python3 -c "
from tools.mcp_utils.filesystem_tools import discover_all_tools, get_scanner

tools = discover_all_tools(force_refresh=True)
scanner = get_scanner()
tool = scanner.get_tool('my_custom_tool')
print(tool.get_summary('full'))
"
```

### Step 5: Restart MCP Server

The MCP server will automatically discover your new tool on next startup:

```bash
# Restart Claude Desktop or
# Re-run the MCP server
```

## Using Tools

### Via Search (Recommended)

Agents can discover tools progressively:

```python
# Search for tools
search_tools("delegation", detail_level="minimal")
# Returns: List of delegation tools with brief descriptions

# Get full details
search_tools("delegate", detail_level="full")
# Returns: Complete tool signatures, parameters, examples

# Filter by category
search_tools("codex", category="codex", detail_level="standard")
# Returns: All codex tools with signatures
```

### Via Direct Execution

Tools can be executed directly from the filesystem:

```python
from tools.mcp_utils.filesystem_tools import execute_tool_by_name

result = execute_tool_by_name(
    "sync_execute",
    {"task": "Create hello.py", "timeout_minutes": 5.0}
)
```

## Docstring Format

### Required Sections

1. **Tool**: Name of the tool (matches filename)
2. **Category**: Category for organization
3. **Description**: What the tool does

### Optional Sections

4. **Parameters**: List of parameters with types and requirements
5. **Returns**: What the tool returns
6. **Examples**: Usage examples

### Parameter Format

```
param_name: type (required/optional, default=value) - Description
```

Examples:
- `task: str (required) - The task to execute`
- `timeout: float (optional, default=10.0) - Timeout in minutes`
- `verbose: bool (optional, default=False) - Enable verbose output`

## Best Practices

### 1. Keep Tools Focused

Each tool should do one thing well:

✅ **Good**: `search.py` - Search codex
✅ **Good**: `add_issue.py` - Add single issue
❌ **Bad**: `codex_manager.py` - Does everything

### 2. Validate Parameters

Always validate required parameters:

```python
required = ['task', 'working_directory']
for param in required:
    if param not in params:
        raise ValueError(f"Missing required parameter: {param}")
```

### 3. Return JSON

Always return JSON for structured data:

```python
result = {
    "status": "success",
    "data": processed_data,
    "metadata": {"timestamp": "2025-11-13T22:00:00"}
}
print(json.dumps(result, indent=2))
```

### 4. Handle Errors Gracefully

Catch exceptions and return error JSON:

```python
except Exception as e:
    error_result = json.dumps({
        "error": str(e),
        "status": "failed",
        "traceback": traceback.format_exc()  # Optional: for debugging
    })
    print(error_result)
    sys.exit(1)
```

### 5. Use Existing Infrastructure

Reuse Context Foundry's implementation functions:

```python
# ✅ Reuse existing code
from tools.mcp_utils.delegation import delegate_to_claude_code_impl
result = delegate_to_claude_code_impl(task=params['task'])

# ❌ Don't reimplement
def my_delegation_implementation():
    # Duplicate code...
```

### 6. Add Comprehensive Examples

Provide 2-3 examples showing different parameter combinations:

```python
Examples:
  - tool_name({"param1": "simple"})
  - tool_name({"param1": "with options", "param2": 20})
  - tool_name({"param1": "full example", "param2": 20, "param3": True})
```

## Advanced Features

### Custom Categories

Create your own tool categories:

```bash
mkdir -p ~/.context-foundry/tools/my-category
# Add tools to this directory
```

Tools will be automatically categorized based on directory structure.

### Tool Versioning

Tools are cache-versioned using file hash:

```python
# In ToolMetadata
file_hash = hashlib.sha256(source.encode()).hexdigest()[:16]
```

If a tool file changes, cache is invalidated automatically.

### Timeout Configuration

Adjust timeout per tool:

```python
from tools.mcp_utils.filesystem_tools import execute_tool_by_name

result = execute_tool_by_name(
    "long_running_tool",
    params,
    timeout=600  # 10 minutes
)
```

### Subprocess Isolation

All tools execute in isolated subprocesses:

- Separate process space
- Independent file descriptors
- Timeout protection
- Clean shutdown on errors

## Troubleshooting

### Tool Not Discovered

**Problem**: Tool doesn't appear in `search_tools` results

**Solutions**:
1. Check file has module docstring with required sections
2. Ensure file is in `~/.context-foundry/tools/` subdirectory
3. Verify filename doesn't start with `_` (e.g., `__init__.py`)
4. Force cache refresh: `discover_all_tools(force_refresh=True)`

### Tool Execution Fails

**Problem**: Tool returns error when executed

**Solutions**:
1. Test tool manually: `echo '{}' | python3 tool_file.py`
2. Check parameter validation
3. Verify imports work from tool directory
4. Check error output in JSON result

### Missing Parameters

**Problem**: `ValueError: missing required parameters`

**Solutions**:
1. Verify parameter names match docstring exactly
2. Check parameter is marked as `(required)` in docstring
3. Provide all required parameters in call

### Import Errors

**Problem**: `ModuleNotFoundError` when tool runs

**Solutions**:
1. Verify path insertion is correct:
   ```python
   sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
   ```
2. Check Context Foundry is in expected location
3. Use absolute imports from `tools.mcp_utils` or `context_foundry`

## Testing

### Unit Tests

Test individual tools:

```bash
# Run all filesystem tool tests
pytest tests/test_filesystem_tools.py -v

# Test specific function
pytest tests/test_filesystem_tools.py::TestToolMetadataParser::test_parse_docstring_basic -v
```

### Integration Tests

Test complete workflow:

```python
def test_custom_tool():
    # 1. Discover tools
    tools = discover_all_tools(force_refresh=True)

    # 2. Find your tool
    scanner = get_scanner()
    tool = scanner.get_tool('my_custom_tool')

    # 3. Verify metadata
    assert tool.name == 'my_custom_tool'
    assert tool.category == 'custom'

    # 4. Test execution
    executor = ToolExecutor()
    result = executor.execute_tool(
        tool,
        {"input": "test data"}
    )

    # 5. Verify output
    output = json.loads(result)
    assert output['status'] == 'success'
```

### Manual Testing

Test tool directly from command line:

```bash
# Simple test
echo '{"param1": "value"}' | python3 ~/.context-foundry/tools/category/tool.py

# With jq for formatted output
echo '{"param1": "value"}' | python3 tool.py | jq .

# Test error handling
echo '{}' | python3 tool.py  # Missing required params
```

## Performance Considerations

### Token Usage

- **Traditional**: Load all 28+ tool schemas = ~15K-20K tokens
- **Filesystem-based**: Load only searched tools = ~500-2K tokens
- **Savings**: 90-98% reduction in tool loading overhead

### Discovery Caching

Tools are cached after first discovery:

```python
# First call: Scans filesystem (~50-100ms)
tools = discover_all_tools(force_refresh=False)

# Subsequent calls: Loads from cache (~1-5ms)
tools = discover_all_tools(force_refresh=False)
```

Cache invalidation:
- Automatic: File hash changes
- Manual: `force_refresh=True`

### Search Performance

```python
# Minimal: ~1-2ms (names only)
search_tools("query", detail_level="minimal")

# Standard: ~5-10ms (with signatures)
search_tools("query", detail_level="standard")

# Full: ~20-50ms (everything)
search_tools("query", detail_level="full")
```

## Security

### Subprocess Isolation

Tools run in isolated subprocesses:
- Cannot affect parent process
- Timeout protection
- Resource limits (via OS)

### Input Validation

Always validate parameters:
- Check required parameters exist
- Validate types when possible
- Sanitize file paths

### Safe Tool Execution

```python
# ✅ Safe: Uses subprocess isolation
result = execute_tool_by_name("tool", params)

# ✅ Safe: Validates parameters first
executor = ToolExecutor()
executor._validate_parameters(tool, params)
result = executor.execute_tool(tool, params)
```

## Community Sharing

### Sharing Your Tools

1. Create tools in `~/.context-foundry/tools/`
2. Test thoroughly
3. Document with comprehensive examples
4. Submit PR to Context Foundry repository

### Installing Community Tools

```bash
# Browse community tools
ls ~/.context-foundry/tools/

# Install from repository
git clone https://github.com/user/context-foundry-tools
cp -r context-foundry-tools/* ~/.context-foundry/tools/

# Verify installation
python3 -c "from tools.mcp_utils.filesystem_tools import discover_all_tools; print(len(discover_all_tools(force_refresh=True)))"
```

## Examples

### Example 1: Simple Calculation Tool

```python
#!/usr/bin/env python3
"""
Tool: calculate
Category: math
Description: Perform basic arithmetic calculations

Parameters:
  operation: str (required) - Operation (add, subtract, multiply, divide)
  a: float (required) - First operand
  b: float (required) - Second operand

Returns:
  str - JSON with result

Examples:
  - calculate({"operation": "add", "a": 5, "b": 3})
  - calculate({"operation": "multiply", "a": 4, "b": 7})
"""

import sys
import json

def main():
    try:
        params = json.loads(sys.stdin.read())

        op = params['operation']
        a = float(params['a'])
        b = float(params['b'])

        operations = {
            'add': a + b,
            'subtract': a - b,
            'multiply': a * b,
            'divide': a / b if b != 0 else None
        }

        result = operations.get(op)
        if result is None:
            raise ValueError(f"Invalid operation or division by zero: {op}")

        print(json.dumps({"result": result, "operation": op}))

    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

if __name__ == "__main__":
    main()
```

### Example 2: File Processor Tool

```python
#!/usr/bin/env python3
"""
Tool: process_file
Category: files
Description: Process a text file and return statistics

Parameters:
  file_path: str (required) - Path to file
  count_words: bool (optional, default=True) - Count words
  count_lines: bool (optional, default=True) - Count lines

Returns:
  str - JSON with file statistics

Examples:
  - process_file({"file_path": "/tmp/data.txt"})
  - process_file({"file_path": "/tmp/data.txt", "count_words": False})
"""

import sys
import json
from pathlib import Path

def main():
    try:
        params = json.loads(sys.stdin.read())

        file_path = Path(params['file_path'])
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        content = file_path.read_text()

        stats = {}

        if params.get('count_lines', True):
            stats['lines'] = len(content.splitlines())

        if params.get('count_words', True):
            stats['words'] = len(content.split())

        stats['chars'] = len(content)
        stats['file'] = str(file_path)

        print(json.dumps(stats, indent=2))

    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

if __name__ == "__main__":
    main()
```

## References

- [Anthropic: Code Execution with MCP](https://www.anthropic.com/engineering/code-execution-with-mcp)
- [Model Context Protocol Specification](https://modelcontextprotocol.io/)
- [Context Foundry Documentation](../README.md)

## Support

- Issues: [GitHub Issues](https://github.com/anthropics/context-foundry/issues)
- Discussions: [GitHub Discussions](https://github.com/anthropics/context-foundry/discussions)
- Examples: `~/.context-foundry/tools/` directory
