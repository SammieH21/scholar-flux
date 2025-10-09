import scholar_flux.sessions.session_manager as sm
from scholar_flux.sessions import EncryptionPipelineFactory
import pytest
from pathlib import Path
import os
import importlib.util


@pytest.fixture(scope="session")
def default_cache_directory():
    """Helper fixture that indicates where mocked data and persistent test caching data will be stored"""
    return Path(__file__).resolve().parent.parent / "mocks"


@pytest.fixture(scope="session")
def default_cache_filename():
    """The filename to use when creating a new session that caches raw requests using the filesystem"""
    return "testing_session_cache"


@pytest.fixture(scope="session")
def default_seconds_cache_expiration():
    """
    Defines the time interval in seconds that should elapse before previously cached requests expire. Cached
    requests are set to expire after 1 second to more quickly validate cache invalidation settings during testing.
    """
    return 1


@pytest.fixture(scope="session")
def default_backend():
    """Indicates the default backend that should be used when testing cache settings"""
    return "sqlite"


@pytest.fixture(scope="session")
def default_cache_session_manager(
    default_cache_filename, default_cache_directory, default_seconds_cache_expiration, default_backend
):
    """
    Creates a cached session manager that can create a new session from the settings defined in the following fixtures:
        - default_cache_filename: Indicates the name of the cached session
        - default_cache_directory: Indicates where cache should be stored in the case of filesystem/sqlite cache
        - default_seconds_cache_expiration: Indicates how long to wait before previously cached requests are invalidated
        - default_backend:  Indicates the backend to use for caching - SQLite by default
    """

    return sm.CachedSessionManager(
        user_agent="test_session",
        cache_name=default_cache_filename,
        cache_directory=default_cache_directory,
        expire_after=default_seconds_cache_expiration,
        backend=default_backend,
    )


@pytest.fixture(scope="session")
def default_cache_session(default_cache_session_manager):
    """
    Initializes a cached session using the previously defined defaults previously specified when creating a
    `default_cache_session_manager` factory class. By default, this session uses sqlite for backend request caching.
    """
    cached_session = default_cache_session_manager.configure_session()
    yield cached_session
    cached_session.cache.clear()


###############


@pytest.fixture(scope="session")
def default_encryption_cache_filename():
    """The filename to use when creating a cached session that encrypts raw responses"""
    return "testing_encrypted_session_cache"


@pytest.fixture(scope="session")
def default_encryption_serializer_pipeline():
    """
    Returns a EncryptionPipelineFactory class that is later used to create a new encryption serialization and
    deserialization pipeline if and only if the `cryptography` and `itsdangerous` package dependencies are installed.

    Otherwise pytest skips the creation of this fixture.
    """
    if not all(importlib.util.find_spec(pkg) for pkg in ("cryptography", "itsdangerous")):
        pytest.skip()
    return EncryptionPipelineFactory


@pytest.fixture(scope="session")
def default_secret_key():
    """
    Default secret key to use for both encrypting and caching responses from API providers. The creation of this
    fixture is skipped when `cryptography` package is not available.
    """
    if not importlib.util.find_spec("cryptography"):
        pytest.skip()

    from cryptography.fernet import Fernet

    return Fernet.generate_key()


@pytest.fixture(scope="session")
def default_secret_salt():
    """Default secret salt to use when encrypting and caching responses from API providers with a cached session"""
    return os.urandom(16)


@pytest.fixture(scope="session")
def incorrect_secret_key():
    """
    Defines a new secret key to be used when simulating an attempt to access an encrypted cache storage that
    was instead created using the `default_secret_key` fixture.

    Attempts to access a encrypted session cache with the wrong key should fail and instead raise an InvalidToken error.
    """
    if not importlib.util.find_spec("cryptography"):
        pytest.skip()

    from cryptography.fernet import Fernet

    return Fernet.generate_key()


@pytest.fixture(scope="session")
def incorrect_secret_salt():
    """
    Secret salt to be used in combination with a secret key to create an encrypted cached session. This salt is
    used in subsequent tests to simulate an attempt to access a previously created encrypted cache with the
    wrong secret key.
    """
    secret_salt = os.urandom(18)
    return secret_salt


@pytest.fixture(scope="session")
def default_encryption_cache_session_manager(
    default_encryption_cache_filename,
    default_cache_directory,
    default_encryption_serializer_pipeline,
    default_secret_key,
    default_secret_salt,
):
    """
    Creates a new CachedSessionManager factory instance that, in turn, is used to generate a new cached session that
    encrypts cached requests. This fixture is used by the `default_encryption_cache_session` fixture in later testing 
    to verify that cache encryption works as intended.
    """
    if not default_encryption_serializer_pipeline:
        pytest.skip()

    create_serializer = default_encryption_serializer_pipeline(secret_key=default_secret_key, salt=default_secret_salt)
    return sm.CachedSessionManager(
        user_agent="test_session",
        cache_name=default_encryption_cache_filename,
        cache_directory=default_cache_directory,
        backend="memory",
        serializer=create_serializer(),
    )


@pytest.fixture(scope="session")
def default_memory_cache_session_manager():
    """
    Creates a minimal cached session manager factory instance that can be used to create an in-memory cache.
    """
    return sm.CachedSessionManager(
        user_agent="test_session",
        backend="memory",
    )


@pytest.fixture(scope="session")
def default_memory_cache_session(default_memory_cache_session_manager):
    """Creates a basic cached session manager that uses minimal settings for in-memory caching."""
    return default_memory_cache_session_manager()


@pytest.fixture(scope="session")
def incorrect_secret_salt_encryption_cache_session_manager(
    default_encryption_cache_filename,
    default_cache_directory,
    default_encryption_serializer_pipeline,
    incorrect_secret_key,
    incorrect_secret_salt,
):
    """
    Creates a new cached session manager for testing access to a previously created encrypted cache when using the
    wrong secret key. Used to verify error handling when an incorrect secret key is used to access encrypted request
    cache.
    
    Note that attempts to access a previously encrypted file cache/sqlite database with a different secret key than the
    original should then raise an error.

    Pytest will skip the creation of this fixture if the EncryptionPipelineFactory is not available due to missing
    `cryptography` and `itsdangerous` dependencies.
    """
    if not default_encryption_serializer_pipeline:
        pytest.skip()

    create_serializer = default_encryption_serializer_pipeline(
        secret_key=incorrect_secret_key, salt=incorrect_secret_salt
    )
    return sm.CachedSessionManager(
        user_agent="test_session",
        cache_name=default_encryption_cache_filename,
        cache_directory=default_cache_directory,
        backend="filesystem",
        serializer=create_serializer(),
    )


@pytest.fixture(scope="session")
def default_encryption_cache_session(default_encryption_cache_session_manager):
    """
    Creates a new encrypted cache session to later validate the encryption capability of the encryption pipeline
    serializer and deserializer.    
    """

    cached_session = default_encryption_cache_session_manager.configure_session()
    yield cached_session
    cached_session.cache.clear()
    path = default_encryption_cache_session_manager.cache_path
    if path and path.endswith("json"):
        os.remove(path)


@pytest.fixture(scope="session")
def sqlite_db_url():
    """
    Fixture that defines a location and SQLite DB file for storing processing cache. Used during response retrieval and
    processed response data storage tests to validate both raw and processed response caching capability.
    """
    sqlite_db_url = Path(__file__).resolve().parent.parent / "mocks/processing_cache.sqlite"
    return "sqlite:///" + str(sqlite_db_url)


__all__ = [
    "default_cache_session_manager",
    "default_cache_session",
    "default_seconds_cache_expiration",
    "default_backend",
    "default_cache_filename",
    "default_cache_directory",
    "default_memory_cache_session_manager",
    "default_memory_cache_session",
    "default_encryption_cache_session",
    "default_secret_salt",
    "default_secret_key",
    "default_encryption_cache_session_manager",
    "default_encryption_cache_filename",
    "default_encryption_serializer_pipeline",
    "incorrect_secret_key",
    "incorrect_secret_salt",
    "incorrect_secret_salt_encryption_cache_session_manager",
    "sqlite_db_url",
]
