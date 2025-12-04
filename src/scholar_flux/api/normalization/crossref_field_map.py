# scholar_flux.api.normalization.crossref_field_map.py
"""The scholar_flux.api.normalization.crossref_field_map.py module defines the normalization mappings used for
Crossref."""
from scholar_flux.api.normalization.academic_field_map import AcademicFieldMap


field_map = AcademicFieldMap(
    provider_name="crossref",
    # Identifiers
    doi="DOI",
    url="URL",
    record_id="DOI",
    # Bibliographic
    title="title",
    abstract="abstract",
    authors="author.name",
    # Publication metadata
    journal="container-title",  # Array
    publisher="publisher",
    year="published.date-parts",  # Nested: [[year, month, day]]
    date_published="published.date-parts",
    date_created="created.date-time",
    # Content
    keywords="subject",
    subjects="subject",  # Array of subject classifications
    full_text=None,
    # Metrics
    citation_count="is-referenced-by-count",
    # Access
    open_access=None,  # Check 'license' array for access info
    license="license.URL",  # License array
    # Metadata
    record_type="type",
    language="language",
    api_specific_fields={
        "issn": "ISSN",
        "isbn": "ISBN",
        "volume": "volume",
        "issue": "issue",
        "page": "page",
        "references_count": "reference-count",
        "funder": "funder.name",
    },
)

__all__ = ["field_map"]
