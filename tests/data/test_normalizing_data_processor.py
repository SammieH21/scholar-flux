from scholar_flux.data import NormalizingDataProcessor
from scholar_flux.exceptions import DataProcessingException
import pytest


def test_normalizing_processor_basic():
    """Test basic flattening and extraction."""
    data: list[dict] = [
        {"id": 1, "school": {"department": "Math"}},
        {"id": 2, "school": {"department": "History"}},
    ]

    processor = NormalizingDataProcessor(record_keys=[["id"], ["school", "department"]], value_delimiter=None)

    result = processor.process_page(data)

    assert len(result) == 2
    assert result[0]["id"] == 1
    assert result[0]["school.department"] == "Math"
    assert result[1]["id"] == 2
    assert result[1]["school.department"] == "History"


@pytest.mark.parametrize(
    ("path", "expected"),
    (
        (["a", "b", 1, 3], "a.b"),
        (["a", "b", "1", 3], "a.b.1"),
        ("x.y.z", "x.y.z"),
        ([1, 2, 3], "1.2.3"),
        ([1, "bc", "cd", "de"], "bc.cd.de"),
    ),
)
def test_normalized_key_generation(path, expected):
    """Tests normalization rules and edge-cases when preparing keys for record normalization and value retrieval.

    Non-string numeric values should be filtered from the path unless their removal results in an empty path-string.

    """
    key = NormalizingDataProcessor._as_normalized_key(path=path)
    assert key == expected


def test_flattening_empty_dict(caplog):
    """Verifies that attempting to flatten a falsy value returns an empty dictionary."""
    record_keys: list[str] = ["a.b.c", "d.e.f"]
    processor = NormalizingDataProcessor(record_keys)

    value: None | list | dict
    for value in ({}, None, []):
        assert processor.process_record(value) == dict()  # type: ignore
        assert "Record is empty: skipping..." in caplog.text
        caplog.clear()


def test_processing_incorrect_values(caplog):
    """Verifies that attempting to flatten a falsy value returns an empty dictionary."""
    record_keys: list[str] = ["a.b.c", "d.e.f"]
    processor = NormalizingDataProcessor(record_keys)
    with pytest.raises(DataProcessingException) as excinfo:
        _ = processor(12)  # type: ignore

    # integer is not iterable - can't loop over an integer
    assert "An unexpected error occurred during data processing" in str(excinfo.value)


def test_processing_without_record_keys(caplog):
    """Verifies that attempting to flatten a falsy value returns an empty dictionary."""
    record_keys: list[str] = []
    processor = NormalizingDataProcessor(record_keys=record_keys)
    result = processor.process_record({"a": "b", "c": "d"})  # type: ignore
    assert result == {}  # if record keys are not provided, the resulting dictionary will always be empty


def test_normalizing_processor_unnested():
    """Tests whether the processor functions as intended with a simple structure"""
    data: list[dict] = [{"key1": "value1", "key2": 2, "key3": True}]
    processor = NormalizingDataProcessor(record_keys=["key1", "key2", "key3"], value_delimiter="; ")

    results = processor(data)
    assert results == data
    assert results == processor(results)


def test_normalizing_processor_simple_nested():
    """Tests whether the processor also handles nested structures"""
    data: list[dict] = [{"a": {"key1": "value1"}, "b": {"key2": 2}, "c": {"d": {"key3": True}}}]
    keys = ["a.key1", "b.key2", "c.d.key3"]
    flattened_dict = dict(zip(keys, ["value1", 2, True]))
    processor = NormalizingDataProcessor(record_keys=keys, value_delimiter="; ")

    results = processor(data)
    assert results == [flattened_dict]
    assert results == processor(results)


def test_normalizing_processor_string_paths():
    """Test using string paths instead of list paths."""
    data: list[dict] = [
        {"id": 1, "school": {"department": "Math"}},
    ]

    processor = NormalizingDataProcessor(record_keys=["id", "school.department"], value_delimiter=None)

    result = processor.process_page(data)

    assert result[0]["id"] == 1
    assert result[0]["school.department"] == "Math"


def test_unsuccessfully_extracted_keys(caplog):
    """Verifies that, when `process_and_flatten` returns an empty list, an dictionary with record keys is returned."""
    example_record = {"a": 2, "b": {"c": 3}}
    record_keys: list[str] = ["d.e.f"]
    normalizing_data_processor = NormalizingDataProcessor(record_keys=record_keys)
    assert normalizing_data_processor.process_record(example_record) == {key: None for key in record_keys}
    assert "Flattening returned no results" in caplog.text


def test_normalizing_processor_idempotent():
    """Test that already-flattened records pass through correctly."""
    flattened_data: list[dict] = [
        {"id": 1, "school.department": "Math"},
    ]

    processor = NormalizingDataProcessor(record_keys=["id", "school.department"], value_delimiter=None)

    result = processor.process_page(flattened_data)
    assert result[0]["id"] == 1
    assert result[0]["school.department"] == "Math"

    # Process again - should be identical
    result2 = processor.process_page(result)
    assert result == result2


def test_normalizing_processor_with_renaming():
    """Test field renaming via dict-style record_keys."""
    data: list[dict] = [
        {"id": 1, "school": {"department": "Math"}},
    ]

    processor = NormalizingDataProcessor(
        record_keys={"record_id": ["id"], "dept": ["school", "department"]}, value_delimiter=None
    )

    result = processor.process_page(data)
    assert result[0]["record_id"] == 1
    assert result[0]["dept"] == "Math"


def test_normalizing_processor_missing_keys():
    """Test handling of missing keys with None values."""
    data: list[dict] = [
        {"id": 1, "school": {"department": "Math"}},
        {"id": 2, "school": {"organization": "Research Lab"}},
    ]

    processor = NormalizingDataProcessor(
        record_keys=[["id"], ["school", "department"], ["school", "organization"]], value_delimiter=None
    )

    result = processor.process_page(data)

    assert result[0]["school.department"] == "Math"
    assert result[0]["school.organization"] is None
    assert result[1]["school.department"] is None
    assert result[1]["school.organization"] == "Research Lab"


def test_normalizing_processor_with_list_indices2():
    """Test extraction with explicit list indices."""
    data: list[dict] = [{"Ids": [{"id": 1}], "authors": [{"name": "Alice"}, {"name": "Bob"}]}]

    processor = NormalizingDataProcessor(
        record_keys={"id": ["Ids", 0, "id"], "first_author": ["authors", "name"]}, value_delimiter=None
    )

    result = processor.process_page(data)

    assert result[0]["id"] == 1
    assert result[0]["first_author"][0] == "Alice"


def test_normalizing_processor_with_list_indices3():
    """Test extraction with explicit list indices in paths."""
    data: list[dict] = [
        {"id": 1, "authors": [{"name": "Alice", "affiliation": "MIT"}, {"name": "Bob", "affiliation": "Stanford"}]}
    ]

    # Using list paths with integer indices
    processor = NormalizingDataProcessor(
        record_keys={
            "id": ["id"],
            "authors": ["authors", 0, "name"],
            "first_affiliation": ["authors", 0, "affiliation"],
        },
        value_delimiter=None,
        traverse_lists=False,
    )

    result = processor.process_page(data)

    assert result[0]["id"] == 1
    assert result[0]["authors"] == "Alice"
    assert result[0]["first_affiliation"] == "MIT"


def test_normalizing_processor_nested_lists():
    """Test handling of nested list structures."""
    data: list[dict] = [
        {"study": {"participants": [{"id": 1, "measurements": [10, 20, 30]}, {"id": 2, "measurements": [15, 25, 35]}]}}
    ]

    processor = NormalizingDataProcessor(
        record_keys={
            "first_participant_id": ["study", "participants", 0, "id"],
            "first_measurements": ["study", "participants", 0, "measurements"],
        }
    )

    result = processor.process_page(data)

    assert result[0]["first_participant_id"] == 1
    # measurements should be joined with delimiter or kept as list
    assert "first_measurements" in result[0]


def test_normalizing_processor_deeply_nested():
    """Test deeply nested structures (4+ levels)."""
    data: list[dict] = [{"organization": {"department": {"team": {"lead": {"name": "Dr. Smith"}}}}}]

    processor = NormalizingDataProcessor(
        record_keys={"team_lead": ["organization", "department", "team", "lead", "name"]}, value_delimiter=None
    )

    result = processor.process_page(data)

    assert result[0]["team_lead"] == "Dr. Smith"


def test_normalizing_processor_empty_lists():
    """Test handling of empty list fields."""
    data: list[dict] = [
        {"id": 1, "authors": []},
        {"id": 2, "authors": [{"name": "Alice"}]},
    ]

    record_keys: list = ["id", ["authors", "name"]]
    processor = NormalizingDataProcessor(record_keys=record_keys, value_delimiter=None)

    result = processor.process_page(data)

    assert result[0]["id"] == 1
    assert result[0]["authors.name"] is None or result[0]["authors.name"] == []
    assert result[1]["authors.name"] == "Alice"


def test_normalizing_processor_with_basic_dictionary_record_path():
    """Verifies that dictionary keys found in the `record_keys variable show in the result when available."""
    data: list[dict] = [{"user": {"profile": {"name": "Alice"}}, "admin": {"profile": {"name": "Bob"}}}]

    processor = NormalizingDataProcessor(
        record_keys={"user_name": ["user", "profile", "name"], "admin_name": ["admin", "profile", "name"]},
        value_delimiter=None,
    )

    result = processor.process_page(data)

    assert "user_name" in result[0]
    assert "admin_name" in result[0]


def test_normalizing_processor_mixed_types():
    """Test handling of mixed data types in values."""
    data: list[dict] = [
        {"id": 1, "metadata": {"counts": 42, "active": True, "score": 3.14, "tags": ["python", "json"]}}
    ]

    processor = NormalizingDataProcessor(
        record_keys={
            "id": ["id"],
            "count": ["metadata", "counts"],
            "active": ["metadata", "active"],
            "score": ["metadata", "score"],
            "tags": ["metadata", "tags"],
        },
        value_delimiter=None,
    )

    result = processor.process_page(data)

    assert result[0]["id"] == 1
    assert result[0]["count"] == 42
    assert result[0]["active"] is True
    assert result[0]["score"] == 3.14
    assert result[0]["tags"] == ["python", "json"]  # List joined with delimiter


def test_normalizing_processor_mixed_types_joined():
    """Test handling of mixed data types in values with a string delimiter."""
    data: list[dict] = [
        {"id": 1, "metadata": {"counts": 42, "active": True, "score": 3.14, "tags": ["python", "json"]}}
    ]

    processor = NormalizingDataProcessor(
        record_keys={
            "id": ["id"],
            "count": ["metadata", "counts"],
            "active": ["metadata", "active"],
            "score": ["metadata", "score"],
            "tags": ["metadata", "tags"],
        },
        value_delimiter="; ",
        traverse_lists=False,
    )

    result = processor.process_page(data)

    assert result[0]["id"] == 1
    assert result[0]["count"] == 42
    assert result[0]["active"] is True
    assert result[0]["score"] == 3.14
    assert result[0]["tags"] == "python; json"  # List joined with delimiter
