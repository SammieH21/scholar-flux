from typing import Dict, List, Any, Optional, Union, Tuple, Callable
from ..utils import get_nested_data, try_int

import logging
logger = logging.getLogger(__name__)

class DataExtractor:
    def __init__(self, record_path: Optional[List[str]] = None,
                metadata_path_overrides: Optional[Dict[str, List[str]]] = None):
        """
        Initialize the DataExtractor with optional path overrides for metadata and records.

        Args:
            record_path (List[str], optional): Custom path to find records in the parsed data.
            metadata_path_overrides (Dict[str, List[str]], optional): Custom paths to find specific metadata fields.
        """
        self.metadata_path = metadata_path_overrides or {}
        self.record_path = record_path

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
            metadata = {key: try_int(get_nested_data(parsed_page_dict, path))
                        for key, path in self.metadata_path.items()}
            missing_keys = [k for k, v in metadata.items() if v is None]
            if missing_keys:
                logger.warning(f"The following metadata keys are missing or None: {', '.join(missing_keys)}")
        except KeyError as e:
            logger.error(f"Error extracting metadata due to missing key: {e}")
        return metadata

    def extract_records(self, parsed_page_dict: Dict) -> Optional[List[Dict]]:
        """
        Extract records from parsed data as a list of dicts.

        Args:
            parsed_page_dict (Dict): The dictionary containing the page data to be parsed.

        Returns:
            Optional[List[Dict]]: A list of records as dictionaries, or None if extraction fails.
        """
        return get_nested_data(parsed_page_dict, self.record_path) if self.record_path else None

    def dynamic_identification(self, parsed_page_dict: Dict) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Dynamically identify and separate metadata from records.

        Args:
            parsed_page_dict (Dict): The dictionary containing the page data to be parsed.

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
                    if len(value) > 1:  # assuming it's records if it's a list of dicts
                        records.extend(value)
                    else:
                        sub_metadata, sub_records = self.dynamic_identification(value[0])
                        metadata.update(sub_metadata)
                        records.extend(sub_records)
            else:
                metadata[key] = value

        return metadata, records

    def extract(self, parsed_page_dict: Dict) -> Tuple[Optional[List[Dict]], Optional[Dict]]: 
        """
        Extract both records and metadata from the parsed page dictionary.

        Args:
            parsed_page_dict (Dict): The dictionary containing the page data to be parsed.

        Returns:
            Tuple[Optional[List[Dict]], Optional[Dict]]: A tuple containing the list of records and the metadata dictionary.
        """
        if self.metadata_path or self.record_path:
            records = self.extract_records(parsed_page_dict)
            metadata = self.extract_metadata(parsed_page_dict)
        else:
            metadata, records = self.dynamic_identification(parsed_page_dict)

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


############################

# class DataExtractor:
#     # Providing default paths that work for a common case (e.g., Springer XML format)
#     DEFAULT_METADATA_PATH = {
#         'total_records': ['response', 'result', 'total'],
#         'page_length': ['response', 'result', 'recordsDisplayed'],
#         'total_displayed_records': ['response', 'result', 'pageLength'],
#     }
    
#     DEFAULT_RECORD_PATH = ['response','records','record']

#     def __init__(self, record_path: Optional[List[str]] = None,
#                 metadata_path_overrides: Optional[Dict[str, List[str]]] = None,
#                 search_metadata: bool = True
#                 ):
#         """
#         Initialize the DataExtractor with optional path overrides for metadata and records.

#         Args:
#             record_path (List[str], optional): Custom path to find records in the parsed data.
#             metadata_path_overrides (Dict[str, List[str]], optional): Custom paths to find specific metadata fields.
#             search_metadata (bool): Flag to determine if metadata should be extracted.
#         """
#         # Apply any user-provided overrides to the default paths
        
#         #self.search_text=search_text
#         #self.search_record_info=search_record_info
        
#         self.metadata_path = {**self.DEFAULT_METADATA_PATH, **(metadata_path_overrides or {})} if search_metadata else {}
#         self.record_path = record_path or self.DEFAULT_RECORD_PATH

#     def extract_metadata(self, parsed_page_dict: Dict) -> Dict:
#         """
#         Extracts and def extract(self, parsed_page_dict: Dict) -> Dict:
#         """
#         if not self.metadata_path:
#             logger.info("metadata paths are empty: skipping...")
#             return {}
        
#         metadata = {}
    
#         try:
#             # Use paths from self.metadata_path, leveraging the power of get_nested_data and try_int for flexibility
#             metadata = {key: try_int(get_nested_data(parsed_page_dict, path))
#                     for key, path in self.metadata_path.items()}

#             # Detect missing or None values
#             missing_keys = ",".join(k for k, v in metadata.items() if v is None)
#             if missing_keys:
#                 logger.warning(f'The following metadata keys are missing or None: {missing_keys}')

#             return metadata

#         except KeyError as e:
#             logger.error(f"Error extracting metadata due to missing key: {e}")
#             return {}
    
#     def extract_records(self, parsed_page_dict: Dict) -> List[Dict] | None:
#         """Extract records from parsed data as a list of dicts.

#         Args:    
#             dict (response type) : The dict object  response parsing step.

#         Returns:
#             list [dict] : response dict containing A list containing processed records as dictionaries.
#         """
#         return(get_nested_data(parsed_page_dict, self.record_path))
    
#     def extract(self,parsed_page_dict: Dict) -> Tuple[Optional[List[Dict]],Optional[Dict]]: 
#         """
#         Extracts both records and metadata from the parsed page dictionary.

#         Args:
#             parsed_page_dict (Dict): The dictionary containing the page data to be parsed.

#         Returns:
#             Tuple[Optional[List[Dict]],
#         """
            
#         records = self.extract_records(parsed_page_dict)
#         metadata = self.extract_metadata(parsed_page_dict)
#         return records, metadata
