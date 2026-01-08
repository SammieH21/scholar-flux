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

Example:
    >>> from scholar_flux import SearchCoordinator
    >>> coordinator = SearchCoordinator(query="sight restoration", provider_name="crossref")
    >>> response = coordinator.search_page(1)
    >>>
    >>> # Check if processing succeeded
    >>> if response:
    ...     print(f"Retrieved {response.record_count} records for page {response.page} with query {response.query}")
    ...     print(f"Total available: {response.total_query_hits}")
    ...
    ...     # Normalize to common schema with post-processing
    ...     normalized = response.normalize(include = {'query', 'page', 'display_name'})
    ...     for record in normalized[:3]:
    ...         print(f"Title: {record['title']}")
    ...         print(f"Authors: {record['authors']}")  # Formatted as a list
    ...         print(f"Publisher: {record['publisher']}") # Recursively extracted
    ...         print(f"Year: {record['year']}")  # Extracted and parsed as an integer
    ...         print("-"*100)  # Already extracted
    ... else:
    ...     print(f"Error: {response.error} - {response.message}")

"""
from __future__ import annotations
from scholar_flux.api.models import ProcessedResponse, ErrorResponse
from scholar_flux.utils.response_protocol import ResponseProtocol
from scholar_flux.api.normalization import BaseFieldMap
from scholar_flux.api.models import ResponseMetadataMap
from scholar_flux.exceptions import RecordNormalizationException
from scholar_flux.api.providers import provider_registry
from scholar_flux.data.data_extractor import DataExtractor
from scholar_flux.utils.record_types import (
    RecordType,
    NormalizedRecordType,
    MetadataType,
    RecordList,
    NormalizedRecordList,
)
from scholar_flux.utils.helpers import coerce_str
from typing import Optional, Any, MutableSequence, Iterable, Iterator, Literal, Sequence, overload, TYPE_CHECKING
from requests import Response
from pydantic import BaseModel, Field, AliasChoices, computed_field
import logging

if TYPE_CHECKING:
    from re import Pattern


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

        Parsed API responses are generally formatted as dictionaries that contain the extracted JSON, XML, or YAML
        content from a successfully received, raw response.

        If an ErrorResponse was received instead, the value of this property is None.

        Returns:
            Optional[Any]:
                The parsed response when `ProcessedResponse.parsed_response` is not None. Otherwise None.

        """
        return self.response_result.parsed_response if self.response_result else None

    @property
    def extracted_records(self) -> Optional[RecordList]:
        """Contains the extracted records from the response record extraction step after successful response parsing.

        If an ErrorResponse was received instead, the value of this property is None.

        Returns:
            Optional[RecordList]:
                A list of extracted records if `ProcessedResponse.extracted_records` is not None. None otherwise.

        """
        return self.response_result.extracted_records if self.response_result else None

    @property
    def metadata(self) -> Optional[MetadataType]:
        """Contains the metadata from the API response metadata extraction step after successful response parsing.

        If an ErrorResponse was received instead, the value of this property is None.

        Returns:
            Optional[MetadataType]:
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
    def processed_records(self) -> Optional[RecordList]:
        """Contains the processed records from the API response processing step after processing the response.

        If an error response was received instead, the value of this property is None.

        Returns:
            Optional[RecordList]:
                The list of processed records if `ProcessedResponse.processed_records` is not None. None otherwise.

        """
        return self.response_result.processed_records if self.response_result else None

    @property
    def processed_metadata(self) -> Optional[MetadataType]:
        """Contains the processed metadata from the API response processing step after the response has been processed.

        If an error response was received instead, the value of this property is None.

        Returns:
            Optional[MetadataType]:
                The processed metadata dict if `ProcessedResponse.processed_metadata` is not None. None otherwise.

        """
        return self.response_result.processed_metadata if self.response_result else None

    @property
    def normalized_records(self) -> Optional[NormalizedRecordList]:
        """Contains the normalized records from the API response processing step after normalization.

        If an error response was received instead, the value of this property is None.

        Returns:
            Optional[NormalizedRecordList]:
                The list of normalized dictionary records if `ProcessedResponse.normalized_records` is not None.

        """
        return self.response_result.normalized_records if self.response_result else None

    def strip_annotations(
        self,
        records: Optional[RecordType | RecordList] = None,
    ) -> RecordList:
        """Convenience method for removing metadata annotations from a record list for clean export.

        Strips fields prefixed with underscore that were added during extraction
        for pipeline traceability (e.g., `_extraction_index`, `_record_id`).

        Args:
            records (Optional[RecordType | RecordList]): Records to strip. Defaults to `processed_records` if None.

        Returns:
            New list of records with annotation fields removed. If there are no records to strip, an empty list is
            returned instead.

        Example:
            >>> clean_data = response.strip_annotations()
            >>> df = pd.DataFrame(clean_data)  # No internal fields in DataFrame

        """
        return self.response_result.strip_annotations(records) if self.response_result is not None else []

    @property
    def data(self) -> Optional[RecordList]:
        """Alias referring back to the processed records from the ProcessedResponse or ErrorResponse.

        Contains the processed records from the API response processing step after a successfully received response has
        been processed. If an error response was received instead, the value of this property is None.

        Returns:
            Optional[RecordList]:
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
    def cached(self) -> Optional[bool]:
        """Identifies whether the current response was retrieved from the session cache.

        Returns:
            bool: True if the response is a CachedResponse object and False if it is a fresh requests.Response object
            None: Unknown (e.g., the response attribute is not a requests.Response object or subclass)

        """
        return self.response_result.cached if self.response_result is not None else None

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

    @computed_field
    def display_name(self) -> str:
        """Returns a human readable provider name for the current provider when available."""
        return provider_registry.get_display_name(self.provider_name) or self.provider_name

    def process_metadata(
        self,
        metadata_map: Optional[ResponseMetadataMap] = None,
        update_metadata: Optional[bool] = None,
    ) -> Optional[MetadataType]:
        """Processes and maps API-specific `ProcessedResponse.metadata` fields to provider-agnostic field names.

        By default, the `ResponseMetadataMap` map retrieves and converts the API-specific page-size (records per page)
        and total results (total query hits) fields to integers when possible.

        The field map is resolved in the following order of priority:

        1. User-specified field maps
        2. resolving a provider name to a ResponseMetadataMap or subclass from the registry.
        3. Resolving the URL to a ResponseMetadataMap or subclass

        If a metadata_map is not available, `None` will be returned.

        Args:
            metadata_map: (Optional[ResponseMetadataMap]):
                An optional response metadata map to use in the mapping and processing of the response metadata. If not
                provided, the metadata map is looked up via the registry using the name or URL of the current provider.
            update_metadata (Optional[bool]):
                A flag that determines whether updates should be made to the `processed_metadata` attribute after
                computation. If `None`, updates are made only if the `processed_metadata` attribute is None.

        Returns:
            MetadataType:
                A processed metadata dictionary mapping `total_query_hits` and `records_per_page` fields where possible.

        """
        if self.response_result is None:
            return None

        if not isinstance(metadata_map, ResponseMetadataMap):
            provider_config = provider_registry.get(self.provider_name)
            # if the lookup by provider name fails, the APIResponse.processed_metadata method tries by URL
            metadata_map = getattr(provider_config, "metadata_map", None)
        return self.response_result.process_metadata(metadata_map, update_metadata=update_metadata)

    def build_record_id_index(self, *args, **kwargs) -> dict[str, RecordType]:
        """Builds a lookup table mapping record IDs to their original extracted records.

        This method delegates to the underlying `ProcessedResponse` or `ErrorResponse` to build an index
        for O(1) ID-based resolution of extracted records. Useful for batch resolution operations where
        multiple records need to be resolved to their original nested structures.

        Args:
            *args:
                Positional arguments passed through to the underlying response's `build_record_id_index` method.
                The ProcessedResponse implementation accepts no positional arguments.
            **kwargs:
                Keyword arguments passed through to the underlying response's `build_record_id_index` method.
                The ProcessedResponse implementation accepts no keyword arguments.

        Returns:
            dict[str, RecordType]:
                A dictionary mapping `_record_id` values to their corresponding extracted records.
                Returns an empty dict if `response_result` is None or if no extracted records exist.

        """
        return (self.response_result.build_record_id_index(*args, **kwargs) if self.response_result else None) or {}

    def resolve_extracted_record(self, *args, **kwargs) -> Optional[RecordType]:
        """Resolves a processed record back to its original extracted record.

        This method delegates to the underlying `ProcessedResponse` or `ErrorResponse` to resolve a single
        processed record (identified by its index) back to its original extracted record with nested structure.
        Uses annotation fields (`_extraction_index`, `_record_id`) added during extraction.

        Args:
            *args:
                Positional arguments passed through to the underlying response's `resolve_extracted_record` method.
                The ProcessedResponse implementation accepts:
                - processed_index (int): Index of the record in processed_records
                - validate_id (bool): Whether to validate record ID matches (default True)
                - fallback_to_id_search (bool): Whether to search by ID if index fails (default True)
            **kwargs:
                Keyword arguments passed through to the underlying response's `resolve_extracted_record` method.

        Returns:
            Optional[RecordType]:
                The original extracted record with nested structure, or None if:
                - `response_result` is None
                - The record index is invalid
                - No matching extracted record is found

        """
        return self.response_result.resolve_extracted_record(*args, **kwargs) if self.response_result else None

    def normalize(
        self,
        field_map: Optional[BaseFieldMap] = None,
        raise_on_error: bool = False,
        update_records: Optional[bool] = None,
        resolve_records: Optional[bool] = None,
        include_api_specific_fields: Optional[bool | Sequence] = None,
        *,
        include: Optional[set[Literal["query", "provider_name", "display_name", "page"]]] = None,
        strip_annotations: Optional[bool] = None,
    ) -> NormalizedRecordList:
        """Normalizes `ProcessedResponse` record fields to map API-specific fields to provider-agnostic field names.

        The field map is resolved in the following order of priority:

        1. User-specified field maps
        2. resolving a provider name to a BaseFieldMap or subclass from the registry.
        3. Resolving the URL to a BaseFieldMap or subclass

        If a field map is not available, an empty list will be returned if `raise_on_error=False`. Otherwise, a
        `RecordNormalizationException` is raised.

        Args:
            field_map (Optional[BaseFieldMap]):
                Optional field map to use in the normalization of the record list. If not provided, the field map is
                looked up from the registry using the name or URL of the current provider.
            raise_on_error (bool):
                A flag indicating whether to raise an error. If a field_map cannot be identified for the current
                response and `raise_on_error` is also True, a normalization error is raised.
            update_records (Optional[bool]):
                A flag that determines whether updates should be made to the `normalized_records` attribute after
                computation. If `None`, updates are made only if the `normalized_records` attribute is None.
            resolve_records (Optional[bool]):
                A flag that determines if resolution with annotated records should occur. If True or None, resolution
                occurs. If False, normalization uses `processed_records` when not None and `extracted_records`
                otherwise.
            include_api_specific_fields (Optional[bool | Sequence]):
                Indicates what API-specific records should be retained from the complete list of API parameters that
                are returned. If False, only the core parameters defined by the FieldMap are returned. If True or None,
                all parameters are returned instead.
            include (Optional[set[Literal['query', 'provider_name', "display_name", 'page']]]):
                Optionally appends the specified model fields as key-value pairs to each normalized record dictionary.
                Possible fields include `provider_name`, `query`, `display_name`, and `page`. By default, no model
                fields are appended.
            strip_annotations (Optional[bool]):
                A flag indicating whether to remove metadata annotations from normalized records. If True or None,
                fields with leading underscores are removed from each normalized record.

        Returns:
            NormalizedRecordList: A list of normalized records, or empty list if normalization is unavailable.

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
            normalized_record = (
                self.response_result.normalize(
                    field_map=field_map,
                    raise_on_error=True,
                    update_records=update_records,
                    resolve_records=resolve_records,
                    include_api_specific_fields=include_api_specific_fields,
                    strip_annotations=strip_annotations,
                )
                or []
            )
            return self.with_search_fields(normalized_record, include=include) if include else normalized_record
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

    @overload
    def with_search_fields(
        self,
        records: NormalizedRecordType,
        include: Optional[set[Literal["query", "provider_name", "display_name", "page"]]] = None,
        strip_annotations: Optional[bool] = None,
    ) -> NormalizedRecordType:
        """When a normalized record is received, the same record is returned with additional search fields."""
        ...

    @overload
    def with_search_fields(
        self,
        records: NormalizedRecordList,
        include: Optional[set[Literal["query", "provider_name", "display_name", "page"]]] = None,
        strip_annotations: Optional[bool] = None,
    ) -> NormalizedRecordList:
        """When a normalized record list is received, the normalized list is returned with additional search fields."""
        ...

    @overload
    def with_search_fields(
        self,
        records: RecordType,
        include: Optional[set[Literal["query", "provider_name", "display_name", "page"]]] = None,
        strip_annotations: Optional[bool] = None,
    ) -> RecordType:
        """When a parsed record is received, the record is returned with additional search fields."""
        ...

    @overload
    def with_search_fields(
        self,
        records: RecordList | Iterator[RecordType],
        include: Optional[set[Literal["query", "provider_name", "display_name", "page"]]] = None,
        strip_annotations: Optional[bool] = None,
    ) -> RecordList:
        """When a parsed records list is received, a parsed record list with additional search fields is returned."""
        ...

    @overload
    def with_search_fields(
        self,
        records: None,
        include: Optional[set[Literal["query", "provider_name", "display_name", "page"]]] = None,
        strip_annotations: Optional[bool] = None,
    ) -> RecordType:
        """When called with None, a dictionary is returned containing the search fields indicating the request."""
        ...

    def with_search_fields(
        self,
        records: Optional[
            RecordType | Iterator[RecordType] | NormalizedRecordType | RecordList | NormalizedRecordList
        ] = None,
        include: Optional[set[Literal["query", "provider_name", "display_name", "page"]]] = None,
        strip_annotations: Optional[bool] = None,
    ) -> RecordType | NormalizedRecordType | RecordList | NormalizedRecordList:
        """Returns a record or list of record dictionaries merged with selected SearchResult fields.

        Args:
            records (RecordType | Iterator[RecordType] | NormalizedRecordType |  RecordList | NormalizedRecordList):
                The record dictionary or list of records to be merged with `SearchResult` fields.

            include:
                Set of SearchResult fields to include (default: {"provider_name", "page"}).
            strip_annotations (Optional[bool]):
                A flag indicating whether to remove metadata annotations from records. If True, fields with leading
                underscores are removed from each processed record.

        Returns:
            RecordType: A single dictionary is returned if a single parsed record is provided.
            RecordList: A list of dictionaries is returned if a list of parsed records is provided.
            NormalizedRecordType: A single normalized dictionary is returned if a single normalized record is provided.
            NormalizedRecordList: A list of normalized dictionaries is returned if a list of normalized records is provided.

        """
        try:
            fields: set = set(include) if include is not None else {"provider_name", "page"}

            # Lists of records are primarily expected by default. Iterators aren't recommended but still supported
            if isinstance(records, (list, tuple, Iterator)):
                # Will raise a TypeError if an element type is not a `record_dict`
                record_list = [(record_dict or {}) | self.model_dump(include=fields) for record_dict in records]
                return DataExtractor.strip_annotations(record_list) if strip_annotations else record_list

            if isinstance(records, dict) or records is None:
                annotated_record = (records or {}) | self.model_dump(include=fields)
                return DataExtractor.strip_annotations(annotated_record) if strip_annotations else annotated_record

            raise TypeError(
                f"Expected a dictionary or list of records to append search fields, but received type, {type(records)}"
            )
        except TypeError as e:
            raise TypeError(
                f"Encountered an invalid type when attempting to append search fields to the current input: {e}"
            )


class SearchResultList(list[SearchResult]):
    """A custom list that store the results of multiple `SearchResult` instances for enhanced type safety.

    The `SearchResultList` class inherits from a list and extends its functionality to tailor its utility to
    `ProcessedResponse` and `ErrorResponse` objects received from `SearchCoordinators` and `MultiSearchCoordinators`.

    Methods:
        - SearchResultList.append: Basic `list.append` implementation extended to accept only SearchResults
        - SearchResultList.extend: Basic `list.extend` implementation extended to accept only iterables of SearchResults
        - SearchResultList.filter: Removes NonResponses and ErrorResponses from the list of SearchResults
        - SearchResultList.select: Selects a subset of SearchResults by `query`, `provider_name`, or `page`
        - SearchResultList.join: Combines all records from ProcessedResponses into a list of dictionary-based records

    Note: Attempts to add other classes to the SearchResultList other than SearchResults will raise a TypeError.

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

        if isinstance(other, Iterator):
            other = list(other)

        if not isinstance(other, (MutableSequence, Iterable)):
            raise TypeError(f"Expected an iterable of SearchResults, received an object of type {type(other)}")

        if not (all(isinstance(item, SearchResult) for item in other)):
            raise TypeError(
                "Expected an iterable of SearchResults, but not all elements in the iterable are SearchResult elements."
            )

        super().extend(other)

    def __add__(  # type: ignore[override]
        self, other: SearchResultList | MutableSequence[SearchResult] | Iterable[SearchResult]
    ) -> SearchResultList:
        """Overrides the default `list.__add__` to return a SearchResultList.

        Args:
            other (SearchResultList | MutableSequence[SearchResult] | Iterable[SearchResult]):
                A SearchResultList, list of SearchResults, or an iterable of SearchResult instances to concatenate.

        Returns:
            SearchResultList: A new SearchResultList containing elements from both objects.

        Raises:
            TypeError: When `other` contains non-SearchResult items.

        """
        search_result_list = self.copy()
        try:
            search_result_list.extend(other)
        except TypeError as e:
            raise TypeError(
                f"Encountered an error while attempting to concatenate search results to a SearchResultList: {e} "
            ) from e
        return search_result_list

    def copy(self) -> SearchResultList:
        """Overrides the default `list.copy` to return a shallow copy as a SearchResultList.

        Returns:
            SearchResultList: A new, shallow copy of the current list.

        """
        return SearchResultList(self)

    def join(
        self,
        include: Optional[set[Literal["query", "provider_name", "display_name", "page"]]] = None,
        strip_annotations: Optional[bool] = None,
    ) -> RecordList:
        """Combines all successfully processed API responses into a single list of dictionary records across all pages.

        This method is especially useful for compatibility with pandas and polars dataframes that can accept a list of
        records when individual records are dictionaries.

        Note that this method will only load processed responses that contain records that were also successfully
        extracted and processed.

        Args:
            include (Optional[set[Literal['query', 'provider_name', "display_name", 'page']]]):
                Optionally appends the specified model fields as key-value pairs to each parsed record
                dictionary. Possible fields include `provider_name`, `display_name`, `query`, and `page`.
            strip_annotations (Optional[bool]):
                A flag indicating whether to remove metadata annotations from records. If True, fields with leading
                underscores are removed from each processed record.

        Returns:
            RecordList: A single list containing all records retrieved from each page

        """
        record_list: list[RecordType] = []

        for record in self:
            record_list.extend(
                record.with_search_fields(record.data or [], include=include, strip_annotations=strip_annotations)
            )
        return record_list

    def process_metadata(
        self,
        update_metadata: Optional[bool] = None,
        include: Optional[set[Literal["query", "provider_name", "display_name", "page"]]] = None,
    ) -> list[MetadataType]:
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
                computation. If `None`, updates are made only if the `processed_metadata` attribute is None.
            include (Optional[set[Literal['query', 'provider_name', "display_name", 'page']]]):
                Optionally appends the specified model fields as key-value pairs to each listed metadata dictionary.
                Possible fields include `provider_name`, `display_name`, `query`, and `page`.

        Returns:
            list[MetadataType]:
                A list of processed metadata dictionaries mapping `total_query_hits` and `records_per_page` fields where
                possible.

        Raises:
            RecordNormalizationException: If raise_on_error=True and no field map found.

        """
        include = include if include is not None else {"provider_name", "page", "query"}

        return [
            search_result.with_search_fields(
                search_result.process_metadata(update_metadata=update_metadata) or {}, include=include
            )
            for search_result in self
        ]

    def normalize(
        self,
        raise_on_error: bool = False,
        update_records: Optional[bool] = None,
        include: Optional[set[Literal["query", "provider_name", "display_name", "page"]]] = None,
        **kwargs,
    ) -> NormalizedRecordList:
        """Convenience method allowing the batch normalization of all SearchResults in a SearchResultList.

        Args:
            raise_on_error (bool):
                A flag indicating whether to raise an error. If False, iteration will continue through failures in
                processing such as cases where ErrorResponses and NonResponses otherwise raise a `NotImplementedError`.
                if `raise_on_error` is True, the normalization error will be raised.
            update_records (Optional[bool]):
                A flag that determines whether updates should be made to the `normalized_records` attribute after
                computation. If `None`, updates are made only if the `normalized_records` attribute is None.
            include (Optional[set[Literal['query', 'provider_name', "display_name", 'page']]]):
                Optionally appends the specified model fields as key-value pairs to each normalized record
                dictionary. Possible fields include `provider_name`, `query`, `display_name`, and `page`. By default,
                no model fields are appended.
            **kwargs:
                Additional keyword parameters forwarded to `SearchResult.normalize()`. Supported parameters include:

                - `strip_annotations` (bool): Removes internal annotation fields from normalized records
                - `resolve_records` (bool): Merges extracted and processed records when annotations exist
                - `include_api_specific_fields` (bool | Sequence): Controls API-specific field inclusion
                - `field_map` (BaseFieldMap): An optional override to the field map to be used for record normalization

        Returns:
            NormalizedRecordList:
                A list of normalized records, or an empty list if no records are available for normalization.

        Raises:
            RecordNormalizationException: If raise_on_error=True and no field map found.

        """
        try:
            return [
                record
                for result in self
                for record in result.normalize(
                    raise_on_error=raise_on_error, update_records=update_records, include=include, **kwargs
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
        provider_name: Optional[str | Pattern] = None,
        page: Optional[tuple | MutableSequence | int] = None,
        *,
        fuzzy: bool = True,
        regex: Optional[bool] = None,
    ) -> SearchResultList:
        """Helper method that enables the selection of all responses (successful or failed) based on its attributes.

        Args:
            query (Optional[str]): The exact query string to match (if provided). Ignored if None
            provider_name (Optional[str | Pattern]): The provider string or regex pattern to match (if provided). Ignored if None.
            page (Optional[tuple | MutableSequence | int]): The page or sequence of pages to match. Ignored if None.
            fuzzy (bool):
                Indicates whether fuzzy matched provider names should be included after name normalization. When True,
                `provider_registry.find()` is used to find providers within the registry with names that start with the
                prefix. Pattern matching is performed if `provider_name` is a re.Pattern. If `fuzzy=False`, then only
                strict string matches will be preserved.
            regex (Optional[bool]):
                An optional keyword parameter passed to `provider_registry.find()` when `fuzzy=True`. When True, key
                pattern matching is enabled and registered providers can be identified using regex. This parameter is
                No-Op if `fuzzy=False`.

        Returns:
            SearchResultList: A filtered list of search results containing only results that match the conditions.

        """
        if page is not None and not isinstance(page, (MutableSequence, tuple)):
            page = [page]

        # Identify known providers and coerce+normalize strings/patterns for both known/unknown providers as a fallback

        known_providers: set[str] = set()

        if provider_name:
            normalized_provider_name = provider_registry._normalize_name(coerce_str(provider_name) or "")
            known_providers |= set(provider_registry.find(provider_name, regex=regex)) if fuzzy else set()
            if normalized_provider_name:
                known_providers.add(normalized_provider_name)

        # Only use a provider, page, or query as a filter when explicitly provided:
        return SearchResultList(
            search_result
            for search_result in self
            if (query is None or search_result.query == query)
            and (
                provider_name is None
                or provider_registry._normalize_name(search_result.provider_name) in known_providers
            )
            and (not page or search_result.page in page)
        )

    @property
    def record_count(self) -> int:
        """Retrieves the overall record count across all search results if available."""
        return sum(search_result.record_count for search_result in self if search_result is not None)


__all__ = ["SearchResult", "SearchResultList"]
