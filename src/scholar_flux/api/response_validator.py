# /api/response_validator.py
"""The scholar_flux.api.response_validator module implements a basic ResponseValidator that is used for preliminary
response validation to determine whether received responses are valid and successful.

This class is used by default in SearchCoordinators to determine whether to proceed with response processing.

"""
import requests
import logging
from scholar_flux.exceptions.api_exceptions import InvalidResponseException, RequestFailedException
from scholar_flux.utils.response_protocol import ResponseProtocol
from scholar_flux.utils.repr_utils import generate_repr

logger = logging.getLogger(__name__)


class ResponseValidator:
    """Helper class that serves as an initial response validation step to ensure that, in custom retry handling, the
    basic structure of a response can be validated to determine whether or not to retry the response retrieval process.

    The ResponseValidator implements class methods that are simple tools that return boolean values
    (True/False) when response or response-like objects do not contain the required structure and
    raise errors when encountering non-response objects or when `raise_on_error = True` otherwise.

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
        For valid response or response- like objects, the status code is verified, returning True for 400 and 500 level
        validation errors and raising an error if `raise_on_error` is set to True.

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
            if not isinstance(response, requests.Response) and not isinstance(response, ResponseProtocol):
                raise TypeError(
                    "The response is not a valid response or response-like object, " f"Received type: {type(response)}"
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
