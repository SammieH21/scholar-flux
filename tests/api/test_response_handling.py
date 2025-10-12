from scholar_flux import ResponseCoordinator, DataCacheManager
from scholar_flux.api import ResponseValidator
from scholar_flux.data_storage import InMemoryStorage
from scholar_flux.api.models import ErrorResponse, ReconstructedResponse
from scholar_flux.exceptions import StorageCacheException, InvalidResponseException
import pytest
import requests
import re

from scholar_flux.exceptions.data_exceptions import DataParsingException


def test_default_cache():
    """
    Tests whether the response coordinator builds with an in-memory cache as intended with the defaults.
    null cache managers, should always be replaced when directly specifying a value for cache_results.
    """
    response_coordinator = ResponseCoordinator.build()
    assert response_coordinator.cache_manager

    response_coordinator = ResponseCoordinator.build(cache_manager=DataCacheManager.null(), cache_results=True)
    assert isinstance(response_coordinator.cache_manager.cache_storage, InMemoryStorage)


def test_plos_handling(plos_page_1_response, monkeypatch, caplog):
    """
    Tests whether, upon receiving a valid response object, the ResponseCoordinator wll process
    the result as intended. handle_response, when successful returns a ProcessedResponse while the
    handle_response_data method returns the underlying list of dictionary records from the response.

    The code also verifies whether caching occurs as intended and whether, if an error occurs,
    the response result will catch and log the error while returning None as intended.
    """
    assert isinstance(plos_page_1_response, requests.Response)

    response_coordinator = ResponseCoordinator.build(cache_results=True)

    record_list = response_coordinator.handle_response_data(plos_page_1_response, cache_key="test_cache_key")
    assert isinstance(record_list, list) and all(isinstance(record, dict) for record in record_list)

    monkeypatch.setattr(response_coordinator.cache_manager, "retrieve", lambda *args, **kwargs: None)

    assert response_coordinator._from_cache(response=plos_page_1_response) is None
    assert response_coordinator._from_cache(response=plos_page_1_response, cache_key="test_cache_key") is None

    monkeypatch.setattr(
        response_coordinator.cache_manager,
        "generate_fallback_cache_key",
        lambda *args, **kwargs: (_ for _ in ()).throw(StorageCacheException("Directly raised exception")),
    )

    assert response_coordinator._from_cache(response=plos_page_1_response) is None
    assert re.search(
        "An exception occurred while attempting to retrieve '[a-zA-Z0-9]+' " "from cache: Directly raised exception",
        caplog.text,
    )


def test_error_handling(plos_page_1_response, monkeypatch):
    """
    Test whether errors in responses are handled as intended to aid the creation of an ErrorResponse
    when encountering errors at any point in the response handling process. The _process_response
    function is parsed to throw an DataParsingException to simulate an error occurring in the
    response handling process.
    """

    response_coordinator = ResponseCoordinator.build(cache_results=True)
    monkeypatch.setattr(
        response_coordinator,
        "_process_response",
        lambda *args, **kwargs: (_ for _ in ()).throw(DataParsingException("Directly raised exception")),
    )

    error_response = response_coordinator.handle_response(plos_page_1_response)
    assert isinstance(error_response, ErrorResponse)
    assert error_response.message and "Error processing" in error_response.message

    monkeypatch.setattr(
        response_coordinator,
        "_process_response",
        lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("Directly raised exception")),
    )

    error_response = response_coordinator.handle_response(plos_page_1_response)
    assert isinstance(error_response, ErrorResponse)
    assert (
        error_response.message
        and "An unexpected error occurred during the processing of the response: Directly raised exception"
        in error_response.message
    )


def test_data_parsing_exception(plos_page_1_response, monkeypatch, caplog):
    """
    Tests whether exceptions are caught and handled as intended upon encountering errors in data parsing.
    This function patches the parser to throw an error upon being called in order to determine whether
    an ErrorResponse is returned as intended, stating the error message encountered.
    """

    response_coordinator = ResponseCoordinator.build(cache_results=True)

    monkeypatch.setattr(
        response_coordinator.parser,
        "parse",
        lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("Directly raised exception")),
    )

    error_response = response_coordinator.handle_response(plos_page_1_response)
    assert isinstance(error_response, ErrorResponse)
    assert (
        error_response.message
        and "An unexpected error occurred during the processing of the response: Directly raised exception"
        in error_response.message
    )


def test_empty_data_parsing_exception(plos_page_1_response, monkeypatch, caplog):
    """
    Ensures that upon receiving a None value from the `parse` method of the response_coordinator.parser,
    the `handle_response` method will raise a DataParsingException.
    """

    response_coordinator = ResponseCoordinator.build(cache_results=True)

    monkeypatch.setattr(response_coordinator.parser, "parse", lambda *args, **kwargs: None)

    with pytest.raises(DataParsingException) as excinfo:
        response_coordinator._process_response(plos_page_1_response)

    assert "The parsed response contained no parsable content" in str(excinfo.value)


def test_inccorrect_data_parsing_exception(plos_page_1_response, monkeypatch, caplog):
    """
    Ensures that upon receiving a None value from the `parse` method of the response_coordinator.parser,
    the `handle_response` method will raise a DataParsingException.
    """

    response_coordinator = ResponseCoordinator.build(cache_results=True)

    dictionary_response = plos_page_1_response.__dict__

    with pytest.raises(DataParsingException) as excinfo:
        response_coordinator._process_response(dictionary_response)
    assert f"Expected a response or response-like object, received type {type(dictionary_response)}" in str(
        excinfo.value
    )

    updated_response = ReconstructedResponse.build(plos_page_1_response)
    updated_response.headers = {}

    with pytest.raises(DataParsingException) as excinfo:
        response_coordinator._process_response(updated_response)
    assert "Unsupported content type: ''" in caplog.text

    result = response_coordinator.parser.parse_from_defaults(updated_response)
    assert result is None
    assert "Unsupported format: 'unknown'" in caplog.text


def test_response_validator_representation():
    """
    Verifies that the ResponseValidator class, when printed in the CLI, creates a reasonably simple CLI representation
    """
    response_validator = ResponseValidator()
    assert repr(response_validator) == "ResponseValidator()"


def test_invalid_response_validation(mock_unauthorized_response):
    """
    Tests that the response validator raises an error when `raise_on_error = True` and returns a boolean otherwise
    when encountering invalid responses with level 400/500 status codes
    """
    assert ResponseValidator.validate_response(mock_unauthorized_response, raise_on_error=False) is False
    with pytest.raises(InvalidResponseException):
        _ = ResponseValidator.validate_response(mock_unauthorized_response, raise_on_error=True)


def test_response_content_validation(plos_page_1_response, caplog):
    """
    Tests whether the ResponseValidator verifies whether the response object contains application/json in the header.
    On `raise_on_error`=False, a boolean should be returned while an error should be raised otherwise when a
    JSON, XML, or YAML-based response is not provided based on the content headers.
    """
    assert ResponseValidator.validate_content(plos_page_1_response, expected_format="application/json") is True

    assert (
        ResponseValidator.validate_content(
            plos_page_1_response, expected_format="application/txt", raise_on_error=False
        )
        is False
    )

    with pytest.raises(InvalidResponseException) as excinfo:
        _ = ResponseValidator.validate_content(
            plos_page_1_response, raise_on_error=True, expected_format="application/txt"
        )

    assert (
        "Content type validation failed: received 'application/json charset=UTF-8', and expected 'application/txt'"
        in str(caplog.text)
    )
    assert "Invalid Response format: received 'application/json charset=UTF-8', and expected 'application/txt'" in str(
        excinfo.value
    )


def test_response_coordinator_summary():
    """
    Tests and Verifies that the summary of the structure of the ResponseCoordinator contains the required attribute
    summaries.
    """
    response_coordinator = ResponseCoordinator.build()
    representation = response_coordinator.summary()

    assert re.search(r"^ResponseCoordinator\(.*\)$", representation, re.DOTALL)
    assert f"parser={response_coordinator.parser.__class__.__name__}(...)" in representation
    assert f"extractor={response_coordinator.extractor.__class__.__name__}(...)" in representation
    assert (
        f"cache_manager={response_coordinator.cache_manager.__class__.__name__}(cache_storage={response_coordinator.cache_manager.cache_storage.__class__.__name__}(...))"
        in representation
    )  # ignore padding
