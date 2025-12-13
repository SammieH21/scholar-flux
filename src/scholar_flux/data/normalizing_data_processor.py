# /data/normalizing_data_processor.py
"""This normalizing_data_processor.py module implements the NormalizingDataProcessor for normalizing API field names."""
from scholar_flux.data.data_processor import DataProcessor
from scholar_flux.utils.json_processing_utils import RecursiveJsonProcessor, PathUtils
from scholar_flux.utils.helpers import is_nested_json
from typing import Optional, Any
import logging

logger = logging.getLogger(__name__)


class NormalizingDataProcessor(DataProcessor):
    """A data processor that flattens records before extraction, extending DataProcessor.

    This processor adds a normalization step to DataProcessor:
    1. Flattens each record into dot-notation keys (e.g., "school.department")
    2. Extracts specified fields using parent class logic
    3. Handles already-flattened records (idempotent operation)

    Inherits all functionality from DataProcessor, including:
    - Field extraction via record_keys
    - Record filtering via ignore_keys/keep_keys
    - Value collapsing via value_delimiter

    Args:
        record_keys: Keys to extract (same as DataProcessor).
        ignore_keys: List of keys to ignore during processing.
        keep_keys: List of keys that must be present to keep a record.
        value_delimiter: Delimiter for joining multiple values.
        regex: Whether to use regex for filtering.
        use_full_path: Whether to preserve full paths in flattened keys.

    Examples:
        >>> from scholar_flux.data import NormalizingDataProcessor
        >>> data = [{'id':1, 'school':{'department':'NYU Department of Mathematics'}},
        >>>         {'id':2, 'school':{'department':'GSU Department of History'}},
        >>>         {'id':3, 'school':{'organization':'Pharmaceutical Research Team'}}]
        # creating a basic processor
        >>> data_processor = NormalizingDataProcessor(record_keys = [['id'], ['school', 'department'], ['school', 'organization']]) # instantiating the class
        ### The process_page method can then be referenced using the processor as a callable:
        >>> result = data_processor(data) # recursively flattens and processes by default
        >>> print(result)
        # OUTPUT: [{'id': 1, 'school.department': 'NYU Department of Mathematics', 'school.organization': None},
        #          {'id': 2, 'school.department': 'GSU Department of History', 'school.organization': None},
        #          {'id': 3, 'school.department': None, 'school.organization': 'Pharmaceutical Research Team'}]
        # String paths can also be used to accomplish the same:
        >>> data_processor = NormalizingDataProcessor(record_keys = ['id', 'school.department', 'school.organization']) # instantiating the class
        >>> assert data_processor.process_page(data) == result

    """

    def __init__(
        self,
        record_keys: Optional[
            dict[str | int, Any] | dict[str, Any] | list[list[str | int]] | list[list[str]] | list[str]
        ] = None,
        ignore_keys: Optional[list[str]] = None,
        keep_keys: Optional[list[str]] = None,
        value_delimiter: Optional[str] = None,
        regex: Optional[bool] = True,
        traverse_lists: Optional[bool] = True,
    ) -> None:
        """Initializes the NormalizingDataProcessor.

        Args:
            record_keys: Keys to extract, as a dict of output_key to path, or a list of paths.
            ignore_keys: List of keys to ignore during processing.
            value_delimiter: Delimiter for joining multiple values.
            regex: Whether to use regex for ignore filtering.
            traverse_lists: (Optional[bool]):
                Determines whether lists are automatically traversed when indices are not specified in the path.

        """
        # Call parent constructor
        super().__init__(
            record_keys=record_keys,
            ignore_keys=ignore_keys,
            keep_keys=keep_keys,
            value_delimiter=value_delimiter,
            regex=regex,
        )

        self.traverse_lists = traverse_lists

        # Initialize the flattening processor
        self.recursive_processor = RecursiveJsonProcessor(
            object_delimiter=self.value_delimiter,
            use_full_path=True,  # True for effortless later extraction by path after flattening
        )

    @staticmethod
    def _as_normalized_key(path: list[str | int]) -> str:
        """Generate the expected normalized key from a path.

        This key can be later used to retrieve the values at normalized dictionary keys after flattening each record.

        Args:
            path: The original path (may include integer indices).

        Returns:
            str: The flattened key name (without indices).

        """
        # Remove integer indices to get the base path
        key_path = PathUtils.remove_path_indices(path)

        if not key_path:
            # Fallback to original path if nothing remains
            return PathUtils.path_str(path)

        # Join into dot-notation string
        return PathUtils.path_str(key_path)

    def process_record(self, record_dict: dict[str, Any] | dict[str | int, Any]) -> dict[str, Any]:
        """Process a single record by flattening it first, then extracting fields.

        Overrides parent method to add flattening step before field extraction.

        Args:
            record_dict: The dictionary containing the record data.

        Returns:
            dict: A processed record with specified keys extracted.

        """
        if not record_dict:
            logger.debug("Record is empty: skipping...")
            return {}

        if not self.record_keys:
            return {}

        # Step 1: Flatten the record if needed
        if not is_nested_json(record_dict):
            flattened_record: dict[str, Any] | dict[str | int, Any] = record_dict
        else:
            # Flatten the entire record using traversal_paths for efficiency
            record_keys_paths = list(self.record_keys.values())
            flattened_record = (
                self.recursive_processor.process_and_flatten(
                    obj=record_dict, traversal_paths=record_keys_paths, traverse_lists=self.traverse_lists or False
                )
                or {}
            )

            if not flattened_record:
                logger.debug("Flattening returned no results")
                # Return dict with None values for all expected keys
                return self.collapse_fields({key: None for key in self.record_keys})

        processed_record_dict = {}
        for output_key, path in self.record_keys.items():
            # Get the expected flattened key (without indices)
            flattened_key = self._as_normalized_key(path)

            # Try to get the value from flattened record
            value = flattened_record.get(flattened_key or "") if isinstance(flattened_record, dict) else None

            processed_record_dict[output_key] = value

        return self.collapse_fields(processed_record_dict)


__all__ = ["NormalizingDataProcessor"]
