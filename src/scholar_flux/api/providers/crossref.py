# /api/providers/crossref.py
"""Defines the core configuration necessary to interact with the Crossref API using the scholar_flux package."""
from scholar_flux.api.models.provider_config import ProviderConfig
from scholar_flux.api.models.base_parameters import BaseAPIParameterMap, APISpecificParameter
from scholar_flux.api.validators import validate_and_process_email

provider = ProviderConfig(
    parameter_map=BaseAPIParameterMap(
        query="query",
        start="offset",
        records_per_page="rows",
        api_key_parameter="api_key",
        api_key_required=False,
        auto_calculate_page=True,
        api_specific_parameters=dict(
            mailto=APISpecificParameter(
                name="mailto",
                description="An optional contact email for API usage feedback (must be a valid email address",
                validator=validate_and_process_email,
                required=False,
            ),
        ),
    ),
    provider_name="crossref",
    base_url="https://api.crossref.org/works",
    api_key_env_var="CROSSREF_API_KEY",
    records_per_page=25,
    docs_url="https://www.crossref.org/documentation/retrieve-metadata/rest-api/",
)

__all__ = ["provider"]
