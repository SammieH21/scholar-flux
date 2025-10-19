# /sessions/models
"""The scholar_flux.sessions.models module contains classes and form the basis for the creation and validation of
sessions and the parameters used to create them.

This module also contains the underlying config that is necessary for the creation and validation of the
CachedSessionManager class.

Classes:
    - The BaseSessionManager serves as a template for subclassing and orchestrating the creation of sessions
    - The CachedSessionConfig class is based on Pydantic and supports the validation of input parameters.

Usage:
    Neither classes are currently intended to be client facing.
    Instead, they support the creation and use of existing Session Managers behind the scenes.

For example, the BaseSessionManager is subclassed into the SessionManager to create user-facing session managers:

    >>> from scholar_flux.sessions import SessionManager
    ### Implementations validate parameters on instantiation and/or fill in missing details with defaults
    >>> session_manager = SessionManager("my_scholar_flux_session") # Enforces the creation of a user agent
    ### The session_manager creates a session object for direct use in APIs
    >>> session = session_manager() # In this case, the manager creates a standard requests.Session

"""
from scholar_flux.sessions.models.session import BaseSessionManager, CachedSessionConfig

__all__ = ["BaseSessionManager", "CachedSessionConfig"]
