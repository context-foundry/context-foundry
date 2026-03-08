use crate::utils::truncate_str;
use std::path::Path;

use super::{
    attachments::{format_attachments_block, ResolvedAttachment},
    model::{
        ExecutionContract, SessionState, FOLLOW_UP_CONTEXT_MAX_CHARS, FOLLOW_UP_CONTEXT_MAX_LINES,
    },
    scan::ProjectScan,
    shared::join_or_none,
};

#[allow(clippy::too_many_arguments)]
pub(super) fn compose_smoothed_prompt(
    provider_label: &str,
    raw_prompt: &str,
    execution_contract: &ExecutionContract,
    attachments: &[ResolvedAttachment],
    scan: &ProjectScan,
    workspace_dir: &str,
    artifact_dir: &str,
    prior_context: Option<&str>,
) -> String {
    let prior_context_block = prior_context
        .filter(|text| !text.trim().is_empty())
        .map(|text| {
            format!(
                "\n\nPrevious session context:\n--- BEGIN PRIOR OUTPUT ---\n{}\n--- END PRIOR OUTPUT ---",
                text
            )
        })
        .unwrap_or_default();
    let rendered_contract = render_execution_contract_body(
        &execution_contract.body,
        provider_label,
        workspace_dir,
        artifact_dir,
    );
    let attachments_block = format_attachments_block(attachments);
    format!(
        r#"You are running inside Foundry Studio through the {provider_label} CLI.

User objective:
{raw_prompt}

Execution contract: {contract_name}
--- BEGIN EXECUTION CONTRACT ---
{rendered_contract}
--- END EXECUTION CONTRACT ---{attachments_block}

Project scan:
- stack signals: {stack}
- top-level entries: {top}
- likely data/report inputs: {data}
- likely output areas: {outputs}
- Keep changes scoped to the request and leave unrelated files untouched.{prior_context_block}"#,
        contract_name = execution_contract.name,
        stack = join_or_none(&scan.stack_signals, ", "),
        top = join_or_none(&scan.top_level, ", "),
        data = join_or_none(&scan.data_candidates, ", "),
        outputs = join_or_none(&scan.output_targets, ", "),
    )
}

pub(super) fn render_execution_contract_body(
    body: &str,
    provider_label: &str,
    workspace_dir: &str,
    artifact_dir: &str,
) -> String {
    body.replace("{{provider_label}}", provider_label)
        .replace("{{workspace_dir}}", workspace_dir)
        .replace("{{artifact_dir}}", artifact_dir)
}

pub(super) fn follow_up_context(session: &SessionState) -> String {
    let mut tail = Vec::new();
    let mut total_chars = 0usize;

    for line in session
        .output
        .iter()
        .rev()
        .filter(|line| !line.trim().is_empty())
        .take(FOLLOW_UP_CONTEXT_MAX_LINES)
    {
        let capped_line = truncate_str(line, FOLLOW_UP_CONTEXT_MAX_CHARS);
        let additional_chars = capped_line.len() + usize::from(!tail.is_empty());
        if total_chars + additional_chars > FOLLOW_UP_CONTEXT_MAX_CHARS {
            if tail.is_empty() {
                tail.push(capped_line.to_string());
            }
            break;
        }
        tail.push(capped_line.to_string());
        total_chars += additional_chars;
    }

    tail.reverse();
    tail.join("\n")
}

pub(super) fn follow_up_workspace_issue(workspace_dir: &Path) -> Option<String> {
    if !workspace_dir.exists() {
        Some(format!(
            "follow-up blocked: selected workspace no longer exists: {}",
            workspace_dir.display()
        ))
    } else if !workspace_dir.is_dir() {
        Some(format!(
            "follow-up blocked: selected workspace is not a directory: {}",
            workspace_dir.display()
        ))
    } else {
        None
    }
}

#[cfg(test)]
mod tests {
    use super::super::{
        attachments::{AttachmentMode, AttachmentSpec, ResolvedAttachment},
        model::{SessionStatus, FOLLOW_UP_CONTEXT_MAX_CHARS},
        test_helpers::{test_contract, test_scan, test_session},
    };
    use super::{
        compose_smoothed_prompt, follow_up_context, follow_up_workspace_issue,
        render_execution_contract_body,
    };

    #[test]
    fn smoothed_prompt_includes_artifact_contract() {
        let mut scan = test_scan();
        scan.top_level.push("Cargo.toml".into());

        let prompt = compose_smoothed_prompt(
            "Claude",
            "Build me a usage dashboard.",
            &test_contract(),
            &[],
            &scan,
            "/tmp/workspace",
            "/tmp/workspace/.foundry/studio/artifacts/run/claude",
            None,
        );

        assert!(prompt.contains("Build me a usage dashboard."));
        assert!(prompt.contains("BEGIN EXECUTION CONTRACT"));
        assert!(prompt.contains("/tmp/workspace/.foundry/studio/artifacts/run/claude"));
    }

    #[test]
    fn compose_smoothed_prompt_places_attachments_between_contract_and_scan() {
        let attachment = ResolvedAttachment {
            spec: AttachmentSpec {
                path: "docs/api.md".into(),
                mode: AttachmentMode::InlineFile,
                label: None,
            },
            label: "docs/api.md".into(),
            content: "# API".into(),
            truncated: false,
            error: None,
        };

        let prompt = compose_smoothed_prompt(
            "Claude",
            "Build me a usage dashboard.",
            &test_contract(),
            &[attachment],
            &test_scan(),
            "/tmp/workspace",
            "/tmp/workspace/.foundry/studio/artifacts/run/claude",
            None,
        );

        let contract_end = prompt
            .find("--- END EXECUTION CONTRACT ---")
            .expect("missing contract end marker");
        let attachment_start = prompt
            .find("--- BEGIN ATTACHMENT: docs/api.md")
            .expect("missing attachment block");
        let scan_start = prompt.find("Project scan:").expect("missing project scan");

        assert!(contract_end < attachment_start);
        assert!(attachment_start < scan_start);
    }

    #[test]
    fn execution_contract_body_renders_placeholders() {
        let rendered = render_execution_contract_body(
            "use {{provider_label}} in {{workspace_dir}} and write to {{artifact_dir}}",
            "Claude",
            "/tmp/workspace",
            "/tmp/artifacts",
        );

        assert!(rendered.contains("Claude"));
        assert!(rendered.contains("/tmp/workspace"));
        assert!(rendered.contains("/tmp/artifacts"));
    }

    #[test]
    fn follow_up_context_is_capped_by_character_budget() {
        let mut session = test_session(SessionStatus::Succeeded);
        session.output = vec![
            "older line".into(),
            "x".repeat(FOLLOW_UP_CONTEXT_MAX_CHARS),
            "latest line".into(),
        ];

        let context = follow_up_context(&session);
        assert!(context.len() <= FOLLOW_UP_CONTEXT_MAX_CHARS);
        assert!(context.contains("latest line"));
    }

    #[test]
    fn follow_up_workspace_issue_detects_missing_path() {
        let missing = std::env::temp_dir().join(format!(
            "foundry-missing-workspace-{}",
            chrono::Utc::now().timestamp_nanos_opt().unwrap_or_default()
        ));
        let issue = follow_up_workspace_issue(&missing);
        assert!(issue.is_some());
        assert!(issue.unwrap_or_default().contains("no longer exists"));
    }
}
