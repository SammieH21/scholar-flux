# /api/models/base_parameters.py
"""
The scholar_flux.api.models.base_parameters module implements the foundational BaseAPIParameterMap
and APISpecificParameters required to interact with and create requests to API providers.

Classes:
    BaseAPIParameterMap: Defines the parameters and required settings to successfully interact with
                         a provider's API specification.
    APISpecificParameters:  Defines the optional and required parameters that are specific to the current API provider
"""
from __future__ import annotations
from typing import Optional, Dict, Any, Callable
from pydantic import BaseModel, Field
from pydantic.dataclasses import dataclass
from scholar_flux.utils.repr_utils import generate_repr, generate_repr_from_string
import logging

logger = logging.getLogger(__name__)


@dataclass
class APISpecificParameter:
    """
    Dataclass with the responsibility of recording the specifics of parameters that correspond only to a single API
    with specific defaults, validation steps, and indicators of optional vs. required fields.

    Args:
        name (str): The name of the parameter used when sending requests to APis
        description (str): A description of the API Specific parameter
        validator (Optional[Callable[[Any], Any]]): An optional step for verifying the input to the dataclass based on
                                                    required types, constrained values, etc.
        default (Any): An optional default value to populate the required parameter with if otherwise not specified
        required (bool): An attribute used as a flag for identifying additional parameters that must be provided when
                         creating extensible API clients for particular providers.
    """

    name: str
    description: str
    validator: Optional[Callable[[Any], Any]] = None
    default: Any = None
    required: bool = False

    @property
    def validator_name(self):
        """Helper method for generating a human readable string from the validator function, if used"""
        if self.validator is None:
            return "None"
        name = getattr(self.validator, "__name__", "unnamed")
        validator_type = type(self.validator).__name__
        return f"{name} ({validator_type})"

    def structure(self, flatten: bool = False, show_value_attributes: bool = True) -> str:
        """Helper method for showing the structure of the current APISpecificParameter"""
        class_name = self.__class__.__name__
        # the representation will include all attributes in the current dataclass
        attribute_dict = dict(
            name=self.name,
            description=self.description,
            # validator manually added. otherwise, functions don't show in dataclass representations
            validator=self.validator_name,
            default=self.default,
            required=self.required,
        )
        return generate_repr_from_string(
            class_name, attribute_dict, flatten=flatten, show_value_attributes=show_value_attributes
        )

    def __repr__(self) -> str:
        """Helper method for displaying parameter information in a user-friendly manner"""
        return self.structure()


class BaseAPIParameterMap(BaseModel):
    """
    Maps universal search API parameter names to API-specific parameter names,
    including API key parameter name and whether an API key is required.

    Attributes:
        query (str): The API-specific parameter name for the search query.
        start (Optional[str]): The API-specific parameter name for optional pagination (either start index or page number).
        records_per_page (str): The API-specific parameter name for records per page.
        api_key_parameter (Optional[str]): The API-specific parameter name for the API key.
        api_key_required (bool): Whether the API key is required by this API.
        page_required (bool): If True, indicates that a page is required for the current API
        auto_calculate_page (bool): If True, calculates start index from page; if False, passes page number directly.
        zero_indexed_pagination (bool): If True, treats 0 as an allowed page value when retrieving data from APIs
        api_specific_parameters (Dict[str, APISpecificParameter]): Additional universal to API-specific parameter mappings.
        additional_parameter_validators (Dict[str, str]): Additional universal to API-specific parameter mappings.
    """

    query: str
    records_per_page: str
    start: Optional[str] = None
    api_key_parameter: Optional[str] = None
    api_key_required: bool = False
    auto_calculate_page: bool = True
    zero_indexed_pagination: bool = False
    api_specific_parameters: Dict[str, APISpecificParameter] = Field(default_factory=dict)

    def update(self, other: BaseAPIParameterMap | Dict[str, Any]) -> BaseAPIParameterMap:
        """
        Update the current instance with values from another BaseAPIParameterMap or dictionary.

        Args:
            other (BaseAPIParameterMap | Dict): The object containing updated values.

        Returns:
            BaseAPIParameterMap: A new instance with updated values.
        """
        if isinstance(other, BaseAPIParameterMap):
            other = other.to_dict()
        updated_dict = self.to_dict() | other
        return self.from_dict(updated_dict)

    @classmethod
    def from_dict(cls, obj: Dict[str, Any]) -> BaseAPIParameterMap:
        """
        Create a new instance of BaseAPIParameterMap from a dictionary.

        Args:
            obj (dict): The dictionary containing the data for the new instance.

        Returns:
            BaseAPIParameterMap: A new instance created from the given dictionary.
        """
        return cls.model_validate(obj)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the current instance into a dictionary representation.

        Returns:
            Dict: A dictionary representation of the current instance.
        """
        return self.model_dump()

    def show_parameters(self) -> list:
        """
        Helper method to show the complete list of all parameters that can be found in the current ParameterMap

        Returns:
            List: The complete list of all universal and api specific parameters corresponding to the current API
        """
        parameters = [
            parameter
            for parameter in self.model_dump()
            if parameter
            not in ("api_key_required", "auto_calculate_page", "api_specific_parameters", "zero_indexed_pagination")
        ]

        parameters += list(self.api_specific_parameters.keys())
        return parameters

    def structure(self, flatten: bool = False, show_value_attributes: bool = True) -> str:
        """Helper method that shows the current structure of the BaseAPIParameterMap"""
        return generate_repr(self, flatten=flatten, show_value_attributes=show_value_attributes)

    def __repr__(self) -> str:
        """Helper method for displaying the config in a user-friendly manner"""
        return self.structure()
