from typing import Any, Optional, Union
from scholar_flux.exceptions import DataExtractionException
from scholar_flux.utils import get_nested_data, try_int, try_dict, as_list_1d, unlist_1d
from scholar_flux.utils.repr_utils import generate_repr_from_string

import logging

logger = logging.getLogger(__name__)


class BaseDataExtractor:

    def __init__(
        self,
        record_path: Optional[list] = None,
        metadata_path: Optional[list[list] | dict[str, list]] = None,
    ):
        """
        Initialize the DataExtractor with metadata and records to extract separately.

        If record path or metadata_path are specified,
           then the data extractor will attempt to retrieve the metadata and records at the
           provided paths. Note that, as metadata_paths can be associated with multiple keys,
           starting from the outside dictionary, we may have to specify a dictionary containing
           keys denoting metadata variables and their paths as a list of values indicating how to
           retrieve the value. The path can also be given by a list of lists describing how to
           retrieve the last element.

        Args:
            record_path (Optional[List[str]]): Custom path to find records in the parsed data. Contains a list of strings and
                                               rarely integers indexes indicating how to recursively find the list of records
            metadata_path (List[List[str]] | Optional[Dict[str, List[str]]]): Identifies the paths in a dictionary
                associated with metadata as opposed to records. This can be a list of paths where each element is a list
                describing how to get to a terminal
            element
        """
        self.metadata_path = metadata_path or {}
        self.record_path = record_path
        self._validate_paths(record_path, metadata_path)

    def _validate_paths(
        self,
        record_path: Optional[list] = None,
        metadata_path: Optional[list[list] | dict[str, list]] = None,
    ):
        """
        Method used to validate the path inputs provided to the DataExtractor prior to its later use
        In extracting metadata and records
        Args:
            record_path (Optional[List[str | None]]): The path where a list of records are located
            metadata_path (Optional[List[str | None]]): The list or dictionary of paths where metadata records are located
        Raises:
            DataExtractionException: Indicates an error in the DataExtractor and identifies where the inputs take on an invalid value
        """
        try:
            if record_path is not None:
                if not isinstance(record_path, list):
                    raise TypeError(f"A list is required for a record path. Received: {type(record_path)}")

                if not all(isinstance(path, (str, int)) for path in record_path):
                    raise KeyError(
                        f"At least one path in the provided record path is not an integer or string: {record_path}"
                    )
            if metadata_path is not None:
                if not isinstance(metadata_path, (list, dict)):
                    raise KeyError(
                        f"the provided metadata_path override is not a list or dictionary: {type(metadata_path)}"
                    )
                if not all(isinstance(path, (str, int, list)) for path in metadata_path):
                    raise KeyError(
                        f"At least one path in the provided metadata path override is not a list, integer, or string: {metadata_path}"
                    )

        except (KeyError, TypeError) as e:
            raise DataExtractionException(
                f"Error initializing the DataExtractor: At least one of the inputs are invalid. {e}"
            ) from e
        return None

    def extract_metadata(self, parsed_page_dict: dict) -> dict:
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
                metadata_path = {as_list_1d(key)[-1]: as_list_1d(path) for key, path in self.metadata_path.items()}

            # attempts to retrieve the path from the
            metadata = {key: try_int(get_nested_data(parsed_page_dict, path)) for key, path in metadata_path.items()}

            missing_keys = [str(k) for k, v in metadata.items() if v is None]
            if missing_keys:
                logger.warning(f"The following metadata keys are missing or None: {', '.join(missing_keys)}")

        except KeyError as e:
            logger.error(f"Error extracting metadata due to missing key: {e}")

        except Exception as e:
            logger.error(f"An unexpected error occurred during metadata extraction due to the following exception: {e}")
            raise DataExtractionException(
                f"An unexpected error occurred during metadata extraction due to the following exception: {e}"
            )

        return metadata

    def extract_records(self, parsed_page_dict: dict) -> Optional[list[dict[str, Any]]]:
        """
        Extract records from parsed data as a list of dicts.

        Args:
            parsed_page_dict (Dict): The dictionary containing the page data to be parsed.

        Returns:
            Optional[List[Dict]]: A list of records as dictionaries, or None if extraction fails.
        """
        nested_data = get_nested_data(parsed_page_dict, self.record_path) if self.record_path else None

        if isinstance(nested_data, list):
            return nested_data

        if not nested_data:
            logger.debug(f"No records extracted from path {self.record_path}")
            return None

        logger.debug(f"Expected a list at path {self.record_path}. Instead received {type(nested_data)}")
        return None

    @classmethod
    def _prepare_page(cls, parsed_page: Union[list[dict], dict]) -> dict:
        """
        Prepares the JSON data for metadata and record extraction by coercing it into a dictionary
        if not already a dictionary.

        Args:
            parsed_page (List[Dict] | Dict): The list or dictionary containing the page data and metadata to be
                                             extracted.

        Returns:
            Dict]: A dictionary containing the metadata and records to extract
        """

        if isinstance(parsed_page, list):
            parsed_page = unlist_1d(parsed_page)

        if not isinstance(parsed_page, dict):
            parsed_page_dict = try_dict(parsed_page)

            if parsed_page_dict is None:
                raise DataExtractionException(
                    f"Error converting parsed_page_dict of type {parsed_page_dict} to a dictionary"
                )
            parsed_page = parsed_page_dict
        return parsed_page

    def extract(self, parsed_page: Union[list[dict], dict]) -> tuple[Optional[list[dict]], Optional[dict[str, Any]]]:
        """
        Extract both records and metadata from the parsed page dictionary.

        Args:
            parsed_page (List[Dict] | Dict): The dictionary containing the page data and metadata to be extracted.

        Returns:
            Tuple[Optional[List[Dict]], Optional[Dict]]: A tuple containing the list of records and the metadata dictionary.
        """

        parsed_page = self._prepare_page(parsed_page)

        records = self.extract_records(parsed_page)
        metadata = self.extract_metadata(parsed_page)

        return records, metadata

    def __call__(self, parsed_page: Union[list[dict], dict]) -> tuple[Optional[list[dict]], Optional[dict[str, Any]]]:
        """
        Helper method enabling users to call the extractor as a function to extract both records and metadata

        Args:
            parsed_page (List[Dict] | Dict): The dictionary containing the page data and metadata to be extracted.

        Returns:
            Tuple[Optional[List[Dict]], Optional[Dict]]: A tuple containing the list of records and the metadata dictionary.

        """
        return self.extract(parsed_page)

    def __repr__(self) -> str:
        """
        Base method for indentifying the current implementation of the BaseDataExtractor. Subclasses can
        override this for more specific descriptions of attributes and defaults.
        Useful for showing the options being used for extracting metadata and records from the parsed
        json/data dictionaries from the api response.
        """
        class_name = self.__class__.__name__
        attribute_dict = {
            "record_path": self.record_path,
            "metadata_path": self.metadata_path,
        }
        return generate_repr_from_string(class_name, attribute_dict)
