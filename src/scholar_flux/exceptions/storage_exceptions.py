## storage_exceptions.py
import logging

logger = logging.getLogger(__name__)


class StorageCacheException(Exception):
    """Base exception for Storage Issuse Issues"""

    pass


class ConnectionFailed(StorageCacheException):
    """Exception arising from storage connection errors"""

    pass


class KeyNotFound(Exception):
    """Exception resulting from a missing or empty key being provided"""

    pass
