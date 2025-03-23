import re
import os
import logging
from typing import Optional, List, Dict, Union, Any, Tuple, Pattern, Set

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class PathUtils:
    @staticmethod
    def path_name(level_names: Union[str, List[Any]], min_length=2, delimiter='.') -> Optional[str]:
        """Generates a name for the given level names"""
        if not level_names:
            return None

        level_list = [level for level in PathUtils.split_path(level_names, delimiter) if isinstance(level, str) and not  level.isdigit()]
        name_list = level_list[-min_length:]
        
        name = PathUtils.path_str(name_list, delimiter=delimiter)
        logger.debug(f"Found name: {name}")
        return name
        #logger.debug(f"Generating path name for levels: {level_names}")
#        if not level_names:
#            return ""
#        name_list = [level for level in PathUtils.split_path(level_names,delimiter) if not isinstance(level, int) and level is not None]
#        name_list=name_list[-min_length:]
#        name=PathUtils.path_str(name_list,delimiter=delimiter)
#        if name and name is not None:
#            logger.debug(f"Found non-integer/non-null name: {name}")
#        return name


    @staticmethod
    def path_str(level_names: Union[str, List[Any]], delimiter='.') -> Optional[str]:
        """Joins a list of keys forming a path as a string"""
        if isinstance(level_names, str):
            path_str = level_names.split(delimiter)
        elif isinstance(level_names, list):
            path_str = [str(key) for key in level_names]
        else:
            return None
        #logger.debug(f"Joined path: {path_str}")
        return delimiter.join(path_str)


    @staticmethod
    def remove_path_indices(path: List[Any]) -> List[Any]:
        """Removes indices from the given path"""
        logger.debug(f"Removing indices from path: {path}")
        key_path = [k for k in path if isinstance(k, str) and not k.isdigit()]
        logger.debug(f"Path without indices: {key_path}")
        return key_path

    @staticmethod
    def constant_path_indices(path: List[Any],constant='i') -> List[Any]:
        """Converts any integer elements into a string 'i'"""
        key_path = [constant if isinstance(k, int) or (isinstance(k,str) and k.isdigit()) else k for k in path]
        logger.debug(f"constant path indices: {key_path}")
        return key_path

    @staticmethod
    def group_path_assignments(path: List[Any],delimiter: str = '.',constant='i') -> Optional[str]:
        """Groups the given path assignments"""
        if not  isinstance(path,list):
            logger.debug(f"cannot group {path}: is not a list") 
            return None

        key_path = PathUtils.constant_path_indices(path,constant)
        
        if key_path:
            grouped_path = PathUtils.path_str(key_path, delimiter=delimiter)
            logger.debug(f"Grouped path: {grouped_path}")
            return grouped_path
        else:
            logger.debug("No valid keys found in the path")
            return None

    @staticmethod
    def _extract_child_keys(parent_keys: Union[str, List[str]], child_keys: Union[str, List[str]],delimiter='.') -> List[str]:
        """Retrieve the keys that should appear subsequent to known parent keys, if any.
           Otherwise, returns the child_keys as is, assuming child_keys must be added
           starting from the root node"""
        if parent_keys:
            parent_keys=PathUtils.split_path(parent_keys,delimiter)
            child_keys=PathUtils.split_path(child_keys,delimiter)

            if parent_keys == child_keys[:len(parent_keys)]:
                child_keys = child_keys[len(parent_keys):]
        return child_keys

    @staticmethod
    def path_as_parent_child(node_path: Union[str, List[str]],delimiter='.') -> Tuple[List[str], Optional[str]]:
        """Split the given path (list or string) as parent child"""
        if node_path:
            node_path = PathUtils.split_path(node_path,delimiter) 
            return node_path[:-1], node_path[-1]
        return [], None

    @staticmethod
    def split_path(node_path: Union[str, List[str]],delimiter = '.') -> List[str]:
        """Splits the given path into a list of strings"""
        if not isinstance(node_path, str) and not isinstance(node_path, list):
            raise ValueError(f"Cannot split {node_path} as list of keys")
        
        path_list = node_path.split(delimiter) if isinstance(node_path, str) else node_path
        

        #logger.debug(f"Split path: {path_list}")
        return [str(key) for key in path_list]

    @staticmethod
    def _construct_full_path(parent_keys: Union[str, List[str]], child_key: Optional[Union[str, List[str]]] = None,delimiter: str ='.') -> str:
        """Return the string representation of the full path"""
        parent_keys = PathUtils.path_str(parent_keys,delimiter) or "" if isinstance(parent_keys, list) else parent_keys 
        child_key = child_key[0] if child_key and isinstance(child_key, list) else child_key
        if child_key is None or not child_key:
            raise KeyError(f"Child Key '{child_key}' is missing or blank")
        return f'{parent_keys}{delimiter}{child_key}' if parent_keys else f"{child_key}"


