# Agent Orchestration Framework Comparison

**Date:** 2026-03-22
**Subjects:** Context Foundry vs Citadel vs Gas City/Gastown
**Evaluator:** Claude Opus 4.6 (primary), Codex 5.4 (validation)

---

## Executive Summary

Three frameworks, three philosophies for the same problem: how do you make AI coding agents reliable at scale?

| | Context Foundry | Citadel | Gas City / Gastown |
|---|---|---|---|
| **One-liner** | Build loop engine with pattern learning | Campaign harness with cost-aware routing | Multi-agent workspace manager ("K8s for agents") |
| **Author** | snedea | Seth Gammon | Steve Yegge |
| **Language** | Rust (14K LOC) | JavaScript/Node.js | Go (large codebase) |
| **GitHub Stars** | ~small | ~125 | ~12,700 |
| **License** | MIT | MIT | MIT |
| **Agent Target** | Claude Code, Codex | Claude Code only | Claude Code, Copilot, Codex, Gemini |
| **Scale Model** | 1-2 agents per task (sequential pipeline) | 1-3 agents (Fleet parallelism) | 20-30+ agents (enterprise fleet) |

---

## 1. Architecture Philosophy

### Context Foundry: Isolated Pipeline Stages
The core bet is **isolated context windows**. Each SPID stage (Scout, Plan, Implement, Doubt) runs a fresh agent with only curated artifacts from the previous stage. No agent shares history with another. This prevents compounding hallucinations and makes each stage independently auditable.

The pipeline is **complexity-scaled**: simple tasks skip stages (rename/typo -> straight to builder), complex tasks get the full treatment. Learned doubt confidence can skip review for task shapes that pass consistently.

### Citadel: Cost-Aware Routing Ladder
The core bet is **right-sizing every request**. A 4-tier hierarchy (Skill -> Marshal -> Archon -> Fleet) routes tasks to the cheapest capable tier. Pattern matching handles 80% of routing at zero tokens; LLM fallback costs ~500 tokens for ambiguous requests.

Campaign persistence (markdown-based state files) enables multi-session work spanning days/weeks. Fleet agents coordinate via discovery briefs (~500 tokens each) shared between waves.

### Gas City: Primitive-Based Orchestration SDK
The core bet is **composable primitives at scale**. Five irreducible primitives (Bead Store, Event Bus, Config, Agent Protocol, Prompt Templates) compose into derived mechanisms (Messaging, Formulas, Dispatch, Health Patrol). Zero hardcoded roles -- all behavior is user-supplied configuration.

Designed for Stage 6-8 developers already running 20-30 parallel agents. Treats coordination, attribution, and state management as foundational rather than retrofit.

---

## 2. Feature Comparison Matrix

### 2.1 Pipeline / Workflow

| Feature | Context Foundry | Citadel | Gas City |
|---------|:-:|:-:|:-:|
| Named pipeline stages | SPID (4 stages) | 6-stage campaign | Formula steps (N stages) |
| Stage skip for simple tasks | Yes (complexity classifier) | Yes (Tier 0-2 pattern match) | No (user-defined) |
| Crash recovery / checkpoints | Yes (.buildloop/checkpoint.json) | Yes (campaign markdown) | Yes (bead state in git) |
| Prerequisite gates between stages | Programmatic (file existence + structure) | Prompt-based (skill protocol) | Dependency graph (step.needs) |
| Pipeline progress indicator | [SPID] 4-char in TASKS.md | Campaign status field | Molecule step status |
| Iterative fix loops | Reviewer -> Fixer loop (configurable N) | Circuit breaker (3 fail -> suggest, 5 -> escalate) | Convergence loops (bounded iterations) |
| Human approval gates | Review mode (PR-based) | Not documented | Not documented (possible via manual gate) |

### 2.2 Agent Management

| Feature | Context Foundry | Citadel | Gas City |
|---------|:-:|:-:|:-:|
| Max concurrent agents | 2 (dual-model arena) | 2-3 (Fleet) | 20-30+ |
| Agent isolation | Fresh CLI per stage | Git worktrees | Git worktrees + tmux sessions |
| Multi-model support | Claude + Codex side-by-side | Claude only | Claude, Copilot, Codex, Gemini |
| Agent health monitoring | Timeout + retry | Circuit breaker hook | 3-tier watchdog (Witness/Deacon/Dogs) |
| Agent communication | None (isolated by design) | Discovery briefs between waves | Mail (persistent) + Nudge (fire-and-forget) |
| Role-based tool scoping | Yes (Scout=Read, Builder=Read/Edit/Write) | Yes (skill protocol defines scope) | Yes (prompt templates per role) |
| Agent attribution/tracking | Task-level (SPID indicator) | Campaign-level | Per-action (first-class attribution) |

### 2.3 Knowledge & Learning

| Feature | Context Foundry | Citadel | Gas City |
|---------|:-:|:-:|:-:|
| Pattern extraction (post-task) | Yes (agent scans build artifacts) | No (manual skill creation) | No (event archival only) |
| Pattern matching | Keyword + Semantic (Ollama) | Not applicable | Not applicable |
| Pattern injection into prompts | Yes (planner + reviewer) | Via skill protocol | Via prompt templates |
| Frequency tracking | Yes (auto_apply at 3+) | No | No |
| Doubt confidence learning | Yes (skip review for proven task shapes) | No | No |
| Reusable knowledge format | JSON patterns | Markdown skills | TOML packs + formulas |
| Cross-project knowledge sharing | Global ~/.foundry/patterns/ | Copy .claude/ directory | Shareable packs (local/git) |
| Extension/domain system | Yes (6+ extensions with CLAUDE.md + patterns) | No (skill categories) | Packs (agent + formula bundles) |

### 2.4 Configuration & Setup

| Feature | Context Foundry | Citadel | Gas City |
|---------|:-:|:-:|:-:|
| Config format | JSON (.foundry.json) | JSON (harness.json + settings.json) | TOML (city.toml) |
| Config fields | 50+ | ~15 | Extensible (progressive activation) |
| Setup command | N/A (TUI startup screen) | `/do setup` (interactive) | `gt install` + `gt config` |
| Per-model configuration | Yes (per stage: scout_model, builder_model, etc.) | No (single model) | Yes (per agent) |
| Lifecycle hooks | No (pipeline handles lifecycle) | 8 hooks (post-edit, circuit-breaker, quality-gate, etc.) | Controller daemon (watch + reconcile) |
| Protected files | No | Yes (protect-files.js hook) | No (but scope claims prevent overlap) |
| Quality gates (automated) | Backpressure gates (programmatic) | Quality-gate.js hook (anti-pattern scan) | Health Patrol (liveness, drift detection) |

### 2.5 User Interface

| Feature | Context Foundry | Citadel | Gas City |
|---------|:-:|:-:|:-:|
| TUI | Yes (ratatui, 10fps, interactive) | No | Yes (bubbletea) |
| Web dashboard | No | No | Yes (`gc dashboard`) |
| HTTP API | No | No | Yes (OpenAPI spec) |
| Real-time agent output | Yes (PTY streaming to TUI) | Via Claude Code terminal | Yes (`gt feed`) |
| Hot-inject tasks | Yes (press 'i' during run) | Not documented | Via beads CLI (`bd create`) |
| Headless mode | Yes (`--no-tui`) | Yes (Claude Code terminal) | Yes (daemon mode) |

### 2.6 Git / CI Integration

| Feature | Context Foundry | Citadel | Gas City |
|---------|:-:|:-:|:-:|
| Auto-commit on task complete | Yes (feat/WIP prefix) | Via skill exit protocol | Not built-in (agent responsibility) |
| PR creation | Yes (review mode) | Not built-in | Refinery merge queue |
| Branch management | Auto-create per task (review mode) | Worktree branches (Fleet) | Rig branches + worktrees |
| Merge queue | No | No | Yes (Refinery, Bors-style bisecting) |
| Auto-push | Configurable (auto_push_remote) | Not documented | Not documented |

### 2.7 Scalability & Enterprise

| Feature | Context Foundry | Citadel | Gas City |
|---------|:-:|:-:|:-:|
| Target user | Solo developer / small team | Solo developer / small team | Team / enterprise (20-30 agents) |
| Session providers | PTY, Tmux | Claude Code only | Tmux, subprocess, Kubernetes, custom |
| Multi-project | Sequential (one project at a time) | Sequential | Yes (rigs = multiple repos) |
| Federated / distributed | No | No | Yes (Wasteland via DoltHub) |
| Scheduling / capacity | pause_between_tasks_secs | Not documented | Orders with 5 gate types (cron, cooldown, condition, event, manual) |
| Observability | TUI + planned Observatory | Telemetry.js | OpenTelemetry (metrics, traces, logs) |

---

## 3. Strengths & Weaknesses

### Context Foundry

**Strengths:**
- Isolated context windows prevent compounding errors (strongest architectural alignment with CCA principles)
- Pattern learning is genuinely novel -- the system gets smarter over time
- Complexity-scaled pipeline avoids wasting tokens on trivial tasks
- Dual-model arena enables objective Claude vs Codex comparison
- Doubt confidence learning reduces unnecessary review cycles
- Semantic matching via Ollama adds conceptual pattern discovery
- Rich TUI with real-time streaming

**Weaknesses:**
- Single-project, single-operator focus -- no multi-agent fleet coordination
- No lifecycle hooks (relies entirely on pipeline structure)
- No web dashboard or HTTP API
- Agent communication is zero (by design, but limits collaboration patterns)
- Extension system is manual (copy files, no remote pack fetching)
- Smaller community (fewer external contributors)

### Citadel

**Strengths:**
- Cost-aware routing is genuinely innovative (zero-token pattern matching for 80% of tasks)
- Campaign persistence across sessions is production-hardened
- 8 lifecycle hooks provide automatic quality enforcement
- Fleet parallelism with discovery relay prevents redundant work
- Zero external dependencies (pure orchestration layer)
- Clean skill protocol (5-part structure) is easy to author and extend
- Well-documented setup flow

**Weaknesses:**
- Claude Code only -- no multi-model support
- No pattern learning or knowledge extraction
- No TUI (relies on Claude Code's own terminal)
- No semantic matching or AI-enhanced routing
- Smaller community than Gas City
- Skills are manually authored -- no automatic extraction from completed work

### Gas City / Gastown

**Strengths:**
- Scale: designed for 20-30+ concurrent agents from day one
- Multi-agent, multi-model, multi-project support
- Composable primitive architecture is theoretically sound
- First-class attribution and provenance tracking
- Health Patrol with Erlang/OTP-style supervision
- Merge queue (Refinery) with Bors-style bisecting
- Kubernetes session provider for distributed deployments
- Federated networks (Wasteland) for multi-org collaboration
- Largest community (12K+ stars)
- Comprehensive documentation

**Weaknesses:**
- No pattern learning or knowledge extraction system
- Complexity: 9 core concepts + deep configuration surface
- No complexity-scaled pipeline (all tasks get same treatment)
- Steeper learning curve (Go toolchain, Dolt, tmux, beads CLI)
- No dual-model arena for objective comparison
- No doubt confidence learning
- Event bus is append-only with no built-in analytics

---

## 4. Philosophical Differences

| Dimension | Context Foundry | Citadel | Gas City |
|-----------|---|---|---|
| **Core metaphor** | Assembly line (stages) | Military campaign (tiers) | City governance (primitives) |
| **Knowledge** | Machine-learned patterns | Human-authored skills | Configuration-driven packs |
| **Agent model** | Isolated specialists | Coordinated teams | Autonomous citizens |
| **State** | File-based (.buildloop/) | Markdown-based (.planning/) | Git-backed (beads + hooks) |
| **Scaling strategy** | Pipeline efficiency | Cost optimization | Fleet parallelism |
| **Quality assurance** | Doubt loop (fresh-eyes audit) | Circuit breaker + quality hooks | Health Patrol + watchdogs |
| **Learning** | Automatic (patterns + doubt confidence) | Manual (skill authoring) | Manual (pack authoring) |

---

## Appendix A: CCA (Claude Certified Architect) Alignment Analysis

The Claude Certified Architect exam tests 5 competency domains. Here's how each framework aligns:

### A.1 Agentic Architecture & Orchestration (27% of exam)

| CCA Principle | Context Foundry | Citadel | Gas City |
|---------------|:-:|:-:|:-:|
| Agent loop design | Strong (SPID pipeline with explicit stages) | Strong (4-tier routing ladder) | Strong (controller daemon + dispatch) |
| Orchestration patterns | Strong (sequential pipeline with gates) | Strong (campaign lifecycle) | Very Strong (composable primitives) |
| Failure handling | Strong (checkpoint recovery, fixer loops) | Strong (circuit breaker, escalation) | Very Strong (Health Patrol, crash quarantine) |
| Context isolation | Very Strong (core architectural principle) | Moderate (worktree isolation) | Moderate (session isolation) |
| **Subtotal** | **Very Strong** | **Strong** | **Very Strong** |

### A.2 Claude Code Configuration & Workflows (20%)

| CCA Principle | Context Foundry | Citadel | Gas City |
|---------------|:-:|:-:|:-:|
| Claude Code integration | Strong (PTY spawning, tool scoping) | Very Strong (native hooks, skills) | Moderate (one of many providers) |
| Settings & hooks usage | Weak (no Claude Code hooks) | Very Strong (8 lifecycle hooks) | Strong (hooks hierarchy) |
| Workflow automation | Strong (TUI-driven, auto-mode) | Strong (/do routing) | Strong (orders + gates) |
| **Subtotal** | **Moderate** | **Very Strong** | **Strong** |

### A.3 Prompt Engineering & Structured Output (20%)

| CCA Principle | Context Foundry | Citadel | Gas City |
|---------------|:-:|:-:|:-:|
| Prompt design | Very Strong (32 role-specific prompt functions) | Strong (5-part skill protocol) | Strong (Go templates) |
| Structured output | Strong (build-claims.md, review-report.md) | Moderate (HANDOFF blocks) | Strong (bead schema) |
| Context management | Very Strong (curated artifacts per stage) | Moderate (campaign files) | Strong (prompt templates with variables) |
| Pattern injection | Very Strong (keyword + semantic matching) | N/A | N/A |
| **Subtotal** | **Very Strong** | **Strong** | **Strong** |

### A.4 Tool Design & MCP Integration (18%)

| CCA Principle | Context Foundry | Citadel | Gas City |
|---------------|:-:|:-:|:-:|
| MCP server | Yes (pattern catalog + extension index) | No | No |
| Tool boundary design | Strong (per-role tool whitelists) | Strong (skill scope) | Moderate (agent-level) |
| Tool composition | Moderate (pipeline stages) | Strong (skill chaining) | Very Strong (primitive composition) |
| **Subtotal** | **Strong** | **Moderate** | **Moderate** |

### A.5 Context Management & Reliability (15%)

| CCA Principle | Context Foundry | Citadel | Gas City |
|---------------|:-:|:-:|:-:|
| Token budget management | Very Strong (complexity scaling, pattern caps) | Very Strong (cost-aware routing) | Moderate (no explicit budget mgmt) |
| Crash resilience | Strong (checkpoint.json) | Strong (campaign markdown) | Very Strong (git-backed beads) |
| Graceful degradation | Strong (Ollama circuit breaker, provider fallback) | Moderate (circuit breaker hook) | Strong (quarantine, restart) |
| **Subtotal** | **Very Strong** | **Strong** | **Strong** |

### CCA Alignment Summary

| Domain (Weight) | Context Foundry | Citadel | Gas City |
|-----------------|:-:|:-:|:-:|
| Agentic Architecture (27%) | Very Strong | Strong | Very Strong |
| Claude Code Config (20%) | Moderate | Very Strong | Strong |
| Prompt Engineering (20%) | Very Strong | Strong | Strong |
| Tool Design & MCP (18%) | Strong | Moderate | Moderate |
| Context Mgmt & Reliability (15%) | Very Strong | Strong | Strong |
| **Overall CCA Alignment** | **Strong-Very Strong** | **Strong** | **Strong** |

**Key insight:** Context Foundry's isolated context windows, pattern injection, and MCP integration align most closely with CCA's emphasis on context management and tool design. Citadel leads on Claude Code-specific configuration. Gas City leads on agentic architecture at scale.

---

## Appendix B: When to Use Which

| Scenario | Recommended | Why |
|----------|-------------|-----|
| Solo dev, want AI to learn from mistakes | **Context Foundry** | Pattern learning + doubt confidence |
| Solo dev, multi-day features | **Citadel** | Campaign persistence + session handoff |
| Team with 10+ parallel agents | **Gas City** | Scale, attribution, health monitoring |
| Comparing Claude vs Codex objectively | **Context Foundry** | Dual-model arena |
| Claude Code-heavy workflow with hooks | **Citadel** | 8 lifecycle hooks, native integration |
| Multi-model fleet (Claude + Copilot + Gemini) | **Gas City** | Multi-provider agent protocol |
| Kubernetes deployment | **Gas City** | Native K8s session provider |
| Quick setup, minimal dependencies | **Citadel** | Zero npm deps, copy-paste setup |
| Pattern matching across projects | **Context Foundry** | Global pattern store + semantic matching |

---

## Appendix C: Codex 5.4 Validation Prompt

The following prompt is formatted for OpenAI Codex 5.4 to validate this comparison, identify gaps, and surface blind spots.

```
You are a technical reviewer validating a comparison of three AI agent orchestration
frameworks. Your job is to find what we missed, challenge assumptions, and identify
where the comparison may be biased toward the author's own project.

## Context

The author (snedea) built Context Foundry. They are comparing it against:
- Citadel (github.com/SethGammon/Citadel) -- campaign harness for Claude Code
- Gas City / Gastown (github.com/steveyegge/gastown, docs.gascityhall.com) -- multi-agent orchestration SDK

The full comparison report is at: docs/COMPARISON_REPORT.md in the context-foundry repo.

## Your Tasks

1. READ the comparison report thoroughly.

2. VERIFY claims by checking the actual repos:
   - Does Citadel really have zero npm dependencies?
   - Does Gas City really support 20-30 concurrent agents in practice (not just docs)?
   - Is Context Foundry's "isolated context windows" truly unique, or do others achieve similar isolation differently?
   - Are the CCA alignment ratings defensible, or inflated for Context Foundry?

3. IDENTIFY missing comparisons:
   - Cost (token usage, API spend) -- which framework is cheapest to run?
   - Setup time / onboarding -- which gets productive fastest?
   - Error recovery -- real failure modes, not just documented features
   - Documentation quality comparison
   - Community activity (commit frequency, issue response time, contributor diversity)
   - Security model differences (tool scoping, file protection, secret handling)

4. CHECK for author bias:
   - Is Context Foundry rated "Very Strong" in areas where it should be "Strong" or "Moderate"?
   - Are weaknesses of Context Foundry understated?
   - Are strengths of competitors understated?
   - Is the "When to Use Which" section fair, or does it steer toward Context Foundry?

5. SURFACE blind spots:
   - What use cases are NOT covered by any of these three?
   - What emerging patterns in AI orchestration (2026) are none of them addressing?
   - Are there other frameworks that should be in this comparison instead?

6. OUTPUT your findings as a structured review:
   - Confirmed claims (things that check out)
   - Challenged claims (things that seem wrong or inflated)
   - Missing dimensions (gaps in the comparison)
   - Bias indicators (where author favoritism shows)
   - Recommendations (how to make the comparison more objective)

Be direct. Be specific. Reference exact cells in the comparison tables when challenging ratings.
```

---

*Generated by Claude Opus 4.6. Pending Codex 5.4 validation pass.*
