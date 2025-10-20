import pytest
import re
from scholar_flux.api import APIParameterMap, APIParameterConfig
from scholar_flux.api.models.base_parameters import BaseAPIParameterMap, APISpecificParameter
from scholar_flux.exceptions.api_exceptions import APIParameterException


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


def test_api_specific_parameter_model():
    """Test the APISpecificParameter class to ensure that it accepts the intended classes."""
    param = APISpecificParameter(
        name="mailto", description="Contact email", validator=lambda value: value, default=None, required=True
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
    """Ensures that an APIParameterConfig can be instantiated as intended from both dictionaries and base param maps."""
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

    assert parameter_map == parameter_map2


def test_overwrite_mapping():
    """Tests that the parameter map can first be instantiated from known provider defaults while overwriting specific
    parameters where needed."""
    plos_parameter_map = APIParameterMap.from_defaults(provider_name="PLOS")
    parameter_map = APIParameterMap.from_defaults(
        provider_name="PLOS", start="starting", records_per_page="maxpagesize"
    )

    plos_parameter_config = APIParameterConfig(plos_parameter_map)
    parameter_config = APIParameterConfig(parameter_map)
    assert parameter_config.map.start == "starting" != plos_parameter_config.map.start
    assert parameter_config.map.records_per_page == "maxpagesize" != plos_parameter_config.map.records_per_page


def test_api_parameter_config_repr():
    """Tests whether the representation provides basic information about the parameter map in the CLI."""
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
    """Tests whether the `as_config` class method results in the same APIParameterConfig independent of whether a
    dictionary, BaseAPIParameterMap, or APIParameterMap is used to create the config."""
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
    """Tests whether updates to the BaseAPIParameterMap are registered and updated as intended using a dictionary."""
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
    """Tests whether updates to the parameter map successfully overwrites params from the previous parameter map."""
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
    """Tests whether the APISpecificParameter class, when used in an APIParameterMap, is registered as intended."""
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
    """Test whether the db parameter components are predictable or mask issues after assignment to attributes."""
    param = APISpecificParameter(name="db", description="Database parameter", default="pubmed", required=False)
    assert param.name == "db"
    assert param.description == "Database parameter"
    assert param.default == "pubmed"
    assert param.required is False


def test_set_default_api_key_parameter_sets_default():
    """When an api key parameter is not specified but is required by the API, it should be autoset to `api_key`"""
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
    """Tests whether, the api_key_parameter, as expected, does not default to `api_key` when the attribute is set."""
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
    """Tests whether keys within the `api_specific_parameters` field can be found via a simple membership test: (e.g key
    in parameter_map.api_specific_parameters."""
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
    """Tests whether passing a list to api_specific_parameters raises an error as expected."""
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
    """Tests that a dictionary with a string value, when passed to `api_specific_parameters`, raises an error."""
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
    """Ensures that a provider can be referenced via `APIParameterMap.get_defaults`"""
    result = APIParameterMap.get_defaults("pubmed")
    assert isinstance(result, APIParameterMap)
    assert result.query == "term"


def test_get_defaults_unknown_provider():
    """Tests whether `get_defaults` returns None when supplied when an unknown provider."""
    result = APIParameterMap.get_defaults("unknown")
    assert result is None


def test_from_defaults_unknown_provider():
    """Test whether `from_defaults` throws an error when supplied with an unknown provider."""
    with pytest.raises(NotImplementedError):
        APIParameterMap.from_defaults("unknown")


def test_build_parameters():
    """Tests that the APIParameterConfig, when calling `build_parameters`, raises an error when encountering an override
    to core parameters (which should ideally be handled with a context manager instead)"""
    from scholar_flux import SearchAPI

    search_api = SearchAPI.from_defaults(query="test query", provider_name="PLOS")

    with pytest.raises(APIParameterException) as excinfo:
        _ = search_api.build_parameters(page=1, query=None)
    assert (
        "Attempted to override core parameters (query, records_per_page, api_key) via api_specific_parameters. "
        "This is not allowed. Please set these values via the SearchAPI constructor or attributes or use"
        "the `with_config` context manager instead."
    ) in str(excinfo.value)


@pytest.mark.parametrize(
    ("page_number", "records_per_page", "expected_index"),
    ((1, 20, 1), (1, 50, 1), (1, 100, 1), (2, 20, 21), (2, 50, 51), (3, 100, 201)),
)
def test_auto_calculate_start_index(page_number, records_per_page, expected_index):
    """Tests that the auto_calculate_page attribute works as intended when entering a page number with a specific
    `records_per_page` value."""
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

    page_index = parameter_config._calculate_start_index(page=page_number, records_per_page=records_per_page)
    assert page_index == expected_index


@pytest.mark.parametrize(("page_number", "records_per_page", "expected_index"), ((1, 10, 1), (2, 20, 2), (5, 100, 5)))
def test_manual_page_start_index(page_number, records_per_page, expected_index):
    """Iterates through various page numbers and records per page to verify that the page start index is calculated as
    intended when `auto_calculate_page` is set to False."""

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
    assert expected_index == parameter_config._calculate_start_index(
        page=page_number, records_per_page=records_per_page
    )


@pytest.mark.parametrize("page", [(None), (0), (-1), (-10)])
def test_page_start_index_exception(page, caplog):
    """Verifies that exceptions are raised when encountering values such as `None`, 0 (when zero_indexed_pagination is
    False), and negative page."""
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

    assert f"Expected a positive integer for page. Received '{page}'" in caplog.text


@pytest.mark.parametrize("page", [(0), (1), (2)])
def test_zero_indexed_pagination(page, caplog):
    """Tests if the zero indexed pagination field operates as intended to ensure that `0`, when zero_indexed_pagination
    is True, works as intended.

    Other page numbers are checked with a default records per page to ensure that the calculated page number is correct.

    """
    parameter_config = APIParameterConfig.as_config(
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

    RECORDS_PER_PAGE = 6
    start = parameter_config._calculate_start_index(page=page, records_per_page=RECORDS_PER_PAGE)
    assert start == page * RECORDS_PER_PAGE

    parameter_config.map.auto_calculate_page = False
    start = parameter_config._calculate_start_index(page=page, records_per_page=RECORDS_PER_PAGE)
    assert start == page

    if page == 0:
        assert "Expected a positive integer for page" not in caplog.text


@pytest.mark.parametrize("records_per_page", [(None), (0), (-1), (-10)])
def test_records_per_page_start_index_exception(basic_parameter_config, records_per_page, caplog):
    """Tests the calculation of records_per_page when encountering invalid values.

    In such scenarios, an error should be raised.

    """
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
    """Tests and verifies whether a list raises an APIParameterException when provided to
    `_get_api_specific_parameters`"""
    empty_list: list = []
    with pytest.raises(APIParameterException) as excinfo:
        basic_parameter_config._get_api_specific_parameters(parameters=empty_list)  # type: ignore
    assert f"Expected `parameters` to be a dictionary, instead received {type(empty_list)}" in str(excinfo.value)

    parameter_results = basic_parameter_config._get_api_specific_parameters(parameters={"q": 1}, q=2)  # type: ignore
    assert parameter_results == {"q": 2}
    assert f"Overwriting the following keys that have been specified twice: {['q']}" in caplog.text


def test_show_parameters(basic_parameter_config):
    """Ensures that each of the core parameters can be found within the list returned by `show_parameters()`"""
    assert all(
        parameter in ("query", "start", "records_per_page", "api_key_parameter")
        for parameter in basic_parameter_config.show_parameters()
    )


def test_get_api_key(caplog):
    """Verifies that the `test_get_api_key` function appropriately raises errors as intended."""
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

    # a list should be invalid:
    with pytest.raises(APIParameterException) as excinfo:
        parameter_config._get_api_key([])  # type: ignore
    assert f"Expected `parameters` to be a dictionary, instead received {type([])}" in str(excinfo.value)

    # a dictionary should also raise an error:
    with pytest.raises(APIParameterException) as excinfo:
        parameter_config._get_api_key({})  # type: ignore
    msg = "An API key is required but not provided"
    assert msg in str(excinfo.value)
    assert msg in caplog.text
