import hashlib
import logging
from typing import Any, Dict, Optional, Union
from urllib.parse import urlparse
from requests import Response
import base64
from scholar_flux.data_storage.base import BaseStorage
from scholar_flux.data_storage.null_storage import NullStorage
from scholar_flux.data_storage.in_memory_storage import InMemoryStorage
from scholar_flux.exceptions import RequestFailedException,  StorageCacheException

logger = logging.getLogger(__name__)

class DataCacheManager:
    """
    DataCacheManager class manages caching of API responses.

    This class provides methods to generate cache keys, verify cache entries, check cache validity,
    update cache with new data, and retrieve data from the cache storage.

    Args:
    - cache_storage: Optional; A dictionary to store cached data. Defaults to using In-Memory Storage .

    Methods:
    - generate_fallback_cache_key(response): Generates a unique fallback cache key based on the response URL and status code.
    - verify_cache(cache_key): Checks if the provided cache_key exists in the cache storage.
    - cache_is_valid(cache_key, response): Determines whether the cached data for a given key is still valid.
    - update_cache(cache_key, response, store_raw=False, metadata=None, parsed_response=None, processed_response=None): Updates the cache storage with new data.
    - retrieve(cache_key): Retrieves data from the cache storage based on the cache key.
    - retrieve_from_response(response): Retrieves data from the cache storage based on the response if within cache.
    """

    def __init__(self, cache_storage: Optional[BaseStorage] = None) -> None:
        self.cache_storage: BaseStorage = cache_storage if cache_storage is not None else InMemoryStorage()

    def verify_cache(self, cache_key: Optional[str]) -> bool:
        """
        Checks if the provided cache_key exists in the cache storage.

        Args:
        - cache_key: A unique identifier for the cached data.

        Returns:
        - bool: True if the cache key exists, False otherwise.
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

    @staticmethod
    def _verify_cached_response(cache_key: str,
                                cached_response: Dict[str, Any]) -> bool:
        """ Verifies whether the cache key matches the key from cached_response (if available)
            Note that this method expects that a cache key is provided
        Args:
            cache_key (str): The unique identifier for cached data.
            cached_response: Optional[Dict[str, Any]]: The cached data associated with the key

        Returns:
            bool: True if the cache is valid, False otherwise.
        """

        if not isinstance(cached_response, dict):
            logger.warning(
                f'The provided cached_response is not a dictionary'
            )
            return False

        cached_response_key = cached_response.get('cache_key')
        if not cached_response_key:
            logger.warning(
                f'The provided cached key from the provided cached response (key={cached_response_key}) is empty'
            )
            return False

        if cached_response_key != cache_key:
            logger.warning(
                f'The provided cached response (key={cached_response_key}) is not associated with the provided cache key {cache_key}'
            )
            return False
        return True


    def cache_is_valid(self, cache_key: str, response: Response,
                       cached_response: Optional[Dict[str, Any]] = None) -> bool:
        """
        Determines whether the cached data for a given key is still valid.

        Args:
            cache_key (str): The unique identifier for cached data.
            response: The API response used to validate the cache.
            cached_response: Optional[Dict[str, Any]]: The cached data associated with the key

        Returns:
            bool: True if the cache is valid, False otherwise.
        """
        if not self.verify_cache(cache_key):
            return False

        if cached_response:
            if not self._verify_cached_response(cache_key, cached_response):
                return False
            current_cached_response = cached_response
        else:
            current_cached_response = self.cache_storage.retrieve(cache_key) or {}

        current_hash = self.generate_response_hash(response)
        previous_hash = current_cached_response.get('response_hash')

        if current_hash != previous_hash:
            logger.info(f"Cached data is outdated for key: {cache_key}")
            return False

        if current_cached_response.get("processed_response") is None:
            logger.info(f"Previously processed response is missing for recorded cache key: {cache_key}")
            return False

        logger.info(f"Cached data is valid for key: {cache_key}")
        return True

    def update_cache(
        self,
        cache_key: str,
        response: Response,
        store_raw: bool = False,
        parsed_response: Optional[Any] = None,
        metadata: Optional[Dict[str, Any]] = None,
        extracted_records: Optional[Any] = None,
        processed_response: Optional[Any] = None,
        **kwargs
    ) -> None:
        """
        Updates the cache storage with new data.

        Args:
            cache_key: A unique identifier for the cached data.
            response: The API response object.
            store_raw: Optional; A boolean indicating whether to store the raw response. Defaults to False.
            metadata: Optional; Additional metadata associated with the cached data. Defaults to None.
            parsed_response: Optional; The response data parsed into a structured format. Defaults to None.
            processed_response: Optional; The response data processed for specific use. Defaults to None.
            kwargs: Optional additional hashable dictionary fields that can be stored using sql cattrs encodings or in-memory cache.
        """
        self.cache_storage.update(cache_key,{
            'response_hash': self.generate_response_hash(response),
            'status_code':response.status_code,
            'raw_response': response.content if store_raw else None,
            'parsed_response': parsed_response,
            'extracted_records': extracted_records,
            'processed_response': processed_response,
            'metadata': metadata
        } | dict(**kwargs)
        )

        logger.debug(f"Cache updated for key: {cache_key}")

    def retrieve(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves data from the cache storage based on the cache key.

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
            logger.error(f"Error encountered during attempted retrieval from cache: {e}")
            raise StorageCacheException


    def retrieve_from_response(self, response: Response) -> Optional[Dict[str, Any]]:
        """
        Retrieves data from the cache storage based on the response if within cache.

        Args:
            response: The API response object.

        Returns:
            Optional[Dict[str, Any]]: The cached data corresponding to the response if found, otherwise None.
        """
        cache_key = self.generate_fallback_cache_key(response)
        return self.retrieve(cache_key)

    def delete(self, cache_key: str) -> None:
        """
        Deletes data from the cache storage based on the cache key.

        Args:
            cache_key: A unique identifier for the cached data.

        Returns:
            None: The cached data corresponding to the cache key if found, otherwise None.
        """
        logger.debug(f"deleting the record for cache key: {cache_key}")
        try:
            self.cache_storage.delete(cache_key)
            logger.debug("Cache key deleted successfuly")
        except KeyError:
            logger.warning(f"A record for the cache key: '{cache_key}', did not exist...")


    @staticmethod
    def generate_fallback_cache_key(response: Response) -> str:
        """
        Generates a unique fallback cache key based on the response URL and status code.

        Args:
            response: The API response object.

        Returns:
            str: A unique fallback cache key.
        """
        parsed_url = urlparse(response.url)
        simplified_url = f"{parsed_url.netloc}{parsed_url.path}"
        status_code = response.status_code
        cache_key = hashlib.sha256(f"{simplified_url}_{status_code}".encode()).hexdigest()
        logger.debug(f"Generated fallback cache key: {cache_key}")
        return cache_key

    @staticmethod
    def generate_response_hash(response: Response) -> str:
        """
        Generates a hash of the response content.

        Args:
            response: The API response object.

        Returns:
            str: A SHA-256 hash of the response content.
        """
        return hashlib.sha256(response.content).hexdigest()

    @classmethod
    def null(cls):
        """
        Creates a DataCacheManager using a NullStorage (no storage.

        This storage device has the effect of returning False when validating
        whether the current DataCacheManager is in operation or not

        Returns:
            DataCacheManager: The current class initialized without storage
        """
        return cls(NullStorage())

    def __bool__(self) -> bool:
        """
        This method has the effect of returning 'False' when
        the DataCacheManager class is initialized with NullStorage()
        and will return 'True' otherwise
        """
        return bool(self.cache_storage)

