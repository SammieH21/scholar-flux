# /api/models/rate_limiter_registry.py
"""The scholar_flux.api.models.rate_limiter_registry module implements a registry that stores rate limiters by provider.

The `RateLimiterRegistry` implements several helpers for interacting with, retrieving, and creating default and thread-
safe rate limiters for both default and new providers.

"""
from __future__ import annotations
from scholar_flux.api.models.base_provider_dict import BaseProviderDict
from scholar_flux.api.rate_limiting import RateLimiter, ThreadedRateLimiter
from scholar_flux.exceptions import APIParameterException
import scholar_flux.api.providers as api_providers
from typing_extensions import Self
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class RateLimiterRegistry(BaseProviderDict):
    """A registry for creating, retrieving, updating, and deleting rate limiters by provider.

    The `RateLimiterRegistry` standardizes CRUD operations with thread-safe rate limiters for both default and
    custom providers. It ensures compatibility when using rate limiters in active applications. This implementation
    is especially important when using `MultiSearchCoordinators` to enforce normalized rate limiting by provider.

    Attributes:
        threaded (bool): Indicates whether the registry should use ThreadedRateLimiters.

    """

    def __init__(self, *args, threaded: bool = False, **kwargs):
        """Initializes the RateLimiterRegistry and enforces the use of ThreadedRateLimiters when `threaded=True`."""
        self.threaded = threaded
        super().__init__(*args, **kwargs)

    @property
    def rate_limiter(self) -> type[RateLimiter | ThreadedRateLimiter]:
        """Helper method that returns the class constructor for a rate limiter.

        Returns:
            A ThreadedRateLimiter if `self.threaded=True`, otherwise the core `RateLimiter`

        """
        return ThreadedRateLimiter if self.threaded else RateLimiter

    def __getitem__(self, key: str) -> RateLimiter:
        """Attempt to retrieve a RateLimiter instance for the given provider name.

        Args:
            key (str): Name of the provider

        Returns:
            RateLimiter: The RateLimiter for the provider if it exists

        """
        return super().__getitem__(key)

    def __setitem__(
        self,
        key: str,
        value: RateLimiter | ThreadedRateLimiter,
    ) -> None:
        """Sets a key-value pair to the current registry where all keys are strings and values are RateLimiters.

        This method overrides the core functionality of dictionaries to ensure that validation for the `value`
        parameter occurs before saving the provider name-rate limiter pair

        Args:
            key (str): Name of the provider to add to the registry
            value (RateLimiter | ThreadedRateLimiter): The rate limiter for the API Provider

        """
        try:

            if not isinstance(value, self.rate_limiter):
                raise TypeError(
                    f"The value provided to the {self.__class__.__name__} is invalid. "
                    f"Expected a {self.rate_limiter.__name__}, received {type(value)}"
                )

            super().__setitem__(key, value)
        except (TypeError, ValueError) as e:
            raise APIParameterException(e) from e

    def get_from_url(self, provider_url: Optional[str]) -> Optional[RateLimiter | ThreadedRateLimiter]:
        """Attempts to retrieve a RateLimiter for the specified provider from a URL.

        This method retrieves the rate limiter of the provider associated with the provided URL if the URL after normalization exists within
        the `scholar_flux.api.provider_registry`. If a provider does not exist, a value of None will be returned instead.

        Args:
            provider_url (Optional[str]): URL of the provider to look up.

        Returns:
            Optional[RateLimiter | ThreadedRateLimiter]:
                The rate limiter of the provider when available. Otherwise None.

        """
        if provider_config := api_providers.provider_registry.get_from_url(provider_url):
            return self.data.get(provider_config.provider_name)
        return None

    def get_or_create(
        self, key: str, default_request_delay: Optional[int | float] = None
    ) -> RateLimiter | ThreadedRateLimiter:
        """Helper method that retrieves rate limiter from the registry or creates one if it doesn't exist.

        This method is useful when a provider may or may not exist in the current registry and otherwise
        needs to be added. If a provider's rate limiter does not yet exist, the registry attempts to create
        a new rate limiter.

        Args:
            key (str):
                The name of the provider to retrieve a rate limiter for, and otherwise create a new rate limiter if it
                doesn't exist.
            default_request_delay (Optional[int | float]):
                The default minimum interval to use when creating a new rate limiter if one does not already exist
                for the provider

        Returns:
            RateLimiter | ThreadedRateLimiter:
                The retrieved rate limiter for the current provider if available. Otherwise a new,
                RateLimiter will be created, registered, and returned.

        """
        # If a rate limiter exists for the current key, return it
        if rate_limiter := self.data.get(key):
            return rate_limiter

        # otherwise, create a new rate limiter
        return self.create(key, default_request_delay)

    def create(
        self, provider_name: str, default_request_delay: Optional[int | float] = None
    ) -> RateLimiter | ThreadedRateLimiter:
        """Helper method that creates a new rate limiter for the current provider.

        The minimum interval for the provider is chosen based on the following order of priority:

        1. If the provider exists in the `provider_registry`, use the `request_delay` from its configuration settings.
        2. Otherwise, use the `default_request_delay` parameter if it is a float or integer.
        3. If a provider doesn't exist in the registry and `default_request_delay` isn't specified, use the
           `RateLimiter.DEFAULT_MIN_INTERVAL` class parameter.

        Args:
            provider_name (str):
                The name of the provider to create a new rate limiter for.
            default_request_delay (Optional[int | float]):
                The default minimum interval to use when creating a new rate limiter.

        """
        try:
            if default_request_delay is not None:
                self.rate_limiter._validate(default_request_delay)

            if provider_config := api_providers.provider_registry.get(provider_name):
                # Otherwise, create a new rate limiter from the `provider_registry`
                request_delay = provider_config.request_delay
            else:
                # Default to `default_request_delay` when possible
                request_delay = default_request_delay

            # Creates a new rate limiter with the `RateLimiter.default_request_delay` or `default_request_delay` if available
            rate_limiter = self.rate_limiter(request_delay)

            # adds the rate limiter to the registry
            self.add(provider_name, rate_limiter)

            return rate_limiter
        except Exception as e:
            raise APIParameterException(
                f"Encountered an error when creating a new rate limiter with the provider name, '{provider_name}': {e}"
            )

    def add(self, provider_name: str, rate_limiter: RateLimiter | ThreadedRateLimiter) -> None:
        """Helper method for adding a new provider and rate limiter to the provider registry."""

        provider_name = self._normalize_name(provider_name)

        if provider_name in self.data:
            logger.warning(f"Overwriting the previous RateLimiter for the provider, '{provider_name}'")

        self.data[provider_name] = rate_limiter

        logger.debug(
            f"Created a new rate limiter for the provider, {provider_name} "
            f"with a request delay of {rate_limiter.min_interval}"
        )

    def remove(self, provider_name: str) -> None:
        """Helper method for removing a provider configuration from the provider registry."""
        provider_name = (
            self._normalize_name(provider_name) if isinstance(provider_name, str) and provider_name else provider_name
        )

        if self.data.pop(provider_name, None):
            logger.info(f"Removed the rate limiter for the provider, '{provider_name}' from the rate limiter registry")
        else:
            logger.warning(f"A RateLimiter with the provider name, '{provider_name}' was not found")

    @classmethod
    def from_defaults(cls, threaded: bool = False) -> Self:
        """Initializes a new `RateLimiterRegistry` for known providers based on their configurations.

        This method specifically uses the `provider_name` and `request_delay` of each provider listed within the
        `scholar_flux.api.providers.provider_registry` to create rate limiters for all known configurations.

        Returns:
            RateLimiterRegistry: A new rate limiter registry that contains default rate limiters for known providers.

        """
        Limiter = ThreadedRateLimiter if threaded else RateLimiter

        return cls(
            {
                provider_name: Limiter(provider_config.request_delay)
                for provider_name, provider_config in api_providers.provider_registry.items()
            },
            threaded=threaded,
        )


__all__ = ["RateLimiterRegistry"]
