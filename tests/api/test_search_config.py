import pytest
from unittest.mock import patch
from pydantic import SecretStr
import logging
from scholar_flux.api import SearchAPIConfig, provider_registry
from scholar_flux.api.models import APISpecificParameter
from scholar_flux.security import SensitiveDataMasker
import scholar_flux
import os
import scholar_flux.api.models.search_api_config


@pytest.mark.parametrize(
    ["provider", "basename"],
    [
        ("plos", "plos"),
        ("openalex", "openalex"),
        ("arxiv", "arxiv"),
        ("pubmed_efetch", "nih"),
        ("pubmed", "nih"),
        ("springernature", "springernature"),
        ("crossref", "crossref"),
        ("core", "core"),
    ],
)
def test_default_provider_initialization(provider, basename):
    """Verifies that specifying a default provider successfully retrieves its corresponding config/parameter map.

    This function uses a parametrized set of arguments to test different combinations of providers to verify that it
    retrieves the expected base name for the URL of the provider.

    """
    api_config = SearchAPIConfig.from_defaults(provider_name=provider.upper(), request_delay=None)
    default_provider = provider_registry.get(provider)
    assert api_config and default_provider
    assert api_config.provider_name == default_provider.provider_name
    assert default_provider and default_provider.base_url == api_config.base_url
    assert api_config and api_config.url_basename == basename
    assert api_config.request_delay == api_config.default_request_delay(v=None, provider_name=provider)


@pytest.mark.parametrize(
    "api_key_dictionary",
    (
        {"plos": None},
        {"openalex": "open_alex_api_key"},
        {"arxiv": "arxiv_api_key"},
        {"pubmed": "pubmed_api_key"},
        {"pubmed_efetch": "pubmed_api_key"},
        {"springernature": "springer_nature_api_key"},
        {"crossref": "crossref_api_key"},
        {"core": "core_api_key"},
    ),
)
def test_api_key_format(api_key_dictionary, request):
    """Test that verifies whether all API keys, if available, are of the correct type (SecretStr or None).

    This function uses parametrize to iteratively evaluate each individual provider config to ascertain whether there
    are any inconsistencies preventing the correct API key from being loaded and used in the scholar_flux.config.

    """

    # first ensures that we're dealing with the intended provider
    provider, api_key_parameter = next((provider, api_key) for provider, api_key in api_key_dictionary.items())
    assert provider is not None
    provider_config = provider_registry.get(provider)
    assert provider_config is not None

    # proceeds with API key format verification if the provider can an API key (whether optional or required)
    if provider_config.api_key_env_var is not None:
        # verifying format and type
        api_key = request.getfixturevalue(api_key_parameter)
        assert isinstance(api_key, SecretStr) or api_key is None

        # ensure that the API keys are masked prior to use when read
        env_api_key = SensitiveDataMasker.mask_secret(os.getenv(provider_config.api_key_env_var))
        config_api_key = scholar_flux.config[provider_config.api_key_env_var]

        # identifies any inconsistencies with the API key being applied based on the config and API key env var
        # either both should be unavailable or should be exactly equal as secret strings
        assert (api_key is None and env_api_key is None) or env_api_key == api_key == config_api_key


@pytest.mark.parametrize("provider", ["plos", "pubmed_efetch", "pubmed", "springernature", "crossref", "core"])
def test_api_key_additions(provider):
    """Tests whether masked API keys that are validated via the SearchAPIConfig remain masked when included as an
    attribute the created SearchAPIConfig instance.

    The config, which contains a masked list of environment variables for providers, is patched to include the masked
    api key so that the environment variable can be automatically retrieved from the config.

    """

    provider_info = provider_registry.get(provider)
    api_key = SensitiveDataMasker.mask_secret("A Secret")
    assert provider_info

    with patch.dict(
        scholar_flux.api.models.search_api_config.config_settings.config, {provider_info.api_key_env_var: api_key}
    ):
        config = SearchAPIConfig.from_defaults(provider)
        if provider_info.api_key_env_var:
            assert config.api_key == api_key
            assert config.api_key == SensitiveDataMasker.mask_secret(api_key)
        else:
            assert not config.api_key


def test_api_key_missing(monkeypatch, caplog):
    """Tests whether missing API keys correctly trigger the expected log message and return None before use.

    This test uses SpringerNature to validate whether the warning message is triggered when no API key can
    be found.
    """

    provider = "springernature"
    provider_info = provider_registry.get(provider)
    assert provider_info

    api_key = None
    monkeypatch.setenv(provider_info.api_key_env_var, "")
    with patch.dict(
        scholar_flux.api.models.search_api_config.config_settings.config, {provider_info.api_key_env_var: api_key}
    ):
        config = SearchAPIConfig.from_defaults(provider)

    assert config.api_key is None
    assert f"Could not load the required API key for: {provider_info.provider_name}" in caplog.text


def test_api_default():
    """Verifies that the SearchAPIConfig allows for `None` the api_key parameter to be later validated in the parameter
    building steps as opposed to configuration creation.

    PLOS does not require an API key, so the value is not populated with a known default from the environment.

    """
    api = SearchAPIConfig.from_defaults("plos", api_key=None)  # API key should default to an empty string
    assert api.api_key is None


def test_search_api_config_validation(caplog):
    """Ensures that invalid values passed to the SearchAPIConfig are flagged with a ValueError or subclass that inherits
    from the ValueError exception type.

    - API keys are flagged and raise a ValueError if an empty string is passed (as opposed to None)
    - URLs must be valid and raise an exception if otherwise invalid.
    - The provider name and URL type variables are turned into empty strings (for typing) for later inference in the
      following `model_validation` step when possible.
    - Each individual parameter is further validated to ensure that errors are raised appropriately when encountering
      wrong types.

    """
    with pytest.raises(ValueError) as excinfo:
        _ = SearchAPIConfig.validate_api_key(v="")  # type:ignore
    assert "Received an empty string as an api_key, expected None or a non-empty string" in str(excinfo.value)

    invalid_url = "hsttps://invalid_url.com"
    with pytest.raises(ValueError) as excinfo:
        _ = SearchAPIConfig.validate_url(v=invalid_url)  # type:ignore
    assert f"The URL provided to the SearchAPIConfig is invalid: {invalid_url}" in str(excinfo.value)

    assert SearchAPIConfig.validate_provider_name(None) == ""  # type:ignore
    assert SearchAPIConfig.validate_url_type(None) == ""  # type:ignore

    invalid_url_type: set = set()
    with pytest.raises(ValueError) as excinfo:
        _ = SearchAPIConfig.validate_url_type(invalid_url_type)  # type:ignore
    assert (
        f"Incorrect type received for the base_url. Expected None or string, received ({type(invalid_url_type)})"
        in str(excinfo.value)
    )

    with pytest.raises(ValueError) as excinfo:
        _ = SearchAPIConfig.validate_provider_name([])  # type:ignore
    assert f"Incorrect type received for the provider_name. Expected None or string, received ({type([])})" in str(
        excinfo.value
    )

    invalid_request_delay = "five"
    with pytest.raises(ValueError) as excinfo:
        _ = SearchAPIConfig.validate_request_delay(v=invalid_request_delay)  # type:ignore
    assert (
        f"Incorrect type received for the request delay parameter. Expected integer or float, received ({type(invalid_request_delay)})"
        in str(excinfo.value)
    )

    assert SearchAPIConfig.set_records_per_page(v=5) == 5  # type:ignore

    api_key = "This is a mock key"
    secret_api_key = SecretStr(api_key)
    assert SearchAPIConfig.validate_api_key(api_key) == secret_api_key  # type:ignore
    v = 5
    with pytest.raises(ValueError) as excinfo:
        _ = SearchAPIConfig.validate_api_key(v)  # type:ignore
    assert f"Incorrect type received for the api_key. Expected None or string, received ({type(v)})" in str(
        excinfo.value
    )
    assert "The received api_key is less than 20 characters long - verify that the api_key is correct" in caplog.text
    assert SearchAPIConfig.validate_api_key(secret_api_key) == secret_api_key  # type:ignore

    long_api_key = "v" * 257
    assert SearchAPIConfig.validate_api_key(long_api_key)  # type:ignore
    assert "The received api_key is more than 256 characters long - verify that the api_key is correct" in caplog.text


def test_missing_provider_information(caplog):
    """Verifies that a missing provider and URL will raise a ValueError when a provider cannot be inferred."""
    original_default_provider = SearchAPIConfig.DEFAULT_PROVIDER
    SearchAPIConfig.DEFAULT_PROVIDER = None  # type: ignore
    with pytest.raises(ValueError) as excinfo:
        _ = SearchAPIConfig._prepare_provider_info("", "")
    assert "Neither a base URL nor a provider name was provided - falling back to default: None" in caplog.text
    assert (
        f"Either a base URL or a valid provider name must be specified. SearchAPIConfig could not fall back "
        f"to the default, {SearchAPIConfig.DEFAULT_PROVIDER}"
    ) in str(excinfo.value)
    SearchAPIConfig.DEFAULT_PROVIDER = original_default_provider


def test_missing_provider_url(caplog):
    """Verifies that the PLOS url is inferred as intended when the PLOS provider is specified."""
    base_url, provider, provider_info = SearchAPIConfig._prepare_provider_info(provider_name="plos", base_url="")
    assert base_url and provider_info and base_url == provider_info.base_url


def test_api_key_modification(caplog):
    """Validates that the modification of an API key takes place as intended with changes in providers To verify, the
    `config` dictionary is patched to include mock API keys for each provider and later checked to determine whether the
    API key matches the provider's assigned string/secret key.

    This method also verifies that the provider api key is removed as intended when it no longer applies to the current
    provider after a configuration update.

    """
    api_key = SensitiveDataMasker.mask_secret("A Secret")
    another_api_key = SensitiveDataMasker.mask_secret("Another Secret")
    another_api_key_two = SensitiveDataMasker.mask_secret("Another Secret Two")

    # retrieving the configuration for PLOS and PUBMED
    plos_provider_info = provider_registry["PLOS"]
    pubmed_provider_info = provider_registry["PUBMED"]
    crossref_provider_info = provider_registry["CROSSREF"]

    assert plos_provider_info and pubmed_provider_info

    # ensure that the config holds the appropriate API key for its associated environment variable name
    with patch.dict(
        scholar_flux.api.models.search_api_config.config_settings.config,
        {
            pubmed_provider_info.api_key_env_var: another_api_key,
            crossref_provider_info.api_key_env_var: another_api_key_two,
        },
    ):

        # plos is used by default when not specified
        plos_config = SearchAPIConfig()  # type: ignore
        assert plos_config.api_key is None

        # ensures that PUBMED is used with the specified API key
        pubmed_config = SearchAPIConfig.update(plos_config, provider_name="pubmed", api_key=api_key)
        # because the API key was directly specified, the API key should not be overridden
        assert (
            pubmed_config.provider_name == "pubmed"
            and pubmed_config.api_key == api_key
            and pubmed_config.api_key != another_api_key
        )

        # when attempting to modify the configuration used from PLOS->PUBMED, the API key should automatically be read
        pubmed_config_two = SearchAPIConfig.update(plos_config, provider_name="pubmed")
        assert pubmed_config.provider_name == pubmed_config_two.provider_name
        assert pubmed_config_two.api_key == another_api_key

        crossref_three = SearchAPIConfig.update(pubmed_config_two, provider_name="crossref")
        assert crossref_three.api_key == another_api_key_two

        # changing from PUBMED->PLOS, the API key should no longer apply and be removed
        plos_config_two = SearchAPIConfig.update(pubmed_config_two, provider_name="plos")
        assert plos_config_two.provider_name == "plos" and plos_config_two.api_key is None


def test_nondefault_initialization():
    """Ensures that non-default initializations use the base-name of the url as the provider name."""
    api = SearchAPIConfig(base_url="https://test_api.com")  # type: ignore
    assert api.provider_name == "test_api"


def test_conflicting_default_initialization(caplog):
    """Validates that, when the provided defaults conflict, the base URL is prioritized."""
    provider_from_url = provider_registry.get("crossref")
    assert provider_from_url
    base_url = provider_from_url.base_url
    provider_name = "PLOS"
    api = SearchAPIConfig(provider_name=provider_name, base_url=base_url)  # type: ignore
    assert api.provider_name == provider_from_url.provider_name

    msg = (
        f"The URL, {base_url} and provider_name {provider_name} were both provided, "
        "each resolving to two different providers. \nPreferring provider: "
        f"{provider_from_url.provider_name} resolved from the provided URL."
    )
    assert msg in caplog.text


def test_missing_required_parameter():
    """Validates that, when a parameter is required but missing, it throws an error if a default is otherwise not
    specified.

    Uses crossref to validate that a value error is thrown when a SearchAPIConfig instance is created without the api
    specific parameter being assigned a value.

    """
    provider_name = "crossref"
    provider_from_url = provider_registry.get(provider_name)
    assert provider_from_url

    mock_required_parameter = APISpecificParameter(
        "a_missing_parameter", description="for mocking required parameter errors", required=True
    )
    api_specific_parameters = provider_from_url.parameter_map.api_specific_parameters
    api_specific_parameters[mock_required_parameter.name] = mock_required_parameter
    with pytest.raises(ValueError) as excinfo:
        _ = SearchAPIConfig(provider_name=provider_name)  # type: ignore

    assert "The value for the additional parameter, a_missing_parameter, was not provided and has no default" in str(
        excinfo.value
    )

    api_specific_parameters.pop(mock_required_parameter.name, None)


def test_nonneeded_api_key(caplog):
    """Tests that, upon changing the config to a new provider, the previous API key is removed."""
    provider_name = "core"
    config = SearchAPIConfig.from_defaults(provider_name, api_key="my_core_api_key")
    new_config = SearchAPIConfig.update(config, base_url="https://testing_site.com")
    assert "(" not in new_config.provider_name
    assert "testing_site" in new_config.provider_name
    assert new_config.api_key is None
    assert "The previous API key may not be applicable to the new provider. Omitting.." in caplog.text


def test_search_api_config_dynamic_provider_override(caplog):
    """Test that the SearchAPI handles dynamic provider overrides the base URL appropriately and replaces an invalid
    provider name with the provider name from the base URL.

    This test also validates that the logger prints the appropriate warning message describing preference for the URL.

    """

    plos_api_config = SearchAPIConfig()  # type: ignore
    assert plos_api_config.provider_name == "plos"

    provider_info = provider_registry.get("pubmed")
    api_key = SensitiveDataMasker.mask_secret("A Secret")
    assert provider_info

    with patch.dict(
        scholar_flux.api.models.search_api_config.config_settings.config, {provider_info.api_key_env_var: api_key}
    ):
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
