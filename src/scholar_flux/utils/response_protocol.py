# /utils/response_protocol.py
"""The scholar_flux.utils.response_protocol module implements response object duck-typing for API client operations.

The implemented `ResponseProtocol` class and the `is_response_like` function are each implemented to ensure that
responses during API retrieval and processing steps can be successfully duck-typed and validated without favoring
a specific client such as `requests` (or by extension, `requests_cache`), `httpx`, or `aiohttp`.

An object is then seen as response-like if it passes the preliminary check, containing all of the following attributes:
    - url
    - status_code
    - raise_for_status
    - headers

To ensure compatibility, the scholar_flux.api.ReconstructedResponse class is used as an adapter throughout the
request retrieval, response processing, and caching processes to ensure that the ResponseProtocol generalizes to
other implementations when not directly using the default `requests` client.

"""
from __future__ import annotations
from typing import TYPE_CHECKING, Any, runtime_checkable, Protocol, TypeGuard
from requests import Response

if TYPE_CHECKING:
    from collections.abc import MutableMapping


@runtime_checkable
class ResponseProtocol(Protocol):
    """Protocol for HTTP response objects compatible with requests.Response, httpx.Response, and other response classes.

    This protocol defines the common interface shared between popular HTTP client libraries, allowing for type-safe
    interoperability.

    The URL is kept flexible to allow for other types outside of the normal string including basic pydantic and httpx
    type for both httpx and other custom objects.

    """

    status_code: int
    headers: MutableMapping[str, str]
    content: bytes
    url: Any

    # Status and validation methods
    def raise_for_status(self) -> None:
        """Raises an exception for HTTP error status codes."""
        ...


@runtime_checkable
class ResponseSupportsJSONProtocol(ResponseProtocol, Protocol):
    """Extends the `ResponseProtocol` for the identification of response-like objects that support JSON deserialization.

    JSON parsing is supported for python http clients such as `requests` and `httpx`.

    Use this protocol to narrow response types when JSON parsing is required, such as response parsing and the
    extraction of error details for unsuccessful responses.

    """

    def json(self, **kwargs: Any) -> Any:
        """Deserializes response content into JSON format."""
        ...


def is_response_like(response: object) -> TypeGuard[Response | ResponseProtocol]:
    """Identifies whether an object is a response or duck typed response protocol."""
    return isinstance(response, Response | ResponseProtocol)


def response_supports_json(response: object) -> TypeGuard[ResponseSupportsJSONProtocol]:
    """Determines whether the current object is a response-like object that supports JSON content parsing."""
    return isinstance(response, ResponseSupportsJSONProtocol)


__all__ = ["ResponseProtocol", "ResponseSupportsJSONProtocol", "is_response_like", "response_supports_json"]
