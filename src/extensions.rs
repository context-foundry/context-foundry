use std::path::{Path, PathBuf};

use crate::patterns::{self, Pattern};
use crate::utils::truncate_str;

#[derive(Debug, Clone)]
pub struct ExtensionInfo {
    pub name: String,
    pub claude_md_path: PathBuf,
    pub patterns_dir: Option<PathBuf>,
    pub source: ExtensionSource,
    // Discovered for the modern plugin layout; reserved for future plugin tooling.
    #[allow(dead_code)]
    pub plugin_manifest: Option<PathBuf>,
    pub skills_dir: Option<PathBuf>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ExtensionSource {
    Global,
    /// Found in an ancestor directory's `extensions/` folder.
    Ancestor,
    ProjectLocal,
}

impl ExtensionSource {
    /// Higher number = higher priority when deduplicating.
    fn priority(self) -> u8 {
        match self {
            Self::Global => 0,
            Self::Ancestor => 1,
            Self::ProjectLocal => 2,
        }
    }
}

/// Discover extensions by scanning three sources (highest priority wins):
///
/// 1. **ProjectLocal** -- `<project_dir>/extensions/`
/// 2. **Ancestor** -- walk up from `project_dir` checking each ancestor for
///    an `extensions/` subdirectory (closest ancestor wins)
/// 3. **Global** -- `~/.foundry/extensions/`
///
/// When the same extension name appears in multiple sources the higher-priority
/// source wins.
pub fn discover_extensions(project_dir: &Path) -> Vec<ExtensionInfo> {
    let mut results = Vec::new();

    // Global extensions dir: ~/.foundry/extensions/
    if let Some(home) = crate::utils::home_dir() {
        let global_dir = home.join(".foundry").join("extensions");
        scan_extensions_dir(&global_dir, ExtensionSource::Global, &mut results);
    }

    // Ancestor extensions: walk up from project_dir, collect ancestor
    // `extensions/` dirs, then scan farthest-first so closer ancestors appear
    // later in `results` and win during dedup (via `>=`).
    {
        let canonical = project_dir
            .canonicalize()
            .unwrap_or_else(|_| project_dir.to_path_buf());
        let mut ancestor_ext_dirs = Vec::new();
        let mut cur = canonical.parent();
        while let Some(dir) = cur {
            let ext_dir = dir.join("extensions");
            if ext_dir.is_dir() {
                ancestor_ext_dirs.push(ext_dir);
            }
            cur = dir.parent();
        }
        // Reverse so farthest ancestor is scanned first, closest last (wins dedup).
        for ext_dir in ancestor_ext_dirs.into_iter().rev() {
            scan_extensions_dir(&ext_dir, ExtensionSource::Ancestor, &mut results);
        }
    }

    // Project-local extensions dir: <project_dir>/extensions/
    let local_dir = project_dir.join("extensions");
    scan_extensions_dir(&local_dir, ExtensionSource::ProjectLocal, &mut results);

    // Deduplicate: higher-priority source wins
    let mut seen: std::collections::HashMap<String, usize> = std::collections::HashMap::new();
    for (i, ext) in results.iter().enumerate() {
        if let Some(&prev_idx) = seen.get(&ext.name) {
            if ext.source.priority() >= results[prev_idx].source.priority() {
                seen.insert(ext.name.clone(), i);
            }
        } else {
            seen.insert(ext.name.clone(), i);
        }
    }
    let mut deduped: Vec<ExtensionInfo> = seen.into_values().map(|i| results[i].clone()).collect();
    deduped.sort_by(|a, b| a.name.cmp(&b.name));
    deduped
}

fn scan_extensions_dir(dir: &Path, source: ExtensionSource, results: &mut Vec<ExtensionInfo>) {
    let entries = match std::fs::read_dir(dir) {
        Ok(e) => e,
        Err(_) => return,
    };

    for entry in entries.flatten() {
        let path = entry.path();
        if !path.is_dir() {
            continue;
        }
        let claude_md_path = path.join("CLAUDE.md");
        let plugin_manifest_path = path.join(".claude-plugin").join("plugin.json");
        let skills_dir_path = path.join("skills");

        let has_claude_md = claude_md_path.exists();
        let has_plugin_manifest = plugin_manifest_path.is_file();
        if !has_claude_md && !has_plugin_manifest {
            continue;
        }

        let plugin_manifest = if has_plugin_manifest {
            Some(plugin_manifest_path)
        } else {
            None
        };
        let skills_dir = if skills_dir_path.is_dir() && skills_dir_has_any_skill_md(&skills_dir_path)
        {
            Some(skills_dir_path)
        } else {
            None
        };

        let name = entry.file_name().to_string_lossy().into_owned();
        let pdir = path.join("patterns");
        let patterns_dir = if pdir.is_dir() { Some(pdir) } else { None };
        results.push(ExtensionInfo {
            name,
            claude_md_path,
            patterns_dir,
            source,
            plugin_manifest,
            skills_dir,
        });
    }
}

fn skills_dir_has_any_skill_md(skills_dir: &Path) -> bool {
    let entries = match std::fs::read_dir(skills_dir) {
        Ok(e) => e,
        Err(_) => return false,
    };
    for entry in entries.flatten() {
        if entry.path().join("SKILL.md").is_file() {
            return true;
        }
    }
    false
}

fn strip_skill_frontmatter(content: &str) -> &str {
    let stripped = content.strip_prefix('\u{feff}').unwrap_or(content);
    if !stripped.starts_with("---\n") {
        return content;
    }
    let after_open = &stripped[4..];
    let close_idx = match after_open.find("\n---\n") {
        Some(i) => i,
        None => return content,
    };
    let body_start_in_after = close_idx + "\n---\n".len();
    let body = &after_open[body_start_in_after..];
    body.strip_prefix('\n').unwrap_or(body)
}

fn read_skills_body(skills_dir: &Path) -> String {
    let entries_iter = match std::fs::read_dir(skills_dir) {
        Ok(e) => e,
        Err(_) => return String::new(),
    };
    let mut entries: Vec<PathBuf> = Vec::new();
    for entry in entries_iter.flatten() {
        let p = entry.path();
        if p.is_dir() {
            let skill_md = p.join("SKILL.md");
            if skill_md.is_file() {
                entries.push(skill_md);
            }
        }
    }
    entries.sort();

    let mut out = String::new();
    for path in &entries {
        let content = match std::fs::read_to_string(path) {
            Ok(c) => c,
            Err(e) => {
                eprintln!("warning: failed to read skill {}: {}", path.display(), e);
                continue;
            }
        };
        let body = strip_skill_frontmatter(&content);
        let trimmed = body.trim();
        if trimmed.is_empty() {
            continue;
        }
        if !out.is_empty() {
            out.push_str("\n\n");
        }
        out.push_str(body);
    }
    out
}

/// Extract a one-line description from a CLAUDE.md file.
/// Returns the first non-empty, non-heading line after the first `#` heading.
pub fn extract_description(claude_md_path: &Path) -> String {
    let content = match std::fs::read_to_string(claude_md_path) {
        Ok(c) => c,
        Err(_) => return "(no description)".to_string(),
    };
    let mut past_heading = false;
    for line in content.lines() {
        if !past_heading {
            if line.starts_with('#') {
                past_heading = true;
            }
            continue;
        }
        let trimmed = line.trim();
        if !trimmed.is_empty() && !trimmed.starts_with('#') {
            if trimmed.len() > 80 {
                return truncate_str(trimmed, 80).to_string();
            }
            return trimmed.to_string();
        }
    }
    "(no description)".to_string()
}

/// Count JSON pattern files in an extension's patterns directory.
pub fn count_extension_patterns(patterns_dir: &Option<PathBuf>) -> usize {
    let Some(dir) = patterns_dir else {
        return 0;
    };
    let entries = match std::fs::read_dir(dir) {
        Ok(e) => e,
        Err(_) => return 0,
    };
    entries
        .flatten()
        .filter(|e| {
            e.path()
                .extension()
                .and_then(|ext| ext.to_str())
                .is_some_and(|ext| ext == "json")
        })
        .count()
}

/// Build the concatenated agent-prompt context block for selected extensions.
/// Prefers `skills/*/SKILL.md` content (modern plugin layout) and falls back to
/// `CLAUDE.md` (legacy layout). Each extension's body is wrapped in the
/// `--- BEGIN/END EXTENSION CONTEXT ---` delimiter pair (format unchanged).
pub fn load_extension_context(extensions: &[ExtensionInfo], selected: &[String]) -> String {
    let mut context = String::new();
    for name in selected {
        let Some(ext) = extensions.iter().find(|e| e.name == *name) else {
            eprintln!(
                "warning: selected extension '{}' not found in discovered extensions",
                name
            );
            continue;
        };
        let body = if let Some(skills_dir) = ext.skills_dir.as_ref() {
            read_skills_body(skills_dir)
        } else {
            match std::fs::read_to_string(&ext.claude_md_path) {
                Ok(c) => c,
                Err(e) => {
                    eprintln!(
                        "warning: failed to read CLAUDE.md for extension '{}': {}",
                        name, e
                    );
                    String::new()
                }
            }
        };
        if body.trim().is_empty() {
            continue;
        }
        context.push_str(&format!(
            "\n--- BEGIN EXTENSION CONTEXT: {} ---\n{}\n--- END EXTENSION CONTEXT: {} ---\n",
            name,
            body.trim(),
            name
        ));
    }
    context
}

/// Verify all configured extensions have usable content -- either a non-empty
/// `skills/*/SKILL.md` body (modern plugin layout) or a non-empty `CLAUDE.md`
/// (legacy layout). Called before the IMPLEMENT stage as a prerequisite gate.
pub fn validate_extensions(
    extensions: &[ExtensionInfo],
    selected: &[String],
) -> Result<(), Vec<String>> {
    let mut errors = Vec::new();
    for name in selected {
        match extensions.iter().find(|e| e.name == *name) {
            None => {
                errors.push(format!(
                    "Extension '{}' is configured but not found in ~/.foundry/extensions/, ancestor directories, or project extensions/",
                    name
                ));
            }
            Some(ext) => {
                let has_skills_body = ext
                    .skills_dir
                    .as_ref()
                    .map(|d| !read_skills_body(d).trim().is_empty())
                    .unwrap_or(false);
                let has_claude_md_body = ext.claude_md_path.exists()
                    && std::fs::read_to_string(&ext.claude_md_path)
                        .map(|c| !c.trim().is_empty())
                        .unwrap_or(false);

                if !has_skills_body && !has_claude_md_body {
                    errors.push(format!(
                        "Extension '{}' is configured but has no usable content (no skills/*/SKILL.md and no non-empty CLAUDE.md at {})",
                        name,
                        ext.claude_md_path.display()
                    ));
                }
            }
        }
    }
    if errors.is_empty() {
        Ok(())
    } else {
        Err(errors)
    }
}

/// Extract domain-specific keywords from an extension's CLAUDE.md for reference detection.
/// Pulls inline code spans (backtick-delimited) and bold text (**-delimited) as keyword candidates.
pub fn extract_keywords(claude_md_path: &Path) -> Vec<String> {
    let content = match std::fs::read_to_string(claude_md_path) {
        Ok(c) => c,
        Err(_) => return Vec::new(),
    };

    let mut keywords = std::collections::HashSet::new();

    for line in content.lines() {
        // Extract inline code spans (backtick-delimited)
        let parts: Vec<&str> = line.split('`').collect();
        for (i, part) in parts.iter().enumerate() {
            if i % 2 == 1 {
                let term = part.trim();
                if term.len() >= 3 && term.len() <= 40 && !term.chars().all(|c| c.is_ascii_digit())
                {
                    keywords.insert(term.to_lowercase());
                }
            }
        }

        // Extract bold text (**-delimited)
        let bold_parts: Vec<&str> = line.split("**").collect();
        for (i, part) in bold_parts.iter().enumerate() {
            if i % 2 == 1 {
                let term = part.trim();
                if term.len() >= 3 && term.len() <= 40 && !term.chars().all(|c| c.is_ascii_digit())
                {
                    keywords.insert(term.to_lowercase());
                }
            }
        }
    }

    let mut result: Vec<String> = keywords.into_iter().collect();
    result.sort();
    result.truncate(50);
    result
}

/// Load all pattern JSON files from selected extensions' patterns directories.
pub fn load_extension_patterns(extensions: &[ExtensionInfo], selected: &[String]) -> Vec<Pattern> {
    let mut all_patterns = Vec::new();
    for name in selected {
        let Some(ext) = extensions.iter().find(|e| e.name == *name) else {
            continue;
        };
        let Some(ref pdir) = ext.patterns_dir else {
            continue;
        };
        let mut ext_patterns = patterns::load_patterns(pdir);
        all_patterns.append(&mut ext_patterns);
    }
    all_patterns
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_ancestor_discovery() {
        // Create: /tmp/xxx/extensions/testext/CLAUDE.md
        //         /tmp/xxx/child/grandchild/   <-- project_dir
        // The ancestor walk from grandchild should find testext.
        let root = tempfile::tempdir().unwrap();
        let ext_dir = root.path().join("extensions").join("testext");
        std::fs::create_dir_all(&ext_dir).unwrap();
        std::fs::write(ext_dir.join("CLAUDE.md"), "# Test\n\nA test.\n").unwrap();

        let project_dir = root.path().join("child").join("grandchild");
        std::fs::create_dir_all(&project_dir).unwrap();

        let discovered = discover_extensions(&project_dir);
        let names: Vec<&str> = discovered.iter().map(|e| e.name.as_str()).collect();
        assert!(
            names.contains(&"testext"),
            "ancestor walk should find testext, got: {:?}",
            names
        );
        let testext = discovered.iter().find(|e| e.name == "testext").unwrap();
        assert_eq!(testext.source, ExtensionSource::Ancestor);
    }

    #[test]
    fn test_project_local_overrides_ancestor() {
        // Both ancestor and project-local have "samename" extension.
        // Project-local should win.
        let root = tempfile::tempdir().unwrap();

        // Ancestor version
        let ancestor_ext = root.path().join("extensions").join("samename");
        std::fs::create_dir_all(&ancestor_ext).unwrap();
        std::fs::write(ancestor_ext.join("CLAUDE.md"), "# Ancestor\n\nOld.\n").unwrap();

        // Project-local version
        let project_dir = root.path().join("child");
        std::fs::create_dir_all(&project_dir).unwrap();
        let local_ext = project_dir.join("extensions").join("samename");
        std::fs::create_dir_all(&local_ext).unwrap();
        std::fs::write(local_ext.join("CLAUDE.md"), "# Local\n\nNew.\n").unwrap();

        let discovered = discover_extensions(&project_dir);
        let ext = discovered.iter().find(|e| e.name == "samename").unwrap();
        assert_eq!(ext.source, ExtensionSource::ProjectLocal);
    }

    #[test]
    fn test_plugin_only_extension_is_discovered() {
        let root = tempfile::tempdir().unwrap();
        let ext_dir = root
            .path()
            .join("extensions")
            .join("onlyplugin")
            .join(".claude-plugin");
        std::fs::create_dir_all(&ext_dir).unwrap();
        std::fs::write(
            ext_dir.join("plugin.json"),
            r#"{"name":"foo","version":"0.1.0","description":"x"}"#,
        )
        .unwrap();

        let project_dir = root.path().join("child");
        std::fs::create_dir_all(&project_dir).unwrap();

        let discovered = discover_extensions(&project_dir);
        let ext = discovered
            .iter()
            .find(|e| e.name == "onlyplugin")
            .expect("plugin-only extension should be discovered");
        assert!(ext.plugin_manifest.is_some());
        assert!(ext.skills_dir.is_none());
    }

    #[test]
    fn test_load_extension_context_prefers_skills_over_claude_md() {
        let root = tempfile::tempdir().unwrap();
        let ext_root = root.path().join("extensions").join("dual");
        std::fs::create_dir_all(&ext_root).unwrap();
        std::fs::write(ext_root.join("CLAUDE.md"), "LEGACY-BODY").unwrap();

        let topic_a = ext_root.join("skills").join("topicA");
        let topic_b = ext_root.join("skills").join("topicB");
        std::fs::create_dir_all(&topic_a).unwrap();
        std::fs::create_dir_all(&topic_b).unwrap();
        std::fs::write(
            topic_a.join("SKILL.md"),
            "---\nname: topicA\ndescription: a\n---\n\nMODERN-BODY-A\n",
        )
        .unwrap();
        std::fs::write(
            topic_b.join("SKILL.md"),
            "---\nname: topicB\ndescription: b\n---\n\nMODERN-BODY-B\n",
        )
        .unwrap();

        // Use a child project_dir so root.path()/extensions/dual is found via ancestor walk.
        let project_dir = root.path().join("child");
        std::fs::create_dir_all(&project_dir).unwrap();
        let extensions = discover_extensions(&project_dir);
        let result = load_extension_context(&extensions, &vec!["dual".to_string()]);

        assert!(
            result.contains("--- BEGIN EXTENSION CONTEXT: dual ---"),
            "missing BEGIN delimiter: {}",
            result
        );
        assert!(
            result.contains("MODERN-BODY-A"),
            "missing MODERN-BODY-A: {}",
            result
        );
        assert!(
            result.contains("MODERN-BODY-B"),
            "missing MODERN-BODY-B: {}",
            result
        );
        assert!(
            !result.contains("LEGACY-BODY"),
            "LEGACY-BODY should not appear when skills present: {}",
            result
        );
        let pos_a = result.find("MODERN-BODY-A").unwrap();
        let pos_b = result.find("MODERN-BODY-B").unwrap();
        assert!(
            pos_a < pos_b,
            "topicA should appear before topicB (lex order)"
        );
    }

    #[test]
    fn test_load_extension_context_falls_back_to_claude_md() {
        let root = tempfile::tempdir().unwrap();
        let ext_root = root.path().join("extensions").join("legacy");
        std::fs::create_dir_all(&ext_root).unwrap();
        std::fs::write(ext_root.join("CLAUDE.md"), "LEGACY-FALLBACK-BODY").unwrap();

        let project_dir = root.path().join("child");
        std::fs::create_dir_all(&project_dir).unwrap();
        let extensions = discover_extensions(&project_dir);
        let result = load_extension_context(&extensions, &vec!["legacy".to_string()]);

        assert!(
            result.contains("LEGACY-FALLBACK-BODY"),
            "missing legacy body: {}",
            result
        );
        assert!(
            result.contains("--- BEGIN EXTENSION CONTEXT: legacy ---"),
            "missing BEGIN delimiter: {}",
            result
        );
    }
}
