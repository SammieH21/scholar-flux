# tests/api/test_api_history.py
"""Tests for the history module used for rate limiting and retry observability."""
import pytest
from scholar_flux.api.rate_limiting.history import HistoryDeque, RateLimitEvent, RetryAttempt
from scholar_flux.api import RateLimiter, RetryHandler, ReconstructedResponse
from scholar_flux.utils import parse_iso_timestamp
from datetime import datetime


@pytest.fixture(autouse=True)
def reset_history():
    """Reset class-level history deques before and after each test."""
    # Store original history references
    original_rate_limiter_history = RateLimiter.history
    original_retry_handler_history = RetryHandler.history

    # Reset to fresh deques
    RateLimiter.history = HistoryDeque.create()
    RetryHandler.history = HistoryDeque.create()

    yield

    # Restore original history references
    RateLimiter.history = original_rate_limiter_history
    RetryHandler.history = original_retry_handler_history


class TestHistoryDeque:
    """Tests for `HistoryDeque` functionality."""

    def test_create_default_maxlen(self):
        """Verifies that the `create` factory method uses DEFAULT_MAX_HISTORY to bound the size of the deque."""
        history = HistoryDeque.create()
        assert history.maxlen == HistoryDeque.DEFAULT_MAX_HISTORY

    def test_create_custom_maxlen(self):
        """Verifies that a custom `maxlen` parameter is accepted by the `HistoryDeque.create()` factory method."""
        history = HistoryDeque.create(maxlen=50)
        assert history.maxlen == 50

    def test_append_sleep_event(self):
        """Verifies that `HistoryDeque.append()` can be used to append a new `RateLimitEvent` to the deque."""
        history = HistoryDeque.create()
        event = RateLimitEvent(interval=1.5)
        history.append(event)
        assert len(history) == 1
        assert history[0] is event

    def test_append_retry_attempt(self):
        """Verifies that `HistoryDeque.append()` can be used to append a new `RetryAttempt` to the deque."""
        history = HistoryDeque.create()
        attempt = RetryAttempt(
            status_code=429,
            delay=2.0,
            min_retry_delay=0.5,
            backoff_factor=1.5,
            attempt_number=1,
            success=False,
            duration=0.005,
        )
        history.append(attempt)
        assert len(history) == 1
        assert history[0] is attempt

    def test_maxlen_evicts_oldest(self):
        """Verifies that the oldest events are evicted from a `HistoryDeque` when the maxlen is exceeded."""
        history = HistoryDeque.create(maxlen=3)
        events = [RateLimitEvent(interval=float(i)) for i in range(5)]
        for event in events:
            history.append(event)

        assert len(history) == 3
        # Oldest (0, 1) should be evicted, newest (2, 3, 4) remain
        assert history[0].interval == 2.0
        assert history[1].interval == 3.0
        assert history[2].interval == 4.0

    def test_clear_history(self):
        """Verifies that `HistoryDeque.clear_history()` removes all stored events."""
        history = HistoryDeque.create()
        history.append(RateLimitEvent(interval=1.0))
        history.append(RateLimitEvent(interval=2.0))
        assert len(history) == 2

        history.clear_history()
        assert len(history) == 0

    def test_modify_history_size(self):
        """Verifies that `HistoryDeque.modify_history_size()` creates new deque with an updated maximum deque length."""
        history = HistoryDeque.create(maxlen=10)
        for i in range(5):
            history.append(RateLimitEvent(interval=float(i)))

        resized = history.modify_history_size(maxlen=3)

        assert resized.maxlen == 3
        assert len(resized) == 3
        # Should keep the 3 most recent
        assert resized[0].interval == 2.0
        assert resized[2].interval == 4.0

    def test_export_history_sleep_events(self):
        """Verifies that `HistoryDeque.export_history()` serializes appended RateLimitEvents as dicts."""
        # When first created, the deque should be empty
        history = HistoryDeque.create()
        exported = history.export_history()
        assert exported == []

        event = RateLimitEvent(interval=1.5, metadata={"caller": "wait"})
        history.append(event)

        # Should have a single event
        exported = history.export_history()

        assert len(exported) == 1
        assert exported[0]["interval"] == 1.5
        assert exported[0]["metadata"] == {"caller": "wait"}
        assert "timestamp" in exported[0]

    @pytest.mark.parametrize(
        "mask_values,expected_url_params", ([False, "mailto=random.email@example.com"], [True, "mailto=***"])
    )
    def test_export_history_retry_attempts(self, mask_values, expected_url_params):
        """Verifies that `HistoryDeque.export_history()` serializes RetryAttempts as dicts.

        Sensitive data should also be masked on export if `mask_values=True` (default)

        """
        history = HistoryDeque.create()
        attempt = RetryAttempt(
            status_code=503,
            delay=4.0,
            min_retry_delay=1.0,
            backoff_factor=2.0,
            attempt_number=2,
            success=False,
            url="https://api.example.com/search?mailto=random.email@example.com",
        )
        history.append(attempt)

        exported = history.export_history(mask_values=mask_values)

        assert len(exported) == 1
        assert exported[0]["status_code"] == 503
        assert exported[0]["delay"] == 4.0
        assert exported[0]["attempt_number"] == 2
        assert exported[0]["success"] is False
        assert exported[0]["url"] == f"https://api.example.com/search?{expected_url_params}"

    def test_history_representation(self):
        """Verifies that the generated `HistoryDeque` representation accurately displays its structure."""

        history = HistoryDeque(
            [
                RateLimitEvent(
                    interval=3.5,
                    request_delay=5,
                    caller="search",
                    url="https://api.example.com/search?page=1&api_key=random_api_key",
                ),
                RateLimitEvent(
                    interval=3.5,
                    request_delay=5,
                    caller="search",
                    url="https://api.example.com/search?page=2&api_key=random_api_key",
                ),
            ]
        )

        representation = repr(history)
        page_1_url = "https://api.example.com/search?page=1&api_key=***"
        page_2_url = "https://api.example.com/search?page=2&api_key=***"
        assert page_1_url in representation
        assert page_2_url in representation

        assert f"HistoryDeque([{repr(history[0])}, {repr(history[1])}])" == representation

    def test_retry_attempt_representation(self):
        """Verifies the successful generation of the representation of an unsuccessful retry attempt."""
        retry_attempt = RetryAttempt(
            status_code=401,
            delay=4.0,
            min_retry_delay=1.0,
            backoff_factor=2.0,
            attempt_number=2,
            message="Max limit reached for email: random.email@example.com",
            success=False,
            url="https://api.example.com/search?mailto=random.email@example.com",
        )

        representation = repr(retry_attempt)
        assert "https://api.example.com/search?mailto=***" in representation
        assert "Max limit reached for email: ***" in representation


class TestRateLimitEvent:
    """Tests for `RateLimitEvent` dataclasses."""

    def test_timestamp_auto_generated(self):
        """Verifies that a valid timestamp is automatically generated on `RateLimitEvent` creation."""
        event = RateLimitEvent(interval=1.0)
        assert event.timestamp is not None
        assert isinstance(event.timestamp, str)

        assert isinstance(parse_iso_timestamp(event.timestamp), datetime)  # Should be a valid timestamp

    def test_metadata_optional(self):
        """Verifies that the `metadata` field defaults to None on `RateLimitEvent` creation."""
        event = RateLimitEvent(interval=1.0)
        assert event.metadata is None

    def test_metadata_retained(self):
        """Verifies the `metadata` field correctly validates and accepts dictionaries as input without error."""
        metadata = {"caller": "wait_since", "url": "https://api.example.com"}
        event = RateLimitEvent(interval=2.5, metadata=metadata)
        assert event.metadata == metadata
        assert event.metadata["caller"] == "wait_since"

    def test_frozen(self):
        """Verifies that the `RateLimitEvent` class is immutable."""
        event = RateLimitEvent(interval=1.0)
        with pytest.raises(AttributeError):
            event.interval = 2.0  # type: ignore


class TestRetryAttempt:
    """Tests for RetryAttempt dataclass."""

    def test_required_fields(self):
        """Verifies that `RetryAttempt` correctly accepts valid values on all core fields."""
        attempt = RetryAttempt(
            status_code=200,
            delay=0,
            min_retry_delay=0.5,
            backoff_factor=1.5,
            attempt_number=0,
            success=True,
        )
        assert attempt.status_code == 200
        assert attempt.success is True

        # Other fields should default to None
        assert attempt.url is None
        assert attempt.duration is None

    def test_timestamp_auto_generated(self):
        """Verifies that a valid timestamp is automatically generated on creation."""
        attempt = RetryAttempt(
            status_code=200,
            delay=0,
            min_retry_delay=0.5,
            backoff_factor=1.5,
            attempt_number=0,
            success=True,
        )
        assert attempt.timestamp is not None
        assert isinstance(attempt.timestamp, str)
        assert isinstance(parse_iso_timestamp(attempt.timestamp), datetime)

    def test_url_retained(self):
        """Verifies that the `url` field is stored correctly."""
        url = "https://api.crossref.org/works"
        attempt = RetryAttempt(
            status_code=429,
            delay=5.0,
            min_retry_delay=1.0,
            backoff_factor=2.0,
            attempt_number=1,
            success=False,
            url=url,
        )
        assert attempt.url == url

    def test_frozen(self):
        """Verifies that the `RetryAttempt` class is immutable."""
        attempt = RetryAttempt(
            status_code=200,
            delay=0,
            min_retry_delay=0.5,
            backoff_factor=1.5,
            attempt_number=0,
            success=True,
        )
        with pytest.raises(AttributeError):
            attempt.success = False  # type: ignore

    def test_retry_attempt_from_successful_response(self):
        """Verifies that `RetryAttempt.from_response` correctly initializes a new instance from a response."""
        response = ReconstructedResponse.build(
            status_code=200,
            url="https://api.crossref.org/works",
            json={"status": "ok"},
        )
        attempt = RetryAttempt.from_response(
            response,
            delay=2.0,
            min_retry_delay=0.5,
            backoff_factor=1.5,
            attempt_number=0,
            duration=None,
        )
        assert attempt.url == response.url
        assert attempt.status_code == 200
        assert attempt.success is True
        assert attempt.elapsed is None
        assert attempt.message is None
        assert attempt.error is None

    def test_retry_attempt_from_error_response(self):
        """Verifies that `RetryAttempt.from_response` can correctly initialize from an unsuccessful response."""
        response = ReconstructedResponse.build(
            status_code=429,
            url="https://api.crossref.org/works",
            json={"status": "Too Many Requests"},
        )
        attempt = RetryAttempt.from_response(
            response,
            delay=2.0,
            min_retry_delay=0.5,
            backoff_factor=1.5,
            attempt_number=1,
            duration=5.0,
        )
        assert attempt.url == response.url
        assert attempt.status_code == 429
        assert attempt.success is False
        assert attempt.elapsed is None
        assert attempt.message == (
            "Expected a 200 (ok) status_code for the ReconstructedResponse. Received: 429 (Too Many Requests)"
        )
        assert attempt.error == "HTTPError"

    def test_retry_attempt_from_no_response(self):
        """Verifies that `RetryAttempt.from_response` can correctly initialize a new instance without a response."""
        message = "Failed response"
        attempt = RetryAttempt.from_response(
            response=None,
            url=None,
            delay=2.0,
            min_retry_delay=0.5,
            backoff_factor=1.5,
            attempt_number=1,
            duration=5.0,
            message=message,
        )

        assert attempt.url is None
        assert attempt.status_code is None
        assert attempt.success is False
        assert attempt.elapsed is None
        assert attempt.message == message
        assert attempt.error is None
        assert attempt.timeout is False


class TestClassLevelHistory:
    """Tests for class-level history on RateLimiter and RetryHandler."""

    def test_rate_limiter_resize_history(self):
        """Verifies that `RateLimiter.resize_history()` correctly resizes the number of events stored at any point."""
        for i in range(7):
            RateLimiter.history.append(RateLimitEvent(interval=float(i)))

        RateLimiter.resize_history(maxlen=3)

        assert RateLimiter.history.maxlen == 3
        assert len(RateLimiter.history) == 3
        assert {event.interval for event in RateLimiter.history} == {4, 5, 6}

    def test_retry_handler_resize_history(self):
        """Verifies that `RetryHandler.resize_history()` correctly resizes the number of stored retry attempts."""
        for i in range(5):
            RetryHandler.history.append(
                RetryAttempt(
                    status_code=503,
                    delay=float(i),
                    min_retry_delay=0.5,
                    backoff_factor=1.5,
                    attempt_number=i,
                    success=False,
                )
            )

        RetryHandler.resize_history(maxlen=2)

        assert RetryHandler.history.maxlen == 2
        assert len(RetryHandler.history) == 2
        assert {attempt.attempt_number for attempt in RetryHandler.history} == {3, 4}  # Stores the last two most recent
