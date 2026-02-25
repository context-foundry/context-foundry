---
paths:
  - "src/**/*.rs"
---

# Rust Conventions

## Error Handling
- Use `anyhow::Result<T>` everywhere — no custom error enums.
- Wrap errors with `.context("descriptive message")`.
- Use `.unwrap_or(default)` for graceful fallbacks.
- Best-effort operations (git push, file cleanup) use `let _ = operation()`.

## Async / Concurrency
- Tokio runtime with `#[tokio::main]`.
- `tokio::spawn` for fire-and-forget background tasks.
- `mpsc::unbounded_channel` for fan-out event streams (agent output → TUI).
- `oneshot::channel` for request-response patterns.
- Blocking operations (PTY reads) go on `tokio::task::spawn_blocking`.

## Code Style
- 4-space indentation.
- Trailing commas in multi-line structs/enums/function args.
- Section separators: `// ─── Section Name ───────────────────────────`
- Explicit `use` statements — no wildcard imports.
- `&str` for borrowed string params, `String` for owned. `&Path` / `PathBuf` likewise.

## Serde Patterns
- `#[serde(default)]` on config structs for backward compatibility.
- All config fields optional with `Default` impls.
- Pattern files support both single-object and array JSON formats.

## Testing
- Unit tests in `#[cfg(test)]` blocks at end of module.
- Test function naming: `#[test] fn test_descriptive_name()`.
