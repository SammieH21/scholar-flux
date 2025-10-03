from scholar_flux.api.models import (
    ProcessedResponse,
    ErrorResponse,
    SearchResult,
    SearchResultList,
)
import pytest


def test_basic_search_results(mock_successful_response, mock_unauthorized_response, caplog):
    """
    Test for whether the defaults are specified correctly and whether the mocked response is processed
    as intended throughout the coordinator
    """
    extracted_records = [dict(record=1, data=1), dict(record=2, data=2), dict(record=3, data=3)]
    processed_records = extracted_records.copy()
    metadata = {"a": 1, "b": 2}

    success_response = ProcessedResponse(
        response=mock_successful_response,
        extracted_records=extracted_records,
        processed_records=processed_records,
        metadata=metadata,
    )

    unauthorized_response = ErrorResponse(
        response=mock_unauthorized_response, message="This is an unauthorized response", error="Unauthorized"
    )

    search_result_success = SearchResult(
        provider_name="test-provider", query="test-query", page=1, response_result=success_response
    )

    search_result_error = SearchResult(
        provider_name="test-provider", query="test-query", page=2, response_result=unauthorized_response
    )

    assert isinstance(search_result_success, SearchResult) and search_result_success
    assert search_result_success.data == processed_records == search_result_success.processed_records
    assert search_result_error != unauthorized_response  # the two aren't the same class, so this shouldn't equal
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
    )

    assert isinstance(search_result_error, SearchResult) and not search_result_error
    assert search_result_error.data is None
    assert search_result_error.metadata is None
    assert search_result_error.extracted_records is None
    assert search_result_error.response == unauthorized_response.response
    assert search_result_error.error == "Unauthorized"
    assert search_result_error.message == "This is an unauthorized response"
    assert len(search_result_error) == 0

    assert search_result_success.cache_key == search_result_error.cache_key


def test_invalid_search_list():
    result_list = SearchResultList()

    extracted_records = [dict(record=1, data=1), dict(record=2, data=2), dict(record=3, data=3)]
    processed_records = extracted_records.copy()
    metadata = {"a": 1, "b": 2}

    search_result_success = SearchResult(
        provider_name="test-provider",
        query="test-query",
        page=1,
        response_result=ProcessedResponse.from_response(
            cahe_key="test-cache-key",
            status_code=200,
            url="https://www.example-url-test.com",
            extracted_records=extracted_records,
            processed_records=processed_records,
            metadata=metadata,
        ),
    )

    search_result_error = SearchResult(
        provider_name="test-provider",
        query="test-query",
        page=2,
        response_result=ErrorResponse.from_response(
            cahe_key="test-cache-key", status_code=401, url="https://www.example-url-test.com"
        ),
    )

    search_result_none = SearchResult(provider_name="test-provider", query="test-query", page=3, response_result=None)

    with pytest.raises(TypeError):
        result_list.append(1)  # type: ignore

    with pytest.raises(TypeError):
        result_list[0] = True  # type: ignore

    with pytest.raises(TypeError):
        result_list.extend([True, False])  # type: ignore

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

    assert len(joined_records) == response_record_total
    assert joined_records == [record | {"provider_name": "test-provider", "page_number": 1} for record in data_records]
