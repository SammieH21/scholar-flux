from typing import Optional, Callable
from scholar_flux.data.base_parser import BaseDataParser
import requests

import logging

logger = logging.getLogger(__name__)


class DataParser(BaseDataParser):
    """
    Extensible class that handles the identification and parsing of typical formats seen
    in APIs that send news and academic articles in XML, JSON, and YAML formats.

    The BaseDataParser contains each of the necessary class elements to parse JSON, XML,
    and YAML formats as classmethods while this class allows for the specification
    of additional parsers.

    Args:
        additional_parsers (Optional[dict[str, Callable]]):
            Allows overrides for parsers in addition to the JSON, XML and YAML parsers
            that are enabled by default.
    """

    def __init__(self, additional_parsers: Optional[dict[str, Callable]] = None):
        """
        On initialization, the data parser is set to use built-in class methods to
        parse json, xml, and yaml-based response content by default and the parse
        halper class to determine which parser to use based on the Content-Type.

        Args:
            additional_parsers (Optional[dict[str, Callable]]): Allows for the addition of
            new parsers and overrides to class methods to be used on content-type identification.
        """

        self.format_parsers = self.get_default_parsers() | (additional_parsers or {})

    def parse(
        self, response: requests.Response, format: Optional[str] = None
    ) -> dict | list[dict] | None:
        """
        Parses the API response content using to core steps.
        1. Detects the API response format if a format is not already specified
        2. Uses the previously determined format to parse the content of the response
           and return a parsed dictionary (json) structure.

        Args:
            response (response type): The response object from the API request.
            format (str): The parser needed to format the response as a list of dicts

        Returns:
            dict: response dict containing fields including a list of metadata records as dictionaries.
        """

        use_format = (
            format.lower() if format is not None else self.detect_format(response)
        )

        parser = self.format_parsers.get(use_format, None) if use_format else None
        if parser is not None:
            return parser(response.content)
        else:
            logger.error("Unsupported format: %s", format)
            return None

    def __repr__(self):
        """
        Helper method for indentifying the current implementation of the DataParser.
        Useful for showing the options being used for parsing response content into dictionary objects
        """
        class_name = self.__class__.__name__
        return f"{class_name}(format_parsers={self.format_parsers.keys()})"
