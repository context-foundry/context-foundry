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
    /// Which `BuildBackend` to run: `"mock"` (default) or `"local_docker"`.
    pub build_backend: String,
    /// Docker image used by the `LocalDocker` backend.
    pub builder_image: String,
    /// URL a build container uses for `ANTHROPIC_BASE_URL` — the daemon's auth
    /// proxy, reachable from inside the container.
    pub builder_proxy_url: String,
    /// The `docker` CLI binary the `LocalDocker` backend invokes.
    pub docker_bin: String,
    /// Docker network preview containers join — isolated/inbound-only.
    pub preview_network: String,
    /// Base domain previews are routed under (`build-<job>.<domain>`).
    pub preview_base_domain: String,
    /// Caddy admin API URL used to add/remove preview routes.
    pub caddy_admin_url: String,
    /// The Caddy HTTP-server name routes are appended to (default `srv0`).
    pub caddy_server_name: String,
    /// How long a preview health check polls before giving up.
    pub preview_health_timeout_secs: u64,
    /// `--memory` cap for a preview container.
    pub preview_memory: String,
    /// `--cpus` cap for a preview container.
    pub preview_cpus: String,
    /// `--pids-limit` cap for a preview container.
    pub preview_pids_limit: u32,
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

        let build_backend = env_or("FOUNDRY_SERVICE_BUILD_BACKEND", "mock");
        let builder_image = env_or("FOUNDRY_SERVICE_BUILDER_IMAGE", "foundry-builder:latest");
        let builder_proxy_url = env_or(
            "FOUNDRY_SERVICE_BUILDER_PROXY_URL",
            "http://host.docker.internal:8788",
        );
        let docker_bin = env_or("FOUNDRY_SERVICE_DOCKER_BIN", "docker");
        let preview_health_timeout_secs: u64 =
            env_or("FOUNDRY_SERVICE_PREVIEW_HEALTH_TIMEOUT_SECS", "60")
                .parse()
                .context("parse FOUNDRY_SERVICE_PREVIEW_HEALTH_TIMEOUT_SECS")?;
        let preview_pids_limit: u32 = env_or("FOUNDRY_SERVICE_PREVIEW_PIDS_LIMIT", "256")
            .parse()
            .context("parse FOUNDRY_SERVICE_PREVIEW_PIDS_LIMIT")?;

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
            build_backend,
            builder_image,
            builder_proxy_url,
            docker_bin,
            preview_network: env_or("FOUNDRY_SERVICE_PREVIEW_NETWORK", "foundry-preview"),
            preview_base_domain: env_or("FOUNDRY_SERVICE_PREVIEW_DOMAIN", "foundry.local"),
            caddy_admin_url: env_or("FOUNDRY_SERVICE_CADDY_ADMIN_URL", "http://localhost:2019"),
            caddy_server_name: env_or("FOUNDRY_SERVICE_CADDY_SERVER", "srv0"),
            preview_health_timeout_secs,
            preview_memory: env_or("FOUNDRY_SERVICE_PREVIEW_MEMORY", "512m"),
            preview_cpus: env_or("FOUNDRY_SERVICE_PREVIEW_CPUS", "1"),
            preview_pids_limit,
        })
    }
}
