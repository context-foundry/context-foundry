use serde::Deserialize;
use std::path::Path;

#[derive(Debug, Clone, Deserialize)]
pub struct Config {
    pub planner_model: String,
    pub builder_model: String,
    pub validator_model: String,
    pub fixer_model: String,
    pub discovery_model: String,

    pub max_fix_attempts: usize,
    pub pause_between_tasks_secs: u64,
    pub pause_between_cycles_secs: u64,
}

impl Default for Config {
    fn default() -> Self {
        Self {
            planner_model: "opus".into(),
            builder_model: "opus".into(),
            validator_model: "opus".into(),
            fixer_model: "opus".into(),
            discovery_model: "opus".into(),

            max_fix_attempts: 3,
            pause_between_tasks_secs: 5,
            pause_between_cycles_secs: 30,
        }
    }
}

impl Config {
    pub fn load(project_dir: &Path) -> Self {
        let config_path = project_dir.join(".foundry.json");
        if config_path.exists() {
            let content = std::fs::read_to_string(&config_path).unwrap_or_default();
            serde_json::from_str(&content).unwrap_or_default()
        } else {
            Self::default()
        }
    }
}
