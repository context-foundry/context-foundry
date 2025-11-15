# Context Foundry Build Modes

Context Foundry supports 6 distinct build modes that control how the autonomous build pipeline behaves. The mode is automatically detected from your task description, or you can specify it explicitly.

## Mode Overview

| Mode | Use Case | Codebase Analysis | Branch Pattern | Auto-Detect Keywords |
|------|----------|-------------------|----------------|---------------------|
| **new_project** | Create from scratch | ❌ Skipped | N/A (new repo) | Default fallback |
| **fix_bug** | Fix bugs/errors | ✅ Runs | `bugfix/` | fix, bug, issue, error, broken, repair |
| **add_feature** | Add functionality | ✅ Runs | `feature/` | add, enhance, improve, implement |
| **upgrade_deps** | Update packages | ✅ Runs | `upgrade/` | upgrade, update deps, migrate to |
| **refactor** | Restructure code | ✅ Runs | `refactor/` | refactor, restructure, reorganize, clean up |
| **add_tests** | Add test coverage | ✅ Runs | `test/` | add tests, write tests, test coverage |

## Mode Details

### 1. new_project

**When to use**: Building a completely new project from scratch

**Behavior**:
- Skips Codebase Analysis phase (Phase 0)
- Creates new Git repository
- Full pipeline: Scout → Architect → Builder → Test → Deploy
- Sets up project structure from scratch
- Initializes README, dependencies, and configuration

**Example tasks**:
```
"Create a real-time chat application with WebSocket support"
"Build a REST API for managing tasks with PostgreSQL"
```

**Explicit usage**:
```python
autonomous_build_and_deploy(
    task="Build a web scraper",
    working_directory="/path/to/project",
    mode="new_project"
)
```

---

### 2. fix_bug

**When to use**: Fixing bugs, errors, or broken functionality

**Behavior**:
- **Phase 0**: Analyzes existing codebase
- Creates feature branch: `bugfix/descriptive-name`
- Focuses on minimal changes to fix the issue
- Includes regression tests
- Creates PR with bug fix description

**Example tasks**:
```
"Fix the authentication timeout error in login.py"
"Repair the broken CSV export functionality"
"Debug the memory leak in the background worker"
```

**Auto-detected keywords**: fix, bug, issue, error, broken, repair

**Explicit usage**:
```python
autonomous_build_and_deploy(
    task="Fix database connection pooling issue",
    working_directory="/path/to/existing-project",
    mode="fix_bug"
)
```

---

### 3. add_feature

**When to use**: Adding new features or enhancing existing functionality

**Behavior**:
- **Phase 0**: Analyzes existing codebase architecture
- Creates feature branch: `feature/descriptive-name`
- Integrates with existing code patterns
- Adds comprehensive tests for new functionality
- Updates documentation
- Creates PR with feature description

**Example tasks**:
```
"Add OAuth2 authentication support"
"Implement dark mode toggle for the UI"
"Create export to PDF functionality"
```

**Auto-detected keywords**: add, enhance, improve, implement, create feature, new feature

**Explicit usage**:
```python
autonomous_build_and_deploy(
    task="Add real-time notifications with WebSocket",
    working_directory="/path/to/existing-project",
    mode="add_feature"
)
```

---

### 4. upgrade_deps

**When to use**: Updating dependencies, migrating to new versions, or upgrading frameworks

**Behavior**:
- **Phase 0**: Analyzes current dependency versions and compatibility
- Creates feature branch: `upgrade/descriptive-name`
- Updates package manifests (package.json, requirements.txt, etc.)
- Tests for breaking changes
- Updates code for API changes
- Verifies all tests pass

**Example tasks**:
```
"Upgrade to React 18 and fix breaking changes"
"Update all npm packages to latest versions"
"Migrate from Python 3.9 to Python 3.12"
```

**Auto-detected keywords**: upgrade, update dependencies, update deps, update packages, migrate to

**Explicit usage**:
```python
autonomous_build_and_deploy(
    task="Upgrade Django to version 5.0",
    working_directory="/path/to/existing-project",
    mode="upgrade_deps"
)
```

---

### 5. refactor

**When to use**: Restructuring code without changing functionality

**Behavior**:
- **Phase 0**: Analyzes code structure and identifies refactoring opportunities
- Creates feature branch: `refactor/descriptive-name`
- Maintains existing functionality (no behavior changes)
- Improves code organization, readability, or performance
- Ensures all existing tests still pass
- May add new tests to prevent regressions

**Example tasks**:
```
"Refactor the authentication module to use dependency injection"
"Reorganize components into feature-based folders"
"Clean up the database query layer and remove duplication"
```

**Auto-detected keywords**: refactor, restructure, reorganize, clean up

**Explicit usage**:
```python
autonomous_build_and_deploy(
    task="Refactor API routes to use middleware pattern",
    working_directory="/path/to/existing-project",
    mode="refactor"
)
```

---

### 6. add_tests

**When to use**: Adding test coverage to existing code

**Behavior**:
- **Phase 0**: Analyzes code coverage and identifies untested areas
- Creates feature branch: `test/descriptive-name`
- Adds unit tests, integration tests, or e2e tests
- Improves test coverage metrics
- May refactor code for better testability
- Documents test patterns

**Example tasks**:
```
"Add unit tests for the user authentication module"
"Write integration tests for the payment API"
"Increase test coverage to 80%"
```

**Auto-detected keywords**: add tests, write tests, test coverage, unit test

**Explicit usage**:
```python
autonomous_build_and_deploy(
    task="Add comprehensive tests for the shopping cart",
    working_directory="/path/to/existing-project",
    mode="add_tests"
)
```

---

## Auto-Detection

Context Foundry automatically detects the appropriate mode from your task description using keyword matching (see `tools/mcp_utils/task_classification.py`).

**Priority order**:
1. fix_bug (highest priority - if any fix/bug keywords found)
2. upgrade_deps
3. refactor
4. add_tests
5. add_feature
6. new_project (default fallback)

**Examples**:
```
"Fix the login bug" → fix_bug
"Add dark mode" → add_feature
"Upgrade to React 18" → upgrade_deps
"Refactor the API layer" → refactor
"Add tests for auth" → add_tests
"Build a todo app" → new_project
```

## Enhancement Modes (Modes 2-6)

All modes except `new_project` are considered "enhancement modes" and share common behavior:

### Phase 0: Codebase Analysis
Before Scout phase, enhancement modes run a Codebase Analysis phase that:
- Scans existing code structure
- Identifies dependencies and frameworks
- Detects project type (Python, Node.js, etc.)
- Maps architecture patterns
- Identifies areas affected by the task
- Creates `.context-foundry/codebase-analysis.md`

This analysis informs all subsequent phases about the existing codebase.

### Git Workflow
Enhancement modes follow a feature branch workflow:
1. Create feature branch from main
2. Make changes on feature branch
3. Commit changes with descriptive message
4. Push to remote
5. Create Pull Request (not auto-merged)

### Minimal Changes
Enhancement modes focus on targeted changes:
- Respect existing code patterns and style
- Minimize scope to the specific task
- Preserve existing functionality
- Add tests for changes
- Update documentation as needed

## Using Modes via MCP

When using the Context Foundry MCP server:

```python
# Auto-detected mode
result = mcp__context_foundry__autonomous_build_and_deploy(
    task="Fix the memory leak in worker.py",
    working_directory="/path/to/project"
)

# Explicit mode
result = mcp__context_foundry__autonomous_build_and_deploy(
    task="Improve the caching layer",
    working_directory="/path/to/project",
    mode="refactor"
)
```

## Using Modes via CF Daemon

When using `cfd` CLI or daemon:

```bash
# Auto-detected mode
cfd build "Fix authentication bug" /path/to/project

# Explicit mode (via config file or API)
cfd build "Update dependencies" /path/to/project --mode upgrade_deps
```

## Best Practices

### Choose the Right Mode

| Scenario | Recommended Mode | Reason |
|----------|-----------------|--------|
| Fixing a bug | `fix_bug` | Minimal changes, focused testing |
| Adding new functionality | `add_feature` | Integrated with existing architecture |
| Updating libraries | `upgrade_deps` | Handles breaking changes systematically |
| Improving code structure | `refactor` | Preserves functionality, improves maintainability |
| Improving test coverage | `add_tests` | Focuses on testing patterns and coverage |
| Starting fresh | `new_project` | No legacy constraints |

### Mode-Specific Tips

**fix_bug**:
- Be specific about the bug in your task description
- Include steps to reproduce if known
- Mention any error messages

**add_feature**:
- Describe the feature clearly
- Mention integration points if known
- Specify any UI/UX requirements

**upgrade_deps**:
- Specify target versions if known
- Mention any known breaking changes
- Consider gradual upgrades for major versions

**refactor**:
- Describe what needs improvement
- Mention any performance goals
- Specify if code style should change

**add_tests**:
- Specify coverage targets if known
- Mention specific modules to test
- Indicate test types (unit/integration/e2e)

## See Also

- [Getting Started Guide](GETTING_STARTED.md)
- [Phase Process Documentation](PHASE_PROCESS_SPAWNING_DESIGN.md)
- [FAQ](FAQ.md)
- [Changelog](../CHANGELOG.md) - v2.1.0 Enhancement Mode Release
