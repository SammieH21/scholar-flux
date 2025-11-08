# /data/base_parser.py
"""The scholar_flux.data.base_parser module contains the core logic for parsing data structures received from APIs.

This module implements the BaseDataParser that is used to prepare and parse JSON, XML, and YAML into dictionary-based
nested structures prior to record extraction and processing.

"""
from typing import Callable, TYPE_CHECKING
from scholar_flux.exceptions import XMLToDictImportError, YAMLImportError
from scholar_flux.exceptions import DataParsingException
from scholar_flux.utils.response_protocol import ResponseProtocol
from scholar_flux.utils.repr_utils import generate_repr_from_string
import json
import requests

import logging

logger = logging.getLogger(__name__)
if TYPE_CHECKING:
    import xmltodict
    import yaml
else:
    try:
        import xmltodict
    except ImportError:
        xmltodict = None

    try:
        import yaml
    except ImportError:
        yaml = None


class BaseDataParser:
    """Base class responsible for parsing typical formats seen in APIs that send news and academic articles in XML,
    JSON, and YAML formats."""

    def __init__(self):
        """On initialization, the data parser is set to use built-in class methods to parse json, xml, and yaml-based
        response content by default and the parse helper class to determine which parser to use based on the Content-
        Type.

        Args:
            additional_parsers (Optional[dict[str, Callable]]): Allows for the addition of
            new parsers and overrides to class methods to be used on content-type identification.

        """
        pass

    @classmethod
    def detect_format(cls, response: requests.Response | ResponseProtocol) -> str | None:
        """Helper method for determining the format corresponding to a response object."""
        if not isinstance(response, requests.Response) and not isinstance(response, ResponseProtocol):
            raise DataParsingException(f"Expected a response or response-like object, received type {type(response)}")

        content_type = response.headers.get("Content-Type", "")
        if "xml" in content_type:
            return "xml"
        elif "json" in content_type:
            return "json"
        elif "yaml" in content_type or "yml" in content_type:
            return "yaml"
        else:
            logger.warning("Unsupported content type: '%s'", content_type)
            return "unknown"

    @classmethod
    def parse_from_defaults(cls, response: requests.Response | ResponseProtocol) -> dict | list[dict] | None:
        """Detects the API response format if a format is not already specified and uses one of the default structures
        to parse the data structure into a dictionary depending on the content type stored in the API response header.

        Args:
            response (response type): The response (or response-like) object from the API request.

        Returns:
            dict: response dict containing fields including a list of metadata records as dictionaries.

        """
        use_format = cls.detect_format(response)

        format_parsers = cls.get_default_parsers()
        parser = format_parsers.get(use_format) if use_format else None

        if parser is not None:
            return parser(response.content)
        else:
            logger.error("Unsupported format: '%s'", use_format)
            return None

    @classmethod
    def parse_xml(cls, content: bytes) -> dict | list[dict]:
        """Uses the optional `xmltodict` library to parse XML content into a dictionary."""
        if xmltodict is None:
            raise XMLToDictImportError
        return xmltodict.parse(content)

    @classmethod
    def parse_json(cls, content: bytes) -> dict | list[dict]:
        """Uses the standard `json` library to parse XML content into a dictionary."""
        return json.loads(content)

    @classmethod
    def parse_yaml(cls, content: bytes) -> dict | list[dict]:
        """Uses the optional `yaml` library to parse YAML content."""
        if yaml is None:
            raise YAMLImportError
        return yaml.safe_load(content)

    @classmethod
    def get_default_parsers(cls) -> dict[str, Callable]:
        """Helper method used to retrieve the default parsers to parse XML, JSON, and YAML response data.

        Returns:
            dict[str, Callable]: A dictionary of data parsers that can be used to parse response data
                                 into usable json format

        """
        format_parsers = {
            "xml": cls.parse_xml,
            "json": cls.parse_json,
            "yaml": cls.parse_yaml,
        }
        return format_parsers

    def parse(self, response: requests.Response | ResponseProtocol) -> dict | list[dict] | None:
        """Uses one of the default parsing methods to extract a dictionary of data from the response content."""
        try:
            return self.parse_from_defaults(response)
        except DataParsingException:
            raise
        except Exception as e:
            raise DataParsingException(f"An error occurred during response content parsing: {e}") from e

    def __call__(self, response: requests.Response | ResponseProtocol, *args, **kwargs) -> dict | list[dict] | None:
        """Helper method for Parsing API response content into dictionary (json) structure.

        Args:
            response (response type): The response object from the API request.
            format (str): The parser needed to format the response as a list of dicts
        Returns:
            dict: response dict containing fields including a list of metadata records as dictionaries.

        """
        return self.parse(response, *args, **kwargs)

    def structure(self, flatten: bool = False, show_value_attributes: bool = True) -> str:
        """Helper method for retrieving a string representation of the structure of the current BaseDataParser or
        subclass of the BaseDataParser.

        Override this for more specific descriptions of attributes and defaults.
        Useful for showing the options being used for parsing response content into dictionary objects.

        Returns:
            str: A string representation of the base parser indicating all registered or default parsers

        """
        class_name = self.__class__.__name__
        format_parsers = getattr(self, "format_parsers", self.get_default_parsers()).keys()
        return generate_repr_from_string(
            class_name,
            dict(format_parsers=format_parsers),
            flatten=flatten,
            show_value_attributes=show_value_attributes,
        )

    def __repr__(self):
        """Helper method for identifying the current implementation of the BaseDataParser and its configuration."""
        return self.structure()


__all__ = ["BaseDataParser"]
