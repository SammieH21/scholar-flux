import pytest
from scholar_flux.api.providers import ProviderRegistry, provider_registry
from types import NoneType
from scholar_flux.api.models import ProviderConfig


@pytest.mark.parametrize(
    ("provider", "expected_type"),
    [
        ("pubmed", ProviderConfig),
        ("pubmed_efetch", ProviderConfig),
        ("crossref ", ProviderConfig),
        ("Core", ProviderConfig),
        ("SpringerNature", ProviderConfig),
        ("plos ", ProviderConfig),
        ("non_existent_provider ", NoneType),
        (None, NoneType),
        ("__getitem__", NoneType),
        (1, NoneType),
    ],
)
def test_match(provider, expected_type):
    provider_config = provider_registry.get(provider)
    assert isinstance(provider_config, expected_type)

    if provider_config:
        assert provider in provider_registry
        base_url = provider_config.base_url
        provider_from_url = provider_registry.get_from_url(base_url)
        assert provider_from_url and provider_from_url.provider_name == provider_config.provider_name

    if provider is None:
        assert isinstance(provider_registry, ProviderRegistry)
        assert provider not in provider_registry
        assert provider_registry.get(provider) is None  # type: ignore
        assert provider_registry.get("https://plos_api.com") is None

        with pytest.raises(ValueError):
            provider_registry.get_from_url("anonexistent_url")
