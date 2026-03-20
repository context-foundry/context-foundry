# Archive

Retired components preserved for future reference.

## studio/

Interactive multi-model TUI workspace (Claude + Codex side-by-side prompting).
Retired 2026-03-20 -- features were absorbed into the main Foundry TUI.

Notable ideas worth revisiting:
- **Execution Contracts** (`contracts.rs`, `model.rs`) -- reusable prompt preambles/guidelines
- **Attachments** (`attachments.rs`) -- file/directory tree specs resolved and injected into prompts
- **Multi-provider sessions** (`session.rs`, `providers.rs`) -- running Claude and Codex in parallel
