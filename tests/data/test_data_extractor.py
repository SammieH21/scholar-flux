import pytest
from typing import Dict, Any
from scholar_flux.data.base_extractor import BaseDataExtractor
from scholar_flux.data.data_extractor import DataExtractor
from scholar_flux.exceptions import DataExtractionException
from typing import Any, Dict, List


def test_extract_with_manual_paths(mock_academic_json: Dict[str, Any]):
    """
    Verify that DataExtractor correctly splits the payload when explicit
    paths are provided.  The JSON payload contains a top‑level ``data`` key
    that holds the list of records, and the remaining keys are considered
    metadata.
    """
    record_path = ["data"]
    # Use the real metadata keys that exist in the payload
    metadata = [
        ["total"],
        ["start"],
        ["pageLength"],
        ["recordsDisplayed"],
    ]

    extractor = DataExtractor(
        record_path=record_path,
        metadata_path=metadata,
    )

    base_extractor = BaseDataExtractor(
        record_path=record_path,
        metadata_path=metadata,
    )

    records, metadata = extractor(mock_academic_json)
    base_records, base_metadata = base_extractor(mock_academic_json)

    assert base_records == records and base_metadata == metadata

    # Records should be the list found under ``data``.
    assert isinstance(records, list)
    assert len(records) == 3
    assert records == mock_academic_json["data"]

    # Metadata should contain the keys we specified in overrides.
    assert metadata
    assert metadata["total"] == int(mock_academic_json["total"])
    assert metadata["start"] == int(mock_academic_json["start"])
    assert metadata["pageLength"] == int(mock_academic_json["pageLength"])
    assert metadata["recordsDisplayed"] == int(mock_academic_json["recordsDisplayed"])
    # No other keys should appear because we didn't override ``apiMessage`` or ``query``.
    assert set(metadata.keys()) == {"total", "start", "pageLength", "recordsDisplayed"}


def test_dynamic_identification_heuristics(mock_academic_json: Dict[str, Any]):
    """
    When no explicit paths are supplied, the extractor should
    automatically split the payload: everything that is not a list
    under a top‑level key is considered metadata.
    """
    extractor = DataExtractor()
    records, metadata = extractor(mock_academic_json)

    # Records should be the list under ``data``.
    assert records == mock_academic_json["data"]

    # Metadata should include all other top‑level keys.
    expected_metadata_keys = {
        "apiMessage",
        "query",
        "total",
        "start",
        "pageLength",
        "recordsDisplayed",
    }
    assert metadata and set(metadata.keys()) == expected_metadata_keys


def test_extract_records_returns_none_on_invalid_type(mock_academic_json: Dict[str, Any]):
    """
    When the data at ``record_path`` is not a list, ``extract_records`` should return None.
    """
    mock_academic_json["data"] = {"single": {"title": "Only one"}}
    extractor = DataExtractor(record_path=["data"])
    records = extractor.extract_records(mock_academic_json)
    assert records is None



@pytest.fixture
def extractor_manual_paths() -> DataExtractor:
    """
    Create an extractor with explicit record and metadata paths.
    The JSON fixture contains the top‑level keys:
      * data – a list of records
      * total, query, etc. – metadata
    """
    return DataExtractor(
        record_path=["data"],
        metadata_path=[
            ["query"],
            ["total"],
            ["apiMessage"],
            ["pageLength"],
            ["recordsDisplayed"],
        ],
    )


def test_extract_manual_paths(extractor_manual_paths: DataExtractor, mock_academic_json: Dict[str, Any]):
    """
    Verify that both metadata and records are returned when explicit
    paths are supplied.
    """
    records, metadata = extractor_manual_paths(mock_academic_json)

    # metadata
    assert metadata == {
        "apiMessage": "This JSON was provided by scholar_flux testing mocks",
        "query": "Computationaly Aided Analysis",
        "total": 3,
        "pageLength": 3,
        "recordsDisplayed": 3,
    }

    # records
    assert isinstance(records, list)
    assert len(records) == 3
    for r in records:
        assert isinstance(r, dict)
        # every record must contain a DOI
        assert "doi" in r
        assert r["doi"].startswith("10.")


def test_extract_metadata_without_paths(mock_academic_json: Dict[str, Any]):
    """
    When no metadata path is supplied, extract_metadata should
    return an empty dict and log the information.
    """
    extractor = DataExtractor(record_path=["data"])
    # override metadata_path to None to force an empty dict
    extractor.metadata_path = {}
    assert extractor.extract_metadata(mock_academic_json) == {}


def test_extract_records_wrong_path_type():
    """
    Providing a non‑list record_path should raise a DataExtractionException
    during extractor initialisation.
    """
    with pytest.raises(DataExtractionException) as exc:
        DataExtractor(record_path="data")  # type error – must be a list
    assert "list" in str(exc.value)


def test_extract_records_invalid_path(extractor_manual_paths: DataExtractor, mock_academic_json: Dict[str, Any]):
    """
    When record_path points to a non‑list, extract_records must return None.
    """
    # point to a key that contains a string instead of a list
    extractor_manual_paths.record_path = ["start"]
    records = extractor_manual_paths.extract_records(mock_academic_json)
    assert records is None


def test_extract_records_success(extractor_manual_paths: DataExtractor, mock_academic_json: Dict[str, Any]):
    """
    With a correct record_path the extractor should return the full list of records.
    """
    records = extractor_manual_paths.extract_records(mock_academic_json)
    assert isinstance(records, list)
    assert len(records) == 3
    # check that each record contains the expected identifier field
    ids = {r["identifier"] for r in records}
    expected_ids = {
        "doi:10.1000/j.jmb.2025.00123",
        "doi:10.1000/j.canc.2025.00999",
        "doi:10.1000/j.soft.2025.00456",
    }
    assert ids == expected_ids


def test_dynamic_identification_basic(mock_academic_json: Dict[str, Any]):
    """
    Verify that the extractor can split the payload into metadata
    (query, total, etc.) and records (the items in ``data``) when no
    explicit paths are provided.
    """
    extractor = DataExtractor()          # no paths
    metadata, records = extractor.dynamic_identification(mock_academic_json)

    # All top‑level meta keys should be in the metadata dict
    assert set(metadata.keys()) == {"apiMessage", "query", "total", "start", "pageLength", "recordsDisplayed"}
    # The data list should be returned as records
    assert len(records) == 3
    assert all("doi" in r for r in records)


def test_extract_from_dict_and_list(mock_academic_json: Dict[str, Any]):
    """
    ``extract`` must work with a plain dict and with a list of dicts.
    """
    extractor = DataExtractor(
        record_path=["data"],
        metadata_path={"query": ["query"], "total": ["total"]},
    )

    # dict input
    records, metadata = extractor.extract(mock_academic_json)
    assert isinstance(records, list) and len(records) == 3
    assert metadata["query"] == "Computationaly Aided Analysis"

    # list input (should be converted via try_dict)
    # create a minimal wrapper list: [[dict]] – the extractor expects a single dict
    wrapper = [mock_academic_json]
    records, metadata = extractor.extract(wrapper)
    assert isinstance(records, list) and len(records) == 3
    assert metadata["total"] == 3


def test_identify_by_key_logic():
    """
    Ensure that _identify_by_key returns True when a record contains
    one of the dynamic record identifiers.
    """
    extractor = DataExtractor()
    record_with_title = {"title": "Some title", "foo": "bar"}
    record_without_title = {"foo": "bar"}

    assert extractor._identify_by_key(record_with_title, extractor.dynamic_record_identifiers)
    assert not extractor._identify_by_key(record_without_title, extractor.dynamic_record_identifiers)


def test_metadata_path_dict(mock_academic_json):
    """
    Test that a dictionary of metadata paths works correctly.
    """
    extractor = DataExtractor(
        record_path=["data"],
        metadata_path={
            "query": ["query"],
            "total": ["total"],
        },
    )
    records, metadata = extractor.extract(mock_academic_json)
    assert metadata == {"query": "Computationaly Aided Analysis", "total": 3}
    assert records and len(records) == 3


@pytest.mark.parametrize("bad_path", ["data", 5])
def test_invalid_metadata_path_type(bad_path: Any, mock_academic_json: List):
    """
    Passing a non‑list/dict for metadata_path should raise an exception.
    """
    
    with pytest.raises(DataExtractionException):
        extractor = DataExtractor(record_path=["data"], metadata_path=bad_path)  # type: ignore[arg-type]
