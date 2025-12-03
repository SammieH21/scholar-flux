# /api/models/reconstructed_response.py
"""The scholar_flux.api.reconstructed_response module implements a basic ReconstructedResponse data structure.

The ReconstructedResponse class was designed to be request-client agnostic to improve flexibility in the request
clients that can be used to retrieve data from APIs and load response data from cache.

The ReconstructedResponse is a minimal implementation of a response-like
object that can transform response classes from `requests`, `httpx`, and
`asyncio` into a singular representation of the same response.

"""
from __future__ import annotations
from typing import Optional, Dict, List, Any, MutableMapping, Mapping
from dataclasses import dataclass, asdict, fields
from scholar_flux.api.validators import validate_url
from scholar_flux.exceptions import InvalidResponseReconstructionException, InvalidResponseStructureException
import requests
from scholar_flux.utils.response_protocol import ResponseProtocol
from http.client import responses
from json import JSONDecodeError
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class ReconstructedResponse:
    """Helper class for retaining the most relevant of fields when reconstructing responses from different sources such
    as requests and httpx (if chosen). The primary purpose of the ReconstructedResponse in scholar_flux is to create a
    minimal representation of a response when we need to construct a ProcessedResponse without an actual response and
    verify content fields.

    In applications such as retrieving cached data from a `scholar_flux.data_storage.DataCacheManager`, if an original
    or cached response is not available, then a ReconstructedResponse is created from the cached response fields when
    available.

    Args:
        status_code (int): The integer code indicating the status of the response
        reason (str): Indicates the reasoning associated with the status of the response
        headers MutableMapping[str, str]: Indicates metadata associated with the response (e.g. Content-Type, etc.)
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

    @classmethod
    def build(cls, response: Optional[Any] = None, **kwargs) -> ReconstructedResponse:
        """Helper method for building a new ReconstructedResponse from a regular response object. This classmethod can
        either construct a new ReconstructedResponse object from a response object or response-like object or create a
        new ReconstructedResponse altogether with its inputs.

        Args:
            response: (Optional[Any]): A response or response-like object of unknown type or None
        kwargs: The underlying components needed to construct a new response. Note that ideally,
                this set of key-value pairs would be specific only to the types expected by the
                ReconstructedResponse.

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
                    response.__dict__
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
    def fields(cls) -> list:
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
    def from_keywords(cls, **kwargs) -> ReconstructedResponse:
        """Uses the provided keyword arguments to create a ReconstructedResponse. keywords include the default
        attributes of the ReconstructedResponse, or can be inferred and processed from other keywords.

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
            ReconstructedResponse: A newly reconstructed response from the given keyword components

        """

        status_code = cls._normalize_status_code(**kwargs)

        if status_code is not None:
            kwargs["status_code"] = status_code

        kwargs["headers"] = cls._normalize_headers(**kwargs)

        if url := cls._normalize_url(**kwargs):
            kwargs["url"] = url

        kwargs["reason"] = cls._normalize_reason(**kwargs)

        kwargs["content"] = cls._resolve_content_sources(**kwargs)

        filtered_response_dictionary = {
            name: value for name, value in kwargs.items() if name in (field.name for field in fields(cls))
        }

        try:
            return ReconstructedResponse(**filtered_response_dictionary)
        except TypeError as e:
            raise InvalidResponseReconstructionException(
                f"Missing the core required fields needed to create a ReconstructedResponse: {e}"
            )

    @classmethod
    def _normalize_status_code(cls, **kwargs) -> Optional[int]:
        """Helper class method for extracting status codes from the status_code or status field.

        Some status fields may actually contain a numeric code - this method accounts for
        these scenarios and returns None if a code isn't available.

        Args:
            **kwargs: A set of keyword arguments to extract a status code from the `status_code` or `status` parameters

        Returns:
            An integer code if available, otherwise None

        """
        status_code = kwargs.get("status_code") or (
            int(kwargs["status"])
            if isinstance(kwargs.get("status"), int)
            or (isinstance(kwargs.get("status"), str) and kwargs.get("status", "").isnumeric())
            else None
        )
        return status_code

    @classmethod
    def _normalize_reason(cls, **kwargs) -> Optional[str]:
        """Helper class for extracting a reason associated with the status of a response. This method accounts for
        several scenarios: 1) where status may actually be the status code and not an actual reason 2) either status or
        reason is provided and not the other 3) where the status code needs to be inferred from the status code instead.

        Args:
            **kwargs: The list of parameters to extract a status from. Includes `reason`, `reason_phrase`,
                      `status`, and otherwise, `status_code` directly using the `responses` enumeration
                      from the standard http.client module

        Returns:
            Optional[str]: A string explaining the status code and reason behind it, otherwise None

        """
        reason = (
            kwargs.get("reason")
            or (
                kwargs["status"]
                if isinstance(kwargs.get("status"), str) and not kwargs.get("status", "").isnumeric()
                else None
            )
            or kwargs.get("reason_phrase")
            or responses.get(kwargs.get("status_code") or -1)
        )
        return reason

    @classmethod
    def _normalize_url(cls, **kwargs) -> Optional[str]:
        """Helper method to extract a URL as a string if available. If the URL is a non-string field, this method
        attempts to convert the field into a string.

        Args:
            **kwargs: A set of keyword arguments containing the `url` parameter

        Returns:
            str: A String-formatted URL

        """
        url = kwargs.get("url")
        return (str(url) if not isinstance(url, str) else url) if url is not None else None

    @classmethod
    def _normalize_headers(cls, **kwargs) -> MutableMapping:
        """Helper method for extracting and converting headers to a MutableMapping if the header field is a Mapping
        other than a dictionary type.

        The field attempts to extract the necessary headers from either
        the `headers` field or `_headers` field if either is provided with preference
        to `headers`.

        Args:
            **kwargs: The keyword arguments to extract the headers from. Includes `headers` and `_headers`

        Returns:
            MutableMapping: The headers associated with the response or an empty mapping

        """
        headers = kwargs.get("headers") or kwargs.get("_headers", {})
        headers = (
            dict(headers)
            if isinstance(headers, (Mapping, MutableMapping)) and not isinstance(headers, dict)
            else headers
        )

        return headers

    @classmethod
    def _resolve_content_sources(cls, **kwargs) -> Optional[bytes]:
        """Helper method for retrieving the content field from a set of provided, disparate parameters that each could
        have been provided by the user. This method searches for the following keys: 1) content, 2) _content, 3) json,
        4) text.

        If multiple fields are provided, this implementation prefers the field that contains the most
        information available .

        This is especially important when processing structured data formats (e.g., JSON, XML, YAML).

        If an empty content field is provided along with a populated json list/dictionary, the json data
        will be encoded, dumped, and used in the content field as a bytes object. Otherwise, fields with
        empty-strings and bytes are treated as data, if provided, and preferred over `None`.

        Args:
            **kwargs: The keyword arguments to extract the content from.
                       Includes `content`, `_content`, `json`, and `text` fields.

        Returns:
            Optional[bytes]: The parsed bytes object containing the expected content

        """
        # resolve content types by converting to bytes
        text = kwargs["text"] if isinstance(kwargs.get("text", None), (str, bytes)) else None

        # encode and dump json content if provided
        json_data = json.dumps(kwargs["json"]) if isinstance(kwargs.get("json"), (dict, list)) else None

        content_sources = (kwargs.get("content"), kwargs.get("_content"), json_data, text)

        # search for the first populated (or most populated field accounting for provided, yet empty strings/bytes)
        content_fields = sorted(
            (content for content in content_sources if content is not None),
            key=lambda x: len(x) if isinstance(x, (str, bytes)) else -1,
            reverse=True,
        )

        # retrieve the content and encode if not already encoded
        content = (
            (content_fields[0].encode("utf-8") if isinstance(content_fields[0], str) else content_fields[0])
            if content_fields
            else None
        )

        return content

    @property
    def status(self) -> Optional[str]:
        """Helper property for retrieving a human-readable status description of the status.

        Returns:
            Optional[int]: The status description associated with the response (if available)

        """
        return self.reason or responses.get(self.status_code) if self.status_code else None

    @property
    def text(self) -> Optional[str]:
        """Helper property for retrieving the text from the bytes content as a string.

        Returns:
            Optional[str]: The decoded text from the content of the response

        """
        return self.content.decode() if isinstance(self.content, bytes) else None

    def json(self) -> Optional[List[Any] | Dict[str, Any]]:
        """Return JSON-decoded body from the underlying response, if available."""
        if not isinstance(self.content, bytes):
            logger.warning("The current response object does not contain jsonable content")
            return None
        try:
            return json.loads(self.content)
        except (JSONDecodeError, AttributeError, TypeError):
            logger.warning("The current ReconstructedResponse object " "does not have a valid json format.")
        return None

    @classmethod
    def _identify_invalid_fields(
        cls, response: requests.Response | ReconstructedResponse | ResponseProtocol
    ) -> dict[str, Any]:
        """Helper class method for identifying invalid fields within a response.

        This class iteratively validates the complete list of all invalid fields that populate the current
        ReconstructedResponse.

        If any invalid fields exist, the method returns a dictionary of each field and its corresponding value.

        Args:
            response (requests.Response | ReconstructedResponse | ResponseProtocol):
                A response or response-like field to identify invalid values within

        Returns:
            (dict[str, Any]): A dictionary containing each invalid field as a keys and their assigned values

        """

        if not (isinstance(response, requests.Response) or isinstance(response, ResponseProtocol)):  # noqa SIM101
            raise InvalidResponseStructureException(
                "The current class of type {type(response)} is not a response or response-like object."
            )

        # will hold the full list of all invalid fields and respective values
        invalid_fields: Dict[str, Any] = {}

        # in classes such as httpx, reason might instead be reason_phrase for instance:
        reason = getattr(response, "reason", None) or getattr(response, "reason_phrase", None)

        if not (isinstance(response.status_code, int) and 100 <= response.status_code < 600):
            invalid_fields["status_code"] = response.status_code
        if not (isinstance(response.url, str) and validate_url(response.url)):
            invalid_fields["url"] = response.url
        if not isinstance(reason, str):
            invalid_fields["reason"] = reason
        if not isinstance(response.content, bytes):
            invalid_fields["content"] = response.content
        if not (
            isinstance(response.headers, (dict, Mapping)) and all(isinstance(field, str) for field in response.headers)
        ):
            invalid_fields["headers"] = response.headers
        return invalid_fields

    def is_response(self) -> bool:
        """Method for directly validating the fields that indicate that a response has been minimally recreated
        successfully. The fields that are validated include:

            1) status codes (should be an integer)
            2) URLs     (should be a valid url)
            3) reasons  (should originate from a reason attribute or inferred from the status code)
            4) content  (should be a bytes field or encoded from a string text field)
            5) headers  (should be a dictionary with string fields and preferably a content type

        Returns:
            bool: Indicates whether the current reconstructed response minimally recreates a response object.

        """
        invalid_fields = self._identify_invalid_fields(self)

        invalid_fields = {
            field: value if field in ("status_code", "url") else type(value) for field, value in invalid_fields.items()
        }

        if invalid_fields:
            logger.warning(f"The following fields contain invalid values: {invalid_fields}")

        return not any(invalid_fields)

    def validate(self) -> None:
        """Raises an error if the recreated response object does not contain valid properties expected of a response. if
        the response validation is successful, a response is not raised and an object is not returned.

        Raises:
            InvalidResponseReconstructionException: if at least one field is determined to be invalid and
                                                    unexpected of a true response object.

        """
        if invalid_fields := self._identify_invalid_fields(self):
            raise InvalidResponseReconstructionException(
                "The ReconstructedResponse was not created successfully: Missing valid values for critical "
                f"fields to validate the response. The following fields are invalid: {invalid_fields}"
            )

    @property
    def ok(self) -> bool:
        """Indicates whether the current response indicates a successful request (200 <= status_code < 400) or whether
        an invalid response has been received. Accounts for the.

        Returns:
            bool: True if the status code is an integer value within the range of 200 and 399, False otherwise

        """
        return isinstance(self.status_code, int) and 200 <= self.status_code < 400

    def __eq__(self, other: Any) -> bool:
        """Helper method for validating whether reconstructed API responses are the same."""
        if isinstance(other, ReconstructedResponse) and asdict(self) == asdict(other):
            return True
        return False

    def raise_for_status(self) -> None:
        """Method that imitates the capability of the requests and httpx response types to raise errors when
        encountering status codes that are indicative of failed responses.

        As scholar_flux processes data that is generally only sent when  status codes are within the
        200s (or exactly 200 [ok]), an error is raised when encountering a value outside of this range.

        Raises:
            InvalidResponseReconstructionException: If the structure of the ReconstructedResponse is invalid
            RequestException: If the expected response is not within the range of 200-399

        """
        try:
            self.validate()

        except InvalidResponseReconstructionException as e:
            raise requests.RequestException(
                "Could not verify from the ReconstructedResponse to determine whether the "
                f"original request was successful: {e}"
            )

        if not 200 <= self.status_code < 300:
            raise requests.RequestException(
                "Expected a 200 (ok) status_code for the ReconstructedResponse. Received: "
                f"{self.status_code} ({self.reason or self.status})"
            )


__all__ = ["ReconstructedResponse"]
