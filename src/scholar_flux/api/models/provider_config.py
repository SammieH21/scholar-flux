# /api/models/provider_config.py
"""The scholar_flux.api.models.provider_config module implements the basic provider configuration necessary for
interacting with APIs.

It provides the foundational information necessary for the SearchAPI to resolve provider names to the URLs of the
providers, as well as basic defaults necessary for interaction.

"""
from pydantic import BaseModel, field_validator, ConfigDict, Field
from typing import Optional, ClassVar, Any
from scholar_flux.api.validators import validate_url, normalize_url
from scholar_flux.api.models.base_parameters import BaseAPIParameterMap
from scholar_flux.api.normalization.base_field_map import BaseFieldMap
from scholar_flux.api.models.response_metadata_map import ResponseMetadataMap
from scholar_flux.exceptions.api_exceptions import APIParameterException
from scholar_flux.utils.repr_utils import generate_repr_from_string

import logging

logger = logging.getLogger(__name__)


class ProviderConfig(BaseModel):
    """Config for creating the basic instructions and settings necessary to interact with new providers. This config, on
    initialization, is created for default providers on package initialization in the scholar_flux.api.providers
    submodule. A new, custom provider or override can be added to the provider_registry (a custom user dictionary) from
    the scholar_flux.api.providers module.

    Args:
        provider_name (str): The name of the provider to be associated with the config.
        base_url (str): The URL of the provider to send requests with the specified parameters.
        parameter_map (BaseAPIParameterMap): The parameter map indicating the specific semantics of the API.
        metadata_map (MetadataMap): Defines the names of metadata fields used to distinguish response characteristics.
        field_map (Optional[BaseFieldMap]):
            A provider-specific field map that normalizes processed response records into a universal record structure.
        records_per_page (int):
            Generally the upper limit (for some APIs) or reasonable limit for the number of retrieved records per request
            (specific to the API provider).
        request_delay (float):
            Indicates exactly how many seconds to wait before sending successive requests. Note that the requested
            interval may vary based on the API provider.
        api_key_env_var (Optional[str]):
            Indicates the environment variable to look for if the API requires or accepts API keys.
        docs_url (Optional[str]):
            An optional URL that indicates where documentation related to the use of the API can be found.

    Example Usage:
        >>> from scholar_flux.api import ProviderConfig, APIParameterMap, SearchAPI
        >>> # Maps each of the individual parameters required to interact with the Guardian API
        >>> parameters = APIParameterMap(query='q',
        >>>                              start='page',
        >>>                              records_per_page='page-size',
        >>>                              api_key_parameter='api-key',
        >>>                              auto_calculate_page=False,
        >>>                              api_key_required=True)
        >>> # creating the config object that holds the basic configuration necessary to interact with the API
        >>> guardian_config = ProviderConfig(provider_name = 'GUARDIAN',
        >>>                                  parameter_map = parameters,
        >>>                                  base_url = 'https://content.guardianapis.com//search',
        >>>                                  records_per_page=10,
        >>>                                  api_key_env_var='GUARDIAN_API_KEY',
        >>>                                  request_delay=6)
        >>> api = SearchAPI.from_provider_config(query = 'economic welfare',
        >>>                                      provider_config = guardian_config,
        >>>                                      use_cache = True)
        >>> assert api.provider_name == 'guardian'
        >>> response = api.search(page = 1) # assumes that you have the GUARDIAN_API_KEY stored as an env variable
        >>> assert response.ok

    """

    provider_name: str = Field(min_length=1, description="Provider Name or Base URL for the article API")
    base_url: str = Field(description="Base URL for the API")
    parameter_map: BaseAPIParameterMap = Field(description="Map detailing the parameter names used by the API")
    metadata_map: Optional[ResponseMetadataMap] = Field(
        default=None, description="Metadata map used to distinguish field names"
    )
    field_map: Optional[BaseFieldMap] = Field(
        default=None, description="Maps API-Specific fields to commonly named parameters"
    )
    records_per_page: int = Field(default=20, ge=0, le=1000, description="Number of records per page (1-1000)")
    request_delay: float = Field(default=6.1, ge=0, description="Minimum delay between requests in seconds")
    api_key_env_var: Optional[str] = Field(
        default=None, description="The API Key environment variable to read from the system environment, if specified"
    )
    docs_url: Optional[str] = Field(default=None, description="URL for the API's documentation")
    model_config: ClassVar[ConfigDict] = ConfigDict(str_strip_whitespace=True)

    @field_validator("provider_name", mode="after")
    def normalize_provider_name(cls, v: str) -> str:
        """Helper method for normalizing the names of providers to a consistent structure."""
        return cls._normalize_name(v)

    def search_config_defaults(self) -> dict[str, Any]:
        """Convenience method for retrieving ProviderConfig fields as a dict. Useful for providing the missing
        information needed to create a SearchAPIConfig object for a provider when only the provider_name has been
        provided.

        Returns:
            dict: A dictionary containing the URL, name, records_per_page, and request_delay
                  for the current provider.

        """
        return self.model_dump(include={"provider_name", "base_url", "records_per_page", "request_delay"})

    @field_validator("base_url")
    def validate_base_url(cls, v: str) -> str:
        """Validates the current URL and raises an APIParameterException if invalid."""
        if not isinstance(v, str) or not validate_url(v):
            msg = f"Error validating the API base URL: The URL provided to the ProviderConfig is invalid: {v}"
            logger.error(msg)
            raise APIParameterException(msg)
        return cls._normalize_url(v, normalize_https=False)

    @field_validator("docs_url")
    def validate_docs_url(cls, v: Optional[str]) -> Optional[str]:
        """Validates the documentation URL and raises an APIParameterException if invalid."""
        if v is not None and not validate_url(v):
            msg = f"Error validating the document URL: The URL provided to the ProviderConfig is invalid: {v}"
            logger.error(msg)
            raise APIParameterException(msg)
        return cls._normalize_url(v, normalize_https=False) if v is not None else None

    @staticmethod
    def _normalize_name(provider_name: str) -> str:
        """Helper method for normalizing names to resolve them against string input with minor differences in case.

        Args:
            provider_name (str): The name of the provider to normalize.

        """
        return provider_name.lower().replace("_", "").strip()

    @staticmethod
    def _normalize_url(url: str, normalize_https: bool = True) -> str:
        """Helper method to normalize URLs including the protocol and schema format.

        This method is later used to ensure accurate comparisons between URLs and aids in the retrieval of the correct
        configuration from the `scholar_flux.api.providers.provider_registry` for known providers.

        Args:
            url (str): The url to normalize into a consistent structure for later comparison.
            normalize_https (bool):
                Indicates whether to normalize the HTTP identifier on the URL. This is True by default.

        Returns:
            str: The normalized URL.

        """
        return normalize_url(url, normalize_https=normalize_https)

    def structure(self, flatten: bool = False, show_value_attributes: bool = True) -> str:
        """Helper method that shows the current structure of the ProviderConfig."""
        class_name = self.__class__.__name__
        fields = dict(self)
        return generate_repr_from_string(
            class_name, fields, flatten=flatten, show_value_attributes=show_value_attributes
        )

    def __repr__(self) -> str:
        """Utility method for creating an easy to view representation of the current configuration."""
        return self.structure()


__all__ = ["ProviderConfig"]
