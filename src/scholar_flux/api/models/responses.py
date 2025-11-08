# /api/models/responses.py
"""The scholar_flux.api.models.responses module contains the core response types used to indicate whether the retrieval
and processing of API responses was successful or unsuccessful. Each class uses pydantic to ensure type-validated
responses while ensuring flexibility in how responses can be used and applied.

Classes:
    ProcessedResponse:
        Indicates whether an API was successfully retrieved, parsed, and processed. This model is designed to
        facilitate the inspection of intermediate results and retrieval of extracted response records.
    ErrorResponse:
        Indicates that an error occurred somewhere in the retrieval or processing of an API response. This
        class is designed to allow inspection of error messages and failure results to aid in debugging in case
        of unexpected scenarios.
    NonResponse:
        Inherits from ErrorResponse and is designed to indicate that an error occurred in the preparation of a
        request or the sending/retrieval of a response.

"""
from typing import Optional, Dict, List, Any, MutableMapping
from scholar_flux.exceptions import InvalidResponseReconstructionException
from typing_extensions import Self
from pydantic import BaseModel, field_serializer, field_validator
from scholar_flux.api.models.reconstructed_response import ReconstructedResponse
from scholar_flux.utils.helpers import generate_iso_timestamp, parse_iso_timestamp, format_iso_timestamp
from scholar_flux.utils import CacheDataEncoder, generate_repr
from scholar_flux.utils.response_protocol import ResponseProtocol
from scholar_flux.api.validators import validate_url
from datetime import datetime
from http.client import responses
from scholar_flux.utils import try_int
from json import JSONDecodeError
import json
import logging
import requests

logger = logging.getLogger(__name__)


class APIResponse(BaseModel):
    """A Response wrapper for responses of different types that allows consistency when using several possible backends.
    The purpose of this class is to serve as the base for managing responses received from scholarly APIs while
    processing each component in a predictable, reproducible manner,

    This class uses pydantic's data validation and serialization/deserialization methods to aid caching and includes
    properties that refer back to the original response for displaying valid response codes, URLs, etc.

    All future processing/error-based responses classes inherit from and build off of this class.

    Args:
        cache_key (Optional[str]): A string for recording cache keys for use in later steps of the response
                                   orchestration involving processing, cache storage, and cache retrieval
        response (Any): A response or response-like object to be validated and used/re-used in later caching
                        and response processing/orchestration steps.
        created_at (Optional[str]): A value indicating the time in which a response or response-like object was created.

    Example:
        >>> from scholar_flux.api import APIResponse
        # Using keyword arguments to build a basic APIResponse data container:
        >>> response = APIResponse.from_response(
        >>>     cache_key = 'test-response',
        >>>     status_code = 200,
        >>>     content=b'success',
        >>>     url='https://example.com',
        >>>     headers={'Content-Type': 'application/text'}
        >>> )
        >>> response
        # OUTPUT: APIResponse(cache_key='test-response', response = ReconstructedResponse(
        #    status_code=200, reason='OK', headers={'Content-Type': 'application/text'},
        #    text='success', url='https://example.com'
        #)
        >>> assert response.status == 'OK' and response.text == 'success' and response.url == 'https://example.com'
        # OUTPUT: True
        >>> assert response.validate_response()
        # OUTPUT: True

    """

    cache_key: Optional[str] = None
    response: Optional[Any] = None
    created_at: Optional[str] = None

    @field_validator("created_at", mode="before")
    def validate_iso_timestamp(cls, v: Optional[str | datetime]) -> Optional[str]:
        """Helper method for validating and ensuring that the timestamp accurately follows an iso 8601 format."""
        if not v:
            return None

        if isinstance(v, str):
            if not parse_iso_timestamp(v):
                logger.warning(f"Expected a parsed timestamp but received an unparseable value: {v}")
                return None

        elif isinstance(v, datetime):
            v = format_iso_timestamp(v)

        else:
            logger.warning(f"Expected an iso8601-formatted datetime, Received type ({type(v)})")
            return None

        return v

    @field_validator("response", mode="after")
    def transform_response(cls, v: Any) -> Optional[requests.Response | ResponseProtocol]:
        """Attempts to resolve a response object as an original or
        ReconstructedResponse: All original response objects (duck-typed or
        requests response) with valid values will be returned as is.

        If the passed object is a string - this function will attempt to serialize it before
        attempting to parse it as a dictionary.

        Dictionary fields will be decoded, if originally encoded, and parsed as a ReconstructedResponse object,
        if possible.

        Otherwise, the original object is returned as is.
        """

        if isinstance(v, (requests.Response, ReconstructedResponse)) or cls._is_response_like(v):
            return v
        try:
            v = cls.from_serialized_response(v)
            if v is not None:
                return v
        except (TypeError, JSONDecodeError, AttributeError) as e:
            logger.warning(f"Couldn't decode a valid response object: {e}")
        logger.warning("Couldn't decode a valid response object. Returning the object as is")
        return v

    @property
    def status_code(self) -> Optional[int]:
        """Helper property for retrieving a status code from the APIResponse.

        Returns:
            Optional[int]: The status code associated with the response (if available)

        """
        try:
            status_code = getattr(self.response, "status_code", None)
            return status_code if isinstance(status_code, int) else try_int(status_code)
        except (ValueError, AttributeError):
            return None

    @property
    def reason(self) -> Optional[str]:
        """Uses the underlying reason attribute on the response object, if available, to create a human readable status
        description.

        Returns:
            Optional[str]: The status description associated with the response.

        """
        reason = getattr(self.response, "reason", None)
        reason = reason if reason else responses.get(self.status_code or -1)
        if isinstance(reason, str):
            return reason
        return None

    @property
    def status(self) -> Optional[str]:
        """Helper property for retrieving a human-readable status description APIResponse.

        Returns:
            Optional[int]: The status description associated with the response (if available).

        """
        return self.reason or getattr(self.response, "status", None) or responses.get(self.status_code or -1)

    @property
    def headers(self) -> Optional[MutableMapping[str, str]]:
        """Return headers from the underlying response, if available and valid.

        Returns:
            MutableMapping[str, str]: A dictionary of headers from the response

        """
        if self.response is not None:
            headers = getattr(self.response, "headers", None)
            if isinstance(headers, (dict, MutableMapping)):
                return dict(headers)
            logger.warning("The current APIResponse does not have a valid response header")
        return None

    @property
    def content(self) -> Optional[bytes]:
        """Return content from the underlying response, if available and valid.

        Returns:
            (bytes): The bytes from the original response content

        """
        if self.response is not None:
            content = getattr(self.response, "content", None)
            if isinstance(content, str):
                return content.encode("utf-8")
            if isinstance(content, bytes):
                return content
            logger.warning("The current APIResponse does not have a valid response content attribute")
        return None

    @property
    def text(self) -> Optional[str]:
        """Attempts to retrieve the response text by first decoding the bytes of the its content. If not available, this
        property attempts to directly reference the text attribute directly.

        Returns:
            Optional[str]: A text string if the text is available in the correct format, otherwise None

        """
        if self.response is not None:
            #
            text = self.content.decode("utf-8") if self.content is not None else getattr(self.response, "text", None)

            if isinstance(text, str):
                return text
            logger.warning("The current APIResponse does not have a valid response text attribute")
        return None

    @property
    def url(self) -> Optional[str]:
        """Return URL from the underlying response, if available and valid.

        Returns:
            str: A string of the original URL if available. Accounts for objects that
                 that indicate the original url when converted as a string

        """
        url = getattr(self.response, "url", None)

        if url:
            url_string = url if isinstance(url, str) else str(url)

            return url_string if validate_url(url_string) else None
        return None

    def validate_response(self) -> bool:
        """Helper method for determining whether the response attribute is truly a response. If the response isn't a
        requests response, we use duck-typing to determine whether the response attribute, itself, has the expected
        attributes of a response by using properties for checking types vs None (if the attribute isn't the expected
        type)

        Returns:
            bool: An indicator of whether the current APIResponse.response attribute is
                  actually a response

        """
        if isinstance(self.response, requests.Response):
            return True

        return self._is_response_like(self)

    @classmethod
    def _is_response_like(cls, response: Any) -> bool:
        """Helper method for validating whether each of the core components of a response are populated with the correct
        response types or are instead missing.

        The following properties that refer back to the original response should be available:

            1. status_code: (int)
            2. reason: string
            3. headers: dictionary
            4. content: bytes
            5. url: string or URL-like field

        """
        if not isinstance(response, ResponseProtocol):
            return False

        # e.g. status code, reason, headers, content, ir;
        response_like = all(
            getattr(response, attribute, None) is not None for attribute in ReconstructedResponse.fields()
        )
        return response_like

    @classmethod
    def from_response(
        cls,
        response: Optional[Any] = None,
        cache_key: Optional[str] = None,
        auto_created_at: Optional[bool] = None,
        **kwargs,
    ) -> Self:
        """Construct an APIResponse from a response object or from keyword arguments.

        If response is not a valid response object, builds a minimal response-like object from kwargs.

        """

        model_kwargs = {field: kwargs.pop(field, None) for field in cls.model_fields if field in kwargs}

        response = (
            ReconstructedResponse.build(response, **kwargs) if not isinstance(response, requests.Response) else response
        )

        if auto_created_at is True and not model_kwargs.get("created_at"):
            model_kwargs["created_at"] = generate_iso_timestamp()
        return cls(response=response, cache_key=cache_key, **model_kwargs)

    @field_serializer("response", when_used="json")
    def encode_response(self, response: Any) -> Optional[Dict[str, Any] | List[Any]]:
        """Helper method for serializing a response into a json format. Accounts for special cases such as
        CaseInsensitiveDict fields that are otherwise unserializable.

        From this step, pydantic can safely use json internally to dump the encoded response fields

        """
        if isinstance(response, (requests.Response, ReconstructedResponse)) or self._is_response_like(response):
            return self._encode_response(response)
        return None

    @classmethod
    def serialize_response(cls, response: requests.Response | ResponseProtocol) -> Optional[str]:
        """Helper method for serializing a response into a json format. The response object is first converted into a
        serialized string and subsequently dumped after ensuring that the field is serializable.

        Args:
            response (Response, ResponseProtocol)

        """
        try:
            encoded_response = cls._encode_response(response)

            if encoded_response:
                return json.dumps(encoded_response)
        except (InvalidResponseReconstructionException, TypeError, AttributeError, UnicodeEncodeError) as e:
            logger.error(
                f"Could not encode the value of type {type(response)} into a serialized json object "
                f"due to an error: {e}"
            )

        return None

    @classmethod
    def _encode_response(cls, response: requests.Response | ResponseProtocol) -> Dict[str, Any]:
        """Helper method for encoding a response using a ReconstructedResponse to store the core fields for responses
        and response-like objects.

        Elements from the response are first extracted from the response object using the ReconstructedResponse data
        model. After extracting the fields from the model as a dictionary, the fields are subsequently encoded using
        the scholar_flux.utils.CacheDataEncoder that ensures all fields are encodable.

        Afterward, the dictionary can safely be serialized via json.dumps.

        Note that fields such as CaseInsensitiveDicts and other MutableMappings are converted to dictionaries
        to support the process of encoding each field.

        Args:
            response: A response or response-like object whose core fields are be encoded

        Returns:
            Dict[str, Any]: A dictionary formatted in a way that enables core fields to be encoded
                            using json.dumps function from the json module in the standard library that
                            serializes dictionaries into strings.

        """
        reconstructed_response = ReconstructedResponse.build(response)
        response_dictionary = CacheDataEncoder.encode(reconstructed_response.asdict())
        return response_dictionary

    @classmethod
    def _decode_response(cls, encoded_response_dict: Dict[str, Any], **kwargs) -> Optional[ReconstructedResponse]:
        """Helper method for decoding a dictionary of encoded fields that were previously encoded using
        _encode_response. This class approximately creates the previous response object by creating a
        ReconstructedResponse that retains core fields from the original response to support the orchestration of
        response processing and caching.

        Args:
            encoded_response_dict (Dict[str, Any]):
                Contains a list of all encoded dictionary-based elements of the original response or response-like
                object.
            **kwargs:
                Any keyword-based overrides to use when building a request from the decoded response dictionary
                when the same values in the decoded_response are otherwise missing

        Returns:
            Optional[ReconstructedResponse]:
                Creates a reconstructed response with from the original encoded fields.

        """
        field_set = set(ReconstructedResponse.fields())

        response_dict = (
            encoded_response_dict.get("response")
            if not field_set.intersection(encoded_response_dict)
            and isinstance(encoded_response_dict, dict)
            and "response" in encoded_response_dict
            else encoded_response_dict
        )

        decoded_response = CacheDataEncoder.decode(response_dict) or {}

        decoded_response.update(
            {field: value for field, value in kwargs.items() if decoded_response.get(field) is None}
        )

        return ReconstructedResponse.build(**decoded_response)

    @classmethod
    def from_serialized_response(cls, response: Optional[Any] = None, **kwargs) -> Optional[ReconstructedResponse]:
        """Helper method for creating a new APIresponse from the original dumped object. This method Accounts for lack
        of ease of serialization of responses by decoding the response dictionary that was loaded from a string using
        json.loads from the json module in the standard library.

        If the response input is still a serialized string, this method will manually load the response dict with
        the `APIresponse._deserialize_response_dict` class method before further processing.

        Args:
            response (Any):  A prospective response value to load into the API Response.

        Returns:
            Optional[ReconstructedResponse]: A reconstructed response object, if possible. Otherwise returns None

        """

        if isinstance(response, str):
            response = cls._deserialize_response_dict(response)

        if isinstance(response, dict):
            return cls._decode_response(response, **kwargs)

        elif kwargs:
            return ReconstructedResponse.build(**kwargs)
        return None

    @classmethod
    def as_reconstructed_response(cls, response: Any) -> ReconstructedResponse:
        """Classmethod designed to create a reconstructed response from an original response object. This method coerces
        response attributes into a reconstructed response that retains the original content, status code, headers, URL,
        reason, etc.

        Returns:
            ReconstructedResponse: A minimal response object that contains the core attributes needed to support
                                   other processes in the scholar_flux module such as response parsing and caching.

        """

        if isinstance(response, APIResponse):
            response = response.response

        return ReconstructedResponse.build(response)

    def __eq__(self, other: Any) -> bool:
        """Helper method for validating whether responses are equal. Elements of the same type are considered a
        necessary quality for processing components to be considered equal.

        Args:
            other (Any): An object to compare against the current APIResponse object/subclass

        Returns:
            bool: True if the value is equal to the current APIResponse object, otherwise False

        """
        # accounting for subclasses:
        if not isinstance(other, self.__class__):
            return False

        return self.model_dump(exclude={"created_at"}) == other.model_dump(exclude={"created_at"})

    @classmethod
    def _deserialize_response_dict(cls, serialized_response_dict: str) -> Optional[dict]:
        """Helper method for deserializing the dumped model json.

        Attempts to load json data from a string if possible. Otherwise returns None

        """
        try:
            deserialized_dict = json.loads(serialized_response_dict)
            return deserialized_dict
        except (JSONDecodeError, TypeError) as e:
            logger.warning(f"Could not decode the response argument from a string to JSON object: {e}")
        return None

    def raise_for_status(self):
        """Uses an underlying response object to validate the status code associated with the request.

        If the attribute isn't a response or reconstructed response, the code will coerce the class into a response
        object to verify the status code for the request URL and response.

        """

        if self.response is not None and isinstance(self.response, (requests.Response, ReconstructedResponse)):
            self.response.raise_for_status()
        else:
            self.as_reconstructed_response(self.response).raise_for_status()

    def __repr__(self) -> str:
        """Helper method for generating a simple representation of the current API Response."""
        return generate_repr(
            self,
            exclude={
                "created_at",
            },
        )


class ErrorResponse(APIResponse):
    """Returned when something goes wrong, but we don’t want to throw immediately—just hand back failure details.

    The class is formatted for compatibility with the ProcessedResponse,

    """

    message: Optional[str] = None
    error: Optional[str] = None

    @classmethod
    def from_error(
        cls,
        message: str,
        error: Exception,
        cache_key: Optional[str] = None,
        response: Optional[requests.Response | ResponseProtocol] = None,
    ) -> Self:
        """Creates and logs the processing error if one occurs during response processing.

        Args:
            response (Response): Raw API response.
            cache_key (Optional[str]): Cache key for storing results.

        Returns:
            ErrorResponse: A Dataclass Object that contains the error response data
                            and background information on what precipitated the error.

        """

        creation_timestamp = generate_iso_timestamp()
        return cls(
            cache_key=cache_key,
            response=response.response if isinstance(response, APIResponse) else response,
            message=message,
            error=type(error).__name__,
            created_at=creation_timestamp,
        )

    @property
    def parsed_response(self) -> None:
        """Provided for type hinting + compatibility."""
        return None

    @property
    def extracted_records(self) -> None:
        """Provided for type hinting + compatibility."""
        return None

    @property
    def processed_records(self) -> None:
        """Provided for type hinting + compatibility."""
        return None

    @property
    def metadata(self) -> None:
        """Provided for type hinting + compatibility."""
        return None

    @property
    def data(self) -> None:
        """Provided for type hinting + compatibility."""
        return self.processed_records

    def __repr__(self) -> str:
        """Helper method for creating a string representation of the underlying ErrorResponse."""
        return f"ErrorResponse(status_code={self.status_code}, error={self.error}, " f"message={self.message!r})"

    def __len__(self) -> int:
        """Helper method added for compatibility with the use-case of the ProcessedResponse.

        Always returns 0, indicating that no records were successfully processed.

        """
        return 0

    def __bool__(self):
        """Indicates that the underlying response was not successfully processed or contained an error code."""
        return False


class NonResponse(ErrorResponse):
    """Response class used to indicate that an error occurred in the preparation of a request or in the retrieval of a
    response object from an API.

    This class is used to signify the error that occurred within the search process using a similar interface as the
    other scholar_flux Response dataclasses.

    """

    response: None = None

    def __repr__(self) -> str:
        """Helper method for creating a string representation of the underlying ErrorResponse."""
        return f"NonResponse(error={self.error}, " f"message={self.message!r})"


class ProcessedResponse(APIResponse):
    """Helper class for returning a ProcessedResponse object that contains information on the original, cached, or
    reconstructed_response received and processed after retrieval from an API in addition to the cache key. This object
    also allows storage of intermediate steps including:

    1) parsed responses     2) extracted records and metadata     3) processed records (aliased as data)     4) any
    additional messages An error field is provided for compatibility with the ErrorResponse class.

    """

    parsed_response: Optional[Any] = None
    extracted_records: Optional[List[Any]] = None
    processed_records: Optional[List[Dict[Any, Any]]] = None
    metadata: Optional[Any] = None
    message: Optional[str] = None

    @property
    def data(self) -> Optional[List[Dict[Any, Any]]]:
        """Alias to the processed_records attribute that holds a list of dictionaries, when available."""
        return self.processed_records

    @property
    def error(self) -> None:
        """Provided for type hinting + compatibility."""
        return None

    def __repr__(self) -> str:
        """Helper method for creating a simple representation of the ProcessedResponse."""
        return (
            f"ProcessedResponse(len={len(self.processed_records or [])}, "
            f"cache_key={self.cache_key!r}, "
            f"metadata={'{'+str(self.metadata)[1:40]+'...'+'}' if isinstance(self.metadata, (dict, list, str)) and self.metadata else self.metadata!r})"
        )

    def __len__(self) -> int:
        """Indicates the overall length of the processed data field as processed in the last step after filtering."""
        return len(self.processed_records or [])

    def __bool__(self) -> bool:
        """Returns true to indicate that processing was successful, independent of the number of processed records."""
        return True


__all__ = ["APIResponse", "ProcessedResponse", "ErrorResponse", "NonResponse"]
