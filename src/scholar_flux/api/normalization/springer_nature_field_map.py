# scholar_flux.api.normalization.springer_nature_field_map.py
"""scholar_flux.api.normalization.springer_nature_field_map.py defines the normalization steps for Springer Nature."""
from scholar_flux.api.normalization.academic_field_map import AcademicFieldMap, URL_PATTERN
from scholar_flux.utils.record_types import NormalizedRecordType
from typing import Optional
from re import Pattern


class SpringerNatureFieldMap(AcademicFieldMap):
    """Springer Nature specific field mapping with custom transformations.

    The `SpringerNatureFieldMap` defines a minimal set of Springer Nature-specific post-processing steps that aid in the
    normalization of preprocessed records retrieved from the Springer Nature API.

    Post-Processed Fields:
        - DOI and record identifiers
        - Year extraction from publication date
        - URL extraction from nested URL objects
        - Open access status conversion from string to boolean
        - Author and abstract normalization

    Note:
        Springer Nature records may contain arrays and nested objects for key fields (e.g., `year` and primary URL).
        The field map configuration and post-processing logic handle these for consistent normalization.

    """

    def _post_process(self, record: NormalizedRecordType) -> NormalizedRecordType:
        """Applies Springer Nature-specific transformations to an individual Springer Nature record.

        Args:
            record (NormalizedRecordType): The Normalized Springer Nature record dictionary to further process.

        Returns:
            NormalizedRecordType: The normalized, post-processed Springer Nature record with transformations applied.

        """
        record = super()._post_process(record)

        # Extract year from date strings (e.g., "2026-03-01" -> "2026")
        record["year"] = self.extract_year(record, "date_published")

        # Extract and format a list of authors from the current set of records
        record["authors"] = self.extract_authors(record)

        # Convert open_access string to boolean
        record["open_access"] = self.extract_open_access(record)

        # Extracts the article/record creation date when available
        record["date_created"] = self.extract_iso_date(record, "date_created")

        # Extracts the article/record publication date when available
        record["date_published"] = self.extract_iso_date(record, "date_published")

        # Springer Nature-specific URL extraction for the first valid URL in a nested array of URLs
        record["url"] = self.extract_primary_url(record, field="url")

        return record

    @classmethod
    def extract_primary_url(
        cls, record: NormalizedRecordType, field: str = "url", pattern_delimiter: Optional[str | Pattern] = URL_PATTERN
    ) -> Optional[str]:
        """Extracts the primary (or first valid) URL from a record field with a flat or nested JSON structure.

        Args:
            record (NormalizedRecordType): The normalized record to extract the primary URL field from
            field (str): The field to extract a primary URL from
            pattern_delimiter (Optional[str | re.Pattern]):
                An optional pattern used to separate URLs when combined as a list for primary URL extraction

        Returns:
            Optional[str]: The extracted primary URL when extraction is successful, and None otherwise.

        """
        return (
            cls.extract_url(
                record, [field], [field, 0], [field, "value"], [field, 0, "value"], pattern_delimiter=pattern_delimiter
            )
            or None
        )

    @classmethod
    def extract_open_access(cls, record: NormalizedRecordType, field: str = "open_access") -> Optional[bool]:
        """Extracts the current record's open access status by delegating processing to `.extract_boolean_field()`.

        Args:
            record (NormalizedRecordType): The normalized record to extract the open_access status for
            field (str): The field to extract the open access status from.

        Returns:
            (Optional[bool]): The open access status of the record when available, and None otherwise.

        Examples:
            >>> from scholar_flux.api.normalization import SpringerNatureFieldMap
            >>> record = {"doi": "10.1234/example", "title": "Sample Article","open_access": "true"}
            >>> SpringerNatureFieldMap.extract_open_access(record)
            # OUTPUT: True
            >>> record = {"doi": "10.5678/example", "title": "Sample Publication","open_access": "false"}
            >>> SpringerNatureFieldMap.extract_open_access(record)
            # OUTPUT: False
            >>> record = {"title": "Another Article","open_access": "N/A"}
            >>> SpringerNatureFieldMap.extract_open_access(record)
            # OUTPUT: None

        """
        return cls.extract_boolean_field(record, field)


field_map = SpringerNatureFieldMap(
    provider_name="springernature",
    # Identifiers
    doi="doi",
    url="url",  # Array of URL objects
    record_id="identifier",
    # Bibliographic
    title="title",
    abstract="abstract",
    authors="creators.creator",  # Auto-traverses list of creator names
    # Publication metadata
    journal="publicationName",
    publisher="publisher",
    year="publicationDate",  # Extract year from date string
    date_published="publicationDate",
    date_created="onlineDate",
    # Content
    keywords="keyword",
    subjects="subjects",
    full_text=None,  # Not provided in metadata API
    # Metrics
    citation_count=None,  # Not in metadata API
    # Access
    open_access="openaccess",  # Boolean field
    license="copyright",  # Or openaccess field
    # Metadata
    record_type="contentType",  # Article, Chapter, Book, etc.
    language="language",
    # API-specific fields
    api_specific_fields={
        "isbn": "isbn",
        "issn": "issn",
        "eisbn": "eisbn",
        "eissn": "eIssn",
        "journal_id": "journalId",
        "volume": "volume",
        "issue": "number",  # Issue number
        "start_page": "startingPage",
        "end_page": "endingPage",
        "article_type": "genre",
        "url_list": "url",
    },
)


__all__ = ["SpringerNatureFieldMap", "field_map"]
