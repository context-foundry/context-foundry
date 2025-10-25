# Codebase Analysis Report

## Project Overview
- Type: Python MCP Server + Autonomous Build System
- Languages: Python 3.10+
- Architecture: FastMCP server that spawns Claude Code instances recursively for autonomous software builds
- Current Version: v2.1.0 (MCP-based, v2.0+ architecture)

## Key Files
- Entry point: `tools/mcp_server.py` (FastMCP server)
- Main orchestrator: `tools/orchestrator_prompt.txt` (63KB prompt for autonomous builds)
- Config: `requirements.txt`, `requirements-mcp.txt`, `.mcp.json`
- Tests: `tests/` directory
- Documentation: `README.md`, `docs/` directory

## Project Structure
```
context-foundry/
├── tools/
│   ├── mcp_server.py          # FastMCP server - spawns Claude instances
│   ├── orchestrator_prompt.txt # Main autonomous build workflow (Scout→Test→Deploy)
│   ├── builder_task_prompt.txt # Parallel builder agent prompts
│   ├── test_task_prompt.txt   # Parallel test agent prompts
│   ├── github_agent_prompt.txt # GitHub integration agent
│   ├── banner.py              # CLI banner
│   ├── config_manager.py      # Configuration management
│   ├── livestream/            # Real-time monitoring (websocket, metrics)
│   └── tui/                   # Terminal UI dashboard
├── docs/                      # Comprehensive documentation
├── tests/                     # Test suite
├── examples/                  # Example projects
└── scripts/                   # Utility scripts
```

## Dependencies
**Core:**
- anthropic>=0.40.0 (Claude API)
- fastmcp (MCP server framework)
- click, rich (CLI)

**Pattern Library:**
- sentence-transformers (semantic search)
- numpy, pyyaml

**Monitoring:**
- watchdog (filesystem events)
- requests, beautifulsoup4 (pricing data)

## Code to Modify
**Task**: Integrate BAML for improved LLM reliability and structured outputs

**Files to change:**
1. `tools/orchestrator_prompt.txt` - May recommend BAML to generated projects
2. `tools/mcp_server.py` - Could use BAML for structured phase tracking
3. `requirements.txt` - Add BAML dependency
4. `docs/` - Add BAML integration documentation

**Approach**: 
1. Research BAML library capabilities deeply
2. Identify integration points:
   - Scout/Architect/Builder agents: Use BAML for structured responses?
   - Phase tracking: Use BAML types instead of JSON?
   - Projects Context Foundry generates: Should they use BAML?
3. Design BAML integration strategy
4. Implement where it adds value (prioritize orchestrator reliability)
5. Add tests for BAML integration
6. Document BAML usage

## Architecture Notes
- **Meta-MCP Innovation**: Uses MCP to recursively spawn Claude Code instances
- **Self-healing**: Test loop (up to 3 iterations) with Architect→Builder→Test cycle
- **Parallel execution**: Spawns multiple builder/test agents concurrently
- **Phase tracking**: JSON files in `.context-foundry/` directory
- **Pattern library**: Self-learning system stores patterns globally at `~/.context-foundry/patterns/`

## Risks
1. **Scope creep**: BAML is a large library - need focused integration plan
2. **Backward compatibility**: Must not break existing orchestrator workflow
3. **Dependency weight**: BAML adds complexity - ensure value justifies cost
4. **Learning curve**: Team needs to understand BAML patterns
5. **Version compatibility**: BAML is actively developed - pin versions carefully

## Integration Opportunities
**High Value:**
- Phase tracking with BAML types (replace JSON parsing)
- Structured Scout/Architect outputs (eliminate parsing errors)
- Type-safe configuration (replace dict-based configs)

**Medium Value:**
- Projects Context Foundry generates could use BAML
- Semantic streaming for real-time progress updates
- Observability integration

**Lower Priority:**
- Suspension feature (builds are relatively fast already)
- Full orchestrator rewrite (works well, high risk)

## Current Branch Status
- On branch: `enhancement/multi-agent-monitoring-dashboard`
- Git clean: No (current-phase.json modified, safe to ignore)
- Recent work: Livestream monitoring dashboard, GitHub agent, prompt optimization
