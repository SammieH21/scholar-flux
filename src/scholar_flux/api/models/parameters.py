from pydantic import BaseModel, Field, model_validator
from .provider_info import ProviderInfo
from .providers import PROVIDER_DEFAULTS
from typing import  List, Optional, Dict, Any, Union, ClassVar
from .base import BaseAPIParameterMap
from ...exceptions.api_exceptions import APIParameterException
import logging

logger = logging.getLogger(__name__)

class APIParameterMap(BaseAPIParameterMap):
    """
    Extends BaseAPIParameterMap by adding validation and setting default values
    for specific attributes related to API keys and additional parameter names.

    Attributes:
        query (str): The API-specific parameter name for the search query.
        start (str): The API-specific parameter name for pagination (either start index or page number).
        records_per_page (str): The API-specific parameter name for records per page.
        api_key_param (Optional[str]): The API-specific parameter name for the API key.
        api_key_required (bool): Whether the API key is required by this API.
        auto_calculate_page (bool): If True, calculates start index from page; if False, passes page number directly.
        additional_parameter_names (Dict[str, str]): Additional universal to API-specific parameter mappings.
    """

    @model_validator(mode="before")
    def set_default_api_key_param(cls, values: dict[str, Any]) -> dict[str, Any]:
        """
        Sets the default for the api key parameter in the case where where api_key_required is set to True
        and api_key_param is None

        Args:
            values (dict[str, Any]): The dictionary of attributes to validate 

        Returns:
            dict[str, Any]: The updated parameter values passed to the APIParameterMap.
                            `api_key_param` is set to "api_key" if key is required but not specified
        """
        if values.get("api_key_required") and not values.get("api_key_param"):
            values["api_key_param"] = "api_key"
        return values

    @model_validator(mode="before")
    def validate_additional_parameter_names(cls, values: dict[str, Any]) -> dict[str, Any]:
        """
        Validates the additional mappings provided to the APIParameterMap,
        ensuring a dictionary with keys and values that are strings.

        Args:
            values (dict[str, Any]): The dictionary of attribute values to validate.

        Returns:
            dict[str, Any]: The updated dictionary if validation passes.

        Raises:
            APIParameterException: If `additional_parameter_names` is not a dictionary or contains non-string keys/values.
        """
        additional_parameter_names = values.get("additional_parameter_names", {})
        if not isinstance(additional_parameter_names, dict):
            raise APIParameterException("additional_parameter_names must be a dict")
        for k, v in additional_parameter_names.items():
            if not isinstance(k, str) or not isinstance(v, str):
                raise APIParameterException("Keys and values in additional_parameter_names must be strings")
        return values


    @classmethod
    def from_defaults(cls, provider_name: str,
                      **additional_parameters) -> "APIParameterMap":
        """
        Factory method that uses the `APIParameterMap.get_defaults` classmethod
        to retrieve the provider config. Raises an error if the provider does not exist

        Args:
            provider_name (str): The name of the API to create the parameter map for.
            additional_parameters (dict): Additional parameter mappings.

        Returns:
            APIParameterMap: Configured parameter map for the specified API.

        Raises:
            NotImplementedError: If the API name is unknown.
        """


        parameter_map = cls.get_defaults(provider_name, **additional_parameters)

        if parameter_map is None:
            logger.error(f"Default APIParameterMap for '{provider_name}' not implemented")
            raise NotImplementedError(f"The requested API default config '{provider_name}' has not been implemented")
        
        return parameter_map

    @classmethod
    def get_defaults(cls, provider_name: str, **additional_parameters) -> Optional["APIParameterMap"]:
        """
        Factory method to create APIParameterMap instances with sensible defaults for
        known APIs. Returns `None` in the event that an APIParameterMap cannot be found.

        Valid providers (as indicated in PROVIDER_DEFAULTS) include:
            - springernature
            - plos
            - core
            - crossref

        Args:
            provider_name (str): The name of the API to create the parameter map for.
            additional_parameters (dict): Additional parameter mappings.

        Returns:
            Optional[APIParameterMap]: Configured parameter map for the specified API.
        """
        provider_info = PROVIDER_DEFAULTS.get(provider_name)

        if not provider_info:
            return None

        defaults = provider_info.parameter_map
        class_vars = defaults.to_dict() if isinstance(defaults, BaseAPIParameterMap) else defaults

        if additional_parameters:
            class_vars = class_vars | additional_parameters

        return cls(**class_vars)

class APIParameterConfig:
    """
    Uses an APIParameterMap instance and runtime parameter values to build
    request parameter dictionaries for API calls.

    Attributes:
        param_map (APIParameterMap): The mapping of universal to API-specific parameter names.
    """

    def __init__(
        self,
        param_map: APIParameterMap,
    ):
        """
        Initializes the APIParameterConfig.

        Args:
            param_map (APIParameterMap): The parameter mapping configuration.
        """
        self.param_map = param_map



    def _calculate_start_index(self, page: int, records_per_page: int) -> int:
        """
        Calculate the starting record index for a given page.

        Args:
            page (int): The page number (1-based).
            records_per_page (int): Number of records per page.

        Returns:
            int: The calculated start index.
        """
        return 1 + (page - 1) * records_per_page

    def build_params(
        self,
        query: Optional[str],
        page: int,
        records_per_page: int,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Build the dictionary of request parameters using the parameter map and provided values.

        Args:
            query (Optional[str]): The search query string.
            page (int): The page number for pagination (1-based).
            records_per_page (Union[str, int]): Number of records to fetch per page.
            **kwargs: Additional parameters to include, keyed by universal parameter names.

        Returns:
            Dict[str, Any]: The fully constructed API request parameters dictionary,
                            with keys as API-specific parameter names and values as provided.
        """

        if not isinstance(page,int) or page < 1:
            logger.error("f'Expected a non-zero integer for page. Received '{page}'")
            raise APIParameterException(f"Expected a non-zero integer for page. Received '{page}'")

        start_index = self._calculate_start_index(page, int(records_per_page)) if \
                self.param_map.auto_calculate_page else page

        # Base parameters mapped to API-specific names
        params = {
            self.param_map.query: query,
            self.param_map.start: start_index,
            self.param_map.records_per_page: records_per_page,
        }

        # Include additional parameters provided via kwargs by mapping universal keys to API-specific names
        extra_params = {
            api_param_name: kwargs.get(universal_key, None)
            for universal_key, api_param_name in self.param_map.additional_parameter_names.items()
        }

        params.update(extra_params)

        # Include API key if provided
        if self.param_map.api_key_param:
            key_name = self.param_map.api_key_param
            api_key=kwargs.get('api_key')

            # set the api key if it exists
            if api_key:
                params[key_name] = api_key

            # raise an error if an api key is required, but does not exist
            elif self.param_map.api_key_required:
                logger.error("API key required but not provided")
                raise APIParameterException("API key is required but not provided")



        # Filter out None values from parameters
        return {k: v for k, v in params.items() if v is not None}

    @classmethod
    def get_defaults(cls, provider_name: str,
                      **additional_parameters) -> Optional["APIParameterConfig"]:
        """
        Factory method to create APIParameterConfig instances with sensible defaults for
        known APIs. Avoids throwing an error if the provider name does not already exist

        Args:
            provider_name (str): The name of the API to create the parameter map for.
            additional_parameters (dict): Additional parameter mappings.

        Returns:
            Optional[APIParameterConfig]: Configured parameter config instance for the specified API.
                                            Returns None if a mapping for the provider_name isn't retrieved
        """

        param_map = APIParameterMap.get_defaults(provider_name, **additional_parameters)
        return cls(param_map) if param_map else None

    @classmethod
    def from_defaults(cls, provider_name: str,
                      **additional_parameters) -> "APIParameterConfig":
        """
        Factory method to create APIParameterConfig instances with sensible defaults for
        known APIs. If the provider_name does not exist, the code will raise an exception

        Args:
            provider_name (str): The name of the API to create the parameter map for.
            api_key (Optional[str]): API key value if required.
            additional_parameters (dict): Additional parameter mappings.

        Returns:
            APIParameterConfig: Configured parameter config instance for the specified API.

        Raises:
            NotImplementedError: If the API name is unknown.

        """

        param_map = APIParameterMap.from_defaults(provider_name, **additional_parameters)
        return cls(param_map)
