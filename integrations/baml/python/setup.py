"""
Setup script for BAML + Anthropic Agent Skills integration.

Pattern: python-missing-setup-py
Reason: Include both pyproject.toml AND setup.py for maximum compatibility
"""

from setuptools import setup, find_packages

setup(
    name="baml-anthropic-integration",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "anthropic>=0.40.0",
        "baml-py>=0.75.0",
        "python-dotenv>=1.0.0",
        "pydantic>=2.0.0",
    ],
    python_requires=">=3.10",
)
