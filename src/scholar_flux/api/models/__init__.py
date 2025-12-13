# /api/models

"""The scholar_flux.api.models module includes all of the needed configuration classes that are needed to define the
configuration needed to configure APIs for specific providers and to ensure that the process is orchestrated in a robust
way.

Core Models:
    - APIParameterMap: Contains the mappings and settings used to customized common and API Specific parameters
                       to the requirements for each API.
    - APIParameterConfig: Encapsulates the created APIParameterMap as well as the methods used to create each request.
    - SearchAPIConfig: Defines the core logic to abstract the creation of requests with parameters specific to each API.
    - ProviderConfig: Allows users to define each of the defaults and mappings settings needed to create a Search API.
    - ProviderRegistry: A customized dictionary mapping provider names to their dynamically retrieved configuration.
    - ProcessedResponse: Indicates a successfully retrieved and processed response from an API provider.
    - ErrorResponse: Indicates that an exception occurred somewhere in the process of response retrieval and processing.
    - NonResponse: Indicates a that a response of any status code could not be retrieved due to an exception.

"""

from scholar_flux.api.models.reconstructed_response import ReconstructedResponse
from scholar_flux.api.models.base_parameters import BaseAPIParameterMap, APISpecificParameter
from scholar_flux.api.models.api_parameters import APIParameterMap, APIParameterConfig
from scholar_flux.api.models.response_metadata_map import ResponseMetadataMap
from scholar_flux.api.models.provider_config import ProviderConfig
from scholar_flux.api.models.provider_registry import ProviderRegistry
from scholar_flux.api.models.response_history import ResponseHistoryRegistry
from scholar_flux.api.models.base_provider_dict import BaseProviderDict

from scholar_flux.api.models.response_types import APIResponseType
from scholar_flux.api.models.search_api_config import SearchAPIConfig
from scholar_flux.api.models.search_inputs import PageListInput

from scholar_flux.api.models.responses import (
    APIResponse,
    ErrorResponse,
    NonResponse,
    ProcessedResponse,
)

from scholar_flux.api.models.search_results import SearchResult, SearchResultList

from scholar_flux.api.normalization.base_field_map import BaseFieldMap
from scholar_flux.api.normalization.academic_field_map import AcademicFieldMap

__all__ = [
    "BaseAPIParameterMap",
    "APISpecificParameter",
    "APIParameterMap",
    "APIParameterConfig",
    "ResponseMetadataMap",
    "BaseFieldMap",
    "AcademicFieldMap",
    "ProviderConfig",
    "ProviderRegistry",
    "ResponseHistoryRegistry",
    "BaseProviderDict",
    "APIResponse",
    "ErrorResponse",
    "NonResponse",
    "ProcessedResponse",
    "ReconstructedResponse",
    "APIResponseType",
    "SearchResult",
    "SearchResultList",
    "SearchAPIConfig",
    "PageListInput",
]
