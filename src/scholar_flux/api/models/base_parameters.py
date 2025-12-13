# /api/models/base_parameters.py
"""The scholar_flux.api.models.base_parameters module implements BaseAPIParameterMap and APISpecificParameter classes.

These classes define the core and API-specific fields required to interact with and create requests to API providers.

Classes:
    BaseAPIParameterMap: Defines parameters for interacting with a provider's API specification.
    APISpecificParameters: Defines optional and required parameters specific to an API provider.

"""
from __future__ import annotations
from typing import Optional, Dict, Any, Callable
from typing_extensions import Self
from pydantic import BaseModel, Field
from pydantic.dataclasses import dataclass
from scholar_flux.utils.repr_utils import generate_repr, generate_repr_from_string
import logging

logger = logging.getLogger(__name__)


@dataclass
class APISpecificParameter:
    """Dataclass that defines the specification of an API-specific parameter for an API provider.

    Implements optionally specifiable defaults, validation steps, and indicators for optional vs. required fields.

    Args:
        name (str):
            The name of the parameter used when sending requests to APis.
        description (str):
            A description of the API-specific parameter.
        validator (Optional[Callable[[Any], Any]]):
            An optional function/method for verifying and pre-processing parameter input based on required types,
            constrained values, etc.
        default (Any):
            An default value used for the parameter if not specified by the user
        required (bool):
            Indicates whether the current parameter is required for API calls.

    """

    name: str
    description: str
    validator: Optional[Callable[[Any], Any]] = None
    default: Any = None
    required: bool = False

    @property
    def validator_name(self):
        """Helper method for generating a human readable string from the validator function, if used."""
        if self.validator is None:
            return "None"
        name = getattr(self.validator, "__name__", "unnamed")
        validator_type = type(self.validator).__name__
        return f"{name} ({validator_type})"

    def structure(self, flatten: bool = False, show_value_attributes: bool = True) -> str:
        """Helper method for showing the structure of the current APISpecificParameter."""
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
        """Helper method for displaying parameter information in a user- friendly manner."""
        return self.structure()


class BaseAPIParameterMap(BaseModel):
    """Base class for Mapping universal SearchAPI parameter names to API-specific parameter names.

     Includes core logic for distinguishing parameter names, indicating required API keys, and
     defining pagination logic.

    Attributes:
        query (str): The API-specific parameter name for the search query.
        start (Optional[str]): The API-specific parameter name for optional pagination (start index or page number).
        records_per_page (str): The API-specific parameter name for records per page.
        api_key_parameter (Optional[str]): The API-specific parameter name for the API key.
        api_key_required (bool): Indicates whether an API key is required.
        page_required (bool): If True, indicates that a page is required.
        auto_calculate_page (bool): If True, calculates start index from page; if False, passes page number directly.
        zero_indexed_pagination (bool): Treats page=0 as an allowed page value when retrieving data from the API.
        api_specific_parameters (Dict[str, APISpecificParameter]): Additional API-specific parameter mappings.

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
        """Update the current instance with values from another BaseAPIParameterMap or dictionary.

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
        """Create a new instance of BaseAPIParameterMap from a dictionary.

        Args:
            obj (dict): The dictionary containing the data for the new instance.

        Returns:
            BaseAPIParameterMap: A new instance created from the given dictionary.

        """
        return cls.model_validate(obj)

    def to_dict(self) -> Dict[str, Any]:
        """Convert the current instance into a dictionary representation.

        Returns:
            Dict: A dictionary representation of the current instance.

        """
        return self.model_dump()

    def show_parameters(self) -> list:
        """Helper method to show the complete list of all parameters that can be found in the current ParameterMap.

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

    def add_parameter(
        self,
        name: str,
        description: Optional[str] = None,
        validator: Optional[Callable[[Any], Any]] = None,
        default: Any = None,
        required: bool = False,
        inplace=True,
    ) -> Self:
        """Helper method that enables the efficient addition of parameters to the current parameter map.

        Args:
            name (str):
                The name of the parameter used when sending requests to APis.
            description (str):
                A description of the API-specific parameter.
            validator (Optional[Callable[[Any], Any]]):
                An optional function/method for verifying and pre-processing parameter input based on required types,
                constrained values, etc.
            default (Any):
                An default value used for the parameter if not specified by the user
            required (bool):
                Indicates whether the current parameter is required for API calls.
            inplace (bool):
                A flag that, if True, modifies the current parameter map instance in place. If False, it returns a new
                parameter map that contains the added parameter, while leaving the original unchanged.

                Note: If this instance is shared (e.g., retrieved from provider_registry), changes will affect all
                references to this parameter map. if `inplace=True` .

        Returns:
            Self: A parameter map containing the specified parameter. If `inplace=True`, the original is
            returned. Otherwise a new parameter map containing an updated `api_specific_parameters` dict is returned.

        """

        description = description if description else f"Custom Parameter: {name}"

        parameter_map = self if inplace else self.model_copy(deep=True)
        parameter_map.api_specific_parameters[name] = APISpecificParameter(
            name=name, description=description, validator=validator, default=default, required=required
        )
        return parameter_map

    def structure(self, flatten: bool = False, show_value_attributes: bool = True) -> str:
        """Helper method that shows the current structure of the BaseAPIParameterMap."""
        return generate_repr(self, flatten=flatten, show_value_attributes=show_value_attributes)

    def __repr__(self) -> str:
        """Helper method for displaying the config in a user-friendly manner."""
        return self.structure()


__all__ = ["BaseAPIParameterMap", "APISpecificParameter"]
