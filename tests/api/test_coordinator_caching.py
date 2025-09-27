from scholar_flux.api.models import ProcessedResponse, ReconstructedResponse, APIResponse
from scholar_flux.api import SearchCoordinator, ResponseCoordinator
from scholar_flux.data import PassThroughDataProcessor
from scholar_flux.exceptions import InvalidResponseStructureException
import requests_mock
import pytest


def test_plos_reprocessing(
    plos_search_api, plos_page_1_url, plos_page_1_data, plos_page_2_url, plos_page_2_data, plos_headers, caplog
):

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

        # ensure that we're pulling from cache for the same response in the future
        response_from_cache = plos_search_coordinator.responses._from_cache(
            response=response, cache_key=processed_response.cache_key
        )
        assert response_from_cache is not None and original_response_created_at == response_from_cache.created_at
        assert f"retrieved response '{processed_response.cache_key}' from cache" in caplog.text

        # if the schema varies, the data for that configuration shouldn't be cached
        # all records should contain an abstract field
        plos_search_coordinator.responses.processor = PassThroughDataProcessor(keep_keys=["abstract"])
        current_schema = plos_search_coordinator.responses.schema_fingerprint()

        # ensure it isn't returning True for validation cache with arbitrary keyword/psitional parameers
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

        assert processed_response.model_dump(exclude={"response"}) == reconstructed_response.model_dump(
            exclude={"response"}
        )
        assert APIResponse.serialize_response(processed_response) == APIResponse.serialize_response(reconstructed_response)  # type: ignore

        newly_reconstructed_response = plos_search_coordinator.responses._from_cache(
            cache_key=processed_response.cache_key, response=reconstructed_response  # type: ignore
        )

        assert reconstructed_response == newly_reconstructed_response

        reconstructed_handled_response = plos_search_coordinator.responses.handle_response(
            response=reconstructed_response, cache_key=processed_response.cache_key  # type: ignore
        )

        # checking for continued idempotence, even when using reconstructed responses retrieved directly from a cache key
        assert reconstructed_handled_response == newly_reconstructed_response


def test_rebuild_processed_response_missing(caplog):

    with pytest.raises(InvalidResponseStructureException) as excinfo:
        _ = ResponseCoordinator._rebuild_processed_response(cache_key=None)  # type: ignore

    assert (
        f"A non-dictionary cache of type {type(None)} was encountered when rebuilding "
        "a ProcessedResponse from its components. Skipping retrieval of processed fields..."
    ) in caplog.text

    assert "Missing the core required fields needed to create a ReconstructedResponse" in str(excinfo.value)
