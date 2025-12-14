# /api/providers/core.py
"""Defines the core configuration necessary to interact with the CORE API using the scholar_flux package."""
from functools import partial
from scholar_flux.api.models.provider_config import ProviderConfig
from scholar_flux.api.models.base_parameters import BaseAPIParameterMap, APISpecificParameter
from scholar_flux.api.models.response_metadata_map import ResponseMetadataMap
from scholar_flux.api.normalization.core_field_map import field_map
from scholar_flux.api.validators import validate_api_specific_field, validate_str

name = "core"
validate_core_field = partial(validate_api_specific_field, provider_name=name)

provider = ProviderConfig(
    parameter_map=BaseAPIParameterMap(
        query="q",
        start="offset",
        records_per_page="limit",
        api_key_parameter="api_key",
        api_key_required=False,
        auto_calculate_page=True,
        api_specific_parameters=dict(
            sort=APISpecificParameter(
                name="sort",
                description="Sort by field:direction (e.g., 'publishedDate:desc').",
                validator=validate_core_field(validate_str, field="sort"),
                required=False,
            ),
            entityType=APISpecificParameter(
                name="entityType",
                description=(
                    "The type of entity or work to retrieve from the Core API endpoint. Options include the following: "
                    "['works', 'outputs', 'data-providers', 'journals']"
                ),
                validator=validate_core_field(validate_str, field="entityType"),
                required=False,
            ),
        ),
    ),
    metadata_map=ResponseMetadataMap(total_query_hits="totalHits", records_per_page="limit"),
    field_map=field_map,
    provider_name=name,
    base_url="https://api.core.ac.uk/v3/search/works",
    api_key_env_var="CORE_API_KEY",
    records_per_page=25,
    docs_url="https://api.core.ac.uk/docs/v3#section/Welcome!",
)

__all__ = ["provider"]
