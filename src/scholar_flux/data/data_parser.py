from typing import Dict, List, Optional, Union, Tuple, Any, TYPE_CHECKING
from scholar_flux.utils import get_nested_data, try_int
from scholar_flux.exceptions import XMLToDictImportError, YAMLImportError
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


class DataParser:
    def __init__(self):
        pass

    def detect_format(self, response: requests.Response) -> str | None:
        content_type = response.headers.get('Content-Type', '')
        if 'xml' in content_type:
            return 'xml'
        elif 'json' in content_type:
            return 'json'
        elif 'yaml' in content_type or 'yml' in content_type:
            return 'yaml'
        else:
            logger.warning("Unsupported content type: %s", content_type)
            return 'unknown'

    def parse(self, response: requests.Response, format: Optional[str] = None) -> Dict[str,Any] | List[Dict[str,Any]] | None:
        """Parses the API response data for your application's needs.

        Args:
            response (response type) : The response object from the API request.
            format (str) : The parser needed to format the response as a list of dicts

        Returns:
            [dict] : response dict containing fields including a list of metadata records as dictionaries.
        """
        use_format = format if format is not None else self.detect_format(response)

        format_parsers = {
            'xml': self.parse_xml,
            'json': self.parse_json,
            'yaml': self.parse_yaml,
        }

        parser = format_parsers.get(use_format,None) if use_format else None
        if parser is not None:
            return parser(response.content)
        else:
            logger.error("Unsupported format: %s", format)
            return None

    def parse_xml(self, content: bytes) -> Dict[str,Any] | List[Dict[str,Any]]:
        """Parses XML content."""
        if xmltodict is None:
            raise XMLToDictImportError
        return xmltodict.parse(content)

    def parse_json(self, content: bytes) -> Dict[str,Any] | List[Dict[str,Any]]:
        """Parses JSON content."""
        return json.loads(content)

    def parse_yaml(self, content: bytes) -> Dict[str,Any] | List[Dict[str,Any]]:
        """Parses YAML content. Example of adding YAML support."""
        if yaml is None:
            raise YAMLImportError
        return yaml.safe_load(content)
