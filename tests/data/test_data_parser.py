from scholar_flux.exceptions import DataParsingException
from scholar_flux.data import BaseDataParser, DataParser
from scholar_flux import logger
import json
import pytest
import requests


def custom_json_parser(response_content: bytes) -> dict:
    """Custom JSON parser for testing whether overrides occur as intended with the `DataParser`"""
    records = json.loads(response_content)
    logger.debug(f"Loaded {len(records)} json records with custom parser")
    return records


def test_json_data_parsing(plos_page_1_response):
    """Tests whether a basic response with json content can be parsed as intended without error."""
    assert isinstance(plos_page_1_response, requests.Response)

    base_parser = BaseDataParser()

    base_parsed_response = base_parser.parse(plos_page_1_response)
    assert isinstance(base_parsed_response, dict) and base_parsed_response


def test_xml_data_parsing(mock_pubmed_search_response, xml_parsing_dependency):
    """Verifies that an attempt to parse an XML response will return a dictionary when available."""
    if not xml_parsing_dependency:
        pytest.skip("XML dependency not available for testing the data parser")

    assert isinstance(mock_pubmed_search_response, requests.Response)

    base_parser = BaseDataParser()

    base_parsed_response = base_parser.parse(mock_pubmed_search_response)
    assert isinstance(base_parsed_response, dict) and base_parsed_response


def test_yaml_data_parsing(academic_yaml_response, mock_academic_json, yaml_parsing_dependency):
    """Verifies that an attempt to parse a YAML response will return a dictionary when available."""
    if not yaml_parsing_dependency:
        pytest.skip("YAML dependency not available for testing the data parser")
    assert isinstance(academic_yaml_response, requests.Response)

    base_parser = BaseDataParser()

    base_parsed_response = base_parser.parse(academic_yaml_response)
    assert isinstance(base_parsed_response, dict) and base_parsed_response
    assert mock_academic_json == base_parsed_response


def test_custom_data_parser(mock_academic_json, academic_json_response, caplog):
    """Uses a custom JSON data parser to verify whether logging occurs as intended with parser overrides."""
    parser = DataParser({"json": custom_json_parser})
    loaded_records = parser(academic_json_response)
    assert isinstance(loaded_records, dict) and loaded_records == mock_academic_json
    assert f"Loaded {len(mock_academic_json)} json records with custom parser" in caplog.text


def test_json_data_parsing_invalid():
    """Validates that, on encountering a value that is not a JSON format, the parser raises a DataParsingException."""
    invalid_response = requests.Response()
    invalid_response._content = b"not a json"
    invalid_response.headers["Content-Type"] = "application/json"
    base_parser = BaseDataParser()
    with pytest.raises(DataParsingException):
        base_parser.parse(invalid_response)
