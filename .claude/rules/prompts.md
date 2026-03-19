---
paths:
  - "src/prompts.rs"
---

# Prompt Engineering

## Prompt Functions
| Function | Role | Output |
|----------|------|--------|
| `planner_prompt()` | Plan implementation | `.buildloop/current-plan.md` |
| `builder_prompt()` | Execute plan | Code changes |
| `reviewer_prompt()` | Validate changes | `.buildloop/review-report.md` (JSON findings) |
| `fixer_prompt()` | Fix review issues | Code changes |
| `pattern_extraction_prompt()` | Extract learnings | `.buildloop/patterns-extracted.json` |
| `discovery_prompt()` | Find new work | Appends tasks to TASKS.md |

## Conventions
- Raw string literals: `r#"..."#`
- Pattern context injected as clearly delimited reference blocks (not authoritative instructions).
- Reviewer is combined audit+fix agent -- has Read, Glob, Grep, Edit, Write, Bash tools.
- Stack detection: looks for Cargo.toml (Rust), package.json (Node), pyproject.toml (Python), etc.
- Every finding must cite file, line, concrete issue, source_evidence (snippet + line_range + reasoning), and confidence (0.0-1.0).

## Reviewer Prompt Design (CCA-aligned)
- **Explicit criteria over vague instructions** (CCA 4.1): "what to report" and "what to skip" lists, not "be conservative."
- **Few-shot borderline examples** (CCA 4.2): three calibration cases at prompts.rs:572-602 showing HIGH vs MEDIUM vs LOW vs SKIP decisions with reasoning. These reduce false positives by demonstrating judgment, not rules.
- **Provenance requirement** (CCA 5.6): every finding includes source_evidence with the exact code snippet, line range, and reasoning chain. Findings without provenance are less actionable.
- **Confidence scores** (CCA 5.5): 0.0-1.0 self-assessment enables calibrated routing -- high-confidence findings auto-fix, low-confidence flag for manual review.
- **Multi-pass for large changesets** (CCA 4.6): reviewer_per_file_prompt and reviewer_integration_prompt split analysis to avoid attention dilution on 8+ file changes.

## When Modifying Prompts
- Keep prompts focused on the role -- planner plans, builder builds, reviewer audits+fixes.
- Maintain the JSON structure for review findings (review.rs parses it programmatically).
- Preserve the few-shot severity examples -- they are calibration data, not decoration.
- Test prompt changes with `cargo test` -- prompts.rs has unit tests for context wrapping.
- Pattern injection count scales by complexity (simple: 0-2, medium: 5, complex: 10).
