use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::time::SystemTime;

use anyhow::{Context, Result};
use chrono::{DateTime, Utc};
use rusqlite::{params, Connection};

use crate::patterns::CommitOutcome;

#[allow(dead_code)]
#[derive(Debug, Clone, Default)]
pub struct TelemetryRecord {
    pub skill_name: String,
    pub citations_pass: u64,
    pub citations_wip: u64,
    pub last_used: Option<String>,
    pub cited_by_stage: HashMap<String, u64>,
}

/// Feedback signal from a builder agent about an injected skill's quality.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum SkillFeedback {
    /// Skill was helpful and correct.
    Confirmed(String),
    /// Skill is outdated for the current codebase.
    Stale(String),
    /// Skill is actively wrong or misleading.
    Wrong(String),
}

pub fn db_path() -> PathBuf {
    let base = if cfg!(target_os = "windows") {
        std::env::var("LOCALAPPDATA")
            .or_else(|_| std::env::var("USERPROFILE"))
            .ok()
            .map(PathBuf::from)
    } else {
        crate::utils::home_dir()
    };
    if let Some(base) = base {
        return base.join(".foundry").join("skills-telemetry.db");
    }
    let fallback = std::env::temp_dir()
        .join(".foundry")
        .join("skills-telemetry.db");
    eprintln!(
        "warning: HOME not set, using {} for skill telemetry",
        fallback.display()
    );
    fallback
}

pub fn open_db(path: &Path) -> Result<Connection> {
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent).with_context(|| {
            format!(
                "failed to create parent dir for skills telemetry at {}",
                parent.display()
            )
        })?;
    }
    let conn = Connection::open(path)
        .with_context(|| format!("failed to open skills telemetry DB at {}", path.display()))?;
    conn.pragma_update(None, "journal_mode", "WAL")
        .context("failed to set journal_mode")?;
    conn.pragma_update(None, "synchronous", "NORMAL")
        .context("failed to set synchronous")?;
    init_schema(&conn)?;
    Ok(conn)
}

fn init_schema(conn: &Connection) -> Result<()> {
    conn.execute_batch(
        r#"
        CREATE TABLE IF NOT EXISTS skill_telemetry (
            skill_name        TEXT PRIMARY KEY,
            citations_pass    INTEGER NOT NULL DEFAULT 0,
            citations_wip     INTEGER NOT NULL DEFAULT 0,
            last_used         TEXT,
            cited_by_planner  INTEGER NOT NULL DEFAULT 0,
            cited_by_reviewer INTEGER NOT NULL DEFAULT 0,
            cited_by_builder  INTEGER NOT NULL DEFAULT 0,
            cited_by_scout    INTEGER NOT NULL DEFAULT 0,
            feedback_confirmed INTEGER NOT NULL DEFAULT 0,
            feedback_stale     INTEGER NOT NULL DEFAULT 0,
            feedback_wrong     INTEGER NOT NULL DEFAULT 0,
            last_feedback      TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_skill_telemetry_last_used
            ON skill_telemetry(last_used);
        "#,
    )
    .context("failed to initialize skills telemetry schema")?;
    ensure_column(
        conn,
        "feedback_confirmed",
        "ALTER TABLE skill_telemetry ADD COLUMN feedback_confirmed INTEGER NOT NULL DEFAULT 0",
    )?;
    ensure_column(
        conn,
        "feedback_stale",
        "ALTER TABLE skill_telemetry ADD COLUMN feedback_stale INTEGER NOT NULL DEFAULT 0",
    )?;
    ensure_column(
        conn,
        "feedback_wrong",
        "ALTER TABLE skill_telemetry ADD COLUMN feedback_wrong INTEGER NOT NULL DEFAULT 0",
    )?;
    ensure_column(
        conn,
        "last_feedback",
        "ALTER TABLE skill_telemetry ADD COLUMN last_feedback TEXT",
    )?;
    Ok(())
}

fn ensure_column(conn: &Connection, column: &str, ddl: &str) -> Result<()> {
    let mut stmt = conn
        .prepare("PRAGMA table_info(skill_telemetry)")
        .context("failed to inspect skill_telemetry schema")?;
    let rows = stmt
        .query_map([], |row| row.get::<_, String>(1))
        .context("failed to query skill_telemetry schema")?;
    for row in rows {
        if row.context("failed to read skill_telemetry column")? == column {
            return Ok(());
        }
    }
    conn.execute(ddl, [])
        .with_context(|| format!("failed to add skill_telemetry.{column}"))?;
    Ok(())
}

pub fn record_citations_batch(
    conn: &mut Connection,
    citations: &[(String, String)],
    outcome: CommitOutcome,
) -> Result<usize> {
    if citations.is_empty() {
        return Ok(0);
    }
    let today = Utc::now().format("%Y-%m-%d").to_string();

    let mut tally: HashMap<String, HashMap<String, u64>> = HashMap::new();
    for (skill_name, role) in citations {
        let role_lc = role.to_lowercase();
        let entry = tally.entry(skill_name.clone()).or_default();
        *entry.entry(role_lc).or_insert(0) += 1;
    }

    let mut names: Vec<String> = tally.keys().cloned().collect();
    names.sort();
    names.dedup();

    let pass_inc: i64 = match outcome {
        CommitOutcome::Pass => 1,
        CommitOutcome::Wip => 0,
    };
    let wip_inc: i64 = match outcome {
        CommitOutcome::Pass => 0,
        CommitOutcome::Wip => 1,
    };

    let tx = conn.transaction().context("failed to begin telemetry tx")?;

    let mut updated = 0usize;
    for skill_name in &names {
        let role_map = tally.get(skill_name).cloned().unwrap_or_default();
        let planner_inc = *role_map.get("planner").unwrap_or(&0) as i64;
        let reviewer_inc = *role_map.get("reviewer").unwrap_or(&0) as i64;
        let builder_inc = *role_map.get("builder").unwrap_or(&0) as i64;
        let scout_inc = *role_map.get("scout").unwrap_or(&0) as i64;

        tx.execute(
            r#"
            INSERT INTO skill_telemetry (
                skill_name, citations_pass, citations_wip, last_used,
                cited_by_planner, cited_by_reviewer, cited_by_builder, cited_by_scout
            ) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)
            ON CONFLICT(skill_name) DO UPDATE SET
                citations_pass    = citations_pass    + excluded.citations_pass,
                citations_wip     = citations_wip     + excluded.citations_wip,
                last_used         = excluded.last_used,
                cited_by_planner  = cited_by_planner  + excluded.cited_by_planner,
                cited_by_reviewer = cited_by_reviewer + excluded.cited_by_reviewer,
                cited_by_builder  = cited_by_builder  + excluded.cited_by_builder,
                cited_by_scout    = cited_by_scout    + excluded.cited_by_scout
            "#,
            params![
                skill_name,
                pass_inc,
                wip_inc,
                today,
                planner_inc,
                reviewer_inc,
                builder_inc,
                scout_inc,
            ],
        )
        .with_context(|| format!("failed to upsert telemetry for {}", skill_name))?;
        updated += 1;
    }

    tx.commit().context("failed to commit telemetry tx")?;
    Ok(updated)
}

/// Parse SKILL_FEEDBACK markers from builder output.
/// Format: `SKILL_FEEDBACK: skill-id | confirmed|stale|wrong | optional reason`
pub fn parse_skill_feedback(text: &str) -> Vec<(String, SkillFeedback)> {
    let mut results = Vec::new();
    for line in text.lines() {
        let trimmed = line.trim();
        if !trimmed.starts_with("SKILL_FEEDBACK:") {
            continue;
        }
        let rest = trimmed.trim_start_matches("SKILL_FEEDBACK:").trim();
        let parts: Vec<&str> = rest.splitn(3, '|').map(|s| s.trim()).collect();
        if parts.len() < 2 || parts[0].is_empty() {
            continue;
        }
        let skill_name = parts[0].to_string();
        let reason = parts.get(2).unwrap_or(&"").to_string();
        let feedback = match parts[1].to_lowercase().as_str() {
            "confirmed" => SkillFeedback::Confirmed(reason),
            "stale" => SkillFeedback::Stale(reason),
            "wrong" => SkillFeedback::Wrong(reason),
            _ => continue,
        };
        results.push((skill_name, feedback));
    }
    results
}

pub fn record_feedback_batch(
    conn: &mut Connection,
    feedback: &[(String, SkillFeedback)],
) -> Result<usize> {
    if feedback.is_empty() {
        return Ok(0);
    }
    let today = Utc::now().format("%Y-%m-%d").to_string();

    let mut tally: HashMap<String, (i64, i64, i64)> = HashMap::new();
    for (skill_name, signal) in feedback {
        let entry = tally.entry(skill_name.clone()).or_insert((0, 0, 0));
        match signal {
            SkillFeedback::Confirmed(_) => entry.0 += 1,
            SkillFeedback::Stale(_) => entry.1 += 1,
            SkillFeedback::Wrong(_) => entry.2 += 1,
        }
    }

    let tx = conn
        .transaction()
        .context("failed to begin skill feedback tx")?;
    let mut updated = 0usize;
    let mut names: Vec<String> = tally.keys().cloned().collect();
    names.sort();
    for skill_name in names {
        let (confirmed, stale, wrong) = tally.get(&skill_name).copied().unwrap_or_default();
        tx.execute(
            r#"
            INSERT INTO skill_telemetry (
                skill_name, feedback_confirmed, feedback_stale, feedback_wrong, last_feedback
            ) VALUES (?1, ?2, ?3, ?4, ?5)
            ON CONFLICT(skill_name) DO UPDATE SET
                feedback_confirmed = feedback_confirmed + excluded.feedback_confirmed,
                feedback_stale     = feedback_stale     + excluded.feedback_stale,
                feedback_wrong     = feedback_wrong     + excluded.feedback_wrong,
                last_feedback      = excluded.last_feedback
            "#,
            params![&skill_name, confirmed, stale, wrong, today],
        )
        .with_context(|| format!("failed to upsert skill feedback for {}", skill_name))?;
        updated += 1;
    }
    tx.commit().context("failed to commit skill feedback tx")?;
    Ok(updated)
}

#[allow(dead_code)]
pub fn load_record(conn: &Connection, skill_name: &str) -> Result<Option<TelemetryRecord>> {
    let mut stmt = conn
        .prepare(
            r#"SELECT skill_name, citations_pass, citations_wip, last_used,
                      cited_by_planner, cited_by_reviewer, cited_by_builder, cited_by_scout
               FROM skill_telemetry WHERE skill_name = ?1"#,
        )
        .context("failed to prepare load_record")?;
    let result = stmt.query_row(params![skill_name], |row| {
        let name: String = row.get(0)?;
        let pass: i64 = row.get(1)?;
        let wip: i64 = row.get(2)?;
        let last_used: Option<String> = row.get(3)?;
        let planner: i64 = row.get(4)?;
        let reviewer: i64 = row.get(5)?;
        let builder: i64 = row.get(6)?;
        let scout: i64 = row.get(7)?;
        let mut by_stage: HashMap<String, u64> = HashMap::new();
        if planner > 0 {
            by_stage.insert("planner".to_string(), planner as u64);
        }
        if reviewer > 0 {
            by_stage.insert("reviewer".to_string(), reviewer as u64);
        }
        if builder > 0 {
            by_stage.insert("builder".to_string(), builder as u64);
        }
        if scout > 0 {
            by_stage.insert("scout".to_string(), scout as u64);
        }
        Ok(TelemetryRecord {
            skill_name: name,
            citations_pass: pass as u64,
            citations_wip: wip as u64,
            last_used,
            cited_by_stage: by_stage,
        })
    });
    match result {
        Ok(rec) => Ok(Some(rec)),
        Err(rusqlite::Error::QueryReturnedNoRows) => Ok(None),
        Err(e) => Err(e).context("failed to query telemetry record"),
    }
}

#[derive(Debug, Clone, Default)]
pub struct PopularityRecord {
    pub citations_pass: u64,
    pub citations_wip: u64,
    pub last_used: Option<String>,
    pub feedback_confirmed: u64,
    pub feedback_stale: u64,
    pub feedback_wrong: u64,
}

pub fn load_popularity_scores(conn: &Connection) -> Result<HashMap<String, PopularityRecord>> {
    let mut stmt = conn
        .prepare(
            r#"SELECT skill_name, citations_pass, citations_wip, last_used,
                      feedback_confirmed, feedback_stale, feedback_wrong
               FROM skill_telemetry"#,
        )
        .context("failed to prepare load_popularity_scores")?;
    let rows = stmt
        .query_map([], |row| {
            let name: String = row.get(0)?;
            let pass: i64 = row.get(1)?;
            let wip: i64 = row.get(2)?;
            let last_used: Option<String> = row.get(3)?;
            let confirmed: i64 = row.get(4)?;
            let stale: i64 = row.get(5)?;
            let wrong: i64 = row.get(6)?;
            Ok((
                name,
                PopularityRecord {
                    citations_pass: pass as u64,
                    citations_wip: wip as u64,
                    last_used,
                    feedback_confirmed: confirmed as u64,
                    feedback_stale: stale as u64,
                    feedback_wrong: wrong as u64,
                },
            ))
        })
        .context("failed to query popularity rows")?;
    let mut out: HashMap<String, PopularityRecord> = HashMap::new();
    for row in rows {
        let (name, rec) = row.context("failed to read popularity row")?;
        out.insert(name, rec);
    }
    Ok(out)
}

pub fn top_cited_skills(conn: &Connection, limit: usize) -> Result<Vec<TelemetryRecord>> {
    let mut stmt = conn
        .prepare(
            r#"SELECT skill_name, citations_pass, citations_wip, last_used,
                      cited_by_planner, cited_by_reviewer, cited_by_builder, cited_by_scout
               FROM skill_telemetry
               ORDER BY citations_pass DESC, last_used DESC
               LIMIT ?1"#,
        )
        .context("failed to prepare top_cited_skills")?;
    let rows = stmt
        .query_map(params![limit as i64], |row| {
            let name: String = row.get(0)?;
            let pass: i64 = row.get(1)?;
            let wip: i64 = row.get(2)?;
            let last_used: Option<String> = row.get(3)?;
            let planner: i64 = row.get(4)?;
            let reviewer: i64 = row.get(5)?;
            let builder: i64 = row.get(6)?;
            let scout: i64 = row.get(7)?;
            let mut by_stage: HashMap<String, u64> = HashMap::new();
            if planner > 0 {
                by_stage.insert("planner".to_string(), planner as u64);
            }
            if reviewer > 0 {
                by_stage.insert("reviewer".to_string(), reviewer as u64);
            }
            if builder > 0 {
                by_stage.insert("builder".to_string(), builder as u64);
            }
            if scout > 0 {
                by_stage.insert("scout".to_string(), scout as u64);
            }
            Ok(TelemetryRecord {
                skill_name: name,
                citations_pass: pass as u64,
                citations_wip: wip as u64,
                last_used,
                cited_by_stage: by_stage,
            })
        })
        .context("failed to query top_cited_skills rows")?;
    let mut out: Vec<TelemetryRecord> = Vec::new();
    for row in rows {
        let rec = row.context("failed to read top_cited_skills row")?;
        out.push(rec);
    }
    Ok(out)
}

pub fn recent_citations(conn: &Connection, since: DateTime<Utc>) -> Result<Vec<TelemetryRecord>> {
    let since_date = since.format("%Y-%m-%d").to_string();
    let mut stmt = conn
        .prepare(
            r#"SELECT skill_name, citations_pass, citations_wip, last_used,
                      cited_by_planner, cited_by_reviewer, cited_by_builder, cited_by_scout
               FROM skill_telemetry
               WHERE last_used >= ?1
               ORDER BY citations_pass DESC, last_used DESC"#,
        )
        .context("failed to prepare recent_citations")?;
    let rows = stmt
        .query_map(params![since_date], |row| {
            let name: String = row.get(0)?;
            let pass: i64 = row.get(1)?;
            let wip: i64 = row.get(2)?;
            let last_used: Option<String> = row.get(3)?;
            let planner: i64 = row.get(4)?;
            let reviewer: i64 = row.get(5)?;
            let builder: i64 = row.get(6)?;
            let scout: i64 = row.get(7)?;
            let mut by_stage: HashMap<String, u64> = HashMap::new();
            if planner > 0 {
                by_stage.insert("planner".to_string(), planner as u64);
            }
            if reviewer > 0 {
                by_stage.insert("reviewer".to_string(), reviewer as u64);
            }
            if builder > 0 {
                by_stage.insert("builder".to_string(), builder as u64);
            }
            if scout > 0 {
                by_stage.insert("scout".to_string(), scout as u64);
            }
            Ok(TelemetryRecord {
                skill_name: name,
                citations_pass: pass as u64,
                citations_wip: wip as u64,
                last_used,
                cited_by_stage: by_stage,
            })
        })
        .context("failed to query recent_citations rows")?;
    let mut out: Vec<TelemetryRecord> = Vec::new();
    for row in rows {
        let rec = row.context("failed to read recent_citations row")?;
        out.push(rec);
    }
    Ok(out)
}

// T1.36: exercised only from the test below. Kept on the public surface so
// future TUI/telemetry consumers can adopt it without re-implementation;
// allow(dead_code) is the lowest-risk option (deleting would lose the query).
#[allow(dead_code)]
pub fn session_citation_count(conn: &Connection, since: SystemTime) -> Result<usize> {
    let dt: DateTime<Utc> = since.into();
    let since_date = dt.format("%Y-%m-%d").to_string();
    let mut stmt = conn
        .prepare("SELECT COUNT(*) FROM skill_telemetry WHERE last_used >= ?1")
        .context("failed to prepare session_citation_count")?;
    let count: i64 = stmt
        .query_row(params![since_date], |row| row.get::<_, i64>(0))
        .context("failed to query session_citation_count")?;
    Ok(count as usize)
}

pub fn load_popularity_scores_or_default() -> HashMap<String, PopularityRecord> {
    let path = db_path();
    let conn = match open_db(&path) {
        Ok(c) => c,
        Err(_) => return HashMap::new(),
    };
    load_popularity_scores(&conn).unwrap_or_default()
}

#[allow(dead_code)]
pub fn load_all(conn: &Connection) -> Result<HashMap<String, TelemetryRecord>> {
    let mut stmt = conn
        .prepare(
            r#"SELECT skill_name, citations_pass, citations_wip, last_used,
                      cited_by_planner, cited_by_reviewer, cited_by_builder, cited_by_scout
               FROM skill_telemetry"#,
        )
        .context("failed to prepare load_all")?;
    let rows = stmt
        .query_map([], |row| {
            let name: String = row.get(0)?;
            let pass: i64 = row.get(1)?;
            let wip: i64 = row.get(2)?;
            let last_used: Option<String> = row.get(3)?;
            let planner: i64 = row.get(4)?;
            let reviewer: i64 = row.get(5)?;
            let builder: i64 = row.get(6)?;
            let scout: i64 = row.get(7)?;
            let mut by_stage: HashMap<String, u64> = HashMap::new();
            if planner > 0 {
                by_stage.insert("planner".to_string(), planner as u64);
            }
            if reviewer > 0 {
                by_stage.insert("reviewer".to_string(), reviewer as u64);
            }
            if builder > 0 {
                by_stage.insert("builder".to_string(), builder as u64);
            }
            if scout > 0 {
                by_stage.insert("scout".to_string(), scout as u64);
            }
            Ok(TelemetryRecord {
                skill_name: name,
                citations_pass: pass as u64,
                citations_wip: wip as u64,
                last_used,
                cited_by_stage: by_stage,
            })
        })
        .context("failed to query telemetry rows")?;
    let mut out: HashMap<String, TelemetryRecord> = HashMap::new();
    for row in rows {
        let rec = row.context("failed to read telemetry row")?;
        out.insert(rec.skill_name.clone(), rec);
    }
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn temp_db_path() -> (tempfile::TempDir, PathBuf) {
        let tmp = tempfile::tempdir().expect("tempdir");
        let path = tmp.path().join("telemetry.db");
        (tmp, path)
    }

    #[test]
    fn open_db_creates_schema_and_is_idempotent() {
        let (_tmp, path) = temp_db_path();
        {
            let _conn = open_db(&path).expect("first open");
        }
        let _conn2 = open_db(&path).expect("second open");
    }

    #[test]
    fn record_citations_batch_pass_increments_pass_only() {
        let (_tmp, path) = temp_db_path();
        let mut conn = open_db(&path).unwrap();
        record_citations_batch(
            &mut conn,
            &[("alpha".to_string(), "Planner".to_string())],
            CommitOutcome::Pass,
        )
        .unwrap();
        let rec = load_record(&conn, "alpha").unwrap().unwrap();
        assert_eq!(rec.citations_pass, 1);
        assert_eq!(rec.citations_wip, 0);
        assert!(rec.last_used.is_some());
        assert_eq!(rec.cited_by_stage.get("planner"), Some(&1));
    }

    #[test]
    fn record_citations_batch_wip_increments_wip_only() {
        let (_tmp, path) = temp_db_path();
        let mut conn = open_db(&path).unwrap();
        record_citations_batch(
            &mut conn,
            &[("beta".to_string(), "Reviewer".to_string())],
            CommitOutcome::Wip,
        )
        .unwrap();
        let rec = load_record(&conn, "beta").unwrap().unwrap();
        assert_eq!(rec.citations_pass, 0);
        assert_eq!(rec.citations_wip, 1);
        assert_eq!(rec.cited_by_stage.get("reviewer"), Some(&1));
    }

    #[test]
    fn record_citations_batch_dedupes_pass_count_across_roles() {
        let (_tmp, path) = temp_db_path();
        let mut conn = open_db(&path).unwrap();
        record_citations_batch(
            &mut conn,
            &[
                ("alpha".to_string(), "Planner".to_string()),
                ("alpha".to_string(), "Reviewer".to_string()),
            ],
            CommitOutcome::Pass,
        )
        .unwrap();
        let rec = load_record(&conn, "alpha").unwrap().unwrap();
        assert_eq!(rec.citations_pass, 1);
        assert_eq!(rec.cited_by_stage.get("planner"), Some(&1));
        assert_eq!(rec.cited_by_stage.get("reviewer"), Some(&1));
    }

    #[test]
    fn parse_skill_feedback_accepts_supported_signals() {
        let text = "noise\nSKILL_FEEDBACK: rust-async | confirmed | helped\nSKILL_FEEDBACK: old-api | stale | docs moved\nSKILL_FEEDBACK: bad-advice | wrong | broke build\n";
        let feedback = parse_skill_feedback(text);
        assert_eq!(feedback.len(), 3);
        assert_eq!(feedback[0].0, "rust-async");
        assert!(matches!(feedback[0].1, SkillFeedback::Confirmed(_)));
        assert!(matches!(feedback[1].1, SkillFeedback::Stale(_)));
        assert!(matches!(feedback[2].1, SkillFeedback::Wrong(_)));
    }

    #[test]
    fn record_feedback_batch_updates_popularity_penalty_fields() {
        let (_tmp, path) = temp_db_path();
        let mut conn = open_db(&path).unwrap();
        record_feedback_batch(
            &mut conn,
            &[
                (
                    "alpha".to_string(),
                    SkillFeedback::Confirmed("useful".to_string()),
                ),
                ("alpha".to_string(), SkillFeedback::Wrong("bad".to_string())),
                ("beta".to_string(), SkillFeedback::Stale("old".to_string())),
            ],
        )
        .unwrap();

        let scores = load_popularity_scores(&conn).unwrap();
        let alpha = scores.get("alpha").unwrap();
        assert_eq!(alpha.feedback_confirmed, 1);
        assert_eq!(alpha.feedback_wrong, 1);
        assert_eq!(alpha.feedback_stale, 0);
        let beta = scores.get("beta").unwrap();
        assert_eq!(beta.feedback_stale, 1);
    }

    #[test]
    fn load_all_returns_every_row() {
        let (_tmp, path) = temp_db_path();
        let mut conn = open_db(&path).unwrap();
        record_citations_batch(
            &mut conn,
            &[("alpha".to_string(), "Planner".to_string())],
            CommitOutcome::Pass,
        )
        .unwrap();
        record_citations_batch(
            &mut conn,
            &[("beta".to_string(), "Reviewer".to_string())],
            CommitOutcome::Pass,
        )
        .unwrap();
        let all = load_all(&conn).unwrap();
        assert_eq!(all.len(), 2);
    }

    #[test]
    fn top_cited_skills_orders_by_pass_then_last_used() {
        let (_tmp, path) = temp_db_path();
        let mut conn = open_db(&path).unwrap();
        // alpha: 3 passes
        for _ in 0..3 {
            record_citations_batch(
                &mut conn,
                &[("alpha".to_string(), "Planner".to_string())],
                CommitOutcome::Pass,
            )
            .unwrap();
        }
        // beta: 1 pass
        record_citations_batch(
            &mut conn,
            &[("beta".to_string(), "Planner".to_string())],
            CommitOutcome::Pass,
        )
        .unwrap();
        // gamma: 2 passes
        for _ in 0..2 {
            record_citations_batch(
                &mut conn,
                &[("gamma".to_string(), "Planner".to_string())],
                CommitOutcome::Pass,
            )
            .unwrap();
        }
        let top = top_cited_skills(&conn, 10).unwrap();
        assert_eq!(top.len(), 3);
        assert_eq!(top[0].skill_name, "alpha");
        assert_eq!(top[0].citations_pass, 3);
        assert_eq!(top[1].skill_name, "gamma");
        assert_eq!(top[1].citations_pass, 2);
        assert_eq!(top[2].skill_name, "beta");
        assert_eq!(top[2].citations_pass, 1);
    }

    #[test]
    fn recent_citations_filters_by_date() {
        let (_tmp, path) = temp_db_path();
        let mut conn = open_db(&path).unwrap();
        record_citations_batch(
            &mut conn,
            &[("alpha".to_string(), "Planner".to_string())],
            CommitOutcome::Pass,
        )
        .unwrap();
        let one_day_ago = Utc::now() - chrono::Duration::days(1);
        let one_day_ahead = Utc::now() + chrono::Duration::days(1);
        let recent = recent_citations(&conn, one_day_ago).unwrap();
        assert_eq!(recent.len(), 1);
        let future = recent_citations(&conn, one_day_ahead).unwrap();
        assert_eq!(future.len(), 0);
    }

    #[test]
    fn session_citation_count_returns_recent_total() {
        let (_tmp, path) = temp_db_path();
        let mut conn = open_db(&path).unwrap();
        record_citations_batch(
            &mut conn,
            &[("alpha".to_string(), "Planner".to_string())],
            CommitOutcome::Pass,
        )
        .unwrap();
        record_citations_batch(
            &mut conn,
            &[("beta".to_string(), "Reviewer".to_string())],
            CommitOutcome::Pass,
        )
        .unwrap();
        let since = SystemTime::now() - std::time::Duration::from_secs(60 * 60);
        let count = session_citation_count(&conn, since).unwrap();
        assert_eq!(count, 2);
    }
}
