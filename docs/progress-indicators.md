# Progress Indicators (QRPBA)

Every completed task in `TASKS.md` carries a bracketed indicator that records which
pipeline stages ran and whether they succeeded. The indicator is committed alongside
the code so the project retains a permanent audit trail.

```
- [x] T1.1: Set up project scaffolding          [QRPBA]
- [x] T1.2: Implement auth flow                 [--PBA]
- [x] T1.3: Add rate limiting                   [QRPBA!]
- [ ] T1.4: Write integration tests             [....]
```

## Letter scheme

Each character maps to a pipeline stage:

| Position | Letter | Stage | Meaning |
|----------|--------|-------|---------|
| 1 | **Q** | Query | Query stage ran |
| 2 | **R** | Research | Research/scout stage ran |
| 3 | **P** | Plan | Planner stage ran |
| 4 | **B** | Build | Builder (implement) stage ran |
| 5 | **A** | Audit | Audit/verify (doubt) stage ran |

### Modifiers

| Symbol | Meaning |
|--------|---------|
| `-` | Stage was skipped (e.g. `--PBA` means Query and Research were skipped) |
| `+` | Deferred stage (e.g. `QRP+BA` means Plan review was deferred) |
| `!` | Audit did not pass -- commit was `WIP(task-id)` instead of `feat(task-id)` |

### Examples

| Indicator | Interpretation |
|-----------|---------------|
| `QRPBA` | Full pipeline, clean pass |
| `--PBA` | Query and Research skipped (simple task), planned, built, audited, clean pass |
| `---B-` | Only Build ran (simplest path -- no scout, plan, or audit) |
| `QRP+BA` | Plan review deferred; Build and Audit ran |
| `QRPBA!` | Full pipeline but Audit found unfixable issues (WIP commit) |
| `---B-!` | Build-only, Audit skipped, but the commit was WIP (e.g. EmptyDeliverable) |

## Complexity-scaled indicators

The task complexity classifier (Simple / Medium / Complex) determines which stages
run. Simple tasks may skip Query, Research, Plan, and Audit -- producing indicators
like `---B-`. Complex tasks always run the full pipeline (`QRPBA`). The indicator
reflects the actual execution, not the configured pipeline.

## TUI display

The TUI shows these indicators in the task queue with color coding:
- Green for clean passes (no `!` suffix)
- Yellow/red for failed audit (`!` suffix)
- Gray for pending tasks (`[....]`)

Indicators survive across TUI restarts because they are written directly into
`TASKS.md`.

## Legacy indicators (SPID / RPID)

Before P33.1 (commit `5560b0a`), indicators used the SPID scheme:
**S**=Scout, **P**=Plan, **I**=Implement, **D**=Doubt/Verify. Older `TASKS.md` files
may still contain these indicators (e.g. `[SPID]`, `[S-ID]`). They are read-only
historical artifacts -- do not rewrite them to QRPBA.

If you see the letters `I` or `D` in an indicator produced by the current version
of foundry, that is a regression. The smoke gate
(`scripts/smoke-local-model.sh`, check 6) asserts that `I` and `D` never appear in
new indicators. See [`docs/local-model-setup.md`](local-model-setup.md) for the
full smoke-gate failure interpretation guide.

## Related docs

- [README.md](../README.md) -- project overview with indicator examples
- [Local model setup](local-model-setup.md) -- smoke gate check 6 validates QRPBA convention
- [Per-stage routing](per-stage-routing.md) -- how different models can be pinned to each stage
