# /api/rate_limiting/rate_limiter.py
"""The scholar_flux.api.rate_limiting.rate_limiter module implements a simple, general RateLimiter that scholar_flux
uses to ensure that rate limits to a provider are not exceeded within the specified constant time interval."""
from __future__ import annotations
from contextlib import contextmanager
from typing_extensions import Self
import time
from functools import wraps
from scholar_flux.exceptions import APIParameterException
from typing import Optional, Iterator
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """A basic rate limiter used to ensure that future API requests don't exceed the provider-specific limits on the
    total number of requests that can be made within a defined time interval.

    This class ensures that calls to `RateLimiter.wait()` (or any decorated function) are spaced
    by at least `min_interval` seconds.

    # Examples

    >>> import requests
    >>> from scholar_flux.api import RateLimiter
    >>> rate_limiter = RateLimiter(min_interval = 5)
    # the first call won't sleep, because a prior call using the rate limiter doesn't yet exist
    >>> with rate_limiter:
    >>>     response = requests.get("http://httpbin.org/get")
    # will sleep if 5 seconds since the last call hasn't elapsed.
    >>> with rate_limiter:
    >>>     response = requests.get("http://httpbin.org/get")
    # or simply call the `wait` method directly:
    >>> rate_limiter.wait()
    >>> response = requests.get("http://httpbin.org/get")
    """

    DEFAULT_MIN_INTERVAL: Optional[float | int] = 6.1

    def __init__(self, min_interval: Optional[float | int] = None):
        """Initializes the rate limiter with the `min_interval` argument.

        Args:
            min_interval (Optional[float | int]): Minimum number of seconds to wait before the next action
                                                  is taken or request sent.
        """

        self.min_interval = self._validate(min_interval if min_interval is not None else self.DEFAULT_MIN_INTERVAL)
        self._last_call: float | int | None = None

    @staticmethod
    def _validate(min_interval: Optional[float | int]) -> float:
        """Helper method that verifies that the minimum interval is a valid number that is also greater than or equal to
        0."""
        if not isinstance(min_interval, (int, float)):
            raise APIParameterException(
                "min_interval must be an number greater than or " f"equal to 0. Received value {min_interval}"
            )
        if min_interval < 0:
            raise APIParameterException("min_interval must be non-negative")
        return min_interval

    def wait(self, min_interval: Optional[float | int] = None) -> None:
        """Block (time.sleep) until at least `min_interval` has passed since last call.

        This method can be used with the min_interval attribute to determine when
        a search has been last sent and throttle requests to make sure rate limits
        aren't exceeded. If not enough time has passed, the API will
        wait before sending the next request.

        Args:
            min_interval (Optional[float | int] = None): The minimum time to wait until another call is sent.
                                                         Note that the min_interval attribute or argument must be
                                                         non-null, otherwise, the default min_interval value is used
        Exceptions:
            APIParameterException: Occurs if the value provided is either not an integer/float or is less than 0
        """

        min_interval = self._validate(
            min_interval
            if min_interval is not None
            else (self.min_interval if self.min_interval is not None else self.DEFAULT_MIN_INTERVAL)
        )

        if self._last_call is not None and min_interval:
            self._wait(min_interval, self._last_call)
        # record the time we actually proceed
        self._last_call = time.time()

    @staticmethod
    def _wait(min_interval: float | int, last_call: float | int):
        """Helper Method that calls time.sleep() in the background to wait based on the current time, the previous
        function call, and the minimum interval between the two time periods.

        Args:
            min_interval (float | int): The minimum time to wait until another call is sent.
            last_call (float | int): The start time. In context, the previously recorded time when
                                    the function was called

        The time to wait is essentially calculated as follows

        E.g: time.sleep(last_call - min_interval)
        """
        now = time.time()
        elapsed = now - last_call
        remaining = min_interval - elapsed

        if remaining > 0:
            logger.info(f"RateLimiter: sleeping {remaining:.2f}s to respect rate limit")
            time.sleep(remaining)

    def __call__(self, fn):
        """Rate limits the current function when used as a decorator. Can be used to ensure that rate limits are not
        exceeded for APIs.

        Decorator syntax:

            @limiter
            def send_request(...):
                ...

            response = send_request(...)
        """

        @wraps(fn)
        def wrapped(*args, **kwargs):
            """Helper function that wraps a function with the RateLimiter decorator to rate limit how frequently the
            decorated function can be called per `min_interval` seconds."""

            self.wait()
            return fn(*args, **kwargs)

        return wrapped

    def __enter__(self):
        """Context‐manager usage:

        with limiter:     do_slow_call()
        """
        self.wait()
        return self

    def __exit__(self, exc_type, exc, tb):
        """Exits the context manager after the execution of the wrapped function."""

        return False

    @contextmanager
    def rate(self, min_interval: float | int) -> Iterator[Self]:
        """Allows a temporary adjustment to the minimum interval when used with a context manager. The original minimum
        interval value is then reassigned afterward and the time of the last call is recorded.

        Args:
            min_interval: Indicates the minimum interval to be temporarily used during the call

        Yields:
            RateLimiter: The original rate limiter with a temporarily changed minimum interval
        """
        current_min_interval = self.min_interval
        try:
            self.wait(min_interval)
            yield self

        finally:
            self.min_interval = current_min_interval


__all__ = ["RateLimiter"]
