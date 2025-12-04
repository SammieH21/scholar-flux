import pytest
import requests_mock

from scholar_flux.sessions import CachedSessionManager
from scholar_flux.api import SearchAPI, BaseCoordinator, ResponseCoordinator
from scholar_flux.api.models import ProcessedResponse, ErrorResponse
from scholar_flux.api.validators import normalize_url
from scholar_flux.exceptions import InvalidCoordinatorParameterException, RequestFailedException
from scholar_flux.data import BaseDataParser, DataExtractor, PassThroughDataProcessor, PathDataProcessor


def test_base_coordinator_initialization(caplog):
    """Tests both valid and invalid inputs to ensure that upon creating a BaseCoordinator, inputs are validated to
    accept only a SearchAPI and a ResponseCoordinator.

    For all other possible input types, a InvalidCoordinatorParameterException should be raised instead.

    """
    api = SearchAPI(query="biology")
    response_coordinator = ResponseCoordinator.build()

    with pytest.raises(InvalidCoordinatorParameterException):
        _ = BaseCoordinator(search_api=api, response_coordinator=1)  # type: ignore

    with pytest.raises(InvalidCoordinatorParameterException):
        _ = BaseCoordinator(search_api=1, response_coordinator=response_coordinator)  # type: ignore
        assert "Could not initialize the BaseCoordinator due to an issue creating the SearchAPI." in caplog.text

    base_coordinator = BaseCoordinator(api, response_coordinator)
    assert (
        isinstance(base_coordinator, BaseCoordinator)
        and base_coordinator.search_api == api
        and base_coordinator.response_coordinator == response_coordinator
    )


def test_base_coordinator_build():
    """Tests whether the `as_coordinator` argument creates a new BaseCoordinator as a classmethod that can be extended
    by subclasses.

    Independent of whether the regular __init__ method or the classmethod is used, the result should have the same
    structure as indicated by its representation

    """
    api = SearchAPI(query="biology")
    response_coordinator = ResponseCoordinator.build()

    base_search_coordinator = BaseCoordinator.as_coordinator(api, response_coordinator)
    new_base_coordinator = BaseCoordinator(api, response_coordinator)
    assert repr(new_base_coordinator) == repr(base_search_coordinator)


def test_base_coordinator_override_build():
    """All additional parameters should override previous configurations as requested with updates to the properties
    that hold the search_api and response_coordinator while simultaneously not allowing bad inputs for components when
    set directly."""
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
    base_search_coordinator.extractor = extractor
    base_search_coordinator.processor = processor
    base_search_coordinator.search_api = new_api

    assert base_search_coordinator.parser == base_parser
    assert base_search_coordinator.extractor == extractor
    assert base_search_coordinator.processor == processor
    assert base_search_coordinator.search_api == base_search_coordinator.api == new_api
    assert base_search_coordinator.responses == base_search_coordinator.response_coordinator == response_coordinator
    assert base_search_coordinator.responses.cache == base_search_coordinator.responses.cache_manager

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
        base_search_coordinator.response_coordinator.cache = 1  # type:ignore

    with pytest.raises(InvalidCoordinatorParameterException):
        base_search_coordinator.parser = 1  # type:ignore

    with pytest.raises(InvalidCoordinatorParameterException):
        base_search_coordinator.extractor = 1  # type:ignore

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


def test_base_coordinator_initialization_updates():
    """Ensure that updates to core components don't directly impact the configuration of an existing base coordinator,
    and instead create new objects without changing the original."""
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


def test_base_coordinator_request_failed_exception(monkeypatch, caplog):
    """Verifies that failed `BaseCoordinator.search` requests are caught, instead returning None if possible."""

    api = SearchAPI(query="biology")
    response_coordinator = ResponseCoordinator.build()

    coordinator = BaseCoordinator(api, response_coordinator)
    monkeypatch.setattr(
        coordinator.api, "search", lambda *a, **kw: (_ for _ in ()).throw(RequestFailedException("fail"))
    )
    res = coordinator.search(page=2)
    assert f"Failed to get a valid response from the {api.provider_name} API: fail" in caplog.text
    assert res is None


def test_base_coordinator_nonpaginated_search_success():
    """Verifies that the `BaseCoordinator.parameter_search()` method can send non-paginated searches."""
    api = SearchAPI.from_defaults(
        provider_name="plos",
        query="basic coordination",
        base_url="https://test-example-url.com",
        request_delay=0,
    )
    responses = ResponseCoordinator.build()
    coordinator = BaseCoordinator.as_coordinator(search_api=api, response_coordinator=responses)

    prepared_base_url_request = coordinator.api.prepare_search(page=None, parameters={})

    with requests_mock.Mocker() as m:
        m.get(
            prepared_base_url_request.url,
            status_code=200,
            json={"status": "success"},
            headers={"Content-Type": "application/json"},
        )

        response = coordinator.parameter_search(parameters={})
        assert response
        assert (
            response.url
            and prepared_base_url_request.url
            and normalize_url(response.url, remove_parameters=False) == normalize_url(prepared_base_url_request.url)
        )
        assert normalize_url(prepared_base_url_request.url) == normalize_url(coordinator.api.base_url)


def test_base_coordinator_nonpaginated_search_with_endpoint_success():
    """Tests that the BaseCoordinator can send non-paginated searches via `BaseCoordinator.parameter_search()`."""

    endpoint = "example-endpoint"
    api = SearchAPI.from_defaults(
        provider_name="plos",
        query="basic coordination",
        base_url=f"https://test-example-url.com/{endpoint}",
        request_delay=0,
    )
    responses = ResponseCoordinator.build()
    coordinator = BaseCoordinator.as_coordinator(search_api=api, response_coordinator=responses)

    prepared_endpoint_request = coordinator.api.prepare_search(page=None, endpoint=endpoint)

    with requests_mock.Mocker() as m:
        m.get(
            prepared_endpoint_request.url,
            status_code=200,
            json={"status": "success"},
            headers={"Content-Type": "application/json"},
        )

        endpoint_response = coordinator.parameter_search(endpoint=endpoint)
        assert endpoint_response
        assert endpoint_response.url and prepared_endpoint_request.url
        assert normalize_url(endpoint_response.url) == normalize_url(prepared_endpoint_request.url)

        response = coordinator.parameter_search(parameters={})
        assert response


def test_basic_coordinator_search(default_memory_cache_session, academic_json_response):
    """Tests for whether the defaults are specified correctly and whether the mocked response is processed as intended
    throughout the coordinator.

    All successfully received and processed responses should return a ProcessedResponse object, even in the absence
    of an extracted record.

    For processed responses, the `.data` attribute should contain the records that have been parsed and processed.

    Errors that occur during retrieval or processing should instead be logged and recorded in an ErrorResponse.

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

    prepared_request = api.prepare_search(page=1)
    assert prepared_request.url is not None

    with requests_mock.Mocker() as m:
        m.get(
            prepared_request.url,
            status_code=200,
            content=academic_json_response.content,
            headers={"Content-Type": "application/json"},
        )

        result = coordinator.search(page=1, cache_key="test-cache-key")

        assert result and result.data and len(result.data) == 3

        # Overwrites the previous mocked URL
        m.get(prepared_request.url, status_code=429, headers={"Content-Type": "application/json"})

        # The cache should retrieve the previously cached response directly without sending a new request
        result = coordinator.search(page=1, cache_key="test-cache-key")
        assert isinstance(result, ProcessedResponse) and result

        request_key = api.cache.create_key(prepared_request)
        api.cache.delete(request_key)

        # the previous request should be deleted at this point, sending a new request that fails with status code = 429
        result = coordinator.search(page=1, cache_key="test-cache-key")
        assert isinstance(result, ErrorResponse) and not result
