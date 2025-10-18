.. scholar_flux documentation master file, created by
   sphinx-quickstart on Tue Oct 14 02:35:36 2025.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to Scholar Flux's documentation!
=========================================

Scholar Flux is a Python library for searching and processing academic articles from multiple providers with built-in caching and data management capabilities.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   api/modules

Getting Started
===============

Installation
------------

The scholar-flux module is currently in beta, and is available right now for testing and preliminary use! Install Scholar Flux using pypi index for testing:

.. code-block:: bash

   pip install --extra-index-url https://test.pypi.org/simple/ scholar-flux --pre

Quick Start Example
===================

Here's a complete example demonstrating Scholar Flux's core features:

.. code-block:: python

   from scholar_flux import SearchAPI, SearchCoordinator, DataCacheManager
   
   # Initialize the API client with requests-cache to cache successful responses
   api = SearchAPI.from_defaults(
       query="psychology", 
       provider_name='plos', 
       use_cache=True
   )
   
   # Perform a search and get a response object
   response = api.search(page=1)
   
   # Coordinate the response retrieval processing with a single search 
   # and in-memory record cache
   coordinator = SearchCoordinator(api)
   
   # Turn off process caching altogether
   coordinator = SearchCoordinator(api, cache_results=False)
   
   # Or use sqlalchemy, redis, or mongodb with an optional config
   # (assuming a redis server and redis-py are installed)
   coordinator = SearchCoordinator(
       api, 
       cache_manager=DataCacheManager.with_storage('redis', 'localhost')
   )
   
   # Retrieves the previously cached response and processes it
   processed_response = coordinator.search(page=1)
   
   # Show each record from a flattened dictionary
   print(processed_response.data)
   
   # Transform the dictionary of records into a pandas dataframe
   import pandas as pd
   record_data_frame = pd.DataFrame(processed_response.data)
   
   # Display each record in a table, line-by-line
   print(record_data_frame.head(5))
   
   # View each record's metadata
   print(processed_response.metadata)
   
   # Search the next page
   processed_response_two = coordinator.search(page=2)

Key Features
============

* **Multiple Provider Support**: Search across different academic databases
* **Smart Caching**: Built-in request caching with requests-cache
* **Flexible Storage**: In-memory, Redis, MongoDB, or SQLAlchemy backends
* **Data Processing**: Transform responses into pandas DataFrames
* **Response Management**: Coordinate searches with automatic caching

API Reference
=============

For detailed API documentation, see the :doc:`modules` section.

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
