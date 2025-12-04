![ScholarFluxBanner](assets/Banner.png)

[![codecov](https://codecov.io/gh/sammieh21/scholar-flux/graph/badge.svg?token=D06ZSHP5GF)](https://codecov.io/gh/sammieh21/scholar-flux)
[![CI](https://github.com/SammieH21/scholar-flux/actions/workflows/ci.yml/badge.svg)](https://github.com/SammieH21/scholar-flux/actions/workflows/ci.yml)
[![CodeQL](https://github.com/SammieH21/scholar-flux/actions/workflows/github-code-scanning/codeql/badge.svg)](https://github.com/SammieH21/scholar-flux/actions/workflows/github-code-scanning/codeql)
[![Documentation Status](https://readthedocs.org/projects/mypy/badge/?version=latest)](https://mypy.readthedocs.io/en/latest/?badge=latest)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

[![Beta](https://img.shields.io/badge/status-beta-yellow.svg)](https://github.com/SammieH21/scholar-flux)
[![mypy: Type Checked](https://www.mypy-lang.org/static/mypy_badge.svg)](https://mypy-lang.org/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Linting: Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/charliermarsh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)



## Table of Contents

- **Home**: https://github.com/SammieH21/scholar-flux
- **Documentation**: https://SammieH21.github.io/scholar-flux/
- **Source Code**: https://github.com/SammieH21/scholar-flux/tree/main/src/scholar_flux
- **Contributing**: https://github.com/SammieH21/scholar-flux/blob/main/CONTRIBUTING.md
- **Code Of Conduct**: https://github.com/SammieH21/scholar-flux/blob/main/CODE_OF_CONDUCT.md
- **Issues**: https://github.com/SammieH21/scholar-flux/issues
- **Security**: https://github.com/SammieH21/scholar-flux/blob/main/SECURITY.md


## Overview

ScholarFlux is a production-grade orchestration layer for academic APIs that enables **concurrent multi-provider search with automatic rate limiting, streaming result delivery, and schema normalization**. Built for researchers, data engineers, and ML practitioners, ScholarFlux aggregates scientific data across multiple databases—arXiv, PubMed, Springer Nature, Crossref, OpenAlex, PLOS, and others—through a single unified interface.

Query 7+ scholarly databases simultaneously while ScholarFlux handles provider-specific quirks, rate limits, and response formats, delivering ML-ready datasets with consistent schemas.

### Why ScholarFlux?

Academic research requires querying multiple databases, but each provider implements their own parameter names, pagination mechanisms, rate limits, error conditions, and response formats. Building integrations with multiple academic APIs typically means:

- Manually coordinating rate limits across providers (6s for PLOS, 4s for arXiv, 1s for Crossref...)
- Writing custom parsers for XML (PubMed, arXiv) and JSON (Crossref, OpenAlex) responses
- Mapping **75+ inconsistent field names** across 8 providers (`title` vs `article_title` vs `headline`)
- Implementing retry logic and error handling for each API's quirks
- Building caching layers to avoid redundant requests

**Result**: Weeks of integration work just to retrieve data consistently.

**ScholarFlux handles those complexities** so researchers and data professionals can focus on research rather than API documentation.

### Key Innovations

- **🚀 Concurrent Thread Orchestration**: Maximizes throughput by querying multiple providers simultaneously with automatic rate limit coordination. While PLOS waits 6 seconds for rate limiting, arXiv, Crossref, and OpenAlex query in parallel—resulting in **3x faster retrieval** for multi-provider searches.

- **📡 Streaming Results**: Generator-based architecture delivers results as they arrive. Process page 1 while pages 2-100 are still being fetched—memory-efficient for large-scale retrieval.

- **🔒 Shared Rate Limiting**: Multiple queries to the same provider automatically coordinate through shared rate limiters. Query PubMed for "gene therapy" and "CRISPR" concurrently without exceeding rate limits.

- **🎯 Schema Normalization**: Automatically transforms provider-specific field names into universal academic fields (`title`, `doi`, `authors`, `abstract`). Build ML datasets without manual schema mapping.

- **🗄️ Two-Tier Caching**: HTTP response caching (Layer 1) + processed result caching (Layer 2) with Redis/MongoDB/SQLAlchemy support for production deployments.

- **🛡️ Security-First**: Automatic masking of API keys, emails, and credentials before logging. Optional encrypted session caching.

### Features

- **Rate limiting** - Automatically respects per-provider rate limits to avoid getting banned
- **Two-Layer caching** - Optionally caches successful requests and response processing to avoid sending redundant requests and performing unnecessary computation
- **Security-First** - Identifies and masks sensitive data (API keys, emails, credentials) before they ever grace the logs
- **Request preparation** - Configures provider-specific API parameters and settings for data retrieval
- **Response validation** - Verifies response structure before attempting to process data
- **Record processing** - Prepares, logs, and returns the intermediate data steps and the final processed results for full transparency
- **Concurrent orchestration** - Retrieves data from multiple APIs concurrently with multithreading while respecting individual rate limits
- **Intelligent Halting** - After unsuccessful requests, ScholarFlux knows when to retry a request or halt multi-page retrieval for a provider altogether

As a result, ScholarFlux offers a seamless experience in data engineering and analytical workflows, simplifying the process of querying academic databases, retrieving metadata, and performing comprehensive searches for articles, journals, and publications.


## Focus

- **Unified Access**: Aggregate searches across multiple academic databases and publishers.
- **Rich Metadata Retrieval**: Fetch detailed metadata for each publication, including authors, publication date, abstracts, and more.
- **Advanced Search Capabilities**: Support both simple searches and provider-specific, complex query structures to filter by publication date, authorship, and keywords.
- **Open Access Integration**: Prioritize and query open-access resources (for use within the terms of service for each provider).
- **Production-Ready Architecture**: Built with dependency injection, comprehensive error handling, and type safety for deployment in production environments.



## Architecture

ScholarFlux is built around three core components that work together through dependency injection:

```
SearchCoordinator
├── SearchAPI (HTTP retrieval + rate limiting)
│   ├── RateLimiter
│   ├── Session (requests or requests-cache)
│   ├── APIParameterMap (provider-specific parameter translation)
│   ├── SensitiveDataMasker (Masks and unmasks sensitive data when needed)
│   └── SearchAPIConfig (records per page, request delays, provider URL/name, API keys, etc.)
│
└── ResponseCoordinator (processing pipeline)
    ├── DataParser (XML/JSON/YAML → dict)
    ├── DataExtractor (dict → records list)
    ├── DataProcessor (records transformation)
    └── DataCacheManager (result storage)
```

### Concurrency Architecture

For multi-provider searches, ScholarFlux uses a sophisticated threading model with shared rate limiters:

```
MultiSearchCoordinator
├── Thread Pool (per-provider threads)
│   ├── Thread 1: PLOS (shared rate limiter across all PLOS queries)
│   │   └── Concurrent: query1_page1, query1_page2, query1_page3 → (waits 6s between)
│   ├── Thread 2: arXiv (shared rate limiter)
│   ├── Thread 3: OpenAlex (shared rate limiter)
│   └── Thread 4: Crossref (shared rate limiter)
│
├── Shared Rate Limiter Registry (cross-query coordination)
└── Generator Pipeline (streaming results via concurrent.futures.as_completed)
```

**Key Design Decisions**:
- **Threading over asyncio**: Simpler for users, better for I/O-bound workloads with rate limits. Academic APIs are pure I/O-bound with mandatory wait periods.
- **Generator-based streaming**: Memory-efficient, process results incrementally without blocking.
- **Shared rate limiters**: Multiple queries to the same provider coordinate through a single `ThreadedRateLimiter`, preventing rate limit violations.
- **Concurrent execution**: Maximizes throughput by requesting from all providers simultaneously within their rate limit constraints.

Each of these components are designed with a specific focus in mind:

- **SearchAPI**: Creates HTTP requests while handling the specifics of parameter building for provider-specific configurations
- **ResponseCoordinator**: Coordinates response handling (parsing → extraction → transformation → caching) while logging and validating each step of the process
- **SearchCoordinator**: Delegates and Orchestrates the entire process using the SearchAPI (response retrieval) and ResponseCoordinator (response processing)

Other components are designed to support the orchestration of each step in the process including:

- **SensitiveDataMasker**: Uses pattern matching to identify, mask, and register sensitive strings such as API Keys and Authorization Bearer tokens during critical steps before and after response retrieval
- **DataParser**: Parses responses of different types (XML, JSON, and YAML) into dictionaries to support later response handling processes
- **DataExtractor**: Extracts and separates both records and response metadata from parsed responses
- **DataProcessor**: Optionally filters and flattens records extracted from previous steps
- **DataCacheManager**: Provides storage abstraction supporting in-memory, Redis, MongoDB, and SQLAlchemy backends. The ResponseCoordinator detects schema changes and stale responses to determine whether or not to pull from cache

## Getting Started


### Prerequisites

- Python 3.10+
- [Poetry](https://python-poetry.org/) for dependency management
- An API key depending on the API Service Provider. This may be available through your academic institution or by registering directly with the API Provider

### Provider Access

While some APIs may require an API key, the majority of Providers do not.
OpenAlex, PLOS API, Crossref, and arXiv are four resources that work out-of-the-box and seamlessly for both single page and multi-page/provider retrieval, even with the default settings.

APIs such as PubMed, Core, and SpringerNature do, however, provide API access without payment or subscription for uses within the terms of service.

All sources do, however, have rate limits that users should abide by to prevent `Too Many Requests` status codes when requesting data.
Luckily, ScholarFlux handles this part automatically for you, as we'll see later!

## Installation

ScholarFlux is in the beta stage and is now available for testing on PyPI! You can install scholar-flux using the following command:


```bash
pip install scholar-flux
```

For out-of-the-box usability with minimal dependencies, ScholarFlux only requires a core set of packages by default. Several providers rely on different data processing strategies and may require additional dependencies. As a result, ScholarFlux makes these dependencies optional.

```bash
pip install scholar-flux[parsing,database,cryptography]
```

Or install specific features:
```bash
# Just parsing support
pip install scholar-flux[parsing]

# Database backends only
pip install scholar-flux[database]

# All extras (recommended for development)
pip install scholar-flux[parsing,database,cryptography]
```

### Or, To download the source code and documentation for testing and development:

1. **Clone the repository:**
```bash
git clone https://github.com/SammieH21/scholar-flux.git
```

2.  Navigate to the project directory:
```bash
cd scholar-flux
```
   
3.  Install dependencies using Poetry:
```bash
poetry install
```

3b. Or to download development tools, testing packages and dependencies for PubMed and arXiv processing:
```bash
poetry install --with dev --with tests --all-extras
```


**Requirements:**
- Python 3.10+
- Poetry (for development)
- Optional: Redis, MongoDB for production caching

**Provider-specific requirements:**
- PubMed: API key for rate limit increase (3 req/sec → 10 req/sec)
- Springer Nature: API key required
- Crossref: `mailto` parameter recommended for faster rate limits


**Optional Dependencies**
- **XML Parsing** (`parsing` extra): Required for providers like `PubMed` and `arXiv` that return XML responses
  - Installs: `xmltodict`, `pyyaml`
  
- **Encrypted Cache** (`cryptography` extra): Required for encrypted session caching
  - Installs: `cryptography`
  
- **Storage Backends** (`database` extra): Required for advanced caching strategies
  - `scholar_flux.data_storage.RedisStorage` → `redis`
  - `scholar_flux.data_storage.MongoDBStorage` → `pymongo`
  - `scholar_flux.data_storage.SQLAlchemyStorage` → `sqlalchemy`


**Note:** Tests automatically install all extras to ensure comprehensive testing across all features.

## Quick Start

### Basic Search

```python
from scholar_flux import SearchCoordinator

# Initializes a basic coordinator with a query and the default provider (PLOS)
coordinator = SearchCoordinator(query="machine learning", provider_name='plos')

# Get a single page
result = coordinator.search(page=1)

# ProcessedResponse is truthy, errors are falsy
if result:
    print(f"Got {len(result)} records")
    for record in result.data:
        print(f"{record.get('id')} - {record.get('title_display')}")
else:
    print(f"Error: {result.error}: Message: {result.message}")
```

### Multi-Page Retrieval with Caching

```python
from scholar_flux import SearchCoordinator, DataCacheManager

# Enable both HTTP caching and result caching
coordinator = SearchCoordinator(
    query="sleep",
    provider_name='plos',
    use_cache=True,  # Caches HTTP responses
    cache_manager=DataCacheManager.with_storage('redis')  # Caches processed results with redis on localhost
)

# Get multiple pages (rate limiting happens automatically)
results = coordinator.search_pages(pages=range(1, 3))

# Access the first ProcessedResponse
page_one = results[0]
print(page_one.provider_name)            # 'plos'
print(page_one.page)                     # page=1
response = page_one.response_result      # ProcessedResponse (if successful)

print(page_one.record_count)           # Total number of records
print(response.metadata)               # Total available
print(response.cache_key)              # 'plos_sleep_1_50'

# Filter out failures
successful_responses = results.filter()
print(f"Success rate: {len(successful_responses)}/{len(results)}")

# Aggregate response records into a DataFrame (this requires `pandas` to be installed)
import pandas as pd
df = pd.DataFrame(successful_responses.join())
print(df.columns)
# Index(['id', 'journal', 'eissn', 'publication_date', 'article_type',
#       'author_display', 'abstract', 'title_display', 'score', 'provider_name',
#       'page_number']

print(f'Total number of records: {df.shape[0]}')
```

## Core Features


### Two-Layer Caching

ScholarFlux caches at two levels: HTTP responses and processed results.

**Layer 1: Request caching**

Caches raw HTTP responses. If you make the same request twice, the second one is instant (no network call).

```python
from scholar_flux import SearchAPI, CachedSessionManager

# assumes you have the redis cache server installed on your local computer:
session_manager = CachedSessionManager(user_agent = 'ResearchEnthusiast', backend='redis')

api = SearchAPI.from_defaults(
    query="quantum computing",
    provider_name='arxiv',
    session = session_manager.configure_session(), # remove for a simple in-memory session caching
    use_cache=True # defaults to in-memory cache if a valid session cache isn't specified
)

response1 = api.search(page=1)  # Network request
# OUTPUT: <Response [200]>
response2 = api.search(page=1)  # Instant from cache
# OUTPUT: CachedResponse(...)
```

**Layer 2: Result caching**

Caches processed records after extraction and transformation. Useful when processing is expensive or when you want results to survive restarts.

```python
from scholar_flux import SearchCoordinator, DataCacheManager

# In-memory (default - fast, but lost on restart)
coordinator = SearchCoordinator(api)

# Redis (production - fast + persistent)
cache = DataCacheManager.with_storage('redis', 'localhost:6379')
coordinator = SearchCoordinator(api, cache_manager=cache)

# SQLAlchemy (archival - queryable)
cache = DataCacheManager.with_storage('sqlalchemy', 'postgresql://localhost/cache')
coordinator = SearchCoordinator(api, cache_manager=cache)

# MongoDB (document storage)
cache = DataCacheManager.with_storage('mongodb', 'mongodb://localhost:27017/')
coordinator = SearchCoordinator(api, cache_manager=cache)
```

### Concurrent Multi-Provider Search

Search multiple providers at the same time while respecting each one's rate limits.
Different providers return data in varying formats and field names which makes it difficult to standardize data for downstream research and analytics. ScholarFlux's normalization feature solves this problem by standardizing API-specific fields into common academic fields like `title`, `doi`, `authors`, `abstract`, etc.

```python
from scholar_flux import SearchCoordinator, MultiSearchCoordinator, RecursiveDataProcessor, CachedSessionManager
from scholar_flux.api.models import AcademicFieldMap

# Note: For production use, consider setting a custom user agent with contact information:
user_agent='MyResearchProject/1.0 (mailto:your.email@institution.edu)'
session_manager = CachedSessionManager(backend = 'sqlite', user_agent=user_agent)

# Sets up each coordinator: The RecursiveDataProcessor flattens record fields into path-value combinations  (i.e. `authors.affiliation.name`, `editor.affiliation`, etc.)
plos = SearchCoordinator(query="machine learning", provider_name='plos', processor = RecursiveDataProcessor(), session = session_manager())
crossref = SearchCoordinator(query="machine learning", provider_name='crossref', processor = RecursiveDataProcessor(), session = session_manager())
openalex = SearchCoordinator(query="machine learning", provider_name='openalex', processor = RecursiveDataProcessor(), session = session_manager())
arxiv = SearchCoordinator(query="machine learning", provider_name='arxiv', processor = RecursiveDataProcessor(), session = session_manager()) # requires `xmltodict`

# Runs each request using multithreading across providers while respecting rate-limits (the default)
multi = MultiSearchCoordinator()
# None of the following will require an API key
multi.add_coordinators([plos, crossref, openalex, arxiv])

# One call retrieves data from all providers in parallel
results = multi.search_pages(pages=range(1, 3))

# Responses are received in a SearchResultList:
print(results)

# OUTPUT: [query='machine learning' provider_name='arxiv' page=1 response_result=ProcessedResponse(cache_key='arxiv_machine learning_1_25', metadata='{'@xmlns:opensearch ': 'http://a9.com...}', data='[{'id': 'http://arxiv.org/abs/2306.0...] (25 items)')
#          query='machine learning' provider_name='arxiv' page=2 response_result=ProcessedResponse(cache_key='arxiv_machine learning_2_25', metadata='{'@xmlns:opensearch ': 'http://a9.com...}', data='[{'id': 'http://arxiv.org/abs/1811.0...] (25 items)')
#          query='machine learning' provider_name='plos' page=1 response_result=ProcessedResponse(cache_key='plos_machine learning_1_50', metadata='{'numFound': 28928, ' start': 1, 'max...}', data='[{'id': '10.1371/journal.pcbi.101271...] (50 items)')
#          query='machine learning' provider_name='plos' page=2 response_result=ProcessedResponse(cache_key='plos_machine learning_2_50', metadata='{'numFound': 28928, ' start': 51, 'ma...}', data='[{'id': '10.1371/journal.pone.024202...] (50 items)')
#          query='machine learning' provider_name='crossref' page=1 response_result=ProcessedResponse(cache_key='crossref_machine learning_1_25', metadata='{'status': 'ok', 'message-type': 'wo...}', data='[{'indexed.date-parts': '2025; 10; 3...] (25 items)')
#          query='machine learning' provider_name='crossref' page=2 response_result=ProcessedResponse(cache_key='crossref_machine learning_2_25', metadata='{'status': 'ok', 'message-type': 'wo...}', data='[{'indexed.date-parts': '2025; 3; 27...] (25 items)')
#          query='machine learning' provider_name='openalex' page=1 response_result=ProcessedResponse(cache_key='openalex_machine learning_1_25', metadata='{'count': 2520753, 'db_response_time...}', data='[{'id': 'https://openalex.org/W21012...] (25 items)')
#          query='machine learning' provider_name='openalex' page=2 response_result=ProcessedResponse(cache_key='openalex_machine learning_2_25', metadata='{'count': 2520753, 'db_response_time...}', data='[{'id': 'https://openalex.org/W21312...] (25 items)')

response_total = len(results)
successful_responses = len(results.filter())
print(f"{successful_responses} / {response_total} successful pages")


# Transform the list of response records into a searchable DataFrame:
import pandas as pd
# Filter out unsuccessful searches and normalize record fields into a list of dictionaries with universally mapped column names
normalized_records = results.filter().normalize()
# Transform the list of records into a pandas DataFrame
df = pd.DataFrame(normalized_records)

# Contains the full range of fields that are mapped for any given provider plus API-specific fields
universal_fields = [column for column in df.columns if column in AcademicFieldMap.model_fields.keys()]
provider_field_counts = df.groupby('provider_name')[universal_fields].count()
# Find fields that are populated for at least 3 of the 4 providers
filtered_fields = (provider_field_counts > 0).sum() >= 3
common_fields = filtered_fields[filtered_fields].index.tolist()

print(f"Fields commonly available across providers:")
print(common_fields)
print("\nRecord counts per provider for common fields:")
print(provider_field_counts[common_fields])

# OUTPUT: Fields commonly available across providers:
#         ['provider_name', 'doi', 'url', 'record_id', 'title', 'abstract', 'authors', 'journal', 'publisher', 'year', 'date_published', 'date_created', 'subjects', 'record_type']
#
#         Record counts per provider for common fields:
#                        provider_name  doi  url  record_id  title  abstract  authors  journal  publisher  year  date_published  date_created  subjects  record_type
#         provider_name
#         arxiv                     50    0   50         50     50        50       50       25          0    50              50            50        50            0
#         crossref                  50   50   50         50     50         3        0       47         50    49              49            50         0           50
#         openalex                  50   40   49         50     50         0       47       39         38    50              50            50        50           50
#         plos                     100  100    0        100    100        99      100      100        100   100             100           100       100          100 
```

### Performance: Real-World Impact

**Scenario**: Retrieve 1,250 records from 4 providers (PLOS, arXiv, OpenAlex, Crossref)

| Method | Time | Speedup |
|--------|------|---------|
| Sequential requests | ~18 min | Baseline |
| ScholarFlux concurrent threading | ~6 min | **3x faster** |

**Why?** ScholarFlux uses concurrent threads with shared rate limiters. While PLOS thread waits 6s for rate limiting, arXiv (4s), OpenAlex (6s), and Crossref (1s) threads query simultaneously. The more providers you query, the greater the optimization.

*Tested on: Standard laptop, stable connection*

### How Concurrent Orchestration Works

```python
# ❌ Sequential approach (traditional)
results_plos = plos.search()      # Request → wait 6 seconds
results_arxiv = arxiv.search()    # Request → wait 4 seconds  
results_crossref = crossref.search()  # Request → wait 1 second
# Total: 11 seconds for 3 requests (waits add up)

# ✅ ScholarFlux concurrent threading (default)
multi = MultiSearchCoordinator()
multi.add_coordinators([plos, arxiv, crossref])
results = multi.search(page=1)  # multithreading=True by default

# What happens:
# t=0s: Thread 1 requests PLOS (starts 6s timer)
# t=0s: Thread 2 requests arXiv (starts 4s timer)  
# t=0s: Thread 3 requests Crossref (starts 1s timer)
# t=1s: Crossref completes
# t=4s: arXiv completes
# t=6s: PLOS completes
# Total: ~6 seconds for 3 requests (concurrent execution)
```

This optimization compounds with multiple pages. For 10 pages across 4 providers, the speedup grows to **3x faster** than sequential retrieval.

For more details on threading behavior and optimization, see the [Multi-Provider Search Tutorial](https://SammieH21.github.io/scholar-flux/tutorials/multi_provider_search.html).

### Response Validation & Error Handling

ScholarFlux validates responses at multiple stages and gives you three distinct response types for clear error handling.

**Three response types:**

```python
from scholar_flux.api import NonResponse, ProcessedResponse, ErrorResponse, SearchCoordinator
coordinator = SearchCoordinator(query = 'sleep')
result = coordinator.search(page=1)

# ProcessedResponse (truthy) - when retrieval and processing are successful
if result:
    print(f"Success: {len(result.data)} records")
    print(f"Metadata: {result.metadata}")
    
# NonResponse (falsy) - couldn't reach the API or incorrect parameters/configurations
elif isinstance(result.response_result, NonResponse):
    print("Network error or API down")
    print(f"Error: {result.error}: Message: {result.message}")
    
# ErrorResponse (falsy) - either received an invalid response code or couldn't process it successfully
elif isinstance(result.response_result, ErrorResponse):
    print("Response received but response validation or processing  failed")
    print(f"Error: {result.error}: Message: {result.message}")
```


**Validation happens at every stage:**

1. **Request validation**: checks required parameters before sending
2. **Response structure**: verifies HTTP response is valid JSON/XML
3. **Schema validation**: checks parsed response has expected fields
4. **Record validation**: validates individual records before processing
5. **Cache validation**: checks cached data integrity before returning

### Rate Limiting

ScholarFlux implements relatively conservative rate limits that are adjusted to respect each provider's rate limits because these rate limits
can potentially change over time, each limit is set higher than the actual rate limit of each API to future-proof its defaults and avoid bans.

**Internally set ScholarFlux Rate limits:**
- **PLOS**: 6.1 seconds between requests
- **arXiv**: 4 seconds between requests
- **OpenAlex**: conservatively set to 6 seconds between requests: OpenAlex takes into account 5 metrics for the rate of requests received
- **PubMed**: 2 seconds between requests
- **Crossref**: 1 second between requests
- **Core**: 6 seconds between requests: the CORE API takes into account token usage instead of limiting by requests per second
- **Springer Nature**: 2 seconds between requests

When needed, these parameters can be modified directly when creating a SearchCoordinator or SearchAPI:

```python
# Rate limiting happens automatically:
coordinator = SearchCoordinator(query="sleep", provider_name='plos')

# Each request waits as needed to maintain the rate limit:
results = coordinator.search_pages(pages=range(1, 3))
```

**Override the default delay:**

```python
from scholar_flux import SearchAPIConfig

config = SearchAPIConfig(
    provider_name='plos',
    base_url='https://api.plos.org/search',
    request_delay=10.0  # Increase to 10 seconds
)

api = SearchAPI(query="topic", config=config)
coordinator = SearchCoordinator(api)
```

### Multi-Step Workflows

Some providers (like PubMed) require multiple API calls to get complete article data. ScholarFlux handles this automatically.

**PubMed workflow happens behind the scenes:**

1. **PubMedSearch**: Gathers a list of IDs that can be used use to fetch manuscripts in the next step
2. **PubMedFetch**: Retrieves each manuscript using the IDs from the search results of previous step 

```python
# This single call executes a two-step workflow automatically
coordinator = SearchCoordinator(query="neuroscience", provider_name='pubmed')
result = coordinator.search(page=1)

# Behind the scenes:
# Step 1: GET eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?term=neuroscience
# Step 2: GET eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?id=123,456,789

# Displays the final response of the workflow containing record data
print(result)
# OUTPUT: ProcessedResponse(len=20, cache_key='pubmedefetch_neuroscience_1_20', metadata={})

result.data # contains the final processed data set, including abstracts and metadata
```

See the [Advanced Workflows Tutorial](https://SammieH21.github.io/scholar-flux/tutorials/advanced_workflows.html) for examples of building custom multi-step workflows.

### Provider-Specific Configuration

Although the target use of ScholarFlux is scholarly metadata, articles, and manuscripts, as an API client, it can be extended to additional providers.

See the [Custom Provider Configuration Tutorial](https://SammieH21.github.io/scholar-flux/tutorials/custom_providers.html) for detailed examples of adding new providers to ScholarFlux.

## When to Use ScholarFlux

**ScholarFlux is ideal for:**
- ✅ Multi-provider searches (3+ academic databases)
- ✅ Large-scale retrieval (hundreds to thousands of records)
- ✅ ML/analytics requiring consistent schemas across providers
- ✅ Production deployments with caching and horizontal scaling
- ✅ Research projects requiring comprehensive database coverage

**Use provider-specific clients** (e.g., `habanero`, `biopython`, `arxiv`) when:
- ❌ You only need one database
- ❌ You need provider-specific advanced features not exposed by ScholarFlux

**Use raw `requests`/`httpx` when:**
- ❌ You're building a completely custom integration
- ❌ ScholarFlux's abstractions don't fit your use case

## How ScholarFlux Differs from Existing Packages

ScholarFlux is **not a replacement** for single-provider clients like `habanero`, `pybliometrics`, or `arxiv`. Instead, it's an **orchestration layer** that complements these tools for multi-provider research workflows.

### Architectural Differences

**Existing packages** (`habanero`, `pybliometrics`, `arxiv`, `metapub`, `scholarly`):
- Single-provider API wrappers
- Provider-specific response structures
- Basic or no caching
- Sequential request patterns
- Designed for provider-specific features

**ScholarFlux**:
- Multi-provider orchestration engine
- Unified schema normalization across providers
- Two-tier caching (HTTP + processed results)
- Concurrent threading with shared rate limiters
- Production-ready architecture (Redis, MongoDB, SQLAlchemy)

### Feature Comparison

| Feature | ScholarFlux | habanero | pybliometrics | arxiv | metapub |
|---------|-------------|----------|---------------|-------|---------|
| **Multi-provider concurrent execution** | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Shared rate limiter coordination** | ✅ | ❌ | ⚠️ Single provider | ❌ | ⚠️ Single provider |
| **Two-tier caching system** | ✅ | ❌ | ⚠️ Basic file cache | ❌ | ❌ |
| **Cross-provider schema normalization** | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Streaming generator results** | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Multi-step workflow automation** | ✅ | ❌ | ❌ | ❌ | ⚠️ PubMed only |
| **Production cache backends** | ✅ Redis, MongoDB, SQL | ❌ | ⚠️ File system | ❌ | ❌ |
| **Security features** (credential masking) | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Type safety** (mypy strict) | ✅ | ⚠️ Partial | ⚠️ Partial | ⚠️ Partial | ❌ |

### Real-World Scenario

**Without ScholarFlux** (using individual packages):
```python
# Researcher needs data from 4 sources
from habanero import Crossref
import arxiv
from pymed import PubMed

# Manual threading implementation needed
# Manual rate limiting for each provider
# Manual schema normalization
# Manual caching layer
# Manual error handling for each API
# Result: 200+ lines of boilerplate code
```

**With ScholarFlux**:
```python
from scholar_flux import SearchCoordinator, MultiSearchCoordinator

# Automatic concurrent execution with rate limiting
coordinators = [
    SearchCoordinator(query="CRISPR", provider_name='crossref'),
    SearchCoordinator(query="CRISPR", provider_name='arxiv'),
    SearchCoordinator(query="CRISPR", provider_name='pubmed'),
    SearchCoordinator(query="CRISPR", provider_name='plos')
]

multi = MultiSearchCoordinator()
multi.add_coordinators(coordinators)
results = multi.search_pages(pages=range(1, 10))

# Automatic normalization to common schema
df = pd.DataFrame(results.filter().normalize())
# Result: 10 lines, production-ready
```

### What ScholarFlux Adds

1. **Concurrent Orchestration**: Query 7+ providers simultaneously with automatic rate limit coordination—**3x faster** than sequential retrieval
2. **Schema Unification**: Normalize **75+ provider-specific fields** into consistent academic schema (`title`, `doi`, `authors`, `abstract`)
3. **Production Infrastructure**: Redis/MongoDB/SQL caching, credential masking, comprehensive error handling
4. **Workflow Automation**: Handle multi-step APIs (PubMed's search→fetch) transparently
5. **Memory Efficiency**: Stream results as they arrive—process page 1 while fetching page 100

### When to Use Each Approach

**Use provider-specific packages** (`habanero`, `arxiv`, `pybliometrics`) when:
- ✅ You need **one database** with provider-specific advanced features
- ✅ You want **fine-grained control** over provider-specific parameters
- ✅ You're building **provider-specific workflows** not covered by ScholarFlux

**Use ScholarFlux** when:
- ✅ You need **3+ databases** queried concurrently
- ✅ You need **consistent schemas** for ML/analytics pipelines
- ✅ You're building **production systems** requiring caching, monitoring, and horizontal scaling
- ✅ You want **rapid prototyping** without writing orchestration boilerplate

**Complementary use**: ScholarFlux can be extended to wrap existing packages for providers it doesn't support natively. See the [Custom Provider Tutorial](https://SammieH21.github.io/scholar-flux/tutorials/custom_providers.html).

For a detailed comparison with alternatives, see the [documentation](https://SammieH21.github.io/scholar-flux/).

## Documentation

**Comprehensive tutorials and API reference**: https://SammieH21.github.io/scholar-flux/

### 📚 Core Tutorials

- **[Getting Started](https://SammieH21.github.io/scholar-flux/tutorials/getting_started.html)** - Installation through first search
- **[Multi-Provider Search](https://SammieH21.github.io/scholar-flux/tutorials/multi_provider_search.html)** - Concurrent orchestration and streaming results
- **[Schema Normalization](https://SammieH21.github.io/scholar-flux/tutorials/schema_normalization.html)** - Building ML-ready datasets across providers

### 🔧 Advanced Topics

- **[Caching Strategies](https://SammieH21.github.io/scholar-flux/tutorials/caching_strategies.html)** - Two-tier caching with Redis, MongoDB, SQLAlchemy
- **[Custom Providers](https://SammieH21.github.io/scholar-flux/tutorials/custom_providers.html)** - Extending ScholarFlux to new APIs
- **[Advanced Workflows](https://SammieH21.github.io/scholar-flux/tutorials/advanced_workflows.html)** - Multi-step retrieval and custom pipelines
- **[Production Deployment](https://SammieH21.github.io/scholar-flux/tutorials/production_deployment.html)** - Docker, Kubernetes, monitoring

### Contributing

We welcome contributions from the community! If you have suggestions for improvements or new features, please feel free to fork the repository and submit a pull request. Please refer to our [Contributing Guidelines](CONTRIBUTING.md) for more information on how you can contribute to the ScholarFlux API.

### License

This project is licensed under the Apache License 2.0.

[Apache License 2.0 Official Text](http://www.apache.org/licenses/LICENSE-2.0)


See the LICENSE file for the full terms.

### NOTICE

The Apache License 2.0 applies only to the code and gives no rights to the underlying data. Be sure to reference the terms of use for each provider to ensure that your use is within their terms.


### Acknowledgments

Thanks to Springer Nature, Crossref, PLOS, PubMed and other Providers for providing public access to their academic databases through the respective APIs.
This project uses Poetry for dependency management and requires Python 3.10 or higher.

### Contact

Questions or suggestions? Open an issue or email scholar.flux@gmail.com.

---

## 📈 Project Stats

- **96% Test Coverage** (24.5k LOC production code, 15k LOC tests)
- **7 Default Providers** with schema normalization support
- **Type-Safe Architecture** (mypy strict mode, comprehensive type hints)
- **Security-Audited** (automated CVE scanning via CodeQL and Safety CLI, credential masking)
- **Beta Status** (v0.3.0 - production-ready for early adopters)

---

**Built with ❤️ for researchers, data engineers, and ML practitioners who may one day become analytical pioneers
