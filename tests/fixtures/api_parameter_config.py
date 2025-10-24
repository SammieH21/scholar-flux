import pytest
from scholar_flux.api.models import APIParameterConfig, APIParameterMap


@pytest.fixture
def basic_parameter_config():
    """Fixture that uses an APIParameterConfig to indicate the parameters accepted by a mock API provider."""
    basic_parameter_config = APIParameterConfig.as_config(
        {
            "query": "q",
            "start": "start",
            "records_per_page": "pagesize",
            "api_key_parameter": None,
            "api_key_required": False,
            "auto_calculate_page": True,
        }
    )
    return basic_parameter_config


@pytest.fixture()
def default_api_parameter_map():
    """A parameter map configuration that helps to simulate the parameters taken by an API when formatting requests."""
    return APIParameterMap(
        query="test",
        start="s",
        records_per_page="p",
        api_key_parameter="key",
        api_key_required=True,
        auto_calculate_page=True,
    )


@pytest.fixture()
def default_api_parameter_config(default_api_parameter_map):
    """API parameter configuration that helps to simulate the configuration taken by an API when formatting requests."""
    config = APIParameterConfig(parameter_map=default_api_parameter_map)
    print("config type:", type(config))
    return config


@pytest.fixture
def zero_indexed_parameter_config():
    """Fixture that uses a zero-indexed APIParameterConfig to indicate the parameters accepted by the mock API Provider.

    This parameter map simulates scenarios where the first record starts at 0 instead of 1.
    """
    zero_indexed_parameter_config = APIParameterConfig.as_config(
        {
            "query": "q",
            "start": "start",
            "records_per_page": "pagesize",
            "api_key_parameter": None,
            "api_key_required": False,
            "auto_calculate_page": True,
            "zero_indexed_pagination": True,
        }
    )
    return zero_indexed_parameter_config


@pytest.fixture
def default_zero_indexed_config():
    """Fixture that sets the APIParameterConfig.DEFAULT_CORRECT_ZERO_INDEX class variable to False.

    After testing, the fixture restores the default value after the conclusion of the test.
    """
    default_value = APIParameterConfig.DEFAULT_CORRECT_ZERO_INDEX
    APIParameterConfig.DEFAULT_CORRECT_ZERO_INDEX = False
    yield
    APIParameterConfig.DEFAULT_CORRECT_ZERO_INDEX = default_value


@pytest.fixture
def default_correct_zero_index_config():
    """Fixture that sets the APIParameterConfig.DEFAULT_CORRECT_ZERO_INDEX class variable to True.

    This is the default behavior of the APIParameterConfig. After testing, the fixture restores the default
    value after the conclusion of the test.
    """
    default_value = APIParameterConfig.DEFAULT_CORRECT_ZERO_INDEX
    APIParameterConfig.DEFAULT_CORRECT_ZERO_INDEX = True
    yield
    APIParameterConfig.DEFAULT_CORRECT_ZERO_INDEX = default_value


__all__ = [
    "default_api_parameter_map",
    "basic_parameter_config",
    "default_api_parameter_config",
    "zero_indexed_parameter_config",
    "default_zero_indexed_config",
    "default_correct_zero_index_config",
]
