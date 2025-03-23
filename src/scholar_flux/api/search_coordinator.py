from typing import List, Dict, Optional, Any
from requests import Response
import time
import logging

from .. import SessionManager
from .retry_handler import RetryHandler
from .. import DataCacheManager
from .. import config
from ..api import SearchAPI, ResponseCoordinator, ResponseValidator
from .. import DataParser, DataExtractor, DataProcessor
from ..exceptions import RequestFailedException, SearchRequestException

logger = logging.getLogger(__name__)

class SearchCoordinator:
    def __init__(self, query: Optional[str] = None,
                 search_api: Optional[SearchAPI] = None,
                 parser: Optional[DataParser] = None,
                 extractor: Optional[DataExtractor] = None,
                 processor: Optional[DataProcessor] = None,
                 cache_manager: Optional[DataCacheManager] = None,
                 cache_results: bool = True,
                 retry_handler: Optional[RetryHandler] = None,
                 base_url: str = config['BASE_URL'],
                 api_key: str = config['SPRINGER_API_KEY'],
                 **kwargs):
        self.api: SearchAPI = search_api or SearchAPI(query=query, base_url=base_url, api_key=api_key, **kwargs)
        self.coord: ResponseCoordinator = ResponseCoordinator(
            parser=parser or DataParser(),
            data_extractor=extractor or DataExtractor(),
            processor=processor or DataProcessor(),
            cache_manager=(cache_manager or DataCacheManager()) if cache_results else None
        )
        self.retry_handler = retry_handler or RetryHandler()
        self.validator = ResponseValidator

    # Search Execution
    def search(self, page=1):
        """Public method to perform a search, specifying the page and records per page."""
        try:
            response = self.fetch(page)
            cache_key = self._create_cache_key(page)
            if getattr(response, 'from_cache', False):
                logger.info(f"Using cached response for cache key: {cache_key}")
            else:
                logger.info(f"Handling response for cache key: {cache_key}")
            processed_response = self.coord.handle_response(response, cache_key)
            return processed_response
        except Exception as e:
            logger.error(f"Error in processing the response: {e}")

    # Request Handling
    def robust_request(self, page, **kwargs):
        """Constructs and sends a request to the Springer API."""
        try:
            response = self.retry_handler.execute_with_retry(
                request_func=self.api.search,
                validator_func=self.validator.validate_response,
                page=page,
                **kwargs
            )
        except RequestFailedException as e:
            logger.error(f"Failed to get a valid response from Springer API: {e}")
            raise
        if getattr(response, 'from_cache', False):
            logger.info(f"Retrieved cached response for query: {self.api.query} and page: {page}")
        return response

    def fetch(self, page, **kwargs):
        """Fetches a response from the Springer API."""
        try:
            response = self.robust_request(page, **kwargs)
            return response
        except Exception as e:
            logger.error(f"Error in fetching response: {e}")
            raise SearchRequestException(f"Error in fetching response: {e}")

    def api_request(self, page: int):
        params = self.api._build_params(page=page)
        request = self.api.prepare_request(params=params)
        return request

    def _get_request_key(self, page: int):
        try:
            request = self.api_request(page)
            request_key = self.api.session.cache.create_key(request)
            return request_key
        except:
            logger.error("Issue retrieving requests-cache key")
            raise ValueError(f"Error retrieving requests-cache key from session: {self.api.session}")

    def _get_cached_request(self, page: int):
        try:
            request_key = self._get_request_key(page)
            return self.api.session.cache.get_response(request_key)
        except Exception as e:
            logger.error(f"Error retrieving cached request: {e}")

    # Cache Management
    def _create_cache_key(self, page):
        """
        Combines information about the query type and current page to create an identifier for the current query.

        Args:
                page (int): The current page number.

        Returns:
        str: A unique cache key based on the provided parameters.
        """
        return f"{self.api.name}_{self.api.query}_{page}_{self.api.records_per_page}"

    def get_cached_response(self, page: int) -> Optional[Dict[str, Any]]:
        """
        Retrieves the cached response for a given page number if available.

        Args:
            page (int): The page number to retrieve from the cache.

        Returns:
            Optional[List[Dict[str, Any]]]: The cached response data if available, otherwise None.
        """
        cache_key = self._create_cache_key(page)
        if self.coord.cache_manager:
            cached_data = self.coord.cache_manager.retrieve(cache_key)
            if cached_data:
                logger.info(f"Retrieved cached data for cache key: {cache_key}")
                return cached_data
        logger.info(f"No cached data found for cache key: {cache_key}")
        return None

    def _delete_cached_request(self, page):
        if self.api.cached:
            try:
                request_key = self._get_request_key(page)
                logger.debug(f"Attempting to delete requests cache key: {request_key}")
                if not self.api.session.cache.contains(request_key):
                    raise KeyError(f"Key {request_key} not found in the API session request cache")
                self.api.session.cache.delete(request_key)
            except Exception as e:
                logger.error(f"Error deleting cached request: {e}")

    def _delete_cached_response(self, page):
        if self.coord.cache_manager:
            try:
                cache_key = self._create_cache_key(page)
                logger.debug(f"Attempting to delete processing cache key: {cache_key}")
                self.coord.cache_manager.delete(cache_key)
            except Exception as e:
                logger.error(f"Error in deleting from processing cache: {e}")

