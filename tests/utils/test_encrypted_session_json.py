import pytest
from unittest.mock import patch
from requests_cache.session import CachedSession
import requests_mock
from contextlib import suppress
import importlib
from scholar_flux.sessions import CachedSessionManager
import scholar_flux.sessions.encryption
from scholar_flux.api import SearchAPI
from scholar_flux.utils import config_settings
from scholar_flux.exceptions import (
    ItsDangerousImportError,
    CryptographyImportError,
    SecretKeyError,
    CachedSessionValidationError,
)
from pydantic import SecretStr

import logging

logger = logging.getLogger(__name__)

from scholar_flux.sessions.encryption import EncryptionPipelineFactory, Fernet
from base64 import b64encode, b64decode


@pytest.fixture(scope="session")
def skip_missing_encryption_dependency(session_encryption_dependency):
    if not session_encryption_dependency:
        pytest.skip("Missing encryption optional dependencies")


def test_validate_key_error():
    """Verifies that a SecretKeyError is raised when provided with an invalid secret key.

    When initialized with an argument for the `key` parameter, the `EncryptionPipelineFactory` validates that the
    object is a Fernet key. If the key is not a bytes object with a length of 44 characters, the `_validate_key`
    method will raise a SecretKeyError.

    """
    with pytest.raises(SecretKeyError):
        key = " " * 44
        EncryptionPipelineFactory._validate_key(key.encode())


def test_generate_secret_key(skip_missing_encryption_dependency):
    """Tests the generation of a new Fernet key and verifies the type.

    Fernet keys should be URL encoded bytes with a length: `len(fernet) == 44`

    """
    fernet = EncryptionPipelineFactory.generate_secret_key()
    assert isinstance(fernet, bytes) and len(fernet) == 44


def test_env_key_loader(skip_missing_encryption_dependency, caplog, restore_config_settings):
    """Validates whether the EncryptionPipelineFactory can load SCHOLAR_FLUX_CACHE_SECRET_KEY from the env settings."""
    # generates the secret key used for Fernet encryption/decryption
    fernet = EncryptionPipelineFactory.generate_secret_key()

    # simulates the fernet key being saved as a secret key in the config
    config_settings.set("SCHOLAR_FLUX_CACHE_SECRET_KEY", SecretStr(fernet.decode()))
    # verifies whether, when a fernet key is not provided, the secret key will be used by default
    factory = EncryptionPipelineFactory()
    assert "Using secret key from SCHOLAR_FLUX_CACHE_SECRET_KEY" in caplog.text
    # Verifies that _prepare_key is being called correctly on factory initialization
    assert fernet == factory.secret_key == EncryptionPipelineFactory._prepare_key(key=None)


def test_encryption_factory_secret_initialization(session_encryption_dependency):
    """Tests whether the initialization of a faulty and secret keys will raise the intended error.

    Also validates whether valid secret keys are successfully used in the EncryptionPipelineFactory

    """
    if not session_encryption_dependency:
        pytest.skip()

    faulty_secret_key = b"%this%a%bad%string%is%a%secret%key%%%%"

    with pytest.raises(SecretKeyError):
        faulty_b64_encoded_secret_key = b64encode(faulty_secret_key)
        EncryptionPipelineFactory(faulty_b64_encoded_secret_key)

    with pytest.raises(SecretKeyError):
        EncryptionPipelineFactory(123)  # type:ignore

    secret_key = b"%this%string%is%a%secret%key%%%%"
    byte44_encoded_secret_key = b64encode(secret_key)
    try:
        EncryptionPipelineFactory._validate_key(byte44_encoded_secret_key)
    except SecretKeyError as e:
        assert False, e

    factory = EncryptionPipelineFactory(byte44_encoded_secret_key, salt=None)
    assert isinstance(factory.fernet, Fernet)
    assert secret_key == b64decode(factory.secret_key)

    factory_with_str = EncryptionPipelineFactory(byte44_encoded_secret_key.decode("utf-8"), salt="")
    assert isinstance(factory_with_str.secret_key, bytes) and secret_key == b64decode(factory_with_str.secret_key)


def test_encryption_factory_key_assignment(skip_missing_encryption_dependency):
    """Verifies that encryption correctly handles the assignment of strings, bytes, and secret str objects."""
    secret_key = EncryptionPipelineFactory.generate_secret_key()
    secret_key_str = secret_key.decode(EncryptionPipelineFactory.ENCODING)

    # SecretStrs, bytes, and strs should be coerced into a secret str
    default_factory = EncryptionPipelineFactory(secret_key)
    factory_from_str = EncryptionPipelineFactory(secret_key_str)

    assert isinstance(default_factory._secret_key, SecretStr)
    assert default_factory._secret_key == factory_from_str._secret_key

    factory_from_secret = EncryptionPipelineFactory(SecretStr(secret_key_str))
    assert factory_from_str._secret_key == factory_from_secret._secret_key

    # Should recover the key exactly from the property getter
    assert factory_from_str.secret_key == default_factory.secret_key == secret_key


def test_encryption_cryptography_dependency_missing(skip_missing_encryption_dependency):
    """Verifies the behavior of the sessions.encryption module when `cryptography` is missing."""
    try:
        with patch.dict("sys.modules", {"cryptography.fernet": None}):
            importlib.reload(scholar_flux.sessions.encryption)
            assert scholar_flux.sessions.encryption.Fernet is None
            assert scholar_flux.sessions.encryption.Signer is not None
            with pytest.raises(scholar_flux.sessions.encryption.CryptographyImportError):
                _ = scholar_flux.sessions.encryption.EncryptionPipelineFactory()
    finally:
        importlib.reload(scholar_flux.sessions.encryption)


def test_encryption_itsdangerous_dependencies_missing(skip_missing_encryption_dependency):
    """Verifies the behavior of the sessions.encryption module when `itsdangerous` is missing."""
    try:
        with patch.dict("sys.modules", {"itsdangerous": None}):
            importlib.reload(scholar_flux.sessions.encryption)
            assert scholar_flux.sessions.encryption.Signer is None
            assert scholar_flux.sessions.encryption.Fernet is not None
            with pytest.raises(scholar_flux.sessions.encryption.ItsDangerousImportError):
                _ = scholar_flux.sessions.encryption.EncryptionPipelineFactory()
    finally:
        importlib.reload(scholar_flux.sessions.encryption)


def test_encryption_factory_key_reassignment(skip_missing_encryption_dependency):
    """Verifies that encryption correctly handles the re-assignment of the `secret_key` property."""
    # generating a new secret key entirely and coercing into strings and secret strings
    secret_key = EncryptionPipelineFactory.generate_secret_key()
    secret_key_str = secret_key.decode(EncryptionPipelineFactory.ENCODING)
    masked_secret_key = SecretStr(secret_key_str)

    # generates a new secret key or reads from env
    pipeline = EncryptionPipelineFactory(secret_key)

    # testing reassignment
    new_pipeline = EncryptionPipelineFactory()

    # storing a secret keys as a masked strings under-the-hood using Pydantic
    new_pipeline.secret_key = masked_secret_key
    assert isinstance(new_pipeline._secret_key, SecretStr)
    assert new_pipeline.secret_key == pipeline.secret_key

    # masking bytes as secret strings directly via the property setter
    new_pipeline.secret_key = secret_key
    assert isinstance(new_pipeline._secret_key, SecretStr)
    assert new_pipeline.secret_key == pipeline.secret_key

    # masking strings as secret strings
    new_pipeline.secret_key = secret_key_str
    assert isinstance(new_pipeline._secret_key, SecretStr)
    assert new_pipeline.secret_key == pipeline.secret_key


def test_missing_encryption(session_encryption_dependency):
    """Validates whether a missing package dependency will correctly raise an error once instantiated."""
    if not session_encryption_dependency:
        pytest.skip()

    with patch("scholar_flux.sessions.encryption.Signer", None):
        with pytest.raises(ItsDangerousImportError):
            from scholar_flux.sessions.encryption import EncryptionPipelineFactory

            _ = EncryptionPipelineFactory()
    with patch("scholar_flux.sessions.encryption.Fernet", None):
        with pytest.raises(CryptographyImportError):
            from scholar_flux.sessions.encryption import EncryptionPipelineFactory

            _ = EncryptionPipelineFactory()


def test_validate_encrypted_cached_session_raises_on_invalid_token(tmp_path, cleanup, caplog):
    """Verifies that sessions using pipelines with bad keys will raise an error on cache retrieval and validation."""
    # Ensure that any set env variables are overridden by explicitly generated secret keys:
    encryption_factory = EncryptionPipelineFactory(secret_key=EncryptionPipelineFactory.generate_secret_key())
    encryption_factory_two = EncryptionPipelineFactory(secret_key=EncryptionPipelineFactory.generate_secret_key())

    cache_manager = CachedSessionManager(backend="sqlite", cache_directory=tmp_path, serializer=encryption_factory())

    cached_session = cache_manager()

    test_url = "https://httpbin.org/status/200"
    with requests_mock.Mocker() as m:
        m.get(url=test_url, json="ok")
        assert cached_session.get(test_url)

        cache_manager_two = CachedSessionManager(
            backend="sqlite", cache_directory=tmp_path, serializer=encryption_factory_two()
        )

        msg = "CachedSession validation was unsuccessful due to the following: InvalidToken"
        with pytest.raises(CachedSessionValidationError, match=msg):
            _ = cache_manager_two(verify_connection=True)

    assert msg in caplog.text


def test_validate_encrypted_cached_session_does_not_raise_on_new_key_if_empty(tmp_path, cleanup):
    """Verifies that `verify_connection=True` does not raise an InvalidToken with a new key if the cache is empty."""
    # Ensure that any set env variables are overridden by explicitly generated secret keys:
    encryption_factory = EncryptionPipelineFactory(secret_key=EncryptionPipelineFactory.generate_secret_key())
    encryption_factory_two = EncryptionPipelineFactory(secret_key=EncryptionPipelineFactory.generate_secret_key())

    cache_manager = CachedSessionManager(backend="sqlite", cache_directory=tmp_path, serializer=encryption_factory())

    cached_session = cache_manager()

    test_url = "https://httpbin.org/status/200"
    with requests_mock.Mocker() as m:
        m.get(url=test_url, json="ok")
        assert cached_session.get(test_url)
        cached_session.cache.clear()

        cache_manager_two = CachedSessionManager(
            backend="sqlite", cache_directory=tmp_path, serializer=encryption_factory_two()
        )
        cached_session_two = cache_manager_two(verify_connection=True)
        assert cached_session_two.get(test_url)
        cached_session_two.cache.clear()


def test_encrypted_cached_session_initialization(
    default_encryption_cache_session_manager,
    incorrect_secret_salt_encryption_cache_session_manager,
    session_encryption_dependency,
):
    """Verifies that, when available, the EncryptionPipelineFactory works as intended to encrypt session cache when
    using the initial fernet key for session encryption and decryption.

    Also validates that, when a new fernet key is used to attempt to access the same encrypted cache sql file with a
    session encryption pipeline, the SearchAPI will instead raise an InvalidToken error indicating that the previously
    accessible resource can't be accessed with the current, incorrect Fernet key.

    """

    if not session_encryption_dependency:
        pytest.skip()

    session = default_encryption_cache_session_manager.configure_session()
    incorrect_session = incorrect_secret_salt_encryption_cache_session_manager.configure_session()
    assert isinstance(session, CachedSession)

    URL = "https://mocked_websited.com/endpoints"

    api = SearchAPI.from_defaults(
        query="darkness", provider_name="plos", session=session, request_delay=0, base_url=URL
    )

    params = api.build_parameters(page=1)
    prepared_request = api.prepare_request(api.base_url, parameters=params)

    assert prepared_request.url is not None
    with requests_mock.Mocker() as m:
        m.get(prepared_request.url, status_code=200, json=params)

        response = api.search(page=1)
        assert not getattr(response, "from_cache", False)

        response_two = api.send_request(api.base_url, parameters=params)
        assert getattr(response_two, "from_cache", False)

        assert response.content == response_two.content

        assert api.cache

    api.cache.clear()

    api_two = SearchAPI.from_defaults(
        query="darkness", provider_name="plos", session=incorrect_session, request_delay=0, base_url=URL
    )

    from cryptography.fernet import InvalidToken

    with requests_mock.Mocker() as m:
        response_three = None
        m.get(prepared_request.url, status_code=200, json=params)
        with suppress(InvalidToken):
            response_three = api_two.search(page=1)
        assert not getattr(response_three, "from_cache", False)
