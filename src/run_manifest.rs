#![allow(dead_code)]

use crate::agent::AgentRole;
use crate::eval::stage_id::StageId;
use crate::utils::atomic_write_file;
use anyhow::{Context, Result};
use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct StageInvocationId(pub u64);

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum StageStatus {
    Ran,
    Skipped,
    Reused,
    CheckpointResume,
    Failed,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ArtifactSource {
    ThisRun,
    Checkpoint,
    PreviousRun,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum CompletionPath {
    AuditPass,
    AuditFail,
    AuditSkipped,
    BuilderFailure,
    PlannerFailure,
    Aborted,
}

#[derive(Debug, Clone, Default)]
pub struct AgentExitInfo {
    pub log_path: Option<PathBuf>,
    pub actual_provider: String,
    pub actual_model: String,
    pub fallback_reason: Option<String>,
}

pub struct PromptEvidenceSpec<'a> {
    pub stage_id: StageId,
    pub role: AgentRole,
    pub expected_artifact_path: Option<PathBuf>,
    pub originally_configured_provider: String,
    pub originally_configured_model: String,
    pub effective_provider: String,
    pub effective_model: String,
    pub override_reason: Option<String>,
    pub system_prompt: &'a str,
    pub user_prompt: &'a str,
    pub matched_pattern_ids: Vec<String>,
    pub selected_extension_names: Vec<String>,
    pub prior_artifact_paths: Vec<PathBuf>,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct StageInvocation {
    pub invocation_id: u64,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub stage_id: Option<StageId>,
    #[serde(default)]
    pub role: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub status: Option<StageStatus>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub superseded_by: Option<u64>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub skip_reason: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub artifact_source: Option<ArtifactSource>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub log_path: Option<PathBuf>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub expected_artifact_path: Option<PathBuf>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub originally_configured_provider: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub originally_configured_model: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub effective_provider: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub effective_model: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub actual_provider: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub actual_model: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub fallback_reason: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub override_reason: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub system_prompt_hash: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub system_prompt_bytes: Option<usize>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub user_prompt_hash: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub user_prompt_bytes: Option<usize>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub system_prompt_preview: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub user_prompt_preview: Option<String>,
    #[serde(default)]
    pub matched_pattern_ids: Vec<String>,
    #[serde(default)]
    pub selected_extension_names: Vec<String>,
    #[serde(default)]
    pub prompt_pattern_ids_found: Vec<String>,
    #[serde(default)]
    pub prompt_artifact_refs_found: Vec<String>,
    #[serde(default)]
    pub prompt_extension_names_found: Vec<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub started_at: Option<DateTime<Utc>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub exit_status: Option<String>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub exit_observed_at: Option<DateTime<Utc>>,
}

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct RunManifest {
    #[serde(default)]
    pub schema_version: u32,
    #[serde(default)]
    pub run_id: String,
    #[serde(default)]
    pub task_id: String,
    #[serde(default)]
    pub started_at: DateTime<Utc>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub finished_at: Option<DateTime<Utc>>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub completion_path: Option<CompletionPath>,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub audit_skipped_reason: Option<String>,
    #[serde(default)]
    pub invocations: Vec<StageInvocation>,
    #[serde(skip)]
    pub manifest_path: PathBuf,
    #[serde(skip)]
    pub next_invocation_id: u64,
}

pub const RUN_MANIFEST_SCHEMA_VERSION: u32 = 1;

#[derive(Clone)]
pub struct ManifestHandle {
    inner: Arc<Mutex<RunManifest>>,
}

pub fn blake3_hex(data: &[u8]) -> String {
    let hash = blake3::hash(data);
    format!("blake3:{}", hash.to_hex())
}

pub fn truncate_preview(s: &str, max_bytes: usize) -> String {
    crate::utils::truncate_str(s, max_bytes).to_string()
}

fn compute_pattern_evidence(prompt: &str, ids: &[String]) -> Vec<String> {
    ids.iter()
        .filter(|id| prompt.contains(&format!("[{}]", id)))
        .cloned()
        .collect()
}

fn compute_extension_evidence(prompt: &str, names: &[String]) -> Vec<String> {
    names
        .iter()
        .filter(|name| prompt.contains(&format!("--- BEGIN EXTENSION CONTEXT: {} ---", name)))
        .cloned()
        .collect()
}

fn compute_artifact_evidence(prompt: &str, paths: &[PathBuf]) -> Vec<String> {
    let mut out = Vec::new();
    for p in paths {
        let basename = match p.file_name().and_then(|n| n.to_str()) {
            Some(b) => b,
            None => continue,
        };
        if prompt.contains(basename) {
            out.push(basename.to_string());
        }
    }
    out
}

impl ManifestHandle {
    pub fn new(buildloop_dir: &Path, task_id: &str, started_at: DateTime<Utc>) -> Self {
        let run_id = format!(
            "{}-{}",
            started_at.format("%Y-%m-%dT%H-%M-%S"),
            task_id
        );
        let manifest = RunManifest {
            schema_version: RUN_MANIFEST_SCHEMA_VERSION,
            run_id,
            task_id: task_id.to_string(),
            started_at,
            finished_at: None,
            completion_path: None,
            audit_skipped_reason: None,
            invocations: Vec::new(),
            manifest_path: buildloop_dir.join("run-manifest.json"),
            next_invocation_id: 1,
        };
        Self {
            inner: Arc::new(Mutex::new(manifest)),
        }
    }

    pub fn record_invocation(&self, spec: PromptEvidenceSpec<'_>) -> StageInvocationId {
        let system_prompt_hash = blake3_hex(spec.system_prompt.as_bytes());
        let user_prompt_hash = blake3_hex(spec.user_prompt.as_bytes());
        let system_prompt_bytes = spec.system_prompt.len();
        let user_prompt_bytes = spec.user_prompt.len();
        let system_prompt_preview = truncate_preview(spec.system_prompt, 1024);
        let user_prompt_preview = truncate_preview(spec.user_prompt, 1024);
        let prompt_pattern_ids_found =
            compute_pattern_evidence(spec.user_prompt, &spec.matched_pattern_ids);
        let prompt_extension_names_found =
            compute_extension_evidence(spec.user_prompt, &spec.selected_extension_names);
        let prompt_artifact_refs_found =
            compute_artifact_evidence(spec.user_prompt, &spec.prior_artifact_paths);

        let mut m = self.inner.lock().expect("run manifest mutex poisoned");
        let id = m.next_invocation_id;
        m.next_invocation_id += 1;

        let invocation = StageInvocation {
            invocation_id: id,
            stage_id: Some(spec.stage_id),
            role: format!("{:?}", spec.role),
            status: Some(StageStatus::Ran),
            superseded_by: None,
            skip_reason: None,
            artifact_source: Some(ArtifactSource::ThisRun),
            log_path: None,
            expected_artifact_path: spec.expected_artifact_path,
            originally_configured_provider: Some(spec.originally_configured_provider),
            originally_configured_model: Some(spec.originally_configured_model),
            effective_provider: Some(spec.effective_provider),
            effective_model: Some(spec.effective_model),
            actual_provider: None,
            actual_model: None,
            fallback_reason: None,
            override_reason: spec.override_reason,
            system_prompt_hash: Some(system_prompt_hash),
            system_prompt_bytes: Some(system_prompt_bytes),
            user_prompt_hash: Some(user_prompt_hash),
            user_prompt_bytes: Some(user_prompt_bytes),
            system_prompt_preview: Some(system_prompt_preview),
            user_prompt_preview: Some(user_prompt_preview),
            matched_pattern_ids: spec.matched_pattern_ids,
            selected_extension_names: spec.selected_extension_names,
            prompt_pattern_ids_found,
            prompt_artifact_refs_found,
            prompt_extension_names_found,
            started_at: Some(Utc::now()),
            exit_status: None,
            exit_observed_at: None,
        };
        m.invocations.push(invocation);
        StageInvocationId(id)
    }

    pub fn record_exit(
        &self,
        id: StageInvocationId,
        status: StageStatus,
        exit_observed_at: DateTime<Utc>,
        exit_info: AgentExitInfo,
    ) {
        let mut m = self.inner.lock().expect("run manifest mutex poisoned");
        if let Some(inv) = m.invocations.iter_mut().find(|i| i.invocation_id == id.0) {
            inv.status = Some(status);
            inv.exit_observed_at = Some(exit_observed_at);
            inv.log_path = exit_info.log_path;
            inv.actual_provider = if exit_info.actual_provider.is_empty() {
                None
            } else {
                Some(exit_info.actual_provider)
            };
            inv.actual_model = if exit_info.actual_model.is_empty() {
                None
            } else {
                Some(exit_info.actual_model)
            };
            inv.fallback_reason = exit_info.fallback_reason;
        }
    }

    pub fn record_skip(
        &self,
        stage_id: StageId,
        role: AgentRole,
        status: StageStatus,
        skip_reason: String,
        artifact_source: Option<ArtifactSource>,
    ) -> StageInvocationId {
        let mut m = self.inner.lock().expect("run manifest mutex poisoned");
        let id = m.next_invocation_id;
        m.next_invocation_id += 1;
        let invocation = StageInvocation {
            invocation_id: id,
            stage_id: Some(stage_id),
            role: format!("{:?}", role),
            status: Some(status),
            skip_reason: Some(skip_reason),
            artifact_source,
            started_at: Some(Utc::now()),
            ..Default::default()
        };
        m.invocations.push(invocation);
        StageInvocationId(id)
    }

    pub fn mark_superseded(&self, prior_id: StageInvocationId, by_id: StageInvocationId) {
        let mut m = self.inner.lock().expect("run manifest mutex poisoned");
        if let Some(inv) = m
            .invocations
            .iter_mut()
            .find(|i| i.invocation_id == prior_id.0)
        {
            inv.superseded_by = Some(by_id.0);
        }
    }

    pub fn record_completion(&self, completion_path: CompletionPath) {
        let mut m = self.inner.lock().expect("run manifest mutex poisoned");
        m.completion_path = Some(completion_path);
        m.finished_at = Some(Utc::now());
    }

    pub fn flush(&self) -> Result<()> {
        let m = self.inner.lock().expect("run manifest mutex poisoned");
        let path = m.manifest_path.clone();
        let bytes = serde_json::to_vec_pretty(&*m)
            .context("failed to serialize run manifest")?;
        drop(m);
        if let Some(parent) = path.parent() {
            std::fs::create_dir_all(parent).with_context(|| {
                format!("failed to create manifest parent dir {}", parent.display())
            })?;
        }
        atomic_write_file(&path, &bytes)
            .with_context(|| format!("failed to write manifest to {}", path.display()))?;
        Ok(())
    }

    pub fn snapshot(&self) -> RunManifest {
        let m = self.inner.lock().expect("run manifest mutex poisoned");
        m.clone()
    }
}

pub fn read_manifest(path: &Path) -> Result<RunManifest> {
    let bytes = std::fs::read(path)
        .with_context(|| format!("failed to read manifest {}", path.display()))?;
    let mut m: RunManifest = serde_json::from_slice(&bytes)
        .with_context(|| format!("failed to parse manifest {}", path.display()))?;
    m.manifest_path = path.to_path_buf();
    m.next_invocation_id = m
        .invocations
        .iter()
        .map(|i| i.invocation_id)
        .max()
        .unwrap_or(0)
        + 1;
    Ok(m)
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;

    fn empty_spec<'a>(system: &'a str, user: &'a str) -> PromptEvidenceSpec<'a> {
        PromptEvidenceSpec {
            stage_id: StageId::Plan,
            role: AgentRole::Planner,
            expected_artifact_path: None,
            originally_configured_provider: String::new(),
            originally_configured_model: String::new(),
            effective_provider: String::new(),
            effective_model: String::new(),
            override_reason: None,
            system_prompt: system,
            user_prompt: user,
            matched_pattern_ids: Vec::new(),
            selected_extension_names: Vec::new(),
            prior_artifact_paths: Vec::new(),
        }
    }

    #[test]
    fn blake3_hex_labels_with_prefix() {
        assert!(blake3_hex(b"hello").starts_with("blake3:"));
        assert_ne!(blake3_hex(b""), blake3_hex(b"x"));
        assert_eq!(
            blake3_hex(b""),
            format!("blake3:{}", blake3::hash(b"").to_hex())
        );
    }

    #[test]
    fn pattern_evidence_requires_brackets() {
        let prompt = "head [pat-1] middle simple tail";
        let ids = vec!["pat-1".to_string(), "simple".to_string()];
        let found = compute_pattern_evidence(prompt, &ids);
        assert_eq!(found, vec!["pat-1".to_string()]);
    }

    #[test]
    fn extension_evidence_matches_marker() {
        let prompt = "before --- BEGIN EXTENSION CONTEXT: recon --- after";
        let names = vec!["recon".to_string(), "missing".to_string()];
        let found = compute_extension_evidence(prompt, &names);
        assert_eq!(found, vec!["recon".to_string()]);
    }

    #[test]
    fn artifact_evidence_matches_basename() {
        let prompt = "see research-report.md";
        let paths = vec![PathBuf::from(".buildloop/research-report.md")];
        let found = compute_artifact_evidence(prompt, &paths);
        assert_eq!(found, vec!["research-report.md".to_string()]);
    }

    #[test]
    fn record_invocation_assigns_monotonic_ids() {
        let tmp = TempDir::new().unwrap();
        let h = ManifestHandle::new(tmp.path(), "T1.1", Utc::now());
        let id1 = h.record_invocation(empty_spec("", ""));
        let id2 = h.record_invocation(empty_spec("", ""));
        assert_eq!(id1.0, 1);
        assert_eq!(id2.0, 2);
    }

    #[test]
    fn record_invocation_computes_evidence_and_hashes() {
        let tmp = TempDir::new().unwrap();
        let h = ManifestHandle::new(tmp.path(), "T1.1", Utc::now());
        let user = "head [pat-a] middle research-report.md tail --- BEGIN EXTENSION CONTEXT: recon --- end";
        let spec = PromptEvidenceSpec {
            stage_id: StageId::Plan,
            role: AgentRole::Planner,
            expected_artifact_path: None,
            originally_configured_provider: String::new(),
            originally_configured_model: String::new(),
            effective_provider: String::new(),
            effective_model: String::new(),
            override_reason: None,
            system_prompt: "",
            user_prompt: user,
            matched_pattern_ids: vec!["pat-a".to_string(), "pat-b".to_string()],
            selected_extension_names: vec!["recon".to_string()],
            prior_artifact_paths: vec![PathBuf::from(".buildloop/research-report.md")],
        };
        h.record_invocation(spec);
        let m = h.snapshot();
        let inv = &m.invocations[0];
        assert_eq!(inv.prompt_pattern_ids_found, vec!["pat-a".to_string()]);
        assert_eq!(
            inv.prompt_extension_names_found,
            vec!["recon".to_string()]
        );
        assert_eq!(
            inv.prompt_artifact_refs_found,
            vec!["research-report.md".to_string()]
        );
        assert_eq!(inv.system_prompt_bytes, Some(0));
        assert_eq!(inv.user_prompt_bytes, Some(user.len()));
        assert!(inv
            .system_prompt_hash
            .as_deref()
            .unwrap()
            .starts_with("blake3:"));
        assert!(inv
            .user_prompt_hash
            .as_deref()
            .unwrap()
            .starts_with("blake3:"));
        assert_ne!(inv.system_prompt_hash, inv.user_prompt_hash);
    }

    #[test]
    fn flush_atomic_writes_manifest() {
        let tmp = TempDir::new().unwrap();
        let h = ManifestHandle::new(tmp.path(), "T1.1", Utc::now());
        h.record_invocation(empty_spec("", ""));
        h.flush().unwrap();
        let path = tmp.path().join("run-manifest.json");
        assert!(path.exists());
        let m = read_manifest(&path).unwrap();
        assert_eq!(m.invocations.len(), 1);
        assert_eq!(m.next_invocation_id, 2);
    }

    #[test]
    fn flush_overwrites_atomically() {
        let tmp = TempDir::new().unwrap();
        let h = ManifestHandle::new(tmp.path(), "T1.1", Utc::now());
        h.record_invocation(empty_spec("", ""));
        h.flush().unwrap();
        h.record_invocation(empty_spec("", ""));
        h.flush().unwrap();
        let path = tmp.path().join("run-manifest.json");
        let m = read_manifest(&path).unwrap();
        assert_eq!(m.invocations.len(), 2);
        for entry in std::fs::read_dir(tmp.path()).unwrap() {
            let e = entry.unwrap();
            let name = e.file_name().to_string_lossy().to_string();
            assert!(
                !name.ends_with(".tmp"),
                "leftover tmp file: {}",
                name
            );
        }
    }

    #[test]
    fn record_skip_then_record_exit_idempotent() {
        let tmp = TempDir::new().unwrap();
        let h = ManifestHandle::new(tmp.path(), "T1.1", Utc::now());
        let id = h.record_skip(
            StageId::Plan,
            AgentRole::Planner,
            StageStatus::Skipped,
            "simple_task_skip_planner".to_string(),
            None,
        );
        let log_path = PathBuf::from("/tmp/skipped.jsonl");
        h.record_exit(
            id,
            StageStatus::Skipped,
            Utc::now(),
            AgentExitInfo {
                log_path: Some(log_path.clone()),
                actual_provider: String::new(),
                actual_model: String::new(),
                fallback_reason: None,
            },
        );
        let m = h.snapshot();
        let inv = &m.invocations[0];
        assert_eq!(inv.status, Some(StageStatus::Skipped));
        assert_eq!(inv.log_path, Some(log_path));
    }

    #[test]
    fn mark_superseded_sets_field() {
        let tmp = TempDir::new().unwrap();
        let h = ManifestHandle::new(tmp.path(), "T1.1", Utc::now());
        let id1 = h.record_invocation(empty_spec("", ""));
        let id2 = h.record_invocation(empty_spec("", ""));
        h.mark_superseded(id1, id2);
        let m = h.snapshot();
        assert_eq!(m.invocations[0].superseded_by, Some(2));
    }

    #[test]
    fn handle_clones_share_state() {
        let tmp = TempDir::new().unwrap();
        let h = ManifestHandle::new(tmp.path(), "T1.1", Utc::now());
        let h2 = h.clone();
        h2.record_invocation(empty_spec("", ""));
        let m = h.snapshot();
        assert_eq!(m.invocations.len(), 1);
    }

    #[test]
    fn read_manifest_recovers_next_invocation_id() {
        let tmp = TempDir::new().unwrap();
        let h = ManifestHandle::new(tmp.path(), "T1.1", Utc::now());
        h.record_invocation(empty_spec("", ""));
        h.record_invocation(empty_spec("", ""));
        h.record_invocation(empty_spec("", ""));
        h.flush().unwrap();
        let path = tmp.path().join("run-manifest.json");
        let m = read_manifest(&path).unwrap();
        assert_eq!(m.next_invocation_id, 4);
    }
}
