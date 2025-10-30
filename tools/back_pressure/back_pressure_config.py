"""
Back Pressure Configuration - Language-Specific Profiles

Defines validation strictness and requirements based on project language.
Languages with weaker natural pressure (Python) get stricter validation.
Languages with strong natural pressure (Rust) get lighter validation.
"""

import json
from pathlib import Path
from typing import Dict, Optional


# Language-specific back pressure profiles
LANGUAGE_PROFILES = {
    'python': {
        'natural_pressure': 'low',
        'description': 'Interpreted, no compilation - needs strict checks',
        'checks': {
            'syntax': {
                'enabled': True,
                'command': 'python3 -m py_compile {file}',
                'timeout': 10
            },
            'type': {
                'enabled': True,
                'command': 'mypy --strict {file}',
                'optional': True,  # Don't fail if mypy not installed
                'timeout': 15
            },
            'lint': {
                'enabled': True,
                'command': 'ruff check {file}',
                'optional': True,  # Don't fail if ruff not installed
                'timeout': 10
            },
            'imports': {
                'enabled': True
            }
        },
        'test_requirements': {
            'min_coverage': 80,
            'timeout_seconds': 60,
            'require_unit_tests': True,
            'require_integration_tests': True
        }
    },
    
    'typescript': {
        'natural_pressure': 'medium',
        'description': 'Type system helps, but not compiled to native',
        'checks': {
            'syntax': {
                'enabled': True,
                'command': 'npx tsc --noEmit',
                'timeout': 30
            },
            'type': {
                'enabled': True,
                'command': 'npx tsc --noEmit',
                'timeout': 30
            },
            'lint': {
                'enabled': True,
                'command': 'npx eslint {file}',
                'optional': True,
                'timeout': 15
            },
            'imports': {
                'enabled': True
            }
        },
        'test_requirements': {
            'min_coverage': 70,
            'timeout_seconds': 45,
            'require_unit_tests': True,
            'require_integration_tests': False
        }
    },
    
    'javascript': {
        'natural_pressure': 'low',
        'description': 'No type system, interpreted - needs checks',
        'checks': {
            'syntax': {
                'enabled': True,
                'command': 'node --check {file}',
                'timeout': 10
            },
            'lint': {
                'enabled': True,
                'command': 'npx eslint {file}',
                'optional': True,
                'timeout': 15
            },
            'imports': {
                'enabled': True
            }
        },
        'test_requirements': {
            'min_coverage': 75,
            'timeout_seconds': 45,
            'require_unit_tests': True,
            'require_integration_tests': True
        }
    },
    
    'rust': {
        'natural_pressure': 'high',
        'description': 'Strong type system, borrow checker, compiler - excellent natural pressure',
        'checks': {
            'syntax': {
                'enabled': True,
                'command': 'cargo check',
                'timeout': 60
            },
            'type': {
                'enabled': False,  # Included in cargo check
            },
            'lint': {
                'enabled': True,
                'command': 'cargo clippy',
                'optional': True,
                'timeout': 60
            },
            'imports': {
                'enabled': False  # Cargo handles dependency resolution
            }
        },
        'test_requirements': {
            'min_coverage': 60,  # Lower OK because compiler catches so much
            'timeout_seconds': 120,  # Compilation can be slow
            'require_unit_tests': True,
            'require_integration_tests': False
        }
    },
    
    'go': {
        'natural_pressure': 'medium-high',
        'description': 'Type system, compiled, fast compiler - good natural pressure',
        'checks': {
            'syntax': {
                'enabled': True,
                'command': 'go build',
                'timeout': 30
            },
            'type': {
                'enabled': False,  # Included in go build
            },
            'lint': {
                'enabled': True,
                'command': 'go vet',
                'timeout': 20
            },
            'format': {
                'enabled': True,
                'command': 'gofmt -l .',
                'timeout': 10
            },
            'imports': {
                'enabled': False  # Compiler handles
            }
        },
        'test_requirements': {
            'min_coverage': 65,
            'timeout_seconds': 30,  # Go tests are fast
            'require_unit_tests': True,
            'require_integration_tests': False
        }
    },
    
    'ruby': {
        'natural_pressure': 'low',
        'description': 'Interpreted, dynamic typing - needs checks',
        'checks': {
            'syntax': {
                'enabled': True,
                'command': 'ruby -c {file}',
                'timeout': 10
            },
            'lint': {
                'enabled': True,
                'command': 'rubocop {file}',
                'optional': True,
                'timeout': 15
            }
        },
        'test_requirements': {
            'min_coverage': 75,
            'timeout_seconds': 60,
            'require_unit_tests': True,
            'require_integration_tests': True
        }
    }
}


def get_back_pressure_config(working_directory: str) -> Dict:
    """
    Detect project language and return appropriate back pressure config.
    
    Args:
        working_directory: Project root directory
        
    Returns:
        Language configuration dict
    """
    language = detect_language(working_directory)
    
    # Return config for detected language, default to Python if unknown
    config = LANGUAGE_PROFILES.get(language, LANGUAGE_PROFILES['python'])
    
    # Add detected language to config
    config['detected_language'] = language
    
    return config


def detect_language(working_directory: str) -> str:
    """
    Check for language-specific files to detect project type.
    
    Returns: 'python' | 'typescript' | 'javascript' | 'rust' | 'go' | 'ruby' | 'unknown'
    """
    working_dir = Path(working_directory)
    
    # Check for definitive language markers
    if (working_dir / 'Cargo.toml').exists():
        return 'rust'
    
    if (working_dir / 'go.mod').exists():
        return 'go'
    
    if (working_dir / 'Gemfile').exists():
        return 'ruby'
    
    if (working_dir / 'package.json').exists():
        # Distinguish TypeScript from JavaScript
        try:
            package_json = json.loads((working_dir / 'package.json').read_text())
            dependencies = {
                **package_json.get('dependencies', {}),
                **package_json.get('devDependencies', {})
            }
            
            if 'typescript' in dependencies:
                return 'typescript'
        except:
            pass
        
        # Check for tsconfig.json
        if (working_dir / 'tsconfig.json').exists():
            return 'typescript'
        
        return 'javascript'
    
    if (working_dir / 'requirements.txt').exists() or (working_dir / 'pyproject.toml').exists():
        return 'python'
    
    # Fallback: check for source files
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
    elif list(working_dir.rglob('*.rb')):
        return 'ruby'
    
    return 'unknown'


def get_language_natural_pressure(language: str) -> str:
    """
    Get natural pressure level for a language.
    
    Returns: 'low' | 'medium' | 'medium-high' | 'high'
    """
    profile = LANGUAGE_PROFILES.get(language.lower())
    return profile['natural_pressure'] if profile else 'low'


def should_enable_check(language: str, check_type: str) -> bool:
    """
    Check if a specific validation should be enabled for a language.
    
    Args:
        language: Language name
        check_type: 'syntax' | 'type' | 'lint' | 'imports'
        
    Returns:
        True if check should be enabled
    """
    profile = LANGUAGE_PROFILES.get(language.lower())
    
    if not profile:
        return False
    
    check_config = profile.get('checks', {}).get(check_type, {})
    return check_config.get('enabled', False)


# CLI interface for standalone usage
if __name__ == '__main__':
    import sys
    import json
    
    if len(sys.argv) < 2:
        print("Usage: python back_pressure_config.py <working-directory>")
        print("\nAvailable commands:")
        print("  python back_pressure_config.py <dir>           - Show config for directory")
        print("  python back_pressure_config.py list            - List all language profiles")
        sys.exit(1)
    
    if sys.argv[1] == 'list':
        # List all available profiles
        print("Available Language Profiles:")
        print()
        for lang, profile in LANGUAGE_PROFILES.items():
            print(f"  {lang}:")
            print(f"    Natural Pressure: {profile['natural_pressure']}")
            print(f"    Description: {profile['description']}")
            print()
    else:
        # Show config for directory
        working_directory = sys.argv[1]
        config = get_back_pressure_config(working_directory)
        print(json.dumps(config, indent=2))
