Caching Strategies
==================

ScholarFlux uses **two-layer caching** to speed up data collection while keeping results accurate and fresh. This tutorial shows you how to configure caching for common research workflows.

.. contents:: Table of Contents
   :local:
   :depth: 2

Prerequisites
-------------

- Complete :doc:`getting_started` for basic usage
- Understanding of :doc:`response_handling_patterns` for error handling with caching
- Basic knowledge of cache backends (Redis, MongoDB, SQLite)

Understanding the Two Caches
-----------------------------

ScholarFlux has two independent caches that work together:

**Session Cache (HTTP Responses)**
   Caches raw API responses to avoid redundant network requests. Uses ``requests-cache``.
   
   - **Status**: Disabled by default
   - **Thread-safe**: ❌ No (create one session per thread)
   - **Best for**: Repeated analysis of same data

**Processing Cache (Parsed Data)**
   Caches processed results after parsing and extraction.
   
   - **Status**: Enabled by default (in-memory)
   - **Thread-safe**: ✅ Yes (safe to share)
   - **Best for**: Avoiding re-processing of API responses

.. tip::
   Both caches work identically across all providers (PubMed, Crossref, PLOS, CORE, Springer Nature).

Quick Start Patterns
--------------------

Default: Processing Cache Only
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

By default, processed results are cached in memory:

.. code-block:: python

   from scholar_flux import SearchCoordinator
   
   coordinator = SearchCoordinator(
       query="machine learning applications",
       provider_name="pubmed"
   )
   
   # First search: fetches from API and caches processed results
   results = coordinator.search(page=1)
   
   # Second search: retrieves from processing cache (no re-parsing)
   results_cached = coordinator.search(page=1)

Enable Session Caching
~~~~~~~~~~~~~~~~~~~~~~~

Add HTTP response caching to reduce network requests (and avoid potential rate-limit-exceeded status codes):

.. code-block:: python

   from scholar_flux import SearchCoordinator
   from scholar_flux.sessions import CachedSessionManager
   
   # Create session manager (factory for thread-safe sessions)
   session_manager = CachedSessionManager(
       cache_name="my_cache",
       backend="memory"
   )
   
   coordinator = SearchCoordinator(
       query="deep learning",
       provider_name="crossref",
       session=session_manager.configure_session()  # Creates new session instance
   )
   
   results = coordinator.search(page=1)

Disable All Caching
~~~~~~~~~~~~~~~~~~~~

For testing or when you always need fresh data:

.. code-block:: python

   from scholar_flux import SearchCoordinator
   
   # Disable processing cache
   coordinator = SearchCoordinator(
       query="quantum computing",
       provider_name="plos",
       cache_results=False
   )
   
   # Every search reprocesses results
   results = coordinator.search(page=1)
   
   # Or temporarily disable for one request:
   results = coordinator.search(
       page=1,
       from_request_cache=False,  # Force fresh HTTP request
       from_process_cache=False    # Force re-processing
   )

Choosing a Storage Backend
---------------------------

The processing cache supports four backends. Choose based on your needs:

+------------------+---------------+---------+-------------+------------------+
| Backend          | Thread-Safe   | TTL     | Persistence | Best For         |
+==================+===============+=========+=============+==================+
| **memory**       | ✅ Yes        | ❌ No   | ❌ No       | Development      |
+------------------+---------------+---------+-------------+------------------+
| **sql**          | ✅ Yes        | ❌ No   | ✅ Yes      | Local projects   |
+------------------+---------------+---------+-------------+------------------+
| **redis**        | ✅ Yes        | ✅ Yes  | ✅ Yes      | Production       |
+------------------+---------------+---------+-------------+------------------+
| **mongodb**      | ✅ Yes        | ✅ Yes  | ✅ Yes      | Document storage |
+------------------+---------------+---------+-------------+------------------+

InMemory (Default)
~~~~~~~~~~~~~~~~~~

Fast but data is lost when your program ends:

.. code-block:: python

   from scholar_flux import SearchCoordinator
   from scholar_flux.data_storage import DataCacheManager
   
   cache = DataCacheManager.with_storage("memory")
   
   coordinator = SearchCoordinator(
       query="climate change",
       provider_name="core",
       cache_manager=cache
   )

SQLite (Persistent)
~~~~~~~~~~~~~~~~~~~

Best for local projects where you want cache to persist:

.. code-block:: python

   from scholar_flux.data_storage import DataCacheManager
   from scholar_flux import SearchCoordinator
   
   # Uses ~/.scholar-flux/package_cache/data_store.sqlite by default
   cache = DataCacheManager.with_storage(
       "sql",
       namespace="literature_review"
   )
   
   # Or specify custom location:
   cache = DataCacheManager.with_storage(
       "sql",
       namespace="literature_review",
       url="sqlite:///./my_cache/data.db"
   )
   
   coordinator = SearchCoordinator(
       query="renewable energy",
       provider_name="springernature",
       cache_manager=cache
   )

Redis (Production)
~~~~~~~~~~~~~~~~~~

High-performance with automatic expiration (TTL):

.. code-block:: python

   from scholar_flux.data_storage import DataCacheManager
   
   cache = DataCacheManager.with_storage(
       "redis",
       namespace="production_search",
       host="localhost",  # Default configuration if omitted
       port=6379,         # Default configuration if omitted
       ttl=86400          # Expire after 24 hours
   )

MongoDB (Document Storage)
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Similar to Redis but with document-oriented storage:

.. code-block:: python

   from scholar_flux.data_storage import DataCacheManager
   
   cache = DataCacheManager.with_storage(
       "mongodb",
       namespace="research_project",
       host="mongodb://127.0.0.1", # Default configuration if omitted
       port=27017, # Default configuration if omitted
       database="scholar_flux",
       collection="cache",
       ttl=604800  # Expire after 7 days
   )

Using Namespaces
----------------

Namespaces let you organize cache by project, environment, or data source, even when they use the same DB:

.. code-block:: python

   from scholar_flux.data_storage import DataCacheManager
   from scholar_flux import SearchCoordinator
   
   # Separate cache for different projects
   cancer_cache = DataCacheManager.with_storage(
       "sql",
       namespace="cancer_research"
   )
   
   climate_cache = DataCacheManager.with_storage(
       "sql",
       namespace="climate_science"
   )
   
   # Each uses separate cache space
   cancer_coord = SearchCoordinator(
       query="immunotherapy",
       provider_name="pubmed",
       cache_manager=cancer_cache
   )
   
   climate_coord = SearchCoordinator(
       query="ocean acidification",
       provider_name="plos",
       cache_manager=climate_cache
   )

**Namespace best practices:**

.. code-block:: python

   # Organize by environment
   dev_cache = DataCacheManager.with_storage("memory", namespace="dev")
   prod_cache = DataCacheManager.with_storage("redis", namespace="prod")
   
   # Organize hierarchically if needed
   cache = DataCacheManager.with_storage(
       "redis",
       namespace="user/123/project/ml_research"
   )

Encrypted Session Caching
--------------------------

For sensitive queries, use encrypted session cache:

.. code-block:: python

   """
   Encrypt cached HTTP responses for security
   """
   from scholar_flux.api import SearchCoordinator
   from scholar_flux.sessions import EncryptionPipelineFactory, CachedSessionManager
   from scholar_flux.utils import config_settings
   import os
   
   # Load or create encryption key
   key = os.environ.get("SCHOLAR_FLUX_CACHE_SECRET_KEY")
   encryption_factory = EncryptionPipelineFactory(key)
   
   if not key:
       # Save this key securely - losing it means losing cached data
       new_key = encryption_factory.secret_key
       print(f"Saving the secret key...")

       
       # next reload of scholar_flux should hold the following variable after it is saved
       config_settings.write_key(
           "SCHOLAR_FLUX_CACHE_SECRET_KEY", # the name of the key
           new_key.decode(), # the value of the key bytes to write
           env_path=config_settings.env_path # the current `env_path` is actually the default
       )
   
   # Create encrypted serializer
   serializer = encryption_factory()
   
   # Create cached session with encryption
   session_manager = CachedSessionManager(
       cache_name="encrypted_cache",
       backend="sqlite",
       cache_directory=None,  # Uses default scholar-flux directory
       serializer=serializer
   )
   
   coordinator = SearchCoordinator(
       query="sensitive research query",
       provider_name="pubmed",
       session=session_manager()
   )
   
   # Responses are encrypted in cache
   results = coordinator.search(page=1)

.. warning::
   - Never commit encryption keys to version control
   - Rotate encryption keys periodically
   - If the key is lost, cached data cannot be recovered
   - Use different keys for development and production


Monitoring Cache Behavior
--------------------------

Enable logging to see what's being cached:

.. code-block:: python

   import logging
   
   # Enable ScholarFlux logging (console output is enabled by default)
   logger = logging.getLogger('scholar_flux')
   logger.setLevel(logging.INFO)

   # Optional: prevent propogating (duplicate) logs
   logger.propagate = False

**Inspecting cache directly:**

.. code-block:: python

   from scholar_flux.data_storage import DataCacheManager
   
   cache = DataCacheManager.with_storage("memory")
   storage_backend = cache.cache_storage
   
   # Perform searches...
   # coordinator.search(page=1)
   # coordinator.search(page=2)
   
   # Check what's cached
   all_keys = storage_backend.retrieve_keys()
   print(f"Cached pages: {len(all_keys)}")
   print(f"Keys: {all_keys}")
   
   # Get all cached data
   all_data = storage_backend.retrieve_all()
   for key, value in all_data.items():
       records = value.get('processed_records', {})
       print(f"Key: {key}, Records: {len(records)}")

Practical Examples
------------------

Example: Machine Learning Data Collection
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Collect training data with persistent caching:

.. code-block:: python

   """
   Collect labeled papers for ML classification task
   """
   from scholar_flux import SearchCoordinator, MultiSearchCoordinator
   from scholar_flux.data_storage import DataCacheManager
   from pathlib import Path
   import pandas as pd
   
   # Setup persistent cache with the default SQL-storage
   cache = DataCacheManager.with_storage(
       "sql",
       namespace="ml_training_data", # limit the record scope
   )
   
   # Collect papers on different topics
   topics = {
       "machine learning algorithms":"machine_learning",
       "deep learning neural networks": "deep_learning",
       "reinforcement learning": "reinforcement" 
   }
   
   # Create coordinators for threaded searches by provider (sequential in this case)
   multicoordinator = MultiSearchCoordinator()
   multicoordinator.add_coordinators(
       SearchCoordinator(
           query=query,
           provider_name="pubmed",
           cache_manager=cache
       ) for query in topics.keys()
   )

   # Fetch pages 1 and 2 across several
   search_result_list = multicoordinator.search_pages(range(1, 3))

   # Show the results of the search:
   for search_result in search_result_list:
       print(f"Collected {search_result.query} page {search_result.page}: {search_result.record_count} papers")
   print(f"Total records: {search_result_list.record_count}")

   # Maps record fields to common names and stores each dictionary record inside the same list
   normalized_records = search_result_list.filter().normalize(include={'provider_name', 'query', 'page'})
   df = pd.DataFrame(normalized_records)
   df['label'] = df['query'].apply(lambda q: topics[q])
   
   print(f"Cached pages: {len(cache.cache_storage.retrieve_keys())}")

Multi-Provider Parallel Searches
---------------------------------

For concurrent searches across providers, use ``MultiSearchCoordinator``:

.. code-block:: python

   from scholar_flux import SearchCoordinator, MultiSearchCoordinator
   from scholar_flux.data_storage import DataCacheManager
   from scholar_flux.sessions import CachedSessionManager
   
   user_agent="Research/1.0 (mailto:user@institution.edu)" # Change this
   # Each provider needs a separate session factory, independent of backend (request-cache sessions are not thread-safe)
   session_manager = CachedSessionManager(backend="redis", user_agent = user_agent)

   # The data cache manager uses a shared cache (thread-safe)
   cache_manager = DataCacheManager.with_storage("redis", namespace="multi_search")
   
   # Create coordinators for each provider
   plos = SearchCoordinator(query="neural networks", provider_name="plos", cache_manager = cache_manager, session=session_manager())
   arxiv = SearchCoordinator(query="neural networks", provider_name="arxiv", cache_manager = cache_manager, session=session_manager())
   crossref = SearchCoordinator(query="neural networks", provider_name="crossref", cache_manager = cache_manager, session=session_manager())
   
   # Search all concurrently
   multicoordinator = MultiSearchCoordinator()
   multicoordinator.add_coordinators([plos, arxiv, crossref])
   
   # All providers search in parallel (thread-safe)
   results = multicoordinator.search_pages(pages=range(1, 11))

.. tip::
   For multi-provider concurrent searches with caching, see :doc:`multi_provider_search`.
   For workflow-based caching patterns, see :doc:`advanced_workflows`.
   For production caching deployment, see :doc:`production_deployment`.

Cache Invalidation
------------------

The processing cache automatically invalidates when:

1. **Response content changed** - API returned different data
2. **Coordinator structure changed** - Different parsing/processing steps
3. **TTL expired** - Cache entry too old (Redis/MongoDB only)

**Manual cache control:**

.. code-block:: python

   from scholar_flux.data_storage import DataCacheManager
   from scholar_flux import SearchCoordinator
   
   cache_manager = DataCacheManager.with_storage("sql", namespace="temp")
   
   coordinator = SearchCoordinator(
       query="test query",
       provider_name="pubmed",
       cache_manager=cache_manager
   )
   
   # Cache results
   results = coordinator.search(page=1)
   
   # Clear specific page (will re-cache on next search)
   cache_key = coordinator._create_cache_key(page=1)
   cache_manager.delete(cache_key)
   
   # Clear entire namespace
   cache_manager.cache_storage.delete_all()

Time-To-Live (TTL) Strategies
------------------------------

Redis and MongoDB support automatic cache expiration:

.. code-block:: python

   from scholar_flux.data_storage import DataCacheManager
   
   # Short TTL for frequently-changing data (1 hour)
   news_cache = DataCacheManager.with_storage(
       "redis",
       namespace="news",
       ttl=3600
   )
   
   # Medium TTL for general searches (1 day)
   research_cache = DataCacheManager.with_storage(
       "redis",
       namespace="research",
       ttl=86400
   )
   
   # Long TTL for stable data (30 days)
   archive_cache = DataCacheManager.with_storage(
       "mongodb",
       namespace="archive",
       ttl=86400 * 30
   )

Troubleshooting
---------------

Cache Not Persisting
~~~~~~~~~~~~~~~~~~~~

**Problem**: Using in-memory cache (default)

.. code-block:: python

   # Problem: Data lost when program ends
   cache = DataCacheManager.with_storage("memory")
   
   # Solution: Use persistent backend
   cache = DataCacheManager.with_storage("sql")

Thread Safety Errors
~~~~~~~~~~~~~~~~~~~~~

**Problem**: Sharing session across threads

.. code-block:: python

   # ❌ Wrong: Single session shared across threads
   session = CachedSessionManager(backend="memory").configure_session()
   # Used in multiple threads - NOT SAFE
   
   # ✅ Correct: Create session per thread
   session_manager = CachedSessionManager(backend="memory")
   # Call session_manager() to create new instance per thread

Redis Connection Failed
~~~~~~~~~~~~~~~~~~~~~~~~

**Check these common issues:**

1. Redis server not running: ``sudo systemctl start redis``
2. Wrong host/port configuration
3. Firewall blocking port 6379
4. Python redis library not installed: ``pip install redis``

.. code-block:: python

   # import the RedisStorage directly
   from scholar_flux.data_storage.redis_storage import RedisStorage
   
   if RedisStorage.is_available():
       cache = DataCacheManager.with_storage("redis")
   else:
       print("Redis not available, falling back to SQL")
       cache = DataCacheManager.with_storage("sql")

Best Practices
--------------

**1. Choose the Right Backend**

- Development: ``memory`` (fast, no setup)
- Local projects: ``sql`` (persistent, simple)
- Production: ``redis`` or ``mongodb`` (scalable, TTL)

**2. Use Namespaces**

- Separate projects: ``namespace="project_name"``
- Separate environments: ``namespace="dev"`` vs ``namespace="prod"``
- Hierarchical: ``namespace="user:123:project:cancer"``

**3. Set Appropriate TTL**

- Frequently-changing data: 1-6 hours
- General research: 1-7 days
- Archival data: 30+ days
- Development: No TTL (never expires)

**4. Monitor Your Cache**

.. code-block:: python

   import logging
   logger = logging.getLogger('scholar_flux')

   # Will log rate-limits, response retrieval, processing, etc.
   logger.setLevel(logging.INFO)

**5. Handle Errors Gracefully**

.. code-block:: python

   # Continue processing even if cache fails
   cache = DataCacheManager.with_storage(
       "redis",
       raise_on_error=False  # Log errors, don't crash
   )

**6. Thread Safety**

- Sessions: Create per thread with ``session_manager()``
- Processing cache: Safe to share across threads
- For parallel work: Use ``MultiSearchCoordinator``

Further Reading
---------------

**Related Tutorials:**

- :doc:`getting_started` - Basic ScholarFlux usage
- :doc:`response_handling_patterns` - Error handling with caching
- :doc:`multi_provider_search` - Parallel searches and threading
- :doc:`advanced_workflows` - Cache multi-step workflows

**Production:**

- :doc:`production_deployment` - Production caching patterns with SCHOLAR_FLUX_HOME
- `Security Guidelines <https://github.com/SammieH21/scholar-flux?tab=security-ov-file>`_ - Comprehensive security guidelines including encryption and security best practices

For questions or issues, visit the `GitHub repository <https://github.com/SammieH21/scholar-flux>`_.

