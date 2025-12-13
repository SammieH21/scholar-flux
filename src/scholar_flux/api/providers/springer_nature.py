# /api/providers/springer_nature.py
"""Defines the core configuration necessary to interact with the Springer Nature API using the scholar_flux package."""
from functools import partial
from scholar_flux.api.models.provider_config import ProviderConfig
from scholar_flux.api.models.response_metadata_map import ResponseMetadataMap
from scholar_flux.api.models.base_parameters import BaseAPIParameterMap, APISpecificParameter
from scholar_flux.api.normalization.springer_nature_field_map import field_map
from scholar_flux.api.validators import (
    validate_api_specific_field,
    validate_str,
    validate_date,
)

name = "springernature"
validate_springer_field = partial(validate_api_specific_field, provider_name=name)

provider = ProviderConfig(
    parameter_map=BaseAPIParameterMap(
        query="q",
        start="s",
        records_per_page="p",
        api_key_parameter="api_key",
        api_key_required=True,
        auto_calculate_page=True,
        api_specific_parameters=dict(
            sort=APISpecificParameter(
                name="sort",
                description=(
                    "Sort field for results. Common options: 'date' (publication date), 'relevance'. "
                    "Append ':asc' or ':desc' for direction (e.g., 'date:desc' for newest first)."
                ),
                validator=validate_springer_field(validate_str, field="sort"),
                default=None,
                required=False,
            ),
            subject=APISpecificParameter(
                name="subject",
                description=(
                    "Filter by subject area. Examples: 'Chemistry', 'Computer Science', "
                    "'Medicine & Public Health', 'Physics', 'Engineering'. "
                    "Use facets to discover available subjects for your query."
                ),
                validator=validate_springer_field(validate_str, field="subject"),
                default=None,
                required=False,
            ),
            keyword=APISpecificParameter(
                name="keyword",
                description="Filter results by specific keyword(s). Searches within article keywords/tags.",
                validator=validate_springer_field(validate_str, field="keyword"),
                default=None,
                required=False,
            ),
            type=APISpecificParameter(
                name="type",
                description=(
                    "Filter by content type: 'Journal' (journal articles), 'Book' (book chapters), "
                    "'BookSeries', or 'Protocol'. Helps narrow results to specific publication types."
                ),
                validator=validate_springer_field(validate_str, field="type"),
                default=None,
                required=False,
            ),
            datefrom=APISpecificParameter(
                name="datefrom",
                description=(
                    "Filter results published on or after this date. Format: YYYY-MM-DD. "
                    "Example: '2023-01-01' for papers from 2023 onwards."
                ),
                validator=validate_springer_field(validate_date, field="datefrom"),
                default=None,
                required=False,
            ),
            dateto=APISpecificParameter(
                name="dateto",
                description=(
                    "Filter results published on or before this date. Format: YYYY-MM-DD. "
                    "Use with 'datefrom' for date range queries."
                ),
                validator=validate_springer_field(validate_date, field="dateto"),
                default=None,
                required=False,
            ),
        ),
    ),
    metadata_map=ResponseMetadataMap(total_query_hits="total", records_per_page="pageLength"),
    field_map=field_map,
    provider_name=name,
    base_url="https://api.springernature.com/meta/v2/json",
    api_key_env_var="SPRINGER_NATURE_API_KEY",
    records_per_page=25,
    docs_url="https://dev.springernature.com/docs/introduction/",
)


__all__ = ["provider"]
