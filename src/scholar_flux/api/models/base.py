from __future__ import annotations
from typing import  Optional, Dict, Any, Callable
from pydantic import BaseModel, Field
from pydantic.dataclasses import dataclass
from scholar_flux.utils.repr_utils import generate_repr
import logging

logger = logging.getLogger(__name__)


@dataclass
class APISpecificParameter:
    name: str
    description: str
    validator: Optional[Callable[[Any], Any]] = None
    default: Any = None
    required: bool = False

    @property
    def validator_name(self):
        return self.validator.__name__ if self.validator else 'None'

    def __repr__(self) -> str:
        """Helper method for displaying parameter information in a user-friendly manner"""
        return generate_repr(self)

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
        api_specific_parameters (Dict[str, str]): Additional universal to API-specific parameter mappings.
        additional_parameter_validators (Dict[str, str]): Additional universal to API-specific parameter mappings.
    """

    query: str
    records_per_page: str
    start: Optional[str] = None
    api_key_parameter: Optional[str] = None
    api_key_required: bool = False
    auto_calculate_page: bool = True
    api_specific_parameters: Dict[str, APISpecificParameter] = Field(default_factory=dict)

    def update(self, other: BaseAPIParameterMap | Dict[str,Any]) -> BaseAPIParameterMap:
        """
        Update the current instance with values from another BaseAPIParameterMap or dictionary.

        Args:
            other (BaseAPIParameterMap | Dict): The object containing updated values.

        Returns:
            BaseAPIParameterMap: A new instance with updated values.
        """
        if isinstance(other, BaseAPIParameterMap):
            other = other.to_dict()
        updated_dict=self.to_dict() | other
        return self.from_dict(updated_dict)

    @classmethod
    def from_dict(cls, obj: Dict[str,Any]) -> BaseAPIParameterMap:
        """
        Create a new instance of BaseAPIParameterMap from a dictionary.

        Args:
            obj (dict): The dictionary containing the data for the new instance.

        Returns:
            BaseAPIParameterMap: A new instance created from the given dictionary.
        """
        return cls(**obj)

    def to_dict(self) -> Dict[str,Any]:
        """
        Convert the current instance into a dictionary representation.

        Returns:
            Dict: A dictionary representation of the current instance.
        """
        return self.model_dump()

    def __repr__(self) -> str:
        """Helper method for displaying the config in a user-friendly manner"""
        return generate_repr(self)
