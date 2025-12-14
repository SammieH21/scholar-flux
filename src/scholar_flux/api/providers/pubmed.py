# /api/providers/pubmed.py
"""PubMed API configuration for scholar_flux."""
from functools import partial
from scholar_flux.api.models.provider_config import ProviderConfig
from scholar_flux.api.models.base_parameters import BaseAPIParameterMap, APISpecificParameter
from scholar_flux.api.models.response_metadata_map import ResponseMetadataMap
from scholar_flux.api.normalization.pubmed_field_map import field_map
from scholar_flux.api.validators import validate_api_specific_field, validate_str

name = "pubmed"
validate_pubmed_field = partial(validate_api_specific_field, provider_name=name)

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
                description="An Entrez database to connect to for retrieving records/metadata",
                validator=validate_pubmed_field(validate_str, field="db"),
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
            sort=APISpecificParameter(
                name="sort",
                description="Sort order: 'relevance' or 'pub_date'.",
                validator=validate_pubmed_field(validate_str, field="sort"),
                required=False,
            ),
            mindate=APISpecificParameter(
                name="mindate",
                description="Start of date range (YYYY/MM/DD, YYYY/MM, or YYYY).",
                validator=validate_pubmed_field(validate_str, field="mindate"),
                required=False,
            ),
            maxdate=APISpecificParameter(
                name="maxdate",
                description="End of date range (YYYY/MM/DD, YYYY/MM, or YYYY).",
                validator=validate_pubmed_field(validate_str, field="maxdate"),
                required=False,
            ),
        ),
    ),
    metadata_map=ResponseMetadataMap(total_query_hits="Count", records_per_page="RetMax"),
    field_map=field_map,
    provider_name=name,
    base_url="https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
    api_key_env_var="PUBMED_API_KEY",
    records_per_page=20,
    request_delay=2,
    docs_url="https://www.ncbi.nlm.nih.gov/books/NBK25499/",
)

__all__ = ["provider"]
