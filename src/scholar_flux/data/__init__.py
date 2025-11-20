# /data
"""The scholar_flux.data module contains components that process the raw responses, enabling end users to interact with
structured and formatted data after the scholar_flux SearchApi receives a valid response. This module, after receiving
the response performs the following steps: Response Parsing --> Record Extraction --> Record Processing.

Stages:
    **Response Parsing**:
        Extracts XML, JSON, or YAML-based responses from the response content. The response content is automatically
        parsed  depending on the content type listed in the response header. This can be further customized to enable
        the processing of other content types in a streamlined way.
    **Record Extraction**:
        This phase involves the extraction of metadata and records from parsed API responses.
        The process can be performed in two ways:

        1. The paths of records are listed ahead of time, indicating individual metadata fields and where the
        list of JSON records can be found if available.

        2. The metadata and records can be identified automatically using heuristics instead.
        Records are generally identified as a list of dictionaries where each list entry is a separate record that
        may contain similar sets of fields.

        The record extraction phase then returns the records and metadata as a tuple in that order.
    **Record Processing**:
        The final stage of the response processing pipeline where the records are flattened, processed, and filtered.
        This stage often involves flattening each individual record element into the path where the data can be found
        and the value found at the end of the nested path. This stage also allows individual records to be filtered
        by key - paths can be retained or removed based on whether it contains a regex pattern or fixed string.
        The results are then returned as a list of flattened dictionaries, depending on the Processor chosen.

        Processors:

            - DataProcessor:
                Requires the end-user to manually specify the paths where data should be extracted in each record as
                well as a key that should correspond to the extracted value in each record.
            - NormalizingDataProcessor:
                Inherits from the DataProcessor and implements flattening prior to extracting the required parameters
                needed to normalize field maps. Useful in later steps of processing where fields may or may not already
                be normalized.
            - PassThroughDataProcessor:
                The simplest implementation of the DataProcessor that does not automatically flatten records.
                This implementation still allows for the filtering of records similarly to the DataProcessor.
            - RecursiveDataProcessor:
                A recursive implementation that dynamically discovers terminal paths and flattens them, using the path
                as the key for the extracted value.
            - PathDataProcessor:
                A custom implementation of a data processor that uses trie-based processing to
                efficiently process and filter a flattened and processed list of JSON records. This implementation is
                universally applicable to JSON-formatted data and allows for further customization in the
                specifics of how records (and JSON dictionaries) are processed.

    Each element in the processing pipeline is designed to be extensible and can be further customized and used in
    the retrieval of response data using base/ABC implementations:

        - BaseDataParser
        - BaseDataExtractor
        - ABCDataProcessor

    The resulting classes can then be used as such:
        >>> from scholar_flux.data import DataParser, DataExtractor, PathDataProcessor
        >>> from scholar_flux.api import SearchCoordinator
        >>> search_coordinator = SearchCoordinator(query='Pharmaceuticals', parser=DataParser(), extractor=DataExtractor(), processor=PathDataProcessor())
        >>> response = search_coordinator.search(page = 1)
        >>> response
        # OUTPUT: <ProcessedResponse(len=50, cache_key='plos_Pharmaceuticals_1_50', metadata=...")>
        ### Elements from each stage of the process can be accessed:
        >>> response.parsed_response # a JSON formatted response after parsing the response with the search_coordinator.parser
        >>> response.extracted_records # list of dictionaries containing records extracted using the search_coordinator.extractor
        >>> response.data # the list of dictionaries processed from the search_coordinator.processor

"""

from scholar_flux.data.base_extractor import BaseDataExtractor
from scholar_flux.data.data_extractor import DataExtractor
from scholar_flux.data.base_parser import BaseDataParser
from scholar_flux.data.data_parser import DataParser
from scholar_flux.data.abc_processor import ABCDataProcessor
from scholar_flux.data.data_processor import DataProcessor
from scholar_flux.data.normalizing_data_processor import NormalizingDataProcessor
from scholar_flux.data.pass_through_data_processor import PassThroughDataProcessor
from scholar_flux.data.recursive_data_processor import RecursiveDataProcessor
from scholar_flux.data.path_data_processor import PathDataProcessor
from scholar_flux.utils.json_processing_utils import RecursiveJsonProcessor

__all__ = [
    "BaseDataExtractor",
    "DataExtractor",
    "BaseDataParser",
    "DataParser",
    "ABCDataProcessor",
    "DataProcessor",
    "NormalizingDataProcessor",
    "PassThroughDataProcessor",
    "RecursiveDataProcessor",
    "PathDataProcessor",
    "RecursiveJsonProcessor",
]
