"""
Utility functions for BAML + Anthropic integration.

Includes logging setup, retry logic, and helper functions.
"""

import asyncio
import logging
import sys
from typing import TypeVar, Callable, Any, Optional
from functools import wraps


T = TypeVar("T")


def setup_logging(level: str = "INFO") -> logging.Logger:
    """
    Set up logging with consistent format.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        Configured logger instance
    """
    # Create logger
    logger = logging.getLogger("baml_anthropic")
    logger.setLevel(getattr(logging, level.upper()))

    # Create console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, level.upper()))

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)

    # Add handler to logger
    if not logger.handlers:
        logger.addHandler(handler)

    return logger


async def retry_with_backoff(
    func: Callable[..., T],
    *args: Any,
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    **kwargs: Any,
) -> T:
    """
    Retry an async function with exponential backoff.

    Args:
        func: Async function to retry
        *args: Positional arguments for func
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds before first retry
        backoff_factor: Multiplier for delay after each retry
        **kwargs: Keyword arguments for func

    Returns:
        Result from successful function call

    Raises:
        Exception: Last exception if all retries fail
    """
    logger = logging.getLogger("baml_anthropic")
    delay = initial_delay
    last_exception: Optional[Exception] = None

    for attempt in range(max_retries):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            logger.warning(
                f"Attempt {attempt + 1}/{max_retries} failed: {e}. "
                f"Retrying in {delay:.1f}s..."
            )
            await asyncio.sleep(delay)
            delay *= backoff_factor

    # All retries failed
    logger.error(f"All {max_retries} attempts failed")
    raise last_exception or Exception("Retry failed with unknown error")


def async_retry(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
) -> Callable:
    """
    Decorator for automatic retry with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds before first retry
        backoff_factor: Multiplier for delay after each retry

    Returns:
        Decorated function with retry logic

    Example:
        @async_retry(max_retries=3)
        async def my_api_call():
            return await anthropic_client.call()
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            return await retry_with_backoff(
                func,
                *args,
                max_retries=max_retries,
                initial_delay=initial_delay,
                backoff_factor=backoff_factor,
                **kwargs,
            )

        return wrapper

    return decorator


class DocumentProcessingError(Exception):
    """Exception raised for document processing errors."""

    pass


class DataAnalysisError(Exception):
    """Exception raised for data analysis errors."""

    pass


class SkillExecutionError(Exception):
    """Exception raised for skill execution errors."""

    pass


class ConfigurationError(Exception):
    """Exception raised for configuration errors."""

    pass
