from scholar_flux.api.providers import provider_registry
from scholar_flux.api.rate_limiting.rate_limiter import RateLimiter
from scholar_flux.api.rate_limiting.threaded_rate_limiter import ThreadedRateLimiter
from scholar_flux.api.rate_limiting.retry_handler import RetryHandler

rate_limiter_registry = {
    provider_name: RateLimiter(provider_config.request_delay)
    for provider_name, provider_config in provider_registry.items()
}

threaded_rate_limiter_registry = {
    provider_name: ThreadedRateLimiter(provider_config.request_delay)
    for provider_name, provider_config in provider_registry.items()
}

__all__ = [
    "RateLimiter",
    "ThreadedRateLimiter",
    "RetryHandler",
    "rate_limiter_registry",
    "threaded_rate_limiter_registry",
]
