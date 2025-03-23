from ..utils.safer_serializer import generate_secret_key,safe_pickle_serializer_with_encryption
from urllib.parse import urlparse
from collections import OrderedDict
import hashlib

from typing import Any, Dict, Optional
from urllib.parse import urlparse
from requests import Response

import logging
logger = logging.getLogger(__name__)

class DataCacheManager:
    """
    DataCacheManager class manages caching of API responses.

    This class provides methods to generate cache keys, verify cache entries, check cache validity, 
    update cache with new data, and retrieve data from the cache storage.

    Args:
    - cache_storage: Optional; A dictionary to store cached data. Defaults to an empty dictionary.

    Methods:
    - generate_fallback_cache_key(response): Generates a unique fallback cache key based on the response URL and status code.
    - verify_cache(cache_key): Checks if the provided cache_key exists in the cache storage.
    - cache_is_valid(cache_key, response): Determines whether the cached data for a given key is still valid.
    - update_cache(cache_key, response, store_raw=False, metadata=None, parsed_response=None, processed_response=None): Updates the cache storage with new data.
    - retrieve(cache_key): Retrieves data from the cache storage based on the cache key.
    - retrieve_from_response(response): Retrieves data from the cache storage based on the response if within cache.
    """

    def __init__(self, cache_storage: Optional[Dict[str, Any]] = None) -> None:
        self.cache_storage = cache_storage or {}


    def verify_cache(self, cache_key: str) -> bool:
        """
        Checks if the provided cache_key exists in the cache storage.

        Args:
        - cache_key: A unique identifier for the cached data.

        Returns:
        - bool: True if the cache key exists, False otherwise.
        """
        if cache_key is None:
            logger.info("Cache key is None: No cache lookup was performed.")
            return False
        if cache_key in self.cache_storage:
            logger.info(f"Cache hit for key: {cache_key}")
            return True
        logger.info(f"No cached data for key: '{cache_key}'")
        return False
    
    def cache_is_valid(self, cache_key: str, response: Response) -> bool:
        """
        Determines whether the cached data for a given key is still valid.

        Args:
        - cache_key (str): The unique identifier for cached data.
        - response: The API response used to validate the cache.

        Returns:
        - bool: True if the cache is valid, False otherwise.
        """
        if not self.verify_cache(cache_key):
            return False
        
        cached_response = self.cache_storage.get(cache_key, {})
        current_hash = self.generate_response_hash(response)
        previous_hash = cached_response.get('response_hash')
        
        if current_hash != previous_hash:
            logger.info(f"Cached data is outdated for key: {cache_key}")
            return False
        
        if cached_response.get("processed_response") is None:
            logger.info(f"Previously processed response is missing for recorded cache key: {cache_key}")
            return False
        
        logger.info(f"Cached data is valid for key: {cache_key}")
        return True
        
    def update_cache(
        self,
        cache_key: str,
        response: Response,
        store_raw: bool = False,
        metadata: Optional[Dict[str, Any]] = None,
        parsed_response: Optional[Any] = None,
        processed_response: Optional[Any] = None
    ) -> None:
        """
        Updates the cache storage with new data.

        Args:
        - cache_key: A unique identifier for the cached data.
        - response: The API response object.
        - store_raw: Optional; A boolean indicating whether to store the raw response. Defaults to False.
        - metadata: Optional; Additional metadata associated with the cached data. Defaults to None.
        - parsed_response: Optional; The response data parsed into a structured format. Defaults to None.
        - processed_response: Optional; The response data processed for specific use. Defaults to None.
        """
        self.cache_storage[cache_key] = {
            'response_hash': self.generate_response_hash(response),
            'raw_response': response.content if store_raw else None,
            'parsed_response': parsed_response,
            'processed_response': processed_response,
            'metadata': metadata
        }
        logger.debug(f"Cache updated for key: {cache_key}") 
        
    def retrieve(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves data from the cache storage based on the cache key.

        Args:
        - cache_key: A unique identifier for the cached data.

        Returns:
        - Optional[Dict[str, Any]]: The cached data corresponding to the cache key if found, otherwise None.
        """
        result = self.cache_storage.get(cache_key)
        if result:
            logger.debug(f"Retrieved record for key {cache_key}...")
        else:
            logger.warning(f"Record for key {cache_key} not found...")
        return result
    
    def retrieve_from_response(self, response: Response) -> Optional[Dict[str, Any]]:
        """
        Retrieves data from the cache storage based on the response if within cache.

        Args:
        - response: The API response object.

        Returns:
        - Optional[Dict[str, Any]]: The cached data corresponding to the response if found, otherwise None.
        """
        cache_key = self.generate_fallback_cache_key(response)
        return self.retrieve(cache_key)
    
    @staticmethod
    def generate_response_hash(response: Response) -> str:
        """
        Generates a hash of the response content.

        Args:
        - response: The API response object.

        Returns:
        - str: A SHA-256 hash of the response content.
        """
        return hashlib.sha256(response.content).hexdigest()

    @staticmethod
    def generate_fallback_cache_key(response: Response) -> str:
        """
        Generates a unique fallback cache key based on the response URL and status code.

        Args:
        - response: The API response object.

        Returns:
        - str: A unique fallback cache key.
        """
        parsed_url = urlparse(response.url)
        simplified_url = f"{parsed_url.netloc}{parsed_url.path}"
        status_code = response.status_code
        cache_key = hashlib.sha256(f"{simplified_url}_{status_code}".encode()).hexdigest()
        logger.debug(f"Generated fallback cache key: {cache_key}")
        return cache_key

