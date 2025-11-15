"""
Storage layer for Context Foundry

Provides S3 integration for community patterns and skills library.
"""

from .s3_client import S3PatternClient

__all__ = ["S3PatternClient"]
