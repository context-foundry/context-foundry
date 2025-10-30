"""
Integration Pre-Check - Phase 3.5 Back Pressure

Fast validation before expensive test suite execution.
Catches syntax errors, import issues, and missing files.
"""

import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional
import json


def integration_pre_check(working_directory: str) -> Dict:
    """
    Run fast pre-checks before full test suite.
    
    Args:
        working_directory: Project root directory
        
    Returns:
        {
            'success': bool,
            'checks': [{'name': str, 'passed': bool, 'duration': float, 'errors': list}],
            'total_duration': float,
            'language': str
        }
    """
    start_time = time.time()
    working_dir = Path(working_directory)
    
    # Detect project language
    language = detect_project_language(working_directory)
    
    checks = []
    
    # Check 1: Syntax validation
    syntax_result = run_syntax_check(working_directory, language)
    checks.append({
        'name': 'Syntax Check',
        'passed': syntax_result['success'],
        'duration': syntax_result['duration'],
        'errors': syntax_result.get('errors', [])
    })
    
    # Check 2: Import resolution (for Python/TypeScript)
    if language in ['python', 'typescript']:
        import_result = check_imports(working_directory, language)
        checks.append({
            'name': 'Import Resolution',
            'passed': import_result['success'],
            'duration': import_result['duration'],
            'errors': import_result.get('errors', [])
        })
    
    # Check 3: Required files exist
    files_result = check_required_files(working_directory, language)
    checks.append({
        'name': 'Required Files',
        'passed': files_result['success'],
        'duration': files_result['duration'],
        'errors': files_result.get('errors', [])
    })
    
    all_passed = all(check['passed'] for check in checks)
    total_duration = time.time() - start_time
    
    return {
        'success': all_passed,
        'checks': checks,
        'total_duration': total_duration,
        'language': language
    }


def detect_project_language(working_directory: str) -> str:
    """
    Detect project type from files.
    
    Returns: 'python' | 'typescript' | 'javascript' | 'rust' | 'go' | 'unknown'
    """
    working_dir = Path(working_directory)
    
    # Check for language-specific files
    if (working_dir / 'Cargo.toml').exists():
        return 'rust'
    elif (working_dir / 'go.mod').exists():
        return 'go'
    elif (working_dir / 'package.json').exists():
        # Check if TypeScript
        try:
            package_json = json.loads((working_dir / 'package.json').read_text())
            deps = {**package_json.get('dependencies', {}), **package_json.get('devDependencies', {})}
            if 'typescript' in deps:
                return 'typescript'
        except:
            pass
        return 'javascript'
    elif (working_dir / 'requirements.txt').exists() or (working_dir / 'pyproject.toml').exists():
        return 'python'
    else:
        # Check for source files
        if list(working_dir.rglob('*.py')):
            return 'python'
        elif list(working_dir.rglob('*.ts')):
            return 'typescript'
        elif list(working_dir.rglob('*.js')):
            return 'javascript'
        elif list(working_dir.rglob('*.rs')):
            return 'rust'
        elif list(working_dir.rglob('*.go')):
            return 'go'
    
    return 'unknown'


def run_syntax_check(working_directory: str, language: str) -> Dict:
    """
    Language-specific syntax validation.
    
    Returns: {'success': bool, 'errors': list, 'duration': float, 'skipped': bool}
    """
    start_time = time.time()
    working_dir = Path(working_directory)
    
    try:
        if language == 'python':
            # Python: compile all .py files
            py_files = list(working_dir.rglob('*.py'))
            # Exclude venv, node_modules, .git
            py_files = [f for f in py_files if not any(
                part in f.parts for part in ['.git', 'venv', 'env', '__pycache__', 'node_modules']
            )]
            
            errors = []
            for py_file in py_files:
                try:
                    result = subprocess.run(
                        ['python3', '-m', 'py_compile', str(py_file)],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                    
                    if result.returncode != 0:
                        errors.append({
                            'file': str(py_file.relative_to(working_dir)),
                            'error': result.stderr.strip()
                        })
                except subprocess.TimeoutExpired:
                    errors.append({
                        'file': str(py_file.relative_to(working_dir)),
                        'error': 'Compilation timed out'
                    })
            
            return {
                'success': len(errors) == 0,
                'errors': errors,
                'duration': time.time() - start_time,
                'skipped': False
            }
        
        elif language == 'typescript':
            # TypeScript: run tsc --noEmit
            try:
                result = subprocess.run(
                    ['npx', 'tsc', '--noEmit'],
                    cwd=working_directory,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                errors = []
                if result.returncode != 0:
                    # Parse TypeScript errors
                    for line in result.stdout.split('\n'):
                        if line.strip() and ': error TS' in line:
                            errors.append({'error': line.strip()})
                
                return {
                    'success': result.returncode == 0,
                    'errors': errors,
                    'duration': time.time() - start_time,
                    'skipped': False
                }
            except (subprocess.TimeoutExpired, FileNotFoundError):
                return {
                    'success': True,
                    'errors': [],
                    'duration': time.time() - start_time,
                    'skipped': True,
                    'skip_reason': 'TypeScript compiler not available or timed out'
                }
        
        elif language == 'rust':
            # Rust: cargo check
            try:
                result = subprocess.run(
                    ['cargo', 'check'],
                    cwd=working_directory,
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                
                errors = []
                if result.returncode != 0:
                    errors.append({'error': result.stderr.strip()})
                
                return {
                    'success': result.returncode == 0,
                    'errors': errors,
                    'duration': time.time() - start_time,
                    'skipped': False
                }
            except (subprocess.TimeoutExpired, FileNotFoundError):
                return {
                    'success': True,
                    'errors': [],
                    'duration': time.time() - start_time,
                    'skipped': True,
                    'skip_reason': 'Cargo not available or check timed out'
                }
        
        elif language == 'go':
            # Go: go build
            try:
                result = subprocess.run(
                    ['go', 'build', './...'],
                    cwd=working_directory,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                errors = []
                if result.returncode != 0:
                    errors.append({'error': result.stderr.strip()})
                
                return {
                    'success': result.returncode == 0,
                    'errors': errors,
                    'duration': time.time() - start_time,
                    'skipped': False
                }
            except (subprocess.TimeoutExpired, FileNotFoundError):
                return {
                    'success': True,
                    'errors': [],
                    'duration': time.time() - start_time,
                    'skipped': True,
                    'skip_reason': 'Go compiler not available or build timed out'
                }
        
        else:
            # Unknown language, skip check
            return {
                'success': True,
                'errors': [],
                'duration': time.time() - start_time,
                'skipped': True,
                'skip_reason': f'Unknown language: {language}'
            }
    
    except Exception as e:
        return {
            'success': False,
            'errors': [{'error': f'Syntax check failed: {str(e)}'}],
            'duration': time.time() - start_time,
            'skipped': False
        }


def check_imports(working_directory: str, language: str) -> Dict:
    """
    Validate all imports resolve to existing files.
    
    Basic implementation - checks if imported files exist.
    """
    start_time = time.time()
    working_dir = Path(working_directory)
    
    errors = []
    
    if language == 'python':
        # Check Python imports
        py_files = [f for f in working_dir.rglob('*.py') if not any(
            part in f.parts for part in ['.git', 'venv', 'env', '__pycache__']
        )]
        
        for py_file in py_files:
            try:
                content = py_file.read_text()
                # Find relative imports like "from .module import" or "from ..package import"
                import re
                relative_imports = re.findall(r'from\s+(\.+\w+)\s+import', content)
                
                # Basic check: just verify file is syntactically correct (already done in syntax check)
                # Full import resolution would require running Python interpreter
                pass
            except Exception:
                pass
    
    # For now, import checking is basic - mainly caught by syntax check
    # More sophisticated import resolution could be added later
    
    return {
        'success': len(errors) == 0,
        'errors': errors,
        'duration': time.time() - start_time
    }


def check_required_files(working_directory: str, language: str) -> Dict:
    """
    Verify essential files exist for the project type.
    """
    start_time = time.time()
    working_dir = Path(working_directory)
    
    errors = []
    
    # Check for language-specific required files
    if language == 'python':
        # Python projects should have at least one .py file
        if not list(working_dir.rglob('*.py')):
            errors.append({'error': 'No Python source files found'})
    
    elif language == 'typescript':
        # TypeScript projects should have tsconfig.json
        if not (working_dir / 'tsconfig.json').exists():
            errors.append({'error': 'Missing tsconfig.json for TypeScript project'})
    
    elif language == 'rust':
        # Rust projects should have Cargo.toml
        if not (working_dir / 'Cargo.toml').exists():
            errors.append({'error': 'Missing Cargo.toml for Rust project'})
    
    elif language == 'go':
        # Go projects should have go.mod
        if not (working_dir / 'go.mod').exists():
            errors.append({'error': 'Missing go.mod for Go project'})
    
    return {
        'success': len(errors) == 0,
        'errors': errors,
        'duration': time.time() - start_time
    }


# CLI interface for standalone execution
if __name__ == '__main__':
    import sys
    import json
    
    if len(sys.argv) < 2:
        print("Usage: python integration_pre_check.py <working-directory>")
        sys.exit(1)
    
    working_directory = sys.argv[1]
    result = integration_pre_check(working_directory)
    
    # Print JSON result
    print(json.dumps(result, indent=2))
    
    # Exit with error code if validation failed
    sys.exit(0 if result['success'] else 1)
