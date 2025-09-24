# /api/models

"""
The scholar_flux.api.models module includes all of the needed configuration classes that
are needed to define the configuration needed to configure APIs for specific providers and
to ensure that the process is orchestrated in a robust way.

Core Models:
    - APIParameterMap: Contains the mappings and settings used to customized common and API Specific parameters
                       to the requirements for each API.
    - APIParameterConfig: Encapsulates the created APIParameterMap as well as the methods used to create each request.
    - ProviderConfig: Allows users to define each of the defaults and mappings settings needed to create a Search API
    - ProviderRegistry: Defines the structure
"""

from scholar_flux.api.models.reconstructed_response import ReconstructedResponse
from scholar_flux.api.models.base import BaseAPIParameterMap, APISpecificParameter
from scholar_flux.api.models.parameters import APIParameterMap, APIParameterConfig
from scholar_flux.api.models.provider_config import ProviderConfig
from scholar_flux.api.models.provider_registry import ProviderRegistry

from scholar_flux.api.models.response_types import ResponseResult
from scholar_flux.api.models.search import SearchAPIConfig
from scholar_flux.api.models.search_inputs import PageListInput

from scholar_flux.api.models.response import (
    APIResponse,
    ErrorResponse,
    ProcessedResponse,
)

from scholar_flux.api.models.search_results import SearchResult, SearchResultList

__all__ = [
    "BaseAPIParameterMap",
    "APISpecificParameter",
    "APIParameterMap",
    "APIParameterConfig",
    "ProviderConfig",
    "ProviderRegistry",
    "APIResponse",
    "ErrorResponse",
    "ProcessedResponse",
    "ReconstructedResponse",
    "ResponseResult",
    "SearchResult",
    "SearchResultList",
    "SearchAPIConfig",
    "PageListInput",
]
