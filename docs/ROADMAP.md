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

## Recently Completed

### v2.3.0 - Smart Incremental Builds Phase 2 (January 2025)
**Major Feature: 70-90% Speedup on Rebuilds**

Context Foundry now includes Phase 2 of Smart Incremental Builds, delivering dramatic performance improvements through advanced caching and change detection:

**✅ Global Scout Cache (Cross-Project Sharing)**
- ✅ Share Scout analysis across ALL projects (not just per-project)
- ✅ Location: `~/.context-foundry/global-cache/scout/`
- ✅ Cache key: Hash of (task + project_type + tech_stack)
- ✅ 7-day TTL with semantic similarity matching
- ✅ **Impact**: 80-95% faster Scout phase for similar projects

**✅ File-Level Change Detection**
- ✅ Track changes using git diff + SHA256 hashing
- ✅ Works with or without git repository
- ✅ Snapshot saved to `.context-foundry/last-build-snapshot.json`
- ✅ **Impact**: Enables selective rebuilds

**✅ Incremental Builder (Smart File Preservation)**
- ✅ Preserve unchanged files from previous build
- ✅ Dependency graph analysis (Python + JavaScript)
- ✅ Only rebuild files affected by changes + transitive dependencies
- ✅ Conservative approach: when in doubt, rebuild
- ✅ **Impact**: 85-95% faster for isolated changes

**✅ Test Impact Analysis (Selective Test Execution)**
- ✅ Map tests to source files they cover
- ✅ Only run tests affected by code changes
- ✅ Supports pytest (others planned)
- ✅ Fallback to full test suite if > 30% changed
- ✅ **Impact**: 60-80% faster Test phase

**✅ Incremental Documentation (Selective Doc Updates)**
- ✅ Only regenerate docs for changed modules
- ✅ Preserve screenshots for unchanged UI
- ✅ Update README sections selectively
- ✅ **Impact**: 90-95% faster for doc-only updates

**📊 Performance Impact**

| Change Type | Phase 1 Speedup | Phase 2 Speedup |
|-------------|----------------|----------------|
| Small code changes (1-3 files) | 10-20% | 70-90% |
| Documentation-only updates | 20-30% | 95% |
| Similar project (reuse Scout) | 15-25% | 50-70% |
| Full rebuild (no cache hits) | 0% | 0% |

**🏗️ Technical Implementation**
- `tools/incremental/global_scout_cache.py` - Cross-project Scout cache (220 lines)
- `tools/incremental/change_detector.py` - File-level change detection (280 lines)
- `tools/incremental/incremental_builder.py` - Smart file preservation (340 lines)
- `tools/incremental/test_impact_analyzer.py` - Test selection logic (280 lines)
- `tools/incremental/incremental_docs.py` - Documentation updates (220 lines)
- Updated `tools/cache/__init__.py` to export Phase 2 modules
- Added comprehensive configuration in `.env.example`
- 13 integration tests (all passing)

**✅ Testing & Validation**
- ✅ 13 integration tests covering all Phase 2 modules
- ✅ All tests passing (100% success rate)
- ✅ Backward compatible with Phase 1 cache
- ✅ Graceful degradation when features unavailable

**📚 Configuration**
All Phase 2 features configurable in `.env.example`:
```bash
INCREMENTAL_PHASE2_ENABLED=true
GLOBAL_SCOUT_CACHE_ENABLED=true
CHANGE_DETECTION_ENABLED=true
INCREMENTAL_BUILDER_ENABLED=true
TEST_IMPACT_ANALYSIS_ENABLED=true
INCREMENTAL_DOCS_ENABLED=true
```

**Key Insight:** Phase 2 transforms incremental builds from "nice to have" to "dramatic speedup." By combining global caching with intelligent change detection and selective rebuilds, Context Foundry now delivers 70-90% faster builds on repeated/similar tasks - making iterative development and CI/CD dramatically more efficient.

**GitHub Issue**: #11
**Completed:** January 13, 2025

---

## Planned Features

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

---

## 🔬 Foundation Sentinel Enhancements (Agent Feedback Analysis)

**Status:** Under Review (January 2025)

**Context:** External agent feedback proposed AWS Lambda/DynamoDB-based enhancements. This section documents what makes sense for Context Foundry's CLI-based architecture vs. what doesn't.

### ⚠️ **Architecture Mismatch Analysis**

The feedback assumed an **AWS serverless architecture** (Lambda, Step Functions, DynamoDB, CloudWatch), but Context Foundry is:
- A **CLI-based tool** using Claude Code CLI
- Uses **stateless conversation architecture** with file-based state
- Runs **locally or in GitHub Actions**, not on AWS infrastructure

**Key Insight:** We need to adapt the feedback to our architecture, not adopt AWS-specific solutions.

---

### ✅ **HIGH PRIORITY: Immediate Implementation**

#### 1. Pattern-Aware Self-Healing Loop
**What:** Wire existing pattern library into Tester/Architect agents during failures

**Why:** We're already collecting patterns in `.context-foundry/patterns/common-issues.json` but not actively using them during builds. This is low-hanging fruit with high impact.

**Implementation:**
- Modify Tester agent prompt to load matching patterns when tests fail
- Feed pattern matches to Architect with targeted remediation guidance
- Update orchestrator to pass pattern context between agents
- Add pattern matching logic based on error fingerprints

**Technical Details:**
```python
# In lambda/tester/handler.py (or equivalent):
def get_relevant_patterns(test_output):
    """Load patterns matching current failure"""
    patterns = load_patterns('.context-foundry/patterns/common-issues.json')
    matches = [p for p in patterns if p['fingerprint'] in test_output]
    return matches

# Inject into Architect prompt:
"""
Previous failures with similar patterns:
{matched_patterns}

Recommended approaches:
{pattern_solutions}
"""
```

**Expected Impact:**
- Faster iteration on known issues
- Reduced token usage (targeted fixes vs. trial-and-error)
- Self-improving system (patterns accumulate over time)

**Estimated Effort:** 2-3 days
**Priority:** ⭐⭐⭐⭐⭐ (Critical - unlocks pattern library value)

---

#### 2. Smart Log Summarization & Context Reduction
**What:** Pre-process logs/test output before feeding to agents to reduce token usage by 60-80%

**Why:** Context Foundry struggles with token usage. Smart filtering delivers immediate savings.

**Implementation:**
- Add pre-processing step before agent prompts
- Extract only: error messages, stack traces, failed test names, relevant lines
- Filter out: verbose logging, successful tests, build boilerplate
- Use structured extraction (regex, AST parsing for Python tracebacks)
- Save full logs to file, pass summary to agent

**Technical Details:**
```python
# tools/log_summarizer.py
def summarize_test_output(full_output):
    """Extract only relevant failure info"""
    summary = {
        'failed_tests': extract_failed_tests(full_output),
        'error_messages': extract_errors(full_output),
        'stack_traces': extract_stack_traces(full_output, max_depth=5),
        'relevant_code': extract_code_context(full_output)
    }

    # Full output saved to .context-foundry/logs/test-output.txt
    # Summary (10-20% of original) passed to agent
    return summary
```

**Expected Impact:**
- 60-80% reduction in token usage for test failures
- Faster agent responses (less to process)
- More targeted fixes (noise filtered out)

**Estimated Effort:** 3-4 days
**Priority:** ⭐⭐⭐⭐⭐ (Critical - immediate cost savings)

---

#### 3. Pre-Flight Code Validation (Guardrails)
**What:** Validate generated code BEFORE execution to catch obvious mistakes early

**Why:** Saves expensive test iterations on trivial errors (missing imports, syntax errors, markdown artifacts)

**Implementation:**
- Add validation step in Builder agent output processing
- AST parsing for syntax errors (Python: `ast.parse`, JS: esprima/acorn)
- Import validation (check all imports exist in dependencies)
- Markdown fence detection (catch ```python artifacts)
- Static analysis (pylint, ruff for Python; eslint for JS)
- Fail fast with clear error message to re-prompt Builder

**Technical Details:**
```python
# tools/code_validator.py
def validate_generated_code(file_path, language):
    """Pre-flight checks before execution"""
    issues = []

    # 1. Syntax check
    if language == 'python':
        try:
            ast.parse(open(file_path).read())
        except SyntaxError as e:
            issues.append(f"Syntax error: {e}")

    # 2. Import validation
    missing_imports = check_imports(file_path, language)
    if missing_imports:
        issues.append(f"Missing imports: {missing_imports}")

    # 3. Markdown artifacts
    if has_markdown_fences(file_path):
        issues.append("Code contains markdown fences (```)")

    # 4. Static analysis
    static_issues = run_linter(file_path, language)
    issues.extend(static_issues[:5])  # Top 5 only

    return issues

# In Builder output processing:
issues = validate_generated_code(file_path, language)
if issues:
    return {
        'status': 'validation_failed',
        'issues': issues,
        'action': 're-prompt Builder with specific fixes'
    }
```

**Expected Impact:**
- Catch 40-60% of common errors before test execution
- Faster iteration (skip expensive test runs)
- Better code quality (enforce standards early)

**Estimated Effort:** 4-5 days
**Priority:** ⭐⭐⭐⭐⭐ (Critical - prevents wasted iterations)

---

### ✅ **MEDIUM PRIORITY: Short-Term (Next Sprint)**

#### 4. Automated GitHub Issue Creation on Build Failures
**What:** File GitHub issue automatically when builds fail after max iterations

**Why:** Tracks failures, enables manual review, creates accountability

**Implementation:**
- Hook into build completion (success/failure status)
- On failure after max iterations, create GitHub issue
- Include: build ID, task description, pattern matches, test summary, log links
- Label: `build-failure`, `needs-triage`, `context-foundry`
- Assign to repository owner or team

**Technical Details:**
```bash
# In orchestrator or GitHub Agent:
gh issue create \
  --title "Build Failed: ${TASK_SUMMARY}" \
  --body "$(cat <<EOF
## Build Failure Report

**Build ID:** ${BUILD_ID}
**Task:** ${TASK}
**Mode:** ${MODE}
**Iterations:** ${ITERATION_COUNT}/${MAX_ITERATIONS}

### Failure Summary
${FAILURE_SUMMARY}

### Pattern Matches
${MATCHED_PATTERNS}

### Test Output (Last Iteration)
\`\`\`
${TEST_OUTPUT_SUMMARY}
\`\`\`

### Full Logs
${LOG_FILE_PATH}

### Next Steps
- [ ] Review failure context
- [ ] Check pattern library for similar issues
- [ ] Manual fix or adjust task requirements
- [ ] Update patterns with learnings

---
*Auto-generated by Context Foundry*
EOF
)" \
  --label "build-failure,needs-triage,context-foundry"
```

**Expected Impact:**
- Better failure tracking and accountability
- Pattern identification (recurring issues surface)
- Team collaboration on difficult builds

**Estimated Effort:** 1-2 days
**Priority:** ⭐⭐⭐⭐ (High value, easy to implement)

---

#### 5. CLI Command for Manual Context Injection
**What:** Allow users to inject hints/context into running or failed builds

**Why:** Sometimes the agent needs human guidance to unblock

**Implementation:**
```bash
# New CLI commands:
foundry inject-hint <build-id> "Try using asyncio instead of threading"
foundry inject-context <build-id> --file ./hint.md
foundry retry-with-hint <build-id> "Check the API documentation for rate limits"

# Stored in:
.context-foundry/builds/<build-id>/manual-context.json
```

**Technical Details:**
```python
# tools/mcp_server.py - new MCP tool
def inject_build_context(build_id: str, hint: str, context_file: Optional[str] = None):
    """Inject manual context into build for next iteration"""
    context = {
        'timestamp': datetime.now().isoformat(),
        'hint': hint,
        'context_file': context_file,
        'source': 'manual'
    }

    # Save to build directory
    context_path = f'.context-foundry/builds/{build_id}/manual-context.json'
    save_json(context_path, context)

    # Next Architect iteration reads this file
    return {'status': 'injected', 'path': context_path}
```

**Expected Impact:**
- Unblock difficult builds
- Preserve human expertise
- Hybrid AI-human workflow

**Estimated Effort:** 2-3 days
**Priority:** ⭐⭐⭐⭐ (High value for complex builds)

---

#### 6. Failure Fingerprinting & Classification
**What:** Categorize failures into types (syntax, import, logic, timeout, etc.) for better pattern matching

**Why:** Enables targeted remediation and better pattern library organization

**Implementation:**
```python
# tools/failure_classifier.py
def classify_failure(test_output, error_logs):
    """Classify failure into categories"""
    categories = []

    # Pattern matching on error signatures
    if 'ModuleNotFoundError' in error_logs:
        categories.append('missing_dependency')
    if 'SyntaxError' in error_logs:
        categories.append('syntax_error')
    if 'AssertionError' in test_output:
        categories.append('test_assertion_failed')
    if 'timeout' in test_output.lower():
        categories.append('timeout')
    if 'connection refused' in error_logs.lower():
        categories.append('service_unavailable')

    # Confidence scoring
    confidence = calculate_confidence(categories, error_logs)

    return {
        'categories': categories,
        'confidence': confidence,
        'fingerprint': generate_fingerprint(error_logs)
    }

# Used by pattern matcher and Architect
```

**Expected Impact:**
- Better pattern matching accuracy
- Targeted remediation strategies
- Organized pattern library

**Estimated Effort:** 3-4 days
**Priority:** ⭐⭐⭐⭐ (Enables better self-healing)

---

### ✅ **LOW PRIORITY: Long-Term (Nice to Have)**

#### 7. Local Metrics Database (SQLite)
**What:** Track build metrics, success rates, iteration counts, pattern effectiveness

**Why:** Data-driven insights, identify regressions, measure improvements

**Implementation:**
```python
# ~/.context-foundry/metrics.db (SQLite)
# Tables: builds, iterations, patterns_used, failures

# CLI commands:
foundry metrics --last 30 days
foundry metrics --pattern-effectiveness
foundry metrics --success-rate-by-project-type
```

**Estimated Effort:** 5-7 days
**Priority:** ⭐⭐⭐ (Good to have, not critical)

---

#### 8. Post-Incident Review Automation
**What:** Auto-generate markdown postmortem after build failures

**Why:** Enforce learning from failures, seed pattern library

**Implementation:**
```markdown
# Auto-generated: .context-foundry/postmortems/build-<id>.md

## Build Postmortem: <Task>

**Date:** 2025-01-29
**Build ID:** abc-123-def
**Status:** Failed
**Iterations:** 3/3

### What Happened
<AI-generated summary>

### Root Cause
<Classification and fingerprint>

### Patterns Matched
- Pattern #42: Async context manager issues

### Lessons Learned
<AI-extracted insights>

### Action Items
- [ ] Update pattern library with this case
- [ ] Add guardrail for this error type
- [ ] Document workaround

---
*Auto-generated by Context Foundry*
```

**Estimated Effort:** 3-4 days
**Priority:** ⭐⭐⭐ (Good practice, not urgent)

---

#### 9. GitHub Actions Dashboard (Observability)
**What:** Enhanced GitHub Actions summary pages with metrics, visualizations

**Why:** Better visibility into build health, trends over time

**Implementation:**
- Use GitHub Actions `$GITHUB_STEP_SUMMARY` for rich output
- Generate charts (success rate, iteration distribution)
- Link to pattern library hits
- Trend analysis over time

**Estimated Effort:** 4-5 days
**Priority:** ⭐⭐⭐ (Nice polish, not critical)

---

### ❌ **REJECTED: Wrong Architecture**

These features assume AWS infrastructure and don't align with Context Foundry's CLI-based design:

1. **DynamoDB persistence** - Use SQLite or enhanced JSON instead
2. **Lambda handlers** - We're a CLI tool, not a serverless API
3. **CloudWatch monitoring** - Use GitHub Actions artifacts or local logs
4. **EventBridge triggers** - Use GitHub Actions workflows
5. **Step Functions** - We use sequential agent orchestration
6. **REST API endpoints** - CLI commands instead

---

### 📊 **Implementation Priority Summary**

**Phase 1: Quick Wins (1-2 weeks)**
1. ⭐⭐⭐⭐⭐ Pattern-aware self-healing
2. ⭐⭐⭐⭐⭐ Smart log summarization
3. ⭐⭐⭐⭐⭐ Pre-flight validation

**Phase 2: High Value Features (2-3 weeks)**
4. ⭐⭐⭐⭐ Auto-create GitHub issues on failure
5. ⭐⭐⭐⭐ Manual context injection CLI
6. ⭐⭐⭐⭐ Failure classification system

**Phase 3: Polish & Metrics (Later)**
7. ⭐⭐⭐ Local metrics database
8. ⭐⭐⭐ Post-incident review automation
9. ⭐⭐⭐ GitHub Actions dashboard

---

### 🎯 **Success Metrics**

After Phase 1 implementation, we should see:
- **60-80% reduction** in token usage for failing builds
- **40-60% fewer** trivial errors reaching test phase
- **30-50% faster** iteration on known failure patterns
- **Better pattern library utilization** (currently collected but underused)

---

### 🤝 **Adapted AWS Concepts**

| AWS Concept | Context Foundry Adaptation |
|-------------|---------------------------|
| DynamoDB | SQLite (`~/.context-foundry/metrics.db`) |
| Lambda Functions | CLI commands + Python scripts |
| CloudWatch Logs | Local logs + GitHub Actions artifacts |
| EventBridge | GitHub Actions workflow triggers |
| Step Functions | Sequential agent orchestration |
| REST API | CLI interface (`foundry <command>`) |
| SNS/SQS | File-based state management |

**Key Insight:** We can adopt the *concepts* (monitoring, structured knowledge, guardrails, failure tracking) without adopting the *AWS infrastructure*. Context Foundry's strength is simplicity - local execution, file-based state, GitHub integration. Let's enhance that, not replace it.

---

**Analysis Date:** January 29, 2025
**Feedback Source:** External agent architecture review
**Status:** Recommendations accepted, implementation roadmap created

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

### v1.2 - MCP Server Mode (Released October 2025)
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

### v2.1.0 - Enhancement Mode (Released October 2025)
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

### v2.2.0 - GitHub Agent (Released October 2025)
**Major Feature: Comprehensive GitHub Integration & Automation**

Context Foundry now sets up complete GitHub project infrastructure automatically:

**✅ Phase 7.5: GitHub Integration Agent**
- ✅ Dedicated GitHub agent with specialized prompt
- ✅ Intelligent project type detection
- ✅ Autonomous GitHub configuration
- ✅ Full CI/CD workflow generation
- ✅ Professional project setup from day 1

**✅ Issue Tracking & Project Management**
- ✅ Automatic issue creation from Scout reports
- ✅ Issue-commit-PR linking
- ✅ Issue closure on completion
- ✅ Standard labels for project organization
- ✅ Issue/PR templates for collaboration

**✅ CI/CD Automation (GitHub Actions)**
- ✅ Test workflow generation (automatic)
- ✅ Deployment workflow for web apps (GitHub Pages)
- ✅ Docker build & publish workflow (GHCR)
- ✅ Context-aware workflow creation based on project type
- ✅ Branch protection rules for new projects

**✅ Release Management**
- ✅ Automatic version detection from package files
- ✅ Git tag creation and push
- ✅ GitHub release with generated changelog
- ✅ Test results and build metadata in release notes
- ✅ Links to documentation and artifacts

**✅ Deployment Integration**
- ✅ GitHub Pages auto-setup for web applications
- ✅ Live demo link added to README
- ✅ Automatic deployment on push to main
- ✅ Multi-platform Docker builds (if applicable)

**✅ Enhancement Mode Integration**
- ✅ Draft PR creation for tracking progress
- ✅ PR updates as build progresses
- ✅ Automatic PR readiness marking
- ✅ Issue-PR linking with "Closes #N"

**🏗️ Technical Implementation**
- `tools/github_agent_prompt.txt` - Comprehensive agent instructions (800+ lines)
  - Phase 1: Project type detection (web app, CLI, API, library, container)
  - Phase 2: Issue creation and tracking
  - Phase 3: Labels and templates
  - Phase 4: CI/CD workflows (test, deploy, docker)
  - Phase 5: Release creation with changelog
  - Phase 6: GitHub Pages setup
  - Phase 7: Branch protection
  - Phase 8: Issue updates and closure
- `tools/orchestrator_prompt.txt` - Phase 7.5 integration (lines 1736-1849)
- `docs/SESSION_SUMMARY_SCHEMA.md` - Extended schema with GitHub metadata
- `docs/GITHUB_AGENT_PROPOSAL.md` - Complete feature specification

**📊 Session Summary Schema v2.0**
New `github` metadata object includes:
```json
{
  "github": {
    "issue_number": 1,
    "issue_url": "https://github.com/owner/repo/issues/1",
    "release_version": "1.0.0",
    "release_url": "https://github.com/owner/repo/releases/tag/v1.0.0",
    "pages_url": "https://owner.github.io/repo",
    "workflows_created": true,
    "actions_url": "https://github.com/owner/repo/actions",
    "branch_protection_enabled": true
  }
}
```

**🎯 What Users Get Automatically**

**For New Projects:**
1. 🎫 Tracking issue created with Scout report
2. ⚙️ GitHub Actions CI/CD workflows
3. 🏷️ Standard labels (context-foundry, autonomous-build, etc.)
4. 📋 Issue/PR templates for collaboration
5. 📦 GitHub release with changelog
6. 🌐 GitHub Pages deployment (web apps)
7. 🔒 Branch protection on main
8. 📚 Professional README with badges and links

**For Enhancements:**
1. 🎫 Tracking issue for the fix/feature
2. 🔀 Draft PR with progress tracking
3. 🔗 Issue-PR-commit linking
4. ✅ Automatic PR readiness marking
5. 📝 Test results in PR description

**📈 Benefits**
- **Professional Setup**: Projects look mature from day 1
- **Full Automation**: CI/CD runs automatically on every push
- **Better Tracking**: Complete audit trail (Issue → PR → Release)
- **Easy Deployment**: GitHub Pages live immediately
- **Collaboration Ready**: Templates and guidelines in place
- **Showcase Quality**: Autonomous builds are deployment-ready

**🎓 Design Decisions**
1. **Dedicated Agent**: Sophisticated decision-making based on project type
2. **Intelligent Detection**: Reads Scout/Architect context to customize setup
3. **Graceful Degradation**: Optional features don't block build completion
4. **Context-Aware**: Different workflows for web apps vs APIs vs libraries
5. **Enhancement-Friendly**: Respects existing project settings
6. **Error Resilient**: Continues on non-critical failures

**📝 Example: Web App Build**

Before GitHub Agent:
```
✅ Code written → ✅ Tests pass → ✅ Pushed to GitHub → Done
```

After GitHub Agent:
```
✅ Code written → ✅ Tests pass → ✅ Pushed to GitHub
  ↓
✅ Issue #1 created
✅ CI workflow configured (test + deploy)
✅ GitHub Pages enabled
✅ Release v1.0.0 created with changelog
✅ Issue #1 closed with summary
✅ Live demo: https://user.github.io/app
✅ Professional project ready for collaboration
```

**Key Insight:** The GitHub Agent elevates Context Foundry builds from "code pushed to GitHub" to "fully automated, deployment-ready, professionally managed projects." Every build now includes comprehensive CI/CD, release management, and collaboration infrastructure - no manual setup required.

**Completed:** October 24, 2025

## Contributing

Want to help implement these features? Check out our [CONTRIBUTING.md](CONTRIBUTING.md) guide!

## Feedback

Have ideas for features not on this roadmap? Open an issue on GitHub:
https://github.com/snedea/context-foundry/issues

---

*Last Updated: 2025-10-29*
