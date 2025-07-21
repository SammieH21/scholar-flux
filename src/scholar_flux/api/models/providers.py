from dataclasses import dataclass
from typing import Dict, Optional, Union, Any
from .provider_info import ProviderInfo 
from .base import BaseAPIParameterMap
from enum import Enum

class PROVIDER_DEFAULTS(Enum):
    """Enumerated class specifying default API parameters for default providers"""
    PLOS = ProviderInfo(
        parameter_map=BaseAPIParameterMap(
            query="q",
            start="start",
            records_per_page="rows",
            api_key_param=None,
            api_key_required=False,
            auto_calculate_page=True,
            ),
        name="plos",
        base_url="https://api.plos.org/search",
        records_per_page=50,
        docs_url="https://api.plos.org/solr/faq/"
    )

    SPRINGERNATURE = ProviderInfo(
        parameter_map=BaseAPIParameterMap(
            query="q",
            start="s",
            records_per_page="p",
            api_key_param="api_key",
            api_key_required=True,
            auto_calculate_page=True,
            ),
        name="springernature",
        base_url="https://api.springernature.com/meta/v2/json",
        records_per_page=25,
        docs_url="https://dev.springernature.com/docs/introduction/"
    )

    CORE = ProviderInfo(
        parameter_map=BaseAPIParameterMap(
            query="q",
            start="offset",
            records_per_page="limit",
            api_key_param="api_key",
            api_key_required=False,
            auto_calculate_page=True,
            ),
        name="core",
        base_url="https://api.core.ac.uk/v3/search/works/",
        records_per_page=25,
        docs_url="https://api.core.ac.uk/docs/v3#section/Welcome!"
    )

    CROSSREF = ProviderInfo(
        parameter_map=BaseAPIParameterMap(
            query="query",
            start="offset",
            records_per_page="rows",
            api_key_param="api_key",
            api_key_required=False,
            auto_calculate_page=True,
            additional_parameter_names=dict(mailto='mailto')
        ),
        name="crossref",
        base_url="https://api.crossref.org/works",
        records_per_page=25,
        docs_url="https://www.crossref.org/documentation/retrieve-metadata/rest-api/"
    )

    @classmethod
    def get(cls, name:str) -> Optional[ProviderInfo]:
        """
        Attempt to retrieve a ProviderInfo instance for the given provider name.
        Will not throw an error in the event that the provider does not exist.

        Args:
            name (str): Name of the default Provider
        Returns:
            ProviderInfo: instance configuration for the provider if it exists
        """

        if provider_info:=getattr(cls, name.upper(), None):
            return provider_info.value
        return None
