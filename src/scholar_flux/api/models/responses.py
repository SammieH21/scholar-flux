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
from typing import cast, ClassVar, Optional, Any, Mapping, MutableMapping, Sequence
from scholar_flux.exceptions import (
    InvalidResponseStructureException,
    InvalidResponseReconstructionException,
    RecordNormalizationException,
)
from typing_extensions import Self
from pydantic import BaseModel, field_serializer, field_validator, ConfigDict
from scholar_flux.api.response_validator import ResponseValidator
from scholar_flux.api.models.reconstructed_response import ReconstructedResponse
from scholar_flux.utils.record_types import RecordType, RecordList, NormalizedRecordList, MetadataType
from scholar_flux.utils.helpers import (
    generate_iso_timestamp,
    parse_iso_timestamp,
    format_iso_timestamp,
    coerce_int,
    is_nested_json,
)
from scholar_flux.utils import CacheDataEncoder, generate_repr, generate_repr_from_string, truncate
from scholar_flux.utils.response_protocol import ResponseProtocol, is_response_like
from scholar_flux.utils.logger import log_level_context
from scholar_flux.api.providers import provider_registry
from scholar_flux.api.normalization.base_field_map import BaseFieldMap
from scholar_flux.data.data_extractor import DataExtractor
from scholar_flux.api.models.response_metadata_map import ResponseMetadataMap
from datetime import datetime
from http.client import responses
from json import JSONDecodeError
import json
import logging
import requests
from requests_cache.models.response import CachedResponse

logger = logging.getLogger(__name__)


class APIResponse(BaseModel):
    """A Response wrapper for responses of different types that allows consistency when using several possible backends.

    The purpose of this class is to serve as the base for managing responses received from scholarly APIs while
    processing each component in a predictable, reproducible manner.

    This class uses pydantic's data validation and serialization/deserialization methods to aid caching and includes
    properties that refer back to the original response for displaying valid response codes, URLs, etc.

    All future processing/error-based responses classes inherit from and build off of this class.

    Args:
        cache_key (Optional[str]):
            A string for recording cache keys for use in later steps of the response orchestration involving
            processing, cache storage, and cache retrieval
        response (Optional[requests.Response | ResponseProtocol]):
            A response or response-like object to be validated and used/re-used in later caching and response
            processing/orchestration steps.
        created_at (Optional[str]):
            A value indicating the time at which a response or response-like object was created.

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
    response: Optional[requests.Response | ResponseProtocol] = None
    created_at: Optional[str] = None

    model_config: ClassVar[ConfigDict] = ConfigDict(arbitrary_types_allowed=True)

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
            logger.warning(f"Expected an iso8601-formatted datetime, but received type ({type(v)})")
            return None

        return v

    @field_validator("response", mode="before")
    def transform_response(
        cls, v: Optional[requests.Response | ResponseProtocol]
    ) -> Optional[requests.Response | ResponseProtocol]:
        """Attempts to resolve a valid or a serialized response-like object as an original or `ReconstructedResponse`.

        All original response objects (duck-typed or requests response) with valid values will be returned as is.

        If the passed object is a string - this function will attempt to serialize it before
        attempting to parse it as a dictionary.

        Dictionary fields will be decoded, if originally encoded, and parsed as a ReconstructedResponse object,
        if possible.

        Otherwise, the original object is returned as is.

        """
        if (
            v is None
            or isinstance(v, (requests.Response, ReconstructedResponse))
            or ResponseValidator.is_valid_response_structure(v)
        ):
            return v

        try:
            return cls.from_serialized_response(v) if not is_response_like(v) else cls.as_reconstructed_response(v)
        except (TypeError, JSONDecodeError, AttributeError) as e:
            logger.warning(f"Couldn't decode a valid response object: {e}")
        except InvalidResponseStructureException as e:
            logger.warning(
                f"A valid response could not be reconstructed from the object of type {type(v).__name__}: {e}"
            )
        return None

    @property
    def cached(self) -> Optional[bool]:
        """Identifies whether the current response was retrieved from the session cache.

        Returns:
            bool: True if the response is a CachedResponse object and False if it is a fresh requests.Response object
            None: Unknown (e.g., the response attribute is not a requests.Response object or subclass)

        """
        match self.response:
            case CachedResponse():
                return True
            case requests.Response():
                return False
            case ReconstructedResponse():
                with log_level_context(logging.ERROR):
                    return True if self.response.is_response() else None
            case _:
                return None

    @property
    def status_code(self) -> Optional[int]:
        """Helper property for retrieving a status code from the APIResponse.

        Returns:
            Optional[int]: The status code associated with the response (if available)

        """
        try:
            status_code = getattr(self.response, "status_code", None)
            return coerce_int(status_code)
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
        return reason if ResponseValidator.is_valid_reason(reason) else None

    @property
    def status(self) -> Optional[str]:
        """Helper property for retrieving a human-readable status description APIResponse.

        Returns:
            Optional[str]: The status description associated with the response (if available).

        """
        status = self.reason or getattr(self.response, "status", None)
        return status if ResponseValidator.is_valid_reason(status) else None

    @property
    def headers(self) -> Optional[MutableMapping[str, str]]:
        """Return headers from the underlying response, if available and valid.

        Returns:
            MutableMapping[str, str]: A dictionary of headers from the response

        """
        headers = getattr(self.response, "headers", None)
        if ResponseValidator.is_valid_headers(headers):
            return headers if isinstance(headers, dict) else dict(headers)
        if self.response is not None:
            logger.warning("The current APIResponse does not have a valid response header")
        return None

    @property
    def content(self) -> Optional[bytes]:
        """Return content from the underlying response, if available and valid.

        Returns:
            (bytes): The bytes from the original response content

        """
        content = getattr(self.response, "content", None)

        if ResponseValidator.is_valid_content(content):
            return content

        if self.response is not None:
            logger.warning("The current APIResponse does not have a valid response content attribute")
        return None

    @property
    def text(self) -> Optional[str]:
        """Attempts to retrieve the response text by first decoding the bytes of its content.

        If not available, this property attempts to directly reference the text attribute directly.

        Returns:
            Optional[str]: A text string if the text is available in the correct format, otherwise None

        """
        with log_level_context(logging.ERROR):
            content = self.content

        text = content.decode("utf-8") if content is not None else getattr(self.response, "text", None)

        if isinstance(text, str):
            return text

        if self.response is not None:
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
        url_string = url if isinstance(url, str) else str(url)
        return url_string if ResponseValidator.is_valid_url(url_string) else None

    def validate_response(self, raise_on_error: bool = False) -> bool:
        """Helper method for determining whether the response attribute is truly a response or response-like object.

        If the response isn't a requests.Response object, we use duck-typing to determine whether the response, itself,
        contains the attributes expected of a response.

        For this purpose, response properties are checked in order to determine whether the properties of the nested
        response match object matches the expected type.

        Args:
            raise_on_error (bool):
                Indicates whether an error should be raised if the response attribute is invalid (False by default).

        Returns:
            bool: Indicates whether the current `APIResponse.response` attribute is a valid response.

        Raises:
            InvalidResponseStructureException: When the response attribute is invalid and `raise_on_error=True`

        """
        if isinstance(self.response, requests.Response):
            return True

        # Assumes the object is a ResponseProtocol and validates the duck-type within `validate_response_structure`
        return ResponseValidator.validate_response_structure(
            cast("ResponseProtocol", self.response), raise_on_error=raise_on_error
        )

    @classmethod
    def from_response(
        cls,
        response: Optional[Any] = None,
        cache_key: Optional[str] = None,
        auto_created_at: Optional[bool] = None,
        **kwargs: Any,
    ) -> Self:
        """Construct an APIResponse from a response object or from keyword arguments.

        If response is not a valid response object, builds a minimal response-like object from kwargs.

        """
        model_kwargs = {field: kwargs.pop(field, None) for field in cls.model_fields if field in kwargs}

        response = (
            response if isinstance(response, requests.Response) else ReconstructedResponse.build(response, **kwargs)
        )

        if auto_created_at is True and not model_kwargs.get("created_at"):
            model_kwargs["created_at"] = generate_iso_timestamp()
        return cls(response=response, cache_key=cache_key, **model_kwargs)

    @field_serializer("response", when_used="json")
    def encode_response(self, response: object) -> Optional[dict[str, Any] | list[Any]]:
        """Helper method for serializing a response into a json format.

        Accounts for special cases such as `CaseInsensitiveDict` fields that are otherwise unserializable.

        From this step, pydantic can safely use json internally to dump the encoded response fields

        """
        return self._encode_response(response) if is_response_like(response) else None

    @classmethod
    def serialize_response(cls, response: requests.Response | ResponseProtocol) -> Optional[str]:
        """Helper method for serializing a response into a json format.

        The response object is first converted into a serialized string and subsequently dumped after ensuring that the
        field is serializable.

        Args:
            response (Response, ResponseProtocol): A requests.Response or response-like object to serialize as a string.

        Returns:
            Optional[str]: A serialized response when response serialization is possible. Otherwise None.

        """
        try:
            encoded_response = cls._encode_response(response)

            if encoded_response:
                return json.dumps(encoded_response)
        except (InvalidResponseReconstructionException, TypeError, UnicodeEncodeError, AttributeError) as e:
            logger.error(
                f"Could not encode the value of type {type(response)} into a serialized json object "
                f"due to an error: {e}"
            )

        return None

    @classmethod
    def _encode_response(cls, response: requests.Response | ResponseProtocol) -> dict[str, Any]:
        """Encodes a response using a `ReconstructedResponse` to store core fields from response-like objects.

        Elements from the response are first extracted from the response object using the ReconstructedResponse data
        model. After extracting the fields from the model as a dictionary, the fields are subsequently encoded using
        the scholar_flux.utils.CacheDataEncoder that ensures all fields are encodable.

        Afterward, the dictionary can safely be serialized via json.dumps.

        Note that fields such as CaseInsensitiveDicts and other MutableMappings are converted to dictionaries
        to support the process of encoding each field.

        Args:
            response (requests.Response | ResponseProtocol):
                A response or response-like object whose core fields are to be encoded

        Returns:
            dict[str, Any]: A dictionary formatted in a way that enables core fields to be encoded
                            using json.dumps function from the json module in the standard library that
                            serializes dictionaries into strings.

        """
        reconstructed_response = ReconstructedResponse.build(response)
        response_dictionary = CacheDataEncoder.encode(reconstructed_response.asdict())
        return response_dictionary

    @classmethod
    def _decode_response(cls, encoded_response_dict: dict[str, Any], **kwargs: Any) -> Optional[ReconstructedResponse]:
        """Helper method for decoding a dict of encoded fields that were previously encoded using _encode_response.

        This class approximately creates the previous response object by creating a `ReconstructedResponse` that
        retains core fields from the original response to support the orchestration of response processing and caching.

        Args:
            encoded_response_dict (dict[str, Any]):
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
    def from_serialized_response(
        cls, response: Optional[object] = None, **kwargs: Any
    ) -> Optional[ReconstructedResponse]:
        """Helper method for creating a new `APIResponse` from dumped JSON object.

        This method accounts for lack of ease of serialization of responses by decoding the response dictionary that was
        loaded from a string using `json.loads` from the JSON module in the standard library.

        If the response input is still a serialized string, this method will manually load the response dict with
        the `APIresponse._deserialize_response_dict` class method before further processing.

        Args:
            response (object):  A prospective response value to load into the API Response.

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
    def as_reconstructed_response(cls, response: object) -> ReconstructedResponse:
        """Classmethod designed to create a reconstructed response from an original response object.

        This method coerces response attributes into a reconstructed response that retains the original content, status
        code, headers, URL, reason, etc.

        Returns:
            ReconstructedResponse: A minimal response object that contains the core attributes needed to support
                                   other processes in the scholar_flux module such as response parsing and caching.

        """
        raw_response = response.response if isinstance(response, APIResponse) else response

        try:
            return ReconstructedResponse.build(raw_response)
        except InvalidResponseReconstructionException as e_reconstruction:
            # diagnostics - investigating why the error occurred
            response_input_type = type(response).__name__
            validation_subject = (
                "a valid raw response" if isinstance(response, APIResponse) else "valid response fields"
            )
            err = f"The object of type '{response_input_type}' does not contain {validation_subject}"

            if not isinstance(raw_response, Mapping):
                # Raises an InvalidResponseStructureException if the object is not response-like:
                try:
                    ResponseValidator.validate_response_like(raw_response)
                except InvalidResponseStructureException as e_validation:
                    raise InvalidResponseStructureException(f"{err}: {e_validation}")
            raise InvalidResponseStructureException(f"{err}: {e_reconstruction}")

    def __eq__(self, other: object) -> bool:
        """Helper method for validating whether responses are equal.

        Elements of the same type are considered a necessary quality for processing components to be considered equal.

        Args:
            other (object): An object to compare against the current APIResponse object/subclass

        Returns:
            bool: True if the value is equal to the current APIResponse object, otherwise False

        """
        # accounting for subclasses:
        return isinstance(other, self.__class__) and self.model_dump(exclude={"created_at"}) == other.model_dump(
            exclude={"created_at"}
        )

    @classmethod
    def _deserialize_response_dict(cls, serialized_response_dict: str) -> Optional[dict]:
        """Helper method for deserializing the dumped model JSON.

        Attempts to load JSON data from a string if possible. Otherwise returns None

        """
        try:
            deserialized_dict = json.loads(serialized_response_dict)
            return deserialized_dict
        except (JSONDecodeError, UnicodeDecodeError, TypeError) as e:
            logger.warning(f"Could not decode the response argument from a string to JSON object: {e}")
        return None

    def raise_for_status(self) -> None:
        """Uses the underlying response or response-like object to validate the status code associated with the request.

        If the attribute isn't a response or reconstructed response, the code will coerce the class into a response
        object to verify the status code for the request URL and response.

        Raises:
            requests.RequestException: Errors for status codes that indicate unsuccessfully received responses.

        """
        if is_response_like(self.response):
            self.response.raise_for_status()
        else:
            self.as_reconstructed_response(self.response).raise_for_status()

    def process_metadata(self, *args: Any, **kwargs: Any) -> Optional[MetadataType]:
        """Abstract processing method that `APIResponse` subclasses can override to process metadata.

        Args:
            *args: No-Op - Added for compatibility with the `APIResponse` subclasses.
            **kwargs: No-Op - Added for compatibility with the `APIResponse` subclasses.

        Raises:
            NotImplementedError: Unless overridden, this method will raise an error unless defined in a subclass.

        """
        raise NotImplementedError(
            f"Metadata processing is not implemented for responses of type, {self.__class__.__name__}"
        )

    def resolve_extracted_record(self, *args: Any, **kwargs: Any) -> Optional[RecordType]:
        """Defines a No-Op method to be overridden by ProcessedResponse subclasses."""
        raise NotImplementedError(
            f"Extracted record resolution is not implemented for responses of type, {self.__class__.__name__}"
        )

    def build_record_id_index(self, *args: Any, **kwargs: Any) -> Optional[dict[str, RecordType]]:
        """Defines a No-Op method to be overridden by ProcessedResponse subclasses."""
        raise NotImplementedError(
            f"Extracted record resolution is not implemented for responses of type, {self.__class__.__name__}"
        )

    def strip_annotations(self, *args: Any, **kwargs: Any) -> RecordList:
        """Defines a No-Op method to be overridden by ProcessedResponse subclasses."""
        raise NotImplementedError(
            f"Record annotation removal is not implemented for responses of type, {self.__class__.__name__}"
        )

    def normalize(self, *args: Any, **kwargs: Any) -> NormalizedRecordList:
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
    """Returned when something goes wrong, but we don't want to throw immediately—just hand back failure details.

    The class is formatted for compatibility with the ProcessedResponse.

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
            message (str): Error message describing the failure.
            error (Exception): The exception instance that was raised.
            cache_key (Optional[str]): Cache key for storing results.
            response (Optional[requests.Response | ResponseProtocol]): Raw API response.

        Returns:
            ErrorResponse:
                A pydantic model that contains the error response data and background information on what precipitated
                the error.

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

    def process_metadata(self, *args: Any, **kwargs: Any) -> Optional[MetadataType]:
        """No-Op: This method is retained for compatibility. It returns None by default."""
        try:
            return super().process_metadata(*args, **kwargs)
        except NotImplementedError as e:
            logger.warning(f"{e}: Skipping metadata processing...")
        return None

    def build_record_id_index(self, *args: Any, **kwargs: Any) -> dict[str, RecordType]:
        """No-Op: Returns an empty dict when no extracted records are available.

        This method is retained for compatibility with ProcessedResponse. Since ErrorResponse has no extracted records
        to index, this method always returns an empty dictionary regardless of arguments provided.

        Args:
            *args:
                Positional argument placeholder for compatibility with the `ProcessedResponse.build_record_id_index`
                method. All arguments are ignored.
            **kwargs:
                Keyword argument placeholder for compatibility with the `ProcessedResponse.build_record_id_index`
                method. All arguments are ignored.

        Returns:
            dict[str, RecordType]: An empty dictionary indicating no records are available for indexing.

        """
        return {}

    def resolve_extracted_record(self, *args: Any, **kwargs: Any) -> None:
        """No-Op: Returns None when no records are available.

        This method is retained for compatibility with ProcessedResponse. Since ErrorResponse has no extracted or
        processed records, resolution is not possible and this method always returns None.

        Args:
            *args:
                Positional argument placeholder for compatibility with the `ProcessedResponse.resolve_extracted_record`
                method. Currently includes `processed_index` (int).
            **kwargs:
                Keyword argument placeholder for compatibility with the `ProcessedResponse.resolve_extracted_record`
                method. All arguments are ignored.

        Returns:
            None: Always returns None since no records exist to resolve.

        """
        return None

    def strip_annotations(self, records: Optional[RecordType | RecordList] = None) -> RecordList:
        """Convenience method for removing internal metadata annotations from a provided list of records.

        This method removes all metadata annotations (dictionary keys that are prefixed with an underscore) that were
        added during the record extraction step for pipeline traceability (e.g., `_extraction_index`, `_record_id`).

        Args:
            records: (RecordType | RecordList) Records to strip. Defaults to `processed_records` if None.

        Returns:
            RecordList:
                A list of dictionary records with stripped metadata annotations when provided. If a record or record
                list is not provided, a warning is logged, and an empty list is returned.

        Note: This method is defined primarily for compatibility with the `ProcessedResponse` API.

        """
        if records is not None:
            stripped_records = DataExtractor.strip_annotations(records)
            return [stripped_records] if isinstance(stripped_records, dict) else stripped_records

        logger.warning(
            "Record Annotation removal for `processed_records` is not implemented for responses of type, "
            f"{self.__class__.__name__}: There are no records to strip annotations from. Returning an empty list..."
        )
        return []

    def normalize(
        self, field_map: Optional[BaseFieldMap] = None, raise_on_error: bool = True, *args: Any, **kwargs: Any
    ) -> NormalizedRecordList:
        """No-Op: Raises a RecordNormalizationException when `raise_on_error=True` and returns an empty list otherwise.

        Args:
            field_map (Optional[BaseFieldMap]):
                An optional field map that can be used to normalize the current response. This is inferred from the
                registry if not provided as input.
            raise_on_error (bool):
                A flag indicating whether to raise an error. If a field_map cannot be identified for the current
                response and `raise_on_error` is also True, a `RecordNormalizationException` is raised.
            *args:
                 Positional argument placeholder for compatibility with the `ProcessedResponse.normalize` method
            **kwargs:
                 Keyword argument placeholder for compatibility with the `ProcessedResponse.normalize` method

        Returns:
            NormalizedRecordList: An empty list if `raise_on_error=False`

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

    def __bool__(self) -> bool:
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

    1. Parsed responses
    2. Extracted records and metadata
    3. Processed records (aliased as data)
    4. Normalized records
    5. Processed metadata
    6. Any additional messages. An error field is provided for compatibility with the ErrorResponse class.

    """

    parsed_response: Optional[Any] = None
    extracted_records: Optional[RecordList] = None
    processed_records: Optional[RecordList] = None
    normalized_records: Optional[NormalizedRecordList] = None
    metadata: Optional[MetadataType] = None
    processed_metadata: Optional[MetadataType] = None
    message: Optional[str] = None

    @property
    def data(self) -> Optional[RecordList]:
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
    ) -> Optional[MetadataType]:
        """Uses a `ResponseMetadataMap` to process metadata for tertiary information on the response.

        This method is a helper that is meant for primarily internal use for providing metadata information on the
        response where helpful and for informing users of the characteristics of the current response.

        This function will update the `ProcessedResponse.processed_metadata` attribute when `update_metadata=True`
        or in a secondary case where the current `processed_metadata` field is an empty dict or `None` unless
        `update_metadata=False`

        Args:
            metadata_map (Optional[ResponseMetadataMap]):
                A mapping that resolve API-specific metadata names to a universal parameter name.
            update_metadata (Optional[bool]):
                Determines whether the underlying `processed_metadata` field should be updated. If True,
                the processed_metadata field is updated inplace. If `None`, the field is only updated when
                metadata fields have been successfully processed and the `processed_metadata ` field is None.

        Returns:
            Optional[MetadataType]: The processed metadata returned as a dictionary when available. None otherwise.

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
        resolve_records: Optional[bool] = None,
        keep_api_specific_fields: Optional[bool | Sequence] = None,
        strip_annotations: Optional[bool] = None,
    ) -> NormalizedRecordList:
        """Applies a field map to normalize the processed records of a ProcessedResponse into a common structure.

        Note that if a field_map is not provided, this method will return the previously created `normalized_records`
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
                computation. If `None`, updates are made only if the `normalized_records` attribute is currently None.
            resolve_records (Optional[bool]):
                A flag that determines if resolution with annotated records should occur. If True or None, resolution
                occurs. If False, normalization uses `processed_records` when not None and `extracted_records`
                otherwise.
            keep_api_specific_fields (Optional[bool | Sequence]):
                Indicates what API-specific records should be retained from the complete list of API parameters that
                are returned. If False, only the core parameters defined by the FieldMap are returned. If True or None,
                all parameters are returned instead.
            strip_annotations (Optional[bool]):
                A flag for removing metadata annotations denoted by a leading underscore. When True or None (default),
                annotations are removed from normalized records.

        Returns:
            NormalizedRecordList:
                The list of normalized records in the same dimension as the original processed response. If a map for
                the current provider does not exist and `raise_on_error=False`, an empty list is returned instead.

        Raises:
            RecordNormalizationException: If an error occurs during the normalization of record list.

        Example:
            >>> from scholar_flux import SearchCoordinator
            >>> from scholar_flux.utils import truncate, coerce_flattened_str
            >>> coordinator = SearchCoordinator(query = 'public health')
            >>> response = coordinator.search_page(page = 1)
            >>> normalized_records = response.normalize()
            >>> for record in normalized_records[:5]:
            ...     print(f"Title: {record['title']}")
            ...     print(f"URL: {record['url']}")
            ...     print(f"Source: {record['provider_name']}")
            ...     print(f"Abstract: {truncate(record['abstract'] or 'Not available')}")
            ...     print(f"Authors: {coerce_flattened_str(record['authors'])}")
            ...     print("-"*100)

            # OUTPUT:
            Title: Are we prepared? The development of performance indicators for ...
            URL: https://journals.plos.org/plosone/article?id=...
            Source: plos
            Abstract: Background: Disasters and emergencies...
            Authors: ...
            ----------------------------------------------------------------------------------------------------

        Note:
            Computation is performed in one of three cases:

            1.`normalized_records` does not already exist
            2.`update_records` is not True
            3. Either `resolve_records` or `keep_api_specific_fields` is not None

        """
        if field_map is None:

            if (
                self.normalized_records is not None
                and update_records is not True
                and resolve_records is None
                and keep_api_specific_fields is None
            ):
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

        resolve_records = resolve_records if resolve_records is not None else True
        data = self._prepare_normalization_records(resolve_records)
        normalized_records = (
            field_map.normalize_records(data, keep_api_specific_fields=keep_api_specific_fields)
            if data is not None
            else None
        )
        normalized_records = (
            DataExtractor.strip_annotations(normalized_records)
            if strip_annotations is True or strip_annotations is None
            else normalized_records
        )

        # records are saved only if a normalized response does not exist or `update_records=True`
        if (
            update_records is None and normalized_records is not None and not self.normalized_records
        ) or update_records:
            self.normalized_records = normalized_records

        return normalized_records or []

    def _prepare_normalization_records(self, resolve_records: Optional[bool] = True) -> RecordList | None:
        """Merge extracted and processed records when annotation fields exist.

        Extracted and processed records are only merged if the `processed_records` contains flattened fields.

        Internal method that returns merged records (extracted | processed) when
        resolution is beneficial, otherwise returns data unchanged.

        Args:
            resolve_records (Optional[bool]):
                A flag that determines if resolution with annotated records should occur. If True or None, resolution
                occurs. If False, normalization uses `processed_records` when not None and `extracted_records`
                otherwise.

        Returns:
            RecordList | None:
                Merged records if annotations exist, otherwise unchanged

        """
        if self.extracted_records is not None and self.processed_records is None:
            return self.extracted_records
        if self.extracted_records is None or self.processed_records is None or resolve_records is False:
            return self.processed_records

        # If the first sample contains no records, no other record will have the field either
        sample = self.processed_records[0] if self.processed_records else {}
        if DataExtractor.EXTRACTION_INDEX_KEY not in sample or all(
            is_nested_json(record) for record in self.processed_records
        ):
            return self.processed_records

        id_index = self.build_record_id_index()

        if not id_index:
            return self.processed_records

        return [self._merge_record_pair(rec, id_index) for rec in self.processed_records]

    def _merge_record_pair(
        self,
        processed_record: RecordType,
        id_index: dict[str, RecordType],
    ) -> RecordType:
        """Merge a processed record with its corresponding extracted record.

        Creates a combined view where extracted record fields serve as the base
        and processed record fields overlay them, preserving nested structures
        while including flattened/transformed fields.

        Args:
            processed_record (RecordType):
                The processed (possibly flattened) record
            id_index (dict[str, RecordType]):
                Mapping of record IDs to extracted records

        Returns:
            RecordType: Merged record, or original processed_record if no match

        """
        record_id = processed_record.get(DataExtractor.RECORD_ID_KEY)

        if not isinstance(record_id, str):
            return processed_record

        extracted_record = id_index.get(record_id)

        if not extracted_record:
            return processed_record

        return extracted_record | processed_record

    def strip_annotations(
        self,
        records: Optional[RecordType | RecordList] = None,
    ) -> RecordList:
        """Convenience method that removes metadata annotations from a record list for clean export.

        This method removes all metadata annotations (dictionary keys that are prefixed with an underscore) that were
        added during the record extraction step for pipeline traceability (e.g., `_extraction_index`, `_record_id`).

        Args:
            records: (RecordType | RecordList) Records to strip. Defaults to `processed_records` if None.

        Returns:
            RecordType | RecordList: New list of records with annotation fields removed.

        Example:
            >>> clean_data = response.strip_annotations()
            >>> df = pd.DataFrame(clean_data)  # No internal fields in DataFrame

        """
        records = records if records is not None else self.processed_records

        if not records:
            return []

        stripped_records = DataExtractor.strip_annotations(records)
        return [stripped_records] if isinstance(stripped_records, dict) else stripped_records

    def resolve_extracted_record(
        self,
        processed_index: int,
    ) -> Optional[RecordType]:
        """Resolve a processed record back to its original extracted record.

        This method uses a two-phase resolution strategy with optional validation:

        1. Primary: Direct index lookup via `_extraction_index` (fast, single access)
        2. Validation: Verify `_record_id` matches
        3. Fallback: Search by `_record_id` if index lookup fails or mismatches (scans all records)

        Args:
            processed_index (int):
                The index of the record in `processed_records` to resolve.

        Returns:
            Optional[RecordType]:
                The original extracted record, or None if resolution fails.

        Example:
            >>> from scholar_flux import SearchCoordinator, RecursiveDataProcessor
            >>> coordinator = SearchCoordinator(
            ...     query='public health',
            ...     provider_name='openalex',
            ...     annotate_records=True,
            ...     processor=RecursiveDataProcessor()
            ... )
            >>> response = coordinator.search(page=1)
            >>> # Get processed (possibly flattened) record
            >>> processed = response.processed_records[0]
            >>> print(processed.get("authorships.author.display_name"))  # ['Kenneth L. Howard...']
            >>> # Resolve to original nested structure
            >>> original = response.resolve_extracted_record(0)
            >>> print(original.get("authorships"))
            >>> print(original.get("authorships")[0].keys())
            # OUTPUT: dict_keys(['author_position', 'author', 'institutions', 'countries', 'is_corresponding', 'raw_author_name', 'raw_affiliation_strings', 'affiliations'])

        Note:
            Resolution requires that records were extracted with `annotate_records=True` in the DataExtractor. Without
            annotation fields, this method returns None.

        """
        if not self.processed_records or not self.extracted_records:
            return None

        if not 0 <= processed_index < len(self.processed_records):
            return None

        processed_record = self.processed_records[processed_index]
        extraction_index = processed_record.get(DataExtractor.EXTRACTION_INDEX_KEY)
        record_id = processed_record.get(DataExtractor.RECORD_ID_KEY)

        if not record_id:
            return None

        # Phase 1: Direct index lookup
        if isinstance(extraction_index, int) and 0 <= extraction_index < len(self.extracted_records):
            candidate = self.extracted_records[extraction_index]

            if candidate.get(DataExtractor.RECORD_ID_KEY) == record_id:
                return candidate

            logger.debug(
                f"Record ID mismatch at index {extraction_index}: "
                f"expected {record_id}, found {candidate.get(DataExtractor.RECORD_ID_KEY)}"
            )

        # Phase 2: Fallback ID search
        return self._resolve_by_record_id(record_id)

    def _resolve_by_record_id(self, record_id: str) -> Optional[RecordType]:
        """Resolves an extracted record by its content-based ID.

        This method resolves a record ID to its original, unprocessed, extracted record using a linear search in which
        the received record ID is compared to the ID of each raw record until a match is found. This method is intended
        as a fallback for finding the original, extracted record from an ID for when index-based resolution fails.

        Args:
            record_id (str): The `_record_id` value to search for.

        Returns:
            Optional[RecordType]: The matching extracted record, or None if not found.

        """
        extracted_records = self.extracted_records or []
        return next(
            (record for record in extracted_records if record.get(DataExtractor.RECORD_ID_KEY) == record_id),
            None,
        )

    def build_record_id_index(self) -> dict[str, RecordType]:
        """Builds a lookup table for ID-based resolution of extracted records.

        This method creates a dictionary that maps `_record_id` values to their corresponding extracted records. Useful
        when performing multiple resolutions for records the same response.

        Returns:
            dict[str, RecordType]:
                A new dictionary mapping record IDs to the original record. An empty dictionary is returned if
                `extracted_records` is None/empty or all records do not have an associated ID

        Example:
            >>> from scholar_flux import SearchCoordinator
            >>> coordinator = SearchCoordinator(query = 'public health', annotate_records=True)
            >>> response = coordinator.search(page = 1)
            >>> id_index = response.build_record_id_index()
            >>> processed_record = response.data[0]
            >>> extracted_record = id_index.get(processed_record["_record_id"])
            >>> isinstance(extracted_record, dict)
            # OUTPUT: True

        Note:
            This method is used in the process of identifying raw, unprocessed records after extensive post-processing
            and filtering has been performed on each record and relies on record annotation being enabled during data
            extraction.

        """
        extracted_records = self.extracted_records or []
        record_index = {
            record[DataExtractor.RECORD_ID_KEY]: record
            for record in extracted_records
            if record and isinstance(record.get(DataExtractor.RECORD_ID_KEY), str)
        }
        return record_index

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
