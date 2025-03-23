import requests

class APIException(Exception):
    """Base exception for API-related errors."""
    pass

class PermissionException(APIException):
    """Exception raised for permission errors."""
    pass

class RateLimitExceededException(APIException):
    """Exception raised when the API's rate limit is exceeded."""
    pass

class InvalidResponseException(APIException):
    """Exception raised for invalid or unexpected responses from the API."""
    pass

class NotFoundException(APIException):
    """Exception raised when a requested resource is not found."""
    pass

class SearchRequestException(APIException):
    """Exception raised when a requested resource is not found."""
    pass

class SearchAPIException(APIException):
    """Exception raised when the search api fails in retrieing data from APIs ."""
    pass

class RequestFailedException(APIException):
    """Exception raised for failed API requests."""

    def __init__(self, response: requests.Response, *args, **kwargs):
        self.response = response
        self.status_code = response.status_code
        self.error_details = self.extract_error_details(response)

        error_message = f'HTTP error occurred: {response} - Status code: {self.status_code}'

        if self.error_details:
            error_message += f" - Details: {self.error_details}"

        super().__init__(error_message, *args, **kwargs)

    @staticmethod
    def extract_error_details(response: requests.Response) -> str:
        """Extracts detailed error message from response body."""
        try:
            return response.json().get('error', {}).get('message', '')
        except (ValueError, KeyError):
            return ''



class RetryLimitExceededException(APIException):
    """Exception raised when the retry limit is exceeded."""
    pass

class TimeoutException(APIException):
    """Exception raised for request timeouts."""
    pass
