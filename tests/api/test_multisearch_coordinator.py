from contextlib import contextmanager
from scholar_flux.api import SearchAPI, SearchCoordinator, APIParameterMap, MultiSearchCoordinator
from scholar_flux.exceptions import InvalidCoordinatorParameterException
from scholar_flux.utils import parse_iso_timestamp
from scholar_flux.api.models import SearchResultList, ProcessedResponse, ErrorResponse, PageListInput
from unittest.mock import patch
from warnings import warn
from typing import Any
from pathlib import Path
import requests_mock
import pytest
from time import time
from datetime import datetime
import re
from time import sleep


@pytest.fixture
def parameter_map():
    """Holds the default configuration used to simulate the requirements of an API"""
    parameter_map = APIParameterMap(query="q", start="page", auto_calculate_page=False, records_per_page="pagesize")
    return parameter_map


@pytest.fixture
def paginated_records_directory() -> Path:
    """
    Location holding multiple AI-generated mock json examples simulated and modeled after the default response structure
    of the PLOS API.
    """
    return Path(__file__).parent.parent / "mocks" / "mocked_paginated_records"


@pytest.fixture
def mock_json_provider_page_dict(paginated_records_directory):
    """
    Dictionary where each value holds a list of paths corresponding to a page number from each
    mock-generated API provider.
    """
    mock_json_providers = ("api-one", "api-two", "api-three")
    return {
        mock_json_provider: [path for path in paginated_records_directory.iterdir() if mock_json_provider in str(path)]
        for mock_json_provider in mock_json_providers
    }


@pytest.fixture
def pause_rate_limiting():
    """
    Fixture for briefly turning off the default rate limit for unknown providers:
    Used to temporarily pauses rate limiting for individual tests when included as a fixture dependency
    """
    default_rate_limit = MultiSearchCoordinator.DEFAULT_THREADED_REQUEST_DELAY
    MultiSearchCoordinator.DEFAULT_THREADED_REQUEST_DELAY = 0
    yield
    MultiSearchCoordinator.DEFAULT_THREADED_REQUEST_DELAY = default_rate_limit


def get_path_components(json_page_path: Path, url_prefix="") -> dict[str, Any]:
    """
    Helper function for quickly generating a dictionary where each element corresponds to some
    aspect of the provider including the page number, URL, and corresponding content from the provider.
    """

    page_match = re.match(r".*api.*page-(\d+)\.json", json_page_path.name)

    if not page_match:
        raise ValueError(f"Expected a page number match from the JSON path, {json_page_path}")

    page_number = int(page_match.group(1))

    base_url_match = re.match(r".*?(api-[a-z]+)-.*?.json", str(json_page_path.name))

    if not base_url_match:
        raise ValueError(f"Expected a base-url match from the JSON path, {json_page_path}")
    base_name = base_url_match.group(1)

    example_url = f"https://example.{url_prefix}{base_name}.com"

    content = json_page_path.open().read().encode("utf-8")

    return {"page": page_number, "provider_name": base_name, "base_url": example_url, "content": content}


def create_coordinators(path_component_dict, query, parameter_config):
    """
    Generates a dictionary of coordinators from the path_component_dict which indicates the page number and provider
    and the APIParameterMap that maps parameters to the parameters expected by the API.
    """
    return {
        path_components["base_url"]: SearchCoordinator(
            SearchAPI(
                query=query,
                base_url=path_components["base_url"],
                provider_name=path_components["provider_name"],
                parameter_config=parameter_config,
                request_delay=0,
                records_per_page=3,
                use_cache=True,
            ),
            request_delay=0,
        )
        for path_components in path_component_dict.values()
    }


@pytest.fixture
def path_component_dict(mock_json_provider_page_dict) -> dict[Path, Any]:
    """
    Uses the `get_path_components` function to generate a dictionary of parameters corresponding to each individual
    mock API provider and the path to where each mocked response JSON file for each page can be found.
    """
    component_dict = {
        path: get_path_components(path) for path_group in mock_json_provider_page_dict.values() for path in path_group
    }
    return component_dict


@pytest.fixture
def path_component_dict_rate(mock_json_provider_page_dict) -> dict[Path, Any]:
    """Generates a similar dictionary as the path_component_dict with the only modifications being the
    `base_url` and `provider_name`. The url is prefixed with `rate-` so that `https://example-api-one.com` becomes
    `https://example-rate-api-one.com`.

    This dictionary fixture is used to help simulate retrieval from multiple providers simultaneously.
    """
    component_dict = {
        path: get_path_components(path, url_prefix="rate-")
        for path_group in mock_json_provider_page_dict.values()
        for path in path_group
    }
    return component_dict


@pytest.fixture
def coordinator_dict(path_component_dict, parameter_map) -> dict[str, SearchCoordinator]:
    """Generates a coordinator dictionary using the `create_coordinators` helper function from a path_component_dict"""
    return create_coordinators(path_component_dict, query="quantum-computing", parameter_config=parameter_map)


@pytest.fixture
def coordinator_dict_rate(path_component_dict_rate, parameter_map) -> dict[str, SearchCoordinator]:
    """
    Similarly generates a coordinator dictionary using the `create_coordinators` helper function for the
    URLs prefixed with `rate-`.
    """
    return create_coordinators(path_component_dict_rate, query="quantum-computing", parameter_config=parameter_map)


@pytest.fixture
def coordinator_dict_new_query(path_component_dict, parameter_map) -> dict[str, SearchCoordinator]:
    """
    Creates new coordinators that retrieve data from the API with the query, `new-query`. Used
    to simulate pulling from the same provider with a different query, while require the same rate limit
    to be triggered as used with the initial `quantum-computing` query
    """
    return create_coordinators(path_component_dict, query="new-query", parameter_config=parameter_map)


@pytest.fixture
def coordinator_dict_rate_new_query(path_component_dict_rate, parameter_map) -> dict[str, SearchCoordinator]:
    """
    Creates new coordinators that retrieve data from the API with the query, `new-query` from the URLs
    prefixed with `rate-`. Simulate pulling from a different provider with a different query,
    while require a different rate limiter given that the provider differs from the initial `coordinator_dict`
    """

    return create_coordinators(path_component_dict_rate, query="new-query", parameter_config=parameter_map)


def patch_provider_url(
    coordinator_dict: dict[str, "SearchCoordinator"],
    base_url: str,
    page_number: int,
    content: bytes,
    mocker: requests_mock.Mocker,
) -> None:
    """Helper function for patching coordinators to ensure that only mocked results are retrieved"""

    if coordinator := coordinator_dict.get(base_url):
        parameters = coordinator.api.build_parameters(page=page_number)
        prepared_page = coordinator.api.prepare_request(parameters=parameters)

        assert prepared_page.url and f"&page={page_number}" in str(prepared_page.url)

        mocker.get(
            prepared_page.url,
            content=content,
            headers={"Content-Type": "application/json; charset=UTF-8"},
            status_code=200,
        )
    else:
        warn(f"Couldn't find a coordinator with the URL, {base_url} in the dictionary of coordinators")


@pytest.fixture
def initialize_mocker(
    coordinator_dict,
    coordinator_dict_new_query,
    coordinator_dict_rate,
    coordinator_dict_rate_new_query,
    path_component_dict,
    path_component_dict_rate,
):
    """
    Helper function for quickly initializing each url to return simulated data for testing the MultiCoordinator.

    This function uses a context manager to set up mocking for each of the following sites.

        1) `https://example.api-one.com`
        2) `https://example.api-two.com`
        3) `https://example.api-three.com`
        4) `https://example.rate-api-one.com`
        5) `https://example.rate-api-two.com`
        6) `https://example.rate-api-three.com`

    The `patch_provider_url` helper function is used to patch requests sent by each coordinator within a dictionary of
    coordinators. This helper function uses requests_mock to simulate responses to requests for validation of the
    functionality of the MultiSearchCoordinator.

    It can be used as follows:
        >>> with initialize_mocker() as _:
        >>>     response = coordinator_dict['https://example.api-one.com'].search(page = 1)
        >>> assert isinstance(response, ProcessedResponse) # indicates successful retrieval and processing
    """

    @contextmanager
    def with_mocker():
        """Nested function for creating a reusable mocker without redefining each individual URL across tests"""
        all_path_component_dicts = list(path_component_dict.values()) + list(path_component_dict_rate.values())

        all_coordinator_dicts = (
            coordinator_dict | coordinator_dict_rate,
            coordinator_dict_new_query | coordinator_dict_rate_new_query,
        )

        with requests_mock.Mocker(real_http=False) as m:
            for component_dict in all_path_component_dicts:

                for current_coordinator_dict in all_coordinator_dicts:
                    patch_provider_url(
                        coordinator_dict=current_coordinator_dict,
                        base_url=component_dict["base_url"],
                        page_number=component_dict["page"],
                        content=component_dict["content"],
                        mocker=m,
                    )
            yield m

        return False

    return with_mocker


def test_mocked_initialization(coordinator_dict, path_component_dict, initialize_mocker):
    """
    Helper function for first determining whether the context manager `initialize_mocker`
    is working as intended. Loops through each coordinator to determine whether the coordinators
    return the expected result.
    """
    with initialize_mocker() as _:
        for component_dict in path_component_dict.values():

            base_url = component_dict["base_url"]
            page_number = component_dict["page"]
            coordinator = coordinator_dict[base_url]

            parameters = coordinator.api.build_parameters(page=page_number)
            prepared_page = coordinator.api.prepare_request(parameters=parameters)

            assert f"&page={page_number}" in str(prepared_page.url)
            response = coordinator.search(page=page_number)
            assert isinstance(response, ProcessedResponse)


def test_multisearch_initialization(coordinator_dict, pause_rate_limiting):
    """
    Test whether a multisearch_coordinator is created as intended and that individual components can be
    added independent on the method used to populate the MultiSearchCoordinator object.

    Also tests whether the addition of non-coordinators will fail as expected when added.
    """
    multisearch_coordinator_one = MultiSearchCoordinator()
    multisearch_coordinator_one.add_coordinators(list(coordinator_dict.values()))
    multisearch_coordinator_two = MultiSearchCoordinator()

    for provider_name, coordinator in multisearch_coordinator_one.items():
        multisearch_coordinator_two[provider_name] = coordinator

    noncoordinator = "not a coordinator"
    with pytest.raises(InvalidCoordinatorParameterException) as excinfo:
        multisearch_coordinator_two["a provider"] = noncoordinator  # type: ignore
    assert f"Expected a SearchCoordinator, received type {type(noncoordinator)}" in str(excinfo.value)

    assert len(multisearch_coordinator_one) == len(coordinator_dict) > 0
    assert multisearch_coordinator_one == multisearch_coordinator_two

    multisearch_coordinator_two.clear()
    for coordinator in multisearch_coordinator_one.values():
        multisearch_coordinator_two.add_coordinators(coordinator)  # type: ignore

    noncoordinator = "not a coordinator"
    with pytest.raises(InvalidCoordinatorParameterException) as excinfo:
        multisearch_coordinator_two.add_coordinators(noncoordinator)  # type: ignore
    assert f"Expected a sequence or iterable of search_coordinators, received type {type(noncoordinator)}" in str(
        excinfo.value
    )

    assert multisearch_coordinator_one == multisearch_coordinator_two


def test_page_iteration(coordinator_dict, initialize_mocker, path_component_dict, pause_rate_limiting):
    """
    Tests whether iter_pages returns a generator that iteratively returns each page for as long
    as there is a page with data to return. Each page should only be requested and processed upon
    retrieving the next page via an iterator such as a `for loop`, the `next` function, a list, or a `while loop`
    """
    multisearch_coordinator = MultiSearchCoordinator()
    multisearch_coordinator.add_coordinators(coordinator_dict.values())
    max_pages = max(component_dict["page"] for component_dict in path_component_dict.values())
    total_pages = len(path_component_dict.keys())
    page_range = range(1, max_pages + 1)

    with initialize_mocker() as _:
        result_list = SearchResultList()
        iter_pages = multisearch_coordinator.iter_pages(pages=page_range)
        for page in iter_pages:
            result_list.append(page)

        assert isinstance(result_list, SearchResultList) and len(result_list) == total_pages
        # assert len(result_list.filter()) == total_pages

        result_list_two = SearchResultList()
        iter_pages = multisearch_coordinator.iter_pages(pages=page_range, iterate_by_group=True)

        # first method of adding successfully retrieved and processed pages to a SearchResultList
        for page in iter_pages:
            result_list_two.append(page)

        assert len(result_list) == len(result_list_two) == total_pages
        assert sorted(result_list_two.join(), key=lambda x: str(x)) == sorted(result_list.join(), key=lambda x: str(x))

        # initial_api_responses = [other.response_result for other in result_list]

        iter_pages = multisearch_coordinator.iter_pages_threaded(pages=page_range)
        result_list_three = SearchResultList(iter_pages)  # a list should successfully consume the generator.

        assert isinstance(result_list_three, SearchResultList) and len(result_list_three) == total_pages

        # as all elements should be successful, the size should be equal before and after filtering
        assert len(result_list) == len(result_list_three) == total_pages
        assert len(result_list.filter()) == len(result_list_three.filter()) == total_pages
        assert sorted(result_list_two.join(), key=lambda x: str(x)) == sorted(
            result_list_three.join(), key=lambda x: str(x)
        )

        # cached responses should be equally found across all tables
        assert len(result_list_two) == len(result_list_three) and all(
            result in result_list_three for result in result_list_two
        )


def test_page_search(coordinator_dict, initialize_mocker, pause_rate_limiting):
    """
    Uses the MultiSearchCoordinator to retrieve the first page across all coordinators by query and URL.
    Both `search` and `search_pages` should return the same result when requesting a single page
    """
    multisearch_coordinator = MultiSearchCoordinator()
    multisearch_coordinator.add_coordinators(coordinator_dict.values())

    with initialize_mocker() as _:
        # should have the same number of coordinators as results, no providers repeated with differing queries
        uncached_result_list = multisearch_coordinator.search(page=1, from_request_cache=False)

        # the rest are cached, both should be equal although requests mock doesn't consider byte addresses equal:
        result_list_one = multisearch_coordinator.search(page=1)
        result_list_two = multisearch_coordinator.search_pages(pages=[1])
        assert (
            len(uncached_result_list)
            == len(result_list_two)
            == len(result_list_two)
            == len(multisearch_coordinator.coordinators)
        )

        # the search result lists should also be the same length after filtering ErrorResponses and non-responses
        assert (
            len(uncached_result_list.filter())
            == len(result_list_one.filter())
            == len(result_list_two.filter())
            == len(multisearch_coordinator.coordinators)
        )

        # the bytes themselves aren't equal but the response content should be:
        assert all(
            search_result.response_result.content  # type: ignore
            in (cached_result.response_result.response.content for cached_result in result_list_one)  # type: ignore
            for search_result in uncached_result_list
        )

        # the cached responses should always be equal
        assert (
            all(
                response_one.response_result == response_two
                for (response_one, response_two) in zip(result_list_one, result_list_two)
            )
            or result_list_one.filter().join() == result_list_two.filter().join() == result_list_two.filter().join()
        )


def test_page_range_search(coordinator_dict, initialize_mocker, path_component_dict, pause_rate_limiting):
    """
    Attempts to retrieve the full length of pages available from each mock provider. The actual page
    count retrieved will depend on the number of successful results available and whether any unsuccessful
    status codes are returned. In the latter scenario, the method should stop early.
    """
    multisearch_coordinator = MultiSearchCoordinator()
    multisearch_coordinator.add_coordinators(coordinator_dict.values())
    max_pages = max(component_dict["page"] for component_dict in path_component_dict.values())
    total_pages = len(path_component_dict.keys())
    page_range = range(1, max_pages + 1)

    with initialize_mocker() as _:
        result_list = multisearch_coordinator.search_pages(
            pages=page_range, iterate_by_group=True, multithreading=False
        )

        assert isinstance(result_list, SearchResultList) and len(result_list) == total_pages

        result_list_two = SearchResultList()
        result_list_two = multisearch_coordinator.search_pages(
            pages=page_range, iterate_by_group=True, multithreading=False
        )

        assert len(result_list) == len(result_list_two) == total_pages
        assert sorted(result_list_two.join(), key=lambda x: str(x)) == sorted(result_list.join(), key=lambda x: str(x))

        # iterate_by_group irrelevant when using multithreading
        result_list_three = multisearch_coordinator.search_pages(pages=page_range, multithreading=True)
        assert isinstance(result_list_three, SearchResultList) and len(result_list_three) == total_pages

        # should give the same results as iter pages, just performed automatically instead of requiring manual iteration
        assert len(result_list) == len(result_list_three) == total_pages
        assert len(result_list.filter()) == len(result_list_three.filter()) == total_pages
        assert sorted(result_list_two.join(), key=lambda x: str(x)) == sorted(
            result_list_three.join(), key=lambda x: str(x)
        )


def test_rate_limiter_normalization(
    coordinator_dict_rate,
    coordinator_dict_rate_new_query,
    initialize_mocker,
    path_component_dict,
    pause_rate_limiting,  # added to restore the default afterward
):
    """
    Test whether each rate limiter for each individual provider will trigger universally for each individual provider
    independent of coordinator configuration used to request the next page.

    The MultiSearchCoordinator uses the `coordinator.api.provider_name` attribute to assign the same rate limiter
    across each coordinator querying from the same provider
    """
    MIN_REQUEST_DELAY_INTERVAL = 0.200
    TOLERANCE = 0.7
    MultiSearchCoordinator.DEFAULT_THREADED_REQUEST_DELAY = MIN_REQUEST_DELAY_INTERVAL
    multisearch_coordinator = MultiSearchCoordinator()

    coordinators = list(coordinator_dict_rate_new_query.values()) + list(coordinator_dict_rate.values())

    multisearch_coordinator.add_coordinators(coordinators)
    total_coordinators = len(coordinators)
    unique_providers = multisearch_coordinator.current_providers()

    # all coordinators should be added at this point
    assert len(multisearch_coordinator) == total_coordinators
    print(repr(multisearch_coordinator))

    assert unique_providers == {"api-one", "api-two", "api-three"}

    grouped_provider_dict = multisearch_coordinator.group_by_provider()

    for coordinator in multisearch_coordinator.values():
        coordinator.api.config.request_delay = MIN_REQUEST_DELAY_INTERVAL

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
        for provider_coordinators in grouped_provider_dict.values()
        for coordinator in provider_coordinators.values()
    ]
    assert len(set(map(id, all_rate_limiters))) == len(multisearch_coordinator.current_providers())

    original_sleep_fn = sleep
    sleep_args = []

    def sleep_and_record(arg):
        """Helper class used to both sleep and verify the arguments passed to sleep during request rate limiting"""
        sleep_args.append(arg)
        original_sleep_fn(arg)

    # patch the endpoints to use requests_mock instead of actually sending requests, and patch with `sleep_and_record`
    with initialize_mocker() as _, patch("time.sleep", side_effect=sleep_and_record):
        max_pages = max(component_dict["page"] for component_dict in path_component_dict.values())
        page_range = range(1, max_pages + 1)
        start = time()

        # although not encouraged, search can be used with page-ranges
        all_searches = multisearch_coordinator.search(
            page=page_range, from_request_cache=False, iterate_by_group=False, multithreading=True  # type: ignore
        )
        end = time()
        time_elapsed = end - start

        # the time waited should be from sleeping, yet be threaded to allow for multiple searches at the same time
        max_single_provider_requests = max(
            len([coordinator for coordinator in coordinators if provider_name == coordinator.api.provider_name])
            for provider_name in unique_providers
        )

        total_request_delays = max_single_provider_requests * max_pages - 1
        min_wait_time = total_request_delays * MIN_REQUEST_DELAY_INTERVAL
        assert min_wait_time * 1.2 > time_elapsed > min_wait_time

        intervals = {
            provider_name: sorted(
                parse_iso_timestamp(search.created_at)  # type: ignore
                for search in all_searches
                if search.response_result and search.created_at and search.provider_name == provider_name
            )
            for provider_name in unique_providers
        }

        time_betweeen_requests = []
        for provider_name in unique_providers:
            prev_timestamp = None
            for timestamp in intervals[provider_name]:
                assert timestamp is not None and (isinstance(prev_timestamp, datetime) or prev_timestamp is None)
                # ignore first requests that aren't rate limited
                if prev_timestamp is not None:
                    time_elapsed = abs(timestamp - prev_timestamp).total_seconds()
                    time_betweeen_requests.append(time_elapsed)

                # record the current as the previous for the next addition
                prev_timestamp = timestamp

        assert time_betweeen_requests

        # sometimes sleep is flaky and sleeps for too little time due to machine-related precision randomness
        # The second condition verifies the time.sleep arguments in case the first step fails due to this.
        assert all(
            time_elapsed >= MIN_REQUEST_DELAY_INTERVAL * TOLERANCE for time_elapsed in time_betweeen_requests
        ) or min(arg for arg in sleep_args) <= min(
            coordinator.api.request_delay for coordinator in multisearch_coordinator.coordinators
        )


def test_failed_response(coordinator_dict, monkeypatch, initialize_mocker, caplog):
    """
    Test whether retrieving a single failed result will halt retrieval from a single coordinator.
    This method should only stop the process of retrieving a response from the first provider while other
    response should be retrieved successfully.
    """
    multisearch_coordinator = MultiSearchCoordinator()
    multisearch_coordinator.add_coordinators(coordinator_dict.values())
    provider_name = "api-one"

    coordinator = next((coordinator for url, coordinator in coordinator_dict.items() if provider_name in url))
    key = multisearch_coordinator._create_key(coordinator)
    monkeypatch.setattr(
        multisearch_coordinator[key],
        "search",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("Directly raised exception")),
    )

    msg = "Encountered an unexpected error during iteration for provider, {provider_name}"

    with initialize_mocker() as _:
        search_results_list = multisearch_coordinator.search(page=1, from_request_cache=False, multithreading=False)
        for provider in set(multisearch_coordinator.coordinators):
            error_encountered = provider is provider_name
            assert (msg.format(provider_name=provider) in caplog.text) is error_encountered

        caplog.clear()
        search_results_list_two = multisearch_coordinator.search(
            page=1, from_request_cache=False, iterate_by_group=True, multithreading=False
        )
        for provider in set(multisearch_coordinator.coordinators):
            error_encountered = provider is provider_name
            assert (msg.format(provider_name=provider) in caplog.text) is error_encountered

        caplog.clear()
        search_results_list_three = multisearch_coordinator.search(
            page=1, from_request_cache=False, multithreading=True
        )
        assert f"Encountered an unexpected error during iteration for provider, {provider_name}" in caplog.text

        assert search_results_list.join() == search_results_list_two.join() == search_results_list_three.join()
        assert (
            len(search_results_list.filter()) == len(multisearch_coordinator.coordinators) - 1
        )  # only one key is invalid


def test_invalid_parameters(initialize_mocker, pause_rate_limiting, caplog):
    """
    Ensures that invalid parameters provided for the MultiSearchCoordinator halt processing prior to any
    requests being sent. This includes parameters for the number of workers, non-integer page numbers,
    non-positive page values provided to the API
    """
    multisearch_coordinator = MultiSearchCoordinator()

    with initialize_mocker() as _:
        # simulate an issue such as an unauthorized error occurring at the level of the provider (as opposed to the query or page
        with pytest.raises(InvalidCoordinatorParameterException) as excinfo:
            _ = multisearch_coordinator.search(page={})  # type:ignore
        assert (
            "Expected `pages` to be a list or other sequence of integer pages. Received an error on validation"
            in str(excinfo.value)
        )

        caplog.clear()
        with pytest.raises(InvalidCoordinatorParameterException) as excinfo:
            _ = multisearch_coordinator.search_pages(pages={})  # type:ignore
        assert (
            "Expected `pages` to be a list or other sequence of integer pages. Received an error on validation"
            in str(excinfo.value)
        )

        caplog.clear()
        invalid_workers = "no worker"
        with pytest.raises(InvalidCoordinatorParameterException) as excinfo:
            _ = SearchResultList(multisearch_coordinator.search_pages(pages=[1, 2], max_workers=invalid_workers))  # type: ignore
        assert (
            f"Expected max_workers to be a positive integer, Received a value of type {type(invalid_workers)}"
            in str(excinfo.value)
        )

        pages = SearchResultList(multisearch_coordinator.iter_pages(pages=PageListInput([1, 2])))
        assert isinstance(pages, SearchResultList) and not pages

        non_positive_workers = -1
        pages = SearchResultList(
            multisearch_coordinator.iter_pages_threaded(pages=PageListInput([1, 2]), max_workers=non_positive_workers)
        )
        assert isinstance(pages, SearchResultList) and not pages
        assert f"The value for workers ({non_positive_workers}) is non-positive: defaulting to 1 worker"


def test_empty_search(pause_rate_limiting, caplog):
    """
    Ensure that an empty search triggers a log message indicating that no coordinators have been registered.
    The SearchResultList should then be returned but completely empty as a result.
    """
    multisearch_coordinator = MultiSearchCoordinator()
    search_result_list = multisearch_coordinator.search(page=1)
    assert not search_result_list and isinstance(search_result_list, SearchResultList)
    assert (
        "A coordinator has not yet been registered with the MultiSearchCoordinator: returning an empty list..."
    ) in caplog.text


def test_error_response(
    coordinator_dict, coordinator_dict_new_query, monkeypatch, initialize_mocker, pause_rate_limiting, caplog
):
    """
    Ensure that the MultiSearchCoordinator returns an error response as expected upon encountering invalid
    responses or processing errors.

    Mocks the `search` method to return an error to verify that the result contains a SearchResultList that
    in turn contains each SearchResult indicating the page number, provider, and ErrorResponse for all pages
    """
    multisearch_coordinator = MultiSearchCoordinator()
    multisearch_coordinator.add_coordinators(
        list(coordinator_dict.values()) + list(coordinator_dict_new_query.values())
    )

    with initialize_mocker() as _:
        # simulate an issue such as an unauthorized error occurring at the level of the provider (as opposed to the query or page
        for key in multisearch_coordinator:
            monkeypatch.setattr(
                multisearch_coordinator[key],
                "search",
                lambda *args, **kwargs: ErrorResponse.from_response(
                    status_code=401, url="https://test_url", content=b""
                ),
            )
        search_results_list = multisearch_coordinator.search_pages(
            pages=(1, 2), from_request_cache=False, iterate_by_group=True, multithreading=False
        )
        assert "Encountered a non-retryable response during retrieval:" in caplog.text
        assert "Halting retrieval for provider" in caplog.text

        # breaks if a non-retryable status code is encountered.
        assert len(search_results_list) == 3
        assert not search_results_list.filter()
