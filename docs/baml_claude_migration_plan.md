# BAML → Claude-CLI Alignment Plan

Goal: Make all BAML calls ride the same Claude CLI subscription (no OpenAI key, no direct Anthropic API key management by users) while keeping structured outputs stable.

## Principle
BAML itself calls providers via `clients.baml` definitions. It cannot natively “reuse” the CLI transport, but we can: (a) define Claude clients, and (b) auto-source the CLI’s stored credentials/model so users don’t supply API keys manually. Result: BAML uses the same subscription/model that the CLI is configured to use.

## Step 1: Add Claude clients in `tools/baml_schemas/clients.baml`
- Reintroduce `ClaudeCLI` (primary) and optional fallback `ClaudeCLILite` with `provider anthropic`.
- Model: read from env var (e.g., `env.CLAUDE_MODEL`) with default to a sane code-capable model (e.g., `claude-3.5-sonnet`), but allow override from the CLI config (see Step 2). Keep temperature low (0.0–0.2) for structured outputs.
- Keep OpenAI clients as cold backups only.

## Step 2: Auto-load CLI credentials/model in `tools/baml_integration.py`
- Detect the Claude CLI config (paths to probe: typical macOS `~/Library/Application Support/Claude/claude.json` or `~/.config/claude/config.json`; make the paths overridable via env `CLAUDE_CONFIG_PATH`).
- If `ANTHROPIC_API_KEY` is not set, read the CLI config and set it in-process before creating the BAML runtime. Do not require users to export anything manually.
- If the CLI config contains a default model, set `CLAUDE_MODEL` env accordingly so BAML uses the same model as the CLI.
- Provide clear error if neither env nor CLI config yields a key/model.

## Step 3: Point BAML functions to Claude clients
- Update schema files to use `client ClaudeCLI`:
  - `build_planning.baml` → `ClaudeCLI`
  - `scout.baml` → `ClaudeCLI` (Generate + Parse)
  - `architect.baml` → `ClaudeCLI` (Generate + Parse)
  - `builder.baml` → `ClaudeCLI` (Execute/Validate)
- Ensure any future schemas default to `ClaudeCLI` unless explicitly overridden.

## Step 4: Validation and tests
- Add unit tests (mocking `BamlRuntime`) to assert the runtime is initialized with Anthropic/Claude client and that env hydration happens when CLI config is present.
- Add an integration smoke: `python tools/use_baml.py status`, `... scout-report`, `... architecture`, `... validate-build-plan` with only the CLI config present (no env key).
- Update CI/pre-commit guidance: skip BAML integration tests if neither env key nor CLI config is available; otherwise run them.

## Step 5: Telemetry and logging
- When building the BAML client, log the chosen client, model, and credential source (env vs CLI config) to stderr for debugging.
- Emit actionable errors when credential/model is missing or CLI config can’t be read.

## Step 6: Cleanup and rollout
- Update docs/README to explain the “CLI-sourced” credential path and the optional env overrides.
- Demote OpenAI clients to fallback status (or remove) once Claude CLI sourcing is stable.
- Communicate migration steps: install/configure Claude CLI; ensure its config is present; run `python tools/use_baml.py status` to verify BAML sees the Claude client.
