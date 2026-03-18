from unittest.mock import patch

from scholar_flux.api import SearchAPI, SearchCoordinator
import requests_mock
from scholar_flux.api.models import (
    ProcessedResponse,
    ErrorResponse,
    NonResponse,
    SearchResult,
    PageListInput,
    SearchResultList,
)
import pytest


@patch("scholar_flux.api.search_coordinator.SearchCoordinator.search")
def test_multisearch(mock_search, mock_successful_response, mock_rate_limit_exceeded_response, caplog):
    """Tests whether `SearchCoordinator.search_pages()` correctly handles both successful and unsuccessful responses."""
    extracted_records = [dict(record=1, data=1), dict(record=2, data=2), dict(record=3, data=3)]

    api = SearchAPI.from_defaults(
        provider_name="plos",
        query="test",
        base_url="https://api.example.com",
        records_per_page=len(extracted_records),
        request_delay=0,
    )

    coordinator = SearchCoordinator(api)

    success_response = ProcessedResponse(response=mock_successful_response, extracted_records=extracted_records)
    rate_limit_response = ErrorResponse(response=mock_rate_limit_exceeded_response, message="Rate limit exceeded")

    page_results = [success_response, success_response, rate_limit_response]

    page_list = [1, 2, 3]

    mock_search.side_effect = page_results

    pages = coordinator.search_pages(page_list)
    assert len(pages) == 3
    for page, expected_response in zip(pages, page_results):
        assert (
            page.response_result is not None
            and isinstance(page, SearchResult)
            and page.response_result.status_code == expected_response.status_code
        )
    caplog.text

    mock_search.side_effect = page_results
    assert coordinator.search_records(7) == pages


@pytest.mark.parametrize(
    "records_per_page,min_records,page_offset,expected_page_count",
    [(5, 10, 0, 2), (6, 15, 1, 3), (3, 12, 0, 4), (3, 12, 5, 4), (0, 5, 0, 0), (3, 0, 5, 0)],
)
def test_coordinator_calculate_page_limit(records_per_page, min_records, page_offset, expected_page_count):
    """Verifies that the pages to be queried as calculated from `PageListInput` equals the expected page count."""
    coordinator = SearchCoordinator(query="q", records_per_page=records_per_page)
    page_limit = PageListInput.from_record_count(min_records, coordinator.api.records_per_page, page_offset)
    assert expected_page_count == len(page_limit.page_numbers)


@pytest.mark.parametrize(
    "page_offset",
    (-1, None, "blue", ["r", "g", "b"]),
)
def test_coordinator_calculate_page_limit_with_invalid_offset(page_offset, caplog):
    """Verifies that `page_offset` defaults to 0 when `PageListInput.from_record_count` receives an invalid value."""
    coordinator = SearchCoordinator(query="q", records_per_page=10)
    page_limit = PageListInput.from_record_count(40, coordinator.api.records_per_page, page_offset)
    assert len(page_limit.page_numbers) == 4

    err = (
        f"Expected a valid, non-negative integer for `page_offset`, but received '{page_offset}'. Defaulting to 0 "
        "instead..."
    )
    assert err in caplog.text


def test_invalid_coordinator_value_retrieval(caplog):
    """Verifies that the pages to be queried calculated from `_calculate_page_limit` equals the expected page count."""
    coordinator = SearchCoordinator(query="q", provider_name="plos")
    with requests_mock.Mocker():
        # Should fail, min_records expects an integer
        invalid_min_records = "puppy"
        search_result_list = coordinator.search_records(min_records=invalid_min_records)  # type: ignore
    e = f"Expected `min_records` to be a positive integer, but received value '{invalid_min_records}'"
    assert f"An unexpected error occurred when processing the response: {e}" in caplog.text
    assert isinstance(search_result_list, SearchResultList) and not search_result_list


def test_search_records_returns_empty_list_with_no_record_count():
    """Verifies that `search_records()` correctly returns an empty result list when `SearchAPI.records_per_page=0`."""
    api = SearchAPI.from_defaults(
        provider_name="plos",
        query="test",
        base_url="https://api.example.com",
        records_per_page=0,
    )
    coordinator = SearchCoordinator(search_api=api)

    with requests_mock.Mocker():
        search_result_list = coordinator.search_records(min_records=5)  # Should return an empty list
        assert isinstance(search_result_list, SearchResultList) and not search_result_list


def test_plos_multisearch_integration(
    plos_coordinator, plos_page_1_url, plos_page_2_url, plos_page_1_data, plos_page_2_data, plos_headers
):
    """Verifies that `search_pages` correctly processes multiple PLOS response pages, enabling record extraction.

    Note:
        This test mocks responses from the PLOS API to verify the behavior of the pre-normalization processing pipeline,
        including the consolidation of records into a single list.

    """
    with (
        plos_coordinator.with_components(annotate_records=True) as coordinator,
        requests_mock.Mocker(real_http=False) as m,
    ):
        m.get(
            plos_page_1_url,
            json=plos_page_1_data,
            headers=plos_headers,
            status_code=200,
        )
        m.get(
            plos_page_2_url,
            json=plos_page_2_data,
            headers=plos_headers,
            status_code=200,
        )

        search_result_list = coordinator.search_pages(pages=[1, 2], request_delay=0.01)
        assert len(search_result_list) == 2
        assert search_result_list.record_count == 200

        record_list = search_result_list.join(strip_annotations=True, include={})
        assert record_list == plos_page_1_data["response"]["docs"] + plos_page_2_data["response"]["docs"]


def test_cache_only_multipage_retrieval_without_halting(caplog):
    """Verifies that `cache_only=True` does not halt retrieval when a page is not available."""
    coordinator = SearchCoordinator(
        provider_name="plos", query="test", base_url="https://example-base-url.com", request_delay=0.01, use_cache=True
    )
    pages = list(range(1, 4))
    with requests_mock.Mocker(real_http=False):
        # Retrieval should return None here:
        results = coordinator.search_pages(pages=pages, cache_only=True)

    assert len(results) == len(pages)

    for result in results:
        assert (
            f"Failed to retrieve page {result.page} from the session cache for the provider, "
            f"{coordinator.display_name}."
        ) in caplog.text
        assert (
            f"Response retrieval from {coordinator.display_name} for page {result.page} was unsuccessful: "
            f"{result.message}" in caplog.text
        )


@patch("scholar_flux.api.search_coordinator.SearchCoordinator.search")
def test_last_response_page(mock_search, mock_successful_response, mock_unauthorized_response, caplog):
    """Test for whether the defaults are specified correctly and whether the mocked response is processed as intended
    throughout the coordinator."""
    extracted_records = [dict(record=1, data=1), dict(record=2, data=2), dict(record=3, data=3)]
    success_response = ProcessedResponse(response=mock_successful_response, extracted_records=extracted_records)
    no_response = None
    unauthorized_response = ErrorResponse(response=mock_unauthorized_response, message="Unauthorized")

    page_results = [no_response, success_response, unauthorized_response]

    page_list = [0, 1, 2]

    mock_search.side_effect = page_results

    expected_page_count = len(extracted_records) + 1
    api = SearchAPI.from_defaults(
        provider_name="plos",
        query="test",
        base_url="https://api.example.com",
        records_per_page=expected_page_count,  # so that it simulates the last response page
        request_delay=0,
    )

    coordinator = SearchCoordinator(api)

    pages = coordinator.search_pages(page_list)
    assert len(pages) == 2
    search_result = pages[1]  # get the result for page 1
    assert (
        f"The response from {coordinator.display_name} for page, 1 contains less than the expected "
        f"{expected_page_count} records. Received {repr(search_result.response_result)}. "
        f"Halting multi-page retrieval..."
    ) in caplog.text
    assert "Skipping the page number, 0, as it is not a valid page number..." in caplog.text


def test_search_exception(monkeypatch, caplog, mock_unauthorized_response):
    """Verifies that exceptions are successfully handled and formatted as an ErrorResponse when an error is encountered.

    The presence of a specific error should ideally halt the process, especially relevant when encountering `400` status
    codes.

    """
    search_coordinator = SearchCoordinator(query="test_query", base_url="https://thisisatesturl.com")

    monkeypatch.setattr(
        search_coordinator.api.session,
        "send",
        lambda *args, **kwargs: (_ for _ in ()).throw(Exception("Directly raised exception")),
    )

    response_list = search_coordinator.search_pages(pages=[0, 1, 2, 3])
    non_response_0 = response_list[0].response_result
    non_response_1 = response_list[1].response_result

    assert isinstance(non_response_0, NonResponse) and isinstance(non_response_1, NonResponse)
    assert len(response_list) == 2
    assert "Skipping the page number, 0, as it is not a valid page number..." in caplog.text
    assert (
        f"Could not retrieve a valid response code for page 1. "
        f"Received {repr(non_response_1)}. Halting multi-page retrieval..."
    ) in caplog.text

    monkeypatch.setattr(search_coordinator.api, "search", lambda *args, **kwargs: mock_unauthorized_response)

    response_list = search_coordinator.search_pages(pages=[1, 2, 3])
    assert len(response_list) == 1 and isinstance(response_list[0].response_result, ErrorResponse)
    assert (
        f"Received an invalid response from {search_coordinator.display_name} for page 1. "
        f"(Status Code: {mock_unauthorized_response.status_code}={mock_unauthorized_response.status}). Halting multi-page retrieval..."
    ) in caplog.text

    monkeypatch.setattr(
        search_coordinator,
        "search",
        lambda *args, **kwargs: (_ for _ in ()).throw(Exception("Directly raised exception")),
    )

    response_list = search_coordinator.search_pages(pages=[1, 2, 3])
    assert isinstance(response_list, SearchResultList) and response_list == []
    assert f"Received an invalid response from {search_coordinator.display_name} for page 1. " in caplog.text
