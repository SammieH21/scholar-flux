from typing import Optional, Dict, List, Any
from pydantic import BaseModel

class APIResponse(BaseModel):
    """All outcomes of our API wrapper inherit from this."""
    pass

class ErrorResponse(APIResponse):
    """
    Returned when something goes wrong, but we don’t want
    to throw immediately—just hand back failure details.
    """
    cache_key: Optional[str] = None
    response: Optional[Any] = None
    message: Optional[str] = None
    error: Optional[str] = None
    metadata: None = None
    parsed_response: None = None
    extracted_records: None = None
    data: None = None

    def __repr__(self):
        # show the class of the error and its message
        return (f"<ErrorResponse(error={self.error}, "
                f"message={self.message!r})>")

    def __bool__(self):
        return False


class ProcessedResponse(APIResponse):
    """
    Helper class for returning a processed object containing
    either
    """
    cache_key: Optional[str] = None
    response: Optional[Any] = None
    metadata: Optional[Any] = None
    parsed_response: Optional[Any] = None
    extracted_records: Optional[Any] = None
    data: Optional[List[Dict[Any, Any]]] = None
    message: Optional[str] = None
    error: None = None

    def __repr__(self):
        return (f"<ProcessedResponse(len={len(self.data or [])}, "
                f"cache_key={self.cache_key!r}, metadata={str(self.metadata)[:40]+'...' if isinstance(self.metadata, (dict, list, str)) else self.metadata!r})>")

    def __len__(self):
        return len(self.data or [])

    def __bool__(self):
        """
        Whether the response object is Truthy or not depends on
        whether the `data` attribute exists
        """
        return True
