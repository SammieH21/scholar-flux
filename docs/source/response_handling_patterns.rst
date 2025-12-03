Response Handling and Error Patterns
====================================

This guide covers essential response handling patterns for working with ScholarFlux.

.. contents:: Table of Contents
   :local:
   :depth: 2

Prerequisites
-------------

- Complete the :doc:`getting_started` tutorial
- Understand basic search patterns with ``SearchCoordinator``

Response Access Patterns
=========================

ScholarFlux provides two methods for executing searches:

search_page() - Recommended
---------------------------

Returns SearchResult container with safe attribute access. Returns ``None`` instead of raising errors when accessing attributes on failed requests.

.. code-block:: python

   from scholar_flux import SearchCoordinator
   
   coordinator = SearchCoordinator(
       query="machine learning",
       provider_name="plos"
   )
   
   result = coordinator.search_page(page=1)
   
   if result:
       # Success - ProcessedResponse
       print(f"Found {len(result.data)} records")
       print(result.data)
   else:
       # Failure - ErrorResponse, NonResponse, or None
       # Safe to access - returns None if unavailable
       print(f"Error: {result.error} - {result.message}")
       print(f"Context: {result.query} on {result.provider_name}")

search() - Direct Access
------------------------

Returns response directly (ProcessedResponse, ErrorResponse, NonResponse, or None). Requires more careful error handling.

.. code-block:: python

   response = coordinator.search(page=1)
   
   if response:
       # Success - ProcessedResponse
       print(response.data)
   elif response is None:
       # Unexpected error - check logs
       print("Unexpected error during search.")
   else:
       # ErrorResponse or NonResponse
       print(f"Error: {response.error} - {response.message}")

.. note::
   ``search_page(page=1).response_result == search(page=1)``

.. tip::
   Use ``search_page()`` for safer error handling and better diagnostics.

Response Types in Detail
=========================

All responses are subclasses of :class:`~scholar_flux.api.models.APIResponse`.

ProcessedResponse (Success)
----------------------------

Returned when the API request succeeds and records are successfully processed.

.. code-block:: python

   from scholar_flux.api.models import ProcessedResponse
   
   result = coordinator.search_page(page=1)
   
   if isinstance(result.response_result, ProcessedResponse):
       print("✅ Success!")
       print(f"Records: {len(result.data)}")
       print(f"Metadata: {result.metadata}")

**Key attributes:** ``data`` (records), ``metadata`` (provider info), ``response`` (raw API response), ``normalized_records`` (if normalization performed)

ErrorResponse (HTTP Errors)
----------------------------

Returned when the API returns an HTTP error (4xx, 5xx status codes).

.. code-block:: python

   from scholar_flux.api.models import ErrorResponse
   
   if isinstance(result.response_result, ErrorResponse):
       print(f"❌ HTTP Error: {result.response_result.status_code}")
       print(f"Message: {result.response_result.message}")

**Common errors:**

- **400** - Bad request (invalid parameters)
- **401** - Unauthorized (invalid API key)
- **429** - Rate limit exceeded (auto-retried)
- **500** - Server error (auto-retried)
- **503** - Service unavailable (auto-retried)

NonResponse (Network/Config Errors)
------------------------------------

Returned when the request fails before receiving an HTTP response. Subclass of ErrorResponse.

.. code-block:: python

   from scholar_flux.api.models import NonResponse
   
   if isinstance(result.response_result, NonResponse):
       print(f"❌ Network/Config Error: {result.error}")
       print(f"Message: {result.message}")

**Common causes:** Network timeout, DNS failure, SSL errors, invalid provider name, missing configuration

.. tip::
   NonResponse errors indicate environmental issues (network, firewall) or configuration problems.

Error Handling Patterns
========================

Basic Boolean Check
-------------------

Simplest pattern for most use cases:

.. code-block:: python

   result = coordinator.search_page(page=1)
   
   if result:
       # Process successful results
       for record in result.data:
           print(record.get('title'))
   else:
       # Handle failure
       print(f"Search failed: {result.error}")

Type-Specific Handling
----------------------

Use ``isinstance()`` when you need to handle different errors differently:

.. code-block:: python

   from scholar_flux.api.models import ProcessedResponse, ErrorResponse, NonResponse
   
   result = coordinator.search_page(page=1)
   
   if isinstance(result.response_result, ProcessedResponse):
       # Success - process records
       process_records(result.data)
   
   elif isinstance(result.response_result, ErrorResponse):
       # HTTP error - check status code
       if result.response_result.status_code == 429:
           print("Rate limited (automatically retried)")
       elif result.response_result.status_code >= 500:
           print("Server error (automatically retried)")
       else:
           print(f"Client error: {result.response_result.status_code}")
   
   elif isinstance(result.response_result, NonResponse):
       # Network/config error
       print(f"Configuration issue: {result.message}")
   
   elif result.response_result is None:
       # Unexpected error
       print("Critical error - check logs")

Handling None Responses
-----------------------

When using ``search()`` directly, always check for ``None``:

.. code-block:: python

   response = coordinator.search(page=1)
   
   if response is None:
       # Exception was caught - check logs
       print("Critical error during search")
   elif response:
       # ProcessedResponse
       print("Success")
   else:
       # ErrorResponse or NonResponse
       print(f"Error: {response.error}")

.. warning::
   With ``search_page()``, accessing attributes on ``None`` returns ``None`` instead of raising errors. With ``search()``, explicitly check for ``None``.

Batch Error Handling
--------------------

Use ``search_pages()`` with built-in filtering for multiple pages:

.. code-block:: python

   from scholar_flux import SearchCoordinator
   
   coordinator = SearchCoordinator(query="CRISPR", provider_name="plos")
   
   # Retrieve pages 1-10
   results = coordinator.search_pages(pages=range(1, 11))
   
   # Filter successful results
   successful = results.filter()
   
   print(f"Success: {len(successful)}/{len(results)} pages")
   print(f"Total records: {successful.record_count}")
   
   # Check failures
   failed = results.filter(invert=True)
   if failed:
       print("\nFailed pages:")
       for result in failed:
           print(f"  Page {result.page}: {result.error}")
   
   # Process all successful records
   all_records = successful.join()
   print(f"\nCollected {len(all_records)} records")

.. tip::
   For multi-provider search patterns, see :doc:`multi_provider_search`.

Built-In Retry System
=====================

ScholarFlux automatically retries failed requests using :class:`~scholar_flux.api.RetryHandler`. No manual retry logic needed.

How Automatic Retries Work
---------------------------

**Automatically retried:**

- **429** - Rate limit exceeded
- **500** - Internal server error
- **503** - Service unavailable  
- **504** - Gateway timeout

**Never retried:**

- **400** - Bad request
- **401** - Unauthorized
- **403** - Forbidden
- **404** - Not found

.. code-block:: python

   coordinator = SearchCoordinator(query="test", provider_name="plos")
   
   # If provider returns 429/500/503/504, ScholarFlux automatically retries
   # with exponential backoff (up to 3 attempts by default)
   result = coordinator.search_page(page=1)

.. note::
   Retry system respects ``Retry-After`` headers when provided.

Configuring Retry Behavior
---------------------------

Customize the built-in retry handler:

.. code-block:: python

   coordinator = SearchCoordinator(query="test", provider_name="plos")
   
   # Access retry handler
   retry_handler = coordinator.retry_handler
   
   # Customize settings
   retry_handler.max_retries = 5              # Default: 3
   retry_handler.backoff_factor = 1.0         # Default: 0.5
   retry_handler.max_backoff = 180            # Default: 120s
   
   result = coordinator.search_page(page=1)

**Configuration parameters:**

+---------------------+----------+------------------------------------------------+
| Parameter           | Default  | Description                                    |
+=====================+==========+================================================+
| ``max_retries``     | 3        | Maximum retry attempts                         |
+---------------------+----------+------------------------------------------------+
| ``backoff_factor``  | 0.5      | Multiplier for exponential backoff             |
+---------------------+----------+------------------------------------------------+
| ``max_backoff``     | 120      | Maximum wait time (seconds)                    |
+---------------------+----------+------------------------------------------------+
| ``raise_on_error``  | False    | Raise exception on max retries exceeded        |
+---------------------+----------+------------------------------------------------+

Retry Delay Calculation
------------------------

Delays use exponential backoff:

.. code-block:: text

   delay = min(backoff_factor * (2 ** attempt_number), max_backoff)
   
   Default settings (backoff_factor=0.5, max_backoff=120):
   - Attempt 1: 0.5 * 2^1 = 1.0 seconds
   - Attempt 2: 0.5 * 2^2 = 2.0 seconds  
   - Attempt 3: 0.5 * 2^3 = 4.0 seconds

Provider ``Retry-After`` headers override this calculation.

Common Retry Configurations
---------------------------

**Disable retries (testing/debugging):**

.. code-block:: python

   coordinator.retry_handler.max_retries = 0

**Raise exceptions on failure:**

.. code-block:: python

   from scholar_flux.exceptions import InvalidResponseException
   
   coordinator.retry_handler.raise_on_error = True
   
   try:
       result = coordinator.search_page(page=1)
   except InvalidResponseException as e:
       print(f"Failed after {coordinator.retry_handler.max_retries} retries")

**Aggressive retries (production with unreliable network):**

.. code-block:: python

   coordinator.retry_handler.max_retries = 5
   coordinator.retry_handler.backoff_factor = 1.0
   coordinator.retry_handler.max_backoff = 300

.. tip::
   Enable logging to see retry attempts: ``logging.getLogger('scholar_flux').setLevel(logging.INFO)``

Practical Examples
==================

Example 1: Basic Search with Error Handling
--------------------------------------------

.. code-block:: python

   from scholar_flux import SearchCoordinator
   
   coordinator = SearchCoordinator(
       query="machine learning",
       provider_name="plos"
   )
   
   result = coordinator.search_page(page=1)
   
   if result:
       print(f"✅ Found {len(result.data)} records")
       
       # Process records
       for record in result.data[:5]:
           title = record.get('title_display', 'No title')
           doi = record.get('id', 'No DOI')
           print(f"  {title} ({doi})")
   else:
       print(f"❌ Search failed: {result.error}")
       print(f"   Message: {result.message}")

Example 2: Multi-Page Retrieval with Error Handling
---------------------------------------------------

.. code-block:: python

   from scholar_flux import SearchCoordinator
   import pandas as pd
   
   coordinator = SearchCoordinator(query="CRISPR", provider_name="plos")
   
   # Retrieve 10 pages
   results = coordinator.search_pages(pages=range(1, 11))
   
   # Filter and combine successful results
   successful = results.filter()
   all_records = successful.join()
   
   if all_records:
       df = pd.DataFrame(all_records)
       print(f"✅ Collected {len(df)} records from {len(successful)} pages")
       print(df[['title_display', 'id']].head())
   else:
       print("❌ No successful results")

Example 3: Custom Retry Configuration
--------------------------------------

.. code-block:: python

   from scholar_flux import SearchCoordinator
   
   coordinator = SearchCoordinator(query="test", provider_name="pubmed")
   
   # More aggressive retries for unreliable connection
   coordinator.retry_handler.max_retries = 5
   coordinator.retry_handler.backoff_factor = 1.0
   coordinator.retry_handler.max_backoff = 300
   
   result = coordinator.search_page(page=1)
   
   if result:
       print(f"Success after potential retries: {len(result.data)} records")
   else:
       print(f"Failed after {coordinator.retry_handler.max_retries} attempts")

Where to Go Next
~~~~~~~~~~~~~~~~

**Related Guides:**

- :doc:`getting_started` - Basic search patterns
- :doc:`multi_provider_search` - Concurrent searches and fallback patterns
- :doc:`caching_strategies` - Production caching strategies

**Advanced Topics:**

- :doc:`advanced_workflows` - Multi-step retrieval patterns
- :doc:`custom_providers` - Add new API providers
- :doc:`production_deployment` - Production deployment

**API Reference:**

- :class:`~scholar_flux.api.SearchCoordinator` - Complete coordinator API
- :class:`~scholar_flux.api.RetryHandler` - Retry handler reference
- :class:`~scholar_flux.api.models.ProcessedResponse` - Success response
- :class:`~scholar_flux.api.models.ErrorResponse` - Error response
- :class:`~scholar_flux.api.models.NonResponse` - Network error response
