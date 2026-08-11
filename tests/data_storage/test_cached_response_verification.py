from unittest.mock import Mock

import pytest
from requests import Response

from scholar_flux.api import ReconstructedResponse
from scholar_flux.data_storage import DataCacheManager
from scholar_flux.data_storage.in_memory_storage import InMemoryStorage
from scholar_flux.exceptions import (
    InvalidResponseStructureException,
    MissingResponseException,
)


@pytest.fixture
def original_response_json() -> dict:
    """Fixture of a basic JSON data structure consisting of three minimal records and a metadata dictionary."""
    records = [
        {"a": 1},
        {"b": 2},
        {"c": 3},
    ]
    metadata = {"response_key": "value", "record_num": 3}
    response_json = {**metadata, "data": records}
    return response_json


@pytest.fixture
def original_response(original_response_json) -> ReconstructedResponse:
    """Test fixture for verifying cache behavior for the `DataCacheManager`."""
    url = "https://an-example-url.com"

    original_response = ReconstructedResponse.build(
        url=url,
        json=original_response_json,
        status_code=200,
    )
    return original_response


@pytest.fixture
def updated_response(original_response) -> ReconstructedResponse:
    """Test fixture for verifying caching behavior after content updates."""
    json_dict = original_response.json()
    json_dict["data"] += [{"d": 4}]
    return ReconstructedResponse.build(
        url=original_response.url,
        json=json_dict,
        status_code=200,
    )


@pytest.fixture
def updated_response_with_url_parameters(updated_response) -> ReconstructedResponse:
    """Test fixture for verifying cache behavior for the `DataCacheManager`."""
    url = "https://an-example-url.com?a=1&b=2"

    parameter_dict = updated_response.asdict() | {"url": url}

    return ReconstructedResponse.build(**parameter_dict)


@pytest.fixture
def original_processed_response_dict(original_response) -> dict:
    """Test fixture for verifying processed dictionary response inputs to the data cache manager."""
    cache_key = "reconstructed_response_cache_validation_key"

    json = original_response.json()
    original_response_dict = {
        "cache_key": cache_key,
        "response": original_response,
        "parsed_response": json,
        "metadata": {k: v for k, v in json.items() if k != "data"},
        "extracted_records": json["data"],
        "processed_records": json["data"],
    }
    return original_response_dict


@pytest.fixture
def updated_processed_response_dict(updated_response) -> dict:
    """Test fixture for verifying processed dictionary response inputs to the data cache manager on updates."""
    cache_key = "reconstructed_response_cache_validation_key"

    json = updated_response.json()
    updated_response_dict = {
        "cache_key": cache_key,
        "response": updated_response,
        "parsed_records": json,
        "metadata": {k: v for k, v in json.items() if k != "data"},
        "extracted_records": json["data"],
        "processed_records": json["data"],
    }
    return updated_response_dict


@pytest.fixture()
def default_cache_manager():
    """Fixture that creates a basic `DataCacheManager` for later testing."""
    cache_manager = DataCacheManager()
    return cache_manager


def test_cache_with_different_response_hashes(mock_response):
    """Test cache validation with different response hashes."""
    cache_manager = DataCacheManager(InMemoryStorage())
    cache_key = cache_manager.generate_fallback_cache_key(mock_response)

    # Update with first response
    cache_manager.update_cache(cache_key=cache_key, response=mock_response, processed_records={"original": True})

    # Cache should be valid initially
    assert cache_manager.cache_is_valid(cache_key, mock_response) is True

    # Create a new response with different content
    new_response = Mock(spec=Response)
    new_response.url = "https://api.example.com/test"
    new_response.status_code = 200
    new_response.content = b"different content"

    # Cache should no longer be valid with different content
    assert cache_manager.cache_is_valid(cache_key, new_response) is False


def test_reconstructed_response_cache_verification(
    original_response,
    original_processed_response_dict,
    updated_processed_response_dict,
    default_cache_manager,
):
    """Tests response cache structure validation."""
    cache_key = original_processed_response_dict["cache_key"]
    # Update with first response
    default_cache_manager.update_cache(**original_processed_response_dict)

    # Cache should be valid initially
    assert default_cache_manager.cache_is_valid(cache_key, original_response) is True
    assert default_cache_manager._verify_cached_response(cache_key, updated_processed_response_dict) is True


def test_reconstructed_response_cache_retrieval_from_response(
    original_response,
    original_processed_response_dict,
    default_cache_manager,
):
    """Tests that responses can be retrieved from the response cache via fallback cache keys when available."""
    generated_cache_key = default_cache_manager.generate_fallback_cache_key(
        original_response, original_processed_response_dict
    )
    # Each of the following will be present in the response dict
    core_response_record_keys = ("parsed_response", "metadata", "extracted_records", "processed_records")
    core_response_record_content = {key: original_processed_response_dict[key] for key in core_response_record_keys}

    default_cache_manager.update_cache(
        cache_key=generated_cache_key, response=original_response, store_raw=True, **core_response_record_content
    )

    expected_core_record_dict_fields = dict(
        status_code=original_response.status_code,
        raw_response=original_response.content,
        **core_response_record_content,
    )
    retrieved_response_dict = default_cache_manager.retrieve_from_response(original_response)

    # all fields found in the retrieved response fields should be present in the original dict (cache key not included)
    assert retrieved_response_dict

    nonmatching_fields = {
        key: value
        for key, value in expected_core_record_dict_fields.items()
        if value != retrieved_response_dict.get(key)
    }
    assert not nonmatching_fields


def test_verify_cached_response_invalid_cache_key(
    original_response, original_processed_response_dict, default_cache_manager, caplog
):
    """Tests that the `DataCacheManager._verify_cached_response` returns False if the cache key is None.

    Under the hood, `cache_is_valid` checks that the following holds:
    1. The response hash should not have changed
    2. The cache key within the `cached_response` dictionary should match
    3. The data should have a valid processed response

    The check should fail on the second step since the cross checked, cached response dictionary has a modified cache key

    """
    cache_key = original_processed_response_dict["cache_key"]
    modified_cache_key = "modified_cache_key"
    modified_response_dict = original_processed_response_dict | {"cache_key": modified_cache_key}
    default_cache_manager.update_cache(**original_processed_response_dict)

    # Cache should be valid initially
    assert default_cache_manager.cache_is_valid(cache_key, original_response, modified_response_dict) is False
    assert (
        f"The provided cached response (key={modified_response_dict['cache_key']}) is not associated with the provided cache key "
        f"{cache_key}"
    ) in caplog.text


def test_verify_cached_response_with_empty_processed_records(
    original_response, original_processed_response_dict, default_cache_manager, caplog
):
    """Tests that `DataCacheManager._verify_cached_response` returns False if `processed_records` is missing."""
    cache_key = original_processed_response_dict["cache_key"]
    modified_response_dict = original_processed_response_dict | {"processed_records": None}
    default_cache_manager.update_cache(**modified_response_dict)

    # Cache should be valid initially
    assert default_cache_manager.cache_is_valid(cache_key, original_response) is False
    assert f"Previously processed response is missing for recorded cache key: {cache_key}" in caplog.text


def test_verify_cached_response_with_invalid_type(original_processed_response_dict, default_cache_manager, caplog):
    """Tests that the `DataCacheManager._verify_cached_response` returns False if the cache key is None."""
    cache_key = original_processed_response_dict["cache_key"]
    default_cache_manager.update_cache(**original_processed_response_dict)

    assert (
        default_cache_manager._verify_cached_response(
            cache_key, cached_response="not a cached response dictionary"  # type: ignore
        )
        is False
    )
    assert "The provided `cached_response` is not a dictionary of response fields" in caplog.text


def test_verify_fallback_cache_key_generation_without_url_parameters(
    default_cache_manager, original_response, updated_response, updated_response_with_url_parameters
):
    """Verifies the idempotence of fallback cache key generation by URL."""
    original_fallback_cache_key = default_cache_manager.generate_fallback_cache_key(original_response)
    updated_fallback_cache_key = default_cache_manager.generate_fallback_cache_key(updated_response)
    url_parameters_fallback_cache_key = default_cache_manager.generate_fallback_cache_key(
        updated_response_with_url_parameters, use_parameters=False
    )

    assert original_fallback_cache_key == updated_fallback_cache_key == url_parameters_fallback_cache_key


def test_verify_fallback_cache_key_generation(
    default_cache_manager, original_response, updated_response_with_url_parameters
):
    """Verifies the idempotence of fallback cache key generation by URL with URL parameter sensitivity."""
    original_fallback_cache_key = default_cache_manager.generate_fallback_cache_key(
        original_response, use_parameters=True
    )
    url_parameters_fallback_cache_key = default_cache_manager.generate_fallback_cache_key(
        updated_response_with_url_parameters, use_parameters=True
    )

    assert original_fallback_cache_key != url_parameters_fallback_cache_key


def test_generate_fallback_cache_key_raises_on_invalid_parameters(caplog):
    """Verifies that invalid parameters passed to `DataCacheManager.generate_fallback_cache_key` raises an error."""
    invalid_response = "123"
    msg = f"A response or response-like object was expected, but received type ({type(invalid_response)})"
    with pytest.raises(InvalidResponseStructureException) as excinfo:
        _ = DataCacheManager.generate_fallback_cache_key(invalid_response)  # type: ignore

    assert msg in caplog.text
    assert msg in str(excinfo.value)


def test_generate_fallback_cache_key_raises_on_missing_response(caplog):
    """Verifies that invalid parameters passed to `DataCacheManager.generate_fallback_cache_key` raises an error."""
    invalid_response = None
    msg = "A response or response-like object was expected but was not provided"
    with pytest.raises(MissingResponseException) as excinfo:
        _ = DataCacheManager.generate_fallback_cache_key(invalid_response)  # type: ignore

    assert msg in caplog.text
    assert msg in str(excinfo.value)
