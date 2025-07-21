from typing import List, Dict, Optional, Any, Tuple
from requests import PreparedRequest, Response
import time
import logging

from scholar_flux import SessionManager
from scholar_flux.api.retry_handler import RetryHandler
from scholar_flux import DataCacheManager
from scholar_flux import config
from scholar_flux.api import SearchAPI, ResponseCoordinator, ResponseValidator, ProcessedResponse
from scholar_flux.data import DataParser, DataExtractor, BaseDataProcessor, DataProcessor, RecursiveDataProcessor, PathDataProcessor
from scholar_flux.exceptions import RequestFailedException, RequestCacheException, StorageCacheException, APIParameterException

logger = logging.getLogger(__name__)

class SearchCoordinator:
    """
    High-level coordinator for requesting and retrieving records and metadata
    from APIs.

    This class uses dependency injection to orchestrate the process of constructing requests,
    validating response, and processing scientific works and articles. This class is designed
    to abstract away the complexity of using APIs while providing a consistent and
    robust interface for retrieving record data and metadata from request and storage cache
    if valid to help avoid exceeding limits in API requests.
    """
    def __init__(self,
                 search_api: Optional[SearchAPI] = None,
                 parser: Optional[DataParser] = None,
                 extractor: Optional[DataExtractor] = None,
                 processor: Optional[BaseDataProcessor] = None,
                 cache_manager: Optional[DataCacheManager] = None,
                 cache_results: bool = True,
                 query: Optional[str] = None,
                 retry_handler: Optional[RetryHandler] = None,
                 validator: Optional[ResponseValidator] = None,
                 **kwargs):

        if query is None and not search_api:
            raise ValueError("Either 'query' or 'search_api' must be provided.")



        self.api: SearchAPI = search_api or SearchAPI.from_defaults(query if isinstance(query, str) else '',
                                                                    provider_name='plos',
                                                                    **kwargs)

        if not cache_results:
            cache = DataCacheManager.null()
        else:
            cache = cache_manager or DataCacheManager()

        self.coord: ResponseCoordinator = ResponseCoordinator(
            parser=parser or DataParser(),
            data_extractor=extractor or DataExtractor(),
            processor=processor or PathDataProcessor(),
            cache_manager=cache
        )
        self.retry_handler = retry_handler or RetryHandler()
        self.validator = validator or ResponseValidator()

        self.last_response: Optional[ProcessedResponse] = None

    # Search Execution
    def search(self,
               page: int = 1,
               from_request_cache: bool= True,
               from_process_cache: bool= True
              ) -> Optional[ProcessedResponse]:
        """
        Public method for retrieving and processing records
        from the API specifying the page and records per page.
        Note that the response object is saved under the
        last_response attribute in the event that the
        data is processed successfully, irrespective of
        whether responses are cached or not.

        Args:
            page (int): The current page number.
            from_request_cache (bool): This parameter determines whether to try to retrieve
                                       the response from the requests-cache storage
            from_process_cache (bool): This parameter determines whether to attempt to pull
                                       processed responses from the cache storage
        Returns:
            Optional[ProcessedResponse]: A response data class containing processed
                                         article data (data), and metadata
        """
        try:
            response, cache_key = self._search(page,from_request_cache=from_request_cache)
            self._log_response_source(response, page, cache_key)

            if response:
                processed_response = self.coord.handle_response(response,
                                                                cache_key,
                                                                from_cache = from_process_cache)
                if processed_response.data:
                    self.last_response = processed_response

                return processed_response

        except Exception as e:
            logger.error(f"An unexpected error occurred when processing the response: {e}")
        return None

    def search_data(self,
                    page: int = 1,
                    from_request_cache: bool= True,
                    from_process_cache: bool= True
                   ) -> Optional[List[Dict]]:
        """
        Public method to perform a search, specifying the page and records per page.
        Note that instead of returning a ProcessedResponse, this calls the search_data method
        and only retrieves the list of processed records from the ProcessedResponse

        Args:
            page (int): The current page number.
            from_request_cache (bool): This parameter determines whether to try to retrieve
                                       the response from the requests-cache storage
            from_process_cache (bool): This parameter determines whether to attempt to pull
                                       processed responses from the cache storage

        Returns:
            Optional[List[Dict]]: A List of records containing processed article data
        """
        try:
            response = self.search(page,
                                   from_request_cache=from_request_cache,
                                   from_process_cache=from_process_cache
                                  )
            if response:
                return response.data

        except Exception as e:
            logger.error(f"An unexpected error occurred when attempting to retrieve the processsed response data: {e}")
        return None

    # Request Handling
    def fetch(self, page: int,
              from_request_cache: bool= True,
              **kwargs) -> Optional[Response]:
        """
        Fetches the raw response from the current API.

        Args:
            page (int): The page number to retrieve from the cache.
            from_request_cache (bool): This parameter determines whether to
                                       try to fetch from cache

        Returns:
            Optional[Response]: The response object if available, otherwise None.
        """
        try:

            if from_request_cache:
                # attempts to retrieve the cached request associated with the page
                if response:=self.get_cached_request(page, **kwargs):
                    return response
            else:
                # if the key does not exist, will log at the INFO level and continue
                self._delete_cached_request(page, **kwargs)

            response = self.robust_request(page, **kwargs)
            return response
        except RequestFailedException as e:
            logger.warning(f"Failed to fetch page {page}: {e}")
        return None

    def robust_request(self, page: int, **kwargs) -> Optional[Response]:
        """Constructs and sends a request to the current API.
        Fetches a response from the current API.

        Args:
            page (int): The page number to retrieve from the cache.
            **kwargs: Optional Additional parameters to pass to the
        Returns:
            Optional[Response]: The request object if available, otherwise None.
        """

        try:
            response = self.retry_handler.execute_with_retry(
                request_func=self.api.search,
                validator_func=self.validator.validate_response,
                page=page,
                **kwargs
            )

        except RequestFailedException as e:
            logger.error(f"Failed to get a valid response from the {self.api.name} API: {e}")
            raise

        if getattr(response, 'from_cache', False):
            logger.info(f"Retrieved cached response for query: {self.api.query} and page: {page}")
        return response

    def get_cached_request(self, page: int, **kwargs) -> Optional[Response]:
        """
        Retrieves the cached request for a given page number if available.
        Args:
            page (int): The page number to retrieve from the cache.
        Returns:
            Optional[Response]: The cached request object if available, otherwise None.
        """
        try:
            if not self.api.cache:
                return None
            request_key = self._get_request_key(page, **kwargs)
            if not request_key:
                return None
            return self.api.cache.get_response(request_key)

        except RequestCacheException as e:
            logger.error(f"Error retrieving cached request: {e}")
            return None

    def get_cached_response(self, page: int) -> Optional[Dict[str, Any]]:
        """
        Retrieves the cached response for a given page number if available.

        Args:
            page (int): The page number to retrieve from the cache.

        Returns:
            Optional[Dict[str, Any]]: The cached response data if available, otherwise None.
        """
        try:
            if not self.coord.cache_manager:
                return None
            cache_key = self._create_cache_key(page)
            cached = self.coord.cache_manager.retrieve(cache_key)
            if cached:
                logger.info(f"Cache hit for key: {cache_key}")
                return cached
            logger.info(f"Cache miss for key: {cache_key}")
            return None
        except StorageCacheException as e:
            logger.error(f"Error retrieving cached response: {e}")
            return None

    def _search(self, page: int, from_request_cache: bool= True) -> Tuple[Optional[Response], str]:
        """Helper method for fetching the response and retrieving the cache key.
        Args:
            page (int): The page number to retrieve from the cache.
        Returns:
            Tuple[Optional[Response], str]: A tuple containing The request object
                                            if available and its cache key
        """
        response = self.fetch(page, from_request_cache = from_request_cache)
        cache_key = self._create_cache_key(page)

        if response is None:
            logger.info("Response retrieval for cache key {cache_key} was unsuccessful.")
        return response, cache_key

    def _log_response_source(self, response: Optional[Response], page: int, cache_key: Optional[str]) -> None:
        """
        Logs and indicates whether the response originated from a
        requests-cache session or was retrieved directly from the current API.
        Also indicates whether we're using a cache key to attempt to pull from
        cache if available.

        Args:
            response (Response): Response retrieved from a request.
            page (int): The current page number.
            cache_key: The an optional cache key associated with the current request.
        """

        if not response:
            logger.warning(f'Response retrieval and processing for page {page} was unsuccessful.')
            return

        if getattr(response, 'from_cache', False):
            logger.info(f"Retrieved a cached response for cache key: {cache_key}" )

        if self.coord.cache_manager:
            logger.info(f"Handling response (cache key: {cache_key})")
        else:
            logger.info(f"Handling response")

    def _prepare_request(self, page: int, **kwargs) -> PreparedRequest:
        """
        Prepares the request after constructing the request parameters for the API call.
        Args:
            page (int): The page number to request.
            **kwargs: Additional parameters for the request.
        Returns:
            PreparedRequest: The prepared request object to send to the api
        """

        params = self.api.build_params(page=page, **kwargs)
        request = self.api.prepare_request(self.api.base_url,
                                           params=params)
        return request


    # Cache Management
    def _create_cache_key(self, page: int) -> str:
        """
        Combines information about the query type and current page to create an identifier for the current query.

        Args:
            page (int): The current page number.

        Returns:
            str: A unique cache key based on the provided parameters.
        """
        return f"{self.api.name}_{self.api.query}_{page}_{self.api.records_per_page}"

    def _get_request_key(self, page: int, **kwargs) -> Optional[str]:
        """
        Creates a request key from the requests session cache if available
        Args:
            page (int): The page number associated with the request key.
            **kwargs: Additional parameters for the request.
        Returns:
            str: The prepared request key to be associated with the request
        """

        try:
            if self.api.cache:
                request = self._prepare_request(page, **kwargs)
                request_key = self.api.cache.create_key(request)
                return request_key
        except (APIParameterException, AttributeError, ValueError) as e:
            logger.error("Error retrieving requests-cache key")
            raise RequestCacheException(f"Error retrieving requests-cache key from session: {self.api.session}: {e}")
        return None

    def _delete_cached_request(self, page: int, **kwargs) -> None:
        """
        Deletes the cached request for a given page number if available.
        Args:
            page (int): The page number to delete from the cache.
        """
        if self.api.cache:
            try:
                request_key = self._get_request_key(page,**kwargs)
                logger.debug(f"Attempting to delete requests cache key: {request_key}")
                if not request_key:
                    raise KeyError("Request key is None or empty")

                if not self.api.cache.contains(request_key):
                    raise KeyError(f"Key {request_key} not found in the API session request cache")

                self.api.cache.delete(request_key)

            except KeyError:
                logger.info("A cached response for the current request does not exist.")

            except Exception as e:
                logger.error(f"Error deleting cached request: {e}")

    def _delete_cached_response(self, page: int) -> None:
        """
        Deletes the cached response for a given page number if available.
        Args:
            page (int): The page number to delete from the cache.
        """
        if self.coord.cache_manager:
            try:
                cache_key = self._create_cache_key(page)
                logger.debug(f"Attempting to delete processing cache key: {cache_key}")
                self.coord.cache_manager.delete(cache_key)
            except Exception as e:
                logger.error(f"Error in deleting from processing cache: {e}")

