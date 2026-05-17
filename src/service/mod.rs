//! Context Foundry build service (`foundry serve`) — M1 skeleton.
//!
//! A long-running HTTP control plane: an axum `/v1` API, a Postgres-backed
//! job store, a worker pool that drives builds through a [`backend::BuildBackend`],
//! a TTL reaper, and an Anthropic auth proxy. M1 wires the
//! [`mock_backend::MockBuildBackend`] (replays a recorded event stream) and
//! [`storage_local::LocalFilesystem`]; real Docker builds land in M2 (T35.4).

pub mod api;
pub mod backend;
pub mod caddy;
pub mod config;
pub mod db;
pub mod localdocker;
pub mod mock_backend;
pub mod models;
pub mod proxy;
pub mod ratelimit;
pub mod reaper;
pub mod storage_local;
pub mod telemetry;
pub mod worker;

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::Duration;

use anyhow::{Context, Result};
use sqlx::PgPool;
use tokio::sync::Semaphore;

/// Shared application state handed to every axum handler and worker.
pub struct AppState {
    pub pool: PgPool,
    pub config: config::ServiceConfig,
    pub storage: Arc<dyn backend::StorageBackend>,
    pub build: Arc<dyn backend::BuildBackend>,
    pub proxy: Arc<proxy::ProxyRegistry>,
    /// Global build-concurrency gate: workers acquire a permit before claiming
    /// a job, so in-flight builds are capped independently of `worker_count`.
    pub build_slots: Arc<Semaphore>,
    /// Structured service telemetry (backend failures, limiter denials, status transitions).
    pub telemetry: Arc<telemetry::Telemetry>,
}

/// Entry point for the `foundry serve` subcommand.
///
/// Boots the Postgres pool, applies migrations, reconciles jobs left mid-build
/// by a previous process, then runs the worker pool, TTL reaper, auth proxy,
/// and `/v1` API until the process is killed. Graceful SIGTERM drain is M4.
pub async fn run_serve() -> Result<()> {
    let config = config::ServiceConfig::from_env()?;
    let pool = db::connect(&config).await?;
    db::run_migrations(&pool).await?;

    let storage: Arc<dyn backend::StorageBackend> =
        Arc::new(storage_local::LocalFilesystem::new(config.storage_root.clone()));
    let build: Arc<dyn backend::BuildBackend> = match config.build_backend.as_str() {
        "local_docker" => {
            let preview = localdocker::PreviewConfig {
                network: config.preview_network.clone(),
                base_domain: config.preview_base_domain.clone(),
                caddy_admin_url: config.caddy_admin_url.clone(),
                caddy_server_name: config.caddy_server_name.clone(),
                container_port: 8080,
                health_timeout_secs: config.preview_health_timeout_secs,
                memory: config.preview_memory.clone(),
                cpus: config.preview_cpus.clone(),
                pids_limit: config.preview_pids_limit,
            };
            Arc::new(
                localdocker::LocalDocker::new(
                    config.builder_image.clone(),
                    config.storage_root.clone(),
                    config.builder_proxy_url.clone(),
                    config.docker_bin.clone(),
                )
                .with_preview_config(preview)
                .with_build_limits(localdocker::BuildLimits {
                    memory: config.build_memory.clone(),
                    cpus: config.build_cpus.clone(),
                    pids_limit: config.build_pids_limit,
                }),
            )
        }
        _ => Arc::new(mock_backend::MockBuildBackend::new()),
    };
    let proxy = Arc::new(proxy::ProxyRegistry::new(config.clone()));
    // `.max(1)` guards against a misconfigured `0`, which would otherwise
    // deadlock every worker on the build-slots gate.
    let build_slots = Arc::new(Semaphore::new(config.max_concurrent_builds.max(1)));
    let telemetry = Arc::new(telemetry::Telemetry::new());

    let state = Arc::new(AppState {
        pool,
        config,
        storage,
        build,
        proxy,
        build_slots,
        telemetry,
    });

    // Reconcile jobs left mid-build by a dead process, then kill any
    // containers they orphaned. The reconciled jobs are already terminal
    // (`failed`), so the LLM build is never silently re-run.
    let reconciled = db::reconcile_startup(&state.pool)
        .await
        .context("reconcile jobs on startup")?;
    for id in &reconciled {
        let _ = state.build.teardown(id).await;
    }

    let shutdown = Arc::new(AtomicBool::new(false));
    let workers = worker::run_worker_pool(state.clone(), shutdown.clone());
    tokio::spawn(reaper::run_reaper(state.clone(), shutdown.clone()));
    tokio::spawn(proxy::serve_proxy(state.clone()));

    let listener = tokio::net::TcpListener::bind(state.config.bind_addr)
        .await
        .with_context(|| format!("bind service listener on {}", state.config.bind_addr))?;
    eprintln!(
        "foundry service: API on {}, proxy on {}",
        state.config.bind_addr, state.config.proxy_bind_addr
    );

    axum::serve(listener, api::router(state.clone()))
        .with_graceful_shutdown(shutdown_signal())
        .await
        .context("serve /v1 API")?;

    // SIGTERM/SIGINT received: stop new claims, drain in-flight workers to a
    // deadline. Stragglers past the deadline are caught by next-start
    // reconciliation, so no LLM build is ever silently re-run.
    eprintln!(
        "foundry service: shutdown signal received; stopping new claims, draining workers"
    );
    shutdown.store(true, Ordering::Relaxed);
    let deadline = Duration::from_secs(state.config.drain_deadline_secs);
    if tokio::time::timeout(deadline, async {
        for h in workers {
            let _ = h.await;
        }
    })
    .await
    .is_err()
    {
        eprintln!(
            "foundry service: drain deadline exceeded; stragglers reconciled on next start"
        );
    }
    Ok(())
}

/// Resolve when the process receives SIGTERM or SIGINT (Ctrl-C).
async fn shutdown_signal() {
    let ctrl_c = async {
        let _ = tokio::signal::ctrl_c().await;
    };
    #[cfg(unix)]
    let terminate = async {
        match tokio::signal::unix::signal(tokio::signal::unix::SignalKind::terminate()) {
            Ok(mut sig) => {
                sig.recv().await;
            }
            Err(_) => std::future::pending::<()>().await,
        }
    };
    #[cfg(not(unix))]
    let terminate = std::future::pending::<()>();
    tokio::select! {
        _ = ctrl_c => {}
        _ = terminate => {}
    }
}
