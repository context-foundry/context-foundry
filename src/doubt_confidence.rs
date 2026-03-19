use std::collections::HashSet;
use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};

use crate::complexity::TaskComplexity;
use crate::embeddings;
use crate::utils::atomic_write_file_best_effort;

// ─── Constants ──────────────────────────────────────────────

const SIMILARITY_THRESHOLD: f32 = 0.85;
const KEYWORD_OVERLAP_THRESHOLD: f32 = 0.4;

// ─── Types ──────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DoubtCluster {
    pub centroid: Vec<f32>,
    pub representative_desc: String,
    pub passes: u32,
    pub fails: u32,
    pub consecutive_passes: u32,
    pub last_fail: Option<String>,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
#[serde(default)]
pub struct DoubtHistory {
    pub clusters: Vec<DoubtCluster>,
}

#[allow(dead_code)]
pub struct DoubtConfidenceResult {
    pub should_skip: bool,
    pub cluster_idx: Option<usize>,
    pub log_message: String,
}

// ─── Stopwords ──────────────────────────────────────────────

const STOPWORDS: &[&str] = &[
    "the", "a", "an", "is", "are", "was", "were", "to", "for", "of", "in", "on", "and", "or",
    "with", "that", "this",
];

// ─── Persistence ────────────────────────────────────────────

fn history_path() -> PathBuf {
    let base = if cfg!(target_os = "windows") {
        std::env::var("LOCALAPPDATA")
            .or_else(|_| std::env::var("USERPROFILE"))
            .ok()
    } else {
        std::env::var("HOME").ok()
    };
    if let Some(base) = base {
        PathBuf::from(base).join(".foundry/doubt-history.json")
    } else {
        PathBuf::from("/tmp/.foundry/doubt-history.json")
    }
}

fn load_history_from(path: &Path) -> DoubtHistory {
    match std::fs::read_to_string(path) {
        Ok(data) => serde_json::from_str(&data).unwrap_or_default(),
        Err(_) => DoubtHistory::default(),
    }
}

fn load_history() -> DoubtHistory {
    load_history_from(&history_path())
}

fn save_history_to(path: &Path, history: &DoubtHistory) {
    if let Some(parent) = path.parent() {
        let _ = std::fs::create_dir_all(parent);
    }
    if let Ok(json) = serde_json::to_string_pretty(history) {
        atomic_write_file_best_effort(path, json.as_bytes());
    }
}

fn save_history(history: &DoubtHistory) {
    save_history_to(&history_path(), history);
}

// ─── Cluster Matching ───────────────────────────────────────

fn find_cluster_semantic(embedding: &[f32], history: &DoubtHistory) -> Option<(usize, f32)> {
    if history.clusters.is_empty() {
        return None;
    }
    let mut best_idx = 0;
    let mut best_sim = f32::NEG_INFINITY;
    for (i, cluster) in history.clusters.iter().enumerate() {
        let sim = embeddings::cosine_similarity(embedding, &cluster.centroid);
        if sim > best_sim {
            best_sim = sim;
            best_idx = i;
        }
    }
    if best_sim >= SIMILARITY_THRESHOLD {
        Some((best_idx, best_sim))
    } else {
        None
    }
}

fn find_cluster_keyword(task_desc: &str, history: &DoubtHistory) -> Option<(usize, f32)> {
    if history.clusters.is_empty() {
        return None;
    }
    let stopwords: HashSet<&str> = STOPWORDS.iter().copied().collect();
    let task_lower = task_desc.to_lowercase();
    let task_words: HashSet<&str> = task_lower
        .split_whitespace()
        .filter(|w| !stopwords.contains(w))
        .collect();
    if task_words.is_empty() {
        return None;
    }

    let mut best_idx = 0;
    let mut best_jaccard = 0.0f32;

    for (i, cluster) in history.clusters.iter().enumerate() {
        let cluster_lower = cluster.representative_desc.to_lowercase();
        let cluster_words: HashSet<&str> = cluster_lower
            .split_whitespace()
            .filter(|w| !stopwords.contains(w))
            .collect();
        let overlap = task_words.intersection(&cluster_words).count() as f32;
        let total = task_words.union(&cluster_words).count() as f32;
        let jaccard = if total > 0.0 { overlap / total } else { 0.0 };
        if jaccard > best_jaccard {
            best_jaccard = jaccard;
            best_idx = i;
        }
    }

    if best_jaccard >= KEYWORD_OVERLAP_THRESHOLD {
        Some((best_idx, best_jaccard))
    } else {
        None
    }
}

// ─── Public API ─────────────────────────────────────────────

pub async fn check_doubt_confidence(
    task_desc: &str,
    complexity: TaskComplexity,
    threshold: usize,
    embedding_model: &str,
    embedding_timeout_ms: u64,
    ollama_url: &str,
) -> DoubtConfidenceResult {
    if threshold == 0 {
        return DoubtConfidenceResult {
            should_skip: false,
            cluster_idx: None,
            log_message: String::new(),
        };
    }

    if complexity == TaskComplexity::Complex {
        return DoubtConfidenceResult {
            should_skip: false,
            cluster_idx: None,
            log_message: "Doubt required: Complex tasks always run doubt".to_string(),
        };
    }

    let history = load_history();
    if history.clusters.is_empty() {
        return DoubtConfidenceResult {
            should_skip: false,
            cluster_idx: None,
            log_message: String::new(),
        };
    }

    // Try semantic match first, fall back to keyword
    let cluster_match = if embeddings::is_available() {
        let normalized_text = embeddings::normalize_task_text(task_desc);
        match embeddings::embed_batch(
            &[normalized_text],
            embedding_model,
            embedding_timeout_ms,
            ollama_url,
        )
        .await
        {
            Ok(ref embeddings) if !embeddings.is_empty() => {
                let embedding = embeddings::normalize(&embeddings[0]);
                find_cluster_semantic(&embedding, &history)
            }
            _ => find_cluster_keyword(task_desc, &history),
        }
    } else {
        find_cluster_keyword(task_desc, &history)
    };

    match cluster_match {
        None => DoubtConfidenceResult {
            should_skip: false,
            cluster_idx: None,
            log_message: String::new(),
        },
        Some((idx, _sim)) => {
            let cluster = &history.clusters[idx];
            if cluster.consecutive_passes >= threshold as u32 {
                DoubtConfidenceResult {
                    should_skip: true,
                    cluster_idx: Some(idx),
                    log_message: format!(
                        "Doubt skip: matched cluster '{}' ({} consecutive passes)",
                        cluster.representative_desc, cluster.consecutive_passes
                    ),
                }
            } else {
                let log_message = if cluster.last_fail.is_some() {
                    format!(
                        "Doubt required: cluster '{}' last failed {}",
                        cluster.representative_desc,
                        cluster.last_fail.as_deref().unwrap_or("unknown")
                    )
                } else {
                    format!(
                        "Doubt required: cluster '{}' has only {} consecutive passes (need {})",
                        cluster.representative_desc, cluster.consecutive_passes, threshold
                    )
                };
                DoubtConfidenceResult {
                    should_skip: false,
                    cluster_idx: Some(idx),
                    log_message,
                }
            }
        }
    }
}

fn update_centroid(old_centroid: &[f32], count: u32, new_embedding: &[f32]) -> Vec<f32> {
    let n = count as f32;
    let new_vec: Vec<f32> = old_centroid
        .iter()
        .zip(new_embedding.iter())
        .map(|(o, e)| o * n + e)
        .collect();
    embeddings::normalize(&new_vec)
}

fn truncate_to_char_boundary(s: &str, max_chars: usize) -> &str {
    if s.len() <= max_chars {
        return s;
    }
    let mut end = 0;
    for (i, _) in s.char_indices() {
        if i > max_chars {
            break;
        }
        end = i;
    }
    &s[..end]
}

pub async fn record_doubt_result(
    task_desc: &str,
    passed: bool,
    embedding_model: &str,
    embedding_timeout_ms: u64,
    ollama_url: &str,
) {
    let mut history = load_history();
    let normalized_text = embeddings::normalize_task_text(task_desc);

    // Attempt embedding
    let embedding = if embeddings::is_available() {
        match embeddings::embed_batch(
            std::slice::from_ref(&normalized_text),
            embedding_model,
            embedding_timeout_ms,
            ollama_url,
        )
        .await
        {
            Ok(ref embs) if !embs.is_empty() => Some(embeddings::normalize(&embs[0])),
            _ => None,
        }
    } else {
        None
    };

    // Find matching cluster
    let cluster_match = match embedding {
        Some(ref emb) => find_cluster_semantic(emb, &history),
        None => find_cluster_keyword(task_desc, &history),
    };

    match cluster_match {
        Some((idx, _)) => {
            let cluster = &mut history.clusters[idx];
            if passed {
                cluster.passes += 1;
                cluster.consecutive_passes += 1;
            } else {
                cluster.fails += 1;
                cluster.consecutive_passes = 0;
                cluster.last_fail =
                    Some(chrono::Utc::now().format("%Y-%m-%d").to_string());
            }
            if let Some(ref emb) = embedding {
                cluster.centroid =
                    update_centroid(&cluster.centroid, cluster.passes + cluster.fails - 1, emb);
            }
        }
        None => {
            if let Some(emb) = embedding {
                let desc = truncate_to_char_boundary(&normalized_text, 60).to_string();
                let new_cluster = DoubtCluster {
                    centroid: emb,
                    representative_desc: desc,
                    passes: if passed { 1 } else { 0 },
                    fails: if !passed { 1 } else { 0 },
                    consecutive_passes: if passed { 1 } else { 0 },
                    last_fail: if !passed {
                        Some(chrono::Utc::now().format("%Y-%m-%d").to_string())
                    } else {
                        None
                    },
                };

                // Cap at 200 clusters
                if history.clusters.len() >= 200 {
                    if let Some((evict_idx, _)) = history
                        .clusters
                        .iter()
                        .enumerate()
                        .min_by_key(|(_, c)| c.passes + c.fails)
                    {
                        history.clusters.remove(evict_idx);
                    }
                }

                history.clusters.push(new_cluster);
            }
            // If no embedding, cannot create cluster -- do nothing
        }
    }

    save_history(&history);
}

// ─── Tests ──────────────────────────────────────────────────

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_load_empty_history() {
        let tmp = tempfile::tempdir().expect("create tempdir");
        let path = tmp.path().join("nonexistent.json");
        let history = load_history_from(&path);
        assert!(history.clusters.is_empty());
    }

    #[test]
    fn test_save_and_reload_history() {
        let tmp = tempfile::tempdir().expect("create tempdir");
        let path = tmp.path().join("doubt-history.json");

        let history = DoubtHistory {
            clusters: vec![DoubtCluster {
                centroid: vec![1.0, 0.0, 0.0],
                representative_desc: "rename files".to_string(),
                passes: 5,
                fails: 1,
                consecutive_passes: 3,
                last_fail: Some("2025-01-15".to_string()),
            }],
        };

        save_history_to(&path, &history);
        let reloaded = load_history_from(&path);

        assert_eq!(reloaded.clusters.len(), 1);
        assert_eq!(reloaded.clusters[0].representative_desc, "rename files");
        assert_eq!(reloaded.clusters[0].passes, 5);
        assert_eq!(reloaded.clusters[0].fails, 1);
        assert_eq!(reloaded.clusters[0].consecutive_passes, 3);
        assert_eq!(
            reloaded.clusters[0].last_fail.as_deref(),
            Some("2025-01-15")
        );
    }

    #[test]
    fn test_find_cluster_semantic_match() {
        let centroid = embeddings::normalize(&[1.0, 0.0, 0.0]);
        let history = DoubtHistory {
            clusters: vec![DoubtCluster {
                centroid: centroid.clone(),
                representative_desc: "rename files".to_string(),
                passes: 5,
                fails: 0,
                consecutive_passes: 5,
                last_fail: None,
            }],
        };

        let query = embeddings::normalize(&[0.99, 0.01, 0.0]);
        let result = find_cluster_semantic(&query, &history);
        assert!(result.is_some());
        let (idx, sim) = result.unwrap();
        assert_eq!(idx, 0);
        assert!(sim >= SIMILARITY_THRESHOLD);
    }

    #[test]
    fn test_find_cluster_semantic_no_match() {
        let centroid = embeddings::normalize(&[1.0, 0.0, 0.0]);
        let history = DoubtHistory {
            clusters: vec![DoubtCluster {
                centroid,
                representative_desc: "rename files".to_string(),
                passes: 5,
                fails: 0,
                consecutive_passes: 5,
                last_fail: None,
            }],
        };

        let query = embeddings::normalize(&[0.0, 1.0, 0.0]);
        let result = find_cluster_semantic(&query, &history);
        assert!(result.is_none());
    }

    #[test]
    fn test_find_cluster_keyword_match() {
        let history = DoubtHistory {
            clusters: vec![DoubtCluster {
                centroid: vec![],
                representative_desc: "rename move files".to_string(),
                passes: 5,
                fails: 0,
                consecutive_passes: 5,
                last_fail: None,
            }],
        };

        let result = find_cluster_keyword("rename the config files", &history);
        assert!(result.is_some());
        let (idx, _jaccard) = result.unwrap();
        assert_eq!(idx, 0);
    }

    #[test]
    fn test_find_cluster_keyword_no_match() {
        let history = DoubtHistory {
            clusters: vec![DoubtCluster {
                centroid: vec![],
                representative_desc: "rename move files".to_string(),
                passes: 5,
                fails: 0,
                consecutive_passes: 5,
                last_fail: None,
            }],
        };

        let result = find_cluster_keyword("architect new system", &history);
        assert!(result.is_none());
    }

    #[test]
    fn test_update_centroid_moves_toward_new() {
        let old = embeddings::normalize(&[1.0, 0.0]);
        let new_emb = embeddings::normalize(&[0.0, 1.0]);
        let updated = update_centroid(&old, 1, &new_emb);
        // Should be roughly normalize([1.0, 1.0])
        let expected = embeddings::normalize(&[1.0, 1.0]);
        for (a, b) in updated.iter().zip(expected.iter()) {
            assert!((a - b).abs() < 0.01, "expected ~{b}, got {a}");
        }
    }

    #[test]
    fn test_cluster_cap_at_200() {
        let tmp = tempfile::tempdir().expect("create tempdir");
        let path = tmp.path().join("doubt-history.json");

        let mut clusters = Vec::new();
        for i in 0..200 {
            clusters.push(DoubtCluster {
                centroid: vec![i as f32, 0.0, 0.0],
                representative_desc: format!("cluster {}", i),
                passes: (i + 1) as u32, // cluster 0 has lowest count (1)
                fails: 0,
                consecutive_passes: (i + 1) as u32,
                last_fail: None,
            });
        }
        let history = DoubtHistory { clusters };
        save_history_to(&path, &history);

        // Simulate adding a new cluster by loading, evicting, and pushing
        let mut loaded = load_history_from(&path);
        assert_eq!(loaded.clusters.len(), 200);

        // Evict lowest-count cluster (cluster 0 with passes=1)
        if loaded.clusters.len() >= 200 {
            if let Some((evict_idx, _)) = loaded
                .clusters
                .iter()
                .enumerate()
                .min_by_key(|(_, c)| c.passes + c.fails)
            {
                loaded.clusters.remove(evict_idx);
            }
        }
        loaded.clusters.push(DoubtCluster {
            centroid: vec![999.0, 0.0, 0.0],
            representative_desc: "new cluster".to_string(),
            passes: 1,
            fails: 0,
            consecutive_passes: 1,
            last_fail: None,
        });

        assert_eq!(loaded.clusters.len(), 200);
        // Verify cluster 0 (lowest count) was evicted
        assert!(!loaded
            .clusters
            .iter()
            .any(|c| c.representative_desc == "cluster 0"));
        // Verify new cluster exists
        assert!(loaded
            .clusters
            .iter()
            .any(|c| c.representative_desc == "new cluster"));
    }

    #[test]
    fn test_truncate_to_char_boundary() {
        assert_eq!(truncate_to_char_boundary("hello", 10), "hello");
        assert_eq!(truncate_to_char_boundary("hello world", 5), "hello");
        // Multi-byte: ensure no panic on unicode
        let s = "cafe\u{0301} au lait"; // cafe with combining accent
        let truncated = truncate_to_char_boundary(s, 6);
        assert!(truncated.len() <= 6);
    }

    #[test]
    fn test_corrupt_history_file_returns_empty() {
        let tmp = tempfile::tempdir().expect("create tempdir");
        let path = tmp.path().join("doubt-history.json");
        std::fs::write(&path, "{ broken json").expect("write");
        let history = load_history_from(&path);
        assert!(history.clusters.is_empty());
    }
}
