# /exceptions
"""The scholar_flux.exceptions module implements different types of exceptions used within the scholar_flux package with
customized exceptions with applications to client setup, API retrieval, API processing, and caching.

Modules:
    api_exceptions: Exceptions crafted for unforeseen issues in API client creation and errors in response retrieval
    data_exceptions: Exceptions that could occur during the parsing, extraction, and processing of response data
    util_exceptions: Exceptions used in the creation of utilities used throughout the module
    coordinator_exceptions: Exceptions revolving around the coordination of requests, response processing and caching
    storage_exceptions: Exceptions involving potential and common issues involving storage
    path_exceptions: Exceptions for edge-cases when processing JSON files using custom path processing utilities
    import_exceptions: Exceptions for handling missing dependencies

"""
from scholar_flux.exceptions.api_exceptions import (
    APIException,
    MissingAPIKeyException,
    MissingAPISpecificParameterException,
    MissingProviderException,
    MissingResponseException,
    PermissionException,
    NoRecordsAvailableException,
    InvalidResponseException,
    NotFoundException,
    SearchAPIException,
    SearchRequestException,
    RequestCreationException,
    RequestFailedException,
    RateLimitExceededException,
    RetryLimitExceededException,
    TimeoutException,
    APIParameterException,
    RecordNormalizationException,
    RequestCacheException,
    InvalidResponseStructureException,
    InvalidResponseReconstructionException,
    QueryValidationException,
)

from scholar_flux.exceptions.coordinator_exceptions import (
    CoordinatorException,
    InvalidCoordinatorParameterException,
)

from scholar_flux.exceptions.util_exceptions import (
    SessionCreationError,
    SessionConfigurationError,
    SessionInitializationError,
    SessionCacheDirectoryError,
    LogDirectoryError,
    PackageInitializationError,
    SecretKeyError,
)

from scholar_flux.exceptions.data_exceptions import (
    ResponseProcessingException,
    DataParsingException,
    InvalidDataFormatException,
    DataExtractionException,
    FieldNotFoundException,
    DataProcessingException,
    DataValidationException,
)
from scholar_flux.exceptions.import_exceptions import (
    OptionalDependencyImportError,
    ItsDangerousImportError,
    RedisImportError,
    MongoDBImportError,
    XMLToDictImportError,
    SQLAlchemyImportError,
    YAMLImportError,
    CryptographyImportError,
)
from scholar_flux.exceptions.storage_exceptions import (
    StorageCacheException,
    KeyNotFound,
    CacheRetrievalException,
    CacheUpdateException,
    CacheDeletionException,
    CacheVerificationException,
)

from scholar_flux.exceptions.path_exceptions import (
    PathUtilsError,
    InvalidProcessingPathError,
    InvalidComponentTypeError,
    PathSimplificationError,
    InvalidPathDelimiterError,
    PathIndexingError,
    InvalidPathNodeError,
    RecordPathNodeMapError,
    RecordPathChainMapError,
    PathNodeIndexError,
    PathCombinationError,
    PathCacheError,
    PathNodeMapError,
    PathDiscoveryError,
)

__all__ = [
    "APIException",
    "MissingAPIKeyException",
    "MissingAPISpecificParameterException",
    "MissingProviderException",
    "MissingResponseException",
    "PermissionException",
    "NoRecordsAvailableException",
    "InvalidResponseException",
    "NotFoundException",
    "SearchAPIException",
    "SearchRequestException",
    "RequestCreationException",
    "RequestFailedException",
    "RateLimitExceededException",
    "RetryLimitExceededException",
    "TimeoutException",
    "APIParameterException",
    "RecordNormalizationException",
    "RequestCacheException",
    "InvalidResponseStructureException",
    "InvalidResponseReconstructionException",
    "QueryValidationException",
    "CoordinatorException",
    "InvalidCoordinatorParameterException",
    "SessionCreationError",
    "SessionConfigurationError",
    "SessionInitializationError",
    "SessionCacheDirectoryError",
    "LogDirectoryError",
    "PackageInitializationError",
    "SecretKeyError",
    "ResponseProcessingException",
    "DataParsingException",
    "InvalidDataFormatException",
    "DataExtractionException",
    "FieldNotFoundException",
    "DataProcessingException",
    "DataValidationException",
    "OptionalDependencyImportError",
    "ItsDangerousImportError",
    "RedisImportError",
    "MongoDBImportError",
    "XMLToDictImportError",
    "SQLAlchemyImportError",
    "YAMLImportError",
    "CryptographyImportError",
    "StorageCacheException",
    "KeyNotFound",
    "CacheRetrievalException",
    "CacheUpdateException",
    "CacheDeletionException",
    "CacheVerificationException",
    "PathUtilsError",
    "InvalidProcessingPathError",
    "InvalidComponentTypeError",
    "PathSimplificationError",
    "InvalidPathDelimiterError",
    "PathIndexingError",
    "InvalidPathNodeError",
    "RecordPathNodeMapError",
    "RecordPathChainMapError",
    "PathNodeIndexError",
    "PathCombinationError",
    "PathCacheError",
    "PathNodeMapError",
    "PathDiscoveryError",
]
