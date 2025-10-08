from scholar_flux.api.models import ProcessedResponse, ReconstructedResponse, APIResponse
from scholar_flux.api import SearchCoordinator, ResponseCoordinator
from scholar_flux.data import PassThroughDataProcessor
from scholar_flux.utils import parse_iso_timestamp
from scholar_flux.exceptions import InvalidResponseStructureException
from requests import Response
import requests_mock
import pytest


def test_plos_reprocessing(plos_search_api, plos_page_1_url, plos_page_1_data, plos_headers, caplog):
    """
    Test whether caching occurs as intended with the underlying response coordinator and accounts for
    both common and special cases.

    First, the search should be successful and afterward, cache the response.

    The caching mechanism is verified by determining whether the created_at date is created as intended and is not null

    Because the structure and options of the response_coordinator can have an impact the final result,
    schema validation should be performed to determine whether to pull from the processing cache
    (as opposed to the requests_cache)
    """

    response_coordinator = ResponseCoordinator.build(processor=PassThroughDataProcessor(), cache_results=True)

    plos_search_coordinator = SearchCoordinator(
        query="social wealth equity",
        search_api=plos_search_api,
        response_coordinator=response_coordinator,
        provider_name="plos",
    )

    original_schema = plos_search_coordinator.responses.schema_fingerprint()

    with requests_mock.Mocker() as m:
        m.get(
            plos_page_1_url,
            json=plos_page_1_data,
            headers=plos_headers,
            status_code=200,
        )

        # process the code once, so it remains in cache
        processed_response = plos_search_coordinator.search(page=1)
        assert isinstance(processed_response, ProcessedResponse) and processed_response.response is not None
        assert processed_response.created_at

        original_response_created_at = processed_response.created_at
        response = processed_response.response

        # ensure the response time was recorded as a valid string
        assert (
            isinstance(original_response_created_at, str)
            and parse_iso_timestamp(original_response_created_at) is not None
        )

        # ensure that we received a valid response object
        assert isinstance(response, Response)

        # ensure that we're pulling from cache for the same response in the future
        response_from_cache = plos_search_coordinator.responses._from_cache(
            response=response, cache_key=processed_response.cache_key
        )

        # the created_at time should be exactly the same if we're pulling from cache
        assert response_from_cache is not None and original_response_created_at == response_from_cache.created_at
        assert f"retrieved response '{processed_response.cache_key}' from cache" in caplog.text

        # if the schema varies, the data for that configuration shouldn't be cached
        # all records should contain an abstract field
        plos_search_coordinator.responses.processor = PassThroughDataProcessor(keep_keys=["abstract"])
        current_schema = plos_search_coordinator.responses.schema_fingerprint()

        # ensure it isn't returning True for validation cache with arbitrary keyword/positional parameters
        assert plos_search_coordinator.responses._validate_cached_schema(None) is False  # type:ignore

        # the field should not be retrievable via processing cache with the current configuration
        assert (
            plos_search_coordinator.responses._from_cache(response=response, cache_key=processed_response.cache_key)
            is None
        )

        assert (
            "The current schema does not match the previous schema that generated the "
            f"previously cached response.\n\n Current schema: \n{current_schema}\n"
            f"\nCached schema: \n{original_schema}\n\n Skipping retrieval from cache."
        ) in caplog.text

        # if schema checks are turned off, then the previous cache should be retrieved regardless:
        assert (
            plos_search_coordinator.responses._from_cache(
                response=response,
                cache_key=processed_response.cache_key,
            )
            is None
        )


def cache_without_keys(caplog):
    """
    Tests whether attempts to retrieve from cache without a key returns nothing, as expected,
    and verify that logs operate as intended when unsuccessfully retrieving an invalid cache key
    """
    response_coordinator = ResponseCoordinator.build(processor=PassThroughDataProcessor(), cache_results=True)
    response_without_cache_key = response_coordinator._from_cache(cache_key=None)  # type: ignore
    assert response_without_cache_key is None
    assert "A cache key was not specified. Attempting to create a cache key from the response..." in caplog.text
    assert "A response or response-like object was expected but was not provided" in caplog.text
    caplog.clear()

    response_without_valid_cache_key = response_coordinator._from_cache(cache_key=1)  # type: ignore
    assert "A cache key was not specified. Attempting to create a cache key from the response..." in caplog.text
    assert f"A response or response-like object was expected, Received ({type(1)})" in caplog.text
    assert response_without_valid_cache_key is None


def test_cache_without_response(
    plos_search_api, plos_page_1_url, plos_page_1_data, plos_page_2_url, plos_page_2_data, plos_headers, caplog
):
    """
    Tests whether pulling from cache without using a valid response will still return a value, except without
    additional validation checks such as content hashes and response comparisons. Without this response,
    a ReconstructedResponse instance will be created from the core cached elements of the response.

    This script also checks for idempotence when pulling from cache using a ReconstructedResponse instead of
    a requests.Response instance
    """
    response_coordinator = ResponseCoordinator.build(processor=PassThroughDataProcessor(), cache_results=True)
    plos_search_coordinator = SearchCoordinator(
        query="social wealth equity",
        search_api=plos_search_api,
        response_coordinator=response_coordinator,
        provider_name="plos",
    )

    with requests_mock.Mocker() as m:
        m.get(
            plos_page_1_url,
            json=plos_page_1_data,
            headers=plos_headers,
            status_code=200,
        )

        # process the code once, so it remains in cache
        processed_response = plos_search_coordinator.search(page=1)
        assert (
            isinstance(processed_response, ProcessedResponse) and processed_response.cache_key
        )  # a cache key should exist at this point

        # attempt to retrieve the response without response hash validation
        reconstructed_response = plos_search_coordinator.responses._from_cache(cache_key=processed_response.cache_key)
        assert reconstructed_response and isinstance(reconstructed_response.response, ReconstructedResponse)

        # throws an error if unsuccessful
        reconstructed_response.response.validate()

        # ensures that the reconstructed response matches the core response elements from the original
        assert processed_response.model_dump(exclude={"response"}) == reconstructed_response.model_dump(
            exclude={"response"}
        )
        assert APIResponse.serialize_response(processed_response) == APIResponse.serialize_response(reconstructed_response)  # type: ignore

        newly_reconstructed_response = plos_search_coordinator.responses._from_cache(
            cache_key=processed_response.cache_key, response=reconstructed_response  # type: ignore
        )

        # idempotence with repeat pulling from  cache
        assert reconstructed_response == newly_reconstructed_response

        reconstructed_handled_response = plos_search_coordinator.responses.handle_response(
            response=reconstructed_response, cache_key=processed_response.cache_key  # type: ignore
        )

        # checking for continued idempotence, even when using reconstructed responses retrieved directly from a cache key
        assert reconstructed_handled_response == newly_reconstructed_response


def test_rebuild_processed_response_missing(caplog):
    """
    Tests and verifies that an attempt to rebuild a processed response will return the expected error and log message
    without the specification of a cache key
    """

    with pytest.raises(InvalidResponseStructureException) as excinfo:
        _ = ResponseCoordinator._rebuild_processed_response(cache_key=None)  # type: ignore

    assert (
        f"A non-dictionary cache of type {type(None)} was encountered when rebuilding "
        "a ProcessedResponse from its components. Skipping retrieval of processed fields..."
    ) in caplog.text

    assert "Missing the core required fields needed to create a ReconstructedResponse" in str(excinfo.value)
