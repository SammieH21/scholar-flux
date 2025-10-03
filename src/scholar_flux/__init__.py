"""
ScholarFlux API
===============

The `scholar_flux` package is an open-source project designed to streamline access to academic and scholarly resources across
various platforms. It offers a unified API that simplifies querying academic databases, retrieving metadata,
and performing comprehensive searches within scholarly articles, journals, and publications.

In addition, this API has built in extension capabilities for applications in News retrieval and other domains.

The SearchCoordinator offers the core functionality needed to orchestrate the process the process, including:
API Retrieval -> Response Parsing -> Record Extraction -> Record Processing -> Returning the Processed Response

This module initializes the package and includes the core functionality and helper classes needed to retrieve
API Responses from API Providers.
"""

from scholar_flux.package_metadata import __version__
from scholar_flux.utils.initializer import initialize_package

config, logger, masker = initialize_package()

from scholar_flux.sessions import SessionManager, CachedSessionManager
from scholar_flux.data_storage import (
    DataCacheManager,
    SQLAlchemyStorage,
    RedisStorage,
    InMemoryStorage,
    MongoDBStorage,
    NullStorage,
)
from scholar_flux.data import (
    DataParser,
    DataExtractor,
    DataProcessor,
    PassThroughDataProcessor,
    RecursiveDataProcessor,
    PathDataProcessor,
)
from scholar_flux.api import (
    SearchAPI,
    BaseAPI,
    ResponseValidator,
    ResponseCoordinator,
    SearchCoordinator,
    MultiSearchCoordinator,
    SearchAPIConfig,
    ProviderConfig,
    APIParameterConfig,
    APIParameterMap,
)

__all__ = [
    "__version__",
    "config",
    "logger",
    "masker",
    "SessionManager",
    "CachedSessionManager",
    "DataCacheManager",
    "SQLAlchemyStorage",
    "RedisStorage",
    "InMemoryStorage",
    "MongoDBStorage",
    "NullStorage",
    "DataParser",
    "DataExtractor",
    "DataProcessor",
    "PassThroughDataProcessor",
    "RecursiveDataProcessor",
    "PathDataProcessor",
    "SearchAPI",
    "BaseAPI",
    "ResponseValidator",
    "ResponseCoordinator",
    "SearchCoordinator",
    "MultiSearchCoordinator",
    "SearchAPIConfig",
    "ProviderConfig",
    "APIParameterConfig",
    "APIParameterMap",
]
