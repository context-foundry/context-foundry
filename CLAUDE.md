# Context Foundry

Context Foundry is a pattern-learning system that helps AI agents improve over time by capturing and sharing solutions to common problems.

## Build & Install

After any code change, rebuild and install:

```bash
cd ~/homelab/context-foundry && cargo build --release && cp target/release/foundry ~/.cargo/bin/ && codesign -s - --force ~/.cargo/bin/foundry
```

Run from any project directory:

```bash
cd ~/some-project && foundry
```

**IMPORTANT:** The running TUI does NOT hot-reload. You must quit the TUI, rebuild, and restart to pick up changes. If you see errors like `No such tool available: Write`, you are running a stale binary.

## Local Models

LM Studio + opencode is wired into the builder pipeline via Phase 32. Runbook:
[`docs/local-model-setup.md`](docs/local-model-setup.md). Smoke gate:
`bash scripts/smoke-local-model.sh` (asserts schema_version, opencode routing,
and typed-error absence).

## Global Patterns

Patterns are stored in `~/.foundry/patterns/`. Read them before starting work:

```lua
mcp__context-foundry__read_global_patterns("common-issues")
```

## Plugins

Context Foundry has domain-specific plugins (formerly called "extensions"). **When working on tasks for a specific domain, read that plugin's CLAUDE.md first.** The on-disk directory is `plugins/`. The legacy `plugins/` name is auto-migrated on first startup; do not reference it in new code or docs.

### Roblox Plugin
**Location:** `plugins/roblox/`
**When to read:** Any Roblox world generation, Lune scripting, or .rbxl/.rbxm work

**IMPORTANT - Read before Roblox work:**
- `plugins/roblox/CLAUDE.md` - Critical patterns and commands
- `plugins/roblox/skills/roblox-common-pitfalls/SKILL.md` - Learned pitfalls (Anthropic Skills format)

**Key learnings:**
- Use `add_to_world.luau` (not `generate_world.luau`)
- Use CFrame, not Position, for moving parts
- Don't generate worlds from scratch - load original and clone

### Workday Extend Plugin
**Location:** `plugins/extend/`
**When to read:** Any Workday Extend app development, orchestrations, integrations, security configuration, BIRT reports, or Workday API work

**IMPORTANT - Read before Extend work:**
- `plugins/extend/CLAUDE.md` - Index of all guides and critical rules
- `plugins/extend/WORKDAY_EXTEND_DEVELOPER_GUIDE.md` - Comprehensive dev workflow
- `plugins/extend/WORKDAY_EXTEND_ARCHITECTURE.md` - AMD/PMD/SMD metadata structures
- `plugins/extend/orchestrations-integrations-guide.md` - Orchestrations deep dive
- `plugins/extend/security-reporting-birt-notes.md` - Security, reporting, BIRT

**Key learnings:**
- Extend apps are metadata-driven (no arbitrary code execution)
- Always activate security policy changes after modification
- WIDs are tenant-specific -- use Reference IDs instead
- Credentials never migrate between tenants
- Test before every biannual Workday release

### Recon Plugin
**Location:** `plugins/recon/`
**When to read:** Any fleet checks, iDRAC queries, racadm commands, server inventory lookups, or batch ops from a management server

**IMPORTANT - Read before ops/recon work:**
- `plugins/recon/CLAUDE.md` - Domain rules and key files
- `plugins/recon/config/inventory-schema.json` - CSV column mapping
- `plugins/recon/templates/` - Proven command templates

**Key learnings:**
- Always use `grep -w` for hostname lookups (avoid substring matches)
- SSH to iDRAC needs `-o ConnectTimeout=5` to avoid hanging loops
- Always label batch output with the current hostname

### Workday Agents Plugin
**Location:** `plugins/workday-agents/`
**When to read:** Building any standalone compliance rule engine targeting the Workday Marketplace (ACA auditor, multi-state tax, Davis-Bacon, or similar)

**IMPORTANT - Read before building a new Workday agent:**
- `plugins/workday-agents/CLAUDE.md` - Architecture pattern, design rules, existing agents
- `plugins/workday-agents/skills/workday-agents-common-pitfalls/SKILL.md` - Learned pitfalls (Anthropic Skills format)

**Key learnings:**
- Normalize dict KEYS (not just values) at the Pydantic model level
- Inclusive date ranges need +1 for month counting
- Specific rules must replace generic rules, not supplement them
- Resolve exemptions/reciprocity before general rules fire
- Threshold comparisons (> vs >=) vary by jurisdiction -- make configurable
- SPEC.md drifts from implementation every commit -- update counts and phase status

### Other Plugins
| Plugin | Path | Domain |
|-----------|------|--------|
| Flowise | `plugins/flowise/` | Flowise AI workflows |

## MCP Tools Available

Context Foundry provides these MCP tools:

| Tool | Purpose |
|------|---------|
| `read_global_patterns` | Read learned patterns |
| `save_global_patterns` | Save new patterns |
| `merge_project_patterns` | Merge project patterns to global |
| `delegate_to_claude_code` | Delegate tasks to fresh Claude instances |
| `search_skills` | Find reusable code skills |

## After Solving Issues

When you solve a new problem, save the pattern:

1. Add to the relevant plugin's patterns file
2. Merge to global: `mcp__context-foundry__merge_project_patterns(path, "common-issues")`

This helps future agents avoid the same issues.

## Settings Overlay

Press `?` in the TUI to open the Settings Overlay -- a modal exposing ~40
configuration fields in 9 collapsible sections. Esc/click-outside/`[ X ]` to close.
Full reference: [`docs/settings-overlay.md`](docs/settings-overlay.md).

Per-stage model routing (e.g. Claude Opus on Plan, Codex on Build) is configured
from the Routing section. See [`docs/per-stage-routing.md`](docs/per-stage-routing.md).

## Coach Mode

`run_mode = "coach"` (toggle via Ctrl+M or Settings -> Pipeline -> Run Mode)
inserts an intake-clarification stage before bootstrap Scout. v1 is a
non-interactive pre-flight: Coach reads SPEC.md, writes
`.buildloop/intake-brief.md` with a clarified outline + suspected task
decomposition, and Scout consumes the brief. v2 will add multi-turn chat
in the startup input box. Full reference: [`docs/coach-mode.md`](docs/coach-mode.md).

## Eval Harness

An eval harness runs after every task completion and grades the run for plumbing
integrity (system prompts, pattern injection, prior-artifact reads) and heuristic
outcome quality. Per-stage badges appear in the TUI status meter as
`EVAL Q✓R✓P✓B⚠A✓`; the full breakdown is in the Settings overlay
(`?` -> Pipeline Health). The harness never blocks the pipeline. See
[`docs/eval-harness.md`](docs/eval-harness.md) for the full reference.

## Progress Indicators (QRPBA)

Completed tasks in `TASKS.md` carry QRPBA indicators: **Q**uery, **R**esearch,
**P**lan, **B**uild, **A**udit. `-` = skipped, `+` = deferred, `!` = failed audit.
Full reference: [`docs/progress-indicators.md`](docs/progress-indicators.md).

**Note for agents:** The pipeline stages are internally called `query`, `research`,
`plan`, `implement`, `doubt` (used in code and prompt instructions). Completed tasks
use the QRPBA letters in `TASKS.md`. Do NOT "fix" QRPBA indicators back to RPID or
SPID -- they are the current convention as of P33.1.

## Doubt Loop

The doubt loop is handled by the AUDIT stage of the pipeline (a fresh-context
agent that reads build-claims.md and audits with "Audit and validate these claims.
Find the gaps."). Individual agents (researcher, planner, builder) should NOT self-audit
or spawn sub-agents for verification -- that wastes time and tokens. Focus on doing
your job well and let DOUBT catch the gaps with fresh eyes.

## Task Composition

Task composition is the upstream lever that drives the pipeline cost. The
complexity engine reads the shape of a task to set its budget; well-composed
tasks land cheaply, bundled tasks thrash through P+ revisions.

**Rule of thumb: one mental model change per task.**

Signs a task is over-bundled (split it):

- Numbered sub-features in the description: `(1) ... (2) ... (3)`
- Lead sentence contains "AND also", "plus", "three layers", "and additionally"
- Multiple distinct verbs in the opening clause ("add X and refactor Y and rename Z")
- File references span more than ~6 distinct paths (real blast radius)
- Description exceeds ~500 words
- The Constraints section needs subsections to organize itself

Signs a task is well-composed (let it run):

- One verb, one concern, one mental model
- File refs concentrated in 1-3 modules
- Constraints can be checked independently
- Verification checks are local to the change

**Why it matters:** T1.16 (`(1) wire ranker (2) BM25 upgrade (3) telemetry boost`)
burned ~$20 over 63 minutes through 4 PLAN attempts because P+ couldn't reason
about three independent concerns as one coherent change. The same scope split
into T1.16a/b/c would have shipped in ~$8 over 25 minutes total.

T1.18 (Esc + Ctrl+C modals) is borderline -- two modals + key handler + render
dispatch + tests is four concerns, but they share state plumbing. P+ ran 3/3
iterations and caught real bugs each pass. Borderline tasks pay rigor tax;
clearly-bundled tasks pay thrashing tax. Bias toward splitting.

**Per-task override flags** (planned via T1.23):

- `[fast]` after the task ID -- skips P+ entirely; use when the spec is
  well-specified and you trust BUILD+AUDIT to catch what slips.
- `[strict]` -- forces full 3-iteration P+ even on Simple tasks.

Until T1.23 ships, the lever is composition: rewrite the task to match what
you want the pipeline to do.

**When NOT to pipeline at all:** if a task has zero ``file:line`` references
and zero verifiable behavioral claims (pure prose -- README updates,
brainstorming, architecture decision records), the pipeline adds no value.
Its mechanism is verifying claims against code; prose has no code counterpart.
Write those directly. Full guidance: [`docs/task-composition.md`](docs/task-composition.md).
