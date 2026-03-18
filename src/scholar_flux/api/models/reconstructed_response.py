# /api/models/reconstructed_response.py
"""The scholar_flux.api.reconstructed_response module implements the ReconstructedResponse for transformation.

The ReconstructedResponse class was designed to be request-client agnostic to improve flexibility in the request
clients that can be used to retrieve data from APIs and load response data from cache.

The ReconstructedResponse is a minimal implementation of a response-like
object that can transform response classes from `requests`, `httpx`, and
`aiohttp` into a singular representation of the same response.

"""
from __future__ import annotations
from typing import Optional, Any, MutableMapping, Mapping
from dataclasses import dataclass, asdict, fields
from scholar_flux.api.response_validator import ResponseValidator
from scholar_flux.exceptions import InvalidResponseReconstructionException, InvalidResponseStructureException
from scholar_flux.utils.helpers import coerce_int, as_str, coerce_str, coerce_bytes, try_bytes, coerce_json_str
import requests
from http.client import responses
from json import JSONDecodeError
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class ReconstructedResponse:
    """Core class for constructing minimal, universal response representations from responses and response-like objects.

    The `ReconstructedResponse` implements several helpers that enable the reconstruction of response-like objects from
    different sources such as the `requests`, `aiohttp`, and `httpx` libraries.

    The primary purpose of the `ReconstructedResponse` in scholar_flux is to create a minimal representation of a
    response when we need to construct a ProcessedResponse without an actual response and verify content fields.

    In applications such as retrieving cached data from a `scholar_flux.data_storage.DataCacheManager`, if an original
    or cached response is not available, then a ReconstructedResponse is created from the cached response fields when
    available.

    Args:
        status_code (int): The integer code indicating the status of the response
        reason (str): Indicates the reasoning associated with the status of the response
        headers (MutableMapping[str, str]): Indicates metadata associated with the response (e.g. Content-Type, etc.)
        content (bytes): The content within the response
        url: (Any): The URL from which the response was received

    Note:
        The `ReconstructedResponse.build` factory method is recommended in cases when one property may contain the
        needed fields but may need to be processed and prepared first before being used.
        Examples include instances where one has text or json data instead of content, a reason_phrase field instead
        of reason, etc.

    Example:
        >>> from scholar_flux.api.models import ReconstructedResponse
        # build a response using a factory method that infers fields from existing ones when not directly specified
        >>> response = ReconstructedResponse.build(status_code = 200, content = b"success", url = "https://google.com")
        # check whether the current class follows a ResponseProtocol and contains valid fields
        >>> assert response.is_response()
        # OUTPUT: True
        >>> response.validate() # raises an error if invalid
        >>> response.raise_for_status() # no error for 200 status codes
        >>> assert response.reason == 'OK' == response.status  # inferred from the status_code attribute

    """

    status_code: int
    reason: str
    headers: MutableMapping[str, str]
    content: bytes
    url: Any

    @property
    def status(self) -> Optional[str]:
        """Helper property for retrieving a human-readable description of the status.

        Returns:
            Optional[str]: The status description associated with the response (if available).

        """
        reason = (
            self.reason or responses.get(self.status_code)
            if ResponseValidator.is_valid_status_code(self.status_code)
            else None
        )
        return reason if ResponseValidator.is_valid_reason(reason) else None

    @property
    def text(self) -> Optional[str]:
        """Helper property for retrieving the text from the bytes content as a string.

        Returns:
            Optional[str]: The decoded text from the content of the response.

        """
        return coerce_str(self.content) if ResponseValidator.is_valid_content(self.content) else None

    @property
    def ok(self) -> bool:
        """Indicates whether the current response indicates a successful request (200 <= status_code < 300).

        To account for the nature of successful requests to APIs in academic pipelines, status codes from 300 to 399
        are excluded.

        Returns:
            bool: True if the status code is an integer value within the range of 200 and 299, False otherwise.

        """
        return isinstance(self.status_code, int) and 200 <= self.status_code < 300

    @classmethod
    def build(cls, response: Optional[object] = None, **kwargs: Any) -> ReconstructedResponse:
        """Helper method for building a new ReconstructedResponse from a regular response object.

        This classmethod can either construct a new ReconstructedResponse object from a response or response-like object
        or otherwise build a new ReconstructedResponse via its keyword parameters.

        Args:
            response (Optional[object]):
                A response or response-like object of unknown type or None.
            **kwargs:
                The underlying components needed to construct a new response. Note that ideally, this set of key-value pairs
                would be specific only to the types expected by the ReconstructedResponse.

        Returns:
            ReconstructedResponse: A minimal `ReconstructedResponse` object created from the received parameter set.

        """
        if isinstance(response, ReconstructedResponse):
            return response

        if response is not None:
            if isinstance(response, dict):
                kwargs = response | kwargs
            elif isinstance(response, (Mapping, MutableMapping)):
                kwargs = dict(response) | kwargs
            else:
                kwargs = (
                    getattr(response, "__dict__", {})
                    | {
                        # extract properties not serialized in a dict
                        field: getattr(response, field)
                        for field in ReconstructedResponse.fields()
                        if hasattr(response, field)
                    }
                    | kwargs
                )

        return ReconstructedResponse.from_keywords(**kwargs)

    @classmethod
    def fields(cls) -> list[str]:
        """Retrieves a list containing the names of all fields associated with the `ReconstructedResponse` class.

        Returns:
            list[str]: A list containing the name of each attribute in the ReconstructedResponse.

        """
        return [field.name for field in fields(ReconstructedResponse)]

    def asdict(self) -> dict[str, Any]:
        """Converts the ReconstructedResponse into a dictionary containing attributes and their corresponding values.

        This convenience method uses `dataclasses.asdict()` under the hood to convert a `ReconstructedResponse` to a
        dictionary consisting of key-value pairs.

        Returns:
            dict[str, Any]:
                A dictionary that maps the field names of a `ReconstructedResponse` instance to their assigned values.

        """
        return asdict(self)

    @classmethod
    def prepare_response_fields(cls, **kwargs: Any) -> dict[str, Any]:
        """Extracts and prepares the fields required to reconstruct the response from the provided keyword arguments.

        Args:
            status_code (int): The integer code indicating the status of the response
            reason (str): Indicates the reasoning associated with the status of the response
            headers (MutableMapping[str, str]): Indicates metadata associated with the response (e.g. Content-Type)
            content (bytes): The content within the response
            url: (Any): The URL from which the response was received

        Some fields can be both provided directly or inferred from other similarly common fields:

            - content: ['content', '_content', 'text', 'json']
            - headers: ['headers', '_headers']
            - reason:  ['reason', 'status', 'reason_phrase', 'status_code']

        Returns:
            dict[str, Any]: A dictionary containing the prepared response fields.

        """
        status_code = cls._normalize_status_code(**kwargs)
        url = cls._normalize_url(**kwargs)

        if status_code is not None:
            kwargs["status_code"] = status_code

        kwargs["headers"] = cls._normalize_headers(**kwargs)

        if url is not None:
            kwargs["url"] = url

        kwargs["reason"] = cls._normalize_reason(**kwargs)

        kwargs["content"] = cls._resolve_content_sources(**kwargs)

        return kwargs

    @classmethod
    def from_keywords(cls, **kwargs: Any) -> ReconstructedResponse:
        """Uses the provided keyword arguments to create a ReconstructedResponse.

        Args:
            **kwargs:
                The `ReconstructedResponse` keyword arguments to normalize. Possible keywords include:

                - status_code (int): The integer code indicating the status of the response
                - reason (str): Indicates the reasoning associated with the status of the response.
                - headers (MutableMapping[str, str]): Indicates metadata associated with the response (e.g. Content-Type)
                - content (bytes): The content within the response
                - url: (Any): The URL from which the response was received


                The keywords can alternatively be inferred from other common response fields:

                - content: ['content', '_content', 'text', 'json']
                - headers: ['headers', '_headers']
                - reason:  ['reason', 'status', 'reason_phrase', 'status_code']

        Returns:
            ReconstructedResponse: A newly reconstructed response from the given keyword components.

        """

        filtered_response_dictionary = {
            name: value
            for name, value in cls.prepare_response_fields(**kwargs).items()
            if name in (field.name for field in fields(cls))
        }

        try:
            return ReconstructedResponse(**filtered_response_dictionary)
        except TypeError as e:
            missing = [
                f"'{field}'" for field in ReconstructedResponse.fields() if field not in filtered_response_dictionary
            ]
            err = f"Missing the core required fields needed to create a ReconstructedResponse: {', '.join(missing)}"
            raise InvalidResponseReconstructionException(err if missing else e)

    @classmethod
    def _normalize_status_code(cls, **kwargs: Any) -> Optional[int]:
        """Helper class method for extracting status codes from the status_code or status field.

        Some status fields may actually contain a numeric code - this method accounts for
        these scenarios and returns None if a code isn't available.

        Args:
            **kwargs: A set of keyword arguments to extract a status code from the `status_code` or `status` parameters.

        Returns:
            An integer code if available, otherwise None.

        """
        status_code = coerce_int(kwargs.get("status_code")) or coerce_int(kwargs.get("status"))
        return status_code

    @classmethod
    def _normalize_reason(cls, **kwargs: Any) -> Optional[str]:
        """Helper class method for extracting a reason associated with the status of a response.

        This method accounts for several scenarios:

        1. Where a `status` attribute is actually a valid, integer status code and not an actual `reason`.
        2. Either `status` or `reason` is provided (but not both).
        3. When `reason` needs to be inferred from the status code via `http.client.responses`.

        Args:
            **kwargs:
                The list of parameters to extract a status from. Includes `reason`, `reason_phrase`, `status`, and
                otherwise, `status_code` directly using the `responses` enumeration from the standard http.client
                module.

        Returns:
            Optional[str]: A string explaining the status code and reason behind it, otherwise None.

        """
        reason = (
            kwargs.get("reason")
            or (status if (status := coerce_str(kwargs.get("status"))) and not coerce_int(status) else None)
            or coerce_str(kwargs.get("reason_phrase"))
            or responses.get(kwargs.get("status_code") or -1)
        )
        return reason

    @classmethod
    def _normalize_url(cls, **kwargs: Any) -> Optional[str]:
        """Helper method to extract a URL as a string if available.

        If the URL is a non-string field, this method attempts to convert the field into a string.

        Args:
            **kwargs: A set of keyword arguments containing the `url` parameter.

        Returns:
            Optional[str]: A string-formatted URL when non-missing.

        """
        return coerce_str(kwargs.get("url"))

    @classmethod
    def _normalize_headers(cls, **kwargs: Any) -> MutableMapping[str, str]:
        """Helper method for extracting and converting headers to a MutableMapping if the header field is a Mapping
        other than a dictionary type.

        The field attempts to extract the necessary headers from either
        the `headers` field or `_headers` field if either is provided with preference
        to `headers`.

        Args:
            **kwargs: The keyword arguments to extract the headers from. Includes `headers` and `_headers`.

        Returns:
            MutableMapping[str, str]: The headers associated with the response or an empty mapping.

        """
        headers = kwargs.get("headers") or kwargs.get("_headers") or {}
        if isinstance(headers, Mapping):
            headers = {k: as_str(v, encoding="utf-8", errors="replace") for k, v in headers.items()}

        return headers

    @classmethod
    def _resolve_content_sources(cls, **kwargs: Any) -> Optional[bytes]:
        """Helper method for retrieving the content field from a set of provided, disparate parameters that each could
        have been provided by the user. This method searches for the following keys: 1) content, 2) _content, 3) json,
        4) text.

        If multiple fields are provided, this implementation prefers the field that contains the most
        information available.

        This is especially important when processing structured data formats (e.g., JSON, XML, YAML).

        If an empty content field is provided along with a populated json list/dictionary, the json data
        will be encoded, dumped, and used in the content field as a bytes object. Otherwise, fields with
        empty-strings and bytes are treated as data, if provided, and preferred over `None`.

        Args:
            **kwargs:
                The keyword arguments to extract the content from. Includes `content`, `_content`, `json`, and `text`
                fields.

        Returns:
            Optional[bytes]: The parsed bytes object containing the expected content.

        """
        content_sources = (
            try_bytes(kwargs.get("content")),
            try_bytes(kwargs.get("_content")),
            coerce_bytes(coerce_json_str(kwargs.get("json"))),
            try_bytes(kwargs.get("text")),
        )

        # search for the first populated (or most populated field accounting for provided, yet empty strings/bytes)
        content_fields = sorted(
            (content for content in content_sources if content is not None),
            key=lambda x: len(x) if isinstance(x, bytes) else -1,
            reverse=True,
        )

        # retrieve the content and encode if not already encoded
        return content_fields[0] if content_fields else None

    def json(self) -> Optional[list[Any] | dict[str, Any]]:
        """Return JSON-decoded body from the underlying response, if available."""
        if not ResponseValidator.is_valid_content(self.content):
            logger.warning("The current response object does not contain jsonable content")
            return None
        try:
            return json.loads(self.content)
        except (JSONDecodeError, AttributeError):
            logger.warning("The current ReconstructedResponse object does not have a valid json format.")
        return None

    def is_response(self) -> bool:
        """Validates the fields of the minimally reconstructed response, indicating whether all fields are valid.

        The fields that are validated include:

            1. status codes (should be an integer)
            2. URLs     (should be a valid url)
            3. reasons  (should originate from a reason attribute or inferred from the status code)
            4. content  (should be a bytes field or encoded from a string text field)
            5. headers  (should be a dictionary with string fields and preferably a content type)

        Returns:
            bool: Indicates whether the current reconstructed response minimally recreates a response object.

        """
        invalid_fields = ResponseValidator.identify_invalid_fields(self)

        invalid_fields = {
            field: value if field in ("status_code", "url") else type(value) for field, value in invalid_fields.items()
        }

        if invalid_fields:
            logger.warning(f"The following fields contain invalid values: {invalid_fields}")

        return not any(invalid_fields)

    def __eq__(self, other: object) -> bool:
        """Helper method for validating whether reconstructed API responses are the same."""
        return isinstance(other, ReconstructedResponse) and asdict(self) == asdict(other)

    def validate(self) -> None:
        """Convenience method for the validation of the current ReconstructedResponse.

        If the response validation is successful, an `InvalidResponseReconstructionException` will not be raised.

        Raises:
            InvalidResponseReconstructionException:
                If at least one field is determined to be invalid and unexpected of a true response object.

        """
        try:
            ResponseValidator.validate_response_structure(self)
        except InvalidResponseStructureException as e:
            raise InvalidResponseReconstructionException(
                "The ReconstructedResponse was not created successfully: Missing valid values for critical fields to "
                f"validate the response. {e}"
            )

    def raise_for_status(self) -> None:
        """Verifies the status code for the current `ReconstructedResponse`, raising an error for failed responses.

        This method follows a similar convention as `requests` and `httpx` response types, raising an error when
        encountering status codes that are indicative of failed responses.

        As scholar_flux processes data that is generally only sent when status codes are between 200-299
        (or exactly 200 [ok]), an error is raised when encountering a value outside of this range.

        Raises:
            HTTPError:
                If the structure of the response is invalid or the status code is not within the range of 200-299.

        """
        try:
            self.validate()

        except InvalidResponseReconstructionException as e:
            raise requests.HTTPError(
                "Could not verify from the ReconstructedResponse to determine whether the "
                f"original request was successful: {e}"
            )

        if not 200 <= self.status_code < 300:
            raise requests.HTTPError(
                "Expected a 200 (ok) status_code for the ReconstructedResponse. Received: "
                f"{self.status_code} ({self.reason or self.status})"
            )


__all__ = ["ReconstructedResponse"]
