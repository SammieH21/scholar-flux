# /exceptions/storage_exceptions.py
"""Implements exceptions involving both potential edge-cases and common issues involving data and cache storage."""


class StorageCacheException(Exception):
    """Base exception for Storage Issues."""

    pass


class ConnectionFailed(StorageCacheException):
    """Exception arising from storage connection errors."""

    pass


class KeyNotFound(KeyError):
    """Exception resulting from a missing or empty key being provided."""

    pass


class CacheRetrievalException(StorageCacheException):
    """Exception raised when retrieval from a storage device fails."""

    pass


class CacheUpdateException(StorageCacheException):
    """Exception raised when updating a cache storage device fails."""

    pass


class CacheDeletionException(StorageCacheException):
    """Exception raised when record deletion from a storage device fails."""

    pass


class CacheVerificationException(StorageCacheException):
    """Exception raised when the cache validation from a storage device fails."""

    pass


__all__ = [
    "StorageCacheException",
    "ConnectionFailed",
    "KeyNotFound",
    "CacheRetrievalException",
    "CacheUpdateException",
    "CacheDeletionException",
    "CacheVerificationException",
]
