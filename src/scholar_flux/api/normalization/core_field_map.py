# scholar_flux.api.normalization.core_field_map.py
"""The scholar_flux.api.normalization.core_field_map.py module defines the normalization mappings used for Core API."""
from scholar_flux.api.normalization.academic_field_map import AcademicFieldMap
from scholar_flux.utils.helpers import as_tuple, try_none
from scholar_flux.utils.record_types import NormalizedRecordType
from typing import Optional


class CoreFieldMap(AcademicFieldMap):
    """Core specific field mappings with custom transformations.

    The Core API provides open access scholarly content aggregated from thousands of repositories worldwide.

    The `CoreFieldMap` implements several methods for record normalization and the extraction of record fields and cross
    platform IDs. The post-processing step finalizes the structure of each normalized record to consistently prepare and
    post-process records retrieved from the CORE API.

    Post-Processed Fields:
        - Year extraction from various date formats
        - Journal list flattening (Core can return multiple journal titles)
        - Record ID coercion to string format
        - Open access default (Core sources are generally all open access)
        - Cross-reference identifier extraction (arXiv, PubMed, MAG IDs)
        - Multi-identifier normalization for entity resolution

    """

    def _post_process(self, record: NormalizedRecordType) -> NormalizedRecordType:
        """Applies Core API-specific transformations to an individual Core record.

        Args:
            record (NormalizedRecordType): The Normalized Core API record dictionary further process.

        Returns:
            NormalizedRecordType: The normalized, post-processed Core record with transformations applied.

        """
        record = super()._post_process(record)

        # Extracts year from date strings (e.g., "2025-12-01" -> 2025)
        record["year"] = self.extract_year(record)

        # Coerces a record ID into string
        record["record_id"] = self.extract_id(record)

        # Flattens a journal list to semicolon-delimited string
        record["journal"] = self.extract_journal(record)

        # Ensures that author fields are lists when available
        record["authors"] = self.extract_authors(record)

        # Extracts and clean arXiv cross-reference identifiers
        record["arxiv_id"] = self.extract_arxiv_id(record)

        # Extracts the article/record creation date when available
        record["date_created"] = self.extract_iso_date(record, "date_created")

        # Extracts the article/record publication date when available
        record["date_published"] = self.extract_iso_date(record, "date_published")

        # Extracts pmid (PubMed record ID resolution)
        record["pmid"] = self.extract_pmid(record)

        # Microsoft Academic Graph identifier-database resolution.
        record["mag_id"] = self.extract_mag_id(record)

        # Core Articles are generally open source, although no explicit field exists
        record["open_access"] = True

        # Extracts the OAI IDs for the current record
        record["oai_ids"] = self.extract_oai_ids(record)
        return record

    @classmethod
    def extract_arxiv_id(cls, record: NormalizedRecordType) -> Optional[str]:
        """Extracts the arXiv identifier for cross-database entity resolution.

        Args:
            record (NormalizedRecordType): Normalized Core record dictionary.

        Returns:
            Optional[str]: The arXiv ID (e.g., '1012.4340') or None if not available.

        """
        return cls.extract_id(record, "arxiv_id")

    @classmethod
    def extract_pmid(cls, record: NormalizedRecordType) -> Optional[str]:
        """Extracts the PubMed identifier for cross-database entity resolution.

        Args:
            record (NormalizedRecordType): Normalized Core record dictionary

        Returns:
            Optional[str]: The PubMed ID or None if not available

        Examples:
            >>> CoreFieldMap.extract_pmid({"pmid": "12345678"})
            '12345678'
            >>> CoreFieldMap.extract_pmid({"pmid": "None"})
            None

        """
        return cls.extract_id(record, "pmid") or cls.extract_id(record, "pubmed_id")

    @classmethod
    def extract_mag_id(cls, record: NormalizedRecordType) -> Optional[str]:
        """Extracts the Microsoft Academic Graph identifier for cross-database entity resolution.

        Args:
            record (NormalizedRecordType): Normalized Core record dictionary

        Returns:
            Optional[str]: The MAG ID or None if not available

        Examples:
            >>> CoreFieldMap.extract_mag_id({"mag_id": "2056403249"})
            '2056403249'
            >>> CoreFieldMap.extract_mag_id({"mag_id": "None"})
            None

        """
        return cls.extract_id(record, "mag_id")

    @classmethod
    def extract_oai_ids(cls, record: NormalizedRecordType) -> Optional[list[str]]:
        """Extracts the OAI identifiers for cross-database entity resolution.

        Args:
            record (NormalizedRecordType): Normalized Core record dictionary

        Returns:
            Optional[list[str]]: The OAI IDs for the current record as a list or None if not available

        """
        oai_ids = record.get("oai_ids")

        # Keeps only valid IDs, returning a list of IDs when valid, an empty list if empty, and None if not found
        return [str(id) for id in as_tuple(oai_ids) if try_none(id)] if oai_ids is not None else None


field_map = CoreFieldMap(
    provider_name="core",
    # ==== Core Identifiers ====
    doi="doi",
    url="downloadUrl",  # Direct PDF/full text link
    record_id="id",
    # ==== Bibliographic ====
    title="title",
    abstract="abstract",
    authors="authors.name",
    # ==== Publication Metadata ====
    journal="journals.title",
    publisher="publisher",
    year="yearPublished",
    date_published="publishedDate",
    date_created="createdDate",
    # Content
    keywords="fieldOfStudy",
    subjects="fieldOfStudy",
    full_text="fullText",
    # Metrics
    citation_count="citationCount",
    # Access
    open_access=None,  # Core sources are generally all open access
    license=None,  # Not provided by Core API
    # Metadata
    record_type="documentType",
    language="language.name",
    default_field_values={"open_access": True},
    api_specific_fields={
        # Cross-reference identifiers for entity resolution
        "arxiv_id": "arxivId",
        "pmid": "pubmedId",
        "mag_id": "magId",
        # OAI identifiers for cross-repository deduplication
        "oai_ids": "oaiIds",
        # Reference/citation data for graph construction
        "references": "references",
    },
)

__all__ = ["CoreFieldMap", "field_map"]
