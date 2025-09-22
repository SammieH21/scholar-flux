from scholar_flux.api.models import ProcessedResponse
from scholar_flux.api import SearchCoordinator, ResponseCoordinator
from scholar_flux.data import PassThroughDataProcessor
import requests_mock


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
        response = processed_response.response

        # ensure that we're pulling from cache for the same response in the future
        assert (
            plos_search_coordinator.responses._from_cache(response, cache_key=processed_response.cache_key) is not None
        )
        assert f"retrieved response '{processed_response.cache_key}' from cache" in caplog.text

        # if the schema varies, the data for that configuration shouldn't be cached
        # all records should contain an abstract field
        plos_search_coordinator.responses.processor = PassThroughDataProcessor(keep_keys=["abstract"])
        current_schema = plos_search_coordinator.responses.schema_fingerprint()

        # the field should not be retrievable via processing cache with the current configuration
        assert plos_search_coordinator.responses._from_cache(response, cache_key=processed_response.cache_key) is None

        assert (
            "The current schema does not match the previous schema that generated the "
            f"previously cached response.\n\n Current schema: \n{current_schema}\n"
            f"\nCached schema: \n{original_schema}\n\n Skipping retrieval from cache."
        ) in caplog.text

        # if schema checks are turned off, then the previous cache should be retrieved regardless:
        assert (
            plos_search_coordinator.responses._from_cache(
                response,
                cache_key=processed_response.cache_key,
            )
            is None
        )
