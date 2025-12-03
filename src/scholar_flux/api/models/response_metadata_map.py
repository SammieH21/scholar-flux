# /api/models/response_metadata_map.py
"""The scholar_flux.api.models.response_metadata_map module implements the ResponseMetadataMap for field resolution."""
from pydantic import BaseModel
from typing import Optional, Any, Mapping
from scholar_flux.utils import coerce_int, get_nested_data, PathUtils
from math import ceil


class ResponseMetadataMap(BaseModel):
    """Maps API-specific response metadata field names to common names.

    This class enables extraction of metadata from API responses, primarily used for pagination decisions in multi-page
    searches. This class extracts and processes metadata fields from metadata dictionaries and can be used for nested
    path reversal by denoting fields with periods.
    field retrieval.

    Args:
        total_query_hits:
            Field name containing the total number of results for a query (used to determine if more pages exist)
        records_per_page: Field name indicating the number of records on the current page


    Example:
        >>> from scholar_flux.api.models.response_metadata_map import ResponseMetadataMap
        >>> metadata_map = ResponseMetadataMap(total_query_hits="totalHits")
        >>> metadata = {"totalHits": 318942, "limit": 10}
        >>> total = metadata_map.calculate_query_hits(metadata)
        >>> print(total)  # 318942
        >>> # Used for pagination decisions
        >>> has_more = total > (current_page * records_per_page)

    """

    total_query_hits: Optional[str] = None
    records_per_page: Optional[str] = None

    @classmethod
    def _extract_key(cls, metadata: dict[str, Any], key: str) -> Any:
        """Helper method for reliably extracting available keys from metadata given a path."""

        if not isinstance(metadata, Mapping) or not (key and isinstance(key, str)):
            return None

        if key in metadata:
            return metadata[key]

        # recursively extracts nested data at the current path if possible
        value = get_nested_data(metadata, key, verbose=False) if PathUtils.DELIMITER in key else None

        # returns None if coercion into an integer isn't possible
        return value

    def calculate_query_hits(self, metadata: dict[str, Any]) -> Optional[int]:
        """Extract and convert total query hits from response metadata.

        Args:
            metadata: A mapping containing response metadata typically from ProcessedResponse.metadata

        Returns:
            Total number of query hits as an integer if available and convertible,
            otherwise None

        Example:
            >>> from scholar_flux.api.models.response_metadata_map import ResponseMetadataMap
            >>> metadata_map = ResponseMetadataMap(total_query_hits="totalHits")
            >>> metadata = {"totalHits": "1500", "results": [...]}
            >>> total = metadata_map.calculate_query_hits(metadata)
            >>> print(total)  # 1500 (converted from string)

        """
        key = self.total_query_hits or ""
        return coerce_int(self._extract_key(metadata, key))

    def calculate_records_per_page(self, metadata: dict[str, Any]) -> Optional[int]:
        """Extract and convert the total number of records on the current page from response metadata.

        Args:
            metadata (dict[str, Any]):
                A mapping containing response metadata (typically from ProcessedResponse.metadata)

        Returns:
            Total number of records on the current page as an integer if available and convertible,
            otherwise None

        Example:
            >>> from scholar_flux.api.models.response_metadata_map import ResponseMetadataMap
            >>> metadata_map = ResponseMetadataMap(records_per_page="pageSize")
            >>> metadata = {"pageSize": "20", "results": [...]}
            >>> total = metadata_map.calculate_records_per_page(metadata)
            >>> print(total)  # 20 (converted from string)

        """
        key = self.records_per_page or ""
        return coerce_int(self._extract_key(metadata, key))

    def process_metadata(self, metadata: dict[str, Any]) -> dict[str, Any]:
        """Helper method for processing metadata after mapping relevant fields using the metadata schema.

        Args:
            metadata (dict[str, Any]):
                A mapping containing response metadata (typically from ProcessedResponse.metadata)

        Returns:
            metadata (dict[str, Any]):
                A mapped dictionary of processed metadata fields.

        Example:
            >>> from scholar_flux.api.models.response_metadata_map import ResponseMetadataMap
            >>> metadata_map = ResponseMetadataMap(total_query_hits="totalHits", records_per_page="pageSize")
            >>> metadata = {"totalHits": "1500","pageSize": "20", "results": [...]}
            >>> metadata_map.process_metadata(metadata)
            # OUTPUT: {"total_query_hits": 1500, "pageSize": "records_per_page", 20}

        """
        return {
            "total_query_hits": self.calculate_query_hits(metadata),
            "records_per_page": self.calculate_records_per_page(metadata),
        }

    def calculate_pages_remaining(
        self,
        page: int,
        total_query_hits: Optional[int] = None,
        records_per_page: Optional[int] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Optional[int]:
        """Calculating the total number of pages yet to be queried using either metadata or direct integer fields.

        Args:
            total_query_hits (Optional[int]):
                Total number of record hits associated with a given query. If not specified, this is parsed
                from the metadata
            records_per_page (Optional[int]):
                Total number of records on the current page as an integer if available and convertible

        Returns:
            Optional[int]:
                The total number of pages that remain given the values `total_query_hits` and `records_per_page`

        Example:
            >>> from scholar_flux.api.models.response_metadata_map import ResponseMetadataMap
            >>> metadata_map = ResponseMetadataMap(
            ... total_query_hits="statistics.totalHits", records_per_page="metadata.pageSize"
            ... )
            >>> metadata = {"statistics": {"totalHits": "1500"},"metadata": {"pageSize": "20"}}
            >>> total = metadata_map.calculate_pages_remaining(page = 74, metadata = metadata)
            >>> print(total) # 1 (converted from string)

        """
        records_per_page = records_per_page if records_per_page else self.calculate_records_per_page(metadata or {})
        total_query_hits = total_query_hits if total_query_hits else self.calculate_query_hits(metadata or {})

        if total_query_hits is None or records_per_page is None or page is None:
            return None

        return self._calculate_pages_remaining(
            page, total_query_hits=total_query_hits, records_per_page=records_per_page
        )

    @classmethod
    def _calculate_pages_remaining(cls, page: int, total_query_hits: int, records_per_page: int):
        """Calculates the total number of pages that remain given the total number of hits and records per page.

        Args:
            total_query_hits (int):
                Total number of record hits associated with a given query
            records_per_page (int):
                Total number of records on the current page as an integer

        Returns:
            int: The total number of pages that remain given the values `total_query_hits` and `records_per_page`

        """

        calculated_page_max = ceil(total_query_hits / records_per_page)

        # accounts for variability in Core API record retrieval count
        under_record_limit = calculated_page_max - page
        return max(0, under_record_limit)

    def __call__(self, *args, **kwargs) -> Optional[dict[str, Any]]:
        """Helper method that enables the current map to be used as a callable to map and process response metadata.

        The call delegates metadata processing to the `process_metadata` method which will return a list if it receives
        a list and returns a dictionary if a single record is received, otherwise.

        """
        return self.process_metadata(*args, **kwargs)


__all__ = ["ResponseMetadataMap"]
