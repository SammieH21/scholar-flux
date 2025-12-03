==================
Custom Providers
==================

ScholarFlux enables integration with any API through a three-layer configuration system. This guide demonstrates how to add custom providers—from news APIs to specialized research databases—with full support for normalization, caching, and concurrent search.

.. contents:: Table of Contents
   :local:
   :depth: 2

Overview
========

Why Add Custom Providers?
--------------------------

ScholarFlux ships with seven academic providers (PLOS, arXiv, PubMed, OpenAlex, Crossref, CORE, Springer Nature), but research needs vary:

- **Institution-specific databases**: University repositories, institutional archives
- **Domain-specific resources**: Medical databases, patent databases, legal research platforms
- **News and media APIs**: The Guardian, New York Times, Reuters
- **Specialized platforms**: bioRxiv, SSRN, RePEc, HAL, Europe PMC
- **Internal APIs**: Company knowledge bases, proprietary research databases

**ScholarFlux's provider system is universal**—it works with any REST API returning JSON or XML.

The Three Configuration Layers
-------------------------------

Every provider is defined by three components:

**1. APIParameterMap** - Request parameter mapping

This core component needed to create a minimally viable ProviderConfig. It maps ScholarFlux parameters to API-specific parameter names:

.. code-block:: python

   APIParameterMap(
       query='q',                    # query → q
       start='page',                 # start → page
       records_per_page='page-size'  # records_per_page → page-size
   )


**2. Field Map** - Record field normalization

An optional component that is used to map API-specific field names to universal field names used throughout ScholarFlux (particularly in academic applications). Normalizes API-specific fields to provider-agnostic field names:

.. code-block:: python

   # For academic APIs, use AcademicFieldMap
   from scholar_flux.api.normalization import AcademicFieldMap
   
   field_map = AcademicFieldMap(
       provider_name='my_provider',
       title='article_title',
       abstract='summary',
       doi='DOI'
   )
   
   # For non-academic APIs, subclass NormalizingFieldMap
   from scholar_flux.api.normalization import NormalizingFieldMap
   
   class ArticleFieldMap(NormalizingFieldMap):
       provider_name: str = ""
       title: str | list[str] | None = None
       url: str | list[str] | None = None
       text: str | list[str] | None = None

.. seealso::
   For detailed information on field normalization patterns, see :doc:`schema_normalization`.

**3. ResponseMetadataMap** - Response metadata extraction

Extracts pagination info from API responses. This map is optional and mainly used when determining if there are more retrievable pages associated with a query when retrieving multiple pages in succession.

.. code-block:: python

   ResponseMetadataMap(
       total_query_hits='total',  # Path to total results
       records_per_page='pageSize' # path to page-size
   )

Minimal Provider Example
========================

ScholarFlux offers a high degree of customization, the minimally viable provider-config only requires users to create an APIParameterMap and a ProviderConfig: 

.. code-block:: python

   from scholar_flux.api import ProviderConfig, APIParameterMap, provider_registry
   from scholar_flux import SearchCoordinator
   
   # Minimal configuration - just parameter mapping
   minimal_config = ProviderConfig(
       provider_name='a_custom_api_provider',
       base_url='https://api.a_custom_api_provider.com/search',
       parameter_map=APIParameterMap(
           query='query',
           start='item-start-number',
           records_per_page='items-per-page'
       ),
       records_per_page=20
   )
   
   provider_registry.add(minimal_config)
   
   # Use immediately - returns raw API response
   coordinator = SearchCoordinator(
       query="test",
       provider_name="a_custom_api_provider"
   )
   # [Dry Run] - Shows how each parameter is mapped in the prepared request URL
   prepared_request = coordinator.api.prepare_search(page=1)
   print(prepared_request.url) # indicates the URL that the request would be sent to
   # OUTPUT: https://api.a_custom_api_provider.com/search?query=test&item-start-number=1&items-per-page=20

   result = coordinator.search_page(page=1) # response container with additional metadata
   
   if result:
       # Records have raw API field names
       print(result.response)  # The raw API response
       print(result.metadata)  # Extracted metadata
       print(result.data)  # Processed records
    else:
        print(f"Error retrieving page {result.page}. {result.error}: {result.message}")

Complete Example: Guardian News API
====================================

Let's add The Guardian's news API as a custom provider. This demonstrates a non-academic API with typical JSON responses.

Full Configuration
------------------

.. code-block:: python

   from scholar_flux.api import (
       ProviderConfig,
       APIParameterMap,
       ResponseMetadataMap,
       provider_registry
   )
   from scholar_flux import SearchCoordinator
   from scholar_flux.api.normalization import NormalizingFieldMap

   
   # Step 1: Configure API parameters
   parameters = APIParameterMap(
       query='q',                     # Guardian uses 'q' for queries
       start='page',                  # Guardian uses 'page' for pagination
       records_per_page='page-size',  # Guardian uses 'page-size' for limit
       api_key_parameter='api-key',   # API key parameter name
       auto_calculate_page=False,     # Use page number directly
       zero_indexed_pagination=False, # Pages start at 1, not 0
       api_key_required=True          # API key is mandatory
   )
   
   # Step 2 (Optional - for field normalization): Define custom field map for news articles
   class ArticleFieldMap(NormalizingFieldMap):
       """Field map for journalism/news APIs."""
       provider_name: str = ""
       title: str | list[str] | None = None
       record_id: str | list[str] | None = None
       record_type: str | list[str] | None = None
       subject: str | list[str] | None = None
       text: str | list[str] | None = None
       url: str | list[str] | None = None
       date_published: str | list[str] | None = None

   
   # Step 3 (Optional - for field normalization): Configure field mappings
   field_map = ArticleFieldMap(
       provider_name='guardian',
       title='webTitle',              # Guardian's title field
       record_id='id',                # Guardian's ID field
       record_type='type',            # Article type
       subject='sectionName',         # Section as subject
       text='fields.trailText',       # Nested field for preview text
       url='webUrl',                  # Article URL
       date_published='webPublicationDate',
       api_specific_fields={          # Guardian-specific fields
           'section_name': 'sectionName',
           'pillar_name': 'pillarName'
       }
   )
   
   # Step 4 (Optional): Configure metadata extraction
   metadata = ResponseMetadataMap(
       total_query_hits='total', # Path to total results
       records_per_page='pageSize' # path to page-size
   )

   
   # Step 5: Create provider configuration
   guardian_config = ProviderConfig(
       provider_name='guardian',
       base_url='https://content.guardianapis.com/search',
       parameter_map=parameters,
       metadata_map=metadata,
       field_map=field_map,
       records_per_page=10,           # Default page size
       request_delay=1.0,             # Wait 1s between requests
       api_key_env_var='GUARDIAN_API_KEY',  # Environment variable
       docs_url='https://open-platform.theguardian.com/documentation/'
   )
   
   # Step 6: Add to registry
   provider_registry.add(guardian_config)
   
   # Step 7: Use immediately!
   coordinator = SearchCoordinator(
       query="artificial intelligence",
       provider_name="guardian"
   )
   result = coordinator.search(page=1, normalize_records=True)
   
   if result:
       print(f"Retrieved {len(result.data)} articles")
       normalized = result.normalized_records or []
       if normalized:
           print(f"First article: {normalized[0]['title']}")

**What just happened:**

✅ Configured parameter mapping (query → q, page → page)  
✅ Created custom field map for news articles  
✅ Configured field normalization (webTitle → title)  
✅ Configured metadata extraction (total results)  
✅ Added to registry—now works like built-in providers  
✅ Full ScholarFlux integration (caching, rate limiting, multi-provider search)

Understanding the Configuration
--------------------------------

**APIParameterMap explained:**

The core step used by ScholarFlux to translate requests into something that Guardian can understand. The Guardian API expects parameters like ``?q=technology&page=1&page-size=10&api-key=xxx``. ScholarFlux uses standard names (``query``, ``start``, ``records_per_page``), so we map them:

.. code-block:: python

   APIParameterMap(
       query='q',                     # ScholarFlux 'query' → Guardian 'q'
       start='page',                  # ScholarFlux 'start' → Guardian 'page'
       records_per_page='page-size',  # ScholarFlux 'records_per_page' → Guardian 'page-size'
       api_key_parameter='api-key',   # Where to insert the API key
       auto_calculate_page=False,     # Guardian uses page numbers (1, 2, 3...), so these are used directly
       zero_indexed_pagination=False  # First page is 1, not 0
   )

**Field map explained:**

Guardian returns records with fields like ``webTitle``, ``webUrl``, etc. We normalize these:

.. code-block:: python

   field_map = ArticleFieldMap(
       provider_name='guardian',
       title='webTitle',              # Guardian's title → universal 'title'
       url='webUrl',                  # Guardian's URL → universal 'url'
       text='fields.trailText'        # Nested field extraction
   )

**ResponseMetadataMap explained:**

Guardian returns JSON like:

.. code-block:: text

   {
     "response": {
       "total": 50000,
       "pageSize": "25",
       "results": [...]
     }
   }

As nested metadata paths are traversed directly on extraction, we simply tell ScholarFlux the field names:

.. code-block:: python

   ResponseMetadataMap(
       total_query_hits='total', # Path to total results
       records_per_page='pageSize' # path to page-size
   )

Common Patterns
===============

Pagination Styles
-----------------

Different APIs use different pagination approaches:

**Page-based, one-indexed (e.g., OpenAlex):**

.. code-block:: python

   # API expects: ?page=1, ?page=2, ?page=3
   APIParameterMap(
        query="search",
        start="page",
        records_per_page="per_page",
        api_key_parameter="api_key",
        api_key_required=False,
        auto_calculate_page=False,
        zero_indexed_pagination=False,
    )

**Offset-based, zero-indexed (e.g., arXiv):**

.. code-block:: python

   # API expects: ?start=0, ?start=25, ?start=50
   APIParameterMap(
       query='search_query',
       start='start',
       records_per_page='max_results',
       api_key_parameter="api_key",
       api_key_required=False,
       auto_calculate_page=True,      # Calculate: (page-1) × records_per_page
       zero_indexed_pagination=True   # First record is at index 0
   )

**Example page -> offset calculation (one-indexed):**

- Page 1: ``start = 1 + (1-1) × 25 = 1``
- Page 2: ``start = 1 + (2-1) × 25 = 26``
- Page 3: ``start = 1 + (3-1) × 25 = 51``

**Mixed (Crossref):**

.. code-block:: python

   # API uses offset but calls it 'cursor' or 'offset'
   APIParameterMap(
       query='query',
       start='offset',
       records_per_page='rows',
       auto_calculate_page=True,
       zero_indexed_pagination=False
   )

API Key Handling
----------------

**Query parameter (Guardian):**

.. code-block:: python

   parameters = APIParameterMap(
       query='q',
       records_per_page='pageSize',
       api_key_parameter='api-key',  # Parameter name
       api_key_required=True         # Raise error if missing
   )
   
   config = ProviderConfig(
       provider_name='my_provider',
       parameter_map=parameters,
       api_key_env_var='MY_API_KEY'  # Environment variable to check
   )

**Optional API key:**

.. code-block:: python

   parameters = APIParameterMap(
       query='q',
       records_per_page='pageSize',
       api_key_parameter='apikey',
       api_key_required=False  # API works without key (slower rate limit)
   )

.. note::
   For header-based authentication (``Authorization: Bearer xxx``), use a custom session with headers. See API reference for details.

Field Mapping Patterns
----------------------

**Simple field mapping:**

.. code-block:: python

   # Direct field name mapping
   field_map = AcademicFieldMap(
       provider_name='my_provider',
       title='article_title',  # API field: article_title → title
       doi='DOI',              # API field: DOI → doi
       authors='author_list'   # API field: author_list → authors
   )

**Nested field mapping:**

.. code-block:: python

   # Extract from nested objects
   field_map = AcademicFieldMap(
       provider_name='my_provider',
       title='metadata.title',           # metadata.title → title
       abstract='content.abstract',      # content.abstract → abstract
       authors='authors.contributor.name' # Deep nesting
   )

**Fallback field mapping:**

.. code-block:: python

   # Try multiple field names (uses first non-null value)
   field_map = AcademicFieldMap(
       provider_name='my_provider',
       title=['title', 'headline', 'name'],  # Try in order
       abstract=['abstract', 'summary', 'description']
   )

.. seealso::
   For advanced field mapping including nested arrays, conditional extraction, and custom processors, see :doc:`schema_normalization`.

Testing Your Provider
=====================

Validation Checklist
--------------------

Before using a custom provider in production:

1. **Test with real queries:**

   .. code-block:: python
   
      coordinator = SearchCoordinator(
          query="test query",
          provider_name="my_provider"
      )
      
      # Test basic retrieval with `search_page` (returns a `SearchResult` container with additional metadata)
      result = coordinator.search_page(page=1)
      assert result, f"Failed: {type(result.response_result)}: {result.error} - {result.message}"
      print(f"✓ Retrieved {len(result.data)} records")
      
      # Test multiple pages
      results = coordinator.search_pages(pages=range(1, 4))
      successful = results.filter()
      print(f"✓ Retrieved {len(successful)}/{len(results)} pages")

2. **Verify normalization:**

   .. code-block:: python
   
      # Tests retrieval with the returned `ProcessedResponse`, `ErrorResponse`, or None
      result = coordinator.search(page=2, normalize_records=True)
      if result and result.normalized_records:
          record = result.normalized_records[0]
          print(f"✓ Title: {record.get('title')}")
          print(f"✓ DOI: {record.get('doi')}")
          print(f"✓ Provider: {record.get('provider_name')}")
      else:
          print("✗ Normalization failed")

3. **Test pagination:**

   .. code-block:: python
   
      # Verify pages return different records
      page1 = coordinator.search(page=1)
      page2 = coordinator.search(page=2)
      
      if page1 and page2:
          ids1 = [r['id'] for r in page1.data if 'id' in r]
          ids2 = [r['id'] for r in page2.data if 'id' in r]
          overlap = set(ids1) & set(ids2)
          print(f"✓ Pages have {len(overlap)} overlapping IDs (should be 0)")

4. **Check metadata extraction:**

   .. code-block:: python
   
      result = coordinator.search(page=1)
      if result:
          print(f"✓ Total results: {result.total_query_hits}")
          print(f"✓ Records per page: {result.records_per_page}")

Common Issues
-------------

**"No records found" but API returns data:**

Check your record extraction path. Add debug logging:

.. code-block:: python

   result = coordinator.search(page=1)
   if result:
       print(f"Parsed response keys: {result.parsed_response.keys()}")
       print(f"Extracted records: {len(result.extracted_records or [])}")

**"Field not found" during normalization:**

Check field names in actual API response:

.. code-block:: python

   result = coordinator.search(page=1)
   if result and result.data:
       sample_record = result.data[0]
       print(f"Available fields: {list(sample_record.keys())}")

**Pagination returns same records:**

Verify the mapped parameters from ``APIParameterMap`` against the API provider's requirements using its documentation:

.. code-block:: python

   # If API uses page numbers (1, 2, 3):
   print(coordinator.api.parameter_config.map)
   

Best Practices
==============

Configuration Guidelines
------------------------

1. **Check API rate limiting requirements directly and start conservative with rate limits:**

   .. code-block:: python
   
      # Start with a longer delay
      request_delay=5.0
      
      # Monitor API response headers
      # Adjust based on documented limits

2. **Use descriptive provider names:**

   .. code-block:: python
   
      # Good
      provider_name='europepmc'
      provider_name='semantic_scholar'
      
      # Avoid
      provider_name='api1'
      provider_name='custom'

3. **Document your configuration:**

   .. code-block:: python
   
      """
      Custom ScholarFlux Provider: Europe PMC
      
      Requirements:
      - No API key required
      - Rate limit: 3 requests/second
      
      Usage:
          >>> from my_providers import europepmc_config
          >>> provider_registry.add(europepmc_config)
          >>> coordinator = SearchCoordinator(
          ...     query="cancer",
          ...     provider_name="europepmc"
          ... )
      
      API Documentation:
      - https://europepmc.org/RestfulWebService
      """

4. **Test with diverse queries:**

   .. code-block:: python
   
      test_queries = [
          "simple query",
          "complex AND (query OR terms)",
          "phrase in quotes",
          "year:2024"
      ]
      
      for query in test_queries:
          coordinator = SearchCoordinator(
              query=query,
              provider_name="my_provider"
          )
          result = coordinator.search(page=1)
          print(f"{query}: {'✓' if result else '✗'}")

Error Handling
--------------

ScholarFlux uses response types instead of exceptions:

.. code-block:: python

   from scholar_flux import SearchCoordinator
   from scholar_flux.api.models import NonResponse, ErrorResponse
   
   def safe_search(query: str, provider_name: str):
       coordinator = SearchCoordinator(query=query, provider_name=provider_name)
       result = coordinator.search(page=1)
       
       # ProcessedResponse (truthy) - success
       if result:
           return result.normalize()
       
       # NonResponse - network error or API unreachable
       if isinstance(result.response_result, NonResponse):
           print(f"Network error: {result.message}")
           return []
       
       # ErrorResponse - API returned error
       if isinstance(result.response_result, ErrorResponse):
           print(f"API error: {result.message}")
           return []
       
       return []

.. tip::
   Check response validity with ``if result:`` rather than ``try/except`` for cleaner code.

Next Steps
==========

**Related Guides:**

- :doc:`schema_normalization` - Deep dive into field normalization patterns
- :doc:`multi_provider_search` - Use custom providers in concurrent searches
- :doc:`advanced_workflows` - Multi-step retrieval for complex APIs (like PubMed's two-step process)

**Advanced Topics:**

- :doc:`caching_strategies` - Production caching with Redis, MongoDB, SQLAlchemy
- :doc:`production_deployment` - Deploy custom providers at scale

**API Reference:**

- :class:`scholar_flux.api.models.ProviderConfig` - Complete configuration reference
- :class:`scholar_flux.api.models.APIParameterMap` - Parameter mapping reference
- :class:`scholar_flux.api.normalization.AcademicFieldMap` - Academic field mapping
- :class:`scholar_flux.api.normalization.NormalizingFieldMap` - Base field map for custom schemas

Community Contributions
-----------------------

Consider sharing your custom providers:

1. Test thoroughly with the validation checklist
2. Document clearly with usage examples
3. Open a pull request at https://github.com/SammieH21/scholar-flux
4. Include tests demonstrating functionality

Popular community providers may be included in future ScholarFlux releases!

Getting Help
------------

If you encounter issues:

1. **Check API documentation**: Verify parameter names and response structure
2. **Test API directly**: Use ``curl`` or ``requests`` to understand behavior
3. **Search issues**: https://github.com/SammieH21/scholar-flux/issues
4. **Open an issue**: Include provider details, config code, and error messages
5. **Email**: scholar.flux@gmail.com

When requesting help, include:

- Provider name and documentation URL
- Your ``ProviderConfig`` code
- Sample API response (anonymize sensitive data)
- Error messages or unexpected behavior
- ScholarFlux version: ``pip show scholar-flux``
