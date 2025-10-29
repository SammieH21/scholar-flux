import pytest
from unittest.mock import MagicMock
import re
import requests_mock

from requests import Response
from requests_cache import CachedResponse
from scholar_flux.api import SearchAPI, BaseCoordinator, SearchCoordinator, ResponseCoordinator
from scholar_flux.api.workflows import BaseWorkflow, BaseWorkflowStep, SearchWorkflow, WorkflowStep
from scholar_flux.api.rate_limiting import threaded_rate_limiter_registry
from scholar_flux.api.models import ProcessedResponse, ErrorResponse, NonResponse

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
    """Verifies that the SearchCoordinator correctly raises an error on encountering an invalid value when setting an
    attribute.

    This test parametrizes several individual fields to determine whether whether values for each field raise an
    InvalidCoordinatorParameterException.

    """
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


def test_blank_create_api():
    """Validates whether an attempt to create a Search API without any arguments correctly raises a
    QueryValidationError."""
    with pytest.raises(InvalidCoordinatorParameterException) as excinfo:
        _ = SearchCoordinator._create_search_api()
    assert "Either 'query' or 'search_api' must be provided." in str(excinfo.value)


def test_build():
    """First attempts to build a new search coordinator from the previously created components as well as defaults to
    determine whether the structure of the coordinator is exactly the same as before.

    The string representation of the coordinator will include a basic overview on the structure of the coordinator which
    should use the same api and response_coordinator while using the same defaults.

    """
    search_coordinator = SearchCoordinator(query="test_query")
    new_search_coordinator = SearchCoordinator.as_coordinator(
        search_coordinator.api, search_coordinator.response_coordinator
    )
    assert repr(new_search_coordinator) == repr(search_coordinator)


def test_workflow_called():
    """Validates whether the workflow for the search coordinator, when included, is correctly called when running
    `SearchCoordinator.search` if `use_workflow` is set to True.

    Otherwise, a workflow should not be used when `use_workflow` is set to False.

    """

    api = SearchAPI.from_defaults(
        provider_name="plos",
        query="test",
        base_url="https://api.example.com",
        records_per_page=10,
        request_delay=0,
    )
    search_coordinator = SearchCoordinator(api)

    workflow = MagicMock()
    workflow._run.return_value = True

    search_coordinator.workflow = workflow

    search = MagicMock()
    search.return_value = False
    search_coordinator._search = search  # type: ignore

    uses_workflow = search_coordinator.search(page=1, use_workflow=False)
    assert not workflow.called and search.called and uses_workflow is False

    uses_workflow = search_coordinator.search(page=1, use_workflow=True)
    assert workflow.called and isinstance(uses_workflow, MagicMock)


def test_search_exception(monkeypatch, caplog):
    """Tests to verify that `search` correctly returns `None` when an unexpected error occurs during retrieval.

    The `_search` private method is patched to raise an Exception to be handled within the `search` method.

    """
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
    """Validates the preset configuration for a BaseWorkflowStep that, by default, should not be modified when
    `pre_transform` is called with `None`. Also validates that the context of the workflow step is returned as is by
    default.

    These basic configurations are used to provide the blueprint for flexible modification of workflow steps before and
    after the execution of a workflow step while not providing additional functionality by default.

    """
    workflow_step = BaseWorkflowStep()
    assert workflow_step.__dict__ == workflow_step.pre_transform(None).__dict__

    ctx = True
    workflow_step = BaseWorkflowStep()
    assert workflow_step.post_transform(ctx) == ctx

    with pytest.raises(NotImplementedError):
        basic_workflow = BaseWorkflow()
        basic_workflow()

    basic_workflow_step = BaseWorkflowStep()
    with pytest.raises(NotImplementedError):
        basic_workflow_step()

    # a simple context manager that has no side effects and only yields itself for the duration of the context
    with basic_workflow_step.with_context() as context_step:
        assert basic_workflow_step is context_step


def test_with_workflow_error(monkeypatch, caplog):
    """Validates whether errors in a workflow are successfully caught when attempting to retrieve and process a response
    using a `SearchWorkflow`"""
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
    """Verifies that the input parameters successfully initialize a new SearchCoordinator as intended while ensuring
    that unspecified defaults are automatically created."""
    # create a new SearchCoordinator specifying only an API and a query override
    api = SearchAPI.from_defaults(provider_name="crossref", query="testing_query")
    search_coordinator = SearchCoordinator(api, query="new_query", request_delay=api.request_delay + 5)

    # the API should override the previous request_delay and use the new query only
    assert (
        api.query != search_coordinator.api.query
        and api.provider_name == search_coordinator.api.provider_name
        and search_coordinator.api.request_delay == api.request_delay + 5
    )
    # Queries usually need to be specified. The query already exists in the SearchAPI, so `query=""` is ignored.
    assert SearchCoordinator(api, query="")  # should initialize since a query is available through the SearchAPI

    # retrieves the rate limiter for the current provider
    rate_limiter = threaded_rate_limiter_registry.get(api.provider_name)
    assert rate_limiter is not None
    # modifies the interval for the global threaded rate limiter of the current provider
    rate_limiter.min_interval = 30

    # when initializing a new search api using the underlying private method,
    # this should produce essentially the same result as the basic SearchCoordinator initialization
    new_api = SearchCoordinator._create_search_api(api, query="new_query", request_delay=api.request_delay + 5)

    # as a template rather than modify it inplace altogether
    assert api is not new_api
    assert new_api._rate_limiter != api._rate_limiter

    # reinitializes the original API object in comparison with a new query, config, and rate limiter
    api._initialize(api.query, config=api.config, parameter_config=api.parameter_config, rate_limiter=rate_limiter)
    # ensure that the rate limiter is overridden as intended and the newly created search APIs use a previous SearchAPI
    assert api._rate_limiter is rate_limiter and api.config.request_delay == rate_limiter.min_interval == 30

    # the SearchCoordinator should also use the same rate limiter from the current API
    search_coordinator2 = SearchCoordinator.as_coordinator(new_api, search_coordinator.responses)

    # The structure of the first SearchCoordinator should exactly equal that of the second
    assert repr(search_coordinator) == repr(search_coordinator2)


def test_request_failed_exception(monkeypatch, caplog):
    """Verifies that, when a request fails to generate a response and, instead, throws an error, the error is logged and
    the response result is `None`."""
    coordinator = SearchCoordinator(query="Computer Science Testing", request_delay=0)
    monkeypatch.setattr(
        coordinator, "robust_request", lambda *a, **kw: (_ for _ in ()).throw(RequestFailedException("fail"))
    )
    res = coordinator.search(page=3)
    assert isinstance(res, NonResponse)
    assert "Failed to fetch page 3" in caplog.text
    assert res.message and "fail" in res.message
    assert res.error and res.error in "RequestFailedException" in res.error
    assert "NonResponse(error=RequestFailedException, message='Failed to fetch page 3: fail')" in repr(res)


def test_none_type_fetch(monkeypatch, caplog):
    """Tests to verify that a NonResponse is returned when a retry_handler receives None in the request retrieval
    step."""
    search_coordinator = SearchCoordinator(
        query="new query", base_url="https://example-example-example-url.com", request_delay=0
    )
    search_coordinator.retry_handler.max_backoff = 0

    monkeypatch.setattr(
        search_coordinator.api,
        "search",
        lambda *args, **kwargs: None,
    )

    with pytest.raises(RequestFailedException) as excinfo:
        _ = search_coordinator.robust_request(page=1)
        assert ("Expected to receive a valid response or response-like object, " f"Received type: {type(None)}") in str(
            excinfo.value
        )

    response = search_coordinator._fetch_api_response(page=1)
    assert isinstance(response, NonResponse)
    assert "NonResponse" in repr(response)


def test_cache_retrieval_failure(monkeypatch, default_memory_cache_session, caplog):
    """Test for validating exception handling when errors occur in the retrieval of cached responses.

    The function first validates that the `default_memory_cache_session` session object is cached as intended.
    Afterward, the `create_key` function of the API cache is patched to raise an error, which is then logged
    while a None value is returned.

    In context, this would later prompt the  SearchCoordinator to retrieve the result from the API when `search`
    is called and cache retrieval fails.

    """
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
    """Validates that, when request caching and response processing is off, each associated method should return
    None."""
    search_coordinator = SearchCoordinator(query="comp sci", cache_requests=False, cache_results=False)
    # should be a falsy NullCacheManager
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
    """Tests to validate whether cached request/response deletions for non-existent keys will return None by default and
    logs missing keys."""
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


@pytest.mark.parametrize("page", [(0), (1), (2)])
def test_parameter_building(page, zero_indexed_parameter_config, default_correct_zero_index_config):
    """Integration test to determine whether parameters are built correctly to always start at page 1.

    With APIParameterConfig.DEFAULT_CORRECT_ZERO_INDEX = True, the first page should always be page 1,
    despite whether an API is zero indexed or not. The building and preparation of parameter values happens
    prior to the preparation of the URL string and before the request is sent.

    """

    RECORDS_PER_PAGE = 10
    api = SearchAPI(
        query="new query", parameter_config=zero_indexed_parameter_config, records_per_page=RECORDS_PER_PAGE
    )
    search_coordinator = SearchCoordinator(api)

    adjusted_page = page + 1
    parameters = search_coordinator.api.build_parameters(page=adjusted_page)

    assert parameters["q"] == "new query"
    assert parameters["start"] == page * RECORDS_PER_PAGE
    assert parameters["pagesize"] == RECORDS_PER_PAGE


@pytest.mark.parametrize("page", [(0), (1), (2)])
def test_parameter_building_with_zero_indexing(page, zero_indexed_parameter_config, default_zero_indexed_config):
    """Integration test to determine whether the page start varies based on zero indexed pagination.

    With APIParameterConfig.DEFAULT_CORRECT_ZERO_INDEX = False, the first page for zero indexed APIs will be 0, and
    1 for non-zero indexed APIs. The building and preparation of parameter values happens
    prior to the preparation of the URL string and before the request is sent.

    """

    RECORDS_PER_PAGE = 10
    api = SearchAPI(
        query="new query", parameter_config=zero_indexed_parameter_config, records_per_page=RECORDS_PER_PAGE
    )
    search_coordinator = SearchCoordinator(api)

    parameters = search_coordinator.api.build_parameters(page=page)

    assert parameters["q"] == "new query"
    assert parameters["start"] == page * RECORDS_PER_PAGE
    assert parameters["pagesize"] == RECORDS_PER_PAGE


def test_basic_fetch():
    """Tests the basic searching feature of the SearchCoordinator to determine its behavior when fetching from APIs."""
    api = SearchAPI.from_defaults(
        provider_name="plos",
        query="test",
        base_url="https://api.example.com",
    )
    coordinator = SearchCoordinator(api, request_delay=0)
    coordinator.retry_handler.max_backoff = 0
    prepared_request = api.prepare_search(page=1)

    with requests_mock.Mocker() as m:
        m.get(
            prepared_request.url,
            status_code=200,
            content=b'{"test": "success"}',
            headers={"Content-Type": "application/json"},
        )
        result = coordinator.fetch(page=1)
        assert isinstance(result, Response) and result.status_code == 200

        m.get(
            prepared_request.url,
            status_code=429,
            content=b'{"test": "failure"}',
            headers={"Content-Type": "application/json"},
        )
        result = coordinator.fetch(page=1)
        assert isinstance(result, Response) and result.status_code == 429

    # returns None because Mocker doesn't allow non-registered URLs
    with requests_mock.Mocker() as m:
        result = coordinator.fetch(page=1)
        assert result is None


def test_basic_coordinator_search(default_memory_cache_session, academic_json_response, caplog):
    """Test for whether the defaults are specified correctly and whether the mocked response is processed as intended
    throughout the coordinator."""

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
    prepared_request = api.prepare_search(page=1)

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

    with requests_mock.Mocker() as m:
        non_response = coordinator.search(page=1)
        assert isinstance(non_response, NonResponse)


@pytest.mark.parametrize("Coordinator", (BaseCoordinator, SearchCoordinator))
def test_base_coordinator_summary(Coordinator):
    """Validates whether the coordinator shows the correct representation of the structure when using the summary
    method.

    The summaries for the BaseCoordinator and SearchCoordinator are checked and tested using `parametrize` in pytest.

    """
    api = SearchAPI.from_defaults(query="light", provider_name="CROSSREF")
    response_coordinator = ResponseCoordinator.build()

    coordinator = Coordinator(api, response_coordinator)
    representation = coordinator.summary()

    class_name = Coordinator.__name__
    assert re.search(rf"^{class_name}\(.*\)$", representation, re.DOTALL)
    assert re.search(r"SearchAPI\(.*\)", representation, re.DOTALL)
    assert f"query='{api.query}'" in representation
    assert f"provider_name='{api.provider_name}'" in representation
    assert f"base_url='{api.base_url}'" in representation  # ignore padding
    assert f"records_per_page={api.records_per_page}" in representation  # ignore padding
    assert re.search(f"session=.*{api.session.__class__.__name__}", representation)
    assert f"timeout={api.timeout}" in representation

    assert re.search(r"ResponseCoordinator\(.*\)", representation, re.DOTALL)
    assert f"parser={response_coordinator.parser.__class__.__name__}(...)" in representation
    assert f"extractor={response_coordinator.extractor.__class__.__name__}(...)" in representation
    assert (
        f"cache_manager={response_coordinator.cache_manager.__class__.__name__}(cache_storage={response_coordinator.cache_manager.cache_storage.__class__.__name__}(...))"
        in representation
    )  # ignore padding
