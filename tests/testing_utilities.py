# /tests/testing_utilities
"""Helper module for reusing test functionality with similar logic under the hood to verify ScholarFlux
functionality."""
import os
from collections.abc import Callable, Generator, Iterable, Mapping
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any

import requests_mock

if TYPE_CHECKING:
    from scholar_flux import SearchCoordinator


DISABLE_ENV_LIST: list[str] = [
    "SCHOLAR_FLUX_HOME",
    "SCHOLAR_FLUX_DEFAULT_MAILTO",
    "SCHOLAR_FLUX_DEFAULT_USER_AGENT",
    "SCHOLAR_FLUX_DEFAULT_SESSION_CACHE_BACKEND",
    "SCHOLAR_FLUX_DEFAULT_RESPONSE_CACHE_STORAGE",
    "SCHOLAR_FLUX_DEFAULT_SESSION_CACHE_TTL",
    "SCHOLAR_FLUX_DEFAULT_RESPONSE_CACHE_TTL",
    "SCHOLAR_FLUX_DEFAULT_PROVIDER",
    "SCHOLAR_FLUX_MONGODB_USERNAME",
    "SCHOLAR_FLUX_MONGODB_PASSWORD",
    "SCHOLAR_FLUX_MONGODB_DATABASE",
    "SCHOLAR_FLUX_MONGODB_COLLECTION",
    "SCHOLAR_FLUX_REDIS_USERNAME",
    "SCHOLAR_FLUX_REDIS_PASSWORD",
    "SCHOLAR_FLUX_CACHE_DIRECTORY",
    "SCHOLAR_FLUX_SESSION_CACHE_DIRECTORY",
    "SCHOLAR_FLUX_SQLALCHEMY_URL",
    "SCHOLAR_FLUX_REDIS_URL",
    "SCHOLAR_FLUX_MONGODB_URL",
    "SCHOLAR_FLUX_LOG_DIRECTORY",
    "SCHOLAR_FLUX_LOG_STREAM",
    "SCHOLAR_FLUX_USE_SESSION_CACHE_ENCRYPTION",
    "SCHOLAR_FLUX_CACHE_SECRET_KEY",
]


def enable_debugging() -> None:
    """Helper function that defines the environment variables needed to enable logging by default in ScholarFlux."""
    os.environ["SCHOLAR_FLUX_LOG_LEVEL"] = "DEBUG"
    os.environ["SCHOLAR_FLUX_ENABLE_LOGGING"] = "TRUE"
    os.environ["SCHOLAR_FLUX_PROPAGATE_LOGS"] = "TRUE"


def prepare_env() -> None:
    """Helper function that temporarily configures env variables needed to enable consistent logging and testing."""
    enable_debugging()
    os.environ["SCHOLAR_FLUX_LOAD_ENV"] = "FALSE"

    for env_var in DISABLE_ENV_LIST:
        os.environ.pop(env_var, None)


def raise_error(exception_type: type[BaseException], message: str | None = None) -> Callable:
    """Helper method for manually raising an error message."""
    return lambda *args, **kwargs: (_ for _ in ()).throw(exception_type(message) if message else exception_type())


@contextmanager
def search_coordinator_mocking_context(
    search_coordinator: "SearchCoordinator",
    page: int | Iterable[int] | None = 1,
    endpoint: str | None = None,
    status_code: int = 200,
    headers: Mapping | None = None,
    json: dict | None = None,
    kwargs: dict[str, Any] | None = None,
) -> Generator[requests_mock.Mocker, None, None]:
    """Context manager that uses the coordinator as well as the response json to mock a response."""
    headers = headers or {"content-type": "application/json"}

    with requests_mock.Mocker() as m:
        page_list = ([] if page is None else [page]) if not isinstance(page, Iterable) else page

        # if page_list is an empty list, no results are mocked
        for p in page_list:
            prepared_search = search_coordinator.api.prepare_search(page=p, endpoint=endpoint)
            m.get(prepared_search.url, headers=headers, status_code=status_code, json=json, **(kwargs or {}))
        yield m


__all__ = ["enable_debugging", "prepare_env", "raise_error", "search_coordinator_mocking_context"]
