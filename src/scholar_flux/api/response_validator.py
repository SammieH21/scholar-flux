# /api/response_validator.py
"""The scholar_flux.api.response_validator module implements a basic ResponseValidator that is used for preliminary
response validation to determine whether received responses are valid and successful.

This class is used by default in SearchCoordinators to determine whether to proceed with response processing.

"""
import logging
import requests
from scholar_flux.exceptions.api_exceptions import (
    InvalidResponseException,
    InvalidResponseStructureException,
    RequestFailedException,
)
from typing import Any, Mapping, Optional
from typing_extensions import TypeGuard
from scholar_flux.utils.response_protocol import ResponseProtocol, is_response_like
from scholar_flux.utils.repr_utils import generate_repr
from scholar_flux.api.validators import validate_url

logger = logging.getLogger(__name__)


class ResponseValidator:
    """Helper class that serves as an initial response validation step to ensure that, in custom retry handling, the
    basic structure of a response can be validated to determine whether or not to retry the response retrieval process.

    The ResponseValidator implements class methods that are simple tools that return boolean values
    (True/False) when response or response-like objects do not contain the required structure and
    raise errors when encountering non-response objects or when `raise_on_error = True` otherwise.

    The ResponseValidator also contains helpers for the validation of both processed responses and responses
    that are reconstructed after storage and deserialization.

    Example:
        >>> from scholar_flux.api import ResponseValidator, ReconstructedResponse
        >>> mock_success_response = ReconstructedResponse.build(status_code = 200,
        >>>                                                     json = {'response': 'success'},
        >>>                                                     url = "https://an-example-url.com",
        >>>                                                     headers={'Content-Type': 'application/json'}
        >>>                                                     )
        >>> ResponseValidator.validate_response(mock_success_response) is True
        >>> ResponseValidator.validate_content(mock_success_response) is True

    """

    @classmethod
    def validate_response(cls, response: requests.Response | ResponseProtocol, *, raise_on_error: bool = False) -> bool:
        """Validates HTTP responses by verifying first whether the object is a Response or follows a ResponseProtocol.
        For valid response or response- like objects, the status code is verified, returning False for 400 and 500 level
        validation errors when `raise_on_error=False`. If `raise_on_error` is set to True, an error is raised instead.

        Note that a ResponseProtocol duck-types and verifies that each of a minimal set of attributes and/or properties
        can be found within the current response.

        In the scholar_flux retrieval step, this validator verifies that the response received is a valid response.

        Args:
            response: (requests.Response | ResponseProtocol): The HTTP response object to validate
            raise_on_error (bool): If True, raises InvalidResponseException on error for invalid response status codes

        Returns:
            True if valid, False otherwise

        Raises:
            InvalidResponseException: If response is invalid and raise_on_error is True
            RequestFailedException: If an exception occurs during response validation due to missing or incorrect types

        """
        try:
            if not is_response_like(response):
                raise TypeError(
                    f"The response is not a valid response or response-like object, Received type: {type(response)}"
                )

            response.raise_for_status()
            logger.debug("Successfully received response from %s", response.url)
            return True
        except requests.HTTPError as e:
            logger.error(f"Response validation failed. {e}")
            if raise_on_error:
                raise InvalidResponseException(response, e)
        except Exception as e:
            logger.error(f"Response validation failed. {e}")
            raise RequestFailedException(e)
        return False

    @classmethod
    def validate_content(
        cls,
        response: requests.Response | ResponseProtocol,
        expected_format: str = "application/json",
        *,
        raise_on_error: bool = False,
    ) -> bool:
        """Validates the response content type.

        Args:
            response (requests.Response | ResponseProtocol): The HTTP response or response-like object to check.
            expected_format (str): The expected content type substring (e.g., "application/json").
            raise_on_error (bool): If True, raises InvalidResponseException on mismatch.

        Returns:
            bool: True if the content type matches, False otherwise.

        Raises:
            InvalidResponseException: If the content type does not match and raise_on_error is True.

        """
        content_type = (response.headers or {}).get("Content-Type", "")

        if expected_format in content_type:
            return True

        logger.warning(f"Content type validation failed: received '{content_type}', and expected '{expected_format}'")

        if raise_on_error:
            raise InvalidResponseException(
                response,
                f"Invalid Response format: received '{content_type}', and expected '{expected_format}'",
            )

        return False

    @classmethod
    def validate_response_like(cls, response: object) -> TypeGuard[requests.Response | ResponseProtocol]:
        """Validates that an object is a response or a duck typed ResponseProtocol, raising an error if invalid.

        Args:
            response (object): An object to verify as a response or response-like object

        Returns:
            TypeGuard[requests.Response | ResponseProtocol]:
                True when the received object is a requests.Response or a ResponseProtocol.

        Raises:
            InvalidResponseStructureException:
                Raised when the object is not a response-like object.

        """
        if not is_response_like(response):
            raise InvalidResponseStructureException(
                f"The current class of type {type(response)} is not a response or response-like object."
            )
        return True

    @classmethod
    def validate_response_structure(
        cls, response: requests.Response | ResponseProtocol, raise_on_error: bool = True
    ) -> TypeGuard[requests.Response | ResponseProtocol]:
        """Raises an error if a response object does not contain valid properties expected of a response. If the
        response validation is successful, True is returned, indicating that the value is a valid ResponseLike object.

        Args:
            response (requests.Response | ResponseProtocol): The response or response-like object to validate.
            raise_on_error (bool):
                Flag indicating whether an InvalidResponseStructureException should be raised for objects with invalid
                structures (True by default).

        Returns:
            TypeGuard[requests.Response | ResponseProtocol]:
                True when the received object is a requests.Response or a ResponseProtocol.

        Raises:
            InvalidResponseStructureException:
                Raised when the object is not a response-like object or if at least one field is determined to be
                invalid and unexpected of a response-like object.

        """
        invalid_fields = cls.identify_invalid_fields(response)
        if invalid_fields and raise_on_error:
            raise InvalidResponseStructureException(f"The following fields are invalid: {invalid_fields}")
        return not invalid_fields

    @classmethod
    def is_valid_response_structure(cls, response: object) -> TypeGuard[ResponseProtocol]:
        """Validates whether each of the core components of a response are populated with the correct response types.

        The following properties that refer back to the original response should be available:

            1. status_code: (int)
            2. reason: string
            3. headers: dictionary
            4. content: bytes
            5. url: string or URL-like field

        Args:
            response (object): An object to evaluate as a response or response-like object.

        Returns:
            TypeGuard[ResponseProtocol]:
                True if all core response fields are valid, False otherwise.

        """
        return is_response_like(response) and cls.validate_response_structure(response, raise_on_error=False)

    @classmethod
    def identify_invalid_keywords(
        cls,
        status_code: Optional[object] = None,
        url: Optional[object] = None,
        reason: Optional[object] = None,
        content: Optional[object] = None,
        headers: Optional[object] = None,
    ) -> dict[str, object]:
        """Validates response field keyword arguments, indicating those that contain invalid values.

        Args:
            status_code (Optional[object]): The status code to validate (expected: int 100-599).
            url (Optional[object]): The URL to validate (should be a valid url).
            reason (Optional[object]): The reason string to validate (should be a string).
            content (Optional[object]): The content to validate (should be a bytes field).
            headers (Optional[object]): The headers to validate (should be a mapping with string-typed keys).

        Returns:
            dict[str, object]: A dictionary containing each invalid field as a key and its assigned value.

        """
        # will hold the full list of all invalid fields and respective values
        invalid_fields: dict[str, Any] = {}

        if not cls.is_valid_status_code(status_code):
            invalid_fields["status_code"] = status_code
        if not cls.is_valid_url(url):
            invalid_fields["url"] = url
        if not cls.is_valid_reason(reason):
            invalid_fields["reason"] = reason
        if not cls.is_valid_content(content):
            invalid_fields["content"] = content
        if not cls.is_valid_headers(headers):
            invalid_fields["headers"] = headers
        return invalid_fields

    @classmethod
    def identify_invalid_fields(cls, response: requests.Response | ResponseProtocol) -> dict[str, Any]:
        """Helper class method for identifying invalid fields within a response.

        This class iteratively validates the complete list of all invalid fields that populate the current response.

        If any invalid fields exist, the method returns a dictionary of each field and its corresponding value.

        Args:
            response (requests.Response | ResponseProtocol):
                A response or response-like object to check for the presence of invalid values.

        Returns:
            (dict[str, Any]): A dictionary containing each invalid field as keys and their assigned values

        """
        cls.validate_response_like(response)

        # in classes such as httpx, reason might instead be reason_phrase for instance:
        reason = getattr(response, "reason", None) or getattr(response, "reason_phrase", None)

        return cls.identify_invalid_keywords(
            status_code=response.status_code,
            url=response.url,
            reason=reason,
            content=response.content,
            headers=response.headers,
        )

    @classmethod
    def is_valid_status_code(cls, status_code: object) -> TypeGuard[int]:
        """Validates whether the status_code is a valid integer between 100-599."""
        return isinstance(status_code, int) and 100 <= status_code < 600

    @classmethod
    def is_valid_url(cls, url: object) -> TypeGuard[str]:
        """Validates whether the provided value is a valid URL."""
        return isinstance(url, str) and validate_url(url, verbose=True)

    @classmethod
    def is_valid_reason(cls, reason: object) -> TypeGuard[str]:
        """Validates whether `reason` is a valid string."""
        return isinstance(reason, str)

    @classmethod
    def is_valid_content(cls, content: object) -> TypeGuard[bytes]:
        """Validates whether `content` is a valid bytes object."""
        return isinstance(content, bytes)

    @classmethod
    def is_valid_headers(cls, headers: object) -> TypeGuard[Mapping[str, str]]:
        """Validates whether `headers` is a dict containing string-typed keys/values."""
        return isinstance(headers, (dict, Mapping)) and all(
            isinstance(field, str) and isinstance(value, str) for field, value in headers.items()
        )

    def structure(self, flatten: bool = False, show_value_attributes: bool = True) -> str:
        """Helper method that shows the current structure of the ResponseValidator class in a string format. This method
        will show the name of the current class along with its attributes (`ResponseValidator()`)

        Returns:
            str: A string representation of the current structure of the ResponseValidator

        """
        return generate_repr(self, flatten=flatten, show_value_attributes=show_value_attributes)

    def __repr__(self) -> str:
        """Helper method that uses the `structure` method to create a string representation of the ResponseValidator."""
        return self.structure()


__all__ = ["ResponseValidator"]
