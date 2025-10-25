# CI/CD System for Context Foundry

This document describes the Continuous Integration and Continuous Deployment (CI/CD) infrastructure for Context Foundry.

## Overview

The CI/CD system provides automated testing, linting, and safety checks to ensure code quality and prevent regressions. It consists of three main components:

1. **Pre-commit Hooks** - Local checks before committing
2. **GitHub Actions** - Automated CI pipeline on push/PR
3. **Backup System** - Automated pattern backups

## Pre-commit Hooks

### Installation

```bash
# Install pre-commit tool
pip install pre-commit

# Install the hooks
cd ~/homelab/context-foundry
pre-commit install
```

### What It Does

Every time you run `git commit`, the following checks run automatically:

1. **Ruff Linter** - Checks Python code quality
2. **Ruff Formatter** - Auto-formats Python code
3. **Fast Tests** - Runs quick unit tests
4. **Debug Check** - Ensures no debug code (breakpoint, pdb)
5. **Large File Check** - Prevents committing files >500KB
6. **Trailing Whitespace** - Removes trailing spaces
7. **YAML/JSON Check** - Validates config files
8. **Private Key Detection** - Prevents committing secrets

### Manual Run

```bash
# Run all hooks on all files
pre-commit run --all-files

# Run specific hook
pre-commit run ruff-check --all-files

# Skip hooks (not recommended)
git commit --no-verify
```

### Configuration

Edit `.pre-commit-config.yaml` to customize hooks.

## GitHub Actions CI

### Triggers

CI pipeline runs on:
- Every push to `main` or `multi-agent-orchestration` branches
- Every pull request to `main`

### Jobs

#### 1. Lint (Code Quality)
- Runs Ruff linter on all Python files
- Checks code formatting
- **Status:** Must pass for merge

#### 2. Test (Functionality)
- Runs test suite on Python 3.10, 3.11, 3.12
- Generates code coverage report
- Uploads coverage to Codecov
- **Status:** Must pass for merge

#### 3. Security (Safety Checks)
- Runs Bandit security linter
- Checks for known vulnerabilities with Safety
- **Status:** Warning only (doesn't block merge)

#### 4. Integration (System Checks)
- Verifies MCP server can start
- Checks pattern system functions exist
- **Status:** Must pass for merge

#### 5. Build Status (Summary)
- Aggregates results from all jobs
- Reports overall success/failure
- **Status:** Final build indicator

### Viewing CI Results

1. Go to your GitHub repository
2. Click "Actions" tab
3. See status of recent workflow runs

### Badge

Add this badge to README.md to show CI status:

```markdown
![CI](https://github.com/snedea/context-foundry/workflows/CI%20Pipeline/badge.svg)
```

## Pattern Backup System

### Automatic Backups

The backup script (`scripts/backup_patterns.sh`) creates timestamped backups of all pattern files.

### Running Backups

```bash
# Manual backup
./scripts/backup_patterns.sh

# Backup before changes (recommended)
./scripts/backup_patterns.sh && git pull
```

### Backup Location

Backups are stored in:
```
~/.context-foundry/backups/
├── 20251019-100530/  # Timestamp: YYYYMMDD-HHMMSS
│   ├── common-issues.json
│   ├── scout-learnings.json
│   └── backup_info.txt
└── 20251019-143022/
```

### Retention Policy

- Automatically keeps last 10 backups
- Older backups are deleted automatically
- Each backup includes metadata file

### Restoring from Backup

```bash
# List available backups
ls -lh ~/.context-foundry/backups/

# Restore from specific backup
BACKUP_DIR=~/.context-foundry/backups/20251019-100530
cp -r $BACKUP_DIR/* ~/.context-foundry/patterns/

# Verify restoration
ls -lh ~/.context-foundry/patterns/
```

## Development Workflow

### Before Making Changes

```bash
# 1. Ensure you're up to date
git pull origin main

# 2. Create feature branch
git checkout -b feature/your-feature-name

# 3. Backup patterns (if modifying pattern system)
./scripts/backup_patterns.sh
```

### Making Changes

```bash
# 1. Make your code changes
vim mcp_server/server.py

# 2. Run tests locally
pytest tests/ -v

# 3. Commit (pre-commit hooks run automatically)
git add .
git commit -m "feat: your feature description"

# If hooks fail, fix issues and retry
# Hooks will auto-format some issues
```

### Pushing Changes

```bash
# 1. Push to your feature branch
git push origin feature/your-feature-name

# 2. GitHub Actions CI runs automatically
# 3. Check CI status on GitHub

# 4. Create pull request when CI passes
gh pr create --title "Your Feature" --body "Description"
```

## Troubleshooting

### Pre-commit Hooks Failing

**Problem:** Hooks fail on commit

**Solution:**
```bash
# See what failed
git commit -v

# Fix issues manually or let hooks auto-fix
git add -u
git commit -m "fix: address pre-commit issues"
```

### Tests Failing Locally

**Problem:** pytest fails

**Solution:**
```bash
# Run tests with verbose output
pytest tests/ -vv

# Run specific test
pytest tests/test_pattern_system.py::TestPatternDirectory -v

# Update dependencies
pip install -r requirements.txt --upgrade
```

### CI Failing on GitHub

**Problem:** GitHub Actions shows red X

**Solution:**
1. Click on the failed job
2. Read the error logs
3. Fix locally:
   ```bash
   # Run same checks locally
   pre-commit run --all-files
   pytest tests/ -v
   ```
4. Commit fix and push again

### Backup Script Errors

**Problem:** backup_patterns.sh fails

**Solution:**
```bash
# Check if patterns directory exists
ls -la ~/.context-foundry/patterns/

# Create if missing
mkdir -p ~/.context-foundry/patterns

# Check permissions
chmod +x scripts/backup_patterns.sh

# Run with verbose output
bash -x scripts/backup_patterns.sh
```

## Testing the CI/CD System

### Test Pre-commit Hooks

```bash
# Run all hooks
pre-commit run --all-files

# Expected: All hooks pass with green checkmarks
```

### Test Pytest Suite

```bash
# Run tests with coverage
pytest tests/ -v --cov=mcp_server

# Expected: All tests pass, coverage >80%
```

### Test Backup Script

```bash
# Run backup
./scripts/backup_patterns.sh

# Verify backup created
ls -lh ~/.context-foundry/backups/

# Expected: New backup directory with timestamp
```

### Test GitHub Actions (Local Simulation)

```bash
# Install act (GitHub Actions local runner)
brew install act  # macOS
# or
curl https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash

# Run CI locally
act -j test
```

## Best Practices

1. **Always run tests locally before pushing**
   ```bash
   pytest tests/ -v
   ```

2. **Use feature branches**
   ```bash
   git checkout -b feature/meaningful-name
   ```

3. **Backup before major changes**
   ```bash
   ./scripts/backup_patterns.sh
   ```

4. **Keep commits atomic and descriptive**
   ```bash
   git commit -m "feat: add global pattern reading"
   git commit -m "fix: handle missing pattern files"
   ```

5. **Review CI output even if it passes**
   - Check coverage reports
   - Review security warnings
   - Monitor test execution time

## Nightly Releases

### Automatic Nightly Builds

The nightly release workflow automatically creates pre-release builds every day at midnight UTC (00:00).

### How It Works

1. **Daily Schedule**: Runs automatically at 00:00 UTC
2. **Smart Commit Detection**:
   - Checks for new commits since the last nightly release
   - If no previous nightly exists, checks since the last stable release
   - Skips release if there are 0 new commits
   - Creates release if there are 1+ new commits
3. **Version Format**: `v2.1.0-nightly.YYYYMMDD` (base version + date)
4. **Release Notes**: Auto-generated and categorized by commit type:
   - 🚀 Features (`feat:` commits)
   - 🐛 Bug Fixes (`fix:` commits)
   - 📚 Documentation (`docs:` commits)
   - ♻️ Refactoring (`refactor:` commits)
   - 🔧 Maintenance (`chore:` commits)
   - 📝 Other Changes
5. **Pre-release**: Marked as pre-release (won't override "Latest" stable)
6. **Authentication**: Uses `GH_TOKEN` secret (personal access token with workflow permissions)

### Manual Trigger

You can manually trigger a nightly release from GitHub Actions:

```bash
# Via GitHub UI
1. Go to Actions tab
2. Select "Nightly Release" workflow
3. Click "Run workflow"
4. Optionally enable "Force release" to create one even without new commits

# Via GitHub CLI
gh workflow run nightly-release.yml
gh workflow run nightly-release.yml -f force=true  # Force release
```

### Using Nightly Releases

```bash
# Clone a specific nightly version
git clone --branch v2.1.0-nightly.20251025 https://github.com/context-foundry/context-foundry.git

# Or checkout if already cloned
git fetch --all --tags
git checkout v2.1.0-nightly.20251025

# List all nightly releases
gh release list --exclude-drafts | grep nightly
```

### Important Notes

- ⚠️ Nightly builds are unstable and intended for testing purposes only
- All commits pushed to `main` are automatically included in the next nightly
- Commits from any computer/contributor will be included
- Empty commits won't trigger a release (smart detection)
- Pre-releases won't interfere with stable release versioning
- Requires `GH_TOKEN` secret to be configured in repository settings

### Setup Requirements

The workflow requires a personal access token with `workflow` permissions:

1. **Create Personal Access Token**:
   - Go to GitHub Settings → Developer settings → Personal access tokens → Fine-grained tokens
   - Create token with `workflow` permission
   - Copy the token

2. **Add to Repository**:
   - Go to repository Settings → Secrets and variables → Actions
   - Create new secret named `GH_TOKEN`
   - Paste your personal access token

## Future Enhancements

Planned improvements to the CI/CD system:

- [ ] Automated deployments to PyPI on release tags
- [ ] Performance regression testing
- [ ] Integration tests with real Claude Code builds
- [ ] Automated changelog generation
- [ ] Dependency update bot (Dependabot)
- [ ] Docker image builds for CI

## References

- [Pre-commit Documentation](https://pre-commit.com/)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [pytest Documentation](https://docs.pytest.org/)
- [Ruff Documentation](https://docs.astral.sh/ruff/)

---

**Last Updated:** October 19, 2025
**Maintainer:** Claude Code Team
