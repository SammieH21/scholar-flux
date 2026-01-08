import pytest
from unittest.mock import MagicMock
import re
import requests_mock

from requests import Response
from requests_cache import CachedResponse
from scholar_flux.api import SearchAPI, BaseCoordinator, SearchCoordinator, ResponseCoordinator
import datetime
from scholar_flux.api.workflows import BaseWorkflow, BaseWorkflowStep, SearchWorkflow, WorkflowStep, StepContext
from scholar_flux.api.rate_limiting import threaded_rate_limiter_registry
from scholar_flux.api.providers import provider_registry
from scholar_flux.api.models import ProcessedResponse, ErrorResponse, NonResponse
from scholar_flux.utils import format_iso_timestamp, parse_iso_timestamp
from tests.testing_utilities import raise_error

from scholar_flux.exceptions import (
    InvalidCoordinatorParameterException,
    RequestFailedException,
    RetryAfterDelayExceededException,
)
from scholar_flux.api import ReconstructedResponse
from scholar_flux import logger
from tests.testing_utilities import search_coordinator_mocking_context
from requests.exceptions import Timeout

from scholar_flux.exceptions import (
    RequestCacheException,
    StorageCacheException,
)


@pytest.fixture(autouse=True)
def clear_response_history():
    """Helper fixture that clears response history in between tests to ensure that invalid mocks don't carry over."""
    yield
    SearchCoordinator._response_history.clear()


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

    This test parametrizes several individual fields to determine whether values for each field raise an
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
    """Verifies that an attempt to create a Search API without any arguments correctly raises a QueryValidationError."""
    with pytest.raises(InvalidCoordinatorParameterException) as excinfo:
        _ = SearchCoordinator._create_search_api()
    assert "Either 'query' or 'search_api' must be provided." in str(excinfo.value)


def test_build():
    """Verifies that building a new search coordinator from previously created components produces the same structure.

    The string representation of the coordinator includes a basic overview of the structure which should use the same
    api and response_coordinator with the same defaults.

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
    """Tests to verify that `search` correctly returns a `NonResponse` when an unexpected error occurs during retrieval.

    The `_search` private method is patched to raise an Exception to be handled within the `search` method.

    """
    search_coordinator = SearchCoordinator(query="test_query", base_url="https://thisisatesturl.com")

    e = "Directly raised exception"
    monkeypatch.setattr(
        search_coordinator,
        "_search",
        lambda *args, **kwargs: (_ for _ in ()).throw(Exception(e)),
    )

    msg = f"An unexpected error occurred when processing the response: {e}"
    response = search_coordinator.search(page=1)
    assert isinstance(response, NonResponse)
    assert msg in caplog.text
    assert e == response.message
    assert response.cache_key and search_coordinator._create_cache_key(page=1) == response.cache_key

    caplog.clear()

    response_list = search_coordinator.search_pages(pages=[1, 2, 3])
    assert len(response_list) == 1 and isinstance(response_list[0].response_result, NonResponse)
    assert msg in caplog.text

    caplog.clear()

    monkeypatch.setattr(
        search_coordinator,
        "search",
        lambda *args, **kwargs: (_ for _ in ()).throw(Exception(e)),
    )

    response_data = search_coordinator.search_data(page=1)
    assert response_data is None
    assert re.search(
        f"An unexpected error occurred when attempting to retrieve the processed response data:.*{e}",
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


def test_workflow_step_different_provider_pre_transform():
    """Verifies that the use of separate providers in the same workflow modifies the expected result as intended."""

    arxiv_workflow_step = WorkflowStep(provider_name="arxiv")
    crossref_workflow_step = WorkflowStep(provider_name="crossref")
    arxiv_step_context = StepContext(step=arxiv_workflow_step, step_number=0, result=None)

    updated_crossref_workflow_step = crossref_workflow_step.pre_transform(arxiv_step_context)
    crossref_config = provider_registry["crossref"]
    crossref_config_defaults = crossref_config.search_config_defaults()
    # Because the range of valid parameters for arxiv are not exactly the same for crossref, use a new parameter set
    assert all(
        updated_crossref_workflow_step.config_parameters[parameter] == value
        for parameter, value in crossref_config_defaults.items()
    )


def test_workflow_step_current_provider_pre_transform():
    """Verifies that not specifying a provider will then use the provider and parameters from the previous step."""

    arxiv_workflow_step = WorkflowStep(provider_name="arxiv")
    second_workflow_step = WorkflowStep(provider_name=None)
    # There should be no defaults to retrieve, because the provider name wasn't specified
    assert second_workflow_step._get_provider_config_defaults() is None
    arxiv_step_context = StepContext(step=arxiv_workflow_step, step_number=0, result=None)

    updated_second_workflow_step = second_workflow_step.pre_transform(arxiv_step_context)
    assert updated_second_workflow_step.config_parameters == arxiv_workflow_step.config_parameters


def test_blank_workflow_step():
    """Verifies that not specifying a provider will then default to using the config the SearchCoordinator."""
    identity_workflow = SearchWorkflow(steps=[WorkflowStep()])
    search_coordinator = SearchCoordinator(query="test query", provider_name="arxiv", workflow=identity_workflow)

    # prepares the initial search independent of the workflow
    prepared_search = search_coordinator.api.prepare_search(page=1)

    with requests_mock.Mocker() as m:
        m.get(
            prepared_search.url,
            status_code=200,
            content=b'{"test": "success"}',
            headers={"Content-Type": "application/json"},
        )
        mocked_page_result = search_coordinator.search(page=1)

        assert mocked_page_result and mocked_page_result.response
        assert mocked_page_result.response.url == prepared_search.url


def test_unknown_provider_workflow_step(caplog):
    """Verifies that specifying an unknown provider will then default to using the config the SearchCoordinator."""
    provider_name = "unknownprovider"
    unknown_provider_workflow = SearchWorkflow(steps=[WorkflowStep(), WorkflowStep(provider_name=provider_name)])
    assert (
        f"The provider, '{provider_name}' doesn't exist in the registry. The default settings for the "
        "SearchCoordinator will not be applied when applying this step in a workflow."
    ) in caplog.text
    search_coordinator = SearchCoordinator(
        query="test query", provider_name="arxiv", workflow=unknown_provider_workflow, request_delay=0
    )

    # prepares the initial search independent of the workflow
    prepared_search = search_coordinator.api.prepare_search(page=1)

    with requests_mock.Mocker() as m:
        m.get(
            prepared_search.url,
            status_code=200,
            content=b'{"test": "success"}',
            headers={"Content-Type": "application/json"},
        )
        mocked_page_result = search_coordinator.search(page=1)

        assert f"Couldn't find a configuration for the provider, '{provider_name}'." in caplog.text
        assert mocked_page_result and mocked_page_result.response
        assert mocked_page_result.response.url == prepared_search.url


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
        and api.provider_name == search_coordinator.provider_name
        and api.display_name == search_coordinator.display_name
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
    assert new_api.rate_limiter != api.rate_limiter

    # reinitializes the original API object in comparison with a new query, config, and rate limiter
    api._initialize(api.query, config=api.config, parameter_config=api.parameter_config, rate_limiter=rate_limiter)
    # ensure that the rate limiter is overridden as intended and the newly created search APIs use a previous SearchAPI
    assert api.rate_limiter is rate_limiter and api.config.request_delay == rate_limiter.min_interval == 30

    # the SearchCoordinator should also use the same rate limiter from the current API
    search_coordinator2 = SearchCoordinator.as_coordinator(new_api, search_coordinator.responses)

    # The structure of the first SearchCoordinator should exactly equal that of the second
    assert repr(search_coordinator) == repr(search_coordinator2)


def test_request_failed_exception(monkeypatch, caplog):
    """Verifies that when a request fails to generate a response and instead throws an error, the error is logged and
    the response result is a `NonResponse`."""
    coordinator = SearchCoordinator(query="Computer Science Testing", request_delay=0)
    monkeypatch.setattr(
        coordinator, "robust_request", lambda *a, **kw: (_ for _ in ()).throw(RequestFailedException("fail"))
    )
    res = coordinator.search(page=3)
    assert isinstance(res, NonResponse)
    assert "Failed to fetch page 3" in caplog.text
    assert res.message and "fail" in res.message
    assert res.error and res.error in "RequestFailedException" in res.error
    assert "NonResponse(error='RequestFailedException', message='Failed to fetch page 3: fail')" in repr(res)


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
        assert ("Expected to receive a valid response or response-like object, but received type: {type(None)}") in str(
            excinfo.value
        )

    response = search_coordinator._fetch_api_response(page=1)
    assert isinstance(response, NonResponse)
    assert "NonResponse" in repr(response)


def test_cache_retrieval_failure(monkeypatch, default_memory_cache_session, caplog):
    """Verifies exception handling when errors occur in the retrieval of cached responses.

    The function first validates that the `default_memory_cache_session` session object is cached as intended.
    Afterward, the `create_key` function of the API cache is patched to raise an error, which is then logged
    while a None value is returned.

    In context, this would later prompt the SearchCoordinator to retrieve the result from the API when `search`
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
    """Verifies that cached request/response deletions for non-existent keys catch exceptions and log missing keys."""
    search_coordinator = SearchCoordinator(query="Computer Science Testing", cache_requests=True, request_delay=0)
    search_coordinator._delete_cached_request(page=4)  # type: ignore
    assert re.search(
        "A cached response for the current request does not exist: 'Key [a-zA-Z0-9]+ not found", caplog.text
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
        assert f"Failed to get a valid response from {coordinator.display_name}"

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


def test_nonpaginated_search_success():
    """Tests that the SearchCoordinator can send non-paginated searches via `BaseCoordinator.parameter_search()`."""

    api = SearchAPI.from_defaults(
        provider_name="plos",
        query="basic coordination",
        base_url="https://test-example-url.com",
        request_delay=0,
    )

    coordinator = SearchCoordinator(search_api=api)

    prepared_api_request = coordinator.api.prepare_search(page=None, parameters={})
    prepared_search = coordinator._prepare_request(page=None, parameters={})

    # the URL should contain no additional arguments
    assert prepared_search.url and re.search(f"{coordinator.api.base_url}/?$", prepared_search.url)
    assert prepared_search.url == prepared_api_request.url

    with requests_mock.Mocker(real_http=False) as m:
        m.get(
            prepared_search.url,
            status_code=200,
            json={"result": []},
            headers={"Content-Type": "application/json"},
        )
        processed_response = coordinator.parameter_search(parameters={})
        # indicates successful processing and confirms that the URL was successfully mocked
        assert isinstance(processed_response, ProcessedResponse) and processed_response.url == prepared_search.url


def test_nonpaginated_search_with_endpoint_success():
    """Tests that the SearchCoordinator can send non-paginated searches via `SearchCoordinator.parameter_search()`."""

    endpoint = "example-endpoint"
    coordinator = SearchCoordinator(base_url="https://test-example-url.com", query="basic coordination")

    prepared_search = coordinator.api.prepare_search(page=None, endpoint=endpoint)

    assert prepared_search.url and re.search(f"{coordinator.api.base_url}/{endpoint}/?$", prepared_search.url)

    with requests_mock.Mocker() as m:
        m.get(
            prepared_search.url,
            status_code=200,
            json={"results": []},
            headers={"Content-Type": "application/json"},
        )

        processed_response = coordinator.parameter_search(endpoint=endpoint)
        # indicates successful processing and confirms that the endpoint at the URL was successfully mocked
        assert isinstance(processed_response, ProcessedResponse) and processed_response.url == prepared_search.url


def test_nonpaginated_search_resolution_failure():
    """Tests that the SearchCoordinator can send non-paginated searches via `BaseCoordinator.parameter_search()`."""
    coordinator = SearchCoordinator(base_url="https://test-example-url.com", query="basic coordination")

    with requests_mock.Mocker(real_http=False):
        # won't work due to the endpoint not being mocked
        nonresponse = coordinator.parameter_search(endpoint="test-endpoint")  #
    assert isinstance(nonresponse, NonResponse)

    error = nonresponse.error or ""
    message = nonresponse.message or ""
    assert "RequestFailedException" in error and "No mock address" in message

    # cache keys for mock-responses should originate from the response URL hash: missing URL -> missing cache key
    assert not nonresponse.url and not nonresponse.cache_key


def test_unexpected_nonpaginated_search_failure(monkeypatch, caplog):
    """Tests that `SearchCoordinator.parameter_search()` gracefully returns a `NonResponse` on unexpected errors."""

    coordinator = SearchCoordinator(base_url="https://test-example-url.com", query="basic coordination")
    err = "Forced unexpected error"
    monkeypatch.setattr(coordinator, "_search", raise_error(RuntimeError, err))

    with requests_mock.Mocker(real_http=False):
        # will throw an error before a request is ever sent (mocking is retained for safety)
        nonresponse = coordinator.parameter_search(endpoint="test-endpoint")

    assert isinstance(nonresponse, NonResponse)

    nonresponse_error = nonresponse.error or ""
    nonresponse_message = nonresponse.message or ""
    message = f"An unexpected error occurred when processing the response: {err}"
    assert "RuntimeError" in nonresponse_error and err == nonresponse_message
    assert message in caplog.text

    # cache keys for mock-responses should originate from the response URL hash: missing URL -> missing cache key
    assert not nonresponse.url and not nonresponse.cache_key


def test_respect_retry_after_date_sleep_called():
    """Tests that `_respect_retry_after` calls `sleep` with correct delay and timestamp when retry-after is present."""
    api = SearchAPI.from_defaults(
        provider_name="plos",
        query="test",
        records_per_page=10,
    )
    coordinator = SearchCoordinator(api)
    coordinator.api.rate_limiter._sleep = MagicMock()  # type: ignore
    coordinator.retry_handler.max_retries = 0

    # Simulate a last_response with a Retry-After header as a date
    retry_after_date = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=3)
    date_str = retry_after_date.strftime("%a, %d %b %Y %H:%M:%S GMT")

    prepared_search = coordinator.api.prepare_search(page=1)

    with requests_mock.Mocker() as m:
        m.get(
            prepared_search.url, status_code=429, headers={"Content-Type": "application/json", "Retry-After": date_str}
        )
        result = coordinator.search(page=1, from_request_cache=False, from_process_cache=False)
        coordinator._respect_retry_after()
        assert isinstance(result, ErrorResponse)
        assert isinstance(coordinator.last_response, ErrorResponse)

    # Assert sleep was called with a positive delay and correct timestamp
    assert coordinator.api.rate_limiter._sleep.called
    args, _ = coordinator.api.rate_limiter._sleep.call_args
    delay = args[0]
    assert delay > 0
    assert isinstance(delay, (int, float))


def test_cached_response_identification():
    """Verifies that ProcessedResponses can successfully indicate whether a response originated from session cache."""
    api = SearchAPI.from_defaults(
        provider_name="plos", query="test", base_url="https://example-base-url.com", request_delay=0.01
    )
    coordinator = SearchCoordinator(api, use_cache=True)
    with search_coordinator_mocking_context(coordinator, page=1, json={"success": True}):
        uncached_result = coordinator.search_page(page=1)
        cached_result = coordinator.search_page(page=1)

    assert uncached_result.cached is False
    assert cached_result.cached is True


def test_respect_retry_after_wait_called(caplog):
    """Tests that `_respect_retry_after` calls `_wait` with correct delay and timestamp when retry-after is present."""
    api = SearchAPI.from_defaults(
        provider_name="plos",
        query="test",
        records_per_page=10,
    )
    coordinator = SearchCoordinator(api)
    coordinator.api.rate_limiter._wait = MagicMock()  # type: ignore
    coordinator.retry_handler.max_retries = 0

    with search_coordinator_mocking_context(
        coordinator,
        page=1,
        status_code=429,
        headers={"Content-Type": "application/json", "Retry-After": "2"},
    ):
        result = coordinator.search(page=1, from_request_cache=False, from_process_cache=False)
        coordinator._respect_retry_after()
        assert isinstance(result, ErrorResponse)
        assert isinstance(coordinator.last_response, ErrorResponse)

    # Assert _wait was called with a positive delay and correct timestamp
    assert coordinator.api.rate_limiter._wait.called
    args, kwargs = coordinator.api.rate_limiter._wait.call_args
    delay, timestamp = args
    assert delay > 0
    assert isinstance(timestamp, float)
    timestamp = parse_iso_timestamp(result.created_at or "")
    formatted_timestamp = timestamp.strftime("%Y-%m-%d at %H:%M:%S") if timestamp else "<error>"
    provider_name = coordinator.display_name
    logged_msg = (
        rf"{provider_name} sent a `Retry-After` field of {delay}s on {formatted_timestamp}. Respecting the delay of "
        rf"~\d+.\d?..."
    )
    assert re.search(logged_msg, caplog.text)


def test_retry_after_does_not_raise_when_disabled(caplog, monkeypatch):
    """Tests that the RetryHandler waits for long `Retry-After` headers when `RAISE_ON_RETRY_DELAY_EXCEEDED=False`.

    In addition, the behavior upon re-requesting a previously excessively rate limited request is verified to ensure
    that future searches still respect the rate limit. `wait_since` should see the original sleep time and compare
    it against the moment that the request was made.

    """
    api = SearchAPI.from_defaults(
        provider_name="plos",
        query="test",
        records_per_page=10,
    )
    coordinator = SearchCoordinator(api, request_delay=0.01)
    coordinator.retry_handler.max_retries = 1
    coordinator.retry_handler.max_backoff = 0.5

    retry_after = "100"
    with (
        monkeypatch.context() as m,
        search_coordinator_mocking_context(
            coordinator,
            page=1,
            status_code=429,
            headers={"Content-Type": "application/json", "Retry-After": retry_after},
        ),
    ):
        m.setattr(coordinator.retry_handler, "RAISE_ON_DELAY_EXCEEDED", False)
        # skip
        m.setattr(coordinator.api.rate_limiter, "_sleep", lambda *args, **kwargs: None)
        result = coordinator.search(page=1, from_request_cache=False, from_process_cache=False)
        assert (
            isinstance(result, ErrorResponse)
            and result.error
            and result.message
            and result.error != "RetryAfterDelayExceededException"
            and f"Server requested a {retry_after}s wait before retrying" not in result.message
        )
        assert (
            "RAISE_ON_DELAY_EXCEEDED is disabled. The retry handler will wait for the full duration "
            f"of {retry_after}s as requested by the server, even if it exceeds your configured maximum. This "
            "may result in long waits."
        ) in caplog.text

        # The rate limiter should respect the previously registered rate limit for future classes:
        coordinator.api.rate_limiter.wait_since = MagicMock()  # type: ignore

        # Called automatically during `.search()`
        coordinator._respect_retry_after()
        assert coordinator.api.rate_limiter.wait_since.called
        # Retry-After Delay should be the same
        assert coordinator.api.rate_limiter.wait_since.call_args[0][0] == int(retry_after)
        # Response retrieval time
        assert format_iso_timestamp(coordinator.api.rate_limiter.wait_since.call_args[0][1]) == result.created_at


def test_robust_request_reraises_retry_after_delay_exceeded():
    """Verifies that `robust_request` re-raises  and propagates the `RetryAfterDelayExceededException` context."""
    api = SearchAPI.from_defaults(provider_name="crossref", query="test")
    coordinator = SearchCoordinator(api)

    retry_after = "300"
    err = (
        "Server requested a 300s wait before retrying, which exceeds the configured limit of 120s. This typically "
        "means you've hit a rate limit"
    )
    with (
        search_coordinator_mocking_context(
            coordinator,
            page=1,
            status_code=429,
            headers={"Retry-After": retry_after},
        ),
        pytest.raises(RetryAfterDelayExceededException) as excinfo,
    ):
        _ = coordinator.robust_request(page=1)

    assert err in str(excinfo.value)
    assert err in excinfo.value.message
    assert excinfo.value.response is not None


def test_retry_after_raise_rate_limit_exceeded_exception(caplog):
    """Tests that a `RetryAfterDelayExceededException` is raised when a Retry-After field exceeds the limit."""
    api = SearchAPI.from_defaults(
        provider_name="plos",
        query="test",
        records_per_page=10,
    )
    coordinator = SearchCoordinator(api)
    retry_after = "200"
    with search_coordinator_mocking_context(
        coordinator,
        page=1,
        status_code=429,
        headers={"Content-Type": "application/json", "Retry-After": retry_after},
    ):
        result = coordinator.search(page=1, from_request_cache=False, from_process_cache=False)
        assert (
            isinstance(result, ErrorResponse)
            and result.message
            and result.error == "RetryAfterDelayExceededException"
            and f"Server requested a {retry_after}s wait before retrying" in result.message
        )
        assert "Failed to fetch page 1" in caplog.text


def test_retry_after_raise_rate_limit_exceed_fetch_returns_response(caplog):
    """Tests that the `fetch` method handles and returns a response if `raise_on_error=False` on large Retry-After."""
    api = SearchAPI.from_defaults(
        provider_name="plos",
        query="test",
        records_per_page=10,
    )
    coordinator = SearchCoordinator(api)
    retry_after = "200"
    with search_coordinator_mocking_context(
        coordinator,
        page=1,
        status_code=429,
        headers={"Content-Type": "application/json", "Retry-After": retry_after},
    ):
        result = coordinator.fetch(page=1, raise_on_error=False)
        assert isinstance(result, Response) and result.status_code == 429
        assert "Failed to fetch page 1" in caplog.text


def test_retry_after_does_not_raise_when_disabled(caplog, monkeypatch):
    """Tests that the RetryHandler waits for long `Retry-After` headers when `RAISE_ON_RETRY_DELAY_EXCEEDED=False`.

    In addition, the behavior upon re-requesting a previously excessively rate limited request is verified to ensure
    that future searches still respect the rate limit. `wait_since` should see the original sleep time and compare
    it against the moment that the request was made.

    """
    api = SearchAPI.from_defaults(
        provider_name="plos",
        query="test",
        records_per_page=10,
    )
    coordinator = SearchCoordinator(api, request_delay=0.01)
    coordinator.retry_handler.max_retries = 1
    coordinator.retry_handler.max_backoff = 0.5

    retry_after = "100"
    with (
        monkeypatch.context() as m,
        search_coordinator_mocking_context(
            coordinator,
            page=1,
            status_code=429,
            headers={"Content-Type": "application/json", "Retry-After": retry_after},
        ),
    ):
        m.setattr(coordinator.retry_handler, "RAISE_ON_DELAY_EXCEEDED", False)
        # skip
        m.setattr(coordinator.api.rate_limiter, "_sleep", lambda *args, **kwargs: None)
        result = coordinator.search(page=1, from_request_cache=False, from_process_cache=False)
        assert (
            isinstance(result, ErrorResponse)
            and result.error
            and result.message
            and result.error != "RetryAfterDelayExceededException"
            and f"Server requested a {retry_after}s wait before retrying" not in result.message
        )
        assert (
            "RAISE_ON_DELAY_EXCEEDED is disabled. The retry handler will wait for the full duration "
            f"of {retry_after}s as requested by the server, even if it exceeds your configured maximum. This "
            "may result in long waits."
        ) in caplog.text

        # The rate limiter should respect the previously registered rate limit for future classes:
        coordinator.api.rate_limiter.wait_since = MagicMock()  # type: ignore

        # Called automatically during `.search()`
        coordinator._respect_retry_after()
        assert coordinator.api.rate_limiter.wait_since.called
        # Retry-After Delay should be the same
        assert coordinator.api.rate_limiter.wait_since.call_args[0][0] == int(retry_after)
        # Response retrieval time
        assert format_iso_timestamp(coordinator.api.rate_limiter.wait_since.call_args[0][1]) == result.created_at


def test_robust_request_reraises_retry_after_delay_exceeded():
    """Verifies that `robust_request` re-raises  and propagates the `RetryAfterDelayExceededException` context."""
    api = SearchAPI.from_defaults(provider_name="crossref", query="test")
    coordinator = SearchCoordinator(api)

    retry_after = "300"
    err = (
        "Server requested a 300s wait before retrying, which exceeds the configured limit of 120s. This typically "
        "means you've hit a rate limit"
    )
    with (
        search_coordinator_mocking_context(
            coordinator,
            page=1,
            status_code=429,
            headers={"Retry-After": retry_after},
        ),
        pytest.raises(RetryAfterDelayExceededException) as excinfo,
    ):
        _ = coordinator.robust_request(page=1)

    assert err in str(excinfo.value)
    assert err in excinfo.value.message
    assert excinfo.value.response is not None


def test_retry_after_raise_rate_limit_exceeded_exception(caplog):
    """Tests that a `RetryAfterDelayExceededException` is raised when a Retry-After field exceeds the limit."""
    api = SearchAPI.from_defaults(
        provider_name="plos",
        query="test",
        records_per_page=10,
    )
    coordinator = SearchCoordinator(api)
    retry_after = "200"
    with search_coordinator_mocking_context(
        coordinator,
        page=1,
        status_code=429,
        headers={"Content-Type": "application/json", "Retry-After": retry_after},
    ):
        result = coordinator.search(page=1, from_request_cache=False, from_process_cache=False)
        assert (
            isinstance(result, ErrorResponse)
            and result.message
            and result.error == "RetryAfterDelayExceededException"
            and f"Server requested a {retry_after}s wait before retrying" in result.message
        )
        assert "Failed to fetch page 1" in caplog.text


def test_retry_after_raise_rate_limit_exceed_fetch_returns_response(caplog):
    """Tests that the `fetch` method handles and returns a response if `raise_on_error=False` on large Retry-After."""
    api = SearchAPI.from_defaults(
        provider_name="plos",
        query="test",
        records_per_page=10,
    )
    coordinator = SearchCoordinator(api)
    retry_after = "200"
    with search_coordinator_mocking_context(
        coordinator,
        page=1,
        status_code=429,
        headers={"Content-Type": "application/json", "Retry-After": retry_after},
    ):
        result = coordinator.fetch(page=1, raise_on_error=False)
        assert isinstance(result, Response) and result.status_code == 429
        assert "Failed to fetch page 1" in caplog.text


@pytest.mark.parametrize("retry_after_value", (None, "", "non-numeric", "3-23-1923"))
def test_respect_retry_after_malformed(retry_after_value):
    """Verifies that `sleep()` method is not called if the `retry_after` header value is malformed."""
    api = SearchAPI.from_defaults(
        provider_name="plos",
        query="test",
        records_per_page=10,
    )
    coordinator = SearchCoordinator(api)
    coordinator.api.rate_limiter.sleep = MagicMock()  # type: ignore
    coordinator.retry_handler.max_retries = 0

    with search_coordinator_mocking_context(
        coordinator,
        page=1,
        status_code=429,
        json={"status": "not ok"},
        headers={"Content-Type": "application/json", "Retry-After": retry_after_value},
    ):
        result = coordinator.search(page=1, from_request_cache=False, from_process_cache=False)
        assert isinstance(result, ErrorResponse) and result is not None
        coordinator._respect_retry_after()  # retry-after then defaults to 0 and skips

    # Assert sleep was not called
    assert not coordinator.api.rate_limiter.sleep.called


def test_respect_retry_after_implicit_wait():
    """Verifies that `wait()` method is called when the retry-handler requires the request to be re-sent."""
    api = SearchAPI.from_defaults(
        provider_name="plos",
        query="test",
        records_per_page=10,
    )
    coordinator = SearchCoordinator(api, request_delay=0.01)

    coordinator.api.rate_limiter._wait = MagicMock()  # type: ignore
    coordinator.retry_handler.max_retries = 4
    coordinator.retry_handler.backoff_factor = 0

    with search_coordinator_mocking_context(
        coordinator,
        status_code=429,
        headers={"Content-Type": "application/json"},
    ):
        result = coordinator.search(page=1, from_request_cache=False, from_process_cache=False)
        assert coordinator.api.rate_limiter._wait.called
        assert isinstance(result, ErrorResponse) and result is not None
        assert len(coordinator.api.rate_limiter._wait.call_args_list) == coordinator.retry_handler.max_retries


def test_robust_request_min_retry_delay(monkeypatch):
    """Test that robust_request passes min_retry_delay from request_delay to RetryHandler."""
    api = SearchAPI.from_defaults(
        provider_name="plos",
        query="test",
        base_url="https://api.example.com",
        request_delay=2.0,
    )
    coordinator = SearchCoordinator(api)
    called_kwargs = {}

    def mock_execute_with_retry(*args, **kwargs) -> None:
        """Helper function for monitoring keywords that are passed to the `RetryHandler.execute_with_retry` method."""
        called_kwargs.update(kwargs)
        return None

    monkeypatch.setattr(coordinator.retry_handler, "execute_with_retry", mock_execute_with_retry)
    coordinator.robust_request(page=1)
    assert called_kwargs["min_retry_delay"] == 2.0
    coordinator.robust_request(page=1, request_delay=3.0)
    assert called_kwargs["min_retry_delay"] == 3.0


def test_api_specific_parameter_field_overrides(monkeypatch):
    """Test that the `SearchAPI.search` method correctly accepts keyword parameters specified in the parameter map."""

    api = SearchAPI.from_defaults(
        provider_name="crossref",
        query="test",
        base_url="https://api.example.com",
        request_delay=2.0,
    )
    coordinator = SearchCoordinator(api)
    called_kwargs = {}

    def monitor_and_mock_response(*args, **kwargs) -> ReconstructedResponse:
        """Monitors the keyword args that are passed to the `api.search` method and returns a response-like object."""
        mock_response = ReconstructedResponse.build(status_code=200, json={"status": "ok"}, url=api.base_url)
        called_kwargs.update(kwargs)
        return mock_response

    monkeypatch.setattr(coordinator.api, "search", monitor_and_mock_response)

    email = "a.valid@email.com"
    sort_parameter = "published"
    sort_order = "asc"

    # The first call should not add any API-specific parameters to the API-call if they aren't directly specified.
    _ = coordinator.search(1, mailto=email, sort=sort_parameter, order=sort_order)
    assert called_kwargs["page"] == 1
    assert "mailto" not in called_kwargs and "sort" not in called_kwargs and "order" not in called_kwargs

    # The second call explicitly sets overrides for these variables which should be extracted into a `parameters` dict
    _ = coordinator.search(2, mailto=email, sort=sort_parameter, order=sort_order)
    assert called_kwargs["page"] == 2
    assert called_kwargs["parameters"]["mailto"] == email
    assert called_kwargs["parameters"]["sort"] == sort_parameter
    assert called_kwargs["parameters"]["order"] == sort_order


@pytest.mark.parametrize("timeout_exception", [Timeout, TimeoutError])
def test_timeouterror_exception(timeout_exception, monkeypatch):
    """Verifies that timeouts are caught and handled correctly within the retry handler during search execution."""

    api = SearchAPI.from_defaults(
        provider_name="crossref",
        query="test",
        base_url="https://api.example.com",
        request_delay=2.0,
    )
    coordinator = SearchCoordinator(api)
    error_message = f"HTTPSConnectionPool(host='{coordinator.api.base_url}', port=443): Read timed out."
    monkeypatch.setattr(coordinator.api, "send_request", raise_error(timeout_exception, error_message))

    with requests_mock.Mocker(real_http=False) as _:
        result = coordinator.search_page(page=1)

    assert isinstance(result.response_result, NonResponse)
    assert result.error == timeout_exception.__name__

    recorded_retry_attempt = coordinator.retry_handler.history[-1]

    # Verifying core field values
    assert (
        recorded_retry_attempt.success is False
        and recorded_retry_attempt.duration is not None
        and recorded_retry_attempt.duration > 0
        and recorded_retry_attempt.timeout is True
    )

    # Verifying the error message
    assert recorded_retry_attempt.error == timeout_exception.__name__
    assert recorded_retry_attempt.url == coordinator.api.base_url
    assert recorded_retry_attempt.message == error_message


def test_search_coordinator_retry_handling_masks_sensitive_URL_api_keys(caplog):
    """Validates that historical records of throttled searches filter api keys from recorded URLs if logged."""
    api_key_to_mask = "mock_api_key_that_should_be_masked"
    api = SearchAPI.from_defaults(
        provider_name="core", query="test", records_per_page=10, api_key=api_key_to_mask, use_cache=False
    )
    coordinator = SearchCoordinator(api, request_delay=0.01)
    coordinator.retry_handler.history.clear_history()

    with requests_mock.Mocker() as m:
        # queries the first 3 pages
        pages = range(1, 4)
        for i in pages:
            prepared_search = coordinator.api.prepare_search(page=i)
            m.get(
                prepared_search.url,
                status_code=200,
                json={"status": "success", "data": []},
                headers={"Content-Type": "application/json"},
            )
            _ = coordinator.search_page(i)

    assert len(coordinator.retry_handler.history) == 3
    logger.info(coordinator.retry_handler.history)  # Records a custom bounded deque containing queried URLs
    assert api_key_to_mask not in caplog.text
    for i in pages:
        masked_url = str(coordinator._prepare_request(page=1).url).replace(api_key_to_mask, "***")
        assert masked_url and masked_url in caplog.text
