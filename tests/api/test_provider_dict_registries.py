import pytest
from scholar_flux.api.models import BaseProviderDict
from scholar_flux.api.providers import provider_registry
from scholar_flux.api.rate_limiting import (
    rate_limiter_registry,
    threaded_rate_limiter_registry,
    RateLimiterRegistry,
    RateLimiter,
    ThreadedRateLimiter,
)
from scholar_flux.exceptions import APIParameterException
import copy

EXPECTED_PROVIDERS = ["arxiv", "crossref", "pubmed", "pubmedefetch", "openalex", "springernature", "core"]

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
def default_base_provider_dict():
    """Simple initialization of a BaseProviderDict to mock its functionality"""
    return BaseProviderDict({"a": 1, "b": 2, "c": 3})


@pytest.mark.parametrize(("name", "variation"), NAME_VARIATIONS)
def test_provider_name_resolution(name, variation):
    """Tests whether name resolution happens as intended with the `_normalize_name` helper method"""
    assert BaseProviderDict._normalize_name(variation) == name


def test_provider_additions_and_keys():
    """Tests that records can be added and whether each name can be found via the `__contains__` method"""
    providers = BaseProviderDict({provider: 1 for provider in EXPECTED_PROVIDERS})

    assert all(provider in providers for provider in EXPECTED_PROVIDERS)
    assert all(value == 1 for value in providers.values())


# each provider dict is either a BaseProviderDict or subclass of it. The following tests its implementations
@pytest.mark.parametrize(
    "provider_dict",
    (
        None,
        provider_registry,
        threaded_rate_limiter_registry,
        rate_limiter_registry,
    ),
)
def test_base_provider_dict_unknown_key(provider_dict, default_base_provider_dict):
    """Tests that the functionality is otherwise similar to a dict when unknown keys of type `str` are encountered"""
    test_dict = provider_dict if provider_dict is not None else default_base_provider_dict

    with pytest.raises(KeyError):
        _ = test_dict["unknown_provider"]


@pytest.mark.parametrize(
    "provider_dict",
    (
        None,
        provider_registry,
        threaded_rate_limiter_registry,
        rate_limiter_registry,
    ),
)
def test_base_provider_dict_incorrect_type(provider_dict, default_base_provider_dict):
    """Tests the behavior of the BaseProviderDict and its subclasses when incorrect types of keys are encountered"""

    test_dict = provider_dict if provider_dict is not None else default_base_provider_dict

    assert isinstance(test_dict, BaseProviderDict)

    key = 23
    with pytest.raises(KeyError):
        _ = test_dict[key]  # type: ignore

    with pytest.raises(TypeError) as excinfo:
        _ = test_dict._normalize_name(key)  # type: ignore

    class_name = test_dict.__class__.__name__

    assert f"The key provided to the {class_name} is invalid. Expected a string, received {type(key)}" in str(
        excinfo.value
    )

    if isinstance(provider_dict, RateLimiterRegistry):
        valid_provider_name = "valid_provider_name"
        invalid_request_delay = "an_invalid_integer"

        with pytest.raises(APIParameterException) as api_excinfo:
            provider_dict.create(valid_provider_name, invalid_request_delay)  # type: ignore
        assert (
            f"Encountered an error when creating a new rate limiter with the provider name, '{valid_provider_name}': "
            f"`min_interval` must be a number greater than or equal to 0. Received value, '{invalid_request_delay}'"
        ) in str(api_excinfo.value)


def test_empty_provider_additions():
    """Tests whether attempts to use an empty string for a provider name will error as intended."""
    expected_error = "The key provided to the {class_name} is empty. Expected a non-empty string"

    base_provider_dict = BaseProviderDict()
    with pytest.raises(ValueError) as base_excinfo:
        base_provider_dict[""] = 1

    assert expected_error.format(class_name=base_provider_dict.__class__.__name__) in str(base_excinfo.value)

    with pytest.raises(APIParameterException) as rate_limiter_registry_excinfo:
        rate_limiter_registry[""] = rate_limiter_registry["plos"]  # type: ignore

    assert expected_error.format(class_name=rate_limiter_registry.__class__.__name__) in str(
        rate_limiter_registry_excinfo.value
    )

    with pytest.raises(APIParameterException) as provider_registry_excinfo:
        provider_registry[""] = provider_registry["plos"]  # type: ignore

    assert expected_error.format(class_name=provider_registry.__class__.__name__) in str(
        provider_registry_excinfo.value
    )


def test_rate_limiter_registry_expected_values():
    """Tests whether the attempted addition of invalid types will raise the expected"""
    valid_provider_name = "ValidProvider"
    invalid_value = "Not a Rate Limiter"

    with pytest.raises(APIParameterException) as excinfo:
        rate_limiter_registry[valid_provider_name] = invalid_value  #  type: ignore
    assert (
        f"The value provided to the RateLimiterRegistry is invalid. Expected a RateLimiter, received {type(invalid_value)}"
    ) in str(excinfo.value)

    with pytest.raises(APIParameterException) as excinfo:
        threaded_rate_limiter_registry[valid_provider_name] = invalid_value  # type: ignore
    assert (
        f"The value provided to the RateLimiterRegistry is invalid. Expected a ThreadedRateLimiter, received {type(invalid_value)}"
    ) in str(excinfo.value)


def test_rate_limiter_registry_roundtrip_addition(caplog):
    """Tests whether the roundtrip removal and the re-addition for a new rate limiter works as intended"""
    a, b, c = RateLimiter(1), RateLimiter(2), ThreadedRateLimiter(3)
    rate_limiter_registry = RateLimiterRegistry(a=a, b=b, c=c, threaded=False)
    copied_rate_limiter_registry = copy.copy(rate_limiter_registry)

    assert len(rate_limiter_registry) == 3

    all_providers = list(rate_limiter_registry.keys())
    for provider in all_providers:
        rate_limiter_registry.remove(provider)
        assert f"Removed the rate limiter for the provider, '{provider}' from the rate limiter registry" in caplog.text

    # dictionaries with 0 parameters are Falsy
    assert not rate_limiter_registry

    # verifies that attempting to remove a non-existent rate limiter does not raise an error
    for provider in all_providers:
        rate_limiter_registry.remove(provider)
        assert f"A RateLimiter with the provider name, '{provider}' was not found" in caplog.text

    # all rate limiters
    for provider, limiter in zip(all_providers, [a, b, c]):
        rate_limiter_registry.add(provider, limiter)

    assert rate_limiter_registry == copied_rate_limiter_registry

    # verify logging messages for RateLimiter additions
    for provider, limiter in rate_limiter_registry.items():
        assert (
            f"Created a new rate limiter for the provider, {provider} "
            f"with a request delay of {limiter.min_interval}"
        ) in caplog.text

        # verifies the behavior of `add` when attempting to overwrite a RateLimiter for a provider
        overwrite_warning = f"Overwriting the previous RateLimiter for the provider, '{provider}'"
        assert overwrite_warning not in caplog.text

        rate_limiter_registry.add(provider, limiter)
        assert overwrite_warning in caplog.text


def test_default_provider_rate_limiter_registry_addition_and_removal(caplog):
    """Tests whether the roundtrip removal and the re-addition of provider rate limiters works as intended"""
    test_rate_limiter_registry = copy.copy(rate_limiter_registry)

    all_providers = provider_registry.keys()
    # verifies that all registered rate limiters can be found for all available providers registered within the registry
    assert all(provider in test_rate_limiter_registry for provider in all_providers)

    for provider in all_providers:
        test_rate_limiter_registry.remove(provider)
        new_rate_limiter = test_rate_limiter_registry.create(provider)

        assert new_rate_limiter == test_rate_limiter_registry[provider]
        assert new_rate_limiter.min_interval == provider_registry[provider].request_delay

    # verify whether the round trip removal and re-addition of default provider rate limiters works as intended
    assert all(
        test_rate_limiter_registry[provider].min_interval == rate_limiter_registry[provider].min_interval
        for provider in all_providers
    )
