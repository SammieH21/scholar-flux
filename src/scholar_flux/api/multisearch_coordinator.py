# /api/search_coordinator.py
"""Defines the MultiSearchCoordinator that builds on the features implemented by the SearchCoordinator to create
multiple queries to different providers either sequentially or by using multithreading.

This implementation uses shared rate limiting to ensure that rate limits to different providers are not exceeded.

"""
from __future__ import annotations
from typing import Optional, Generator, Sequence, Iterable
from concurrent.futures import ThreadPoolExecutor
import concurrent.futures
import logging

from collections import UserDict, defaultdict
from scholar_flux.api import ProviderConfig
from scholar_flux.utils import generate_repr_from_string
from scholar_flux.api.models import SearchResultList, SearchResult, PageListInput
from scholar_flux.api.rate_limiting import threaded_rate_limiter_registry
from scholar_flux.api import SearchAPI, SearchCoordinator, ErrorResponse, APIResponse, NonResponse
from scholar_flux.exceptions import InvalidCoordinatorParameterException


logger = logging.getLogger(__name__)


class MultiSearchCoordinator(UserDict):
    """The MultiSearchCoordinator is a utility class for orchestrating searches across multiple providers, pages, and
    queries sequentially or using multithreading. This coordinator builds on the SearchCoordinator's core structure to
    ensure consistent, rate-limited API requests.

    The multi-search coordinator uses shared rate limiters to ensure that requests to the same provider (even across
    different queries) will use the same rate limiter.

    This implementation uses the `ThreadedRateLimiter.min_interval` parameter from the shared rate limiter of each
    provider to determine the `request_delay` across all queries. These settings can be found and modified in the
    `scholar_flux.api.providers.threaded_rate_limiter_registry` by `provider_name`.

    For new, unregistered providers, users can override the `MultiSearchCoordinator.DEFAULT_THREADED_REQUEST_DELAY`
    class variable to adjust the shared request_delay.

    # Examples:

        >>> from scholar_flux import MultiSearchCoordinator, SearchCoordinator, RecursiveDataProcessor
        >>> from scholar_flux.api.rate_limiting import threaded_rate_limiter_registry
        >>> multi_search_coordinator = MultiSearchCoordinator()
        >>> threaded_rate_limiter_registry['arxiv'].min_interval = 6 # arbitrary rate limit (seconds per request)
        >>>
        >>> # Create coordinators for different queries and providers
        >>> coordinators = [
        ...     SearchCoordinator(
        ...         provider_name=provider,
        ...         query=query,
        ...         processor=RecursiveDataProcessor(),
        ...         user_agent="SammieH",
        ...         cache_requests=True
        ...     )
        ...     for query in ('ml', 'nlp')
        ...     for provider in ('plos', 'arxiv', 'openalex', 'crossref')
        ... ]
        >>>
        >>> # Add coordinators to the multi-search coordinator
        >>> multi_search_coordinator.add_coordinators(coordinators)
        >>>
        >>> # Execute searches across multiple pages
        >>> all_pages = multi_search_coordinator.search_pages(pages=[1, 2, 3])
        >>>
        >>> # filters and retains successful requests from the multi-provider search
        >>> filtered_pages = all_pages.filter()
        >>> # The results will contain successfully processed responses across all queries, pages, and providers
        >>> print(filtered_pages)  # Output will be a list of SearchResult objects
        >>> # Extracts successfully processed records into a list of records where each record is a dictionary
        >>> record_dict = filtered_pages.join() # retrieves a list of records
        >>> print(record_dict)  # Output will be a flattened list of all records

    """

    DEFAULT_THREADED_REQUEST_DELAY: float | int = 6.0

    def __init__(self, *args, **kwargs):
        """Initializes the MultiSearchCoordinator, allowing positional and keyword arguments to be specified when
        creating the MultiSearchCoordinator.

        The initialization of the MultiSearchCoordinator operates similarly to that of a regular dict with the caveat
        that values are statically typed as SearchCoordinator instances.

        """
        super().__init__(*args, **kwargs)

    def __setitem__(
        self,
        key: str,
        value: SearchCoordinator,
    ) -> None:
        """Sets an item in the MultiSearchCoordinator.

        Args:
            key (str): The key used to retrieve a SearchCoordinator
            value (SearchCoordinator): The value (SearchCoordinator) to associate with the key.

        Raises:
            InvalidCoordinatorParameterException: If the value is not a SearchCoordinator instance.

        """

        self._verify_search_coordinator(value)
        super().__setitem__(key, value)

    @classmethod
    def _verify_search_coordinator(cls, search_coordinator: SearchCoordinator):
        """Helper method that ensures that the current value is a SearchCoordinator.

        Raises:
            InvalidCoordinatorParameterException: If the received value is not a SearchCoordinator instance

        """
        if not isinstance(search_coordinator, SearchCoordinator):
            raise InvalidCoordinatorParameterException(
                f"Expected a SearchCoordinator, received type {type(search_coordinator)}"
            )

    @property
    def coordinators(self) -> list[SearchCoordinator]:
        """Utility property for quickly retrieving a list of all currently registered coordinators."""
        return list(self.data.values())

    def add(self, search_coordinator: SearchCoordinator):
        """Adds a new SearchCoordinator to the MultiSearchCoordinator instance.

        Args:
            search_coordinator (SearchCoordinator): A search coordinator to add to the MultiSearchCoordinator dict

        Raises: InvalidCoordinatorParameterException: If the expected type is not a SearchCoordinator

        """
        self._verify_search_coordinator(search_coordinator)
        search_coordinator = self._normalize_rate_limiter(search_coordinator)
        key = self._create_key(search_coordinator)

        # skipping re-evaluation via __setitem___
        super().__setitem__(key, search_coordinator)

    def add_coordinators(self, search_coordinators: Iterable[SearchCoordinator]):
        """Helper method for adding a sequence of coordinators at a time."""

        # ignore flagging singular coordinators as invalid by adding them to a list beforehand
        search_coordinators = (
            [search_coordinators] if isinstance(search_coordinators, SearchCoordinator) else search_coordinators
        )

        if not isinstance(search_coordinators, (Sequence, Iterable)) or isinstance(search_coordinators, str):
            raise InvalidCoordinatorParameterException(
                f"Expected a sequence or iterable of search_coordinators, received type {type(search_coordinators)}"
            )

        for search_coordinator in search_coordinators:
            self.add(search_coordinator)

    def search(
        self,
        page: int = 1,
        iterate_by_group: bool = False,
        max_workers: Optional[int] = None,
        multithreading: bool = True,
        **kwargs,
    ) -> SearchResultList:
        """Public method used to search for a single or multiple pages from multiple providers at once using a
        sequential or multithreading approach. This approach delegates the search to search_pages to retrieve a single
        page for query and provider using an iterative approach to search for articles grouped by provider.

        Note that the `MultiSearchCoordinator.search_pages` method uses shared rate limiters to ensure
        that APIs are not overwhelmed by the number of requests being sent within a specific time interval.

        Args:
            pages (Sequence[int]): A sequence of page numbers to iteratively request from the API Provider.
            iterate_by_group (bool):
                Determines whether all searches should be performed by page or by group. Note that page-based
                iteration is significantly faster due to API rate limits. This is set to `False` by default as a result.
            max_workers (Optional[int]):
                Determines how many threads should operate at one time. Applies when only when `multithreading` is
                set to `True`. When `None`, as many threads are used as required.
            multithreading (bool):
                Multithreading is used when this parameter is set to `True`. Otherwise, sequential iteration is
                performed. Multithreading is enabled by default.
            from_request_cache (bool):
                This parameter determines whether to try to retrieve the response from the requests-cache storage.
            from_process_cache (bool):
                This parameter determines whether to attempt to pull processed responses from the cache storage.
            use_workflow (bool):
                Indicates whether to use a workflow if available Workflows are utilized by default.

        Returns:
            SearchResultList:
                The list containing all retrieved and processed pages from the API. If any non-stopping errors occur,
                this will return an ErrorResponse instead with error and message attributes further explaining any
                issues that occurred during processing.

        """
        return self.search_pages(
            pages=[page] if isinstance(page, int) else page,
            iterate_by_group=iterate_by_group,
            max_workers=max_workers,
            multithreading=multithreading,
            **kwargs,
        )

    def search_page(
        self,
        page: int = 1,
        **kwargs,
    ) -> SearchResultList:
        """Retrieves a single page from all registered coordinators.

        This method provides API compatibility with SearchCoordinator.search_page, returning results wrapped in
        SearchResult containers with provider metadata.

        Args:
            page (int):
                The page number to retrieve from each provider.
            **kwargs:
                Additional arguments to pass to `MultiSearchCoordinator.search_pages` or the `search_pages` method
                for each individual coordinator
                method otherwise.

        Returns:
            SearchResultList: Results from all coordinators for the specified page.

        """
        return self.search_pages(
            pages=[page] if isinstance(page, int) else page,
            **kwargs,
        )

    def search_pages(
        self,
        pages: Sequence[int] | PageListInput,
        iterate_by_group: bool = False,
        max_workers: Optional[int] = None,
        multithreading: bool = True,
        **kwargs,
    ) -> SearchResultList:
        """Public method used to search articles from multiple providers at once using a sequential or multithreading
        approach. This approach uses `iter_pages` under the.

        Note that the `MultiSearchCoordinator.search_pages` method uses shared rate limiters to ensure
        that APIs are not overwhelmed by the number of requests being sent within a specific time interval.

        Args:
            pages (Sequence[int]): A sequence of page numbers to iteratively request from the API Provider.
            from_request_cache (bool): This parameter determines whether to try to retrieve the response from the
                                       requests-cache storage.
            from_process_cache (bool): This parameter determines whether to attempt to pull processed responses from
                                       the cache storage.
            use_workflow (bool): Indicates whether to use a workflow if available Workflows are utilized by default.

        Returns:
            SearchResultList: The list containing all retrieved and processed pages from the API. If any non-stopping
                              errors occur, this will return an ErrorResponse instead with error and message attributes
                              further explaining any issues that occurred during processing.

        """

        search_results = SearchResultList()

        if max_workers is not None and not isinstance(max_workers, int):
            raise InvalidCoordinatorParameterException(
                "Expected max_workers to be a positive integer, " f"Received a value of type {type(max_workers)}"
            )

        pages = SearchCoordinator._validate_page_list_input(pages)

        if not self.data:
            logger.warning(
                "A coordinator has not yet been registered with the MultiSearchCoordinator: "
                "returning an empty list..."
            )
            return search_results

        if multithreading:
            search_iterator: Generator[SearchResult, None, None] = self.iter_pages_threaded(
                pages, max_workers=max_workers, **kwargs
            )
        else:
            search_iterator = self.iter_pages(pages, iterate_by_group=iterate_by_group, **kwargs)

        for search_result in search_iterator:
            search_results.append(search_result)

        logging.debug("Completed multi-search coordinated retrieval and processing")

        return search_results

    def iter_pages(
        self, pages: Sequence[int] | PageListInput, iterate_by_group: bool = False, **kwargs
    ) -> Generator[SearchResult, None, None]:
        """Helper method that creates and joins a sequence of generator functions for retrieving and processing records
        from each combination of queries, pages, and providers in sequence. This implementation uses the
        SearchCoordinator.iter_pages to dynamically identify when page retrieval should halt for each API provider,
        accounting for errors, timeouts, and less than the expected amount of records before filtering records with pre-
        specified criteria.

        Args:
            pages (Sequence[int]): A sequence of page numbers to iteratively request from the API Provider.
            from_request_cache (bool): This parameter determines whether to try to retrieve the response from the
                                       requests-cache storage.
            from_process_cache (bool): This parameter determines whether to attempt to pull processed responses from
                                       the cache storage.
            use_workflow (bool): Indicates whether to use a workflow if available Workflows are utilized by default.

        Yields:
            SearchResult: Iteratively returns the SearchResult for each provider, query, and page using a generator
                          expression. Each result contains the requested page number (page), the name of the provider
                          (provider_name), and the result of the search containing a ProcessedResponse,
                          an ErrorResponse, or None (api response)

        """

        # to eventually be used for threading by provider where each is assigned to the same chain
        provider_search_dict = self.group_by_provider()

        # creates a dictionary of generators grouped by provider. On each yield, each generator retrieves a single page
        provider_generator_dict = {
            provider_name: self._process_provider_group(group, pages, **kwargs)
            for provider_name, group in provider_search_dict.items()
        }

        if iterate_by_group:
            # Retrieve all pages from a single provider before moving to the next provider
            yield from self._grouped_iteration(provider_generator_dict)

        else:
            # Retrieve a single page number for all providers before moving to the next page
            yield from self._round_robin_iteration(provider_generator_dict)

    @classmethod
    def _grouped_iteration(
        cls, provider_generator_dict: dict[str, Generator[SearchResult, None, None]]
    ) -> Generator[SearchResult, None, None]:
        """Helper method for iteratively retrieves all pages from a single provider before moving to the next.

        Args:
            generator_dict (Mapping[str, Generator[SearchResult, None, None]]):
                A dictionary containing provider names as keys and generators as values.

        Yields:
            SearchResult: A search result containing the provider name, query, and page, and response from each
                          API Provider

        """

        for provider_name, generator in provider_generator_dict.items():
            yield from cls._process_page_generator(provider_name, generator)

    @classmethod
    def _round_robin_iteration(
        cls, provider_generator_dict: dict[str, Generator[SearchResult, None, None]]
    ) -> Generator[SearchResult, None, None]:
        """Helper method for iteratively yielding each page from each provider in a cyclical order. This method is
        implemented to ensure faster iteration given common rate-limits associated with API Providers. Note that the
        received generator dictionary will be popped as each generator is consumed.

        Args:
            provider_generator_dict (Mapping[str, Generator[SearchResult, None, None]]):
                A dictionary containing provider names as keys and generators as values.

        Yields:
            SearchResult: A search result containing the provider name, query, and page, and response from each
                          API Provider

        """

        while provider_generator_dict:
            inactive_generators = []
            for provider_name, generator in provider_generator_dict.items():
                try:
                    yield next(generator)
                # If successful, put it back at the end
                except StopIteration:
                    logger.debug(f"Successfully halted retrieval for provider, {provider_name}")
                    inactive_generators.append(provider_name)
                except Exception as e:
                    logger.error(
                        "Encountered an unexpected error during iteration for provider, " f"{provider_name}: {e}"
                    )
                    inactive_generators.append(provider_name)

            for provider_name in inactive_generators:
                provider_generator_dict.pop(provider_name)

    def iter_pages_threaded(
        self, pages: Sequence[int] | PageListInput, max_workers: Optional[int] = None, **kwargs
    ) -> Generator[SearchResult, None, None]:
        """Threading by provider to respect rate limits Helper method that implements threading to simultaneously
        retrieve a sequence of generator functions for retrieving and processing records from each combination of
        queries, pages, and providers in a multi-threaded set of sequences grouped by provider.

        This implementation also uses the SearchCoordinator.iter_pages to dynamically identify when page retrieval
        should halt for each API provider, accounting for errors, timeouts, and less than the expected amount of
        records before filtering records with pre-specified criteria.

        Note, that as threading is performed by provider, this method will not differ significantly in speed from
        the `MultiSearchCoordinator.iter_pages` method if only a single provider has been specified.

        Args:
            pages (Sequence[int] | PageListInput): A sequence of page numbers to request from the API Provider.
            from_request_cache (bool): This parameter determines whether to try to retrieve the response from the
                                       requests-cache storage.
            from_process_cache (bool): This parameter determines whether to attempt to pull processed responses from
                                       the cache storage.
            use_workflow (bool): Indicates whether to use a workflow if available Workflows are utilized by default.

        Yields:
            SearchResult: Iteratively returns the SearchResult for each provider, query, and page using a generator
                          expression as each SearchResult becomes available after multi-threaded processing.
                          Each result contains the requested page number (page), the name of the provider
                          (provider_name), and the result of the search containing a ProcessedResponse, an ErrorResponse,
                          or None (api response)

        """

        provider_groups = self.group_by_provider()

        workers = max_workers if max_workers is not None else min(8, len(provider_groups) or 1)
        if workers < 1:
            logger.warning(f"The value for workers ({workers}) is non-positive: defaulting to 1 worker")
            workers = 1

        # creates a dictionary of generators grouped by provider. On each yield, each generator retrieves a single page
        provider_generator_dict = {
            provider_name: self._process_provider_group(group, pages, **kwargs)
            for provider_name, group in provider_groups.items()
        }

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [
                executor.submit(list, self._process_page_generator(provider_name, generator))
                for provider_name, generator in provider_generator_dict.items()
            ]

            for future in concurrent.futures.as_completed(futures):
                yield from future.result()

    @classmethod
    def _process_page_generator(
        cls, provider_name: str, generator: Generator[SearchResult, None, None]
    ) -> Generator[SearchResult, None, None]:
        """Helper method for safely consuming a generator, accounting for errors that could stop iteration during
        threaded retrieval of page data.

        Args:
            provider_name (str): The name of the current provider
            generator (Generator[SearchResult, None, None]):
                A generator that returns a SearchResult upon the successful retrieval of the next page

        Yields:
            SearchResult: The next search result from the generator if there is at least one more page to retrieve

        """
        try:
            yield from generator
            logger.debug(f"Successfully halted retrieval for provider, {provider_name}")

        except Exception as e:
            logger.error("Encountered an unexpected error during iteration for provider, " f"{provider_name}: {e}")

    def _process_provider_group(
        self, provider_coordinators: dict[str, SearchCoordinator], pages: Sequence[int] | PageListInput, **kwargs
    ) -> Generator[SearchResult, None, None]:
        """Helper method used to process all queries and pages for a single provider under a common thread. This method
        is especially useful during multithreading given that API Providers often have hard limits on the total number
        of requests that can be sent within a provider-specific interval.

        Args:
            provider_coordinators (dict[str, SearchCoordinator]):
                A dictionary of all coordinators corresponding to a single provider.
            pages (Sequence[int] | PageListInput): A list, set, or other common sequence of integer page numbers
                                    corresponding to records/articles to iteratively request from the API Provider.
            **kwargs: Keyword arguments to pass to the `iter_pages` method call to facilitate single or multithreaded
                      record page retrieval

        Yields:
           SearchResult: Iteratively returns the SearchResult for each provider, query, and page using a generator
                          expression as each SearchResult becomes available after multi-threaded processing.
                          Each result contains the requested page number (page), the name of the provider
                          (provider_name), and the result of the search containing a ProcessedResponse, an ErrorResponse,
                          or None (api response)

        """
        # All coordinators in this group share the same threaded rate limiter

        # will be used to flag non-retryable error codes from the provider for early stopping across queries if needed
        last_response: Optional[APIResponse] = None
        for search_coordinator in provider_coordinators.values():
            provider_name = ProviderConfig._normalize_name(search_coordinator.api.provider_name)

            if (
                isinstance(last_response, ErrorResponse)
                and not isinstance(last_response, NonResponse)
                and isinstance(last_response.status_code, int)
                and last_response != 200
                and last_response.status_code not in search_coordinator.retry_handler.retry_statuses
            ):
                # breaks if a non-retryable status code is encountered.
                logger.warning(
                    f"Encountered a non-retryable response during retrieval: {last_response}. "
                    f"Halting retrieval for provider, {provider_name}"
                )
                break

            # retrieve the rate from within the threaded rate limiter
            default_request_delay = search_coordinator.api._rate_limiter.min_interval
            request_delay = kwargs.pop("request_delay", default_request_delay)

            # iterate over the current coordinator given its session, query, and settings
            for page in search_coordinator.iter_pages(pages, **kwargs, request_delay=request_delay):
                if isinstance(page, SearchResult):
                    last_response = page.response_result
                yield page

    def current_providers(self) -> set[str]:
        """Extracts a set of names corresponding to the each API provider assigned to the MultiSearchCoordinator."""
        return {ProviderConfig._normalize_name(coordinator.api.provider_name) for coordinator in self.data.values()}

    def group_by_provider(self) -> dict[str, dict[str, SearchCoordinator]]:
        """Groups all coordinators by provider name to facilitate retrieval with normalized components where needed.
        Especially helpful in the latter retrieval of articles when using multithreading by provider (as opposed to by
        page) to account for strict rate limits. All coordinated searches corresponding to a provider would appear under
        a nested dictionary to facilitate orchestration on the same thread with the same rate limiter.

        Returns:
            dict[str, dict[str, SearchCoordinator]]:
                All elements in the final dictionary map provider-specific coordinators to the normalized provider name
                for the nested dictionary of coordinators.

        """

        provider_search_dict: dict[str, dict[str, SearchCoordinator]] = defaultdict(dict)
        for key, coordinator in self.data.items():
            provider_name = ProviderConfig._normalize_name(coordinator.api.provider_name)
            provider_search_dict[provider_name][key] = coordinator
        return dict(provider_search_dict)

    def _normalize_rate_limiter(self, search_coordinator: SearchCoordinator):
        """Helper method that retrieves the threaded rate_limiter for the coordinator's provider and normalizes the rate
        limiter used for searches."""
        provider_name = ProviderConfig._normalize_name(search_coordinator.api.provider_name)

        # ensure that the same rate limiter is used with threading if needed to ensure rate limiting across providers
        # if the provider doesn't already exist, initialize the provider rate limiter in the registry
        threaded_rate_limiter = threaded_rate_limiter_registry.get_or_create(
            provider_name, self.DEFAULT_THREADED_REQUEST_DELAY
        )

        if threaded_rate_limiter:
            search_coordinator.api = SearchAPI.update(search_coordinator.api, rate_limiter=threaded_rate_limiter)
        return search_coordinator

    @classmethod
    def _create_key(cls, search_coordinator: SearchCoordinator):
        """Create a hashed key from a coordinator using the provider name, query, and structure of the
        SearchCoordinator."""
        hash_value = hash(repr(search_coordinator))
        provider_name = ProviderConfig._normalize_name(search_coordinator.api.provider_name)
        query = str(search_coordinator.api.query)
        key = f"{provider_name}_{query}:{hash_value}"
        return key

    def select(
        self,
        query: Optional[str] = None,
        provider_name: Optional[str] = None,
    ) -> list[SearchCoordinator]:
        """Helper method that enables the selection of coordinators based on their query or provider name."""
        provider_name = (
            ProviderConfig._normalize_name(provider_name) if isinstance(provider_name, str) else provider_name
        )
        return [
            coordinator
            for coordinator in self.coordinators
            if (query is None or query == coordinator.api.query)
            and provider_name is None
            or provider_name == coordinator.api.provider_name
        ]

    def structure(self, flatten: bool = False, show_value_attributes: bool = True) -> str:
        """Helper method that shows the current structure of the MultiSearchCoordinator."""
        class_name = self.__class__.__name__
        attributes = {key: coordinator.summary() for key, coordinator in self.data.items()}
        return generate_repr_from_string(class_name, attributes)

    def __repr__(self) -> str:
        """Helper method for generating a string representation of the current list of coordinators."""
        return self.structure()


__all__ = ["MultiSearchCoordinator"]
