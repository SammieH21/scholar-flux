# /api/models/api_parameters.py
"""The scholar_flux.api.models.api_parameters module implements the APIParameterMap and APIParameterConfig classes.

These two classes are designed for flexibility in the creation and handling of API Responses given provider-specific
differences in request parameters and configuration.

Classes:
    APIParameterMap:
        Extends the BaseAPIParameterMap to provide factory functions and utilities to more
        efficiently retrieve and use default parameter maps.
    APIParameterConfig:
        Uses or creates an APIParameterMap to prepare request parameters according to the
        specifications of the current provider's API.

"""

from __future__ import annotations
from pydantic import SecretStr, model_validator, ValidationError
from typing import overload, Any, ClassVar, TYPE_CHECKING
from scholar_flux.api.models.base_parameters import BaseAPIParameterMap, APISpecificParameter
from scholar_flux.exceptions.api_exceptions import APIParameterException, APIKeyValidationException
from scholar_flux.utils.repr_utils import generate_repr_from_string
from scholar_flux.utils.helpers import with_fallback
from scholar_flux.utils.settings_utils import SettingsDict, SettingsDictType
from scholar_flux.security import SecretUtils
from scholar_flux.api.providers import provider_registry
from pydantic.dataclasses import dataclass
import logging

if TYPE_CHECKING:
    from collections.abc import Callable


logger = logging.getLogger(__name__)


class APIParameterMap(BaseAPIParameterMap):
    """Extends BaseAPIParameterMap by adding validation and the optional retrieval of provider defaults for known APIs.

    This class also specifies default mappings for specific attributes such as API keys and additional parameter names.

    Attributes:
        query (str): The API-specific parameter name for the search query.
        start (Optional[str]): The API-specific parameter name for pagination (start index or page number).
        records_per_page (str): The API-specific parameter name for records per page.
        api_key_parameter (Optional[str]): The API-specific parameter name for the API key.
        api_key_required (bool): Indicates whether an API key is required.
        api_key_in_headers (bool): Indicates whether API keys are transmitted via headers or parameters (default).
        api_key_scheme (str | None): Scheme that prefixes the api key in the request header (i.e., `Bearer [API_KEY]`).
        auto_calculate_page (bool): If True, calculates start index from page; if False, passes page number directly.
        zero_indexed_pagination (bool): If True, treats 0 as an allowed page value when retrieving data from APIs.
        api_specific_parameters (Dict[str, str]): Additional universal to API-specific parameter mappings.

    """

    @model_validator(mode="before")
    @classmethod
    def set_default_api_key_parameter(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Sets the default for the API key parameter when `api_key_required`=True and `api_key_parameter` is None.

        Args:
            values (dict[str, Any]): The dictionary of attributes to validate

        Returns:
            dict[str, Any]:
                The updated parameter values passed to the APIParameterMap. `api_key_parameter` is set to
                `APIParameterMap.DEFAULT_API_KEY_PARAMETER` if an API key is required but not specified.

        """
        if values.get("api_key_required") and not values.get("api_key_parameter"):
            values["api_key_parameter"] = cls.DEFAULT_API_KEY_PARAMETER
        return values

    @model_validator(mode="before")
    @classmethod
    def validate_api_specific_parameter_mappings(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Validates the additional mappings provided to the APIParameterMap.

        This method validates that the input is dictionary of mappings that consists of only string-typed keys mapped
        to API-specific parameters as defined by the APISpecificParameter class.

        Args:
            values (dict[str, Any]): The dictionary of attribute values to validate.

        Returns:
            dict[str, Any]: The updated dictionary if validation passes.

        Raises:
            APIParameterException: If `api_specific_parameters` is not a dictionary or contains non-string keys/values.

        """
        api_specific_parameters = values.get("api_specific_parameters", {})

        if not isinstance(api_specific_parameters, dict):
            raise APIParameterException(
                f"All api_specific_parameters must be a dict. Received type {api_specific_parameters}"
            )

        for parameter_name, parameter_metadata in api_specific_parameters.items():
            if not isinstance(parameter_name, str) or not isinstance(parameter_metadata, (dict, APISpecificParameter)):
                raise APIParameterException(
                    "The `api_specific_parameters` input must be a dictionary that maps a parameter (string) to either "
                    "a dictionary containing `APISpecificParameter` fields or a direct `APISpecificParameter` class. "
                    f"Instead, a key-value pair with the following types was received: {type(parameter_name)}: {type(parameter_metadata)}"
                )
        return values

    @classmethod
    def from_defaults(cls, provider_name: str, **additional_parameters: Any) -> APIParameterMap:
        """Factory method that uses the `APIParameterMap.get_defaults` classmethod to retrieve the provider config.

        Raises an error if the provider does not exist.

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
    def get_defaults(cls, provider_name: str, **additional_parameters: Any) -> APIParameterMap | None:
        """Retrieves the APIParameterMap associated with a known API, returning None if the provider cannot be found.

        This class method attempts to pull from the list of known providers defined in the
        `scholar_flux.api.providers.provider_registry` and returns `None` if an APIParameterMap for the
        provider cannot be found.

        Using the `additional_parameters` keyword arguments, users can specify optional overrides for
        specific parameters if needed. This is helpful in circumstances where an API's specification overlaps
        with that of a known provider.

        Valid providers (as indicated in provider_registry) include:

        - springernature
        - plos
        - arxiv
        - openalex
        - core
        - crossref

        Args:
            provider_name (str): The name of the API provider to retrieve the parameter map for.
            additional_parameters (dict): Additional parameter mappings.

        Returns:
            Optional[APIParameterMap]: Configured parameter map for the specified API.

        """
        provider_info = provider_registry.get(provider_name)

        if not provider_info:
            return None

        defaults = provider_info.parameter_map
        class_vars = defaults.to_dict() if isinstance(defaults, BaseAPIParameterMap) else defaults

        if additional_parameters:
            class_vars = class_vars | additional_parameters

        return cls.model_validate(class_vars)


@dataclass
class APIParameterConfig:
    """Uses an APIParameterMap instance and runtime parameter values to build parameter dictionaries for API requests.

    Args:
        parameter_map (APIParameterMap): The mapping of universal to API-specific parameter names.

    Class Attributes:
        DEFAULT_CORRECT_ZERO_INDEX (bool):
            Autocorrects zero-indexed API parameter building specifications to only accept positive values when True.
            If otherwise False, page calculation APIs will start from page 0 if zero-indexed (i.e., arXiv).

    Examples:
        >>> from scholar_flux.api import APIParameterConfig, APIParameterMap
        >>> # the API parameter map is defined and used to resolve parameters to the API's language
        >>> api_parameter_map = APIParameterMap(
        ... query='q', records_per_page = 'pagesize', start = 'page', auto_calculate_page = False
        ... )
        # The APIParameterConfig defines class and settings that indicate how to create requests
        >>> api_parameter_config = APIParameterConfig(api_parameter_map, auto_calculate_page = False)
        # Builds parameters using the specification from the APIParameterMap
        >>> page = api_parameter_config.build_parameters(query= 'ml', page = 10, records_per_page=50)
        >>> print(page)
        # OUTPUT {'q': 'ml', 'page': 10, 'pagesize': 50}

    """

    parameter_map: APIParameterMap
    DEFAULT_CORRECT_ZERO_INDEX: ClassVar[bool] = True

    @property
    def map(self) -> APIParameterMap:
        """Helper property that is an alias for the APIParameterMap attribute.

        The APIParameterMap maps all universal parameters to the parameter names specific to the API provider.

        Returns:
            APIParameterMap:
                The mapping that the current APIParameterConfig will use to build a dictionary of parameter requests
                specific to the current API.

        """
        return self.parameter_map

    def build_parameters(
        self,
        query: str | None,
        page: int | None,
        records_per_page: int,
        include_api_key: bool | None = None,
        **api_specific_parameters: Any,
    ) -> SettingsDictType:
        """Builds the dictionary of request parameters using the current parameter map and provided values at runtime.

        Args:
            query (Optional[str]): The search query string.
            page (Optional[int]): The page number for pagination (1-based).
            records_per_page (int): Number of records to fetch per page.
            include_api_key (bool | None):
                Indicates whether an API key should be included. If `None`, an API key is added when required.
            **api_specific_parameters: Additional API-specific parameters to include.

        Returns:
            Dict[str, Any]:
                The fully constructed API request parameters dictionary, with keys as API-specific parameter names and
                values as provided.

        """
        start_index = self._calculate_start_index(page, records_per_page)

        # Base parameters mapped to API-specific names
        parameters = {
            self.parameter_map.query: query,
            self.parameter_map.start: start_index,
            self.parameter_map.records_per_page: records_per_page,
        }

        parameters = self._get_api_specific_parameters(parameters, **api_specific_parameters)

        if include_api_key is True or (include_api_key is None and not self.parameter_map.api_key_in_headers):
            parameters = self._include_api_key(parameters, **api_specific_parameters)
        else:
            parameters.pop(self.parameter_map.api_key_parameter, None)
            parameters.pop(self.parameter_map.DEFAULT_API_KEY_PARAMETER, None)

        # Filter out None values from parameters
        prepared_parameters = {k: v for k, v in parameters.items() if k is not None and v is not None}
        return SettingsDict(prepared_parameters) if isinstance(parameters, SettingsDict) else prepared_parameters

    def _calculate_start_index(self, page: int | None = None, records_per_page: int | None = None) -> int | None:
        """Helper method for retrieving the start index as an offset and records_per_page.

        Note that the behavior of the pagination depends on whether 0 is allowed for an API and whether pagination
        is calculated on the server or client side.

        If `auto_calculate_page` is True, the page number input is returned as a regular page number and the offset
        is calculated on the server side. Otherwise, the offset is calculated in this helper function.


        Page is allowed to be optional on the condition that the API does not require the page parameter

        Args:
            page (int): The page number (1-based).
            records_per_page (int): Number of records per page.

        Returns:
            int: The calculated start index.

        Raises:
            APIParameterException:
                If page is not a valid value (integer > 0) or, when otherwise required, records per page is missing
                or contains an invalid value.

        """
        if not self.parameter_map.start:
            return None

        zero_indexed = self.parameter_map.zero_indexed_pagination
        adjusted_page = page - 1 if zero_indexed and isinstance(page, int) and self.DEFAULT_CORRECT_ZERO_INDEX else page
        start = int(not zero_indexed)  # 0 if zero-indexed, 1 if one-indexed
        if not isinstance(adjusted_page, int) or (adjusted_page < start):
            expected = "non-negative" if zero_indexed and not self.DEFAULT_CORRECT_ZERO_INDEX else "positive"
            logger.error(f"Expected a {expected} integer for page. Received '{page}'")
            raise APIParameterException(f"Expected a {expected} integer for page. Received '{page}'")

        if not isinstance(records_per_page, int) or records_per_page < 1:
            logger.error(f"Expected a non-zero integer for records_per_page. Received '{records_per_page}'")
            raise APIParameterException(
                f"Expected a non-zero integer for records_per_page. Received '{records_per_page}'"
            )

        if not self.parameter_map.auto_calculate_page:
            return adjusted_page

        return start + (adjusted_page - start) * records_per_page

    def _get_api_specific_parameters(
        self, parameters: SettingsDictType | None, **api_specific_parameters: Any
    ) -> SettingsDictType:
        """Helper method for extracting API-specific parameters from additional keyword arguments.

        These additional parameters are retrieved from `**api_specific_parameters` when available and not already
        provided in the `parameters` dictionary.

        Args:
            parameters (dict[str, Any] | SettingsDict): The dictionary of parameters being built for a request.
            api_specific_parameters (dict): A list of key-value pairs from which to extract any additional parameters.

        Returns:
            dict: With or without the additional_parameters depending on whether any have been provided.

        Raises:
            APIParameterException: If the parameters argument is not a dictionary

        """
        # if parameters is None, create an empty dictionary
        parameters = parameters if parameters is not None else {}

        # raise an error if parameters is not actually a dictionary
        if not isinstance(parameters, (dict, SettingsDict)):
            raise APIParameterException(
                f"Expected `parameters` to be a dictionary, instead received {type(parameters)}"
            )

        api_parameter_mappings = self.parameter_map.model_dump()
        api_specific_parameter_names = api_parameter_mappings.pop("api_specific_parameters")

        filtered_api_specific_parameters = {
            parameter: value for parameter, value in api_specific_parameters.items() if value is not None
        }

        if duplicated_keys := filtered_api_specific_parameters.keys() & parameters.keys():
            logger.warning(f"Overwriting the following keys that have been specified twice: {list(duplicated_keys)}")

        # Include additional parameters provided via api_specific_parameters by mapping universal keys to API-specific names
        extra_parameters = {
            api_parameter_name: api_specific_parameters.get(api_parameter_name)
            for api_parameter_name in duplicated_keys.union(api_specific_parameter_names)
            if api_specific_parameters.get(api_parameter_name) is not None
        }

        parameters = parameters | extra_parameters  # so extractions don't modify the original object

        return parameters

    def show_parameters(self) -> list:
        """Helper method to show the complete list of all parameters that can be found in the current_mappings.

        Returns:
            List: The complete list of all universal and API-specific parameters corresponding to the current API

        """
        return self.parameter_map.show_parameters()

    def add_parameter(
        self,
        name: str,
        description: str | None = None,
        validator: Callable[[Any], Any] | None = None,
        default: Any = None,
        required: bool = False,
        inplace: bool = True,
    ) -> APIParameterConfig:
        """Passes keyword arguments to the current parameter map to add a new API-specific parameter to its config.

        Args:
            name (str):
                The name of the parameter used when sending requests to APIs.
            description (str):
                A description of the API-specific parameter.
            validator (Optional[Callable[[Any], Any]]):
                An optional function/method for verifying and pre-processing parameter input based on required types,
                constrained values, etc.
            default (Any):
                A default value used for the parameter if not specified by the user
            required (bool):
                Indicates whether the current parameter is required for API calls.
            inplace (bool):
                A flag that, if True, modifies the current parameter map instance in place. If False, it returns a new
                parameter map that contains the added parameter, while leaving the original unchanged.

                Note: If this instance is shared (e.g., retrieved from provider_registry), changes will affect all
                references to this parameter map. if `inplace=True`.

        Returns:
            APIParameterConfig:
                An APIParameterConfig with the updated parameter map. If `inplace=True`, the original is returned.
                Otherwise a new parameter map containing an updated `api_specific_parameters` dict is returned.

        """
        parameter_map = self.parameter_map.add_parameter(
            name=name, description=description, validator=validator, default=default, required=required, inplace=inplace
        )

        return self if inplace else APIParameterConfig.as_config(parameter_map)

    def extract_parameters(self, parameters: SettingsDictType | None, *, inplace: bool = True) -> SettingsDictType:
        """Extracts all parameters from a dictionary: Helpful for when keywords must be extracted by provider.

        Note: this method modifies the original parameter dictionary, using the `pop()` method to `extract` all
        values identified as `api_specific_parameters` from the `parameters` dictionary when possible. These
        extracted parameters are then returned in a separate dictionary.

        Useful for reorganizing dictionaries that contain dynamically specified input parameters for distinct APIs.

        Args:
            parameters (Optional[dict[str, Any]] | SettingsDict):
                An optional parameter dictionary from which to extract API-specific parameters.
            inplace (bool):
                Indicates whether the original parameter dict should be mutated inplace. If False, the dict is copied.


        Returns:
            (dict[str, Any] | SettingsDict): A dictionary containing all extracted parameters if available.

        """
        if not parameters:
            return {}

        if not inplace and isinstance(parameters, (dict, SettingsDict)):
            parameters = parameters.copy()

        api_specific_parameters = {
            parameter: parameters.pop(parameter)
            for parameter in self.parameter_map.api_specific_parameters
            if parameter in parameters
        }

        api_specific_parameters |= parameters.get("parameters", {})
        return api_specific_parameters

    def extract_api_key(
        self, parameters: SettingsDictType | None, *, inplace: bool = True, **api_specific_parameters: Any
    ) -> SecretStr | None:
        """Helper method for extracting the API key from a dictionary of parameters and keyword arguments.

        Note: The removal of API keys from the received `parameters` dictionary is intentional with the aim of removing
        empty API keys and stale `api_key` parameter names that don't apply to a particular API provider. To avoid this
        behavior, unpack the parameter dictionary instead (e.g., `.extract_api_key(**parameters)`).

        Args:
            parameters (dict[str, Any] | SettingsDict):
                The dictionary of parameters from which API keys are extracted when building the request.
            inplace (bool):
                Indicates whether the original parameter dict should be mutated inplace. If False, the dict is copied.
            **api_specific_parameters:
                A list of key-value pairs from which the key will be extracted if available

        Returns:
            Optional[SecretStr]: The extracted API key formatted as a secret key if available and `None` otherwise.

        """
        # Extracts the API key if available
        key_name = self.parameter_map.api_key_parameter
        api_key = api_specific_parameters.get(self.parameter_map.DEFAULT_API_KEY_PARAMETER) or (
            api_specific_parameters.get(key_name) if key_name else None
        )

        if not inplace and isinstance(parameters, (dict, SettingsDict)):
            parameters = parameters.copy()

        # Should remove both api key parameters if any one of them still exists (potentially out of date)
        extracted_api_key = (
            with_fallback(
                parameters.pop(self.parameter_map.api_key_parameter or "", None),
                parameters.pop(self.parameter_map.DEFAULT_API_KEY_PARAMETER, None),
            )
            if isinstance(parameters, (dict, SettingsDict))
            else None
        )

        # Prioritize api_specific_parameters over the parameters dict (consider the latter as the dictionary to prepare)
        api_key = extracted_api_key if api_key is None else api_key

        # Returns a secret string when available, otherwise None
        return self.validate_api_key(api_key, allow_missing=True)

    @classmethod
    @overload
    def validate_api_key(cls, api_key: None, *, allow_missing: bool = False) -> SecretStr | None:
        """If the API key is None, an API key is not returned."""

    @classmethod
    @overload
    def validate_api_key(cls, api_key: str | SecretStr, *, allow_missing: bool = False) -> SecretStr:
        """If the API key is a string or secret string, the key is returned after masking."""

    @classmethod
    def validate_api_key(cls, api_key: object, *, allow_missing: bool = False) -> SecretStr | None:
        """Verifies that the received api_key is of the correct type.

        Args:
            api_key (object): The API key to validate.
            allow_missing (bool): Whether a missing API key should gracefully return None or raise an error (default).

        Returns:
            SecretStr: The API key, masked as a secret string when valid.
            None: If an API key has not been provided.

        """
        if api_key is None and allow_missing:
            return None

        if not isinstance((unmasked_key := SecretUtils.unmask_secret(api_key)), str):
            key_type = "extracted and unmasked" if isinstance(api_key, SecretStr) else "extracted"
            raise APIKeyValidationException(
                f"Expected the {key_type} API key to be of type `str` or `SecretStr`, but instead received "
                f"{type(unmasked_key)}."
            )
        return SecretUtils.mask_secret(api_key)

    def _include_api_key(self, parameters: SettingsDictType | None, **api_specific_parameters: Any) -> SettingsDictType:
        """Helper method for including the API key as a parameter in a dictionary of request parameters.

        This helper method attempts to extract the API key from the received parameters, including the extracted key
        within the prepared dictionary of request parameters when successful. Referencing the current API parameter
        mapping, the key-value pair is assigned under the correct parameter name for the current API when the API key is
        successfully extracted.

        Args:
            parameters (dict[str, Any] | SettingsDict): The dictionary of parameters being built for a request
            api_specific_parameters (dict): A list of key-value pairs from which the key will be extracted if available
        Returns:
            dict: If the API key extraction was successful or if it wasn't required

        Raises:
            APIParameterException:
                If the API key is required, but not provided or if the parameters argument is not a dictionary.

        """
        # if parameters is None, create an empty dictionary
        parameters = parameters if parameters is not None else {}

        # raise an error if parameters is not actually a dictionary
        if not isinstance(parameters, (dict, SettingsDict)):
            raise APIParameterException(
                f"Expected `parameters` to be a dictionary, instead received {type(parameters)}"
            )

        # Include API key if provided
        if key_name := self.parameter_map.api_key_parameter:
            # Extracts the API key from the parameters dictionary if exists. Removes keys inplace (This is intentional).
            api_key = self.extract_api_key(parameters, **api_specific_parameters)

            # Sets the API key into `parameters` with the correct parameter name if a key exists
            if api_key:
                parameters.update({key_name: api_key})

            # Raise an error if an api key is required, but does not exist
            elif self.parameter_map.api_key_required and not parameters.get(key_name):
                logger.error("An API key is required but not provided")
                raise APIParameterException("An API key is required but not provided")
        # Returns a new dictionary with the api key
        return parameters

    @classmethod
    def get_defaults(cls, provider_name: str, **additional_parameters: Any) -> APIParameterConfig | None:
        """Factory method to create APIParameterConfig instances with sensible defaults for known APIs.

        Avoids throwing an error if the provider name does not already exist.

        Args:
            provider_name (str): The name of the API to create the parameter map for.
            additional_parameters (dict): Additional parameter mappings.

        Returns:
            Optional[APIParameterConfig]:
                Configured parameter config instance for the specified API. Returns None if a mapping for the
                provider_name isn't retrieved

        """
        parameter_map = APIParameterMap.get_defaults(provider_name, **additional_parameters)
        return cls(parameter_map) if parameter_map else None

    @classmethod
    def as_config(
        cls, parameter_map: dict | BaseAPIParameterMap | APIParameterMap | APIParameterConfig
    ) -> APIParameterConfig:
        """Factory method for creating a new APIParameterConfig from a dictionary or APIParameterMap.

        This helper class method resolves the structure of the APIParameterConfig against its basic building blocks
        to create a new configuration when possible.

        Args:
            parameter_map (dict | BaseAPIParameterMap | APIParameterMap | APIParameterConfig):
                A parameter mapping/config to use in the instantiation of an APIParameterConfig.

        Returns:
            APIParameterConfig: A new structure from the inputs

        Raises:
            APIParameterException: If there is an error in the creation/resolution of the required parameters

        """
        if isinstance(parameter_map, APIParameterConfig):
            return parameter_map

        if not isinstance(parameter_map, (dict, APIParameterMap, BaseAPIParameterMap)):
            raise APIParameterException(
                "Expected a base API Parameter map, config, or dictionary."
                f" Received type ({type(parameter_map).__name__})"
            )

        logger.info(
            f"Attempting to instantiate an APIParameterConfig with parameters of type ({type(parameter_map).__name__})..."
        )

        if isinstance(parameter_map, APIParameterMap):
            return cls(parameter_map)

        parameter_dict = parameter_map.model_dump() if isinstance(parameter_map, BaseAPIParameterMap) else parameter_map
        try:
            updated_parameter_mapping = APIParameterMap(**parameter_dict)
            return cls(updated_parameter_mapping)
        except ValidationError as e:
            raise APIParameterException(
                "Encountered an error instantiating an APIParameterConfig from the provided "
                f"parameter, `{parameter_dict}`: {e}"
            )

    def _find_duplicated_parameters(self, api_specific_parameters: SettingsDictType) -> SettingsDictType:
        """Finds and flags duplicated parameters in the provided `api_specific_parameters` dictionary.

        This helper method identifies key conflicts with known defaults and flags them ahead of time to
        prevent downstream errors and inconsistencies in the creation of requests.

        The function returns a list of all duplicated_parameters if they exist. Otherwise the dictionary will be empty.

        Args:
            api_specific_parameters (dict[str, Any] | SettingsDict): The dictionary to check for duplicated_parameters

        Returns:
            dict[str, Any] | SettingsDict: A dictionary containing all API-specific parameters that have been duplicated

        """
        core_parameters = {"query", "records_per_page", "api_key"}

        query_parameter_name = self.parameter_map.query
        records_per_page_parameter_name = self.parameter_map.records_per_page
        api_key_parameter = self.parameter_map.api_key_parameter

        api_parameters = core_parameters | {query_parameter_name, records_per_page_parameter_name, api_key_parameter}
        duplicated_parameters = {
            parameter: api_specific_parameters.get(parameter)
            for parameter in api_parameters
            if parameter is not None and parameter in api_specific_parameters
        }

        return duplicated_parameters

    @classmethod
    def from_defaults(cls, provider_name: str, **additional_parameters: Any) -> APIParameterConfig:
        """Factory method to create APIParameterConfig instances with sensible defaults for known APIs.

        If the provider_name does not exist, this method will raise an exception.

        Args:
            provider_name (str): The name of the API to create the parameter map for.
            **additional_parameters: Additional parameter mappings.

        Returns:
            APIParameterConfig: Configured parameter config instance for the specified API.

        Raises:
            NotImplementedError: If the API name is unknown.

        """
        parameter_map = APIParameterMap.from_defaults(provider_name, **additional_parameters)
        return cls(parameter_map)

    def structure(self, flatten: bool = False, show_value_attributes: bool = True) -> str:
        """Helper method that shows the current structure of the APIParameterConfig."""
        class_name = self.__class__.__name__
        return generate_repr_from_string(
            class_name,
            dict(parameter_map=repr(self.parameter_map)),
            flatten=flatten,
            show_value_attributes=show_value_attributes,
        )

    def __repr__(self) -> str:
        """Helper method for displaying the config and parameter mappings for the API in a user-friendly manner."""
        return self.structure()


__all__ = ["APIParameterMap", "APIParameterConfig"]
