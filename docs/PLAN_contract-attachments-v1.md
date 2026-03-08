# Plan: Contract Attachments v1

Date: 2026-03-07
Version: v1
Status: implemented

## Context

Studio's `ExecutionContract` is a markdown instruction document. It tells the agent *how to work*. There is currently no mechanism for the user to say "also read *this specific material* before you start." The `ProjectScan` provides shallow automatic discovery (top-level entries, stack signals, data candidates up to depth 3), but it is not user-directed and not per-contract.

This plan adds **Attachments** -- bounded, per-contract file/folder inclusions that get resolved at run time and injected into the prompt alongside the contract.

Framing: "Contracts tell the agent how to work. Attachments tell it what extra material to read."

## Current State

- `ExecutionContract` struct: `studio.rs:314` -- `{ file_name, path, name, body }`
- Contracts are `.md` files in `.foundry/studio/contracts/`: `studio.rs:2424`
- Loaded by `load_execution_contracts_with_selection`: `studio.rs:2506`
- Rendered into the prompt by `compose_smoothed_prompt`: `studio.rs:2283`
- Prompt template injects contract between `--- BEGIN/END EXECUTION CONTRACT ---` delimiters: `studio.rs:2314`
- `ProjectScan` provides automatic context: `studio.rs:2151`
- In isolated mode, `prepare_workspace` copies a snapshot: `studio.rs:1392`, via `copy_workspace_snapshot`: `studio.rs:2762`
- The workspace copy uses `should_skip_snapshot_path` for exclusion: `studio.rs:2813`
- Contracts pane renders a selectable list: `studio.rs:1753`
- Execution Brief pane previews the rendered prompt: `studio.rs:1804`
- `SessionLaunch` carries the contract to the session runner: `studio.rs:1293`

## Domain Model

### Three Types

```rust
/// Persisted specification of what material to attach to a contract.
/// Stored in a sidecar JSON file next to the contract markdown.
#[derive(Clone, Debug, Serialize, Deserialize)]
struct AttachmentSpec {
    /// Path relative to the project root. Must not escape the project.
    path: String,
    /// How to present this material.
    mode: AttachmentMode,
    /// Optional label for the prompt section header. Defaults to the path.
    #[serde(default, skip_serializing_if = "Option::is_none")]
    label: Option<String>,
}

#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
enum AttachmentMode {
    /// Read the file and include its full content (single file only).
    /// Capped at MAX_INLINE_FILE_BYTES.
    InlineFile,
    /// List the directory tree: names, sizes, structure.
    /// Capped at MAX_TREE_DEPTH / MAX_TREE_FILES.
    DirectoryTree,
}

/// Runtime-resolved attachment with actual content ready for prompt injection.
#[derive(Clone, Debug)]
struct ResolvedAttachment {
    spec: AttachmentSpec,
    /// The display label (spec.label or spec.path).
    label: String,
    /// The resolved content to inject.
    content: String,
    /// Whether the content was truncated.
    truncated: bool,
    /// If resolution failed, the error message. Content will be the error text.
    error: Option<String>,
}
```

### Constants

```rust
const MAX_INLINE_FILE_BYTES: usize = 64 * 1024;      // 64 KB
const MAX_TREE_DEPTH: usize = 3;
const MAX_TREE_FILES: usize = 50;
const MAX_TOTAL_ATTACHMENT_CHARS: usize = 100_000;     // ~100K chars across all attachments
```

### On-Disk Format

Sidecar JSON file next to the contract markdown. Name derived by replacing `.md` with `.attachments.json`.

```
.foundry/studio/contracts/
  standard.md
  standard.attachments.json          # optional; [] if absent or missing
  reporting.md
  reporting.attachments.json
```

Example `reporting.attachments.json`:
```json
[
  { "path": "data/sales.csv", "mode": "inline_file", "label": "Sales Data" },
  { "path": "docs/", "mode": "directory_tree" }
]
```

Why JSON over TOML: the TUI already uses serde_json throughout. Adding a TOML dependency for one file type is not worth it. Users can edit JSON; the structure is flat.

Why sidecar over frontmatter: keeps contracts as pure markdown. Users edit them in vim/vscode without worrying about metadata headers. The sidecar is machine-owned.

## Implementation Steps

### Step 1: Add types and constants

- [x] T1.1: Add `AttachmentSpec`, `AttachmentMode`, `ResolvedAttachment` structs to `studio.rs`
- [x] T1.2: Add attachment constants (`MAX_INLINE_FILE_BYTES`, `MAX_TREE_DEPTH`, `MAX_TREE_FILES`, `MAX_TOTAL_ATTACHMENT_CHARS`)

### Step 2: Sidecar loading

- [x] T2.1: Add `fn attachment_sidecar_path(contract_path: &Path) -> PathBuf` -- replaces `.md` extension with `.attachments.json`
- [x] T2.2: Add `fn load_attachment_specs(contract_path: &Path) -> Vec<AttachmentSpec>` -- reads and deserializes the sidecar; returns `Vec::new()` on missing file or parse error (log warning on parse error)
- [x] T2.3: Extend `ExecutionContract` struct with `attachments: Vec<AttachmentSpec>` field
- [x] T2.4: Update `load_execution_contracts_with_selection` to call `load_attachment_specs` for each contract and populate the new field

### Step 3: Runtime resolution

- [x] T3.1: Add `fn resolve_attachment(spec: &AttachmentSpec, project_dir: &Path) -> ResolvedAttachment`
  - Validates path is relative, contains no `..` components, and is not absolute
  - Joins `project_dir` + `spec.path`, canonicalizes the result, and verifies it starts with the canonicalized `project_dir` (catches symlink escape)
  - For `InlineFile`: reads file content, truncates at `MAX_INLINE_FILE_BYTES`, sets `truncated` flag
  - For `DirectoryTree`: walks directory up to `MAX_TREE_DEPTH` / `MAX_TREE_FILES`, produces indented tree listing with file sizes, uses `should_skip_snapshot_path` for exclusion
  - All displayed paths in resolved content must be repo-relative (never host-absolute)
  - On any error (file not found, permission denied, path escape, symlink escape): returns `ResolvedAttachment` with `error` set and `content` = error message
- [x] T3.2: Add `fn resolve_all_attachments(specs: &[AttachmentSpec], project_dir: &Path) -> Vec<ResolvedAttachment>` -- resolves each spec, then enforces `MAX_TOTAL_ATTACHMENT_CHARS` by truncating the last attachment(s) if the total exceeds the cap
- [x] T3.3: Add `fn format_attachments_block(resolved: &[ResolvedAttachment]) -> String` -- produces the prompt block:
  ```
  Attached context:
  --- BEGIN ATTACHMENT: <label> (<mode>, <line count> lines) ---
  <content>
  --- END ATTACHMENT: <label> ---
  ```
  Returns empty string if no attachments.

### Step 4: Preview caching

- [x] T4.1: Add `preview_cache: Option<PreviewPromptCache>` field to `StudioState`
- [x] T4.2: Populate the cache in `preview_prompt(&mut self)` -- resolve the selected contract's attachments against `self.project_dir`, compose the rendered prompt, and store the final preview string
- [x] T4.3: Invalidate the cache (set to `None`) on: contract cycle (`cycle_execution_contract`), contract edit return (`PendingStudioAction::EditExecutionContract` completion), attachment edit return (new `t` keybind completion), rescan (`r`), prompt edits, provider/workspace mode changes, and contract create/delete
- [x] T4.4: In `preview_prompt`, if cache is `None` resolve attachments and compose the prompt once, then reuse the cached rendered preview. This keeps disk I/O out of the 100ms render loop.

### Step 5: Prompt integration

- [x] T5.1: Extend `compose_smoothed_prompt` signature to accept `attachments: &[ResolvedAttachment]`
- [x] T5.2: Insert the formatted attachments block after `--- END EXECUTION CONTRACT ---` and before `Project scan:`
- [x] T5.3: Update all call sites of `compose_smoothed_prompt`:
  - `preview_prompt` (`studio.rs:563`): use cached resolved attachments
  - `run_session` (`studio.rs:1331`): resolve attachments fresh at session start (not from cache -- session must use current disk state), pass to `compose_smoothed_prompt`

### Step 6: TUI display

- [x] T6.1: Update `render_contracts` (`studio.rs:1753`) to show attachment count: `> standard [2 attached]` or just `> standard` when zero
- [x] T6.2: The Execution Brief pane (`render_preview`) already renders the full prompt, so attachments will appear naturally after the contract. No separate rendering needed.
- [x] T6.3: Add `t` keybind when Contracts pane is focused: on macOS, leave the TUI and open a native file/folder picker that appends attachment entries to the selected contract; on other platforms, fall back to opening the sidecar JSON in the editor
- [x] T6.4: After the picker/editor returns for `t`, reload attachments for the edited contract and invalidate the preview cache

### Step 7: Tests

- [x] T7.1: Test `load_attachment_specs` -- missing file returns empty vec, valid JSON round-trips, malformed JSON returns empty vec
- [x] T7.2: Test `resolve_attachment` for `InlineFile` -- file exists, file missing, file exceeds max size (truncation)
- [x] T7.3: Test `resolve_attachment` for `DirectoryTree` -- directory exists, empty directory, directory exceeds max files
- [x] T7.4: Test path validation -- reject `../../../etc/passwd`, reject absolute paths, reject symlink that escapes project root, accept normal relative paths
- [x] T7.5: Test `format_attachments_block` -- empty vec produces empty string, single attachment produces correct delimiters, all paths in output are repo-relative
- [x] T7.6: Test `compose_smoothed_prompt` with attachments -- verify block appears between contract and scan
- [x] T7.7: Test `attachment_sidecar_path` -- `standard.md` -> `standard.attachments.json`
- [x] T7.8: Test total attachment cap -- two large attachments, second gets truncated
- [x] T7.9: Test preview cache invalidation -- cache is `Some` after first preview, `None` after contract cycle

## Architecture Decisions

**Attachments are per-contract, not global.** When you cycle contracts with `c`, the attachments switch too. The reporting contract wants CSVs; the refactoring contract wants source files. This is the right granularity.

**v1 restricts to repo-relative paths only.** External absolute paths would require explicit mounting/copying logic -- that's a phase 2 concern. Note that repo-relative does not guarantee the path exists in an isolated workspace: `copy_workspace_snapshot` (`studio.rs:2762`) excludes `.git`, `target`, `node_modules`, `.foundry/studio`, and other paths via `should_skip_snapshot_path` (`studio.rs:2813`). This is fine because attachments are resolved from `project_dir` (the original) and inlined into the prompt text. The agent receives the content, not a file path to read. If an attached path happens to be excluded from the workspace copy, the agent still sees its content but cannot modify it -- which is the correct behavior for read-only context material.

**Resolution happens at run time with preview caching.** `AttachmentSpec`s are loaded with contracts (once at startup, reloaded on editor return). The actual disk reads that produce `ResolvedAttachment`s happen:
- For **sessions**: fresh at session start, so the agent always gets current content.
- For **preview**: cached in `StudioState.preview_cache` as the fully rendered preview prompt. The cache is invalidated on contract cycle, contract/attachment edit return, rescan, prompt edits, provider/workspace mode changes, and contract create/delete. This keeps disk I/O out of the 100ms TUI render loop.

**Path safety uses canonicalization, not just string checks.** `resolve_attachment` joins `project_dir` + `spec.path`, canonicalizes the result with `fs::canonicalize`, and verifies the canonical path starts with the canonical `project_dir`. This catches symlink escape (e.g. `data/sneaky-link` -> `/etc/shadow`) in addition to `..` traversal and absolute paths.

**All displayed paths are repo-relative.** Resolved attachment content (tree listings, error messages, prompt section headers) uses paths relative to the project root, never host-absolute paths. In isolated mode the agent only has the workspace copy, so `docs/api.md` is actionable; `/Users/name/.../docs/api.md` is not.

**Attachments are injected into the prompt, not passed as files.** Claude CLI's `--print` mode takes a single prompt string. The prompt is the only injection point. This means attachment content counts against the context window, which is why bounds are critical.

**Errors don't abort the run.** A missing attachment produces a visible error block in the prompt (`[ATTACHMENT ERROR: file not found: data/missing.csv]`) rather than preventing the session from starting. The user can see the error in the Execution Brief preview before starting.

## v1 Scope Boundaries

**In scope:**
- `AttachmentSpec` / `ResolvedAttachment` types
- Sidecar JSON loading
- `InlineFile` and `DirectoryTree` modes
- Prompt injection
- TUI indicator (`[N attached]`) and editor keybind (`t`)
- Path validation (relative only, no escape, symlink canonicalization)
- Size/depth/count bounds
- Preview caching with invalidation
- Repo-relative display paths only
- Tests

**Explicitly out of scope (phase 2+):**
- `GlobContent` / `DirectoryInlineMatches` mode
- External (absolute) paths
- `ExecutionProfile` umbrella type
- TUI inline attachment editor (phase 1 uses external editor on the JSON)
- Per-attachment size override in the spec

## Risks and Open Questions

1. **Sidecar file lifecycle.** When `create_execution_contract` or `delete_selected_execution_contract` runs, the sidecar should be created empty / moved to trash alongside the `.md`. The existing trash logic at `studio.rs:2677` already moves to `.trash/`; extend it to also move the sidecar.

2. **Contract rename.** There is no rename operation today. If one is added later, the sidecar must be renamed in lockstep.

3. **Isolated mode: attached paths excluded from workspace.** Paths like `.git/config` or files inside `target/` are excluded from the isolated workspace copy by `should_skip_snapshot_path`. Since we inline content into the prompt (resolved from `project_dir`), the agent still receives the content. But if the agent tries to modify an attached file that wasn't copied to the workspace, it won't find it. This is acceptable: attachments are read-only context, not editable inputs. The `DirectoryTree` listing should note if a listed path falls under a snapshot-excluded prefix, so the agent knows not to try editing it.

4. **Symlink canonicalization on missing targets.** `fs::canonicalize` requires the target to exist. If an attached path doesn't exist yet (e.g. an output directory), canonicalization fails. `resolve_attachment` should handle this: first check `Path::is_relative()` and no `..` components (string-level), then attempt canonicalization only if the path exists. If it doesn't exist, report a file-not-found error in the `ResolvedAttachment`.

5. **Cross-platform attachment UX.** On macOS, `t` uses a native picker and writes the sidecar automatically. On other platforms, the fallback is still raw JSON editing. A fully inline TUI attachment manager would still be a better phase 2 UX.

6. **Cache staleness window.** The preview cache is invalidated on explicit user actions (contract cycle, edit, rescan) but not on external file changes. If the user modifies an attached file outside Studio, the preview won't update until the next invalidation event. This is acceptable -- `r` (rescan) is the escape hatch and is already wired.

## Migration Path

Zero migration needed. The only structural change is adding `attachments: Vec<AttachmentSpec>` to `ExecutionContract` with a default of `Vec::new()`. All existing contracts load with no sidecar file, get an empty attachment list, and behave identically to today. No existing tests break. No disk format changes for existing files.
