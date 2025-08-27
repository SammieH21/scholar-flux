import pytest
import requests
from unittest.mock import patch, MagicMock
from requests_cache import CachedSession
from pathlib import Path
import requests_mock
from scholar_flux.api import SearchAPI
from scholar_flux.utils import try_call
from scholar_flux.exceptions import ItsDangerousImportError, CryptographyImportError,SecretKeyError

from unittest.mock import Mock, patch
import logging
logger = logging.getLogger(__name__)

import scholar_flux.sessions.session_manager as sm
from scholar_flux.utils import config_settings
from scholar_flux.exceptions.util_exceptions import SessionCreationError
from time import sleep
from base64 import b64encode, b64decode

def test_encryption_factory_secret_initialization():
    from scholar_flux.sessions.encryption import EncryptionPipelineFactory, Fernet

    faulty_secret_key = b'%this%a%bad%string%is%a%secret%key%%%%'

    with pytest.raises(SecretKeyError):
        faulty_b64_encoded_secret_key = b64encode(faulty_secret_key)
        EncryptionPipelineFactory(faulty_b64_encoded_secret_key)

    with pytest.raises(SecretKeyError):
        EncryptionPipelineFactory(123)

    secret_key = b'%this%string%is%a%secret%key%%%%'
    byte44_encoded_secret_key = b64encode(secret_key)
    try:
        EncryptionPipelineFactory._validate_key(byte44_encoded_secret_key)
    except SecretKeyError as e:
        assert False, e

    factory = EncryptionPipelineFactory(byte44_encoded_secret_key, salt=None)
    assert isinstance(factory.fernet, Fernet)
    assert secret_key == b64decode(factory.secret_key)


    factory_with_str = EncryptionPipelineFactory(byte44_encoded_secret_key.decode('utf-8'), salt='')
    assert isinstance(factory_with_str.secret_key, bytes) and secret_key == b64decode(factory_with_str.secret_key)

def test_missing_encryption():
    with patch('scholar_flux.sessions.encryption.Signer', None):
        with pytest.raises(ItsDangerousImportError):
            from scholar_flux.sessions.encryption import EncryptionPipelineFactory
            factory=EncryptionPipelineFactory()
    with patch('scholar_flux.sessions.encryption.Fernet', None):
        with pytest.raises(CryptographyImportError):
            from scholar_flux.sessions.encryption import EncryptionPipelineFactory
            factory_two=EncryptionPipelineFactory()


def test_encrypted_cached_session_initialization(default_encryption_cache_session_manager,
                                                 incorrect_secret_salt_encryption_cache_session_manager,
                                                 mock_academic_json):
    session = default_encryption_cache_session_manager.configure_session()
    incorrect_session = incorrect_secret_salt_encryption_cache_session_manager.configure_session()
    assert isinstance(session, CachedSession)

    URL = 'https://mocked_websited.com/endpoints'

    api = SearchAPI.from_defaults(query= 'darkness', provider_name = 'plos', session = session, request_delay=0,
                                  base_url = URL)

    params = api.build_parameters(page=1)
    prepared_request = api.prepare_request(api.base_url, parameters=params)

    assert prepared_request.url is not None
    with requests_mock.Mocker() as m:
        m.get(prepared_request.url, status_code = 200, json=params)

        response=api.send_request(api.base_url, parameters=params)
        assert not getattr(response, 'from_cache', False)

        response_two=api.send_request(api.base_url, parameters=params)
        assert getattr(response_two, 'from_cache', False)

        assert response.content == response_two.content

        from cryptography.fernet import InvalidToken
        assert api.cache

    api.cache.clear()

    api_two = SearchAPI.from_defaults(query= 'darkness', provider_name = 'plos', session = incorrect_session, request_delay=0,
                                  base_url = URL)

    
    with requests_mock.Mocker() as m:
        m.get(prepared_request.url, status_code = 200)

        response_three = None
        try:
                m.get(prepared_request.url, status_code = 200, json=params)
                response_three=api_two.send_request(api.base_url, parameters=params)
        except InvalidToken:
            pass
        assert not getattr(response_three, 'from_cache', False)
