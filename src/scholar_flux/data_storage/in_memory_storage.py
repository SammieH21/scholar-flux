from typing import Any, List, Dict, Optional
import logging

logger = logging.getLogger(__name__)
from scholar_flux.data_storage.abc_storage import ABCStorage
from scholar_flux.utils.repr_utils import generate_repr_from_string


class InMemoryStorage(ABCStorage):
    """
    Default storage class that implements in-memory cache using a dictionary.
    This class provides methods to check the cache, delete from the cache,
            update the cache with new data, and retrieve data from the cache storage.

    Args:
        namespace (Optional[str]): Prefix for cache keys. Defaults to None.
        ttl (Optional[int]): Ignored. Included for interface compatibility; not implemented.
        **kwargs (Dict): Ignored. Included for interface compatibility; not implemented.

    """

    def __init__(
        self,
        namespace: Optional[str] = None,
        ttl: Optional[int] = None,
        **memory_config,
    ) -> None:
        """
        Initialize a basic memory_cache using a namespace. Note that ttl and **memory_config
        are provided for interface compatibility and do not affect processing or cache initialization
        """
        self.namespace = namespace

        if ttl is not None:
            logger.warning("TTL is not enforced in InMemoryStorage. Skipping.")
        self.ttl = None

        self._initialize()

    def _initialize(self, **kwargs) -> None:
        """
        Initializes an empty memory cache if kwargs is empty. Otherwise initializes the dictionary
        Starting from the key-value mappings specified as key-value pairs
        """
        logger.debug("Initializing in-memory cache...")
        self.memory_cache: dict = {} | kwargs

    def retrieve(self, key: str) -> Optional[Any]:
        """Attempts to retrieve a response containing the specified cache key within the current namespace"""
        namespace_key = self._prefix(key)
        return self.memory_cache.get(namespace_key)

    def retrieve_all(self) -> Optional[Dict[str, Any]]:
        """Retrieves the full dictionary of all cache key-response mappings found within the current namespace"""
        return {
            k: v
            for k, v in self.memory_cache.items()
            if not self.namespace or k.startswith(self.namespace)
        }

    def retrieve_keys(self) -> Optional[List[str]]:
        """Retrieves the full list of all cache keys found within the current namespace"""
        return [
            key
            for key in self.memory_cache
            if not self.namespace or key.startswith(self.namespace)
        ] or []

    def update(self, key: str, data: Any) -> None:
        """Attempts to update the data associated with a specific cache key in the namespace"""
        namespace_key = self._prefix(key)
        self.memory_cache[namespace_key] = data

    def delete(self, key: str) -> None:
        """Attempts to delete the selected cache key if found within the current namespace"""
        namespace_key = self._prefix(key)
        del self.memory_cache[namespace_key]
        logger.debug(f"Key: {key} deleted successfuly")

    def delete_all(self) -> None:
        """Attempts to delete all cache keys found within the current namespace"""
        logger.debug("deleting all record within cache...")
        try:
            n = len(self.memory_cache)
            if not self.namespace:
                self.memory_cache.clear()
            else:
                filtered_cache = {
                    k: v
                    for k, v in self.memory_cache.items()
                    if not k.startswith(self.namespace)
                }
                self.memory_cache.clear()
                self.memory_cache.update(filtered_cache)

                n -= len(filtered_cache)

            logger.debug(f"Deleted {n} records.")

        except Exception as e:
            logger.warning(f"An error occured deleting e: {e}")

    def verify_cache(self, key: str) -> bool:
        """Verifies whether a cache key can be found under the current namespace"""
        namespace_key = self._prefix(key)
        if not namespace_key:
            raise ValueError(f"Key invalid. Received {key}")
        return namespace_key in self.memory_cache

    def __repr__(self) -> str:
        """
        Helper method for creating an in-memory cache without overloading the repr with the spcifics of
        what is being cached
        """
        class_name = self.__class__.__name__
        str_memory_cache = f"dict(n={len(self.memory_cache)})"
        class_attribute_dict = dict(
            namespace=self.namespace, memory_cache=str_memory_cache
        )
        return generate_repr_from_string(
            class_name, attribute_dict=class_attribute_dict
        )
