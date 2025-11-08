# Evolution System: Merge Conflict Fix Plan

## Problem Summary

**Every Evolution PR is being created with merge conflicts in `tools/evolution/daemon.py`**

Current PR #41 status:
- Branch: `self-improvement/task-86029002`
- Status: OPEN with conflicts
- Conflicts: `tools/evolution/daemon.py`
- URL: https://github.com/context-foundry/context-foundry/pull/41

## Root Cause Analysis

### Why This Happens

1. **PR #41 was created from an outdated branch state:**
   - Base commits: 4fe0a16 → a24d772 → 596c5fa → ff30d78 → 914119b
   - These commits modified `daemon.py` extensively

2. **Main branch has evolved since PR creation:**
   - Main currently at: 596c5fa (race condition fix)
   - PR #41 branch diverged BEFORE the race condition fix was merged to main

3. **Conflict Pattern:**
   - Both main and PR #41 modified the same sections of `daemon.py`
   - Git cannot auto-merge because both branches changed overlapping code

### Why It Will Keep Happening

The daemon workflow currently:
1. Creates feature branch from current main
2. Spawns Claude to make changes
3. Claude commits and creates PR
4. **PROBLEM:** If main evolves while PR is open, next PR conflicts with pending PR

This creates a **cascading conflict problem** where each new PR conflicts with the previous one.

## Immediate Fix: Resolve PR #41

### For Human

#### Option 1: Merge PR #41 via Command Line (Recommended)

```bash
# 1. Fetch latest changes
cd /Users/name/homelab/context-foundry
git fetch origin

# 2. Checkout the PR branch
git checkout self-improvement/task-86029002
git pull origin self-improvement/task-86029002

# 3. Rebase onto latest main to resolve conflicts
git fetch origin main:main
git rebase main

# 4. Git will stop at conflicts - resolve them
# Open tools/evolution/daemon.py in your editor
# Look for conflict markers: <<<<<<< HEAD, =======, >>>>>>>

# 5. After resolving conflicts in your editor:
git add tools/evolution/daemon.py
git rebase --continue

# 6. Force push the rebased branch
git push origin self-improvement/task-86029002 --force

# 7. Merge the PR via GitHub UI
gh pr merge 41 --squash --delete-branch
```

#### Option 2: Use Claude Code to Resolve (Easier)

Start a new Claude Code session and paste this command:

```
Resolve merge conflicts for PR #41 in context-foundry repo.

1. Checkout branch: self-improvement/task-86029002
2. Rebase onto main
3. Resolve conflicts in tools/evolution/daemon.py by:
   - Keeping ALL race condition prevention code (the RUNNING state logic)
   - Keeping ALL PR detection code (_detect_prs_and_complete_tasks method)
   - Merging any new test coverage improvements from the PR
   - Ensuring no duplicate code or logic
4. Complete the rebase
5. Force push to origin
6. Verify PR #41 no longer has conflicts

Working directory: /Users/name/homelab/context-foundry
```

### For Claude Code (New Context Window)

**Prompt to paste into new Claude Code session:**

```
Working directory: /Users/name/homelab/context-foundry

Task: Resolve merge conflicts in PR #41 and prepare the Evolution System for conflict-free operation.

STEP 1: Resolve Current Conflicts
1. Read /Users/name/homelab/context-foundry/docs/EVOLUTION_MERGE_CONFLICT_FIX.md
2. Checkout branch: self-improvement/task-86029002
3. Fetch and rebase onto main: git fetch origin && git rebase origin/main
4. Resolve conflicts in tools/evolution/daemon.py:
   - Keep ALL race condition prevention code (RUNNING state management)
   - Keep ALL PR detection code (_detect_prs_and_complete_tasks)
   - Merge test coverage improvements from PR branch
   - Remove duplicate code sections
   - Ensure clean, conflict-free merge
5. Complete rebase: git add . && git rebase --continue
6. Force push: git push origin self-improvement/task-86029002 --force
7. Verify PR has no conflicts: gh pr view 41

STEP 2: Implement Long-term Fix (see below)
```

## Long-term Fix: Prevent Future Conflicts

### The Solution: Always Rebase Before Creating PR

Modify the daemon to ALWAYS rebase feature branches onto latest main before creating PRs.

### Files to Modify

#### 1. `tools/evolution/modes/self_improvement.py`

**Location:** Line ~390 in `_delegate_to_context_foundry` method

**Current Problem:**
```python
# Creates branch and makes changes, but doesn't rebase before PR creation
claude_prompt = f"""fix {prompt}"""
```

**Fix Required:**
Update the prompt to include rebase instructions:

```python
claude_prompt = f"""fix {prompt}

IMPORTANT WORKFLOW STEPS:
1. Fetch latest main: git fetch origin main
2. Rebase your branch onto main BEFORE creating PR: git rebase origin/main
3. Resolve any conflicts that arise
4. Only then create the PR

This ensures your PR is conflict-free and ready to merge."""
```

#### 2. Alternative: Create Rebase Script

**Create:** `tools/evolution/scripts/rebase_and_pr.sh`

```bash
#!/bin/bash
# Rebase feature branch onto main and create PR
set -e

BRANCH_NAME=$1
PR_TITLE=$2

echo "📡 Fetching latest main..."
git fetch origin main

echo "🔄 Rebasing $BRANCH_NAME onto main..."
git rebase origin/main

if [ $? -ne 0 ]; then
    echo "❌ Rebase conflicts detected - attempting auto-resolution..."
    # Try to auto-resolve by preferring our changes
    git checkout --ours tools/evolution/daemon.py
    git add tools/evolution/daemon.py
    git rebase --continue
fi

echo "✅ Rebase complete - branch is up to date with main"

echo "📤 Pushing branch..."
git push origin $BRANCH_NAME --force-with-lease

echo "🎯 Creating PR..."
gh pr create --title "$PR_TITLE" --body "Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"

echo "✅ PR created successfully!"
```

Then modify `self_improvement.py` to use this script:

```python
# Instead of letting Claude create PR directly, use our rebase script
claude_prompt = f"""fix {prompt}

Before creating PR:
1. Run: bash tools/evolution/scripts/rebase_and_pr.sh {branch_name} "{pr_title}"
   This will rebase onto main and create a conflict-free PR
"""
```

#### 3. Update Daemon PR Detection Logic

**Location:** `tools/evolution/daemon.py` - `_check_open_prs()` method

**Enhancement:** Add conflict detection to pause daemon if conflicts exist

```python
def _check_open_prs(self) -> List[Dict]:
    """Check for open Evolution PRs and detect conflicts"""
    try:
        result = subprocess.run(
            ['gh', 'pr', 'list', '--json', 'number,headRefName,mergeable'],
            capture_output=True, text=True, timeout=10
        )

        prs = json.loads(result.stdout)
        evolution_prs = []

        for pr in prs:
            branch = pr.get('headRefName', '')
            if any(branch.startswith(p) for p in ['self-improvement/', 'enhancement/', 'fix/']):
                # Check if PR has conflicts
                mergeable = pr.get('mergeable', 'UNKNOWN')
                if mergeable == 'CONFLICTING':
                    self.logger.warning(f"⚠️  PR #{pr['number']} has merge conflicts!")
                    self.logger.warning(f"   Branch: {branch}")
                    self.logger.warning(f"   Human intervention required to resolve conflicts")

                evolution_prs.append(pr)

        return evolution_prs

    except Exception as e:
        self.logger.error(f"Error checking PRs: {e}")
        return []
```

## Implementation Priority

### Phase 1: Immediate (Do Now)
1. ✅ Create this documentation file
2. 🔲 Resolve PR #41 conflicts (use Claude Code in new window)
3. 🔲 Merge PR #41 to unblock the daemon

### Phase 2: Short-term (Next Session)
1. 🔲 Implement rebase script (`tools/evolution/scripts/rebase_and_pr.sh`)
2. 🔲 Update `self_improvement.py` to use rebase script
3. 🔲 Test with one manual TODO fix
4. 🔲 Commit and merge the rebase prevention fix

### Phase 3: Medium-term (Future Enhancement)
1. 🔲 Add conflict detection to daemon PR monitoring
2. 🔲 Implement auto-rebase for existing PRs when conflicts detected
3. 🔲 Add metrics tracking: "PRs created vs PRs with conflicts"

## Testing Plan

### Test 1: Manual Rebase Test
```bash
# Create test branch
git checkout -b test-rebase-workflow
echo "# Test change" >> README.md
git commit -am "test: Verify rebase workflow"

# Simulate main moving forward
git checkout main
echo "# Main change" >> docs/test.md
git commit -am "chore: Main evolves"

# Rebase test branch
git checkout test-rebase-workflow
git rebase main
# Should complete cleanly

# Cleanup
git checkout main
git branch -D test-rebase-workflow
```

### Test 2: Daemon with Rebase Fix
1. Stop daemon
2. Apply rebase fix to `self_improvement.py`
3. Restart daemon
4. Wait for next PR creation
5. Verify PR has no conflicts
6. Merge PR
7. Verify next PR also has no conflicts

## Current System State

### Daemon Status
- **Running:** Yes (PID: 74127)
- **Status:** Paused, waiting for PR #41
- **Log:** `/tmp/daemon_both_fixes.log`

### Active PR
- **PR #41:** "Add comprehensive test coverage for critical paths"
- **Status:** OPEN with conflicts
- **Branch:** `self-improvement/task-86029002`
- **Conflicts:** `tools/evolution/daemon.py`

### Next Steps
1. Human or Claude Code: Resolve PR #41 conflicts
2. Merge PR #41
3. Daemon will auto-resume
4. Implement rebase prevention fix before next PR

## Success Criteria

✅ **Immediate Success:**
- PR #41 conflicts resolved
- PR #41 merged to main
- Daemon resumes operation

✅ **Long-term Success:**
- Next 5 PRs created WITHOUT conflicts
- All PRs merge cleanly
- No human intervention needed for conflict resolution

## References

- Current daemon: `/Users/name/homelab/context-foundry/tools/evolution/daemon.py`
- Self-improvement mode: `/Users/name/homelab/context-foundry/tools/evolution/modes/self_improvement.py`
- PR #41: https://github.com/context-foundry/context-foundry/pull/41
- Main branch state: commit 596c5fa

---

**Document Created:** 2025-11-08
**Status:** Ready for implementation
**Priority:** HIGH - Blocks autonomous operation
