# Advanced Optimization Strategies (Phase 3+)

**Beyond v1.4.0:** More aggressive optimizations requiring architectural changes

## Phase 3: Modular Architecture (~1,500-2,000 tokens)

### Concept: Mode-Specific Prompts

**Current Issue:** Single monolithic prompt contains instructions for all modes (new_project, fix_bug, add_feature, etc.)

**Solution:** Dynamic prompt loading based on mode

```
tools/prompts/
├── core_orchestrator.txt          # Core instructions (all modes)
├── modes/
│   ├── new_project.txt            # New project additions
│   ├── fix_bug.txt                # Bug fix additions
│   ├── add_feature.txt            # Feature addition additions
│   ├── upgrade_deps.txt           # Dependency upgrade additions
│   └── refactor.txt               # Refactoring additions
└── shared/
    ├── git_workflow.txt           # Git commands reference
    ├── pattern_library.txt        # Pattern catalog
    └── examples.txt               # Detailed examples
```

**Implementation:**
```python
def load_orchestrator_prompt(mode: str) -> str:
    core = read_file("core_orchestrator.txt")
    mode_specific = read_file(f"modes/{mode}.txt")
    shared_refs = read_file("shared/git_workflow.txt")

    return f"{core}\n\n{mode_specific}\n\n{shared_refs}"
```

**Benefits:**
- New project: ~7,000 tokens (doesn't load enhancement mode instructions)
- Fix bug: ~6,500 tokens (skips architecture phase instructions)
- Add feature: ~7,500 tokens (full workflow)

**Average savings:** ~1,500 tokens per build (depends on mode distribution)

**Risk:** Medium (requires MCP server changes)
**Effort:** 6-8 hours

---

## Phase 4: Template Variables & Macros (~500 tokens)

### Concept: Reusable Instruction Templates

**Current Issue:** Similar instructions repeated with slight variations

**Solution:** Define macros/variables for common patterns

**Example - Phase Updates:**

**Before:**
```
Update phase: "Scout" (1/7, "researching", "Analyzing task requirements")
Update phase: "Architect" (2/7, "designing", "Creating system architecture")
Update phase: "Builder" (3/7, "implementing", "Writing code")
...
```

**After (with macro system):**
```
{{PHASE_START|Scout|1|researching|Analyzing task requirements}}
{{PHASE_START|Architect|2|designing|Creating system architecture}}
{{PHASE_START|Builder|3|implementing|Writing code}}
```

Define macro once:
```
MACRO DEFINITIONS:
{{PHASE_START|name|num|status|detail}} =
  Update .context-foundry/current-phase.json:
  - current_phase: {name}
  - phase_number: {num}/7
  - status: {status}
  - progress_detail: {detail}
  Broadcast to livestream.
```

**Savings:** ~500 tokens

**Risk:** High (model must expand macros correctly)
**Feasibility:** Low (Claude may not reliably expand custom macros)

**Better Alternative:** Pre-process prompt before sending to model

---

## Phase 5: Semantic Compression (~800 tokens)

### Concept: Shorter, Denser Instructions

**Current Issue:** Verbose, friendly explanations

**Example - Current:**
```
**IMPORTANT**: After writing EACH .context-foundry/current-phase.json file,
broadcast the update to the livestream server (if running):

Execute this curl command (non-blocking, continues even if server is down):
[curl command]

This enables real-time monitoring at http://localhost:8080 during autonomous builds.

**When to broadcast**:
- After creating/updating current-phase.json in each phase
- Both at phase start (status: "in_progress") AND phase end (status: "completed")
- During test iterations (when test_iteration changes)
```

**Optimized:**
```
**Livestream:** POST current-phase.json to localhost:8080/api/phase-update after each phase update (start/end/iteration). Non-blocking.
```

**Applies to:**
- All instructional prose
- Repeated explanations
- Verbose guidelines

**Savings:** ~800 tokens

**Risk:** Medium (may lose clarity)
**Trade-off:** Shorter but potentially harder to follow

---

## Phase 6: JSON Schema References (~400 tokens)

### Concept: Reference Schemas Instead of Inline JSON

**Current Issue:** Full JSON examples throughout prompt

**Example - Current:**
```
{
  "session_id": "{project_directory_name}",
  "current_phase": "Scout",
  "phase_number": "1/7",
  "status": "researching",
  "progress_detail": "Analyzing task requirements",
  "test_iteration": 0,
  "phases_completed": [],
  "started_at": "{ISO timestamp}",
  "last_updated": "{ISO timestamp}"
}
```

**Optimized:**
```
Schema: session-summary.json (see docs/SESSION_SUMMARY_SCHEMA.md)
Fields: session_id, current_phase, phase_number, status, progress_detail, test_iteration, phases_completed, started_at, last_updated
```

**Savings:** ~400 tokens (across all JSON examples)

**Risk:** Low (model understands schema references)

---

## Phase 7: Instruction Hierarchy (~600 tokens)

### Concept: Progressive Disclosure with References

**Current Issue:** All details inline, even rare edge cases

**Example - Current:**
```
**E2E Testing for SPAs (MANDATORY for web apps):**
SPAs MUST have at least ONE E2E test that:
- Starts actual dev server (NOT mocked)
- Opens real browser (Playwright/Cypress, NOT jsdom)
- Navigates to app URL
- Waits for content to load
- Checks for console errors
- Tests key user interaction (click, input, navigation)

**Why this is critical:**
- Unit tests DON'T catch: CORS errors, infinite loops, broken clicks
- Integration tests DON'T catch: Real browser issues, API integration
- E2E tests catch 80% of production bugs
- ONE simple E2E test would have caught ALL 4 flight tracker issues

**Example E2E test (Playwright):**
[30 lines of example code]
```

**Optimized:**
```
**E2E Testing for SPAs:** MANDATORY. Real browser (Playwright/Cypress), real server, tests user interaction. See Appendix E for rationale and examples.
```

**Savings:** ~600 tokens (across all detailed sections)

**Risk:** Low (details available on reference)

---

## Phase 8: Conditional Instructions (~500 tokens)

### Concept: Load Instructions Only When Relevant

**Current Issue:** React-specific instructions always loaded, even for Python projects

**Solution:** Conditional blocks based on detected project type

**Example:**
```
{{IF project_type=react}}
**React State Architecture:**
- When to use useEffect vs useCallback vs useMemo
- Initialization patterns (mount-only effects with empty deps [])
...
{{ENDIF}}
```

**Implementation:** Pre-process based on codebase detection

**Savings:** ~500 tokens for non-React projects

**Risk:** Medium (requires preprocessing logic)

---

## Phase 9: External Knowledge Base (~1,000 tokens)

### Concept: Move Pattern Library to MCP Resource

**Current Issue:** Pattern examples and best practices in prompt

**Solution:** Store in external MCP resource, reference by ID

**Example:**

**Current (in prompt):**
```
Pattern ID: react-useeffect-infinite-loop

For EVERY useEffect in code, validate:
- Does effect call setState/action that updates a dependency? → INFINITE LOOP RISK
- If effect modifies state, is that state in dependency array? → REMOVE IT
...
[20 more lines]
```

**Optimized (in prompt):**
```
Check patterns: react-useeffect-infinite-loop, cors-external-api, e2e-testing-spa
(Details: read_global_patterns() MCP tool)
```

**External storage:**
- `~/.context-foundry/patterns/react-patterns.json`
- `~/.context-foundry/patterns/cors-patterns.json`
- `~/.context-foundry/patterns/testing-patterns.json`

**Savings:** ~1,000 tokens

**Benefits:**
- Patterns can be updated without prompt changes
- Patterns grow over time without bloating prompt
- Shared across all projects

**Risk:** Low (MCP already used for patterns)

---

## Cumulative Advanced Savings

| Optimization | Tokens Saved | Risk | Effort |
|--------------|--------------|------|--------|
| Modular architecture | 1,500 | Medium | 6-8h |
| Semantic compression | 800 | Medium | 4-6h |
| Instruction hierarchy | 600 | Low | 3-4h |
| Conditional instructions | 500 | Medium | 4-5h |
| JSON schema references | 400 | Low | 1-2h |
| External knowledge base | 1,000 | Low | 3-4h |
| **TOTAL** | **4,800** | - | **22-29h** |

---

## Recommended Roadmap

### Short-term (v1.2.0 - v1.4.0)
Focus on **Phase 2** optimizations:
- Target: 7,600 tokens (~30% reduction)
- Risk: Low-Medium
- Effort: 6-8 hours total
- Backward compatible

### Medium-term (v2.0.0)
Implement selected **Phase 3** optimizations:
1. ✅ External knowledge base (1,000 tokens, low risk)
2. ✅ JSON schema references (400 tokens, low risk)
3. ✅ Instruction hierarchy (600 tokens, low risk)

- Target: 5,600 tokens (~48% reduction)
- Risk: Medium
- Effort: 8-10 hours

### Long-term (v2.5.0)
Major architectural changes:
1. ✅ Modular architecture (1,500 tokens, medium risk)
2. ✅ Semantic compression (800 tokens, medium risk)

- Target: 3,300 tokens (~70% reduction!)
- Risk: High
- Effort: 10-14 hours
- Requires extensive testing

---

## Innovation Opportunities

### 1. Prompt Caching (Claude 3.5+)
**Concept:** Cache static portions of prompt

Claude 3.5 Sonnet supports prompt caching:
- Cache: Core instructions, pattern library, examples (never changes)
- Dynamic: Mode-specific instructions, project context (changes per build)

**Benefits:**
- 90% cache hit rate = 90% token cost reduction
- Even faster response times

**Implementation:**
```python
# Cache static content
cache_key = "orchestrator-core-v1.2.0"

# Build prompt with cache
prompt = {
    "cached": read_cached_prompt(cache_key),
    "dynamic": f"Task: {task_description}\nMode: {mode}"
}
```

**Potential savings:** ~9,000 cached tokens per build after first!

### 2. RAG-based Pattern Retrieval
**Concept:** Embed pattern library, retrieve relevant patterns only

Instead of including all patterns:
1. Embed pattern library in vector DB
2. Detect project characteristics (React? CORS? E2E?)
3. Retrieve only relevant patterns
4. Include in prompt

**Savings:** Include 3-5 patterns instead of 20 = ~600 tokens

### 3. Prompt Compression Models
**Concept:** Use LongLLMLingua or similar to compress prompt

Tools like LongLLMLingua can compress prompts by 50-80% while maintaining semantic meaning.

**Example:**
- Input: 10,000 tokens
- Compressed: 3,000 tokens
- Quality: 95%+ task performance maintained

**Caveat:** Requires validation that compressed prompt works correctly

---

## Decision Framework

**Choose optimization based on:**

| Criteria | Phase 2 | Phase 3 | Phase 9 | Prompt Caching |
|----------|---------|---------|---------|----------------|
| Token savings | 2,000+ | 2,000+ | 1,000+ | 9,000+ (cache) |
| Implementation effort | Low | Medium | Low | Medium |
| Risk | Low | Medium | Low | Low |
| Backward compatible | Yes | No | Yes | Yes |
| Requires testing | 5-10 builds | 20+ builds | 10 builds | 5 builds |

**Recommendation:**
1. **Now:** Complete Phase 2 (v1.2.0 - v1.4.0)
2. **Next:** Implement prompt caching (v2.0.0) - biggest ROI
3. **Then:** External knowledge base (v2.1.0)
4. **Finally:** Modular architecture (v2.5.0) if needed

---

## ROI Analysis

### Phase 2 Optimizations (v1.2.0 - v1.4.0)
- **Effort:** 6-8 hours
- **Savings:** 2,000 tokens/build
- **100 builds:** 200,000 tokens saved = $0.60
- **1,000 builds:** 2,000,000 tokens = $6.00

### Prompt Caching (v2.0.0)
- **Effort:** 8-10 hours (implementation + testing)
- **Savings:** ~9,000 tokens/build (after cache warm)
- **100 builds:** 900,000 tokens saved = **$2.70**
- **1,000 builds:** 9,000,000 tokens = **$27.00**

**Winner:** Prompt caching has best ROI by far!

---

**Status:** Analysis complete
**Recommended:** Implement Phase 2, then evaluate prompt caching
