# Deprecation Notice

## Python Direct API Call Orchestrators (DEPRECATED)

The following files are **deprecated** and marked for retirement. They represent an early version of Context Foundry that made direct API calls to Anthropic/OpenAI, which:

1. ❌ Requires API keys in `.env` file
2. ❌ Doesn't inherit Claude Code's authentication
3. ❌ Breaks the "MCP server rides on Claude Code configuration" design principle
4. ❌ Creates authentication complexity for users

### Deprecated Files:

**Orchestrators:**
- `workflows/autonomous_orchestrator.py` - Early Python orchestrator with direct API calls
- `workflows/multi_agent_orchestrator.py` - Multi-agent variant with direct API calls

**Runners:**
- `tools/run_parallel_build.py` - Parallel build runner using Python orchestrator
- `tools/test_parallel_runner.py` - Test runner for parallel mode

**MCP Server:**
- `tools/mcp_server.py` - `use_parallel=True` mode (lines 1080-1189)

### ✅ Correct Approach: `/agents` Method

The **correct and supported** method is the `/agents` approach:

**Architecture:**
```
User's Claude Code (authenticated)
  ↓
MCP Server
  ↓
Delegates to fresh `claude` CLI instance
  ↓
Uses `orchestrator_prompt.txt` as system prompt
  ↓
Orchestrator uses `/agents` command to spawn Scout/Architect/Builder
  ↓
Agents inherit Claude Code's authentication automatically ✅
```

**Implementation:**
- System Prompt: `tools/orchestrator_prompt.txt` (1372 lines)
- Delegation: `claude --print --system-prompt {prompt} {task}`
- Agent Spawning: Native `/agents` command (line 83, 209, 296, etc.)
- Authentication: Inherited automatically from parent Claude Code process

**Usage:**
```python
autonomous_build_and_deploy(
    task="Build XYZ",
    use_parallel=False  # ✅ Uses /agents (correct)
)
```

### Migration Path:

1. **Immediate:** Use `use_parallel=False` (sequential mode with `/agents`)
2. **Future:** Deprecate `use_parallel` parameter entirely
3. **Long-term:** Remove Python orchestrator files completely

### Why This Matters:

Users expect Context Foundry to "ride on Claude Code's configuration" - meaning:
- ✅ No separate API keys needed
- ✅ Works with Claude Max/Pro subscriptions
- ✅ Inherits all Claude Code authentication
- ✅ Zero additional setup

The Python orchestrator approach violated this principle and should be retired.

---

**Date:** 2025-10-22
**Reason:** Incompatible with Claude Code authentication inheritance
**Replacement:** Sequential mode with `/agents` command
**Status:** Marked for removal in next major version
