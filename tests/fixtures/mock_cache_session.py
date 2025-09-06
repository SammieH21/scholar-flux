import scholar_flux.sessions.session_manager as sm
from scholar_flux.sessions import EncryptionPipelineFactory
import pytest
from pathlib import Path
import os
import importlib.util

@pytest.fixture(scope='session')
def default_cache_directory():
    return Path(__file__).resolve().parent.parent / 'mocks'

@pytest.fixture(scope='session')
def default_cache_filename():
    return "testing_session_cache"


@pytest.fixture(scope='session')
def default_seconds_cache_expiration():
    """Cached requests expire after 1 second"""
    return 1

@pytest.fixture(scope='session')
def default_backend():
    return 'sqlite'

@pytest.fixture(scope='session')
def default_cache_session_manager(default_cache_filename,
                                  default_cache_directory,
                                  default_seconds_cache_expiration,
                                  default_backend):

    return sm.CachedSessionManager(user_agent="test_session",
                                   cache_name=default_cache_filename,
                                   cache_directory=default_cache_directory,
                                   expire_after=default_seconds_cache_expiration,
                                   backend=default_backend)

@pytest.fixture(scope='session')
def default_cache_session(default_cache_session_manager):
    cached_sesssion = default_cache_session_manager.configure_session()
    yield cached_sesssion
    cached_sesssion.cache.clear()

###############

@pytest.fixture(scope='session')
def default_encryption_cache_filename():
    return "testing_encrypted_session_cache"

@pytest.fixture(scope='session')
def default_encryption_serializer_pipeline():
    if not all(importlib.util.find_spec(pkg) for pkg in ('cryptography', 'itsdangerous')):
        pytest.skip()
    return EncryptionPipelineFactory

@pytest.fixture(scope='session')
def default_secret_key():
    """Default secret key to use for both encrypting and caching responses from API providers"""
    if not importlib.util.find_spec('cryptography'):
        pytest.skip()

    from cryptography.fernet import Fernet
    return Fernet.generate_key()

@pytest.fixture(scope='session')
def default_secret_salt():
    return os.urandom(16)

@pytest.fixture(scope='session')
def incorrect_secret_key():
    """
    Key to be used for attempting to access a previously created cache that was created
    with the default_secret_key. This should fail since it will be the wrong key
    """
    if not importlib.util.find_spec('cryptography'):
        pytest.skip()

    from cryptography.fernet import Fernet
    return Fernet.generate_key()


@pytest.fixture(scope='session')
def incorrect_secret_salt():
    """
    Salt to be used in conjunction with the incorrect key to be
    used for attempting to access a previously created cache that was created
    with the default_secret_key. This should also fail.
    """
    secret_salt = os.urandom(18)
    return secret_salt

@pytest.fixture(scope='session')
def default_encryption_cache_session_manager(default_encryption_cache_filename,
                                             default_cache_directory,
                                             default_encryption_serializer_pipeline,
                                             default_secret_key, default_secret_salt
                                             ):
    if not default_encryption_serializer_pipeline:
        pytest.skip()

    create_serializer = default_encryption_serializer_pipeline(secret_key = default_secret_key, salt = default_secret_salt)
    return sm.CachedSessionManager(user_agent="test_session",
                                   cache_name=default_encryption_cache_filename,
                                   cache_directory=default_cache_directory,
                                   backend='memory',
                                   serializer = create_serializer()
                                  )

@pytest.fixture(scope='session')
def default_memory_cache_session_manager():
    return sm.CachedSessionManager(user_agent="test_session",
                                   backend='memory',
                                  )

@pytest.fixture(scope='session')
def default_memory_cache_session(default_memory_cache_session_manager):
    return default_memory_cache_session_manager()

@pytest.fixture(scope='session')
def incorrect_secret_salt_encryption_cache_session_manager(default_encryption_cache_filename,
                                                           default_cache_directory,
                                                           default_encryption_serializer_pipeline,
                                                           incorrect_secret_key, incorrect_secret_salt
                                             ):
    if not default_encryption_serializer_pipeline:
        pytest.skip()

    create_serializer = default_encryption_serializer_pipeline(secret_key = incorrect_secret_key, salt = incorrect_secret_salt)
    return sm.CachedSessionManager(user_agent="test_session",
                                   cache_name=default_encryption_cache_filename,
                                   cache_directory=default_cache_directory,
                                   backend='filesystem',
                                   serializer = create_serializer()
                                  )


@pytest.fixture(scope='session')
def default_encryption_cache_session(default_encryption_cache_session_manager):
    cached_sesssion = default_encryption_cache_session_manager.configure_session()
    yield cached_sesssion
    cached_sesssion.cache.clear()
    path = default_encryption_cache_session_manager.cache_path
    if path and path.endswith('json'):
        os.remove(path)

@pytest.fixture(scope='session')
def sqlite_db_url():
    sqlite_db_url =  Path(__file__).resolve().parent.parent / 'mocks/processing_cache.sqlite'
    return 'sqlite:///' + str(sqlite_db_url)


__all__= ['default_cache_session_manager', 'default_cache_session',
          'default_seconds_cache_expiration', 'default_backend',
          'default_cache_filename', 'default_cache_directory',
          'default_memory_cache_session_manager', 'default_memory_cache_session',
          'default_encryption_cache_session', 'default_secret_salt',
          'default_secret_key', 'default_encryption_cache_session_manager',
          'default_encryption_cache_filename', 'default_encryption_serializer_pipeline',
          'incorrect_secret_key', 'incorrect_secret_salt',
          'incorrect_secret_salt_encryption_cache_session_manager', 'sqlite_db_url']
