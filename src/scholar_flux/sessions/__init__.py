# sessions/
"""The scholar_flux.sessions module contains helper classes to set up HTTP sessions, both cached and uncached, with
relatively straightforward configurations and a unified interface. The SessionManager and CachedSessionManager are
designed as factory classes that return a constructed session object with the parameters provided.

Classes:
    - SessionManager:
        Creates a standard requests.Session that simply takes a user-agent parameter.
    - CachedSessionManager:
        Creates a requests-cache.CachedSession with configurable options. This implementation uses pydantic for
        configuration to validate the parameters used to create the requests.CachedSession object.

Basic Usage:
    >>> from scholar_flux.api import SearchAPI
    >>> from scholar_flux.sessions import SessionManager, CachedSessionManager, EncryptionPipelineFactory
    >>> from requests import Response
    >>> from requests_cache import CachedResponse
    >>> session_manager = SessionManager(user_agent='scholar_flux_session')
    >>> requests_session = session_manager.configure_session() # or session_manager()
    >>> api = SearchAPI(query = 'functional programming', session = requests_session)

Cached Sessions:
    >>> from scholar_flux.api import SearchAPI
    >>> from scholar_flux.sessions import CachedSessionManager
    ### And for cached sessions, the following defaults to sqlite in the package_cache subfolder
    >>> session_manager = CachedSessionManager(user_agent='scholar_flux_session')
    ### Or initialize the session manager with a custom requests_cache backend
    >>> from requests_cache import RedisCache, CachedResponse
    >>> session_manager = CachedSessionManager(user_agent='scholar_flux_session', backend = RedisCache())
    >>> cached_requests_session = session_manager() # or session_manager.configure_session()
    >>> api_with_cache = SearchAPI(query = 'functional programming', session = cached_requests_session)
    >>> response = api_with_cache.search(page=1) # will be cached on subsequent runs
    >>> isinstance(response, Response)
    # OUTPUT: True
    >>> cached_response = api_with_cache.search(page=1) # is now cached
    >>> isinstance(cached_response, CachedResponse)
    # OUTPUT: True

Encrypted Cached Sessions
    >>> from scholar_flux.api import SearchAPI
    >>> from scholar_flux.sessions import CachedSessionManager, EncryptionPipelineFactory
    ### For encrypting requests we can create a serializer that encrypts data before it's stored:
    >>> encryption_pipeline_factory = EncryptionPipelineFactory()
    ### The pipeline, if a Fernet key is not provided and not saved in a .env file that is read on import,
    ### the following generates a random Fernet key by default.
    >>> fernet = encryption_pipeline_factory.fernet # (make sure you save this)
    >>> print(fernet)
    # OUTPUT: <cryptography.fernet.Fernet at 0x7efd9de62450>
    ### The encryption has to be specified when creating a cached session:
    >>> session_manager = CachedSessionManager(user_agent='scholar_flux_session',
    >>>                                        backend='filesystem',
    >>>                                        serializer=encryption_pipeline_factory())
    ### Now assignment to a SearchAPI occurs similarly as before
    >>> api_with_encrypted_cache = SearchAPI(query = 'object oriented programming', session = session_manager())


Raises:
    - SessionCreationError
    - SessionConfigurationError
    - SessionInitializationError
    - SessionCacheDirectoryError


Cached Session Support:
    Cached sessions support all built-in subclasses originating from the BaseCache base class in requests-cache.
    This includes the following built-ins:

    - Dynamo DB,
    - File System cache,
    - GridFS
    - In-Memory
    - Mongo DB
    - Redis
    - SQLite

    Custom implementations of BaseCache are also supported.

See Also:
    - https://requests-cache.readthedocs.io/

"""
from scholar_flux.sessions.models import BaseSessionManager, CachedSessionConfig
from scholar_flux.sessions.session_manager import SessionManager, CachedSessionManager
from scholar_flux.sessions.encryption import EncryptionPipelineFactory


__all__ = [
    "SessionManager",
    "CachedSessionManager",
    "EncryptionPipelineFactory",
    "BaseSessionManager",
    "CachedSessionConfig",
]
