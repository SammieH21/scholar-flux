Production Deployment
=====================

This guide covers essential configuration and patterns for deploying ScholarFlux in production environments for machine learning and data engineering workflows.

.. contents:: Table of Contents
   :local:
   :depth: 2

Overview
--------

ScholarFlux is designed for production-grade data collection from academic APIs. This MVP guide focuses on:

- **ML/Data Engineering**: Building training datasets, systematic reviews, longitudinal monitoring
- **Reproducibility**: Environment configuration and containerization
- **Essential patterns**: Caching, concurrency, and security basics

.. note::
   ScholarFlux is currently **beta (v0.3.0)**. Test thoroughly before production deployment and monitor the `GitHub repository <https://github.com/SammieH21/scholar-flux>`_ for updates.

Prerequisites
-------------

- Completed :doc:`getting_started` tutorial
- Understanding of :doc:`response_handling_patterns` for error handling in production
- Understanding of :doc:`caching_strategies` for persistent storage
- Python 3.10+ in production environment
- Redis or MongoDB for production caching (recommended)

Environment Configuration
=========================

SCHOLAR_FLUX_HOME (Recommended)
--------------------------------

The recommended approach for production is to set ``SCHOLAR_FLUX_HOME`` to centralize all ScholarFlux configuration, caching, and logging in a single directory:

.. code-block:: bash

   # Set SCHOLAR_FLUX_HOME
   export SCHOLAR_FLUX_HOME=/opt/scholar-flux
   
   # ScholarFlux will automatically use:
   # - .env file:    $SCHOLAR_FLUX_HOME/.env
   # - Cache:        $SCHOLAR_FLUX_HOME/package_cache/
   # - Logs:         $SCHOLAR_FLUX_HOME/logs/

**Directory structure:**

.. code-block:: text

   /opt/scholar-flux/
   ├── .env                    # Configuration and API keys
   ├── package_cache/          # Processed results cache
   │   └── data_store.sqlite   # SQLite cache (if using SQL backend)
   └── logs/                   # Application logs (with rotation)
       └── scholar_flux.log

**Setup:**

.. code-block:: bash

   # Create directory structure
   mkdir -p /opt/scholar-flux/{package_cache,logs}
   
   # Create .env file
   cat > /opt/scholar-flux/.env << 'EOF'
   SCHOLAR_FLUX_ENABLE_LOGGING=TRUE
   SCHOLAR_FLUX_LOG_LEVEL=INFO
   PUBMED_API_KEY=<your_api_key>
   EOF
   
   # Set environment variable (add to ~/.bashrc or /etc/environment)
   export SCHOLAR_FLUX_HOME=/opt/scholar-flux

**How it works:**

ScholarFlux searches for writable directories in priority order:

1. ``$SCHOLAR_FLUX_HOME`` (if set) ← **Recommended for production**
2. ``~/.scholar_flux`` (user home directory)
3. ``.scholar_flux`` (current working directory)
4. Package installation directory

For ``.env`` files specifically, ScholarFlux also checks the current working directory, making it easy to place ``.env`` in either ``$SCHOLAR_FLUX_HOME/.env`` or simply ``./env`` in your project directory.

See ``scholar_flux.package_metadata.directories.get_default_writable_directory`` for implementation details.

.. tip::
   Using ``SCHOLAR_FLUX_HOME`` is especially useful for:
   
   - Docker containers (mount a volume to a known location)
   - Shared servers (separate directories per user/project)
   - Production environments (centralized configuration)
   - Multi-user systems (avoid ~/.scholar_flux conflicts)

Configuration System
--------------------

ScholarFlux uses a hierarchical configuration system with the following priority:

1. **Explicit parameters** in code
2. **Environment variables** (highest priority for production)
3. **``.env`` file** (auto-loaded from ``$SCHOLAR_FLUX_HOME`` or fallback locations)
4. **Default values**

See :doc:`getting_started` for basic configuration setup.

Production Environment Variables
---------------------------------

With ``SCHOLAR_FLUX_HOME`` set, create a ``.env`` file at ``$SCHOLAR_FLUX_HOME/.env``:

Core Configuration
~~~~~~~~~~~~~~~~~~

Based on ``scholar_flux.config.config_loader``:

.. code-block:: bash

   # Logging (auto-uses $SCHOLAR_FLUX_HOME/logs/ if SCHOLAR_FLUX_HOME is set)
   SCHOLAR_FLUX_ENABLE_LOGGING=TRUE
   SCHOLAR_FLUX_LOG_LEVEL=INFO              # DEBUG, INFO, WARNING, ERROR
   SCHOLAR_FLUX_PROPAGATE_LOGS=FALSE        # Set FALSE for production
   
   # Optional: Override log directory (otherwise uses $SCHOLAR_FLUX_HOME/logs/)
   # SCHOLAR_FLUX_LOG_DIRECTORY=/var/log/scholar-flux

   # Optional: Override cache directory (otherwise uses $SCHOLAR_FLUX_HOME/package_cache/)
   # SCHOLAR_FLUX_CACHE_DIRECTORY=/var/cache/scholar-flux

   # Cache encryption (generate secure random key)
   SCHOLAR_FLUX_CACHE_SECRET_KEY=your_secure_random_key_here

.. note::
   If ``SCHOLAR_FLUX_HOME`` is set, you typically don't need to set ``SCHOLAR_FLUX_LOG_DIRECTORY`` or ``SCHOLAR_FLUX_CACHE_DIRECTORY`` explicitly. They default to subdirectories within ``$SCHOLAR_FLUX_HOME``.

API Provider Keys
~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # Required for specific providers
   PUBMED_API_KEY=<insert_your_key>
   SPRINGER_NATURE_API_KEY=<insert_your_key>
   CORE_API_KEY=<insert_your_key>
   
   # Optional (some providers don't require keys)
   ARXIV_API_KEY=<insert_your_key>
   OPEN_ALEX_API_KEY=<insert_your_key>
   CROSSREF_API_KEY=<insert_your_key>

Cache Backend Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # Redis (recommended for production)
   SCHOLAR_FLUX_REDIS_HOST=localhost        # or REDIS_HOST
   SCHOLAR_FLUX_REDIS_PORT=6379             # or REDIS_PORT

   # MongoDB (alternative)
   SCHOLAR_FLUX_MONGODB_HOST=mongodb://127.0.0.1   # or MONGODB_HOST
   SCHOLAR_FLUX_MONGODB_PORT=27017                 # or MONGODB_PORT

   # Default provider (optional)
   SCHOLAR_FLUX_DEFAULT_PROVIDER=plos

.. tip::
   ScholarFlux accepts both prefixed (``SCHOLAR_FLUX_*``) and unprefixed (``REDIS_HOST``) variables for cache backends, prioritizing the prefixed version.

Loading Configuration
---------------------

Automatic Loading (Recommended)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

ScholarFlux automatically loads environment configuration on import, but **caching requires explicit setup**:

.. code-block:: python

   import scholar_flux  # Loads .env from $SCHOLAR_FLUX_HOME or fallback locations
   from scholar_flux import SearchCoordinator
   from scholar_flux.sessions import CachedSessionManager
   from scholar_flux.data_storage import DataCacheManager
   
   # Request cache (off by default) - CachedSessionManager automatically uses 
   # $SCHOLAR_FLUX_HOME/package_cache/ for SQLite backend
   session_manager = CachedSessionManager(
       backend='sqlite',
       user_agent='Research/1.0 mailto:your@institution.edu',
       expire_after=86400  # 24 hours
   )
   
   # Response processing cache (in-memory by default) - DataCacheManager automatically uses
   # $SCHOLAR_FLUX_HOME/package_cache/ for SQLite backend
   cache = DataCacheManager.with_storage(
       'sqlite',
       namespace='my_project',
       ttl=86400  # 24 hours
   )
   
   coordinator = SearchCoordinator(
       query="machine learning",
       provider_name="pubmed",
       session=session_manager(),  # Enable request caching
       cache_manager=cache          # Configure response cache
   )
   
   # Both caches automatically use SCHOLAR_FLUX_HOME/package_cache/
   print(session_manager.cache_path)
   # Example: /opt/scholar-flux/package_cache/search_requests_cache
   
   print(cache.cache_storage.config.get('url'))
   # Example: sqlite:////opt/scholar-flux/package_cache/data_store.sqlite

.. tip::
   With ``SCHOLAR_FLUX_HOME`` set, both ``CachedSessionManager`` and ``DataCacheManager`` with SQLite backend automatically store cache files in ``$SCHOLAR_FLUX_HOME/package_cache/``. No path configuration needed!

.. note::
   **Default caching behavior:**
   
   - **Request cache** (HTTP responses): Off by default. Enable with ``session=CachedSessionManager()`` or ``use_cache=True``
   - **Response cache** (processed data): In-memory by default. Use ``DataCacheManager.with_storage()`` for persistence

Custom Configuration Path
~~~~~~~~~~~~~~~~~~~~~~~~~~

For custom ``.env`` locations:

.. code-block:: python

   from scholar_flux import initialize_package
   
   initialize_package(
       env_path="/etc/scholar-flux/.env.production",
       config_params={'enable_logging': True, 'log_level': 'INFO'}
   )

Validation
~~~~~~~~~~

Validate required secrets on startup:

.. code-block:: python

   import os
   
   required_secrets = ['PUBMED_API_KEY', 'REDIS_HOST', 'SCHOLAR_FLUX_CACHE_SECRET_KEY']
   missing = [key for key in required_secrets if not os.getenv(key)]
   
   if missing:
       raise EnvironmentError(f"Missing required configuration: {missing}")

Docker for Reproducibility
===========================

Using SCHOLAR_FLUX_HOME in Docker
----------------------------------

The recommended approach is to mount a volume to ``SCHOLAR_FLUX_HOME``:

.. code-block:: bash

   # Create host directory
   mkdir -p /opt/scholar-flux
   
   # Run container with volume mount
   docker run \
     -e SCHOLAR_FLUX_HOME=/app/scholar-flux \
     -v /opt/scholar-flux:/app/scholar-flux \
     scholar-flux-app

This mounts the host's ``/opt/scholar-flux`` to the container's ``/app/scholar-flux``, making ``.env``, cache, and logs persist across container restarts.

Basic Dockerfile
----------------

Create reproducible research environments:

.. code-block:: dockerfile

   FROM python:3.11-slim
   
   WORKDIR /app
   
   # Install dependencies
   COPY requirements.txt .
   RUN pip install --no-cache-dir -r requirements.txt
   
   # Copy application
   COPY . .
   
   # Create SCHOLAR_FLUX_HOME directory
   RUN mkdir -p /app/scholar-flux/{package_cache,logs}
   ENV SCHOLAR_FLUX_HOME=/app/scholar-flux
   
   # Non-root user
   RUN useradd -m scholar && \
       chown -R scholar:scholar /app
   USER scholar
   
   CMD ["python", "research_pipeline.py"]

**requirements.txt:**

.. code-block:: text

   scholar-flux[parsing,database,cryptography]>=0.2.0
   redis>=5.0.0
   pymongo>=4.0.0
   pandas>=2.0.0

Environment Variables in Docker
--------------------------------

**Option 1: .env file in SCHOLAR_FLUX_HOME (Recommended)**

.. code-block:: bash

   # Create .env on host
   cat > /opt/scholar-flux/.env << 'EOF'
   SCHOLAR_FLUX_ENABLE_LOGGING=TRUE
   PUBMED_API_KEY=<insert_your_key>
   EOF
   
   # Run with volume mount
   docker run \
     -e SCHOLAR_FLUX_HOME=/app/scholar-flux \
     -v /opt/scholar-flux:/app/scholar-flux \
     scholar-flux-app

**Option 2: Direct environment variables**

.. code-block:: bash

   docker run \
     -e SCHOLAR_FLUX_HOME=/app/scholar-flux \
     -e PUBMED_API_KEY=$PUBMED_API_KEY \
     -e REDIS_HOST=redis \
     -v /opt/scholar-flux:/app/scholar-flux \
     scholar-flux-app

**Option 3: Docker Compose (Recommended for multi-container)**

.. code-block:: yaml

   version: '3.8'
   
   services:
     app:
       build: .
       environment:
         - SCHOLAR_FLUX_HOME=/app/scholar-flux
         - REDIS_HOST=redis
       volumes:
         - ./scholar-flux:/app/scholar-flux  # Host directory to container
       depends_on:
         - redis
     
     redis:
       image: redis:7-alpine
       volumes:
         - redis-data:/data
   
   volumes:
     redis-data:

**Directory structure on host:**

.. code-block:: text

   ./
   ├── docker-compose.yml
   ├── Dockerfile
   ├── research_pipeline.py
   └── scholar-flux/           # Mounted to container
       ├── .env                # Contains API keys
       ├── package_cache/      # Persisted cache
       └── logs/               # Persisted logs

.. note::
   Docker is recommended for **reproducible research environments**, not necessarily for production deployment at scale. Using ``SCHOLAR_FLUX_HOME`` with volume mounts ensures your configuration, cache, and logs persist across container restarts.

Production Patterns
===================

This section references core patterns covered in detail elsewhere. For production deployments, understand these foundational concepts:

Caching Strategy
----------------

ScholarFlux uses two-layer caching (HTTP responses + processed results). For production:

- Use **persistent backends** (SQLite, Redis, or MongoDB) not in-memory
- Set appropriate **TTL** based on data freshness needs
- Use **namespaces** to isolate different projects/experiments

**Example with SCHOLAR_FLUX_HOME:**

.. code-block:: python

   from scholar_flux import SearchCoordinator, CachedSessionManager
   from scholar_flux.data_storage import DataCacheManager
   import os
   
   # 24 Hour request cache expiration by default
   session_manager = CachedSessionManager(
       backend='sqlite',
       user_agent='Research/1.0 mailto:user@your.affiliation.edu',
       expire_after=86400
   )
   
   # Production response processing cache with Redis
   cache = DataCacheManager.with_storage(
       'redis',
       namespace='my_project',
       ttl=86400  # 24 hours
   )
   
   coordinator = SearchCoordinator(
       query="deep learning",
       provider_name="pubmed",
       session=session_manager(),
       cache_manager=cache
   )
   
   print(os.environ.get("SCHOLAR_FLUX_HOME"))
   # ~/.scholar_flux for package debugging in development
   
   print(session_manager.cache_path)
   # OUTPUT: ~/.scholar_flux/package_cache/search_requests_cache
   
   print(cache.cache_storage.config.get('url'))
   # Redis connection details

.. note::
   **For production with Redis**: Simply change ``backend='sqlite'`` to ``backend='redis'`` in the session manager.
   Both session caching and data caching will automatically use the same Redis connection via 
   ``SCHOLAR_FLUX_REDIS_HOST`` and ``SCHOLAR_FLUX_REDIS_PORT`` environment variables.

.. seealso::
   See :doc:`caching_strategies` for comprehensive coverage including Redis/MongoDB configuration, encryption, TTL strategies, and thread-safety patterns.

Multi-Provider Search
---------------------

For ML dataset collection across multiple providers, use ``MultiSearchCoordinator`` for concurrent searches:

.. code-block:: python

   from scholar_flux import SearchCoordinator, MultiSearchCoordinator
   
   # Create coordinators for different providers
   coordinators = [
       SearchCoordinator(query="CRISPR", provider_name="pubmed"),
       SearchCoordinator(query="CRISPR", provider_name="plos"),
       SearchCoordinator(query="CRISPR", provider_name="crossref")
   ]
   
   # Execute concurrently (thread-safe)
   multi = MultiSearchCoordinator()
   multi.add_coordinators(coordinators)
   results = multi.search_pages(pages=range(1, 11))

.. seealso::
   See :doc:`multi_provider_search` for threading, rate limiting coordination, and session management.

Schema Normalization
--------------------

Build ML-ready datasets with consistent schemas across providers:

.. code-block:: python

   # Normalize results from multiple providers
   results = multi.search_pages(pages=range(1, 6))
   normalized = results.filter().normalize(
       include={'provider_name', 'query'}
   )
   
   # Export to pandas
   import pandas as pd
   df = pd.DataFrame(normalized)

.. seealso::
   See :doc:`schema_normalization` for field mappings, custom transformations, and ML pipeline integration.

Workflows
---------

For APIs requiring multi-step retrieval (e.g., PubMed ID search → fetch records):

.. code-block:: python

   # PubMed workflow automatically handles search → fetch
   coordinator = SearchCoordinator(
       query="cancer treatment",
       provider_name="pubmed"  # Uses PubMedWorkflow automatically
   )
   
   results = coordinator.search_pages(pages=range(1, 11))

.. seealso::
   See :doc:`advanced_workflows` for custom workflows, PubMed examples, and multi-step retrieval patterns.

Production Use Cases
====================

Systematic Literature Review
-----------------------------

Collect and cache papers for reproducible reviews:

.. code-block:: python

   from scholar_flux import SearchCoordinator
   from scholar_flux.data_storage import DataCacheManager
   
   cache = DataCacheManager.with_storage(
       'mongodb',
       namespace='systematic_review_2024',
       ttl=2592000  # 30 days
   )
   
   coordinator = SearchCoordinator(
       query="machine learning healthcare",
       provider_name="pubmed",
       cache_manager=cache
   )
   
   # Collect all pages
   results = coordinator.search_pages(pages=range(1, 101))
   successful = results.filter()
   
   # Export for analysis
   normalized = successful.normalize()
   
   import pandas as pd
   df = pd.DataFrame(normalized)
   df.to_csv('systematic_review_data.csv', index=False)

ML Training Data Collection
----------------------------

Build labeled datasets from multiple sources:

.. code-block:: python

   from scholar_flux import SearchCoordinator, MultiSearchCoordinator
   from scholar_flux.data_storage import DataCacheManager
   
   cache = DataCacheManager.with_storage('redis', namespace='ml_training')
   
   # Define queries with labels
   queries = {
       'machine learning classification': 'ml',
       'deep learning neural networks': 'dl',
       'reinforcement learning agents': 'rl'
   }
   
   # Create multi-coordinator
   multi = MultiSearchCoordinator()
   for query, label in queries.items():
       coord = SearchCoordinator(
           query=query,
           provider_name="pubmed",
           cache_manager=cache
       )
       multi.add_coordinator(coord)
   
   # Collect data
   results = multi.search_pages(pages=range(1, 11))
   
   # Add labels and export
   import pandas as pd
   normalized = results.filter().normalize(include={'query'})
   df = pd.DataFrame(normalized)
   df['label'] = df['query'].map(queries)
   
   # Train/test split, etc.

Longitudinal Monitoring
-----------------------

Track new publications over time with scheduled collection:

.. code-block:: python

   import schedule
   import time
   from datetime import datetime
   from scholar_flux import SearchCoordinator
   from scholar_flux.data_storage import DataCacheManager
   
   cache = DataCacheManager.with_storage(
       'mongodb',
       namespace='monitoring',
       ttl=604800  # 7 days
   )
   
   def collect_new_papers():
       """Daily collection of new papers."""
       coordinator = SearchCoordinator(
           query="AI safety",
           provider_name="arxiv",
           cache_manager=cache
       )
       
       results = coordinator.search_pages(pages=range(1, 6))
       
       # Process and store
       timestamp = datetime.now().isoformat()
       normalized = results.filter().normalize()
       
       # Save to database/file with timestamp
       import pandas as pd
       df = pd.DataFrame(normalized)
       df['collected_at'] = timestamp
       df.to_csv(f'papers_{timestamp}.csv', index=False)
   
   # Schedule daily collection
   schedule.every().day.at("09:00").do(collect_new_papers)
   
   while True:
       schedule.run_pending()
       time.sleep(3600)

Data Ownership & Citation
==========================

.. warning::
   **Important Legal and Ethical Notice**
   
   ScholarFlux facilitates data retrieval but **does not grant ownership** of the data. Users must:
   
   1. Comply with API Terms of Service
   2. Properly cite original data sources in publications
   3. Respect rate limits and provider guidelines
   4. Consider data privacy (GDPR, CCPA) when handling personal information
   5. Obtain permission for commercial use

Provider Attribution
--------------------

Always cite data sources in publications:

**Example acknowledgment:**

    "Data was retrieved from PubMed (NCBI), PLOS, and Crossref APIs using ScholarFlux. 
    We acknowledge these providers for making scholarly data accessible."

**Provider requirements:**

- **PubMed/NCBI**: Acknowledge "Entrez Programming Utilities"
- **PLOS**: Attribution required for PLOS content
- **Crossref**: Use ``mailto`` in requests for higher rate limits
- **Springer Nature**: Commercial use requires separate licensing

See individual provider documentation for complete terms of service.

Security Essentials
===================

API Key Management
------------------

Never commit secrets to version control:

.. code-block:: bash

   # .gitignore
   .env
   .env.*
   *.key

**Key rotation:**

Rotate API keys periodically when possible. Note that some providers only issue a single API key without rotation support. For providers that support it:

.. code-block:: bash

   # Update .env file in SCHOLAR_FLUX_HOME
   # Old: PUBMED_API_KEY=old_key_123
   # New: PUBMED_API_KEY=new_key_456

Then restart your application to load the new key.

Cache Security
--------------

For sensitive research data, use encrypted caching:

.. code-block:: python

   from scholar_flux.sessions import EncryptionPipelineFactory, CachedSessionManager
   import os
   
   # Load or generate encryption key
   key = os.getenv('SCHOLAR_FLUX_CACHE_SECRET_KEY')
   encryption_factory = EncryptionPipelineFactory(key)
   
   # Create encrypted session
   serializer = encryption_factory()
   session_manager = CachedSessionManager(
       backend='redis',
       serializer=serializer
   )

.. seealso::
   See `SECURITY <https://github.com/SammieH21/scholar-flux?tab=security-ov-file>`_ for comprehensive security guidelines including cache encryption, network security, and vulnerability reporting.

Logging
-------

ScholarFlux includes built-in rotating logs. Configure via environment:

.. code-block:: bash

   SCHOLAR_FLUX_ENABLE_LOGGING=TRUE
   SCHOLAR_FLUX_LOG_LEVEL=INFO
   SCHOLAR_FLUX_LOG_DIRECTORY=/var/log/scholar-flux
   SCHOLAR_FLUX_PROPAGATE_LOGS=FALSE  # Prevent duplicate logs

Logs automatically rotate when they reach size limits. For custom logging:

.. code-block:: python

   import logging
   
   logger = logging.getLogger('scholar_flux')
   logger.setLevel(logging.INFO)
   
   # Add custom handlers as needed

Best Practices
==============

Configuration
-------------

✅ **Set ``SCHOLAR_FLUX_HOME``** for centralized configuration, caching, and logging

✅ Use environment-specific ``.env`` files in ``$SCHOLAR_FLUX_HOME``

✅ Validate required secrets on application startup

✅ Use prefixed variables (``SCHOLAR_FLUX_*``) for clarity in shared environments

**Example setup:**

.. code-block:: bash

   # Set up SCHOLAR_FLUX_HOME
   export SCHOLAR_FLUX_HOME=/opt/scholar-flux
   mkdir -p $SCHOLAR_FLUX_HOME/{package_cache,logs}
   
   # Create .env file
   cat > $SCHOLAR_FLUX_HOME/.env << 'EOF'
   SCHOLAR_FLUX_ENABLE_LOGGING=TRUE
   SCHOLAR_FLUX_LOG_LEVEL=INFO
   PUBMED_API_KEY=<insert_your_key>
   EOF

Caching
-------

✅ Use persistent backends (SQLite, Redis, MongoDB) for production

✅ Set appropriate TTL: 1-7 days for general research, 30+ days for archival

✅ Use namespaces: ``namespace='project_name'`` or ``namespace='user:123:project'``

✅ **Request caching** (HTTP responses): Off by default, enable with ``CachedSessionManager`` or ``use_cache=True``

✅ **Response caching** (processed data): In-memory by default, use ``DataCacheManager.with_storage()`` for persistence

✅ SQLite backends automatically use ``$SCHOLAR_FLUX_HOME/package_cache/`` when ``SCHOLAR_FLUX_HOME`` is set

See :doc:`caching_strategies` for detailed patterns.

Concurrency
-----------

✅ Use ``MultiSearchCoordinator`` for parallel provider searches

✅ Create new session per thread: ``session_manager()`` (sessions not thread-safe)

✅ Share ``DataCacheManager`` across threads (thread-safe)

See :doc:`multi_provider_search` for detailed threading patterns.

Data Management
---------------

✅ Always cite data sources in publications

✅ Check API terms of service for commercial use

✅ Implement proper data retention policies

✅ Consider GDPR/CCPA compliance for personal data

Security
--------

✅ Rotate API keys when possible (note: some providers only issue a single key)

✅ Use encrypted caching for sensitive queries

✅ Never log API keys (ScholarFlux masks them automatically)

✅ Monitor for security advisories on GitHub

✅ Keep ``.env`` files in ``$SCHOLAR_FLUX_HOME`` with restricted permissions (``chmod 600``)

Production Checklist
====================

Before deploying to production:

**Environment**

☐ Set up ``SCHOLAR_FLUX_HOME`` directory structure

☐ Create ``.env`` file in ``$SCHOLAR_FLUX_HOME`` with all required secrets

☐ Validate configuration on startup

☐ Verify write permissions for cache and log directories

**Caching**

☐ Deploy Redis or MongoDB for persistent caching

☐ Configure appropriate TTL for your use case

☐ Test cache connectivity before starting collection

**Security**

☐ Remove all hardcoded secrets from code

☐ Set up API key rotation schedule

☐ Review `SECURITY <https://github.com/SammieH21/scholar-flux?tab=security-ov-file>`_ guidelines

☐ Configure encrypted caching if handling sensitive data

**Testing**

☐ Test with small page ranges first

☐ Verify rate limiting works correctly

☐ Test failure recovery (API errors, network issues)

☐ Validate data quality and completeness

**Documentation**

☐ Document which providers and queries you're using

☐ Record data collection dates for reproducibility

☐ Plan for data citation in publications

☐ Document any provider-specific configurations

Next Steps
==========

You now understand production deployment essentials for ScholarFlux. Continue with:

**Related Guides:**

- :doc:`getting_started` - Installation and basic configuration
- :doc:`multi_provider_search` - Concurrent provider coordination
- :doc:`schema_normalization` - Building ML-ready datasets

**Advanced Topics:**

- :doc:`caching_strategies` - Advanced caching backends and patterns
- :doc:`advanced_workflows` - Multi-step retrieval workflows

**Reference:**

- `Security Guidelines <https://github.com/SammieH21/scholar-flux?tab=security-ov-file>`_ - Comprehensive security guidelines
- :doc:`custom_providers` - Adding new API providers
- `GitHub Issues <https://github.com/SammieH21/scholar-flux>`_ - Report bugs or request features

API Reference
-------------
- :class:`~scholar_flux.api.SearchAPI`
- :class:`~scholar_flux.api.SearchCoordinator`
- :class:`~scholar_flux.api.MultiSearchCoordinator`
- :class:`~scholar_flux.utils.ConfigLoader`
- :class:`~scholar_flux.data_storage.DataCacheManager`
- :class:`~scholar_flux.sessions.CachedSessionManager`


Getting Help
------------

For production deployment questions:

1. **Check documentation**: Especially :doc:`caching_strategies` and :doc:`multi_provider_search`
2. **GitHub Issues**: https://github.com/SammieH21/scholar-flux/issues
3. **Email**: scholar.flux@gmail.com
4. **Security issues**: Use GitHub Security Advisories (private reporting)

When reporting issues, include:

- ScholarFlux version: ``import scholar_flux; print(scholar_flux.__version__)``
- Python version and OS
- Cache backend (Redis/MongoDB/SQL)
- Relevant environment variables (mask secrets!)
- Complete error messages

---

**This is an MVP guide.** We'll expand with more patterns and examples as ScholarFlux matures toward v1.0. Feedback welcome!
