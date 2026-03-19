# Context Foundry vs Claude Certified Architect -- Alignment Matrix

Source: Claude Certified Architect -- Foundations Certification Exam Guide (Anthropic, 2025)

Three categories:
- **Implemented** -- Foundry already does this
- **N/A** -- Applies to Agent SDK / API applications, not a build-loop harness
- **Opportunity** -- Applicable to foundry but not yet implemented

---

## Domain 1: Agentic Architecture & Orchestration (27%)

| Task | Principle | Foundry Status | Evidence / Notes |
|------|-----------|----------------|------------------|
| 1.1 | Agentic loop lifecycle (stop_reason, tool_use vs end_turn) | **Implemented** | `agent.rs:38` -- parses stream-json events, loops on tool_use, terminates on end_turn |
| 1.1 | Model-driven decision-making vs pre-configured decision trees | **Implemented** | Agents choose their own tools; foundry provides role prompts, not tool sequences |
| 1.1 | Avoid anti-patterns: parsing natural language for termination, arbitrary iteration caps | **Implemented** | Uses stream-json structured events, not text parsing. Agent timeout is a safety net, not a stop mechanism |
| 1.2 | Hub-and-spoke coordinator with isolated subagent context | **Implemented** | `app/build.rs` orchestrates scout/planner/builder/reviewer as isolated CLI invocations. No shared conversation history between agents |
| 1.2 | Coordinator handles task decomposition, delegation, result aggregation | **Implemented** | Build loop decomposes via TASKS.md, delegates to stage-specific agents, aggregates via .buildloop/ artifacts |
| 1.3 | Subagent context must be explicitly provided, not inherited | **Implemented** | Each agent is a fresh `claude` CLI invocation. Scout report, plan, and build claims are passed as file references, not conversation history |
| 1.3 | AgentDefinition with descriptions, system prompts, tool restrictions | **Implemented** | `prompts.rs` defines per-role prompts; `agent.rs:562` supports `allowed_tools` per invocation |
| 1.3 | Fork-based session management | **N/A** | Foundry spawns fresh processes, not Claude Code sessions. Fork semantics don't apply |
| 1.4 | Programmatic enforcement (hooks, prerequisite gates) vs prompt-based guidance | **Implemented** | `gate_builder` and `gate_reviewer` in `app/build.rs:73,96` block execution if preconditions aren't met. Extension validation gate at `build.rs:1513` |
| 1.4 | Deterministic compliance for critical operations | **Implemented** | Gates are code, not prompts. Plan must have `## File Operations` and `## Verification` or builder won't run |
| 1.4 | Structured handoff protocols | **Implemented** | Each stage writes structured artifacts (.buildloop/*.md) that downstream stages consume |
| 1.5 | Agent SDK hooks (PostToolUse) for tool call interception | **N/A** | Foundry uses Claude Code CLI, not the Agent SDK. No hook interception layer |
| 1.5 | Hooks for deterministic guarantees vs prompt instructions for probabilistic compliance | **Partially Implemented** | Foundry uses gates (deterministic) for stage ordering, but no tool-call-level interception within an agent's session |
| 1.6 | Fixed sequential pipelines vs dynamic adaptive decomposition | **Implemented** | Fixed pipeline (scout > plan > build > verify) with adaptive elements (complexity-based planner skip, retry-with-error-feedback on gate failure) |
| 1.6 | Prompt chaining for multi-step workflows | **Implemented** | Each pipeline stage chains into the next via file artifacts. Reviewer findings chain into fixer |
| 1.6 | Adaptive investigation plans based on discoveries | **Partially Implemented** | Discovery agent adapts task generation based on codebase state, but within a stage, agents don't dynamically spawn sub-investigations |
| 1.7 | Named session resumption (--resume) | **N/A** | Foundry agents are stateless one-shot invocations. State lives in .buildloop/ files, not Claude sessions |
| 1.7 | fork_session for parallel exploration | **N/A** | Not applicable -- foundry doesn't use Claude Code sessions |
| 1.7 | Crash recovery via structured state persistence | **Implemented** | `.buildloop/` artifacts persist across crashes. TASKS.md tracks SPID progress. Pipeline resumes from last incomplete task |

## Domain 2: Tool Design & MCP Integration (18%)

| Task | Principle | Foundry Status | Evidence / Notes |
|------|-----------|----------------|------------------|
| 2.1 | Clear tool descriptions with input formats and boundaries | **N/A** | Foundry doesn't define MCP tools for agents -- agents use Claude Code's built-in tools |
| 2.2 | Structured error responses (isError, errorCategory, isRetryable) | **N/A** | Foundry's MCP server tools (read_global_patterns, etc.) exist but are for external use, not internal agent orchestration |
| 2.3 | Scoped tool access per agent role | **Implemented** | `agent.rs:562` -- `allowed_tools` parameter restricts tools per invocation. Skills use `allowed-tools` frontmatter |
| 2.3 | Too many tools degrades selection reliability | **Implemented** | Reviewer is read-only (no Write/Edit). Skills restrict to 3-4 tools each |
| 2.4 | MCP server scoping (project .mcp.json vs user ~/.claude.json) | **N/A** | Foundry doesn't configure MCP servers for its agents |
| 2.4 | MCP resources as content catalogs | **Opportunity** | Foundry could expose pattern catalog, extension index, or task queue as MCP resources so agents can browse without tool calls |
| 2.5 | Effective use of built-in tools (Read, Write, Edit, Bash, Grep, Glob) | **Implemented** | Agent prompts guide tool selection: reviewer uses read-only tools, builder uses all, scout does investigation |

## Domain 3: Claude Code Configuration & Workflows (20%)

| Task | Principle | Foundry Status | Evidence / Notes |
|------|-----------|----------------|------------------|
| 3.1 | CLAUDE.md hierarchy (user > project > directory) | **Implemented** | Agents inherit CLAUDE.md via Claude Code's normal loading. Foundry appends orchestration override to prevent conflicts (`prompts.rs:wrap_with_extensions`) |
| 3.1 | .claude/rules/ for path-scoped conventions | **Implemented** | 6 rule files with `paths:` frontmatter scoping. README documents the system |
| 3.1 | @import for modular CLAUDE.md | **Not Used** | Foundry's rules are already split into `.claude/rules/`. No @import needed, but could be useful for extensions |
| 3.2 | Custom slash commands in .claude/commands/ | **Not Used** | `.claude/commands/` exists but is empty. Skills in `.claude/skills/` serve this purpose instead |
| 3.2 | Skills with SKILL.md, context: fork, allowed-tools | **Implemented** | 3 skills (audit, scout, extract-patterns) with fork context and scoped tools |
| 3.3 | Path-specific rules with YAML frontmatter | **Implemented** | All 6 rule files use `paths:` frontmatter for conditional loading |
| 3.4 | Plan mode vs direct execution | **Implemented** | Foundry's planner stage IS plan mode -- it writes a plan before the builder executes. Complexity classifier can skip planning for simple tasks |
| 3.5 | Iterative refinement with concrete I/O examples | **Implemented** | Reviewer prompt includes few-shot severity examples. Pattern extraction prompt includes JSON template with example |
| 3.5 | Test-driven iteration | **Implemented** | Builder runs build/test commands. Reviewer re-runs them independently. Fixer iterates on failures |
| 3.6 | CI/CD integration (-p flag, --output-format json) | **Partially Implemented** | `--no-tui` headless mode exists for CI. Uses `--output-format stream-json`. No `--json-schema` structured output for CI consumption |
| 3.6 | Session context isolation -- fresh reviewer catches what builder misses | **Implemented** | Core design principle. Verify agent runs in completely separate CLI invocation. README documents this explicitly |

## Domain 4: Prompt Engineering & Structured Output (20%)

| Task | Principle | Foundry Status | Evidence / Notes |
|------|-----------|----------------|------------------|
| 4.1 | Explicit criteria over vague instructions | **Implemented** | Reviewer prompt defines explicit severity criteria with examples: HIGH=security/crashes, MEDIUM=error-handling, LOW=style. "What to report" and "what to skip" lists |
| 4.1 | Explicit criteria reduce false positives vs "be conservative" | **Implemented** | Reviewer has categorical criteria, not confidence-based filtering |
| 4.2 | Few-shot examples for output consistency | **Implemented** | Reviewer prompt has few-shot severity examples. Pattern extractor has JSON template. Builder prompt has build-claims format |
| 4.2 | Few-shot for ambiguous-case handling | **Opportunity** | Reviewer could benefit from few-shot examples showing borderline HIGH vs MEDIUM classifications |
| 4.3 | Structured output via tool_use with JSON schemas | **N/A** | Foundry uses Claude Code CLI, not the API. No tool_use/JSON schema enforcement |
| 4.3 | tool_choice configuration | **N/A** | CLI invocation, not API |
| 4.4 | Retry-with-error-feedback | **Implemented** | Gate failure triggers planner retry with validation error appended (`build.rs:1533-1594`). Agent timeout triggers retry (`agent.rs:78,291`) |
| 4.4 | Feedback loops -- tracking which patterns trigger findings | **Implemented** | "Applied" counter tracks patterns whose keywords appeared in agent output. Patterns with frequency 3+ auto-promote |
| 4.5 | Batch processing (Message Batches API) | **N/A** | Foundry processes tasks sequentially through Claude Code CLI, not the API batch endpoint |
| 4.6 | Multi-instance review -- independent reviewer catches what generator misses | **Implemented** | Core architecture. Verify agent is a fresh CLI invocation with zero shared context from builder. README explicitly cites this as the Anthropic-recommended pattern |
| 4.6 | Multi-pass review (per-file local + cross-file integration) | **Opportunity** | Current reviewer does a single pass over all changes. Could split into per-file analysis + cross-file integration pass for large changesets |

## Domain 5: Context Management & Reliability (15%)

| Task | Principle | Foundry Status | Evidence / Notes |
|------|-----------|----------------|------------------|
| 5.1 | Lost-in-the-middle effect mitigation | **Implemented** | Scout report structures output with "Key Facts" first (beginning bias) and "Risks" last (recency bias). See `prompts.rs` bootstrap scout |
| 5.1 | Trimming verbose tool output | **Opportunity** | Agents receive full tool output. No post-processing to trim irrelevant fields before they accumulate in context |
| 5.1 | Persistent "case facts" outside summarized history | **Implemented** | .buildloop/ files persist structured state (scout report, plan, claims, review) outside conversation context |
| 5.2 | Escalation patterns (human-in-the-loop) | **Implemented** | Review mode pauses after each task for human approval. WIP commits + GitHub issues escalate failures to humans |
| 5.2 | Escalation triggers: inability to make progress, not just complexity | **Implemented** | Verify gate failure after fixer retry produces WIP commit + issue. Discovery backs off with increasing cooldown when nothing found |
| 5.3 | Structured error propagation across multi-agent systems | **Partially Implemented** | Agent failures are caught and logged. Retry logic exists. But error context passed between stages is minimal -- just pass/fail, not structured failure metadata |
| 5.3 | Distinguish access failures from valid empty results | **Opportunity** | Agent timeout vs clean completion vs error are tracked, but downstream stages don't get structured error context to adapt their behavior |
| 5.4 | Context degradation in extended sessions | **Implemented** | Each agent is a fresh session -- no context degradation within the pipeline. Long sessions are architecturally impossible |
| 5.4 | Scratchpad files for persisting findings across context boundaries | **Implemented** | `.buildloop/scout-report.md`, `current-plan.md`, `build-claims.md`, `review-report.md` are exactly this pattern |
| 5.4 | Crash recovery via structured state exports | **Implemented** | TASKS.md tracks SPID progress. .buildloop/ artifacts survive crashes. Pipeline resumes at last incomplete stage |
| 5.5 | Human review workflows and confidence calibration | **Partially Implemented** | Review mode creates PRs for human review. Severity calibration exists (HIGH/MEDIUM/LOW). No field-level confidence scores on individual findings |
| 5.6 | Information provenance in multi-source synthesis | **Opportunity** | Pattern `learned_from` tracks origin task. But reviewer findings don't carry provenance (which file evidence came from which analysis step) |

---

## Summary

| Category | Count | % |
|----------|-------|---|
| **Implemented** | 33 | 62% |
| **Partially Implemented** | 6 | 11% |
| **Opportunity** | 7 | 13% |
| **N/A** (Agent SDK / API specific) | 7 | 13% |
| **Not Used** (valid alternative exists) | 2 | 4% |

## Top Opportunities (ranked by impact)

1. **Structured error propagation** (5.3) -- Pass structured failure context (what failed, what was attempted, partial results) between pipeline stages instead of just pass/fail. Enables smarter retry and fixer behavior.

2. **Multi-pass review for large changesets** (4.6) -- Split reviewer into per-file local analysis + cross-file integration pass. Prevents attention dilution when a task touches 10+ files.

3. **Verbose tool output trimming** (5.1) -- Post-process agent tool results to strip irrelevant fields before they accumulate in context. Particularly valuable for build output and test results that include noisy warnings.

4. **MCP resources for content catalogs** (2.4) -- Expose the pattern catalog and extension index as MCP resources so agents can browse available knowledge without exploratory tool calls.

5. **Few-shot borderline severity examples** (4.2) -- Add examples to the reviewer prompt showing borderline cases between HIGH and MEDIUM to improve classification consistency.

6. **Reviewer finding provenance** (5.6) -- Attach source evidence (file, line, analysis step) to each finding so downstream consumers (fixer, issue creator) have full context.

7. **Confidence scores on findings** (5.5) -- Add per-finding confidence to enable calibrated routing: high-confidence findings auto-fix, low-confidence findings route to human review.
