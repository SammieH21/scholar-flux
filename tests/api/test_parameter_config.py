import pytest
import re
from scholar_flux.api import APIParameterMap, APIParameterConfig
from scholar_flux.api.models.base import BaseAPIParameterMap, APISpecificParameter
from scholar_flux.exceptions.api_exceptions import APIParameterException


@pytest.fixture
def basic_parameter_config():
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


def test_api_specific_parameter_model():
    param = APISpecificParameter(
        name="mailto", description="Contact email", validator=lambda _: True, default=None, required=True
    )
    assert param.name == "mailto"
    assert param.description == "Contact email"
    assert param.validator_name == "<lambda> (function)"

    representation = repr(param)
    assert re.search(r"^APISpecificParameter\(.*\)$", representation, re.DOTALL) is not None
    assert "name='mailto'" in representation
    assert "description='Contact email'" in representation
    assert "validator='<lambda> (function)'" in representation

    param_no_validator = APISpecificParameter(name="field_type", description="Field types to receive")
    assert param_no_validator.name == "field_type"
    assert param_no_validator.description == "Field types to receive"
    assert param_no_validator.validator_name == "None"
    assert param_no_validator.validator is None


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


def test_overwrite_mapping():
    parameter_map = APIParameterMap.from_defaults(provider_name="PLOS", start="start", records_per_page="maxpagesize")

    parameter_config = APIParameterConfig(parameter_map)
    assert parameter_config.parameter_map.start == "start"
    assert parameter_config.parameter_map.records_per_page == "maxpagesize"


def test_api_parameter_config_repr():
    base_parameter_map = BaseAPIParameterMap(query="q", start="start", records_per_page="size")
    base_representation = repr(base_parameter_map)
    assert (
        re.search(r"^BaseAPIParameterMap\(.*\)$", base_representation, re.DOTALL) is not None
        and "query='q'" in base_representation
        and "start='start'" in base_representation
        and "records_per_page='size'" in base_representation
    )

    representation = repr(APIParameterConfig.as_config(base_parameter_map))
    assert (
        re.search(r"^APIParameterConfig\(.*\)$", representation, re.DOTALL) is not None
        and "parameter_map=APIParameterMap(" in representation
        and "query='q'" in representation
        and "start='start'" in representation
        and "records_per_page='size'" in representation
    )


def test_base_api_parameter_map_as_config(caplog):
    base_parameter_map = BaseAPIParameterMap(query="q", start="start", records_per_page="size")
    validated_fields = base_parameter_map.model_dump()
    parameter_map = APIParameterMap.model_validate(validated_fields)

    _ = APIParameterConfig.as_config(validated_fields)
    assert "Attempting to instantiate an APIParameterConfig with parameters of type (dict)..." in caplog.text

    _ = APIParameterConfig.as_config(base_parameter_map)
    assert (
        "Attempting to instantiate an APIParameterConfig with parameters of type (BaseAPIParameterMap)..."
        in caplog.text
    )
    _ = APIParameterConfig.as_config(parameter_map)
    assert "Attempting to instantiate an APIParameterConfig with parameters of type (APIParameterMap)..." in caplog.text

    with pytest.raises(APIParameterException) as excinfo:
        _ = APIParameterConfig.as_config({})
    assert "Encountered an error instantiating an APIParameterConfig from the provided parameter, `{}`" in str(
        excinfo.value
    )

    invalid_parameter = 1
    with pytest.raises(APIParameterException) as excinfo:
        _ = APIParameterConfig.as_config(1)  # type: ignore
    assert (
        "Expected a base API Parameter map, config, or dictionary."
        f" Received type ({type(invalid_parameter).__name__})" in str(excinfo.value)
    )


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


def test_build_parameters(caplog):
    from scholar_flux import SearchAPI

    search_api = SearchAPI.from_defaults(query="test query", provider_name="PLOS")

    with pytest.raises(APIParameterException) as excinfo:
        _ = search_api.build_parameters(page=1, query=None)
    assert (
        "Attempted to override core parameters (query, records_per_page, api_key) via api_specific_parameters. "
        "This is not allowed. Please set these values via the SearchAPI constructor or attributes or use"
        "the `with_config` context manager instead."
    ) in str(excinfo.value)


def test_auto_calculate_start_index(caplog):
    parameter_config = APIParameterConfig.as_config(
        {
            "query": "q",
            "start": "start",
            "records_per_page": "pagesize",
            "api_key_parameter": None,
            "api_key_required": False,
            "auto_calculate_page": True,
        }
    )

    idx = parameter_config._calculate_start_index(page=1, records_per_page=20)
    assert idx == 1

    idx = parameter_config._calculate_start_index(page=1, records_per_page=50)
    assert idx == 1

    idx = parameter_config._calculate_start_index(page=1, records_per_page=100)
    assert idx == 1

    idx = parameter_config._calculate_start_index(page=2, records_per_page=20)
    assert idx == 21

    idx = parameter_config._calculate_start_index(page=2, records_per_page=50)
    assert idx == 51

    idx = parameter_config._calculate_start_index(page=3, records_per_page=100)
    assert idx == 201


def test_manual_page_start_index(caplog):
    parameter_config = APIParameterConfig.as_config(
        {
            "query": "q",
            "start": "start",
            "records_per_page": "pagesize",
            "api_key_parameter": None,
            "api_key_required": False,
            "auto_calculate_page": False,
        }
    )
    assert parameter_config._calculate_start_index(page=1, records_per_page=10) == 1
    assert parameter_config._calculate_start_index(page=2, records_per_page=10) == 2
    assert parameter_config._calculate_start_index(page=10, records_per_page=10) == 10


@pytest.mark.parametrize("page", [(None), (0), (-1), (-10)])
def test_page_start_index_exception(page, caplog):
    parameter_config = APIParameterConfig.as_config(
        {
            "query": "q",
            "start": "start",
            "records_per_page": "pagesize",
            "api_key_parameter": None,
            "api_key_required": False,
            "auto_calculate_page": False,
        }
    )

    with pytest.raises(APIParameterException):
        parameter_config._calculate_start_index(page=page)
    assert f"Expected a non-zero integer for page. Received '{page}'" in caplog.text


@pytest.mark.parametrize("records_per_page", [(None), (0), (-1), (-10)])
def test_records_per_page_start_index_exception(basic_parameter_config, records_per_page, caplog):
    basic_parameter_config = APIParameterConfig.as_config(
        {
            "query": "q",
            "start": "start",
            "records_per_page": "pagesize",
            "api_key_parameter": None,
            "api_key_required": False,
            "auto_calculate_page": False,
        }
    )

    with pytest.raises(APIParameterException):
        basic_parameter_config._calculate_start_index(page=1, records_per_page=records_per_page)
    assert f"Expected a non-zero integer for records_per_page. Received '{records_per_page}'" in caplog.text


def test_api_specific_parameters(basic_parameter_config, caplog):
    empty_list: list = []
    with pytest.raises(APIParameterException) as excinfo:
        basic_parameter_config._get_api_specific_parameters(parameters=empty_list)  # type: ignore
    assert f"Expected `parameters` to be a dictionary, instead received {type(empty_list)}" in str(excinfo.value)

    parameter_results = basic_parameter_config._get_api_specific_parameters(parameters={"q": 1}, q=2)  # type: ignore
    assert parameter_results == {"q": 2}
    f"Overwriting the following keys that have been specified twice: {['q']}"


def test_show_parameters(basic_parameter_config):
    assert all(
        parameter in ("query", "start", "records_per_page", "api_key_parameter")
        for parameter in basic_parameter_config.show_parameters()
    )


def test_get_api_key(caplog):
    parameter_config = APIParameterConfig.as_config(
        {
            "query": "q",
            "start": "start",
            "records_per_page": "pagesize",
            "api_key_parameter": "apikey",
            "api_key_required": True,
            "auto_calculate_page": True,
        }
    )

    with pytest.raises(APIParameterException) as excinfo:
        parameter_config._get_api_key([])  # type: ignore
    assert f"Expected `parameters` to be a dictionary, instead received {type([])}" in str(excinfo.value)

    with pytest.raises(APIParameterException) as excinfo:
        parameter_config._get_api_key({})  # type: ignore
    msg = "An API key is required but not provided"
    assert msg in str(excinfo.value)
    assert msg in caplog.text
