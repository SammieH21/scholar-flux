# /api/validators.py
"""The scholar_flux.api.validators module implements methods that are used within the validation of scholar_flux API
configurations to ensure that valid and invalid inputs are received as such.

Functions:

    validate_email:
        Used to verify whether an email matches the expected pattern
    validate_and_process_email:
        Attempts to mask valid emails and raises an error on invalid input
    validate_url:
        Used to verify whether a URL is a valid string
    normalize_url:
        Uses regular expressions to format the URL in a consistent format for string comparisons
    validate_and_process_url:
        validates URLs to ensure that it matches the expected format and normalizes the URL for later use

"""
import re
from urllib.parse import urlparse, urlunparse
from typing import Optional
from scholar_flux.security.utils import SecretUtils
from pydantic import SecretStr
import logging

logger = logging.getLogger(__name__)


def validate_email(email: str) -> bool:
    """Uses regex to determine whether the provided value is an email.

    Args:
        email (str): The email string to validate

    Returns:
        True if the email is valid, and False otherwise

    """
    regex = r"^[a-zA-Z0-9._%+-]+(%40|@)[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if isinstance(email, str) and re.match(regex, email):
        return True
    logger.warning(f"The value, '{email}' is not a valid email")
    return False


def validate_and_process_email(email: Optional[SecretStr | str]) -> Optional[SecretStr]:
    """If a string value is provided, determine whether the email is valid.

    This function first uses the validate_email function for the validation of the email.
    If the value is not an email, this implementation will raise an Error

    Args:
        email (Optional[str]): an email to validate if non-missing

    Returns:
        True if the email is valid or is not provided, and False otherwise

    Raises:
        ValueError: If the current value is not an email

    """
    if email is None:
        return None

    email_string = SecretUtils.unmask_secret(email)

    if not validate_email(email_string):
        raise ValueError(f"The provided email is invalid, received {email_string}")

    return SecretUtils.mask_secret(email)


def validate_url(url: str, verbose: bool = True) -> bool:
    """Uses urlparse to determine whether the provided value is a URL.

    Args:
        url (str): The url string to validate
        verbose (bool): Determines whether to log upon encountering invalid URLs

    Returns:
        True if the url is valid, and False otherwise

    """
    try:
        result = urlparse(url)
        if result.scheme not in ("http", "https"):
            raise ValueError(f"Only http/https protocols are allowed. Received scheme: '{result.scheme}'")

        if not result.netloc:
            raise ValueError(
                f"Expected a domain in the URL after the http/https protocol. Only the scheme was received: {url}"
            )
        return True

    except (ValueError, AttributeError) as e:
        if verbose:
            logger.warning(f"The value, '{url}' is not a valid URL: {e}")
    return False


def remove_url_parameters(url: str) -> str:
    """Helper method for removing queries and parameters from URLs.

    Args:
        url (str):
            The URL

    """
    parsed = urlparse(url)
    # Remove query and params
    cleaned = parsed._replace(query="", params="")
    return urlunparse(cleaned)


def normalize_url(url: str, normalize_https: bool = True, remove_parameters: bool = False) -> str:
    """Helper class to aid in comparisons of string urls. Normalizes a URL for consistent comparisons by converting to
    https:// and stripping right-most forward slashes ('/').

    Args:
        url (str):
            The URL to normalize into a consistent structure for later comparison
        normalize_https (bool):
            indicates whether to normalize the http identifier on the URL. This is True by default.

    Returns:
        str: The normalized URL

    """
    if normalize_https:
        url = "https://" + re.sub(r"^https?://(www\.)?", "", url, flags=re.IGNORECASE)

    if remove_parameters:
        url = remove_url_parameters(url)

    url = url.rstrip("/")
    return url


def validate_and_process_url(url: Optional[str], **kwargs) -> Optional[str]:
    """If a string value is provided, determine whether the url is valid.

    This function first uses the validate_url function for the validation of the url.

    Args:
        url (Optional[str]): an URL to validate if non-missing

    Returns:
        True if the URL is valid or is not provided, and False otherwise

    """
    if url is None:
        return None

    if not validate_url(url):
        raise ValueError(
            f"The provided URL '{url}' is invalid. "
            "It must include a scheme (e.g., 'http://' or 'https://') "
            "and a domain name."
        )

    return normalize_url(url, **kwargs)


__all__ = [
    "validate_email",
    "validate_and_process_email",
    "validate_url",
    "remove_url_parameters",
    "normalize_url",
    "validate_and_process_url",
]
