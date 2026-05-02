use std::path::{Path, PathBuf};

use crate::patterns::{self, Pattern};
use crate::utils::truncate_str;

#[derive(Debug, Clone)]
pub struct ExtensionInfo {
    pub name: String,
    pub claude_md_path: PathBuf,
    pub patterns_dir: Option<PathBuf>,
    pub source: ExtensionSource,
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
    if let Ok(home) = std::env::var("HOME") {
        let global_dir = PathBuf::from(home).join(".foundry").join("extensions");
        scan_extensions_dir(&global_dir, ExtensionSource::Global, &mut results);
    } else {
        eprintln!("warning: HOME not set, skipping global extensions directory");
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
        if !claude_md_path.exists() {
            continue;
        }
        let name = entry.file_name().to_string_lossy().into_owned();
        let pdir = path.join("patterns");
        let patterns_dir = if pdir.is_dir() { Some(pdir) } else { None };
        results.push(ExtensionInfo {
            name,
            claude_md_path,
            patterns_dir,
            source,
        });
    }
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

/// Read CLAUDE.md from each selected extension and build a single concatenated
/// context string wrapped in delimiter blocks.
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
        let content = match std::fs::read_to_string(&ext.claude_md_path) {
            Ok(c) => c,
            Err(e) => {
                eprintln!(
                    "warning: failed to read CLAUDE.md for extension '{}': {}",
                    name, e
                );
                continue;
            }
        };
        if content.trim().is_empty() {
            continue;
        }
        context.push_str(&format!(
            "\n--- BEGIN EXTENSION CONTEXT: {} ---\n{}\n--- END EXTENSION CONTEXT: {} ---\n",
            name,
            content.trim(),
            name
        ));
    }
    context
}

/// Verify all configured extensions have their CLAUDE.md present and non-empty.
/// Called before the IMPLEMENT stage as a prerequisite gate.
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
                if !ext.claude_md_path.exists() {
                    errors.push(format!(
                        "Extension '{}' is configured but CLAUDE.md not found at {}",
                        name,
                        ext.claude_md_path.display()
                    ));
                } else {
                    match std::fs::read_to_string(&ext.claude_md_path) {
                        Err(e) => {
                            errors.push(format!(
                                "Extension '{}' CLAUDE.md cannot be read at {}: {}",
                                name,
                                ext.claude_md_path.display(),
                                e
                            ));
                        }
                        Ok(content) => {
                            if content.trim().is_empty() {
                                errors.push(format!(
                                    "Extension '{}' has empty CLAUDE.md at {}",
                                    name,
                                    ext.claude_md_path.display()
                                ));
                            }
                        }
                    }
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
}
