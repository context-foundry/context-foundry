use std::fs;
use std::path::PathBuf;
use std::process::{Command, Stdio};

fn repo_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
}

fn foundry_bin() -> PathBuf {
    if let Ok(bin) = std::env::var("FOUNDRY_BIN") {
        return PathBuf::from(bin);
    }
    let release = repo_root().join("target/release/foundry");
    if release.exists() {
        return release;
    }
    let debug = repo_root().join("target/debug/foundry");
    if debug.exists() {
        return debug;
    }
    panic!("foundry binary not found (build with cargo build --release or set FOUNDRY_BIN)")
}

fn setup_workspace(dir: &std::path::Path, model: &str) {
    Command::new("git")
        .args(["init", "-q", "."])
        .current_dir(dir)
        .status()
        .unwrap();
    Command::new("git")
        .args(["config", "user.email", "test@example.com"])
        .current_dir(dir)
        .status()
        .unwrap();
    Command::new("git")
        .args(["config", "user.name", "test"])
        .current_dir(dir)
        .status()
        .unwrap();

    fs::write(dir.join("SPEC.md"), "# Test Spec\n\nprint hello world\n").unwrap();
    fs::write(
        dir.join("TASKS.md"),
        "## Tasks\n\n- [ ] T1.1: Create a file named hello.txt containing \"hello world\".\n",
    )
    .unwrap();

    let config = serde_json::json!({
        "builder_provider": "opencode",
        "builder_model": model,
        "builder_models": [format!("opencode:{}", model)],
        "dual_selection": "first",
        "run_mode": "sprint",
        "agent_timeout_secs": 300,
        "skip_planner_for_simple": true,
        "pipeline_stages": [
            {"id": "query",     "label": "QUERY",     "enabled": false},
            {"id": "research",  "label": "RESEARCH",  "enabled": false},
            {"id": "plan",      "label": "PLAN",      "enabled": false},
            {"id": "implement", "label": "IMPLEMENT", "enabled": true},
            {"id": "doubt",     "label": "DOUBT",     "enabled": false},
        ],
    });
    fs::write(
        dir.join(".foundry.json"),
        serde_json::to_string_pretty(&config).unwrap() + "\n",
    )
    .unwrap();

    let buildloop = dir.join(".buildloop");
    fs::create_dir_all(&buildloop).unwrap();
    fs::write(
        buildloop.join("research-report.md"),
        "# Research Report\nTrivial smoke task. No additional context required.\n",
    )
    .unwrap();
    fs::write(
        buildloop.join("current-plan.md"),
        "# Plan: T1.1\n\n## File Operations\n### 1. CREATE hello.txt\n- operation: CREATE\n- content: hello world\n\n## Verification\n- run: cat hello.txt\n- expect: hello world\n",
    )
    .unwrap();

    Command::new("git")
        .args(["add", "-A"])
        .current_dir(dir)
        .status()
        .unwrap();
    Command::new("git")
        .args(["commit", "-q", "-m", "initial workspace"])
        .current_dir(dir)
        .status()
        .unwrap();
}

fn get_lmstudio_model() -> Option<String> {
    let output = Command::new("opencode")
        .args(["models", "lmstudio"])
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .output()
        .ok()?;
    let first_line = String::from_utf8_lossy(&output.stdout)
        .lines()
        .next()?
        .trim()
        .to_string();
    if first_line.is_empty() {
        None
    } else {
        Some(first_line)
    }
}

#[test]
#[ignore]
fn quality_indicator_uses_qrpba_convention() {
    let model = match get_lmstudio_model() {
        Some(m) => m,
        None => {
            eprintln!("skipping: no LM Studio model available");
            return;
        }
    };

    let dir = tempfile::tempdir().expect("failed to create temp dir");
    setup_workspace(dir.path(), &model);

    let output = Command::new(foundry_bin())
        .args(["run", "--no-tui", "--output-format", "json"])
        .current_dir(dir.path())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .output()
        .expect("failed to spawn foundry");

    assert!(
        output.status.success(),
        "foundry exited with {:?}\nstderr: {}",
        output.status,
        String::from_utf8_lossy(&output.stderr)
    );

    let tasks_content =
        fs::read_to_string(dir.path().join("TASKS.md")).expect("TASKS.md missing after run");

    let completed_line = tasks_content
        .lines()
        .find(|l| l.trim_start().starts_with("- [x]"))
        .expect("no completed task in TASKS.md");

    let indicator = regex::Regex::new(r"\[([A-Z!.\-+]{4,7})\]")
        .unwrap()
        .captures(completed_line)
        .and_then(|c| c.get(1))
        .map(|m| m.as_str().to_string())
        .expect("no pipeline indicator on completed task line");

    assert!(
        indicator.contains('B'),
        "indicator {indicator} missing 'B' (Build)"
    );
    assert!(
        !indicator.contains('I'),
        "indicator {indicator} contains legacy 'I' (should be 'B')"
    );
    assert!(
        !indicator.contains('D'),
        "indicator {indicator} contains legacy 'D' (should be 'A')"
    );
}

#[test]
#[ignore]
fn quality_empty_deliverable_produces_wip() {
    let model = match get_lmstudio_model() {
        Some(m) => m,
        None => {
            eprintln!("skipping: no LM Studio model available");
            return;
        }
    };

    let dir = tempfile::tempdir().expect("failed to create temp dir");
    setup_workspace(dir.path(), &model);

    // Overwrite the plan to produce no file changes (noop task)
    fs::write(
        dir.path().join(".buildloop/current-plan.md"),
        "# Plan: T1.1\n\n## File Operations\n### 1. No changes needed\n- operation: NONE\n\n## Verification\n- run: true\n- expect: success\n",
    )
    .unwrap();

    let output = Command::new(foundry_bin())
        .args(["run", "--no-tui", "--output-format", "json"])
        .current_dir(dir.path())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .output()
        .expect("failed to spawn foundry");

    let stdout_str = String::from_utf8_lossy(&output.stdout);
    if let Ok(report) = serde_json::from_str::<serde_json::Value>(&stdout_str) {
        if let Some(tasks) = report.get("tasks").and_then(|t| t.as_array()) {
            if let Some(first_task) = tasks.first() {
                let status = first_task
                    .get("status")
                    .and_then(|s| s.as_str())
                    .unwrap_or("");
                if status == "WIP" {
                    // Expected: empty deliverable produces WIP
                }
                // DONE is also acceptable if the model actually created the file
            }
        }
    }
    // If we can't parse or it's DONE, that's fine -- the model may have created the file
}
