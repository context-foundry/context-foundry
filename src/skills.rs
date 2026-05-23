use std::collections::{BTreeSet, HashMap};
use std::path::{Path, PathBuf};
use std::sync::OnceLock;

use anyhow::{Context, Result};
use chrono::{NaiveDate, Utc};

use crate::embeddings;
use crate::patterns::{Pattern, PatternSolution};
use crate::skill_discovery::{DiscoveredSkill, SkillSource};
use crate::skills_telemetry;
use crate::utils::atomic_write_file;

/// Where a `SkillFile` came from. Drives telemetry/citation labels and the
/// dedup precedence when two skills share a `name`/`dir_name`.
///
/// Order of variants matches precedence (highest first) used by the
/// merged-pool dedup in `load_skills_from_global_and_project`:
///   1. `GlobalFoundry`  (`~/.foundry/skills/<topic>/SKILL.md`)
///   2. `ClaudeProject`  (`<project>/.claude/skills/<topic>/SKILL.md`)
///   3. `AgentsMd`       (project AGENTS.md, then ancestor AGENTS.md)
///   4. `CopilotInstructions` (`.github/copilot-instructions.md`)
///   5. `CursorRules`    (`<project>/.cursorrules`)
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum SkillProvenance {
    #[default]
    GlobalFoundry,
    ClaudeProject,
    AgentsMd,
    CopilotInstructions,
    CursorRules,
}

impl SkillProvenance {
    /// Higher = wins on name collision.
    pub fn precedence(self) -> u8 {
        match self {
            Self::GlobalFoundry => 5,
            Self::ClaudeProject => 4,
            Self::AgentsMd => 3,
            Self::CopilotInstructions => 2,
            Self::CursorRules => 1,
        }
    }

    /// Short label for telemetry attribution and citation logs.
    #[allow(dead_code)]
    pub fn label(self) -> &'static str {
        match self {
            Self::GlobalFoundry => "global-foundry",
            Self::ClaudeProject => "claude-project",
            Self::AgentsMd => "agents-md",
            Self::CopilotInstructions => "copilot",
            Self::CursorRules => "cursor",
        }
    }

    /// Map a `SkillSource` from cross-provider discovery into a `SkillProvenance`.
    pub fn from_skill_source(src: SkillSource) -> Self {
        match src {
            SkillSource::ClaudeProjectSkill => Self::ClaudeProject,
            SkillSource::AgentsMd => Self::AgentsMd,
            SkillSource::CopilotInstructions => Self::CopilotInstructions,
            SkillSource::CursorRules => Self::CursorRules,
        }
    }
}

/// A single SKILL.md file on disk parsed back into a Pattern shape so the
/// existing matcher can consume it without further changes.
#[derive(Debug, Clone, Default)]
pub struct SkillFile {
    pub dir_name: String,
    pub frontmatter: SkillFrontmatter,
    pub body: String,
    /// T2.4: source of this skill. Default `GlobalFoundry` for any code
    /// path that pre-dates the cross-provider merge (parse_skill_file,
    /// load_skills, etc.). The cross-provider discovery path sets this
    /// explicitly via `discovered_to_skill_file`.
    pub provenance: SkillProvenance,
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

/// T2.4: return the merged auto-retrieval skill pool combining
/// `~/.foundry/skills/` and cross-provider discovered SKILL.md / AGENTS.md /
/// .cursorrules / .github/copilot-instructions.md files in the given project
/// directory. Dedup rule: on `dir_name` collision the higher
/// `SkillProvenance::precedence()` wins (global > .claude > AGENTS.md >
/// copilot > cursor).
pub fn load_skills_from_global_and_project(project_dir: &Path) -> Vec<SkillFile> {
    let global = load_skills_from_global();
    let discovered = crate::skill_discovery::discover_external_skills(project_dir);

    let mut by_name: HashMap<String, SkillFile> =
        HashMap::with_capacity(global.len() + discovered.len());
    let key_of = |sf: &SkillFile| -> String {
        if !sf.dir_name.is_empty() {
            sf.dir_name.clone()
        } else {
            sf.frontmatter.name.clone()
        }
    };

    for sf in global {
        let key = key_of(&sf);
        by_name.insert(key, sf);
    }

    for disc in &discovered {
        let cand = discovered_to_skill_file(disc);
        let key = key_of(&cand);
        let new_winner = match by_name.get(&key) {
            Some(existing) => cand.provenance.precedence() > existing.provenance.precedence(),
            None => true,
        };
        if new_winner {
            by_name.insert(key, cand);
        }
    }

    by_name.into_values().collect()
}

/// T2.4: render the one-line skill-pool summary that appears above the
/// Plugins panel on the startup screen. Buckets are listed in the same
/// precedence order as `SkillProvenance`; zero-count buckets are omitted.
/// Returns `"Skill pool: 0 total"` when the slice is empty.
pub fn skill_pool_summary(skills: &[SkillFile]) -> String {
    if skills.is_empty() {
        return "Skill pool: 0 total".to_string();
    }
    let mut global = 0usize;
    let mut claude = 0usize;
    let mut agents = 0usize;
    let mut copilot = 0usize;
    let mut cursor = 0usize;
    for s in skills {
        match s.provenance {
            SkillProvenance::GlobalFoundry => global += 1,
            SkillProvenance::ClaudeProject => claude += 1,
            SkillProvenance::AgentsMd => agents += 1,
            SkillProvenance::CopilotInstructions => copilot += 1,
            SkillProvenance::CursorRules => cursor += 1,
        }
    }
    let total = global + claude + agents + copilot + cursor;
    let mut buckets: Vec<String> = Vec::new();
    if global > 0 {
        buckets.push(format!("{} global", global));
    }
    if claude > 0 {
        buckets.push(format!("{} from .claude/skills/", claude));
    }
    if agents > 0 {
        buckets.push(format!("{} from AGENTS.md", agents));
    }
    if copilot > 0 {
        buckets.push(format!("{} from copilot", copilot));
    }
    if cursor > 0 {
        buckets.push(format!("{} from .cursorrules", cursor));
    }
    format!("Skill pool: {} = {} total", buckets.join(", "), total)
}

/// Build display rows for the Skills Browser overlay. Sorted by source
/// precedence (global -> .claude -> agents -> copilot -> cursor) then name.
pub fn build_skills_overlay_rows(
    skills: &[SkillFile],
    project_dir: &Path,
) -> Vec<crate::app::SkillsOverlayRow> {
    let home = std::env::var_os("HOME").map(PathBuf::from);
    let project_str = project_dir.display().to_string();

    let mut rows: Vec<crate::app::SkillsOverlayRow> = skills
        .iter()
        .map(|s| {
            let (source_label, path_hint) = match s.provenance {
                SkillProvenance::GlobalFoundry => {
                    let raw = format!("~/.foundry/skills/{}/SKILL.md", s.dir_name);
                    let p = if let Some(ref h) = home {
                        raw.replacen("~", &h.display().to_string(), 1)
                    } else {
                        raw
                    };
                    ("global", p)
                }
                SkillProvenance::ClaudeProject => (
                    ".claude",
                    format!("{}/.claude/skills/{}/SKILL.md", project_str, s.dir_name),
                ),
                SkillProvenance::AgentsMd => ("agents", format!("{}/AGENTS.md", project_str)),
                SkillProvenance::CopilotInstructions => (
                    "copilot",
                    format!("{}/.github/copilot-instructions.md", project_str),
                ),
                SkillProvenance::CursorRules => ("cursor", format!("{}/.cursorrules", project_str)),
            };
            let name = if s.frontmatter.name.is_empty() {
                s.dir_name.clone()
            } else {
                s.frontmatter.name.clone()
            };
            crate::app::SkillsOverlayRow {
                name,
                description: s.frontmatter.description.clone(),
                source_label,
                path_hint,
            }
        })
        .collect();

    rows.sort_by(|a, b| {
        source_rank(a.source_label)
            .cmp(&source_rank(b.source_label))
            .then(a.name.to_lowercase().cmp(&b.name.to_lowercase()))
    });
    rows
}

fn source_rank(label: &str) -> u8 {
    match label {
        "global" => 0,
        ".claude" => 1,
        "agents" => 2,
        "copilot" => 3,
        "cursor" => 4,
        _ => 9,
    }
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

    let keywords = {
        let mut out: Vec<String> = Vec::new();
        let mut seen: std::collections::HashSet<String> = std::collections::HashSet::new();
        // 1. curated overrides keyed by pattern_id (applies to ANY skill with an
        //    entry in the sidecar JSON; in practice only the 14 Superpowers ids).
        if let Some(over) = keyword_overrides().get(&pattern_id) {
            for k in over {
                if seen.insert(k.clone()) {
                    out.push(k.clone());
                }
            }
        }
        // 2. baseline source: synthesized fallback when frontmatter cf-keywords
        //    is empty, otherwise the authored cf-keywords verbatim. Preserves
        //    pre-T2.1 behavior for skills with explicit metadata so unrelated
        //    skills don't have their BM25 vocabulary silently broadened.
        if s.frontmatter.cf_keywords.is_empty() {
            for k in synthesize_keywords(&pattern_id, &s.frontmatter.description) {
                if seen.insert(k.clone()) {
                    out.push(k);
                }
            }
        } else {
            for k in &s.frontmatter.cf_keywords {
                if seen.insert(k.clone()) {
                    out.push(k.clone());
                }
            }
        }
        out
    };

    Pattern {
        pattern_id,
        title: s.frontmatter.description.clone(),
        first_seen: String::new(),
        last_seen: String::new(),
        frequency: s.frontmatter.cf_frequency,
        severity: s.frontmatter.cf_severity.clone(),
        keywords,
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

/// Generate fallback keywords when a SKILL.md omits the `metadata.cf-keywords`
/// block. Without explicit keywords, the BM25 path scores 0; combined with a
/// cold embedding cache or an unavailable Ollama, the skill becomes invisible
/// to the retriever. Synthesizing from the pattern_id (kebab-case) and the
/// description gives the keyword path a baseline signal.
///
/// Source order: `pattern_id` tokens (kebab-split) + description content words
/// (filtered against stopwords). Lowercased. Deduplicated. Capped at 24 tokens
/// to keep the BM25 vocabulary bounded.
pub fn synthesize_keywords(pattern_id: &str, description: &str) -> Vec<String> {
    const STOPWORDS: &[&str] = &[
        "the", "a", "an", "and", "or", "but", "if", "is", "are", "was", "were", "be", "been",
        "being", "use", "uses", "used", "using", "when", "where", "what", "which", "who", "whom",
        "this", "that", "these", "those", "of", "on", "in", "at", "to", "for", "with", "without",
        "any", "all", "you", "must", "should", "before", "after", "from", "by", "into", "as", "it",
        "its", "your", "yours", "we", "our", "us", "i", "they", "their", "them", "do", "does",
        "did", "have", "has", "had", "can", "could", "will", "would", "may", "might", "etc",
    ];

    let mut out: Vec<String> = Vec::with_capacity(24);
    let mut seen: std::collections::HashSet<String> = std::collections::HashSet::new();
    let push =
        |token: String, out: &mut Vec<String>, seen: &mut std::collections::HashSet<String>| {
            if token.len() < 3 || STOPWORDS.contains(&token.as_str()) {
                return;
            }
            if seen.insert(token.clone()) {
                out.push(token);
            }
        };

    // 1. pattern_id tokens (kebab-split)
    for tok in pattern_id.split('-') {
        push(tok.to_lowercase(), &mut out, &mut seen);
    }

    // 2. description content words: lowercase alphanum + apostrophe runs, drop short/stopwords
    let mut buf = String::new();
    let flush =
        |buf: &mut String, out: &mut Vec<String>, seen: &mut std::collections::HashSet<String>| {
            if !buf.is_empty() {
                let token = std::mem::take(buf);
                push(token, out, seen);
            }
        };
    for ch in description.chars() {
        if ch.is_ascii_alphanumeric() || ch == '\'' {
            buf.extend(ch.to_lowercase());
        } else {
            flush(&mut buf, &mut out, &mut seen);
        }
        if out.len() >= 24 {
            break;
        }
    }
    flush(&mut buf, &mut out, &mut seen);

    out
}

/// Curated per-skill keyword overrides loaded once from
/// `~/.foundry/skill-keywords-overrides.json`. Used to give foreign skill
/// packs (e.g. Anthropic Superpowers) a hand-tuned BM25 vocabulary without
/// modifying their on-disk SKILL.md files.
static KEYWORD_OVERRIDES: OnceLock<HashMap<String, Vec<String>>> = OnceLock::new();

fn keyword_overrides() -> &'static HashMap<String, Vec<String>> {
    KEYWORD_OVERRIDES.get_or_init(load_keyword_overrides)
}

fn load_keyword_overrides() -> HashMap<String, Vec<String>> {
    let home = match crate::utils::home_dir() {
        Some(h) => h,
        None => return HashMap::new(),
    };
    let path = home.join(".foundry").join("skill-keywords-overrides.json");
    if !path.exists() {
        return HashMap::new();
    }
    let content = match std::fs::read_to_string(&path) {
        Ok(c) => c,
        Err(e) => {
            eprintln!(
                "warning: failed to read {}: {} -- skipping",
                path.display(),
                e
            );
            return HashMap::new();
        }
    };
    match serde_json::from_str::<HashMap<String, Vec<String>>>(&content) {
        Ok(map) => map,
        Err(e) => {
            eprintln!(
                "warning: failed to parse {}: {} -- skipping",
                path.display(),
                e
            );
            HashMap::new()
        }
    }
}

/// Synthesize a `SkillFile` from an externally-discovered skill (AGENTS.md,
/// .cursorrules, or a project-local `.claude/skills/<topic>/SKILL.md`).
///
/// For `ClaudeProjectSkill` sources whose files have valid SKILL.md
/// frontmatter, the parsed `name` and `description` are reused verbatim. For
/// AGENTS.md and .cursorrules (plain markdown, no frontmatter), the name is
/// derived and the description is a stub indicating import provenance.
///
/// `cf-stage` defaults to `both` so the skill is offered to both planner and
/// reviewer prompts -- external skills don't carry CF's per-stage targeting.
///
/// T2.4: this is the canonical converter for the auto-retrieval merge path;
/// `load_skills_from_global_and_project` calls it to materialize an in-memory
/// `SkillFile` from each foreign discovered skill before the dedup step.
pub fn discovered_to_skill_file(disc: &DiscoveredSkill) -> SkillFile {
    let (name, description, cf_stage) = match (&disc.frontmatter, disc.source) {
        (Some(fm), SkillSource::ClaudeProjectSkill) => {
            let name = if !fm.name.is_empty() {
                fm.name.clone()
            } else {
                disc.derived_name.clone()
            };
            let description = if !fm.description.is_empty() {
                fm.description.clone()
            } else {
                format!("Imported from {}", disc.source.ui_label())
            };
            let stage = if fm.cf_stage.trim().is_empty() {
                "both".to_string()
            } else {
                fm.cf_stage.clone()
            };
            (name, description, stage)
        }
        _ => (
            disc.derived_name.clone(),
            format!("Imported from {}", disc.source.ui_label()),
            "both".to_string(),
        ),
    };

    let frontmatter = SkillFrontmatter {
        name,
        description,
        cf_stage,
        cf_citations_pass: 0,
        cf_citations_wip: 0,
        cf_last_used: None,
        cf_frequency: 0,
        cf_severity: None,
        cf_keywords: Vec::new(),
    };

    SkillFile {
        // Use derived_name as a stable dir_name placeholder so collision
        // resolution and the matcher's pattern_id derivation work consistently.
        dir_name: disc.derived_name.clone(),
        frontmatter,
        body: disc.body.clone(),
        provenance: SkillProvenance::from_skill_source(disc.source),
    }
}

/// Render a discovered external skill as a prompt-embeddable Markdown block
/// with an explicit `source: <label>` so the agent sees provenance and the
/// post-AUDIT citation scanner can attribute the contribution.
///
/// Each block is prefixed with the source label and the file path, then the
/// raw body is included verbatim. Returns an empty string if `discovered` is
/// empty.
///
/// T2.4: no longer called from any production path -- cross-provider skills
/// now flow through `load_skills_from_global_and_project` and the standard
/// ranker. Kept for the existing test suite in `src/skills.rs`.
#[allow(dead_code)]
pub fn format_discovered_skills_for_prompt(
    discovered: &[(SkillSource, &DiscoveredSkill)],
) -> String {
    if discovered.is_empty() {
        return String::new();
    }
    let mut out = String::from("\n\n---\n## External Skills (decide which to apply)\n\n");
    for (source, disc) in discovered {
        out.push_str(&format!(
            "### `{}` [source: {}]\n",
            disc.derived_name,
            source.prompt_label()
        ));
        out.push_str(&format!("**Path:** `{}`\n\n", disc.path.display()));
        let body = disc.body.trim();
        if !body.is_empty() {
            out.push_str(body);
            out.push('\n');
        }
        out.push('\n');
    }
    out.push_str(
        "**Citation instruction:** when you apply guidance from any external skill above, \
list its name in a `**Skills referenced:**` footer at the bottom of your output.\n",
    );
    out
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
        let final_score =
            apply_skill_telemetry_multiplier(*score, telemetry.get(&p.pattern_id), today);
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

fn apply_skill_telemetry_multiplier(
    score: usize,
    rec: Option<&skills_telemetry::PopularityRecord>,
    today: NaiveDate,
) -> usize {
    let mut multiplier: f64 = 1.0;
    if let Some(rec) = rec {
        if rec.citations_pass > 0 {
            multiplier *= 1.10;
        }
        if rec.citations_wip > rec.citations_pass {
            multiplier *= 0.85;
        }
        if rec.feedback_confirmed > 0 {
            multiplier *= 1.05_f64.powi(rec.feedback_confirmed.min(3) as i32);
        }
        if rec.feedback_stale > 0 {
            multiplier *= 0.65_f64.powi(rec.feedback_stale.min(3) as i32);
        }
        if rec.feedback_wrong > 0 {
            multiplier *= 0.35_f64.powi(rec.feedback_wrong.min(3) as i32);
        }
        if let Some(date_str) = rec.last_used.as_deref() {
            if let Ok(last) = NaiveDate::parse_from_str(date_str, "%Y-%m-%d") {
                let days_ago = (today - last).num_days().max(0) as f64;
                let decay = (-days_ago / 90.0_f64).exp().max(0.1_f64);
                multiplier *= decay;
            }
        }
    }
    ((score as f64) * multiplier).round() as usize
}

/// T2.2: same ranking algorithm as `rank_skills_for_task` but returns each
/// ranked skill paired with its post-telemetry-boost score (as f32) so the
/// TUI can surface per-stage retrieval transparency. The eight existing call
/// sites use the score-less variant unchanged.
#[allow(clippy::too_many_arguments)]
pub async fn rank_skills_for_task_with_scores<'a>(
    skills: &[&'a SkillFile],
    task_desc: &str,
    detected_stack: &[String],
    semantic_match_enabled: bool,
    embedding_model: &str,
    embedding_timeout_ms: u64,
    ollama_url: &str,
) -> Vec<(&'a SkillFile, f32)> {
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
        let final_score =
            apply_skill_telemetry_multiplier(*score, telemetry.get(&p.pattern_id), today);
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

    let mut ranked_with_scores: Vec<(&'a SkillFile, f32)> = Vec::with_capacity(boosted.len());
    for (id, score) in &boosted {
        if let Some(skill) = id_to_skill.get(id.as_str()) {
            ranked_with_scores.push((*skill, *score as f32));
        }
    }
    ranked_with_scores
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

/// Stage-tolerant skill selector. When `strict == false` (the default),
/// returns every skill so the ranker can decide what is relevant for the
/// requested stage. When `strict == true`, falls back to the legacy
/// `match_skills_for_stage` behavior that filters on the `cf-stage`
/// frontmatter field.
pub fn select_skills_for_stage<'a>(
    skills: &'a [SkillFile],
    stage: &str,
    strict: bool,
) -> Vec<&'a SkillFile> {
    if strict {
        return match_skills_for_stage(skills, stage);
    }
    let mut out: Vec<&'a SkillFile> = Vec::with_capacity(skills.len());
    for s in skills {
        out.push(s);
    }
    out
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
            out.push_str(&format!("**Description:** {}\n", s.frontmatter.description));
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
        provenance: SkillProvenance::GlobalFoundry,
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
                        fm.cf_citations_pass =
                            value_part.trim().parse::<usize>().with_context(|| {
                                format!("integer field {} not parseable: {}", key, value_part)
                            })?;
                    }
                    "cf-citations-wip" => {
                        fm.cf_citations_wip =
                            value_part.trim().parse::<usize>().with_context(|| {
                                format!("integer field {} not parseable: {}", key, value_part)
                            })?;
                    }
                    "cf-frequency" => {
                        fm.cf_frequency =
                            value_part.trim().parse::<usize>().with_context(|| {
                                format!("integer field {} not parseable: {}", key, value_part)
                            })?;
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
    let one_line: String = v.replace(['\n', '\r'], " ");
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
    std::fs::create_dir_all(&dir).with_context(|| format!("failed to create {}", dir.display()))?;
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
            provenance: SkillProvenance::GlobalFoundry,
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
        let names: Vec<&str> = result.iter().map(|s| s.frontmatter.name.as_str()).collect();
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
    fn select_skills_for_stage_non_strict_returns_all_regardless_of_cf_stage() {
        let skills = vec![
            make_skill("a", "planner"),
            make_skill("b", "reviewer"),
            make_skill("c", "both"),
            make_skill("d", ""),
        ];
        let result = select_skills_for_stage(&skills, "builder", false);
        assert_eq!(result.len(), 4);
    }

    #[test]
    fn select_skills_for_stage_strict_matches_legacy_filter() {
        let skills = vec![
            make_skill("a", "planner"),
            make_skill("b", "reviewer"),
            make_skill("c", "both"),
            make_skill("d", ""),
        ];
        let result = select_skills_for_stage(&skills, "planner", true);
        assert_eq!(result.len(), 3);
        let names: Vec<&str> = result.iter().map(|s| s.frontmatter.name.as_str()).collect();
        assert!(!names.contains(&"b"));
    }

    #[test]
    fn select_skills_for_stage_non_strict_preserves_input_order() {
        let skills = vec![make_skill("z", "planner"), make_skill("a", "reviewer")];
        let result = select_skills_for_stage(&skills, "query", false);
        assert_eq!(result.len(), 2);
        assert_eq!(result[0].frontmatter.name, "z");
        assert_eq!(result[1].frontmatter.name, "a");
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
            provenance: SkillProvenance::GlobalFoundry,
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
        let pats: Vec<crate::patterns::Pattern> =
            vec![s1, s2, s3].into_iter().map(skill_to_pattern).collect();

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
            provenance: SkillProvenance::GlobalFoundry,
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
        let names: Vec<&str> = out.iter().map(|s| s.frontmatter.name.as_str()).collect();
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
    fn skill_telemetry_multiplier_applies_feedback_penalties() {
        let today = Utc::now().date_naive();
        let confirmed = crate::skills_telemetry::PopularityRecord {
            feedback_confirmed: 2,
            ..Default::default()
        };
        let stale = crate::skills_telemetry::PopularityRecord {
            feedback_stale: 1,
            ..Default::default()
        };
        let wrong = crate::skills_telemetry::PopularityRecord {
            feedback_wrong: 1,
            ..Default::default()
        };
        let wip_heavy = crate::skills_telemetry::PopularityRecord {
            citations_pass: 1,
            citations_wip: 2,
            ..Default::default()
        };

        assert_eq!(apply_skill_telemetry_multiplier(100, None, today), 100);
        assert_eq!(
            apply_skill_telemetry_multiplier(100, Some(&confirmed), today),
            110
        );
        assert_eq!(
            apply_skill_telemetry_multiplier(100, Some(&stale), today),
            65
        );
        assert_eq!(
            apply_skill_telemetry_multiplier(100, Some(&wrong), today),
            35
        );
        assert_eq!(
            apply_skill_telemetry_multiplier(100, Some(&wip_heavy), today),
            94
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

        let first = write_extracted_skills(dir.path(), std::slice::from_ref(&p)).expect("write1");
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

    #[test]
    fn discovered_to_skill_file_agents_md_uses_default_name_and_stub_description() {
        let disc = DiscoveredSkill {
            source: SkillSource::AgentsMd,
            path: PathBuf::from("/tmp/AGENTS.md"),
            body: "Some agents rules.".to_string(),
            derived_name: "agents-md".to_string(),
            frontmatter: None,
        };
        let sf = discovered_to_skill_file(&disc);
        assert_eq!(sf.frontmatter.name, "agents-md");
        assert_eq!(sf.frontmatter.cf_stage, "both");
        assert!(
            sf.frontmatter.description.contains("AGENTS.md"),
            "expected description to mention AGENTS.md, got: {}",
            sf.frontmatter.description
        );
        assert_eq!(sf.body, "Some agents rules.");
        assert_eq!(sf.dir_name, "agents-md");
    }

    #[test]
    fn discovered_to_skill_file_claude_skill_reuses_existing_frontmatter() {
        let fm = SkillFrontmatter {
            name: "audit-flowise".to_string(),
            description: "Audit a Flowise flow.".to_string(),
            ..Default::default()
        };
        let disc = DiscoveredSkill {
            source: SkillSource::ClaudeProjectSkill,
            path: PathBuf::from("/tmp/.claude/skills/audit-flowise/SKILL.md"),
            body: "Do audit.".to_string(),
            derived_name: "audit-flowise".to_string(),
            frontmatter: Some(fm),
        };
        let sf = discovered_to_skill_file(&disc);
        assert_eq!(sf.frontmatter.name, "audit-flowise");
        assert_eq!(sf.frontmatter.description, "Audit a Flowise flow.");
        // No cf_stage configured -> default to "both".
        assert_eq!(sf.frontmatter.cf_stage, "both");
        assert_eq!(sf.body, "Do audit.");
    }

    #[test]
    fn discovered_to_skill_file_claude_skill_falls_back_to_derived_name_when_blank() {
        let fm = SkillFrontmatter::default(); // empty name + description
        let disc = DiscoveredSkill {
            source: SkillSource::ClaudeProjectSkill,
            path: PathBuf::from("/tmp/.claude/skills/topic/SKILL.md"),
            body: "body".to_string(),
            derived_name: "topic".to_string(),
            frontmatter: Some(fm),
        };
        let sf = discovered_to_skill_file(&disc);
        assert_eq!(sf.frontmatter.name, "topic");
        assert!(
            sf.frontmatter.description.contains(".claude/skills"),
            "expected description fallback to mention path label, got: {}",
            sf.frontmatter.description
        );
    }

    #[test]
    fn format_discovered_skills_returns_empty_when_none() {
        let out = format_discovered_skills_for_prompt(&[]);
        assert_eq!(out, "");
    }

    #[test]
    fn format_discovered_skills_includes_source_label_and_path() {
        let disc = DiscoveredSkill {
            source: SkillSource::AgentsMd,
            path: PathBuf::from("/tmp/AGENTS.md"),
            body: "Imported agent rules go here.".to_string(),
            derived_name: "agents-md".to_string(),
            frontmatter: None,
        };
        let entries: Vec<(SkillSource, &DiscoveredSkill)> = vec![(SkillSource::AgentsMd, &disc)];
        let out = format_discovered_skills_for_prompt(&entries);
        assert!(out.contains("## External Skills"));
        assert!(
            out.contains("source: agents-md"),
            "expected source label, got: {}",
            out
        );
        assert!(out.contains("/tmp/AGENTS.md"));
        assert!(out.contains("Imported agent rules"));
        assert!(
            out.contains("Skills referenced:"),
            "expected citation instruction footer, got: {}",
            out
        );
    }

    #[test]
    fn format_discovered_skills_renders_each_source_with_distinct_label() {
        let agents = DiscoveredSkill {
            source: SkillSource::AgentsMd,
            path: PathBuf::from("/p/AGENTS.md"),
            body: "agents body".to_string(),
            derived_name: "agents-md".to_string(),
            frontmatter: None,
        };
        let cursor = DiscoveredSkill {
            source: SkillSource::CursorRules,
            path: PathBuf::from("/p/.cursorrules"),
            body: "cursor body".to_string(),
            derived_name: "cursorrules".to_string(),
            frontmatter: None,
        };
        let claude = DiscoveredSkill {
            source: SkillSource::ClaudeProjectSkill,
            path: PathBuf::from("/p/.claude/skills/x/SKILL.md"),
            body: "claude body".to_string(),
            derived_name: "x".to_string(),
            frontmatter: None,
        };
        let entries: Vec<(SkillSource, &DiscoveredSkill)> = vec![
            (SkillSource::ClaudeProjectSkill, &claude),
            (SkillSource::AgentsMd, &agents),
            (SkillSource::CursorRules, &cursor),
        ];
        let out = format_discovered_skills_for_prompt(&entries);
        assert!(out.contains("source: claude-project"));
        assert!(out.contains("source: agents-md"));
        assert!(out.contains("source: cursor"));
        assert!(out.contains("agents body"));
        assert!(out.contains("cursor body"));
        assert!(out.contains("claude body"));
        // Footer appears exactly once.
        assert_eq!(out.matches("Citation instruction:").count(), 1);
    }

    #[test]
    fn discovered_to_skill_file_copilot_uses_default_name_and_stub_description() {
        let disc = DiscoveredSkill {
            source: SkillSource::CopilotInstructions,
            path: PathBuf::from("/tmp/.github/copilot-instructions.md"),
            body: "Use anyhow.".to_string(),
            derived_name: "copilot-instructions".to_string(),
            frontmatter: None,
        };
        let sf = discovered_to_skill_file(&disc);
        assert_eq!(sf.frontmatter.name, "copilot-instructions");
        assert_eq!(sf.frontmatter.cf_stage, "both");
        assert!(
            sf.frontmatter
                .description
                .contains(".github/copilot-instructions.md"),
            "expected description to mention the ui_label, got: {}",
            sf.frontmatter.description
        );
        assert_eq!(sf.body, "Use anyhow.");
        assert_eq!(sf.dir_name, "copilot-instructions");
    }

    #[test]
    fn format_discovered_skills_renders_copilot_source_label() {
        let disc = DiscoveredSkill {
            source: SkillSource::CopilotInstructions,
            path: PathBuf::from("/tmp/.github/copilot-instructions.md"),
            body: "Imported copilot instructions go here.".to_string(),
            derived_name: "copilot-instructions".to_string(),
            frontmatter: None,
        };
        let entries: Vec<(SkillSource, &DiscoveredSkill)> =
            vec![(SkillSource::CopilotInstructions, &disc)];
        let out = format_discovered_skills_for_prompt(&entries);
        assert!(out.contains("## External Skills"));
        assert!(
            out.contains("source: copilot"),
            "expected copilot source label, got: {}",
            out
        );
        assert!(out.contains("/tmp/.github/copilot-instructions.md"));
        assert!(out.contains("Imported copilot instructions"));
        assert!(
            out.contains("Skills referenced:"),
            "expected citation instruction footer, got: {}",
            out
        );
    }
}

#[cfg(test)]
mod synthesize_keywords_tests {
    use super::synthesize_keywords;

    #[test]
    fn synthesizes_from_kebab_name_and_description() {
        let kw = synthesize_keywords(
            "test-driven-development",
            "Use when implementing any feature or bugfix, before writing implementation code",
        );
        // name tokens
        assert!(kw.contains(&"test".to_string()));
        assert!(kw.contains(&"driven".to_string()));
        assert!(kw.contains(&"development".to_string()));
        // description content words (stopwords filtered)
        assert!(kw.contains(&"implementing".to_string()));
        assert!(kw.contains(&"feature".to_string()));
        assert!(kw.contains(&"bugfix".to_string()));
        // stopwords excluded
        assert!(!kw.contains(&"use".to_string()));
        assert!(!kw.contains(&"any".to_string()));
        assert!(!kw.contains(&"the".to_string()));
        assert!(!kw.contains(&"or".to_string()));
        // dedupe
        let dups: std::collections::HashSet<_> = kw.iter().collect();
        assert_eq!(dups.len(), kw.len());
    }

    #[test]
    fn handles_empty_inputs() {
        assert_eq!(synthesize_keywords("", "").len(), 0);
    }

    #[test]
    fn caps_at_24_tokens() {
        let long = "alpha bravo charlie delta echo foxtrot golf hotel india juliet kilo lima mike november oscar papa quebec romeo sierra tango uniform victor whiskey xray yankee zulu";
        let kw = synthesize_keywords("an-id", long);
        assert!(kw.len() <= 24);
    }
}

#[cfg(test)]
mod ranks_tests {
    use super::{
        load_skills_from_global_and_project, skill_pool_summary, skill_to_pattern, SkillFile,
        SkillFrontmatter, SkillProvenance,
    };
    use crate::patterns::{keyword_scores, Pattern, PatternSolution};
    use std::collections::HashMap;
    use std::path::Path;

    fn make_pattern(pattern_id: &str, keywords: Vec<&str>) -> Pattern {
        Pattern {
            pattern_id: pattern_id.to_string(),
            title: pattern_id.to_string(),
            first_seen: String::new(),
            last_seen: String::new(),
            frequency: 0,
            severity: None,
            keywords: keywords.into_iter().map(|s| s.to_string()).collect(),
            tech_stack: Vec::new(),
            issue: None,
            solution: Some(PatternSolution {
                planner: String::new(),
                reviewer: String::new(),
            }),
            auto_apply: false,
            learned_from: None,
            used_count: 0,
            promoted_to: String::new(),
            promoted_at: String::new(),
            last_used_at: None,
            cited_in_pass: 0,
            cited_in_wip: 0,
            cited_by_stage: HashMap::new(),
        }
    }

    // T1.36: 400-line literal rewrite deferred -- behavior-preserving but
    // high-risk in one pass (34 elements built via `make_pattern(...)` calls).
    #[allow(clippy::vec_init_then_push)]
    fn synthetic_corpus() -> Vec<Pattern> {
        let mut patterns: Vec<Pattern> = Vec::with_capacity(34);
        // 14 Superpowers skills with curated keyword arrays (lockstep with the
        // overrides JSON; kept inline so the test does not depend on on-disk state).
        patterns.push(make_pattern(
            "brainstorming",
            vec![
                "brainstorm",
                "brainstorming",
                "ideation",
                "design",
                "alternatives",
                "options",
                "tradeoffs",
                "approach",
                "architecture",
                "decision",
                "explore",
                "exploratory",
                "discuss",
                "proposal",
                "rfc",
            ],
        ));
        patterns.push(make_pattern(
            "dispatching-parallel-agents",
            vec![
                "parallel",
                "agents",
                "dispatch",
                "concurrent",
                "fan-out",
                "subagent",
                "spawn",
                "multi-agent",
                "delegate",
                "orchestrate",
                "workers",
                "tasks",
                "background",
            ],
        ));
        patterns.push(make_pattern(
            "executing-plans",
            vec![
                "execute",
                "executing",
                "plan",
                "implementation",
                "implement",
                "build",
                "ship",
                "stepwise",
                "checklist",
                "follow",
                "carry-out",
                "construction",
            ],
        ));
        patterns.push(make_pattern(
            "finishing-a-development-branch",
            vec![
                "finish",
                "finishing",
                "branch",
                "merge",
                "pull-request",
                "pr",
                "complete",
                "wrap-up",
                "integrate",
                "review",
                "cleanup",
                "completion",
                "ready",
            ],
        ));
        patterns.push(make_pattern(
            "receiving-code-review",
            vec![
                "receive",
                "receiving",
                "review",
                "feedback",
                "comments",
                "incorporate",
                "address",
                "respond",
                "fix",
                "code-review",
                "reviewer",
                "patch",
            ],
        ));
        patterns.push(make_pattern(
            "requesting-code-review",
            vec![
                "request",
                "requesting",
                "review",
                "code-review",
                "pr",
                "pull-request",
                "reviewer",
                "ask",
                "submit",
                "feedback",
                "ready",
            ],
        ));
        patterns.push(make_pattern(
            "subagent-driven-development",
            vec![
                "subagent",
                "sub-agent",
                "delegation",
                "agent-driven",
                "spawn",
                "delegate",
                "task",
                "isolate",
                "context",
                "fresh-context",
                "compose",
            ],
        ));
        patterns.push(make_pattern(
            "systematic-debugging",
            vec![
                "debug",
                "debugging",
                "bug",
                "crash",
                "investigate",
                "investigation",
                "reproduce",
                "isolate",
                "root-cause",
                "trace",
                "fault",
                "diagnose",
                "failure",
                "intermittent",
                "regression",
            ],
        ));
        patterns.push(make_pattern(
            "test-driven-development",
            vec![
                "test",
                "tests",
                "testing",
                "tdd",
                "test-driven",
                "test-first",
                "implementation",
                "code",
                "feature",
                "bugfix",
                "failing-test",
                "red-green-refactor",
                "unit",
                "spec",
            ],
        ));
        patterns.push(make_pattern(
            "using-git-worktrees",
            vec![
                "worktree",
                "worktrees",
                "git",
                "branch",
                "checkout",
                "parallel",
                "isolated",
                "workspace",
                "switch",
                "concurrent",
            ],
        ));
        patterns.push(make_pattern(
            "using-superpowers",
            vec![
                "superpowers",
                "skill",
                "skills",
                "dispatcher",
                "master",
                "start",
                "begin",
                "establish",
                "find",
                "use",
            ],
        ));
        patterns.push(make_pattern(
            "verification-before-completion",
            vec![
                "verify",
                "verification",
                "complete",
                "completion",
                "done",
                "check",
                "validate",
                "before",
                "finish",
                "confirm",
                "asserts",
            ],
        ));
        patterns.push(make_pattern(
            "writing-plans",
            vec![
                "write",
                "writing",
                "plan",
                "planning",
                "draft",
                "spec",
                "design",
                "outline",
                "document",
                "structure",
                "blueprint",
            ],
        ));
        patterns.push(make_pattern(
            "writing-skills",
            vec![
                "write",
                "writing",
                "skill",
                "skills",
                "author",
                "create",
                "edit",
                "skill-md",
                "frontmatter",
                "verify",
            ],
        ));
        // 20 distractor patterns derived from existing CF-native pattern ids.
        patterns.push(make_pattern(
            "phantom-path-survives-targeted-cleanup-planner",
            vec![
                "phantom", "path", "survives", "targeted", "cleanup", "planner", "flowise", "json",
                "metadata",
            ],
        ));
        patterns.push(make_pattern(
            "phantom-path-survives-targeted-cleanup-reviewer",
            vec![
                "phantom", "path", "survives", "targeted", "cleanup", "reviewer", "flowise",
                "json", "metadata",
            ],
        ));
        patterns.push(make_pattern(
            "rust-struct-literal-field-explosion-planner",
            vec![
                "rust",
                "struct",
                "literal",
                "field",
                "explosion",
                "planner",
                "serde",
                "default",
                "compile",
            ],
        ));
        patterns.push(make_pattern(
            "rust-struct-literal-field-explosion-reviewer",
            vec![
                "rust",
                "struct",
                "literal",
                "field",
                "explosion",
                "reviewer",
                "serde",
                "default",
                "compile",
            ],
        ));
        patterns.push(make_pattern(
            "broken-venv-symlinks-platform-mismatch-planner",
            vec![
                "broken", "venv", "symlink", "platform", "mismatch", "planner", "uv", "cpython",
                "macos",
            ],
        ));
        patterns.push(make_pattern(
            "broken-venv-symlinks-platform-mismatch-reviewer",
            vec![
                "broken", "venv", "symlink", "platform", "mismatch", "reviewer", "uv", "cpython",
                "macos",
            ],
        ));
        patterns.push(make_pattern(
            "python-venv-uv-symlink-broken-planner",
            vec![
                "python", "venv", "uv", "symlink", "broken", "planner", "fastapi", "runtime",
            ],
        ));
        patterns.push(make_pattern(
            "python-venv-uv-symlink-broken-reviewer",
            vec![
                "python", "venv", "uv", "symlink", "broken", "reviewer", "fastapi", "runtime",
            ],
        ));
        patterns.push(make_pattern(
            "broken-venv-symlink-uv-python-planner",
            vec![
                "broken", "venv", "symlink", "uv", "python", "planner", "aarch64",
            ],
        ));
        patterns.push(make_pattern(
            "broken-venv-symlink-uv-python-reviewer",
            vec![
                "broken", "venv", "symlink", "uv", "python", "reviewer", "aarch64",
            ],
        ));
        patterns.push(make_pattern(
            "dict-get-default-fails-on-explicit-null-planner",
            vec![
                "dict",
                "get",
                "default",
                "fails",
                "explicit",
                "null",
                "planner",
                "python",
                "typeerror",
            ],
        ));
        patterns.push(make_pattern(
            "dict-get-default-fails-on-explicit-null-reviewer",
            vec![
                "dict",
                "get",
                "default",
                "fails",
                "explicit",
                "null",
                "reviewer",
                "python",
                "typeerror",
            ],
        ));
        patterns.push(make_pattern(
            "broken-venv-cross-platform-planner",
            vec![
                "broken", "venv", "cross", "platform", "planner", "python", "exit", "127",
            ],
        ));
        patterns.push(make_pattern(
            "broken-venv-cross-platform-reviewer",
            vec![
                "broken", "venv", "cross", "platform", "reviewer", "python", "exit", "127",
            ],
        ));
        patterns.push(make_pattern(
            "keyword-missing-hyphenated-compound-adjective-planner",
            vec![
                "keyword",
                "missing",
                "hyphenated",
                "compound",
                "adjective",
                "planner",
                "substring",
                "threshold",
            ],
        ));
        patterns.push(make_pattern(
            "keyword-missing-hyphenated-compound-adjective-reviewer",
            vec![
                "keyword",
                "missing",
                "hyphenated",
                "compound",
                "adjective",
                "reviewer",
                "substring",
                "threshold",
            ],
        ));
        patterns.push(make_pattern(
            "compute-once-cross-cutting-embedding-reviewer",
            vec![
                "compute",
                "once",
                "cross",
                "cutting",
                "embedding",
                "reviewer",
                "ollama",
                "performance",
            ],
        ));
        patterns.push(make_pattern(
            "docker-healthcheck-tcp-fallback-planner",
            vec![
                "docker",
                "healthcheck",
                "tcp",
                "fallback",
                "planner",
                "container",
                "compose",
            ],
        ));
        patterns.push(make_pattern(
            "csp-wasm-unsafe-eval-required-planner",
            vec![
                "csp", "wasm", "unsafe", "eval", "required", "planner", "argon2", "caddy",
            ],
        ));
        patterns.push(make_pattern(
            "utc-timestamp-missing-z-suffix-reviewer",
            vec![
                "utc",
                "timestamp",
                "missing",
                "suffix",
                "reviewer",
                "date",
                "browser",
                "frontend",
            ],
        ));
        patterns
    }

    fn top_5_ids(patterns: &[Pattern], task_desc: &str) -> Vec<String> {
        let mut scored = keyword_scores(patterns, task_desc, &[]);
        scored.sort_by_key(|b| std::cmp::Reverse(b.1));
        scored
            .into_iter()
            .take(5)
            .map(|(idx, _)| patterns[idx].pattern_id.clone())
            .collect()
    }

    #[test]
    fn ranks_test_driven_development_for_tdd_task() {
        let patterns = synthetic_corpus();
        let task = "Implement the new auth feature using TDD: write failing unit tests first then implementation code for the bugfix";
        let top = top_5_ids(&patterns, task);
        assert!(
            top.iter().any(|id| id == "test-driven-development"),
            "expected test-driven-development in top 5, got {:?}",
            top
        );
    }

    #[test]
    fn ranks_systematic_debugging_for_bug_task() {
        let patterns = synthetic_corpus();
        let task = "Debug intermittent crash in the payment processor: reproduce the bug, isolate the failure, and diagnose the root-cause regression";
        let top = top_5_ids(&patterns, task);
        assert!(
            top.iter().any(|id| id == "systematic-debugging"),
            "expected systematic-debugging in top 5, got {:?}",
            top
        );
    }

    #[test]
    fn ranks_brainstorming_for_design_task() {
        let patterns = synthetic_corpus();
        let task = "Brainstorm design alternatives and tradeoffs for the new caching layer architecture; explore options before writing the RFC";
        let top = top_5_ids(&patterns, task);
        assert!(
            top.iter().any(|id| id == "brainstorming"),
            "expected brainstorming in top 5, got {:?}",
            top
        );
    }

    #[test]
    fn skill_to_pattern_preserves_frontmatter_cf_keywords_without_synthesizing() {
        let sf = SkillFile {
            dir_name: "some-non-superpowers-id".to_string(),
            body: String::new(),
            frontmatter: SkillFrontmatter {
                name: "some-non-superpowers-id".to_string(),
                description: "This description contains many synthesizable tokens including bugfix feature implementation that must NOT appear in the merged keyword vector".to_string(),
                cf_stage: "planner".to_string(),
                cf_citations_pass: 0,
                cf_citations_wip: 0,
                cf_last_used: None,
                cf_frequency: 0,
                cf_severity: None,
                cf_keywords: vec![
                    "frontmatter-only-tok-a".to_string(),
                    "frontmatter-only-tok-b".to_string(),
                ],
            },
            provenance: SkillProvenance::GlobalFoundry,
        };
        let p = skill_to_pattern(sf);
        assert_eq!(
            p.keywords,
            vec![
                "frontmatter-only-tok-a".to_string(),
                "frontmatter-only-tok-b".to_string(),
            ],
            "frontmatter cf-keywords must not be augmented by synthesized tokens when overrides absent"
        );
        assert!(
            !p.keywords
                .iter()
                .any(|k| k == "bugfix" || k == "feature" || k == "implementation"),
            "synthesized tokens must not appear when cf-keywords is non-empty and no override matches pattern_id"
        );
    }

    // T2.4 tests: merged auto-retrieval pool + summary line.

    fn write_global_skill_into(home_skills_dir: &Path, dir: &str, name: &str, desc: &str) {
        let topic = home_skills_dir.join(dir);
        std::fs::create_dir_all(&topic).unwrap();
        let body = format!(
            "---\nname: {}\ndescription: {}\nmetadata:\n  cf-stage: planner\n---\n\nbody\n",
            name, desc
        );
        std::fs::write(topic.join("SKILL.md"), body).unwrap();
    }

    fn with_pinned_home<F: FnOnce(&Path)>(f: F) {
        // Pin HOME to a tempdir so resolve_skills_dir("~/.foundry/skills") and
        // the ancestor walk are both scoped to a sandbox. Critical to avoid
        // reading the user's real ~/.foundry/skills/ during tests.
        let tmp_home = tempfile::tempdir().unwrap();
        let prev_home = std::env::var("HOME").ok();
        std::env::set_var("HOME", tmp_home.path());
        let result = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| f(tmp_home.path())));
        match prev_home {
            Some(h) => std::env::set_var("HOME", h),
            None => std::env::remove_var("HOME"),
        }
        if let Err(e) = result {
            std::panic::resume_unwind(e);
        }
    }

    #[serial_test::serial(home_env)]
    #[test]
    fn merged_pool_dedupes_global_winning_over_claude_project() {
        with_pinned_home(|home| {
            let home_skills = home.join(".foundry").join("skills");
            write_global_skill_into(&home_skills, "foo", "foo", "global foo");

            // Project sits INSIDE the pinned HOME so the ancestor walk is bounded.
            let project = tempfile::tempdir_in(home).unwrap();
            let topic = project.path().join(".claude").join("skills").join("foo");
            std::fs::create_dir_all(&topic).unwrap();
            std::fs::write(
                topic.join("SKILL.md"),
                "---\nname: foo\ndescription: project foo\n---\n\nbody\n",
            )
            .unwrap();

            let merged = load_skills_from_global_and_project(project.path());
            let foos: Vec<&SkillFile> = merged.iter().filter(|s| s.dir_name == "foo").collect();
            assert_eq!(
                foos.len(),
                1,
                "expected exactly one foo entry after dedup, got {:?}",
                foos
            );
            assert_eq!(
                foos[0].provenance,
                SkillProvenance::GlobalFoundry,
                "global must win over .claude/skills/ on name collision"
            );
        });
    }

    #[serial_test::serial(home_env)]
    #[test]
    fn merged_pool_includes_distinct_foreign_skills() {
        with_pinned_home(|home| {
            let project = tempfile::tempdir_in(home).unwrap();
            std::fs::write(project.path().join("AGENTS.md"), "# AGENTS rules\n").unwrap();
            let merged = load_skills_from_global_and_project(project.path());
            let agents: Vec<&SkillFile> = merged
                .iter()
                .filter(|s| s.provenance == SkillProvenance::AgentsMd)
                .collect();
            assert!(
                !agents.is_empty(),
                "expected merged pool to include an AgentsMd-sourced skill, got {:?}",
                merged
            );
        });
    }

    #[serial_test::serial(home_env)]
    #[test]
    fn merged_pool_does_not_walk_when_project_has_no_foreign_skills() {
        with_pinned_home(|home| {
            // Pin HOME to an empty dir so load_skills_from_global() returns
            // zero entries.
            let project = tempfile::tempdir_in(home).unwrap();
            let merged = load_skills_from_global_and_project(project.path());
            assert!(
                merged.is_empty(),
                "merged pool should be empty when neither global nor project carry skills, got {:?}",
                merged
            );
        });
    }

    #[test]
    fn skill_pool_summary_renders_zero() {
        assert_eq!(skill_pool_summary(&[]), "Skill pool: 0 total");
    }

    #[test]
    fn skill_pool_summary_renders_mixed() {
        let mk = |prov: SkillProvenance| SkillFile {
            dir_name: "x".to_string(),
            frontmatter: SkillFrontmatter::default(),
            body: String::new(),
            provenance: prov,
        };
        let pool = vec![
            mk(SkillProvenance::GlobalFoundry),
            mk(SkillProvenance::GlobalFoundry),
            mk(SkillProvenance::ClaudeProject),
            mk(SkillProvenance::AgentsMd),
        ];
        let s = skill_pool_summary(&pool);
        assert_eq!(
            s,
            "Skill pool: 2 global, 1 from .claude/skills/, 1 from AGENTS.md = 4 total"
        );
    }

    #[test]
    fn skill_pool_summary_omits_empty_buckets() {
        let mk = || SkillFile {
            dir_name: "x".to_string(),
            frontmatter: SkillFrontmatter::default(),
            body: String::new(),
            provenance: SkillProvenance::GlobalFoundry,
        };
        let pool = vec![mk(), mk(), mk()];
        let s = skill_pool_summary(&pool);
        assert_eq!(s, "Skill pool: 3 global = 3 total");
    }
}
