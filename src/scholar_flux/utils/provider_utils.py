from __future__ import annotations
from typing import Optional
from scholar_flux.api.models.provider_config import ProviderConfig
import scholar_flux.api.providers as scholar_flux_api_providers
from functools import lru_cache
import pkgutil
import importlib


class ProviderUtils:

    @classmethod
    @lru_cache(1)
    def load_provider_config_dict(cls) -> dict[str, ProviderConfig]:
        """
        Helper method for dynamically retrieving the default provider list as a dictionary.

        Returns:
            dict[str, ProviderConfig]: A dictionary containing the formatted name of the provider
                                       as well as its associated configuration in a dictionary
        """

        providers_module_path = scholar_flux_api_providers.__path__
        providers_module_name = scholar_flux_api_providers.__name__
        config_generator = (
            cls.load_provider_config(f"{providers_module_name}.{module.name}")
            for module in pkgutil.iter_modules(providers_module_path)
        )
        provider_configs = {
            provider.provider_name: provider
            for provider in config_generator
            if provider is not None
        }
        return provider_configs

    @classmethod
    def load_provider_config(
        cls, provider_module: str, provider_config_variable: str = "provider"
    ) -> Optional[ProviderConfig]:
        """
        Helper method that loads a single config from the provided module in the event that
        The module contains a ProviderConfig by the same name as the provider_config_variable.
        The default variable to look for is `provider`.

        Args:
            provider_module (str): The name of the module to load.
            provider_config_variable (str): The name of the variable carrying the config to check for.

        Returns:
            Optional[ProviderConfig]: The ProviderConfig associated with the module if one has been found,
                                      by the same variable name, `provider_config_variable`. Otherwise, the
                                      method will return `None` instead.

        """

        try:
            module = importlib.import_module(provider_module)
            config = getattr(module, provider_config_variable, None)
            return config if isinstance(config, ProviderConfig) else None

        except (ModuleNotFoundError, AttributeError):
            return None
