from contextlib import contextmanager
from scholar_flux.api import SearchAPI, SearchCoordinator, APIParameterMap, MultiSearchCoordinator
from scholar_flux.utils import parse_iso_timestamp
from scholar_flux.api.models import SearchResultList,  ErrorResponse
from typing import Any
from pathlib import Path
import requests_mock
import pytest
from time import time
from datetime import datetime
import re

@pytest.fixture
def parameter_map():
    parameter_map = APIParameterMap(query="q", start="page", auto_calculate_page=False, records_per_page="pagesize")
    return parameter_map


@pytest.fixture
def paginated_records_directory() -> Path:
    return Path(__file__).parent.parent / "mocks" / "mocked_paginated_records"


@pytest.fixture
def pages_one(paginated_records_directory):
    return [path for path in paginated_records_directory.iterdir() if "api-one" in str(path)]


@pytest.fixture
def pages_two(paginated_records_directory):
    return [path for path in paginated_records_directory.iterdir() if "api-two" in str(path)]


@pytest.fixture
def pages_three(paginated_records_directory):
    return [path for path in paginated_records_directory.iterdir() if "api-three" in str(path)]


@pytest.fixture
def coordinator_one(parameter_map):
    api = SearchAPI(
        query="quantum-computing",
        base_url="https://example.api-one.com",
        parameter_config=parameter_map,
        request_delay=0,
        records_per_page=3,
    )
    return SearchCoordinator(api, request_delay=0, cache_requests=True)


@pytest.fixture
def coordinator_two(parameter_map):
    api = SearchAPI(
        query="quantum-computing",
        base_url="https://example.api-two.com",
        parameter_config=parameter_map,
        request_delay=0,
        records_per_page=3,
    )
    return SearchCoordinator(api, request_delay=0, cache_requests=True)


@pytest.fixture
def coordinator_three(parameter_map):
    api = SearchAPI(
        query="quantum-computing",
        base_url="https://example.api-three.com",
        parameter_config=parameter_map,
        request_delay=0,
        records_per_page=3,
    )
    return SearchCoordinator(api, request_delay=0, cache_requests=True)


def get_path_components(json_page_path: Path) -> dict[str, Any]:

    page_match = re.match(r".*api.*page-(\d+)\.json", json_page_path.name)

    if not page_match:
        raise ValueError(f"Expected a page number match from the josn path, {json_page_path}")

    page_number = int(page_match.group(1))

    base_url_match = re.match(r".*?(api-[a-z]+)-.*?.json", str(json_page_path.name))

    if not base_url_match:
        raise ValueError(f"Expected a base-url match from the josn path, {json_page_path}")
    base_name = base_url_match.group(1)

    example_url = f"https://example.{base_name}.com"

    content = json_page_path.open().read().encode("utf-8")

    return {"page": page_number, "provider-name": base_name, "base_url": example_url, "content": content}


@pytest.fixture
def coordinator_dict(coordinator_one, coordinator_two, coordinator_three) -> dict[str, SearchCoordinator]:
    coordinator_dict = {
        coordinator.api.base_url: coordinator for coordinator in (coordinator_one, coordinator_two, coordinator_three)
    }
    return coordinator_dict

@pytest.fixture
def coordinator_dict_two(coordinator_dict) -> dict[str, SearchCoordinator]:
    coordinator_dict_two = {
        url: SearchCoordinator.update(coordinator, search_api = SearchAPI.update(coordinator.api, query = 'new-query'))
        for url, coordinator in coordinator_dict.items()
    }
    return coordinator_dict_two


@pytest.fixture
def path_component_dict(pages_one, pages_two, pages_three) -> dict[Path, Any]:
    component_dict = {
        path: get_path_components(path) for path_group in (pages_one, pages_two, pages_three) for path in path_group
    }

    return component_dict


@pytest.fixture
def initialize_mocker(coordinator_dict, coordinator_dict_two, path_component_dict):

    @contextmanager
    def with_mocker():
        with requests_mock.Mocker() as m:
            for component_dict in path_component_dict.values():

                base_url = component_dict["base_url"]
                page_number = component_dict["page"]
                content = component_dict["content"]

                for current_coordinator_dict in (coordinator_dict, coordinator_dict_two):
                    coordinator = current_coordinator_dict[base_url]
                    parameters = coordinator.api.build_parameters(page=page_number)
                    prepared_page = coordinator.api.prepare_request(parameters=parameters)

                    assert f"&page={page_number}" in str(prepared_page.url)

                    m.get(
                        prepared_page.url,
                        content=content,
                        headers={"Content-Type": "application/json; charset=UTF-8"},
                        status_code=200,
                    )
            yield m


        return False

    return with_mocker


def test_mocked_initialization(coordinator_dict, path_component_dict, initialize_mocker):
    with initialize_mocker() as _:
        for component_dict in path_component_dict.values():

            base_url = component_dict["base_url"]
            page_number = component_dict["page"]
            coordinator = coordinator_dict[base_url]

            parameters = coordinator.api.build_parameters(page=page_number)
            prepared_page = coordinator.api.prepare_request(parameters=parameters)

            assert f"&page={page_number}" in str(prepared_page.url)
            assert coordinator.search(page=page_number)

def test_multi_search_initialization(coordinator_dict):
    MultiSearchCoordinator.DEFAULT_THREADED_REQUEST_DELAY = 0
    multisearch_coordinator_one = MultiSearchCoordinator()
    multisearch_coordinator_one.add_coordinators(list(coordinator_dict.values()))
    multisearch_coordinator_two = MultiSearchCoordinator()

    for provider_name, coordinator in multisearch_coordinator_one.items():
        multisearch_coordinator_two[provider_name] = coordinator

    noncoordinator='not a coordinator'
    with pytest.raises(TypeError) as excinfo:
        multisearch_coordinator_two['a provider'] = noncoordinator # type: ignore
    assert f"Expected a SearchCoordinator, received type {type(noncoordinator)}" in str(excinfo.value)

    assert multisearch_coordinator_one == multisearch_coordinator_two

    multisearch_coordinator_two.clear()
    for coordinator in multisearch_coordinator_one.values():
        multisearch_coordinator_two.add_coordinators(coordinator) # type: ignore

    noncoordinator='not a coordinator'
    with pytest.raises(TypeError) as excinfo:
        multisearch_coordinator_two.add_coordinators(noncoordinator) # type: ignore
    assert f"Expected a sequence or iterable of search_coordinators, received type {type(noncoordinator)}" in str(excinfo.value)

    assert multisearch_coordinator_one == multisearch_coordinator_two



def test_page_iteration(
    coordinator_dict,
    initialize_mocker,
    path_component_dict,
):
    MultiSearchCoordinator.DEFAULT_THREADED_REQUEST_DELAY = 0
    multi_search_coordinator = MultiSearchCoordinator()
    multi_search_coordinator.add_coordinators(coordinator_dict.values())
    max_pages = max(component_dict["page"] for component_dict in path_component_dict.values())
    total_pages = len(path_component_dict.keys())
    page_range = range(1, max_pages + 1)

    with initialize_mocker() as _:
        result_list = SearchResultList()
        iter_pages = multi_search_coordinator.iter_pages(pages=page_range)
        for page in iter_pages:
            result_list.append(page)

        assert isinstance(result_list, SearchResultList) and len(result_list) == total_pages
        # assert len(result_list.filter()) == total_pages

        result_list_two = SearchResultList()
        iter_pages = multi_search_coordinator.iter_pages(pages=page_range, iterate_by_group=True)
        for page in iter_pages:
            result_list_two.append(page)

        assert len(result_list) == len(result_list_two) == total_pages
        assert sorted(result_list_two.join(), key=lambda x: str(x)) == sorted(result_list.join(), key=lambda x: str(x))

        # initial_api_responses = [other.response_result for other in result_list]

        result_list_three = SearchResultList()
        iter_pages = multi_search_coordinator.iter_pages_threaded(pages=page_range)
        for page in iter_pages:
            result_list_three.append(page)

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


def test_page_search(
    coordinator_dict,
    initialize_mocker,
    path_component_dict,
):
    MultiSearchCoordinator.DEFAULT_THREADED_REQUEST_DELAY = 0
    multi_search_coordinator = MultiSearchCoordinator()
    multi_search_coordinator.add_coordinators(coordinator_dict.values())

    with initialize_mocker() as _:
        # should have the same number of coordinators as rseults, no providers repeated with differing queries
        uncached_result_list = multi_search_coordinator.search(page=1, from_request_cache=False)

        # the rest are cached, both should be equal although requests mock doesn't consider byte addresses equal:
        result_list_one = multi_search_coordinator.search(page=1)
        result_list_two = multi_search_coordinator.search_pages(pages=[1])
        assert (
            len(uncached_result_list)
            == len(result_list_two)
            == len(result_list_two)
            == len(multi_search_coordinator.data)
        )

        # the search result lists should also be the same length after filtering ErrorResponses and non-responses
        assert (
            len(uncached_result_list.filter())
            == len(result_list_one.filter())
            == len(result_list_two.filter())
            == len(multi_search_coordinator.data)
        )

        # the bytes themselves aren't equal but the response content should be:
        assert all(
            search_result.response_result.content # type: ignore
            in (cached_result.response_result.response.content for cached_result in result_list_one) # type: ignore
            for search_result in uncached_result_list
        )

        # the cached responses should always be equal
        assert all(
            response_one.response_result == response_two
            for (response_one, response_two) in zip(result_list_one, result_list_two)
        ) or result_list_one.filter().join() == result_list_two.filter().join() == result_list_two.filter().join()


def test_page_range_search(
    coordinator_dict,
    initialize_mocker,
    path_component_dict,
    caplog
):
    MultiSearchCoordinator.DEFAULT_THREADED_REQUEST_DELAY = 0
    multi_search_coordinator = MultiSearchCoordinator()
    multi_search_coordinator.add_coordinators(coordinator_dict.values())
    max_pages = max(component_dict["page"] for component_dict in path_component_dict.values())
    total_pages = len(path_component_dict.keys())
    page_range = range(1, max_pages + 1)

    with initialize_mocker() as _:
        result_list = multi_search_coordinator.search_pages(
            pages=page_range, iterate_by_group=True, multithreading=False
        )

        assert isinstance(result_list, SearchResultList) and len(result_list) == total_pages

        result_list_two = SearchResultList()
        result_list_two = multi_search_coordinator.search_pages(
            pages=page_range, iterate_by_group=True, multithreading=False
        )

        assert len(result_list) == len(result_list_two) == total_pages
        assert sorted(result_list_two.join(), key=lambda x: str(x)) == sorted(result_list.join(), key=lambda x: str(x))

        # iterate_by_group irrelevant when using multithreading
        result_list_three = multi_search_coordinator.search_pages(pages=page_range, multithreading=True)
        assert isinstance(result_list_three, SearchResultList) and len(result_list_three) == total_pages

        # should give the same results as iter pages, just performed automatically instead of requiring manual iteration
        assert len(result_list) == len(result_list_three) == total_pages
        assert len(result_list.filter()) == len(result_list_three.filter()) == total_pages
        assert sorted(result_list_two.join(), key=lambda x: str(x)) == sorted(
            result_list_three.join(), key=lambda x: str(x)
        )



def test_rate_limiter_normalization(
    coordinator_dict,
    coordinator_dict_two,
    initialize_mocker,
    path_component_dict,
):
    multi_search_coordinator = MultiSearchCoordinator()

    coordinators = list(coordinator_dict_two.values()) + list(coordinator_dict.values())

    multi_search_coordinator.add_coordinators(coordinators)
    total_coordinators = len(coordinators)
    unique_providers = multi_search_coordinator.current_providers()


    # all coordinators should be added at this point
    assert len(multi_search_coordinator) == total_coordinators
    print(repr(multi_search_coordinator))

    assert unique_providers == {'api-one', 'api-two', 'api-three'}



    grouped_provider_dict = multi_search_coordinator.group_by_provider()

    MIN_REQUEST_DELAY_INTERVAL = .200
    TOLERANCE = .87

    for coordinator in multi_search_coordinator.values():
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
    assert len(set(map(id, all_rate_limiters))) == len(multi_search_coordinator.current_providers())

    with initialize_mocker() as _:
        max_pages = max(component_dict["page"] for component_dict in path_component_dict.values())
        page_range = range(1, max_pages + 1)
        start = time()

        # although not encouraged, search can be used with page-ranges
        all_searches = multi_search_coordinator.search(page=page_range, # type: ignore
                                                             from_request_cache = False,
                                                             iterate_by_group = False,
                                                             multithreading = True
                                                            )
        end = time()
        time_elapsed = end - start

        # the time waited should be from sleeping, yet be threaded to allow for multiple searches at the same time
        max_single_provider_requests = max(
            len([coordinator for coordinator in coordinators if provider_name == coordinator.api.provider_name])
            for provider_name in unique_providers
        )

        total_request_delays = (max_single_provider_requests * max_pages -1)
        min_wait_time = total_request_delays * MIN_REQUEST_DELAY_INTERVAL
        assert  min_wait_time * 1.2 > time_elapsed > min_wait_time

        intervals = {provider_name: sorted(parse_iso_timestamp(search.response_result.created_at) # type: ignore
                                           for search in all_searches
                                           if search.response_result and \
                                           search.response_result.created_at and \
                                           search.provider_name == provider_name)
                     for provider_name in unique_providers}

        for provider_name in unique_providers:
            prev_timestamp = None
            for timestamp in intervals[provider_name]:
                assert timestamp is not None
                assert (isinstance(prev_timestamp, datetime) and
                        abs(timestamp - prev_timestamp).total_seconds() >= MIN_REQUEST_DELAY_INTERVAL*TOLERANCE ) or \
                        prev_timestamp is None
                prev_timestamp = timestamp

def test_failed_response(coordinator_dict, path_component_dict, monkeypatch, initialize_mocker, caplog):
    multisearch_coordinator = MultiSearchCoordinator()
    multisearch_coordinator.add_coordinators(coordinator_dict.values())
    provider_name = 'api-one'

    coordinator = next((coordinator for url, coordinator in coordinator_dict.items() if provider_name in url))
    key = multisearch_coordinator._create_key(coordinator)
    monkeypatch.setattr(
        multisearch_coordinator[key],
        'search',
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("Directly raised exception")),
    )

    with initialize_mocker() as _:
        search_results_list = multisearch_coordinator.search(page = 1, from_request_cache = False, multithreading = False)
        assert f"Encountered an unexpected error during iteration for provider, {provider_name}" in caplog.text

        caplog.clear()
        search_results_list_two = multisearch_coordinator.search(page = 1, from_request_cache = False, iterate_by_group = True, multithreading = False)
        assert f"Encountered an unexpected error during iteration for provider, {provider_name}" in caplog.text

        caplog.clear()
        search_results_list_three = multisearch_coordinator.search(page = 1, from_request_cache = False, multithreading = True)
        assert f"Encountered an unexpected error during iteration for provider, {provider_name}" in caplog.text

        assert search_results_list.join() == search_results_list_two.join() == search_results_list_three.join()
        assert len(search_results_list.filter()) == len(multisearch_coordinator.data) - 1 # only one keey is invalid

def test_error_response(coordinator_dict, coordinator_dict_two,  monkeypatch, initialize_mocker, caplog):
    multisearch_coordinator = MultiSearchCoordinator()
    multisearch_coordinator.add_coordinators(list(coordinator_dict.values()) + list(coordinator_dict_two.values()))

    with initialize_mocker() as _:
        # simulate an issue such as an unauthorized error occurring at the level of the provider (as opposed to the query or page
        for key in multisearch_coordinator:
            monkeypatch.setattr(
                multisearch_coordinator[key], 'search', lambda *args, **kwargs:  ErrorResponse.from_response(status_code = 401, url = 'https://test_url', content=b'')
            )
        search_results_list = multisearch_coordinator.search_pages(pages = (1, 2), from_request_cache = False, iterate_by_group = True, multithreading = False)
        assert "Encountered a non-retriable response during retrieval:" in caplog.text
        assert "Halting retrieval for provider" in caplog.text

        # breaks if a non-retriable status code is encountered.
        assert len(search_results_list) == 3
        assert not search_results_list.filter()




