use std::path::{Path, PathBuf};

use crate::patterns::{self, Pattern};

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
    ProjectLocal,
}

/// Scan both `~/.foundry/extensions/` and `<project_dir>/extensions/` for
/// directories containing CLAUDE.md. Project-local extensions override global
/// ones with the same name.
pub fn discover_extensions(project_dir: &Path) -> Vec<ExtensionInfo> {
    let mut results = Vec::new();

    // Global extensions dir: ~/.foundry/extensions/
    if let Ok(home) = std::env::var("HOME") {
        let global_dir = PathBuf::from(home).join(".foundry").join("extensions");
        scan_extensions_dir(&global_dir, ExtensionSource::Global, &mut results);
    } else {
        eprintln!("warning: HOME not set, skipping global extensions directory");
    }

    // Project-local extensions dir: <project_dir>/extensions/
    let local_dir = project_dir.join("extensions");
    scan_extensions_dir(&local_dir, ExtensionSource::ProjectLocal, &mut results);

    // Deduplicate: project-local overrides global
    let mut seen: std::collections::HashMap<String, usize> = std::collections::HashMap::new();
    for (i, ext) in results.iter().enumerate() {
        if let Some(&prev_idx) = seen.get(&ext.name) {
            // If this one is ProjectLocal and prev is Global, replace
            if ext.source == ExtensionSource::ProjectLocal
                && results[prev_idx].source == ExtensionSource::Global
            {
                seen.insert(ext.name.clone(), i);
            }
        } else {
            seen.insert(ext.name.clone(), i);
        }
    }
    let mut deduped: Vec<ExtensionInfo> = seen
        .into_values()
        .map(|i| results[i].clone())
        .collect();
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

/// Read CLAUDE.md from each selected extension and build a single concatenated
/// context string wrapped in delimiter blocks.
pub fn load_extension_context(extensions: &[ExtensionInfo], selected: &[String]) -> String {
    let mut context = String::new();
    for name in selected {
        let Some(ext) = extensions.iter().find(|e| e.name == *name) else {
            eprintln!("warning: selected extension '{}' not found in discovered extensions", name);
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
            "\n--- BEGIN EXTENSION CONTRACT: {} ---\n{}\n--- END EXTENSION CONTRACT: {} ---\n",
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
                    "Extension '{}' is configured but not found in ~/.foundry/extensions/ or project extensions/",
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

/// Load all pattern JSON files from selected extensions' patterns directories.
pub fn load_extension_patterns(
    extensions: &[ExtensionInfo],
    selected: &[String],
) -> Vec<Pattern> {
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
