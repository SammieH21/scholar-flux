Schema Normalization
====================

This tutorial demonstrates ScholarFlux's schema normalization system, which transforms inconsistent provider-specific field names into a unified academic schema—ready for machine learning, analytics, and systematic reviews.

.. contents:: Table of Contents
   :local:
   :depth: 2

Overview
========

The Challenge: Different Field Names for the Same Data
-------------------------------------------------------

Academic APIs return the same information using wildly different field names:

.. code-block:: python

   # The same "title" field across providers:
   plos_record = {
       'title_display': 'Machine Learning in Genomics',  # PLOS
       'author_display': ['Smith J', 'Jones K']
   }
   
   arxiv_record = {
       'title': 'Machine Learning in Genomics',          # arXiv
       'author': [{'name': 'Smith J'}, {'name': 'Jones K'}]
   }
   
   crossref_record = {
       'title': ['Machine Learning in Genomics'],         # Crossref
       'author': [{'family': 'Smith', 'given': 'J'}]
   }
   
   openalex_record = {
       'display_name': 'Machine Learning in Genomics',    # OpenAlex
       'authorships': [{'author': {'display_name': 'Smith J'}}]
   }

**Result**: Building ML datasets requires hours of manual schema mapping and custom parsers for each provider.

The Solution: Automatic Schema Normalization
---------------------------------------------

ScholarFlux normalizes provider-specific field names into universal academic fields:

.. code-block:: python

   from scholar_flux import SearchCoordinator, MultiSearchCoordinator
   import pandas as pd
   
   # Query 4 providers
   multi = MultiSearchCoordinator()
   multi.add_coordinators([
       SearchCoordinator(query="machine learning", provider_name=provider)
       for provider in ['plos', 'arxiv', 'openalex', 'crossref']
   ])
   
   results = multi.search_pages(pages=range(1, 3))
   
   # Filter successful responses and normalize
   normalized_records = results.filter().normalize()
   
   # All records now have consistent field names
   df = pd.DataFrame(normalized_records)
   print(df.columns)
   # Index(['provider_name', 'doi', 'url', 'record_id', 'title', 'abstract',
   #        'authors', 'journal', 'publisher', 'year', 'date_published',
   #        'date_created', 'keywords', 'subjects', 'citation_count',
   #        'open_access', 'license', 'record_type', 'language', ...])

**What happened:**
- ✅ 4 different response schemas normalized to 1 unified schema
- ✅ Nested fields flattened (``author.name`` → ``authors``)
- ✅ Provider-specific fields preserved in additional columns
- ✅ Ready for immediate ML/analytics workflows

Learning Objectives
-------------------

By the end of this tutorial, you will:

- Normalize multi-provider search results with one method call
- Understand the universal academic fields in ``AcademicFieldMap``
- Build ML-ready pandas DataFrames from heterogeneous API responses
- Create custom field mappings for new providers
- Use fallback paths for fields with multiple possible locations
- Apply normalization at different levels (SearchResultList, SearchResult, ProcessedResponse)

Prerequisites
-------------

Before starting, ensure you have:

- Completed the :doc:`getting_started` tutorial
- Familiarity with :doc:`multi_provider_search` for concurrent queries
- Basic pandas knowledge (optional, for DataFrame examples)
- Installed ScholarFlux: ``pip install scholar-flux``

.. note::
   Normalization works with any provider—no special configuration needed!

Basic Normalization
===================

Single Provider Normalization
------------------------------

Normalize results from a single provider:

.. code-block:: python

   from scholar_flux import SearchCoordinator
   import pandas as pd
   
   # Search PLOS
   coordinator = SearchCoordinator(query="CRISPR", provider_name="plos")
   results = coordinator.search_pages(pages=range(1, 6))
   
   # Filter successful responses and normalize
   normalized_records = results.filter().normalize()
   
   # Convert to DataFrame
   df = pd.DataFrame(normalized_records)
   
   # All records have consistent field names
   print(df[['provider_name', 'title', 'doi', 'authors', 'journal']].head())

**Expected output:**

.. code-block:: text

   provider_name                                    title              doi
   0          plos  CRISPR-Cas9 genome editing in plants  10.1371/jour...
   1          plos       Therapeutic applications of...  10.1371/jour...
   2          plos  Ethical considerations in CRISPR use  10.1371/jour...

**Before normalization** (PLOS-specific fields):
- ``title_display`` → **After normalization**: ``title``
- ``id`` → ``doi``
- ``author_display`` → ``authors``

Multi-Provider Normalization
-----------------------------

The real power emerges with multiple providers:

.. code-block:: python

   from scholar_flux import SearchCoordinator, MultiSearchCoordinator
   import pandas as pd
   
   # Query 4 providers simultaneously
   multi = MultiSearchCoordinator()
   multi.add_coordinators([
       SearchCoordinator(query="machine learning", provider_name='plos'),
       SearchCoordinator(query="machine learning", provider_name='arxiv'),
       SearchCoordinator(query="machine learning", provider_name='openalex'),
       SearchCoordinator(query="machine learning", provider_name='crossref')
   ])
   
   # Retrieve 10 pages per provider (40 total requests)
   results = multi.search_pages(pages=range(1, 11))
   
   # Normalize all 1,250+ records in one call
   normalized_records = results.filter().normalize()
   
   # ML-ready DataFrame
   df = pd.DataFrame(normalized_records)
   
   print(f"Total records: {len(df)}")
   print(f"Providers: {df['provider_name'].unique()}")
   print(f"Fields: {len(df.columns)}")

**Expected output:**

.. code-block:: text

   Total records: 1250
   Providers: ['plos' 'arxiv' 'openalex' 'crossref']
   Fields: 37

**What ScholarFlux normalized:**

+------------------+-------------------------+---------------------------+------------------------+
| Universal Field  | PLOS                    | arXiv                     | OpenAlex               |
+==================+=========================+===========================+========================+
| ``title``        | ``title_display``       | ``title``                 | ``display_name``       |
+------------------+-------------------------+---------------------------+------------------------+
| ``doi``          | ``id``                  | ``doi`` (from links)      | ``doi``                |
+------------------+-------------------------+---------------------------+------------------------+
| ``authors``      | ``author_display``      | ``author.name``           | ``authorships.author`` |
+------------------+-------------------------+---------------------------+------------------------+
| ``abstract``     | ``abstract``            | ``summary``               | ``abstract``           |
+------------------+-------------------------+---------------------------+------------------------+
| ``year``         | ``publication_date``    | ``published``             | ``publication_year``   |
+------------------+-------------------------+---------------------------+------------------------+

.. tip::
   Normalization preserves provider-specific fields as additional columns—you get the best of both worlds!

The normalize() Method
----------------------

The :meth:`~scholar_flux.api.models.SearchResultList.normalize` method is available at three levels:

1. **SearchResultList** (recommended for batch operations):

   .. code-block:: python
   
      results = coordinator.search_pages(pages=range(1, 11))
      normalized = results.filter().normalize()  # List[dict]

2. **SearchResult** (single page):

   .. code-block:: python
   
      result = coordinator.search(page=1)
      normalized = result.normalize()  # List[dict]

3. **ProcessedResponse** (lowest level):

   .. code-block:: python
   
      result = coordinator.search(page=1)
      normalized = result.response_result.normalize()  # List[dict]

.. note::
   All three methods return the same structure: a list of dictionaries with normalized field names.

Inline Normalization
--------------------

For convenience, normalize during search execution:

.. code-block:: python

   from scholar_flux import SearchCoordinator
   
   coordinator = SearchCoordinator(query="CRISPR", provider_name="plos")
   
   # Normalize automatically during search
   result = coordinator.search(page=1, normalize_records=True)
   
   # Access cached normalized records
   normalized = result.response_result.normalized_records
   
   # Or call normalize() - returns cached results
   normalized = result.normalize()

**Why use inline normalization?**
- Normalized records are cached in ``ProcessedResponse.normalized_records``
- Subsequent ``normalize()`` calls return cached results (no recomputation)
- Useful when you know you'll need normalized data later

The filter() Method
-------------------

``SearchResultList.filter()`` removes unsuccessful responses before normalization:

.. code-block:: python

   from scholar_flux import SearchCoordinator
   
   coordinator = SearchCoordinator(query="test", provider_name="plos")
   results = coordinator.search_pages(pages=range(1, 20))
   
   # Without filter - may include ErrorResponse/NonResponse
   print(f"Total results: {len(results)}")
   
   # With filter - only ProcessedResponse instances
   successful = results.filter()
   print(f"Successful: {len(successful)}")
   
   # Normalize only successful responses
   normalized = successful.normalize()

**filter() behavior:**
- Keeps: ``ProcessedResponse`` instances (successful retrievals)
- Removes: ``ErrorResponse`` and ``NonResponse`` instances (failures)
- Returns: New ``SearchResultList`` with filtered results

.. tip::
   Always use ``filter()`` before ``normalize()`` to avoid errors from failed responses.

Understanding Universal Fields
==============================

The AcademicFieldMap
--------------------

ScholarFlux defines 18 universal academic fields through the ``AcademicFieldMap``:

.. code-block:: python

   from scholar_flux.api.normalization import AcademicFieldMap
   
   # View all universal fields
   universal_fields = AcademicFieldMap.model_fields.keys()
   print(list(universal_fields))

**Core Identifiers:**
- ``provider_name``: Source database (plos, arxiv, crossref, etc.)
- ``doi``: Digital Object Identifier
- ``url``: Direct link to article
- ``record_id``: Provider-specific identifier

**Bibliographic Metadata:**
- ``title``: Article title
- ``abstract``: Article abstract/summary
- ``authors``: Author list

**Publication Metadata:**
- ``journal``: Journal name
- ``publisher``: Publisher name
- ``year``: Publication year
- ``date_published``: Full publication date
- ``date_created``: Record creation date

**Content Classification:**
- ``keywords``: Article keywords
- ``subjects``: Subject classifications
- ``full_text``: Full text availability

**Metrics:**
- ``citation_count``: Number of citations

**Access Information:**
- ``open_access``: Open access status
- ``license``: License type

**Document Metadata:**
- ``record_type``: Article type
- ``language``: Primary language

Field Map Architecture
----------------------

Each provider has a custom field map defining how to extract universal fields:

.. code-block:: python

   from scholar_flux.api.providers import provider_registry
   
   # Get PLOS field map
   plos_config = provider_registry.get('plos')
   field_map = plos_config.field_map
   
   # View field mappings
   print(field_map.fields)
   # {'provider_name': 'plos',
   #  'title': 'title_display',
   #  'doi': 'id',
   #  'authors': 'author_display',
   #  'abstract': 'abstract',
   #  'year': 'publication_date',
   #  ...}

**How it works:**
1. Field map defines mapping from API-specific fields to universal fields
2. ``normalize()`` applies the field map to transform records
3. Missing fields are set to ``None`` (not excluded)
4. Provider-specific fields are preserved as additional columns

Nested Field Access
-------------------

Field maps support dot notation for nested fields:

.. code-block:: python

   from scholar_flux.api.normalization import AcademicFieldMap
   
   # Define nested field paths
   field_map = AcademicFieldMap(
       provider_name="custom_api",
       title="article.metadata.title",
       authors="article.authors.name",
       doi="identifiers.doi",
       year="publication.year"
   )
   
   # Sample nested record
   record = {
       'article': {
           'metadata': {'title': 'Deep Learning'},
           'authors': [
               {'name': 'Smith, J'},
               {'name': 'Doe, A'}
           ]
       },
       'identifiers': {'doi': '10.1234/example'},
       'publication': {'year': 2024}
   }
   
   # Normalize
   normalized = field_map.normalize_record(record)
   
   print(normalized)
   # {'provider_name': 'custom_api',
   #  'title': 'Deep Learning',
   #  'authors': ['Smith, J', 'Doe, A'],
   #  'doi': '10.1234/example',
   #  'year': 2024,
   #  ...}

**Nested field features:**
- Uses dot notation (``parent.child.field``)
- Automatically traverses lists (``authors.name`` extracts from all authors)
- Returns ``None`` if path doesn't exist
- Handles mixed types gracefully

Fallback Paths
--------------

Some providers store the same data in different locations. Use fallback paths:

.. code-block:: python

   from scholar_flux.api.normalization import AcademicFieldMap
   
   # Define fallback paths as a list
   field_map = AcademicFieldMap(
       provider_name="custom_api",
       # Try primary_title first, then fallback_title, then title
       title=["primary_title", "fallback_title", "title"],
       # Try detailed abstract first, then summary
       abstract=["detailed_abstract", "summary"]
   )
   
   # Record with fallback field
   record = {
       'fallback_title': 'Machine Learning Advances',
       'summary': 'A comprehensive review...'
   }
   
   normalized = field_map.normalize_record(record)
   
   print(normalized['title'])    # 'Machine Learning Advances'
   print(normalized['abstract']) # 'A comprehensive review...'

**Fallback behavior:**
- Tries paths in order (left to right)
- Uses first non-None value found
- Sets to ``None`` if all paths fail
- Defined per-field (each field can have different fallbacks)

**Example from PubMed field map:**

.. code-block:: python

   # scholar_flux/api/normalization/pubmed_field_map.py
   field_map = AcademicFieldMap(
       provider_name="pubmed",
       # Try with #text attribute first, fallback to field directly
       title=[
           "MedlineCitation.Article.ArticleTitle.#text",
           "MedlineCitation.Article.ArticleTitle"
       ],
       abstract=[
           "MedlineCitation.Article.Abstract.AbstractText.#text",
           "MedlineCitation.Article.Abstract.AbstractText"
       ],
       # ... other fields
   )

This handles cases where XML parsing produces different structures depending on content.

Advanced Normalization
======================

Including Metadata in Normalized Records
-----------------------------------------

Include query/provider metadata alongside normalized records:

.. code-block:: python

   from scholar_flux import SearchCoordinator
   
   coordinator = SearchCoordinator(query="CRISPR", provider_name="plos")
   results = coordinator.search_pages(pages=range(1, 3))
   
   # Default: includes provider_name and page
   normalized = results.filter().normalize()
   print(normalized[0].keys())
   # dict_keys(['provider_name', 'page', 'title', 'doi', ...])
   
   # Include only provider_name
   normalized = results.filter().normalize(include={'provider_name'})
   
   # Include all metadata
   normalized = results.filter().normalize(include={'query', 'provider_name', 'page'})
   print(normalized[0])
   # {'query': 'CRISPR',
   #  'provider_name': 'plos',
   #  'page': 1,
   #  'title': '...',
   #  'doi': '...',
   #  ...}

**Available metadata fields:**
- ``query``: Search query used
- ``provider_name``: Data source
- ``page``: Page number

Controlling Normalization Updates
----------------------------------

Control when normalized records are cached:

.. code-block:: python

   from scholar_flux import SearchCoordinator
   
   coordinator = SearchCoordinator(query="test", provider_name="plos")
   result = coordinator.search(page=1)
   
   # First normalization - computes and caches
   normalized1 = result.normalize(update_records=True)
   assert result.response_result.normalized_records == normalized1
   
   # Second normalization - uses cached results
   normalized2 = result.normalize()
   assert normalized1 is result.response_result.normalized_records
   
   # Force recomputation without caching
   normalized3 = result.normalize(update_records=False)
   # Recomputes but doesn't update .normalized_records

**update_records parameter:**
- ``None`` (default): Update cache if not already set
- ``True``: Always update cache
- ``False``: Never update cache (recompute each time)

Error Handling
--------------

Normalization handles errors gracefully:

.. code-block:: python

   from scholar_flux import SearchCoordinator
   from scholar_flux.exceptions import RecordNormalizationException
   
   coordinator = SearchCoordinator(query="test", provider_name="unknown_provider")
   result = coordinator.search(page=1)
   
   # Graceful failure - returns empty list
   normalized = result.normalize(raise_on_error=False)
   print(normalized)  # []
   
   # Strict failure - raises exception
   try:
       normalized = result.normalize(raise_on_error=True)
   except RecordNormalizationException as e:
       print(f"Normalization failed: {e}")

**Error scenarios:**
- Provider not in registry → ``RecordNormalizationException``
- No field map defined → ``RecordNormalizationException``
- ErrorResponse/NonResponse → Returns ``[]`` if ``raise_on_error=False``
- Missing response result → ``RecordNormalizationException``

Working with DataFrames
=======================

Building ML-Ready Datasets
---------------------------

Convert normalized records directly to pandas DataFrames:

.. code-block:: python

   from scholar_flux import SearchCoordinator, MultiSearchCoordinator
   from scholar_flux.api.normalization import AcademicFieldMap
   import pandas as pd
   
   # Multi-provider search
   multi = MultiSearchCoordinator()
   multi.add_coordinators([
       SearchCoordinator(query="machine learning", provider_name='plos'),
       SearchCoordinator(query="machine learning", provider_name='crossref'),
       SearchCoordinator(query="machine learning", provider_name='openalex')
   ])
   
   results = multi.search_pages(pages=range(1, 11))
   
   # Normalize with metadata
   normalized = results.filter().normalize(include={'provider_name', 'page'})
   
   # Convert to DataFrame
   df = pd.DataFrame(normalized)
   
   # Analyze field coverage
   universal_fields = list(AcademicFieldMap.model_fields.keys())
   coverage = df[universal_fields].notna().mean() * 100
   
   print(coverage.sort_values(ascending=False))
   # provider_name    100.0
   # title            100.0
   # doi               95.2
   # authors           87.3
   # abstract          76.8
   # year              98.1
   # ...

Analyzing Provider Coverage
----------------------------

Compare which fields are available across providers:

.. code-block:: python

   import pandas as pd
   from scholar_flux.api.normalization import AcademicFieldMap
   
   # Assume df is a DataFrame from normalized multi-provider results
   universal_fields = list(AcademicFieldMap.model_fields.keys())
   
   # Count records per provider with each field
   provider_field_counts = df.groupby('provider_name')[universal_fields].count()
   
   # Find fields available in 3+ providers
   min_providers = 3
   common_fields = (provider_field_counts > 0).sum() >= min_providers
   common_field_list = common_fields[common_fields].index.tolist()
   
   print("Fields common across providers:")
   print(common_field_list)
   
   print("\nRecord counts per provider:")
   print(provider_field_counts[common_field_list])

**Example output:**

.. code-block:: text

   Fields common across providers:
   ['provider_name', 'doi', 'url', 'record_id', 'title', 'abstract', 
    'authors', 'journal', 'publisher', 'year', 'date_published', 
    'date_created', 'subjects', 'record_type']
   
   Record counts per provider:
                      doi  url  record_id  title  abstract  ...
   provider_name                                             ...
   arxiv              0   50      50       50       50      ...
   crossref          50   50      50       50        3      ...
   openalex          40   49      50       50        0      ...
   plos             100    0     100      100       99      ...

Creating Custom Field Maps
==========================

Basic Custom Field Map
-----------------------

Create a custom field map for a new provider:

.. code-block:: python

   from scholar_flux.api.normalization import AcademicFieldMap
   
   # Define mapping for custom provider
   custom_map = AcademicFieldMap(
       provider_name="custom_api",
       # Direct field mappings
       title="article_title",
       doi="digital_identifier",
       abstract="summary_text",
       # Nested field mappings
       authors="contributors.author_name",
       journal="publication_venue.name",
       year="published_year",
       # API-specific fields to preserve
       api_specific_fields={
           'internal_id': 'record_number',
           'subject_codes': 'classification_codes',
           'access_level': 'availability_status'
       }
   )
   
   # Test with sample record
   sample = {
       'article_title': 'Deep Learning Methods',
       'digital_identifier': '10.1234/example.2024',
       'summary_text': 'A comprehensive review...',
       'contributors': [
           {'author_name': 'Smith, J'},
           {'author_name': 'Doe, A'}
       ],
       'publication_venue': {'name': 'Nature'},
       'published_year': 2024,
       'record_number': 12345,
       'classification_codes': ['CS.AI', 'STAT.ML']
   }
   
   normalized = custom_map.normalize_record(sample)
   
   print(normalized)
   # {'provider_name': 'custom_api',
   #  'title': 'Deep Learning Methods',
   #  'doi': '10.1234/example.2024',
   #  'abstract': 'A comprehensive review...',
   #  'authors': ['Smith, J', 'Doe, A'],
   #  'journal': 'Nature',
   #  'year': 2024,
   #  'internal_id': 12345,
   #  'subject_codes': ['CS.AI', 'STAT.ML'],
   #  ...}

Integrating Custom Maps with Providers
---------------------------------------

Add custom field maps to provider configurations:

.. code-block:: python

   from scholar_flux.api import ProviderConfig, APIParameterMap, SearchCoordinator
   from scholar_flux.api.providers import provider_registry
   from scholar_flux.api.normalization import AcademicFieldMap
   
   # Create custom field map
   field_map = AcademicFieldMap(
       provider_name="guardian",
       title="webTitle",
       url="webUrl",
       date_published="webPublicationDate",
       authors="tags.contributor",
       abstract="fields.trailText",
       api_specific_fields={
           'section_name': 'sectionName',
           'word_count': 'fields.wordcount'
       }
   )
   
   # Create provider config with field map
   guardian_config = ProviderConfig(
       provider_name='guardian',
       base_url='https://content.guardianapis.com/search',
       parameter_map=APIParameterMap(
           query='q',
           start='page',
           records_per_page='page-size',
           api_key_parameter='api-key',
           auto_calculate_page=False,
           api_key_required=True
       ),
       field_map=field_map,  # Add custom field map
       records_per_page=10,
       request_delay=6,
       api_key_env_var='GUARDIAN_API_KEY'
   )
   
   # Add to registry
   provider_registry.add(guardian_config)
   
   # Use with automatic normalization
   coordinator = SearchCoordinator(query="climate change", provider_name='guardian')
   result = coordinator.search(page=1, normalize_records=True)
   
   # Access normalized records
   normalized = result.response_result.normalized_records

Processing Complex Structures
------------------------------

For complex nested structures, combine with data processors:

.. code-block:: python

   from scholar_flux import SearchCoordinator
   from scholar_flux.data import RecursiveDataProcessor
   from scholar_flux.api.normalization import AcademicFieldMap
   
   # RecursiveDataProcessor flattens nested structures
   processor = RecursiveDataProcessor()
   
   coordinator = SearchCoordinator(
       query="test",
       provider_name="complex_api",
       processor=processor  # Flattens before normalization
   )
   
   # Field map works on flattened structure
   field_map = AcademicFieldMap(
       provider_name="complex_api",
       title="article.metadata.title",  # Will be flattened to "article.metadata.title"
       authors="authors.name"            # Auto-extracts from flattened author list
   )

Best Practices
==============

Performance Optimization
------------------------

**1. Cache normalized records when possible:**

.. code-block:: python

   # Good - normalizes once, caches result
   result = coordinator.search(page=1, normalize_records=True)
   normalized = result.response_result.normalized_records  # Uses cache
   
   # Less efficient - recomputes each time
   result = coordinator.search(page=1)
   normalized1 = result.normalize()
   normalized2 = result.normalize()  # Recomputes

**2. Batch normalization with SearchResultList:**

.. code-block:: python

   # Good - normalizes all at once
   results = coordinator.search_pages(pages=range(1, 100))
   normalized = results.filter().normalize()
   
   # Less efficient - normalizes one at a time
   normalized = []
   for result in results.filter():
       normalized.extend(result.normalize())

**3. Use filter() before normalize():**

.. code-block:: python

   # Good - only normalizes successful responses
   normalized = results.filter().normalize()
   
   # Less efficient - tries to normalize errors
   normalized = results.normalize(raise_on_error=False)

Memory Management
-----------------

For large datasets, process in chunks:

.. code-block:: python

   import pandas as pd
   from scholar_flux import SearchCoordinator
   
   coordinator = SearchCoordinator(query="machine learning", provider_name="plos")
   
   # Process 100 pages in chunks of 10
   all_records = []
   for start in range(1, 101, 10):
       chunk_pages = range(start, min(start + 10, 101))
       results = coordinator.search_pages(pages=chunk_pages)
       normalized = results.filter().normalize()
       all_records.extend(normalized)
       
       # Optional: Save intermediate results
       if start % 50 == 1:
           pd.DataFrame(all_records).to_parquet(f'checkpoint_{start}.parquet')
   
   # Final DataFrame
   df = pd.DataFrame(all_records)

Data Quality Checks
-------------------

Validate normalized data before analysis:

.. code-block:: python

   import pandas as pd
   from scholar_flux.api.normalization import AcademicFieldMap
   
   # Get normalized records
   normalized = results.filter().normalize(include={'provider_name'})
   df = pd.DataFrame(normalized)
   
   # Check for required fields
   required_fields = ['provider_name', 'title', 'doi']
   missing_required = df[required_fields].isna().sum()
   print("Missing required fields:")
   print(missing_required[missing_required > 0])
   
   # Check universal field coverage
   universal_fields = list(AcademicFieldMap.model_fields.keys())
   coverage = df[universal_fields].notna().mean() * 100
   print("\nField coverage:")
   print(coverage[coverage > 0].sort_values(ascending=False))
   
   # Check for duplicates by DOI
   duplicates = df[df.duplicated(subset=['doi'], keep=False)]
   print(f"\nDuplicate records: {len(duplicates)}")

Next Steps
==========

Congratulations! You now understand ScholarFlux's schema normalization system. You can:

✅ Normalize multi-provider search results with one method call
✅ Build ML-ready pandas DataFrames from heterogeneous APIs
✅ Create custom field mappings for new providers
✅ Use fallback paths for flexible field resolution
✅ Optimize normalization performance for large datasets

Real-World Use Cases
====================

Systematic Literature Review
-----------------------------

Build evidence tables for systematic reviews:

.. code-block:: python

   from scholar_flux import MultiSearchCoordinator, SearchCoordinator
   import pandas as pd
   
   # Search all major databases for a medical topic
   multi = MultiSearchCoordinator()
   multi.add_coordinators([
       SearchCoordinator(query="COVID-19 vaccine efficacy", provider_name=p)
       for p in ['pubmed', 'plos', 'crossref']
   ])
   
   results = multi.search_pages(pages=range(1, 51))  # 150 pages
   df = pd.DataFrame(results.filter().normalize(include={'provider_name'}))
   
   # Create evidence table
   evidence = df[[
       'title', 'authors', 'journal', 'year', 'doi', 'abstract'
   ]].copy()
   
   # Add PRISMA screening columns
   evidence['include_abstract'] = None
   evidence['include_fulltext'] = None
   evidence['exclusion_reason'] = None
   
   # Export for manual review
   evidence.to_excel('covid_vaccine_evidence.xlsx', index=False)

Citation Network Analysis
-------------------------

Build citation graphs from normalized data:

.. code-block:: python

   from scholar_flux import SearchCoordinator
   import pandas as pd
   import networkx as nx
   
   # Retrieve papers with citation data
   coordinator = SearchCoordinator(query="neural networks", provider_name="openalex")
   results = coordinator.search_pages(pages=range(1, 101))
   df = pd.DataFrame(results.filter().normalize())
   
   # Filter papers with citations
   cited = df[df['citation_count'] > 0].copy()
   
   # Build citation network (simplified)
   G = nx.DiGraph()
   
   for _, row in cited.iterrows():
       if pd.notna(row['doi']):
           G.add_node(row['doi'], 
                      title=row['title'],
                      year=row['year'],
                      citations=row['citation_count'])
   
   # Analyze network
   print(f"Nodes: {G.number_of_nodes()}")
   if G.number_of_nodes() > 0:
       most_cited = max(G.nodes(data=True), key=lambda x: x[1].get('citations', 0))
       print(f"Most cited: {most_cited[1]['title']} ({most_cited[1]['citations']} citations)")

Meta-Analysis Pipeline
----------------------

Extract data for meta-analysis:

.. code-block:: python

   from scholar_flux import SearchCoordinator
   import pandas as pd
   import re
   
   # Search for clinical trials
   coordinator = SearchCoordinator(
       query="randomized controlled trial depression treatment",
       provider_name="pubmed"
   )
   
   results = coordinator.search_pages(pages=range(1, 21))
   df = pd.DataFrame(results.filter().normalize())
   
   # Extract sample sizes from abstracts (simplified)
   def extract_n(abstract):
       if pd.isna(abstract):
           return None
       match = re.search(r'[Nn]=(\d+)', str(abstract))
       return int(match.group(1)) if match else None
   
   df['sample_size'] = df['abstract'].apply(extract_n)
   
   # Filter for meta-analysis
   meta_data = df[df['sample_size'].notna()].copy()
   
   # Export for RevMan or comprehensive meta-analysis
   meta_data[['title', 'authors', 'year', 'journal', 'sample_size', 'doi']].to_csv(
       'depression_rct_meta.csv',
       index=False
   )


Getting Help
------------

If you encounter issues with normalization:

1. **Check field availability**: Print ``result.data[0].keys()`` to see actual field names
2. **Verify provider has field map**: ``provider_registry[provider_name].field_map``
3. **Test with sample record**: Use ``field_map.normalize_record(sample)`` to debug
4. **Search existing issues**: https://github.com/SammieH21/scholar-flux/issues
5. **Ask for help**: Open a new issue or email scholar.flux@gmail.com

When reporting normalization issues, include:

- Provider name
- Sample raw record (``result.data[0]``)
- Expected normalized fields
- Actual normalized output
- ScholarFlux version



Where to Go Next
----------------

**Related Tutorials:**

- :doc:`multi_provider_search` - Concurrent multi-provider orchestration (pairs with normalization)
- :doc:`custom_providers` - Add new providers with custom field maps
- :doc:`advanced_workflows` - Multi-step normalization pipelines

**Advanced Topics:**

- :doc:`caching_strategies` - Cache normalized results for production
- :doc:`production_deployment` - Deploy normalized data pipelines

**Reference:**

- :class:`~scholar_flux.api.normalization.AcademicFieldMap` - Full field map API
- :class:`~scholar_flux.api.normalization.NormalizingFieldMap` - Base normalization class
- :class:`~scholar_flux.api.models.SearchResultList` - Batch normalization methods

