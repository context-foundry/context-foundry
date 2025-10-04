# Context Foundry Roadmap

## Current Status: v1.0

Context Foundry currently supports building new projects from scratch with:
- ✅ Scout → Architect → Builder workflow
- ✅ Automated context management
- ✅ Pattern library learning
- ✅ Claude CLI authentication (in addition to API key)
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

### v1.1 - Claude CLI Support
- ✅ Claude CLI authentication backend
- ✅ Auto-detection of auth method
- ✅ Environment variable configuration
- ✅ Documentation updates

## Contributing

Want to help implement these features? Check out our [CONTRIBUTING.md](CONTRIBUTING.md) guide!

## Feedback

Have ideas for features not on this roadmap? Open an issue on GitHub:
https://github.com/snedea/context-foundry/issues

---

*Last Updated: 2025-10-04*
