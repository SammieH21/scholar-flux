# scholar_flux.api.normalization.arxiv_field_map.py
"""The scholar_flux.api.normalization.arxiv_field_map.py module defines the normalization mappings used for Arxiv."""

from scholar_flux.api.normalization.academic_field_map import AcademicFieldMap
from scholar_flux.utils.helpers import as_tuple, try_none, infer_text_pattern_search
from scholar_flux.api.validators import validate_url
from scholar_flux.utils.record_types import NormalizedRecordType
from typing import Optional
import re

RECORD_TYPE_PATTERNS: dict[re.Pattern[str], str] = {
    # Book chapters (these are the most specific)
    re.compile(r"\bIn .+\(Eds?\.\)|\(eds?\.\)|chapter:|book chapter", re.IGNORECASE): "book-chapter",
    # Conference/proceedings
    re.compile(
        r"proceedings? of\b|workshop|conference paper|accepted at.* (conference|[a-z]+ *[1-2][0-9]{3})", re.IGNORECASE
    ): "proceedings-article",
    # arXiv-specific statuses
    re.compile(r"accepted (by|for publication|in)\b|to appear in\b", re.IGNORECASE): "accepted",
    re.compile(r"submitted to\b|(under|to be) review|has been submitted", re.IGNORECASE): "submitted",
    # Journal (literal word in title)
    re.compile(r"published in\b|in press at|open access published|\bjournal\b", re.IGNORECASE): "journal-article",
}


class ArXivFieldMap(AcademicFieldMap):
    """arXiv specific field mapping with custom transformations.

    The `ArXivFieldMap` implements a minimal set of methods for record normalization to finalize the structure of each
    extracted and normalized record during postprocessing.

    Post-Processed Fields:
        - arXiv, DOI, and record identifiers
        - Year extraction from ISO date strings
        - PDF URL extraction from link arrays
        - Open access status (always true for arXiv)
        - Subject and category normalization

    Note:
        arXiv records use unique identifier and link structures.
        The field map configuration and post-processing logic handle these for consistent output.

    """

    def _post_process(self, record: NormalizedRecordType) -> NormalizedRecordType:
        """Applies arXiv-specific transformations to an individual arXiv record.

        Args:
            record (NormalizedRecordType): The Normalized arXiv API record dictionary to further process.

        Returns:
            NormalizedRecordType: The normalized, post-processed arXiv record with transformations applied.

        """
        record = super()._post_process(record)

        # Extracts year from date strings (e.g., "2026-03-01" -> "2026")
        record["year"] = self.extract_year(record)

        # Both date_published and date_created extract from the same field
        record["date_published"] = self.extract_iso_date(record, "date_published")

        record["date_created"] = self.extract_iso_date(record, "date_created")

        # Convert open_access string to boolean
        record["open_access"] = True

        record["record_id"] = self.extract_url_id(record, field="record_id", strip_prefix="https?://arxiv.org/abs/")

        record["pdf_url"] = self.extract_pdf_url(record)

        record["authors"] = self.extract_authors(record)

        # Uses heuristics and record types to determine record type by `journal` or `comment`
        record["record_type"] = self.extract_record_type(record)
        return record

    @staticmethod
    def extract_pdf_url(record: NormalizedRecordType, field: str = "url_list") -> Optional[str]:
        """Extracts a valid PDF URL from the array of URLs corresponding to the record.

        Args:
            record (NormalizedRecordType): A Normalized arXiv record dictionary to extract a PDF URL from.
            field (str): The field to extract the list of URLs from.

        Returns:
            Optional[str]: A validated PDF URL if available, otherwise None.

        """
        links = as_tuple(record.get(field))
        for link in links:
            if (
                isinstance(link, dict)
                and link.get("@type") == "application/pdf"
                and validate_url(link.get("@href") or "", verbose=False)
            ):
                return link.get("@href")
        return None

    @classmethod
    def extract_record_type(
        cls, record: NormalizedRecordType, journal_field: str = "journal", comment_field: str = "comment"
    ) -> str:
        """Infers a record type from the journal or comment field for an arXiv record using pattern matching.

        Record Type is inferred using predefined patterns to determine whether a record is a journal article,
        a book chapter, preprint, etc.

        The possible types are defined within `scholar_flux.api.normalization.arxiv_field_map` as a
        `RECORD_TYPE_PATTERNS` dictionary that maps patterns to record types.

        Args:
            record (NormalizedRecordType): Normalized arXiv record to infer the record type with.
            journal_field (str): The journal field used to infer record type with.
            comment_field (str): The comment field used to infer record type with if a journal field does not exist.

        Returns:
            When `journal_field` is available, the record type associated with the matched pattern is returned.
            If no patterns match, then `journal-article` is returned instead.
            When `journal_field` is not available, a record type is extracted by pattern matching against the
            `comment_field`. If no match is found, `preprint` is returned.

        """

        return (
            infer_text_pattern_search(record[journal_field], RECORD_TYPE_PATTERNS, default="journal-article")
            if try_none(record.get(journal_field))
            else infer_text_pattern_search(record.get(comment_field, ""), RECORD_TYPE_PATTERNS, default="preprint")
        )


field_map = ArXivFieldMap(
    provider_name="arxiv",
    doi="arxiv:doi",
    url="id",  # The arxiv.org/abs/...
    record_id="id",
    # Bibliographic
    title="title",
    abstract="summary",
    authors="author.name",
    # Publication metadata
    journal="arxiv:journal_ref",
    publisher=None,  # arXiv itself
    year="published",  # Extract year from ISO datetime
    date_published="published",
    date_created="published",
    # Content
    keywords=None,  # arXiv doesn't provide keywords
    subjects="arxiv:primary_category.@term",
    full_text=None,
    # Metrics
    citation_count=None,
    # Access
    open_access=None,  # Always true, no explicit field
    license="rights",
    # Metadata
    record_type=None,  # Inferred from journal/comment fields
    language=None,
    api_specific_fields={
        "primary_category": "arxiv:primary_category.@term",
        "categories": "category.@term",  # NEW: All categories (list)
        "comment": "arxiv:comment",
        "updated_date": "updated",
        "url_list": "link",
        "pdf_url": "link.@href",  # Filtered to extract the PDF link
    },
)

__all__ = ["ArXivFieldMap", "field_map"]
