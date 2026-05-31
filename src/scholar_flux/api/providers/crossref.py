# /api/providers/crossref.py
"""Defines the core configuration necessary to interact with the Crossref API using the scholar_flux package.

Note that Crossref has a plus tier for increased API support/features and supports API keys via a
`CROSSREF-PLUS-API-TOKEN` header, prefixed with `Bearer [API Key]`. To use header-based authentication with
Crossref, ensure that `CROSSREF_API_KEY` (aliased as `CROSSREF-PLUS-API-TOKEN`) is stored either as an environment
variable or directly within `scholar_flux.config_settings`. The token will be automatically read and formatted on
`SearchAPI`/`SearchCoordinator` instantiation.

Example:
    >>> from scholar_flux import SearchAPI, config_settings
    >>> crossref_api_key = config_settings.get("CROSSREF_API_KEY")  # Read as a `SecretStr` if exists, None otherwise
    >>> crossref_search_api = SearchAPI(query='example_query', provider_name = "crossref", api_key=crossref_api_key)
    # Check whether the token is available. Should return an `AuthHeader(SecretKey)` if the API key exists.
    >>> crossref_search_api.build_auth()

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
        api_key_parameter="CROSSREF-PLUS-API-TOKEN",
        api_key_required=False,
        api_key_scheme="Bearer",
        api_key_in_headers=True,
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
            filter=APISpecificParameter(
                name="filter",
                description=(
                    "Return filtered records by key-value pair (e.g., 'has-abstract:1', 'update-type:retraction', "
                    "'from-created-date:YYYY-MM-DD', 'has-license:f'). Filter parameters can also be used together "
                    "(i.e., has-abstract:1,from-created-date:2025)"
                ),
                validator=validate_crossref_field(validate_str, field="filter"),
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
    display_name="Crossref",
)

__all__ = ["provider"]
