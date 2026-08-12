from itertools import cycle

import pytest

from scholar_flux.api.models import ErrorResponse, ProcessedResponse, ResponseHistoryRegistry
from scholar_flux.api.providers import provider_registry
from scholar_flux.exceptions import APIParameterException

EXPECTED_PROVIDERS = provider_registry.providers

NAME_VARIATIONS = (
    ("arxiv", "arXiv"),
    ("arxiv", "ARXIV"),
    ("arxiv", "Arxiv"),
    ("crossref", "CrossRef"),
    ("crossref", "CROSSREF"),
    ("crossref", "Crossref"),
    ("pubmed", "PUBMED"),
    ("pubmed", "PubMed"),
    ("openalex", "OpenAlex"),
    ("openalex", "open_alex"),
    ("springernature", "springer_nature"),
    ("springernature", "SPRINGER_NATURE"),
    ("springernature", "SpringerNature"),
    ("core", "CORE"),
    ("core", "Core"),
)


@pytest.fixture
def default_response_history():
    """Simple initialization of a ResponseHistoryRegistry to mock its functionality."""
    return ResponseHistoryRegistry()


@pytest.fixture
def simple_response_history():
    """Simple response history instance holding a single processed response per class."""
    simple_response_history = ResponseHistoryRegistry(
        {
            provider: ProcessedResponse.from_response(
                cache_key=provider,
                auto_created_at=True,
                status_code=200,
                json={"status": "ok"},
                url=provider_registry[provider].base_url,
            )
            for provider in EXPECTED_PROVIDERS
        }
    )
    return simple_response_history


@pytest.fixture
def error_response_history():
    """Simple response history instance holding a single processed response per class."""
    error_status_codes = cycle([401, 404, 429, 400, 500])

    simple_response_history = ResponseHistoryRegistry(
        {
            provider: ErrorResponse.from_response(
                cache_key=provider,
                auto_created_at=True,
                status_code=status_code,
                json={"status": "failed"},
                url=provider_registry[provider].base_url,
            )
            for provider, status_code in zip(EXPECTED_PROVIDERS, error_status_codes)
        }
    )
    return simple_response_history


@pytest.mark.parametrize(("name", "variation"), NAME_VARIATIONS)
def test_provider_processed_response_retrieval(name, variation, simple_response_history):
    """Verifies that each method of response history retrieval produces the intended result after a valid assignment."""
    response = simple_response_history[name]
    assert response and response.cache_key == name and simple_response_history.get(variation) == response
    assert simple_response_history.get_from_url(response.url) == response
    assert simple_response_history[variation] == response


@pytest.mark.parametrize(("name", "variation"), NAME_VARIATIONS)
def test_provider_error_response_retrieval(name, variation, error_response_history):
    """Verifies that each method of response history retrieval returns the intended error response after assignment."""
    response = error_response_history[name]
    assert response is not None and not response and response.cache_key == name
    assert error_response_history.get(variation) == response
    assert error_response_history.get_from_url(response.url) == response
    assert error_response_history[variation] == response
    assert error_response_history.get_from_url("https://this-is-not-a-provider.com") is None


def test_simple_provider_response_additions():
    """Verifies that direct assignment via `ResponseHistoryRegistry.__setitem__` and `add` produce the same result."""
    response = ProcessedResponse()
    response_history1 = ResponseHistoryRegistry()
    response_history2 = ResponseHistoryRegistry()

    # the keys will be normalized into `testprovider`
    response_history1.add("TestProvider", response)
    response_history2["test_provider"] = response

    # methods should give equivalent results
    assert response_history1 == response_history2 and response_history1["testprovider"] is response


def test_simple_provider_response_removal(caplog):
    """Verifies that direct assignment via `ResponseHistoryRegistry.__setitem__` and `add` produce the same result."""
    original_response = ProcessedResponse.from_response(
        status_code=200, url="https://example-url.com", json={"status": "ok"}, cache_key="testprovider"
    )
    response_history1 = ResponseHistoryRegistry({"testprovider": original_response})
    # The response_history1 subclasses from a dictionary and is thus convertible into a mapping
    response_history2 = ResponseHistoryRegistry(**dict(response_history1))

    # the keys will be normalized into `testprovider`
    response_history1.remove("TestProvider")
    assert (
        f"Removed the {type(original_response)} for the provider, 'testprovider' from the response history registry"
    ) in caplog.text

    assert not response_history1 and response_history2
    removed_response = response_history2.pop("testprovider")
    assert removed_response is original_response

    # methods should give equivalent results
    assert not response_history2 and response_history1 == response_history2


@pytest.mark.parametrize(("name", "variation"), NAME_VARIATIONS)
def test_provider_response_resolution(name, variation):
    """Tests whether name resolution happens as intended with the `_normalize_name` helper method."""
    assert ResponseHistoryRegistry._normalize_name(variation) == name


def test_invalid_response_history_element_addition(default_response_history):
    """Verifies that the `ResponseHistoryRegistry` raises an error if the added value is invalid."""
    with pytest.raises(APIParameterException) as excinfo:
        default_response_history[1] = ProcessedResponse()  # type: ignore
    assert f"The key provided to the ResponseHistoryRegistry is invalid. Expected a string, received {int}" in str(
        excinfo.value
    )
    with pytest.raises(APIParameterException) as excinfo:
        default_response_history[""] = ProcessedResponse()  # type: ignore

    with pytest.raises(APIParameterException) as excinfo:
        default_response_history["CORE"] = 1  # type: ignore
    assert (
        f"The value provided to the ResponseHistoryRegistry is invalid. "
        f"Expected a ErrorResponse or ProcessedResponse, received {int}"
    ) in str(excinfo.value)


def test_basic_response_history_representations(simple_response_history):
    """Tests whether the representation of the simple `ResponseHistoryRegistry` displays as intended in the CLI."""
    assert simple_response_history.structure() == repr(simple_response_history)
