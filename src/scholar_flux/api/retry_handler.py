from email.utils import parsedate_to_datetime
import time
import requests
import datetime
import logging
from scholar_flux.exceptions import RequestFailedException

class RetryHandler:

    DEFAULT_VALID_STATUSES = {200}
    DEFAULT_RETRY_STATUSES = {429, 503, 504}

    def __init__(self, max_retries=3, backoff_factor=0.5, max_backoff=120, retry_statuses=None):
        self.max_retries = max_retries if max_retries >= 0 else 0
        self.backoff_factor = backoff_factor
        self.max_backoff = max_backoff
        self.retry_statuses = retry_statuses if retry_statuses is not None else self.DEFAULT_RETRY_STATUSES
        self.logger = logging.getLogger(__name__)

    def execute_with_retry(self, request_func, validator_func=None, *args, **kwargs):
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

        validator_func = validator_func or self._validator_func

        try:
            while attempts <= self.max_retries:
                response = request_func(*args, **kwargs)

                if validator_func(response):
                    return response

                if not response or not self.should_retry(response):
                    self.log_retry_warning("Received an invalid or non-retryable response.")
                    break

                delay = self.calculate_retry_delay(attempts, response)
                self.log_retry_attempt(delay, response.status_code if response else None)
                time.sleep(delay)
                attempts += 1
            self.log_retry_warning("Max retries exceeded without a valid response.")
            return None
        except Exception as e:
            raise RequestFailedException from e

    @classmethod
    def _validator_func(cls,response: requests.Response):
        return response and response.status_code in cls.DEFAULT_VALID_STATUSES

    def should_retry(self, response):
        """Determine whether the request should be retried."""
        return response.status_code in self.retry_statuses

    def calculate_retry_delay(self, attempt_count, response=None):
        """Calculate delay for the next retry attempt."""
        if response and 'Retry-After' in response.headers:
            return self.parse_retry_after(response.headers['Retry-After'])
        return min(self.backoff_factor * (2 ** attempt_count), self.max_backoff)

    def parse_retry_after(self, retry_after):
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


    def log_retry_attempt(self, delay, status_code=None):
        """Log an attempt to retry a request."""
        message = f"Retrying in {delay} seconds..."
        if status_code:
            message += f" due to status {status_code}."
        self.logger.info(message)

    def log_retry_warning(self, message):
        """Log a warning when retries are exhausted or an error occurs."""
        self.logger.warning(message)

