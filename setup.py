#!/usr/bin/env python3
"""
Context Foundry - Setup Script
Installs the 'cf' CLI command for easy access to Mission Control
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read version from __version__.py
version_file = Path(__file__).parent / "__version__.py"
version_info = {}
exec(version_file.read_text(), version_info)

# Read README for long description
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text() if readme_file.exists() else ""

setup(
    name="context-foundry",
    version=version_info["__version__"],
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
