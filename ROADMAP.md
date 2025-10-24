# Context Foundry Roadmap

## Current Status: v1.2

Context Foundry supports two execution modes:

**✅ MCP Mode (Terminal-Based MCP Server):**
- ✅ Fully implemented and functional
- ✅ Uses Anthropic API key (same as CLI mode)
- ✅ Terminal-based MCP server via `foundry serve`
- ⚠️ Future: Claude Desktop integration (would use subscription instead of API charges - blocked by sampling support)

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

**✅ MCP Mode (Terminal-Based - Claude Desktop Integration Pending)**
- ✅ MCP (Model Context Protocol) server implementation using FastMCP (complete and functional)
- ✅ Terminal-based MCP server works with API keys
- ⚠️ Future: Claude Desktop integration blocked by lack of sampling support (would use subscription instead of API charges)
- ✅ Three MCP tools implemented: `context_foundry_build`, `context_foundry_enhance`, `context_foundry_status`
- ✅ `foundry serve` command to start MCP server
- ⚠️ Tools return helpful error messages explaining current limitation
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

### v2.1.0 - Enhancement Mode (October 2025)
**Major Feature: Fix, Enhance, and Upgrade Existing Codebases**

Context Foundry can now intelligently modify existing projects instead of only building from scratch:

**✅ Multi-Mode Support**
- ✅ `new_project` - Build from scratch (original functionality)
- ✅ `fix_bug` - Fix bugs in existing code
- ✅ `add_feature` - Add features to existing code
- ✅ `upgrade_deps` - Upgrade dependencies
- ✅ `refactor` - Refactor existing code
- ✅ `add_tests` - Add tests to existing code

**✅ Intelligent Detection System**
- ✅ Automatic codebase detection (15+ project types supported)
  - Python (`requirements.txt`, `setup.py`, `pyproject.toml`)
  - Node.js (`package.json`, `tsconfig.json`)
  - Rust (`Cargo.toml`), Go (`go.mod`), Java (`pom.xml`)
  - Ruby (`Gemfile`), PHP (`composer.json`), .NET (`*.csproj`)
  - And more...
- ✅ Intent detection from natural language keywords
  - "fix" → `fix_bug`, "add" → `add_feature`, "upgrade" → `upgrade_deps`
- ✅ Auto-mode adjustment with conflict warnings
- ✅ Git repository status checking
- ✅ Confidence scoring (high/medium/low)

**✅ Phase 0: Codebase Analysis** (NEW!)
- ✅ Runs ONLY for enhancement modes (skipped for new projects)
- ✅ Analyzes project structure, architecture, and existing tests
- ✅ Reviews git history and current branch state
- ✅ Creates `codebase-analysis.md` report for context
- ✅ Provides full understanding before making changes

**✅ Enhancement-Aware Orchestrator**
- ✅ Scout phase: Mode-specific analysis strategies
  - Target ed bug finding for `fix_bug`
  - Integration point analysis for `add_feature`
  - Dependency impact assessment for `upgrade_deps`
- ✅ PHASE 2.5 (Parallel Builders): Targeted modifications
  - Modifies existing files instead of creating new projects
  - Preserves existing code structure and patterns
  - Creates feature branches before making changes
  - Groups changes by logical components
- ✅ Test phase: Validates existing functionality preserved
- ✅ Deploy phase: Feature branch + Pull Request workflow
  - Pushes to feature branch (NOT main)
  - Creates PR with detailed description
  - Links to GitHub issues (`Closes #N`)
  - Requires human review before merge

**✅ Testing & Validation**
- ✅ Standalone test script (`test_detection.py`)
- ✅ Live test: YouTube Transcript Summarizer enhancement
  - Added auto-save markdown feature
  - 21 new tests (all passing)
  - Created PR #2 on feature branch
  - Zero impact on existing functionality
  - Completed in ~12 minutes, 1 test iteration

**📊 Impact**
- 🎯 **Codebase Coverage**: Detects Python, JavaScript/TypeScript, Rust, Go, Java, Ruby, PHP, .NET, C/C++, and more
- 🚀 **Success Rate**: 100% on first live test (YouTube Transcript Summarizer)
- 📝 **Code Quality**: Professional PR workflow with detailed descriptions
- ⚡ **Efficiency**: Feature branches + PRs enable safe, reviewable changes

**🔧 Technical Implementation**
- `tools/mcp_server.py` (lines 768-1165): Detection and integration
  - `_detect_existing_codebase()` - 15+ project types
  - `_detect_task_intent()` - keyword-based mode detection
  - `autonomous_build_and_deploy()` - integrated detection and warnings
- `tools/orchestrator_prompt.txt`: Enhancement-aware phases
  - Mode detection section (lines 49-70)
  - Phase 0: Codebase Analysis (lines 71-175)
  - Scout enhancement guidance (lines 257-295)
  - PHASE 2.5 targeted modifications (lines 481-514)
  - Deploy PR workflow (lines 1237-1407)
- `test_detection.py`: Standalone validation script

**📚 Use Cases**
```python
# Fix a bug in existing codebase
autonomous_build_and_deploy(
    task="Fix the authentication bug in the login page",
    working_directory="/path/to/project",
    mode="fix_bug"  # Auto-detected from "fix" keyword
)

# Add a feature
autonomous_build_and_deploy(
    task="Add dark mode toggle to settings page",
    working_directory="/path/to/project",
    mode="add_feature"  # Auto-detected from "add" keyword
)

# Upgrade dependencies
autonomous_build_and_deploy(
    task="Upgrade all npm packages to latest versions",
    working_directory="/path/to/project",
    mode="upgrade_deps"  # Auto-detected from "upgrade" keyword
)
```

**Key Insight:** Enhancement mode transforms Context Foundry from a greenfield development tool into a comprehensive code evolution platform. It can now fix bugs, add features, upgrade dependencies, refactor code, and add tests to ANY existing project - whether built by Context Foundry or not.

**Completed:** October 24, 2025

## Contributing

Want to help implement these features? Check out our [CONTRIBUTING.md](CONTRIBUTING.md) guide!

## Feedback

Have ideas for features not on this roadmap? Open an issue on GitHub:
https://github.com/snedea/context-foundry/issues

---

*Last Updated: 2025-10-24*
