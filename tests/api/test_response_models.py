from scholar_flux.api.models import ErrorResponse, ProcessedResponse, APIResponse, ReconstructedResponse
from scholar_flux.exceptions import InvalidResponseReconstructionException, InvalidResponseStructureException
from collections import UserDict
from scholar_flux.utils import quote_if_string, ResponseProtocol
from scholar_flux.utils.helpers import generate_iso_timestamp, parse_iso_timestamp
from requests import Response, RequestException
from http.client import responses
from unittest.mock import patch
from datetime import datetime
import json
import pytest
import re


class DummyResponse(Response):
    """Helper class for testing how `status_code functions for requests.Response subclassess"""
    def __init__(*args, **kwargs):
        pass

    @property
    def status_code(self) -> int:  # type: ignore
        """Used to automatically raise a ValueError for later testing with the ReconstructedResponse class"""
        raise ValueError


@patch("scholar_flux.utils.helpers.try_int")
def test_response_creation(mock_try_int, mock_successful_response):
    """Tests whether the property accounts for issues such as raised value errors when retrieving status codes"""
    api_response = APIResponse(cache_key="key", response=DummyResponse())
    code = api_response.status_code
    assert code is None


def test_blank_initialization():
    """
    Verifies that initializing a reconstructed response is possible when explicitly setting `url` and `status_code`
    to None.
    """
    response = ReconstructedResponse.build(url=None, status_code=None)

    assert response
    assert response.reason is None and response.status_code is None and response.headers == {} and response.url is None
    assert not response.is_response()

    api_response = APIResponse.from_response(url=None, status_code=None, created_at=None)
    assert api_response.response == response
    assert api_response.url is None
    assert api_response.status_code is None
    assert api_response.created_at is None


def test_error_response(mock_unauthorized_response):
    """Verifies the representation of the ErrorResponse as defined by its original parent class __repr__"""
    error_response = ErrorResponse(cache_key="key", response=mock_unauthorized_response)
    assert (
        repr(error_response) == f"<ErrorResponse(status_code={error_response.status_code}, error=None, message=None)>"
    )
    assert not error_response


def test_success_response():
    """Tests if the processed reecords and data fields are populated as intended for a ProcessedResponse"""
    response_dict: list[dict] = [{1: 1}, {2: 2}, {3: 3}, {4: 4}]
    processed_response = ProcessedResponse(processed_records=response_dict)
    assert processed_response and processed_response.data
    assert len(processed_response) == 4 == len(processed_response.data) == len(processed_response.processed_records or [])


def test_api_response_from_response(mock_successful_response):
    """Verifies elements of the APIResponse parent clsas such as status code, status, cache_key, etc"""
    api_response = APIResponse.from_response(response=mock_successful_response, cache_key="foo")
    assert api_response.status_code == 200
    assert api_response.cache_key == "foo"
    assert api_response.status == "OK"
    assert api_response.headers is not None


def test_api_response_from_kwargs():
    """
    Verifies that header, content, and other relevant fields are populated as intended when constructed manually
    """
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
    """
    Tests idempotence and the reliability of serializing and deserializing responses using ReconstructedResponses
    and the most important fields derived from response classes.
    """
    api_response = APIResponse.from_response(response=mock_successful_response, cache_key="foo", auto_created_at=True)
    dumped = api_response.model_dump_json()
    loaded = APIResponse.model_validate_json(dumped)
    assert loaded.status_code == 200
    assert loaded.cache_key == "foo"
    assert loaded.status == "OK"

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


def test_deserializing_response(monkeypatch, caplog):
    """Verifies whether desrialization occurs as intended when encountering errors in the desrialization process"""
    response = APIResponse.from_response(status_code=200, content=b"success", url="https://examples.com")

    exc = "Directly raised exception"
    monkeypatch.setattr(
        APIResponse, "from_serialized_response", lambda *args, **kwargs: (_ for _ in ()).throw(TypeError(exc))
    )

    response_dict = response.model_dump()

    deserialized_response = response.transform_response(response_dict)
    assert deserialized_response is deserialized_response  # cant serialize/process the response so returns as is
    assert f"Couldn't decode a valid response object: {exc}" in caplog.text
    assert "Couldn't decode a valid response object. Returning the object as is" in caplog.text

    # desrialization for invalid values should return None
    assert APIResponse._deserialize_response_dict([]) is None  # type: ignore
    assert (
        "Could not decode the response argument from a string to JSON object: the JSON object "
        "must be str, bytes or bytearray, not list"
    ) in caplog.text


def test_reconstructed_response_json():
    """Tests whether reconstructed responses from JSON objects can be parsed as intended using the `json()` method"""
    rr = ReconstructedResponse(
        status_code=200,
        reason="OK",
        headers={"Content-Type": "application/json"},
        content=b"[1,2,3]",
        url="https://api.example.com/test",
    )
    assert rr.json() == [1, 2, 3]


def test_reconstructed_response_equality():
    """
    Verifies that reconstructed response objects only factor in data types and values instead of memory bytes
    when determining whether two instances are equal.
    """
    rr1 = ReconstructedResponse(status_code=200, reason="OK", headers={}, content=b"abc", url="u")
    rr2 = ReconstructedResponse(status_code=200, reason="OK", headers={}, content=b"abc", url="u")
    assert rr1 == rr2


def test_validate_api_response(mock_successful_response):
    api_response = APIResponse.from_response(response=mock_successful_response)
    assert api_response.validate_response()


def test_api_response_validate_response_like():
    api_response = APIResponse.from_response(status_code=200, headers={}, content=b"", text="", url="u")
    assert not api_response.validate_response()


def test_api_response_as_json_with_invalid_json():
    api_response = APIResponse.from_response(status_code=200, headers={}, content=b"notjson", text="notjson", url="u")
    assert api_response.response is not None and api_response.response.json() is None


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
    api_response = APIResponse(cache_key=None, response=UserDict())
    # a user dict isn't a response-like object, so it is not serialized
    json_data = api_response.model_dump_json()
    assert json.loads(json_data)["response"] is None


def test_representation():
    response = APIResponse.from_response(
        cache_key="test-key",
        status_code=200,
        url="https://another-example.com",
    )
    representation = repr(response)

    assert re.search(r"APIResponse\(cache_key='test-key',(\n| )*response=ReconstructedResponse\(.*\)\)", representation)


def test_api_response_timestamp_validation(caplog):

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
    assert f"Expected an iso8601-formatted datetime, Received type ({type(True)})" in caplog.text


def test_raise_for_status():
    valid_response = ReconstructedResponse.build(
        status_code=200, url="https://example.com", content=b"content", headers={"Content-Type": "text/plain"}
    )

    # direct comparison with a reconstructed response
    api_response = APIResponse(response=valid_response)
    assert valid_response.ok
    assert api_response.raise_for_status() is None

    # ensuring that, as a dictionary, when reconstructed into a response, no error:
    api_response.response = valid_response.asdict()
    assert api_response.raise_for_status() is None

    # changing it back for future dumping and direct checking against the response
    api_response.response = valid_response

    api_response_two = APIResponse(response=api_response.model_dump().get("response"))

    api_response_two.raise_for_status()  # Should not raise an exception

    invalid_response = ReconstructedResponse.build(
        status_code=500, url="https://example.com", content=b"error", headers={"Content-Type": "text/plain"}
    )

    assert not invalid_response.ok
    invalid_api_response = APIResponse(response=invalid_response)

    with pytest.raises(RequestException) as excinfo:
        _ = invalid_api_response.raise_for_status()
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
        _ = invalid_api_response_two.raise_for_status()
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
    api_response = APIResponse.from_response(
        status_code=200,
        reason=True,
        url="https://www.another_example.com",
        content="not bytes",
        headers={"Content-Type": "text/plain"},
    )
    assert api_response.response is not None

    assert api_response.reason is None  # a boolean reason is not a valid value
    assert api_response.content == b"not bytes"
    assert api_response.text == "not bytes"
    api_response.response.content = False
    assert api_response.content is None
    assert api_response.text is None

    api_response.response.content = "also not bytes"
    assert api_response.content == b"also not bytes"
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
    api_response = APIResponse()
    assert api_response.url is None
    assert api_response.reason is None
    assert api_response.status_code is None
    assert api_response.status is None
    assert api_response.content is None
    assert api_response.text is None


def test_reconstruction():
    api_response = APIResponse.from_response(
        status_code=200,
        url="https://www.another_example.com",
        content=b"success",
        headers={"Content-Type": "text/plain"},
    )

    assert isinstance(api_response, ResponseProtocol)
    assert not ReconstructedResponse._identify_invalid_fields(api_response)

    reconstructed_response = ReconstructedResponse.build(
        status_code=200,
        url="https://www.another_example.com",
        content=b"success",
        headers={"Content-Type": "text/plain"},
    )

    api_response_two = APIResponse(response=reconstructed_response)

    assert api_response == api_response_two
    api_response.response.status_code = 201  # type: ignore
    assert api_response != api_response_two


def test_success_args_build():
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
    with pytest.raises(InvalidResponseReconstructionException) as excinfo:
        _ = ReconstructedResponse.build()

    assert "Missing the core required fields needed to create a ReconstructedResponse:" in str(excinfo.value)
    assert "'status_code' and 'url'" in str(excinfo.value)


@pytest.mark.parametrize(
    ("override",), [({"status_code": 1},), ({"url": "not-an-url"},), ({"content": 12},), ({"headers": "not-a-dict"},)]
)
def test_error_validation(override, caplog):
    args = {
        "status_code": 200,
        "url": "https://example.com",
        "content": b"success",
        "headers": {"Content-Type": "text/plain"},
    } | override
    response = ReconstructedResponse.build(**args)

    assert not response.is_response()

    with pytest.raises(InvalidResponseStructureException):
        _ = ReconstructedResponse._identify_invalid_fields("not a response")  # type: ignore

    with pytest.raises(InvalidResponseReconstructionException):
        response.validate()

    direct_inputs = ("status_code", "url")
    field = list(override.keys())[0]
    value = override[field]
    text = f"{quote_if_string(field)}: {quote_if_string(value) if field in direct_inputs else type(value)}"
    # invalid_fields = {field:value if field in ('status_code', 'url') else type(value) for field, value in override.items()}

    assert "The following fields contain invalid values:" in caplog.text
    assert text in caplog.text


def test_overrides():
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
    response = ReconstructedResponse.build(text={1, 2, 3}, status_code=200, url="https://example-site.com")
    assert response.json() is None
    assert "The current response object does not contain jsonable content" in caplog.text

    # non-jsonable
    response = ReconstructedResponse.build(text="{{]", status_code=200, url="https://example-site.com")
    assert response.json() is None

    assert ("The current ReconstructedResponse object " "does not have a valid json format.") in caplog.text


def test_next_api_response():
    assert 1 == 1


def test_processed_response_properties():
    api_response = ProcessedResponse(
        cache_key="1-2-3-4",
        response=ReconstructedResponse.build(url="https://wwww.processing-example.com", status_code=200),
    )

    # a property that isn't a mutable attribute
    assert api_response.error is None


def test_serialization(caplog):
    response = {"url": "https://my-url.com"}

    assert APIResponse.serialize_response(response) is None  # type: ignore
    assert f"Could not encode the value of type {type(response)} into a serialized json object " in caplog.text


def test_error_response_properties():
    api_response = ErrorResponse(
        cache_key="1-2-3-4",
        response=ReconstructedResponse.build(url="https://wwww.processing-example.com", status_code=401),
        error="InvalidResponseException",
        message="The status code is invalid",
    )

    # a properties that aren't mutable attributes
    assert api_response.parsed_response is None
    assert api_response.extracted_records is None
    assert api_response.metadata is None
    assert api_response.data is None
    assert len(api_response) == 0  # for error responses, this should always be 0 (no data)
