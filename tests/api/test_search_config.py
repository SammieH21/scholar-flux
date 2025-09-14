import pytest
from unittest.mock import patch
from pydantic import SecretStr
import logging
from scholar_flux.api import SearchAPIConfig, provider_registry, PROVIDER_DEFAULTS
from scholar_flux.api.models import APISpecificParameter
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

def test_api_default():
    api = SearchAPIConfig.from_defaults('plos', api_key = None) # API key should default to an empty string

def test_search_api_config_validation(caplog):
    with pytest.raises(ValueError) as excinfo:
        _  = SearchAPIConfig.validate_api_key( v= '') #type:ignore
    assert "Received an empty string as an api_key, expected None or a non-empty string" in str(excinfo.value)

    invalid_url = 'hsttps://invalid_url.com'
    with pytest.raises(ValueError) as excinfo:
        _  = SearchAPIConfig.validate_url( v=invalid_url ) # type:ignore
    assert f"The URL provided to the SearchAPIConfig is invalid: {invalid_url}" in str(excinfo.value)
    
    assert SearchAPIConfig.validate_provider_name(None) == '' # type:ignore
    assert SearchAPIConfig.validate_url_type(None) == '' # type:ignore

    invalid_url_type = set()
    with pytest.raises(ValueError) as excinfo:
        _ = SearchAPIConfig.validate_url_type(invalid_url_type) # type:ignore
    assert f"Incorrect type received for the base_url. Expected None or string, received ({type(invalid_url_type)})" in str(excinfo.value)

    with pytest.raises(ValueError) as excinfo:
        _ = SearchAPIConfig.validate_provider_name([]) # type:ignore
    assert f"Incorrect type received for the provider_name. Expected None or string, received ({type([])})" in str(excinfo.value)

    invalid_request_delay = 'five'
    with pytest.raises(ValueError) as excinfo:
        _  = SearchAPIConfig.set_default_request_delay( v = invalid_request_delay ) #type:ignore
    assert f"Incorrect type received for the request delay parameter. Expected integer or float, received ({type(invalid_request_delay)})" in str(excinfo.value)


    assert SearchAPIConfig.set_records_per_page(v= 5) == 5 #type:ignore

    api_key = 'This is a mock key'
    secret_api_key = SecretStr(api_key)
    assert SearchAPIConfig.validate_api_key(api_key) == secret_api_key #type:ignore
    v = 5
    with pytest.raises(ValueError) as excinfo:
        _ =  SearchAPIConfig.validate_api_key(v) #type:ignore
    assert f"Incorrect type received for the api_key. Expected None or string, received ({type(v)})" in str(excinfo.value)
    assert "The received api_key is less than 20 characters long - verify that the api_key is correct" in caplog.text
    assert SearchAPIConfig.validate_api_key(secret_api_key) == secret_api_key #type:ignore

    long_api_key = "v" * 257
    assert SearchAPIConfig.validate_api_key(long_api_key) # type:ignore
    assert "The received api_key is more than 256 characters long - verify that the api_key is correct" in caplog.text

def test_missing_provider_information(caplog):
    original_default_provider = SearchAPIConfig.DEFAULT_PROVIDER
    SearchAPIConfig.DEFAULT_PROVIDER = None # type: ignore
    with pytest.raises(ValueError) as excinfo:
        _ = SearchAPIConfig._prepare_provider_info('', '')
    assert "Neither a base url nor a provider name was provided - falling back to default: None" in caplog.text
    assert (f"Either a base url or a valid provider name must be specified. SearchAPIConfig could not fall back "
            f"to the default, {SearchAPIConfig.DEFAULT_PROVIDER}") in str(excinfo.value)
    SearchAPIConfig.DEFAULT_PROVIDER = original_default_provider


def test_missing_provider_url(caplog):
    base_url, provider, provider_info  = SearchAPIConfig._prepare_provider_info(provider_name = 'plos', base_url = "")
    assert base_url and provider_info and base_url == provider_info.base_url



def test_api_key_modification(caplog):

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

def test_nondefault_initialization():
    api = SearchAPIConfig(base_url = "https://test_api.com") # type: ignore
    assert api.provider_name == 'test_api'

def test_conflicting_default_initialization(caplog):
    provider_from_url = provider_registry.get('crossref')
    assert provider_from_url
    base_url = provider_from_url.base_url
    provider_name = 'PLOS'
    api = SearchAPIConfig(provider_name = provider_name, base_url = base_url) # type: ignore
    assert api.provider_name == provider_from_url.provider_name

    msg = ( f"The URL, {base_url} and provider_name {provider_name} were both provided, "
           "each resolving to two different providers. \nPreferring provider: "
           f"{provider_from_url.provider_name} resolved from the provided URL.")
    assert msg in caplog.text

def test_missing_required_parameter():
    provider_name = 'crossref'
    provider_from_url = provider_registry.get(provider_name)
    assert provider_from_url

    mock_required_parameter = APISpecificParameter('a_missing_parameter',
                                                   description = 'for mocking required parameter errors',
                                                   required = True)
    api_specific_parameters = provider_from_url.parameter_map.api_specific_parameters
    api_specific_parameters[mock_required_parameter.name] = mock_required_parameter
    with pytest.raises(ValueError) as excinfo:
        _ = SearchAPIConfig(provider_name = provider_name) # type: ignore

    assert f"The value for the additional parameter, a_missing_parameter, was not provided and has no default" in str(excinfo.value)

    api_specific_parameters.pop(mock_required_parameter.name, None)

def test_nonneeded_api_key(caplog):
    provider_name = 'core'
    provider_from_url = provider_registry.get(provider_name)
    config = SearchAPIConfig.from_defaults(provider_name, api_key = 'my_core_api_key')
    new_config = SearchAPIConfig.update(config, base_url = 'https://testing_site.com')
    assert '(' not in new_config.provider_name
    assert 'testing_site' in new_config.provider_name 
    assert new_config.api_key is None
    assert "The previous API key may not be applicable to the new provider. Omitting.." in caplog.text

    

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
    assert "Initializing SearchAPIConfig with provider_name: pubmed" in caplog.text

    with caplog.at_level(logging.WARNING):
        default_plos_config = SearchAPIConfig.update(plos_api_config, provider_name="BAD PROVIDER NAME")
        warning_msg = (
            "The provided base URL resolves to a provider while the provider name, "
            f"BAD PROVIDER NAME, does not. \nPreferring provider: "
            f"{default_plos_config.provider_name} resolved from the provided URL."
        )
        assert warning_msg in caplog.text

    assert SearchAPIConfig.update(plos_api_config) == plos_api_config
