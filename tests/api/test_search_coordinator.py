import pytest
from unittest.mock import MagicMock
import re
import requests_mock

from requests_cache import CachedResponse
from scholar_flux.api import SearchAPI, SearchCoordinator
from scholar_flux.api.workflows import BaseWorkflow, BaseWorkflowStep, SearchWorkflow, WorkflowStep
from scholar_flux.api.models import ProcessedResponse, ErrorResponse

from scholar_flux.exceptions import InvalidCoordinatorParameterException, RequestFailedException

from scholar_flux.exceptions import (
    RequestCacheException,
    StorageCacheException,
)


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
        _ = SearchCoordinator(api="")  # type: ignore

    with pytest.raises(InvalidCoordinatorParameterException):
        _ = SearchCoordinator(api=1)  # type: ignore
        assert "Could not initialize the SearchCoordinator due to an issue creating the SearchAPI." in caplog.text

    with pytest.raises(InvalidCoordinatorParameterException):
        _ = SearchCoordinator(query="")

    with pytest.raises(InvalidCoordinatorParameterException) as excinfo:
        _ = SearchCoordinator(query="a valid query", api_key="*" * 513)
        assert "Could not initialize the SearchCoordinator due to an issue creating the SearchAPI." in str(
            excinfo.value
        )

    with pytest.raises(InvalidCoordinatorParameterException):
        _ = SearchCoordinator(query="valid_query", response_coordinator="invalid response coordinator")  # type: ignore
        assert "Could not initialize the SearchCoordinator due to an issue creating the SearchAPI." in caplog.text


def test_build():
    search_coordinator = SearchCoordinator(query="test_query")
    new_search_coordinator = SearchCoordinator.as_coordinator(
        search_coordinator.api, search_coordinator.response_coordinator
    )
    assert repr(new_search_coordinator) == repr(search_coordinator)


def test_worfklow_called():
    api = SearchAPI.from_defaults(
        provider_name="plos",
        query="test",
        base_url="https://api.example.com",
        records_per_page=10,
        request_delay=0,
    )
    search_coordinator = SearchCoordinator(api)

    workflow = MagicMock()
    workflow._run.return_value = False

    search_coordinator.workflow = workflow

    search = MagicMock()
    search.return_value = True
    search_coordinator._search = search  # type: ignore

    nonworkflow = search_coordinator.search(page=1, use_workflow=False)
    assert not workflow.called and search.called and nonworkflow is True

    nonworkflow = search_coordinator.search(page=1, use_workflow=True)
    assert workflow.called and isinstance(nonworkflow, MagicMock)


def test_search_exception(monkeypatch, caplog):
    search_coordinator = SearchCoordinator(query="test_query", base_url="https://thisisatesturl.com")

    monkeypatch.setattr(
        search_coordinator,
        "_search",
        lambda *args, **kwargs: (_ for _ in ()).throw(Exception("Directly raised exception")),
    )

    response = search_coordinator.search(page=1)
    assert response is None
    assert "An unexpected error occurred when processing the response: Directly raised exception" in caplog.text

    caplog.clear()

    response_list = search_coordinator.search_pages(pages=[1, 2, 3])
    assert len(response_list) == 1 and response_list[0].response_result is None
    assert "An unexpected error occurred when processing the response: Directly raised exception" in caplog.text

    caplog.clear()

    monkeypatch.setattr(
        search_coordinator,
        "search",
        lambda *args, **kwargs: (_ for _ in ()).throw(Exception("Directly raised search exception")),
    )

    response_data = search_coordinator.search_data(page=1)
    assert response_data is None
    assert re.search(
        "An unexpected error occurred when attempting to retrieve the processed response data:.*Directly raised search exception",
        caplog.text,
    )


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
    basic_workflow = SearchWorkflow(steps=[basic_workflow_step])
    api = SearchAPI.from_defaults(
        provider_name="plos",
        query="history",
        base_url="https://api.example.com",
        records_per_page=10,
        request_delay=0,
        workflow=basic_workflow,
    )

    search_coordinator = SearchCoordinator(api)
    monkeypatch.setattr(
        search_coordinator,
        "_search",
        lambda *args, **kwargs: (_ for _ in ()).throw(Exception("Directly raised exception")),
    )

    with pytest.raises(RuntimeError):
        basic_workflow(search_coordinator, page=1)

    test_value = 1
    with pytest.raises(TypeError):
        basic_workflow.steps[0].pre_transform(test_value)  # type: ignore
    with pytest.raises(TypeError):
        basic_workflow.steps[0].post_transform(test_value)  # type: ignore
    assert (
        f"Expected the `ctx` of the current workflow to be a StepContext. " f"Received: {type(test_value).__name__}"
    ) in caplog.text


def test_initialization_updates():
    api = SearchAPI.from_defaults(provider_name="crossref", query="testing_query")
    search_coordinator = SearchCoordinator(api, query="new_query", request_delay=api.request_delay + 5)
    assert (
        api.query != search_coordinator.api.query
        and api.provider_name == search_coordinator.api.provider_name
        and search_coordinator.api.request_delay == api.request_delay + 5
    )
    assert SearchCoordinator(api, query="")  # should initialize since a query is available through the SearchAPI


def test_request_failed_exception(monkeypatch, caplog):
    coordinator = SearchCoordinator(query="Computer Science Testing", request_delay=0)
    monkeypatch.setattr(
        coordinator, "robust_request", lambda *a, **kw: (_ for _ in ()).throw(RequestFailedException("fail"))
    )
    res = coordinator.search(page=3)
    assert res is None
    assert "Failed to fetch page 3" in caplog.text


def test_cache_retrieval_failure(monkeypatch, default_memory_cache_session, caplog):
    # default_memory_cache_session.cache.clear()
    search_coordinator = SearchCoordinator(
        query="new query", session=default_memory_cache_session, base_url="https://non-existent-http-url.com"
    )
    assert search_coordinator.api.cache

    monkeypatch.setattr(
        search_coordinator.search_api.cache,
        "create_key",
        lambda *args, **kwargs: (_ for _ in ()).throw(AttributeError("Directly raised exception")),
    )

    monkeypatch.setattr(
        search_coordinator.response_coordinator.cache_manager,
        "retrieve",
        lambda *args, **kwargs: (_ for _ in ()).throw(StorageCacheException("Directly raised exception")),
    )

    assert search_coordinator.get_cached_request(page=1) is None
    assert "Error retrieving requests-cache key" in caplog.text
    assert "Error retrieving cached request: Error retrieving requests-cache key" in caplog.text
    assert search_coordinator.get_cached_response(page=1) is None
    assert "Error retrieving cached response: Directly raised exception" in caplog.text

    monkeypatch.setattr(search_coordinator, "_get_request_key", lambda *args, **kwargs: None)

    assert search_coordinator.get_cached_request(page=1) is None


def test_no_result_caching(caplog):
    search_coordinator = SearchCoordinator(query="comp sci", cache_requests=False, cache_results=False)
    # should be a falsey NullCacheManager
    assert search_coordinator.response_coordinator.cache_manager is not None
    assert not search_coordinator.response_coordinator.cache_manager
    # shouldn't return any value
    caplog.clear()
    # operates as if the cache were never initialized to begin with and was None
    assert search_coordinator.get_cached_response(page=1) is None
    assert search_coordinator.get_cached_request(page=1) is None
    assert search_coordinator._get_request_key(page=1) is None
    assert not caplog.text


def test_cache_deletions(monkeypatch, caplog):
    search_coordinator = SearchCoordinator(query="Computer Science Testing", cache_requests=True, request_delay=0)
    # search_coordinator = SearchCoordinator(query = 'hi', cache_requests = True)
    search_coordinator._delete_cached_request(page=4)  # type: ignore
    assert re.search(
        "A cached response for the current request does not exist: 'Key [a-zA-z0-9]+ not found", caplog.text
    )

    monkeypatch.setattr(search_coordinator, "_get_request_key", lambda *args, **kwargs: None)

    search_coordinator._delete_cached_request(page=1)  # type: ignore
    assert "A cached response for the current request does not exist: 'Request key is None or empty'" in caplog.text
    monkeypatch.setattr(
        search_coordinator,
        "_get_request_key",
        lambda *args, **kwargs: (_ for _ in ()).throw(RequestCacheException("Directly raised exception")),
    )
    search_coordinator._delete_cached_request(page=1)  # type: ignore
    assert "Error deleting cached request: Directly raised exception" in caplog.text

    monkeypatch.setattr(
        search_coordinator,
        "_create_cache_key",
        lambda *args, **kwargs: (_ for _ in ()).throw(StorageCacheException("Directly raised exception")),
    )

    search_coordinator._delete_cached_response(page=1)  # type: ignore
    assert "Error in deleting from processing cache: Directly raised exception" in caplog.text


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
    coordinator.retry_handler.max_retries = 0
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

    caplog.clear()
    with requests_mock.Mocker() as m:
        m.get(prepared_request.url, status_code=429, headers={"Content-Type": "application/json"})
        result = coordinator.search(page=1, from_request_cache=True, from_process_cache=False)
        assert isinstance(result, ProcessedResponse)

        response = coordinator.robust_request(page=1)
        assert result and isinstance(response, CachedResponse)
        assert f"Retrieved cached response for query: {coordinator.search_api.query} and page: 1" in caplog.text
        assert response == coordinator.get_cached_request(page=1)

    caplog.clear()
    with requests_mock.Mocker() as m:
        m.get(prepared_request.url, status_code=429, headers={"Content-Type": "application/json"})
        result = coordinator.search(page=1, from_request_cache=False, from_process_cache=False)
        assert isinstance(result, ErrorResponse)

        coordinator.retry_handler.raise_on_error = True
        with pytest.raises(RequestFailedException):
            _ = coordinator.robust_request(page=1)
        assert f"Failed to get a valid response from the {coordinator.search_api.provider_name} API"
