import pytest
from scholar_flux.api.models import ProcessedResponse
from scholar_flux.api import  SearchCoordinator, SearchAPI
import requests
def test_plos_api(plos_search_api):
    assert isinstance(plos_search_api, SearchAPI)
    response = plos_search_api.search(page=1)
    assert isinstance(response, requests.Response)

def test_plos_coordinator(plos_coordinator):
    assert isinstance(plos_coordinator, SearchCoordinator)
    response = plos_coordinator.search(page=2)
    assert isinstance(response, ProcessedResponse)
    assert len(response) > 1


