# /api/providers/pubmed_efetch.py
"""Defines the core configuration necessary to interact with the PubMed eFetch API using the scholar_flux package."""
from functools import partial
from scholar_flux.api.models.provider_config import ProviderConfig
from scholar_flux.api.models.base_parameters import BaseAPIParameterMap, APISpecificParameter
from scholar_flux.api.models.response_metadata_map import ResponseMetadataMap
from scholar_flux.api.normalization.pubmed_efetch_field_map import field_map
from scholar_flux.api.validators import validate_api_specific_field, validate_str

name = "pubmed_efetch"
validate_pubmed_efetch_field = partial(validate_api_specific_field, provider_name=name)

provider = ProviderConfig(
    parameter_map=BaseAPIParameterMap(
        query="term",
        start=None,
        records_per_page="retmax",
        api_key_parameter="api_key",
        api_key_required=True,
        auto_calculate_page=False,
        api_specific_parameters=dict(
            db=APISpecificParameter(
                name="db",
                description="A database to connect to for retrieving records/metadata",
                validator=validate_pubmed_efetch_field(validate_str, field="db"),
                default="pubmed",
                required=False,
            ),
            cmd=APISpecificParameter(
                name="cmd",
                description=(
                    "An optional command to run in order to enter a supported command to the query. "
                    "Example: cmd=neighbor_history (Used to determine computational neighbors "
                    "during an Entrez search)"
                ),
                validator=validate_pubmed_efetch_field(validate_str, field="cmd"),
                required=False,
            ),
            query_key=APISpecificParameter(
                name="query_key",
                description=(
                    "The key associated with the previous esearch. When use_history is enabled for an "
                    "esearch, this parameter, when provided together with the WebEnv parameter, allows "
                    "for the retrieval of abstracts/metadata associated with the previous search term. "
                    "without the explicit specification of article Ids"
                ),
                validator=validate_pubmed_efetch_field(validate_str, field="query_key"),
                required=False,
            ),
            WebEnv=APISpecificParameter(
                name="WebEnv",
                description=(
                    "The environment corresponding to previously executed searches: used to retrieve "
                    "associated abstracts and articles without needing to specify manually them by ID"
                ),
                validator=None,
                required=False,
            ),
            id=APISpecificParameter(
                name="id",
                description="Ids corresponding to the metadata and abstracts of publications",
                default=None,
                validator=None,
                required=False,
            ),
            retmode=APISpecificParameter(
                name="retmode",
                description="The format to retrieve",
                default="xml",
                validator=validate_pubmed_efetch_field(validate_str, field="retmode"),
                required=False,
            ),
        ),
    ),
    metadata_map=ResponseMetadataMap(total_query_hits="Count", records_per_page="RetMax"),
    field_map=field_map,
    provider_name=name,
    base_url="https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
    api_key_env_var="PUBMED_API_KEY",
    records_per_page=20,
    request_delay=2,
    docs_url="https://www.ncbi.nlm.nih.gov/books/NBK25499/",
)


__all__ = ["provider"]
