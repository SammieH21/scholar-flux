# /api/providers/plos.py
"""PLOS API configuration for scholar_flux."""
from functools import partial
from scholar_flux.api.models.provider_config import ProviderConfig
from scholar_flux.api.models.base_parameters import BaseAPIParameterMap, APISpecificParameter
from scholar_flux.api.models.response_metadata_map import ResponseMetadataMap
from scholar_flux.api.normalization.plos_field_map import field_map
from scholar_flux.api.validators import validate_api_specific_field, validate_str

name = "plos"
validate_plos_field = partial(validate_api_specific_field, provider_name=name)

provider = ProviderConfig(
    parameter_map=BaseAPIParameterMap(
        query="q",
        start="start",
        records_per_page="rows",
        api_key_parameter=None,
        api_key_required=False,
        auto_calculate_page=True,
        api_specific_parameters=dict(
            sort=APISpecificParameter(
                name="sort",
                description="Sort field and direction (e.g., 'publication_date desc').",
                validator=validate_plos_field(validate_str, field="sort"),
                required=False,
            ),
            fq=APISpecificParameter(
                name="fq",
                description=(
                    "Filter query to narrow results without affecting relevance scoring. "
                    "Examples: 'journal:PLoS ONE', 'article_type:Research Article', "
                    "'publication_date:[2020-01-01T00:00:00Z TO *]'."
                ),
                validator=validate_plos_field(validate_str, field="fq"),
                required=False,
            ),
        ),
    ),
    metadata_map=ResponseMetadataMap(total_query_hits="numFound", records_per_page=None),
    field_map=field_map,
    provider_name=name,
    base_url="https://api.plos.org/search",
    records_per_page=50,
    docs_url="https://api.plos.org/solr/faq",
)

__all__ = ["provider"]
