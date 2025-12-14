# /exceptions/api_exceptions.py
"""Implements exceptions involving the creation of requests and retrieval of responses from API Providers."""
import requests
from json import JSONDecodeError
from typing import Optional
import logging
from scholar_flux.utils.response_protocol import ResponseProtocol

logger = logging.getLogger(__name__)


class APIException(Exception):
    """Base exception for API-related errors."""

    pass


class MissingAPIKeyException(ValueError):
    """Exception raised when a blank string is provided yet invalid."""

    pass


class MissingAPISpecificParameterException(ValueError):
    """Exception raised when an API specific parameter is required but not provided in the config."""

    pass


class MissingProviderException(ValueError):
    """Exception raised when an API specific parameter is required but not provided in the config."""

    pass


class MissingResponseException(ValueError):
    """Exception raised when a response or response-like objects is required but not provided."""

    pass


class NoRecordsAvailableException(APIException):
    """Exception raised when an operation depends on the presence of records but none exist."""

    pass


class PermissionException(APIException):
    """Exception raised for permission errors."""

    pass


class RateLimitExceededException(APIException):
    """Exception raised when the API's rate limit is exceeded."""

    pass


class RequestFailedException(APIException):
    """Exception raised for failed API requests."""

    pass


class RequestCreationException(APIException):
    """Exception raised when the preparation of an API request fails."""


class RecordNormalizationException(APIException):
    """Exception raised when the normalization of a response record cannot be completed."""


class NotFoundException(APIException):
    """Exception raised when a requested resource is not found."""

    pass


class QueryValidationException(APIException):
    """Exception raised when a requested resource is not found."""

    pass


class SearchRequestException(APIException):
    """Exception raised when a requested resource is not found."""

    pass


class SearchAPIException(APIException):
    """Exception raised when the search api fails in retrying data from APIs ."""

    pass


class APIParameterException(APIException):
    """Exception raised for API Parameter-related errors."""

    pass


class RequestCacheException(APIException):
    """Exception raised for API request-cache related errors."""

    pass


class InvalidResponseStructureException(APIException):
    """Exception raised on when encountering an non response/response-like object when a valid response was expected."""

    pass


class InvalidResponseReconstructionException(InvalidResponseStructureException):
    """Exception raised on the attempted creation of a ReconstructedResponse if an exception is encountered."""

    pass


class InvalidResponseException(RequestFailedException):
    """Exception raised for invalid responses from the API."""

    def __init__(self, response: Optional[requests.Response | ResponseProtocol] = None, *args, **kwargs):
        """Initializes the `InvalidResponseException` class with a response or response-like parameter for logging."""

        self.response: Optional[requests.Response | ResponseProtocol] = (
            response if (isinstance(response, requests.Response) or isinstance(response, ResponseProtocol)) else None
        )
        self.error_details: str = self.extract_error_details(self.response) if self.response is not None else ""

        if self.response is not None:
            error_message = f"HTTP error occurred: {response} - Status code: {self.response.status_code}."

            if self.error_details:
                error_message += f" Details: {self.error_details}"
        else:
            error_message = f"An error occurred when making the request - Received a nonresponse: {type(response)}"

        logger.error(error_message)
        super().__init__(error_message, *args, **kwargs)

    @staticmethod
    def extract_error_details(response: requests.Response | ResponseProtocol) -> str:
        """Extracts detailed error message from response body."""
        try:
            return response.json().get("error", {}).get("message", "")  # type: ignore
        except (ValueError, KeyError, AttributeError, JSONDecodeError):
            return ""


class RetryLimitExceededException(APIException):
    """Exception raised when the retry limit is exceeded."""

    pass


class TimeoutException(APIException):
    """Exception raised for request timeouts."""

    pass


__all__ = [
    "APIException",
    "MissingAPIKeyException",
    "MissingAPISpecificParameterException",
    "MissingProviderException",
    "MissingResponseException",
    "NoRecordsAvailableException",
    "PermissionException",
    "InvalidResponseException",
    "NotFoundException",
    "SearchAPIException",
    "SearchRequestException",
    "RequestCreationException",
    "RequestFailedException",
    "RateLimitExceededException",
    "RetryLimitExceededException",
    "TimeoutException",
    "APIParameterException",
    "RequestCacheException",
    "InvalidResponseStructureException",
    "InvalidResponseReconstructionException",
    "QueryValidationException",
]
