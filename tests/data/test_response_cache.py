from scholar_flux.api import SearchCoordinator, SearchAPI, SearchAPIConfig, APIParameterConfig
from scholar_flux.data import RecursiveDataProcessor
from scholar_flux.api.models import ProcessedResponse
from scholar_flux.sessions import CachedSessionManager
from scholar_flux.data_storage import DataCacheManager
from pydantic import SecretStr
from requests_mock import Mocker
from requests import Session
from requests_cache import CachedSession
import pytest


def test_response_cache(mock_academic_json_response, redis_dependency, mongodb_dependency,sqlalchemy_dependency, sqlite_db_url):

    search_api_config=SearchAPIConfig(
        records_per_page = 3,
        request_delay=.01,
        base_url= 'https://test_url.com/search',
        api_key = SecretStr('this-is-a-test-key'),
        api_specific_parameters=dict(mailto=SecretStr('this.is.a@testemail.com'))
    )
    api = SearchAPI.from_settings(
        config = search_api_config,
        parameter_config = APIParameterConfig.from_defaults('crossref'),
        query="Computationaly Aided Analysis",
    )

    if not redis_dependency:
        pytest.skip()

    if not mongodb_dependency:
        pytest.skip()

    if not sqlalchemy_dependency:
        pytest.skip()

    redis_session=CachedSessionManager('redis_cache', backend='redis').configure_session()
    assert isinstance(redis_session, CachedSession)
    
    storage_cache=DataCacheManager.with_storage('redis')


    search_coordinator = SearchCoordinator( 
        api,
        session=redis_session,
        cache_manager=storage_cache,
        processor=RecursiveDataProcessor()
    )

    cache_key = search_coordinator._create_cache_key(page=1)
    search_coordinator.response_coordinator.cache_manager.delete(cache_key)
    prepared_request = api.prepare_request(api.base_url, parameters=api.build_parameters(page=1))

    with Mocker() as m:
        m.get(prepared_request.url, 
              status_code = mock_academic_json_response.status_code,
              json = mock_academic_json_response.json,
              headers={'Content-Type': 'application/json'}
             )
        assert not search_coordinator.response_coordinator.cache_manager.verify_cache(cache_key)
        processed_response=search_coordinator.search(page=1)
        assert search_coordinator.response_coordinator.cache_manager.verify_cache(cache_key)


        assert isinstance(processed_response, ProcessedResponse)
        response = processed_response.response
        assert response is not None and prepared_request.url == response.url

        assert not getattr(response, 'from_cache', False)
        cached_response=search_coordinator.search(page=1)
        assert getattr(response, 'from_cache', True)
        #assert search_coordinator.response_coordinator

        search_coordinator.response_coordinator.cache_manager.delete(cache_key)
        assert not search_coordinator.response_coordinator.cache_manager.verify_cache(cache_key)

        search_coordinator.response_coordinator.cache_manager = DataCacheManager.with_storage('null')
        response = processed_response=search_coordinator.search(page=1)
        cached_response = processed_response=search_coordinator.search(page=1)
        assert not getattr(response, 'from_cache', False)
        assert not getattr(cached_response, 'from_cache', False)
        assert not search_coordinator.response_coordinator.cache_manager.verify_cache(cache_key)

        search_coordinator.response_coordinator.cache_manager = DataCacheManager.with_storage('inmemory')
        assert not search_coordinator.response_coordinator.cache_manager.verify_cache(cache_key)
        response = processed_response=search_coordinator.search(page=1)
        assert search_coordinator.response_coordinator.cache_manager.verify_cache(cache_key)
        assert search_coordinator.response_coordinator.cache_manager.retrieve(cache_key)
        search_coordinator.response_coordinator.cache_manager.delete(cache_key)
        assert not search_coordinator.response_coordinator.cache_manager.verify_cache(cache_key)
        
        search_coordinator.response_coordinator.cache_manager = DataCacheManager.with_storage('sql',url=sqlite_db_url)
        search_coordinator._delete_cached_response(page=1)
        assert not search_coordinator.response_coordinator.cache_manager.verify_cache(cache_key)
        processed_response = processed_response=search_coordinator.search(page=1)
        assert search_coordinator.response_coordinator.cache_manager.verify_cache(cache_key)
        retrieved_cache=search_coordinator.response_coordinator.cache_manager.retrieve(cache_key)
        retrieved_data=search_coordinator.search_data(page=1)
        assert retrieved_cache is not None and retrieved_cache['processed_response'] == retrieved_data
        # assert retrieved_page
        search_coordinator._delete_cached_response(page=1)
        # assert not search_coordinator.cache_is_valid(cache_key, response.response)
        # assert not search_coordinator.response_coordinator.cache_manager.verify_cache(cache_key)



       
#        response = processed_response.response
#        assert not getattr(response, 'from_cache', False)
