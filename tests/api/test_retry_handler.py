import pytest
import json
import datetime
from textwrap import dedent
from unittest.mock import patch
from requests import Response
from scholar_flux.api import RetryHandler
from scholar_flux.exceptions import RequestFailedException, InvalidResponseException


def response_factory(
    status_code=200,
    headers=None,
    json_data=None,
    text=None,
):
    """Helper function for creating mock response objects using a requests.Response object."""
    response = Response()
    response.status_code = status_code
    response.headers.update(headers or {})
    if json_data is not None:
        response._content = json.dumps(json_data).encode("utf-8")
        response.headers["Content-Type"] = "application/json"
    elif text is not None:
        response._content = text.encode("utf-8")
    else:
        response._content = b""
    response.encoding = "utf-8"
    return response


def test_execute_with_retry_valid_first_try():
    """Tests and ensures that responses with 200 status codes are returned as valid responses."""
    handler = RetryHandler()
    response = response_factory(200)
    request_func = lambda: response
    result = handler.execute_with_retry(request_func)
    assert isinstance(result, Response) and result.status_code == 200


def test_execute_with_retry_retry_then_success():
    """Tests whether the retry handler continues to retrieve from the response list until the 200 status code is
    encountered."""
    handler = RetryHandler()
    responses = [response_factory(503), response_factory(200)]
    request_func = lambda: responses.pop(0)
    with patch("time.sleep"):
        result = handler.execute_with_retry(request_func)
    assert isinstance(result, Response) and result.status_code == 200


def test_execute_with_retry_max_retries_exceeded():
    """Tests whether the response is returned as is at `max_retries=503`"""
    handler = RetryHandler(max_retries=1)
    response = response_factory(503)
    request_func = lambda: response
    with patch("time.sleep"):
        result = handler.execute_with_retry(request_func)
    assert isinstance(result, Response) and result.status_code == 503


def test_execute_with_retry_max_retries_and_raise(caplog):
    """Verifies that an InvalidResponseException is raised when `raise_on_error` is set to True."""
    handler = RetryHandler(max_retries=3, raise_on_error=True)
    status_code = 503
    response = response_factory(status_code)
    request_func = lambda: response
    with pytest.raises(InvalidResponseException), patch("time.sleep"):
        _ = handler.execute_with_retry(request_func)
    assert f"HTTP error occurred: {response} - Status code: {status_code}." in caplog.text


def test_execute_with_retry_non_retryable_status(caplog):
    """Tests whether an error is raised with the response message when `raise_on_error` is set to True.

    Also verifies that the response is returned as is when `raise_on_error` is False

    """
    handler = RetryHandler(raise_on_error=True)
    message = "Cannot process the current request with your credentials"
    status_code = 400
    response = response_factory(status_code, json_data={"error": {"message": message}})
    request_func = lambda: response
    with pytest.raises(InvalidResponseException):
        _ = handler.execute_with_retry(request_func)

    assert f"HTTP error occurred: {response} - Status code: {status_code}. Details: {message}" in caplog.text

    handler = RetryHandler(raise_on_error=False)
    response = handler.execute_with_retry(request_func)
    assert isinstance(response, Response)
    assert f"Returning a request of type {type(response)}, status_code={status_code}" in caplog.text


def test_invalid_response_exception_non_json(caplog):
    """Tests and verifies that the InvalidResponseException is retrieves the error details as intended when
    available."""
    from scholar_flux.exceptions import InvalidResponseException

    response = response_factory(400, text="Not JSON")
    exc = InvalidResponseException(response)
    assert exc.error_details == ""

    response = response_factory(400, json_data=["Even moreso not a json"])
    exc = InvalidResponseException(response)
    assert exc.error_details == ""

    response = response_factory(400, json_data={"error": [1, 2, 3]})
    exc = InvalidResponseException(response)
    assert exc.error_details == ""

    with pytest.raises(InvalidResponseException):
        raise InvalidResponseException(None)  # type: ignore
    assert f"An error occurred when making the request - Received a nonresponse: {type(None)}" in caplog.text


def test_calculate_retry_delay_with_invalid_retry_after(caplog):
    """Validates the calculation of the retry delay when a `retry_after` value is available.

    Also verifies whether the backoff is calculated as intended when `retry_after` is not available.

    """
    handler = RetryHandler(backoff_factor=2, max_backoff=10)
    retry_after = "not-a-date"
    response = response_factory(503, headers={"Retry-After": retry_after})
    delay = handler.calculate_retry_delay(1, response)
    # Should fallback to exponential backoff
    assert delay == 4  # 2 * 2^1
    assert f"'Retry-After' is not a valid number: {retry_after}. Attempting to parse as a date.." in caplog.text
    assert "Couldn't parse 'Retry-After' as a date:" in caplog.text
    assert "Defaulting to using 'max_backoff'..." in caplog.text


def test_nonresponse():
    """Verifies that an error is raised when a non-response is encountered."""
    handler = RetryHandler()
    value = "a nonresponse"
    with pytest.raises(RequestFailedException):
        handler.execute_with_retry(value)  # type:ignore


def test_repr():
    """Verifies that the representation of the RetryHandler appears as intended when printed in the CLI."""
    handler = RetryHandler()
    assert repr(handler) == dedent(
        f"RetryHandler(max_retries={handler.max_retries},\n"
        f"             backoff_factor={handler.backoff_factor},\n"
        f"             max_backoff={handler.max_backoff},\n"
        f"             retry_statuses={handler.retry_statuses},\n"
        f"             raise_on_error={handler.raise_on_error})"
    )


def test_execute_with_retry_exception():
    """Verifies that, when an exception is encountered when requesting a response with a custom function, the exception
    is caught and instead raises a RequestFailedException."""
    handler = RetryHandler()

    def request_func():
        raise Exception("fail")

    with pytest.raises(RequestFailedException):
        handler.execute_with_retry(request_func)


def test_execute_with_retry_custom_validator(caplog):
    """Tests the retry handler to determine if it successfully uses the `validator_func` for custom data validation."""
    handler = RetryHandler(raise_on_error=True)
    response = response_factory(201)
    request_func = lambda: response
    validator_func = lambda r: r.status_code == 201
    with patch("time.sleep"):
        result = handler.execute_with_retry(request_func, validator_func)
    assert isinstance(result, Response) and result.status_code == 201
    assert "Received an invalid or non-retryable response." not in caplog.text


def test_default_validator_func():
    """Validates and verifies that the default validator successfully marks 200 status codes as valid and marks non-200
    responses as  invalid status codes."""
    response = response_factory(200)
    assert RetryHandler._default_validator_func(response)
    resp2 = response_factory(404)
    assert not RetryHandler._default_validator_func(resp2)
    assert not RetryHandler._default_validator_func("not a response")  # type:ignore


def test_should_retry():
    """Verifies that the `should_retry` function successfully marks specific status codes as retryable."""
    handler = RetryHandler()
    response = response_factory(429)
    assert handler.should_retry(response)
    resp2 = response_factory(400)
    assert not handler.should_retry(resp2)


def test_calculate_retry_delay_no_retry_after():
    """Verifies the calculation of the retry delay given the backoff_factor and default retry delay.

    given the calculation: delay = min(backoff_factor * 2^attempt_count, max_backoff).

    """
    handler = RetryHandler(backoff_factor=1, max_backoff=10)
    response = response_factory(503)
    delay = handler.calculate_retry_delay(2, response)
    assert delay == 4


def test_calculate_retry_delay_with_retry_after_int():
    """Verifies that the `calculate_retry_delay`, when possible, extracts and uses the integer `retry-after` field."""
    handler = RetryHandler()
    response = response_factory(503, headers={"Retry-After": "5"})
    assert handler.calculate_retry_delay(1, response) == 5


def test_calculate_retry_delay_with_retry_after_date():
    """Verifies that the `calculate_retry_delay`, when possible, extracts and uses date from the `retry-after` field."""
    handler = RetryHandler()
    future = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=10)
    date_str = future.strftime("%a, %d %b %Y %H:%M:%S GMT")
    response = response_factory(503, headers={"Retry-After": date_str})
    delay = handler.calculate_retry_delay(1, response)
    assert 0 <= delay <= 10


def test_parse_retry_after_int():
    """Verifies that simple integer parsing works as intended."""
    assert RetryHandler.parse_retry_after("7") == 7


def test_parse_retry_after_None():
    """Verifies that simple integer parsing works as intended."""
    assert RetryHandler.parse_retry_after(None) is None


def test_parse_retry_after_date():
    """Verifies that date parsing works as intended upon receiving a datetime GMT string."""
    future = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=15)
    date_str = future.strftime("%a, %d %b %Y %H:%M:%S GMT")
    delay = RetryHandler.parse_retry_after(date_str)
    assert delay is not None
    assert 0 <= delay <= 15


@pytest.mark.parametrize("retry_header", ("retry-after", "Retry-After", "x-ratelimit-retry-after"))
def test_get_retry_after_date(retry_header):
    """Verifies that timezone-aware response headers can be retrieved and parsed as intended with case-insensitivity."""
    future = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=15, hours=-5)
    date_str = future.strftime("%a, %d %b %Y %H:%M:%S -0500")

    response = response_factory(headers={retry_header: date_str})

    delay = RetryHandler.get_retry_after(response)
    assert delay is not None
    assert 0 <= delay <= 15


def test_get_retry_after_invalid_parameter():
    """Verifies that timezone-aware response headers can be retrieved and parsed as intended with case-insensitivity."""
    invalid_str = "invalid date parameter"
    response = response_factory(headers={"retry-after": invalid_str})

    delay = RetryHandler.get_retry_after(response)
    assert delay is None

    nonresponse = "non-response class"

    delay = RetryHandler.get_retry_after(nonresponse)  # type: ignore
    assert delay is None


def test_log_retry_attempt_and_warning(caplog):
    """Verifies that logging works as intended when encountering non-200 status codes."""
    handler = RetryHandler()
    with caplog.at_level("INFO"):
        handler.log_retry_attempt(2, 503)
        assert "Retrying in 2 seconds" in caplog.text
        assert "due to status 503" in caplog.text
    with caplog.at_level("WARNING"):
        handler.log_retry_warning("warn!")
        assert "warn!" in caplog.text
