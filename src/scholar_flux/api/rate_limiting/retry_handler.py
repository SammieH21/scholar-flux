# /api/rate_limiting/retry_handler.py
"""The scholar_flux.api.rate_limiting.retry_handler implements a basic RetryHandler that defines a variable period of
time to wait in between successive unsuccessful requests to the same provider.

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
from typing import Any, Optional, Callable, Mapping

logger = logging.getLogger(__name__)


class RetryHandler:
    """Core class used for determining whether or not to retry failed requests when rate limiting, backoff factors, and
    max backoff when enabled."""

    DEFAULT_VALID_STATUSES = {200}
    DEFAULT_RETRY_STATUSES = {429, 500, 503, 504}
    DEFAULT_RETRY_AFTER_HEADERS = ("retry-after", "x-ratelimit-retry-after")
    DEFAULT_RAISE_ON_ERROR = False

    def __init__(
        self,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
        max_backoff: int | float = 120,
        retry_statuses: Optional[set[int] | list[int]] = None,
        raise_on_error: Optional[bool] = None,
        min_retry_delay: Optional[int | float] = None,
    ):
        """Helper class to send and retry requests of a specific status code. The RetryHandler also dynamically controls
        the degree of rate limiting that occurs upon observing a rate limiting error status code.

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
            request_func:
                The function to send the request.
            validator_func:
                A function that takes a response and returns True if valid.
            sleep_func:
                An optional function used for blocking the next request until a specified duration has passed.
            *args:
                Positional arguments for the request function.
            min_retry_delay:
                The minimum delay in seconds between requests.
            backoff_factor (float):
                Indicates the factor used to adjust when the next request is should be attempted based on past
                unsuccessful attempts.
            max_backoff (int | float):
                Describes the maximum number of seconds to wait before submitting the next request.
            **kwargs: Arbitrary keyword arguments for the request function.

        Returns:
            requests.Response: The response received, or None if no valid response was obtained.

        Raises:
            RequestFailedException: When a request raises an exception for whatever reason
            InvalidResponseException: When the number of retries has been exceeded and self.raise_on_error is True

        """
        attempts = 0

        validator_func = validator_func or self._default_validator_func
        sleep_func = sleep_func or time.sleep

        response = None
        msg = None

        try:
            while attempts <= self.max_retries:
                response = request_func(*args, **kwargs)

                if validator_func(response):
                    break

                if not (
                    isinstance(response, requests.Response) or isinstance(response, ResponseProtocol)
                ) or not self.should_retry(response):
                    msg = "Received an invalid or non-retryable response."
                    self.log_retry_warning(msg)
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
                    sleep_func(delay)
            else:
                msg = "Max retries exceeded without a valid response."
                self.log_retry_warning(msg)

                if self.raise_on_error:
                    raise InvalidResponseException(response, msg)

            logger.debug(
                f"Returning a request of type {type(response)}, status_code={response.status_code if isinstance(response, requests.Response) else None}"
            )
            return response

        except InvalidResponseException:
            raise
        except Exception as e:
            msg = f"A valid response could not be retrieved after {attempts} attempts"
            err = f"{msg}: {e}" if str(e) else f"{msg}."
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
        """Calculate delay for the next retry attempt."""
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
            response: Any response object with headers

        Returns:
            Optional[str]: The unparsed `retry-after` header in seconds, or None if not present

        """
        if isinstance(response, requests.Response) or isinstance(response, ResponseProtocol):
            return cls.extract_retry_after({k: v for k, v in (response.headers or {}).items() if v is not None})
        return None

    @classmethod
    def extract_retry_after(cls, headers: Optional[Mapping[str, Any]], keys: Optional[tuple] = None) -> Optional[str]:
        """Extracts the `retry-after field from dictionary headers if the field exists."""
        candidate_rate_limiter_keys: tuple = keys or cls.DEFAULT_RETRY_AFTER_HEADERS
        value = get_first_available_key(headers or {}, candidate_rate_limiter_keys, case_sensitive=False)
        return value

    @classmethod
    def get_retry_after(cls, response: Optional[requests.Response | ResponseProtocol]) -> Optional[int | float]:
        """Calculates the time that must elapse before the next request is sent according to the headers.

        Args:
            requests.Response object or a (duck-typed) response-like object

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
            int: Delay time in seconds.

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
        """Log an attempt to retry a request."""
        message = f"Retrying in {delay} seconds..."
        if status_code:
            message += f" due to status {status_code}."
        logger.info(message)

    @staticmethod
    def log_retry_warning(message: str) -> None:
        """Log a warning when retries are exhausted or an error occurs."""
        logger.warning(message)

    def __repr__(self) -> str:
        """Helper method to generate a summary of the RetryHandler instance.

        This method will show the name of the class in addition to the values used to create it

        """
        return generate_repr(self)


__all__ = ["RetryHandler"]
