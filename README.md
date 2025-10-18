![ScholarFluxBanner](assets/Banner.png)

[![codecov](https://codecov.io/gh/sammieh21/scholar-flux/graph/badge.svg?token=D06ZSHP5GF)](https://codecov.io/gh/sammieh21/scholar-flux)
[![CI](https://github.com/SammieH21/scholar-flux/actions/workflows/ci.yml/badge.svg)](https://github.com/SammieH21/scholar-flux/actions/workflows/ci.yml)o

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Beta](https://img.shields.io/badge/status-beta-yellow.svg)](https://github.com/SammieH21/scholar-flux)


The ScholarFlux API is an open-source project designed to streamline access to academic and scholarly resources across various platforms. It offers a unified API that simplifies querying academic databases, retrieving metadata, and performing comprehensive searches within scholarly articles, journals, and publications.
In addition, this API has built in extension capabilities for applications in News retrieval and other domains.

## Features

- **Unified Access**: Aggregate searches across multiple academic databases and publishers.
- **Rich Metadata Retrieval**: Fetch detailed metadata for each publication, including authors, publication date, abstracts, and more.
- **Advanced Search Capabilities**: Supports complex query structures to filter by fields such as publication date, authorship, and keywords.
- **Open Access Integration**: Prioritize or exclusively query open-access resources for unrestricted use.

## Getting Started

### Prerequisites

- Python 3.10+
- [Poetry](https://python-poetry.org/) for dependency management
- An API key depending on the API Service Provider. This may be available through your academic institution or by registering directly with the API Provider

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/sammih21/scholar-flux.git
   ```
2.  Navigate to the project directory:

    ```bash
    cd ScholarFlux
    ```
   
3  Install dependencies using Poetry:

    ```bash
    poetry install
    ```

### Usage

Below is a simple example of how to use the API to perform a search query:

```python
# Example Python code to demonstrate a simple query
from scholar_flux import SearchAPI, SearchCoordinator, DataCacheManager

# Initialize the API client with requests-cache to cache successful responses
api = SearchAPI.from_defaults(query = "psychology", provider_name='plos', use_cache = True)

# Perform a search and get a response object:
response = api.search(page = 1)

# Coordinate the response retrieval processing with a single search and in-memory record cache:
coordinator = SearchCoordinator(api, )

# Turn off process caching altogether:
coordinator = SearchCoordinator(api, cache_results = False)

# Or use sqlalchemy, redis, or mongodb with an optional config assuming a redis server and redis-py are installed:
coordinator = SearchCoordinator(api, cache_manager = DataCacheManager.with_storage('redis', 'localhost'))

 # retrieves the previously cached response and processes it
processed_response = coordinator.search(page = 1)

# Show each record from a flattened dictionary:
print(processed_response.data)

# Transform the dictionary of records into a pandas dataframe:
import pandas as pd
record_data_frame = pd.DataFrame(processed_response.data)

# Displaying Each record in a table, line-by-line
print(record_data_frame.head(5))

# And to view each record's metadata:
print(processed_response.metadata)

# Afterward, the search begins anew:
processed_response_two = coordinator.search(page = 2)
```

### Contributing

We welcome contributions from the community! If you have suggestions for improvements or new features, please feel free to fork the repository and submit a pull request. Please refer to our Contributing Guidelines for more information on how you can contribute to the ScholarFlux API.

### License

Apache License 2.0


This project is licensed under the Apache License 2.0 and to link to the `LICENSE` file in your repository. This informs users and contributors about the legal terms under which your software is provided here:

[Apache License 2.0 Official Text](http://www.apache.org/licenses/LICENSE-2.0)


See the LICENSE file for the full terms.

### NOTICE

The Apache License 2.0 applies only to the code only and gives no rights to the underlying data. Be sure to reference the terms of use for each provider to ensure that your use is within their terms.


### Acknowledgments

    Thanks to Springer Nature, Crossref, PLOS, PubMed and other Providers for providing public access to their academic databases through the respective APIs.
    This project uses Poetry for dependency management and requires python 3.10 or higher.

### Contact

Questions or suggestions? Open an issue or email scholar.flux@gmail.com.
