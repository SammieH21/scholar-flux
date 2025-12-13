# /api/models/provider_registry.py
"""The scholar_flux.api.models.provider_registry module implements the ProviderRegistry class, which extends Python's
user-dictionary implementation to map providers to their unique scholar_flux `ProviderConfig`.

When scholar_flux uses the name of a provider to create a `SearchAPI` or `SearchCoordinator`, the package-level
`scholar_flux.api.providers.provider_registry` is referenced to retrieve the necessary configuration for easier
interaction and specification of APIs.

"""
from __future__ import annotations
from typing import Optional
from scholar_flux.api.models.provider_config import ProviderConfig
from scholar_flux.api.models.base_provider_dict import BaseProviderDict
from scholar_flux.api.validators import validate_and_process_url, normalize_url
from scholar_flux.utils.provider_utils import ProviderUtils
from scholar_flux.utils.repr_utils import generate_repr, generate_repr_from_string
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
            key (str): Name of the provider

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
            provider_name (str):
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
        """Attempt to retrieve a ProviderConfig instance for the given provider by resolving the provided URL to the
        provider's base URL. Will not throw an error in the event that the provider does not exist.

        Args:
            provider_url (Optional[str]): URL of the provider to look up.

        Returns:
            Optional[ProviderConfig]: Instance configuration for the provider if it exists, else None

        """
        if not provider_url:
            return None

        normalized_url = validate_and_process_url(provider_url, remove_parameters=True)

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
        """Dynamically loads provider configurations from the scholar_flux.api.providers module.

        This method specifically uses the `provider_name` of each provider listed within the
        `scholar_flux.api.providers.provider_registry` to lookup and return its `ProviderConfig`.

        Returns:
            ProviderRegistry: A new registry containing the loaded default provider configurations

        """
        provider_dict = ProviderUtils.load_provider_config_dict()
        return cls(provider_dict)

    def structure(self, flatten: bool = False, show_value_attributes: bool = True) -> str:
        """Helper method that shows the current structure of the ProviderRegistry."""
        class_name = self.__class__.__name__
        dictionary_elements = {
            key: generate_repr(value, show_value_attributes=show_value_attributes) for key, value in self.data.items()
        }

        return generate_repr_from_string(class_name, dictionary_elements, flatten=flatten, as_dict=True)

    def resolve_config(
        self, provider_url: Optional[str] = None, provider_name: Optional[str] = None, verbose: bool = True
    ) -> Optional[ProviderConfig]:
        """Helper method to resolve mismatches between the URL and the provider_name when both are provided. The default
        behavior is to always prefer a provided provider_url over the provider_name to offer maximum flexibility.

        Args:
            provider_url (Optional[str]):
                The prospective URL associated with a provider configuration.
            provider_name (Optional[str]):
                The prospective name of the provider associated with a provider configuration.
            verbose (bool):
                Determines whether the origin of the configuration should be logged.
        Returns:
            Optional[ProviderConfig]:
                A provider configuration resolved with priority given to the base URL or the provider name otherwise.
                If neither the base URL and provider name resolve to a known provider, None is returned instead.

        """
        # if both provider name and information is provided, prioritize the url first.
        provider_from_url = self.get_from_url(provider_url) if provider_url else None
        provider_from_name = self.get(provider_name) if provider_name else None
        provider_config = provider_from_url or provider_from_name
        if provider_config:
            if verbose:
                origin = "URL" if provider_from_url else "provider name"
                logger.debug(f"The configuration was resolved from the {origin}.")
            return provider_config
        if verbose:
            logger.debug(
                f"A configuration associated with the URL ({provider_url}) or provider name ({provider_name}) was not located."
            )
        return None

    def __repr__(self) -> str:
        """Helper method for displaying the config in a user-friendly manner."""
        return self.structure(show_value_attributes=False)


__all__ = ["ProviderRegistry"]
