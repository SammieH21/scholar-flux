# /data_storage/abc_storage.py
"""
The scholar_flux.data_storage.abc_storage module implements the ABCStorage that defines the abstractions that
are to be implemented to create a scholar_flux compatible storage. The ABCStorage defines basic CRUD operations
and convenience methods used to perform operations on the entire range of cached records, or optionally, cached
records specific to a namespace.

scholar_flux implements the ABCStorage with subclasses for SQLite (through SQLAlchemy), Redis, MongoDB, and In-Memory
cache and can be further extended to duckdb and other abstractions supported by SQLAlchemy.
"""
from typing import Any, List, Dict, Optional
from typing_extensions import Self
from abc import ABC, abstractmethod
from scholar_flux.utils.repr_utils import generate_repr

import logging

logger = logging.getLogger(__name__)


class ABCStorage(ABC):
    """
    The ABCStorage class provides the basic structure required to implement
    the data storage cache with customized backend.

    This subclass provides methods to check the cache, delete from the cache,
    update the cache with new data, and retrieve data from the cache storage.
    """

    def __init__(self, *args, **kwargs) -> None:
        """Initializes the current storage implementation"""
        self.namespace: Optional[str] = None

    def _initialize(self, *args, **kwargs) -> None:
        """Optional base method to implement for initializing/reinitializing connections"""
        pass

    def __deepcopy__(self, memo) -> Self:
        """
        Future implementations of ABCStorage devices are unlikely to be deep-copied. This method
        defines the error message that will be used by default upon failures.
        """
        class_name = self.__class__.__name__
        raise NotImplementedError(
            f"{class_name} cannot be deep-copied. Use the .clone() method to create a new instance with "
            "the same configuration."
        )

    @abstractmethod
    def retrieve(self, *args, **kwargs) -> Optional[Any]:
        """Core method for retrieving a page of records from the cache"""
        raise NotImplementedError

    @abstractmethod
    def retrieve_all(self, *args, **kwargs) -> Optional[Dict[str, Any]]:
        """Core method for retrieving all pages of records from the cache"""
        raise NotImplementedError

    @abstractmethod
    def retrieve_keys(self, *args, **kwargs) -> Optional[List[str]]:
        """Core method for retrieving all keys from the cache"""
        raise NotImplementedError

    @abstractmethod
    def update(self, *args, **kwargs) -> None:
        """Core method for updating the cache with new records"""
        raise NotImplementedError

    @abstractmethod
    def delete(self, *args, **kwargs) -> None:
        """Core method for deleting a page from the cache"""
        raise NotImplementedError

    @abstractmethod
    def delete_all(self, *args, **kwargs) -> None:
        """Core method for deleting all pages of records from the cache"""
        raise NotImplementedError

    @abstractmethod
    def verify_cache(self, *args, **kwargs) -> bool:
        """Core method for verifying the cache based on the key"""
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def is_available(cls, *args, **kwargs) -> bool:
        """Core method for verifying whether a storage/service is available"""
        raise NotImplementedError

    @abstractmethod
    def clone(self) -> Self:
        """Helper method for cloning the structure and configuration of future implementations"""
        raise NotImplementedError

    def _prefix(self, key: str) -> str:
        """
        prefixes a namespace to the given `key`:
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
        """Helper method for validating the current namespace key. Raises a KeyError if the key is not a string"""
        if (key is None or key == "") and not required:
            return True

        if key and isinstance(key, str):
            return True

        msg = f"A non-empty namespace string must be provided for the {cls.__name__}. " f"Received {type(key)}"
        logger.error(msg)

        raise KeyError(msg)

    def structure(self, flatten: bool = False, show_value_attributes: bool = True) -> str:
        """
        Helper method for quickly showing a representation of the overall structure of the current storage
        subclass. The instance uses the generate_repr helper function to produce human-readable
        representations of the core structure of the storage subclass with its defaults.

        Returns:
            str: The structure of the current storage subclass as a string.
        """

        return generate_repr(self, flatten=flatten, show_value_attributes=show_value_attributes)

    def __repr__(self) -> str:
        """
        Method for identifying the current implementation and subclasses of the BaseStorage.
        Useful for showing the options being used to store and retrieve data stored as cache.
        """
        return self.structure()


__all__ = ["ABCStorage"]
