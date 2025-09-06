from typing import Any, Optional
from pydantic import SecretStr


class SecretUtils:
    @staticmethod
    def mask_secret(obj: Any) -> Optional[SecretStr]:
        """
        Helper method masking variables into secret strings

        Args:
            obj (Any | SecretStr): An object to attempt to unmask if it is a secret string
        Returns:
            obj (SecretStr): A SecretStr representation of the oiginal object
        """

        return obj if isinstance(obj, SecretStr) else SecretStr(str(obj)) if obj is not None else obj

    @staticmethod
    def unmask_secret(obj: Any) -> Any:
        """
        Helper method for unmasking a variable from a SecretStr into its native type if a secret string

        Args:
            obj (Any | SecretStr): An object to attempt to unmask if it is a secret string
        Returns:
            obj (Any): The object's original type before being converted into a secret string
        """

        return obj.get_secret_value() if isinstance(obj, SecretStr) else obj
