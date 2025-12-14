# /data/base_extractor
"""The scholar_flux.data.base_extractor implements the core processes used to extract data from parsed responses.

The `BaseDataExtractor` implements the methods and functionality that are used when the structure of the parsed response
and paths for records and metadata are already known. The `BaseDataExtractor` serves as the base for later extension
with the `scholar_flux.data.data_extractor.DataExtractor` to dynamically identify records and metadata paths when the
structure of the response is not provided.

"""
from typing import Any, Optional, Union
from scholar_flux.exceptions import DataExtractionException
from scholar_flux.utils import get_nested_data, try_int, try_dict, as_list_1d, unlist_1d, PathUtils
from scholar_flux.utils.repr_utils import generate_repr

import logging

logger = logging.getLogger(__name__)


class BaseDataExtractor:
    """Base DataExtractor implementing the minimum components necessary to extract records and metadata from parsed
    responses when the location of records and metadata is known beforehand."""

    def __init__(
        self,
        record_path: Optional[list] = None,
        metadata_path: Optional[list[list] | dict[str, list]] = None,
    ):
        """Initialize the DataExtractor with metadata and records to extract separately.

        If record path or metadata_path are specified,
        then the data extractor will attempt to retrieve the metadata and records at the
        provided paths. Note that, as metadata_paths can be associated with multiple keys,
        starting from the outside dictionary, we may have to specify a dictionary containing
        keys denoting metadata variables and their paths as a list of values indicating how to
        retrieve the value. The path can also be given by a list of lists describing how to
        retrieve the last element.

        While the encouraged type for `record_path` is a list of strings that each represent each nested path element
        to be traversed to arrive at a value for a field, a delimited string can also be used with the default
        delimiter being `scholar_flux.utils.PathStr.DELIMITER`. Similarly, a list or dictionary of path strings
        can also be used as shorthand for the individual metadata fields containing relevant metadata values.

        Similarly, a list or dictionary of path strings can also be used as shorthand for the individual metadata
        fields containing relevant metadata values.

        Args:
            record_path (Optional[List[str]]):
                Custom path to find records in the parsed data. Contains a list of strings and rarely integers indexes
                indicating how to recursively find the list of records.
            metadata_path (List[List[str]] | Optional[Dict[str, List[str]]]):
                Identifies the paths in a dictionary associated with metadata as opposed to records. This can be a list
                of paths where each element is a list describing how to arrive at a terminal element.

        """
        self.metadata_path = self._prepare_metadata_path(metadata_path or {})
        self.record_path = record_path if not isinstance(record_path, str) else PathUtils.path_split(record_path)
        self._validate_inputs()

    @staticmethod
    def _prepare_metadata_path(
        metadata_path: list[list] | list[str] | dict[str, list] | dict[str, Any],
    ) -> list[list[str]] | Optional[dict[str, list[str]]]:
        """Helper method for splitting metadata paths with nested elements that are represented as strings.

        The delimiter, `scholar_flux.utils.PathUtils.DELIMITER` (`.` by default) is used if a delimiter is not
        directly specified.

        Args:
            metadata_path (list[list] | list[str] | dict[str, list] | dict[str, Any]):
                A metadata path to split if represented as a list containing nested string elements representing paths.

        Returns:
             metadata_path (List[List[str]] | Dict[str, List[str]]):
                 The metadata path list that identifies metadata fields within a parsed response retrieved from an API.

        """

        if isinstance(metadata_path, list):
            return [
                PathUtils.path_split(path_element) if isinstance(path_element, str) else path_element
                for path_element in metadata_path
            ]
        if isinstance(metadata_path, dict):
            return {
                key: PathUtils.path_split(path_element) if isinstance(path_element, str) else path_element
                for key, path_element in metadata_path.items()
            }
        return metadata_path

    @staticmethod
    def _prepare_record_path(record_path: Optional[list[str] | str]) -> Optional[list[str]]:
        """Helper method for splitting record paths with nested elements that are represented as strings.

        The delimiter, `scholar_flux.utils.PathUtils.DELIMITER` (`.` by default) is used if a delimiter is not
        directly specified.

        Args:
            record_path (Optional[List[str] | str]):
                A record path to split if represented as a string

        Returns:
             metadata_path (List[List[str]] | Optional[Dict[str, List[str]]]):
                 The formatted record path representing the keys that must be traversed to arrive at response records.

        """
        return PathUtils.path_split(record_path) if isinstance(record_path, str) else record_path

    def _validate_inputs(self) -> None:
        """Method used to validate the inputs provided to the DataExtractor prior to its later use in extracting
        metadata and records. This method operates by verifying the attributes associated with the current data
        extractor once the attributes are set.

        Validated Attributes:
            record_path (Optional[List[str | None]]): The path where a list of records are located
            metadata_path (Optional[List[str | None]]): The list or dictionary of paths where metadata records are located
            dynamic_record_identifiers (Optional[List[str | None]]): Keyword identifier indicating when singular records in a dictionary
                                                                      can be identified as such in contrast to metadata
            dynamic_metadata_identifiers (Optional[List[str | None]]): Keyword identifier indicating when record metadata keys in a dictionary
                                                                       can be identified as such in contrast to metadata

        Raises:
            DataExtractionException: Indicates an error in the DataExtractor and identifies where the inputs take on an invalid value

        """
        self._validate_paths(self.record_path, self.metadata_path)
        return None

    @classmethod
    def _validate_paths(
        cls,
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
                        f"The provided metadata path override is not a list or dictionary: {type(metadata_path)}"
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

    def extract_metadata(self, parsed_page_dict: dict[str, Any]) -> dict[str, Any]:
        """Extract metadata from the parsed page dictionary.

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

            # attempts to retrieve the path from the dictionary of metadata paths
            metadata = {key: try_int(get_nested_data(parsed_page_dict, path)) for key, path in metadata_path.items()}

            missing_keys = [str(k) for k, v in metadata.items() if v is None]
            if missing_keys:
                logger.warning(f"The following metadata keys are missing or None: {', '.join(missing_keys)}")

        except KeyError as e:
            logger.error(f"Error extracting metadata due to missing key: {e}")

        except Exception as e:
            msg = f"An unexpected error occurred during metadata extraction due to the following exception: {e}"
            logger.error(msg)
            raise DataExtractionException(msg)

        return metadata

    def extract_records(self, parsed_page_dict: dict) -> Optional[list[dict[str, Any]]]:
        """Extract records from parsed data as a list of dicts.

        Args:
            parsed_page_dict (Dict): The dictionary containing the page data to be parsed.

        Returns:
            Optional[List[Dict]]: A list of records as dictionaries, or None if extraction fails.

        """
        try:
            nested_data = get_nested_data(parsed_page_dict, self.record_path) if self.record_path else None

            if isinstance(nested_data, list):
                return nested_data

            if not nested_data:
                logger.debug(f"No records extracted from path {self.record_path}")
                return None

            logger.debug(f"Expected a list at path {self.record_path}. Instead received {type(nested_data)}")
            return None
        except Exception as e:
            msg = f"An unexpected error occurred during record extraction due to the following exception: {e}"
            logger.error(msg)
            raise DataExtractionException(msg)

    @classmethod
    def _prepare_page(cls, parsed_page: Union[list[dict], dict]) -> dict:
        """Prepares the JSON data for metadata and record extraction by coercing it into a dictionary if not already a
        dictionary.

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
                    f"Error converting parsed_page_dict of type {parsed_page} to a dictionary"
                )
            parsed_page_dict = {str(k): v for k, v in parsed_page_dict.items()}
            parsed_page = parsed_page_dict
        return parsed_page

    def extract(self, parsed_page: Union[list[dict], dict]) -> tuple[Optional[list[dict]], Optional[dict[str, Any]]]:
        """Extract both records and metadata from the parsed page dictionary.

        Args:
            parsed_page (Union[list[dict], dict]): The dictionary containing the page data and metadata to be extracted.

        Returns:
            Tuple[Optional[list[dict]], Optional[dict]]: A tuple containing the list of records and the metadata dictionary.

        """

        parsed_page = self._prepare_page(parsed_page)

        records = self.extract_records(parsed_page)
        metadata = self.extract_metadata(parsed_page)

        return records, metadata

    def __call__(self, parsed_page: Union[list[dict], dict]) -> tuple[Optional[list[dict]], Optional[dict[str, Any]]]:
        """Helper method enabling users to call the extractor as a function to extract both records and metadata.

        Args:
            parsed_page (List[Dict] | Dict): The dictionary containing the page data and metadata to be extracted.

        Returns:
            Tuple[Optional[List[Dict]], Optional[Dict]]: A tuple containing the list of records and the metadata dictionary.

        """
        return self.extract(parsed_page)

    def structure(self, flatten: bool = False, show_value_attributes: bool = True) -> str:
        """Base method for showing the structure of the current Data Extractor. This method reveals the configuration
        settings of the extractor config that will be used to extract records and metadata.

        Returns:
            str: The current structure of the BaseDataExtractor or its subclass.

        """

        return generate_repr(self, flatten=flatten, show_value_attributes=show_value_attributes)

    def __repr__(self) -> str:
        """Base method for identifying the current implementation of the BaseDataExtractor. Subclasses can override this
        for more specific descriptions of attributes and defaults. Useful for showing the options being used for
        extracting metadata and records from the parsed json/data dictionaries from the api response.

        Returns:
            str: The representation of the current object

        """
        return self.structure()


__all__ = ["BaseDataExtractor"]
