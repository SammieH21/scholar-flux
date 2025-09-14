import pytest
from unittest.mock import patch, MagicMock
import requests_mock
from collections import namedtuple

from scholar_flux.utils import generate_repr
from scholar_flux.api import SearchAPI, SearchCoordinator
from scholar_flux.api.workflows import BaseWorkflow, BaseWorkflowStep, SearchWorkflow, WorkflowStep
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
def test_incorrect_config(param_overrides, caplog):
    params = {"query": "Computer Science Testing"} | param_overrides
    with pytest.raises(InvalidCoordinatorParameterException):
        coordinator = SearchCoordinator(**params)
        print(coordinator.__dict__)

    with pytest.raises(InvalidCoordinatorParameterException):
        _ = SearchCoordinator(api = '') # type: ignore

    with pytest.raises(InvalidCoordinatorParameterException):
        _ = SearchCoordinator(api = 1) # type: ignore
        assert "Could not initialize the SearchCoordinator due to an issue creating the SearchAPI." in caplog.text

    with pytest.raises(InvalidCoordinatorParameterException):
        _ = SearchCoordinator(query = '')

    with pytest.raises(InvalidCoordinatorParameterException):
        _ = SearchCoordinator(query = 'valid_query', response_coordinator = 'invalid response coordinator') # type: ignore
        assert "Could not initialize the SearchCoordinator due to an issue creating the SearchAPI." in caplog.text

def test_build():
    search_coordinator = SearchCoordinator(query = 'test_query')
    new_search_coordinator = SearchCoordinator.as_coordinator(search_coordinator.api,
                                                              search_coordinator.response_coordinator)
    assert repr(new_search_coordinator) == repr(search_coordinator)

def test_worfklow_called(monkeypatch):
    api = SearchAPI.from_defaults(
        provider_name="plos",
        query="test",
        base_url="https://api.example.com",
        records_per_page=10,
        request_delay=0,
    )
    search_coordinator =  SearchCoordinator(api)

    workflow_result = namedtuple('workflow_result', 'result')
    workflow = MagicMock()
    workflow._run.return_value = False

    search_coordinator.workflow = workflow

    search = MagicMock()
    search.return_value = True
    search_coordinator._search = search

    nonworkflow = search_coordinator.search(page = 1, use_workflow = False)
    assert not workflow.called and search.called and nonworkflow is True

    nonworkflow = search_coordinator.search(page = 1, use_workflow = True)
    assert workflow.called and isinstance(nonworkflow , MagicMock)

def test_workflow_components():
    workflow_step = BaseWorkflowStep()
    assert workflow_step.__dict__ == workflow_step.pre_transform(None).__dict__

    ctx = True
    workflow_step = BaseWorkflowStep()
    assert workflow_step.post_transform(ctx) == ctx
    
    with pytest.raises(NotImplementedError):
        basic_workflow = BaseWorkflow()
        basic_workflow()


def test_with_worfklow_error(monkeypatch, caplog):
    basic_workflow_step = WorkflowStep()
    basic_workflow = SearchWorkflow(steps = [basic_workflow_step])
    api = SearchAPI.from_defaults(
        provider_name="plos",
        query="history",
        base_url="https://api.example.com",
        records_per_page=10,
        request_delay=0,
        workflow = basic_workflow
    )

    search_coordinator =  SearchCoordinator(api)
    monkeypatch.setattr(
        search_coordinator,
       '_search',
        lambda *args, **kwargs: (_ for _ in ()).throw(Exception(f"Directly raised exception"))
    )

    with pytest.raises(RuntimeError):
        basic_workflow(search_coordinator, page=1)

    test_value = 1
    with pytest.raises(TypeError):
        basic_workflow.steps[0].pre_transform(test_value) # type: ignore
    with pytest.raises(TypeError):
        basic_workflow.steps[0].post_transform(test_value) # type: ignore
    assert (f"Expected the `ctx` of the current workflow to be a StepContext. "
            f"Received: {type(test_value).__name__}") in caplog.text   

def test_initialization_updates():
    api = SearchAPI.from_defaults(provider_name = 'crossref', query = 'testing_query')
    search_coordinator = SearchCoordinator(api, query = 'new_query',
                                           request_delay = api.request_delay + 5)
    assert (api.query != search_coordinator.api.query and
            api.provider_name == search_coordinator.api.provider_name and
            search_coordinator.api.request_delay == api.request_delay + 5)
    assert SearchCoordinator(api, query = '') # should initialize since a query is available through the SearchAPI


def test_request_failed_exception(monkeypatch, caplog):
    coordinator = SearchCoordinator(query="Computer Science Testing", request_delay = 0)
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
