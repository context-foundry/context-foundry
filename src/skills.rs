use std::collections::{BTreeSet, HashMap};
use std::path::{Path, PathBuf};

use anyhow::{Context, Result};
use chrono::{NaiveDate, Utc};

use crate::embeddings;
use crate::patterns::{Pattern, PatternSolution};
use crate::skills_telemetry;
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

/// Hybrid retrieval over a stage-filtered set of skills. Combines BM25 keyword
/// scoring (via `patterns::keyword_scores`), optional Ollama-backed semantic
/// reranking (via `embeddings::match_patterns_semantic`), and a popularity +
/// recency multiplier sourced from `skills-telemetry.db`. Returns all skills
/// with a non-zero ranked score in descending order; the caller is still
/// responsible for capping via `format_skills_for_prompt(.., max_skills)`.
pub async fn rank_skills_for_task<'a>(
    skills: &[&'a SkillFile],
    task_desc: &str,
    detected_stack: &[String],
    semantic_match_enabled: bool,
    embedding_model: &str,
    embedding_timeout_ms: u64,
    ollama_url: &str,
) -> Vec<&'a SkillFile> {
    if skills.is_empty() {
        return Vec::new();
    }

    let owned_patterns: Vec<Pattern> = skills
        .iter()
        .map(|s| skill_to_pattern((*s).clone()))
        .collect();

    let kw_scores = crate::patterns::keyword_scores(&owned_patterns, task_desc, detected_stack);

    let semantic_scored: Vec<(&Pattern, usize)> = if semantic_match_enabled {
        let (scored, _result) = embeddings::match_patterns_semantic(
            &owned_patterns,
            task_desc,
            embedding_model,
            embedding_timeout_ms,
            &kw_scores,
            ollama_url,
        )
        .await;
        scored
    } else {
        let mut s: Vec<(&Pattern, usize)> = kw_scores
            .iter()
            .filter(|(_, sc)| *sc > 0)
            .map(|(idx, sc)| (&owned_patterns[*idx], *sc))
            .collect();
        s.sort_by_key(|a| std::cmp::Reverse(a.1));
        s
    };

    let telemetry = skills_telemetry::load_popularity_scores_or_default();
    let today = Utc::now().date_naive();

    let mut boosted: Vec<(String, usize)> = Vec::with_capacity(semantic_scored.len());
    for (p, score) in &semantic_scored {
        let mut multiplier: f64 = 1.0;
        if let Some(rec) = telemetry.get(&p.pattern_id) {
            if rec.citations_pass > 0 {
                multiplier *= 1.10;
            }
            if let Some(date_str) = rec.last_used.as_deref() {
                if let Ok(last) = NaiveDate::parse_from_str(date_str, "%Y-%m-%d") {
                    let days_ago = (today - last).num_days().max(0) as f64;
                    let decay = (-days_ago / 90.0_f64).exp().max(0.1_f64);
                    multiplier *= decay;
                }
            }
        }
        let final_score = ((*score as f64) * multiplier).round() as usize;
        if final_score > 0 {
            boosted.push((p.pattern_id.clone(), final_score));
        }
    }

    boosted.sort_by_key(|a| std::cmp::Reverse(a.1));

    let mut id_to_skill: HashMap<String, &'a SkillFile> = HashMap::with_capacity(skills.len());
    for s in skills {
        let id = if !s.dir_name.is_empty() {
            s.dir_name.clone()
        } else {
            s.frontmatter.name.clone()
        };
        id_to_skill.insert(id, *s);
    }

    let mut ranked: Vec<&'a SkillFile> = Vec::with_capacity(boosted.len());
    for (id, _) in &boosted {
        if let Some(skill) = id_to_skill.get(id.as_str()) {
            ranked.push(*skill);
        }
    }
    ranked
}

pub fn match_skills_for_stage<'a>(skills: &'a [SkillFile], stage: &str) -> Vec<&'a SkillFile> {
    let stage_lc = stage.trim().to_lowercase();
    skills
        .iter()
        .filter(|s| {
            let cf = s.frontmatter.cf_stage.trim().to_lowercase();
            cf == stage_lc || cf == "both" || cf.is_empty()
        })
        .collect()
}

/// Render the matched skills as a prompt-embeddable Markdown block.
///
/// Each skill block leads with its kebab-case `skill_id` (from
/// `frontmatter.name`) in a backtick-quoted header so the agent's natural
/// quoting style picks the ID up verbatim. A closing **Citation instruction**
/// asks the agent to list applied skill_ids in a `**Skills referenced:**`
/// footer at the bottom of its output -- this is what the post-AUDIT citation
/// scanner in `src/app/build.rs` greps for to close the feedback loop.
///
/// The citation instruction is injected *here* (rather than in `prompts.rs`)
/// so it stays adjacent to the skill list the agent must reference and is
/// emitted only when skills are actually present. Returns an empty string
/// when `skills` is empty.
pub fn format_skills_for_prompt(skills: &[&SkillFile], max_skills: usize) -> String {
    if skills.is_empty() {
        return String::new();
    }
    let limit = if max_skills == 0 { 10 } else { max_skills };
    let mut out = String::from("\n\n---\n## Available Skills (decide which to apply)\n\n");
    for (i, s) in skills.iter().take(limit).enumerate() {
        // Lead each block with the skill_id in backticks so the agent quotes
        // it verbatim (kebab-case, lowercase, exact match for scan_citations).
        out.push_str(&format!(
            "### {}. `{}` [cf-stage: {}]\n",
            i + 1,
            s.frontmatter.name,
            s.frontmatter.cf_stage
        ));
        if !s.frontmatter.description.is_empty() {
            out.push_str(&format!(
                "**Description:** {}\n",
                s.frontmatter.description
            ));
        }
        if !s.frontmatter.cf_keywords.is_empty() {
            out.push_str(&format!(
                "**Keywords:** {}\n",
                s.frontmatter.cf_keywords.join(", ")
            ));
        }
        out.push('\n');
    }
    out.push_str(
        "**Citation instruction:** when you apply guidance from any skill above, \
list its `skill_id` in a `**Skills referenced:**` footer at the bottom of your output. \
Only cite skill_ids from the list above -- do not invent new ones.\n",
    );
    out
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
pub fn write_skill(skills_dir: &Path, dir_name: &str, contents: &str) -> Result<()> {
    let dir = skills_dir.join(dir_name);
    std::fs::create_dir_all(&dir)
        .with_context(|| format!("failed to create {}", dir.display()))?;
    let target = dir.join("SKILL.md");
    atomic_write_file(&target, contents.as_bytes())
        .with_context(|| format!("failed to write {}", target.display()))?;
    Ok(())
}

/// Tally of what `write_extracted_skills` did so the build loop can
/// log per-skill outcomes through `LoopEvent::BackgroundLog`.
#[derive(Debug, Default)]
pub struct WriteExtractedReport {
    /// Skills written for the first time (one entry per dir_name actually placed).
    pub created: Vec<String>,
    /// Skills whose body matched an existing SKILL.md; frequency + last-used were bumped in place.
    pub bumped: Vec<String>,
    /// Patterns whose `solution` was None or both planner+reviewer empty -- nothing to emit.
    pub skipped_empty: usize,
}

/// Convert each freshly-extracted `Pattern` into one or two SKILL.md files
/// under `skills_dir`. Idempotent: bytewise-equal body bumps frequency in
/// place; differing body gets a `-2`, `-3`, ... suffix. Never silently
/// overwrites a different skill.
pub fn write_extracted_skills(
    skills_dir: &Path,
    patterns: &[Pattern],
) -> Result<WriteExtractedReport> {
    std::fs::create_dir_all(skills_dir)
        .with_context(|| format!("failed to create {}", skills_dir.display()))?;
    let mut report = WriteExtractedReport::default();
    let today = Utc::now().format("%Y-%m-%d").to_string();
    for p in patterns {
        let pairs = pattern_to_skill_files(p);
        if pairs.is_empty() {
            report.skipped_empty += 1;
            continue;
        }
        for (base_dir_name, contents) in pairs {
            apply_skill_emission(skills_dir, &base_dir_name, &contents, &today, &mut report)?;
        }
    }
    Ok(report)
}

fn apply_skill_emission(
    skills_dir: &Path,
    base_dir_name: &str,
    contents: &str,
    today: &str,
    report: &mut WriteExtractedReport,
) -> Result<()> {
    let new_body = body_only_from_skill_md(contents);
    let mut suffix: usize = 0;
    loop {
        let candidate = if suffix == 0 {
            base_dir_name.to_string()
        } else {
            format!("{}-{}", base_dir_name, suffix + 1)
        };
        let target_path = skills_dir.join(&candidate).join("SKILL.md");
        if !target_path.exists() {
            if suffix == 0 {
                write_skill(skills_dir, &candidate, contents)?;
            } else {
                let rewritten = rewrite_name_in_skill_md(contents, &candidate);
                write_skill(skills_dir, &candidate, &rewritten)?;
            }
            report.created.push(candidate);
            return Ok(());
        }
        let existing = std::fs::read_to_string(&target_path)
            .with_context(|| format!("failed to read {}", target_path.display()))?;
        let existing_body = body_only_from_skill_md(&existing);
        if existing_body == new_body {
            bump_skill_frequency_and_last_used(&target_path, today)?;
            report.bumped.push(candidate);
            return Ok(());
        }
        suffix += 1;
        if suffix > 99 {
            anyhow::bail!(
                "skill suffix exhausted for {} (>99 collisions)",
                base_dir_name
            );
        }
    }
}

fn body_only_from_skill_md(contents: &str) -> String {
    match parse_skill_file("", contents) {
        Ok(sf) => sf.body.trim().to_string(),
        Err(_) => contents.trim().to_string(),
    }
}

fn rewrite_name_in_skill_md(contents: &str, new_name: &str) -> String {
    let sf = match parse_skill_file("", contents) {
        Ok(sf) => sf,
        Err(_) => return contents.to_string(),
    };
    let mut fm = sf.frontmatter;
    fm.name = new_name.to_string();
    render_skill(&fm, &sf.body)
}

fn bump_skill_frequency_and_last_used(skill_md_path: &Path, today: &str) -> Result<()> {
    let original = std::fs::read_to_string(skill_md_path)
        .with_context(|| format!("failed to read {}", skill_md_path.display()))?;
    let sf = parse_skill_file("", &original)
        .with_context(|| format!("failed to parse {}", skill_md_path.display()))?;
    let mut fm = sf.frontmatter;
    fm.cf_frequency = fm.cf_frequency.saturating_add(1);
    fm.cf_last_used = Some(format!("{}T00:00:00Z", today));
    let new_contents = render_skill(&fm, &sf.body);
    atomic_write_file(skill_md_path, new_contents.as_bytes())
        .with_context(|| format!("failed to write {}", skill_md_path.display()))?;
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

    fn make_skill(name: &str, cf_stage: &str) -> SkillFile {
        SkillFile {
            dir_name: name.to_string(),
            frontmatter: SkillFrontmatter {
                name: name.to_string(),
                description: String::new(),
                cf_stage: cf_stage.to_string(),
                cf_citations_pass: 0,
                cf_citations_wip: 0,
                cf_last_used: None,
                cf_frequency: 0,
                cf_severity: None,
                cf_keywords: Vec::new(),
            },
            body: String::new(),
        }
    }

    #[test]
    fn match_skills_for_stage_filters_planner() {
        let skills = vec![
            make_skill("a", "planner"),
            make_skill("b", "reviewer"),
            make_skill("c", "both"),
        ];
        let result = match_skills_for_stage(&skills, "planner");
        assert_eq!(result.len(), 2);
        let names: Vec<&str> = result
            .iter()
            .map(|s| s.frontmatter.name.as_str())
            .collect();
        assert!(names.contains(&"a"));
        assert!(names.contains(&"c"));
    }

    #[test]
    fn match_skills_for_stage_keeps_empty_stage() {
        let skills = vec![make_skill("a", "")];
        let result = match_skills_for_stage(&skills, "reviewer");
        assert_eq!(result.len(), 1);
    }

    #[test]
    fn format_skills_for_prompt_lists_name_description_keywords() {
        let skill = SkillFile {
            dir_name: "sample".to_string(),
            frontmatter: SkillFrontmatter {
                name: "sample".to_string(),
                description: "does X".to_string(),
                cf_stage: "planner".to_string(),
                cf_citations_pass: 0,
                cf_citations_wip: 0,
                cf_last_used: None,
                cf_frequency: 0,
                cf_severity: None,
                cf_keywords: vec!["a".to_string(), "b".to_string()],
            },
            body: String::new(),
        };
        let refs: Vec<&SkillFile> = vec![&skill];
        let out = format_skills_for_prompt(&refs, 10);
        assert!(out.contains("## Available Skills"));
        assert!(out.contains("sample"));
        assert!(out.contains("does X"));
        assert!(out.contains("a, b"));
        assert!(out.contains("cf-stage: planner"));
        // T1.30: skill_id must appear as a backtick-quoted header so the
        // agent quotes it verbatim, and the citation instruction footer
        // must be present so the agent knows to cite applied skills.
        assert!(
            out.contains("`sample`"),
            "expected backtick-quoted skill_id header, got: {}",
            out
        );
        assert!(
            out.contains("Skills referenced:"),
            "expected citation instruction footer, got: {}",
            out
        );
        assert!(
            out.contains("skill_id"),
            "expected the word skill_id in the citation instruction, got: {}",
            out
        );
    }

    #[test]
    fn format_skills_for_prompt_lists_each_skill_id_only_once() {
        // Idempotence guard: re-formatting the same skill twice must not
        // duplicate the closing citation footer.
        let s1 = make_skill("alpha-planner", "planner");
        let s2 = make_skill("beta-planner", "planner");
        let refs: Vec<&SkillFile> = vec![&s1, &s2];
        let out = format_skills_for_prompt(&refs, 10);
        let footer_count = out.matches("Citation instruction:").count();
        assert_eq!(
            footer_count, 1,
            "footer must appear exactly once per format call, got {}: {}",
            footer_count, out
        );
        assert!(out.contains("`alpha-planner`"));
        assert!(out.contains("`beta-planner`"));
    }

    #[test]
    fn scan_citations_finds_skill_ids_in_skills_referenced_footer() {
        // T1.30 citation round-trip: a synthetic current-plan.md with the
        // expected `**Skills referenced:**` footer should be parsed by
        // patterns::scan_citations into a list of skill_ids.
        let s1 = make_skill("plan-file-token-overflow-planner", "planner");
        let s2 = make_skill("stats-structs-need-clone-for-tui-state-planner", "planner");
        let s3 = make_skill("unused-skill-planner", "planner");
        let pats: Vec<crate::patterns::Pattern> = vec![s1, s2, s3]
            .into_iter()
            .map(skill_to_pattern)
            .collect();

        let synthetic_plan = "\
# Plan: T1.30

## Dependencies
- none

## File Operations
- [MODIFY] src/app/build.rs -- counter wiring fix.

**Skills referenced:** `plan-file-token-overflow-planner`, \
`stats-structs-need-clone-for-tui-state-planner`
";

        let cited = crate::patterns::scan_citations(synthetic_plan, &pats);
        assert!(
            cited
                .iter()
                .any(|c| c == "plan-file-token-overflow-planner"),
            "expected plan-file-token-overflow-planner in {:?}",
            cited
        );
        assert!(
            cited
                .iter()
                .any(|c| c == "stats-structs-need-clone-for-tui-state-planner"),
            "expected stats-structs-need-clone-for-tui-state-planner in {:?}",
            cited
        );
        assert!(
            !cited.iter().any(|c| c == "unused-skill-planner"),
            "unused skill must NOT appear, got {:?}",
            cited
        );
    }

    #[test]
    fn format_skills_for_prompt_returns_empty_when_no_skills() {
        let empty: Vec<&SkillFile> = Vec::new();
        let out = format_skills_for_prompt(&empty, 10);
        assert_eq!(out, "");
    }

    fn make_skill_with_keywords(name: &str, kws: &[&str]) -> SkillFile {
        SkillFile {
            dir_name: name.to_string(),
            frontmatter: SkillFrontmatter {
                name: name.to_string(),
                description: String::new(),
                cf_stage: "planner".to_string(),
                cf_citations_pass: 0,
                cf_citations_wip: 0,
                cf_last_used: None,
                cf_frequency: 0,
                cf_severity: None,
                cf_keywords: kws.iter().map(|s| s.to_string()).collect(),
            },
            body: String::new(),
        }
    }

    #[tokio::test]
    async fn rank_skills_for_task_returns_empty_for_empty_input() {
        let empty: Vec<&SkillFile> = Vec::new();
        let out = rank_skills_for_task(
            &empty,
            "anything goes here",
            &[],
            false,
            "",
            0,
            "http://localhost:1",
        )
        .await;
        assert!(out.is_empty());
    }

    #[tokio::test]
    async fn rank_skills_for_task_orders_by_keyword_relevance() {
        let s1 = make_skill_with_keywords("alpha", &["phantom-path"]);
        let s2 = make_skill_with_keywords("beta", &["wholly-unrelated"]);
        let s3 = make_skill_with_keywords("gamma", &["templates"]);
        let refs: Vec<&SkillFile> = vec![&s1, &s2, &s3];
        let out = rank_skills_for_task(
            &refs,
            "task touches phantom-path templates handling",
            &[],
            false,
            "",
            0,
            "http://localhost:1",
        )
        .await;

        assert!(!out.is_empty(), "expected at least one matching skill");
        let names: Vec<&str> = out
            .iter()
            .map(|s| s.frontmatter.name.as_str())
            .collect();
        assert!(
            names.contains(&"alpha") || names.contains(&"gamma"),
            "expected alpha or gamma to surface; got {:?}",
            names
        );
        assert!(
            !names.contains(&"beta"),
            "beta has no overlapping keywords; should be excluded"
        );
    }

    #[test]
    fn write_extracted_skills_creates_planner_and_reviewer_for_dual_solution() {
        let p = sample_pattern("plan body", "review body");
        let dir = tempfile::tempdir().expect("tempdir");
        let report = write_extracted_skills(dir.path(), &[p]).expect("write");
        assert_eq!(report.created.len(), 2);
        assert!(report.bumped.is_empty());
        assert_eq!(report.skipped_empty, 0);
        assert!(dir.path().join("sample-pid-planner/SKILL.md").exists());
        assert!(dir.path().join("sample-pid-reviewer/SKILL.md").exists());
    }

    #[test]
    fn write_extracted_skills_bumps_frequency_on_byte_identical_body() {
        let p = sample_pattern("plan body", "review body");
        let dir = tempfile::tempdir().expect("tempdir");

        let first = write_extracted_skills(dir.path(), &[p.clone()]).expect("write1");
        assert_eq!(first.created.len(), 2);

        // Capture pre-bump frequency from the planner side.
        let planner_path = dir.path().join("sample-pid-planner/SKILL.md");
        let pre_contents = std::fs::read_to_string(&planner_path).expect("read pre");
        let pre = parse_skill_file("sample-pid-planner", &pre_contents).expect("parse pre");
        let pre_freq = pre.frontmatter.cf_frequency;

        let second = write_extracted_skills(dir.path(), &[p]).expect("write2");
        assert!(second.created.is_empty());
        assert_eq!(second.bumped.len(), 2);

        let post_contents = std::fs::read_to_string(&planner_path).expect("read post");
        let post = parse_skill_file("sample-pid-planner", &post_contents).expect("parse post");
        assert_eq!(post.frontmatter.cf_frequency, pre_freq + 1);
        let last_used = post.frontmatter.cf_last_used.expect("last_used set");
        assert!(
            last_used.ends_with("T00:00:00Z"),
            "expected ISO date suffix, got {}",
            last_used
        );
    }

    #[test]
    fn write_extracted_skills_appends_numeric_suffix_when_body_differs() {
        let dir = tempfile::tempdir().expect("tempdir");
        let p1 = sample_pattern("body A", "body A reviewer");
        let _ = write_extracted_skills(dir.path(), &[p1]).expect("first");

        let p2 = sample_pattern("body B", "body A reviewer");
        let report = write_extracted_skills(dir.path(), &[p2]).expect("second");

        assert!(dir.path().join("sample-pid-planner/SKILL.md").exists());
        assert!(dir.path().join("sample-pid-planner-2/SKILL.md").exists());
        assert!(report.bumped.iter().any(|s| s == "sample-pid-reviewer"));
        assert!(!dir.path().join("sample-pid-reviewer-2").exists());
    }

    #[test]
    fn write_extracted_skills_collision_rewrites_inner_name_to_match_dir() {
        let dir = tempfile::tempdir().expect("tempdir");
        let p1 = sample_pattern("body A", "body A reviewer");
        let _ = write_extracted_skills(dir.path(), &[p1]).expect("first");

        let p2 = sample_pattern("body B", "body A reviewer");
        let _ = write_extracted_skills(dir.path(), &[p2]).expect("second");

        let suffix_path = dir.path().join("sample-pid-planner-2/SKILL.md");
        let contents = std::fs::read_to_string(&suffix_path).expect("read suffix");
        let parsed = parse_skill_file("sample-pid-planner-2", &contents).expect("parse suffix");
        assert_eq!(parsed.frontmatter.name, "sample-pid-planner-2");
    }

    #[test]
    fn write_extracted_skills_skips_pattern_without_solution() {
        let dir = tempfile::tempdir().expect("tempdir");
        let mut p_none = sample_pattern("x", "y");
        p_none.solution = None;
        let mut p_empty = sample_pattern("x", "y");
        p_empty.solution = Some(PatternSolution {
            planner: String::new(),
            reviewer: String::new(),
        });

        let report = write_extracted_skills(dir.path(), &[p_none, p_empty]).expect("write");
        assert!(report.created.is_empty());
        assert!(report.bumped.is_empty());
        assert_eq!(report.skipped_empty, 2);
    }

    #[test]
    fn bump_frequency_and_last_used_round_trips_after_crlf_normalization() {
        let dir = tempfile::tempdir().expect("tempdir");
        let target_dir = dir.path().join("crlf-skill");
        std::fs::create_dir_all(&target_dir).expect("mkdir");
        let target = target_dir.join("SKILL.md");
        let raw = "---\r\nname: crlf-skill\r\ndescription: d\r\nmetadata:\r\n  cf-stage: planner\r\n  cf-citations-pass: 0\r\n  cf-citations-wip: 0\r\n  cf-frequency: 4\r\n  cf-keywords:\r\n    - foo\r\n---\r\n\r\n## Issue\r\n\r\nBody text\r\n\r\n## Solution\r\n\r\nDo X\r\n";
        std::fs::write(&target, raw).expect("write raw");

        bump_skill_frequency_and_last_used(&target, "2026-05-10").expect("bump");

        let after = std::fs::read_to_string(&target).expect("read after");
        let parsed = parse_skill_file("crlf-skill", &after).expect("parse after");
        assert_eq!(parsed.frontmatter.cf_frequency, 5);
        assert_eq!(
            parsed.frontmatter.cf_last_used.as_deref(),
            Some("2026-05-10T00:00:00Z")
        );
        assert!(parsed.body.contains("Body text"));
        assert!(parsed.body.contains("Do X"));
        assert!(!after.contains('\r'), "re-rendered file should be LF-only");
    }
}
