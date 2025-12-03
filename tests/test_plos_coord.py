from scholar_flux.api.models import ProcessedResponse
from scholar_flux.api import SearchCoordinator, SearchAPI
import requests_mock
import requests


def test_plos_api(plos_search_api, plos_page_1_url, plos_page_1_data, plos_headers):
    """Verifies that, with requests_mock, the PLOS API can be successfully queried with `SearchAPI.search()`."""
    assert isinstance(plos_search_api, SearchAPI)

    with requests_mock.Mocker() as m:
        m.get(
            plos_page_1_url,
            json=plos_page_1_data,
            headers=plos_headers,
            status_code=200,
        )

        response = plos_search_api.search(page=1)
    assert isinstance(response, requests.Response)
    assert response.json() == plos_page_1_data


def test_plos_coordinator(plos_coordinator, plos_page_2_url, plos_page_2_data, plos_headers):
    """Verifies that, with requests_mock, the PLOS API can be successfully queried with `SearchCoordinator.search()`."""
    assert isinstance(plos_coordinator, SearchCoordinator)
    with requests_mock.Mocker() as m:
        m.get(
            plos_page_2_url,
            json=plos_page_2_data,
            headers=plos_headers,
            status_code=200,
        )
        response = plos_coordinator.search(page=2)
    assert isinstance(response, ProcessedResponse)
    assert len(response.data or []) == plos_coordinator.api.config.records_per_page

    assert response.data == plos_page_2_data["response"]["docs"]

    num_found = response.metadata.get("numFound") if response.metadata else None

    assert num_found and num_found == plos_page_2_data["response"]["numFound"]
    assert response.total_query_hits and int(num_found) == response.total_query_hits > 0
