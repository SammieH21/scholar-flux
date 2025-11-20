# scholar_flux.api.normalization.open_alex_field_map.py
"""The scholar_flux.api.normalization.open_alex_field_map.py module defines the normalization mappings for OpenAlex."""
from scholar_flux.api.normalization.academic_field_map import AcademicFieldMap


field_map = AcademicFieldMap(
    provider_name="openalex",
    doi="doi",
    url="primary_location.landing_page_url",
    record_id="id",
    title="title",
    abstract=None,
    authors="authorships.author.display_name",
    # Publication metadata
    journal="primary_location.source.display_name",
    publisher="primary_location.source.host_organization_name",
    year="publication_year",
    date_published="publication_date",
    date_created="created_date",
    # Content
    keywords="keywords.display_name",
    subjects="topics.display_name",  # / 'concepts.display_name'
    full_text=None,
    # Metrics
    citation_count="cited_by_count",
    # Access Permissions
    open_access="open_access.is_oa",
    license="primary_location.license",
    # Metadata
    record_type="type",
    language="language",
    # Potentially useful fields
    api_specific_fields={
        "oa_status": "open_access.oa_status",
        "cited_by_api_url": "cited_by_api_url",
        "references_count": "referenced_works_count",
        "affiliations": "authorships.institutions.display_name",
        "fields": "topics.field.display_name",
        "sdgs": "sustainable_development_goals.display_name",
    },
)

__all__ = ["field_map"]
