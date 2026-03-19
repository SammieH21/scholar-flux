import pytest
from copy import deepcopy
from scholar_flux.api import (
    BaseCoordinator,
    SearchCoordinator,
    SearchAPI,
    ResponseCoordinator,
    RetryHandler,
    ResponseValidator,
)
from scholar_flux.exceptions import InvalidCoordinatorParameterException
from requests_cache.session import CachedSession


@pytest.fixture(scope="session")
def default_coordinator():
    """Fixture for a basic SearchCoordinator serving as a baseline for testing update functionality."""
    search_coordinator = SearchCoordinator(query="original_query", provider_name="pubmed", cache_results=False)
    return search_coordinator


def test_identical_update(default_coordinator):
    """Tests whether all components are unmodified as expected, since no elements were modified."""
    identical_coordinator = SearchCoordinator.update(default_coordinator)
    assert (
        default_coordinator.search_api == identical_coordinator.search_api
        and default_coordinator.response_coordinator == identical_coordinator.response_coordinator
        and default_coordinator.retry_handler == identical_coordinator.retry_handler
        and default_coordinator.workflow == identical_coordinator.workflow
        and default_coordinator.validator == identical_coordinator.validator
    )


@pytest.mark.parametrize("coordinator_class", (BaseCoordinator, SearchCoordinator))
def test_invalid_coordinator_parameter_exception(coordinator_class):
    """Tests whether an exception is raised when `SearchCoordinator.update()` receives the incorrect type."""
    invalid_coordinator = "not a coordinator"
    err = f"Expected a {coordinator_class.__name__} to perform parameter updates. Received type {type(invalid_coordinator)}"
    with pytest.raises(InvalidCoordinatorParameterException, match=err):
        _ = coordinator_class.update(invalid_coordinator)  # type: ignore


def test_with_new_components(default_coordinator):
    """Test whether each component, outside of the workflow, will be modified in a new instance as expected after
    updating the response coordinator."""
    new_response_coordinator = deepcopy(default_coordinator.responses)
    new_response_coordinator.cache_manager = new_response_coordinator.cache_manager.with_storage("inmemory")
    new_search_api = default_coordinator.search_api.update(default_coordinator.search_api, query="new_query")
    new_retry_handler = RetryHandler(max_retries=0)
    new_response_validator = ResponseValidator()

    new_coordinator = SearchCoordinator.update(
        default_coordinator,
        search_api=new_search_api,
        retry_handler=new_retry_handler,
        validator=new_response_validator,
        response_coordinator=new_response_coordinator,
    )

    assert (
        default_coordinator.search_api != new_search_api == new_coordinator.search_api
        and default_coordinator.response_coordinator != new_response_coordinator == new_coordinator.responses
        and default_coordinator.retry_handler != new_retry_handler == new_coordinator.retry_handler
        and default_coordinator.workflow == new_coordinator.workflow
        and default_coordinator.validator != new_response_validator == new_coordinator.validator
    )


def test_default_coordinator_with_config_parameters_context(default_coordinator):
    """Verifies that the SearchCoordinator context selectively updates components only if their parameters change."""
    search_coordinator = SearchCoordinator.as_coordinator(default_coordinator.search_api, default_coordinator.responses)

    with search_coordinator.with_components(query="new-query", cache_requests=True) as new_coordinator:
        assert search_coordinator.responses is new_coordinator.responses
        assert search_coordinator.workflow is new_coordinator.workflow
        assert search_coordinator.retry_handler is new_coordinator.retry_handler
        assert search_coordinator.search_api != new_coordinator.search_api
        assert isinstance(new_coordinator.api.session, CachedSession) and not isinstance(
            search_coordinator.api.session, CachedSession
        )
        assert new_coordinator.search_api.query == "new-query"
        assert search_coordinator.search_api.query != new_coordinator.search_api.query

    with search_coordinator.with_components(cache_results=False) as new_coordinator:
        assert search_coordinator.api is new_coordinator.api
        assert search_coordinator.responses is not new_coordinator.responses
        assert search_coordinator.responses.cache_manager.__dict__ != new_coordinator.responses.cache_manager.__dict__

    assert search_coordinator.responses is default_coordinator.responses
    assert search_coordinator.api is default_coordinator.api


def test_base_coordinator_with_config_parameters_context(default_coordinator):
    """Verifies that the BaseCoordinator context selectively updates components only if their parameters change."""
    base_coordinator = BaseCoordinator.update(default_coordinator)
    search_api = SearchAPI.update(base_coordinator.api, query="new-query", use_cache=True)
    with base_coordinator.with_components(search_api) as new_coordinator:
        assert base_coordinator.responses is new_coordinator.responses
        assert isinstance(new_coordinator.api.session, CachedSession) and not isinstance(
            base_coordinator.api.session, CachedSession
        )

    response_coordinator = ResponseCoordinator.build(annotate_records=True, cache_results=False)
    with base_coordinator.with_components(response_coordinator=response_coordinator) as new_coordinator:
        assert base_coordinator.api is new_coordinator.api
        assert base_coordinator.responses is not new_coordinator.responses
        # Annotate records is False by default, but is changed to True within the context:
        assert base_coordinator.responses.extractor.__dict__ != new_coordinator.extractor.__dict__
        # The original ResponseCoordinator uses a basic memory cache while the new coordinator uses a NullStorage
        assert base_coordinator.responses.cache_manager.__dict__ != new_coordinator.responses.cache_manager.__dict__

    assert base_coordinator.responses is default_coordinator.responses
    assert base_coordinator.api is default_coordinator.api


def test_provider_update(default_coordinator):
    """The workflow shouldn't apply any more since this will be a different provider - will be None"""
    coordinator_with_updated_provider = SearchCoordinator.update(
        default_coordinator, search_api=SearchAPI.update(default_coordinator.search_api, provider_name="crossref")
    )

    assert (
        coordinator_with_updated_provider.search_api != default_coordinator.search_api
        and coordinator_with_updated_provider.search_api.provider_name == "crossref"
        and coordinator_with_updated_provider.response_coordinator == default_coordinator.responses
        and coordinator_with_updated_provider.retry_handler == default_coordinator.retry_handler
        and coordinator_with_updated_provider.workflow is None
        and coordinator_with_updated_provider.validator == default_coordinator.validator
    )
