# /data_storage/data_cache_manager.py
"""The scholar_flux.data_storage.data_cache_manager implements a DataCacheManager that allows the storage and cached
retrieval of processed responses.

This class is the user-interface that implements a unified interface for different cache storage devices that inherit
from the ABCStorage class.

"""
from __future__ import annotations
import hashlib
import logging
from typing import Any, Dict, Optional, Literal
from urllib.parse import urlparse
from requests import Response
from scholar_flux.data_storage.abc_storage import ABCStorage
from scholar_flux.data_storage.null_storage import NullStorage
from scholar_flux.data_storage.in_memory_storage import InMemoryStorage
from scholar_flux.data_storage.mongodb_storage import MongoDBStorage
from scholar_flux.data_storage.redis_storage import RedisStorage
from scholar_flux.data_storage.sql_storage import SQLAlchemyStorage
from scholar_flux.utils.repr_utils import generate_repr
from scholar_flux.utils.response_protocol import ResponseProtocol
from scholar_flux.exceptions import (
    StorageCacheException,
    MissingResponseException,
    InvalidResponseStructureException,
)
from scholar_flux.package_metadata import __version__
import copy

logger = logging.getLogger(__name__)


class DataCacheManager:
    """DataCacheManager class manages caching of API responses.

    This class provides methods to generate cache keys, verify cache entries, check cache validity,
    update cache with new data, and retrieve data from the cache storage.

    Args:
        - cache_storage: Optional; A dictionary to store cached data. Defaults to using In-Memory Storage .

    Methods:
        - generate_fallback_cache_key(response): Generates a unique fallback cache key based on the response URL and status code.
        - verify_cache(cache_key): Checks if the provided cache_key exists in the cache storage.
        - cache_is_valid(cache_key, response=None, cached_response=None): Determines whether the cached data for a given key is still valid.
        - update_cache(cache_key, response, store_raw=False, metadata=None, parsed_response=None, processed_records=None): Updates the cache storage with new data.
        - retrieve(cache_key): Retrieves data from the cache storage based on the cache key.
        - retrieve_from_response(response): Retrieves data from the cache storage based on the response if within cache.

    Examples:
        >>> from scholar_flux.data_storage import DataCacheManager
        >>> from scholar_flux.api import SearchCoordinator
        # Factory method that creates a default redis connection to the service on localhost if available.
        >>> redis_cache_manager = DataCacheManager.with_storage('redis')
        # Creates a search coordinator for retrieving API responses from the PLOS API provider
        >>> search_coordinator = SearchCoordinator(query = 'Computational Caching Strategies',
                                                   provider_name='plos',
                                                   cache_requests = True, # caches raw requests prior to processing
                                                   cache_manager=redis_cache_manager) # caches response processing
        # Uses the cache manager to temporarily store cached responses for the default duration
        >>> processed_response = search_coordinator.search(page = 1)
        # On the next search, the processed response data can be retrieved directly for later response reconstruction
        >>> retrieved_response_json = search_coordinator.responses.cache.retrieve(processed_response.cache_key)
        # Serialized responses store the core response fields (content, URL, status code) associated with API responses
        >>> assert isinstance(retrieved_response_json, dict) and 'serialized_response' in retrieved_response_json

    """

    def __init__(self, cache_storage: Optional[ABCStorage] = None) -> None:
        """Initializes the DataCacheManager with the selected cache storage."""
        self.cache_storage: ABCStorage = cache_storage if cache_storage is not None else InMemoryStorage()

    def verify_cache(self, cache_key: Optional[str]) -> bool:
        """Checks if the provided cache_key exists in the cache storage.

        Args:
            cache_key: A unique identifier for the cached data.

        Returns:
            bool: True if the cache key exists, False otherwise.

        """
        if cache_key is None:
            logger.warning("Cache key is None: No cache lookup was performed.")
            return False

        # Check if the cache_key is a valid and exists in the storage
        if self.cache_storage.verify_cache(cache_key):
            logger.info(f"Cache hit for key: {cache_key}")
            return True
        logger.info(f"No cached data for key: '{cache_key}'")
        return False

    def cache_is_valid(
        self,
        cache_key: str,
        response: Optional[Response | ResponseProtocol] = None,
        cached_response: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Determines whether the cached data for a given key is still valid or needs reprocessing due to missing fields
        or modified content when checked against the current response.

        If a cached_response dictionary was not directly passed, the cache key will be retrieved from
        storage before comparison.

        Args:
            cache_key (str): The unique identifier for cached data.
            response (Optional[Response | ResponseProtocol]): The API response or response-like object used to validate
                                                              the cache, if available.
            cached_response: Optional[Dict[str, Any]]: The cached data associated with the key

        Returns:
            bool: True if the cache is valid, False otherwise.

        """

        if not cached_response and not self.verify_cache(cache_key):
            return False

        current_cached_response = cached_response or self.retrieve(cache_key) or {}

        if not self._verify_cached_response(cache_key, current_cached_response):
            return False

        if response is not None and not self._verify_hash(response, current_cached_response):
            logger.info(f"Cached data is outdated for key: {cache_key}")
            return False

        logger.info(f"Cached data is valid for key: {cache_key}")
        return True

    def update_cache(
        self,
        cache_key: str,
        response: Response | ResponseProtocol,
        store_raw: bool = False,
        parsed_response: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None,
        extracted_records: Optional[Any] = None,
        processed_records: Optional[Any] = None,
        **kwargs,
    ) -> None:
        """Updates the cache storage with new data.

        Args:
            cache_key: A unique identifier for the cached data.
            response: (requests.Response | ResponseProtocol) The API response or response-like object.
            store_raw: (Optional) A boolean indicating whether to store the raw response. Defaults to False.
            metadata: (Optional) Additional metadata associated with the cached data. Defaults to None.
            parsed_response: (Optional) The response data parsed into a structured format. Defaults to None.
            processed_records: (Optional) The response data processed for specific use. Defaults to None.
            kwargs: Optional additional hashable dictionary fields that can be stored using sql cattrs encodings or in-memory cache.

        """
        self.cache_storage.update(
            cache_key,
            {
                "response_hash": self.generate_response_hash(response),
                "status_code": response.status_code,
                "raw_response": response.content if store_raw else None,
                "parsed_response": parsed_response,
                "extracted_records": extracted_records,
                "processed_records": processed_records,
                "metadata": metadata,
            }
            | dict(**kwargs),
        )

        logger.debug(f"Cache updated for key: {cache_key}")

    def retrieve(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Retrieves data from the cache storage based on the cache key.

        Args:
            cache_key: A unique identifier for the cached data.

        Returns:
            Optional[Dict[str, Any]]: The cached data corresponding to the cache key if found, otherwise None.

        """
        try:
            result = self.cache_storage.retrieve(cache_key) or {}
            if result:
                logger.debug(f"Retrieved record for key {cache_key}...")
            else:
                logger.warning(f"Record for key {cache_key} not found...")
            return result
        except Exception as e:
            msg = f"Error encountered during attempted retrieval from cache: {e}"
            logger.error(msg)
            raise StorageCacheException(msg) from e

    def retrieve_from_response(self, response: Response | ResponseProtocol) -> Optional[Dict[str, Any]]:
        """Retrieves data from the cache storage based on the response if within cache.

        Args:
            response: The API response object.

        Returns:
            Optional[Dict[str, Any]]: The cached data corresponding to the response if found, otherwise None.

        """
        cache_key = self.generate_fallback_cache_key(response)
        return self.retrieve(cache_key)

    def delete(self, cache_key: str) -> None:
        """Deletes data from the cache storage based on the cache key.

        Args:
            cache_key: A unique identifier for the cached data.

        Returns:
            None: The cached data corresponding to the cache key if found, otherwise None.

        """
        logger.debug(f"deleting the record for cache key: {cache_key}")
        try:
            self.cache_storage.delete(cache_key)
            logger.debug("Cache key deleted successfully")
        except KeyError:
            logger.warning(f"A record for the cache key: '{cache_key}', did not exist...")

    @classmethod
    def generate_fallback_cache_key(cls, response: Response | ResponseProtocol) -> str:
        """Generates a unique fallback cache key based on the response URL and status code.

        Args:
            response: The API response object.

        Returns:
            str: A unique fallback cache key.

        """
        if not response:
            msg = "A response or response-like object was expected but was not provided"
            logger.error(msg)
            raise MissingResponseException(msg)

        if not isinstance(response, Response) and not isinstance(response, ResponseProtocol):
            msg = f"A response or response-like object was expected, Received ({type(response)})"
            logger.error(msg)
            raise InvalidResponseStructureException(msg)

        parsed_url = urlparse(response.url)
        simplified_url = f"{parsed_url.netloc}{parsed_url.path}"
        status_code = response.status_code
        cache_key = hashlib.sha256(f"{simplified_url}_{status_code}".encode()).hexdigest()
        logger.debug(f"Generated fallback cache key: {cache_key}")
        return cache_key

    @classmethod
    def generate_response_hash(cls, response: Response | ResponseProtocol) -> str:
        """Generates a hash of the response content.

        Args:
            response: The API response object.

        Returns:
            str: A SHA-256 hash of the response content.

        """
        return hashlib.sha256(response.content).hexdigest()

    @classmethod
    def _verify_cached_response(cls, cache_key: str, cached_response: Dict[str, Any]) -> bool:
        """Verifies whether the cache key matches the key from cached_response (if available)
            Note that this method expects that a cache key is provided
        Args:
            cache_key (str): The unique identifier for cached data.
            cached_response: Optional[Dict[str, Any]]: The cached data associated with the key

        Returns:
            bool: True if the cache is valid, False otherwise.
        """

        if not (cached_response and isinstance(cached_response, dict)):
            logger.warning("The provided cached_response is not a dictionary")
            return False

        cached_response_key = cached_response.get("cache_key")
        if cached_response_key and cached_response_key != cache_key:
            logger.warning(
                f"The provided cached response (key={cached_response_key}) is not associated with the provided cache key {cache_key}"
            )
            return False

        if cached_response.get("processed_records") is None:
            logger.info(f"Previously processed response is missing for recorded cache key: {cache_key}")
            return False

        return True

    @classmethod
    def _verify_hash(cls, response: Response | ResponseProtocol, cached_response: Dict[str, Any]) -> bool:
        """Determines whether the cached data for a given key is still valid and the hashed content hasn't significantly
        changed. If the hash between the current response and cached response_dict has changed, True is returned, and
        False otherwise.

        Args:
            response: The API response or response-like object used to validate the cache.
            cached_response: Optional[Dict[str, Any]]: The cached data associated with the key

        Returns:
            bool: True if the cache is valid, False otherwise.

        """

        current_hash = cls.generate_response_hash(response)
        previous_hash = cached_response.get("response_hash")

        return current_hash == previous_hash

    @classmethod
    def null(cls) -> DataCacheManager:
        """Creates a DataCacheManager using a NullStorage (no storage.

        This storage device has the effect of returning False when validating
        whether the current DataCacheManager is in operation or not

        Returns:
            DataCacheManager: The current class initialized without storage

        """
        return cls(NullStorage())

    @classmethod
    def with_storage(
        cls,
        storage: Optional[
            Literal["redis", "sql", "sqlalchemy", "mongodb", "pymongo", "inmemory", "memory", "null"]
        ] = None,
        *args,
        **kwargs,
    ) -> DataCacheManager:
        """Creates a DataCacheManager using a known storage device.

        This is a convenience function allowing the user to create a DataCacheManager with
        redis, sql, mongodb, or inmemory storage with default settings or through the use of
        optional positional and keyword parameters to initialize the storage as needed.
        Returns:
            DataCacheManager: The current class initialized the chosen storage

        """
        if not isinstance(storage, str):
            raise StorageCacheException(
                "The chosen storage device for caching processed responses is not valid. Expected a valid string"
            )
        match storage.lower():
            case "inmemory" | "memory":
                return cls(InMemoryStorage(*args, **kwargs))
            case "sql" | "sqlalchemy":
                return cls(SQLAlchemyStorage(*args, **kwargs))
            case "mongodb" | "pymongo":
                return cls(MongoDBStorage(*args, **kwargs))
            case "redis":
                return cls(RedisStorage(*args, **kwargs))
            case "null" | None:
                return cls.null()
            case _:
                raise StorageCacheException(
                    "The chosen storage device does not exist. Expected one of the following:"
                    " ['redis', 'sql', 'mongodb', 'inmemory', 'null']"
                )

    def __bool__(self) -> bool:
        """This method has the effect of returning 'False' when the DataCacheManager class is initialized with
        NullStorage() and will return 'True' otherwise."""
        return bool(self.cache_storage)

    def isnull(self) -> bool:
        """Helper method for determining whether the current cache manager uses a null storage."""
        return not self

    @classmethod
    def cache_fingerprint(cls, obj: Optional[str | Any] = None, package_version: Optional[str] = __version__) -> str:
        """This method helps identify changes in class/configuration for later cache retrieval. It generates a unique
        string based on the object and the package version.

        By default, a fingerprint is generated from the current package version and object representation, if provided.
        If otherwise not provided, a new human-readable object representation is generated using the
        `scholar_flux.utils.generate_repr` helper function that represents the object name and its current state. A
        package version is also prepended to the current finger-print if enabled (not None), and can be customized if
        needed for object-specific versioning.

        Args:
            obj (Optional[str]): A finger-printed object, or an object to generate a representation of
            package_version (Optional[str]): The current package version string or manually provided version
                                             for a component).

        Returns:
            str: A human-readable string including the version, object identity

        """

        # coerce provided objects to a string representation if not already. Otherwise generate a new representation
        obj_repr = f"{obj}" if obj and isinstance(obj, str) else generate_repr(obj)

        # Prepend human-readable object representation with the package version or manual versioning, if provided
        return f"{package_version}:{obj_repr}" if package_version is not None else obj_repr

    def structure(self, flatten: bool = False, show_value_attributes: bool = False) -> str:
        """Helper method for quickly showing a representation of the overall structure of the current DataCacheManager.
        The instance uses the generate_repr helper function to produce human-readable representations of the core
        structure of the storage subclass with its defaults.

        Returns:
            str: The structure of the current DataCacheManager as a string.

        """

        return generate_repr(self, flatten=flatten, show_value_attributes=show_value_attributes)

    def __copy__(self) -> DataCacheManager:
        """Helper method for creating a new instance of the current DataCacheManager."""
        cls = self.__class__
        storage = copy.copy(self.cache_storage)
        return cls(cache_storage=storage)

    def clone(self) -> DataCacheManager:
        """Helper method for creating a newly cloned instance of the current DataCacheManager."""
        cls = self.__class__
        storage_cls = self.cache_storage
        return cls(storage_cls.clone())

    def __deepcopy__(self, memo) -> DataCacheManager:
        """Helper method for creating a new DataCacheManager with the same configuration as the original
        DataCacheManager.

        Note that many clients cannot be directly deep-copied, and as a result, this implementation uses `clone` instead
        to create a new instance with a similar configuration. For easier API compatibility

        """
        return self.clone()

    def __repr__(self) -> str:
        """Helper for showing a representation of the current Cache Manager in the form of a string.

        This class will indicate the current cache storage device that is being used for data caching.

        """
        return self.structure()


__all__ = ["DataCacheManager"]
