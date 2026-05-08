#![allow(dead_code)]

use anyhow::Result;
use std::path::Path;

pub mod parser;
pub mod run;
pub mod stage_id;

pub fn run_for_current_task(_project_dir: &Path) -> Result<()> {
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn run_for_current_task_stub_returns_ok() {
        assert!(run_for_current_task(Path::new("/tmp")).is_ok());
    }
}
