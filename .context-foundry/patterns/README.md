# Context Foundry Pattern Library

**Self-Learning Knowledge Base for Continuous Improvement**

This directory contains the accumulated learnings from all autonomous builds. Each file stores patterns, issues, and solutions discovered during builds.

---

## Pattern Files

### common-issues.json
**Purpose:** General issues encountered across all project types

**Current Patterns:** 5
- X-Frame-Options iframe blocking (HIGH)
- CORS errors with ES6 modules (HIGH)
- AWS Lambda inline handler mismatch (HIGH)
- API Gateway path routing precedence (MEDIUM)
- Bedrock Agent SUPERVISOR collaboration mode (HIGH)

**Schema:**
```json
{
  "pattern_id": "unique-id",
  "title": "Human-readable title",
  "first_seen": "YYYY-MM-DD",
  "last_seen": "YYYY-MM-DD",
  "frequency": 1,
  "severity": "HIGH|MEDIUM|LOW",
  "project_types": ["browser-app", "cli-tool", ...],
  "issue": {...},
  "root_cause": "Description",
  "solution": {
    "scout": {...},
    "architect": {...},
    "builder": {...},
    "test": {...}
  },
  "prevention": {
    "auto_apply": true/false,
    "conditions": [...],
    "actions": [...]
  }
}
```

### test-patterns.json
**Purpose:** Testing strategies and gaps discovered

Contains patterns for:
- Test coverage gaps
- Integration testing needs
- Browser compatibility checks
- Environment-specific tests

### architecture-patterns.json
**Purpose:** Proven architectural patterns from successful builds

Contains patterns for:
- Code organization strategies
- Design patterns that work well
- File structures
- Module separation approaches

### scout-learnings.json
**Purpose:** Risk detection and research insights

Contains patterns for:
- Risk flags to raise
- Technology compatibility issues
- Common pitfalls to warn about
- Questions to ask during research

---

## Pattern Coverage by Domain

### Frontend & Browser (2 patterns)
- **iframe-embedding:** X-Frame-Options blocking, proxy solutions
- **ES6 modules:** CORS errors from file://, dev server requirements

### AWS & Cloud Infrastructure (3 patterns)
- **AWS CDK + Lambda:** Inline code handler naming (`index.lambda_handler` vs `handler.lambda_handler`)
- **API Gateway:** REST API routing logic precedence (exact matches before patterns)
- **Bedrock Agents:** SUPERVISOR collaboration mode configuration

### Auto-Apply Coverage
- **3 patterns** have auto-apply enabled (60% of library)
- **4 patterns** are HIGH severity
- **1 pattern** is MEDIUM severity

---

## Quick Reference: AWS Patterns

When deploying AWS infrastructure, these patterns automatically apply:

### Pattern: AWS Lambda Handler Mismatch
**Triggers when:** Project uses AWS CDK with `lambda.Code.fromInline()`
```typescript
// ✅ CORRECT - Auto-applied by Builder
new lambda.Function(this, 'MyFunction', {
  handler: 'index.lambda_handler',  // Matches CDK's inline code filename
  code: lambda.Code.fromInline('...')
});

// ❌ WRONG - Will cause ImportModuleError
new lambda.Function(this, 'MyFunction', {
  handler: 'handler.lambda_handler',  // Doesn't match index.py
  code: lambda.Code.fromInline('...')
});
```

### Pattern: API Gateway Routing Precedence
**Triggers when:** Lambda proxy integration with similar path patterns
```python
# ✅ CORRECT - Auto-applied by Builder
def lambda_handler(event, context):
    path = event.get('path', '')
    if path == '/builds':              # Exact match first
        return list_builds()
    elif path.startswith('/build/'):   # Pattern match second
        return handle_build()

# ❌ WRONG - /builds returns 404
def lambda_handler(event, context):
    path = event.get('path', '')
    if path.startswith('/build/'):     # Pattern matches /builds!
        return handle_build()
    elif path == '/builds':            # Never reached
        return list_builds()
```

### Pattern: Bedrock Agent Collaboration Mode
**Triggers when:** Creating Bedrock Agent with action groups

**Manual Checklist (added to documentation):**
1. Create agent in Bedrock console
2. Add action groups (Scout, Architect, Builder, Tester)
3. **Check Agent Collaboration settings**
4. If SUPERVISOR mode is enabled → Disable it
5. Prepare agent
6. Create alias

**Why:** Single agents with action groups should have collaboration DISABLED. SUPERVISOR mode requires sub-agents.

---

## How Patterns Are Used

### Phase 1: Scout
1. Reads `scout-learnings.json` and `common-issues.json`
2. Identifies project type from task description
3. Flags risks matching this project type
4. Includes warnings in scout-report.md

### Phase 2: Architect
1. Reads `architecture-patterns.json` and `common-issues.json`
2. Applies proven architectural patterns
3. Includes preventive measures for flagged risks
4. Adds dependencies/config to prevent common issues

### Phase 4: Test
1. Reads `test-patterns.json` and `common-issues.json`
2. Runs pattern-based integration tests
3. Checks for known issues
4. Validates against project-type-specific requirements

### Phase 7: Feedback
1. Analyzes current build
2. Extracts new patterns
3. Updates existing patterns (increments frequency)
4. Stores learnings for future builds

---

## Pattern Lifecycle

### New Pattern
1. Discovered during feedback analysis
2. Added to appropriate JSON file
3. `frequency: 1`, `first_seen: today`
4. `auto_apply: false` initially

### Recurring Pattern
1. Seen in multiple builds
2. `frequency` incremented
3. `last_seen` updated
4. If `frequency >= 3`: Consider `auto_apply: true`

### Proven Pattern
1. High frequency (5+)
2. High success rate when applied
3. `auto_apply: true`
4. Scout/Architect phases apply automatically

### Stale Pattern
1. Not seen in 6+ months
2. Low frequency (< 3)
3. Marked for review/pruning

---

## Auto-Apply Logic

Patterns with `"auto_apply": true` are automatically applied when conditions match:

**Example:**
```json
{
  "auto_apply": true,
  "conditions": [
    "project_type includes 'browser'",
    "uses ES6 modules"
  ],
  "actions": [
    "Scout: Add CORS warning to scout-report.md",
    "Architect: Include http-server in package.json"
  ]
}
```

When Scout detects a browser app with ES6 modules:
1. Automatically flags CORS risk
2. Architect automatically includes dev server
3. No manual intervention needed
4. Issue prevented before it occurs

---

## Pattern Statistics

Each JSON file includes a `statistics` section:
```json
{
  "statistics": {
    "total_patterns": 5,
    "high_severity": 2,
    "medium_severity": 2,
    "low_severity": 1,
    "auto_apply_enabled": 3
  }
}
```

Track trends:
- Growth of pattern library over time
- Effectiveness (frequency of auto-applied patterns)
- Coverage (project types represented)

---

## Adding Patterns Manually

While patterns are auto-generated by Phase 7, you can manually add patterns:

1. Follow the schema in existing patterns
2. Assign unique `pattern_id`
3. Set `first_seen` to current date
4. Start with `frequency: 1` and `auto_apply: false`
5. Document thoroughly with examples
6. Test pattern application in a build

---

## Best Practices

✅ **Do:**
- Keep patterns specific and actionable
- Include concrete examples
- Document severity accurately
- Update `last_seen` when pattern recurs
- Provide clear solution steps for each phase

❌ **Don't:**
- Create duplicate patterns (check existing first)
- Leave vague descriptions
- Set `auto_apply: true` without testing
- Ignore low-frequency patterns (review and prune)

---

## Metrics to Track

**Pattern Library Health:**
- Total patterns across all files
- Auto-apply ratio (should increase over time)
- Average frequency (indicates pattern refinement)
- Pattern diversity (project types covered)

**Build Improvement:**
- Test iterations trend (should decrease)
- Build success rate (should increase)
- Common issue prevention rate
- Time saved per build

---

## Future Enhancements

- **Pattern Confidence Scores:** Based on success rate
- **Pattern Dependencies:** Some patterns require others
- **Pattern Conflicts:** Flag when patterns contradict
- **ML-Based Pattern Detection:** Automatically identify new patterns
- **Cross-Project Analysis:** Find patterns across multiple repositories

---

## Recent Additions

### October 28, 2025 - AWS Deployment Patterns
Added 3 new patterns from `bedrock-agentic-builder` project:

1. **AWS Lambda Inline Handler Mismatch** (HIGH)
   - CDK inline code creates `index.py` but handler configured as `handler.lambda_handler`
   - Auto-applies correct handler naming for all CDK Lambda deployments
   - Prevents `ImportModuleError` at runtime

2. **API Gateway Path Routing Precedence** (MEDIUM)
   - Generic path patterns (`startsWith`) matched before specific paths
   - Auto-applies correct if/elif ordering (exact matches first)
   - Prevents 404 errors on valid endpoints

3. **Bedrock Agent SUPERVISOR Collaboration Mode** (HIGH)
   - Agent defaults to SUPERVISOR mode without collaborators configured
   - Provides manual checklist for single-agent setups
   - Prevents "ValidationException" during agent preparation

**Impact:** These patterns will automatically prevent common AWS deployment errors, saving 15-30 minutes per deployment.

---

**Last Updated:** 2025-10-28
**Version:** 1.1.0
**Total Patterns:** 5 (common-issues.json)

**Pattern Growth:**
- Oct 18, 2025: 2 patterns (v1.0.0)
- Oct 28, 2025: 5 patterns (v1.1.0) - Added 3 AWS patterns
