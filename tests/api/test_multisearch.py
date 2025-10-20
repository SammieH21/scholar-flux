from unittest.mock import patch

from scholar_flux.api import SearchAPI, SearchCoordinator
from scholar_flux.api.models import ProcessedResponse, ErrorResponse, NonResponse, SearchResult, SearchResultList


@patch("scholar_flux.api.search_coordinator.SearchCoordinator.search")
def test_multisearch(mock_search, mock_successful_response, mock_rate_limit_exceeded_response, caplog):
    """Test for whether the defaults are specified correctly and whether the mocked response is processed as intended
    throughout the coordinator."""
    extracted_records = [dict(record=1, data=1), dict(record=2, data=2), dict(record=3, data=3)]
    success_response = ProcessedResponse(response=mock_successful_response, extracted_records=extracted_records)
    rate_limit_response = ErrorResponse(response=mock_rate_limit_exceeded_response, message="Rate limit exceeded")

    page_results = [success_response, success_response, rate_limit_response]

    page_list = [1, 2, 3]

    mock_search.side_effect = page_results

    api = SearchAPI.from_defaults(
        provider_name="plos",
        query="test",
        base_url="https://api.example.com",
        records_per_page=len(extracted_records),
        request_delay=0,
    )
    coordinator = SearchCoordinator(api)

    pages = coordinator.search_pages(page_list)
    assert len(pages) == 3
    for page, expected_response in zip(pages, page_results):
        assert (
            page.response_result is not None
            and isinstance(page, SearchResult)
            and page.response_result.status_code == expected_response.status_code
        )
    caplog.text


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
        f"The response for page, 1 contains less than the expected "
        f"{expected_page_count} records. Received {repr(search_result.response_result)}. "
        f"Halting multi-page retrieval..."
    ) in caplog.text
    assert "Skipping the page number, 0, as it is not a valid page number..." in caplog.text


def test_search_exception(monkeypatch, caplog, mock_unauthorized_response):
    """Tests whether exceptions are successfully captured and formatted as an ErrorResponse within a API Response when
    an error is encountered.

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
        f"Received an invalid response for page 1. "
        f"(Status Code: {mock_unauthorized_response.status_code}={mock_unauthorized_response.status}). Halting multi-page retrieval..."
    ) in caplog.text

    monkeypatch.setattr(
        search_coordinator,
        "search",
        lambda *args, **kwargs: (_ for _ in ()).throw(Exception("Directly raised exception")),
    )

    response_list = search_coordinator.search_pages(pages=[1, 2, 3])
    assert isinstance(response_list, SearchResultList) and response_list == []
    assert "Received an invalid response for page 1. " in caplog.text
