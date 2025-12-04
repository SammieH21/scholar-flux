# Contributing to ScholarFlux

Thank you for your interest in ScholarFlux!

If you wish to contribute to our growth as a member of the team, it's important to know our aims, focus, and philosophy in data engineering and software design.

## Our Aim

Many tools exist today that can facilitate the retrieval of scientific and scholarly information, but, as far as we've seen, none provide a unified client that can integrate and orchestrate API retrieval across multiple providers.

### Enter ScholarFlux

Using modern software design principles and a focus on growth and testing, we're seeking to fill that gap. We sought to provide a single production-grade client that allows for the smooth retrieval and processing of scholarly data from sources such as PubMed, Crossref, SpringerNature, and others, with even more to come. In doing so, we aim to provide an extensible set of tools in the process that can be useful for data engineers, researchers, data scientists, and just about anyone else who loves working with research!

To support this mission, ScholarFlux includes 8 comprehensive tutorials covering everything from basic usage through production deployment—ensuring contributors and users alike have clear, working examples to learn from.

## Our Philosophy

### *The Whole is Greater than the Sum of Its Parts* — Aristotle

ScholarFlux is designed to be an extensible solution that delegates responsibility in data retrieval, security, processing, and caching to components that specialize in that area. Each module, while containing vital features in the orchestration of API workflows, is designed as a distinct library in and of itself.

### Modules

- **scholar_flux.api**: The core module that integrates all other steps to produce the coordinated response retrieval and processing that gives ScholarFlux its purpose
- **scholar_flux.security**: Contains the building blocks for masking with sensitive string pattern matching with applications that can extend to future frameworks requiring security when managing secrets, API keys, and other forms of sensitive data
- **scholar_flux.data_storage**: Creates the caching and data storage backends that support the processing and preparation of response records and metadata. It defines custom implementations supporting the use of SQL, In-Memory, Redis, MongoDB based on a common class that defines how data processing cache should operate
- **scholar_flux.sessions**: Implements CachedSessionManagers that can be used to easily create and reproduce the sessions that send and cache requests
- **scholar_flux.data**: Produces the core classes and implementations used in the orchestration of response handling steps for response parsing → record extraction → data processing/transformation
- **scholar_flux.utils**: Contains the backbone of all reusable helper functions that support ScholarFlux in ways unsung, ranging from package initialization, robust configuration loading and processing utilities

The benefits of this level of modularization and separation of concerns are enormous:

1. Those who specialize in a specific area can easily contribute their area of expertise
2. Developers can easily integrate ScholarFlux utilities and its core building blocks into the open source projects of the future
3. Debugging is less of a headache, and errors can be more easily traced and resolved for faster bug fixes

## Our Focus

There are many more tools out there, but our aim is to ensure that whatever code and methods we use, they're vetted, robust, and reliable. With that in mind, let's ensure that what we use, we also understand deeply enough to teach.

As the IT, analytical, and scientific landscape changes, our aim is to ensure that each contribution tackles a key consideration in the formatting for current use and future compatibility.

## Quick Start

### Prerequisites

- Python 3.10 or higher
- Poetry (install: `curl -sSL https://install.python-poetry.org | python3 -`)
- Git

### Setup Steps

1. **Fork and clone the repository**
   ```bash
   git clone https://github.com/YOUR-USERNAME/scholar-flux.git
   cd scholar-flux
   ```

2. **Install all dependencies**
   ```bash
   # Install with all extras and dev dependencies
   poetry install --all-extras --with dev,testing,docs
   ```

3. **Set up environment variables** (optional but recommended for testing)
   ```bash
   # Create a .env file in the project root
   # Add your API keys (tests will work without them using mocked responses):
   # ARXIV_API_KEY=your_key_here
   # SPRINGER_NATURE_API_KEY=your_key_here
   # CROSSREF_API_KEY=your_key_here
   # CORE_API_KEY=your_key_here
   # PUBMED_API_KEY=your_key_here
   # OPEN_ALEX_API_KEY=your_key_here
   
   # See our Security Policy for best practices: SECURITY.md
   ```

4. **Run the test suite**
   ```bash
   # Run tests for your Python version
   poetry run pytest tests -rsx -vv
   
   # Or use tox to test all Python versions (3.10, 3.11, 3.12, 3.13, optionally 3.14)
   poetry run tox
   ```

5. **Verify code quality**
   ```bash
   poetry run tox -e lint
   ```

6. **Make your changes and submit a PR!**

## Understanding Extras

ScholarFlux uses optional dependency groups for different features:

- **`database`**: SQLAlchemy, Redis, and MongoDB support for advanced caching
- **`cryptography`**: Enhanced cache encryption capabilities
- **`parsing`**: XML and YAML parsing for various API responses

### Installing Specific Extras

```bash
# Install only what you need
poetry install --extras "database cryptography"

# Install all extras (recommended for development)
poetry install --all-extras
```

**Note:** All test environments automatically install all extras to ensure comprehensive testing.

## API Keys for Testing

ScholarFlux integrates with multiple academic APIs. For full testing, you may need API keys:

### Supported APIs

- `ARXIV_API_KEY`
- `OPEN_ALEX_API_KEY`
- `SPRINGER_NATURE_API_KEY`
- `CROSSREF_API_KEY`
- `CORE_API_KEY`
- `PUBMED_API_KEY`

### Setup

1. Create a `.env` file in the project root or in `$HOME/.scholar_flux` (never commit this!)
2. Add your API keys (optional - tests use mocked responses by default)
3. Before sending a pull request, verify that, after each commit, you haven't inadvertently committed an api key: `git grep $PUBMED_API_KEY $(git rev-list --all)`
4. See our [Security Policy](SECURITY.md) for best practices on handling credentials

**Note:** All tests use mocked responses, so API keys are optional for basic development. They're only required if you're testing actual API integrations on live data from PubMed, Core, and SpringerNature.
OpenAlex, PLOS API, Crossref, and arXiv are four resources that don't, however, require API Keys and work out-of-the-box.

### Enabling Debug Logging

By default, ScholarFlux runs with minimal logging (WARNING level and above). If you need detailed logs for development or debugging:

### Method 1: Environment Variables (Recommended)

Set these before importing ScholarFlux:
```bash
export SCHOLAR_FLUX_ENABLE_LOGGING=TRUE
export SCHOLAR_FLUX_LOG_LEVEL=DEBUG
export SCHOLAR_FLUX_PROPAGATE_LOGS=TRUE
```

Or in your Python code:

```python
import os
os.environ["SCHOLAR_FLUX_ENABLE_LOGGING"] = "TRUE"
os.environ["SCHOLAR_FLUX_LOG_LEVEL"] = "DEBUG"
os.environ["SCHOLAR_FLUX_PROPAGATE_LOGS"] = "TRUE"

import scholar_flux
```

### Method 2: Direct Configuration

Use the `setup_logging` function directly for more fine-grained control:

```python
import logging
from scholar_flux.utils import setup_logging
from scholar_flux import masker
from scholar_flux.security import MaskingFilter

# Enable console logging only without file rotation
setup_logging(
    log_level=logging.DEBUG,
    log_file=None  # Console only
)

# Or with file rotation
setup_logging(
    log_directory="./logs", # leave blank to create and use default $HOME/.scholar_flux directory for logging
    log_file="debug.log",
    log_level=logging.DEBUG,
    logging_filter=MaskingFilter(masker), # keeps known api keys from displaying in the console
    max_bytes=10485760,  # 10MB
    backup_count=3
)
```

**Available Log Levels:** `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`

**Note:** The environment variable method is preferred for tests and CI/CD, while direct configuration is useful for custom logging requirements.

**About `SCHOLAR_FLUX_PROPAGATE_LOGS`:**

This environment variable controls whether ScholarFlux log messages are passed to ancestor loggers (such as the root logger).  
- Set to `TRUE` (default) to allow integration with your application's logging configuration.
- Set to `FALSE` to prevent duplicate log messages in environments like Jupyter or VS Code, or if you want ScholarFlux logs to be handled only by its own handlers.

This environment variable only needs to be set when using interactive REPLs such as IPython when you'd like to remove duplicated log messages (i.e., SCHOLAR_FLUX_PROPAGATE_LOGS=FALSE).


## Testing & Code Quality

ScholarFlux uses a comprehensive testing and linting setup to ensure code quality:

### Running Tests

**Quick test (current Python version):**
```bash
poetry run pytest tests -rsx -vv
```

**Test all Python versions (3.10, 3.11, 3.12, 3.13, optionally 3.14):**
```bash
poetry run tox
```

**With coverage report:**
```bash
poetry run tox -e coverage
```

Coverage reports are generated as both terminal output and XML format in `coverage.xml`.

**GitHub Workflow Testing Locally**

For testing GitHub Actions workflows locally, users can use [`act`](https://github.com/nektos/act) if workflow functionality needs to be vetted before implementation. 

**Installation:**
```bash
# macOS
brew install act

# Linux/Windows
curl -sSf https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash
```

**Important Note for CI Workflow Testing:**

When testing `.github/workflows/ci.yml`, which runs pytest for multiple Python versions in parallel, you may encounter port conflicts with Redis and MongoDB service containers. Since `act` runs all matrix jobs on your local machine (unlike GitHub Actions which uses separate VMs), the services will try to bind to the same ports.

**Solutions:**

1. **Run one Python version at a time** (recommended):
```bash
   act -W .github/workflows/ci.yml --matrix python-version:3.13
```

2. **Run sequentially instead of in parallel**:
   Temporarily modify the workflow to remove the matrix strategy

3. **Use dynamic port mapping**:
   Modify the workflow to use dynamic ports (see GitHub Actions service container documentation)

**Note:** If you run the full matrix workflow with `act` without addressing port conflicts, MongoDB and Redis tests may be skipped for all but one Python version.

For more information on `act`, see the [official documentation](https://github.com/nektos/act).


### Code Quality Checks

**Run all linting tools:**
```bash
poetry run tox -e lint
```

This runs:
- **mypy**: Type checking for type safety
- **ruff**: Fast linting and code quality checks (PEP 8 compliance)
- **interrogate**: Documentation coverage verification

**Individual tools:**
```bash
# Type checking
poetry run mypy src tests

# Linting
poetry run ruff check src tests

# Documentation coverage
poetry run interrogate src tests

# Auto-fix linting issues where possible
poetry run ruff check --fix src tests
```

### Our Quality Standards

- **Type hints**: All functions must have type annotations
- **Docstrings**: All public classes and functions must be documented (verified by interrogate)
- **Test coverage**: New features should include tests
- **PEP 8 compliance**: Code must pass ruff checks
- **Line length**: Maximum 120 characters (configured in pyproject.toml)
- **Security**: Follow guidelines in [SECURITY.md](SECURITY.md) for handling sensitive data

## What Can I Contribute?

### 🎯 Good First Issues

Look for issues labeled `good-first-issue` - these are:
- Well-defined and scoped
- Don't require deep knowledge of the codebase
- Great for new contributors

### 🔌 New API Integrations

We're always looking to add more academic databases and APIs! Feel free to leave your suggestions in a feature request!

When adding a new API integration:
1. Follow the existing provider patterns in `scholar_flux.api.providers`
2. Include comprehensive tests with mocked responses (that preferably simulate responses received from the API)
3. Document authentication requirements in a Pull Request 
4. Add rate limiting considerations

### 📚 Documentation

- API usage examples and tutorials
- Jupyter notebook examples
- Docstring improvements
- README enhancements
- Sphinx documentation additions

### 🐛 Bug Fixes

- Check open issues labeled `bug`
- Reproduce the bug locally
- Write a failing test that demonstrates the bug
- Fix the bug
- Submit PR with the test and fix

### ⚡ Performance Improvements

- Caching optimizations
- Query efficiency improvements
- Memory usage reduction
- Async/await implementations

### 🧪 Testing

- Increase test coverage
- Add integration tests
- Improve test documentation
- Add edge case tests

### 🔒 Security

- Identify and report vulnerabilities (see [SECURITY.md](SECURITY.md))
- Improve credential handling
- Enhance encryption implementations
- Add security-focused tests

## Contribution Workflow

### 1. Choose an Issue or Create One

- Check existing issues or create a new one
- Discuss your approach before major changes
- Get maintainer feedback on your proposal
- Tag issues appropriately (`bug`, `enhancement`, `documentation`, etc.)

### 2. Branch Naming Convention

Use descriptive branch names following this pattern:

```
feature/add-semantic-scholar-support
fix/pubmed-pagination-bug
docs/improve-api-examples
refactor/simplify-caching-logic
test/add-crossref-integration-tests
```

**Staging Branch**: `develop` (Staging branch for vetting releases with `testpypi`)
**Production Branch**: `main` (Main branch for major releases via `pypi`)

### 3. Development Process

1. Create a new branch from `main`
2. Write tests first (Test Driven Development encouraged!)
3. Implement your changes
4. Add type hints and docstrings to all new functions
5. Document all public APIs with docstrings following PEP 257
6. Run `poetry run tox -e lint` before committing
7. Ensure all tests pass with `poetry run tox`

### 4. Commit Messages

Follow conventional commits format:

```
feat: add Semantic Scholar API integration
fix: resolve pagination bug in PubMed queries
docs: add examples for caching configuration
test: add tests for Crossref API error handling
refactor: simplify session management logic
style: format code according to ruff standards
chore: update dependencies
```

**Format:**
```
<type>: <short description>

[optional body explaining what and why]

[optional footer with issue references]
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `test`: Test additions or modifications
- `refactor`: Code restructuring without functional changes
- `style`: Formatting changes
- `chore`: Maintenance tasks
- `perf`: Performance improvements

### 5. Pull Request Requirements

Before submitting your PR, ensure:

- [ ] All tests pass (`poetry run tox`)
- [ ] Code is properly typed (`poetry run mypy src tests`)
- [ ] Code is documented (`poetry run interrogate src tests`)
- [ ] Code passes linting (`poetry run ruff check src tests`)
- [ ] Changes are described clearly in PR description
- [ ] Related issue is linked (use `Fixes #123` or `Closes #123`)
- [ ] New features include tests
- [ ] Documentation is updated if needed
- [ ] No sensitive data (API keys, credentials) is committed

**PR Description Template:**

```markdown
## Description
Brief description of changes

## Related Issue
Fixes #123

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Documentation update
- [ ] Performance improvement

## Testing
How did you test these changes?

## Checklist
- [ ] Tests pass locally
- [ ] Code is typed and documented
- [ ] Follows code style guidelines
```

### 6. Review Process

- Maintainers will review your PR within 3-5 business days
- Address feedback and update your PR as needed
- Engage in constructive discussion
- Once approved and all checks pass, we'll merge your contribution!
- Your contribution will be credited in the release notes

## Module-Specific Guidelines

When contributing to specific modules, follow these conventions. For practical examples of how these modules work together, see the [comprehensive tutorials](https://SammieH21.github.io/scholar-flux/).

### scholar_flux.api
- Each API provider should have its own class
- Use consistent method naming across providers (`search()`, `fetch()`, etc.)
- Handle rate limiting appropriately
- Include comprehensive error handling
- Mock external API calls in tests

### scholar_flux.security
- Never log sensitive information without a masking pattern
- Follow secure coding practices
- Test with various input patterns
- Document security implications

### scholar_flux.data_storage
- Ensure backend implementations follow the base class interface
- Test cache expiration and invalidation
- Consider memory and disk usage
- Document performance characteristics

### scholar_flux.sessions
- Maintain backward compatibility with existing session managers
- Test session persistence and recovery
- Document caching behavior
- Include examples for common use cases

### scholar_flux.data
- Validate all inputs with Pydantic models
- Handle edge cases gracefully
- Document data transformations clearly
- Include type hints for all data structures

### scholar_flux.utils
- Keep utility functions focused and reusable
- Include comprehensive docstrings with examples
- Add unit tests for all utilities
- Avoid external dependencies when possible

## Documentation

ScholarFlux includes **8 comprehensive tutorials** in addition to full API reference documentation. When contributing, please ensure your changes are reflected in relevant documentation.

### Available Tutorials

**Core Tutorials:**
- **[Getting Started](https://SammieH21.github.io/scholar-flux/getting_started.html)** - Installation, first search, environment configuration
- **[Response Handling Patterns](https://SammieH21.github.io/scholar-flux/response_handling_patterns.html)** - Error handling, metadata extraction
- **[Multi-Provider Search](https://SammieH21.github.io/scholar-flux/multi_provider_search.html)** - Concurrent orchestration, streaming results
- **[Schema Normalization](https://SammieH21.github.io/scholar-flux/schema_normalization.html)** - Building ML-ready datasets across providers

**Advanced Topics:**
- **[Caching Strategies](https://SammieH21.github.io/scholar-flux/caching_strategies.html)** - Production-scale caching with Redis, MongoDB, SQLAlchemy
- **[Advanced Workflows](https://SammieH21.github.io/scholar-flux/advanced_workflows.html)** - Multi-step retrieval, PubMed internals
- **[Custom Providers](https://SammieH21.github.io/scholar-flux/custom_providers.html)** - Extending ScholarFlux to new APIs
- **[Production Deployment](https://SammieH21.github.io/scholar-flux/production_deployment.html)** - Docker, monitoring, encrypted caching, and security essentials

### Building Documentation Locally

```bash
# Install documentation dependencies
poetry install --with docs

# Build HTML documentation
cd docs
poetry run make html

# View documentation
open _build/html/index.html  # macOS
xdg-open _build/html/index.html  # Linux
```

### Docstring Format

Follow PEP 257 and use the following format:

```python
def example_function(param1: str, param2: int) -> bool:
    """
    Brief one-line description.

    More detailed explanation if needed. This can span multiple
    lines and include examples.

    Args:
        param1: Description of param1
        param2: Description of param2

    Returns:
        Description of return value

    Raises:
        ValueError: When and why this is raised
        TypeError: When and why this is raised

    Example:
        >>> example_function("test", 42)
        True

    """
    pass
```

Visit the [Sphinx documentation](https://SammieH21.github.io/scholar-flux/) for the published documentation.

## Code Style Guidelines

### General Principles

- **Readability counts**: Write code that's easy to understand
- **Explicit is better than implicit**: Make your intentions clear
- **Don't repeat yourself (DRY)**: Extract common patterns
- **Keep it simple**: Prefer simple solutions over complex ones

### Python Style

- Follow PEP 8 (enforced by ruff)
- Maximum line length: 120 characters
- Use type hints for all function signatures
- Use meaningful variable names
- Prefer f-strings for string formatting
- Use list comprehensions for simple transformations

### Testing Style

- Use descriptive test names: `test_pubmed_search_returns_correct_results()`
- One assertion per test when possible
- Use fixtures for common setup
- Mock external dependencies
- Test edge cases and error conditions

## Getting Help

### Resources

- **Documentation**: [https://SammieH21.github.io/scholar-flux/](https://SammieH21.github.io/scholar-flux/)
- **Tutorials**: [8 comprehensive tutorials](https://SammieH21.github.io/scholar-flux/) covering basics through production deployment
- **Issues**: [GitHub Issues](https://github.com/SammieH21/scholar-flux/issues)
- **Security**: See [SECURITY.md](SECURITY.md) for security-related questions

### Questions?

- Check existing [documentation and tutorials](https://SammieH21.github.io/scholar-flux/) first
- Open a discussion for general questions
- Open an issue for bugs or feature requests
- Email us at scholar.flux@gmail.com for other inquiries

### Response Times

- **Issues/PRs**: We aim to respond within 3-5 business days
- **Security issues**: Within 72 hours (see [SECURITY.md](SECURITY.md))
- **General inquiries**: Within 1 week

## Code of Conduct

We are committed to providing a welcoming and inclusive environment. 

- Be respectful and considerate
- Welcome newcomers and help them learn
- Focus on constructive feedback

Find the code of conduct [**here**](https://github.com/SammieH21/scholar-flux/blob/main/CODE_OF_CONDUCT.md)

## Project Status

ScholarFlux is currently in **beta** (v0.3.0). This means:

- APIs may change between versions
- We're actively seeking feedback
- Breaking changes may occur before 1.0
- Security vulnerabilities are addressed promptly
- Contributors have significant impact on project direction

## Recognition

Contributors will be recognized in:
- Release notes for their contributions
- GitHub contributors page
- Project documentation (if desired)

Thank you for helping make ScholarFlux better! 🎓✨

---

**Remember:** Every contribution, no matter how small, makes a difference. Whether you're fixing a typo, adding a test, or implementing a new feature, we appreciate your effort!
