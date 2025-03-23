#from data import DataParser  # Adjust the import path as necessary
#from data import DataProcessor  # Adjust the import path as necessary

#from api import ResponseHandler
#from api import ResponseCoordinator


from collections import OrderedDict
import requests

from ..utils.safer_serializer import safe_pickle_serializer_with_encryption # generate_secret_key,
from ..utils import generate_response_hash
from urllib.parse import urlparse
import hashlib

from typing import Any, Dict, Optional, Union
from requests import Response

import logging
logger = logging.getLogger(__name__)

class BaseCacheManager:
    """
    Manages caching of API responses.
    """

    def __init__(self):
        self.cache_storage = self.initialize_cache()

    def initialize_cache(self) -> Dict[str, Any]:
        raise NotImplementedError("This method should be overridden by subclasses")

    @staticmethod
    def generate_fallback_cache_key(response: Response) -> str:
        """
        Generates a unique fallback cache key based on the response URL and status code.
        
        Args:
            response (Response): The HTTP response object.
        
        Returns:
            str: A unique cache key.
        """
        parsed_url = urlparse(response.url)
        simplified_url = f"{parsed_url.netloc}{parsed_url.path}"
        status_code = response.status_code
        cache_key = hashlib.sha256(f"{simplified_url}_{status_code}".encode()).hexdigest()
        logger.debug(f"Generated fallback cache key: {cache_key}")
        return cache_key

    def verify_cache(self, cache_key: Optional[str]) -> bool:
        """
        Checks if the provided cache_key exists in the cache storage.
        
        Args:
            cache_key (Optional[str]): The cache key to verify.
        
        Returns:
            bool: True if the cache key exists, False otherwise.
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
            cache_key (str): The unique identifier for cached data.
            response (Response): The API response used to validate the cache.
        
        Returns:
            bool: True if the cache is valid, False otherwise.
        """
        if not self.verify_cache(cache_key):
            return False
        
        cached_response = self.cache_storage.get(cache_key, {})
        current_hash = generate_response_hash(response)
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
        parsed_response: Optional[Union[Dict[str, Any], Any]] = None,
        processed_response: Optional[Union[Dict[str, Any], Any]] = None
    ) -> None:
        """
        Updates the cache storage with new data.
        
        Args:
            cache_key (str): The unique identifier for cached data.
            response (Response): The HTTP response to cache.
            store_raw (bool): Whether to store the raw response.
            metadata (Optional[Dict[str, Any]]): Additional metadata to store.
            parsed_response (Optional[Union[Dict[str, Any], Any]]): The parsed response data.
            processed_response (Optional[Union[Dict[str, Any], Any]]): The processed response data.
        """
        cache_data = {
            'response_hash': generate_response_hash(response),
            'raw_response': response if store_raw else None,
            'parsed_response': parsed_response,
            'processed_response': processed_response,
            'metadata': metadata
        }
        self.cache_storage[cache_key] = cache_data
        logger.debug(f"Cache updated for key: {cache_key}")

#    @staticmethod
#    def add_cache(cash_key,cache_data,name_space=''):
#        nm = name_space if name_space is not None or self.name_space
#        fnm
#        self.session

    def retrieve(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """
        Selects from the cache storage based on key.
        
        Args:
            cache_key (str): The unique identifier for cached data.
        
        Returns:
            Optional[Dict[str, Any]]: The cached data if found, else None.
        """
        result = self.cache_storage.get(cache_key)
        if result:
            logger.debug(f"Retrieved record for key {cache_key}...")
            return result
        else:
            logger.warning(f"Record for key {cache_key} not found...")
        return result

    def retrieve_from_response(self, response: Response) -> Optional[Dict[str, Any]]:
        """
        Selects from the cache storage based on response if within cache.
        
        Args:
            response (Response): The HTTP response to use for generating the cache key.
        
        Returns:
            Optional[Dict[str, Any]]: The cached data if found, else None.
        """
        cache_key = self.generate_fallback_cache_key(response)
        return self.retrieve(cache_key)


class InMemoryCacheManager(BaseCacheManager):
    def initialize_cache(self) -> Dict[str, Any]:
        return {}


try:
    
    from redis import Redis
    from requests_cache import CachedSession, RedisCache
    #from requests_cache.backends.redis import RedisHashDict
    class RedisCacheManager(BaseCacheManager):
        def initialize_cache(self,redis_port=6379) -> Dict[str, Any]:
            redis_connection = Redis(host='localhost', port=6379)
            self.secret=generate_secret_key()
            self.serializer=safe_pickle_serializer_with_encryption(self.secret)
            self.session = CachedSession(backend=RedisCache(connection=redis_connection,serializer=self.serializer))

            return self.session.cache.responses

except ImportError:
    RedisCacheManager = None


# Example usage
if __name__ == "__main__":
    import requests

    cache_manager = RedisCacheManager() if RedisCacheManager else InMemoryCacheManager()

    response = cache_manager.session.get("https://requests-cache.readthedocs.io/en/stable/modules/requests_cache.backends.redis.html#requests_cache.backends.redis.RedisHashDict")
    cache_key = cache_manager.generate_fallback_cache_key(response)
    
    if not cache_manager.verify_cache(cache_key):
        cache_manager.update_cache(cache_key, response, store_raw=True)
    else:
        cached_data = cache_manager.retrieve(cache_key)
        print(cached_data)






#########################################
import logging
logger = logging.getLogger(__name__)

class ProcessingCacheManager:
    """
    Summary:
    ProcessingCacheManager class manages caching of API responses.

    Explanation:
    This class provides methods to generate cache keys, verify cache entries, check cache validity, update cache with new data, and retrieve data from the cache storage.

    Args:
    - cache_key: A unique identifier for the cached data.
    - response: The API response object.
    - store_raw: A boolean indicating whether to store the raw response.
    - metadata: Additional metadata associated with the cached data.
    - parsed_response: The response data parsed into a structured format.
    - processed_response: The response data processed for specific use.

    Returns:
    - cache_key: A unique identifier for the cached data.
    - result: The cached data corresponding to the cache key.
    """
    def __init__(self,cache_storage=None):
        self.cache_storage = cache_storage or {}
    
    @staticmethod
    def generate_fallback_cache_key(response):
        """
        Generates a unique fallback cache key based on the response URL and status code.
        """
        parsed_url = urlparse(response.url)
        simplified_url = f"{parsed_url.netloc}{parsed_url.path}"
        status_code = response.status_code
        cache_key = hashlib.sha256(f"{simplified_url}_{status_code}".encode()).hexdigest()
        logger.debug(f"Generated fallback cache key: {cache_key}")
        return cache_key

    def verify_cache(self, cache_key):
        """
        Checks if the provided cache_key exists in the cache storage.
        """
        if cache_key is None:
            logger.info("Cache key is None: No cache lookup was performed.")
            return False
        if cache_key in self.cache_storage:
            logger.info(f"Cache hit for key: {cache_key}")
            return True
        logger.info(f"No cached data for key: '{cache_key}'")
        return False
    
    def cache_is_valid(self,cache_key,response):
        """
        Determines whether the cached data for a given key is still valid.
        
        Args:
            cache_key (str): The unique identifier for cached data.
            response: The API response used to validate the cache.

        Returns:
            bool: True if the cache is valid, False otherwise.  
        """
        if not self.verify_cache(cache_key):
            return False
        
        cached_response = self.cache_storage.get(cache_key, {})
        current_hash = generate_response_hash(response)
        previous_hash = cached_response.get('response_hash')
        
        if current_hash != previous_hash:
            logger.info(f"Cached data is outdated for key: {cache_key}")
            return False
        
        if cached_response.get("processed_response") is None:
            logger.info(f"Previously processed response is missing for recorded cache key: {cache_key}")
            return False
        
        logger.info(f"Cached data is valid for key: {cache_key}")
        return True
        
    def update_cache(self, cache_key, response, store_raw=False, metadata=None, parsed_response=None, processed_response=None):
        """Updates the cache storage with new data."""
        self.cache_storage[cache_key] = {
            'response_hash': generate_response_hash(response),
            'raw_response': response if store_raw else None,
            'parsed_response': parsed_response,
            'processed_response': processed_response,
            'metadata':metadata
        }
        logger.debug(f"Cache updated for key: {cache_key}") 
        
    def retrieve(self, cache_key):
        """Selects from the cache storage based on key."""
        result=self.cache_storage.get(cache_key)
        if result:
            logger.debug(f"Retrieved record for key {cache_key}...")
        else:
            logger.warning(f"Record for key {cache_key} not found...")
        return result
    
    def retrieve_from_response(self, response):
        """Selects from the cache storage based on response if within cache."""
        cache_key=self.generate_fallback_cache_key(response)
        return self.retrieve(cache_key)
        
        
        

# Example usage:
# cache_manager = ProcessingCacheManager()
# response = requests.get("some_url")
# if validator.validate_response(response):
#     cache_key = cache_manager.generate_fallback_cache_key(response)
#     if not cache_manager.verify_cache(cache_key, some_cache_storage):
#         # Proceed with processing the response
#     else:
#         # Use cached data
