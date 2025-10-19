# /api/providers/springer_nature.py
"""Defines the core configuration necessary to interact with the Springer Nature API using the scholar_flux package."""
from scholar_flux.api.models.provider_config import ProviderConfig
from scholar_flux.api.models.base_parameters import BaseAPIParameterMap

provider = ProviderConfig(
    parameter_map=BaseAPIParameterMap(
        query="q",
        start="s",
        records_per_page="p",
        api_key_parameter="api_key",
        api_key_required=True,
        auto_calculate_page=True,
    ),
    provider_name="springernature",
    base_url="https://api.springernature.com/meta/v2/json",
    api_key_env_var="SPRINGER_NATURE_API_KEY",
    records_per_page=25,
    docs_url="https://dev.springernature.com/docs/introduction/",
)


__all__ = ["provider"]
