# Smart Incremental Builds

**Status**: ✅ Phase 1 and Phase 2 delivered  
**Latest Update**: October 30 2025 (v2.2.0)  
**Target Impact**: 70‑90 % faster rebuilds, 80 %+ cache hit rate on iterative work

---

## 1. Overview

Smart Incremental Builds is the two-phase optimisation program that transforms how Context Foundry re-runs familiar work. It adds cross-project intelligence, file-level change awareness, and selective execution so the autonomous builder can skip expensive phases whenever possible.

| Capability | Phase 1 (Oct 25) | Phase 2 (Oct 30) | Implementation Notes |
|------------|-----------------|------------------|----------------------|
| Scout caching | ✅ Per-project reuse (24 h TTL) | ✅ Global cache shared at `~/.context-foundry/global-cache/scout` | `tools/cache/scout_cache.py`, `tools/incremental/global_scout_cache.py` |
| Test caching | ✅ Reuse results when source hashes unchanged | ✅ Hooked into orchestrator + incremental change reporting | `tools/cache/test_cache.py`, `tools/orchestrator_prompt.txt:1250` |
| File change detection | ❌ | ✅ Git diff first, SHA256 fallback | `tools/incremental/change_detector.py` |
| Incremental builder | ❌ | ✅ Dependency-aware plan + preservation | `tools/incremental/incremental_builder.py` |
| Test impact analysis | ❌ | ✅ Selective plan with coverage map | `tools/incremental/test_impact_analyzer.py` |
| Incremental docs | ❌ | ✅ Manifest-driven selective regeneration | `tools/incremental/incremental_docs.py` |
| Orchestrator integration | ⚡ Phase skip prompts | ⚡ Phase 2 hooks for cache/test/doc plans | `tools/orchestrator_prompt.txt` |

---

## 2. Phase Highlights

### Phase 1 – Foundation (Delivered Oct 25)
- Local cache infrastructure under `.context-foundry/cache/` with TTL metadata (`tools/cache/__init__.py`, `tools/cache/cache_manager.py`).
- Scout caching of research reports keyed by normalized task descriptions.
- Test-result caching that stores source file hashes to guarantee correctness.
- Orchestrator updates to check caches before the Scout and Test phases.
- Regression suite in `tests/test_cache_system.py` validating hashing, TTL, and cache cleanup.

### Phase 2 – Deep Incremental Intelligence (Delivered Oct 30)
- **Global Scout Cache**: reusable reports shared across projects with similarity matching and stats (`tools/incremental/global_scout_cache.py:1`, `tools/cache/__init__.py:1`).
- **Change Detector**: builds snapshots, prefers Git when available, falls back to hashing, and reports precise change sets (`tools/incremental/change_detector.py:21`).
- **Incremental Builder**: dependency graph construction, transitive impact calculation, and smart preservation plan (`tools/incremental/incremental_builder.py:25`).
- **Selective Testing**: coverage-map generation (currently Pytest-focused), threshold rules, and explicit skip/save reasoning (`tools/incremental/test_impact_analyzer.py:25`).
- **Incremental Documentation**: manifest of docs-to-sources plus README section tracking (`tools/incremental/incremental_docs.py:24`).
- Updated exports so incremental capabilities are available via `tools.cache` (`tools/cache/__init__.py:1`).
- Integration and smoke coverage in `tests/test_phase2_integration.py:1` with temporary directory workflows.

---

## 3. How It Works (Phase 2 Flow)

1. **Scout Phase**: look for local cache hit, then global cache (`save_scout_report_to_global_cache`, `get_cached_scout_report_global`). On success, copy metadata and skip the phase.
2. **Change Snapshot**: `capture_build_snapshot` writes git SHA + file hashes to `.context-foundry/last-build-snapshot.json` for future comparisons.
3. **Change Detection**: `detect_changes` produces a `ChangeReport` describing modified/added/deleted files, % churn, and whether Git or hashing was used.
4. **Incremental Build Plan**: `create_incremental_build_plan` loads/updates `.context-foundry/build-graph.json`, determines affected files (transitive), and outputs preserve/rebuild lists.
5. **Selective Tests**: `create_test_plan` reads or generates `.context-foundry/test-coverage-map.json`, decides whether to run all or only affected tests, and estimates time saved.
6. **Incremental Docs**: `create_docs_plan` uses `.context-foundry/docs-manifest.json` to skip untouched documentation and screenshots.
7. **Execution & Cache Save**: Orchestrator applies the plan, preserves files from `.context-foundry/previous-build`, runs the chosen tests, and saves fresh cache metadata.

---

## 4. Usage

```python
from tools.mcp_client import autonomous_build_and_deploy

autonomous_build_and_deploy(
    task="Build a todo app with incremental mode",
    working_directory="/tmp/todo-app",
    incremental=True,
    force_rebuild=False  # Set True to bypass caching
)
```

Enable or tune features through `.env` (defaults shown in `./.env.example:80`):

```
INCREMENTAL_PHASE2_ENABLED=true
GLOBAL_SCOUT_CACHE_TTL_HOURS=168
INCREMENTAL_BUILDER_ENABLED=true
INCREMENTAL_BUILDER_THRESHOLD=30
INCREMENTAL_DOCS_ENABLED=true
INCREMENTAL_DOCS_THRESHOLD=30
```

Set `force_rebuild=True` or `INCREMENTAL_PHASE2_ENABLED=false` for one-off full builds.

---

## 5. Testing

- **Unit Tests**: `tests/test_cache_system.py`, `tests/test_cache_integration.py`, and module-specific unit tests embedded in `tests/test_phase2_integration.py`.
- **Integration**: `tests/test_phase2_integration.py:120` runs end-to-end incremental workflows (snapshot → detect changes → build plan).
- **PyTest Command**: `pytest tests/test_phase2_integration.py -v` exercises all Phase 2 components via temporary projects.
- **Real-world Logs**: `tests/real_world_incremental_test.md` documents observed speedups and cache hit rates during validation runs.

---

## 6. Performance Guidance

- Re-running a build with **zero changes** should reuse snapshots and skip tests, targeting ~95 % time savings.
- **Small code edits** (≤5 files in a medium project) typically rebuild only the touched modules and their dependents, saving 70‑90 %.
- **Docs-only updates** trigger docs manifest checks so tests and builder work can be skipped entirely.
- Use `tools/incremental/global_scout_cache.get_global_scout_cache_stats()` to monitor cache utilisation and detect stale entries.

---

## 7. File & Manifest Layout

```
.context-foundry/
├── cache/                         # Phase 1 per-project caches
├── last-build-snapshot.json       # Change detector snapshot
├── build-graph.json               # Dependency graph for builder
├── test-coverage-map.json         # Test impact analyzer input
└── docs-manifest.json             # Incremental docs manifest

~/.context-foundry/
└── global-cache/
    └── scout/
        ├── cache-<hash>.json      # Global Scout entries
        └── ...                    # Metadata & stats
```

Modules live under `tools/incremental/` with shared exports through `tools/cache/__init__.py`.

---

## 8. Troubleshooting

- **Cache misses expected hits**: verify `incremental=True` in task config, inspect `.context-foundry/cache/` and `~/.context-foundry/global-cache/scout/` for existing entries, ensure TTL values haven’t expired.
- **Incremental builder rebuilds too much**: inspect `.context-foundry/build-graph.json` and the logged change percentage; large diffs (> threshold) intentionally fall back to full rebuilds.
- **Selective tests running everything**: check change percentage; if it exceeds `INCREMENTAL_BUILDER_THRESHOLD`, `create_test_plan` forces a full run for safety (`tools/incremental/test_impact_analyzer.py:255`).
- **Docs regenerated unexpectedly**: confirm `docs-manifest.json` sources cover your new files—update manifest logic if new doc types were introduced.

---

## 9. Roadmap

- **Short Term**: broaden coverage-map support beyond Pytest, improve JS/TS dependency resolution, persist incremental builder metrics for dashboards.
- **Future Phases**: parallelised selective testing, incremental documentation rendering, distributed cache backends, ML-driven change impact predictions.

Smart Incremental Builds is now the default optimisation path for Context Foundry. Continue extending manifests, dependency heuristics, and coverage analysis to tighten skip accuracy without sacrificing safety.
