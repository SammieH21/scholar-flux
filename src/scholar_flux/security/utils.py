from typing import Any, Optional
from pydantic import SecretStr


class SecretUtils:
    """
    Helper utility for both masking and unmasking strings. Class methods are defined
    so that they can be used directly or implemented as a mixin so that subclasses
    can implement the class methods directly.
    """

    @classmethod
    def mask_secret(cls, obj: Any) -> Optional[SecretStr]:
        """
        Helper method masking variables into secret strings:

        Args:
            obj (Any | SecretStr): An object to attempt to unmask if it is a secret string

        Returns:
            obj (SecretStr): A SecretStr representation of the oiginal object

        Examples:
            >>> string = 'a secret'
            >>> secret_string = SecretUtils.mask_secret(string)
            >>> isinstance(secret_string, SecretStr) is True

            >>> no_string = None
            >>> non_secret = SecretUtils.mask_secret(no_string)
            >>> non_secret is None

        """

        return obj if isinstance(obj, SecretStr) else SecretStr(str(obj)) if obj is not None else obj

    @classmethod
    def unmask_secret(cls, obj: Any) -> Any:
        """
        Helper method for unmasking a variable from a SecretStr into its native type if a secret string.

        Args:
            obj (Any | SecretStr): An object to attempt to unmask if it is a secret string

        Returns:
            obj (Any): The object's original type before being converted into a secret string

        Examples:
            >>> string = 'a secret'
            >>> secret_string = SecretUtils.mask_secret(string)
            >>> isinstance(secret_string, SecretStr) is True
            >>> SecretUtils.unmask_secret(secret_string) == string
            >>> SecretUtils.unmask_secret(None) is None
        """

        return obj.get_secret_value() if isinstance(obj, SecretStr) else obj
