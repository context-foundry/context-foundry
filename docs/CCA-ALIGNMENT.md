# CCA Alignment Matrix

Context Foundry's architecture maps to the principles in Anthropic's [Claude Certified Architect -- Foundations](CCA-Exam-Guide.pdf) exam guide. This document cross-references each exam principle to specific code locations in the codebase.

An interactive version with filtering is available at [`docs/cca-alignment.html`](cca-alignment.html).

## Summary

| | Count |
|---|---|
| Implemented | 43 |
| Partial | 3 |
| N/A (architectural mismatch) | 7 |
| Not Used (alternative chosen) | 2 |
| Open Opportunities | 0 |

---

## Domain 1: Agentic Architecture & Orchestration (27%)

| Principle | Status | Evidence |
|---|---|---|
| Agentic loop lifecycle (stop_reason, tool_use vs end_turn) | Implemented | `agent.rs:38` -- parses stream-json events, loops on tool_use |
| Model-driven decision-making vs pre-configured decision trees | Implemented | Agents choose their own tools; foundry provides role prompts, not tool sequences |
| Avoid anti-patterns: NL parsing for termination, arbitrary iteration caps | Implemented | Uses stream-json structured events. Timeout is a safety net, not a stop mechanism |
| Hub-and-spoke coordinator with isolated subagent context | Implemented | `app/build.rs` orchestrates agents as isolated CLI invocations with no shared history |
| Coordinator handles decomposition, delegation, result aggregation | Implemented | TASKS.md for decomposition, stage agents for delegation, .buildloop/ for aggregation |
| Subagent context must be explicitly provided, not inherited | Implemented | Each agent is a fresh CLI process. Artifacts passed as file references |
| AgentDefinition with descriptions, prompts, tool restrictions | Implemented | `prompts.rs` per-role prompts; `agent.rs:562` allowed_tools per invocation |
| Fork-based session management | N/A | Foundry spawns fresh processes, not Claude Code sessions |
| Programmatic enforcement (hooks, prerequisite gates) | Implemented | `gate_builder` and `gate_reviewer` in `build.rs:73,96`. Extension gate at `build.rs:1513` |
| Deterministic compliance for critical operations | Implemented | Gates are code, not prompts. Plan must have File Operations + Verification sections |
| Structured handoff protocols between stages | Implemented | Each stage writes structured .buildloop/ artifacts consumed by downstream stages |
| Agent SDK hooks (PostToolUse) for tool call interception | N/A | Uses Claude Code CLI, not Agent SDK |
| Hooks for deterministic guarantees vs prompt-based compliance | Partial | Gates enforce stage ordering; no tool-call-level interception within a session |
| Fixed sequential pipelines vs dynamic adaptive decomposition | Implemented | Fixed pipeline with adaptive elements (complexity-based skip, retry-with-feedback) |
| Prompt chaining for multi-step workflows | Implemented | Stages chain via file artifacts. Reviewer findings chain into fixer |
| Adaptive investigation plans based on discoveries | Partial | Discovery agent adapts task generation, but agents don't spawn sub-investigations |
| Named session resumption (--resume) | N/A | Agents are stateless one-shot invocations. State lives in .buildloop/ files |
| fork_session for parallel exploration | N/A | Not applicable -- foundry doesn't use Claude Code sessions |
| Crash recovery via structured state persistence | Implemented | .buildloop/ artifacts + TASKS.md SPID progress survive crashes |

## Domain 2: Tool Design & MCP Integration (18%)

| Principle | Status | Evidence |
|---|---|---|
| Clear tool descriptions with input formats and boundaries | N/A | Agents use Claude Code's built-in tools, not custom MCP tools |
| Structured error responses (isError, errorCategory, isRetryable) | N/A | MCP tools exist for external use, not internal agent orchestration |
| Scoped tool access per agent role | Implemented | `agent.rs:562` allowed_tools. Skills restrict to 3-4 tools each |
| Too many tools degrades selection reliability | Implemented | Reviewer is read-only. Skills restrict to role-appropriate tools |
| MCP server scoping (project vs user level) | N/A | Foundry doesn't configure MCP servers for its agents |
| MCP resources as content catalogs | Implemented | `mcp.rs:125` pattern catalog + `mcp.rs:131` extension index as browsable MCP resources via `foundry://` URIs |
| Effective use of built-in tools (Read, Write, Edit, Bash, Grep, Glob) | Implemented | Agent prompts guide tool selection per role |

## Domain 3: Claude Code Configuration & Workflows (20%)

| Principle | Status | Evidence |
|---|---|---|
| CLAUDE.md hierarchy (user > project > directory) | Implemented | Agents inherit CLAUDE.md via normal loading. Foundry appends orchestration override |
| .claude/rules/ for path-scoped conventions | Implemented | 6 rule files with paths: frontmatter scoping |
| @import for modular CLAUDE.md | Not Used | Rules already split into .claude/rules/. Could be useful for extensions |
| Custom slash commands in .claude/commands/ | Not Used | Skills in .claude/skills/ serve this purpose instead |
| Skills with SKILL.md, context: fork, allowed-tools | Implemented | 3 skills (audit, scout, extract-patterns) with fork context and scoped tools |
| Path-specific rules with YAML frontmatter | Implemented | All 6 rule files use paths: frontmatter for conditional loading |
| Plan mode vs direct execution | Implemented | Planner stage IS plan mode. Complexity classifier can skip for simple tasks |
| Iterative refinement with concrete I/O examples | Implemented | Few-shot severity examples in reviewer. JSON template in pattern extractor |
| Test-driven iteration | Implemented | Builder runs tests. Reviewer re-runs independently. Fixer iterates on failures |
| CI/CD integration (--output-format json) | Implemented | `--output-format json` on `foundry run --no-tui`. SessionReport with tasks/session/config. Schema: `docs/ci-output-schema.json` |
| Session context isolation -- fresh reviewer | Implemented | Core design principle. Verify agent is a completely separate CLI invocation |

## Domain 4: Prompt Engineering & Structured Output (20%)

| Principle | Status | Evidence |
|---|---|---|
| Explicit criteria over vague instructions | Implemented | Reviewer defines severity criteria with examples. "What to report" and "what to skip" lists |
| Explicit criteria reduce false positives | Implemented | Categorical criteria, not confidence-based filtering |
| Few-shot examples for output consistency | Implemented | Reviewer severity examples. Pattern extractor JSON template. Build-claims format |
| Few-shot for ambiguous-case handling | Implemented | `prompts.rs:572-602` three borderline severity examples: unchecked file read = HIGH, test-only return value = LOW, unwrap on constant = SKIP |
| Structured output via tool_use with JSON schemas | N/A | Uses Claude Code CLI, not the API |
| Retry-with-error-feedback | Implemented | Gate failure triggers planner retry with validation error appended. Agent timeout retry |
| Feedback loops -- tracking which patterns trigger findings | Implemented | "Applied" counter tracks patterns in agent output. Frequency 3+ auto-promotes |
| Batch processing (Message Batches API) | N/A | Sequential processing via CLI, not API batch endpoint |
| Multi-instance review -- independent reviewer | Implemented | Core architecture. Fresh CLI invocation with zero shared context from builder |
| Multi-pass review (per-file + cross-file integration) | Implemented | `review.rs:269` run_multipass_review splits into per-file analysis + cross-file integration pass when files exceed `review_multipass_threshold` (default 8) |

## Domain 5: Context Management & Reliability (15%)

| Principle | Status | Evidence |
|---|---|---|
| Lost-in-the-middle effect mitigation | Implemented | Scout report: Key Facts first (beginning bias), Risks last (recency bias) |
| Trimming verbose tool output before context accumulation | Implemented | `agent.rs:1505` truncate_for_preview trims tool output to 200 chars. Build/test results trimmed between builder and reviewer stages |
| Persistent structured state outside conversation history | Implemented | .buildloop/ files persist scout report, plan, claims, review across context boundaries |
| Escalation patterns (human-in-the-loop) | Implemented | Review mode pauses for approval. WIP commits + GitHub issues escalate failures |
| Escalation on inability to progress, not just complexity | Implemented | Verify failure after fixer retry = WIP + issue. Discovery backs off when nothing found |
| Structured error propagation across multi-agent systems | Implemented | `context.rs:35` StageResult struct with failure_type, attempted_action, partial_results, suggestions. Fixer receives structured context |
| Distinguish access failures from valid empty results | Implemented | `context.rs:13` FailureType enum: Timeout, Crash, GateFail, ReviewFail, RateLimited, StopRequested |
| Context degradation in extended sessions | Implemented | Each agent is a fresh session. Long sessions are architecturally impossible |
| Scratchpad files for persisting findings | Implemented | .buildloop/ artifacts are exactly this pattern |
| Crash recovery via structured state exports | Implemented | TASKS.md SPID progress + .buildloop/ artifacts survive crashes |
| Human review workflows and confidence calibration | Implemented | Review mode creates PRs with polling. `review.rs:714` confidence scores (0.0-1.0) with `config.rs:199` configurable threshold |
| Information provenance in multi-source synthesis | Implemented | `review.rs:675` source_evidence field on every finding: snippet, line_range, reasoning chain. Fixer receives full provenance |
| Confidence scores for calibrated review routing | Implemented | `review.rs:714-758` per-finding confidence (0.0-1.0). Below `confidence_threshold` (default 0.5) flagged for manual review, not auto-fixed |

---

## Resolved Opportunities (Phase 13)

Seven gaps were identified during the initial audit and resolved in commits `55e2684` through `7b9bf8b`:

| Opportunity | Task | Commit | What was added |
|---|---|---|---|
| Structured error propagation | T13.1 | `55e2684` | StageResult struct + FailureType enum for typed failure context between stages |
| Multi-pass review | T13.2/T13.3 | `0ea2640` | Per-file analysis + cross-file integration when changeset > 8 files |
| Tool output trimming | T13.3 | `0ea2640` | truncate_for_preview strips verbose build/test output before reviewer |
| MCP content catalogs | T13.4 | `10d56df` | Pattern catalog + extension index as `foundry://` MCP resources |
| Borderline severity examples | T13.5 | `2a67cb6` | Three calibration examples (HIGH/MEDIUM/LOW boundary cases) in reviewer prompt |
| Finding provenance | T13.6 | `02fad70` | source_evidence field (snippet, line_range, reasoning) on every finding |
| Confidence scores | T13.7 | `7b9bf8b` | Per-finding confidence (0.0-1.0) with configurable routing threshold |

## Remaining Partials

Three principles have partial alignment due to architectural choices, not missing implementation:

| Principle | Why partial |
|---|---|
| Hooks for deterministic guarantees (1.5) | Gates enforce stage ordering, but no tool-call-level interception within an agent session (would require Agent SDK, not CLI) |
| Adaptive investigation plans (1.6) | Discovery adapts task generation, but individual agents don't spawn sub-investigations mid-session |
| *(none remaining in Domains 3-5)* | |
