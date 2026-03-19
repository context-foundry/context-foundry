---
paths:
  - "src/config.rs"
  - ".foundry.json"
  - "**/.foundry.json"
---

# Configuration

## `.foundry.json` (project root) and `~/.foundry/config.json` (global defaults)

Global config provides defaults for all projects. Project `.foundry.json` overrides.
`Config::load()` reads global first, then merges project fields on top via JSON object merge.

Key config groups:
```json
{
  "run_mode": "auto|sprint|review",
  "builder_models": ["claude:opus", "codex:"],
  "dual_selection": "first|second|both|",
  "planner_model": "opus",
  "builder_model": "opus",
  "reviewer_model": "sonnet",
  "fixer_model": "sonnet",
  "discovery_model": "opus",
  "scout_provider": "claude",
  "planner_provider": "claude",
  "builder_provider": "claude",
  "reviewer_provider": "claude",
  "review_multipass_threshold": 8,
  "confidence_threshold": 0.5,
  "skip_planner_for_simple": true,
  "adaptive_pauses": true,
  "create_issue_on_wip": false,
  "auto_push_remote": null,
  "agent_timeout_secs": 600,
  "patterns_dir": "~/.foundry/patterns",
  "theme": "dark"
}
```
All fields optional -- `#[serde(default)]` provides sensible defaults.
`Config::for_pipeline(spec)` overrides all provider fields for dual-model routing.
`Config::normalize_model_for_provider()` clears model names incompatible with the target provider.

## TASKS.md Task Format
```markdown
- [ ] T1.1: Short task description
- [x] T1.2: Completed task (checked by build loop)
- [ ] D1.1: Discovery-generated task (round 1)
```
Task ID regex: `^([A-Za-z]\d+\.\d+):\s*`

## Git Commit Convention
- Pass: `feat(T1.1): Short task description`
- Fail: `WIP(T1.1): Short task description`
- Footer: `Automated by: foundry`
- Commits `git add -A` but resets `.buildloop/logs/` before staging.
