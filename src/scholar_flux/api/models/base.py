from __future__ import annotations
from typing import  List, Optional, Dict, Any, Union, ClassVar
from pydantic import BaseModel, Field, model_validator
import logging

logger = logging.getLogger(__name__)

class BaseAPIParameterMap(BaseModel):
    """
    Maps universal search API parameter names to API-specific parameter names,
    including API key parameter name and whether an API key is required.

    Attributes:
        query (str): The API-specific parameter name for the search query.
        start (str): The API-specific parameter name for pagination (either start index or page number).
        records_per_page (str): The API-specific parameter name for records per page.
        api_key_param (Optional[str]): The API-specific parameter name for the API key.
        api_key_required (bool): Whether the API key is required by this API.
        auto_calculate_page (bool): If True, calculates start index from page; if False, passes page number directly.
        additional_parameter_names (Dict[str, str]): Additional universal to API-specific parameter mappings.
    """

    query: str
    start: str
    records_per_page: str
    api_key_param: Optional[str] = None
    api_key_required: bool = False
    auto_calculate_page: bool = True
    additional_parameter_names: Dict[str, str] = Field(default_factory=dict)

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
