# /exceptions/api_exceptions.py
"""Implements exceptions involving the creation of requests and retrieval of responses from API Providers."""
import requests
from json import JSONDecodeError
from typing import Any
import logging
from scholar_flux.utils.response_protocol import ResponseProtocol, response_supports_json
from scholar_flux.utils.helpers import get_nested_data, as_str

logger = logging.getLogger(__name__)


class APIException(Exception):
    """Base exception for API-related errors."""


class MissingAPIKeyException(ValueError):
    """Exception raised when a blank string is provided yet invalid."""


class MissingAPISpecificParameterException(ValueError):
    """Exception raised when an API specific parameter is required but not provided in the config."""


class MissingProviderException(ValueError):
    """Exception raised when the specification of a provider is required but not provided in the config."""


class MissingResponseException(ValueError):
    """Exception raised when a response or response-like object is required but not provided."""


class NoRecordsAvailableException(APIException):
    """Exception raised when an operation depends on the presence of records but none exist."""


class RateLimitExceededException(APIException):
    """Exception raised when the API's rate limit is exceeded."""


class RequestFailedException(APIException):
    """Exception raised for failed API requests."""

    @classmethod
    def extract_error_details(cls, response: requests.Response | ResponseProtocol) -> str:
        """Extracts detailed error message from response body."""
        try:
            json_data: dict[str, Any] = response.json() if response_supports_json(response) else {}
            error_details = get_nested_data(json_data, "error.message")
            return as_str(error_details) if error_details else ""
        except (ValueError, KeyError, AttributeError, JSONDecodeError):
            return ""


class PageUnavailableFromCacheException(RequestFailedException):
    """Exception raised when a valid response cannot be retrieved from the session cache."""

    def __init__(self, *args: Any, message: str = "", **kwargs: Any) -> None:
        """Initializes the `PageUnavailableFromCacheException` class with a response or response-like parameter."""
        self.message = f"{message}" or ""
        super().__init__(self.message, *args, **kwargs)

    @property
    def response(self) -> None:
        """Added for interface compatibility."""
        return None

    @property
    def error_details(self) -> str:
        """Added for interface compatibility."""
        return ""


class RequestCreationException(APIException):
    """Exception raised when the preparation of an API request fails."""


class RecordNormalizationException(APIException):
    """Exception raised when the normalization of a response record cannot be completed."""


class QueryValidationException(APIException):
    """Exception raised when a requested resource is not found."""


class APIParameterException(APIException):
    """Exception raised for API Parameter-related errors."""


class APIKeyValidationException(APIParameterException):
    """Exception raised for API key validation-related errors."""


class RequestCacheException(APIException):
    """Exception raised for API request-cache related errors."""


class InvalidResponseStructureException(APIException):
    """Exception raised when encountering a non-response/response-like object where a valid response is expected."""


class InvalidResponseReconstructionException(InvalidResponseStructureException):
    """Exception raised on the attempted creation of a ReconstructedResponse if an exception is encountered."""


class RetryAfterDelayExceededException(RequestFailedException):
    """Exception raised when a Retry-After field from a rate limited (429) response exceeds the user-specified limit."""

    def __init__(
        self, response: requests.Response | ResponseProtocol | None, *args: Any, message: str = "", **kwargs: Any
    ) -> None:
        """Initializes the `RetryAfterDelayExceededException` class with a response or response-like parameter."""
        self.response: requests.Response | ResponseProtocol | None = response
        self.error_details: str = self.extract_error_details(response) if response is not None else ""
        self.message = f"{message}: {self.error_details}" if self.error_details else message
        super().__init__(self.message, *args, **kwargs)


class InvalidResponseException(RequestFailedException):
    """Exception raised for invalid responses from the API."""

    def __init__(self, response: requests.Response | ResponseProtocol | None = None, *args: Any, **kwargs: Any) -> None:
        """Initializes the `InvalidResponseException` class with a response or response-like parameter."""

        self.response: requests.Response | ResponseProtocol | None = (
            response if (isinstance(response, requests.Response) or isinstance(response, ResponseProtocol)) else None
        )
        self.error_details: str = self.extract_error_details(response) if response is not None else ""

        if response is not None:
            error_message = f"HTTP error occurred: {response} - Status code: {response.status_code}."

            if self.error_details:
                error_message += f" Details: {self.error_details}"
        else:
            error_message = f"An error occurred when making the request - Received a nonresponse: {type(response)}"

        self.message = error_message

        super().__init__(self.message, *args, **kwargs)


class RetryLimitExceededException(APIException):
    """Exception raised when the retry limit is exceeded."""


__all__ = [
    "APIException",
    "MissingAPIKeyException",
    "MissingAPISpecificParameterException",
    "MissingProviderException",
    "MissingResponseException",
    "APIKeyValidationException",
    "NoRecordsAvailableException",
    "InvalidResponseException",
    "RetryAfterDelayExceededException",
    "RequestCreationException",
    "RequestFailedException",
    "PageUnavailableFromCacheException",
    "RateLimitExceededException",
    "RetryLimitExceededException",
    "APIParameterException",
    "RequestCacheException",
    "InvalidResponseStructureException",
    "InvalidResponseReconstructionException",
    "QueryValidationException",
]
