import pytest
from typing import Any
from scholar_flux.data.base_extractor import BaseDataExtractor
from scholar_flux.data.data_extractor import DataExtractor
from scholar_flux.exceptions import DataExtractionException
from scholar_flux.utils import try_int, PathUtils
from unittest.mock import patch
from tests.testing_utilities import raise_error
import re
import json
import copy


def test_extract_with_manual_paths(mock_academic_json):
    """Verifies that DataExtractor correctly splits the parsed response content when explicit paths are provided.

    The JSON response contains a top‑level `data` key that holds the list of records, and the remaining keys are
    considered metadata.

    """
    record_path = ["data"]
    # Use the real metadata keys that exist in the payload
    metadata_path = [
        ["total"],
        ["start"],
        ["pageLength"],
        ["recordsDisplayed"],
    ]

    extractor = DataExtractor(
        record_path=record_path,
        metadata_path=metadata_path,
    )

    base_extractor = BaseDataExtractor(
        record_path=record_path,
        metadata_path=metadata_path,
    )

    records, metadata = extractor(mock_academic_json)
    base_records, base_metadata = base_extractor(mock_academic_json)

    assert base_records == records and base_metadata == metadata

    # Records should be the list found under ``data``.
    assert isinstance(records, list)
    assert len(records) == 3
    assert records == mock_academic_json["data"]

    # Metadata should contain the keys we specified in overrides.
    assert metadata and isinstance(metadata, dict)
    assert metadata["total"] == try_int(mock_academic_json["total"])
    assert metadata["start"] == try_int(mock_academic_json["start"])
    assert metadata["pageLength"] == try_int(mock_academic_json["pageLength"])
    assert metadata["recordsDisplayed"] == try_int(mock_academic_json["recordsDisplayed"])
    # No other keys should appear because we didn't override ``apiMessage`` or ``query``.
    assert isinstance(metadata, dict) and set(metadata.keys()) == {"total", "start", "pageLength", "recordsDisplayed"}


def test_extract_records_with_annotations(mock_academic_json):
    """Verifies that DataExtractor correctly retrieves and annotates extracted records with `annotate_records=True`."""
    extractor = DataExtractor(annotate_records=True)

    records, _ = extractor(mock_academic_json)

    assert records and len(records) == 3
    assert all(
        record[DataExtractor.EXTRACTION_INDEX_KEY] == i and record[DataExtractor.RECORD_ID_KEY].endswith(f"_{i}")
        for i, record in enumerate(records)
    )


def test_prepare_mixed_path_list_string_representations(mock_academic_json):
    """Verifies that the DataExtractor correctly prepares record and metadata paths with string representations."""
    record_path = ["data"]
    # Use the real metadata keys that exist in the payload
    metadata_path: list[str | list[str]] = [
        ["total"],
        ["start"],
        ["pageLength"],
        ["recordsDisplayed"],
    ]

    record_path_string = "data"
    metadata_path_strings = metadata_path.copy()
    for i in range(2):
        metadata_path_strings[i] = ".".join(metadata_path_strings[i])

    assert DataExtractor._prepare_metadata_path(metadata_path_strings) == metadata_path  # type: ignore
    assert DataExtractor._prepare_record_path(record_path_string) == record_path


def test_prepare_metadata_dictionary_path_representations(mock_academic_json):
    """Verifies that DataExtractor correctly prepares metadata dictionary paths from path string representations."""
    # Use the real metadata keys that exist in the payload
    metadata_path: dict[str, str] = {
        "total": "total",
        "start": "start",
        "pageLength": "pageLength",
        "recordsDisplayed": "recordsDisplayed",
        "created-at": "origin.created-at",
    }

    assert DataExtractor._prepare_metadata_path(metadata_path) == {
        key: value.split(PathUtils.DELIMITER) for key, value in metadata_path.items()
    }


def test_dynamic_identification_heuristics(mock_academic_json):
    """When no explicit paths are supplied, the extractor should automatically split the response content: everything
    that is not a list under a top‑level key is considered metadata."""
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


def test_extract_records_returns_none_on_invalid_type(mock_academic_json):
    """When the data at `record_path` is not a list, `extract_records` should return None."""
    mock_academic_json["data"] = {"single": {"title": "Only one"}}
    extractor = DataExtractor(record_path=["data"])
    records = extractor.extract_records(mock_academic_json)
    assert records is None


@pytest.fixture
def extractor_manual_paths() -> DataExtractor:
    """Create an extractor with explicit record and metadata paths. The JSON fixture contains the top‑level keys:

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


def test_extract_manual_paths(extractor_manual_paths: DataExtractor, mock_academic_json):
    """Verifies that both metadata and records are returned when explicit paths are supplied."""
    records, metadata = extractor_manual_paths(mock_academic_json)

    # metadata
    assert metadata == {
        "apiMessage": "This JSON was provided by scholar_flux testing mocks",
        "query": "Computationally Aided Analysis",
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


def test_extract_metadata_without_paths(mock_academic_json):
    """When no metadata path is supplied, extract_metadata should return an empty dict and log the information."""
    extractor = DataExtractor(record_path=["data"])
    # override metadata_path to None to force an empty dict
    extractor.metadata_path = {}
    assert extractor.extract_metadata(mock_academic_json) == {}


def test_extractor_invalid_configuration():
    """Providing a non‑list record_path should raise a DataExtractionException during extractor initialization."""
    with pytest.raises(DataExtractionException) as excinfo:
        DataExtractor(record_path=23)  # type: ignore
    assert f"A list is required for a record path. Received: {type(23)}" in str(excinfo.value)

    with pytest.raises(DataExtractionException) as excinfo:
        DataExtractor(metadata_path="invalid metadata identifier")  # type: ignore
    assert f"The provided metadata path override is not a list or dictionary: {type('')}" in str(excinfo.value)

    with pytest.raises(DataExtractionException) as excinfo:
        DataExtractor(dynamic_metadata_identifiers="invalid metadata")  # type: ignore
    assert f"The dynamic metadata identifiers provided must be a tuple or list. Received: {type('')}" in str(
        excinfo.value
    )

    with pytest.raises(DataExtractionException) as excinfo:
        DataExtractor(dynamic_record_identifiers="invalid record identifier")  # type: ignore
    assert f"The dynamic record identifiers provided must be a tuple or list. Received: {type('')}" in str(
        excinfo.value
    )


def test_extractor_invalid_nested_configuration():
    """Verifies whether providing a non‑list record_path will raise a DataExtractionException during extractor
    initialization."""
    list_set = [{True, False}]
    with pytest.raises(DataExtractionException) as excinfo:
        DataExtractor(record_path=list_set)  # type: ignore
    assert f"At least one path in the provided record path is not an integer or string: {list_set}" in str(
        excinfo.value
    )

    with pytest.raises(DataExtractionException) as excinfo:
        DataExtractor(metadata_path=list_set)  # type: ignore
    assert (
        f"At least one path in the provided metadata path override is not a list, integer, or string: {list_set}"
        in str(excinfo.value)
    )

    with pytest.raises(DataExtractionException) as excinfo:
        DataExtractor(dynamic_metadata_identifiers=list_set)  # type: ignore
    assert (
        f"At least one value in the provided dynamic metadata identifier is not an integer or string: {list_set}"
        in str(excinfo.value)
    )

    with pytest.raises(DataExtractionException) as excinfo:
        DataExtractor(dynamic_record_identifiers=list_set)  # type: ignore
    assert (
        f"At least one value in the provided dynamic record identifier is not an integer or string: {list_set}"
        in str(excinfo.value)
    )


def test_extract_records_invalid_path(extractor_manual_paths: DataExtractor, mock_academic_json, caplog):
    """Verifies that an attempt to provide an invalid record path type returns None.

    Also verifies that, when a metadata path cannot be found, a dictionary is still returned with a value of `None` for
    the key.

    """
    # point to a key that contains a string instead of a list
    extractor_manual_paths.record_path = ["start"]
    extractor_manual_paths.metadata_path = [["starting"]]
    records = extractor_manual_paths.extract_records(mock_academic_json)
    metadata = extractor_manual_paths.extract_metadata(mock_academic_json)
    assert records is None
    assert metadata.get("starting") is None
    assert f"The following metadata keys are missing or None: {', '.join(['starting'])}" in caplog.text


def test_key_error(mock_academic_json, extractor_manual_paths, caplog):
    """Tests whether an attempt to extract records from a dictionary, when KeyErrors occur, is instead caught and
    logged."""
    extractor_manual_paths.metadata_path = [["starting"]]

    metadata = extractor_manual_paths.extract_metadata(mock_academic_json)
    assert metadata == {"starting": None}
    msg = "The starting key is missing"
    with patch("scholar_flux.data.base_extractor.get_nested_data", side_effect=KeyError(msg)):
        extracted_metadata = extractor_manual_paths.extract_metadata(mock_academic_json)

    assert not extracted_metadata
    assert (f"Error extracting metadata due to missing key: '{msg}'") in caplog.text


def test_blank_extraction(extractor_manual_paths, caplog):
    """Verifies that an attempt to extract records when None is specified will also return None."""
    assert extractor_manual_paths.extract_records(None) is None
    assert "No records extracted from path" in caplog.text


def test_dictionary_transformation():
    """Tests that the steps taken to extract both records and metadata from a dictionary work as intended."""
    extractor = DataExtractor()
    data = [[{"a": 1}, {"b": 3}, {"c": 4}, {"d": 5}]]
    prepped_page = extractor._prepare_page(data)  # type: ignore
    assert isinstance(prepped_page, dict)
    assert prepped_page == {"0": {"a": 1}, "1": {"b": 3}, "2": {"c": 4}, "3": {"d": 5}}
    records, metadata = extractor.extract(prepped_page)
    assert records == []
    assert metadata == {"a": 1, "b": 3, "c": 4, "d": 5}


def test_blank_prepare_page():
    """Verifies that attempting to extract records and metadata from a list of dictionaries will raise an error when
    `None` is provided instead of a list or dictionary."""
    extractor = DataExtractor()
    with pytest.raises(DataExtractionException):
        _ = extractor._prepare_page(None)  # type: ignore


def test_extract_records_success(extractor_manual_paths: DataExtractor, mock_academic_json):
    """With a correct record_path the extractor should return the full list of records."""
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


def test_invalid_extract_metadata(extractor_manual_paths: DataExtractor, mock_academic_json, caplog):
    """With a correct record_path the extractor should return the full list of records."""
    extractor_manual_paths.metadata_path = True  # type: ignore
    with pytest.raises(DataExtractionException) as excinfo:
        _ = extractor_manual_paths.extract_metadata(mock_academic_json)

    msg = (
        "An unexpected error occurred during metadata extraction due to the following exception: "
        "'bool' object has no attribute 'items'"
    )
    assert msg in str(excinfo.value)
    assert msg in caplog.text


def test_invalid_extract_records(extractor_manual_paths: DataExtractor, mock_academic_json, caplog):
    """With a correct record_path the extractor should return the full list of records."""
    extractor_manual_paths.record_path = True  # type: ignore
    with pytest.raises(DataExtractionException) as excinfo:
        _ = extractor_manual_paths.extract_records(mock_academic_json)

    msg = (
        "An unexpected error occurred during record extraction due to the following exception: "
        "'bool' object is not iterable"
    )

    assert msg in str(excinfo.value)
    assert msg in caplog.text


def test_basic_dynamic_identification(mock_academic_json):
    """Verifies that the extractor can split the payload into metadata (query, total, etc.) and records.

    Each of the items in `data` should be extracted into a separate list of dictionary records, even when no explicit
    paths are provided.

    """
    extractor = DataExtractor()  # no paths
    records, metadata = extractor.dynamic_identification(mock_academic_json)

    # All top‑level meta keys should be in the metadata dict
    assert set(metadata.keys()) == {"apiMessage", "query", "total", "start", "pageLength", "recordsDisplayed"}
    # The data list should be returned as records
    assert len(records) == 3
    assert all("doi" in r for r in records)


def test_extract_from_dict_and_list(mock_academic_json):
    """Verifies that the `extract` method works with a plain dict and a dictionary nested within a list."""
    extractor = DataExtractor(
        record_path=["data"],
        metadata_path={"query": ["query"], "total": ["total"]},
    )

    # dict input
    records, metadata = extractor.extract(mock_academic_json)
    assert isinstance(records, list) and len(records) == 3
    assert metadata and metadata["query"] == "Computationally Aided Analysis"

    # list input (should be converted via try_dict)
    wrapper = [mock_academic_json]
    records, metadata = extractor.extract(wrapper)
    assert isinstance(records, list) and len(records) == 3
    assert metadata and metadata["total"] == 3


def test_identify_by_key_logic():
    """Tests whether _identify_by_key returns True when a record contains one of the dynamic record identifiers."""
    extractor = DataExtractor()
    record_with_title = {"title": "Some title", "foo": "bar"}
    record_without_title = {"foo": "bar"}

    assert extractor._identify_by_key(record_with_title, extractor.dynamic_record_identifiers)
    assert not extractor._identify_by_key(record_without_title, extractor.dynamic_record_identifiers)


def test_metadata_path_dict(mock_academic_json):
    """Tests that a dictionary of metadata paths correctly extracts records that can be in each path."""
    extractor = DataExtractor(
        record_path=["data"],
        metadata_path={
            "query": ["query"],
            "total": ["total"],
        },
    )
    records, metadata = extractor.extract(mock_academic_json)
    assert metadata == {"query": "Computationally Aided Analysis", "total": 3}
    assert records and len(records) == 3


@pytest.mark.parametrize("bad_path", ["data", 5])
def test_invalid_metadata_path_type(bad_path: Any, mock_academic_json: list):
    """Verifies that passing a non‑list/dict for metadata_path should raise an exception."""

    with pytest.raises(DataExtractionException):
        # the extractor shouldn't accept a list of containing integers
        _ = DataExtractor(record_path=["data"], metadata_path=bad_path)  # type: ignore[arg-type]


def test_key_discovery(caplog):
    """Verifies that keys are discovered correctly with the default dynamic record identification heuristics."""
    extractor = DataExtractor(dynamic_metadata_identifiers=["a", "b"])
    # specifying metadata directly
    json_records = [{"x": 1, "y": 0}, {"x": 3, "y": 2}, {"x": 5, "y": 6}]
    json_data = {"a": {"red": 1}, "b": {"blue": 2}, "nested": {"data": json_records}}

    extracted_records, extracted_metadata = extractor.dynamic_identification(json_data)

    assert extracted_metadata == {k: d for k, d in json_data.items() if k != "nested"}
    assert extracted_records == json_records

    # no arguments to the extractor, extracts all records by default
    extractor = DataExtractor()
    extracted_records, extracted_metadata = extractor.dynamic_identification(json_data)
    assert extracted_metadata == {"red": 1, "blue": 2}
    assert extracted_records == json_records

    # identifying records from whether it contains the key, 'x'
    extractor = DataExtractor(dynamic_record_identifiers=["x"])
    json_records = [{"x": 1, "y": 0}]
    json_data = {"a": {"red": 1}, "b": {"blue": 2}, "nested": {"data": json_records}}
    extracted_records, extracted_metadata = extractor.dynamic_identification(json_data)
    assert extracted_metadata == {"red": 1, "blue": 2}
    assert extracted_records == json_records

    # skips registration of the single record as a record without a heuristic, thinks it metadata
    extractor = DataExtractor(dynamic_record_identifiers=[])
    extracted_records, extracted_metadata = extractor.dynamic_identification(json_data)
    assert extracted_metadata == {"red": 1, "blue": 2, "x": 1, "y": 0}
    assert extracted_records == []

    json_records = []
    json_data = {"a": {"red": 1}, "b": {"blue": 2}, "nested": {"data": json_records}}
    extracted_records, extracted_metadata = extractor.dynamic_identification(json_data)
    assert extracted_metadata == {"red": 1, "blue": 2}
    assert extracted_records == json_records
    assert "Element at key: data is empty" in caplog.text


def test_base_representation():
    extraction_path = ["test", "path"]
    metadata_paths = [["path", "x1"], ["path", "x2"]]
    extractor = BaseDataExtractor(metadata_path=metadata_paths, record_path=extraction_path)
    representation = repr(extractor)
    assert re.search(r"^BaseDataExtractor\(.*\)$", representation, re.DOTALL)
    assert f"record_path={extraction_path}" in representation
    assert f"metadata_path={metadata_paths}" in representation


def test_representation():
    extraction_path = ["test", "path"]
    metadata_paths = [["path", "x1"], ["path", "x2"]]
    extractor = DataExtractor(metadata_path=metadata_paths, record_path=extraction_path)
    representation = repr(extractor)
    assert re.search(r"^DataExtractor\(.*\)$", representation, re.DOTALL)
    assert f"record_path={extraction_path}" in representation
    assert f"metadata_path={metadata_paths}" in representation
    assert f"dynamic_record_identifiers={extractor.dynamic_record_identifiers}" in representation
    assert f"dynamic_metadata_identifiers={extractor.dynamic_metadata_identifiers}" in representation


def test_generate_record_id_basic():
    """Verifies that generate record ID produces a basic hash with two underscore delimited pieces."""
    record = {"id": 1, "title": "Test Paper"}
    record_id = DataExtractor._generate_record_id(record, 0)

    # The hash should always be a string
    assert isinstance(record_id, str)

    parts = record_id.split("_")

    # The hash should have two basic parts (hash and index)
    assert len(parts) == 2
    hash, index = parts[0], parts[1]

    # the first portion should be a 16 digit alphanumeric hash
    assert len(hash) == 16 and re.match(r"[a-zA-Z0-9]{16}", hash) is not None

    # The index should match the second argument to `_generate_record_id`
    assert index == "0"


def test_generate_record_id_stable_hash():
    """Verifies that two equal dictionaries, regardless of order, should always produce the same hash."""
    record1 = {"id": 1, "title": "Test"}
    record2 = {"title": "Test", "id": 1}
    record3 = {"title": "Test B", "id": 1}

    id1 = DataExtractor._generate_record_id(record1, 0)
    id2 = DataExtractor._generate_record_id(record2, 0)
    id3 = DataExtractor._generate_record_id(record3, 0)

    assert id1 == id2  # should be equal regardless of order
    assert id1 != id3 and id2 != id3  # shouldn't be equal - a value differs


def test_generate_record_id_excludes_internal_fields():
    """Verifies that private record metadata are excluded when calculating the hash of a record.."""
    record1 = {"id": 1, "title": "Test", "_internal": "value1"}
    record2 = {"id": 1, "title": "Test", "_internal": "value2"}
    record3 = {"id": 1, "title": "Test", "_different": "value3"}

    # All records should have same hash since internal fields are excluded and all other fields are equal
    id1 = DataExtractor._generate_record_id(record1, 0)
    id2 = DataExtractor._generate_record_id(record2, 0)
    id3 = DataExtractor._generate_record_id(record3, 0)

    assert id1 == id2 == id3


def test_generate_record_id_non_serializable_fallback(monkeypatch):
    """Verifies that hash creation fails due to non-serializable content falls back to `record_id=f'idx_{index}'`."""
    monkeypatch.setattr(json, "dumps", raise_error(TypeError))
    record = {"a": 1, "b": 2, "c": 3}
    index = 5
    record_id = DataExtractor._generate_record_id(record, index)
    expected = f"idx_{index}"

    assert record_id == expected


def test_generate_record_id_empty_record():
    """Verifies that ID generation doesn't fail in the calculation of record hashes for empty dictionaries."""
    record: dict = {}
    index = 0
    record_id = DataExtractor._generate_record_id(record, index)

    assert record_id.endswith(f"_{index}") and len(record_id.split("_")[0]) == 16


def test_strip_annotations():
    """Verifies the functionality of `strip_annotations` with different inputs.

    The core logic is delegated to `filter_records`

    """
    record_one = {
        "title": "A title",
        "author": "Anonymous",
        "_extraction_index": 0,
        "_record_id": "abcdefghijklmpqrs_0",
    }
    record_two = {
        "title": "Another title",
        "author": "Unknown",
        "_extraction_index": 1,
        "_record_id": "'srqpmlkjihgfedcba'_1",
    }

    stripped_record_one = {"title": "A title", "author": "Anonymous"}
    stripped_record_two = {"title": "Another title", "author": "Unknown"}

    record_list = [record_one, record_two]
    stripped_record_list = [stripped_record_one, stripped_record_two]

    assert DataExtractor.strip_annotations(record_one) == stripped_record_one
    assert DataExtractor.strip_annotations(record_two) == stripped_record_two
    assert DataExtractor.strip_annotations(record_list) == stripped_record_list

    # When an annotation is not available, return None instead to continue processing
    assert DataExtractor.strip_annotations(None) is None

    # `None` should ideally be handled and accounted for to ensure that a valid `RecordList` is returned.
    assert DataExtractor.strip_annotations(record_list + [None]) == stripped_record_list + [{}]  # type: ignore


def test_strip_annotations_invalid_type():
    """Verifies the functionality of `strip_annotations` with different inputs.

    The core logic is delegated to `filter_records`

    """
    invalid_record = "an invalid record"
    invalid_record_error = (
        f"Expected a dict or list of dicts to strip metadata annotations from, but received type {type(invalid_record)}"
    )
    with pytest.raises(
        TypeError,
        match=invalid_record_error,
    ):
        _ = DataExtractor.strip_annotations(invalid_record)  # type: ignore

    invalid_record_list = ["an invalid record"]
    invalid_record_list_error = (
        f"Expected a dictionary record to filter key prefixes from, but received type {type(invalid_record)}"
    )
    with pytest.raises(TypeError, match=invalid_record_list_error):
        _ = DataExtractor.strip_annotations(invalid_record_list)  # type: ignore


def test_extractor_updates(extractor_manual_paths):
    """Verifies that updates to the DataExtractor class account for passed keywords, ignoring unspecified keys."""
    copied_extractor = copy.deepcopy(extractor_manual_paths)
    updated_extractor = DataExtractor.update(extractor_manual_paths, record_path=None)
    original_attribute_dict = extractor_manual_paths.__dict__
    assert copied_extractor.__dict__ == original_attribute_dict
    assert all(
        value == original_attribute_dict[attribute]
        for attribute, value in updated_extractor.__dict__.items()
        if attribute != "record_path"
    )
    assert extractor_manual_paths.record_path != updated_extractor.record_path


def test_base_extractor_updates(extractor_manual_paths):
    """Verifies that updates to the BaseDataExtractor account for passed keywords, ignoring undefined attributes."""
    base_extractor = BaseDataExtractor.update(
        extractor_manual_paths, metadata_path=None
    )  # should retain only native fields
    assert extractor_manual_paths.record_path is base_extractor.record_path
    assert extractor_manual_paths.metadata_path != base_extractor.metadata_path

    updated_extractor = DataExtractor.update(base_extractor)

    # assigned the default values when not specified
    assert updated_extractor.dynamic_metadata_identifiers is DataExtractor.DEFAULT_DYNAMIC_METADATA_IDENTIFIERS
    assert updated_extractor.dynamic_record_identifiers is DataExtractor.DEFAULT_DYNAMIC_RECORD_IDENTIFIERS
    assert updated_extractor.annotate_records is False


@pytest.mark.parametrize("extractor_class", (BaseDataExtractor, DataExtractor))
def test_invalid_data_extractor_update(extractor_class):
    """Verifies that a TypeError is raised when encountering a non-extractor subclass."""
    invalid_extractor = "not a data extractor"
    err = (
        "Expected a BaseDataExtractor or subclass to perform parameter updates. Received type "
        f"{type(invalid_extractor)}"
    )
    with pytest.raises(TypeError, match=err):
        _ = extractor_class.update(invalid_extractor)  # type: ignore
