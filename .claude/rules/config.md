# Configuration

## `.foundry.json` (project root)
```json
{
  "planner_model": "opus",
  "builder_model": "opus",
  "reviewer_model": "opus",
  "fixer_model": "opus",
  "discovery_model": "opus",
  "pause_between_tasks_secs": 5,
  "pause_between_cycles_secs": 30,
  "agent_timeout_secs": 600,
  "patterns_dir": "~/.foundry/patterns"
}
```
All fields optional — `#[serde(default)]` provides sensible defaults.

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
