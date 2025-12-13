# /api/models/search_results.py
"""The scholar_flux.api.models.search_results module defines the SearchResult and SearchResultList implementations.

These two classes are containers of API response data and aid in the storage of retrieved and processed response results
while allowing the efficient identification of individual queries to providers from both multi-page and
multi-coordinated searches.

These implementations allow increased organization for the API output of multiple searches by defining the provider, page,
query, and response result retrieved from multi-page searches from the SearchCoordinator and multi-provider/page searches
using the MultiSearchCoordinator.

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
from scholar_flux.api.normalization import BaseFieldMap
from scholar_flux.api.models import ResponseMetadataMap
from scholar_flux.exceptions import RecordNormalizationException
from scholar_flux.api.providers import provider_registry
from typing import Optional, Any, MutableSequence, Iterable, Literal
from requests import Response
from pydantic import BaseModel, Field, AliasChoices
import logging


logger = logging.getLogger(__name__)


class SearchResult(BaseModel):
    """Core container for search results that stores the retrieved and processed data from API Searches.

    This class is useful when iterating and searching over a range of pages, queries, and providers at a time.
    This class uses pydantic to ensure that field validation is automatic, ensuring integrity and reliability
    of response processing. This supports multi-page searches that link each response result to a particular
    query, page, and provider.

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
    page: int = Field(..., ge=0, validation_alias=AliasChoices("page", "page_number"))
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
    def record_count(self) -> int:
        """Retrieves the overall length of the `processed_record` field from the API response if available."""
        return len(self)

    @property
    def response(self) -> Optional[Response | ResponseProtocol]:
        """Directly references the raw response or response-like object from the API Response if available.

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
        """Contains the parsed response content from the API response parsing step.

        The parsed response is generally a dictionary that contains the extracted the JSON, XML, or YAML content from a
        successfully received response.

        If an ErrorResponse was received instead, the value of this property is None.

        Returns:
            Optional[Any]:
                The parsed response when `ProcessedResponse.parsed_response` is not None. Otherwise None.

        """
        return self.response_result.parsed_response if self.response_result else None

    @property
    def extracted_records(self) -> Optional[list[Any]]:
        """Contains the extracted records from the response record extraction step after successful response parsing.

        If an ErrorResponse was received instead, the value of this property is None.

        Returns:
            Optional[list[Any]]:
                A list of extracted records if `ProcessedResponse.extracted_records` is not None. None otherwise.

        """
        return self.response_result.extracted_records if self.response_result else None

    @property
    def metadata(self) -> Optional[Any]:
        """Contains the metadata from the API response metadata extraction step after successful response parsing.

        If an ErrorResponse was received instead, the value of this property is None.

        Returns:
            Optional[dict[str, Any]]:
                A dictionary of metadata if `ProcessedResponse.metadata` is not None. None otherwise.

        """
        return self.response_result.metadata if self.response_result else None

    @property
    def total_query_hits(self) -> Optional[int]:
        """Returns the total number of query hits according to the processed metadata field specific to the API."""
        return self.response_result.total_query_hits if self.response_result else None

    @property
    def records_per_page(self) -> Optional[int]:
        """Returns the number of records sent on the current page according to the API-specific metadata field."""
        return self.response_result.records_per_page if self.response_result else None

    @property
    def processed_records(self) -> Optional[list[dict[Any, Any]]]:
        """Contains the processed records from the API response processing step after a processing the response.

        If an error response was received instead, the value of this property is None.

        Returns:
            Optional[list[dict[Any, Any]]]:
                The list of processed records if `ProcessedResponse.processed_records` is not None. None otherwise.

        """
        return self.response_result.processed_records if self.response_result else None

    @property
    def processed_metadata(self) -> Optional[dict[str, Any]]:
        """Contains the processed metadata from the API response processing step after the response has been processed.

        If an error response was received instead, the value of this property is None.

        Returns:
            Optional[dict[str, Any]]:
                The processed metadata dict if `ProcessedResponse.processed_metadata` is not None. None otherwise.

        """
        return self.response_result.processed_metadata if self.response_result else None

    @property
    def normalized_records(self) -> Optional[list[dict[Any, Any]]]:
        """Contains the normalized records from the API response processing step after normalization.

        If an error response was received instead, the value of this property is None.

        Returns:
            Optional[list[dict[Any, Any]]]:
                The list of normalized records if `ProcessedResponse.normalized_records` is not None. None otherwise.

        """
        return self.response_result.normalized_records if self.response_result else None

    @property
    def data(self) -> Optional[list[dict[Any, Any]]]:
        """Alias referring back to the processed records from the ProcessedResponse or ErrorResponse.

        Contains the processed records from the API response processing step after a successfully received response has
        been processed. If an error response was received instead, the value of this property is None.

        Returns:
            Optional[list[dict[Any, Any]]]:
                The list of processed records if `ProcessedResponse.data` is not None. None otherwise.

        """
        return self.response_result.data if self.response_result else None

    @property
    def cache_key(self) -> Optional[str]:
        """Extracts the cache key from the API Response if available.

        This cache key is used when storing and retrieving data from response processing cache storage.


        Returns:
            Optional[str]: The key if the `response_result` contains a `cache_key` that is not None. None otherwise.

        """
        return (
            self.response_result.cache_key
            if isinstance(self.response_result, (ProcessedResponse, ErrorResponse))
            else None
        )

    @property
    def error(self) -> Optional[str]:
        """Extracts the error name associated with the result from the base class.

        This field is generally populated when `ErrorResponse` objects are received and indicates why an error occurred.

        Returns:
            Optional[str]:
                The error if the `response_result` is an `ErrorResponse` with a populated `error` field. None otherwise.

        """
        return self.response_result.error if isinstance(self.response_result, ErrorResponse) else None

    @property
    def message(self) -> Optional[str]:
        """Extracts the message associated with the result from the base class.

        This message is generally populated when `ErrorResponse` objects are received and indicates why an error
        occurred in the event that the response_result is an ErrorResponse.

        Returns:
            Optional[str]:
                The message if the `ProcessedResponse.message` or `ErrorResponse.message` is not None. None otherwise.

        """
        return self.response_result.message if isinstance(self.response_result, ErrorResponse) else None

    @property
    def created_at(self) -> Optional[str]:
        """Extracts the time in which the ErrorResponse or ProcessedResponse was created, if available."""
        return (
            self.response_result.created_at
            if isinstance(self.response_result, (ErrorResponse, ProcessedResponse))
            else None
        )

    @property
    def url(self) -> Optional[str]:
        """Extracts the URL from the underlying response, if available."""
        return self.response_result.url if self.response_result is not None else None

    @property
    def status_code(self) -> Optional[int]:
        """Extracts the HTTP status code from the underlying response, if available."""
        return self.response_result.status_code if self.response_result is not None else None

    @property
    def status(self) -> Optional[str]:
        """Extracts the human-readable status description from the underlying response, if available."""
        return self.response_result.status if self.response_result is not None else None

    def process_metadata(
        self,
        metadata_map: Optional[ResponseMetadataMap] = None,
        update_metadata: Optional[bool] = None,
    ) -> Optional[dict[str, Any]]:
        """Processes the `ProcessedResponse.metadata` field to map metadata fields to provider-agnostic field names.

        By default, the `ResponseMetadataMap` map retrieves and converts the API-specific page-size (records per page)
        and total results (total query hits) fields to integers when possible.

        The field map is resolved in the following order of priority:

        1. User-specified field maps
        2. resolving a provider name to a BaseFieldMap or subclass from the registry.
        3. Resolving the URL to a BaseFieldMap or subclass

        If a metadata_map is not available, `None` will be returned.

        Args:
            metadata_map: (Optional[ResponseMetadataMap]):
                An optional response metadata map to use in the mapping and processing of the response metadata. If not
                provided, the metadata map is looked up via the registry using the name or URL of the current provider.
            update_metadata (Optional[bool]):
                A flag that determines whether updates should be made to the `normalized_records` attribute after
                computation. If `None`, updates are made only if the `normalized_records` attribute is None.

        Returns:
            dict[str, Any]:
                A processed metadata dictionary mapping `total_query_hits` and `records_per_page` fields where possible.

        Raises:
            RecordNormalizationException: If raise_on_error=True and no field map found.

        """
        if self.response_result is None:
            return None

        if not isinstance(metadata_map, ResponseMetadataMap):
            provider_config = provider_registry.get(self.provider_name)
            # if the lookup by provider name fails, the APIResponse.processed_metadata method tries by URL
            metadata_map = getattr(provider_config, "metadata_map", None)
        return self.response_result.process_metadata(metadata_map, update_metadata=update_metadata)

    def normalize(
        self,
        field_map: Optional[BaseFieldMap] = None,
        raise_on_error: bool = False,
        update_records: Optional[bool] = None,
    ) -> list[dict[str, Any]]:
        """Normalizes `ProcessedResponse` record fields to map API-specific fields to provider-agnostic field names.

        The field map is resolved in the following order of priority:

        1. User-specified field maps
        2. resolving a provider name to a BaseFieldMap or subclass from the registry.
        3. Resolving the URL to a BaseFieldMap or subclass

        If a field map is not available, an empty list will be returned if `raise_on_error=False`. Otherwise, a
        `RecordNormalizationException` is raised.

        Args:
            field_map (Optional[field_map]):
                Optional field map to use in the normalization of the record list. If not provided, the field map is
                looked up from the registry using the name or URL of the current provider.
            raise_on_error (bool):
                A flag indicating whether to raise an error. If a field_map cannot be identified for the current
                response and `raise_on_error` is also True, a normalization error is raised.
            update_records (Optional[bool]):
                A flag that determines whether updates should be made to the `normalized_records` attribute after
                computation. If `None`, updates are made only if the `normalized_records` attribute is None.

        Returns:
            list[dict[str, Any]]: A list of normalized records, or empty list if normalization is unavailable.

        Raises:
            RecordNormalizationException: If raise_on_error=True and no field map found.

        """
        try:
            if self.response_result is None:
                raise RecordNormalizationException("Cannot normalize a response result of type `None`.")

            if field_map is None:
                provider_config = provider_registry.get(self.provider_name)
                # if the lookup by provider name fails, the APIResponse.normalize method tries by URL
                field_map = getattr(provider_config, "field_map", None)
            return (
                self.response_result.normalize(field_map=field_map, raise_on_error=True, update_records=update_records)
                or []
            )
        except (RecordNormalizationException, NotImplementedError) as e:
            msg = (
                f"The normalization of the page {self.page} response result for provider, {self.provider_name} failed: "
                f"{e}"
            )

            if raise_on_error:
                raise RecordNormalizationException(msg) from e
            logger.warning(f"{msg} Returning an empty list.")
        return []

    def __eq__(self, other: Any) -> bool:
        """Helper method for determining whether two search results are equal.

        The equality check operates by determining whether the other object is, first, a SearchResult instance. If it
        is, the components are dumped into a dictionary and checked for equality.

        Args:
            other (Any): An object to compare against the current search result

        Returns:
            bool: True if the class is the same and all components are equal, False otherwise.

        """
        if not isinstance(other, self.__class__):
            return False
        return self.model_dump() == other.model_dump()


class SearchResultList(list[SearchResult]):
    """A custom list that store the results of multiple `SearchResult` instances for enhanced type safety.

    The `SearchResultList` class inherits from a list and extends its functionality to tailor its utility to
    `ProcessedResponse` and `ErrorResponse` objects received from `SearchCoordinators` and `MultiSearchCoordinators`.

    Methods:
        - SearchResultList.append: Basic `list.append` implementation extended to accept only SearchResults
        - SearchResultList.extend: Basic `list.extend` implementation extended to accept only iterables of SearchResults
        - SearchResultList.filter: Removes NonResponses and ErrorResponses from the list of SearchResults
        - SearchResultList.filter: Removes NonResponses and ErrorResponses from the list of SearchResults
        - SearchResultList.join: Combines all records from ProcessedResponses into a list of dictionary-based records

    Note Attempts to add other classes to the SearchResultList other than SearchResults will raise a TypeError.

    """

    def __setitem__(self, index, item):
        """Overrides the default `list.__setitem__` method to ensure that only `SearchResult` objects can be added.

        This override ensures that only SearchResult objects can be added to the `SearchResultList`. For all other
        types, a TypeError will be raised when attempting to insert a non `SearchResult` into the `SearchResultList`.

        Args:
            index (int):
                The numeric index that defines where the SearchResult should be inserted within the `SearchResultList`.
            item (SearchResult):
                The response result containing the API response data, the provider name, and page associated
                with the response.

        """
        if not isinstance(item, SearchResult):
            raise TypeError(f"Expected a SearchResult, received an item of type {type(item)}")
        super().__setitem__(index, item)

    def append(self, item: SearchResult):
        """Overrides the default `list.append` method for type-checking compatibility.

        This override ensures that only SearchResult objects can be appended to the `SearchResultList`. For all other
        types, a TypeError will be raised when attempting to append it to the `SearchResultList.`

        Args:
            item (SearchResult):
                A `SearchResult` containing API response data, the name of the queried provider, the query, and the page
                number associated with the `ProcessedResponse` or `ErrorResponse` response result.

        Raises:
            TypeError: When the item to append to the `SearchResultList` is not a `SearchResult`.

        """
        if not isinstance(item, SearchResult):
            raise TypeError(f"Expected a SearchResult, received an item of type {type(item)}")
        super().append(item)

    def extend(self, other: SearchResultList | MutableSequence[SearchResult] | Iterable[SearchResult]):
        """Overrides the default `list.extend` method for type-checking compatibility.

        This override ensures that only an iterable of SearchResult objects can be appended to the SearchResultList. For
        all other types, a TypeError will be raised when attempting to extend the `SearchResultList` with them.

        Args:
            other (Iterable[SearchResult]): An iterable/sequence of response results containing the API response
            data, the provider name, and page associated with the response

        Raises:
            TypeError:
                When the item used to extend the `SearchResultList` is not a mutable sequence of `SearchResult`
                instances

        """
        if not isinstance(other, SearchResultList) and not (
            isinstance(other, (MutableSequence, Iterable)) and all(isinstance(item, SearchResult) for item in other)
        ):
            raise TypeError(f"Expected an iterable of SearchResults, received an object type {type(other)}")
        super().extend(other)

    def join(self, include: Optional[set[Literal["query", "provider_name", "page"]]] = None) -> list[dict[str, Any]]:
        """Combines all successfully processed API responses into a single list of dictionary records across all pages.

        This method is especially useful for compatibility with pandas and polars dataframes that can accept a list of
        records when individual records are dictionaries.

        Note that this method will only load processed responses that contain records that were also successfully
        extracted and processed.

        Args:
            include (Optional[set[Literal['query', 'provider_name', 'page']]]):
                Optionally appends the specified model fields as key-value pairs to each normalized record
                dictionary. Possible fields include `provider_name`, `query`, and `page`.

        Returns:
            list[dict[str, Any]]: A single list containing all records retrieved from each page

        """
        return [
            self._resolve_record(record, item, include) for item in self for record in self._get_records(item) if record
        ]

    @classmethod
    def _get_records(cls, item: SearchResult) -> list[dict[str, Any]] | list[dict[str | int, Any]]:
        """Extracts a list of records (dictionaries) from a SearchResult."""
        records = (
            None if not isinstance(item, SearchResult) or item.response_result is None else item.response_result.data
        )

        return records or []

    @classmethod
    def _resolve_record(
        cls,
        record: Optional[dict],
        item: SearchResult,
        include: Optional[set[Literal["query", "provider_name", "page"]]] = None,
    ) -> dict[str, Any]:
        """Formats the current record and appends the provider_name and page number to the record."""
        fields = include if include is not None else ("provider_name", "page")
        record_dict = record or {}
        return record_dict | item.model_dump(include=set(fields))

    def process_metadata(
        self,
        update_metadata: Optional[bool] = None,
        include: Optional[set[Literal["query", "provider_name", "page"]]] = None,
    ) -> list[dict[str, Any]]:
        """Processes the `ProcessedResponse.metadata` field to map metadata fields to provider-agnostic field names.

        By default, the `ResponseMetadataMap` map retrieves and converts the API-specific page-size (records per page)
        and total results (total query hits) fields to integers when possible.

        The field map is resolved in the following order of priority:

        1. User-specified field maps
        2. resolving a provider name to a BaseFieldMap or subclass from the registry.
        3. Resolving the URL to a BaseFieldMap or subclass

        Args:
            update_metadata (Optional[bool]):
                A flag that determines whether updates should be made to the `processed_metadata` attribute after
                computation. If `None`, updates are made only if the `normalized_records` attribute is None.
            include (Optional[set[Literal['query', 'provider_name', 'page']]]):
                Optionally appends the specified model fields as key-value pairs to each normalized record
                dictionary. Possible fields include `provider_name`, `query`, and `page`.

        Returns:
            list[dict[str, Any]]:
                A processed metadata dictionary mapping `total_query_hits` and `records_per_page` fields where possible.

        Raises:
            RecordNormalizationException: If raise_on_error=True and no field map found.

        """
        include = include if include is not None else {"provider_name", "page", "query"}

        return [
            self._resolve_record(
                search_result.process_metadata(update_metadata=update_metadata), search_result, include=include
            )
            for search_result in self
        ]

    def normalize(
        self,
        raise_on_error: bool = False,
        update_records: Optional[bool] = None,
        include: Optional[set[Literal["query", "provider_name", "page"]]] = None,
    ) -> list[dict[str, Any]]:
        """Convenience method allowing the batch normalization of all SearchResults in a SearchResultList.

        Args:
            raise_on_error (bool):
                A flag indicating whether to raise an error. If False, iteration will continue through failures in
                processing such as cases where ErrorResponses and NonResponses otherwise raise a `NotImplementedError`.
                if `raise_on_error` is True, the normalization error will be raised.
            update_records (Optional[bool]):
                A flag that determines whether updates should be made to the `normalized_records` attribute after
                computation. If `None`, updates are made only if the `normalized_records` attribute is None.
            include (Optional[set[Literal['query', 'provider_name', 'page']]]):
                Optionally appends the specified model fields as key-value pairs to each normalized record
                dictionary. Possible fields include `provider_name`, `query`, and `page`. By default,
                no model fields are appended.

        Returns:
            list[dict[str, Any]]:
                A list of normalized records, or an empty list if no records are available for normalization.

        Raises:
            RecordNormalizationException: If raise_on_error=True and no field map found.

        """
        try:
            return [
                (
                    self._resolve_record(normalized_records, search_result, include=include)
                    if include
                    else normalized_records
                )
                for search_result in self
                for normalized_records in search_result.normalize(
                    raise_on_error=raise_on_error, update_records=update_records
                )
            ]
        except RecordNormalizationException as e:
            msg = f"An error was encountered during the batch normalization of a search result list: {e}"
            raise RecordNormalizationException(msg)

    def filter(self, invert: bool = False) -> SearchResultList:
        """Helper method that retains only elements from the original response that indicate successful processing.

        Args:
            invert (bool):
                Controls whether SearchResults containing ProcessedResponses or ErrorResponses should be selected.
                If True, ProcessedResponses are omitted from the filtered SearchResultList. Otherwise, only
                ProcessedResponses are retained.

        """
        return SearchResultList(
            search_result
            for search_result in self
            if isinstance(search_result.response_result, ProcessedResponse) ^ bool(invert)
        )

    def select(
        self,
        query: Optional[str] = None,
        provider_name: Optional[str] = None,
        page: Optional[tuple | MutableSequence | int] = None,
    ) -> SearchResultList:
        """Helper method that enables the selection of all responses (successful or failed) based on its attributes."""
        if page is not None and not isinstance(page, (MutableSequence, tuple)):
            page = [page]

        provider_name = (
            provider_registry._normalize_name(provider_name) if isinstance(provider_name, str) else provider_name
        )

        return SearchResultList(
            search_result
            for search_result in self
            if (query is None or search_result.query == query)
            and (
                provider_name is None or provider_registry._normalize_name(search_result.provider_name) == provider_name
            )
            and (not page or search_result.page in page)
        )

    @property
    def record_count(self) -> int:
        """Retrieves the overall record count across all search results if available."""
        return sum(search_result.record_count for search_result in self if search_result is not None)


__all__ = ["SearchResult", "SearchResultList"]
