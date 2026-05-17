//! Library surface for the `foundry` crate.
//!
//! The binary (`src/main.rs`) keeps its own module tree; this library target
//! exists so the build-service control plane (`foundry serve`) is reachable
//! from integration tests under `tests/`. Integration tests are separate
//! crates and can only link a library target, so `service` lives here.

pub mod service;
