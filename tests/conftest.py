from tests.fixtures.plos_api import plos_search_api, plos_coordinator
from tests.fixtures.config import (scholar_flux_logger, original_config_test_api_key,
                                   new_config_test_api_key, original_config, new_config,
                                   original_param_config, new_param_config,
                                  core_api_key, pubmed_api_key)

from tests.fixtures.response_simulation import (mock_response,
                                                mock_cache_storage_data,
                                                mock_academic_json_path,
                                                mock_pubmed_search_json_path,
                                                mock_pubmed_fetch_json_path,
                                                mock_academic_json,
                                                mock_academic_json_response,
                                                academic_json_response,
                                                mock_pubmed_search_data,
                                                mock_pubmed_fetch_data,
                                                mock_pubmed_search_endpoint,
                                                mock_pubmed_fetch_endpoint,
                                                mock_pubmed_search_response,
                                                mock_pubmed_fetch_response,
                                               )
from tests.fixtures.cleanup_utils import cleanup
from tests.fixtures.package_dependencies import *
from tests.fixtures.jsons import sample_json, mock_api_parsed_json_records

from tests.fixtures.mock_cache_session import (default_encryption_cache_session,
                                               default_secret_salt,
                                               default_secret_key,
                                               default_encryption_cache_session_manager,
                                               default_encryption_cache_filename,
                                               default_cache_directory,
                                               default_encryption_serializer_pipeline,
                                               incorrect_secret_salt,
                                               incorrect_secret_salt_encryption_cache_session_manager,
                                               sqlite_db_url
                                              )
from tests.fixtures.data_storage_classes import (redis_test_config,
                                                 storage_test_namespace,
                                                 mongo_test_config,
                                                 sqlite_test_config,
                                                 redis_test_storage, 
                                                 mongo_test_storage, 
                                                 mongo_nm_test_storage,
                                                 sqlite_test_storage, 
                                                 sqlite_nm_test_storage,
                                                 in_memory_test_storage, 
                                                 in_memory_nm_test_storage,
                                                 null_test_storage)
