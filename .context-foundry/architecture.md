# Architecture: Smart Incremental Builds Phase 2

## System Architecture Overview

```
Phase 2 Incremental Build System
═══════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────┐
│                     Orchestrator                             │
│  (tools/orchestrator_prompt.txt - Phase 2 integration)      │
└──────────────────┬───────────────────────────────────────────┘
                   │
    ┌──────────────┼──────────────┬──────────────┬────────────┐
    │              │              │              │            │
    ▼              ▼              ▼              ▼            ▼
┌────────┐   ┌─────────┐   ┌──────────┐   ┌─────────┐  ┌─────────┐
│ Global │   │ Change  │   │Increment │   │  Test   │  │Increm.  │
│ Scout  │   │Detector │   │ Builder  │   │ Impact  │  │  Docs   │
│ Cache  │   │         │   │          │   │Analyzer │  │         │
└────────┘   └─────────┘   └──────────┘   └─────────┘  └─────────┘
    │              │              │              │            │
    ▼              ▼              ▼              ▼            ▼
┌────────────────────────────────────────────────────────────────┐
│            ~/.context-foundry/global-cache/                    │
│            .context-foundry/cache/ (project-local)             │
└────────────────────────────────────────────────────────────────┘
```

## Module Breakdown

### 1. Global Scout Cache (`tools/incremental/global_scout_cache.py`)

**Purpose**: Share Scout analysis across all projects

**API**:
```python
def get_global_cache_dir() -> Path:
    """Returns ~/.context-foundry/global-cache/scout/"""

def generate_global_scout_key(
    task: str,
    project_type: str,
    tech_stack: List[str]
) -> str:
    """Generate cache key from semantic components"""

def get_cached_scout_report_global(
    task: str,
    project_type: str,
    tech_stack: List[str],
    ttl_hours: int = 168  # 7 days
) -> Optional[str]:
    """Retrieve Scout report from global cache"""

def save_scout_report_to_global_cache(
    task: str,
    project_type: str,
    tech_stack: List[str],
    scout_report: str,
    metadata: Dict[str, Any]
) -> None:
    """Save Scout report to global cache with metadata"""

def find_similar_cached_reports(
    task: str,
    project_type: str,
    tech_stack: List[str],
    similarity_threshold: float = 0.85
) -> List[Tuple[str, float, Dict]]:
    """Find similar cached reports by semantic similarity"""
```

**Cache Entry Structure**:
```json
{
  "cache_key": "hash123...",
  "task": "Build a weather app with React",
  "normalized_task": "build weather app react",
  "project_type": "web-app",
  "tech_stack": ["react", "javascript", "es6"],
  "created_at": "2025-01-13T00:00:00Z",
  "accessed_count": 5,
  "last_accessed": "2025-01-13T10:30:00Z",
  "scout_report": "# Scout Report\n...",
  "metadata": {
    "success": true,
    "build_duration_minutes": 12.5
  }
}
```

### 2. Change Detector (`tools/incremental/change_detector.py`)

**Purpose**: Detect which files changed since last build

**API**:
```python
def get_last_build_snapshot_path(working_directory: str) -> Path:
    """Returns .context-foundry/last-build-snapshot.json"""

def capture_build_snapshot(working_directory: str) -> Dict[str, Any]:
    """Capture current state: git SHA + file hashes"""

def detect_changes(
    working_directory: str,
    previous_snapshot: Dict[str, Any]
) -> ChangeReport:
    """Detect changes between snapshots"""

@dataclass
class ChangeReport:
    changed_files: List[str]  # Files modified
    added_files: List[str]    # New files
    deleted_files: List[str]  # Removed files
    unchanged_files: List[str]  # Same as before
    change_percentage: float  # % of files changed
    git_available: bool  # Whether git was used
    git_diff_sha: Optional[str]  # Git commit SHA
```

**Snapshot Structure**:
```json
{
  "timestamp": "2025-01-13T00:00:00Z",
  "git_sha": "abc123...",
  "git_available": true,
  "file_hashes": {
    "tools/mcp_server.py": "sha256...",
    "tools/cache/scout_cache.py": "sha256..."
  },
  "total_files": 45
}
```

### 3. Incremental Builder (`tools/incremental/incremental_builder.py`)

**Purpose**: Preserve unchanged files, rebuild only affected files

**API**:
```python
def build_dependency_graph(
    working_directory: str,
    source_files: List[str]
) -> DependencyGraph:
    """Build dependency graph from source code"""

def find_affected_files(
    graph: DependencyGraph,
    changed_files: List[str]
) -> List[str]:
    """Find files affected by changes (transitive dependencies)"""

def preserve_unchanged_files(
    working_directory: str,
    previous_build_dir: str,
    unchanged_files: List[str]
) -> int:
    """Copy unchanged files from previous build"""

def create_incremental_build_plan(
    working_directory: str,
    change_report: ChangeReport
) -> BuildPlan:
    """Generate build plan with preservation + rebuild lists"""

@dataclass
class BuildPlan:
    files_to_preserve: List[str]  # Copy from previous build
    files_to_rebuild: List[str]   # Regenerate
    files_to_create: List[str]    # New files
    dependency_order: List[str]   # Build order
    estimated_time_saved_minutes: float
```

**Dependency Graph Structure**:
```json
{
  "nodes": {
    "tools/mcp_server.py": {
      "type": "python",
      "imports": ["tools.cache.scout_cache", "tools.config_manager"]
    },
    "tools/cache/scout_cache.py": {
      "type": "python",
      "imports": ["tools.cache"]
    }
  },
  "edges": [
    ["tools/mcp_server.py", "tools/cache/scout_cache.py"],
    ["tools/mcp_server.py", "tools/config_manager.py"]
  ]
}
```

### 4. Test Impact Analyzer (`tools/incremental/test_impact_analyzer.py`)

**Purpose**: Run only tests affected by code changes

**API**:
```python
def build_test_coverage_map(
    working_directory: str,
    test_framework: str = "pytest"
) -> TestCoverageMap:
    """Build mapping of tests → source files"""

def find_affected_tests(
    coverage_map: TestCoverageMap,
    changed_files: List[str]
) -> List[str]:
    """Find tests that need to run"""

def create_test_plan(
    working_directory: str,
    change_report: ChangeReport,
    coverage_map: Optional[TestCoverageMap] = None
) -> TestPlan:
    """Generate selective test execution plan"""

@dataclass
class TestPlan:
    tests_to_run: List[str]  # Affected tests
    tests_to_skip: List[str]  # Unaffected tests
    run_all: bool  # Fallback to running all
    reason: str  # Why this plan was chosen
    estimated_time_saved_minutes: float
```

**Coverage Map Structure**:
```json
{
  "framework": "pytest",
  "tests": {
    "tests/test_scout_cache.py::test_generate_key": {
      "covers": ["tools/cache/scout_cache.py"],
      "duration_seconds": 0.15
    },
    "tests/test_mcp_server.py::test_build": {
      "covers": ["tools/mcp_server.py", "tools/config_manager.py"],
      "duration_seconds": 2.3
    }
  },
  "total_duration_seconds": 45.2
}
```

### 5. Incremental Docs (`tools/incremental/incremental_docs.py`)

**Purpose**: Update only documentation affected by changes

**API**:
```python
def build_docs_manifest(
    working_directory: str
) -> DocsManifest:
    """Map documentation files to source files"""

def find_affected_docs(
    manifest: DocsManifest,
    changed_files: List[str]
) -> List[str]:
    """Find docs that need regeneration"""

def create_docs_plan(
    working_directory: str,
    change_report: ChangeReport
) -> DocsPlan:
    """Generate selective documentation update plan"""

@dataclass
class DocsPlan:
    docs_to_regenerate: List[str]  # Affected docs
    docs_to_preserve: List[str]    # Unchanged docs
    screenshots_to_preserve: List[str]  # Unchanged UI
    readme_sections_to_update: List[str]  # Specific sections
    regenerate_all: bool  # Fallback
    reason: str
```

**Docs Manifest Structure**:
```json
{
  "documentation": {
    "docs/ARCHITECTURE.md": {
      "sources": ["tools/mcp_server.py", "tools/orchestrator_prompt.txt"],
      "auto_generated": false
    },
    "docs/screenshots/hero.png": {
      "sources": ["src/main.js", "src/App.jsx"],
      "auto_generated": true,
      "ui_component": true
    }
  },
  "readme_sections": {
    "## Installation": {
      "sources": ["setup.py", "requirements.txt"]
    },
    "## API Reference": {
      "sources": ["tools/mcp_server.py"]
    }
  }
}
```

## File Structure

```
tools/
├── incremental/
│   ├── __init__.py
│   ├── global_scout_cache.py    (NEW - 200 lines)
│   ├── change_detector.py       (NEW - 250 lines)
│   ├── incremental_builder.py   (NEW - 300 lines)
│   ├── test_impact_analyzer.py  (NEW - 250 lines)
│   └── incremental_docs.py      (NEW - 200 lines)
├── cache/
│   ├── __init__.py              (UPDATED - add Phase 2 imports)
│   ├── scout_cache.py           (UNCHANGED - Phase 1)
│   ├── test_cache.py            (UNCHANGED - Phase 1)
│   └── cache_manager.py         (UPDATED - integrate Phase 2)
└── orchestrator_prompt.txt      (UPDATED - Phase 2 integration)

tests/
├── test_global_scout_cache.py   (NEW)
├── test_change_detector.py      (NEW)
├── test_incremental_builder.py  (NEW)
├── test_test_impact_analyzer.py (NEW)
├── test_incremental_docs.py     (NEW)
└── test_phase2_integration.py   (NEW)

~/.context-foundry/
└── global-cache/
    └── scout/                    (NEW - global cache)
        ├── cache-{hash1}.json
        └── cache-{hash2}.json

.context-foundry/
├── cache/                        (EXISTING - Phase 1)
├── last-build-snapshot.json      (NEW - Phase 2)
├── build-graph.json              (NEW - Phase 2)
├── test-coverage-map.json        (NEW - Phase 2)
└── docs-manifest.json            (NEW - Phase 2)
```

## Implementation Steps (Ordered)

1. **Create tools/incremental/ directory and __init__.py**
2. **Implement global_scout_cache.py**
   - Copy patterns from scout_cache.py
   - Change cache location to global
   - Add project_type + tech_stack to cache key
   - Implement similarity search
3. **Implement change_detector.py**
   - Git diff logic with subprocess
   - SHA256 hashing fallback
   - Snapshot save/load
   - Change detection and reporting
4. **Implement incremental_builder.py**
   - Dependency graph builder (static analysis)
   - Transitive dependency finder
   - File preservation logic
   - Build plan generator
5. **Implement test_impact_analyzer.py**
   - Coverage map parser (pytest + coverage.py)
   - Affected test finder
   - Test plan generator
6. **Implement incremental_docs.py**
   - Docs manifest builder
   - Affected docs finder
   - Docs plan generator
7. **Update tools/cache/__init__.py** to export Phase 2 modules
8. **Update tools/cache/cache_manager.py** to manage Phase 2 caches
9. **Update tools/orchestrator_prompt.txt** to use Phase 2 features
10. **Add configuration to .env.example**
11. **Write comprehensive tests**
12. **Update documentation**

## Testing Requirements

### Unit Tests
- Each module tested independently
- Mock file system operations
- Test both git and non-git scenarios
- Test graceful fallbacks

### Integration Tests
- Phase 1 + Phase 2 working together
- Full build with incremental features
- Verify caching across phases

### Performance Benchmarks
- Measure actual speedup on real projects
- Compare Phase 1 vs Phase 2 performance
- Validate 70-90% speedup claims

### Regression Tests
- Ensure Phase 1 functionality unchanged
- Backward compatibility tests
- Existing cache formats still valid

## Success Criteria

✅ Global Scout cache reduces Scout time by 80%+ for similar projects  
✅ Change detection works with and without git  
✅ Incremental Builder preserves 70%+ files on small changes  
✅ Test impact analysis runs 60% fewer tests  
✅ Docs updates skip 90%+ unchanged content  
✅ All existing tests pass  
✅ New tests achieve 90%+ coverage  
✅ Performance benchmarks validate claims  
✅ No breaking changes to Phase 1
