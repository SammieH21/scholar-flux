from typing import Dict, List, Any, Optional, Union, Tuple
from scholar_flux.exceptions import DataExtractionException
from scholar_flux.utils import (get_nested_data, try_int,
                                try_dict, as_list_1d
                               )

import logging
logger = logging.getLogger(__name__)

class DataExtractor:
    DEFAULT_DYNAMIC_RECORD_IDENTIFIERS = ('title','doi', 'abstract')
    def __init__(self, record_path: Optional[List[str | int]] = None,
                metadata_path_overrides: Optional[List[List[str | int]] | Dict[str, List[str | int]]] = None,
                 dynamic_record_identifiers: Optional[List | Tuple] = None):
        """
        Initialize the DataExtractor with optional path overrides for metadata and records.
        The data extractor provides two ways to identify metadata paths and record paths:

            1) manual identification: If record path or metadata_path_overrides are specified,
               then the data extractor will attempt to retrieve the metadata and records at the
               provided paths. Note that, as metadata_paths can be associated with multiple keys,
               starting from the outside dictionary, we may have to specify a dictionary containing
               keys denoting metadata variables and their paths as a list of values indicating how to
               retrieve the value. The path can also be given by a list of lists describing how to
               retrieve the last element.
            2) Dynamic identification: Uses heuristics to determine records from metadata. records
               will nearly always be defined by a list containing only dictionaries as its elements
               while the metadata will generally contain a variety of elements, some nested and others
               as integers, strings, etc. In some cases where its harder to determine, we can use
               dynamic_record_identifiers to determine whether a list containing a single nested dictionary
               is a record or metadata. For scientific purposes, its keys may contain 'abstract', 'title', 'doi',
               etc. This can be defined manually by the usersif the defaults are not reliable for a given API.

        Args:
            record_path (Optional[List[str]]): Custom path to find records in the parsed data. Contains a list of strings and
                                               rarely integers indexes indicating how to recursively find the list of records
            metadata_path_overrides (List[List[str]] | Optional[Dict[str, List[str]]]): Identifies the paths in a dictionary
                associated with metadata as opposed to records. This can be a list of paths where each element is a list
                describing how to get to a terminal
            element
            dynamic_record_identifiers (Optional[List[str]]): Helps to identify dictionary keys that only belong to records when
                                                              dealing with a single element that would otherwise be classified
                                                              as metadata.

        """
        self.metadata_path = metadata_path_overrides or {}
        self.record_path = record_path
        self.dynamic_record_identifiers = (dynamic_record_identifiers
                                            if dynamic_record_identifiers is not None
                                            else self.DEFAULT_DYNAMIC_RECORD_IDENTIFIERS
                                           )
        self._validate_inputs(record_path, metadata_path_overrides, dynamic_record_identifiers)

    def _validate_inputs(self,record_path: Optional[List[str | int]] = None,
                         metadata_path_overrides: Optional[List[List[str | int]] | Dict[str, List[str | int]]] = None,
                         dynamic_record_identifiers: Optional[List | Tuple] = None
                        ):
        """
        Method used to validate the inputs provided to the DataExtractor prior to its later use
        In extracting metadata and records
        Args:
            record_path (Optional[List[str | None]]): The path where a list of records are located
            metadata_path_overrides (Optional[List[str | None]]): The list or dictionary of paths where metadata records are located
            dynamic_record_identifiers (Optional[List[str | None]]): Keyword identifier indicating when singular records in a dictionary
                                                                     can be identified as such in contrast to metadata
        Raises:
            DataExtractionException: Indicates an error in the DataExtractor and identifies where the inputs take on an invalid value
        """
        try:
            if record_path is not None:
                if not isinstance(record_path, list):
                    raise TypeError(f"A list is required for a record path. Received: {type(record_path)}")

                if not all(isinstance(path, (str, int)) for path in record_path):
                    raise KeyError(f"At least one path in the provided record path is not an integer or string: {record_path}")
            if metadata_path_overrides is not None:
                if not isinstance(metadata_path_overrides, (list, dict)):
                    raise KeyError(f"the provided metadata_path override is not a list or dictionary: {type(metadata_path_overrides)}")
                if not all(isinstance(path, (str, int, list)) for path in metadata_path_overrides):
                    raise KeyError(f"At least one path in the provided metadata path override is not a list, integer, or string: {metadata_path_overrides}")
            if dynamic_record_identifiers is not None:
                if not isinstance(dynamic_record_identifiers, (list, tuple)):
                    raise KeyError(f"The dynamic record identifiers provided must be a tuple or list. Received: {type(dynamic_record_identifiers)}")
                if not all(isinstance(path, (str)) for path in dynamic_record_identifiers):
                    raise KeyError(f"At least one value in the provided dynamic record identifier is not an integer or string: {dynamic_record_identifiers}")
        except (KeyError, TypeError) as e:
            raise DataExtractionException(f"Error initializing the DataExtractor: At least one of the inputs are invalid. {e}") from e
        return None

    def extract_metadata(self, parsed_page_dict: Dict) -> Dict:
        """
        Extract metadata from the parsed page dictionary.

        Args:
            parsed_page_dict (Dict): The dictionary containing the page data to be parsed.

        Returns:
            Dict: The extracted metadata.
        """
        if not self.metadata_path:
            logger.info("Metadata paths are empty: skipping metadata extraction")
            return {}

        metadata = {}
        try:
            if isinstance(self.metadata_path, list):
                # converts a list into a dictionary to ensure compatibility with the current method
                # as_list_1d ensures that, if the current path is not in a list, it is coerced into a list
                metadata_path = {as_list_1d(path)[-1]: as_list_1d(path) for path in self.metadata_path}
            else:
                ## ensures that all paths are lists and nests the path in a list otherwise
                metadata_path = {key: as_list_1d(path) for key, path in self.metadata_path.items()}

            # attempts to retrieve the path from the
            metadata = {key: try_int(get_nested_data(parsed_page_dict, path)) for key, path in metadata_path.items()}
#           elif isinstance(self.metadata_path, list):
#               metadata = {path[-1]: try_int(get_nested_data(parsed_page_dict, as_list_1d(path)))
#                           for path in self.metadata_path}

            missing_keys = [k for k, v in metadata.items() if v is None]
            if missing_keys:
                logger.warning(f"The following metadata keys are missing or None: {', '.join(missing_keys)}")
        except KeyError as e:
            logger.error(f"Error extracting metadata due to missing key: {e}")
        except Exception as e:
            logger.error(f"An unexpected error occurred during metadata extraction due to the following exception: {e}")
            raise DataExtractionException(f"An unexpected error occurred during metadata extraction due to the following exception: {e}")
        return metadata

    def extract_records(self, parsed_page_dict: Dict) -> Optional[List[Dict[str, Any]]]:
        """
        Extract records from parsed data as a list of dicts.

        Args:
            parsed_page_dict (Dict): The dictionary containing the page data to be parsed.

        Returns:
            Optional[List[Dict]]: A list of records as dictionaries, or None if extraction fails.
        """
        nested_data =  get_nested_data(parsed_page_dict, self.record_path) if self.record_path else None

        if isinstance(nested_data, list):
            return nested_data

        if not nested_data:
            logger.debug(f"No records extracted from path {self.record_path}")
            return None

        logger.debug(f"Expected a list at path {self.record_path}. Instead received {type(nested_data)}")
        return None



    def dynamic_identification(self, parsed_page_dict: Dict) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Dynamically identify and separate metadata from records. This function recursively traverses the
        dictionary and uses a heuristic to determine whether a specific record corresponds to metadata
        or is a list of records: Generally, keys associated with values corresponding to metadata will
        contain only lists of dictionarys On the other hand, nested structures containing metadata
        will be associated with a singular value other a dictionary of keys associated with a
        singular value that is not a list. Using this heuristic, we're able to determine metadata
        from records with a high degree of confidence.

        Args:
            parsed_page_dict (Dict): The dictionary containing the page data and metadata to be extracted.

        Returns:
            Tuple[Dict[str, Any], List[Dict[str, Any]]]: A tuple containing the metadata dictionary and the list of record dictionaries.
        """
        metadata = {}
        records = []

        for key, value in parsed_page_dict.items():
            if isinstance(value, dict):
                sub_metadata, sub_records = self.dynamic_identification(value)
                metadata.update(sub_metadata)
                records.extend(sub_records)
            elif isinstance(value, list):
                if all(isinstance(item, dict) for item in value):
                    if len(value) == 0:
                        logger.debug(f"Element at key: {key} is empty")
                    elif len(value) > 1:  # assuming it's records if it's a list of dicts
                        records.extend(value)
                    else:
                        record = value[0]
                        if all([
                            isinstance(record, dict),
                            any(True for id_key in self.dynamic_record_identifiers
                                if any(id_key in record_key for record_key in record.keys()))
                        ]):
                            records.extend(value)
                            continue
                        sub_metadata, sub_records = self.dynamic_identification(value[0])
                        metadata.update(sub_metadata)
                        records.extend(sub_records)
            else:
                metadata[key] = value

        return metadata, records

    def extract(self, parsed_page: Union[List[Dict],Dict]) -> Tuple[Optional[List[Dict]], Optional[Dict[str, Any]]]:
        """
        Extract both records and metadata from the parsed page dictionary.

        Args:
            parsed_page (List[Dict] | Dict): The dictionary containing the page data and metadata to be extracted.

        Returns:
            Tuple[Optional[List[Dict]], Optional[Dict]]: A tuple containing the list of records and the metadata dictionary.
        """

        if not isinstance(parsed_page, dict):
            parsed_page_dict = try_dict(parsed_page)

            if parsed_page_dict is None:
                raise DataExtractionException(f"Error converting parsed_page_dict of type {parsed_page_dict} to a dictionary")

            parsed_page = parsed_page_dict

        if self.metadata_path or self.record_path:
            records = self.extract_records(parsed_page)
            metadata = self.extract_metadata(parsed_page)
        else:
            metadata, records = self.dynamic_identification(parsed_page)

        return records, metadata


# # Example of using DataExtractor with default paths
# extractor = DataExtractor()
# metadata = extractor.extract(parsed_response)

# # Example of customizing MetadataExtractor for a different data format or structure
# custom_paths = {
#     'totals_path': ['customResponse', 'totalResults'],
#     'displayed_path': ['customResponse', 'resultsDisplayed'],
#     'page_length_path': ['customResponse', 'resultsPerPage']
# }
# custom_extractor = DataExtractor(path_overrides=custom_paths)
# custom_metadata = custom_extractor.extract(custom_parsed_response)
