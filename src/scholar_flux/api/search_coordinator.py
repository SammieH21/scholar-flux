# /api/search_coordinator.py
"""Implements the SearchCoordinator for orchestrating single/multi-page API response retrieval and record processing."""
from __future__ import annotations
from typing import List, Dict, Optional, Any, Sequence, cast, Generator
from requests import PreparedRequest, Response
from pydantic import ValidationError
import logging

from scholar_flux.api.rate_limiting.retry_handler import RetryHandler
from scholar_flux import DataCacheManager
from scholar_flux.api import (
    SearchAPI,
    ResponseCoordinator,
    ResponseValidator,
    ProcessedResponse,
    APIResponse,
    ErrorResponse,
    NonResponse,
)
from scholar_flux.api.models import PageListInput, SearchResult, SearchResultList
from scholar_flux.api.models.response_metadata_map import ResponseMetadataMap
from scholar_flux.api.validators import normalize_url, validate_url

from scholar_flux.data.base_parser import BaseDataParser
from scholar_flux.data.base_extractor import BaseDataExtractor
from scholar_flux.data.abc_processor import ABCDataProcessor

from scholar_flux.utils.response_protocol import ResponseProtocol
from scholar_flux.utils.helpers import parse_iso_timestamp, try_call
from scholar_flux.api.providers import provider_registry

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
    """High-level coordinator for requesting and retrieving records and metadata from APIs.

    This class uses dependency injection to orchestrate the process of constructing requests,
    validating responses, and processing scientific works and articles. This class is designed
    to abstract away the complexity of using APIs while providing a consistent and
    robust interface for retrieving record data and metadata from request and storage cache
    if valid to help avoid exceeding limits in API requests.

    If no search_api is provided, the coordinator will create a Search API that uses the default
    provider if the environment variable, `SCHOLAR_FLUX_DEFAULT_PROVIDER`, is not provided.
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
        query: Optional[str] = None,
        provider_name: Optional[str] = None,
        cache_requests: Optional[bool] = None,
        cache_results: Optional[bool] = None,
        retry_handler: Optional[RetryHandler] = None,
        validator: Optional[ResponseValidator] = None,
        workflow: Optional[SearchWorkflow] = None,
        **kwargs,
    ):
        """Flexible initializer that constructs a `SearchCoordinator` from its core components or their building blocks.

        If `SearchAPI` and `ResponseCoordinator` are provided, then this method will use these inputs directly.
        Otherwise, the coordinator will be created from their underlying dependencies when these core components are not
        directly provided.

        The additional parameters can still be used to update these two components. For example, a `search_api` can be
        updated with a new `query`, `session`, and SearchAPIConfig parameters through keyword arguments (**kwargs))

        When neither component is provided:
            - The creation of the search_api requires, at minimum, a query.
            - If the response_coordinator, a parser, extractor, processor, and cache_manager aren't provided,
              then a new ResponseCoordinator will be built from the default settings.


        Core Components/Attributes:
            SearchAPI: handles all requests to an API based on its configuration.
                Dependencies: `query`, `**kwargs`
            ResponseCoordinator: handles the parsing, record/metadata extraction, processing, and caching of responses
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
            search_api (Optional[SearchAPI]): The search API to use for the retrieval of response records from APIs.
            response_coordinator (Optional[ResponseCoordinator]):
                Core class used to coordinate the handling and processing of all responses received from APIs.
            parser (Optional(BaseDataParser)):
                First step of the response processing pipeline - parses response records into a dictionary.
            extractor (Optional[BaseDataExtractor]): Extracts both records and metadata from responses separately.
            processor (Optional[ABCDataProcessor]):
                Processes the previously extracted API records into list of dictionaries that are filtered and
                optionally flattened during processing.
            cache_manager (Optional[DataCacheManager]): Manages the caching of processed records for faster retrieval.
            query (Optional[str]):
                Query to be used when sending requests when creating an API - modifies the query if the API already
                exists.
            provider_name (Optional[str]):
                The name of the API provider where requests will be sent. If a provider_name and base_url are both
                given, the SearchAPIConfig will prioritize base_urls over the provider_name.
            cache_requestOptional[bool]):
                Determines whether or not to cache requests - api is the ground truth if not directly specified
            cache_results (Optional[bool]):
                Determines whether or not to cache processed responses - on by default unless specified otherwise
            retry_handler (Optional[RetryHandler]): Class used to retry failed requests-cache.
            validator (Optional[ResponseValidator]): Class used to verify and validate responses returned from APIs.
            workflow (Optional[SearchWorkflow]):
                An optional workflow used to customize how records are retrieved from APIs. Uses the default workflow
                for the current provider when a workflow is not directly specified.
            **kwargs: Keyword arguments to be passed to the SearchAPIConfig if a SearchAPI doesn't already exist.

            Examples:
                >>> from scholar_flux import SearchCoordinator
                >>> from scholar_flux.api import APIResponse, ReconstructedResponse
                >>> from scholar_flux.sessions import CachedSessionManager
                >>> from typing import MutableMapping
                >>> session = CachedSessionManager(user_agent = 'scholar_flux', backend='redis').configure_session()
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

        api = self._create_search_api(
            search_api, query=query, provider_name=provider_name, cache_requests=cache_requests, **kwargs
        )

        response_coordinator = self._create_response_coordinator(
            response_coordinator, parser, extractor, processor, cache_manager, cache_results
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
        """Helper method for initializing the core components of the `SearchCoordinator` once created.

        This method is used directly after the `SearchAPI` and the `ResponseCoordinator` are successfully created to
        fully initialize the `SearchCoordinator` for API response retrieval and processing.

        Args:
            search_api (SearchAPI): The SearchAPI to use for the retrieval of response records from APIs
            response_coordinator (ResponseCoordinator):
                Core class used to coordinate the handling and processing of all responses received from APIs.
            retry_handler (Optional[RetryHandler]): Class used to retry failed requests-cache
            validator (Optional[ResponseValidator]): Class used to verify and validate responses returned from APIs.
            workflow (Optional[SearchWorkflow]):
                An optional workflow used to customize how records are retrieved from APIs. Uses the default workflow
                for the current provider when a workflow is not directly specified.

        """
        super()._initialize(search_api, response_coordinator)
        self.retry_handler = retry_handler or RetryHandler(
            min_retry_delay=self.api.request_delay,
            backoff_factor=min(self.api.request_delay * 0.25, 0.5),
        )
        self.validator = validator or ResponseValidator()
        self.workflow = workflow or WORKFLOW_DEFAULTS.get(self.search_api.provider_name)

    @classmethod
    def _create_search_api(
        cls,
        search_api: Optional[SearchAPI] = None,
        provider_name: Optional[str] = None,
        query: Optional[str] = None,
        cache_requests: Optional[bool] = None,
        **kwargs,
    ) -> SearchAPI:
        """Helper method for creating a new Search API from its components or an existing SearchAPI.

        This method is useful for when a `SearchAPI` instance needs to be created and used from scratch rather than
        directly copied given constraints on copying session and cached session objects.

        Args:
            search_api (Optional[SearchAPI]):
                The search API to use for the retrieval of response records from APIs.
            provider_name (Optional[str]):
                The name of the API provider where requests will be sent. If a `provider_name` and `base_url` are both
                given, the `SearchAPIConfig` will prioritize the `base_url` over the `provider_name`.
            query (Optional[str]):
                Query to be used when sending requests when creating an API. Specifying a query when a `SearchAPI`
                already exists will modify the query.
            cache_requests (Optional[bool]):
                Determines whether or not to cache requests. The `SearchAPI` defaults are the ground truth determinants
                of whether caching is enabled if `cache_requests` is not specified.
            **kwargs: Keyword arguments to be passed to the SearchAPIConfig if a SearchAPI doesn't already exist.

        Returns:
            SearchAPI: A new search API either based on the original search api with modified components or created
                entirely anew.

        """
        if not query and search_api is None:
            raise InvalidCoordinatorParameterException("Either 'query' or 'search_api' must be provided.")

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
        return api

    @classmethod
    def _create_response_coordinator(
        cls,
        response_coordinator: Optional[ResponseCoordinator] = None,
        parser: Optional[BaseDataParser] = None,
        extractor: Optional[BaseDataExtractor] = None,
        processor: Optional[ABCDataProcessor] = None,
        cache_manager: Optional[DataCacheManager] = None,
        cache_results: Optional[bool] = None,
    ) -> ResponseCoordinator:
        """Helper method for creating a new response coordinator either from an existing response coordinator with
        overrides or created anew entirely from its core dependencies.

        Args:
            response_coordinator (Optional[ResponseCoordinator]):
                Core class used to handle the processing and core handling of all responses from APIs
            parser (Optional[BaseDataParser]):
                First step of the response processing pipeline. Parses response records into a dictionary
            extractor (Optional[BaseDataExtractor]):
                Extracts both records and metadata from responses separately.
            processor (Optional[ABCDataProcessor]):
                Processes the previously extracted API records into list of dictionaries that are filtered and
                optionally flattened during processing.
            cache_manager (Optional[DataCacheManager]): Manages the caching of processed records for faster retrieval
            cache_results (Optional[bool]):
                Determines whether or not to cache processed responses. On by default unless specified otherwise.

        Returns:
            ResponseCoordinator:
                A new response coordinator consisting of the base components from the original response coordinator or
                constructed directly from its components.

        """
        try:
            coordinator = (
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

        return coordinator

    @classmethod
    def as_coordinator(
        cls, search_api: SearchAPI, response_coordinator: ResponseCoordinator, *args, **kwargs
    ) -> SearchCoordinator:
        """Helper factory method for building a SearchCoordinator that allows users to build from the final building
        blocks of a SearchCoordinator.

        Args:
            search_api (Optional[SearchAPI]): The search API to use for the retrieval of response records from APIs
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
        """Helper factory method allowing the creation of a new components based on an existing configuration while
        allowing the replacement of previous components. Note that this implementation does not directly copy the
        underlying components if a new component is not selected.

        Args:
            SearchCoordinator: A previously created coordinator containing the components to use if a default
                               is not provided
            search_api (Optional[SearchAPI]): The search API to use for the retrieval of response records from APIs
            response_coordinator (Optional[ResponseCoordinator]): Core class used to handle the processing and
                                                                 core handling of all responses from APIs
            retry_handler (Optional[RetryHandler]): class used to retry failed requests-cache
            validator (Optional[ResponseValidator]): class used to verify and validate responses returned from APIs
            workflow (Optional[SearchWorkflow]): An optional workflow used to customize how records are retrieved
                                                 from APIs. Uses the default workflow for the current provider when
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
        normalize_records: Optional[bool] = None,
        **api_specific_parameters,
    ) -> Optional[ProcessedResponse | ErrorResponse]:
        """Public method for retrieving and processing records from the API specifying the page and records per page.
        Note that the response object is saved under the last_response attribute in the event that the response is
        retrieved and processed successfully, irrespective of whether the response was cached.

        Args:
            page (int): The current page number. Used for process caching purposes even if not required by the API
            from_request_cache (bool): This parameter determines whether to try to retrieve
                                       the response from the requests-cache storage
            from_process_cache (bool): This parameter determines whether to attempt to pull
                                       processed responses from the cache storage
            use_workflow (bool): Indicates whether to use a workflow if available Workflows are utilized by default.
            normalize_records (Optional[bool]): Determines whether records should be normalized after processing
            **api_specific_parameters (SearchAPIConfig): Fields to temporarily override when building the request.
        Returns:
            Optional[ProcessedResponse | ErrorResponse]:
                A ProcessedResponse model containing the response (response), processed records (data), and article
                metadata (metadata) if the response was successful. Otherwise returns an ErrorResponse where the reason
                behind the error (message), exception type (error), and response (response) are provided.
                Possible error responses also include a `NonResponse` (an `ErrorResponse` subclass) for cases where a
                response object is irretrievable. Like the `ErrorResponse` class, `NonResponse` is also Falsy
                (i.e., `not NonResponse` returns True)

        """
        try:
            if use_workflow and self.workflow:
                workflow_output = self.workflow(
                    self,
                    page=page,
                    from_request_cache=from_request_cache,
                    from_process_cache=from_process_cache,
                    normalize_records=normalize_records,
                    **api_specific_parameters,
                )

                return workflow_output.result if workflow_output is not None else None
            else:
                return self._search(
                    page,
                    from_request_cache=from_request_cache,
                    from_process_cache=from_process_cache,
                    normalize_records=normalize_records,
                    **api_specific_parameters,
                )
        except Exception as e:
            logger.error(f"An unexpected error occurred when processing the response: {e}")
            # `page` input could have a type issue, so create a cache key only if valid
            cache_key = self._create_cache_key(page=page) if isinstance(page, int) and page >= 0 else None
            return NonResponse.from_error(error=e, message=str(e), cache_key=cache_key)

    def parameter_search(
        self,
        from_request_cache: bool = True,
        from_process_cache: bool = True,
        normalize_records: Optional[bool] = None,
        **api_specific_parameters,
    ) -> Optional[ProcessedResponse | ErrorResponse]:
        """Public method for retrieving and processing records from the API with pre-specified parameters.

        Note that the response object is saved under the last_response attribute in the event that the response is
        retrieved and processed successfully, irrespective of whether the response was cached.

        Args:
            from_request_cache (bool): This parameter determines whether to try to retrieve
                                       the response from the requests-cache storage
            from_process_cache (bool): This parameter determines whether to attempt to pull
                                       processed responses from the cache storage
            normalize_records (Optional[bool]): Determines whether records should be normalized after processing
            **api_specific_parameters (SearchAPIConfig): Fields to temporarily override when building the request.
        Returns:
            Optional[ProcessedResponse | ErrorResponse]:
                A ProcessedResponse model containing the response (response), processed records (data), and article
                metadata (metadata) if the response was successful. Otherwise returns an ErrorResponse where the reason
                behind the error (message), exception type (error), and response (response) are provided.
                Possible error responses also include a `NonResponse` (an `ErrorResponse` subclass) for cases where a
                response object is irretrievable. Like the `ErrorResponse` class, `NonResponse` is also Falsy
                (i.e., `not NonResponse` returns True)

        """
        # remove parameters that aren't relevant for parameter_searches
        api_specific_parameters.pop("page", None)
        api_specific_parameters.pop("use_workflow", None)

        try:
            return self._search(
                page=None,
                from_request_cache=from_request_cache,
                from_process_cache=from_process_cache,
                normalize_records=normalize_records,
                **api_specific_parameters,
            )
        except Exception as e:
            logger.error(f"An unexpected error occurred when processing the response: {e}")
            # `page` input could have a type issue, so create a cache key only if valid
            return NonResponse.from_error(error=e, message=str(e), cache_key=None)

    def search_pages(
        self,
        pages: Sequence[int] | PageListInput,
        from_request_cache: bool = True,
        from_process_cache: bool = True,
        use_workflow: Optional[bool] = True,
        **api_specific_parameters,
    ) -> SearchResultList:
        """Public method for retrieving and processing records from the API specifying the page and records per page in
        sequence.

        This method collects search results from multiple pages into a SearchResultList, which provides
        specialized methods for filtering, normalization, selection, and aggregation. Unlike iter_pages(),
        which streams results one at a time, this method returns the full collection for cross-page analysis
        and batch operations.

        The SearchResultList return type enables powerful operations like filtering out failures, normalizing
        records across different providers, selecting subsets by query/provider/page, and joining all records
        into a single list for DataFrame creation.

        Args:
            pages (Sequence[int] | PageListInput):
                A sequence of page numbers to request from the API Provider. Can be a list, range, or
                PageListInput instance.
            from_request_cache (bool):
                This parameter determines whether to try to retrieve the response from the requests-cache
                storage.
            from_process_cache (bool):
                This parameter determines whether to attempt to pull processed responses from the cache storage.
            use_workflow (bool):
                Indicates whether to use a workflow if available Workflows are utilized by default.
            **api_specific_parameters (SearchAPIConfig):
                Fields to temporarily override when building the request.

        Returns:
            SearchResultList:
                A specialized list containing SearchResult instances for each requested page. The SearchResultList
                provides methods including:
                - filter(): Retain only successful ProcessedResponses or filter by success/failure
                - select(): Filter results by query, provider_name, or page number
                - normalize(): - Apply field mapping to create provider-agnostic record schemas
                - join(): - Combine all records into a single list with optional metadata
                - process_metadata(): - Extract and process metadata across all results
                - record_count: - Total number of records across all pages

                Note that retrieval stops early if a page response is None, not retrievable, or contains fewer
                than the expected number of records, indicating that subsequent pages may be empty.

        """
        page_results: SearchResultList = SearchResultList()

        try:

            search_results = self.iter_pages(
                pages=pages,
                from_request_cache=from_request_cache,
                from_process_cache=from_process_cache,
                use_workflow=use_workflow,
                **api_specific_parameters,
            )

            for search_result in search_results:
                page_results.append(search_result)

        except Exception as e:
            logger.error(f"An unexpected error occurred when processing the response: {e}")

        return page_results

    def iter_pages(
        self,
        pages: Sequence[int] | PageListInput,
        from_request_cache: bool = True,
        from_process_cache: bool = True,
        use_workflow: Optional[bool] = True,
        **api_specific_parameters,
    ) -> Generator[SearchResult, None, None]:
        """Helper method that creates a generator function for retrieving and processing records from the API Provider
        for a page range in sequence. This implementation dynamically examines the properties of the page search result
        for each retrieved API response to determine whether or not iteration should halt early versus determining
        whether iteration should continue.

        This method is directly used by SearchCoordinator.search_pages to provide a clean interface that abstracts
        the complexity of iterators and is also provided for convenience when iteration is more preferable.

        Args:
            pages (Sequence[int] | PageListInput): A sequence of page numbers to request from the API Provider.
            from_request_cache (bool): This parameter determines whether to try to retrieve the response from the
                                       requests-cache storage.
            from_process_cache (bool): This parameter determines whether to attempt to pull processed responses from
                                       the cache storage.
            use_workflow (bool): Indicates whether to use a workflow if available Workflows are utilized by default.

            **api_specific_parameters (SearchAPIConfig): Fields to temporarily override when building the request.

        Yields:
            SearchResult: Iteratively returns the SearchResult for each page using a generator expression.
                          Each result contains the requested page number (page), the name of the provider
                          (provider_name), and the result of the search containing a ProcessedResponse,
                          an ErrorResponse, or None (api response)

        """
        # preprocesses the iterable or sequence of pages to reduce redundancy and validate beforehand
        page_list_input = self._validate_page_list_input(pages)

        for page in page_list_input.page_numbers:

            search_result = self.search_page(
                page=page,
                from_request_cache=from_request_cache,
                from_process_cache=from_process_cache,
                use_workflow=use_workflow,
                **api_specific_parameters,
            )

            halt = self._process_page_result(search_result.response_result, page)

            yield search_result

            if halt:
                break

    def search_page(
        self,
        page: int,
        from_request_cache: bool = True,
        from_process_cache: bool = True,
        use_workflow: Optional[bool] = True,
        **api_specific_parameters,
    ) -> SearchResult:
        """Retrieves a single-page `SearchResult`, returning the processed response with additional metadata.

        This method is used to support the retrieval of a page range while wrapping each result in a
        SearchResult class as a BaseModel that provides more structured information about the received API Response,
        including the provider's name, the page number, and the response result.

        The `SearchResult.response_result` attribute can hold three different types of responses:

        1. ProcessedResponse - indicates the successful retrieval and processing of the data
        2. ErrorResponse/Nonresponse - indicates that a response was successfully received, but that an error
                                       occurred during request building, response retrieval or response processing
        3. None - indicates an issue in the retrieval of the response or formatting/preparation of the request

        The SearchResult wrapper enables:
        - **Introspection**: Access provider, query, and page without unpacking the response
        - **Aggregation**: Combine results across pages with consistent metadata
        - **Normalization**: Apply field mapping to create provider-agnostic schemas

        When a workflow is active, the provider name is determined from the last-queried URL to ensure correct labeling.
        For non-workflow searches, the SearchAPI's provider name is used.

        Args:
            page (int): The current page number. Used for process caching purposes even if not required by the API
            from_request_cache (bool):
                This parameter determines whether to try to retrieve the response from the requests-cache storage.
            from_process_cache (bool):
                This parameter determines whether to attempt to pull processed responses from the cache storage.
            use_workflow (bool): Indicates whether to use a workflow if available Workflows are utilized by default.
            **api_specific_parameters (SearchAPIConfig): Fields to temporarily override when building the request.

        Returns:
            SearchResult:
                A search result containing the requested page number (page), the name of the provider (provider_name),
                and the result of the search (api_response) which contains a ProcessedResponse, an ErrorResponse,
                or None.

        """
        api_response = self.search(
            page=page,
            from_request_cache=from_request_cache,
            from_process_cache=from_process_cache,
            use_workflow=use_workflow,
            **api_specific_parameters,
        )

        # for workflow resolution where needed
        if self.workflow and use_workflow:
            provider_url = api_response.url if api_response is not None else None
            provider_config = provider_registry.resolve_config(provider_url, self.api.provider_name, verbose=False)
            provider_name = provider_config.provider_name if provider_config else self.api.provider_name
        else:
            provider_name = self.api.provider_name

        search_result = SearchResult(
            response_result=api_response,
            provider_name=provider_name,
            query=self.api.query,
            page=page,
        )

        return search_result

    @classmethod
    def _validate_page_list_input(cls, pages: Sequence[int] | PageListInput) -> PageListInput:
        """Helper method for validating the input to pages: Used to coerce a sequence of pages to PageListInput if
        possible.

        Args:
            pages (Sequence[int] | PageListInput): The input to pass to search_pages containing
                                                   a sequence of pages to retrieve.

        Returns:
            PageListInput: If the conversion to a page_list_input object was successful.

        Raises:
            InvalidCoordinatorParameterException: If conversion to a page list is not possible.

        """
        try:
            page_list_input = pages if isinstance(pages, PageListInput) else PageListInput(pages)
            return page_list_input
        except ValidationError as e:
            raise InvalidCoordinatorParameterException(
                "Expected `pages` to be a list or other sequence of integer "
                f"pages. Received an error on validation: {e}"
            )

    def _process_page_result(self, response_result: Optional[ErrorResponse | ProcessedResponse], page: int) -> bool:
        """Helper method for logging the result of each page search and determining whether to continue."""
        halt = True

        if isinstance(response_result, ProcessedResponse):
            expected_page_count = self.search_api.config.records_per_page
            total_hits = response_result.total_query_hits

            # 0 and None signal that processing should halt or reference the expected_page_count, respectively
            pages_remaining = (
                ResponseMetadataMap._calculate_pages_remaining(page, total_hits, expected_page_count)
                if page is not None and total_hits is not None and expected_page_count is not None
                else None
            )

            if pages_remaining == 0 or (
                len(response_result.extracted_records or []) < expected_page_count and pages_remaining is None
            ):
                logger.warning(
                    f"The response for page, {page} contains less than the expected "
                    f"{expected_page_count} records. Received {repr(response_result)}. "
                    f"Halting multi-page retrieval..."
                )
            else:
                halt = False
        elif (response_result is None or isinstance(response_result, NonResponse)) and page == 0:
            logger.warning("Skipping the page number, 0, as it is not a valid page number...")
            halt = False

        elif isinstance(response_result, ErrorResponse) and not isinstance(response_result, NonResponse):
            status_code = response_result.status_code
            status_description = (
                f"(Status Code: {status_code}={response_result.status})" if status_code else "(Status Code: Missing)"
            )

            logger.warning(
                f"Received an invalid response for page {page}. "
                f"{status_description}. Halting multi-page retrieval..."
            )
        else:
            logger.warning(
                f"Could not retrieve a valid response code for page {page}. "
                f"Received {repr(response_result)}. Halting multi-page retrieval..."
            )
        return halt

    def search_data(self, page: int = 1, *args, **kwargs) -> Optional[List[Dict]]:
        """Public convenience method to perform a search, specifying the page and records per page.

        Note that instead of returning a ProcessedResponse or ErrorResponse, this calls the `search` method an
        retrieves only the list of processed dictionary records from the ProcessedResponse.

        Args:
            page (int): The current page number.
            *args: Positional arguments to pass directly to the `.search()` method
            **kwargs: Keyword arguments to pass directly to the `.search()` method

        Returns:
            Optional[List[Dict]]:
                A List of record dictionaries containing the processed article data when parsed successfully
                and records exist. If no records exist, or an error occurs somewhere within the processes,
                None is returned, instead.

        """
        try:
            response = self.search(page, *args, **kwargs)
            if response:
                return response.data

        except Exception as e:
            logger.error(f"An unexpected error occurred when attempting to retrieve the processed response data: {e}")
        return None

    # Search Execution
    def _search(
        self,
        page: Optional[int] = 1,
        from_request_cache: bool = True,
        from_process_cache: bool = True,
        normalize_records: Optional[bool] = None,
        **api_specific_parameters,
    ) -> Optional[ProcessedResponse | ErrorResponse]:
        """Helper method for retrieving and processing records from the API specifying the page and records per page.
        This method is called to perform all steps necessary to retrieve and process a response from the selected API.
        Beyond catching basic exceptions related to raised error codes and processing response issues, further errors
        are to be caught at a higher level such as in the public SearchCoordinator.search method.

        Args:
            page (int): The current page number. Used for process caching purposes even if not required by the API
            from_request_cache (bool): Indicates whether to attempt to retrieve the response from the requests-cache
            from_process_cache (bool): This parameter determines whether to attempt to pull processed responses from
                                       the processing cache storage device (or memory)

            normalize_records (Optional[bool]): Determines whether records should be normalized
            **api_specific_parameters (SearchAPIConfig): Fields to temporarily override when building the request.
        Returns:
            Optional[ProcessedResponse | ErrorResponse]:
                A Processed API Response if successful, Otherwise, returns an ErrorResponse

        """
        # all missing response values are handled at this step and transformed into NonResponses
        api_response = self._fetch_api_response(page, from_request_cache=from_request_cache, **api_specific_parameters)

        self._log_response_source(api_response.response, page, api_response.cache_key)

        # if there is no data to process within the response, return it as is
        if isinstance(api_response, NonResponse):
            return api_response

        # otherwise process the data before returning it
        processed_response = self._process_response(
            response=cast(ResponseProtocol, api_response.response),
            cache_key=cast(str, api_response.cache_key),
            from_process_cache=from_process_cache,
            normalize_records=normalize_records,
        )
        return processed_response

    # Request Handling
    def fetch(
        self,
        page: Optional[int],
        from_request_cache: bool = True,
        raise_on_error: bool = False,
        **api_specific_parameters,
    ) -> Optional[Response | ResponseProtocol]:
        """Fetches the raw response from the current API or from cache if available.

        If `page` is None, `fetch` will default to a basic parameter search using the API base URL given the specified
        parameters.

        Args:
            page (Optional[int]): The page number to retrieve from the cache.
            from_request_cache (bool): This parameter determines whether to try to fetch a valid response from cache.
            **api_specific_parameters (SearchAPIConfig): Fields to temporarily override when building the request.

        Returns:
            Optional[Response]: The response object if available, otherwise None.

        """
        current_page = str(page) if page is not None else f" for {self.api.base_url}"
        try:

            if from_request_cache:
                # attempts to retrieve the cached request associated with the page
                if response := self.get_cached_request(page, **api_specific_parameters):
                    return response
            else:
                # if the key does not exist, will log at the INFO level and continue
                self._delete_cached_request(page, **api_specific_parameters)
                self._respect_retry_after()

            response = self.robust_request(page, **api_specific_parameters)
            return response
        except RequestFailedException as e:
            msg = f"Failed to fetch page {current_page}"
            err = f"{msg}: {e}" if str(e) else msg
            logger.warning(err)
            if raise_on_error:
                raise RequestFailedException(err)
        return None

    def _respect_retry_after(self) -> None:
        """Helper method that respects `retry_after` field before requests exceed dynamic API rate limits."""
        # If the current URL has not changed from the last request, attempt to extract a Retry-After parameter directly
        last_response = self.last_response

        if (
            last_response is not None
            and last_response.url
            and normalize_url(self.api.base_url) == normalize_url(last_response.url, remove_parameters=True)
        ):

            # parsed `retry-after` value as a float - this accounts the amount of time that has elapsed since last-call
            retry_after_value = self.retry_handler.extract_retry_after_from_response(last_response.response)

            delay = self.retry_handler.parse_retry_after(retry_after_value)

            # if no delay exists, skip a delay
            if not delay:
                return

            # attempts to coerce the unparsed value into a numeric value
            retry_after_date = try_call(
                self.retry_handler._parse_retry_after_date, (retry_after_value,), suppress=(ValueError,), log_level=10
            )

            # Refer to the delay calculated from a valid `retry_after_date` as the source of truth when possible.
            # If not available, attempt to extract a creation date from the APIResponse container.
            reference_time = None if retry_after_date else parse_iso_timestamp(last_response.created_at or "")
            self.api.rate_limiter.wait_since(delay, reference_time)

    def robust_request(self, page: Optional[int], **api_specific_parameters) -> Optional[Response | ResponseProtocol]:
        """Constructs and sends a request to the current API. Fetches a response from the current API.

        Args:
            page (Optional[int]):
                The page number to retrieve from the cache. If missing, this implementation relies on
                `api_specific_parameters` to retrieve data from an API.
            **kwargs: Optional Additional parameters to pass to the SearchAPI
        Returns:
            Optional[Response]: The request object if available, otherwise None.

        """
        try:
            request_delay = api_specific_parameters.get("request_delay") or self.api.request_delay

            if api_specific_parameter_fields := self.api.parameter_config.extract_parameters(api_specific_parameters):
                api_specific_parameters["parameters"] = api_specific_parameter_fields

            response = self.retry_handler.execute_with_retry(
                request_func=self.search_api.search,
                validator_func=self.validator.validate_response,
                sleep_func=self.api.rate_limiter.sleep,
                page=page,
                min_retry_delay=request_delay,
                backoff_factor=min(request_delay * 0.25, 0.5),
                **api_specific_parameters,
            )

        except RequestFailedException as e:
            msg = f"Failed to get a valid response from the {self.search_api.provider_name} API"
            err = f"{msg}: {e}" if str(e) else msg
            logger.error(err)
            raise RequestFailedException(err) from e

        if getattr(response, "from_cache", False):
            logger.info(f"Retrieved cached response for query: {self.search_api.query} and page: {page}")
        return response

    def get_cached_request(self, page: Optional[int], **kwargs) -> Optional[Response | ResponseProtocol]:
        """Retrieves the cached request for a given page number if available.

        Args:
            page (Optional[int]): The page number to retrieve from the cache.
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

    def get_cached_response(self, page: int, url: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Retrieves the cached response for a given page number if available.

        Args:
            page (int): The page number to retrieve from the cache.
            url (Optional[str]): The request URL for parameter-based cache keys. Used when page is None.

        Returns:
            Optional[Dict[str, Any]]: The cached response data if available, otherwise None.

        """
        try:
            if not self.response_coordinator.cache_manager:
                return None
            cache_key = self._create_cache_key(page, url)
            cached = self.response_coordinator.cache_manager.retrieve(cache_key)
            if cached:
                logger.info(f"Cache hit for key: {cache_key}")
                return cached
            logger.info(f"Cache miss for key: {cache_key}")
            return None
        except StorageCacheException as e:
            logger.error(f"Error retrieving cached response: {e}")
            return None

    def _fetch_api_response(
        self, page: Optional[int], from_request_cache: bool = True, **api_specific_parameters
    ) -> APIResponse:
        """Helper method for fetching the response and retrieving the cache key.

        Args:
            page (Optional[int]): The page number to retrieve from the cache.
            from_request_cache (bool): This parameter determines whether to try to fetch a valid response from cache.
            **api_specific_parameters (SearchAPIConfig): Fields to temporarily override when building the request.

        Returns:
            APIResponse | NonResponse: A data class containing the response and cache key when successfully retrieved,
                                       independent of status code, and a NonResponse otherwise when retrieval is
                                       unsuccessful due to an error.

        """
        cache_key = self._create_cache_key(page) if page is not None else None
        try:
            response = self.fetch(
                page, from_request_cache=from_request_cache, raise_on_error=True, **api_specific_parameters
            )
            if not cache_key and response and response.url:
                cache_key = self._create_cache_key(page=None, url=response.url)
        except RequestFailedException as e:
            return NonResponse.from_error(error=e, message=str(e), cache_key=cache_key)

        if not response:
            logger.info(f"Response retrieval for cache key {cache_key} was unsuccessful.")
        return APIResponse(response=response, cache_key=cache_key)

    def _log_response_source(
        self, response: Optional[Response | ResponseProtocol], page: Optional[int], cache_key: Optional[str]
    ) -> None:
        """Logs and indicates whether the received response is fresh or retrieved from session cache.

        The response structure is checked to determine whether a response is a `requests_cache.CachedResponse` or
        whether it was retrieved directly from the current API. This method also indicates whether we're using the
        response processing cache from the `ResponseCoordinator` to attempt to pull from cache if available.

        Args:
            response (Response): Response retrieved from a request.
            page (int): The current page number.
            cache_key (Optional[str]): An optional cache key associated with the current request.

        """
        current_page = str(page) if page is not None else getattr(response, "url", None)
        current_page = f"page {current_page}" if current_page else "the current page"

        if not response:
            logger.warning(f"Response retrieval and processing for {current_page} was unsuccessful.")
            return

        if getattr(response, "from_cache", False):
            logger.info(f"Retrieved a cached response for cache key: {cache_key}")

        if self.response_coordinator.cache_manager:
            logger.info(f"Handling response (cache key: {cache_key})")
        else:
            logger.info("Handling response")

    def _process_response(
        self,
        response: Response | ResponseProtocol,
        cache_key: str,
        from_process_cache: bool = True,
        normalize_records: Optional[bool] = None,
    ) -> Optional[ProcessedResponse | ErrorResponse]:
        """
        Helper method for processing records from the API and, upon success, saving records to cache
        if from_process_cache = True and caching is enabled.

        Args:
            response (Optional[Response]): The response retrieved from an API
            cache_key (Optional[str]): The key used for caching responses, data processing, and metadata when enabled
            from_process_cache (bool): Indicates whether or not to pull from cache when available.
                                       This option is only relevant when a caching backend is enabled.
            normalize_records (Optional[bool]): Determines whether records should be normalized after processing

        Returns:
            Optional[ProcessedResponse | ErrorResponse]:
                A Processed API Response if successful, Otherwise, returns an ErrorResponse
        """
        # assume that the entered value is a response protocol to be further validated when handled
        processed_response = self.response_coordinator.handle_response(
            response,
            cache_key,
            from_cache=from_process_cache,
            normalize_records=normalize_records,
        )

        if isinstance(processed_response, (ErrorResponse, ProcessedResponse)):
            self.last_response = processed_response

        return processed_response

    def _prepare_request(self, page: Optional[int], **kwargs) -> PreparedRequest:
        """Prepares the request after constructing the request parameters for the API call.

        If neither a page nor extra keyword arguments are prepared, the request URL defaults
        to the base URL.

        Supports two parameter styles that are functionally equivalent:
            - Nested: `_prepare_request(page=None, parameters={'filter': 'value'})`
            - Flat: `_prepare_request(page=None, filter='value')`

        When both are provided, flat kwargs take precedence over nested parameters.

        Args:
            page (Optional[int]): The page number to request.
            **kwargs:
                Additional parameters for the request. Can include a 'parameters' dict that will be merged with other
                kwargs. Note that the `endpoint` parameter is directly extracted from the parameter list and formatted
                as a valid endpoint, separate from the parameter list. No preprocessing for `endpoint` is required.

        Returns:
            PreparedRequest: The prepared request object to send to the api

        """
        parameters = self.api._validate_parameters((kwargs.pop("parameters", {}))) | kwargs
        endpoint = parameters.pop("endpoint", None)
        request = self.search_api.prepare_search(page, parameters, endpoint=endpoint)
        return request

    # Cache Management
    def _create_cache_key(self, page: Optional[int], url: Optional[str] = None) -> str:
        """Combines information about the query type and current page to create an identifier for the current query.

        The cache key is generated using the current page argument, as well as the provider_name, query, and
        records_per_page, all of which originate from the SearchAPIConfig (accessible as properties). If a page
        parameter is not provided and a valid URL is given, a cache key can instead be calculated by hashing the URL
        with hashlib's sha256 implementation (via `DataCacheManager._cache_key_from_url`) when possible. As a result,
        consistency in cache key formation is guaranteed for the same input.

        Args:
            page (Optional[int]): The current page number. None for parameter-based searches.
            url (Optional[str]): The request URL for parameter-based cache keys. Used when page is None.

        Returns:
            str: A unique cache key based on the provided parameters.

        """
        if not page and url is not None and validate_url(url, verbose=False):
            return DataCacheManager._cache_key_from_url(url)
        return (
            f"{self.search_api.provider_name}_{self.search_api.query}_{page}_{self.search_api.records_per_page}".lower()
        )

    def _get_request_key(self, page: Optional[int], **kwargs) -> Optional[str]:
        """Creates a request key from the requests session cache if available.

        If a page is not supplied (is NA), then keyword arguments are instead
        used to generate a cache key from the prepared request.

        Args:
            page (Optional[int]): The page number associated with the request key.
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

    def _delete_cached_request(self, page: Optional[int], **kwargs) -> None:
        """Deletes the cached request for a given page number if available.

        Args:
            page (Optional[int]): The page number to delete from the cache.

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

    def _delete_cached_response(self, page: Optional[int], url: Optional[str] = None) -> None:
        """Deletes the cached response for a given page number if available.

        Args:
            page (int): The page number to delete from the cache.
            url (Optional[str]): The request URL for parameter-based cache keys. Used when page is None.

        """
        if self.response_coordinator.cache_manager:
            try:
                cache_key = self._create_cache_key(page, url)
                logger.debug(f"Attempting to delete processing cache key: {cache_key}")
                self.response_coordinator.cache_manager.delete(cache_key)
            except Exception as e:
                logger.error(f"Error in deleting from processing cache: {e}")


__all__ = ["SearchCoordinator"]
