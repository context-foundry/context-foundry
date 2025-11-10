#!/usr/bin/env python3
"""
Context Foundry - Setup Script
Installs the 'cf' CLI command for easy access to Mission Control
"""

from setuptools import setup, find_packages
from pathlib import Path
import sys
import re

# Check Python version early with helpful error message
if sys.version_info < (3, 10):
    sys.stderr.write(
        "ERROR: Context Foundry requires Python 3.10 or higher.\n\n"
        f"Your current Python version: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}\n\n"
        "Why Python 3.10+?\n"
        "  - Context Foundry uses structural pattern matching (match statements)\n"
        "  - Advanced type hints (TypeAlias, ParamSpec, etc.)\n"
        "  - These features are exclusive to Python 3.10+\n\n"
        "Solutions:\n"
        "  1. Upgrade Python: brew install python@3.11 (macOS) or use your package manager\n"
        "  2. Use pyenv: pyenv install 3.11 && pyenv local 3.11\n"
        "  3. Use a virtual environment with Python 3.10+:\n"
        "     python3.11 -m venv venv\n"
        "     source venv/bin/activate\n"
        "     pip install -e .\n\n"
    )
    sys.exit(1)

# Read version from __version__.py safely without code execution
version_file = Path(__file__).parent / "__version__.py"
version_content = version_file.read_text(encoding='utf-8')
version_match = re.search(
    r'^__version__\s*=\s*["\']([^"\']+)["\']',
    version_content,
    re.MULTILINE
)
if not version_match:
    raise RuntimeError(
        "Unable to find version string in __version__.py. "
        "Expected format: __version__ = \"x.y.z\""
    )
version = version_match.group(1)

# Read README for long description
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text() if readme_file.exists() else ""

setup(
    name="context-foundry",
    version=version,
    description="The AI That Builds Itself: Recursive Claude Spawning via Meta-MCP",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Context Foundry",
    author_email="noreply@contextfoundry.dev",
    url="https://github.com/context-foundry/context-foundry",
    packages=find_packages(),
    include_package_data=True,
    python_requires=">=3.10",
    install_requires=[
        "fastmcp>=2.0.0",
        "nest-asyncio>=1.5.0",
        "tiktoken>=0.5.0",
        "baml-py>=0.211.0",
        "textual>=0.50.0",
        "psutil>=5.9.0",
    ],
    entry_points={
        "console_scripts": [
            "cf=tools.cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Topic :: Software Development :: Build Tools",
        "Topic :: Software Development :: Code Generators",
    ],
    keywords="ai claude mcp autonomous-build code-generation",
)
