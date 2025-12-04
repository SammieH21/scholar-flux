# scholar_flux.api.normalization.plos_field_map.py
"""The scholar_flux.api.normalization.plos_field_map.py module defines the normalization mappings used for the PLoS
API."""
from scholar_flux.api.normalization.academic_field_map import AcademicFieldMap


field_map = AcademicFieldMap(
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
        # "reference": "reference",  # Uncomment if you want to extract references
    },
    default_field_values={"publisher": "Public Library of Science", "open_access": True},
)

__all__ = ["field_map"]
