# Contributing to Scholar Flux

Thank you for your interest!

## Quick Start
1. Fork the repo
2. Install dev and testing dependencies: `poetry install`
3. Run tests: `poetry run tox` (runs tests) and `poetry run tox -e lint` (uses mypy and ruff fo lint the repository)
4. Submit PR

## Test Suite
This test uses a combination of tools to ensure that the code complies with PEP8 standards including:

- `pytest`: An automated test suite for the verification of the major assumptions of the code
- `mypy`: Verifying variable, class, and function typing to mitigate unforeseen errors with unexpected inputs
- `ruff`: For verifying the code format and quality
- `black`: To ensure that the code follows a consistent structure
- `interrogate`: To verify that all major classes and functions in the code is documented

## Our Focus

There are many more tools out there, but our aim is to ensure that whatever code and methods we use, it's vetted,
robust, and reliable. With that in mind, let's ensure that what we use, we also understand deeply enough to teach.

As the IT, analytical, and scientific landscape changes, our aim is to ensure that each contribution tackles
a key consideration in the formatting of for current use and future compatibility.

## Documentation

The code uses sphinx under the hood for automatic documentation generation using the docstrings of major classes,
functions, and variables.
