# /api/rate_limiting/rate_limiter.py
"""The scholar_flux.api.rate_limiting.threaded_rate_limiter module implements ThreadedRateLimiter for thread safety.

The ThreadedRateLimiter extends the basic functionality of the original RateLimiter class and can be used in
multithreaded scenarios to ensure that provider rate limits are not exceeded within a constant time interval.

This implementation provides thread-safe access to rate limiting functionality through the use of reentrant locks,
making it suitable for use in concurrent environments where multiple threads may access the same rate limiter instance.

"""
from __future__ import annotations
from contextlib import contextmanager
import time
from typing_extensions import Self
from scholar_flux.api.rate_limiting.rate_limiter import RateLimiter
from typing import Optional, Iterator, TYPE_CHECKING
import threading

if TYPE_CHECKING:
    from datetime import datetime


class ThreadedRateLimiter(RateLimiter):
    """Thread-safe version of RateLimiter that can be safely used across multiple threads.

    Inherits all functionality from RateLimiter but adds thread synchronization to prevent race conditions when multiple
    threads access the same limiter instance.

    """

    def __init__(self, min_interval: Optional[float | int] = None):
        """Initialize with thread safety."""
        super().__init__(min_interval)
        # Add thread synchronization
        self._lock = threading.RLock()

    def wait(self, min_interval: Optional[float | int] = None) -> None:
        """Thread-safe version of the `.wait` method that prevents race conditions."""
        min_interval = self._validate(min_interval if min_interval is not None else self.default_min_interval())

        # Synchronize access to _last_call and timing logic
        with self._lock:
            if self._last_call is not None and min_interval:
                self._wait(min_interval, self._last_call)
            # Record the time we actually proceed
            self._last_call = time.time()

    def wait_since(
        self, min_interval: Optional[float | int] = None, timestamp: Optional[float | int | datetime] = None
    ) -> None:
        """Thread-safe method for waiting until an interval from a reference timestamp or datetime has passed.

        Args:
            min_interval: Minimum interval to wait. Uses default if None.
            timestamp: Reference time as Unix timestamp or datetime. If None, sleeps for min_interval.

        """
        with self._lock:
            super().wait_since(min_interval, timestamp)

    def sleep(self, interval: Optional[float | int] = None) -> None:
        """Thread-safe version of `.sleep` that prevents race conditions.

        This method provides thread-safe access to the sleep functionality by acquiring the internal lock
        before performing the sleep operation. This ensures that the sleep duration is calculated and
        executed atomically.

        Args:
            interval: Optional interval to sleep for. If None, uses the default interval.

        """
        with self._lock:
            interval = self._validate(interval if interval is not None else self.default_min_interval())
            if interval > 0:
                self._sleep(interval)

    @contextmanager
    def rate(self, min_interval: float | int) -> Iterator[Self]:
        """Thread-safe version of `.rate` context manager.

        Args:
            min_interval: The minimum interval to temporarily use during the call

        Yields:
            ThreadSafeRateLimiter: The rate limiter with temporarily changed interval

        """
        # Synchronize min_interval changes
        with self._lock:
            current_min_interval = self.min_interval
            self.min_interval = self._validate(min_interval)
            self.wait()  # Uses its own locking internally

        try:
            yield self

        finally:
            # Restore original min_interval atomically
            with self._lock:
                self.min_interval = current_min_interval


__all__ = ["ThreadedRateLimiter"]
