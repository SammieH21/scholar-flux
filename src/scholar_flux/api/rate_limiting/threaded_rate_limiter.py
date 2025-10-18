# /api/rate_limiting/rate_limiter.py
"""
The scholar_flux.api.rate_limiting.threaded_rate_limiter module implements creates a ThreadedRateLimiter that extends
the basic functionality of the original RateLimiter class. This class can be used in multithreaded scenarios to ensure
that rate limits to a provider are not exceeded within the specified constant time interval.
"""
from __future__ import annotations
from contextlib import contextmanager
import time
from typing_extensions import Self
from scholar_flux.api.rate_limiting.rate_limiter import RateLimiter
from typing import Optional, Iterator
import threading


class ThreadedRateLimiter(RateLimiter):
    """
    Thread-safe version of RateLimiter that can be safely used across multiple threads.

    Inherits all functionality from RateLimiter but adds thread synchronization
    to prevent race conditions when multiple threads access the same limiter instance.
    """

    def __init__(self, min_interval: Optional[float | int] = None):
        """Initialize with thread safety."""
        super().__init__(min_interval)
        # Add thread synchronization
        self._lock = threading.Lock()

    def wait(self, min_interval: Optional[float | int] = None) -> None:
        """Thread-safe version of wait() that prevents race conditions."""
        min_interval = self._validate(
            min_interval
            if min_interval is not None
            else (self.min_interval if self.min_interval is not None else self.DEFAULT_MIN_INTERVAL)
        )

        # Synchronize access to _last_call and timing logic
        with self._lock:
            if self._last_call is not None and min_interval:
                self._wait(min_interval, self._last_call)
            # Record the time we actually proceed
            self._last_call = time.time()

    @contextmanager
    def rate(self, min_interval: float | int) -> Iterator[Self]:
        """
        Thread-safe version of rate() context manager.

        Args:
            min_interval: The minimum interval to temporarily use during the call

        Yields:
            ThreadSafeRateLimiter: The rate limiter with temporarily changed interval
        """
        # Synchronize min_interval changes
        with self._lock:
            current_min_interval = self.min_interval
            self.min_interval = self._validate(min_interval)

        try:
            self.wait()  # Uses its own locking internally
            yield self

        finally:

            # Restore original min_interval atomically
            with self._lock:
                self.min_interval = current_min_interval


__all__ = ["ThreadedRateLimiter"]
