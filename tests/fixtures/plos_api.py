from scholar_flux.api import SearchCoordinator, SearchAPI
import pytest


@pytest.fixture
def plos_search_api()->SearchAPI:
    plos_search_api = SearchAPI.from_defaults( query='social wealth equity',
                                              provider_name='plos',
                                              records_per_page=100,
                                              user_agent='SammieH'
                                             )
    return plos_search_api

@pytest.fixture
def plos_coordinator(plos_search_api):
    coordinator = SearchCoordinator(search_api=plos_search_api)
    return coordinator

