from scholar_flux.api.models import (
    ProcessedResponse,
    ErrorResponse,
    SearchResult,
    SearchResultList,
)
from typing import Any
import pytest


@pytest.fixture
def extracted_records() -> list[dict[str, int]]:
    """Mocks the extracted_records attribute that indicates the total number of records present in the response."""
    extracted_records = [dict(record=1, data=1), dict(record=2, data=2), dict(record=3, data=3)]
    return extracted_records


@pytest.fixture
def processed_records(extracted_records) -> list[dict[str, int]]:
    """Fixture for mocking the processed_records attribute in the creation of a ProcessedResponse."""
    processed_records = extracted_records.copy()
    return processed_records


@pytest.fixture
def normalized_records(processed_records) -> list[dict[str, int]]:
    """Fixture for mocking the normalized_records attribute in the creation of a ProcessedResponse."""
    normalized_records = [
        {str(key): value for key, value in record.items()} | {"provider_name": "test"} for record in processed_records
    ]

    return normalized_records


@pytest.fixture
def metadata() -> dict[str, Any]:
    """Mocks a simple metadata dictionary used in creating a success_response."""
    metadata = {"a": 1, "b": 2}
    return metadata


@pytest.fixture
def success_response(
    mock_successful_response, extracted_records, metadata, processed_records, normalized_records
) -> ProcessedResponse:
    """Fixture used to mock an SuccessResponse to be later encapsulated in a SearchResult."""
    success_response = ProcessedResponse(
        cache_key="test-cache-key",
        response=mock_successful_response,
        extracted_records=extracted_records,
        processed_records=processed_records,
        metadata=metadata,
        normalized_records=normalized_records,
    )
    return success_response


@pytest.fixture
def unauthorized_response(mock_unauthorized_response) -> ErrorResponse:
    """Fixture used to mock an ErrorResponse to be later encapsulated in a SearchResult."""
    unauthorized_response = ErrorResponse(
        response=mock_unauthorized_response,
        message="This is an unauthorized response",
        error="Unauthorized",
        cache_key="test-cache-key",
    )
    return unauthorized_response


@pytest.fixture
def search_result_success(extracted_records, processed_records, metadata) -> SearchResult:
    """Fixture that indicates that the retrieval and processing of the response was successful."""

    search_result_success = SearchResult(
        provider_name="test-provider",
        query="test-query",
        page=1,
        response_result=ProcessedResponse.from_response(
            cache_key="test-cache-key",
            status_code=200,
            url="https://www.example-url-test.com",
            extracted_records=extracted_records,
            processed_records=processed_records,
            metadata=metadata,
        ),
    )

    return search_result_success


@pytest.fixture
def search_result_error() -> SearchResult:
    """Fixture that indicates that an error occurred somewhere in the retrieval or processing of the API Response."""
    search_result_error = SearchResult(
        provider_name="test-provider",
        query="test-query",
        page=2,
        response_result=ErrorResponse.from_response(
            cache_key="test-cache-key", status_code=401, url="https://www.example-url-test.com"
        ),
    )

    return search_result_error


@pytest.fixture
def search_result_none() -> SearchResult:
    """Indicates that a request could not be retrieved as intended - logs should be checked in such scenarios"""
    return SearchResult(provider_name="test-provider", query="test-query", page=3, response_result=None)


def test_search_result_errors(unauthorized_response):
    """Tests the instantiation of SearchResult with ErrorResponses and verifies whether the attributes are retrievable.

    Also verifies whether error responses contain the logged errors involved and associated messages.

    """
    search_result_error = SearchResult(
        provider_name="test-provider",
        query="test-query",
        page=2,
        response_result=unauthorized_response,
    )

    # validating the attributes of the `search_result_error` instance that holds an ErrorResponse
    assert search_result_error != unauthorized_response  # the two aren't the same class, so this shouldn't equal
    assert search_result_error.data is None
    assert search_result_error.metadata is None
    assert search_result_error.extracted_records is None
    assert search_result_error.response == unauthorized_response.response
    assert search_result_error.error == "Unauthorized"
    assert search_result_error.message == "This is an unauthorized response"
    assert len(search_result_error) == search_result_error.record_count == 0
    assert search_result_error.cache_key == "test-cache-key"

    # ensuring that the search_result_error is falsy
    assert isinstance(search_result_error, SearchResult) and not search_result_error


def test_search_result_success(success_response, extracted_records, metadata, processed_records, normalized_records):
    """Tests the instantiation of SearchResults with ProcessedResponses to verifies whether attributes are retrievable.

    Also verifies whether processed responses contain the correct extracted and processed records and whether error
    responses contain the logged errors involved and associated messages.

    """

    search_result_success = SearchResult(
        provider_name="test-provider", query="test-query", page=1, response_result=success_response
    )

    # ensuring that the search_result_success is truthy
    assert search_result_success

    # validating elements of the search_result_success class
    assert isinstance(search_result_success, SearchResult) and search_result_success.response_result
    assert search_result_success.data == processed_records == search_result_success.processed_records
    assert search_result_success.normalized_records == normalized_records
    assert search_result_success.metadata == metadata
    assert search_result_success.parsed_response is None
    assert search_result_success.extracted_records == extracted_records
    assert search_result_success.response == success_response.response
    assert search_result_success.error is None
    assert search_result_success.message is None

    assert (
        len(search_result_success)
        == len(search_result_success.data or [])
        == len(search_result_success.extracted_records or [])
        == search_result_success.record_count
    )

    assert search_result_success.cache_key == "test-cache-key"


def test_invalid_search_list_elements():
    """Tests whether the SearchResultList correctly raises a type error when encountering invalid values."""
    result_list = SearchResultList()

    with pytest.raises(TypeError):
        result_list.append(1)  # type: ignore

    with pytest.raises(TypeError):
        result_list[0] = True  # type: ignore

    with pytest.raises(TypeError):
        result_list.extend([True, False])  # type: ignore


def test_valid_search_list_elements(search_result_success, search_result_error, search_result_none):
    """Verifies whether the SearchResultList successfully adds SearchResult instances to the list."""
    result_list = SearchResultList()

    result_list.extend(SearchResultList([search_result_success, search_result_error]))
    result_list.append(search_result_error)  # duplicated value
    result_list[2] = search_result_none  # replacement value

    assert len(result_list) == 3
    assert result_list[-1].response_result is None

    filtered_records = result_list.filter()
    assert (
        isinstance(filtered_records[0], SearchResult)
        and isinstance(filtered_records[0].response_result, ProcessedResponse)
        and len(filtered_records[0].response_result.data or []) > 0
    )

    data_records = filtered_records[0].response_result.data or []  # type: ignore
    joined_records = result_list.join()

    response_record_total = sum(
        len(result.response_result.data or []) for result in filtered_records if result.response_result
    )

    assert len(joined_records) == response_record_total == result_list.record_count
    assert joined_records == [record | {"provider_name": "test-provider", "page_number": 1} for record in data_records]


def test_search_result_selection():
    """Verifies elements of a SearchResultList can be selected based on query, provider, and/or page."""

    pages = list(range(1, 5))  # 1 to 4
    mock_providers = ["Provider_one", "ProviderTwo", "ProviderThree"]
    mock_queries = ["test-query-one", "test-query-two", "test-query-three"]
    search_result_list = SearchResultList(
        SearchResult(page=i, provider_name=provider_name, query=query)
        for i in pages
        for provider_name in mock_providers
        for query in mock_queries
    )
    filtered_search_results = search_result_list.select(page=1)

    assert len(mock_providers) * len(mock_queries) == len(filtered_search_results)

    assert all(
        SearchResult(page=1, provider_name=provider_name, query=query) in filtered_search_results
        for query in mock_queries
        for provider_name in mock_providers
    )

    # provider names should resolve with normalization
    filtered_search_results_two = search_result_list.select(query="test-query-one", provider_name="provider_one")
    assert len(pages) == len(filtered_search_results_two)
    filtered_search_results_two_pages = (search_result.page for search_result in filtered_search_results_two)
    assert all(page in filtered_search_results_two_pages for page in pages)

    for search_result in search_result_list:
        filtered_search_result = (
            search_result_list.select(query=search_result.query)
            .select(provider_name=search_result.provider_name)
            .select(page=search_result.page)
        )

        assert len(filtered_search_result) == 1 and filtered_search_result[0] == search_result
