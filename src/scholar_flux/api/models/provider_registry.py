# /api/models/provider_registry.py
"""
The scholar_flux.models.provider_registry module implements the ProviderRegistry class which extends
a dictionary to map provider names to their scholar_flux ProviderConfig.

When scholar_flux uses a provider_name to create a SearchAPI or SearchCoordinator, the package-level
provider_registry is instantiated and referenced to retrieve the necessary configuration for easier
interaction and specification of APIs.
"""
from __future__ import annotations
from typing import Optional
from scholar_flux.api.models.provider_config import ProviderConfig
from scholar_flux.api.validators import validate_and_process_url, normalize_url
from scholar_flux.utils.provider_utils import ProviderUtils
from scholar_flux.exceptions import APIParameterException
from collections import UserDict
import logging

logger = logging.getLogger(__name__)


class ProviderRegistry(UserDict[str, ProviderConfig]):
    """
    The ProviderRegistry implementation allows the smooth and efficient retrieval of API parameter maps and
    default configuration settings to aid in the creation of a SearchAPI that is specific to the current
    API.

    Note that the ProviderRegistry uses the ProviderConfig._normalize_name to ignore underscores and case-sensitivity.

    Methods:
        - ProviderRegistry.from_defaults: Dynamically imports configurations stored within scholar_flux.api.providers,
                                          and fails gracefully if a provider's module does not contain a ProviderConfig.
        - ProviderRegistry.get: resolves a provider name to its ProviderConfig if it exists in the registry.
        - ProviderRegistry.get_from_url: resolves a provider URL to its ProviderConfig if it exists in the registry.
    """

    def __contains__(self, key: object) -> bool:
        """
        Helper method for determining whether a specific provider name after normalization can
        be found within the current ProviderRegistry.

        Args:
            key (str): Name of the default Provider

        Returns:
            bool: indicates the presence or absence of a key in the registry

        """

        if isinstance(key, str):
            key = ProviderConfig._normalize_name(key)
            return key in self.data
        return False

    def __getitem__(self, key: str) -> ProviderConfig:
        """
        Attempt to retrieve a ProviderConfig instance for the given provider name.

        Args:
            provider_name (str): Name of the default Provider

        Returns:
            ProviderConfig: instance configuration for the provider if it exists

        """

        key = ProviderConfig._normalize_name(key) if isinstance(key, str) else key
        return super().__getitem__(key)

    def __setitem__(
        self,
        key: str,
        value: ProviderConfig,
    ) -> None:
        """
        Allows for the addition of a ProviderConfig to the ProviderRegistry.
        This handles the implicit validation necessary to ensure that keys are strings
        and values are ProviderConfig values

        Args:
            key (str): Name of the provider to add to the registry
            value (ProviderConfig): The configuration of the API Provider
        """

        # Check if the key already exists and handle overwriting behavior
        if not isinstance(key, str):
            raise APIParameterException(
                f"The key provided to the ProviderRegistry is invalid. Expected a string, received {type(key)}"
            )

        if not isinstance(value, ProviderConfig):
            raise APIParameterException(
                f"The value provided to the ProviderRegistry is invalid. "
                f"Expected a ProviderConfig, received {type(ProviderConfig)}"
            )

        # normalizing as insurance for name normalization in cases where a config is manually added:
        normalized_key = ProviderConfig._normalize_name(key)
        super().__setitem__(normalized_key, value)

    def add(self, provider_config: ProviderConfig) -> None:
        """Helper method for adding a new provider to the provider registry"""
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
        """Helper method for removing a provider configuration from the provider registry"""
        provider_name = ProviderConfig._normalize_name(provider_name)
        if config := self.data.pop(provider_name, None):
            logger.info(
                f"Removed the provider config for the provider, '{config.provider_name}' " "from the provider registry"
            )
        else:
            logger.warning(f"A ProviderConfig with the provider name, '{provider_name}' was not found")

    def __delitem__(self, key: str) -> None:
        """
        Attempt to delete an element from a ProviderConfig instance for the given provider name.

        Args:
            provider_name (str): Name of the default Provider
        """

        key = ProviderConfig._normalize_name(key) if isinstance(key, str) else key
        return super().__delitem__(key)

    def get_from_url(self, provider_url: Optional[str]) -> Optional[ProviderConfig]:
        """
        Attempt to retrieve a ProviderConfig instance for the given provider by
        resolving matching an url to the provider's.
        Will not throw an error in the event that the provider does not exist.

        Args:
            provider_url (Optional[str]): Name of the default Provider

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
        """
        Helper method that dynamically loads providers from the scholar_flux.api.providers module specifically
        reserved for default provider configs.

        Returns:
            ProviderRegistry: A pydantic model holding a single dictionary under `root` which holds all loaded configs
        """
        provider_dict = ProviderUtils.load_provider_config_dict()
        return cls(provider_dict)
