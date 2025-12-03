Getting Started
===============

Welcome to ScholarFlux! This tutorial will guide you through installation, configuration, and your first search across academic databases.

Overview
--------

ScholarFlux is a production-grade orchestration layer for academic APIs that enables concurrent multi-provider search with automatic rate limiting and schema normalization. By the end of this tutorial, you'll be querying multiple scholarly databases with just a few lines of Python.

Prerequisites
-------------

Before starting, ensure you have:

- **Python 3.10 or higher** installed
- **pip** or **Poetry** for package management
- Basic familiarity with Python
- (Optional) API keys for providers requiring authentication

.. note::
   Most providers (PLOS, arXiv, OpenAlex, Crossref) work out-of-the-box without API keys!

Learning Objectives
-------------------

By the end of this tutorial, you will:

- Install ScholarFlux with the appropriate extras
- Configure environment variables and API keys
- Execute your first search query
- Handle successful and failed searches safely
- Retrieve multiple pages of results
- Enable caching for better performance

Installation
------------

Basic Installation
~~~~~~~~~~~~~~~~~~

Install ScholarFlux using pip:

.. code-block:: bash

   pip install scholar-flux

This installs the core package with minimal dependencies, sufficient for providers like PLOS, OpenAlex, and Crossref that return JSON responses.

Installation with Extras
~~~~~~~~~~~~~~~~~~~~~~~~

For full functionality, install optional dependencies:

.. code-block:: bash

   # All features (recommended for development)
   pip install scholar-flux[parsing,database,cryptography]

   # XML parsing only (for PubMed, arXiv)
   pip install scholar-flux[parsing]

   # Database caching backends (Redis, MongoDB, SQLAlchemy)
   pip install scholar-flux[database]

   # Encrypted caching support
   pip install scholar-flux[cryptography]

**When to use which extras:**

+------------------+------------------------------------------------+--------------------------------+
| Extra            | Installs                                       | Required For                   |
+==================+================================================+================================+
| ``parsing``      | ``xmltodict``, ``pyyaml``                      | PubMed, arXiv (XML responses)  |
+------------------+------------------------------------------------+--------------------------------+
| ``database``     | ``redis``, ``pymongo``, ``sqlalchemy``         | Production caching backends    |
+------------------+------------------------------------------------+--------------------------------+
| ``cryptography`` | ``cryptography``                               | Encrypted session caching      |
+------------------+------------------------------------------------+--------------------------------+

Development Installation
~~~~~~~~~~~~~~~~~~~~~~~~

For contributing or running tests:

.. code-block:: bash

   git clone https://github.com/SammieH21/scholar-flux.git
   cd scholar-flux
   poetry install --with dev,tests --all-extras

Verifying Installation
~~~~~~~~~~~~~~~~~~~~~~

Test your installation:

.. code-block:: python

   import scholar_flux
   print(scholar_flux.__version__)
   # Output: 0.3.0

.. code-block:: python

   from scholar_flux import SearchCoordinator

   # Quick test with PLOS (no API key needed)
   coordinator = SearchCoordinator(query="computer science validation strategies", provider_name="plos")
   result = coordinator.search_page(page=1)
   
   if result:
       print(f"✅ Installation successful! Retrieved {len(result.data)} records")
   else:
       print(f"❌ Search failed: {result.error}")

If you see "✅ Installation successful!", you're ready to continue!

Configuration
-------------

Environment Variables
~~~~~~~~~~~~~~~~~~~~~

ScholarFlux supports configuration via environment variables. Create a ``.env`` file in your project root:

.. code-block:: bash

   # Logging configuration
   SCHOLAR_FLUX_ENABLE_LOGGING=TRUE
   SCHOLAR_FLUX_LOG_LEVEL=INFO
   SCHOLAR_FLUX_PROPAGATE_LOGS=TRUE

   # API keys (optional - only needed for specific providers)
   PUBMED_API_KEY=your_pubmed_key_here
   SPRINGER_NATURE_API_KEY=your_springer_key_here
   CORE_API_KEY=your_core_key_here

   # Cache encryption (optional)
   SCHOLAR_FLUX_CACHE_SECRET_KEY=your_secret_key_here

.. warning::
   Never commit ``.env`` files to version control! Add ``.env`` to your ``.gitignore``.

Loading Configuration
~~~~~~~~~~~~~~~~~~~~~

Option 1: Automatic loading (recommended)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Create a ``.env`` file in your project root. ScholarFlux automatically loads it on import:

.. code-block:: python

   import scholar_flux  # Automatically loads .env

Option 2: Explicit initialization
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

For custom configuration paths:

.. code-block:: python

   from scholar_flux import initialize_package

   initialize_package(
       config_params={'enable_logging': True, 'log_level': 'DEBUG'},
       env_path='path/to/custom/.env'
   )

Option 3: Direct environment variables
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Set environment variables directly (useful for containers):

.. code-block:: bash

   export SCHOLAR_FLUX_ENABLE_LOGGING=TRUE
   export SCHOLAR_FLUX_LOG_LEVEL=DEBUG
   export PUBMED_API_KEY=your_key_here

API Key Setup
~~~~~~~~~~~~~

Providers requiring API keys
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

+---------------------+----------------+---------------------------------------+
| Provider            | API Key Needed | How to Obtain                         |
+=====================+================+=======================================+
| PLOS                |    No          | Works out-of-the-box                  |
+---------------------+----------------+---------------------------------------+
| arXiv               |    No          | Works out-of-the-box                  |
+---------------------+----------------+---------------------------------------+
| OpenAlex            |    No          | Works out-of-the-box                  |
+---------------------+----------------+---------------------------------------+
| Crossref            |    No          | Optional ``mailto`` for higher limits |
+---------------------+----------------+---------------------------------------+
| PubMed              | ✅ Yes         | https://www.ncbi.nlm.nih.gov/account/ |
+---------------------+----------------+---------------------------------------+
| CORE                | ✅ Yes         | https://core.ac.uk/services/api       |
+---------------------+----------------+---------------------------------------+
| Springer Nature     | ✅ Yes         | https://dev.springernature.com        |
+---------------------+----------------+---------------------------------------+

PubMed API Key Setup
^^^^^^^^^^^^^^^^^^^^

1. Create an NCBI account: https://www.ncbi.nlm.nih.gov/account/
2. Navigate to Settings → API Key Management
3. Generate a new API key
4. Add to ``.env``:

.. code-block:: bash

   PUBMED_API_KEY=your_key_here

5. Verify:

.. code-block:: python

   from scholar_flux import SearchCoordinator
   
   coordinator = SearchCoordinator(query="cancer", provider_name="pubmed")
   result = coordinator.search_page(page=1)
   
   if result:
       print(f"✅ PubMed API key working! Retrieved {len(result.data)} records")

Your First Search
-----------------

Single-Provider Search
~~~~~~~~~~~~~~~~~~~~~~

Let's search PLOS for articles about machine learning:

.. code-block:: python

   from scholar_flux import SearchCoordinator

   # Create a coordinator for PLOS
   coordinator = SearchCoordinator(
       query="machine learning",
       provider_name="plos"
   )

   # Execute search for page 1
   result = coordinator.search_page(page=1)

   # Check if search was successful
   if result:
       print(f"Found {len(result.data)} records")
       
       # Access the first record
       first_record = result.data[0]
       print(f"\nTitle: {first_record.get('title_display')}")
       print(f"DOI: {first_record.get('id')}")
       print(f"Journal: {first_record.get('journal')}")
   else:
       print(f"Search failed: {result.error} - {result.message}")

**Expected output:**

.. code-block:: text

   Found 50 records

   Title: Deep learning applications in medical image analysis
   DOI: 10.1371/journal.pone.0212345
   Journal: PLOS ONE

Understanding the Response
~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``coordinator.search_page()`` method returns a :class:`~scholar_flux.api.models.SearchResult` container with search metadata (query, provider_name, page) and a ``response_result`` attribute.

SearchResult is truthy when the search succeeds and falsy when it fails, making error checking simple:

.. code-block:: python

   result = coordinator.search_page(page=1)
   
   if result:
       # Success - access data safely
       print(f"Found {len(result.data)} records")
       for record in result.data[:3]:
           print(f"Title: {record.get('title_display')}")
   else:
       # Failure - diagnostic info always available
       print(f"Error: {result.error} - {result.message}")
       print(f"Provider: {result.provider_name}, Page: {result.page}")

**What's in a SearchResult:**

- ``response``: The raw response received from an API
- ``processed_records``: List of records (dictionaries) after processing
- ``data``: An alias for ``processed_records``, containing a list of records after processing
- ``extracted_records``: List of records (dictionaries) after parsing but before processing
- ``metadata``: Provider-specific info (total results, page size, etc.)
- ``parsed_response``: The response data after parsing with JSON, XML, or YAML
- ``query``: Your search query
- ``provider_name``: The provider that was queried
- ``page``: The page number requested
- ``response_result``: The underlying response object (ProcessedResponse, ErrorResponse, or NonResponse) after response processing

.. tip::
   For detailed information on response types, error handling patterns, and the ``search()`` method, see :doc:`response_handling_patterns`.

Retrieving Multiple Pages
--------------------------

Sequential Page Retrieval
~~~~~~~~~~~~~~~~~~~~~~~~~~

Retrieve multiple pages one at a time:

.. code-block:: python

   from scholar_flux import SearchCoordinator

   coordinator = SearchCoordinator(query="CRISPR", provider_name="plos")

   # Retrieve pages 1-5
   for page_num in range(1, 6):
       result = coordinator.search_page(page=page_num)
       
       if result:
           print(f"Page {page_num}: {len(result.data)} records")
       else:
           print(f"Page {page_num} failed: {result.error}")
           break  # Stop on first error

**Expected output:**

.. code-block:: text

   Page 1: 50 records
   Page 2: 50 records
   Page 3: 50 records
   Page 4: 50 records
   Page 5: 50 records

Batch Page Retrieval
~~~~~~~~~~~~~~~~~~~~

Retrieve multiple pages in one call using :meth:`~scholar_flux.api.SearchCoordinator.search_pages`:

.. code-block:: python

   from scholar_flux import SearchCoordinator

   coordinator = SearchCoordinator(query="CRISPR", provider_name="plos")

   # Retrieve pages 1-5 in one call
   results = coordinator.search_pages(pages=range(1, 6))

   # Results is a SearchResultList
   print(f"Retrieved {len(results)} pages")

   # Filter successful responses
   successful = results.filter()
   print(f"Success rate: {len(successful)}/{len(results)}")

   # Combine all records into a single list
   all_records = successful.join()
   print(f"Total records: {len(all_records)}")

**Expected output:**

.. code-block:: text

   Retrieved 5 pages
   Success rate: 5/5
   Total records: 250

Working with SearchResultList
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The :class:`~scholar_flux.api.models.SearchResultList` provides convenient methods:

.. code-block:: python

   results = coordinator.search_pages(pages=range(1, 6))

   # Filter only successful responses
   successful = results.filter()

   # Combine all records
   all_records = successful.join()

   # Convert to pandas DataFrame (requires pandas)
   import pandas as pd
   df = pd.DataFrame(all_records)
   print(df.head())

   # Iterate through results
   for result in results:
       if result:
           print(f"Page {result.page}: {len(result.data)} records")

Caching Results
---------------

Request Caching (Layer 1)
~~~~~~~~~~~~~~~~~~~~~~~~~~

Cache HTTP responses to avoid redundant network requests:

.. code-block:: python

   from scholar_flux import SearchCoordinator

   coordinator = SearchCoordinator(
       query="machine learning",
       provider_name="plos",
       use_cache=True  # Enable HTTP response caching
   )

   # First call: Makes network request
   result1 = coordinator.search_page(page=1)
   print("First call - from network")

   # Second call: Retrieved from cache (instant)
   result2 = coordinator.search_page(page=1)
   print("Second call - from cache")

.. note::
   By default, ``use_cache=True`` uses an in-memory SQLite cache. For production, use Redis or MongoDB.

Result Caching (Layer 2)
~~~~~~~~~~~~~~~~~~~~~~~~~

Cache processed results after extraction and transformation:

.. code-block:: python

   from scholar_flux import SearchCoordinator, DataCacheManager

   # Use Redis for persistent caching
   cache_manager = DataCacheManager.with_storage('redis', 'localhost:6379')

   coordinator = SearchCoordinator(
       query="machine learning",
       provider_name="plos",
       cache_manager=cache_manager
   )

   # First call: Processes and caches results
   result1 = coordinator.search_page(page=1)

   # Second call: Retrieved from processed cache
   result2 = coordinator.search_page(page=1)

.. seealso::
   For advanced caching strategies, see :doc:`caching_strategies`.

Next Steps
----------

Congratulations! You've completed the Getting Started tutorial. You now know how to:

✅ Install ScholarFlux with appropriate extras
✅ Configure environment variables and API keys
✅ Execute searches across academic providers
✅ Handle successful and failed searches safely
✅ Retrieve multiple pages of results
✅ Cache responses for performance


Common Pitfalls
---------------

1. **Forgetting to check response validity**
   
   ❌ Bad:
   
   .. code-block:: python
   
      result = coordinator.search_page(page=1)
      for record in result.data:  # May crash if result.data is None (ErrorResponses and NonResponses)!
          print(record)
   
   ✅ Good:
   
   .. code-block:: python
   
      result = coordinator.search_page(page=1)
      for record in result.data or []:
          print(record)

2. **Using wrong provider names**
   
   ❌ Bad:
   
   .. code-block:: python
   
      coordinator = SearchCoordinator(query="test", provider_name="pubmed_api")
      # No provider named "pubmed_api"!
   
   ✅ Good:
   
   .. code-block:: python
   
      coordinator = SearchCoordinator(query="test", provider_name="pubmed")

3. **Not installing extras required for specific providers**
   
   ❌ Bad:
   
   .. code-block:: python
   
      # Basic install without [parsing] extra
      coordinator = SearchCoordinator(query="test", provider_name="arxiv")
      result = coordinator.search_page(page=1)  # Will fail - arXiv returns XML!
      # OUTPUT: ErrorResponse(...)
   
   ✅ Good:
   
   .. code-block:: bash
   
      pip install scholar-flux[parsing]  # Installs xmltodict for XML parsing

4. **Hardcoding API keys**
   
   ❌ Bad:
   
   .. code-block:: python
   
      coordinator = SearchCoordinator(
          query="test",
          provider_name="pubmed",
          api_key="abc123xyz"  # Hardcoded - will be committed to git!
      )
   
   ✅ Good:
   
   .. code-block:: python
   
      # Use .env file
      # PUBMED_API_KEY=abc123xyz
      coordinator = SearchCoordinator(query="test", provider_name="pubmed")

Where to Go Next
~~~~~~~~~~~~~~~~

**Core Tutorials:**

- :doc:`response_handling_patterns` - Response types, error handling, retry configuration
- :doc:`multi_provider_search` - Query multiple providers concurrently
- :doc:`schema_normalization` - Build ML-ready datasets with consistent schemas
- :doc:`caching_strategies` - Advanced caching with Redis, MongoDB, SQLAlchemy

**Advanced Topics:**

- :doc:`advanced_workflows` - Multi-step retrieval pipelines
- :doc:`custom_providers` - Add new API providers to ScholarFlux
- :doc:`production_deployment` - Deploy ScholarFlux in production

**Reference:**

- :doc:`index` - Documentation home

Getting Help
------------

If you encounter issues:

1. **Check the documentation**: https://SammieH21.github.io/scholar-flux/
2. **Search existing issues**: https://github.com/SammieH21/scholar-flux/issues
3. **Ask a question**: Open a new issue with details about your environment
4. **Email**: scholar.flux@gmail.com

When reporting issues, include:

- ScholarFlux version: ``import scholar_flux; print(scholar_flux.__version__)``
- Python version: ``python --version``
- Operating system
- Minimal code to reproduce the issue
- Complete error message

Further Reading
---------------

- :doc:`response_handling_patterns` - Response handling and error patterns
- :doc:`multi_provider_search` - Concurrent multi-provider orchestration
- :doc:`schema_normalization` - Building ML datasets with consistent schemas
- :class:`~scholar_flux.api.SearchCoordinator` API reference
- :class:`~scholar_flux.api.SearchAPI` API reference
- :class:`~scholar_flux.api.models.ProcessedResponse` API reference
