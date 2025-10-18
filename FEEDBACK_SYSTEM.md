# Context Foundry Self-Learning Feedback System

**Making Context Foundry Smarter with Every Build**

Version: 1.0.0 | Last Updated: October 18, 2025

---

## Overview

Context Foundry now includes a **Phase 7: Feedback Analysis** that runs after every build (success or failure). This phase analyzes what happened, extracts learnings, and stores them in a pattern library that future builds can leverage.

**Result:** Context Foundry gets smarter over time, preventing issues before they occur.

---

## The Feedback Loop

```
Build Project (Phases 1-6)
          ↓
Phase 7: Analyze Build → Extract Patterns → Store Learnings
          ↓                                        ↓
     Update Pattern Library          ←────────────┘
          ↓
Next Build: Apply Past Learnings (Phases 1-4 read patterns)
```

**Key Insight:** Every build makes the next build better.

---

## How It Works

### Phase 7: Feedback Analysis

**Runs:** After Phase 6 (Deploy) on success, or after Phase 4 (Test) on failure

**What It Does:**

1. **Collects build data:**
   - Reads all artifacts (.context-foundry/)
   - Reviews test iterations and failures
   - Analyzes what worked and what didn't
   - Identifies root causes of issues

2. **Categorizes feedback:**
   - Scout improvements (missing research/risk flags)
   - Architect improvements (design gaps/preventive measures)
   - Builder improvements (implementation patterns)
   - Test improvements (coverage gaps/integration tests)

3. **Extracts patterns:**
   - Identifies if issue is recurring or one-time
   - Determines applicable project types
   - Documents proven solutions
   - Assigns severity (HIGH/MEDIUM/LOW)

4. **Updates pattern library:**
   - Creates new pattern entries
   - Increments frequency for existing patterns
   - Updates last_seen dates
   - Enables auto-apply for proven patterns

5. **Generates recommendations:**
   - Specific actions for each phase
   - Priorities (what to fix first)
   - Expected impact
   - Implementation guidance

**Output Files:**
- `.context-foundry/feedback/build-feedback-{timestamp}.json` (this build's analysis)
- `.context-foundry/patterns/common-issues.json` (updated)
- `.context-foundry/patterns/test-patterns.json` (updated)
- `.context-foundry/patterns/architecture-patterns.json` (updated)
- `.context-foundry/patterns/scout-learnings.json` (updated)
- `.context-foundry/feedback/recommendations.md` (improvement suggestions)

---

## Pattern Library

Location: `.context-foundry/patterns/`

### Files

**common-issues.json**
- General issues across all project types
- Example: CORS errors, module loading problems, dependency conflicts

**test-patterns.json**
- Testing strategy improvements
- Example: Unit tests miss browser issues, integration test needs

**architecture-patterns.json**
- Proven design patterns
- Example: Entity-component architecture for games

**scout-learnings.json**
- Risk detection and research insights
- Example: Flag CORS risk for browser apps with ES6 modules

### Pattern Schema

```json
{
  "pattern_id": "unique-identifier",
  "title": "Human-readable title",
  "first_seen": "2025-10-18",
  "last_seen": "2025-10-18",
  "frequency": 1,
  "severity": "HIGH|MEDIUM|LOW",
  "project_types": ["browser-app", "cli-tool", ...],
  "issue": {...},
  "root_cause": "Description",
  "solution": {
    "scout": "What Scout should do",
    "architect": "What Architect should include",
    "builder": "What Builder should implement",
    "test": "What Test should verify"
  },
  "prevention": {
    "auto_apply": true/false,
    "conditions": ["when to apply"],
    "actions": ["specific steps"]
  }
}
```

---

## How Patterns Are Applied

### Phase 1: Scout (Updated)

**Before starting research:**

1. Reads `.context-foundry/patterns/scout-learnings.json`
2. Reads `.context-foundry/patterns/common-issues.json`
3. Identifies project type from task description
4. Checks for patterns matching this type
5. Flags known risks in scout-report.md

**Example:**
```
Task: "Build a browser game with HTML5 Canvas"
Scout reads patterns → Finds "cors-es6-modules" pattern
Scout flags: ⚠️ CORS RISK: ES6 modules require dev server
Scout includes: Recommendation for http-server in scout-report.md
```

### Phase 2: Architect (Updated)

**During design:**

1. Reads `.context-foundry/patterns/architecture-patterns.json`
2. Reads `.context-foundry/patterns/common-issues.json`
3. Checks Scout's flagged risks
4. Applies proven architectural patterns
5. Includes preventive measures

**Example:**
```
Scout flagged: CORS risk
Architect reads: cors-es6-modules pattern
Architect includes: http-server in package.json automatically
Architect documents: Server requirement in architecture.md
```

### Phase 4: Test (Updated)

**Before running tests:**

1. Reads `.context-foundry/patterns/test-patterns.json`
2. Reads `.context-foundry/patterns/common-issues.json`
3. Checks for project-type-specific test needs
4. Runs additional integration tests if indicated

**Example:**
```
Project type: browser-app
Test reads: "unit-tests-miss-browser-issues" pattern
Test runs: Browser integration checks (if tools available)
Test verifies: Dev server config exists, modules load properly
```

---

## Real-World Example: 1942 Clone

### The Problem

**Build completed:**
- ✅ 86 unit tests passing
- ✅ Deployed to GitHub
- ❌ Game stuck at loading screen (CORS error)

**Root cause:** Jest+jsdom doesn't test actual browser environment.

### Feedback Analysis

Phase 7 analyzed the build:

```json
{
  "issue": "CORS error not caught by unit tests",
  "should_detect_in_phase": "Test",
  "detected_in_phase": "Manual user testing",
  "solution": "Include http-server, add browser integration tests",
  "severity": "HIGH",
  "project_types": ["browser-app", "es6-modules"]
}
```

### Pattern Created

Added to `common-issues.json`:

```json
{
  "pattern_id": "cors-es6-modules",
  "solution": {
    "scout": "Flag CORS risk for browser apps",
    "architect": "Include http-server in package.json",
    "test": "Verify dev server config exists"
  },
  "auto_apply": true
}
```

### Next Build Improvement

**When building next browser game with ES6 modules:**

1. **Scout:** Automatically flags CORS risk
2. **Architect:** Automatically includes http-server
3. **Test:** Automatically verifies server config
4. **Result:** Issue prevented, no manual intervention needed

**Time saved:** ~8 minutes debugging + better UX

---

## Pattern Lifecycle

### 1. Discovery (Frequency: 1)
```
Issue occurs → Feedback Analysis → New pattern created
Status: frequency=1, auto_apply=false
```

### 2. Validation (Frequency: 2-3)
```
Issue recurs → Pattern matched → Frequency incremented
Status: frequency=3, consider auto_apply=true
```

### 3. Proven (Frequency: 5+)
```
Pattern consistently applies → High success rate
Status: frequency=5+, auto_apply=true, prevention rate tracked
```

### 4. Maintenance
```
Stale patterns (not seen in 6+ months, frequency < 3):
→ Reviewed for removal
→ Pruned to keep library focused
```

---

## Metrics & Analytics

### Build Quality Metrics

Track over time:
- **Test iterations trend:** Should decrease as patterns prevent issues
- **Build success rate:** Should increase to 95%+
- **Common issue prevention:** Track how often patterns prevent problems
- **Average build duration:** Should stabilize/decrease

### Pattern Library Metrics

- **Total patterns:** Growth indicates learning accumulation
- **Auto-apply ratio:** Higher = more automation
- **Pattern frequency:** Identifies most common issues
- **Coverage:** Project types represented

### Example Metrics Dashboard

```
Builds Completed: 25
Average Test Iterations: 1.2 (down from 2.5 initially)
Common Issues Prevented: 18 (72%)
Patterns in Library: 12
Auto-Apply Patterns: 8 (67%)
High-Severity Patterns: 4
```

---

## Integration with Autonomous Builds

### MCP Tool Integration

The `mcp__autonomous_build_and_deploy` tool automatically:

1. Runs Phases 1-6 (as before)
2. Runs Phase 7 (Feedback Analysis)
3. Updates pattern library
4. Returns feedback data in JSON

**No changes needed to existing builds!**

### Async Builds

Works with `mcp__autonomous_build_and_deploy_async` too:

```
Build runs in background → Completes → Feedback generated
User checks status → Sees patterns added
Next build → Benefits from learnings
```

---

## Best Practices

### For Users

✅ **Do:**
- Review `.context-foundry/feedback/recommendations.md` after builds
- Check pattern library growth over time
- Note when patterns prevent issues
- Provide feedback on pattern accuracy

❌ **Don't:**
- Disable feedback analysis (it's lightweight, ~1-2 min)
- Ignore high-priority recommendations
- Delete pattern library files
- Modify pattern files without understanding schema

### For Developers

✅ **Do:**
- Keep pattern library in version control (.context-foundry/patterns/)
- Share patterns across projects/teams
- Review and prune low-frequency patterns periodically
- Document custom patterns clearly
- Test auto-apply logic before enabling

---

## Configuration

### Enable/Disable Feedback

**Enabled by default.** To disable:

Edit `tools/orchestrator_prompt.txt`:
- Comment out Phase 7 section
- Or set environment variable: `SKIP_FEEDBACK_ANALYSIS=true`

### Customize Pattern Application

Edit pattern JSON files:
- Set `auto_apply: false` to disable automatic application
- Adjust `conditions` to refine when patterns apply
- Update `severity` based on real-world impact

---

## Troubleshooting

### Patterns Not Being Applied

**Check:**
1. Pattern file exists: `.context-foundry/patterns/*.json`
2. Pattern `auto_apply: true`
3. Pattern conditions match project type
4. Phase is reading pattern files (check orchestrator_prompt.txt)

**Debug:**
- Review scout-report.md for flagged risks
- Check architecture.md for applied patterns
- Look for pattern mentions in build artifacts

### Feedback Analysis Fails

**Common causes:**
- Malformed JSON in pattern files
- Missing .context-foundry/test-results-*.md
- Feedback agent crashed

**Solution:**
- Validate JSON: `cat .context-foundry/patterns/common-issues.json | jq`
- Check .context-foundry/errors.md for details
- Review orchestrator execution logs

---

## Future Enhancements

### Planned Features

1. **ML-Based Pattern Detection**
   - Automatically identify new patterns without manual analysis
   - Predict likely issues before they occur

2. **Cross-Project Learning**
   - Share patterns across multiple repositories
   - Team-wide pattern libraries

3. **Pattern Confidence Scores**
   - Track success rate when applied
   - Adjust auto-apply based on confidence

4. **Visualization Dashboard**
   - View pattern library growth
   - See metrics trends over time
   - Identify most impactful patterns

5. **Pattern Testing**
   - Automated validation of patterns
   - A/B testing: with vs without pattern
   - Measure effectiveness quantitatively

---

## Contributing Patterns

Want to contribute patterns to the community?

1. Build projects with Context Foundry
2. Review generated feedback files
3. Identify high-value, reusable patterns
4. Submit PR with:
   - Pattern JSON
   - Real-world example
   - Success metrics
   - Documentation

---

## FAQ

**Q: Does feedback analysis slow down builds?**
A: Minimal impact. ~1-2 minutes per build, fully automated.

**Q: Can I use patterns from one machine on another?**
A: Yes! Copy `.context-foundry/patterns/` directory. Patterns are portable.

**Q: What if a pattern is wrong?**
A: Edit the pattern JSON file or set `auto_apply: false` to disable.

**Q: How many patterns before it's "smart enough"?**
A: Quality over quantity. 10-20 well-defined patterns cover 80% of issues.

**Q: Can I share patterns with my team?**
A: Yes! Commit `.context-foundry/patterns/` to your repo or share the directory.

**Q: Does this work with all project types?**
A: Yes. Patterns are tagged by project type, so they only apply when relevant.

---

## Summary

**Context Foundry's feedback system creates a self-improving development workflow:**

1. ✅ Learns from every build automatically
2. ✅ Prevents issues before they occur
3. ✅ Reduces test iterations over time
4. ✅ Improves build quality continuously
5. ✅ No manual intervention required

**The more you use Context Foundry, the smarter it gets.**

---

**Version:** 1.0.0
**Last Updated:** October 18, 2025
**Status:** Production Ready
**Learn More:** [README.md](README.md) | [ARCHITECTURE_DECISIONS.md](ARCHITECTURE_DECISIONS.md)
