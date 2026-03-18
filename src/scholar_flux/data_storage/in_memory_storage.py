# /data_storage/in_memory_storage.py
"""The scholar_flux.data_storage.in_memory_storage module implements an InMemoryStorage class that implements a basic
cache storage with an in-memory dictionary.

The InMemoryStorage class implements the basic CRUD operations and convenience methods used to perform operations.

"""

from __future__ import annotations
from typing import Any, Optional
import logging
import threading

logger = logging.getLogger(__name__)
from scholar_flux.data_storage.abc_storage import ABCStorage
from scholar_flux.utils.repr_utils import generate_repr_from_string
from scholar_flux import masker


class InMemoryStorage(ABCStorage):
    """Default storage class that implements an in-memory storage cache using a dictionary.

    This class implements the required abstract methods from the ABCStorage base class to ensure compatibility with
    the scholar_flux.DataCacheManager. Methods are provided to delete from the cache, update the cache with new data,
    and retrieve data from the cache.

    Args:
        namespace (Optional[str]): Prefix for cache keys. Defaults to None.
        ttl (Optional[int]): Ignored. Included for interface compatibility; not implemented.
        **kwargs: Ignored. Included for interface compatibility; not implemented.

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
    STORAGE_TYPE: str = "InMemory"

    def __init__(
        self,
        namespace: Optional[str] = None,
        ttl: Optional[int] = None,
        raise_on_error: Optional[bool] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize a basic, dictionary-like memory_cache using a namespace.

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
        self.config = {}
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

    def _initialize(self, **kwargs: Any) -> None:
        """Initializes an empty memory cache if kwargs is empty.

        Otherwise initializes the dictionary starting from the key-value mappings specified as key-value pairs.

        """
        logger.debug("Initializing in-memory cache...")
        with self.lock:
            self.memory_cache: dict[str, Any] = {} | kwargs

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

    def retrieve_all(self) -> Optional[dict[str, Any]]:
        """Retrieves all cache key-response mappings found within the current namespace.

        Returns:
            dict: A dictionary containing each key-value mapping for all cached data within the same namespace

        """
        with self.lock:
            return {k: v for k, v in self.memory_cache.items() if not self.namespace or k.startswith(self.namespace)}

    def retrieve_keys(self) -> list[str]:
        """Retrieves the full list of all cache keys found within the current namespace.

        Returns:
            list[str]: The full list of all keys that are currently mapped within the storage

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

    def delete(self, key: str) -> Optional[bool]:
        """Attempts to delete the selected cache key if found within the current namespace.

        Args:
            key (str): The key used associated with the stored data from the dictionary cache.

        """
        namespace_key = self._prefix(key)

        with self.lock:
            if namespace_key in self.memory_cache:
                del self.memory_cache[namespace_key]
                logger.debug(f"Key: {key}  (namespace = '{self.namespace}') successfully deleted")
                return True
            logger.info(f"Record for key {key} (namespace = '{self.namespace}') does not exist")
            return False

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
        """Verifies whether a cache key exists within the current namespace in the in-memory cache.

        Args:
            key (str): The key to lookup in the cache

        Returns:
            bool: True if the key is found otherwise False.

        """
        namespace_key = self._prefix(key)
        with self.lock:
            return namespace_key in self.memory_cache

    def verify_connection(self) -> None:
        """No-Op that otherwise raises an error when connections can't be established successfully."""
        pass

    @classmethod
    def is_available(cls, *args: Any, **kwargs: Any) -> bool:
        """Helper method that returns True, indicating that dictionary-based storage will always be available.

        Returns:
            (bool): True to indicate that the dictionary-base cache storage will always be available

        """
        return True

    def structure(self, flatten: bool = False, show_value_attributes: bool = True, mask_values: bool = False) -> str:
        """Creates a concise string representation of the current `InMemoryStorage` device.

        The representation displays the total number of records that have been registered to avoid overloading the
        representation with the specifics of what is being cached.

        Args:
            flatten (bool):
                Flag indicating whether to flatten the string representation of the object into a single line when True
                or preserve the multiline representation of the storage cache when False (default).
            show_value_attributes (bool):
                Flag for hiding the internal attributes of nested objects when True (arguments replaced with `...`) and
                showing their default representation when False (default).
            mask_values (bool):
                Masks any potentially sensitive data shown in the representation when True. This is false by default, as
                the representation of the `InMemoryStorage` displays non-sensitive information, including only the
                namespace of the cache and the total cached record count.

        Returns:
            A basic string representation of the current object.

        """
        class_name = self.__class__.__name__
        str_memory_cache = f"dict(n={len(self.memory_cache)})"
        class_attribute_dict = dict(namespace=self.namespace, memory_cache=str_memory_cache)
        representation = generate_repr_from_string(
            class_name,
            attribute_dict=class_attribute_dict,
            flatten=flatten,
            show_value_attributes=show_value_attributes,
        )

        return masker.mask_text(representation) if mask_values else representation


__all__ = ["InMemoryStorage"]
