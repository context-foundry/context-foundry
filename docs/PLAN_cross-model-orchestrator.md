# Plan: Cross-Model Orchestrator
Date: 2026-03-13
Version: v2 (revised after Codex review)
Status: planning

## Context
The user currently acts as a manual router between Claude (proposer) and Codex
(reviewer). The workflow is formulaic and automatable:

1. Claude proposes a plan or fix
2. User copies to Codex with "review this" or "validate this"
3. Codex returns structured findings
4. User copies findings back to Claude
5. Claude addresses them
6. Repeat until clean

The human judgment involved is classifiable and the routing is mechanical.

## What This Is
A design-time conversation loop that orchestrates proposal and review across
different models. It produces a reviewed artifact (plan, fix, or decision) that
the human explicitly applies to the project.

This is NOT a replacement for the build loop. The build loop handles task
execution. The orchestrator handles design-time decisions.

## Core Principle: Structured Contracts

The key insight from review: free-form output parsing is brittle. Both the
proposer and reviewer MUST output structured envelopes. The orchestrator parses
envelopes, not prose.

### Proposer Envelope
```json
{
  "artifact_type": "plan" | "code_change" | "analysis",
  "artifact_text": "... the actual content ...",
  "rationale": "why this approach was chosen",
  "claims": [
    "claim 1 that can be verified",
    "claim 2 that can be verified"
  ]
}
```

### Reviewer Envelope
```json
{
  "status": "clean" | "findings",
  "findings": [
    {
      "severity": "high" | "medium" | "low",
      "description": "what is wrong",
      "location": "file or section reference",
      "suggestion": "what to do instead"
    }
  ],
  "validated": [
    "claim that was verified as correct"
  ]
}
```

## Implementation Steps

- [ ] Step 1 -- Define data model (new file: src/orchestrator.rs)
  - `OrchestratorConfig { proposer_provider, proposer_model, reviewer_provider, reviewer_model, max_iterations }`
  - `ProposerOutput { artifact_type, artifact_text, rationale, claims }`
  - `ReviewerOutput { status, findings, validated }`
  - `Finding { severity, description, location, suggestion }`
  - `OrchestratorOutcome { artifact: ProposerOutput, review: ReviewerOutput, iterations: usize }`
  - Parse from JSON with serde, with graceful fallback if agent doesn't follow format

- [ ] Step 2 -- Add proposer prompt template
  - System prompt instructs the agent to output the ProposerOutput JSON envelope
  - User prompt contains: the intent, any prior findings to address, project context
  - The prompt explicitly says: "Output ONLY a JSON object with these fields..."
  - Fallback: if response isn't valid JSON, wrap the raw text as artifact_text with artifact_type="analysis"

- [ ] Step 3 -- Add reviewer prompt template
  - Input: the ProposerOutput envelope
  - System prompt instructs: output the ReviewerOutput JSON envelope
  - Review scope varies by artifact_type:
    - plan: "Review for gaps, risks, implementation soundness"
    - code_change: "Validate claims, check for bugs, verify files"
    - analysis: "Check factual accuracy, flag unsupported claims"
  - NOT "explanation -> skip" (explanations can contain wrong claims too)

- [ ] Step 4 -- Add acceptance policy (configurable)
  - Default: accept if no high or medium findings
  - Configurable in .foundry.json: `orchestrator_accept_policy: "no-high" | "no-high-medium" | "no-findings"`
  - "no-high": accept with medium/low findings (default since 2026-06-09;
    mediums append to the plan as advisory constraints)
  - "no-high-medium": accept only with low findings (original default)
  - "no-findings": accept only when completely clean (strict)

- [ ] Step 5 -- Build the orchestration loop
  - `async fn orchestrate(intent: &str, config: &OrchestratorConfig, project_dir: &Path) -> OrchestratorOutcome`
  - Uses existing agent::run_agent infrastructure
  - Loop (max config.max_iterations, default 3):
    1. Send to proposer with intent + any prior findings
    2. Parse ProposerOutput from response
    3. Send to reviewer
    4. Parse ReviewerOutput from response
    5. Apply acceptance policy
    6. If accepted -> return outcome
    7. If rejected -> format findings into next proposer prompt
  - On max iterations: return last artifact with unresolved findings attached
  - Each iteration gets a fresh agent (no conversation history bloat)

- [ ] Step 6 -- CLI entry point (v1: headless only, no TUI)
  - `foundry design "intent text here"`
  - Runs the orchestration loop
  - Prints each iteration's status to stderr
  - Writes final artifact to .buildloop/orchestrator-output.md
  - Prints summary: "Completed in N iterations. Status: clean|findings_remaining"
  - Does NOT auto-write to TASKS.md or SPEC.md

- [ ] Step 7 -- Startup integration (after CLI is stable)
  - New startup action: "Design with review" (only when orchestrator config is set)
  - Opens intent input (same as Describe work)
  - Runs orchestration loop (shown in Planning phase UI)
  - On completion: returns to startup with message
  - User can then view .buildloop/orchestrator-output.md
  - User explicitly copies/applies to TASKS.md or SPEC.md via the editor
  - Future: "Apply" action that does this automatically

- [ ] Step 8 -- Tests
  - Unit: ProposerOutput and ReviewerOutput JSON parsing with valid/invalid inputs
  - Unit: acceptance policy evaluation for each policy level
  - Unit: findings are formatted correctly for the next proposer round
  - Unit: max iterations terminates the loop
  - Unit: fallback wrapping when proposer output isn't valid JSON
  - Integration: end-to-end with mock agents returning known envelopes

## Configuration (separate from build loop config)
```json
{
  "orchestrator_proposer_provider": "claude",
  "orchestrator_proposer_model": "opus",
  "orchestrator_reviewer_provider": "codex",
  "orchestrator_reviewer_model": "codex-5.4",
  "orchestrator_max_iterations": 3,
  "orchestrator_accept_policy": "no-high-medium"
}
```

## What This Does NOT Do in v1
- Auto-write to TASKS.md or SPEC.md (human applies explicitly)
- TUI orchestration view (CLI/headless first)
- Conversation history across iterations (fresh agent each round)
- Replace the build loop's review.rs (that handles code, this handles plans)

## Risks & Open Questions
- JSON envelope compliance: models may not follow the format perfectly.
  Mitigation: fallback parsing wraps raw text as artifact_text.
- Context: each iteration is a fresh agent call. The proposer needs enough
  context (project state + findings) without full conversation history.
- Cost: each iteration is 2 agent calls (proposer + reviewer). At 3 iterations
  max, that's 6 calls per design decision. Acceptable for design-time work.
- Ordering: should the orchestrator run before or instead of "Describe work"?
  Recommendation: it's a separate action. "Describe work" is fast and direct.
  "Design with review" is thorough and multi-round.
