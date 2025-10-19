import pytest
from unittest.mock import patch
from requests_cache import CachedSession
import requests_mock
from scholar_flux.api import SearchAPI
import scholar_flux.sessions.encryption
from scholar_flux.exceptions import ItsDangerousImportError, CryptographyImportError, SecretKeyError

import logging

logger = logging.getLogger(__name__)

from scholar_flux.sessions.encryption import EncryptionPipelineFactory, Fernet
from base64 import b64encode, b64decode


@pytest.fixture(scope="session")
def skip_missing_encryption_dependency(session_encryption_dependency):
    if not session_encryption_dependency:
        pytest.skip("Missing encryption optional dependencies")


def test_validate_key_error():
    """Validates whether the a string secret key will raise an error: The EncryptionPipelineFactory expects a Fernet if
    a key is provided.

    Otherwise it should generate it automatically.
    """
    with pytest.raises(SecretKeyError):
        key = " " * 44
        EncryptionPipelineFactory._validate_key(key.encode())


def test_generate_secret_key(skip_missing_encryption_dependency):
    """Tests the generation of a new Fernet key and verifies the type.

    Fernet keys should be URL encoded bytes with a of a length
    `len(fernet) == 44`
    """
    fernet = EncryptionPipelineFactory.generate_secret_key()
    assert isinstance(fernet, bytes) and len(fernet) == 44


def test_env_key_loader(skip_missing_encryption_dependency, caplog):
    """Validates whether the use of a SCHOLAR_FLUX_CACHE_SECRET_KEY will be successfully when generating a new
    encryption pipeline factory class."""
    # generates the fernet key
    fernet = EncryptionPipelineFactory.generate_secret_key()

    # simulates the fernet key being saved as a bytes object in the config
    with patch.dict(scholar_flux.sessions.encryption.config, {"SCHOLAR_FLUX_CACHE_SECRET_KEY": fernet}):
        # verifies whether, when a fernet key is not provided, the secret key will be used by default
        new_fernet = EncryptionPipelineFactory._prepare_key(None)
        assert "Using secret key from SCHOLAR_FLUX_CACHE_SECRET_KEY" in caplog.text
        assert fernet == new_fernet


def test_encryption_factory_secret_initialization(session_encryption_dependency):
    """Tests whether the initialization of a faulty and secret keys will raise the intended error.

    Also validates whether valid secret keys are successfully used in
    the EncryptionPipelineFactory
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


def test_encrypted_cached_session_initialization(
    default_encryption_cache_session_manager,
    incorrect_secret_salt_encryption_cache_session_manager,
    session_encryption_dependency,
):
    """Verifies that, when available, the EncryptionPipelineFactory works as intended to encrypt session cache when
    using the initial fernet key for session encryption and decryption.

    Also validates that, when a new fernet key is used to attempt to
    access the same encrypted cache sql file with a a session encryption
    pipeline, the SearchAPI will instead raise an InvalidToken error
    indicating that the previously accessible resource can't be accessed
    with the current, incorrect Fernet key.
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

        from cryptography.fernet import InvalidToken

        assert api.cache

    api.cache.clear()

    api_two = SearchAPI.from_defaults(
        query="darkness", provider_name="plos", session=incorrect_session, request_delay=0, base_url=URL
    )

    with requests_mock.Mocker() as m:
        m.get(prepared_request.url, status_code=200)

        response_three = None
        try:
            m.get(prepared_request.url, status_code=200, json=params)
            response_three = api_two.search(page=1)
        except InvalidToken:
            pass
        assert not getattr(response_three, "from_cache", False)
