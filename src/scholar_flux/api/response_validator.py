import requests
import logging
from scholar_flux.exceptions.api_exceptions import InvalidResponseException
from scholar_flux.utils.repr_utils import generate_repr

logger = logging.getLogger(__name__)


class ResponseValidator:
    @staticmethod
    def validate_response(
        response: requests.Response, *, raise_on_error: bool = False
    ) -> bool:
        """
        Validates HTTP response for errors.

        Args:
            response: The HTTP response object to validate
            raise_on_error: If True, raises InvalidResponseException on error

        Returns:
            True if valid, False otherwise

        Raises:
            InvalidResponseException: If response is invalid and raise_on_error is True
        """
        try:
            response.raise_for_status()
            logger.debug("Successfully received response from %s", response.url)
            return True
        except requests.HTTPError as e:
            logger.error(f"Response validation failed: {e}")  # Better
            if raise_on_error:
                raise InvalidResponseException(response, str(e))
        return False

    @staticmethod
    def validate_content(
        response: requests.Response,
        expected_format: str = "application/json",
        *,
        raise_on_error: bool = False,
    ) -> bool:
        """
        Validates the response content type.

        Args:
            response (requests.Response): The HTTP response object to check.
            expected_format (str): The expected content type substring (e.g., "application/json").
            raise_on_error (bool): If True, raises InvalidResponseException on mismatch.

        Returns:
            bool: True if the content type matches, False otherwise.

        Raises:
            InvalidResponseException: If the content type does not match and raise_on_error is True.
        """
        content_type = response.headers.get("Content-Type", "")

        if expected_format in content_type:
            return True

        logger.warning(
            f"Content type validation failed: received '{content_type}', expected '{expected_format}'"
        )

        if raise_on_error:
            raise InvalidResponseException(
                response,
                f"Invalid Response format: received {content_type} and expected {expected_format}",
            )

        return False

    def __repr__(self) -> str:
        """
        Helper method to generate a summary of the ResponsValidator class. This method
        will show the name of the class and the (non-existent) attributes used to
        instantiate the validator.
        """
        return generate_repr(self)
