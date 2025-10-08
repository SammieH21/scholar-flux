import base64
import json
import binascii
from typing import Any, Optional
from typing import MutableMapping, MutableSequence
import logging

logger = logging.getLogger(__name__)


class CacheDataEncoder:
    """
    A utility class to encode data into a base64 string representation or decode it back from base64.

    This class supports encoding binary data (bytes) and recursively handles nested structures
    such as dictionaries and lists by encoding their elements, preserving the original structure upon decoding.

    This class is used to serialize json structures when the structure isn't known and contains unpredictable
    elements such as 1) None, 2) bytes, 3) nested lists, 4) Other unpredictable structures typically found in JSON

    Example:
        >>> from scholar_flux.utils import CacheDataEncoder
        >>> import json
        >>> data = {'note': 'hello', 'another_note': b'a non-serializable string', 'list': ['a', True, 'series' 'of', None]}
        >>> try:
        >>>     json.dumps(data)
        >>> except TypeError:
        >>>     print('The `data` is non-serializable as expected ')
        >>>
        >>> encoded_data = CacheDataEncoder.encode(data)
        >>> serialized_data = json.dumps(encoded_data)
        >>> assert data == CacheDataEncoder.decode(json.loads(serialized_data))
    """

    @classmethod
    def is_base64(cls, s: str | bytes, hash_prefix: Optional[str] = "<hashbytes>") -> bool:
        """
        Check if a given string is a valid base64 encoded string. Encoded strings can optionally
        be identified with a hash_prefix to streamline checks to determine whether or not to
        later decode a base64 encoded string.

        As a general heuristic when encoding and decoding base 64 objects, a string should be equal
        to its original value after encoding and decoding the string. In this implementation,
        we strip equals signs as minor differences in padding aren't relevant.

        Args:
            s (str | bytes): The string to check.
            hash_prefix (Optional[str]): The prefix to identify hash bytes. Defaults to '<hashbytes>'.

        Returns:
            bool: True if the string is base64 encoded, False otherwise.
        """
        if isinstance(s, (str, bytes)) and not s:
            return False

        if isinstance(s, str):
            # removes the hash_prefix if it exists, then encodes the data
            hash_prefix = hash_prefix or ""
            s_fmt = s.replace(hash_prefix, "", 1) if hash_prefix and s.startswith(hash_prefix) else s
            s_bytes = s_fmt.encode("utf-8")
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
            return base64.b64encode(base64.b64decode(s_bytes)).strip(b"=") == s_bytes.strip(b"=")
        except Exception:
            return False

    @classmethod
    def is_nonreadable(cls, s: bytes, p=0.5) -> bool:
        """
        Check if a decoded byte string contains a high percentage of non-printable characters.
        Non-printable characters are defined as those not within the unicode range of (32 <= c <= 126).

        Args:
            s (bytes): The byte string to check.
            p (float): The threshold percentage of non-printable characters. Defaults to 0.5.

        Returns:
            bool: True if the string is likely gibberish, False otherwise.
        """
        non_printable_count = sum(1 for c in s if not (32 <= c <= 126))
        return (
            non_printable_count > 1 and non_printable_count / len(s) > p
        )  # Threshold set at a proportion of p non-printable characters

    @classmethod
    def encode(cls, data: Any, hash_prefix: Optional[str] = "<hashbytes>") -> Any:
        """
        Recursively encodes all items that contain elements that cannot be directly serialized into JSON into
        a format more suitable for serialization:

            - Mappings are converted into dictionaries
            - Sets and other uncommon Sequences other than lists and tuples are converted into lists
            - Bytes objects are converted into strings and hashed with an optional prefix-identifier.

        Args:
            data (Any): The input data. This can be:
                * bytes: Encoded directly to a base64 string.
                * Mappings/Sequences/Sets/Tuples: Recursively encodes elements if they are bytes.
            hash_prefix (Optional[str]): The prefix to identify hash bytes. Defaults to '<hashbytes>'.

        Returns:
            Any: Encoded string (for bytes) or a dictionary/list/tuple
                 with recursively encoded elements.
        """

        match data:
            case bytes():
                return cls._encode_bytes(data, hash_prefix)
            case data if isinstance(data, MutableMapping):
                return cls._encode_dict(data, hash_prefix)
            case tuple():
                return cls._encode_tuple(data, hash_prefix)
            case data if isinstance(data, (MutableSequence, set)):
                return cls._encode_list(data, hash_prefix)
            case _:
                return data

    @classmethod
    def decode(cls, data: Any, hash_prefix: Optional[str] = "<hashbytes>") -> Any:
        """
        Recursively decodes base64 strings back to bytes or recursively decode elements within dictionaries and lists.

        Args:
            data (Any): The input data that needs decoding from a base64 encoded format.
                        This could be a base64 string or nested structures like dictionaries
                        and lists containing base64 strings as values.
            hash_prefix (Optional[str]): The prefix to identify hash bytes. Defaults to '<hashbytes>'.

        Returns:
            Any: Decoded bytes for byte-based representations or recursively decoded elements
                 within the dictionary/list/tuple if applicable.
        """
        match data:
            case None:
                return None
            case str():
                return cls._decode_string(data, hash_prefix)
            case dict():
                return cls._decode_dict(data, hash_prefix)
            case list():
                return cls._decode_list(data, hash_prefix)
            case tuple():
                return cls._decode_tuple(data, hash_prefix)

        return data  # Return unmodified non-decodable types

    @classmethod
    def _encode_bytes(cls, data: bytes, hash_prefix: Optional[str] = None) -> str:
        """
        Helper method for encoding a bytes objects into strings.

        Args:
            data (bytes): The bytes to encode.
            hash_prefix (Optional[str]): Prefix to prepend and identify the encoded string.

        Returns:
            str: The base64-encoded string, optionally prefixed.
        """

        try:
            hash_prefix = hash_prefix or ""
            return hash_prefix + base64.b64encode(data).decode("utf-8")
        except Exception as e:
            err = f"Error encoding element of {type(data)} into a base64 encoded string"
            logger.error(f"{err}: {e}")
            raise ValueError(f"{err}.") from e

    @classmethod
    def _encode_dict(cls, data: MutableMapping, hash_prefix: Optional[str] = None) -> dict:
        """
        Helper method for recursively encoding a mutable mapping containing encoded value into its original encoded
        representation.

        Args:
            data (MutableMapping): The MutableMapping or dictionary to encode.
            hash_prefix (Optional[str]): Prefix to prepend to recursively encoded strings.

        Returns:
            dict: A dictionary containing the recursively encoded elements.
        """
        # exact type comparison, ignores format
        if type(data) is not dict:  # noqa: E721
            logger.warning("Non-dictionary mutable mappings are coerced into dictionaries when encoded")
        try:
            return {key: cls.encode(value, hash_prefix) for key, value in data.items()}
        except Exception as e:
            err = f"Error encoding an element of type {type(data)} into a recursively encoded dictionary"
            logger.error(f"{err}: {e}")
            raise ValueError(f"{err}.") from e

    @classmethod
    def _encode_list(cls, data: MutableSequence | set, hash_prefix: Optional[str] = None) -> list:
        """
        Helper method for encoding a list containing encoded value into its original encoded representation.

        Args:
            data (MutableSequence | set): The MutableSequence, list, or set to encode.
            hash_prefix (Optional[str]): Prefix to prepend to recursively encoded strings.

        Returns:
            list: A list containing the recursively encoded elements
        """
        # exact type comparison, ignores format
        if type(data) is not list:  # noqa: E721
            logger.warning("Non-list/tuple mutable sequences are coerced into lists when encoded")
        try:
            return [cls.encode(item, hash_prefix) for item in data]
        except Exception as e:
            err = f"Error encoding an element of type {type(data)} into a recursively encoded list"
            logger.error(f"{err}: {e}")
            raise ValueError(f"{err}.") from e

    @classmethod
    def _encode_tuple(cls, data: tuple, hash_prefix: Optional[str] = None) -> tuple:
        """
        Helper method for encoding a tuple containing encoded value into its original encoded representation.

        Args:
            data (tuple): The tuple to encode.
            hash_prefix (Optional[str]): Prefix to prepend to recursively encoded strings.

        Returns:
            tuple: A tuple containing the recursively encoded elements
        ."""
        try:
            return tuple(cls.encode(item, hash_prefix) for item in data)
        except Exception as e:
            err = f"Error encoding an element of type {type(data)} into a recursively encoded tuple"
            logger.error(f"{err}: {e}")
            raise ValueError(f"{err}.") from e

    @classmethod
    def _decode_string(cls, data: str | bytes, hash_prefix: Optional[str] = None) -> str | bytes:
        """
        Helper method for decoding a string into bytes if possible. Otherwise the original string is returned.

        Args:
            data (str): The string to encode back into bytes if a bytes type.
            hash_prefix (Optional[str]): Optionally used to identify if the current string was encoded from bytes.

        Returns:
            str | bytes: A bytes object decoded from a base64 string if successful, otherwise returns the original str
        """

        if isinstance(hash_prefix, str) and isinstance(data, str) and not data.startswith(hash_prefix):
            return data

        try:
            data_string = data.decode("utf8") if isinstance(data, bytes) else data
            data_string = data_string.replace(hash_prefix, "", 1) if hash_prefix else data_string
            if not cls.is_base64(data_string):
                return data

            decoded_bytes = base64.b64decode(data_string.encode("utf-8"))
            if not hash_prefix and cls.is_nonreadable(decoded_bytes):
                return data  # Return original if decoded data is likely gibberish
            return decoded_bytes
        except (ValueError, TypeError) as e:
            logger.error(f"Failed to decode a value of type {type(data)} as bytes: {e}\nReturning original input...")
            return data  # Return original if decoding error occurs

    @classmethod
    def _decode_dict(cls, data: dict, hash_prefix: Optional[str] = None) -> dict:
        """
        Helper method for decoding a dictionary containing encoded value into its original decoded representation.

        Args:
            data (dict): The dictionary containing elements to recursively decode.
            hash_prefix (Optional[str]): Optional Prefix that identifies recursively encoded strings to decode.

        Returns:
            dict: A dictionary containing the recursively decoded elements
        """
        try:
            return {key: cls.decode(value, hash_prefix) for key, value in data.items()}
        except Exception as e:
            err = f"Failed to decode an element of type {type(data)} into a recursively decoded dictionary"
            logger.error(f"{err}: {e}")
            raise ValueError(f"{err}.") from e

    @classmethod
    def _decode_list(cls, data: list, hash_prefix: Optional[str] = None) -> list:
        """
        Helper method for decoding a recursively encoded list into its original decoded representation.

        Args:
            data (list): The list containing elements to recursively decode.
            hash_prefix (Optional[str]): Optional Prefix that identifies recursively encoded strings to decode.

        Returns:
            list: A list containing the recursively decoded elements
        """
        try:
            return [cls.decode(item, hash_prefix) for item in data]
        except Exception as e:
            err = f"Failed to decode an element of type {type(data)} into a recursively decoded list"
            logger.error(f"{err}: {e}")
            raise ValueError(f"{err}.") from e

    @classmethod
    def _decode_tuple(cls, data: tuple, hash_prefix: Optional[str] = None) -> tuple:
        """
        Helper method for decoding a recursively encoded tuple into its original decoded representation.

        Args:
            data (tuple): The tuple containing elements to recursively decode.
            hash_prefix (Optional[str]): Optional Prefix that identifies recursively encoded strings to decode.

        Returns:
            tuple: A tuple containing the recursively decoded elements
        """
        try:
            return tuple(cls.decode(item, hash_prefix) for item in data)
        except Exception as e:
            err = f"Failed to decode an element of type {type(data)} into a recursively decoded tuple"
            logger.error(f"{err}: {e}")
            raise ValueError(f"{err}.") from e


class JsonDataEncoder(CacheDataEncoder):
    """
    Helper class used to extend the CacheDataEncoder to provide functionality directly relevant
    to serializing and deserializing data from JSON formats into serialized JSON strings for
    easier storage and recovery.

    This method includes utility dumping and loading tools directly applicable to safely dumping
    and reloading responses received by various APIs.

    Example Use:
        >>> from scholar_flux.utils import JsonDataEncoder
        >>> data = {'note': 'hello', 'another_note': b'a non-serializable string',
        >>>         'list': ['a', True, 'series' 'of', None]}
        # serializes the original data even though it contains otherwise unserializable components
        >>> serialized_data = JsonDataEncoder.dumps(data)
        >>> assert isinstance(serialized_data, str)
        # deserializes the data, returning the original structure
        >>> recovered_data = json.loads(serialized_data)
        # the result should be the original string
        >>> assert data == recovered_data
        # OUTPUT: True
    """

    @classmethod
    def serialize(cls, data: Any, **json_kwargs) -> str:
        """
        Class method that encodes and serializes data to a JSON string.

        Args:
            data (Any): The data to encode and serialize as a json string.
            **json_kwargs: Additional keyword arguments for json.dumps.

        Returns:
            str: The JSON string.
        """
        encoded = cls.encode(data)
        return cls.dumps(encoded, **json_kwargs)

    @classmethod
    def deserialize(cls, s: str, **json_kwargs) -> Any:
        """
        Class method that deserializes and decodes json data from a JSON string.

        Args:
            s (str): The JSON string to deserialize and decode.
            **json_kwargs: Additional keyword arguments for json.loads.

        Returns:
            Any: The decoded data.
        """
        loaded = cls.loads(s, **json_kwargs)
        return cls.decode(loaded)

    @classmethod
    def dumps(cls, data: Any, **json_kwargs) -> str:
        """
        Convenience method that uses the `json` module to serialize (dump) JSON
        data into a JSON string.

        Args:
            data (Any): The data to serialize as a json string.
            **json_kwargs: Additional keyword arguments for json.dumps.

        Returns:
            str: The JSON string.
        """
        return json.dumps(data, **json_kwargs)

    @classmethod
    def loads(cls, s: str, **json_kwargs) -> Any:
        """
        Convenience method that uses the `json` module to deserialize (load) from a JSON string.

        Args:
            s (str): The JSON string to deserialize and decode.
            **json_kwargs: Additional keyword arguments for json.loads.

        Returns:
            Any: The loaded json data.
        """
        return json.loads(s, **json_kwargs)


# if __name__ == "__main__":
#     # Example usage of CacheDataEncoder class
#     try:
#         original_data = b"example data"
#         encoded_data = CacheDataEncoder.encode(original_data)
#         print(f"Encoded: {encoded_data}")
#
#         decoded_data = CacheDataEncoder.decode(encoded_data)
#         print(f"Decoded: {decoded_data}")
#
#         # Test with a non-byte string
#         original_string = "1728"
#         encoded_string = CacheDataEncoder.encode(original_string)
#         print(f"Encoded string: {encoded_string}")
#
#         decoded_string = CacheDataEncoder.decode(encoded_string)
#         print(f"Decoded string: {decoded_string}")
#
#     except ValueError as e:
#         logger.error(f"An error occurred: {e}")
