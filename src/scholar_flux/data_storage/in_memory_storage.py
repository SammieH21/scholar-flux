# /data_storage/in_memory_storage.py
"""The scholar_flux.data_storage.in_memory_storage module implements an InMemoryStorage class that implements a basic
cache storage with an in-memory dictionary.

The InMemoryStorage class implements the basic CRUD operations and convenience methods used to perform operations.

"""

from __future__ import annotations
from typing import Any, List, Dict, Optional
import logging
import threading

logger = logging.getLogger(__name__)
from scholar_flux.data_storage.abc_storage import ABCStorage
from scholar_flux.utils.repr_utils import generate_repr_from_string


class InMemoryStorage(ABCStorage):
    """Default storage class that implements an in-memory storage cache using a dictionary.

    This class implements the required abstract methods from the ABCStorage base class to ensure compatibility with
    the scholar_flux.DataCacheManager. Methods are provided to delete from the cache, update the cache with new data,
    and retrieve data from the cache.

    Args:
        namespace (Optional[str]): Prefix for cache keys. Defaults to None.
        ttl (Optional[int]): Ignored. Included for interface compatibility; not implemented.
        **kwargs (Dict): Ignored. Included for interface compatibility; not implemented.

    Examples:
        >>> from scholar_flux.data_storage import InMemoryStorage
        ### defaults to a basic dictionary:
        >>> memory_storage = InMemoryStorage(namespace='testing_functionality')
        >>> print(memory_storage)
        # OUTPUT: InMemoryStorage(...)
        ### Adding records to the storage
        >>> memory_storage.update('record_page_1', {'id':52, 'article': 'A name to remember'})
        >>> memory_storage.update('record_page_2', {'id':55, 'article': 'A name can have many meanings'})
        ### Revising and overwriting a record
        >>> memory_storage.update('record_page_2', {'id':53, 'article': 'A name has many meanings'})
        >>> memory_storage.retrieve_keys() # retrieves all current keys stored in the cache under the namespace
        # OUTPUT: ['testing_functionality:record_page_1', 'testing_functionality:record_page_2']
        >>> memory_storage.retrieve_all() # Will also be empty
        # OUTPUT: {'testing_functionality:record_page_1': {'id': 52,
        #           'article': 'A name to remember'},
        #          'testing_functionality:record_page_2': {'id': 53,
        #           'article': 'A name has many meanings'}}
        >>> memory_storage.retrieve('record_page_1') # retrieves the record for page 1
        # OUTPUT: {'id': 52, 'article': 'A name to remember'}
        >>> memory_storage.delete_all() # deletes all records from the namespace
        >>> memory_storage.retrieve_keys() # Will now be empty
        >>> memory_storage.retrieve_all() # Will also be empty

    """

    # for compatibility with other storage backends
    DEFAULT_NAMESPACE: Optional[str] = None
    DEFAULT_RAISE_ON_ERROR: bool = False

    def __init__(
        self,
        namespace: Optional[str] = None,
        ttl: Optional[int] = None,
        raise_on_error: Optional[bool] = None,
        **kwargs,
    ) -> None:
        """Initialize a basic, dictionary-like  memory_cache using a namespace.

        Note that `ttl` and `**kwargs` are provided for interface compatibility, and specifying any of these as
        arguments will not affect processing or cache initialization.

        """
        self.namespace = namespace if namespace is not None else self.DEFAULT_NAMESPACE

        if ttl is not None:
            logger.warning("The parameter, `ttl` is not enforced in InMemoryStorage. Skipping.")
        if raise_on_error is not None:
            logger.warning("The parameter, `raise_on_error` is not enforced in InMemoryStorage. Skipping.")
        self.ttl = None
        self.raise_on_error = False
        self.lock = threading.Lock()

        self._validate_prefix(namespace, required=False)
        self._initialize()

    def clone(self) -> InMemoryStorage:
        """Helper method for creating a new InMemoryStorage with the same configuration."""
        cls = self.__class__
        storage = cls(namespace=self.namespace)
        with self.lock:
            storage.memory_cache = self.memory_cache.copy()
        return storage

    def _initialize(self, **kwargs) -> None:
        """Initializes an empty memory cache if kwargs is empty.

        Otherwise initializes the dictionary Starting from the key-value mappings specified as key-value pairs.

        """
        logger.debug("Initializing in-memory cache...")
        with self.lock:
            self.memory_cache: dict = {} | kwargs

    def retrieve(self, key: str) -> Optional[Any]:
        """Attempts to retrieve a response containing the specified cache key within the current namespace.

        Args:
            key (str): The key used to fetch the stored data from cache.

        Returns:
            Any: The value returned is deserialized JSON object if successful. Returns None if the key does not exist.

        """
        namespace_key = self._prefix(key)
        with self.lock:
            return self.memory_cache.get(namespace_key)

    def retrieve_all(self) -> Optional[Dict[str, Any]]:
        """Retrieves all cache key-response mappings found within the current namespace.

        Returns:
            A dictionary containing each key-value mapping for all cached data within the same namespace

        """
        with self.lock:
            return {k: v for k, v in self.memory_cache.items() if not self.namespace or k.startswith(self.namespace)}

    def retrieve_keys(self) -> Optional[List[str]]:
        """Retrieves the full list of all cache keys found within the current namespace.

        Returns:
            List[str]: The full list of all keys that are currently mapped within the storage

        """
        with self.lock:
            return [key for key in self.memory_cache if not self.namespace or key.startswith(self.namespace)] or []

    def update(self, key: str, data: Any) -> None:
        """Attempts to update the data associated with a specific cache key in the namespace.

        Args:
            key (str): The key of the key-value pair
            data (Any): The data to be associated with the key

        """
        namespace_key = self._prefix(key)
        with self.lock:
            self.memory_cache[namespace_key] = data

    def delete(self, key: str) -> None:
        """Attempts to delete the selected cache key if found within the current namespace.

        Args:
            key (str): The key used associated with the stored data from the dictionary cache.

        """
        namespace_key = self._prefix(key)

        with self.lock:
            key = self.memory_cache.pop(namespace_key, None)

        if key is not None:
            logger.debug(f"Key: {key} deleted successfully")
        else:
            logger.info(f"Key: {key}  (namespace = '{self.namespace}') does not exist in cache.")

    def delete_all(self) -> None:
        """Attempts to delete all cache keys found within the current namespace."""
        logger.debug("deleting all record within cache...")
        try:
            with self.lock:
                n = len(self.memory_cache)
                if not self.namespace:
                    self.memory_cache.clear()
                else:
                    filtered_cache = {k: v for k, v in self.memory_cache.items() if not k.startswith(self.namespace)}
                    self.memory_cache.clear()
                    self.memory_cache.update(filtered_cache)

                    n -= len(filtered_cache)

            logger.debug(f"Deleted {n} records.")

        except Exception as e:
            logger.warning(f"An error occurred deleting e: {e}")

    def verify_cache(self, key: str) -> bool:
        """Verifies whether a cache key exists the current namespace in the in-memory cache.

        Args:
            key (str): The key to lookup in the cache

        Returns:
            bool: True if the key is found otherwise False.

        """
        namespace_key = self._prefix(key)
        with self.lock:
            return namespace_key in self.memory_cache

    @classmethod
    def is_available(cls, *args, **kwargs) -> bool:
        """Helper method that returns True, indicating that dictionary-based storage will always be available.

        Returns:
            (bool): True to indicate that the dictionary-base cache storage will always be available

        """
        return True

    def structure(self, flatten: bool = False, show_value_attributes: bool = True) -> str:
        """Helper method for creating an in-memory cache without overloading the representation with the specifics of
        what is being cached."""
        class_name = self.__class__.__name__
        str_memory_cache = f"dict(n={len(self.memory_cache)})"
        class_attribute_dict = dict(namespace=self.namespace, memory_cache=str_memory_cache)
        return generate_repr_from_string(
            class_name,
            attribute_dict=class_attribute_dict,
            flatten=flatten,
            show_value_attributes=show_value_attributes,
        )


__all__ = ["InMemoryStorage"]
