# /api/providers
"""The scholar_flux.api.providers module contains the pre-defined config settings that are used to make a set of API
providers available by default. The module was designed for extensibility to enable the addition of new providers with
as little effort as possible.

Each individual sub-module within scholar_flux.api.providers defines a `ProviderConfig` that indicates the basic
settings describing how requests to each provider will be built. It also defines parameters that may need to be
included that are specific to that particular API that may not apply to other providers.

Basic ProviderConfig Components:
    **parameter_map**:
        Defines the specific parameter names within an BaseAPIParameterMap that will be required by the
        API provider to interact with their API in a predictable and robust manner.
    **provider_name**:
        An name alias of an API or a service within an API. Indicates how the API will be referenced.
    **base_url**:
        Indicates the base URL of the API and where all requests will be sent (note that this may differ
        from the organization's website slightly - or sometimes greatly - for a particular API service)
    api_key_env_var:
        An indicator of the name of an environment variable that will be referenced if an API key is
        not specifically listed.
    records_per_page:
        Indicates the default records per page that will be retrieved when a SearchAPI is created by default
        if otherwise left unspecified by the user. Depending on the provider, most APIs require a hard
        limit on the total number of records that are retrieved if this total isn't already specified.


Default Providers:
    **arXiv**:
        - website: https://arxiv.org/
        - purpose: An open access archive and repository allowing access to scientific papers in several
                   fields such as engineering, mathematics, and computer science.
        - access:  Allows access to metadata/research papers without an API key. Note that the use of the
                   works found through arXiv may require contacting the authors for re-use.

    **OpenAlex**:
        - website: https://openalex.org/
        - purpose: A comprehensive index and a worldwide, open access database consisting of scientific
                   papers and bibliographic materials available to the public.
        - access:  Allows access to metadata/research papers without an API key for use-cases inside
                   the terms of service

    **Core**:
        - website: https://core.ac.uk/services
        - purpose: Contains a vast corpus of searchable papers - both full-text papers and abstracts
        - access:  Allows access to metadata/research papers with an API key for use-cases inside
                   the terms of service
    **Crossref**:
        - website: https://api.crossref.org
        - purpose: A community-owned scholarly metadata source that specializes in metadata retrieval
                   used to aid the development of insight into research.
        - access:  Allows access open source access to scholarly articles without restriction. Note
                   that providing a `mailto` and `user-agent` optional but encouraged, allowing them to
                   contact you with feedback on API usage

    **PLOS**:
        - website: https://plos.org
        - purpose: A non-profit organization aimed at innovation and the advancement of research. Provides
                   access to an API containing scientific articles, manuscripts, and abstracts.
        - access:  Free to access without an API key - be cognizant of rate limits however.

    **PubMed**:
        - website: https://pubmed.ncbi.nlm.nih.gov
        - purpose: A freely accessible database hosted by the United States National Library of Medicine
                   that enables access to a vast range of medical research papers, references, and abstracts.
        - access:  The PubMed database is available to those with an API Key. an API key is free and usage
                   is permitted within the terms of service.

    **SpringerNature**:
        - website: https://dev.springernature.com
        - purpose: A publisher committed to open science that provides access to books, abstracts and
                   scientific manuscripts to aid the advancement of research. The API offers access to a
                   wide range of materials to support the advancement of research.
        - access:  Allows access to the SpringerNature API with an API key without cost. Usage, similar to other
                   APIs is rate limited. For higher rate limits and advance queries, the provider also offers
                   a premium service.

Note that the use of a default provider doesn't require the ProviderConfig to be explicitly provided. Instead,
a user can specify the name of a provider and provide API specific information if needed on the creation of
a search API or coordinator.

Example:
    >>> import os
    >>> from scholar_flux.api import SearchAPI
    # When an API key is required, it can be set:
    >>> api = SearchAPI.from_defaults('CORE', api_key = <Your API key here>)
    # or if it's set as an environment variable already:
    >>> api = SearchAPI.from_defaults('CORE')
    # You can determine whether the API key was read otherwise by checking:
    >>> assert api.api_key is not None

"""
from scholar_flux.api.models.provider_registry import ProviderRegistry
from types import MappingProxyType

# creates an object that can be overridden to add new mappings of provider names to provider configs
provider_registry = ProviderRegistry.from_defaults()

# create a separate immutable mapping of the same providers
PROVIDER_DEFAULTS = MappingProxyType(provider_registry.copy())

__all__ = ["provider_registry", "PROVIDER_DEFAULTS"]
