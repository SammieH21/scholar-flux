from scholar_flux.data import PathDataProcessor


def test_path_data_processor(sample_json):
    """Verifies that the recursive data processor correctly filters keys as required.

    The data processor should use a custom KeyFilter to ensure that the processed data, when flattened, will return the
    expected, flattened set of records.

    """
    processor = PathDataProcessor(sample_json)
    assert isinstance(processor.json_data, list)
    processed = processor.process_page()
    assert isinstance(processed, list)
    assert all(isinstance(d, dict) for d in processed)
    assert processor.cached
    discovered_keys = processor.discover_keys()
    assert isinstance(discovered_keys, dict) and all(isinstance(key, (str)) for key in discovered_keys)

    processed_records = processor.process_page()

    assert isinstance(processed_records, list) and all(
        isinstance(record, dict) and all(isinstance(key, str) for key in record) for record in processed_records
    )

    records_kept = processor.process_page(keep_keys=["n.me"], regex=True)
    assert records_kept == processed_records

    records_removed = processor.process_page(ignore_keys=["name"])
    assert records_kept != records_removed
