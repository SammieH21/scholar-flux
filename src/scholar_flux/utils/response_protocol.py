from __future__ import annotations
from typing import Any, MutableMapping, runtime_checkable, Protocol


@runtime_checkable
class ResponseProtocol(Protocol):
    """
    Protocol for HTTP response objects compatible with both requests.Response, httpx.Response, and other
    response-like classes.

    This protocol defines the common interface shared between popular HTTP client libraries, allowing for
    type-safe interoperability.

    The URL is kept flexible to allow for other types outside of the normal string including basic pydantic
    and httpx type for both httpx and other custom objects.
    """

    status_code: int
    headers: MutableMapping[str, str]
    content: bytes
    url: Any

    # Status and validation methods
    def raise_for_status(self) -> None:
        """Raise an exception for HTTP error status codes."""
        ...
