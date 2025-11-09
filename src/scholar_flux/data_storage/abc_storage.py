# /data_storage/abc_storage.py
"""The scholar_flux.data_storage.abc_storage module implements the ABCStorage that defines the abstractions that are to
be implemented to create a scholar_flux compatible storage. The ABCStorage defines basic CRUD operations and convenience
methods used to perform operations on the entire range of cached records, or optionally, cached records specific to a
namespace.

scholar_flux implements the ABCStorage with subclasses for SQLite (through SQLAlchemy), Redis, MongoDB, and In-Memory
cache and can be further extended to duckdb and other abstractions supported by SQLAlchemy.

"""
from typing import Any, List, Dict, Optional
from typing_extensions import Self, Type
from abc import ABC, abstractmethod
from contextlib import contextmanager
from scholar_flux.utils.repr_utils import generate_repr

import logging

logger = logging.getLogger(__name__)


class ABCStorage(ABC):
    """The ABCStorage class provides the basic structure required to implement the data storage cache with customized
    backend.

    This subclass provides methods to check the cache, delete from the cache, update the cache with new data, and
    retrieve data from the cache storage.

    """

    def __init__(self, *args, **kwargs) -> None:
        """Initializes the current storage implementation."""
        self.namespace: Optional[str] = None
        self.raise_on_error: bool = False

    def _initialize(self, *args, **kwargs) -> None:
        """Optional base method to implement for initializing/reinitializing connections."""
        pass

    def __deepcopy__(self, memo) -> Self:
        """Future implementations of ABCStorage devices are unlikely to be deep-copied.

        This method defines the error message that will be used by default upon failures.

        """
        class_name = self.__class__.__name__
        raise NotImplementedError(
            f"{class_name} cannot be deep-copied. Use the .clone() method to create a new instance with "
            "the same configuration."
        )

    @abstractmethod
    def retrieve(self, *args, **kwargs) -> Optional[Any]:
        """Core method for retrieving a page of records from the cache."""
        raise NotImplementedError

    @abstractmethod
    def retrieve_all(self, *args, **kwargs) -> Optional[Dict[str, Any]]:
        """Core method for retrieving all pages of records from the cache."""
        raise NotImplementedError

    @abstractmethod
    def retrieve_keys(self, *args, **kwargs) -> Optional[List[str]]:
        """Core method for retrieving all keys from the cache."""
        raise NotImplementedError

    @abstractmethod
    def update(self, *args, **kwargs) -> None:
        """Core method for updating the cache with new records."""
        raise NotImplementedError

    @abstractmethod
    def delete(self, *args, **kwargs) -> None:
        """Core method for deleting a page from the cache."""
        raise NotImplementedError

    @abstractmethod
    def delete_all(self, *args, **kwargs) -> None:
        """Core method for deleting all pages of records from the cache."""
        raise NotImplementedError

    @abstractmethod
    def verify_cache(self, *args, **kwargs) -> bool:
        """Core method for verifying the cache based on the key."""
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def is_available(cls, *args, **kwargs) -> bool:
        """Core method for verifying whether a storage/service is available."""
        raise NotImplementedError

    @abstractmethod
    def clone(self) -> Self:
        """Helper method for cloning the structure and configuration of future implementations."""
        raise NotImplementedError

    def _prefix(self, key: str) -> str:
        """prefixes a namespace to the given `key`:

        This method is useful for when you are using a single redis/mongodb server
            and also need to retrieve a subset of articles for a particular task.
        Args:
            key (str) The key to prefix with a namespace (Ex. CORE_PUBLICATIONS)
        Returns:
            str: The cache key prefixed with a namespace (Ex. f'CORE_PUBLICATIONS:{key}')

        """
        if not key:
            raise KeyError(f"No valid value provided for key {key}")
        if not self.namespace:
            return key
        return f"{self.namespace}:{key}" if not key.startswith(f"{self.namespace}:") else key

    @classmethod
    def _validate_prefix(cls, key: Optional[str], required: bool = False) -> bool:
        """Helper method for validating the current namespace key.

        Raises a KeyError if the key is not a string

        """
        if (key is None or key == "") and not required:
            return True

        if key and isinstance(key, str):
            return True

        msg = f"A non-empty namespace string must be provided for the {cls.__name__}. " f"Received {type(key)}"
        logger.error(msg)

        raise KeyError(msg)

    @classmethod
    def _handle_storage_exception(
        cls, exception: BaseException, operation_exception_type: Optional[Type[BaseException]] = None, msg: str = ""
    ) -> None:
        """Helper method for logging errors and raising a new exception if needed.

        Another exception is only raised if `operation_exception_type` is assigned an exception. If `None`,
        an exception is not raised. An error will be logged regardless, however.

        Args:
            exception (BaseException): The exception instance raised from the last storage cache operation
            operation_exception_type (Type[BaseException]): The exception to raise
            msg (str): The error message to log and/or raise.

        """
        error_message = msg or str(exception)
        logger.error(error_message)
        if operation_exception_type is not None:
            raise operation_exception_type(error_message) from exception

    @contextmanager
    def with_raise_on_error(self, value: bool = True):
        """Uses a context manager to temporarily modify the `raise_on_error` attribute for the context duration.

        All storage backends that inherit from the `ABCStorage` will also inherit the `with_raise_on_error` context
        manager. When used, this context manager temporarily sets the `raise_on_error` attribute to True or False for
        the duration of a code block without permanently changing the storage subclass's configuration.

        This context manager is most useful for briefly suppressing errors and in cache verification when errors
        need to be logged and reported instead of silently indicating that a cache entry couldn't be found.

        Args:
            value (bool): A value to temporarily assign to `raise_on_error` for the context duration

        Example:
            >>> with storage.with_raise_on_error(True):
            >>>     # Any storage operation here will raise on error, regardless of the instance default
            >>>     storage.retrieve(key)

        """
        original_value = self.raise_on_error
        self.raise_on_error = value

        try:
            yield
        finally:
            self.raise_on_error = original_value

    def structure(self, flatten: bool = False, show_value_attributes: bool = True) -> str:
        """Helper method for quickly showing a representation of the overall structure of the current storage subclass.
        The instance uses the generate_repr helper function to produce human-readable representations of the core
        structure of the storage subclass with its defaults.

        Returns:
            str: The structure of the current storage subclass as a string.

        """

        return generate_repr(self, flatten=flatten, show_value_attributes=show_value_attributes)

    def __repr__(self) -> str:
        """Method for identifying the current implementation and subclasses of the BaseStorage.

        Useful for showing the options being used to store and retrieve data stored as cache.

        """
        return self.structure()


__all__ = ["ABCStorage"]
