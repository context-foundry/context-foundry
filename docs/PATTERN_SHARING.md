# Pattern Sharing System

**Automatic knowledge sharing - your builds make everyone smarter**

Context Foundry learns from every build and **automatically shares** patterns with the community. When you run builds, your learnings help prevent issues for everyone else - completely automatically, no manual steps required.

---

## Table of Contents

- [Quick Start](#quick-start)
- [How It Works (Automatic)](#how-it-works-automatic)
- [One-Time Setup](#one-time-setup)
- [What Gets Shared Automatically](#what-gets-shared-automatically)
- [Manual Sharing (Optional)](#manual-sharing-optional)
- [Pattern Types](#pattern-types)
- [Privacy & Security](#privacy--security)
- [Troubleshooting](#troubleshooting)
- [Advanced Usage](#advanced-usage)

---

## Quick Start

### Automatic Sharing (Recommended)

**One-time setup:**

```bash
# Install GitHub CLI (if not already installed)
brew install gh   # macOS
# or
sudo apt install gh   # Linux

# Authenticate with GitHub (one-time)
gh auth login
```

**That's it!** Now every build automatically shares patterns. Zero manual work.

### Manual Sharing (If you prefer)

```bash
# Share patterns manually anytime
cd ~/homelab/context-foundry
./scripts/share-my-patterns.sh
```

---

## How It Works (Automatic)

### The Pattern Learning Cycle

```
┌─────────────────────────────────────────────────────────────┐
│  1. Build Runs on Your Computer                            │
│     └─> Context Foundry learns patterns locally             │
│         Saved to: ~/.context-foundry/patterns/              │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  2. Phase 7: Feedback (AUTOMATIC)                          │
│     └─> Patterns merged to local database                   │
│     └─> share_patterns_to_community() called automatically │
│         Creates PR to Context Foundry repo                   │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  3. Automatic Validation (GitHub Actions)                   │
│     ✅ Validates JSON schema                                │
│     ✅ Checks for duplicates                                │
│     ✅ Tests merge integrity                                │
│     ✅ Auto-merges if all checks pass                       │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  4. Nightly Release                                         │
│     └─> Merged patterns included in next nightly build     │
│         Everyone gets the latest learnings!                 │
└─────────────────────────────────────────────────────────────┘
```

**Key Point:** After Step 1 (running `gh auth login` once), everything else happens **automatically** with every build. No manual intervention needed!

### Flow Diagram

```
┌──────────────────┐
│  Computer A      │
│  (You)           │         ┌──────────────────────────┐
│                  │         │  GitHub Repository       │
│  ~/.context-     │─────────│  .context-foundry/       │
│   foundry/       │  PR     │   patterns/              │
│   patterns/      │         │                          │
└──────────────────┘         │  ✅ Validated            │
                             │  ✅ Merged               │
┌──────────────────┐         └──────────────────────────┘
│  Computer B      │                    │
│  (Other User)    │                    │ Nightly Release
│                  │◄───────────────────┘
│  Pulls latest    │         Contains your patterns!
│  Context Foundry │
└──────────────────┘
```

---

## One-Time Setup

To enable automatic pattern sharing, you only need to do this once:

### Install GitHub CLI

```bash
# macOS
brew install gh

# Linux (Debian/Ubuntu)
sudo apt install gh

# Or download from: https://cli.github.com/
```

### Authenticate

```bash
gh auth login
```

Follow the prompts to authenticate with GitHub. This gives Context Foundry permission to create PRs on your behalf.

**That's it!** Every build will now automatically share patterns.

### Verify Setup

```bash
# Check if gh is authenticated
gh auth status

# Should show: "Logged in to github.com as YOUR_USERNAME"
```

### What If I Don't Set This Up?

No problem! Builds will work normally, but pattern sharing will be skipped with a friendly message:

```
⚠️  Pattern sharing skipped: GitHub CLI not authenticated
   Run 'gh auth login' to enable automatic pattern sharing
```

Your local patterns still work and improve YOUR builds - they just won't be shared with the community.

---

## What Gets Shared Automatically

After **every successful build**, Context Foundry automatically:

1. ✅ Checks if there are new patterns since last share
2. ✅ Creates a PR with your patterns
3. ✅ GitHub validates the patterns
4. ✅ Auto-merges if validation passes
5. ✅ Patterns included in next nightly release

**Smart deduplication:**
- Won't create duplicate PRs (tracks last share timestamp)
- Only shares if patterns were modified since last share
- Gracefully skips if gh not authenticated

**What happens in session-summary.json:**
```json
"feedback": {
  "patterns_shared_to_community": true,
  "pattern_share_status": "success",
  "pattern_share_pr_url": "https://github.com/context-foundry/context-foundry/pull/456",
  "pattern_share_timestamp": "2025-10-27T14:32:00Z"
}
```

---

## Manual Sharing (Optional)

If you prefer to share manually instead of automatically:

```bash
cd ~/homelab/context-foundry
./scripts/share-my-patterns.sh
```

This gives you full control over when to share. Useful if you want to:
- Review patterns before sharing
- Batch multiple builds before sharing
- Share only specific patterns (by editing local files first)

---

## When to Share (Manual Mode)

### Good Times to Share

✅ **After successful builds** - Patterns that helped solve real problems

✅ **After fixing build failures** - Learnings from debugging sessions

✅ **Weekly/Monthly** - Accumulate patterns, then share in batch

✅ **When you have 5+ new patterns** - Makes the PR more valuable

### Don't Share If...

❌ **You haven't run any builds yet** - No patterns to share

❌ **Testing/experimenting** - Wait until patterns are proven

❌ **Patterns contain sensitive info** - See [Privacy & Security](#privacy--security)

---

## Sharing Your Patterns

### Step 1: Run the Script

```bash
cd ~/homelab/context-foundry
./scripts/share-my-patterns.sh
```

### Step 2: Review Summary

The script will show what you're about to share:

```
📊 Pattern Summary
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  📄 common-issues.json
     → 12 common issue patterns

  📄 scout-learnings.json
     → 8 scout learnings

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Share these patterns with the community? (y/N)
```

### Step 3: Confirm

Press `y` to continue. The script will:

1. ✅ Create a feature branch (`patterns/{username}/{timestamp}`)
2. ✅ Merge your patterns intelligently
3. ✅ Commit changes
4. ✅ Push to GitHub
5. ✅ Create a pull request

### Step 4: Wait for Auto-Merge

The PR will be automatically validated and merged (usually within 2-3 minutes).

---

## What Happens Next

### Automatic Validation

When you create a PR, GitHub Actions runs these checks:

| Check | What It Does |
|-------|-------------|
| **JSON Syntax** | Ensures all files are valid JSON |
| **Duplicate IDs** | Prevents duplicate pattern_id or learning_id |
| **Required Fields** | Validates all required fields are present |
| **Severity Levels** | Checks severity is CRITICAL/HIGH/MEDIUM/LOW |
| **Merge Integrity** | Tests that merge doesn't corrupt data |

### Auto-Merge

If all checks pass and the PR has `patterns` and `automated` labels:

1. ✅ PR is automatically approved
2. ✅ Auto-merge is enabled
3. ✅ Branch is deleted after merge

You'll receive a GitHub notification when it's merged.

### Nightly Release

The next nightly release (midnight UTC) will:

1. ✅ Include your merged patterns
2. ✅ Tag a new nightly version (`v{VERSION}-nightly.{DATE}`)
3. ✅ Generate release notes mentioning pattern updates

Anyone who pulls/clones Context Foundry will get your patterns!

---

## Pattern Types

### Common Issues (`common-issues.json`)

**Purpose:** Problems encountered during builds and their solutions

**Example Pattern:**

```json
{
  "pattern_id": "python-fastapi-cors-missing",
  "title": "CORS not configured for FastAPI",
  "first_seen": "2025-10-15",
  "last_seen": "2025-10-20",
  "frequency": 3,
  "severity": "HIGH",
  "project_types": ["python-api", "fastapi", "web-api"],
  "issue": "FastAPI app works locally but fails in browser due to missing CORS",
  "solution": {
    "architect": "Include fastapi.middleware.cors in architecture",
    "builder": "Add CORSMiddleware with allow_origins=['*'] for development",
    "tester": "Test API from browser console to verify CORS headers"
  },
  "auto_apply": true
}
```

**Fields:**
- `pattern_id`: Unique kebab-case identifier
- `title`: Human-readable description
- `first_seen` / `last_seen`: Date tracking
- `frequency`: How many times this was encountered
- `severity`: CRITICAL | HIGH | MEDIUM | LOW
- `project_types`: Where this applies
- `issue`: Problem description
- `solution`: Phase-specific guidance (scout, architect, builder, tester)
- `auto_apply`: Whether to automatically apply this pattern

### Scout Learnings (`scout-learnings.json`)

**Purpose:** Research insights from the Scout phase

**Example Learning:**

```json
{
  "learning_id": "textual-framework-2025",
  "category": "framework",
  "project_types": ["tui-application", "cli-tool"],
  "key_points": [
    "Textual 0.40+ has breaking changes from 0.38",
    "App.run() is now async in latest version",
    "CSS system completely redesigned"
  ],
  "recommendations": [
    "Pin textual version in pyproject.toml",
    "Use textual>=0.40.0 for new projects",
    "Include textual-dev for live reloading during development"
  ],
  "antipatterns": [
    "Using textual without version constraint",
    "Mixing async and sync event handlers"
  ],
  "first_seen": "2025-10-18",
  "confidence": "high"
}
```

**Fields:**
- `learning_id`: Unique identifier
- `category`: library | framework | best-practice | architecture | tooling | deployment
- `project_types`: Applicable project types
- `key_points`: Main takeaways
- `recommendations`: What to do
- `antipatterns`: What to avoid
- `confidence`: high | medium | low

---

## Privacy & Security

### What Gets Shared

✅ **Shared:**
- Pattern IDs and descriptions
- Error types and solutions
- Technology stack information
- Best practices and learnings

❌ **NOT Shared:**
- Your actual code
- Project names
- File paths
- API keys or secrets
- Personal information

### Review Before Sharing

The script shows you exactly what will be shared before creating the PR. Always review:

1. ✅ No project-specific file paths
2. ✅ No API keys or credentials
3. ✅ No proprietary business logic
4. ✅ Only generic, reusable patterns

### Opting Out

Don't want to share patterns? Simply don't run the script. Your local patterns in `~/.context-foundry/patterns/` stay private.

---

## Troubleshooting

### "gh CLI is not installed"

Install GitHub CLI:

```bash
# macOS
brew install gh

# Linux
sudo apt install gh

# Or download from: https://cli.github.com/
```

### "gh is not authenticated"

Authenticate with GitHub:

```bash
gh auth login
```

Follow the prompts to authenticate.

### "Git repository has uncommitted changes"

Commit or stash your changes first:

```bash
git status
git add .
git commit -m "your changes"

# Then try again
./scripts/share-my-patterns.sh
```

### "No local patterns found"

This means you haven't run any Context Foundry builds yet:

```bash
# Run a build first
cd ~/homelab/context-foundry
python3 tools/mcp_server.py

# In Claude Code or Claude Desktop:
# Use autonomous_build_and_deploy() to run a build
# Then patterns will be saved to ~/.context-foundry/patterns/
```

### PR Validation Failed

If the validation workflow fails:

1. Check the GitHub Actions log for details
2. Fix the issue in your local patterns
3. Run the script again (creates a new PR)

Common validation failures:
- Invalid JSON syntax
- Duplicate pattern IDs
- Missing required fields
- Invalid severity level

---

## Advanced Usage

### Manual Pattern Merge

If you want to merge patterns without creating a PR:

```bash
python3 scripts/merge-patterns-intelligent.py \
  --source ~/.context-foundry/patterns/common-issues.json \
  --dest .context-foundry/patterns/common-issues.json \
  --type common-issues \
  --output merged-common-issues.json
```

### Test Merge Locally

Before sharing, test the merge:

```bash
# Create temp directory
TEMP_DIR=$(mktemp -d)

# Test merge
python3 scripts/merge-patterns-intelligent.py \
  --source ~/.context-foundry/patterns/common-issues.json \
  --dest .context-foundry/patterns/common-issues.json \
  --type common-issues \
  --output "$TEMP_DIR/test-merge.json"

# Review output
cat "$TEMP_DIR/test-merge.json" | jq .

# Cleanup
rm -rf "$TEMP_DIR"
```

### Selective Sharing

If you only want to share specific patterns:

1. Create a temporary copy of your patterns directory
2. Remove patterns you don't want to share
3. Point the script to the temporary directory (edit the script)
4. Run the script

**Better approach:** Just edit your local `~/.context-foundry/patterns/*.json` files to remove patterns you don't want to share before running the script.

### Check Pattern Stats

See what patterns you have locally:

```bash
# Common issues
jq '{
  total_patterns: (.patterns | length),
  total_builds: .total_builds,
  last_updated: .last_updated
}' ~/.context-foundry/patterns/common-issues.json

# Scout learnings
jq '{
  total_learnings: (.learnings | length),
  categories: [.learnings[].category] | unique,
  last_updated: .last_updated
}' ~/.context-foundry/patterns/scout-learnings.json
```

---

## Contributing to the System

Want to improve the pattern sharing system itself?

### Files

- `scripts/share-my-patterns.sh` - User-facing sharing script
- `scripts/merge-patterns-intelligent.py` - Merge logic
- `.github/workflows/validate-patterns.yml` - Validation workflow
- `docs/PATTERN_SHARING.md` - This documentation

### Submitting Improvements

1. Fork the Context Foundry repository
2. Make your changes
3. Test thoroughly
4. Submit a PR with description of improvements

---

## FAQ

**Q: How often should I share patterns?**
A: Whenever you have valuable learnings! Weekly or monthly is a good cadence.

**Q: Will my patterns be attributed to me?**
A: The PR will show your GitHub username, but patterns themselves are anonymized.

**Q: Can I see what patterns exist globally?**
A: Yes! Browse `.context-foundry/patterns/` in the GitHub repository.

**Q: What if I share a bad pattern?**
A: The validation catches most issues. If a bad pattern makes it through, submit a fix PR.

**Q: Can I delete a pattern I shared?**
A: Yes, submit a PR removing it from `.context-foundry/patterns/*.json`

**Q: How do I know my patterns helped someone?**
A: Future build feedback will reference patterns that prevented issues!

---

## Support

Having issues? Need help?

1. **Check this documentation** - Most common issues are covered
2. **GitHub Issues** - Search for similar problems or create a new issue
3. **Community Discussions** - Ask questions in GitHub Discussions

---

**Last Updated:** 2025-10-26
**Version:** 1.0.0
**Maintainer:** Context Foundry Community
