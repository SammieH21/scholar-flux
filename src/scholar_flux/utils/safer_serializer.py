from ..exceptions import ItsDangerousImportError
from requests_cache.serializers.pipeline import SerializerPipeline, Stage
from requests_cache.serializers.preconf import make_stage
from requests_cache.serializers.cattrs import CattrStage

from requests_cache import CachedSession
from cryptography.fernet import Fernet
import pickle

try:
    from itsdangerous import Signer
    class EncryptionPipelineFactory:
        def __init__(self, secret_key=None, salt='requests-cache'):
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
                Signer(secret_key=self.secret_key, salt=self.salt),
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
except ImportError as e:
    class EncryptionPipelineFactory:
        def __init__(self,*args,**kwargs):
            raise ItsDangerousImportError

# Example usage
if __name__ == "__main__":
    factory = EncryptionPipelineFactory()
    serializer = factory.create_pipeline()
    session = CachedSession(serializer=serializer)
    response = session.get("https://docs.python.org/3/library/typing.html")
    cached_response = session.get("https://docs.python.org/3/library/typing.html")



###########################################

#from requests_cache.serializers.pipeline import SerializerPipeline, Stage
#from requests_cache.serializers.preconf import make_stage
#from requests_cache.serializers.cattrs import CattrStage
#from requests_cache import CachedSession
#from cryptography.fernet import Fernet
#from itsdangerous import Signer
#import pickle
#
#def encryption_stage(secret_key) -> Stage:
#    """Create a stage that uses Fernet encryption"""
#    fernet = Fernet(secret_key)
#
#    return Stage(
#        fernet,
#        dumps=fernet.encrypt,
#        loads=fernet.decrypt,
#    )
#
#def generate_secret_key():
#    """Generate a secret key for Fernet encryption"""
#    return Fernet.generate_key()
#
#def signer_stage(secret_key=None, salt='requests-cache') -> Stage:
#    """Create a stage that uses `itsdangerous` to add a signature to responses on write, and
#    validate that signature with a secret key on read.
#    """
#
#
#    return Stage(
#        Signer(secret_key=secret_key, salt=salt),
#        dumps='sign',
#        loads='unsign',
#    )
#
#def safe_pickle_serializer_with_encryption(secret_key=None, salt='requests-cache', **kwargs) -> SerializerPipeline:
#    """Create a serializer that uses pickle + itsdangerous for signing and cryptography for encryption"""
#    if secret_key is None:
#        secret_key = generate_secret_key()
#
#    base_stage = CattrStage()
#
#    return SerializerPipeline(
#        [base_stage, Stage(pickle), signer_stage(secret_key, salt), encryption_stage(secret_key)],
#        name='safe_pickle_with_encryption',
#        is_binary=True,
#    )
#
## Example usage
#if __name__ == "__main__":
#    secret_key = generate_secret_key()
#    serializer = safe_pickle_serializer_with_encryption(secret_key=secret_key)
#    session=CachedSession(serializer=serializer)
#    response=session.get("https://docs.python.org/3/library/typing.html")
#    cached_response=session.get("https://docs.python.org/3/library/typing.html")
#
#    # Example data to serialize
#    data = {'key': 'value'}
#
#    # Serialize and encrypt data
#    serialized_data = serializer.dumps(data)
#
#
#    fernet = Fernet(secret_key)
#    pickle.loads(fernet.decrypt(serialized_data))
#    pickle.loads(fernet.decrypt(serialized_data))
#
#    # Deserialize and decrypt data
#    deserialized_data = serializer.loads(serialized_data)
#    print(deserialized_data.__dict__)
#
#
