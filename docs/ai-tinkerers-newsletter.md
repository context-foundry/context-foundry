**Context Foundry** is an autonomous build loop written in Rust. Give it a task list in markdown, and it works through every task using AI agents -- scouting the codebase, planning, building, and verifying with an independent reviewer in a fresh context. Passing tasks get committed. When the list runs out, a discovery agent scans for new work and keeps going.

```
SCOUT ──▶─ PLAN ──▶─ IMPLEMENT ──▶─ DOUBT        COMMIT
```

Here's the thing about autonomous coding agents: they don't know when they're wrong. An agent builds task 1, makes a subtle mistake, and moves on. Task 2 builds on that mistake. By task 3, the codebase has drifted from the intended architecture, and nobody noticed because the same agent that wrote the bug is the one reviewing its own work.

Foundry fixes this by making sure no agent ever sees another agent's reasoning. The scout writes a report and exits. The planner reads that report -- just the report, not the scout's tool calls or thought process -- and writes a plan. The builder reads the plan and writes code. Then a completely separate verifier reads the code cold, with no idea why any of it was written the way it was. If something looks wrong, it looks wrong. There's no accumulated context to paper over a bad decision three stages ago.

On top of that, every solved problem gets captured as a pattern and fed back into future runs. A mistake you make in one project becomes a check that runs in every project after it.

```
- [x] T1.1: Set up scaffolding       [SPID]   ● feat
- [x] T1.2: Implement auth           [SPID!]  ✗ WIP
- [ ] T1.3: Write tests              [....]
```

You can also race two models against each other -- Claude and Codex each get their own worktree and run the full pipeline independently, so you compare finished solutions, not just raw outputs. Simple tasks skip the planner and reviewer and commit in about 30 seconds. There are three run modes: Auto keeps going forever, Sprint stops when the list is done, Review creates a PR after each task and waits for approval.

Foundry has completed 141 tasks on its own codebase across 33 discovery rounds. Most of the features described here were built by the loop itself.

Rust binary, ratatui TUI, MIT licensed.
