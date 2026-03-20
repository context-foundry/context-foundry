**Context Foundry** is an autonomous build loop written in Rust. Give it a task list in markdown, and it works through every task using AI agents -- scouting the codebase, planning, building, and verifying with an independent reviewer in a fresh context. Passing tasks get committed. When the list runs out, a discovery agent scans for new work and keeps going.

```
SCOUT ──▶─ PLAN ──▶─ IMPLEMENT ──▶─ DOUBT        COMMIT
```

**The core insight:** every agent starts with a clean context window and receives only curated artifacts from the previous stage -- not a bloated conversation history full of noise. The scout writes a structured report. The planner reads that report and writes a plan. The builder reads that plan and writes code. The verifier reads the code with zero knowledge of why it was written that way. No shared context windows, no accumulated reasoning, no inherited blind spots. Each stage gets signal, not noise. This is how foundry prevents the compounding error problem where task 3 builds on task 2's mistakes. On top of this, **pattern learning** extracts reusable lessons after each task and injects them into future runs across all projects.

```
- [x] T1.1: Set up scaffolding       [SPID]   ● feat
- [x] T1.2: Implement auth           [SPID!]  ✗ WIP
- [ ] T1.3: Write tests              [....]
```

Other features: **dual-model arena** (race Claude vs Codex through the full pipeline in parallel worktrees), **complexity scaling** (simple tasks skip planner and reviewer -- 30 seconds instead of 10 minutes), and **three run modes** (Auto/Sprint/Review with GitHub PR polling).

141 tasks completed on its own codebase across 33 discovery rounds. Foundry built most of itself.

Rust binary, ratatui TUI, MIT licensed.
