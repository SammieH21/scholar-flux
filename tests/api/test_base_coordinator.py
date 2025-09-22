import pytest
import requests_mock

from scholar_flux.sessions import CachedSessionManager
from scholar_flux.api import SearchAPI, BaseCoordinator, ResponseCoordinator
from scholar_flux.api.models import ProcessedResponse, ErrorResponse
from scholar_flux.exceptions import InvalidCoordinatorParameterException, RequestFailedException
from scholar_flux.data import BaseDataParser, DataExtractor, PassThroughDataProcessor, PathDataProcessor


def test_init(caplog):
    api = SearchAPI(query="biology")
    response_coordinator = ResponseCoordinator.build()

    with pytest.raises(InvalidCoordinatorParameterException):
        _ = BaseCoordinator(search_api=api, response_coordinator=1)  # type: ignore

    with pytest.raises(InvalidCoordinatorParameterException):
        _ = BaseCoordinator(search_api=1, response_coordinator=response_coordinator)  # type: ignore
        assert "Could not initialize the BaseCoordinator due to an issue creating the SearchAPI." in caplog.text


def test_build():
    api = SearchAPI(query="biology")
    response_coordinator = ResponseCoordinator.build()

    base_search_coordinator = BaseCoordinator.as_coordinator(api, response_coordinator)
    new_base_coordinator = BaseCoordinator(api, response_coordinator)
    assert repr(new_base_coordinator) == repr(base_search_coordinator)


def test_override_build():
    api = SearchAPI(query="biology")
    response_coordinator = ResponseCoordinator.build()
    base_search_coordinator = BaseCoordinator.as_coordinator(api, response_coordinator)
    base_parser = BaseDataParser()
    extractor = DataExtractor()
    processor = PassThroughDataProcessor()
    path_processor = PathDataProcessor()

    new_response_coordinator = ResponseCoordinator.update(response_coordinator, base_parser, extractor, path_processor)
    new_api = SearchAPI.update(api, query="history", use_cache=True)

    assert repr(new_api) != repr(api)
    assert repr(response_coordinator) != repr(new_response_coordinator)

    base_search_coordinator.parser = base_parser
    base_search_coordinator.data_extractor = extractor
    base_search_coordinator.processor = processor
    base_search_coordinator.search_api = new_api
    base_search_coordinator.search_api = new_api

    assert base_search_coordinator.parser == base_parser
    assert base_search_coordinator.data_extractor == extractor
    assert base_search_coordinator.processor == processor
    assert base_search_coordinator.search_api == base_search_coordinator.api == new_api

    base_search_coordinator.response_coordinator = new_response_coordinator
    assert base_search_coordinator.responses == base_search_coordinator.response_coordinator == new_response_coordinator
    assert base_search_coordinator.processor != processor
    base_search_coordinator.responses = response_coordinator
    assert base_search_coordinator.response_coordinator == base_search_coordinator.responses == response_coordinator
    # at this point, the processor changed since the base search coordinator properties point to the new_response_coordinator

    assert base_search_coordinator.processor == processor

    with pytest.raises(InvalidCoordinatorParameterException):
        base_search_coordinator.response_coordinator.cache_manager = 1  # type:ignore

    with pytest.raises(InvalidCoordinatorParameterException):
        base_search_coordinator.parser = 1  # type:ignore

    with pytest.raises(InvalidCoordinatorParameterException):
        base_search_coordinator.data_extractor = 1  # type:ignore

    with pytest.raises(InvalidCoordinatorParameterException):
        base_search_coordinator.processor = 1  # type:ignore

    with pytest.raises(InvalidCoordinatorParameterException):
        base_search_coordinator.processor = 1  # type:ignore

    with pytest.raises(InvalidCoordinatorParameterException):
        base_search_coordinator.api = 1  # type:ignore

    with pytest.raises(InvalidCoordinatorParameterException):
        base_search_coordinator.search_api = 1  # type:ignore

    with pytest.raises(InvalidCoordinatorParameterException):
        base_search_coordinator.responses = 1  # type:ignore

    with pytest.raises(InvalidCoordinatorParameterException):
        base_search_coordinator.response_coordinator = 1  # type:ignore


def test_initialization_updates():
    api = SearchAPI(query="biology")
    response_coordinator = ResponseCoordinator.build(cache_results=True)
    base_search_coordinator = BaseCoordinator.as_coordinator(api, response_coordinator)

    new_api = SearchAPI.update(api, query="comp sci")
    new_response_coordinator = ResponseCoordinator.update(response_coordinator, cache_results=False)

    base_search_coordinator._initialize(new_api, new_response_coordinator)

    assert base_search_coordinator.api.query == "comp sci" == new_api.query
    assert api.query != new_api.query

    assert not response_coordinator.cache_manager.isnull()
    assert base_search_coordinator.response_coordinator.cache_manager.isnull()


def test_request_failed_exception(monkeypatch, caplog):
    api = SearchAPI(query="biology")
    response_coordinator = ResponseCoordinator.build()

    coordinator = BaseCoordinator(api, response_coordinator)
    monkeypatch.setattr(
        coordinator.api, "search", lambda *a, **kw: (_ for _ in ()).throw(RequestFailedException("fail"))
    )
    res = coordinator.search(page=2)
    assert f"Failed to get a valid response from the {api.provider_name} API: fail" in caplog.text
    assert res is None


def test_basic_coordinator_search(default_memory_cache_session, academic_json_response, caplog):
    """
    Test for whether the defaults are specified correctly and whether the mocked response is processed
    as intended throughout the coordinator
    """

    session_manager = CachedSessionManager(user_agent="test-user", backend="memory")
    api = SearchAPI.from_defaults(
        provider_name="plos",
        query="basic coordination",
        base_url="https://api.example.com",
        records_per_page=10,
        session=session_manager(),
        request_delay=0,
    )

    assert api.cache is not None
    response_coordinator = ResponseCoordinator.build(cache_results=True)
    coordinator = BaseCoordinator(api, response_coordinator)

    params = api.build_parameters(page=1)
    prepared_request = api.prepare_request(api.base_url, parameters=params)
    assert prepared_request.url is not None

    with requests_mock.Mocker() as m:
        m.get(
            prepared_request.url,
            status_code=200,
            content=academic_json_response.content,
            headers={"Content-Type": "application/json"},
        )

        result = coordinator.search(page=1, cache_key="test-cache-key")
        assert result and result.data  # and len(result.data) == 3

    with requests_mock.Mocker() as m:
        m.get(prepared_request.url, status_code=429, headers={"Content-Type": "application/json"})
        result = coordinator.search(page=1, cache_key="test-cache-key")
        assert isinstance(result, ProcessedResponse)

        request_key = api.cache.create_key(prepared_request)
        api.cache.delete(request_key)

        result = coordinator.search(page=1, cache_key="test-cache-key")
        assert isinstance(result, ErrorResponse)
