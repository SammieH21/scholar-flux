from scholar_flux.api import SearchCoordinator, SearchAPI, SearchAPIConfig, APIParameterConfig
from scholar_flux.data import RecursiveDataProcessor
from scholar_flux.api.models import ProcessedResponse
from scholar_flux.data_storage import DataCacheManager
from contextlib import contextmanager
from requests import Response
from pydantic import SecretStr
from requests_mock import Mocker
from typing import Literal, Callable
import pytest


@pytest.fixture
def search_api() -> SearchAPI:
    """Basic SearchAPI for testing response retrieval and caching. By default, request cache is turned off by default
    but can be turned on during the creation of the SearchCoordinator.

    Returns:
        SearchAPI: A search API configured for response testing and retrieval.
    """
    # basic setup
    search_api_config = SearchAPIConfig(
        records_per_page=3,
        request_delay=0.01,
        base_url="https://test_url.com/search",
        api_key=SecretStr("this-is-a-test-key"),
        api_specific_parameters=dict(mailto=SecretStr("this.is.a@testemail.com")),
    )
    search_api = SearchAPI.from_settings(
        config=search_api_config,
        parameter_config=APIParameterConfig.from_defaults("crossref"),
        query="Computationally Aided Analysis",
    )
    return search_api


@pytest.fixture()
def initialize_mocker(search_api: SearchAPI, academic_json_response: Response) -> Callable:
    """Helper function for quickly initializing a mock URL for testing and verifying cache settings.

    Returns:
        A callable to be used as a context for retrieving mock API responses

    It can be used as follows:
        >>> with initialize_mocker() as _:
        >>>     response = search_api.search(page = 1)
        >>> assert isinstance(response, Response)
    """

    @contextmanager
    def with_mocker():
        """Nested function for creating a reusable mocker without redefining each individual URL across tests."""
        parameters = search_api.build_parameters(page=1)
        prepared_request = search_api.prepare_request(parameters=parameters)
        with Mocker() as m:
            m.get(
                prepared_request.url,
                status_code=academic_json_response.status_code,
                json=academic_json_response.json(),
                headers={"Content-Type": "application/json"},
            )
            yield m
        return False

    return with_mocker


def create_search_coordinator(
    search_api: SearchAPI,
    cache_backend: Literal["redis", "null", "inmemory", "sql", "redis"],
    cache_requests: bool = False,
    **cache_kwargs,
) -> SearchCoordinator:
    """Helper method for creating a new search coordinator for response cache testing. Takes a cache backend and creates
    the required backend based on the keyword arguments applied.

    Args:
        search_api (SearchAPI): A SearchAPI instance that the SearchCoordinator will use for response retrieval
        cache_backend (Literal): The backend to use for caching the processing of responses
        cache_requests (bool): Indicates whether request caching will be performed during response retrieval
        **cache_kwargs: A list of key-value pairs to use when creating the response processing cache storage

    Returns:
        SearchCoordinator: A new SearchCoordinator that will retrieve, process, and cache processed responses depending
                           on the selected options used during instantiation.
    """

    # uses the DataCacheManager to directly setup caching with additional default arguments
    storage_cache = DataCacheManager.with_storage(cache_backend, **cache_kwargs)

    # sets up a new SearchCoordinator that uses the API and a response coordinator to retrieve and process responses
    search_coordinator = SearchCoordinator(
        search_api, cache_manager=storage_cache, cache_requests=cache_requests, processor=RecursiveDataProcessor()
    )

    return search_coordinator


@pytest.mark.parametrize(
    ["cache_backend", "cache_kwargs", "cache_requests"],
    [
        ("redis", {}, True),
        ("null", {}, True),
        ("inmemory", {}, True),
        ("sql", {"url": "sqlite_db_url"}, True),
        ("redis", {}, False),
        ("null", {}, False),
        ("inmemory", {}, False),
        ("sql", {"url": "sqlite_db_url"}, False),
    ],
)
def test_response_cache(
    initialize_mocker, db_dependency_unavailable, request, search_api, cache_backend, cache_kwargs, cache_requests
):
    """Performs an integration test to verify that the functions of the response cache (as opposed to the request cache)
    correctly retrieves cached data as needed with the appropriate backend.

    `pytest.mark.parametrize` is used to test each backend in sequence.
    """
    # Skip if required dependency is missing
    if db_dependency_unavailable(cache_backend):
        pytest.skip(f"{cache_backend} not available")

    cache_kwargs = {k: request.getfixturevalue(v) for k, v in cache_kwargs.items()}
    search_coordinator = create_search_coordinator(
        search_api, cache_backend, cache_requests=cache_requests, **cache_kwargs
    )

    # ensures that any cached requests and responses are deleted beforehand
    search_coordinator._delete_cached_request(page=1)
    search_coordinator._delete_cached_response(page=1)

    # Mocks a new response that is associated with the current URL:
    with initialize_mocker() as _:

        cache_key = search_coordinator._create_cache_key(page=1)

        # at this point, there should not be a response cached under the current cache key
        assert not search_coordinator.response_coordinator.cache_manager.verify_cache(cache_key)

        # retrieves an uncached response
        processed_response = search_coordinator.search(page=1)

        # verifies whether the response has been retrieved as intended
        assert isinstance(processed_response, ProcessedResponse) and isinstance(processed_response.response, Response)

        # either the response processing is now cached or we were using a null storage which doesn't cache
        assert search_coordinator.responses.cache.verify_cache(cache_key) ^ search_coordinator.responses.cache.isnull()

        # should retrieve from requests cache when cache_requests is True
        processed_cached_response = search_coordinator.search(page=1)
        assert isinstance(processed_cached_response, ProcessedResponse)
        cached_response = processed_cached_response.response

        # indicates whether the current response is cached when cached is enabled, and fresh when cache is disabled
        assert getattr(cached_response, "from_cache", False) is cache_requests

        # ensure that processing isn't saved with the null storage
        if cache_backend == "null":
            assert not search_coordinator.response_coordinator.cache_manager.verify_cache(cache_key)
            retrieved_cache = search_coordinator.response_coordinator.cache_manager.retrieve(cache_key)
            assert retrieved_cache == {} and retrieved_cache != search_coordinator.search_data(page=1)
        else:
            # ensure that the retrieval of cached and uncached processed responses returns the same result
            assert search_coordinator.response_coordinator.cache_manager.verify_cache(cache_key)
            retrieved_cache = search_coordinator.response_coordinator.cache_manager.retrieve(cache_key)
            retrieved_data = search_coordinator.search_data(page=1, from_process_cache=False)
            assert retrieved_cache is not None and retrieved_cache["processed_records"] == retrieved_data
            search_coordinator._delete_cached_response(page=1)
