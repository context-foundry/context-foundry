# `json-stream` Output Schema

`foundry run --no-tui --output-format json-stream` writes a line-delimited
JSON event stream to stdout: exactly one JSON object per line. Human-readable
progress text, tool output, and logs go to stderr; stdout carries only
machine-readable JSONL.

The stream has two kinds of line:

1. **Event lines** -- every line except the last. Each has an `event`
   discriminator and `event_schema_version` (currently `1`). Bump
   `EVENT_SCHEMA_VERSION` in `src/app/stream.rs` on any breaking change.
2. **Terminal report** -- the final line. It has no `event` key; it is the
   same `SessionReport` object emitted by `--output-format json` (schema in
   [`ci-output-schema.json`](ci-output-schema.json)), serialized as one line.
   It carries `schema_version` (currently `3`).

A consumer distinguishes the two by key presence: an `event` key marks an
event line; a `schema_version` key marks the terminal report.

## Event types

| `event` | Fields | Meaning |
|---|---|---|
| `stage_started` | `stage`, `role`, `model`, `label` (string\|null), `task_id` (string\|null) | A pipeline stage began |
| `stage_finished` | `stage`, `role`, `ok` (bool), `task_id` (string\|null) | The current stage ended; `ok` is its success flag |
| `task_started` | `task_id`, `description` | A task began |
| `task_completed` | `task_id`, `ok` (bool) | A task ended; `ok=false` means WIP / audit-fail |
| `counts` | `tasks_total`, `tasks_completed`, `tasks_wip` | Running task tallies |
| `cost` | `delta_usd`, `cumulative_usd`, `input_tokens`, `output_tokens` | A per-`Usage` cost delta and the running total |

`stage` is the canonical QRPBA stage slug: `query`, `research`, `plan`,
`implement`, `doubt` (also `scout`, `plan-review`, `discover`, `coach`).
`role` is the display name (`QUERY`, `RESEARCH`, `PLAN`, `BUILD`, `AUDIT`,
...). Events carry no timestamp; a consumer records receipt time itself.

The `label` field is non-null only for stages emitted with a stage id
(per-stage routing, e.g. `plan-review`). The core Q/R/P/B/A stages emit
`label: null`.

## Ordering guarantees

- A `stage_finished` always follows the matching `stage_started`.
- A `task_completed` always follows its `task_started`.
- `cumulative_usd` is non-decreasing.
- The terminal report's `cost_usd` equals the last `cumulative_usd`.

The position of a `cost` event relative to the surrounding `stage_finished`
is **unspecified**: at runtime a stage's `Usage` delta drains before its
`AgentDone`, so `cost` typically precedes `stage_finished`. Consumers must
not depend on `cost`-vs-`stage_finished` interleaving.

## Replay fixture

A recorded reference stream lives at
`tests/fixtures/json-stream-sample.jsonl` and is validated by
`tests/json_stream_fixture.rs`. Downstream consumers (the M1
`MockBuildBackend`) can replay it without invoking an LLM.
