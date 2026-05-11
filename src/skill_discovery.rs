use std::path::{Path, PathBuf};

use crate::skills::{parse_skill_file, SkillFrontmatter};

/// Source of a discovered external skill (a skill or instruction file authored
/// for another AI tool that CF reads in read-only mode).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum SkillSource {
    /// `<project>/AGENTS.md` or `<ancestor>/AGENTS.md` (Linux Foundation standard).
    AgentsMd,
    /// `<project>/.cursorrules` (legacy Cursor rule file).
    CursorRules,
    /// `<project>/.claude/skills/<topic>/SKILL.md` (Anthropic Claude Code).
    ClaudeProjectSkill,
}

impl SkillSource {
    /// Short label embedded in the planner prompt as `source: <label>` so the
    /// agent can see provenance.
    pub fn prompt_label(self) -> &'static str {
        match self {
            Self::AgentsMd => "agents-md",
            Self::CursorRules => "cursor",
            Self::ClaudeProjectSkill => "claude-project",
        }
    }

    /// Human-readable label for UI.
    pub fn ui_label(self) -> &'static str {
        match self {
            Self::AgentsMd => "AGENTS.md",
            Self::CursorRules => ".cursorrules",
            Self::ClaudeProjectSkill => ".claude/skills/",
        }
    }

    /// Higher number = higher precedence when two discovered skills share a
    /// derived_name. Mirrors the precedence rule documented in T1.27.
    pub fn precedence(self) -> u8 {
        match self {
            Self::ClaudeProjectSkill => 3,
            Self::AgentsMd => 2,
            Self::CursorRules => 1,
        }
    }
}

/// A single skill or instruction file discovered outside CF's native
/// `~/.foundry/skills/` directory and outside plugin-bundled
/// `extensions/<name>/skills/<topic>/SKILL.md`.
#[derive(Debug, Clone)]
pub struct DiscoveredSkill {
    pub source: SkillSource,
    pub path: PathBuf,
    pub body: String,
    pub derived_name: String,
    /// Parsed SKILL.md frontmatter when the source carries one
    /// (`ClaudeProjectSkill`). AGENTS.md and .cursorrules have no
    /// frontmatter so this is always `None` for them. Currently consumed
    /// by `skills::discovered_to_skill_file`, which is wired up for future
    /// matcher integration but not yet on the prompt-injection path.
    #[allow(dead_code)]
    pub frontmatter: Option<SkillFrontmatter>,
}

/// Walk the project directory looking for external skill files authored for
/// other AI tools. Discovery is read-only -- CF never writes back to any of
/// these paths.
///
/// Three sources are scanned:
///  1. `<project>/.claude/skills/<topic>/SKILL.md` (project root only -- the
///     Claude Code convention is project-local).
///  2. `<project>/AGENTS.md`, plus each ancestor directory up to (and
///     including) the user's home directory.
///  3. `<project>/.cursorrules` (project root only).
///
/// Results are returned in stable order (claude-project skills first, then the
/// project AGENTS.md, then ancestor AGENTS.md walking outward, then
/// .cursorrules) so the UI surface and the precedence resolver are
/// deterministic.
pub fn discover_external_skills(project_dir: &Path) -> Vec<DiscoveredSkill> {
    let mut out = Vec::new();

    // 1. .claude/skills/<topic>/SKILL.md (project-local only)
    let claude_skills_dir = project_dir.join(".claude").join("skills");
    if claude_skills_dir.is_dir() {
        if let Ok(entries) = std::fs::read_dir(&claude_skills_dir) {
            let mut topic_dirs: Vec<PathBuf> = entries
                .flatten()
                .map(|e| e.path())
                .filter(|p| p.is_dir())
                .collect();
            topic_dirs.sort();
            for topic_dir in topic_dirs {
                let skill_md = topic_dir.join("SKILL.md");
                if !skill_md.is_file() {
                    continue;
                }
                let content = match std::fs::read_to_string(&skill_md) {
                    Ok(c) => c,
                    Err(e) => {
                        eprintln!(
                            "warning: failed to read {}: {}",
                            skill_md.display(),
                            e
                        );
                        continue;
                    }
                };
                let topic_name = topic_dir
                    .file_name()
                    .and_then(|n| n.to_str())
                    .unwrap_or("")
                    .to_string();
                let parsed = parse_skill_file(&topic_name, &content).ok();
                let body = parsed
                    .as_ref()
                    .map(|sf| sf.body.clone())
                    .unwrap_or_else(|| content.clone());
                let derived_name = parsed
                    .as_ref()
                    .map(|sf| {
                        if !sf.frontmatter.name.is_empty() {
                            sf.frontmatter.name.clone()
                        } else {
                            topic_name.clone()
                        }
                    })
                    .unwrap_or_else(|| topic_name.clone());
                let frontmatter = parsed.map(|sf| sf.frontmatter);
                out.push(DiscoveredSkill {
                    source: SkillSource::ClaudeProjectSkill,
                    path: skill_md,
                    body,
                    derived_name,
                    frontmatter,
                });
            }
        }
    }

    // 2. AGENTS.md -- project root + each ancestor up to (and including) HOME.
    let canonical = project_dir
        .canonicalize()
        .unwrap_or_else(|_| project_dir.to_path_buf());
    let home = crate::utils::home_dir();
    let mut agents_md_paths: Vec<PathBuf> = Vec::new();
    let mut cur: Option<&Path> = Some(canonical.as_path());
    while let Some(dir) = cur {
        let candidate = dir.join("AGENTS.md");
        if candidate.is_file() {
            agents_md_paths.push(candidate);
        }
        // Stop at HOME (inclusive of HOME) to avoid reading global rules
        // outside the user's home directory.
        if let Some(h) = home.as_ref() {
            if dir == h.as_path() {
                break;
            }
        }
        cur = dir.parent();
    }
    for path in agents_md_paths {
        let content = match std::fs::read_to_string(&path) {
            Ok(c) => c,
            Err(e) => {
                eprintln!("warning: failed to read {}: {}", path.display(), e);
                continue;
            }
        };
        // Derive a stable name from the parent dir so the user sees which
        // AGENTS.md is which when multiple ancestors carry one.
        let parent_label = path
            .parent()
            .and_then(|p| p.file_name())
            .and_then(|n| n.to_str())
            .unwrap_or("root")
            .to_string();
        let derived_name = if parent_label == "root" || parent_label.is_empty() {
            "agents-md".to_string()
        } else {
            format!("agents-md-{}", parent_label)
        };
        out.push(DiscoveredSkill {
            source: SkillSource::AgentsMd,
            path,
            body: content,
            derived_name,
            frontmatter: None,
        });
    }

    // 3. .cursorrules (project root only).
    let cursorrules = project_dir.join(".cursorrules");
    if cursorrules.is_file() {
        match std::fs::read_to_string(&cursorrules) {
            Ok(content) => {
                out.push(DiscoveredSkill {
                    source: SkillSource::CursorRules,
                    path: cursorrules,
                    body: content,
                    derived_name: "cursorrules".to_string(),
                    frontmatter: None,
                });
            }
            Err(e) => eprintln!(
                "warning: failed to read {}: {}",
                cursorrules.display(),
                e
            ),
        }
    }

    out
}

/// Discover external skills and filter to only those the user has opted in
/// via the `external_skills_enabled` map in `.foundry.json`. Returns an empty
/// vec when no enabled skills are present, so callers can short-circuit
/// without triggering directory walks beyond the initial discovery.
///
/// This is the entrypoint the build/planning pipeline uses to inject external
/// skills into the planner/reviewer prompt context.
pub fn load_enabled_external_skills(
    project_dir: &Path,
    enabled: &std::collections::HashMap<String, bool>,
) -> Vec<DiscoveredSkill> {
    if enabled.is_empty() {
        return Vec::new();
    }
    let all = discover_external_skills(project_dir);
    all.into_iter()
        .filter(|d| {
            let key = d.path.to_string_lossy().into_owned();
            enabled.get(&key).copied().unwrap_or(false)
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn discovers_no_skills_in_empty_project() {
        let tmp = tempfile::tempdir().unwrap();
        let result = discover_external_skills(tmp.path());
        assert!(
            result.is_empty(),
            "empty project should produce no discovered skills, got {:?}",
            result
        );
    }

    #[test]
    fn discovers_agents_md_in_project_root() {
        let tmp = tempfile::tempdir().unwrap();
        std::fs::write(tmp.path().join("AGENTS.md"), "# Agents rules\n\nUse X.").unwrap();
        let result = discover_external_skills(tmp.path());
        let agents: Vec<&DiscoveredSkill> = result
            .iter()
            .filter(|d| d.source == SkillSource::AgentsMd)
            .collect();
        assert_eq!(agents.len(), 1, "expected one AGENTS.md, got {:?}", result);
        assert!(agents[0].body.contains("Agents rules"));
    }

    #[test]
    fn discovers_cursorrules_in_project_root() {
        let tmp = tempfile::tempdir().unwrap();
        std::fs::write(tmp.path().join(".cursorrules"), "Rule one\nRule two\n").unwrap();
        let result = discover_external_skills(tmp.path());
        let cursor: Vec<&DiscoveredSkill> = result
            .iter()
            .filter(|d| d.source == SkillSource::CursorRules)
            .collect();
        assert_eq!(cursor.len(), 1);
        assert!(cursor[0].body.contains("Rule one"));
        assert_eq!(cursor[0].derived_name, "cursorrules");
    }

    #[test]
    fn discovers_claude_project_skills() {
        let tmp = tempfile::tempdir().unwrap();
        let skills_root = tmp.path().join(".claude").join("skills");
        let topic_a = skills_root.join("audit-flowise");
        let topic_b = skills_root.join("build-flowise");
        std::fs::create_dir_all(&topic_a).unwrap();
        std::fs::create_dir_all(&topic_b).unwrap();
        std::fs::write(
            topic_a.join("SKILL.md"),
            "---\nname: audit-flowise\ndescription: Audit a flow.\n---\n\nDo audit.\n",
        )
        .unwrap();
        // Topic with non-standard frontmatter (FlowiseKit-style fields ignored).
        std::fs::write(
            topic_b.join("SKILL.md"),
            "---\nname: build-flowise\ndescription: Build a flow.\ncontext: fork\nallowed-tools:\n  - Read\nargument-hint: \"path\"\n---\n\nBuild it.\n",
        )
        .unwrap();

        let result = discover_external_skills(tmp.path());
        let claude: Vec<&DiscoveredSkill> = result
            .iter()
            .filter(|d| d.source == SkillSource::ClaudeProjectSkill)
            .collect();
        assert_eq!(claude.len(), 2, "expected 2 claude skills, got {:?}", result);
        let names: Vec<&str> = claude.iter().map(|d| d.derived_name.as_str()).collect();
        assert!(names.contains(&"audit-flowise"));
        assert!(names.contains(&"build-flowise"));
        // The body should be the parsed body (without frontmatter).
        let audit = claude
            .iter()
            .find(|d| d.derived_name == "audit-flowise")
            .unwrap();
        assert!(audit.body.contains("Do audit"));
        assert!(!audit.body.contains("description:"));
        assert!(audit.frontmatter.is_some());
    }

    #[test]
    fn claude_project_skills_use_topic_dir_as_fallback_name() {
        let tmp = tempfile::tempdir().unwrap();
        let topic = tmp.path().join(".claude").join("skills").join("topic-x");
        std::fs::create_dir_all(&topic).unwrap();
        // Body without frontmatter -- parser fails, body is raw content,
        // derived_name falls back to the topic dir name.
        std::fs::write(topic.join("SKILL.md"), "Just plain markdown body.\n").unwrap();
        let result = discover_external_skills(tmp.path());
        let claude: Vec<&DiscoveredSkill> = result
            .iter()
            .filter(|d| d.source == SkillSource::ClaudeProjectSkill)
            .collect();
        assert_eq!(claude.len(), 1);
        assert_eq!(claude[0].derived_name, "topic-x");
        assert!(claude[0].body.contains("Just plain"));
    }

    #[test]
    fn claude_project_skills_does_not_recurse_into_ancestors() {
        let tmp = tempfile::tempdir().unwrap();
        // .claude/skills only at the ROOT, not at the child "project_dir".
        let parent_topic = tmp.path().join(".claude").join("skills").join("parent-skill");
        std::fs::create_dir_all(&parent_topic).unwrap();
        std::fs::write(
            parent_topic.join("SKILL.md"),
            "---\nname: parent-skill\ndescription: x\n---\n\nbody\n",
        )
        .unwrap();
        let child_dir = tmp.path().join("child");
        std::fs::create_dir_all(&child_dir).unwrap();

        let result = discover_external_skills(&child_dir);
        let claude_count = result
            .iter()
            .filter(|d| d.source == SkillSource::ClaudeProjectSkill)
            .count();
        assert_eq!(
            claude_count, 0,
            "ancestor walk for .claude/skills/ MUST NOT happen, got {:?}",
            result
        );
    }

    #[test]
    fn precedence_orders_correctly() {
        assert!(
            SkillSource::ClaudeProjectSkill.precedence()
                > SkillSource::AgentsMd.precedence()
        );
        assert!(
            SkillSource::AgentsMd.precedence() > SkillSource::CursorRules.precedence()
        );
    }

    #[test]
    fn load_enabled_returns_empty_when_no_opt_ins() {
        let tmp = tempfile::tempdir().unwrap();
        std::fs::write(tmp.path().join("AGENTS.md"), "rules").unwrap();
        let enabled: std::collections::HashMap<String, bool> =
            std::collections::HashMap::new();
        let result = load_enabled_external_skills(tmp.path(), &enabled);
        assert!(result.is_empty());
    }

    #[test]
    fn load_enabled_includes_only_opted_in_paths() {
        let tmp = tempfile::tempdir().unwrap();
        std::fs::write(tmp.path().join("AGENTS.md"), "agents body").unwrap();
        std::fs::write(tmp.path().join(".cursorrules"), "cursor body").unwrap();
        // Build the opt-in keys from the actual discovered paths so this test
        // is robust to symlink resolution (macOS canonicalizes /var ->
        // /private/var, etc.).
        let discovered = discover_external_skills(tmp.path());
        let mut enabled: std::collections::HashMap<String, bool> =
            std::collections::HashMap::new();
        for d in &discovered {
            let key = d.path.to_string_lossy().into_owned();
            let v = matches!(d.source, SkillSource::AgentsMd);
            enabled.insert(key, v);
        }
        let result = load_enabled_external_skills(tmp.path(), &enabled);
        assert_eq!(
            result.len(),
            1,
            "expected only AgentsMd to be enabled, got {:?}",
            result
        );
        assert_eq!(result[0].source, SkillSource::AgentsMd);
    }

    #[test]
    fn prompt_labels_are_stable() {
        // The labels are persisted in prompts the agent reads -- changing them
        // would break any docs/tests grepping for them.
        assert_eq!(SkillSource::AgentsMd.prompt_label(), "agents-md");
        assert_eq!(SkillSource::CursorRules.prompt_label(), "cursor");
        assert_eq!(
            SkillSource::ClaudeProjectSkill.prompt_label(),
            "claude-project"
        );
    }

    #[test]
    fn discovers_all_four_flowise_kit_skills_in_real_scaffold() {
        // Smoke test against the canonical FlowiseKit scaffold checked into
        // the repo. T1.27 verification spec: "launch CF in
        // scaffolds/flowise-agentflow-portable-kit/, confirm all 4 FlowiseKit
        // skills (audit-flowise, build-flowise, promote-flowise,
        // repair-flowise) appear under External Skills with the
        // .claude/skills/ source label".
        let scaffold = std::env::current_dir()
            .unwrap()
            .join("scaffolds")
            .join("flowise-agentflow-portable-kit");
        if !scaffold.join(".claude").join("skills").is_dir() {
            // Scaffold not present in this build context (e.g., distributed
            // binary). Skip rather than fail.
            return;
        }
        let result = discover_external_skills(&scaffold);
        let claude_skills: Vec<&DiscoveredSkill> = result
            .iter()
            .filter(|d| d.source == SkillSource::ClaudeProjectSkill)
            .collect();
        let names: Vec<&str> = claude_skills
            .iter()
            .map(|d| d.derived_name.as_str())
            .collect();
        for expected in &[
            "audit-flowise",
            "build-flowise",
            "promote-flowise",
            "repair-flowise",
        ] {
            assert!(
                names.contains(expected),
                "expected to discover {} in FlowiseKit scaffold, got names {:?}",
                expected,
                names
            );
        }
    }
}
