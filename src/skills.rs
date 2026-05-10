use std::collections::BTreeSet;
use std::path::{Path, PathBuf};

use anyhow::{Context, Result};

use crate::patterns::{Pattern, PatternSolution};
use crate::utils::atomic_write_file;

/// A single SKILL.md file on disk parsed back into a Pattern shape so the
/// existing matcher can consume it without further changes.
#[derive(Debug, Clone)]
pub struct SkillFile {
    pub dir_name: String,
    pub frontmatter: SkillFrontmatter,
    pub body: String,
}

#[derive(Debug, Clone, Default)]
pub struct SkillFrontmatter {
    pub name: String,
    pub description: String,
    /// "planner" | "reviewer" | "both". Migration only ever writes "planner"
    /// or "reviewer"; "both" is reserved for hand-curated skills.
    pub cf_stage: String,
    pub cf_citations_pass: usize,
    pub cf_citations_wip: usize,
    pub cf_last_used: Option<String>,
    pub cf_frequency: usize,
    pub cf_severity: Option<String>,
    pub cf_keywords: Vec<String>,
}

/// Expand `~/` prefix using $HOME (or USERPROFILE/LOCALAPPDATA on Windows).
/// Falls back to platform temp dir + .foundry/skills if HOME is unset.
pub fn resolve_skills_dir(config_str: &str) -> PathBuf {
    if let Some(rest) = config_str.strip_prefix("~/") {
        let base = if cfg!(target_os = "windows") {
            std::env::var("LOCALAPPDATA")
                .or_else(|_| std::env::var("USERPROFILE"))
                .ok()
                .map(PathBuf::from)
        } else {
            crate::utils::home_dir()
        };
        if let Some(base) = base {
            return base.join(rest);
        }
        let fallback = std::env::temp_dir().join(".foundry").join("skills");
        eprintln!(
            "warning: HOME not set, using {} for skill storage",
            fallback.display()
        );
        return fallback;
    }
    PathBuf::from(config_str)
}

/// Walk `<dir>/*/SKILL.md` and parse each into a `SkillFile`.
pub fn load_skills(dir: &Path) -> Vec<SkillFile> {
    let mut out = Vec::new();
    let entries = match std::fs::read_dir(dir) {
        Ok(e) => e,
        Err(_) => return out,
    };
    for entry in entries.flatten() {
        let path = entry.path();
        if !path.is_dir() {
            continue;
        }
        let skill_md = path.join("SKILL.md");
        if !skill_md.exists() {
            continue;
        }
        let content = match std::fs::read_to_string(&skill_md) {
            Ok(s) => s,
            Err(_) => continue,
        };
        let dir_name = path
            .file_name()
            .and_then(|n| n.to_str())
            .unwrap_or("")
            .to_string();
        match parse_skill_file(&dir_name, &content) {
            Ok(sf) => out.push(sf),
            Err(e) => eprintln!(
                "warning: failed to parse skill at {}: {}",
                skill_md.display(),
                e
            ),
        }
    }
    out
}

pub fn load_skills_from_global() -> Vec<SkillFile> {
    let dir = resolve_skills_dir("~/.foundry/skills");
    load_skills(&dir)
}

/// Drop-in shape for the matcher. Each `SkillFile` becomes one `Pattern`.
pub fn load_skills_as_patterns_from_global() -> Vec<Pattern> {
    load_skills_from_global()
        .into_iter()
        .map(skill_to_pattern)
        .collect()
}

/// Re-hydrate a `Pattern` from a parsed `SkillFile` so the existing matcher
/// (`patterns::keyword_scores`, etc.) can score skill-backed entries.
pub fn skill_to_pattern(s: SkillFile) -> Pattern {
    let stage = s.frontmatter.cf_stage.to_lowercase();
    let (planner, reviewer) = match stage.as_str() {
        "planner" => (s.body.clone(), String::new()),
        "reviewer" => (String::new(), s.body.clone()),
        "both" => (s.body.clone(), s.body.clone()),
        _ => (s.body.clone(), s.body.clone()),
    };

    let pattern_id = if !s.dir_name.is_empty() {
        s.dir_name.clone()
    } else {
        s.frontmatter.name.clone()
    };

    Pattern {
        pattern_id,
        title: s.frontmatter.description.clone(),
        first_seen: String::new(),
        last_seen: String::new(),
        frequency: s.frontmatter.cf_frequency,
        severity: s.frontmatter.cf_severity.clone(),
        keywords: s.frontmatter.cf_keywords.clone(),
        tech_stack: Vec::new(),
        issue: extract_issue_from_body(&s.body),
        solution: Some(PatternSolution { planner, reviewer }),
        auto_apply: false,
        learned_from: None,
        used_count: s.frontmatter.cf_citations_pass + s.frontmatter.cf_citations_wip,
        promoted_to: String::new(),
        promoted_at: String::new(),
        last_used_at: s.frontmatter.cf_last_used.as_deref().map(iso_to_date_only),
        cited_in_pass: s.frontmatter.cf_citations_pass,
        cited_in_wip: s.frontmatter.cf_citations_wip,
        cited_by_stage: std::collections::HashMap::new(),
    }
}

fn extract_issue_from_body(body: &str) -> Option<String> {
    let marker = body.find("## Issue")?;
    let after_marker = &body[marker..];
    let mut lines = after_marker.lines();
    lines.next();
    let mut captured = String::new();
    for line in lines {
        if line.starts_with("## ") {
            break;
        }
        captured.push_str(line);
        captured.push('\n');
    }
    let trimmed = captured.trim();
    if trimmed.is_empty() || trimmed == "(no issue recorded)" {
        return None;
    }
    Some(trimmed.to_string())
}

fn iso_to_date_only(iso: &str) -> String {
    iso.split('T').next().unwrap_or(iso).to_string()
}

/// Parse a SKILL.md string into a `SkillFile`.
pub fn parse_skill_file(dir_name: &str, content: &str) -> Result<SkillFile> {
    let content = content.replace("\r\n", "\n");
    let trimmed = content.trim_start_matches('\u{feff}');

    let mut idx = 0usize;
    let bytes = trimmed.as_bytes();
    while idx < bytes.len() && (bytes[idx] == b'\n' || bytes[idx] == b' ' || bytes[idx] == b'\t') {
        idx += 1;
    }
    let starting = &trimmed[idx..];

    if !starting.starts_with("---\n") && starting != "---" && !starting.starts_with("---\r") {
        anyhow::bail!("missing opening --- delimiter");
    }

    let after_open = if let Some(rest) = starting.strip_prefix("---\n") {
        rest
    } else {
        anyhow::bail!("missing opening --- delimiter");
    };

    let mut yaml_block = String::new();
    let mut body = String::new();
    let mut found_close = false;
    let mut lines_iter = after_open.split('\n');
    while let Some(line) = lines_iter.next() {
        if line == "---" {
            found_close = true;
            let remaining: Vec<&str> = lines_iter.collect();
            body = remaining.join("\n");
            break;
        }
        yaml_block.push_str(line);
        yaml_block.push('\n');
    }

    if !found_close {
        anyhow::bail!("missing closing --- delimiter");
    }

    let body = body.strip_prefix('\n').map(String::from).unwrap_or(body);

    let frontmatter = parse_frontmatter(&yaml_block)?;
    Ok(SkillFile {
        dir_name: dir_name.to_string(),
        frontmatter,
        body,
    })
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
enum Section {
    Top,
    Metadata,
    Keywords,
}

fn parse_frontmatter(yaml_block: &str) -> Result<SkillFrontmatter> {
    let mut fm = SkillFrontmatter::default();
    let mut section = Section::Top;

    let lines: Vec<&str> = yaml_block.lines().collect();
    let mut i = 0usize;
    while i < lines.len() {
        let line = lines[i];
        let trimmed = line.trim();
        if trimmed.is_empty() || trimmed.starts_with('#') {
            i += 1;
            continue;
        }
        let indent = line.len() - line.trim_start().len();

        match section {
            Section::Top => {
                if trimmed == "metadata:" {
                    section = Section::Metadata;
                    i += 1;
                    continue;
                }
                if let Some(rest) = trimmed.strip_prefix("name:") {
                    fm.name = parse_scalar(rest);
                } else if let Some(rest) = trimmed.strip_prefix("description:") {
                    fm.description = parse_scalar(rest);
                }
                i += 1;
            }
            Section::Metadata => {
                if indent < 2 {
                    section = Section::Top;
                    continue;
                }
                let colon_idx = match trimmed.find(':') {
                    Some(c) => c,
                    None => {
                        i += 1;
                        continue;
                    }
                };
                let key = &trimmed[..colon_idx];
                let value_part = &trimmed[colon_idx + 1..];

                match key {
                    "cf-keywords" => {
                        section = Section::Keywords;
                        i += 1;
                        continue;
                    }
                    "cf-stage" => {
                        fm.cf_stage = parse_scalar(value_part);
                    }
                    "cf-last-used" => {
                        let v = parse_scalar(value_part);
                        if !v.is_empty() {
                            fm.cf_last_used = Some(v);
                        }
                    }
                    "cf-severity" => {
                        let v = parse_scalar(value_part);
                        if !v.is_empty() {
                            fm.cf_severity = Some(v);
                        }
                    }
                    "cf-citations-pass" => {
                        fm.cf_citations_pass = value_part.trim().parse::<usize>().with_context(
                            || format!("integer field {} not parseable: {}", key, value_part),
                        )?;
                    }
                    "cf-citations-wip" => {
                        fm.cf_citations_wip = value_part.trim().parse::<usize>().with_context(
                            || format!("integer field {} not parseable: {}", key, value_part),
                        )?;
                    }
                    "cf-frequency" => {
                        fm.cf_frequency = value_part.trim().parse::<usize>().with_context(
                            || format!("integer field {} not parseable: {}", key, value_part),
                        )?;
                    }
                    _ => {}
                }
                i += 1;
            }
            Section::Keywords => {
                if indent < 2 {
                    section = Section::Top;
                    continue;
                }
                if let Some(rest) = trimmed.strip_prefix("- ") {
                    fm.cf_keywords.push(parse_scalar(rest));
                    i += 1;
                } else {
                    section = Section::Metadata;
                }
            }
        }
    }

    Ok(fm)
}

fn parse_scalar(raw: &str) -> String {
    let v = raw.trim();
    if v.starts_with('"') && v.ends_with('"') && v.len() >= 2 {
        return v[1..v.len() - 1].replace("\\\"", "\"");
    }
    v.to_string()
}

/// Convert a `Pattern` to one or two `(dir_name, full_skill_md_text)` pairs
/// ready for the migration command to write under `<skills_dir>/<dir_name>/SKILL.md`.
/// Returns `Vec::new()` when both solution stages are empty.
pub fn pattern_to_skill_files(p: &Pattern) -> Vec<(String, String)> {
    let solution = match &p.solution {
        Some(s) => s,
        None => return Vec::new(),
    };
    let planner = solution.planner.trim().to_string();
    let reviewer = solution.reviewer.trim().to_string();
    if planner.is_empty() && reviewer.is_empty() {
        return Vec::new();
    }

    let keywords = dedupe_keywords(&p.keywords, &p.tech_stack);
    let cf_last_used = p.last_used_at.as_deref().map(date_to_iso);

    let make_fm = |stage: &str| SkillFrontmatter {
        name: p.pattern_id.clone(),
        description: p.title.clone(),
        cf_stage: stage.to_string(),
        cf_citations_pass: p.cited_in_pass,
        cf_citations_wip: p.cited_in_wip,
        cf_last_used: cf_last_used.clone(),
        cf_frequency: p.frequency,
        cf_severity: p.severity.clone(),
        cf_keywords: keywords.clone(),
    };

    if planner.is_empty() {
        let body = render_body(&p.issue, &reviewer);
        let fm = make_fm("reviewer");
        return vec![(p.pattern_id.clone(), render_skill(&fm, &body))];
    }
    if reviewer.is_empty() {
        let body = render_body(&p.issue, &planner);
        let fm = make_fm("planner");
        return vec![(p.pattern_id.clone(), render_skill(&fm, &body))];
    }
    let mut fm_planner = make_fm("planner");
    fm_planner.name = format!("{}-planner", p.pattern_id);
    let mut fm_reviewer = make_fm("reviewer");
    fm_reviewer.name = format!("{}-reviewer", p.pattern_id);
    vec![
        (
            format!("{}-planner", p.pattern_id),
            render_skill(&fm_planner, &render_body(&p.issue, &planner)),
        ),
        (
            format!("{}-reviewer", p.pattern_id),
            render_skill(&fm_reviewer, &render_body(&p.issue, &reviewer)),
        ),
    ]
}

fn dedupe_keywords(keywords: &[String], tech_stack: &[String]) -> Vec<String> {
    let mut seen: BTreeSet<String> = BTreeSet::new();
    let mut out: Vec<String> = Vec::new();
    for kw in keywords.iter().chain(tech_stack.iter()) {
        if seen.insert(kw.clone()) {
            out.push(kw.clone());
        }
    }
    out
}

fn date_to_iso(d: &str) -> String {
    let parts: Vec<&str> = d.split('-').collect();
    if parts.len() == 3
        && parts[0].len() == 4
        && parts[0].chars().all(|c| c.is_ascii_digit())
        && parts[1].len() == 2
        && parts[1].chars().all(|c| c.is_ascii_digit())
        && parts[2].len() == 2
        && parts[2].chars().all(|c| c.is_ascii_digit())
    {
        return format!("{}T00:00:00Z", d);
    }
    d.to_string()
}

fn render_body(issue: &Option<String>, solution: &str) -> String {
    format!(
        "## Issue\n\n{}\n\n## Solution\n\n{}\n",
        issue.as_deref().unwrap_or("(no issue recorded)").trim(),
        crate::utils::truncate_str(solution, 16000)
    )
}

fn render_skill(fm: &SkillFrontmatter, body: &str) -> String {
    let mut s = String::from("---\n");
    s.push_str(&format!("name: {}\n", escape_scalar(&fm.name)));
    s.push_str(&format!(
        "description: {}\n",
        escape_scalar(&fm.description)
    ));
    s.push_str("metadata:\n");
    s.push_str(&format!("  cf-stage: {}\n", fm.cf_stage));
    s.push_str(&format!("  cf-citations-pass: {}\n", fm.cf_citations_pass));
    s.push_str(&format!("  cf-citations-wip: {}\n", fm.cf_citations_wip));
    if let Some(d) = &fm.cf_last_used {
        s.push_str(&format!("  cf-last-used: {}\n", d));
    }
    s.push_str(&format!("  cf-frequency: {}\n", fm.cf_frequency));
    if let Some(sev) = &fm.cf_severity {
        s.push_str(&format!("  cf-severity: {}\n", sev));
    }
    s.push_str("  cf-keywords:\n");
    for kw in &fm.cf_keywords {
        s.push_str(&format!("    - {}\n", escape_scalar(kw)));
    }
    s.push_str("---\n\n");
    s.push_str(body);
    s
}

fn escape_scalar(v: &str) -> String {
    let one_line: String = v.replace('\n', " ").replace('\r', " ");
    let needs_quote = one_line.is_empty()
        || one_line.starts_with(' ')
        || one_line.ends_with(' ')
        || one_line.starts_with('-')
        || one_line.starts_with('#')
        || one_line.contains(':')
        || one_line.contains('"')
        || one_line.contains('\'');
    if !needs_quote {
        return one_line;
    }
    format!("\"{}\"", one_line.replace('"', "\\\""))
}

/// Write a single skill to `<skills_dir>/<dir_name>/SKILL.md`.
#[allow(dead_code)]
pub fn write_skill(skills_dir: &Path, dir_name: &str, contents: &str) -> Result<()> {
    let dir = skills_dir.join(dir_name);
    std::fs::create_dir_all(&dir)
        .with_context(|| format!("failed to create {}", dir.display()))?;
    let target = dir.join("SKILL.md");
    atomic_write_file(&target, contents.as_bytes())
        .with_context(|| format!("failed to write {}", target.display()))?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;

    fn sample_pattern(planner: &str, reviewer: &str) -> Pattern {
        Pattern {
            pattern_id: "sample-pid".to_string(),
            title: "Sample title".to_string(),
            first_seen: String::new(),
            last_seen: String::new(),
            frequency: 2,
            severity: Some("HIGH".to_string()),
            keywords: vec!["alpha".to_string(), "beta".to_string()],
            tech_stack: vec!["rust".to_string()],
            issue: Some("Things break".to_string()),
            solution: Some(PatternSolution {
                planner: planner.to_string(),
                reviewer: reviewer.to_string(),
            }),
            auto_apply: false,
            learned_from: None,
            used_count: 0,
            promoted_to: String::new(),
            promoted_at: String::new(),
            last_used_at: Some("2026-04-09".to_string()),
            cited_in_pass: 1,
            cited_in_wip: 0,
            cited_by_stage: HashMap::new(),
        }
    }

    #[test]
    fn parse_then_render_round_trips_minimal_skill() {
        let fm = SkillFrontmatter {
            name: "test-skill".to_string(),
            description: "Some skill".to_string(),
            cf_stage: "planner".to_string(),
            cf_citations_pass: 3,
            cf_citations_wip: 1,
            cf_last_used: Some("2026-04-09T00:00:00Z".to_string()),
            cf_frequency: 4,
            cf_severity: Some("HIGH".to_string()),
            cf_keywords: vec!["a".to_string(), "b".to_string()],
        };
        let body = "## Issue\n\nSomething\n\n## Solution\n\nDo X\n";
        let rendered = render_skill(&fm, body);
        let parsed = parse_skill_file("test-skill", &rendered).expect("parse");
        assert_eq!(parsed.frontmatter.name, "test-skill");
        assert_eq!(parsed.frontmatter.description, "Some skill");
        assert_eq!(parsed.frontmatter.cf_stage, "planner");
        assert_eq!(parsed.frontmatter.cf_citations_pass, 3);
        assert_eq!(parsed.frontmatter.cf_citations_wip, 1);
        assert_eq!(
            parsed.frontmatter.cf_last_used.as_deref(),
            Some("2026-04-09T00:00:00Z")
        );
        assert_eq!(parsed.frontmatter.cf_frequency, 4);
        assert_eq!(parsed.frontmatter.cf_severity.as_deref(), Some("HIGH"));
        assert_eq!(
            parsed.frontmatter.cf_keywords,
            vec!["a".to_string(), "b".to_string()]
        );
        assert_eq!(parsed.body, body);
    }

    #[test]
    fn parse_skill_file_handles_crlf() {
        let raw = "---\r\nname: x\r\ndescription: d\r\nmetadata:\r\n  cf-stage: planner\r\n  cf-citations-pass: 0\r\n  cf-citations-wip: 0\r\n  cf-frequency: 1\r\n  cf-keywords:\r\n    - foo\r\n---\r\n\r\n## Issue\r\n\r\nBody\r\n";
        let parsed = parse_skill_file("x", raw).expect("parse crlf");
        assert_eq!(parsed.frontmatter.name, "x");
        assert_eq!(parsed.frontmatter.cf_stage, "planner");
        assert_eq!(parsed.frontmatter.cf_keywords, vec!["foo".to_string()]);
    }

    #[test]
    fn pattern_to_skill_files_planner_only_emits_one_file() {
        let p = sample_pattern("do X", "");
        let out = pattern_to_skill_files(&p);
        assert_eq!(out.len(), 1);
        let (dir_name, contents) = &out[0];
        assert_eq!(dir_name, "sample-pid");
        assert!(contents.contains("cf-stage: planner"));
        assert!(contents.contains("do X"));
        assert!(contents.contains("## Issue"));
    }

    #[test]
    fn pattern_to_skill_files_both_stages_emits_two_files() {
        let p = sample_pattern("planner advice", "reviewer advice");
        let out = pattern_to_skill_files(&p);
        assert_eq!(out.len(), 2);
        assert_eq!(out[0].0, "sample-pid-planner");
        assert_eq!(out[1].0, "sample-pid-reviewer");
        assert!(out[0].1.contains("cf-stage: planner"));
        assert!(out[1].1.contains("cf-stage: reviewer"));
        assert!(out[0].1.contains("planner advice"));
        assert!(out[1].1.contains("reviewer advice"));
    }

    #[test]
    fn pattern_to_skill_files_no_solution_emits_zero_files() {
        let mut p = sample_pattern("x", "y");
        p.solution = None;
        assert!(pattern_to_skill_files(&p).is_empty());
    }

    #[test]
    fn pattern_to_skill_files_keywords_dedupe_preserves_order() {
        let mut p = sample_pattern("plan", "");
        p.keywords = vec!["a".to_string(), "b".to_string(), "rust".to_string()];
        p.tech_stack = vec!["rust".to_string(), "c".to_string()];
        let out = pattern_to_skill_files(&p);
        assert_eq!(out.len(), 1);
        let parsed = parse_skill_file(&out[0].0, &out[0].1).expect("parse");
        assert_eq!(
            parsed.frontmatter.cf_keywords,
            vec![
                "a".to_string(),
                "b".to_string(),
                "rust".to_string(),
                "c".to_string()
            ]
        );
    }

    #[test]
    fn pattern_to_skill_files_truncates_oversized_solution() {
        let mut p = sample_pattern(&"x".repeat(20000), "");
        p.solution = Some(PatternSolution {
            planner: "x".repeat(20000),
            reviewer: String::new(),
        });
        let out = pattern_to_skill_files(&p);
        assert_eq!(out.len(), 1);
        let body = &out[0].1;
        let solution_x_count = body.matches('x').count();
        assert!(
            solution_x_count <= 16100,
            "expected <=16100 x chars, got {}",
            solution_x_count
        );
    }

    #[test]
    fn load_skills_walks_subdirectories() {
        let tmp = tempfile::tempdir().expect("tempdir");
        let p = sample_pattern("plan", "");
        let files = pattern_to_skill_files(&p);
        let (dir_name, contents) = &files[0];
        write_skill(tmp.path(), dir_name, contents).expect("write");

        let p2 = Pattern {
            pattern_id: "second-pid".to_string(),
            ..sample_pattern("plan2", "")
        };
        let files2 = pattern_to_skill_files(&p2);
        write_skill(tmp.path(), &files2[0].0, &files2[0].1).expect("write");

        std::fs::write(tmp.path().join("not-a-skill.txt"), "ignored").expect("write");

        let skills = load_skills(tmp.path());
        assert_eq!(skills.len(), 2);
    }

    #[test]
    fn skill_to_pattern_round_trips_metadata() {
        let raw = "---\nname: x\ndescription: d\nmetadata:\n  cf-stage: planner\n  cf-citations-pass: 3\n  cf-citations-wip: 1\n  cf-last-used: 2026-04-09T00:00:00Z\n  cf-frequency: 4\n  cf-severity: HIGH\n  cf-keywords:\n    - foo\n---\n\n## Issue\n\nBad\n\n## Solution\n\nFix it\n";
        let sf = parse_skill_file("x", raw).expect("parse");
        let p = skill_to_pattern(sf);
        assert_eq!(p.cited_in_pass, 3);
        assert_eq!(p.cited_in_wip, 1);
        assert_eq!(p.frequency, 4);
        assert_eq!(p.severity.as_deref(), Some("HIGH"));
        assert_eq!(p.last_used_at.as_deref(), Some("2026-04-09"));
    }

    #[test]
    fn parse_frontmatter_rejects_missing_closing_delimiter() {
        let raw = "---\nname: x\ndescription: d\nmetadata:\n  cf-stage: planner\n";
        let err = parse_skill_file("x", raw).unwrap_err();
        assert!(format!("{:?}", err).contains("missing closing"));
    }

    #[test]
    fn skill_to_pattern_uses_dir_name_for_pattern_id() {
        let raw = "---\nname: stale-or-renamed\ndescription: d\nmetadata:\n  cf-stage: planner\n  cf-citations-pass: 0\n  cf-citations-wip: 0\n  cf-frequency: 1\n  cf-keywords:\n    - foo\n---\n\n## Issue\n\nBad\n\n## Solution\n\nFix it\n";
        let sf = parse_skill_file("on-disk-id", raw).expect("parse");
        let p = skill_to_pattern(sf);
        assert_eq!(p.pattern_id, "on-disk-id");
    }

    #[test]
    fn skill_to_pattern_falls_back_to_name_when_dir_name_empty() {
        let raw = "---\nname: only-name\ndescription: d\nmetadata:\n  cf-stage: planner\n  cf-citations-pass: 0\n  cf-citations-wip: 0\n  cf-frequency: 1\n  cf-keywords:\n    - foo\n---\n\n## Issue\n\nBad\n\n## Solution\n\nFix it\n";
        let sf = parse_skill_file("", raw).expect("parse");
        let p = skill_to_pattern(sf);
        assert_eq!(p.pattern_id, "only-name");
    }
}
