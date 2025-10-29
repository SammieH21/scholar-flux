# /api/models/provider_registry.py
"""The scholar_flux.models.provider_registry module implements the ProviderRegistry class which extends a dictionary to
map provider names to their scholar_flux ProviderConfig.

When scholar_flux uses a provider_name to create a SearchAPI or SearchCoordinator, the package-level provider_registry
is instantiated and referenced to retrieve the necessary configuration for easier interaction and specification of APIs.

"""
from __future__ import annotations
from typing import Optional
from scholar_flux.api.models.provider_config import ProviderConfig
from scholar_flux.api.models.base_provider_dict import BaseProviderDict
from scholar_flux.api.validators import validate_and_process_url, normalize_url
from scholar_flux.utils.provider_utils import ProviderUtils
from scholar_flux.exceptions import APIParameterException
import logging

logger = logging.getLogger(__name__)


class ProviderRegistry(BaseProviderDict):
    """The ProviderRegistry implementation allows the smooth and efficient retrieval of API parameter maps and default
    configuration settings to aid in the creation of a SearchAPI that is specific to the current API.

    Note that the ProviderRegistry uses the ProviderConfig._normalize_name to ignore underscores and case-sensitivity.

    Methods:
        - ProviderRegistry.from_defaults: Dynamically imports configurations stored within scholar_flux.api.providers,
                                          and fails gracefully if a provider's module does not contain a ProviderConfig.
        - ProviderRegistry.get: resolves a provider name to its ProviderConfig if it exists in the registry.
        - ProviderRegistry.get_from_url: resolves a provider URL to its ProviderConfig if it exists in the registry.

    """

    def __getitem__(self, key: str) -> ProviderConfig:
        """Attempt to retrieve a ProviderConfig instance for the given provider name.

        Args:
            provider_name (str): Name of the default provider

        Returns:
            ProviderConfig: instance configuration for the provider if it exists

        """
        return super().__getitem__(key)

    def __setitem__(
        self,
        key: str,
        value: ProviderConfig,
    ) -> None:
        """Allows for the addition of a ProviderConfig to the ProviderRegistry. This handles the implicit validation
        necessary to ensure that keys are strings and values are ProviderConfig values.

        Args:
            key (str): Name of the provider to add to the registry
            value (ProviderConfig): The configuration of the API Provider

        """
        try:
            if not isinstance(value, ProviderConfig):
                raise TypeError(
                    f"The value provided to the ProviderRegistry is invalid. "
                    f"Expected a ProviderConfig, received {type(value)}"
                )

            super().__setitem__(key, value)
        except (TypeError, ValueError) as e:
            raise APIParameterException(e) from e

    def create(self, provider_name: str, **kwargs) -> ProviderConfig:
        """Helper method that creates and registers a new ProviderConfig with the current provider registry.

        Args:
            key (str):
                The name of the provider to create a new provider_config for.
            `**kwargs`:
                Additional keyword arguments to pass to `scholar_flux.api.models.ProviderConfig`

        """
        try:

            # Creates a new provider configuration with keyword
            provider_config = ProviderConfig(provider_name=provider_name, **kwargs)

            # adds the provider configuration to the registry
            self.add(provider_config)

            return provider_config
        except Exception as e:
            raise APIParameterException(
                "Encountered an error when creating a new ProviderConfig with the provider name, "
                f"'{provider_name}': {e}"
            )

    def add(self, provider_config: ProviderConfig) -> None:
        """Helper method for adding a new provider to the provider registry."""
        if not isinstance(provider_config, ProviderConfig):
            raise APIParameterException(
                f"The value could not be added to the provider registry: "
                f"Expected a ProviderConfig, received {type(provider_config)}"
            )

        provider_name = provider_config.provider_name

        if provider_name in self.data:
            logger.warning(f"Overwriting the previous ProviderConfig for the provider, '{provider_name}'")

        self[provider_name] = provider_config

    def remove(self, provider_name: str) -> None:
        """Helper method for removing a provider configuration from the provider registry."""
        provider_name = ProviderConfig._normalize_name(provider_name)
        if config := self.data.pop(provider_name, None):
            logger.info(
                f"Removed the provider config for the provider, '{config.provider_name}' from the provider registry"
            )
        else:
            logger.warning(f"A ProviderConfig with the provider name, '{provider_name}' was not found")

    def get_from_url(self, provider_url: Optional[str]) -> Optional[ProviderConfig]:
        """Attempt to retrieve a ProviderConfig instance for the given provider by resolving the provided url to the
        provider's. Will not throw an error in the event that the provider does not exist.

        Args:
            provider_url (Optional[str]): Name of the default provider

        Returns:
            Optional[ProviderConfig]: Instance configuration for the provider if it exists, else None

        """
        if not provider_url:
            return None

        normalized_url = validate_and_process_url(provider_url)

        return next(
            (
                registered_provider
                for registered_provider in self.data.values()
                if normalize_url(registered_provider.base_url) == normalized_url
            ),
            None,
        )

    @classmethod
    def from_defaults(cls) -> ProviderRegistry:
        """Helper method that dynamically loads providers from the scholar_flux.api.providers module specifically
        reserved for default provider configs.

        Returns:
            ProviderRegistry: A new registry containing the loaded default provider configurations

        """
        provider_dict = ProviderUtils.load_provider_config_dict()
        return cls(provider_dict)


__all__ = ["ProviderRegistry"]
