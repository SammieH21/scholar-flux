![ScholarFluxBanner](assets/Banner.png)

[![codecov](https://codecov.io/gh/sammieh21/scholar-flux/graph/badge.svg?token=D06ZSHP5GF)](https://codecov.io/gh/sammieh21/scholar-flux)
[![CI](https://github.com/SammieH21/scholar-flux/actions/workflows/ci.yml/badge.svg)](https://github.com/SammieH21/scholar-flux/actions/workflows/ci.yml)

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Beta](https://img.shields.io/badge/status-beta-yellow.svg)](https://github.com/SammieH21/scholar-flux)



## Table of Contents

- **Home**: https://github.com/SammieH21/scholar-flux
- **Documentation**: https://SammieH21.github.io/scholar-flux/
- **Source Code**: https://github.com/SammieH21/scholar-flux/tree/main/src/scholar_flux
- **Contributing**: https://github.com/SammieH21/scholar-flux/blob/main/CONTRIBUTING.md
- **Code Of Conduct**: https://github.com/SammieH21/scholar-flux/blob/main/CODE_OF_CONDUCT.md
- **Issues**: https://github.com/SammieH21/scholar-flux/issues
- **Security**: https://github.com/SammieH21/scholar-flux/blob/main/SECURITY.md


## Overview

The ScholarFlux API is an open-source production-grade client library designed to streamline and aggregate scientific data across several databases
and APIs such as arXiv, PubMed, Springer Nature, Crossref, and others — all through a single unified interface. ScholarFlux handles the often all-too-complex
aspects of working with academic databases.

### Why ScholarFlux?

Oftentimes, when working with scientific APIs, news APIs, or APIs of nearly any type, understanding the documentation is a feat in and of itself— each source
implements their provider-specific names for common parameters, mechanisms of pagination (if any), error conditions, rate limits, and response formats.
ScholarFlux handles those complexities so that researchers, data professionals, and others who love research can focus on research, rather than documentation.

### Features

- **Rate limiting** - Automatically respects per-provider rate limits to avoid getting banned
- **Two-Layer caching** - Optionally caches successful requests and response processing to avoid sending redundant requests and performing unnecessary computation
- **Security-First** - Identifies and masks sensitive data (API keys, emails, credentials) before they ever grace the logs
- **Request preparation** - Configures provider-specific API parameters and settings for data retrieval
- **Response validation** - Verifies response structure before attempting to process data
- **Record processing** - Prepares, logs, and returns the intermediate data steps and the final processed results for full transparency
- **Workflow orchestration** - Retrieves data from multiple APIs concurrently with multithreading while respecting individual rate limits
- **Intelligent Halting** - After unsuccessful requests, ScholarFlux knows when to retry a request or halt multi-page retrieval for a provider altogether

As a result, ScholarFlux offers a seamless experience in data engineering and analytical workflows, simplifying the process of querying academic databases,
retrieving metadata, and performing comprehensive searches for articles, journals, and publications.


## Focus

- **Unified Access**: Aggregate searches across multiple academic databases and publishers.
- **Rich Metadata Retrieval**: Fetch detailed metadata for each publication, including authors, publication date, abstracts, and more.
- **Advanced Search Capabilities**: Support both simple searches and provider-specific, complex query structures to filter by publication date, authorship, and keywords.
- **Open Access Integration**: Prioritize and query open-access resources (for use within the terms of service for each provider).



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

print(len(response.data))              # Total number of records
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
    session = session_manager.configure_session(), # remove for a simple in-memory storage
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

```python
from scholar_flux import SearchCoordinator, MultiSearchCoordinator, RecursiveDataProcessor

# Sets up each coordinator: The RecursiveDataProcessor flattens record fields into path-value combinations  (i.e. `authors.affiliation.name`, `editor.affiliation`, etc.)
plos = SearchCoordinator(query="machine learning", provider_name='plos', processor = RecursiveDataProcessor())
crossref = SearchCoordinator(query="machine learning", provider_name='crossref', processor = RecursiveDataProcessor())
core = SearchCoordinator(query="machine learning", provider_name='core', processor = RecursiveDataProcessor())

# Runs each request using multithreading across providers while respecting rate-limits (the default)
multi = MultiSearchCoordinator()
multi.add_coordinators([plos, crossref, core])

# One call retrieves data from all providers in parallel
results = multi.search_pages(pages=range(1, 3))

# Responses are received in a SearchResultList:
print(results)
response_total = len(results)

# OUTPUT: [SearchResult(query='machine learning', provider_name='core', page=1, response_result=ProcessedResponse(len=10, cache_key='core_machine learning_1_25', metadata="{'totalHits': 2153137, 'limit': 25, 'off...}")),
#          SearchResult(query='machine learning', provider_name='plos', page=1, response_result=ProcessedResponse(len=50, cache_key='plos_machine learning_1_50', metadata="{'numFound': 28560, 'start': 1, 'maxScor...}")),
#          SearchResult(query='machine learning', provider_name='plos', page=2, response_result=ProcessedResponse(len=50, cache_key='plos_machine learning_2_50', metadata="{'numFound': 28560, 'start': 51, 'maxSco...}")),
#          SearchResult(query='machine learning', provider_name='crossref', page=1, response_result=ProcessedResponse(len=25, cache_key='crossref_machine learning_1_25', metadata="{'status': 'ok', 'message-type': 'work-l...}")),
#          SearchResult(query='machine learning', provider_name='crossref', page=2, response_result=ProcessedResponse(len=25, cache_key='crossref_machine learning_2_25', metadata="{'status': 'ok', 'message-type': 'work-l...}"))]

successful_responses = len(results.filter())
print(f"{successful_responses} / {response_total} successful pages")


# transform the list of response records into a searchable DataFrame:
import pandas as pd 
data = results.join() # filters out unsuccessful and joins response records into a single list of dictionaries
df = pd.DataFrame(data)

# Filter to relevant fields
relevant_fields = ['doi', 'title', 'abstract', 'text']
columns = [col for col in df.columns if col in relevant_fields]
df[columns].describe()

# OUTPUT:                                                       abstract                      doi                                              title
#         count                                                 111                        6                                                 60
#         unique                                                111                        6                                                 57
#         top     Machine Learning (ML) is the discipline that s...  10.1145/3183440.3183461  Einleitung: Vom Batch Machine Learning zum Onl...
#         freq                                                    1                        1                                                  2
```

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

# The Console shows:
# Handling response (cache key: plos_sleep_1_50)
# No cached data for key: 'plos_sleep_1_50'
# processing response: plos_sleep_1_50
# adding_to_cache
# DEBUG - Cache updated for key: plos_sleep_1_50
# Data processed for plos_sleep_1_50
# sleeps for the remaining duration from when the last response was received
# INFO - RateLimiter: sleeping 5.78s to respect rate limit
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

**Custom workflows:**

Sometimes, for more advanced data retrieval scenarios, you may need to implement multi-step data retrieval and processing procedures using workflows.
You can build your own multi-step workflows by subclassing `WorkflowStep`.

The following example displays how each step of the PubMed workflow, after creation, is used in the backend

```python
from scholar_flux.api.workflows import SearchWorkflow, PubMedSearchStep, PubMedFetchStep
from scholar_flux.api import SearchCoordinator

# Note that the workflow is already pulled from the defaults behind the scenes, so you don't have to define it.
pubmed_workflow = SearchWorkflow(steps = [PubMedSearchStep(), PubMedFetchStep()])

# Applies the workflow
coordinator = SearchCoordinator(query = 'gene therapy',
                                provider_name = 'pubmed',
                                workflow = pubmed_workflow)

# Uses the workflow automatically and returns the same result as before
result = coordinator.search(page = 1)
```


### Provider-Specific Configuration

Although the target use of ScholarFlux is scholarly metadata, articles, and manuscripts, as an API client, it can be used for far more with applications
to news retrieval, business article parsing, medical APIs, etc.


The following example demonstrates how the API can be extended to the news source, Guardian:

```python
from scholar_flux.api import APIParameterMap, ProviderConfig, SearchCoordinator, provider_registry

parameters = APIParameterMap(query='q', # Defines the name of the query parameter understood by the Guardian API
                             start='page', # Maps the `start` page/record to the `page` field on the API
                             records_per_page='page-size', # Parameter that indicates how many records to fit on a page in a response
                             api_key_parameter='api-key', # Indicates what the API key parameter is called if available
                             auto_calculate_page=False, # If True, calculates start position from page number and records_per_page
                             zero_indexed_pagination=False, # The first record starts from start=1 and not start=0
                             api_key_required=True) # Indicate that an error needs to be raised if missing

# Defines the basic configuration necessary to temporarily or permanently and add the Guardian API to the registry for the python session
guardian_config = ProviderConfig(provider_name = 'GUARDIAN', # Alias for the Guardian API
                                 parameter_map = parameters, # Translates the language of parameters spoken by the API
                                 base_url = 'https://content.guardianapis.com//search', # indicates WHERE the guardian URL is actually found
                                 records_per_page=10, # Defines the default records per page if not defined when creating a SearchCoordinator
                                 api_key_env_var='GUARDIAN_API_KEY', # Looks here in the OS environment for the API key if not directly specified 
                                 request_delay=6) # Wait a total of 6 seconds after a single request to send the next

provider_registry.add(guardian_config)

coordinator = SearchCoordinator(query="quantum mechanics", provider_name = 'Guardian') # Not caps sensitive

response = coordinator.search(page = 1)
# OUTPUT: ProcessedResponse(len=10, cache_key='guardian_quantum mechanics_1_10', metadata="{'status': 'ok', 'userTier': 'developer'...}")
```

## Documentation

For comprehensive documentation including:
- Workflows and custom components
- Detailed API references
- Extension examples

Visit the [Sphinx documentation](https://SammieH21.github.io/scholar-flux/).

### Contributing

We welcome contributions from the community! If you have suggestions for improvements or new features, please feel free to fork the repository and submit a pull request. Please refer to our Contributing Guidelines for more information on how you can contribute to the ScholarFlux API.

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
