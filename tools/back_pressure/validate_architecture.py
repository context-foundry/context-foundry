"""
Architecture Validator - Architect Phase Back Pressure

Validates that Architect's design is complete, consistent, and implementable.
"""

import re
import time
from pathlib import Path
from typing import Dict, List


def validate_architecture(architecture_md_path: str) -> Dict:
    """
    Check architecture.md for completeness and consistency.
    
    Args:
        architecture_md_path: Path to architecture.md file
        
    Returns:
        {
            'valid': bool,
            'issues': [{'severity': 'error|warning', 'message': str, 'fix': str}],
            'checks_performed': int,
            'duration': float
        }
    """
    start_time = time.time()
    
    # Read architecture document
    try:
        content = Path(architecture_md_path).read_text()
    except FileNotFoundError:
        return {
            'valid': False,
            'issues': [{'severity': 'error', 'message': f'Architecture file not found: {architecture_md_path}', 'fix': 'Ensure Architect phase completed successfully'}],
            'checks_performed': 0,
            'duration': time.time() - start_time
        }
    
    issues = []
    checks_performed = 0
    
    # Check 1: Test strategy exists
    checks_performed += 1
    if not check_test_strategy_exists(content):
        issues.append({
            'severity': 'error',
            'message': 'No test strategy specified in architecture',
            'fix': 'Add "Testing Requirements", "Test Plan", or similar section with test framework and approach'
        })
    
    # Check 2: File structure is specified
    checks_performed += 1
    if not check_file_structure_specified(content):
        issues.append({
            'severity': 'error',
            'message': 'No file structure specified in architecture',
            'fix': 'Add "File Structure", "Directory Structure", or "Project Structure" section with file tree'
        })
    
    # Check 3: Duplicate file paths
    checks_performed += 1
    duplicates = find_duplicate_file_paths(content)
    if duplicates:
        issues.append({
            'severity': 'error',
            'message': f'Duplicate file paths found: {", ".join(duplicates)}',
            'fix': 'Ensure each file path is unique in the architecture'
        })
    
    # Check 4: Implementation steps exist
    checks_performed += 1
    if not check_implementation_steps_exist(content):
        issues.append({
            'severity': 'warning',
            'message': 'No implementation steps or plan specified',
            'fix': 'Add "Implementation Steps", "Build Plan", or similar section with ordered steps'
        })
    
    duration = time.time() - start_time
    
    # Valid if no errors (warnings are OK)
    errors = [issue for issue in issues if issue['severity'] == 'error']
    valid = len(errors) == 0
    
    return {
        'valid': valid,
        'issues': issues,
        'checks_performed': checks_performed,
        'duration': duration
    }


def check_test_strategy_exists(content: str) -> bool:
    """
    Check if architecture specifies a test strategy.
    
    Looks for sections with 'test' in heading or mentions of test frameworks.
    """
    # Check for test-related headings
    test_heading_pattern = r'##\s+.*test.*'
    if re.search(test_heading_pattern, content, re.IGNORECASE):
        return True
    
    # Check for test framework mentions
    test_frameworks = [
        'pytest', 'jest', 'mocha', 'junit', 'rspec', 'go test',
        'cargo test', 'unittest', 'vitest', 'playwright', 'cypress'
    ]
    
    content_lower = content.lower()
    return any(framework in content_lower for framework in test_frameworks)


def check_file_structure_specified(content: str) -> bool:
    """
    Check if architecture includes a file/directory structure.
    
    Looks for sections with 'structure', 'directory', or 'files' in heading.
    """
    structure_patterns = [
        r'##\s+.*(?:file|directory|project|folder)\s+structure.*',
        r'##\s+.*structure.*',
        r'```.*\n.*(?:src/|lib/|app/|tests/)',  # Code block with paths
    ]
    
    for pattern in structure_patterns:
        if re.search(pattern, content, re.IGNORECASE | re.MULTILINE):
            return True
    
    return False


def check_implementation_steps_exist(content: str) -> bool:
    """
    Check if architecture includes implementation steps or plan.
    
    Looks for sections with 'implementation', 'steps', 'plan', or numbered lists.
    """
    step_patterns = [
        r'##\s+.*(?:implementation|build|development)\s+(?:steps|plan|order).*',
        r'##\s+.*(?:steps|plan).*',
        r'(?:Step|Phase)\s+\d+:',  # "Step 1:", "Phase 2:"
        r'^\d+\.\s+\w+',  # Numbered list "1. Create..."
    ]
    
    for pattern in step_patterns:
        if re.search(pattern, content, re.IGNORECASE | re.MULTILINE):
            return True
    
    return False


def find_duplicate_file_paths(content: str) -> List[str]:
    """
    Extract all file paths and find duplicates.
    
    Returns list of duplicate paths.
    """
    file_paths = extract_file_paths(content)
    
    # Find duplicates
    seen = set()
    duplicates = set()
    
    for path in file_paths:
        if path in seen:
            duplicates.add(path)
        else:
            seen.add(path)
    
    return sorted(list(duplicates))


def extract_file_paths(content: str) -> List[str]:
    """
    Extract file paths from architecture document.
    
    Looks for patterns like:
        src/main.py
        lib/utils.js
        - src/components/Header.tsx
        ├── app/
        │   └── main.rs
    """
    paths = []
    
    # Pattern 1: Lines starting with directory tree characters or list markers
    tree_pattern = r'^[\s│├└─\-\*]*([a-zA-Z0-9_\-\.]+(?:/[a-zA-Z0-9_\-\.]+)*\.[a-z]{1,4})'
    
    for line in content.split('\n'):
        match = re.search(tree_pattern, line)
        if match:
            paths.append(match.group(1))
    
    # Pattern 2: Paths in backticks or quotes
    inline_pattern = r'[`"\']([a-zA-Z0-9_\-\.]+(?:/[a-zA-Z0-9_\-\.]+)*\.[a-z]{1,4})[`"\']'
    paths.extend(re.findall(inline_pattern, content))
    
    return paths


# CLI interface for standalone execution
if __name__ == '__main__':
    import sys
    import json
    
    if len(sys.argv) < 2:
        print("Usage: python validate_architecture.py <architecture-md-path>")
        sys.exit(1)
    
    architecture_md_path = sys.argv[1]
    result = validate_architecture(architecture_md_path)
    
    # Print JSON result
    print(json.dumps(result, indent=2))
    
    # Exit with error code if validation failed
    sys.exit(0 if result['valid'] else 1)
