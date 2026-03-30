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
    pub trust: Option<TrustDashboard>,
    pub trend: Option<TrendData>,
    pub pr_reviews: Option<PrReviewStats>,
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

#[derive(Debug, Serialize)]
pub struct TrustDashboard {
    pub acceptance_rate: Option<f64>,
    pub completed_tasks: usize,
    pub feat_tasks: usize,
    pub review_rescue_rate: Option<f64>,
    pub rescued_tasks: usize,
    pub tasks_with_findings: usize,
    pub longest_feat_streak: usize,
    pub model_comparisons: Vec<ModelComparison>,
    pub regression_proxies: Vec<RegressionProxy>,
}

#[derive(Debug, Serialize)]
pub struct ModelComparison {
    pub model_key: String,
    pub task_count: usize,
    pub feat_rate: f64,
    pub avg_cost_per_task: f64,
    pub avg_duration_per_task: f64,
}

#[derive(Debug, Serialize)]
pub struct RegressionProxy {
    pub discovery_task_id: String,
    pub discovery_description: String,
    pub prior_feat_task_id: String,
    pub shared_tokens: Vec<String>,
}

#[derive(Debug, Serialize)]
pub struct TrendData {
    pub daily_pass_rate: Vec<DailyMetric>,
    pub daily_avg_cost: Vec<DailyMetric>,
}

#[derive(Debug, Serialize)]
pub struct DailyMetric {
    pub date: String,
    pub value: f64,
    pub count: usize,
}

#[derive(Debug, Serialize)]
pub struct PrReviewStats {
    pub total_reviews: usize,
    pub failed_reviews: usize,
    pub total_cost_usd: f64,
    pub findings_high: usize,
    pub findings_medium: usize,
    pub findings_low: usize,
    pub reviews: Vec<PrReviewEntry>,
}

#[derive(Debug, Serialize)]
pub struct PrReviewEntry {
    pub session_id: String,
    pub high: usize,
    pub medium: usize,
    pub low: usize,
    pub cost_usd: f64,
}

// ─── Entry Point ─────────────────────────────────────────────

pub fn run_stats(days: u32, project: &Path, output: &str, trend: bool) -> Result<()> {
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
        trend,
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

// ─── Internal Types ─────────────────────────────────────────

struct CompletedTask {
    task_id: String,
    verdict: String,
    #[allow(dead_code)]
    complexity: String,
    total_cost_usd: f64,
    total_duration_secs: f64,
    findings_high: usize,
    findings_medium: usize,
    #[allow(dead_code)]
    findings_low: usize,
    #[allow(dead_code)]
    phases_run: String,
    builder_provider: String,
    builder_model: String,
    #[allow(dead_code)]
    reviewer_provider: String,
    #[allow(dead_code)]
    reviewer_model: String,
    #[allow(dead_code)]
    commit_sha: String,
    timestamp: String,
    description: String,
}

// ─── Computation ─────────────────────────────────────────────

fn is_pr_review_session(session_id: &str) -> bool {
    session_id.starts_with("pr-review-")
}

pub fn compute_stats(
    events: &[EventEnvelope],
    skipped: usize,
    days: u32,
    project: Option<&str>,
    trend: bool,
) -> StatsReport {
    let today = Utc::now().date_naive();
    let cutoff = today - chrono::Duration::days(days as i64);

    let mut sessions = HashSet::new();
    let mut tasks = HashSet::new();
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

    // TaskCompleted tracking (T24.3)
    let mut completed_tasks: Vec<CompletedTask> = Vec::new();
    let mut task_descriptions: HashMap<String, String> = HashMap::new();

    // PR review tracking (D58.1)
    let mut pr_review_sessions: HashSet<String> = HashSet::new();
    let mut pr_review_costs: HashMap<String, f64> = HashMap::new();
    let mut pr_review_findings: Vec<PrReviewEntry> = Vec::new();

    for (idx, ev) in events.iter().enumerate() {
        session_events
            .entry(ev.session_id.clone())
            .or_default()
            .push(idx);

        match ev.event_type.as_str() {
            "session_started" => {
                if is_pr_review_session(&ev.session_id) {
                    pr_review_sessions.insert(ev.session_id.clone());
                } else {
                    sessions.insert(ev.session_id.clone());
                }
            }
            "task_started" => {
                if is_pr_review_session(&ev.session_id) {
                    // PR reviews don't emit TaskStarted, but skip if they ever do
                } else if let Some(task_id) = ev.payload.get("task_id").and_then(|v| v.as_str()) {
                    tasks.insert((ev.session_id.clone(), task_id.to_string()));
                    if let Some(complexity) =
                        ev.payload.get("complexity").and_then(|v| v.as_str())
                    {
                        task_complexity.insert(
                            (ev.session_id.clone(), task_id.to_string()),
                            complexity.to_string(),
                        );
                    }
                    if let Some(desc) = ev.payload.get("description").and_then(|v| v.as_str()) {
                        task_descriptions.insert(task_id.to_string(), desc.to_string());
                    }
                }
            }
            "agent_done" => {
                let cost = ev
                    .payload
                    .get("cost_usd")
                    .and_then(|v| v.as_f64())
                    .unwrap_or(0.0);

                if is_pr_review_session(&ev.session_id) {
                    *pr_review_costs.entry(ev.session_id.clone()).or_insert(0.0) += cost;
                } else {
                    agent_done_count += 1;
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
            }
            "committed" => {
                if is_pr_review_session(&ev.session_id) {
                    // PR reviews don't emit Committed, but skip if they ever do
                } else if let (Some(task_id), Some(commit_type)) = (
                    ev.payload.get("task_id").and_then(|v| v.as_str()),
                    ev.payload.get("commit_type").and_then(|v| v.as_str()),
                ) {
                    // Last commit for a (session, task) wins
                    task_committed.insert(
                        (ev.session_id.clone(), task_id.to_string()),
                        commit_type.to_string(),
                    );
                }
            }
            "review_findings" => {
                if is_pr_review_session(&ev.session_id) {
                    let high = ev.payload.get("high").and_then(|v| v.as_u64()).unwrap_or(0) as usize;
                    let medium = ev.payload.get("medium").and_then(|v| v.as_u64()).unwrap_or(0) as usize;
                    let low = ev.payload.get("low").and_then(|v| v.as_u64()).unwrap_or(0) as usize;
                    let cost = pr_review_costs.get(&ev.session_id).copied().unwrap_or(0.0);
                    pr_review_findings.push(PrReviewEntry {
                        session_id: ev.session_id.clone(),
                        high,
                        medium,
                        low,
                        cost_usd: cost,
                    });
                } else if let Some(task_id) = ev.payload.get("task_id").and_then(|v| v.as_str()) {
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
                if !is_pr_review_session(&ev.session_id) {
                    budget_overruns += 1;
                }
            }
            "pattern_injected" => {
                if !is_pr_review_session(&ev.session_id) {
                    total_injections += 1;
                    if let Some(ids) = ev.payload.get("pattern_ids").and_then(|v| v.as_array()) {
                        for id in ids {
                            if let Some(s) = id.as_str() {
                                *pattern_counts.entry(s.to_string()).or_insert(0) += 1;
                            }
                        }
                    }
                }
            }
            "pattern_cited" => {
                if !is_pr_review_session(&ev.session_id) {
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
            }
            "task_completed" => {
                if !is_pr_review_session(&ev.session_id) {
                    let tc = CompletedTask {
                        task_id: ev.payload.get("task_id").and_then(|v| v.as_str()).unwrap_or("").to_string(),
                        verdict: ev.payload.get("verdict").and_then(|v| v.as_str()).unwrap_or("").to_string(),
                        complexity: ev.payload.get("complexity").and_then(|v| v.as_str()).unwrap_or("").to_string(),
                        total_cost_usd: ev.payload.get("total_cost_usd").and_then(|v| v.as_f64()).unwrap_or(0.0),
                        total_duration_secs: ev.payload.get("total_duration_secs").and_then(|v| v.as_f64()).unwrap_or(0.0),
                        findings_high: ev.payload.get("findings_high").and_then(|v| v.as_u64()).unwrap_or(0) as usize,
                        findings_medium: ev.payload.get("findings_medium").and_then(|v| v.as_u64()).unwrap_or(0) as usize,
                        findings_low: ev.payload.get("findings_low").and_then(|v| v.as_u64()).unwrap_or(0) as usize,
                        phases_run: ev.payload.get("phases_run").and_then(|v| v.as_str()).unwrap_or("").to_string(),
                        builder_provider: ev.payload.get("builder_provider").and_then(|v| v.as_str()).unwrap_or("").to_string(),
                        builder_model: ev.payload.get("builder_model").and_then(|v| v.as_str()).unwrap_or("").to_string(),
                        reviewer_provider: ev.payload.get("reviewer_provider").and_then(|v| v.as_str()).unwrap_or("").to_string(),
                        reviewer_model: ev.payload.get("reviewer_model").and_then(|v| v.as_str()).unwrap_or("").to_string(),
                        commit_sha: ev.payload.get("commit_sha").and_then(|v| v.as_str()).unwrap_or("").to_string(),
                        timestamp: ev.timestamp.clone(),
                        description: String::new(),
                    };
                    completed_tasks.push(tc);
                }
            }
            _ => {}
        }
    }

    // ── Derive deduplicated feat/wip counts from task_committed HashMap ──
    // A retried task may have WIP then feat commits in one session;
    // task_committed keeps only the last commit_type per (session, task_id).
    let mut feat_count = 0usize;
    let mut wip_count = 0usize;
    for commit_type in task_committed.values() {
        let ct_lower = commit_type.to_lowercase();
        if ct_lower == "feat" {
            feat_count += 1;
        } else if ct_lower == "wip" {
            wip_count += 1;
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
        if is_pr_review_session(session_id) {
            continue;
        }
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

    // ── Trust Dashboard (T24.3) ──

    // Fill descriptions for completed tasks
    for ct in &mut completed_tasks {
        if ct.description.is_empty() {
            if let Some(desc) = task_descriptions.get(&ct.task_id) {
                ct.description = desc.clone();
            }
        }
    }

    let trust = if !completed_tasks.is_empty() {
        let total_completed = completed_tasks.len();
        let feat_completed = completed_tasks.iter().filter(|t| t.verdict == "feat").count();

        let acceptance_rate = if total_completed > 0 {
            Some(feat_completed as f64 / total_completed as f64)
        } else {
            None
        };

        // Review rescue rate: tasks with findings_high + findings_medium > 0 that ended as feat
        let tasks_with_hi_med: Vec<&CompletedTask> = completed_tasks
            .iter()
            .filter(|t| t.findings_high + t.findings_medium > 0)
            .collect();
        let rescued = tasks_with_hi_med.iter().filter(|t| t.verdict == "feat").count();
        let review_rescue_rate = if !tasks_with_hi_med.is_empty() {
            Some(rescued as f64 / tasks_with_hi_med.len() as f64)
        } else {
            None
        };

        // Longest feat streak: sort by timestamp, find max consecutive feats
        let mut sorted_tasks: Vec<&CompletedTask> = completed_tasks.iter().collect();
        sorted_tasks.sort_by(|a, b| a.timestamp.cmp(&b.timestamp));
        let mut max_streak = 0usize;
        let mut current_streak = 0usize;
        for t in &sorted_tasks {
            if t.verdict == "feat" {
                current_streak += 1;
                if current_streak > max_streak {
                    max_streak = current_streak;
                }
            } else {
                current_streak = 0;
            }
        }

        // Model comparison: group by builder_provider:builder_model
        let mut model_groups: HashMap<String, Vec<&CompletedTask>> = HashMap::new();
        for t in &completed_tasks {
            let key = format!("{}:{}", t.builder_provider, t.builder_model);
            model_groups.entry(key).or_default().push(t);
        }
        let mut model_comparisons: Vec<ModelComparison> = model_groups
            .into_iter()
            .map(|(key, tasks)| {
                let count = tasks.len();
                let feats = tasks.iter().filter(|t| t.verdict == "feat").count();
                let total_cost: f64 = tasks.iter().map(|t| t.total_cost_usd).sum();
                let total_dur: f64 = tasks.iter().map(|t| t.total_duration_secs).sum();
                ModelComparison {
                    model_key: key,
                    task_count: count,
                    feat_rate: if count > 0 { feats as f64 / count as f64 } else { 0.0 },
                    avg_cost_per_task: if count > 0 { total_cost / count as f64 } else { 0.0 },
                    avg_duration_per_task: if count > 0 { total_dur / count as f64 } else { 0.0 },
                }
            })
            .collect();
        model_comparisons.sort_by(|a, b| b.task_count.cmp(&a.task_count));

        // Regression proxy
        let regression_proxies = compute_regression_proxies(&completed_tasks);

        Some(TrustDashboard {
            acceptance_rate,
            completed_tasks: total_completed,
            feat_tasks: feat_completed,
            review_rescue_rate,
            rescued_tasks: rescued,
            tasks_with_findings: tasks_with_hi_med.len(),
            longest_feat_streak: max_streak,
            model_comparisons,
            regression_proxies,
        })
    } else {
        // Fallback to derived metrics from T24.1-style events
        let total_committed = feat_count + wip_count;
        if total_committed > 0 {
            let acceptance_rate = Some(feat_count as f64 / total_committed as f64);

            let rescued = tasks_with_findings
                .iter()
                .filter(|key| {
                    task_committed.get(*key).map(|ct| ct.to_lowercase() == "feat").unwrap_or(false)
                })
                .count();
            let review_rescue_rate = if !tasks_with_findings.is_empty() {
                Some(rescued as f64 / tasks_with_findings.len() as f64)
            } else {
                None
            };

            // Longest feat streak from committed events (sorted by timestamp)
            let mut committed_events: Vec<&EventEnvelope> = events
                .iter()
                .filter(|e| e.event_type == "committed" && !is_pr_review_session(&e.session_id))
                .collect();
            committed_events.sort_by(|a, b| a.timestamp.cmp(&b.timestamp));
            let mut max_streak = 0usize;
            let mut current_streak = 0usize;
            for ev in &committed_events {
                let ct = ev.payload.get("commit_type").and_then(|v| v.as_str()).unwrap_or("");
                if ct.to_lowercase() == "feat" {
                    current_streak += 1;
                    if current_streak > max_streak {
                        max_streak = current_streak;
                    }
                } else {
                    current_streak = 0;
                }
            }

            Some(TrustDashboard {
                acceptance_rate,
                completed_tasks: total_committed,
                feat_tasks: feat_count,
                review_rescue_rate,
                rescued_tasks: rescued,
                tasks_with_findings: tasks_with_findings.len(),
                longest_feat_streak: max_streak,
                model_comparisons: vec![],
                regression_proxies: vec![],
            })
        } else {
            None
        }
    };

    // ── Trend Data (T24.3) ──
    let trend_data = if trend {
        Some(compute_trend_data(&completed_tasks, events, days, &task_committed))
    } else {
        None
    };

    // ── PR Review Stats (D58.1) ──

    let pr_reviews = if !pr_review_sessions.is_empty() {
        let total_reviews = pr_review_findings.len();
        let failed_reviews = pr_review_sessions.len() - pr_review_findings.len();
        let total_pr_cost: f64 = pr_review_costs.values().sum();
        let total_high: usize = pr_review_findings.iter().map(|r| r.high).sum();
        let total_medium: usize = pr_review_findings.iter().map(|r| r.medium).sum();
        let total_low: usize = pr_review_findings.iter().map(|r| r.low).sum();
        Some(PrReviewStats {
            total_reviews,
            failed_reviews,
            total_cost_usd: total_pr_cost,
            findings_high: total_high,
            findings_medium: total_medium,
            findings_low: total_low,
            reviews: pr_review_findings,
        })
    } else {
        None
    };

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
        trust,
        trend: trend_data,
        pr_reviews,
    }
}

// ─── Helper Functions (T24.3) ────────────────────────────────

fn normalize_tokens(text: &str) -> Vec<String> {
    static STOPWORDS: &[&str] = &[
        "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
        "being", "have", "has", "had", "do", "does", "did", "will", "would",
        "could", "should", "may", "might", "shall", "can", "need", "must",
        "it", "its", "this", "that", "these", "those", "not", "no", "so",
        "if", "then", "else", "when", "up", "out", "all", "each", "every",
        "both", "few", "more", "most", "other", "some", "such", "only",
        "into", "over", "after", "before", "between", "under", "above",
        "add", "update", "fix", "remove", "change", "make", "set", "get",
    ];
    text.to_lowercase()
        .split(|c: char| !c.is_alphanumeric())
        .filter(|w| w.len() >= 3 && !STOPWORDS.contains(w))
        .map(|w| w.to_string())
        .collect()
}

fn compute_regression_proxies(completed_tasks: &[CompletedTask]) -> Vec<RegressionProxy> {
    let mut sorted: Vec<&CompletedTask> = completed_tasks.iter().collect();
    sorted.sort_by(|a, b| a.timestamp.cmp(&b.timestamp));

    let mut feat_history: Vec<(&str, &str, Vec<String>)> = Vec::new();
    let mut proxies: Vec<RegressionProxy> = Vec::new();

    for task in &sorted {
        if task.verdict == "feat" {
            let tokens = normalize_tokens(&task.description);
            feat_history.push((&task.task_id, &task.description, tokens));
        }

        if task.task_id.starts_with('D') || task.task_id.starts_with('d') {
            let disc_tokens = normalize_tokens(&task.description);
            for (feat_id, _feat_desc, feat_tokens) in &feat_history {
                let shared: Vec<String> = disc_tokens
                    .iter()
                    .filter(|t| feat_tokens.contains(t))
                    .cloned()
                    .collect();
                if shared.len() >= 2 {
                    proxies.push(RegressionProxy {
                        discovery_task_id: task.task_id.clone(),
                        discovery_description: task.description.clone(),
                        prior_feat_task_id: feat_id.to_string(),
                        shared_tokens: shared,
                    });
                    break;
                }
            }
        }
    }

    proxies
}

fn compute_trend_data(
    completed_tasks: &[CompletedTask],
    events: &[EventEnvelope],
    days: u32,
    task_committed: &HashMap<(String, String), String>,
) -> TrendData {
    let today = Utc::now().date_naive();
    let cutoff = today - chrono::Duration::days(days as i64);

    if !completed_tasks.is_empty() {
        let mut daily: BTreeMap<String, (usize, usize, f64)> = BTreeMap::new();

        for task in completed_tasks {
            let date_str = task.timestamp.get(..10).unwrap_or("").to_string();
            if date_str.is_empty() {
                continue;
            }
            let entry = daily.entry(date_str).or_insert((0, 0, 0.0));
            entry.1 += 1;
            if task.verdict == "feat" {
                entry.0 += 1;
            }
            entry.2 += task.total_cost_usd;
        }

        let daily_pass_rate: Vec<DailyMetric> = daily
            .iter()
            .map(|(date, (feats, total, _))| DailyMetric {
                date: date.clone(),
                value: if *total > 0 { *feats as f64 / *total as f64 } else { 0.0 },
                count: *total,
            })
            .collect();

        let daily_avg_cost: Vec<DailyMetric> = daily
            .iter()
            .map(|(date, (_, total, cost))| DailyMetric {
                date: date.clone(),
                value: if *total > 0 { *cost / *total as f64 } else { 0.0 },
                count: *total,
            })
            .collect();

        TrendData {
            daily_pass_rate,
            daily_avg_cost,
        }
    } else {
        // Fallback: derive from committed events, deduplicated via task_committed.
        // task_committed keeps only the last commit_type per (session, task_id).
        // Iterate events in reverse to find the last committed event per (session, task_id)
        // so we bucket by the date of the final commit, not an earlier retry.
        let mut daily: BTreeMap<String, (usize, usize)> = BTreeMap::new();
        let mut daily_cost: BTreeMap<String, (f64, usize)> = BTreeMap::new();
        let mut seen_committed: HashSet<(String, String)> = HashSet::new();

        for ev in events.iter().rev() {
            if is_pr_review_session(&ev.session_id) {
                continue;
            }
            let date_str = ev.timestamp.get(..10).unwrap_or("").to_string();
            if date_str.is_empty() {
                continue;
            }
            match ev.event_type.as_str() {
                "committed" => {
                    if let Some(task_id) = ev.payload.get("task_id").and_then(|v| v.as_str()) {
                        let key = (ev.session_id.clone(), task_id.to_string());
                        if task_committed.contains_key(&key) && seen_committed.insert(key) {
                            let final_ct = &task_committed[&(ev.session_id.clone(), task_id.to_string())];
                            let entry = daily.entry(date_str).or_insert((0, 0));
                            entry.1 += 1;
                            if final_ct.to_lowercase() == "feat" {
                                entry.0 += 1;
                            }
                        }
                    }
                }
                "agent_done" => {
                    let cost = ev.payload.get("cost_usd").and_then(|v| v.as_f64()).unwrap_or(0.0);
                    let entry = daily_cost.entry(date_str).or_insert((0.0, 0));
                    entry.0 += cost;
                    entry.1 += 1;
                }
                _ => {}
            }
        }

        let _ = cutoff;

        let daily_pass_rate: Vec<DailyMetric> = daily
            .iter()
            .map(|(date, (feats, total))| DailyMetric {
                date: date.clone(),
                value: if *total > 0 { *feats as f64 / *total as f64 } else { 0.0 },
                count: *total,
            })
            .collect();

        let daily_avg_cost: Vec<DailyMetric> = daily
            .iter()
            .map(|(date, (_, total))| {
                let cost_data = daily_cost.get(date);
                let total_cost = cost_data.map(|(c, _)| *c).unwrap_or(0.0);
                DailyMetric {
                    date: date.clone(),
                    value: if *total > 0 { total_cost / *total as f64 } else { 0.0 },
                    count: *total,
                }
            })
            .collect();

        TrendData {
            daily_pass_rate,
            daily_avg_cost,
        }
    }
}

fn sparkline(values: &[f64]) -> String {
    if values.is_empty() {
        return String::new();
    }
    let chars = ['_', '.', '-', '~', '=', '#', '@', '*'];
    let min = values.iter().cloned().fold(f64::INFINITY, f64::min);
    let max = values.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
    let range = max - min;
    values
        .iter()
        .map(|v| {
            if range == 0.0 {
                chars[chars.len() / 2]
            } else {
                let idx = (((v - min) / range) * (chars.len() - 1) as f64).round() as usize;
                chars[idx.min(chars.len() - 1)]
            }
        })
        .collect()
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

    // Trust Dashboard (T24.3)
    if let Some(ref trust) = report.trust {
        println!();
        println!("Trust Dashboard");
        println!("---------------");
        match trust.acceptance_rate {
            Some(r) => println!(
                "  Acceptance rate:      {:.1}%  ({} feat / {} completed)",
                r * 100.0, trust.feat_tasks, trust.completed_tasks
            ),
            None => println!("  Acceptance rate:      n/a  (no completed tasks)"),
        }
        match trust.review_rescue_rate {
            Some(r) => println!(
                "  Review rescue rate:   {:.1}%  ({} rescued / {} with findings)",
                r * 100.0, trust.rescued_tasks, trust.tasks_with_findings
            ),
            None => println!("  Review rescue rate:   n/a  (no tasks with findings)"),
        }
        println!("  Longest feat streak:  {}", trust.longest_feat_streak);

        if !trust.model_comparisons.is_empty() {
            println!();
            println!("  Model Comparison:");
            println!(
                "  {:<30} {:>6} {:>8} {:>10} {:>10}",
                "Model", "Tasks", "Feat %", "Avg Cost", "Avg Dur"
            );
            for mc in &trust.model_comparisons {
                println!(
                    "  {:<30} {:>6} {:>7.1}% {:>9.2} {:>9.1}s",
                    mc.model_key, mc.task_count, mc.feat_rate * 100.0,
                    mc.avg_cost_per_task, mc.avg_duration_per_task
                );
            }
        }

        if !trust.regression_proxies.is_empty() {
            println!();
            println!("  Regression Proxies (heuristic -- shared token overlap, not causal):");
            for rp in &trust.regression_proxies {
                println!(
                    "    {} may revisit {} (shared: {})",
                    rp.discovery_task_id,
                    rp.prior_feat_task_id,
                    rp.shared_tokens.join(", ")
                );
            }
        }
    }

    // Trend (T24.3)
    if let Some(ref trend) = report.trend {
        println!();
        println!("Trend");
        println!("-----");
        if !trend.daily_pass_rate.is_empty() {
            let values: Vec<f64> = trend.daily_pass_rate.iter().map(|d| d.value).collect();
            let spark = sparkline(&values);
            let first = &trend.daily_pass_rate[0].date;
            let last = &trend.daily_pass_rate[trend.daily_pass_rate.len() - 1].date;
            println!("  Pass rate:  {} .. {}  [{}]", first, last, spark);
            for d in &trend.daily_pass_rate {
                println!("    {}  {:.0}%  ({} tasks)", d.date, d.value * 100.0, d.count);
            }
        } else {
            println!("  Pass rate:  (no data)");
        }
        println!();
        if !trend.daily_avg_cost.is_empty() {
            let values: Vec<f64> = trend.daily_avg_cost.iter().map(|d| d.value).collect();
            let spark = sparkline(&values);
            let first = &trend.daily_avg_cost[0].date;
            let last = &trend.daily_avg_cost[trend.daily_avg_cost.len() - 1].date;
            println!("  Avg cost:   {} .. {}  [{}]", first, last, spark);
            for d in &trend.daily_avg_cost {
                println!("    {}  ${:.2}  ({} tasks)", d.date, d.value, d.count);
            }
        } else {
            println!("  Avg cost:   (no data)");
        }
    }

    // PR Reviews (D58.1)
    if let Some(ref pr) = report.pr_reviews {
        println!();
        println!("PR Reviews (excluded from build-loop metrics above)");
        println!("---------------------------------------------------");
        println!("  Total reviews:  {}", pr.total_reviews);
        if pr.failed_reviews > 0 {
            println!("  Failed reviews: {}", pr.failed_reviews);
        }
        println!("  Total cost:     ${:.2}", pr.total_cost_usd);
        println!(
            "  Findings:       {} high, {} medium, {} low",
            pr.findings_high, pr.findings_medium, pr.findings_low
        );
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
        let report = compute_stats(&[], 0, 7, None, false);
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
        let report = compute_stats(&events, 0, 7, None, false);

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
        let report = compute_stats(&events, 0, 7, None, false);

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
        let report = compute_stats(&events, 0, 7, None, false);

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
        let report = compute_stats(&events, 0, 7, None, false);

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
        let report = compute_stats(&events, 0, 7, None, false);

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
        let report = compute_stats(&events, 0, 7, None, false);

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
        let report = compute_stats(&events, 0, 7, None, false);

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
        let report = compute_stats(&events, 0, 7, Some("/test/project"), false);

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
        let report = compute_stats(&events, 0, 7, None, false);
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
        let report = compute_stats(&events, 0, 7, None, false);

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
        let report = compute_stats(&events, 0, 7, None, false);

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
        let report = compute_stats(&events, 0, 7, None, false);

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
        let report = compute_stats(&events, 0, 7, None, false);

        // pat-a only injected 2 times, below threshold of 3
        assert!(report.patterns.effectiveness.is_empty());
    }

    #[test]
    fn test_trust_dashboard_from_task_completed() {
        let p = "/test/project";
        let s = "sess-1";
        let events = vec![
            make_event(
                "2025-01-15T10:00:00Z", s, p, "session_started",
                serde_json::json!({"type": "SessionStarted", "config": {}}),
            ),
            make_event(
                "2025-01-15T10:01:00Z", s, p, "task_started",
                serde_json::json!({"type": "TaskStarted", "task_id": "T1", "description": "Build feature X", "complexity": "Medium"}),
            ),
            make_event(
                "2025-01-15T10:05:00Z", s, p, "task_completed",
                serde_json::json!({
                    "type": "TaskCompleted",
                    "task_id": "T1", "verdict": "feat", "complexity": "Medium",
                    "total_cost_usd": 0.50, "total_duration_secs": 240.0,
                    "findings_high": 0, "findings_medium": 1, "findings_low": 2,
                    "phases_run": "SPID", "builder_provider": "claude", "builder_model": "opus",
                    "reviewer_provider": "claude", "reviewer_model": "sonnet",
                    "commit_sha": "abc123"
                }),
            ),
            make_event(
                "2025-01-15T10:10:00Z", s, p, "task_started",
                serde_json::json!({"type": "TaskStarted", "task_id": "T2", "description": "Fix bug Y", "complexity": "Simple"}),
            ),
            make_event(
                "2025-01-15T10:15:00Z", s, p, "task_completed",
                serde_json::json!({
                    "type": "TaskCompleted",
                    "task_id": "T2", "verdict": "wip", "complexity": "Simple",
                    "total_cost_usd": 0.30, "total_duration_secs": 300.0,
                    "findings_high": 2, "findings_medium": 1, "findings_low": 0,
                    "phases_run": "-PID", "builder_provider": "claude", "builder_model": "opus",
                    "reviewer_provider": "claude", "reviewer_model": "sonnet",
                    "commit_sha": "def456"
                }),
            ),
            make_event(
                "2025-01-15T10:20:00Z", s, p, "task_completed",
                serde_json::json!({
                    "type": "TaskCompleted",
                    "task_id": "T3", "verdict": "feat", "complexity": "Medium",
                    "total_cost_usd": 0.40, "total_duration_secs": 200.0,
                    "findings_high": 1, "findings_medium": 0, "findings_low": 1,
                    "phases_run": "SPID", "builder_provider": "codex", "builder_model": "",
                    "reviewer_provider": "claude", "reviewer_model": "sonnet",
                    "commit_sha": "ghi789"
                }),
            ),
        ];
        let report = compute_stats(&events, 0, 7, None, false);
        let trust = report.trust.unwrap();

        // 3 completed, 2 feat -> 66.7%
        assert_eq!(trust.completed_tasks, 3);
        assert_eq!(trust.feat_tasks, 2);
        assert!((trust.acceptance_rate.unwrap() - 2.0 / 3.0).abs() < 0.001);

        // Tasks with findings (high+medium > 0): T1 (0+1=1), T2 (2+1=3), T3 (1+0=1) -> all 3
        // Rescued (verdict=feat among those): T1 and T3 -> 2/3
        assert_eq!(trust.tasks_with_findings, 3);
        assert_eq!(trust.rescued_tasks, 2);
        assert!((trust.review_rescue_rate.unwrap() - 2.0 / 3.0).abs() < 0.001);

        // Longest feat streak: T1=feat, T2=wip, T3=feat -> streak = 1
        assert_eq!(trust.longest_feat_streak, 1);

        // Model comparison: claude:opus (2 tasks), codex: (1 task)
        assert_eq!(trust.model_comparisons.len(), 2);
        let claude_opus = trust.model_comparisons.iter().find(|m| m.model_key == "claude:opus").unwrap();
        assert_eq!(claude_opus.task_count, 2);
        assert!((claude_opus.feat_rate - 0.5).abs() < 0.001);
        assert!((claude_opus.avg_cost_per_task - 0.40).abs() < 0.001);
    }

    #[test]
    fn test_trust_dashboard_fallback_no_task_completed() {
        let events = synthetic_session();
        let report = compute_stats(&events, 0, 7, None, false);
        let trust = report.trust.unwrap();

        // Fallback: 1 feat + 1 wip = 2 completed, acceptance = 50%
        assert_eq!(trust.completed_tasks, 2);
        assert_eq!(trust.feat_tasks, 1);
        assert!((trust.acceptance_rate.unwrap() - 0.5).abs() < 0.001);

        // T2 has high=1, committed as WIP -> 0 rescued / 1 with findings
        assert_eq!(trust.tasks_with_findings, 1);
        assert_eq!(trust.rescued_tasks, 0);
        assert!((trust.review_rescue_rate.unwrap() - 0.0).abs() < 0.001);

        // Streak: T1=feat, T2=WIP -> streak = 1
        assert_eq!(trust.longest_feat_streak, 1);

        // No model comparisons in fallback mode
        assert!(trust.model_comparisons.is_empty());
    }

    #[test]
    fn test_trend_data_from_task_completed() {
        let p = "/test/project";
        let s = "sess-1";
        let events = vec![
            make_event(
                "2025-01-15T10:00:00Z", s, p, "task_completed",
                serde_json::json!({
                    "type": "TaskCompleted",
                    "task_id": "T1", "verdict": "feat", "complexity": "Medium",
                    "total_cost_usd": 0.50, "total_duration_secs": 100.0,
                    "findings_high": 0, "findings_medium": 0, "findings_low": 0,
                    "phases_run": "SPID", "builder_provider": "claude", "builder_model": "opus",
                    "reviewer_provider": "claude", "reviewer_model": "sonnet",
                    "commit_sha": "a"
                }),
            ),
            make_event(
                "2025-01-15T11:00:00Z", s, p, "task_completed",
                serde_json::json!({
                    "type": "TaskCompleted",
                    "task_id": "T2", "verdict": "wip", "complexity": "Simple",
                    "total_cost_usd": 0.30, "total_duration_secs": 50.0,
                    "findings_high": 1, "findings_medium": 0, "findings_low": 0,
                    "phases_run": "-PID", "builder_provider": "claude", "builder_model": "opus",
                    "reviewer_provider": "claude", "reviewer_model": "sonnet",
                    "commit_sha": "b"
                }),
            ),
            make_event(
                "2025-01-16T09:00:00Z", s, p, "task_completed",
                serde_json::json!({
                    "type": "TaskCompleted",
                    "task_id": "T3", "verdict": "feat", "complexity": "Medium",
                    "total_cost_usd": 0.60, "total_duration_secs": 120.0,
                    "findings_high": 0, "findings_medium": 0, "findings_low": 0,
                    "phases_run": "SPID", "builder_provider": "claude", "builder_model": "opus",
                    "reviewer_provider": "claude", "reviewer_model": "sonnet",
                    "commit_sha": "c"
                }),
            ),
        ];
        let report = compute_stats(&events, 0, 7, None, true);
        let trend = report.trend.unwrap();

        // Day 2025-01-15: 2 tasks, 1 feat -> 50% pass rate, avg cost (0.50+0.30)/2 = 0.40
        assert_eq!(trend.daily_pass_rate.len(), 2);
        let day1 = &trend.daily_pass_rate[0];
        assert_eq!(day1.date, "2025-01-15");
        assert!((day1.value - 0.5).abs() < 0.001);
        assert_eq!(day1.count, 2);

        let day1_cost = &trend.daily_avg_cost[0];
        assert!((day1_cost.value - 0.40).abs() < 0.001);

        // Day 2025-01-16: 1 task, 1 feat -> 100% pass rate, avg cost 0.60
        let day2 = &trend.daily_pass_rate[1];
        assert_eq!(day2.date, "2025-01-16");
        assert!((day2.value - 1.0).abs() < 0.001);
        assert_eq!(day2.count, 1);
    }

    #[test]
    fn test_regression_proxy() {
        let p = "/test/project";
        let s = "sess-1";
        let events = vec![
            make_event(
                "2025-01-15T10:00:00Z", s, p, "task_started",
                serde_json::json!({"type": "TaskStarted", "task_id": "T1.1", "description": "Implement authentication middleware", "complexity": "Complex"}),
            ),
            make_event(
                "2025-01-15T10:05:00Z", s, p, "task_completed",
                serde_json::json!({
                    "type": "TaskCompleted",
                    "task_id": "T1.1", "verdict": "feat", "complexity": "Complex",
                    "total_cost_usd": 1.0, "total_duration_secs": 300.0,
                    "findings_high": 0, "findings_medium": 0, "findings_low": 0,
                    "phases_run": "SPID", "builder_provider": "claude", "builder_model": "opus",
                    "reviewer_provider": "claude", "reviewer_model": "sonnet",
                    "commit_sha": "aaa"
                }),
            ),
            make_event(
                "2025-01-16T10:00:00Z", s, p, "task_started",
                serde_json::json!({"type": "TaskStarted", "task_id": "D1.1", "description": "Authentication middleware returns wrong status code", "complexity": "Simple"}),
            ),
            make_event(
                "2025-01-16T10:05:00Z", s, p, "task_completed",
                serde_json::json!({
                    "type": "TaskCompleted",
                    "task_id": "D1.1", "verdict": "feat", "complexity": "Simple",
                    "total_cost_usd": 0.30, "total_duration_secs": 100.0,
                    "findings_high": 0, "findings_medium": 0, "findings_low": 0,
                    "phases_run": "-PID", "builder_provider": "claude", "builder_model": "opus",
                    "reviewer_provider": "claude", "reviewer_model": "sonnet",
                    "commit_sha": "bbb"
                }),
            ),
        ];
        let report = compute_stats(&events, 0, 7, None, false);
        let trust = report.trust.unwrap();

        // D1.1 should match T1.1: shared tokens "authentication" and "middleware"
        assert_eq!(trust.regression_proxies.len(), 1);
        assert_eq!(trust.regression_proxies[0].discovery_task_id, "D1.1");
        assert_eq!(trust.regression_proxies[0].prior_feat_task_id, "T1.1");
        assert!(trust.regression_proxies[0].shared_tokens.contains(&"authentication".to_string()));
        assert!(trust.regression_proxies[0].shared_tokens.contains(&"middleware".to_string()));
    }

    #[test]
    fn test_sparkline() {
        let values = vec![0.0, 0.25, 0.5, 0.75, 1.0];
        let spark = sparkline(&values);
        assert_eq!(spark.len(), 5);
        assert_eq!(spark.chars().next().unwrap(), '_');
        assert_eq!(spark.chars().last().unwrap(), '*');

        assert_eq!(sparkline(&[]), "");

        let same = sparkline(&[0.5, 0.5, 0.5]);
        assert_eq!(same.len(), 3);
        let chars: Vec<char> = same.chars().collect();
        assert!(chars.iter().all(|c| *c == chars[0]));
    }

    #[test]
    fn test_normalize_tokens() {
        let tokens = normalize_tokens("Implement authentication middleware for API");
        assert!(tokens.contains(&"implement".to_string()));
        assert!(tokens.contains(&"authentication".to_string()));
        assert!(tokens.contains(&"middleware".to_string()));
        assert!(tokens.contains(&"api".to_string()));
        assert!(!tokens.contains(&"for".to_string()));
    }

    #[test]
    fn test_compute_stats_passes_trend_false() {
        let events = synthetic_session();
        let report = compute_stats(&events, 0, 7, None, false);
        assert!(report.trend.is_none());
    }

    #[test]
    fn test_is_pr_review_session() {
        assert!(is_pr_review_session("pr-review-owner--repo-42"));
        assert!(is_pr_review_session("pr-review-alice-org--repo-10"));
        assert!(!is_pr_review_session("build-sess-1"));
        assert!(!is_pr_review_session(""));
        assert!(!is_pr_review_session("af20d11b-1234-5678-9abc-def012345678"));
    }

    #[test]
    fn test_pr_review_sessions_excluded_from_build_stats() {
        let p = "/test/project";
        let events = vec![
            // Build-loop session
            make_event(
                "2025-01-15T10:00:00Z", "build-sess-1", p, "session_started",
                serde_json::json!({"type": "SessionStarted", "config": {}}),
            ),
            make_event(
                "2025-01-15T10:01:00Z", "build-sess-1", p, "task_started",
                serde_json::json!({"type": "TaskStarted", "task_id": "T1", "description": "task", "complexity": "medium"}),
            ),
            make_event(
                "2025-01-15T10:02:00Z", "build-sess-1", p, "agent_done",
                serde_json::json!({"type": "AgentDone", "role": "Builder", "success": true, "duration_secs": 30.0, "tokens_in": 1000, "tokens_out": 500, "cost_usd": 0.10, "context_pct": 10}),
            ),
            make_event(
                "2025-01-15T10:03:00Z", "build-sess-1", p, "review_findings",
                serde_json::json!({"type": "ReviewFindings", "task_id": "T1", "high": 1, "medium": 0, "low": 0, "findings_json": "[]"}),
            ),
            make_event(
                "2025-01-15T10:04:00Z", "build-sess-1", p, "committed",
                serde_json::json!({"type": "Committed", "task_id": "T1", "sha": "abc", "commit_type": "feat"}),
            ),
            make_event(
                "2025-01-15T10:05:00Z", "build-sess-1", p, "session_ended",
                serde_json::json!({"type": "SessionEnded", "total_tasks": 1, "feat_count": 1, "wip_count": 0, "total_cost_usd": 0.10, "duration_secs": 300.0}),
            ),
            // PR review session -- should be excluded from build stats
            make_event(
                "2025-01-15T11:00:00Z", "pr-review-owner--repo-42", p, "session_started",
                serde_json::json!({"type": "SessionStarted", "config": {"pr_number": 42}}),
            ),
            make_event(
                "2025-01-15T11:01:00Z", "pr-review-owner--repo-42", p, "agent_done",
                serde_json::json!({"type": "AgentDone", "role": "Reviewer", "success": true, "duration_secs": 60.0, "tokens_in": 5000, "tokens_out": 2000, "cost_usd": 0.50, "context_pct": 40}),
            ),
            make_event(
                "2025-01-15T11:02:00Z", "pr-review-owner--repo-42", p, "review_findings",
                serde_json::json!({"type": "ReviewFindings", "task_id": "pr-review-owner--repo-42", "high": 2, "medium": 1, "low": 3, "findings_json": "[]"}),
            ),
            make_event(
                "2025-01-15T11:03:00Z", "pr-review-owner--repo-42", p, "session_ended",
                serde_json::json!({"type": "SessionEnded", "total_tasks": 0, "feat_count": 0, "wip_count": 0, "total_cost_usd": 0.50, "duration_secs": 180.0}),
            ),
        ];

        let report = compute_stats(&events, 0, 7, None, false);

        // Build-loop metrics should only reflect the build session
        assert_eq!(report.summary.total_sessions, 1, "PR review session should not inflate total_sessions");
        assert_eq!(report.summary.total_tasks, 1);
        assert_eq!(report.summary.feat_count, 1);
        assert!((report.summary.total_cost_usd - 0.10).abs() < 0.001, "PR review cost should not inflate total_cost");

        // Phase costs should only have Builder from build session, not Reviewer from PR review
        let reviewer_phase = report.phase_costs.iter().find(|p| p.role == "Reviewer");
        assert!(reviewer_phase.is_none(), "PR review Reviewer cost should not appear in phase_costs");

        // Quality metrics should only reflect build-loop review_findings
        assert_eq!(report.quality.tasks_reviewed, 1, "PR review findings should not inflate tasks_reviewed");
        assert_eq!(report.quality.tasks_with_findings, 1);

        // PR review stats should be present and accurate
        let pr = report.pr_reviews.as_ref().expect("pr_reviews should be Some");
        assert_eq!(pr.total_reviews, 1);
        assert_eq!(pr.failed_reviews, 0, "completed review should not be counted as failed");
        assert!((pr.total_cost_usd - 0.50).abs() < 0.001);
        assert_eq!(pr.findings_high, 2);
        assert_eq!(pr.findings_medium, 1);
        assert_eq!(pr.findings_low, 3);
        assert_eq!(pr.reviews.len(), 1);
    }

    #[test]
    fn test_pr_review_no_findings_still_excluded() {
        let p = "/test/project";
        let events = vec![
            make_event(
                "2025-01-15T11:00:00Z", "pr-review-org--repo-7", p, "session_started",
                serde_json::json!({"type": "SessionStarted", "config": {"pr_number": 7}}),
            ),
            make_event(
                "2025-01-15T11:01:00Z", "pr-review-org--repo-7", p, "agent_done",
                serde_json::json!({"type": "AgentDone", "role": "Reviewer", "success": true, "duration_secs": 20.0, "tokens_in": 1000, "tokens_out": 500, "cost_usd": 0.05, "context_pct": 10}),
            ),
            make_event(
                "2025-01-15T11:02:00Z", "pr-review-org--repo-7", p, "session_ended",
                serde_json::json!({"type": "SessionEnded", "total_tasks": 0, "feat_count": 0, "wip_count": 0, "total_cost_usd": 0.05, "duration_secs": 60.0}),
            ),
        ];

        let report = compute_stats(&events, 0, 7, None, false);

        assert_eq!(report.summary.total_sessions, 0, "PR review-only should yield 0 build sessions");
        assert_eq!(report.summary.total_cost_usd, 0.0);
        assert!(report.phase_costs.is_empty());

        let pr = report.pr_reviews.as_ref().expect("pr_reviews should be Some");
        assert_eq!(pr.total_reviews, 0);
        assert_eq!(pr.failed_reviews, 1, "session with no review_findings counts as failed");
        assert!((pr.total_cost_usd - 0.05).abs() < 0.001);
    }

    #[test]
    fn test_pr_review_orphaned_session_not_counted_as_review() {
        // A PR review session starts but the agent crashes before emitting review_findings.
        // total_reviews should be 0, but cost should still be tracked.
        let p = "/test/project";
        let events = vec![
            make_event(
                "2025-01-15T11:00:00Z", "pr-review-owner--repo-99", p, "session_started",
                serde_json::json!({"type": "SessionStarted", "config": {"pr_number": 99}}),
            ),
            make_event(
                "2025-01-15T11:01:00Z", "pr-review-owner--repo-99", p, "agent_done",
                serde_json::json!({"type": "AgentDone", "role": "Reviewer", "success": false, "duration_secs": 45.0, "tokens_in": 3000, "tokens_out": 100, "cost_usd": 0.25, "context_pct": 20}),
            ),
            make_event(
                "2025-01-15T11:02:00Z", "pr-review-owner--repo-99", p, "session_ended",
                serde_json::json!({"type": "SessionEnded", "total_tasks": 0, "feat_count": 0, "wip_count": 0, "total_cost_usd": 0.25, "duration_secs": 120.0}),
            ),
        ];

        let report = compute_stats(&events, 0, 7, None, false);

        let pr = report.pr_reviews.as_ref().expect("pr_reviews should be Some (session existed)");
        assert_eq!(pr.total_reviews, 0, "orphaned session (no review_findings) should not count as a completed review");
        assert_eq!(pr.failed_reviews, 1, "orphaned session should count as failed review");
        assert!((pr.total_cost_usd - 0.25).abs() < 0.001, "cost should still be tracked even for failed reviews");
        assert_eq!(pr.findings_high, 0);
        assert_eq!(pr.findings_medium, 0);
        assert_eq!(pr.findings_low, 0);
        assert!(pr.reviews.is_empty());
    }

    #[test]
    fn test_pr_review_mixed_completed_and_orphaned() {
        // Two PR review sessions: one completes with findings, one crashes.
        // total_reviews should be 1 (only the completed one).
        let p = "/test/project";
        let events = vec![
            // Completed review
            make_event(
                "2025-01-15T11:00:00Z", "pr-review-owner--repo-42", p, "session_started",
                serde_json::json!({"type": "SessionStarted", "config": {"pr_number": 42}}),
            ),
            make_event(
                "2025-01-15T11:01:00Z", "pr-review-owner--repo-42", p, "agent_done",
                serde_json::json!({"type": "AgentDone", "role": "Reviewer", "success": true, "duration_secs": 60.0, "tokens_in": 5000, "tokens_out": 2000, "cost_usd": 0.50, "context_pct": 40}),
            ),
            make_event(
                "2025-01-15T11:02:00Z", "pr-review-owner--repo-42", p, "review_findings",
                serde_json::json!({"type": "ReviewFindings", "task_id": "pr-review-owner--repo-42", "high": 1, "medium": 0, "low": 2, "findings_json": "[]"}),
            ),
            // Orphaned review (crashed, no review_findings)
            make_event(
                "2025-01-15T12:00:00Z", "pr-review-owner--repo-55", p, "session_started",
                serde_json::json!({"type": "SessionStarted", "config": {"pr_number": 55}}),
            ),
            make_event(
                "2025-01-15T12:01:00Z", "pr-review-owner--repo-55", p, "agent_done",
                serde_json::json!({"type": "AgentDone", "role": "Reviewer", "success": false, "duration_secs": 30.0, "tokens_in": 2000, "tokens_out": 50, "cost_usd": 0.15, "context_pct": 10}),
            ),
        ];

        let report = compute_stats(&events, 0, 7, None, false);

        let pr = report.pr_reviews.as_ref().expect("pr_reviews should be Some");
        assert_eq!(pr.total_reviews, 1, "only the completed review should count");
        assert_eq!(pr.failed_reviews, 1, "orphaned session should count as failed review");
        assert!((pr.total_cost_usd - 0.65).abs() < 0.001, "total cost should include both sessions ($0.50 + $0.15)");
        assert_eq!(pr.findings_high, 1);
        assert_eq!(pr.findings_low, 2);
        assert_eq!(pr.reviews.len(), 1);
    }

    #[test]
    fn test_retried_task_dedup_feat_wip_count() {
        // Same task committed twice in one session: first WIP, then feat (retry succeeded).
        // feat_count should be 1, wip_count should be 0 (last commit wins).
        let p = "/test/project";
        let s = "sess-1";
        let events = vec![
            make_event(
                "2025-01-15T10:00:00Z", s, p, "session_started",
                serde_json::json!({"type": "SessionStarted", "config": {}}),
            ),
            make_event(
                "2025-01-15T10:01:00Z", s, p, "task_started",
                serde_json::json!({"type": "TaskStarted", "task_id": "T1", "description": "Build X", "complexity": "medium"}),
            ),
            // First attempt: committed as WIP
            make_event(
                "2025-01-15T10:05:00Z", s, p, "committed",
                serde_json::json!({"type": "Committed", "task_id": "T1", "sha": "aaa111", "commit_type": "WIP"}),
            ),
            // Retry: same task committed as feat
            make_event(
                "2025-01-15T10:10:00Z", s, p, "committed",
                serde_json::json!({"type": "Committed", "task_id": "T1", "sha": "bbb222", "commit_type": "feat"}),
            ),
            make_event(
                "2025-01-15T10:15:00Z", s, p, "session_ended",
                serde_json::json!({"type": "SessionEnded", "total_tasks": 1, "feat_count": 1, "wip_count": 0, "total_cost_usd": 0.10, "duration_secs": 900.0}),
            ),
        ];
        let report = compute_stats(&events, 0, 7, None, false);
        assert_eq!(report.summary.feat_count, 1, "feat_count should be 1 (last commit wins)");
        assert_eq!(report.summary.wip_count, 0, "wip_count should be 0 (WIP overwritten by feat)");
        assert!(report.summary.feat_wip_ratio.is_none(), "no WIP means ratio is None");

        // Verify the fallback trust dashboard also uses deduplicated counts
        if let Some(ref trust) = report.trust {
            // acceptance_rate = feat_count / total_committed = 1/1 = 1.0
            assert_eq!(trust.acceptance_rate, Some(1.0));
            assert_eq!(trust.completed_tasks, 1);
            assert_eq!(trust.feat_tasks, 1);
        }
    }
}
