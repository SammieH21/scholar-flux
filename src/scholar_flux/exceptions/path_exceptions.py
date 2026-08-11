## path_exceptions.py
"""The scholar_flux.exceptions.path_exceptions module implements the fundamental exception types necessary to interact
with various path processing utilities while accounting for any potential errors that are specific to path
processing."""


class PathUtilsError(Exception):
    """Exception class raised for invalid operations in Path Utilities."""


class InvalidProcessingPathError(PathUtilsError):
    """Exception class raised for invalid operations on ProcessingPaths."""


class InvalidComponentTypeError(PathUtilsError):
    """Exception class raised for invalid inputs to ProcessingPath component types."""


class PathSimplificationError(PathUtilsError):
    """Exception raised for when encountering invalid values during simplification."""


class InvalidPathDelimiterError(InvalidProcessingPathError):
    """Exception raised for invalid delimiters used in ProcessingPath."""


class PathIndexingError(InvalidProcessingPathError):
    """Exception raised when attempting to retrieve the first element of a ProcessingPath as a record/page index."""


class InvalidPathNodeError(PathUtilsError):
    """Exception raised for invalid operations resulting from the handling of PathNodes."""


class RecordPathChainMapError(PathUtilsError):
    """Exception raised for invalid operations on a RecordPathChainMap."""


class PathNodeIndexError(PathUtilsError):
    """Exception raised when performing an invalid operation on a PathNodeIndex."""


class PathCombinationError(PathUtilsError):
    """Exception raised when an invalid operation occurs during the combination of PathNodes within a PathNodeIndex."""


class PathCacheError(PathUtilsError):
    """Exception raised when attempting to perform an invalid operation on the PathProcessingCache."""


class PathNodeMapError(PathUtilsError):
    """Exception raised when attempting to perform an invalid operation on a PathNodeMap."""


class RecordPathNodeMapError(PathNodeMapError):
    """Exception raised when attempting to perform an invalid operation on a RecordPathNodeMap."""


class PathDiscoveryError(PathUtilsError):
    """Exception raised for invalid operations resulting from the handling of PathNodes."""


__all__ = [
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
