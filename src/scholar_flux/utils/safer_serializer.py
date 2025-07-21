from scholar_flux.exceptions import ItsDangerousImportError, CryptographyImportError
from requests_cache.serializers.pipeline import SerializerPipeline, Stage
from requests_cache.serializers.preconf import make_stage
from requests_cache.serializers.cattrs import CattrStage

from requests_cache import CachedSession
from cryptography.fernet import Fernet
from typing import List, Dict, Any, Optional, TYPE_CHECKING
import pickle

if TYPE_CHECKING:
    from itsdangerous import Signer
    from cryptography.fernet import Fernet
else:
    try:
        from itsdangerous import Signer
    except ImportError:
        Signer=None

    try:
        from cryptography.fernet import Fernet
    except ImportError:
        cryptography=None

class EncryptionPipelineFactory:
    def __init__(self, secret_key=None, salt='requests-cache'):

        if Signer is None:
            raise ItsDangerousImportError

        if Fernet is None:
            raise CryptographyImportError

        self.signer = Signer
        self.secret_key = secret_key or self.generate_secret_key()
        self.salt = salt

    @staticmethod
    def generate_secret_key():
        """Generate a secret key for Fernet encryption"""
        return Fernet.generate_key()

    def encryption_stage(self) -> Stage:
        """Create a stage that uses Fernet encryption"""
        fernet = Fernet(self.secret_key)

        return Stage(
            fernet,
            dumps=fernet.encrypt,
            loads=fernet.decrypt,
        )

    def signer_stage(self) -> Stage:
        """Create a stage that uses `itsdangerous` to add a signature to responses on write, and
        validate that signature with a secret key on read.
        """
        return Stage(
            self.signer(secret_key=self.secret_key, salt=self.salt),
            dumps='sign',
            loads='unsign',
        )

    def create_pipeline(self) -> SerializerPipeline:
        """Create a serializer that uses pickle + itsdangerous for signing and cryptography for encryption"""
        base_stage = CattrStage()

        return SerializerPipeline(
            [base_stage, Stage(pickle), self.signer_stage(), self.encryption_stage()],
            name='safe_pickle_with_encryption',
            is_binary=True,
        )

# Example usage
if __name__ == "__main__":
    factory = EncryptionPipelineFactory()
    serializer = factory.create_pipeline()
    session = CachedSession(serializer=serializer)
    response = session.get("https://docs.python.org/3/library/typing.html")
    cached_response = session.get("https://docs.python.org/3/library/typing.html")




