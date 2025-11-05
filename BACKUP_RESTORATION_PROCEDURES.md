# Backup & Restoration Procedures

**Last Updated**: November 4, 2025
**Current Backup Tag**: `backup-pre-orchestrator-revamp-2025-11-04`
**Purpose**: Safety valve before major orchestrator script changes

---

## Quick Restoration (Emergency)

If you need to restore immediately:

```bash
# Navigate to repository
cd /Users/name/homelab/context-foundry

# Restore to backup point (creates detached HEAD)
git checkout backup-pre-orchestrator-revamp-2025-11-04

# OR restore to backup and create new branch
git checkout -b restore-from-backup backup-pre-orchestrator-revamp-2025-11-04
```

**Warning**: This creates a detached HEAD state. See "Safe Restoration Options" below for production workflows.

---

## Backup Details

### What's Included in This Backup

**Commit**: `2ecd4ac`
**Tag**: `backup-pre-orchestrator-revamp-2025-11-04`
**Date**: November 4, 2025

**Files Added** (5 new files, 2,633 insertions):
1. `extensions/flowise/BLOG_POST_CONFLICT_OF_INTEREST_FLOWISE_FLOW.md`
   - Complete 9,000-word tutorial for COI workflows
   - 18 screenshot locations
   - Production-ready guide

2. `extensions/flowise/templates/conflict-of-interest-spec.md`
   - 5-node architecture specification
   - State management schema
   - All 9 pattern prevention validations

3. `extensions/flowise/learning-management-system-spec.md`
   - LMS workflow specification
   - Personalized training recommendations

4. `extensions/flowise/prompts/HIL-NODE-TEMPLATE.json`
   - Drop-in Human-in-the-Loop templates
   - Fixed and Dynamic variants
   - Complete integration checklist

5. `extensions/flowise/BAML-VALUE-DEMONSTRATION.md`
   - BAML structured output demonstration
   - Pattern learning examples

**State Before Backup**:
- ✅ All Flowise HIL patterns documented
- ✅ Pattern #10 enforcement active
- ✅ 13 commits rebased on origin/main
- ✅ Favicon updates integrated
- ✅ All tests passing

---

## Safe Restoration Options

### Option 1: Temporary Inspection (Read-Only)

Use this to inspect the backup state without making changes:

```bash
# Checkout the backup tag (detached HEAD)
git checkout backup-pre-orchestrator-revamp-2025-11-04

# Inspect files, run tests, etc.
ls -la extensions/flowise/
cat orchestrator_prompt.txt

# Return to current state
git checkout main
```

**Use Case**: Verify backup contents, compare files, check configurations

### Option 2: Create Recovery Branch

Use this to work from the backup state without affecting main:

```bash
# Create new branch from backup tag
git checkout -b recovery-branch backup-pre-orchestrator-revamp-2025-11-04

# Now you can make changes, commit, etc.
# Your main branch is untouched

# If you want to merge recovery back to main:
git checkout main
git merge recovery-branch
```

**Use Case**: Test restoration, make fixes, experiment with rollback changes

### Option 3: Hard Reset to Backup (DESTRUCTIVE)

**⚠️ WARNING**: This permanently discards all commits after the backup point!

```bash
# First, create a safety branch of current state
git branch safety-current-state

# Verify you created the branch
git branch -v

# Hard reset main to backup point
git checkout main
git reset --hard backup-pre-orchestrator-revamp-2025-11-04

# Force push to GitHub (if needed)
git push --force origin main
```

**Use Case**: Complete rollback when orchestrator changes broke everything

**Recovery from Hard Reset**:
```bash
# If you regret the hard reset, restore from safety branch
git reset --hard safety-current-state
git push --force origin main
```

### Option 4: Cherry-Pick Specific Commits

Use this to restore only specific files or commits:

```bash
# Stay on main branch
git checkout main

# Restore a specific file from backup
git checkout backup-pre-orchestrator-revamp-2025-11-04 -- extensions/flowise/prompts/HIL-NODE-TEMPLATE.json

# Or cherry-pick a specific commit from backup
git cherry-pick <commit-hash>

# Commit the restoration
git commit -m "Restore HIL template from backup"
```

**Use Case**: Selective restoration when only certain files were affected

---

## Verification Procedures

After restoring, verify the backup state:

### 1. Check Git State

```bash
# Verify you're on the backup tag
git log -1 --oneline
# Should show: 2ecd4ac Add comprehensive Flowise documentation and HIL templates

# Verify tag is correct
git describe --tags
# Should show: backup-pre-orchestrator-revamp-2025-11-04

# Check for uncommitted changes
git status
# Should show: HEAD detached at backup-pre-orchestrator-revamp-2025-11-04
```

### 2. Verify Critical Files

```bash
# Check Flowise documentation exists
ls -lh extensions/flowise/BLOG_POST_CONFLICT_OF_INTEREST_FLOWISE_FLOW.md
# Should show: ~37KB file

# Check HIL template exists
ls -lh extensions/flowise/prompts/HIL-NODE-TEMPLATE.json
# Should show: ~13KB file

# Verify file count
find extensions/flowise -name "*.md" | wc -l
# Should show: 22 files

# Check orchestrator script (should be unmodified from this backup)
wc -l orchestrator_prompt.txt
# Should show: original line count before revamp
```

### 3. Run Tests

```bash
# Run Flowise extension tests
cd extensions/flowise
python3 -m unittest discover tests/

# Expected output:
# Ran XX tests in X.XXXs
# OK

# Run full Context Foundry tests (if needed)
cd ../..
pytest tests/ -v
```

### 4. Verify GitHub Sync

```bash
# Ensure backup tag exists on GitHub
git ls-remote --tags origin | grep backup-pre-orchestrator
# Should show: refs/tags/backup-pre-orchestrator-revamp-2025-11-04

# Check if local and remote match
git fetch origin
git diff HEAD origin/main
# Should show no diff if on latest backup
```

---

## Restoration Scenarios

### Scenario 1: Orchestrator Revamp Broke Everything

**Symptoms**:
- Context Foundry won't start
- Agents fail to execute
- BAML integration broken

**Solution**:
```bash
# Create safety branch of broken state (for debugging later)
git branch broken-orchestrator-attempt

# Hard reset to backup
git checkout main
git reset --hard backup-pre-orchestrator-revamp-2025-11-04

# Verify restoration
git log -1 --oneline
# Should show backup commit

# Test Context Foundry
cf build "test build"
```

### Scenario 2: Lost HIL Template Files

**Symptoms**:
- HIL-NODE-TEMPLATE.json missing
- Flowise builds fail without HIL patterns

**Solution**:
```bash
# Restore only the HIL template
git checkout backup-pre-orchestrator-revamp-2025-11-04 -- extensions/flowise/prompts/HIL-NODE-TEMPLATE.json

# Verify restoration
ls -lh extensions/flowise/prompts/HIL-NODE-TEMPLATE.json

# Commit the restoration
git add extensions/flowise/prompts/HIL-NODE-TEMPLATE.json
git commit -m "Restore HIL template from backup"
```

### Scenario 3: Need to Compare Current vs Backup

**Symptoms**:
- Want to see what changed after backup
- Need to audit orchestrator modifications

**Solution**:
```bash
# Compare current main to backup
git diff backup-pre-orchestrator-revamp-2025-11-04..main

# Compare specific file
git diff backup-pre-orchestrator-revamp-2025-11-04..main -- orchestrator_prompt.txt

# Show files changed since backup
git diff --name-only backup-pre-orchestrator-revamp-2025-11-04..main

# Show detailed stats
git diff --stat backup-pre-orchestrator-revamp-2025-11-04..main
```

### Scenario 4: Partial Rollback (Keep Some Changes)

**Symptoms**:
- Orchestrator changes failed
- But you want to keep Flowise documentation

**Solution**:
```bash
# Create recovery branch from backup
git checkout -b partial-recovery backup-pre-orchestrator-revamp-2025-11-04

# Cherry-pick specific commits you want to keep
git cherry-pick <commit-hash-of-good-change>

# Switch to main and merge
git checkout main
git merge partial-recovery

# Or use interactive rebase for fine-grained control
git rebase -i backup-pre-orchestrator-revamp-2025-11-04
```

---

## Backup Tag Management

### List All Backup Tags

```bash
# List all backup tags
git tag -l | grep backup

# Show backup tags with dates
git tag -l | grep backup | xargs -I {} git show {} --no-patch --format="%ci %s"

# Show backup tag details
git show backup-pre-orchestrator-revamp-2025-11-04 --no-patch
```

### Create New Backup Tag

```bash
# Before major changes, create a new backup tag
git tag -a backup-pre-<feature>-$(date +%Y-%m-%d) -m "Safety backup before <feature> changes

Created: $(date -u +%Y-%m-%dT%H:%M:%SZ)
Commit: $(git rev-parse HEAD)
"

# Push tag to GitHub
git push origin backup-pre-<feature>-$(date +%Y-%m-%d)
```

### Delete Old Backup Tags

```bash
# Delete local backup tag
git tag -d backup-pre-orchestrator-revamp-2025-11-04

# Delete remote backup tag (if needed)
git push origin :refs/tags/backup-pre-orchestrator-revamp-2025-11-04
```

---

## GitHub Recovery

If local repository is corrupted, restore from GitHub:

### Full Repository Restore

```bash
# Backup corrupted local repo (just in case)
mv /Users/name/homelab/context-foundry /Users/name/homelab/context-foundry.corrupted

# Clone fresh from GitHub
cd /Users/name/homelab
git clone https://github.com/context-foundry/context-foundry
cd context-foundry

# Checkout backup tag
git checkout backup-pre-orchestrator-revamp-2025-11-04

# Verify restoration
git log -1 --oneline
```

### Restore Specific Tag from Remote

```bash
# Fetch backup tag from GitHub
git fetch origin tag backup-pre-orchestrator-revamp-2025-11-04

# Checkout the tag
git checkout backup-pre-orchestrator-revamp-2025-11-04

# Create branch from tag if needed
git checkout -b restore-from-github backup-pre-orchestrator-revamp-2025-11-04
```

---

## Pre-Change Checklist

Before making major changes (like orchestrator revamp), always:

- [ ] Run `git status` - ensure working directory is clean
- [ ] Create commit with all current work
- [ ] Create annotated backup tag with descriptive name
- [ ] Push tag to GitHub: `git push origin <tag-name>`
- [ ] Verify tag on GitHub: check https://github.com/context-foundry/context-foundry/tags
- [ ] Document what the backup includes (this file)
- [ ] Test restoration on a separate branch
- [ ] Run full test suite before and after backup

---

## Post-Restoration Checklist

After restoring from backup:

- [ ] Verify git state: `git log -1 --oneline`
- [ ] Check critical files exist
- [ ] Run test suite: `python3 -m unittest discover tests/`
- [ ] Test Context Foundry: `cf build "test"`
- [ ] Verify Flowise extension: `python3 extensions/flowise/detector.py`
- [ ] Check GitHub sync: `git fetch origin && git diff HEAD origin/main`
- [ ] Document what was restored and why
- [ ] If on detached HEAD, create branch: `git checkout -b recovery-branch`
- [ ] Create new commit if changes made: `git commit -m "Restore from backup"`

---

## Emergency Contacts

If restoration fails or you need help:

1. **Check Git reflog**: `git reflog` shows all recent HEAD movements
2. **Check GitHub backup**: Tag exists remotely, can re-clone
3. **Check local backups**: Time Machine or other backup systems
4. **Context Foundry team**: GitHub issues for help

---

## Backup History

| Tag Name | Date | Commit | Purpose |
|----------|------|--------|---------|
| `backup-pre-orchestrator-revamp-2025-11-04` | 2025-11-04 | `2ecd4ac` | Pre-orchestrator script revamp |

**Future backups will be documented here.**

---

## Additional Resources

- **Git Documentation**: https://git-scm.com/docs
- **GitHub Tag Management**: https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository
- **Git Reflog Guide**: https://git-scm.com/docs/git-reflog
- **Context Foundry Docs**: https://github.com/context-foundry/context-foundry/wiki

---

**Created**: November 4, 2025
**Last Verified**: November 4, 2025
**Next Review**: Before next major change
