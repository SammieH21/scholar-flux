import pytest
from scholar_flux import config
from scholar_flux import logger
from scholar_flux.api import SearchAPIConfig, APIParameterConfig
from scholar_flux.security import SecretUtils
from pydantic import SecretStr
from typing import Optional
import logging
import os


@pytest.fixture
def core_api_key() -> Optional[SecretStr]:
    """Masked API key that is otherwise required for testing and retrieval of data from the CORE API.

    To prevent unnecessary API calls and rate limiting issues, the key is not used to send requests and
    is instead validated to ensure it is registered as a valid secret key in the config

    Returns:
        Optional[SecretStr]: The Core API key that has been formatted as a secret string if available. Otherwise None.

    """
    if not isinstance(os.getenv("CORE_API_KEY"), str):
        pytest.skip()

    return SecretUtils.mask_secret(config.get("CORE_API_KEY"))


@pytest.fixture
def open_alex_api_key() -> Optional[SecretStr]:
    """Masked API key that is otherwise required for testing and retrieval of data from the OpenAlex API.

    To prevent unnecessary API calls and rate limiting issues, the key is not used to send requests and
    is instead validated to ensure it is registered as a valid secret key in the config

    Returns:
        Optional[SecretStr]: The OpenAlex API key formatted as a secret string if available. Otherwise None.

    """
    if not isinstance(os.getenv("OPEN_ALEX_API_KEY"), str):
        pytest.skip()

    return SecretUtils.mask_secret(config.get("OPEN_ALEX_API_KEY"))


@pytest.fixture
def arxiv_api_key() -> Optional[SecretStr]:
    """Masked API key that is otherwise required for testing and retrieval of data from the arXiv API.

    To prevent unnecessary API calls and rate limiting issues, the key is not used to send requests and
    is instead validated to ensure it is registered as a valid secret key in the config

    Returns:
        Optional[SecretStr]: The arXiv API key that has been formatted as a secret string if available. Otherwise None.

    """
    if not isinstance(os.getenv("ARXIV_API_KEY"), str):
        pytest.skip()

    return SecretUtils.mask_secret(config.get("ARXIV_API_KEY"))


@pytest.fixture
def pubmed_api_key() -> Optional[SecretStr]:
    """Masked API key that is otherwise required for testing and retrieval of data from the NIH PubMed database.

    To prevent unnecessary API calls and rate limiting issues, the key is not used to send requests and
    is instead validated to ensure it is registered as a valid secret key in the config

    Returns:
        Optional[SecretStr]: The PubMed API key that has been formatted as a secret string if available. Otherwise None.

    """
    if not isinstance(os.getenv("PUBMED_API_KEY"), str):
        pytest.skip()

    return SecretUtils.mask_secret(config["PUBMED_API_KEY"])


@pytest.fixture
def springer_nature_api_key() -> Optional[SecretStr]:
    """Masked API key that is otherwise required for testing and retrieval of data from the Springer Nature API.

    To prevent unnecessary API calls and rate limiting issues, the key is not used to send requests and
    is instead validated to ensure it is registered as a valid secret key in the config

    Returns:
        Optional[SecretStr]: The Springer Nature API key, formatted as a secret string if available. Otherwise None.

    """
    if not isinstance(os.getenv("SPRINGER_NATURE_API_KEY"), str):
        pytest.skip()

    return SecretUtils.mask_secret(config["SPRINGER_NATURE_API_KEY"])


@pytest.fixture
def crossref_api_key() -> Optional[SecretStr]:
    """Masked API key that is otherwise required for testing and retrieval of data from the Crossref API.

    To prevent unnecessary API calls and rate limiting issues, the key is not used to send requests and
    is instead validated to ensure it is registered as a valid secret key in the config

    Returns:
        Optional[SecretStr]: The Crossref API key, formatted as a secret string if available. Otherwise None.

    """
    if not isinstance(os.getenv("CROSSREF_API_KEY"), str):
        pytest.skip()

    return SecretUtils.mask_secret(config["CROSSREF_API_KEY"])


@pytest.fixture
def scholar_flux_logger() -> logging.Logger:
    """Helper method used for retrieving the logger used by scholar_flux to log events that occur during use for user
    feedback."""
    return logger


@pytest.fixture
def original_config_test_api_key() -> SecretStr:
    """Helper API key used to later mock and test using a fake, yet consistent API key.

    SecretStr: The mocked API key that has been formatted as a secret string.

    """
    return SecretStr("a fake api key")


@pytest.fixture
def new_config_test_api_key() -> SecretStr:
    """A helper API key used to later mock and test configurations that, for different provider, require a different
    mocked API key.

    Returns:
        SecretStr: The mocked API key that has been formatted as a secret string.

    """
    return SecretStr("a new fake api key")


@pytest.fixture
def original_config(original_config_test_api_key):
    """A helper config fixture used to simulate a configuration that aids in the retrieval of data from the mocked
    http://original.com API."""
    return SearchAPIConfig(
        base_url="https://original.com", records_per_page=10, request_delay=1, api_key=original_config_test_api_key
    )


@pytest.fixture
def new_config(new_config_test_api_key):
    """A helper config fixture used to simulate a configuration that aids in the retrieval of data from the mocked
    http://new.com API."""
    return SearchAPIConfig(
        base_url="https://new.com", records_per_page=5, request_delay=2, api_key=new_config_test_api_key
    )


@pytest.fixture
def original_api_parameter_config():
    """Helper configuration used to mock the creation of api parameter configurations without requiring explicit
    settings.

    This parameter configuration is used to mock the APIParameterConfig for the mocked `https://original.com` API.

    """
    return APIParameterConfig.from_defaults("crossref")


@pytest.fixture
def new_api_parameter_config():
    """Helper configuration used to mock the creation of a new configuration without requiring explicit settings This
    parameter configuration is used to mock the APIParameterConfig for the mocked `https://new.com` API."""
    return APIParameterConfig.from_defaults("plos")


__all__ = [
    "scholar_flux_logger",
    "original_config_test_api_key",
    "new_config_test_api_key",
    "original_config",
    "new_config",
    "original_api_parameter_config",
    "new_api_parameter_config",
    "core_api_key",
    "arxiv_api_key",
    "open_alex_api_key",
    "pubmed_api_key",
    "springer_nature_api_key",
    "crossref_api_key",
]
