import pytest
from unittest.mock import MagicMock, patch
import requests
import requests_mock
import logging
import contextlib
import re

from math import ceil
from time import time, sleep

from scholar_flux.api import SearchAPI, SearchAPIConfig, APIParameterConfig
from scholar_flux.security import SecretUtils

from scholar_flux.exceptions import QueryValidationException, APIParameterException


def test_missing_query():
    with pytest.raises(QueryValidationException):
        # an empty query should error
        _ = SearchAPI.from_defaults(provider_name="plos", query="")


def test_describe_api():
    api = SearchAPI.from_defaults(query="light", provider_name="CROSSREF")
    assert isinstance(api.describe(), dict)

def test_session_mod():
    api = SearchAPI.from_defaults(query="light", provider_name="CROSSREF", use_cache = True)
    api.session = None # type: ignore
     # at the moment, removing a session isn't ever encouraged but possible for mocking/testing
    assert api.cache is None

@pytest.mark.parametrize(
    "param_overrides",
    [
        {"provider_name": "a_non_implemented_provider"},
        {"records_per_page": "10"},
        {"api_key": ""},
        {"timeout": 0},
        {"timeout": -1},
        {"api_key": "*" * 513},
    ],
)
def test_incorrect_config(param_overrides):
    """
    Test for common potential pitfalls in creating a search api instance
    1. if records_per_page is a non integer, raises an error
    2. api key must be provided for the springer API, If empty string, triggers an error.
    3. If an api key is more than 512 characters long, the api key is likely incorrect

    """
    kwargs = {
        "query": "test_query",
        "provider_name": "springernature",
        "records_per_page": 10,
        "api_key": "thisisacompletelyfakekey",
    } | param_overrides

    with pytest.raises(APIParameterException):
        # at each step, the API session creation should throw an error
        _ = SearchAPI.from_defaults(**kwargs)

def test_incorrect_property_settings():
    api = SearchAPI(query = 'another valid query', use_cache = False)
    value = 'not a parameter config'
    with pytest.raises(APIParameterException) as excinfo:
        api.parameter_config = value # type: ignore
    assert f"Expected an APIParameterConfig, received type: {type(value)}"

def test_cache_storage_off():
    api = SearchAPI(query = 'another valid query', use_cache = False)
    assert not api.cache
    

def test_incorrect_init():
    with pytest.raises(APIParameterException) as excinfo:
        _ = SearchAPI('valid query', base_url = 'invalid_base_url')
    assert "Invalid SearchAPIConfig: " in str(excinfo.value)


def test_incorrect_config_type():
    api = SearchAPI.from_defaults(query="no-query", provider_name="plos")
    config_dict = api.config.model_dump()
    with pytest.raises(APIParameterException):
        api = SearchAPI.from_settings(
            query="no-query",
            config=config_dict,  # type:ignore
            parameter_config=api.parameter_config,
        )


def test_default_params():
    """
    Test for whether the defaults are specified correctly:
        1. api key stays null
        2. session defauls to a requests.Session object
        3. records per page defaults to 20
        4. mailto defaults to None
        5. timeout is correctly set to the default 20 seconds
    """

    parameter_config = APIParameterConfig.from_defaults("plos")
    api = SearchAPI(
        query="test",
        base_url="https://api.example.com",
        parameter_config=parameter_config,
        records_per_page=None,  # type:ignore
        session=None,
        api_key=None,
        request_delay=None,  # type:ignore
        timeout=None,
    )

    assert api.api_key is None
    assert api.session is not None and isinstance(api.session, requests.Session)
    assert api.api_specific_parameters.get("mailto") is None
    assert api.records_per_page is not None and api.records_per_page == api.config.DEFAULT_RECORDS_PER_PAGE
    assert api.request_delay is not None and api.request_delay == api.config.DEFAULT_REQUEST_DELAY
    assert api.timeout is not None and api.timeout == api.DEFAULT_TIMEOUT


def test_search_api_initialization(default_api_parameter_config):
    """
    Tests whether the search_api can be initialized independently from the
    api parameter configuration.
    Validations:
        - SearchAPI.query is correctly set
        - SearchAPI.records_per_page is correctly set
        - SearchAPI.query can be modified as a mutable property
        - Invalid query assignment raises QueryValidationException but retains previous valid query value
    """
    api = SearchAPI(
        query="test",
        records_per_page=10,
        api_key="thisisacompletelyfakekey",
        base_url="https://api.example.com",
        parameter_config=default_api_parameter_config,
    )

    assert not api.is_cached_session(api.session)
    assert api.query == "test"
    assert api.records_per_page == 10

    api.query = "tested"

    with pytest.raises(QueryValidationException):
        # setting a query as blank should throw an exception
        api.query = ""

    assert api.query == "tested"  # Confirms the value is retained after exception


def test_cached_session(default_api_parameter_config, default_cache_session):
    api = SearchAPI(
        query="test",
        records_per_page=10,
        api_key="thisisacompletelyfakekey",
        base_url="https://api.example.com",
        session=default_cache_session,
        parameter_config=default_api_parameter_config,
    )

    assert api.is_cached_session(api.session)


@patch.object(SearchAPI, "search", return_value=MagicMock(status_code=200, json={"page": 1, "results": ["record1"]}))
def test_search_by_page(make_request, default_api_parameter_config):

    api = SearchAPI(
        query="test",
        records_per_page=10,
        api_key="thisisacompletelyfakekey",
        base_url="https://api.example.com",
        parameter_config=default_api_parameter_config,
    )

    search_results = api.search(page=1)
    assert search_results.json == {"page": 1, "results": ["record1"]}


@pytest.mark.parametrize("page, records_per_page", [(1, 1), (2, 5), (1, 20), (2, 10)])
def test_search_api_parameter_ranges(page: int, records_per_page: int, default_api_parameter_config):
    api = SearchAPI(
        query="test",
        records_per_page=records_per_page,
        api_key="key",
        base_url="https://api.example.com",
        parameter_config=default_api_parameter_config,
    )

    params = api.build_parameters(page)

    parameter_mappings = api.parameter_config.parameter_map.model_dump()
    start_key = parameter_mappings.get("start", "nokey")
    records_per_page_key = parameter_mappings.get("records_per_page")

    assert start_key and records_per_page_key

    # Test parameter calculation
    start = params.get(start_key)
    records_per_page_param = params.get(records_per_page_key)
    assert start is not None
    start_page = ceil(start / records_per_page)
    assert start_page == page
    assert records_per_page_param == records_per_page


# @patch('scholar_flux.api.BaseAPI.send_request', return_value=MagicMock(status_code=200,json={"page": 1, "results": ["record1"]}))
def test_cached_response_success(default_api_parameter_config, default_cache_session):
    api = SearchAPI(
        query="test",
        records_per_page=10,
        api_key="thisisacompletelyfakekey",
        base_url="https://api.example.com",
        session=default_cache_session,
        parameter_config=default_api_parameter_config,
    )

    params = api.build_parameters(page=1)
    prepared_request = api.prepare_request(api.base_url, parameters=params)
    assert prepared_request.url is not None
    with requests_mock.Mocker() as m:
        m.get(prepared_request.url, status_code=200, json={"page": 1, "results": ["record1"]})
        response = api.send_request(api.base_url, parameters=params)
        assert isinstance(response, requests.Response)
        assert not getattr(response, "from_cache", False)
        response_two = api.send_request(api.base_url, parameters=params)
        assert getattr(response_two, "from_cache", False)
        assert api.cache is not None
        cache_key = api.cache.create_key(prepared_request)
        cached_response = api.cache.get_response(cache_key)
        assert cache_key is not None and cached_response is not None
        assert response.json() == cached_response.json()


@pytest.mark.parametrize("unsuccessful_response_code", [400, 402, 404, 500])
def test_cached_response_failure(unsuccessful_response_code, default_api_parameter_config, default_cache_session):
    api = SearchAPI(
        query="test",
        records_per_page=10,
        api_key="thisisacompletelyfakekey",
        base_url="https://api.example.com",
        session=default_cache_session,
        parameter_config=default_api_parameter_config,
    )

    params = api.build_parameters(page=2)
    prepared_request = api.prepare_request(api.base_url, parameters=params)
    assert prepared_request.url is not None
    with requests_mock.Mocker() as m:
        m.get(prepared_request.url, status_code=unsuccessful_response_code, json={})

        response = api.send_request(api.base_url, parameters=params)
        response_two = api.send_request(api.base_url, parameters=params)

        assert not getattr(response, "from_cache", False)
        assert not getattr(response_two, "from_cache", False)


def test_cache_expiration(default_api_parameter_config, default_cache_session, default_seconds_cache_expiration):

    api = SearchAPI(
        query="test",
        records_per_page=10,
        api_key="thisisacompletelyfakekey",
        base_url="https://api.example.com",
        session=default_cache_session,
        parameter_config=default_api_parameter_config,
    )

    params = api.build_parameters(page=2)
    prepared_request = api.prepare_request(api.base_url, parameters=params)
    assert prepared_request.url is not None
    with requests_mock.Mocker() as m:
        m.get(prepared_request.url, status_code=200, json={})

        start = time()
        response = api.send_request(api.base_url, parameters=params)
        assert not getattr(response, "from_cache", False)
        response_two = api.send_request(api.base_url, parameters=params)
        assert getattr(response_two, "from_cache", False)

        #
        end = time()
        elapsed = end - start
        while default_seconds_cache_expiration > elapsed:
            sleep(0.1)
            elapsed = time() - start

        response_three = api.send_request(api.base_url, parameters=params)
        assert not getattr(response_three, "from_cache", False)


def test_prepare_search_url_and_params():
    api = SearchAPI.from_defaults(query="test", provider_name="core", api_key="this_is_a_fake_api_key")
    req = api.prepare_request("https://api.example.com", "endpoint", {"foo": "bar"}, api_key="123")
    assert isinstance(req.url, str) and req.url.startswith("https://api.example.com/endpoint")
    assert "foo=bar" in req.url
    assert "api_key=123" in req.url


def test_core_api_filtering(monkeypatch, caplog, scholar_flux_logger):
    core_api_key = "this_is_a_mock_api_key"
    api = SearchAPI.from_defaults(query="a search string", provider_name="core", api_key=core_api_key)
    api.masker.clear()
    assert not api.masker.patterns

    req = api.prepare_request(api.base_url, parameters=api.build_parameters(page=1))
    monkeypatch.setattr(
        api.session,
        "send",
        lambda *args, **kwargs: (_ for _ in ()).throw(requests.RequestException(f"Full url={req.url}")),
    )
    with caplog.at_level(logging.ERROR):
        with contextlib.suppress(Exception):
            api.search(page=1)

        key_list = list(api.masker.get_patterns_by_name("api_key"))
        assert key_list and len(key_list) == 1
        unmasked_key = SecretUtils.unmask_secret(key_list[0].pattern)  # type: ignore

        assert "api_key" in caplog.text
        assert f"{unmasked_key}" not in caplog.text
        assert re.search(r"api_key.*\*\*\*", caplog.text) is not None

    scholar_flux_logger.info(f"Test: The received value is: {unmasked_key}")
    assert f"{unmasked_key}" not in caplog.text
    assert "Test: The received value is: ***" in caplog.text


def test_api_key_exists_true_and_false():
    assert SearchAPI._api_key_exists({"api_key": "123"})
    assert SearchAPI._api_key_exists({"API_KEY": "123"})
    assert not SearchAPI._api_key_exists({"foo": "bar"})


def test_with_config_parameters_temporary_override(original_config, original_param_config):
    api = SearchAPI(
        query="test",
        base_url=original_config.base_url,
        records_per_page=original_config.records_per_page,
        api_key=original_config.api_key,
        parameter_config=original_param_config,
    )
    original_config = api.config

    with api.with_config_parameters(records_per_page=99, request_delay=42):
        assert api.config.records_per_page == 99
        assert api.config.request_delay == 42

    # Ensure restoration
    assert api.config == original_config


def test_with_config_parameters_invalid_field_ignored(original_config, original_param_config):
    api = SearchAPI(
        query="test",
        base_url=original_config.base_url,
        records_per_page=original_config.records_per_page,
        api_key=original_config.api_key,
        parameter_config=original_param_config,
    )
    original_config = api.config

    # Pass an invalid field; should not raise, but should not be present
    with api.with_config_parameters(nonexistent_field=123):
        assert not hasattr(api.config, "nonexistent_field")
        assert api.config.records_per_page == original_config.records_per_page

    assert api.config == original_config


def test_with_config_parameters_exception_restores(original_config, original_param_config):
    api = SearchAPI(
        query="test",
        base_url=original_config.base_url,
        records_per_page=original_config.records_per_page,
        api_key=original_config.api_key,
        parameter_config=original_param_config,
    )
    original_config = api.config

    with api.with_config_parameters(records_per_page=77):
        assert api.config.records_per_page == 77

    assert api.config == original_config


def test_with_config_precedence_over_provider(monkeypatch, new_config, original_param_config):
    api = SearchAPI(
        query="test",
        base_url="https://original.com",
        records_per_page=10,
        api_key=new_config.api_key,
        parameter_config=original_param_config,
    )

    monkeypatch.setattr(
        SearchAPIConfig,
        "from_defaults",
        lambda provider_name: SearchAPIConfig(
            base_url="https://shouldnotuse.com", records_per_page=1, request_delay=1, api_key=None
        ),
    )
    monkeypatch.setattr(
        APIParameterConfig, "from_defaults", lambda provider_name: APIParameterConfig(parameter_map=MagicMock())
    )

    # Explicit config should take precedence over provider_name
    with api.with_config(config=new_config, provider_name="testprovider"):
        assert api.config == new_config
        assert api.config.base_url == "https://new.com"


def test_nested_with_config_and_with_config_parameters(
    original_config, new_config, original_param_config, new_param_config
):
    api = SearchAPI(
        query="test",
        base_url=original_config.base_url,
        records_per_page=original_config.records_per_page,
        api_key=original_config.api_key,
        parameter_config=original_param_config,
    )
    original_config = api.config
    orig_param_config = api.parameter_config

    with api.with_config(config=new_config, parameter_config=new_param_config):
        # Inside first context: config and parameter_config are swapped
        assert api.config == new_config
        assert api.parameter_config == new_param_config

        with api.with_config_parameters(records_per_page=123, request_delay=99):
            # Inside nested context: config is a modified copy of new_config
            assert api.config.records_per_page == 123
            assert api.config.request_delay == 99
            # parameter_config remains as new_param_config
            assert api.parameter_config == new_param_config

        # After inner context: config and parameter_config are as in outer context
        assert api.config == new_config
        assert api.parameter_config == new_param_config

    # After both contexts: originals are restored
    assert api.config == original_config
    assert api.parameter_config == orig_param_config
