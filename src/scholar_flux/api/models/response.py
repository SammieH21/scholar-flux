from typing import Optional, Dict, List, Any
from pydantic import BaseModel
from http.client import responses
from scholar_flux.utils import try_int


class APIResponse(BaseModel):
    """All outcomes of our API wrapper inherit from this."""

    cache_key: Optional[str] = None
    response: Optional[Any] = None

    @property
    def status_code(self) -> Optional[int]:
        """
        Helper property from retrieving a status code from the APIResponse

        Returns:
            Optional[int]: The status code associated with the response (if available)
        """
        try:
            status_code = getattr(self.response, "status_code", None)
            return status_code if isinstance(status_code, int) else try_int(status_code)
        except (ValueError, AttributeError):
            return None

    @property
    def status(self) -> Optional[str]:
        """
        Helper property from retrieving a human-readable status description APIResponse

        Returns:
            Optional[int]: The status description associated with the response (if available)
        """
        return responses.get(self.status_code) if self.status_code else None


class ErrorResponse(APIResponse):
    """
    Returned when something goes wrong, but we don’t want
    to throw immediately—just hand back failure details.
    """

    message: Optional[str] = None
    error: Optional[str] = None
    metadata: None = None
    parsed_response: None = None
    extracted_records: None = None
    data: None = None

    def __repr__(self):
        # show the class of the error and its message
        return f"<ErrorResponse(error={self.error}, " f"message={self.message!r})>"

    def __bool__(self):
        return False


class ProcessedResponse(APIResponse):
    """
    Helper class for returning a processed object containing
    either
    """

    metadata: Optional[Any] = None
    parsed_response: Optional[Any] = None
    extracted_records: Optional[List[Any]] = None
    data: Optional[List[Dict[Any, Any]]] = None
    message: Optional[str] = None
    error: None = None

    def __repr__(self):
        return (
            f"<ProcessedResponse(len={len(self.data or [])}, "
            f"cache_key={self.cache_key!r}, metadata={str(self.metadata)[:40]+'...' if isinstance(self.metadata, (dict, list, str)) else self.metadata!r})>"
        )

    def __len__(self):
        return len(self.data or [])

    def __bool__(self):
        """
        Whether the response object is Truthy or not depends on
        whether the `data` attribute exists
        """
        return True
