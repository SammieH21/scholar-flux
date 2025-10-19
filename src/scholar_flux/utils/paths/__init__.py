# /utils/paths
"""The scholar_flux.utils.paths module contains a series of related classes that serve the purpose of providing a
unified interface for processing json paths in a manner that simplifies the implementation of nested values into paths
leading to terminal values (keys) and the terminal elements (values).

Modules:
    - processing_path.py:    Implements the ProcessingPath class which provides the basic building block for defining the
                              nested path location where terminal values are stored in structured json data consisting of
                              dictionaries, lists, and other nested elements.
    - path_nodes.py:          Implements a PathNode class where processing paths are paired with a `value` at its `path`
    - path_discoverer.py:     Defines the PathDiscoverer that recursively finds terminal paths up to a specific max depth.
                              This implementation is designed to create a dictionary by processing a json data structure to
                              create a new flattened dictionary consisting of terminal ProcessingPaths (keys) and their
                              associated data at these terminal paths (values).
    - processing_cache.py     Implements a caching mechanism using ProcessingPaths and weak references. The processing cache
                              uses lazy path additions and WeakKeyDictionaries implement a cache that store terminal path
                              references to ensure the efficient retrieval of path-node combinations.
    - path_node_map:          Defines validated PathNodeMap data structure built off a user dict to efficiently store
                              nodes found at terminal paths. This mapping also uses a generated a cache that uses `weakref`
                              to keep a running mapping of all terminal nodes.
    - record_path_chain_map:  Implements the RecordPathNodeMap that adds a mandatory record index to PathNodeMaps for consistency
                              when reading and manipulating JSON data nested within lists. The RecordPathChainMap is also implemented,
                              building on the RecordPathChainMap for increased consistency and faster retrieval of nodes associated with
                              particular records in a JSON data set. Operates as a drop-in replacement when used in a PathNodeIndex.
    - path_node_index:        Implements a PathNodeIndex data structure used to orchestrate the processing path-based
                              sparse trie data structures that take a JSON  and extract, flatten, and simplify the original
                              data structure to create an easy to process flattened dictionary.
    - path_simplifier         Implements the PathSimplifier utility class that takes a PathNodeIndex as input, identifies
                              unique paths (ignoring index) and simplifying the path into a flattened list that outputs
                              joined paths collapsed into string or flattened into a list.


Examples:
    >>> from scholar_flux.utils import PathNodeIndex
    >>> record_test_json: list[dict] = [
    >>>         {
    >>>             "authors": {
    >>>                 "principle_investigator": "Dr. Smith",
    >>>                 "assistant": "Jane Doe"
    >>>             },
    >>>             "doi": "10.1234/example.doi",
    >>>             "title": "Sample Study",
    >>>             "abstract": ["This is a sample abstract.", "keywords: 'sample', 'abstract'"],
    >>>             "genre": {
    >>>                 "subspecialty": "Neuroscience"
    >>>             },
    >>>             "journal": {
    >>>                 "topic": "Sleep Research"
    >>>             }
    >>>         },
    >>>         {
    >>>             "authors": {
    >>>                 "principle_investigator": "Dr. Lee",
    >>>                 "assistant": "John Roe"
    >>>             },
    >>>             "doi": "10.5678/example2.doi",
    >>>             "title": "Another Study",
    >>>             "abstract": "Another abstract.",
    >>>             "genre": {
    >>>                 "subspecialty": "Psychiatry"
    >>>             },
    >>>             "journal": {
    >>>                 "topic": "Dreams"
    >>>             }
    >>>         }
    >>>     ]
    ### Create a new index to process the current json
    >>> path_node_index = PathNodeIndex()
    # orchestrate the pipeline of identifying terminal paths and nodes, followed by formatting and flattening
    # the paths used to arrive at each value at the end of the terminal path.
    >>> normalized_records = path_node_index.normalize_records(record_test_json, object_delimiter = None)
    >>> print(normalized_records)
    # OUTPUT: [{'abstract': 'Another abstract.',
                'doi': '10.5678/example2.doi',
                'title': 'Another Study',
                'authors.assistant': 'John Roe',
                'authors.principle_investigator': 'Dr. Lee',
                'genre.subspecialty': 'Psychiatry',
                'journal.topic': 'Dreams'},
               {'doi': '10.1234/example.doi',
                'title': 'Sample Study',
                'abstract': ['This is a sample abstract.', "keywords: 'sample', 'abstract'"],
                'authors.assistant': 'Jane Doe',
                'authors.principle_investigator': 'Dr. Smith',
                'genre.subspecialty': 'Neuroscience',
                'journal.topic': 'Sleep Research'}]

"""
from scholar_flux.utils.paths.processing_path import ProcessingPath
from scholar_flux.utils.paths.processing_cache import PathProcessingCache
from scholar_flux.utils.paths.path_nodes import PathNode
from scholar_flux.utils.paths.path_simplification import PathSimplifier
from scholar_flux.utils.paths.path_discoverer import PathDiscoverer
from scholar_flux.utils.paths.path_node_map import PathNodeMap
from scholar_flux.utils.paths.record_path_chain_map import RecordPathNodeMap, RecordPathChainMap
from scholar_flux.utils.paths.path_node_index import PathNodeIndex
from scholar_flux.utils.module_utils import set_public_api_module

__all__ = [
    "ProcessingPath",
    "PathNode",
    "PathSimplifier",
    "PathDiscoverer",
    "PathProcessingCache",
    "PathNodeMap",
    "RecordPathNodeMap",
    "RecordPathChainMap",
    "PathNodeIndex",
]

set_public_api_module(__name__, __all__, globals())
