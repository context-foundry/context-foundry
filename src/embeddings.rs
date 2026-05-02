use std::collections::{HashMap, HashSet};
use std::path::PathBuf;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::OnceLock;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use serde::{Deserialize, Serialize};

use crate::patterns::Pattern;
use crate::utils::atomic_write_file_best_effort;

// ─── Config ──────────────────────────────────────────────────

// Ollama URL is now configurable via Config.ollama_url
const COOLDOWN_MS: u64 = 60_000;
const CACHE_SCHEMA_VERSION: u32 = 1;

// ─── Circuit Breaker ─────────────────────────────────────────

struct OllamaState {
    cooldown_until_ms: AtomicU64,
}

static OLLAMA_STATE: OnceLock<OllamaState> = OnceLock::new();

fn state() -> &'static OllamaState {
    OLLAMA_STATE.get_or_init(|| OllamaState {
        cooldown_until_ms: AtomicU64::new(0),
    })
}

fn now_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or(Duration::ZERO)
        .as_millis() as u64
}

pub fn is_available() -> bool {
    now_ms() >= state().cooldown_until_ms.load(Ordering::Relaxed)
}

fn mark_failed() {
    state()
        .cooldown_until_ms
        .store(now_ms() + COOLDOWN_MS, Ordering::Relaxed);
}

#[cfg(test)]
fn force_cooldown(until_ms: u64) {
    state().cooldown_until_ms.store(until_ms, Ordering::Relaxed);
}

#[cfg(test)]
fn clear_cooldown() {
    state().cooldown_until_ms.store(0, Ordering::Relaxed);
}

// ─── Canonical Text ──────────────────────────────────────────

pub fn pattern_embedding_text(pattern: &Pattern) -> String {
    let title = &pattern.title;
    let issue = pattern.issue.as_deref().unwrap_or("");
    if issue.is_empty() {
        title.to_string()
    } else {
        format!("{title}. {issue}")
    }
}

pub fn normalize_task_text(task_desc: &str) -> String {
    // Strip task ID prefix like "T1.1: " or "D2.3: " or "H1.1: "
    let stripped = if let Some(pos) = task_desc.find(": ") {
        let prefix = &task_desc[..pos];
        let looks_like_id = prefix.len() <= 8
            && prefix
                .chars()
                .all(|c| c.is_ascii_alphanumeric() || c == '.');
        if looks_like_id {
            &task_desc[pos + 2..]
        } else {
            task_desc
        }
    } else {
        task_desc
    };
    stripped.trim().to_lowercase()
}

// ─── Ollama Client ───────────────────────────────────────────

fn embed_batch_sync(
    texts: &[String],
    model: &str,
    timeout_ms: u64,
    ollama_url: &str,
) -> Result<Vec<Vec<f32>>, String> {
    let body = serde_json::json!({
        "model": model,
        "input": texts,
    });

    let timeout_secs = (timeout_ms as f64 / 1000.0).max(1.0);
    let url = format!("{}/api/embed", ollama_url);
    let output = std::process::Command::new("curl")
        .args([
            "-s",
            "-X",
            "POST",
            &url,
            "-H",
            "Content-Type: application/json",
            "-d",
            &body.to_string(),
            "--max-time",
            &format!("{:.0}", timeout_secs),
        ])
        .output()
        .map_err(|e| format!("curl failed: {}", e))?;

    if !output.status.success() {
        return Err(format!(
            "Ollama returned status {}",
            output.status.code().unwrap_or(-1)
        ));
    }

    let resp: OllamaEmbedResponse = serde_json::from_slice(&output.stdout)
        .map_err(|e| format!("Ollama response parse failed: {}", e))?;

    Ok(resp.embeddings)
}

#[derive(Deserialize)]
struct OllamaEmbedResponse {
    embeddings: Vec<Vec<f32>>,
}

pub async fn embed_batch(
    texts: &[String],
    model: &str,
    timeout_ms: u64,
    ollama_url: &str,
) -> Result<Vec<Vec<f32>>, String> {
    if texts.is_empty() {
        return Ok(Vec::new());
    }

    let texts = texts.to_vec();
    let model = model.to_string();
    let url = ollama_url.to_string();

    tokio::task::spawn_blocking(move || embed_batch_sync(&texts, &model, timeout_ms, &url))
        .await
        .map_err(|e| format!("embed task panicked: {}", e))?
}

// ─── Vector Math ─────────────────────────────────────────────

pub fn normalize(v: &[f32]) -> Vec<f32> {
    let mag: f32 = v.iter().map(|x| x * x).sum::<f32>().sqrt();
    if mag < 1e-10 {
        return v.to_vec();
    }
    v.iter().map(|x| x / mag).collect()
}

pub fn cosine_similarity(a: &[f32], b: &[f32]) -> f32 {
    if a.len() != b.len() || a.is_empty() {
        return 0.0;
    }
    // Vectors are pre-normalized at cache write time
    a.iter().zip(b.iter()).map(|(x, y)| x * y).sum()
}

// ─── Cache ───────────────────────────────────────────────────

#[derive(Serialize, Deserialize)]
struct EmbeddingCache {
    schema_version: u32,
    entries: HashMap<String, CacheEntry>,
}

#[derive(Serialize, Deserialize, Clone)]
struct CacheEntry {
    model: String,
    content_hash: String,
    embedding: Vec<f32>,
}

fn cache_dir() -> PathBuf {
    let base = if cfg!(target_os = "windows") {
        std::env::var("LOCALAPPDATA")
            .or_else(|_| std::env::var("USERPROFILE"))
            .ok()
    } else {
        std::env::var("HOME").ok()
    };
    if let Some(base) = base {
        PathBuf::from(base).join(".foundry/cache")
    } else {
        let fallback = std::env::temp_dir().join(".foundry").join("cache");
        eprintln!(
            "warning: HOME not set, using {} for embedding cache",
            fallback.display()
        );
        fallback
    }
}

fn cache_path() -> PathBuf {
    cache_dir().join("pattern-embeddings.json")
}

fn content_hash(text: &str) -> String {
    blake3::hash(text.as_bytes()).to_hex().to_string()
}

fn load_cache_from(path: &std::path::Path) -> EmbeddingCache {
    match std::fs::read_to_string(path) {
        Ok(data) => serde_json::from_str(&data).unwrap_or(EmbeddingCache {
            schema_version: CACHE_SCHEMA_VERSION,
            entries: HashMap::new(),
        }),
        Err(_) => EmbeddingCache {
            schema_version: CACHE_SCHEMA_VERSION,
            entries: HashMap::new(),
        },
    }
}

fn load_cache() -> EmbeddingCache {
    load_cache_from(&cache_path())
}

fn save_cache_to(path: &std::path::Path, cache: &EmbeddingCache, current_patterns: &[Pattern]) {
    let valid_hashes: HashSet<String> = current_patterns
        .iter()
        .map(|p| content_hash(&pattern_embedding_text(p)))
        .collect();

    let pruned = EmbeddingCache {
        schema_version: cache.schema_version,
        entries: cache
            .entries
            .iter()
            .filter(|(_, entry)| valid_hashes.contains(&entry.content_hash))
            .map(|(k, v)| (k.clone(), v.clone()))
            .collect(),
    };

    if let Some(parent) = path.parent() {
        let _ = std::fs::create_dir_all(parent);
    }
    if let Ok(data) = serde_json::to_string_pretty(&pruned) {
        atomic_write_file_best_effort(path, data.as_bytes());
    }
}

fn save_cache(cache: &EmbeddingCache, current_patterns: &[Pattern]) {
    save_cache_to(&cache_path(), cache, current_patterns);
}

// ─── Semantic Matcher ────────────────────────────────────────

pub struct SemanticMatchResult {
    pub mode: &'static str, // "semantic", "keyword-only", "cooldown"
    pub cache_hits: usize,
    pub cache_misses: usize,
}

pub async fn match_patterns_semantic<'a>(
    patterns: &'a [Pattern],
    task_desc: &str,
    model: &str,
    timeout_ms: u64,
    keyword_scores: &[(usize, usize)], // (pattern_index, keyword_score)
    ollama_url: &str,
) -> (Vec<(&'a Pattern, usize)>, SemanticMatchResult) {
    // Start with keyword scores
    let mut scores: Vec<(usize, usize)> = keyword_scores.to_vec();

    // No patterns = nothing to embed, skip Ollama entirely
    if patterns.is_empty() {
        return (
            finalize_scores(patterns, &scores),
            SemanticMatchResult {
                mode: "keyword-only",
                cache_hits: 0,
                cache_misses: 0,
            },
        );
    }

    if !is_available() {
        return (
            finalize_scores(patterns, &scores),
            SemanticMatchResult {
                mode: "cooldown",
                cache_hits: 0,
                cache_misses: 0,
            },
        );
    }

    // Load cache and determine which patterns need embedding
    let mut cache = load_cache();
    if cache.schema_version != CACHE_SCHEMA_VERSION {
        cache = EmbeddingCache {
            schema_version: CACHE_SCHEMA_VERSION,
            entries: HashMap::new(),
        };
    }

    let mut pattern_texts: Vec<(usize, String)> = Vec::new(); // (index, text)
    let mut cached_embeddings: Vec<(usize, Vec<f32>)> = Vec::new();
    let mut cache_hits = 0usize;
    let mut cache_misses = 0usize;

    for (i, pattern) in patterns.iter().enumerate() {
        let text = pattern_embedding_text(pattern);
        let hash = content_hash(&text);
        // Cache key = model:content_hash (not pattern_id, which can collide across files)
        let cache_key = format!("{}:{}", model, hash);

        if let Some(entry) = cache.entries.get(&cache_key) {
            if entry.model == model && entry.content_hash == hash {
                cached_embeddings.push((i, entry.embedding.clone()));
                cache_hits += 1;
                continue;
            }
        }
        pattern_texts.push((i, text));
        cache_misses += 1;
    }

    // Batch embed missing patterns
    if !pattern_texts.is_empty() {
        let texts: Vec<String> = pattern_texts.iter().map(|(_, t)| t.clone()).collect();
        match embed_batch(&texts, model, timeout_ms, ollama_url).await {
            Ok(embeddings) => {
                for ((idx, text), embedding) in pattern_texts.iter().zip(embeddings.iter()) {
                    let normalized = normalize(embedding);
                    let hash = content_hash(text);
                    let cache_key = format!("{}:{}", model, hash);
                    cache.entries.insert(
                        cache_key,
                        CacheEntry {
                            model: model.to_string(),
                            content_hash: hash,
                            embedding: normalized.clone(),
                        },
                    );
                    cached_embeddings.push((*idx, normalized));
                }
                save_cache(&cache, patterns);
            }
            Err(_) => {
                mark_failed();
                return (
                    finalize_scores(patterns, &scores),
                    SemanticMatchResult {
                        mode: "keyword-only",
                        cache_hits,
                        cache_misses,
                    },
                );
            }
        }
    }

    // Embed the task description
    let task_text = normalize_task_text(task_desc);
    let task_embedding = match embed_batch(&[task_text], model, timeout_ms, ollama_url).await {
        Ok(mut embeddings) if !embeddings.is_empty() => normalize(&embeddings.remove(0)),
        _ => {
            mark_failed();
            return (
                finalize_scores(patterns, &scores),
                SemanticMatchResult {
                    mode: "keyword-only",
                    cache_hits,
                    cache_misses,
                },
            );
        }
    };

    // Compute similarities and boost scores
    let threshold = 0.35f32;
    for (idx, embedding) in &cached_embeddings {
        let similarity = cosine_similarity(&task_embedding, embedding);
        if similarity > threshold {
            let boost = (similarity * 10.0) as usize;
            if let Some(entry) = scores.iter_mut().find(|(i, _)| i == idx) {
                entry.1 += boost;
            } else {
                scores.push((*idx, boost));
            }
        }
    }

    (
        finalize_scores(patterns, &scores),
        SemanticMatchResult {
            mode: "semantic",
            cache_hits,
            cache_misses,
        },
    )
}

fn finalize_scores<'a>(
    patterns: &'a [Pattern],
    scores: &[(usize, usize)],
) -> Vec<(&'a Pattern, usize)> {
    let mut result: Vec<(&Pattern, usize)> = scores
        .iter()
        .filter(|(_, score)| *score > 0)
        .filter_map(|(idx, score)| patterns.get(*idx).map(|p| (p, *score)))
        .collect();
    result.sort_by_key(|a| std::cmp::Reverse(a.1));
    result
}

// ─── Tests ───────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;
    use serial_test::serial;

    #[test]
    fn pattern_embedding_text_combines_title_and_issue() {
        let pattern = Pattern {
            pattern_id: "test".into(),
            title: "Fix auth flow".into(),
            issue: Some("Login fails on redirect".into()),
            ..default_test_pattern()
        };
        assert_eq!(
            pattern_embedding_text(&pattern),
            "Fix auth flow. Login fails on redirect"
        );
    }

    #[test]
    fn pattern_embedding_text_uses_title_only_when_no_issue() {
        let pattern = Pattern {
            pattern_id: "test".into(),
            title: "Fix auth flow".into(),
            issue: None,
            ..default_test_pattern()
        };
        assert_eq!(pattern_embedding_text(&pattern), "Fix auth flow");
    }

    #[test]
    fn normalize_task_text_strips_id_prefix() {
        assert_eq!(
            normalize_task_text("T1.1: Build the login page"),
            "build the login page"
        );
        assert_eq!(
            normalize_task_text("D2.3: Fix broken import"),
            "fix broken import"
        );
        assert_eq!(
            normalize_task_text("H1.1: Add smiley face"),
            "add smiley face"
        );
    }

    #[test]
    fn normalize_task_text_preserves_text_without_id() {
        assert_eq!(
            normalize_task_text("Build a korg 808 emulator"),
            "build a korg 808 emulator"
        );
    }

    #[test]
    fn cosine_similarity_of_identical_normalized_vectors() {
        let v = normalize(&[1.0, 2.0, 3.0]);
        let sim = cosine_similarity(&v, &v);
        assert!((sim - 1.0).abs() < 1e-5);
    }

    #[test]
    fn cosine_similarity_of_orthogonal_vectors() {
        let a = normalize(&[1.0, 0.0, 0.0]);
        let b = normalize(&[0.0, 1.0, 0.0]);
        let sim = cosine_similarity(&a, &b);
        assert!(sim.abs() < 1e-5);
    }

    #[test]
    fn cosine_similarity_of_opposite_vectors() {
        let a = normalize(&[1.0, 0.0]);
        let b = normalize(&[-1.0, 0.0]);
        let sim = cosine_similarity(&a, &b);
        assert!((sim + 1.0).abs() < 1e-5);
    }

    #[test]
    fn content_hash_is_deterministic() {
        let h1 = content_hash("Fix auth flow. Login fails on redirect");
        let h2 = content_hash("Fix auth flow. Login fails on redirect");
        assert_eq!(h1, h2);
        assert!(!h1.is_empty());
    }

    #[test]
    fn content_hash_changes_with_input() {
        let h1 = content_hash("Fix auth flow");
        let h2 = content_hash("Fix auth flow. Login fails");
        assert_ne!(h1, h2);
    }

    #[test]
    fn normalize_produces_unit_vector() {
        let v = normalize(&[3.0, 4.0]);
        let mag: f32 = v.iter().map(|x| x * x).sum::<f32>().sqrt();
        assert!((mag - 1.0).abs() < 1e-5);
    }

    #[test]
    #[serial]
    fn circuit_breaker_starts_available() {
        assert!(is_available());
    }

    #[test]
    fn cache_round_trip() {
        let mut cache = EmbeddingCache {
            schema_version: CACHE_SCHEMA_VERSION,
            entries: HashMap::new(),
        };
        cache.entries.insert(
            "test-pattern".into(),
            CacheEntry {
                model: "nomic-embed-text".into(),
                content_hash: "abc123".into(),
                embedding: vec![0.1, 0.2, 0.3],
            },
        );

        let json = serde_json::to_string(&cache).expect("serialize");
        let loaded: EmbeddingCache = serde_json::from_str(&json).expect("deserialize");
        assert_eq!(loaded.schema_version, CACHE_SCHEMA_VERSION);
        assert_eq!(loaded.entries.len(), 1);
        assert_eq!(loaded.entries["test-pattern"].content_hash, "abc123");
    }

    #[test]
    fn stale_cache_entry_discarded_on_model_mismatch() {
        // Setup: create a temp dir with a cache file
        let tmp = tempfile::tempdir().expect("create tempdir");
        let cache_file = tmp.path().join("pattern-embeddings.json");

        // Create a pattern and compute its canonical text + hash
        let pattern = Pattern {
            pattern_id: "stale-test".into(),
            title: "Auth redirect bug".into(),
            issue: Some("Login fails on callback".into()),
            ..default_test_pattern()
        };
        let text = pattern_embedding_text(&pattern);
        let hash = content_hash(&text);

        // Write a cache file with an entry under the WRONG model name
        let stale_key = format!("old-model:{}", hash);
        let stale_embedding: Vec<f32> = vec![0.9, 0.1, 0.0];
        let mut stale_entries = HashMap::new();
        stale_entries.insert(
            stale_key.clone(),
            CacheEntry {
                model: "old-model".into(),
                content_hash: hash.clone(),
                embedding: stale_embedding.clone(),
            },
        );
        let stale_cache = EmbeddingCache {
            schema_version: CACHE_SCHEMA_VERSION,
            entries: stale_entries,
        };
        let json = serde_json::to_string_pretty(&stale_cache).expect("serialize cache");
        std::fs::write(&cache_file, &json).expect("write cache file");

        // Load the cache from disk (exercises real file I/O + deserialization)
        let loaded = load_cache_from(&cache_file);
        assert_eq!(
            loaded.entries.len(),
            1,
            "cache file should load with 1 entry"
        );
        assert!(
            loaded.entries.contains_key(&stale_key),
            "stale key should exist in loaded cache"
        );

        // Exercise the lookup logic from match_patterns_semantic (lines 280-294):
        // Current model is "nomic-embed-text", so the cache key differs from "old-model:hash"
        let current_model = "nomic-embed-text";
        let lookup_key = format!("{}:{}", current_model, hash);

        // The stale entry should NOT be found under the current model's key
        assert!(
            !loaded.entries.contains_key(&lookup_key),
            "stale entry under wrong model key must not match current model lookup"
        );

        // Simulate the full cache-hit check: even if we look up by the stale key,
        // the model mismatch in the inner check must reject it
        let entry = loaded.entries.get(&stale_key).expect("stale key exists");
        let model_matches = entry.model == current_model;
        assert!(
            !model_matches,
            "entry.model 'old-model' must not match current model 'nomic-embed-text'"
        );

        // Now write a VALID cache entry under the correct model and verify it IS a hit
        let mut valid_cache = loaded;
        let valid_key = format!("{}:{}", current_model, hash);
        let valid_embedding: Vec<f32> = vec![0.5, 0.5, 0.0];
        valid_cache.entries.insert(
            valid_key.clone(),
            CacheEntry {
                model: current_model.into(),
                content_hash: hash.clone(),
                embedding: valid_embedding.clone(),
            },
        );

        // Save and reload to exercise full round-trip
        let json2 = serde_json::to_string_pretty(&valid_cache).expect("serialize valid cache");
        std::fs::write(&cache_file, &json2).expect("write valid cache file");
        let reloaded = load_cache_from(&cache_file);

        // Valid entry lookup succeeds
        let hit = reloaded.entries.get(&valid_key);
        assert!(
            hit.is_some(),
            "valid entry must be found under correct model key"
        );
        let hit = hit.unwrap();
        assert_eq!(hit.model, current_model);
        assert_eq!(hit.content_hash, hash);
        assert_eq!(hit.embedding, valid_embedding);

        // Stale entry still exists but is ignored by the lookup logic
        assert!(
            reloaded.entries.contains_key(&stale_key),
            "stale entry persists in cache file"
        );
        assert_eq!(
            reloaded.entries.len(),
            2,
            "cache has both stale and valid entries"
        );
    }

    #[test]
    fn test_cache_key_uses_model_hash_not_pattern_id() {
        let pattern_a = Pattern {
            pattern_id: "duplicate-id".into(),
            title: "Auth flow error".into(),
            issue: Some("Token expired".into()),
            ..default_test_pattern()
        };
        let pattern_b = Pattern {
            pattern_id: "duplicate-id".into(),
            title: "Database timeout".into(),
            issue: Some("Connection pool exhausted".into()),
            ..default_test_pattern()
        };

        let text_a = pattern_embedding_text(&pattern_a);
        let text_b = pattern_embedding_text(&pattern_b);
        let hash_a = content_hash(&text_a);
        let hash_b = content_hash(&text_b);
        assert_ne!(hash_a, hash_b);

        let cache_key_a = format!("{}:{}", "nomic-embed-text", hash_a);
        let cache_key_b = format!("{}:{}", "nomic-embed-text", hash_b);
        assert_ne!(cache_key_a, cache_key_b);

        let mut cache = EmbeddingCache {
            schema_version: CACHE_SCHEMA_VERSION,
            entries: HashMap::new(),
        };
        cache.entries.insert(
            cache_key_a.clone(),
            CacheEntry {
                model: "nomic-embed-text".into(),
                content_hash: hash_a.clone(),
                embedding: vec![0.1, 0.2, 0.3],
            },
        );
        cache.entries.insert(
            cache_key_b.clone(),
            CacheEntry {
                model: "nomic-embed-text".into(),
                content_hash: hash_b.clone(),
                embedding: vec![0.4, 0.5, 0.6],
            },
        );
        assert_eq!(cache.entries.len(), 2);
        assert_eq!(cache.entries[&cache_key_a].content_hash, hash_a);
        assert_eq!(cache.entries[&cache_key_b].content_hash, hash_b);
    }

    #[tokio::test]
    #[serial]
    async fn test_empty_patterns_skips_ollama() {
        clear_cooldown();
        let patterns: Vec<Pattern> = Vec::new();
        let keyword_scores: Vec<(usize, usize)> = Vec::new();
        let (results, info) = match_patterns_semantic(
            &patterns,
            "T1.1: Build something",
            "nomic-embed-text",
            5000,
            &keyword_scores,
            "http://127.0.0.1:11434",
        )
        .await;
        assert!(results.is_empty());
        assert_eq!(info.mode, "keyword-only");
        assert_eq!(info.cache_hits, 0);
        assert_eq!(info.cache_misses, 0);
    }

    #[test]
    #[serial]
    fn test_circuit_breaker_cooldown_and_recovery() {
        clear_cooldown();
        assert!(is_available());

        force_cooldown(now_ms() + 60_000);
        assert!(!is_available());

        force_cooldown(now_ms().saturating_sub(1));
        assert!(is_available());

        clear_cooldown();
    }

    #[tokio::test]
    #[serial]
    async fn test_match_patterns_semantic_returns_keyword_only_when_ollama_unavailable() {
        force_cooldown(now_ms() + 300_000);

        let patterns = vec![
            Pattern {
                pattern_id: "pat-a".into(),
                title: "Fix auth flow".into(),
                issue: Some("Login redirect broken".into()),
                ..default_test_pattern()
            },
            Pattern {
                pattern_id: "pat-b".into(),
                title: "Database retry logic".into(),
                issue: Some("Connection drops".into()),
                ..default_test_pattern()
            },
        ];
        let keyword_scores: Vec<(usize, usize)> = vec![(0, 5), (1, 3)];
        let (results, info) = match_patterns_semantic(
            &patterns,
            "T1.1: Fix the auth login redirect",
            "nomic-embed-text",
            5000,
            &keyword_scores,
            "http://127.0.0.1:11434",
        )
        .await;
        assert_eq!(info.mode, "cooldown");
        assert_eq!(info.cache_hits, 0);
        assert_eq!(info.cache_misses, 0);
        assert_eq!(results.len(), 2);
        assert_eq!(results[0].0.pattern_id, "pat-a");
        assert_eq!(results[0].1, 5);
        assert_eq!(results[1].0.pattern_id, "pat-b");
        assert_eq!(results[1].1, 3);

        clear_cooldown();
    }

    #[test]
    fn test_save_cache_prunes_stale_entries() {
        let tmp = tempfile::tempdir().expect("create tempdir");
        let cache_file = tmp.path().join("pattern-embeddings.json");

        // Two current patterns
        let patterns = vec![
            Pattern {
                pattern_id: "active-1".into(),
                title: "Auth redirect bug".into(),
                issue: Some("Login fails on callback".into()),
                ..default_test_pattern()
            },
            Pattern {
                pattern_id: "active-2".into(),
                title: "Database timeout".into(),
                issue: None,
                ..default_test_pattern()
            },
        ];

        let text_1 = pattern_embedding_text(&patterns[0]);
        let hash_1 = content_hash(&text_1);
        let text_2 = pattern_embedding_text(&patterns[1]);
        let hash_2 = content_hash(&text_2);

        // Build a cache with 3 entries: 2 valid, 1 stale
        let model = "nomic-embed-text";
        let mut entries = HashMap::new();
        entries.insert(
            format!("{}:{}", model, hash_1),
            CacheEntry {
                model: model.into(),
                content_hash: hash_1.clone(),
                embedding: vec![0.1, 0.2, 0.3],
            },
        );
        entries.insert(
            format!("{}:{}", model, hash_2),
            CacheEntry {
                model: model.into(),
                content_hash: hash_2.clone(),
                embedding: vec![0.4, 0.5, 0.6],
            },
        );
        // Stale entry: hash for a pattern that no longer exists
        let stale_hash = content_hash("Deleted pattern. This was removed");
        entries.insert(
            format!("{}:{}", model, stale_hash),
            CacheEntry {
                model: model.into(),
                content_hash: stale_hash.clone(),
                embedding: vec![0.9, 0.9, 0.9],
            },
        );

        let cache = EmbeddingCache {
            schema_version: CACHE_SCHEMA_VERSION,
            entries,
        };

        assert_eq!(cache.entries.len(), 3);

        // Save with pruning
        save_cache_to(&cache_file, &cache, &patterns);

        // Reload and verify stale entry was removed
        let reloaded = load_cache_from(&cache_file);
        assert_eq!(reloaded.entries.len(), 2);
        assert!(reloaded
            .entries
            .contains_key(&format!("{}:{}", model, hash_1)));
        assert!(reloaded
            .entries
            .contains_key(&format!("{}:{}", model, hash_2)));
        assert!(!reloaded
            .entries
            .contains_key(&format!("{}:{}", model, stale_hash)));
    }

    #[test]
    fn test_save_cache_with_empty_patterns_clears_all_entries() {
        let tmp = tempfile::tempdir().expect("create tempdir");
        let cache_file = tmp.path().join("pattern-embeddings.json");

        let mut entries = HashMap::new();
        entries.insert(
            "nomic-embed-text:somehash".into(),
            CacheEntry {
                model: "nomic-embed-text".into(),
                content_hash: "somehash".into(),
                embedding: vec![0.1, 0.2],
            },
        );

        let cache = EmbeddingCache {
            schema_version: CACHE_SCHEMA_VERSION,
            entries,
        };

        let empty_patterns: Vec<Pattern> = Vec::new();
        save_cache_to(&cache_file, &cache, &empty_patterns);

        let reloaded = load_cache_from(&cache_file);
        assert_eq!(reloaded.entries.len(), 0);
        assert_eq!(reloaded.schema_version, CACHE_SCHEMA_VERSION);
    }

    fn default_test_pattern() -> Pattern {
        Pattern {
            pattern_id: String::new(),
            title: String::new(),
            first_seen: String::new(),
            last_seen: String::new(),
            frequency: 0,
            severity: None,
            keywords: Vec::new(),
            tech_stack: Vec::new(),
            issue: None,
            solution: None,
            auto_apply: false,
            learned_from: None,
            used_count: 0,
            promoted_to: String::new(),
            promoted_at: String::new(),
            last_used_at: None,
        }
    }
}
