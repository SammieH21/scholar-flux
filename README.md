# ScholarFlux

The Scholar Flux API is an open-source project designed to streamline access to academic and scholarly resources across various platforms. It offers a unified API that simplifies querying academic databases, retrieving metadata, and performing comprehensive searches within scholarly articles, journals, and publications.

## Features

- **Unified Access**: Aggregate searches across multiple academic databases and publishers.
- **Rich Metadata Retrieval**: Fetch detailed metadata for each publication, including authors, publication date, abstracts, and more.
- **Advanced Search Capabilities**: Supports complex query structures to filter by fields such as publication date, authorship, and keywords.
- **Open Access Integration**: Prioritize or exclusively query open-access resources for unrestricted use.

## Getting Started

### Prerequisites

- Python 3.8+
- [Poetry](https://python-poetry.org/) for dependency management
- A Springer API key, which may be available through your academic institution or by [registering directly with Springer](https://developer.springernature.com/).

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/sammi/ScholarFluxAPI.git
   ```
2.  Navigate to the project directory:

    ```bash
    cd ScholarFlux
    ```
   
3  Install dependencies using Poetry:

    ```bash
    poetry install
    ```
### Configuration

Before using the Scholar Flux API, you need to configure your Springer API key:

    Create a .env file in the project root directory.
    Add the following line, replacing your_api_key_here with your actual Springer API key:

    ```makefile
    SPRINGER_API_KEY=your_api_key_here
    ```
### Usage

Below is a simple example of how to use the API to perform a search query:

```python
# Example Python code to demonstrate a simple query
from scholar_flux import scholar_flux

# Initialize the API client
client = ScholarFlux(api_key="your_api_key_here")

# Perform a search
results = client.search("quantum computing")
print(results)
```

### Contributing

We welcome contributions from the community! If you have suggestions for improvements or new features, please feel free to fork the repository and submit a pull request. Please refer to our Contributing Guidelines for more information on how you can contribute to the Scholar Flux API.

### License

This project is licensed under the Apache License 2.0 and to link to the `LICENSE` file in your repository. This informs users and contributors about the legal terms under which your software is provided.

### LICENSE File

This project is licensed under Apache License 2.0.

[Apache License 2.0 Official Text](http://www.apache.org/licenses/LICENSE-2.0)


### Acknowledgments

    Thanks to Springer Nature for providing access to their academic databases through the Springer API.
    This project uses Poetry for dependency management.

### Contact

For questions, suggestions, or issues regarding ScholarFlux, please open an issue on GitHub or contact us directly at sammiehstat@gmail.com.
