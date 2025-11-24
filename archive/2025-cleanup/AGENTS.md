# Repository Guidelines

## Project Structure & Module Organization
Core orchestration lives in `foundry/` (phase managers, spawn logic) and `ace/` (Agent Control Engine primitives). MCP entry points, CLI helpers, and automation glue are under `tools/` and `scripts/`. Prompts and auto-generated assets live in `prompts/`, `templates/`, and `docs/`. Tests reside in `tests/` plus targeted scenario suites like `test_real_delegation.py`; fixtures and schemas sit in `schemas/` and `config/`. Keep large assets out of the repo—store only references inside `public/` or `docs/assets/`.

## Build, Test, and Development Commands
```bash
python -m venv venv && source venv/bin/activate  # isolate deps
pip install -r requirements-mcp.txt             # minimal MCP stack
ruff check --fix && ruff format                 # lint + format Python
pytest tests/ -m "not slow"                     # fast validation loop
pytest --cov=ace --cov=foundry                  # full coverage sweep
pre-commit run --all-files                      # mirror CI hooks
```
Run scripts from repo root; most utilities (e.g., `tools/mcp_server.py`) assume relative paths.

## Coding Style & Naming Conventions
Python code uses 4-space indents, type hints, and Ruff’s defaults (PEP 8 + sane extras). Modules and functions follow `snake_case`; classes use `PascalCase`; constants stay uppercase. Prefer dataclasses or TypedDicts for structured data passed between agents. Keep prompt YAML/JSON compact, and place autonomous workflow specs in `templates/<feature>/` with descriptive, hyphenated filenames. Avoid ad-hoc logging—reuse the structured logger in `foundry.telemetry`.

## Testing Guidelines
Pytest is authoritative (`pytest.ini` defines markers). Name files `test_<topic>.py` and functions `test_<behavior>`. Every feature touching orchestration must include `tier1` coverage; longer flows may mark supporting cases as `tier2` or `slow`. When adding new autonomous flows, include golden prompt fixtures and, if applicable, integration probes under `tests/integration/`. Run `pytest -m "tier1 and not slow"` before opening a PR and attach coverage deltas when touching critical services.

## Commit & Pull Request Guidelines
Follow the existing Conventional Commit style (`feat:`, `fix:`, `test:`, etc.) so changelog automation stays accurate. Squash noisy WIP history locally; each commit should be reviewable and green against `pre-commit`. PRs must include: concise summary, linked issue or task ID, reproduction or validation steps (paste pytest/ruff output), and screenshots for UI-facing artifacts listed under `docs/screenshots/`. Tag security-sensitive updates with `SECURITY.md` guidance and request review from an owner in `.github/CODEOWNERS` when touching deployment or credential code paths.
