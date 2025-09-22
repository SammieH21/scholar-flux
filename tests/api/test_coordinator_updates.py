import pytest
from copy import deepcopy
from scholar_flux.api.search_coordinator import SearchCoordinator, SearchAPI, RetryHandler, ResponseValidator


@pytest.fixture(scope="session")
def base_coordinator():
    base_coordinator = SearchCoordinator(query="original_query", provider_name="pubmed", cache_results=False)
    return base_coordinator


def test_identical_update(base_coordinator):
    """All components should be the same since no individual component was modified"""
    identical_coordinator = SearchCoordinator.update(base_coordinator)
    assert (
        base_coordinator.search_api == identical_coordinator.search_api
        and base_coordinator.response_coordinator == identical_coordinator.response_coordinator
        and base_coordinator.retry_handler == identical_coordinator.retry_handler
        and base_coordinator.workflow == identical_coordinator.workflow
        and base_coordinator.validator == identical_coordinator.validator
    )


def test_with_new_components(base_coordinator):
    """Each component, outside of the workflow will be different"""
    new_response_coordinator = deepcopy(base_coordinator.responses)
    new_response_coordinator.cache_manager = new_response_coordinator.cache_manager.with_storage("inmemory")
    new_search_api = base_coordinator.search_api.update(base_coordinator.search_api, query="new_query")
    new_retry_handler = RetryHandler(max_retries=0)
    new_response_validator = ResponseValidator()

    new_coordinator = SearchCoordinator.update(
        base_coordinator,
        search_api=new_search_api,
        retry_handler=new_retry_handler,
        validator=new_response_validator,
        response_coordinator=new_response_coordinator,
    )

    assert (
        base_coordinator.search_api != new_search_api == new_coordinator.search_api
        and base_coordinator.response_coordinator != new_response_coordinator == new_coordinator.responses
        and base_coordinator.retry_handler != new_retry_handler == new_coordinator.retry_handler
        and base_coordinator.workflow == new_coordinator.workflow
        and base_coordinator.validator != new_response_validator == new_coordinator.validator
    )


def test_provider_update(base_coordinator):
    """The workflow shouldn't apply any more since this will be a different provider - will be None"""
    coordinator_with_updated_provider = SearchCoordinator.update(
        base_coordinator, search_api=SearchAPI.update(base_coordinator.search_api, provider_name="crossref")
    )

    assert (
        coordinator_with_updated_provider.search_api != base_coordinator.search_api
        and coordinator_with_updated_provider.search_api.provider_name == "crossref"
        and coordinator_with_updated_provider.response_coordinator == base_coordinator.responses
        and coordinator_with_updated_provider.retry_handler == base_coordinator.retry_handler
        and coordinator_with_updated_provider.workflow is None
        and coordinator_with_updated_provider.validator == base_coordinator.validator
    )
