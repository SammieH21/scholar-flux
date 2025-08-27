from typing import Any, Optional
from scholar_flux.utils import (get_nested_data, as_list_1d,
                                unlist_1d, nested_key_exists)

from scholar_flux.data import ABCDataProcessor
from scholar_flux.exceptions import DataProcessingException

import logging
logger = logging.getLogger(__name__)

class DataProcessor(ABCDataProcessor):
    """
    Initialize the DataProcessor with explicit extraction paths and options.

    Args:
        record_keys: Keys to extract, as a dict of output_key to path, or a list of paths.
        ignore_keys: List of keys to ignore during processing.
        ignore_keys: List of keys that records should contain during processing.
        value_delimiter: Delimiter for joining multiple values.
        regex: Whether to use regex for ignore filtering.
    """
    def __init__(self,
                 record_keys: Optional[dict[str | int, Any] | list[list[str | int]]]=None,
                 ignore_keys: Optional[list[str]] = None,
                 keep_keys: Optional[list[str]] = None,
                 value_delimiter: Optional[str] = "; ",
                 regex: Optional[bool]=True) -> None:
        """
        Initialize the DataProcessor with explicit extraction paths and options.

        Args:
            record_keys: Keys to extract, as a dict of output_key to path, or a list of paths.
            ignore_keys: List of keys to ignore during processing.
            value_delimiter: Delimiter for joining multiple values.
            regex: Whether to use regex for ignore filtering.
        """
        super().__init__()

        self._validate_inputs(record_keys, ignore_keys, keep_keys, value_delimiter)
        self.record_keys: dict[str | int, list[str | int]] = self._prepare_record_keys(record_keys) or {}
        self.ignore_keys: list[str] =  ignore_keys or []
        self.keep_keys: list[str] =  keep_keys or []
        self.value_delimiter = value_delimiter
        self.regex: bool = regex if regex else False

    @staticmethod
    def _validate_inputs(record_keys: Optional[dict[str | int, Any] | list[list[str | int]]],
                         ignore_keys: Optional[list[str]],
                         keep_keys: Optional[list[str]],
                         value_delimiter: Optional[str]
                        ):
        """Helper class for ensuring that inputs to the data processor match the intended types"""
        if record_keys is not None and not isinstance(record_keys, list) and not isinstance(record_keys, dict):
            raise DataProcessingException(
                f"record_keys must be a list or dict, got {type(record_keys)}"
            )
        if ignore_keys is not None and not isinstance(ignore_keys, list):
            raise DataProcessingException(
                f"ignore_keys must be a list, got {type(ignore_keys)}"
            )
        if keep_keys is not None and not isinstance(keep_keys, list):
            raise DataProcessingException(
                f"keep_keys must be a list, got {type(keep_keys)}"
            )
        if value_delimiter is not None and not isinstance(value_delimiter, str):
            raise DataProcessingException(
                f"value_delimiter must be a string, got {type(value_delimiter)}"
            )

    @staticmethod
    def _prepare_record_keys(record_keys: Optional[dict[str | int, Any] | list[list[str | int]]]
                            ) -> Optional[dict[str | int, list[str | int]]]:
        """
        Convert record_key input into a standardized dict key value pairs. The keys represent the final key/column name
        corresponding to each nested path. Its corresponding value is a list containing each step as an element leading
        up to the final element/node in the path.

        Accepts either a list of paths or a dict of output_key to path.

        Args:
            record_keys (Optional[dict[str | int, Any] | list[list[str | int]]]): Key/path combinations indicating
                        the necessary paths to extract and, if a dictionary, the key to rename the path with.
        Returns:

        """

        try:
            if record_keys is None:
                return None
            elif isinstance(record_keys, list):
                # creates a dictionary where the joined list represents the key
                record_keys_dict: Optional[dict[str | int, list[str | int]]] = {
                    ".".join(f"{p}" for p in as_list_1d(record_key_path)) : as_list_1d(record_key_path)
                    for record_key_path in record_keys if record_key_path != []
                }

            elif isinstance(record_keys, dict):
                # retrieve the value in the dictionary as the full path to the element.
                # If the path is an empty list, the path will defaults to the key instead
                record_keys_dict = {key: (as_list_1d(path) or [key]) for key, path in record_keys.items()}

            else:
                raise TypeError('Expected a dictionary of string to path mappings or a list of lists containing paths. '
                                f'Received type ({record_keys})')

            return record_keys_dict
        except (TypeError, AttributeError, ValueError) as e:
            raise DataProcessingException('The record_keys attribute could not be prepared. Check the inputs: ') from e


    @staticmethod
    def extract_key(record: dict[str | int, Any] | list[str | int] | str | int | None,
                    key: str | int,
                    path: Optional[list[str | int]] = None) -> Optional[list]:
        """
        Processes a specific key from a record by retrieving the value associated with the key at the nested path.
        Depending on whether `value_delimiter` is set, the method will joining non-None values into a string
        using the delimiter. Otherwise, keys with lists as values will contain the lists un-edited.

        Args:
            record: The record dictionary to extract the key from.
            key: The key to process within the record dictionary.

        Returns:
            str: A string containing non-None values from the specified key in the record dictionary, joined by '; '.
        """

        if record is None:
            logger.warning(f'Cannot retrieve {key} as the record is None.')
            return None

        nested_record_data = (get_nested_data(record, path)
                              if path and isinstance(record, (list, dict))
                              else record)

        if not isinstance(nested_record_data, dict):
            logger.warning(f'Cannot retrieve {key} from the following record: {record}')
            return None

        record_field = as_list_1d(nested_record_data.get(key, [])) or None
        return record_field

    def process_record(self, record_dict: dict[str | int, Any])->dict[str, Any]:
        """
        Processes a record dictionary to extract record data and article content, creating a processed record dictionary with an abstract field.

        Args:
        - record_dict: The dictionary containing the record data.

        Returns:
        - dict: A processed record dictionary with record keys processed and an abstract field created from the article content.
        """

        # retrieve a dict containing the fields for the current record
        if not record_dict:
            logger.debug("A record is empty: skipping,,,")
            # Simplified record data processing using dictionary comprehension

        processed_record_dict = {
            key: self.extract_key(record_dict, path[-1], path[:-1]) for key, path in self.record_keys.items()
        } if self.record_keys else {}



        return self.collapse_fields(processed_record_dict)

    def collapse_fields(self, processed_record_dict: dict) -> dict[str, list[str | int] | str | int]:
        """Helper method for joining lists of data into a singular string for flattening"""
        if processed_record_dict and self.value_delimiter is not None:
            return {k : (self.value_delimiter.join(str(i) for i in field_item)
                        if field_item is not None and len(field_item) > 1
                         else unlist_1d(field_item)) for
                    k, field_item in processed_record_dict.items()}
        return {k: unlist_1d(v) for k, v in processed_record_dict.items()}

    def process_page(self,
                     parsed_records: list[dict[str | int, Any]],
                     ignore_keys:Optional[list[str]]=None,
                     keep_keys:Optional[list[str]]=None,
                     regex: Optional[bool]=None)->list[dict]:

        keep_keys = keep_keys or self.keep_keys
        ignore_keys = ignore_keys or self.ignore_keys
        regex = regex if regex is not None else self.regex

        # processes each individual record dict
        processed_record_dict_list = [
            self.process_record(record_dict) for record_dict in parsed_records
            if (not keep_keys or self.record_filter(record_dict, keep_keys, regex)) and
            not self.record_filter(record_dict, ignore_keys, regex)
        ]

        logging.info(f"total included records - {len(processed_record_dict_list)}")


        # return the list of processed record dicts
        return processed_record_dict_list

    def record_filter(self,
                      record_dict: dict[str | int, Any],
                      record_keys: Optional[list[str]]=None,
                      regex:Optional[bool]=None) -> bool:
        ''' filter records, using regex pattern matching, checking if any of the keys provided in the function call exist '''
        use_regex = regex if regex is not None else False
        if record_keys:
            logger.debug(f"Finding field key matches within processing data: {record_keys}")
            matches=[nested_key_exists(record_dict,key,regex=use_regex) for key in record_keys] or []
            return len([match for match in matches if match]) > 0
        return False


# if __name__ == '__main__':
#     record_test_json: list[dict] = [
#             {
#                 "authors": {
#                     "principle_investigator": "Dr. Smith",
#                     "assistant": "Jane Doe"
#                 },
#                 "doi": "10.1234/example.doi",
#                 "title": "Sample Study",
#                 "abstract": ["This is a sample abstract.", "keywords: 'sample', 'abstract'"],
#                 "genre": {
#                     "subspecialty": "Neuroscience"
#                 },
#                 "journal": {
#                     "topic": "Sleep Research"
#                 }
#             },
#             {
#                 "authors": {
#                     "principle_investigator": "Dr. Lee",
#                     "assistant": "John Roe"
#                 },
#                 "doi": "10.5678/example2.doi",
#                 "title": "Another Study",
#                 "abstract": "Another abstract.",
#                 "genre": {
#                     "subspecialty": "Psychiatry"
#                 },
#                 "journal": {
#                     "topic": "Dreams"
#                 }
#             }
#         ]
#     processor = DataProcessor(
#         record_keys = [
#         ["authors","principle_investigator"],
#         ["authors", "assistant"],
#         ["doi"],
#         ["title"],
#         ["genre","subspecialty"],
#         ["journal","topic"],
#         ["abstract"]
#         ],
#         value_delimiter= None
#     )
#     processed = processor.process_page(record_test_json)
#
#     processor_two = DataProcessor(
#         record_keys = {
#             "authors.principle_investigator":["authors","principle_investigator"],
#             "authors.assistant":["authors", "assistant"],
#             "doi":["doi"],
#             "title":["title"],
#             "genre.subspecialty":["genre","subspecialty"],
#             "journal.topic":["journal","topic"],
#             "abstract":["abstract"]
#         },
#         value_delimiter= None
#     )
#     processed_two = processor.process_page(record_test_json)
#
#     assert processed == processed_two
