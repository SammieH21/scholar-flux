# api/models/search_api_config.py
"""The scholar_flux.api.models.search_api_config module implements the core SearchAPIConfig used to drive API searches.

The SearchAPIConfig is used by the SearchAPI to interact with API providers via a unified interface for orchestrating
response retrieval.

This configuration defines settings such as rate limiting, the number of records retrieved per request, API keys,
and the API provider/URL where requests will be sent.

Under the hood, the SearchAPIConfig can use both pre-created and custom defaults to create a new configuration
with minimal code.

"""
from __future__ import annotations
from pydantic import BaseModel, Field, field_validator, SecretStr, model_validator
from typing import Optional, Any, ClassVar
from typing_extensions import Self
from urllib.parse import urlparse
from scholar_flux.api.validators import validate_url
from scholar_flux.api.models.provider_config import ProviderConfig
from scholar_flux.api.models.api_parameters import APIParameterConfig
from scholar_flux.api.providers import provider_registry
from scholar_flux.api.models.base_parameters import APISpecificParameter
from scholar_flux.utils.repr_utils import generate_repr
from scholar_flux.exceptions import (
    MissingAPIKeyException,
    MissingAPISpecificParameterException,
    MissingProviderException,
)
from scholar_flux.utils import config_settings
import re
import logging

logger = logging.getLogger(__name__)


class SearchAPIConfig(BaseModel):
    """The SearchAPIConfig class provides the core tools necessary to set and interact with the API. The SearchAPI uses
    this class to retrieve data from an API using universal parameters to simplify the process of retrieving raw
    responses.

    Attributes:
        provider_name (str):
            Indicates the name of the API to use when making requests to a provider. If the provider name matches a
            known default and the `base_url` is unspecified, the base URL for the current provider is used instead.
        base_url (str):
            Indicates the API URL where data will be searched and retrieved.
        records_per_page (int):
            Controls the number of records that will appear on each page.
        request_delay (float):
            Indicates the minimum delay between each request to avoid exceeding API rate limits.
        api_key (Optional[str | SecretStr]):
            This is an API-specific parameter for validating the current user's identity.
            If a `str` type is provided, it is converted into a `SecretStr`.
        api_specific_parameters (dict[str, APISpecificParameter]):
            A dictionary containing all parameters specific to the current API. API-specific parameters
            include the following:

            1. mailto (Optional[str | SecretStr]):
                An optional email address for receiving feedback on usage from providers. This parameter is
                currently applicable only to the Crossref API.
            2. db (str):
                The parameter used by the `NIH` to direct requests for data to the pubmed database. This parameter
                defaults to pubmed and does not require direct specification.

    Examples:
        >>> from scholar_flux.api import SearchAPIConfig, SearchAPI, provider_registry
        # To create a CROSSREF configuration with minimal defaults and provide an api_specific_parameter:
        >>> config = SearchAPIConfig.from_defaults(provider_name = 'crossref', mailto = 'your_email_here@example.com')
        # The configuration automatically retrieves the configuration for the "Crossref" API.
        >>> assert config.provider_name == 'crossref' and config.base_url == provider_registry['crossref'].base_url
        >>> api = SearchAPI.from_settings(query = 'q', config = config)
        >>> assert api.config == config
        # To retrieve all defaults associated with a provider and automatically read an API key if needed:
        >>> config = SearchAPIConfig.from_defaults(provider_name = 'pubmed', api_key = 'your api key goes here')
        # The API key is retrieved automatically if you have the API key specified as an environment variable.
        >>> assert config.api_key is not None
        # Default provider API specifications are already pre-populated if they are set with defaults.
        >>> assert config.api_specific_parameters['db'] == 'pubmed'  # Required by pubmed and defaults to pubmed.
        # Update a provider and automatically retrieve its API key - the previous API key will no longer apply.
        >>> updated_config = SearchAPIConfig.update(config, provider_name = 'core')
        # The API key should have been overwritten to use core. Looks for a `CORE_API_KEY` env variable by default.
        >>> assert updated_config.provider_name  == 'core' and  updated_config.api_key != config.api_key

    """

    provider_name: str = Field(default="", description="Provider Name or Base URL for the article API")
    base_url: str = Field(default="", description="Base URL for the article API")
    records_per_page: int = Field(20, ge=0, le=1000, description="Number of records per page (1-1000)")
    request_delay: float = Field(-1, description="Minimum delay between requests in seconds")
    api_key: Optional[SecretStr] = Field(None, description="API key if required")
    api_specific_parameters: Optional[dict[str, Any]] = Field(
        default=None,
        description=("Additional parameters specific to the current API to add to the configuration."),
    )
    DEFAULT_RECORDS_PER_PAGE: ClassVar[int] = 25
    DEFAULT_REQUEST_DELAY: ClassVar[float] = 6.1
    DEFAULT_PROVIDER: ClassVar[str] = "PLOS"
    MAX_API_KEY_LENGTH: ClassVar[int] = 512

    @field_validator("provider_name", mode="before")
    def validate_provider_name(cls, v: Optional[str]) -> str:
        """Validates the `provider_name` attribute and triggers a validation error if it is not valid."""

        if v is None:
            return ""

        if not isinstance(v, str):
            raise ValueError(
                f"Incorrect type received for the provider_name. Expected None or string, received {type(v)}"
            )
        return v.strip()

    @field_validator("base_url", mode="before")
    def validate_url_type(cls, v: Optional[str]) -> str:
        """Validates the type for the `base_url` attribute and triggers a validation error if it is not valid."""
        if v is None:
            return ""

        if not isinstance(v, str):
            raise ValueError(f"Incorrect type received for the base_url. Expected None or string, received {type(v)}")
        return v.strip()

    @field_validator("base_url", mode="after")
    def validate_url(cls, v: str):
        """Validates the `base_url` and triggers a validation error if it is not valid."""
        if v and not validate_url(v):
            logger.error(f"The URL provided to the SearchAPIConfig is invalid: {v}")
            raise ValueError(f"The URL provided to the SearchAPIConfig is invalid: {v}")
        return v

    @field_validator("request_delay", mode="before")
    def validate_request_delay(cls, v: Optional[int | float]) -> Optional[int | float]:
        """Sets the request delay (delay between each request) for valid `request delays`. This validator triggers a
        validation error when the request delay is an invalid type.

        If a request delay is left None or is a negative number, this class method returns -1, and further
        validation is performed by `cls.default_request_delay` to retrieve the provider's default request delay.

        If not available, SearchAPIConfig.DEFAULT_REQUEST_DELAY is used.

        """
        if v is not None and not isinstance(v, (int, float)):
            raise ValueError(
                f"Incorrect type received for the request delay parameter. Expected integer or float, received {type(v)}"
            )
        if v is None or v < 0:
            return -1

        if v == 0:
            logger.warning(
                "Request delay is 0: this may result in a `Too Many Requests` (429) status code "
                "if several requests are sent in succession"
            )
        return v

    @classmethod
    def default_request_delay(cls, v: Optional[int | float], provider_name: Optional[str] = None) -> float:
        """Helper method enabling the retrieval of the most appropriate rate limit for the current provider.

        Defaults to the SearchAPIConfig default rate limit when the current provider is unknown and a valid rate limit
        has not yet been provided.

        Args:
            v (Optional[int | float]): The value received for the current request_delay
            provider_name (Optional[str]): The name of the provider to retrieve a rate limit for

        Returns:
            float: The inputted non-negative request delay, the retrieved rate limit for the current provider
                   if available, or the SearchAPIConfig.DEFAULT_REQUEST_DELAY - all in order of priority.

        """
        if isinstance(v, (int, float)) and v >= 0:
            return v

        if provider_config := provider_registry.get(provider_name or ""):
            return provider_config.request_delay
        return cls.DEFAULT_REQUEST_DELAY

    @field_validator("records_per_page", mode="before")
    def set_records_per_page(cls, v: Optional[int]):
        """Sets the records_per_page parameter with the default if the supplied value is not valid:

        Triggers a validation error when records_per_page is an invalid type. Otherwise uses the
        `DEFAULT_RECORDS_PER_PAGE` class attribute if the supplied value is missing or is a negative number.

        """
        if v is not None and not isinstance(v, int):
            raise ValueError(
                f"Incorrect type received for the records_per_page parameter. Expected integer, received {type(v)}"
            )
        if v is None or v < 0:
            return cls.DEFAULT_RECORDS_PER_PAGE
        return v

    @field_validator("api_key", mode="before")
    def validate_api_key(cls, v: Optional[SecretStr | str]) -> Optional[SecretStr]:
        """Validates the `api_key` attribute and triggers a validation error if it is not valid."""

        if v is None:
            return v

        if not isinstance(v, (str, SecretStr)):
            raise ValueError(f"Incorrect type received for the api_key. Expected None or string, received {type(v)}")

        key = v.get_secret_value() if isinstance(v, SecretStr) else v

        if not key:
            raise MissingAPIKeyException("Received an empty string as an api_key, expected None or a non-empty string")

        if len(key) > cls.MAX_API_KEY_LENGTH:
            raise ValueError(
                f"The received api_key is more than {cls.MAX_API_KEY_LENGTH} characters long - verify that the api_key is correct"
            )

        if len(key) < 20:
            logger.warning("The received api_key is less than 20 characters long - verify that the api_key is correct")
        elif len(key) > 256:
            logger.warning("The received api_key is more than 256 characters long - verify that the api_key is correct")

        return SecretStr(v) if not isinstance(v, SecretStr) else v

    @model_validator(mode="after")
    def validate_search_api_config_parameters(self) -> Self:
        """Validation method that resolves URLs and/or provider names to provider_info when one or the other is not
        explicitly provided.

        Occurs as the last step in the validation process.

        """
        self.base_url, self.provider_name, provider_info = self._prepare_provider_info(
            self.base_url, self.provider_name
        )

        logger.info(f"Initializing SearchAPIConfig with provider_name: {self.provider_name}")

        # identify the provider's parameter map - used for identifying parameters specific to the api
        parameter_map = provider_info.parameter_map if provider_info else None
        provider_name = provider_info.provider_name if provider_info else None
        self.request_delay = self.default_request_delay(self.request_delay, provider_name)

        if not parameter_map:
            return self

        if not self.api_key:
            # attempts to load an API key if the provider config is required and contains an API key that can be read
            self.api_key = self._load_api_key(provider_info)

        # Remaining steps involve preparing api specific parameters based on the identified api mappings
        api_specific_parameter_mappings = parameter_map.api_specific_parameters or {}
        api_specific_parameter_values = self.api_specific_parameters or {}

        self.api_specific_parameters = self._prepare_api_specific_parameters(
            api_specific_parameter_mappings, api_specific_parameter_values
        )

        return self

    @classmethod
    def _prepare_api_specific_parameters(
        cls,
        api_specific_parameter_mappings: dict[str, APISpecificParameter],
        api_specific_parameter_values: dict[Any, Any],
    ) -> dict[str, Any]:
        """Helper method for extracting both necessary and/or default API-specific parameters from the configuration."""
        if api_specific_parameter_mappings or api_specific_parameter_values:
            ignored_keys = api_specific_parameter_values.keys() - api_specific_parameter_mappings.keys()

            if ignored_keys:
                logger.warning(
                    "The following parameters are ignored by default, as they are not "
                    f"defined in the Provider's Parameter map by default: {ignored_keys}"
                )

            logger.info("Attempting to retrieve additional API-specific parameters")
            api_specific_parameter_values = {
                parameter: cls._validate_api_specific_parameter(
                    api_specific_parameter_values.get(parameter, parameter_metadata.default), parameter_metadata
                )
                for parameter, parameter_metadata in api_specific_parameter_mappings.items()
            }
        return api_specific_parameter_values

    @classmethod
    def _remove_nonprovider_config_parameters(
        cls, config_parameters: dict[str, Any], current_provider: Optional[str]
    ) -> dict[str, Any]:
        """Helper method for removing unneeded API-specific parameters that aren't defined for the current provider."""
        current_config = APIParameterConfig.get_defaults(current_provider or "")
        valid_config_parameters = set(
            current_config.show_parameters() + list(SearchAPIConfig.model_fields.keys()) if current_config else []
        )

        removal_fields = config_parameters.keys() - valid_config_parameters
        return {field: value for field, value in config_parameters.items() if field not in removal_fields}

    @classmethod
    def _prepare_provider_info(
        cls, base_url: str, provider_name: str, fallback_to_default: bool = True
    ) -> tuple[str, str, Optional[ProviderConfig]]:
        """Helper method to identify the base_url or provider_name in addition to provider info when one is missing.

        The provider information is also returned if available to assist with later validation steps.

        """
        provider_info = None
        # account for incomplete information in the SearchAPIConfig
        if not base_url and not provider_name:

            if not fallback_to_default:
                raise MissingProviderException("Either a base URL or a valid provider name must be specified.")

            logger.info(
                f"Neither a base URL nor a provider name was provided - falling back to default: {cls.DEFAULT_PROVIDER}"
            )

            if provider_info := provider_registry.get(cls.DEFAULT_PROVIDER):
                base_url = provider_info.base_url
                provider_name = provider_info.provider_name
            else:
                raise MissingProviderException(
                    "Either a base URL or a valid provider name must be specified. "
                    f"SearchAPIConfig could not fall back to the default, {cls.DEFAULT_PROVIDER}"
                )

        # attempt to retrieve the base URL from the provider name if a base URL is not provided
        elif not base_url:
            provider_info = provider_registry.get(provider_name) if not base_url and provider_name else None

            if not provider_info:
                raise MissingProviderException(
                    f"A base URL was not specified and the provider could not be identified from the provider, {provider_name}"
                )

            base_url = provider_info.base_url

        # attempt to retrieve the name of the provider if the provider name is not provided
        elif not provider_name:
            provider_info = provider_registry.get_from_url(base_url)

            # indicate the name of the provider from the provider info if not already provided
            provider_name = provider_info.provider_name if provider_info else cls._extract_url_basename(base_url)
        else:
            base_url, provider_name, provider_info = cls._resolve_provider_config(base_url, provider_name)

        return base_url, provider_name, provider_info

    @classmethod
    def _resolve_provider_config(cls, base_url: str, provider_name: str) -> tuple[str, str, Optional[ProviderConfig]]:
        """Helper method to resolve mismatches between the URL and the provider_name when both are provided. The default
        behavior is to always prefer a provided base_url over the provider_name to offer maximum flexibility.

        Args:
            base_url (str): The URL where API requests will be sent
            provider_name (str): The provider of the API where requests will be made
        Returns:
            tuple[str, str, Optional[ProviderConfig]]: A tuple containing the base URL, provider name, and the
            provider config in that order.

            If neither the base URL and provider name resolve to a known provider, they will be returned as is.

        """
        # if both provider name and information is provided, prioritize the url first.
        provider_from_url = provider_registry.get_from_url(base_url) if base_url else None
        provider_from_name = provider_registry.get(provider_name) if provider_name else None
        provider_info = provider_from_url or provider_from_name

        if isinstance(provider_from_url, ProviderConfig):
            if (
                isinstance(provider_from_name, ProviderConfig)
                and provider_from_url.provider_name != provider_from_name.provider_name
            ):

                logger.warning(
                    f"The URL, {base_url} and provider_name {provider_name} were both provided, "
                    "each resolving to two different providers. \nPreferring provider: "
                    f"{provider_from_url.provider_name} resolved from the provided URL."
                )

            elif not isinstance(provider_from_name, ProviderConfig):
                logger.warning(
                    f"The provided base URL resolves to a provider while the provider name, "
                    f"{provider_name}, does not. \nPreferring provider: "
                    f"{provider_from_url.provider_name} resolved from the provided URL."
                )

            logger.info(f"Defaulting to the use of the provider_name resolved from the URL, {base_url}")
            provider_name = provider_from_url.provider_name

        elif isinstance(provider_from_name, ProviderConfig):
            url_basename = cls._extract_url_basename(base_url)
            logger.warning(
                f"The provided URL does not resolve to a default provider while the "
                f"provided name resolves to API, {provider_from_name.provider_name}.\n"
                f"The default behavior is to assume that the provided URL is a new provider "
                f"and use the base of the URL, '{url_basename}', as the provider name. "
                "If this is not the expected behavior, omit the `base_url` parameter entirely."
            )

            provider_name = url_basename
        elif provider_name and base_url:
            logger.info(
                "Initializing the SearchAPIConfig non-default parameters: "
                f"base_url={base_url} and provider_name={provider_name}"
            )
        return base_url, provider_name, provider_info

    @classmethod
    def _validate_api_specific_parameter(cls, parameter_value: Any, parameter_metadata: APISpecificParameter) -> Any:
        """Helper method for validating parameters during api-specific parameter validation."""
        logger.debug(f"Validating the value for the additional parameter, {parameter_metadata.name}")
        if parameter_value is None and parameter_metadata.default is None and parameter_metadata.required:
            raise MissingAPISpecificParameterException(
                f"The value for the additional parameter, {parameter_metadata.name}, "
                "was not provided and has no default"
            )

        if parameter_metadata.validator:
            parameter_value = parameter_metadata.validator(parameter_value)

        return parameter_value

    @classmethod
    def _extract_url_basename(cls, url: str) -> str:
        """Extracts the main site name from a URL by removing everything before 'www' and everything including and after
        the top-level domain.

        Args:
            url (str): The URL to process.

        Returns:
            str: The main site name.

        """
        # Parse the URL to extract the hostname
        parsed_url = urlparse(url)
        hostname = parsed_url.hostname

        if not hostname:
            # Handle case when urlparse fails to get hostname
            hostname = url.split("/")[0]

        # Regular expression to match the main site name in the hostname
        pattern = re.compile(r"^(?:.*\.)?([a-zA-Z0-9-_]+)\.(?:com|org|net|ac\.uk|io|gov|edu)")
        match = pattern.search(hostname)

        if match:
            return match.group(1)

        if url:
            logger.warning(f"Couldn't extract the base URL for the URL, '{url}'. Falling back to using the host name")

        return hostname  # fall back to using the hostname - more preferable than omitting entirely

    @property
    def url_basename(self) -> str:
        """Uses the _extract_url_basename method from the provider URL associated with the current config instance."""
        return self._extract_url_basename(self.base_url)

    @classmethod
    def _load_api_key(cls, provider_info: Optional[ProviderConfig] = None) -> Optional[SecretStr]:
        """Helper method that determines whether or not the API key associated with a specific provider is loaded. This
        method is generally called in circumstances where a key is required but not provided. It will attempt to revert
        to an API key if the provider_config indicates that there is an environment variable to look for that may
        contain the variable.

        Args:
            provider_info (ProviderConfig):
                Config for the API Provider. This config will be checked to determine whether there is an api key to
                potentially load and by what name.
        Returns:
            Optional[SecretStr]: A key converted to a SecretStr if successfully read, otherwise None

        """
        # skip attempting to load an API key altogether if an environment variable for the config does not exist
        if not isinstance(provider_info, ProviderConfig) or provider_info.api_key_env_var is None:
            return None

        logger.info(
            "Attempting to read an API key from the environment variable "
            f"for the provider, {provider_info.provider_name}..."
        )

        # attempt to load the api key if a variable is referenced in the provider config
        if api_key := config_settings.get(provider_info.api_key_env_var):
            logger.info(f"API key successfully loaded for the provider, {provider_info.provider_name}")
            return SecretStr(api_key) if isinstance(api_key, str) else api_key

        if provider_info.parameter_map.api_key_required:
            logger.warning(f"Could not load the required API key for: {provider_info.provider_name}")
        return None

    @classmethod
    def update(cls, current_config: SearchAPIConfig, **overrides) -> SearchAPIConfig:
        """Create a new SearchAPIConfig by updating an existing config with new values and/or switching to a different
        provider. This method ensures that the new provider's base_url and defaults are used if provider_name is given,
        and that API-specific parameters are prioritized and merged as expected.

        Args:
            current_config (SearchAPIConfig): The existing configuration to update.
            **overrides: Any fields or API-specific parameters to override or add.

        Returns:
            SearchAPIConfig: A new config with the merged and prioritized values.

        """
        # Start with the current config as a dict, omitting base_url if switching providers
        config_dict = current_config.model_dump() or {}

        # resolve provider inconsistencies: highest priority = base_url, second = provider_name
        # retrieve provider from base URL if couldn't retrieve it from the provider name
        previous_provider_name = ProviderConfig._normalize_name(current_config.provider_name)
        provider_name = overrides.get("provider_name", "")
        base_url = overrides.get("base_url", "")
        provider_info = None

        try:
            base_url, provider_name, provider_info = cls._prepare_provider_info(
                base_url=base_url, provider_name=provider_name, fallback_to_default=False
            )
        except MissingProviderException:
            logger.debug(
                "Neither a provider nor base URL were provided: using configuration from the original config..."
            )

        previous_config_url = cls._extract_url_basename(config_dict.get("base_url", ""))
        current_config_url = cls._extract_url_basename(base_url or "")

        # determines whether to replace the API key with one more specific to the provider
        if provider_info is not None:
            # if a previous api key is not needed, remove the previous configuration's key
            if (
                cls._extract_url_basename(provider_info.base_url) != previous_config_url
                and config_dict.get("api_key") is not None
            ):
                if provider_info.parameter_map.api_key_parameter is None:
                    logger.debug(
                        f"An API key is not required for the provider, {provider_info.provider_name}. Omitting.."
                    )
                config_dict.pop("api_key")

            # use the previous base URL and provider info if the current options are associated with a provider
            overrides["base_url"] = base_url or provider_info.base_url
            overrides["provider_name"] = provider_name or provider_info.provider_name

        else:
            # if a provider is not associated with the current url/provider name, remove the previous key
            if current_config_url != previous_config_url and current_config_url:
                logger.debug("The previous API key may not be applicable to the new provider. Omitting..")
                config_dict.pop("api_key", None)

            overrides["provider_name"] = provider_name or config_dict.get("provider_name")

        # Flatten and retrieve any nested api_specific_parameters
        api_specific_parameters = config_dict.pop("api_specific_parameters", None) or {}
        api_specific_parameters |= overrides.pop("api_specific_parameters", None) or {}

        # Merge in explicit overrides (these take highest precedence)
        config_dict |= {k: v for k, v in api_specific_parameters.items() if v is not None}
        config_dict |= {k: v for k, v in overrides.items() if v is not None}

        # if the configuration changed providers, then update the API-specific parameter list
        if provider_info and provider_info.provider_name != previous_provider_name:
            config_dict = cls._remove_nonprovider_config_parameters(config_dict, provider_info.provider_name)
        # make the additional parameters a harmonized field in the dictionary
        config_dict = cls._extract_api_specific_parameter(config_dict)

        return cls.model_validate(config_dict)

    @classmethod
    def _extract_api_specific_parameter(cls, config_dict: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """Helper class method to ensure that api_specific_parameters are handled accordingly in constructor methods
        that can receive API-specific parameters as keyword arguments.

        Args:
            config_dict (Optional[dict]): The dictionary to extract additional parameters from as a separate keyword.
        Returns:
            The original dictionary that now includes all API-specific parameters as a separate dictionary field.
            If the original config is empty or None, this method will return an empty dictionary instead.

        """
        if not config_dict:
            return {}

        core_fields = set(cls.model_fields)

        core_parameters = {parameter: value for parameter, value in config_dict.items() if parameter in core_fields}

        api_specific_parameters = core_parameters.pop("api_specific_parameters", {})
        api_specific_parameters.update(
            {parameter: value for parameter, value in config_dict.items() if parameter not in core_fields}
        )

        class_parameter_dict = core_parameters | api_specific_parameters
        class_parameter_dict |= {"api_specific_parameters": api_specific_parameters}
        return class_parameter_dict

    @classmethod
    def from_defaults(cls, provider_name: str, **overrides) -> SearchAPIConfig:
        """Uses the default configuration for the chosen provider to create a SearchAPIConfig object containing
        configuration parameters. Note that additional parameters and field overrides can be added via the `**overrides`
        field.

        Args:
            provider_name (str): The name of the provider to create the config
            **overrides: Optional keyword arguments to specify overrides and additional arguments

        Returns:
            SearchAPIConfig: A default APIConfig object based on the chosen parameters

        """
        provider = provider_registry.get(provider_name)

        if not provider:
            raise NotImplementedError(f"Provider '{provider_name}' config not implemented")

        custom_parameter_config = cls._extract_api_specific_parameter(overrides)
        custom_parameter_config["provider_name"] = provider.provider_name

        config_dict: dict[str, Any] = provider.search_config_defaults() | custom_parameter_config

        api_key = config_dict.get("api_key")
        if api_key and isinstance(api_key, str):
            config_dict["api_key"] = SecretStr(api_key)

        return cls.model_validate(config_dict)

    def structure(self, flatten: bool = False, show_value_attributes: bool = True) -> str:
        """Helper method for retrieving a string representation of the overall structure of the current
        SearchAPIConfig."""
        return generate_repr(self, flatten=flatten, show_value_attributes=show_value_attributes)

    def __repr__(self) -> str:
        """Helper method for displaying the config in a user-friendly manner."""
        return self.structure()


__all__ = ["SearchAPIConfig"]
