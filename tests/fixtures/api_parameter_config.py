import pytest
from scholar_flux.api.models import APIParameterConfig, APIParameterMap

@pytest.fixture()
def default_api_parameter_map():
    return APIParameterMap(query='test',
                           start='s',
                           records_per_page='p',
                           api_key_parameter='key',
                           api_key_required = True,
                           auto_calculate_page = True
                          )

@pytest.fixture()
def default_api_parameter_config(default_api_parameter_map):
    config=APIParameterConfig(parameter_map=default_api_parameter_map)
    print("config type:",type(config))
    return config

__all__ = ['default_api_parameter_map', 'default_api_parameter_config']
