# scholar_flux.api.normalization.open_alex_field_map.py
"""The scholar_flux.api.normalization.open_alex_field_map.py module defines the normalization mappings for OpenAlex."""

from scholar_flux.api.normalization.academic_field_map import AcademicFieldMap
from scholar_flux.utils.helpers import get_nested_data
from scholar_flux.utils.record_types import NormalizedRecordType
import re


class OpenAlexFieldMap(AcademicFieldMap):
    """OpenAlex specific field mapping with custom transformations.

    The `OpenAlexFieldMap` implements a minimal set of methods for field extraction and abstract reconstruction,
    finalizing the structure of each normalized record in the post-processing step.

    Post-Processed Fields:
        - Abstract reconstruction from inverted index format
        - DOI normalization (stripping URL prefix)
        - PMID extraction from ids object
        - Author list cleanup (filter empty entries)

    """

    def _post_process(self, record: NormalizedRecordType) -> NormalizedRecordType:
        """Applies OpenAlex-specific transformations to an individual OpenAlex record.

        Args:
            record (NormalizedRecordType): The Normalized OpenAlex record dictionary to further process.

        Returns:
            NormalizedRecordType: The normalized, post-processed OpenAlex record with transformations applied.

        """
        record = super()._post_process(record)

        # Reconstruct abstract from inverted index
        record["abstract"] = self.reconstruct_abstract(record)

        # Normalize DOI (strip https://doi.org/ prefix)
        record["doi"] = self.normalize_doi(record)

        # Clean author list (filter empty/None entries)
        record["authors"] = self.extract_authors(record)

        # Coerces year into an integer and returns None otherwise
        record["year"] = self.extract_year(record)

        # Indicates whether the current paper is open access (available to the public online)
        record["open_access"] = self.extract_open_access(record)

        # Extracts the `url` field when validated (the default). Tries to fallback and validate record_id
        record["url"] = self.extract_url(record, "url", "record_id")

        return record

    @classmethod
    def reconstruct_abstract(cls, record: NormalizedRecordType, field: str = "abstract_inverted_index") -> str | None:
        """Reconstructs abstract text from OpenAlex inverted index format.

        OpenAlex stores abstracts as inverted indexes where keys are words
        and values are arrays of positions where those words appear.

        Args:
            record (NormalizedRecordType): Normalized OpenAlex record dictionary.
            field (str): The field containing the inverted index.

        Returns:
            Optional[str]: Reconstructed abstract string, or None if not available.

        Examples:
            >>> record = {'abstract_inverted_index': {'Hello': [0], 'world': [1]}}
            >>> OpenAlexFieldMap.reconstruct_abstract(record)
            'Hello world'

        """
        inverted_index = record.get(field)
        if not isinstance(inverted_index, dict) or not inverted_index:
            return None

        # Build position -> word mapping
        position_word_pairs: list[tuple[int, str]] = []
        for word, positions in inverted_index.items():
            if isinstance(positions, list):
                for pos in positions:
                    if isinstance(pos, int):
                        if re.search(r"[a-zA-Z0-9]", word) and pos != 0 and not word.startswith(" "):
                            word = " " + word
                        position_word_pairs.append((pos, str(word)))

        if not position_word_pairs:
            return None

        # Sort by position and join words
        position_word_pairs.sort(key=lambda x: x[0])

        # Ensure that punctuation and special characters are not preceded by a space
        return "".join(word for _, word in position_word_pairs) if position_word_pairs else None

    @classmethod
    def extract_pmid(cls, record: NormalizedRecordType, field: str = "pmid") -> str | None:
        """Extracts PubMed ID from the ids object.

        Args:
            record (NormalizedRecordType): Normalized OpenAlex record dictionary.
            field (str): The field to extract the PMID from.

        Returns:
            Optional[str]: PMID string without URL prefix, or None if not found.

        Examples:
            >>> record = {'pmid': 'https://pubmed.ncbi.nlm.nih.gov/29241234'}
            >>> OpenAlexFieldMap.extract_pmid(record)
            '29241234'

        """
        pmid_url = record.get(field) or get_nested_data(record, "ids.pmid", verbose=False)
        return (
            (pmid_url.strip().removeprefix("https://pubmed.ncbi.nlm.nih.gov/").strip("/") or None)
            if isinstance(pmid_url, str)
            else None
        )

    @classmethod
    def extract_open_access(cls, record: NormalizedRecordType, field: str = "open_access") -> bool | None:
        """Extracts the open access status from the OpenAlex record as a boolean field.

        The value returned can be `True` or `False`, indicating whether the full text of the record is freely accessible
        to the public, or `None` if the field is missing or status cannot be determined from the field.

        Args:
            record (NormalizedRecordType): The Normalized OpenAlex record dictionary.
            field (str): The field to extract the open access status from.

        Returns:
            Optional[bool]:
                - True if the record is open access (e.g., arXiv, CORE, PubMed Central, CC-BY license).
                - False if the record is not open access (e.g., subscription, restricted, or fee-based access).
                - None if the status cannot be determined from the available metadata.

        Note:
            How OpenAlex determines open access status is explained here:
                https://help.openalex.org/hc/en-us/articles/24347035046295-Open-Access-OA

        """
        return cls.extract_boolean_field(
            record,
            field,
            true_values=("diamond", "gold", "green", "hybrid", "bronze", "true"),
            false_values=("closed", "false"),
            default=None,
        )


field_map = OpenAlexFieldMap(
    provider_name="openalex",
    # Core identifiers
    doi="doi",
    url="primary_location.landing_page_url",
    record_id="id",
    # Bibliographic metadata
    title="title",
    abstract=None,  # Reconstructed from abstract_inverted_index in _post_process
    authors="authorships.author.display_name",
    # Publication metadata
    journal="primary_location.source.display_name",
    publisher="primary_location.source.host_organization_name",
    year="publication_year",
    date_published="publication_date",
    date_created="created_date",
    # Content and classification
    keywords="keywords.display_name",
    subjects=["topics.display_name", "concepts.display_name"],
    full_text=None,
    # Metrics and impact
    citation_count="cited_by_count",
    # Access Permissions
    open_access=["open_access.is_oa", "open_access.oa_status"],
    license="primary_location.license",
    # Document metadata
    record_type="type",
    language="language",
    is_retracted="is_retracted",
    # API-specific fields (extensible for downstream use)
    api_specific_fields={
        # Required for abstract reconstruction
        "abstract_inverted_index": "abstract_inverted_index",
        # Additional identifiers
        "openalex_id": "ids.openalex",
        "pmid": "ids.pmid",
        "mag_id": "ids.mag",
        # Open Access details
        "oa_status": "open_access.oa_status",
        # Bibliographic details
        "volume": "biblio.volume",
        "issue": "biblio.issue",
        "first_page": "biblio.first_page",
        "last_page": "biblio.last_page",
        # Journal identifiers
        "issn": "primary_location.source.issn",
        "issn_l": "primary_location.source.issn_l",
        # Author affiliations
        "affiliations": "authorships.institutions.display_name",
        # Citation data
        "references_count": "referenced_works_count",
        "fwci": "fwci",
        # Retraction status
    },
)

__all__ = ["OpenAlexFieldMap", "field_map"]
