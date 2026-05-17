//! Service configuration, loaded from the environment.

use std::net::SocketAddr;
use std::path::PathBuf;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use anyhow::{bail, Context, Result};

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
    /// Wall-clock timeout for a build's LLM phase; exceeding it kills the
    /// build container and fails the job with `build_timeout`. `0` = fire immediately (tests).
    pub build_timeout_secs: u64,
    /// How long SIGTERM drain waits for in-flight workers before exiting;
    /// stragglers are caught by next-start reconciliation.
    pub drain_deadline_secs: u64,
    /// Global cap on concurrently in-flight builds, independent of `worker_count`;
    /// keeps build count below the Anthropic account's rate-limit headroom.
    pub max_concurrent_builds: usize,
    /// `--memory` cap for a build container.
    pub build_memory: String,
    /// `--cpus` cap for a build container.
    pub build_cpus: String,
    /// `--pids-limit` cap for a build container.
    pub build_pids_limit: u32,
}

/// Which credential the `foundry serve` auth proxy presents to Anthropic
/// upstream. Selected by `FOUNDRY_SERVICE_UPSTREAM_AUTH`.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum UpstreamAuthMode {
    /// `x-api-key: <ANTHROPIC_API_KEY>` -- the legacy default.
    ApiKey,
    /// `Authorization: Bearer <token>` + the OAuth `anthropic-beta` header.
    OAuth,
}

impl UpstreamAuthMode {
    /// Parse the `FOUNDRY_SERVICE_UPSTREAM_AUTH` env value into the enum. An
    /// empty value selects the legacy `ApiKey` default.
    pub fn parse(raw: &str) -> Result<UpstreamAuthMode> {
        match raw.trim().to_ascii_lowercase().as_str() {
            "" | "api_key" => Ok(UpstreamAuthMode::ApiKey),
            "oauth" => Ok(UpstreamAuthMode::OAuth),
            other => bail!(
                "invalid FOUNDRY_SERVICE_UPSTREAM_AUTH '{other}': expected 'api_key' or 'oauth'"
            ),
        }
    }
}

/// The upstream-auth configuration resolved from the environment. Not a
/// field of `ServiceConfig` -- kept separate so `ServiceConfig`'s struct
/// literal (built in test helpers outside `src/service/`) is unchanged.
#[derive(Clone, Debug)]
pub struct UpstreamAuthConfig {
    pub mode: UpstreamAuthMode,
    /// `ANTHROPIC_API_KEY` (also held by `ServiceConfig.anthropic_api_key`).
    pub api_key: String,
    /// `FOUNDRY_SERVICE_OAUTH_TOKEN` -- long-lived OAuth access token
    /// (the kind produced by `claude setup-token`).
    pub oauth_token: String,
    /// `FOUNDRY_SERVICE_OAUTH_REFRESH_TOKEN` -- empty if not configured.
    pub oauth_refresh_token: String,
    /// `FOUNDRY_SERVICE_OAUTH_CLIENT_ID` -- empty if not configured.
    pub oauth_client_id: String,
    /// `FOUNDRY_SERVICE_OAUTH_REFRESH_URL` -- the OAuth token endpoint.
    pub oauth_refresh_url: String,
    /// `FOUNDRY_SERVICE_OAUTH_EXPIRES_AT` (unix seconds) -> `None` when unset.
    pub oauth_expires_at: Option<SystemTime>,
}

/// Read every upstream-auth env var into an [`UpstreamAuthConfig`]. `api_key`
/// is passed in (rather than re-read) so it stays the single value the rest of
/// `ServiceConfig` already holds. `Err` only on an invalid mode string or an
/// unparseable expiry.
pub fn resolve_upstream_auth(api_key: &str) -> Result<UpstreamAuthConfig> {
    let mode = UpstreamAuthMode::parse(&env_or("FOUNDRY_SERVICE_UPSTREAM_AUTH", "api_key"))
        .context("parse FOUNDRY_SERVICE_UPSTREAM_AUTH")?;
    let raw_exp = env_or("FOUNDRY_SERVICE_OAUTH_EXPIRES_AT", "");
    let oauth_expires_at = if raw_exp.is_empty() {
        None
    } else {
        let secs: u64 = raw_exp
            .parse()
            .context("parse FOUNDRY_SERVICE_OAUTH_EXPIRES_AT as unix seconds")?;
        UNIX_EPOCH.checked_add(Duration::from_secs(secs))
    };
    Ok(UpstreamAuthConfig {
        mode,
        api_key: api_key.to_string(),
        oauth_token: env_or("FOUNDRY_SERVICE_OAUTH_TOKEN", ""),
        oauth_refresh_token: env_or("FOUNDRY_SERVICE_OAUTH_REFRESH_TOKEN", ""),
        oauth_client_id: env_or("FOUNDRY_SERVICE_OAUTH_CLIENT_ID", ""),
        oauth_refresh_url: env_or(
            "FOUNDRY_SERVICE_OAUTH_REFRESH_URL",
            "https://console.anthropic.com/v1/oauth/token",
        ),
        oauth_expires_at,
    })
}

/// Fail fast when the selected upstream-auth mode lacks its credential, or
/// when `api_key` mode is genuinely ambiguous (both credentials present).
///
/// In `oauth` mode a present `ANTHROPIC_API_KEY` is ignored, not rejected:
/// the explicit `FOUNDRY_SERVICE_UPSTREAM_AUTH=oauth` selector already states
/// intent, and `ANTHROPIC_API_KEY` is a near-universal exported env var.
/// Error messages name env vars only -- never the credential value.
pub fn validate_upstream_credentials(cfg: &UpstreamAuthConfig) -> Result<()> {
    let has_api_key = !cfg.api_key.is_empty();
    let has_oauth = !cfg.oauth_token.is_empty();
    match cfg.mode {
        UpstreamAuthMode::ApiKey => {
            if !has_api_key {
                bail!("upstream_auth=api_key requires ANTHROPIC_API_KEY but it is empty");
            }
            if has_oauth {
                bail!(
                    "upstream_auth=api_key but FOUNDRY_SERVICE_OAUTH_TOKEN is also set; \
                     provide exactly one credential"
                );
            }
        }
        UpstreamAuthMode::OAuth => {
            if !has_oauth {
                bail!("upstream_auth=oauth requires FOUNDRY_SERVICE_OAUTH_TOKEN but it is empty");
            }
        }
    }
    Ok(())
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
        let build_timeout_secs: u64 = env_or("FOUNDRY_SERVICE_BUILD_TIMEOUT_SECS", "3600")
            .parse()
            .context("parse FOUNDRY_SERVICE_BUILD_TIMEOUT_SECS")?;
        let drain_deadline_secs: u64 = env_or("FOUNDRY_SERVICE_DRAIN_DEADLINE_SECS", "30")
            .parse()
            .context("parse FOUNDRY_SERVICE_DRAIN_DEADLINE_SECS")?;
        let max_concurrent_builds: usize =
            env_or("FOUNDRY_SERVICE_MAX_CONCURRENT_BUILDS", "3")
                .parse()
                .context("parse FOUNDRY_SERVICE_MAX_CONCURRENT_BUILDS")?;
        let build_pids_limit: u32 = env_or("FOUNDRY_SERVICE_BUILD_PIDS_LIMIT", "512")
            .parse()
            .context("parse FOUNDRY_SERVICE_BUILD_PIDS_LIMIT")?;

        let anthropic_api_key = env_or("ANTHROPIC_API_KEY", "");
        let upstream_auth =
            resolve_upstream_auth(&anthropic_api_key).context("resolve upstream auth config")?;
        // The mock build backend never forwards through the auth proxy, so a
        // missing upstream credential is tolerated there -- this preserves the
        // pre-T35.7d behavior where from_env() did not validate
        // ANTHROPIC_API_KEY. Fail-fast validation runs for a real build
        // backend, or whenever the operator explicitly selected an upstream
        // auth mode via FOUNDRY_SERVICE_UPSTREAM_AUTH.
        let upstream_auth_explicit = !env_or("FOUNDRY_SERVICE_UPSTREAM_AUTH", "").is_empty();
        if build_backend != "mock" || upstream_auth_explicit {
            validate_upstream_credentials(&upstream_auth)
                .context("validate upstream auth credentials")?;
        }

        Ok(ServiceConfig {
            database_url: env_or(
                "FOUNDRY_SERVICE_DATABASE_URL",
                "postgres://foundry:foundry@localhost:5432/foundry",
            ),
            bind_addr,
            proxy_bind_addr,
            api_keys: split_csv(&env_or("FOUNDRY_SERVICE_API_KEYS", "")),
            anthropic_api_key,
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
            build_timeout_secs,
            drain_deadline_secs,
            max_concurrent_builds,
            build_memory: env_or("FOUNDRY_SERVICE_BUILD_MEMORY", "4g"),
            build_cpus: env_or("FOUNDRY_SERVICE_BUILD_CPUS", "2"),
            build_pids_limit,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Build an `UpstreamAuthConfig` with the given mode/api_key/oauth_token
    /// and empty refresh/client/url/expiry fields.
    fn ua(mode: UpstreamAuthMode, api_key: &str, oauth_token: &str) -> UpstreamAuthConfig {
        UpstreamAuthConfig {
            mode,
            api_key: api_key.to_string(),
            oauth_token: oauth_token.to_string(),
            oauth_refresh_token: String::new(),
            oauth_client_id: String::new(),
            oauth_refresh_url: String::new(),
            oauth_expires_at: None,
        }
    }

    #[test]
    fn upstream_auth_mode_parse_accepts_known_values() {
        assert_eq!(
            UpstreamAuthMode::parse("api_key").unwrap(),
            UpstreamAuthMode::ApiKey
        );
        assert_eq!(UpstreamAuthMode::parse("").unwrap(), UpstreamAuthMode::ApiKey);
        assert_eq!(
            UpstreamAuthMode::parse("OAuth").unwrap(),
            UpstreamAuthMode::OAuth
        );
        assert_eq!(
            UpstreamAuthMode::parse("oauth ").unwrap(),
            UpstreamAuthMode::OAuth
        );
    }

    #[test]
    fn upstream_auth_mode_parse_rejects_garbage() {
        assert!(UpstreamAuthMode::parse("bogus").is_err());
    }

    #[test]
    fn validate_api_key_mode_missing_key_errs() {
        assert!(validate_upstream_credentials(&ua(UpstreamAuthMode::ApiKey, "", "")).is_err());
    }

    #[test]
    fn validate_api_key_mode_ambiguous_errs() {
        assert!(
            validate_upstream_credentials(&ua(UpstreamAuthMode::ApiKey, "sk-x", "oauth-tok"))
                .is_err()
        );
    }

    #[test]
    fn validate_api_key_mode_ok() {
        assert!(validate_upstream_credentials(&ua(UpstreamAuthMode::ApiKey, "sk-x", "")).is_ok());
    }

    #[test]
    fn validate_oauth_mode_missing_token_errs() {
        assert!(validate_upstream_credentials(&ua(UpstreamAuthMode::OAuth, "", "")).is_err());
    }

    #[test]
    fn validate_oauth_mode_ignores_present_api_key() {
        // Deviation from the original plan test `validate_oauth_mode_ambiguous_errs`:
        // per unresolved plan-review feedback, `oauth` mode tolerates a
        // present-but-unused ANTHROPIC_API_KEY rather than refusing startup.
        assert!(
            validate_upstream_credentials(&ua(UpstreamAuthMode::OAuth, "sk-x", "oauth-tok"))
                .is_ok()
        );
    }

    #[test]
    fn validate_oauth_mode_ok() {
        assert!(
            validate_upstream_credentials(&ua(UpstreamAuthMode::OAuth, "", "oauth-tok")).is_ok()
        );
    }
}
