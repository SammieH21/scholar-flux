from scholar_flux.api import SearchCoordinator, SearchAPI, SearchAPIConfig, APIParameterConfig
from scholar_flux.data import RecursiveDataProcessor
from scholar_flux.api.models import ProcessedResponse
from scholar_flux.sessions import CachedSessionManager
from scholar_flux.data_storage import DataCacheManager
from pydantic import SecretStr
from requests_mock import Mocker
import requests_mock
from requests_cache import CachedSession, CachedResponse
import pytest




@pytest.mark.parametrize(
    ['cache_backend', 'cache_kwargs', 'cache_requests'],
    [
        ("redis", {}, True),
        ("null", {}, True),
        ("inmemory", {}, True),
        ("sql", {"url": "sqlite_db_url"}, True),
        ("redis", {}, False),
        ("null", {}, False),
        ("inmemory", {}, False),
        ("sql", {"url": "sqlite_db_url"}, False),
    ]
)
def test_response_cache(
    mock_academic_json_response,
    db_dependency_unavailable,
    request,
    cache_backend,
    cache_kwargs,
    cache_requests
):
    # Skip if required dependency is missing
    if db_dependency_unavailable(cache_backend):
        pytest.skip(f"{cache_backend} not available")

    search_api_config = SearchAPIConfig(
        records_per_page=3,
        request_delay=0.01,
        base_url="https://test_url.com/search",
        api_key=SecretStr("this-is-a-test-key"),
        api_specific_parameters=dict(mailto=SecretStr("this.is.a@testemail.com")),
    )
    api = SearchAPI.from_settings(
        config=search_api_config,
        parameter_config=APIParameterConfig.from_defaults("crossref"),
        query="Computationaly Aided Analysis",
    )
    cache_kwargs = {k: request.getfixturevalue(v) for k, v in cache_kwargs.items()}
    storage_cache = DataCacheManager.with_storage(cache_backend, **cache_kwargs)
    search_coordinator = SearchCoordinator(
        api, cache_manager=storage_cache,
        use_cache = cache_requests, 
        processor=RecursiveDataProcessor()
    )

    search_coordinator._delete_cached_request(page=1)
    search_coordinator._delete_cached_response(page=1)
    prepared_request = api.prepare_request(api.base_url,
                                           parameters=api.build_parameters(page=1))

    with Mocker() as m:
        m.get(
            prepared_request.url,
            status_code=mock_academic_json_response.status_code,
            json=mock_academic_json_response.json,
            headers={"Content-Type": "application/json"},
        )
        cache_key = search_coordinator._create_cache_key(page=1)
        assert not search_coordinator.response_coordinator.cache_manager.verify_cache(cache_key)
        processed_response = search_coordinator.search(page=1)
        # either the response processing is now cached or we were using a null storage which doesn't cache
        assert search_coordinator.response_coordinator.cache_manager.verify_cache(cache_key) ^ storage_cache.isnull()
        assert processed_response
        response = processed_response.response
        assert response is not None and prepared_request.url == response.url

        processed_cached_response = search_coordinator.search(page=1)
        assert isinstance(processed_cached_response, ProcessedResponse)
        cached_response = processed_cached_response.response
 
        assert getattr(cached_response, "from_cache", False) is cache_requests

        # ensure that processing isn't saved with the null storage
        if cache_backend == "null":
            assert not search_coordinator.response_coordinator.cache_manager.verify_cache(cache_key)
            retrieved_cache = search_coordinator.response_coordinator.cache_manager.retrieve(cache_key)
            assert retrieved_cache == {} and retrieved_cache != search_coordinator.search_data(page=1)
        else:
            # ensure that the retrieval of cached and uncached processed responses returns the same result
            assert search_coordinator.response_coordinator.cache_manager.verify_cache(cache_key)
            retrieved_cache = search_coordinator.response_coordinator.cache_manager.retrieve(cache_key)
            retrieved_data = search_coordinator.search_data(page=1, from_process_cache = False)
            assert retrieved_cache is not None and retrieved_cache["processed_response"] == retrieved_data
            search_coordinator._delete_cached_response(page=1)
