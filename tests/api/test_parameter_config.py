import pytest
from scholar_flux.api import APIParameterMap
from scholar_flux.api.models.base import BaseAPIParameterMap, APISpecificParameter
from scholar_flux.exceptions.api_exceptions import APIParameterException


def test_api_specific_parameter_properties():
    param = APISpecificParameter(
        name="mailto", description="Contact email", validator=lambda x: x, default=None, required=True
    )
    assert param.name == "mailto"
    assert param.description == "Contact email"
    assert param.validator_name == "<lambda>"
    param_no_validator = APISpecificParameter(name="foo", description="desc")
    assert param_no_validator.validator_name == "None"


def test_base_api_parameter_map_to_dict_and_from_dict():
    parameter_map = BaseAPIParameterMap(
        query="q",
        start="start",
        records_per_page="rows",
        api_key_parameter=None,
        api_key_required=False,
        auto_calculate_page=True,
        api_specific_parameters={},
    )
    d = parameter_map.to_dict()
    assert d["query"] == "q"
    assert d["start"] == "start"
    assert d["records_per_page"] == "rows"
    parameter_map2 = BaseAPIParameterMap.from_dict(d)
    assert parameter_map2.query == "q"
    assert parameter_map2.start == "start"


def test_base_api_parameter_map_update_with_dict():
    parameter_map = BaseAPIParameterMap(
        query="q",
        start="start",
        records_per_page="rows",
        api_key_parameter=None,
        api_key_required=False,
        auto_calculate_page=True,
        api_specific_parameters={},
    )
    updated = parameter_map.update({"query": "new_query", "start": "new_start"})
    assert updated.query == "new_query"
    assert updated.start == "new_start"
    assert updated.records_per_page == "rows"


def test_base_api_parameter_map_update_with_instance():
    parameter_map1 = BaseAPIParameterMap(
        query="q",
        start="start",
        records_per_page="rows",
        api_key_parameter=None,
        api_key_required=False,
        auto_calculate_page=True,
        api_specific_parameters={},
    )
    parameter_map2 = BaseAPIParameterMap(
        query="new_q",
        start="new_start",
        records_per_page="new_rows",
        api_key_parameter="api_key",
        api_key_required=True,
        auto_calculate_page=False,
        api_specific_parameters={},
    )
    updated = parameter_map1.update(parameter_map2)
    assert updated.query == "new_q"
    assert updated.api_key_parameter == "api_key"
    assert updated.api_key_required is True
    assert updated.auto_calculate_page is False


def test_api_specific_parameters_dict():
    param = APISpecificParameter(name="mailto", description="Contact email", validator=lambda x: x, required=False)
    parameter_map = BaseAPIParameterMap(
        query="query",
        start="offset",
        records_per_page="rows",
        api_key_parameter="api_key",
        api_key_required=False,
        auto_calculate_page=True,
        api_specific_parameters={"mailto": param},
    )
    assert "mailto" in parameter_map.api_specific_parameters
    assert isinstance(parameter_map.api_specific_parameters["mailto"], APISpecificParameter)


def test_api_specific_parameter_default_and_required():
    param = APISpecificParameter(name="db", description="Database parameter", default="pubmed", required=False)
    assert param.default == "pubmed"
    assert param.required is False


def test_set_default_api_key_parameter_sets_default():
    parameter_map = APIParameterMap(
        query="q",
        start="start",
        records_per_page="rows",
        api_key_parameter=None,
        api_key_required=True,
        auto_calculate_page=True,
        api_specific_parameters={},
    )
    assert parameter_map.api_key_parameter == "api_key"


def test_set_default_api_key_parameter_does_not_override():
    parameter_map = APIParameterMap(
        query="q",
        start="start",
        records_per_page="rows",
        api_key_parameter="custom_key",
        api_key_required=True,
        auto_calculate_page=True,
        api_specific_parameters={},
    )
    assert parameter_map.api_key_parameter == "custom_key"


def test_validate_api_specific_parameter_mappings_valid():
    param = APISpecificParameter(name="foo", description="desc")
    parameter_map = APIParameterMap(
        query="q",
        start="start",
        records_per_page="rows",
        api_key_parameter=None,
        api_key_required=False,
        auto_calculate_page=True,
        api_specific_parameters={"foo": param},
    )
    assert "foo" in parameter_map.api_specific_parameters


def test_validate_api_specific_parameter_mappings_invalid_type():
    with pytest.raises(APIParameterException):
        APIParameterMap(
            query="q",
            start="start",
            records_per_page="rows",
            api_key_parameter=None,
            api_key_required=False,
            auto_calculate_page=True,
            api_specific_parameters=["not", "a", "dict"],  # type:ignore
        )


def test_validate_api_specific_parameter_mappings_invalid_value_type():
    with pytest.raises(APIParameterException):
        APIParameterMap(
            query="q",
            start="start",
            records_per_page="rows",
            api_key_parameter=None,
            api_key_required=False,
            auto_calculate_page=True,
            api_specific_parameters={"foo": "not_a_param"},  # type:ignore
        )


def test_get_defaults_known_provider():
    result = APIParameterMap.get_defaults("pubmed")
    assert isinstance(result, APIParameterMap)
    assert result.query == "term"


def test_get_defaults_unknown_provider():
    result = APIParameterMap.get_defaults("unknown")
    assert result is None


def test_from_defaults_known_provider():
    result = APIParameterMap.from_defaults("pubmed")
    assert isinstance(result, APIParameterMap)
    assert result.query == "term"


def test_from_defaults_unknown_provider():
    with pytest.raises(NotImplementedError):
        APIParameterMap.from_defaults("unknown")
