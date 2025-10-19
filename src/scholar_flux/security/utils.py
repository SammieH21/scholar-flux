# /security/utils.py
"""The scholar_flux.security.utils module defines the SecretUtils class that implements the basic set of tools for both
masking and unmasking text, and identifying if a field is masked.

This class uses the pydantic.SecretStr class to mask and unmask fields and can be further extended to encrypt and
decrypt text as needed before and after conversion to a secret string, respectively.

"""
from typing import Any, Optional
from pydantic import SecretStr


class SecretUtils:
    """Helper utility for both masking and unmasking strings.

    Class methods are defined so that they can be used directly or implemented as a mixin so that subclasses can
    implement the class methods directly.

    """

    @classmethod
    def mask_secret(cls, obj: Any) -> Optional[SecretStr]:
        """Helper method masking variables into secret strings:

        Args:
            obj (Any | SecretStr): An object to attempt to unmask if it is a secret string

        Returns:
            obj (SecretStr): A SecretStr representation of the original object

        Examples:
            >>> from scholar_flux.security import SecretUtils
            >>> string = 'a secret'
            >>> secret_string = SecretUtils.mask_secret(string)
            >>> isinstance(secret_string, SecretStr) is True
            # OUTPUT: True

            >>> no_string = None
            >>> non_secret = SecretUtils.mask_secret(no_string)
            >>> non_secret is None
            # OUTPUT: True

        """

        return obj if cls.is_secret(obj) else SecretStr(str(obj)) if obj is not None else obj

    @classmethod
    def unmask_secret(cls, obj: Any) -> Any:
        """Helper method for unmasking a variable from a SecretStr into its native type if a secret string.

        Args:
            obj (Any | SecretStr): An object to attempt to unmask if it is a secret string

        Returns:
            obj (Any): The object's original type before being converted into a secret string

        Examples:
            >>> from scholar_flux.security import SecretUtils
            >>> string = 'a secret'
            >>> secret_string = SecretUtils.mask_secret(string)
            >>> isinstance(secret_string, SecretStr) is True
            # OUTPUT: True
            >>> SecretUtils.unmask_secret(secret_string) == string
            >>> SecretUtils.unmask_secret(None) is None
            # OUTPUT: True

        """

        return obj.get_secret_value() if cls.is_secret(obj) else obj

    @classmethod
    def is_secret(cls, obj: Any) -> bool:
        """Utility class method used to verify whether the current variable is a secret string. This method abstracts
        the implementation details into a single method to aid further extensibility.

        Args:
            obj (Any): The object to check

        Returns:
            bool: True if the object is a SecretStr, False otherwise

        """
        return isinstance(obj, SecretStr)


__all__ = ["SecretUtils"]
