# scholar_flux.api.normalization.springer_nature_field_map.py
"""scholar_flux.api.normalization.springer_nature_field_map.py defines the normalization steps for SpringerNature."""
from scholar_flux.api.normalization.academic_field_map import AcademicFieldMap
from scholar_flux.api.validators import validate_bool_str
from scholar_flux.utils.record_types import NormalizedRecordType


class SpringerNatureFieldMap(AcademicFieldMap):
    """Springer Nature specific field mapping with custom transformations.

    The `SpringerNatureFieldMap` defines a minimal set of Springer Nature specific post-processing steps that aid in the
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
        record["open_access"] = (
            validate_bool_str(record["open_access"]) if isinstance(record.get("open_access"), str) else None
        )

        # Extracts the article/record creation date when available
        record["date_created"] = self.extract_iso_date(record, "date_created")

        # Extracts the article/record publication date when available
        record["date_published"] = self.extract_iso_date(record, "date_published")

        # SpringerNature-specific URL extraction for the first valid URL in a nested array of URLs
        record["url"] = (
            self.extract_url(
                record,
                ["url"],
                ["url", 0],
                ["url", "value"],
                ["url", 0, "value"],
                pattern_delimiter=self._processor.value_delimiter or "; *",
            )
            or None
        )

        return record


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
