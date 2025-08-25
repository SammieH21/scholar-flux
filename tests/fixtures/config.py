import pytest
import os
from scholar_flux.security import SecretUtils
from pydantic import SecretStr
from typing import Optional
from scholar_flux import config
import logging
from scholar_flux import logger
from scholar_flux.api import SearchAPIConfig, APIParameterConfig
from scholar_flux.security import SecretUtils
from pydantic import SecretStr

@pytest.fixture
def core_api_key()-> Optional[SecretStr]:
    if not isinstance(os.getenv('CORE_API_KEY'), str):
        pytest.skip()

    return SecretUtils.mask_secret(config.get('CORE_API_KEY'))

@pytest.fixture
def pubmed_api_key()-> Optional[SecretStr]:
    if not isinstance(os.getenv('PUBMED_API_KEY'), str):
        pytest.skip()

    return SecretUtils.mask_secret(config['PUBMED_API_KEY'])

@pytest.fixture
def scholar_flux_logger()-> logging.Logger:
    return logger

import pytest
from unittest.mock import MagicMock, patch

from scholar_flux.api import SearchAPI, SearchAPIConfig, APIParameterConfig

@pytest.fixture
def original_config_test_api_key() -> SecretStr:
    return SecretStr('a fake api key')

@pytest.fixture
def new_config_test_api_key() -> SecretStr:
    return SecretStr('a new fake api key')

@pytest.fixture
def original_config(original_config_test_api_key):
    return SearchAPIConfig(base_url="https://original.com", records_per_page=10, request_delay=1, api_key=original_config_test_api_key)

@pytest.fixture
def new_config(new_config_test_api_key):
    return SearchAPIConfig(base_url="https://new.com", records_per_page=5, request_delay=2, api_key=new_config_test_api_key)

@pytest.fixture
def original_param_config():
    return APIParameterConfig(parameter_map=MagicMock())

@pytest.fixture
def new_param_config():
    return APIParameterConfig(parameter_map=MagicMock())

import pytest
import os
from scholar_flux.security import SecretUtils
from pydantic import SecretStr
from typing import Optional
from scholar_flux import config
import logging
from scholar_flux import logger
from scholar_flux.api import SearchAPIConfig, APIParameterConfig

def test_with_config_temporary_swap(original_config, new_config, original_param_config, new_param_config):
    api = SearchAPI(
        query="test",
        base_url=original_config.base_url,
        records_per_page=original_config.records_per_page,
        parameter_config=original_param_config
    )
    # Save originals for later comparison
    orig_config = api.config
    orig_param_config = api.parameter_config

    # Use with_config to swap config and parameter_config
    with api.with_config(config=new_config, parameter_config=new_param_config):
        assert api.config == new_config
        assert api.parameter_config == new_param_config

    # After context, originals are restored
    assert api.config == orig_config
    assert api.parameter_config == orig_param_config

def test_with_config_provider_name(monkeypatch, original_config, original_param_config):
    api = SearchAPI(
        query="test",
        base_url=original_config.base_url,
        records_per_page=original_config.records_per_page,
        parameter_config=original_param_config
    )

    # Patch from_defaults to return new configs
    monkeypatch.setattr(SearchAPIConfig, "from_defaults", lambda provider_name: SearchAPIConfig(base_url=f"https://{provider_name}.com", records_per_page=99, request_delay=3))
    monkeypatch.setattr(APIParameterConfig, "from_defaults", lambda provider_name: APIParameterConfig(parameter_map=MagicMock()))

    with api.with_config(provider_name="testprovider"):
        assert api.config.base_url == "https://testprovider.com"
        assert api.config.records_per_page == 99

def test_with_config_precedence(monkeypatch, new_config, original_param_config):
    api = SearchAPI(
        query="test",
        base_url="https://original.com",
        records_per_page=10,
        parameter_config=original_param_config
    )

    # Patch from_defaults to return a different config
    monkeypatch.setattr(SearchAPIConfig, "from_defaults", lambda provider_name: SearchAPIConfig(base_url="https://shouldnotuse.com", records_per_page=1, request_delay=1))
    monkeypatch.setattr(APIParameterConfig, "from_defaults", lambda provider_name: APIParameterConfig(parameter_map=MagicMock()))

    # Provide both config and provider_name; config should take precedence
    with api.with_config(config=new_config, provider_name="testprovider"):
        assert api.config == new_config
        assert api.config.base_url == "https://new.com"

def test_with_config_exception_restores(monkeypatch, original_config, original_param_config, new_config):
    api = SearchAPI(
        query="test",
        base_url=original_config.base_url,
        records_per_page=original_config.records_per_page,
        parameter_config=original_param_config
    )
    orig_config = api.config
    orig_param_config = api.parameter_config

    with pytest.raises(ValueError):
        with api.with_config(config=new_config):
            assert api.config == new_config
            raise ValueError("Intentional error")

    # After exception, originals are restored
    assert api.config == orig_config
    assert api.parameter_config == orig_param_config
