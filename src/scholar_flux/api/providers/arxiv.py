# /api/providers/arxiv.py
"""Defines the core configuration necessary to interact with the arXiv API using the scholar_flux package."""
from scholar_flux.api.models.provider_config import ProviderConfig
from scholar_flux.api.models.base_parameters import BaseAPIParameterMap

provider = ProviderConfig(
    parameter_map=BaseAPIParameterMap(
        query="search_query",
        start="start",
        records_per_page="max_results",
        api_key_parameter="api_key",
        api_key_required=False,
        auto_calculate_page=True,
        zero_indexed_pagination=True,
    ),
    provider_name="arXiv",
    base_url="https://export.arxiv.org/api/query/",
    api_key_env_var="ARXIV_API_KEY",
    records_per_page=25,
    request_delay=4,
    docs_url="https://info.arxiv.org/help/api/basics.html",
)

__all__ = ["provider"]
