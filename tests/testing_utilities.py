# /tests/testing_utilities
from typing import Optional, Callable, Type

"""Helper module for reusing tests that use similar logic under the hood to verify ScholarFlux functionality"""


def raise_error(exception_type: Type[BaseException], message: Optional[str] = None) -> Callable:
    """Helper method for manually raising an error message."""
    return lambda *args, **kwargs: (_ for _ in ()).throw(exception_type(message))
