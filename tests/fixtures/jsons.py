import pytest

@pytest.fixture
def sample_json():

    return [
            {
                "name": "John",
                "address": {
                    "street": "123 Maple Street",
                    "city": "Springfield",
                    "state": "IL"
                },
                "phones": [
                    {"type": "home", "number": "123-456-7890"},
                    {"type": "work", "number": "098-765-4321"}
                ]
            }
        ]


@pytest.fixture
def mock_api_parsed_json_records():
    return [
        {
            "authors": {
                "principle_investigator": "Dr. Smith",
                "assistant": "Jane Doe"
            },
            "doi": "10.1234/example.doi",
            "title": "Sample Study",
            "abstract": ["This is a sample abstract.", "keywords: 'sample', 'abstract'"],
            "genre": {
                "subspecialty": "Neuroscience"
            },
            "journal": {
                "topic": "Sleep Research"
            }
        },
        {
            "authors": {
                "principle_investigator": "Dr. Lee",
                "assistant": "John Roe"
            },
            "doi": "10.5678/example2.doi",
            "title": "Another Study",
            "abstract": "Another abstract.",
            "genre": {
                "subspecialty": "Psychiatry"
            },
            "journal": {
                "topic": "Dreams"
            }
        }
    ]
