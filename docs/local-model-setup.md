# Local Model Setup -- LM Studio + opencode

Foundry's Phase 32 routes the builder stage through the `opencode` CLI when the
user picks an LM Studio (or Ollama) model in the settings overlay. To exercise
that wiring end-to-end, you need: (1) `opencode` on PATH, (2) LM Studio running
with its OpenAI-compatible server bound to `http://127.0.0.1:1234`, and (3) at
least one model loaded inside LM Studio whose context window (`n_ctx`) is at
least 8192 tokens. Foundry's prompts plus `agent_system_directives` regularly
push past 4096 tokens; a smaller `n_ctx` produces the `exceeds the available
context size` error that P32.7 surfaces as `ContextOverflow`. After loading,
confirm the model is visible to opencode by running `opencode models lmstudio`
-- the leaf name (last path segment) is the canonical opencode model id.

To run the smoke test, build a release foundry binary (`cargo build --release`)
then execute `bash scripts/smoke-local-model.sh`. The script creates a throw-
away project in `$TMPDIR`, points `.foundry.json` at the first model returned
by `opencode models lmstudio`, runs `foundry run --no-tui --output-format json`,
and asserts five checks: foundry exits 0, the JSON output reports
`config.builder_provider == "opencode"`, at least one log file exists under
`.buildloop/logs/`, that log carries the opencode `sessionID` marker (and
zero log files carry Claude's `subtype:"init"` marker), and stderr is free of
the typed errors `ContextOverflow`, `ProviderUnreachable`, and `ModelNotLoaded`.
On PASS the script prints `[smoke] PASS  (workspace: ...)` and exits 0; pass
`--keep` to leave the workspace behind for inspection. The same gate is wired
to `cargo test --test local_model_smoke -- --ignored` for parity with the rest
of the test suite.
