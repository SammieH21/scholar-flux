"""Tests for dictionary masking and key matching functionality.

This module tests the enhanced masking capabilities including:
- KeyMaskingPattern.matches_key() helper method
- FuzzyKeyMaskingPattern.matches_key() helper method
- SensitiveDataMasker.mask_dict() method for direct dictionary masking
- Recursive masking of nested structures

"""

import pytest
import json
from scholar_flux import logger
from scholar_flux.api.validators import validate_and_process_url
import uuid
from scholar_flux.security import (
    KeyMaskingPattern,
    FuzzyKeyMaskingPattern,
    SensitiveDataMasker,
)

# ======================================================================================
# Key Matching Helper Method Tests
#
# Verifies the behavior of the `matches_key()` helper methods that are added to
# KeyMaskingPattern` and `FuzzyKeyMaskingPattern` to simplify dictionary masking logic.
# ======================================================================================


def test_key_masking_pattern_exact_match():
    """Verifies that KeyMaskingPattern.matches_key() performs exact string matching."""
    pattern = KeyMaskingPattern(name="test", field="password")

    assert pattern.matches_key("password") is True
    assert pattern.matches_key("PASSWORD") is True  # ignore_case=True by default
    assert pattern.matches_key("pass") is False
    assert pattern.matches_key("password123") is False


def test_key_masking_pattern_case_sensitive():
    """Verifies that case-sensitive matching works when ignore_case=False."""
    pattern = KeyMaskingPattern(name="test", field="password", ignore_case=False)

    assert pattern.matches_key("password") is True
    assert pattern.matches_key("PASSWORD") is False
    assert pattern.matches_key("Password") is False


def test_fuzzy_key_masking_pattern_regex_match():
    """Verifies that FuzzyKeyMaskingPattern.matches_key() uses regex matching."""
    pattern = FuzzyKeyMaskingPattern(name="test", field="pass(word)?")

    assert pattern.matches_key("password") is True
    assert pattern.matches_key("pass") is True
    assert pattern.matches_key("passphrase") is True
    assert pattern.matches_key("mypass") is True
    assert pattern.matches_key("user") is False


def test_fuzzy_key_masking_pattern_case_sensitive():
    """Verifies that fuzzy patterns respect ignore_case flag."""
    pattern = FuzzyKeyMaskingPattern(name="test", field="Pass", ignore_case=False)

    assert pattern.matches_key("Pass") is True
    assert pattern.matches_key("pass") is False
    assert pattern.matches_key("PASSWORD") is False


def test_masking_pattern_wrong_type():
    """Verifies that the `.matches_key()` method returns `False` when encountering non-string keys."""
    key_pattern = KeyMaskingPattern(name="test_key", field="password")
    fuzzy_key_pattern = FuzzyKeyMaskingPattern(name="test_key", field="passkey2")

    assert key_pattern.matches_key(1) is False  # type: ignore
    assert fuzzy_key_pattern.matches_key(None) is False  # type: ignore


# ============================================================================
# Dictionary Masking Tests
#
# Validates the mask_dict() method that provides direct dictionary masking
# as a more reliable alternative to string pattern matching for structured data.
# ============================================================================


def test_basic_dict_masking():
    """Verifies that basic dictionary masking works for registered patterns."""
    masker = SensitiveDataMasker(register_defaults=False)
    masker.add_sensitive_key_patterns(name="passwords", fields=["password", "pass"])

    data = {"password": "secret123", "host": "localhost", "port": 5432}

    masked = masker.mask_dict(data)

    assert masked["password"] == "***"
    assert masked["host"] == "localhost"
    assert masked["port"] == 5432


def test_nested_dict_masking():
    """Verifies that nested dictionaries are recursively masked."""
    masker = SensitiveDataMasker(register_defaults=False)
    masker.add_sensitive_key_patterns(name="credentials", fields=["password", "api_key"])

    data = {
        "database": {"host": "localhost", "password": "db_secret"},
        "api": {"api_key": "sk-123456", "endpoint": "https://api.example.com"},
    }

    masked = masker.mask_dict(data)

    assert masked["database"]["password"] == "***"
    assert masked["database"]["host"] == "localhost"
    assert masked["api"]["api_key"] == "***"
    assert masked["api"]["endpoint"] == "https://api.example.com"


def test_dict_masking_with_tuple_of_dicts():
    masker = SensitiveDataMasker(register_defaults=False)
    masker.add_sensitive_key_patterns(name="passwords", fields="password")

    data = {"servers": ({"password": "secret1"}, {"password": "secret2"})}
    masked = masker.mask_dict(data)
    assert masked["servers"][0]["password"] == "***"
    assert isinstance(masked["servers"], tuple)


def test_list_of_dicts_masking():
    """Verifies that lists containing dictionaries are properly masked."""
    masker = SensitiveDataMasker(register_defaults=False)
    masker.add_sensitive_key_patterns(name="passwords", fields="password")

    data = {"servers": [{"host": "server1", "password": "pass1"}, {"host": "server2", "password": "pass2"}]}

    masked = masker.mask_dict(data)

    assert masked["servers"][0]["password"] == "***"
    assert masked["servers"][1]["password"] == "***"
    assert masked["servers"][0]["host"] == "server1"
    assert masked["servers"][1]["host"] == "server2"


def test_dict_masking_case_insensitive():
    """Verifies that case-insensitive key matching works in dictionaries."""
    masker = SensitiveDataMasker(register_defaults=False)
    masker.add_sensitive_key_patterns(name="passwords", fields="password", ignore_case=True)

    data = {"password": "secret1", "Password": "secret2", "PASSWORD": "secret3", "host": "localhost"}

    masked = masker.mask_dict(data)

    assert masked["password"] == "***"
    assert masked["Password"] == "***"
    assert masked["PASSWORD"] == "***"
    assert masked["host"] == "localhost"


def test_fuzzy_dict_masking():
    """Verifies that fuzzy (regex) patterns work with dictionary masking."""
    masker = SensitiveDataMasker(register_defaults=False)
    masker.add_sensitive_key_patterns(name="email_fields", fields="e?mail", fuzzy=True)

    data = {
        "email": "user@example.com",
        "mail": "admin@example.com",
        "mailto": "support@example.com",
        "username": "testuser",
    }

    masked = masker.mask_dict(data)

    assert masked["email"] == "***"
    assert masked["mail"] == "***"
    assert masked["mailto"] == "***"
    assert masked["username"] == "testuser"


def test_dict_masking_with_custom_replacement():
    """Verifies that custom replacement strings are respected in dictionary masking."""
    masker = SensitiveDataMasker(register_defaults=False)
    masker.add_sensitive_key_patterns(name="secrets", fields="secret", replacement="[REDACTED]")

    data = {"secret": "top_secret", "public": "information"}
    masked = masker.mask_dict(data)

    assert masked["secret"] == "[REDACTED]"
    assert masked["public"] == "information"


def test_mask_dict_with_embedded_sensitive_strings():
    """Tests that string values with embedded sensitive patterns are masked even when key is not sensitive."""
    masker = SensitiveDataMasker(register_defaults=True)
    data = {
        "url": "https://api.example.com?api_key=secret123",
        "connection": "postgresql://user:password@localhost/db",
        "status": "ok",
    }
    masked = masker.mask_dict(data)
    assert "secret123" not in masked["url"] and "api_key=***" in masked["url"]
    assert "password" not in masked["connection"] and "user:***@localhost" in masked["connection"]
    assert masked["status"] == "ok"


def test_dict_masking_preserves_types():
    """Verifies that non-string values in dictionaries are preserved correctly."""
    masker = SensitiveDataMasker(register_defaults=False)
    masker.add_sensitive_key_patterns(name="passwords", fields="password")

    data = {"password": "secret", "port": 5432, "enabled": True, "timeout": None, "tags": ["prod", "critical"]}

    masked = masker.mask_dict(data)

    assert masked["password"] == "***"
    assert masked["port"] == 5432
    assert masked["enabled"] is True
    assert masked["timeout"] is None
    assert masked["tags"] == ["prod", "critical"]


def test_dict_masking_with_defaults():
    """Verifies that default patterns work correctly with dictionary masking."""
    masker = SensitiveDataMasker(register_defaults=True)

    data = {
        "api_key": "sk-proj-abc123",
        "password": "secret_pass",
        "email": "user@example.com",
        "host": "localhost",
        "apikey": "another_key",
    }

    masked = masker.mask_dict(data)

    assert masked["api_key"] == "***"
    assert masked["password"] == "***"
    assert masked["email"] == "***"
    assert masked["apikey"] == "***"
    assert masked["host"] == "localhost"


# ============================================================================
# Real-World Scenario Tests
#
# Validates actual configuration masking scenarios that occur in ScholarFlux
# when using various cache storage backends (Redis, MongoDB, PostgreSQL).
# ============================================================================


@pytest.fixture(autouse=True)
def masker() -> SensitiveDataMasker:
    """Fixture for quickly creating and using a preconfigured masker with default settings."""
    return SensitiveDataMasker(register_defaults=True)


def test_redis_config_masking(masker):
    """Verifies that Redis configuration dictionaries are properly masked."""
    redis_config = {"host": "localhost", "port": 6379, "password": "redis_secret_123", "db": 0}

    masked = masker.mask_dict(redis_config)

    assert masked["password"] == "***"
    assert masked["host"] == "localhost"
    assert masked["port"] == 6379
    assert masked["db"] == 0


def test_edge_case_config_processing(masker):
    """Verifies that non-dictionary elements (empty dictionaries, wrong types) are ignored when masked."""
    assert masker.mask_dict(None) is None
    assert masker.mask_dict({}) == {}
    assert masker.mask_dict("not a dictionary") == "not a dictionary"
    assert masker.mask_dict([1, 2, 3]) == [1, 2, 3]


def test_database_config_masking(masker):
    """Verifies that complex database configurations are properly masked."""
    db_config = {
        "connections": {
            "primary": {
                "host": "db.example.com",
                "port": 5432,
                "database": "myapp",
                "username": "dbuser",
                "password": "db_p@ssw0rd!",
            },
            "replica": {"host": "db-replica.example.com", "password": "replica_pass"},
        }
    }

    masked = masker.mask_dict(db_config)

    assert masked["connections"]["primary"]["password"] == "***"
    assert masked["connections"]["replica"]["password"] == "***"
    assert masked["connections"]["primary"]["host"] == "db.example.com"
    assert masked["connections"]["primary"]["username"] == "dbuser"


def test_api_config_with_multiple_credentials(masker, caplog):
    """Verifies that configurations with multiple credential types are fully masked."""
    config = {
        "api_key": "sk-1234567890",
        "email": "admin@company.com",
        "database": {"password": "db_secret"},
        "cache": {"redis": {"password": "redis_secret"}},
    }

    masked_config = masker.mask_dict(config)

    assert masked_config["api_key"] == "***"
    assert masked_config["email"] == "***"
    assert masked_config["database"]["password"] == "***"
    assert masked_config["cache"]["redis"]["password"] == "***"

    # verify that dumping after conversion with mask_dict returns the same as masking after dumping with mask_text
    masked_text = masker.mask_text(json.dumps(config)).replace('"', "'")
    assert masked_text == str(masked_config)

    logger.debug(config)  # masks and logs the dictionary to caplog
    assert masked_text in caplog.text


def test_api_config_with_non_string_keys(masker, caplog):
    """Verifies that configurations with non-string keys will be successfully skipped where required."""
    config = {1: "ignored", "nested": {"api_key": "masked"}}

    masked_text = masker.mask_text(json.dumps(config))
    assert masked_text == json.dumps(masker.mask_dict(config))

    logger.debug(config)  # masks and logs the dictionary to caplog

    assert (
        masked_text.replace('"1"', "1").replace('"', "'") in caplog.text
    )  # 1 is automatically transformed into "1" (string formatted)


def test_exception_traceback_masking(caplog):
    """Verifies that sensitive data in exception tracebacks is masked."""
    api_key = "sk-12345secret"

    try:
        # Simulate an exception that includes the credential in the traceback
        def function_with_credential():
            api_key_local = api_key
            raise ValueError(f"Failed to connect: `api_key: {api_key_local}`")

        function_with_credential()
    except ValueError:
        # Log the exception with traceback
        logger.exception("An error occurred")

    # Verify that the credential is masked in the log output
    assert api_key not in caplog.text
    assert "***" in caplog.text


def test_url_masking_with_failed_config(caplog):
    mock_value = str(uuid.uuid4())
    url = f"https://example url.com?api_key={mock_value}"

    with pytest.raises(ValueError) as excinfo:
        # will find a space in the URL and raise an error - api key should be logged:
        _ = validate_and_process_url(url)

    logger.exception(excinfo.value)
    assert "***" in caplog.text and str(mock_value) not in caplog.text
