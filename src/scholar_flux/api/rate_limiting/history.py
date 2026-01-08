# /api/rate_limiting/history.py
"""The scholar_flux.api.rate_limiting.history module implements the core dataclasses used for request observability.

These dataclasses provide typed, self-documenting records of retry attempts and applied rate-limiting intervals used
to observe the total number of outbound requests being made, the status of each request, and the intervals waited in
between requests.

Classes:
    HistoryDeque:
        Subclasses the deque to create a bounded, thread-safe record storage for monitoring retry attempts and rate
    RateLimitEvent:
        A basic data class for monitoring the time slept in between requests.
    RetryAttempt:
        A data class used to monitor successive requests to APIs, tracking attempts, timestamps, and request, metadata.

Usage:
    >>> from scholar_flux.api.rate_limiting.history import RetryAttempt, RateLimitEvent
    >>> from scholar_flux.api import RetryHandler, SearchCoordinator
    # Note: Cached Requests will not be recorded since these requests are neither sent nor rate limited.
    >>> coordinator = SearchCoordinator(query = 'Economic Security', provider_name='Crossref', use_cache=True)
    >>> result = coordinator.search_pages(pages = (1, 2))
    >>> # After a request is made...
    >>> for attempt in coordinator.retry_handler.history:
    ...     url = attempt.url.split("?")[0] if attempt.url else attempt.url
    ...     success = "Successful" if attempt.success else "Unsuccessful"
    ...     print(f"Request #{attempt.attempt_number} to {url} at {attempt.timestamp} was {success}.")
    ...     if not attempt.success:
    ...         print(f"    Error Type: {attempt.error}; Message: {attempt.message}; Status Code {attempt.status_code}")
    ...     print('-'*100)

"""
from __future__ import annotations
from collections import deque
from pydantic.dataclasses import dataclass
from dataclasses import asdict
from pydantic import Field
from typing import Optional, ClassVar, Generic, TypeVar, Any
from typing_extensions import Self
from scholar_flux.utils.helpers import generate_iso_timestamp, coerce_int, coerce_str
from scholar_flux.utils import generate_repr, generate_sequence_repr
from scholar_flux.utils.response_protocol import ResponseProtocol
from scholar_flux.api.validators import normalize_url
from scholar_flux import masker
from requests import Response
import re


@dataclass(frozen=True)
class RetryAttempt:
    """Data class used to record initial requests and successive retries made for the retrieval of data from APIs.

    The core methods of the Deque (append, pop, len) are thread-safe and use cpython under the hood. These methods
    are directly inherited and do not require manual thread-locks to ensure type safety.

    To more easily create a new `RetryAttempt`, the `from_response` handles the majority of the complexity of recording
    request attempts on the backend.

    Attributes:
        status_code (Optional[int]): HTTP status code from the response, or None if no response.
        attempt_number (int): The attempt number for the current request (0 for initial, 1+ for retries).
        min_retry_delay (float): Configured minimum retry delay at time of attempt.
        backoff_factor (float): Configured backoff factor at time of attempt.
        success (bool): Whether this attempt resulted in a valid response.
        delay (Optional[float]): Delay (in seconds) applied by the RetryHandler before this attempt.
        duration (Optional[float]): Duration from request execution (including rate limiting) to response retrieval.
        elapsed (Optional[float]): Server response time in seconds (network + processing, excludes client delays).
        timeout (bool): Whether the attempt failed due to a timeout error.
        message (Optional[str]): Error message describing the failure.
        error (Optional[str]): The exception class name (e.g., 'ReadTimeout', 'HTTPError').
        timestamp (Optional[str]): ISO 8601 timestamp when the attempt was recorded.

    Note:
        `duration` also includes the internally rate-limited time taken before a request was sent and can appear
        artificially higher than the total seconds elapsed between when a request was sent and a response received.

    """

    status_code: Optional[int]
    attempt_number: int
    min_retry_delay: float
    backoff_factor: float
    success: bool
    url: Optional[str] = None
    delay: Optional[float] = None
    duration: Optional[float] = None
    elapsed: Optional[float] = None
    timeout: bool = False
    message: Optional[str] = None
    error: Optional[str] = None
    timestamp: str = Field(default_factory=generate_iso_timestamp)

    @classmethod
    def from_response(
        cls,
        response: Optional[Response | ResponseProtocol],
        attempt_number: int,
        min_retry_delay: float,
        backoff_factor: float,
        url: Optional[str] = None,
        delay: Optional[float] = None,
        duration: Optional[float] = None,
        timeout: bool = False,
        message: Optional[str] = None,
        error: Optional[str] = None,
    ) -> Self:
        """Helper method for creating a new RetryAttempt from the provided response.

        Args:
            response (Optional[requests.Response | ResponseProtocol]): The response object from the attempt.
            attempt_number (int): The current attempt number in a sequence of requests (0 for initial, 1+ for retries).
            min_retry_delay (float): The configured minimum retry delay
            backoff_factor (float): The configured multiplier for exponential backoff.
            url (Optional[str]): The Request URL. If None, the URL is extracted from the message when possible.
            delay (Optional[float]): Delay (in seconds) to be applied by the RetryHandler before the next retry attempt.
            duration (Optional[float]): Duration from request execution (including rate limiting) to response retrieval.
            timeout (bool): Whether the attempt failed due to a timeout error.
            message (Optional[str]): Error message describing the failure.
            error (Optional[str]): The name of the exception that was raised.

        Returns:
            RetryAttempt: A retry attempt with relevant fields extracted from the response when available.

        Note:
            - `elapsed` is automatically extracted from `requests.Response.elapsed` when available
            - URL is extracted from timeout error messages matching pattern: `host='...'`
            - `success` is determined by calling `response.raise_for_status()`

        """
        status_code: Optional[int] = None
        success: bool = False
        elapsed: Optional[float] = None
        if isinstance(response, Response) or isinstance(response, ResponseProtocol):
            status_code = coerce_int(response.status_code)
            url = coerce_str(url or response.url)

            elapsed = response.elapsed.total_seconds() if isinstance(response, Response) else None

            try:
                response.raise_for_status()
                success = True
            except Exception as e:
                message = message or str(e)
                error = e.__class__.__name__

        url = cls._extract_url_from_message(message) if url is None else url

        return cls(
            status_code=status_code,
            attempt_number=attempt_number,
            min_retry_delay=min_retry_delay,
            success=success,
            url=url,
            delay=delay,
            duration=duration,
            elapsed=elapsed,
            backoff_factor=backoff_factor,
            timeout=timeout,
            message=message,
            error=error,
        )

    @classmethod
    def _extract_url_from_message(cls, message: Optional[str]) -> Optional[str]:
        """Helper method for extracting the URL from error messages (primarily error timeouts) when not provided."""
        if isinstance(message, str) and (url_match := re.search(r"host='(.*?)'", message)):
            return normalize_url(url_match.group(1))
        return None

    def structure(self, flatten: bool = False, show_value_attributes: bool = True, mask_values: bool = True) -> str:
        """Helper method for showing the structure of the current `RetryAttempt`.

        Args:
            flatten (bool): Whether to flatten the `RetryAttempt` representation into a single line.
            show_value_attributes (bool): Whether to show the attributes of the nested components of the `RetryAttempt`.
            mask_values (bool): Indicates whether sensitive data should be masked if found within a dataclass.

        Returns:
            str: The structure of the current RetryAttempt as a string.

        """
        representation = generate_repr(self, flatten=flatten, show_value_attributes=show_value_attributes)
        return masker.mask_text(representation) if mask_values else representation

    def __repr__(self) -> str:
        """Returns a basic, masked string representation of the current RateLimitEvent for observability."""
        return self.structure(flatten=True, show_value_attributes=True, mask_values=True)


@dataclass(frozen=True)
class RateLimitEvent:
    """Dataclass used to record the interval slept between successive calls/requests for rate limiting observability.

    Attributes:
        interval (float): Duration of the sleep in seconds.
        url (Optional[str]): URL associated with the rate-limited request.
        caller (Optional[str]): Name of the method that triggered the sleep (e.g., 'search', 'wait_since').
        request_delay (Optional[float]): The minimum interval that had to elapse before the request was sent.
        metadata (Optional[dict[str, Any]]): Additional key-value pairs to record as metadata for observability.
        timestamp (str): ISO 8601 timestamp when the sleep was initiated.

    """

    interval: float
    url: Optional[str] = None
    caller: Optional[str] = None
    request_delay: Optional[float] = None
    metadata: Optional[dict[str, Any]] = None
    timestamp: str = Field(default_factory=generate_iso_timestamp)

    @classmethod
    def from_metadata(
        cls,
        interval: float,
        *,
        url: Optional[str] = None,
        caller: Optional[str] = None,
        request_delay: Optional[float] = None,
        **metadata: Any,
    ) -> Self:
        """Helper method for initializing a new RateLimitEvent from a list of known attributes and keyword arguments.

        Attributes:
            interval (float): Duration of the sleep in seconds.
            caller (Optional[str]): Name of the method that triggered the sleep (e.g., 'wait', 'wait_since').
            request_delay (Optional[float]): The minimum interval that had to elapse before the request was sent.
            metadata: (Optional[dict[str, Any]]): Additional key-value pairs to record as metadata for observability.
            timestamp (str): ISO 8601 timestamp when the sleep was initiated.

        """
        return cls(interval=interval, url=url, caller=caller, request_delay=request_delay, metadata=metadata)

    def structure(self, flatten: bool = False, show_value_attributes: bool = True, mask_values: bool = True) -> str:
        """Helper method for showing the structure of the current `RateLimitEvent`.

        Args:
            flatten (bool): Whether to flatten the `RateLimitEvent` representation into a single line.
            show_value_attributes (bool): Whether to the attributes of the nested of the `RateLimitEvent`.
            mask_values (bool): Indicates whether sensitive data should be masked if found within a dataclass.

        Returns:
            str: The structure of the current RateLimitEvent as a string.

        """
        representation = generate_repr(self, flatten=flatten, show_value_attributes=show_value_attributes)
        return masker.mask_text(representation) if mask_values else representation

    def __repr__(self) -> str:
        """Returns a basic, masked string representation of the current RateLimitEvent for observability."""
        return self.structure(flatten=True, show_value_attributes=True, mask_values=True)


T = TypeVar("T", RetryAttempt, RateLimitEvent)


class HistoryDeque(deque, Generic[T]):
    """Deque subclass created as a means of bounded, thread-safe record storage for debugging response history.

    While the core methods of the `HistoryDeque` are nearly identical to the original deque class, this subclass defines
    utility methods for both exporting and clearing events, and when required, resizing the total amount of records
    stored at any given time. As new records are appended to the Deque, the oldest records are dropped to ensure that
    class holds no more than `maxlen` records at one time.

    Because the underlying implementation of the `Deque` generally uses cpython, its core methods are thread-safe
    without additional modification being needed for basic `Deque` operations (`append` and `pop`).

    The additional methods are simple helpers that are added as means of utility when verifying request delays:

    - create: factory method that creates a new typed deque that stores `DEFAULT_MAX_HISTORY` records at one time.
    - export_history: Exports the RetryAttempt or RateLimitEvent classes into a list of dictionaries for debugging
    - clear_history: Clears the deque of all previously stored records
    - modify_history_size: Adjust the total size of the current deque, storing `maxlen` of the most recent records.

    """

    DEFAULT_MAX_HISTORY: ClassVar[int] = 1000

    @classmethod
    def create(
        cls,
        maxlen: Optional[int] = None,
    ) -> Self:
        """Factory function to create a bounded history deque.

        Args:
            maxlen: Maximum number of records to retain. Defaults to DEFAULT_MAX_HISTORY.

        Returns:
            A deque with the specified maximum length.

        """
        return cls(maxlen=maxlen if maxlen is not None else cls.DEFAULT_MAX_HISTORY)

    def export_history(self, mask_values: bool = True) -> list[dict[str, Any]]:
        """Export history records to a list of dictionaries for JSON serialization.

        Args:
            mask_values (bool): Optionally masks values of sensitive data that may appear in the JSON-exported history.

        Returns:
            List of dictionaries suitable for JSON export.

        """
        history_records = (asdict(record) for record in self)
        return [masker.mask_dict(record) for record in history_records] if mask_values else list(history_records)

    def clear_history(self) -> None:
        """Clear the retry attempt history.

        Useful for testing or when starting a new batch of requests.

        """
        self.clear()

    def modify_history_size(self, maxlen: int) -> Self:
        """Helper method allowing for the modification of total number of elements stored within the deque."""
        return self.__class__(self, maxlen=maxlen)

    def structure(
        self,
        flatten: bool = False,
        show_value_attributes: bool = True,
        flatten_nested: bool = True,
        mask_values: bool = True,
    ) -> str:
        """Helper method for creating a string representation of the structure of the current `HistoryDeque`.

        Args:
            flatten (bool): Whether to flatten the `HistoryDeque` representation into a single line.
            show_value_attributes (bool): Whether to show the attributes of recorded elements in the `HistoryDeque`.
            flatten_nested (bool): Flag determining whether to flatten entries to span one line (True by default)
            mask_values (bool): Indicates whether sensitive data should be masked if found within a dataclass.

        Returns:
            str: The structure of the current HistoryDeque as a string.

        """
        representation = generate_sequence_repr(
            self, flatten=flatten, show_value_attributes=show_value_attributes, flatten_nested=flatten_nested
        )
        return masker.mask_text(representation) if mask_values else representation

    def __repr__(self) -> str:
        """Returns and displays a basic, masked representation of the current HistoryDeque for observability."""
        return self.structure(flatten=True, flatten_nested=True, mask_values=True)


__all__ = [
    "HistoryDeque",
    "RetryAttempt",
    "RateLimitEvent",
]
