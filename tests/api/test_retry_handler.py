import pytest
import json
import datetime
from textwrap import dedent
from unittest.mock import patch
from requests import Response
from scholar_flux.api.retry_handler import RetryHandler
from scholar_flux.exceptions import RequestFailedException, InvalidResponseException


def response_factory(
    status_code=200,
    headers=None,
    json_data=None,
    text=None,
):
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
    handler = RetryHandler()
    response = response_factory(200)
    request_func = lambda: response
    result = handler.execute_with_retry(request_func)
    assert isinstance(result, Response) and result.status_code == 200


def test_execute_with_retry_retry_then_success():
    handler = RetryHandler()
    responses = [response_factory(503), response_factory(200)]
    request_func = lambda: responses.pop(0)
    with patch("time.sleep"):
        result = handler.execute_with_retry(request_func)
    assert isinstance(result, Response) and result.status_code == 200


def test_execute_with_retry_max_retries_exceeded():
    handler = RetryHandler(max_retries=1)
    response = response_factory(503)
    request_func = lambda: response
    with patch("time.sleep"):
        result = handler.execute_with_retry(request_func)
    assert isinstance(result, Response) and result.status_code == 503


def test_execute_with_retry_max_retries_and_raise(caplog):
    handler = RetryHandler(max_retries=3, raise_on_error=True)
    status_code = 503
    response = response_factory(status_code)
    request_func = lambda: response
    with pytest.raises(InvalidResponseException), patch("time.sleep"):
        _ = handler.execute_with_retry(request_func)
    assert f"HTTP error occurred: {response} - Status code: {status_code}." in caplog.text


def test_execute_with_retry_non_retryable_status(caplog):
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
    handler = RetryHandler(backoff_factor=2, max_backoff=10)
    retry_after = "not-a-date"
    response = response_factory(503, headers={"Retry-After": retry_after})
    delay = handler.calculate_retry_delay(1, response)
    # Should fallback to exponential backoff
    assert delay == 4  # 2 * 2^1
    assert f"'Retry-After' is not a valid number: {retry_after}. Attempting to parse as a date.." in caplog.text
    assert "Couldn't parse 'Retry-After' as a date." in caplog.text
    assert "Defaulting to using 'max_backoff'..." in caplog.text


def test_nonresponse():
    handler = RetryHandler()
    value = "a nonresponse"
    with pytest.raises(RequestFailedException):
        handler.execute_with_retry(value)  # type:ignore


def test_repr():
    handler = RetryHandler()
    assert repr(handler) == dedent(
        f"RetryHandler(max_retries={handler.max_retries},\n"
        f"             backoff_factor={handler.backoff_factor},\n"
        f"             max_backoff={handler.max_backoff},\n"
        f"             retry_statuses={handler.retry_statuses},\n"
        f"             raise_on_error={handler.raise_on_error})"
    )


def test_execute_with_retry_exception():
    handler = RetryHandler()

    def request_func():
        raise Exception("fail")

    with pytest.raises(RequestFailedException):
        handler.execute_with_retry(request_func)


def test_execute_with_retry_custom_validator():
    handler = RetryHandler()
    response = response_factory(201)
    request_func = lambda: response
    validator_func = lambda r: r.status_code == 201
    with patch("time.sleep"):
        result = handler.execute_with_retry(request_func, validator_func)
    assert isinstance(result, Response) and result.status_code == 201


def test_default_validator_func():
    response = response_factory(200)
    assert RetryHandler._default_validator_func(response)
    resp2 = response_factory(404)
    assert not RetryHandler._default_validator_func(resp2)
    assert not RetryHandler._default_validator_func("not a response")  # type:ignore


def test_should_retry():
    handler = RetryHandler()
    response = response_factory(429)
    assert handler.should_retry(response)
    resp2 = response_factory(400)
    assert not handler.should_retry(resp2)


def test_calculate_retry_delay_no_retry_after():
    handler = RetryHandler(backoff_factor=1, max_backoff=10)
    response = response_factory(503)
    delay = handler.calculate_retry_delay(2, response)
    assert delay == 4


def test_calculate_retry_delay_with_retry_after_int():
    handler = RetryHandler()
    response = response_factory(503, headers={"Retry-After": "5"})
    assert handler.calculate_retry_delay(1, response) == 5


def test_calculate_retry_delay_with_retry_after_date():
    handler = RetryHandler()
    future = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=10)
    date_str = future.strftime("%a, %d %b %Y %H:%M:%S GMT")
    response = response_factory(503, headers={"Retry-After": date_str})
    delay = handler.calculate_retry_delay(1, response)
    assert 0 <= delay <= 10


def test_parse_retry_after_int():
    handler = RetryHandler()
    assert handler.parse_retry_after("7") == 7


def test_parse_retry_after_date():
    handler = RetryHandler()
    future = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=15)
    date_str = future.strftime("%a, %d %b %Y %H:%M:%S GMT")
    delay = handler.parse_retry_after(date_str)
    assert delay is not None
    assert 0 <= delay <= 15


def test_log_retry_attempt_and_warning(caplog):
    handler = RetryHandler()
    with caplog.at_level("INFO"):
        handler.log_retry_attempt(2, 503)
        assert "Retrying in 2 seconds" in caplog.text
        assert "due to status 503" in caplog.text
    with caplog.at_level("WARNING"):
        handler.log_retry_warning("warn!")
        assert "warn!" in caplog.text
