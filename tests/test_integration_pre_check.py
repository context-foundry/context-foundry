"""
Comprehensive tests for tools/back_pressure/integration_pre_check.py

This module tests the fast pre-check validation system (Phase 3.5 back pressure)
that catches syntax errors, import issues, and missing files before expensive
test suite execution.

Test coverage: 35-40 tests for 90%+ code coverage
Pytest markers: unit, integration, tier1
"""

import pytest
import json
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.back_pressure.integration_pre_check import (
    integration_pre_check,
    detect_project_language,
    run_syntax_check,
    check_imports,
    check_required_files
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def tmp_python_project(tmp_path):
    """Create temporary Python project with valid syntax"""
    (tmp_path / "main.py").write_text("print('hello world')")
    (tmp_path / "utils.py").write_text("def helper():\n    return 42")
    (tmp_path / "requirements.txt").write_text("pytest>=7.0.0")
    return tmp_path


@pytest.fixture
def tmp_invalid_python_project(tmp_path):
    """Create Python project with syntax errors"""
    (tmp_path / "bad.py").write_text("def broken(\nprint('unclosed parenthesis')")
    (tmp_path / "requirements.txt").write_text("pytest")
    return tmp_path


@pytest.fixture
def tmp_typescript_project(tmp_path):
    """Create temporary TypeScript project"""
    package_json = {
        "name": "test-ts",
        "dependencies": {},
        "devDependencies": {"typescript": "^5.0.0"}
    }
    (tmp_path / "package.json").write_text(json.dumps(package_json))
    (tmp_path / "tsconfig.json").write_text('{"compilerOptions": {}}')
    (tmp_path / "index.ts").write_text("const x: number = 42;")
    return tmp_path


@pytest.fixture
def tmp_javascript_project(tmp_path):
    """Create temporary JavaScript project (no TypeScript)"""
    package_json = {"name": "test-js", "dependencies": {}}
    (tmp_path / "package.json").write_text(json.dumps(package_json))
    (tmp_path / "index.js").write_text("console.log('hello');")
    return tmp_path


@pytest.fixture
def tmp_rust_project(tmp_path):
    """Create temporary Rust project"""
    (tmp_path / "Cargo.toml").write_text('[package]\nname = "test"\nversion = "0.1.0"')
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "main.rs").write_text('fn main() { println!("hello"); }')
    return tmp_path


@pytest.fixture
def tmp_go_project(tmp_path):
    """Create temporary Go project"""
    (tmp_path / "go.mod").write_text('module test\n\ngo 1.20')
    (tmp_path / "main.go").write_text('package main\n\nfunc main() {}')
    return tmp_path


# ============================================================================
# LANGUAGE DETECTION TESTS (8 tests)
# ============================================================================

@pytest.mark.unit
@pytest.mark.tier1
def test_detect_language_python_requirements(tmp_python_project):
    """Test Python detection via requirements.txt"""
    lang = detect_project_language(str(tmp_python_project))
    assert lang == 'python'


@pytest.mark.unit
@pytest.mark.tier1
def test_detect_language_python_pyproject(tmp_path):
    """Test Python detection via pyproject.toml"""
    (tmp_path / "pyproject.toml").write_text('[tool.poetry]\nname = "test"')
    lang = detect_project_language(str(tmp_path))
    assert lang == 'python'


@pytest.mark.unit
@pytest.mark.tier1
def test_detect_language_python_py_files(tmp_path):
    """Test Python detection via .py files only"""
    (tmp_path / "script.py").write_text("print('test')")
    lang = detect_project_language(str(tmp_path))
    assert lang == 'python'


@pytest.mark.unit
@pytest.mark.tier1
def test_detect_language_typescript(tmp_typescript_project):
    """Test TypeScript detection"""
    lang = detect_project_language(str(tmp_typescript_project))
    assert lang == 'typescript'


@pytest.mark.unit
@pytest.mark.tier1
def test_detect_language_javascript(tmp_javascript_project):
    """Test JavaScript detection"""
    lang = detect_project_language(str(tmp_javascript_project))
    assert lang == 'javascript'


@pytest.mark.unit
@pytest.mark.tier1
def test_detect_language_rust(tmp_rust_project):
    """Test Rust detection"""
    lang = detect_project_language(str(tmp_rust_project))
    assert lang == 'rust'


@pytest.mark.unit
@pytest.mark.tier1
def test_detect_language_go(tmp_go_project):
    """Test Go detection"""
    lang = detect_project_language(str(tmp_go_project))
    assert lang == 'go'


@pytest.mark.unit
@pytest.mark.tier1
def test_detect_language_unknown(tmp_path):
    """Test unknown language detection"""
    (tmp_path / "README.md").write_text("# Test")
    lang = detect_project_language(str(tmp_path))
    assert lang == 'unknown'


# ============================================================================
# PYTHON SYNTAX CHECKING TESTS (8 tests)
# ============================================================================

@pytest.mark.unit
@pytest.mark.tier1
def test_syntax_check_python_valid(tmp_python_project):
    """Test Python syntax check with valid files"""
    result = run_syntax_check(str(tmp_python_project), 'python')
    assert result['success'] is True
    assert result['errors'] == []
    assert result['skipped'] is False


@pytest.mark.unit
@pytest.mark.tier1
def test_syntax_check_python_invalid(tmp_invalid_python_project):
    """Test Python syntax check with invalid syntax"""
    result = run_syntax_check(str(tmp_invalid_python_project), 'python')
    assert result['success'] is False
    assert len(result['errors']) > 0
    assert 'bad.py' in result['errors'][0]['file']


@pytest.mark.unit
@pytest.mark.tier1
def test_syntax_check_python_multiple_files_one_error(tmp_path):
    """Test multiple Python files with one error"""
    (tmp_path / "good.py").write_text("x = 1")
    (tmp_path / "bad.py").write_text("def f(\npass")
    (tmp_path / "also_good.py").write_text("y = 2")
    
    result = run_syntax_check(str(tmp_path), 'python')
    assert result['success'] is False
    assert len(result['errors']) == 1
    assert 'bad.py' in result['errors'][0]['file']


@pytest.mark.unit
@pytest.mark.tier1
@patch('subprocess.run')
def test_syntax_check_python_timeout(mock_run, tmp_python_project):
    """Test Python syntax check timeout handling"""
    mock_run.side_effect = subprocess.TimeoutExpired('python', 10)
    
    result = run_syntax_check(str(tmp_python_project), 'python')
    assert result['success'] is False
    assert 'timed out' in result['errors'][0]['error'].lower()


@pytest.mark.unit
@pytest.mark.tier1
def test_syntax_check_python_excludes_venv(tmp_path):
    """Test that venv directories are excluded"""
    (tmp_path / "main.py").write_text("x = 1")
    venv_dir = tmp_path / "venv" / "lib"
    venv_dir.mkdir(parents=True)
    (venv_dir / "bad.py").write_text("syntax error here")
    
    result = run_syntax_check(str(tmp_path), 'python')
    # Should only check main.py, not venv/lib/bad.py
    assert result['success'] is True


@pytest.mark.unit
@pytest.mark.tier1
def test_syntax_check_python_empty_project(tmp_path):
    """Test Python project with no .py files"""
    (tmp_path / "README.md").write_text("# Empty")
    
    result = run_syntax_check(str(tmp_path), 'python')
    # No Python files = success (nothing to check)
    assert result['success'] is True
    assert result['errors'] == []


@pytest.mark.unit
@pytest.mark.tier1
@patch('subprocess.run')
def test_syntax_check_python_subprocess_exception(mock_run, tmp_python_project):
    """Test subprocess exception handling"""
    mock_run.side_effect = Exception("Unexpected error")
    
    result = run_syntax_check(str(tmp_python_project), 'python')
    assert result['success'] is False
    assert 'failed' in result['errors'][0]['error'].lower()


@pytest.mark.unit
@pytest.mark.tier1
def test_syntax_check_python_excludes_pycache(tmp_path):
    """Test that __pycache__ directories are excluded"""
    (tmp_path / "main.py").write_text("x = 1")
    cache_dir = tmp_path / "__pycache__"
    cache_dir.mkdir()
    (cache_dir / "bad.pyc").write_text("compiled python")
    
    result = run_syntax_check(str(tmp_path), 'python')
    assert result['success'] is True


# ============================================================================
# TYPESCRIPT/JAVASCRIPT CHECKING TESTS (6 tests)
# ============================================================================

@pytest.mark.unit
@pytest.mark.tier1
@patch('subprocess.run')
def test_syntax_check_typescript_valid(mock_run, tmp_typescript_project):
    """Test TypeScript syntax check (tsc available)"""
    mock_result = Mock()
    mock_result.returncode = 0
    mock_result.stdout = ""
    mock_run.return_value = mock_result
    
    result = run_syntax_check(str(tmp_typescript_project), 'typescript')
    assert result['success'] is True
    assert result['skipped'] is False


@pytest.mark.unit
@pytest.mark.tier1
@patch('subprocess.run')
def test_syntax_check_typescript_invalid(mock_run, tmp_typescript_project):
    """Test TypeScript syntax check with errors"""
    mock_result = Mock()
    mock_result.returncode = 1
    mock_result.stdout = "index.ts(5,10): error TS2322: Type 'string' is not assignable to type 'number'"
    mock_run.return_value = mock_result
    
    result = run_syntax_check(str(tmp_typescript_project), 'typescript')
    assert result['success'] is False
    assert len(result['errors']) > 0


@pytest.mark.unit
@pytest.mark.tier1
@patch('subprocess.run')
def test_syntax_check_typescript_not_available(mock_run, tmp_typescript_project):
    """Test TypeScript graceful skip when tsc not available"""
    mock_run.side_effect = FileNotFoundError("tsc not found")
    
    result = run_syntax_check(str(tmp_typescript_project), 'typescript')
    assert result['success'] is True
    assert result['skipped'] is True
    assert 'not available' in result.get('skip_reason', '')


@pytest.mark.unit
@pytest.mark.tier1
@patch('subprocess.run')
def test_syntax_check_typescript_timeout(mock_run, tmp_typescript_project):
    """Test TypeScript timeout handling"""
    mock_run.side_effect = subprocess.TimeoutExpired('tsc', 30)
    
    result = run_syntax_check(str(tmp_typescript_project), 'typescript')
    assert result['success'] is True
    assert result['skipped'] is True


@pytest.mark.unit
@pytest.mark.tier1
def test_syntax_check_javascript_skipped(tmp_javascript_project):
    """Test JavaScript project (no TypeScript check)"""
    result = run_syntax_check(str(tmp_javascript_project), 'javascript')
    # JavaScript has no syntax check implemented
    assert result['success'] is True


@pytest.mark.unit
@pytest.mark.tier1
@patch('subprocess.run')
def test_syntax_check_typescript_parse_errors(mock_run, tmp_typescript_project):
    """Test TypeScript error parsing"""
    mock_result = Mock()
    mock_result.returncode = 1
    mock_result.stdout = "index.ts(1,1): error TS1005: ';' expected\nindex.ts(2,3): error TS2304: Cannot find name 'foo'"
    mock_run.return_value = mock_result
    
    result = run_syntax_check(str(tmp_typescript_project), 'typescript')
    assert result['success'] is False
    assert len(result['errors']) == 2


# ============================================================================
# RUST/GO CHECKING TESTS (4 tests)
# ============================================================================

@pytest.mark.unit
@pytest.mark.tier1
@patch('subprocess.run')
def test_syntax_check_rust_success(mock_run, tmp_rust_project):
    """Test Rust cargo check success"""
    mock_result = Mock()
    mock_result.returncode = 0
    mock_run.return_value = mock_result
    
    result = run_syntax_check(str(tmp_rust_project), 'rust')
    assert result['success'] is True
    assert result['skipped'] is False


@pytest.mark.unit
@pytest.mark.tier1
@patch('subprocess.run')
def test_syntax_check_rust_failure(mock_run, tmp_rust_project):
    """Test Rust cargo check failure"""
    mock_result = Mock()
    mock_result.returncode = 1
    mock_result.stderr = "error: expected `;`, found `}`"
    mock_run.return_value = mock_result
    
    result = run_syntax_check(str(tmp_rust_project), 'rust')
    assert result['success'] is False
    assert len(result['errors']) > 0


@pytest.mark.unit
@pytest.mark.tier1
@patch('subprocess.run')
def test_syntax_check_go_success(mock_run, tmp_go_project):
    """Test Go build success"""
    mock_result = Mock()
    mock_result.returncode = 0
    mock_run.return_value = mock_result
    
    result = run_syntax_check(str(tmp_go_project), 'go')
    assert result['success'] is True


@pytest.mark.unit
@pytest.mark.tier1
@patch('subprocess.run')
def test_syntax_check_go_failure(mock_run, tmp_go_project):
    """Test Go build failure"""
    mock_result = Mock()
    mock_result.returncode = 1
    mock_result.stderr = "syntax error: unexpected newline"
    mock_run.return_value = mock_result
    
    result = run_syntax_check(str(tmp_go_project), 'go')
    assert result['success'] is False


# ============================================================================
# IMPORT CHECKING TESTS (4 tests)
# ============================================================================

@pytest.mark.unit
@pytest.mark.tier1
def test_check_imports_python_relative(tmp_path):
    """Test Python relative imports detection"""
    (tmp_path / "module.py").write_text("from .submodule import func\nfrom ..parent import other")
    
    result = check_imports(str(tmp_path), 'python')
    # Basic implementation - should succeed
    assert result['success'] is True


@pytest.mark.unit
@pytest.mark.tier1
def test_check_imports_python_basic(tmp_python_project):
    """Test basic Python import checking"""
    result = check_imports(str(tmp_python_project), 'python')
    assert result['success'] is True
    assert 'duration' in result


@pytest.mark.unit
@pytest.mark.tier1
def test_check_imports_typescript_skipped(tmp_typescript_project):
    """Test TypeScript imports (currently skipped)"""
    result = check_imports(str(tmp_typescript_project), 'typescript')
    # TypeScript import checking not implemented yet
    assert result['success'] is True


@pytest.mark.unit
@pytest.mark.tier1
def test_check_imports_duration(tmp_python_project):
    """Test import check completes quickly"""
    result = check_imports(str(tmp_python_project), 'python')
    assert result['duration'] < 1.0  # Should be very fast


# ============================================================================
# REQUIRED FILES CHECKING TESTS (5 tests)
# ============================================================================

@pytest.mark.unit
@pytest.mark.tier1
def test_required_files_python_missing(tmp_path):
    """Test Python project missing .py files"""
    (tmp_path / "README.md").write_text("# Project")
    
    result = check_required_files(str(tmp_path), 'python')
    assert result['success'] is False
    assert 'No Python source files' in result['errors'][0]['error']


@pytest.mark.unit
@pytest.mark.tier1
def test_required_files_typescript_missing_config(tmp_path):
    """Test TypeScript missing tsconfig.json"""
    package_json = {"name": "test", "devDependencies": {"typescript": "^5.0.0"}}
    (tmp_path / "package.json").write_text(json.dumps(package_json))
    
    result = check_required_files(str(tmp_path), 'typescript')
    assert result['success'] is False
    assert 'tsconfig.json' in result['errors'][0]['error']


@pytest.mark.unit
@pytest.mark.tier1
def test_required_files_rust_missing_cargo(tmp_path):
    """Test Rust missing Cargo.toml"""
    (tmp_path / "main.rs").write_text("fn main() {}")
    
    result = check_required_files(str(tmp_path), 'rust')
    assert result['success'] is False
    assert 'Cargo.toml' in result['errors'][0]['error']


@pytest.mark.unit
@pytest.mark.tier1
def test_required_files_go_missing_gomod(tmp_path):
    """Test Go missing go.mod"""
    (tmp_path / "main.go").write_text("package main")
    
    result = check_required_files(str(tmp_path), 'go')
    assert result['success'] is False
    assert 'go.mod' in result['errors'][0]['error']


@pytest.mark.unit
@pytest.mark.tier1
def test_required_files_valid_projects(tmp_python_project, tmp_typescript_project):
    """Test valid projects pass required files check"""
    python_result = check_required_files(str(tmp_python_project), 'python')
    assert python_result['success'] is True
    
    ts_result = check_required_files(str(tmp_typescript_project), 'typescript')
    assert ts_result['success'] is True


# ============================================================================
# CLI INTEGRATION TESTS (3 tests)
# ============================================================================

@pytest.mark.integration
@pytest.mark.tier1
def test_cli_valid_project(tmp_python_project):
    """Test CLI with valid project"""
    import subprocess
    result = subprocess.run(
        ['python3', '-m', 'tools.back_pressure.integration_pre_check', str(tmp_python_project)],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).parent.parent)
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output['success'] is True


@pytest.mark.integration
@pytest.mark.tier1
def test_cli_invalid_project(tmp_invalid_python_project):
    """Test CLI with invalid project"""
    import subprocess
    result = subprocess.run(
        ['python3', '-m', 'tools.back_pressure.integration_pre_check', str(tmp_invalid_python_project)],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).parent.parent)
    )
    assert result.returncode == 1
    output = json.loads(result.stdout)
    assert output['success'] is False


@pytest.mark.integration
@pytest.mark.tier1
def test_cli_exit_codes(tmp_python_project, tmp_invalid_python_project):
    """Test CLI exit codes"""
    import subprocess
    
    # Valid project: exit 0
    result = subprocess.run(
        ['python3', '-m', 'tools.back_pressure.integration_pre_check', str(tmp_python_project)],
        capture_output=True,
        cwd=str(Path(__file__).parent.parent)
    )
    assert result.returncode == 0
    
    # Invalid project: exit 1
    result = subprocess.run(
        ['python3', '-m', 'tools.back_pressure.integration_pre_check', str(tmp_invalid_python_project)],
        capture_output=True,
        cwd=str(Path(__file__).parent.parent)
    )
    assert result.returncode == 1


# ============================================================================
# INTEGRATION PRE-CHECK MAIN FUNCTION TESTS (5 tests)
# ============================================================================

@pytest.mark.integration
@pytest.mark.tier1
def test_integration_pre_check_python_success(tmp_python_project):
    """Test full integration pre-check with Python project"""
    result = integration_pre_check(str(tmp_python_project))
    
    assert result['success'] is True
    assert result['language'] == 'python'
    assert result['total_duration'] > 0
    assert len(result['checks']) > 0
    assert all(check['passed'] for check in result['checks'])


@pytest.mark.integration
@pytest.mark.tier1
def test_integration_pre_check_python_failure(tmp_invalid_python_project):
    """Test integration pre-check with failing Python project"""
    result = integration_pre_check(str(tmp_invalid_python_project))
    
    assert result['success'] is False
    assert result['language'] == 'python'
    # At least syntax check should fail
    failed_checks = [c for c in result['checks'] if not c['passed']]
    assert len(failed_checks) > 0


@pytest.mark.integration
@pytest.mark.tier1
@patch('subprocess.run')
def test_integration_pre_check_typescript(mock_run, tmp_typescript_project):
    """Test integration pre-check with TypeScript project"""
    mock_result = Mock()
    mock_result.returncode = 0
    mock_result.stdout = ""
    mock_run.return_value = mock_result
    
    result = integration_pre_check(str(tmp_typescript_project))
    
    assert result['language'] == 'typescript'
    # Should include syntax, import, and required files checks
    assert len(result['checks']) >= 3


@pytest.mark.integration
@pytest.mark.tier1
def test_integration_pre_check_performance(tmp_python_project):
    """Test that pre-check is fast (< 5 seconds for small project)"""
    result = integration_pre_check(str(tmp_python_project))
    assert result['total_duration'] < 5.0


@pytest.mark.integration
@pytest.mark.tier1
def test_integration_pre_check_all_checks_recorded(tmp_python_project):
    """Test that all check results are recorded"""
    result = integration_pre_check(str(tmp_python_project))
    
    # Should have at least: syntax, imports, required files
    assert len(result['checks']) >= 3
    
    for check in result['checks']:
        assert 'name' in check
        assert 'passed' in check
        assert 'duration' in check
        assert 'errors' in check


# ============================================================================
# EDGE CASE TESTS (2 tests)
# ============================================================================

@pytest.mark.unit
@pytest.mark.tier1
def test_large_project_performance(tmp_path):
    """Test performance with 100+ files"""
    # Create 100 Python files
    for i in range(100):
        (tmp_path / f"file_{i}.py").write_text(f"x{i} = {i}")
    
    result = run_syntax_check(str(tmp_path), 'python')
    # Should still complete reasonably fast
    assert result['duration'] < 10.0
    assert result['success'] is True


@pytest.mark.unit
@pytest.mark.tier1
def test_unicode_filenames(tmp_path):
    """Test handling of Unicode filenames"""
    (tmp_path / "тест.py").write_text("print('unicode')")
    (tmp_path / "日本語.py").write_text("x = 1")
    
    result = run_syntax_check(str(tmp_path), 'python')
    # Should handle Unicode filenames gracefully
    assert result['success'] is True
