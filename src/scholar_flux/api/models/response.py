from typing import Optional, Dict, List, Any

from dataclasses import dataclass
@dataclass(frozen=True)
class ProcessedResponse:
    cache_key: Optional[str] = None
    response: Optional[Any] = None
    metadata: Optional[Any] = None
    parsed_response: Optional[Any] = None
    extracted_records: Optional[Any] = None
    data: Optional[List[Dict[Any, Any]]] = None

    def __repr__(self):
        return (f"<ProcessedResponse(len={len(self.data or [])}, "
                f"cache_key={self.cache_key!r}, metadata={self.metadata!r})>")

    def __len__(self):
        return len(self.data or [])

    def __bool__(self):
        """
        Whether the response object is Truthy or not depends on
        whether the `data` attribute exists
        """
        return bool(self.data)
