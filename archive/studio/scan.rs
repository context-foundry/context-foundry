use anyhow::Result;
use chrono::{DateTime, Utc};
use std::{fs, path::Path};

use super::shared::{join_or_none, should_skip_snapshot_path};

#[derive(Clone, Debug)]
pub(super) struct ProjectScan {
    pub(super) generated_at: DateTime<Utc>,
    pub(super) top_level: Vec<String>,
    pub(super) stack_signals: Vec<String>,
    pub(super) data_candidates: Vec<String>,
    pub(super) output_targets: Vec<String>,
}

impl ProjectScan {
    pub(super) fn summary_lines(&self) -> Vec<String> {
        let mut lines = Vec::new();
        lines.push(format!(
            "scan: {}",
            self.generated_at.format("%Y-%m-%d %H:%M:%S UTC")
        ));
        lines.push(format!(
            "stack: {}",
            join_or_none(&self.stack_signals, ", ")
        ));
        lines.push(format!("top: {}", join_or_none(&self.top_level, ", ")));
        lines.push(format!(
            "data: {}",
            join_or_none(&self.data_candidates, ", ")
        ));
        lines.push(format!(
            "outputs: {}",
            join_or_none(&self.output_targets, ", ")
        ));
        lines
    }
}

pub(super) fn scan_project(project_dir: &Path) -> Result<ProjectScan> {
    let mut top_level = Vec::new();
    for entry in fs::read_dir(project_dir)? {
        let entry = entry?;
        let name = entry.file_name().to_string_lossy().to_string();
        if should_skip_snapshot_path(Path::new(&name)) {
            continue;
        }
        top_level.push(name);
    }
    top_level.sort();
    top_level.truncate(12);

    let mut stack_signals = Vec::new();
    let stack_checks = [
        ("Cargo.toml", "Rust"),
        ("package.json", "Node/TS"),
        ("pyproject.toml", "Python"),
        ("requirements.txt", "Python"),
        ("docker-compose.yml", "Docker Compose"),
        ("Dockerfile", "Docker"),
    ];
    for (file, label) in stack_checks {
        if project_dir.join(file).exists() {
            stack_signals.push(label.to_string());
        }
    }

    if stack_signals.is_empty() {
        stack_signals.push("unknown".to_string());
    }

    let data_candidates = collect_matching_paths(
        project_dir,
        3,
        10,
        &[
            "json", "jsonl", "csv", "tsv", "sqlite", "db", "parquet", "md", "yaml", "yml",
        ],
    )?;
    let output_targets = collect_output_targets(project_dir)?;

    Ok(ProjectScan {
        generated_at: Utc::now(),
        top_level,
        stack_signals,
        data_candidates,
        output_targets,
    })
}

fn collect_matching_paths(
    root: &Path,
    max_depth: usize,
    limit: usize,
    extensions: &[&str],
) -> Result<Vec<String>> {
    let mut results = Vec::new();
    collect_matching_paths_inner(root, root, 0, max_depth, limit, extensions, &mut results)?;
    Ok(results)
}

fn collect_matching_paths_inner(
    root: &Path,
    current: &Path,
    depth: usize,
    max_depth: usize,
    limit: usize,
    extensions: &[&str],
    results: &mut Vec<String>,
) -> Result<()> {
    if depth > max_depth || results.len() >= limit {
        return Ok(());
    }

    let mut entries: Vec<_> = fs::read_dir(current)?
        .filter_map(|entry| entry.ok())
        .collect();
    entries.sort_by_key(|entry| entry.file_name());

    for entry in entries {
        if results.len() >= limit {
            break;
        }
        let path = entry.path();
        let rel = path
            .strip_prefix(root)
            .unwrap_or(&path)
            .to_string_lossy()
            .to_string();
        if should_skip_snapshot_path(Path::new(&rel)) {
            continue;
        }

        let file_type = entry.file_type()?;
        if file_type.is_dir() {
            collect_matching_paths_inner(
                root,
                &path,
                depth + 1,
                max_depth,
                limit,
                extensions,
                results,
            )?;
            continue;
        }

        if let Some(ext) = path.extension().and_then(|ext| ext.to_str()) {
            if extensions
                .iter()
                .any(|wanted| ext.eq_ignore_ascii_case(wanted))
            {
                results.push(rel);
            }
        }
    }

    Ok(())
}

fn collect_output_targets(root: &Path) -> Result<Vec<String>> {
    let candidates = ["public", "dist", "apps", "tools", "reports", "dashboard"];
    let mut found = Vec::new();
    for name in candidates {
        if root.join(name).exists() {
            found.push(name.to_string());
        }
    }

    if found.is_empty() {
        found = collect_matching_paths(root, 2, 8, &["html", "htm", "tsx", "jsx"])?;
    }

    Ok(found)
}

#[cfg(test)]
mod tests {
    use anyhow::Result;
    use std::fs;

    use super::super::test_helpers::temp_test_dir;
    use super::{collect_matching_paths, collect_output_targets, scan_project};

    #[test]
    fn project_scan_detects_stack_signals() -> Result<()> {
        let temp_dir = temp_test_dir("foundry-studio-scan");
        fs::create_dir_all(temp_dir.join("src"))?;
        fs::write(temp_dir.join("Cargo.toml"), "[package]\nname = \"demo\"\n")?;
        fs::write(temp_dir.join("metrics.json"), "{}")?;
        fs::create_dir_all(temp_dir.join("public"))?;

        let scan = scan_project(&temp_dir)?;
        assert!(scan.stack_signals.iter().any(|item| item == "Rust"));
        assert!(scan
            .data_candidates
            .iter()
            .any(|item| item == "metrics.json"));
        assert!(scan.output_targets.iter().any(|item| item == "public"));

        fs::remove_dir_all(&temp_dir)?;
        Ok(())
    }

    #[test]
    fn collect_matching_paths_respects_depth_and_extensions() -> Result<()> {
        let temp_dir = temp_test_dir("foundry-scan-matching-paths");
        fs::create_dir_all(temp_dir.join("reports/daily"))?;
        fs::create_dir_all(temp_dir.join("reports/daily/deep"))?;
        fs::write(temp_dir.join("reports/summary.json"), "{}")?;
        fs::write(temp_dir.join("reports/daily/chart.csv"), "a,b\n")?;
        fs::write(temp_dir.join("reports/daily/deep/ignored.json"), "{}")?;
        fs::write(temp_dir.join("reports/readme.md"), "# Docs\n")?;

        let matches = collect_matching_paths(&temp_dir, 2, 10, &["json", "csv"])?;

        fs::remove_dir_all(&temp_dir)?;
        assert!(matches.iter().any(|path| path == "reports/summary.json"));
        assert!(matches.iter().any(|path| path == "reports/daily/chart.csv"));
        assert!(!matches.iter().any(|path| path == "reports/readme.md"));
        assert!(!matches
            .iter()
            .any(|path| path == "reports/daily/deep/ignored.json"));
        Ok(())
    }

    #[test]
    fn collect_output_targets_falls_back_to_html_like_files() -> Result<()> {
        let temp_dir = temp_test_dir("foundry-scan-output-targets");
        fs::create_dir_all(temp_dir.join("app"))?;
        fs::write(
            temp_dir.join("app/dashboard.tsx"),
            "export default function Dashboard() {}",
        )?;
        fs::write(temp_dir.join("report.html"), "<html></html>")?;

        let targets = collect_output_targets(&temp_dir)?;

        fs::remove_dir_all(&temp_dir)?;
        assert!(targets.iter().any(|path| path == "app/dashboard.tsx"));
        assert!(targets.iter().any(|path| path == "report.html"));
        Ok(())
    }
}
