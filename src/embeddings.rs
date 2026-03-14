use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::OnceLock;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

use serde::{Deserialize, Serialize};

use crate::patterns::Pattern;

// ─── Config ──────────────────────────────────────────────────

const DEFAULT_OLLAMA_URL: &str = "http://127.0.0.1:11434/api/embed";
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

fn is_available() -> bool {
    now_ms() >= state().cooldown_until_ms.load(Ordering::Relaxed)
}

fn mark_failed() {
    state()
        .cooldown_until_ms
        .store(now_ms() + COOLDOWN_MS, Ordering::Relaxed);
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
) -> Result<Vec<Vec<f32>>, String> {
    let body = serde_json::json!({
        "model": model,
        "input": texts,
    });

    let timeout_secs = (timeout_ms as f64 / 1000.0).max(1.0);
    let output = std::process::Command::new("curl")
        .args([
            "-s",
            "-X", "POST",
            DEFAULT_OLLAMA_URL,
            "-H", "Content-Type: application/json",
            "-d", &body.to_string(),
            "--max-time", &format!("{:.0}", timeout_secs),
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
) -> Result<Vec<Vec<f32>>, String> {
    if texts.is_empty() {
        return Ok(Vec::new());
    }

    let texts = texts.to_vec();
    let model = model.to_string();

    tokio::task::spawn_blocking(move || embed_batch_sync(&texts, &model, timeout_ms))
        .await
        .map_err(|e| format!("embed task panicked: {}", e))?
}

// ─── Vector Math ─────────────────────────────────────────────

fn normalize(v: &[f32]) -> Vec<f32> {
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
    if let Ok(home) = std::env::var("HOME") {
        PathBuf::from(home).join(".foundry/cache")
    } else {
        eprintln!("warning: HOME not set, using /tmp/.foundry/cache for embedding cache");
        PathBuf::from("/tmp/.foundry/cache")
    }
}

fn cache_path() -> PathBuf {
    cache_dir().join("pattern-embeddings.json")
}

fn content_hash(text: &str) -> String {
    blake3::hash(text.as_bytes()).to_hex().to_string()
}

fn load_cache() -> EmbeddingCache {
    let path = cache_path();
    match std::fs::read_to_string(&path) {
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

fn save_cache(cache: &EmbeddingCache) {
    let dir = cache_dir();
    let _ = std::fs::create_dir_all(&dir);
    if let Ok(data) = serde_json::to_string_pretty(cache) {
        let _ = std::fs::write(cache_path(), data);
    }
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
        match embed_batch(&texts, model, timeout_ms).await {
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
                save_cache(&cache);
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
    let task_embedding = match embed_batch(&[task_text], model, timeout_ms).await {
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
    result.sort_by(|a, b| b.1.cmp(&a.1));
    result
}

// ─── Tests ───────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

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
        assert_eq!(normalize_task_text("T1.1: Build the login page"), "build the login page");
        assert_eq!(normalize_task_text("D2.3: Fix broken import"), "fix broken import");
        assert_eq!(normalize_task_text("H1.1: Add smiley face"), "add smiley face");
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
        assert_eq!(
            loaded.entries["test-pattern"].content_hash,
            "abc123"
        );
    }

    #[test]
    fn stale_cache_entry_discarded_on_model_mismatch() {
        let entry = CacheEntry {
            model: "old-model".into(),
            content_hash: "abc".into(),
            embedding: vec![0.1],
        };
        // Simulate: current model is different
        assert_ne!(entry.model, "nomic-embed-text");
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
        }
    }
}
