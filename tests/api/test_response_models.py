import json
import re
from collections import UserDict
from collections.abc import MutableMapping
from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import datetime
from http.client import responses
from typing import Any
from unittest.mock import patch

import pytest
from requests import RequestException, Response

from scholar_flux.api.models.responses import (
    APIResponse,
    ErrorResponse,
    NonResponse,
    ProcessedResponse,
    ReconstructedResponse,
)
from scholar_flux.api.models.search_results import SearchResult
from scholar_flux.api.response_validator import ResponseValidator
from scholar_flux.exceptions import InvalidResponseReconstructionException, InvalidResponseStructureException
from scholar_flux.utils import (
    ResponseProtocol,
    coerce_bytes,
    generate_iso_timestamp,
    is_response_like,
    parse_iso_timestamp,
    quote_if_string,
)
from tests.testing_utilities import raise_error


class DummyResponse(Response):
    """Helper class for testing how `status_code` functions for requests.Response subclasses."""

    def __init__(*args, **kwargs):
        pass

    @property
    def status_code(self) -> int:  # type: ignore
        """Used to automatically raise a ValueError for later testing with the ReconstructedResponse class."""
        raise ValueError


@dataclass
class URL:
    """Helper for testing URL validation with specific objects."""

    value: str

    def __str__(self) -> str:
        """Helper that returns the underlying url."""
        return self.value


@dataclass
class ResponseLikeObject:
    """Helper for validating response parsing for response-like objects."""

    status_code: int
    headers: MutableMapping[str, str]
    content: bytes
    url: URL | str

    def raise_for_status(self) -> None:
        """Dummy method for raising an exception for HTTP error status codes."""

    def validate(self) -> None:
        """Helper for performing field validation via the `ResponseValidator`."""
        ResponseValidator.validate_response_structure(self)


def test_build_with_response_like():
    """Verifies that response-like objects are coerced as ReconstructedResponse if possible when validation fails."""

    response_like = ResponseLikeObject(
        status_code="200",  # type: ignore
        headers={"Content-Type": "application/json", "User-Agent": b"ExampleApp/1.0"},  # type: ignore
        content="success",  # type: ignore
        url=URL("https://httpbin.org/status/200"),
    )
    assert is_response_like(response_like) and isinstance(response_like, ResponseLikeObject)

    with pytest.raises(InvalidResponseStructureException):
        response_like.validate()

    expected_headers = dict(response_like.headers)
    expected_headers["User-Agent"] = expected_headers["User-Agent"].decode()
    expected_content = coerce_bytes(response_like.content)

    reconstructed_response = ReconstructedResponse.build(response_like)
    reconstructed_response.validate()

    # Coercion occurs within `ReconstructedResponse`
    assert reconstructed_response.status_code == int(response_like.status_code)
    assert reconstructed_response.reason == responses.get(int(response_like.status_code))
    assert reconstructed_response.headers == expected_headers
    assert reconstructed_response.content == expected_content
    assert isinstance(response_like.url, URL) and reconstructed_response.url == response_like.url.value

    # converted to `ReconstructedResponse` under the hood
    api_response = APIResponse(response=response_like)
    assert api_response.response == reconstructed_response


def test_build_with_arbitrary_response_like_object():
    """Verifies that `APIResponse` objects coerce response-like objects into `ReconstructedResponses` on creation."""
    response_like = ResponseLikeObject(
        status_code=400,
        headers={"Content-Type": "application/json"},
        content=b"Bad Request",
        url="https://httpbin.org/status/400",
    )

    response = APIResponse(response=response_like)
    assert isinstance(response.response, ReconstructedResponse)
    assert response.validate_response()


def test_build_with_response_like_raises_exception(monkeypatch, caplog):
    """Validates the log message shared when the conversion of response-like objects fails from unexpected errors."""
    response_like = ResponseLikeObject(
        status_code=429,
        headers={"Content-Type": "application/json"},
        content=b"OK",
        url="https://httpbin.org/status/429",
    )

    api_response = APIResponse(response=response_like)
    assert api_response.response

    message = "Directly raised exception"
    monkeypatch.setattr(
        ReconstructedResponse,
        "build",
        raise_error(InvalidResponseReconstructionException, message),
    )

    # The object has fields typically associated with a response-like object:
    assert ResponseValidator.validate_response_like(response_like)

    response_like_err = f"The object of type 'ResponseLikeObject' does not contain valid response fields: {message}"
    with pytest.raises(InvalidResponseStructureException, match=response_like_err):
        _ = APIResponse.as_reconstructed_response(response_like)

    api_response_err = f"The object of type 'APIResponse' does not contain a valid raw response: {message}"
    with pytest.raises(InvalidResponseStructureException, match=api_response_err):
        _ = APIResponse.as_reconstructed_response(api_response)

    new_api_response = APIResponse(response=response_like)
    assert new_api_response.response is None
    api_response_creation_err = (
        f"A valid response could not be reconstructed from the object of type ResponseLikeObject: {response_like_err}"
    )
    assert api_response_creation_err in caplog.text


def test_build_with_non_response_like_raises_exception():
    """Verifies that `as_reconstructed_response` raises an exception when the received object is not a response."""
    non_response_like = ["not", "a", "response", "like"]
    err = f"The object of type 'list' does not contain valid response fields: The current class of type {type(non_response_like)} is not a response or response-like object."
    with pytest.raises(InvalidResponseStructureException, match=re.escape(err)):
        _ = APIResponse.as_reconstructed_response(non_response_like)


def test_build_with_response_dict_with_invalid_fields_raises_exception(monkeypatch, caplog):
    """Verifies that an `InvalidResponseReconstructionException` is raised when encountering a reconstruction error."""
    response_like = ResponseLikeObject(
        status_code=429,
        headers={"Content-Type": "application/json"},
        content=b"OK",
        url="https://httpbin.org/status/429",
    )

    response_dict = asdict(response_like)
    response_dict.pop("url")

    err = (
        r"The object of type 'dict' does not contain valid response fields: Missing the core required fields needed "
        "to create a ReconstructedResponse: 'url'"
    )
    with pytest.raises(InvalidResponseStructureException, match=err):
        _ = APIResponse.as_reconstructed_response(response_dict)


@patch("scholar_flux.utils.helpers.try_int")
def test_status_code_code_property(mock_try_int, mock_successful_response):
    """Tests whether the `status_code` property accounts for ValueErrors and retrieves status codes when available."""
    api_response = APIResponse(cache_key="key", response=DummyResponse())
    code = api_response.status_code
    assert code is None

    api_response_two = APIResponse(cache_key="key", response=mock_successful_response)
    assert api_response_two.status_code == 200

    api_response_three = APIResponse(cache_key="key", response=None)
    assert api_response_three.status_code is None


def test_blank_initialization():
    """Verifies that initializing a reconstructed response is possible when explicitly setting `url` and `status_code`
    to None."""
    response = ReconstructedResponse.build(url=None, status_code=None)

    assert response
    assert response.reason is None and response.status_code is None and response.headers == {} and response.url is None
    assert not response.is_response()

    api_response = APIResponse.from_response(url=None, status_code=None, created_at=None)
    assert api_response.response == response
    assert api_response.url is None
    assert api_response.status_code is None
    assert api_response.created_at is None

    with pytest.raises(NotImplementedError):
        assert api_response.process_metadata() is None


def test_error_response_representation(mock_unauthorized_response):
    """Verifies the representation of the `ErrorResponse` as defined by its original parent class __repr__."""
    error_response = ErrorResponse(cache_key="key", response=mock_unauthorized_response)
    assert repr(error_response) == f"ErrorResponse(status_code={error_response.status_code}, error=None, message=None)"


def test_error_response_metadata_fields(mock_unauthorized_response):
    """Tests if `ErrorResponse` properties, more so specific to `ProcessedResponse`, default to 0/`None` instead."""
    error_response = ErrorResponse(cache_key="key", response=mock_unauthorized_response)
    assert not error_response.record_count
    assert error_response.total_query_hits is None
    assert error_response.records_per_page is None
    assert error_response.process_metadata() is None and error_response.processed_metadata is None


def test_success_response():
    """Tests if the processed records and data fields are populated as intended for a ProcessedResponse."""
    response_dict: list[dict] = [{1: 1}, {2: 2}, {3: 3}, {4: 4}]
    processed_response = ProcessedResponse(processed_records=response_dict)
    assert processed_response and processed_response.data
    assert len(processed_response) == 4 == len(processed_response.data) == processed_response.record_count


def test_api_response_from_response(mock_successful_response):
    """Verifies elements of the `APIResponse` parent class such as status code, status, cache_key, etc."""
    api_response = APIResponse.from_response(response=mock_successful_response, cache_key="foo")
    assert api_response.status_code == 200
    assert api_response.cache_key == "foo"
    assert api_response.status == "OK"
    assert api_response.headers is not None


def test_api_response_from_kwargs():
    """Verifies that header, content, and other relevant fields are populated as intended when constructed manually."""
    api_response = APIResponse.from_response(
        status_code=201,
        headers={"X-Test": "yes"},
        content=b'{"foo": "bar"}',
        text='{"foo": "bar"}',
        url="https://api.example.com/test",
    )
    assert api_response.status_code == 201
    assert api_response.headers == {"X-Test": "yes"}
    assert api_response.content == b'{"foo": "bar"}'
    assert api_response.text == '{"foo": "bar"}'
    assert api_response.url == "https://api.example.com/test"
    assert isinstance(api_response.response, ReconstructedResponse)


def test_api_response_serialize_and_deserialize(mock_successful_response):
    """Tests idempotence and the reliability of serializing and deserializing responses using ReconstructedResponses and
    the most important fields derived from response classes."""
    api_response = APIResponse.from_response(response=mock_successful_response, cache_key="foo", auto_created_at=True)

    # Validates the response class on initialization
    assert isinstance(api_response.response, Response)

    dumped = api_response.model_dump_json()
    loaded = APIResponse.model_validate_json(dumped)
    assert loaded.status_code == 200
    assert loaded.cache_key == "foo"
    assert loaded.status == "OK"

    # Response classes are reloaded as reconstructed responses:
    assert isinstance(loaded.response, ReconstructedResponse)

    redumped = loaded.model_dump_json()
    reloaded = APIResponse.model_validate_json(redumped)
    assert loaded == reloaded

    # testing components
    assert api_response.response is not None
    encoded_response = api_response._encode_response(api_response.response)
    serialized_response = json.dumps(encoded_response)
    assert isinstance(encoded_response, dict)

    string_deserialized_response = api_response.from_serialized_response(serialized_response)
    kw_deserialized_response = api_response.from_serialized_response(**encoded_response)
    response_dict_deserialized_response = api_response.from_serialized_response(encoded_response)
    assert isinstance(response_dict_deserialized_response, ReconstructedResponse)
    assert kw_deserialized_response == response_dict_deserialized_response == string_deserialized_response


def test_deserialize_response_dict(monkeypatch, caplog):
    """Verifies whether deserialization occurs as intended when encountering errors in the deserialization process."""
    response = APIResponse.from_response(status_code=200, content=b"success", url="https://examples.com")

    exc = "Directly raised exception"
    monkeypatch.setattr(APIResponse, "from_serialized_response", raise_error(TypeError, exc))

    response_dict = response.model_dump()

    deserialized_response = response.transform_response(response_dict)  # type: ignore
    assert deserialized_response is deserialized_response  # can't serialize/process the response, so returns as is
    assert f"Couldn't decode a valid response object: {exc}" in caplog.text

    # desrialization for invalid values should return None
    assert APIResponse._deserialize_response_dict([]) is None  # type: ignore
    assert (
        "Could not decode the response argument from a string to JSON object: the JSON object "
        "must be str, bytes or bytearray, not list"
    ) in caplog.text


def test_reconstructed_response_json():
    """Tests whether reconstructed responses from JSON objects can be parsed as intended using the `json()` method."""
    rr = ReconstructedResponse(
        status_code=200,
        reason="OK",
        headers={"Content-Type": "application/json"},
        content=b"[1,2,3]",
        url="https://api.example.com/test",
    )
    assert rr.json() == [1, 2, 3]


def test_reconstructed_response_equality():
    """Verifies that reconstructed response objects check underlying data to determine if two instances are equal."""
    rr1 = ReconstructedResponse(status_code=200, reason="OK", headers={}, content=b"abc", url="u")
    rr2 = deepcopy(rr1)
    assert rr1 == rr2
    rr2.headers["Content-Type"] = "application/json"
    assert rr1 != rr2


def test_validate_api_response(mock_successful_response):
    """Verifies that successful Response objects are identified as such with `APIResponse.validate_response()`."""
    api_response = APIResponse.from_response(response=mock_successful_response)
    assert api_response.validate_response(raise_on_error=True)


def test_api_response_validate_response_like():
    """Verifies that a bad URL is identified as such with `APIResponse.validate_response()`."""
    api_response = APIResponse.from_response(status_code=200, headers={}, content=b"", text="", url="u")
    assert not api_response.validate_response()


def test_api_response_as_json_with_invalid_json():
    """Verifies that non-json content, when converted into JSON format returns None instead."""
    api_response = APIResponse.from_response(status_code=200, headers={}, content=b"notjson", text="notjson", url="u")
    assert isinstance(api_response.response, ReconstructedResponse) and api_response.response.json() is None


def test_api_response_headers_warning(caplog):
    class BadHeaders:
        pass

    api_response = APIResponse.from_response(status_code=200, headers=BadHeaders(), content=b"", text="", url="u")
    with caplog.at_level("WARNING"):
        _ = api_response.headers
        assert "does not have a valid response header" in caplog.text


def test_reconstructed_response_valid():
    api_response = APIResponse.from_response(status_code=200, headers={}, content=b"", text="", url="u")

    with pytest.raises(InvalidResponseReconstructionException):
        api_response.response.validate()  # type: ignore


def test_reconstructed_response_validation():
    # Valid response
    valid_response = ReconstructedResponse(
        status_code=200,
        reason="OK",
        url="https://example.com",
        content=b"content",
        headers={"Content-Type": "text/plain"},
    )
    assert valid_response.is_response()

    # Invalid status code
    invalid_status_code_response = ReconstructedResponse(
        status_code=-1,  # Invalid status code
        reason="OK",
        url="https://example.com",
        content=b"content",
        headers={"Content-Type": "text/plain"},
    )
    assert not invalid_status_code_response.is_response()


def test_reconstructed_response_validate():
    valid_response = ReconstructedResponse(
        status_code=200,
        reason="OK",
        url="https://example.com",
        content=b"content",
        headers={"Content-Type": "text/plain"},
    )
    valid_response.validate()  # Should not raise an exception

    invalid_status_code_response = ReconstructedResponse(
        status_code=-1,  # Invalid status code
        reason="OK",
        url="https://example.com",
        content=b"content",
        headers={"Content-Type": "text/plain"},
    )
    with pytest.raises(InvalidResponseReconstructionException):
        invalid_status_code_response.validate()


def test_api_response_creation():
    # Create from keyword arguments
    api_response_from_kwargs = APIResponse.from_response(
        status_code=201,
        reason="Created",
        url="https://example.com",
        content=b"created content",
        headers={"Content-Type": "application/json"},
    )
    assert api_response_from_kwargs.response is not None and api_response_from_kwargs.response.status_code == 201

    api_response_from_kwargs_two = APIResponse.from_response(
        status_code=401,
        url="https://example.com",
        content=b"created content",
        headers={"Content-Type": "application/json"},
    )
    assert (
        api_response_from_kwargs_two.response is not None and api_response_from_kwargs_two.response.status_code == 401
    )

    # each of these comparisons should be unequal
    assert api_response_from_kwargs != api_response_from_kwargs_two != 401


def test_api_response_serialization():
    api_response = APIResponse.from_response(
        status_code=200,
        reason="OK",
        url="https://example.com",
        content=b"content",
        headers={"Content-Type": "text/plain"},
    )
    serialized_data = api_response.model_dump_json()
    serialized_response = json.loads(serialized_data)["response"]
    assert "status_code" in serialized_response
    assert serialized_response["status_code"] == 200


def test_failed_serialization():
    """Verifies that non-response-like objects (even if directly assigned) are not serialized."""

    basic_dict: UserDict[str, Any] = UserDict()
    api_response = APIResponse(cache_key=None, response=basic_dict)  # type: ignore
    assert api_response.response is None
    api_response.response = basic_dict  # type: ignore

    # a user dict isn't a response-like object, so it is not serialized
    json_data = api_response.model_dump_json()
    assert json.loads(json_data)["response"] is None


def test_representation():
    """Verifies that the representation of an APIResponse shows the correct fields in the expected format."""
    response = APIResponse.from_response(
        cache_key="test-key",
        status_code=200,
        url="https://another-example.com",
    )
    representation = repr(response)

    assert re.search(r"APIResponse\(cache_key='test-key',(\n| )*response=ReconstructedResponse\(.*\)\)", representation)


def test_api_response_timestamp_validation(caplog):
    """Verifies that timestamps are automatically validated on APIResponse creation."""
    example_timestamp = generate_iso_timestamp()
    keywords = dict(
        cache_key="another-test-key", status=200, url="https://another-example.com", created_at=example_timestamp
    )

    response = APIResponse.model_validate(keywords)
    assert response.created_at is not None and response.created_at == example_timestamp

    # parse the timestamp into a date-time value from string format
    parsed_example_timestamp = parse_iso_timestamp(example_timestamp)
    assert isinstance(parsed_example_timestamp, datetime)

    # created_at implicitly formatted as a string in iso 8601 format
    dt_response = APIResponse.model_validate(keywords | dict(created_at=parsed_example_timestamp))
    assert dt_response.created_at is not None
    assert parse_iso_timestamp(dt_response.created_at) == parsed_example_timestamp

    # non-parseable strings not allowed --> None
    invalid_value = "an invalid datetime"
    invalid_dt_response = APIResponse.model_validate(keywords | dict(created_at=invalid_value))
    assert invalid_dt_response.created_at is None
    assert f"Expected a parsed timestamp but received an unparseable value: {invalid_value}" in caplog.text

    caplog.clear()

    # non-datetime/parseable string fields not allowed --> None
    another_invalid_dt_response = APIResponse.model_validate(keywords | dict(created_at=True))

    assert another_invalid_dt_response.created_at is None
    assert f"Expected an iso8601-formatted datetime, but received type ({bool})" in caplog.text


def test_raise_for_status():
    valid_response = ReconstructedResponse.build(
        status_code=200, url="https://example.com", content=b"content", headers={"Content-Type": "text/plain"}
    )

    # direct comparison with a reconstructed response
    api_response = APIResponse(response=valid_response)
    assert valid_response.ok

    # If valid, an error is not raised.
    api_response.raise_for_status()

    # ensuring that, as a dictionary, when reconstructed into a response, no error:
    api_response.response = valid_response.asdict()  # type: ignore
    api_response.raise_for_status()

    # changing it back for future dumping and direct checking against the response
    api_response.response = valid_response

    api_response_two = APIResponse(response=api_response.model_dump().get("response"))

    # Should also not raise an exception
    api_response_two.raise_for_status()

    invalid_response = ReconstructedResponse.build(
        status_code=500, url="https://example.com", content=b"error", headers={"Content-Type": "text/plain"}
    )

    assert not invalid_response.ok
    invalid_api_response = APIResponse(response=invalid_response)

    with pytest.raises(RequestException) as excinfo:
        invalid_api_response.raise_for_status()
        assert (
            "Expected a 200 (ok) status_code for the ReconstructedResponse. Received: "
            f"{invalid_response.status_code} ({invalid_response.reason or invalid_response.status})"
        ) in str(excinfo.value)

    invalid_response_two = ReconstructedResponse.build(
        status_code=None, url="https://example.com", content=b"success?", headers={"Content-Type": "text/plain"}
    )
    assert not invalid_response_two.ok

    assert invalid_response != invalid_response_two

    invalid_api_response_two = APIResponse(response=invalid_response_two)

    with pytest.raises(RequestException) as excinfo:
        invalid_api_response_two.raise_for_status()
        assert (
            "Could not verify from the ReconstructedResponse to determine whether the "
            "original request was successful "
        ) in str(excinfo.value)


def test_blank_content():
    api_response = APIResponse.from_response(
        status_code=200, url="https://www.another_example.com", text="", headers={"Content-Type": "text/plain"}
    )

    reconstructed_response = ReconstructedResponse.build(
        status_code=200, url="https://www.another_example.com", text="", headers={"Content-Type": "text/plain"}
    )

    assert api_response and api_response.content is not None and api_response.text is not None
    assert (
        reconstructed_response
        and reconstructed_response.content is not None
        and reconstructed_response.text is not None
    )


def test_properties(caplog):
    """Verifies the APIResponse properties are correctly handled for both response-like objects and `None`."""
    api_response = APIResponse.from_response(
        status_code=200,
        reason=True,
        url="https://www.another_example.com",
        content="not bytes",
        headers={"Content-Type": "text/plain"},
    )
    assert api_response.response is not None
    assert api_response.cached is None  # When a requests.Response is not available, `cached` is None

    assert api_response.reason is None  # a boolean reason is not a valid value
    assert api_response.content == b"not bytes"
    assert api_response.text == "not bytes"
    api_response.response.content = False  # type: ignore
    assert api_response.content is None
    assert api_response.text is None
    assert "The current APIResponse does not have a valid response content attribute" in caplog.text
    assert "The current APIResponse does not have a valid response text attribute" in caplog.text
    caplog.clear()

    api_response.response.content = "also not bytes"
    assert api_response.content is None
    assert "The current APIResponse does not have a valid response content attribute" in caplog.text

    assert api_response.headers and isinstance(api_response.headers, dict)
    api_response.response.headers = True
    assert api_response.headers is None
    assert "The current APIResponse does not have a valid response header" in caplog.text

    assert api_response.url
    api_response.response.url = "not-an-url"

    assert api_response.url is None
    assert f"The value, '{api_response.response.url}' is not a valid URL" in caplog.text


def test_no_response():
    """Verifies that an empty API response object automatically defaults missing response field properties with None."""
    api_response = APIResponse()
    assert api_response.url is None
    assert api_response.reason is None
    assert api_response.status_code is None
    assert api_response.status is None
    assert api_response.content is None
    assert api_response.text is None


def test_reconstruction():
    """Verifies that ReconstructedResponse objects can be created used in the place of request.Response objects."""
    api_response = APIResponse.from_response(
        status_code=200,
        url="https://www.another_example.com",
        content=b"success",
        headers={"Content-Type": "text/plain"},
    )

    # As long as a response-like object has the required fields as attributes/properties, this should be True:
    assert isinstance(api_response.response, ResponseProtocol) and isinstance(api_response, ResponseProtocol)
    assert not ResponseValidator.identify_invalid_fields(api_response)

    reconstructed_response = ReconstructedResponse.build(
        status_code=200,
        url="https://www.another_example.com",
        content=b"success",
        headers={"Content-Type": "text/plain"},
    )

    api_response_two = APIResponse(response=reconstructed_response)

    assert api_response == api_response_two
    api_response.response.status_code = 201
    assert api_response != api_response_two


def test_success_args_build():
    """Verifies that `ReconstructedResponse.build()` successfully creates response-like objects with dictionaries."""
    args = {
        "status_code": 200,
        "url": "https://example.com",
        "content": b"success",
        "headers": {"Content-Type": "text/plain"},
    }

    response = ReconstructedResponse.build(**args)
    assert response
    assert response.validate() is None  # type: ignore

    # testing a dictionary of inputs
    response_two = ReconstructedResponse.build(args)
    assert response == response_two

    user_dict_args = UserDict(args)  # testing a non-dict mutable mapping
    response_three = ReconstructedResponse.build(user_dict_args)
    assert response_two == response_three


def test_missing_args_build():
    """Verifies that instantiating response-like objects with missing response fields correctly raises an exception."""
    with pytest.raises(InvalidResponseReconstructionException) as excinfo:
        _ = ReconstructedResponse.build()

    assert "Missing the core required fields needed to create a ReconstructedResponse:" in str(excinfo.value)
    assert "'status_code', 'url'" in str(excinfo.value)


@pytest.mark.parametrize(
    ("override",), [({"status_code": 1},), ({"url": "not-an-url"},), ({"content": 12},), ({"headers": "not-a-dict"},)]
)
def test_error_validation(override, caplog):
    """Verifies that `validate()` correctly validates fields and raise an exception when fields are invalid."""
    args = {
        "status_code": 200,
        "url": "https://example.com",
        "content": b"success",
        "headers": {"Content-Type": "text/plain"},
    } | override
    response = ReconstructedResponse.build(**args)

    assert not response.is_response()

    with pytest.raises(InvalidResponseStructureException):
        _ = ResponseValidator.identify_invalid_fields("not a response")  # type: ignore

    with pytest.raises(InvalidResponseReconstructionException):
        response.validate()

    direct_inputs = ("status_code", "url")
    field = next(iter(override.keys()))
    value = override[field]
    text = f"{quote_if_string(field)}: {quote_if_string(value) if field in direct_inputs else type(value)}"

    assert "The following fields contain invalid values:" in caplog.text
    assert text in caplog.text


def test_overrides():
    """Verifies that `ReconstructedResponse.build()` correctly overrides fields based on received keyword arguments."""
    data = {"request_status": "success", "records": 100}

    status_code = 302
    status = responses.get(status_code, "")
    response = ReconstructedResponse(
        status_code=status_code,
        reason=status,
        content=json.dumps(data).encode("utf-8"),
        url="https://example.com",
        headers={"Content-Type": "application/json"},
    )

    assert response.is_response()
    assert response.status == status == "Found"
    assert response.json() == data
    assert response.url == "https://example.com"

    response_build = ReconstructedResponse.build(
        status_code=status_code, json=data, url="https://example.com", headers={"Content-Type": "application/json"}
    )

    response_build_two = ReconstructedResponse.build(
        status_code=status_code,
        status=responses.get(status_code),
        text=json.dumps(data),
        url="https://example.com",
        headers={"Content-Type": "application/json"},
    )

    assert response_build_two.text and response_build_two.text.encode("utf-8") == response_build_two.content
    assert response_build.is_response()
    # the status is inferred from the reason, which is inferred from the status code during ReconstructedResponse.build
    assert (
        response == response_build == response_build_two
        and response.status == response_build.status == response_build_two.status
    )
    assert response_build == response_build_two


def test_json(caplog):
    """Verifies that non-jsonable fields default to `None` on instantiation when invalid."""
    response = ReconstructedResponse.build(text={1, 2, 3}, status_code=200, url="https://example-site.com")
    assert response.json() is None
    assert "The current response object does not contain jsonable content" in caplog.text

    # non-jsonable
    response = ReconstructedResponse.build(text="{[][]}", status_code=200, url="https://example-site.com")
    assert response.json() is None

    assert ("The current ReconstructedResponse object " "does not have a valid json format.") in caplog.text


def test_processed_response_properties():
    """Verifies that the error property of ProcessedResponse returns None as expected when missing an `error`."""
    api_response = ProcessedResponse(
        cache_key="1-2-3-4",
        response=ReconstructedResponse.build(url="https://www.processing-example.com", status_code=200),
    )

    # a property that isn't a mutable attribute
    assert api_response.error is None


def test_serialization(caplog):
    """Verifies that attempting to serialize an invalid response type logs an error and returns None."""
    response = {"url": "https://my-url.com"}

    assert APIResponse.serialize_response(response) is None  # type: ignore
    assert f"Could not encode the value of type {type(response)} into a serialized json object " in caplog.text


def test_error_response_properties():
    """Verifies that all response properties from the `ErrorResponse` class are accessible despite being `None`."""
    api_response = ErrorResponse(
        cache_key="1-2-3-4",
        response=ReconstructedResponse.build(url="https://www.processing-example.com", status_code=401),
        error="InvalidResponseException",
        message="The status code is invalid",
    )

    # properties that aren't mutable attributes
    assert api_response.parsed_response is None
    assert api_response.extracted_records is None
    assert api_response.normalized_records is None
    assert api_response.metadata is None
    assert api_response.data is None
    assert api_response.record_count == len(api_response) == 0  # for error responses, this should always be 0 (no data)


def test_successful_search_result_core_properties(mock_successful_response):
    """Verifies that core ProcessedResponse elements can be extracted from SearchResult instances as properties."""
    success_response = ProcessedResponse.from_response(response=mock_successful_response, cache_key="MOCK_CACHE_KEY")
    response_search_result = SearchResult(
        query="test-query", page=1, provider_name="mock_provider", response_result=success_response
    )
    assert response_search_result.response_result is not None
    assert response_search_result.url and response_search_result.status_code and response_search_result.status
    assert response_search_result.url == response_search_result.response_result.url
    assert response_search_result.status_code == response_search_result.response_result.status_code
    assert response_search_result.status == response_search_result.response_result.status
    assert response_search_result.cached is False


def test_error_search_result_core_properties(mock_unauthorized_response):
    """Verifies that core ErrorResponse elements can be extracted from SearchResult instances as properties."""
    error_response = ErrorResponse.from_response(response=mock_unauthorized_response, cache_key="MOCK_CACHE_KEY")
    err_response_search_result = SearchResult(
        query="test-query", page=1, provider_name="mock_provider", response_result=error_response
    )
    assert err_response_search_result.response_result is not None
    assert (
        err_response_search_result.url and err_response_search_result.status_code and err_response_search_result.status
    )
    assert err_response_search_result.url == err_response_search_result.response_result.url
    assert err_response_search_result.status_code == err_response_search_result.response_result.status_code
    assert err_response_search_result.status == err_response_search_result.response_result.status
    assert err_response_search_result.cached is False


def test_no_response_search_result_core_properties():
    """Verifies that core response elements can be extracted from SearchResult instances as `None` when unavailable."""
    no_response_search_result = SearchResult(
        query="test-query", page=1, provider_name="mock_provider", response_result=None
    )
    assert no_response_search_result.response_result is None
    assert no_response_search_result.url is None
    assert no_response_search_result.status_code is None
    assert no_response_search_result.status is None
    assert no_response_search_result.cached is None


def test_no_op_api_response_annotation_removal_raises_exception():
    """Verifies that attempts to strip annotations with an `APIResponse` class raises a NotImplementedError."""
    err = "Record annotation removal is not implemented for responses of type, APIResponse"
    api_response = APIResponse()

    with pytest.raises(NotImplementedError, match=err):
        _ = api_response.strip_annotations()


def test_successful_search_result_annotation_removal(mock_successful_response):
    """Verifies that SearchResults.strip_annotations() removes private metadata from processed records."""
    record_list = [
        {"title": "A title", "abstract": "An abstract", "_private_annotation": True, "_idx": 0},
        {"title": "Another title", "abstract": "Another abstract", "_private_annotation": True, "_idx": 1},
    ]

    response = ProcessedResponse(
        response=mock_successful_response, extracted_records=record_list, processed_records=record_list
    )
    search_result = SearchResult(response_result=response, query="query", page=1, provider_name="unknown")

    stripped_records = search_result.strip_annotations()
    assert all("_private_annotation" not in record and "_idx" not in record for record in stripped_records)

    # User-provided record lists should be stripped when available
    assert stripped_records == search_result.strip_annotations(record_list)

    # For error/non-responses, A non-empty, stripped record list should only be returned if a record list is provided
    unsuccessful_search_result = SearchResult(
        response_result=NonResponse(), query="query", page=1, provider_name="unknown"
    )
    assert unsuccessful_search_result.strip_annotations(record_list) == stripped_records

    # Records are coerced into lists of records when available
    assert stripped_records[-1:] == search_result.strip_annotations(record_list[-1])


def test_empty_search_result_result_strip_annotations(mock_successful_response):
    """Verifies that `SearchResult.strip_annotations()` returns an empty list when `processed_records` is None."""
    successful_search_result = SearchResult(
        response_result=ProcessedResponse(response=mock_successful_response),
        query="query",
        page=1,
        provider_name="unknown",
    )
    no_search_result = SearchResult(response_result=None, query="query", page=1, provider_name="unknown")
    assert successful_search_result.strip_annotations() == no_search_result.strip_annotations() == []


def test_unsuccessful_search_result_result_strip_annotations(mock_unauthorized_response, caplog):
    """Verifies that `SearchResult.strip_annotations()` with ErrorResponse/NonResponse classes returns an empty list."""
    nonresponse_search_result = SearchResult(
        response_result=NonResponse(), query="query", page=1, provider_name="unknown"
    )

    unauthorized_search_result = SearchResult(
        response_result=ErrorResponse(response=mock_unauthorized_response),
        query="query",
        page=1,
        provider_name="unknown",
    )
    assert unauthorized_search_result.strip_annotations() == []
    assert nonresponse_search_result.strip_annotations() == []

    err_response_warning = (
        "Record Annotation removal for `processed_records` is not implemented for responses of type, "
        "{response}: There are no records to strip annotations from. Returning an empty list..."
    )
    assert err_response_warning.format(response=ErrorResponse.__name__) in caplog.text
    assert err_response_warning.format(response=NonResponse.__name__) in caplog.text


def test_search_result_equality():
    """Verifies that comparisons of a SearchResult with other results and objects are type aware value comparisons."""
    error_response = ErrorResponse()
    nonresponse_search_result = SearchResult(
        query="test-query", page=1, provider_name="mock_provider", response_result=error_response
    )
    nonresponse_search_result2 = deepcopy(nonresponse_search_result)
    assert nonresponse_search_result == nonresponse_search_result2
    nonresponse_search_result2.page = 2
    assert nonresponse_search_result != nonresponse_search_result2
    assert nonresponse_search_result != "an incorrect class comparison"
