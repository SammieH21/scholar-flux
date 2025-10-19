import pytest
from scholar_flux.api import RateLimiter, ThreadedRateLimiter
import time

from unittest.mock import patch
from scholar_flux.exceptions import APIParameterException


@pytest.fixture
def set_default_rate_limiter_interval():
    """This fixture is used to verify that the RateLimiter uses the DEFAULT_MIN_INTERVAL when otherwise not specified.

    The default value is reset after the current test that uses
    this dependency concludes.
    """
    default_min_interval = RateLimiter.DEFAULT_MIN_INTERVAL
    RateLimiter.DEFAULT_MIN_INTERVAL = 999
    yield
    RateLimiter.DEFAULT_MIN_INTERVAL = default_min_interval


def test_default_initialization(set_default_rate_limiter_interval):
    """Tests if the RateLimiter is populated with the DEFAULT_MIN_INTERVAL when instantiated without input."""
    limiter = RateLimiter()
    assert limiter.min_interval == RateLimiter.DEFAULT_MIN_INTERVAL == 999


@pytest.mark.parametrize(("min_interval"), (0, 1.5, 2))
def test_custom_initialization(min_interval):
    """Verifies that the assignment of a min-interval is valid for non-negative integers/floats."""
    assert RateLimiter._validate(min_interval) == min_interval


def test_validate_invalid_type():
    """Verifies that the use of strings raises an error upon assignment."""
    with pytest.raises(APIParameterException):
        RateLimiter._validate("bad")  # type:ignore


def test_validate_negative():
    """Verifies that an error is thrown when min_interval is assigned a negative number."""
    with pytest.raises(APIParameterException):
        RateLimiter._validate(-1)


@pytest.mark.parametrize("Limiter", (RateLimiter, ThreadedRateLimiter))
def test_wait_sleeps_when_needed_real_time(Limiter):
    """Tests the sleep function of the rate limiter to verify that the `wait` method executes successfully for the
    specified interval.

    This function patches time.sleep to verify that the sleep argument
    is called with the intended arguments while recording the time when
    sleep was last performed.
    """
    limiter = Limiter(0.05)
    limiter._last_call = time.time()
    # Simulate a call before min_interval has passed
    with patch("scholar_flux.api.rate_limiting.rate_limiter.time.sleep") as mock_sleep:
        limiter.wait()
        # Should sleep for close to min_interval
        mock_sleep.assert_called()
        sleep_arg = mock_sleep.call_args[0][0]
        assert sleep_arg > 0


@pytest.mark.parametrize("Limiter", (RateLimiter, ThreadedRateLimiter))
def test_wait_no_sleep_if_enough_time_real_time(Limiter):
    """Verifies that the sleep function will not wait if enough time has passed between the last call of the `wait()`
    method."""
    limiter = Limiter(0.01)
    limiter._last_call = time.time() - 0.02  # Enough time has passed
    with patch("scholar_flux.api.rate_limiting.rate_limiter.time.sleep") as mock_sleep:
        limiter.wait()
        mock_sleep.assert_not_called()


def test_decorator_respects_rate_limit():
    """Tests the `wait()` method to ensure that, when setting `min_interval` to 0, the `sleep` function is never called.

    A helper function (`fn`) is defined and decorated so that subsequent calls are both rate limited and recorded

    After patching sleep to record the call count, the test verifies that sleep never triggers due to `min_interval=0`.
    """

    limiter = RateLimiter(0)
    called = []

    @limiter
    def fn(x):
        called.append(x)
        return x

    with patch("scholar_flux.api.rate_limiting.rate_limiter.time.sleep") as mock_sleep:
        fn(1)
        fn(2)
        assert called == [1, 2]
        assert mock_sleep.call_count == 0  # min_interval=0, no sleep


@patch("scholar_flux.api.rate_limiting.rate_limiter.RateLimiter._wait")
def test_context_manager_calls_wait(mock_sleep):
    """Tests the total number of times that the `_wait` helper method is called when the rate limiter's min_interval
    parameter is set to a value of 1.

    Patches the  `_wait` method to record the number of calls to the
    sleep function.
    """
    limiter = RateLimiter(1)
    mock_sleep.side_effect = ["method called 0 times", "called 1 time"]
    limiter._last_call = 99.0
    with limiter:
        pass
    mock_sleep.assert_called_once()


@patch("scholar_flux.api.rate_limiting.rate_limiter.RateLimiter.wait")
def test_rate_context_manager_temporary_interval(mock_time):
    """Tests that the temporary modification of the min_interval attribute with a context manager will not affect the
    parameter value of the original rate limiter outside of the context manager."""
    limiter = RateLimiter(5)
    mock_time.side_effect = ["method called 0 times", "called 1 time"]
    orig_interval = limiter.min_interval
    with limiter.rate(2):
        assert limiter.min_interval == orig_interval  # min_interval is not changed permanently
    assert limiter.min_interval == orig_interval
