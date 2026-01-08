"""
ScholarFlux API
===============

The `scholar_flux` package is an open-source project designed to streamline access to academic and scholarly resources
across various platforms. ScholarFlux offers a unified API that simplifies the processes of querying multiple academic
databases, retrieving academic metadata, and performing comprehensive searches for scholarly articles, journals, and
publications.

In addition, this API client has built in extension capabilities for applications in News retrieval and other domains.

The SearchCoordinator offers the core functionality needed to orchestrate the process, including:
API Retrieval -> Response Parsing -> Record Extraction -> Record Processing -> Returning the Processed Response

This module initializes the package and includes the core functionality and helper classes needed to retrieve
API Responses from API Providers.
"""

from scholar_flux.package_metadata import __version__
from scholar_flux.utils.initializer import initialize_package
from typing import Any

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

from scholar_flux.utils.lazy_loader import lazy_import_attr


_lazy_imports = {("scholar_flux.utils", "config_settings")}


def __getattr__(name: str) -> Any:
    """Enables the lazy retrieval of objects within the `scholar_flux.utils` module's namespace.

    These modules are not loaded until they are explicitly needed by a package resource or by a user.

    """
    return lazy_import_attr(name, _lazy_imports, __name__)


__all__ = [
    "__version__",
    "config",
    "config_settings",
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
