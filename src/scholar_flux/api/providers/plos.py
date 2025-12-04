# /api/providers/plos.py
"""Defines the core configuration necessary to interact with the PLOS API using the scholar_flux package."""
from scholar_flux.api.models.provider_config import ProviderConfig
from scholar_flux.api.models.base_parameters import BaseAPIParameterMap
from scholar_flux.api.models.response_metadata_map import ResponseMetadataMap
from scholar_flux.api.normalization.plos_field_map import field_map

provider = ProviderConfig(
    parameter_map=BaseAPIParameterMap(
        query="q",
        start="start",
        records_per_page="rows",
        api_key_parameter=None,
        api_key_required=False,
        auto_calculate_page=True,
    ),
    metadata_map=ResponseMetadataMap(total_query_hits="numFound", records_per_page=None),
    field_map=field_map,
    provider_name="plos",
    base_url="https://api.plos.org/search",
    records_per_page=50,
    docs_url="https://api.plos.org/solr/faq",
)


__all__ = ["provider"]
