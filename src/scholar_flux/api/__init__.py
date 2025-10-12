# api/
"""

The scholar_flux.api module includes the core classes and functionality necessary
to interact with APIs in a universally applicable manner. This module defines
the methods necessary to retrieve the raw responses from APIs based on the
configuration used for the API client (SearchAPI).

Sub-modules:
    models: Contains the classes used to set up new configurations in addition to the API utility models
            and modules necessary to interact with APIs
    providers: Defines the default provider specifications to easily create a new client for a specific
               provider with minimal code. (e.g, plos.py contains the necessary config settings for the PLOS API)
    workflows: Defines custom workflows for APIs requiring API-specific logic modifications for easier record retrieval.
               This includes the PubMed Workflow which searches IDs and then fetches the records
    rate_limiting: Defines the methods and classes used to ensure that the rate limits associated with each API
                   are not exceeded. The SearchAPI implements rate limiting using the `RateLimiter` and, optionally,
                   ThreadedRateLimiter class to wait a specified interval of time before sending the next request.

In order to use the API one can get started with the SearchCoordinator with minimal effort:
    >>> from scholar_flux.api import SearchCoordinator # imports the most forward facing interface for record retrieval
    >>> search_coordinator = SearchCoordinator(query = 'Turing Machines') # uses PLOS by default
    >>> print(search_coordinator.api) # Shows the core SearchAPI specification used to send requests to APIs
    >>> processed_response = search_coordinator.search(page = 1) # retrieves and processes records from the API response

You can also retrieve the responses directly without processing via the SearchAPI:
    >>> from scholar_flux.api import SearchAPI # imports the core SearchAPI used by the coordinator to send requests
    >>> api = SearchAPI(query='ML') # uses PLOS by default
    >>> response = api.search(page = 1) # retrieves and processes records from the API response

The functionality of the SearchCoordinators are further customized using the following moodules:
    scholar_flux.sessions: Contains the core classes for directly setting up cached sessions
    scholar_flux.data: Contains the core classes used to parse, extract, and process records
    scholar_flux.data_storage: Contains the core classes used for caching
    scholar_flux.security: Contains the core classes used for ensuring security in console and logging (e.g API keys)
"""

from scholar_flux.api.response_validator import ResponseValidator
from scholar_flux.api.validators import validate_url, validate_email

from scholar_flux.api.models import APIParameterMap, APIParameterConfig
from scholar_flux.api.models import ProviderConfig, ProviderRegistry
from scholar_flux.api.providers import PROVIDER_DEFAULTS, provider_registry

from scholar_flux.api.models.responses import APIResponse, ErrorResponse, ProcessedResponse, NonResponse
from scholar_flux.api.models import SearchAPIConfig

from scholar_flux.api.rate_limiting.rate_limiter import RateLimiter
from scholar_flux.api.rate_limiting.threaded_rate_limiter import ThreadedRateLimiter
from scholar_flux.api.rate_limiting.retry_handler import RetryHandler
from scholar_flux.api.base_api import BaseAPI
from scholar_flux.api.search_api import SearchAPI

from scholar_flux.api.response_coordinator import ResponseCoordinator
from scholar_flux.api.base_coordinator import BaseCoordinator
from scholar_flux.api.search_coordinator import SearchCoordinator
from scholar_flux.api.multisearch_coordinator import MultiSearchCoordinator
from scholar_flux.api.models.reconstructed_response import ReconstructedResponse

__all__ = [
    "ResponseValidator",
    "APIParameterMap",
    "APIParameterConfig",
    "ProviderConfig",
    "PROVIDER_DEFAULTS",
    "ProviderRegistry",
    "provider_registry",
    "APIResponse",
    "ErrorResponse",
    "NonResponse",
    "ProcessedResponse",
    "ReconstructedResponse",
    "SearchAPIConfig",
    "RateLimiter",
    "ThreadedRateLimiter",
    "RetryHandler",
    "BaseAPI",
    "SearchAPI",
    "ResponseCoordinator",
    "BaseCoordinator",
    "SearchCoordinator",
    "MultiSearchCoordinator",
    "validate_url",
    "validate_email",
]
