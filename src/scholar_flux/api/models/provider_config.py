from pydantic import BaseModel, field_validator, ConfigDict
from typing import Optional, ClassVar, Any
from scholar_flux.api.validators import validate_url, normalize_url
from scholar_flux.api.models.base import BaseAPIParameterMap
from scholar_flux.exceptions.api_exceptions import APIParameterException
from scholar_flux.utils.repr_utils import generate_repr

import logging
logger = logging.getLogger(__name__)

class ProviderConfig(BaseModel):
    """
    Config for creating the basic instructions and settings necessary to interact with
    with new providers. This config on initialization is created for default providers
    on package initialization in the scholar_flux.api.providers submodule.
    A new, custom provider or override can be added to the
    provider_registry (A custom user dictionary) from scholar_flux.api.providers

    Args:
        provider_name (str): The name of the provider to be associated with the config
        base_url (str): The URL of the provider to send requests with the specified parameters
        parameter_map (BaseAPIParameterMap): The parameter map indicating the specific semantics of the API
        records_per_page (int): Generally the upper limit (for some APIs) or reasonable limit for the number of requsets
                                 specific to the API provider
        request_delay (float): Indicates exactly how long to wait before sending successive requests (may vary based on API)
        api_key_env_var (Optional[str]): Indicates the environment variable to look for if the API requires or accepts API keys
        docs_url: (Optional[str]): An optional URL that indicates where documentation related to the use of the API can be found
    """
    provider_name: str
    base_url: str
    parameter_map: BaseAPIParameterMap
    records_per_page: int = 25
    request_delay: float = 6.1
    api_key_env_var: Optional[str] = None
    docs_url: Optional[str] = None
    model_config: ClassVar[ConfigDict]  = ConfigDict(str_strip_whitespace=True)

    @field_validator('provider_name', mode='after')
    def normalize_provider_name(cls, v: str) -> str:
        """Helper method for normalizing the names of providers to a consistent structure"""
        return cls._normalize_name(v)

    def search_config_defaults(self) -> dict[str, Any]:
        """
        Convenience Method for retrieving ProviderConfig fields as a dict. Useful for 
        providing the missing information needed to create a SearchAPIConfig object for a
        provider when only the provider_name has been provided

        Returns:
            (dict): A dictionary containing the URL, name, records_per_page, and request_delay
                    for the current provider.
        """
        return self.model_dump(include={'provider_name', 'base_url', 'records_per_page', 'request_delay'})

    @field_validator('base_url')
    def validate_base_url(cls, v: str) -> str:
        """Validates the current url and raises a APIParameterException if invalid"""
        if not isinstance(v, str) or not validate_url(v):
            logger.error(f"The URL provided to the ProviderConfig is invalid: {v}")
            raise APIParameterException(f"The URL provided to the ProviderConfig is invalid: {v}")
        return cls._normalize_url(v, normalize_https = False)

    @field_validator('docs_url')
    def validate_docs_url(cls, v: Optional[str]) -> Optional[str]:
        """Validates the documentation url and raises a APIParameterException if invalid"""
        if v is not None and not validate_url(v):
            logger.error(f"The URL provided to the ProviderConfig is invalid: {v}")
            raise APIParameterException(f"The URL provided to the ProviderConfig is invalid: {v}")
        return cls._normalize_url(v, normalize_https = False) if v is not None else None


    @staticmethod
    def _normalize_name(provider_name: str) -> str:
        """
        Helper method for normalizing names to resolve them against string input
        with minor differences in case.
        Args:
            provider_name (str): The name of the provider to normalize
        """
        return provider_name.lower().replace('_','').strip()

    @staticmethod
    def _normalize_url(url: str, normalize_https: bool = True) -> str:
        """
        Helper method to aid in comparisons of string urls. Because of the idios

        Args:
            url (str): The url to normalize into a consistent structure for later comparison
            normalize_https (bool): indicates whether to normalize the http identifier on the URL.
                                    This is True by default.
        Returns:
            str: The normalized url

        """
        return normalize_url(url, normalize_https=normalize_https)

    def __repr__(self) -> str:
        """Utility method for creating an easy to view representation of the current configuration"""
        return generate_repr(self)
