import pytest
from scholar_flux.utils import JsonFileUtils
from pathlib import Path
from typing import cast


@pytest.fixture
def sample_json() -> list[dict]:
    """A JSON fixture used to mock a simple json data set to validate the JSON processing utilities that filter,
    process, and flatten JSON files."""
    sample_json = [
        {
            "name": "John",
            "address": {"street": "123 Maple Street", "city": "Springfield", "state": "IL"},
            "phones": [{"type": "home", "number": "123-456-7890"}, {"type": "work", "number": "098-765-4321"}],
        }
    ]
    return sample_json


@pytest.fixture
def mock_api_parsed_json_records() -> list[dict]:
    """A mock json data set used to verify whether recursive and path-based scholar_flux JSON processing utilities
    produce the expected result using a format that more closely matches the general format that is returned by academic
    APIs."""
    return [
        {
            "authors": {"principle_investigator": "Dr. Smith", "assistant": "Jane Doe"},
            "doi": "10.1234/example.doi",
            "title": "Sample Study",
            "abstract": ["This is a sample abstract.", "keywords: 'sample', 'abstract'"],
            "genre": {"subspecialty": "Neuroscience"},
            "journal": {"topic": "Sleep Research"},
            "affiliations": ["KSU", "LSU"],
        },
        {
            "authors": {"principle_investigator": "Dr. Lee", "assistant": "John Roe"},
            "doi": "10.5678/example2.doi",
            "title": "Another Study",
            "abstract": "Another abstract.",
            "genre": {"subspecialty": "Psychiatry"},
            "journal": {"topic": "Dreams"},
            "affiliations": ["LSU"],
        },
    ]


@pytest.fixture
def mock_complex_json_records() -> list[dict]:
    path = Path(__file__).resolve().parent.parent / "mocks" / "mock_response_data.json"
    return cast("list[dict]", JsonFileUtils.load_data(path))


__all__ = ["sample_json", "mock_api_parsed_json_records", "mock_complex_json_records"]
