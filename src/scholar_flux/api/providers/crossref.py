# /api/providers/crossref.py
"""Defines the core configuration necessary to interact with the Crossref API using the scholar_flux package.

Note that Crossref has a plus tier for increased API support/features and does not accept an API key directly.

Crossref Plus users instead use a session header.

Example:
    >>> from scholar_flux import SearchAPI
    >>> import os
    >>>
    >>> token = os.environ.get("CROSSREF_PLUS_API_TOKEN")
    >>> crossref_search_api = SearchAPI(query='example_query', provider_name = "crossref")
    >>> crossref_search_api.session.headers['Crossref-Plus-API-Token'] = f"Bearer {token}"

Direct addition for auth headers may be added in the future when needed.

"""
from functools import partial
from scholar_flux.api.models.provider_config import ProviderConfig
from scholar_flux.api.models.base_parameters import BaseAPIParameterMap, APISpecificParameter
from scholar_flux.api.validators import (
    validate_and_process_email,
    validate_api_specific_field,
    validate_str,
)
from scholar_flux.api.models.response_metadata_map import ResponseMetadataMap
from scholar_flux.api.normalization.crossref_field_map import field_map

name = "crossref"
validate_crossref_field = partial(validate_api_specific_field, provider_name=name)

provider = ProviderConfig(
    parameter_map=BaseAPIParameterMap(
        query="query",
        start="offset",
        records_per_page="rows",
        api_key_parameter=None,
        api_key_required=False,
        auto_calculate_page=True,
        api_specific_parameters=dict(
            mailto=APISpecificParameter(
                name="mailto",
                description="An optional contact email for API usage feedback and increases rate limits. A value, when "
                "provided, must be a valid email address.",
                validator=validate_crossref_field(validate_and_process_email, field="mailto"),
                required=False,
            ),
            sort=APISpecificParameter(
                name="sort",
                description="Sort field (e.g., 'published', 'deposited', 'is-referenced-by-count', 'score').",
                validator=validate_crossref_field(validate_str, field="sort"),
                required=False,
            ),
            order=APISpecificParameter(
                name="order",
                description="Sort direction: 'asc' or 'desc'.",
                validator=validate_crossref_field(validate_str, field="order"),
                required=False,
            ),
        ),
    ),
    metadata_map=ResponseMetadataMap(total_query_hits="total-results", records_per_page="items-per-page"),
    field_map=field_map,
    provider_name=name,
    base_url="https://api.crossref.org/works",
    api_key_env_var="CROSSREF_API_KEY",
    request_delay=1.0,
    records_per_page=25,
    docs_url="https://www.crossref.org/documentation/retrieve-metadata/rest-api/",
)

__all__ = ["provider"]
