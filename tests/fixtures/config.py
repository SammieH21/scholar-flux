import pytest
from scholar_flux import config
from scholar_flux import logger
from scholar_flux.api import SearchAPIConfig, APIParameterConfig
from scholar_flux.security import SecretUtils
from unittest.mock import MagicMock
from pydantic import SecretStr
from typing import Optional
import logging
import os


@pytest.fixture
def core_api_key() -> Optional[SecretStr]:
    if not isinstance(os.getenv("CORE_API_KEY"), str):
        pytest.skip()

    return SecretUtils.mask_secret(config.get("CORE_API_KEY"))


@pytest.fixture
def pubmed_api_key() -> Optional[SecretStr]:
    if not isinstance(os.getenv("PUBMED_API_KEY"), str):
        pytest.skip()

    return SecretUtils.mask_secret(config["PUBMED_API_KEY"])


@pytest.fixture
def scholar_flux_logger() -> logging.Logger:
    return logger


@pytest.fixture
def original_config_test_api_key() -> SecretStr:
    return SecretStr("a fake api key")


@pytest.fixture
def new_config_test_api_key() -> SecretStr:
    return SecretStr("a new fake api key")


@pytest.fixture
def original_config(original_config_test_api_key):
    return SearchAPIConfig(
        base_url="https://original.com", records_per_page=10, request_delay=1, api_key=original_config_test_api_key
    )


@pytest.fixture
def new_config(new_config_test_api_key):
    return SearchAPIConfig(
        base_url="https://new.com", records_per_page=5, request_delay=2, api_key=new_config_test_api_key
    )


@pytest.fixture
def original_param_config():
    return APIParameterConfig(parameter_map=MagicMock())


@pytest.fixture
def new_param_config():
    return APIParameterConfig(parameter_map=MagicMock())


__all__ = [
    "scholar_flux_logger",
    "original_config_test_api_key",
    "new_config_test_api_key",
    "original_config",
    "new_config",
    "original_param_config",
    "new_param_config",
    "core_api_key",
    "pubmed_api_key",
]
