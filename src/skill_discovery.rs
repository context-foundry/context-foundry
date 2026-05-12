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
    /// `<project>/.github/copilot-instructions.md` (GitHub Copilot custom instructions).
    CopilotInstructions,
}

impl SkillSource {
    /// Short label embedded in the planner prompt as `source: <label>` so the
    /// agent can see provenance.
    pub fn prompt_label(self) -> &'static str {
        match self {
            Self::AgentsMd => "agents-md",
            Self::CursorRules => "cursor",
            Self::ClaudeProjectSkill => "claude-project",
            Self::CopilotInstructions => "copilot",
        }
    }

    /// Human-readable label for UI.
    pub fn ui_label(self) -> &'static str {
        match self {
            Self::AgentsMd => "AGENTS.md",
            Self::CursorRules => ".cursorrules",
            Self::ClaudeProjectSkill => ".claude/skills/",
            Self::CopilotInstructions => ".github/copilot-instructions.md",
        }
    }

    /// Higher number = higher precedence when two discovered skills share a
    /// derived_name. Mirrors the precedence rule documented in T1.27.
    pub fn precedence(self) -> u8 {
        match self {
            Self::ClaudeProjectSkill => 3,
            Self::AgentsMd => 2,
            Self::CursorRules => 1,
            Self::CopilotInstructions => 2,
        }
    }
}

/// A single skill or instruction file discovered outside CF's native
/// `~/.foundry/skills/` directory and outside plugin-bundled
/// `plugins/<name>/skills/<topic>/SKILL.md`.
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
/// Four sources are scanned:
///  1. `<project>/.claude/skills/<topic>/SKILL.md` (project root only -- the
///     Claude Code convention is project-local).
///  2. `<project>/AGENTS.md`, then `<project>/.github/copilot-instructions.md`
///     (Copilot is project-local only and is inserted between the project-root
///     AGENTS.md and the ancestor AGENTS.md walk so the on-screen order is
///     "closest first"), then each ancestor directory's AGENTS.md up to (and
///     including) the user's home directory.
///  3. `<project>/.cursorrules` (project root only).
///
/// Results are returned in stable order (claude-project skills first, then the
/// project AGENTS.md, then `.github/copilot-instructions.md`, then ancestor
/// AGENTS.md walking outward, then .cursorrules) so the UI surface and the
/// precedence resolver are deterministic.
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

    // 2. AGENTS.md split: project root first, then Copilot, then ancestor
    //    AGENTS.md (closest first, stop at HOME inclusive).
    let canonical = project_dir
        .canonicalize()
        .unwrap_or_else(|_| project_dir.to_path_buf());
    let home = crate::utils::home_dir();

    let push_agents_md = |out: &mut Vec<DiscoveredSkill>, path: PathBuf| {
        let content = match std::fs::read_to_string(&path) {
            Ok(c) => c,
            Err(e) => {
                eprintln!("warning: failed to read {}: {}", path.display(), e);
                return;
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
    };

    // 2a. Project-root AGENTS.md.
    let project_agents_md = canonical.join("AGENTS.md");
    if project_agents_md.is_file() {
        push_agents_md(&mut out, project_agents_md);
    }

    // 2b. .github/copilot-instructions.md (project root only, no ancestor walk).
    let copilot_path = project_dir.join(".github").join("copilot-instructions.md");
    if copilot_path.is_file() {
        match std::fs::read_to_string(&copilot_path) {
            Ok(content) => out.push(DiscoveredSkill {
                source: SkillSource::CopilotInstructions,
                path: copilot_path,
                body: content,
                derived_name: "copilot-instructions".to_string(),
                frontmatter: None,
            }),
            Err(e) => eprintln!(
                "warning: failed to read {}: {}",
                copilot_path.display(),
                e
            ),
        }
    }

    // 2c. Ancestor AGENTS.md (closest first, stop at HOME inclusive).
    // Guard: when project_dir IS home, 2a already wrote home/AGENTS.md; skip
    // the ancestor walk entirely to avoid escaping out of HOME and reading
    // global AGENTS.md outside the user's home directory.
    let starts_at_home = home
        .as_ref()
        .map(|h| canonical.as_path() == h.as_path())
        .unwrap_or(false);
    if !starts_at_home {
        let mut cur: Option<&Path> = canonical.parent();
        while let Some(dir) = cur {
            let candidate = dir.join("AGENTS.md");
            if candidate.is_file() {
                push_agents_md(&mut out, candidate);
            }
            if let Some(h) = home.as_ref() {
                if dir == h.as_path() {
                    break;
                }
            }
            cur = dir.parent();
        }
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

    #[test]
    fn discovers_copilot_instructions_in_project_root() {
        let tmp = tempfile::tempdir().unwrap();
        let github_dir = tmp.path().join(".github");
        std::fs::create_dir_all(&github_dir).unwrap();
        std::fs::write(
            github_dir.join("copilot-instructions.md"),
            "Use Rust. Prefer anyhow.",
        )
        .unwrap();
        let result = discover_external_skills(tmp.path());
        let copilot: Vec<&DiscoveredSkill> = result
            .iter()
            .filter(|d| d.source == SkillSource::CopilotInstructions)
            .collect();
        assert_eq!(
            copilot.len(),
            1,
            "expected one Copilot entry, got {:?}",
            result
        );
        assert!(copilot[0].body.contains("Prefer anyhow"));
        assert_eq!(copilot[0].derived_name, "copilot-instructions");
        assert!(copilot[0].frontmatter.is_none());
    }

    #[test]
    fn copilot_instructions_does_not_recurse_into_ancestors() {
        let tmp = tempfile::tempdir().unwrap();
        // .github/copilot-instructions.md only at the ROOT, not at the child
        // "project_dir".
        let github_dir = tmp.path().join(".github");
        std::fs::create_dir_all(&github_dir).unwrap();
        std::fs::write(
            github_dir.join("copilot-instructions.md"),
            "Use anyhow.",
        )
        .unwrap();
        let child = tmp.path().join("child");
        std::fs::create_dir_all(&child).unwrap();

        let result = discover_external_skills(&child);
        let copilot_count = result
            .iter()
            .filter(|d| d.source == SkillSource::CopilotInstructions)
            .count();
        assert_eq!(
            copilot_count, 0,
            "ancestor walk for .github/copilot-instructions.md MUST NOT happen, got {:?}",
            result
        );
    }

    #[test]
    fn copilot_precedence_ties_agents_md_and_exceeds_cursorrules() {
        assert_eq!(
            SkillSource::CopilotInstructions.precedence(),
            SkillSource::AgentsMd.precedence()
        );
        assert!(
            SkillSource::CopilotInstructions.precedence()
                > SkillSource::CursorRules.precedence()
        );
        assert!(
            SkillSource::ClaudeProjectSkill.precedence()
                > SkillSource::CopilotInstructions.precedence()
        );
    }

    #[test]
    fn copilot_appears_between_project_and_ancestor_agents_md() {
        let tmp = tempfile::tempdir().unwrap();
        // Layout: tmp/AGENTS.md (ancestor) + tmp/child/AGENTS.md (project) +
        // tmp/child/.github/copilot-instructions.md.
        std::fs::write(tmp.path().join("AGENTS.md"), "# ancestor agents").unwrap();
        let child = tmp.path().join("child");
        std::fs::create_dir_all(&child).unwrap();
        std::fs::write(child.join("AGENTS.md"), "# child agents").unwrap();
        let github_dir = child.join(".github");
        std::fs::create_dir_all(&github_dir).unwrap();
        std::fs::write(
            github_dir.join("copilot-instructions.md"),
            "# copilot",
        )
        .unwrap();

        let result = discover_external_skills(&child);
        let agents_idxs: Vec<usize> = result
            .iter()
            .enumerate()
            .filter(|(_, d)| d.source == SkillSource::AgentsMd)
            .map(|(i, _)| i)
            .collect();
        assert_eq!(
            agents_idxs.len(),
            2,
            "expected exactly two AGENTS.md entries, got {:?}",
            result
        );
        let copilot_idx = result
            .iter()
            .position(|d| d.source == SkillSource::CopilotInstructions)
            .expect("expected one Copilot entry");
        assert!(
            agents_idxs[0] < copilot_idx,
            "project AGENTS.md should precede Copilot, got result={:?}",
            result
        );
        assert!(
            copilot_idx < agents_idxs[1],
            "Copilot should precede ancestor AGENTS.md, got result={:?}",
            result
        );
    }

    #[test]
    fn copilot_appears_between_project_agents_md_and_cursorrules_in_discovery_order() {
        let tmp = tempfile::tempdir().unwrap();
        std::fs::write(tmp.path().join("AGENTS.md"), "# agents").unwrap();
        let github_dir = tmp.path().join(".github");
        std::fs::create_dir_all(&github_dir).unwrap();
        std::fs::write(
            github_dir.join("copilot-instructions.md"),
            "# copilot",
        )
        .unwrap();
        std::fs::write(tmp.path().join(".cursorrules"), "rules").unwrap();

        let result = discover_external_skills(tmp.path());
        let agents_idx = result
            .iter()
            .position(|d| d.source == SkillSource::AgentsMd)
            .expect("expected AGENTS.md");
        let copilot_idx = result
            .iter()
            .position(|d| d.source == SkillSource::CopilotInstructions)
            .expect("expected Copilot");
        let cursor_idx = result
            .iter()
            .position(|d| d.source == SkillSource::CursorRules)
            .expect("expected .cursorrules");
        assert!(
            agents_idx < copilot_idx && copilot_idx < cursor_idx,
            "expected AGENTS.md < Copilot < .cursorrules, got result={:?}",
            result
        );
    }

    #[test]
    fn prompt_labels_include_copilot() {
        assert_eq!(
            SkillSource::CopilotInstructions.prompt_label(),
            "copilot"
        );
        assert_eq!(
            SkillSource::CopilotInstructions.ui_label(),
            ".github/copilot-instructions.md"
        );
    }

    #[test]
    fn load_enabled_external_skills_with_copilot_path() {
        let tmp = tempfile::tempdir().unwrap();
        let github_dir = tmp.path().join(".github");
        std::fs::create_dir_all(&github_dir).unwrap();
        std::fs::write(
            github_dir.join("copilot-instructions.md"),
            "Use anyhow.",
        )
        .unwrap();
        // Discover once to recover the canonical path string (mirrors
        // load_enabled_includes_only_opted_in_paths -- macOS canonicalizes
        // /var to /private/var so the map key must come from the discovered
        // path, not the tempdir's raw path).
        let discovered = discover_external_skills(tmp.path());
        let mut enabled: std::collections::HashMap<String, bool> =
            std::collections::HashMap::new();
        for d in &discovered {
            if d.source == SkillSource::CopilotInstructions {
                enabled.insert(d.path.to_string_lossy().into_owned(), true);
            }
        }
        let result = load_enabled_external_skills(tmp.path(), &enabled);
        assert_eq!(
            result.len(),
            1,
            "expected only Copilot to be enabled, got {:?}",
            result
        );
        assert_eq!(result[0].source, SkillSource::CopilotInstructions);
    }
}
