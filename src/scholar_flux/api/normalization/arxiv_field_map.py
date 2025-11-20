# scholar_flux.api.normalization.arxiv_field_map.py
"""The scholar_flux.api.normalization.arxiv_field_map.py module defines the normalization mappings used for Arxiv."""
from scholar_flux.api.normalization.academic_field_map import AcademicFieldMap


field_map = AcademicFieldMap(
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
    record_type=None,  # Always preprint
    language=None,
    api_specific_fields={
        "primary_category": "arxiv:primary_category.@term",
        "updated_date": "updated",
        "pdf_url": "link.@href",  # TEST: Filter for PDF link
    },
)

__all__ = ["field_map"]
