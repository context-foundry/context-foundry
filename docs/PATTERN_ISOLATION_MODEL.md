# Pattern Isolation Model

## Overview

Context Foundry uses a **pattern isolation model** to prevent context bloat and cross-contamination between different build types. Extension-specific patterns (Flowise, Roblox, etc.) are kept separate from general patterns to ensure specialized agents only load relevant knowledge.

## Why Pattern Isolation?

### The Problem (Before Isolation)

When extension patterns were merged into global storage:

- **Massive context bloat**: 140KB+ of irrelevant patterns loaded into every build
- **Cross-contamination**: Flowise AgentFlow patterns loaded during Python FastAPI builds
- **Token waste**: 99.8% bloat in `common-issues.json` (134KB → 202 bytes after cleanup)
- **Hallucination risk**: Agents confused Flowise node patterns with general programming patterns

### Example of Bloat

**Before isolation (general Python build):**
```
Loading patterns...
✓ Loaded 80 common issues
  ├─ 65 Flowise AgentFlow issues (IRRELEVANT!)
  ├─ 15 Roblox Luau issues (IRRELEVANT!)
  └─ 0 general Python issues

Context: 134KB, 99.8% waste
```

**After isolation (general Python build):**
```
Loading patterns...
✓ Loaded 0 common issues (clean start for general builds)

Context: 202 bytes, 0% waste
```

## Pattern Storage Structure

```
~/.context-foundry/patterns/                    # Global patterns (general builds)
  ├─ common-issues.json                         # General issues ONLY
  ├─ architecture-patterns.json                 # General patterns ONLY
  ├─ scout-learnings.json                       # General learnings ONLY
  └─ test-patterns.json                         # General test patterns ONLY

/path/to/context-foundry/
  └─ extensions/
      ├─ flowise/
      │   └─ patterns/
      │       └─ flowise-expertise.json         # Flowise-ONLY patterns
      │
      ├─ roblox/
      │   └─ patterns/
      │       └─ roblox-expertise.json          # Roblox-ONLY patterns
      │
      └─ future-extension/
          └─ patterns/
              └─ extension-patterns.json        # Extension-specific patterns
```

## Pattern Loading Rules

### Rule 1: Extension Builds Load Extension Patterns ONLY

**Flowise builds:**
- ✅ Read `extensions/flowise/patterns/*.json`
- ✅ Read `extensions/flowise/docs/*.md`
- ❌ DO NOT read `~/.context-foundry/patterns/`

**Roblox builds:**
- ✅ Read `extensions/roblox/patterns/*.json`
- ✅ Read `extensions/roblox/docs/*.md`
- ❌ DO NOT read `~/.context-foundry/patterns/`

### Rule 2: General Builds Load Global Patterns ONLY

**Python/Node.js/Go/C++ builds:**
- ✅ Read `~/.context-foundry/patterns/*.json`
- ❌ DO NOT read extension patterns

### Rule 3: Detection is Session-Based

Check `.context-foundry/session-summary.json`:

```json
{
  "configuration": {
    "extension": "flowise",  // or "roblox", or null for general
    "flowise_flow": true     // backward compatibility flag
  }
}
```

## How Phases Enforce Isolation

### Scout Phase (phase_scout.txt)

```markdown
**Step 1: Detect Extension Mode and Load Isolated Patterns**

Check session configuration:
cat .context-foundry/session-summary.json | grep -E '"extension"|"flowise_flow"'

OPTION A: FLOWISE BUILD
- Read extensions/flowise/patterns/*.json
- DO NOT read global patterns

OPTION B: ROBLOX BUILD
- Read extensions/roblox/patterns/*.json
- DO NOT read global patterns

OPTION C: GENERAL BUILD
- read_global_patterns("scout-learnings")
- read_global_patterns("common-issues")
```

### Architect Phase (phase_architect.txt)

```markdown
**Step 2: Load Isolated Patterns (Same as Scout)**

OPTION A: FLOWISE BUILD
- Read extensions/flowise/patterns/*.json
- DO NOT read global patterns

OPTION B: ROBLOX BUILD
- Read extensions/roblox/patterns/*.json
- DO NOT read global patterns

OPTION C: GENERAL BUILD
- read_global_patterns("common-issues")
- read_global_patterns("architecture-patterns")
```

### Builder Phase (phase_builder.txt)

Already implements isolation:

```markdown
**AUTHORITATIVE REFERENCE DIRECTORY:**
- Read **every JSON file** inside extensions/flowise/patterns/
- Roblox projects: read all JSON files in extensions/roblox/patterns/
```

## Migration from Old Model

### If You Have Contaminated Global Patterns

**Cleanup process:**

```bash
# 1. Back up current global patterns
cp ~/.context-foundry/patterns/common-issues.json \
   ~/.context-foundry/patterns/common-issues.json.backup

cp ~/.context-foundry/patterns/architecture-patterns.json \
   ~/.context-foundry/patterns/architecture-patterns.json.backup

# 2. Remove extension patterns
cat ~/.context-foundry/patterns/common-issues.json | \
  jq 'del(.patterns[] | select(.category == "flowise" or .category == "roblox"))' \
  > ~/.context-foundry/patterns/common-issues.json.tmp

mv ~/.context-foundry/patterns/common-issues.json.tmp \
   ~/.context-foundry/patterns/common-issues.json

cat ~/.context-foundry/patterns/architecture-patterns.json | \
  jq 'del(.patterns[] | select(.category == "flowise" or .category == "roblox"))' \
  > ~/.context-foundry/patterns/architecture-patterns.json.tmp

mv ~/.context-foundry/patterns/architecture-patterns.json.tmp \
   ~/.context-foundry/patterns/architecture-patterns.json

# 3. Verify cleanup
wc -c ~/.context-foundry/patterns/common-issues.json
# Should be ~200 bytes (not 134KB)

wc -c ~/.context-foundry/patterns/architecture-patterns.json
# Should be ~33KB (not 73KB)
```

### Bootstrap Scripts are Deprecated

**DO NOT run these scripts:**
- `python scripts/bootstrap_flowise_patterns.py`
- `python scripts/bootstrap_roblox_patterns.py`

Both scripts now require `--force-merge` flag and display warnings about pattern isolation.

**If you accidentally run them:**
```bash
# They will exit with error and display:
⚠️  WARNING: PATTERN ISOLATION MODEL
Extension patterns should stay ISOLATED in their own directories.
```

## Adding New Extensions

### Step 1: Create Extension Directory

```bash
mkdir -p extensions/my-extension/patterns
```

### Step 2: Create Extension Patterns

```bash
# extensions/my-extension/patterns/my-extension-expertise.json
{
  "version": "1.0.0",
  "last_updated": "2025-11-19",
  "description": "My Extension patterns and best practices",

  "patterns": [
    {
      "pattern_id": "my-ext-pattern-001",
      "description": "Core pattern for my extension",
      "category": "architecture",
      "confidence": 0.9,
      ...
    }
  ],

  "common_issues": [
    {
      "issue_id": "my-ext-issue-001",
      "description": "Common issue in my extension",
      "severity": "MEDIUM",
      "solution": {...},
      ...
    }
  ]
}
```

### Step 3: Update Phase Prompts

Add your extension to the pattern loading logic:

**In `tools/prompts/phases/phase_scout.txt`:**

```markdown
**OPTION D: MY-EXTENSION BUILD** (if `extension: "my-extension"`)
- Read extensions/my-extension/patterns/*.json
- DO NOT read global patterns
```

**In `tools/prompts/phases/phase_architect.txt`:**

```markdown
**OPTION D: MY-EXTENSION BUILD** (if `extension: "my-extension"`)
- Read extensions/my-extension/patterns/*.json
- DO NOT read global patterns
```

### Step 4: Update Builder Phase

**In `tools/prompts/phases/phase_builder.txt`:**

```markdown
**OTHER EXTENSION PATTERN DIRECTORIES:**
- Flowise: extensions/flowise/patterns/
- Roblox: extensions/roblox/patterns/
- My Extension: extensions/my-extension/patterns/  # ADD THIS
```

## Benefits of Pattern Isolation

### 1. Efficiency
- **99.8% reduction** in common-issues.json (134KB → 202 bytes)
- **54% reduction** in architecture-patterns.json (73KB → 33KB)
- **Total savings**: 140KB of irrelevant patterns removed

### 2. Specialization
- Flowise builds focus ONLY on AgentFlow v2.2 patterns
- Roblox builds focus ONLY on Luau/game development patterns
- General builds focus ONLY on universal programming patterns

### 3. No Cross-Contamination
- Flowise node patterns don't confuse Python builds
- Roblox RemoteEvent patterns don't interfere with web apps
- Each extension maintains its own expertise domain

### 4. Scalability
- Add new extensions without bloating global patterns
- Future extensions (Go, C++, Rust, etc.) stay isolated
- No limit to number of specialized extensions

## Testing Pattern Isolation

### Verify Flowise Build Loads Only Flowise Patterns

```bash
# Start a Flowise build
cfd submit "Create Flowise routing flow" \
  --working-dir /path/to/flowise-project \
  --extension flowise

# Check Scout phase logs
cfd logs <job-id> | grep "Read.*patterns"

# Should see:
✓ Reading extensions/flowise/patterns/flowise-expertise.json
✗ Should NOT see: read_global_patterns("common-issues")
```

### Verify General Build Loads Only Global Patterns

```bash
# Start a general Python build
cfd submit "Create FastAPI backend" \
  --working-dir /path/to/python-project

# Check Scout phase logs
cfd logs <job-id> | grep "Read.*patterns"

# Should see:
✓ read_global_patterns("scout-learnings")
✓ read_global_patterns("common-issues")
✗ Should NOT see: extensions/flowise/patterns
✗ Should NOT see: extensions/roblox/patterns
```

## FAQs

### Q: Can I share patterns between extensions?

**A:** No. Each extension should be self-contained. If you find patterns that apply to multiple extensions, they should be elevated to global patterns.

**Example:**
- "Validate API keys before requests" → General pattern (applies everywhere)
- "Use `agentModel` not `model` in AgentFlow nodes" → Flowise-specific (stays isolated)

### Q: What about learning from successful builds?

**A:** Pattern learning still works, but stays isolated:

- Flowise builds update `extensions/flowise/patterns/flowise-expertise.json`
- Roblox builds update `extensions/roblox/patterns/roblox-expertise.json`
- General builds update `~/.context-foundry/patterns/*.json`

Learned patterns are automatically categorized and stay in their respective domains.

### Q: Can I manually merge patterns if needed?

**A:** Yes, but not recommended. Use:

```bash
python scripts/bootstrap_flowise_patterns.py --force-merge
python scripts/bootstrap_roblox_patterns.py --force-merge
```

This will merge extension patterns into global storage, but you'll lose the benefits of isolation.

### Q: How do I know which patterns to keep global vs. extension-specific?

**Global patterns (universal):**
- Error handling best practices
- API authentication patterns
- Database connection pooling
- Testing strategies
- Git workflow patterns

**Extension-specific patterns (domain-specific):**
- Flowise: AgentFlow node structures, tool integration, memory management
- Roblox: Luau scripting, RemoteEvents, DataStore patterns
- Go: Goroutine patterns, channel usage (future extension)
- Rust: Ownership patterns, lifetimes (future extension)

**Rule of thumb:** If it applies to multiple languages/frameworks, it's global. If it's specific to one technology, it's extension-specific.

## Summary

**Pattern Isolation Model ensures:**
- ✅ Specialized agents for specialized tasks
- ✅ No context bloat or token waste
- ✅ No cross-contamination between extensions
- ✅ Scalable extension architecture
- ✅ Clear separation of concerns

**Key Principle:**
> "Flowise patterns for Flowise builds, Roblox patterns for Roblox builds, general patterns for everything else."
