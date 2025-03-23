import re
import logging
from typing import Dict, List, Tuple, Any, Optional, Union
from collections import defaultdict
from itertools import chain

logger = logging.getLogger(__name__)

class PathUtils:
    @staticmethod
    def path_name(level_names: List[Any]) -> str:
        logger.debug(f"Generating path name for levels: {level_names}")
        if not level_names:
            return ""
        for name in reversed(level_names):
            if not isinstance(name, int):
                logger.debug(f"Found non-integer name: {name}")
                return str(name)
        path_str = PathUtils.path_str(level_names)
        logger.debug(f"Generated path string: {path_str}")
        return path_str

    @staticmethod
    def path_str(level_names: List[Any]) -> str:
        logger.debug(f"Joining path levels: {level_names}")
        path_str = ".".join(map(str, level_names))
        logger.debug(f"Joined path string: {path_str}")
        return path_str

    @staticmethod
    def remove_path_indices(path: List[Any]) -> List[Any]:
        logger.debug(f"Removing indices from path: {path}")
        key_path = [k for k in path if not isinstance(k, int) and k not in ('value')]
        logger.debug(f"Path without indices: {key_path}")
        return key_path

    @staticmethod
    def constant_path_indices(path: List[Any]) -> List[Any]:
        key_path = ['i' if isinstance(k, int) else k for k in path]
        logger.debug(f"constant path indices: {key_path}")
        return key_path

    @staticmethod
    def group_path_assignments(path: List[Any]) -> Optional[str]:
        logger.debug(f"Grouping path assignments for path: {path}")
        key_path = PathUtils.constant_path_indices(path)
        if key_path:
            grouped_path = PathUtils.path_str(key_path)
            logger.debug(f"Grouped path: {grouped_path}")
            return grouped_path
        logger.debug("No valid keys found in path")
        return None

class TriePath:
    """
    A utility class to handle path operations within the trie.
    """

    def __init__(self, path: Union[str, List[str]], delimiter: str = '<>'):
        if isinstance(path, str):
            self.components = path.split(delimiter)
        elif isinstance(path, list):
            self.components = path
        else:
            raise ValueError("Path must be a string or a list of strings.")
        self.delimiter = delimiter

    def __str__(self) -> str:
        return self.delimiter.join(self.components)

    def __repr__(self) -> str:
        return f"TriePath({self.delimiter.join(self.components)})"

    def __truediv__(self, other: Union['TriePath', str]) -> 'TriePath':
        """
        Overloads the '/' operator for path concatenation.
        """
        if isinstance(other, TriePath):
            new_components = self.components + other.components
        elif isinstance(other, str):
            new_components = self.components + [other]
        else:
            raise ValueError("Can only concatenate with a TriePath or string.")
        return TriePath(new_components, self.delimiter)

    def to_string(self) -> str:
        return str(self)

    def to_list(self) -> List[str]:
        return self.components.copy()

    def to_alphanum(self, pad: int = 8) -> str:
        """
        Generates an alphanumeric representation of the path, padding numeric components for sorting.
        """
        padded_components = [
            re.sub(
                r'(^[a-zA-Z_\.\-]*)(\d+)$',
                lambda x: f"{x.group(1)}{x.group(2).zfill(pad)}",
                comp
            )
            for comp in self.components
        ]
        return self.delimiter.join(padded_components)

    def remove_indices(self, num: int = -1) -> 'TriePath':
        """
        Removes numeric components from the path.

        Args:
            num (int): Number of numeric components to remove. If negative, removes all.

        Returns:
            TriePath: A new TriePath without the specified numeric components.
        """
        if num < 0:
            filtered_components = [comp for comp in self.components if not comp.isdigit()]
        else:
            filtered_components = []
            removal_count = 0
            for component in self.components:
                if component.isdigit() and removal_count < num:
                    removal_count += 1
                else:
                    filtered_components.append(component)
        return TriePath(filtered_components, self.delimiter)

    def replace_indices(self, placeholder: str = 'i') -> 'TriePath':
        """
        Replaces numeric components with a placeholder.

        Args:
            placeholder (str): The placeholder string to replace numeric components.

        Returns:
            TriePath: A new TriePath with indices replaced.
        """
        new_components = [placeholder if comp.isdigit() else comp for comp in self.components]
        return TriePath(new_components, self.delimiter)

    def get_parent(self) -> Optional['TriePath']:
        """
        Returns the parent path.

        Returns:
            Optional[TriePath]: The parent TriePath or None if at the root.
        """
        if len(self.components) > 1:
            return TriePath(self.components[:-1], self.delimiter)
        return None

    def remove(self, removal_list: List[str]) -> 'TriePath':
        """
        Removes specified components from the path.

        Args:
            removal_list (List[str]): Components to remove.

        Returns:
            TriePath: A new TriePath without the specified components.
        """
        filtered_components = [comp for comp in self.components if comp not in removal_list]
        return TriePath(filtered_components, self.delimiter)

    def calculate_information_content(self, non_informative: List[str]) -> int:
        """
        Calculates the number of informative components.

        Args:
            non_informative (List[str]): Components considered non-informative.

        Returns:
            int: Number of informative components.
        """
        informative_path = self.remove(non_informative)
        return len(informative_path.components)

    def get_name(self, min_length: int = 2) -> 'TriePath':
        """
        Generates a name based on the last 'min_length' components.

        Args:
            min_length (int): Number of components to include.

        Returns:
            TriePath: The generated name as a TriePath.
        """
        return TriePath(self.components[-min_length:], self.delimiter)


class SparseTrieNode:
    def __init__(self, full_path: TriePath, value: Any = None, terminal_nodes: Optional[Dict[str, 'SparseTrieNode']] = None):
        self.full_path = full_path
        self.terminal_nodes = terminal_nodes or {}  # Child terminal nodes
        self.is_end_of_path = not bool(terminal_nodes)  # Mark as terminal if no children
        self.value = value

#   def update(self,var,value):
#       valid_vars = ('full_path','terminal_nodes','is_end_of_path','value')
#       if not var in valid_vars:
#           raise KeyError(f'Value {var} does not exist; valid values: {valid_vars}')
#       setattr(self,var,value)
#       return self

    def update(self, var: str, value: Any, inplace: bool = True) -> 'SparseTrieNode':
        """
        Updates an attribute of the node.

        Args:
            var (str): Attribute name to update.
            value (Any): New value for the attribute.
            inplace (bool): If True, updates the current node in place. If False, returns a new node with the updated value.

        Returns:
            SparseTrieNode: The updated node (self if inplace=True, a new node if inplace=False).

        Raises:
            KeyError: If the attribute does not exist.
        """
        valid_vars = ('full_path', 'terminal_nodes', 'is_end_of_path', 'value')
        if var not in valid_vars:
            raise KeyError(f"Attribute '{var}' does not exist; valid attributes: {valid_vars}")

        if inplace:
            # Update the current node in place
            setattr(self, var, value)
            return self
        else:
            # Create and return a new node with the updated value
            new_node = SparseTrieNode(
                full_path=self.full_path,
                terminal_nodes=deepcopy(self.terminal_nodes),
                value=self.value
            )
            setattr(new_node, var, value)
            return new_node


    def __repr__(self) -> str:
        """Represents the SparseTrieNode object as a string.

        Returns:
            str: A string representation of the SparseTrieNode, showing value, end-of-path status, and full path.
        """
        return ("SparseTrieNode("
                f"full_path='{self.full_path}')"
                f"is_end_of_path={self.is_end_of_path}, "
                f"terminal_nodes={self.terminal_nodes}, "
                f"value={self.value if isinstance(self.value, (float, int, type(None))) else str(self.value)[:30] + '...'}, )"
               )

class SparseTrie:
    def __init__(self, delimiter: str = '<>'):
        self.terminal_nodes: Dict[str, SparseTrieNode] = {}  # Only store terminal nodes
        self.delimiter = delimiter

    def index_json(self, nested_obj: Dict, path: List[str] = []) -> None:
        """Flattens the nested dictionary and inserts it into the trie."""
        if isinstance(nested_obj, dict):
            for key, value in nested_obj.items():
                new_path = path + [key]
                self.index_json(value, new_path)
        elif isinstance(nested_obj, list):
            for key, value in enumerate(nested_obj):
                new_path = path + [str(key)]
                self.index_json(value, new_path)
        else:
            self.insert(path, nested_obj)

    def insert(self, path: Union[str, List[str]], value: Any) -> None:
        """Inserts a new terminal node and updates paths upwards."""
        trie_path = TriePath(path, self.delimiter)  # Convert to TriePath
        

        # Create a new terminal node
        new_node = SparseTrieNode(full_path=trie_path, value=value)
        path_str = str(trie_path)  # Get path as string
        self.terminal_nodes[path_str] = new_node

        # Update paths starting from the new terminal node, moving upwards
        self.update_path_upwards(new_node)

    def update_path_upwards(self, current_node: SparseTrieNode) -> None:
        """Updates the path information for the given node and its ancestors."""

        path_str=str(current_node.full_path)
        if self.implicit_search(path_str,search_exact=False) and current_node.is_end_of_path:
            # If node is terminal, add it to terminal_nodes (generally already done during insertion)
            self.terminal_nodes[path_str] = current_node

        parent_path = current_node.full_path.get_parent()       
        while parent_path is not None:

            # If node is a parent (has children), it's not terminal anymore, so remove it from terminal_nodes
            parent_path_str=str(parent_path)
            self.terminal_nodes.pop(parent_path_str,None)

            #  parent_node = self.implicit_search(parent_path_str,search_exact=False)
            #  if parent_node is not None and parent_node.is_end_of_path:
            #      parent_node.is_end_of_path = False

            parent_path=parent_path.get_parent()

    def search(self, path: Union[str, List[str]]) -> Optional[SparseTrieNode]:
        """Searches for a node by its path."""
        trie_path = TriePath(path, self.delimiter)  # Convert to TriePath
        path_str = str(trie_path)  # Get path as string
        return self.terminal_nodes.get(path_str) or self.implicit_search(path_str)

    def implicit_search(self, path: str, search_exact: bool = False) -> Optional[SparseTrieNode]:
        """Searches for a value based on the given implicit path."""
        if search_exact and path in self.terminal_nodes:
            return self.terminal_nodes.get(path)

        # Find all terminal nodes that share the same prefix
        implicit_terminal_nodes = {key: node for key, node in self.terminal_nodes.items() if key.startswith(f"{path}{self.delimiter}")}
        if implicit_terminal_nodes:
            return SparseTrieNode(full_path=TriePath(path, self.delimiter),
                                  terminal_nodes=implicit_terminal_nodes)
        return None

    def update(self, path: Union[str, List[str]], new_value: Any) -> None:
        """Updates a terminal node's value based on the path."""
        node = self.search(path)
        if node:
            node.value = new_value
        else:
            self.insert(path, new_value)

    def remove(self, path: Union[str, List[str]]) -> None:
        """Removes a terminal node by its path."""
        trie_path = TriePath(path, self.delimiter)  # Convert to TriePath
        path_str = str(trie_path)  # Get path as string

        # Remove the node if it exists
        if path_str in self.terminal_nodes:
            del self.terminal_nodes[path_str]

        # Update paths upwards to ensure correct terminal node status
        parent_path = trie_path.get_parent()
        parent_path_str=str(parent_path)
        parent_node=self.implicit_search(parent_path_str,search_exact=False)
        if parent_node:
            self.update_path_upwards(parent_node)

    def search_fullmatch(self, pattern: str) -> List[str]:
        """Searches for paths that match the given regular expression pattern."""
        regex = re.compile(pattern)
        return [key for key in self.terminal_nodes if regex.fullmatch(key)]

    def remove_paths(self, paths: List[str]) -> None:
        """Removes multiple terminal nodes by absolute path."""
        for path in paths:
            if path in self.terminal_nodes:
                del self.terminal_nodes[path]

    def filter(self, path_string: str, keep: bool = False) -> bool:
        """Filters and removes or keeps paths matching a specific string pattern."""
        path_matches = self.search_fullmatch(f"{path_string}.*")
        if keep:
            # If keeping, remove all other paths except the matches
            all_paths = set(self.terminal_nodes.keys())
            path_matches = all_paths.difference(set(path_matches))
        if path_matches:
            self.remove_paths(list(path_matches))
            return True
        return False

    def prune(self, path_string: str, keep: bool = False) -> None:
        """Recursively filters nodes until no more matches are found."""
        continue_pruning = True
        while continue_pruning:
            continue_pruning = self.filter(path_string, keep)

    def collapse_indexed_trie(self) -> List[Dict[str,Any]]:
        #digits=set(int(node.full_path.components[0]) for  path_str, node in self.terminal_nodes.items()
        #    if node.full_path.components[0].isdigit())
        #indices = re.search(f'^[0-9]+{re.escape(self.delimiter)}',self.terminal_nodes.keys())

        indices=sorted(set(int(node.full_path.components[0]) for node in self.terminal_nodes.values()
            if node.full_path.components[0].isdigit()))
        nonindexed_nodes=[terminal_path for terminal_path, node in self.terminal_nodes.items()
                    if not node.full_path.components[0].isdigit()]
        if nonindexed_nodes:
            raise ValueError("Some Paths do not start with an Index")
        parent_nodes=[self.implicit_search(str(idx)) for idx in indices]
        simplifier=TrieSimplifier(non_informative=['i','value'])
        simplifier.simplify_paths(list(set(str(terminal_path.full_path.replace_indices()) for terminal_path in self.terminal_nodes.values())),
                                  #list(set(str(terminal_path.full_path.replace_indices()) for parent_node in parent_nodes for terminal_path in parent_node.terminal_nodes.values())),
                                  min_components=3,
                                 remove_noninformative=True)
        paginated_data_dict = []
        for parent_node in parent_nodes:
            if parent_node and parent_node.terminal_nodes:
               grouped_nodes=sorted([node for node
                                     in parent_node.terminal_nodes.values() ],
                                    key=lambda node: node.full_path.to_alphanum()
                                   )
               row_dict=simplifier.simplify_to_row([node.update('full_path',node.full_path.replace_indices(),inplace=False) for node in grouped_nodes])
               paginated_data_dict.append(row_dict)
        return paginated_data_dict
            

    def _get_structure(self, node: SparseTrieNode, structure_str: str = '', recursion_idx: int = 0, tab: int = 4) -> str:
        """Generates a human-readable representation of the Trie structure."""
        structure_str += f"{recursion_idx * (' ' * tab)}{node}\n"
        for child in node.terminal_nodes.values():
            structure_str = self._get_structure(child, structure_str, recursion_idx + 1)
        return structure_str

    def __repr__(self) -> str:
        """Represents the Trie object as a string."""
        structure_str = "SparseTrie Structure:\n"
        for node in self.terminal_nodes.values():
            structure_str += self._get_structure(node)
        return structure_str

class TrieSimplifier:
    def __init__(self, non_informative: List[str], delimiter: str = '<>'):
        """
        Initializes the TrieSimplifier with non-informative components and a delimiter.
        
        Args:
            - non_informative (List[str]): List of non-informative components to remove.
            - delimiter (str): The delimiter used to split path components. Defaults to '<>'.
        """
        self.non_informative = non_informative
        self.delimiter = delimiter
        self.name_mappings = dict()  # To track used names and avoid collisions
        #self.row_dict = defaultdict(list)  # To flatten/normalize tries into singular-row dictionaries for creating data sets

    def _generate_base_name(self, informative_path: TriePath, min_length: int) -> "TriePath":
        """
        Generates a base name by taking the minimum number of components from the path.
        
        Args:
            - informative_path (TriePath): The TriePath object representing the informative path components.
            - min_length (int): The minimum length of informative components to use in the name.
        
        Returns:
            - TriePath: A Trie Path for the base name generated from the path.
        """
        return informative_path.get_name(min_length=min_length)

    def _handle_collision(self, original_name: "TriePath") -> "TriePath":
        """
        Handles collisions by appending a number to the original name.
        
        Args:
            - original_name (str): The original name that caused a collision.
        
        Returns:
            - str: A unique name generated by appending a number to the original name.
        """
        counter = 1
        while f"{str(original_name)}_{counter}" in self.name_mappings.values():
            counter += 1
        return original_name / f'_{counter}'

    def generate_unique_name(self, trie_path: TriePath, min_components: int,remove_noninformative: bool = False) -> "TriePath":
        """
        Fallback mechanism to ensure a unique name by dynamically increasing the number of components
        or adding numbers as a last resort if the name is already used.
        
        Args:
            - trie_path (TriePath): The TriePath object representing the path components.
            - min_components (int): The minimum length of components to use in the name.
        
        Returns:
            - Trie Path generated with a unique string based on the last n informative path names, extended if necessary, or appended with a number as a last resort.
        """

        if remove_noninformative:
            trie_path = trie_path.remove(self.non_informative)

        component_index = min_components
        candidate_name = self._generate_base_name(trie_path, component_index)
        

        # Dynamically increase the number of components until the name is unique
        while (
            str(candidate_name) in self.name_mappings.values() or
            (candidate_name.calculate_information_content(self.non_informative) < min_components and
             component_index < len(trie_path.components))
              ):
            component_index += 1
            candidate_name = self._generate_base_name(trie_path, component_index)
        #print(candidate_name,'info =',candidate_name.calculate_information_content(self.non_informative))

            if component_index >= len(trie_path.components):
                break
        
        # If all components are exhausted and the name is still not unique, append a number
        if str(candidate_name) in self.name_mappings.values():
            candidate_name=self._handle_collision(candidate_name)
        

        return candidate_name

    def simplify_paths(self, paths: List[str], min_components: int,remove_noninformative: bool = False) -> Dict[str, str]:
        """
        Simplifies paths by removing non-informative components and selecting the last 'min_components' informative components,
        ensuring that each name is unique.
        
        Args:
            paths (List[str]): List of path strings to simplify.
            min_components (int): The desired number of informative components to retain in the simplified path.
            remove_noninformative (bool): Whether to remove non-informative components.
        
        Returns:
            Dict[str, str]: A dictionary mapping the original path to its simplified unique name.
        """
        for original_path in paths:
            trie_path = TriePath(original_path, delimiter=self.delimiter)
            
            # Remove non-informative components


            
            # Generate a unique name
            unique_name = self.name_mappings.get(original_path) or self.generate_unique_name(trie_path, min_components,remove_noninformative)
            self.name_mappings[str(original_path)] = str(unique_name)
        
        return self.name_mappings

# Unit tests

import unittest

class KeyFilterTests(unittest.TestCase):
    def setUp(self):
        # Create a sample dictionary for testing
        self.discovered_keys = {
            "John Doe": ["user.profile.name"],
            "johndoe@example.com": ["user.profile.email"],
            "en-US": ["system.settings.language"],
            "access_log_20240707.txt": ["system.logs.access"],
            "Widget X": ["product.catalog.item123.name"],
            "$19.99": ["product.catalog.item456.price"]
        }

    def test_filter_by_prefix(self):
        filtered = KeyFilter.filter_keys(self.discovered_keys, prefix="John")
        self.assertEqual(filtered, {
            "John Doe": ["user.profile.name"]
        })

    def test_filter_by_min_length(self):
        filtered = KeyFilter.filter_keys(self.discovered_keys, min_length=3)
        self.assertEqual(filtered, {
            "John Doe": ["user.profile.name"],
            "johndoe@example.com": ["user.profile.email"],
            "en-US": ["system.settings.language"],
            "access_log_20240707.txt": ["system.logs.access"],
            "Widget X": ["product.catalog.item123.name"],
            "$19.99": ["product.catalog.item456.price"]
        })

    def test_filter_by_substring(self):
        filtered = KeyFilter.filter_keys(self.discovered_keys, substring="catalog")
        self.assertEqual(filtered, {
            "Widget X": ["product.catalog.item123.name"],
            "$19.99": ["product.catalog.item456.price"]
        })

    def test_filter_by_pattern(self):
        filtered = KeyFilter.filter_keys(self.discovered_keys, pattern=r"[a-z]+\d+")  # Match prices
        self.assertEqual(filtered, {
            'Widget X': ['product.catalog.item123.name'],
            "$19.99": ["product.catalog.item456.price"]
        })

    def test_filter_with_multiple_criteria(self):
        filtered = KeyFilter.filter_keys(
            self.discovered_keys, substring="product.catalog.item123", min_length=4, prefix="19"
        )
        self.assertEqual(filtered, {
            "Widget X": ["product.catalog.item123.name"],
            "$19.99": ["product.catalog.item456.price"]
        })

    def test_filter_with_include_false(self):
        filtered = KeyFilter.filter_keys(self.discovered_keys, substring="product", include_matches=False)
        self.assertEqual(filtered, {
            "John Doe": ["user.profile.name"],
            "johndoe@example.com": ["user.profile.email"],
            "en-US": ["system.settings.language"],
            "access_log_20240707.txt": ["system.logs.access"]
        })

if __name__ == '__main__':
    unittest.main(argv=[''], verbosity=2, exit=False)

