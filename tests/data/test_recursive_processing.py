from scholar_flux.data import RecursiveDataProcessor


def test_recursive_processor(sample_json, mock_api_parsed_json_records):
    """
    Verifies that the recursive data processor correctly filters keys as needed a custom KeyFilter
    and ensures that the processed data, when flattened, returns the expected, flattened records.
    """
    processor = RecursiveDataProcessor(sample_json)
    assert isinstance(processor.json_data, list)
    processed = processor.process_page()
    assert isinstance(processed, list)
    assert all(isinstance(d, dict) for d in processed)
    discovered_keys = processor.discover_keys()
    filtered_keys_by_prefix = processor.filter_keys(prefix="address")
    filtered_keys_by_length = processor.filter_keys(min_length=3)
    filtered_keys_by_substring = processor.filter_keys(substring="state")

    flattened_process = (
        [processor.recursive_processor.process_and_flatten(data) for data in processor.json_data]
        if processor.json_data
        else None
    )
    assert flattened_process is not None and len(flattened_process) == 1
    processed_records = processor.process_page()

    assert discovered_keys
    assert filtered_keys_by_prefix
    assert filtered_keys_by_length
    assert filtered_keys_by_substring
    assert len(processed_records) == 1

    processed_records2 = processor.process_page(mock_api_parsed_json_records)
    assert processed_records2
    discovered_keys2 = processor.discover_keys()
    assert discovered_keys2 and discovered_keys != discovered_keys2
