========================
Multi-Provider Search
========================

ScholarFlux enables concurrent searches across multiple academic databases with automatic rate limiting, shared thread management, and unified result handling. This guide demonstrates how to query multiple providers simultaneously and work with aggregated results.

.. contents:: Table of Contents
   :local:
   :depth: 2

Prerequisites
-------------

- Complete :doc:`getting_started` to understand SearchCoordinator basics
- Understand :doc:`response_handling_patterns` for SearchResultList error handling
- Basic familiarity with concurrent programming concepts

Overview
========

Why Multi-Provider Search?
---------------------------

Comprehensive literature reviews require querying multiple databases. The traditional sequential approach is time-consuming:

.. code-block:: python

   from scholar_flux import SearchCoordinator
   
   # Create coordinators
   plos = SearchCoordinator(query="machine learning", provider_name='plos')
   arxiv = SearchCoordinator(query="machine learning", provider_name='arxiv')
   crossref = SearchCoordinator(query="machine learning", provider_name='crossref')
   
   # Sequential: query each provider one at a time
   # 6.1 second delay × 8 waits = 48.8 seconds
   plos_results = plos.search_pages(range(1, 10))
   
   # 4 second delay × 8 waits = 32 seconds
   arxiv_results = arxiv.search_pages(range(1, 10))
   
   # 1 second delay × 8 waits = 8 seconds
   crossref_results = crossref.search_pages(range(1, 10))
   
   # Total time: ~89 seconds

**ScholarFlux's concurrent approach:**

.. code-block:: python

   from scholar_flux import MultiSearchCoordinator
   
   # Add all coordinators to multi-search
   multi = MultiSearchCoordinator()
   multi.add_coordinators([plos, arxiv, crossref])
   
   # Concurrent: all providers query simultaneously
   results = multi.search_pages(pages=range(1, 10))
   # Total time: ~49 seconds (limited by most rate-limited provider: PLOS)

For 3 providers × 9 pages, ScholarFlux is **~1.8x faster** through concurrent execution with automatic rate limit coordination.

Key Features
------------

- **Thread-per-provider execution**: Each provider runs in its own thread
- **Shared rate limiters**: Multiple queries to the same provider coordinate automatically
- **Unified result handling**: `SearchResultList` provides filtering, aggregation, and normalization
- **Graceful error handling**: Individual provider failures don't stop the entire search

Quick Start
===========

Basic Example: Four Providers
------------------------------

Query four providers concurrently and retrieve results:

.. code-block:: python

   from scholar_flux import SearchCoordinator, MultiSearchCoordinator
   
   # Create multi-coordinator
   multi = MultiSearchCoordinator()
   
   # Add coordinators for each provider
   multi.add_coordinators([
       SearchCoordinator(query="machine learning", provider_name='plos'),
       SearchCoordinator(query="machine learning", provider_name='arxiv'),
       SearchCoordinator(query="machine learning", provider_name='openalex'),
       SearchCoordinator(query="machine learning", provider_name='crossref')
   ])
   
   # Execute concurrent search across 10 pages per provider
   results = multi.search_pages(pages=range(1, 11))
   
   # Check results
   print(f"Total results: {len(results)}")  # 40 (4 providers × 10 pages)
   print(f"Successful: {len(results.filter())}/{len(results)}")

**Expected output:**

.. code-block:: text

   Total results: 40
   Successful: 40/40

What Just Happened?
^^^^^^^^^^^^^^^^^^^

1. **Created coordinators**: Each `SearchCoordinator` configures a provider with query settings
2. **Concurrent execution**: `search_pages` spawned 4 threads (one per provider)
3. **Rate limiting**: Each thread respected its provider's rate limits automatically
4. **Result collection**: All 40 responses (4 providers × 10 pages) returned as `SearchResultList`

Complete Example: Normalized Data
----------------------------------

Retrieve records from multiple providers and convert to a pandas DataFrame:

.. code-block:: python

   import pandas as pd
   from scholar_flux import SearchCoordinator, MultiSearchCoordinator
   
   # Create and configure multi-coordinator
   multi = MultiSearchCoordinator()
   multi.add_coordinators([
       SearchCoordinator(query="machine learning", provider_name=provider)
       for provider in ['plos', 'arxiv', 'openalex', 'crossref']
   ])
   
   # Retrieve 10 pages from each provider
   results = multi.search_pages(pages=range(1, 11))
   
   # Filter successful responses and normalize to universal schema
   normalized_records = results.filter().normalize()
   
   # Convert to DataFrame for analysis
   df = pd.DataFrame(normalized_records)
   print(f"Total records: {df.shape[0]}")
   print(f"Columns: {list(df.columns[:5])}...")  # First 5 columns

**Expected output:**

.. code-block:: text

   Total records: 1250
   Columns: ['provider_name', 'doi', 'url', 'record_id', 'title']...

**Record counts by provider:**

- PLOS: 50 records/page × 10 pages = 500 records
- arXiv: 25 records/page × 10 pages = 250 records  
- OpenAlex: 25 records/page × 10 pages = 250 records
- Crossref: 25 records/page × 10 pages = 250 records
- **Total: 1,250 records**

Understanding Multi-Provider Architecture
==========================================

Thread-Per-Provider Model
--------------------------

ScholarFlux uses a sophisticated threading architecture:

.. code-block:: text

   MultiSearchCoordinator
   ├── Thread 1: PLOS
   │   ├── Page 1 request → wait 6.1s
   │   ├── Page 2 request → wait 6.1s
   │   └── Page 3 request
   ├── Thread 2: arXiv
   │   ├── Page 1 request → wait 4.0s
   │   ├── Page 2 request → wait 4.0s
   │   └── Page 3 request
   ├── Thread 3: OpenAlex (similar pattern)
   └── Thread 4: Crossref (similar pattern)

**Key characteristics:**

- Each provider runs in its own thread for true parallelism
- Results stream back as they complete (no waiting for all)
- Memory-efficient generator-based design
- Provider failures are isolated

Shared Rate Limiting
--------------------

When multiple queries target the same provider, they automatically share a rate limiter:

.. code-block:: python

   multi = MultiSearchCoordinator()
   multi.add_coordinators([
       SearchCoordinator(query="gene therapy", provider_name='plos'),
       SearchCoordinator(query="CRISPR", provider_name='plos'),
       SearchCoordinator(query="immunotherapy", provider_name='plos')
   ])
   
   # All three queries share PLOS's rate limiter (6.1s between requests)
   # Requests are automatically coordinated: 
   #   Query 1, Page 1 at t=0
   #   Query 2, Page 1 at t=6.1
   #   Query 3, Page 1 at t=12.2
   results = multi.search_pages(pages=range(1, 5))

**Without shared rate limiting:** Multiple queries could violate provider rate limits and trigger IP bans.

**With shared rate limiting:** ScholarFlux coordinates all requests to the same provider, ensuring compliance.

Working with Results
====================

SearchResultList Basics
-----------------------

The `SearchResultList` class provides methods for filtering, aggregating, and normalizing multi-provider results:

.. code-block:: python

   # After executing a multi-provider search
   results = multi.search_pages(pages=range(1, 6))
   
   # Check total results
   print(f"Total results: {len(results)}")
   
   # Access individual SearchResult
   first_result = results[0]
   print(f"Provider: {first_result.provider_name}")
   print(f"Page: {first_result.page}")
   print(f"Record count: {first_result.record_count}")
   
   # Check if result is successful
   if first_result:  # ProcessedResponse is truthy
       print(f"Success! Retrieved {len(first_result.data)} records")
   else:
       print(f"Failed: {first_result.error} - {first_result.message}")

Filtering Successful Responses
-------------------------------

Remove failed requests to work only with successful data:

.. code-block:: python

   # Filter keeps only ProcessedResponse (successful) results
   successful_results = results.filter()
   print(f"Success rate: {len(successful_results)}/{len(results)}")
   
   # Invert filter to get only failures
   failed_results = results.filter(invert=True)
   for failure in failed_results:
       print(f"Failed: {failure.provider_name} page {failure.page}")
       print(f"Error: {failure.error} - {failure.message}")

Aggregating Records
-------------------

Combine all records from multiple providers into a single list:

.. code-block:: python

   # Method 1: Use .join() to get all processed records
   all_records = results.filter().join()
   print(f"Total records: {len(all_records)}")
   
   # Method 2: Include metadata fields (provider_name, page, query)
   records_with_metadata = results.filter().join(
       include={'provider_name', 'page'}
   )
   
   # Each record now has provider_name and page
   print(records_with_metadata[0].keys())
   # dict_keys(['title', 'abstract', 'doi', ..., 'provider_name', 'page'])

Normalizing Fields
------------------

ScholarFlux normalizes provider-specific fields to a universal schema. For detailed information on field mapping, see :doc:`schema_normalization`.

**Quick normalization:**

.. code-block:: python

   # Normalize all records to universal field names
   normalized_records = results.filter().normalize()
   
   # Each record now has standardized field names
   for record in normalized_records[:3]:
       print(f"Title: {record.get('title')}")
       print(f"DOI: {record.get('doi')}")
       print(f"Authors: {record.get('authors')}")
       print(f"Provider: {record.get('provider_name')}")
       print("---")

**Include metadata during normalization:**

.. code-block:: python

   # Add provider_name, page, and query to each normalized record
   normalized = results.filter().normalize(
       include={'provider_name', 'page', 'query'}
   )

**Alternative: Normalize during search:**

.. code-block:: python

   # Normalize records automatically during retrieval
   results = multi.search_pages(pages=range(1, 3), normalize_records=True)
   
   # Access normalized records directly
   for result in results.filter():
       if result.normalized_records:
           for record in result.normalized_records:
               print(record['title'])

.. seealso::
   For detailed information on field normalization, provider-specific mappings, and custom field maps, see :doc:`schema_normalization`.

Rate Limiting
=============

Default Rate Limits
-------------------

ScholarFlux implements conservative rate limits for each provider:

+------------------+------------------------+
| Provider         | Delay Between Requests |
+==================+========================+
| PLOS             | 6.1 seconds            |
+------------------+------------------------+
| arXiv            | 4.0 seconds            |
+------------------+------------------------+
| OpenAlex         | 6.0 seconds            |
+------------------+------------------------+
| PubMed           | 2.0 seconds            |
+------------------+------------------------+
| Crossref         | 1.0 seconds            |
+------------------+------------------------+
| CORE             | 6.0 seconds            |
+------------------+------------------------+
| Springer Nature  | 2.0 seconds            |
+------------------+------------------------+

**Rate limiting happens automatically.** You don't need to configure anything for standard usage.

Inspecting Rate Limits
-----------------------

View current rate limiter settings:

.. code-block:: python

   from scholar_flux.api.rate_limiting import threaded_rate_limiter_registry
   
   # View all provider rate limiters
   for provider, limiter in threaded_rate_limiter_registry.items():
       print(f"{provider}: {limiter.min_interval}s between requests")

.. warning::
   Only modify rate limits if you have explicit permission from the provider, institutional access, or documentation confirming higher limits. Violating rate limits may result in IP bans.

Real-World Example: Systematic Literature Review
=================================================

This example demonstrates a comprehensive search across six providers for a systematic review:

.. code-block:: python

   import pandas as pd
   from scholar_flux import SearchCoordinator, MultiSearchCoordinator
   
   # Configure search across all major providers
   providers = ['pubmed', 'plos', 'arxiv', 'crossref', 'openalex', 'core']
   
   multi = MultiSearchCoordinator()
   multi.add_coordinators([
       SearchCoordinator(
           query="cancer immunotherapy clinical trials",
           provider_name=provider
       )
       for provider in providers
   ])
   
   # Retrieve 20 pages per provider (120 total requests)
   print("Starting systematic search...")
   results = multi.search_pages(pages=range(1, 21))
   
   # Check success rate
   successful = results.filter()
   print(f"Retrieved: {len(successful)}/{len(results)} pages successfully")
   
   # Normalize and deduplicate by DOI
   normalized_records = successful.normalize(include={'provider_name'})
   df = pd.DataFrame(normalized_records)
   
   # Deduplicate by DOI (keep first occurrence)
   df_dedup = df.drop_duplicates(subset=['doi'], keep='first')
   
   # Analysis
   print(f"\nResults Summary:")
   print(f"Total records: {len(df)}")
   print(f"Unique records (after deduplication): {len(df_dedup)}")
   print(f"\nCoverage by provider:")
   print(df.groupby('provider_name').size())
   
   # Export for analysis
   df_dedup.to_csv('systematic_review_results.csv', index=False)
   print("\nExported to systematic_review_results.csv")

**Expected output:**

.. code-block:: text

   Starting systematic search...
   Retrieved: 118/120 pages successfully
   
   Results Summary:
   Total records: 2,450
   Unique records (after deduplication): 1,823
   
   Coverage by provider:
   provider_name
   arxiv         250
   core          400
   crossref      500
   openalex      500
   plos          400
   pubmed        400
   
   Exported to systematic_review_results.csv

Best Practices
==============

Query Design
------------

**DO:**

- Use specific, targeted queries
- Test queries on a single provider first before scaling
- Use Boolean operators when supported (``AND``, ``OR``, ``NOT``)
- Start with small page ranges for testing

**DON'T:**

- Use overly broad queries (e.g., "science" or "health")
- Request excessive pages (>100 per provider) without caching
- Ignore error responses without investigation
- Skip validation of results

Caching Strategy
----------------

Enable caching to minimize redundant API calls:

.. code-block:: python

   from scholar_flux import SearchCoordinator, DataCacheManager
   from scholar_flux.sessions import CachedSessionManager
   
   # HTTP response caching (session-level)
   session_manager = CachedSessionManager(backend='redis')
   
   # Result caching (processed data)
   cache_manager = DataCacheManager.with_storage('redis', 'localhost:6379')
   
   # Apply to coordinators
   coordinators = [
       SearchCoordinator(
           query="machine learning",
           provider_name=provider,
           session=session_manager.configure_session(),
           cache_manager=cache_manager
       )
       for provider in ['plos', 'arxiv', 'crossref']
   ]

Resource Management
-------------------

**Memory:**

- Process large result sets in batches
- Use ``.filter().join()`` to aggregate efficiently
- Clear large result lists when no longer needed

**Network:**

- Enable caching to reduce API calls
- Respect rate limits (don't customize without permission)
- Handle provider failures gracefully with error checking

**Time estimates:**

- 4 providers × 10 pages: ~2-3 minutes
- 4 providers × 50 pages: ~10-15 minutes
- 6 providers × 100 pages: ~30-40 minutes

Troubleshooting
===============

"No coordinators registered" Warning
-------------------------------------

This occurs when searching before adding coordinators:

.. code-block:: python

   multi = MultiSearchCoordinator()
   results = multi.search(page=1)  # Warning: returns empty list
   
   # Fix: add coordinators first
   multi.add_coordinators([
       SearchCoordinator(query="AI", provider_name='plos')
   ])
   results = multi.search(page=1)  # Now works

Memory Issues with Large Searches
----------------------------------

Process results in batches instead of all at once:

.. code-block:: python

   # Instead of: pages=range(1, 200)
   batch_size = 20
   all_data = []
   
   for batch_start in range(1, 200, batch_size):
       batch_end = min(batch_start + batch_size, 200)
       batch_pages = range(batch_start, batch_end)
       
       results = multi.search_pages(pages=batch_pages)
       batch_data = results.filter().join()
       all_data.extend(batch_data)
       
       # Clear memory
       del results
       print(f"Processed pages {batch_start}-{batch_end-1}")

Provider-Specific Failures
---------------------------

Investigate individual provider failures:

.. code-block:: python

   results = multi.search_pages(pages=range(1, 11))
   
   # Separate successes and failures
   successful = results.filter()
   failed = results.filter(invert=True)
   
   # Analyze failures
   if failed:
       print(f"{len(failed)} failures:")
       for failure in failed:
           print(f"  {failure.provider_name} page {failure.page}")
           print(f"  Error: {failure.error}")
           print(f"  Message: {failure.message}")

**Common failure causes:**

- API temporary downtime (retry later)
- Rate limit exceeded (check if limits were customized)
- Network connectivity issues
- Invalid API keys (for providers requiring authentication)

Next Steps
==========

**Related Guides:**

- :doc:`schema_normalization` - Detailed guide on field normalization and custom mappings
- :doc:`custom_providers` - Add new providers to ScholarFlux
- :doc:`advanced_workflows` - Multi-step retrieval for complex APIs (e.g., PubMed)

**Advanced Topics:**

- :doc:`caching_strategies` - Production caching patterns with Redis, MongoDB, SQLAlchemy
- :doc:`production_deployment` - Deploy ScholarFlux at scale with Docker and Kubernetes

**API Reference:**

- :class:`scholar_flux.api.MultiSearchCoordinator` - Complete API documentation
- :class:`scholar_flux.api.SearchCoordinator` - Single-provider coordinator reference
- :class:`scholar_flux.api.models.SearchResultList` - Result list methods and properties
- :class:`scholar_flux.api.models.SearchResult` - Individual result structure
