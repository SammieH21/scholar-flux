import pytest
from pydantic import SecretStr, BaseModel, Field
from random import randint
from dataclasses import dataclass, field
from scholar_flux import logger
from collections import deque
from typing import Callable
import json
import re
import uuid
from scholar_flux.security import (
    MaskingPattern,
    MaskingPatternSet,
    KeyMaskingPattern,
    FuzzyKeyMaskingPattern,
    StringMaskingPattern,
    SensitiveDataMasker,
)
from scholar_flux import masker
from scholar_flux.utils import generate_repr


class MockInputs(BaseModel):
    url: str = "https://mock-example.url.com"
    api_key: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: str = "mock@email.com"


@dataclass
class MockConfig:
    host: str = "localhost"
    password: str = field(default_factory=lambda: str(uuid.uuid4()))
    api_key: str = field(default_factory=lambda: "sk-" + str(randint(1000000, 9999999)))


class MockConfigWithMasking(BaseModel):
    """Integrates the repr with automatic string masking."""

    host: str = "127.0.0.1"
    password: str = Field(default_factory=lambda: str(uuid.uuid4()))
    api_key: str = Field(default_factory=lambda: "sk-" + str(randint(1000000, 9999999)))

    @masker.mask_output(convert_objects=True)
    def __repr__(self) -> str:
        """Repr that uses a masker to mask sensitive fields"""
        myrepr = generate_repr(self, flatten=True)
        return myrepr


@pytest.fixture
def mock_pydantic_model() -> MockInputs:
    return MockInputs()


def test_initialization():
    """Verifies that the sensitive data masker is populated with masking defaults only if `register_defaults=True."""
    masker = SensitiveDataMasker(register_defaults=True)
    assert masker.patterns

    masker = SensitiveDataMasker(register_defaults=False)
    assert not masker.patterns


def test_basic_string_pattern():
    """Verifies that basic string patterns can be redacted by defining the masking pattern with associated options."""
    masker = SensitiveDataMasker(register_defaults=False)
    masking_text = "<redacted>"
    password = "paxw0rD"
    string_pattern = StringMaskingPattern(name="birthdate", pattern=password, replacement=masking_text, use_regex=False)
    masker.add_pattern(string_pattern)

    assert masker.mask_text(password) == masking_text
    string = f"My password is {password}. Please keep this secure"
    masked_string = string.replace(password, masking_text)
    assert masker.mask_text(string) == masked_string


def test_regex_string_pattern():
    """Verifies that regular expressions can be masked from text using regular expressions to identify text to mask."""
    masker = SensitiveDataMasker(register_defaults=False)
    masking_text = "<redacted>"
    string_pattern = StringMaskingPattern(name="birthdate", pattern=r"\d\d\d\d-\d\d-\d\d", replacement=masking_text)
    masker.add_pattern(string_pattern)

    birthdate = "1863-05-25"
    assert masker.mask_text(birthdate) == masking_text
    string = f"He was born in {birthdate} on a sunny day"
    masked_string = string.replace(birthdate, masking_text)
    assert masker.mask_text(string) == masked_string


def test_secret_string_pattern():
    """Verifies that `SecretStr` types and partially masked strings are fully masked by the SensitiveDataMasker."""
    masker = SensitiveDataMasker(register_defaults=True)

    # smoke check: Verifies that stray, partially masked secret strings don't exist in the log
    assert masker.mask_text("SecretStr(**********)") == "**********"
    assert masker.mask_text("***(**********)") == "**********"
    assert masker.mask_value(SecretStr("**********"), convert_objects=True) == "**********"  # auto converted via `str`


def test_split_pattern_with_escaped_pipe():
    """Verifies that pattern splitting is only performed when pipes in patterns are not escaped."""
    pattern = r"a|b\|c"
    expected_split_pattern = ["a", r"b\|c"]
    assert expected_split_pattern == KeyMaskingPattern._split_pattern(pattern)

    pattern_two = r"|_/\|_|op"
    expected_split_pattern_two = ["", r"_/\|_", "op"]
    assert expected_split_pattern_two == KeyMaskingPattern._split_pattern(pattern_two)

    pattern_three = "generic_field"
    assert [pattern_three] == KeyMaskingPattern._split_pattern(pattern_three)


def test_fuzzy_key_pattern():
    """Verifies that fuzzy field matching can be performed to mask unknown, fuzzy fields before entry."""
    masker = SensitiveDataMasker(register_defaults=False)
    masking_text = "<redacted>"
    fuzzy_field_pattern = "[a-z_]*birth[a-z_]*|dob|[a-z_]*bday[a-z_]*|[a-z_]*born"
    fuzzy_key_pattern = FuzzyKeyMaskingPattern(
        name="birthdate", field=fuzzy_field_pattern, pattern=r"\d\d\d\d-\d\d-\d\d", replacement=masking_text
    )
    masker.add_pattern(fuzzy_key_pattern)

    birthday_keys = ["birthday", "birth", "date_of_birth", "dob", "my_dob", "my_bday", "date_born"]
    test_dictionary = {key: "1122-34-56" for key in birthday_keys}
    birthday_json = json.dumps(test_dictionary)
    masked_json = masker.mask_text(birthday_json)
    loaded_masked_dictionary = json.loads(masked_json)
    assert loaded_masked_dictionary == {key: masking_text for key in birthday_keys}


def test_fuzzy_fixed_values_pattern():
    """Verifies that fixed-value string masking works as expected while fuzzy key string matching finds fuzzy fields."""
    masking_text = "<redacted>"
    fuzzy_field_pattern = "[Rr]ed|[Bb]lue|[Gg]reen"

    # an impossible regex pattern - the end can never come before the beginning
    fixed_value = "$^"
    test_dictionary = {"red": fixed_value, "Green": fixed_value, "blue": fixed_value}
    color_json = json.dumps(test_dictionary)

    fuzzy_key_pattern = FuzzyKeyMaskingPattern(
        name="base-colors", field=fuzzy_field_pattern, pattern=fixed_value, replacement=masking_text, use_regex=False
    )
    masked_color_json = fuzzy_key_pattern.apply_masking(color_json)
    redacted_dictionary = json.loads(masked_color_json)
    assert redacted_dictionary.keys() == test_dictionary.keys()
    assert fixed_value not in masked_color_json and all(value == masking_text for value in redacted_dictionary.values())


def test_sensitive_key_pattern_type():
    """Verifies that the masker uses fuzzy field matching when `fuzzy=True` and, otherwise, uses a KeyMaskingPattern."""
    masker = SensitiveDataMasker(register_defaults=False)

    masker.add_sensitive_key_patterns(name="test", fields=["test_key1", "test_key2"], fuzzy=True)
    assert all(isinstance(pattern, FuzzyKeyMaskingPattern) for pattern in masker.get_patterns_by_name("test"))
    masker.remove_pattern_by_name(name="test")

    masker.add_sensitive_key_patterns(name="test", fields=["test_key1", "test_key2"], fuzzy=False)
    assert all(
        isinstance(pattern, KeyMaskingPattern) and not isinstance(pattern, FuzzyKeyMaskingPattern)
        for pattern in masker.get_patterns_by_name("test")
    )


def test_basic_key_pattern():
    """Validates that key-value pairs that indicate patterns to mask will successfully trigger when encountering strings
    containing the matching pattern."""
    masker = SensitiveDataMasker(register_defaults=False)
    masking_text = "<redacted>"
    birthdate = r"[0-9][0-9][0-9][0-9]-[0-9][0-9]?-[0-9][0-9]?|[0-9][0-9]?-[0-9][0-9]?-[0-9][0-9][0-9][0-9]"
    fields = ["dob", "birthdate", "birthday"]
    string_patterns = {
        KeyMaskingPattern(name="birthdate", field=field, pattern=birthdate, replacement=masking_text)
        for field in fields
    }
    masker.update(string_patterns)
    masked_parameters = json.dumps({field: masking_text for field in fields}).strip()
    parameters = json.dumps({field: "5-12-2024" for field in fields})
    parameters2 = json.dumps({field: "2024-05-12" for field in fields})

    assert masker.mask_text(parameters) == masked_parameters
    assert masker.mask_text(parameters2) == masked_parameters

    # testing selective filtering, only the last should be when regex turned off
    parameters3 = json.dumps(dict(zip(fields, ("aaaaa", "abcde", "ab.*e"))))
    parameters_masked3 = json.dumps(dict(zip(fields, ("aaaaa", "abcde", "***"))))

    masker.add_sensitive_key_patterns(name="no_regex", fields=fields, pattern="ab.*e", use_regex=False)

    assert masker.mask_text(parameters3) == parameters_masked3


def test_encryption_key_masking():
    """Verifies that encryption keys are never logged."""
    masker = SensitiveDataMasker(register_defaults=False)

    # Register encryption key pattern
    encryption_key = "fernet_key_base64_encoded_32_bytes_xxxxxxxxxxxxxx"
    masker.add_sensitive_string_patterns(name="encryption_keys", patterns=[encryption_key], use_regex=False)

    log_message = f"Using encryption key: {encryption_key}"
    masked = masker.mask_text(log_message)
    assert encryption_key not in masked
    assert masked == "Using encryption key: ***"


def test_pattern_removal():
    """Validates whether patterns can be removed as intended by the name associated with the pattern."""
    masker = SensitiveDataMasker(register_defaults=True)
    assert masker.get_patterns_by_name("api_key") is not None
    masker.remove_pattern_by_name("api_key")
    assert not masker.get_patterns_by_name("api_key")


def test_factory_key_patterns():
    """Validates whether key patterns can be initialized without defining the underlying KeyMaskingPattern upfront."""
    masker = SensitiveDataMasker(register_defaults=False)

    # lists and strings should work in this scenario:
    masker.add_sensitive_key_patterns(name="api_key", fields=["api_key"])
    masker.add_sensitive_key_patterns(name="api_key", fields="API_KEY")

    string = '{"api_key": "abcd1234", "API_KEY": "abcd5432"}'
    masked_string = '{"api_key": "***", "API_KEY": "***"}'
    assert masker.mask_text(string) == masked_string

    masker.add_sensitive_string_patterns(name="string_match", patterns="[pP][aA][sS][sS](:|=) *1234")

    assert masker.mask_text("here is my password: pass: 1234") == "here is my password: ***"


def test_secret_masking():
    """Ensures that secrets can be masked and unmasked when required based on whether or not the key is already a secret
    string.

    When non-secrets are entered into `unmask_secret`, they should be returned as is.

    Conversely, with `mask_secret`, non-secrets, unless None, should be coerced into secrets if not already a secret.
    Otherwise, secrets should be returned as is.

    The `register_secret_if_exists` method is also tested and expected to work similarly:
        With a secret as input, the value of the secret will be added as a masked text patterns and return True.
        Otherwise, no patterns are added, and False is returned to signify that nothing was added.

    """
    masker = SensitiveDataMasker(register_defaults=False)
    assert masker.mask_secret(None) is None
    assert masker.mask_secret("") == SecretStr("")
    assert masker.unmask_secret(masker.mask_secret("")) == masker.unmask_secret(SecretStr(""))
    assert masker.unmask_secret(None) is None

    a_secret = SecretStr("plaintext_password")
    a_non_secret = "plaintext_info"

    assert not masker.register_secret_if_exists(field="another_secret", value=a_non_secret, name="non_secret")
    assert not masker.get_patterns_by_name("non_secret")

    assert masker.register_secret_if_exists(field="a_secret", value=a_secret, name="new_secret")
    new_secret = list(masker.get_patterns_by_name("new_secret"))
    assert new_secret and isinstance(new_secret[0].pattern, SecretStr) and new_secret[0].pattern == a_secret

    masker.add_sensitive_string_patterns(name="new_secret", patterns=[a_secret.get_secret_value()], use_regex=False)

    assert masker.mask_text(None) is None and masker.mask_text(1) == 1  # type:ignore


def test_repr():
    """Verifies that the patterns shown in the SensitiveDataMasker's representation are masked and not directly
    shown."""
    masker = SensitiveDataMasker(register_defaults=True)
    assert repr(masker) == "SensitiveDataMasker(patterns=MaskingPatternSet(...))"

    # when no patterns are added, the `...` won't be present
    masker = SensitiveDataMasker(register_defaults=False)
    assert repr(masker) == "SensitiveDataMasker(patterns=MaskingPatternSet())"


def test_masking_pattern_abc():
    """Tests the underlying MaskingPattern parent class to verify the implementation of the underlying methods used to
    compare patterns, hashes, and `_identity_key` methods."""
    string_pattern = StringMaskingPattern(name="abstract testing", pattern="abc")
    key_pattern = KeyMaskingPattern(name="abstract testing", field="subclassing", pattern="abc")

    assert MaskingPattern.apply_masking(string_pattern, "placeholder") is None
    assert isinstance(MaskingPattern.__hash__(string_pattern), int)
    assert MaskingPattern.__eq__(string_pattern, string_pattern) is True
    assert MaskingPattern.__eq__(string_pattern, 1) is False
    assert MaskingPattern.__eq__(string_pattern, key_pattern) is False
    assert MaskingPattern._identity_key(string_pattern) is None


def test_pattern_identity():
    """Validates whether the identity_key correctly identifies StringMaskingPatterns and KeyMaskingPatterns based on
    their respective configuration.

    StringMaskingPatterns should be identifiable based their assigned names and the secret values of their patterns.

    KeyMaskingPatterns should be identifiable based on the name assigned to a pattern, the associated field (or key)
    indicating the pattern to mask, and the secret values of their patterns.

    """
    string_pattern = StringMaskingPattern(name="abstract testing", pattern="abc")
    key_pattern = KeyMaskingPattern(name="key_patterns", field="identity", pattern="abc")
    assert string_pattern._identity_key() == f"('StringMaskingPattern', '{string_pattern.name}', '{string_pattern.pattern.get_secret_value()}')"  # type: ignore
    assert key_pattern._identity_key() == f"('KeyMaskingPattern', '{key_pattern.name}', '{key_pattern.field}', '{key_pattern.pattern.get_secret_value()}')"  # type: ignore


def test_pattern_set():
    """Validates whether, as intended, the `MaskingPatternSet` will correctly allow only patterns and otherwise raise a
    type error when encountering incorrect types."""
    string_pattern = StringMaskingPattern(name="abstract testing", pattern="abc")
    key_pattern = KeyMaskingPattern(name="key_patterns", field="identity", pattern="abc")
    pattern_set = MaskingPatternSet()

    pattern_set.add(key_pattern)
    pattern_set.update(string_pattern)  # type: ignore
    assert string_pattern in pattern_set

    item = 1
    with pytest.raises(TypeError) as excinfo:
        pattern_set.add(item)  # type: ignore
    assert f"Expected a MaskingPattern, got {type(item)}" in str(excinfo.value)

    item_tuple = (2,)
    with pytest.raises(TypeError) as excinfo:
        pattern_set.update((item_tuple,))  # type: ignore
    assert f"Expected a masking pattern, received type {type(item_tuple)}" in str(excinfo.value)


# ============================================================================
# Database URI Credential Masking Tests
#
# Validates credential masking for cache backend connection strings.
# Prevents accidental exposure of database credentials in logs when ScholarFlux
# cache storage backends are misconfigured or log their connection strings.
#
# Aligns with SECURITY.md sections:
#   - Lines 122-131: Database connection security
#   - Lines 58-111: Caching security and credential management
#   - Lines 195-200: Error handling and logging security
#
# ScholarFlux data_storage backends (src/scholar_flux/data_storage/):
#   - SQLAlchemyStorage: PostgreSQL, MySQL, MariaDB, SQLite (via SQLAlchemy)
#   - DuckDBStorage: DuckDB (dedicated subclass of SQLAlchemyStorage)
#   - RedisStorage: Redis (dict-based config: host, port, password)
#   - MongoStorage: MongoDB (URI and dict-based configs)
#
# Coverage patterns:
#   1. URI-based config: postgresql://user:pass@host:5432/db
#   2. Dict-based config: {"host": "localhost", "password": "secret"}
#   3. Query strings: motherduck_token=abc123 (DuckDB alternative)
# ============================================================================


@pytest.mark.parametrize(
    "uri,expected",
    [
        # PostgreSQL variants
        ("postgresql://myuser:secretpass@localhost:5432/mydb", "postgresql://myuser:***@localhost:5432/mydb"),
        ("postgres://admin:p@ssw0rd!@db.example.com/production", "postgres://admin:***@db.example.com/production"),
        ("postgresql+asyncpg://user:secret123@host/db", "postgresql+asyncpg://user:***@host/db"),
        ("postgres+psycopg2://admin:hunter2@localhost/app", "postgres+psycopg2://admin:***@localhost/app"),
        # MySQL/MariaDB variants
        ("mysql://root:password123@localhost:3306/scholar_cache", "mysql://root:***@localhost:3306/scholar_cache"),
        (
            "mysql+pymysql://app_user:secretpass@db.example.com:3306/production",
            "mysql+pymysql://app_user:***@db.example.com:3306/production",
        ),
        ("mysql+mysqlconnector://user:pass@localhost/testdb", "mysql+mysqlconnector://user:***@localhost/testdb"),
        (
            "mariadb+pymysql://admin:mariapass@mariadb.host.com/mydb",
            "mariadb+pymysql://admin:***@mariadb.host.com/mydb",
        ),
        # MongoDB variants
        ("mongodb://admin:secretpass@mongo.example.com:27017/mydb", "mongodb://admin:***@mongo.example.com:27017/mydb"),
        (
            "mongodb+srv://user:atlaspass@cluster0.abc123.mongodb.example.com:27017/adb",
            "mongodb+srv://user:***@cluster0.abc123.mongodb.example.com:27017/adb",
        ),
        # Redis variants
        ("redis://default:myredispass@redis.example.com:6379/0", "redis://default:***@redis.example.com:6379/0"),
        ("redis://:cachepassword@redis.example.com:6379/0", "redis://:***@redis.example.com:6379/0"),
        # DuckDB
        ("duckdb://user:duckpass@localhost/analytics", "duckdb://user:***@localhost/analytics"),
        # Special characters in password
        ("postgresql://user:P@ssw0rd!#$%@localhost:5432/db", "postgresql://user:***@localhost:5432/db"),
        ("mysql://user:p%40ss%3Aword@localhost/db", "mysql://user:***@localhost/db"),
        # IPv6 hosts (bracketed notation per RFC 2732)
        ("postgresql://user:secret@[::1]:5432/db", "postgresql://user:***@[::1]:5432/db"),
        ("postgresql://user:secret@[2001:db8::1]:5432/db", "postgresql://user:***@[2001:db8::1]:5432/db"),
        ("redis://default:pass@[::1]:6379/0", "redis://default:***@[::1]:6379/0"),
        ("mongodb://admin:mongopass@[fe80::1]:27017/mydb", "mongodb://admin:***@[fe80::1]:27017/mydb"),
    ],
)
def test_database_uri_password_masking(uri, expected):
    """Verifies credentials are masked for ScholarFlux's supported cache backends.

    Tests URI-based credential masking for all data_storage backends:
      - SQLAlchemyStorage: PostgreSQL, MySQL, MariaDB, SQLite
      - DuckDBStorage: DuckDB
      - RedisStorage: Redis
      - MongoStorage: MongoDB

    This prevents accidental credential exposure when storage URIs are logged
    during initialization, configuration errors, or debug output.

    """
    masker = SensitiveDataMasker(register_defaults=True)
    assert masker.mask_text(uri) == expected


def test_motherduck_token_masking():
    """Verifies that MotherDuck tokens in query strings are masked.

    MotherDuck is a serverless DuckDB alternative. When querying MotherDuck, authentication tokens appear in query
    strings and must not leak into logs. This complements URI-based credential masking for DuckDB backends.

    """
    masker = SensitiveDataMasker(register_defaults=True)

    # Token in query string
    uri = "md:my_database?motherduck_token=eyJhbGciOiJIUzI1NiJ9.secret"
    masked = masker.mask_text(uri)
    assert masked == "md:my_database?motherduck_token=***"

    # Token with additional parameters
    uri = "md:db?motherduck_token=abc123&read_only=true"
    masked = masker.mask_text(uri)
    assert masked == "md:db?motherduck_token=***&read_only=true"


def test_uri_without_password_unchanged():
    """Verifies that storage URIs without credentials are not modified by masking.

    Ensures the masker doesn't incorrectly transform valid URIs that don't contain password fields, which could occur
    during storage backend initialization.

    """
    masker = SensitiveDataMasker(register_defaults=True)

    # No password in URI
    uri = "postgresql://localhost:5432/mydb"
    assert masker.mask_text(uri) == uri

    # User but no password
    uri = "postgres://user@localhost/db"
    assert masker.mask_text(uri) == uri


def test_uri_in_json_context():
    """Verifies that storage URIs embedded in JSON structures are properly masked.

    Covers the scenario where storage configuration or URIs are serialized to JSON (e.g., in configuration files, debug
    output, or log records) and must have credentials masked to prevent exposure.

    """
    masker = SensitiveDataMasker(register_defaults=True)

    config = json.dumps({"database_url": "postgresql://app:secret@db.host.com/prod"})
    masked = masker.mask_text(config)
    expected = json.dumps({"database_url": "postgresql://app:***@db.host.com/prod"})
    assert masked == expected


@pytest.mark.parametrize(
    "config,secret",
    [
        # Redis JSON config
        ('{"host": "redis.example.com", "port": 6379, "password": "my_redis_secret", "db": 0}', "my_redis_secret"),
        # Redis Python dict repr
        ("{'host': 'localhost', 'port': 6379, 'password': 'secret123'}", "secret123"),
        # MongoDB config dict
        ('{"host": "mongo.example.com", "port": 27017, "password": "mongo_secret_pass"}', "mongo_secret_pass"),
        # PostgreSQL config dict
        ("{'host': 'localhost', 'port': 5432, 'password': 'pg_secret', 'dbname': 'mydb'}", "pg_secret"),
    ],
)
def test_database_config_dict_password_masking(config, secret):
    """Verifies that passwords in storage backend dict/JSON configs are properly masked.

    Storage backends accept dict-based configurations with separate host, port, and password fields
    (RedisStorage, MongoStorage) or may be logged in repr() format. This test ensures passwords
    in these configurations are masked when they appear in logs, error messages, or debug output.

    Example scenarios:
      - Logging storage initialization parameters
      - Displaying configuration in error messages
      - Debug output showing backend connection details

    """
    masker = SensitiveDataMasker(register_defaults=True)
    masked = masker.mask_text(config)
    assert secret not in masked


def test_database_uri_in_configuration_context():
    """Verifies that database URIs with password credentials are masked when embedded in config strings or logs.

    ScholarFlux may log or display storage backend configuration in various formats:
      - Environment variable exports
      - Python code assignments
      - YAML/config file representations
      - Debug or error output

    This test ensures credentials are masked across these different contexts.

    """
    masker = SensitiveDataMasker(register_defaults=True)

    # Environment variable export
    config = "export DATABASE_URL=postgresql://app:secretpass@db.prod.com:5432/analytics"
    masked = masker.mask_text(config)
    assert "secretpass" not in masked
    assert masked == "export DATABASE_URL=postgresql://app:***@db.prod.com:5432/analytics"

    # Python code assignment
    code = 'connection_string = "mysql+pymysql://root:password123@localhost/cache"'
    masked = masker.mask_text(code)
    assert "password123" not in masked
    assert 'connection_string = "mysql+pymysql://root:***@localhost/cache"' in masked

    # YAML-style configuration with Redis password-only format
    yaml_config = "database:\n  url: redis://:redispass@redis.example.com:6379/0\n  timeout: 30"
    masked = masker.mask_text(yaml_config)
    assert "redispass" not in masked
    assert "redis://:***@redis.example.com:6379/0" in masked


def test_multiple_credential_types_in_single_text():
    """Verifies that multiple credential types are all masked correctly in a single log/output block.

    ScholarFlux logs could otherwise contain multiple types of credentials:
      - Storage backend URIs (database, cache)
      - API keys (for academic providers)
      - Bearer tokens (API authentication)
      - Email addresses (for polite pool access)

    This test ensures all credential types are masked simultaneously without false positives or credential bleeding.

    """
    masker = SensitiveDataMasker(register_defaults=True)

    # Simulate a log message with multiple credential types in key-value format
    log_message = """
    Connecting to database: postgresql://admin:dbpass123@db.host.com:5432/prod
    Config: {"api_key": "sk-1234567890abcdef", "email": "researcher@institution.edu"}
    Redis cache: redis://:cachepass@cache.host.com:6379/0
    Auth header: Authorization: Bearer abc123xyz789
    """

    masked = masker.mask_text(log_message)

    # Verify database credentials are masked
    assert "dbpass123" not in masked
    assert "postgresql://admin:***@db.host.com:5432/prod" in masked

    # Verify API key is masked (key-value pattern)
    assert "sk-1234567890abcdef" not in masked

    # Verify Redis password is masked
    assert "cachepass" not in masked
    assert "redis://:***@cache.host.com:6379/0" in masked

    # Verify auth header is masked
    assert "abc123xyz789" not in masked
    assert "Authorization: Bearer ***" in masked


# ============================================================================
# Credential Exfiltration Prevention Tests
#
# Verifies credential masking in common exfiltration vectors where sensitive data might leak through logs, error
# messages, or monitoring systems when AI is involved. While this might not be a problem for the intended use of
# ScholarFlux, better safe than sorry.
# Note: If this ever becomes a possible issue in practice, the user might have bigger problems elsewhere to patch.
#
#   - Lines 195-200: Error handling and logging security
#   - Lines 40-56: API key management and secure configuration
#   - Lines 201-207: Network security considerations
#
# Common exfiltration vectors covered by ScholarFlux's masker:
#   - URL query parameters: token, api_key, secret, password, access_token
#   - Private key headers: RSA, EC, DSA, OpenSSH, PGP, encrypted keys
#   - Authorization headers: Bearer tokens
#
# These tests prevent accidental credential exposure through:
#   - Application logs and console output
#   - Error stack traces and debug messages
#   - Monitoring and observability platforms
#   - Third-party logging services
# ============================================================================


# Verifies that credentials in URLs are not displayed when Logged
@pytest.mark.parametrize(
    "param_name", ["token", "access_token", "session_token", "auth_token", "api_key", "apikey", "secret", "password"]
)
def test_url_query_string_secrets(param_name):
    """Verifies that secrets in URL query parameters are masked.

    Query parameters are commonly used to pass authentication tokens and API keys to external services. If these URLs
    are logged, credentials could be exposed. This test ensures all common query parameter credential types are masked.

    """
    masker = SensitiveDataMasker(register_defaults=True)
    url = f"https://api.example.com?{param_name}=secret123"
    assert masker.mask_text(url) == f"https://api.example.com?{param_name}=***"


def test_url_query_secrets_with_other_params():
    """Verifies that secrets are masked while preserving other query parameters."""
    masker = SensitiveDataMasker(register_defaults=True)

    url = "https://api.example.com?page=1&token=secret&limit=10"
    masked = masker.mask_text(url)
    assert masked == "https://api.example.com?page=1&token=***&limit=10"


@pytest.mark.parametrize(
    "key_type",
    [
        "RSA PRIVATE KEY",
        "PRIVATE KEY",
        "OPENSSH PRIVATE KEY",
        "EC PRIVATE KEY",
        "ENCRYPTED PRIVATE KEY",
        "DSA PRIVATE KEY",
        "PGP PRIVATE KEY",
    ],
)
def test_private_key_header_masking(key_type):
    """Verifies that private key headers are masked to prevent key exposure.

    While ScholarFlux doesn't touch ssh keys whatsoever, these tests are meant to provide a line of defense against the
    possibility of exfiltration.

    """
    masker = SensitiveDataMasker(register_defaults=True)
    text = f"Found key: -----BEGIN {key_type}-----"
    assert "***PRIVATE_KEY_REDACTED***" in masker.mask_text(text)


# ============================================================================
# List Masking Tests
# ============================================================================


@pytest.mark.parametrize("sequence_class", (list, tuple, set, deque))
def test_mask_sequence_with_urls(sequence_class):
    """Tests that lists and tuples are masked and converted into a masked list containing URLs with API keys."""
    masker = SensitiveDataMasker(register_defaults=True)
    urls = (
        "https://api.example.com?api_key=secret123",
        "https://normal.com/path",
    )
    expected = sequence_class(
        [
            "https://api.example.com?api_key=***",
            "https://normal.com/path",
        ]
    )
    masked = masker.mask_value(sequence_class(urls))
    assert masked == expected


def test_mask_list_with_nested_config_dicts():
    """Tests that the masker correctly masks dictionary data nested sensitive data within lists."""
    masker = SensitiveDataMasker(register_defaults=True)
    configs = [
        {"host": "localhost", "password": "secret123"},
        {"api_key": "sk-1234567890"},
    ]
    expected = [
        {"host": "localhost", "password": "***"},
        {"api_key": "***"},
    ]
    masked = masker.mask_list(configs)
    assert masked == expected


def test_mask_list_with_nested_mixed_structures():
    """Tests that `masker.mask_list` correctly masks strings within nested dictionaries and nested lists."""
    masker = SensitiveDataMasker(register_defaults=True)
    data = [
        {"config": {"password": "nested_secret"}},
        ["https://api.com?token=key123", {"email": "test@example.com"}],
    ]
    expected = [
        {"config": {"password": "***"}},
        ["https://api.com?token=***", {"email": "***"}],
    ]
    masked = masker.mask_list(data)
    assert masked == expected


def test_masking_with_pydantic_input_structures(mock_pydantic_model):
    """Verifies that representations of pydantic input structures are masked of sensitive data when via `masker.mask_text"""
    masker = SensitiveDataMasker(register_defaults=True)
    expected = "MockInputs(url='https://mock-example.url.com', api_key='***', email='***')"
    assert expected == masker.mask_text(repr(mock_pydantic_model))


def test_mask_list_returns_input_for_non_sequence():
    """Tests that `masker.mask_list` outputs the exact structure that is given if it is not a list or tuple."""
    masker = SensitiveDataMasker(register_defaults=True)
    assert masker.mask_list("not a list") == "not a list"  # type: ignore
    assert masker.mask_list(42) == 42  # type: ignore
    assert masker.mask_list(None) is None  # type: ignore


def test_mask_value_with_tuple():
    """Tests that tuples are recursively masked, only modifying nested sensitive data."""
    masker = SensitiveDataMasker(register_defaults=True)
    data = ({"password": "secret"}, "https://api.com?token=key123")
    masked = masker.mask_value(data)
    assert isinstance(masked, tuple)
    assert masked[0]["password"] == "***"
    assert "key123" not in masked[1] and "token=***" in masked[1]


def test_filter_masks_pydantic_model(mock_pydantic_model, caplog):
    """Tests that the representations of pydantic models that are logged directly are also masked internally."""
    from scholar_flux import logger

    logger.info(mock_pydantic_model)
    assert "mockapikey" not in caplog.text
    assert "mock@email.com" not in caplog.text
    assert "api_key='***'" in caplog.text
    assert "email='***'" in caplog.text


def test_filter_masks_dataclass(caplog):
    """Tests that the representations of dataclasses that are logged directly are also masked internally."""
    from scholar_flux import logger

    config = MockConfig()

    mock_key_type = "api_key"  # avoid CodeQL flags
    pattern = "'sk-[0-9]{7}'"

    logger.info(config)
    assert not re.search(f"{mock_key_type}={pattern}", caplog.text)  # filter for `sk + 7 digit key`
    assert "password='***'" in caplog.text
    assert "api_key='***'" in caplog.text
    assert "host='localhost'" in caplog.text


def test_nested_object_masking(caplog):
    """Verifies that pydantic models that are nested within lists and dicts are recursively masked when encountered."""
    mock_key_type = "secret_key"  # avoid CodeQL flags

    mock_inputs = {"storage": "MockStorage", "config": MockConfig(), mock_key_type: uuid.uuid4()}
    logger.info(mock_inputs)
    assert not re.search("'secret_key': '[a-z0-9-]+'", caplog.text)  # filter for
    assert "password='***'" in caplog.text
    assert "api_key='***'" in caplog.text
    assert "host='localhost'" in caplog.text
    assert "'storage': 'MockStorage'" in caplog.text
    assert "'secret_key': '***'" in caplog.text


@pytest.mark.parametrize(
    "mock_key",
    (
        SecretStr("secret"),
        {"api_key": SecretStr(str(uuid.uuid4()))},
        ["this", "has", "a", SecretStr(str(uuid.uuid4()))],
    ),
)
def test_secret_string_stays_masked(mock_key, caplog):
    """Verifies that `SecretStr` stay fully masked in logs, given that they should already be masked to begin with."""
    masker = SensitiveDataMasker(register_defaults=True)
    # Retrieves the pattern for masking SecretStr('**********') implementations
    pattern = masker.unmask_secret(list(masker.get_patterns_by_name("SecretStr"))[0].pattern)

    # Verifies masking behavior on different types before and after string conversion
    logger.info(mock_key)

    # Verifies that the pattern for secret strings doesn't appear in the logs:
    assert re.search(pattern, caplog.text) is None and "***" in caplog.text


def test_masking_decorator_filters_sensitive_patterns():
    """Verifies that the `masker.mask_output` decorator correctly masks output when required.

    This uses the package-level masker to verify the behavior of `mask_output` when directly used
    and on using decorators

    """
    config = MockConfig()
    config_representation = masker.mask_output(convert_objects=True)(config.__repr__)  # type: ignore

    assert config_representation() == f"MockConfig(host='{config.host}', password='***', api_key='***')"

    masking_config = MockConfigWithMasking()
    assert repr(masking_config) == f"MockConfigWithMasking(host='{masking_config.host}', password='***', api_key='***')"


def test_mask_output_preserves_function_metadata():
    """Verifies that the mask_output decorator preserves function metadata via @wraps."""

    def return_sensitive_data(config: dict) -> dict:
        """Function used to verify the behavior of `masked_output: Returns a basic configuration with sensitive data."""
        return config

    decorated: Callable = masker.mask_output(convert_objects=True)(return_sensitive_data)

    # Verify metadata preservation
    assert decorated.__name__ == "return_sensitive_data"
    assert decorated.__doc__ == (
        """Function used to verify the behavior of `masked_output: Returns a basic configuration with sensitive data."""
    )
    assert "config" in str(decorated.__annotations__)
    assert decorated.__annotations__["return"] == dict
