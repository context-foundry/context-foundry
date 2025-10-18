# Claude Code Delegation - Test Examples

This document provides test scenarios for the `delegate_to_claude_code` MCP tool that allows delegating tasks to fresh Claude Code CLI instances.

## Prerequisites

Before running these tests, ensure:
1. The MCP server is running (Terminal 1): `python3 /Users/name/homelab/context-foundry/tools/mcp_server.py`
2. Claude Code CLI is connected to the MCP server (Terminal 2): Start `claude-code` normally
3. The `claude-code` command is in your PATH
4. MCP settings are configured at `~/.config/claude-code/mcp_settings.json`

## Test Scenario 1: Simple Task Delegation

**Objective:** Verify basic task delegation works

**Test:**
```
Use the mcp__delegate_to_claude_code tool with:
- task: "Create a file called hello.py that prints 'Hello from delegated Claude Code instance!'"
```

**Expected Result:**
- Status: ✅ Success
- A new `hello.py` file should be created in the working directory
- Output should show the task completion
- Duration should be displayed in seconds
- stdout/stderr should be captured

**Verification:**
```bash
cat hello.py
python3 hello.py
```

Expected output: `Hello from delegated Claude Code instance!`

---

## Test Scenario 2: Task with Specific Working Directory

**Objective:** Verify working directory parameter works correctly

**Setup:**
```bash
mkdir -p /tmp/claude-test-delegation
```

**Test:**
```
Use the mcp__delegate_to_claude_code tool with:
- task: "Create a file named test_output.txt containing the current date and directory path"
- working_directory: "/tmp/claude-test-delegation"
```

**Expected Result:**
- Status: ✅ Success
- File should be created in `/tmp/claude-test-delegation/` not the current directory
- Output should show the correct working directory

**Verification:**
```bash
ls -la /tmp/claude-test-delegation/
cat /tmp/claude-test-delegation/test_output.txt
```

---

## Test Scenario 3: Task with Timeout (Short)

**Objective:** Verify timeout mechanism works

**Test:**
```
Use the mcp__delegate_to_claude_code tool with:
- task: "Create a simple calculator function in calc.py"
- timeout_minutes: 0.5
```

**Expected Result:**
- Should complete within 30 seconds (0.5 minutes)
- Status: ✅ Success (if task completes quickly)
- OR Status: ⏱️ Timeout (if task takes longer than 30 seconds)

**Note:** This tests that the timeout parameter is respected.

---

## Test Scenario 4: Task with Additional CLI Flags

**Objective:** Verify additional_flags parameter works

**Test:**
```
Use the mcp__delegate_to_claude_code tool with:
- task: "List all Python files in the current directory"
- additional_flags: "--model claude-sonnet-4"
```

**Expected Result:**
- Status: ✅ Success
- Command should include the `--model claude-sonnet-4` flag
- Output should show the command that was executed

**Note:** The actual flag behavior depends on what the claude-code CLI supports.

---

## Test Scenario 5: Error Handling - Invalid Working Directory

**Objective:** Verify error handling for invalid paths

**Test:**
```
Use the mcp__delegate_to_claude_code tool with:
- task: "Create a test file"
- working_directory: "/nonexistent/path/that/does/not/exist"
```

**Expected Result:**
- Status: ❌ Error
- Clear error message indicating the directory does not exist
- Suggested action to fix the issue

---

## Test Scenario 6: Parallel Delegation

**Objective:** Test delegating multiple tasks to separate instances

**Test:**
```
Sequentially delegate two tasks:

Task 1:
- task: "Create math_functions.py with add, subtract, multiply, divide functions"
- working_directory: "/tmp/project1"

Task 2:
- task: "Create string_utils.py with reverse, uppercase, lowercase functions"
- working_directory: "/tmp/project2"
```

**Expected Result:**
- Both tasks complete successfully
- Files created in separate directories
- Each delegation is independent with fresh context

**Verification:**
```bash
ls -la /tmp/project1/
ls -la /tmp/project2/
cat /tmp/project1/math_functions.py
cat /tmp/project2/string_utils.py
```

---

## Test Scenario 7: Code Analysis Delegation

**Objective:** Delegate a code analysis task

**Test:**
```
Use the mcp__delegate_to_claude_code tool with:
- task: "Analyze the codebase in the current directory and create a summary.md file with the architecture overview"
- working_directory: "/Users/name/homelab/context-foundry"
- timeout_minutes: 15.0
```

**Expected Result:**
- Status: ✅ Success
- A `summary.md` file created with codebase analysis
- Duration shown (should be less than 15 minutes)
- Comprehensive analysis in the output

---

## Test Scenario 8: Testing and Verification Delegation

**Objective:** Delegate testing tasks to fresh instances

**Setup:**
```bash
# Create a simple Python file to test
mkdir -p /tmp/test-delegation
cat > /tmp/test-delegation/sample.py << 'EOF'
def add(a, b):
    return a + b

def multiply(a, b):
    return a * b
EOF
```

**Test:**
```
Use the mcp__delegate_to_claude_code tool with:
- task: "Create comprehensive pytest tests for sample.py and run them"
- working_directory: "/tmp/test-delegation"
- timeout_minutes: 5.0
```

**Expected Result:**
- Status: ✅ Success
- Test file created (e.g., `test_sample.py`)
- Tests executed
- Output shows test results

---

## Common Issues and Troubleshooting

### Issue: "claude-code command not found"

**Solution:**
- Ensure claude-code CLI is installed
- Add it to your PATH: `export PATH="/path/to/claude-code:$PATH"`
- Verify: `which claude-code`

### Issue: Timeout too short

**Solution:**
- Increase `timeout_minutes` parameter
- Default is 10 minutes, increase to 15-30 for complex tasks

### Issue: Working directory errors

**Solution:**
- Use absolute paths for working_directory
- Ensure the directory exists before delegating
- Create it first: `mkdir -p /path/to/directory`

### Issue: Output not showing correctly

**Solution:**
- Check stdout and stderr sections separately
- Some output may go to stderr instead of stdout
- Review the full formatted output

---

## Performance Benchmarks

Expected typical durations for reference:

| Task Type | Expected Duration | Recommended Timeout |
|-----------|------------------|---------------------|
| Simple file creation | 5-15 seconds | 2 minutes |
| Code generation (1-2 files) | 15-45 seconds | 5 minutes |
| Analysis of small codebase | 30-90 seconds | 10 minutes |
| Analysis of large codebase | 2-5 minutes | 15 minutes |
| Test creation and execution | 30-120 seconds | 10 minutes |
| Full project scaffold | 1-3 minutes | 15 minutes |

---

## Next Steps

After verifying these test scenarios work:

1. **Integration Testing**: Use delegation in real workflows
2. **Performance Tuning**: Optimize timeout values for your use cases
3. **Automation**: Chain multiple delegations for complex pipelines
4. **Documentation**: Document your own delegation patterns

---

## Additional Resources

- MCP Server Code: `/Users/name/homelab/context-foundry/tools/mcp_server.py`
- MCP Settings: `~/.config/claude-code/mcp_settings.json`
- Setup Guide: `CLAUDE_CODE_MCP_SETUP.md`
