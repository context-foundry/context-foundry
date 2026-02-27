use serde::Deserialize;
use std::path::Path;

#[derive(Debug, Clone, Deserialize)]
#[serde(default)]
pub struct Config {
    pub planner_model: String,
    pub builder_model: String,
    pub reviewer_model: String,
    pub fixer_model: String,
    pub discovery_model: String,

    pub pause_between_tasks_secs: u64,
    pub pause_between_agents_secs: u64,
    pub pause_between_cycles_secs: u64,

    pub agent_timeout_secs: u64,

    pub patterns_dir: String,
}

impl Default for Config {
    fn default() -> Self {
        Self {
            planner_model: "opus".into(),
            builder_model: "opus".into(),
            reviewer_model: "opus".into(),
            fixer_model: "opus".into(),
            discovery_model: "opus".into(),

            pause_between_tasks_secs: 10,
            pause_between_agents_secs: 3,
            pause_between_cycles_secs: 30,

            agent_timeout_secs: 600, // 10 minutes

            patterns_dir: "~/.foundry/patterns".into(),
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
