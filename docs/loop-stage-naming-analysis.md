z# Loop Stage Naming Analysis

Date: 2026-03-06

## Question

Should Foundry keep using stage names like `Planner`, `Builder`, `Reviewer`, and `Fixer`, especially when the prompt bodies say things like "You are the PLANNER agent"?

The concern is valid: for an LLM, anthropomorphic persona labels are often weaker than direct task framing. The safer question is not "are these labels ugly?" but "where are they coupled into behavior, data, and operator workflows?"

## Short Answer

- Yes, the current prompt bodies explicitly use persona-style framing.
- No, Foundry does not define a separate hidden "system prompt" layer for these roles in its own code.
- The labels are not only cosmetic. Some of them are embedded in prompt text, orchestration code, UI/logging, README language, and the learned-pattern schema.
- A careful prompt-first refactor is low risk and likely beneficial.
- A full internal rename is possible, but it is not the first move I would make.

## What The Code Actually Does

### 1. There is no Foundry-managed hidden system prompt

The build loop passes a single prompt string to Claude Code via `claude -p`:

- `src/agent.rs:241` — `run_agent(...)`
- `src/agent.rs:258` — `cmd.arg(prompt);`

That means the persona wording is not in a separate system channel implemented by Foundry. It is just ordinary prompt text generated in `src/prompts.rs`.

### 2. The prompt bodies do explicitly say "You are the X agent"

Current openings:

- `src/prompts.rs:15` — `You are the PLANNER agent...`
- `src/prompts.rs:98` — `You are the BUILDER agent...`
- `src/prompts.rs:161` — `You are the REVIEWER agent...`
- `src/prompts.rs:251` — `You are the FIXER agent...`
- `src/prompts.rs:276` — `You are the PATTERN EXTRACTOR agent...`
- `src/prompts.rs:327` — `You are the DISCOVERY agent...`

So the concern is real. The model sees persona-style phrasing at the top of every loop-stage prompt.

### 3. The loop names also exist outside model-facing prompts

They are used in orchestration and operator-facing surfaces:

- `src/agent.rs:15` — `AgentRole` enum
- `src/app.rs:542`, `583`, `715`, `775` — loop orchestration uses those role names
- `src/tui.rs:199-203` — TUI color mapping for those stage names
- `README.md:17-26` and `README.md:130-136` — flow diagram and prompt documentation

Important nuance:

- The enum names themselves are not sent to the model as a separate control mechanism.
- The model behavior is driven by the actual prompt text in `src/prompts.rs`.
- The enum and labels still matter for operator comprehension, logs, filenames, and mental model.

### 4. "Planner" and "Reviewer" are also part of learned-pattern data

This is the biggest hidden coupling:

- `src/patterns.rs:7-12` — `PatternSolution` has `planner` and `reviewer` fields
- `src/patterns.rs:168` — pattern advice selection branches on `reviewer`
- `src/prompts.rs:303-304` — pattern extraction prompt tells the model to emit `"planner"` and `"reviewer"` keys

This means a broad rename is not just a prompt rewrite. It can become a persisted-data migration problem.

There is already precedent for careful compatibility handling:

- `src/patterns.rs:11` — `reviewer` accepts `validator` as a serde alias

That is a good sign, but it also proves these names are schema-level, not only presentation-level.

## Assessment

## What is actually wrong today?

I would not call the current system "wrong" in a catastrophic sense. The prompts are not only role labels; they are heavily action-constrained and output-specific. For example:

- Planner is told to write `.buildloop/current-plan.md` in a rigid schema
- Builder is told to execute `.buildloop/current-plan.md`
- Reviewer is told to run checks and produce `.buildloop/review-report.md`
- Fixer is told to repair issues from the review report

So the current loop is already action-oriented in substance.

The weaker part is the opening frame. The first sentence says "You are the X agent", which is persona-first rather than task-first.

## Why changing the framing may still help

For LLMs, the strongest prompt anchor is usually:

1. what step this is
2. what artifact must be produced
3. what constraints apply
4. what is out of scope

The current prompts do 2-4 well. They are less crisp on 1 because they start with a persona noun instead of a stage objective.

Net-net, this looks like a prompt hygiene improvement opportunity, not a deep architectural flaw.

## Options

### Option A: Prompt-only reframing, keep internal names stable

Change only the opening language in `src/prompts.rs`.

Examples:

- Planner:
  - Current: `You are the PLANNER agent...`
  - Safer: `Planning stage for an autonomous build loop. Produce a deterministic implementation plan in .buildloop/current-plan.md.`

- Builder:
  - Current: `You are the BUILDER agent...`
  - Safer: `Implementation stage for an autonomous build loop. Execute .buildloop/current-plan.md precisely and verify the result.`

- Reviewer:
  - Current: `You are the REVIEWER agent...`
  - Safer: `Validation and audit stage for an autonomous build loop. Inspect the changed files, run the required checks, and write .buildloop/review-report.md.`

- Fixer:
  - Current: `You are the FIXER agent...`
  - Safer: `Repair stage for an autonomous build loop. Resolve the HIGH and MEDIUM issues documented in .buildloop/review-report.md.`

- Discovery:
  - Current: `You are the DISCOVERY agent...`
  - Safer: `Discovery stage for an autonomous build loop. Identify credible new tasks and append them to TASKS.md.`

- Pattern Extractor:
  - Current: `You are the PATTERN EXTRACTOR agent...`
  - Safer: `Pattern extraction stage for an autonomous build loop. Extract reusable lessons from this build into .buildloop/patterns-extracted.json.`

Pros:

- Lowest behavioral risk
- Likely improves prompt sharpness
- No schema migration
- No UI churn
- No operator retraining required

Cons:

- Internal names still remain `Planner`, `Builder`, etc.
- README and TUI still reinforce the persona framing

Recommendation level: High

### Option B: Prompt reframing plus operator-facing terminology cleanup

Keep internals stable, but update docs and UI language to use stage verbs/nouns like:

- Plan
- Implement
- Review
- Repair
- Discover
- Extract Patterns

This could include:

- README flow diagram
- README prompt table
- TUI display labels and logs

Pros:

- Better operator mental model
- Less anthropomorphic framing everywhere
- Still avoids risky schema migration

Cons:

- Broader surface-area change than Option A
- Can make code/docs feel temporarily mixed if internals still use old enum names

Recommendation level: Medium-high, but after Option A

### Option C: Full internal rename

Rename core internals such as:

- `AgentRole` -> `LoopStage` or `StageKind`
- `Planner` -> `Plan`
- `Builder` -> `Implement`
- `Reviewer` -> `Review`
- `Fixer` -> `Repair`
- `Discovery` -> `Discover`

Potentially also rename prompt constructors, README terms, tests, logs, pattern schema keys, and migration aliases.

Pros:

- Most semantically consistent long-term
- Eliminates persona naming from the codebase itself

Cons:

- Highest risk
- Touches orchestration, tests, docs, logs, persisted patterns, and extraction schema
- Needs compatibility strategy for existing pattern data

Recommendation level: Low as a first step

## Recommendation

I recommend a staged approach:

1. Do Option A first.
2. Evaluate output quality on a small set of representative tasks.
3. If results are neutral-to-positive, do Option B.
4. Only consider Option C after the prompt and operator-facing language have stabilized.

This is the safest path because it improves the model-facing instructions without forcing a broad rename across code, docs, and persisted data.

## Why I Would Not Start With A Full Rename

The system is more coupled than it first appears:

- Prompt bodies use persona labels
- UI/logs use role labels
- README explains the system using those labels
- Learned patterns encode `planner` / `reviewer` in persisted JSON
- Pattern extraction tells the model to emit those keys

That means a full rename is not just "clean up some names." It is a multi-surface migration.

## Minimal Safe Change Set For A Future PR

If the goal is "improve the system without breaking it", the minimal safe PR would:

1. Update the first 1-3 lines of each prompt in `src/prompts.rs`
2. Keep all output artifacts, filenames, report formats, and JSON schema unchanged
3. Keep `AgentRole` unchanged for now
4. Keep `PatternSolution.planner` / `PatternSolution.reviewer` unchanged for now
5. Add a short note in the README that these are loop stages, not personas

That change would preserve behavior while making the model-facing framing more action-first.

## Suggested Decision

If the objective is net improvement with low break risk:

- Yes: change the prompt framing
- Yes: gradually change docs/UI wording
- No: do not start by renaming core enums or persisted schema keys

## Bottom Line

The professionals' criticism is directionally correct: the persona wording is real, and it is probably not the sharpest way to frame the loop to an LLM.

But the right response is not a broad rename first.

The right first move is a prompt-first, action-first rewrite that keeps internal identifiers stable until the behavioral impact is understood.
