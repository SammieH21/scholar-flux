from typing import Any, Optional, Union
from scholar_flux.exceptions import DataExtractionException

from scholar_flux.data.base_extractor import BaseDataExtractor

import logging

logger = logging.getLogger(__name__)


class DataExtractor(BaseDataExtractor):
    DEFAULT_DYNAMIC_RECORD_IDENTIFIERS = ("title", "doi", "abstract")
    DEFAULT_DYNAMIC_METADATA_IDENTIFIERS = ("metadata", "facets", "IdList")

    def __init__(
        self,
        record_path: Optional[list] = None,
        metadata_path: Optional[list[list] | dict[str, list]] = None,
        dynamic_record_identifiers: Optional[list | tuple] = None,
        dynamic_metadata_identifiers: Optional[list | tuple] = None,
    ):
        """
        Initialize the DataExtractor with optional path overrides for metadata and records.
        The data extractor provides two ways to identify metadata paths and record paths:

            1) manual identification: If record path or metadata_path are specified,
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
            metadata_path (List[List[str]] | Optional[Dict[str, List[str]]]): Identifies the paths in a dictionary
                associated with metadata as opposed to records. This can be a list of paths where each element is a list
                describing how to get to a terminal
            element
            dynamic_record_identifiers (Optional[List[str]]): Helps to identify dictionary keys that only belong to records when
                                                              dealing with a single element that would otherwise be classified
                                                              as metadata.
            dynamic_metadata_identifiers (Optional[List[str]]): Helps to identify dictionary keys that are likely to only belong
                                                               to metadata that could otherwise share a similar structure to
                                                               a list of dictionaries, similar to what's seen with records.


        """
        super().__init__(record_path, metadata_path)

        self.dynamic_record_identifiers = (
            dynamic_record_identifiers
            if dynamic_record_identifiers is not None
            else self.DEFAULT_DYNAMIC_RECORD_IDENTIFIERS
        )
        self.dynamic_metadata_identifiers = (
            dynamic_metadata_identifiers
            if dynamic_metadata_identifiers is not None
            else self.DEFAULT_DYNAMIC_METADATA_IDENTIFIERS
        )
        self._validate_dynamic_identifiers(
            dynamic_record_identifiers, dynamic_metadata_identifiers
        )

    def _validate_dynamic_identifiers(
        self,
        dynamic_record_identifiers: Optional[list | tuple] = None,
        dynamic_metadata_identifiers: Optional[list | tuple] = None,
    ):
        """
        Method used to validate the dynamic record identifiers provided to the DataExtractor prior to its later use
        In extracting metadata and records
        Args:
            dynamic_record_identifiers (Optional[List[str | None]]): Keyword identifier indicating when singular records in a dictionary
                                                                     can be identified as such in contrast to metadata
            dynamic_metadata_identifiers (Optional[List[str | None]]): Keyword identifier indicating when record metadata keys in a dictionary
                                                                        can be identified as such in contrast to metadata
        Raises:
            DataExtractionException: Indicates an error in the DataExtractor and identifies where the inputs take on an invalid value
        """
        try:
            if dynamic_record_identifiers is not None:
                if not isinstance(dynamic_record_identifiers, (list, tuple)):
                    raise KeyError(
                        f"The dynamic record identifiers provided must be a tuple or list. Received: {type(dynamic_record_identifiers)}"
                    )
                if not all(
                    isinstance(path, (str)) for path in dynamic_record_identifiers
                ):
                    raise KeyError(
                        f"At least one value in the provided dynamic record identifier is not an integer or string: {dynamic_record_identifiers}"
                    )

            if dynamic_metadata_identifiers is not None:
                if not isinstance(dynamic_metadata_identifiers, (list, tuple)):
                    raise KeyError(
                        f"The dynamic metadata identifiers provided must be a tuple or list. Received: {type(dynamic_metadata_identifiers)}"
                    )
                if not all(
                    isinstance(path, (str)) for path in dynamic_metadata_identifiers
                ):
                    raise KeyError(
                        f"At least one value in the provided dynamic metadata identifier is not an integer or string: {dynamic_metadata_identifiers}"
                    )

        except (KeyError, TypeError) as e:
            raise DataExtractionException(
                f"Error initializing the DataExtractor: At least one of the inputs are invalid. {e}"
            ) from e
        return None

    def _validate_inputs(
        self,
        record_path: Optional[list] = None,
        metadata_path: Optional[list[list] | dict[str, list]] = None,
        dynamic_record_identifiers: Optional[list | tuple] = None,
        dynamic_metadata_identifiers: Optional[list | tuple] = None,
    ):
        """
        Method used to validate the inputs provided to the DataExtractor prior to its later use
        In extracting metadata and records
        Args:
            record_path (Optional[List[str | None]]): The path where a list of records are located
            metadata_path (Optional[List[str | None]]): The list or dictionary of paths where metadata records are located
            dynamic_record_identifiers (Optional[List[str | None]]): Keyword identifier indicating when singular records in a dictionary
                                                                       can be identified as such in contrast to metadata
            dynamic_metadata_identifiers (Optional[List[str | None]]): Keyword identifier indicating when record metadata keys in a dictionary
                                                                        can be identified as such in contrast to metadata
        Raises:
            DataExtractionException: Indicates an error in the DataExtractor and identifies where the inputs take on an invalid value
        """
        self._validate_paths(record_path, metadata_path)
        self._validate_dynamic_identifiers(
            dynamic_record_identifiers, dynamic_metadata_identifiers
        )
        return None

    def dynamic_identification(
        self, parsed_page_dict: dict
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
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

            if key in self.dynamic_metadata_identifiers:
                metadata[key] = value

            elif isinstance(value, dict):
                sub_metadata, sub_records = self.dynamic_identification(value)
                metadata.update(sub_metadata)
                records.extend(sub_records)

            elif isinstance(value, list):
                if all(isinstance(item, dict) for item in value):
                    if len(value) == 0:
                        logger.debug(f"Element at key: {key} is empty")
                    elif (
                        len(value) > 1
                    ):  # assuming it's records if it's a list of dicts

                        records.extend(value)
                    else:
                        record = value[0]
                        if self._identify_by_key(
                            record, self.dynamic_record_identifiers
                        ):
                            records.extend(value)
                            continue

                        sub_metadata, sub_records = self.dynamic_identification(
                            value[0]
                        )
                        metadata.update(sub_metadata)
                        records.extend(sub_records)
            else:
                metadata[key] = value

        return metadata, records

    @staticmethod
    def _identify_by_key(record: Any, key_identifiers: list | tuple) -> bool:
        """
        Helper method for determining if a key exists in a dictionary.
        If a record is not a dictionary, or a key is not contained in a record dictionary,
        then this method will return False by default.
        Args:
            record (Any):
                The an element in a JSON object. if a dictionary, Is checked to determine
                whether any of the selected key identifiers exist within it.
            key_identifiers (list | tuple):
                              contains keys to check for. if the key exists, we'll
        """
        return all(
            [
                isinstance(record, dict),
                any(
                    True
                    for id_key in (key_identifiers or [])
                    if any(id_key in record_key for record_key in record)
                ),
            ]
        )

    def extract(
        self, parsed_page: Union[list[dict], dict]
    ) -> tuple[Optional[list[dict]], Optional[dict[str, Any]]]:
        """
        Extract both records and metadata from the parsed page dictionary.

        Args:
            parsed_page (List[Dict] | Dict): The dictionary containing the page data and metadata to be extracted.

        Returns:
            Tuple[Optional[List[Dict]], Optional[Dict]]: A tuple containing the list of records and the metadata dictionary.
        """

        parsed_page_dict = self._prepare_page(parsed_page)

        if self.metadata_path or self.record_path:
            records = self.extract_records(parsed_page_dict)
            metadata = self.extract_metadata(parsed_page_dict)
        else:
            metadata, records = self.dynamic_identification(parsed_page_dict)

        return records, metadata

    def __repr__(self):
        """
        Method for indentifying the current implementation of the DataExtractor.
        Useful for showing the options being used for extracting metadata and records from the parsed
        json/data dictionaries from the api response.
        """
        class_name = self.__class__.__name__
        pad = "\n" + " " * (len(class_name) + 1)
        return (
            f"{class_name}(record_path={self.record_path},"
            f"{pad}metadata_path={self.metadata_path},"
            f"{pad}dynamic_record_identifiers={self.dynamic_record_identifiers}),"
            f"{pad}dynamic_metadata_identifiers={self.dynamic_metadata_identifiers})"
        )


# # Example of using DataExtractor with default paths
# if __name__ == "__main__":
#     from scholar_flux.api import SearchAPI
#     from scholar_flux.data import DataParser, DataExtractor
#     api = SearchAPI(query='game theory', use_cache = True)
#     response = api.search(page=1)
#
#     parser = DataParser()
#     extractor = DataExtractor()
#
#     parsed_response = parser(response)
#     records, metadata = extractor(parsed_response) if parsed_response is not None else (None, None)
#
#     # Example of customizing MetadataExtractor for a different data format or structure
#     custom_record_paths:list  = [
#        'response', 'docs'
#     ]
#
#     custom_metadata_paths: list[list] = [
#         ['response', 'numFound'],
#         ['response', 'start'],
#         ['response', 'maxScore']
#     ]
#
#     custom_extractor = DataExtractor(record_path=custom_record_paths,
#                                      metadata_path = custom_metadata_paths)
#     if parsed_response is not None:
#         records, metadata = custom_extractor.extract(parsed_response)
