# scholar_flux.api.normalization.springer_nature_field_map.py
"""scholar_flux.api.normalization.springer_nature_field_map.py defines the normalization steps for SpringerNature."""
from scholar_flux.api.normalization.academic_field_map import AcademicFieldMap


field_map = AcademicFieldMap(
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
    },
)

__all__ = ["field_map"]
