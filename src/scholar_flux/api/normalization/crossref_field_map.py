# scholar_flux.api.normalization.crossref_field_map.py
"""The scholar_flux.api.normalization.crossref_field_map.py module defines the normalization mappings for Crossref."""
from scholar_flux.api.normalization.academic_field_map import AcademicFieldMap
from scholar_flux.utils.helpers import (
    build_iso_date,
    coerce_int,
    as_tuple,
    unlist_1d,
    coerce_flattened_str,
    infer_text_pattern_search,
)
from scholar_flux.utils.record_types import NormalizedRecordType
from typing import Optional
import re

# Direct mapping: pattern -> Optional[bool]
LICENSE_PATTERNS: dict[str, Optional[bool]] = {
    # === BOAI-Compliant (True) ===
    # CC0 - Public domain dedication, no restrictions
    "creativecommons.org/publicdomain/zero": True,
    "creativecommons.org/licenses/cc0": True,
    # CC-BY - Attribution only, BOAI recommended license
    # Note: Must check SA variant first to avoid false match
    "creativecommons.org/licenses/by-sa/": True,  # ShareAlike (copyleft, still BOAI)
    "creativecommons.org/licenses/by/": True,
    # === Debatable (None) - Restrictions violate BOAI "any lawful purpose" ===
    # Order: most restrictive first for accurate substring matching
    "creativecommons.org/licenses/by-nc-nd/": None,  # NonCommercial + NoDerivatives
    "creativecommons.org/licenses/by-nc-sa/": None,  # NonCommercial + ShareAlike
    "creativecommons.org/licenses/by-nc/": None,  # NonCommercial
    "creativecommons.org/licenses/by-nd/": None,  # NoDerivatives
    # === Restricted (False) - Subscription/publisher-controlled ===
    # TDM (Text and Data Mining) licenses - require institutional subscription
    "tdm_license": False,  # Wiley: doi.wiley.com/10.1002/tdm_license_1.1
    "tdm/userlicense": False,  # Elsevier: elsevier.com/tdm/userlicense/1.0/
    "/tdm": False,  # Generic TDM path: springer.com/tdm
    "text-and-data-mining": False,  # SpringerNature verbose URL
    # Publisher terms pages - not licenses, indicate restricted access
    "termsandconditions": False,  # Wiley: onlinelibrary.wiley.com/termsAndConditions
    "/core/terms": False,  # Cambridge: cambridge.org/core/terms
}


class CrossrefFieldMap(AcademicFieldMap):
    """Crossref specific field mapping with custom transformations.

    Post-Processed Fields:
        - DOI, URL, and record identifiers
        - Year and date extraction from nested date fields
        - Author name formatting
        - Open access status resolution from license URLs
        - Journal extraction
        - Abstract retrieval and HTML tag removal
        - Retraction status detection


    Note:
        Crossref records may contain nested lists and multiple date fields.
        The field map configuration and post-processing logic handle these variations and normalizes the output.

    """

    def _post_process(self, record: NormalizedRecordType) -> NormalizedRecordType:
        """Applies Crossref-specific transformations to an individual normalized record.

        Args:
            record (NormalizedRecordType): The Normalized Crossref record dictionary to further process.

        Returns:
            NormalizedRecordType: The normalized, post-processed Crossref record with transformations applied.

        """
        record = super()._post_process(record)
        record["authors"] = self.extract_authors(record)
        record["date_created"] = self.extract_date_parts(record, field="date_created")
        record["date_published"] = self.extract_date_parts(record)
        record["year"] = self.extract_year(record)
        record["open_access"] = self.resolve_open_access(record)
        record["journal"] = self.extract_journal(record)
        record["title"] = self.extract_title(record)
        record["abstract"] = self.extract_abstract(record, strip_html=True, separator=" ", strip=True)
        record["is_retracted"] = self.check_retraction(record)
        return record

    @classmethod
    def extract_title(cls, record: NormalizedRecordType, field: str = "title") -> Optional[str]:
        """Extracts the record title or a nested list indicating the title (or titles for the article) as a string.

        Args:
            record (NormalizedRecordType): Normalized Crossref record dictionary.
            field (str): The field to extract the title from.

        Returns:
            Optional[str]: The title or delimited set of titles associated with the record, joined by a semicolon.

        """
        return coerce_flattened_str(record.get(field))

    @classmethod
    def extract_year(cls, record: NormalizedRecordType, field: str = "year") -> Optional[int]:
        """Extracts the year of publication or creation.

        Args:
            record (NormalizedRecordType): Normalized Crossref record dictionary.
            field (str): The field name to extract the year from.

        Returns:
            Optional[int]: The year of record publication or creation extracted as an integer.

        """
        date_parts = as_tuple(unlist_1d(record.get(field)))
        return coerce_int(date_parts[0]) if date_parts else None

    @classmethod
    def extract_date_parts(cls, record: NormalizedRecordType, field: str = "date_published") -> Optional[str]:
        """Extracts the publication date or `date_created` for the current record.

        Args:
            record (NormalizedRecordType): Normalized Crossref record dictionary.
            field (str): The field to extract a Crossref date field from.

        Returns:
            Optional[str]: ISO formatted date string (YYYY-MM-DD) or None.

        Note: This class method is designed to handle Crossref's unique processing structure to consistently
        convert date fields in `[[Year, Month, Date]]` format to `%Y-%m-%d` format.

        """
        date_published = as_tuple(unlist_1d(record.get(field)))
        return build_iso_date(*date_published) if date_published else None

    @classmethod
    def extract_authors(cls, record: NormalizedRecordType, field: str = "author_list") -> Optional[list[str]]:
        """Extracts formatted author names by combining GivenName and LastName.

        Args:
            record (NormalizedRecordType): Normalized Crossref record dictionary.
            field (str): The field to extract the nested list of authors from.

        Returns:
            Optional[list[str]]: List of author names in 'ForeName LastName' format, or None if no authors.

        Note:
            Returns None for organizational records (datasets, reports) where Crossref does not provide
            individual authors. Check the 'publisher' or 'institution' fields for organizational attribution.

        """
        authors = as_tuple(record.get(field))

        formatted_authors = [
            f"{author['given']} {author['family']}" if author.get("given") else f"{author['family']}"
            for author in authors
            if isinstance(author, dict) and author.get("family")
        ]

        return formatted_authors if formatted_authors else None

    @classmethod
    def resolve_open_access(cls, record: NormalizedRecordType, field: str = "license") -> Optional[bool]:
        """Resolves the Open Access Status from known license URLs.

        Args:
            record (NormalizedRecordType): Normalized Crossref record dictionary.
            field (str): The field to extract license URLs from.

        Returns:
            Optional[bool]: True if open access, False if restricted, None if indeterminate.

        """
        open_access_statuses = {
            infer_text_pattern_search(url, LICENSE_PATTERNS, default=None, regex=False, flags=re.IGNORECASE)
            for url in as_tuple(record.get(field))
            if isinstance(url, str)
        }

        if True in open_access_statuses:
            return True
        if open_access_statuses == {False}:
            return False
        return None

    @staticmethod
    def check_retraction(record: NormalizedRecordType, field: str = "updated_by_list") -> Optional[bool]:
        """Checks if the record is a retraction notice.

        Note:
            Crossref's `update-to` field is on the retraction NOTICE,
            pointing to the retracted paper. The retracted paper itself does
            not contain this field. To determine if a paper has been retracted,
            a separate lookup against Retraction Watch or checking the `relation`
            field would be needed.

        Args:
            record (NormalizedRecordType): Normalized Crossref record dictionary.
            field (str): The field to check for retraction updates.

        Returns:
            Optional[bool]: True if the paper has been retracted, None if the status is unknown.

        """
        # Check if this paper HAS BEEN retracted (updated-by field)
        updated_by_list = as_tuple(record.get(field))
        for update in updated_by_list:
            if (
                isinstance(update, dict)
                and isinstance(update.get("type"), str)
                and re.search(r"retract|withdraw", update["type"].lower())
            ):
                return True  # This paper HAS BEEN retracted
        return None


field_map = CrossrefFieldMap(
    provider_name="crossref",
    # Identifiers
    doi="DOI",
    url="URL",
    record_id="DOI",
    # Bibliographic
    title="title",
    abstract="abstract",
    authors="author",
    # Publication metadata
    journal="container-title",  # Array
    publisher="publisher",
    year=[
        "created.date-parts",
        "published.date-parts",
        "published-print.date-parts",
        "published-online.date-parts",
        "indexed.date-parts",
    ],  # Nested: [[year, month, day]]
    date_published=["published.date-parts", "published-print.date-parts", "indexed.date-parts"],
    date_created=[
        "created.date-parts",
        "published.date-parts",
        "published-print.date-parts",
        "published-online.date-parts",
        "indexed.date-parts",
    ],
    # Content
    keywords="subject",
    subjects="subject",  # Array of subject classifications
    full_text=None,
    # Metrics
    citation_count="is-referenced-by-count",
    # Access
    open_access=None,  # Check 'license' array for access info
    license="license.URL",  # License array
    is_retracted=None,  # Calculated using `retraction` and `update_to_list`
    # Metadata
    record_type="type",
    language="language",
    api_specific_fields={
        "author_list": "author",
        "institution": "institution.name",
        "license_list": "license",
        "update_to_list": "update-to",
        "updated_by_list": "updated-by",
        "issn": "ISSN",
        "isbn": "ISBN",
        "volume": "volume",
        "issue": "issue",
        "page": "page",
        "references_count": "reference-count",
        "funder": "funder.name",
    },
)

__all__ = ["CrossrefFieldMap", "field_map"]
