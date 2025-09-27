import pytest
from unittest.mock import MagicMock, patch
import requests
from pydantic import SecretStr
import requests_mock
import logging
import contextlib
import re

from math import ceil
from time import time, sleep

from scholar_flux.api.validators import validate_and_process_url, validate_url
from scholar_flux.api import SearchAPI, SearchAPIConfig, APIParameterConfig, provider_registry
from scholar_flux.security import SecretUtils

from scholar_flux.exceptions import QueryValidationException, APIParameterException, RequestCreationException


def test_missing_query():
    with pytest.raises(QueryValidationException):
        # an empty query should error
        _ = SearchAPI.from_defaults(provider_name="plos", query="")


def test_describe_api():
    api = SearchAPI.from_defaults(query="light", provider_name="CROSSREF")
    assert isinstance(api.describe(), dict)
    representation = repr(api)

    assert re.search(r"^SearchAPI\(.*\)$", representation, re.DOTALL)
    assert f"query='{api.query}'" in representation
    assert re.sub("\n +", " ", f"config={repr(api.config)}") in re.sub("\n +", " ", representation)  # ignore padding
    assert re.search(f"session=.*{api.session.__class__.__name__}", representation)
    assert f"timeout={api.timeout}" in representation


def test_api_summary():
    api = SearchAPI.from_defaults(query="light", provider_name="CROSSREF")
    assert isinstance(api.describe(), dict)
    representation = api.summary()

    assert re.search(r"^SearchAPI\(.*\)$", representation, re.DOTALL)
    assert f"query='{api.query}'" in representation
    assert f"provider_name='{api.provider_name}'" in representation
    assert f"base_url='{api.base_url}'" in representation  # ignore padding
    assert f"records_per_page={api.records_per_page}" in representation  # ignore padding
    assert re.search(f"session=.*{api.session.__class__.__name__}", representation)
    assert f"timeout={api.timeout}" in representation


def test_session_mod():
    api = SearchAPI.from_defaults(query="light", provider_name="CROSSREF", use_cache=True)
    api.session = None  # type: ignore
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
    api = SearchAPI(query="another valid query", use_cache=False)
    value = "not a parameter config"
    with pytest.raises(APIParameterException) as excinfo:
        api.parameter_config = value  # type: ignore
    assert f"Expected an APIParameterConfig, received type: {type(value)}" in str(excinfo.value)


def test_cache_storage_off():
    api = SearchAPI(query="another valid query", use_cache=False)
    assert not api.cache


def test_incorrect_init():
    with pytest.raises(APIParameterException) as excinfo:
        _ = SearchAPI("valid query", base_url="invalid_base_url")
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


def test_api_specific_parameter_specification(caplog):
    """Crossref requires an email, the SearchAPI should send the mailto field to the config for validation"""
    bad_mailto = "dsdn2#"
    with pytest.raises(APIParameterException) as excinfo:
        api = SearchAPI(query="test", provider_name="crossref", mailto=bad_mailto, api_key=None)

    assert f"The value, '{bad_mailto}' is not a valid email" in caplog.text
    assert f"The provided email is invalid, received {bad_mailto}" in str(excinfo.value)

    mailto = "atestemail@anaddress.com"
    api = SearchAPI(query="test", provider_name="crossref", mailto=mailto, api_key=None)

    api_specific_parameters = api.config.api_specific_parameters
    assert api_specific_parameters is not None
    assert api_specific_parameters["mailto"].get_secret_value() == mailto


def test_validate_url(caplog):
    crossref = provider_registry.get("crossref")
    assert crossref is not None
    crossref_url = crossref.base_url

    assert validate_and_process_url(None) is None
    assert validate_url("https://") is False
    assert (
        "Expected a domain in the URL after the http/https protocol. " "Only the scheme was received: https://"
    ) in caplog.text
    assert validate_and_process_url(crossref_url) == crossref_url


def test_search_api_url_validation(caplog):
    bad_mailto = "dsdn2#"
    crossref = provider_registry.get("crossref")
    assert crossref is not None
    crossref_url = crossref.base_url
    # will skip api mailto validation altogether if it doesn't recognize crossref from its url
    with pytest.raises(APIParameterException) as excinfo:
        _ = SearchAPI(query="test", base_url=crossref_url, mailto=bad_mailto)
    assert f"The provided email is invalid, received {bad_mailto}" in str(excinfo.value)
    # if the error is raised, crossref was recognized. now if we malform the url:
    bad_crossref_url = crossref_url.replace("https", "httpz")

    # should recognize the error:
    with pytest.raises(APIParameterException) as excinfo:
        _ = SearchAPI(query="test", base_url=bad_crossref_url)
    assert (f"The value, '{bad_crossref_url}' is not a valid URL:") in caplog.text
    assert f"The URL provided to the SearchAPIConfig is invalid: {bad_crossref_url}" in str(excinfo.value)


def test_basic_parameter_overrides(caplog):
    mailto = "atestemail@anaddress.com"
    api = SearchAPI(query="test", provider_name="crossref", mailto=mailto, api_key=None)
    params = api.build_parameters(page=1, additional_parameters={"new_parameter": 1})

    mapping = api.parameter_config.parameter_map
    assert params.get(mapping.query) is not None
    assert params.get(mapping.start or "") is not None
    assert params.get(mapping.records_per_page) is not None
    mailto_secretstr = params.get("mailto")
    assert isinstance(mailto_secretstr, SecretStr) and mailto_secretstr.get_secret_value() == mailto
    assert api.parameter_config.parameter_map.api_key_parameter not in params  # won't show in the map if `None`

    key = SecretStr("A nonmissing api key")
    params = api.build_parameters(page=1, api_key=key, mailto="another@validemail.com")
    secret_api_key = params.get(api.parameter_config.parameter_map.api_key_parameter or "")
    assert isinstance(secret_api_key, SecretStr) and secret_api_key == key
    assert (
        "Note that, while dynamic changes to a missing API key is possible in request building, "
        "is not encouraged. Instead, redefine the `api_key` parameter as an "
        "attribute in the current SearchAPI."
    ) in caplog.text
    assert (
        "The following additional parameters will be used to override the current parameter list: {'mailto': '***'}"
        in caplog.text
    )
    assert (
        "The following additional parameters are not associated with the current API config: {'new_parameter': 1}"
        in caplog.text
    )


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
    assert api.request_delay == api.config.DEFAULT_REQUEST_DELAY  # should have the same value with default


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
def test_search_by_page(_, default_api_parameter_config):

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
    prepared_request = api.prepare_request(parameters=params)
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
    prepared_request = api.prepare_request(parameters=params)
    assert prepared_request.url is not None
    with requests_mock.Mocker() as m:
        m.get(prepared_request.url, status_code=unsuccessful_response_code, json={})

        response = api.send_request(api.base_url, parameters=params)
        response_two = api.send_request(api.base_url, parameters=params)

        assert not getattr(response, "from_cache", False)
        assert not getattr(response_two, "from_cache", False)


def test_missing_api_key(default_api_parameter_config, caplog):
    # default_api_parameter_config requires an API key
    with caplog.at_level(logging.WARNING):
        _ = SearchAPI(query="test", parameter_config=default_api_parameter_config)
        assert "An API key is required but was not provided" in caplog.text


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
    prepared_request = api.prepare_request(parameters=params)
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

    req = api.prepare_request(parameters=api.build_parameters(page=1))
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


def test_updates():
    api = SearchAPI(query="test")

    identical_api = SearchAPI.update(api)

    assert repr(identical_api) == repr(identical_api)

    with pytest.raises(APIParameterException) as excinfo:
        _ = api.update(None, config=api.config, parameter_config=api.parameter_config)  # type: ignore

    assert f"Expected a SearchAPI to perform parameter updates. Received type {type(None)}" in str(excinfo.value)


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


def test_missing_parameters():
    api = SearchAPI(query="new query")
    with pytest.raises(APIParameterException) as excinfo:
        api.search()
    assert "One of 'page' or 'parameters' must be provided" in str(excinfo.value)


def test_parameter_exceptions(monkeypatch, mock_successful_response):
    minimum_request_delay = 0.5  # second interval between requests minimum

    api = SearchAPI.from_defaults(
        provider_name="plos",
        query="test",
        base_url="https://a-non-existent-test-url.com",
        request_delay=minimum_request_delay,
    )
    with pytest.raises(RequestCreationException) as excinfo:
        _ = api.prepare_request(parameters=[1, 2, 3])  # type: ignore
    assert (
        "An unexpected error occurred: The request could "
        f"not be prepared for base_url={api.base_url}, "
        f"endpoint={None}"
    ) in str(excinfo.value)


def test_base_url_omission(default_api_parameter_config):
    api = SearchAPI(
        query="test",
        records_per_page=10,
        api_key="another-private-api-key",
        base_url="https://api.another-example.com",
        parameter_config=default_api_parameter_config,
    )

    params = api.build_parameters(page=1)
    prepared_request = api.prepare_request(api.base_url, parameters=params)
    prepared_request_default = api.prepare_request(parameters=params)

    assert prepared_request.url == prepared_request_default.url


def test_rate_limiter_use(monkeypatch, mock_successful_response):
    minimum_request_delay = 0.5  # second interval between requests minimum

    api = SearchAPI.from_defaults(
        provider_name="plos",
        query="test",
        base_url="https://a-non-existent-test-url.com",
        request_delay=minimum_request_delay,
    )

    monkeypatch.setattr(api.session, "send", lambda *args, **kwargs: mock_successful_response)

    api.search(page=1)
    next_request_start = time()
    api.search(page=2)
    next_request_end = time()
    seconds_interval = next_request_end - next_request_start
    assert seconds_interval >= minimum_request_delay

    next_request_start = time()
    with api.with_config_parameters(request_delay=0):
        api.search(parameters={"mock_parameter": True})
    next_request_end = time()
    seconds_interval = next_request_end - next_request_start
    assert seconds_interval < minimum_request_delay
