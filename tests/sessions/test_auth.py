"""Tests for verifying basic session authentication with API keys."""

import pytest
from pydantic import SecretStr
from scholar_flux.sessions.auth import AuthAPIKeyBase, AuthAPIKeyNoOp, AuthAPIKeyHeader, AuthAPIKeyParameter
from scholar_flux.security import SecretUtils
from scholar_flux.exceptions import APIParameterException, APIKeyValidationException
import requests


@pytest.fixture
def patch_auth_base(monkeypatch):
    """Patches AuthAPIKeyBase allow direct instantiation for testing base class methods."""
    monkeypatch.setattr(AuthAPIKeyBase, "__abstractmethods__", set())


@pytest.fixture
def auth_base(patch_auth_base, mock_api_key) -> AuthAPIKeyBase:
    """Creates a basic AuthAPIKeyBase bypassing the abstract method checks."""
    return AuthAPIKeyBase(api_key=SecretUtils.unmask_secret(mock_api_key))  # type: ignore


@pytest.fixture
def auth_header(mock_api_key) -> AuthAPIKeyHeader:
    """Creates a AuthAPIKeyHeader for later testing."""
    return AuthAPIKeyHeader(api_key=mock_api_key, parameter_name="Authentication", scheme="Bearer")


@pytest.fixture
def auth_parameter(mock_api_key) -> AuthAPIKeyParameter:
    """Creates a AuthAPIKeyParameter for later testing."""
    return AuthAPIKeyParameter(api_key=SecretUtils.unmask_secret(mock_api_key), parameter_name="secret")


@pytest.fixture
def mock_base_url() -> str:
    """Defines the name of the base URL used for testing auth functionality."""
    return "https://example-url.com"


@pytest.fixture
def mock_prepared_request(mock_base_url) -> requests.PreparedRequest:
    """Mocks a prepared URL for later testing."""
    request = requests.Request("GET", mock_base_url, params={"q": "example query"})
    prepared_request = request.prepare()
    return prepared_request


def test_auth_base_initialization(auth_base, mock_api_key):
    """Verifies that an AuthAPIKeyBase can be initialized, bypassing ABC instantiation via `patch_auth_base`"""
    assert auth_base
    assert auth_base.api_key == mock_api_key  # should be masked automatically on assignment
    assert auth_base.parameter_name == AuthAPIKeyBase.DEFAULT_PARAMETER_NAME  # defaults to the class var


def test_auth_api_key_header_initialization(auth_header, mock_api_key):
    """Verifies that the AuthAPIKeyHeader initializes as intended with the expected configuration."""
    assert auth_header.api_key == mock_api_key
    assert auth_header.parameter_name == "Authentication"
    assert auth_header.scheme == "Bearer"


def test_auth_api_key_parameter_initialization(auth_parameter, mock_api_key):
    """Verifies that the AuthAPIKeyParameter initializes as intended with the expected configuration."""
    assert auth_parameter.api_key == mock_api_key
    assert auth_parameter.parameter_name == "secret"


def test_auth_api_key_noop_functionality(mock_api_key, mock_prepared_request) -> None:
    """Tests the functionality of the `AuthAPIKeyNoOp` to ensure that it operates as a No-Op."""
    auth_noop = AuthAPIKeyNoOp(api_key=mock_api_key, parameter_name="api_key")  # both are completely no-op
    assert auth_noop.api_key is None
    assert auth_noop.parameter_name is None

    request = mock_prepared_request.copy()
    identical_request = auth_noop(mock_prepared_request)

    assert request.url == identical_request.url
    assert request.headers == identical_request.headers


def test_auth_base_call_raises_not_implemented_error(auth_base, mock_prepared_request):
    """Verifies that an AuthBase can be initialized, bypassing ABC instantiation via `patch_auth_base`"""
    with pytest.raises(NotImplementedError):
        _ = auth_base(mock_prepared_request)


def test_auth_parameter_reassignment(mock_api_key):
    """Verifies that reassigning AuthAPIKeyParameter properties will validate and format the modified assignments."""
    auth_parameter = AuthAPIKeyParameter(mock_api_key)

    parameter_name = "api_key"

    auth_parameter.api_key = SecretUtils.unmask_secret(mock_api_key)
    assert auth_parameter.api_key == mock_api_key  # validated and masked on reassignment

    assert auth_parameter.parameter_name == AuthAPIKeyBase.DEFAULT_PARAMETER_NAME
    auth_parameter.parameter_name = parameter_name
    assert auth_parameter.parameter_name == parameter_name


def test_auth_header_reassignment(mock_api_key):
    """Verifies that re-assigning AuthAPIKeyHeader properties will validate and format the modified assignments."""
    auth_header = AuthAPIKeyHeader(SecretUtils.unmask_secret(mock_api_key))

    parameter_name = "Authentication"
    scheme = "Bearer"

    auth_header.api_key = mock_api_key
    assert auth_header.api_key == mock_api_key  # validated and masked on reassignment

    assert auth_header.parameter_name == AuthAPIKeyBase.DEFAULT_PARAMETER_NAME
    auth_header.parameter_name = parameter_name
    assert auth_header.parameter_name == parameter_name

    auth_header.scheme = scheme
    assert auth_header.scheme == scheme


def test_auth_parameter_call(auth_parameter, mock_prepared_request):
    """Verifies that AuthAPIKeyParameter.__call__ successsfully adds an API key parameter to prepared requests."""
    expected = f"{auth_parameter.parameter_name}={SecretUtils.unmask_secret(auth_parameter.api_key)}"

    updated_request = auth_parameter(mock_prepared_request)
    assert isinstance(updated_request, requests.PreparedRequest) and updated_request.url
    assert expected in updated_request.url


def test_auth_parameter_call_when_duplicated(auth_parameter, mock_prepared_request, mock_base_url, caplog):
    """Verifies that AuthAPIKeyParameter.__call__ is idempotent, producing the same URL on each successive call."""
    expected = f"{auth_parameter.parameter_name}={SecretUtils.unmask_secret(auth_parameter.api_key)}"

    updated_request = auth_parameter(mock_prepared_request)
    assert isinstance(updated_request, requests.PreparedRequest) and updated_request.url
    assert expected in updated_request.url

    url_first_call = str(updated_request.url)  # save the URL since `prepare_request()` is otherwise overwritten
    reupdated_request = auth_parameter(updated_request)
    assert url_first_call == reupdated_request.url
    assert f"Replacing API key field for base URL, '{mock_base_url}'..." in caplog.text


def test_auth_header_call(auth_header, mock_prepared_request):
    """Verifies that AuthAPIKeyHeader.__call__ successfully adds an API key header to prepared requests."""
    unmasked_key = SecretUtils.unmask_secret(auth_header.api_key)
    expected = f"{auth_header.scheme} {unmasked_key}"
    not_expected = f"{auth_header.parameter_name}={unmasked_key}"

    updated_request = auth_header(mock_prepared_request)
    assert isinstance(updated_request, requests.PreparedRequest) and updated_request.url and updated_request.headers
    assert not_expected not in updated_request.url
    assert auth_header.parameter_name in updated_request.headers
    assert updated_request.headers[auth_header.parameter_name] == expected


def test_auth_parameter_invalid_type_reassignment_raises(auth_parameter):
    """Verifies that AuthAPIKeyParameter inherits AuthAPIKeyBase validation to raise on invalid types."""

    invalid_parameter_name = [1, 2, 3]
    parameter_name_err = (
        "The `AuthAPIKeyParameter` expected a valid API key parameter name but instead received "
        f"{type(invalid_parameter_name)}"
    )

    with pytest.raises(APIParameterException, match=parameter_name_err):
        auth_parameter.parameter_name = invalid_parameter_name

    invalid_api_key = {4, 5, 6}
    api_key_err = f"The `AuthAPIKeyParameter` expected a valid API key but instead received {type(invalid_api_key)}"

    with pytest.raises(APIKeyValidationException, match=api_key_err):
        auth_parameter.api_key = invalid_api_key


def test_auth_parameter_raises_on_empty_api_key(auth_parameter):
    """Verifies that AuthAPIKeyParameter inherits AuthAPIKeyBase validation to raise on invalid types."""
    invalid_api_key = SecretStr("")

    api_key_err = "The `AuthAPIKeyParameter` expected a valid API key but the value received is an empty `SecretStr`."

    with pytest.raises(APIKeyValidationException, match=api_key_err):
        auth_parameter.api_key = invalid_api_key

    invalid_api_key = None  # type: ignore

    api_key_err = "The `AuthAPIKeyParameter` expected a valid API key but the value received is None."

    with pytest.raises(APIKeyValidationException, match=api_key_err):
        auth_parameter.api_key = invalid_api_key


def test_auth_header_invalid_type_reassignment_raises(auth_header):
    """Verifies that AuthAPIKeyHeader inherits AuthAPIKeyBase validation to raise on invalid types."""

    invalid_parameter_name = {1: "1", 2: "2", 3: "3"}
    parameter_name_err = (
        "The `AuthAPIKeyHeader` expected a valid API key parameter name but instead received "
        f"{type(invalid_parameter_name)}"
    )

    with pytest.raises(APIParameterException, match=parameter_name_err):
        auth_header.parameter_name = invalid_parameter_name

    invalid_api_key = (7, 8, 9, 10)
    api_key_err = f"The `AuthAPIKeyHeader` expected a valid API key but instead received {type(invalid_api_key)}"

    with pytest.raises(APIKeyValidationException, match=api_key_err):
        auth_header.api_key = invalid_api_key

    invalid_scheme = 11
    scheme_err = (
        f"The `AuthAPIKeyHeader` expected a valid scheme for the API key but instead received {type(invalid_scheme)}"
    )

    with pytest.raises(APIParameterException, match=scheme_err):
        auth_header.scheme = invalid_scheme


def test_auth_header_invalid_masked_type_reassignment_raises(auth_header):
    """Verifies that validation with an AuthAPIKeyBase raises on invalid masked secrets."""

    invalid_api_key = SecretUtils.mask_secret([1, 2, 3], convert_object=False)
    err = (
        "The `AuthAPIKeyHeader` expected the unmasked API key to be of type `str` but instead received "
        f"{type(invalid_api_key)}"
    )

    with pytest.raises(APIParameterException, match=err):
        auth_header.api_key = invalid_api_key


def test_auth_header_representation(auth_header):
    """Verifies that AuthAPIKeyHeader correctly shows the current configuration when viewed via `repr`."""
    key, name, scheme = auth_header.api_key, auth_header.parameter_name, auth_header.scheme
    expected = f"AuthAPIKeyHeader(api_key={key}, parameter_name='{name}', scheme='{scheme}')"
    assert repr(auth_header) == expected


def test_auth_parameters_representation(auth_parameter):
    """Verifies that AuthAPIKeyParameters correctly shows the current configuration when viewed via `repr`."""
    key, name = auth_parameter.api_key, auth_parameter.parameter_name
    expected = f"AuthAPIKeyParameter(api_key={key}, parameter_name='{name}')"
    assert repr(auth_parameter) == expected


def test_auth_noop_representation():
    """Verifies that AuthAPIKeyNoOp correctly shows the current configuration when viewed via `repr`."""
    auth_noop = AuthAPIKeyNoOp()
    expected = "AuthAPIKeyNoOp()"
    assert repr(auth_noop) == expected
