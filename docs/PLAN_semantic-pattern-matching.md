# Plan: Semantic Pattern Matching via Local Embeddings
Date: 2026-03-13
Version: v3 (revised after Codex v2 review)
Status: ready

## Context
Pattern matching currently uses keyword/substring lookup, which misses semantic
connections (e.g. "build a korg 808 emulator" should match design patterns but
doesn't because no keyword matches). Local Ollama with nomic-embed-text can
provide semantic matching without API costs or latency.

## Current State
- Pattern matching: `patterns::match_patterns()` in src/patterns.rs:85 (synchronous)
- Build loop calls it inline at build.rs:159 on the async task hot path
- `load_patterns()` reads ALL .json files in patterns dir
- Ollama installed at /opt/homebrew/bin/ollama

## Implementation Steps

- [ ] Step 1 -- Define canonical text functions
  - `pattern_embedding_text(pattern) -> String`: "{title}. {issue}"
  - `normalize_task_text(task_desc) -> String`: strip task ID prefix, lowercase, trim
  - Both functions are pure, deterministic, testable

- [ ] Step 2 -- Add config fields to .foundry.json (all optional, serde defaults)
  - `semantic_match_enabled: bool` (default: true)
  - `embedding_model: String` (default: "nomic-embed-text")
  - `embedding_timeout_ms: u64` (default: 2000)

- [ ] Step 3 -- Add async Ollama embedding client (new file: src/embeddings.rs)
  - `async fn embed_batch(texts: &[&str], model: &str, timeout_ms: u64) -> Result<Vec<Vec<f32>>>`
  - HTTP POST to http://127.0.0.1:11434/api/embed with array input
  - Uses reqwest or hyper (check existing deps first)
  - Explicit timeout from config
  - Returns Result, caller handles errors

- [ ] Step 4 -- Add circuit breaker (in src/embeddings.rs)
  - `struct OllamaState { cooldown_until_ms: AtomicU64 }`
  - Store wall-clock millis from SystemTime (not Instant -- AtomicU64-safe)
  - After any Ollama failure: set cooldown_until_ms = now + 60_000
  - Before any call: check if now < cooldown_until_ms, skip if so
  - Module-level static via OnceLock<OllamaState>
  - `fn is_available() -> bool` and `fn mark_failed()`

- [ ] Step 5 -- Add embedding cache (in src/embeddings.rs)
  - Location: ~/.foundry/cache/pattern-embeddings.json
  - Resolve ~ with same HOME fallback as patterns.rs:41 (with /tmp fallback)
  - Create ~/.foundry/cache/ dir on first write
  - Schema:
    ```json
    {
      "schema_version": 1,
      "entries": {
        "pattern-id": {
          "model": "nomic-embed-text",
          "content_hash": "blake3-hex-string",
          "embedding": [0.1, 0.2, ...]
        }
      }
    }
    ```
  - content_hash: blake3 hash of pattern_embedding_text() UTF-8 bytes (hex-encoded)
  - On load: discard entries where model != config or content_hash != current
  - Lazy fill: compute missing embeddings on first match call via batch embed
  - Log cache hit rate ("semantic cache: 12/15 hit, 3 computed")

- [ ] Step 6 -- Add similarity function (in src/embeddings.rs)
  - `fn cosine_similarity(a: &[f32], b: &[f32]) -> f32`
  - Normalize vectors explicitly at cache-write time (don't assume Ollama normalizes)
  - Cosine = dot product of pre-normalized vectors
  - Threshold: 0.35 (log scores for tuning, don't hardcode as the only knob)

- [ ] Step 7 -- Add async semantic matcher (in src/patterns.rs)
  - `async fn match_patterns_semantic(patterns, task_desc, config) -> Vec<&Pattern>`
  - Check circuit breaker -> if cooldown, fall back to keyword-only
  - Embed task description (normalize_task_text first)
  - Load/fill cache for pattern embeddings
  - First pass: keyword scoring (existing logic)
  - Second pass: compute similarity for all patterns
  - Rerank: patterns above threshold get boost = similarity * 10
  - Final score = keyword_score + semantic_boost
  - Log matching mode: "semantic", "keyword-only", "cooldown"

- [ ] Step 8 -- Integrate into build loop (build.rs)
  - Replace synchronous match_patterns() call with async match_patterns_semantic()
  - This is already in an async context (build_loop is async)
  - Fallback: if semantic matcher returns error, use keyword matcher result
  - No changes to prompt injection (format_patterns_for_prompt stays the same)

- [ ] Step 9 -- Tests
  - Unit: pattern_embedding_text() and normalize_task_text() produce expected output
  - Unit: cosine_similarity with known vectors (hand-computed expected values)
  - Unit: vector normalization is applied at cache write
  - Unit: cache load/save round-trip, stale entry discard (wrong model, changed hash)
  - Unit: circuit breaker enters cooldown, recovers after duration
  - Unit: hybrid scorer boosts semantic matches, doesn't drop keyword matches
  - Unit: cache file is NOT loaded by load_patterns() (lives outside patterns dir)
  - Integration: keyword-only fallback when Ollama is unavailable
  - Integration: semantic matching finds a pattern with zero keyword overlap

## Architecture Decisions
- **Async boundary**: matcher is async, called from async build loop. No blocking HTTP on the task hot path.
- **blake3 for content hash**: stable, fast, deterministic. Not Rust's default hasher (which isn't stable across versions).
- **Explicit normalization**: normalize vectors at write time, don't assume Ollama behavior.
- **Wall-clock millis for cooldown**: AtomicU64-safe, no Instant serialization issues.
- **Cache outside patterns dir**: ~/.foundry/cache/ prevents load_patterns() collision.
- **HOME fallback**: same discipline as patterns.rs resolver.
- **Lazy cache fill**: works for TUI, headless, and plan mode entry points.
- **Reranking not raw addition**: keyword results are baseline, semantic is a boost layer.
- **No auto-start Ollama**: detect, try, back off. Auto-start is platform-specific.

## Dependencies
- blake3 crate (for stable content hashing)
- reqwest or hyper (for HTTP -- check if already in Cargo.toml)
- serde_json (already present)

## Risks
- First-call latency when cache is empty (batch embed may take 1-2s for all patterns)
- Similarity threshold needs tuning with real task descriptions (log and adjust)
- blake3 adds a new dependency (~small, pure Rust)
