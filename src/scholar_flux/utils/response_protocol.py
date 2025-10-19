# /utils/response_protocol.py
"""The scholar_flux.utils.response_protocol module is used to ensure that responses can be successfully duck-typed and
implemented without favoring a specific client such as `requests` (or by extension, `requests_cache`), `httpx`, or
`asyncio`.

An object is then seen as response-like if it passes the preliminary check of having all of the following attributes:
    - url
    - status_code
    - raise_for_status
    - headers

To ensure compatibility, the scholar_flux.api.ReconstructedResponse class is used for as an adapter throughout the
request retrieval, response processing, and caching processes to ensure that the ResponseProtocol generalizes to
other implementations when not directly using the default `requests` client.

"""
from __future__ import annotations
from typing import Any, MutableMapping, runtime_checkable, Protocol


@runtime_checkable
class ResponseProtocol(Protocol):
    """Protocol for HTTP response objects compatible with both requests.Response, httpx.Response, and other response-
    like classes.

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


__all__ = ["ResponseProtocol"]
