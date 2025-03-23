from email.utils import parsedate_to_datetime
import time
import requests
import datetime
import logging


class RetryHandler:

    DEFAULT_RETRY_STATUSES = {429, 503, 504}

    def __init__(self, max_retries=3, backoff_factor=0.5, max_backoff=120, retry_statuses=None):
        self.max_retries = max_retries
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
        retries = 0
        while retries <= self.max_retries:
            response = request_func(*args, **kwargs)

            if validator_func(response):
                return response

            if not response or not self.should_retry(response):
                self.log_retry_warning("Received an invalid or non-retryable response.")
                break

            delay = self.calculate_retry_delay(retries, response)
            self.log_retry_attempt(delay, response.status_code if response else None)
            time.sleep(delay)
            retries += 1

        self.log_retry_warning("Max retries exceeded without a valid response.")
        return None

    
    def should_retry(self, response):
        """Determine whether the request should be retried."""
        return response.status_code in self.retry_statuses
        
    def calculate_retry_delay(self, retry_count, response=None):
        """Calculate delay for the next retry attempt."""
        if response and 'Retry-After' in response.headers:
            return self.parse_retry_after(response.headers['Retry-After'])
        return min(self.backoff_factor * (2 ** retry_count), self.max_backoff)

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
        
        
    # def execute_with_retry(self, request_func, **kwargs):
    #     attempt = 0
    #     while attempt < self.max_retries:
    #         response = request_func(*args, **kwargs)
    #         is_valid, error_info = ResponseValidator.validate_response(response)
            
    #         if is_valid:
    #             return response  # Successful response
    #         elif error_info['retry_after']:
    #             retry_delay = error_info['retry_after']
    #         else:
    #             retry_delay = self.default_retry_delay
            
    #         attempt += 1
    #         time.sleep(retry_delay)
    #         retry_delay *= 2  # Exponential back-off
    #         APIErrorLogger.log_error(response, additional_info=f"Attempt {attempt} failed")
            
    #     logger.error(f"Request failed after {self.max_retries} attempts.")
    #     return response  # Return last attempt
    

    # def execute_with_retry(self, request_func, *args,**kwargs):
    #     """
    #     Sends a request and retries on failure based on predefined criteria.

    #     Args:
    #         **kwargs: Arbitrary keyword arguments that your request function takes.

    #     Returns:
    #         requests.Response: The response received.
    #     """
    #     retries = 0
    #     while retries <= self.max_retries:
    #         response = request_func(*args, **kwargs)
    #         if response.status_code not in self.retry_statuses:
    #             break    # Successful request or non-retry status code
    #         delay = self.get_retry_delay(response, retries)
    #         if delay is None:  # No delay means no more retries
    #             self.logger.warning("Max retries exceeded without success.")
    #             break
    #         self.logger.info(f"Retrying in {delay} seconds...")
    #         time.sleep(delay)
    #         retries += 1
    #     return response
    
#  def get_retry_delay(self, response, current_retry):
#         """
#         Calculates the delay for the next retry attempt.

#         Args:
#             response (requests.Response): The response received from the server.
#             current_retry (int): The current retry attempt number.

#         Returns:
#             int or None: Delay time in seconds for the next retry, or None if no retry should be attempted.
#         """
#         # Check for 'Retry-After' header in the response
#         if 'Retry-After' in response.headers:
#             retry_after = response.headers['Retry-After']
#             return self.parse_retry_after(retry_after)
