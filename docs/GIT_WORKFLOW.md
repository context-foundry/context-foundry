# Git Workflow Reference

Quick reference for daily development workflow in Context Foundry.

## Table of Contents
- [Daily Pre-Work Checklist](#daily-pre-work-checklist)
- [Bug Fix Workflow](#bug-fix-workflow)
- [Feature Development Workflow](#feature-development-workflow)
- [Common Commands](#common-commands)
- [Troubleshooting](#troubleshooting)

---

## Daily Pre-Work Checklist

**Before starting ANY work:**

```bash
# 1. Check sync status
gitsync

# 2. Pull if needed
git pull

# 3. Verify you're on main
git branch
```

**Expected output from gitsync when in sync:**
```
## main...origin/main
```

**If you see commits listed, you're behind:**
```bash
git pull
```

---

## Bug Fix Workflow

### 1. Start Fresh

```bash
# Sync with remote
gitsync
git pull

# Create bug fix branch
git checkout -b fix/descriptive-name
# Examples:
#   git checkout -b fix/authentication-timeout
#   git checkout -b issue-42-memory-leak
```

### 2. Make Changes

```bash
# Work on your fix
# Edit files, test, etc.

# Check what changed
git status
git diff

# Stage specific files
git add path/to/file.py

# Or stage all changes
git add .
```

### 3. Commit

```bash
# Commit with clear message
git commit -m "fix: Clear description of what you fixed"

# Examples:
#   git commit -m "fix: Resolve authentication timeout on slow connections"
#   git commit -m "fix: Memory leak in pattern merge process"
```

### 4. Push and Create PR

```bash
# Push your branch
git push -u origin fix/descriptive-name

# Create pull request
gh pr create --title "Fix: Bug description" --body "
## Summary
Brief description of the fix

## Test plan
How you tested this

## Related issues
Fixes #123
"
```

---

## Feature Development Workflow

### 1. Start Fresh

```bash
# Sync and pull
gitsync
git pull

# Create feature branch
git checkout -b feat/feature-name
# Examples:
#   git checkout -b feat/parallel-testing
#   git checkout -b feat/github-integration
```

### 2. Develop

```bash
# Make changes, commit frequently
git add <files>
git commit -m "feat: Add initial structure"
git commit -m "feat: Implement core logic"
git commit -m "test: Add unit tests"

# Push regularly to backup work
git push -u origin feat/feature-name
git push  # After first push with -u
```

### 3. Create PR

```bash
gh pr create --title "Feature: Name" --body "
## Summary
What this adds

## Test plan
How to test it

## Screenshots/Examples
If applicable
"
```

---

## Common Commands

### Sync Check (Use This Often!)

```bash
gitsync
```

Shows:
- Current branch
- How many commits ahead/behind
- Working tree status

### Branch Management

```bash
# List all branches
git branch -a

# Switch branches
git checkout main
git checkout feat/my-feature

# Delete local branch (after merged)
git branch -d fix/old-bug

# Delete remote branch
git push origin --delete fix/old-bug
```

### Viewing History

```bash
# Recent commits
git log --oneline -10

# What changed in a commit
git show <commit-hash>

# Compare branches
git diff main..feat/my-feature
```

### Undoing Changes

```bash
# Discard unstaged changes to a file
git checkout -- path/to/file

# Unstage a file (keep changes)
git reset HEAD path/to/file

# Undo last commit (keep changes)
git reset --soft HEAD~1

# Undo last commit (discard changes) ⚠️ DANGEROUS
git reset --hard HEAD~1
```

### Stashing (Save Work Temporarily)

```bash
# Save current work
git stash

# List stashes
git stash list

# Apply most recent stash
git stash pop

# Apply specific stash
git stash apply stash@{0}
```

---

## Troubleshooting

### "Your branch is behind 'origin/main'"

```bash
git pull
```

### "Your branch is ahead of 'origin/main'"

```bash
# Push your commits
git push
```

### Merge Conflicts

```bash
# After git pull shows conflicts:
# 1. Open conflicted files
# 2. Look for <<<<<<< HEAD markers
# 3. Edit to resolve
# 4. Stage resolved files
git add path/to/resolved-file
# 5. Complete merge
git commit
```

### Accidentally Committed to Main

```bash
# Move uncommitted changes to a new branch
git checkout -b fix/my-fix

# Or move last commit to a new branch
git branch fix/my-fix
git reset --hard HEAD~1
git checkout fix/my-fix
```

### Out of Sync Across Terminals

```bash
# On each terminal:
gitsync

# Pull on whichever is behind
git pull
```

---

## Commit Message Conventions

Use these prefixes for clarity:

- `fix:` - Bug fixes
- `feat:` - New features
- `docs:` - Documentation changes
- `test:` - Adding/updating tests
- `refactor:` - Code refactoring
- `perf:` - Performance improvements
- `chore:` - Maintenance tasks

**Examples:**
```
fix: Resolve memory leak in pattern merge
feat: Add parallel test execution
docs: Update workflow documentation
test: Add integration tests for GitHub agent
refactor: Simplify delegation model
```

---

## Quick Reference Card

```
┌─────────────────────────────────────────┐
│         BEFORE ANY WORK                 │
├─────────────────────────────────────────┤
│ gitsync                                 │
│ git pull                                │
│ git checkout -b fix/name OR feat/name   │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│         WHILE WORKING                   │
├─────────────────────────────────────────┤
│ git status      # Check changes         │
│ git diff        # Review changes        │
│ git add <file>  # Stage files           │
│ git commit -m "type: message"           │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│         FINISHING UP                    │
├─────────────────────────────────────────┤
│ git push -u origin branch-name          │
│ gh pr create --title "..." --body "..." │
└─────────────────────────────────────────┘
```

---

## Setup gitsync Alias

If you haven't already:

```bash
echo 'alias gitsync="git fetch origin && git log HEAD..origin/main --oneline --color=always && echo && git status -sb"' >> ~/.bashrc
source ~/.bashrc
```

Now you can run `gitsync` anytime to check sync status!
