use std::path::PathBuf;
use std::process::{Command, Stdio};

fn repo_root() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
}

#[test]
#[ignore]
fn smoke_lmstudio_round_trip() {
    let script = repo_root().join("scripts").join("smoke-local-model.sh");
    assert!(
        script.exists(),
        "missing smoke script at {}",
        script.display()
    );

    let mut cmd = Command::new("bash");
    cmd.arg(&script);
    if std::env::var_os("FOUNDRY_SMOKE_KEEP").is_some() {
        cmd.arg("--keep");
    }
    cmd.stdout(Stdio::inherit()).stderr(Stdio::inherit());
    cmd.current_dir(repo_root());

    let status = cmd.status().expect("failed to spawn smoke script");
    assert!(
        status.success(),
        "smoke-local-model.sh exited with status: {:?}",
        status
    );
}

#[test]
#[ignore]
fn smoke_script_is_executable() {
    let script = repo_root().join("scripts").join("smoke-local-model.sh");
    let meta = std::fs::metadata(&script).expect("smoke script missing");
    assert!(meta.len() > 0, "smoke script is empty");
}
