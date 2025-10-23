#!/usr/bin/env python3
"""
Setup configuration for Context Foundry.
Makes the 'foundry' command available globally.
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read long description from README
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text() if readme_file.exists() else ""

# Read requirements
requirements_file = Path(__file__).parent / "requirements.txt"
requirements = []
if requirements_file.exists():
    requirements = [
        line.strip()
        for line in requirements_file.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]

setup(
    name="context-foundry",
    version="2.0.1",
    description="The Anti-Vibe Coding System - Spec-first development through automated context engineering",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Context Foundry Team",
    author_email="contact@contextfoundry.dev",
    url="https://github.com/yourusername/context-foundry",
    license="MIT",
    packages=find_packages(),
    include_package_data=True,
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "foundry=tools.cli:foundry",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Code Generators",
        "Topic :: Software Development :: Libraries :: Application Frameworks",
    ],
    python_requires=">=3.8",
    keywords=[
        "ai",
        "coding-assistant",
        "claude",
        "context-engineering",
        "code-generation",
        "development-workflow",
        "automation",
    ],
)
