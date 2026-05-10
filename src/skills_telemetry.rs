use std::collections::HashMap;
use std::path::{Path, PathBuf};

use anyhow::{Context, Result};
use chrono::Utc;
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
    let conn = Connection::open(path).with_context(|| {
        format!(
            "failed to open skills telemetry DB at {}",
            path.display()
        )
    })?;
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
            cited_by_scout    INTEGER NOT NULL DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_skill_telemetry_last_used
            ON skill_telemetry(last_used);
        "#,
    )
    .context("failed to initialize skills telemetry schema")?;
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

    let tx = conn
        .transaction()
        .context("failed to begin telemetry tx")?;

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
}
