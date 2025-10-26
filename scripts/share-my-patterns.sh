#!/bin/bash

#
# Context Foundry Pattern Sharing Script
#
# This script shares your locally-learned patterns with the global Context Foundry community.
# It creates a PR with your patterns, which will be automatically validated and merged.
#
# Usage:
#   ./scripts/share-my-patterns.sh
#
# Prerequisites:
#   - gh CLI installed and authenticated
#   - Git repository is clean (all changes committed)
#   - Python 3.10+ available
#

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOCAL_PATTERNS_DIR="$HOME/.context-foundry/patterns"
REPO_PATTERNS_DIR="$REPO_ROOT/.context-foundry/patterns"
MERGE_SCRIPT="$REPO_ROOT/scripts/merge-patterns-intelligent.py"
TEMP_DIR=$(mktemp -d)

# Get username for branch name
GH_USERNAME=$(gh api user -q .login 2>/dev/null || echo "user")
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BRANCH_NAME="patterns/${GH_USERNAME}/${TIMESTAMP}"

echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║  Context Foundry Pattern Sharing                      ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
echo ""

# ============================================================================
# Validation Checks
# ============================================================================

echo -e "${GREEN}🔍 Running pre-flight checks...${NC}"
echo ""

# Check if gh CLI is installed
if ! command -v gh &> /dev/null; then
    echo -e "${RED}❌ Error: GitHub CLI (gh) is not installed${NC}"
    echo ""
    echo "Install it from: https://cli.github.com/"
    exit 1
fi

# Check if gh is authenticated
if ! gh auth status &> /dev/null; then
    echo -e "${RED}❌ Error: GitHub CLI is not authenticated${NC}"
    echo ""
    echo "Run: gh auth login"
    exit 1
fi

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Error: Python 3 is not installed${NC}"
    exit 1
fi

# Check if local patterns directory exists
if [ ! -d "$LOCAL_PATTERNS_DIR" ]; then
    echo -e "${YELLOW}⚠️  Warning: No local patterns found at $LOCAL_PATTERNS_DIR${NC}"
    echo ""
    echo "This is normal if you haven't run any Context Foundry builds yet."
    echo "Run some builds first, then come back to share your learnings!"
    exit 0
fi

# Check if there are any pattern files
PATTERN_FILES=$(find "$LOCAL_PATTERNS_DIR" -name "*.json" ! -name "README.md" 2>/dev/null | wc -l | tr -d ' ')
if [ "$PATTERN_FILES" -eq 0 ]; then
    echo -e "${YELLOW}⚠️  No pattern files found to share${NC}"
    exit 0
fi

# Check if git repo is clean
cd "$REPO_ROOT"
if ! git diff-index --quiet HEAD -- 2>/dev/null; then
    echo -e "${RED}❌ Error: Git repository has uncommitted changes${NC}"
    echo ""
    echo "Please commit or stash your changes first:"
    echo "  git status"
    echo "  git add ."
    echo "  git commit -m \"your message\""
    exit 1
fi

echo -e "${GREEN}✅ All checks passed${NC}"
echo ""

# ============================================================================
# Show what will be shared
# ============================================================================

echo -e "${BLUE}📊 Pattern Summary${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

for pattern_file in "$LOCAL_PATTERNS_DIR"/*.json; do
    if [ -f "$pattern_file" ]; then
        filename=$(basename "$pattern_file")
        echo "  📄 $filename"

        # Count patterns/learnings
        if [[ "$filename" == "common-issues.json" ]]; then
            count=$(jq '.patterns | length' "$pattern_file" 2>/dev/null || echo "0")
            echo "     → $count common issue patterns"
        elif [[ "$filename" == "scout-learnings.json" ]]; then
            count=$(jq '.learnings | length' "$pattern_file" 2>/dev/null || echo "0")
            echo "     → $count scout learnings"
        fi
        echo ""
    fi
done

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Ask for confirmation
read -p "Share these patterns with the community? (y/N) " -n 1 -r
echo ""
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled by user"
    exit 0
fi

echo ""

# ============================================================================
# Create feature branch
# ============================================================================

echo -e "${GREEN}🌿 Creating branch: $BRANCH_NAME${NC}"
git checkout -b "$BRANCH_NAME"
echo ""

# ============================================================================
# Merge patterns intelligently
# ============================================================================

echo -e "${GREEN}🔀 Merging patterns...${NC}"
echo ""

MERGE_STATS=()

# Merge common-issues.json if exists
if [ -f "$LOCAL_PATTERNS_DIR/common-issues.json" ]; then
    echo "  📋 Merging common-issues.json..."

    python3 "$MERGE_SCRIPT" \
        --source "$LOCAL_PATTERNS_DIR/common-issues.json" \
        --dest "$REPO_PATTERNS_DIR/common-issues.json" \
        --type common-issues \
        --output "$TEMP_DIR/common-issues.json"

    # Copy merged result to repo
    cp "$TEMP_DIR/common-issues.json" "$REPO_PATTERNS_DIR/common-issues.json"

    # Extract stats
    NEW=$(jq '.patterns | length' "$TEMP_DIR/common-issues.json")
    MERGE_STATS+=("common-issues: $NEW patterns")
    echo ""
fi

# Merge scout-learnings.json if exists
if [ -f "$LOCAL_PATTERNS_DIR/scout-learnings.json" ]; then
    echo "  🔍 Merging scout-learnings.json..."

    python3 "$MERGE_SCRIPT" \
        --source "$LOCAL_PATTERNS_DIR/scout-learnings.json" \
        --dest "$REPO_PATTERNS_DIR/scout-learnings.json" \
        --type scout-learnings \
        --output "$TEMP_DIR/scout-learnings.json"

    # Copy merged result to repo
    cp "$TEMP_DIR/scout-learnings.json" "$REPO_PATTERNS_DIR/scout-learnings.json"

    # Extract stats
    NEW=$(jq '.learnings | length' "$TEMP_DIR/scout-learnings.json")
    MERGE_STATS+=("scout-learnings: $NEW learnings")
    echo ""
fi

echo -e "${GREEN}✅ Patterns merged successfully${NC}"
echo ""

# ============================================================================
# Commit changes
# ============================================================================

echo -e "${GREEN}💾 Committing changes...${NC}"

# Stage pattern files
git add .context-foundry/patterns/*.json

# Create commit message
COMMIT_MSG="chore: Share learned patterns from ${GH_USERNAME}

Merged patterns from local builds into global pattern database.

$(printf '%s\n' "${MERGE_STATS[@]}")

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"

git commit -m "$COMMIT_MSG"

echo -e "${GREEN}✅ Changes committed${NC}"
echo ""

# ============================================================================
# Push branch and create PR
# ============================================================================

echo -e "${GREEN}🚀 Pushing branch to GitHub...${NC}"
git push -u origin "$BRANCH_NAME"
echo ""

echo -e "${GREEN}📝 Creating pull request...${NC}"

PR_BODY="## Pattern Sharing from @${GH_USERNAME}

This PR contributes learned patterns from local Context Foundry builds to the global pattern database.

### 📊 Patterns Included

$(printf '- %s\n' "${MERGE_STATS[@]}")

### ✅ Validation

The \`validate-patterns\` workflow will:
- ✅ Validate JSON schema
- ✅ Check for duplicate pattern IDs
- ✅ Test merge integrity
- ✅ Auto-merge if all checks pass

### 🎯 Impact

These patterns will be included in the next nightly release and will help future builds:
- Detect common issues earlier
- Apply proven solutions automatically
- Reduce build failures

---

🤖 Generated via \`scripts/share-my-patterns.sh\`"

# Create PR
PR_URL=$(gh pr create \
    --title "chore: Share learned patterns from ${GH_USERNAME}" \
    --body "$PR_BODY" \
    --label "patterns" \
    --label "automated" \
    2>&1)

echo ""
echo -e "${GREEN}✅ Pull request created!${NC}"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${BLUE}🎉 Success!${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Your patterns have been submitted for review."
echo ""
echo "PR URL: $PR_URL"
echo ""
echo "The validate-patterns workflow will automatically:"
echo "  1. ✅ Validate all pattern files"
echo "  2. ✅ Run merge tests"
echo "  3. ✅ Auto-merge if all checks pass"
echo ""
echo "Your patterns will be included in the next nightly release!"
echo ""
echo "Thank you for contributing to the Context Foundry community! 🙏"
echo ""

# Cleanup
rm -rf "$TEMP_DIR"

# Switch back to main branch
git checkout main

exit 0
