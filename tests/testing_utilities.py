# /tests/testing_utilities
"""Helper module for reusing test functionality with similar logic under the hood to verify ScholarFlux
functionality."""
from typing import Optional, Callable, Type, TYPE_CHECKING, Generator, Mapping
import os
import requests_mock
from contextlib import contextmanager

if TYPE_CHECKING:
    from scholar_flux import SearchCoordinator


def enable_debugging():
    """Helper function that defines the environment variables needed to enable logging by default in ScholarFlux."""
    os.environ["SCHOLAR_FLUX_LOG_LEVEL"] = "DEBUG"
    os.environ["SCHOLAR_FLUX_ENABLE_LOGGING"] = "TRUE"
    os.environ["SCHOLAR_FLUX_PROPAGATE_LOGS"] = "TRUE"


def raise_error(exception_type: Type[BaseException], message: Optional[str] = None) -> Callable:
    """Helper method for manually raising an error message."""
    return lambda *args, **kwargs: (_ for _ in ()).throw(exception_type(message) if message else exception_type())


@contextmanager
def search_coordinator_mocking_context(
    search_coordinator: "SearchCoordinator",
    page: Optional[int] = 1,
    endpoint: Optional[str] = None,
    status_code: int = 200,
    headers: Optional[Mapping] = None,
    json_data: Optional[dict] = None,
    kwargs: Optional[dict] = None,
) -> Generator[requests_mock.Mocker, None, None]:
    """Context manager that uses the coordinator as well as the response json to mock a response."""
    headers = headers or {"content-type": "application/json"}
    prepared_search = search_coordinator.api.prepare_search(page=page, endpoint=endpoint)

    with requests_mock.Mocker() as m:
        m.get(prepared_search.url, headers=headers, status_code=status_code, json=json_data, **(kwargs or {}))
        yield m


__all__ = ["enable_debugging", "raise_error", "search_coordinator_mocking_context"]
