# Claude Code Rules

These rules are automatically loaded by [Claude Code](https://docs.anthropic.com/en/docs/claude-code) when working in this repository. Each file is scoped to specific paths via frontmatter -- Claude only sees a rule when it touches the files that rule covers.

This is how we keep AI-assisted contributions consistent with the project's architecture and conventions without requiring contributors to read and internalize everything upfront.

## Rules

| File | Scope | What it covers |
|------|-------|----------------|
| `architecture.md` | `src/app.rs`, `src/agent.rs`, `src/main.rs` | Build loop pipeline, module responsibilities, event system, agent invocation, review gate |
| `config.md` | `src/config.rs`, `.foundry.json` | Configuration schema, task format, git commit conventions |
| `plugins.md` | `plugins/**/*` | Plugin directory structure, available plugins, domain rules |
| `patterns.md` | `src/patterns.rs`, `**/*.json` | Legacy pattern JSON (deprecated, kept for back-compat fallback) |
| `prompts.md` | `src/prompts.rs` | Agent prompt functions, conventions, modification guidelines |
| `rust.md` | `src/**/*.rs` | Error handling, async patterns, code style, serde conventions, testing |

## How it works

Claude Code loads rules from `.claude/rules/` automatically. The `paths` frontmatter in each file controls when it activates:

```yaml
---
paths:
  - "src/patterns.rs"
  - "**/*.json"
---
```

This means `patterns.md` is only loaded when Claude is working with pattern-related files. Rules don't consume context window space when they're not relevant.

## For contributors

You don't need to read these files yourself -- they exist to guide Claude Code. But if you're curious about project conventions, they're a good reference for how the codebase is organized and what patterns to follow.
