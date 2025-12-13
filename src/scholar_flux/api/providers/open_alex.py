# /api/providers/open_alex.py
"""Defines the core configuration necessary to interact with the OpenAlex API using the scholar_flux package."""
from functools import partial
from scholar_flux.api.models.provider_config import ProviderConfig
from scholar_flux.api.models.base_parameters import BaseAPIParameterMap, APISpecificParameter
from scholar_flux.api.models.response_metadata_map import ResponseMetadataMap
from scholar_flux.api.normalization.open_alex_field_map import field_map
from scholar_flux.api.validators import validate_and_process_email, validate_api_specific_field, validate_str

name = "openalex"
validate_openalex_field = partial(validate_api_specific_field, provider_name=name)

provider = ProviderConfig(
    parameter_map=BaseAPIParameterMap(
        query="search",
        start="page",
        records_per_page="per_page",
        api_key_parameter="api_key",
        api_key_required=False,
        auto_calculate_page=False,
        zero_indexed_pagination=False,
        api_specific_parameters=dict(
            sort=APISpecificParameter(
                name="sort",
                description=(
                    "Field to sort results by with optional direction. Examples: 'cited_by_count:desc', "
                    "'publication_year:asc', 'relevance_score'. Sortable fields: display_name, cited_by_count, "
                    "works_count, publication_year, relevance_score, publication_date"
                ),
                validator=validate_openalex_field(validate_str, field="sort"),
                default=None,
                required=False,
            ),
            filter=APISpecificParameter(
                name="filter",
                description=(
                    "Filter results using attribute:value syntax. Multiple filters separated by commas (AND logic). "
                    "Examples: 'publication_year:2023', 'is_oa:true', 'has_fulltext:true', 'type:article'. See "
                    "OpenAlex docs for complete filter list."
                ),
                validator=validate_openalex_field(validate_str, field="filter"),
                default=None,
                required=False,
            ),
            mailto=APISpecificParameter(
                name="mailto",
                description=(
                    "Email address for the 'polite pool' - increases rate limit to 10 req/sec (2025). Strongly "
                    "recommended for production use."
                ),
                validator=validate_openalex_field(validate_and_process_email, field="mailto"),
                default=None,
                required=False,
            ),
        ),
    ),
    metadata_map=ResponseMetadataMap(total_query_hits="count", records_per_page="per_page"),
    field_map=field_map,
    provider_name=name,
    base_url="https://api.openalex.org/works",
    api_key_env_var="OPEN_ALEX_API_KEY",
    request_delay=1,
    records_per_page=25,
    docs_url="https://docs.openalex.org/api-entities/works/get-lists-of-works",
)

__all__ = ["provider"]
