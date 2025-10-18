# /exceptions/storage_exceptions.py
"""
Implements exceptions involving both potential edge-cases and common issues involving data and cache storage.
"""


class StorageCacheException(Exception):
    """Base exception for Storage Issues"""

    pass


class ConnectionFailed(StorageCacheException):
    """Exception arising from storage connection errors"""

    pass


class KeyNotFound(KeyError):
    """Exception resulting from a missing or empty key being provided"""

    pass

__all__ = [
    "StorageCacheException",
    "ConnectionFailed",
    "KeyNotFound"
]
