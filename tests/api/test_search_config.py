import pytest
from unittest.mock import patch
import logging


from scholar_flux.api import SearchAPIConfig, provider_registry
from scholar_flux.security import SensitiveDataMasker
import scholar_flux
import scholar_flux.api.models.search


@pytest.mark.parametrize(
    ["provider", "basename"],
    [
        ("plos", "plos"),
        ("pubmed_efetch", "nih"),
        ("pubmed", "nih"),
        (
            "springernature",
            "springernature",
        ),
        ("crossref", "crossref"),
        ("core", "core"),
    ],
)
def test_non_provider_initialization(provider, basename):
    api_config = SearchAPIConfig.from_defaults(provider_name=provider.upper())
    default_provider = provider_registry.get(provider)
    assert api_config and default_provider
    assert api_config.provider_name == default_provider.provider_name
    assert default_provider and default_provider.base_url == api_config.base_url
    assert api_config and api_config.url_basename == basename


@pytest.mark.parametrize("provider", ["plos", "pubmed_efetch", "pubmed", "springernature", "crossref", "core"])
def test_api_key_additions(provider):

    provider_info = provider_registry.get(provider)
    api_key = SensitiveDataMasker.mask_secret("A Secret")
    assert provider_info

    with patch.dict(scholar_flux.api.models.search.config, {provider_info.api_key_env_var: api_key}):
        config = SearchAPIConfig.from_defaults(provider)
        if provider_info.api_key_env_var:
            assert config.api_key == api_key
            assert config.api_key == SensitiveDataMasker.mask_secret(api_key)
        else:
            assert not config.api_key


def test_api_key_modification():

    api_key = SensitiveDataMasker.mask_secret("A Secret")
    another_api_key = SensitiveDataMasker.mask_secret("Another Secret")

    plos_provider_info = provider_registry.get("PLOS")
    pubmed_provider_info = provider_registry.get("PUBMED")

    assert plos_provider_info and pubmed_provider_info

    with patch.dict(scholar_flux.api.models.search.config, {pubmed_provider_info.api_key_env_var: another_api_key}):

        plos_config = SearchAPIConfig()  # type: ignore
        assert plos_config.api_key is None

        pubmed_config = SearchAPIConfig.update(plos_config, provider_name="pubmed", api_key=api_key)
        assert (
            pubmed_config.provider_name == "pubmed"
            and pubmed_config.api_key == api_key
            and pubmed_config.api_key != another_api_key
        )

        pubmed_config_two = SearchAPIConfig.update(plos_config, provider_name="pubmed")
        assert pubmed_config.provider_name == pubmed_config_two.provider_name
        assert pubmed_config_two.api_key == another_api_key

        plos_config_two = SearchAPIConfig.update(pubmed_config_two, provider_name="plos")
        assert plos_config_two.provider_name == "plos" and plos_config_two.api_key is None


def test_search_api_config_dynamic_provider_override(caplog):
    """
    Test that the SearchAPI handles dynamic provider override values.

    Args:
        caplog: Will indicate logged messages sent by the API
    """

    plos_api_config = SearchAPIConfig()  # type: ignore
    assert plos_api_config.provider_name == "plos"

    provider_info = provider_registry.get("pubmed")
    api_key = SensitiveDataMasker.mask_secret("A Secret")
    assert provider_info

    with patch.dict(scholar_flux.api.models.search.config, {provider_info.api_key_env_var: api_key}):
        pubmed_config = SearchAPIConfig.update(plos_api_config, provider_name="pubmed")
        assert (
            pubmed_config.base_url == provider_info.base_url
            and pubmed_config.provider_name == provider_info.provider_name
        )
        assert pubmed_config.api_key == api_key
        assert SearchAPIConfig.update(pubmed_config) == pubmed_config
        # shouldn't vary after an update
        assert plos_api_config.request_delay == pubmed_config.request_delay

    with caplog.at_level(logging.WARNING):
        default_plos_config = SearchAPIConfig.update(plos_api_config, provider_name="BAD PROVIDER NAME")
        warning_msg = (
            "The provided base URL resolves to a provider while the provider name, "
            f"BAD PROVIDER NAME, does not. \nPreferring provider: "
            f"{default_plos_config.provider_name} resolved from the provided URL."
        )
        assert warning_msg in caplog.text

    assert SearchAPIConfig.update(plos_api_config) == plos_api_config
