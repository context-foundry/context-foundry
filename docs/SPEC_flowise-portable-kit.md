# Portable Flowise Kit Specification

Status: Draft
Last updated: 2026-03-31
Audience: teams that want Flowise AgentFlow v2 generation and audit in Claude Code or GitHub Copilot CLI without Context Foundry.

## 1. Purpose

Build a portable kit that lets Claude Code and GitHub Copilot CLI:

- generate Flowise AgentFlow v2 JSON from prompts
- validate structure before import
- audit flows with Floweyes
- repair failures in a fresh review context
- promote working flows into reusable examples

This spec does not try to recreate the full Context Foundry TUI. It rebuilds the parts that matter for Flowise quality: domain instructions, selective retrieval, builder and auditor separation, deterministic audit gates, and a benchmark harness.

## 2. Reality Model

This spec is based on the current Context Foundry implementation, not assumptions:

- Foundry programmatically loads selected extension `CLAUDE.md` files via [src/extensions.rs](../src/extensions.rs) and merges extension `patterns/*.json`.
- Foundry does not bulk-load the full Flowise corpus. Examples, templates, and expertise docs are loaded because [extensions/flowise/CLAUDE.md](../extensions/flowise/CLAUDE.md) tells the agent to read them.
- Therefore the portable kit must use selective retrieval, not unconditional injection.

Concretely, the current Flowise extension points the agent at:

- [extensions/flowise/FLOWISE.md](../extensions/flowise/FLOWISE.md)
- [extensions/flowise/docs/flowise-expertise.json](../extensions/flowise/docs/flowise-expertise.json)
- `example-flows/masterclass-2025/*.json`
- `node-templates/*.json`

That operating model should be preserved outside Foundry.

## 3. CAA-Aligned Design Principles

This design follows the relevant parts of the Claude Certified Architect Foundations guide in [CCA-Exam-Guide.pdf](./CCA-Exam-Guide.pdf). These task statements are broader than the mapping below; the list here names the sub-principles used by this spec.

- Task Statements 1.4 and 1.5: use multi-step workflows, explicit handoffs, and hooks for deterministic gates instead of relying only on prompt wording.
- Task Statements 3.1 through 3.3: keep persistent instructions modular, use skills for task-shaped workflows, and scope rules by path to reduce conflicts.
- Task Statement 5.1: manage context by loading only the relevant references, not the entire corpus.

Resulting rules for this kit:

- Always-on instructions must stay short and stable.
- Examples and templates must be retrieved selectively.
- A builder must not self-certify its own output.
- “Done” must be tied to validator and audit results, not to agent confidence.

## 4. Non-Goals

- Replacing Context Foundry for every domain other than Flowise.
- Reproducing the full Foundry orchestration UI.
- Bulk-loading all 111 example flows and all 16 node templates into every session.
- Assuming `floweyes` is published on PyPI.
- Treating chatflows or sequential v1 flows as part of the audited path.

## 5. Canonical Source Corpus

The portable kit should be generated from the Flowise extension already in this repo. That keeps Claude Code, Copilot CLI, and Foundry aligned.

### 5.1 Source of truth

- [extensions/flowise/FLOWISE.md](../extensions/flowise/FLOWISE.md): core structural rules and invariants
- [extensions/flowise/docs/flowise-expertise.json](../extensions/flowise/docs/flowise-expertise.json): learned patterns, anti-patterns, model defaults, testing checklists
- [extensions/flowise/example-flows/](../extensions/flowise/example-flows/): reference flows
- [extensions/flowise/node-templates/](../extensions/flowise/node-templates/): exact node blueprints
- [extensions/flowise/patterns/flowise-agentflow-patterns.json](../extensions/flowise/patterns/flowise-agentflow-patterns.json): portable keyword and pattern mapping
- [extensions/flowise/hackathon-devcon-2026/validate-flows.js](../extensions/flowise/hackathon-devcon-2026/validate-flows.js): structural validator seed

### 5.2 Corpus tiers

| Tier | Files | Runtime behavior |
|------|-------|------------------|
| Always-on | distilled rules derived from [extensions/flowise/FLOWISE.md](../extensions/flowise/FLOWISE.md), plus audit requirements | loaded every session |
| Retrieved on demand | [extensions/flowise/docs/flowise-expertise.json](../extensions/flowise/docs/flowise-expertise.json), selected AgentFlow v2 examples, selected node templates, selected pattern records | loaded only for the current task |
| Maintenance only | [extensions/flowise/DEVELOPMENT_WORKFLOW.md](../extensions/flowise/DEVELOPMENT_WORKFLOW.md), [extensions/flowise/docs/flowise-expertise-analyzer-output.json](../extensions/flowise/docs/flowise-expertise-analyzer-output.json) | used to evolve the kit, not injected into normal build sessions |

### 5.3 Runtime retrieval rule

When generating or repairing an audited AgentFlow v2 flow:

- retrieve at most 4 examples
- retrieve at most 2 node templates
- retrieve only the relevant `flowise-expertise.json` sections
- prefer AgentFlow v2 examples over chatflow examples
- exclude unsupported flow types from the audited path

## 6. Target Repository Layout

The portable kit should be consumable from any normal repository, not just this repo.

```text
repo/
├── AGENTS.md
├── CLAUDE.md
├── .flowiseauditor.yaml
├── output/
├── example-flows/
├── artifacts/
│   └── flowise/
├── scripts/
│   ├── flowise-select-context.py
│   ├── resolve-floweyes.sh
│   ├── validate-flowise.js
│   ├── validate-flowise.sh
│   ├── audit-flowise.sh
│   ├── repair-flowise.sh
│   └── benchmark-flowise.sh
├── .flowise-kit/
│   ├── manifest.json
│   ├── benchmarks.yaml
│   ├── source-map.md
│   └── corpus/
│       ├── flowise-expertise.json
│       ├── patterns/
│       │   └── flowise-agentflow-patterns.json
│       └── node-templates/
│           ├── AGENT-NODE-TEMPLATE.json
│           ├── CONDITIONAGENT-NODE-TEMPLATE.json
│           └── ...
├── .claude/
│   ├── rules/
│   │   ├── flowise-core.md
│   │   ├── flowise-json.md
│   │   └── flowise-promotion.md
│   ├── skills/
│   │   ├── build-flowise/
│   │   │   └── SKILL.md
│   │   ├── audit-flowise/
│   │   │   └── SKILL.md
│   │   ├── repair-flowise/
│   │   │   └── SKILL.md
│   │   └── promote-flowise/
│   │       └── SKILL.md
│   ├── agents/
│   │   └── flowise-auditor.md
│   └── settings.json
└── .github/
    ├── copilot-instructions.md
    ├── instructions/
    │   ├── flowise-core.instructions.md
    │   ├── flowise-json.instructions.md
    │   └── flowise-promotion.instructions.md
    ├── agents/
    │   ├── flowise-builder.agent.md
    │   └── flowise-auditor.agent.md
    └── hooks/
        └── flowise.json
```

### 6.1 Shared vs tool-specific assets

- `AGENTS.md`, `.flowiseauditor.yaml`, `scripts/`, `.flowise-kit/`, `output/`, and `example-flows/` are shared.
- `.claude/skills/` is also shared. Both Claude Code and Copilot CLI support project skills from `.claude/skills/`, so task workflows should live there once.
- `.claude/rules/`, `.claude/settings.json`, and `.claude/agents/` are Claude Code specific.
- `.github/copilot-instructions.md`, `.github/instructions/`, `.github/agents/`, and `.github/hooks/` are Copilot CLI specific.

## 7. Instruction Model

### 7.1 Shared root instructions

`AGENTS.md` is the tool-neutral instruction file. It should contain:

- the Flowise output contract
- the “read selected context before building” rule
- the requirement that validator and audit must pass before claiming success
- the promotion rule for adding new references back to the corpus

`CLAUDE.md` should import `AGENTS.md` and add only Claude-specific notes.

Recommended shape:

```md
@AGENTS.md

## Claude Code

- Use the Flowise project skills in `.claude/skills/`.
- Treat a flow as incomplete until `validate-flowise.sh` and `audit-flowise.sh` both pass.
```

### 7.2 Claude Code rules

`.claude/rules/flowise-core.md`

- unscoped
- contains only stable Flowise invariants

`.claude/rules/flowise-json.md`

- path-scoped to `output/**/*.json` and `example-flows/**/*.json`
- contains JSON-formatting and naming constraints

`.claude/rules/flowise-promotion.md`

- path-scoped to `example-flows/**/*`
- contains documentation and manifest update requirements

### 7.3 Copilot CLI instructions

`.github/copilot-instructions.md`

- repository-wide summary of the Flowise contract

`.github/instructions/flowise-core.instructions.md`

- general Flowise rules

`.github/instructions/flowise-json.instructions.md`

- scoped to draft and promoted JSON paths

`.github/instructions/flowise-promotion.instructions.md`

- scoped to promoted examples and docs

## 8. Shared Skills

The task workflows should be centered on shared `.claude/skills/` so both Claude Code and Copilot CLI can reuse them.

### 8.1 `build-flowise`

Responsibilities:

- classify the request against `.flowise-kit/manifest.json`
- load only the selected examples, templates, and expertise sections
- generate `output/<slug>.json`
- run structural validation
- run Floweyes audit
- hand off failures to the repair path

### 8.2 `audit-flowise`

Responsibilities:

- read the generated JSON
- read validator output
- read Floweyes JSON findings
- produce a defect list with concrete fix targets

This skill must be usable in a fresh context. It is the portable replacement for Foundry’s doubt loop.

### 8.3 `repair-flowise`

Responsibilities:

- apply the minimum changes needed to clear validation and audit findings
- preserve working structure
- re-run validation and audit after edits

### 8.4 `promote-flowise`

Responsibilities:

- move a passing draft into `example-flows/`
- add or update a README or rationale stub if required
- update `.flowise-kit/manifest.json`
- record new patterns back into the canonical corpus during maintenance work

## 9. Optional Dedicated Agents

Dedicated agents are optional for baseline portability but recommended for better separation.

### 9.1 Claude Code

Use either:

- shared skills with `context: fork`, or
- a project subagent in `.claude/agents/flowise-auditor.md`

The auditor agent should be read-mostly and should not generate a new flow from scratch.

### 9.2 Copilot CLI

Define:

- `.github/agents/flowise-builder.agent.md`
- `.github/agents/flowise-auditor.agent.md`

The builder produces JSON. The auditor critiques and repairs or requests repair. Copilot CLI custom agents live in `.github/agents/` and use `.agent.md` files.

## 10. Manifest Design

The kit needs a small manifest that maps problem classes to the right corpus slice.

### 10.1 Required fields

```json
{
  "version": 1,
  "defaults": {
    "max_examples": 4,
    "max_templates": 2,
    "max_expertise_entries": 8
  },
  "patterns": [
    {
      "id": "routing",
      "keywords": ["route", "triage", "classify", "billing", "technical"],
      "pattern_file": ".flowise-kit/corpus/patterns/flowise-agentflow-patterns.json#routing",
      "examples": [
        "example-flows/afv2-patterns/03-routing.json",
        "example-flows/succession-planning-orchestrator.json"
      ],
      "templates": [
        ".flowise-kit/corpus/node-templates/CONDITIONAGENT-NODE-TEMPLATE.json",
        ".flowise-kit/corpus/node-templates/AGENT-NODE-TEMPLATE.json"
      ],
      "expertise_paths": [
        "$.patterns[?(@.pattern_id=='afv2-routing-pattern')]",
        "$.agentflow_structure.required_fields.condition_agent"
      ],
      "benchmarks": ["routing-helpdesk"]
    }
  ]
}
```

### 10.2 Selection algorithm

`scripts/flowise-select-context.py` must:

1. classify the request into one or two pattern buckets
2. return the top matching examples and templates
3. exclude chatflow and sequential v1 references when audit mode is enabled
4. write a machine-readable selection report to `artifacts/flowise/selected-context.json`

### 10.3 Manifest maintenance

- Update the manifest when new examples or templates are added.
- Use [extensions/flowise/docs/flowise-expertise-analyzer-output.json](../extensions/flowise/docs/flowise-expertise-analyzer-output.json) as a maintenance aid only.
- Do not inject the analyzer output into build sessions.

## 11. Script Contracts

### 11.1 `scripts/validate-flowise.js`

- Ported from [extensions/flowise/hackathon-devcon-2026/validate-flows.js](../extensions/flowise/hackathon-devcon-2026/validate-flows.js)
- validates Flowise JSON structure before audit
- returns exit `0` on success, non-zero on failure
- writes machine-readable results to stdout or `artifacts/flowise/<slug>.validate.json`

### 11.2 `scripts/validate-flowise.sh`

- thin wrapper that calls `node scripts/validate-flowise.js <file>`
- standardizes output location and exit code handling

### 11.3 `scripts/resolve-floweyes.sh`

Resolution order:

1. use `floweyes` on `PATH`
2. use `$FLOWEYES_BIN` if set
3. use `uv run --directory "$FLOWEYES_DIR" floweyes` if `$FLOWEYES_DIR` is set and contains the Floweyes source tree
4. use a vendored binary at `.flowise-kit/vendor/floweyes/floweyes` if present
5. fail with setup instructions

Do not assume `pip install floweyes` from PyPI. The wrapper must support local source checkouts and release binaries.

### 11.4 `scripts/audit-flowise.sh`

Contract:

```bash
scripts/audit-flowise.sh output/my-flow.json
```

Behavior:

- resolves Floweyes through `resolve-floweyes.sh`
- runs strict JSON audit
- writes `artifacts/flowise/my-flow.audit.json`
- returns exit `1` when ACTION findings exist

Target invocation:

```bash
floweyes --strict --format json output/my-flow.json
```

### 11.5 `scripts/repair-flowise.sh`

- orchestrates `validate-flowise.sh` then `audit-flowise.sh`
- if either fails, invokes the repair path and reruns both checks
- stops after a bounded retry count

### 11.6 `scripts/benchmark-flowise.sh`

- runs the benchmark suite against the portable kit
- records pass rate, repair iterations, and time to green
- emits a summary report under `artifacts/flowise/benchmarks/`

## 12. Hook Contracts

Hooks turn advice into gates.

### 12.1 Guardrails

Pre-write guard:

- block edits to canonical references unless the user explicitly requests maintenance
- protected paths: `example-flows/`, `.flowise-kit/corpus/node-templates/`, `.flowise-kit/corpus/flowise-expertise.json`, `.flowise-kit/manifest.json`, and portable instruction files

Post-write gate:

- when a JSON file under `output/` or `example-flows/` changes, run `validate-flowise.sh`
- if validation passes, run `audit-flowise.sh`
- attach findings back to agent context

Completion gate:

- block success claims if the latest validation or audit artifact is missing
- block success claims if ACTION findings remain

### 12.2 Claude Code configuration

Use `.claude/settings.json` hooks for:

- `PreToolUse` on `Write|Edit|MultiEdit`
- `PostToolUse` on `Write|Edit|MultiEdit`
- `Stop` for final completion checks

### 12.3 Copilot CLI configuration

Use `.github/hooks/flowise.json` for:

- `preToolUse`
- `postToolUse`
- `sessionEnd` or final task completion behavior

The hook scripts should be shared. Only the wrapper configuration should differ by tool.

## 13. Floweyes Integration

Floweyes is the hard audit gate for the portable kit.

Supported audited path:

- Flowise AgentFlow v2 only

Excluded from audited path:

- chatflows
- sequential agents v1

Recommended config:

```yaml
profile: strict
```

Store that in `.flowiseauditor.yaml`.

If a team wants deeper organization-specific rules, add Floweyes custom rules rather than encoding those constraints only in prompts.

## 14. Benchmark Suite

The portable kit must be compared against Foundry on a fixed set of prompts.

### 14.1 Benchmark cases

| ID | Prompt | Reference file |
|----|--------|----------------|
| `chaining-review` | Build an AgentFlow v2 that ingests a policy document, extracts obligations, validates them, pauses for human review, and returns a final approval report. | [extensions/flowise/example-flows/afv2-patterns/01-chaining.json](../extensions/flowise/example-flows/afv2-patterns/01-chaining.json) |
| `parallel-research` | Build an AgentFlow v2 that researches a vendor from web, internal knowledge, and risk analysis in parallel, then synthesizes one recommendation. | [extensions/flowise/example-flows/afv2-patterns/02-parallel.json](../extensions/flowise/example-flows/afv2-patterns/02-parallel.json) |
| `routing-helpdesk` | Build an AgentFlow v2 that routes incoming requests to billing, technical, or general support specialists and returns one synthesized answer. | [extensions/flowise/example-flows/afv2-patterns/03-routing.json](../extensions/flowise/example-flows/afv2-patterns/03-routing.json) |
| `iteration-review` | Build an AgentFlow v2 that iterates over a list of requirements, evaluates each item, accumulates findings, and returns a summary. | [extensions/flowise/example-flows/afv2-patterns/04-iteration.json](../extensions/flowise/example-flows/afv2-patterns/04-iteration.json) |
| `software-dev-team` | Build a software development team flow with planner, developer, tester, and reviewer agents. | [extensions/flowise/example-flows/masterclass-2025/software-dev-team-agents.json](../extensions/flowise/example-flows/masterclass-2025/software-dev-team-agents.json) |
| `deep-research` | Build a deep research orchestrator with planning, search loops, evidence gathering, and synthesis. | [extensions/flowise/example-flows/masterclass-2025/deep-research-agentflow.json](../extensions/flowise/example-flows/masterclass-2025/deep-research-agentflow.json) |
| `succession-planning` | Build a Workday-style succession planning orchestrator with approval gates and structured recommendations. | [extensions/flowise/example-flows/succession-planning-orchestrator.json](../extensions/flowise/example-flows/succession-planning-orchestrator.json) |

### 14.2 Metrics

- first-pass structural validation rate
- first-pass Floweyes pass rate
- repair iterations to green
- final pass rate
- time to green
- manual import success rate

### 14.3 Migration rule

Foundry remains the benchmark and fallback until the portable kit matches it closely enough on this suite.

## 15. Maintenance Workflow

When the portable kit discovers a new pattern or failure mode:

1. update [extensions/flowise/docs/flowise-expertise.json](../extensions/flowise/docs/flowise-expertise.json)
2. update [extensions/flowise/FLOWISE.md](../extensions/flowise/FLOWISE.md) if the issue reflects a stable rule
3. add or refresh an example in [extensions/flowise/example-flows/](../extensions/flowise/example-flows/)
4. update a node template in [extensions/flowise/node-templates/](../extensions/flowise/node-templates/) if structure changed
5. regenerate `.flowise-kit/corpus/` for the portable target repo
6. update `.flowise-kit/manifest.json`

This mirrors the intent of [extensions/flowise/DEVELOPMENT_WORKFLOW.md](../extensions/flowise/DEVELOPMENT_WORKFLOW.md) while keeping runtime context lean.

## 16. Acceptance Criteria

The portable kit is acceptable when all of the following are true:

- a prompt can produce a draft flow into `output/`
- structural validation runs automatically
- Floweyes audit runs automatically
- ACTION findings block completion
- the auditor runs in fresh context or equivalent isolation
- the benchmark suite is reproducible
- results are compared against Foundry before deprecating Foundry for Flowise work

## 17. Bottom Line

The portable path is credible, but only if it preserves selective retrieval, fresh auditing, and hard gates.

Prompt files alone are not enough.

The minimum viable portable stack is:

- short always-on instructions
- shared skills
- selective example and template retrieval
- validator wrapper
- Floweyes strict audit wrapper
- builder and auditor separation
- benchmark harness against Foundry
