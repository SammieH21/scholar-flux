## path_exceptions.py

class PathUtilsError(Exception):
    """Exception class raised for invalid operations in Path Utilities"""
    pass

class InvalidProcessingPathError(PathUtilsError):
    """Exception class raised for invalid operations on ProcessingPaths"""
    pass

class InvalidComponentTypeError(PathUtilsError):
    """Exception class raised for invalid inputs to ProcessingPath component types"""
    pass

class PathSimplificationError(PathUtilsError):
    """Exception raised for when encountering invalid values during simplification."""
    pass

class InvalidPathDelimiterError(InvalidProcessingPathError):
    """Exception raised for invalid delimiters used in ProcessingPath."""
    pass

class PathIndexingError(InvalidProcessingPathError):
    """Exception raised when attempting to retrieve the first element of attempting
       ProcessingPath as a record/page index"""
    pass

class InvalidPathNodeError(PathUtilsError):
    """Exception raised for invalid operations resulting from the handling of PathNodes."""
    pass

class PathNodeIndexError(PathUtilsError):
    """Exception raised when performing an invalid operation on a PathNodeIndex"""
    pass

class PathCombinationError(PathUtilsError):
    """
    Exception raised when performing an invalid operation during the combination of 
    athNodes within a PathNodeIndex
    """
    pass

class PathCacheError(PathUtilsError):
    """Exception raised when attempting to perform an invalid operation on path cache"""
    pass

class PathNodeMapError(PathUtilsError):
    """Exception raised when attempting to perform an invalid operation a PathNodeMap"""
    pass


class PathDiscoveryError(PathUtilsError):
    """Exception raised for invalid operations resulting from the handling of PathNodes."""
    pass
