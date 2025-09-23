from __future__ import annotations
from scholar_flux.api.models import ProcessedResponse, ResponseResult
from scholar_flux.utils.response_protocol import ResponseProtocol
from typing import Optional, Any, MutableSequence, Iterable
from requests import Response
from pydantic import BaseModel
import logging


logger = logging.getLogger(__name__)



class SearchResult(BaseModel):
    """
    Core class used in order to store data in the retrieval and processing of API Searches
    when iterating and searching over a range of pages, queries, and providers at a time.
    This class uses pydantic to ensure that field validation is automatic for ensuring integrity
    and reliability of response processing.

    The SearchResult class is especially important when using the SearchCoordinator.search_pages
    method to record the query, provider name, and page for a particular search across pages
    in addition to recording the result.

    Args:
        query (str): THe query used to retrieve records and response metadata
        provider_name (str): The provider where data is being retrieved
        page (int): THe page number indicating the records to retrieve when creating a response
        response_result (Optional[ProcessedResponse | ErrorResponse]):
            The ResponseResult containing the specifics of the data retrieved from the response
            or the error messages recorded if the request is not successful.
    """
    query: str
    provider_name: str
    page: int
    response_result: Optional[ResponseResult] = None

    def __bool__(self) -> bool:
        """Makes the SearchResult truthy for ProcessedResponses and False for ErrorResponses/None"""
        return isinstance(self.response_result, ProcessedResponse)

    def __len__(self) -> int:
        """
        Returns the total number of successfully processed records from the ProcessedResponse. If
        the received Response was an ErrorResponse or NoneType object, then this value will be 0,
        indicating that no records were processed successfully.
        """
        return len(self.response_result) if isinstance(self.response_result, ProcessedResponse) else 0

    @property
    def response(self) -> Optional[Response | ResponseProtocol]:
        """
        Helper method directly referencing the original or reconstructed response or response-like object
        from the API Response if available. If the received response is not available (None in the response_result),
        then this value will also be absent (None).
        """
        return (
            self.response_result.response
            if self.response_result is not None and self.response_result.validate_response()
            else None
        )

    @property
    def parsed_response(self) -> Optional[Any]:
        """
        Contains the parsed response content from the APIResponse handling steps that extract the JSON,
        XML, or YAML content from a successfully received response. If an ErrorResponse was received
        instead, the value of this property is None.
        """
        return self.response_result.parsed_response if self.response_result else None

    @property
    def extracted_records(self) -> Optional[list[Any]]:
        """
        Contains the extracted records from the APIResponse handling steps that extract individual records from
        successfully received and parsed response. If an ErrorResponse was received instead, the value of
        this property is None.
        """
        return self.response_result.extracted_records if self.response_result else None

    @property
    def metadata(self) -> Optional[Any]:
        """
        Contains the metadata from the APIResponse handling steps that extract response metadata from
        successfully received and parsed responses. If an ErrorResponse was received instead, the value of
        this property is None.
        """
        return self.response_result.metadata if self.response_result else None

    @property
    def data(self) -> Optional[list[dict[Any, Any]]]:
        """
        Contains the processed records from the APIResponse processing step after a successfully
        received response has been processed. If an error response was received instead, the value
        of this property is None.
        """
        return self.response_result.data if self.response_result else None

    @property
    def cache_key(self) -> Optional[str]:
        """
        Extracts the cache key from the API Response if available. This cache key is
        used when storing and retrieving data from response processing cache storage.
        """
        return self.response_result.cache_key if self.response_result else None

    @property
    def error(self) -> Optional[str]:
        """
        Extracts the error name associated with the result from the base class, indicating the
        name/category of the error in the event that the response_result is an ErrorResponse.
        """
        return self.response_result.error if self.response_result else None

    @property
    def message(self) -> Optional[str]:
        """
        Extracts the message associated with the result from the base class, indicating why an error occurred
        in the event that the response_result is an ErrorResponse 
        """
        return self.response_result.message if self.response_result else None

    

class SearchResultList(list[SearchResult]):
    def __setitem__(self, index, item):
        """
        Overwrites the default __setitem__ method to ensure that only SearchResult objects can
        be added to the custom list
        
        Args:
            index (int): The numeric index that defines where in the list to insert the SearchResult 
            item (SearchResult): The response result containing the API response data, the provider name,
                                 and page associated with the response
        """
        if not isinstance(item, SearchResult):
            raise TypeError(f"Expected a SearchResult, received an item of type {type(item)}")
        super().__setitem__(index, item)

    def append(self, item: SearchResult):
        """
        Overwrites the default append method on the user dict to ensure that only SearchResult objects can
        be appended to the custom list
        
        Args:
            item (SearchResult): The response result containing the API response data, the provider name,
                                 and page associated with the response
        """
        if not isinstance(item, SearchResult):
            raise TypeError(f"Expected a SearchResult, received an item of type {type(item)}")
        super().append(item)

    def extend(self, other: SearchResultList | MutableSequence[SearchResult] | Iterable[SearchResult]):
        """
        Overwrites the default append method on the user dict to ensure that only an iterable of
        SearchResult objects can be appended to the SearchResultList.
        
        Args:
            other (Iterable[SearchResult]): An iterable/sequence of response results containing the API response
            data, the provider name, and page associated with the response
        """
        if not isinstance(other, SearchResultList) and not (
            isinstance(other, (MutableSequence, Iterable)) and all(isinstance(item, SearchResult) for item in other)
        ):
            raise TypeError(f"Expected an iterable of SearchResults, received an object type {type(other)}")
        super().extend(other)

    def join(self) -> list[dict[Any, Any]]:
        """
        Helper method for joining all successfully processed API responses into a single list of dictionaries
        that can be loaded into a pandas or polars dataframe.

        Note that this method will only load processed responses that contain records that were also successfully
        extracted and processed.

        Returns:
            list[dict[Any, Any]]: A single list containing all records retrieved from each page 
        """
        return [
            (record or {}) | {'provider_name': item.provider_name, 'page_number': item.page}
            for item in self for record in getattr(item.response_result,'data', [])
            if item.response_result and item.response_result.data is not None
        ]
