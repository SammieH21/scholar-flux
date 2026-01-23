.PHONY: install test lint format help shell spell_checker docs

# Designed mainly for linux/Unix (Mac) compatibility. Use [Git Bash](https://gitforwindows.org/) if you encounter any issues using Windows.

# A simple help command to list available targets
help:
	@echo "Available commands:"
	@echo "  install        Installs the ScholarFlux package for development with all extras"
	@echo "  test           Runs tests with pytest within the poetry environment"
	@echo "  lint           Runs linting and type checking tools (e.g., ruff, mypy, docstr-coverage)"
	@echo "  format         Runs Black for stylistic code changes and Ruff with --fix for potential linting issues"
	@echo "  docs           Autogenerates Sphinx documentation from in-code docstrings and rst files"
	@echo "  spell_check    Uses cspell to check spelling in python files (docstrings, etc.)"
	@echo "  shell          Activates the project's virtual environment shell"

# Installs dependencies from poetry.lock
install:
	@echo "Installing project dependencies..."
	poetry install --all-extras --with dev,testing,docs
	poetry run mypy --install-types --non-interactive src tests
	poetry run pip install types-requests types-xmltodict types-PyYAML

# Runs tests using `poetry run` to execute commands within the virtual environment
test:
	@echo "Running tests..."
	poetry run pytest  -rsx -vv --cov=scholar_flux --cov-report=term-missing --cov-report xml

# Runs code quality checks
lint:
	@echo "Running code checks (linting and type checking)..."
	poetry run mypy src tests
	poetry run ruff check src tests
	poetry run docstr-coverage src
	poetry run black src tests --check

# Uses Black and Ruff for stylistic codebase formatting and fixing missing imports, stylistic issues, etc.
format:
	@echo "Formatting code structure..."
	poetry run black src tests
	poetry run ruff check src tests --fix

# Builds Sphinx documentation
docs:
	poetry run $(MAKE) -C docs clean
	poetry run $(MAKE) -C docs html

# Uses cspell to check spelling in python files (docstrings, etc.)
spell_check:
	@echo "Running CSpell spell checker..."
	act -W .github/workflows/spell_checker.yml

# Activates the poetry virtual environment shell
shell:
	poetry shell



