# MCP Server Template

A template for building Model Context Protocol (MCP) servers that integrate with Claude Desktop, Claude Code, and other MCP clients.

## What is an MCP Server?

MCP servers expose tools and data to AI assistants like Claude. They allow you to:

- Create custom tools that Claude can use
- Provide data sources Claude can access
- Integrate external APIs and services
- Build reusable tool libraries

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Test the Server

```bash
python3 mcp_server.py
```

You should see:
```
🚀 MCP Server Starting

📋 Available tools:
   - hello
   - calculate
   - fetch_data
   - get_server_info
```

Press `Ctrl+C` to stop.

### 3. Configure in Claude Desktop

Add to your Claude Desktop config file:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "my-server": {
      "command": "python3",
      "args": ["/absolute/path/to/mcp_server.py"]
    }
  }
}
```

### 4. Restart Claude Desktop

Tools will appear automatically!

## Adding Your Own Tools

### Simple Tool

```python
@mcp.tool()
def my_tool(input: str) -> str:
    """
    Description of what your tool does.
    This appears to Claude.
    """
    # Your implementation
    return f"Processed: {input}"
```

### Async Tool (for I/O operations)

```python
@mcp.tool()
async def my_async_tool(url: str) -> str:
    """Fetch data from a URL."""
    import httpx
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response.text
```

### Tool with Multiple Parameters

```python
@mcp.tool()
def complex_tool(
    required_param: str,
    optional_param: str = "default",
    flag: bool = False
) -> str:
    """Tool with multiple parameters."""
    return json.dumps({
        "required": required_param,
        "optional": optional_param,
        "flag": flag
    })
```

## Adding Resources

Resources provide read-only data:

```python
@mcp.resource("data://my-data")
def get_my_data() -> str:
    """Provide data as a resource."""
    return json.dumps({"data": "value"})
```

## Best Practices

### 1. Clear Descriptions

Tool docstrings become descriptions Claude sees:

```python
@mcp.tool()
def search(query: str, limit: int = 10) -> str:
    """
    Search for items matching the query.

    Returns up to 'limit' results sorted by relevance.
    """
```

### 2. Type Hints

Always use type hints for automatic validation:

```python
def my_tool(text: str, count: int, enabled: bool = False) -> dict:
    # Python knows text is string, count is int, etc.
```

### 3. Error Handling

Return error info instead of crashing:

```python
@mcp.tool()
def safe_tool(input: str) -> str:
    try:
        result = risky_operation(input)
        return json.dumps({"success": True, "data": result})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})
```

### 4. Structured Responses

Return JSON for complex data:

```python
return json.dumps({
    "status": "success",
    "data": [1, 2, 3],
    "count": 3,
    "message": "Processed successfully"
}, indent=2)
```

### 5. Logging to stderr

Use stderr for debug logging (stdout is for MCP protocol):

```python
import sys
print(f"Debug: Processing {count} items", file=sys.stderr)
```

## Testing

Test tools as regular Python functions:

```python
def test_my_tool():
    result = my_tool("test input")
    assert "success" in result
    data = json.loads(result)
    assert data["success"] == True
```

Run tests:
```bash
python3 -m pytest tests/
```

## Deployment

### Local Development

Use the Claude Desktop config above.

### Distribution

**Option 1: GitHub Repository**
```bash
# Users install with:
git clone https://github.com/you/your-mcp-server
cd your-mcp-server
pip install -r requirements.txt
```

**Option 2: Python Package**
```bash
# Publish to PyPI
pip install your-mcp-server
```

**Option 3: NPX Wrapper**
```bash
# Users can run with:
npx your-mcp-server
```

## Troubleshooting

### Tools don't appear in Claude Desktop

- ✅ Check config file syntax is valid JSON
- ✅ Use absolute path to mcp_server.py
- ✅ Verify Python 3.10+ with `python3 --version`
- ✅ Ensure FastMCP installed: `pip install fastmcp`
- ✅ Restart Claude Desktop

### Tool execution errors

- ✅ Check parameter types match type hints
- ✅ Add try/except for error handling
- ✅ Test tool functions individually first
- ✅ Check logs in Claude Desktop (stderr output)

### Import errors

- ✅ Install all dependencies: `pip install -r requirements.txt`
- ✅ Use virtual environment to avoid conflicts
- ✅ Check Python version (3.10+ required)

## Examples

This template includes working examples:

- `hello` - Simple string tool
- `calculate` - Tool with multiple parameters
- `fetch_data` - Async HTTP request tool
- `get_server_info` - Structured JSON response
- `data://example` - Resource example

## Resources

- **MCP Specification**: https://modelcontextprotocol.io
- **FastMCP Documentation**: https://github.com/jlowin/fastmcp
- **Example Servers**: https://github.com/modelcontextprotocol/servers
- **Claude Desktop Config**: https://modelcontextprotocol.io/docs/tools/claude-desktop

## License

MIT

## Created By

Generated by Context Foundry - Autonomous Development Platform
