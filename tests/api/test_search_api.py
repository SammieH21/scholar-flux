import pytest
from unittest.mock import MagicMock, patch
import requests
from pydantic import SecretStr
import requests_mock
import logging
import contextlib
from copy import deepcopy
import re

from math import ceil
from time import time, sleep

from scholar_flux.api.validators import validate_and_process_url, validate_url
from scholar_flux.api import SearchAPI, APIParameterMap, SearchAPIConfig, APIParameterConfig, provider_registry
from scholar_flux.security import SecretUtils

from scholar_flux.exceptions import QueryValidationException, APIParameterException, RequestCreationException


@pytest.mark.parametrize("query", (None, ""))
def test_missing_query(query):
    """Tests whether a query validation exception is raised when an empty value is supplied to a query."""
    with pytest.raises(QueryValidationException):
        # an empty query should error
        _ = SearchAPI.from_defaults(provider_name="plos", query=query)


def test_describe_api():
    """Verifies that the representation of the SearchAPI in a command line interface contains the expected fields."""
    api = SearchAPI.from_defaults(query="light", provider_name="CROSSREF")
    assert isinstance(api.describe(), dict)
    representation = repr(api)

    assert re.search(r"^SearchAPI\(.*\)$", representation, re.DOTALL)
    assert f"query='{api.query}'" in representation
    assert re.sub("\n +", " ", f"config={repr(api.config)}") in re.sub("\n +", " ", representation)  # ignore padding
    assert re.search(f"session=.*{api.session.__class__.__name__}", representation)
    assert f"timeout={api.timeout}" in representation


def test_api_summary():
    """Verifies that the summary of the SearchAPI contains the expected fields and structure."""
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
    """Tests to determine how a missing session object impacts the cache property (should be returned as None)"""
    api = SearchAPI.from_defaults(query="light", provider_name="CROSSREF", use_cache=True)
    api.session = None  # type: ignore
    # at the moment, removing a session isn't ever encouraged but possible for mocking/testing
    assert api.cache is None


@pytest.mark.parametrize("provider_name", ("plos", "pubmed", "springernature", "crossref", "core"))
def test_parameter_build_successful(provider_name, original_config_test_api_key):
    """Verifies that the `build_parameters` method successfully prepares all required fields and, when required, API
    keys and mailto addresses for each individual provider.

    This method uses the pytest's `parametrize` feature to validate parameters generated automatically by
    `SearchAPI.build_parameters()` against the configuration and parameter map required by each provider.

    This test ensures that all required parameters and api keys (when required) are present in the final
    dictionary of parameter key-value pairs and does not send requests to the api provider.

    """

    # first ensures that we're dealing with the intended provider
    provider_config = provider_registry.get(provider_name)
    assert provider_config is not None

    api_parameter_map = provider_config.parameter_map

    # retrieves the full list of parameters that are required and optional for a specific provider
    required_provider_parameters = {
        api_parameter_map.query,
        api_parameter_map.start,
        api_parameter_map.records_per_page,
        *(
            key
            for key, parameter_info in api_parameter_map.api_specific_parameters.items()
            if parameter_info.required or key == "mailto"
        ),
    }

    if api_parameter_map.api_key_parameter:
        required_provider_parameters.add(api_parameter_map.api_key_parameter)

    # uses the default configuration under the hood for the current provider with a mocked API key to verify the result
    crossref_user_email = "avalid@email.com" if provider_name == "crossref" else None
    api = SearchAPI(
        query="test_query",
        provider_name=provider_name,
        api_key=original_config_test_api_key if api_parameter_map.api_key_parameter else None,
        mailto=crossref_user_email,  # for crossref, sufficiently important for feedback/usage
    )

    # prepares the list of parameters to be sent to the current API based on the config and page/records per page
    prepared_parameters = api.build_parameters(page=1)

    # verifies that no parameters from the `required_provider_parameters` set are missing from the prepared_parameters
    assert not required_provider_parameters.difference(prepared_parameters)


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
    """Verifies that an API parameter exception is raised when an invalid parameter config value is encountered."""
    api = SearchAPI(query="another valid query", use_cache=False)
    value = "not a parameter config"
    with pytest.raises(APIParameterException) as excinfo:
        api.parameter_config = value  # type: ignore
    assert f"Expected an APIParameterConfig, received type: {type(value)}" in str(excinfo.value)


def test_cache_storage_off():
    """Tests to ensure that API cache is not registered when `use_cache=False`"""
    api = SearchAPI(query="another valid query", use_cache=False)
    assert not api.cache


def test_incorrect_base_url(caplog):
    """Verifies that providing an invalid base URL will raise an APIParameterException indicating an issue in the
    URL."""
    with pytest.raises(APIParameterException) as excinfo:
        _ = SearchAPI("valid query", base_url="invalid_base_url")
    assert "The value, 'invalid_base_url' is not a valid URL" in str(caplog.text)
    assert "Invalid SearchAPIConfig: " in str(excinfo.value)


def test_incorrect_config_type():
    """Verifies that an incorrect configuration raises an APIParameterException when a dictionary is provided inplace of
    a SearchAPIConfig."""
    api = SearchAPI.from_defaults(query="no-query", provider_name="plos")
    config_dict = api.config.model_dump()
    with pytest.raises(APIParameterException):
        api = SearchAPI.from_settings(
            query="no-query",
            config=config_dict,  # type:ignore
            parameter_config=api.parameter_config,
        )


def test_default_params():
    """Test for whether the defaults are specified correctly:

    1. api key stays null
    2. session defaults to a requests.Session object
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
    """Crossref requires an email, the SearchAPI should send the mailto field to the config for validation."""
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
    """Verifies that the underlying api validator for URLs correctly identifies missing schemas/protocols."""
    crossref = provider_registry.get("crossref")
    assert crossref is not None
    crossref_url = crossref.base_url

    assert validate_and_process_url(None) is None
    assert validate_url("https://") is False
    assert (
        "Expected a domain in the URL after the http/https protocol. " "Only the scheme was received: https://"
    ) in caplog.text
    assert validate_and_process_url(crossref_url) == crossref_url


def test_search_api_url_mailto_validation(caplog):
    """Validates the URL of the SearchAPI to verify that both invalid and valid mailto/URLs are identified as such."""
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
    """Validates and verifies that basic parameters are overridden as needed when preparing the parameters needed to
    retrieve data from each API."""
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
    """Verifies that a cached session is used when specified in the SearchAPI arguments."""
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
    """Tests and verifies that the features needed to prepare a request and receive a response via a SearchAPI instance
    are working as intended and return the MagicMock object."""
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
    """Verifies that, when attempting to retrieve a page, the page start is successfully calculated and fields such as
    `api_key` and `records_per_page` are mapped to their respective values according to the APIParameterConfig."""
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
    """Tests whether responses are successfully cached when using a cached session.

    For this purpose, requests_mock package is used to simulate a request that can be cached to determine whether
    caching is working as intended.

    """
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
    """Tests and verifies that unsuccessful_response_codes are received but not cached when requesting a response via a
    requests_mock mocker."""
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
    """Verifies that an error is raised when an API key is required according to the ParamConfig but is not set."""
    # default_api_parameter_config requires an API key
    with caplog.at_level(logging.WARNING):
        _ = SearchAPI(query="test", parameter_config=default_api_parameter_config)
        assert "An API key is required but was not provided" in caplog.text


def test_cache_expiration(default_api_parameter_config, default_cache_session, default_seconds_cache_expiration):
    """Tests the cache expiration time using requests_cache to ensure that the expiration field is successfully used."""
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
    """Ensures that the URL used in requests preparation can be overridden prior to being sent."""
    api = SearchAPI.from_defaults(query="test", provider_name="core", api_key="this_is_a_fake_api_key")
    req = api.prepare_request("https://api.example.com", "endpoint", {"foo": "bar"}, api_key="123")
    assert isinstance(req.url, str) and req.url.startswith("https://api.example.com/endpoint")
    assert "foo=bar" in req.url
    assert "api_key=123" in req.url


def test_core_api_filtering(monkeypatch, caplog, scholar_flux_logger):
    """
    Tests and verifies that
    1, the API key is successfully prepared in the URL when created
    2. that the Masker, when cleared of all masking patterns corresponding to the API key, automatically masks and adds
       the key to a list of secret strings to mask from logs when preparing the request to be sent
    3. When patching `api.session.send()` to always return a request exception and reveal the full URL in the log,
       that the received API key is replaced with `***`
    """
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
    """Verifies that the `api_key_exists` method is working as intended to ensure that API keys are identified with
    booleans when parameters are built and requests prepared."""
    assert SearchAPI._api_key_exists({"api_key": "123"})
    assert SearchAPI._api_key_exists({"apikey": "123"})
    assert SearchAPI._api_key_exists({"API_KEY": "123"})
    assert SearchAPI._api_key_exists({"APIKEY": "123"})
    assert not SearchAPI._api_key_exists({"foo": "bar"})


def test_with_config_parameters_temporary_override(original_config, original_api_parameter_config):
    """Tests and verifies that the API's SearchAPIConfig can be temporarily overridden with a context manager and the
    `with_api_parameters` method and identically reverted back to the previous SearchAPIConfig after the context manager
    closes."""
    api = SearchAPI(
        query="test",
        base_url=original_config.base_url,
        records_per_page=original_config.records_per_page,
        api_key=original_config.api_key,
        parameter_config=original_api_parameter_config,
    )
    original_config = api.config

    with api.with_config_parameters(records_per_page=99, request_delay=42):
        assert api.config.records_per_page == 99
        assert api.config.request_delay == 42

    # Ensure restoration
    assert api.config == original_config


def test_with_config_parameters_invalid_field_ignored(original_config, original_api_parameter_config):
    """Verifies that fields unknown to the APIParameterConfig are ignored when building parameters for a new request."""
    api = SearchAPI(
        query="test",
        base_url=original_config.base_url,
        records_per_page=original_config.records_per_page,
        api_key=original_config.api_key,
        parameter_config=original_api_parameter_config,
    )
    # copy the current config
    original_config = deepcopy(api.config)

    # Temporarily modify the config -  Pass an invalid field; should not raise
    with api.with_config_parameters(nonexistent_field=123):
        # the field is not added as an extra attribute
        assert not hasattr(api.config, "nonexistent_field")

        # all other other fields should not have changed:
        assert api.config.model_dump(exclude={"api_specific_parameters"}) == original_config.model_dump(
            exclude={"api_specific_parameters"}
        )

        # added but shouldn't be used in the parameter building stages
        assert "nonexistent_field" in (api.config.api_specific_parameters or {})

        # the nonexistent_field, because it's not in the parameter map, won't be added
        assert "nonexistent_field" not in api.build_parameters(page=1)

    assert api.config == original_config
    # the non-existent field should no longer be a part of the api_specific_parameters
    assert "nonexistent_field" not in (api.config.api_specific_parameters or {})


def test_with_config_parameters_exception_restores(original_config, original_api_parameter_config):
    """Tests and verifies that the configuration can temporarily be modified and restored with the context manager."""
    api = SearchAPI(
        query="test",
        base_url=original_config.base_url,
        records_per_page=original_config.records_per_page,
        api_key=original_config.api_key,
        parameter_config=original_api_parameter_config,
    )
    original_config = api.config

    with api.with_config_parameters(records_per_page=77):
        assert api.config.records_per_page == 77

    assert api.config == original_config


def test_with_config_precedence_over_provider(monkeypatch, new_config, original_api_parameter_config):
    """Tests and verifies that the SearchAPIConfig.from_defaults factory method is overridden as intended when the
    `with_config` method is called as a context manager to temporarily change the config.

    The base URL should always take precedence over the provider unless not explicitly provided.

    """
    api = SearchAPI(
        query="test",
        base_url="https://original.com",
        records_per_page=10,
        api_key=new_config.api_key,
        parameter_config=original_api_parameter_config,
    )

    monkeypatch.setattr(
        SearchAPIConfig,
        "from_defaults",
        lambda provider_name: SearchAPIConfig(
            base_url="https://shouldnotuse.com", records_per_page=1, request_delay=1, api_key=None
        ),
    )
    monkeypatch.setattr(
        APIParameterConfig,
        "from_defaults",
        lambda provider_name: APIParameterConfig(parameter_map=MagicMock(spec=APIParameterMap)),
    )

    # Explicit config should take precedence over provider_name
    previous_config = deepcopy(api.config)
    with api.with_config(config=new_config, provider_name="testprovider"):
        assert api.config == new_config
        assert api.config.base_url == "https://new.com"
    assert api.config != new_config and api.config == previous_config


def test_updates():
    """Ensures that updates to the API occur in the intended manner:

    1. Calling update with only a SearchAPIConfig will return the identical config
    2. Calling update without a SearchAPI object will throw an error, because `update` is a classmethod and
       requires a SearchAPI for the first argument.

    """
    api = SearchAPI(query="test")

    identical_api = SearchAPI.update(api)

    assert repr(identical_api) == repr(identical_api)

    with pytest.raises(APIParameterException) as excinfo:
        _ = api.update(None, config=api.config, parameter_config=api.parameter_config)  # type: ignore

    assert f"Expected a SearchAPI to perform parameter updates. Received type {type(None)}" in str(excinfo.value)


def test_nested_with_config_and_with_config_parameters(
    original_config, new_config, original_api_parameter_config, new_api_parameter_config
):
    """Verifies that nested context managers modifies the current config with precedence given to the latest context
    that modifies the configuration and other parameters for the SearchAPI."""
    api = SearchAPI(
        query="test",
        base_url=original_config.base_url,
        records_per_page=original_config.records_per_page,
        api_key=original_config.api_key,
        parameter_config=original_api_parameter_config,
    )
    original_config = api.config
    orig_api_parameter_config = api.parameter_config

    with api.with_config(config=new_config, parameter_config=new_api_parameter_config):
        # Inside first context: config and parameter_config are swapped
        assert api.config == new_config
        assert api.parameter_config == new_api_parameter_config

        with api.with_config_parameters(records_per_page=123, request_delay=99):
            # Inside nested context: config is a modified copy of new_config
            assert api.config.records_per_page == 123
            assert api.config.request_delay == 99
            # parameter_config remains as new_api_parameter_config
            assert api.parameter_config == new_api_parameter_config

        # After inner context: config and parameter_config are as in outer context
        assert api.config == new_config
        assert api.parameter_config == new_api_parameter_config

    # After both contexts: originals are restored
    assert api.config == original_config
    assert api.parameter_config == orig_api_parameter_config


def test_from_provider_config(caplog):
    """Helper method for validating the functionality of the `from_provider_config` method. This method should allow the
    creation of a SearchAPI instance with a provider configuration by temporarily adding it to the registry.

    If the provider already exists, then this method will temporarily replace the current config while conserving the
    previous configuration until the SearchAPI is created.

    """
    provider_name = "plos"
    query = "q"
    plos = provider_registry[provider_name]
    plos_api_one = SearchAPI.from_defaults(query=query, provider_name=provider_name)
    plos_api_two = SearchAPI.from_provider_config(query=query, provider_config=plos)

    assert repr(plos_api_one) == repr(plos_api_two)
    assert provider_name in provider_registry  # ensure that the temporary addition does not change

    assert plos is provider_registry["plos"]

    # ensure even minor changes to parameters do not temporarily replaced configurations
    plos_10_records = plos.model_copy()
    plos_10_records.records_per_page = plos.records_per_page + 10

    plos_api_three = SearchAPI.from_provider_config(query=query, provider_config=plos_10_records)
    assert plos_api_three.records_per_page == plos_10_records.records_per_page

    # the updated config should still be configured to retrieve 10 more records than the original
    assert (
        plos_10_records.records_per_page == provider_registry[provider_name].records_per_page + 10
        and provider_registry[provider_name] is plos
    )

    plosser = plos.model_copy()
    plosser.provider_name = "plosser"
    plosser.base_url = plosser.base_url.replace("plos", "plosser")
    plos_api_two = SearchAPI.from_provider_config(query=query, provider_config=plosser)
    assert plos_api_two.provider_name == "plosser" and "plosser" not in provider_registry

    with pytest.raises(APIParameterException) as excinfo:
        _ = SearchAPI.from_provider_config(query=query, provider_config=provider_name)  # type: ignore

    assert "The SearchAPI could not be created with the provided configuration" in caplog.text
    assert "The SearchAPI could not be created with the provided configuration" in str(excinfo.value)

    assert provider_name in provider_registry


def test_missing_parameters():
    """Validates that an APIParameterException is thrown when neither page nor parameter is provided."""
    api = SearchAPI(query="new query")
    with pytest.raises(APIParameterException) as excinfo:
        api.search()
    assert "One of 'page' or 'parameters' must be provided" in str(excinfo.value)


def test_parameter_exceptions(monkeypatch, mock_successful_response):
    """Tests whether an APIParameterException is raised when the `parameters` argument to `prepare_request` is not a
    dictionary as intended."""
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
    """Validates that the omission of a base URL in the preparation of a request will return the automatically same URL
    value for the API as when it is specified explicitly."""
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
    """Validates and tests whether the request delay, when modified with a context manager, successfully changes the
    duration between requests for the duration of the context."""
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
