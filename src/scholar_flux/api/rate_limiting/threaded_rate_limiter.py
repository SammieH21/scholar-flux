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
from typing import Optional, Iterator, TYPE_CHECKING, Dict, Any
import threading

if TYPE_CHECKING:
    from datetime import datetime


class ThreadedRateLimiter(RateLimiter):
    """Thread-safe version of RateLimiter that can be safely used across multiple threads.

    Inherits all functionality from RateLimiter but adds thread synchronization to prevent race conditions when multiple
    threads access the same limiter instance.

    """

    def __init__(self, min_interval: Optional[float | int] = None):
        """Initializes a new `ThreadedRateLimiter` with thread safety.

        Args:
            min_interval (Optional[float | int]): The default minimum interval to wait. Uses default if None

        """
        super().__init__(min_interval)
        # Add thread synchronization
        self._lock = threading.RLock()

    def wait(self, min_interval: Optional[float | int] = None, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Thread-safe version of the `.wait` method that prevents race conditions.

        Args:
            min_interval (Optional[float | int]): Minimum interval to wait. Uses default if None.
            metadata (Optional[Dict[str, Any]]): Optional metadata for observability (e.g., url, caller, reason).
        """
        min_interval = self._validate(min_interval if min_interval is not None else self.default_min_interval())

        # Synchronize access to _last_call and timing logic
        with self._lock:
            if self._last_call is not None and min_interval:
                self._wait(min_interval, self._last_call, metadata=metadata)
            # Record the time we actually proceed
            self._last_call = time.time()

    def wait_since(
        self,
        min_interval: Optional[float | int] = None,
        timestamp: Optional[float | int | datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Thread-safe method for waiting until an interval from a reference timestamp or datetime has passed.

        Args:
            min_interval (Optional[float | int]): Minimum interval to wait. Uses default if None.
            timestamp (Optional[float | int]):
                Reference time formatted as a Unix timestamp or datetime. If None, sleeps for min_interval.
            metadata (Optional[Dict[str, Any]]): Optional metadata for observability (e.g., url, caller, reason).

        """
        with self._lock:
            super().wait_since(min_interval, timestamp, metadata=metadata)

    def sleep(self, interval: Optional[float | int] = None, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Thread-safe version of `.sleep` that prevents race conditions.

        This method provides thread-safe access to the sleep functionality by acquiring the internal lock
        before performing the sleep operation. This ensures that the sleep duration is calculated and
        executed atomically.

        Args:
            interval (Optional[float | int]): Optional interval to sleep for. If None, uses the default interval.
            metadata (Optional[Dict[str, Any]]): Optional metadata for observability (e.g., url, caller, reason).

        """
        with self._lock:
            interval = self._validate(interval if interval is not None else self.default_min_interval())
            if interval > 0:
                self._sleep(interval, metadata=metadata)

    @contextmanager
    def rate(self, min_interval: float | int, metadata: Optional[Dict[str, Any]] = None) -> Iterator[Self]:
        """Thread-safe version of `.rate` context manager.

        Args:
            min_interval (float | int): The minimum interval to temporarily use during the call
            metadata (Optional[Dict[str, Any]]): Optional metadata for observability (e.g., url, caller, reason).

        Yields:
            Self: The rate limiter with temporarily changed interval

        """
        # Synchronize min_interval changes
        with self._lock:
            current_min_interval = self.min_interval
            self.min_interval = self._validate(min_interval)
            self.wait(metadata=metadata)  # Uses its own locking internally

        try:
            yield self

        finally:
            # Restore original min_interval atomically
            with self._lock:
                self.min_interval = current_min_interval


__all__ = ["ThreadedRateLimiter"]
