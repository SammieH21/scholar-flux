import pytest
import requests_mock


from scholar_flux.api import SearchAPI, SearchCoordinator
from scholar_flux.api.models import ProcessedResponse, ErrorResponse

from scholar_flux.exceptions import InvalidCoordinatorParameterException, RequestFailedException


@pytest.mark.parametrize(
    "param_overrides",
    [
        {"query": None},
        {"parser": "Incorrect Field"},
        {"extractor": "Incorrect Field"},
        {"processor": "Incorrect Field"},
        {"cache_manager": "Incorrect Field"},
    ],
)
def test_incorrect_config(param_overrides):
    params = {"query": "Computer Science Testing"} | param_overrides
    with pytest.raises(InvalidCoordinatorParameterException):
        coordinator = SearchCoordinator(**params)
        print(coordinator.__dict__)


def test_request_failed_exception(monkeypatch, caplog):
    coordinator = SearchCoordinator(query="Computer Science Testing")
    monkeypatch.setattr(
        coordinator, "robust_request", lambda *a, **kw: (_ for _ in ()).throw(RequestFailedException("fail"))
    )
    res = coordinator.search(page=3)
    assert res is None
    assert "Failed to fetch page 3" in caplog.text


def test_basic_coordinator_search(default_memory_cache_session, academic_json_response, caplog):
    """
    Test for whether the defaults are specified correctly and whether the mocked response is processed
    as intended throughout the coordinator
    """

    api = SearchAPI.from_defaults(
        provider_name="plos",
        query="test",
        base_url="https://api.example.com",
        records_per_page=10,
        session=default_memory_cache_session,
        request_delay=0,
    )
    coordinator = SearchCoordinator(api)

    params = api.build_parameters(page=1)
    prepared_request = api.prepare_request(api.base_url, parameters=params)

    #   with patch.object(coordinator.api.session, 'send', return_value=academic_json_response):
    #       result = coordinator.search(page = 1, from_request_cache= False, from_process_cache=False)
    #       assert isinstance(result, ProcessedResponse)
    #       assert result.data and len(result.data) == 3

    assert coordinator.get_cached_request(page=1) is None
    assert coordinator.get_cached_response(page=1) is None

    with requests_mock.Mocker() as m:
        m.get(
            prepared_request.url,
            status_code=200,
            content=academic_json_response.content,
            headers={"Content-Type": "application/json"},
        )
        result = coordinator.search(page=1, from_request_cache=False, from_process_cache=False)
        assert isinstance(result, ProcessedResponse)
        assert result.data and len(result.data) == 3

    assert coordinator.get_cached_request(page=1) is not None
    assert coordinator.get_cached_response(page=1) is not None

    with requests_mock.Mocker() as m:
        m.get(prepared_request.url, status_code=429, headers={"Content-Type": "application/json"})
        result = coordinator.search(page=1, from_request_cache=True, from_process_cache=False)
        assert isinstance(result, ProcessedResponse)

    with requests_mock.Mocker() as m:
        m.get(prepared_request.url, status_code=429, headers={"Content-Type": "application/json"})
        result = coordinator.search(page=1, from_request_cache=False, from_process_cache=False)
        assert isinstance(result, ErrorResponse)
