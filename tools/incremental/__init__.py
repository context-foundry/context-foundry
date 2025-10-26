"""
Incremental Build System - Phase 2

Advanced caching and change detection for 70-90% faster rebuilds.

Modules:
- global_scout_cache: Cross-project Scout cache
- change_detector: File-level change detection
- incremental_builder: Smart file preservation
- test_impact_analyzer: Selective test execution
- incremental_docs: Selective documentation updates
"""

from .global_scout_cache import (
    get_global_cache_dir,
    generate_global_scout_key,
    get_cached_scout_report_global,
    save_scout_report_to_global_cache,
    find_similar_cached_reports,
    clear_global_scout_cache,
    get_global_scout_cache_stats
)

from .change_detector import (
    ChangeReport,
    capture_build_snapshot,
    detect_changes,
    get_last_build_snapshot_path
)

from .incremental_builder import (
    BuildPlan,
    DependencyGraph,
    build_dependency_graph,
    find_affected_files,
    create_incremental_build_plan,
    preserve_unchanged_files
)

from .test_impact_analyzer import (
    TestPlan,
    TestCoverageMap,
    build_test_coverage_map,
    find_affected_tests,
    create_test_plan
)

from .incremental_docs import (
    DocsPlan,
    DocsManifest,
    build_docs_manifest,
    find_affected_docs,
    create_docs_plan
)

__all__ = [
    # Global Scout Cache
    'get_global_cache_dir',
    'generate_global_scout_key',
    'get_cached_scout_report_global',
    'save_scout_report_to_global_cache',
    'find_similar_cached_reports',
    'clear_global_scout_cache',
    'get_global_scout_cache_stats',

    # Change Detector
    'ChangeReport',
    'capture_build_snapshot',
    'detect_changes',
    'get_last_build_snapshot_path',

    # Incremental Builder
    'BuildPlan',
    'DependencyGraph',
    'build_dependency_graph',
    'find_affected_files',
    'create_incremental_build_plan',
    'preserve_unchanged_files',

    # Test Impact Analyzer
    'TestPlan',
    'TestCoverageMap',
    'build_test_coverage_map',
    'find_affected_tests',
    'create_test_plan',

    # Incremental Docs
    'DocsPlan',
    'DocsManifest',
    'build_docs_manifest',
    'find_affected_docs',
    'create_docs_plan',
]
