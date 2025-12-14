# /api/rate_limiting/rate_limiter.py
"""The scholar_flux.api.rate_limiting.rate_limiter module implements a simple, general RateLimiter.

ScholarFlux uses and builds upon this `RateLimiter` implementation to ensure that the number of requests to an API
provider does not exceed the limit within the specified time interval.

"""
from __future__ import annotations
from contextlib import contextmanager
from typing_extensions import Self
import time
from functools import wraps
from scholar_flux.exceptions import APIParameterException
from scholar_flux.utils.repr_utils import generate_repr_from_string
from datetime import datetime
from typing import Optional, Iterator
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """A basic rate limiter used to ensure that function calls (such as API requests) do not exceed a specified rate.

    The `RateLimiter` is used within ScholarFlux to throttle the total number of requests that can be made within a
    defined time interval (measured in seconds).

    This class ensures that calls to `RateLimiter.wait()` (or any decorated function) are spaced
    by at least `min_interval` seconds.

    For multithreading applications, the `RateLimiter` is not thread-safe. Instead, the `ThreadedRateLimiter` subclass
    can provide a thread-safe implementation when required.

    Args:
        min_interval (Optional[float | int]):
            The minimum number of seconds that must elapse before another request sent or call is performed. If
            `min_interval` is not specified, then class attribute, `RateLimiter.DEFAULT_MIN_INTERVAL` will be assigned
            to `RateLimiter.min_interval` instead.

    Examples:
        >>> import requests
        >>> from scholar_flux.api import RateLimiter
        >>> rate_limiter = RateLimiter(min_interval = 5)
        >>> # The first call won't sleep, because a prior call using the rate limiter doesn't yet exist
        >>> with rate_limiter:
        ...     response = requests.get("http://httpbin.org/get")
        >>> # will sleep if 5 seconds since the last call hasn't elapsed.
        >>> with rate_limiter:
        ...     response = requests.get("http://httpbin.org/get")
        >>> # Or simply call the `wait` method directly:
        >>> rate_limiter.wait()
        >>> response = requests.get("http://httpbin.org/get")

    """

    DEFAULT_MIN_INTERVAL: float | int = 6.1

    def __init__(self, min_interval: Optional[float | int] = None):
        """Initializes the rate limiter with the `min_interval` argument.

        Args:
            min_interval (Optional[float | int]): Minimum number of seconds to wait before the next call
                                                  is performed or request sent.

        """
        self.min_interval = min_interval if min_interval is not None else self.DEFAULT_MIN_INTERVAL
        self._last_call: float | int | None = None

    @property
    def min_interval(self) -> float | int:
        """The minimum number of seconds that must elapse before another request sent or action is taken."""
        return self._min_interval

    @min_interval.setter
    def min_interval(self, min_interval: float | int):
        """Validates the `min_interval` property upon assignment to ensure that the received value is numeric.

        This setter allows the `min_interval` property to be assigned directly to a rate limiter instance and requires
        no further action (e.g., `rate_limiter.min_interval=4`).

        Args:
            min_interval (float | int):
                The minimum number of seconds that must elapse before another request sent or call is performed.

        Raises:
            APIParameterException: If the received value is a non-missing value that is not a float or integer

        """
        self._min_interval = self._validate(min_interval)

    @staticmethod
    def _validate(min_interval: float | int) -> float:
        """Helper that verifies if the input to `min_interval` is a valid number that is greater than or equal to 0."""
        if not isinstance(min_interval, (int, float)):
            raise APIParameterException(
                f"`min_interval` must be a number greater than or equal to 0. Received value, '{min_interval}'"
            )
        if min_interval < 0:
            raise APIParameterException("min_interval must be non-negative")
        return min_interval

    @staticmethod
    def _validate_timestamp(timestamp: float | int) -> float | int:
        """Validates timestamp is a non-negative number."""
        if not isinstance(timestamp, (float, int)) or timestamp < 0:
            raise APIParameterException(
                f"`timestamp` must a valid timestamp formatted as a non-negative number. Received value, '{timestamp}'"
            )
        return timestamp

    def wait(self, min_interval: Optional[float | int] = None) -> None:
        """Block (`time.sleep`) until at least `min_interval` has passed since last call.

        This method can be used with the min_interval attribute to determine when
        a search was last sent and throttle requests to make sure rate limits
        aren't exceeded. If not enough time has passed, the API will
        wait before sending the next request.

        Args:
            min_interval (Optional[float | int] = None):
                The minimum time to wait until another call is sent. Note that the min_interval attribute or argument
                must be non-null, otherwise, the default min_interval value is used.

        Exceptions:
            APIParameterException: Occurs if the value provided is either not an integer/float or is less than 0

        """
        min_interval = self._validate(min_interval if min_interval is not None else self.default_min_interval())

        if self._last_call is not None and min_interval:
            self._wait(min_interval, self._last_call)
        # record the time we actually proceed
        self._last_call = time.time()

    @classmethod
    def _wait(cls, min_interval: float | int, last_call: float | int):
        """Helper Method that calls `time.sleep()` in the background to wait for a specific number of seconds.

        This method determines how long to wait by referencing when `._wait()` was last called along with the
        `min_interval` that defines the minimum amount of time between successive calls/requests.

        Args:
            min_interval (float | int): The minimum time to wait until another call is sent.
            last_call (float | int): The start time. In context, the previously recorded time when
                                    the function was called

        The time to wait is essentially calculated as follows:

        1. Determine the number of seconds that have elapsed since the last call:
           (e.g., `elapsed = time.time() - rate_limiter._last_call`)
        2. Calculate the number of seconds remaining until the minimum interval is reached:
           (e.g., `remaining = rate_limiter.min_interval - elapsed`)
        3. If `remaining` is positive, sleep for that duration:
           (e.g., `time.sleep(remaining)`)

        """
        now = time.time()
        elapsed = now - last_call
        remaining = min_interval - elapsed

        if remaining > 0:
            cls._sleep(remaining)

    def default_min_interval(self) -> float | int:
        """Returns the default minimum interval for the current rate limiter."""
        return self.min_interval if self.min_interval is not None else self.DEFAULT_MIN_INTERVAL

    def sleep(self, interval: Optional[float | int] = None) -> None:
        """Simple Instance level implementation of `sleep` that can be overridden when needed.

        Args:
            interval (Optional[float | int] = None):
                The time interval to sleep. If None, the default minimum interval for the current rate limiter is used.
                must be non-null, otherwise, the default min_interval value is used.

        Exceptions:
            APIParameterException: Occurs if the value provided is either not an integer/float or is less than 0

        """
        interval = self._validate(interval if interval is not None else self.default_min_interval())
        if interval > 0:
            self._sleep(interval)

    def wait_since(
        self, min_interval: Optional[float | int] = None, timestamp: Optional[float | int | datetime] = None
    ) -> None:
        """Wait based on a reference timestamp or datetime.

        Args:
            min_interval: Minimum interval to wait. Uses default if None.
            timestamp: Reference time as Unix timestamp or datetime. If None, sleeps for min_interval.

        """
        if timestamp is not None:
            timestamp = self._validate_timestamp(
                timestamp.timestamp() if isinstance(timestamp, datetime) else timestamp
            )

        min_interval = self._validate(min_interval if min_interval is not None else self.default_min_interval())

        if timestamp is None:
            self._sleep(min_interval)
        else:
            self._wait(min_interval, timestamp)

    @classmethod
    def _sleep(cls, interval: int | float) -> None:
        """Logs the sleeping duration and blocks (`time.sleep`) until at `interval` has passed."""
        logger.info(f"RateLimiter: sleeping {interval:.2f}s to respect rate limit")
        time.sleep(interval)

    def __call__(self, fn):
        """Implements a rate limit for the defined function when the `RateLimiter` is used as a decorator.

        This decorator can be used to ensure a function can be called once every `min_interval` seconds and helps to
        ensure that API rate limits are not exceeded.

        Decorator syntax:

            @limiter
            def send_request(...):
                ...

            response = send_request(...)

        """

        @wraps(fn)
        def wrapped(*args, **kwargs):
            """Wraps and decorates a function using the rate limiter to limit how frequently it can be called."""
            self.wait()
            return fn(*args, **kwargs)

        return wrapped

    def __enter__(self):
        """Enables a `RateLimiter` instance to be used as a context manager for throttling function calls or requests.

        Example:
        >>> with limiter:
        ...     do_slow_call()

        """
        self.wait()
        return self

    def __exit__(self, exc_type, exc, tb):
        """Exits the context manager after the execution of the wrapped function."""
        return False

    @contextmanager
    def rate(self, min_interval: float | int) -> Iterator[Self]:
        """Temporarily adjusts the minimum interval between function calls or requests when used with a context manager.

        After the context manager exits, the original minimum interval value is then reassigned its previous value,
        and the time of the last call is recorded.

        Args:
            min_interval: Indicates the minimum interval to be temporarily used during the call

        Yields:
            RateLimiter: The original rate limiter with a temporarily changed minimum interval

        """
        current_min_interval = self.min_interval
        try:
            self.min_interval = self._validate(min_interval)
            self.wait()
            yield self

        finally:
            self.min_interval = current_min_interval

    def __repr__(self) -> str:
        """Defines the string representation of the RateLimiter/subclasses to show the class name and `min_interval`."""
        class_name = self.__class__.__name__
        attributes = dict(min_interval=self.min_interval)
        return generate_repr_from_string(class_name, attributes, flatten=True)


__all__ = ["RateLimiter"]
