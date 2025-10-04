# Context Foundry Roadmap

## Current Status: v1.2

Context Foundry supports two execution modes:

**🆓 MCP Mode (Free):**
- ✅ Use through Claude Desktop without API charges
- ✅ Powered by your Claude Pro/Max subscription
- ✅ Interactive and conversational workflow

**💳 API Mode (Paid):**
- ✅ Standalone CLI for automation and CI/CD
- ✅ Direct Anthropic API access
- ✅ Traditional command-line operation

**Core Features (Both Modes):**
- ✅ Scout → Architect → Builder workflow
- ✅ Automated context management
- ✅ Pattern library learning
- ✅ Local git commits
- ✅ Human review checkpoints

## Planned Features


### 🚧 High Priority: Enhance Existing Projects

**Status:** Design Complete, Implementation Pending

**What:** Add `foundry enhance` command to modify existing codebases instead of building from scratch.

**Use Case:**
```bash
cd ~/my-existing-project
foundry enhance "Add JWT authentication to the API"
```

**Implementation Tasks:**
1. ✅ Add `mode` parameter to `AutonomousOrchestrator` ("new" vs "enhance")
2. ✅ Create `foundry enhance` CLI command stub
3. ✅ Update Scout prompts to handle existing codebases
4. ⏳ Implement codebase scanning in Scout phase
5. ⏳ Detect git repository and validate it's clean
6. ⏳ Make targeted file modifications instead of creating new projects
7. ⏳ Create feature branch automatically
8. ⏳ Push changes and create PR via `gh` CLI

**Estimated Completion:** Q1 2025

### 📋 Medium Priority: Pull Request Automation

**Status:** Planned

**What:** Automatically create PRs after successful builds/enhancements.

**Features:**
- Create branch from current branch
- Push changes to remote
- Generate PR description from SPEC and changes
- Use `gh pr create` for GitHub integration
- Support for other git platforms (GitLab, Bitbucket)

**Estimated Completion:** Q2 2025

### 🎯 Medium Priority: Better Codebase Understanding

**Status:** Research Phase

**What:** Enhanced Scout agent that deeply understands existing code.

**Features:**
- AST parsing for accurate code structure
- Dependency graph analysis
- Test coverage detection
- Architecture pattern recognition
- Integration with LSP for better code intelligence

**Estimated Completion:** Q2 2025

### 🎛️ Medium Priority: Temperature Control

**Status:** Planned

**What:** Add configurable temperature settings for more deterministic/creative outputs.

**Proposed Defaults:**
- Scout phase: 0.7 (allow creativity in architecture design)
- Architect phase: 0.5 (balanced - structured but flexible)
- Builder phase: 0.3 (deterministic code generation)

**Configuration:**
```bash
# In .env file
SCOUT_TEMPERATURE=0.7
ARCHITECT_TEMPERATURE=0.5
BUILDER_TEMPERATURE=0.3
```

**Benefits:**
- More consistent code generation
- Reduced hallucinations in Builder phase
- Allow creativity where it matters (Scout/Architect)
- User override for specific use cases

**Estimated Completion:** Q2 2025

### 🔧 Low Priority: Interactive Mode Improvements

**Status:** Ideas Phase

**What:** Better UX for review checkpoints.

**Ideas:**
- TUI (Text User Interface) for reviewing plans
- Side-by-side diff view for proposed changes
- Interactive task reordering
- Inline comments on specs/plans
- Better visualization of context usage

**Estimated Completion:** Q3 2025

### 🌐 Low Priority: Multi-Repo Support

**Status:** Ideas Phase

**What:** Handle changes across multiple repositories.

**Use Case:**
```bash
foundry enhance-multi "Add authentication" \
  --frontend ~/projects/web-app \
  --backend ~/projects/api-server
```

**Estimated Completion:** Q4 2025

## Completed Features

### v1.0 - Initial Release
- ✅ Three-phase workflow (Scout → Architect → Builder)
- ✅ Automated Context Engineering (ACE)
- ✅ Pattern library with semantic search
- ✅ Smart context compaction
- ✅ Interactive and autonomous modes
- ✅ Livestream dashboard
- ✅ Session analysis and metrics

### v1.1 - Authentication Improvements
- ✅ Attempted Claude CLI integration (later found to still use API)
- ✅ Auto-detection of auth method
- ✅ Environment variable configuration
- ✅ Documentation updates
- ⚠️ **Note:** Claude CLI mode removed in v1.2 - was misleading as it still charged API fees

### v1.2 - MCP Server Mode (October 2025)
**Major Feature: Dual-Mode Architecture**

Context Foundry now supports two execution modes, giving users flexibility based on their needs:

**🆓 MCP Mode (Free - No API Charges)**
- ✅ MCP (Model Context Protocol) server implementation using FastMCP
- ✅ Integration with Claude Desktop via MCP tools
- ✅ Uses Claude Pro/Max subscription instead of API calls
- ✅ Interactive development through Claude Desktop interface
- ✅ Three MCP tools: `context_foundry_build`, `context_foundry_enhance`, `context_foundry_status`
- ✅ `foundry serve` command to start MCP server
- ✅ Automatic configuration help with `--config-help`

**💳 API Mode (Continues to Work)**
- ✅ Standalone CLI operation via `foundry build`
- ✅ Direct Anthropic API integration
- ✅ Works with Python 3.9+
- ✅ Good for CI/CD and automation

**📦 Two-Tier Dependency Architecture**
- ✅ Base installation works with Python 3.9+ (`requirements.txt`)
- ✅ Optional MCP mode requires Python 3.10+ (`requirements-mcp.txt`)
- ✅ Graceful degradation - users only install what they need
- ✅ Clear error messages guiding users to correct setup

**🏗️ Technical Implementation**
- ✅ Created `ClaudeCodeClient` for MCP mode (mirrors `ClaudeClient` interface)
- ✅ Factory function `get_claude_client()` selects appropriate client
- ✅ MCP server with three tools for building, enhancing, and status checking
- ✅ Fixed package structure - added `__init__.py` to all package directories
- ✅ Removed misleading `claude_cli_integration.py`

**📚 Comprehensive Documentation**
- ✅ New `INSTALL.md` with installation guide, troubleshooting, and lessons learned
- ✅ New `docs/MCP_SETUP.md` with step-by-step MCP configuration
- ✅ Configuration template in `config/claude_desktop_config.example.json`
- ✅ Documented 8 key lessons learned from implementation
- ✅ Common issues section with 6 specific problems and solutions
- ✅ Verification checklists for both modes

**🎓 Lessons Learned**
1. Python version management is critical - two-tier architecture solves compatibility
2. Package structure matters - `find_packages()` requires `__init__.py` files
3. PATH management is non-trivial - document exactly where scripts install
4. Editable installs can be tricky - explicit Python version helps
5. Dependencies should be gradual - optional features = optional dependencies
6. Error messages should be helpful - guide users with exact commands
7. Documentation should match reality - write after debugging, not before
8. Two modes require two strategies - shared core with different clients

**Key Insight:** Users discovered that the original "Claude CLI" mode still charged API fees, leading to this comprehensive dual-mode implementation that provides true free usage via MCP while maintaining API mode for automation.

**Completed:** October 4, 2025

## Contributing

Want to help implement these features? Check out our [CONTRIBUTING.md](CONTRIBUTING.md) guide!

## Feedback

Have ideas for features not on this roadmap? Open an issue on GitHub:
https://github.com/snedea/context-foundry/issues

---

*Last Updated: 2025-10-04*
