import pytest
from scholar_flux.api import RateLimiter
import time

from unittest.mock import patch
from scholar_flux.exceptions import APIParameterException

def test_default_initialization():
    limiter = RateLimiter()
    assert limiter.min_interval == RateLimiter.DEFAULT_MIN_INTERVAL

def test_custom_initialization():
    limiter = RateLimiter(2.5)
    assert limiter.min_interval == 2.5

def test_validate_valid():
    assert RateLimiter._validate(0) == 0
    assert RateLimiter._validate(1.5) == 1.5

def test_validate_invalid_type():
    with pytest.raises(APIParameterException):
        RateLimiter._validate("bad") #type:ignore

def test_validate_negative():
    with pytest.raises(APIParameterException):
        RateLimiter._validate(-1)

def test_wait_sleeps_when_needed_real_time():
    limiter = RateLimiter(0.05)
    limiter._last_call = time.time()
    # Simulate a call before min_interval has passed
    with patch("scholar_flux.api.rate_limiter.time.sleep") as mock_sleep:
        limiter.wait()
        # Should sleep for close to min_interval
        mock_sleep.assert_called()
        sleep_arg = mock_sleep.call_args[0][0]
        assert sleep_arg > 0

def test_wait_no_sleep_if_enough_time_real_time():
    limiter = RateLimiter(0.01)
    limiter._last_call = time.time() - 0.02  # Enough time has passed
    with patch("scholar_flux.api.rate_limiter.time.sleep") as mock_sleep:
        limiter.wait()
        mock_sleep.assert_not_called()

def test_decorator_respects_rate_limit():
    limiter = RateLimiter(0)
    called = []

    @limiter
    def fn(x):
        called.append(x)
        return x

    with patch("scholar_flux.api.rate_limiter.time.sleep") as mock_sleep:
        fn(1)
        fn(2)
        assert called == [1, 2]
        assert mock_sleep.call_count == 0  # min_interval=0, no sleep

@patch("scholar_flux.api.rate_limiter.RateLimiter.wait")
@patch("scholar_flux.api.rate_limiter.RateLimiter._wait")
def test_context_manager_calls_wait(mock_time, mock_sleep):
    limiter = RateLimiter(1)
    mock_time.side_effect = [100., 101.]
    limiter._last_call = 99.
    with limiter:
        pass
    mock_sleep.assert_called_once()

@patch("scholar_flux.api.rate_limiter.RateLimiter.wait")
@patch("scholar_flux.api.rate_limiter.RateLimiter._wait")
def test_rate_context_manager_temporary_interval(mock_time, mock_sleep):
    limiter = RateLimiter(5)
    mock_time.side_effect = [100., 101.]
    limiter._last_call = 99.
    orig_interval = limiter.min_interval
    with limiter.rate(2):
        assert limiter.min_interval == orig_interval  # min_interval is not changed permanently
    assert limiter.min_interval == orig_interval


if __name__ == '__main__':
    limiter = RateLimiter(2)
    limiter.wait()
    with limiter.rate(2):
        print(1)
    
