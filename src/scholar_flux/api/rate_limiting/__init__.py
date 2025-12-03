# /api/rate_limiting/
"""The scholar_flux.api.rate_limiting module defines the rate-limiting behavior for all providers. The rate limiting
module is designed to be relatively straightforward to apply to a variety of context and extensible to account for
several varying contexts where rate limiting is required.

Modules:
    **rate_limiter**:
        Implements a basic rate limiter that applies rate limiting for a specified interval of time. Rate limiting
        directly using `RateLimiter.wait`  or used with a context manager that records the time of execution and the
        amount of time to wait directly.
    **threaded_rate_limiter**:
        Inherits from the basic RateLimiter class to account for multithreading scenarios that require the same
        resource. The usage is the same, but it is thread-safe.
    **retry_handler**:
        Basic implementation that defines a period of time to wait in between requests that are unsuccessful.
        This class is used to automatically retry failed requests until successful or the maximum retry limit has
        been exceeded. The end-user can decide whether to retry specific status codes or whether to halt early.

Classes:
    **RateLimiter**:
        The most basic rate limiter used for throttling requests using a constant interval
    **ThreadedRateLimiter**:
        A thread-safe implementation that inherits from the RateLimiter to apply in multithreading
    **RetryHandler**:
        Used to define the period of time to wait before sending a failed request with applications of max backoff and
        backoff_factor to assist in dynamically timing requests on successive request failures.

In addition, a `rate_limiter_registry` and `threaded_rate_limiter_registry` are implemented to aid in the normalization
of responses to the same provider across multiple search APIs. This is particularly relevant when using the
`scholar_flux.api.MultiSearchCoordinator` for multi-threaded requests across queries and configurations, where the
`threaded_rate_limiter_registry` is implemented under the hood for throttling across APIs.

Example usage:

    >>> import requests
    # both the RateLimiter and threaded rate limiter are implemented similarly:
    >>> from scholar_flux.api.rate_limiting import ThreadedRateLimiter
    >>> rate_limiter = ThreadedRateLimiter(min_interval = 3)
    # defines a simple decorated function that does the equivalent of calling `rate_limiter.wait()` between requests
    >>> @rate_limiter
    >>> def rate_limited_request(url = 'https://httpbin.org/get'):
    >>>    return requests.get(url)
     # the first call won't be throttled
    >>> rate_limited_request()
    # the second call will wait the minimum duration from the time `rate_limited_request` was last called
    >>> rate_limited_request()

"""
from scholar_flux.api.rate_limiting.rate_limiter import RateLimiter
from scholar_flux.api.rate_limiting.threaded_rate_limiter import ThreadedRateLimiter
from scholar_flux.api.rate_limiting.retry_handler import RetryHandler
from scholar_flux.api.models.rate_limiter_registry import RateLimiterRegistry

rate_limiter_registry = RateLimiterRegistry.from_defaults(threaded=False)
threaded_rate_limiter_registry = RateLimiterRegistry.from_defaults(threaded=True)

__all__ = [
    "RateLimiter",
    "ThreadedRateLimiter",
    "RetryHandler",
    "rate_limiter_registry",
    "threaded_rate_limiter_registry",
]
