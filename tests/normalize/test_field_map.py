from scholar_flux.api.normalization import BaseFieldMap, NormalizingFieldMap, AcademicFieldMap
from scholar_flux.data import NormalizingDataProcessor
from scholar_flux.exceptions import RecordNormalizationException, DataProcessingException
from tests.testing_utilities import raise_error
import pytest
import re
from typing import Any
from textwrap import dedent


@pytest.fixture
def mock_simple_record_dictionary() -> dict[str, Any]:
    """A simple, mock record dictionary used to verify the normalization of academic API fields."""
    mock_simple_record_dictionary = {
        "provider_name": "scholar_flux_mocks",
        "mock_title": "Heisenberg Uncertainty Principle in Motion",
        "mock_doi": "https://doi.org/12.3456/mock.2025.11.10",
        "mock_abstract": dedent(
            """Abstract: To paraphrase, how well the exact location of a quantum variable can be
                                measured at any moment in time is inversely proportional to our ability to measure its
                                velocity (and vice versa).

                                — Werner Heisenberg 1927
                                """
        ),
    }
    return mock_simple_record_dictionary


@pytest.fixture
def mock_complex_record_dictionary(mock_simple_record_dictionary: dict[str, Any]) -> dict[str, Any]:
    """A somewhat complex, mock record dictionary used to verify the normalization of academic API fields"""
    (paraphrased_abstract_text, attribution) = mock_simple_record_dictionary["mock_abstract"].split("—")
    attribution = f"—{attribution}"
    mock_complex_record_dictionary = {
        "mock_title": {"name": mock_simple_record_dictionary["mock_title"]},
        "mock_metadata": {"doi": mock_simple_record_dictionary["mock_doi"]},
        "mock_abstract": [paraphrased_abstract_text, attribution],
    }
    return mock_complex_record_dictionary


def test_provider_name_overrides():
    """Tests the specification of defaults based on provided parameters."""
    default_provider_name = "default_provider_name"
    record_provider_name = "record_provider_name"
    base_mapping = BaseFieldMap(provider_name=default_provider_name)
    default_record_fields = base_mapping._add_defaults({"provider_name": record_provider_name})
    default_record_fields_two = base_mapping._add_defaults({})

    assert all(field in default_record_fields for field in base_mapping.fields)
    assert default_record_fields["provider_name"] == record_provider_name

    assert all(
        field in default_record_fields_two and value is None
        for field, value in default_record_fields_two.items()
        if field != "provider_name"
    )

    assert default_record_fields_two["provider_name"] == default_provider_name


def test_base_field_map_representation():
    """Tests whether attempts at normalization with missing records/values show the absence of records on return."""
    base_mapping = BaseFieldMap(
        provider_name="example_provider",
        api_specific_fields={"mapped_name_one": "field_one", "mapped_name_two": "field_two"},
    )

    representation = base_mapping.structure()
    assert repr(base_mapping) == representation
    assert "BaseFieldMap" in representation
    assert f"{base_mapping.api_specific_fields}" in representation


def test_missing_record_base_field_map_edge_cases():
    """Tests whether attempts at normalization with missing records/values show the absence of records on return."""
    base_mapping = BaseFieldMap(provider_name=None)  # type: ignore
    assert base_mapping([]) == base_mapping(None) == []
    assert base_mapping.apply([]) == []
    assert base_mapping.apply({}) == {"provider_name": None}


def test_field_map_apply_equivalence(mock_simple_record_dictionary):
    """Tests whether attempts at normalization with missing records/values show the absence of records on return."""
    base_mapping = BaseFieldMap(provider_name=None)  # type: ignore
    assert base_mapping([]) == base_mapping(None) == []
    assert base_mapping.apply(mock_simple_record_dictionary) == base_mapping.normalize_record(
        mock_simple_record_dictionary
    )
    assert base_mapping.apply([mock_simple_record_dictionary]) == base_mapping.normalize_records(
        mock_simple_record_dictionary
    )


def test_multiple_record_base_field_map_normalization(mock_simple_record_dictionary, mock_complex_record_dictionary):
    """Tests that record normalization returns a consistent result for both single and multi-record normalization."""
    api_specific_fields: dict = dict(title="mock_title", doi="mock_doi", abstract="mock_abstract")
    base_mapping = BaseFieldMap(provider_name=None, api_specific_fields=api_specific_fields)  # type: ignore
    simulated_records = [mock_simple_record_dictionary, mock_complex_record_dictionary]
    normalized_records = base_mapping.normalize_records(
        simulated_records
    )  # calls .normalized_records() using *args + **kwargs
    assert len(normalized_records) == len(simulated_records)

    # records should process consistently across different types
    assert normalized_records[0] == base_mapping.normalize_record(simulated_records[0])
    assert normalized_records[1] == base_mapping.normalize_record(simulated_records[1])


def test_record_dict_simplification(mock_simple_record_dictionary):
    """Tests that a record can be normalized as intended by applying an AcademicFieldMap."""
    api_specific_fields: dict = dict(title="mock_title", doi="mock_doi", abstract="mock_abstract")
    base_mapping = BaseFieldMap(provider_name=None, api_specific_fields=api_specific_fields)  # type: ignore
    custom_mapping = NormalizingFieldMap(provider_name="", api_specific_fields=api_specific_fields)  # type: ignore
    mapping = AcademicFieldMap(**api_specific_fields)

    assert base_mapping.provider_name == ""
    base_normalized_record = base_mapping.normalize_record(mock_simple_record_dictionary)
    custom_normalized_record = custom_mapping.normalize_record(mock_simple_record_dictionary)
    normalized_record = mapping.normalize_record(mock_simple_record_dictionary)
    expected_nonmissing_fields = {"provider_name", "title", "doi", "abstract"}
    mapped_record_fields: dict = {field: value for field, value in normalized_record.items() if value is not None}

    assert expected_nonmissing_fields == mapped_record_fields.keys()
    assert mapped_record_fields["provider_name"] == "scholar_flux_mocks"
    assert base_normalized_record["provider_name"] == "scholar_flux_mocks"

    assert mock_simple_record_dictionary["provider_name"] == normalized_record["provider_name"]
    assert mock_simple_record_dictionary[mapping.title] == normalized_record["title"]
    assert mock_simple_record_dictionary[mapping.abstract] == normalized_record["abstract"]
    assert mock_simple_record_dictionary[mapping.doi] == normalized_record["doi"]

    assert custom_normalized_record == {field: normalized_record.get(field) for field in custom_normalized_record}

    for field, record_key in mapping.fields.items():
        if record_key is None:
            assert normalized_record[field] is None

    assert mapping.normalize_records([mock_simple_record_dictionary]) == [normalized_record]


def test_base_field_map_type_exception(caplog):
    """Verifies that DataProcessingExceptions are handled when the field_map applies multi-record normalization."""
    mapping = BaseFieldMap(provider_name="provider")

    err = f"Expected a dictionary-typed record, but received a value of type '{type(None)}'."
    with pytest.raises(TypeError) as excinfo:
        _ = mapping([None])

    assert err in str(excinfo.value)


def test_academic_field_map_exception_handling(mock_simple_record_dictionary, monkeypatch, caplog):
    """Verifies that DataProcessingExceptions are handled when the field_map applies multi-record normalization."""
    err = "Simulated Record Processing Exception"
    monkeypatch.setattr(
        NormalizingDataProcessor,
        "process_record",
        raise_error(DataProcessingException, err),
    )
    mapping = AcademicFieldMap()
    with pytest.raises(RecordNormalizationException) as excinfo:
        _ = mapping.normalize_records(mock_simple_record_dictionary)

    message = f"Encountered an error during the data processing step of record normalization:.*{err}"
    assert re.search(message, str(excinfo.value))
    assert re.search(message, caplog.text)


def test_complex_record_dict_simplification(mock_simple_record_dictionary, mock_complex_record_dictionary):
    """Tests that a record with a complex structure can be normalized as intended by applying an AcademicFieldMap."""
    mapping = AcademicFieldMap(title="mock_title", doi="mock_doi", abstract="mock_abstract")

    normalized_record = mapping.normalize_record(mock_simple_record_dictionary)

    complex_mapping = AcademicFieldMap(
        provider_name="scholar_flux_mocks", title="mock_title.name", doi="mock_metadata.doi", abstract="mock_abstract"
    )
    processor = complex_mapping.processor
    processor.value_delimiter = ""  # join on an empty string (basic string concatenation)
    complex_mapping.processor = processor

    complex_normalized_record = complex_mapping.normalize_record(mock_complex_record_dictionary)
    assert complex_normalized_record == normalized_record


def test_caching(mock_simple_record_dictionary: dict[str, Any]):
    """Tests whether caching recomputes only when needed and lazily caches the configuration of the AcademicFieldMap."""
    mapping = AcademicFieldMap(title="mock_title", doi="mock_doi", abstract="mock_abstract")
    # none of these conditions should generate inequalities among `field` and the `_cached_fields` property
    assert mapping.fields == mapping._cached_fields
    processor = mapping.processor
    _ = mapping.normalize_record(mock_simple_record_dictionary)
    assert mapping.fields == mapping._cached_fields
    mapping.provider_name = mapping.provider_name
    assert mapping.fields == mapping._cached_fields
    assert processor is mapping.processor

    # the lazily cached field dictionary should now be unequal
    mapping.provider_name = "new_provider_name"
    assert mapping.fields != mapping._cached_fields
    # calling `mapping.processor` property will dynamically update the keys only when needed
    assert processor.record_keys != mapping.processor.record_keys
    processor = mapping.processor

    # now the cache should be recalculated and the field values identical
    assert processor is mapping.processor and mapping.fields == mapping._cached_fields


def test_simple_empty_record_normalization():
    """Tests response normalization behavior when `None` is provided instead of one or more records."""
    mapping = AcademicFieldMap(provider_name="Missing Provider Name")
    assert mapping.normalize_record(None) == {}  # type: ignore
    assert mapping.normalize_records(None) == []  # type: ignore


def test_incorrect_record_normalization(caplog):
    """Tests response normalization behavior when `None` is provided instead of one or more records."""
    mapping = AcademicFieldMap(provider_name="Missing Provider Name")
    invalid_record_list = {1, 2, 3}
    with pytest.raises(RecordNormalizationException) as excinfo:
        _ = mapping.normalize_records(invalid_record_list)  # type: ignore
    message = f"Expected the record list to be of type `list`, but received a variable of {type(invalid_record_list)}"
    assert message in caplog.text
    assert message in str(excinfo.value)


def test_incorrect_field_map_provider_type():
    """Verifies that the BaseFieldMap raises an error when the provider type is of the incorrect type"""
    invalid_provider_name = ["not a valid provider"]
    with pytest.raises(ValueError) as excinfo:
        _ = BaseFieldMap(provider_name=invalid_provider_name)  # type: ignore

    message = f"Incorrect type received for the provider_name. Expected None or string, received {type(invalid_provider_name)}"
    assert message in str(excinfo.value)


def test_incorrect_value_types(caplog):
    mock_field_map = AcademicFieldMap()

    invalid_processor_type = "Not a processor"
    with pytest.raises(RecordNormalizationException) as excinfo:
        mock_field_map.processor = invalid_processor_type  # type: ignore
    message = f"Expected a DataProcessor, but received a variable of {type(invalid_processor_type)}"
    assert message in caplog.text
    assert message in str(excinfo.value)

    invalid_record_type = 0
    with pytest.raises(RecordNormalizationException) as excinfo:
        _ = mock_field_map.normalize_record(record=0)  # type: ignore
    message = f"Expected record to be of type `dict`, but received a variable of {type(invalid_record_type)}"
    assert message in caplog.text
    assert message in str(excinfo.value)
