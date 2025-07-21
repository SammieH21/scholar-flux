import base64
import binascii
from typing import Any, Union, Optional
import logging

logger = logging.getLogger(__name__)

class CacheDataEncoder:
    """
    A utility class to encode data into a base64 string representation or decode it back from base64.

    This class supports encoding binary data (bytes) and recursively handles nested structures
    such as dictionaries and lists by encoding their elements, preserving the original structure upon decoding.
    """

    @staticmethod
    def is_base64(s: Union[str, bytes], hash_prefix: Optional[str] ='<hashbytes>') -> bool:
        """
        Check if a given string is a valid base64 encoded string.

        Args:
            s (Union[str, bytes]): The string to check.
            hash_prefix (Optional[str]): The prefix to identify hash bytes. Defaults to '<hashbytes>'.

        Returns:
            bool: True if the string is base64 encoded, False otherwise.
        """
        if isinstance(s, str):
            # removes the hash_prefix if it exists, then encodes the data
            hash_prefix = hash_prefix or ''
            s_fmt = s.replace(hash_prefix, '', 1) if hash_prefix and s.startswith(hash_prefix) else s
            s_bytes = s_fmt.encode('utf-8')
        elif isinstance(s, bytes):
            s_bytes = s
        else:
            raise ValueError("Argument must be string or bytes")

        # Base64 strings should have a length that's a multiple of 4
        if len(s_bytes) % 4 != 0:
            return False

        # Check for only valid base64 characters
        try:
            base64.b64decode(s_bytes, validate=True)
        except (binascii.Error, ValueError):
            return False

        # Validate by encoding and decoding
        try:
            if base64.b64encode(base64.b64decode(s_bytes)).strip(b'=') == s_bytes.strip(b'='):
                return True
            else:
                return False
        except Exception:
            return False

    @staticmethod
    def is_nonreadable(s: bytes, p = .5) -> bool:
        """
        Check if a decoded string contains a high percentage of non-printable characters.

        Args:
            s (bytes): The byte string to check.
            p (float): The threshold percentage of non-printable characters. Defaults to 0.5.

        Returns:
            bool: True if the string is likely gibberish, False otherwise.
        """
        non_printable_count = sum(1 for c in s if not (32 <= c <= 126))
        return non_printable_count > 1 and non_printable_count / len(s) > p  # Threshold set at a proportion of p non-printable characters

    @staticmethod
    def encode(data: Any, hash_prefix: Optional[str] ='<hashbytes>') -> Any:
        """
        Encode data to a base64 string representation or dictionary.

        Args:
            data (Any): The input data. This can be:
                * bytes: Encoded directly to a base64 string.
                * dict/list/tuple: Recursively encodes elements if they are bytes.
            hash_prefix (Optional[str]): The prefix to identify hash bytes. Defaults to '<hashbytes>'.
        Returns:
            Any: Encoded string (for bytes) or a dictionary/list/tuple
                 with recursively encoded elements.
        """

        # if data == 'None':
        #     return '<<None>>'

        if isinstance(data, bytes):
            try:
                hash_prefix = hash_prefix or ''
                return hash_prefix + base64.b64encode(data).decode('utf-8')
            except Exception as e:
                logger.error(f"Error encoding bytes to base64: {e}")
                raise ValueError("Failed to encode bytes to base64.") from e

        elif isinstance(data, dict):
            try:
                return {key: CacheDataEncoder.encode(value) for key, value in data.items()}
            except Exception as e:
                logger.error(f"Error encoding a dictionary element to base64: {e}")
                raise ValueError("Failed to encode dictionary element to base64.") from e

        elif isinstance(data, list):
            try:
                return [CacheDataEncoder.encode(item) for item in data]
            except Exception as e:
                logger.error(f"Error encoding a list element to base64: {e}")
                raise ValueError("Failed to encode list element to base64.") from e

        elif isinstance(data, tuple):
            try:
                return tuple(CacheDataEncoder.encode(item) for item in data)
            except Exception as e:
                logger.error(f"Error encoding a tuple element to base64: {e}")
                raise ValueError("Failed to encode tuple element to base64.") from e



        return data  # Return unmodified non-encodable types

    @staticmethod
    def decode(data: Any, hash_prefix: Optional[str] ='<hashbytes>') -> Any:
        """
        Decode base64 string back to bytes or recursively decode elements within dictionaries and lists.

        Args:
            data (Any): The input data that needs decoding from a base64 encoded format.
                        This could be a base64 string or nested structures like dictionaries
                        and lists containing base64 strings as values.
            hash_prefix (Optional[str]): The prefix to identify hash bytes. Defaults to '<hashbytes>'.

        Returns:
            Any: Decoded bytes for byte-based representations or recursively decoded elements
                 within the dictionary/list/tuple if applicable.
        """
        if data is None:
            return None

        if isinstance(hash_prefix, str) and isinstance(data,str) and not data.startswith(hash_prefix):
            return data

        if isinstance(data, str):
            try:
                data_fmt = data.replace(hash_prefix, '', 1) if hash_prefix is not None else data
                if not CacheDataEncoder.is_base64(data_fmt):
                    return data

                decoded_bytes = base64.b64decode(data_fmt)
                if not hash_prefix and CacheDataEncoder.is_nonreadable(decoded_bytes):
                    return data  # Return original if decoded data is likely gibberish
                return decoded_bytes
            except (ValueError, TypeError) as e:
                logger.error(f"Invalid or malformed base64 data; returning original input. {e}")
                return data  # Return original if decoding error occurs

        elif isinstance(data, dict):
            try:
                return {key: CacheDataEncoder.decode(value) for key, value in data.items()}
            except Exception as e:
                logger.error(f"Error decoding a dictionary element from base64: {e}")
                raise ValueError("Failed to decode dictionary element from base64.") from e

        elif isinstance(data, list):
            try:
                return [CacheDataEncoder.decode(item) for item in data]
            except Exception as e:
                logger.error(f"Error decoding a list element from base64: {e}")
                raise ValueError("Failed to decode list element from base64.") from e

        elif isinstance(data, tuple):
            try:
                return tuple(CacheDataEncoder.decode(item) for item in data)
            except Exception as e:
                logger.error(f"Error decoding a tuple element from base64: {e}")
                raise ValueError("Failed to decode tuple element from base64.") from e

        return data  # Return unmodified non-decodable types

if __name__ == '__main__':
    # Example usage of CacheDataEncoder class
    try:
        original_data = b"example data"
        encoded_data = CacheDataEncoder.encode(original_data)
        print(f"Encoded: {encoded_data}")

        decoded_data = CacheDataEncoder.decode(encoded_data)
        print(f"Decoded: {decoded_data}")

        # Test with a non-byte string
        original_string = "1728"
        encoded_string = CacheDataEncoder.encode(original_string)
        print(f"Encoded string: {encoded_string}")

        decoded_string = CacheDataEncoder.decode(encoded_string)
        print(f"Decoded string: {decoded_string}")

    except ValueError as e:
        logger.error(f"An error occurred: {e}")

