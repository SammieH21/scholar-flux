# /api/rate_limiting/retry_handler.py
"""The scholar_flux.api.rate_limiting.retry_handler implements a basic RetryHandler for dynamic request throttling.

This implementation defines a variable period of time to wait in between successive unsuccessful requests to the same
provider.

This class is implemented by default within the `SearchCoordinator` class to verify and retry each request until
successful or the maximum retry limit has been reached.

"""
from email.utils import parsedate_to_datetime
import time
import requests
import datetime
import logging
from scholar_flux.exceptions import RequestFailedException, InvalidResponseException
from scholar_flux.utils.response_protocol import ResponseProtocol
from scholar_flux.utils.helpers import get_first_available_key, parse_iso_timestamp
from scholar_flux.utils.repr_utils import generate_repr
from scholar_flux.api.rate_limiting.history import (
    HistoryDeque,
    RetryAttempt,
)
from typing import Any, Optional, Callable, Mapping

logger = logging.getLogger(__name__)


class RetryHandler:
    """Core class used to send and dynamically retry failed requests with exponential backoff.

    The `RetryHandler` automatically handles HTTP errors (429, 500, 501, 502, 503, 504) by retrying failed requests with
    increasing delays between attempts. Additional status codes can be added to the retry set via
    `RetryHandler.DEFAULT_RETRY_STATUSES.add(<status_code>)`.

    Features:
        - Exponential backoff with configurable parameters
        - Respects Retry-After headers when provided
        - Thread-safe history tracking of all retry attempts
        - Configurable maximum retries and timeout limits

    Example:
        >>> from scholar_flux import SearchCoordinator
        >>> coordinator = SearchCoordinator(query="nutrition", provider_name="plos")
        >>> # Configure retry behavior
        >>> coordinator.retry_handler.max_retries = 5
        >>> coordinator.retry_handler.backoff_factor = 1.0
        >>> # The history is stored at the class level
        >>> coordinator.retry_handler.history.clear_history()
        >>> # Execute search with automatic retries
        >>> result = coordinator.search_page(page=1)
        >>> # Access retry statistics
        >>> print(f"Retry attempts: {len(coordinator.retry_handler.history)}")

    Attributes:
        max_retries (int): Maximum number of retry attempts (default: 3)
        backoff_factor (float): The multiplier used for exponential backoff (default: 0.5)
        max_backoff (float): Maximum delay between retries in seconds (default: 120)
        retry_statuses (set): HTTP status codes that trigger retries (default: {429, 500, 501, 502, 503, 504})
        history (HistoryDeque): Thread-safe storage of all retry attempts

    Note:
        The retry handler is automatically used by SearchCoordinator for all requests. Each parameter is adjusted
        dynamically based on the provider. No manual intervention is required for basic usage.

    """

    DEFAULT_VALID_STATUSES = {200}
    DEFAULT_RETRY_STATUSES = {429, 500, 501, 502, 503, 504}
    DEFAULT_RETRY_AFTER_HEADERS = ("retry-after", "x-ratelimit-retry-after")
    DEFAULT_RAISE_ON_ERROR = False
    history: HistoryDeque[RetryAttempt] = HistoryDeque.create()

    def __init__(
        self,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
        max_backoff: int | float = 120,
        retry_statuses: Optional[set[int] | list[int]] = None,
        raise_on_error: Optional[bool] = None,
        min_retry_delay: Optional[int | float] = None,
    ):
        """Initializes the `RetryHandler` with configurable parameters for dynamically throttling successive requests.

        Args:
            max_retries (int):
                Indicates how many attempts should be performed before halting retries at retrieving a valid response.
            backoff_factor (float):
                Indicates the factor used to adjust when the next request is should be attempted based on past
                unsuccessful attempts.
            max_backoff (int | float):
                Describes the maximum number of seconds to wait before submitting the next request.
            retry_statuses (Optional[set[int]]):
                Indicates the full list of status codes that should be retried if encountered.
            raise_on_error (Optional[bool]):
                A flag that indicates whether or not to raise an error upon encountering an invalid status_code or
                exception.
            min_retry_delay (Optional[int | float]):
                The minimum delay in seconds between requests.

        Note:
            The class-level history deque is a design choice. While RateLimiter instances are designed to be
            stateless. This attribute enables class-level monitoring and allows introspection into how request delays
            are computed. The `HistoryDeque` is thread-safe (uses cpython on the backend) and allows global
            observability which is helpful for debugging, especially in cases where you need to adjust the total amount
            of requests sent within a given interval to avoid 429 errors.

        """
        self.max_retries = max_retries if max_retries >= 0 else 0
        self.backoff_factor = backoff_factor if backoff_factor >= 0 else 0
        self.max_backoff = max_backoff if max_backoff >= 0 else 0
        self.retry_statuses = retry_statuses if retry_statuses is not None else self.DEFAULT_RETRY_STATUSES
        self.raise_on_error = raise_on_error if raise_on_error is not None else self.DEFAULT_RAISE_ON_ERROR
        self.min_retry_delay = min_retry_delay if min_retry_delay and min_retry_delay >= 0 else 0

    def execute_with_retry(
        self,
        request_func: Callable,
        validator_func: Optional[Callable] = None,
        sleep_func: Optional[Callable[[float], None]] = None,
        *args,
        backoff_factor: Optional[int | float] = None,
        max_backoff: Optional[int | float] = None,
        min_retry_delay: Optional[int | float] = None,
        **kwargs,
    ) -> Optional[requests.Response | ResponseProtocol]:
        """Sends a request and retries on failure based on predefined criteria and validation function.

        Args:
            request_func (Callable):
                The function to send the request.
            validator_func (Optional[Callable]):
                A function that takes a response and returns True if valid.
            sleep_func (Optional[Callable[[float], None]]):
                An optional function used for blocking the next request until a specified duration has passed.
            *args:
                Positional arguments for the request function.
            backoff_factor (Optional[int | float]):
                Indicates the factor used to adjust when the next request is should be attempted based on past
                unsuccessful attempts.
            max_backoff (Optional[int | float]):
                Describes the maximum number of seconds to wait before submitting the next request.
            min_retry_delay (Optional[int | float]):
                The minimum delay in seconds between requests.
            **kwargs: Arbitrary keyword arguments for the request function.

        Returns:
            Optional[requests.Response | ResponseProtocol]: The response received, or None if no valid response was obtained.

        Raises:
            RequestFailedException: When a request raises an exception for whatever reason.
            TimeoutError: When a request times out during response retrieval.
            InvalidResponseException: When the number of retries has been exceeded and self.raise_on_error is True.

        """
        attempts = 0

        validator_func = validator_func or self._default_validator_func
        sleep_func = sleep_func or time.sleep
        min_retry_delay = min_retry_delay or self.min_retry_delay
        backoff_factor = backoff_factor or self.backoff_factor

        response = None
        msg = None
        request_time = None
        retrieval_time = None
        duration = None
        delay: Optional[float] = None

        try:
            while attempts <= self.max_retries:
                request_time = time.time()
                response = request_func(*args, **kwargs)
                retrieval_time = time.time()
                duration = retrieval_time - request_time

                if validator_func(response):
                    self._record_attempt(
                        response=response,
                        min_retry_delay=min_retry_delay,
                        backoff_factor=backoff_factor,
                        attempt_number=attempts,
                        duration=duration,
                    )
                    break

                if not (
                    isinstance(response, requests.Response) or isinstance(response, ResponseProtocol)
                ) or not self.should_retry(response):
                    msg = "Received an invalid or non-retryable response."
                    self.log_retry_warning(msg)
                    self._record_attempt(
                        response=response,
                        min_retry_delay=min_retry_delay,
                        backoff_factor=backoff_factor,
                        attempt_number=attempts,
                        duration=duration,
                    )
                    if self.raise_on_error:
                        raise InvalidResponseException(response, msg)
                    break

                attempts += 1
                if attempts <= self.max_retries:
                    delay = self.calculate_retry_delay(attempts, response, min_retry_delay, backoff_factor, max_backoff)
                    self.log_retry_attempt(
                        delay,
                        (
                            response.status_code
                            if (isinstance(response, requests.Response) or isinstance(response, ResponseProtocol))
                            else None
                        ),
                    )
                    self._record_attempt(
                        response=response,
                        delay=delay,
                        min_retry_delay=min_retry_delay,
                        backoff_factor=backoff_factor,
                        attempt_number=attempts - 1,
                        duration=duration,
                    )
                    sleep_func(delay)
            else:
                msg = "Max retries exceeded without a valid response."
                self.log_retry_warning(msg)

                if self.raise_on_error:
                    raise InvalidResponseException(response, msg)

            current_status_code = response.status_code if isinstance(response, requests.Response) else None
            logger.debug(f"Returning a request of type {type(response)}, status_code={current_status_code}")
            return response
        except (TimeoutError, requests.exceptions.Timeout) as e:
            timeout_time = time.time()
            duration = timeout_time - request_time if request_time else None
            self._record_attempt(
                min_retry_delay=min_retry_delay,
                backoff_factor=backoff_factor,
                attempt_number=attempts,
                duration=duration,
                timeout=True,
                error=e.__class__.__name__,
                message=str(e),
            )
            raise
        except InvalidResponseException:
            raise
        except Exception as e:
            msg = f"A valid response could not be retrieved after {attempts} attempts"
            err = f"{msg}: {e}" if str(e) else f"{msg}."

            # Note: Avoid recording an attempt here: Errors are propagated and recorded in an ErrorResponse or NonResponse.
            # Errors are recorded at the level of the SearchCoordinator instead.
            raise RequestFailedException(err) from e

    @classmethod
    def _default_validator_func(cls, response: requests.Response | ResponseProtocol) -> bool:
        """Defines a basic default validator that verifies type and status code.

        It evaluates:     1) Whether the `response` is a
        requests.Response object or a (duck-typed) response-like object
        based        on whether it evaluates as a ResponseProtocol.
        2) Whether the response status code is in the list of valid
        statuses: `RetryHandler.DEFAULT_VALID_STATUSES`

        """
        return (
            isinstance(response, requests.Response) or isinstance(response, ResponseProtocol)
        ) and response.status_code in cls.DEFAULT_VALID_STATUSES

    def should_retry(self, response: requests.Response | ResponseProtocol) -> bool:
        """Determine whether the request should be retried."""
        return response.status_code in self.retry_statuses

    def calculate_retry_delay(
        self,
        attempt_count: int,
        response: Optional[requests.Response | ResponseProtocol] = None,
        min_retry_delay: Optional[int | float] = None,
        backoff_factor: Optional[int | float] = None,
        max_backoff: Optional[int | float] = None,
    ) -> int | float:
        """Calculates the delay in seconds to wait before the next retry attempt.

        Args:
            attempt_count (int): The number of attempts made so far.
            response (Optional[requests.Response | ResponseProtocol]): The response object from the last attempt.
            min_retry_delay (Optional[int | float]): The minimum delay in seconds between requests.
            backoff_factor (Optional[int | float]): The factor used to adjust the delay.
            max_backoff (Optional[int | float]): The maximum delay in seconds between requests.

        Returns:
            int | float: The delay in seconds for the next retry attempt.

        """
        min_retry_delay = min_retry_delay if isinstance(min_retry_delay, (int, float)) else self.min_retry_delay
        backoff_factor = backoff_factor if isinstance(backoff_factor, (int, float)) else self.backoff_factor
        max_backoff = max_backoff if isinstance(max_backoff, (int, float)) else self.max_backoff

        retry_after = self.get_retry_after(response)

        if retry_after is not None:
            return retry_after

        logger.debug("Defaulting to using 'max_backoff'...")
        return min_retry_delay + min(backoff_factor * (2**attempt_count), max_backoff)

    @classmethod
    def extract_retry_after_from_response(
        cls, response: Optional[requests.Response | ResponseProtocol]
    ) -> Optional[str]:
        """Extracts and parses retry-after delay from any response type.

        This method handles both raw responses (Response/ResponseProtocol) and processed responses
        (ProcessedResponse/ErrorResponse), making it the single entry point for retry-after extraction.

        Args:
            response (Optional[requests.Response | ResponseProtocol]): Any response object with headers

        Returns:
            Optional[str]: The unparsed `retry-after` header in seconds, or None if not present

        """
        if isinstance(response, requests.Response) or isinstance(response, ResponseProtocol):
            return cls.extract_retry_after({k: v for k, v in (response.headers or {}).items() if v is not None})
        return None

    @classmethod
    def extract_retry_after(cls, headers: Optional[Mapping[str, Any]], keys: Optional[tuple] = None) -> Optional[str]:
        """Extracts the `retry-after field from dictionary headers if the field exists.

        Args:
            headers (Optional[Mapping[str, Any]]): A headers dictionary or mapping to extract the retry-after field from
            keys (Optional[tuple]): The keys to look for in the headers. (case insensitive)

        Returns:
            Optional[str]: The retry-after field value, or None if not present.

        """
        candidate_rate_limiter_keys: tuple = keys or cls.DEFAULT_RETRY_AFTER_HEADERS
        value = get_first_available_key(headers or {}, candidate_rate_limiter_keys, case_sensitive=False)
        return value

    @classmethod
    def get_retry_after(cls, response: Optional[requests.Response | ResponseProtocol]) -> Optional[int | float]:
        """Calculates the time that must elapse before the next request is sent according to the headers.

        Args:
            response (requests.Response | ResponseProtocol): The response object from the last attempt.

        Returns:
            Optional[float]: Indicates the number of seconds that must elapse before the next request is sent.

        """
        value = cls.extract_retry_after_from_response(response)
        retry_after = cls.parse_retry_after(value) if value is not None else None
        return retry_after

    @classmethod
    def _parse_retry_after_date(cls, retry_after: str) -> datetime.datetime:
        """Parses the retry-after date as a datetime when possible and returns None otherwise."""
        # Header might be a date
        retry_date = parse_iso_timestamp(retry_after) or parsedate_to_datetime(retry_after)
        return retry_date

    @classmethod
    def parse_retry_after(cls, retry_after: Optional[str]) -> Optional[int | float]:
        """Parse the 'Retry-After' header to calculate delay.

        Args:
            retry_after (str): The value of 'Retry-After' header.

        Returns:
            Optional[int | float]: The total delay in seconds parsed from the response field if available.

        """
        if retry_after is None:
            return None

        try:
            return int(retry_after)
        except (ValueError, TypeError):
            logger.debug(f"'Retry-After' is not a valid number: {retry_after}. Attempting to parse as a date..")
        try:
            # Header might be a date
            retry_date = cls._parse_retry_after_date(retry_after)
            delay = (retry_date - datetime.datetime.now(retry_date.tzinfo)).total_seconds()
            return max(0, int(delay))
        except (ValueError, TypeError) as e:
            logger.debug(f"Couldn't parse 'Retry-After' as a date: {e}")
        return None

    def log_retry_attempt(self, delay: float, status_code: Optional[int] = None) -> None:
        """Log an attempt to retry a request.

        Args:
            delay (float): The delay in seconds before the next retry attempt.
            status_code (Optional[int]): The status code of the response that triggered the retry.

        """
        message = f"Retrying in {delay} seconds..."
        if status_code:
            message += f" due to status {status_code}."
        logger.info(message)

    @staticmethod
    def log_retry_warning(message: str) -> None:
        """Log a warning when retries are exhausted or an error occurs.

        Args:
            message (str): The warning message to log.

        """
        logger.warning(message)

    def _record_attempt(
        self,
        min_retry_delay: float,
        backoff_factor: float,
        attempt_number: int,
        response: Optional[requests.Response | ResponseProtocol] = None,
        delay: Optional[float] = None,
        duration: Optional[float] = None,
        timeout: bool = False,
        message: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        """Record a retry attempt to the history deque.

        Args:
            min_retry_delay (float): The configured minimum retry delay.
            backoff_factor (float): The configured multiplier for exponential backoff.
            attempt_number (int): Which attempt this was (0 for initial, 1+ for retries).
            response (Optional[requests.Response | ResponseProtocol]): The response object from the attempt.
            delay (Optional[float]): The delay in seconds to be applied before the next retry attempt.
            duration (Optional[float]): Total seconds from request was sent and when a response/timeout occurred
            timeout (bool): Whether the attempt failed due to a timeout error.
            message (Optional[str]): Error message describing the failure.
            error (Optional[str]): The exception instance that was raised.

        """
        attempt = RetryAttempt.from_response(
            response=response,
            attempt_number=attempt_number,
            min_retry_delay=min_retry_delay,
            backoff_factor=backoff_factor,
            delay=delay,
            duration=duration,
            timeout=timeout,
            message=message,
            error=error,
        )
        self.history.append(attempt)

    @classmethod
    def resize_history(cls, maxlen: int) -> None:
        """Resize the global history deque, preserving existing records up to the new limit.

        Args:
            maxlen (int): The new maximum length of the history deque.

        """
        cls.history = cls.history.modify_history_size(maxlen)

    def __repr__(self) -> str:
        """Helper method to generate a summary of the RetryHandler instance.

        This method will show the name of the class in addition to the values used to create it

        """
        return generate_repr(self)


__all__ = ["RetryHandler"]
