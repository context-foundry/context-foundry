# Why the Conflict-of-Interest Agent Screams “Hierarchy”

If you love building with Flowise, you probably have a folder full of JSON flows that already work but are hard to classify. I dusted off `conflict-of-interest-agent/conflict-of-interest-detection-flow.json` and ran it through our new primary-pattern picker to see which AgentFlow v2 template it actually wants. The answer matters: once we slot flows into the right skeleton, we get predictable state contracts, guardrails, and speed-to-production when we upgrade a workflow.

## Start With the Picker

Our decision order is strict—first true condition wins:

1. Routing → domain/skill fan-out
2. Hierarchy → orchestrated roles (supervisor, reviewer, workers)
3. Parallel → ensemble branches
4. Chaining → strict dependency ladder
5. Iteration → quality-driven refinements
6. Looping → validator-driven retries  
Tie-breakers pull Hierarchy ahead of Routing when both are true, and Parallel outranks Chaining when you need fan-out.

## What’s Inside the Conflict-of-Interest Flow?

Key moments straight from the JSON:

- `startAgentflow_0` prompts for client, engagement type, team, description, and revenue (form input).
- `Agent.ConflictDetector` scores risk, lists affected parties, and writes audit data.
- `humanInputAgentflow_0` pauses execution for compliance to approve or reject the engagement.
- A “Proceed” decision hands off to `Agent.ConflictApprover`; “Reject” routes to `Agent.ConflictRemediator`.

No automatic router decides between Approver and Remediator—the human reviewer does. We also have clearly separated roles: an analyst agent, a human reviewer, and two specialized follow-up agents that carry different tool permissions.

## Pattern Verdict: Hierarchy Wins

- **Role orchestration is explicit.** The flow is a supervisor (ConflictDetector) handing work to a human reviewer, who then dispatches to domain specialists. That’s a textbook Hierarchy brief.
- **Hierarchy outranks Routing.** Even though we ultimately branch into “approved” vs. “remediate,” the tie-breaker says Hierarchy dominates when role orchestration is in play.
- **Nested patterns show up downstream.** Once compliance selects a path, each branch behaves like a short Chaining sequence (generate waiver paperwork, log evidence) that could later inherit the Chaining template for consistency.

Think of the human gate as your Reviewer node; Approver and Remediator are Worker subflows executing with their own ACLs. Applying the Hierarchy template gives us:

- A supervisor plan that spells out who does what (`state.plan[]`).
- Worker nodes with scoped tool access (Approver vs. Remediator).
- A reviewer decision router that cleanly loops back if compliance says “try again.”

## Where to Embed Secondary Patterns

| Flow segment | Recommended nested pattern | Why |
| --- | --- | --- |
| ConflictDetector analysis | Chaining (micro-steps) | Intake → existing conflicts → risk scoring |
| Post-approval tasks | Iteration | Waiver drafts often need refinement against a rubric |
| Remediation loop | Looping | Run mitigation plan → validate → retry until compliant |

By nesting these beneath the Hierarchy skeleton, we keep the primary orchestration clear while giving each worker the structure it needs.

## Retrofit Checklist Before Dropping Into AFv2 Library

- Add a `START` node that populates `state.input` according to the Hierarchy template contract.
- Insert sticky notes for: 🎯 PURPOSE, 👤 REVIEW PROCESS, ⚙️ APPROVER TASKS, ⚠️ REMEDIATION PATH (remember ±150/±550 offsets).
- Record planner output as `state.plan[]` and worker artifacts in `state.worker_outputs[]`.
- Capture reviewer decisions (`state.review.score`, `state.review.go_no_go`) before calling downstream branches.
- Wire a Run Report at the bottom with `{pattern:"hierarchy", decisions, metrics, risks, final_output}`.
- Drop HIL gates in front of any tool that mutates external systems; that keeps us compliant with the global invariants.

## Takeaways for Fellow Builders

1. **Run the picker before touching JSON.** Knowing the primary pattern up front saves rework when you bolt on state and guardrails.
2. **Hierarchy = people + permissions.** If a human or supervisor controls the sequencing, treat the flow as Hierarchy even if you see domain branching later.
3. **Use nested patterns intentionally.** Workers and mitigation branches can still inherit Chaining, Iteration, or Looping templates to stay disciplined.
4. **Document the why.** Sticky notes and a Run Report make the flow self-explanatory for auditors and new teammates.

Have a legacy Flowise build that feels “in between” patterns? Drop it into the picker and share what you learn—I’d love to compare notes. In the meantime, this conflict-of-interest agent is heading straight for the Hierarchy template in our Context Foundry library.
