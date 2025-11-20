# scholar_flux.api.normalization.core_field_map.py
"""The scholar_flux.api.normalization.core_field_map.py module defines the normalization mappings used for Core API."""
from scholar_flux.api.normalization.academic_field_map import AcademicFieldMap


field_map = AcademicFieldMap(
    provider_name="core",
    # Identifiers
    doi="doi",
    url="downloadUrl",  # Direct PDF/full text link
    record_id="id",
    # Bibliographic
    title="title",
    abstract="abstract",
    authors="authors.name",
    # Publication metadata
    journal="journals",
    publisher="publisher",
    year="yearPublished",
    date_published="publishedDate",
    date_created="createdDate",
    # Content
    keywords="subjects",  # Array of subject strings
    subjects="subjects",  # Same as keywords for Core
    full_text="fullText",  # full text is nearly always available
    # Metrics
    citation_count="citationCount",
    # Access
    open_access=None,  # Core Sources are generally all open access, but no explicit field
    license=None,  # Not provided
    # Metadata
    record_type="documentType",
    language="language.name",
    default_field_values={"open_access": True},
)

__all__ = ["field_map"]
