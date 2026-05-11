# Observability

Foundry's observatory subsystem records every pipeline event (session start,
agent spawn, agent done, task classification, pattern injection, review
findings, commit, etc.) as append-only JSON lines.

## Storage layout

All observatory data lives under `~/.foundry/observatory/`:

| Path | Purpose | Lifecycle |
|------|---------|-----------|
| `events-YYYY-MM-DD.jsonl` | One JSON line per event for that UTC date. Written by `observatory::log_event` (`src/observatory.rs`). | Active file is never touched by retention. |
| `.archived/` | Files moved here by the retention pass (orphan SQLite, expired event logs). | Manual cleanup. |

There is intentionally no SQLite database here. An older `observatory.db` lived
alongside the JSONL files until T1.32; it had no readers and was archived by
the first launch after the upgrade.

## Event schema

See `EventEnvelope` and `ObservatoryEvent` in `src/observatory.rs`. Each line
on disk is:

```
{"timestamp":"2026-05-11T18:15:23.123Z","session_id":"...","project_dir":"/abs/path","event_type":"agent_done","payload":{...}}
```

`event_type` is the snake_case discriminant from `event_type_str`; `payload` is
the variant-specific fields.

## Retention policy

On every Foundry launch:

1. Any file in `~/.foundry/observatory/` matching the legacy SQLite family
   (`observatory.db`, `observatory.db-wal`, `observatory.db-shm`,
   `observatory.db-journal`) is moved to `.archived/`. One-shot cleanup of the
   legacy SQLite store; harmless if there is nothing to move. Other `*.db`
   files (e.g. ad-hoc analysis databases) are left alone.
2. Each `events-YYYY-MM-DD.jsonl` file older than
   `observatory_jsonl_retention_days` is moved to `.archived/`. Today's active
   file is never touched.
3. The pass is idempotent: the second run is a no-op when no new files have
   appeared (rename-collision is treated as "already archived").

Configure the retention window via `~/.foundry/config.json`, `.foundry.json`,
or the Settings overlay (Pipeline behavior -> Observatory Retention (days)).
Default 30. Set to 0 to disable JSONL pruning entirely (orphan SQLite cleanup
still runs).

The pass is best-effort: per-file failures are surfaced as `state.log`
warnings on the TUI but never abort startup.

## Reading events

`foundry stats` reads the JSONL files via `stats::load_events` (`src/stats.rs`)
and renders aggregates in the terminal. `foundry dashboard` serves the same
data on `127.0.0.1:9400`.
