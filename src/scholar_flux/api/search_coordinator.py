from __future__ import annotations
from typing import List, Dict, Optional, Any, Tuple, Sequence, cast
from requests import PreparedRequest, Response
import logging

from scholar_flux.api.retry_handler import RetryHandler
from scholar_flux import DataCacheManager
from scholar_flux.api import (
    SearchAPI,
    ResponseCoordinator,
    ResponseValidator,
    ProcessedResponse,
    ErrorResponse,
)
from scholar_flux.api.models import ResponseResult, PageListInput

from scholar_flux.data.base_parser import BaseDataParser
from scholar_flux.data.base_extractor import BaseDataExtractor
from scholar_flux.data.abc_processor import ABCDataProcessor

from scholar_flux.utils.response_protocol import ResponseProtocol

from scholar_flux.exceptions import (
    RequestFailedException,
    RequestCacheException,
    StorageCacheException,
    APIParameterException,
    InvalidCoordinatorParameterException,
)
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

    def __init__(
        self,
        search_api: Optional[SearchAPI] = None,
        response_coordinator: Optional[ResponseCoordinator] = None,
        parser: Optional[BaseDataParser] = None,
        extractor: Optional[BaseDataExtractor] = None,
        processor: Optional[ABCDataProcessor] = None,
        cache_manager: Optional[DataCacheManager] = None,
        cache_requests: Optional[bool] = None,
        cache_results: Optional[bool] = None,
        query: Optional[str] = None,
        retry_handler: Optional[RetryHandler] = None,
        validator: Optional[ResponseValidator] = None,
        workflow: Optional[SearchWorkflow] = None,  # updating workflow with a workflow method by default
        **kwargs,
    ):
        """

        Flexible initializer that constructs a SearchCoordinator either from its core components or from their
        basic building blocks when these core components are not directly provided.

        If `search_api` and `response_coordinator` are provided, then this method will use these inputs directly.

        The additional parameters can still be used to update these two components. For example, a `search_api` can be
        updated with a new `query`, `session`, and SearchAPIConfig parameters through key word arguments [**kwargs])

        When neither component is provided:
            - The creation of the search_api requires, at minimum, a query.
            - If the response_coordinator, a parser, extractor, processor, and cache_manager aren't provided, then
              then a new ResponseCoordinator will be built from the default settings.


        Core Components/Attributes:
            SearchAPI: handles all requests to an API based on its configuration.
                Dependencies: `query`, `**kwargs`
            ResponseCoordinator:handles the parsing, record/metadata extraction, processing, and caching of responses
                Dependencies: `parser`, `extractor`, `processor`, `cache_manager`

        Other Attributes:
            RetryHandler: Addresses when to retry failed requests and how failed requests are retried
            SearchWorkflow: An optional workflow that defines custom search logic from specific APIs
            Validator: handles how requests are validated. The default determines whether a 200 response was received

        Note:
            This implementation uses the underlying private method `_initialize` to handle the assignment
            of parameters under the hood while the core function of the __init__ creates these components if
            they do not already exist.

        Args:
            search_api (Optional[SearchAPI]): The search API to use for the retrieval of response records from APIs
            response_coordinator (Optional[ResponseCoordinator]): Core class used to handle the processing and
                                                                 core handling of all responses from APIs
            parser: Optional([BaseDataParser]): First step of the response processing pipeline - parses response records into a dictionary
            extractor: (Optional[BaseDataExtractor]): Extracts both records and metadata from responses separately
            processor: (Optional[ABCDataProcessor]): Processes API responses into list of dictionaries
            cache_manager: (Optional[DataCacheManager]): Manages the caching of processed records for faster retrieval
            cache_requests: (Optional[bool]): Determines whether or not to cache requests - api is the ground truth if not directly specified
            cache_results: (Optional[bool]): Determines whether or not to cache processed responses - on by default unless specified otherwise
            query: (Optional[str]): Query to be used when sending requests when creating an API - modifies the query if the API already exists
            retry_handler (Optional[RetryHandler]): class used to retry failed requests-cache
            validator (Optional[ResponseValidator]): class used to verify and validate responses returned from APIs
            workflow (Optional[SearchWorkflow]): An optional workflow used to customize how records are retrieved
                                                 from APis. Uses the default workflow for the current provider when
                                                 a workflow is not directly specified.
            **kwargs: Keyword arguments to be passed to the SearchAPIConfig that creates the SearchAPI if it doesn't already exist

            Examples:
                >>> from scholar_flux import SearchCoordinator
                >>> from scholar_flux.api import APIResponse, ReconstructedResponse
                >>> from scholar_flux.sessions import CachedSessionManager
                >>> from typing import MutableMapping
                >>> session = CachedSessionManager(user_agent = 'sammih', backend='redis').configure_session()
                >>> search_coordinator = SearchCoordinator(query = "Intrinsic Motivation", session = session, cache_results = False)
                >>> response = search_coordinator.search(page = 1)
                >>> response
                # OUTPUT: <ProcessedResponse(len=50, cache_key='plos_Functional Processing_1_50', metadata='...') ': 1, 'maxSco...")>
                >>> new_response = ReconstructedResponse.build(**response.response.__dict__)
                >>> new_response.validate()
                >>> new_response = ReconstructedResponse.build(response.response)
                >>> ReconstructedResponse.build(new_response).validate()
                >>> new_response.validate()
                >>> newer_response = APIResponse.as_reconstructed_response(new_response)
                >>> newer_response.validate()
                >>> double_processed_response = search_coordinator._process_response(response = newer_response, cache_key = response.cache_key)
        """

        if not query and search_api is None:
            raise InvalidCoordinatorParameterException("Either 'query' or 'search_api' must be provided.")

        provider_name = kwargs.pop("provider_name", None)
        kwargs["use_cache"] = cache_requests if cache_requests is not None else kwargs.get("use_cache")

        try:
            api: SearchAPI = (
                SearchAPI.from_defaults(cast(str, query), provider_name=provider_name, **kwargs)
                if not search_api
                else SearchAPI.update(search_api, query=query, provider_name=provider_name, **kwargs)
            )
        except APIParameterException as e:
            logger.error("Could not initialize the SearchCoordinator due to an issue creating the SearchAPI.")
            raise InvalidCoordinatorParameterException(
                "Could not initialize the SearchCoordinator due to an API " f"parameter exception. {e}"
            )

        try:
            response_coordinator = (
                ResponseCoordinator.build(parser, extractor, processor, cache_manager, cache_results)
                if not response_coordinator
                else ResponseCoordinator.update(
                    response_coordinator, parser, extractor, processor, cache_manager, cache_results
                )
            )
        except (APIParameterException, InvalidCoordinatorParameterException) as e:
            logger.error("Could not initialize the SearchCoordinator due to an issue creating the ResponseCoordinator.")
            raise InvalidCoordinatorParameterException(
                "Could not initialize the SearchCoordinator due to an "
                f"exception creating the ResponseCoordinator. {e}"
            )

        self._initialize(api, response_coordinator, retry_handler, validator, workflow)

    def _initialize(
        self,
        search_api: SearchAPI,
        response_coordinator: ResponseCoordinator,
        retry_handler: Optional[RetryHandler] = None,
        validator: Optional[ResponseValidator] = None,
        workflow: Optional[SearchWorkflow] = None,
    ):
        """
        Helper method for initializing the final components of the SearchCoordinator after
        the creation of the SearchAPI and the ResponseCoordinator.

        Args:
            searchAPI (Optional[SearchAPI]): The search API to use for the retrieval of response records from APIs
            response_coordinator (Optional[ResponseCoordinator]): Core class used to handle the processing and
                                                                 core handling of all responses from APIs
            retry_handler (Optional[RetryHandler]): class used to retry failed requests-cache
            validator (Optional[ResponseValidator]): class used to verify and validate responses returned from APIs
            workflow (Optional[SearchWorkflow]): An optional workflow used to customize how records are retrieved
                                                 from APis. Uses the default workflow for the current provider when
                                                 a workflow is not directly specified.
        """

        super()._initialize(search_api, response_coordinator)
        self.retry_handler = retry_handler or RetryHandler()
        self.validator = validator or ResponseValidator()
        self.workflow = workflow or WORKFLOW_DEFAULTS.get(self.search_api.provider_name)

    @classmethod
    def as_coordinator(
        cls, search_api: SearchAPI, response_coordinator: ResponseCoordinator, *args, **kwargs
    ) -> SearchCoordinator:
        """
        Helper factory method for building a SearchCoordinator that allows users to build from the
        final building blocks of a SearchCoordinator

        Args:
            searchAPI (Optional[SearchAPI]): The search API to use for the retrieval of response records from APIs
            response_coordinator (Optional[ResponseCoordinator]): Core class used to handle the processing and
                                                                 core handling of all responses from APIs

        Returns:
            SearchCoordinator: A newly created coordinator that orchestrates record retrieval and processing
        """
        search_coordinator = cls.__new__(cls)
        search_coordinator._initialize(search_api, response_coordinator, *args, **kwargs)
        return search_coordinator

    @classmethod
    def update(
        cls,
        search_coordinator: SearchCoordinator,
        search_api: Optional[SearchAPI] = None,
        response_coordinator: Optional[ResponseCoordinator] = None,
        retry_handler: Optional[RetryHandler] = None,
        validator: Optional[ResponseValidator] = None,
        workflow: Optional[SearchWorkflow] = None,
    ) -> SearchCoordinator:
        """
        Helper factory method allowing the creation of a new components based on an existing configuration
        while allowing the replacement of previous components. Note that this implementation does not directly
        copy the underlying components if a new component is not selected.

        Args:
            SearchCoordinator: A previously created coordinator containing the components to use if a default
                               is not provided
            searchAPI (Optional[SearchAPI]): The search API to use for the retrieval of response records from APIs
            response_coordinator (Optional[ResponseCoordinator]): Core class used to handle the processing and
                                                                 core handling of all responses from APIs
            retry_handler (Optional[RetryHandler]): class used to retry failed requests-cache
            validator (Optional[ResponseValidator]): class used to verify and validate responses returned from APIs
            workflow (Optional[SearchWorkflow]): An optional workflow used to customize how records are retrieved
                                                 from APis. Uses the default workflow for the current provider when
                                                 a workflow is not directly specified and does not directly carry
                                                 over in cases where a new provider is chosen.
        Returns:
            SearchCoordinator: A newly created coordinator that orchestrates record retrieval and processing
        """
        search_api = search_api or search_coordinator.search_api
        if workflow is None:
            # use the previous workflow only if the providers are the same
            workflow = (
                search_coordinator.workflow
                if search_coordinator.search_api.provider_name == search_api.provider_name
                else None
            )

        return cls.as_coordinator(
            search_api=search_api,
            response_coordinator=response_coordinator or search_coordinator.response_coordinator,
            retry_handler=retry_handler or search_coordinator.retry_handler,
            validator=validator or search_coordinator.validator,
            workflow=workflow,
        )

    # Search Execution
    def search(
        self,
        page: int = 1,
        from_request_cache: bool = True,
        from_process_cache: bool = True,
        use_workflow: Optional[bool] = True,
        **api_specific_parameters,
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
                workflow_output = self.workflow(
                    self,
                    page=page,
                    from_request_cache=from_request_cache,
                    from_process_cache=from_process_cache,
                    **api_specific_parameters,
                )

                return workflow_output.result if workflow_output is not None else None
            else:
                return self._search(
                    page,
                    from_request_cache=from_request_cache,
                    from_process_cache=from_process_cache,
                    **api_specific_parameters,
                )
        except Exception as e:
            logger.error(f"An unexpected error occurred when processing the response: {e}")
        return None

    def search_pages(
        self,
        pages: Sequence[int],
        from_request_cache: bool = True,
        from_process_cache: bool = True,
        use_workflow: Optional[bool] = True,
        **api_specific_parameters,
    ) -> List[ResponseResult]:
        """
        Public method for retrieving and processing records from the API specifying the page and records per page
        in sequence. This method
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
            List[ProcessedResponse]: A list of response data classes containing processed article data (data).
                                     Note that processing stops if the response for a given page is None,
                                     is not retrievable, or contains less than the expected number of responses,
                                     indicating that the next page may contain no more records
        """
        # preprocesses the iterable of pages to reduce redundancy and validate beforehand
        page_list_input = PageListInput(pages)
        page_results: List[ResponseResult] = []

        try:
            for page in page_list_input.page_numbers:
                result = self.search(
                    page=page,
                    from_request_cache=from_request_cache,
                    from_process_cache=from_process_cache,
                    use_workflow=use_workflow,
                    **api_specific_parameters,
                )

                if isinstance(result, (ProcessedResponse, ErrorResponse)):
                    page_results.append(result)

                halt = self._process_search_page(result, page)

                if halt:
                    break

        except Exception as e:
            logger.error(f"An unexpected error occurred when processing the response: {e}")
        return page_results

    def _process_search_page(self, search_result: Optional[ProcessedResponse | ErrorResponse], page: int) -> bool:
        """Helper method for logging the result of each page search and determining whether to continue"""
        halt = True

        if isinstance(search_result, ProcessedResponse):
            expected_page_count = self.search_api.config.records_per_page

            if expected_page_count and len(search_result.extracted_records or []) < expected_page_count:
                logger.warning(
                    f"The response for page, {page} contains less than the expected "
                    f"{expected_page_count} records. Received {repr(search_result)}. "
                    f"Halting multi-page retrieval..."
                )
            else:
                halt = False

        elif isinstance(search_result, ErrorResponse):
            status_code = search_result.status_code
            status_description = (
                f"(Status Code: {status_code}={search_result.status})" if status_code else "(Status Code: Missing)"
            )

            logger.warning(
                f"Received an invalid response for page {page}. "
                f"{status_description}. Halting multi-page retrieval..."
            )
        else:
            logger.warning(
                f"Could not retrieve a valid response code for page {page}. "
                f"Received {repr(search_result)}. Halting multi-page retrieval..."
            )
        return halt

    def search_data(
        self,
        page: int = 1,
        from_request_cache: bool = True,
        from_process_cache: bool = True,
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
            response = self.search(
                page,
                from_request_cache=from_request_cache,
                from_process_cache=from_process_cache,
            )
            if response:
                return response.data

        except Exception as e:
            logger.error(f"An unexpected error occurred when attempting to retrieve the processsed response data: {e}")
        return None

    # Search Execution
    def _search(
        self,
        page: int = 1,
        from_request_cache: bool = True,
        from_process_cache: bool = True,
        **api_specific_parameters,
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
        response, cache_key = self._fetch_and_log(
            page, from_request_cache=from_request_cache, **api_specific_parameters
        )
        self._log_response_source(response, page, cache_key)
        processed_response = self._process_response(response, cache_key, from_process_cache)
        return processed_response

    # Request Handling
    def fetch(
        self, page: int, from_request_cache: bool = True, **api_specific_parameters
    ) -> Optional[Response | ResponseProtocol]:
        """
        Fetches the raw response from the current API or from cache if available.

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
                if response := self.get_cached_request(page, **api_specific_parameters):
                    return response
            else:
                # if the key does not exist, will log at the INFO level and continue
                self._delete_cached_request(page, **api_specific_parameters)

            response = self.robust_request(page, **api_specific_parameters)
            return response
        except RequestFailedException as e:
            logger.warning(f"Failed to fetch page {page}: {e}")
        return None

    def robust_request(self, page: int, **api_specific_parameters) -> Optional[Response | ResponseProtocol]:
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
                request_func=self.search_api.search,
                validator_func=self.validator.validate_response,
                page=page,
                **api_specific_parameters,
            )

        except RequestFailedException as e:
            logger.error(f"Failed to get a valid response from the {self.search_api.provider_name} API: {e}")
            raise

        if getattr(response, "from_cache", False):
            logger.info(f"Retrieved cached response for query: {self.search_api.query} and page: {page}")
        return response

    def get_cached_request(self, page: int, **kwargs) -> Optional[Response | ResponseProtocol]:
        """
        Retrieves the cached request for a given page number if available.
        Args:
            page (int): The page number to retrieve from the cache.
        Returns:
            Optional[Response]: The cached request object if available, otherwise None.
        """
        try:
            if not self.search_api.cache:
                return None
            request_key = self._get_request_key(page, **kwargs)
            if not request_key:
                return None
            return self.search_api.cache.get_response(request_key)

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

    def _fetch_and_log(
        self, page: int, from_request_cache: bool = True, **api_specific_parameters
    ) -> Tuple[Optional[Response | ResponseProtocol], str]:
        """Helper method for fetching the response and retrieving the cache key.
        Args:
            page (int): The page number to retrieve from the cache.
        Returns:
            Tuple[Optional[Response], str]: A tuple containing The request object
                                            if available and its cache key
            **api_specific_parameters (SearchAPIConfig): Fields to temporarily override when building the request.
        """
        response = self.fetch(page, from_request_cache=from_request_cache, **api_specific_parameters)
        cache_key = self._create_cache_key(page)

        if not response:
            logger.info(f"Response retrieval for cache key {cache_key} was unsuccessful.")
        return response, cache_key

    def _log_response_source(
        self, response: Optional[Response | ResponseProtocol], page: int, cache_key: Optional[str]
    ) -> None:
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
            logger.warning(f"Response retrieval and processing for page {page} was unsuccessful.")
            return

        if getattr(response, "from_cache", False):
            logger.info(f"Retrieved a cached response for cache key: {cache_key}")

        if self.response_coordinator.cache_manager:
            logger.info(f"Handling response (cache key: {cache_key})")
        else:
            logger.info("Handling response")

    def _process_response(
        self,
        response: Optional[Response | ResponseProtocol],
        cache_key: str,
        from_process_cache: bool = True,
    ) -> Optional[ResponseResult]:
        """
        Helper method for processing records from the API and, upon success, saving records to cache
        if from_process_cache = True and caching is enabled.

        Args:
            response (Optional[Response]): The response retrieved from an API
            cache_key (Optional[str]): The key used for caching responses, data processing, and metadata when enabled
            from_process_cache (bool): Indicates whether or not to use pull from cache when available.
                                       This option is only relevant when a caching backend is enabled.
        """

        if not isinstance(response, Response) and not isinstance(response, ResponseProtocol):  # noqa: S101
            return None

        processed_response = self.response_coordinator.handle_response(
            response, cache_key, from_cache=from_process_cache
        )

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

        parameters = self.search_api.build_parameters(page=page, **kwargs)
        request = self.search_api.prepare_request(parameters=parameters)
        return request

    # Cache Management
    def _create_cache_key(self, page: int) -> str:
        """
        Combines information about the query type and current page to create an identifier for the current query.
        The cache key is always generated using the current page argument as well as the provider_name, query,
        and records_per_page, all of which originate from the SearchAPIConfig (accessible as properties).
        As a result, consistency is guaranteed

        Args:
            page (int): The current page number.

        Returns:
            str: A unique cache key based on the provided parameters.
        """
        return (
            f"{self.search_api.provider_name}_{self.search_api.query}_{page}_{self.search_api.records_per_page}".lower()
        )

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
            if self.search_api.cache:
                request = self._prepare_request(page, **kwargs)
                request_key = self.search_api.cache.create_key(request)
                return request_key
        except (APIParameterException, AttributeError, ValueError) as e:
            logger.error("Error retrieving requests-cache key")
            raise RequestCacheException(
                f"Error retrieving requests-cache key from session: {self.search_api.session}: {e}"
            )
        return None

    def _delete_cached_request(self, page: int, **kwargs) -> None:
        """
        Deletes the cached request for a given page number if available.
        Args:
            page (int): The page number to delete from the cache.
        """
        if self.search_api.cache:
            try:
                request_key = self._get_request_key(page, **kwargs)
                logger.debug(f"Attempting to delete requests cache key: {request_key}")
                if not request_key:
                    raise KeyError("Request key is None or empty")

                if not self.search_api.cache.contains(request_key):
                    raise KeyError(f"Key {request_key} not found in the API session request cache")

                self.search_api.cache.delete(request_key)

            except KeyError as e:
                logger.info(f"A cached response for the current request does not exist: {e}")

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
