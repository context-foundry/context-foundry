#!/bin/bash
# Rebase feature branch onto main before creating PR
# This prevents merge conflicts by ensuring branch is up-to-date
set -e

BRANCH_NAME="$1"

if [ -z "$BRANCH_NAME" ]; then
    echo "Usage: $0 <branch-name>"
    exit 1
fi

echo "🔄 Rebase Script: Ensuring branch '$BRANCH_NAME' is up-to-date with main"
echo ""

# Fetch latest main
echo "📡 Fetching latest main from origin..."
git fetch origin main

# Check if we're on the correct branch
CURRENT_BRANCH=$(git branch --show-current)
if [ "$CURRENT_BRANCH" != "$BRANCH_NAME" ]; then
    echo "⚠️  Warning: Current branch is '$CURRENT_BRANCH', expected '$BRANCH_NAME'"
    echo "   Checking out correct branch..."
    git checkout "$BRANCH_NAME"
fi

# Attempt rebase
echo ""
echo "🔄 Rebasing '$BRANCH_NAME' onto origin/main..."
if git rebase origin/main; then
    echo "✅ Rebase successful!"
else
    REBASE_EXIT_CODE=$?
    echo ""
    echo "❌ Rebase failed with conflicts"
    echo ""
    echo "CONFLICT RESOLUTION REQUIRED:"
    echo "1. Resolve conflicts in the affected files"
    echo "2. Stage resolved files: git add <file>"
    echo "3. Continue rebase: git rebase --continue"
    echo "4. Or abort rebase: git rebase --abort"
    echo ""
    exit $REBASE_EXIT_CODE
fi

# Push rebased branch
echo ""
echo "📤 Pushing rebased branch to origin..."
if git push origin "$BRANCH_NAME" --force-with-lease; then
    echo "✅ Branch pushed successfully!"
else
    echo ""
    echo "⚠️  Push failed - branch may have protection rules"
    echo "   Attempting regular push (merge-based update)..."

    # Reset to before rebase and try merge instead
    git rebase --abort 2>/dev/null || true
    git fetch origin "$BRANCH_NAME"
    git reset --hard "origin/$BRANCH_NAME"

    # Merge main instead of rebase
    echo "   Merging origin/main into branch..."
    if git merge origin/main -m "Merge main to resolve conflicts before PR"; then
        echo "✅ Merge successful!"
        git push origin "$BRANCH_NAME"
        echo "✅ Branch updated via merge instead of rebase"
    else
        echo "❌ Merge also failed - manual intervention required"
        exit 1
    fi
fi

echo ""
echo "✅ Branch '$BRANCH_NAME' is now up-to-date and ready for PR creation!"
echo ""
