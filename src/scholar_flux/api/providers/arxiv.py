# /api/providers/arxiv.py
"""Defines the core configuration necessary to interact with the arXiv API using the scholar_flux package.

Note:
    While arXiv allows you to filter by several categories, this is handled at the level of the query. This is defined
    when creating a` SearchCoordinator` or `SearchAPI` with the required `query` parameter for basic searches.

    Possible categories include:
    - `au:` To filter results by author
    - `abs:` Records containing abstracts
    - `all:` all results for a particular query

    For a complete list of arXiv category codes, see: https://arxiv.org/category_taxonomy

Example:
    >>> from scholar_flux import SearchCoordinator
    >>> from pprint import pprint
    >>> coordinator = SearchCoordinator(query = "cat:cs.AI AND probability", provider_name='arXiv')
    >>> results = coordinator.search_page(1)
    >>> pprint(results.data[:5] if results.data else "No data retrieved")

"""
from functools import partial
from scholar_flux.api.models.provider_config import ProviderConfig
from scholar_flux.api.models.base_parameters import BaseAPIParameterMap, APISpecificParameter
from scholar_flux.api.models.response_metadata_map import ResponseMetadataMap
from scholar_flux.api.normalization.arxiv_field_map import field_map
from scholar_flux.api.validators import validate_api_specific_field, validate_str

name = "arXiv"
validate_arxiv_field = partial(validate_api_specific_field, provider_name=name)

# Valid sort options for arXiv API
ARXIV_SORT_BY_OPTIONS = ("relevance", "lastUpdatedDate", "submittedDate")
ARXIV_SORT_ORDER_OPTIONS = ("ascending", "descending")

provider = ProviderConfig(
    parameter_map=BaseAPIParameterMap(
        query="search_query",
        start="start",
        records_per_page="max_results",
        api_key_parameter="api_key",
        api_key_required=False,
        auto_calculate_page=True,
        zero_indexed_pagination=True,
        api_specific_parameters=dict(
            sortBy=APISpecificParameter(
                name="sortBy",
                description=(
                    "Field to sort results by. Options: 'relevance' (default), 'lastUpdatedDate' (date of last update),"
                    " 'submittedDate' (original submission date). Use with sortOrder to control direction."
                ),
                validator=validate_arxiv_field(partial(validate_str, allowed=ARXIV_SORT_BY_OPTIONS), field="sortBy"),
                default="relevance",
                required=False,
            ),
            sortOrder=APISpecificParameter(
                name="sortOrder",
                description=(
                    "Sort direction: 'ascending' or 'descending' (default). For latest papers, use "
                    "sortBy='submittedDate' with sortOrder='descending'."
                ),
                validator=validate_arxiv_field(
                    partial(validate_str, allowed=ARXIV_SORT_ORDER_OPTIONS), field="sortOrder"
                ),
                default="descending",
                required=False,
            ),
        ),
    ),
    metadata_map=ResponseMetadataMap(
        total_query_hits="opensearch:totalResults", records_per_page="opensearch:itemsPerPage"
    ),
    field_map=field_map,
    provider_name=name,
    base_url="https://export.arxiv.org/api/query/",
    api_key_env_var="ARXIV_API_KEY",
    records_per_page=25,
    request_delay=4,
    docs_url="https://info.arxiv.org/help/api/basics.html",
    display_name="arXiv",
)

__all__ = ["provider"]
