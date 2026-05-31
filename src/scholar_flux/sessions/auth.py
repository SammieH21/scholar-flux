"""Defines authorization-related session helpers for the secure transmission of API-keys."""

from requests.auth import AuthBase
from requests import PreparedRequest
from scholar_flux.exceptions import APIParameterException, APIKeyValidationException
from scholar_flux.security.utils import SecretUtils
from scholar_flux.utils.repr_utils import generate_repr
from scholar_flux.utils.helpers import coerce_str
from pydantic import SecretStr
from abc import ABC, abstractmethod
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
from typing import Any

import logging

logger = logging.getLogger(__name__)


class AuthAPIKeyBase(AuthBase, ABC):
    """Authentication helper base class for sending API keys via requests/sessions."""

    DEFAULT_PARAMETER_NAME: str = "api_key"

    def __init__(
        self,
        api_key: str | SecretStr,
        parameter_name: str | None = None,
    ) -> None:
        """Initializes a AuthAPIKeyBase subclass, validating `api_key` and `parameter_name` before their assignment."""
        super().__init__()
        self.api_key = api_key
        self.parameter_name = parameter_name if parameter_name else self.DEFAULT_PARAMETER_NAME

    @property
    def api_key(self) -> SecretStr:
        """Retrieves the current value of the API key from the AuthAPIBase subclass."""
        return self._api_key

    @api_key.setter
    def api_key(self, key: str | SecretStr) -> None:
        """Validates and assigns the received value to the API key of the AuthAPIBase subclass."""
        self.validate_api_key(key)
        self._api_key = SecretUtils.mask_secret(key)

    @classmethod
    def validate_api_key(cls, api_key: str | SecretStr) -> None:
        """Verifies that received API key is a non-empty string or secret string.

        Args:
            api_key (str | SecretStr):
                A valid API key string or secret string.

        Raises:
            APIKeyValidationException: If the API key is empty or has an invalid type.

        """
        if api_key is not None and not isinstance(api_key, (str, SecretStr)):
            raise APIKeyValidationException(
                f"The `{cls.__name__}` expected a valid API key but instead received {type(api_key)}"
            )

        # Special Case: where the masked value has an invalid type
        if isinstance(api_key, SecretStr) and not isinstance(SecretUtils.unmask_secret(api_key), str):
            raise APIKeyValidationException(
                f"The `{cls.__name__}` expected the unmasked API key to be of type `str` but instead received "
                f"{type(api_key)}"
            )

        # Catch empty strings
        if not SecretUtils.unmask_secret(api_key):
            class_name = cls.__name__
            status = "None" if api_key is None else f"an empty `{type(api_key).__name__}`"
            raise APIKeyValidationException(
                f"The `{class_name}` expected a valid API key but the value received is {status}."
            )

    @property
    def parameter_name(self) -> str:
        """Retrieves the current name of the API key parameter from the AuthAPIKeyBase subclass."""
        return self._parameter_name

    @parameter_name.setter
    def parameter_name(self, name: str) -> None:
        """Validates and assigns the received API key parameter name to the AuthAPIKeyBase subclass."""
        if name is not None and not isinstance(name, str):
            class_name = self.__class__.__name__
            raise APIParameterException(
                f"The `{class_name}` expected a valid API key parameter name but instead received {type(name)}"
            )
        self._parameter_name = name if name is not None else self.DEFAULT_PARAMETER_NAME

    def __repr__(self) -> str:
        """Helper method for identifying the configuration for the AuthBase subclass.

        Returns:
            str: The current structure of the BaseAPI or its subclass.

        """
        return generate_repr(self, flatten=True, resolve_property_attributes=True)

    @abstractmethod
    def __call__(self, r: PreparedRequest) -> PreparedRequest:
        """Adds an API key to the current request."""
        raise NotImplementedError()


class AuthAPIKeyParameter(AuthAPIKeyBase):
    """Authentication helper for sending API keys via request/session `params` when making requests."""

    URL_ENCODING: str = "utf-8"

    def __init__(self, api_key: str | SecretStr, parameter_name: str | None = None) -> None:
        """Initializes a new AuthAPIKeyParameter for storing API keys via headers."""
        super().__init__(api_key=api_key, parameter_name=parameter_name)

    def __call__(self, r: PreparedRequest) -> PreparedRequest:
        """Adds an auth parameter to the current request."""
        api_key = SecretUtils.unmask_secret(self.api_key)

        # Parse the current URL to get existing query parameters
        parsed_url = urlparse(r.url)
        query_parameters: dict[str, str] = dict(parse_qsl(coerce_str(parsed_url.query), keep_blank_values=True))

        if self.parameter_name in query_parameters:
            sep = "://" if parsed_url.scheme else ""
            base_url = f"{coerce_str(parsed_url.scheme)}{sep}{coerce_str(parsed_url.netloc)}"
            logger.debug("Replacing API key field for base URL, '%s'...", base_url)

        # Update the API key parameter
        query_parameters[self.parameter_name] = api_key

        # `.prepare_url()` is additive — remove the previously defined query fields
        url = urlunparse(parsed_url._replace(query=""))  # type: ignore [arg-type]
        # Encode the updated query parameter dictionary
        parameters = urlencode(query_parameters)

        # Rebuild the URL with the updated query parameter dictionary
        r.prepare_url(url, params=parameters)
        return r


class AuthAPIKeyHeader(AuthAPIKeyBase):
    """Authentication helper for sending API keys via request/session `headers` when making requests."""

    def __init__(
        self, api_key: str | SecretStr, parameter_name: str | None = None, *, scheme: str | None = None
    ) -> None:
        """Initializes a new AuthAPIKeyHeader parameter for storing API keys via headers."""
        super().__init__(api_key=api_key, parameter_name=parameter_name)
        self.scheme = scheme

    @property
    def scheme(self) -> str | None:
        """Retrieves the current value of the scheme from the AuthAPIBase subclass."""
        return self._scheme

    @scheme.setter
    def scheme(self, value: str | None) -> None:
        """Validates and assigns the received scheme to the AuthAPIBase subclass."""
        if value is not None and not isinstance(value, str):
            raise APIParameterException(
                f"The `AuthAPIKeyHeader` expected a valid scheme for the API key but instead received {type(value)}"
            )
        self._scheme = value

    def __call__(self, r: PreparedRequest) -> PreparedRequest:
        """Adds an auth header to the current request."""
        api_key = SecretUtils.unmask_secret(self.api_key)

        if self.scheme:
            api_key_base = api_key.removeprefix(self.scheme).lstrip()
            api_key = f"{self.scheme.strip()} {api_key_base}"

        r.headers[self.parameter_name] = api_key
        return r


class AuthAPIKeyNoOp(AuthBase):
    """No-Op API key authentication subclass used to avoid the addition of an API key or token to a request."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initializes a new Auth subclass with No-Op parameters, discarding positional and keyword arguments."""
        super().__init__()

    @property
    def api_key(self) -> None:
        """No-Op property for added compatibility."""

    @property
    def parameter_name(self) -> None:
        """No-Op property for added compatibility."""

    def __call__(self, r: PreparedRequest) -> PreparedRequest:
        """No-Op: returns the prepared request as is without modification."""
        return r

    def __repr__(self) -> str:
        """Returns a summary representation of the `AuthAPIKeyNoOp`."""
        return generate_repr(self)


__all__ = ["AuthAPIKeyBase", "AuthAPIKeyParameter", "AuthAPIKeyHeader", "AuthAPIKeyNoOp"]
