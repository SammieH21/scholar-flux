# /sessions/encryption.py
"""The scholar_flux.sessions.encryption module is tasked with the implementation of an EncryptionPipelineFactory that
can be used to easily and efficiently create a serializer that is accepted by CachedSession objects to store requests
cache.

This encryption factory uses encryption and a safer_serializer for two steps:
    1) To sign the requests storage cache for invalidation on unexpected data changes/tampering
    2) To encrypt request cache for storage after serialization and decrypt it before deserialization during retrieval

If a key does not exist and is not provided, the EncryptionPipelineFactory will create a new Fernet key for these steps

"""
from scholar_flux.exceptions import (
    ItsDangerousImportError,
    CryptographyImportError,
    SecretKeyError,
)
from requests_cache.serializers.pipeline import SerializerPipeline, Stage
from requests_cache.serializers.cattrs import CattrStage
from scholar_flux.security import SecretUtils
from scholar_flux.utils import config_settings
from pydantic import SecretStr
import logging


from typing import Final, Optional, TYPE_CHECKING
import pickle

if TYPE_CHECKING:
    from itsdangerous import Signer
    from cryptography.fernet import Fernet
else:
    try:
        from itsdangerous import Signer
    except ImportError:
        Signer = None
    try:
        from cryptography.fernet import Fernet
    except ImportError:
        Fernet = None


logger = logging.getLogger(__name__)


class EncryptionPipelineFactory:
    """Helper class used to create a factory for encrypting and decrypting session cache and pipelines using a secret
    key.

    Note that pickle in common use carries the potential for vulnerabilities when reading untrusted serialized
    data and can otherwise perform arbitrary code execution. This implementation makes use of a safe serializer
    that uses a fernet generated secret_key to validate the serialized data before reading and decryption.
    This prevents errors and halts reading the cached data in case of modification via a malicious source.

    The EncryptionPipelineFactory can be used for generalized use cases requiring encryption outside scholar_flux.
    and implemented as follows:

        >>> from scholar_flux.sessions import EncryptionPipelineFactory
        >>> from requests_cache import CachedSession, CachedResponse
        >>> encryption_pipeline_factory = EncryptionPipelineFactory()
        >>> encryption_serializer = encryption_pipeline_factory()
        >>> cached_session = CachedSession('filesystem', serializer = encryption_serializer)
        >>> endpoint = "https://docs.python.org/3/library/typing.html"
        >>> response = cached_session.get(endpoint)
        >>> cached_response = cached_session.get(endpoint)
        >>> assert isinstance(cached_response, CachedResponse)

    """

    ENCODING: Final[str] = "utf-8"

    def __init__(self, secret_key: Optional[str | bytes | SecretStr] = None, salt: Optional[str] = ""):
        """Initializes the EncryptionPipelineFactory class that generates an encryption pipeline for use with
        CachedSession objects.

        If no secret_key is provided, the code attempts to retrieve a secret key from the
        SCHOLAR_FLUX_CACHE_SECRET_KEY environment variable from the config.

        Otherwise a random Fernet key is generated and used to encrypt the session.

        Args:
            secret_key Optional[str | bytes]:
                The key to use for encrypting and decrypting the data that flows through the pipeline.
            salt: Optional[str]: An optional salt used to further increase security on write

        """

        if Signer is None:
            raise ItsDangerousImportError()

        if Fernet is None:
            raise CryptographyImportError()

        self.signer = Signer

        prepared_key = self._prepare_key(secret_key)
        self.secret_key = prepared_key or self.generate_secret_key()
        self.salt = salt or ""

    @property
    def secret_key(self) -> bytes:
        """Returns the secret key used for encrypting and decrypting the cache serialization pipeline."""
        unmasked_secret_str = SecretUtils.unmask_secret(self._secret_key)
        return (
            unmasked_secret_str.encode(self.ENCODING) if isinstance(unmasked_secret_str, str) else unmasked_secret_str
        )

    @secret_key.setter
    def secret_key(self, key: str | bytes | SecretStr) -> None:
        """Validates and assigns a secret key for encrypting and decrypting the cache serialization pipeline."""
        unmasked_key = SecretUtils.unmask_secret(key)
        unmasked_key_bytes = unmasked_key.encode(self.ENCODING) if isinstance(unmasked_key, str) else unmasked_key
        self._validate_key(unmasked_key_bytes)
        self._secret_key = SecretUtils.mask_secret(unmasked_key_bytes.decode(self.ENCODING))

    @classmethod
    def _prepare_key(cls, key: Optional[str | bytes | SecretStr]) -> Optional[bytes]:
        """Prepares the input (bytes, string) and returns a bytes variable if a non-missing value is provided.

        Args:
            key (Optional[str | bytes]): The input key to use as a fernet/secret key.

        Returns:
            Optional[bytes]: The key prepared as a bytes object. If no key is provided, this method will return None.

        """
        if not key and (cache_secret_key := config_settings.get("SCHOLAR_FLUX_CACHE_SECRET_KEY")):
            logger.debug(
                "Using secret key from SCHOLAR_FLUX_CACHE_SECRET_KEY to build cache‑session" " encryption pipeline"
            )

            key = SecretUtils.unmask_secret(cache_secret_key)

        if key is None:
            return None

        byte_key = SecretUtils.unmask_secret(key).encode(cls.ENCODING) if isinstance(key, str | SecretStr) else key
        if not isinstance(byte_key, bytes):
            raise SecretKeyError(
                f"The secret key used for pipeline serialization encryption must be a bytes or {cls.ENCODING.upper()} "
                "string object."
            )

        return byte_key

    @staticmethod
    def _validate_key(key: bytes) -> None:
        """Ensures that the length of the received bytes is 44 characters."""
        if len(key) != 44:  # 32 bytes encoded in base64 => 44 characters
            raise SecretKeyError("Fernet key must be 32 URL-safe base64-encoded bytes (length 44)")
        try:
            Fernet(key)
        except Exception as e:
            raise SecretKeyError("Provided secret_key is not a valid Fernet key.") from e

    @staticmethod
    def generate_secret_key() -> bytes:
        """Generates a secret key for Fernet encryption using the `cryptography` package.

        Returns:
            bytes: A new 32 byte URL-safe base 64 key

        """
        return Fernet.generate_key()

    @property
    def fernet(self) -> Fernet:
        """Returns the current fernet key using the validated 32 byte URL-safe base64 key."""
        return Fernet(self.secret_key)

    def encryption_stage(self) -> Stage:
        """Creates a new serializer stage that uses Fernet encryption and decryption using the generated Fernet key.

        Returns:
            Stage: A new serializer stage that encrypts data when dumped and decrypts data when loaded.

        """
        fernet = self.fernet

        return Stage(
            fernet,
            dumps=fernet.encrypt,
            loads=fernet.decrypt,
        )

    def signer_stage(self) -> Stage:
        """Creates a stage that uses `itsdangerous` to add a signature to responses during serialization.

        This signature is generated on `write` and uses the provided secret key to enforce signature validation on
        deserialization, verifying that the response data hasn't been tampered when the response is reloaded.

        Returns:
            Stage: A new stage that uses the secret key and salt for signature creation and validation.

        """
        return Stage(
            self.signer(secret_key=self.secret_key, salt=self.salt),
            dumps="sign",
            loads="unsign",
        )

    def create_pipeline(self) -> SerializerPipeline:
        """Create a serializer that uses pickle + itsdangerous for signing and cryptography for encryption.

        This pipeline encrypts the response data after generating a signature when serialized. On load, the data is then
        decrypted and the signature that was previously generated with the secret key is verified prior to
        deserialization of the response.

        Returns:
            SerializerPipeline: A new serializer pipeline that enforces signature validation and encryption.

        """
        base_stage = CattrStage()

        return SerializerPipeline(
            [base_stage, Stage(pickle), self.signer_stage(), self.encryption_stage()],
            name="safe_pickle_with_encryption",
            is_binary=True,
        )

    def __call__(self) -> SerializerPipeline:
        """Convenience method that calls `EncryptionPipelineFactory.create_pipeline()` to create a serializer pipeline.

        Returns:
            SerializerPipeline: A new serializer pipeline that enforces signature validation and encryption.

        """
        return self.create_pipeline()


__all__ = ["EncryptionPipelineFactory"]
