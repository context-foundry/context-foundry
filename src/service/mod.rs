//! Context Foundry build service (`foundry serve`) — M1 skeleton.
//!
//! A long-running HTTP control plane: an axum `/v1` API, a Postgres-backed
//! job store, a worker pool that drives builds through a [`backend::BuildBackend`],
//! a TTL reaper, and an Anthropic auth proxy. M1 wires the
//! [`mock_backend::MockBuildBackend`] (replays a recorded event stream) and
//! [`storage_local::LocalFilesystem`]; real Docker builds land in M2 (T35.4).

pub mod api;
pub mod backend;
pub mod config;
pub mod db;
pub mod mock_backend;
pub mod models;
pub mod proxy;
pub mod reaper;
pub mod storage_local;
pub mod worker;

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;

use anyhow::{Context, Result};
use sqlx::PgPool;

/// Shared application state handed to every axum handler and worker.
pub struct AppState {
    pub pool: PgPool,
    pub config: config::ServiceConfig,
    pub storage: Arc<dyn backend::StorageBackend>,
    pub build: Arc<dyn backend::BuildBackend>,
    pub proxy: Arc<proxy::ProxyRegistry>,
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
    let build: Arc<dyn backend::BuildBackend> = Arc::new(mock_backend::MockBuildBackend::new());
    let proxy = Arc::new(proxy::ProxyRegistry::new(config.clone()));

    let state = Arc::new(AppState {
        pool,
        config,
        storage,
        build,
        proxy,
    });

    db::reconcile_startup(&state.pool)
        .await
        .context("reconcile jobs on startup")?;

    let shutdown = Arc::new(AtomicBool::new(false));
    let _workers = worker::run_worker_pool(state.clone(), shutdown.clone());
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
        .await
        .context("serve /v1 API")?;

    shutdown.store(true, Ordering::Relaxed);
    Ok(())
}
