# /api/providers/pubmed.py
"""Defines the core configuration necessary to interact with the PubMed eSearch API using the scholar_flux package."""
from scholar_flux.api.models.provider_config import ProviderConfig
from scholar_flux.api.models.base_parameters import BaseAPIParameterMap, APISpecificParameter

provider = ProviderConfig(
    parameter_map=BaseAPIParameterMap(
        query="term",
        start="retstart",
        records_per_page="retmax",
        api_key_parameter="api_key",
        api_key_required=True,
        auto_calculate_page=True,
        api_specific_parameters=dict(
            db=APISpecificParameter(
                name="db",
                description="A database to connect to for retrieving records/metadata",
                validator=None,
                default="pubmed",
                required=False,
            ),
            use_history=APISpecificParameter(
                name="use_history",
                description="Determines whether to use the previous history when fetching abstracts",
                validator=None,
                default="y",
                required=False,
            ),
        ),
    ),
    provider_name="pubmed",
    base_url="https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
    api_key_env_var="PUBMED_API_KEY",
    records_per_page=20,
    request_delay=2,
    docs_url="https://www.ncbi.nlm.nih.gov/books/NBK25499/",
)


__all__ = ["provider"]
