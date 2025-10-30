"""
Tech Stack Validator - Scout Phase Back Pressure

Validates that Scout's technology recommendations are feasible and available
in the current environment.
"""

import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional
import time


def validate_tech_stack(scout_report_path: str) -> Dict:
    """
    Extract tech stack from scout-report.md and validate availability.
    
    Args:
        scout_report_path: Path to scout-report.md file
        
    Returns:
        {
            'success': bool,
            'errors': [{'message': str, 'fix': str, 'severity': str}],
            'warnings': [{'message': str}],
            'checks_performed': int,
            'duration': float
        }
    """
    start_time = time.time()
    
    # Read scout report
    try:
        content = Path(scout_report_path).read_text()
    except FileNotFoundError:
        return {
            'success': False,
            'errors': [{'message': f'Scout report not found: {scout_report_path}', 'fix': 'Ensure Scout phase completed successfully', 'severity': 'error'}],
            'warnings': [],
            'checks_performed': 0,
            'duration': time.time() - start_time
        }
    
    # Extract technology recommendations
    tech_stack = extract_tech_stack(content)
    
    if not tech_stack:
        # No tech stack section found - not an error, just skip validation
        return {
            'success': True,
            'errors': [],
            'warnings': [{'message': 'No technology stack section found in scout report - skipping validation'}],
            'checks_performed': 0,
            'duration': time.time() - start_time
        }
    
    errors = []
    warnings = []
    checks_performed = 0
    
    # Validate each technology
    for tech in tech_stack:
        checks_performed += 1
        
        if tech['type'] in ['language', 'runtime']:
            result = check_language_available(tech['name'], tech.get('version'))
            
            if result['status'] == 'error':
                errors.append(result)
            elif result['status'] == 'warning':
                warnings.append(result)
        
        elif tech['type'] == 'framework':
            # Framework checks could be added here
            # For now, we just check if the language for the framework is available
            pass
    
    duration = time.time() - start_time
    
    return {
        'success': len(errors) == 0,
        'errors': errors,
        'warnings': warnings,
        'checks_performed': checks_performed,
        'duration': duration
    }


def extract_tech_stack(scout_report_content: str) -> List[Dict]:
    """
    Extract technology stack from scout-report markdown.
    
    Looks for sections like:
    ## Technology Stack
    - Language: Python 3.11+
    - Framework: FastAPI
    - Database: PostgreSQL 15
    
    Returns:
        [{'type': 'language', 'name': 'Python', 'version': '3.11', 'raw': 'Python 3.11+'}]
    """
    tech_stack = []
    
    # Find Technology Stack section
    tech_section_match = re.search(
        r'##\s+Technology Stack.*?\n(.*?)(?=\n##|\Z)',
        scout_report_content,
        re.DOTALL | re.IGNORECASE
    )
    
    if not tech_section_match:
        return tech_stack
    
    tech_section = tech_section_match.group(1)
    
    # Parse each technology line
    # Format: "- Language: Python 3.11+" or "- **Language**: Python 3.11+"
    for line in tech_section.split('\n'):
        line = line.strip()
        if not line.startswith('-'):
            continue
        
        # Parse "Category: Name Version" or "**Category**: Name Version"
        match = re.match(r'-\s*\*{0,2}(\w+)\*{0,2}:\s*(.+)', line)
        if match:
            category = match.group(1).lower()
            value = match.group(2).strip()
            
            # Extract name and version
            # "Python 3.11+" → name="Python", version="3.11"
            version_match = re.search(r'(\d+\.[\d.]+)', value)
            version = version_match.group(1) if version_match else None
            name = re.sub(r'\s*\d+\.[\d.]+\+?', '', value).strip()
            
            tech_stack.append({
                'type': category,
                'name': name,
                'version': version,
                'raw': value
            })
    
    return tech_stack


def check_language_available(language: str, min_version: Optional[str] = None) -> Dict:
    """
    Check if programming language runtime is available.
    
    Args:
        language: Language name (e.g., 'Python', 'Node', 'Rust')
        min_version: Minimum required version (optional)
        
    Returns:
        {
            'status': 'success' | 'error' | 'warning',
            'message': str,
            'fix': str (optional),
            'severity': str (optional)
        }
    """
    version_commands = {
        'python': 'python3 --version',
        'node': 'node --version',
        'nodejs': 'node --version',
        'rust': 'rustc --version',
        'go': 'go version',
        'ruby': 'ruby --version',
        'java': 'java -version',
    }
    
    language_lower = language.lower()
    cmd = version_commands.get(language_lower)
    
    if not cmd:
        return {
            'status': 'warning',
            'message': f'Unknown language: {language} - skipping version check'
        }
    
    try:
        result = subprocess.run(
            cmd.split(),
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            # Parse version from output
            installed_version = parse_version(result.stdout + result.stderr)
            
            if not installed_version:
                return {
                    'status': 'warning',
                    'message': f'{language} found but version could not be determined'
                }
            
            # Compare versions if min_version specified
            if min_version:
                comparison = version_compare(installed_version, min_version)
                
                if comparison >= 0:
                    return {
                        'status': 'success',
                        'message': f'{language} {installed_version} available (required: {min_version}+)'
                    }
                else:
                    return {
                        'status': 'error',
                        'message': f'{language} {installed_version} too old (required: {min_version}+)',
                        'fix': f'Upgrade {language} to {min_version}+ or revise architecture to use {installed_version}',
                        'severity': 'error'
                    }
            else:
                # No version requirement, just confirm it's available
                return {
                    'status': 'success',
                    'message': f'{language} {installed_version} available'
                }
        else:
            return {
                'status': 'error',
                'message': f'{language} not found in PATH',
                'fix': f'Install {language} {min_version or ""} or choose a different language',
                'severity': 'error'
            }
    
    except subprocess.TimeoutExpired:
        return {
            'status': 'warning',
            'message': f'{language} version check timed out (5s)'
        }
    except Exception as e:
        return {
            'status': 'warning',
            'message': f'{language} check failed: {str(e)}'
        }


def parse_version(version_string: str) -> Optional[str]:
    """
    Extract version number from version command output.
    
    Examples:
        "Python 3.11.4" → "3.11.4"
        "node v18.16.0" → "18.16.0"
        "rustc 1.70.0" → "1.70.0"
    """
    # Try to find version pattern X.Y.Z
    match = re.search(r'(\d+\.\d+(?:\.\d+)?)', version_string)
    return match.group(1) if match else None


def version_compare(v1: str, v2: str) -> int:
    """
    Compare two semantic version strings.
    
    Returns:
        -1 if v1 < v2
         0 if v1 == v2
         1 if v1 > v2
    """
    try:
        v1_parts = [int(x) for x in v1.split('.')]
        v2_parts = [int(x) for x in v2.split('.')]
        
        # Pad shorter version with zeros
        max_len = max(len(v1_parts), len(v2_parts))
        v1_parts += [0] * (max_len - len(v1_parts))
        v2_parts += [0] * (max_len - len(v2_parts))
        
        for a, b in zip(v1_parts, v2_parts):
            if a < b:
                return -1
            elif a > b:
                return 1
        
        return 0
    except (ValueError, AttributeError):
        # If version parsing fails, consider them equal
        return 0


# CLI interface for standalone execution
if __name__ == '__main__':
    import sys
    import json
    
    if len(sys.argv) < 2:
        print("Usage: python validate_tech_stack.py <scout-report-path>")
        sys.exit(1)
    
    scout_report_path = sys.argv[1]
    result = validate_tech_stack(scout_report_path)
    
    # Print JSON result
    print(json.dumps(result, indent=2))
    
    # Exit with error code if validation failed
    sys.exit(0 if result['success'] else 1)
