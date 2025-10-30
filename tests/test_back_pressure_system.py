"""
Comprehensive test suite for the Back Pressure System

Tests all validators: tech stack, architecture, and integration pre-checks.
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import subprocess

# Import validators
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.back_pressure.validate_tech_stack import (
    validate_tech_stack,
    extract_tech_stack,
    check_language_available,
    parse_version,
    version_compare
)

from tools.back_pressure.validate_architecture import (
    validate_architecture,
    check_test_strategy_exists,
    check_file_structure_specified,
    find_duplicate_file_paths,
    extract_file_paths
)

from tools.back_pressure.integration_pre_check import (
    integration_pre_check,
    detect_project_language,
    run_syntax_check
)

from tools.back_pressure.back_pressure_config import (
    get_back_pressure_config,
    detect_language,
    get_language_natural_pressure,
    should_enable_check
)


# ============================================================================
# TECH STACK VALIDATOR TESTS
# ============================================================================

class TestValidateTechStack:
    """Tests for validate_tech_stack.py"""
    
    def test_validate_tech_stack_file_not_found(self):
        """Should return error when scout report doesn't exist"""
        result = validate_tech_stack('/nonexistent/scout-report.md')
        
        assert result['success'] is False
        assert len(result['errors']) == 1
        assert 'not found' in result['errors'][0]['message'].lower()
    
    def test_validate_tech_stack_no_tech_section(self, tmp_path):
        """Should skip validation when no tech stack section exists"""
        scout_report = tmp_path / 'scout-report.md'
        scout_report.write_text('# Scout Report\n\nNo tech stack here')
        
        result = validate_tech_stack(str(scout_report))
        
        assert result['success'] is True
        assert len(result['warnings']) == 1
        assert 'no technology stack' in result['warnings'][0]['message'].lower()
    
    def test_extract_tech_stack_with_languages(self):
        """Should extract language and version from tech stack section"""
        content = """
## Technology Stack

- Language: Python 3.11+
- Framework: FastAPI
- Database: PostgreSQL 15
"""
        tech_stack = extract_tech_stack(content)
        
        assert len(tech_stack) >= 1
        python_tech = [t for t in tech_stack if t['name'] == 'Python'][0]
        assert python_tech['type'] == 'language'
        assert python_tech['version'] == '3.11'
    
    def test_extract_tech_stack_with_bold_labels(self):
        """Should handle markdown bold in labels"""
        content = """
## Technology Stack

- **Language**: Node 18+
- **Framework**: Express
"""
        tech_stack = extract_tech_stack(content)
        
        assert len(tech_stack) >= 1
        node_tech = [t for t in tech_stack if 'Node' in t['name']]
        assert len(node_tech) > 0
    
    @patch('subprocess.run')
    def test_check_language_available_python_success(self, mock_run):
        """Should pass when Python version is sufficient"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='Python 3.11.4',
            stderr=''
        )
        
        result = check_language_available('Python', '3.10')
        
        assert result['status'] == 'success'
        assert '3.11.4' in result['message']
    
    @patch('subprocess.run')
    def test_check_language_available_python_too_old(self, mock_run):
        """Should fail when Python version is too old"""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='Python 3.9.7',
            stderr=''
        )
        
        result = check_language_available('Python', '3.10')
        
        assert result['status'] == 'error'
        assert 'too old' in result['message'].lower()
        assert 'fix' in result
    
    @patch('subprocess.run')
    def test_check_language_available_not_installed(self, mock_run):
        """Should fail when language not installed"""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout='',
            stderr='command not found'
        )
        
        result = check_language_available('Rust', '1.70')
        
        assert result['status'] == 'error'
        assert 'not found' in result['message'].lower()
    
    def test_parse_version_python(self):
        """Should parse Python version string"""
        assert parse_version('Python 3.11.4') == '3.11.4'
        assert parse_version('Python 3.10.0') == '3.10.0'
    
    def test_parse_version_node(self):
        """Should parse Node version string"""
        assert parse_version('v18.16.0') == '18.16.0'
        assert parse_version('node v20.0.0') == '20.0.0'
    
    def test_version_compare_equal(self):
        """Should return 0 for equal versions"""
        assert version_compare('3.11.0', '3.11.0') == 0
        assert version_compare('1.0', '1.0.0') == 0
    
    def test_version_compare_greater(self):
        """Should return 1 when v1 > v2"""
        assert version_compare('3.11.0', '3.10.0') == 1
        assert version_compare('2.0.0', '1.99.99') == 1
    
    def test_version_compare_less(self):
        """Should return -1 when v1 < v2"""
        assert version_compare('3.9.0', '3.10.0') == -1
        assert version_compare('1.0.0', '2.0.0') == -1


# ============================================================================
# ARCHITECTURE VALIDATOR TESTS
# ============================================================================

class TestValidateArchitecture:
    """Tests for validate_architecture.py"""
    
    def test_validate_architecture_file_not_found(self):
        """Should return error when architecture file doesn't exist"""
        result = validate_architecture('/nonexistent/architecture.md')
        
        assert result['valid'] is False
        assert len(result['issues']) == 1
        assert 'not found' in result['issues'][0]['message'].lower()
    
    def test_validate_architecture_missing_test_strategy(self, tmp_path):
        """Should fail when no test strategy specified"""
        arch_file = tmp_path / 'architecture.md'
        arch_file.write_text("""
# Architecture

## File Structure
- src/main.py
- src/utils.py

## Implementation
Build the thing.
""")
        
        result = validate_architecture(str(arch_file))
        
        assert result['valid'] is False
        test_issues = [i for i in result['issues'] if 'test' in i['message'].lower()]
        assert len(test_issues) > 0
    
    def test_validate_architecture_valid(self, tmp_path):
        """Should pass when architecture is complete"""
        arch_file = tmp_path / 'architecture.md'
        arch_file.write_text("""
# Architecture

## File Structure
- src/main.py
- src/utils.py
- tests/test_main.py

## Testing Requirements
- Framework: pytest
- Coverage: 80%

## Implementation Steps
1. Create main.py
2. Create tests
""")
        
        result = validate_architecture(str(arch_file))
        
        # Should have no errors (warnings are OK)
        errors = [i for i in result['issues'] if i['severity'] == 'error']
        assert len(errors) == 0
        assert result['valid'] is True
    
    def test_check_test_strategy_exists_with_pytest(self):
        """Should detect pytest mention"""
        content = "We will use pytest for testing"
        assert check_test_strategy_exists(content) is True
    
    def test_check_test_strategy_exists_with_heading(self):
        """Should detect test heading"""
        content = "## Testing Requirements\nRun tests with npm test"
        assert check_test_strategy_exists(content) is True
    
    def test_check_test_strategy_exists_none(self):
        """Should return False when no test mentions"""
        content = "## Implementation\nBuild stuff"
        assert check_test_strategy_exists(content) is False
    
    def test_check_file_structure_specified_with_heading(self):
        """Should detect file structure heading"""
        content = "## File Structure\n- src/main.py"
        assert check_file_structure_specified(content) is True
    
    def test_check_file_structure_specified_with_paths(self):
        """Should detect code block with paths"""
        content = """
```
src/
├── main.py
└── utils.py
```
"""
        assert check_file_structure_specified(content) is True
    
    def test_extract_file_paths(self):
        """Should extract file paths from architecture"""
        content = """
## File Structure
```
src/
├── main.py
├── utils.py
tests/
└── test_main.py
```
"""
        paths = extract_file_paths(content)
        
        assert 'main.py' in paths
        assert 'utils.py' in paths
        assert 'test_main.py' in paths
    
    def test_find_duplicate_file_paths(self):
        """Should detect duplicate file paths"""
        content = """
- src/main.py
- src/utils.py
- src/main.py
"""
        duplicates = find_duplicate_file_paths(content)

        assert 'src/main.py' in duplicates


# ============================================================================
# INTEGRATION PRE-CHECK TESTS
# ============================================================================

class TestIntegrationPreCheck:
    """Tests for integration_pre_check.py"""
    
    def test_detect_project_language_python(self, tmp_path):
        """Should detect Python project from requirements.txt"""
        (tmp_path / 'requirements.txt').write_text('pytest==7.0.0')
        
        language = detect_project_language(str(tmp_path))
        
        assert language == 'python'
    
    def test_detect_project_language_typescript(self, tmp_path):
        """Should detect TypeScript from package.json"""
        package_json = {
            "name": "test",
            "devDependencies": {"typescript": "^5.0.0"}
        }
        (tmp_path / 'package.json').write_text(json.dumps(package_json))
        
        language = detect_project_language(str(tmp_path))
        
        assert language == 'typescript'
    
    def test_detect_project_language_rust(self, tmp_path):
        """Should detect Rust from Cargo.toml"""
        (tmp_path / 'Cargo.toml').write_text('[package]\nname = "test"')
        
        language = detect_project_language(str(tmp_path))
        
        assert language == 'rust'
    
    def test_detect_project_language_from_files(self, tmp_path):
        """Should detect language from source files"""
        (tmp_path / 'main.py').write_text('print("hello")')
        
        language = detect_project_language(str(tmp_path))
        
        assert language == 'python'
    
    def test_run_syntax_check_python_valid(self, tmp_path):
        """Should pass for valid Python syntax"""
        py_file = tmp_path / 'main.py'
        py_file.write_text('def hello():\n    print("world")\n')
        
        result = run_syntax_check(str(tmp_path), 'python')
        
        assert result['success'] is True
        assert len(result['errors']) == 0
    
    def test_run_syntax_check_python_invalid(self, tmp_path):
        """Should fail for invalid Python syntax"""
        py_file = tmp_path / 'main.py'
        py_file.write_text('def hello(\n    pass')  # Syntax error
        
        result = run_syntax_check(str(tmp_path), 'python')
        
        assert result['success'] is False
        assert len(result['errors']) > 0
    
    def test_run_syntax_check_unknown_language(self, tmp_path):
        """Should skip check for unknown language"""
        result = run_syntax_check(str(tmp_path), 'unknown')
        
        assert result['success'] is True
        assert result['skipped'] is True


# ============================================================================
# BACK PRESSURE CONFIG TESTS
# ============================================================================

class TestBackPressureConfig:
    """Tests for back_pressure_config.py"""
    
    def test_detect_language_python(self, tmp_path):
        """Should detect Python from requirements.txt"""
        (tmp_path / 'requirements.txt').write_text('fastapi')
        
        language = detect_language(str(tmp_path))
        
        assert language == 'python'
    
    def test_detect_language_typescript(self, tmp_path):
        """Should detect TypeScript from package.json"""
        package_json = {"devDependencies": {"typescript": "5.0.0"}}
        (tmp_path / 'package.json').write_text(json.dumps(package_json))
        
        language = detect_language(str(tmp_path))
        
        assert language == 'typescript'
    
    def test_get_back_pressure_config_python(self, tmp_path):
        """Should return Python config for Python project"""
        (tmp_path / 'requirements.txt').write_text('pytest')
        
        config = get_back_pressure_config(str(tmp_path))
        
        assert config['detected_language'] == 'python'
        assert config['natural_pressure'] == 'low'
        assert config['checks']['syntax']['enabled'] is True
    
    def test_get_back_pressure_config_rust(self, tmp_path):
        """Should return Rust config for Rust project"""
        (tmp_path / 'Cargo.toml').write_text('[package]\nname="test"')
        
        config = get_back_pressure_config(str(tmp_path))
        
        assert config['detected_language'] == 'rust'
        assert config['natural_pressure'] == 'high'
    
    def test_get_language_natural_pressure(self):
        """Should return correct natural pressure for languages"""
        assert get_language_natural_pressure('python') == 'low'
        assert get_language_natural_pressure('typescript') == 'medium'
        assert get_language_natural_pressure('rust') == 'high'
    
    def test_should_enable_check_python_syntax(self):
        """Should enable syntax check for Python"""
        assert should_enable_check('python', 'syntax') is True
    
    def test_should_enable_check_rust_type(self):
        """Should not enable type check for Rust (included in cargo check)"""
        assert should_enable_check('rust', 'type') is False


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestIntegration:
    """End-to-end integration tests"""
    
    @patch('subprocess.run')
    def test_full_validation_flow_python_project(self, mock_run, tmp_path):
        """Should validate a complete Python project"""
        # Mock Python version check
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='Python 3.11.4',
            stderr=''
        )

        # Create scout report
        scout_report = tmp_path / 'scout-report.md'
        scout_report.write_text("""
# Scout Report

## Technology Stack

- Language: Python 3.10+
- Framework: FastAPI
- Testing: pytest
""")
        
        # Create architecture
        arch = tmp_path / 'architecture.md'
        arch.write_text("""
# Architecture

## File Structure
- src/main.py
- tests/test_main.py

## Testing Requirements
- Framework: pytest
- Coverage: 80%

## Implementation Steps
1. Create main.py
2. Write tests
""")
        
        # Create valid Python file
        src_dir = tmp_path / 'src'
        src_dir.mkdir()
        (src_dir / 'main.py').write_text('def hello():\n    return "world"\n')
        
        # Run validations
        tech_result = validate_tech_stack(str(scout_report))
        arch_result = validate_architecture(str(arch))
        pre_check_result = integration_pre_check(str(tmp_path))
        
        # All should pass (or skip gracefully)
        assert tech_result['success'] is True or len(tech_result['warnings']) > 0
        assert arch_result['valid'] is True
        assert pre_check_result['success'] is True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
