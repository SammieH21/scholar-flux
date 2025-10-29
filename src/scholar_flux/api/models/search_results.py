# /api/models/search_results.py
"""The scholar_flux.api.models.search_results module defines the SearchResult and SearchResultList implementations that
aid in the retrieval of multi-page and multi-coordinated searches.

These implementations allow increased organization for the API output of multiple searches
by defining the provider, page, query, and response result retrieved from multi-page searches
from the SearchCoordinator and multi-provider/page searches using the MultiSearchCoordinator.

Classes:
    SearchResult:
        Pydantic Base class that stores the search result as well as the query, provider name, and page.
    SearchResultList:
        Inherits from a basic list to constrain the output to a list of SearchResults while providing
        data preparation convenience functions for downstream frameworks.

"""
from __future__ import annotations
from scholar_flux.api.models import ProcessedResponse, ErrorResponse
from scholar_flux.utils.response_protocol import ResponseProtocol
from typing import Optional, Any, MutableSequence, Iterable
from requests import Response
from pydantic import BaseModel
import logging


logger = logging.getLogger(__name__)


class SearchResult(BaseModel):
    """Core class used in order to store data in the retrieval and processing of API Searches when iterating and
    searching over a range of pages, queries, and providers at a time. This class uses pydantic to ensure that field
    validation is automatic for ensuring integrity and reliability of response processing. multi-page searches that link
    each response result to a particular query, page, and provider.

    Args:
        query (str): The query used to retrieve records and response metadata
        provider_name (str): The name of the provider where data is being retrieved
        page (int): The page number associated with the request for data
        response_result (Optional[ProcessedResponse | ErrorResponse]):
            The response result containing the specifics of the data retrieved from the response
            or the error messages recorded if the request is not successful.

    For convenience, the properties of the `response_result` are referenced as properties of
    the SearchResult, including: `response`, `parsed_response`, `processed_records`, etc.

    """

    query: str
    provider_name: str
    page: int
    response_result: Optional[ProcessedResponse | ErrorResponse] = None

    def __bool__(self) -> bool:
        """Makes the SearchResult truthy for ProcessedResponses and False for ErrorResponses/None."""
        return isinstance(self.response_result, ProcessedResponse)

    def __len__(self) -> int:
        """Returns the total number of successfully processed records from the ProcessedResponse.

        If the received Response was an ErrorResponse or None, then this value will be 0, indicating that no records
        were processed successfully.

        """
        return len(self.response_result) if isinstance(self.response_result, ProcessedResponse) else 0

    @property
    def response(self) -> Optional[Response | ResponseProtocol]:
        """Helper method directly referencing the original or reconstructed response or response-like object from the
        API Response if available.

        If the received response is not available (None in the response_result), then this value will also be absent
        (None).

        """
        return (
            self.response_result.response
            if self.response_result is not None and self.response_result.validate_response()
            else None
        )

    @property
    def parsed_response(self) -> Optional[Any]:
        """Contains the parsed response content from the APIResponse handling steps that extract the JSON, XML, or YAML
        content from a successfully received response.

        If an ErrorResponse was received instead, the value of this property is None.

        """
        return self.response_result.parsed_response if self.response_result else None

    @property
    def extracted_records(self) -> Optional[list[Any]]:
        """Contains the extracted records from the APIResponse handling steps that extract individual records from
        successfully received and parsed response.

        If an ErrorResponse was received instead, the value of this property is None.

        """
        return self.response_result.extracted_records if self.response_result else None

    @property
    def metadata(self) -> Optional[Any]:
        """Contains the metadata from the APIResponse handling steps that extract response metadata from successfully
        received and parsed responses.

        If an ErrorResponse was received instead, the value of this property is None.

        """
        return self.response_result.metadata if self.response_result else None

    @property
    def processed_records(self) -> Optional[list[dict[Any, Any]]]:
        """Contains the processed records from the APIResponse processing step after a successfully received response
        has been processed.

        If an error response was received instead, the value of this property is None.

        """
        return self.response_result.processed_records if self.response_result else None

    @property
    def data(self) -> Optional[list[dict[Any, Any]]]:
        """Alias referring back to the processed records from the ProcessedResponse or ErrorResponse.

        Contains the processed records from the APIResponse processing step after a successfully received response has
        been processed. If an error response was received instead, the value of this property is None.

        """
        return self.response_result.data if self.response_result else None

    @property
    def cache_key(self) -> Optional[str]:
        """Extracts the cache key from the API Response if available.

        This cache key is used when storing and retrieving data from response processing cache storage.

        """
        return self.response_result.cache_key if self.response_result else None

    @property
    def error(self) -> Optional[str]:
        """Extracts the error name associated with the result from the base class, indicating the name/category of the
        error in the event that the response_result is an ErrorResponse."""
        return self.response_result.error if isinstance(self.response_result, ErrorResponse) else None

    @property
    def message(self) -> Optional[str]:
        """Extracts the message associated with the result from the base class, indicating why an error occurred in the
        event that the response_result is an ErrorResponse."""
        return self.response_result.message if isinstance(self.response_result, ErrorResponse) else None

    @property
    def created_at(self) -> Optional[str]:
        """Extracts the time in which the ErrorResponse or ProcessedResponse was created, if available."""
        return (
            self.response_result.created_at
            if isinstance(self.response_result, (ErrorResponse, ProcessedResponse))
            else None
        )

    def __eq__(self, other: Any) -> bool:
        """Helper method for determining whether two search results are equal. The equality check operates by
        determining whether the other object is, first, a SearchResult instance. If it is, the components are dumped
        into a dictionary and checked for equality.

        Args:
            other (Any): An object to compare against the current search result

        Returns:
            bool: True if the class is the same and all components are equal, False otherwise.

        """
        if not isinstance(other, self.__class__):
            return False
        return self.model_dump() == other.model_dump()


class SearchResultList(list[SearchResult]):
    """A helper class used to store the results of multiple SearchResult instances for enhanced type safety. This class
    inherits from a list and extends its functionality to tailor its functionality to APIResponses received from
    SearchCoordinators and MultiSearchCoordinators.

    Methods:
        - SearchResultList.append: Basic `list.append` implementation extended to accept only SearchResults
        - SearchResultList.extend: Basic `list.extend` implementation extended to accept only iterables of SearchResults
        - SearchResultList.filter: Removes NonResponses and ErrorResponses from the list of SearchResults
        - SearchResultList.filter: Removes NonResponses and ErrorResponses from the list of SearchResults
        - SearchResultList.join: Combines all records from ProcessedResponses into a list of dictionary-based records

    Note Attempts to add other classes to the SearchResultList other than SearchResults will raise a TypeError.

    """

    def __setitem__(self, index, item):
        """Overwrites the default __setitem__ method to ensure that only SearchResult objects can be added to the custom
        list.

        Args:
            index (int): The numeric index that defines where in the list to insert the SearchResult
            item (SearchResult):
                The response result containing the API response data, the provider name, and page associated
                with the response.

        """
        if not isinstance(item, SearchResult):
            raise TypeError(f"Expected a SearchResult, received an item of type {type(item)}")
        super().__setitem__(index, item)

    def append(self, item: SearchResult):
        """Overwrites the default append method on the user dict to ensure that only SearchResult objects can be
        appended to the custom list.

        Args:
            item (SearchResult):
                The response result containing the API response data, the provider name, and page associated with
                the response.

        """
        if not isinstance(item, SearchResult):
            raise TypeError(f"Expected a SearchResult, received an item of type {type(item)}")
        super().append(item)

    def extend(self, other: SearchResultList | MutableSequence[SearchResult] | Iterable[SearchResult]):
        """Overwrites the default append method on the user dict to ensure that only an iterable of SearchResult objects
        can be appended to the SearchResultList.

        Args:
            other (Iterable[SearchResult]): An iterable/sequence of response results containing the API response
            data, the provider name, and page associated with the response

        """
        if not isinstance(other, SearchResultList) and not (
            isinstance(other, (MutableSequence, Iterable)) and all(isinstance(item, SearchResult) for item in other)
        ):
            raise TypeError(f"Expected an iterable of SearchResults, received an object type {type(other)}")
        super().extend(other)

    def join(self) -> list[dict[str, Any]]:
        """Helper method for joining all successfully processed API responses into a single list of dictionaries that
        can be loaded into a pandas or polars dataframe.

        Note that this method will only load processed responses that contain records that were also successfully
        extracted and processed.

        Returns:
            list[dict[str, Any]]: A single list containing all records retrieved from each page

        """
        return [self._resolve_record(record, item) for item in self for record in self._get_records(item) if record]

    @classmethod
    def _get_records(cls, item: SearchResult) -> list[dict[str, Any]]:
        """Extracts a list of records (dictionaries) from a SearchResult."""
        records = (
            None if not isinstance(item, SearchResult) or item.response_result is None else item.response_result.data
        )

        return records or []

    @classmethod
    def _resolve_record(cls, record: Optional[dict], item: SearchResult) -> dict[str, Any]:
        """Formats the current record and appends the provider_name and page number to the record."""
        record_dict = record or {}
        return record_dict | {"provider_name": item.provider_name, "page_number": item.page}

    def filter(self) -> SearchResultList:
        """Helper method that retains only elements from the original response that indicate successful processing."""
        return SearchResultList(item for item in self if isinstance(item.response_result, ProcessedResponse))


__all__ = ["SearchResult", "SearchResultList"]
