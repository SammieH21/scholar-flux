from scholar_flux import  SearchCoordinator, SearchAPI, DataCacheManager, DataExtractor
from scholar_flux.data import RecursiveDataProcessor

# core API for retrieving search information
search_api=SearchAPI(
    query='Econometric',
    provider_name='CORE',
    records_per_page=20,
    user_agent='SammieH',
    use_cache = True,
)
# orchestrates the full retrieval, processing, and caching pipeline
springer_search_coordinator = SearchCoordinator(search_api=search_api,
                                                cache_manager=DataCacheManager.with_storage('redis'),
                                                extractor=DataExtractor(),
                                                processor=RecursiveDataProcessor(value_delimiter = ';'))

# retrieves results for a page range - reference key value paired arguments from the original API to further customize
economic_results = springer_search_coordinator.search_pages([1, 2, 3, 4, 5], sort='createdDate')

if not economic_results:
    raise ValueError("Retrieval unsuccessful. No search results could be obtained...")

# join the full list of SearchResult objects into a singular dictionary
records_list = economic_results.join()
print(f"Total results: {len(records_list)}")


def get_abstract(record: dict, find: list | set | tuple = ('title', 'abstract', 'text', 'doi', "id", "date"))-> dict[str, str]:
    """Helper function for extracting relevant keys from nested components within records"""
    if not record:
        return {}

    abstract = {key: record_abstract for key, record_abstract in record.items()
                if any(key_type.lower() in str(key).lower() for key_type in find)}
    return abstract

# filter each record to keep only relevant keys
records_list = [get_abstract(record) for record in records_list]

# further exploration with pandas if installed
import pandas as pd
records_data_frame = pd.DataFrame(records_list)

# showing the results:
print(records_data_frame)
