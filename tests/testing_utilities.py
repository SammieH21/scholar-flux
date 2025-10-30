# /tests/testing_utilities
"""Helper module for reusing test functionality with similar logic under the hood to verify ScholarFlux functionality"""
from typing import Optional, Callable, Type
import os


def enable_debugging():
    """Helper function that defines the environment variables needed to enable logging by default in ScholarFlux"""
    os.environ["SCHOLAR_FLUX_LOG_LEVEL"] = "DEBUG"
    os.environ["SCHOLAR_FLUX_ENABLE_LOGGING"] = "TRUE"


def raise_error(exception_type: Type[BaseException], message: Optional[str] = None) -> Callable:
    """Helper method for manually raising an error message."""
    return lambda *args, **kwargs: (_ for _ in ()).throw(exception_type(message))
