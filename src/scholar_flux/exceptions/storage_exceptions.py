# /exceptions/storage_exceptions.py
"""Implements exceptions involving both potential edge-cases and common issues involving data and cache storage."""


class StorageCacheException(Exception):
    """Base exception for Storage Issues."""


class ConnectionFailed(StorageCacheException):
    """Exception arising from storage connection errors."""


class KeyNotFound(KeyError):
    """Exception resulting from a missing or empty key being provided."""


class CacheRetrievalException(StorageCacheException):
    """Exception raised when retrieval from a storage device fails."""


class CacheUpdateException(StorageCacheException):
    """Exception raised when updating a cache storage device fails."""


class CacheDeletionException(StorageCacheException):
    """Exception raised when record deletion from a storage device fails."""


class CacheVerificationException(StorageCacheException):
    """Exception raised when the cache validation from a storage device fails."""


class CacheParameterValidationException(StorageCacheException):
    """Exception raised when invalid parameters are passed to a CacheStorage device."""


__all__ = [
    "StorageCacheException",
    "ConnectionFailed",
    "KeyNotFound",
    "CacheRetrievalException",
    "CacheUpdateException",
    "CacheDeletionException",
    "CacheVerificationException",
    "CacheParameterValidationException",
]
