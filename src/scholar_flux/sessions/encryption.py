# /sessions/encryption.py
"""The scholar_flux.sessions.encryption module is tasked with the implementation of an EncryptionPipelineFactory that
can be used to easily and efficiently create a serializer that is accepted by CachedSession objects to store requests
cache.

This encryption factory uses encryption and a safer_serializer for two steps:
    1) To sign the requests storage cache for invalidation on unexpected data changes/tampering
    2) To encrypt request cache for storage after serialization and decrypt it before deserialization during retrieval

If a key does not exist and is not provided, the EncryptionPipelineFactory will create a new Fernet key. for these steps

"""
from scholar_flux.exceptions import (
    ItsDangerousImportError,
    CryptographyImportError,
    SecretKeyError,
)
from requests_cache.serializers.pipeline import SerializerPipeline, Stage
from requests_cache.serializers.cattrs import CattrStage
from scholar_flux.utils import config_settings
from pydantic import SecretStr
import logging


from typing import Optional, TYPE_CHECKING
import pickle

if TYPE_CHECKING:
    from itsdangerous import Signer
    from cryptography.fernet import Fernet
else:
    try:
        from itsdangerous import Signer
        from cryptography.fernet import Fernet
    except ImportError:
        Signer = None
        Fernet = None


logger = logging.getLogger(__name__)


class EncryptionPipelineFactory:
    """Helper class used to create a factory for encrypting and decrypting session cache and pipelines using a secret
    key.

    Note that pickle in common uses carries the potential for vulnerabilities when reading untrusted serialized
    data and can otherwise perform arbitrary code execution. This implementation makes use of a safe serializer
    that uses a fernet generated secret_key to validate the serialized data before reading and decryption.
    This prevents errors and halts reading the cached data in case of modification via a malicious source.

    The EncryptionPipelineFactory can be used for generalized use cases requiring encryption outside scholar_flux
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

    def __init__(self, secret_key: Optional[str | bytes] = None, salt: Optional[str] = ""):
        """Initializes the EncryptionPipelineFactory class that generates an encryption pipeline for use with
        CachedSession objects.

        If no secret_key is provided, the code attempts to retrieve a secret key from the
        SCHOLAR_FLUX_CACHE_SECRET_KEY environment variable from the config.

        Otherwise a random Fernet key is generated and used to encrypt the session.



        Args:
            secret_key Optional[str | bytes]: The key to use for encrypting and decrypting
                       the data that flows through the pipeline.
            salt: Optional[str]: An optional salt used to further increase security on write

        """

        if Signer is None:
            raise ItsDangerousImportError

        if Fernet is None:
            raise CryptographyImportError

        self.signer = Signer

        prepared_key = self._prepare_key(secret_key)

        if prepared_key:
            self._validate_key(prepared_key)

        self.secret_key = prepared_key or self.generate_secret_key()
        self.salt = salt or ""

    @staticmethod
    def _prepare_key(key: Optional[str | bytes]) -> bytes | None:
        """Prepares the input (bytes, string) and returns a bytes variable if a non-missing value is provided.

        If the key is None, the function will also return None

        """
        cache_secret_key = config_settings.get("SCHOLAR_FLUX_CACHE_SECRET_KEY")

        if not key and cache_secret_key:
            logger.debug(
                "Using secret key from SCHOLAR_FLUX_CACHE_SECRET_KEY to build cache‑session" " encryption pipeline"
            )

            key = cache_secret_key.get_secret_value() if isinstance(cache_secret_key, SecretStr) else cache_secret_key

        if key is None:
            return None

        byte_key = key.encode("utf-8") if isinstance(key, str) else key
        if not isinstance(byte_key, bytes):
            raise SecretKeyError("secret_key must be bytes or UTF-8 string")

        return byte_key

    @staticmethod
    def _validate_key(key: bytes) -> None:
        """Ensures that the length of the received bytes is 44 characters."""
        if len(key) != 44:  # 32 bytes encoded in base64 => 44 characters
            raise SecretKeyError("Fernet key must be 32 url-safe base64-encoded bytes (length 44)")
        try:
            Fernet(key)
        except Exception as e:
            raise SecretKeyError("Provided secret_key is not a valid Fernet key.") from e

    @staticmethod
    def generate_secret_key() -> bytes:
        """Generate a secret key for Fernet encryption."""
        return Fernet.generate_key()

    @property
    def fernet(self) -> Fernet:
        """Returns a fernet key using the validated 32 byte url-safe base64 key."""
        return Fernet(self.secret_key)

    def encryption_stage(self) -> Stage:
        """Create a stage that uses Fernet encryption."""
        fernet = self.fernet

        return Stage(
            fernet,
            dumps=fernet.encrypt,
            loads=fernet.decrypt,
        )

    def signer_stage(self) -> Stage:
        """Create a stage that uses `itsdangerous` to add a signature to responses on write, and validate that signature
        with a secret key on read."""
        return Stage(
            self.signer(secret_key=self.secret_key, salt=self.salt),
            dumps="sign",
            loads="unsign",
        )

    def create_pipeline(self) -> SerializerPipeline:
        """Create a serializer that uses pickle + itsdangerous for signing and cryptography for encryption."""
        base_stage = CattrStage()

        return SerializerPipeline(
            [base_stage, Stage(pickle), self.signer_stage(), self.encryption_stage()],
            name="safe_pickle_with_encryption",
            is_binary=True,
        )

    def __call__(self) -> SerializerPipeline:
        """Helper method for being able to create the serializer pipeline by calling the factory object."""
        return self.create_pipeline()


__all__ = ["EncryptionPipelineFactory"]
