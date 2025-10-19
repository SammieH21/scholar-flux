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
from scholar_flux.utils.repr_utils import generate_repr
from typing import Optional, Callable

logger = logging.getLogger(__name__)


class RetryHandler:
    """Core class used for determining whether or not to retry failed requests when rate limiting, backoff factors, and
    max backoff when enabled."""

    DEFAULT_VALID_STATUSES = {200}
    DEFAULT_RETRY_STATUSES = {429, 500, 503, 504}
    DEFAULT_RAISE_ON_ERROR = False

    def __init__(
        self,
        max_retries: int = 3,
        backoff_factor: float = 0.5,
        max_backoff: int = 120,
        retry_statuses: Optional[set[int] | list[int]] = None,
        raise_on_error: Optional[bool] = None,
    ):
        """Helper class to send and retry requests of a specific status code. The RetryHandler also dynamically controls
        the degree of rate limiting that occurs upon observing a rate limiting error status code.

        Args:
            max_retries (int): indicates how many attempts should be performed before
                               halting retries at retrieving a valid response
            backoff_factor (float): indicates the factor used to adjust when the next request is
                                  should be attempted based on past unsuccessful attempts
            max_backoff (int): describes the maximum number of seconds to wait before submitting
            retry_statuses (Optional[set[int]]):
                Indicates the full list of status codes that should be retried if encountered
            raise_on_error (Optional[bool]): Flag that indicates whether or not to raise an error
                upon encountering an invalid status_code or exception

        """
        self.max_retries = max_retries if max_retries >= 0 else 0
        self.backoff_factor = backoff_factor if backoff_factor >= 0 else 0
        self.max_backoff = max_backoff if max_backoff >= 0 else 0
        self.retry_statuses = retry_statuses if retry_statuses is not None else self.DEFAULT_RETRY_STATUSES
        self.raise_on_error = raise_on_error if raise_on_error is not None else self.DEFAULT_RAISE_ON_ERROR

    def execute_with_retry(
        self,
        request_func: Callable,
        validator_func: Optional[Callable] = None,
        *args,
        **kwargs,
    ) -> Optional[requests.Response | ResponseProtocol]:
        """Sends a request and retries on failure based on predefined criteria and validation function.

        Args:
            request_func: The function to send the request.
            validator_func: A function that takes a response and returns True if valid.
            *args: Positional arguments for the request function.
            **kwargs: Arbitrary keyword arguments for the request function.

        Returns:
            requests.Response: The response received, or None if no valid response was obtained.

        Raises:
            RequestFailedException: When a request raises an exception for whatever reason
            InvalidResponseException: When the number of retries has been exceeded and self.raise_on_error is True

        """
        attempts = 0

        validator_func = validator_func or self._default_validator_func

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

                delay = self.calculate_retry_delay(attempts, response)
                self.log_retry_attempt(
                    delay,
                    (
                        response.status_code
                        if (isinstance(response, requests.Response) or isinstance(response, ResponseProtocol))
                        else None
                    ),
                )
                time.sleep(delay)
                attempts += 1
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
        self, attempt_count: int, response: Optional[requests.Response | ResponseProtocol] = None
    ) -> float:
        """Calculate delay for the next retry attempt."""
        if (
            response is not None
            and (isinstance(response, requests.Response) or isinstance(response, ResponseProtocol))
            and ("Retry-After" in (response.headers or {}) or "retry-after" in (response.headers or {}))
        ):
            value = response.headers.get("Retry-After") or response.headers.get("retry-after")
            retry_after = self.parse_retry_after(value) if value else None
            if isinstance(retry_after, (int, float)) and not retry_after < 0:
                return retry_after

        logger.debug("Defaulting to using 'max_backoff'...")
        return min(self.backoff_factor * (2**attempt_count), self.max_backoff)

    def parse_retry_after(self, retry_after: str) -> Optional[int | float]:
        """Parse the 'Retry-After' header to calculate delay.

        Args:
            retry_after (str): The value of 'Retry-After' header.

        Returns:
            int: Delay time in seconds.

        """
        try:
            return int(retry_after)
        except ValueError:
            logger.debug(f"'Retry-After' is not a valid number: {retry_after}. Attempting to parse as a date..")
        try:
            # Header might be a date
            retry_date = parsedate_to_datetime(retry_after)
            delay = (retry_date - datetime.datetime.now(retry_date.tzinfo)).total_seconds()
            return max(0, int(delay))
        except ValueError:
            logger.debug("Couldn't parse 'Retry-After' as a date.")
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
