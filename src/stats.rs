use std::collections::{BTreeMap, HashMap, HashSet};
use std::path::{Path, PathBuf};

use anyhow::{bail, Context, Result};
use chrono::{NaiveDate, Utc};
use serde::Serialize;

use crate::observatory::EventEnvelope;

// ─── Report Structs ──────────────────────────────────────────

#[derive(Debug, Serialize)]
pub struct StatsReport {
    pub window: WindowInfo,
    pub project: Option<String>,
    pub summary: Summary,
    pub phase_costs: Vec<PhaseCostEntry>,
    pub quality: Quality,
    pub patterns: PatternsInfo,
}

#[derive(Debug, Serialize)]
pub struct WindowInfo {
    pub days: u32,
    pub from: String,
    pub to: String,
    pub events_parsed: usize,
    pub lines_skipped: usize,
}

#[derive(Debug, Serialize)]
pub struct Summary {
    pub total_sessions: usize,
    pub total_tasks: usize,
    pub feat_count: usize,
    pub wip_count: usize,
    pub feat_wip_ratio: Option<f64>,
    pub total_cost_usd: f64,
    pub pass_rate_by_complexity: Vec<ComplexityPassRate>,
    pub task_costs: Vec<TaskCostEntry>,
}

#[derive(Debug, Serialize)]
pub struct ComplexityPassRate {
    pub complexity: String,
    pub total: usize,
    pub feat: usize,
    pub rate: f64,
}

#[derive(Debug, Serialize)]
pub struct TaskCostEntry {
    pub task_id: String,
    pub session_id: String,
    pub cost_usd: f64,
}

#[derive(Debug, Serialize)]
pub struct PhaseCostEntry {
    pub role: String,
    pub invocations: usize,
    pub cost_usd: f64,
    pub tokens_in: u64,
    pub tokens_out: u64,
}

#[derive(Debug, Serialize)]
pub struct Quality {
    pub doubt_finding_rate: Option<f64>,
    pub tasks_with_findings: usize,
    pub tasks_reviewed: usize,
    pub budget_overrun_rate: Option<f64>,
    pub budget_overruns: usize,
    pub budgeted_executions: usize,
}

#[derive(Debug, Serialize)]
pub struct PatternsInfo {
    pub total_injections: usize,
    pub unique_patterns: usize,
    pub top_patterns: Vec<PatternCount>,
    pub effectiveness: Vec<PatternEffectiveness>,
}

#[derive(Debug, Serialize)]
pub struct PatternCount {
    pub pattern_id: String,
    pub count: usize,
}

#[derive(Debug, Serialize)]
pub struct PatternEffectiveness {
    pub pattern_id: String,
    pub injection_count: usize,
    pub citation_count: usize,
    pub citation_rate: f64,
    pub cited_task_ids: Vec<String>,
    pub low_signal: bool,
}

// ─── Entry Point ─────────────────────────────────────────────

pub fn run_stats(days: u32, project: &Path, output: &str) -> Result<()> {
    match output {
        "table" | "json" => {}
        other => bail!("invalid output format '{}': expected 'table' or 'json'", other),
    }

    let obs_dir = observatory_dir()?;
    let canonical = dunce::canonicalize(project).unwrap_or_else(|_| project.to_path_buf());
    let (events, skipped) = load_events(&obs_dir, days, Some(&canonical))?;
    let report = compute_stats(
        &events,
        skipped,
        days,
        Some(&canonical.display().to_string()),
    );

    match output {
        "json" => {
            let json = serde_json::to_string_pretty(&report)
                .context("failed to serialize stats report")?;
            println!("{}", json);
        }
        _ => print_table(&report),
    }

    Ok(())
}

fn observatory_dir() -> Result<PathBuf> {
    let home = std::env::var("HOME").context("HOME not set")?;
    Ok(PathBuf::from(home).join(".foundry").join("observatory"))
}

// ─── Event Loading ───────────────────────────────────────────

pub fn load_events(
    obs_dir: &Path,
    days: u32,
    project: Option<&Path>,
) -> Result<(Vec<EventEnvelope>, usize)> {
    if !obs_dir.exists() {
        return Ok((vec![], 0));
    }

    let today = Utc::now().date_naive();
    let cutoff = today - chrono::Duration::days(days as i64);

    let mut events = Vec::new();
    let mut skipped = 0usize;

    let entries = std::fs::read_dir(obs_dir)
        .with_context(|| format!("cannot read observatory dir: {}", obs_dir.display()))?;

    for entry in entries {
        let entry = entry?;
        let fname = entry.file_name();
        let fname_str = fname.to_string_lossy();

        if !fname_str.starts_with("events-") || !fname_str.ends_with(".jsonl") {
            continue;
        }

        let date_part = &fname_str[7..fname_str.len() - 6];
        let file_date = match NaiveDate::parse_from_str(date_part, "%Y-%m-%d") {
            Ok(d) => d,
            Err(_) => continue,
        };

        if file_date < cutoff || file_date > today {
            continue;
        }

        let content = std::fs::read_to_string(entry.path())
            .with_context(|| format!("cannot read {}", entry.path().display()))?;

        for line in content.lines() {
            let line = line.trim();
            if line.is_empty() {
                continue;
            }
            match serde_json::from_str::<EventEnvelope>(line) {
                Ok(env) => events.push(env),
                Err(e) => {
                    eprintln!("warning: skipping malformed line: {}", e);
                    skipped += 1;
                }
            }
        }
    }

    // Filter by canonicalized project_dir
    if let Some(project_path) = project {
        let canonical = dunce::canonicalize(project_path)
            .unwrap_or_else(|_| project_path.to_path_buf());
        let canonical_str = canonical.display().to_string();
        events.retain(|e| e.project_dir == canonical_str);
    }

    // Sort by timestamp for correct ordering within sessions
    events.sort_by(|a, b| a.timestamp.cmp(&b.timestamp));

    Ok((events, skipped))
}

// ─── Computation ─────────────────────────────────────────────

pub fn compute_stats(
    events: &[EventEnvelope],
    skipped: usize,
    days: u32,
    project: Option<&str>,
) -> StatsReport {
    let today = Utc::now().date_naive();
    let cutoff = today - chrono::Duration::days(days as i64);

    let mut sessions = HashSet::new();
    let mut tasks = HashSet::new();
    let mut feat_count = 0usize;
    let mut wip_count = 0usize;
    let mut total_cost = 0.0f64;

    // Phase cost accumulators: (invocations, cost, tokens_in, tokens_out)
    let mut phase_map: HashMap<String, (usize, f64, u64, u64)> = HashMap::new();

    // Complexity tracking for pass-rate join
    let mut task_complexity: HashMap<(String, String), String> = HashMap::new();
    let mut task_committed: HashMap<(String, String), String> = HashMap::new();

    // Session event indices for task-cost walk
    let mut session_events: BTreeMap<String, Vec<usize>> = BTreeMap::new();

    // Quality metrics
    let mut tasks_reviewed = HashSet::new();
    let mut tasks_with_findings = HashSet::new();
    let mut budget_overruns = 0usize;
    let mut agent_done_count = 0usize;

    // Pattern tracking
    let mut pattern_counts: HashMap<String, usize> = HashMap::new();
    let mut total_injections = 0usize;

    // Pattern citation tracking (T24.2)
    let mut pattern_citation_counts: HashMap<String, usize> = HashMap::new();
    let mut pattern_cited_tasks: HashMap<String, HashSet<String>> = HashMap::new();

    for (idx, ev) in events.iter().enumerate() {
        session_events
            .entry(ev.session_id.clone())
            .or_default()
            .push(idx);

        match ev.event_type.as_str() {
            "session_started" => {
                sessions.insert(ev.session_id.clone());
            }
            "task_started" => {
                if let Some(task_id) = ev.payload.get("task_id").and_then(|v| v.as_str()) {
                    tasks.insert((ev.session_id.clone(), task_id.to_string()));
                    if let Some(complexity) =
                        ev.payload.get("complexity").and_then(|v| v.as_str())
                    {
                        task_complexity.insert(
                            (ev.session_id.clone(), task_id.to_string()),
                            complexity.to_string(),
                        );
                    }
                }
            }
            "agent_done" => {
                agent_done_count += 1;
                let cost = ev
                    .payload
                    .get("cost_usd")
                    .and_then(|v| v.as_f64())
                    .unwrap_or(0.0);
                total_cost += cost;

                if let Some(role) = ev.payload.get("role").and_then(|v| v.as_str()) {
                    let entry = phase_map.entry(role.to_string()).or_default();
                    entry.0 += 1;
                    entry.1 += cost;
                    entry.2 += ev
                        .payload
                        .get("tokens_in")
                        .and_then(|v| v.as_u64())
                        .unwrap_or(0);
                    entry.3 += ev
                        .payload
                        .get("tokens_out")
                        .and_then(|v| v.as_u64())
                        .unwrap_or(0);
                }
            }
            "committed" => {
                if let (Some(task_id), Some(commit_type)) = (
                    ev.payload.get("task_id").and_then(|v| v.as_str()),
                    ev.payload.get("commit_type").and_then(|v| v.as_str()),
                ) {
                    // Last commit for a (session, task) wins
                    task_committed.insert(
                        (ev.session_id.clone(), task_id.to_string()),
                        commit_type.to_string(),
                    );
                    let ct_lower = commit_type.to_lowercase();
                    if ct_lower == "feat" {
                        feat_count += 1;
                    } else if ct_lower == "wip" {
                        wip_count += 1;
                    }
                }
            }
            "review_findings" => {
                if let Some(task_id) = ev.payload.get("task_id").and_then(|v| v.as_str()) {
                    let key = (ev.session_id.clone(), task_id.to_string());
                    tasks_reviewed.insert(key.clone());
                    let high = ev
                        .payload
                        .get("high")
                        .and_then(|v| v.as_u64())
                        .unwrap_or(0);
                    let medium = ev
                        .payload
                        .get("medium")
                        .and_then(|v| v.as_u64())
                        .unwrap_or(0);
                    if high + medium > 0 {
                        tasks_with_findings.insert(key);
                    }
                }
            }
            "budget_overrun" => {
                budget_overruns += 1;
            }
            "pattern_injected" => {
                total_injections += 1;
                if let Some(ids) = ev.payload.get("pattern_ids").and_then(|v| v.as_array()) {
                    for id in ids {
                        if let Some(s) = id.as_str() {
                            *pattern_counts.entry(s.to_string()).or_insert(0) += 1;
                        }
                    }
                }
            }
            "pattern_cited" => {
                if let (Some(pattern_id), Some(task_id)) = (
                    ev.payload.get("pattern_id").and_then(|v| v.as_str()),
                    ev.payload.get("task_id").and_then(|v| v.as_str()),
                ) {
                    *pattern_citation_counts.entry(pattern_id.to_string()).or_insert(0) += 1;
                    pattern_cited_tasks
                        .entry(pattern_id.to_string())
                        .or_default()
                        .insert(task_id.to_string());
                }
            }
            _ => {}
        }
    }

    // ── Pass rate by complexity: join TaskStarted.complexity to final Committed ──

    let mut complexity_map: HashMap<String, (usize, usize)> = HashMap::new(); // (total, feat)
    for (key, complexity) in &task_complexity {
        if let Some(commit_type) = task_committed.get(key) {
            let entry = complexity_map.entry(complexity.clone()).or_default();
            entry.0 += 1;
            if commit_type.to_lowercase() == "feat" {
                entry.1 += 1;
            }
        }
    }
    let mut pass_rate_by_complexity: Vec<ComplexityPassRate> = complexity_map
        .into_iter()
        .map(|(complexity, (total, feat))| ComplexityPassRate {
            complexity,
            total,
            feat,
            rate: if total > 0 {
                feat as f64 / total as f64
            } else {
                0.0
            },
        })
        .collect();
    pass_rate_by_complexity.sort_by(|a, b| a.complexity.cmp(&b.complexity));

    // ── Task costs: sum AgentDone between TaskStarted boundaries per session ──

    let mut task_costs = Vec::new();
    for (session_id, indices) in &session_events {
        let mut current_task: Option<String> = None;
        let mut current_cost = 0.0f64;

        for &idx in indices {
            let evt = &events[idx];
            match evt.event_type.as_str() {
                "task_started" => {
                    // Flush previous task
                    if let Some(tid) = current_task.take() {
                        task_costs.push(TaskCostEntry {
                            task_id: tid,
                            session_id: session_id.clone(),
                            cost_usd: current_cost,
                        });
                    }
                    current_task = evt
                        .payload
                        .get("task_id")
                        .and_then(|v| v.as_str())
                        .map(|s| s.to_string());
                    current_cost = 0.0;
                }
                "agent_done" => {
                    if current_task.is_some() {
                        current_cost += evt
                            .payload
                            .get("cost_usd")
                            .and_then(|v| v.as_f64())
                            .unwrap_or(0.0);
                    }
                }
                "session_ended" => {
                    if let Some(tid) = current_task.take() {
                        task_costs.push(TaskCostEntry {
                            task_id: tid,
                            session_id: session_id.clone(),
                            cost_usd: current_cost,
                        });
                    }
                    current_cost = 0.0;
                }
                _ => {}
            }
        }
        // Flush if session didn't end cleanly
        if let Some(tid) = current_task.take() {
            task_costs.push(TaskCostEntry {
                task_id: tid,
                session_id: session_id.clone(),
                cost_usd: current_cost,
            });
        }
    }
    task_costs.sort_by(|a, b| {
        b.cost_usd
            .partial_cmp(&a.cost_usd)
            .unwrap_or(std::cmp::Ordering::Equal)
    });

    // ── Phase costs ──

    let mut phase_costs: Vec<PhaseCostEntry> = phase_map
        .into_iter()
        .map(|(role, (inv, cost, ti, to))| PhaseCostEntry {
            role,
            invocations: inv,
            cost_usd: cost,
            tokens_in: ti,
            tokens_out: to,
        })
        .collect();
    phase_costs.sort_by(|a, b| {
        b.cost_usd
            .partial_cmp(&a.cost_usd)
            .unwrap_or(std::cmp::Ordering::Equal)
    });

    // ── Top patterns ──

    let unique_patterns = pattern_counts.len();
    let mut top_patterns: Vec<PatternCount> = pattern_counts
        .iter()
        .map(|(id, &count)| PatternCount {
            pattern_id: id.clone(),
            count,
        })
        .collect();
    top_patterns.sort_by(|a, b| b.count.cmp(&a.count));
    top_patterns.truncate(10);

    // ── Pattern effectiveness (T24.2) ──
    // Show patterns injected 3+ times with citation stats
    let mut effectiveness: Vec<PatternEffectiveness> = pattern_counts
        .iter()
        .filter(|(_, &count)| count >= 3)
        .map(|(pid, &injection_count)| {
            let citation_count = pattern_citation_counts.get(pid).copied().unwrap_or(0);
            let mut cited_task_ids: Vec<String> = pattern_cited_tasks
                .get(pid)
                .map(|s| s.iter().cloned().collect())
                .unwrap_or_default();
            cited_task_ids.sort();
            PatternEffectiveness {
                pattern_id: pid.clone(),
                injection_count,
                citation_count,
                citation_rate: if injection_count > 0 {
                    citation_count as f64 / injection_count as f64
                } else {
                    0.0
                },
                cited_task_ids,
                low_signal: injection_count >= 5 && citation_count == 0,
            }
        })
        .collect();
    effectiveness.sort_by(|a, b| b.injection_count.cmp(&a.injection_count));

    // ── Assemble report ──

    StatsReport {
        window: WindowInfo {
            days,
            from: cutoff.to_string(),
            to: today.to_string(),
            events_parsed: events.len(),
            lines_skipped: skipped,
        },
        project: project.map(|s| s.to_string()),
        summary: Summary {
            total_sessions: sessions.len(),
            total_tasks: tasks.len(),
            feat_count,
            wip_count,
            feat_wip_ratio: if wip_count > 0 {
                Some(feat_count as f64 / wip_count as f64)
            } else {
                None
            },
            total_cost_usd: total_cost,
            pass_rate_by_complexity,
            task_costs,
        },
        phase_costs,
        quality: Quality {
            doubt_finding_rate: if !tasks_reviewed.is_empty() {
                Some(tasks_with_findings.len() as f64 / tasks_reviewed.len() as f64)
            } else {
                None
            },
            tasks_with_findings: tasks_with_findings.len(),
            tasks_reviewed: tasks_reviewed.len(),
            budget_overrun_rate: if agent_done_count > 0 {
                Some(budget_overruns as f64 / agent_done_count as f64)
            } else {
                None
            },
            budget_overruns,
            budgeted_executions: agent_done_count,
        },
        patterns: PatternsInfo {
            total_injections,
            unique_patterns,
            top_patterns,
            effectiveness,
        },
    }
}

// ─── Table Output ────────────────────────────────────────────

fn fmt_tokens(n: u64) -> String {
    if n >= 1_000_000 {
        format!("{:.1}M", n as f64 / 1_000_000.0)
    } else if n >= 1_000 {
        format!("{:.1}K", n as f64 / 1_000.0)
    } else {
        n.to_string()
    }
}

fn print_table(report: &StatsReport) {
    println!("Foundry Stats");
    println!("=============");
    println!(
        "Window:  {} .. {} ({} days)",
        report.window.from, report.window.to, report.window.days
    );
    if let Some(ref p) = report.project {
        println!("Project: {}", p);
    }
    println!(
        "Events:  {} parsed, {} skipped",
        report.window.events_parsed, report.window.lines_skipped
    );
    println!();

    // Summary
    println!("Summary");
    println!("-------");
    println!("Sessions:    {}", report.summary.total_sessions);
    println!("Tasks:       {}", report.summary.total_tasks);
    let ratio_str = match report.summary.feat_wip_ratio {
        Some(r) => format!("{:.1}", r),
        None => "n/a".to_string(),
    };
    println!(
        "Commits:     {} feat / {} WIP  (ratio: {})",
        report.summary.feat_count, report.summary.wip_count, ratio_str
    );
    println!("Total Cost:  ${:.2}", report.summary.total_cost_usd);
    println!();

    // Cost by Phase
    println!("Cost by Phase");
    println!("-------------");
    if report.phase_costs.is_empty() {
        println!("  (no data)");
    } else {
        println!(
            "  {:<16} {:>6} {:>10} {:>10} {:>10}",
            "Role", "Runs", "Cost ($)", "Tokens In", "Tokens Out"
        );
        for pc in &report.phase_costs {
            println!(
                "  {:<16} {:>6} {:>10.2} {:>10} {:>10}",
                pc.role,
                pc.invocations,
                pc.cost_usd,
                fmt_tokens(pc.tokens_in),
                fmt_tokens(pc.tokens_out)
            );
        }
    }
    println!();

    // Quality Signals
    println!("Quality Signals");
    println!("---------------");
    match report.quality.doubt_finding_rate {
        Some(r) => println!(
            "  Doubt finding rate:   {:.1}%  ({} of {} reviewed tasks had findings)",
            r * 100.0,
            report.quality.tasks_with_findings,
            report.quality.tasks_reviewed
        ),
        None => println!("  Doubt finding rate:   n/a  (no reviewed tasks)"),
    }
    match report.quality.budget_overrun_rate {
        Some(r) => println!(
            "  Budget overrun rate:  {:.1}%  ({} of {} phase executions)",
            r * 100.0,
            report.quality.budget_overruns,
            report.quality.budgeted_executions
        ),
        None => println!("  Budget overrun rate:  n/a  (no phase executions)"),
    }
    if !report.summary.pass_rate_by_complexity.is_empty() {
        println!();
        println!("  Pass Rate by Complexity:");
        for pr in &report.summary.pass_rate_by_complexity {
            println!(
                "    {:<12} {:.1}%  ({}/{})",
                pr.complexity,
                pr.rate * 100.0,
                pr.feat,
                pr.total
            );
        }
    }
    println!();

    // Top Patterns
    println!("Top Patterns");
    println!("------------");
    if report.patterns.top_patterns.is_empty() {
        println!("  (no patterns injected)");
    } else {
        println!(
            "  Total injections: {}  ({} unique patterns)",
            report.patterns.total_injections, report.patterns.unique_patterns
        );
        println!("  {:<40} {:>6}", "Pattern", "Count");
        for p in &report.patterns.top_patterns {
            println!("  {:<40} {:>6}", p.pattern_id, p.count);
        }
    }

    // Pattern Effectiveness (T24.2)
    if !report.patterns.effectiveness.is_empty() {
        println!();
        println!("Pattern Effectiveness");
        println!("---------------------");
        println!(
            "  {:<40} {:>8} {:>8} {:>8} {:>10}",
            "Pattern", "Injected", "Cited", "Rate", "Signal"
        );
        for pe in &report.patterns.effectiveness {
            let signal = if pe.low_signal { "LOW" } else { "ok" };
            println!(
                "  {:<40} {:>8} {:>8} {:>7.1}% {:>10}",
                pe.pattern_id, pe.injection_count, pe.citation_count,
                pe.citation_rate * 100.0, signal
            );
            if !pe.cited_task_ids.is_empty() {
                println!("    cited in: {}", pe.cited_task_ids.join(", "));
            }
        }
    }
}

// ─── Tests ───────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    fn make_event(
        ts: &str,
        session: &str,
        project: &str,
        event_type: &str,
        payload: serde_json::Value,
    ) -> EventEnvelope {
        EventEnvelope {
            timestamp: ts.to_string(),
            session_id: session.to_string(),
            project_dir: project.to_string(),
            event_type: event_type.to_string(),
            payload,
        }
    }

    /// A complete synthetic session with 2 tasks exercising all event types.
    fn synthetic_session() -> Vec<EventEnvelope> {
        let p = "/test/project";
        let s = "sess-1";
        vec![
            make_event(
                "2025-01-15T10:00:00Z", s, p, "session_started",
                serde_json::json!({"type": "SessionStarted", "config": {}}),
            ),
            make_event(
                "2025-01-15T10:01:00Z", s, p, "task_started",
                serde_json::json!({"type": "TaskStarted", "task_id": "T1", "description": "Build X", "complexity": "medium"}),
            ),
            make_event(
                "2025-01-15T10:02:00Z", s, p, "agent_done",
                serde_json::json!({"type": "AgentDone", "role": "planner", "success": true, "duration_secs": 30.0, "tokens_in": 1000, "tokens_out": 500, "cost_usd": 0.05, "context_pct": 10}),
            ),
            make_event(
                "2025-01-15T10:03:00Z", s, p, "agent_done",
                serde_json::json!({"type": "AgentDone", "role": "builder", "success": true, "duration_secs": 60.0, "tokens_in": 5000, "tokens_out": 2000, "cost_usd": 0.25, "context_pct": 30}),
            ),
            make_event(
                "2025-01-15T10:04:00Z", s, p, "review_findings",
                serde_json::json!({"type": "ReviewFindings", "task_id": "T1", "high": 0, "medium": 0, "low": 1, "findings_json": "[]"}),
            ),
            make_event(
                "2025-01-15T10:05:00Z", s, p, "pattern_injected",
                serde_json::json!({"type": "PatternInjected", "task_id": "T1", "pattern_ids": ["pat-a", "pat-b"], "count": 2}),
            ),
            make_event(
                "2025-01-15T10:06:00Z", s, p, "committed",
                serde_json::json!({"type": "Committed", "task_id": "T1", "sha": "abc123", "commit_type": "feat"}),
            ),
            // Second task in same session
            make_event(
                "2025-01-15T10:10:00Z", s, p, "task_started",
                serde_json::json!({"type": "TaskStarted", "task_id": "T2", "description": "Fix Y", "complexity": "simple"}),
            ),
            make_event(
                "2025-01-15T10:11:00Z", s, p, "agent_done",
                serde_json::json!({"type": "AgentDone", "role": "builder", "success": true, "duration_secs": 45.0, "tokens_in": 3000, "tokens_out": 1000, "cost_usd": 0.15, "context_pct": 20}),
            ),
            make_event(
                "2025-01-15T10:12:00Z", s, p, "review_findings",
                serde_json::json!({"type": "ReviewFindings", "task_id": "T2", "high": 1, "medium": 0, "low": 0, "findings_json": "[]"}),
            ),
            make_event(
                "2025-01-15T10:13:00Z", s, p, "committed",
                serde_json::json!({"type": "Committed", "task_id": "T2", "sha": "def456", "commit_type": "WIP"}),
            ),
            make_event(
                "2025-01-15T10:20:00Z", s, p, "session_ended",
                serde_json::json!({"type": "SessionEnded", "total_tasks": 2, "feat_count": 1, "wip_count": 1, "total_cost_usd": 0.45, "duration_secs": 1200.0}),
            ),
        ]
    }

    #[test]
    fn test_empty_report() {
        let report = compute_stats(&[], 0, 7, None);
        assert_eq!(report.summary.total_sessions, 0);
        assert_eq!(report.summary.total_tasks, 0);
        assert_eq!(report.summary.total_cost_usd, 0.0);
        assert!(report.phase_costs.is_empty());
        assert!(report.patterns.top_patterns.is_empty());
        assert!(report.quality.doubt_finding_rate.is_none());
        assert!(report.quality.budget_overrun_rate.is_none());
    }

    #[test]
    fn test_summary_metrics() {
        let events = synthetic_session();
        let report = compute_stats(&events, 0, 7, None);

        assert_eq!(report.summary.total_sessions, 1);
        assert_eq!(report.summary.total_tasks, 2);
        assert_eq!(report.summary.feat_count, 1);
        assert_eq!(report.summary.wip_count, 1);
        assert_eq!(report.summary.feat_wip_ratio, Some(1.0));
        assert!((report.summary.total_cost_usd - 0.45).abs() < 0.001);
    }

    #[test]
    fn test_phase_costs() {
        let events = synthetic_session();
        let report = compute_stats(&events, 0, 7, None);

        // builder: 2 invocations (0.25 + 0.15 = 0.40)
        let builder = report
            .phase_costs
            .iter()
            .find(|p| p.role == "builder")
            .unwrap();
        assert_eq!(builder.invocations, 2);
        assert!((builder.cost_usd - 0.40).abs() < 0.001);
        assert_eq!(builder.tokens_in, 8000);
        assert_eq!(builder.tokens_out, 3000);

        // planner: 1 invocation (0.05)
        let planner = report
            .phase_costs
            .iter()
            .find(|p| p.role == "planner")
            .unwrap();
        assert_eq!(planner.invocations, 1);
        assert!((planner.cost_usd - 0.05).abs() < 0.001);
    }

    #[test]
    fn test_pass_rate_by_complexity() {
        let events = synthetic_session();
        let report = compute_stats(&events, 0, 7, None);

        // medium: T1 committed as feat -> 100%
        let medium = report
            .summary
            .pass_rate_by_complexity
            .iter()
            .find(|p| p.complexity == "medium")
            .unwrap();
        assert_eq!(medium.total, 1);
        assert_eq!(medium.feat, 1);
        assert!((medium.rate - 1.0).abs() < 0.001);

        // simple: T2 committed as WIP -> 0%
        let simple = report
            .summary
            .pass_rate_by_complexity
            .iter()
            .find(|p| p.complexity == "simple")
            .unwrap();
        assert_eq!(simple.total, 1);
        assert_eq!(simple.feat, 0);
        assert!(simple.rate.abs() < 0.001);
    }

    #[test]
    fn test_task_cost_boundaries() {
        let events = synthetic_session();
        let report = compute_stats(&events, 0, 7, None);

        // T1 cost: planner(0.05) + builder(0.25) = 0.30
        let t1 = report
            .summary
            .task_costs
            .iter()
            .find(|t| t.task_id == "T1")
            .unwrap();
        assert!((t1.cost_usd - 0.30).abs() < 0.001);

        // T2 cost: builder(0.15) = 0.15
        let t2 = report
            .summary
            .task_costs
            .iter()
            .find(|t| t.task_id == "T2")
            .unwrap();
        assert!((t2.cost_usd - 0.15).abs() < 0.001);
    }

    #[test]
    fn test_quality_signals() {
        let events = synthetic_session();
        let report = compute_stats(&events, 0, 7, None);

        // 2 reviewed tasks, 1 with findings (T2 has high=1)
        assert_eq!(report.quality.tasks_reviewed, 2);
        assert_eq!(report.quality.tasks_with_findings, 1);
        assert!((report.quality.doubt_finding_rate.unwrap() - 0.5).abs() < 0.001);

        // 0 budget overruns, 3 agent_done events
        assert_eq!(report.quality.budget_overruns, 0);
        assert_eq!(report.quality.budgeted_executions, 3);
        assert!((report.quality.budget_overrun_rate.unwrap()).abs() < 0.001);
    }

    #[test]
    fn test_pattern_totals() {
        let events = synthetic_session();
        let report = compute_stats(&events, 0, 7, None);

        assert_eq!(report.patterns.total_injections, 1);
        assert_eq!(report.patterns.unique_patterns, 2);
        assert_eq!(report.patterns.top_patterns.len(), 2);
        for p in &report.patterns.top_patterns {
            assert_eq!(p.count, 1);
        }
    }

    #[test]
    fn test_budget_overrun_rate() {
        let p = "/test/project";
        let s = "sess-1";
        let events = vec![
            make_event(
                "2025-01-15T10:00:00Z", s, p, "agent_done",
                serde_json::json!({"role": "builder", "cost_usd": 0.10, "tokens_in": 100, "tokens_out": 50}),
            ),
            make_event(
                "2025-01-15T10:01:00Z", s, p, "agent_done",
                serde_json::json!({"role": "reviewer", "cost_usd": 0.05, "tokens_in": 50, "tokens_out": 25}),
            ),
            make_event(
                "2025-01-15T10:02:00Z", s, p, "budget_overrun",
                serde_json::json!({"task_id": "T1", "phase": "builder", "target_pct": 80, "actual_pct": 95, "recovery_action": "skip_doubt"}),
            ),
        ];
        let report = compute_stats(&events, 0, 7, None);

        assert_eq!(report.quality.budget_overruns, 1);
        assert_eq!(report.quality.budgeted_executions, 2);
        assert!((report.quality.budget_overrun_rate.unwrap() - 0.5).abs() < 0.001);
    }

    #[test]
    fn test_load_events_malformed_lines() {
        let dir = tempfile::tempdir().unwrap();
        let today = Utc::now().format("%Y-%m-%d");
        let filepath = dir.path().join(format!("events-{}.jsonl", today));

        let good_line = serde_json::json!({
            "timestamp": "2025-01-15T10:00:00Z",
            "session_id": "s1",
            "project_dir": "/test",
            "event_type": "session_started",
            "payload": {"type": "SessionStarted", "config": {}}
        });

        std::fs::write(
            &filepath,
            format!("{}\nthis is not json\n{}\n", good_line, good_line),
        )
        .unwrap();

        let (events, skipped) = load_events(dir.path(), 7, None).unwrap();
        assert_eq!(events.len(), 2);
        assert_eq!(skipped, 1);
    }

    #[test]
    fn test_load_events_project_filter() {
        let dir = tempfile::tempdir().unwrap();
        let today = Utc::now().format("%Y-%m-%d");
        let filepath = dir.path().join(format!("events-{}.jsonl", today));

        let event_a = serde_json::json!({
            "timestamp": "2025-01-15T10:00:00Z",
            "session_id": "s1",
            "project_dir": "/project/a",
            "event_type": "session_started",
            "payload": {}
        });
        let event_b = serde_json::json!({
            "timestamp": "2025-01-15T10:01:00Z",
            "session_id": "s2",
            "project_dir": "/project/b",
            "event_type": "session_started",
            "payload": {}
        });

        std::fs::write(&filepath, format!("{}\n{}\n", event_a, event_b)).unwrap();

        // Filter: dunce::canonicalize will fail on non-existent path, fallback to raw
        let (events, _) = load_events(dir.path(), 7, Some(Path::new("/project/a"))).unwrap();
        assert_eq!(events.len(), 1);
        assert_eq!(events[0].project_dir, "/project/a");
    }

    #[test]
    fn test_json_output_has_required_keys() {
        let events = synthetic_session();
        let report = compute_stats(&events, 0, 7, Some("/test/project"));

        let json = serde_json::to_value(&report).unwrap();
        assert!(json.get("window").is_some());
        assert!(json.get("project").is_some());
        assert!(json.get("summary").is_some());
        assert!(json.get("phase_costs").is_some());
        assert!(json.get("quality").is_some());
        assert!(json.get("patterns").is_some());
    }

    #[test]
    fn test_feat_wip_ratio_no_wip() {
        let p = "/test/project";
        let s = "sess-1";
        let events = vec![
            make_event(
                "2025-01-15T10:00:00Z", s, p, "committed",
                serde_json::json!({"task_id": "T1", "sha": "abc", "commit_type": "feat"}),
            ),
        ];
        let report = compute_stats(&events, 0, 7, None);
        // No WIP commits -> ratio is None
        assert!(report.summary.feat_wip_ratio.is_none());
        assert_eq!(report.summary.feat_count, 1);
        assert_eq!(report.summary.wip_count, 0);
    }

    #[test]
    fn test_pattern_cited_tracking() {
        let p = "/test/project";
        let s = "sess-1";
        let events = vec![
            make_event(
                "2025-01-15T10:00:00Z", s, p, "pattern_injected",
                serde_json::json!({"type": "PatternInjected", "task_id": "T1", "pattern_ids": ["pat-a", "pat-b", "pat-c"], "count": 3}),
            ),
            make_event(
                "2025-01-15T10:01:00Z", s, p, "pattern_injected",
                serde_json::json!({"type": "PatternInjected", "task_id": "T2", "pattern_ids": ["pat-a", "pat-b"], "count": 2}),
            ),
            make_event(
                "2025-01-15T10:02:00Z", s, p, "pattern_injected",
                serde_json::json!({"type": "PatternInjected", "task_id": "T3", "pattern_ids": ["pat-a"], "count": 1}),
            ),
            // pat-a cited in T1 and T2
            make_event(
                "2025-01-15T10:03:00Z", s, p, "pattern_cited",
                serde_json::json!({"type": "PatternCited", "task_id": "T1", "role": "Planner", "artifact": "current-plan.md", "pattern_id": "pat-a"}),
            ),
            make_event(
                "2025-01-15T10:04:00Z", s, p, "pattern_cited",
                serde_json::json!({"type": "PatternCited", "task_id": "T2", "role": "Reviewer", "artifact": "review-report.md", "pattern_id": "pat-a"}),
            ),
            // pat-b cited in T1 only
            make_event(
                "2025-01-15T10:05:00Z", s, p, "pattern_cited",
                serde_json::json!({"type": "PatternCited", "task_id": "T1", "role": "Planner", "artifact": "current-plan.md", "pattern_id": "pat-b"}),
            ),
        ];
        let report = compute_stats(&events, 0, 7, None);

        // pat-a: injected 3 times, cited 2 times
        let pat_a = report.patterns.effectiveness.iter().find(|e| e.pattern_id == "pat-a").unwrap();
        assert_eq!(pat_a.injection_count, 3);
        assert_eq!(pat_a.citation_count, 2);
        assert!((pat_a.citation_rate - 2.0 / 3.0).abs() < 0.001);
        assert!(!pat_a.low_signal);
        assert!(pat_a.cited_task_ids.contains(&"T1".to_string()));
        assert!(pat_a.cited_task_ids.contains(&"T2".to_string()));

        // pat-b: injected 2 times (below threshold of 3) -- should NOT appear in effectiveness
        assert!(report.patterns.effectiveness.iter().find(|e| e.pattern_id == "pat-b").is_none());

        // pat-c: injected 1 time -- should NOT appear in effectiveness
        assert!(report.patterns.effectiveness.iter().find(|e| e.pattern_id == "pat-c").is_none());
    }

    #[test]
    fn test_pattern_low_signal_flag() {
        let p = "/test/project";
        let s = "sess-1";
        // Inject pat-x 5 times across 5 tasks, never cite it
        let mut events = Vec::new();
        for i in 1..=5 {
            events.push(make_event(
                &format!("2025-01-15T10:{:02}:00Z", i), s, p, "pattern_injected",
                serde_json::json!({"type": "PatternInjected", "task_id": format!("T{}", i), "pattern_ids": ["pat-x"], "count": 1}),
            ));
        }
        let report = compute_stats(&events, 0, 7, None);

        let pat_x = report.patterns.effectiveness.iter().find(|e| e.pattern_id == "pat-x").unwrap();
        assert_eq!(pat_x.injection_count, 5);
        assert_eq!(pat_x.citation_count, 0);
        assert!(pat_x.low_signal, "pattern injected 5+ times with 0 citations should be low_signal=true");
        assert!(pat_x.cited_task_ids.is_empty());
        assert!((pat_x.citation_rate).abs() < 0.001);
    }

    #[test]
    fn test_uncited_patterns_not_in_cited_stats() {
        let p = "/test/project";
        let s = "sess-1";
        let events = vec![
            // Inject pat-a and pat-b into 3 tasks each
            make_event(
                "2025-01-15T10:00:00Z", s, p, "pattern_injected",
                serde_json::json!({"type": "PatternInjected", "task_id": "T1", "pattern_ids": ["pat-a", "pat-b"], "count": 2}),
            ),
            make_event(
                "2025-01-15T10:01:00Z", s, p, "pattern_injected",
                serde_json::json!({"type": "PatternInjected", "task_id": "T2", "pattern_ids": ["pat-a", "pat-b"], "count": 2}),
            ),
            make_event(
                "2025-01-15T10:02:00Z", s, p, "pattern_injected",
                serde_json::json!({"type": "PatternInjected", "task_id": "T3", "pattern_ids": ["pat-a", "pat-b"], "count": 2}),
            ),
            // Only pat-a is cited; pat-b is never cited
            make_event(
                "2025-01-15T10:03:00Z", s, p, "pattern_cited",
                serde_json::json!({"type": "PatternCited", "task_id": "T1", "role": "Planner", "artifact": "current-plan.md", "pattern_id": "pat-a"}),
            ),
            // PatternApplied only contains cited subset (pat-a only)
            make_event(
                "2025-01-15T10:04:00Z", s, p, "pattern_applied",
                serde_json::json!({"type": "PatternApplied", "task_id": "T1", "pattern_ids": ["pat-a"], "count": 1}),
            ),
        ];
        let report = compute_stats(&events, 0, 7, None);

        // pat-a: injected 3, cited 1
        let pat_a = report.patterns.effectiveness.iter().find(|e| e.pattern_id == "pat-a").unwrap();
        assert_eq!(pat_a.citation_count, 1);
        assert!(!pat_a.low_signal);

        // pat-b: injected 3, cited 0 -- effectiveness shows it with low_signal=false (needs 5+ for low_signal)
        let pat_b = report.patterns.effectiveness.iter().find(|e| e.pattern_id == "pat-b").unwrap();
        assert_eq!(pat_b.injection_count, 3);
        assert_eq!(pat_b.citation_count, 0);
        assert!(!pat_b.low_signal, "low_signal only triggers at injection_count >= 5");
        assert!(pat_b.cited_task_ids.is_empty());
    }

    #[test]
    fn test_pattern_effectiveness_empty_below_threshold() {
        let p = "/test/project";
        let s = "sess-1";
        let events = vec![
            make_event(
                "2025-01-15T10:00:00Z", s, p, "pattern_injected",
                serde_json::json!({"type": "PatternInjected", "task_id": "T1", "pattern_ids": ["pat-a"], "count": 1}),
            ),
            make_event(
                "2025-01-15T10:01:00Z", s, p, "pattern_injected",
                serde_json::json!({"type": "PatternInjected", "task_id": "T2", "pattern_ids": ["pat-a"], "count": 1}),
            ),
        ];
        let report = compute_stats(&events, 0, 7, None);

        // pat-a only injected 2 times, below threshold of 3
        assert!(report.patterns.effectiveness.is_empty());
    }
}
