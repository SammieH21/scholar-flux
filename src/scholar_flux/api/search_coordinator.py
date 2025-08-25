from typing import List, Dict, Optional, Any, Tuple
from requests import PreparedRequest, Response
import logging

from scholar_flux.api.retry_handler import RetryHandler
from scholar_flux import DataCacheManager
from scholar_flux.api import SearchAPI, ResponseCoordinator, ResponseValidator, ProcessedResponse, ErrorResponse
from scholar_flux.api.models import ResponseResult
from scholar_flux.data import (BaseDataParser, DataParser, BaseDataExtractor,
                               DataExtractor, ABCDataProcessor,
                               PathDataProcessor)
from scholar_flux.data_storage import NullStorage
from scholar_flux.exceptions import (RequestFailedException, RequestCacheException, StorageCacheException,
                                     APIParameterException, InvalidCoordinatorParameterException)
from scholar_flux.api import BaseCoordinator
from scholar_flux.api.workflows import WORKFLOW_DEFAULTS, SearchWorkflow
logger = logging.getLogger(__name__)

class SearchCoordinator(BaseCoordinator):
    """
    High-level coordinator for requesting and retrieving records and metadata
    from APIs.

    This class uses dependency injection to orchestrate the process of constructing requests,
    validating response, and processing scientific works and articles. This class is designed
    to abstract away the complexity of using APIs while providing a consistent and
    robust interface for retrieving record data and metadata from request and storage cache
    if valid to help avoid exceeding limits in API requests.

    If no search_api is provided, the coordinator will create a Search API that uses the default
    provider if the environment variable, `DEFAULT_SCHOLAR_FLUX_PROVIDER`is not provided.
    Otherwise PLOS is used on the backend.
    """
    def __init__(self,
                 search_api: Optional[SearchAPI] = None,
                 parser: Optional[BaseDataParser] = None,
                 extractor: Optional[BaseDataExtractor] = None,
                 processor: Optional[ABCDataProcessor] = None,
                 cache_manager: Optional[DataCacheManager] = None,
                 cache_requests: Optional[bool] = None,
                 cache_results: Optional[bool] = None,
                 query: Optional[str] = None,
                 retry_handler: Optional[RetryHandler] = None,
                 validator: Optional[ResponseValidator] = None,
                 workflow: Optional[SearchWorkflow] = None, # updating workflow with a workflow method by default
                 **kwargs):

        if query is None and not search_api:
            raise InvalidCoordinatorParameterException("Either 'query' or 'search_api' must be provided.")



        provider_name = kwargs.pop('provider_name', None)

        # create the Search API if it doesn't already exist
        api: SearchAPI = search_api or SearchAPI.from_defaults(query if isinstance(query, str) else '',
                                                               provider_name = provider_name,
                                                               use_cache = cache_requests or False,
                                                               **kwargs)

        # modify the query if the API key initially existed and a query was also provided
        if search_api and query:
            api.query = query

        # modify the session object if the API originally existed and we want to enable/disable request caching:
        if search_api and cache_requests is not None:
            api.configure_session(api.session, use_cache = cache_requests)

        # caching is enabled if the cache_results is selected and caching was not previously turned on.
        # Otherwise, caching is turned off using a No-Op cache manager
        if cache_results is False:
            cache = DataCacheManager.null() # is falsy and a no-op cache manager
        else:
            # create a cache manager if it doesn't already exist. Ensures cache is an actual Cache Manager
            cache = cache_manager if cache_manager is not None else DataCacheManager()
            # at this point the cache is created but is falsy if using a null cache manager
            # keep the null cache manager if the parameter is not explicitly set to True
            cache = (DataCacheManager()
                     if isinstance(cache, DataCacheManager)
                     and isinstance(cache.cache_storage, NullStorage)
                     and cache_results is True
                     else cache)

        # create a response coordinator using the previously created configuration
        response_coordinator: ResponseCoordinator = ResponseCoordinator(
            parser=parser or DataParser(),
            data_extractor=extractor or DataExtractor(),
            processor=processor or PathDataProcessor(),
            cache_manager=cache
        )

        super().__init__(api, response_coordinator)
        self.retry_handler = retry_handler or RetryHandler()
        self.validator = validator or ResponseValidator()
        self.workflow = workflow or WORKFLOW_DEFAULTS.get(self.api.provider_name)

        self.last_response: Optional[ResponseResult] = None

    # Search Execution
    def search(self,
               page: int = 1,
               from_request_cache: bool= True,
               from_process_cache: bool= True,
               use_workflow: Optional[bool] = True,
               **api_specific_parameters
              ) -> Optional[ResponseResult]:
        """
        Public method for retrieving and processing records from the API specifying the page and records per page.
        Note that the response object is saved under the last_response attribute in the event that the
        data is processed successfully, irrespective of whether responses are cached or not.


        Args:
            page (int): The current page number. Used for process caching purposes even if not required by the API
            from_request_cache (bool): This parameter determines whether to try to retrieve
                                       the response from the requests-cache storage
            from_process_cache (bool): This parameter determines whether to attempt to pull
                                       processed responses from the cache storage
            use_workflow (bool): Indicates whether to use a workflow if available Workflows are utilized by default.

            **api_specific_parameters (SearchAPIConfig): Fields to temporarily override when building the request.
        Returns:
            Optional[ProcessedResponse]: A response data class containing processed
                                         article data (data), and metadata
        """
        try:
            if use_workflow and self.workflow:
                workflow_output =  self.workflow(self, page = page, from_request_cache = from_request_cache,
                                                 from_process_cache = from_process_cache, **api_specific_parameters)

                return workflow_output.result if workflow_output is not None else None
            else:
                return self._search(page, from_request_cache = from_request_cache,
                                    from_process_cache = from_process_cache, **api_specific_parameters)
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

    # Search Execution
    def _search(self,
               page: int = 1,
               from_request_cache: bool= True,
               from_process_cache: bool= True,
               **api_specific_parameters
              ) -> Optional[ResponseResult]:
        """
        Helper method for retrieving and processing records from the API specifying the page and records per page.
        This method is called to perform all steps necessary to retrieve and process a response from the selected API.
        Beyond catching basic exceptions related to raised error codes and processing response issues, further errors
        are to be caught at a higher level such as in the public SearchCoordinator.search method.

        Args:
            page (int): The current page number. Used for process caching purposes even if not required by the API
            from_request_cache (bool): Indicates whether to attempt to retrieve the response from the requests-cache
            from_process_cache (bool): This parameter determines whether to attempt to pull processed responses from
                                       the processing cache storage device (or memory)
            **api_specific_parameters (SearchAPIConfig): Fields to temporarily override when building the request.
        Returns:
            Optional[ProcessedResponse]: A response data class containing processed article data (data), and metadata
        """
        response, cache_key = self._fetch_and_log(page,from_request_cache=from_request_cache, **api_specific_parameters)
        self._log_response_source(response, page, cache_key)
        processed_response = self._process_response(response, cache_key, from_process_cache)
        return processed_response

    # Request Handling
    def fetch(self, page: int,
              from_request_cache: bool= True,
              **api_specific_parameters) -> Optional[Response]:
        """
        Fetches the raw response from the current API.

        Args:
            page (int): The page number to retrieve from the cache.
            from_request_cache (bool): This parameter determines whether to
                                       try to fetch from cache
            **api_specific_parameters (SearchAPIConfig): Fields to temporarily override when building the request.

        Returns:
            Optional[Response]: The response object if available, otherwise None.
        """
        try:

            if from_request_cache:
                # attempts to retrieve the cached request associated with the page
                if response:=self.get_cached_request(page, **api_specific_parameters):
                    return response
            else:
                # if the key does not exist, will log at the INFO level and continue
                self._delete_cached_request(page, **api_specific_parameters)

            response = self.robust_request(page, **api_specific_parameters)
            return response
        except RequestFailedException as e:
            logger.warning(f"Failed to fetch page {page}: {e}")
        return None

    def robust_request(self, page: int, **api_specific_parameters) -> Optional[Response]:
        """Constructs and sends a request to the current API.
        Fetches a response from the current API.

        Args:
            page (int): The page number to retrieve from the cache.
            **kwargs: Optional Additional parameters to pass to the SearchAPI
        Returns:
            Optional[Response]: The request object if available, otherwise None.
        """

        try:
            response = self.retry_handler.execute_with_retry(
                request_func=self.api.search,
                validator_func=self.validator.validate_response,
                page=page,
                **api_specific_parameters
            )

        except RequestFailedException as e:
            logger.error(f"Failed to get a valid response from the {self.api.provider_name} API: {e}")
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
            if not self.response_coordinator.cache_manager:
                return None
            cache_key = self._create_cache_key(page)
            cached = self.response_coordinator.cache_manager.retrieve(cache_key)
            if cached:
                logger.info(f"Cache hit for key: {cache_key}")
                return cached
            logger.info(f"Cache miss for key: {cache_key}")
            return None
        except StorageCacheException as e:
            logger.error(f"Error retrieving cached response: {e}")
            return None

    def _fetch_and_log(self, page: int, from_request_cache: bool= True, **api_specific_parameters) -> Tuple[Optional[Response], str]:
        """Helper method for fetching the response and retrieving the cache key.
        Args:
            page (int): The page number to retrieve from the cache.
        Returns:
            Tuple[Optional[Response], str]: A tuple containing The request object
                                            if available and its cache key
            **api_specific_parameters (SearchAPIConfig): Fields to temporarily override when building the request.
        """
        response = self.fetch(page, from_request_cache = from_request_cache, **api_specific_parameters)
        cache_key = self._create_cache_key(page)

        if not response:
            logger.info(f"Response retrieval for cache key {cache_key} was unsuccessful.")
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

        if self.response_coordinator.cache_manager:
            logger.info(f"Handling response (cache key: {cache_key})")
        else:
            logger.info("Handling response")

    def _process_response(self, response: Optional[Response], cache_key: str, from_process_cache: bool = True) -> Optional[ResponseResult]:
        """
        Helper method for processing records from the API and, upon success, saving records to cache
        if from_process_cache = True and caching is enabled.

        Args:
            response (Optional[Response]): The response retrieved from an API
            cache_key (Optional[str]): The key used for caching responses, data processing, and metadata when enabled
            from_process_cache (bool): Indicates whether or not to use pull from cache when available.
                                       This option is only relevant when a caching backend is enabled.
        """
        if not isinstance(response, Response):
            return None

        processed_response = self.response_coordinator.handle_response(response,
                                                                       cache_key,
                                                                       from_cache = from_process_cache)

        if isinstance(processed_response, (ErrorResponse, ProcessedResponse)):
            self.last_response = processed_response

        return processed_response



    def _prepare_request(self, page: int, **kwargs) -> PreparedRequest:
        """
        Prepares the request after constructing the request parameters for the API call.
        Args:
            page (int): The page number to request.
            **kwargs: Additional parameters for the request.
        Returns:
            PreparedRequest: The prepared request object to send to the api
        """

        parameters = self.api.build_parameters(page=page, **kwargs)
        request = self.api.prepare_request(self.api.base_url,
                                           parameters=parameters)
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
        return f"{self.api.provider_name}_{self.api.query}_{page}_{self.api.records_per_page}"

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
        if self.response_coordinator.cache_manager:
            try:
                cache_key = self._create_cache_key(page)
                logger.debug(f"Attempting to delete processing cache key: {cache_key}")
                self.response_coordinator.cache_manager.delete(cache_key)
            except Exception as e:
                logger.error(f"Error in deleting from processing cache: {e}")

