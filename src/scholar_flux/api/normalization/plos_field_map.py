# scholar_flux.api.normalization.plos_field_map.py
"""The scholar_flux.api.normalization.plos_field_map.py module defines the normalization mappings for the PLOS API."""
from scholar_flux.api.normalization.academic_field_map import AcademicFieldMap
from scholar_flux.utils.record_types import NormalizedRecordType


class PLOSFieldMap(AcademicFieldMap):
    """PLOS specific field mapping with custom transformations.

    The `PLOSFieldMap` defines a minimal set of PLOS-specific post-processing steps to further process dictionary
    records after normalization.

    Post-Processed Fields:
        - DOI and record identifiers
        - Year extraction from publication date
        - URL reconstruction from DOI
        - Author and abstract normalization
        - Open access and license status

    Note:
        The PLOS API provides most fields directly, but some (such as URLs) are reconstructed from the DOI.
        The field map configuration handles fallback paths and default values for publisher and open access status.

    """

    def _post_process(self, record: NormalizedRecordType) -> NormalizedRecordType:
        """Applies PLOS-specific transformations to an individual PLOS record.

        Args:
            record (NormalizedRecordType): The Normalized PLOS record dictionary to further process.

        Returns:
            NormalizedRecordType: The normalized, post-processed PLOS record with transformations applied.

        """
        record = super()._post_process(record)

        # Extract year from date strings (e.g., "2026-03-01" -> "2026")
        record["year"] = self.extract_year(record)

        # Extracting date fields. For now, they each refer to the same API-specific field:
        record["date_published"] = self.extract_iso_date(record, "date_published")

        record["date_created"] = self.extract_iso_date(record, "date_created")

        # Reconstructing the URL for PLOS from the DOI
        record["url"] = self.reconstruct_plos_url(record)

        #  Some abstracts in `list[str]` format need to be converted to `str` for consistency
        record["abstract"] = self.extract_abstract(record)

        # Extracting author fields as a list
        record["authors"] = self.extract_authors(record)

        return record

    @classmethod
    def reconstruct_plos_url(cls, record: NormalizedRecordType, field: str = "doi") -> str | None:
        """Reconstructs the PLOS article URL from the DOI of the article.

        Args:
            record (NormalizedRecordType): The Normalized record dictionary containing the DOI used to reconstruct the URL.
            field (str): The field to extract the DOI from.

        Returns:
            Optional[str]: Reconstructed URL if DOI is valid, None otherwise.

        Examples:
            >>> from scholar_flux.api.normalization.plos_field_map import PLOSFieldMap
            >>> PLOSFieldMap.reconstruct_plos_url({'doi':"10.1371/journal.pone.0123456"})
            # OUTPUT: 'https://journals.plos.org/plosone/article?id=10.1371/journal.pone.0123456'
            >>> PLOSFieldMap.reconstruct_plos_url({})
            # OUTPUT: None

        """
        # Extract primary URL if multiple exist
        doi = record.get(field)
        return cls.reconstruct_url(doi, url="https://journals.plos.org/plosone/article?id=")


field_map = PLOSFieldMap(
    provider_name="plos",
    # Identifiers
    doi="id",  # PLOS ID is the DOI
    url=None,  # Can construct from DOI if needed
    record_id="id",
    # Bibliographic
    title="title_display",
    abstract="abstract",  # Array with single element usually
    authors="author_display",  # Array of author name strings
    # Publication metadata
    journal="journal",
    publisher=None,  # Always "Public Library of Science"
    year="publication_date",  # Extract year from date string
    date_published="publication_date",
    date_created="publication_date",
    # Content
    keywords="subject",  # Array of subject terms
    subjects="article_type",
    full_text=None,  # Requires separate API call
    # Metrics
    citation_count=None,  # Not provided by PLOS API
    # Access
    open_access=None,  # Always true, but no explicit field
    license=None,  # TEST: Check if 'license' field exists
    # Metadata
    record_type="article_type",
    language=None,
    api_specific_fields={
        "issn": "eissn",  # Electronic ISSN
        "page": "page_number",  # Page number if available
        "score": "score",  # Solr relevance score
        "volume": "volume",
        "issue": "issue",
        "page_range": "elocation_id",
        "cross_published_journal": "cross_published_journal_name",
        "reference": "reference",
    },
    default_field_values={"publisher": "Public Library of Science", "open_access": True},
)

__all__ = ["PLOSFieldMap", "field_map"]
