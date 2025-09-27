from __future__ import annotations
from typing import Optional, Generator, Sequence, Iterable
from concurrent.futures import ThreadPoolExecutor
import concurrent
import logging

from collections import UserDict, defaultdict
from scholar_flux.api import ProviderConfig
from scholar_flux.utils import generate_repr_from_string
from scholar_flux.api.models import SearchResultList, SearchResult
from scholar_flux.api.rate_limiting import threaded_rate_limiter_registry, ThreadedRateLimiter
from scholar_flux.api import SearchAPI, SearchCoordinator, ErrorResponse, APIResponse


logger = logging.getLogger(__name__)


class MultiSearchCoordinator(UserDict):
    """
    The MultiSearchCoordinator is a utility method for orchestrating searchs for multiple providers, pages, and
    queries in sequence. This coordinator uses the overall structure of the SearchCoordinator in order to orchestrate
    searches for articles from APIs in a consistently rate-limited manner.

    The multi-search coordinator makes heavy use of normalized rate limiters where requests to the same providers, even
    across different queries, use the same rate limiter. For new providers, the minimum request delay can be
    directly set by overriding the `MultiSearchCoordinator.DEFAULT_THREADED_REQUEST_DELAY` class variable.
    """

    DEFAULT_THREADED_REQUEST_DELAY: int = 6

    def __init__(self, *args, **kwargs):
        """
        Initializes the MultiSearchCoordinator, allowing positional and keyword arguments to be specified when
        creating the MultiSearchCoordinator. The initialzation of the MultiSearchCoordinator operates similarly
        to that of a regular dict with the caveat that values are statically typed as SearchCoordinator instances.
        """
        super().__init__(*args, **kwargs)

    def __setitem__(
        self,
        key: str,
        value: SearchCoordinator,
    ) -> None:
        """
        Sets an item in the MultiSearchCoordinator

        Args:
            key (str): The key used to retrieve a SearchCoordinator
            value (SearchCoordinator): The value (SearchCoordinator) to associate with the key.

        Raises:
            TypeError: If the value is not a SearchCoordinator instance.
        """

        self._verify_search_coordinator(value)
        super().__setitem__(key, value)

    @classmethod
    def _verify_search_coordinator(cls, search_coordinator: SearchCoordinator):
        """
        Helper method that ensures that the current value is a SearchCoordinator.

        Raises:
            TypeError: If the received value is not a SearchCoordinator instance
        """
        if not isinstance(search_coordinator, SearchCoordinator):
            raise TypeError(f"Expected a SearchCoordinator, received type {type(search_coordinator)}")

    def add(self, search_coordinator: SearchCoordinator):
        """
        Adds a new SearchCoordinator to the MultiSearchCoordinator instance

        Args:
            search_coordinator (SearchCoordinator): A search coordinator to add to the MultiSearchCoordinator dict

        Raises: TypeError: If the expected type is not a SearchCoordinator
        """
        self._verify_search_coordinator(search_coordinator)
        search_coordinator = self._normalize_rate_limiter(search_coordinator)
        key = self._create_key(search_coordinator)

        # skipping re-evaluation via __setitem___
        super().__setitem__(key, search_coordinator)

    def add_coordinators(self, search_coordinators: Iterable[SearchCoordinator]):
        """Helper method for adding a sequence of coordinators at a time"""
        if not isinstance(search_coordinators, (Sequence, Iterable)):
            raise TypeError(
                "Expected a sequence or iterable of search_coordinators, " f"received type {type(search_coordinators)}"
            )

        for search_coordinator in search_coordinators:
            self.add(search_coordinator)

    def iter_pages(self, pages: Sequence[int], iterate_by_group: bool = False, **kwargs):
        """
        Helper method that creates and joins a sequence of generator functions for retrieving and processing
        records from each combination of queries, pages, and providers in sequence.
        This implementation uses the SearchCoordinator.iter_pages to dynamically identify when page retrieval
        should halt for each API provider, accounting for errors, timeouts, and less than the expected amount of
        records before filtering records with prespecified criteria.

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

        logging.debug("Completed multi-search coordinated retrieval and processing")

    @classmethod
    def _grouped_iteration(
        cls, provider_generator_dict: dict[str, Generator[SearchResult, None, None]]
    ) -> Generator[SearchResult, None, None]:
        """
        Helper method for iteratively retrieves all pages from a single provider before moving to the next.

        Args:
            generator_dict (Mapping[str, Generator[SearchResult, None, None]]):
                A dictionary containing provider names as keys and generators as values.

        Yields:
            SearchResult: A search result containing the provider name, query, and page, and response from each
                          API Provider
        """

        for provider_name, generator in provider_generator_dict.items():

            try:
                yield from generator
                logger.debug(f"Successfully halted retrieval for provider, {provider_name}")

            except Exception as e:
                logger.debug("Encountered an unexpected error during iteration for provider, " f"{provider_name}: {e}")

    @classmethod
    def _round_robin_iteration(
        cls, provider_generator_dict: dict[str, Generator[SearchResult, None, None]]
    ) -> Generator[SearchResult, None, None]:
        """
        Helper method for iteratively yielding each page from each provider in a cyclical order. This method is
        implemented to ensure faster iteration given common rate-limits associated with API Providers.
        Note that the received generator dictionary will be popped as each generator is consumed.

        Args:
            generator_dict (Mapping[str, Generator[SearchResult, None, None]]):
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
                    logger.debug(
                        "Encountered an unexpected error during iteration for provider, " f"{provider_name}: {e}"
                    )
                    inactive_generators.append(provider_name)

            for provider_name in inactive_generators:
                provider_generator_dict.pop(provider_name)

    def iter_pages_threaded(self, pages, max_workers=None, **kwargs):
        """
        Threading by provider to respect rate limits
        Helper method that implements threading to simultaneously retrieve a sequence of generator functions
        for retrieving and processing records from each combination of queries, pages, and providers in a
        multi-threaded set of sequences grouped by provider.

        This implementation also uses the SearchCoordinator.iter_pages to dynamically identify when page retrieval
        should halt for each API provider, accounting for errors, timeouts, and less than the expected amount of
        records before filtering records with prespecified criteria.

        Note, that as threading is performed by provider, this method will not differ significantly in speed from
        the `MultiSearchCoordinator.iter_pages` method if only a single provider has been specified.

        Args:
            pages (Sequence[int]): A sequence of page numbers to iteratively request from the API Provider.
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

        workers = max_workers if max_workers is not None else min(8, len(provider_groups))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [
                executor.submit(list, self._process_provider_group(provider_search_coordinators, pages, **kwargs))
                for provider_search_coordinators in provider_groups.values()
            ]

            for future in concurrent.futures.as_completed(futures):
                yield from future.result()

    def _process_provider_group(
        self, provider_coordinators: dict[str, SearchCoordinator], pages: Sequence[int], **kwargs
    ) -> Generator[SearchResult, None, None]:
        """
        Helper method used to process all queries and pages for a single provider under a common thread.
        This method is especially useful during multithreading given that API Providers often have hard limuts on the
        total number of requests that can be sent within a provider-specific interval.

        Args:
            provider_coordinators (dict[str, SearchCoordinator]):
                A dictionary of all coordinators corresponding to a single provider.
            pages (Sequence[int]): A sequence of page numbers to iteratively request from the API Provider.
            pages (Sequence[int]): A list, set, or other common sequence of integer page numbers corresponding to
                                   records/articles to iteratively request from the API Provider.
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

        # will be used to flag non-retriable error codes from the provider for early stopping across queries if needed
        last_response: Optional[APIResponse] = None
        for search_coordinator in provider_coordinators.values():
            provider_name = ProviderConfig._normalize_name(search_coordinator.api.provider_name)

            if (
                isinstance(last_response, ErrorResponse)
                and last_response.response is not None
                and not search_coordinator.retry_handler.should_retry(last_response.response)
            ):
                # breaks if a non-retriable status code is encountered.
                logger.warning(
                    f"Encountered a non-retriable response during retrieval: {last_response}. "
                    f"Halting retrieval for provider, {provider_name}"
                )
                break

            # iterate over the current coordinator given its session, query, and settings
            for page in search_coordinator.iter_pages(pages, **kwargs):
                if isinstance(page, SearchResult):
                    last_response = page.response_result
                yield page

    def current_providers(self) -> set[str]:
        """Extracts a set of names corresponding to the each API provider assigned to the MultiSearchCoordinator"""
        return {ProviderConfig._normalize_name(coordinator.api.provider_name) for coordinator in self.data.values()}

    def group_by_provider(self) -> dict[str, dict[str, SearchCoordinator]]:
        """
        Groups all coordinators by provider name to facilitate retrieval with normalized components where needed.
        Especially helpful in the latter retrieval of articles when using multithreading by provider (as opposed to by
        page) to account for strict rate limits. All coordinated searches corresponding to a provider would appear
        under a nested dictionary to facilitate orchestration on the same thread with the same rate limiter.

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
        """
        Helper method that retrieves the threaded rate_limiter for the coordinator's provider and normalizes
        the rate limiter used for searches.
        """
        provider_name = ProviderConfig._normalize_name(search_coordinator.api.provider_name)

        # ensure that the same rate limiter is used with threading if needed to ensure rate limiting across providers
        # if the provider doesn't already exist, initialize the provider rate limiter in the registry
        threaded_rate_limiter = threaded_rate_limiter_registry.setdefault(
            provider_name, ThreadedRateLimiter(self.DEFAULT_THREADED_REQUEST_DELAY)
        )

        if threaded_rate_limiter:
            search_coordinator.api = SearchAPI.update(search_coordinator.api, rate_limiter=threaded_rate_limiter)
        return search_coordinator

    @classmethod
    def _create_key(cls, search_coordinator: SearchCoordinator):
        """
        Create a hashed key from a coordinator using the provider name, query,
        and structure of the SearchCoordinator
        """
        hash_value = hash(repr(search_coordinator))
        provider_name = ProviderConfig._normalize_name(search_coordinator.api.provider_name)
        query = str(search_coordinator.api.query)
        key = f"{provider_name}_{query}:{hash_value}"
        return key

    def __repr__(self) -> str:
        """Helper method for generating a string representation of the current list of coordinators"""
        class_name = self.__class__.__name__
        attributes = {key: coordinator.summary() for key, coordinator in self.data.items()}
        return generate_repr_from_string(class_name, attributes)


if __name__ == "__main__":
    """
    Testing and debugging the functionality of the multisearch_coordinator: Determine first whether rate limiters
    were normalized as intended (Yes), and whether a single generator could be produced successfully (yes).
    The SearchResultList consumes the generator directly although iteration for each result may be more preferable
    in case of run-time errors.
    """
    from scholar_flux.api import MultiSearchCoordinator, SearchCoordinator
    from scholar_flux.api.models import SearchResultList, SearchResult, APIResponse
    from scholar_flux.data_storage import DataCacheManager
    from scholar_flux.utils import FileUtils

    multisearch_coordinator = MultiSearchCoordinator()

    coordinators: list[SearchCoordinator] = [
        SearchCoordinator(
            query=query,
            user="sammie h",
            provider_name=provider,
            cache_requests=True,
            mailto="your_email@email_provider.com",  # email will only register for crossref
            cache_manager=DataCacheManager.with_storage("redis"),
        )
        for query in [
            "depth psychology",
            "occupational psychology",
        ]  # ['AI ML', 'data engineering innovation', 'distributed databases']
        for provider in ["plos", "springernature", "core"]
    ]

    multisearch_coordinator.add_coordinators(coordinators)

    # all coordinators should be added at this point
    assert len(multisearch_coordinator) == len(coordinators)
    print(repr(multisearch_coordinator))

    grouped_provider_dict = multisearch_coordinator.group_by_provider()

    # test to ensure all providers use one rate limiter each
    for provider in grouped_provider_dict:
        rate_limiters = [
            coordinator.api._rate_limiter  # type: ignore
            for current_provider_group, provider_coordinators in grouped_provider_dict.items()
            for coordinator in provider_coordinators.values()
            if current_provider_group == provider
        ]
        assert len(set(map(id, rate_limiters))) == 1

    # ensures there are 3 distinct rate limiters (by provider)
    all_rate_limiters = [
        coordinator.api._rate_limiter  # type: ignore
        for current_provider_group, provider_coordinators in grouped_provider_dict.items()
        for coordinator in provider_coordinators.values()
    ]
    assert len(set(map(id, all_rate_limiters))) == len(multisearch_coordinator.current_providers())

    # caches on the second run with requests-cache on the backend
    page_search_generator = multisearch_coordinator.iter_pages(pages=range(1, 3), iterate_by_group=True)
    search_results = SearchResultList()
    for page in page_search_generator:
        search_results.append(page)
    assert len(search_results) >= 3  # at the very least, assuming worst case an error stops processing
    results_dict = search_results.filter().join()

    # list of dictionaries
    assert isinstance(results_dict, list) and all(isinstance(result, dict) for result in results_dict)

    # saving for later browsing
    FileUtils.save_as(results_dict, "~/Downloads/ai-data-engineering-search-9-25-2025")
