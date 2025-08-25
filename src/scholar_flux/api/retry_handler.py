from email.utils import parsedate_to_datetime
import time
import requests
import datetime
import logging
from scholar_flux.exceptions import RequestFailedException
from scholar_flux.utils.repr_utils import generate_repr
from typing import Optional, Callable

logger = logging.getLogger(__name__)

class RetryHandler:

    DEFAULT_VALID_STATUSES = {200}
    DEFAULT_RETRY_STATUSES = {429, 503, 504}

    def __init__(self, max_retries: int = 3,
                 backoff_factor: float = 0.5, max_backoff: int =120,
                 retry_statuses: Optional[set[int] | list[int]] = None):

        """
        Helper class to send and retry requests of a specific status code.
        The RetryHandler also dynamically controls the
        degree of rate limiting that occurs upon observing a rate limiting error
        status code.
        Args:
            max_retries (int): indicates how many attempts should be performed before
                               halting retries at retrieving a valid response
            backoff_factor (float): indicates the factor used to adjust when the next request is
                                  should be attempted based on past unsuccessful attempts
        """
        self.max_retries = max_retries if max_retries >= 0 else 0
        self.backoff_factor = backoff_factor
        self.max_backoff = max_backoff
        self.retry_statuses = retry_statuses if retry_statuses is not None else self.DEFAULT_RETRY_STATUSES

    def execute_with_retry(self, request_func: Callable,
                           validator_func: Optional[Callable]=None,
                           *args, **kwargs) -> Optional[requests.Response]:
        """
        Sends a request and retries on failure based on predefined criteria and validation function.

        Args:
            request_func: The function to send the request.
            validator_func: A function that takes a response and returns True if valid.
            *args: Positional arguments for the request function.
            **kwargs: Arbitrary keyword arguments for the request function.

        Returns:
            requests.Response: The response received, or None if no valid response was obtained.
        """
        attempts = 0

        validator_func = validator_func or self._default_validator_func

        response = None

        try:
            while attempts <= self.max_retries:
                response = request_func(*args, **kwargs)

                if validator_func(response):
                    break

                if not isinstance(response, requests.Response) or not self.should_retry(response):
                    self.log_retry_warning("Received an invalid or non-retryable response.")
                    break

                delay = self.calculate_retry_delay(attempts, response)
                self.log_retry_attempt(delay, response.status_code if isinstance(response, requests.Response) else None)
                time.sleep(delay)
                attempts += 1
            else:
                self.log_retry_warning("Max retries exceeded without a valid response.")

            logger.debug(f"Request is a {type(response)}, status_code={response.status_code if isinstance(response, requests.Response) else None}")
            return response
        except Exception as e:
            raise RequestFailedException from e

    @classmethod
    def _default_validator_func(cls,response: requests.Response) -> bool:
        return isinstance(response, requests.Response) and \
                response.status_code in cls.DEFAULT_VALID_STATUSES

    def should_retry(self, response: requests.Response) -> bool:
        """Determine whether the request should be retried."""
        return response.status_code in self.retry_statuses

    def calculate_retry_delay(self, attempt_count: int,
                              response: Optional[requests.Response] = None)->float:
        """Calculate delay for the next retry attempt."""
        if isinstance(response, requests.Response) and 'Retry-After' in response.headers:
            return self.parse_retry_after(response.headers['Retry-After'])
        return min(self.backoff_factor * (2 ** attempt_count), self.max_backoff)

    def parse_retry_after(self, retry_after: str) -> int:
        """
        Parse the 'Retry-After' header to calculate delay.

        Args:
            retry_after (str): The value of 'Retry-After' header.

        Returns:
            int: Delay time in seconds.
        """
        try:
            return int(retry_after)
        except ValueError:
            # Header might be a date
            retry_date = parsedate_to_datetime(retry_after)
            delay = (retry_date - datetime.datetime.now(retry_date.tzinfo)).total_seconds()
            return max(0, int(delay))


    def log_retry_attempt(self, delay: float,
                          status_code: Optional[int]=None) -> None:
        """Log an attempt to retry a request."""
        message = f"Retrying in {delay} seconds..."
        if status_code:
            message += f" due to status {status_code}."
        logger.info(message)

    def log_retry_warning(self, message: str) -> None:
        """Log a warning when retries are exhausted or an error occurs."""
        logger.warning(message)

    def __repr__(self) -> str:
        """
        Helper method to generate a summary of the RetryHandler instance. This method
        will show the name of the class in addition to the values used to create it
        """
        return generate_repr(self)
