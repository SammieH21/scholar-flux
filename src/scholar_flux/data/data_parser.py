# /data/data_parser.py
"""The scholar_flux.data.data_parser module defines the DataParser used within the scholar_flux API to parse JSON as
well as uncommon response formats.

This module implements the DataParser which allows for custom overrides to JSON, XML, and YAML files to prepare and
parse dictionary-based nested structures prior to record extraction and processing.

"""

from typing import Optional, Callable
from scholar_flux.data.base_parser import BaseDataParser
from scholar_flux.exceptions import DataParsingException
from scholar_flux.utils.response_protocol import ResponseProtocol
import requests

import logging

logger = logging.getLogger(__name__)


class DataParser(BaseDataParser):
    """Extensible class that handles the identification and parsing of typical formats seen in APIs that send news and
    academic articles in XML, JSON, and YAML formats.

    The BaseDataParser contains each of the necessary class elements to parse JSON, XML,
    and YAML formats as class methods while this class allows for the specification
    of additional parsers.

    Args:
        additional_parsers (Optional[dict[str, Callable]]):
            Allows overrides for parsers in addition to the JSON, XML and YAML parsers
            that are enabled by default.

    """

    def __init__(self, additional_parsers: Optional[dict[str, Callable]] = None):
        """On initialization, the data parser is set to use built-in class methods to parse json, xml, and yaml-based
        response content by default and the parse helper class to determine which parser to use based on the Content-
        Type.

        Args:
            additional_parsers (Optional[dict[str, Callable]]): Allows for the addition of
            new parsers and overrides to class methods to be used on content-type identification.

        """

        self.format_parsers = self.get_default_parsers() | (additional_parsers or {})

    def parse(
        self, response: requests.Response | ResponseProtocol, format: Optional[str] = None
    ) -> dict | list[dict] | None:
        """Parses the API response content using to core steps.

        1. Detects the API response format if a format is not already specified
        2. Uses the previously determined format to parse the content of the response
           and return a parsed dictionary (json) structure.

        Args:
            response (requests.Response | ResponseProtocol): The response or response-like object from the API request.
            format (str): The parser needed to format the response as a list of dicts

        Returns:
            dict: response dict containing fields including a list of metadata records as dictionaries.

        """

        try:
            use_format = format.lower() if format is not None else self.detect_format(response)

            parser = self.format_parsers.get(use_format, None) if use_format else None
            if parser is not None:
                return parser(response.content)
            else:
                logger.error("Unsupported format: %s", format)
                return None
        except DataParsingException:
            raise
        except Exception as e:
            raise DataParsingException(f"An error occurred during response content parsing: {e}") from e


__all__ = ["DataParser"]
