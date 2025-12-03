# /api/providers/open_alex.py
"""Defines the core configuration necessary to interact with the OpenAlex API using the scholar_flux package."""
from scholar_flux.api.models.provider_config import ProviderConfig
from scholar_flux.api.models.base_parameters import BaseAPIParameterMap
from scholar_flux.api.models.response_metadata_map import ResponseMetadataMap
from scholar_flux.api.normalization.open_alex_field_map import field_map

provider = ProviderConfig(
    parameter_map=BaseAPIParameterMap(
        query="search",
        start="page",
        records_per_page="per_page",
        api_key_parameter="api_key",
        api_key_required=False,
        auto_calculate_page=False,
        zero_indexed_pagination=False,
    ),
    metadata_map=ResponseMetadataMap(total_query_hits="count", records_per_page="per_page"),
    field_map=field_map,
    provider_name="openalex",
    base_url="https://api.openalex.org/works",
    api_key_env_var="OPEN_ALEX_API_KEY",
    records_per_page=25,
    docs_url="https://docs.openalex.org/api-entities/works/get-lists-of-works",
)

__all__ = ["provider"]
