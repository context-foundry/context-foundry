//! Public `json-stream` event schema.
//!
//! This module defines the stable, documented event vocabulary emitted by
//! `foundry run --no-tui --output-format json-stream`. It is intentionally
//! NOT a serialization of the private `LoopEvent` enum: `LoopEvent` has ~30
//! internal variants whose shape changes with pipeline internals, and it has
//! no stage-finished signal at all. `StreamEvent` is the public contract;
//! `EVENT_SCHEMA_VERSION` is bumped on any breaking change to it.
//!
//! Schema reference: `docs/json-stream-schema.md`.

use std::io::Write;

use serde::Serialize;

use crate::agent::AgentRole;

/// Schema version of the json-stream event lines. Bump on any breaking
/// change to StreamEvent (renamed/removed field, changed semantics).
pub(super) const EVENT_SCHEMA_VERSION: u32 = 1;

/// One public event line in the `json-stream` output.
///
/// Internally tagged: every serialized object carries an `event` key whose
/// value is the snake_case variant name.
#[derive(Debug, Clone, Serialize)]
#[serde(tag = "event", rename_all = "snake_case")]
pub(super) enum StreamEvent {
    StageStarted {
        stage: String,
        role: String,
        model: String,
        label: Option<String>,
        task_id: Option<String>,
    },
    StageFinished {
        stage: String,
        role: String,
        ok: bool,
        task_id: Option<String>,
    },
    TaskStarted {
        task_id: String,
        description: String,
    },
    TaskCompleted {
        task_id: String,
        ok: bool,
    },
    Counts {
        tasks_total: usize,
        tasks_completed: usize,
        tasks_wip: usize,
    },
    Cost {
        delta_usd: f64,
        cumulative_usd: f64,
        input_tokens: u64,
        output_tokens: u64,
    },
}

/// Envelope that prepends `event_schema_version` to each serialized line.
#[derive(Serialize)]
struct StreamLine<'a> {
    event_schema_version: u32,
    #[serde(flatten)]
    event: &'a StreamEvent,
}

/// Tracks the currently-open stage so a role-less `AgentDone` can be paired
/// with the stage that opened it.
struct StageCtx {
    stage: String,
    role: String,
}

/// Writes `StreamEvent`s as line-delimited JSON to a sink.
pub(super) struct StreamEmitter<W: Write> {
    sink: W,
    current_stage: Option<StageCtx>,
    current_task: Option<String>,
}

impl<W: Write> StreamEmitter<W> {
    /// Construct an emitter writing JSONL to `sink`.
    pub(super) fn new(sink: W) -> StreamEmitter<W> {
        StreamEmitter {
            sink,
            current_stage: None,
            current_task: None,
        }
    }

    /// Serialize one event as a single JSONL line and flush.
    ///
    /// Best-effort: a serialization or write failure is ignored so a failed
    /// progress line never aborts the build.
    fn write_line(&mut self, event: &StreamEvent) {
        let line = StreamLine {
            event_schema_version: EVENT_SCHEMA_VERSION,
            event,
        };
        if let Ok(s) = serde_json::to_string(&line) {
            let _ = writeln!(self.sink, "{}", s);
            let _ = self.sink.flush();
        }
    }

    /// Emit a `task_started` event and record the active task id.
    pub(super) fn emit_task_started(&mut self, task_id: &str, description: &str) {
        self.current_task = Some(task_id.to_string());
        self.write_line(&StreamEvent::TaskStarted {
            task_id: task_id.to_string(),
            description: description.to_string(),
        });
    }

    /// Emit a `task_completed` event. The active task id is intentionally
    /// retained so later counts/stage events keep referencing it.
    pub(super) fn emit_task_completed(&mut self, task_id: &str, ok: bool) {
        self.write_line(&StreamEvent::TaskCompleted {
            task_id: task_id.to_string(),
            ok,
        });
    }

    /// Emit a `counts` event with running task tallies.
    pub(super) fn emit_counts(
        &mut self,
        tasks_total: usize,
        tasks_completed: usize,
        tasks_wip: usize,
    ) {
        self.write_line(&StreamEvent::Counts {
            tasks_total,
            tasks_completed,
            tasks_wip,
        });
    }

    /// Emit a `stage_started` event and record the open stage.
    pub(super) fn emit_stage_started(
        &mut self,
        role: &AgentRole,
        label: Option<&str>,
        model: &str,
    ) {
        let stage = role.slug().to_string();
        let role_name = role.to_string();
        self.current_stage = Some(StageCtx {
            stage: stage.clone(),
            role: role_name.clone(),
        });
        self.write_line(&StreamEvent::StageStarted {
            stage,
            role: role_name,
            model: model.to_string(),
            label: label.map(|s| s.to_string()),
            task_id: self.current_task.clone(),
        });
    }

    /// Emit a `stage_finished` event for the currently-open stage.
    ///
    /// If no stage is open (an unpaired `AgentDone`), this is a no-op.
    pub(super) fn emit_stage_finished(&mut self, ok: bool) {
        if let Some(ctx) = self.current_stage.take() {
            self.write_line(&StreamEvent::StageFinished {
                stage: ctx.stage,
                role: ctx.role,
                ok,
                task_id: self.current_task.clone(),
            });
        }
    }

    /// Emit a `cost` event carrying a per-`Usage` delta and the running total.
    pub(super) fn emit_cost(
        &mut self,
        delta_usd: f64,
        cumulative_usd: f64,
        input_tokens: u64,
        output_tokens: u64,
    ) {
        self.write_line(&StreamEvent::Cost {
            delta_usd,
            cumulative_usd,
            input_tokens,
            output_tokens,
        });
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn parse_lines(buf: &[u8]) -> Vec<serde_json::Value> {
        String::from_utf8(buf.to_vec())
            .expect("utf8")
            .lines()
            .filter(|l| !l.trim().is_empty())
            .map(|l| serde_json::from_str(l).expect("each emitted line must be valid JSON"))
            .collect()
    }

    #[test]
    fn event_schema_version_is_one() {
        assert_eq!(EVENT_SCHEMA_VERSION, 1);
    }

    #[test]
    fn emits_stage_lifecycle_in_order() {
        let mut buf: Vec<u8> = Vec::new();
        {
            let mut em = StreamEmitter::new(&mut buf);
            em.emit_task_started("T1.1", "demo");
            em.emit_stage_started(&AgentRole::Query, None, "claude-opus");
            em.emit_stage_finished(true);
            em.emit_stage_started(&AgentRole::Builder, Some("T1.1"), "claude-opus");
            em.emit_stage_finished(true);
            em.emit_cost(0.5, 0.5, 100, 50);
            em.emit_task_completed("T1.1", true);
            em.emit_counts(1, 1, 0);
        }
        let evts = parse_lines(&buf);
        assert_eq!(evts.len(), 8);
        assert_eq!(evts[0]["event"], "task_started");
        assert_eq!(evts[1]["event"], "stage_started");
        assert_eq!(evts[1]["stage"], "query");
        assert_eq!(evts[2]["event"], "stage_finished");
        assert_eq!(evts[3]["stage"], "implement");
        assert_eq!(evts[3]["label"], "T1.1");
        assert_eq!(evts[5]["event"], "cost");
        assert_eq!(evts[5]["cumulative_usd"], 0.5);
        for e in &evts {
            assert_eq!(e["event_schema_version"], 1);
        }
    }

    #[test]
    fn stage_finished_without_started_is_noop() {
        let mut buf: Vec<u8> = Vec::new();
        {
            let mut em = StreamEmitter::new(&mut buf);
            em.emit_stage_finished(true);
        }
        assert!(buf.is_empty());
    }

    #[test]
    fn stage_events_carry_current_task_id() {
        let mut buf: Vec<u8> = Vec::new();
        {
            let mut em = StreamEmitter::new(&mut buf);
            em.emit_task_started("T2.1", "x");
            em.emit_stage_started(&AgentRole::Planner, None, "m");
            em.emit_stage_finished(false);
        }
        let evts = parse_lines(&buf);
        assert_eq!(evts[1]["task_id"], "T2.1");
        assert_eq!(evts[2]["task_id"], "T2.1");
        assert_eq!(evts[2]["ok"], false);
    }
}
