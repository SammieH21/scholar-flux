import pytest
import re
from scholar_flux.api import ProviderRegistry, ProviderConfig, APIParameterMap
from scholar_flux.utils.provider_utils import ProviderUtils
from scholar_flux.exceptions import APIParameterException
import contextlib
import scholar_flux.api.providers as scholar_flux_api_providers
from copy import deepcopy


def test_provider_config_validation(caplog):
    """Test that ProviderConfig logs and raises APIParameterException for invalid base or documentation URLs.

    Also verifies that valid URLs do not raise errors.

    """
    invalid_url: dict = {}
    with pytest.raises(APIParameterException) as excinfo:
        ProviderConfig.validate_base_url(invalid_url)  # type: ignore
    assert (
        f"Error validating the API base URL: The URL provided to the ProviderConfig is invalid: {invalid_url}"
        in caplog.text
    )
    assert (
        f"Error validating the API base URL: The URL provided to the ProviderConfig is invalid: {invalid_url}"
        in str(excinfo.value)
    )

    with pytest.raises(APIParameterException) as excinfo:
        ProviderConfig.validate_docs_url(invalid_url)  # type: ignore
    assert (
        f"Error validating the document URL: The URL provided to the ProviderConfig is invalid: {invalid_url}"
        in caplog.text
    )
    assert (
        f"Error validating the document URL: The URL provided to the ProviderConfig is invalid: {invalid_url}"
        in str(excinfo.value)
    )

    assert ProviderConfig.validate_base_url("https:// www.usersite.com")  # type: ignore
    assert ProviderConfig.validate_docs_url("https:// www.usersite.com")  # type: ignore


def test_unknown_provider_retrieval():
    """Verifies that the attempted retrieval of a provider will return None if it is not registered."""
    provider_registry = ProviderRegistry.from_defaults()

    assert provider_registry.get_from_url(provider_url="https://non-existent-provider.com") is None
    assert provider_registry.get_from_url(provider_url=None) is None  # type: ignore
    assert provider_registry.get("non-existent-provider") is None


def test_provider_config_base_url_provider_name_resolution(caplog):
    """Tests if the registry resolves URLs and provider names to a ProviderConfig, prioritizing the URL if available."""
    provider_registry = ProviderRegistry.from_defaults()
    test_plos_config = provider_registry["plos"]
    test_crossref_config = provider_registry["crossref"]

    plos_url, plos_name = test_plos_config.base_url, test_plos_config.provider_name
    crossref_url, crossref_name = test_crossref_config.base_url, test_crossref_config.provider_name
    bad_url, bad_name = "https://bad_url.com", "bad_provider_name"

    # Should resolve easily
    assert provider_registry.resolve_config(provider_url=plos_url, provider_name=plos_name) == test_plos_config
    assert (
        provider_registry.resolve_config(provider_url=crossref_url, provider_name=crossref_name) == test_crossref_config
    )
    assert "The configuration was resolved from the URL." in caplog.text
    caplog.clear()

    # URLs are prioritized
    assert provider_registry.resolve_config(provider_url=plos_url, provider_name=bad_name) == test_plos_config
    assert provider_registry.resolve_config(provider_url=plos_url, provider_name=crossref_name) == test_plos_config
    assert "The configuration was resolved from the URL." in caplog.text
    caplog.clear()
    # Provider Names used only if URLs don't resolve
    assert provider_registry.resolve_config(provider_url=bad_url, provider_name=crossref_name) == test_crossref_config
    assert "The configuration was resolved from the provider name." in caplog.text

    # If no input can  be resolved, None is returned
    assert provider_registry.resolve_config(provider_url=bad_url, provider_name=bad_name) is None
    assert (
        f"A configuration associated with the URL ({bad_url}) or provider name ({bad_name}) was not located."
        in caplog.text
    )
    assert provider_registry.resolve_config(provider_url=None, provider_name=None) is None
    assert "A configuration associated with the URL (None) or provider name (None) was not located." in caplog.text


def test_unknown_provider_deletion(caplog):
    """Verifies that the deletion of an unknown provider will raise a KeyError."""
    provider_registry = ProviderRegistry.from_defaults()
    n = len(provider_registry)

    provider_name = "non-existent-provider"

    with pytest.raises(KeyError):
        del provider_registry[provider_name]

    provider_registry.remove(provider_name)
    assert f"A ProviderConfig with the provider name, '{provider_name}' was not found" in caplog.text
    assert len(provider_registry) == n


def test_provider_removal(caplog):
    """Test that ProviderConfig.remove correctly removes a provider and updates the registry as expected."""

    provider_registry = ProviderRegistry.from_defaults()
    provider_name = "plos"
    n = len(provider_registry)

    provider_registry.remove(provider_name)
    assert len(provider_registry) == n - 1

    assert (
        f"Removed the provider config for the provider, '{provider_name}' " "from the provider registry"
    ) in caplog.text


def test_provider_creation(caplog):
    """Tests whether the addition of a new provider occurs as intended when initialized with a string (key) and a
    ProviderConfig (value).

    Upon registering the new provider, the provider should be retrievable from the `provider_registry`.

    """
    provider_registry = ProviderRegistry.from_defaults()

    plos_config = provider_registry.pop("plos")
    plos_config_parameters = plos_config.model_dump()
    plos_config_new = provider_registry.create(**plos_config_parameters)

    assert plos_config_new.model_dump() == plos_config_parameters
    assert plos_config.model_dump() == provider_registry[plos_config.provider_name].model_dump()


def test_provider_addition(caplog):
    """Tests whether the addition of a new provider occurs as intended when initialized with a string (key) and a
    ProviderConfig (value).

    Upon registering the new provider, the provider should be retrievable from the `provider_registry`.

    """
    provider_registry = ProviderRegistry.from_defaults()
    n = len(provider_registry)

    parameter_map = APIParameterMap(
        query="query", start="pagestart", records_per_page="pagesize", api_key_parameter=None, api_key_required=False
    )

    provider_name = "new_provider"
    provider_config = ProviderConfig(
        provider_name=provider_name, base_url="https://www.new_provider.com", parameter_map=parameter_map
    )

    provider_registry[provider_name] = provider_config
    assert len(provider_registry) == n + 1
    assert provider_registry[provider_name] == provider_config
    assert provider_name in provider_registry
    assert re.search(r"^ProviderConfig\(.*'newprovider'.*\)$", repr(provider_registry[provider_name]), re.DOTALL)

    update_config = deepcopy(provider_config)
    update_config.docs_url = "https://the-docs-can-be-found-here.com"

    assert provider_registry.get_from_url("http://www.new_provider.com") is not None
    assert provider_registry.get_from_url("https://www.new_provider.com") is not None

    provider_registry[provider_name] = update_config

    provider_registry.add(update_config)
    assert (
        f"Overwriting the previous ProviderConfig for the provider, '{ProviderConfig._normalize_name(provider_name)}'"
        in caplog.text
    )

    assert provider_registry[provider_name].docs_url == update_config.docs_url


def test_invalid_provider_addition():
    """Tests whether the attempted addition of an invalid provider raises an APIParameterException."""
    provider_registry = ProviderRegistry.from_defaults()
    n = len(provider_registry)

    parameter_map = APIParameterMap(query="q", start="s", records_per_page="size")

    provider_config = ProviderConfig(
        provider_name="otherwise_valid_provider", base_url="https://www.new_provider.com", parameter_map=parameter_map
    )

    empty_provider_config = ProviderConfig

    with pytest.raises(APIParameterException) as excinfo:
        provider_registry["empty_provider"] = empty_provider_config  # type: ignore
    assert (
        f"The value provided to the ProviderRegistry is invalid. "
        f"Expected a ProviderConfig, received {type(ProviderConfig)}"
    ) in str(excinfo.value)

    with pytest.raises(APIParameterException) as excinfo:
        provider_registry.add(empty_provider_config)  # type: ignore
    assert (
        f"The value could not be added to the provider registry: "
        f"Expected a ProviderConfig, received {type(empty_provider_config)}"
    ) in str(excinfo.value)

    with pytest.raises(APIParameterException) as excinfo:
        provider_registry.create(empty_provider_config)  # type: ignore
    assert ("Encountered an error when creating a new ProviderConfig with the provider name, ") in str(excinfo.value)

    invalid_key: set = set()
    with pytest.raises(APIParameterException) as excinfo:
        provider_registry[invalid_key] = provider_config  # type: ignore
    assert (
        f"The key provided to the ProviderRegistry is invalid. " f"Expected a string, received {type(invalid_key)}"
    ) in str(excinfo.value)

    assert n == len(provider_registry)


def test_successful_import():
    """Ensures that dynamic imports for supported providers are loaded using ProviderUtils.load_provider_config_dict."""
    with contextlib.suppress(AttributeError):
        ProviderUtils.load_provider_config_dict.cache_clear()  # lru cached

    config_dict = ProviderUtils.load_provider_config_dict()
    assert isinstance(config_dict, dict) and len(config_dict) > 0


def test_failed_import():
    """Tests and validates that any unsuccessful imports of provider configs do not preclude python from successfully
    loading the scholar_flux package.

    Exceptions should be handled by the `ProviderUtils.load_provider_config` method.

    """
    from scholar_flux.utils.provider_utils import importlib

    providers_module_name = scholar_flux_api_providers.__name__
    valid_module = f"{providers_module_name}.core"
    invalid_config_name = "a_provider_config_that_doesnt_exist"
    invalid_module = f"{providers_module_name}.not_core"
    core_mod = importlib.import_module(valid_module)
    assert core_mod

    assert ProviderUtils.load_provider_config(valid_module)
    assert ProviderUtils.load_provider_config(invalid_module) is None
    assert ProviderUtils.load_provider_config(valid_module, invalid_config_name) is None
