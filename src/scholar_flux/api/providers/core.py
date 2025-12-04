# /api/providers/core.py
"""Defines the core configuration necessary to interact with the CORE API using the scholar_flux package."""
from scholar_flux.api.models.provider_config import ProviderConfig
from scholar_flux.api.models.base_parameters import BaseAPIParameterMap
from scholar_flux.api.models.response_metadata_map import ResponseMetadataMap
from scholar_flux.api.normalization.core_field_map import field_map

provider = ProviderConfig(
    parameter_map=BaseAPIParameterMap(
        query="q",
        start="offset",
        records_per_page="limit",
        api_key_parameter="api_key",
        api_key_required=False,
        auto_calculate_page=True,
    ),
    metadata_map=ResponseMetadataMap(total_query_hits="totalHits", records_per_page="limit"),
    field_map=field_map,
    provider_name="core",
    base_url="https://api.core.ac.uk/v3/search/works",
    api_key_env_var="CORE_API_KEY",
    records_per_page=25,
    docs_url="https://api.core.ac.uk/docs/v3#section/Welcome!",
)

__all__ = ["provider"]
