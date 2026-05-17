//! Service configuration, loaded from the environment.

use std::net::SocketAddr;
use std::path::PathBuf;

use anyhow::{Context, Result};

/// Runtime configuration for the build service.
///
/// All fields are public so tests can construct a config without touching the
/// process environment.
#[derive(Clone, Debug)]
pub struct ServiceConfig {
    pub database_url: String,
    pub bind_addr: SocketAddr,
    pub proxy_bind_addr: SocketAddr,
    pub api_keys: Vec<String>,
    pub anthropic_api_key: String,
    pub anthropic_base_url: String,
    pub worker_count: usize,
    pub queue_cap: usize,
    pub min_ttl_hours: i32,
    pub default_ttl_hours: i32,
    pub max_ttl_hours: i32,
    pub storage_root: PathBuf,
    pub max_input_bytes: usize,
    pub reaper_interval_secs: u64,
    pub proxy_max_concurrent: usize,
    pub proxy_max_body_bytes: usize,
    pub proxy_max_output_tokens: u64,
    pub proxy_model_prefixes: Vec<String>,
}

fn env_or(key: &str, default: &str) -> String {
    std::env::var(key)
        .ok()
        .filter(|s| !s.is_empty())
        .unwrap_or_else(|| default.to_string())
}

fn split_csv(raw: &str) -> Vec<String> {
    raw.split(',')
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .collect()
}

impl ServiceConfig {
    /// Build a config from `FOUNDRY_SERVICE_*` (and `ANTHROPIC_API_KEY`) env
    /// vars. Missing keys fall back to documented defaults; only an
    /// unparseable address or number is a hard error.
    pub fn from_env() -> Result<ServiceConfig> {
        let bind_addr: SocketAddr = env_or("FOUNDRY_SERVICE_BIND", "0.0.0.0:8787")
            .parse()
            .context("parse FOUNDRY_SERVICE_BIND")?;
        let proxy_bind_addr: SocketAddr = env_or("FOUNDRY_SERVICE_PROXY_BIND", "0.0.0.0:8788")
            .parse()
            .context("parse FOUNDRY_SERVICE_PROXY_BIND")?;
        let worker_count: usize = env_or("FOUNDRY_SERVICE_WORKERS", "3")
            .parse()
            .context("parse FOUNDRY_SERVICE_WORKERS")?;
        let queue_cap: usize = env_or("FOUNDRY_SERVICE_QUEUE_CAP", "50")
            .parse()
            .context("parse FOUNDRY_SERVICE_QUEUE_CAP")?;
        let min_ttl_hours: i32 = env_or("FOUNDRY_SERVICE_MIN_TTL_HOURS", "1")
            .parse()
            .context("parse FOUNDRY_SERVICE_MIN_TTL_HOURS")?;
        let default_ttl_hours: i32 = env_or("FOUNDRY_SERVICE_DEFAULT_TTL_HOURS", "24")
            .parse()
            .context("parse FOUNDRY_SERVICE_DEFAULT_TTL_HOURS")?;
        let max_ttl_hours: i32 = env_or("FOUNDRY_SERVICE_MAX_TTL_HOURS", "72")
            .parse()
            .context("parse FOUNDRY_SERVICE_MAX_TTL_HOURS")?;
        let max_input_bytes: usize = env_or("FOUNDRY_SERVICE_MAX_INPUT_BYTES", "524288")
            .parse()
            .context("parse FOUNDRY_SERVICE_MAX_INPUT_BYTES")?;
        let reaper_interval_secs: u64 = env_or("FOUNDRY_SERVICE_REAPER_INTERVAL_SECS", "60")
            .parse()
            .context("parse FOUNDRY_SERVICE_REAPER_INTERVAL_SECS")?;
        let proxy_max_concurrent: usize = env_or("FOUNDRY_SERVICE_PROXY_MAX_CONCURRENT", "8")
            .parse()
            .context("parse FOUNDRY_SERVICE_PROXY_MAX_CONCURRENT")?;
        let proxy_max_body_bytes: usize = env_or("FOUNDRY_SERVICE_PROXY_MAX_BODY_BYTES", "4194304")
            .parse()
            .context("parse FOUNDRY_SERVICE_PROXY_MAX_BODY_BYTES")?;
        let proxy_max_output_tokens: u64 =
            env_or("FOUNDRY_SERVICE_PROXY_MAX_OUTPUT_TOKENS", "8192")
                .parse()
                .context("parse FOUNDRY_SERVICE_PROXY_MAX_OUTPUT_TOKENS")?;
        let proxy_model_prefixes =
            split_csv(&env_or("FOUNDRY_SERVICE_PROXY_MODEL_PREFIXES", "claude-"));

        Ok(ServiceConfig {
            database_url: env_or(
                "FOUNDRY_SERVICE_DATABASE_URL",
                "postgres://foundry:foundry@localhost:5432/foundry",
            ),
            bind_addr,
            proxy_bind_addr,
            api_keys: split_csv(&env_or("FOUNDRY_SERVICE_API_KEYS", "")),
            anthropic_api_key: env_or("ANTHROPIC_API_KEY", ""),
            anthropic_base_url: env_or(
                "FOUNDRY_SERVICE_ANTHROPIC_BASE_URL",
                "https://api.anthropic.com",
            ),
            worker_count,
            queue_cap,
            min_ttl_hours,
            default_ttl_hours,
            max_ttl_hours,
            storage_root: PathBuf::from(env_or(
                "FOUNDRY_SERVICE_STORAGE",
                "./.foundry-service/storage",
            )),
            max_input_bytes,
            reaper_interval_secs,
            proxy_max_concurrent,
            proxy_max_body_bytes,
            proxy_max_output_tokens,
            proxy_model_prefixes,
        })
    }
}
