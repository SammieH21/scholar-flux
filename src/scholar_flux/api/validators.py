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
    validate_int:
        Validates integer values with optional min/max bounds
    validate_str:
        Validates string values with optional allowed values constraint
    validate_date:
        Validates date strings in YYYY-MM-DD format
    validate_bool_str:
        Validates and normalizes boolean string values

"""
import re
from datetime import datetime
from urllib.parse import urlparse, urlunparse
from typing import Optional, Callable, Any
from functools import wraps
from scholar_flux.security.utils import SecretUtils
from scholar_flux.utils import config_settings
from pydantic import SecretStr
import logging

logger = logging.getLogger(__name__)


def validate_api_specific_field(validator: Callable, provider_name: str, field: str) -> Callable:
    """Wrap a validator function with standardized error handling for API-specific parameters.

    Args:
        validator: The validation function to wrap.
        provider_name: Name of the API provider.
        field: Name of the parameter being validated.

    Returns:
        A wrapped validator with enhanced error messages.

    Raises:
        TypeError: If validator is not callable.

    Examples:
        >>> validator = validate_api_specific_field(
        ...     validate_email,
        ...     "openalex",
        ...     "mailto"
        ... )
        >>> validator("user@example.com")

    """
    if not callable(validator):
        raise TypeError(f"Expected callable validator, got {type(validator).__name__}")

    @wraps(validator)
    def wrapped_validator(*args, **kwargs) -> Any:
        """Internal wrapper that returns a validated value upon success and raises a `ValueError` otherwise."""
        try:
            return validator(*args, **kwargs)
        except Exception as e:
            error_msg = f"Validation failed for parameter '{field}' in provider '{provider_name}': {e}"
            logger.error(error_msg)
            raise ValueError(error_msg) from e

    return wrapped_validator


def api_validator(provider_name: str, field: str) -> Callable:
    """Decorator for wrapping validators with standardized error handling.

    Args:
        provider_name: Name of the API provider.
        field: Name of the parameter being validated.

    Returns:
        A decorator that wraps validators with enhanced error handling.

    Examples:
        >>> @api_validator("openalex", "mailto")
        ... def validate_mailto(email):
        ...     return validate_and_process_email(email)

    """

    def decorator(validator: Callable) -> Callable:
        """Internal wrapper that annotates the validator with the name of the current provider and field to validate."""
        return validate_api_specific_field(validator, provider_name, field)

    return decorator


def validate_email(email: str, verbose: bool = True) -> bool:
    """Uses regex to determine whether the provided value is an email.

    Args:
        email (str): The email string to validate

    Returns:
        True if the email is valid, and False otherwise

    """
    regex = r"^[a-zA-Z0-9._%+-]+(%40|@)[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if isinstance(email, str) and re.match(regex, email):
        return True
    if verbose:
        logger.warning(f"The value, '{email}' is not a valid email")
    return False


def validate_and_process_email(
    email: Optional[SecretStr | str], from_env: bool = True, verbose: bool = True
) -> Optional[SecretStr]:
    """If a string value is provided, determine whether the email is valid.

    This function first uses the validate_email function for the validation of the email. If the value is non-missing is
    not an email, this implementation will raise an ValueError. When the provided email is None, this function will
    attempt to load the email from the config and environment if possible (SCHOLAR_FLUX_DEFAULT_MAILTO).

    Args:
        email (Optional[str]): an email to validate if non-missing

    Returns:
        True if the email is valid or is not provided, and False otherwise

    Raises:
        ValueError: If the current value is not an email

    """
    # read the email from the environment only if the passed value is None and `from_env`=True
    env_email = config_settings.get("SCHOLAR_FLUX_DEFAULT_MAILTO") if email is None and from_env else None

    if email is None and env_email is None:
        return None

    email_string = SecretUtils.unmask_secret(env_email or email)

    if not validate_email(email_string):
        if env_email:
            raise ValueError(
                f"The environment variable, SCHOLAR_FLUX_DEFAULT_MAILTO contains an invalid email: '{env_email}'. "
                "Provide a valid email or unset the environment variable."
            )
        raise ValueError(f"The provided email is invalid, received {email_string}")

    return SecretUtils.mask_secret(email_string)


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


def validate_int(value: Optional[int], min: Optional[int] = None, max: Optional[int] = None) -> Optional[int]:
    """Validate that a value is an integer and optionally within bounds.

    Args:
        value: The value to validate as an integer.
        min: Optional minimum value (inclusive).
        max: Optional maximum value (inclusive).

    Returns:
        The validated integer value, or None if value is None.

    Raises:
        ValueError: If value is not an integer or is outside the specified bounds.

    """
    if value is None:
        return None

    if not isinstance(value, int):
        raise ValueError(f"Expected int, got {type(value).__name__}")
    if min is not None and value < min:
        raise ValueError(f"Value {value} is less than minimum {min}")
    if max is not None and value > max:
        raise ValueError(f"Value {value} is greater than maximum {max}")
    return value


def validate_str(value: Optional[str], allowed: Optional[list | set | tuple] = None) -> Optional[str]:
    """Validate that a value is a string and optionally in a set of allowed values.

    Args:
        value: The value to validate as a string.
        allowed: Optional collection of allowed string values.

    Returns:
        The validated string value, or None if value is None.

    Raises:
        ValueError: If value is not a string or is not in the allowed values.

    """
    if value is None:
        return None

    if not isinstance(value, str):
        raise ValueError(f"Expected str, got {type(value).__name__}")
    if allowed is not None and value not in allowed:
        raise ValueError(f"Value '{value}' not in allowed values: {allowed}")
    return value


def validate_date(
    value: Optional[str], format: str = "%Y-%m-%d", format_description: str = "YYYY-MM-DD"
) -> Optional[str]:
    """Validate that a value is a date string in the specified format.

    Args:
        value: The date string to validate.
        format: The expected date format (strptime format string).
        format_description: Human-readable format description for error messages.

    Returns:
        The validated date string, or None if value is None.

    Raises:
        ValueError: If value is not a valid date in the specified format.

    Examples:
        >>> validate_date("2023-01-15")
        '2023-01-15'
        >>> validate_date("2023/01/15", format="%Y/%m/%d", format_description="YYYY/MM/DD")
        '2023/01/15'

    """
    if value is None:
        return None

    if not isinstance(value, str):
        raise ValueError(f"Expected str, got {type(value).__name__}")

    try:
        datetime.strptime(value, format)
        return value
    except ValueError:
        raise ValueError(f"Date must be in {format_description} format, got '{value}'")


__all__ = [
    "validate_api_specific_field",
    "api_validator",
    "validate_email",
    "validate_and_process_email",
    "validate_url",
    "remove_url_parameters",
    "normalize_url",
    "validate_and_process_url",
    "validate_int",
    "validate_str",
    "validate_date",
]
