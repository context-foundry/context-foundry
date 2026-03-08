use std::path::Path;

pub(super) fn should_skip_snapshot_path(rel: &Path) -> bool {
    let components: Vec<String> = rel
        .components()
        .map(|component| component.as_os_str().to_string_lossy().to_string())
        .collect();

    if components.is_empty() {
        return false;
    }

    let first = components[0].as_str();
    if matches!(
        first,
        ".git"
            | "target"
            | "node_modules"
            | ".venv"
            | "venv"
            | "__pycache__"
            | ".pytest_cache"
            | ".ruff_cache"
            | ".build-venv"
    ) {
        return true;
    }

    components.len() >= 2 && components[0] == ".foundry" && components[1] == "studio"
}

pub(super) fn join_or_none(items: &[String], separator: &str) -> String {
    if items.is_empty() {
        "none".to_string()
    } else {
        items.join(separator)
    }
}

#[cfg(test)]
mod tests {
    use std::path::Path;

    use super::{join_or_none, should_skip_snapshot_path};

    #[test]
    fn snapshot_skip_rules_cover_foundry_studio() {
        assert!(should_skip_snapshot_path(Path::new(".git")));
        assert!(should_skip_snapshot_path(Path::new("target")));
        assert!(should_skip_snapshot_path(Path::new(".foundry/studio")));
        assert!(should_skip_snapshot_path(Path::new(".foundry/studio/logs")));
        assert!(!should_skip_snapshot_path(Path::new("src")));
    }

    #[test]
    fn join_or_none_uses_placeholder_for_empty_lists() {
        assert_eq!(join_or_none(&[], ", "), "none");
        assert_eq!(join_or_none(&["a".into(), "b".into()], ", "), "a, b");
    }
}
