# Codebase Analysis Report

## Project Overview
- **Type**: Python CLI tool / MCP Server for autonomous software development
- **Languages**: Python (primary), Bash, Markdown
- **Architecture**: MCP-based tool suite with autonomous build orchestration
- **Current Branch**: main
- **Git Status**: Clean (only .context-foundry/ modified)

## Key Files and Structure

### Entry Points
- `tools/mcp_server.py` - Main MCP server implementation (~3500 lines)
- `tools/orchestrator_prompt.txt` - Core orchestrator prompt for autonomous builds
- `tools/use_baml.py` - BAML integration for type-safe LLM outputs

### Configuration
- `requirements.txt` - Minimal MCP dependencies (fastmcp, tiktoken, baml-py)
- `.env.example` - Environment variable template
- `VERSION` - Version file (v2.x)

### Core Tools Directory (`tools/`)
- **MCP Server**: `mcp_server.py` - FastMCP-based server with multiple tools
- **BAML Integration**: `baml_integration.py`, `baml_schemas/` - Type-safe outputs
- **Context Budget**: `check_context_budget.py`, `context_budget/` - Token tracking
- **Caching**: `cache/` - Scout and test result caching
- **Incremental Builds**: `incremental/` - Change detection and incremental processing
- **Back Pressure**: `back_pressure/` - Validation and quality gates
- **Metrics**: `metrics/` - Cost calculation and tracking
- **Tool Helpers**: `tool_helpers/` - File reading, search, output formatting

### Documentation (`docs/`)
- Extensive documentation covering:
  - Architecture decisions
  - BAML integration
  - Context budget monitoring
  - MCP server setup
  - FAQ and examples
  - 50+ markdown files

### Tests (`tests/`)
- Multiple test directories found:
  - `/tests/` - Main test suite
  - `/tools/livestream/tests/` - Livestream tests
  - `/extensions/flowise/tests/` - Flowise extension tests
  - `/integrations/baml/python/tests/` - BAML integration tests

## Current State Analysis

### Existing Architecture
Context Foundry is a mature autonomous build system with:
1. **MCP Server Integration** - Uses FastMCP for Claude Desktop integration
2. **Multi-Phase Build Process** - Scout → Architect → Builder → Test → Deploy
3. **Self-Learning System** - Pattern library that improves over time
4. **Modular Design** - Plugins, extensions (Flowise), integrations (BAML)
5. **Context Management** - Active budget monitoring, token optimization

### Dependencies (Minimal)
- `fastmcp>=2.0.0` - MCP server framework
- `nest-asyncio>=1.5.0` - Async/sync compatibility
- `tiktoken>=0.5.0` - Token counting
- `baml-py>=0.211.0` - Structured LLM outputs

**Total footprint**: ~60MB (down from 3-4GB in v1.x)

## Task Analysis: Context Foundry Evolution System (CFES)

### What Needs to Be Built

This task requests building a comprehensive autonomous evolution system with:

1. **Evolution Daemon** (`tools/evolution/daemon.py`)
   - Continuously-running service
   - Queue polling + event-driven
   - Resource management
   - systemd/launchd integration

2. **Task Queue System** (`tools/evolution/task_queue.py`)
   - SQLite-based persistent queue
   - Tables: tasks, task_history, project_registry, agent_network

3. **Three Evolution Modes** (plugins in `tools/evolution/modes/`)
   - Self-Improvement: Analyzes CF codebase, generates improvement tasks
   - Chaos/Creative: Random project generator
   - Research/Discovery: Research assistant with web search

4. **Communication Layer** (`tools/evolution/communication/`)
   - Web Dashboard (FastAPI + WebSocket)
   - REST API
   - WebSocket streaming
   - Local file-based exchange

5. **Agent Protocol** (`tools/evolution/agent_protocol.py`)
   - Multi-agent network
   - Message passing
   - Agent discovery

6. **New MCP Tools** (extend `tools/mcp_server.py`)
   - 10 new tools for evolution system control

7. **Scripts** (`scripts/`)
   - start_evolution.sh
   - stop_evolution.sh
   - install_service.sh

8. **Tests** (`tests/evolution/`)
   - Unit tests for all components
   - Integration tests
   - 80%+ coverage target

9. **Documentation** (`docs/EVOLUTION_SYSTEM.md`)
   - Comprehensive guide

### Integration Points

The task requires **extending** existing Context Foundry components:

1. **MCP Server Extension**
   - Add 10 new tools to `tools/mcp_server.py`
   - Integrate with existing delegation model

2. **Pattern Library Integration**
   - Evolution modes should read/write to `~/.context-foundry/patterns/`
   - Use existing pattern sharing infrastructure

3. **Delegation Model**
   - Use existing delegation infrastructure for task execution

4. **Project Registry**
   - Auto-register projects created by existing build system

### Files to Modify

**MODIFY (extend existing)**:
- `tools/mcp_server.py` - Add 10 new MCP tools at end of file

**CREATE (new files)**:
- `tools/evolution/__init__.py`
- `tools/evolution/daemon.py`
- `tools/evolution/task_queue.py`
- `tools/evolution/resource_manager.py`
- `tools/evolution/agent_protocol.py`
- `tools/evolution/modes/__init__.py`
- `tools/evolution/modes/base_mode.py`
- `tools/evolution/modes/self_improvement.py`
- `tools/evolution/modes/chaos_creative.py`
- `tools/evolution/modes/research_discovery.py`
- `tools/evolution/communication/__init__.py`
- `tools/evolution/communication/local_exchange.py`
- `tools/evolution/communication/web_dashboard.py`
- `tools/evolution/communication/rest_api.py`
- `tools/evolution/communication/websocket_stream.py`
- `scripts/start_evolution.sh`
- `scripts/stop_evolution.sh`
- `scripts/install_service.sh`
- `tests/evolution/test_daemon.py`
- `tests/evolution/test_task_queue.py`
- `tests/evolution/test_modes.py`
- `tests/evolution/test_communication.py`
- `tests/evolution/test_agent_protocol.py`
- `docs/EVOLUTION_SYSTEM.md`

### Approach

1. **Create new evolution module** with all components
2. **Extend MCP server** with 10 new tools (non-breaking extension)
3. **Add comprehensive tests** (80%+ coverage target)
4. **Write complete documentation** (user guide + API reference)
5. **Create installation/management scripts**
6. **Create feature branch** for PR (since this modifies CF itself)

## Risks and Considerations

1. **SQLite Concurrency**: Need proper locking for multi-process access
2. **Daemon Safety**: Resource limits are critical (don't consume all CPU/memory)
3. **Breaking Changes**: Must extend MCP server without breaking existing tools
4. **Test Coverage**: Large surface area - need comprehensive tests
5. **Security**: Self-improvement mode modifies CF codebase - needs human approval (PR workflow)
6. **Complexity**: This is a large multi-component system (~2000+ lines of new code)

## Recommended Build Strategy

1. **Phase 1 (Scout)**: Research daemon patterns, FastAPI, SQLite best practices
2. **Phase 2 (Architect)**: Design detailed module architecture, API contracts
3. **Phase 2.5 (Parallel Build)**: Break into 6 parallel tasks:
   - Task 1: Core daemon + task queue
   - Task 2: Three evolution modes  
   - Task 3: Communication layer (dashboard + API)
   - Task 4: Agent protocol
   - Task 5: MCP tools extension
   - Task 6: Scripts and configuration
4. **Phase 4 (Test)**: Comprehensive unit + integration tests
5. **Phase 5 (Documentation)**: EVOLUTION_SYSTEM.md + API docs
6. **Phase 6 (Deploy)**: Create PR on feature branch (not auto-merge)

## Success Criteria

All 10 success criteria from task are achievable with existing CF infrastructure.
