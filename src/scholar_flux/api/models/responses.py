# /api/models/responses.py
"""The scholar_flux.api.models.responses module contains the core response types used during API response retrieval.

These responses are designed to indicate whether the retrieval and processing of API responses was successful or
unsuccessful while also storing relevant fields that aid in post-retrieval diagnostics. Each class uses pydantic to
ensure type-validated responses while also ensuring flexibility in how responses can be used and applied.

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
from scholar_flux.exceptions import InvalidResponseReconstructionException, RecordNormalizationException
from typing_extensions import Self
from pydantic import BaseModel, field_serializer, field_validator
from scholar_flux.api.models.reconstructed_response import ReconstructedResponse
from scholar_flux.utils.helpers import generate_iso_timestamp, parse_iso_timestamp, format_iso_timestamp, coerce_int
from scholar_flux.utils import CacheDataEncoder, generate_repr, generate_repr_from_string, truncate
from scholar_flux.utils.response_protocol import ResponseProtocol
from scholar_flux.api.validators import validate_url
from scholar_flux.api.providers import provider_registry
from scholar_flux.api.normalization.base_field_map import BaseFieldMap
from scholar_flux.api.models.response_metadata_map import ResponseMetadataMap
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
    processing each component in a predictable, reproducible manner.

    This class uses pydantic's data validation and serialization/deserialization methods to aid caching and includes
    properties that refer back to the original response for displaying valid response codes, URLs, etc.

    All future processing/error-based responses classes inherit from and build off of this class.

    Args:
        cache_key (Optional[str]): A string for recording cache keys for use in later steps of the response
                                   orchestration involving processing, cache storage, and cache retrieval
        response (Any): A response or response-like object to be validated and used/re-used in later caching
                        and response processing/orchestration steps.
        created_at (Optional[str]): A value indicating the time at which a response or response-like object was created.

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
        """Helper method for validating and ensuring that the timestamp accurately follows an ISO 8601 format."""
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
        """Attempts to resolve a valid or a serialized response-like object as an original or `ReconstructedResponse`.

        All original response objects (duck-typed or requests response) with valid values will be returned as is.

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
        """Uses the reason or status code attribute on the response object, to retrieve or create a status description.

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
        """Attempts to retrieve the response text by first decoding the bytes of its content.

        If not available, this property attempts to directly reference the text attribute directly.

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
            str: The original URL in string format, if available. For URL objects that are not `str` types, this method
                 attempts to convert them into strings when possible.

        """
        url = getattr(self.response, "url", None)

        if url:
            url_string = url if isinstance(url, str) else str(url)

            return url_string if validate_url(url_string) else None
        return None

    def validate_response(self) -> bool:
        """Helper method for determining whether the response attribute is truly a response or response-like object.

        If the response isn't a requests.Response object, we use duck-typing to determine whether the response, itself,
        contains the attributes expected of a response. For this purpose, response properties are checked in order to
        determine whether the response properties match the expected types. Each property returns `None` if the
        attribute isn't of the expected type.

        Returns:
            bool: An indicator of whether the current `APIResponse.response` attribute is actually a valid response

        """
        if isinstance(self.response, requests.Response):
            return True

        return self._is_response_like(self)

    @classmethod
    def _is_response_like(cls, response: Any) -> bool:
        """Validates whether each of the core components of a response are populated with the correct response types.

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
        """Helper method for serializing a response into a json format.

        Accounts for special cases such as `CaseInsensitiveDict` fields that are otherwise unserializable.

        From this step, pydantic can safely use json internally to dump the encoded response fields

        """
        if isinstance(response, (requests.Response, ReconstructedResponse)) or self._is_response_like(response):
            return self._encode_response(response)
        return None

    @classmethod
    def serialize_response(cls, response: requests.Response | ResponseProtocol) -> Optional[str]:
        """Helper method for serializing a response into a json format.

        The response object is first converted into a serialized string and subsequently dumped after ensuring that the
        field is serializable.

        Args:
            response (Response, ResponseProtocol)

        Returns:
            Optional[str]: A serialized response when response serialization is possible. Otherwise None.

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
        """Encodes a response using a `ReconstructedResponse` to store core fields from response-like objects.

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
        """Helper method for decoding a dict of encoded fields that were previously encoded using _encode_response.

        This class approximately creates the previous response object by creating a `ReconstructedResponse` that
        retains core fields from the original response to support the orchestration of response processing and caching.

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
        """Helper method for creating a new `APIresponse` from dumped json object.

        This method accounts for lack of ease of serialization of responses by decoding the response dictionary that was
        loaded from a string using json.loads from the json module in the standard library.

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
        """Classmethod designed to create a reconstructed response from an original response object.

        This method coerces response attributes into a reconstructed response that retains the original content, status
        code, headers, URL, reason, etc.

        Returns:
            ReconstructedResponse: A minimal response object that contains the core attributes needed to support
                                   other processes in the scholar_flux module such as response parsing and caching.

        """
        if isinstance(response, APIResponse):
            response = response.response

        return ReconstructedResponse.build(response)

    def __eq__(self, other: Any) -> bool:
        """Helper method for validating whether responses are equal.

        Elements of the same type are considered a necessary quality for processing components to be considered equal.

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

        Raises:
            requests.RequestException: Errors for status codes that indicate unsuccessfully received responses.

        """
        if self.response is not None and isinstance(self.response, (requests.Response, ReconstructedResponse)):
            self.response.raise_for_status()
        else:
            self.as_reconstructed_response(self.response).raise_for_status()

    def process_metadata(self, *args, **kwargs) -> Optional[dict[str, Any]]:
        """Abstract processing method that successfully `APIResponse` subclasses can override to process_metadata.

        Args:
            *args: No-Op - Added for compatibility with the `APIResponse` subclasses.
            *kwargs: No-Op - Added for compatibility with the `APIResponse` subclasses.

        Raises:
            NotImplementedError: Unless overridden, this method will raise an error unless defined in a subclass.

        """
        raise NotImplementedError(
            f"Metadata processing is not implemented for responses of type, {self.__class__.__name__}"
        )

    def normalize(self, *args, **kwargs) -> Optional[list[dict[str, Any]]]:
        """Defines the `normalize` method that successfully processed API Responses can override to normalize records.

        Raises:
            NotImplementedError: Unless overridden, this method will raise an error unless defined in a subclass.

        """
        raise NotImplementedError(f"Normalization is not implemented for responses of type, {self.__class__.__name__}")

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
    def normalized_records(self) -> None:
        """Provided for type hinting + compatibility."""
        return None

    @property
    def metadata(self) -> None:
        """Provided for type hinting + compatibility."""
        return None

    @property
    def processed_metadata(self) -> None:
        """Provided for type hinting + compatibility."""
        return None

    @property
    def total_query_hits(self) -> None:
        """Provided for type hinting + compatibility."""
        return None

    @property
    def records_per_page(self) -> None:
        """Provided for type hinting + compatibility."""
        return None

    @property
    def data(self) -> None:
        """Provided for type hinting + compatibility."""
        return self.processed_records

    @property
    def record_count(self) -> int:
        """Number of records in this response."""
        return 0

    def __repr__(self) -> str:
        """Helper method for creating a string representation of the underlying ErrorResponse."""
        return generate_repr_from_string(
            self.__class__.__name__,
            {
                "status_code": self.status_code,
                "error": self.error,
                "message": self.message,
            },
            flatten=True,
        )

    def __len__(self) -> int:
        """Helper method added for compatibility with the use-case of the ProcessedResponse.

        Always returns 0, indicating that no records were successfully processed.

        """
        return 0

    def process_metadata(self, *args, **kwargs) -> Optional[dict[str, Any]]:
        """No-Op: This method is retained for compatibility. It returns None by default.

        Raises:
            NotImplementedError: Unless overridden, this method will raise an error unless defined in a subclass.
        """
        return None

    def normalize(
        self, field_map: Optional[BaseFieldMap] = None, raise_on_error: bool = True, *args, **kwargs
    ) -> list[dict[str, Any]]:
        """No-Op: Raises a RecordNormalizationException when `raise_on_error=True` and returns an empty list otherwise.

        Args:
            field_map (Optional[BaseFieldMap]):
                An optional field map that can be used to normalize the current response. This is inferred from the
                registry if not provided as input.
            raise_on_error (bool):
                A flag indicating whether to raise an error. If a field_map cannot be identified for the current
                response and `raise_on_error` is also True, a normalization error is raised.
            *args:
                 Positional argument placeholder for compatibility with the `ProcessedResponse.normalize` method
            **kwargs:
                 Keyword argument placeholder for compatibility with the `ProcessedResponse.normalize` method

        Returns:
            list[dict[str, Any]]:
                An empty list if `raise_on_error=False`

        Raises:
            RecordNormalizationException:
                If `raise_on_error=True`, this exception is raised after catching `NotImplementedError`

        """
        try:
            super().normalize()
        except (NotImplementedError, RecordNormalizationException) as e:
            msg = str(e)
            if raise_on_error:
                logger.error(msg)
                raise RecordNormalizationException(msg) from e
            logger.warning(f"{msg} Returning an empty list.")
        return []

    def __bool__(self):
        """Indicates that the underlying response was not successfully processed or contained an error code."""
        return False


class NonResponse(ErrorResponse):
    """Response class that indicates that an error occurred during request preparation or API response retrieval.

    This class is used to signify the error that occurred within the search process using a similar interface as the
    other scholar_flux Response dataclasses.

    """

    response: None = None

    def __repr__(self) -> str:
        """Helper method for creating a string representation of the underlying ErrorResponse."""
        return generate_repr_from_string(
            self.__class__.__name__, dict(error=self.error, message=self.message), flatten=True
        )


class ProcessedResponse(APIResponse):
    """APIResponse class that scholar_flux uses to return processed response data after successful response processing.

    This class is populated to return response data containing information on the original, cached, or reconstructed
    API response that is received and processed after retrieval. In addition to returning processed records and
    metadata, this class also allows storage of intermediate steps including:

    1. parsed responses,
    2. extracted records and metadata,
    3. processed records (aliased as data),
    4. and any additional messages An error field is provided for compatibility with the ErrorResponse class.

    """

    parsed_response: Optional[Any] = None
    extracted_records: Optional[List[dict[str, Any]] | List[dict[str | int, Any]]] = None
    processed_records: Optional[List[dict[str, Any]] | List[dict[str | int, Any]]] = None
    normalized_records: Optional[List[dict[str, Any]]] = None
    metadata: Optional[dict[str, Any] | dict[str, Any]] = None
    processed_metadata: Optional[dict[str, Any]] = None
    message: Optional[str] = None

    @property
    def data(self) -> Optional[List[dict[str, Any]] | List[dict[str | int, Any]]]:
        """Alias to the processed_records attribute that holds a list of dictionaries, when available."""
        return self.processed_records

    @property
    def error(self) -> None:
        """Provided for type hinting + compatibility."""
        return None

    @property
    def total_query_hits(self) -> Optional[int]:
        """Returns the total number of results as reported by the API.

        This method retrieves the `total_query_hits` variable from the `processed_metadata` attribute, and if metadata
        hasn't yet been processed, this method will then call `process_metadata()` manually to ensure that the field is
        available.

        """
        if not self.processed_metadata:
            self.process_metadata()

        processed_metadata = self.processed_metadata or {}
        return coerce_int(processed_metadata.get("total_query_hits"))

    @property
    def records_per_page(self) -> Optional[int]:
        """Returns the total number of results on the current page.

        This method retrieves the `records_per_page` variable from the `processed_metadata` attribute, and if metadata
        hasn't yet been processed, this method will then call `process_metadata()` manually to ensure that the field is
        available.

        """
        if not self.processed_metadata:
            self.process_metadata()

        processed_metadata = self.processed_metadata or {}
        return coerce_int(processed_metadata.get("records_per_page"))

    def process_metadata(
        self, metadata_map: Optional[ResponseMetadataMap] = None, update_metadata: Optional[bool] = None
    ) -> Optional[dict[str, Any]]:
        """Uses a `ResponseMetadataMap` to process metadata for tertiary information on the response.

        This method is a helper that is meant for primarily internal use for providing metadata information on the
        response where helpful and for informing users of the characteristics of the current response.

        This function will update the `ProcessedResponse.processed_metadata` attribute when `update_metadata=True`
        or in a secondary case where the current `processed_metadata` field is an empty dict or `None` unless
        `update_metadata=False`

        Args:
            metadata_map (Optional[ResponseMetadataMap]):
                A mapping that resolve api-specific metadata names to a universal parameter name.
            update_metadata (Optional[bool]):
                Determines whether the underlying `processed_metadata` field should be updated. If True,
                the processed_metadata field is updated inplace. If `None`, the field is only updated when
                metadata fields have been successfully processed and the `processed_metadata ` field is None.

        Returns:
            Optional[dict[str, Any]]: The processed metadata returned as a dictionary when available. None otherwise.

        """
        if not self.metadata:
            return None

        if not metadata_map:
            provider_config = provider_registry.get_from_url(self.url or "")
            metadata_map = provider_config.metadata_map if provider_config else None

        processed_metadata = (
            metadata_map.process_metadata(self.metadata) if isinstance(metadata_map, ResponseMetadataMap) else None
        )

        if update_metadata is True or (update_metadata is None and not self.processed_metadata):
            self.processed_metadata = processed_metadata

        return processed_metadata

    def normalize(
        self,
        field_map: Optional[BaseFieldMap] = None,
        raise_on_error: bool = False,
        update_records: Optional[bool] = None,
    ) -> list[dict[str, Any]]:
        """Applies a field map to normalize the processed records of a ProcessedResponse into a common structure.

        Note that if a field_map is not provided, this method will return the previously created  `normalized_records`
        attribute if available. If `normalized_records` is None, this method will attempt to look up the `FieldMap`
        from the current provider_registry.

        If processed records is `None` (and not an empty list), record normalization will fall back to using
        `extracted_records` and will return relatively similar results with minor differences in potential value
        coercion, flattening, and the recursive extraction of values at non-terminal paths depending on the
        implementation of the data processor.

        Args:
            field_map (Optional[BaseFieldMap]):
                An optional field map that can be used to normalize the current response. This is inferred from the
                registry if not provided as input.
            raise_on_error (bool):
                A flag indicating whether to raise an error. If a field_map cannot be identified for the current
                response and `raise_on_error` is also True, a normalization error is raised.
            update_records (Optional[bool]):
                A flag that determines whether updates should be made to the `normalized_records` attribute after
                computation. If `None`, updates are made only if the `normalized_records` attribute is not None.

        Returns:
            list[dict[str, Any]]:
                The list of normalized records in the same dimension as the original processed response. If a map for
                the current provider does not exist and `raise_on_error=False`, an empty list is returned instead.

        Raises:
            RecordNormalizationException: If an error occurs during the normalization of record list.

        """
        data = (
            self.extracted_records
            if self.processed_records is None and self.extracted_records
            else self.processed_records
        )

        if field_map is None:

            # recomputation is performed only if `normalize_records` does not exist or `update_records is not True`
            if self.normalized_records is not None and update_records is not True:
                return self.normalized_records

            provider_config = provider_registry.get_from_url(self.url or "")
            if not (provider_config and provider_config.field_map):
                msg = f"The URL, {self.url}, does not resolve to a known provider in the provider_registry."
                if raise_on_error:
                    logger.error(msg)
                    raise RecordNormalizationException(msg)
                logger.warning(f"{msg} Returning an empty list.")
                return []
            field_map = provider_config.field_map

        normalized_records = field_map.normalize_records(data) if data is not None else None

        # records are saved only if a normalized response does not exist or `update_records=True`
        if (
            update_records is None and normalized_records is not None and not self.normalized_records
        ) or update_records:
            self.normalized_records = normalized_records

        return normalized_records or []

    def __repr__(self) -> str:
        """Helper method for creating a simple representation of the ProcessedResponse."""
        metadata = truncate(self.metadata, max_length=40, show_count=False) if self.metadata is not None else None
        data = truncate(self.data, max_length=40, show_count=True) if self.data is not None else None

        attributes = {"cache_key": self.cache_key, "metadata": metadata, "data": data}
        return generate_repr_from_string(self.__class__.__name__, attributes, flatten=True)

    @property
    def record_count(self) -> int:
        """The overall length of the processed data field as processed in the last step after filtering."""
        return len(self)

    def __len__(self) -> int:
        """Calculates the overall length of the processed data field as processed in the last step after filtering."""
        return len(self.processed_records or [])

    def __bool__(self) -> bool:
        """Returns true to indicate that processing was successful, independent of the number of processed records."""
        return True


__all__ = ["APIResponse", "ProcessedResponse", "ErrorResponse", "NonResponse"]
